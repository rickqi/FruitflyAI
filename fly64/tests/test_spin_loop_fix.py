"""EVO R11 regression — spin-loop fix (brain-first P0).

Covers:
- loop_score exact rolling-window counting (score stays within [0, 1])
- micro_loop reflex progress gate: no movement → mirrored turn direction
- micro_loop reflex progress gate: moved ≥ progress_radius → fresh random turn
- gate is reflex-internal: no new control-cascade tier introduced
"""
import pytest

from fly64.memory import SpatialMemoryMap, ReflexController, MotionStateDetector


# ── P0-1 · loop_score sensory hygiene ────────────────────────────────
#
# API CONTRACT: SpatialMemoryMap.update(x, y=0.0, z=0.0) — THREE coordinates,
# and SpatialMemoryMap._key() hashes all three.  These tests used to call
# update(x, z), so the world coordinate landed in the *vertical* argument and z
# stayed 0.  Every cell then collapsed onto one axis: the "200 distinct cells"
# walk produced just 24 cells, so the last 50 window slots were all revisits and
# loop_score read 1.0 instead of 0.0 (measured: 24 cells / 1.0 before, 200 cells
# / 0.0 with the third argument passed — EVO-071).
#
# The same mistake made `test_loop_score_hits_one_on_pure_revisit` pass for the
# wrong reason: with x and y both stepping by 10 inside a 200-unit cell, the
# "3-cell tight loop" actually visited ONE cell.  Both now express their intent
# and TestUpdateCoordinateContract below pins the contract that was misread.

class TestLoopScoreBounded:
    def test_loop_score_stays_within_unit_after_long_alternation(self):
        m = SpatialMemoryMap(cell_size=200, loop_window=120)
        # March forever between two cells — every step after the first is a
        # revisit.  Old code diverged unboundedly (observed 104.976).
        for i in range(3000):
            x, z = (0.0, 0.0) if i % 2 == 0 else (450.0, 450.0)
            m.update(x, 0.0, z)
        assert 0.0 <= m.loop_score <= 1.0
        assert m.loop_score == pytest.approx(1.0)

    def test_loop_score_hits_one_on_pure_revisit(self):
        m = SpatialMemoryMap(cell_size=200, loop_window=50)
        # A genuine 3-cell tight loop: 250-unit steps cross 200-unit cell
        # boundaries, so three DISTINCT cells are visited and then re-visited.
        for i in range(500):
            m.update(250.0 * (i % 3), 0.0, 0.0)
        assert len(m._cells) == 3, "the loop must actually span 3 cells"
        assert m.loop_score == pytest.approx(1.0)

    def test_loop_score_zero_on_fresh_exploration(self):
        m = SpatialMemoryMap(cell_size=200, loop_window=50)
        # Walk 200 DISTINCT cells inside the grid (grid clamps at ±25 cells
        # = ±5000u — stepping beyond the world edge is a genuine revisit).
        for i in range(200):
            cx = i % 24
            cz = i // 24
            m.update(cx * 400 - 4800 + 100.0, 0.0, cz * 400 - 4800 + 100.0)
        assert len(m._cells) == 200, "the walk must visit 200 distinct cells"
        assert m.loop_score == 0.0


class TestUpdateCoordinateContract:
    """Pin the three-coordinate contract the loop-score tests depend on."""

    def test_all_three_coordinates_enter_the_cell_key(self):
        m = SpatialMemoryMap(cell_size=200, loop_window=50)
        assert m._key(100.0, 0.0, 0.0) != m._key(100.0, 400.0, 0.0), (
            "y (altitude) must be part of the cell key")
        assert m._key(100.0, 0.0, 0.0) != m._key(100.0, 0.0, 400.0), (
            "z must be part of the cell key — passing the world coordinate as "
            "the y argument silently collapses the map onto one axis")

    def test_update_accepts_three_coordinates(self):
        import inspect
        sig = inspect.signature(SpatialMemoryMap.update)
        assert list(sig.parameters)[:4] == ["self", "x", "y", "z"], (
            "update's signature changed; the loop-score tests pass (x, 0, z)")


# ── P0-2 · micro_loop reflex progress gate + mirror alternation ──────

def _fire_micro_loop(reflex, pos, rng_pairs=(0, 1)):
    """Drive the reflex until micro_loop fires; return its turn direction."""
    state = {"state": MotionStateDetector.MICRO_LOOP, "confidence": 1.0}
    for _ in range(50):
        rt = reflex.update(0.02, state, lambda lo, hi: rng_pairs[0],
                           stuck_duration=200.0, pos=pos)
        if rt == MotionStateDetector.MICRO_LOOP:
            return reflex._turn_direction
    return 0


class TestMicroLoopProgressGate:
    def _fresh(self):
        return ReflexController(cooldown_duration=0.0)  # no cooldown friction

    def test_no_movement_mirrors_direction(self):
        r = self._fresh()
        pos = (1000.0, 2000.0)
        d1 = _fire_micro_loop(r, pos)
        # Let the reflex finish (2s) then re-fire from the SAME spot
        for _ in range(150):
            r.update(0.02, {"state": "idle", "confidence": 0.0},
                     lambda lo, hi: 0, pos=pos)
        d2 = _fire_micro_loop(r, pos)
        assert d1 in (69, -69) and d2 in (69, -69)
        assert d2 == -d1, "no progress → direction must mirror"

    def test_mirror_alternates_repeatedly_without_progress(self):
        r = self._fresh()
        pos = (0.0, 0.0)
        dirs = []
        for _ in range(4):
            d = _fire_micro_loop(r, pos)
            dirs.append(d)
            for _ in range(150):
                r.update(0.02, {"state": "idle", "confidence": 0.0},
                         lambda lo, hi: 0, pos=pos)
        for a, b in zip(dirs, dirs[1:]):
            assert b == -a, "consecutive no-progress fires must alternate"

    def test_progress_allows_new_random_direction(self):
        r = self._fresh()
        d1 = _fire_micro_loop(r, (0.0, 0.0))
        for _ in range(150):
            r.update(0.02, {"state": "idle", "confidence": 0.0},
                     lambda lo, hi: 0, pos=(0.0, 0.0))
        # Moved 100u (> progress_radius=30) since last fire → gate open
        d2 = _fire_micro_loop(r, (100.0, 0.0))
        assert d2 in (69, -69)
        assert r._last_fire_pos == (100.0, 0.0)

    def test_first_fire_uses_random_direction(self):
        r = self._fresh()
        d = _fire_micro_loop(r, (5.0, 5.0))
        assert d in (69, -69)
