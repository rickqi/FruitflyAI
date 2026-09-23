#!/usr/bin/env python3
"""P1-2 CONTRACT GUARD: coach prompt range == brain clamp, command lands.

WHY THIS FILE EXISTS
--------------------
P0-4 live verification (docs/analysis/analysis-p0-4-live-verification.md §3.5/§四)
caught the coach being asked for values the brain refuses:

    coach strategy : turn_bias=0.8   bold_explore_stuck_s=20.0  command{turn_and_go,45,2.5,70}
    file after ~26s: turn_bias=0.25  bold_explore_stuck_s=10.0  (no command section *seen*)

and `fly64/main.py` clamps exactly like that on every 600-tick hot-reload
(``max(0.0, min(0.25, ...))`` / ``max(1, min(10, ...))``).  The prompt advertised
``turn_bias 0-1`` and ``bold_explore_stuck_s 建议 20-120``, so **every value the
coach emitted above the ceiling was silently eaten** — "机制存在、报告成功、无法生效".

What this module pins
---------------------
1. The prompt's declared windows are DERIVED from ``plugin.llm_consult``'s
   constants, and those constants are re-derived from ``fly64/main.py``'s live
   clamp expressions here — a clamp change without a prompt change (or the
   reverse) fails instead of quietly voiding the coach.
2. The prompt's own example JSON stays inside the accepted windows (it used to
   teach ``bold_explore_stuck_s: 60.0``, above the 10 s ceiling).
3. The direct-control channel really lands: a coach reply carrying
   ``command{turn_and_go}`` reaches ``active_strategy.json``, is readable through
   the brain's real ``load_active_strategy``, and the brain's consumer formulas
   turn it into model flags.  A ``command`` hoisted OUT of ``strategy`` (a common
   model deviation) is recovered instead of dropped.
4. The requested-vs-accepted record (``coach_acceptance``) is written to
   ``active_strategy.json`` / ``coach_advice.json`` and its "effective" value
   equals what main.py's clamp will really use.

Nothing here touches production artifacts: every writer points at ``tmp_path``
and the consultant is a stub (no network, no DSH session).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent          # fly64/
sys.path.insert(0, str(ROOT))

from plugin.llm_consult import (COACH_NUMERIC_WINDOWS,  # noqa: E402
                                BOLD_EXPLORE_STUCK_S_ACCEPTED,
                                COMMAND_DURATION_S_ACCEPTED,
                                COMMAND_HEADING_ACCEPTED, COMMAND_Y_ACCEPTED,
                                ESCAPE_STUCK_THRESHOLD_S_ACCEPTED,
                                GLMConsultant, PROMPT_TEMPLATE,
                                SECTION_SPECS, TURN_BIAS_ACCEPTED,
                                acceptance_report, sanitize_strategy, window_text)
from plugin.runner import PluginRunner                     # noqa: E402
from plugin.strategy_writer import StrategyWriter          # noqa: E402
from fly64.main import load_active_strategy                # noqa: E402

MAIN_SRC = (ROOT / "fly64" / "main.py").read_text(encoding="utf-8")
CONSULT_SRC = (ROOT / "plugin" / "llm_consult.py").read_text(encoding="utf-8")

#: the live coach reply from the P0-4 verification (§四) — values above the
#: brain's window, exactly as the running model emitted them.
LIVE_STRATEGY = {
    "fallen_recovery": {"mode": "directional_climb"},
    "exploration": {"bold_explore_stuck_s": 20.0, "turn_bias": 0.8},
    "escape": {"stuck_threshold_s": 8.0},
    "command": {"type": "turn_and_go", "heading": 45, "duration_s": 2.5, "y": 70},
}
LIVE_REPLY = json.dumps({
    "scene_elements": ["水", "绿地"],
    "what_i_see": ["×12", "MARIO"],
    "problem": "卡在蓝水里打转",
    "action": "转向并连跳",
    "advice": "别在蓝水里打转了，立刻朝右上角那抹绿色岸边猛转方向并连跳爬上岸！",
    "strategy": LIVE_STRATEGY,
}, ensure_ascii=False)

#: main.py's clamp bounds, read from source rather than hardcoded here.  P1-1
#: (t1) moved the inline `max(0.0, min(0.25, ...))` assignments into the
#: module-level ``CLAMP_BOUNDS`` table applied by ``apply_strategy_clamps``; the
#: older inline form is still recognised so this guard does not depend on which
#: shape is in the tree.
_CLAMP_BOUNDS_RE = {
    key: re.compile(r'"exploration\.%s"\s*:\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)'
                    % key)
    for key in ("turn_bias", "bold_explore_stuck_s")
}
_LEGACY_CLAMP_RES = {
    "turn_bias": re.compile(
        r'if\s+"turn_bias"\s+in\s+_expl:\s*\n\s*_expl\["turn_bias"\]\s*=\s*'
        r'max\(([-\d.]+),\s*min\(([-\d.]+),'),
    "bold_explore_stuck_s": re.compile(
        r'if\s+"bold_explore_stuck_s"\s+in\s+_expl:\s*\n\s*'
        r'_expl\["bold_explore_stuck_s"\]\s*=\s*max\(([-\d.]+),\s*min\(([-\d.]+),'),
}


def _clamp_bounds(key: str) -> tuple:
    """(lo, hi) of main.py's clamp for a coach exploration key, from source."""
    for pattern in (_CLAMP_BOUNDS_RE[key], _LEGACY_CLAMP_RES[key]):
        m = pattern.search(MAIN_SRC)
        if m:
            return float(m.group(1)), float(m.group(2))
    raise AssertionError(
        "fly64/main.py no longer contains the hot-reload clamp bounds for %r — "
        "if the clamp moved, update plugin/llm_consult's accepted windows and "
        "this guard together (P1-2)" % key)


