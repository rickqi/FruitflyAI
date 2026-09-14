#!/bin/bash
# t2 soak verification for the autonomy resident service.
set -u
cd /root/fly64
echo "=== restart via watchdog ==="
bash plugin/watchdog.sh
sleep 4
PID=$(cat plugin/fly64-service.pid 2>/dev/null || echo none)
echo "service pid=$PID"
if [[ -n "$PID" && "$PID" != none ]] && kill -0 "$PID" 2>/dev/null; then
  echo "ALIVE after watchdog"
else
  echo "NOT ALIVE after watchdog"; tail -5 plugin/watchdog.log; exit 1
fi

echo "=== soak 70s (crossing several wsl sessions) ==="
sleep 70

echo "=== pgrep -af fly64 ==="
pgrep -af fly64

echo "=== service status json ==="
cat plugin/service_status.json

echo "=== cycles in log ==="
grep -c "cycle" plugin/service.log
tail -8 plugin/service.log

echo "=== strategy / advice files ==="
ls -la skills/active_strategy.json skills/coach_advice.json 2>&1

echo "=== brain version via dashboard ==="
python3 -c "import json,urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8765/flow.json', timeout=5))['brain_version'])"

echo "=== check_version contract ==="
python3 tests/check_version.py
