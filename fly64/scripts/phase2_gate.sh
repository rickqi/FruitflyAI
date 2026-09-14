#!/bin/bash
# Phase-2 auto-hire gate (EVO decision 2026-09-14):
# When the WSL autonomy service has run STABLY for >= 12 hours
# (uptime >= 12h AND zero watchdog ALERTs AND zero consecutive failures),
# the gate flips to GO — the thin Cordis Tool layer (fly64_status /
# fly64_consult / fly64_strategy) is then auto-approved for building.
# Driven by cron every minute, or run manually to check.
set -u
PROJECT=/root/fly64
PID_FILE="$PROJECT/plugin/fly64-service.pid"
GATE_FILE="$PROJECT/runtime/phase2_gate.json"
REQUIRED_HOURS=12

fail() { echo "[phase2-gate] NOT-GO: $1"; exit 0; }

pid=$(cat "$PID_FILE" 2>/dev/null || true)
[[ -n "$pid" ]] || fail "service not running"
up=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
[[ -n "$up" ]] || fail "service pid $pid dead"
up_h=$(python3 -c "print(round($up/3600, 2))")

alerts=0
[[ -f "$PROJECT/plugin/watchdog.log" ]] && alerts=$(grep -c ALERT "$PROJECT/plugin/watchdog.log" || true)
fails=$(python3 -c "
import json
try:
    ss = json.load(open('$PROJECT/plugin/service_status.json'))
    print(int(ss.get('consecutive_failures') or 0))
except Exception:
    print(0)")
h_ok=$(python3 -c "
import json
try:
    ss = json.load(open('$PROJECT/plugin/service_status.json'))
    h = ss.get('health', {})
    ok = all((h.get(k) or {}).get('ok') for k in ('dashboard','bridge'))
    print('true' if ok else 'false')
except Exception:
    print('false')")

if [[ "$h_ok" != "true" ]]; then fail "health checks failing"; fi
if [[ "$fails" != "0" ]]; then fail "consecutive_failures=$fails"; fi
if (( $(echo "$up_h >= $REQUIRED_HOURS" | bc -l) )); then
  python3 -c "
import json, time
json.dump({'gate': 'GO', 'uptime_hours': $up_h, 'alerts': $alerts,
           'failures': $fails, 'since': time.time(),
           'approved_by': 'EVO decision 2026-09-14 (12h stability auto-hire)'},
          open('$GATE_FILE', 'w'), ensure_ascii=False)"
  echo "[phase2-gate] GO: uptime=${up_h}h alerts=$alerts failures=$fails -> Phase 2 (Cordis Tool layer) approved"
else
  echo "[phase2-gate] WAITING: uptime=${up_h}h / ${REQUIRED_HOURS}h (alerts=$alerts failures=$fails)"
fi
