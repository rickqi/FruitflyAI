#!/bin/bash
# Phase 1+2 live restart per startup contract (setsid, detached from host shell)
cd /root/fly64
# stop old stack
pkill -f 'sm64.us.f3dex2e' 2>/dev/null && echo "killed game" || echo "no game"
pkill -f 'fly64.main' 2>/dev/null && echo "killed brain" || echo "no brain"
sleep 2
# start brain (contract: setsid nohup, output redirected, stdin /dev/null)
setsid nohup ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64_run.log 2>&1 &
sleep 5
# start game
cd /root/fly64/.cache/sm64ex
setsid nohup env FLY64_BRIDGE=/tmp/f64b_traj \
  ./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/sm64.log 2>&1 &
sleep 5
echo "== processes =="
pgrep -af 'fly64.main|sm64.us' | grep -v grep
echo "== brain log tail =="
tail -5 /tmp/fly64_run.log
echo "== game log tail =="
tail -5 /tmp/sm64.log
