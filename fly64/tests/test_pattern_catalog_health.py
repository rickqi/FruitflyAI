"""Regression: PatternCatalog load health — normal, fallback, self-check warnings.

Root cause context (fly64-evo-autofix-closure):
  - default_patterns.json:47 had literal ``\n`` string → json.loads() returned
    2-length string instead of dict → except:pass swallowed → empty patterns
  - Fix: except:pass → explicit Exception logging at line 1632; debug log at
    line 1596; self-check at lines 1607-1628
  - These tests lock the fix: normal load must succeed, any failure must be
    visible (logs), and missing critical IDs / low count must warn.

Conventions (pytest.ini: pythonpath=., testpaths=tests):
    from skills.evolution_skill import PatternCatalog, DEFAULT_PATTERNS_PATH
"""
import json
import logging
from pathlib import Path

import pytest

from skills.evolution_skill import PatternCatalog, DEFAULT_PATTERNS_PATH


# ── helpers ──────────────────────────────────────────────────────────────────

CRITICAL_IDS: set[str] = {
    "circle_loop",
    "ramp_trap",
    "reflex_cooldown_gap",
    "low_coverage_stagnation",
    "below_ground_stuck",
    "fallen_recovery_stuck",
    "suspended_animation",
    "wall_corner_command_decoupled",
    "dopamine_plateau",
    "cliff_standoff",
    "micro_loop_weave",
    "micro_loop_weave_signal",
    "mbon_saturation",
    "primitive_timeout",
    "primitive_zero_disp",
    "mbon_wrong_direction",
}
EXPECTED_MIN_COUNT = 16


# ── tests ────────────────────────────────────────────────────────────────────


class TestPatternCatalogNormalLoad:
    """PatternCatalog loads default_patterns.json successfully."""

    def test_loads_at_least_16_patterns(self):
        catalog = PatternCatalog()
        assert len(catalog.patterns) >= EXPECTED_MIN_COUNT, (
            f"Expected >= {EXPECTED_MIN_COUNT} patterns, got {len(catalog.patterns)}"
        )

    def test_all_critical_ids_present(self):
        catalog = PatternCatalog()
        loaded_ids = {p.get("id") for p in catalog.patterns}
        missing = CRITICAL_IDS - loaded_ids
        assert not missing, (
            f"Critical pattern IDs missing after normal load: {sorted(missing)}"
        )

    def test_every_pattern_has_required_keys(self):
        """Each pattern must have id, name, version, conditions, diagnosis,
        fix_template, and fix_files."""
        catalog = PatternCatalog()
        required_keys = {"id", "name", "version", "conditions", "diagnosis", "fix_template", "fix_files"}
        for p in catalog.patterns:
            missing = required_keys - set(p.keys())
            assert not missing, (
                f"Pattern {p.get('id', '<unknown>')} missing keys: {sorted(missing)}"
            )

    def test_schema_version_is_set(self):
        catalog = PatternCatalog()
        assert catalog.schema_version == "2.0"

    def test_path_defaults_to_expected_file(self):
        catalog = PatternCatalog()
        assert catalog.path == DEFAULT_PATTERNS_PATH


class TestPatternCatalogFallback:
    """PatternCatalog falls back to empty patterns on failure."""

    def test_missing_file_returns_empty_patterns(self):
        """Non-existent path → _raw={}, patterns=[], schema_version='2.0'."""
        catalog = PatternCatalog(path=Path("/nonexistent/patterns.json"))
        assert catalog._raw == {}
        assert catalog.patterns == []
        assert catalog.schema_version == "2.0"

    def test_corrupted_json_returns_empty_patterns(self, tmp_path):
        """Invalid JSON file → Exception caught → empty patterns."""
        bad_file = tmp_path / "bad_patterns.json"
        bad_file.write_text('{"patterns": [broken json}', encoding="utf-8")
        catalog = PatternCatalog(path=bad_file)
        assert catalog._raw == {}
        assert catalog.patterns == []

    def test_corrupted_json_logs_error(self, tmp_path, caplog):
        """Exception during load emits an ERROR-level log."""
        bad_file = tmp_path / "bad_log.json"
        bad_file.write_text("not json at all", encoding="utf-8")
        caplog.set_level(logging.ERROR)
        _ = PatternCatalog(path=bad_file)
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("Failed to load patterns" in r.getMessage() for r in error_records), (
            "Expected ERROR log about failed pattern load"
        )


class TestPatternCatalogSelfCheck:
    """Self-check warnings for low count and missing critical IDs."""

    def test_warning_when_too_few_patterns(self, tmp_path, caplog):
        """Loading < 16 patterns triggers a WARNING."""
        few = tmp_path / "few_patterns.json"
        few.write_text(
            json.dumps({"$schema_version": "2.0", "patterns": [{"id": "only_one", "name": "x", "version": "1.0.0",
                                                                    "severity": "low", "description": "x",
                                                                    "conditions": {"wall_score": {"max": 0.1}},
                                                                    "diagnosis": "x",
                                                                    "fix_template": "x", "fix_files": []}]}),
            encoding="utf-8",
        )
        caplog.set_level(logging.WARNING)
        _ = PatternCatalog(path=few)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "Loaded" in r.getMessage() and "patterns" in r.getMessage()
            for r in warnings
        ), "Expected WARNING about low pattern count"

    def test_warning_when_critical_ids_missing(self, tmp_path, caplog):
        """Loading a valid file that is missing critical IDs triggers a WARNING."""
        missing_some = tmp_path / "missing_critical.json"
        # Only include circle_loop and ramp_trap — skip the other 14
        minimal = {
            "$schema_version": "2.0",
            "patterns": [
                {"id": "circle_loop", "name": "Circle loop", "version": "1.0.0",
                 "severity": "low", "description": "x",
                 "conditions": {"wall_score": {"max": 0.1}},
                 "diagnosis": "x", "fix_template": "x", "fix_files": []},
                {"id": "ramp_trap", "name": "Ramp trap", "version": "1.0.0",
                 "severity": "low", "description": "x",
                 "conditions": {"asymmetry_magnitude": {"max": 0.06}},
                 "diagnosis": "x", "fix_template": "x", "fix_files": []},
            ],
        }
        missing_some.write_text(json.dumps(minimal), encoding="utf-8")
        caplog.set_level(logging.WARNING)
        _ = PatternCatalog(path=missing_some)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "Critical pattern IDs missing" in r.getMessage()
            for r in warnings
        ), "Expected WARNING about missing critical IDs"