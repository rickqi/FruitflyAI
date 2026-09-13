import sys, json
sys.path.insert(0, "/root/fly64")
try:
    from fly64.skills.evolution_skill import EvolutionPipeline
except ModuleNotFoundError:
    from skills.evolution_skill import EvolutionPipeline

pipeline = EvolutionPipeline(auto_fix=False, window_seconds=30)
result = pipeline.run_one_cycle()
print("=== EVO skill diagnosis cycle ===")
if result.errors:
    print("errors:", result.errors)
print("findings:", len(result.findings))
for f in result.findings:
    print(f" - [{f.severity}] {f.pattern_id} ({f.pattern_name} v{f.pattern_version}) conf={f.confidence}")
    print(f"   diagnosis: {f.diagnosis[:220]}")
    print(f"   contradiction: {f.contradiction[:160]}")
print("applied_fixes:", len(result.applied_fixes))
print("documented:", result.documented)

# Also dump raw live snapshot for context
snap = pipeline.collector.latest_snapshot
if snap:
    def pick(d, keys):
        return {k: d.get(k) for k in keys if isinstance(d, dict) and k in d}
    print("--- live snapshot (key fields) ---")
    print(json.dumps(pick(snap, ["stuck_score","stuck_duration","loop_score","novelty","coverage_pct",
        "health_score","anomaly_state","escape_behavior","fallen","cliff_confidence",
        "decision_source","cliff_conf","brain_version","scene_name"]), default=str, ensure_ascii=False))
