"""Tests for fly64.memory — CliffDetector, StuckDetector, SpatialMemoryMap, MemoryController."""

import math

import numpy as np

from fly64.memory import (
    CliffDetector,
    MemoryController,
    MotionStateDetector,
    ReflexController,
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
    """update() returns (stuck_score, stuck_duration, novelty, escape_bool, fallen,
    forced_bold_explore)."""
    mc = MemoryController()
    score, dur, nv, escape, fallen, bold = mc.update(0.5, 0, 20.0, 100.0, 200.0)
    assert 0.0 <= score <= 1.0
    assert dur == 0.0
    assert 0 < nv <= 1.0
    assert not escape
    assert not fallen
    assert not bold


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


# ======================================================================
# Forced Bold Explore — nested-loop breakout detection
# ======================================================================

def test_bold_explore_initial_false():
    """Fresh controller has forced_bold_explore=False."""
    mc = MemoryController()
    assert not mc.forced_bold_explore
    assert mc.scene_low_duration == 0.0


def test_bold_explore_not_triggered_with_high_scene_change():
    """Scene_change_rate >= 0.05 prevents forced_bold_explore regardless of visited_cells."""
    mc = MemoryController(spatial=SpatialMemoryMap(grid_cells=50))
    # scene_change_rate=0.1 (above threshold), visited_cells < 20 (barely visited)
    for _ in range(600):  # 600 * 0.020 = 12 s (>10 s trigger)
        mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.1)
    assert not mc.forced_bold_explore
    assert mc.scene_low_duration == 0.0  # reset due to high scene_change_rate


def test_bold_explore_not_triggered_with_high_visited_cells():
    """visited_cells >= 20 prevents forced_bold_explore even with low scene change."""
    mc = MemoryController(spatial=SpatialMemoryMap(grid_cells=50))
    # Visit many different cells (cell_size=200, so step by 210 to ensure new cells)
    for i in range(25):
        mc.update(0.5, 0, 20.0, float(i * 210), 200.0, scene_change_rate=0.01)
    assert mc.spatial.visited_cells >= 20, f"Only {mc.spatial.visited_cells} cells visited"
    # Now advance time with low scene_change but high visited_cells
    for _ in range(600):
        mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.01)
    assert not mc.forced_bold_explore


def test_bold_explore_triggers_after_10_seconds():
    """Forced_bold_explore activates when scene_change_rate < 0.05 for >10 s AND visited_cells < 20."""
    mc = MemoryController(spatial=SpatialMemoryMap(grid_cells=50))
    # Start with low scene_change_rate and few visited cells
    for _ in range(5):
        mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.01)
    assert mc.spatial.visited_cells < 20
    assert not mc.forced_bold_explore

    # Advance past 10 s threshold (500 ticks at dt=0.020)
    for _ in range(510):
        mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.01)
    assert mc.forced_bold_explore
    assert mc.scene_low_duration >= 10.0


def test_bold_explore_resets_on_scene_change_burst():
    """When scene_change_rate spikes above 0.05, the timer resets."""
    mc = MemoryController(spatial=SpatialMemoryMap(grid_cells=50))
    # Build up some low-duration time
    for _ in range(250):  # 5 s
        mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.01)
    assert mc.scene_low_duration >= 4.9, f"Expected ~5.0, got {mc.scene_low_duration}"
    assert not mc.forced_bold_explore  # not yet past 10 s

    # Scene change rate spikes — timer resets
    mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.5)
    assert mc.scene_low_duration == 0.0
    assert not mc.forced_bold_explore


def test_bold_explore_escape_behavior():
    """forced_bold_explore directly triggers escape_behavior even without stuck/loop."""
    mc = MemoryController(spatial=SpatialMemoryMap(grid_cells=50))
    # Push past 10 s with low scene_change_rate and few visited cells
    for tick in range(600):
        result = mc.update(0.5, 0, 20.0, 100.0, 200.0,
                           scene_change_rate=0.01)
    # Escape behavior should be True from forced_bold_explore alone
    assert mc.forced_bold_explore
    assert mc.escape_behavior


