#!/usr/bin/env python3
"""t24 regression: EscapeEventBuffer five-state outcome + composite schema.

Covers: every outcome branch (in_progress / resolved_effective /
resolved_ineffective / escalated / aborted), composite reasons list,
behavioural snapshot fields, post-escape anomaly tagging, efficiency ratio
inputs, and the new counters contract (source-level + buffer-level).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fly64.main import EscapeEventBuffer  # noqa: E402


class TestFiveStateOutcome:
    def test_in_progress_then_effective(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "stuck", 0, 0, reasons=["stuck", "cliff"])
        ev = b.get_recent(1)[0]
        assert ev["outcome"] == "in_progress"
        b.update_current(2.0)
        out = b.resolve_current(85.0)          # > 30u
        assert out == "resolved_effective"
        ev = b.get_recent(1)[0]
        assert ev["outcome"] == "resolved_effective"
        assert ev["distance_moved"] == 85.0
        assert ev["duration"] == 2.0

    def test_ineffective_at_or_below_30u(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "fallen", 0, 0)
        b.resolve_current(30.0)                # exactly 30u = ineffective
        assert b.get_recent(1)[0]["outcome"] == "resolved_ineffective"

    def test_escalated_on_immediate_reescape(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "stuck", 0, 0)
        b.resolve_current(5.0)                 # ineffective
        b.start_event(3.0, "stuck", 2, 2)      # re-escape 2s later (< 10s)
        evs = b.get_recent(2)
        assert evs[0]["outcome"] == "escalated"   # previous event marked
        assert evs[1]["outcome"] == "in_progress"  # the new attempt
        assert b.get_recent(1)[0]["outcome"] == "in_progress"

    def test_no_escalation_after_window(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "stuck", 0, 0)
        b.resolve_current(80.0)
        b.start_event(60.0, "cliff", 10, 10)   # 59s later — outside window
        evs = b.get_recent(2)
        assert evs[0]["outcome"] == "resolved_effective"  # not escalated
        assert evs[1]["outcome"] == "in_progress"

    def test_aborted(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "flow", 0, 0)
        b.resolve_current(0.0, aborted=True)
        assert b.get_recent(1)[0]["outcome"] == "aborted"

    def test_custom_threshold(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "stuck", 0, 0)
        b.resolve_current(45.0, effective_min_u=50.0)
        assert b.get_recent(1)[0]["outcome"] == "resolved_ineffective"


class TestCompositeSchema:
    def test_reasons_list_and_snapshot(self):
        b = EscapeEventBuffer()
        ev = b.start_event(5.0, "fallen", 1, 2,
                           reasons=["fallen", "stuck", "cliff"],
                           snapshot={
                               "anomaly_state": "micro_loop",
                               "anomaly_duration": 12.5,
                               "terrain": "indoor",
                               "loop_score": 0.97,
                               "novelty": 0.31,
                               "coach_keys": {"turn_bias": 0.7,
                                              "bold_explore_stuck_s": 40.0},
                           })
        assert ev["reasons"] == ["fallen", "stuck", "cliff"]
        assert ev["reason"] == "fallen"          # primary = first
        assert ev["anomaly_state"] == "micro_loop"
        assert ev["terrain"] == "indoor"
        assert ev["loop_score"] == 0.97
        assert ev["coach_keys"]["turn_bias"] == 0.7

    def test_minimal_event_gets_defaults(self):
        b = EscapeEventBuffer()
        ev = b.start_event(1.0, "stuck", 0, 0)   # legacy-style call
        assert ev["reasons"] == ["stuck"]
        assert ev["anomaly_state"] == ""
        assert ev["coach_keys"] == {}
        assert ev["post_escape_anomaly"] is None

    def test_post_escape_anomaly_tagging(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "stuck", 0, 0)
        b.resolve_current(60.0)
        assert b.mark_post_escape_anomaly("wall_stuck") is True
        assert b.get_recent(1)[0]["post_escape_anomaly"] == "wall_stuck"
        # only tagged once; in_progress events are never tagged
        assert b.mark_post_escape_anomaly("micro_loop") is False
        b.start_event(9.0, "cliff", 1, 1)
        assert b.mark_post_escape_anomaly("micro_loop") is False

    def test_efficiency_ratio_inputs(self):
        b = EscapeEventBuffer()
        b.start_event(1.0, "stuck", 0, 0)
        b.update_current(4.0)                   # duration 4s
        b.resolve_current(60.0)                 # 60u / 4s = 15 u/s
        ev = b.get_recent(1)[0]
        assert ev["duration"] == 4.0 and ev["distance_moved"] == 60.0


class TestCountersContract:
    def test_new_counter_keys_documented_in_main(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        for key in ("total_cliff_escapes", "total_fallen_escapes",
                    "total_stuck_escapes", "effective_count",
                    "ineffective_count", "effectiveness_rate"):
            assert key in src, key
