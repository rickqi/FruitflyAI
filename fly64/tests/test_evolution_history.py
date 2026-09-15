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
