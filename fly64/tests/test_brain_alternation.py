"""EVO R14 regression — brain-model loop suppression & scene recognition.

All mechanisms are neural (no Python control decisions):
- TurnAdaptation: turn-circuit fatigue → spontaneous-alternation counter-drive
- DAN punishment: circling-family anomaly states gate dopamine for the
  mushroom body's three-factor learning
- color_signature: P1a 5-channel colour scene codes feed the Kenyon Cells
"""
import pytest

from fly64.memory import MotionStateDetector
from fly64.model import FlyModel, TurnAdaptation


# ── TurnAdaptation · spontaneous alternation dynamics ─────────────────

class TestTurnAdaptation:
    def test_sustained_left_fatigues_left_and_counter_drives_right(self):
        ta = TurnAdaptation()
        for _ in range(150):                      # 3 s of left-turn activity
            ta.update(0.5, 0.0, 0.02)
        to_right, to_left = ta.counter_drive()
        assert ta.left > ta.right
        assert to_right == pytest.approx(ta.gain)  # full counter toward right
        assert to_left == 0.0                      # no fatigue on right circuit

    def test_counter_drive_flips_after_direction_change(self):
        ta = TurnAdaptation()
        for _ in range(150):
            ta.update(0.5, 0.0, 0.02)             # left phase
        for _ in range(300):                      # right phase (2× longer)
            ta.update(0.0, 0.5, 0.02)
        to_right, to_left = ta.counter_drive()
        assert to_left > 0.0                      # now right is fatigued
        assert to_right < to_left                 # counter has flipped

    def test_fatigue_decays_when_turning_stops(self):
        ta = TurnAdaptation()
        for _ in range(150):
            ta.update(0.5, 0.0, 0.02)
        for _ in range(600):                      # 12 s idle
            ta.update(0.0, 0.0, 0.02)
        assert ta.left < 0.05 and ta.right < 0.05

    def test_reset_clears_both(self):
        ta = TurnAdaptation()
        ta.update(0.5, 0.5, 0.02)
        ta.reset()
        assert ta.left == 0.0 and ta.right == 0.0

    def test_alternation_emerges_over_alternating_phases(self):
        """Left phase → counter toward right grows → right phase → flips back.

        This is the anti-circling property: sustained turning automatically
        seeds the opposite direction (spontaneous alternation).
        """
        ta = TurnAdaptation()
        seen = []
        for phase in range(6):
            act = (0.4, 0.0) if phase % 2 == 0 else (0.0, 0.4)
            for _ in range(150):
                ta.update(act[0], act[1], 0.02)
            to_right, to_left = ta.counter_drive()
            seen.append("R" if to_right > to_left else "L")
        # counter-drive alternates R, L, R, L, ... as fatigue hands over
        assert seen[0] == "R" and seen[1] == "L"
        assert all(a != b for a, b in zip(seen, seen[1:]))


# ── DAN dopamine · circling punishment ────────────────────────────────

class TestDanPunishment:
    def test_micro_loop_gates_negative_dopamine(self):
        model = FlyModel(demo=True)
        model.anomaly_state_name = "micro_loop"
        assert model._compute_dopamine() <= -0.35

    def test_stuck_ramp_gates_negative_dopamine(self):
        model = FlyModel(demo=True)
        model.anomaly_state_name = "stuck_ramp"
        assert model._compute_dopamine() <= -0.35

    def test_idle_state_not_punished_by_anomaly_term(self):
        model = FlyModel(demo=True)
        model.anomaly_state_name = "idle"
        # fresh demo model: no stuck/fallen/cliff/looming → no punishment
        assert model._compute_dopamine() >= 0.0


# ── Colour scene signature · MB discrimination ────────────────────────

class TestColourSceneSignature:
    def test_color_signature_enabled_by_default(self):
        model = FlyModel(demo=True)
        assert model.color_signature is True
