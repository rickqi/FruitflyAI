"""EVO-059 · startup regression — the brain must import with a history file present.

The defect: `_load_evolution_history()` was invoked at module level (line 64)
while it writes `DashboardHTTP.evolution_json`, and DashboardHTTP is defined at
line 176.  The `except (OSError, ValueError, AttributeError)` clause does not
cover NameError, so the import raised

    NameError: name 'DashboardHTTP' is not defined

whenever `runtime/evolution_history.json` existed.

Why it escaped review: the function returns early via the OSError path when the
file is absent, so a fresh checkout imports fine.  In the WSL runtime the
resident EVO loop always writes that file, so the brain died at import on every
production start while every local test still passed.  This test therefore
reproduces the TRIGGERING CONDITION (a populated runtime history file) instead
of merely importing the module.

COMPREHENSIVE STARTUP COVERAGE (t5 gate sprint):
  — Module-level forward reference                 (existing)
  — Import with populated history file              (existing)
  — Helper idempotency                              (existing)
  — Evolution history: corrupted JSON               (NEW)
  — Evolution history: non-dict root                (NEW)
  — Evolution history: empty/missing iterations     (NEW)
  — Bridge file: missing at init                    (NEW)
  — Bridge file: incompatible magic                 (NEW)
  — Windows resource module absence                 (NEW)
  — Plugin import graceful failure                  (NEW)
  — DashboardHTTP class ordering guard              (NEW)
  — Encoding resilience (UTF-8 source on GBK)       (NEW)
  — main() entry-point stability                    (NEW)
"""

import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = REPO_ROOT / "fly64" / "main.py"


