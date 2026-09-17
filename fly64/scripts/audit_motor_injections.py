#!/usr/bin/env python3
"""How much of the motor output is still decided by symbolic branches?

WHY
---
`tests/test_invariants.py::test_no_visual_motor_shortcut` asserts that with the
synapse matrix zeroed, a black frame and a white frame produce identical motor
commands — i.e. that vision cannot reach the motor pools except through the
connectome.  Measured (EVO-071): they DIFFER from tick 2, and disabling the two
documented sensory gates (`sky_score`, `opening_score`) does not change that.

The cause is structural rather than a bug in one branch: `FlyModel.step()` writes
current DIRECTLY into motor pools from ~50 sites, many gated on visual features
(sky/wall/ramp/opening/tau/danger/cliff).  With the connectome zeroed those
injections ARE the only path, so the invariant cannot hold.

That matters beyond the test: the project's stated architecture is brain-first
("the LIF network owns the decision"), with P1 "neural takeover" retiring symbolic
branches.  This tool measures how much remains, so the gap is a number instead of
an impression.  It is read-only.

Usage:
    python3 scripts/audit_motor_injections.py [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "fly64" / "model.py"

#: names that carry visual / sensory-derived state into the step() function
VISUAL_FEATURES = {
    "sky_score", "sky_blue_index", "danger_red_index", "wall_score",
    "ramp_score", "opening_score", "opening_asymmetry", "tau",
    "flow_asymmetry", "flow_looming", "flow_cliff", "true_asymmetry",
    "cliff_confirmed", "cliff_tangent_bias", "visual_azimuth", "novelty",
    "scene_change_rate", "ground_angle", "target_count", "enclosure_score",
    "hrc_asymmetry", "true_hrc_asymmetry", "flow_danger", "cliff_detected",
    "underwater", "blue_dom", "danger_level", "restlessness_level",
}

#: names for motor/actuator pools
MOTOR_POOLS = {
    "forward", "turn_left", "turn_right", "jump_nodes", "strike_nodes",
    "crouch_nodes", "motor_nodes", "visual",
}


def _src(node, tree_src):
    try:
        return ast.get_source_segment(tree_src, node) or ""
    except Exception:
        return ""


def analyse():
    text = MODEL.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text)
    parents = {}

    class V(ast.NodeVisitor):
        def generic_visit(self, n):
            for c in ast.iter_child_nodes(n):
                parents[c] = n
                self.visit(c)

    V().visit(tree)

    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AugAssign) and not isinstance(node, ast.Assign):
            continue
        targets = ([node.target] if isinstance(node, ast.AugAssign)
                   else list(node.targets))
        for t in targets:
            s = _src(t, text)
            if not (isinstance(t, ast.Subscript) and s.startswith("self.v[")):
                continue
            pool = s[len("self.v["):].split("]")[0]
            # enclosing if-conditions, innermost first
            conds = []
            cur = parents.get(node)
            depth = 0
            while cur is not None and depth < 12:
                if isinstance(cur, ast.If):
                    conds.append(_src(cur.test, text).replace("\n", " ")[:110])
                cur = parents.get(cur)
                depth += 1
            joined = " | ".join(conds)
            visual = sorted({f for f in VISUAL_FEATURES
                             if f in joined and f != pool})
            rows.append({
                "line": node.lineno,
                "pool": pool,
                "guarded": bool(conds),
                "innermost_condition": conds[0] if conds else "",
                "visual_gates": visual,
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = analyse()
    pools = Counter(r["pool"] for r in rows)
    guarded = [r for r in rows if r["guarded"]]
    visual = [r for r in rows if r["visual_gates"]]

    report = {
        "model": str(MODEL.relative_to(ROOT)),
        "injection_sites": len(rows),
        "by_pool": dict(pools.most_common()),
        "guarded_sites": len(guarded),
        "guarded_fraction": round(len(guarded) / max(1, len(rows)), 3),
        "visually_gated_sites": len(visual),
        "visually_gated_fraction": round(len(visual) / max(1, len(rows)), 3),
        "visually_gated_detail": [
            {"line": r["line"], "pool": r["pool"],
             "features": r["visual_gates"], "condition": r["innermost_condition"]}
            for r in visual],
        "invariant_note": (
            "tests/test_invariants.py::test_no_visual_motor_shortcut asserts that "
            "zeroing the connectome makes black and white frames produce identical "
            "motor commands.  Measured false: they differ from tick 2, and "
            "disabling the documented sky_score/opening_score gates does not help, "
            "because these direct injections are then the only path.  The "
            "invariant is an aspiration the architecture does not meet."),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    print("=" * 78)
    print("MOTOR-POOL CURRENT INJECTIONS IN %s" % report["model"])
    print("=" * 78)
    print("  injection sites           : %d" % report["injection_sites"])
    print("  by pool                   : %s" % report["by_pool"])
    print("  conditionally guarded     : %d (%.0f%%)"
          % (report["guarded_sites"], report["guarded_fraction"] * 100))
    print("  gated on a VISUAL feature : %d (%.0f%%)"
          % (report["visually_gated_sites"],
             report["visually_gated_fraction"] * 100))
    print()
    print("  visually gated sites:")
    for d in report["visually_gated_detail"]:
        print("    line %-5d -> %-12s via %s" % (d["line"], d["pool"],
                                                 ",".join(d["features"])))
    print()
    print("  %s" % report["invariant_note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
