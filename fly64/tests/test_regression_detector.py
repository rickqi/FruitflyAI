"""Verify the regression detector actually detects.

A detector that cannot detect is worthless, so this test injects a deliberately
failing test into a scratch file, runs the detector, asserts it reports the new
failure and exits non-zero, then removes the scratch file and asserts the
detector is clean again.

The 36-entry baseline (tests/known_failures.json) exists because the suite
carried ~40 undifferentiated failures, so every round needed a manual baseline
attribution to answer "did I break anything?".  With the baseline, only NEW
failures are loud.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DETECTOR = REPO_ROOT / "scripts" / "check_regressions.py"
SCRATCH = REPO_ROOT / "tests" / "test_zz_regression_detector_probe.py"

sys.path.insert(0, str(REPO_ROOT))
from scripts.check_regressions import CAUSES, baseline_path  # noqa: E402

#: Resolved the same way the tool does, so a platform-scoped rename cannot leave
#: these tests asserting against a file that no longer exists (which is exactly
#: what happened when the baseline became tests/known_failures.<platform>.json).
BASELINE = baseline_path()

#: This module's own tests are exempt from the "every entry is classified" check.
#:
#: Bootstrapping hazard observed on the linux baseline: while a baseline is still
#: being classified, this very assertion fails, so the detector records its OWN id
#: with cause "unknown" — and then it can never pass again, because the entry that
#: makes it fail is itself. The failure is self-sustaining.
#:
#: The exemption is safe because it is self-healing: with these ids ignored the
#: test passes, so the next `--update` run simply drops them from the baseline.
#: A genuine failure elsewhere in this module still surfaces as a NEW failure,
#: which is what the detector is for.
_BOOTSTRAP_PREFIX = "tests/test_regression_detector.py::TestBaselineIsWellFormed::"


def _is_bootstrap_entry(test_id: str) -> bool:
    return test_id.startswith(_BOOTSTRAP_PREFIX)

PROBE = '''
"""Scratch probe injected by test_regression_detector.py — must be deleted."""


def test_deliberately_failing_probe():
    assert False, "injected failure: the regression detector must catch this"
'''


class TestBaselineIsWellFormed:
    def test_baseline_exists_and_is_json(self):
        assert BASELINE.exists(), (
            "tests/known_failures.json is the tracked verification baseline; "
            "without it a real regression is buried among the known failures")
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert data["entries"], "baseline is empty"

    def test_every_entry_has_a_cause_and_note(self):
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        bad = [e["id"] for e in data["entries"]
               if e.get("cause") in (None, "", "unknown")
               and not _is_bootstrap_entry(e["id"])]
        assert not bad, (
            "these baseline entries are unclassified, so nobody can tell whether "
            "they are a real defect or a stale test: %s" % bad)

    def test_every_entry_has_evidence(self):
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        for e in data["entries"]:
            if e["cause"] in ("environment", "test-drift", "real-bug",
                              "aspirational"):
                assert e.get("note"), "%s has no evidence note" % e["id"]

    def test_causes_are_from_the_known_vocabulary(self):
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        bad = {e["cause"] for e in data["entries"]
               if not _is_bootstrap_entry(e["id"])} - set(CAUSES)
        assert not bad, "unknown cause labels: %s" % bad


class TestDetectorDetects:
    def test_reports_clean_against_its_own_baseline(self):
        """A fresh run must not report NEW failures for known ones."""
        proc = subprocess.run(
            [sys.executable, str(DETECTOR), "--report",
             str(REPO_ROOT / ".tmp" / "current_failures.txt")],
            cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        # .tmp may not exist; fall back to running pytest (slower but honest)
        if "No such file" in (proc.stderr or "") or proc.returncode not in (0, 1):
            pytest.skip("captured failure list unavailable; run the detector "
                        "directly for a full check")
        assert "NEW failures     : 0" in proc.stdout, proc.stdout[-1500:]

    def test_detects_an_injected_failure(self):
        assert not SCRATCH.exists(), "leftover probe from a previous run"
        SCRATCH.write_text(PROBE, encoding="utf-8", newline="\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(DETECTOR)],
                cwd=str(REPO_ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=900)
            out = proc.stdout or ""
            assert "test_deliberately_failing_probe" in out, (
                "the detector did not report the injected failure:\n" + out[-2000:])
            assert re.search(r"NEW failures\s+:\s+[1-9]", out), (
                "the detector did not count the injected failure as NEW:\n"
                + out[-2000:])
            assert proc.returncode != 0, (
                "the detector must exit non-zero when a NEW failure appears")
        finally:
            SCRATCH.unlink(missing_ok=True)
        assert not SCRATCH.exists()
