#!/usr/bin/env bash
# Fly64 WSL-side brain deploy: sync code from the Windows checkout, restart the
# brain as a SINGLE instance, verify health.  Run inside WSL:
#   bash /mnt/d/codes/flygym/fly64/scripts/sync_from_windows.sh
set -euo pipefail

WIN=/mnt/d/codes/flygym/fly64
DST=/root/fly64
LOG=/tmp/fly64_brain.log

# ── 1. sync code dirs (never runtime/artifacts/.cache — those are state) ──
for d in fly64 web scripts plugin environments config patches skills tests; do
  [ -d "$WIN/$d" ] || continue
  mkdir -p "$DST/$d"
  rsync -a --delete \
    --exclude '__pycache__/' --exclude '*.pyc' --exclude '.pytest*' \
    --exclude '*.npz' --exclude '*.log' \
    --exclude 'active_strategy.json' --exclude 'coach_advice.json' \
    --exclude 'coach_outcomes.jsonl' --exclude 'evolution_*.jsonl' \
    --exclude 'evolution_*.json' --exclude 'evo_stall_alarm.jsonl' \
    --exclude 'fix_catalog.json' --exclude 'brain_tunable_params.json' \
    "$WIN/$d/" "$DST/$d/"
done

# syntax gate: never restart onto a broken tree
python3 - <<'EOF'
import ast, pathlib
for f in pathlib.Path('/root/fly64').rglob('*.py'):
    if '__pycache__' in str(f): continue
    ast.parse(f.read_text(encoding='utf-8', errors='ignore'))
print("syntax gate OK")
EOF

# ── 2. single-instance restart ──
pkill -f 'm3_mbon_eval' 2>/dev/null || true   # external sampler retired: recording is in-brain now
pkill -f 'fly64.main'   2>/dev/null || true
sleep 2

export PYTHONPATH=$DST
nohup python3 -m fly64.main \
  --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz \
  --no-browser --http-port 8765 --ws-port 8766 \
  >> "$LOG" 2>&1 &
echo "brain pid $!"
sleep 6

# ── 3. health check ──
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/ || echo 000)
if [ "$code" != "200" ]; then echo "❌ dashboard unhealthy ($code) — log tail:"; tail -20 "$LOG"; exit 1; fi
n=$(curl -s http://127.0.0.1:8765/brain-replay-trace.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["tick_count"])' 2>/dev/null || echo 0)

# ── 4. MHR coach service (single instance) — produces coach_outcomes events ──
if ! pgrep -f 'plugin.runner' >/dev/null; then
  nohup python3 -m plugin.runner --dashboard http://127.0.0.1:8765 \
    >> /tmp/fly64_coach.log 2>&1 &
  echo "coach runner pid $!"
else
  echo "coach runner already running"
fi
echo "✅ brain healthy · replay ticks=$n"
pgrep -af 'fly64.main|plugin.runner' | grep -v grep
