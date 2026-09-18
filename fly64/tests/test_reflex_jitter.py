"""Tests for ReflexController ±30% timing jitter (t29)."""
import importlib.util as _iu
import sys, pathlib

_PKG = pathlib.Path(__file__).resolve().parent.parent / "fly64"
_SPEC = _iu.spec_from_file_location("memory", _PKG / "memory.py")
_mem = _iu.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mem)

import pytest


class FakeRng:
    """Deterministic rng_choice for testing."""

    def __init__(self, seq=None):
        self.idx = -1
        self.seq = seq or [0]

    def __call__(self, low, high):
        self.idx = (self.idx + 1) % len(self.seq)
        return self.seq[self.idx]


class TestReflexJitter:

    # ── _jittered helper ────────────────────────────────────────────────

    def test_no_jitter_below_30s(self):
        """stuck_duration <= 30 → no jitter (return val as-is)."""
        rng = FakeRng([500])  # would produce 1.0 if jittered
        assert _mem.ReflexController._jittered(1.5, 0.0, rng) == 1.5
        assert _mem.ReflexController._jittered(2.0, 30.0, rng) == 2.0
        assert _mem.ReflexController._jittered(0.3, 20.0, rng) == 0.3

    def test_jitter_above_30s(self):
        """stuck_duration > 30 → jitter applied, != val."""
        rng = FakeRng([0])       # 0/1000 → 1.0 - 0.3 = 0.7x
        j = _mem.ReflexController._jittered(1.0, 31.0, rng)
        assert j < 1.0           # 0.7x factor
        rng2 = FakeRng([1000])   # 1000/1000 → 1.0 + 0.3 = 1.3x
        j2 = _mem.ReflexController._jittered(1.0, 31.0, rng2)
        assert j2 > 1.0          # 1.3x factor

    def test_jitter_bounded(self):
        """Jitter stays within ±30% bounds."""
        for seed in range(0, 1001, 33):
            rng = FakeRng([seed])
            j = _mem.ReflexController._jittered(1.0, 60.0, rng)
            assert 0.7 <= j <= 1.3, f"seed={seed} j={j}"

    def test_multiple_calls_diverse(self):
        """10 calls with same params produce non-identical values."""
        results = set()
        for seed in range(10):
            rng = FakeRng([seed * 100])
            results.add(round(
                _mem.ReflexController._jittered(1.5, 45.0, rng), 4))
        assert len(results) > 1, "all calls returned identical value"

    # ── integration: advance_phase receives jitter ──────────────────────

    def test_advance_phase_passes_jitter(self):
        """advance_phase with rng_choice != None triggers jittered durations."""
        rc = _mem.ReflexController()
        # Manually engage a stuck_ramp reflex
        rc._active_reflex = "stuck_ramp"
        rc._reflex_phase = "forward"
        rc._phase_timer = 0.0
        # With stuck=0 (no jitter), timer=1.54 < 1.5? Actually 1.54 >= 1.5
        rc._phase_timer = 1.54
        # No jitter → should release at >= 1.5
        rc._advance_phase(stuck_duration=0.0)
        assert rc._active_reflex == ""  # released normally
        # With stuck=60 and high seed → jitter would increase duration to ~1.95,
        # so timer=1.54 < jittered value → NOT released
        rc2 = _mem.ReflexController()
        rc2._active_reflex = "stuck_ramp"
        rc2._reflex_phase = "forward"
        rc2._phase_timer = 1.54
        rng = FakeRng([1000])  # 1.3x → 1.5 * 1.3 = 1.95
        rc2._advance_phase(rng_choice=rng, stuck_duration=60.0)
        assert rc2._active_reflex == "stuck_ramp"  # held, not released

    def test_wall_stuck_jitter(self):
        """wall_stuck reverse/turn durations jittered when stuck>30."""
        rc = _mem.ReflexController()
        rc._active_reflex = "wall_stuck"
        rc._reflex_phase = "reverse"
        rc._phase_timer = 0.31  # close to default 0.3
        # No jitter → released
        rc._advance_phase(stuck_duration=0.0)
        # With stuck=0, 0.31 >= 0.3 → released
        # Actually it's stuck=0, timer=0.31, duration=0.3 → released (no jitter)
        assert rc._active_reflex == "" or rc._reflex_phase == "turn"
        # With jitter and low seed → duration shrinks to 0.21, so 0.31 still >=
        rc2 = _mem.ReflexController()
        rc2._active_reflex = "wall_stuck"
        rc2._reflex_phase = "reverse"
        rc2._phase_timer = 0.25
        rng = FakeRng([1000])  # 1.3x → 0.39
        rc2._advance_phase(rng_choice=rng, stuck_duration=60.0)
        assert rc2._reflex_phase == "reverse"  # 0.25 < 0.39 → not yet