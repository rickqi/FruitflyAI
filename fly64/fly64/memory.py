"""Spatial memory, stuck detection, and cliff awareness for Fly64.

Phase 1: Stuck detection + spatial memory map + novelty-driven escape.
Phase 3: CliffDetector — multi-frame confirmation of lower_field_green dips.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np


# ---------------------------------------------------------------------------
# CliffDetector — multi-frame cliff confirmation with hysteresis
# ---------------------------------------------------------------------------

class CliffDetector:
    """Detect cliff edges by tracking lower_field_green over multiple frames.

    Uses a confirmation window with hysteresis thresholds to reject single-frame
    noise and provide clean state transitions.

    Configurable parameters:
      entering_threshold  — raw green below this value starts the confirmation
      exiting_threshold   — raw green above this value cancels confirmation
                            (must be >= entering_threshold to provide hysteresis)
      confirmation_window — number of consecutive frames to examine (default 5)
      min_confirmed       — how many frames in the window must be below threshold
                            for cliff_detected to become True (default 3)

    Outputs:
      cliff_detected (bool)   — confirmed after multi-frame check
      cliff_confidence (0-1)  — fraction of window frames below threshold
      raw_lower_field_green   — latest raw measurement (passthrough)
    """

    def __init__(self,
                 entering_threshold: float = 0.35,
                 exiting_threshold: float = 0.40,
                 confirmation_window: int = 5,
                 min_confirmed: int = 3):
        if min_confirmed > confirmation_window:
            raise ValueError("min_confirmed must not exceed confirmation_window")
        if exiting_threshold < entering_threshold:
            raise ValueError("exiting_threshold must be >= entering_threshold")
        self.entering_threshold = entering_threshold
        self.exiting_threshold = exiting_threshold
        self.confirmation_window = confirmation_window
        self.min_confirmed = min_confirmed

        self._history: deque[float] = deque(maxlen=confirmation_window)
        self._cliff_detected: bool = False
        self._raw: float = 1.0

    def update(self, lower_field_green: float) -> dict:
        """Feed one frame's lower_field_green; return cliff detection state.

        Returns dict with keys:
          cliff_detected (bool),
          cliff_confidence (float, 0-1),
          raw_lower_field_green (float).
        """
        self._raw = lower_field_green
        self._history.append(lower_field_green)

        # Count how many frames in window are below the active threshold
        active_threshold = (self.entering_threshold
                            if not self._cliff_detected
                            else self.exiting_threshold)
        below = sum(1 for v in self._history if v < active_threshold)
        confidence = below / self.confirmation_window if len(self._history) == self.confirmation_window else 0.0

        # State transition logic
        if not self._cliff_detected:
            if len(self._history) == self.confirmation_window and below >= self.min_confirmed:
                self._cliff_detected = True
        else:
            if len(self._history) == self.confirmation_window and below == 0:
                self._cliff_detected = False

        return {
            "cliff_detected": self._cliff_detected,
            "cliff_confidence": round(confidence, 3),
            "raw_lower_field_green": round(lower_field_green, 4),
        }

    @property
    def cliff_detected(self) -> bool:
        return self._cliff_detected

    @property
    def cliff_confidence(self) -> float:
        """Fraction of frames in window below active threshold."""
        if not self._history:
            return 0.0
        active_threshold = (self.entering_threshold
                            if not self._cliff_detected
                            else self.exiting_threshold)
        below = sum(1 for v in self._history if v < active_threshold)
        return below / self.confirmation_window

    @property
    def raw(self) -> float:
        return self._raw

    def reset(self) -> None:
        self._history.clear()
        self._cliff_detected = False
        self._raw = 1.0


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
        self._coverage_history: deque[tuple[int, float]] = deque(maxlen=6000)
        self._last_coverage_tick = 0

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
        
        # Record coverage history every 100 ticks
        if self._total_ticks - self._last_coverage_tick >= 100:
            self._last_coverage_tick = self._total_ticks
            self._coverage_history.append((self._total_ticks, self.coverage_percentage))
        
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

    def novelty_direction(self, x: float, z: float, heading: float,
                          dead_end_keys: set[tuple[int, int]] | None = None,
                          scene_change_rate: float = 0.0) -> float:
        """Evaluate novelty in 4 directions relative to *heading* and return a
        turn bias.

        Samples novelty in the forward, left, right, and backward grid cells
        relative to the current heading. Returns a float in [-1, +1] where:
        - positive = turn right toward higher-novelty area
        - negative = turn left toward higher-novelty area
        Returns 0 when no direction offers meaningful novelty advantage.

        If *dead_end_keys* is provided, cells in that set (or their immediate
        neighbors) have their novelty score penalised by 0.5.

        If *scene_change_rate* >= 0.3 (rapid scene changes = new area), the
        dead-end penalty is halved to 0.25, allowing more exploration in
        unfamiliar surroundings where old dead-end information may not apply.
        """
        base_key = self._key(x, z)
        cx, cz = base_key

        # 4 direction offsets relative to heading (sm64: heading 0 = +Z north)
        # Forward = (+sin(heading), +cos(heading)) in grid space
        sin_h = math.sin(heading)
        cos_h = math.cos(heading)

        def grid_dir(sin_a, cos_a):
            """Compute grid-step offset for absolute angle (sin, cos)."""
            dx = 1 if sin_a > 0.3 else (-1 if sin_a < -0.3 else 0)
            dz = 1 if cos_a > 0.3 else (-1 if cos_a < -0.3 else 0)
            return dx, dz

        forward_off = grid_dir(sin_h, cos_h)                 # heading
        left_off = grid_dir(-cos_h, sin_h)                   # heading + 90°
        right_off = grid_dir(cos_h, -sin_h)                  # heading - 90°
        backward_off = grid_dir(-sin_h, -cos_h)              # heading + 180°

        half = self.grid_cells // 2

        # When scene_change_rate >= 0.3 (new area), halve the dead-end penalty
        # so old dead-end info doesn't suppress exploration in a fresh scene.
        _penalty_modifier = 0.5 if scene_change_rate >= 0.3 else 1.0

        def cell_novelty(off):
            """Average novelty over the cell at offset and its onward neighbor,
            penalised if near a dead-end cell."""
            nk = (cx + off[0], cz + off[1])
            if not (-half <= nk[0] < half and -half <= nk[1] < half):
                return 0.0

            # Dead-end penalty: subtract 0.5 × modifier if the target cell or
            # its 4-neighbor is a known dead-end
            dead_end_penalty = 0.0
            if dead_end_keys:
                if nk in dead_end_keys:
                    dead_end_penalty = 0.5 * _penalty_modifier
                else:
                    for dk_off in [(1,0), (-1,0), (0,1), (0,-1)]:
                        if (nk[0] + dk_off[0], nk[1] + dk_off[1]) in dead_end_keys:
                            dead_end_penalty = 0.5 * _penalty_modifier
                            break

            n1 = max(0.0, (self.novelty_at(nk[0] * self.cell_size, nk[1] * self.cell_size)
                    if nk in self._cells else 1.0) - dead_end_penalty)
            # lookahead one cell further
            nk2 = (nk[0] + off[0], nk[1] + off[1])
            if -half <= nk2[0] < half and -half <= nk2[1] < half:
                n2 = max(0.0, (self.novelty_at(nk2[0] * self.cell_size, nk2[1] * self.cell_size)
                        if nk2 in self._cells else 1.0) - dead_end_penalty)
            else:
                n2 = 1.0
            return (n1 + n2) * 0.5

        fwd_n = cell_novelty(forward_off)
        left_n = cell_novelty(left_off)
        right_n = cell_novelty(right_off)
        back_n = cell_novelty(backward_off)

        # Dead-end penalty (applied later externally, but we note the best)
        # Bias: if right > left and right > forward, turn right
        #        if left > right and left > forward, turn left
        bias = 0.0
        if right_n > fwd_n and right_n > left_n:
            bias = min(1.0, (right_n - fwd_n) * 2.0)
        elif left_n > fwd_n and left_n > right_n:
            bias = max(-1.0, -(left_n - fwd_n) * 2.0)
        elif fwd_n < 0.3 and back_n > 0.5:
            # Forward is stale but behind is fresh → turn around
            bias = -1.0 if left_n > right_n else 1.0

        return round(bias, 4)

    @property
    def coverage_percentage(self) -> float:
        """Percentage of grid cells visited out of the total grid (0–100)."""
        total = self.grid_cells * self.grid_cells
        return (len(self._cells) / total) * 100.0

    @property
    def coverage_pct(self) -> float:
        """Alias for coverage_percentage, used by dashboard."""
        return self.coverage_percentage

    @property
    def coverage_rate(self) -> float:
        """Exploration speed: coverage percentage change per 1000 ticks."""
        if len(self._coverage_history) < 10:
            return 0.0
        first_tick, first_pct = self._coverage_history[0]
        last_tick, last_pct = self._coverage_history[-1]
        delta_ticks = last_tick - first_tick
        if delta_ticks < 100:
            return 0.0
        pct_per_tick = (last_pct - first_pct) / delta_ticks
        return round(pct_per_tick * 1000, 4)  # per 1000 ticks

    def reset(self) -> None:
        self._cells.clear()
        self._recency.clear()
        self._last_tick.clear()
        self._total_ticks = 0
        self._current_cell = None
        self._history.clear()
        self._revisit_count = 0
        self._coverage_history.clear()
        self._last_coverage_tick = 0


# ---------------------------------------------------------------------------
# MemoryController — combined navigation memory
# ---------------------------------------------------------------------------

class FailureMemory:
    """Remember positions where Mario fell or got badly stuck.

    Stores fallen locations as grid keys. When returning to a known
    failure cell, the novelty is suppressed and escape behavior is
    biased away from the fall direction.

    Also tracks **dead-end directions** — directions (as heading bins)
    that led to failure from a specific cell, so the agent avoids
    repeating the same bad escape direction.
    """

    def __init__(self, cell_size: float = 200.0):
        self.cell_size = cell_size
        self._failures: set[tuple[int, int]] = set()
        # dead-end directions: {(cell_x, cell_z): set_of_heading_bins}
        # heading bins: N=0, NE=1, E=2, SE=3, S=4, SW=5, W=6, NW=7
        self._dead_ends: dict[tuple[int, int], set[int]] = {}

    @staticmethod
    def _heading_bin(heading: float) -> int:
        """Quantize heading (radians) into 8 bins (0-7, N=0, clockwise)."""
        # Normalise to [0, 2π), then quantize
        h = heading % (2 * math.pi)
        return int(round(h / (2 * math.pi) * 8)) % 8

    def record_failure(self, x: float, z: float) -> None:
        """Mark the grid cell containing (x, z) as a failure location."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        self._failures.add(key)

    def record_dead_end(self, x: float, z: float, heading: float) -> None:
        """Record that heading led to a dead end from cell at (x,z)."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        if key not in self._dead_ends:
            self._dead_ends[key] = set()
        self._dead_ends[key].add(self._heading_bin(heading))

    def is_failure_cell(self, x: float, z: float) -> bool:
        """Check if (x, z) is in a previously failed cell."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        return key in self._failures

    def is_dead_end(self, x: float, z: float, heading: float) -> bool:
        """Check if heading is a known dead-end direction from (x,z)."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        if key not in self._dead_ends:
            return False
        return self._heading_bin(heading) in self._dead_ends[key]

    def worst_heading(self, x: float, z: float) -> int | None:
        """Return the heading bin that most recently caused a dead end
        from the given cell, or None if no dead ends known."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        if key not in self._dead_ends or not self._dead_ends[key]:
            return None
        return max(self._dead_ends[key])  # Return worst (arbitrary pick)

    def best_free_heading(self, x: float, z: float,
                          current_heading: float) -> float:
        """Return a heading (radians) that avoids known dead-end bins.
        Prefers the 3 bins closest to *current_heading* that are not
        dead ends. Falls back to current_heading unchanged."""
        key = (int(math.floor(x / self.cell_size)),
               int(math.floor(z / self.cell_size)))
        blocked = self._dead_ends.get(key, set())
        if not blocked:
            return current_heading

        current_bin = self._heading_bin(current_heading)
        # Check bins in order: current, +1, -1, +2, -2, +3, -3, +4
        candidates = [(current_bin + i) % 8 for i in [0, 1, -1, 2, -2, 3, -3, 4]]
        for cb in candidates:
            if cb not in blocked:
                # Return heading at centre of this bin (in radians)
                return cb * (2 * math.pi / 8)
        return current_heading

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
        # Also check dead-end direction from current cell
        if self.is_dead_end(x, z, heading):
            return 0.5
        return 0.0

    @property
    def failure_count(self) -> int:
        return len(self._failures)

    @property
    def dead_end_count(self) -> int:
        """Total number of (cell, heading_bin) dead-end records."""
        return sum(len(v) for v in self._dead_ends.values())

    @property
    def dead_end_cells(self) -> set[tuple[int, int]]:
        """Set of grid cell keys that have any dead-end heading recorded."""
        return set(self._dead_ends.keys())

    def reset(self) -> None:
        self._failures.clear()
        self._dead_ends.clear()


