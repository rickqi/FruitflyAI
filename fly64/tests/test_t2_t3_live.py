import sys, json, time
sys.path.insert(0, "/root/fly64")
from plugin.llm_consult import GLMConsultant, RESPONSE_PATH
from plugin.llm_consult import build_consult_request

# ── T2: real HTTP consult against GLM (validates key/model/endpoint) ──
c = GLMConsultant(transport="http")
ctx = {"kind": "escalation_test", "scene_name": "室内 #ab12", "stuck_duration": 323.0,
       "anomaly_state": "micro_loop", "health_score": 0.5,
       "diagnosis": "micro_loop reflex produces zero displacement at locked door"}
try:
    out = c.consult(ctx, frame_b64=None)
    print("T2 HTTP OK. advice:", json.dumps(out.get("advice", ""), ensure_ascii=False)[:200])
    print("T2 strategy:", json.dumps(out.get("strategy", {}), ensure_ascii=False)[:200])
except Exception as e:
    print("T2 HTTP FAILED:", str(e)[:300])

# ── T3: subagent file handshake — DSH agent (me) responds as the coach ──
RESPONSE_PATH.parent.mkdir(parents=True, exist_ok=True)
RESPONSE_PATH.write_text(json.dumps({
    "advice": "[DSH] 教官演示响应：向 opening_score 高的扇区方向突围 2.5s，若零位移则跳转+转向90°换面",
    "strategy": {"fallen_recovery": {"mode": "mirror", "climb_period": 3.5, "persist_seconds": 1.5}},
}, ensure_ascii=False), encoding="utf-8")
sub = GLMConsultant(transport="subagent")
ctx2 = {"kind": "escalation_test", "scene_name": "室内 #ab12", "stuck_duration": 100.0}
out2 = sub.consult(ctx2, frame_b64=None)
print("T3 handshake OK. advice:", json.dumps(out2.get("advice", ""), ensure_ascii=False)[:200])
RESPONSE_PATH.unlink(missing_ok=True)
print("handshake response file consumed & cleaned")
