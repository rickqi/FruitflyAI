#!/usr/bin/env python3
"""Regression tests for the LLM dialogue key-decision + pause-wait mode.

BRAIN 2.4.0 (agent.md rule 8).  Covers:

1. Dialogue decision parsing: press_a / press_b / none / invalid output.
2. 10-minute (600s) wait budget: LLM timeout -> autonomous press_a
   fallback with timed_out=True.
3. active_strategy.json atomic writes: dialogue_decision merged via
   tmp-file + os.replace, existing strategy sections preserved.
4. Pause-wait state machine: pause while waiting, consume decision
   exactly once per episode, hold-press ticks, belt-and-braces
   DIALOGUE_LLM_WAIT_S fallback.
5. telemetry: flow.json exposes llm_decision{status,action,reason,
   episode,wait_s,ts}.

Everything runs offline: LLM responses and screenshots are mocked.
Modules are loaded with importlib.util.spec_from_file_location.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
MAIN_PATH = PROJECT / "fly64" / "main.py"
GOOD_FRAME = base64.b64encode(b"fake-screenshot-bytes").decode("ascii")


# ── module loading (importlib.util.spec_from_file_location) ─────────────

def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_BRAIN = None


def _load_brain():
    """Load fly64/fly64/main.py as package module 'fly64_brain.main'."""
    global _BRAIN
    if _BRAIN is None:
        pkg_name = "fly64_brain"
        if pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = [str(PROJECT / "fly64")]
            sys.modules[pkg_name] = pkg
        name = pkg_name + ".main"
        if name not in sys.modules:
            _load_module(name, MAIN_PATH)
        _BRAIN = sys.modules[name]
    return _BRAIN


@pytest.fixture(scope="module")
def brain_main():
    return _load_brain()


@pytest.fixture(scope="module")
def llm_consult():
    return _load_module("fly64_plugin_llm_consult", PROJECT / "plugin" / "llm_consult.py")


@pytest.fixture(scope="module")
def strategy_writer_mod():
    return _load_module("fly64_plugin_strategy_writer",
                        PROJECT / "plugin" / "strategy_writer.py")


def make_consultant(llm_consult, tmp_path, subagent_fn, timeout=5.0):
    kw = dict(transport="subagent",
              request_path=tmp_path / "req.json",
              response_path=tmp_path / "resp.json", timeout=timeout)
    if subagent_fn is not None:
        kw["subagent_fn"] = subagent_fn
    return llm_consult.GLMConsultant(**kw)


def make_writer(strategy_writer_mod, tmp_path):
    return strategy_writer_mod.StrategyWriter(
        strategy_path=tmp_path / "active_strategy.json",
        advice_path=tmp_path / "coach_advice.json")


# ── 1. decision parsing ──────────────────────────────────────────────────

class TestDialogueDecisionParsing:
    def test_press_a(self, llm_consult):
        out = llm_consult.parse_dialogue_response(
            '{"action": "press_a", "reason": "推进对话"}')
        assert out == {"action": "press_a", "reason": "推进对话"}

    def test_press_b_fenced(self, llm_consult):
        out = llm_consult.parse_dialogue_response(
            '```json\n{"action": "press_b", "reason": "跳过"}\n```')
        assert out["action"] == "press_b"

    def test_none_explicit(self, llm_consult):
        out = llm_consult.parse_dialogue_response(
            '{"action": "none", "reason": "对话框展开中"}')
        assert out == {"action": "none", "reason": "对话框展开中"}

    @pytest.mark.parametrize("raw", [
        '{"action": "dance"}',            # invalid action
        '{"action": ""}',                 # empty action
        '{"reason": "no action key"}',    # missing action
        '不是 JSON 的输出',                 # free prose
        '',                               # empty reply
        'null',                           # non-dict JSON
    ])
    def test_invalid_output_degrades_to_none(self, llm_consult, raw):
        out = llm_consult.parse_dialogue_response(raw)
        assert out["action"] == "none"
        assert isinstance(out["reason"], str)

    def test_case_and_whitespace_normalised(self, llm_consult):
        out = llm_consult.parse_dialogue_response('{"action": " PRESS_A "}')
        assert out["action"] == "press_a"

    def test_consult_dialogue_end_to_end_mocked(self, llm_consult, tmp_path):
        c = make_consultant(
            llm_consult, tmp_path,
            lambda req: '{"action": "press_b", "reason": "取消"}')
        out = c.consult_dialogue(GOOD_FRAME, timeout=30.0)
        assert out["action"] == "press_b"
        req = json.loads((tmp_path / "req.json").read_text("utf-8"))
        assert req["kind"] == "dialogue_decision"
        assert req["frame_b64"] == GOOD_FRAME  # screenshot was sent


# ── 2. 600s timeout -> autonomous press_a fallback ──────────────────────

class TestTimeoutFallback:
    def test_llm_never_responds_raises_consult_error(self, llm_consult, tmp_path):
        # File-based exchange with no response file produced in time.
        c = make_consultant(llm_consult, tmp_path, None, timeout=0.5)
        with pytest.raises(llm_consult.ConsultError):
            c.consult_dialogue(GOOD_FRAME, timeout=0.5)

    def test_worker_timeout_fallback_press_a(self, llm_consult,
                                             strategy_writer_mod, tmp_path):
        """Replicates main._request_dialogue_decision's exception path."""
        def blow_up(req):
            raise llm_consult.ConsultError(
                "subagent response not produced within 600s")
        c = make_consultant(llm_consult, tmp_path, blow_up)
        w = make_writer(strategy_writer_mod, tmp_path)
        w.write_strategy({"fallen_recovery": {"mode": "mirror"}}, advice="keep")
        # worker logic under test (mirrors fly64/main.py lines 517-543)
        status, decision, timed_out = "waiting", None, False
        try:
            parsed = c.consult_dialogue(GOOD_FRAME, timeout=600.0)
            decision = {"action": parsed.get("action", "none"),
                        "reason": parsed.get("reason", ""), "ts": 1.0}
            status = "decided"
        except Exception as exc:
            decision = {"action": "press_a",
                        "reason": f"LLM timeout/error, autonomous fallback: {exc}",
                        "ts": 2.0}
            status = "timeout"
            timed_out = True
        assert status == "timeout"
        assert decision["action"] == "press_a"        # autonomous A fallback
        assert "autonomous fallback" in decision["reason"]
        w.write_dialogue_decision(decision["action"], decision["reason"],
                                  wait_seconds=600.1, timed_out=timed_out)
        data = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        d = data["dialogue_decision"]
        assert d["action"] == "press_a" and d["timed_out"] is True

    def test_wait_budget_is_600s(self):
        assert _load_brain().DIALOGUE_LLM_WAIT_S == 600.0  # 10 minutes

    def test_caller_timeout_restored_after_budget_use(self, llm_consult, tmp_path):
        c = make_consultant(llm_consult, tmp_path,
                            lambda req: '{"action": "none"}', timeout=5.0)
        c.consult_dialogue(GOOD_FRAME, timeout=600.0)
        assert c.timeout == 5.0


