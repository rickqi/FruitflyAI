"""PIN: an UNOBSERVABLE lesson goal must not be counted as a failure.

The defect: `disp_60s` is published as `null` for roughly the first four minutes
after a brain restart while the displacement tracker warms up, and `_num(None)`
coerces that to 0.0.  A scalar `disp_60s > 30` goal therefore read as "not met"
on every warmup cycle, so `consecutive_fail` piled up on phantom failures —
observed live as 23 consecutive fails, all of them during a window when the brain
was dead or cold.  With the progressive ladder in place a spurious streak can
also retreat a stage, so this is a correctness bug, not cosmetic noise.

`_goal_met` now returns None for an unobservable metric, and `update_curriculum`
treats None as "do not count this attempt": the attempt is tallied and logged as
`met: null`, `unobserved` increments, and NEITHER streak moves.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin import coach_outcomes as co  # noqa: E402


GOAL = {"metric": "disp_60s", "op": "gt", "target": 30}


def _cur(**over):
    c = {"course": "general-escape", "stage": 1, "goal": dict(GOAL),
         "attempts": 0, "consecutive_ok": 0, "consecutive_fail": 0}
    c.update(over)
    return c


def _mem(disp=100.0, **over):
    m = {"stuck_duration": 1.0, "health_score": 0.7, "disp_60s": disp,
         "loop_score": 0.1}
    m.update(over)
    return m


class TestGoalMetTriState:
    def test_met(self):
        assert co._goal_met(GOAL, _mem(disp=100.0)) is True

    def test_not_met(self):
        assert co._goal_met(GOAL, _mem(disp=5.0)) is False

    def test_none_value_is_unknown(self):
        assert co._goal_met(GOAL, _mem(disp=None)) is None

    def test_missing_metric_is_unknown(self):
        mem = _mem()
        mem.pop("disp_60s")
        assert co._goal_met(GOAL, mem) is None

    def test_non_numeric_is_unknown(self):
        assert co._goal_met(GOAL, _mem(disp="n/a")) is None

    def test_bool_is_not_a_measurement(self):
        assert co._goal_met(GOAL, _mem(disp=True)) is None

    def test_empty_memory_is_unknown(self):
        assert co._goal_met(GOAL, {}) is None

    def test_unknown_operator_is_unknown(self):
        assert co._goal_met({"metric": "disp_60s", "op": "wat",
                             "target": 1}, _mem()) is None


class TestWarmupDoesNotPolluteStreaks:
    def test_repeated_unknowns_do_not_build_a_fail_streak(self):
        cur = _cur()
        for _ in range(23):
            cur = co.update_curriculum(cur, {"verdict": "unchanged"},
                                       _mem(disp=None))
        assert cur["consecutive_fail"] == 0, (
            "warmup cycles were counted as lesson failures")
        assert cur["consecutive_ok"] == 0
        assert cur["attempts"] == 23, "attempts must still be tallied"
        assert cur["unobserved"] == 23

    def test_unknown_does_not_break_an_ok_streak(self):
        cur = _cur()
        cur = co.update_curriculum(cur, {"verdict": "improved"}, _mem(disp=100))
        assert cur["consecutive_ok"] == 1
        cur = co.update_curriculum(cur, {"verdict": "unchanged"}, _mem(disp=None))
        assert cur["consecutive_ok"] == 1, (
            "an unobservable cycle reset a legitimate ok streak")
        cur = co.update_curriculum(cur, {"verdict": "improved"}, _mem(disp=100))
        assert cur["stage"] == 2, "promotion did not resume after warmup"

    def test_unknown_does_not_retreat_a_stage(self):
        cur = _cur(stage=3, goal=co.goal_for_stage(3))
        for _ in range(10):
            cur = co.update_curriculum(cur, {"verdict": "unchanged"},
                                       _mem(disp=None))
        assert cur["stage"] == 3, "unobservable cycles retreated the stage"

    def test_real_failures_still_retreat(self):
        cur = _cur(stage=3, goal=co.goal_for_stage(3))
        for _ in range(3):
            cur = co.update_curriculum(cur, {"verdict": "unchanged"},
                                       _mem(disp=1.0))
        assert cur["stage"] == 2, "genuine not-met cycles must still retreat"

    def test_history_records_null_not_false(self):
        cur = _cur()
        cur = co.update_curriculum(cur, {"verdict": "unchanged"}, _mem(disp=None))
        entry = cur["history"][-1]
        assert entry["met"] is None, (
            "history must distinguish 'unknown' from 'failed'")
        assert json.dumps(entry)              # still serialisable

    def test_real_failures_still_retreat_from_warmup_contamination(self):
        """A warmup burst followed by real successes must promote correctly."""
        cur = _cur()
        for _ in range(5):
            cur = co.update_curriculum(cur, {"verdict": "unchanged"},
                                       _mem(disp=None))
        for _ in range(2):
            cur = co.update_curriculum(cur, {"verdict": "improved"},
                                       _mem(disp=999.0))
        assert cur["stage"] == 2
