#!/bin/bash
exec > /tmp/launch.log 2>&1
set -x

# Start brain
cd /root/fly64
export PYTHONPATH=/root/fly64
rm -f /tmp/f64b_traj /tmp/f64r_traj.npz
setsid nohup python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0 &
BRAIN_PID=$!
echo BRAIN_STARTED $BRAIN_PID

# Wait for brain
for i in $(seq 1 20); do
    python3 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/',timeout=3); exit(0)" 2>/dev/null && break
    sleep 2
done
echo BRAIN_READY

# Start SM64 with WSLg display
cd /root/fly64/.cache/sm64ex
export DISPLAY=:0
export SDL_VIDEODRIVER=x11
export FLY64_BRIDGE=/tmp/f64b_traj
setsid nohup ./build/us_pc/sm64.us.f3dex2e --skip-intro &
SM64_PID=$!
echo SM64_STARTED $SM64_PID

sleep 8
echo FINAL_CHECK
ps aux | grep -E 'fly64|sm64' | grep -v grep