def _effective(value: float, window: tuple) -> float:
    lo, hi = window
    return max(lo, min(hi, value))


def _strategy_of(prompt: str) -> dict:
    """The `strategy` object out of the prompt's example JSON."""
    marker = '{"scene_elements"'
    idx = prompt.find(marker)
    assert idx >= 0, "the prompt's example JSON disappeared"
    obj, _end = json.JSONDecoder().raw_decode(prompt[idx:])
    return obj["strategy"]


def consult_with(tmp_path: Path, reply: str) -> dict:
    """Run consult() against a stub model reply (no network, no DSH session)."""
    c = GLMConsultant(transport="subagent", subagent_fn=lambda req: reply,
                      request_path=tmp_path / ".consult_request.json",
                      response_path=tmp_path / ".consult_response.json")
    return c.consult({"help_reason": "weave_no_progress"}, None)


def writer_for(tmp_path: Path) -> StrategyWriter:
    return StrategyWriter(strategy_path=tmp_path / "active_strategy.json",
                          advice_path=tmp_path / "coach_advice.json")


# ── 1. prompt window == brain clamp ────────────────────────────────────────
class TestPromptRangeMatchesTheBrainClamp:
    def test_turn_bias_window_equals_main_clamp(self):
        bounds = _clamp_bounds("turn_bias")
        assert bounds == TURN_BIAS_ACCEPTED, (
            "plugin/llm_consult.TURN_BIAS_ACCEPTED=%s drifted from main.py's "
            "clamp %s" % (TURN_BIAS_ACCEPTED, bounds))
        assert window_text(TURN_BIAS_ACCEPTED) in PROMPT_TEMPLATE, (
            "the prompt does not state the real usable turn_bias window %r"
            % window_text(TURN_BIAS_ACCEPTED))

    def test_bold_explore_window_equals_main_clamp(self):
        bounds = _clamp_bounds("bold_explore_stuck_s")
        assert bounds == BOLD_EXPLORE_STUCK_S_ACCEPTED, (
            "plugin/llm_consult.BOLD_EXPLORE_STUCK_S_ACCEPTED=%s drifted from "
            "main.py's clamp %s" % (BOLD_EXPLORE_STUCK_S_ACCEPTED, bounds))
        assert window_text(BOLD_EXPLORE_STUCK_S_ACCEPTED) in PROMPT_TEMPLATE

    def test_command_windows_are_stated_in_the_prompt(self):
        for key in ("command.heading", "command.duration_s", "command.y"):
            assert window_text(COACH_NUMERIC_WINDOWS[key]) in PROMPT_TEMPLATE, (
                "the prompt does not state the accepted %s window — the model "
                "would guess and sanitize_strategy would silently clamp" % key)

    def test_escape_window_is_stated_and_not_misleading(self):
        assert window_text(ESCAPE_STUCK_THRESHOLD_S_ACCEPTED) in PROMPT_TEMPLATE
        # main.py does not clamp this key, so the prompt must not promise a
        # tighter window than the sanitizer floor accepts.
        assert ESCAPE_STUCK_THRESHOLD_S_ACCEPTED[0] >= 0.1

    def test_live_coach_values_are_flagged_and_the_effective_value_matches_clamp(self):
        """The values the live coach actually emitted vs what the brain uses."""
        report = acceptance_report(LIVE_STRATEGY,
                                   sanitize_strategy(LIVE_STRATEGY))
        oow = report["out_of_window"]
        assert set(oow) == {"exploration.turn_bias",
                            "exploration.bold_explore_stuck_s"}, (
            "the exact live form (0.8 / 20.0) must be reported as out of window")
        assert oow["exploration.turn_bias"]["effective"] == \
            _effective(0.8, _clamp_bounds("turn_bias")) == 0.25
        assert oow["exploration.bold_explore_stuck_s"]["effective"] == \
            _effective(20.0, _clamp_bounds("bold_explore_stuck_s")) == 10.0

    def test_the_brain_applies_exactly_these_bounds(self):
        """The bound table main.py applies is the one this module reports.

        P1-1 (t1) introduced ``CLAMP_BOUNDS`` + ``apply_strategy_clamps``; the
        clamp arithmetic there must stay ``max(lo, min(hi, requested))`` or the
        ``effective`` value in the acceptance record would be a lie.
        """
        for key, window in (("turn_bias", TURN_BIAS_ACCEPTED),
                            ("bold_explore_stuck_s",
                             BOLD_EXPLORE_STUCK_S_ACCEPTED)):
            assert _clamp_bounds(key) == window, (
                "main.py clamps %s to %s but llm_consult declares %s"
                % (key, _clamp_bounds(key), window))
        if "CLAMP_BOUNDS" in MAIN_SRC:
            assert re.search(r"clamped\s*=\s*max\(lo,\s*min\(hi,\s*requested\)\)",
                             MAIN_SRC), (
                "apply_strategy_clamps no longer computes max(lo, min(hi, x)) — "
                "the acceptance record's `effective` value is derived from it")

    def test_prompt_example_json_stays_inside_the_windows(self):
        """The template must not teach a value the brain clamps away.

        RED on the pre-P1-2 prompt: its example said
        ``"bold_explore_stuck_s": 60.0``, above main.py's 10 s ceiling.
        """
        strategy = _strategy_of(PROMPT_TEMPLATE)
        for section, body in strategy.items():
            if not isinstance(body, dict):
                continue
            for key, val in body.items():
                dotted = "%s.%s" % (section, key)
                window = COACH_NUMERIC_WINDOWS.get(dotted)
                if window is None or isinstance(val, bool) \
                        or not isinstance(val, (int, float)):
                    continue
                assert window[0] <= val <= window[1], (
                    "the prompt's example teaches %s=%s, outside the accepted "
                    "window %s" % (dotted, val, window))

    def test_no_wider_window_is_advertised_anywhere(self):
        """Every numeric range in the card is an accepted window (or the
        explicitly retracted legacy 0-1 scale)."""
        allowed = {window_text(w) for w in COACH_NUMERIC_WINDOWS.values()}
        pattern = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?![\d.])")
        for line in PROMPT_TEMPLATE.splitlines():
            for m in pattern.finditer(line):
                if m.group(0) in allowed:
                    continue
                assert "作废" in line or "失效" in line, (
                    "the prompt advertises the range %r on a line that does not "
                    "retract it: %s" % (m.group(0), line))

    def test_stale_wider_recommendations_are_gone(self):
        for stale in ("建议 20-120", "建议 0.3-1.0", "建议 1-60"):
            assert stale not in PROMPT_TEMPLATE, (
                "%r told the coach to emit values above the brain's clamp" % stale)

    def test_the_prompt_forbids_out_of_window_values(self):
        assert "必须落在" in PROMPT_TEMPLATE and "白调" in PROMPT_TEMPLATE, (
            "the card must tell the model not to emit values the brain refuses")

    def test_section_defaults_are_inside_the_accepted_windows(self):
        """A default above the clamp blames the coach for a value it never sent.

        ``sanitize_strategy`` writes the spec default whenever the model omits a
        key: with the old ``bold_explore_stuck_s`` default of 60.0 the pipeline
        recorded 60.0 and the brain applied 10.
        """
        drift = []
        for section, spec in SECTION_SPECS.items():
            for key, (_typ, default) in spec.items():
                window = COACH_NUMERIC_WINDOWS.get("%s.%s" % (section, key))
                if window is None or not isinstance(default, (int, float)) \
                        or isinstance(default, bool):
                    continue
                if not window[0] <= default <= window[1]:
                    drift.append("%s.%s default=%s window=%s"
                                 % (section, key, default, window))
        assert not drift, (
            "coach spec default(s) outside the accepted window — the model would "
            "be blamed for a value it never sent: %s" % drift)


