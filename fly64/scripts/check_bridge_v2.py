#!/usr/bin/env python3
"""Check SM64 bridge for live frame data - using direct file I/O."""
import struct
import numpy as np

path = "/tmp/f64b_traj"

with open(path, "rb") as f:
    data = f.read()

header_size = 128
frame_bytes = 384 * 256 * 3

hdr = struct.unpack_from("<8sIIIIQbbHI", data, 0)
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
frame = np.frombuffer(data[128:128+frame_bytes], dtype=np.uint8).reshape(256, 384, 3)
print(f"\n=== Frame ===")
print(f"  Shape:      {frame.shape}")
print(f"  Pixel min:  {frame.min()}")
print(f"  Pixel max:  {frame.max()}")
print(f"  Pixel mean: {frame.mean():.2f}")
nonzero = (frame > 0).sum()
total = frame.size
print(f"  Non-zero:   {nonzero} / {total} = {100 * nonzero / total:.1f}%")

if hdr[2] > 0 and nonzero > total * 0.01:
    print("\nRESULT: SM64 IS PRODUCING LIVE FRAMES!")
elif hdr[2] > 0:
    print("\nRESULT: Bridge connected but frames may be dark")
else:
    print("\nRESULT: SM64 NOT writing frames to bridge (frame_seq=0)")