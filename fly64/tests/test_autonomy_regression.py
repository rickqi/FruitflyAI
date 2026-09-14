#!/usr/bin/env python3
"""Regression tests for the autonomy substrate deployment contract (t2).

Covers what test_service.py does not:
  * VERSION triple-sync contract (agent.md rule 8)
  * StrategyWriter atomic-write guarantee (no partial reads, no tmp litter)
  * watchdog.sh restart + failure-counter logic (bash sandbox, POSIX only)
  * consolidate.sh institutional linkage to the autonomy service
  * ServiceRunner.run_forever bounded loop (>=3 cycles for soak verification)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugin.service import ServiceRunner  # noqa: E402
from plugin.strategy_writer import StrategyWriter  # noqa: E402


def _make_runner(tmp: Path, interval: float = 0.01):
    def fetcher(endpoint):
        if endpoint == "/evolution.json":
            return {"v": 1}
        if endpoint == "/help.json":
            return {"help_reason": "test_stuck", "scene_name": "bob"}
        if endpoint == "/memory.json":
            return {"stuck_duration": 100.0}
        return {}

    class _Consultant:
        model = "fake-model"

        def consult(self, context, frame_b64=None):
            return {"advice": "ok", "strategy": {}}

    writer = StrategyWriter(strategy_path=tmp / "active_strategy.json",
                            advice_path=tmp / "coach_advice.json")
    svc = ServiceRunner(dashboard_base="http://127.0.0.1:1", interval=interval,
                        bridge_path=str(tmp / "bridge.bin"),
                        consultant=_Consultant(), writer=writer,
                        status_path=tmp / "service_status.json",
                        log=lambda m: None)
    svc.runner._fetcher = fetcher
    svc.health._fetcher = fetcher
    return svc


# ── VERSION triple-sync contract (agent.md rule 8) ─────────────────────────

class TestVersionContract(unittest.TestCase):
    def test_skill_version_mirror(self):
        sys.path.insert(0, str(ROOT))
        from fly64 import main as brain_main
        from skills import evolution_skill
        self.assertEqual(brain_main.SKILL_VERSION, evolution_skill.SKILL_VERSION,
                         "main.py SKILL_VERSION must mirror skills/evolution_skill.py")

    def test_skills_md_documented_version(self):
        sys.path.insert(0, str(ROOT))
        from skills import evolution_skill
        text = (ROOT / "skills" / "skills.md").read_text(encoding="utf-8")
        self.assertIn(evolution_skill.SKILL_VERSION, text,
                      "skills/skills.md must document the current SKILL_VERSION")

    def test_brain_version_in_skills_md_round_table(self):
        sys.path.insert(0, str(ROOT))
        from fly64 import main as brain_main
        text = (ROOT / "skills" / "skills.md").read_text(encoding="utf-8")
        self.assertIn(brain_main.BRAIN_VERSION, text,
                      "skills/skills.md round table must reference current BRAIN_VERSION")


# ── StrategyWriter atomic write ─────────────────────────────────────────────

class TestAtomicWrite(unittest.TestCase):
    def test_no_tmp_litter_and_valid_json(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            w = StrategyWriter(strategy_path=tmp / "s.json",
                               advice_path=tmp / "a.json")
            w.write_strategy({"escape": {"stuck_threshold_s": 30.0}},
                             advice="hi", source="t")
            w.write_advice("hi", model="t")
            self.assertEqual(list(tmp.glob("*.tmp")), [])
            json.loads((tmp / "s.json").read_text(encoding="utf-8"))
            json.loads((tmp / "a.json").read_text(encoding="utf-8"))

    def test_repeated_writes_always_parse(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            w = StrategyWriter(strategy_path=tmp / "s.json",
                               advice_path=tmp / "a.json")
            for i in range(20):
                w.write_strategy({"escape": {"stuck_threshold_s": 1.0 + i}},
                                 advice=f"m{i}", source="t")
                payload = w.load_strategy()
                self.assertIsNotNone(payload)
                self.assertAlmostEqual(
                    payload["escape"]["stuck_threshold_s"], 1.0 + i)

    def test_advice_history_capped(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            w = StrategyWriter(strategy_path=tmp / "s.json",
                               advice_path=tmp / "a.json", history_limit=5)
            for i in range(9):
                w.write_advice(f"a{i}", model="t")
            data = w.load_advice()
            self.assertEqual(len(data["history"]), 5)
            self.assertEqual(data["history"][-1]["advice"], "a8")


# ── watchdog.sh restart / failure-counter logic (POSIX only) ────────────────

class TestWatchdog(unittest.TestCase):
    def setUp(self):
        if not os.path.exists("/proc") or shutil.which("bash") is None:
            self.skipTest("watchdog sandbox test requires POSIX bash (/proc)")

    def _sandbox(self, tmp: Path) -> Path:
        """Copy watchdog.sh with PROJECT redirected into the sandbox."""
        script = (ROOT / "plugin" / "watchdog.sh").read_text(encoding="utf-8")
        script = script.replace("PROJECT=/root/fly64", f"PROJECT={tmp}")
        path = tmp / "watchdog.sh"
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
        (tmp / "plugin").mkdir(exist_ok=True)
        return path

    def test_restarts_dead_service(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            wd = self._sandbox(tmp)
            # A stand-in *dead* service: pid file points at a killed process.
            sleeper = subprocess.Popen(["sleep", "30"])
            (tmp / "plugin" / "fly64-service.pid").write_text(
                str(sleeper.pid), encoding="utf-8")
            sleeper.kill()
            sleeper.wait()
            (tmp / "plugin" / "service.py").write_text(
                "import os, sys, time, pathlib\n"
                f"pathlib.Path({str(tmp / 'plugin' / 'fly64-service.pid')!r})"
                ".write_text(str(os.getpid()))\n"
                "time.sleep(30)\n", encoding="utf-8")
            subprocess.run(["bash", str(wd)], check=True,
                           timeout=60, capture_output=True)
            pid = int((tmp / "plugin" / "fly64-service.pid")
                      .read_text(encoding="utf-8").strip())
            os.kill(pid, 0)  # alive
            log = (tmp / "plugin" / "watchdog.log").read_text(encoding="utf-8")
            self.assertIn("started pid=", log)
            self.assertEqual((tmp / "plugin" / ".watchdog_fails")
                             .read_text(encoding="utf-8").strip(), "0")
            sleeper.kill()

    def test_counts_consecutive_failures_and_alerts(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            wd = self._sandbox(tmp)
            # No pid file -> not alive; stub start fails (python exits 1).
            (tmp / "plugin" / "service.py").write_text(
                "import sys\nsys.exit(1)\n", encoding="utf-8")
            for _ in range(3):
                subprocess.run(["bash", str(wd)], check=True,
                               timeout=60, capture_output=True)
            fails = int((tmp / "plugin" / ".watchdog_fails")
                        .read_text(encoding="utf-8").strip())
            self.assertGreaterEqual(fails, 3)
            log = (tmp / "plugin" / "watchdog.log").read_text(encoding="utf-8")
            self.assertIn("ALERT", log)

    def test_healthy_service_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            wd = self._sandbox(tmp)
            sleeper = subprocess.Popen(["sleep", "30"])
            (tmp / "plugin" / "fly64-service.pid").write_text(
                str(sleeper.pid), encoding="utf-8")
            r = subprocess.run(["bash", str(wd)], check=True,
                               timeout=60, capture_output=True)
            self.assertEqual(r.returncode, 0)
            self.assertFalse((tmp / "plugin" / "watchdog.log").exists())
            sleeper.kill()


# ── consolidate.sh institutional linkage ────────────────────────────────────

class TestConsolidateLinkage(unittest.TestCase):
    def test_consolidate_restarts_autonomy_service(self):
        text = (ROOT / "scripts" / "consolidate.sh").read_text(encoding="utf-8")
        self.assertIn("-m plugin.service", text)
        self.assertIn("fly64-service.pid", text)

    def test_watchdog_targets_service(self):
        text = (ROOT / "plugin" / "watchdog.sh").read_text(encoding="utf-8")
        self.assertIn("-m plugin.service", text)
        self.assertIn("fly64-service.pid", text)
        self.assertIn("ALERT", text)

    def test_deploy_doc_exists(self):
        self.assertTrue((ROOT / "plugin" / "DEPLOY_AUTONOMY.md").exists())


# ── bounded main loop: >=3 cycles ───────────────────────────────────────────

class TestBoundedLoop(unittest.TestCase):
    def test_run_forever_completes_three_cycles(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc = _make_runner(tmp)
            t0 = time.time()
            svc.run_forever(max_cycles=3)
            self.assertLess(time.time() - t0, 10)
            self.assertEqual(svc.runner.cycles, 3)
            data = json.loads((tmp / "service_status.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(data["cycle"], 3)
            self.assertEqual(data["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
