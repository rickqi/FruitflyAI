"""EVO R20 CX-3 regression — multi-source goal vector competition.

FB-style vector arithmetic: goal sources add as vectors; the resultant
defines the goal column and strength.  A single exhausted source no longer
zeroes the direction sense.
"""
import numpy as np
import pytest

from fly64.central_complex import CentralComplex


class TestGoalVectorCompetition:
    def _cx(self):
        return CentralComplex()

    def test_single_vector_sets_goal(self):
        cx = self._cx()
        # single goal east (dx=1, dz=0, w=1)
        cx.update(heading=None, heading_rate=0.0, dt=0.02,
                  goal_vectors=[(1.0, 0.0, 1.0)])
        assert cx.goal_column == 4  # east = col 4 of 16

    def test_two_vectors_sum(self):
        cx = self._cx()
        # east + north = northeast (col 2 of 16, between col 0(north) and col 4(east))
        cx.update(heading=None, heading_rate=0.0, dt=0.02,
                  goal_vectors=[(1.0, 0.0, 1.0), (0.0, 1.0, 1.0)])
        assert cx.goal_column == 2  # northeast = between north(0) and east(4)

    def test_dominant_source_wins(self):
        cx = self._cx()
        # strong east, weak north → goal close to east
        cx.update(heading=None, heading_rate=0.0, dt=0.02,
                  goal_vectors=[(2.0, 0.0, 1.0), (0.0, 0.5, 0.3)])
        assert cx.goal_column in (3, 4, 5)  # near east

    def test_opposite_vectors_cancel(self):
        cx = self._cx()
        # east + west cancel → goal near 0 (undefined direction)
        cx.update(heading=None, heading_rate=0.0, dt=0.02,
                  goal_vectors=[(1.0, 0.0, 0.5), (-1.0, 0.0, 0.5)])
        # cancelled → goal_strength low
        assert cx.goal_strength < 0.5

    def test_no_vectors_falls_to_legacy(self):
        cx = self._cx()
        cx.update(heading=None, heading_rate=0.0, dt=0.02,
                  novelty_direction=0.0, goal_vectors=None)
        # no goal vectors → legacy novelty path → goal_strength decays
        assert cx.goal_strength < 0.5
