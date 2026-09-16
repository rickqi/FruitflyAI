"""
Tests for EVO verification state persistence across brain restarts.

Verifies that VerificationEngine can save/load its state to/from disk,
and that a pending verification resumes correctly after a simulated restart.
"""

import json
import time
import tempfile
from pathlib import Path

import pytest

from skills.evolution_skill import (
    VerificationEngine, FixCatalog, DataCollector,
    FixEntry, VERIFY_STATE_PATH,
)


# ── Fixtures ──

@pytest.fixture
def tmp_skill_dir(tmp_path: Path):
    """Create a temporary skills directory with fix_catalog.json."""
    d = tmp_path / "skills"
    d.mkdir(parents=True)
    catalog = {
        "$catalog_version": "2.0",
        "meta": {"skill_name": "evolution_skill", "skill_version": "3.0.0",
                 "total_fixes": 1, "effective_count": 0, "ineffective_count": 0,
                 "pending_count": 1, "last_updated": "2026-09-07T00:00:00+00:00"},
        "fixes": [{
            "id": "fix_9999", "pattern_id": "test_pattern",
            "pattern_name": "Test pattern", "pattern_version": "1.0.0",
            "diagnosis": "Test diagnosis",
            "fix_template": "# Test fix template",
            "severity": "high",
            "applied_at": "2026-09-07T00:00:00+00:00",
            "version": 1,
            "baseline_stuck": 100.0, "baseline_coverage": 10.0,
            "post_fix_stuck": None, "post_fix_coverage": None,
            "effective": None, "effectiveness_score": None,
            "reverted": False, "reverted_at": None, "notes": "",
        }]
    }
    (d / "fix_catalog.json").write_text(json.dumps(catalog, indent=2), "utf-8")
    return d


@pytest.fixture
def collector():
    """Minimal DataCollector that returns fixed metrics."""
    c = DataCollector(window_seconds=120)
    c._metrics_cache = {"stuck_duration": 50.0, "coverage_pct": 15.0}
    return c


@pytest.fixture
def catalog(tmp_skill_dir: Path):
    return FixCatalog(path=tmp_skill_dir / "fix_catalog.json")


@pytest.fixture
def engine(collector, catalog, tmp_skill_dir: Path):
    """VerificationEngine with window=0.1s for fast testing."""
    eng = VerificationEngine(collector, catalog, window=0.1)
    eng._verify_state_path = tmp_skill_dir / "verify_state.json"
    eng._cleanup_state()
    return eng


# ── Tests ──

class TestVerifyPersistence:
    """EVO P0-1: verification state survives brain restarts."""

    def test_save_and_load_state(self, engine, catalog):
        """Verify state is correctly saved to disk and can be reloaded."""
        entry = catalog.fixes[0]
        engine.start(entry)

        # Check state file exists and has correct content
        assert engine._verify_state_path.exists()
        state = json.loads(engine._verify_state_path.read_text("utf-8"))
        assert state["active_fix_id"] == "fix_9999"
        assert state["started_at"] is not None
        assert state["baseline"]["stuck"] >= 0
        assert state["baseline"]["coverage"] >= 0

    def test_resume_after_restart(self, engine, catalog):
        """Simulate brain restart: create new engine that loads saved state."""
        entry = catalog.fixes[0]
        engine.start(entry)

        # Simulate restart: create a fresh engine (same state file)
        engine2 = VerificationEngine(engine.collector, catalog, window=10.0)
        engine2._verify_state_path = engine._verify_state_path

        resumed = engine2.resume_pending()
        assert resumed, "Should resume pending verification"
        assert engine2._active is not None
        assert engine2._active.id == "fix_9999"
        assert engine2._start is not None
        assert engine2._baseline is not None

    def test_verify_completes_on_resume_if_expired(self, engine, catalog):
        """If window expired during restart, verification completes immediately."""
        entry = catalog.fixes[0]
        engine.start(entry)

        # Manually set start to far in the past
        engine._start = time.time() - 60.0
        engine.save_state()

        # Fresh engine with short window — will detect expired on resume
        engine2 = VerificationEngine(engine.collector, catalog, window=5.0)
        engine2._verify_state_path = engine._verify_state_path

        # resume_pending should return False (auto-completed on resume)
        resumed = engine2.resume_pending()
        assert not resumed, "Expired window should not return resumed=True"

        # Verify outcome was recorded
        updated = catalog.fixes[0]
        assert updated.post_fix_stuck is not None, "Outcome should be recorded"

    def test_cleanup_after_completion(self, engine, catalog):
        """After verification completes, state file should be removed."""
        entry = catalog.fixes[0]
        engine.start(entry)
        assert engine._verify_state_path.exists()

        # Fast-forward by setting start to past
        engine._start = time.time() - 10.0
        engine._verify_state_path  # still present during verification

        # Complete the verification
        result = engine.tick()
        assert result is not None

        # File should be cleaned up
        assert not engine._verify_state_path.exists(), \
            "State file should be deleted after verification completes"

    def test_no_state_file_on_clean_start(self, engine):
        """Fresh engine without state file should resume_pending=False."""
        engine._cleanup_state()
        assert not engine.resume_pending()

    def test_corrupt_state_file_ignored(self, engine):
        """Corrupt verify_state.json should not crash resume."""
        engine._verify_state_path.write_text("not valid json", "utf-8")
        assert not engine.resume_pending()