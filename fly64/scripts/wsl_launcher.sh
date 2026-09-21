#!/usr/bin/env bash
# =============================================================================
# Fly64 WSL Launcher — tmux-based 可靠启动器
# =============================================================================
# 根因分析（为什么 `wsl -e bash -c` + `setsid nohup` 进程会被 kill）：
#
#   WSL2 的进程树结构:
#     PID 1: /init (WSL 自定义 init)
#       ├── Relay(N)    ← WSL I/O 复用进程，每个终端会话绑定一个
#       │   ├── python3  ← 脑模型 (Relay 的子进程)
#       │   └── sm64.us.f3dex2e ← SM64 (Relay 的子进程)
#       └── Relay(M)    ← 另一个会话
#
#   `wsl -e bash -c "command"`:
#     1. WSL 创建一个临时终端会话 + Relay 进程
#     2. bash 执行 command，command 退出后 bash 终止
#     3. WSL 检测到该会话的 bash shell 已终止，回收 Relay 进程
#     4. Relay 终止 → 所有子进程（包括 setsid nohup 的进程）被 SIGTERM 杀死
#     5. 即使 setsid 创建了新会话，WSL init 仍然会计入该 Relay 的子进程树
#
#   `setsid nohup` 的限制:
#     - nohup 只忽略 SIGHUP，遇到 SIGTERM 一样会退出
#     - setsid 创建新会话但进程仍是 WSL 进程树的一部分
#     - WSL 销毁会话时对所有进程发送 SIGTERM（不限于 SIGHUP）
#
#   `Start-Process wsl /bin/bash script.sh` 为何有效:
#     - Start-Process 创建一个新的 WSL 终端窗口
#     - bash script.sh 在前台运行，窗口保持打开
#     - 因此 Relay 进程和其子进程保持活跃
#     - 缺陷: 窗口关闭时进程仍可能终止
#
# 核心策略: tmux 守护会话 + setsid nohup 双重防护
#   - tmux server 是独立守护进程，不受启动 shell 生命周期影响
#   - tmux 会话内进程即使启动终端退出也保持运行
#   - 每个子进程额外 setsid nohup 防御（defense in depth）
#   - 无需 systemd（WSL 默认禁用），无需用户配置
#
# 用法:
#   bash scripts/wsl_launcher.sh [--rom /path/to/baserom.us.z64]
#   bash scripts/wsl_launcher.sh --restart
#   bash scripts/wsl_launcher.sh --stop
#   bash scripts/wsl_launcher.sh --status
#   bash scripts/wsl_launcher.sh --attach
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMUX_SESSION="fly64"
BRIDGE_PATH="/tmp/f64b_traj"
RECORD_PATH="/tmp/f64r_traj.npz"
BRAIN_LOG="/tmp/fly64.log"
SM64_LOG="/tmp/sm64.log"
LAUNCH_LOG="/tmp/fly64_launcher.log"
PYTHON_BIN="${FLY64_PYTHON:-}"
ROM_PATH=""
ACTION="launch"

# ---- 参数解析 ---------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rom) ROM_PATH="${2:-}"; shift 2 ;;
    --launch) ACTION="launch"; shift ;;
    --restart) ACTION="restart"; shift ;;
    --stop) ACTION="stop"; shift ;;
    --status) ACTION="status"; shift ;;
    --attach) ACTION="attach"; shift ;;
    -h|--help)
      echo "Fly64 WSL Launcher — tmux-based 可靠启动器"
      echo ""
      echo "用法: bash scripts/wsl_launcher.sh [选项]"
      echo ""
      echo "操作选项:"
      echo "  --launch             启动会话（默认）"
      echo "  --restart            停止后重启"
      echo "  --stop               停止所有进程"
      echo "  --status             查看运行状态"
      echo "  --attach             附加到 tmux 终端"
      echo ""
      echo "启动选项:"
      echo "  --rom <路径>         SM64 ROM 路径"
      echo "  -h, --help           显示此帮助"
      echo ""
      echo "示例:"
      echo "  bash scripts/wsl_launcher.sh --rom /root/fly64/.cache/sm64ex/baserom.us.z64"
      echo "  bash scripts/wsl_launcher.sh --status"
      echo "  bash scripts/wsl_launcher.sh --stop"
      exit 0 ;;
    *) echo "未知选项: $1"; exit 2 ;;
  esac
