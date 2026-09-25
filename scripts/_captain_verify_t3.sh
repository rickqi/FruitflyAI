#!/bin/bash
# Captain verification of t3 (P0-3 EVO loop liveness).
cd /root/fly64 || exit 1
LOG=skills/evolution_log.jsonl

echo "=== 1. EVO loop process ==="
ps -eo pid,etime,cmd | grep -E 'evolution_skill|evo_loop' | grep -v grep | cut -c1-150
echo
echo "=== 2. tmux sessions ==="
tmux ls 2>/dev/null || echo "  (no tmux sessions)"
echo
echo "=== 3. evolution_log.jsonl growth (20 s sample) ==="
if [ -f "$LOG" ]; then
  L0=$(wc -l < "$LOG")
  echo "  t0 lines: $L0"
  sleep 20
  L1=$(wc -l < "$LOG")
  echo "  t1 lines: $L1   delta=$((L1 - L0))"
  echo "  last line time: $(tail -1 "$LOG" | grep -o '"time":[0-9.]*' | head -1)"
else
  echo "  $LOG MISSING"
fi
echo
echo "=== 4. new deliverables (repo + deployed) ==="
for f in scripts/evo_loop_launcher.sh scripts/evo_liveness_guard.py; do
  for base in /root/fly64 /mnt/d/codes/flygym/fly64; do
    if [ -f "$base/$f" ]; then
      printf "  %-58s %s\n" "$base/$f" "$(stat -c '%s B  %y' "$base/$f" | cut -c1-30)"
    fi
  done
done
echo
echo "=== 5. alarm artifacts ==="
for f in skills/evo_stall_alarm.jsonl skills/evo_stall_alarm.json plugin/service_status.json; do
  if [ -f "$f" ]; then
    echo "  --- $f (last 2 lines) ---"
    tail -2 "$f" | cut -c1-170
  else
    echo "  $f  (missing)"
  fi
done
echo
echo "=== 6. self-check ==="
python3 scripts/evo_liveness_guard.py --selfcheck 2>&1 | tail -12