# ── 2. command: direct control really lands ────────────────────────────────
class TestCommandDirectControlLands:
    def test_command_reaches_the_file_and_the_brain_reader(self, tmp_path):
        parsed = consult_with(tmp_path, LIVE_REPLY)
        payload = writer_for(tmp_path).write_strategy(
            parsed["strategy"], advice=parsed["advice"], source="stub")
        on_disk = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        assert on_disk["command"]["type"] == "turn_and_go"
        assert on_disk["command"]["heading"] == 45
        assert on_disk["command"]["duration_s"] == pytest.approx(2.5)
        assert on_disk["command"]["y"] == 70
        assert payload["command"]["type"] == "turn_and_go"

        # the brain's REAL reader (fly64.main.load_active_strategy) exposes it
        loaded = load_active_strategy(tmp_path / "active_strategy.json")
        assert loaded["command"]["type"] == "turn_and_go"
        assert loaded["command"]["heading"] == 45

    def test_brain_consumer_formula_turns_the_command_into_model_flags(self, tmp_path):
        """Re-derive the consumer's own arithmetic from main.py's source."""
        parsed = consult_with(tmp_path, LIVE_REPLY)
        writer_for(tmp_path).write_strategy(parsed["strategy"], advice="x")
        cmd = load_active_strategy(
            tmp_path / "active_strategy.json")["command"]

        assert '_cmd = dict(_active_strategy.get("command", {}) or {})' in MAIN_SRC
        assert 'if _cmd.get("type") == "turn_and_go":' in MAIN_SRC
        bias_expr = re.search(
            r"_bias = (max\(-1\.0, min\(1\.0, \(_heading - 180\) / 180\.0\)\))",
            MAIN_SRC)
        assert bias_expr, "main.py's command->flags conversion changed"
        heading = float(cmd.get("heading", 0))
        bias = eval(bias_expr.group(1), {"max": max, "min": min,
                                        "_heading": heading})
        # the four model flags the brain sets (main.py's coach command consumer)
        flags = {
            "coach_turn_bias": bias * 15.0,
            "coach_forward_bias": float(cmd.get("y", 50)),
            "coach_timer": int(float(cmd.get("duration_s", 2.0)) / (1 / 60)),
            "coach_active": True,
        }
        for line in ("model.coach_turn_bias = _bias * 15.0",
                     "model.coach_forward_bias = _y",
                     "model.coach_timer = int(_duration / model.dt)",
                     "model.coach_active = True"):
            assert line in MAIN_SRC, "consumer line missing: %s" % line
        assert flags["coach_turn_bias"] == pytest.approx(-11.25)   # (45-180)/180*15
        assert flags["coach_forward_bias"] == 70.0
        assert flags["coach_active"] is True
        assert flags["coach_timer"] == 150    # 2.5 s at 60 Hz

    def test_command_hoisted_out_of_strategy_is_recovered(self, tmp_path):
        """A sibling `command` (model deviation) must not be silently dropped."""
        reply = json.dumps({
            "advice": "转向",
            "command": {"type": "turn_and_go", "heading": 90, "duration_s": 2.0,
                        "y": 70},
            "strategy": {"exploration": {"turn_bias": 0.2}},
        }, ensure_ascii=False)
        parsed = consult_with(tmp_path, reply)
        assert parsed["strategy"]["command"]["type"] == "turn_and_go", (
            "the direct-control channel was dropped because the model put "
            "`command` next to `strategy` instead of inside it")
        writer_for(tmp_path).write_strategy(parsed["strategy"], advice="x")
        on_disk = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        assert on_disk["command"]["heading"] == 90

    def test_command_is_timestamped_for_the_telemetry_reader(self, tmp_path):
        """main.py reports coach_applied.command_ts — it needs a stamp."""
        parsed = consult_with(tmp_path, LIVE_REPLY)
        writer_for(tmp_path).write_strategy(parsed["strategy"], advice="x")
        on_disk = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        assert isinstance(on_disk["command"].get("ts"), (int, float)), (
            "an unstamped command makes main.py's command_ts telemetry empty")
        assert '"_command_ts"' in MAIN_SRC or '"command_ts"' in MAIN_SRC

    def test_command_survives_the_brain_clamp_selfheal(self, tmp_path):
        """The self-heal rewrites exploration only — the command must survive.

        P0-4 §四 suspected the clamp write-back was dropping the command
        section; it is not (live 45 s watch: the file is rewritten every ~600
        ticks while advice_ts and `command` stay unchanged).  This pins that.
        """
        parsed = consult_with(tmp_path, LIVE_REPLY)
        writer_for(tmp_path).write_strategy(parsed["strategy"], advice="x")
        path = tmp_path / "active_strategy.json"
        before = json.loads(path.read_text("utf-8"))

        # mirror main.py's self-heal: read the file, clamp exploration, rewrite
        raw = json.loads(path.read_text("utf-8"))
        expl = raw.setdefault("exploration", {})
        if "turn_bias" in expl:
            expl["turn_bias"] = _effective(expl["turn_bias"],
                                           _clamp_bounds("turn_bias"))
        if "bold_explore_stuck_s" in expl:
            expl["bold_explore_stuck_s"] = _effective(
                expl["bold_explore_stuck_s"],
                _clamp_bounds("bold_explore_stuck_s"))
        path.write_text(json.dumps(raw, indent=2), "utf-8")

        after = load_active_strategy(path)
        assert after["command"]["type"] == "turn_and_go"
        assert after["command"]["heading"] == before["command"]["heading"]
        assert after["command"]["ts"] == before["command"]["ts"]
        assert after["exploration"]["turn_bias"] == 0.25
        assert after["exploration"]["bold_explore_stuck_s"] == 10.0

    def test_malformed_command_fields_do_not_abort_the_consult(self, tmp_path):
        reply = json.dumps({
            "advice": "x",
            "strategy": {"command": {"type": "turn_and_go", "heading": 400,
                                     "duration_s": "2.5s", "y": "70u"}},
        }, ensure_ascii=False)
        parsed = consult_with(tmp_path, reply)
        cmd = parsed["strategy"]["command"]
        assert cmd["heading"] == 40            # 400 % 360
        assert "duration_s" not in cmd or isinstance(cmd["duration_s"], float)