done

# ---- 辅助函数 ---------------------------------------------------------------
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LAUNCH_LOG"; }
err() { echo "[ERR] $*" >&2; exit 1; }

find_python() {
  if [[ -n "$PYTHON_BIN" ]] && [[ -x "$PYTHON_BIN" ]]; then
    echo "$PYTHON_BIN"
    return
  fi
  # 按优先级选择 Python
  for p in "/usr/bin/python3" "/root/fly64/.venv/bin/python"; do
    if [[ -x "$p" ]]; then
      echo "$p"
      return
    fi
  done
  # 最后尝试系统 python3
  PY=$(which python3 2>/dev/null || true)
  if [[ -n "$PY" ]]; then
    echo "$PY"
    return
  fi
  err "找不到 Python3 解释器"
}

ensure_tmux() {
  if ! command -v tmux &>/dev/null; then
    log "tmux 未安装——正在自动安装..."
    sudo apt-get update -qq && sudo apt-get install -y -qq tmux 2>/dev/null || {
      err "tmux 安装失败，请手动执行: sudo apt-get install -y tmux"
    }
  fi
}

find_brain_pid() {
  pgrep -f "[f]ly64\.main" 2>/dev/null | head -1 || true
}

find_sm64_pid() {
  pgrep -f "sm64\.us\.f3dex2e" 2>/dev/null | head -1 || true
}

tmux_has_session() {
  tmux has-session -t "$TMUX_SESSION" 2>/dev/null
}

# ---- SM64 显示配置 -----------------------------------------------------------
# 配置 SM64 窗口位置、大小和 SDL 显示驱动
# 适配 WSLg Weston/XWayland 环境 (3840x2560 典型分辨率)
setup_sm64_display() {
  local config_file="$1"
  local display_w="${2:-590}"
  local display_h="${3:-443}"
  local pos_x="${4:-18}"
  local pos_y="${5:-160}"

  if [[ ! -f "$config_file" ]]; then
    log "SM64 配置文件不存在: $config_file，跳过显示配置"
    return 1
  fi

  # 检测实际屏幕分辨率并调整窗口位置
  local screen_w=3840
  local screen_h=2560
  local xrandr_out
  xrandr_out=$(xrandr 2>/dev/null | grep -E "\bconnected" | head -1 || true)
  if [[ -n "$xrandr_out" ]]; then
    local dim
    dim=$(echo "$xrandr_out" | grep -oP '\d+x\d+' | head -1 || true)
    if [[ -n "$dim" ]]; then
      screen_w="${dim%%x*}"
      screen_h="${dim##*x}"
      log "检测到屏幕分辨率: ${screen_w}x${screen_h}"
    fi
  fi

  # 如果窗口尺寸大于屏幕，缩小到屏幕的一半
  if (( display_w > screen_w / 2 )); then
    display_w=$(( screen_w / 2 ))
    log "调整窗口宽度: $display_w"
  fi
  if (( display_h > screen_h / 2 )); then
    display_h=$(( screen_h / 2 ))
    log "调整窗口高度: $display_h"
  fi

  # 确保窗口在屏幕范围内
  if (( pos_x + display_w > screen_w )); then
    pos_x=$(( (screen_w - display_w) / 2 ))
  fi
  if (( pos_y + display_h > screen_h )); then
    pos_y=$(( (screen_h - display_h) / 2 ))
  fi

  # 应用配置
  perl -pi -e "s/^window_x .*/window_x $pos_x/;
               s/^window_y .*/window_y $pos_y/;
               s/^window_w .*/window_w $display_w/;
               s/^window_h .*/window_h $display_h/" "$config_file"

  log "SM64 显示配置: 位置=($pos_x,$pos_y) 尺寸=${display_w}x${display_h}"
}