class MemoryController:
    """Aggregate stuck detection, spatial memory, cliff detection, and novelty into an
    ``escape_behavior`` flag.

    The controller combines:
    - StuckDetector (temporal, frame, rate, Y-axis signals)
    - SpatialMemoryMap (novelty, loop_score, exploration_mode)
    - FailureMemory (fallen locations for avoidance)
    - CliffDetector (multi-frame cliff confirmation with hysteresis)
    """

    def __init__(self,
                 stuck: StuckDetector | None = None,
                 spatial: SpatialMemoryMap | None = None,
                 failures: FailureMemory | None = None,
                 cliff: CliffDetector | None = None):
        self.stuck = stuck or StuckDetector()
        self.spatial = spatial or SpatialMemoryMap()
        self.failures = failures or FailureMemory()
        self.cliff = cliff or CliffDetector()
        self.escape_behavior: bool = False
        self._stuck_score: float = 0.0
        self._stuck_duration: float = 0.0
        self._novelty: float = 1.0
        self._fallen: bool = False
        self._last_pos = (0.0, 0.0, 0.0)
        self._fall_pos = (0.0, 0.0, 0.0)
        self._cliff_state = {"cliff_detected": False,
                             "cliff_confidence": 0.0,
                             "raw_lower_field_green": 1.0}

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float, x: float, z: float,
               pos_y: float = 0.0, heading: float = 0.0,
               flow_asymmetry: float = 0.0,
               flow_looming: float = 0.0,
               flow_cliff: float = 1.0) -> tuple:
        """Feed one tick; returns ``(stuck_score, stuck_duration, novelty,
        escape_behavior, fallen)``."""
        self._stuck_score, self._stuck_duration, self._fallen = self.stuck.update(
            temporal_energy, frame_seq, forward_rate, pos_y
        )
        self._novelty = self.spatial.update(x, z)

        # Update cliff detector with multi-frame confirmation
        self._cliff_state = self.cliff.update(flow_cliff)

        # Record position for fall detection
        self._last_pos = (x, pos_y, z)

        # If fallen, record the last safe position as failure + dead-end direction
        if self._fallen and self._fall_pos == (0.0, 0.0, 0.0):
            self._fall_pos = self._last_pos
            self.failures.record_failure(x, z)
            self.failures.record_dead_end(x, z, heading)

        # Flow-aware escape threshold: looming lowers threshold,
        # cliff (multi-frame confirmed) forces immediate escape
        flow_danger = max(0.0, flow_looming - 0.3) * 2.0  # 0..1+ from looming
        cliff_emergency = (self._cliff_state["cliff_detected"]
                           and temporal_energy > 0.005)
        adjusted_threshold = 0.8 - flow_danger * 0.4
        self.escape_behavior = (
            (self._stuck_score >= adjusted_threshold
             and self.spatial.exploration_mode)
            or self._fallen
            or cliff_emergency
        )
        return (self._stuck_score, self._stuck_duration,
                self._novelty, self.escape_behavior, self._fallen)

    def reset(self) -> None:
        self.stuck.reset()
        self.spatial.reset()
        self.failures.reset()
        self.cliff.reset()
        self.escape_behavior = False
        self._stuck_score = 0.0
        self._stuck_duration = 0.0
        self._novelty = 1.0
        self._fallen = False
        self._fall_pos = (0.0, 0.0, 0.0)
        self._cliff_state = {"cliff_detected": False,
                             "cliff_confidence": 0.0,
                             "raw_lower_field_green": 1.0}

    @property
    def stuck_score(self) -> float: return self._stuck_score

    @property
    def stuck_duration(self) -> float: return self._stuck_duration

    @property
    def novelty(self) -> float: return self._novelty

    @property
    def fallen(self) -> bool: return self._fallen

    @property
    def coverage_percentage(self) -> float:
        """Percentage of the total grid cells visited (0–100)."""
        return self.spatial.coverage_percentage

    @property
    def coverage_pct(self) -> float:
        """Alias for coverage_percentage for dashboard."""
        return self.spatial.coverage_pct

    @property
    def coverage_rate(self) -> float:
        """Exploration speed: percentage change per 1000 ticks."""
        return self.spatial.coverage_rate

    @property
    def dead_end_count(self) -> int:
        """Number of recorded (cell, heading) dead-end pairs."""
        return self.failures.dead_end_count

    @property
    def dead_end_cells(self) -> set[tuple[int, int]]:
        """Set of grid cells that are known dead ends."""
        return self.failures.dead_end_cells

    @property
    def cliff_detected(self) -> bool:
        """Multi-frame confirmed cliff state."""
        return self._cliff_state["cliff_detected"]

    @property
    def cliff_confidence(self) -> float:
        """Ratio of frames in confirmation window below threshold."""
        return self._cliff_state["cliff_confidence"]

    @property
    def cliff_raw(self) -> float:
        """Latest raw lower_field_green reading."""
        return self._cliff_state["raw_lower_field_green"]