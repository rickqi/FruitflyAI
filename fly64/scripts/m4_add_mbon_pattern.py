import json

path = "skills/default_patterns.json"
d = json.load(open(path))
pats = d["patterns"]
if any(p["id"] == "mbon_wrong_direction" for p in pats):
    print("already present")
else:
    pats.append({
        "id": "mbon_wrong_direction",
        "name": "MBON 学习方向错误 — 原语列权重持续下行",
        "version": "1.0.0",
        "description": "A primitive MBON column's scene-independent weight mean is falling over the collector window (>=8 samples, >=3 min span) while the primitive is being used — success dopamine is being swamped by concurrent setbacks or the sign path is inverted.",
        "conditions": {
            "mbon_w_min_slope": {"max": -0.0005},
            "cpg_completed": {"min": 10}
        },
        "contradiction": "primitive successes keep firing (cpg_completed rises) yet the corresponding column weight mean declines",
        "diagnosis": "Success-tick dopamine is swamped by concurrent behavioral setbacks (check completion-tick dopamine mean) or the add_primitive_outcome sign path is inverted. Fix: raise the success floor (model._success_pulse_floor) or verify dopamine sign at completion.",
        "fix_template": "# Fix: raise the success dopamine floor / audit sign path\n# File: fly64/fly64/model.py\n# Symbol: _success_pulse_floor (currently 0.2) and add_primitive_outcome\n",
        "fix_files": ["fly64/fly64/model.py"],
        "severity": "medium",
        "tags": ["motor", "mbon", "learning", "plasticity", "primitive"],
        "rollback_strategy": "revert_line",
        "threshold_justification": "columns drift ~+0.002/min under healthy success shaping (M3.1 live data); a sustained -0.0005/min over >=3 min is a 4x-sign opposite trend and cannot arise from noise (delta quantisation 1e-5)"
    })
    json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
    print(f"added mbon_wrong_direction -> total {len(pats)}")
