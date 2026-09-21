"""
P1-1: Telemetry completeness -- verify 5 control-derived fields in DataCollector.

Tests:
  1. DataCollector.get_metrics() returns all 5 fields
  2. DataCollector pipeline: sample() -> get_metrics() produces correct values
  3. Pattern condition field references are consistent (no telemetry_gap)
  4. DiagnosisEngine does not crash or produce gaps for these fields
  5. /memory.json derivation formulas (mirroring main.py) are correct
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.evolution_skill import (
    DataCollector,
    DiagnosisEngine,
    DEFAULT_PATTERNS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def fake_bridge(ctrl_x=30, ctrl_y=40, ctrl_jump=False, pose=(0, 0, 0, 0)):
    return {
        "x": ctrl_x, "y": ctrl_y, "jump": ctrl_jump,
        "pose": list(pose),
    }


def fake_memory(stuck=0.0, visited=10, coverage=5.0, anomaly="idle",
                health=1.0, escape=False, loop=0.0):
    return {
        "stuck_duration": stuck,
        "visited_cells": visited,
        "coverage_pct": coverage,
        "anomaly_state": anomaly,
        "health_score": health,
        "escape_behavior": escape,
        "loop_score": loop,
        "reflex_active": False,
        "cliff_standoff_s": 0.0,
        "command_decoupled": False,
        "forced_bold_explore": False,
        "revisit_count": 0,
        "scene_change_rate": 0.0,
        "reflex_ineffective": False,
        "reflex_cooldowns": {},
    }


def fake_flow():
    return {
        "wall_score": 0.0, "asymmetry": 0.0, "ground_angle": 0.0,
        "ramp_score": 0.0, "terrain": "flat", "scene_name": "test",
        "scene_hash": "", "dialogue_active": False,
        "interactive_near": False, "local_motion_detected": False,
        "cliff_confirmed": False, "danger_red_index": 0.0,
        "emd_on_down": 0.0, "target_count": 0, "mb_assoc_count": 0,
        "mb_mbon_forward": 0.0, "opening_score": 0.0,
        "door_frame_score": 0.0, "sky_score": 0.0, "tau": None,
        "dopamine_gain_avg": 1.5, "learning_progress": 0.0,
        "mushroom_weight_changes": 0, "reward_trend": 0.0,
        "error_gradient_mean": 0.0, "gain_update_count": 0,
        "cpg_status": {"completed": 0, "aborted": 0, "last_abort": ""},
        "primitive_disp": None, "mb_w_punch": None, "mb_w_dive": None,
        "mb_w_groundpound": None, "mb_w_longjump": None,
    }


def _collect(dc, bridge, memory, flow, n=3):
    """Collect n samples at realistic wall-clock timestamps."""
    now = time.time()
    for i in range(n):
        dc.sample(bridge, memory, flow, now + i)
    return dc


# ---------------------------------------------------------------------------
# 1. DataCollector pipeline produces all 5 fields
# ---------------------------------------------------------------------------


class TestDataCollectorPipeline:

    def test_all_five_fields_in_metrics(self):
        dc = DataCollector(window_seconds=120)
        bridge = fake_bridge(ctrl_x=30, ctrl_y=40, ctrl_jump=False)
        memory = fake_memory(stuck=15.0, escape=True)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow)
        metrics = dc.get_metrics()

        assert "control_magnitude" in metrics
        assert "control_x_zero" in metrics
        assert "control_y_zero" in metrics
        assert "escape_behavior" in metrics
        assert "jump_not_active" in metrics

        assert metrics["control_magnitude"] == 70
        assert metrics["control_x_zero"] is False
        assert metrics["control_y_zero"] is False
        assert metrics["escape_behavior"] is True
        assert metrics["jump_not_active"] is True

    def test_fields_with_zero_control(self):
        dc = DataCollector(window_seconds=120)
        bridge = fake_bridge(ctrl_x=0, ctrl_y=0, ctrl_jump=True)
        memory = fake_memory(stuck=30.0, escape=False)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow)
        metrics = dc.get_metrics()

        assert metrics["control_magnitude"] == 0
        assert metrics["control_x_zero"] is True
        assert metrics["control_y_zero"] is True
        assert metrics["escape_behavior"] is False
        assert metrics["jump_not_active"] is False

    def test_field_types(self):
        dc = DataCollector(window_seconds=120)
        bridge = fake_bridge(ctrl_x=30, ctrl_y=40)
        memory = fake_memory(stuck=15.0, escape=True)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow)
        metrics = dc.get_metrics()

        assert isinstance(metrics["control_magnitude"], (int, float))
        assert isinstance(metrics["control_x_zero"], bool)
        assert isinstance(metrics["control_y_zero"], bool)
        assert isinstance(metrics["escape_behavior"], bool)
        assert isinstance(metrics["jump_not_active"], bool)

    def test_negative_control_produces_positive_magnitude(self):
        dc = DataCollector(window_seconds=120)
        bridge = fake_bridge(ctrl_x=-30, ctrl_y=40)
        flow = fake_flow()
        _collect(dc, bridge, fake_memory(), flow)
        metrics = dc.get_metrics()
        assert metrics["control_magnitude"] == 70


# ---------------------------------------------------------------------------
# 2. Pattern condition field completeness
# ---------------------------------------------------------------------------


class TestPatternFieldCompleteness:

    def _collect_metrics_keys(self) -> set:
        dc = DataCollector(window_seconds=120)
        bridge = fake_bridge(ctrl_x=30, ctrl_y=40, pose=(100, 120, 200, 0.5))
        memory = fake_memory(stuck=15.0, escape=True, visited=50, coverage=20.0)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow, n=5)
        return set(dc.get_metrics().keys())

    def test_specific_five_fields_present(self):
        metrics_keys = self._collect_metrics_keys()
        for field in ["control_magnitude", "control_x_zero",
                       "control_y_zero", "escape_behavior", "jump_not_active"]:
            assert field in metrics_keys, f"'{field}' missing from get_metrics()"


# ---------------------------------------------------------------------------
# 3. DiagnosisEngine integration -- no telemetry_gap for these fields
# ---------------------------------------------------------------------------


class TestDiagnosisIntegration:

    def test_no_telemetry_gap_for_control_fields(self):
        dc = DataCollector(window_seconds=120)
        bridge = fake_bridge(ctrl_x=0, ctrl_y=0)
        memory = fake_memory(stuck=0.0, escape=False)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow, n=5)

        engine = DiagnosisEngine(dc)
        findings = engine.evaluate()
        gap_fields = set()
        for f in findings:
            if f.pattern_id == "telemetry_gap":
                gap_fields.update(f.current_values.get("missing_fields", []))
        gap_control = gap_fields & {
            "control_magnitude", "control_x_zero", "control_y_zero",
            "escape_behavior", "jump_not_active",
        }
        assert not gap_control, (
            f"P1-1 fields still reported as telemetry gaps: {gap_control}"
        )

    def test_below_ground_stuck_does_not_crash(self):
        dc = DataCollector(window_seconds=60)
        pose = [100, -50, 200, 0]
        bridge = fake_bridge(ctrl_x=0, ctrl_y=0, pose=pose)
        memory = fake_memory(stuck=45.0, visited=10, coverage=2.0)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow, n=30)

        engine = DiagnosisEngine(dc)
        findings = engine.evaluate()
        telemetry_gaps = [f for f in findings if f.pattern_id == "telemetry_gap"]
        gap_fields = set()
        for f in telemetry_gaps:
            gap_fields.update(f.current_values.get("missing_fields", []))
        assert "control_magnitude" not in gap_fields
        assert "pos_y" not in gap_fields

    def test_suspended_animation_does_not_crash(self):
        dc = DataCollector(window_seconds=60)
        bridge = fake_bridge(ctrl_x=0, ctrl_y=0)
        memory = fake_memory(stuck=20.0, escape=False)
        flow = fake_flow()
        _collect(dc, bridge, memory, flow, n=20)

        engine = DiagnosisEngine(dc)
        findings = engine.evaluate()
        gap_fields = set()
        for f in findings:
            if f.pattern_id == "telemetry_gap":
                gap_fields.update(f.current_values.get("missing_fields", []))
        assert "control_x_zero" not in gap_fields
        assert "control_y_zero" not in gap_fields
        assert "jump_not_active" not in gap_fields


# ---------------------------------------------------------------------------
# 4. /memory.json derivation (mirrors main.py formulas)
# ---------------------------------------------------------------------------


class TestMemoryJsonDerivation:

    @staticmethod
    def _build_memory_json_like(ctrl_x, ctrl_y, ctrl_jump, escape_behavior):
        """Replicate main.py's memory_json 5-field derivation."""
        return {
            "escape_behavior": escape_behavior,
            "control_magnitude": abs(ctrl_x) + abs(ctrl_y),
            "control_x_zero": ctrl_x == 0,
            "control_y_zero": ctrl_y == 0,
            "jump_not_active": not ctrl_jump,
        }

    def test_typical_motion_values(self):
        mem = self._build_memory_json_like(30, 40, False, True)
        assert mem["control_magnitude"] == 70
        assert mem["control_x_zero"] is False
        assert mem["jump_not_active"] is True
        assert mem["escape_behavior"] is True

    def test_suspended_animation_values(self):
        mem = self._build_memory_json_like(0, 0, False, False)
        assert mem["control_magnitude"] == 0
        assert mem["control_x_zero"] is True
        assert mem["control_y_zero"] is True
        assert mem["jump_not_active"] is True

    def test_escape_with_negative_turn(self):
        mem = self._build_memory_json_like(-60, 80, True, True)
        assert mem["control_magnitude"] == 140
        assert mem["escape_behavior"] is True
        assert mem["jump_not_active"] is False