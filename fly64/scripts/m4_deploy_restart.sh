#!/bin/bash
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in skills/evolution_skill.py skills/default_patterns.json skills/skills.md skills/evolution_history.json tests/test_mbon_skill_capability.py; do
  cp "$DEV/$f" "$DEP/$f"
done
pkill -f 'fly64.main' 2>/dev/null || true
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep | head -2
./venv/bin/python -m pytest tests/test_mbon_skill_capability.py -q 2>&1 | tail -1
tail -1 /tmp/fly64_run.log 2>/dev/null || true