# ── 3. requested vs accepted is recorded ───────────────────────────────────
class TestAcceptanceRecord:
    def test_report_pairs_requested_with_accepted(self, tmp_path):
        parsed = consult_with(tmp_path, LIVE_REPLY)
        report = parsed["coach_acceptance"]
        assert report["requested"]["exploration.turn_bias"] == 0.8
        assert report["accepted"]["exploration.turn_bias"] == 0.8
        assert report["out_of_window"]["exploration.turn_bias"]["effective"] == 0.25
        assert report["command"]["requested"]["heading"] == 45
        assert report["command"]["written"]["type"] == "turn_and_go"
        assert report["dropped"] == []

    def test_refused_dead_keys_are_listed(self, tmp_path):
        reply = json.dumps({
            "advice": "x",
            "strategy": {"escape": {"stuck_threshold_s": 5.0,
                                    "reverse_seconds": 0.5}},
        }, ensure_ascii=False)
        report = consult_with(tmp_path, reply)["coach_acceptance"]
        assert "escape.reverse_seconds" in report["dropped"]

    def test_acceptance_record_reaches_both_artifacts(self, tmp_path):
        parsed = consult_with(tmp_path, LIVE_REPLY)
        w = writer_for(tmp_path)
        strat = w.write_strategy(parsed["strategy"], advice=parsed["advice"])
        w.write_advice(parsed["advice"], context={}, strategy=parsed["strategy"])
        assert strat["coach_acceptance"]["out_of_window"], (
            "active_strategy.json must carry the requested-vs-accepted record")
        advice = json.loads((tmp_path / "coach_advice.json").read_text("utf-8"))
        assert advice["coach_acceptance"]["requested"]["exploration.turn_bias"] == 0.8
        assert advice["history"][-1]["coach_acceptance"]["out_of_window"]

    def test_runner_cycle_exposes_the_record_and_a_warning(self, tmp_path):
        """The resident service's cycle result (service_status.json) carries it."""
        mapping = {
            "/memory.json": {"stuck_duration": 70.0, "anomaly_state": "micro_loop",
                             "health_score": 0.5, "scene_name": "山坡"},
            "/help.json": {},
            "/flow.json": {},
            "/evolution.json": {},
        }
        consultant = GLMConsultant(
            transport="subagent", subagent_fn=lambda req: LIVE_REPLY,
            request_path=tmp_path / "req.json", response_path=tmp_path / "resp.json")
        runner = PluginRunner(dashboard_base="http://127.0.0.1:1", interval=10,
                              consultant=consultant, writer=writer_for(tmp_path),
                              fetcher=lambda ep: mapping.get(ep))
        out = runner.run_cycle()
        assert out["status"] == "ok" and out["consulted"]
        assert out["coach_acceptance"]["requested"]["exploration.turn_bias"] == 0.8
        warning = out["coach_acceptance_warning"]
        assert "exploration.turn_bias" in warning
        assert "effective 0.25" in warning
        # ... and the same line is derivable from the artifact on disk
        on_disk = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        assert runner.acceptance_warning(on_disk["coach_acceptance"]) == warning

    def test_no_warning_when_the_coach_stays_inside(self, tmp_path):
        reply = json.dumps({"advice": "x", "strategy": {
            "exploration": {"turn_bias": 0.2, "bold_explore_stuck_s": 5.0}}},
            ensure_ascii=False)
        report = consult_with(tmp_path, reply)["coach_acceptance"]
        assert report["out_of_window"] == {}
        assert PluginRunner.acceptance_warning(report) is None

    def test_resident_service_records_it_without_touching_service_py(self, tmp_path):
        """The production entry point is plugin.service — it must record too.

        The record rides inside ``strategy``, so the service's own write calls
        persist it without any change to service.py (which is outside P1-2's
        scope).
        """
        from plugin.service import ServiceRunner
        mapping = {
            "/memory.json": {"stuck_duration": 70.0, "anomaly_state": "micro_loop",
                             "health_score": 0.5, "scene_name": "山坡"},
            "/help.json": {}, "/flow.json": {}, "/evolution.json": {},
        }
        consultant = GLMConsultant(
            transport="subagent", subagent_fn=lambda req: LIVE_REPLY,
            request_path=tmp_path / "req.json",
            response_path=tmp_path / "resp.json")
        svc = ServiceRunner(dashboard_base="http://127.0.0.1:1", interval=10,
                            bridge_path=str(tmp_path / "no-bridge"),
                            consultant=consultant, writer=writer_for(tmp_path),
                            status_path=tmp_path / "service_status.json",
                            log=lambda *_: None)
        svc.runner._fetcher = lambda ep: mapping.get(ep)
        out = svc.run_cycle()
        assert out["status"] == "ok" and out["consulted"]
        strat = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        advice = json.loads((tmp_path / "coach_advice.json").read_text("utf-8"))
        assert strat["coach_acceptance"]["requested"]["exploration.turn_bias"] == 0.8
        assert advice["coach_acceptance"]["out_of_window"]["exploration.turn_bias"][
            "effective"] == 0.25
        assert strat["command"]["type"] == "turn_and_go"


# ── 4. the constants stay honest about their owner ─────────────────────────
class TestContractSourcesAreDocumented:
    def test_recording_is_documented_next_to_the_contract(self):
        for needle in ("COACH_NUMERIC_WINDOWS", "acceptance_report",
                       "TURN_BIAS_ACCEPTED", "BOLD_EXPLORE_STUCK_S_ACCEPTED"):
            assert needle in CONSULT_SRC
        # the constants must point at their owner, so a reader can re-verify
        assert "main.py: max(0.0, min(0.25, x))" in CONSULT_SRC
        assert "main.py: max(1, min(10, x))" in CONSULT_SRC

    def test_writer_documents_the_command_stamp(self):
        src = (ROOT / "plugin" / "strategy_writer.py").read_text("utf-8")
        assert "command_ts" in src, (
            "the writer must explain why it stamps command.ts")
        assert '"ts": cmd.get("ts") or round(time.time(), 2)' in src


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
