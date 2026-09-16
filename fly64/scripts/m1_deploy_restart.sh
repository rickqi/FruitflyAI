#!/bin/bash
set -e
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
for f in fly64/main.py skills/evolution_skill.py skills/fix_catalog.json tests/test_p1_neural_takeover.py tests/test_evolution_capability.py tests/test_evo_primitive_scoring.py skills/skills.md; do
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
for k in ('brain_version', 'decision_source', 'cpg_status'):
    print(k, '=', f.get(k))
"
echo "== evo cycle sanity (deployment) =="
cd "$DEP" && ./venv/bin/python -m pytest tests/test_evolution_capability.py tests/test_evo_primitive_scoring.py tests/test_p1_neural_takeover.py -q 2>&1 | tail -1
