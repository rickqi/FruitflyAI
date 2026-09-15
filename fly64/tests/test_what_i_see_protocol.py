#!/usr/bin/env python3
"""Tests for the what_i_see protocol (t21+ / Brain 2.14.x).

Covers:
- SceneContext assembly from flow/memory snapshots
- Scene tag generation rules
- Enhanced prompt embedding
- semantic_level parsing
- Frame delta tracking
- Backward compatibility with existing parse_response
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# Try plugin imports (package-relative) then direct
try:
    from plugin.scene_context import (
        SceneContext, FlyVision, TerrainScores, OpticFlowSummary,
        NavigationState, MotorState, PlasticityState,
        assemble_scene_context, generate_scene_tags,
        build_scene_context_summary,
    )
    from plugin.llm_consult import (
        parse_response, sanitize_strategy, normalize_what_i_see,
        ENHANCED_PROMPT_TEMPLATE, build_consult_request,
    )
    from plugin.strategy_writer import StrategyWriter
    SCENE_CONTEXT_OK = True
except ImportError:
    SCENE_CONTEXT_OK = False

import pytest


# ── sample dashboard snapshots ────────────────────────────────────────

SAMPLE_FLOW = {
    "asymmetry": -0.4849,
    "true_asymmetry": -0.0849,
    "heading_rate": 5.0,
    "looming": 0.1234,
    "cliff": 0.0123,
    "cliff_detected": False,
    "cliff_confidence": 0.0,
    "tau": 2.34,
    "terrain": "indoor",
    "wall_score": 0.32,
    "ramp_score": 0.12,
    "sky_score": 0.05,
    "enclosure_score": 0.85,
    "ground_angle": 0.02,
    "door_frame_score": 0.41,
    "opening_score": 0.62,
    "opening_width": 0.74,
    "scene_name": "迷宫室内 #f3f9",
    "scene_hash": "f3f9aa",
    "scene_match": 0.87,
    "target_count": 1,
    "target_tracks": [{"azimuth": -15, "elevation": 5, "age": 1.2}],
    "hrc_asymmetry": -0.0512,
    "local_motion": 0.23,
    "local_motion_detected": True,
    "gate_forward": True,
    "gate_jump": False,
    "decision_source": "steering",
    "mb_mbon_forward": 0.95,
    "mb_dopamine": -0.12,
    "dopamine_gain_avg": 1.25,
    "learning_progress": 0.34,
    "mushroom_weight_changes": 12,
    "dialogue_active": False,
    "tick": 12345,
}

SAMPLE_MEM = {
    "stuck_duration": 62.0,
    "anomaly_state": "micro_loop",
    "anomaly_confidence": 0.85,
    "anomaly_duration": 15.3,
    "health_score": 0.72,
    "coverage_pct": 34.2,
    "disp_60s": 12.5,
    "revisit_count": 3,
    "scene_label": "迷宫室内 #f3f9",
    "scene_id": "f3f9aa",
    "heading": 45.0,
    "heading_rate": 5.2,
    "forward_rate": 12.5,
    "turn_bias": -0.3,
    "jump_rate": 0.5,
    "reflex_active": True,
}


# ── SceneContext assembly ──────────────────────────────────────────────

@pytest.mark.skipif(not SCENE_CONTEXT_OK, reason="scene_context module not importable")
class TestSceneContextAssembly:
    def test_assemble_basic(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        assert isinstance(ctx, SceneContext)
        assert ctx.fly_vision.terrain == "indoor"
        assert ctx.fly_vision.terrain_scores.enclosure_score == 0.85
        assert ctx.fly_vision.optic_flow.asymmetry == -0.4849
        assert ctx.fly_vision.scene_context.revisit_count == 3

    def test_navigation_state(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        assert ctx.navigation.stuck_duration == 62.0
        assert ctx.navigation.anomaly_state == "micro_loop"
        assert ctx.navigation.disp_60s == 12.5

    def test_motor_state(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        assert ctx.motor_state.decision_source == "steering"
        assert ctx.motor_state.gate_forward is True

    def test_plasticity_present(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        assert ctx.plasticity is not None
        assert ctx.plasticity.mb_mbon_forward == 0.95
        assert ctx.plasticity.mb_dopamine == -0.12

    def test_plasticity_absent_when_no_data(self):
        flow_no_plasticity = {k: v for k, v in SAMPLE_FLOW.items()
                              if k not in ("mb_mbon_forward", "mb_dopamine",
                                           "dopamine_gain_avg", "learning_progress",
                                           "mushroom_weight_changes")}
        ctx = assemble_scene_context(flow_no_plasticity, SAMPLE_MEM)
        assert ctx.plasticity is None

    def test_target_tracks(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        assert ctx.fly_vision.targets.count == 1
        assert len(ctx.fly_vision.targets.tracks) == 1


# ── scene tag generation ───────────────────────────────────────────────

@pytest.mark.skipif(not SCENE_CONTEXT_OK, reason="scene_context module not importable")
class TestSceneTags:
    def test_indoor_enclosure(self):
        tags = generate_scene_tags(SAMPLE_FLOW, SAMPLE_MEM)
        assert any("室内场景" in t for t in tags)

    def test_door_frame(self):
        tags = generate_scene_tags(SAMPLE_FLOW, SAMPLE_MEM)
        assert any("门框" in t for t in tags)

    def test_anomaly_tag(self):
        tags = generate_scene_tags(SAMPLE_FLOW, SAMPLE_MEM)
        assert any("微循环编织" in t for t in tags)

    def test_revisit_tag(self):
        tags = generate_scene_tags(SAMPLE_FLOW, SAMPLE_MEM)
        assert any("重复回访" in t for t in tags)

    def test_target_tag(self):
        tags = generate_scene_tags(SAMPLE_FLOW, SAMPLE_MEM)
        assert any("移动目标" in t for t in tags)

    def test_empty_when_no_triggers(self):
        flow_flat = {"terrain": "open_flat", "wall_score": 0.0, "ramp_score": 0.0,
                     "sky_score": 0.0, "enclosure_score": 0.0, "ground_angle": 0.0,
                     "door_frame_score": 0.0, "opening_score": 0.0,
                     "looming": 0.0, "cliff": 0.0, "target_count": 0,
                     "dialogue_active": False, "cliff_detected": False}
        mem_idle = {"stuck_duration": 5.0, "anomaly_state": "idle", "revisit_count": 0}
        tags = generate_scene_tags(flow_flat, mem_idle)
        assert len(tags) == 0

    def test_enclosure_score_appended(self):
        tags = generate_scene_tags(SAMPLE_FLOW, SAMPLE_MEM)
        # "室内场景" should be generated from enclosure_score >= 0.65
        assert any("室内场景" in t for t in tags)


# ── prompt summary builder ─────────────────────────────────────────────

@pytest.mark.skipif(not SCENE_CONTEXT_OK, reason="scene_context module not importable")
class TestPromptSummary:
    def test_summary_contains_key_fields(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        summary = build_scene_context_summary(ctx)
        assert "indoor" in summary
        assert "micro_loop" in summary
        assert "62s" in summary or "62.0" in summary
        assert "0.85" in summary  # enclosure_score

    def test_summary_with_targets(self):
        summary = build_scene_context_summary(
            assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM))
        assert "活跃目标" in summary

    def test_summary_with_plasticity(self):
        summary = build_scene_context_summary(
            assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM))
        assert "MBON" in summary

    def test_summary_no_plasticity(self):
        flow_no_plast = {k: v for k, v in SAMPLE_FLOW.items()
                         if "mb_" not in k and "dopamine" not in k
                         and "learning" not in k and "mushroom" not in k}
        ctx = assemble_scene_context(flow_no_plast, SAMPLE_MEM)
        summary = build_scene_context_summary(ctx)
        assert "MBON" not in summary


# ── frame delta tracking ───────────────────────────────────────────────

@pytest.mark.skipif(not SCENE_CONTEXT_OK, reason="scene_context module not importable")
class TestFrameDelta:
    def test_worsening_stuck(self):
        prev = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        mem_worse = dict(SAMPLE_MEM, stuck_duration=80.0)
        ctx = assemble_scene_context(SAMPLE_FLOW, mem_worse, prev_context=prev)
        assert ctx.frame_delta is not None
        assert ctx.frame_delta.stuck_trend == "worsening"

    def test_stable_stuck(self):
        prev = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM, prev_context=prev)
        assert ctx.frame_delta is not None
        assert ctx.frame_delta.stuck_trend == "stable"

    def test_no_delta_when_no_prev(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM)
        assert ctx.frame_delta is None


# ── semantic_level parsing ─────────────────────────────────────────────

class TestSemanticLevel:
    def test_semantic_level_innate_parsed(self):
        raw = json.dumps({"semantic_level": "innate", "advice": "调参即可",
                           "what_i_see": ["COIN x3"]}, ensure_ascii=False)
        result = parse_response(raw)
        assert result["semantic_level"] == "innate"

    def test_semantic_level_coach_parsed(self):
        raw = json.dumps({"semantic_level": "coach", "advice": "需要钥匙",
                           "what_i_see": ["You need a key"]}, ensure_ascii=False)
        result = parse_response(raw)
        assert result["semantic_level"] == "coach"

    def test_semantic_level_invalid_defaults(self):
        raw = json.dumps({"semantic_level": "invalid_thing", "advice": "x",
                           "what_i_see": []}, ensure_ascii=False)
        result = parse_response(raw)
        assert result["semantic_level"] == ""

    def test_semantic_level_missing_defaults(self):
        raw = json.dumps({"advice": "x", "what_i_see": []}, ensure_ascii=False)
        result = parse_response(raw)
        assert result["semantic_level"] == ""

    def test_semantic_level_non_string_defaults(self):
        raw = json.dumps({"semantic_level": 42, "advice": "x"}, ensure_ascii=False)
        result = parse_response(raw)
        assert result["semantic_level"] == ""


# ── backward compatibility ────────────────────────────────────────────

class TestBackwardCompatibility:
    """All existing t21 tests must still pass unchanged."""

    def test_prompt_has_what_i_see_instruction(self):
        from plugin.llm_consult import PROMPT_TEMPLATE
        assert "what_i_see" in PROMPT_TEMPLATE

    def test_parse_response_keeps_what_i_see(self):
        raw = ('{"what_i_see": ["POWER STARS", "x 3", "生命值 4"], '
               '"advice": "去平台"}')
        out = parse_response(raw)
        assert out["what_i_see"] == ["POWER STARS", "x 3", "生命值 4"]

    def test_parse_response_defaults_empty(self):
        assert parse_response('{"advice": "x"}')["what_i_see"] == []
        assert parse_response("纯文本无 JSON")["what_i_see"] == []

    def test_parse_response_normalizes_non_list(self):
        assert parse_response('{"what_i_see": 42, "advice": "y"}')["what_i_see"] == []
        out = parse_response('{"what_i_see": "单条文本", "advice": "z"}')
        assert out["what_i_see"] == ["单条文本"]

    def test_sanitize_strategy_preserves_what_i_see(self):
        s = sanitize_strategy({"exploration": {"bold_explore_stuck_s": 60.0},
                               "what_i_see": ["COURSE 1", "⭐ x2"]})
        assert s["what_i_see"] == ["COURSE 1", "⭐ x2"]
        assert "what_i_see" not in sanitize_strategy({"exploration": {}})

    def test_normalize_what_i_see(self):
        assert normalize_what_i_see(None) == []
        assert normalize_what_i_see("hello") == ["hello"]
        assert normalize_what_i_see(["a", "b"]) == ["a", "b"]
        assert normalize_what_i_see(["a", "", "c"]) == ["a", "c"]
        assert normalize_what_i_see(42) == []


# ── enhanced prompt ────────────────────────────────────────────────────

class TestEnhancedPrompt:
    def test_enhanced_prompt_has_scene_context_placeholder(self):
        assert "{scene_context_summary}" in ENHANCED_PROMPT_TEMPLATE

    def test_enhanced_prompt_has_semantic_level(self):
        assert "semantic_level" in ENHANCED_PROMPT_TEMPLATE

    def test_enhanced_prompt_has_innate_coach(self):
        assert "innate" in ENHANCED_PROMPT_TEMPLATE
        assert "coach" in ENHANCED_PROMPT_TEMPLATE

    def test_build_request_with_scene_context(self):
        req = build_consult_request(
            context={"scene_name": "test"},
            frame_b64=None,
            scene_context_summary="地形: open_flat\n异常态: idle",
        )
        assert req.get("scene_context_summary") == "地形: open_flat\n异常态: idle"
        # Should use enhanced prompt
        assert "果蝇实际感知摘要" in req["prompt"]

    def test_build_request_without_scene_context(self):
        req = build_consult_request(
            context={"scene_name": "test"},
            frame_b64=None,
        )
        assert "scene_context_summary" not in req
        # Should use default PROMPT_TEMPLATE
        assert "果蝇脑控制系统的教练" in req["prompt"]


# ── consulation history tracking ───────────────────────────────────────

@pytest.mark.skipif(not SCENE_CONTEXT_OK, reason="scene_context module not importable")
class TestConsultHistory:
    def test_history_same_scene_count(self):
        advice = {
            "advice": "向左转",
            "strategy": {"exploration": {"turn_bias": 0.6}},
            "history": [
                {"context": {"scene_name": "迷宫室内 #f3f9"}, "advice": "跳"},
                {"context": {"scene_name": "迷宫室内 #f3f9"}, "advice": "右转"},
                {"context": {"scene_name": "草地 #a1b2"}, "advice": "直行"},
            ]
        }
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM,
                                     consult_history=advice)
        assert ctx.consult_history.same_scene_consults == 2
        assert ctx.consult_history.last_advice == "向左转"

    def test_history_no_previously(self):
        ctx = assemble_scene_context(SAMPLE_FLOW, SAMPLE_MEM,
                                     consult_history={})
        assert ctx.consult_history.same_scene_consults == 0
        assert ctx.consult_history.last_advice == ""


# ── scene context injection into consult method ────────────────────────

class TestSceneTagsPersistence:
    def test_write_advice_persists_scene_tags(self, tmp_path):
        from plugin.strategy_writer import StrategyWriter
        w = StrategyWriter(strategy_path=tmp_path / "strategy.json",
                           advice_path=tmp_path / "advice.json",
                           history_limit=5)
        w.write_advice("向左转", scene_tags=["室内场景", "有门框"])
        loaded = json.loads((tmp_path / "advice.json").read_text(encoding="utf-8"))
        assert loaded.get("scene_tags") == ["室内场景", "有门框"]
        assert loaded["history"][-1].get("scene_tags") == ["室内场景", "有门框"]

    def test_write_strategy_does_not_persist_scene_tags(self, tmp_path):
        """Semantic tags must NOT descend into active_strategy.json."""
        from plugin.strategy_writer import StrategyWriter
        w = StrategyWriter(strategy_path=tmp_path / "strategy.json",
                           advice_path=tmp_path / "advice.json")
        w.write_strategy({"fallen_recovery": {"mode": "mirror"}},
                         advice="向左转",
                         scene_tags=["室内场景"])
        loaded = json.loads((tmp_path / "strategy.json").read_text(encoding="utf-8"))
        assert "scene_tags" not in loaded
        assert loaded.get("fallen_recovery", {}).get("mode") == "mirror"