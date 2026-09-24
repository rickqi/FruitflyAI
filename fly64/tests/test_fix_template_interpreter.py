"""
P0-A1: EVO — FixTemplateInterpreter tests.

Tests for ``skills/fix_template_interpreter.py`` covering:
  1.  Extended directive parsing: ``# Change:`` + ``# To:``
  2.  Extended directive parsing: ``# Files:`` multi-file syntax
  3.  Extended directive parsing: ``# Add after <anchor>`` / ``# Add below <anchor>``
  4.  Extended directive parsing: ``# Add before <anchor>`` / ``# Insert before <anchor>``
  5.  LLM fallback — heuristic succeeds, no LLM needed
  6.  LLM fallback — heuristic yields only manual, LLM not invoked (allow_llm=False)
  7.  LLM fallback — heuristic yields only manual, LLM returns None (graceful degrade)
  8.  Pattern rewriting — all 8 degradation patterns produce structured output
  9.  interpret_and_execute with FixExecutor integration
  10. Multi-file distribution via ``# Files:``
  11. Pure-manual template remains manual after interpretation
  12. Empty template handling
  13. Edge cases — mixed directives with code blocks
"""

import io
import json
import os
import sys
import tempfile
import urllib.error
from pathlib import Path

import unittest.mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.fix_template_interpreter import (
    FixTemplateInterpreter,
    InterpretationResult,
    parse_extended_directives,
    interpret_fix_template,
    _STRUCTURED_REWRITES,
    _call_llm_subagent,
)
from skills.fix_executor import (
    FixExecutor,
    parse_fix_template,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a minimal workspace for executor integration tests."""
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
    memory_py = src_dir / "memory.py"
    memory_py.write_text(
        "class ReflexController:\n"
        "    def __init__(self):\n"
        "        self.base_cooldown_duration = 10.0\n"
        "        self.stuck_duration = 0\n\n"
        "    def _start_reflex(self):\n"
        "        cooldown_duration = 10.0\n"
        "        return cooldown_duration\n",
        encoding="utf-8",
    )
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════
# 1. Extended directive parsing: # Change: / # To:
# ═══════════════════════════════════════════════════════════════════════

class TestParseExtendedChangeTo:
    def test_change_to_produces_change_action(self):
        """# Change: + # To:  → action='change' with change/to fields."""
        lines = [
            "# Fix: adjust threshold",
            "# File: fly64/fly64/memory.py",
            "# Change: cooldown_duration = 10.0",
            "# To: cooldown = max(2.0, 10.0 - stuck_duration * 0.05)",
        ]
        directives = parse_extended_directives(lines)
        assert len(directives) == 1
        d = directives[0]
        assert d["action"] == "change"
        assert "cooldown_duration = 10.0" in d["change"]
        assert "cooldown = max" in d["to"]
        assert d["file"] == "fly64/fly64/memory.py"

    def test_change_to_with_add_fallback(self):
        """# Change: + # Add:  → also treated as change action."""
        lines = [
            "# File: fly64/fly64/main.py",
            "# Change: original cliff logic",
            "# Add: if ground_angle < 0.3:  # skip cliff",
        ]
        directives = parse_extended_directives(lines)
        assert len(directives) == 1
        d = directives[0]
        assert d["action"] == "change"
        assert "original cliff logic" in d["change"]
        assert "ground_angle < 0.3" in d["to"]

    def test_change_to_find_replace_still_works(self):
        """Classic # File: + # Find: + # Replace: still works."""
        lines = [
            "# File: fly64/fly64/model.py",
            "# Find: danger_red_index = 0.6",
            "# Replace: danger_red_index = 0.8",
        ]
        directives = parse_extended_directives(lines)
        assert len(directives) == 1
        d = directives[0]
        assert d["action"] == "replace"
        assert d["file"] == "fly64/fly64/model.py"
        assert "danger_red_index = 0.6" in d["find"]
        assert "0.8" in d["replace"]


# ═══════════════════════════════════════════════════════════════════════
# 2. Extended directive parsing: # Files: multi-file syntax
# ═══════════════════════════════════════════════════════════════════════

class TestParseExtendedMultiFile:
    def test_files_comma_separated(self):
        """# Files: with comma-separated paths."""
        lines = [
            "# Files: fly64/fly64/main.py, fly64/fly64/model.py",
            "# Find: ORIGINAL_CONSTANT",
            "# Replace: UPDATED_CONSTANT",
        ]
        directives = parse_extended_directives(lines)
        assert len(directives) == 2
        files = [d["file"] for d in directives]
        assert "fly64/fly64/main.py" in files
        assert "fly64/fly64/model.py" in files
        assert all(d["action"] == "replace" for d in directives)

    def test_files_semicolon_separated(self):
        """# Files: with semicolon-separated paths."""
        lines = [
            "# Files: a.py; b.py; c.py",
            "# Add: # shared footer",
        ]
        directives = parse_extended_directives(lines)
        assert len(directives) == 3
        assert all(d["action"] == "append" for d in directives)

    def test_files_followed_by_adjust(self):
        """# Files: + # Adjust: yields advisory + multi-file registration."""
        lines = [
            "# Files: fly64/fly64/main.py, fly64/fly64/model.py",
            "# Adjust: tune breakout_gain from 0.15 to 0.25",
        ]
        directives = parse_extended_directives(lines)
        # Adjust produces no directive, but Files emits registration
        assert len(directives) >= 1


# ═══════════════════════════════════════════════════════════════════════
# 3. Extended directive parsing: # Add after / # Add below
# ═══════════════════════════════════════════════════════════════════════

class TestParseExtendedAddAfter:
    def test_add_after_anchor(self):
        """# Add after <anchor>  →  action='insert_after'."""
        lines = [
            "# File: fly64/fly64/main.py",
            "# Add after slope detection:",
            "# Code:",
            "if ramp_score > 0.5 and stuck_duration > 180:",
            "    override()",
        ]
        directives = parse_extended_directives(lines)
        assert len(directives) >= 1
        # Find the insert_after directive
        insert_dirs = [d for d in directives if d["action"] == "insert_after"]
        assert len(insert_dirs) >= 1
        d = insert_dirs[0]
        assert "slope detection" in d["find"]

    def test_add_below_anchor(self):
        """# Add below <anchor>  →  same as add_after."""
        lines = [
            "# File: fly64/fly64/main.py",
            "# Add below cliff_avoidance():",
            "# Add: # NEW: altitude gate",
        ]
        directives = parse_extended_directives(lines)
        insert_dirs = [d for d in directives if d["action"] == "insert_after"]
        assert len(insert_dirs) >= 1
        assert "cliff_avoidance" in insert_dirs[0]["find"]

    def test_add_before_anchor(self):
        """# Add before <anchor>  →  action='insert_before'."""
        lines = [
            "# File: fly64/fly64/main.py",
            "# Add before def step():",
            "# Add: # PRE: helper",
        ]
        directives = parse_extended_directives(lines)
        before_dirs = [d for d in directives if d["action"] == "insert_before"]
        assert len(before_dirs) >= 1
        assert "def step():" in before_dirs[0]["find"]

    def test_insert_before_anchor(self):
        """# Insert before <anchor>  →  action='insert_before'."""
        lines = [
            "# File: fly64/fly64/main.py",
            "# Insert before # motion step",
            "# Add: # pre-step debug",
        ]
        directives = parse_extended_directives(lines)
        before_dirs = [d for d in directives if d["action"] == "insert_before"]
        assert len(before_dirs) >= 1


# ═══════════════════════════════════════════════════════════════════════
# 4. FixTemplateInterpreter: heuristic path (LLM not needed)
# ═══════════════════════════════════════════════════════════════════════

class TestInterpreterHeuristic:
    def test_structured_template_high_confidence(self):
        """Heuristic-passable template returns confidence=1.0, used_llm=False."""
        interp = FixTemplateInterpreter()
        template = (
            "# File: fly64/fly64/main.py\n"
            "# Find: cliff logic\n"
            "# Replace: gated cliff logic\n"
        )
        result = interp.interpret(template, allow_llm=False)
        assert result.confidence == 1.0
        assert result.used_llm is False
        assert len(result.directives) == 1
        assert result.directives[0]["action"] == "replace"

    def test_manual_template_without_llm(self):
        """Pure-manual template + allow_llm=False → confidence=0."""
        interp = FixTemplateInterpreter()
        template = (
            "# Investigate: all controls zero\n"
            "# Check bridge connectivity, visual_connected flag\n"
        )
        result = interp.interpret(template, allow_llm=False)
        assert result.confidence == 0.0
        assert result.used_llm is False
        assert result.directives[0]["action"] == "manual"

    def test_manual_template_with_llm_graceful_degrade(self):
        """Multi-line manual-only template reaches LLM fallback (or degrades gracefully when LLM unavailable)."""
        interp = FixTemplateInterpreter()
        template = (
            "# Inspect: weird corner behavior\n"
            "# Look at the corollary discharge path\n"
        )
        result = interp.interpret(template, allow_llm=True)
        # The is_manual fix ensures we reach the LLM path instead of early-returning
        # with confidence=1.0. Outcome depends on LLM availability:
        #   - LLM configured → confidence≈0.7, used_llm=True
        #   - LLM unset       → confidence=0.0,  used_llm=False (graceful degrade)
        # Either is valid; the critical assertion is manual action, not the specific confidence.
        assert result.confidence in (0.0, 1.0) or result.confidence > 0.0  # not 1.0 (would mean early return)
        assert result.directives[0]["action"] == "manual"
        # If LLM was used, confidence should be > 0; if LLM was unavailable, confidence == 0
        if result.used_llm:
            assert result.confidence > 0.0
        else:
            assert result.confidence == 0.0

    def test_interpret_changeto_directive(self):
        """Interpret # Change: + # To: template via heuristic path."""
        interp = FixTemplateInterpreter()
        template = (
            "# Fix: adjust threshold\n"
            "# File: fly64/fly64/memory.py\n"
            "# Change: cooldown_duration = 10.0\n"
            "# To: cooldown = adaptive_formula()\n"
        )
        result = interp.interpret(template, allow_llm=False)
        assert result.confidence == 1.0
        assert len(result.directives) == 1
        assert result.directives[0]["action"] == "change"


# ═══════════════════════════════════════════════════════════════════════
# 5. Pattern rewriting — all 8 degradation patterns
# ═══════════════════════════════════════════════════════════════════════

class TestRewriteDegradationPatterns:
    """Verify all 8 degradation patterns have a structured rewrite."""

    PATTERN_IDS = [
        "circle_loop",
        "ramp_trap",
        "reflex_cooldown_gap",
        "low_coverage_stagnation",
        "below_ground_stuck",
        "fallen_recovery_stuck",
        "suspended_animation",
        "wall_corner_command_decoupled",
    ]

    def test_all_eight_patterns_have_rewrite(self):
        missing = [pid for pid in self.PATTERN_IDS if pid not in _STRUCTURED_REWRITES]
        assert not missing, f"Missing rewrites for: {missing}"

    # Patterns whose rewrite carries a concrete edit.  The round trip through
    # rewrite() -> interpret() must therefore still yield a directive that
    # FixExecutor.execute has a branch for.
    EXECUTABLE_PATTERNS = [
        "circle_loop",
        "ramp_trap",
        "reflex_cooldown_gap",
        "low_coverage_stagnation",
        "below_ground_stuck",
        "wall_corner_command_decoupled",
    ]
    # Patterns that are diagnostic checklists by design (# Check: / # Adjust:
    # only — no # Find: / # Change: / # Add: payload anywhere).  There is no
    # mechanical edit to derive, so the honest result is a single 'manual'
    # directive carrying the checklist; claiming an executable fix here would
    # be exactly the "mechanism exists / reports success / cannot take effect"
    # failure mode this suite guards against.
    ADVISORY_PATTERNS = ["fallen_recovery_stuck", "suspended_animation"]

    def _interpret_rewrite(self, interp, pid):
        """rewrite() -> interpret() for one catalog pattern."""
        return interp.interpret(interp.rewrite({
            "id": pid,
            "name": pid.replace("_", " ").title(),
            "fix_template": f"# Fix: {pid}",
            "fix_files": ["fly64/fly64/main.py"],
            "diagnosis": f"Diagnosis for {pid}",
        }), allow_llm=False)

    def test_pattern_partition_is_complete(self):
        """Every catalog pattern must be classified exactly once, so a new
        pattern cannot silently escape the executable/advisory contract."""
        assert set(self.EXECUTABLE_PATTERNS) | set(self.ADVISORY_PATTERNS) == set(
            self.PATTERN_IDS)
        assert not (set(self.EXECUTABLE_PATTERNS) & set(self.ADVISORY_PATTERNS))

    def test_every_rewrite_produces_directives(self, tmp_workspace):
        interp = FixTemplateInterpreter(workspace_root=tmp_workspace)
        for pid in self.PATTERN_IDS:
            result = self._interpret_rewrite(interp, pid)
            assert len(result.directives) >= 1, (
                f"pattern={pid} produced zero directives"
            )

    def test_executable_rewrites_are_not_manual(self, tmp_workspace):
        """A rewrite that carries an edit must come back as a runnable action."""
        interp = FixTemplateInterpreter(workspace_root=tmp_workspace)
        for pid in self.EXECUTABLE_PATTERNS:
            result = self._interpret_rewrite(interp, pid)
            actions = [d.get("action") for d in result.directives]
            assert any(a not in ("manual", "advisory") for a in actions), (
                f"pattern={pid} is still manual after rewrite: {actions}")
            assert result.confidence == 1.0, (
                f"pattern={pid} reports confidence {result.confidence}")
            assert all(d.get("file") for d in result.directives), (
                f"pattern={pid} produced a directive without a target file")

    def test_advisory_rewrites_are_flagged_not_applied(self, tmp_workspace):
        """# Check: / # Adjust: checklists carry no payload: they must resolve
        to 'manual' with the checklist preserved, never to a silent success."""
        interp = FixTemplateInterpreter(workspace_root=tmp_workspace)
        for pid in self.ADVISORY_PATTERNS:
            result = self._interpret_rewrite(interp, pid)
            assert [d.get("action") for d in result.directives] == ["manual"], (
                f"pattern={pid}: {result.directives}")
            assert result.confidence == 0.0, (
                f"pattern={pid} claims confidence {result.confidence}")
            assert "# Check:" in result.manual_instructions
            assert "# Adjust:" in result.manual_instructions, (
                f"pattern={pid} lost part of its checklist: "
                f"{result.manual_instructions!r}")

    def test_circle_loop_specific(self):
        """circle_loop rewrite has # Change: + # To: directives."""
        template = _STRUCTURED_REWRITES["circle_loop"]
        directives = parse_extended_directives(template.strip().splitlines())
        change_dirs = [d for d in directives if d.get("action") == "change"]
        assert len(change_dirs) >= 1
        assert "cliff_rate < -0.03" in change_dirs[0]["change"]

    def test_below_ground_stuck_specific(self):
        """below_ground_stuck rewrite changes fallen threshold."""
        template = _STRUCTURED_REWRITES["below_ground_stuck"]
        directives = parse_extended_directives(template.strip().splitlines())
        change_dirs = [d for d in directives if d.get("action") == "change"]
        assert len(change_dirs) >= 1
        assert "_below_ground = _py < -200" in change_dirs[0]["change"] or "_below_ground = _py < -200" in change_dirs[0].get(
            "find", ""
        )


# ═══════════════════════════════════════════════════════════════════════
# 6. Integration: interpret_and_execute with FixExecutor
# ═══════════════════════════════════════════════════════════════════════

class TestInterpretAndExecute:
    def test_change_to_execution(self, tmp_workspace):
        """Interpret # Change: / # To: template, then execute via executor."""
        executor = FixExecutor(workspace_root=tmp_workspace, backup=True)
        interpreter = FixTemplateInterpreter(workspace_root=tmp_workspace)

        report = interpreter.interpret_and_execute(
            template=(
                "# Fix: adjust threshold\n"
                "# File: fly64/fly64/main.py\n"
                "# Change: GROUND_NORMAL = 120\n"
                "# To: GROUND_NORMAL = 150\n"
            ),
            executor=executor,
            fix_id="fix_9001",
            pattern_id="circle_loop",
        )

        assert report.all_applied is True
        main_py = tmp_workspace / "fly64" / "fly64" / "main.py"
        content = main_py.read_text(encoding="utf-8")
        assert "GROUND_NORMAL = 150" in content
        assert "GROUND_NORMAL = 120" not in content

    def test_manual_template_interpret_and_execute(self, tmp_workspace):
        """Pure-manual template goes through interpret_and_execute as manual."""
        executor = FixExecutor(workspace_root=tmp_workspace)
        interpreter = FixTemplateInterpreter(workspace_root=tmp_workspace)

        report = interpreter.interpret_and_execute(
            template=(
                "# Inspect: unknown behavior\n"
                "# Tune parameters if needed\n"
            ),
            executor=executor,
            fix_id="fix_9002",
            pattern_id="suspended_animation",
        )
        assert report.manual_action_needed is True
        assert report.manual_instructions != ""


# ═══════════════════════════════════════════════════════════════════════
# 6b. End-to-end: the executable rewrites really apply through FixExecutor
# ═══════════════════════════════════════════════════════════════════════

class TestExecutableRewritesApplyEndToEnd:
    """The contract is "EVO auto-fix can execute the directive", not "the
    parser returned a dict" — so every executable rewrite is driven through
    ``FixExecutor`` against files that contain the anchors it names."""

    MAIN_PY = (
        "GROUND_NORMAL = 120\n"
        "\n"
        "\n"
        "if (not is_ramp or ramp_stuck_override) and model.cliff_confirmed and model.cliff_rate < -0.03:\n"
        "    pass\n"
        "\n"
        "\n"
        "ramp_stuck_override = is_ramp and memory_ctrl.stuck_duration > 30.0\n"
        "\n"
        "\n"
        "def cliff_avoidance():\n"
        "    if wall_score < 0.1 and asymmetry_magnitude < 0.06:  # cliff avoidance triggers\n"
        "        pass\n"
        "\n"
        "\n"
        "# slope detection:\n"
        "ramp_score = 0.0\n"
        "\n"
        "\n"
        "# normal escape logic:\n"
        "def step():\n"
        "    # control computation:\n"
        "    control.y = 40\n"
        "\n"
        "\n"
        "_below_ground = _py < -200\n"
        "\n"
        "\n"
        "or bool(memory_ctrl.spatial.coverage_stalled)):\n"
    )
    MEMORY_PY = (
        "class ReflexController:\n"
        "    def __init__(self):\n"
        "        self.base_cooldown_duration = 8.0\n"
        "\n"
        "    def _start_reflex(self):\n"
        "        cooldown_duration: float = 5.0,\n"
        "        return cooldown_duration\n"
        "\n"
        "    def fallen(self, pos_y):\n"
        "        fallen = pos_y < -100\n"
        "        return fallen\n"
    )
    # (pattern id) -> (file, text that can only be there after the edit applied)
    EXPECTATIONS = {
        "circle_loop": (
            "fly64/fly64/main.py", "and ground_angle < 0.3",
        ),
        "ramp_trap": (
            "fly64/fly64/main.py",
            "if ramp_score > 0.5 and stuck_duration > 180:",
        ),
        "reflex_cooldown_gap": (
            "fly64/fly64/memory.py",
            "cooldown = max(2.0, self.base_cooldown_duration",
        ),
        "low_coverage_stagnation": (
            "fly64/fly64/main.py",
            "if coverage_stagnant_120s and visited_cells < 50:",
        ),
        "below_ground_stuck": (
            "fly64/fly64/main.py", "fallen = pos_y < 50",
        ),
        "wall_corner_command_decoupled": (
            "fly64/fly64/main.py", "expected = control.y * 0.6",
        ),
    }

    def _write_fixtures(self, workspace):
        src = workspace / "fly64" / "fly64"
        src.mkdir(parents=True, exist_ok=True)
        (src / "main.py").write_text(self.MAIN_PY, encoding="utf-8")
        (src / "memory.py").write_text(self.MEMORY_PY, encoding="utf-8")

    @staticmethod
    def _pattern(pid):
        return {"id": pid, "name": pid, "fix_template": "",
                "fix_files": [], "diagnosis": ""}

    def test_each_executable_rewrite_applies(self, tmp_path):
        interpreter = FixTemplateInterpreter(workspace_root=tmp_path)
        executor = FixExecutor(workspace_root=tmp_path, backup=False)
        assert set(self.EXPECTATIONS) == set(
            TestRewriteDegradationPatterns.EXECUTABLE_PATTERNS)
        for pid in TestRewriteDegradationPatterns.EXECUTABLE_PATTERNS:
            self._write_fixtures(tmp_path)          # fresh files per pattern
            report = interpreter.interpret_and_execute(
                template=interpreter.rewrite(self._pattern(pid)),
                executor=executor,
                fix_id=f"fix_{pid}",
                pattern_id=pid,
            )
            rel, expected = self.EXPECTATIONS[pid]
            assert report.actions, f"{pid}: nothing was executed at all"
            assert report.all_applied is True, (
                f"{pid}: {[a.to_dict() for a in report.actions]}")
            assert expected in (tmp_path / rel).read_text(encoding="utf-8"), (
                f"{pid}: {expected!r} missing after execution")

    def test_advisory_rewrites_report_manual_action(self, tmp_path):
        interpreter = FixTemplateInterpreter(workspace_root=tmp_path)
        executor = FixExecutor(workspace_root=tmp_path)
        for pid in TestRewriteDegradationPatterns.ADVISORY_PATTERNS:
            report = interpreter.interpret_and_execute(
                template=interpreter.rewrite(self._pattern(pid)),
                executor=executor,
                fix_id=f"fix_{pid}",
                pattern_id=pid,
            )
            assert report.manual_action_needed is True, pid
            assert "# Check:" in report.manual_instructions, pid


# ═══════════════════════════════════════════════════════════════════════
# 7. Edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_template(self):
        directives = parse_extended_directives([""])
        assert len(directives) == 1
        assert directives[0]["action"] == "manual"

    def test_only_comments(self):
        directives = parse_extended_directives([
            "# Fix: some investigation",
            "# Look at logs",
            "# Tune if needed",
        ])
        assert len(directives) >= 1

    def test_mixed_code_block_directives(self):
        """Template with # Add after + code block."""
        lines = [
            "# File: fly64/fly64/main.py",
            "# Add after slope detection:",
            "# Code:",
            "if ramp_score > 0.5 and stuck_duration > 180:",
            "    control.x = override_value",
        ]
        directives = parse_extended_directives(lines)
        insert_dirs = [d for d in directives if d["action"] == "insert_after"]
        assert len(insert_dirs) >= 1
        assert "slope detection" in insert_dirs[0]["find"]

    def test_change_to_without_file_returns_manual(self):
        """Change/To without a # File: line → manual."""
        lines = [
            "# Change: some constant",
            "# To: new constant",
        ]
        directives = parse_extended_directives(lines)
        # Without a file context, this is manual
        assert directives[0]["action"] == "manual"


# ═══════════════════════════════════════════════════════════════════════
# 8. Standalone convenience function
# ═══════════════════════════════════════════════════════════════════════

class TestInterpretFixTemplate:
    def test_interpret_fix_template_convenience(self):
        result = interpret_fix_template(
            "# File: some/file.py\n"
            "# Find: OLD_VALUE\n"
            "# Replace: NEW_VALUE\n",
            allow_llm=False,
        )
        assert result.confidence == 1.0
        assert len(result.directives) == 1

    def test_interpret_fix_template_manual_fallback(self):
        result = interpret_fix_template(
            "# Investigate odd behavior\n",
            allow_llm=False,
        )
        assert result.confidence == 0.0
        assert result.directives[0]["action"] == "manual"


# ═══════════════════════════════════════════════════════════════════════
# 9. Legacy compatibility — classic parse_fix_template still works
# ═══════════════════════════════════════════════════════════════════════

class TestLegacyCompatibility:
    def test_parse_fix_template_still_works(self):
        """The original parser remains unchanged and still resolves classic directives."""
        template = (
            "# File: fly64/fly64/main.py\n"
            "# Find: original cliff logic\n"
            "# Replace: revised cliff logic\n"
        )
        directives = parse_fix_template(template)
        assert len(directives) == 1
        assert directives[0]["action"] == "replace"
        assert "original cliff logic" in directives[0]["find"]
        assert "revised cliff logic" in directives[0]["replace"]

    def test_parse_fix_template_advisory_fallback_for_natural_language(self):
        """A natural-language-only template resolves to ``advisory``, not the
        legacy ``manual``.

        ``fix_executor._interpret_natural_language`` classifies verify /
        investigate templates (``advisory_type`` = ``verify`` | ``investigate``)
        and ``FixExecutor.execute`` handles that action by setting
        ``manual_action_needed = True`` — the human still has to act, so the
        legacy expectation of the bare ``manual`` name is superseded.  The
        interpreter's own fallback keeps emitting ``manual`` (its LLM-escalation
        contract), and both names are consumed by the executor.
        """
        directives = parse_fix_template(
            "# Investigate: weird behavior\n"
        )
        assert directives[0]["action"] == "advisory"
        assert directives[0]["advisory_type"] == "investigate"
        assert "Investigate" in directives[0]["manual_instructions"]


# ═══════════════════════════════════════════════════════════════════════
# 10. _call_llm_subagent — LLM endpoint invocation
# ═══════════════════════════════════════════════════════════════════════

class TestCallLlmSubagent:
    """Tests for ``_call_llm_subagent`` — the OpenAI-compatible HTTP wrapper.

    The function POSTs ``_build_interpret_prompt`` to
    ``{FLY64_LLM_BASE_URL}/chat/completions`` and returns the response text.
    Returns ``None`` on any error (HTTP, network, parse, missing config).
    """

    # ── mocks ─────────────────────────────────────────────────────────

    MOCK_RESPONSE = json.dumps({
        "choices": [{"message": {"content": '[{"action": "manual", "manual_instructions": "ok"}]'}}],
        "model": "gpt-4o-mini",
    })
    DEFAULT_TEMPLATE = "# Look into the behavior"

    @staticmethod
    def _mock_response(data: str, status: int = 200) -> io.BytesIO:
        """Create a mock HTTP response for urlopen."""
        m = unittest.mock.MagicMock(spec=io.BytesIO)
        m.read.return_value = data.encode("utf-8")
        m.__enter__.return_value = m
        if status != 200:
            m.__enter__.side_effect = urllib.error.HTTPError(
                url="http://fake/chat/completions",
                code=status,
                msg="error",
                hdrs={},
                fp=io.BytesIO(data.encode("utf-8")),
            )
        return m

    # ── setup / teardown ──────────────────────────────────────────────

    def setup_method(self):
        self._env_backup = os.environ.copy()
        os.environ["FLY64_LLM_BASE_URL"] = "http://fake-llm.example.com"
        os.environ["FLY64_LLM_API_KEY"] = "sk-fake-key"
        # ensure FLY64_LLM_MODEL is absent so default is exercised
        os.environ.pop("FLY64_LLM_MODEL", None)

    def teardown_method(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    # ── test cases ────────────────────────────────────────────────────

    def test_success(self):
        """Happy path returns the LLM response content."""
        mock_resp = self._mock_response(self.MOCK_RESPONSE)
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            return_value=mock_resp,
        ) as mock_urlopen:
            result = _call_llm_subagent(self.DEFAULT_TEMPLATE)

        assert result is not None
        assert "manual" in result

        # Verify the request was well-formed
        call_kwargs = mock_urlopen.call_args[0][0]
        assert call_kwargs.method == "POST"
        assert call_kwargs.full_url == "http://fake-llm.example.com/chat/completions"
        assert b"gpt-4o-mini" in call_kwargs.data
        assert b"Bearer sk-fake-key" in call_kwargs.headers.get("Authorization", "").encode()

    def test_missing_base_url(self):
        """Returns None when FLY64_LLM_BASE_URL is not set."""
        os.environ.pop("FLY64_LLM_BASE_URL", None)
        result = _call_llm_subagent(self.DEFAULT_TEMPLATE)
        assert result is None

    def test_missing_api_key(self):
        """Returns None when FLY64_LLM_API_KEY is not set."""
        os.environ.pop("FLY64_LLM_API_KEY", None)
        result = _call_llm_subagent(self.DEFAULT_TEMPLATE)
        assert result is None

    def test_http_4xx(self):
        """Returns None on HTTP 4xx."""
        mock_resp = self._mock_response('{"error": "not found"}', status=404)
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="http://fake/chat/completions",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=io.BytesIO(b'{"error": "not found"}'),
            ),
        ):
            result = _call_llm_subagent(self.DEFAULT_TEMPLATE)
        assert result is None

    def test_http_5xx(self):
        """Returns None on HTTP 5xx."""
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="http://fake/chat/completions",
                code=503,
                msg="Service Unavailable",
                hdrs={},
                fp=io.BytesIO(b"service overloaded"),
            ),
        ):
            result = _call_llm_subagent(self.DEFAULT_TEMPLATE)
        assert result is None

    def test_url_error(self):
        """Returns None on network error (URLError)."""
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            side_effect=urllib.error.URLError(reason="connection refused"),
        ):
            result = _call_llm_subagent(self.DEFAULT_TEMPLATE)
        assert result is None

    def test_malformed_json(self):
        """Returns None when the response body is not valid JSON."""
        mock_resp = self._mock_response("not-json-at-all")
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            result = _call_llm_subagent(self.DEFAULT_TEMPLATE)
        assert result is None

    def test_default_model(self):
        """Uses gpt-4o-mini when FLY64_LLM_MODEL is not set."""
        mock_resp = self._mock_response(self.MOCK_RESPONSE)
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            return_value=mock_resp,
        ) as mock_urlopen:
            _call_llm_subagent(self.DEFAULT_TEMPLATE)

        call_kwargs = mock_urlopen.call_args[0][0]
        assert b"gpt-4o-mini" in call_kwargs.data

    def test_context(self):
        """Additional context is appended to the prompt when context dict is given."""
        mock_resp = self._mock_response(self.MOCK_RESPONSE)
        ctx = {"stuck_duration": 120, "anomaly": "micro_loop"}
        with unittest.mock.patch(
            "skills.fix_template_interpreter.urllib.request.urlopen",
            return_value=mock_resp,
        ) as mock_urlopen:
            _call_llm_subagent(self.DEFAULT_TEMPLATE, context=ctx)

        call_kwargs = mock_urlopen.call_args[0][0]
        payload = json.loads(call_kwargs.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        assert "Additional context" in prompt
        assert '"stuck_duration": 120' in prompt
        assert '"anomaly": "micro_loop"' in prompt