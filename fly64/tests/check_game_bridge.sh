#!/bin/bash
ps aux | grep us_pc | grep -v grep
echo "---"
for p in $(pgrep -f us_pc); do
  echo "pid $p:"
  tr '\0' '\n' < /proc/$p/environ | grep -i FLY64
done
echo "--- bridges ---"
ls -la /tmp/f64b* /root/fly64/runtime/*.bin 2>/dev/null
