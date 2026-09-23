#!/bin/bash
# Surgical probe: what is actually running, and does the live telemetry expose P0-4 fields?
B=http://127.0.0.1:8765
echo "=== brain process ==="
ps -eo pid,etime,cmd | grep -E 'fly64.main|fly64\.main' | grep -v grep | cut -c1-150
echo
echo "=== /memory.json : P0-4 fields ==="
curl -s -m 5 $B/memory.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for k in ('stuck_duration','anomaly_state','loop_score','coverage_pct',
          'median_speed','displacement_per_speed','progress_ineffective',
          'disp_60s','reflex_active','reflex_ineffective','health_score'):
    if k in d: print('  %-24s %s' % (k, d[k]))
print('  (total keys: %d)' % len(d))
"
echo
echo "=== /flow.json : decision + speed telemetry ==="
curl -s -m 5 $B/flow.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for k in ('decision_source','median_speed','displacement_per_speed',
          'forward_rate','turn_rate','jump_rate','brain_version','evo_iter'):
    if k in d: print('  %-24s %s' % (k, d[k]))
"
echo
echo "=== /help.json : is coach escalation active? ==="
curl -s -m 5 $B/help.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
if not d: print('  (empty)')
for k in ('help_reason','scene_name','diagnosis','stuck_duration','anomaly_state'):
    if k in d: print('  %-24s %s' % (k, str(d[k])[:80]))
"
echo
echo "=== coach service / plugin processes ==="
ps -eo pid,etime,cmd | grep -E 'plugin\.(service|runner)' | grep -v grep | cut -c1-140 || echo "  (none running)"
echo
echo "=== coach artifacts freshness ==="
for f in /root/fly64/skills/active_strategy.json /root/fly64/skills/coach_advice.json /root/fly64/plugin/service_status.json; do
  if [ -f "$f" ]; then echo "  $f  $(stat -c '%y' "$f" | cut -c1-19)  $(stat -c '%s' "$f")B"; else echo "  $f  (missing)"; fi
done
echo
echo "=== coach_frames count ==="
ls /root/fly64/runtime/coach_frames 2>/dev/null | wc -l
