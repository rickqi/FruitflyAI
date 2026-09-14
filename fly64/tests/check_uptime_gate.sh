#!/bin/bash
pid=$(cat /root/fly64/plugin/fly64-service.pid 2>/dev/null)
echo "service pid: $pid"
ps -o pid,etime,lstart,cmd --no-headers -p "$pid" 2>/dev/null
echo "--- stability markers ---"
python3 -c "
import json
ss = json.load(open('/root/fly64/plugin/service_status.json'))
print('cycle:', ss.get('cycle'), '| status:', ss.get('status'))
h = ss.get('health', {})
print('health:', {k: (h.get(k) or {}).get('ok') for k in ('dashboard','bridge','strategy_write')})
"
echo "--- failures ---"
grep -c ALERT /root/fly64/plugin/watchdog.log 2>/dev/null || echo "0 ALERTs"
grep -c '"consecutive_failures": *[1-9]' /root/fly64/plugin/service_status.json 2>/dev/null || echo "no failure records"
# uptime seconds -> hours
ps -o etimes= -p "$pid" 2>/dev/null | awk '{printf "uptime_seconds: %d\nuptime_hours: %.2f\n", $1, $1/3600}'
