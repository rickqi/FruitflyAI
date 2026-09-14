import json, urllib.request, os

for p in ("/root/fly64/skills/coach_advice.json",
          "/root/fly64/skills/active_strategy.json",
          "/root/fly64/plugin/.consult_request.json",
          "/root/fly64/plugin/.consult_response.json"):
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"{p}: EXISTS {sz}B")
    else:
        print(f"{p}: MISSING")

try:
    d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/coach_advice.json", timeout=5))
    print("dashboard /coach_advice.json:", json.dumps(d, ensure_ascii=False)[:300])
except Exception as e:
    print("dashboard /coach_advice.json error:", e)

req = "/root/fly64/plugin/.consult_request.json"
if os.path.exists(req):
    d = json.load(open(req, encoding="utf-8"))
    print("request keys:", list(d.keys())[:8])
    ctx = d.get("context") or d.get("messages", [{}])
    print("request context snippet:", json.dumps(d.get("context", d), ensure_ascii=False)[:300])
