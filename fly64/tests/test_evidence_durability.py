"""PIN tests: the evidence base must survive tests and stale mirrors.

Two incidents motivate these tests (t9):

1. A test session wrote into the LIVE evidence paths, replacing 45 real coach
   outcomes with 30 synthetic rows.  ``*.jsonl`` is git-ignored, so nothing
   could restore it.
2. The live corpus was then found to have shrunk with no truncating code path:
   a Windows↔WSL sync had copied a stale mirror of the file over the richer
   runtime copy.

So: tests must be redirected off production paths, and the corpus must detect
shrinkage and restore itself from a snapshot.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin import coach_outcomes as co  # noqa: E402


class TestTestsNeverTouchProductionEvidence:
    def test_evidence_dir_override_is_active_under_pytest(self):
        assert os.environ.get("FLY64_EVIDENCE_DIR"), (
            "conftest.py did not set FLY64_EVIDENCE_DIR — tests will write "
            "into the live corpus")

    def test_paths_point_outside_the_working_tree(self):
        root = Path(os.environ["FLY64_EVIDENCE_DIR"]).resolve()
        for p in (co.PENDING_PATH, co.OUTCOMES_PATH, co.CURRICULUM_PATH):
            assert root in Path(p).resolve().parents, (
                f"{p} is not redirected into the test evidence dir")

    def test_live_corpus_path_is_not_the_production_path(self):
        prod = (co.PLUGIN_DIR.parent / "skills" / "coach_outcomes.jsonl").resolve()
        assert Path(co.OUTCOMES_PATH).resolve() != prod, (
            "tests are still pointed at the production corpus")

    def test_binding_store_is_also_redirected(self):
        from fly64 import instinct_bindings as ib
        root = Path(os.environ["FLY64_EVIDENCE_DIR"]).resolve()
        assert root in Path(ib.BINDINGS_PATH).resolve().parents

    def test_appending_does_not_create_the_production_corpus(self):
        prod = co.PLUGIN_DIR.parent / "skills" / "coach_outcomes.jsonl"
        before = prod.stat().st_mtime if prod.exists() else None
        co.append_outcome({"t": "isolation-check"})
        after = prod.stat().st_mtime if prod.exists() else None
        assert before == after, "a test append touched the production corpus"
        assert Path(co.OUTCOMES_PATH).exists(), "the redirected corpus was not used"


class TestCorpusShrinkGuard:
    def _fill(self, path, n, tag="real"):
        for i in range(n):
            co.append_outcome({"i": i, "tag": tag}, path)

    def test_shrink_is_detected_and_restored(self, tmp_path):
        path = tmp_path / "o.jsonl"
        self._fill(path, 10)
        assert co._line_count(path) == 10
        # simulate a stale mirror overwriting the richer runtime copy
        path.write_text("\n".join(json.dumps({"i": i, "tag": "stale"})
                                  for i in range(3)) + "\n", encoding="utf-8")
        assert co._line_count(path) == 3
        report = co.guard_outcomes(path)
        assert report["restored"] is True
        assert co._line_count(path) == 10, "corpus was not restored from snapshot"
        assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["tag"] == "real"

    def test_guard_is_noop_when_corpus_grows(self, tmp_path):
        path = tmp_path / "o.jsonl"
        self._fill(path, 5)
        report = co.guard_outcomes(path)
        assert report["restored"] is False
        assert co._line_count(path) == 5

    def test_append_survives_a_clobber_and_keeps_evidence(self, tmp_path):
        path = tmp_path / "o.jsonl"
        self._fill(path, 10)
        path.write_text("", encoding="utf-8")          # total wipe
        co.append_outcome({"i": "new"}, path)
        rows = co.load_outcomes(path)
        assert len(rows) >= 11, "evidence was lost instead of restored"
        assert rows[-1]["i"] == "new"

    def test_high_water_mark_is_tracked(self, tmp_path):
        path = tmp_path / "o.jsonl"
        self._fill(path, 7)
        hwm = path.with_name(path.name + ".hwm")
        assert int(hwm.read_text(encoding="utf-8").strip()) == 7

    def test_guard_on_missing_file_is_not_an_error(self, tmp_path):
        report = co.guard_outcomes(tmp_path / "nope.jsonl")
        assert report["restored"] is False and report["current"] == 0
