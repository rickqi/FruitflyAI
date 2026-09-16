#!/bin/bash
set -e
SRC=/root/fly64/.cache/sm64ex
OUT=/mnt/d/codes/flygym/fly64/patches/sm64ex-fly64.patch
cd "$SRC"
git add -A src/pc/fly64_bridge.c src/pc/fly64_bridge.h src/pc/fly64_vision.c src/pc/fly64_vision.h 2>/dev/null || true
# The deployed tree = upstream sm64ex (d7ca2c0) + full fly64 patch (old + Z
# increment + R21 screen/glew hotfixes).  Regenerate the patch from the
# complete working-tree diff so applying it to a fresh checkout reproduces
# the deployed state exactly.
git diff --binary HEAD -- src/pc/ levels/entry.c src/game/level_geo.c src/game/level_update.c src/game/mario.c src/game/rendering_graph_node.c src/pc/controller/controller_entry_point.c src/pc/gfx/gfx_opengl.c src/pc/gfx/gfx_pc.c src/pc/gfx/gfx_pc.h src/pc/gfx/gfx_sdl2.c Makefile > "$OUT"
echo "new patch lines: $(wc -l < $OUT)"
grep -c 'z_frames' "$OUT" || echo "WARN: no z_frames in patch"
grep -c 'fly64_bridge_write_screen' "$OUT" || echo "WARN: no screen hotfix in patch"
