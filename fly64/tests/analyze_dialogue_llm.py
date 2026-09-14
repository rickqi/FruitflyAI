import sys, json, urllib.request
sys.path.insert(0, "/root/fly64")
try:
    from fly64.skills.evolution_skill import EvolutionPipeline
except ModuleNotFoundError:
    from skills.evolution_skill import EvolutionPipeline

def get(ep):
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))
    except Exception as e:
        return {"__err__": str(e)[:80]}

pipe = EvolutionPipeline(auto_fix=False, window_seconds=30)
res = pipe.run_one_cycle()
print("=== EVO findings:", len(res.findings), "errors:", res.errors)
for f in res.findings:
    print(f" - [{f.severity}] {f.pattern_id} conf={f.confidence}: {f.diagnosis[:150]}")

print("\n=== dialogue / llm state ===")
h = get("/help.json"); print("help.json:", json.dumps(h, ensure_ascii=False)[:200])
ca = get("/coach_advice.json"); print("coach_advice:", json.dumps(ca, ensure_ascii=False)[:250])
m = get("/memory.json")
print("memory:", json.dumps({k: m.get(k) for k in
    ("stuck_duration","anomaly_state","reflex_active","reflex_type","reflex_ineffective",
     "disp_60s","forced_bold_explore","scene_id")}, ensure_ascii=False))
f = get("/flow.json")
print("flow scene:", f.get("scene_name"), "| terrain:", f.get("terrain"),
      "| enclosure:", f.get("enclosure_score"), "| brain:", f.get("brain_version"))
