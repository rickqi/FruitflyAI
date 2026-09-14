import json, os, glob, urllib.request

def get(ep):
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))
    except Exception as e:
        return {"__err__": str(e)[:80]}

ss = get("/plugin/service_status.json") if False else None
# read service status + advice straight from WSL fs via /root path? Not http.
print("== env (brain service process) ==")
print("FLY64_LLM_BASE_URL set?", bool(os.environ.get("FLY64_LLM_BASE_URL")))
print("== /coach_advice.json ==")
print(json.dumps(get("/coach_advice.json"), ensure_ascii=False)[:400])
print("== /help.json ==")
print(json.dumps(get("/help.json"), ensure_ascii=False)[:200])
m = get("/memory.json")
print("memory:", {k: m.get(k) for k in ("stuck_duration","reflex_active","reflex_ineffective","disp_60s","anomaly_state")})
