"""
P0-1: EVO auto-fix闭环 — FixExecutor tests.

Tests for ``skills/fix_executor.py``:
  1. Template parsing — replace directive
  2. Template parsing — insert_after directive
  3. Template parsing — insert_before directive
  4. Template parsing — manual-action fallback
  5. Replace execution (real file edit with backup)
  6. Insert_after execution
  7. Dry-run mode produces no file changes
  8. Rollback restores original content
  9. execute_all convenience integration with FixCatalog
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.fix_executor import (
    FixExecutor,
    FixExecutionReport,
    parse_fix_template,
    auto_fix_findings,
)  # noqa: E402
from skills.evolution_skill import FixCatalog, Finding, FixEntry  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a minimal workspace with a couple of source files."""
    src_dir = tmp_path / "fly64" / "fly64"
    src_dir.mkdir(parents=True)
    main_py = src_dir / "main.py"
    main_py.write_text(
        "GROUND_NORMAL = 120\n"
        "BRAIN_VERSION = \"2.4.0\"\n\n"
        "def cliff_avoidance():\n"
        "    # original cliff logic\n"
        "    pass\n\n"
        "def step():\n"
        "    # motion step\n"
        "    cliff_avoidance()\n"
        "    forward()\n",
        encoding="utf-8",
    )
    model_py = src_dir / "model.py"
    model_py.write_text(
        "def compute(self):\n"
        "    # color modulation\n"
        "    danger_red_index = 0.6\n"
        "    raw_x += danger_red_index * 30.0\n"
        "    return raw_x\n",
        encoding="utf-8",
    )
    return tmp_path


def _finding(**overrides):
    """Build a Finding-like duck object."""
    base = {
        "pattern_id": "circle_loop",
        "pattern_name": "Circle loop test",
        "pattern_version": "1.0.0",
        "severity": "high",
        "diagnosis": "Test diagnosis",
        "contradiction": "",
        "fix_template": "# File: fly64/fly64/main.py\n# Find: original cliff logic\n# Replace: revised cliff logic",
        "fix_files": ["fly64/fly64/main.py"],
        "current_values": {"stuck_duration": 150},
        "confidence": 0.85,
        "timestamp": 1_700_000_000,
    }
    base.update(overrides)
    return type("Finding", (), base)()


# ═══════════════════════════════════════════════════════════════════════
# 1. Template parsing tests
# ═══════════════════════════════════════════════════════════════════════


