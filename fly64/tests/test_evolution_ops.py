"""PIN tests: P2 ops tooling - funnel, pattern drafts, single-instance lock."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills import pattern_drafts as pd  # noqa: E402
from skills.evolution_skill import (acquire_loop_lock, compute_funnel,  # noqa: E402
                                    release_loop_lock)


def _fix_entry(fid, pid, effective):
    """A complete FixEntry-compatible dict (all required dataclass fields)."""
    return {"id": fid, "pattern_id": pid, "pattern_name": pid,
            "pattern_version": "1.0.0", "diagnosis": "d", "fix_template": "t",
            "severity": "high", "applied_at": "2026-09-16T00:00:00+00:00",
            "version": 1, "effective": effective, "reverted": False}


class TestFunnel:
    def _log(self, tmp_path, rows):
        p = tmp_path / "evolution_log.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return p

    def _catalog(self, tmp_path, fixes):
        p = tmp_path / "fix_catalog.json"
        p.write_text(json.dumps({"fixes": fixes}), encoding="utf-8")
        from skills.evolution_skill import FixCatalog
        return FixCatalog(path=p)

    def test_funnel_counts_and_rates(self, tmp_path):
        rows = []
        for i in range(10):
            findings = [{"id": "a", "severity": "high"}] if i % 2 == 0 else []
            rows.append({"iteration": i, "findings": findings})
        log = self._log(tmp_path, rows)
        cat = self._catalog(tmp_path, [
            _fix_entry("fix_0001", "a", True),
            _fix_entry("fix_0002", "a", False),
        ])
        f = compute_funnel(log_path=log, catalog=cat)
        assert f["iterations"] == 10
        assert f["findings_fired"] == 5
        assert f["fixes_recorded"] == 2
        assert f["fixes_verified"] == 2
        assert f["fixes_effective"] == 1
        assert f["rate_verified_to_effective"] == 0.5

    def test_missing_log_gives_zeros(self, tmp_path):
        f = compute_funnel(log_path=tmp_path / "nope.jsonl",
                           catalog=self._catalog(tmp_path, []))
        assert f["iterations"] == 0 and f["findings_fired"] == 0


class TestDrafts:
    def test_stubborn_detection_and_effective_skip(self, tmp_path, monkeypatch):
        rows = []
        for i in range(100):
            ids = [{"id": "stubborn_x", "severity": "high"}]
            if i % 2 == 0:
                ids.append({"id": "healed_y", "severity": "low"})
            rows.append({"iteration": i, "findings": ids})
        log = tmp_path / "log.jsonl"
        log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        cat = tmp_path / "fix_catalog.json"
        cat.write_text(json.dumps({"fixes": [
            _fix_entry("fix_0001", "healed_y", True)]}), encoding="utf-8")
        monkeypatch.setattr(pd, "LOG_PATH", log)
        monkeypatch.setattr(pd, "CATALOG_PATH", cat)
        result = pd.build_drafts(window=100, min_presence=0.10)
        stubborn = [d.get("pattern_id") for d in result["drafts"]
                    if d["type"] == "stubborn_pattern"]
        assert "stubborn_x" in stubborn
        assert "healed_y" not in stubborn

    def test_combo_detection(self, tmp_path, monkeypatch):
        rows = []
        for i in range(30):
            rows.append({"iteration": i, "findings": [
                {"id": "a"}, {"id": "b"}]})
        log = tmp_path / "log.jsonl"
        log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        monkeypatch.setattr(pd, "LOG_PATH", log)
        monkeypatch.setattr(pd, "CATALOG_PATH", tmp_path / "none.json")
        result = pd.build_drafts(window=30, min_presence=0.99)
        combos = [d for d in result["drafts"] if d["type"] == "co_occurring_pair"]
        assert any(d["pair"] == ["a", "b"] and d["co_occurrences"] == 30
                   for d in combos)


class TestLock:
    def test_acquire_release_reacquire(self, tmp_path):
        lock = tmp_path / ".lock"
        assert acquire_loop_lock(lock) == lock
        assert acquire_loop_lock(lock) is None
        release_loop_lock(lock)
        assert acquire_loop_lock(lock) == lock
        release_loop_lock(lock)

    def test_stale_lock_broken(self, tmp_path):
        lock = tmp_path / ".lock"
        lock.write_text("999999999", encoding="utf-8")
        assert acquire_loop_lock(lock) == lock

    def test_current_pid_alive_check(self, tmp_path):
        lock = tmp_path / ".lock"
        lock.write_text(str(os.getpid()), encoding="utf-8")
        assert acquire_loop_lock(lock) is None