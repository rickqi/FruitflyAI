import json, urllib.request
for ep in ("flow.json", "memory.json", "bridge-status.json"):
    try:
        d = json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))
        print(ep, "brain_version:", d.get("brain_version"))
    except Exception as e:
        print(ep, "err:", e)
