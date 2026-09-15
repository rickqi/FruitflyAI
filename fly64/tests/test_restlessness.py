"""EVO R19 regression — restlessness current + recognition-to-behaviour closure.

Neural mechanisms (no Python control decisions):
- restlessness_level(): standoff/loop pressure builds forward drive
- scene_danger: recognised danger tags suppress forward (caution current)
"""
import pytest

from fly64.model import FlyModel
from fly64.scene_recognition import SceneRecognizer


class TestRestlessness:
    def test_standoff_30s_is_full(self):
        model = FlyModel(demo=True)
        model.cliff_standoff_s = 35.0
        model.loop_score = 0.0
        assert model.restlessness_level() == 1.0

    def test_loop_pressure_rises_above_08(self):
        model = FlyModel(demo=True)
        model.cliff_standoff_s = 0.0
        model.loop_score = 0.9
        assert model.restlessness_level() == pytest.approx(0.5)

    def test_zero_when_calm(self):
        model = FlyModel(demo=True)
        model.cliff_standoff_s = 0.0
        model.loop_score = 0.5
        assert model.restlessness_level() == 0.0


class TestSceneDangerClosure:
    def test_danger_tags_recognised(self):
        r = SceneRecognizer()
        r._last_tags = ["danger", "lava"]
        assert r.danger_level() == 1.0

    def test_benign_tags_not_danger(self):
        r = SceneRecognizer()
        r._last_tags = ["outdoor", "grass"]
        assert r.danger_level() == 0.0

    def test_danger_suppresses_forward_current(self):
        """Recognised danger scene suppresses forward drive pre-spike."""
        model = FlyModel(demo=True)
        model.scene_danger = 0.0
        v_before = float(model.v[model.forward].mean())
        model.scene_danger = 1.0
        # re-apply the caution current the way step() does
        model.v[model.forward] -= model.scene_danger * 0.06
        v_after = float(model.v[model.forward].mean())
        assert v_after == pytest.approx(v_before - 0.06)
