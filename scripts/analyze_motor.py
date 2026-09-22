#!/usr/bin/env python3
"""Analyze motor pool activity and why movement is monotonous."""
import urllib.request, json

# Bridge status - actual control output
r = urllib.request.urlopen("http://127.0.0.1:8765/bridge-status.json",timeout=5)
bs = json.loads(r.read())
print("=== Bridge Control Output ===")
print("  X,Y: %s, %s" % (bs.get("x"), bs.get("y")))
print("  Jump: %s" % bs.get("jump"))
print("  Game frame: %s" % bs.get("game_frame"))
print("  State: %s" % bs.get("state"))
print("  Age ms: %.1f" % bs.get("age_ms",0))
print("  Pose: %s" % [round(v,1) for v in bs.get("pose",[])[:3]])

# Flow data - decision source and gates
r = urllib.request.urlopen("http://127.0.0.1:8765/flow.json",timeout=5)
flow = json.loads(r.read())
print()
print("=== Neural Control State ===")
print("  decision_source: %s" % flow.get("decision_source"))
print("  gate_forward: %s" % flow.get("gate_forward"))
print("  gate_jump: %s" % flow.get("gate_jump"))
print("  anomaly_state: %s" % flow.get("anomaly_state"))
print("  reflex_active: %s" % flow.get("reflex_active"))
print("  escape_behavior: %s" % flow.get("escape_behavior"))
print("  wall_score: %.4f" % flow.get("wall_score"))
print("  ramp_score: %.4f" % flow.get("ramp_score"))

# Check if pool rates exist
forward_rate = flow.get("forward_rate")
turn_rate = flow.get("turn_rate")
jump_rate = flow.get("jump_rate")
print()
print("=== Neural Pool Rates ===")
print("  forward_rate key exists: %s" % ("forward_rate" in flow))
print("  turn_rate key exists: %s" % ("turn_rate" in flow))
print("  jump_rate key exists: %s" % ("jump_rate" in flow))
print("  raw values: forward=%s turn=%s jump=%s" % (forward_rate, turn_rate, jump_rate))

# Memory data - anomaly context
r = urllib.request.urlopen("http://127.0.0.1:8765/memory.json",timeout=5)
mem = json.loads(r.read())
print()
print("=== Memory / Anomaly Context ===")
print("  stuck_duration: %.1f" % mem.get("stuck_duration",0))
print("  loop_score: %.3f" % mem.get("loop_score",0))
print("  coverage_pct: %.1f" % mem.get("coverage_pct",0))
print("  health_score: %.4f" % mem.get("health_score",0))
print("  anomaly_state: %s" % mem.get("anomaly_state"))
print("  reflex_active: %s" % mem.get("reflex_active"))
print("  escape_behavior: %s" % mem.get("escape_behavior"))
print("  scene_label: %s" % mem.get("scene_label"))

# Dopamine gains
dg = flow.get("dopamine_gain", {})
print()
print("=== Dopamine Gains ===")
for k in ["visual", "forward", "turn", "jump", "recurrent"]:
    if k in dg:
        print("  %s: %.4f" % (k, dg[k]))

# MBON mushroom body signals
print()
print("=== Mushroom Body Output ===")
for k in ["mb_mbon_forward", "mb_mbon_jump", "mb_mbon_explore", "mb_mbon_left", "mb_mbon_right", "mb_mbon_punch", "mb_mbon_dive"]:
    if k in flow:
        print("  %s: %s" % (k, flow[k]))