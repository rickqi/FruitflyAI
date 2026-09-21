#!/bin/bash
# Verify SM64 window state and display configuration
set -euo pipefail

echo "=========================================="
echo " SM64 WSLg Window State Verification"
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
echo "--- 2. SM64 Window ---"
WID=$(xdotool search --name "Super Mario" 2>/dev/null | head -1 || true)
if [ -n "$WID" ]; then
    echo "PASS: Window found (ID=$WID)"
    xdotool getwindowgeometry $WID 2>/dev/null || true
    WINPID=$(xdotool getwindowpid $WID 2>/dev/null || true)
    echo "Window PID: $WINPID"
    if [ "$WINPID" = "$SM64PID" ]; then
        echo "PASS: Window PID matches SM64 process"
    else
        echo "WARN: Window PID ($WINPID) != SM64 PID ($SM64PID)"
    fi
else
    echo "FAIL: No 'Super Mario' window found"
fi

echo ""
echo "--- 3. X11 Display ---"
if [ -S /tmp/.X11-unix/X0 ]; then
    echo "PASS: X11 socket exists"
else
    echo "FAIL: No X11 socket"
fi
echo "DISPLAY=$DISPLAY"
if xdpyinfo 2>/dev/null | grep -q "dimensions"; then
    xdpyinfo 2>/dev/null | grep "dimensions" | head -1
    echo "PASS: xdpyinfo reports display dimensions"
else
    echo "FAIL: xdpyinfo failed"
fi

echo ""
echo "--- 4. xrandr ---"
XRANDR_OUT=$(xrandr 2>/dev/null | head -5 || true)
if echo "$XRANDR_OUT" | grep -q "connected"; then
    echo "$XRANDR_OUT"
    echo "PASS: xrandr detects connected display"
else
    echo "FAIL: xrandr failed or no display detected"
    echo "$XRANDR_OUT"
fi

echo ""
echo "--- 5. SDL Video Driver ---"
# Build and run minimal SDL video test
cat > /tmp/sdl_check.c << 'EOF'
#include <SDL2/SDL.h>
#include <stdio.h>
int main() {
    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        printf("FAIL: SDL_Init: %s\n", SDL_GetError());
        return 1;
    }
    const char *driver = SDL_GetCurrentVideoDriver();
    int displays = SDL_GetNumVideoDisplays();
    SDL_DisplayMode mode;
    if (displays > 0 && SDL_GetDesktopDisplayMode(0, &mode) == 0) {
        printf("PASS: SDL driver=%s display=%dx%d %dHz\n",
               driver, mode.w, mode.h, mode.refresh_rate);
    } else {
        printf("PARTIAL: driver=%s displays=%d\n", driver, displays);
    }
    SDL_Quit();
    return 0;
}
EOF
gcc -o /tmp/sdl_check /tmp/sdl_check.c -lSDL2 2>/dev/null && /tmp/sdl_check || echo "FAIL: SDL test compile/run failed"

echo ""
echo "--- 6. tmux 'bogus screen size' Warning ---"
echo "ROOT CAUSE: This warning comes from ncurses inside tmux."
echo "When tmux is in a WSL window that doesn't report its terminal size"
echo "correctly, ncurses sees a default size of 131072x1."
echo "This is HARMLESS for SM64 display."
echo ""
echo "FIX: Add to ~/.tmux.conf:"
echo "  set -g default-terminal \"screen-256color\""
echo ""

echo "--- 7. WSLg Compositor ---"
cat /mnt/wslg/versions.txt 2>/dev/null | head -3 || echo "FAIL: No WSLg versions file"

echo ""
echo "=========================================="
echo " Verification Complete"
echo "=========================================="