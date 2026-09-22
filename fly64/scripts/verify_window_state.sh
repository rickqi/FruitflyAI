#!/bin/bash
# Verify SM64 window state — WSLg + xvfb 双模式支持
set -euo pipefail

echo "=========================================="
echo " SM64 Window State Verification"
echo "=========================================="

echo ""
echo "--- 1. SM64 Process ---"
SM64PID=$(pgrep -f "sm64.us.f3dex2e" 2>/dev/null | head -1 || true)
if [ -n "$SM64PID" ]; then
    echo "PASS: SM64 running (PID=$SM64PID)"
    ps -p $SM64PID -o pid,ppid,state,pcpu,pmem,etime --no-headers 2>/dev/null || true
else
    echo "FAIL: SM64 not running"
fi

echo ""
echo "--- 2. Display Mode ---"
# Detect which mode SM64 is using
if [ -n "$SM64PID" ]; then
    ENV_DISPLAY=$(cat /proc/$SM64PID/environ 2>/dev/null | tr '\0' '\n' | grep "^DISPLAY=" | cut -d= -f2 || true)
    ENV_SDL=$(cat /proc/$SM64PID/environ 2>/dev/null | tr '\0' '\n' | grep "^SDL_VIDEODRIVER" | cut -d= -f2 || true)
    echo "Mode: DISPLAY=$ENV_DISPLAY SDL_VIDEODRIVER=$ENV_SDL"
    if echo "$ENV_DISPLAY" | grep -q ":"; then
        echo "DISPLAY_MODE=wslg (X11/Wayland via WSLg)"
    else
        echo "DISPLAY_MODE=xvfb (virtual framebuffer, no visible window)"
    fi
fi

echo ""
echo "--- 3. SM64 Window ---"
WID=$(export DISPLAY=:0; xdotool search --name "Super Mario" 2>/dev/null | head -1 || true)
if [ -n "$WID" ]; then
    echo "PASS: WSLg window found (ID=$WID)"
    GEO=$(export DISPLAY=:0; xdotool getwindowgeometry $WID 2>/dev/null || true)
    echo "$GEO"
    XPX=$(echo "$GEO" | grep "Position" | awk '{print $2}' | cut -d, -f1 || echo "0")
    YPX=$(echo "$GEO" | grep "Position" | awk '{print $2}' | cut -d, -f2 || echo "0")
    SCR=$(xdpyinfo 2>/dev/null | grep "dimensions" | awk '{print $2}' || echo "0x0")
    SCRW=$(echo "$SCR" | cut -dx -f1 || echo "3840")
    SCRH=$(echo "$SCR" | cut -dx -f2 || echo "2560")
    
    # Window visibility assessment
    if [ "$XPX" -lt -100 ] || [ "$YPX" -lt -100 ]; then
        echo "WINDOW_STATUS: OFF-SCREEN (pos=$XPX,$YPY on ${SCRW}x${SCRH})"
        echo "AUTO-REPAIR: attempting windowmove..."
        export DISPLAY=:0
        xdotool windowmove $WID 200 200 2>/dev/null || echo "WARN: xdotool windowmove failed (XWayland limitation)"
        NEWGEO=$(xdotool getwindowgeometry $WID 2>/dev/null || true)
        echo "After repair: $NEWGEO"
    elif [ "$XPX" -gt "$SCRW" ] || [ "$YPX" -gt "$SCRH" ]; then
        echo "WINDOW_STATUS: BEYOND-SCREEN (pos=$XPX,$YPX on ${SCRW}x${SCRH})"
        export DISPLAY=:0
        xdotool windowmove $WID 200 200 2>/dev/null || true
    else
        echo "WINDOW_STATUS: ON-SCREEN (pos=$XPX,$YPX on ${SCRW}x${SCRH})"
    fi
    
    WINPID=$(export DISPLAY=:0; xdotool getwindowpid $WID 2>/dev/null || true)
    echo "Window PID: $WINPID"
    if [ "$WINPID" = "$SM64PID" ]; then
        echo "PASS: Window PID matches SM64 process"
    else
        echo "WARN: Window PID ($WINPID) != SM64 PID ($SM64PID)"
    fi
else
    echo "INFO: No WSLg window found (expected in xvfb mode)"
fi

echo ""
echo "--- 4. X11 Display ---"
if [ -S /tmp/.X11-unix/X0 ]; then
    echo "PASS: WSLg X11 socket exists"
else
    echo "INFO: No WSLg X11 socket"
fi
if xdpyinfo 2>/dev/null | grep -q "dimensions"; then
    xdpyinfo 2>/dev/null | grep "dimensions" | head -1
    echo "PASS: WSLg display available"
else
    echo "INFO: WSLg display not accessible (expected in xvfb mode)"
fi

echo ""
echo "--- 5. xrandr ---"
if xrandr 2>/dev/null | grep -q "connected"; then
    xrandr 2>/dev/null | grep " connected" | head -2
    echo "PASS: xrandr detects display"
else
    echo "INFO: xrandr not available"
fi

echo ""
echo "--- 6. SDL Video Driver ---"
SDL_CHECK=/tmp/sdl_check
if [ -x "$SDL_CHECK" ]; then
    export DISPLAY=:0
    $SDL_CHECK 2>/dev/null || echo "SDL check skipped"
else
    echo "SDL probe not compiled (run make on /tmp/sdl_check.c)"
fi

echo ""
echo "--- 7. Bridge ---"
if [ -f /tmp/f64b_traj ]; then
    BRIDGE_SIZE=$(stat -c%s /tmp/f64b_traj 2>/dev/null || echo "?")
    echo "PASS: Bridge file exists ($BRIDGE_SIZE bytes)"
else
    echo "FAIL: No bridge file"
fi

echo ""
echo "=========================================="
echo " Verification Complete"
echo "=========================================="