"""Verification environment package for Fly64 brain model.

Provides alternative simulation environments to the primary SM64 interface,
enabling verification of the brain model's visual processing and motor
control in a second scenario (P3-2 contract).

Exports abstract protocol classes (VisionSource, MotorTarget) and concrete
SM64 bridge adapters, plus the FlyGym-based verification environment.
"""

from __future__ import annotations

from .protocol import (
    CHANNELS,
    HEIGHT,
    MotorTarget,
    SM64BridgeMotorTarget,
    SM64BridgeVisionSource,
    VisionSource,
    WIDTH,
)
from .flygym_env import FlyGymBrainEnv

__all__ = [
    "VisionSource",
    "MotorTarget",
    "SM64BridgeVisionSource",
    "SM64BridgeMotorTarget",
    "FlyGymBrainEnv",
    "WIDTH",
    "HEIGHT",
    "CHANNELS",
]