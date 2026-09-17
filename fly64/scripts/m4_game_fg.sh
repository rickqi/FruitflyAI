#!/bin/bash
cd /root/fly64/.cache/sm64ex
timeout 12 env FLY64_BRIDGE=/tmp/f64b_traj ./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/game_fg.log 2>&1
echo "exit=$?"
grep -viE 'alsa|sdl_aud' /tmp/game_fg.log | tail -6
