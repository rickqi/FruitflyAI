#!/usr/bin/env python3
import pathlib, re
p = pathlib.Path("/root/fly64/.cache/sm64ex/src/pc/fly64_vision.c")
s = p.read_text()
start = s.index("void fly64_vision_capture_screen(void) {")
end = s.index("\n}\n", start) + 3
new_fn = """void fly64_vision_capture_screen(void) {
    static int dbg = -1;
    if (dbg < 0) dbg = getenv("FLY64_CAPTURE_DEBUG") ? 1 : 0;
    if (!fly64_bridge_connected()) return;
    static unsigned char buf[FLY64_SCREEN_WIDTH * FLY64_SCREEN_HEIGHT * 3];
    static unsigned char block[FLY64_SCREEN_WIDTH * FLY64_SCREEN_HEIGHT * 3];
    if (dbg) fprintf(stderr, "Fly64: capture enter\\n");
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    memset(buf, 0, sizeof(buf));
    /* No glGet* state queries here: mid-pipeline glGetIntegerv segfaults on
     * this driver (R31-fix2 debugging).  glReadPixels alone matches what the
     * old R21 code did safely; the default framebuffer holds the finished
     * game frame right after gfx_rapi->end_frame(). */
    glReadPixels(0, 0, FLY64_SCREEN_WIDTH, FLY64_SCREEN_HEIGHT,
                 GL_RGB, GL_UNSIGNED_BYTE, block);
    for (int y = 0; y < FLY64_SCREEN_HEIGHT; ++y) {
        memcpy(buf + y * FLY64_SCREEN_WIDTH * 3,
               block + (FLY64_SCREEN_HEIGHT - 1 - y) * FLY64_SCREEN_WIDTH * 3,
               FLY64_SCREEN_WIDTH * 3);
    }
    if (glGetError() != GL_NO_ERROR) memset(buf, 0, sizeof(buf));
    fly64_bridge_write_screen(buf);
    if (dbg) fprintf(stderr, "Fly64: capture exit\\n");
}
"""
p.write_text(s[:start] + new_fn)
print("capture rewritten (no GL state queries)")
