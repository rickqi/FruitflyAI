#!/usr/bin/env python3
"""Runner for EvolutionSkill analysis on WSL."""
import sys, json, urllib.request
sys.path.insert(0, '/root/fly64')

from fly64.skills.evolution_skill import EvolutionPipeline

BASE = "http://127.0.0.1:8765"

def fetch(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())

print("=== EVOLUTION SKILL ANALYSIS ===")
mem = fetch("/memory.json")
flow = fetch("/flow.json")
evt = fetch("/events.json")

print("Coverage: %.1f%% (%d cells)" % (mem.get("coverage_pct",0), mem.get("visited_cells",0)))
print("Stuck: %.0fs | Health: %.2f | Loop: %.1f" % (mem.get("stuck_duration",0), mem.get("health_score",1), mem.get("loop_score",0)))
print("Anomaly: %s | Reflex: %s" % (mem.get("anomaly_state","idle"), mem.get("reflex_active",False)))
ct = evt.get("counters",{})
print("Escapes: %d | Falls: %d | FlowAvoids: %d" % (ct.get("total_escapes",0), ct.get("total_falls",0), ct.get("total_flow_avoid",0)))
print("Terrain: %s | Wall: %.2f | Ramp: %.2f | Asym: %.3f | Ground: %.2f" % (
    flow.get("terrain","?"), flow.get("wall_score",0), flow.get("ramp_score",0),
    flow.get("asymmetry",0), flow.get("ground_angle",1)))

print("\n--- Running EvolutionPipeline ---")
pipe = EvolutionPipeline(bridge_url=BASE, auto_fix=False)
result = pipe.run_one_cycle()

print("\nFindings: %d" % len(result.findings))
for f in result.findings:
    print("  [%s] %s" % (f.severity.upper(), f.pattern_name))
    print("    Confidence: %.0f%%" % (f.confidence * 100))
    print("    Values: %s" % f.matched_values)
    print("    Diagnosis: %s" % getattr(f, 'diagnosis', 'N/A'))

if not result.findings:
    print("  (no patterns matched)")
    print("\nPossible reasons:")
    print("  - All conditions not simultaneously met")
    print("  - Window not yet filled with data")
    print("  - Current state doesn't match any pattern")

print("\nFix applied: %s" % result.fix_applied)
print("Cycle complete.")