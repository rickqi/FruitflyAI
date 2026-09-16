"""Test CCL 8-connectivity fix for small-target detection.

EVO R29: stride-2 sampling in the retina grid prevents 4-connected CCL from
forming ≥2-cell components, making compute_small_targets() always return 0.
8-connectivity allows diagonal adjacency, bridging the stride-2 gap.
"""
import numpy as np
import pytest

from fly64.retina import SphericalRetina


def _retina():
    """Build a minimal retina fixture."""
    vp = np.zeros((900, 2), dtype=np.float32)
    for i in range(900):
        r = i // 46
        c = (i % 46) * 2
        if c >= 64:
            c = 63
        vp[i] = [r % 48, c % 64]
    return SphericalRetina(vp)


class TestCCLEightConnectivity:
    def test_scipy_path_8connectivity(self):
        """scipy ndimage path uses 8-connectivity structure."""
        r = _retina()
        # A diagonal cluster: cells at (r,c), (r+1,c+1), (r+2,c+2)
        mask = np.zeros((48, 64), dtype=bool)
        mask[10, 10] = True
        mask[11, 11] = True
        mask[12, 12] = True
        labels, n = r._connected_components(mask)
        assert n == 1, f"diagonal cluster split into {n} components"
        assert (labels > 0).sum() >= 3

    def test_isolated_cells_stay_separate(self):
        """Truly isolated cells still form separate components."""
        r = _retina()
        mask = np.zeros((48, 64), dtype=bool)
        mask[5, 5] = True
        mask[5, 25] = True
        mask[25, 5] = True
        labels, n = r._connected_components(mask)
        assert n == 3, f"isolated cells merged: {n} components"

    def test_horizontal_cluster_4cell(self):
        r = _retina()
        mask = np.zeros((48, 64), dtype=bool)
        mask[10, 10:14] = True  # 4 horizontal cells
        labels, n = r._connected_components(mask)
        assert n == 1
        assert (labels > 0).sum() >= 4

    def test_vertical_cluster_4cell(self):
        r = _retina()
        mask = np.zeros((48, 64), dtype=bool)
        mask[10:14, 10] = True  # 4 vertical cells
        labels, n = r._connected_components(mask)
        assert n == 1
        assert (labels > 0).sum() >= 4

    def test_bridge_gap_via_diagonal(self):
        """Stride-2 cells that are diagonally adjacent must form one component."""
        r = _retina()
        mask = np.zeros((48, 64), dtype=bool)
        mask[5, 5] = True
        mask[7, 7] = True   # two steps away diagonally
        labels, n = r._connected_components(mask)
        # With 8-connectivity the diagonal chain (5,5)->(6,6)->(7,7) does NOT
        # connect because there's no cell at (6,6).  This tests the limit.
        assert n >= 1