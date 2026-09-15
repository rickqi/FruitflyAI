"""PIN tests for the evolution history recorder (agent.md rule 15).

The recorder is the mandatory evolution-record contract: every brain/skill
evolution must land a complete record (version/time/trigger/changes/tests)
in skills/evolution_history.json, and the resident skill loop auto-appends
a brain_update record when it observes a dashboard brain_version change.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.evolution_skill import EvolutionHistory  # noqa: E402


@pytest.fixture()
def hist(tmp_path):
    return EvolutionHistory(path=tmp_path / "evolution_history.json")


class TestAppendAndPersist:
    def test_append_assigns_auto_id_and_timestamp(self, hist):
        rec = hist.append({"kind": "brain_update_auto", "brain_version": "2.13.4",
                           "trigger": "test"})
        assert rec["id"].startswith("AUTO-")
        assert rec["recorded_at"]

    def test_records_persist_across_instances(self, hist):
        hist.append({"kind": "skill_fix", "trigger": "t1"})
        hist.append({"kind": "skill_fix", "trigger": "t2"})
        reloaded = EvolutionHistory(path=hist.path)
        assert len(reloaded.records) == 2
        assert reloaded.records[1]["trigger"] == "t2"

    def test_corrupt_file_quarantined_not_crash(self, tmp_path):
        p = tmp_path / "evolution_history.json"
        p.write_text("{not json at all", encoding="utf-8")
        h = EvolutionHistory(path=p)
        assert h.records == []
        assert p.with_suffix(".json.corrupt").exists()

    def test_missing_file_starts_empty(self, tmp_path):
        h = EvolutionHistory(path=tmp_path / "nope.json")
        assert h.records == [] and h.canonical == {}


class TestBrainVersionAutoRecord:
    def test_version_change_recorded_and_canonical_updated(self, hist):
        hist.canonical["brain"] = "2.13.3"
        rec = hist.record_brain_version("2.14.0", "2.13.3")
        assert rec["kind"] == "brain_update_auto"
        assert rec["brain_version"] == "2.14.0"
        assert rec["previous_version"] == "2.13.3"
        assert hist.canonical["brain"] == "2.14.0"

    def test_no_duplicate_when_unchanged(self, hist):
        hist.canonical["brain"] = "2.13.3"
        assert hist.record_brain_version("2.13.3", "2.13.3") is None
        assert hist.records == []

    def test_no_record_when_old_equals_new(self, hist):
        hist.canonical["brain"] = "2.13.3"
        assert hist.record_brain_version("2.13.3", None) is None

    def test_auto_record_demands_full_entry(self, hist):
        """The auto record must explicitly state it does not exempt the
        full trigger/changes/tests entry (agent.md rule 15)."""
        hist.canonical["brain"] = "2.13.3"
        rec = hist.record_brain_version("2.14.0", "2.13.3")
        assert any("rule 15" in c or "REQUIRED" in c for c in rec["changes"])


class TestFixAndVerificationRecords:
    def test_fix_record_fields(self, hist):
        class F:
            id = "fix_0042"
            fix_template = "# Strengthen oscillation-to-forward breakthrough\n# more"
            baseline_stuck = 155.8
            baseline_coverage = 11.1

        class Finding:
            pattern_id = "micro_loop_weave"
            severity = "high"
            diagnosis = "weave in place"
            current_values = {"loop_score": 1.0}

        rec = hist.record_fix(F(), Finding())
        assert rec["fix_id"] == "fix_0042"
        assert rec["pattern_id"] == "micro_loop_weave"
        assert rec["baseline"]["stuck"] == 155.8
        assert "breakthrough" in rec["changes"][0]

    def test_verification_updates_matching_fix_record(self, hist):
        class F:
            id = "fix_0042"
            fix_template = "x"
            baseline_stuck = 1.0
            baseline_coverage = 0.0

        class Finding:
            pattern_id = "p"
            severity = "high"
            diagnosis = "d"
            current_values = {}

        class V:
            fix_id = "fix_0042"
            passed = True
            effectiveness_score = 0.55
            stuck_reduction_pct = 40.0
            observation_seconds = 60.0

        hist.record_fix(F(), Finding())
        updated = hist.record_verification(V())
        assert updated["verification"]["passed"] is True
        assert updated["verification"]["effectiveness_score"] == 0.55

    def test_verification_unknown_fix_returns_none(self, hist):
        class V:
            fix_id = "fix_9999"
            passed = True
            effectiveness_score = 0.5
            stuck_reduction_pct = 1.0
            observation_seconds = 60.0

        assert hist.record_verification(V()) is None

    def test_saved_file_is_valid_json_with_schema(self, hist):
        hist.canonical = {"brain": "2.13.3", "skill": "3.0.0"}
        hist.append({"kind": "brain_update_auto", "brain_version": "2.14.0"})
        data = json.loads(hist.path.read_text(encoding="utf-8"))
        assert data["$schema"] == "fly64/evolution-history/1.0"
        assert data["canonical_versions"]["brain"] == "2.13.3"
        assert isinstance(data["records"], list)


class TestPipelineWiring:
    """End-to-end: run_one_cycle must detect a dashboard brain_version change
    and land a brain_update_auto record (the 'first second of an upgrade'
    promise), without spurious records when the version is unchanged."""

    def _pipeline(self, tmp_path):
        from skills.evolution_skill import EvolutionHistory, EvolutionPipeline

        p = EvolutionPipeline(
            auto_fix=False,
            fix_catalog_path=tmp_path / "fix_catalog.json",
            readme_path=tmp_path / "README.md")
        p.history = EvolutionHistory(path=tmp_path / "evolution_history.json")
        return p

    @staticmethod
    def _snapshots(version):
        bridge = {"pose": [0.0, 120.0, 0.0], "x": 10, "y": 20, "jump": False}
        memory = {"stuck_duration": 0.0, "visited_cells": 1, "coverage_pct": 0.1,
                  "anomaly_state": "idle", "health_score": 1.0, "reflex_active": False,
                  "escape_behavior": False, "loop_score": 0.0, "revisit_count": 0}
        flow = {"brain_version": version, "wall_score": 0.0, "asymmetry": 0.0,
                "ground_angle": 1.0, "ramp_score": 0.0, "terrain": "open_flat",
                "scene_name": "test", "scene_hash": "t00001", "mb_mbon_forward": 0.0}
        return bridge, memory, flow

    def _run_cycle(self, p, version, monkeypatch):
        bridge, memory, flow = self._snapshots(version)
        monkeypatch.setattr(p.collector, "fetch_all",
                            lambda: (bridge, memory, flow, {"events": []}))
        return p.run_one_cycle()

    def test_first_observation_primes_without_record(self, tmp_path, monkeypatch):
        p = self._pipeline(tmp_path)
        r = self._run_cycle(p, "2.13.3", monkeypatch)
        assert r.errors == []
        assert p.history.records == []          # prime only, no spurious record

    def test_version_change_in_cycle_lands_record(self, tmp_path, monkeypatch):
        p = self._pipeline(tmp_path)
        self._run_cycle(p, "2.13.3", monkeypatch)          # prime
        r = self._run_cycle(p, "2.14.0", monkeypatch)      # upgrade happens
        assert any("2.13.3 -> 2.14.0" in e for e in r.errors)
        autos = [x for x in p.history.records if x["kind"] == "brain_update_auto"]
        assert len(autos) == 1 and autos[0]["brain_version"] == "2.14.0"
        assert p.history.canonical["brain"] == "2.14.0"

    def test_same_version_next_cycle_no_duplicate(self, tmp_path, monkeypatch):
        p = self._pipeline(tmp_path)
        self._run_cycle(p, "2.13.3", monkeypatch)
        self._run_cycle(p, "2.14.0", monkeypatch)
        self._run_cycle(p, "2.14.0", monkeypatch)
        autos = [x for x in p.history.records if x["kind"] == "brain_update_auto"]
        assert len(autos) == 1

    def test_history_persists_across_pipeline_restart(self, tmp_path, monkeypatch):
        from skills.evolution_skill import EvolutionHistory

        p = self._pipeline(tmp_path)
        self._run_cycle(p, "2.13.3", monkeypatch)
        self._run_cycle(p, "2.14.0", monkeypatch)
        # resident loop restarts: fresh pipeline loads canonical from disk
        p2 = self._pipeline(tmp_path)
        assert p2.history.canonical["brain"] == "2.14.0"
        # same version again -> still no new record (already recorded)
        assert self._run_cycle(p2, "2.14.0", monkeypatch) is not None
        autos = [x for x in p2.history.records if x["kind"] == "brain_update_auto"]
        assert len(autos) == 1