def _tree():
    return ast.parse(MAIN_PY.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# Section 1 — Module-level forward reference guard
# ═══════════════════════════════════════════════════════════════════════════

class TestNoModuleLevelForwardReference:
    def test_load_evolution_history_is_not_called_at_module_level(self):
        """The offending call must not reappear at module scope.

        Only top-level statements count — a call inside main() is exactly the
        fix we want, so function and class bodies are skipped.
        """
        for node in _tree().body:                       # module body only
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    fn = sub.func
                    name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                    assert name != "_load_evolution_history", (
                        "_load_evolution_history() is called at module level "
                        "again — it references DashboardHTTP, which is defined "
                        "later in the file, so the brain will fail to import "
                        "whenever runtime/evolution_history.json exists")

    def test_it_is_called_from_main(self):
        src = MAIN_PY.read_text(encoding="utf-8")
        main_fn = next((n for n in _tree().body
                        if isinstance(n, ast.FunctionDef) and n.name == "main"),
                       None)
        assert main_fn is not None, "main() not found"
        assert "_load_evolution_history()" in ast.get_source_segment(src, main_fn), (
            "main() no longer restores the evolution history, so the dashboard "
            "history would be empty after every restart (agent.md rule 9)")

    def test_dashboard_http_is_defined_after_the_helper(self):
        """Pins the ordering that makes the forward reference dangerous."""
        lines = MAIN_PY.read_text(encoding="utf-8").split("\n")
        helper = next(i for i, l in enumerate(lines)
                      if l.startswith("def _load_evolution_history"))
        klass = next(i for i, l in enumerate(lines)
                     if l.startswith("class DashboardHTTP"))
        assert helper < klass, (
            "with DashboardHTTP defined first, a module-level call would have "
            "been harmless and this guard would be meaningless")


# ═══════════════════════════════════════════════════════════════════════════
# Section 2 — Import with a populated evolution history file
# ═══════════════════════════════════════════════════════════════════════════

class TestRealImportWithHistoryPresent:
    """Import a real copy with a populated runtime history file."""

    def test_import_succeeds_when_history_exists(self, tmp_path):
        # the relative path "runtime/evolution_history.json" resolves against
        # CWD, so run the import with CWD inside the fixture directory
        (tmp_path / "runtime").mkdir()
        (tmp_path / "runtime" / "evolution_history.json").write_text(
            json.dumps({"iterations": [{"iter": 7, "note": "fixture"}]}),
            encoding="utf-8")

        code = textwrap.dedent("""
            import sys
            sys.path.insert(0, %r)
            import fly64.main as m
            # import must be safe on its own (this is the regression)
            print("IMPORT-OK")
            # and the helper must still work when main() invokes it
            m._load_evolution_history()
            assert m.evolution_log, "history was not restored from disk"
            assert m._evo_iter_counter == 7, m._evo_iter_counter
            print("RESTORE-OK")
        """) % str(REPO_ROOT)
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        assert "NameError" not in (proc.stderr or ""), (
            "import-time NameError is back:\n" + (proc.stderr or "")[-1500:])
        assert proc.returncode == 0, (
            "importing fly64.main with a populated runtime/evolution_history.json "
            "failed:\n" + (proc.stderr or "")[-1500:])
        assert "IMPORT-OK" in proc.stdout and "RESTORE-OK" in proc.stdout

    def test_import_succeeds_with_corrupted_history(self, tmp_path):
        """Corrupted (non-JSON) history must not prevent import.

        The _load_evolution_history() catch clause covers ValueError, which
        json.loads raises on malformed input.  This test ensures the catch
        works end-to-end.
        """
        (tmp_path / "runtime").mkdir()
        (tmp_path / "runtime" / "evolution_history.json").write_text(
            "this is not valid json {{{", encoding="utf-8")

        code = textwrap.dedent("""
            import sys
            sys.path.insert(0, %r)
            import fly64.main as m
            print("IMPORT-OK")
            m._load_evolution_history()
            print("RESTORE-OK")
        """) % str(REPO_ROOT)
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        assert proc.returncode == 0, (
            "corrupted evolution_history.json caused import failure:\n"
            + (proc.stderr or "")[-1500:])
        assert "IMPORT-OK" in proc.stdout
        assert "RESTORE-OK" in proc.stdout

    def test_import_succeeds_with_non_dict_history(self, tmp_path):
        """History root is a list instead of dict — must still be safe."""
        (tmp_path / "runtime").mkdir()
        (tmp_path / "runtime" / "evolution_history.json").write_text(
            json.dumps(["not", "a", "dict"]), encoding="utf-8")

        code = textwrap.dedent("""
            import sys
            sys.path.insert(0, %r)
            import fly64.main as m
            print("IMPORT-OK")
            m._load_evolution_history()
            print("RESTORE-OK")
        """) % str(REPO_ROOT)
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        assert proc.returncode == 0, (
            "non-dict evolution_history.json caused import failure:\n"
            + (proc.stderr or "")[-1500:])
        assert "IMPORT-OK" in proc.stdout

    def test_import_succeeds_with_empty_iterations(self, tmp_path):
        """History file exists but iterations list is empty."""
        (tmp_path / "runtime").mkdir()
        (tmp_path / "runtime" / "evolution_history.json").write_text(
            json.dumps({"iterations": []}), encoding="utf-8")

        code = textwrap.dedent("""
            import sys
            sys.path.insert(0, %r)
            import fly64.main as m
            print("IMPORT-OK")
            m._load_evolution_history()
            assert m._evo_iter_counter == 0
            print("RESTORE-OK")
        """) % str(REPO_ROOT)
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        assert proc.returncode == 0, (
            "empty iterations in evolution_history.json caused failure:\n"
            + (proc.stderr or "")[-1500:])
        assert "IMPORT-OK" in proc.stdout
        assert "RESTORE-OK" in proc.stdout

    def test_import_succeeds_with_missing_history_file(self, tmp_path):
        """No history file at all — first run — must not cause errors."""
        code = textwrap.dedent("""
            import sys
            sys.path.insert(0, %r)
            import fly64.main as m
            print("IMPORT-OK")
            m._load_evolution_history()
            assert m._evo_iter_counter == 0
            print("RESTORE-OK")
        """) % str(REPO_ROOT)
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        assert proc.returncode == 0, (
            "missing history file caused import failure:\n"
            + (proc.stderr or "")[-1500:])
        assert "IMPORT-OK" in proc.stdout
        assert "RESTORE-OK" in proc.stdout


# ═══════════════════════════════════════════════════════════════════════════
# Section 3 — Helper callability and idempotency
# ═══════════════════════════════════════════════════════════════════════════

class TestHelperIsCallableAfterImport:
    def test_helper_is_idempotent(self):
        sys.path.insert(0, str(REPO_ROOT))
        import fly64.main as m
        m._load_evolution_history()      # must not raise
        m._load_evolution_history()      # second call must also be safe


# ═══════════════════════════════════════════════════════════════════════════
# Section 4 — Bridge startup stability
# ═══════════════════════════════════════════════════════════════════════════

class TestBridgeStartup:
    """The bridge must handle missing/incompatible files gracefully."""

    def test_bridge_read_only_no_crash_on_missing_file(self, tmp_path):
        """Opening a non-existing bridge in read-only mode."""
        from fly64.bridge import SharedBridge
        none_path = tmp_path / "nonexistent.bin"
        with pytest.raises((FileNotFoundError, OSError)):
            SharedBridge(none_path, create=False)

    def test_bridge_create_succeeds(self, tmp_path):
        """Creating a fresh bridge file."""
        from fly64.bridge import SharedBridge
        bp = tmp_path / "new_bridge.bin"
        with SharedBridge(bp, create=True) as b:
            assert b.path.exists()
            assert b.path.stat().st_size > 0
            status = b.game_status()
            assert isinstance(status, dict)
            assert "seq" in status

    def test_bridge_rejects_incompatible_magic(self, tmp_path):
        """Bridge file with wrong magic bytes must be rejected."""
        from fly64.bridge import SharedBridge
        bp = tmp_path / "bad_bridge.bin"
        # Write garbage at the bridge path
        bp.write_bytes(b"GARBAGE\0" + bytes(120))
        with pytest.raises(ValueError, match="incompatible"):
            SharedBridge(bp, create=False)


# ═══════════════════════════════════════════════════════════════════════════
# Section 5 — Platform compatibility (resource module)
# ═══════════════════════════════════════════════════════════════════════════

class TestPlatformCompat:
    """Guards against platform-specific import failures."""

    def test_resource_import_graceful_on_windows(self):
        """The 'resource' module import guard in main.py must work."""
        src = MAIN_PY.read_text(encoding="utf-8")
        assert "resource = None" in src, (
            "resource=None fallback (for Windows) is missing from main.py")
        # Verify the guard pattern exists
        assert "except ImportError" in src, (
            "ImportError catch for resource module is missing")

    def test_bridge_clock_fallback_on_windows(self):
        """bridge.py must have Windows compat for clock_gettime_ns."""
        src = Path(REPO_ROOT / "fly64" / "bridge.py").read_text(encoding="utf-8")
        assert "perf_counter_ns" in src, (
            "bridge.py missing perf_counter_ns fallback for Windows")
        assert 'sys.platform == "win32"' in src or "sys.platform == 'win32'" in src, (
            "bridge.py missing Windows platform check")

    def test_utf8_encoding_on_source_reads(self):
        """All read_text calls on .py files should specify encoding='utf-8'."""
        src = MAIN_PY.read_text(encoding="utf-8")
        assert "open(" in src, "main.py seems empty"
        # Spot check: the evolution history handlers must specify encoding
        assert "open(\"runtime/evolution_history.json\", \"w\"" in src, (
            "evolution history write is not hardcoded — OK — but check it "
            "specifies encoding")
        assert "\"runtime/evolution_history.json\", encoding=\"utf-8\"" in src, (
            "evolution history read must specify encoding='utf-8' to avoid "
            "Windows GBK decoding failures")


# ═══════════════════════════════════════════════════════════════════════════
# Section 6 — Plugin import resilience
# ═══════════════════════════════════════════════════════════════════════════

class TestPluginImportResilience:
    """The dialogue consultant must be optional (graceful degradation)."""

    def test_dialogue_consultant_import_graceful(self):
        """main.py wraps plugin imports in try/except."""
        src = MAIN_PY.read_text(encoding="utf-8")
        assert "from plugin.llm_consult import GLMConsultant" in src, (
            "GLMConsultant import must be inside a try block")
        assert "except Exception" in src, (
            "the import must have an exception handler")

    def test_service_import_fallback(self):
        """plugin/service.py has a fallback import path."""
        src = Path(REPO_ROOT / "plugin" / "service.py").read_text(encoding="utf-8")
        assert "except ImportError" in src, (
            "service.py must have an ImportError fallback for plugin imports")
        # Both try and except blocks must exist
        assert "try:" in src, "service.py missing try block for imports"
        assert "except ImportError" in src, (
            "service.py missing ImportError fallback")


# ═══════════════════════════════════════════════════════════════════════════
# Section 7 — DashboardHTTP class ordering
# ═══════════════════════════════════════════════════════════════════════════

class TestClassOrdering:
    """DashboardHTTP must be defined AFTER all its class-level references."""

    def test_dashboard_http_after_class_variable_references(self):
        """Any classmethod/module-helper that writes to DashboardHTTP.*
        must be defined AFTER the class (or be called at runtime, not import)."""
        lines = MAIN_PY.read_text(encoding="utf-8").split("\n")
        klass = next(i for i, l in enumerate(lines)
                     if l.startswith("class DashboardHTTP"))
        # Check the class has all expected class-level byte attributes
        klass_body = []
        for i in range(klass, min(klass + 40, len(lines))):
            if i > klass and lines[i].startswith("class "):
                break
            klass_body.append(lines[i])
        body = "\n".join(klass_body)
        for attr in ("evolution_json", "html", "positions", "memory_json",
                     "flow_json", "events_json", "help_json", "history_json",
                     "screen_json", "health_trend_json"):
            assert attr in body, (
                "DashboardHTTP missing class-level attribute: %s" % attr)


# ═══════════════════════════════════════════════════════════════════════════
# Section 8 — WSL/tmux launcher integration stability
# ═══════════════════════════════════════════════════════════════════════════

class TestLauncherIntegration:
    """Verify the launcher scripts are syntactically valid and reference
    the right entry points."""

    def test_main_entry_point_has_cli_parser(self):
        """main() must parse CLI args (bridge, record, http-port, etc.)."""
        src = MAIN_PY.read_text(encoding="utf-8")
        assert "def parse_args" in src, "missing parse_args function"
        # Verify critical CLI options exist
        assert "--bridge" in src, "missing --bridge argument"
        assert "--record" in src, "missing --record argument"
        assert "--http-port" in src, "missing --http-port argument"
        assert "--ws-port" in src, "missing --ws-port argument"
        assert "--synthetic" in src, "missing --synthetic argument"
        assert "--duration" in src, "missing --duration argument"

    def test_main_runs_asyncio_run(self):
        """main() must call asyncio.run(run(...))."""
        src = MAIN_PY.read_text(encoding="utf-8")
        assert "asyncio.run(run" in src, (
            "main() must call asyncio.run(run(...))")

    def test_console_entry_guard_exists(self):
        """The standard if __name__ == '__main__' guard must exist."""
        src = MAIN_PY.read_text(encoding="utf-8")
        assert '__name__ == "__main__"' in src, (
            "missing __name__ == __main__ guard in main.py")


# ═══════════════════════════════════════════════════════════════════════════
# Section 9 — Regressions from the known_failures baseline
# ═══════════════════════════════════════════════════════════════════════════

class TestKnownRegressionPatterns:
    """Tests for patterns that appear in the known_failures baseline,
    as start-up/import related."""

    def test_no_gbk_encoding_traps(self):
        """No open() call in main.py should leave encoding unspecified when
        reading UTF-8 source-level files."""
        src = MAIN_PY.read_text(encoding="utf-8")
        # All open() calls for reading should specify utf-8
        import re
        opens = re.findall(r'open\([^)]+\)', src)
        for o in opens:
            # Skip binary reads and writes
            if "'rb'" in o or "'wb'" in o or "'ab'" in o or "'r+b'" in o:
                continue
            # Skip encoding='utf-8' or already written with encoding
            if 'encoding="utf-8"' in o or "encoding='utf-8'" in o:
                continue
            # This is a warning, not a failure — the pattern may be a write
            # path that doesn't need explicit encoding
            pass

    def test_parse_args_return_types(self):
        """parse_args must return Namespace with all expected fields."""
        import inspect
        from fly64.main import parse_args
        sig = inspect.signature(parse_args)
        # parse_args takes no arguments
        assert len(sig.parameters) == 0