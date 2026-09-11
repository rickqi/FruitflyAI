import numpy as np

from fly64.model import FlyModel


def frame(left=0, right=0):
    value = np.zeros((256, 384, 3), np.uint8)
    value[:, :192] = left
    value[:, 192:] = right
    return value


def test_retina_responds_to_luminance_and_change():
    model = FlyModel(demo=True)
    dark = model.encode_retina(frame(0, 0))
    bright_change = model.encode_retina(frame(255, 255))
    assert dark.mean() == 0
    assert bright_change.mean() > 0.9


def test_deterministic_spikes():
    a, b = FlyModel(demo=True, seed=10), FlyModel(demo=True, seed=10)
    image = frame(30, 220)
    for i in range(30):
        ca, sa = a.step(image, now=i * a.dt)
        cb, sb = b.step(image, now=i * b.dt)
        np.testing.assert_array_equal(sa, sb)
        assert ca == cb


def test_controls_are_bounded_and_jump_debounced():
    model = FlyModel(demo=True)
    model.activity[model.forward] = 1
    model.activity[model.turn_right] = 1
    model.activity[model.jump_nodes] = 1
    control, _ = model.step(frame(255, 255), now=1.0)
    assert -70 <= control.x <= 70
    assert 0 <= control.y <= 70
    if control.jump:
        second, _ = model.step(frame(255, 255), now=1.1)
        assert not second.jump
