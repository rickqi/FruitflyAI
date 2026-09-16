#!/bin/bash
set -e
pkill -f 'fly64.main' 2>/dev/null || true
pkill -f 'm3_mbon_eval' 2>/dev/null || true
sleep 2
cd /root/fly64
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 18
rm -f runtime/mbon_eval.csv
setsid nohup python3 scripts/m3_mbon_eval.py sample --minutes 45 --interval 5 \
  --csv runtime/mbon_eval.csv > /tmp/mbon_sample.log 2>&1 &
sleep 10
echo "== procs =="; pgrep -af 'fly64.main|m3_mbon' | grep -v grep
echo "== flow mb_w keys =="
python3 - <<'EOF'
import json, urllib.request
f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json"))
for k in ("brain_version", "mb_w_punch", "mb_w_dive", "mb_w_groundpound", "mb_w_longjump"):
    print(k, "=", f.get(k))
EOF
head -2 runtime/mbon_eval.csv
