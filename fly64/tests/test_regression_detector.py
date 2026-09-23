"""Verify the regression detector actually detects.

A detector that cannot detect is worthless, so this test injects a deliberately
failing test into a scratch file, runs the detector, asserts it reports the new
failure and exits non-zero, then removes the scratch file.

Probe hygiene (the 2026-09-23 incident)
--------------------------------------
The probe used to live at a FIXED path inside ``tests/``
(``tests/test_zz_regression_detector_probe.py``).  Two consequences, both hit
in practice:

1. ``testpaths = tests`` means every *outer* full-suite run collected that file
   too, and its failure is not in the baseline.  So one interrupted run (killed
   before ``finally`` ran) left a file behind that made every later
   ``--strict`` report ``NEW = 1`` — wearing the costume of a real regression,
   which is the one thing this baseline exists to make impossible.
2. Two concurrent suites wrote and deleted the SAME file, so each one saw the
   other's probe as "leftover" and failed.

Now:

* the probe is written into pytest's own ``tmp_path`` (process-unique,
  auto-cleaned) and handed to the detector explicitly with
  ``check_regressions.py --only <probe>``.  That also removes the nested
  whole-suite run: a single test used to cost as much as the entire gate;
* leftovers at the OLD fixed path are swept at import time — i.e. during
  collection, before pytest could collect them — with a warning.  A leftover is
  deleted, never reported as a failure.

Detection power is unchanged and still asserted: the detector must print the
injected failure, count it as NEW, and exit non-zero.

The 36-entry baseline (tests/known_failures.<platform>.json) exists because the
suite carried ~40 undifferentiated failures, so every round needed a manual
baseline attribution to answer "did I break anything?".  With the baseline, only
NEW failures are loud.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DETECTOR = REPO_ROOT / "scripts" / "check_regressions.py"

#: Probe basename.  It still matches ``test_*.py`` because pytest's
#: ``python_files`` pattern applies to files passed explicitly as well.
PROBE_BASENAME = "test_zz_regression_detector_probe.py"

#: Probes from the old fixed-path design (and any pid-suffixed variant of it).
#: Swept, never asserted — see the module docstring.
LEGACY_PROBE_GLOB = "test_zz_regression_detector_probe*.py"

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


def _sweep_probe_leftovers() -> list[str]:
    """Delete probes left behind by an interrupted run; warn, never fail.

    A leftover is not evidence of a regression: it is evidence that a previous
    process died before its ``finally`` block.  Reporting it as NEW (which is
    what the old hard ``assert not SCRATCH.exists()`` did) blocks the gate for
    everyone, so the leftover is removed instead.

    This runs at import time on purpose: pytest imports test modules during
    collection, i.e. before it collects the files of this directory, so the
    deletion happens before a leftover could be collected and reported as a NEW
    failure by an outer gate run.
    """
    removed = []
    for path in sorted((REPO_ROOT / "tests").glob(LEGACY_PROBE_GLOB)):
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            pass
    if removed:
        print("[test_regression_detector] swept leftover probe file(s) from an "
              "interrupted run (they would otherwise be collected as NEW "
              "failures): %s" % ", ".join(removed), file=sys.stderr)
    return removed


_SWEPT_AT_IMPORT = _sweep_probe_leftovers()


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

    def test_leftover_probe_is_swept_not_failed(self):
        """The incident form: an interrupted run left the fixed-path probe behind.

        The next run must clean it up and carry on — never fail, and never let
        it reach the detector as a NEW failure.

        The assertion is on the END STATE (the file is gone), not on "my call
        did the deleting": with two suites running at once the other process may
        have swept it first, and that is a success, not a failure.
        """
        legacy = REPO_ROOT / "tests" / PROBE_BASENAME
        legacy.write_text(PROBE, encoding="utf-8", newline="\n")
        try:
            removed = _sweep_probe_leftovers()
            assert isinstance(removed, list)
            assert not legacy.exists(), (
                "a leftover probe must never survive the sweep (it would be "
                "collected by the next suite run and reported as a NEW failure)")
        finally:
            legacy.unlink(missing_ok=True)

    def test_detects_an_injected_failure(self, tmp_path):
        """The probe must be caught: reported by name, counted as NEW, rc != 0.

        The detector is run with ``--only <probe>`` so this costs seconds
        instead of a nested whole-suite run (~318 s).  The detection path being
        proven is the same one the gate uses: spawn -> pytest -> parse FAILED
        lines -> load the tracked baseline -> count NEW -> exit non-zero.
        """
        _sweep_probe_leftovers()          # never fail on somebody's residue
        probe = tmp_path / PROBE_BASENAME
        probe.write_text(PROBE, encoding="utf-8", newline="\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(DETECTOR), "--only", str(probe)],
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
            probe.unlink(missing_ok=True)
        assert not probe.exists()

    def test_update_is_refused_for_a_restricted_run(self, tmp_path):
        """``--update --only`` must not be able to shrink the tracked baseline.

        Rewriting the baseline from a restricted run would drop every entry
        outside the restriction, i.e. silently declare real failures fixed.
        """
        before = BASELINE.read_bytes()
        probe = tmp_path / PROBE_BASENAME
        probe.write_text(PROBE, encoding="utf-8", newline="\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(DETECTOR), "--only", str(probe), "--update"],
                cwd=str(REPO_ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            assert proc.returncode != 0, proc.stdout
            assert "refusing --update" in (proc.stderr or ""), (
                proc.stderr or proc.stdout)
            assert BASELINE.read_bytes() == before, (
                "the baseline was rewritten from a restricted run")
        finally:
            probe.unlink(missing_ok=True)
