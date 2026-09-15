#!/bin/bash
echo "=== FIX 1: watchdog bridge-path passthrough ==="
echo "watchdog.sh has resolve_bridge: $(grep -c resolve_bridge /root/fly64/plugin/watchdog.sh)"
pgrep -af plugin.service
ps -o cmd= -p $(cat /root/fly64/plugin/fly64-service.pid 2>/dev/null) 2>/dev/null
echo "service_status bridge freshness:"
python3 -c "
import json
ss = json.load(open('/root/fly64/plugin/service_status.json'))
b = ss.get('health',{}).get('bridge',{})
print(' bridge ok:', b.get('ok'), '| detail:', b.get('detail'))"

echo ""
echo "=== FIX 2: cron boot persistence ==="
systemctl is-enabled cron 2>/dev/null || service cron status 2>&1 | head -1
pgrep -af cron | grep -v grep | head -2
echo "cron-driven evidence (watchdog.log last entry):"
tail -1 /root/fly64/plugin/watchdog.log
echo "cron-driven evidence (gate log last entry):"
tail -1 /root/fly64/plugin/phase2_gate.log 2>/dev/null || echo "(phase2_gate.log empty)"
