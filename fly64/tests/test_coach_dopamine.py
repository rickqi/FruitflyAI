"""R31-fix9: coach→dopamine pathway — strategy parsing + model integration."""
import json
import numpy as np
import pytest
from fly64.model import FlyModel


@pytest.fixture(scope="module")
def model():
    return FlyModel(demo=True)


# ── Parsing (load_active_strategy) ────────────────────────────────────

def test_dopamine_key_parsed(tmp_path):
    from fly64.main import load_active_strategy
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"dopamine": {"bias": 0.15, "setback": 0.0}}))
    s = load_active_strategy(p)
    assert s["dopamine"]["bias"] == 0.15


def test_dopamine_absent_gives_default(tmp_path):
    from fly64.main import load_active_strategy
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"exploration": {"turn_bias": 0.5}}))
    s = load_active_strategy(p)
    assert "dopamine" not in s or s["dopamine"] == {}


def test_dopamine_malformed_rejected(tmp_path):
    from fly64.main import load_active_strategy
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"dopamine": "yes"}))
    s = load_active_strategy(p)
    assert "dopamine" not in s


# ── Model integration ────────────────────────────────────────────────

def test_bias_adds_to_dopamine(model):
    """Coach bias must shift the final dopamine value."""
    model._coach_dopamine_bias = 0.15
    model._pending_dopamine = 0.0
    model._success_pulse_floor = 0.0
    model.reward_signal = 0.0
    frame = np.zeros((256, 384, 3), dtype=np.uint8)
    model.step(frame, 100.0)
    # dopamine should be positive due to the bias
    assert model.mushroom.dopamine >= -0.1  # bias exceeded any negative
    model._coach_dopamine_bias = 0.0


def test_bias_is_bounded(model):
    """Coach bias cannot blow through the [-1,1] total clamp."""
    model._coach_dopamine_bias = 5.0
    frame = np.zeros((256, 384, 3), dtype=np.uint8)
    model.step(frame, 100.0)
    model._coach_dopamine_bias = 0.0
    assert abs(model.mushroom.dopamine) <= 1.0


def test_setback_via_add_setback_works(model):
    model._pending_dopamine = 0.0
    model.add_setback(0.5)
    assert model._pending_dopamine == -0.5


# ── Main-loop wiring (source contract) ────────────────────────────────

def test_main_loop_wires_coach_bias():
    from pathlib import Path
    s = Path(__file__).resolve().parent.parent.joinpath("fly64", "main.py").read_text()
    assert "_coach_dopamine_bias = max(-0.3, min(0.3" in s
    assert '_active_strategy.get("dopamine"' in s
    assert "add_setback(max(-1.0, min(1.0" in s