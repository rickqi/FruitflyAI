#!/bin/bash
# t2 live write-out verification: drive one supervised ServiceRunner cycle
# against the LIVE dashboard, answering the subagent file handshake.
set -u
cd /root/fly64
rm -f plugin/.consult_request.json plugin/.consult_response.json
python3 - <<'EOF'
import json, sys, threading, time
from pathlib import Path
sys.path.insert(0, "/root/fly64")
from plugin.llm_consult import GLMConsultant
from plugin.service import ServiceRunne
from plugin.strategy_writer import StrategyWrite

def fetcher(ep):
    from plugin.runner import fetch_json
    return fetch_json("http://127.0.0.1:8765", ep)

class LiveConsultant(GLMConsultant):
    def __init__(self):
        super().__init__(transport="subagent", timeout=30)
        self.model = "glm-5.3-flash"

writer = StrategyWriter()  # real skills/ paths
svc = ServiceRunner(dashboard_base="http://127.0.0.1:8765",
                    consultant=LiveConsultant(), writer=writer,
                    status_path=Path("/tmp/_t2_live_status.json"),
                    log=print)

def live_context():
    snap = svc.runner.fetch_snapshot()
    ctx = svc.runner.check_help_needed(snap)
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

svc.runner.check_help_needed = lambda snap: live_context()  # force consult path

def responder():
    # DSH-side: answer the file handshake like the host agent would.
    req = Path("plugin/.consult_request.json")
    for _ in range(20):
        if req.exists():
            break
        time.sleep(0.5)
    Path("plugin/.consult_response.json").write_text(json.dumps({
        "advice": "t2 验证：保持当前策略，注意前方平台。",
        "strategy": {"escape": {"stuck_threshold_s": 25.0}},
    }, ensure_ascii=False), encoding="utf-8")

t = threading.Thread(target=responder); t.start()
result = svc.run_cycle(); t.join()
print("cycle result:", json.dumps({k: v for k, v in result.items() if k != "context"}, ensure_ascii=False))
print("consulted:", result["consulted"], "strategy_written:", result["strategy_written"])
EOF
echo "=== files ==="
ls -la skills/active_strategy.json skills/coach_advice.json
echo "=== strategy content ==="
cat skills/active_strategy.json
echo "=== advice head ==="
head -c 400 skills/coach_advice.json; echo
echo "=== cleanup request/response ==="
rm -f plugin/.consult_request.json plugin/.consult_response.json