# ── 3. active_strategy.json atomic write ────────────────────────────────

class TestAtomicStrategyWrite:
    def test_decision_merges_and_preserves_sections(self, strategy_writer_mod,
                                                    tmp_path):
        w = make_writer(strategy_writer_mod, tmp_path)
        w.write_strategy({"fallen_recovery": {"mode": "directional_climb",
                                              "climb_period": 3.0},
                          "exploration": {"turn_bias": 15.0}}, advice="v1")
        w.write_dialogue_decision("press_a", "推进", wait_seconds=3.4)
        data = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        assert data["dialogue_decision"]["action"] == "press_a"
        assert data["dialogue_decision"]["wait_seconds"] == 3.4
        assert data["dialogue_decision"]["timed_out"] is False
        assert data["fallen_recovery"]["mode"] == "directional_climb"
        assert data["exploration"]["turn_bias"] == 15.0

    def test_no_tmp_file_left_behind(self, strategy_writer_mod, tmp_path):
        w = make_writer(strategy_writer_mod, tmp_path)
        w.write_dialogue_decision("none", "等待")
        assert (tmp_path / "active_strategy.json").is_file()
        assert not (tmp_path / "active_strategy.json.tmp").exists()

    def test_write_goes_through_tmp_then_replace(self, strategy_writer_mod,
                                                 tmp_path, monkeypatch):
        """Atomicity: bytes land in .tmp first; a crash mid-write cannot
        corrupt the existing strategy file (os.replace is the commit point)."""
        w = make_writer(strategy_writer_mod, tmp_path)
        w.write_strategy({"fallen_recovery": {"mode": "mirror"}}, advice="old")
        before = (tmp_path / "active_strategy.json").read_bytes()
        calls = []

        def fake_replace(src, dst):
            calls.append((str(src), str(dst)))
            assert str(src).endswith(".tmp")
            # content is fully staged in tmp before the atomic swap
            staged = json.loads(Path(src).read_text("utf-8"))
            assert staged["dialogue_decision"]["action"] == "press_b"
            raise RuntimeError("crash before commit")

        import fly64_plugin_strategy_writer as swm
        monkeypatch.setattr(swm.os, "replace", fake_replace)
        with pytest.raises(RuntimeError):
            w.write_dialogue_decision("press_b", "取消")
        # destination untouched — no torn write
        assert (tmp_path / "active_strategy.json").read_bytes() == before
        assert calls and calls[0][1].endswith("active_strategy.json")

    def test_invalid_existing_file_still_writable(self, strategy_writer_mod,
                                                  tmp_path):
        w = make_writer(strategy_writer_mod, tmp_path)
        (tmp_path / "active_strategy.json").write_text("{corrupt", "utf-8")
        w.write_dialogue_decision("press_a", "ok")
        data = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        assert data["dialogue_decision"]["action"] == "press_a"


