import json, urllib.request, os, time

def get(ep):
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))
    except Exception as e:
        return {"__err__": str(e)[:60]}

def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:
        return {"__err__": str(e)[:60]}

print("=== 1) autonomy service ===")
ss = jload("/root/fly64/plugin/service_status.json")
print(json.dumps({k: ss.get(k) for k in ("cycle","ts","status","consulted","degraded","consecutive_failures")},
                 ensure_ascii=False))
h = ss.get("health", {})
print("health:", json.dumps({k: (h.get(k) or {}).get("ok", h.get(k)) for k in ("dashboard","bridge","strategy_write")}, ensure_ascii=False))
pid = open("/root/fly64/plugin/fly64-service.pid").read().strip() if os.path.exists("/root/fly64/plugin/fly64-service.pid") else "?"
alive = os.path.exists(f"/proc/{pid}")
print(f"service pid={pid} alive={alive} | uptime_cycles={ss.get('cycle')}")

print("=== 2) watchdog ===")
wd = "/root/fly64/plugin/watchdog.log"
if os.path.exists(wd):
    lines = open(wd).read().strip().splitlines()
    print(f"log lines: {len(lines)} | last: {lines[-1][:120] if lines else '-'}")
else:
    print("no watchdog.log (no restarts needed)")

print("=== 3) brain ===")
f = get("/flow.json")
print("brain_version:", f.get("brain_version"), "| scene:", f.get("scene_name"))
m = get("/memory.json")
print("motion:", json.dumps({k: m.get(k) for k in
    ("stuck_score","stuck_duration","loop_score","anomaly_state","escape_behavior",
     "reflex_active","reflex_ineffective","disp_60s","forced_bold_explore",
     "dialogue_active","health_score","coverage_pct")}, ensure_ascii=False))

print("=== 4) evolution iterations ===")
e = get("/evolution.json")
its = e.get("iterations", [])
print("iterations recorded:", len(its), "| brain badge:", e.get("brain_version"))
for it in its[-3:]:
    print(f"  #{it.get('iter')} {it.get('time')} trigger={it.get('trigger')} caps={it.get('capabilities')}")

print("=== 5) coach advice (latest) ===")
ca = get("/coach_advice.json")
print("model:", ca.get("model"), "| ts:", ca.get("advice_ts"))
print("advice:", str(ca.get("advice"))[:150])

print("=== 6) strategy hot-reload file ===")
st = jload("/root/fly64/skills/active_strategy.json")
print(json.dumps(st, ensure_ascii=False)[:300])
