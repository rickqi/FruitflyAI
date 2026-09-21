#!/usr/bin/env python3
"""
P0-B1: Tests for Environment Protocol (VisionSource / MotorTarget).

Covers:
  - Interface compliance (abstract methods raise NotImplementedError)
  - SM64Bridge adapter wrappers
  - FlyGym adapter with spatial down-sampling
  - Integration: environment switching with --env flag
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environments.protocol import (
    VisionSource,
    MotorTarget,
    SM64BridgeVisionSource,
    SM64BridgeMotorTarget,
    FlyGymVisionSource,
    FlyGymMotorTarget,
)


# ── Mock bridge for SM64 adapter tests ─────────────────────────────────


class MockBridge:
    """Minimal mock that mimics the SM64 bridge API."""

    def __init__(self):
        self._last_control = None
        self._frame = np.zeros(1536, dtype=np.float32)

    def read_frame(self):
        return self._frame

    def write_control(self, x, y, jump=False, enabled=True):
        self._last_control = (x, y, jump, enabled)

    def close(self):
        self._frame = None


class MockCpgGait:
    """Minimal mock for the FlyGym CPG gait."""

    def __init__(self):
        self._forward_mod = 0.0
        self._turn_mod = 0.0

    def set_modulation(self, name: str, value: float):
        if name == "forward_mod":
            self._forward_mod = value
        elif name == "turn_mod":
            self._turn_mod = value

    def get_joint_angles(self):
        return np.zeros(42, dtype=np.float32)


# ── Test suite ──────────────────────────────────────────────────────────


class TestProtocolBaseClasses:
    """Verify that abstract base classes enforce the contract."""

    def test_vision_source_not_instantiable(self):
        with pytest.raises(TypeError):
            VisionSource()

    def test_motor_target_not_instantiable(self):
        with pytest.raises(TypeError):
            MotorTarget()


class TestSM64BridgeAdapter:
    """SM64 bridge adapters should transparently wrap the bridge."""

    def test_read_frame(self):
        bridge = MockBridge()
        bridge._frame = np.full(1536, 0.5, dtype=np.float32)
        source = SM64BridgeVisionSource(bridge)
        frame = source.read_frame()
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (1536,)
        assert np.allclose(frame, 0.5)

    def test_write_control(self):
        bridge = MockBridge()
        target = SM64BridgeMotorTarget(bridge)
        ctrl = np.array([40.0, 60.0], dtype=np.float32)
        target.write_control(ctrl)
        assert bridge._last_control is not None
        # SM64 bridge expects list/tuple; adapter calls .tolist()
        assert bridge._last_control[0] == 40.0
        assert bridge._last_control[1] == 60.0

    def test_close_propagates(self):
        bridge = MockBridge()
        source = SM64BridgeVisionSource(bridge)
        source.close()
        assert bridge._frame is None  # our mock sets None on close


class TestFlyGymAdapter:
    """FlyGym adapters with spatial down-sampling."""

    def _make_env(self):
        """Return a minimal observation dict as a mock env."""
        return _MockFlyGymEnv()

    def test_vision_source_reads_luminance(self):
        env = _MockFlyGymEnv()
        source = FlyGymVisionSource(env)
        frame = source.read_frame()
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (1536,)
        assert frame.dtype == np.float32
        assert np.all(frame >= 0.0)

    def test_vision_source_after_reset(self):
        env = _MockFlyGymEnv()
        source = FlyGymVisionSource(env)
        source.reset()
        frame = source.read_frame()
        assert frame.shape == (1536,)
        assert frame.sum() > 0  # reset populates raw_vision

    def test_motor_target_writes_control(self):
        env = _MockFlyGymEnv()
        gait = MockCpgGait()
        target = FlyGymMotorTarget(env, gait)
        ctrl = np.array([40.0, 60.0], dtype=np.float32)
        target.write_control(ctrl)
        assert gait._forward_mod == pytest.approx(60.0 / 80.0)
        assert gait._turn_mod == pytest.approx(40.0 / 80.0)

    def test_spatial_downsample_preserves_variation(self):
        """The down-sampler should not collapse to a constant."""
        env = _MockFlyGymEnv(variation=True)
        source = FlyGymVisionSource(env)
        source.reset()
        frame = source.read_frame()
        assert frame.max() > frame.min() + 0.01  # some variation survived


class TestEnvironmentSwitching:
    """The --env flag abstraction should allow clean switching."""

    def test_switch_does_not_crash(self):
        bridge = MockBridge()
        sm64 = SM64BridgeVisionSource(bridge)
        sm64.read_frame()  # no error

        env = _MockFlyGymEnv()
        fly = FlyGymVisionSource(env)
        fly.read_frame()  # no error

    def test_control_interface_consistent_shape(self):
        bridge = MockBridge()
        sm64_target = SM64BridgeMotorTarget(bridge)
        sm64_target.write_control(np.array([0, 50], dtype=np.float32))

        env = _MockFlyGymEnv()
        gait = MockCpgGait()
        fly_target = FlyGymMotorTarget(env, gait)
        fly_target.write_control(np.array([0, 50], dtype=np.float32))
        # Both adapters accept the same (2,) control vector


# ── Mock environment for FlyGym adapter tests ──────────────────────────


class _MockFlyGymEnv:
    """Minimal mock that mimics a FlyGym SingleFlySimulation."""

    def __init__(self, variation: bool = False):
        self._variation = variation
        self._obs = None

    def reset(self, seed=None):
        # Create a synthetic raw_vision frame: (2, 512, 450, 3)
        raw = np.zeros((2, 512, 450, 3), dtype=np.uint8)
        if self._variation:
            # Add a gradient so down-sampler sees something
            raw[0, :, :, 0] = np.linspace(0, 255, 450, dtype=np.uint8)[None, :]
            raw[1, :, :, 0] = np.linspace(255, 0, 450, dtype=np.uint8)[None, :]
        else:
            raw[:, :, :, :] = 128  # mid-gray
        self._obs = {"raw_vision": raw}
        return self._obs, {}

    def step(self, action):
        raw = np.full((2, 512, 450, 3), 100, dtype=np.uint8)
        self._obs = {"raw_vision": raw}
        return self._obs, 0.0, False, False, {}

    def close(self):
        self._obs = None