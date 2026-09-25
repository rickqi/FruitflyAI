#!/usr/bin/env bash
# =============================================================================
# Fly64 EVO Loop Resident Launcher — tmux + setsid nohup 双重防护
# =============================================================================
# P0-3 / t3: 重启并守护自进化闭环（evolution_skill.py 常驻循环）。
#
# 依据 analysis-t2-evolution-pipeline-failure.md 失效点 #1：闭环 2026-09-17 后
# 停摆 7 天、无守护、无计划任务。本项目启动契约 = 参照 fly64/scripts/wsl_launcher.sh
# 与 fly64/docs/wsl-launcher-deployment.md：
#
#   - 不用裸 `wsl -e bash -c "setsid nohup ..."`（WSL 会话回收会 SIGTERM 整棵进程树）
#   - 用 tmux 守护会话（tmux server 由 WSL init 直接管理，不受启动 shell 生命周期影响）
#   - 每个子进程额外 setsid nohup 防御（defense in depth）
#
# 与 wsl_launcher.sh 的区别：本脚本只管【进化闭环】一个进程，用独立 tmux 会话
# ``fly64-evo``，绝不触碰 ``fly64``（脑模型 + SM64）会话，避免 --stop 误杀脑模型。
#
# 用法:
#   bash scripts/evo_loop_launcher.sh --launch     启动（默认）
#   bash scripts/evo_loop_launcher.sh --restart    停止后重启
#   bash scripts/evo_loop_launcher.sh --stop       停止闭环
#   bash scripts/evo_loop_launcher.sh --status     查看闭环运行状态
#   bash scripts/evo_loop_launcher.sh --attach     附加到 tmux 终端看实时日志
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMUX_SESSION="fly64-evo"
LOOP_LOG="/tmp/evo_loop.log"
LAUNCH_LOG="/tmp/evo_loop_launcher.log"
EVO_LOG="$PROJECT_DIR/skills/evolution_log.jsonl"
PYTHON_BIN="${FLY64_PYTHON:-/usr/bin/python3}"
INTERVAL="${EVO_LOOP_INTERVAL:-5}"          # 每轮间隔（秒）
MAX_ITER="${EVO_LOOP_MAX_ITERATIONS:-0}"    # 0 = 常驻直到被 kill
ACTION="launch"

# ---- 参数解析 ---------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --launch)  ACTION="launch";  shift ;;
    --restart) ACTION="restart"; shift ;;
    --stop)    ACTION="stop";    shift ;;
    --status)  ACTION="status";  shift ;;
    --attach)  ACTION="attach";  shift ;;
    -h|--help)
      echo "Fly64 EVO Loop Launcher — tmux + setsid nohup 常驻闭环启动器"
      echo ""
      echo "用法: bash scripts/evo_loop_launcher.sh [选项]"
      echo "  --launch   启动闭环（默认）"
      echo "  --restart  停止后重启"
      echo "  --stop     停止闭环"
      echo "  --status   查看闭环状态"
      echo "  --attach   附加到 tmux 终端（实时日志）"
      echo ""
      echo "环境变量:"
      echo "  FLY64_PYTHON            Python 解释器（默认 /usr/bin/python3）"
      echo "  EVO_LOOP_INTERVAL       每轮间隔秒（默认 5）"
      echo "  EVO_LOOP_MAX_ITERATIONS 最大轮数（默认 0 = 常驻）"
      exit 0 ;;
    *) echo "未知选项: $1"; exit 2 ;;
  esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LAUNCH_LOG"; }
err() { echo "[ERR] $*" >&2; exit 1; }

find_evo_pid() {
  pgrep -f "[e]volution_skill\.py" 2>/dev/null | head -1 || true
}

tmux_has_session() {
  tmux has-session -t "$TMUX_SESSION" 2>/dev/null
}

ensure_tmux() {
  if ! command -v tmux &>/dev/null; then
    log "tmux 未安装，自动安装..."
    sudo apt-get update -qq && sudo apt-get install -y -qq tmux 2>/dev/null || {
      err "tmux 安装失败，请手动: sudo apt-get install -y tmux"
    }
  fi
}

