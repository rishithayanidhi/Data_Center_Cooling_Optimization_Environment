# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Data Center Cooling Optimization Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from .models import CoolingAction, CoolingObservation, CoolingState


class DataCenterCoolingEnv(
    EnvClient[CoolingAction, CoolingObservation, CoolingState]
):
    """
    Client for the Data Center Cooling Optimization Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server (easy task)
        >>> with DataCenterCoolingEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(f"Initial temps: {result.observation.zone_temperatures}")
        ...
        ...     # Increase cooling in zone 0
        ...     action = CoolingAction(zone_id=0, cooling_adjustment=0.5)
        ...     result = client.step(action)
        ...     print(f"New temps: {result.observation.zone_temperatures}")
        ...     print(f"Reward: {result.reward}")

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = DataCenterCoolingEnv.from_docker_image("datacenter-cooling:latest")
        >>> try:
        ...     result = client.reset()
        ...     action = CoolingAction(zone_id=1, cooling_adjustment=0.3)
        ...     result = client.step(action)
        ... finally:
        ...     client.close()

    Example with task selection:
        >>> # Connect to hard task
        >>> import os
        >>> os.environ["TASK_TYPE"] = "hard"
        >>> with DataCenterCoolingEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
    """

    def _step_payload(self, action: CoolingAction) -> Dict:
        """
        Convert CoolingAction to JSON payload for step message.

        Args:
            action: CoolingAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "zone_id": action.zone_id,
            "cooling_adjustment": action.cooling_adjustment,
            "duration": getattr(action, 'duration', 1),
        }

    def _parse_result(self, payload: Dict) -> StepResult[CoolingObservation]:
        """
        Parse server response into StepResult[CoolingObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with CoolingObservation
        """
        obs_data = payload.get("observation", {})
        observation = CoolingObservation(
            zone_temperatures=obs_data.get("zone_temperatures", []),
            zone_workload_intensity=obs_data.get("zone_workload_intensity", []),
            zone_cooling_levels=obs_data.get("zone_cooling_levels", []),
            total_energy_consumption=obs_data.get("total_energy_consumption", 0.0),
            ambient_temperature=obs_data.get("ambient_temperature", 20.0),
            timestamp=obs_data.get("timestamp", 0),
            task_name=obs_data.get("task_name", ""),
            max_temperature=obs_data.get("max_temperature", 0.0),
            min_temperature=obs_data.get("min_temperature", 0.0),
            temperature_variance=obs_data.get("temperature_variance", 0.0),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> CoolingState:
        """
        Parse server response into CoolingState object.

        Args:
            payload: JSON response from state request

        Returns:
            CoolingState object with episode metadata
        """
        return CoolingState(
            episode_id=payload.get("episode_id", ""),
            step_count=payload.get("step_count", 0),
            task_type=payload.get("task_type", "easy"),
            max_steps=payload.get("max_steps", 500),
            total_reward=payload.get("total_reward", 0.0),
            thermal_violations=payload.get("thermal_violations", 0),
            energy_consumed=payload.get("energy_consumed", 0.0),
            workload_profile=payload.get("workload_profile", "constant"),
            initial_temperatures=payload.get("initial_temperatures", []),
        )


# Alias for backwards compatibility
CoolingEnv = DataCenterCoolingEnv
