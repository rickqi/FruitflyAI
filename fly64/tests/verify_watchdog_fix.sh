#!/bin/bash
cp /mnt/d/codes/flygym/fly64/plugin/watchdog.sh /root/fly64/plugin/
pkill -f "plugin.service" 2>/dev/null
sleep 65
cd /root/fly64
grep -o '"bridge": {[^}]*}' plugin/service_status.json
bash /root/fly64/scripts/phase2_gate.sh
pgrep -af "fly64.main|plugin.service"
