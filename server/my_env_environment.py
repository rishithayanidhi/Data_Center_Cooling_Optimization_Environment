# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data Center Cooling Optimization Environment Implementation.

This file is kept for backwards compatibility.
The actual implementation is in environment.py
"""

# Forward imports for backwards compatibility
from .environment import DataCenterCoolingEnvironment as DataCenterCoolingEnvironment

# Legacy name support
MyEnvironment = DataCenterCoolingEnvironment

__all__ = ["DataCenterCoolingEnvironment", "MyEnvironment"]
