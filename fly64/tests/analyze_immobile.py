import sys, json, time, collections, urllib.request
sys.path.insert(0, "/root/fly64")
try:
    from fly64.skills.evolution_skill import EvolutionPipeline
except ModuleNotFoundError:
    from skills.evolution_skill import EvolutionPipeline

def get(ep):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))

pipeline = EvolutionPipeline(auto_fix=False, window_seconds=30)
result = pipeline.run_one_cycle()
print("=== EVO diagnosis ===")
print("errors:", result.errors)
print("findings:", len(result.findings))
for f in result.findings:
    print(f" - [{f.severity}] {f.pattern_id} v{f.pattern_version} conf={f.confidence}")
    print(f"   {f.diagnosis[:250]}")

print("\n=== live snapshot ===")
m = get("memory.json")
print("memory:", json.dumps({k: m.get(k) for k in
    ("stuck_score","stuck_duration","loop_score","novelty","escape_behavior","fallen",
     "health_score","anomaly_state","visited_cells","coverage_pct","coverage_rate",
     "forced_bold_explore","exploration_mode","brain_version")}, ensure_ascii=False))
f = get("flow.json")
print("flow:", json.dumps({k: f.get(k) for k in
    ("terrain","wall_score","ramp_score","sky_score","enclosure_score","ground_angle",
     "opening_score","door_frame_score","tau","scene_name","decision_source",
     "cliff_confidence","cliff_confirmed")}, ensure_ascii=False, default=str))
ev = get("history.json")
events = ev if isinstance(ev, list) else ev.get("events", [])
print("recent events:", json.dumps([{k: e.get(k) for k in ("t","reason","duration","distance_moved")} for e in events[:6]], ensure_ascii=False))
