#!/bin/bash
# CONSOLIDATE smart restart (EVO R9 institutionalization).
#
# ── 启动契约（t18 结构修复，勿删）─────────────────────────────────────────
# SM64 与大脑进程【必须】用 setsid 脱离宿主 shell 常驻：
#
#   # 大脑（FULL 模式，桥接现有游戏）：
#   cd /root/fly64
#   setsid nohup python3 -m fly64.main --bridge /tmp/f64b_traj \
#     --record /tmp/f64r_traj.npz --no-browser --duration 0 \
#     > /tmp/fly64.log 2>&1 < /dev/null &
#
#   # SM64 游戏：
#   cd /root/fly64/.cache/sm64ex
#   setsid nohup env FLY64_BRIDGE=/tmp/f64b_traj \
#     ./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/sm64.log 2>&1 < /dev/null &
#
# 【禁止】把它们作为托管后台 job（pwsh run_in_background / agent 后台 job /
# 交互终端前台子进程）直接启动：宿主会话结束或 job 被回收时，SM64 与大脑
# 作为其前台子进程会被连带 kill → 共享内存桥冻结 → 仪表板显示卡死。
# 此事故已发生两次（两台进程同被回收）。手工调试跑完务必收尾，
# 常驻运行一律 setsid + nohup + 输出重定向 + </dev/null。
#
# Rule: if the SM64 game process is alive, restart the brain in FULL mode on
# the game's bridge so vision input matches the displayed game.  Only fall
# back to --synthetic when no game is running (prevents the R8 incident where
# a --synthetic consolidate silently disconnected vision from the game).
set -euo pipefail
PROJECT=/root/fly64
GAME_BRIDGE=/tmp/f64b

GAME_PID=""
GAME_BRIDGE=/tmp/f64b
# Pick the actual game engine process (not its bash wrapper) and read the
# bridge it was given via FLY64_BRIDGE.
for _p in $(pgrep -f "us_pc.*skip-intro"); do
  _b=$(tr '\0' '\n' < /proc/"$_p"/environ 2>/dev/null | grep '^FLY64_BRIDGE=' | cut -d= -f2 || true)
  if [[ -n "${_b:-}" ]]; then
    GAME_PID=$_p; GAME_BRIDGE=$_b; break
  fi
done
MODE_ARGS=(--no-browser --duration 0)
BRIDGE=$GAME_BRIDGE

if [[ -n "$GAME_PID" ]]; then
  echo "[consolidate] game pid=$GAME_PID bridge=$BRIDGE -> FULL mode"
else
  MODE_ARGS+=(--synthetic --demo-model)
  BRIDGE="$PROJECT/runtime/fly64_bridge.bin"
  echo "[consolidate] no game process -> SYNTHETIC mode"
fi

# Stop any running brain instance.  Match on the module invocation, not the
# interpreter path: instances may run as `python3 -m fly64.main` (system
# python), `venv/bin/python -m fly64.main`, etc.  (EVO R8 follow-up fix.)
pkill -f "[f]ly64\.main" 2>/dev/null || true
sleep 2
pkill -9 -f "[f]ly64\.main" 2>/dev/null || true
sleep 1

# Interpreter: the WSL runtime is the SYSTEM python3 (has numpy/scipy/
# websockets).  ./venv is a stub (31 pkgs, no scipy) and crashes on import —
# only use it if it can actually import scipy (EVO R8-followup fix).
PY=/usr/bin/python3
if ./venv/bin/python -c "import scipy, websockets, numpy" 2>/dev/null; then
  PY=./venv/bin/python
fi
echo "[consolidate] interpreter: $PY"

cd "$PROJECT"
# t18 启动契约：setsid 脱离宿主进程组，防宿主会话回收连带 kill。
PYTHONPATH="$PROJECT" setsid nohup "$PY" -m fly64.main \
  --bridge "$BRIDGE" --record "$PROJECT/artifacts/latest-replay.npz" \
  "${MODE_ARGS[@]}" > /tmp/fly64_consolidate.log 2>&1 < /dev/null &
disown
sleep 8

# Post-start verification.
if ! pgrep -f "fly64.main" > /dev/null; then
  echo "[consolidate] FAILED to start"; tail -20 /tmp/fly64_consolidate.log; exit 1
fi
BV=$(./venv/bin/python - <<'EOF'
import json, urllib.request
print(json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json", timeout=5))["brain_version"])
EOF
)
echo "[consolidate] brain_version=$BV  dashboard ok"

# ── Autonomy resident service (institutionalized) ────────────────────────
# Restart the 10s autonomy loop (plugin/service.py) together with the brain
# so autonomy never outlives a brain restart with a stale dashboard view.
# Watchdog (plugin/watchdog.sh, cron/systemd-timer) keeps it alive afterwards.
# LLM consultant env (API key) — root-only file on WSL, never committed.
[[ -f "$PROJECT/plugin/llm.env" ]] && source "$PROJECT/plugin/llm.env"
AUTONOMY_PID_FILE="$PROJECT/plugin/fly64-service.pid"
if [[ -f "$AUTONOMY_PID_FILE" ]]; then
  _apid=$(cat "$AUTONOMY_PID_FILE" 2>/dev/null || true)
  if [[ -n "${_apid:-}" ]] && kill -0 "$_apid" 2>/dev/null; then
    kill "$_apid" 2>/dev/null || true
    sleep 1
    kill -9 "$_apid" 2>/dev/null || true
  fi
fi
APY=/usr/bin/python3
if ./venv/bin/python -c "import numpy, scipy" 2>/dev/null; then
  APY=./venv/bin/python
fi
cd "$PROJECT"
# t18 启动契约：autonomy 服务同样 setsid 常驻。
PYTHONPATH="$PROJECT" setsid nohup "$APY" -m plugin.service --interval 10 \
  --bridge-path "$BRIDGE" \
  > /tmp/fly64_service_start.log 2>&1 < /dev/null &
disown
sleep 3
if [[ -f "$AUTONOMY_PID_FILE" ]] && kill -0 "$(cat "$AUTONOMY_PID_FILE")" 2>/dev/null; then
  echo "[consolidate] autonomy service restarted pid=$(cat "$AUTONOMY_PID_FILE")"
else
  echo "[consolidate][WARN] autonomy service failed to start (watchdog will retry); see /tmp/fly64_service_start.log"
fi

echo "[consolidate] done. log: /tmp/fly64_consolidate.log"
