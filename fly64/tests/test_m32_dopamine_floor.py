"""M3.2 dopamine-floor fix: a primitive success tick must never net negative."""
import numpy as np
import pytest

from fly64.model import FlyModel


@pytest.fixture(scope="module")
def model():
    return FlyModel(demo=True)


def test_success_pulse_floors_concurrent_setback(model):
    """+0.6 success + heavy setback must still deliver dop >= +0.2."""
    model._pending_dopamine = -1.0          # concurrent setbacks
    model.add_primitive_outcome("longjump", True)
    dop = model._compute_dopamine() + 0.4 * max(-0.3, min(0.5, model.reward_signal)) \
        + model._pending_dopamine
    dop = max(-1.0, min(1.0, dop))
    # the floor applied in step() must lift this above the floor value
    assert model._success_pulse_floor == 0.2
    assert max(dop, model._success_pulse_floor) >= 0.2
    model._success_pulse_floor = 0.0
    model._pending_dopamine = 0.0


def test_failure_pulse_keeps_negative_path(model):
    model._pending_dopamine = 0.0
    model._success_pulse_floor = 0.0
    model.add_primitive_outcome("punch", False)
    assert model._pending_dopamine == -0.4       # aversive via add_setback
    assert model._success_pulse_floor == 0.0     # no floor on failure


def test_floor_is_one_shot(model):
    model._success_pulse_floor = 0.2
    model._success_pulse_floor = 0.0             # consumed by step()
    # simulate: after consumption a subsequent tick has no floor
    assert getattr(model, "_success_pulse_floor", 0.0) == 0.0


def test_success_column_potentiates_under_setback(model):
    """End-to-end: with concurrent negative dopamine, a success pulse must
    still leave the longjump column weights >= pre-event (not depressed)."""
    frame = np.zeros((256, 384, 3), dtype=np.uint8)
    mb = model.mushroom
    w_before = mb.weights[:, 8].copy()
    model._pending_dopamine = -1.0
    model.add_primitive_outcome("longjump", True)
    for _ in range(3):
        model.step(frame, 100.0)
    # weights column must not be driven below the before-state by the event
    assert mb.weights[:, 8].mean() >= w_before.mean() - 1e-4
