import json, urllib.request, time
m = json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json", timeout=5))
print("reflex_ineffective:", m.get("reflex_ineffective"),
      "| disp_60s:", m.get("disp_60s"),
      "| reflex_active:", m.get("reflex_active"),
      "| stuck:", m.get("stuck_duration"))
f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json", timeout=5))
print("brain_version:", f.get("brain_version"))
