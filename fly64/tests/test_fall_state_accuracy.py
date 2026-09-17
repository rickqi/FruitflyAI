"""R31-fix4: accurate fall-state detection — altitude alone is not a fall."""
import pytest

from fly64.memory import StuckDetector


def _det(**kw):
    return StuckDetector(**kw)


def _run(det, ys, forward_rate=10.0, temporal=0.5, dt_ticks=1):
    """Feed a y sequence; return (fallen_flags, last)."""
    flags = []
    t = 0
    for y in ys:
        for _ in range(dt_ticks):
            sc, dur, fallen = det.update(temporal, t, forward_rate, y)
            flags.append(fallen)
            t += 1
    return flags, flags[-1]


def test_standing_on_high_ground_is_not_fallen():
    """The core mislabel: legal platforms at y>500 must never read fallen."""
    d = _det()
    _, last = _run(d, [600.0] * 20)
    assert last is False
    assert d.fallen is False


def test_sustained_descent_is_falling():
    d = _det()
    ys = [500.0 - i * 10.0 for i in range(12)]        # -500 u/s descent
    flags, last = _run(d, ys)
    assert last is True
    assert any(flags)


def test_single_tick_dip_is_debounced_out():
    """A single-tick downward VELOCITY spike is debounced out."""
    d = _det()
    ys = [120.0] * 10 + [70.0] + [120.0] * 10        # 1-tick fast dip (2500 u/s? no:
    # 70 is above floor 50 -> not below_floor; velocity term needs 3 ticks
    flags, last = _run(d, ys)
    assert last is False                              # debounce held


def test_below_floor_sustained_is_fallen():
    d = _det()
    ys = [-150.0] * 15
    flags, last = _run(d, ys)
    assert last is True


def test_high_ground_brief_descent_not_fallen():
    """y>500 with only gentle motion (|vz|<120) is standing, not falling."""
    d = _det()
    ys = [600.0 + (i % 3) for i in range(15)]        # jitter ~33 u/s
    flags, last = _run(d, ys)
    assert last is False


def test_recovery_after_landing():
    d = _det()
    _run(d, [500.0 - i * 10.0 for i in range(12)])   # fall
    flags, last = _run(d, [120.0] * 20)              # landed
    assert last is False
