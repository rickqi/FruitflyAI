#!/bin/bash
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py fly64/memory.py skills/skills.md skills/evolution_history.json \
         tests/test_memory.py scripts/ver_append_fix5.py; do
  cp "$DEV/$f" "$DEP/$f"
done
pkill -f 'fly64.main' 2>/dev/null || true
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep | head -2
./venv/bin/python -m pytest tests/test_memory.py tests/test_fall_state_accuracy.py -q 2>&1 | tail -1
python3 -c "import json, urllib.request; f=json.load(urllib.request.urlopen('http://127.0.0.1:8765/flow.json')); print('brain_version =', f.get('brain_version'))"