"""
P2-3: EVO 健康度量自动化 — tests for HealthTrendCollector.

Tests:
  1. HealthTrendCollector.snapshot() builds a valid row with all fields
  2. HealthTrendCollector appends to JSONL and caches in memory
  3. HealthTrendCollector.trend returns cached rows newest-last
  4. Dashboard /health-trend.json derivations (end-to-end)
  5. Integration: EvolutionPipeline creates HealthTrendCollector automatically
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.evolution_skill import (
    HealthTrendCollector,
    DataCollector,
    FixCatalog,
    EvolutionPipeline,
    SensorSample,
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


def _collect(dc, n=3):
    """Collect n samples at realistic timestamps."""
    now = time.time()
    bridge = fake_bridge(ctrl_x=30, ctrl_y=40)
    memory = fake_memory(stuck=15.0, escape=True, visited=50, coverage=20.0)
    flow = fake_flow()
    for i in range(n):
        dc.sample(bridge, memory, flow, now + i)
    return dc


# ---------------------------------------------------------------------------
# 1. Snapshot building
# ---------------------------------------------------------------------------


class TestSnapshotBuilding:

    def test_snapshot_minimal(self, tmp_path):
        """Snapshot without collector/fix_catalog still produces a row."""
        collector = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        row = collector.snapshot()
        assert "ts" in row
        assert row["fixes_total"] == 0
        assert row["evo_trials"] == 0

    def test_snapshot_with_collector(self, tmp_path):
        """Snapshot uses collector metrics when available."""
        dc = _collect(DataCollector(window_seconds=120))
        collector = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        row = collector.snapshot(collector=dc)
        assert row["health_score"] is not None
        assert row["stuck_duration"] is not None
        assert row["coverage_pct"] is not None

    def test_snapshot_with_fix_catalog(self, tmp_path):
        """Snapshot reads fix catalog statistics."""
        cat = FixCatalog(path=tmp_path / "fix_catalog.json")
        collector = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        row = collector.snapshot(fix_catalog=cat)
        assert row["fixes_total"] == 0
        assert row["fixes_effective"] == 0
        assert row["fixes_pending"] == 0

    def test_snapshot_with_extra(self, tmp_path):
        """Extra fields are merged into the row."""
        collector = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        row = collector.snapshot(extra={"iteration": 42, "findings_count": 3})
        assert row["iteration"] == 42
        assert row["findings_count"] == 3

    def test_snapshot_all_fields_present(self, tmp_path):
        """All expected keys exist in the snapshot."""
        dc = _collect(DataCollector(window_seconds=120))
        cat = FixCatalog(path=tmp_path / "fix_catalog.json")
        collector = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        row = collector.snapshot(collector=dc, fix_catalog=cat)

        expected_keys = [
            "ts", "health_score", "stuck_duration", "coverage_pct",
            "fixes_total", "fixes_effective", "fixes_pending", "fixes_reverted",
            "fix_effectiveness_rate", "evo_trials", "evo_passed",
        ]
        for key in expected_keys:
            assert key in row, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 2. Persistence (JSONL + cache)
# ---------------------------------------------------------------------------


class TestPersistence:

    def test_appends_to_jsonl(self, tmp_path):
        p = tmp_path / "trend.jsonl"
        collector = HealthTrendCollector(path=p)
        collector.snapshot(extra={"seq": 1})
        collector.snapshot(extra={"seq": 2})
        assert p.exists()
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["seq"] == 1
        assert json.loads(lines[1])["seq"] == 2

    def test_cache_returns_recent_rows(self, tmp_path):
        p = tmp_path / "trend.jsonl"
        collector = HealthTrendCollector(path=p, max_cached=5)
        for i in range(10):
            collector.snapshot(extra={"seq": i})
        assert len(collector.trend) == 5
        # Trend is newest-last, so first in cache should be seq=5
        assert collector.trend[0]["seq"] == 5
        assert collector.trend[-1]["seq"] == 9

    def test_reload_from_existing_file(self, tmp_path):
        p = tmp_path / "trend.jsonl"
        # Write some rows manually
        with p.open("w", encoding="utf-8") as f:
            for i in range(5):
                f.write(json.dumps({"seq": i, "ts": "2026-01-01T00:00:00Z"}) + "\n")
        collector = HealthTrendCollector(path=p, max_cached=10)
        assert len(collector.trend) == 5
        assert collector.trend[0]["seq"] == 0
        assert collector.trend[-1]["seq"] == 4

    def test_no_file_graceful(self, tmp_path):
        """Missing file does not crash."""
        p = tmp_path / "nonexistent" / "trend.jsonl"
        collector = HealthTrendCollector(path=p)
        row = collector.snapshot(extra={"seq": 1})
        assert row["seq"] == 1
        # File should have been created
        assert p.exists()


# ---------------------------------------------------------------------------
# 3. Integration: EvolutionPipeline creates HealthTrendCollector
# ---------------------------------------------------------------------------


class TestPipelineIntegration:

    def test_pipeline_has_health_trend(self):
        """EvolutionPipeline creates a HealthTrendCollector automatically."""
        pipe = EvolutionPipeline(auto_fix=False, window_seconds=30)
        assert hasattr(pipe, "health_trend")
        assert isinstance(pipe.health_trend, HealthTrendCollector)
        assert pipe.health_trend.path.name == "evolution_health_trend.jsonl"

    def test_pipeline_snapshot_no_crash(self, tmp_path):
        """Calling snapshot through a pipeline does not crash."""
        pipe = EvolutionPipeline(
            auto_fix=False, window_seconds=30,
            fix_catalog_path=tmp_path / "fix_catalog.json",
        )
        pipe.health_trend = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        # Snapshot without collector data — should not crash
        row = pipe.health_trend.snapshot(fix_catalog=pipe.fix_catalog)
        assert row is not None
        assert "ts" in row


# ---------------------------------------------------------------------------
# 4. /health-trend.json format (simulated)
# ---------------------------------------------------------------------------


class TestHealthTrendEndpoint:

    def test_health_trend_json_format(self, tmp_path):
        """The format served by /health-trend.json must be a JSON array."""
        collector = HealthTrendCollector(path=tmp_path / "trend.jsonl")
        for i in range(3):
            collector.snapshot(extra={"seq": i})
        # Simulate what main.py does: read last 200 rows, encode as JSON array
        rows = []
        with (tmp_path / "trend.jsonl").open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        payload = json.dumps(rows[-200:])
        decoded = json.loads(payload)
        assert isinstance(decoded, list)
        assert len(decoded) == 3
        assert decoded[0]["seq"] == 0
        assert decoded[-1]["seq"] == 2