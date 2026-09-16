#!/bin/bash
set -e
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py web/dashboard.js scripts/m3_mbon_eval.py scripts/m3_js_check.js; do
  cp "$DEV/$f" "$DEP/$f"
done
echo synced
pkill -f 'fly64.main' && echo brain-killed || echo no-brain
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 18
pgrep -af 'fly64.main|sm64.us' | grep -v grep
python3 scripts/m3_mbon_eval.py analyse --csv runtime/mbon_eval.csv | head -4
tail -2 /tmp/fly64_run.log
