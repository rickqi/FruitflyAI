#!/bin/bash
set -e
cd /root/fly64/.cache/sm64ex
make -j"$(nproc)" VERSION=us BETTERCAMERA=1 NODRAWINGDISTANCE=1 EXT_OPTIONS_MENU=1 2>&1 | grep -E 'error|warning.*fly64|CC.*fly64|nothing' | head -8
ls -la build/us_pc/sm64.us.f3dex2e
echo BUILD_DONE
