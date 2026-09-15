#!/bin/bash
echo "=== processes ==="
ps aux | grep -E "fly64.main|us_pc|plugin.service" | grep -v grep
echo "=== bridge mappers ==="
for b in /tmp/f64b /tmp/f64b_traj; do
  echo "$b (mtime $(stat -c %y $b 2>/dev/null | cut -c12-19)):"
  fuser -v $b 2>&1 | tail -3
done
echo "=== brain env (LLM) ==="
for p in $(pgrep -f fly64.main); do
  tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep FLY64_LLM && break
done || echo "brain has no FLY64_LLM env"
echo "=== control reachability (command_decoupled) ==="
curl -s http://127.0.0.1:8765/memory.json | python3 -c "import json,sys; d=json.load(sys.stdin); print({k:d.get(k) for k in ('command_decoupled','exploration_speed','coverage_rate') if k in d})" 2>/dev/null || true
curl -s http://127.0.0.1:8765/ | grep -o "Game: receiving\|Game: waiting" | head -1
