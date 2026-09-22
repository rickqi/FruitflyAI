#!/bin/bash
# Fly64 Full Launch Script — 支持 WSLg / xvfb 双显示模式
# Usage: bash launch_full.sh [wslg|xvfb]
# 默认: wslg（Windows 桌面弹出游戏窗口）

exec > /tmp/launch.log 2>&1
set -x

DISPLAY_MODE="${1:-wslg}"  # wslg (default) or xvfb

# === Start brain ===
cd /root/fly64
export PYTHONPATH=/root/fly64
rm -f /tmp/f64b_traj /tmp/f64r_traj.npz
setsid nohup python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0 &
BRAIN_PID=$!
echo BRAIN_STARTED $BRAIN_PID

# Wait for brain
for i in $(seq 1 20); do
    python3 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/',timeout=3); exit(0)" 2>/dev/null && break
    sleep 2
done
echo BRAIN_READY

# === Start SM64 ===
cd /root/fly64/.cache/sm64ex
export FLY64_BRIDGE=/tmp/f64b_traj

if [ "$DISPLAY_MODE" = "xvfb" ]; then
    # xvfb 虚拟显示模式（无窗口，帧渲染可靠）
    echo DISPLAY_MODE=xvfb
    setsid nohup xvfb-run -s '-screen 0 640x480x24' --auto-servernum \
        ./build/us_pc/sm64.us.f3dex2e --skip-intro &
else
    # WSLg 显示模式（默认，窗口会出现在 Windows 桌面）
    echo DISPLAY_MODE=wslg
    export DISPLAY=:0
    export SDL_VIDEODRIVER=x11
    setsid nohup ./build/us_pc/sm64.us.f3dex2e --skip-intro &
fi

SM64_PID=$!
echo SM64_STARTED $SM64_PID

# === Display monitoring ===
sleep 8

if [ "$DISPLAY_MODE" = "wslg" ]; then
    # Check window position and repair if off-screen
    WID=$(export DISPLAY=:0; xdotool search --name "Super Mario" 2>/dev/null | head -1 || true)
    if [ -n "$WID" ]; then
        GEO=$(export DISPLAY=:0; xdotool getwindowgeometry $WID 2>/dev/null || true)
        X=$(echo "$GEO" | grep "Position" | awk '{print $2}' | cut -d, -f1 || echo "0")
        Y=$(echo "$GEO" | grep "Position" | awk '{print $2}' | cut -d, -f2 || echo "0")
        # Screen dimensions from xdpyinfo
        SCREEN_W=$(xdpyinfo 2>/dev/null | grep "dimensions" | awk '{print $2}' | cut -dx -f1 || echo "3840")
        SCREEN_H=$(xdpyinfo 2>/dev/null | grep "dimensions" | awk '{print $2}' | cut -dx -f2 || echo "2560")
        # If window is off-screen or unreasonably positioned
        if [ "$X" -lt -100 ] || [ "$X" -gt "$SCREEN_W" ] || [ "$Y" -lt -100 ] || [ "$Y" -gt "$SCREEN_H" ]; then
            echo "WINDOW_OFFSCREEN: pos=$X,$Y on ${SCREEN_W}x${SCREEN_H} — attempting repair"
            export DISPLAY=:0
            xdotool windowmove $WID 200 200 2>/dev/null || true
            xdotool windowraise $WID 2>/dev/null || true
            NEWGEO=$(xdotool getwindowgeometry $WID 2>/dev/null || true)
            echo "WINDOW_REPAIR: $NEWGEO"
        else
            echo "WINDOW_OK: pos=$X,$Y on ${SCREEN_W}x${SCREEN_H}"
        fi
    else
        echo "WINDOW_NOT_FOUND: no SM64 window detected"
    fi
fi

echo FINAL_CHECK
ps aux | grep -E 'fly64|sm64' | grep -v grep