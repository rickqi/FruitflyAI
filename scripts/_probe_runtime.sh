#!/bin/bash
# Probe the Fly64 live runtime state (no side effects).
echo "=== running processes ==="
ps aux | grep -E 'fly64|sm64|plugin' | grep -v grep | while read -r line; do
  echo "$line" | cut -c1-160
done
echo
echo "=== bridge files ==="
ls -la /tmp/f64* 2>/dev/null || echo "(none)"
echo
echo "=== deployed BRAIN_VERSION ==="
grep -m1 'BRAIN_VERSION' /root/fly64/fly64/main.py 2>/dev/null || echo "(main.py not found)"
grep -m1 'SKILL_VERSION' /root/fly64/skills/evolution_skill.py 2>/dev/null || echo "(evolution_skill.py not found)"
echo
echo "=== P0-4 markers in deployed copy ==="
printf 'memory.py displacement_per_speed : '
grep -c 'displacement_per_speed' /root/fly64/fly64/memory.py 2>/dev/null || echo 0
printf 'memory.py progress_is_ineffective: '
grep -c 'progress_is_ineffective' /root/fly64/fly64/memory.py 2>/dev/null || echo 0
printf 'main.py  median_speed            : '
grep -c 'median_speed' /root/fly64/fly64/main.py 2>/dev/null || echo 0
printf 'runner.py _weave_escalation      : '
grep -c '_weave_escalation' /root/fly64/plugin/runner.py 2>/dev/null || echo 0
echo
echo "=== dashboard reachable? ==="
curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8765/evolution.json 2>/dev/null || echo "(no dashboard)"
echo
echo "=== WSLg display ==="
echo "DISPLAY=${DISPLAY:-<unset>}"
pgrep -a Xvfb 2>/dev/null | head -3 || true
