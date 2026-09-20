#!/usr/bin/env python3
"""Check SM64 bridge for live frame data."""
import mmap, os, struct
import numpy as np

path = "/tmp/f64b_traj"
if not os.path.exists(path):
    print("Bridge file not found at", path)
    exit(1)

fd = os.open(path, os.O_RDONLY)
mm = mmap.mmap(fd, 525440)

# Read header
hdr = struct.unpack_from("<8sIIIIQbbHI", mm, 0)
print("=== Bridge Header ===")
print(f"  Magic:      {hdr[0]}")
print(f"  Version:    {hdr[1]}")
print(f"  Frame Seq:  {hdr[2]}")
print(f"  Ctrl  Seq:  {hdr[3]}")
print(f"  Enabled:    {hdr[4]}")
print(f"  Heartbeat:  {hdr[5]}")
print(f"  X,Y:        {hdr[6]}, {hdr[7]}")
print(f"  Buttons:    {hdr[8]}")

# Read frame data
frame = np.frombuffer(mm[128:128+384*256*3], dtype=np.uint8).reshape(256, 384, 3)
print(f"\n=== Frame ===")
print(f"  Shape:      {frame.shape}")
print(f"  Pixel min:  {frame.min()}")
print(f"  Pixel max:  {frame.max()}")
print(f"  Pixel mean: {frame.mean():.2f}")
print(f"  Non-zero:   {(frame > 0).sum()}")

# Check if there's meaningful content
nonzero_pixels = (frame > 0).sum()
total_pixels = 384 * 256 * 3
pct = 100 * nonzero_pixels / total_pixels
print(f"  Non-zero%:  {pct:.1f}%")

mm.close()
os.close(fd)

if hdr[2] > 0 and pct > 1:
    print("\nRESULT: SM64 IS PRODUCING LIVE FRAMES!")
elif hdr[2] > 0:
    print("\nRESULT: Bridge connected but frames may be dark")
else:
    print("\nRESULT: SM64 NOT writing frames to bridge (frame_seq=0)")