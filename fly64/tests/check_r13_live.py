import json, urllib.request
f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json", timeout=5))
m = json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json", timeout=5))
print("scene:", f.get("scene_name"))
print("memory scene_label:", m.get("scene_label"), "| dialogue_active:", m.get("dialogue_active"))
print("stuck:", m.get("stuck_duration"), "| reflex_ineffective:", m.get("reflex_ineffective"))