# ---- tmux 'bogus screen size' 修复 ------------------------------------------
# 此警告来自 ncurses 在 tmux 中检测终端尺寸失败
# 对 SM64 游戏窗口无影响，仅 tmux 终端显示
setup_tmux_config() {
  local tmux_conf="$HOME/.tmux.conf"
  if [[ -f "$tmux_conf" ]] && grep -q "default-terminal" "$tmux_conf" 2>/dev/null; then
    return 0  # 已配置
  fi
  # 追加配置以修复 '131072x1 screen size' 警告
  cat >> "$tmux_conf" 2>/dev/null || true
  # 使用 printf 而不是 cat 以避免 heredoc 问题
  if ! grep -q "default-terminal" "$tmux_conf" 2>/dev/null; then
    printf '%s\n' "# Fix ncurses 'bogus screen size' warning in tmux" >> "$tmux_conf"
    printf '%s\n' "set -g default-terminal \"screen-256color\"" >> "$tmux_conf"
    printf '%s\n' "set -ga terminal-overrides ',*:Tc'" >> "$tmux_conf"
    log "已创建 ~/.tmux.conf (修复 ncurses 屏幕尺寸警告)"
  fi
}

# ---- 状态查看 ---------------------------------------------------------------
cmd_status() {
  echo "=========================================="
  echo " Fly64 WSL Launcher — Status"
  echo "=========================================="

  # tmux 会话
  if tmux_has_session; then
    echo "• tmux 会话 [$TMUX_SESSION]: ● 运行中"
    tmux list-windows -t "$TMUX_SESSION" 2>/dev/null | while IFS= read -r line; do
      echo "    $line"
    done
  else
    echo "• tmux 会话 [$TMUX_SESSION]: ○ 未运行"
  fi

  # 脑模型
  BRAIN_PID=$(find_brain_pid)
  if [[ -n "$BRAIN_PID" ]]; then
    BRAIN_AGE=$(ps -o etime= -p "$BRAIN_PID" 2>/dev/null | xargs || echo "?")
    echo "• 脑模型 PID $BRAIN_PID: ● 运行中 (运行时间: $BRAIN_AGE)"
  else
    echo "• 脑模型: ○ 未运行"
  fi

  # SM64
  SM64_PID=$(find_sm64_pid)
  if [[ -n "$SM64_PID" ]]; then
    SM64_AGE=$(ps -o etime= -p "$SM64_PID" 2>/dev/null | xargs || echo "?")
    echo "• SM64 进程 PID $SM64_PID: ● 运行中 (运行时间: $SM64_AGE)"
  else
    echo "• SM64: ○ 未运行"
  fi

  # 仪表板
  if python3 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/',timeout=3); exit(0)" 2>/dev/null; then
    echo "• 仪表板 http://127.0.0.1:8765/: ● 在线"
  else
    echo "• 仪表板 http://127.0.0.1:8765/: ○ 离线"
  fi

  # 日志
  for f in "$BRAIN_LOG" "$SM64_LOG" "$LAUNCH_LOG"; do
    if [[ -f "$f" ]]; then
      echo "• $(basename "$f"): $(du -h "$f" 2>/dev/null | cut -f1)"
    fi
  done

  echo "------------------------------------------"
  echo "  tmux attach -t $TMUX_SESSION   (实时日志)"
  echo "  bash scripts/wsl_launcher.sh --stop   (停止)"
  echo "=========================================="
}

