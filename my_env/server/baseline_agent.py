# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Baseline Rule-Based Agent for Data Center Cooling Optimization.

This agent implements simple heuristic-based cooling management:
- Monitor temperature relative to safe limits
- Increase cooling if temperature is too high
- Decrease cooling if temperature is too low
- Balance cooling across zones
"""

import random
from typing import List, Tuple
import numpy as np

try:
    from ..models import CoolingAction, CoolingObservation
except ImportError:
    from models import CoolingAction, CoolingObservation


class BaselineAgent:
    """
    Simple rule-based agent for data center cooling management.
    
    Strategy:
    1. Monitor each zone's temperature
    2. If temperature > SAFE_MAX: increase cooling
    3. If temperature < SAFE_MIN: decrease cooling
    4. If temperature in range: maintain current cooling
    5. Prefer balanced cooling across all zones
    """
    
    SAFE_TEMPERATURE_MIN = 18.0  # °C
    SAFE_TEMPERATURE_MAX = 42.0  # °C
    WARNING_TEMPERATURE = 40.0   # °C
    CRITICAL_TEMPERATURE = 48.0  # °C
    
    def __init__(self, zone_count: int = 4, strategy: str = "conservative"):
        """
        Initialize the baseline agent.
        
        Args:
            zone_count: Number of cooling zones
            strategy: Type of control strategy
                - "reactive": Simple threshold-based
                - "conservative": Preemptive cooling increase
                - "aggressive": Fast response to changes
        """
        self.zone_count = zone_count
        self.strategy = strategy
        self.previous_temps = [None] * zone_count
        self.step_count = 0
    
    def select_action(self, observation: CoolingObservation) -> CoolingAction:
        """
        Select cooling action based on observation.
        
        Args:
            observation: Current environment state
            
        Returns:
            CoolingAction to apply
        """
        self.step_count += 1
        
        # Select zone with largest temperature deviation
        zone_id, adjustment = self._select_zone_and_adjustment(observation)
        
        return CoolingAction(
            zone_id=zone_id,
            cooling_adjustment=adjustment,
            duration=1
        )
    
    def _select_zone_and_adjustment(
        self, observation: CoolingObservation
    ) -> Tuple[int, float]:
        """
        Determine which zone to adjust and by how much.
        
        Args:
            observation: Current environment state
            
        Returns:
            Tuple of (zone_id, adjustment_value)
        """
        temps = observation.zone_temperatures
        current_cooling = observation.zone_cooling_levels
        
        # Find zone with most problematic temperature
        zone_issues = []
        for i, temp in enumerate(temps):
            # Measure deviation from safe range
            if temp > self.SAFE_TEMPERATURE_MAX:
                deviation = temp - self.SAFE_TEMPERATURE_MAX
                priority = 2.0 + deviation  # Highest priority
            elif temp < self.SAFE_TEMPERATURE_MIN:
                deviation = self.SAFE_TEMPERATURE_MIN - temp
                priority = -1.0 - deviation  # Decrease cooling
            else:
                # In safe range - maintain
                priority = 0.5
            
            zone_issues.append((i, priority, temp))
        
        # Apply strategy
        if self.strategy == "reactive":
            zone_id, _, temp = max(zone_issues, key=lambda x: abs(x[1]))
            adjustment = self._calculate_adjustment_reactive(temp)
        
        elif self.strategy == "conservative":
            zone_id, _, temp = max(zone_issues, key=lambda x: abs(x[1]))
            adjustment = self._calculate_adjustment_conservative(temp, current_cooling[zone_id])
        
        else:  # aggressive
            zone_id, _, temp = max(zone_issues, key=lambda x: abs(x[1]))
            adjustment = self._calculate_adjustment_aggressive(temp, current_cooling[zone_id])
        
        return zone_id, adjustment
    
    def _calculate_adjustment_reactive(self, temperature: float) -> float:
        """Simple threshold-based adjustment."""
        if temperature > self.CRITICAL_TEMPERATURE:
            return 0.8  # Maximum increase
        elif temperature > self.WARNING_TEMPERATURE:
            return 0.5  # Significant increase
        elif temperature > self.SAFE_TEMPERATURE_MAX:
            return 0.3  # Moderate increase
        elif temperature < self.SAFE_TEMPERATURE_MIN:
            return -0.3  # Decrease cooling
        else:
            return 0.0  # Maintain
    
    def _calculate_adjustment_conservative(self, temperature: float, current_cooling: float) -> float:
        """Preemptive cooling increase to prevent overheating."""
        if temperature > self.CRITICAL_TEMPERATURE:
            return 1.0  # Maximum increase
        elif temperature > self.WARNING_TEMPERATURE:
            return 0.6  # Preemptive increase
        elif temperature > self.SAFE_TEMPERATURE_MAX:
            return 0.4  # Early response
        elif temperature < self.SAFE_TEMPERATURE_MIN - 2:
            return -0.5  # Aggressive decrease
        elif temperature < self.SAFE_TEMPERATURE_MIN:
            return -0.2  # Gradual decrease
        else:
            return 0.1  # Slight preemptive increase
    
    def _calculate_adjustment_aggressive(self, temperature: float, current_cooling: float) -> float:
        """Fast response to temperature changes."""
        temp_diff = temperature - (self.SAFE_TEMPERATURE_MAX + self.SAFE_TEMPERATURE_MIN) / 2
        
        # Response magnitude proportional to deviation
        if abs(temp_diff) > 10:
            adjustment = 0.9 if temp_diff > 0 else -0.7
        elif abs(temp_diff) > 5:
            adjustment = 0.6 if temp_diff > 0 else -0.4
        elif abs(temp_diff) > 2:
            adjustment = 0.3 if temp_diff > 0 else -0.2
        else:
            adjustment = 0.0
        
        return adjustment
    
    def get_name(self) -> str:
        """Get agent name for logging."""
        return f"BaselineAgent({self.strategy})"


class SmartBaselineAgent(BaselineAgent):
    """
    Enhanced baseline agent with zone balancing.
    
    Improvements over basic agent:
    - Considers temperature variance across zones
    - Tries to balance cooling distribution
    - Tracks long-term trends
    """
    
    def __init__(self, zone_count: int = 4):
        """Initialize smart baseline agent."""
        super().__init__(zone_count, strategy="conservative")
        self.temp_history = [[] for _ in range(zone_count)]
        self.history_size = 10
    
    def _select_zone_and_adjustment(
        self, observation: CoolingObservation
    ) -> Tuple[int, float]:
        """
        Select zone and adjustment considering balancing.
        
        Args:
            observation: Current environment state
            
        Returns:
            Tuple of (zone_id, adjustment_value)
        """
        temps = observation.zone_temperatures
        current_cooling = observation.zone_cooling_levels
        
        # Update history
        for i, temp in enumerate(temps):
            self.temp_history[i].append(temp)
            if len(self.temp_history[i]) > self.history_size:
                self.temp_history[i].pop(0)
        
        # Find zone with highest temperature
        max_zone = np.argmax(temps)
        max_temp = temps[max_zone]
        
        # Consider temperature trend
        if len(self.temp_history[max_zone]) > 1:
            trend = self.temp_history[max_zone][-1] - self.temp_history[max_zone][0]
        else:
            trend = 0
        
        # Adjust based on current state and trend
        if max_temp > self.CRITICAL_TEMPERATURE or (max_temp > self.WARNING_TEMPERATURE and trend > 0):
            adjustment = 0.7
        elif max_temp > self.SAFE_TEMPERATURE_MAX:
            adjustment = 0.4
        elif max_temp < self.SAFE_TEMPERATURE_MIN and trend < 0:
            adjustment = -0.4
        elif max_temp < self.SAFE_TEMPERATURE_MIN:
            adjustment = -0.2
        else:
            adjustment = 0.1
        
        return max_zone, adjustment
    
    def get_name(self) -> str:
        """Get agent name for logging."""
        return "SmartBaselineAgent"


def run_baseline_evaluation(
    env_client,
    num_episodes: int = 5,
    agent_type: str = "smart",
) -> dict:
    """
    Run baseline agent for evaluation.
    
    Args:
        env_client: Environment client instance
        num_episodes: Number of episodes to run
        agent_type: Type of baseline agent ("smart" or "reactive")
        
    Returns:
        Dictionary with evaluation results
    """
    if agent_type == "smart":
        agent = SmartBaselineAgent(zone_count=4)
    else:
        agent = BaselineAgent(zone_count=4, strategy="conservative")
    
    results = {
        "agent": agent.get_name(),
        "episodes": [],
        "avg_reward": 0.0,
        "avg_violations": 0,
        "avg_energy": 0.0,
    }
    
    episode_rewards = []
    episode_violations = []
    episode_energies = []
    
    for episode_idx in range(num_episodes):
        obs_result = env_client.reset()
        observation = obs_result.observation
        state = obs_result
        
        episode_reward = 0.0
        episode_violations = 0
        episode_energy = 0.0
        
        for step in range(500):  # Max 500 steps per episode
            # Agent selects action
            action = agent.select_action(observation)
            
            # Step environment
            result = env_client.step(action)
            observation = result.observation
            step_reward = result.reward or 0.0
            
            episode_reward += step_reward
            episode_violations += 1 if max(observation.zone_temperatures) > 50.0 else 0
            episode_energy += observation.total_energy_consumption
            
            if result.done:
                break
        
        results["episodes"].append({
            "episode": episode_idx,
            "reward": episode_reward,
            "violations": episode_violations,
            "energy": episode_energy,
        })
        
        episode_rewards.append(episode_reward)
        episode_violations.append(episode_violations)
        episode_energies.append(episode_energy)
    
    # Calculate averages
    if episode_rewards:
        results["avg_reward"] = np.mean(episode_rewards)
        results["avg_violations"] = np.mean(episode_violations)
        results["avg_energy"] = np.mean(episode_energies)
    
    return results
