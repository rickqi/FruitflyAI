#!/bin/bash
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py fly64/model.py skills/skills.md skills/evolution_history.json \
         tests/test_r31fix3_reward_reshaping.py scripts/ver_append_fix3.py; do
  cp "$DEV/$f" "$DEP/$f"
done
pkill -f 'fly64.main' 2>/dev/null || true
sleep 2
cd "$DEP"
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 15
pgrep -af 'fly64.main|sm64.us' | grep -v grep | head -2
python3 - <<'EOF'
import json, urllib.request
f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json"))
print("brain_version =", f.get("brain_version"))
print("decision_source =", f.get("decision_source"))
m = json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json"))
print("scene =", m.get("scene_name"), "stuck =", m.get("stuck_duration"),
      "anomaly =", m.get("anomaly_state"), "health =", m.get("health_score"))
EOF
