"""EVO R20 CX-2 regression — anchor-frame path integration.

The CX integrates displacement along its OWN compass heading (brain's
belief of travel), re-anchors on scene change, and exposes distance and
return bearing.
"""
import numpy as np
import pytest

from fly64.central_complex import CentralComplex


class TestPathIntegration:
    def _cx(self):
        cx = CentralComplex()
        cx.set_anchor(0.0, 0.0)
        return cx

    def test_north_flight_accumulates_z(self):
        cx = self._cx()
        # head north (est≈0, +z) at 50 Hz-equivalent for 2s
        for _ in range(100):
            cx.update(heading=None, heading_rate=0.0, dt=0.02,
                      forward_speed=2.5)
        assert cx.disp_z > 1.0, cx.disp_z
        assert abs(cx.disp_x) < 0.5

    def test_distance_matches_speed_time(self):
        cx = self._cx()
        rate = 2.5  # forward units
        for _ in range(100):  # 2s
            cx.update(heading=None, heading_rate=0.0, dt=0.02,
                      forward_speed=rate)
        # SPEED_TO_UNITS=1.6: distance ≈ 2.5 × 1.6 × 2s = 8.0
        assert cx.anchor_distance == pytest.approx(8.0, rel=0.15)

    def test_turn_then_walk_tracks_compass(self):
        cx = self._cx()
        # rotate the compass east via self-motion, then walk
        for _ in range(25):
            cx.update(heading=None, heading_rate=np.pi / 2, dt=0.02,
                      forward_speed=0.0)
        for _ in range(100):
            cx.update(heading=None, heading_rate=0.0, dt=0.02,
                      forward_speed=2.5)
        # compass tracked rotation with ≤1 col lag → east-dominant walk
        assert cx.disp_x > 0.3 * abs(cx.disp_z), (
            f"disp=({cx.disp_x:.2f},{cx.disp_z:.2f}) — east component lost")

    def test_set_anchor_resets(self):
        cx = self._cx()
        for _ in range(50):
            cx.update(heading=None, heading_rate=0.0, dt=0.02,
                      forward_speed=2.0)
        assert cx.anchor_distance > 0.5
        cx.set_anchor(0.0, 0.0)
        assert cx.anchor_distance == 0.0

    def test_return_bearing_points_home(self):
        cx = self._cx()
        # walk east then compute the return bearing — must be west (≈π)
        for _ in range(60):
            cx.update(heading=None, heading_rate=0.0, dt=0.02,
                      forward_speed=2.0)
        bearing = cx.anchor_return_bearing
        assert bearing is not None
        # displacement is +x; return bearing ≈ π (west)
        assert abs((bearing - np.pi + np.pi) % (2 * np.pi) - np.pi) < 0.3 or \
               abs(bearing - np.pi) < 0.3