# ---- 状态 -------------------------------------------------------------------
cmd_status() {
  echo "=========================================="
  echo " Fly64 EVO Loop Launcher — Status"
  echo "=========================================="
  if tmux_has_session; then
    echo "• tmux 会话 [$TMUX_SESSION]: ● 运行中"
    tmux list-windows -t "$TMUX_SESSION" 2>/dev/null | while IFS= read -r line; do
      echo "    $line"
    done
  else
    echo "• tmux 会话 [$TMUX_SESSION]: ○ 未运行"
  fi

  EVO_PID=$(find_evo_pid)
  if [[ -n "$EVO_PID" ]]; then
    AGE=$(ps -o etime= -p "$EVO_PID" 2>/dev/null | xargs || echo "?")
    echo "• 进化闭环 PID $EVO_PID: ● 运行中 (运行时间: $AGE)"
  else
    echo "• 进化闭环: ○ 未运行"
  fi

  if [[ -f "$EVO_LOG" ]]; then
    MTIME=$(stat -c %Y "$EVO_LOG" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$(( NOW - MTIME ))
    LINES=$(wc -l < "$EVO_LOG" 2>/dev/null | tr -d ' ' || echo "?")
    echo "• evolution_log.jsonl: $LINES 行, 最后写入 ${AGE}s 前"
  else
    echo "• evolution_log.jsonl: ○ 不存在"
  fi

  echo "------------------------------------------"
  echo "  tmux attach -t $TMUX_SESSION      (实时日志)"
  echo "  tail -f $LOOP_LOG                 (闭环 stdout)"
  echo "  bash scripts/evo_loop_launcher.sh --stop"
  echo "=========================================="
}

# ---- 停止 -------------------------------------------------------------------
cmd_stop() {
  log "停止进化闭环..."
  # 1) 终止 tmux 会话（若存在）
  if tmux_has_session; then
    tmux send-keys -t "$TMUX_SESSION" C-c 2>/dev/null || true
    sleep 1
    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    log "tmux 会话 $TMUX_SESSION 已终止"
  fi
  # 2) 终止残留进程（双重保障）
  EVO_PID=$(find_evo_pid)
  if [[ -n "$EVO_PID" ]]; then
    log "终止进化闭环进程 $EVO_PID..."
    kill "$EVO_PID" 2>/dev/null || true
    sleep 2
    kill -9 "$EVO_PID" 2>/dev/null || true
  fi
  log "进化闭环已停止"
}

# ---- 启动（核心）------------------------------------------------------------
cmd_launch() {
  ensure_tmux

  if tmux_has_session; then
    log "tmux 会话 [$TMUX_SESSION] 已在运行"
    cmd_status
    exit 0
  fi

  cd "$PROJECT_DIR"
  log "Python: $PYTHON_BIN | interval=${INTERVAL}s | max-iterations=$MAX_ITER"
  log "创建 tmux 会话 $TMUX_SESSION ..."

  tmux new-session -d -s "$TMUX_SESSION" -n "evo" bash

  # 与 wsl_launcher.sh 同款: setsid nohup 脱离宿主 shell + </dev/null 读端关闭防御
  tmux send-keys -t "$TMUX_SESSION:0" \
    "cd $PROJECT_DIR && \
     echo '===== EVO Loop (resident) =====' && \
     echo 'Starting evolution_skill.py with setsid nohup...' && \
     setsid nohup $PYTHON_BIN skills/evolution_skill.py \
       --max-iterations $MAX_ITER \
       --interval $INTERVAL \
       > $LOOP_LOG 2>&1 < /dev/null & \
     echo \"EVO PID: \$!\"" Enter

  sleep 3
  EVO_PID=$(find_evo_pid)
  if [[ -n "$EVO_PID" ]]; then
    log "进化闭环已启动 (PID: $EVO_PID, 日志: $LOOP_LOG)"
  else
    log "[WARN] 进化闭环可能未启动，日志尾部:"
    tail -8 "$LOOP_LOG" 2>/dev/null || true
  fi

  echo ""
  log "================================================================"
  log " EVO 闭环启动完成"
  log "  tmux 会话 : $TMUX_SESSION"
  log "  闭环 PID  : $(find_evo_pid || echo 'N/A')"
  log "  运行日志  : $LOOP_LOG"
  log "  数据源    : http://127.0.0.1:8765/ (脑模型 dashboard)"
  log "  操作:"
  log "    附加终端 : tmux attach -t $TMUX_SESSION"
  log "    查看状态 : bash scripts/evo_loop_launcher.sh --status"
  log "    停止     : bash scripts/evo_loop_launcher.sh --stop"
  log "================================================================"
}

cmd_attach() {
  if tmux_has_session; then
    exec tmux attach-session -t "$TMUX_SESSION"
  else
    err "tmux 会话 [$TMUX_SESSION] 不存在。先运行: bash scripts/evo_loop_launcher.sh --launch"
  fi
}

# ---- 主流程 -----------------------------------------------------------------
case "$ACTION" in
  launch)  cmd_launch ;;
  restart) cmd_stop; sleep 2; cmd_launch ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  attach)  cmd_attach ;;
  *) err "未知操作: $ACTION" ;;
esac
