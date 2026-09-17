#!/usr/bin/env python3
import pathlib
p = pathlib.Path("/root/fly64/.cache/sm64ex/src/pc/fly64_vision.c")
s = p.read_text()
s = s.replace("void fly64_vision_capture_screen(void) {\n    if (!shared) return;",
              "void fly64_vision_capture_screen(void) {\n    if (!fly64_bridge_connected()) return;")
s = s.replace("glGetIntegerv(GL_PIXEL_PACK_ALIGNMENT, &old_pack);",
              "glGetIntegerv(GL_PACK_ALIGNMENT, &old_pack);")
s = s.replace("glGetIntegerv(GL_FRAMEBUFFER_BINDING, &old_fb);",
              "glGetIntegerv(GL_FRAMEBUFFER_BINDING, &old_fb); /* GLEW: GL_FRAMEBUFFER_BINDING */")
p.write_text(s)
print("patched")
