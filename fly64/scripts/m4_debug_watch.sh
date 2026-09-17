#!/bin/bash
pkill -f 'fly64.main' 2>/dev/null; pkill -f 'sm64.us' 2>/dev/null; sleep 2
cd /root/fly64
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 5
cd /root/fly64/.cache/sm64ex
setsid nohup env FLY64_BRIDGE=/tmp/f64b_traj FLY64_CAPTURE_DEBUG=1 \
  ./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/sm64.log 2>&1 &
for i in 1 2 3 4 5 6; do
  sleep 20
  g=$(pgrep -c -f 'sm64.us' 2>/dev/null || echo 0)
  b=$(pgrep -c -f 'fly64.main' 2>/dev/null || echo 0)
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/flow.json 2>/dev/null)
  echo "t=$((i*20))s game=$g brain=$b http=$code"
done
echo "== capture breadcrumbs (last 8) =="
grep 'capture' /tmp/sm64.log | tail -8
echo "== crash? =="
grep -iE 'segv|segmentation' /tmp/sm64.log | head -2
