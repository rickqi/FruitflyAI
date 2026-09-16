#!/bin/bash
cp /mnt/d/codes/flygym/fly64/fly64/main.py /root/fly64/fly64/main.py
pkill -f 'fly64.main' 2>/dev/null || true
sleep 2
cd /root/fly64
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep
python3 /mnt/d/codes/flygym/fly64/scripts/m2_live_check.py
