#!/bin/bash
# Monitor active_strategy.json for 60s to see whether coach values persist
# or are overwritten by the EVO self-heal writeback.
S=/root/fly64/skills/active_strategy.json
A=/root/fly64/skills/coach_advice.json
echo "t=+0s  (baseline)"
for i in $(seq 0 12); do
  sleep 5
  python3 - "$S" "$A" "$i" <<'PY'
import json, os, sys, time
s_path, a_path, i = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    s = json.load(open(s_path, encoding='utf-8'))
except Exception as e:
    s = {}
try:
    a = json.load(open(a_path, encoding='utf-8'))
except Exception:
    a = {}
se = s.get('exploration') or {}
ase = (a.get('strategy') or {}).get('exploration') or {}
mt = os.path.getmtime(s_path)
print("t=+%2ss  file.turn_bias=%-6s coach.turn_bias=%-6s  file.bold=%-6s coach.bold=%-6s  gen=%-4s advice_ts=%s  mtime_age=%.1fs" % (
    int(i)*5,
    se.get('turn_bias'), ase.get('turn_bias'),
    se.get('bold_explore_stuck_s'), ase.get('bold_explore_stuck_s'),
    s.get('__generation'), s.get('advice_ts'),
    time.time() - mt,
))
PY
done
echo
echo "=== who else writes active_strategy.json? (deployed code references) ==="
grep -rln "active_strategy" /root/fly64/fly64 /root/fly64/skills /root/fly64/plugin 2>/dev/null | head -10
