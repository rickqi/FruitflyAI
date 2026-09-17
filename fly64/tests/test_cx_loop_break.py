"""EVO-057 · P1-1 regression — CX persistent-loop break.

Background.  The tree briefly carried a "force a random column jump" block in
``CentralComplex.update`` which could never fire, for two independent reasons:

1. it read ``getattr(self, "stuck_duration", 0.0)`` — that attribute lives on
   ``StuckDetector``/``FlyModel``, never on ``CentralComplex``, so the test
   always compared ``0.0 > 300``;
2. its guard ``self.goal_strength < 0.10`` was evaluated *after* the wander
   block, which sets ``goal_strength = 0.30`` whenever it was below 0.05 — so
   the guard was False exactly in the situation it was meant to catch.  The
   same self-poisoning applies to *any* guard phrased against ``goal_strength``
   because the loop break itself writes 0.60.

It also called ``np.random.default_rng()`` with no seed, which would have
broken the exact-replay contract had it ever run.

The corrected version passes a real ``stuck_duration`` in from ``FlyModel``,
reads "is there a real target?" from a dedicated ``_ext_goal_strength`` that
only the goal-vector / novelty branches write, rate-limits breaks with a
tick cooldown, and derives the jump index from a hash of the break counter.

These tests pin the corrected behaviour AND each deadness condition, so the
block cannot silently regress to decoration again.
"""
import inspect

import pytest

import fly64.central_complex as cc_mod
from fly64.central_complex import (CX_LOOP_BREAK_COOLDOWN_TICKS,
                                   CX_LOOP_BREAK_STUCK_S, CentralComplex)


def _drive(cx, ticks, stuck_duration=0.0, **kw):
    """Run ticks with no goal vectors and flat novelty (no real target)."""
    for _ in range(ticks):
        cx.update(heading=0.0, heading_rate=0.0, novelty=0.5,
                  novelty_direction=0.0, dt=0.02,
                  stuck_duration=stuck_duration, **kw)
    return cx


class TestSignalActuallyArrives:
    """Deadness cause 1: the stuck signal must reach the CX itself."""

    def test_stuck_duration_is_stored_on_the_cx(self):
        cx = CentralComplex()
        cx.update(heading=0.0, heading_rate=0.0, dt=0.02, stuck_duration=12.5)
        assert cx.stuck_time == 12.5, (
            "stuck_duration never reached CentralComplex — the loop-break "
            "test is reading an attribute that only exists on StuckDetector")

    def test_cx_does_not_own_a_stuck_duration_attribute(self):
        """Pins the root cause so the wrong wiring is not re-added."""
        assert not hasattr(CentralComplex(), "stuck_duration"), (
            "CentralComplex grew a stuck_duration attribute; revisit the "
            "wiring in cx.update()/model.py rather than doubling it")

    def test_flymodel_actually_passes_the_signal(self):
        """The producer side: model.py must forward its mirror of the value."""
        import fly64.model as model_mod
        src = inspect.getsource(model_mod)
        assert "stuck_duration=getattr(self, \"stuck_duration\", 0.0)" in src, (
            "FlyModel stopped forwarding stuck_duration into cx.update()")


