"""PIN tests: consult frame snapshot must survive the 320×240 screen.json
raw-RGB payload (the t21 silent-drop bug: default 384×256 dims made the PNG
converter pass the frame through unconverted, and the magic check dropped
every snapshot — coach_frames stayed empty)."""
import base64
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin.runner import PluginRunner  # noqa: E402


def _raw_rgb_b64(w=320, h=240):
    import numpy as np
    rng = np.random.default_rng(5)
    raw = rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8).tobytes()
    import base64
    return base64.b64encode(raw).decode("ascii")


def _png_len(w, h):
    return 8 + 25 + len(zlib.compress(b"")) + 12  # rough; not asserted


class TestSnapshot320:
    def test_snapshot_saved_for_320x240_raw_rgb(self, tmp_path):
        r = PluginRunner(fetcher=lambda ep: {})
        frame = _raw_rgb_b64(320, 240)
        out = r.save_consult_frame(frame, "unsolvable_stuck",
                                   ts=1789600000.0, frame_dir=tmp_path)
        assert out is not None, "320x240 raw-RGB frame must be saved, not dropped"
        p = Path(out)
        assert p.exists() and p.stat().st_size > 100
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert "unsolvable_stuck" in p.name

    def test_snapshot_saved_for_384x256_raw_rgb(self, tmp_path):
        r = PluginRunner(fetcher=lambda ep: {})
        frame = _raw_rgb_b64(384, 256)
        out = r.save_consult_frame(frame, frame_dir=tmp_path)
        assert out is not None

    def test_empty_frame_returns_none(self, tmp_path):
        r = PluginRunner(fetcher=lambda ep: {})
        assert r.save_consult_frame(None, frame_dir=tmp_path) is None
        assert r.save_consult_frame("", frame_dir=tmp_path) is None

    def test_already_encoded_png_saved(self, tmp_path):
        # unknown-size payload already carrying a PNG magic must be saved as-is
        import base64
        r = PluginRunner(fetcher=lambda ep: {})
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
        out = r.save_consult_frame(png, frame_dir=tmp_path)
        assert out is not None
        assert Path(out).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
