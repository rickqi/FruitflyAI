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


class TestHelperIsCallableAfterImport:
    def test_helper_is_idempotent(self):
        sys.path.insert(0, str(REPO_ROOT))
        import fly64.main as m
        m._load_evolution_history()      # must not raise
        m._load_evolution_history()
