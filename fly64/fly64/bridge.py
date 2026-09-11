from __future__ import annotations

import mmap
import os
import struct
import time
import ctypes
import sys
from pathlib import Path

MAGIC = b"FLY64V2\0"
WIDTH = 384
HEIGHT = 256
CHANNELS = 3
FRAME_BYTES = WIDTH * HEIGHT * CHANNELS
HEADER = struct.Struct("<8sIIIIQbbHI")
HEADER_SIZE = 128
FILE_SIZE = HEADER_SIZE + FRAME_BYTES
A_BUTTON = 0x8000
# Explicit hardware fences for cross-process seqlocks on Apple Silicon.
if sys.platform == "darwin":
    _memory_barrier = ctypes.CDLL(None).OSMemoryBarrier
    _memory_barrier.argtypes = []
    _memory_barrier.restype = None
else:
    def _memory_barrier():
        raise RuntimeError("Fly64 shared-memory bridge currently targets macOS")


class SharedBridge:
    """Versioned, single-producer/single-consumer mmap shared with sm64ex."""

    def __init__(self, path: str | os.PathLike[str], create: bool = True):
        self.path = Path(path)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
            os.ftruncate(fd, FILE_SIZE)
        else:
            fd = os.open(self.path, os.O_RDWR)
        self._file = os.fdopen(fd, "r+b", buffering=0)
        self.mm = mmap.mmap(self._file.fileno(), FILE_SIZE)
        self._last_frame = (0, bytes(FRAME_BYTES))
        self.frame_metadata = dict(pose=[0., 0., 0., 0.], game_frame=0, render_ms=0.)
        if create:
            self.mm[:HEADER_SIZE] = bytes(HEADER_SIZE)
            self._write_header(0, 0, time.clock_gettime_ns(time.CLOCK_MONOTONIC), 0, 0, 0, 1)
        elif self.mm[:8] != MAGIC or struct.unpack_from("<I", self.mm, 8)[0] != 2:
            self.close()
            raise ValueError("incompatible Fly64 bridge")

    def _write_header(self, frame_seq, control_seq, heartbeat_ns, x, y, buttons, enabled):
        self.mm[: HEADER.size] = HEADER.pack(
            MAGIC, 2, frame_seq, control_seq, enabled, heartbeat_ns, x, y, buttons, 0
        )

    def read_frame(self) -> tuple[int, bytes]:
        for _ in range(3):
            before = struct.unpack_from("<I", self.mm, 12)[0]
            _memory_barrier()
            pixels = self.mm[HEADER_SIZE : HEADER_SIZE + FRAME_BYTES]
            pose = struct.unpack_from("<4fIf", self.mm, 64)
            _memory_barrier()
            after = struct.unpack_from("<I", self.mm, 12)[0]
            if before == after and before % 2 == 0:
                self._last_frame = before, pixels
                self.frame_metadata = dict(pose=list(pose[:4]), game_frame=pose[4], render_ms=pose[5])
                return self._last_frame
        return self._last_frame

    def write_control(self, x: int, y: int, jump: bool, enabled: bool = True) -> None:
        buttons = A_BUTTON if jump else 0
        control_seq = struct.unpack_from("<I", self.mm, 16)[0] | 1
        struct.pack_into("<I", self.mm, 16, control_seq)
        _memory_barrier()
        # The game owns the enabled flag, so F8 cannot be overwritten here.
        # On macOS Python monotonic_ns() is mach_absolute_time, whereas the
        # native game's CLOCK_MONOTONIC includes sleep time. Use the exact same
        # POSIX clock in both processes or every packet can appear days stale.
        struct.pack_into("<Q", self.mm, 24, time.clock_gettime_ns(time.CLOCK_MONOTONIC))
        struct.pack_into("<bbH", self.mm, 32, x, y, buttons)
        if jump:
            event = struct.unpack_from("<I", self.mm, 36)[0]
            struct.pack_into("<I", self.mm, 36, (event + 1) & 0xFFFFFFFF)
        _memory_barrier()
        struct.pack_into("<I", self.mm, 16, (control_seq + 1) & 0xFFFFFFFF)
        if not enabled:
            struct.pack_into("<I", self.mm, 20, 0)

    def write_frame(self, pixels: bytes) -> None:
        if len(pixels) != FRAME_BYTES:
            raise ValueError(f"expected {FRAME_BYTES} RGB bytes, got {len(pixels)}")
        magic, version, seq, ctrl, enabled, heartbeat, x, y, buttons, reserved = HEADER.unpack_from(self.mm)
        odd = (seq + 1) | 1
        struct.pack_into("<I", self.mm, 12, odd)
        _memory_barrier()
        self.mm[HEADER_SIZE : HEADER_SIZE + FRAME_BYTES] = pixels
        _memory_barrier()
        struct.pack_into("<I", self.mm, 12, (odd + 1) & 0xFFFFFFFF)

    @property
    def enabled(self) -> bool:
        return bool(struct.unpack_from("<I", self.mm, 20)[0])

    def game_status(self):
        seq, x, y, buttons, clock, state = struct.unpack_from("<IbbHQI", self.mm, 40)
        age = (time.clock_gettime_ns(time.CLOCK_MONOTONIC) - clock) / 1e6
        return dict(seq=seq, x=x, y=y, jump=bool(buttons & A_BUTTON),
                    age_ms=age, state=state if age < 250 else 4, **self.frame_metadata)

    def close(self) -> None:
        self.mm.close()
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