# ---- 停止 ---------------------------------------------------------------
cmd_stop() {
  log "停止 Fly64 进程..."

  # 1) 停止 tmux 会话
  if tmux_has_session; then
    log "停止 tmux 会话 $TMUX_SESSION..."
    tmux send-keys -t "$TMUX_SESSION" C-c 2>/dev/null || true
    sleep 1
    tmux send-keys -t "$TMUX_SESSION" C-c 2>/dev/null || true
    sleep 1
    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    log "tmux 会话已终止"
  fi

  # 2) 清理残留进程（双重保障）
  SM64_PID=$(find_sm64_pid)
  if [[ -n "$SM64_PID" ]]; then
    log "终止 SM64 进程 $SM64_PID..."
    kill "$SM64_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$SM64_PID" 2>/dev/null || true
  fi

  BRAIN_PID=$(find_brain_pid)
  if [[ -n "$BRAIN_PID" ]]; then
    log "终止脑模型进程 $BRAIN_PID..."
    kill "$BRAIN_PID" 2>/dev/null || true
    sleep 2
    kill -9 "$BRAIN_PID" 2>/dev/null || true
  fi

  # 3) 清理桥接文件
  rm -f "$BRIDGE_PATH"
  log "全部停止完成"
}

# ---- 启动（核心）------------------------------------------------------------
cmd_launch() {
  ensure_tmux

  # 修复 tmux ncurses 屏幕尺寸警告（'131072x1 screen size' 对 SM64 显示无影响
  # 但会干扰终端输出，此修复让 tmux 正确报告终端尺寸）
  setup_tmux_config

  # 如果已在运行，提示并退出
  if tmux_has_session; then
    log "tmux 会话 [$TMUX_SESSION] 已在运行"
    cmd_status
    exit 0
  fi

  # 清理旧桥接
  rm -f "$BRIDGE_PATH"
  mkdir -p "$PROJECT_DIR/runtime" "$PROJECT_DIR/artifacts"

  # 确定 Python 解释器
  PYTHON_BIN="$(find_python)"
  log "Python 解释器: $PYTHON_BIN"

  # ==========================================================================
  # 核心设计: tmux 守护会话 + setsid nohup 双重防护
  #
  # 原理:
  #   1. tmux server 是独立守护进程 (WSL init 的直接子进程)
  #   2. tmux 会话内的进程以 tmux 为父进程，不依赖启动 shell
  #   3. 启动 shell 关闭 → tmux 继续运行 → 子进程继续运行
  #   4. setsid + nohup 作为第二层防护 (即使 tmux 意外终止)
  #
  # 与 `wsl -e bash -c` 对比:
  #   - wsl -e: bash 退出 → Relay(会话) 终止 → 子进程被 kill
  #   - tmux:   bash 退出 → tmux server 存活 → 子进程存活
  # ==========================================================================

  cd "$PROJECT_DIR"
  export PYTHONPATH="$PROJECT_DIR"

  # 窗口 0: 脑模型
  log "创建 tmux 会话 $TMUX_SESSION..."
  tmux new-session -d -s "$TMUX_SESSION" -n "brain" bash

  tmux send-keys -t "$TMUX_SESSION:0" \
    "cd $PROJECT_DIR && \
     export PYTHONPATH=$PROJECT_DIR && \
     export FLY64_BRIDGE=$BRIDGE_PATH && \
     echo '' && \
     echo '===== Brain Model =====' && \
     echo 'Starting brain model with setsid nohup...' && \
     rm -f $BRIDGE_PATH && \
     setsid nohup $PYTHON_BIN -m fly64.main \
       --bridge $BRIDGE_PATH \
       --record $RECORD_PATH \
       --no-browser --duration 0 \
       > $BRAIN_LOG 2>&1 < /dev/null &" Enter

  sleep 3

  # 检查脑模型是否已启动
  BRAIN_PID=$(find_brain_pid)
  if [[ -n "$BRAIN_PID" ]]; then
    log "脑模型已启动 (PID: $BRAIN_PID, 日志: $BRAIN_LOG)"
  else
    log "等待脑模型启动..."
    for i in $(seq 1 20); do
      sleep 1
      BRAIN_PID=$(find_brain_pid)
      if [[ -n "$BRAIN_PID" ]]; then
        log "脑模型已启动 (PID: $BRAIN_PID)"
        break
      fi
    done
    if [[ -z "$BRAIN_PID" ]]; then
      log "[WARN] 脑模型可能未启动，检查日志:"
      tail -5 "$BRAIN_LOG" 2>/dev/null || true
    fi
  fi

  # 窗口 1: SM64（如果提供了 ROM）
  if [[ -n "$ROM_PATH" ]]; then
    if [[ ! -f "$ROM_PATH" ]]; then
      log "[WARN] ROM 文件不存在: $ROM_PATH，跳过 SM64"
    else
      SM64_DIR="$PROJECT_DIR/.cache/sm64ex"
      SM64_BIN="$SM64_DIR/build/us_pc/sm64.us.f3dex2e"

      if [[ ! -f "$SM64_BIN" ]]; then
        log "[WARN] SM64 编译产物不存在 ($SM64_BIN)，跳过"
        log "  请先编译: bash $PROJECT_DIR/scripts/setup_sm64.sh $ROM_PATH"
      else
        # 配置 SM64 显示参数（窗口位置、大小、SDL 驱动）
        # WSLg 使用 Weston (Wayland) + XWayland 提供 X11 兼容
        # SDL2 默认自动检测 x11 驱动，显式指定确保稳定
        # DISPLAY=:0 通过 XWayland 桥接到 WSLg → Windows 桌面

        # 准备配置文件
        local sm64_config="$PROJECT_DIR/runtime/sm64config.txt"
        if [[ ! -f "$sm64_config" ]]; then
          if [[ -f "$PROJECT_DIR/config/sm64config.txt" ]]; then
            cp "$PROJECT_DIR/config/sm64config.txt" "$sm64_config"
            log "已复制 SM64 默认配置到 runtime"
          else
            log "[WARN] SM64 默认配置不存在，使用 SM64 内置默认值"
          fi
        fi

        # 配置窗口位置和大小
        if [[ -f "$sm64_config" ]]; then
          setup_sm64_display "$sm64_config" 590 443 18 160
        fi

        log "创建 SM64 窗口..."
        tmux new-window -t "$TMUX_SESSION" -n "sm64" bash

        # WSLg 显示栈: SDL x11 → XWayland → Weston → RDP → Windows 桌面
        # DISPLAY=:0 是 XWayland 端点
        # SDL_VIDEODRIVER=x11 强制 X11 后端（绕过 Wayland 后端可能的兼容问题）
        # WAYLAND_DISPLAY=wayland-0 保留让 SDL 可自动选择
        tmux send-keys -t "$TMUX_SESSION:1" \
          "cd $SM64_DIR && \
           echo '' && \
           echo '===== SM64 Game =====' && \
           echo 'WSLg display: DISPLAY=:0 SDL_VIDEODRIVER=x11' && \
           echo 'Please wait for game window to appear...' && \
           rm -f /tmp/sm64_window_ready && \
           setsid nohup env DISPLAY=:0 SDL_VIDEODRIVER=x11 \
             WAYLAND_DISPLAY=wayland-0 \
             FLY64_BRIDGE=$BRIDGE_PATH \
             $SM64_BIN --skip-intro \
             --configfile $sm64_config \
             > $SM64_LOG 2>&1 </dev/null & \
           SM64PID=\$! && \
           echo \"SM64 PID: \$SM64PID\" && \
           touch /tmp/sm64_window_ready && \
           echo 'Window launched - check your Windows desktop'" Enter

        # 等待窗口出现
        sleep 4
        SM64_PID=$(find_sm64_pid)
        if [[ -n "$SM64_PID" ]]; then
          # 验证窗口是否显示
          local WID
          WID=$(xdotool search --name "Super Mario" 2>/dev/null | head -1 || true)
          if [[ -n "$WID" ]]; then
            log "SM64 窗口已显示 (PID: $SM64_PID, Window ID: $WID)"
          else
            log "SM64 进程已运行 (PID: $SM64_PID)，等待窗口显示..."
            sleep 3
            WID=$(xdotool search --name "Super Mario" 2>/dev/null | head -1 || true)
            if [[ -n "$WID" ]]; then
              log "SM64 窗口已显示 (PID: $SM64_PID, Window ID: $WID)"
            else
              log "[WARN] SM64 进程在运行但窗口未检测到（可能在其他桌面/虚拟屏幕）"
            fi
          fi
        else
          log "[WARN] SM64 可能未启动，检查日志:"
          tail -5 "$SM64_LOG" 2>/dev/null || true
        fi
      fi
    fi
  fi

  # 窗口 2: 监控终端（tail 日志）
  tmux new-window -t "$TMUX_SESSION" -n "monitor" bash
  tmux send-keys -t "$TMUX_SESSION:2" \
    "cd $PROJECT_DIR && \
     echo '===== Monitor =====' && \
     echo 'Waiting 5s for logs...' && \
     sleep 5 && \
     echo '--- Brain log (last 20) ---' && \
     tail -20 $BRAIN_LOG 2>/dev/null || echo '(no brain log yet)' && \
     echo '' && \
     echo '--- SM64 log (last 20) ---' && \
     tail -20 $SM64_LOG 2>/dev/null || echo '(no sm64 log yet)' && \
     echo '' && \
     echo 'Tail -f brain log:' && \
     tail -f $BRAIN_LOG" Enter

  echo ""
  log "================================================================"
  log " Fly64 启动完成"
  log "  tmux 会话: $TMUX_SESSION"
  log "  脑模型    : PID $(find_brain_pid || echo 'N/A')"
  log "  SM64      : PID $(find_sm64_pid || echo '未启动')"
  log "  仪表板    : http://127.0.0.1:8765/"
  log "  日志目录  :"
  log "    脑模型  : $BRAIN_LOG"
  log "    SM64    : $SM64_LOG"
  log "  操作:"
  log "    附加终端: tmux attach -t $TMUX_SESSION"
  log "    查看状态: bash scripts/wsl_launcher.sh --status"
  log "    停止    : bash scripts/wsl_launcher.sh --stop"
  log "================================================================"
}

