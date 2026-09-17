#!/usr/bin/env python3
import pathlib
p = pathlib.Path("/root/fly64/.cache/sm64ex/src/pc/fly64_vision.c")
s = p.read_text()
old = """void fly64_vision_capture_screen(void) {
    if (!fly64_bridge_connected()) return;"""
new = """void fly64_vision_capture_screen(void) {
    static int dbg = -1;
    if (dbg < 0) dbg = getenv("FLY64_CAPTURE_DEBUG") ? 1 : 0;
    if (dbg) fprintf(stderr, "Fly64: capture enter\\n");
    if (!fly64_bridge_connected()) return;"""
assert old in s
s = s.replace(old, new)
old2 = """    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    memset(buf, 0, sizeof(buf));"""
new2 = """    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    if (dbg) fprintf(stderr, "Fly64: capture fb0 bound\\n");
    memset(buf, 0, sizeof(buf));"""
assert old2 in s
s = s.replace(old2, new2)
old3 = """    glBindFramebuffer(GL_FRAMEBUFFER, old_fb);
    glPixelStorei(GL_PACK_ALIGNMENT, old_pack);
    if (glGetError() != GL_NO_ERROR) memset(buf, 0, sizeof(buf));
    fly64_bridge_write_screen(buf);"""
new3 = """    glBindFramebuffer(GL_FRAMEBUFFER, old_fb);
    glPixelStorei(GL_PACK_ALIGNMENT, old_pack);
    if (dbg) fprintf(stderr, "Fly64: capture read done\\n");
    if (glGetError() != GL_NO_ERROR) memset(buf, 0, sizeof(buf));
    fly64_bridge_write_screen(buf);
    if (dbg) fprintf(stderr, "Fly64: capture exit\\n");"""
assert old3 in s
s = s.replace(old3, new3)
p.write_text(s)
print("breadcrumbs added (enable FLY64_CAPTURE_DEBUG=1)")
