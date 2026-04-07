# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Data Center Cooling Optimization Environment.

This environment simulates autonomous cooling management for data centers,
where agents learn to balance thermal stability and energy efficiency.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from openenv.core.env_server.types import Action, Observation, State


class CoolingAction(Action):
    """
    Action for cooling management.
    
    Agents can adjust cooling levels across different zones in the data center.
    """
    
    zone_id: int = Field(..., description="Zone ID (0-3 for 4 zones)")
    cooling_adjustment: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Cooling adjustment: -1.0 (decrease), 0.0 (maintain), +1.0 (increase)"
    )
    duration: int = Field(default=1, description="Duration in simulation steps")


class CoolingObservation(Observation):
    """
    Observation from the data center cooling environment.
    
    Provides real-time metrics about temperatures, workload, and energy.
    """
    
    # Temperature readings (Celsius)
    zone_temperatures: List[float] = Field(
        default_factory=list,
        description="Current temperature in each zone (4 zones)"
    )
    
    # Workload metrics
    zone_workload_intensity: List[float] = Field(
        default_factory=list,
        description="CPU/workload intensity per zone (0.0-1.0)"
    )
    
    # Cooling metrics
    zone_cooling_levels: List[float] = Field(
        default_factory=list,
        description="Current cooling distribution per zone (0.0-1.0)"
    )
    
    # Energy metrics
    total_energy_consumption: float = Field(
        default=0.0,
        description="Current power consumption in kW"
    )
    
    # Ambient conditions
    ambient_temperature: float = Field(
        default=20.0,
        description="Ambient temperature (Celsius)"
    )
    
    # Global state
    timestamp: int = Field(default=0, description="Simulation step count")
    task_name: str = Field(default="", description="Current task (easy/medium/hard)")
    
    # Performance metrics
    max_temperature: float = Field(default=0.0, description="Max temperature across zones")
    min_temperature: float = Field(default=0.0, description="Min temperature across zones")
    temperature_variance: float = Field(
        default=0.0,
        description="Variance in temperatures (lower = more stable)"
    )


class CoolingState(State):
    """
    Episode state metadata.
    
    Contains information about the current episode and performance metrics.
    """
    
    episode_id: str = Field(default="", description="Unique episode identifier")
    step_count: int = Field(default=0, description="Current step in episode")
    task_type: str = Field(
        default="easy",
        description="Task difficulty: easy, medium, or hard"
    )
    max_steps: int = Field(default=1000, description="Maximum steps in episode")
    
    # Performance tracking
    total_reward: float = Field(default=0.0, description="Cumulative reward")
    thermal_violations: int = Field(default=0, description="Number of overheating events")
    energy_consumed: float = Field(default=0.0, description="Total energy consumed (kWh)")
    
    # Episode metadata
    workload_profile: str = Field(
        default="constant",
        description="Workload pattern: constant, fluctuating, or spike"
    )
    initial_temperatures: List[float] = Field(
        default_factory=list,
        description="Initial temperatures at episode start"
    )
