#!/usr/bin/env bash
# Fly64 Full Launch Script
# Starts both brain model and SM64 in WSL using setsid nohup
# Usage: bash /mnt/d/codes/flygym/fly64/scripts/start_fly64_full.sh

set -euo pipefail

cd /root/fly64
export PYTHONPATH=/root/fly64

BRIDGE_PATH=/tmp/f64b_traj
RECORD_PATH=/tmp/f64r_traj.npz
BRAIN_LOG=/tmp/fly64.log
SM64_LOG=/tmp/sm64.log

echo "=== Fly64 Full Launch ==="
echo "Bridge: $BRIDGE_PATH"
echo ""

# Kill any existing processes
echo "Cleaning up old processes..."
pkill -f "fly64.main" 2>/dev/null || true
pkill -f "sm64.us.f3dex2e" 2>/dev/null || true
sleep 2

# Remove old bridge
rm -f "$BRIDGE_PATH"

# 1. Start brain model
echo "Starting brain model..."
setsid nohup python3 -m fly64.main --bridge "$BRIDGE_PATH" \
  --record "$RECORD_PATH" --no-browser --duration 0 \
  > "$BRAIN_LOG" 2>&1 < /dev/null &
BRAIN_PID=$!
echo "Brain PID: $BRAIN_PID"

# Wait for brain to start
sleep 5

# Check if brain is running
if ! kill -0 $BRAIN_PID 2>/dev/null; then
    echo "ERROR: Brain failed to start!"
    tail -20 "$BRAIN_LOG"
    exit 1
fi

# Check brain dashboard
echo "Checking dashboard..."
for i in 1 2 3 4 5; do
    if python3 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/',timeout=3); print('Dashboard:', r.status)" 2>/dev/null; then
        break
    fi
    sleep 2
done

# 2. Start SM64
echo "Starting SM64..."
cd /root/fly64/.cache/sm64ex
setsid nohup env FLY64_BRIDGE="$BRIDGE_PATH" \
  ./build/us_pc/sm64.us.f3dex2e --skip-intro \
  > "$SM64_LOG" 2>&1 < /dev/null &
SM64_PID=$!
echo "SM64 PID: $SM64_PID"

cd /root/fly64

echo ""
echo "=== Launch Complete ==="
echo "Brain PID: $BRAIN_PID   (log: $BRAIN_LOG)"
echo "SM64  PID: $SM64_PID   (log: $SM64_LOG)"
echo "Dashboard: http://127.0.0.1:8765/"
echo ""

# Quick health check after 5 seconds
sleep 5
echo "=== Health Check ==="
if kill -0 $BRAIN_PID 2>/dev/null; then
    echo "[OK] Brain is running"
else
    echo "[FAIL] Brain died!"
    tail -10 "$BRAIN_LOG"
fi
if kill -0 $SM64_PID 2>/dev/null; then
    echo "[OK] SM64 is running"
else
    echo "[FAIL] SM64 died!"
    tail -10 "$SM64_LOG"
fi

# Show bridge status
echo "Bridge file: $(ls -la $BRIDGE_PATH 2>/dev/null || echo 'not found')"
echo ""

# Final dashboard check
python3 -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/',timeout=5)
    print('Dashboard: http://127.0.0.1:8765/ -', r.status)
    r2 = urllib.request.urlopen('http://127.0.0.1:8765/memory.json',timeout=5)
    mem = json.loads(r2.read())
    print('Health:', mem.get('health_score'))
    print('Anomaly:', mem.get('anomaly_state'))
    print('Coverage:', mem.get('coverage_pct'))
except Exception as e:
    print('Dashboard check:', e)
"