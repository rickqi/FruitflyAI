#!/usr/bin/env python3
"""t2 live write-out verification: one supervised cycle against the LIVE
dashboard, answering the subagent file handshake as the DSH responder."""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "/root/fly64")
from plugin.llm_consult import GLMConsultant
from plugin.service import ServiceRunner
from plugin.strategy_writer import StrategyWriter


class LiveConsultant(GLMConsultant):
    def __init__(self):
        super().__init__(transport="subagent", timeout=30)
        self.model = "glm-5.3-flash"


writer = StrategyWriter()  # real skills/ paths
svc = ServiceRunner(dashboard_base="http://127.0.0.1:8765",
                    consultant=LiveConsultant(), writer=writer,
                    status_path=Path("/tmp/_t2_live_status.json"),
                    log=print)


_orig_check = svc.runner.check_help_needed


def live_context():
    snap = svc.runner.fetch_snapshot()
    ctx = _orig_check(snap)
    if ctx is None:  # healthy game: synthesize the escalation context
        mem = snap.get("memory") or {}
        ctx = {"help_reason": "t2_live_writeout_check",
               "scene_name": mem.get("scene_name", "?"),
               "position": mem.get("position") or {},
               "diagnosis": "deployment verification probe",
               "stuck_duration": float(mem.get("stuck_duration", 0.0)),
               "anomaly_state": mem.get("anomaly_state", "?"),
               "health_score": float(mem.get("health_score", 1.0))}
    return ctx


svc.runner.check_help_needed = lambda snap: live_context()


def responder():
    req = Path("/root/fly64/plugin/.consult_request.json")
    for _ in range(20):
        if req.exists():
            break
        time.sleep(0.5)
    Path("/root/fly64/plugin/.consult_response.json").write_text(
        json.dumps({"advice": "t2 验证：保持当前策略，注意前方平台。",
                    "strategy": {"escape": {"stuck_threshold_s": 25.0}}},
                   ensure_ascii=False), encoding="utf-8")


t = threading.Thread(target=responder)
t.start()
result = svc.run_cycle()
t.join()
slim = {k: v for k, v in result.items() if k != "context"}
print("cycle result:", json.dumps(slim, ensure_ascii=False))
print("consulted:", result["consulted"],
      "strategy_written:", result["strategy_written"])
