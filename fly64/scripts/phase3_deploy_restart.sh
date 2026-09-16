#!/bin/bash
set -e
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py fly64/model.py fly64/mushroom_body.py tests/test_neural_pools.py tests/test_mushroom_body.py skills/skills.md; do
  cp "$DEV/$f" "$DEP/$f"
done
echo "synced"
cd "$DEP"
./venv/bin/python -m pytest tests/test_neural_pools.py tests/test_mushroom_body.py tests/test_motor_primitives.py tests/test_autonomy_regression.py -q 2>&1 | tail -1
pkill -f 'fly64.main' && echo "brain killed" || echo "no brain"
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep
echo "== memory sanity =="
curl -s http://127.0.0.1:8765/memory.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('cpg =', d.get('cpg'))
print('stuck =', d.get('stuck_duration'), 'anomaly =', d.get('anomaly_state'))
"
echo "== flow sanity (new keys) =="
curl -s http://127.0.0.1:8765/flow.json | python3 -c "
import json, sys
f = json.load(sys.stdin)
for k in ('mb_mbon_punch','mb_mbon_dive','mb_mbon_groundpound','mb_mbon_longjump','decision_source'):
    print(k, '=', f.get(k))
"
