#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROM_PATH="${1:-$PROJECT_DIR/rom/mario64usa.z64}"
MP4="${2:-$PROJECT_DIR/artifacts/fly64-demo-$(date +%Y%m%d-%H%M%S).mp4}"
mkdir -p "$PROJECT_DIR/runtime" "$PROJECT_DIR/artifacts"
xcrun swiftc -parse-as-library "$PROJECT_DIR/scripts/record_windows.swift" -o "$PROJECT_DIR/runtime/record-windows"
export FLY64_VERIFY_VISION="${FLY64_VERIFY_VISION:-$PROJECT_DIR/artifacts/vision-isolation.json}"

"$PROJECT_DIR/run-fly64" --rom "$ROM_PATH" --duration 85 &
RUN_PID=$!
trap 'kill "$RUN_PID" 2>/dev/null || true' EXIT INT TERM
for attempt in {1..120}; do
  if curl -fsS http://127.0.0.1:8765/bridge-status.json >/dev/null 2>&1 && \
     [[ -f "$PROJECT_DIR/runtime/dashboard.pid" && -f "$PROJECT_DIR/runtime/game.pid" ]]; then break; fi
  kill -0 "$RUN_PID" 2>/dev/null || exit 1
  sleep 1
done
sleep 3
"$PROJECT_DIR/runtime/record-windows" "$(< "$PROJECT_DIR/runtime/game.pid")" \
  "$(< "$PROJECT_DIR/runtime/dashboard.pid")" "$MP4" 75
wait "$RUN_PID"
echo "Recorded $MP4"
