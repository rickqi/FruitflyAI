"""PIN: every help-escalation path must build its context without NameError.

Defect (in-flight patch, caught before it reached the runtime):
`scripts/m8_add_posy_to_consult.py` inserted `"pos_y": pos_y_ctx` into three
returned context dicts, but its definition-insertion `str.replace` never matched
the source (wrong indentation assumption, and an `if self._prim_zero_run >= 3:`
block sits between the two lines it searched for).  `str.replace` is silent when
it does not match, so the script printed success while the name stayed
undefined.

Consequence had it shipped: `check_help_needed` raises NameError on the
`reflex_ineffective_stuck` / `unsolvable_stuck` / `multi_signal_stuck` paths —
i.e. the coach crashes exactly when the fly is stuck, which is the only time it
is consulted at all.

These tests exercise all three paths and assert the returned context carries
`pos_y`, so a missing definition fails here instead of in the game.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from plugin.runner import PluginRunner  # noqa: E402


class _StubConsultant:
    """Never talks to GLM — these tests only exercise context construction."""

    def consult(self, *_a, **_k):        # pragma: no cover - not reached
        raise AssertionError("consult must not be called")


def _runner():
    """A runner with the network fetch and the LLM stubbed out."""
    return PluginRunner(fetcher=lambda _ep: {}, consultant=_StubConsultant(),
                        writer=None)


def _snapshot(memory, flow=None):
    return {"memory": memory, "flow": flow or {}}


def _mem(**over):
    mem = {
        "stuck_duration": 200.0,
        "anomaly_state": "micro_loop",
        "health_score": 0.3,
        "position": {"x": 10.0, "y": 1234.5, "z": 20.0},
        "disp_60s": 0.0,
        "reflex_active": False,
        "reflex_ineffective": False,
        "scene_name": "致命熔岩地 #20c6",
    }
    mem.update(over)
    return mem


class TestEscalationPathsCarryPosY:
    def test_reflex_ineffective_path(self):
        r = _runner()
        r._prim_zero_run = 0
        ctx = r.check_help_needed(_snapshot(_mem(reflex_active=True,
                                                reflex_ineffective=True)))
        assert ctx is not None
        assert ctx["help_reason"] == "reflex_ineffective_stuck"
        assert ctx["pos_y"] == 1234.5, ctx

    def test_unsolvable_stuck_path(self):
        r = _runner()
        ctx = r.check_help_needed(_snapshot(_mem(reflex_active=False)))
        assert ctx is not None
        assert ctx["help_reason"] == "unsolvable_stuck"
        assert ctx["pos_y"] == 1234.5, ctx

    def test_primitive_ineffective_path(self):
        r = _runner()
        r._prim_zero_run = 2              # third zero-progress completion fires
        mem = _mem(cpg={"completed": 5, "zero_run": 3})
        ctx = r.check_help_needed(_snapshot(mem))
        assert ctx is not None
        assert ctx["help_reason"] == "primitive_ineffective"
        assert ctx["pos_y"] == 1234.5, ctx

    def test_multi_signal_path(self):
        r = _runner()
        r.help_score_threshold = 0.0      # force the weighted branch
        ctx = r.check_help_needed(_snapshot(_mem(stuck_duration=50.0,
                                                reflex_ineffective=True),
                                           flow={"danger_red_index": 0.9}))
        assert ctx is not None
        assert ctx["help_reason"] == "multi_signal_stuck"
        assert ctx["pos_y"] == 1234.5, ctx


class TestPosYFallbacks:
    def test_explicit_pos_y_wins(self):
        r = _runner()
        ctx = r.check_help_needed(_snapshot(_mem(pos_y=777.0)))
        assert ctx["pos_y"] == 777.0

    def test_missing_position_yields_none_not_a_crash(self):
        r = _runner()
        ctx = r.check_help_needed(_snapshot(_mem(position={})))
        assert ctx is not None and ctx["pos_y"] is None

    def test_position_absent_yields_none(self):
        r = _runner()
        mem = _mem()
        mem.pop("position")
        ctx = r.check_help_needed(_snapshot(mem))
        assert ctx is not None and ctx["pos_y"] is None


class TestSourceIsDefined:
    def test_pos_y_ctx_is_assigned_before_use(self):
        """Static guard: the name must be bound BEFORE its first code use.

        Comment lines are skipped: the explanatory note in runner.py quotes the
        very string being searched for, and a naive `str.index` on the whole
        source would match the comment and report a false ordering violation.
        """
        import inspect
        src = inspect.getsource(PluginRunner.check_help_needed)
        code = [(i, l) for i, l in enumerate(src.split("\n"))
                if not l.lstrip().startswith("#")]

        def first_index(needle):
            for i, line in code:
                if needle in line:
                    return i
            return None

        assign = first_index("pos_y_ctx = ")
        use = first_index('"pos_y": pos_y_ctx')
        assert assign is not None, (
            "pos_y_ctx is used but never assigned — every help path would "
            "raise NameError")
        assert use is not None, "the pos_y key disappeared from the context"
        assert assign < use, (
            f"pos_y_ctx is first assigned on code line {assign} but first used "
            f"on line {use} — NameError on every help escalation")

    def test_all_context_dicts_carry_pos_y(self):
        import inspect
        src = inspect.getsource(PluginRunner.check_help_needed)
        assert src.count('"pos_y": pos_y_ctx') >= 3, (
            "expected pos_y in the primitive_ineffective / stuck / "
            "multi_signal contexts")
