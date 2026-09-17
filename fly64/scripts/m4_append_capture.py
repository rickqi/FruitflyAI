#!/usr/bin/env python3
import pathlib
p = pathlib.Path("/root/fly64/.cache/sm64ex/src/pc/fly64_vision.c")
s = p.read_text()
if "void fly64_vision_capture_screen(void)" in s:
    print("definition already present")
    raise SystemExit(0)
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
            int src_y = y;
            int dst = FLY64_SCREEN_HEIGHT - 1 - y;
            if (dst < 0 || dst >= FLY64_SCREEN_HEIGHT) continue;
            memcpy(buf + dst * FLY64_SCREEN_WIDTH * 3,
                   block + src_y * w * 3, w * 3);
        }
    }
    glBindFramebuffer(GL_FRAMEBUFFER, old_fb);
    glPixelStorei(GL_PACK_ALIGNMENT, old_pack);
    if (glGetError() != GL_NO_ERROR) memset(buf, 0, sizeof(buf));
    fly64_bridge_write_screen(buf);
}
"""
p.write_text(s + cap)
print("definition appended")
