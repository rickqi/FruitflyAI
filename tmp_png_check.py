import struct, os, pathlib

d = pathlib.Path("/root/fly64/runtime/coach_frames")
for f in sorted(d.glob("*.png")):
    data = f.read_bytes()
    magic_ok = data[:8] == b"\x89PNG\r\n\x1a\n"
    w = h = 0
    if len(data) >= 33:
        w, h = struct.unpack(">II", data[16:24])
    print(f"{f.name:65s} size={len(data):>6}  PNG={magic_ok}  {w}x{h}{' ⚠️' if not magic_ok or (w==0 and h==0 and len(data)>0) else ''}")