# ── 4. pause-wait state machine ─────────────────────────────────────────

class _Ctrl:
    def __init__(self):
        self.x = 30
        self.y = 40
        self.jump = True
        self.b = False


class TestPauseWaitStateMachine:
    """Faithful simulation of the dialogue override branch in
    fly64/main.py (BRAIN 2.4.0), driven with mocked LLM decisions."""

    PRESS_TICKS = 12  # DIALOGUE_PRESS_TICKS

    def _tick(self, ctrl, st):
        """One iteration of the dialogue final-override block."""
        st.setdefault("press_hold", 0)
        st.setdefault("press_b", False)
        ctrl.x = 0
        ctrl.y = 0
        ctrl.jump = False
        ctrl.b = False
        if (st["decision"] is not None and st["decision_ep"] == st["episode"]
                and not st["consumed"]):
            action = st["decision"].get("action", "none")
            if action in ("press_a", "press_b"):
                st["press_hold"] = self.PRESS_TICKS
                st["press_b"] = action == "press_b"
            st["consumed"] = True
        if st["press_hold"] > 0:
            st["press_hold"] -= 1
            if st["press_b"]:
                ctrl.b = True
            else:
                ctrl.jump = True
        elif (st["decision"] is None
              and st["wait_elapsed"] >= _load_brain().DIALOGUE_LLM_WAIT_S):
            ctrl.jump = True   # belt-and-braces autonomous A fallback

    def _st(self, decision=None, decision_ep=-1, episode=1, wait_elapsed=0.0):
        return {"decision": decision, "decision_ep": decision_ep,
                "episode": episode, "consumed": False,
                "wait_elapsed": wait_elapsed}

    def test_pauses_while_waiting(self):
        ctrl, st = _Ctrl(), self._st(decision=None)
        self._tick(ctrl, st)
        assert (ctrl.x, ctrl.y) == (0, 0)          # brain paused
        assert not ctrl.jump and not ctrl.b        # no premature press

    def test_press_a_decision_executes_and_consumed_once(self):
        ctrl = _Ctrl()
        st = self._st(decision={"action": "press_a"}, decision_ep=1)
        self._tick(ctrl, st)
        assert ctrl.jump is True and ctrl.b is False
        assert st["consumed"] is True
        for _ in range(self.PRESS_TICKS - 1):
            self._tick(ctrl, st)
            assert ctrl.jump is True               # held ~0.2s
        self._tick(ctrl, st)                       # hold expired
        assert ctrl.jump is False
        self._tick(ctrl, st)
        assert ctrl.jump is False                  # no repeat press

    def test_press_b_decision_sets_b_button(self):
        ctrl = _Ctrl()
        st = self._st(decision={"action": "press_b"}, decision_ep=1)
        self._tick(ctrl, st)
        assert ctrl.b is True and ctrl.jump is False

    def test_none_decision_no_press(self):
        ctrl = _Ctrl()
        st = self._st(decision={"action": "none"}, decision_ep=1)
        self._tick(ctrl, st)
        assert not ctrl.jump and not ctrl.b

    def test_stale_episode_decision_ignored(self):
        ctrl = _Ctrl()
        st = self._st(decision={"action": "press_a"}, decision_ep=0, episode=1)
        self._tick(ctrl, st)
        assert not ctrl.jump and st["consumed"] is False

    def test_belt_and_braces_timeout_autonomous_a(self):
        ctrl = _Ctrl()
        st = self._st(decision=None, wait_elapsed=600.0)
        self._tick(ctrl, st)
        assert ctrl.jump is True                   # fallback A press
        st2 = self._st(decision=None, wait_elapsed=599.9)
        ctrl2 = _Ctrl()
        self._tick(ctrl2, st2)
        assert ctrl2.jump is False                 # still inside budget: wait

    def test_wait_constant_and_press_ticks_wired(self):
        brain = _load_brain()
        assert brain.DIALOGUE_PRESS_TICKS == self.PRESS_TICKS


