import json, urllib.request

for ep in ("/help.json", "/coach_advice.json", "/active_strategy.json"):
    data = json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))
    print(f"=== {ep} ===")
    print(json.dumps(data, ensure_ascii=False, indent=1)[:800])
    print()