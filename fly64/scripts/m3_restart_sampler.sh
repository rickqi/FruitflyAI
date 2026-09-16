#!/bin/bash
pkill -f m3_mbon_eval 2>/dev/null || true
sleep 1
cd /root/fly64
rm -f runtime/mbon_eval.csv
setsid nohup python3 scripts/m3_mbon_eval.py sample --minutes 40 --interval 5 \
  --csv runtime/mbon_eval.csv > /tmp/mbon_sample.log 2>&1 &
sleep 8
head -1 runtime/mbon_eval.csv
pgrep -af m3_mbon_eval | grep -v grep | head -1
