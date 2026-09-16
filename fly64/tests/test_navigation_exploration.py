"""
Tests for navigation exploration improvements:
- Exploration direction inertia (non-escape mode)
- Frontier exploration direction
- 3D grid Y-layer mapping
- Dual-timescale novelty decay
- Strengthened revisit penalty
"""

import math
import sys
sys.path.insert(0, '.')

import pytest
import numpy as np

from fly64.memory import SpatialMemoryMap
from fly64.central_complex import CentralComplex


class TestFrontierExploration:
    """P1: frontier_direction() finds boundaries of explored terrain."""

    def test_frontier_found(self):
        """Frontier detected at edge of visited region."""
        sm = SpatialMemoryMap()
        # Visit a 5x5 block
        for x in range(-400, 401, 200):
            for z in range(-400, 401, 200):
                sm.update(x, 0, z)
        # Frontier should point outward from the block edge
        front = sm.frontier_direction(0, 0, 0)
        assert front is not None, "Frontier should exist beyond visited block"
        fx, fz = front
        norm = math.hypot(fx, fz)
        assert abs(norm - 1.0) < 0.01, "Frontier should be unit vector, got norm=%.3f" % norm

    def test_frontier_none_when_full(self):
        """No frontier when entire search area is visited."""
        sm = SpatialMemoryMap()
        # Visit a large area (radius 10)
        for x in range(-2000, 2001, 200):
            for z in range(-2000, 2001, 200):
                sm.update(x, 0, z)
        # Search a smaller radius (5) that is fully covered
        front = sm.frontier_direction(0, 0, 0, search_radius=5)
        assert front is None, "No frontier expected in fully visited region (radius 5)"

    def test_frontier_larger_radius(self):
        """Frontier found with larger search radius."""
        sm = SpatialMemoryMap()
        # Visit a 3x3 block
        for x in range(-200, 201, 200):
            for z in range(-200, 201, 200):
                sm.update(x, 0, z)
        front = sm.frontier_direction(0, 0, 0, search_radius=20)
        assert front is not None, "Frontier should exist with large radius"


class TestNoveltyDecay:
    """P2: dual-timescale novelty decay accelerates exploration."""

    def test_default_fast_decay_exists(self):
        """SpatialMemoryMap should have fast_decay parameter."""
        sm = SpatialMemoryMap()
        assert hasattr(sm, 'fast_decay'), "Missing fast_decay attribute"
        assert sm.fast_decay == 0.995, "fast_decay should default to 0.995"

    def test_revisit_penalty_stronger(self):
        """Revisit penalty should ramp faster than original."""
        sm = SpatialMemoryMap()
        # Simulate revisit_count via _scene_db
        sm._scene_db._revisit_count = 0
        assert sm.revisit_penalty == 0.0, "0 revisits: penalty=0"
        sm._scene_db._revisit_count = 3
        p3 = sm.revisit_penalty
        assert p3 > 0.3, "3 revisits: penalty=%.3f should be >0.3" % p3
        sm._scene_db._revisit_count = 5
        p5 = sm.revisit_penalty
        assert p5 >= 0.69, "5 revisits: penalty=%.3f should be ~0.7" % p5


class Test3DGrid:
    """P2: 3D grid correctly maps Y coords to layers."""

    def test_y_layers(self):
        """Different Y values map to different layers."""
        sm = SpatialMemoryMap(y_layers=5)
        # Ground level
        k0 = sm._key(100, -200, 200)
        # Upper platform
        k1 = sm._key(100, 500, 200)
        # Very high
        k2 = sm._key(100, 2000, 200)
        assert k0[1] != k1[1], "Different Y should map to different layers"
        assert k0[1] >= 0, "Layer index should be >= 0"
        assert k2[1] <= 4, "Layer index should be <= 4"

    def test_update_3d(self):
        """Update with Y records in correct layer."""
        sm = SpatialMemoryMap()
        sm.update(0, 0, 0)
        sm.update(0, 500, 0)  # Different layer
        k_ground = sm._key(0, 0, 0)
        k_upper = sm._key(0, 500, 0)
        assert k_ground != k_upper, "Different Y should produce different keys"
        assert k_ground in sm._cells, "Ground cell should be recorded"
        assert k_upper in sm._cells, "Upper cell should be recorded"


class Test3DGridBehavior:
    """Integration: 3D grid correctly separates multi-level exploration."""

    def test_coverage_separate_layers(self):
        """Coverage counter treats different Y layers independently."""
        sm = SpatialMemoryMap(y_layers=3)
        # Visit ground layer
        for x in range(-400, 401, 200):
            for z in range(-400, 401, 200):
                sm.update(x, 0, z)
        cov_ground = sm.coverage_percentage
        # Visit upper layer  
        for x in range(-400, 401, 200):
            for z in range(-400, 401, 200):
                sm.update(x, 500, z)
        cov_total = sm.coverage_percentage
        assert cov_total > cov_ground, "3D coverage should exceed 2D coverage"
        print("3D grid test: ground=%.1f%%, total=%.1f%%" % (cov_ground, cov_total))