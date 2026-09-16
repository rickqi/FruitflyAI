import json

path = "skills/default_patterns.json"
d = json.load(open(path))
pats = d["patterns"]
existing = {p["id"] for p in pats}

new = []
if "primitive_timeout" not in existing:
    new.append({
        "id": "primitive_timeout",
        "name": "CPG primitive timeout — 运动原语超时熔断",
        "version": "1.0.0",
        "description": "A CPG motor primitive (longjump/backflip/groundpound) was aborted by the 2s circuit breaker, meaning the phase script wedged without producing its move.",
        "conditions": {"cpg_aborted": {"min": 1}, "cpg_last_abort": {"const": "timeout"}},
        "contradiction": "primitive requested but phase script exceeded MAX_PRIMITIVE_S without completing",
        "diagnosis": "Phase script duration or game physics state prevents completion (e.g. longjump requested while wedged against geometry); breaker fired and fell back to reflex cascade.",
        "fix_template": "# Fix: shorten the {primitive} phase script or add a state precondition\n# File: fly64/fly64/motor_primitives.py\n# Adjust: PHASE_SCRIPTS[{primitive}] durations / STATE_PRECONDITIONS\n",
        "fix_files": ["fly64/fly64/motor_primitives.py"],
        "severity": "medium",
        "tags": ["motor", "cpg", "primitive", "timeout"],
        "rollback_strategy": "revert_line",
        "threshold_justification": "MAX_PRIMITIVE_S=2.0s breaker (v2.15.0); any timeout event means the scripted duration was exceeded, so a single occurrence is diagnosable"
    })
if "primitive_zero_disp" not in existing:
    new.append({
        "id": "primitive_zero_disp",
        "name": "CPG primitive zero displacement — 原语执行后零位移",
        "version": "1.0.0",
        "description": "Primitive completed but 60s displacement stayed near zero (primitive_disp < 30u over consecutive completions) — the move executed physically but did not escape the trap.",
        "conditions": {"cpg_completed": {"min": 3}, "primitive_disp": {"max": 30}},
        "contradiction": "primitive applied valid button sequence yet displacement stayed at ramp-trap baseline (0u)",
        "diagnosis": "Wrong primitive for the terrain (e.g. longjump on a ledge edge) or Z/A pulse timing lost by the game; needs a different primitive or tighter phase timing.",
        "fix_template": "# Fix: retune {primitive} gating or swap primitive for this scene profile\n# File: fly64/fly64/main.py (gate conditions) / motor_primitives.py (script)\n",
        "fix_files": ["fly64/fly64/main.py", "fly64/fly64/motor_primitives.py"],
        "severity": "high",
        "tags": ["motor", "cpg", "primitive", "displacement", "ramp-trap"],
        "rollback_strategy": "revert_line",
        "threshold_justification": "EVO VerificationEngine effectiveness threshold score>=0.3 and reflex_ineffective uses 30u/60s (v2.x) — same 30u floor reused for primitive outcomes"
    })

if new:
    pats.extend(new)
    json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
    print(f"added {len(new)} patterns -> total {len(pats)}")
else:
    print("nothing to add")
