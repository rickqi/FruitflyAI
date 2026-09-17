"""R31-fix2 regression: coach screen fidelity (the blind-spot test).

The original EVO R21 audit verified the observer pass does not disturb the
player framebuffer but nothing validated that the coach screenshot MATCHES
the game screen.  Result: the capture sat at the tail of the cubemap pass
and produced a partial, mid-frame, observer-camera image for months.

These checks require a live stack (brain + fixed game binary); they are
gated behind FLY64_LIVE=1 so the normal offline suite is unaffected.

Run:  FLY64_LIVE=1 python3 -m pytest tests/test_screen_fidelity.py -v
Equivalent standalone: python3 scripts/m4_screen_fidelity_check.py
"""
import base64
import os
import time

import numpy as np
import pytest
import urllib.request

W, H, C = 320, 240, 3
BASE = "http://127.0.0.1:8765"

pytestmark = pytest.mark.skipif(
    os.environ.get("FLY64_LIVE") != "1", reason="requires live stack (FLY64_LIVE=1)")


def _fetch(ep):
    return urllib.request.urlopen(BASE + ep, timeout=5).read()


def _screen() -> np.ndarray:
    data = json.loads(_fetch("/screen.json"))
    raw = base64.b64decode(data["screen_b64"])[: W * H * C]
    return np.frombuffer(raw, dtype=np.uint8).reshape(H, W, C)


import json  # noqa: E402


def test_screen_decodes_to_full_frame():
    scr = _screen()
    assert scr.shape == (H, W, C)


def test_screen_not_a_partial_viewport_crop():
    """The old bug memset everything outside the stale observer viewport."""
    scr = _screen()
    assert (scr == 0).mean() <= 0.60, "screen mostly zeros -> partial capture"


def test_screen_is_live_not_frozen():
    a = _screen()
    time.sleep(1.0)
    b = _screen()
    assert np.abs(a.astype(int) - b.astype(int)).mean() >= 0.5, \
        "two captures 1s apart identical -> frozen frame"


def test_game_frames_advancing():
    st = json.loads(_fetch("/bridge-status.json"))
    assert st["game_frame"] > 0
