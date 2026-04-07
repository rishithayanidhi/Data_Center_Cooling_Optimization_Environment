# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Data Center Cooling Optimization Environment."""

from .client import DataCenterCoolingEnv, CoolingEnv
from .models import CoolingAction, CoolingObservation, CoolingState

__all__ = [
    # Models
    "CoolingAction",
    "CoolingObservation",
    "CoolingState",
    
    # Client
    "DataCenterCoolingEnv",
    "CoolingEnv",  # Alias for backwards compatibility
]

# Version
__version__ = "1.0.0"
__description__ = "Autonomous Data Center Cooling Optimization Environment"
