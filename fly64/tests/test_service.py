#!/usr/bin/env python3
"""Tests for the autonomy resident service (plugin/service.py)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(PLUGIN_DIR.parent))

from plugin.llm_consult import ConsultError, GLMConsultant  # noqa: E402
from plugin.service import (HealthChecker, ServiceRunner, local_diagnosis)  # noqa: E402
from plugin.strategy_writer import StrategyWriter  # noqa: E402


class FakeConsultant(GLMConsultant):
    """Consultant stub: configurable success/failure without any IO."""

    def __init__(self, fail=False, model="fake-model"):
        super().__init__(transport="subagent",
                         request_path=Path(tempfile.mkdtemp()) / "q.json",
                         response_path=Path(tempfile.mkdtemp()) / "r.json")
        self.fail = fail
        self.model = model
        self.calls = 0

    def consult(self, context, frame_b64=None):
        self.calls += 1
        if self.fail:
            raise ConsultError("subagent response not produced within 120s")
        return {"advice": "ok", "strategy": {"escape": {"stuck_threshold_s": 25.0}}}


def make_runner(tmp: Path, dashboard_ok=True, fail=False):
    evolution = {"v": 1} if dashboard_ok else None

    def fetcher(endpoint):
        if endpoint == "/evolution.json":
            return evolution
        if endpoint == "/help.json":
            return {"help_reason": "test_stuck", "scene_name": "bob"}
        if endpoint == "/memory.json":
            return {"stuck_duration": 200.0}
        return {}

    writer = StrategyWriter(strategy_path=tmp / "active_strategy.json",
                            advice_path=tmp / "coach_advice.json")
    consultant = FakeConsultant(fail=fail)
    svc = ServiceRunner(dashboard_base="http://127.0.0.1:1", interval=10,
                        bridge_path=str(tmp / "bridge.bin"),
                        consultant=consultant, writer=writer,
                        status_path=tmp / "service_status.json",
                        log=lambda m: None)
    svc.runner._fetcher = fetcher
    svc.health._fetcher = fetcher
    return svc, writer, consultant


class TestHealthChecker(unittest.TestCase):
    def test_dashboard_down(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            hc = HealthChecker("http://127.0.0.1:1",
                               bridge_path=str(tmp / "none.bin"),
                               fetcher=lambda ep: None)
            self.assertFalse(hc.check_dashboard()["ok"])
            self.assertFalse(hc.check_bridge()["ok"])  # missing bridge

    def test_bridge_freshness(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            bridge = tmp / "bridge.bin"
            bridge.write_bytes(b"x")
            hc = HealthChecker("http://x", bridge_path=str(bridge),
                               bridge_stale=60.0, fetcher=lambda ep: {})
            self.assertTrue(hc.check_bridge()["ok"])
            # Forge an old mtime -> stale.
            old = time.time() - 3600
            import os
            os.utime(bridge, (old, old))
            res = hc.check_bridge()
            self.assertFalse(res["ok"])

    def test_strategy_write_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            sp = tmp / "active_strategy.json"
            hc = HealthChecker("http://x", bridge_path=str(tmp / "b"),
                               strategy_path=sp, fetcher=lambda ep: {})
            self.assertTrue(hc.check_strategy_write()["ok"])  # no file yet
            sp.write_text("{}", encoding="utf-8")
            self.assertEqual(hc.check_strategy_write()["detail"], "observed")
            time.sleep(0.01)
            sp.write_text("{'a':1}", encoding="utf-8")
            self.assertEqual(hc.check_strategy_write()["detail"], "written")


class TestDegradedConsult(unittest.TestCase):
    def test_local_diagnosis_content(self):
        diag = local_diagnosis({"stuck_duration": 150.0,
                                "anomaly_state": "circling", "scene_name": "bob"})
        self.assertIn("local", diag["advice"])
        self.assertEqual(diag["strategy"], {})

    def test_fallback_on_consult_error(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc, writer, consultant = make_runner(tmp, fail=True)
            result = svc.run_cycle()
            self.assertTrue(result["consulted"])
            self.assertTrue(result["strategy_written"])
            self.assertTrue(svc.degraded)
            self.assertEqual(result["status"], "ok")
            advice = writer.load_advice()
            self.assertEqual(advice["model"], "local_diagnosis")
            self.assertIn("[local]", advice["advice"])

    def test_no_degradation_when_llm_ok(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc, writer, consultant = make_runner(tmp, fail=False)
            result = svc.run_cycle()
            self.assertFalse(svc.degraded)
            self.assertEqual(writer.load_advice()["model"], "fake-model")

    def test_strategy_file_written_on_consult(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc, writer, _ = make_runner(tmp, fail=False)
            svc.run_cycle()
            payload = writer.load_strategy()
            self.assertIsNotNone(payload)
            self.assertEqual(payload["source"], "fake-model")


class TestSupervision(unittest.TestCase):
    def test_failure_counter_and_alert(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc, _, _ = make_runner(tmp, dashboard_ok=False, fail=True)
            statuses = [svc.run_cycle()["status"] for _ in range(5)]
            self.assertTrue(all(s == "ok" for s in statuses))  # degraded is ok
            health = json.loads(
                (tmp / "service_status.json").read_text(encoding="utf-8"))
            self.assertFalse(health["health"]["dashboard"]["ok"])
            self.assertTrue(health["health"]["degraded"])

    def test_error_cycle_counts_failures(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc, _, _ = make_runner(tmp)
            # Force an exception inside the cycle: fetcher raises.
            def boom(ep):
                raise RuntimeError("dashboard exploded")
            svc.runner._fetcher = boom
            result = svc.run_cycle()
            self.assertEqual(result["status"], "error")
            self.assertEqual(svc.consecutive_failures, 1)
            self.assertFalse(result["health"]["alert"])

    def test_status_file_written(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc, _, _ = make_runner(tmp)
            svc.run_cycle()
            data = json.loads(
                (tmp / "service_status.json").read_text(encoding="utf-8"))
            self.assertIn("health", data)
            self.assertIn("cycle", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