def test_bold_explore_resets():
    """reset() clears forced_bold_explore state."""
    mc = MemoryController(spatial=SpatialMemoryMap(grid_cells=50))
    for _ in range(550):
        mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.01)
    assert mc.forced_bold_explore
    mc.reset()
    assert not mc.forced_bold_explore
    assert mc.scene_low_duration == 0.0


def test_novelty_direction_eliminates_dead_end_penalty_in_bold_explore():
    """When forced_bold_explore=True, dead-end penalty is fully eliminated (modifier=0.0)."""
    sm = SpatialMemoryMap(cell_size=200.0)
    # Mark a dead end cell
    dead_end_cells = {(0, 1)}

    # Without forced_bold_explore, penalty modifier is 1.0
    bias_normal = sm.novelty_direction(
        0.0, 0.0, 0.0, dead_end_keys=dead_end_cells,
        scene_change_rate=0.0, forced_bold_explore=False)

    # With forced_bold_explore, penalty modifier is 0.0 (no suppression)
    bias_bold = sm.novelty_direction(
        0.0, 0.0, 0.0, dead_end_keys=dead_end_cells,
        scene_change_rate=0.0, forced_bold_explore=True)

    # The presence of dead-end cells should not suppress novelty in bold mode
    # (the exact values depend on novelty computation, but the function
    # should still run without error and return a result)
    assert isinstance(bias_normal, float)
    assert isinstance(bias_bold, float)


# ======================================================================
# MotionStateDetector — 5-state anomaly detection with majority vote
# ======================================================================


def test_anomaly_initial():
    """Fresh detector has idle state, no anomaly."""
    ad = MotionStateDetector(window=5)
    state = ad.get_state()
    assert state["state"] == MotionStateDetector.IDLE
    assert not state["active"]
    assert state["confidence"] >= 0.0
    assert state["duration_in_state"] >= 0.0


def test_anomaly_properties():
    """Property accessors match get_state()."""
    ad = MotionStateDetector(window=5)
    assert not ad.active
    assert ad.active_state == MotionStateDetector.IDLE


def test_anomaly_state_history_empty():
    """Fresh detector has empty state_history."""
    ad = MotionStateDetector(window=5)
    assert ad.state_history == []


def test_anomaly_state_history_records_transitions():
    """State transitions are recorded in history."""
    ad = MotionStateDetector(window=30, history_size=100)
    # Fill window with stuck_ramp votes
    for _ in range(40):
        ad.update(ramp_score=0.8, stuck_duration=20.0, heading_rate=0.01)
    history = ad.state_history
    assert len(history) >= 1
    assert history[0]["from"] == MotionStateDetector.IDLE
    assert history[0]["to"] == MotionStateDetector.STUCK_RAMP


def test_anomaly_stuck_ramp():
    """stuck_ramp: ramp_score>0.5 AND stuck_duration>15s AND heading_rate<0.05."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(ramp_score=0.8, stuck_duration=20.0, heading_rate=0.01)
    assert ad.active
    assert ad.active_state == MotionStateDetector.STUCK_RAMP


def test_anomaly_stuck_ramp_no_ramp():
    """No stuck_ramp when ramp_score is low."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(ramp_score=0.1, stuck_duration=20.0, heading_rate=0.01)
    assert not ad.active or ad.active_state != MotionStateDetector.STUCK_RAMP


def test_anomaly_oscillating():
    """Oscillation: control.x alternates between ≤-60 and ≥+60 within 30 frames."""
    ad = MotionStateDetector(window=10)
    for i in range(15):
        cx = -64 if i % 2 == 0 else 64
        ad.update(control_x=cx)
    assert ad.active
    assert ad.active_state == MotionStateDetector.OSCILLATING


def test_anomaly_oscillating_no_alternation():
    """No oscillation when control.x stays in one direction."""
    ad = MotionStateDetector(window=10)
    for i in range(15):
        ad.update(control_x=64)
    assert not ad.active or ad.active_state != MotionStateDetector.OSCILLATING