# ── 5. telemetry llm_decision field ─────────────────────────────────────

class TestTelemetryLlmDecision:
    def test_flow_payload_contains_llm_decision_block(self):
        src = MAIN_PATH.read_text(encoding="utf-8")
        assert '"llm_decision"' in src
        assert '"status"' in src and '"action"' in src
        assert '"reason"' in src and '"episode"' in src
        assert '"wait_s"' in src

    def test_status_values_cover_lifecycle(self):
        src = MAIN_PATH.read_text(encoding="utf-8")
        for state in ("idle", "waiting", "decided", "timeout"):
            assert f'"{state}"' in src

    def test_wait_s_published_while_waiting(self):
        src = MAIN_PATH.read_text(encoding="utf-8")
        # wait_s is only non-null while status == waiting
        assert 'if llm_decision_status == "waiting" else None' in src

    def test_brain_version_bumped(self):
        # Version line only moves forward (introduced at 2.4.0).
        ver = _load_brain().BRAIN_VERSION
        parts = [int(p) for p in ver.split(".")]
        assert parts >= [2, 4, 0], ver


# ── 6. worker thread integration (real threads, mocked LLM) ─────────────

class TestWorkerThreadIntegration:
    def test_decision_thread_publishes_and_writes(self, llm_consult,
                                                  strategy_writer_mod, tmp_path):
        c = make_consultant(
            llm_consult, tmp_path,
            lambda req: '{"action": "press_a", "reason": "ok"}')
        w = make_writer(strategy_writer_mod, tmp_path)
        result = {}

        def worker():   # mirrors main._request_dialogue_decision
            try:
                parsed = c.consult_dialogue(GOOD_FRAME, timeout=600.0)
                result["decision"] = {"action": parsed.get("action", "none"),
                                      "reason": parsed.get("reason", "")}
                result["status"] = "decided"
                result["timed_out"] = False
            except Exception as exc:
                result["decision"] = {"action": "press_a", "reason": str(exc)}
                result["status"] = "timeout"
                result["timed_out"] = True
            w.write_dialogue_decision(result["decision"]["action"],
                                      result["decision"]["reason"],
                                      wait_seconds=0.1,
                                      timed_out=result["timed_out"])

        import threading
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=10)
        assert not t.is_alive()
        assert result["status"] == "decided"
        assert result["decision"]["action"] == "press_a"
        data = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        assert data["dialogue_decision"]["action"] == "press_a"
        assert data["dialogue_decision"]["timed_out"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
