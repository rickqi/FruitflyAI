#!/usr/bin/env python3
"""Phase 1 Z-trigger unlock: minimal incremental edits to DEPLOYED C files
(preserving EVO R21 screen/glew hotfixes not yet in the committed patch)."""
import pathlib, sys

ROOT = pathlib.Path("/root/fly64/.cache/sm64ex")
edits_ok = True

def edit(rel, old, new, count=1):
    global edits_ok
    p = ROOT / rel
    s = p.read_text()
    if s.count(old) < count:
        print(f"MISS: {rel}: pattern not found:\n{old[:120]}")
        edits_ok = False
        return
    s = s.replace(old, new, count)
    p.write_text(s)
    print(f"OK:   {rel}")

C = "src/pc/fly64_bridge.c"
H = "src/pc/fly64_bridge.h"

# 1. statics
edit(C, "static unsigned jump_frames;", "static unsigned jump_frames, b_frames, z_frames;")
edit(C, "static uint32_t last_jump_event;", "static uint32_t last_jump_event, last_b_event, last_z_event;")
# 2. locals
edit(C, "uint32_t jump_event;", "uint32_t jump_event, b_event, z_event;")
# 3. disabled reset
edit(C, "if (!shared->h.enabled) { jump_frames = 0; return; }",
        "if (!shared->h.enabled) { jump_frames = b_frames = z_frames = 0; return; }")
# 4. event reads inside seqlock
edit(C, "jump_event = shared->h.reserved;",
        "jump_event = shared->h.reserved; b_event = shared->h.b_event; z_event = shared->h.z_event;")
# 5. stale reset
edit(C, "if (monotonic_ns() - heartbeat > FLY64_STALE_NS) { jump_frames = 0;",
        "if (monotonic_ns() - heartbeat > FLY64_STALE_NS) { jump_frames = b_frames = z_frames = 0;")
# 6. event diff -> frames
edit(C, "if (jump_event != last_jump_event) { jump_frames = 2; last_jump_event = jump_event; }",
        "if (jump_event != last_jump_event) { jump_frames = 2; last_jump_event = jump_event; }\n"
        "    if (b_event != last_b_event) { b_frames = 2; last_b_event = b_event; }\n"
        "    if (z_event != last_z_event) { z_frames = 2; last_z_event = z_event; }")
# 7. button masking + pulse injection
edit(C, "buttons &= ~A_BUTTON;",
        "buttons &= ~(A_BUTTON | B_BUTTON | Z_TRIG);")
edit(C, "if (jump_frames) { buttons |= A_BUTTON; --jump_frames; }",
        "if (jump_frames) { buttons |= A_BUTTON; --jump_frames; }\n"
        "    if (b_frames) { buttons |= B_BUTTON; --b_frames; }\n"
        "    if (z_frames) { buttons |= Z_TRIG; --z_frames; }")
# 8. header struct: split extension into b/z event counters (size stays 40)
edit(H, "uint8_t extension[40];",
        "uint32_t b_event, z_event; uint8_t extension[32]; /* v2.14: b/z pulse events */")

sys.exit(0 if edits_ok else 1)
