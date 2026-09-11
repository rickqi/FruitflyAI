"""Tests for fly64.memory — CliffDetector, StuckDetector, SpatialMemoryMap, MemoryController."""

import math

import numpy as np

from fly64.memory import (
    CliffDetector,
    MemoryController,
    SpatialMemoryMap,
    StuckDetector,
)


# ======================================================================
# CliffDetector — multi-frame cliff confirmation with hysteresis
# ======================================================================

def test_cliff_initial():
    """Fresh detector returns cliff_detected=False."""
    cd = CliffDetector()
    result = cd.update(1.0)
    assert not result["cliff_detected"]
    assert result["raw_lower_field_green"] == 1.0


def test_cliff_confirmation_window_not_full():
    """Before the window fills, cliff_detected is always False."""
    cd = CliffDetector(confirmation_window=5, min_confirmed=3)
    for _ in range(4):  # only 4 of 5 frames
        result = cd.update(0.1)
        assert not result["cliff_detected"]


def test_cliff_confirms_after_sufficient_low_frames():
    """When >= min_confirmed frames in the window are below threshold, cliff_detected becomes True."""
    cd = CliffDetector(entering_threshold=0.35, confirmation_window=5, min_confirmed=3)
    # 3 out of 5 low values
    for v in [0.1, 0.1, 0.1, 0.8, 0.8]:
        result = cd.update(v)
    assert result["cliff_detected"]
    assert result["cliff_confidence"] >= 0.6  # 3/5


def test_cliff_not_confirmed_with_insufficient_low():
    """When too few frames are below threshold, cliff_detected stays False."""
    cd = CliffDetector(entering_threshold=0.35, confirmation_window=5, min_confirmed=3)
    for v in [0.1, 0.1, 0.8, 0.8, 0.8]:
        result = cd.update(v)
    assert not result["cliff_detected"]
    assert result["cliff_confidence"] == 0.4  # 2/5


def test_cliff_hysteresis():
    """Once detected, exiting threshold must be crossed to clear."""
    cd = CliffDetector(entering_threshold=0.35, exiting_threshold=0.45,
                       confirmation_window=3, min_confirmed=2)
    # Enter cliff (2/3 frames below 0.35)
    cd.update(0.1)
    cd.update(0.1)
    result = cd.update(0.1)
    assert result["cliff_detected"]

    # Still detected: 2/3 frames below 0.45 (the exiting threshold)
    result = cd.update(0.4)
    assert result["cliff_detected"]  # 0.4 < 0.45, stays in cliff

    # Clear: all 3 frames at 0.5 (above exiting threshold 0.45)
    result = cd.update(0.5)
    assert result["cliff_detected"]  # still need 3 frames
    result = cd.update(0.5)
    assert result["cliff_detected"]  # still need 3 frames
    result = cd.update(0.5)
    assert not result["cliff_detected"]  # 0/3 below threshold → cleared


def test_cliff_reset():
    """reset() clears the detector."""
    cd = CliffDetector(confirmation_window=3, min_confirmed=2)
    for v in [0.1, 0.1, 0.1]:
        cd.update(v)
    assert cd.cliff_detected
    cd.reset()
    assert not cd.cliff_detected
    assert cd.cliff_confidence == 0.0
    assert cd.raw == 1.0


def test_cliff_invalid_params():
    """Constructor rejects invalid configurations."""
    import pytest
    with pytest.raises(ValueError):
        CliffDetector(min_confirmed=10, confirmation_window=5)
    with pytest.raises(ValueError):
        CliffDetector(entering_threshold=0.5, exiting_threshold=0.3)


def test_cliff_properties():
    """Properties match the last update result."""
    cd = CliffDetector()
    assert cd.raw == 1.0
    cd.update(0.5)
    assert cd.raw == 0.5
    assert cd.cliff_confidence == 0.0  # window not full
    assert not cd.cliff_detected


# ======================================================================
# StuckDetector
# ======================================================================