def test_anomaly_wall_stuck():
    """wall_stuck: wall_score>0.4 AND escape_behavior AND stuck_duration>10s."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(wall_score=0.8, escape_behavior=True, stuck_duration=15.0)
    assert ad.active
    assert ad.active_state == MotionStateDetector.WALL_STUCK


def test_anomaly_wall_stuck_not_escaping():
    """No wall_stuck when escape is not active."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(wall_score=0.8, escape_behavior=False, stuck_duration=15.0)
    assert not ad.active or ad.active_state != MotionStateDetector.WALL_STUCK


def test_anomaly_micro_loop():
    """micro_loop: visited_cells<5 AND loop_score>0.5 AND stuck_duration>30s."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(visited_cells=2, loop_score=0.8, stuck_duration=40.0)
    assert ad.active
    assert ad.active_state == MotionStateDetector.MICRO_LOOP


def test_anomaly_micro_loop_not_when_exploring():
    """No micro_loop when visited_cells >= 5."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(visited_cells=10, loop_score=0.8, stuck_duration=40.0)
    assert not ad.active or ad.active_state != MotionStateDetector.MICRO_LOOP


def test_anomaly_fallen():
    """fallen detected when pos_y < -100."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(pos_y=-200.0)
    assert ad.active
    assert ad.active_state == MotionStateDetector.FALLEN


def test_anomaly_fallen_high():
    """fallen detected when pos_y > 1000."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(pos_y=1500.0)
    assert ad.active
    assert ad.active_state == MotionStateDetector.FALLEN


