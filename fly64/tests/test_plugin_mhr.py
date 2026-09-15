#!/usr/bin/env python3
"""Tests for the fly64-mhr DSH dynamic plugin (fly64/plugin/).

Covers: plugin structure/manifest, the 10s skill cycle
(check_help_needed -> frame capture -> llm_consult -> strategy write),
LLM response parsing, strategy hot-reload writes, and the dashboard
coach_advice wiring.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from plugin import CYCLE_INTERVAL_SECONDS, PLUGIN_NAME, load_manifest  # noqa: E402
from plugin.llm_consult import (ConsultError, GLMConsultant,  # noqa: E402
                                build_consult_request, extract_json_text,
                                parse_response, sanitize_strategy)
from plugin.runner import PluginRunner  # noqa: E402
from plugin.strategy_writer import StrategyWriter  # noqa: E402


# ── plugin structure ────────────────────────────────────────────────────

class TestPluginStructure:
    def test_required_files_exist(self):
        for rel in ("plugin/__init__.py", "plugin/runner.py",
                    "plugin/llm_consult.py", "plugin/strategy_writer.py",
                    "plugin/manifest.json"):
            assert (PROJECT / rel).is_file(), rel

    def test_manifest_valid(self):
        m = load_manifest()
        assert m["name"] == PLUGIN_NAME
        assert m["entry"] == "plugin.runner:PluginRunner"
        assert m["runtime"]["interval_seconds"] == CYCLE_INTERVAL_SECONDS == 10
        assert m["llm"]["model"] == "glm-5.3-flash"
        assert "skills/active_strategy.json" in m["hot_reload_files"]

    def test_modules_parse(self):
        for rel in ("plugin/runner.py", "plugin/llm_consult.py",
                    "plugin/strategy_writer.py", "plugin/__init__.py"):
            ast.parse((PROJECT / rel).read_text(encoding="utf-8"))


# ── helpers ─────────────────────────────────────────────────────────────

MEM_STUCK = {
    "stuck_duration": 150.0, "reflex_active": False,
    "anomaly_state": "fallen", "health_score": 0.6,
    "scene_name": "室内 #ab12", "visited_cells": 10, "coverage_pct": 0.4,
}
MEM_OK = {"stuck_duration": 2.0, "reflex_active": False,
          "anomaly_state": "idle", "health_score": 1.0, "scene_name": "?"}


def make_fetcher(mapping):
    return lambda ep: mapping.get(ep)


def echo_consultant(tmp_path, reply=None):
    reply = reply or json.dumps({
        "scene_elements": ["墙", "金币"], "problem": "卡在墙角",
        "action": "向后退并右转", "advice": "倒退两秒后右转跳跃",
        "strategy": {"fallen_recovery": {"mode": "directional_climb",
                                         "climb_period": 3.0,
                                         "persist_seconds": 1.0},
                     "exploration": {"bold_explore_stuck_s": 45.0,
                                     "turn_bias": 30.0},
                     "escape": {"stuck_threshold_s": 20.0,
                                "reverse_seconds": 0.8}}})
    return GLMConsultant(
        transport="subagent", subagent_fn=lambda req: reply,
        request_path=tmp_path / "req.json", response_path=tmp_path / "resp.json")


def make_runner(tmp_path, mapping, reply=None):
    return PluginRunner(
        dashboard_base="http://127.0.0.1:1", interval=10,
        consultant=echo_consultant(tmp_path, reply),
        writer=StrategyWriter(strategy_path=tmp_path / "active_strategy.json",
                              advice_path=tmp_path / "coach_advice.json"),
        fetcher=make_fetcher(mapping))


GOOD_FRAME = "aGVsbG8="  # base64("hello")


# ── 10s cycle ───────────────────────────────────────────────────────────

class TestCycle:
    def test_full_cycle_writes_strategy_and_advice(self, tmp_path):
        mapping = {"/memory.json": MEM_STUCK, "/evolution.json": {},
                   "/flow.json": {}, "/help.json": {},
                   "/frame.json": {"frame_b64": GOOD_FRAME}}
        r = make_runner(tmp_path, mapping)
        out = r.run_cycle()
        assert out["status"] == "ok"
        assert out["consulted"] and out["strategy_written"]
        assert out["advice"] == "倒退两秒后右转跳跃"
        strat = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        assert strat["fallen_recovery"]["mode"] == "directional_climb"
        assert strat["coach_advice"] == "倒退两秒后右转跳跃"
        adv = json.loads((tmp_path / "coach_advice.json").read_text("utf-8"))
        assert adv["advice"] == "倒退两秒后右转跳跃"
        assert adv["history"][-1]["context"]["stuck_duration"] == 150.0

    def test_no_help_needed_skips_consult(self, tmp_path):
        mapping = {"/memory.json": MEM_OK, "/evolution.json": {},
                   "/flow.json": {}, "/help.json": {}}
        r = make_runner(tmp_path, mapping)
        out = r.run_cycle()
        assert out["status"] == "ok" and not out["consulted"]
        assert not (tmp_path / "active_strategy.json").exists()

    def test_help_json_trigger(self, tmp_path):
        help_snap = {"help_reason": "interaction_blocked",
                     "scene_name": "门", "position": {"x": 1.0},
                     "diagnosis": "habituated", "ts": 1.0}
        mapping = {"/memory.json": MEM_OK, "/evolution.json": {},
                   "/flow.json": {}, "/help.json": help_snap}
        r = make_runner(tmp_path, mapping)
        out = r.run_cycle()
        assert out["consulted"]
        assert out["context"]["help_reason"] == "interaction_blocked"

    def test_stuck_threshold_boundary(self, tmp_path):
        # t20: threshold lowered 120s -> 60s (coach intervenes earlier)
        mem = dict(MEM_OK, stuck_duration=59.0)
        r = make_runner(tmp_path, {"/memory.json": mem})
        assert r.check_help_needed({"memory": mem, "help": {}}) is None
        mem2 = dict(MEM_OK, stuck_duration=61.0, anomaly_state="micro_loop")
        ctx = r.check_help_needed({"memory": mem2, "help": {}})
        assert ctx and ctx["help_reason"] == "unsolvable_stuck"

    def test_stuck_help_threshold_60_contract(self, tmp_path):
        # t20 acceptance: 70s -> consult, 50s -> no consult, 70 <= old
        # 120s bound also triggers under the new threshold
        from plugin.runner import STUCK_HELP_THRESHOLD
        assert STUCK_HELP_THRESHOLD == 60.0
        r = make_runner(tmp_path, {})
        m70 = dict(MEM_OK, stuck_duration=70.0, anomaly_state="micro_loop")
        ctx = r.check_help_needed({"memory": m70, "help": {}})
        assert ctx and ctx["help_reason"] == "unsolvable_stuck"
        m50 = dict(MEM_OK, stuck_duration=50.0, anomaly_state="micro_loop")
        assert r.check_help_needed({"memory": m50, "help": {}}) is None
        m110 = dict(MEM_OK, stuck_duration=110.0, anomaly_state="micro_loop")
        ctx = r.check_help_needed({"memory": m110, "help": {}})
        assert ctx and ctx["help_reason"] == "unsolvable_stuck"

    def test_frame_captured_into_request(self, tmp_path):
        mapping = {"/memory.json": MEM_STUCK, "/evolution.json": {},
                   "/flow.json": {}, "/help.json": {},
                   "/frame.json": {"frame_b64": GOOD_FRAME}}
        r = make_runner(tmp_path, mapping)
        r.run_cycle()
        req = json.loads((tmp_path / "req.json").read_text("utf-8"))
        assert req["frame_b64"] == GOOD_FRAME
        assert req["image"].startswith("data:image/png;base64,")
        assert req["model"] == "glm-5.3-flash"

    def test_consult_failure_keeps_loop_alive(self, tmp_path):
        mapping = {"/memory.json": MEM_STUCK}
        calls = []

        def boom(req):
            calls.append(req)
            raise ConsultError("no subagent")

        c = GLMConsultant(transport="subagent", subagent_fn=boom,
                          request_path=tmp_path / "req.json",
                          response_path=tmp_path / "resp.json")
        r = PluginRunner(dashboard_base="x", consultant=c,
                         writer=StrategyWriter(
                             strategy_path=tmp_path / "s.json",
                             advice_path=tmp_path / "a.json"),
                         fetcher=make_fetcher(mapping))
        out = r.run_cycle()
        assert out["status"] == "consult_failed"
        assert r.last_error
        # loop continues
        out2 = r.run_cycle()
        assert len(calls) == 2 and out2["status"] == "consult_failed"

    def test_run_forever_interval(self, tmp_path, monkeypatch):
        sleeps = []
        monkeypatch.setattr("plugin.runner.time.sleep",
                            lambda s: sleeps.append(s))
        r = make_runner(tmp_path, {})
        r.run_forever(max_cycles=3)
        assert sleeps == [10, 10] and r.cycles == 3


# ── LLM response parsing ────────────────────────────────────────────────

class TestParseResponse:
    def test_plain_json(self):
        raw = '{"advice": "向左", "strategy": {"escape": {"stuck_threshold_s": 25}}}'
        out = parse_response(raw)
        assert out["advice"] == "向左"
        assert out["strategy"]["escape"]["stuck_threshold_s"] == 25.0

    def test_fenced_json(self):
        raw = "分析如下：\n```json\n{\"advice\": \"跳跃\", \"problem\": \"墙\"}\n```"
        out = parse_response(raw)
        assert out["advice"] == "跳跃"

    def test_prose_wrapped_json(self):
        raw = '好的，我的建议是 {"advice": "右转", "action": "turn right"} 请查收。'
        out = parse_response(raw)
        assert out["advice"] == "右转"

    def test_free_text_falls_back_to_advice(self):
        out = parse_response("马里奥应该向后退然后跳跃。")
        assert out["advice"] == "马里奥应该向后退然后跳跃。"

    def test_extract_json_text_prefers_fence(self):
        assert extract_json_text('x ```json {"a":1}``` y') == '{"a":1}'
        assert extract_json_text("") is None

    def test_sanitize_strategy(self):
        s = sanitize_strategy({
            "fallen_recovery": {"mode": "teleport", "climb_period": "abc",
                                "persist_seconds": -5},
            "unknown_section": {"x": 1},
            "escape": {"stuck_threshold_s": "20"}})
        assert s["fallen_recovery"]["mode"] == "mirror"
        assert s["fallen_recovery"]["climb_period"] == 2.0  # default fallback
        assert s["fallen_recovery"]["persist_seconds"] == 0.1  # clamped
        assert s["escape"]["stuck_threshold_s"] == 20.0
        assert "unknown_section" not in s


# ── strategy hot-reload ─────────────────────────────────────────────────

class TestStrategyWriter:
    def test_atomic_write_readable_by_brain_loader(self, tmp_path):
        w = StrategyWriter(strategy_path=tmp_path / "active_strategy.json",
                           advice_path=tmp_path / "coach_advice.json")
        w.write_strategy({"fallen_recovery": {"mode": "directional_climb",
                                              "climb_period": 3.5,
                                              "persist_seconds": 1.5}},
                         advice="test")
        # brain-side defensive loader must accept the plugin's output
        sys.path.insert(0, str(PROJECT))
        from fly64.main import load_active_strategy
        s = load_active_strategy(tmp_path / "active_strategy.json")
        assert s["mode"] == "directional_climb"
        assert s["climb_period"] == pytest.approx(3.5)

    def test_no_tmp_file_left_behind(self, tmp_path):
        w = StrategyWriter(strategy_path=tmp_path / "s.json",
                           advice_path=tmp_path / "a.json")
        w.write_strategy({"escape": {}}, advice="x")
        assert (tmp_path / "s.json").is_file()
        assert not (tmp_path / "s.json.tmp").exists()

    def test_advice_history_capped(self, tmp_path):
        w = StrategyWriter(strategy_path=tmp_path / "s.json",
                           advice_path=tmp_path / "a.json", history_limit=3)
        for i in range(5):
            w.write_advice(f"advice {i}")
        data = w.load_advice()
        assert len(data["history"]) == 3
        assert data["advice"] == "advice 4"
        assert data["history"][-1]["advice"] == "advice 4"


# ── dashboard wiring ────────────────────────────────────────────────────

class TestDashboardWiring:
    def test_coach_advice_endpoint_in_main(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        assert '"/coach_advice.json"' in src
        assert "coach_advice.json" in src

    def test_dashboard_js_renders_advice_and_history(self):
        src = (PROJECT / "web" / "dashboard.js").read_text(encoding="utf-8")
        assert "/coach_advice.json" in src
        assert "renderCoachAdvice" in src
        assert "coachAdviceText" in src
        assert "coachHistory" in src

    def test_index_html_has_coach_panel(self):
        src = (PROJECT / "web" / "index.html").read_text(encoding="utf-8")
        assert 'id="coachPanel"' in src
        assert 'id="coachAdviceText"' in src


# ── dialogue LLM decision (BRAIN 2.4.0 pause-wait mode) ────────────────

class TestDialogueDecision:
    def _dlg_consultant(self, tmp_path, reply, timeout=None):
        kw = dict(transport="subagent", subagent_fn=lambda req: reply,
                  request_path=tmp_path / "req.json",
                  response_path=tmp_path / "resp.json")
        if timeout is not None:
            kw["timeout"] = timeout
        return GLMConsultant(**kw)

    def test_parse_dialogue_response_actions(self):
        from plugin.llm_consult import parse_dialogue_response
        assert parse_dialogue_response(
            '{"action": "press_a", "reason": "推进对话"}') == {
                "action": "press_a", "reason": "推进对话"}
        out = parse_dialogue_response(
            '```json\n{"action": "press_b", "reason": "取消"}\n```')
        assert out["action"] == "press_b"
        # unknown / missing / malformed actions degrade to none
        assert parse_dialogue_response('{"action": "dance"}')["action"] == "none"
        assert parse_dialogue_response('{"reason": "x"}')["action"] == "none"
        assert parse_dialogue_response("乱说一通")["action"] == "none"
        # free text preserved as reason
        assert parse_dialogue_response("等一下")["reason"] == "等一下"

    def test_consult_dialogue_returns_decision(self, tmp_path):
        c = self._dlg_consultant(tmp_path,
                                 '{"action": "press_a", "reason": "按A推进"}')
        out = c.consult_dialogue(GOOD_FRAME)
        assert out == {"action": "press_a", "reason": "按A推进"}
        req = json.loads((tmp_path / "req.json").read_text("utf-8"))
        assert req["frame_b64"] == GOOD_FRAME
        assert req["kind"] == "dialogue_decision"
        assert "press_a|press_b|none" in req["prompt"]

    def test_consult_dialogue_module_level(self, tmp_path):
        import plugin.llm_consult as mod
        c = self._dlg_consultant(tmp_path,
                                 '{"action": "none", "reason": "等待"}')
        old = mod._default_consultant
        mod._default_consultant = c
        try:
            assert mod.consult_dialogue(GOOD_FRAME)["action"] == "none"
        finally:
            mod._default_consultant = old

    def test_consult_dialogue_timeout_restored(self, tmp_path):
        c = self._dlg_consultant(tmp_path, '{"action": "press_b"}',
                                 timeout=5.0)
        c.consult_dialogue(GOOD_FRAME, timeout=120.0)
        assert c.timeout == 5.0  # caller budget restored after the call

    def test_write_dialogue_decision_merges_into_strategy(self, tmp_path):
        w = StrategyWriter(strategy_path=tmp_path / "active_strategy.json",
                           advice_path=tmp_path / "coach_advice.json")
        w.write_strategy({"fallen_recovery": {"mode": "directional_climb"}},
                         advice="keep me")
        w.write_dialogue_decision("press_a", "推进对话",
                                  wait_seconds=12.3)
        data = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        d = data["dialogue_decision"]
        assert d["action"] == "press_a" and d["reason"] == "推进对话"
        assert d["wait_seconds"] == 12.3 and d["timed_out"] is False
        # existing strategy section preserved
        assert data["fallen_recovery"]["mode"] == "directional_climb"
        assert data["coach_advice"] == "keep me"
        w.write_dialogue_decision("press_a", "超时回退", timed_out=True)
        data = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        assert data["dialogue_decision"]["timed_out"] is True

    def test_main_dialogue_pause_wait_wiring(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        assert 'DIALOGUE_LLM_WAIT_S = 600.0' in src
        assert "consult_dialogue" in src
        assert "write_dialogue_decision" in src
        assert "llm_decision" in src          # telemetry + control branch
        assert "autonomous" in src            # timeout fallback
        # BRAIN_VERSION introduced the dialogue pause-wait mode at 2.4.0
        # and only moves forward — pin semantics, not the exact number.
        import re as _re
        _m = _re.search(r'BRAIN_VERSION = "(\d+)\.(\d+)\.(\d+)"', src)
        assert _m and [int(g) for g in _m.groups()] >= [2, 4, 0]
        bridge_src = (PROJECT / "fly64" / "bridge.py").read_text("utf-8")
        assert "B_BUTTON" in bridge_src       # press_b transport
        web_src = (PROJECT / "web" / "dashboard.js").read_text("utf-8")
        assert "renderLlmDecision" in web_src
        html_src = (PROJECT / "web" / "index.html").read_text("utf-8")
        assert 'id="llmDecisionPill"' in html_src


# ── t13: coach-advice effectiveness (dead key, trigger, prompt, 400) ───

class TestCoachAdviceEffectiveness:
    def test_png_conversion_of_raw_frame(self):
        import base64 as b64mod
        import numpy as np
        from plugin.llm_consult import raw_rgb_b64_to_png_b64
        h, w = 256, 384
        raw = np.zeros((h, w, 3), np.uint8)
        raw[0, 0] = (255, 0, 0)
        out = raw_rgb_b64_to_png_b64(b64mod.b64encode(raw.tobytes()).decode())
        assert b64mod.b64decode(out)[:8] == b"\x89PNG\r\n\x1a\n"
        assert b64mod.b64decode(out)[-8:-4] == b"IEND"

    def test_png_passthrough_for_non_raw_payload(self):
        from plugin.llm_consult import raw_rgb_b64_to_png_b64
        assert raw_rgb_b64_to_png_b64(GOOD_FRAME) == GOOD_FRAME

    def test_build_request_converts_frame_to_png(self):
        import base64 as b64mod
        import numpy as np
        from plugin.llm_consult import build_consult_request
        raw = np.zeros((256, 384, 3), np.uint8)
        req = build_consult_request({}, b64mod.b64encode(raw.tobytes()).decode())
        assert b64mod.b64decode(req["frame_b64"])[:4] == b"\x89PNG"
        assert req["image"].startswith("data:image/png;base64,")

    def test_prompt_has_semantic_card(self):
        from plugin.llm_consult import DIALOGUE_PROMPT_TEMPLATE, PROMPT_TEMPLATE
        for key in ("bold_explore_stuck_s", "turn_bias", "stuck_threshold_s"):
            assert key in PROMPT_TEMPLATE
        assert "秒" in PROMPT_TEMPLATE and "0-1" in PROMPT_TEMPLATE
        assert "不要反向调参" in PROMPT_TEMPLATE
        # dialogue prompt untouched by the card
        assert "策略参数" not in DIALOGUE_PROMPT_TEMPLATE

    def test_bold_turn_bias_consumed_with_unit_clamp(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        assert 'getattr(memory_ctrl, "bold_turn_bias"' in src
        assert "max(0.2, min(1.0" in src          # clamp, 0 cannot dead-throttle
        assert "* _mag" in src                    # amplitude reaches the drive
        model_src = (PROJECT / "fly64" / "model.py").read_text("utf-8")
        assert "self.bold_turn_drive" in model_src

    def test_bold_explore_trigger_relaxed_to_any_anomaly(self):
        mem_src = (PROJECT / "fly64" / "memory.py").read_text("utf-8")
        assert "persistent_anomaly_stuck" in mem_src
        assert "micro_loop_stuck" in mem_src      # original path kept
        assert 'self._latest_anomaly_state != "micro_loop"' in mem_src


# ── t21: explicit screen-text readout (what_i_see) ──────────────────────

class TestWhatISee:
    def test_prompt_includes_screen_text_instruction(self):
        from plugin.llm_consult import PROMPT_TEMPLATE
        assert "特别注意屏幕上的文字" in PROMPT_TEMPLATE
        assert "what_i_see" in PROMPT_TEMPLATE
        assert "屏幕看到的" in PROMPT_TEMPLATE

    def test_parse_response_keeps_what_i_see(self):
        from plugin.llm_consult import parse_response
        raw = ('{"what_i_see": ["POWER STARS", "x 3", "生命值 4"], '
               '"advice": "向前", "strategy": {}}')
        out = parse_response(raw)
        assert out["what_i_see"] == ["POWER STARS", "x 3", "生命值 4"]
        assert out["advice"] == "向前"

    def test_parse_response_missing_degrades_to_empty(self):
        from plugin.llm_consult import parse_response
        assert parse_response('{"advice": "x"}')["what_i_see"] == []
        assert parse_response("纯文本无 JSON")["what_i_see"] == []
        # malformed variants don't crash
        assert parse_response('{"what_i_see": 42, "advice": "y"}')["what_i_see"] == []
        out = parse_response('{"what_i_see": "单条文本", "advice": "z"}')
        assert out["what_i_see"] == ["单条文本"]

    def test_sanitize_strategy_preserves_what_i_see(self):
        from plugin.llm_consult import sanitize_strategy
        s = sanitize_strategy({"exploration": {"turn_bias": 0.5},
                               "what_i_see": ["COURSE 1", "⭐ x2"]})
        assert s["what_i_see"] == ["COURSE 1", "⭐ x2"]
        assert "what_i_see" not in sanitize_strategy({"exploration": {}})

    def test_consult_embeds_what_i_see_in_advice(self, tmp_path):
        reply = json.dumps({"what_i_see": ["STAR x 3"], "advice": "跳",
                            "strategy": {"exploration": {"turn_bias": 0.5}}})
        c = echo_consultant(tmp_path, reply)
        out = c.consult({}, GOOD_FRAME)
        assert "👁 屏幕: STAR x 3" in out["advice"]
        assert out["what_i_see"] == ["STAR x 3"]
        assert out["strategy"]["what_i_see"] == ["STAR x 3"]  # survives sanitize

    def test_writer_persists_what_i_see(self, tmp_path):
        w = StrategyWriter(strategy_path=tmp_path / "active_strategy.json",
                           advice_path=tmp_path / "coach_advice.json")
        w.write_strategy({"exploration": {}}, advice="a",
                         what_i_see=["HELLO"])
        w.write_advice("a", what_i_see=["HELLO"])
        strat = json.loads((tmp_path / "active_strategy.json").read_text("utf-8"))
        adv = json.loads((tmp_path / "coach_advice.json").read_text("utf-8"))
        assert strat["what_i_see"] == ["HELLO"]
        assert adv["what_i_see"] == ["HELLO"]
        assert adv["history"][-1]["what_i_see"] == ["HELLO"]


# ── t21 wrap-up: consult frame snapshots ────────────────────────────────

class TestConsultFrameSnapshot:
    def test_save_writes_png_with_expected_name(self, tmp_path):
        import base64 as b64mod
        import numpy as np
        from plugin.runner import PluginRunner
        raw = np.zeros((256, 384, 3), np.uint8)
        fb64 = b64mod.b64encode(raw.tobytes()).decode()
        out = PluginRunner.save_consult_frame(
            fb64, "unsolvable_stuck", ts=1700000000.5,
            frame_dir=tmp_path / "coach_frames")
        p = tmp_path / "coach_frames" / "coach_1700000000.5_unsolvable_stuck.png"
        assert out == str(p) and p.is_file()
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_reason_sanitised_and_default(self, tmp_path):
        import base64 as b64mod
        import numpy as np
        from plugin.runner import PluginRunner
        raw = np.zeros((256, 384, 3), np.uint8)
        fb64 = b64mod.b64encode(raw.tobytes()).decode()
        out = PluginRunner.save_consult_frame(fb64, "weird/reason 双语!",
                                              ts=1.0, frame_dir=tmp_path)
        assert "coach_1.0_weird_reason_双语.png" in out

    def test_none_frame_returns_none(self, tmp_path):
        from plugin.runner import PluginRunner
        assert PluginRunner.save_consult_frame(None, frame_dir=tmp_path) is None

    def test_run_cycle_invokes_snapshot(self, tmp_path):
        # source-level: run_cycle feeds capture_frame output to the saver
        src = (PROJECT / "plugin" / "runner.py").read_text(encoding="utf-8")
        assert "self.save_consult_frame(frame_b64, context.get(\"help_reason\"))" in src
