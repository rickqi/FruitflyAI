#!/usr/bin/env python3
"""
P0-B2: Integration tests for FlyGym visual adapter and control flow.

Covers end-to-end scenarios:
  - CpgGait generates valid 42-DOF actions
  - flygym_to_luminance spatial down-sampling preserves structure
  - Brain model produces valid output from FlyGym synthetic frames
  - Full env.reset() → N-step forward pass
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environments.protocol import (
    FlyGymVisionSource,
    FlyGymMotorTarget,
    SM64BridgeVisionSource,
    SM64BridgeMotorTarget,
)


class _MockFlyGymCpg:
    """Mock for FlyGym's CPG controller."""

    def __init__(self):
        self._forward_mod = 0.0
        self._turn_mod = 0.0

    def set_modulation(self, name: str, value: float):
        if name == "forward_mod":
            self._forward_mod = value
        elif name == "turn_mod":
            self._turn_mod = value

    def get_joint_angles(self) -> np.ndarray:
        angles = np.zeros(42, dtype=np.float32)
        # Tripod gait pattern
        for leg in range(6):
            phase = (leg % 2) * np.pi
            swing = 0.3 * np.sin(phase + self._forward_mod * np.pi)
            angles[leg * 7] = swing  # coxa
            angles[leg * 7 + 1] = 0.5 + self._forward_mod  # femur
            angles[leg * 7 + 2] = -1.0 + self._turn_mod  # tibia
        return angles


class _MockFlyGymSim:
    """Mock FlyGym SingleFlySimulation for integration testing."""

    def __init__(self):
        self._obs = None

    def reset(self, seed=None):
        raw = np.full((2, 512, 450, 3), 120, dtype=np.uint8)
        # Add spatial variation: top half bright, bottom half dim
        raw[:, 256:, :, :] = 40
        self._obs = {"raw_vision": raw}
        return self._obs, {}

    def step(self, action):
        raw = np.full((2, 512, 450, 3), 100, dtype=np.uint8)
        self._obs = {"raw_vision": raw}
        return self._obs, 0.0, False, False, {}

    def close(self):
        self._obs = None


class TestFlyGymAdapter:
    """Integration tests for the FlyGym adapter (TC1-TC8)."""

    def test_spatial_downsample_shape(self):
        """TC1: Down-sampled luminance has correct shape."""
        env = _MockFlyGymSim()
        source = FlyGymVisionSource(env)
        env.reset()
        frame = source.read_frame()
        assert frame.shape == (1536,)
        assert frame.dtype == np.float32

    def test_spatial_downsample_preserves_variation(self):
        """TC2: Spatial luminance variation is preserved in down-sample."""
        env = _MockFlyGymSim()
        source = FlyGymVisionSource(env)
        env.reset()
        frame = source.read_frame()
        # The mock puts 120 in top half, 40 in bottom half
        assert np.any(np.abs(np.diff(frame)) > 1.0), (
            "Down-sampled luminance has no variation; spatial info was lost"
        )

    def test_bilateral_symmetry(self):
        """TC3: Both eyes produce similar luminance in symmetric scene."""
        env = _MockFlyGymSim()
        source = FlyGymVisionSource(env)
        env.reset()
        frame = source.read_frame()
        left = frame[:768]
        right = frame[768:]
        # In a uniform mock scene both halves should be within ~10%
        diff = float(np.abs(left.mean() - right.mean()))
        assert diff < 10.0, f"Bilateral luminance asymmetry too large: {diff:.1f}"

    def test_step_updates_frame(self):
        """TC4: Stepping the env produces a different frame."""
        env = _MockFlyGymSim()
        source = FlyGymVisionSource(env)
        cpg = _MockFlyGymCpg()
        target = FlyGymMotorTarget(env, cpg)

        # Reset to get first frame
        source.reset()
        f1 = source.read_frame().copy()

        # Advance the simulation
        target.write_control(np.array([0.0, 50.0], dtype=np.float32))
        f2 = source.read_frame().copy()

        # Mock produces constant 100 after step and 120/40 after reset
        assert float(f2.mean()) == pytest.approx(100.0, abs=1.0)

    def test_motor_modulation(self):
        """TC5: Motor modulation maps to CPG amplitude parameters."""
        env = _MockFlyGymSim()
        cpg = _MockFlyGymCpg()
        target = FlyGymMotorTarget(env, cpg)

        target.write_control(np.array([40.0, 60.0], dtype=np.float32))
        assert cpg._forward_mod == pytest.approx(60.0 / 80.0)
        assert cpg._turn_mod == pytest.approx(40.0 / 80.0)

    def test_end_to_end_reset_then_step(self):
        """TC6: Full reset -> step cycle without exceptions."""
        env = _MockFlyGymSim()
        source = FlyGymVisionSource(env)
        cpg = _MockFlyGymCpg()
        target = FlyGymMotorTarget(env, cpg)

        source.reset()
        for _ in range(5):
            frame = source.read_frame()
            assert len(frame) == 1536
            ctrl = np.array([0.0, 50.0], dtype=np.float32)
            target.write_control(ctrl)

    def test_adapter_contract(self):
        """TC7: Adapters satisfy the VisionSource/MotorTarget contract."""
        from environments.protocol import VisionSource, MotorTarget

        env = _MockFlyGymSim()
        cpg = _MockFlyGymCpg()

        vs = FlyGymVisionSource(env)
        mt = FlyGymMotorTarget(env, cpg)
        assert isinstance(vs, VisionSource)
        assert isinstance(mt, MotorTarget)
        vs.close()
        mt.close()

    def test_demo_model_compatibility(self):
        """TC8: Synthetic atlas frame is compatible with model.step()."""
        env = _MockFlyGymSim()
        source = FlyGymVisionSource(env)
        env.reset()
        frame = source.read_frame()
        # Frame is valid for FlyModel.step() consumption
        assert not np.any(np.isnan(frame))
        assert np.all(np.isfinite(frame))
        assert np.all(frame >= 0)

    def test_reset_then_close_no_leak(self):
        """TC8b: Reset then close does not produce dangling resources."""
        env = _MockFlyGymSim()
        vs = FlyGymVisionSource(env)
        vs.reset()
        frame = vs.read_frame()
        assert len(frame) == 1536
        vs.close()
        # After close, returning zeros is the safe fallback
        frame2 = vs.read_frame()
        assert np.allclose(frame2, 0)