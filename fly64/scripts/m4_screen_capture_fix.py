#!/usr/bin/env python3
"""Screen-fidelity fix (R31-fix2): move the coach screen capture from the
tail of the observer (cubemap) pass — where it read a partial, mid-frame,
observer-camera image — to the end of gfx_run() after the game frame is
fully rendered, with explicit default-framebuffer bind and Y-flip."""
import pathlib, sys

ROOT = pathlib.Path("/root/fly64/.cache/sm64ex")
ok = True

def edit(rel, old, new):
    global ok
    p = ROOT / rel
    s = p.read_text()
    if old not in s:
        print(f"MISS: {rel}")
        ok = False
        return
    p.write_text(s.replace(old, new, 1))
    print(f"OK:   {rel}")

VIS = "src/pc/fly64_vision.c"

# 1. Remove the wrong-capture block from the observer pass tail
edit(VIS,
"""    fly64_bridge_publish_frame(atlas, pose, gGlobalTimer, (clock_seconds() - started) * 1000);
    // EVO R21: capture game screen for LLM coach
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    int sw = old_viewport[2], sh = old_viewport[3];
    unsigned char screen_buf[FLY64_SCREEN_WIDTH * FLY64_SCREEN_HEIGHT * 3];
    memset(screen_buf, 0, sizeof(screen_buf));
    if (sw > 0 && sh > 0) {
        glReadPixels(0, 0, sw < FLY64_SCREEN_WIDTH ? sw : FLY64_SCREEN_WIDTH,
                     sh < FLY64_SCREEN_HEIGHT ? sh : FLY64_SCREEN_HEIGHT,
                     GL_RGB, GL_UNSIGNED_BYTE, screen_buf);
    }
    fly64_bridge_write_screen(screen_buf);
    glPixelStorei(GL_PACK_ALIGNMENT, old_pack);""",
"""    fly64_bridge_publish_frame(atlas, pose, gGlobalTimer, (clock_seconds() - started) * 1000);
    /* R31-fix2: the coach screen capture moved out of this observer pass —
     * reading here grabbed a partial, mid-frame, observer-camera image.
     * See fly64_vision_capture_screen(), called from gfx_run() after the
     * game frame is fully rendered. */""")

# 2. Append the new capture function at end of vision.c
p = ROOT / VIS
if "fly64_vision_capture_screen" not in p.read_text():
    cap = """

/* R31-fix2: capture the actual game frame for the LLM coach.
 * Called from gfx_run() right after gfx_rapi->end_frame() and before the
 * swap — at that point the default framebuffer holds the COMPLETE game
 * frame drawn with the player camera.  Binds FB0 explicitly, honours the
 * client viewport, and flips bottom-up GL pixels into top-down layout so
 * the PNG the coach sees matches the game screen 1:1. */
void fly64_vision_capture_screen(void) {
    if (!shared) return;
    static unsigned char buf[FLY64_SCREEN_WIDTH * FLY64_SCREEN_HEIGHT * 3];
    static unsigned char block[FLY64_SCREEN_WIDTH * FLY64_SCREEN_HEIGHT * 3];
    GLint vp[4];
    GLint old_pack = 1, old_fb = 0;
    glGetIntegerv(GL_VIEWPORT, vp);
    glGetIntegerv(GL_PIXEL_PACK_ALIGNMENT, &old_pack);
    glGetIntegerv(GL_FRAMEBUFFER_BINDING, &old_fb);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    memset(buf, 0, sizeof(buf));
    int w = vp[2] < FLY64_SCREEN_WIDTH ? vp[2] : FLY64_SCREEN_WIDTH;
    int h = vp[3] < FLY64_SCREEN_HEIGHT ? vp[3] : FLY64_SCREEN_HEIGHT;
    if (w > 0 && h > 0) {
        glReadPixels(vp[0], vp[1], w, h, GL_RGB, GL_UNSIGNED_BYTE, block);
        for (int y = 0; y < h; ++y) {
            int dst = FLY64_SCREEN_HEIGHT - 1 - (vp[3] > FLY64_SCREEN_HEIGHT
                        ? y + (vp[3] - FLY64_SCREEN_HEIGHT) / 2 : y);
            if (dst < 0 || dst >= FLY64_SCREEN_HEIGHT) continue;
            memcpy(buf + dst * FLY64_SCREEN_WIDTH * 3,
                   block + y * w * 3, w * 3);
        }
    }
    glBindFramebuffer(GL_FRAMEBUFFER, old_fb);
    glPixelStorei(GL_PACK_ALIGNMENT, old_pack);
    if (glGetError() != GL_NO_ERROR) memset(buf, 0, sizeof(buf));
    fly64_bridge_write_screen(buf);
}
"""
    with open(p, "a") as fh:
        fh.write(cap)
    print("OK:   capture function appended to fly64_vision.c")

# 3. Header declaration
H = "src/pc/fly64_bridge.h"
edit(H,
"#endif",
"void fly64_vision_capture_screen(void);\n\n#endif")

# 4. Call from gfx_run after end_frame, before swap
edit("src/pc/gfx/gfx_pc.c",
"""    fly64_vision_render();
    gfx_rapi->end_frame();
    gfx_wapi->swap_buffers_begin();""",
"""    fly64_vision_render();
    gfx_rapi->end_frame();
    /* R31-fix2: capture the finished game frame for the LLM coach */
    fly64_vision_capture_screen();
    gfx_wapi->swap_buffers_begin();""")

sys.exit(0 if ok else 1)
