"""Spatial memory and stuck detection for Fly64 autonomous navigation.

Phase 1: Stuck detection + spatial memory map + novelty-driven escape.
Spec: StuckDetector (~15 lines), SpatialMemoryMap (~120 lines),
      MemoryController combining both into escape_behavior.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np


# ---------------------------------------------------------------------------
# StuckDetector — multi-signal stuck detection
# ---------------------------------------------------------------------------

class StuckDetector:
    """Detect stuck states from three independent signals.

    - temporal_energy stagnates (visual collapse < threshold for >2 s)
    - game_frame freezes (no change for >5 s)
    - forward_rate collapses (< 5 Hz for >3 s)

    Outputs ``stuck_score ∈ [0, 1]`` and ``stuck_duration`` (seconds).
    The score is the maximum of the three sub-signals.
    """

    def __init__(self, temporal_threshold: float = 0.05,
                 frame_stuck_s: float = 5.0,
                 rate_threshold: float = 5.0,
                 rate_stuck_s: float = 3.0,
                 temporal_stuck_s: float = 2.0):
        self.temporal_threshold = temporal_threshold
        self.frame_stuck_s = frame_stuck_s
        self.rate_threshold = rate_threshold
        self.rate_stuck_s = rate_stuck_s
        self.temporal_stuck_s = temporal_stuck_s
        self._dt = 0.020
        # per-signal timers (seconds)
        self._temporal_low_s = 0.0
        self._frame_still_s = 0.0
        self._rate_low_s = 0.0
        self._last_frame_seq = -1
        self._stuck_duration = 0.0
        self._was_stuck = False

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float) -> tuple[float, float]:
        """Return ``(stuck_score, stuck_duration)`` for this tick."""
        # --- temporal energy ---
        if temporal_energy < self.temporal_threshold:
            self._temporal_low_s += self._dt
        else:
            self._temporal_low_s = 0.0

        # --- game frame ---
        if frame_seq == self._last_frame_seq:
            self._frame_still_s += self._dt
        else:
            self._frame_still_s = 0.0
        self._last_frame_seq = frame_seq

        # --- forward rate ---
        if forward_rate < self.rate_threshold:
            self._rate_low_s += self._dt
        else:
            self._rate_low_s = 0.0

        # individual flags
        temporal_stuck = self._temporal_low_s >= self.temporal_stuck_s
        frame_stuck = self._frame_still_s >= self.frame_stuck_s
        rate_stuck = self._rate_low_s >= self.rate_stuck_s

        # score = max of normalised sub-scores
        t_score = min(1.0, self._temporal_low_s / self.temporal_stuck_s)
        f_score = min(1.0, self._frame_still_s / self.frame_stuck_s)
        r_score = min(1.0, self._rate_low_s / self.rate_stuck_s)
        stuck_score = max(t_score, f_score, r_score)

        # duration
        currently_stuck = temporal_stuck or frame_stuck or rate_stuck
        if currently_stuck:
            self._stuck_duration += self._dt
        else:
            self._stuck_duration = 0.0
        self._was_stuck = currently_stuck

        return stuck_score, self._stuck_duration

    @property
    def stuck_score(self) -> float:
        """Latest stuck score."""
        return max(
            min(1.0, self._temporal_low_s / self.temporal_stuck_s),
            min(1.0, self._frame_still_s / self.frame_stuck_s),
            min(1.0, self._rate_low_s / self.rate_stuck_s),
        )

    @property
    def stuck_duration(self) -> float:
        return self._stuck_duration

    def reset(self) -> None:
        self._temporal_low_s = 0.0
        self._frame_still_s = 0.0
        self._rate_low_s = 0.0
        self._last_frame_seq = -1
        self._stuck_duration = 0.0
        self._was_stuck = False


# ---------------------------------------------------------------------------
# SpatialMemoryMap — grid-based visitation map with novelty
# ---------------------------------------------------------------------------

class SpatialMemoryMap:
    """Hash-map grid of visited cells with novelty and loop detection.

    Grid spans **50 × 50 cells** at **200 game-units per cell**, covering
    roughly 10 000 × 10 000 SM64 world units.

    Per-cell state:
    - **visit_count** (uint16) — number of times the cell was entered
    - **last_visit_tick** — global tick of the most recent visit
    - **recency** — exponential-decay weight [0, 1]

    Derived:
    - **novelty** = ``1 / (visit_count + 1) × recency``
    - **loop_score** — rolling window fraction of cells that are revisits
    - **exploration_mode** — ``True`` when loop_score > threshold *and*
      the agent is stuck.

    Methods: ``update(x, z)``, ``novelty_at(x, z)``, ``get_heatmap()``,
    ``reset()``.
    """

    def __init__(self, cell_size: float = 200.0, grid_cells: int = 50,
                 recency_decay: float = 0.9995,
                 loop_window: int = 500,
                 loop_threshold: float = 0.6):
        self.cell_size = cell_size
        self.grid_cells = grid_cells
        self.recency_decay = recency_decay
        self.loop_window = loop_window
        self.loop_threshold = loop_threshold

        self._cells: dict[tuple[int, int], np.uint16] = {}
        self._recency: dict[tuple[int, int], float] = {}
        self._last_tick: dict[tuple[int, int], int] = {}
        self._total_ticks = 0
        self._current_cell: tuple[int, int] | None = None
        self._history: deque[tuple[int, int]] = deque(maxlen=loop_window)
        self._revisit_count = 0

    # -- helpers ----------------------------------------------------------

    def _key(self, x: float, z: float) -> tuple[int, int]:
        """Map world coordinates to grid key, clamping to grid bounds."""
        ix = int(math.floor(x / self.cell_size))
        iz = int(math.floor(z / self.cell_size))
        half = self.grid_cells // 2
        return (max(-half, min(half - 1, ix)),
                max(-half, min(half - 1, iz)))

    def _decay_recency(self) -> None:
        c = self.recency_decay
        decay_interval = 10
        if self._total_ticks % decay_interval == 0:
            for k in list(self._recency.keys()):
                self._recency[k] *= c

    # -- public API -------------------------------------------------------

    def update(self, x: float, z: float) -> float:
        """Record a visit; returns the novelty of the visited cell (0–1)."""
        self._total_ticks += 1
        key = self._key(x, z)
        self._current_cell = key

        # Track revisits in rolling window
        if key in self._history:
            self._revisit_count += 1
        self._history.append(key)

        if key not in self._cells:
            # new cell
            self._cells[key] = np.uint16(1)
            self._recency[key] = 1.0
            self._last_tick[key] = self._total_ticks
        else:
            # existing cell — increment
            v = int(self._cells[key]) + 1
            self._cells[key] = np.uint16(min(v, 65535))
            self._recency[key] = min(1.0, self._recency[key] + 0.3)
            self._last_tick[key] = self._total_ticks

        self._decay_recency()
        return self._novelty(key)

    def novelty_at(self, x: float, z: float) -> float:
        """Query novelty at a position without recording a visit."""
        key = self._key(x, z)
        if key not in self._cells:
            return 1.0
        return self._novelty(key)

    def _novelty(self, key: tuple[int, int]) -> float:
        """novelty = 1 / (visit_count + 1) × recency"""
        v = int(self._cells[key])
        r = self._recency.get(key, 0.0)
        return (1.0 / (v + 1)) * r

    @property
    def loop_score(self) -> float:
        """Fraction of recent window spent revisiting old cells."""
        if not self._history:
            return 0.0
        return self._revisit_count / len(self._history)

    @property
    def exploration_mode(self) -> bool:
        """True when loop_score > threshold (suggesting the agent is
        circling familiar territory); callers combine with stuck."""
        return self.loop_score > self.loop_threshold

    @property
    def visited_cells(self) -> int:
        return len(self._cells)

    @property
    def total_ticks(self) -> int:
        return self._total_ticks

    def get_heatmap(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Export cell data for dashboard rendering.

        Returns ``(xs, zs, heats)`` as 1-D float32 arrays.
        """
        if not self._cells:
            return np.array([], np.float32), np.array([], np.float32), np.array([], np.float32)
        keys = list(self._cells.keys())
        xs = np.array(
            [k[0] * self.cell_size + self.cell_size * 0.5 for k in keys],
            dtype=np.float32,
        )
        zs = np.array(
            [k[1] * self.cell_size + self.cell_size * 0.5 for k in keys],
            dtype=np.float32,
        )
        heats = np.array(
            [float(self._recency.get(k, 0.0)) for k in keys],
            dtype=np.float32,
        )
        return xs, zs, heats

    def reset(self) -> None:
        self._cells.clear()
        self._recency.clear()
        self._last_tick.clear()
        self._total_ticks = 0
        self._current_cell = None
        self._history.clear()
        self._revisit_count = 0


