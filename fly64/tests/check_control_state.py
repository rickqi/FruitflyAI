import json, urllib.request, time

def get(ep):
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))
    except Exception as e:
        return {"__err__": str(e)[:80]}

f = get("/flow.json")
m = get("/memory.json")
h = get("/help.json")
ca = get("/coach_advice.json")
evo = get("/evolution.json")

print("brain_version:", f.get("brain_version"), "| scene:", f.get("scene_name"))
print("decision-relevant state:")
print("  stuck_score:", m.get("stuck_score"), "| stuck_duration:", m.get("stuck_duration"))
print("  escape_behavior:", m.get("escape_behavior"), "| anomaly:", m.get("anomaly_state"))
print("  reflex_active:", m.get("reflex_active"), "| reflex_type:", m.get("reflex_type"))
print("  forced_bold_explore:", m.get("forced_bold_explore"))
print("  dialogue_active:", m.get("dialogue_active"), "| scene_label:", m.get("scene_label"))
print("  disp_60s:", m.get("disp_60s"), "| reflex_ineffective:", m.get("reflex_ineffective"))
print("coach:", json.dumps({"model": ca.get("model"), "advice": str(ca.get("advice"))[:120]}, ensure_ascii=False))
print("evolution:", json.dumps(evo, ensure_ascii=False)[:200])