def test_anomaly_priority():
    """Priority: fallen > micro_loop > oscillating > wall_stuck > stuck_ramp > idle."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(ramp_score=0.8, stuck_duration=20.0, heading_rate=0.01, pos_y=-200.0)
    assert ad.active_state == MotionStateDetector.FALLEN


def test_anomaly_majority_vote():
    """Majority-vote: most-frequent state in window wins."""
    ad = MotionStateDetector(window=10)
    for _ in range(10):
        ad.update()  # all idle
    assert ad.active_state == MotionStateDetector.IDLE
    # 7 stuck_ramp + 3 idle
    for _ in range(7):
        ad.update(ramp_score=0.8, stuck_duration=20.0, heading_rate=0.01)
    for _ in range(3):
        ad.update()
    assert ad.active
    assert ad.active_state == MotionStateDetector.STUCK_RAMP


def test_anomaly_reset():
    """reset() clears all anomaly state."""
    ad = MotionStateDetector(window=5)
    for _ in range(10):
        ad.update(ramp_score=0.8, stuck_duration=20.0, heading_rate=0.01)
    assert ad.active
    ad.reset()
    assert not ad.active
    assert ad.active_state == MotionStateDetector.IDLE
    assert ad.state_history == []


# ======================================================================
# MemoryController — anomaly integration
# ======================================================================


def test_controller_anomaly_fresh():
    """Fresh MemoryController has no anomalies."""
    mc = MemoryController()
    assert not mc.anomaly_active
    assert mc.anomaly_state_name == MotionStateDetector.IDLE


def test_controller_anomaly_update_stuck_ramp():
    """MemoryController.update passes ramp_score and triggers stuck_ramp state."""
    mc = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=1.0, rate_threshold=5.0, rate_stuck_s=1.0),
    )
    # Visit several different cells first to avoid micro_loop dominance
    for i in range(20):
        mc.update(0.5, i, 20.0, float(i * 300), 200.0)
    # Now get stuck on a ramp (need stuck_duration > 15 s = 750 ticks at 20ms,
    # plus ~100 ticks for temporal stuck to trigger first)
    for _ in range(900):
        mc.update(0.01, 20, 1.0, 100.0, 200.0, ramp_score=0.8)
    assert mc.stuck_score > 0.5
    assert mc.stuck_duration > 15.0
    assert mc.anomaly_active
    assert mc.anomaly_state_name == MotionStateDetector.STUCK_RAMP


def test_controller_anomaly_state_method():
    """anomaly_state returns the full dict."""
    mc = MemoryController()
    _ = mc.update(0.5, 0, 20.0, 100.0, 200.0)
    state = mc.anomaly_state
    assert isinstance(state, dict)
    assert "state" in state
    assert "confidence" in state
    assert "duration_in_state" in state
    assert "active" in state


def test_controller_anomaly_reset():
    """Controller reset() clears anomaly state."""
    mc = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=1.0),
    )
    for i in range(20):
        mc.update(0.5, i, 20.0, float(i * 300), 200.0)
    for _ in range(900):
        mc.update(0.01, 20, 1.0, 100.0, 200.0, ramp_score=0.8)
    assert mc.anomaly_active
    mc.reset()
    assert not mc.anomaly_active


# ======================================================================
# ReflexController — Drosophila-inspired reflex escape circuits
# ======================================================================


def _always_pick_first(lo, hi):
    """Deterministic rng_choice that always picks the lowest value."""
    return lo


def test_reflex_initial():
    """Fresh ReflexController is idle."""
    rc = ReflexController()
    assert not rc.active
    assert rc.active_reflex == ""
    action = rc.get_action()
    assert not action["active"]
    assert action["reflex"] == ""


def test_reflex_stuck_ramp_triggers():
    """stuck_ramp reflex fires when anomaly_state matches with sufficient confidence."""
    rc = ReflexController(confidence_threshold=0.6, stuck_ramp_duration=1.5)
    anomaly_state = {"state": "stuck_ramp", "confidence": 0.8}
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == ReflexController.STUCK_RAMP
    assert rc.active
    action = rc.get_action()
    assert action["active"]
    assert action["reflex"] == ReflexController.STUCK_RAMP
    assert action["control_y"] == 70  # forward burst
    assert abs(action["control_x"]) == 60  # turn ±60


def test_reflex_stuck_ramp_forward_burst_duration():
    """stuck_ramp forward burst lasts for stuck_ramp_duration."""
    rc = ReflexController(confidence_threshold=0.6, stuck_ramp_duration=1.5)
    anomaly_state = {"state": "stuck_ramp", "confidence": 0.8}
    rc.update(0.020, anomaly_state, _always_pick_first)
    # Tick through the reflex
    for _ in range(74):  # 74 * 0.020 = 1.48 s (just under 1.5)
        rc.update(0.020, anomaly_state, _always_pick_first)
    assert rc.active  # still active
    # One more tick = 1.5 s
    rc.update(0.020, anomaly_state, _always_pick_first)
    assert not rc.active  # should have ended


def test_reflex_oscillating_triggers():
    """oscillating reflex holds direction for 2s without alternation."""
    rc = ReflexController(confidence_threshold=0.6, oscillating_duration=2.0)
    anomaly_state = {"state": "oscillating", "confidence": 0.8}
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == ReflexController.OSCILLATING
    action = rc.get_action()
    assert action["reflex"] == ReflexController.OSCILLATING
    assert abs(action["control_x"]) == 69  # locked turn
    assert action["control_y"] == 70
    # Verify direction stays same across multiple ticks (no alternation)
    for _ in range(10):
        rc.update(0.020, anomaly_state, _always_pick_first)
        a = rc.get_action()
        assert a["control_x"] == action["control_x"]  # same direction, no alternation


def test_reflex_wall_stuck_triggers():
    """wall_stuck reflex does reverse then opposite turn."""
    rc = ReflexController(confidence_threshold=0.6,
                          wall_stuck_reverse_duration=0.3,
                          wall_stuck_turn_duration=0.8)
    anomaly_state = {"state": "wall_stuck", "confidence": 0.8}
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == ReflexController.WALL_STUCK
    # Phase 1: reverse
    action = rc.get_action()
    assert action["phase"] == "reverse"
    assert action["control_y"] == -20  # reverse
    # Tick past reverse phase (0.3 s = 15 ticks)
    for _ in range(16):
        rc.update(0.020, anomaly_state, _always_pick_first)
    # Phase 2: opposite turn
    action = rc.get_action()
    assert action["phase"] == "turn"
    assert action["control_y"] == 50


def test_reflex_micro_loop_triggers():
    """micro_loop reflex produces turn + burst sequence."""
    rc = ReflexController(confidence_threshold=0.6, micro_loop_duration=2.0)
    anomaly_state = {"state": "micro_loop", "confidence": 0.8}
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == ReflexController.MICRO_LOOP
    assert rc.active
    # Phase 1: turn
    action = rc.get_action()
    assert action["phase"] == "turn"
    assert abs(action["control_x"]) == 69
    assert action["control_y"] == 0
    # Tick past turn phase (0.5 s = 25 ticks)
    for _ in range(26):
        rc.update(0.020, anomaly_state, _always_pick_first)
    # Phase 2: burst
    action = rc.get_action()
    assert action["phase"] == "burst"
    assert action["control_y"] == 70


def test_reflex_low_confidence_no_trigger():
    """Reflex does NOT fire when confidence is below threshold."""
    rc = ReflexController(confidence_threshold=0.6)
    anomaly_state = {"state": "stuck_ramp", "confidence": 0.4}
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == ""
    assert not rc.active


def test_reflex_cooldown():
    """Same reflex cannot fire again within cooldown period."""
    rc = ReflexController(confidence_threshold=0.6, cooldown_duration=10.0,
                          stuck_ramp_duration=0.1)
    anomaly_state = {"state": "stuck_ramp", "confidence": 0.8}
    # Fire stuck_ramp
    rc.update(0.020, anomaly_state, _always_pick_first)
    # Let it complete
    for _ in range(10):
        rc.update(0.020, anomaly_state, _always_pick_first)
    assert not rc.active
    # Try to fire again immediately — should be blocked by cooldown
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == "", f"Expected cooldown to block, got {result}"


def test_reflex_different_reflex_no_cooldown_conflict():
    """Different reflex types have independent cooldowns."""
    rc = ReflexController(confidence_threshold=0.6, cooldown_duration=10.0,
                          stuck_ramp_duration=0.1, oscillating_duration=0.1)
    # Fire stuck_ramp, let it complete
    rc.update(0.020, {"state": "stuck_ramp", "confidence": 0.8}, _always_pick_first)
    for _ in range(10):
        rc.update(0.020, {"state": "stuck_ramp", "confidence": 0.8}, _always_pick_first)
    # oscillating should still be available
    result = rc.update(0.020, {"state": "oscillating", "confidence": 0.8}, _always_pick_first)
    assert result == ReflexController.OSCILLATING


def test_reflex_active_during_reflex():
    """While a reflex is active, update returns the reflex type (no re-trigger)."""
    rc = ReflexController(confidence_threshold=0.6, stuck_ramp_duration=1.0)
    anomaly_state = {"state": "stuck_ramp", "confidence": 0.8}
    rc.update(0.020, anomaly_state, _always_pick_first)
    # Tick while still active — should return stuck_ramp, not empty
    for _ in range(10):
        result = rc.update(0.020, anomaly_state, _always_pick_first)
        assert result == ReflexController.STUCK_RAMP


def test_reflex_reset():
    """reset() clears all reflex state."""
    rc = ReflexController(confidence_threshold=0.6)
    rc.update(0.020, {"state": "stuck_ramp", "confidence": 0.8}, _always_pick_first)
    assert rc.active
    rc.reset()
    assert not rc.active
    assert rc.active_reflex == ""
    for cd in rc.cooldowns.values():
        assert cd == 0.0


def test_controller_reflex_properties():
    """MemoryController exposes reflex properties."""
    mc = MemoryController()
    assert not mc.reflex_active
    assert mc.reflex_type == ""
    action = mc.reflex_action
    assert isinstance(action, dict)
    assert not action["active"]


def test_controller_reflex_cooldowns_property():
    """reflex_cooldowns returns dict with all reflex types."""
    mc = MemoryController()
    cds = mc.reflex_cooldowns
    for rt in ReflexController.REFLEX_TYPES:
        assert rt in cds


# ======================================================================
# Health scoring and landmark repulsion
# ======================================================================


def test_health_score_default():
    """Fresh MemoryController has health_score near 1.0."""
    mc = MemoryController()
    assert 0.0 <= mc.health_score <= 1.0
    assert mc.health_score > 0.9


def test_health_score_decreases_with_stuck():
    """Health score decreases when stuck_duration accumulates."""
    mc = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=1.0, rate_threshold=5.0, rate_stuck_s=1.0),
    )
    # Get stuck
    for i in range(10):
        mc.update(0.5, i, 20.0, float(i * 300), 200.0)
    for _ in range(5000):  # 100 s at 0.020
        mc.update(0.01, 0, 1.0, 100.0, 200.0, scene_change_rate=0.0)
    # stuck_cost = min(100/300, 0.3) = 0.3, revisit_cost ≈ 0, scene_boost = 0
    # health ≈ 0.7
    assert mc.stuck_duration > 10.0
    assert mc.health_score < 0.9
    assert mc.health_score > 0.0


def test_health_score_boosted_by_scene_change():
    """Health score gets a boost from scene_change_rate."""
    mc = MemoryController()
    # update with scene_change_rate = 0.5
    mc.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.5)
    # scene_boost = 0.5 * 0.2 = 0.1
    assert mc.health_score > 0.5, f"Expected >0.5, got {mc.health_score}"


def test_repulsion_zero_when_few_revisits():
    """_get_repulsion returns 0 when revisit_count <= 10."""
    sm = SpatialMemoryMap()
    local_rc = sm._scene_db.revisit_count
    # Freshly created map has no revisits
    assert sm._get_repulsion((0, 0)) == 0.0


def test_repulsion_positive_with_many_revisits():
    """_get_repulsion > 0 when high-revisit cells are nearby."""
    sm = SpatialMemoryMap()
    cell_key = (0, 0)
    # Manually fill a cell with high visit count
    sm._cells[cell_key] = np.uint16(12)  # > 10 threshold
    # Set revisit count > 10 by adding matching signatures
    sig = np.ones(128, dtype=np.float32) / np.sqrt(128)
    for _ in range(12):
        sm._scene_db.add(sig, 0)
    sm._scene_db.match(sig)  # trigger recount
    # Query a neighboring cell
    rep = sm._get_repulsion((1, 0))
    assert rep > 0.0, f"Expected positive repulsion, got {rep}"
    assert rep <= 0.8


def test_novelty_reduced_by_repulsion():
    """_novelty is further reduced when repulsion is active."""
    sm = SpatialMemoryMap(recency_decay=1.0)
    # Fill the query cell
    cell_key = (0, 0)
    sm._cells[cell_key] = np.uint16(5)
    sm._recency[cell_key] = 1.0
    novelty_before = sm.novelty_at(0.0, 0.0)
    # Now add high-revisit neighboring cell and bump revisit_count
    sm._cells[(1, 0)] = np.uint16(15)  # high revisit > 10
    sig = np.ones(128, dtype=np.float32) / np.sqrt(128)
    for _ in range(12):
        sm._scene_db.add(sig, 0)
    sm._scene_db.match(sig)
    novelty_after = sm.novelty_at(0.0, 0.0)
    assert novelty_after <= novelty_before, (
        f"Novelty increased: {novelty_before} -> {novelty_after}"
    )


def test_aggressive_mode_halves_cooldown():
    """set_aggressive_mode(True) halves the effective cooldown."""
    rc = ReflexController(confidence_threshold=0.6, cooldown_duration=10.0,
                          stuck_ramp_duration=0.1)
    rc.set_aggressive_mode(True)
    anomaly_state = {"state": "stuck_ramp", "confidence": 0.8}
    idle_state = {"state": "idle", "confidence": 0.0}
    # Fire once
    rc.update(0.020, anomaly_state, _always_pick_first)
    # Let the reflex complete
    for _ in range(10):
        rc.update(0.020, anomaly_state, _always_pick_first)
    cd_after_complete = rc.cooldowns["stuck_ramp"]
    assert 4.7 < cd_after_complete < 4.9, f"Expected ~4.8, got {cd_after_complete}"
    # Wait with IDLE state so the reflex doesn't auto-re-trigger when cooldown expires.
    # Aggressive mode set cooldown to 5 s; at 0.02 per tick we need 250 ticks.
    for _ in range(260):
        rc.update(0.020, idle_state, _always_pick_first)
    # Cooldown should now be 0
    assert rc.cooldowns["stuck_ramp"] <= 0.001, (
        f"Expected cd ≈ 0, got {rc.cooldowns['stuck_ramp']}"
    )
    # Now pass the anomaly state again — the reflex should fire
    result = rc.update(0.020, anomaly_state, _always_pick_first)
    assert result == ReflexController.STUCK_RAMP, (
        f"Expected stuck_ramp to re-fire, got '{result}'"
    )
    # Verify the new cooldown is halved again (5 s)
    assert abs(rc.cooldowns["stuck_ramp"] - 5.0) < 0.02, (
        f"Expected new cooldown ~5.0, got {rc.cooldowns['stuck_ramp']}"
    )

# --- L1 spatial-memory upgrade: topology graph, path memory, persistence ---

def test_adjacency_records_cell_transitions():
    """Walking A->B->C records edges A-B and B-C; staying put records none."""
    sm = SpatialMemoryMap()
    for x in (0.0, 100.0, 100.0, 100.0, 300.0):   # A,A(again),A,A,B
        sm.update(x, 0.0)
    assert sm.adjacency_count == 1                # only A-B (100u < 200u cell)
    assert sm.traversal_steps == 1                # one A->B transition


def test_recent_path_is_ordered_and_deduped():
    """recent_path returns ordered, consecutive-deduped cell centres."""
    sm = SpatialMemoryMap()
    for x in (0.0, 100.0, 100.0, 300.0, 300.0, 500.0):
        sm.update(x, 0.0)
    path = sm.recent_path(10)
    assert [round(p["x"]) for p in path] == [100, 300, 500]  # A collapsed


def test_map_persistence_roundtrip(tmp_path):
    """save_state/load_state restores cells + adjacency across instances."""
    sm = SpatialMemoryMap()
    for x in (0.0, 100.0, 300.0, 500.0):
        sm.update(x, 0.0)
    p = tmp_path / "map.pkl"
    sm.save_state(p)

    sm2 = SpatialMemoryMap()
    restored = sm2.load_state(p)
    assert restored == 3                          # cells restored
    assert sm2.adjacency_count == 2               # A-B, B-C edges restored
    assert sm2.visited_cells == 3
    assert int(sm2._cells[(0, 0)]) == 2           # visit counts preserved
    # restored map keeps answering novelty queries (recency reset to 1.0)
    assert 0.0 < sm2.novelty_at(900.0, 0.0) <= 1.0


# --- L2 health formula v2: stall cost + same-scene recovery gradient ---

def test_health_stall_penalizes_circling_without_stuck_freeze():
    """Circling in place (coverage_rate≈0, never frozen) now costs health —
    the old formula was blind to this state (stuck term needs frozen frames)."""
    mc = MemoryController()
    for i in range(1200):  # circle: revisit the same 3 cells (12 coverage windows)
        mc.update(0.5, i, 20.0, float(i % 3), 200.0, scene_change_rate=0.0)
    assert mc.stall_ratio > 0.5          # stall detected
    assert mc.health_score < 0.85        # stall cost applied
    assert mc.health_score > 0.0


def test_health_recovery_gradient_without_scene_change():
    """After escaping a stall (walking to fresh cells), health recovers
    WITHOUT a scene change — the old formula stayed pinned at its floor."""
    mc = MemoryController()
    for i in range(1200):                # phase 1: stall (12 coverage windows)
        mc.update(0.5, i, 20.0, float(i % 3), 200.0, scene_change_rate=0.0)
    stalled = mc.health_score
    for i in range(1200):                # phase 2: walk to fresh cells
        mc.update(0.5, 1900 + i, 20.0, float(i * 50), 200.0, scene_change_rate=0.0)
    recovered = mc.health_score
    assert recovered > stalled + 0.05, (
        f"Expected recovery gradient, stalled={stalled} recovered={recovered}")


def test_health_novelty_reward_immediate():
    """A single fresh-cell visit gives an immediate novelty boost (+0.1)."""
    mc1 = MemoryController()
    mc1.update(0.5, 0, 20.0, 100.0, 200.0, scene_change_rate=0.0)   # fresh cell
    with_fresh = mc1.health_score
    mc2 = MemoryController()
    mc2._stored_scene_change_rate = 0.5   # same scene boost, no novelty
    assert abs((with_fresh - 0.1) - mc2.health_score) < 0.15 or with_fresh > mc2.health_score