def test_stuck_initial():
    """Fresh detector returns score=0, duration=0."""
    sd = StuckDetector()
    score, dur, fallen = sd.update(0.5, 0, 20.0)
    assert score == 0.0
    assert dur == 0.0
    assert not fallen
    assert sd.stuck_score == 0.0


def test_stuck_temporal_energy_collapse():
    """Low temporal_energy for >2 s → stuck."""
    sd = StuckDetector(temporal_stuck_s=2.0)
    for _ in range(250):      # 250 * 0.020 = 5 s
        score, dur, fallen = sd.update(0.01, 0, 20.0)
    assert score >= 0.5
    assert dur >= 2.0
    assert not fallen


def test_stuck_frame_freeze():
    """Unchanging frame_seq for >5 s → stuck."""
    sd = StuckDetector(frame_stuck_s=5.0)
    for _ in range(520):      # 520 * 0.020 = 10.4 s → dur ≈ 5.4 s
        score, dur, fallen = sd.update(0.5, 42, 20.0)
    assert score >= 0.5
    assert dur > 5.0
    assert not fallen


def test_stuck_forward_rate_low():
    """Low forward_rate (< threshold) for >3 s → stuck."""
    sd = StuckDetector(rate_threshold=5.0, rate_stuck_s=3.0)
    for _ in range(400):      # 400 * 0.020 = 8 s
        score, dur, fallen = sd.update(0.5, 0, 1.0)
    assert score >= 0.5
    assert dur >= 3.0
    assert not fallen


def test_stuck_recovers():
    """Once signals normalise, stuck_score drops."""
    sd = StuckDetector(temporal_stuck_s=2.0, frame_stuck_s=5.0,
                       rate_threshold=5.0, rate_stuck_s=3.0)
    for _ in range(300):
        sd.update(0.01, 42, 1.0)
    assert sd.stuck_score > 0.5

    # Recover — increment frame_seq each tick to avoid re-accumulating
    for i in range(20):
        sd.update(0.5, 99 + i, 20.0)
    assert sd.stuck_score == 0.0


def test_stuck_reset():
    """reset() clears all timers."""
    sd = StuckDetector(temporal_stuck_s=0.5)
    for _ in range(100):
        sd.update(0.01, 0, 20.0)
    sd.reset()
    assert sd.stuck_score == 0.0
    assert sd.stuck_duration == 0.0


# ======================================================================
# SpatialMemoryMap
# ======================================================================

def test_memory_initial():
    """Fresh map has no cells, full novelty."""
    sm = SpatialMemoryMap()
    assert sm.visited_cells == 0
    assert sm.total_ticks == 0
    assert sm.novelty_at(0.0, 0.0) == 1.0
    assert sm.loop_score == 0.0
    assert not sm.exploration_mode


def test_memory_new_cell():
    """First visit creates a cell with visit_count=1."""
    sm = SpatialMemoryMap()
    nv = sm.update(100.0, 200.0)
    assert sm.visited_cells == 1
    assert sm._cells[sm._key(100.0, 200.0)] == np.uint16(1)
    assert 0 < nv <= 1.0


def test_memory_revisit():
    """Revisiting a cell increments count and lowers novelty."""
    sm = SpatialMemoryMap()
    nv1 = sm.update(100.0, 200.0)
    nv2 = sm.update(150.0, 210.0)   # same cell
    assert sm._cells[sm._key(100.0, 200.0)] == np.uint16(2)
    assert nv2 < nv1


def test_memory_novelty_formula():
    """novelty = 1/(visit_count+1) × recency."""
    sm = SpatialMemoryMap(recency_decay=1.0)   # no decay
    sm.update(0.0, 0.0)   # count=1, recency=1
    nv = sm.novelty_at(0.0, 0.0)
    expected = (1.0 / (1 + 1)) * 1.0   # = 0.5
    assert abs(nv - expected) < 1e-6


def test_memory_different_cell():
    """Different grid keys produce separate cells."""
    sm = SpatialMemoryMap(cell_size=200.0)
    sm.update(0.0, 0.0)
    sm.update(500.0, 0.0)   # cell (2,0) vs (0,0)
    assert sm.visited_cells == 2


