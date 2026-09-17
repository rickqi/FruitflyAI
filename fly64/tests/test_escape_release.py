#!/usr/bin/env python3
"""t23 regression: escape release lockup triple fix.

① release cooldown 1800s -> 60s, and a NEW anomaly activation clears it
   immediately; ② _fallen bypasses the release/cooldown gate (fall recovery
   can never be muted); ③ stuck_score no longer pinned at 1.0 by fallen —
   it decays once displacement resumes, letting loop_score fall.

Uses a patched memory.time.monotonic clock to fast-forward through the
cooldown without sleeping.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import fly64.memory as mem  # noqa: E402
from fly64.memory import MemoryController, StuckDetector  # noqa: E402


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt
        return self.t


def make_controller(clock):
    mc = MemoryController()
    # Replace the whole module-level time reference (not just monotonic on
    # the shared stdlib module) so leaked fakes from other test files can
    # never skew the cooldown arithmetic.
    mem.time = types.SimpleNamespace(monotonic=clock)
    return mc


def tick_fallen(mc, clock, n=2):
    """Drive ticks while 'fallen' (y far below map)."""
    out = None
    for i in range(n):
        clock.advance(0.02)
        out = mc.update(temporal_energy=0.5, frame_seq=i, forward_rate=20.0,
                        x=0.0, z=0.0, pos_y=-500.0)
    return out


def tick_normal(mc, clock, n=2, x=0.0, z=0.0):
    out = None
    for i in range(n):
        clock.advance(0.02)
        out = mc.update(temporal_energy=0.5, frame_seq=1000 + i,
                        forward_rate=30.0, x=x, z=z, pos_y=50.0)
    return out


def oscillate(mc, clock, n=40, low_rate=True):
    """Drive control.x oscillation — activates the 'oscillating' anomaly.

    n=40 flushes the detector's 30-sample majority window with oscillating
    votes so the state becomes active.  low_rate=True also reduces the
    forward rate so stuck conditions are met alongside oscillation."""
    out = None
    seq = 2000
    rate = 5.0 if low_rate else 30.0
    for i in range(n):
        clock.advance(0.02)
        seq += 1
        out = mc.update(temporal_energy=0.5, frame_seq=seq,
                        forward_rate=rate, x=0.0, z=0.0, pos_y=50.0,
                        control_x=60 if i % 2 == 0 else -60)
    return out


@pytest.fixture()
def clock(monkeypatch):
    c = FakeClock(1000.0)
    monkeypatch.setattr(mem.time, "monotonic", c)
    return c


class TestCooldownFix:
    def test_fallen_triggers_escape_immediately(self, clock):
        mc = make_controller(clock)
        out = tick_fallen(mc, clock)
        assert out[3] is True and out[4] is True

    def test_release_then_fallen_still_escapes(self, clock):
        # fix②: after the release window fires, a continuing fallen state
        # KEEPS escape alive (bypass), and cooldown starts anyway.
        mc = make_controller(clock)
        tick_fallen(mc, clock)
        clock.t += 61.0                       # _escape_s > 60 -> release
        out = tick_fallen(mc, clock)
        assert mc._escape_released_at == clock.t
        assert out[3] is True                 # fallen bypass (fix②)

    def test_cooldown_60s_not_1800(self, clock):
        mc = make_controller(clock)
        tick_fallen(mc, clock)
        clock.t += 61.0
        tick_fallen(mc, clock)                # release + start cooldown
        clock.t += 2.0
        out = tick_normal(mc, clock)          # fallen gone; cooldown blocks
        assert out[3] is False                # still inside 60s cooldown
        clock.t += 61.0                       # 60s cooldown expired
        out = oscillate(mc, clock)            # anomaly re-activates
        assert mc.anomaly.active
        assert out[3] is True                 # recoverable after 60s (was 1800s)

    def test_new_anomaly_clears_cooldown_immediately(self, clock):
        # fix①: anomaly re-activation resets _escape_released_at, so escape
        # recovers at +19s post-release (would stay blocked for 1800s before).
        mc = make_controller(clock)
        tick_fallen(mc, clock)
        clock.t += 61.0
        tick_fallen(mc, clock)                # release; released_at = now
        clock.t += 2.0
        tick_normal(mc, clock)                # fallen gone -> cooldown pause
        clock.t += 17.0                       # only +19s since release
        out = oscillate(mc, clock)            # fresh anomaly
        assert mc.anomaly.active
        assert out[3] is True                 # immediate recovery (fix①)


class TestStuckScoreDecoupling:
    def test_fallen_still_marks_and_recovers(self):
        sd = StuckDetector()
        s, dur, fallen = sd.update(0.5, 1, 20.0, -500.0)
        assert fallen is True and dur > 0
        # displacement + back on the map: score decays below 1 (fix③)
        s2, dur2, fallen2 = sd.update(0.5, 2, 30.0, 50.0)
        assert fallen2 is False
        assert s2 < 1.0
        assert dur2 == 0.0

    def test_stuck_score_not_pinned_during_fallen_motion(self):
        sd = StuckDetector()
        sd.update(0.5, 1, 20.0, -500.0)
        # while fallen with temporal/rate healthy, the raw score reflects
        # the detectors — it is not synthetically pinned to 1.0 (fix③).
        s, _, fallen = sd.update(0.5, 2, 25.0, -510.0)
        assert fallen is True
        assert s < 1.0

    def test_escape_recovers_and_loop_can_fall(self, clock):
        # end-to-end: fallen escape -> recovery -> stuck_score decays, so
        # loop_score inputs (stuck gating) unhook and breakout can run.
        mc = make_controller(clock)
        tick_fallen(mc, clock)
        clock.t += 61.0
        tick_fallen(mc, clock)
        clock.t += 61.0                       # > 60s cooldown
        out = tick_normal(mc, clock, x=500.0, z=500.0)
        assert out[0] < 1.0                   # stuck_score decayed (fix③)
        assert out[1] == 0.0
