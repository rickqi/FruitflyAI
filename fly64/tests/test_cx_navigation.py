"""EVO R20 · CX-1 regression — compass autonomy (self-motion integration).

The ring-attractor bump must move by INTEGRATED ANGULAR VELOCITY
(autonomous path-integration term) with external heading and sky azimuth
demoted to weak corrections.  No Python direction decisions.
"""
import numpy as np
import pytest

from fly64.central_complex import CentralComplex


class TestCompassAutonomy:
    def test_self_motion_rolls_bump_without_external_drive(self):
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # 90°/s turn for 0.5 s (25 ticks) while external heading held STALE at 0
        for _ in range(25):
            cx.update(heading=0.0, heading_rate=np.pi / 2, dt=0.02)
        est = cx.heading_estimate
        moved = (est - 0.0 + np.pi) % (2 * np.pi) - np.pi
        # 90°/s × 0.5s = 45°; the weak stale drive holds it near ~10° —
        # what matters is DIRECTION against the stale reference
        assert moved > np.radians(5), f"moved only {np.degrees(moved):.1f}°"

    def test_heading_none_fully_autonomous_tracking(self):
        """heading=None (game value unavailable) → pure self-motion + sky."""
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # rotate 90°/s for 0.5 s with NO game heading: sky at 45° anchors
        for _ in range(25):
            cx.update(heading=None, heading_rate=np.pi / 2, dt=0.02,
                      visual_azimuth=np.pi / 4)
        est = cx.heading_estimate
        moved = (est + np.pi) % (2 * np.pi) - np.pi
        assert moved > np.radians(20), f"autonomous tracking failed: {np.degrees(moved):.1f}°"

    def test_fractional_accumulation_no_loss(self):
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # 0.4 columns/tick × 5 ticks = 2.0 columns = 45°
        rate = 0.4 * (2 * np.pi) / (16 * 0.02)
        for _ in range(5):
            cx.update(heading=0.0, heading_rate=rate, dt=0.02)
        est = cx.heading_estimate
        moved = (est + np.pi) % (2 * np.pi) - np.pi
        assert moved == pytest.approx(np.pi / 4, abs=0.2), (
            f"moved {np.degrees(moved):.1f}°, expected ≈45°")

    def test_external_heading_still_corrects(self):
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # no self-motion; external heading π for many ticks → bump follows
        for _ in range(40):
            cx.update(heading=np.pi, heading_rate=0.0, dt=0.02)
        est = cx.heading_estimate
        moved = abs((est - np.pi + np.pi) % (2 * np.pi) - np.pi)
        assert moved < 0.4, f"drive correction broken: est={est:.2f}"

    def test_visual_azimuth_correction_pulls(self):
        """Sky compass (0.12) must out-pull the game heading (0.10): with
        game=0 and sky=0.6 rad the bump settles on the sky side of zero."""
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        for _ in range(40):
            cx.update(heading=0.0, heading_rate=0.0, dt=0.02,
                      visual_azimuth=0.6)
        est = cx.heading_estimate
        assert 0.15 < est < 1.2, f"sky compass failed: est={est:.3f}"

    def test_rough_turn_does_not_lose_columns(self):
        """Wild alternation must not lose net rotation (accumulation test)."""
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        rate = np.pi / 2
        for i in range(50):
            r = rate if i % 2 == 0 else -rate
            cx._self_motion_update(r, 0.02)
        assert abs(cx._col_accum) < 1e-6
        # net rotation zero → bump stays near 0
        est = cx.heading_estimate
        assert abs((est + np.pi) % (2 * np.pi) - np.pi) < 0.5