# ---------------------------------------------------------------------------
# MemoryController — combined navigation memory
# ---------------------------------------------------------------------------

class MemoryController:
    """Aggregate stuck detection, spatial memory, and novelty into an
    ``escape_behavior`` flag.

    The controller combines:
    - StuckDetector (temporal, frame, rate signals)
    - SpatialMemoryMap (novelty, loop_score, exploration_mode)

    When the agent is both **stuck** and **exploration_mode** is active,
    ``escape_behavior`` fires, signalling the main loop to initiate a
    novelty-driven escape turn.
    """

    def __init__(self,
                 stuck: StuckDetector | None = None,
                 spatial: SpatialMemoryMap | None = None):
        self.stuck = stuck or StuckDetector()
        self.spatial = spatial or SpatialMemoryMap()
        self.escape_behavior: bool = False
        self._stuck_score: float = 0.0
        self._stuck_duration: float = 0.0
        self._novelty: float = 1.0

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float, x: float, z: float,
               heading: float = 0.0) -> tuple[float, float, float, bool]:
        """Feed one tick; returns ``(stuck_score, stuck_duration, novelty,
        escape_behavior)``."""
        self._stuck_score, self._stuck_duration = self.stuck.update(
            temporal_energy, frame_seq, forward_rate
        )
        self._novelty = self.spatial.update(x, z)
        self.escape_behavior = (
            self._stuck_score >= 0.8
            and self.spatial.exploration_mode
        )
        return (self._stuck_score, self._stuck_duration,
                self._novelty, self.escape_behavior)

    def reset(self) -> None:
        self.stuck.reset()
        self.spatial.reset()
        self.escape_behavior = False
        self._stuck_score = 0.0
        self._stuck_duration = 0.0
        self._novelty = 1.0

    @property
    def stuck_score(self) -> float:
        return self._stuck_score

    @property
    def stuck_duration(self) -> float:
        return self._stuck_duration

    @property
    def novelty(self) -> float:
        return self._novelty