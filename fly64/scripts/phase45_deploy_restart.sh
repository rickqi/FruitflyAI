#!/bin/bash
set -e
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py fly64/telemetry.py skills/evolution_skill.py skills/default_patterns.json web/dashboard.js patches/sm64ex-fly64.patch tests/test_dashboard_protocol.py; do
  cp "$DEV/$f" "$DEP/$f"
done
echo synced
pkill -f 'fly64.main' && echo brain-killed || echo no-brain
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep
curl -s http://127.0.0.1:8765/flow.json | python3 -c "
import json, sys
f = json.load(sys.stdin)
for k in ('brain_version', 'decision_source', 'primitive_disp', 'cpg_status', 'mb_mbon_longjump'):
    print(k, '=', f.get(k))
"