# ---- 附加 tmux ---------------------------------------------------------------
cmd_attach() {
  if tmux_has_session; then
    exec tmux attach-session -t "$TMUX_SESSION"
  else
    err "tmux 会话 [$TMUX_SESSION] 不存在。先运行: bash scripts/wsl_launcher.sh --launch"
  fi
}

# ---- WSL 持久模式检查 -------------------------------------------------------
# tmux server 由 WSL init 直接管理，无需 systemd
check_persistence() {
  log "进程持久性确认..."
  # 验证 tmux server 的父进程
  TMUX_SERVER_PID=$(pgrep -f "tmux.*server" 2>/dev/null | head -1 || true)
  if [[ -n "$TMUX_SERVER_PID" ]]; then
    TMUX_PARENT=$(ps -o ppid= -p "$TMUX_SERVER_PID" 2>/dev/null | xargs || echo "?")
    log "  tmux server PID: $TMUX_SERVER_PID, PPID: $TMUX_PARENT"
    if [[ "$TMUX_PARENT" == "1" ]]; then
      log "  ✓ tmux server 由 init (PID 1) 管理，不受 shell 生命周期影响"
    else
      log "  ℹ tmux server PPID=$TMUX_PARENT (非 init，但 tmux 自身可守护)"
    fi
  fi
  BRAIN_PID=$(find_brain_pid)
  if [[ -n "$BRAIN_PID" ]]; then
    BRAIN_PPID=$(ps -o ppid= -p "$BRAIN_PID" 2>/dev/null | xargs || echo "?")
    log "  脑模型 PPID: $BRAIN_PPID"
    log "  ✓ 脑模型已脱离终端，独立进程树运行"
  fi
}

# ---- 主流程 ---------------------------------------------------------------
case "$ACTION" in
  launch)
    cmd_launch
    check_persistence
    ;;
  restart)
    cmd_stop
    sleep 2
    cmd_launch
    check_persistence
    ;;
  stop)  cmd_stop  ;;
  status) cmd_status ;;
  attach) cmd_attach ;;
  *) err "未知操作: $ACTION" ;;
esac