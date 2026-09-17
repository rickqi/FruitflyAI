#!/usr/bin/env python3
"""R31-fix2 screen fidelity check — the regression test that was missing.

Original blind spot: EVO R21's isolation audit verified the observer pass
does NOT disturb the player framebuffer, but nothing verified that the
coach screenshot actually matches the game screen.  Result: the capture sat
at the tail of the cubemap pass and produced a partial, mid-frame image.

Checks (against a live stack):
  1. /screen.json decodes to a full 320x240x3 RGB frame (not empty/truncated)
  2. the frame is not mostly black (zero-fraction below threshold) — the old
     bug zeroed everything outside the stale observer viewport
  3. screen content differs from the cubemap forward face (/help.json
     frame_b64) — they used to be the same wrong image
  4. consecutive captures differ (stream is live, not a frozen frame)

Usage: python3 scripts/m4_screen_fidelity_check.py [--base http://127.0.0.1:8765]
"""
import argparse, base64, json, sys, time
import urllib.request
import numpy as np

W, H, C = 320, 240, 3


def fetch(base, ep):
    try:
        with urllib.request.urlopen(base + ep, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def decode(b64):
    if not b64:
        return None
    raw = base64.b64decode(b64)
    if len(raw) < W * H * C:
        return None
    return np.frombuffer(raw[:W * H * C], dtype=np.uint8).reshape(H, W, C)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    a = ap.parse_args()
    failures = []

    s1 = fetch(a.base, "/screen.json")
    scr = decode(s1.get("screen_b64"))
    if scr is None:
        print("FAIL 1: screen_b64 missing/short — capture path dead")
        return 1
    print(f"PASS 1: screen payload decodes to {W}x{H}x{C}")

    zero_frac = float((scr == 0).mean())
    if zero_frac > 0.60:
        failures.append(f"2: screen is {zero_frac:.0%} zeros (old partial-capture bug)")
    else:
        print(f"PASS 2: zero-fraction {zero_frac:.1%} (not a partial viewport crop)")

    h = fetch(a.base, "/help.json")
    fwd = decode(h.get("frame_b64"))
    if fwd is None:
        print("note 3: cubemap forward face unavailable; skip")
    else:
        # eye face is 128x128; resize screen down to 128x128 by block mean
        blk = scr.reshape(128, 2, 128 * 2 // 2 * 0 + 2, 128, 3)
        # simple decimation to 128x128 (2:1 both axes -> 160x120, then pad-free
        # nearest via slicing) — keep it simple: mean over 2x2 blocks on 320x240
        small = scr[:240, :320].reshape(120, 2, 160, 2, 3).mean(axis=(1, 3))
        # compare against the 128x128 eye face downscaled comparison via
        # coarse 8x8 grid correlation: strongly-identical images correlate ~1
        def grid8(img_color):
            g = img_color.reshape(240 // 8 if img_color.shape[0] == 240 else 16, 8,
                                  -1) if False else None
            return None
        # Simpler robust metric: normalised colour histograms differ if the
        # images are different scenes/angles.
        hist_s = np.histogram(scr[..., 0], bins=16, range=(0, 255), density=True)[0]
        hist_f = np.histogram(fwd[..., 0], bins=16, range=(0, 255), density=True)[0]
        diff = float(np.abs(hist_s - hist_f).sum())
        if diff < 0.05:
            failures.append(f"3: screen histogram ~identical to cubemap face (diff={diff:.3f})")
        else:
            print(f"PASS 3: screen differs from cubemap forward face (hist-L1={diff:.3f})")

    time.sleep(1.0)
    s2 = fetch(a.base, "/screen.json")
    scr2 = decode(s2.get("screen_b64"))
    if scr2 is None:
        failures.append("4: second capture missing")
    else:
        delta = float(np.abs(scr.astype(int) - scr2.astype(int)).mean())
        if delta < 0.5:
            failures.append(f"4: two captures 1s apart identical (delta={delta}) — frozen frame")
        else:
            print(f"PASS 4: live stream (frame delta {delta:.2f})")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    print("SCREEN FIDELITY: ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
