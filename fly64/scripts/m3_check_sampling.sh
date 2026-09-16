#!/bin/bash
CSV=/root/fly64/runtime/mbon_eval.csv
pgrep -af m3_mbon_eval | grep -v grep | head -1 || echo "sampler finished"
echo "rows: $(wc -l < $CSV 2>/dev/null)"
cd /root/fly64 && python3 scripts/m3_mbon_eval.py analyse --csv runtime/mbon_eval.csv