def test_memory_loop_score():
    """Revisiting the same cells many times drives loop_score up."""
    sm = SpatialMemoryMap(loop_window=20, loop_threshold=0.6)
    # Visit 3 cells alternating — high revisit ratio
    for i in range(30):
        sm.update(float((i % 3) * 50), 0.0)
    assert sm.loop_score > 0.5


def test_memory_exploration_mode():
    """exploration_mode True when loop_score > threshold."""
    sm = SpatialMemoryMap(loop_window=20, loop_threshold=0.5)
    for i in range(30):
        sm.update(float((i % 2) * 50), 0.0)   # only 2 cells
    assert sm.exploration_mode


def test_memory_get_heatmap_empty():
    """get_heatmap returns empty arrays when no cells visited."""
    sm = SpatialMemoryMap()
    xs, zs, heats = sm.get_heatmap()
    assert len(xs) == 0 and len(zs) == 0 and len(heats) == 0


def test_memory_get_heatmap():
    """get_heatmap returns aligned arrays with correct shape."""
    sm = SpatialMemoryMap(cell_size=200.0)
    sm.update(150.0, 250.0)
    sm.update(550.0, 50.0)
    xs, zs, heats = sm.get_heatmap()
    assert len(xs) == 2 and len(zs) == 2 and len(heats) == 2
    assert np.all(heats > 0)
    # Cell (0,1) centre → 0*200+100 = 100
    assert 50 <= xs[0] <= 150


def test_memory_reset():
    """reset() clears everything."""
    sm = SpatialMemoryMap(cell_size=200.0)
    sm.update(10.0, 20.0)
    sm.update(500.0, 20.0)
    assert sm.visited_cells == 2
    sm.reset()
    assert sm.visited_cells == 0
    assert sm.total_ticks == 0
    assert not sm.exploration_mode


# ======================================================================
# MemoryController
# ======================================================================

def test_controller_update():
    """update() returns (stuck_score, stuck_duration, novelty, escape_bool, fallen)."""
    mc = MemoryController()
    score, dur, nv, escape, fallen = mc.update(0.5, 0, 20.0, 100.0, 200.0)
    assert 0.0 <= score <= 1.0
    assert dur == 0.0
    assert 0 < nv <= 1.0
    assert not escape
    assert not fallen


def test_controller_escape_triggers():
    """Escape activates when stuck AND exploration_mode."""
    mc = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=1.0, rate_threshold=5.0,
                            rate_stuck_s=1.0),
        spatial=SpatialMemoryMap(loop_window=20, loop_threshold=0.5),
    )
    for _ in range(100):
        mc.update(0.01, 0, 1.0, 100.0, 200.0)
    # Also drive loop_score high
    for i in range(40):
        mc.update(0.01, 0, 1.0, float((i % 2) * 50), 200.0)
    assert mc.stuck_score > 0.5
    assert mc.spatial.exploration_mode
    assert mc.escape_behavior


def test_controller_reset():
    """reset() clears both subsystems and escape flag."""
    mc = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=0.5),
    )
    for _ in range(60):
        mc.update(0.01, 0, 20.0, 100.0, 200.0)
    assert mc.stuck_score > 0
    mc.reset()
    assert mc.stuck_score == 0.0
    assert mc.spatial.visited_cells == 0


def test_controller_cliff_detection():
    """Cliff detector is integrated into MemoryController and queryable."""
    mc = MemoryController(cliff=CliffDetector(
        entering_threshold=0.35, confirmation_window=3, min_confirmed=2))
    # Initial state
    assert not mc.cliff_detected
    assert mc.cliff_raw == 1.0

    # Fill window with low green values (cliff)
    for v in [0.1, 0.1, 0.1]:
        mc.update(0.5, 0, 20.0, 100.0, 200.0, flow_cliff=v)
    assert mc.cliff_detected
    assert mc.cliff_confidence >= 0.66
    assert mc.cliff_raw == 0.1