class TestLoopBreakFires:
    """Deadness cause 2: the guard must not read goal_strength."""

    def test_fires_after_threshold_with_no_goal(self):
        cx = CentralComplex()
        _drive(cx, 20, stuck_duration=CX_LOOP_BREAK_STUCK_S - 1.0)
        assert cx._jump_seq == 0, "fired below the stuck threshold"
        _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 1, (
            "loop break never fired — the guard is still being poisoned by "
            "the synthetic goal_strength writes")
        assert cx.goal_strength == 0.60

    def test_guard_survives_the_wander_bump(self):
        """Directly pins cause 2: strength is 0.30 *before* the guard runs."""
        cx = CentralComplex()
        _drive(cx, 1, stuck_duration=0.0)
        assert cx.goal_strength == 0.30, "wander bump did not run"
        _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 1, (
            "goal_strength == 0.30 from wander made the guard unreachable")

    def test_guard_is_not_defeated_by_a_previous_break(self):
        """The break writes 0.60; a second break must still be possible."""
        cx = CentralComplex()
        _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx.goal_strength == 0.60
        _drive(cx, CX_LOOP_BREAK_COOLDOWN_TICKS,
               stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 2, "previous break's 0.60 blocked the next one"

    def test_real_target_signal_is_tracked_separately(self):
        cx = CentralComplex()
        _drive(cx, 5, stuck_duration=0.0)
        assert cx._ext_goal_strength == 0.0, "synthetic writes leaked into it"
        cx.update(heading=0.0, heading_rate=0.0, dt=0.02,
                  goal_vectors=[(1.0, 1.0, 2.0)], stuck_duration=0.0)
        assert cx._ext_goal_strength > 0.05


class TestLoopBreakDoesNotOverfire:
    def test_active_goal_is_never_overridden(self):
        """A real goal vector means the fly is pursuing something: no jump."""
        cx = CentralComplex()
        for _ in range(5):
            cx.update(heading=0.0, heading_rate=0.0, dt=0.02,
                      goal_vectors=[(1.0, 1.0, 2.0)],
                      stuck_duration=CX_LOOP_BREAK_STUCK_S + 600.0)
        assert cx._jump_seq == 0, "loop break overrode an actively held goal"

    def test_cooldown_prevents_a_per_tick_storm(self):
        cx = CentralComplex()
        _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 1
        # one tick short of the cooldown → no second break
        _drive(cx, CX_LOOP_BREAK_COOLDOWN_TICKS - 2,
               stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 1, "cooldown not honoured"
        _drive(cx, 2, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 2, "cooldown never expires"

    def test_not_stuck_means_no_break(self):
        cx = CentralComplex()
        _drive(cx, 3000, stuck_duration=10.0)
        assert cx._jump_seq == 0


class TestDeterminism:
    """The exact-replay contract: identical inputs → identical jumps."""

    @staticmethod
    def _jump_columns(n_breaks=4):
        cx = CentralComplex()
        seq = []
        for _ in range(n_breaks):
            _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
            seq.append(cx.goal_column)
            _drive(cx, CX_LOOP_BREAK_COOLDOWN_TICKS,
                   stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        return seq

    def test_two_identical_runs_jump_identically(self):
        a, b = self._jump_columns(), self._jump_columns()
        assert a == b, (
            f"loop break is nondeterministic: {a} != {b} — replay.py "
            "exact-replay would diverge")
        assert len(set(a)) > 1, f"jump sequence is degenerate: {a}"

    def test_no_unseeded_rng_in_source(self):
        """A global RNG here would poison every downstream replay."""
        src = inspect.getsource(cc_mod)
        assert "default_rng()" not in src, (
            "unseeded np.random.default_rng() reintroduced — breaks exact "
            "replay (use the _jump_seq hash instead)")
        assert "np.random" not in src.replace("np.random.default_rng", ""), (
            "np.random used in the CX: route determinism through _jump_seq")

    def test_jump_spreads_over_columns(self):
        cols = self._jump_columns(n_breaks=6)
        assert len(set(cols)) >= 4, f"jump too concentrated: {cols}"

    def test_reset_clears_jump_state(self):
        cx = CentralComplex()
        _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert cx._jump_seq == 1
        cx.reset()
        assert cx._jump_seq == 0
        assert cx.stuck_time == 0.0
        assert cx._ext_goal_strength == 0.0


class TestTelemetry:
    def test_compass_stats_exposes_loop_break(self):
        cx = CentralComplex()
        _drive(cx, 1, stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        stats = cx.compass_stats
        assert stats["loop_breaks"] == 1
        assert stats["stuck_time"] == pytest.approx(CX_LOOP_BREAK_STUCK_S + 1.0)
