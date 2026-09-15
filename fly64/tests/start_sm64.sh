#!/bin/bash
# Start SM64 with bridge
cd /root/fly64/.cache/sm64ex
FLY64_BRIDGE=/tmp/f64b_traj nohup ./build/us_pc/sm64.us.f3dex2e --skip-intro \
  > /tmp/sm64_start.log 2>&1 &
disown
sleep 4
pgrep -af us_pc | grep -v grep | head -1 && echo "[ok] SM64 started"
