import json, urllib.request
print("llm_env_loader present:", open("/root/fly64/plugin/llm_consult.py").read().count("_load_llm_env") > 0)
m = json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json", timeout=5))
print("ctrl telemetry:", {k: m.get(k) for k in
    ("stuck_score", "stuck_duration", "coverage_rate", "scene_change_rate", "visited_cells") if k in m})
main_src = open("/root/fly64/fly64/main.py").read()
print("WSL main.py BRAIN_VERSION:", main_src.split('BRAIN_VERSION = "')[1].split('"')[0])
print("WSL main.py SKILL_VERSION:", main_src.split('SKILL_VERSION = "')[1].split('"')[0])
