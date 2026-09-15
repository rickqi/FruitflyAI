#!/bin/bash
echo "=== current processes ==="
pgrep -af "fly64.main" | grep -v grep
pgrep -af "us_pc" | grep -v grep
echo "=== bridge freshness ==="
for b in /tmp/f64b /tmp/f64b_traj; do
  [[ -f $b ]] && echo "$b mtime: $(stat -c %y $b | cut -c1-19)"
done
echo "=== ports ==="
curl -s -o /dev/null -w "dashboard 8765: %{http_code}\n" --max-time 3 http://127.0.0.1:8765/ 2>/dev/null || echo "dashboard 8765: down"
