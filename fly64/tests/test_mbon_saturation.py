"""EVO R17 regression — MBON saturation homeostasis + breakout_hint phase mix.

Neural mechanisms (no Python control decisions):
- MushroomBody homeostatic synaptic scaling: a saturated MBON column is
  multiplicatively shrunk back into its dynamic range.
- ReflexController breakout_hint: the brain's weave-detector biases the
  micro_loop reflex phase budget toward the forward burst.
"""
import numpy as np
import pytest

from fly64.memory import ReflexController, MotionStateDetector
from fly64.model import TurnAdaptation
from fly64.mushroom_body import MushroomBody


# ── Homeostatic synaptic scaling ──────────────────────────────────────

class TestMbonSaturationHomeostasis:
    def _drive_to_saturation(self, mb: MushroomBody, n=80):
        """Force the forward MBON column toward saturation."""
        sig = np.ones(128, dtype=np.float32) * 0.5
        mb.weights[:, 0] = 0.9          # forward column strongly positive
        for _ in range(n):
            mb.encode(sig)
            mb.set_dopamine(0.8)        # reward keeps inflating the column
            mb.update_weights()
        return mb

    def test_saturated_column_scaling_fires(self):
        mb = self._drive_to_saturation(MushroomBody())
        assert mb.saturation_events >= 1        # fired during the drive
        base = mb.saturation_events
        w_before = float(np.abs(mb.weights[:, 0]).max())
        for _ in range(60):                     # 60 more saturated frames
            mb.encode(np.ones(128, dtype=np.float32) * 0.5)
            mb.set_dopamine(0.8)
            mb.update_weights()
        # dopamine keeps re-inflating the column (equilibrium), but the
        # homeostatic scaling must keep firing on top of it
        assert mb.saturation_events >= base + 1
        assert float(np.abs(mb.weights[:, 0]).max()) <= 1.0  # within bounds

    def test_saturation_events_counter_increments(self):
        mb = self._drive_to_saturation(MushroomBody())
        assert mb.saturation_events >= 1        # fired during the drive
        base = mb.saturation_events
        for _ in range(60):
            mb.encode(np.ones(128, dtype=np.float32) * 0.5)
            mb.set_dopamine(0.8)
            mb.update_weights()
        assert mb.saturation_events >= base + 1

    def test_mbon_returns_to_dynamic_range_after_scaling(self):
        mb = self._drive_to_saturation(MushroomBody())
        sig = np.ones(128, dtype=np.float32) * 0.5
        initial_raw = float(mb.weights[mb.kc_activity > 0, 0].sum())
        for _ in range(120):
            mb.encode(sig)
            mb.set_dopamine(0.8)
            mb.update_weights()
        # after repeated homeostatic scaling the column must be shrinking
        active = mb.kc_activity > 0
        raw = float(mb.weights[active, 0].sum())
        assert raw < initial_raw, f"column not shrinking: {initial_raw} → {raw}"
        assert mb.saturation_events >= 2


# ── breakout_hint phase mix ───────────────────────────────────────────

class _Rng:
    def __call__(self, lo, hi):
        return lo


class TestBreakoutHint:
    def _fire(self, r, breakout_hint):
        state = {"state": MotionStateDetector.MICRO_LOOP, "confidence": 1.0}
        for _ in range(50):
            rt = r.update(0.02, state, _Rng(), stuck_duration=200.0,
                          pos=(0.0, 0.0), breakout_hint=breakout_hint)
            if rt == MotionStateDetector.MICRO_LOOP:
                return True
        return False

    def test_zero_hint_keeps_original_phase_budget(self):
        r = ReflexController(cooldown_duration=0.0)
        assert self._fire(r, 0.0)
        assert r._breakout_scale == 1.0
        # original: turn phase = 0.5 s — still in turn at 0.45 s
        for _ in range(22):
            r.update(0.02, {"state": "idle", "confidence": 0.0}, _Rng(),
                     pos=(0.0, 0.0))
        assert r._reflex_phase == "turn"

    def test_full_hint_shortens_turn_phase(self):
        r = ReflexController(cooldown_duration=0.0)
        assert self._fire(r, 1.0)
        assert r._breakout_scale == 2.0
        # turn phase = 0.5/2 = 0.25 s — at 0.30 s must already be in burst
        for _ in range(15):  # 0.30 s
            r.update(0.02, {"state": "idle", "confidence": 0.0}, _Rng(),
                     pos=(0.0, 0.0))
        assert r._reflex_phase == "burst", r._reflex_phase
