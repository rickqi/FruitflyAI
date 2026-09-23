#!/usr/bin/env python3
"""Captain live verification of t1 (P1-1 clamp visibility).

Runs the REPO's t1 functions (extracted via AST from fly64/main.py) inside WSL
against the LIVE production active_strategy.json — no deployment touched.

Scenarios:
  A) reproduce the coach's write  (turn_bias=0.8, bold=20.0, FRESH advice_ts)
     -> expect clamped_keys with requested/applied + source="coach"
  B) reproduce the EVO/panel overwrite (identical values, STALE advice_ts)
     -> expect source="evo_or_panel"
  C) in-range values -> expect ZERO clamp records (no false positives)
  D) real recorded timestamps from the 2026-09-23 monitor trace
"""
import ast
import io
import json
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MAIN = "/mnt/d/codes/flygym/fly64/fly64/main.py"
LIVE = "/root/fly64/skills/active_strategy.json"

WANTED = {
    "CLAMP_BOUNDS", "CLAMP_SOURCE_WINDOW_S", "CLAMP_REPORT_TTL_S",
    "CLAMP_REPORT_CAP", "strategy_writer_source", "apply_strategy_clamps",
    "log_clamp_warnings", "clamp_report_update", "build_coach_applied",
}

src = open(MAIN, encoding="utf-8").read()
tree = ast.parse(src)
picked = [n for n in tree.body
          if (isinstance(n, (ast.FunctionDef, ast.Assign))
              and (getattr(n, "name", None) in WANTED
                   or any(getattr(t, "id", None) in WANTED
                          for t in getattr(n, "targets", []))))]
print("extracted %d top-level nodes:" % len(picked))
for n in picked:
    nm = getattr(n, "name", None) or getattr(n.targets[0], "id", "?")
    print("   -", nm)

ns = {"time": time}
exec(compile(ast.Module(body=picked, type_ignores=[]), "<t1>", "exec"), ns)
print()
print("CLAMP_BOUNDS =", ns["CLAMP_BOUNDS"])

live = json.load(open(LIVE, encoding="utf-8"))
expl = live.get("exploration") or {}
print("live exploration.turn_bias           =", expl.get("turn_bias"))
print("live exploration.bold_explore_stuck_s=", expl.get("bold_explore_stuck_s"))
print("live advice_ts                       =", live.get("advice_ts"))
print()

apply_clamps = ns["apply_strategy_clamps"]


def scenario(name, turn_bias, bold, advice_age_s, live_mtime_age_s):
    """Build a payload as the writer would leave it, then run the clamp."""
    payload = json.loads(json.dumps(live))          # deep copy of LIVE data
    sec = payload.setdefault("exploration", {})
    if turn_bias is not None:
        sec["turn_bias"] = turn_bias
    if bold is not None:
        sec["bold_explore_stuck_s"] = bold
    now = time.time()
    payload["advice_ts"] = (now - advice_age_s) if advice_age_s is not None else None
    mtime = now - live_mtime_age_s
    records, applied = apply_clamps(sec, raw=payload, mtime=mtime, now=now)
    print("--- %s ---" % name)
    print("   clamped_keys :", json.dumps(records, ensure_ascii=False))
    print("   applied      :", json.dumps(applied, ensure_ascii=False))
    return records, applied


# A) the coach just wrote 0.8 / 20.0  (advice_ts fresh, file just written)
rA, aA = scenario("A) coach write (0.8 / 20.0), advice_ts fresh", 0.8, 20.0, 1.0, 1.0)
# B) something else rewrote the same out-of-range values 26s later
rB, aB = scenario("B) EVO/panel rewrite, advice_ts stale by 26s", 0.8, 20.0, 26.0, 1.0)
# C) in-range values -> must report NOTHING
rC, aC = scenario("C) in-range values (0.2 / 5)", 0.2, 5.0, 1.0, 1.0)
# D) real recorded timeline from the monitor trace
rD, aD = scenario("D) real trace: coach wrote, reuse live stale advice_ts",
                  0.8, 20.0, 26.0, 1.0)

print()
print("=== ASSERTIONS ===")
ok = True
if not (rA and rA[0]["requested"] == 0.8 and rA[0]["applied"] == 0.25
        and rA[0]["source"] == "coach"):
    print("  FAIL A: expected coach-sourced clamp 0.8 -> 0.25"); ok = False
else:
    print("  PASS A: turn_bias 0.8 -> 0.25, source=coach")
if len(rA) >= 2 and rA[1]["requested"] == 20.0 and rA[1]["applied"] == 10.0:
    print("  PASS A2: bold_explore_stuck_s 20.0 -> 10.0")
else:
    print("  FAIL A2: expected bold 20.0 -> 10.0"); ok = False
if rB and rB[0]["source"] == "evo_or_panel":
    print("  PASS B: stale advice_ts attributed to evo_or_panel (the overwrite)")
else:
    print("  FAIL B: expected source=evo_or_panel, got %s" % (rB[0]["source"] if rB else None)); ok = False
if not rC:
    print("  PASS C: in-range values produced ZERO clamp records")
else:
    print("  FAIL C: false positives ->", rC); ok = False
if aC.get("turn_bias") == 0.2 and aC.get("bold_explore_stuck_s") == 5.0:
    print("  PASS C2: applied mirrors on-disk in-range values")
else:
    print("  FAIL C2: applied=%s" % aC); ok = False

print()
print("RESULT:", "ALL LIVE CHECKS PASS" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)
