# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data Center Cooling Optimization Environment Implementation.

This environment simulates a realistic data center cooling management task where
agents learn to balance thermal stability and energy efficiency.
"""

import logging
import math
import os
import sys
from pathlib import Path
from uuid import uuid4
from typing import List, Dict, Tuple

import numpy as np
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from models import CoolingAction, CoolingObservation, CoolingState
except ImportError:
    try:
        from ..models import CoolingAction, CoolingObservation, CoolingState
    except ImportError:
        from models import CoolingAction, CoolingObservation, CoolingState

log = logging.getLogger("environment")


class DataCenterCoolingEnvironment(Environment):
    """
    Simulates a data center cooling management task.

    The environment models a configurable-zone data center where an agent must manage
    cooling levels to maintain safe temperatures while minimizing energy consumption.

    Physics constants are read from environment variables at class-definition time so
    they can be overridden without modifying source code.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    # Physics constants — all overridable via environment variables
    NUM_ZONES: int = int(os.getenv("NUM_ZONES", "4"))
    AMBIENT_TEMPERATURE: float = float(os.getenv("AMBIENT_TEMPERATURE", "20.0"))
    SAFE_TEMPERATURE_MIN: float = float(os.getenv("SAFE_TEMPERATURE_MIN", "15.0"))
    SAFE_TEMPERATURE_MAX: float = float(os.getenv("SAFE_TEMPERATURE_MAX", "45.0"))
    CRITICAL_TEMPERATURE: float = float(os.getenv("CRITICAL_TEMPERATURE", "50.0"))

    # Thermal dynamics
    THERMAL_CAPACITANCE: float = float(os.getenv("THERMAL_CAPACITANCE", "10.0"))
    COOLING_EFFICIENCY: float = float(os.getenv("COOLING_EFFICIENCY", "5.0"))
    WORKLOAD_TO_HEAT: float = float(os.getenv("WORKLOAD_TO_HEAT", "20.0"))

    # Energy
    BASE_POWER: float = float(os.getenv("BASE_POWER", "50.0"))
    COOLING_POWER_PER_UNIT: float = float(os.getenv("COOLING_POWER_PER_UNIT", "8.0"))

    # Time scales
    TIME_STEP_DURATION: float = float(os.getenv("TIME_STEP_DURATION", "1.0"))

    def __init__(self, task_type: str = "easy") -> None:
        """
        Initialize the data center cooling environment.

        Args:
            task_type: Type of task — "easy", "medium", or "hard".
                       Can also be set via TASK_TYPE env var.
        """
        self.task_type = os.getenv("TASK_TYPE", task_type).lower()
        if self.task_type not in ("easy", "medium", "hard"):
            log.warning("Unknown task_type '%s'; defaulting to 'easy'", self.task_type)
            self.task_type = "easy"

        self._episode_id = str(uuid4())
        self._step_count = 0

        # Episode length — judges run 50 steps per task; overridable for local testing
        self._max_steps = int(os.getenv("MAX_EPISODE_STEPS", "50"))

        log.info(
            "DataCenterCoolingEnvironment init — task=%s max_steps=%d zones=%d",
            self.task_type, self._max_steps, self.NUM_ZONES,
        )

        try:
            # Initialize state
            self._zone_temperatures: List[float] = [25.0] * self.NUM_ZONES
            self._zone_cooling_levels: List[float] = [0.5] * self.NUM_ZONES
            self._zone_workload_intensity: List[float] = [
                self._get_initial_workload() for _ in range(self.NUM_ZONES)
            ]
        except Exception as exc:
            log.error("Failed to initialise environment state: %s", exc)
            raise

        # Tracking
        self._thermal_violations = 0
        self._cumulative_energy = 0.0
        self._cumulative_reward = 0.0
        
        # For physics
        self._step_index = 0
        
    def _get_initial_workload(self) -> float:
        """Get initial workload based on task type."""
        if self.task_type == "easy":
            return 0.5  # Constant moderate load
        elif self.task_type == "medium":
            return 0.6  # Slightly higher
        else:  # hard
            return 0.4  # Variable
    
    def _generate_workload(self, step: int) -> List[float]:
        """
        Generate workload for each zone based on task type and time.
        Creates dynamic heat generation to test agent's cooling management.
        
        Args:
            step: Current simulation step
            
        Returns:
            List of workload intensities [0, 1] for each zone
        """
        workloads = []
        
        for zone in range(self.NUM_ZONES):
            if self.task_type == "easy":
                # Moderate constant workload - requires agent to maintain cooling
                base = 0.7  # Increased from 0.5
                # Add gentle variation by zone for realistic behavior
                base += 0.05 * math.sin(step * 0.02 + zone * 0.5)
                
            elif self.task_type == "medium":
                # Fluctuating workload with clear peaks and valleys
                base = 0.65 + 0.2 * math.sin(step * 0.05 + zone * 0.5)
                # Occasional activity spikes
                if step % 50 == 0:
                    base += 0.2
                    
            else:  # hard
                # Challenging: unpredictable spikes and difficult patterns
                base = 0.5
                # Random spikes that agents must respond to quickly
                if step % 40 == 0 and step > 0:
                    base += 0.4  # Significant thermal spike
                # Multiple harmonic patterns to prevent simple solutions
                base += 0.2 * math.sin(step * 0.1 + zone * 0.3)
                base += 0.1 * math.sin(step * 0.03 + zone * 1.5)
            
            # Clamp to [0, 1]
            workloads.append(max(0.0, min(1.0, base)))
        
        return workloads
    
    def _update_temperatures(self, actions_applied: List[Tuple[int, float]]) -> None:
        """
        Update zone temperatures based on workload, cooling, and physics.
        
        Args:
            actions_applied: List of (zone_id, cooling_adjustment) tuples
        """
        # Get current workload
        workloads = self._generate_workload(self._step_index)
        self._zone_workload_intensity = workloads
        
        # Apply cooling adjustments
        for zone_id, cooling_adj in actions_applied:
            zone_id = int(zone_id)
            change = cooling_adj * 0.1  # Max 10% change per step
            self._zone_cooling_levels[zone_id] = max(0.0, min(1.0, 
                self._zone_cooling_levels[zone_id] + change))
        
        # Update temperatures for each zone
        for zone in range(self.NUM_ZONES):
            # Heat generation from workload
            heat_generated = workloads[zone] * self.WORKLOAD_TO_HEAT
            
            # Cooling effect
            cooling_effect = self._zone_cooling_levels[zone] * self.COOLING_EFFICIENCY
            
            # Net heat flow
            net_heat = heat_generated - cooling_effect
            
            # Temperature change (simplified thermal dynamics)
            temp_change = net_heat / self.THERMAL_CAPACITANCE
            
            # Update temperature with thermal dissipation toward ambient
            T = self._zone_temperatures[zone]
            ambient_diff = self.AMBIENT_TEMPERATURE - T
            dissipation = 0.1 * ambient_diff  # Natural cooling
            
            self._zone_temperatures[zone] = T + temp_change + dissipation
            
            # Clamp to reasonable range
            self._zone_temperatures[zone] = max(10.0, 
                min(70.0, self._zone_temperatures[zone]))
    
    def _calculate_reward(self) -> Tuple[float, Dict]:
        """
        Calculate reward based on environment state.
        
        CRITICAL: Reward must vary meaningfully to distinguish good from bad actions
        Returns:
            Tuple of (reward_value, reward_breakdown)
        """
        reward_breakdown = {}
        total_reward = 0.0
        
        # Get current state metrics
        mean_temp = np.mean(self._zone_temperatures)
        max_temp = max(self._zone_temperatures)
        min_temp = min(self._zone_temperatures)
        temp_variance = np.var(self._zone_temperatures)
        
        # ===== THERMAL PERFORMANCE (PRIMARY REWARD) =====
        # This is the main signal: how well you're keeping temps in safe range
        
        if max_temp > self.CRITICAL_TEMPERATURE:
            # MASSIVE PENALTY for critical overheat (>50°C)
            overheat_severity = min(20.0, (max_temp - self.CRITICAL_TEMPERATURE) / 2.0)
            thermal_reward = -1.0 * min(1.0, overheat_severity)  # -1.0 to 0.0
            self._thermal_violations += 1
            
        elif max_temp > self.SAFE_TEMPERATURE_MAX:
            # LARGE PENALTY for overheating (45-50°C)
            excess_heat = (max_temp - self.SAFE_TEMPERATURE_MAX) / 5.0  # 0-1
            thermal_reward = -0.8 * excess_heat  # -0.8 to 0.0
            
        elif max_temp < self.SAFE_TEMPERATURE_MIN:
            # MEDIUM PENALTY for overcooling (<15°C)
            undercool = (self.SAFE_TEMPERATURE_MIN - max_temp) / 10.0
            thermal_reward = -0.3 * undercool  # -0.3 to 0.0
            
        else:
            # GOOD ZONE: Reward based on distance from ideal
            # Ideal = 35°C (middle of safe range)
            ideal_temp = 35.0
            temp_error = abs(mean_temp - ideal_temp)
            
            # Normalize error (0-10°C error -> 0-1)
            normalized_error = min(1.0, temp_error / 10.0)
            
            # Thermal reward: 0.7 max (when perfect), 0.0 at boundaries
            thermal_reward = 0.7 * (1.0 - normalized_error)
            
            # Bonus for low variance (zones stable with each other)
            # Variance should be < 5 for good thermal distribution
            normalized_variance = min(1.0, temp_variance / 10.0)
            variance_bonus = 0.2 * (1.0 - normalized_variance)
            thermal_reward += variance_bonus
        
        reward_breakdown["thermal"] = thermal_reward
        total_reward += thermal_reward
        
        # ===== ENERGY EFFICIENCY (SECONDARY REWARD) =====
        # Reward for efficient cooling: don't over-cool
        avg_cooling = np.mean(self._zone_cooling_levels)
        total_cooling = sum(self._zone_cooling_levels)
        
        # Only apply energy penalty if temps are well-managed
        if thermal_reward > -0.5:
            # Penalty for excessive cooling (>0.7 average is wasteful)
            if avg_cooling > 0.7:
                excess_cooling = (avg_cooling - 0.7) / 0.3
                energy_penalty = -0.15 * min(1.0, excess_cooling)
            else:
                # Reward for efficient cooling (between 0.3-0.7)
                efficiency = 1.0 - abs(avg_cooling - 0.5) / 0.5
                energy_penalty = 0.1 * max(0.0, efficiency - 0.5)
            
            reward_breakdown["energy"] = energy_penalty
            total_reward += energy_penalty
        
        # ===== BALANCED COOLING BONUS =====
        # Reward for keeping all zones similar temp (good coordination)
        if temp_variance < 3.0:
            coordination_bonus = 0.1
            reward_breakdown["coordination"] = coordination_bonus
            total_reward += coordination_bonus
        
        # ===== FINAL CLIPPING =====
        # Ensure reward is in [-1, 1] and normalize to [0, 1] for judges
        total_reward = np.clip(total_reward, -1.0, 1.0)
        
        # Normalize to [0.0, 1.0] range for judge compatibility
        # Map: -1.0 -> 0.0, 0.0 -> 0.5, 1.0 -> 1.0
        normalized_reward = (total_reward + 1.0) / 2.0
        
        reward_breakdown["total"] = normalized_reward
        return normalized_reward, reward_breakdown
    
    def reset(self) -> CoolingObservation:
        """
        Reset the environment for a new episode.

        Returns:
            CoolingObservation with initial state
        """
        try:
            self._episode_id = str(uuid4())
            self._step_count = 0
            self._step_index = 0
            self._thermal_violations = 0
            self._cumulative_energy = 0.0
            self._cumulative_reward = 0.0

            # Initial temperatures vary by task difficulty
            initial_temp_map = {
                "easy": float(os.getenv("INITIAL_TEMP_EASY", "30.0")),
                "medium": float(os.getenv("INITIAL_TEMP_MEDIUM", "35.0")),
                "hard": float(os.getenv("INITIAL_TEMP_HARD", "38.0")),
            }
            initial_temp = initial_temp_map.get(self.task_type, 30.0)

            self._zone_temperatures = [
                initial_temp + np.random.uniform(-2, 2) for _ in range(self.NUM_ZONES)
            ]
            self._zone_cooling_levels = [0.4] * self.NUM_ZONES
            self._zone_workload_intensity = [
                self._get_initial_workload() for _ in range(self.NUM_ZONES)
            ]

            log.info(
                "reset — episode=%s task=%s initial_temps=%s",
                self._episode_id, self.task_type,
                [round(t, 1) for t in self._zone_temperatures],
            )
            return self._get_observation()
        except Exception as exc:
            log.error("reset failed: %s", exc, exc_info=True)
            raise
    
    def step(self, action: CoolingAction) -> CoolingObservation:  # type: ignore[override]
        """
        Execute one step of the environment.

        Args:
            action: CoolingAction with zone and cooling adjustment

        Returns:
            CoolingObservation with updated state
        """
        try:
            self._step_count += 1
            self._step_index += 1

            actions_applied = [(action.zone_id, action.cooling_adjustment)]
            self._update_temperatures(actions_applied)

            reward, breakdown = self._calculate_reward()
            self._cumulative_reward += reward

            done = (
                self._step_count >= self._max_steps
                or max(self._zone_temperatures) > 70.0
            )

            log.debug(
                "step=%d zone=%d adj=%.2f reward=%.4f done=%s max_temp=%.1f",
                self._step_count, action.zone_id, action.cooling_adjustment,
                reward, done, max(self._zone_temperatures),
            )

            obs = self._get_observation()
            obs.done = done
            obs.reward = reward
            return obs

        except Exception as exc:
            log.error("step %d failed: %s", self._step_count, exc, exc_info=True)
            raise
    
    def _get_observation(self) -> CoolingObservation:
        """
        Generate observation from current state.
        
        Returns:
            CoolingObservation with current metrics
        """
        max_temp = max(self._zone_temperatures)
        min_temp = min(self._zone_temperatures)
        temp_variance = np.var(self._zone_temperatures)
        
        return CoolingObservation(
            zone_temperatures=self._zone_temperatures.copy(),
            zone_workload_intensity=self._zone_workload_intensity.copy(),
            zone_cooling_levels=self._zone_cooling_levels.copy(),
            total_energy_consumption=self.BASE_POWER + sum(self._zone_cooling_levels) * self.COOLING_POWER_PER_UNIT / 10.0,
            ambient_temperature=self.AMBIENT_TEMPERATURE,
            timestamp=self._step_count,
            task_name=self.task_type,
            max_temperature=max_temp,
            min_temperature=min_temp,
            temperature_variance=temp_variance,
        )
    
    @property
    def state(self) -> CoolingState:
        """
        Get the current episode state.
        
        Returns:
            CoolingState with episode metadata
        """
        return CoolingState(
            episode_id=self._episode_id,
            step_count=self._step_count,
            task_type=self.task_type,
            max_steps=self._max_steps,
            total_reward=self._cumulative_reward,
            thermal_violations=self._thermal_violations,
            energy_consumed=self._cumulative_energy,
            workload_profile={
                "easy": "constant",
                "medium": "fluctuating", 
                "hard": "spike"
            }.get(self.task_type, "constant"),
            initial_temperatures=[25.0] * self.NUM_ZONES,
        )
