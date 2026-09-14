#!/bin/bash
cd /root/fly64
sleep 12
{ cat plugin/fly64-service.pid
  ps -p $(cat plugin/fly64-service.pid) -o pid,etime,cmd --no-headers
  cat plugin/service_status.json; } > plugin/DEPLOY_EVIDENCE.txt 2>&1
head -20 plugin/DEPLOY_EVIDENCE.txt
echo "--- evolution.json (history persistence) ---"
curl -s http://127.0.0.1:8765/evolution.json | head -c 400
echo
echo "--- brain version ---"
curl -s http://127.0.0.1:8765/flow.json | grep -o '"brain_version":"[^"]*"'
echo "--- dashboard evolution endpoint restored after restart? ---"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/evolution.json
