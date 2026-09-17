#!/bin/bash
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
cp "$DEV/fly64/memory.py" "$DEV/fly64/main.py" "$DEV/skills/evolution_history.json" "$DEP/fly64/"
pkill -f 'fly64.main' 2>/dev/null || true
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep | head -2
python3 -c "import json,urllib.request;f=json.load(urllib.request.urlopen('http://127.0.0.1:8765/flow.json'));print('bv =',f.get('brain_version'))"