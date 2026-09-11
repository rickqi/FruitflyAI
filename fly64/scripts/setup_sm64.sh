#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROM_PATH="${1:?usage: setup_sm64.sh /absolute/path/to/baserom.us.z64}"
SM64_DIR="$PROJECT_DIR/.cache/sm64ex"
PIN="d7ca2c04364a6dd0dac58b47151e04e26887e6f0"
ROM_SHA="$(shasum -a 1 "$ROM_PATH" | cut -d ' ' -f1)"
if [[ "$ROM_SHA" != "9bef1128717f958171a4afac3ed78ee2bb4e86ce" ]]; then
  echo "ROM validation failed: expected unmodified US .z64 (SHA-1 9bef1128717f958171a4afac3ed78ee2bb4e86ce)." >&2
  exit 2
fi

if [[ ! -d "$SM64_DIR/.git" ]]; then
  git clone https://github.com/sm64pc/sm64ex.git "$SM64_DIR"
fi
if [[ "$(git -C "$SM64_DIR" rev-parse HEAD)" != "$PIN" ]]; then
  git -C "$SM64_DIR" fetch origin "$PIN"
  git -C "$SM64_DIR" checkout --detach "$PIN"
fi
if git -C "$SM64_DIR" apply --check "$PROJECT_DIR/patches/sm64ex-fly64.patch" 2>/dev/null; then
  git -C "$SM64_DIR" apply "$PROJECT_DIR/patches/sm64ex-fly64.patch"
elif git -C "$SM64_DIR" apply --reverse --check "$PROJECT_DIR/patches/sm64ex-fly64.patch" 2>/dev/null; then
  echo "Fly64 patch is already applied."
else
  echo "The Fly64 SM64 patch does not apply cleanly at pinned commit $PIN" >&2
  exit 1
fi

cp "$ROM_PATH" "$SM64_DIR/baserom.us.z64"

missing=()
for formula in make sdl2 glew pkg-config mingw-w64; do
  brew list "$formula" >/dev/null 2>&1 || missing+=("$formula")
done
if [[ ${#missing[@]} -gt 0 ]]; then
  HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install "${missing[@]}"
fi

cd "$SM64_DIR"
export PATH="$(brew --prefix pkgconf)/bin:$PATH"
# This 2021 nightly's generated-asset rules are not parallel-safe on modern
# GNU Make; a serial first build is deterministic and incremental rebuilds are fast.
gmake -j1 VERSION=us \
  CC=clang CXX=clang++ CPP="clang -E -P -x c" \
  BETTERCAMERA=1 NODRAWINGDISTANCE=1 EXT_OPTIONS_MENU=1
