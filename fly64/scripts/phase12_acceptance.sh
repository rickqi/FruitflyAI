#!/bin/bash
# Phase 1+2 acceptance: ramp_trap LONG_JUMP displacement validation
# Samples /flow.json (decision_source), /memory.json (stuck/cpg/disp), /events.json
DUR=${1:-300}   # seconds, default 5 min
END=$(( $(date +%s) + DUR ))
OUT=/tmp/phase12_acceptance.log
echo "ts, stuck_s, anomaly, cpg_active, cpg_completed, cpg_aborted, disp_60s, source, x, y, jump, z" > $OUT
while [ $(date +%s) -lt $END ]; do
  curl -s http://127.0.0.1:8765/memory.json | python3 -c "
import json, sys
m = json.load(sys.stdin)
cpg = m.get('cpg', {})
print(f\"{m.get('stuck_duration',0)}, {m.get('anomaly_state','')}, {cpg.get('active','')}, {cpg.get('completed',0)}, {cpg.get('aborted',0)}, {m.get('disp_60s',0)}\")" > /tmp/_m.csv
  curl -s http://127.0.0.1:8765/flow.json | python3 -c "
import json, sys
f = json.load(sys.stdin)
print(f\"{f.get('decision_source','')}\", end=',')" >> /tmp/_m.csv
  curl -s http://127.0.0.1:8765/bridge-status.json | python3 -c "
import json, sys
b = json.load(sys.stdin)
print(f\"{b['x']}, {b['y']}, {b['jump']}, {b['z']}\")" >> /tmp/_m.csv
  paste -d, /tmp/_m.csv >> $OUT
  sleep 5
done
echo "== summary =="
python3 - <<'PYEOF'
import csv
rows = list(csv.DictReader(open("/tmp/phase12_acceptance.log")))
cpg_rows = [r for r in rows if r["source"].startswith("cpg_primitive")]
stuck_vals = [float(r["stuck_s"]) for r in rows]
disp_vals = [float(r["disp_60s"] or 0) for r in rows]
print(f"samples={len(rows)}  cpg_active_samples={len(cpg_rows)}  ({100*len(cpg_rows)/max(len(rows),1):.0f}%)")
print(f"cpg sources seen: {sorted(set(r['source'] for r in cpg_rows))}")
print(f"stuck: min={min(stuck_vals):.1f}s max={max(stuck_vals):.1f}s (resets mean gating works)")
print(f"disp_60s: max={max(disp_vals):.1f}u mean={sum(disp_vals)/len(disp_vals):.1f}u  (README baseline: 0u)")
z_seen = any(r["z"] in ("True", "true") for r in rows)
print(f"Z trigger observed on applied buttons: {z_seen}")
PYEOF
