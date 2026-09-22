#!/usr/bin/env python3
"""P0-4 PIN — the help/escalation gates must not cancel each other (A2 §1.2 D2, §5 U1).

The incident this file pins: the coach was NOT woken at the one moment it was
needed.  Live form (user 09-17 ``90dd512b`` seq=17557 / 09-18 seq=331573):
median speed 316 u/s, 60 s displacement only 28 u, ``loop_score`` 0.93-0.99,
``stuck_duration`` 54 s and rising, ``health_score`` 0.62 — and yet
``check_help_needed()`` returned ``None``, because three gates cancelled:

  * ``main.py`` L2a required ``coverage_rate < 0.05`` while the live value was
    ``1.14`` (unit: percentage points of newly visited cells / 1000 ticks),
  * ``memory.py`` ``_detect_oscillating`` returned False on ``disp_60s > 300``,
  * ``memory.py`` ``_detect_micro_loop`` Tier-2 returned False on
    ``disp_60s > 300 and loop_score < 0.8`` — i.e. "fast motion = progress".

All of them now read ONE convention — the displacement *efficiency*
``disp_60s / (median_speed * 60)`` (progress-ledger block in
``fly64/fly64/memory.py``) — and motion alone never counts as progress.

RED before the fix (run from ``fly64/``)::

    python -m pytest tests/test_trigger_conflict.py -q
    → tests 1-3 fail (ctx is None), 6 fails (state idle),
      8 fails (burst precondition False / AttributeError),
      9-10 fail (guards)

The P0-4 API is imported lazily through :func:`_ledger` so that the RED run
fails as *assertions*, not as a pytest collection error.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugin.runner import PluginRunner  # noqa: E402

MAIN_SRC = ROOT / "fly64" / "main.py"
MEMORY_SRC = ROOT / "fly64" / "memory.py"

# ── the verbatim synthetic snapshot from the plan (P0-4 §3) ────────────────
VERBATIM_MEMORY = {
    "stuck_duration": 54.2,
    "anomaly_state": "idle",
    "health_score": 0.62,
    "reflex_active": True,
    "reflex_ineffective": False,
    "disp_60s": 2100.0,
}

# the same tick plus the telemetry /memory.json publishes for the window
WEAVE_MEMORY = dict(VERBATIM_MEMORY, median_speed=316.0, loop_score=0.99,
                    escape_behavior=True, scene_name="熔岩地 #6f2a",
                    position={"x": 120.0, "y": 120.0, "z": -40.0})

# the user-reported form: 316 u/s median, only 28 u of net displacement / 60 s
USER_REPORTED_MEMORY = dict(VERBATIM_MEMORY, disp_60s=28.0, median_speed=316.0,
                            loop_score=0.93, escape_behavior=True)

# a genuinely progressing fly at the same speed (18960 u = 316 u/s × 60 s)
PROGRESS_MEMORY = dict(VERBATIM_MEMORY, disp_60s=18960.0, median_speed=316.0)


def _ledger():
    """The P0-4 progress-ledger API (``fly64/fly64/memory.py``)."""
    from fly64 import memory
    return memory


def _runner() -> PluginRunner:
    r = PluginRunner(fetcher=lambda ep: {})
    r._prim_zero_run = 0
    return r


def _snapshot(mem: dict) -> dict:
    return {"memory": mem, "flow": {}, "help": {}, "evolution": {}}


# ── 1. the coach must be woken in the weave form ──────────────────────────
def test_high_speed_weave_wakes_coach_verbatim_snapshot():
    """Plan P0-4 §3, verbatim: this exact snapshot used to return None."""
    ctx = _runner().check_help_needed(_snapshot(dict(VERBATIM_MEMORY)))
    assert ctx is not None, "coach not woken in the high-speed weave form"
    assert ctx["help_reason"] == "weave_no_progress", ctx
    # the classifier disagrees with the behaviour — that IS the defect
    assert ctx["anomaly_state"] == "idle"
    assert ctx["stuck_duration"] == 54.2
    assert ctx["pos_y"] is None            # no position in this snapshot


def test_high_speed_weave_wakes_coach_with_speed_telemetry():
    ctx = _runner().check_help_needed(_snapshot(dict(WEAVE_MEMORY)))
    assert ctx is not None, "coach not woken with full telemetry"
    assert ctx["help_reason"] == "weave_no_progress", ctx
    floor = _ledger().PROGRESS_EFFICIENCY_FLOOR
    assert ctx["displacement_per_speed"] is not None
    assert ctx["displacement_per_speed"] < floor
    assert ctx["median_speed"] == 316.0


def test_user_reported_28u_displacement_also_wakes_coach():
    """stuck=54.2 s, 316 u/s median, 28 u / 60 s (user 09-18 live form)."""
    ctx = _runner().check_help_needed(_snapshot(dict(USER_REPORTED_MEMORY)))
    assert ctx is not None
    assert ctx["help_reason"] == "weave_no_progress", ctx
    assert ctx["displacement_per_speed"] < 0.01


def test_healthy_progress_does_not_wake_coach():
    """No over-triggering: same stuck clock, but real progress → no consult."""
    ctx = _runner().check_help_needed(_snapshot(dict(PROGRESS_MEMORY)))
    assert ctx is None, f"over-triggered on real progress: {ctx}"


# ── 2. one unit convention for the displacement efficiency ────────────────
def test_displacement_efficiency_units():
    m = _ledger()
    assert m.PROGRESS_EFFICIENCY_FLOOR == 0.25
    assert m.MOTION_DISP_60S == 300.0
    assert m.WEAVE_STUCK_DURATION == 45.0
    eff = m.displacement_per_speed(2100.0, 316.0)
    assert eff is not None and abs(eff - 2100.0 / (316.0 * 60.0)) < 1e-9
    assert eff < m.PROGRESS_EFFICIENCY_FLOOR          # weave, not progress
    assert m.displacement_per_speed(18960.0, 316.0) >= 0.99   # straight run
    assert m.displacement_per_speed(None, 316.0) is None     # no reading
    assert m.displacement_per_speed(2100.0, 0.0) is None     # no speed
    # motion alone is not progress (the D2 inversion)
    assert m.progress_is_ineffective(2100.0, None) is True
    assert m.progress_is_ineffective(28.0, None) is False    # too slow to weave
    assert m.progress_is_ineffective(None, None) is False    # no opinion


# ── 3. the anomaly classifier must see the high-speed weave ───────────────
def _feed(detector, *, disp_60s, median_speed, ticks=40, loop_score=0.99):
    for i in range(ticks):
        detector.update(control_x=(-70 if i % 2 == 0 else 70),
                        visited_cells=120, loop_score=loop_score,
                        stuck_duration=54.2, ramp_score=0.0, heading_rate=0.0,
                        wall_score=0.0, escape_behavior=True,
                        disp_60s=disp_60s, median_speed=median_speed)


def test_detector_calls_high_speed_weave_oscillating():
    """disp_60s=2100 at 316 u/s is a weave → oscillating, not idle."""
    m = _ledger()
    det = m.MotionStateDetector(window=30)      # production window
    _feed(det, disp_60s=2100.0, median_speed=316.0)
    assert det.active, "detector stayed idle on the weave form"
    assert det.active_state == m.MotionStateDetector.OSCILLATING, det.get_state()


def test_detector_still_treats_real_progress_as_progress():
    """Same alternating control, but the fly actually covers 316 u/s × 60 s."""
    m = _ledger()
    det = m.MotionStateDetector(window=30)
    _feed(det, disp_60s=18960.0, median_speed=316.0)
    assert not det.active or det.active_state != m.MotionStateDetector.OSCILLATING


def test_detector_micro_loop_tier2_not_gated_by_raw_displacement():
    """Tier-2 (stuck>90 s, loop>0.5) must not be cancelled by disp_60s alone."""
    m = _ledger()
    det = m.MotionStateDetector(window=5)
    for _ in range(10):
        det.update(visited_cells=120, loop_score=0.99, stuck_duration=95.0,
                   ramp_score=0.0, heading_rate=0.0, wall_score=0.0,
                   escape_behavior=True, disp_60s=2100.0, median_speed=316.0)
    assert det.active_state == m.MotionStateDetector.MICRO_LOOP, det.get_state()


# ── 4. the burst branch must be reachable without anomaly_state ───────────
def test_burst_branch_reachable_in_weave_form():
    """loop_score below the breakout threshold and stuck < 60 s: only the new
    progress-ledger criterion can open the burst."""
    m = _ledger()
    assert m.deadlock_burst_ready(stuck_duration=54.2, loop_score=0.85,
                                  disp_60s=2100.0, median_speed=316.0) is True
    # the live form (loop 0.99) is reachable too
    assert m.deadlock_burst_ready(stuck_duration=54.2, loop_score=0.99,
                                  disp_60s=2100.0, median_speed=316.0) is True


def test_burst_branch_not_reachable_when_progressing():
    m = _ledger()
    assert m.deadlock_burst_ready(stuck_duration=54.2, loop_score=0.85,
                                  disp_60s=18960.0, median_speed=316.0) is False
    assert m.deadlock_burst_ready(stuck_duration=10.0, loop_score=0.10,
                                  disp_60s=0.0, median_speed=None) is False


def test_burst_precondition_no_longer_reads_anomaly_state():
    """Static guard: the burst precondition (main.py) must not depend on the
    field the same displacement gate pins to 'idle'."""
    src = MAIN_SRC.read_text(encoding="utf-8")
    anchor = src.index("_deadlock_burst_remaining = 200")
    region = src[anchor - 1200: anchor + 800]
    assert "deadlock_burst_ready" in region, "burst precondition not rewired"
    assert "anomaly_state_name" not in region, (
        "burst precondition still reads anomaly_state_name (D2)")


def test_l2a_gate_no_longer_requires_low_coverage_rate():
    """Static guard: L2a must not be gated on coverage_rate < 0.05 (live 1.14)."""
    src = MAIN_SRC.read_text(encoding="utf-8")
    anchor = src.index("_stuck_no_progress = (")
    region = src[anchor: anchor + 400]
    assert "progress_is_ineffective" in region, "L2a gate not rewired"
    assert "coverage_rate < 0.05" not in region, (
        "L2a still compares the coverage_rate ratio against 0.05 (D2)")


# ── 5. the unit convention must be documented identically in both files ───
def test_unit_convention_documented_in_both_sources():
    """Acceptance P0-4: coverage_rate units + displacement efficiency are
    documented in one comment block referenced by both files."""
    marker = "disp_60s / (median_speed * 60)"
    for path in (MEMORY_SRC, MAIN_SRC):
        src = path.read_text(encoding="utf-8")
        assert marker in src, f"{path.name}: efficiency formula not documented"
        assert "percentage points / 1000 ticks" in src, (
            f"{path.name}: coverage_rate unit not documented")
        assert "coverage_rate 1.14" in src or "1.14" in src, (
            f"{path.name}: the live 1.14 counter-example is not recorded")
