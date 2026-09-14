#!/bin/bash
# Fly64 autonomy service watchdog (WSL).
# Ensures the resident autonomy service (plugin/service.py) stays alive:
#   * restarts it when the process dies (crash / OOM / manual kill)
#   * counts consecutive restart failures and logs an ALERT after MAX_FAILS
# Designed to run from cron (* * * * * /root/fly64/plugin/watchdog.sh)
# or from a systemd timer; it is idempotent and cheap.
set -u
PROJECT=/root/fly64
PID_FILE="$PROJECT/plugin/fly64-service.pid"
LOG_FILE="$PROJECT/plugin/service.log"
WATCHDOG_LOG="$PROJECT/plugin/watchdog.log"
FAIL_COUNTER="$PROJECT/plugin/.watchdog_fails"
MAX_FAILS=3
SERVICE_ARGS="--interval 10"

log() { echo "$(date '+%Y-%m-%dT%H:%M:%S') [watchdog] $*" >> "$WATCHDOG_LOG"; }

is_alive() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid=$(cat "$PID_FILE" 2>/dev/null)
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start_service() {
  cd "$PROJECT"
  # Interpreter: same policy as consolidate.sh — venv only if it can import.
  PY=/usr/bin/python3
  if ./venv/bin/python -c "import numpy, scipy" 2>/dev/null; then
    PY=./venv/bin/python
  fi
  PYTHONPATH="$PROJECT" nohup "$PY" -m plugin.service $SERVICE_ARGS \
    >> "$LOG_FILE" 2>&1 &
  disown
  sleep 3
  if is_alive; then
    log "started pid=$(cat "$PID_FILE") with $PY"
    echo 0 > "$FAIL_COUNTER"
  else
    local fails
    fails=$(( $(cat "$FAIL_COUNTER" 2>/dev/null || echo 0) + 1 ))
    echo "$fails" > "$FAIL_COUNTER"
    log "FAILED to start (consecutive=$fails)"
    if [[ "$fails" -ge "$MAX_FAILS" ]]; then
      log "ALERT: $fails consecutive start failures — manual intervention needed"
      tail -20 "$LOG_FILE" >> "$WATCHDOG_LOG"
    fi
  fi
}

if is_alive; then
  exit 0   # healthy; nothing to do
fi

log "service not alive (pid file: $(cat "$PID_FILE" 2>/dev/null || echo none)) -> restarting"
start_service
