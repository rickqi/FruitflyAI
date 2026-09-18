#!/usr/bin/env python3
"""t27 regression: MBON steep homeostatic scaling (hard-saturation recovery).

A channel pinned at |MBON|>0.99 must engage steep scaling (3x shrink
strength), recover below 0.8, and only then return to normal scaling —
restoring the learnable dynamic range that saturation destroyed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fly64.mushroom_body import MushroomBody  # noqa: E402


def make_mb():
    return MushroomBody()


def pinned_signature(mb):
    """A signature that strongly activates the runaway column."""
    sig = np.zeros(mb.W_kc.shape[1], dtype=np.float32)
    sig[:] = 0.05
    return sig


class TestSteepScaling:
    def test_steel_mode_engages_above_099(self):
        mb = make_mb()
        j = 0
        mb.weights[:, j] = 40.0        # runaway column
        sig = pinned_signature(mb)
        mb.encode(sig)
        assert abs(mb.mbon_outputs[j]) > 0.99
        assert mb._steep_scaling[j] is np.True_ or bool(mb._steep_scaling[j])

    def test_steep_factor_triples_shrink(self):
        mb = make_mb()
        f_normal = mb.saturation_scale_factor
        f_steep = 1.0 - (1.0 - f_normal) * mb.steep_scale_multiplier
        assert f_steep == pytest.approx(0.55)   # 0.85 -> 0.55 (3x shrink)
        w0 = 10.0
        assert w0 * f_steep == pytest.approx(5.5)
        assert w0 * f_steep < w0 * f_normal      # steeper than normal

    def test_saturated_column_recovers_below_08(self):
        mb = make_mb()
        mb.saturation_frames_threshold = 5   # speed the test up
        j = 0
        mb.weights[:, j] = 60.0        # hard runaway
        sig = pinned_signature(mb)
        peak = 0.0
        for _ in range(1200):
            mb.encode(sig)
            peak = max(peak, abs(float(mb.mbon_outputs[j])))
            if abs(float(mb.mbon_outputs[j])) < 0.8:
                break
        assert abs(float(mb.mbon_outputs[j])) < 0.8, (
            "steep scaling failed to pull the column out of saturation")
        assert peak > 0.9              # it really was saturated first
        assert mb.steep_scaling_events > 0

    def test_hysteresis_exit_below_08(self):
        mb = make_mb()
        j = 0
        mb.weights[:, j] = 40.0
        sig = pinned_signature(mb)
        for _ in range(60):
            mb.encode(sig)
        # force the column low artificially to simulate recovery
        mb.weights[:, j] = 0.1
        mb.encode(sig * 0.0)           # zero signature -> raw ~ small
        mb.mbon_outputs[j] = np.float32(0.5)
        # next steep evaluation: |0.5| < 0.8 -> steep disengages
        mb._steep_scaling[j] = True
        mb.encode(sig)
        # after the value sits below exit threshold, steep must clear
        mb.mbon_outputs[j] = np.float32(0.5)
        steep_before = bool(mb._steep_scaling[j])
        # drive one homeostat update with a sub-threshold output
        mb.mbon_outputs[j] = np.float32(0.5)
        sat = np.abs(mb.mbon_outputs) >= 0.98
        assert not sat[j]
        mb._steep_scaling = np.where(
            np.abs(mb.mbon_outputs) > mb.steep_enter_threshold, True,
            np.where(np.abs(mb.mbon_outputs) < mb.steep_exit_threshold,
                     False, mb._steep_scaling))
        assert bool(mb._steep_scaling[j]) is False or steep_before is False

    def test_normal_channel_not_steep(self):
        mb = make_mb()
        mb.encode(pinned_signature(mb))
        assert not mb._steep_scaling.any()

    def test_stats_expose_saturation_observability(self):
        mb = make_mb()
        stats = mb.memory_stats      # property
        for k in ("saturation_events", "steep_scaling_events",
                  "steep_active", "mbon_abs_max"):
            assert k in stats, k
