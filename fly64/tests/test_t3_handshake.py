import sys, json, time, threading
sys.path.insert(0, "/root/fly64")
from plugin.llm_consult import GLMConsultant, RESPONSE_PATH

def dsh_responder():
    """Simulates the DSH agent: watches for the request and answers ~4s later."""
    time.sleep(4)
    for _ in range(20):
        if RESPONSE_PATH.parent.exists():
            RESPONSE_PATH.write_text(json.dumps({
                "advice": "[DSH 教官] 演示：检测到 micro_loop 零位移，向 opening 扇区方向突围 2.5s",
                "strategy": {"exploration": {"turn_bias": 0.4}},
            }, ensure_ascii=False), encoding="utf-8")
            return
        time.sleep(1)

t = threading.Thread(target=dsh_responder, daemon=True)
t.start()
sub = GLMConsultant(transport="subagent")
out = sub.consult({"kind": "test", "stuck_duration": 100.0}, frame_b64=None)
print("T3 handshake OK. advice:", json.dumps(out.get("advice", ""), ensure_ascii=False))
print("T3 strategy:", json.dumps(out.get("strategy", {}), ensure_ascii=False))
