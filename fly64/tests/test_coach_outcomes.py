"""PIN tests: coach outcome attribution + curriculum state machine (P1).

The attribution window turns one-shot coach advice into a measurable
场景 × 策略键 → 效果 table; the curriculum turns repeated outcomes into a
lesson plan (advance on ok-streak, retreat on fail-streak).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin import coach_outcomes as co  # noqa: E402

MEM = {"stuck_duration": 100.0, "health_score": 0.5, "disp_60s": 5.0,
       "loop_score": 0.9, "anomaly_state": "fallen", "scene_label": "洞穴"}


def _strategy():
    return {"exploration": {"bold_explore_stuck_s": 30, "turn_bias": 0.6}}


class TestSnapshotResolve:
    def test_snapshot_captures_keys_and_baseline(self):
        s = co.snapshot_outcome(_strategy(), MEM, {"scene_hash": "ab12cd"},
                                cycle=3, help_reason="unsolvable_stuck")
        assert s["keys"]["exploration"]["turn_bias"] == 0.6
        assert s["baseline"]["stuck_duration"] == 100.0
        assert s["scene_id"] == "ab12cd"
        assert s["help_reason"] == "unsolvable_stuck"

    def test_resolve_returns_none_inside_window(self):
        s = co.snapshot_outcome(_strategy(), MEM, {}, window_s=30)
        assert co.resolve_outcome(s, MEM) is None

    def test_resolve_improved_on_disp_up(self):
        s = co.snapshot_outcome(_strategy(), MEM, {})
        s["ts"] -= 31  # expire window
        after = dict(MEM, disp_60s=45.0, stuck_duration=40.0)
        rec = co.resolve_outcome(s, after)
        assert rec["verdict"] == "improved"
        assert rec["deltas"]["disp_60s"] == 40.0

    def test_resolve_worse_on_big_stuck_increase(self):
        s = co.snapshot_outcome(_strategy(), MEM, {})
        s["ts"] -= 31
        after = dict(MEM, stuck_duration=200.0, health_score=0.3)
        assert co.resolve_outcome(s, after)["verdict"] == "worse"

    def test_empty_pending_resolves_none(self):
        assert co.resolve_outcome(None, MEM) is None

    def test_degraded_memory_does_not_resolve(self):
        """A memory snapshot missing the baseline keys would produce an
        all-zero junk record — keep the window open instead."""
        s = co.snapshot_outcome(_strategy(), MEM, {})
        s["ts"] -= 31
        assert co.resolve_outcome(s, {}) is None              # empty snapshot
        assert co.resolve_outcome(s, {"loop_score": 0.9}) is None  # partial snapshot


class TestPersistence:
    def test_pending_roundtrip(self, tmp_path):
        s = co.snapshot_outcome(_strategy(), MEM, {})
        co.save_pending(s, tmp_path / "p.json")
        assert co.load_pending(tmp_path / "p.json")["keys"] == s["keys"]

    def test_append_and_load_outcomes(self, tmp_path):
        path = tmp_path / "outcomes.jsonl"
        s = co.snapshot_outcome(_strategy(), MEM, {})
        s["ts"] -= 31
        after = dict(MEM, disp_60s=45.0)
        co.append_outcome(co.resolve_outcome(s, after), path)
        co.append_outcome({"torn": True}, path)
        out = co.load_outcomes(path)
        assert len(out) == 2 and out[0]["verdict"] == "improved"


class TestCurriculum:
    def test_seeds_default_when_absent(self):
        """P1 bugfix: without seeding, update_curriculum(None) returned None
        and the state machine could never start."""
        c = co.update_curriculum(None, {"verdict": "unchanged"},
                                 {"disp_60s": 45.0})
        assert c is not None and c["course"] == "general-escape"
        assert c["stage"] == 1

    def _curriculum(self, **goal):
        return {"course": "escape-lava", "stage": 1, "attempts": 0,
                "goal": {"metric": "disp_60s", "op": "gt", "target": 30}, **goal}

    def _outcome(self, verdict):
        return {"verdict": verdict}

    def test_advance_after_ok_streak(self, tmp_path):
        c = self._curriculum()
        mem = {"disp_60s": 45.0}
        c = co.update_curriculum(c, self._outcome("improved"), mem)   # ok 1
        assert c["stage"] == 1                                        # streak 2 needed
        c = co.update_curriculum(c, self._outcome("improved"), mem)   # ok 2 → advance
        assert c["stage"] == 2 and c["consecutive_ok"] == 0

    def test_retreat_after_fail_streak(self, tmp_path):
        c = self._curriculum(stage=2)
        mem = {"disp_60s": 5.0}  # goal not met
        for _ in range(3):
            c = co.update_curriculum(c, self._outcome("unchanged"), mem)
        assert c["stage"] == 1 and c["consecutive_fail"] == 0

    def test_no_retreat_below_stage_1(self):
        c = self._curriculum(stage=1)
        mem = {"disp_60s": 5.0}
        for _ in range(5):
            c = co.update_curriculum(c, self._outcome("unchanged"), mem)
        assert c["stage"] == 1

    def test_history_bounded(self):
        c = self._curriculum()
        mem = {"disp_60s": 5.0}
        for _ in range(30):
            c = co.update_curriculum(c, self._outcome("unchanged"), mem)
        assert len(c["history"]) <= 20

    def test_curriculum_persist_roundtrip(self, tmp_path):
        c = self._curriculum()
        co.save_curriculum(c, tmp_path / "cur.json")
        assert co.load_curriculum(tmp_path / "cur.json")["goal"]["target"] == 30