class TestParseFixTemplate:
    def test_replace_directive(self):
        template = (
            "# Fix: Add ground_angle gate\n"
            "# File: fly64/fly64/main.py\n"
            "# Find: cliff_trigger section\n"
            "# Replace: if ground_angle < 0.3: skip"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 1
        d = directives[0]
        assert d["file"] == "fly64/fly64/main.py"
        assert d["action"] == "replace"
        assert "cliff_trigger section" in d["find"]
        assert "ground_angle" in d["replace"]

    def test_insert_after_directive(self):
        template = (
            "# File: fly64/fly64/model.py\n"
            "# After: color modulation\n"
            "# Add: raw_x += 45.0  # stronger red avoid"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 1
        d = directives[0]
        assert d["action"] == "insert_after"
        assert "color modulation" in d["find"]
        assert "raw_x += 45.0" in d["add"]

    def test_insert_before_directive(self):
        template = (
            "# File: fly64/fly64/main.py\n"
            "# Before: def step():\n"
            "# Add: # NEW: helper function"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 1
        d = directives[0]
        assert d["action"] == "insert_before"
        assert "def step():" in d["find"]
        assert "# NEW: helper function" in d["add"]

    def test_append_directive(self):
        template = (
            "# File: fly64/fly64/main.py\n"
            "# Add: print('end of file')"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 1
        d = directives[0]
        assert d["action"] == "append"
        assert "print('end of file')" in d["add"]

    def test_manual_fallback(self):
        template = (
            "# Fix: Investigate reflex re-trigger gate, not cooldown\n"
            "# Check logs for trigger-candidate rejection\n"
            "# Tune _aggressive_cooldown_factor if needed"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 1
        assert directives[0]["action"] == "manual"
        assert "reflex" in directives[0]["manual_instructions"]

    def test_multiple_files(self):
        """Template with directives for two distinct files."""
        template = (
            "# File: fly64/fly64/main.py\n"
            "# Find: cliff logic\n"
            "# Replace: revised cliff logic\n"
            "# File: fly64/fly64/model.py\n"
            "# After: # color modulation\n"
            "# Add: # new color gain"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 2
        assert directives[0]["file"] == "fly64/fly64/main.py"
        assert directives[0]["action"] == "replace"
        assert directives[1]["file"] == "fly64/fly64/model.py"
        assert directives[1]["action"] == "insert_after"

    def test_empty_template(self):
        directives = parse_fix_template("")
        assert len(directives) == 1
        assert directives[0]["action"] == "manual"


# ═══════════════════════════════════════════════════════════════════════
# 2. Execution tests (real file edits)
# ═══════════════════════════════════════════════════════════════════════


class TestFixExecutorExecute:
    def test_replace_execution(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace, backup=True)
        report = executor.execute(
            fix_id="fix_0001",
            pattern_id="circle_loop",
            fix_template=(
                "# File: fly64/fly64/main.py\n"
                "# Find: original cliff logic\n"
                "# Replace: revised cliff logic with gate"
            ),
            fix_files=["fly64/fly64/main.py"],
        )
        assert report.all_applied is True
        assert len(report.actions) == 1
        assert report.actions[0].applied is True

        # Verify the file was actually changed
        main_py = tmp_workspace / "fly64" / "fly64" / "main.py"
        content = main_py.read_text(encoding="utf-8")
        assert "revised cliff logic with gate" in content
        assert "original cliff logic" not in content

        # Verify backup was created
        assert report.actions[0].backup_path != ""

    def test_insert_after_execution(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace, backup=True)
        report = executor.execute(
            fix_id="fix_0002",
            pattern_id="color_nav_blind",
            fix_template=(
                "# File: fly64/fly64/model.py\n"
                "# After: raw_x += danger_red_index * 30.0\n"
                "# Add: raw_x += 45.0  # boosted avoid"
            ),
            fix_files=["fly64/fly64/model.py"],
        )
        assert report.all_applied is True
        model_py = tmp_workspace / "fly64" / "fly64" / "model.py"
        content = model_py.read_text(encoding="utf-8")
        assert "raw_x += 45.0" in content

    def test_dry_run_no_modifications(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace, dry_run=True)
        main_py = tmp_workspace / "fly64" / "fly64" / "main.py"
        original = main_py.read_text(encoding="utf-8")

        report = executor.execute(
            fix_id="fix_0003",
            pattern_id="circle_loop",
            fix_template=(
                "# File: fly64/fly64/main.py\n"
                "# Find: original cliff logic\n"
                "# Replace: DRY RUN should not apply"
            ),
            fix_files=["fly64/fly64/main.py"],
        )
        assert report.all_applied is True
        assert report.actions[0].dry_run is True
        # File content must be unchanged
        assert main_py.read_text(encoding="utf-8") == original

    def test_execute_manual_action(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace)
        report = executor.execute(
            fix_id="fix_0004",
            pattern_id="reflex_cooldown_gap",
            fix_template=(
                "# Fix: Investigate reflex re-trigger gate\n"
                "# Check: reflex logs, cooldown map\n"
                "# Tune factor if needed"
            ),
        )
        assert report.manual_action_needed is True
        assert report.manual_instructions != ""
        assert report.all_applied is False

    def test_rollback_restores_original(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace, backup=True)
        main_py = tmp_workspace / "fly64" / "fly64" / "main.py"
        original = main_py.read_text(encoding="utf-8")

        report = executor.execute(
            fix_id="fix_0005",
            pattern_id="circle_loop",
            fix_template=(
                "# File: fly64/fly64/main.py\n"
                "# Find: original cliff logic\n"
                "# Replace: WRONG CONTENT"
            ),
            fix_files=["fly64/fly64/main.py"],
        )
        assert report.all_applied is True
        assert main_py.read_text(encoding="utf-8") != original

        outcomes = executor.rollback(report)
        assert all(o["success"] for o in outcomes)
        assert main_py.read_text(encoding="utf-8") == original

    def test_find_text_not_found(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace)
        report = executor.execute(
            fix_id="fix_0006",
            pattern_id="circle_loop",
            fix_template=(
                "# File: fly64/fly64/main.py\n"
                "# Find: NONEXISTENT TEXT\n"
                "# Replace: something else"
            ),
            fix_files=["fly64/fly64/main.py"],
        )
        assert report.all_applied is False
        assert len(report.actions) == 1
        assert report.actions[0].applied is False
        assert "not found" in report.actions[0].error.lower()


# ═══════════════════════════════════════════════════════════════════════
# 3. Integration: execute_all with FixCatalog
# ═══════════════════════════════════════════════════════════════════════


class TestExecuteAll:
    def test_execute_all_integration(self, tmp_workspace):
        """Verify execute_all records fixes in catalog and executes them."""
        cat = FixCatalog(path=tmp_workspace / "fix_catalog.json")
        executor = FixExecutor(workspace_root=tmp_workspace, dry_run=True)

        finding_a = _finding(
            pattern_id="circle_loop",
            fix_template="# File: fly64/fly64/main.py\n"
                         "# Find: original\n# Replace: revised",
        )
        finding_b = _finding(
            pattern_id="ramp_trap",
            fix_template="# File: fly64/fly64/model.py\n"
                         "# After: return raw_x\n# Add: # debug log",
        )

        reports = executor.execute_all([finding_a, finding_b], cat)
        assert len(reports) == 2
        assert all(r.fix_id for r in reports)

        # Verify both were recorded in the catalog
        assert any(f.pattern_id == "circle_loop" for f in cat.fixes)
        assert any(f.pattern_id == "ramp_trap" for f in cat.fixes)

    def test_auto_fix_findings_convenience(self, tmp_workspace):
        """The standalone convenience function works end-to-end."""
        cat = FixCatalog(path=tmp_workspace / "fix_catalog.json")
        finding = _finding(
            pattern_id="circle_loop",
            fix_template="# File: fly64/fly64/main.py\n"
                         "# Find: original\n# Replace: revised_convenience",
        )

        reports = auto_fix_findings(
            [finding], cat, workspace_root=tmp_workspace, dry_run=True,
        )
        assert len(reports) == 1
        assert reports[0].pattern_id == "circle_loop"


# ═══════════════════════════════════════════════════════════════════════
# 4. Edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_file_not_found(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace)
        report = executor.execute(
            fix_id="fix_9999",
            pattern_id="circle_loop",
            fix_template="# File: nonexistent/path.py\n"
                         "# Find: something\n# Replace: else",
        )
        assert report.all_applied is False

    def test_insert_before_execution(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace)
        report = executor.execute(
            fix_id="fix_0010",
            pattern_id="below_ground_stuck",
            fix_template=(
                "# File: fly64/fly64/main.py\n"
                "# Before: BRAIN_VERSION\n"
                "# Add: # DEBUG: fix below_ground_stuck\n"
            ),
            fix_files=["fly64/fly64/main.py"],
        )
        assert report.all_applied is True
        main_py = tmp_workspace / "fly64" / "fly64" / "main.py"
        content = main_py.read_text(encoding="utf-8")
        assert "# DEBUG: fix below_ground_stuck" in content
        # Verify the line was inserted before BRAIN_VERSION
        lines = content.splitlines()
        br_idx = next(i for i, l in enumerate(lines) if "BRAIN_VERSION" in l)
        assert lines[br_idx - 1].strip() == "# DEBUG: fix below_ground_stuck"

    def test_append_to_file(self, tmp_workspace):
        executor = FixExecutor(workspace_root=tmp_workspace)
        report = executor.execute(
            fix_id="fix_0011",
            pattern_id="suspended_animation",
            fix_template=(
                "# File: fly64/fly64/main.py\n"
                "# Add: # EOF marker"
            ),
            fix_files=["fly64/fly64/main.py"],
        )
        assert report.all_applied is True
        main_py = tmp_workspace / "fly64" / "fly64" / "main.py"
        content = main_py.read_text(encoding="utf-8")
        assert "# EOF marker" in content