import json, urllib.request

def get(ep):
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))
    except Exception as e:
        return {"__err__": str(e)}

h = get("help.json")
print("help.json:", json.dumps(h, ensure_ascii=False)[:300])
m = get("memory.json")
print("reflex_active:", m.get("reflex_active"), "| reflex_type:", m.get("reflex_type"),
      "| stuck_duration:", m.get("stuck_duration"), "| anomaly_state:", m.get("anomaly_state"))
print("keys:", [k for k in m.keys()][:30])
