#!/bin/bash
set -e
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py fly64/motor_primitives.py plugin/runner.py skills/skills.md \
         tests/test_m2_coach_primitives.py tests/test_m2_state_refinement.py \
         tests/test_coach_advice_fix.py; do
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
print('brain_version =', f.get('brain_version'))
print('decision_source =', f.get('decision_source'))
print('cpg_status =', f.get('cpg_status'))
"
cd "$DEP" && ./venv/bin/python -m pytest tests/test_m2_state_refinement.py tests/test_m2_coach_primitives.py tests/test_motor_primitives.py -q 2>&1 | tail -1
