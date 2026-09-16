#!/bin/bash
# Phase 1+2 live deployment sync (dev repo -> /root/fly64), patch+rebuild sm64ex
set -e
DEV=/mnt/d/codes/flygym/fly64
DEP=/root/fly64
FILES="fly64/bridge.py fly64/main.py fly64/model.py fly64/motor_primitives.py \
tests/test_bridge.py tests/test_motor_primitives.py tests/test_dashboard_protocol.py \
skills/skills.md patches/sm64ex-fly64.patch"
echo "== sync =="
for f in $FILES; do
  if ! diff -q "$DEP/$f" "$DEV/$f" >/dev/null 2>&1; then
    cp "$DEV/$f" "$DEP/$f"; echo "synced: $f"
  fi
done
echo "== run sync'd tests on deployment =="
cd "$DEP"
./venv/bin/python -m pytest tests/test_motor_primitives.py tests/test_bridge.py -q 2>&1 | tail -2
echo "== patch + rebuild sm64ex =="
cd "$DEP/.cache/sm64ex"
# reverse-apply old patch if present, re-apply the new one
git apply -R patches_fly64_old.patch 2>/dev/null || true
if git apply --check ../../patches/sm64ex-fly64.patch 2>/dev/null; then
  git apply ../../patches/sm64ex-fly64.patch && echo "patch applied fresh"
else
  echo "patch already applied (check) — trying reverse+forward"
  git apply -R ../../patches/sm64ex-fly64.patch 2>/dev/null || true
  git apply ../../patches/sm64ex-fly64.patch && echo "patch re-applied"
fi
cp ../../patches/sm64ex-fly64.patch patches_fly64_old.patch
make -j"$(nproc)" VERSION=us BETTERCAMERA=1 NODRAWINGDISTANCE=1 EXT_OPTIONS_MENU=1 2>&1 | tail -3
ls -la build/us_pc/sm64.us.f3dex2e
echo "== BUILD OK =="
