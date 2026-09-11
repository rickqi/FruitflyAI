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
    """Detect stuck states from three independent signals + Y-axis anomaly.

    - temporal_energy stagnates (visual collapse < threshold for >2 s)
    - game_frame freezes (no change for >5 s)
    - forward_rate collapses (< 5 Hz for >3 s)
    - Y-axis anomaly (y < -100 or y > 1000 → fallen off map)

    Outputs ``stuck_score ∈ [0, 1]``, ``stuck_duration``, and ``fallen`` flag.
    """

    def __init__(self, temporal_threshold: float = 0.05,
                 frame_stuck_s: float = 5.0,
                 rate_threshold: float = 5.0,
                 rate_stuck_s: float = 3.0,
                 temporal_stuck_s: float = 2.0,
                 y_min: float = -100.0,
                 y_max: float = 1000.0):
        self.temporal_threshold = temporal_threshold
        self.frame_stuck_s = frame_stuck_s
        self.rate_threshold = rate_threshold
        self.rate_stuck_s = rate_stuck_s
        self.temporal_stuck_s = temporal_stuck_s
        self.y_min = y_min
        self.y_max = y_max
        self._dt = 0.020
        self._temporal_low_s = 0.0
        self._frame_still_s = 0.0
        self._rate_low_s = 0.0
        self._last_frame_seq = -1
        self._stuck_duration = 0.0
        self._was_stuck = False
        self._fallen = False
        self._fall_recovery_ticks = 0

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float, pos_y: float = 0.0) -> tuple[float, float, bool]:
        """Return ``(stuck_score, stuck_duration, fallen)`` for this tick."""
        # --- Y-axis anomaly (fallen off map) ---
        self._fallen = pos_y < self.y_min or pos_y > self.y_max
        if self._fallen:
            self._fall_recovery_ticks += 1
        else:
            self._fall_recovery_ticks = 0

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

        temporal_stuck = self._temporal_low_s >= self.temporal_stuck_s
        frame_stuck = self._frame_still_s >= self.frame_stuck_s
        rate_stuck = self._rate_low_s >= self.rate_stuck_s

        t_score = min(1.0, self._temporal_low_s / self.temporal_stuck_s)
        f_score = min(1.0, self._frame_still_s / self.frame_stuck_s)
        r_score = min(1.0, self._rate_low_s / self.rate_stuck_s)
        stuck_score = max(t_score, f_score, r_score, 1.0 if self._fallen else 0.0)

        currently_stuck = temporal_stuck or frame_stuck or rate_stuck or self._fallen
        if currently_stuck:
            self._stuck_duration += self._dt
        else:
            self._stuck_duration = 0.0
        self._was_stuck = currently_stuck

        return stuck_score, self._stuck_duration, self._fallen

    @property
    def stuck_score(self) -> float:
        return max(
            min(1.0, self._temporal_low_s / self.temporal_stuck_s),
            min(1.0, self._frame_still_s / self.frame_stuck_s),
            min(1.0, self._rate_low_s / self.rate_stuck_s),
            1.0 if self._fallen else 0.0,
        )

    @property
    def stuck_duration(self) -> float:
        return self._stuck_duration

    @property
    def fallen(self) -> bool:
        return self._fallen

    @property
    def fall_recovery_ticks(self) -> int:
        return self._fall_recovery_ticks

    def reset(self) -> None:
        self._temporal_low_s = 0.0
        self._frame_still_s = 0.0
        self._rate_low_s = 0.0
        self._last_frame_seq = -1
        self._stuck_duration = 0.0
        self._was_stuck = False
        self._fallen = False
        self._fall_recovery_ticks = 0


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

class FailureMemory:
    """Remember positions where Mario fell or got badly stuck.

    Stores fallen locations as grid keys. When returning to a known
    failure cell, the novelty is suppressed and escape behavior is
    biased away from the fall direction.
    """

    def __init__(self, cell_size: float = 200.0):
        self.cell_size = cell_size
        self._failures: set[tuple[int, int]] = set()

    def record_failure(self, x: float, z: float) -> None:
        """Mark the grid cell containing (x, z) as a failure location."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        self._failures.add(key)

    def is_failure_cell(self, x: float, z: float) -> bool:
        """Check if (x, z) is in a previously failed cell."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        return key in self._failures

    def avoid_direction(self, x: float, z: float, heading: float) -> float:
        """If heading points toward a failure cell, suggest a turn away.
        Returns a turn bias in degrees (positive = turn right, negative = turn left)."""
        import math as _math
        if not self._failures:
            return 0.0
        cx = int(_math.floor(x / self.cell_size))
        cz = int(_math.floor(z / self.cell_size))
        # Check adjacent cells in heading direction
        hx = cx + int(round(_math.sin(heading)))
        hz = cz + int(round(_math.cos(heading)))
        if (hx, hz) in self._failures:
            return 0.5  # bias turn right
        return 0.0

    @property
    def failure_count(self) -> int:
        return len(self._failures)

    def reset(self) -> None:
        self._failures.clear()


class MemoryController:
    """Aggregate stuck detection, spatial memory, and novelty into an
    ``escape_behavior`` flag.

    The controller combines:
    - StuckDetector (temporal, frame, rate, Y-axis signals)
    - SpatialMemoryMap (novelty, loop_score, exploration_mode)
    - FailureMemory (fallen locations for avoidance)
    """

    def __init__(self,
                 stuck: StuckDetector | None = None,
                 spatial: SpatialMemoryMap | None = None,
                 failures: FailureMemory | None = None):
        self.stuck = stuck or StuckDetector()
        self.spatial = spatial or SpatialMemoryMap()
        self.failures = failures or FailureMemory()
        self.escape_behavior: bool = False
        self._stuck_score: float = 0.0
        self._stuck_duration: float = 0.0
        self._novelty: float = 1.0
        self._fallen: bool = False
        self._last_pos = (0.0, 0.0, 0.0)
        self._fall_pos = (0.0, 0.0, 0.0)

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float, x: float, z: float,
               pos_y: float = 0.0, heading: float = 0.0) -> tuple:
        """Feed one tick; returns ``(stuck_score, stuck_duration, novelty,
        escape_behavior, fallen)``."""
        self._stuck_score, self._stuck_duration, self._fallen = self.stuck.update(
            temporal_energy, frame_seq, forward_rate, pos_y
        )
        self._novelty = self.spatial.update(x, z)

        # Record position for fall detection
        self._last_pos = (x, pos_y, z)

        # If fallen, record the last safe position as failure
        if self._fallen and self._fall_pos == (0.0, 0.0, 0.0):
            self._fall_pos = self._last_pos
            self.failures.record_failure(x, z)

        self.escape_behavior = (
            self._stuck_score >= 0.8
            and (self.spatial.exploration_mode or self._fallen)
        )
        return (self._stuck_score, self._stuck_duration,
                self._novelty, self.escape_behavior, self._fallen)

    def reset(self) -> None:
        self.stuck.reset()
        self.spatial.reset()
        self.failures.reset()
        self.escape_behavior = False
        self._stuck_score = 0.0
        self._stuck_duration = 0.0
        self._novelty = 1.0
        self._fallen = False
        self._fall_pos = (0.0, 0.0, 0.0)

    @property
    def stuck_score(self) -> float: return self._stuck_score

    @property
    def stuck_duration(self) -> float: return self._stuck_duration

    @property
    def novelty(self) -> float: return self._novelty

    @property
    def fallen(self) -> bool: return self._fallen