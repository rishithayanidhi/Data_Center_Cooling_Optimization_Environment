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

import math
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


class DataCenterCoolingEnvironment(Environment):
    """
    Simulates a data center cooling management task.
    
    The environment models a 4-zone data center where an agent must manage
    cooling levels to maintain safe temperatures while minimizing energy consumption.
    
    State space:
    - 4 Zone temperatures (°C)
    - 4 Zone workload intensities (0.0-1.0)
    - 4 Zone cooling levels (0.0-1.0)
    
    Action space:
    - Adjust cooling in one zone by [-1, 0, +1] (or continuous in [-1, 1])
    - Choose zone (0-3)
    
    Reward signal:
    - Penalty for overheating (T > 50°C)
    - Reward for stability
    - Penalty for excessive cooling
    - Reward for energy efficiency
    """
    
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    
    # Physics constants
    NUM_ZONES = 4
    AMBIENT_TEMPERATURE = 20.0
    SAFE_TEMPERATURE_MIN = 15.0
    SAFE_TEMPERATURE_MAX = 45.0
    CRITICAL_TEMPERATURE = 50.0
    
    # Thermal dynamics
    THERMAL_CAPACITANCE = 10.0  # How fast temperature changes
    COOLING_EFFICIENCY = 5.0  # How effective is cooling
    WORKLOAD_TO_HEAT = 20.0  # How much heat workload generates
    
    # Energy
    BASE_POWER = 50.0  # Base power in kW
    COOLING_POWER_PER_UNIT = 8.0  # kW per unit of cooling
    
    # Time scales
    TIME_STEP_DURATION = 1.0  # Simulation step = 1 minute
    
    def __init__(self, task_type: str = "easy"):
        """
        Initialize the data center cooling environment.
        
        Args:
            task_type: Type of task - "easy", "medium", or "hard"
        """
        self.task_type = task_type
        self._episode_id = str(uuid4())
        self._step_count = 0
        
        # Episode length matches evaluation window (judges run 50 steps per task)
        # All tasks run 50 steps; difficulty varies via workload + initial temps
        self._max_steps = 50
        
        # Initialize state
        self._zone_temperatures = [25.0] * self.NUM_ZONES
        self._zone_cooling_levels = [0.5] * self.NUM_ZONES
        self._zone_workload_intensity = [self._get_initial_workload() for _ in range(self.NUM_ZONES)]
        
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
        self._episode_id = str(uuid4())
        self._step_count = 0
        self._step_index = 0
        self._thermal_violations = 0
        self._cumulative_energy = 0.0
        self._cumulative_reward = 0.0
        
        # Initialize temperatures based on task difficulty
        # Harder tasks start with warmer, more challenging conditions
        if self.task_type == "easy":
            initial_temp = 30.0  # Cool start, agent has some breathing room
        elif self.task_type == "medium":
            initial_temp = 35.0  # Moderate start, immediate management needed
        else:  # hard
            initial_temp = 38.0  # Hot start, agent must respond quickly to avoid overheat
        
        # Add some randomness to make each episode slightly different
        self._zone_temperatures = [
            initial_temp + np.random.uniform(-2, 2) for _ in range(self.NUM_ZONES)
        ]
        
        # Start with moderate cooling (agent must adjust)
        self._zone_cooling_levels = [0.4] * self.NUM_ZONES
        self._zone_workload_intensity = [self._get_initial_workload() for _ in range(self.NUM_ZONES)]
        
        return self._get_observation()
    
    def step(self, action: CoolingAction) -> CoolingObservation:  # type: ignore[override]
        """
        Execute one step of the environment.
        
        Args:
            action: CoolingAction with zone and cooling adjustment
            
        Returns:
            CoolingObservation with updated state
        """
        self._step_count += 1
        self._step_index += 1
        
        # Apply the action
        actions_applied = [(action.zone_id, action.cooling_adjustment)]
        self._update_temperatures(actions_applied)
        
        # Calculate reward
        reward, _ = self._calculate_reward()
        self._cumulative_reward += reward
        
        # Check if episode is done
        done = self._step_count >= self._max_steps or max(self._zone_temperatures) > 70.0
        
        obs = self._get_observation()
        obs.done = done
        obs.reward = reward
        
        return obs
    
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
