"""Spatial memory, stuck detection, and cliff awareness for Fly64.

Phase 1: Stuck detection + spatial memory map + novelty-driven escape.
Phase 3: CliffDetector — multi-frame confirmation of lower_field_green dips.
"""

from __future__ import annotations

import math
import time
import hashlib
import pickle
from collections import deque
from pathlib import Path

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
                 y_min: float = 50.0,       # P0-3: -100→50 (SM64 ground~120, Y<50 fallen)
                 y_max: float = 500.0):      # P0-3: 1000→500
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
        # R31-fix4: y history for the vertical-velocity term + thresholds
        self._y_hist: list[tuple[float, float]] = []
        self.fall_vz_min = -120.0        # u/s: sustained descent = falling
        self.fall_debounce_ticks = 3     # ~60 ms of falling before flagged
        self.map_reset_ticks = 10        # ~200 ms below floor before reset

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float, pos_y: float = 0.0) -> tuple[float, float, bool]:
        """Return ``(stuck_score, stuck_duration, fallen)`` for this tick."""
        # --- Y-axis state: altitude alone is NOT "fallen" (R31-fix4) ---
        # The old predicate `pos_y < y_min or pos_y > y_max` mislabelled
        # legal high ground (towers/platforms at y>500) as a fall and had no
        # velocity term or debounce.  Accurate model:
        #   FALLING   sustained downward velocity (a fall in progress)
        #   OFF_MAP   below the map floor, sustained (needs a reset)
        #   high y with |vz| small is legitimate standing — never a fall.
        self._y_hist.append((0.0, float(pos_y)))
        self._y_hist = self._y_hist[-16:]
        vz = 0.0
        if len(self._y_hist) >= 2:
            za = self._y_hist[0][1]
            zb = self._y_hist[-1][1]
            ticks = len(self._y_hist) - 1
            vz = (zb - za) / (ticks * self._dt)
        falling = vz < self.fall_vz_min
        below_floor = pos_y < self.y_min
        if falling or below_floor:
            self._fall_recovery_ticks += 1
        else:
            self._fall_recovery_ticks = 0
        # debounced: velocity-based FALLING needs 3 sustained ticks; but
        # below-floor is unambiguous — fires immediately (t23 contract:
        # fallen -> escape without waiting)
        self._fallen = ((falling and self._fall_recovery_ticks >= self.fall_debounce_ticks)
                        or below_floor)

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
        # t23 fix③: the fallen term no longer PINS stuck_score at 1.0 —
        # the score decays normally once displacement resumes.  Fallen
        # still drives escape via escape_behavior's unconditional clause;
        # feeding a synthetic 1.0 here kept loop_score saturated for the
        # whole recovery (Ghost House lock factor 3).
        stuck_score = max(t_score, f_score, r_score)

        currently_stuck = temporal_stuck or frame_stuck or rate_stuck or self._fallen
        if currently_stuck:
            self._stuck_duration += self._dt
        else:
            self._stuck_duration = 0.0
        self._was_stuck = currently_stuck

        return stuck_score, self._stuck_duration, self._fallen

    @property
    def stuck_score(self) -> float:
        # t23 fix③: no fallen pin — decays normally with displacement.
        return max(
            min(1.0, self._temporal_low_s / self.temporal_stuck_s),
            min(1.0, self._frame_still_s / self.frame_stuck_s),
            min(1.0, self._rate_low_s / self.rate_stuck_s),
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
                 loop_threshold: float = 0.6,
                 y_layers: int = 5,
                 fast_decay: float = 0.995):    # P2: fast novelty decay
        self.cell_size = cell_size
        self.grid_cells = grid_cells
        self.y_layers = y_layers
        self.recency_decay = recency_decay
        self.fast_decay = fast_decay          # dual-timescale novelty
        self.loop_window = loop_window
        self.loop_threshold = loop_threshold

        self._cells: dict[tuple[int, int, int], np.uint16] = {}
        self._recency: dict[tuple[int, int, int], float] = {}
        self._last_tick: dict[tuple[int, int, int], int] = {}
        self._total_ticks = 0
        self._current_cell: tuple[int, int, int] | None = None
        self._history: deque[tuple[int, int, int]] = deque(maxlen=loop_window)
        self._revisit_count = 0
        self._window_counts: dict[tuple[int, int, int], int] = {}
        self._window_flags: deque[bool] = deque()
        self._coverage_history: deque[tuple[int, float]] = deque(maxlen=6000)
        self._last_coverage_tick = 0
        self._adj: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
        self._scene_db = SceneDatabase()

    # -- helpers ----------------------------------------------------------

    def _key(self, x: float, y: float = 0.0, z: float = 0.0) -> tuple[int, int, int]:
        """Map world coords to grid key (x, y_layer, z).

        EVO L2: x/z are UNBOUNDED — the hash grid grows with exploration so
        the memory map always covers where Mario actually is.  The old ±5000
        clamp piled every out-of-bounds position onto one boundary column,
        desynchronising the memory map from the true trajectory (the grid/
        trajectory mismatch fixed here).  Y stays layered ([-500,1500] →
        [0, y_layers-1])."""
        ix = int(math.floor(x / self.cell_size))
        iy = max(0, min(self.y_layers - 1, int((y + 500) / 400)))
        iz = int(math.floor(z / self.cell_size))
        return (ix, iy, iz)

    def coverage_gap_vector(self, x: float, z: float,
                            radius: int = 6) -> tuple[float, float] | None:
        """EVO R20 (CX-3): unit vector toward the centroid of UNVISITED
        cells within *radius* grid steps of (x, z) — the exploration goal
        direction.  None when the neighbourhood is fully covered.

        EVO L2: keys are unbounded now (no modulo wrap — the old wrap-around
        fabricated unvisited cells beyond the map edge), and the key axis
        order follows the 3D (x, y_layer, z) grid."""
        cxk = self._key(x, 0.0, z)
        sx = sz = n = 0
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                k = (cxk[0] + dx, cxk[1], cxk[2] + dz)
                if k not in self._cells:
                    sx += dx
                    sz += dz
                    n += 1
        if n == 0:
            return None
        vec = (sx / n, sz / n)
        norm = math.hypot(*vec)
        if norm < 1e-6:
            return None
        return (vec[0] / norm, vec[1] / norm)

    def frontier_direction(self, x: float, y: float = 0.0, z: float = 0.0,
                           search_radius: int = 15) -> tuple[float, float] | None:
        """Find unit vector toward the nearest FRONTIER cell — an UNVISITED
        cell that neighbours at least one VISITED cell.  This pulls the agent
        toward the boundary of explored territory rather than just the nearest
        unvisited cell (which may be isolated and unreachable)."""
        cxk = self._key(x, y, z)
        best_dist = float('inf')
        best_dx = best_dz = 0.0
        for dx in range(-search_radius, search_radius + 1):
            for dz in range(-search_radius, search_radius + 1):
                if dx == 0 and dz == 0:
                    continue  # skip center (it is visited)
                k = (cxk[0] + dx, cxk[1], cxk[2] + dz)   # unbounded grid
                if k in self._cells:
                    continue  # already visited
                # Check if any neighbour is visited (frontier condition)
                is_frontier = False
                for ndx in (-1, 0, 1):
                    for ndz in (-1, 0, 1):
                        if ndx == 0 and ndz == 0:
                            continue
                        nk = (k[0] + ndx, cxk[1], k[2] + ndz)
                        if nk in self._cells:
                            is_frontier = True
                            break
                    if is_frontier:
                        break
                if not is_frontier:
                    continue
                dist = math.hypot(dx, dz)
                if dist < best_dist:
                    best_dist = dist
                    best_dx = dx / dist
                    best_dz = dz / dist
        if best_dist == float('inf'):
            return None
        return (best_dx, best_dz)

    def _decay_recency(self) -> None:
        c = self.recency_decay
        decay_interval = 10
        if self._total_ticks % decay_interval == 0:
            for k in list(self._recency.keys()):
                self._recency[k] *= c

    # -- public API -------------------------------------------------------

    def update(self, x: float, y: float = 0.0, z: float = 0.0) -> float:
        """Record a visit at (x, y, z); returns the novelty of the visited cell (0–1)."""
        self._total_ticks += 1
        key = self._key(x, y, z)
        prev_cell = self._current_cell
        self._current_cell = key
        # Topology: a cell *transition* (A→B, A≠B) records one traversal step.
        if prev_cell is not None and prev_cell != key:
            edge = (prev_cell, key) if prev_cell < key else (key, prev_cell)
            self._adj[edge] = self._adj.get(edge, 0) + 1

        # Track revisits in rolling window — exact counting: a visit is a
        # "revisit" when the same key already exists in the current window;
        # evictions decrement, so the score stays within [0, 1] forever.
        revisit = self._window_counts.get(key, 0) > 0
        if self._history.maxlen is not None and len(self._history) >= self._history.maxlen:
            old_key = self._history.popleft()
            old_flag = self._window_flags.popleft()
            if self._window_counts.get(old_key, 0) > 0:
                self._window_counts[old_key] -= 1
            if old_flag:
                self._revisit_count -= 1
        self._history.append(key)
        self._window_flags.append(revisit)
        self._window_counts[key] = self._window_counts.get(key, 0) + 1
        if revisit:
            self._revisit_count += 1
        self._revisit_count = max(0, self._revisit_count)

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
        key = self._key(x, 0, z)
        if key not in self._cells:
            return 1.0
        return self._novelty(key)

    def _novelty(self, key: tuple[int, int]) -> float:
        """novelty = 1 / (visit_count^2 + 1) × recency × (1 - revisit_penalty - repulsion)
        
        Square-law decay: 1 visit=0.50, 2 visits=0.20 (vs 0.33 before).
        This aggressively reduces re-exploration of already-visited cells.
        """
        v = int(self._cells[key])
        r = self._recency.get(key, 0.0)
        base = (1.0 / (v * v + 1)) * r
        penalty = self.revisit_penalty
        if self._scene_db.revisit_count > 10:
            penalty = min(1.0, penalty + self._get_repulsion(key))
        return base * (1.0 - penalty)

    @property
    def revisit_penalty(self) -> float:
        """Scene-revisit penalty in [0, 0.7]: 0 when revisit_count ≤ 2,
        linearly increasing to 0.7 at revisit_count = 5 and above.
        Enhanced from original 0→0.5 over 3→8 for better loop suppression."""
        rc = self._scene_db.revisit_count
        if rc <= 2:
            return 0.0
        return min((rc - 2) * 0.35, 0.7)

    def _get_repulsion(self, key: tuple[int, ...]) -> float:
        """Return repulsion in [0, 0.8] for cells near high-revisit areas.

        When ``revisit_count > 10``, cells whose ``visit_count > 10`` are
        considered *high-revisit*.  This method returns a repulsion value for
        *key* proportional to the nearby high-revisit cells within a 2-cell
        radius, decaying with distance.  Repulsion is 0 when ``revisit_count
        <= 10``.  Keys may be 2-tuples (legacy x,z) or 3-tuples (x,y,z from
        the 3D grid upgrade) — repulsion operates on the x/z footprint.
        """
        max_repulsion = 0.8
        revisit_threshold = 10
        decay_radius = 2

        if self._scene_db.revisit_count <= revisit_threshold:
            return 0.0

        cx = key[0]
        cz = key[-1]
        iy = key[1] if len(key) == 3 else 0
        total_rep = 0.0
        for dx in range(-decay_radius, decay_radius + 1):
            for dz in range(-decay_radius, decay_radius + 1):
                nk = (cx + dx, iy, cz + dz) if len(key) == 3 else (cx + dx, cz + dz)
                if nk in self._cells and int(self._cells[nk]) > revisit_threshold:
                    dist = math.sqrt(dx * dx + dz * dz)
                    weight = 1.0 if dist == 0 else 1.0 / (dist * 1.5)
                    visit_excess = min(1.0, (int(self._cells[nk]) - revisit_threshold) / 20.0)
                    total_rep = max(total_rep, weight * visit_excess * max_repulsion)
        return round(total_rep, 4)

    @property
    def scene_db(self) -> SceneDatabase:
        return self._scene_db

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
        # 3D grid: aggregate the y-layers into one top-down column per (x,z)
        # cell — k[0]=x, k[2]=z (k[1] is the y-LAYER; using it for z was the
        # grid/trajectory desync bug).
        columns: dict[tuple[int, int], float] = {}
        for k in self._cells.keys():
            col = (k[0], k[2])
            r = float(self._recency.get(k, 0.0))
            if r > columns.get(col, -1.0):
                columns[col] = r
        xs = np.array([ix * self.cell_size + self.cell_size * 0.5 for ix, _ in columns], np.float32)
        zs = np.array([iz * self.cell_size + self.cell_size * 0.5 for _, iz in columns], np.float32)
        heats = np.array(list(columns.values()), np.float32)
        return xs, zs, heats

    def novelty_direction(self, x: float, z: float, heading: float,
                          dead_end_keys: set[tuple[int, int]] | None = None,
                          scene_change_rate: float = 0.0,
                          forced_bold_explore: bool = False) -> float:
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

        If *forced_bold_explore* is True (nested loop breakout), the dead-end
        penalty is reduced to 0.0 so old dead-end labels do not suppress the
        forced breakout maneuver.
        """
        base_key = self._key(x, 0, z)
        cx, _, cz = base_key

        # 4 direction offsets relative to heading (sm64: heading 0 = +Z north)
        # Forward = (+sin(heading), +cos(heading)) in grid space
        sin_h = math.sin(heading)
        cos_h = math.cos(heading)

        # A9 (P1, BRAIN 2.7.0): the 8-direction grid discretisation with its
        # ±0.3 dead zone is replaced by a continuous heading→offset mapping
        # (nearest cell along the exact unit direction).  The novelty signal
        # feeding the CX goal memory is now a continuous population vector
        # instead of a thresholded 8-way switch.
        def dir_off(sin_a, cos_a):
            """Continuous direction → nearest grid-cell offset (no dead zone)."""
            return int(round(sin_a)), int(round(cos_a))

        forward_off = dir_off(sin_h, cos_h)                  # heading
        left_off = dir_off(-cos_h, sin_h)                    # heading + 90°
        right_off = dir_off(cos_h, -sin_h)                   # heading - 90°
        backward_off = dir_off(-sin_h, -cos_h)               # heading + 180°

        half = self.grid_cells // 2

        # When scene_change_rate >= 0.3 (new area), halve the dead-end penalty
        # so old dead-end info doesn't suppress exploration in a fresh scene.
        # When forced_bold_explore is active (nested loop breakout), eliminate
        # the dead-end penalty entirely so old labels cannot block the breakout.
        if forced_bold_explore:
            _penalty_modifier = 0.0
        elif scene_change_rate >= 0.3:
            _penalty_modifier = 0.5
        else:
            _penalty_modifier = 1.0

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
        """Percentage of cells visited relative to the explored bounding box.

        EVO L2: the grid is unbounded now, so a fixed 50×50 denominator no
        longer applies.  Denominator = cells enclosed by the visited bounding
        box (+2-cell ring), floored at the nominal 2500 so sparse corridor
        runs don't inflate coverage to 100%."""
        total = max(self.grid_cells * self.grid_cells, 1)
        if self._cells:
            xs = [k[0] for k in self._cells]
            zs = [k[2] for k in self._cells]
            bw = (max(xs) - min(xs) + 5)
            bh = (max(zs) - min(zs) + 5)
            total = max(total, bw * bh)
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

    @property
    def coverage_stalled(self) -> bool | None:
        """``None`` while the coverage history warms up (<10 windows), else
        True when coverage_rate ≈ 0 (no new cells visited recently)."""
        if len(self._coverage_history) < 10:
            return None
        return self.coverage_rate < 0.01

    def recent_path(self, n: int = 80) -> list[dict]:
        """Last *n* distinct cell centres actually walked through (oldest first).

        This is the short-term **ordered path memory** — the ordered trail the
        dashboard trajectory view and any future planner can consume.  Only
        cell *transitions* are kept (consecutive duplicates collapse).
        """
        cells = [k for i, k in enumerate(self._history) if i == 0 or k != self._history[i - 1]]
        return [{"x": k[0] * self.cell_size + self.cell_size * 0.5,
                 "z": k[1] * self.cell_size + self.cell_size * 0.5}
                for k in cells[-n:]]

    @property
    def adjacency_count(self) -> int:
        """Number of distinct traversed cell-to-cell edges (map connectivity)."""
        return len(self._adj)

    @property
    def traversal_steps(self) -> int:
        """Total recorded cell transitions (= sum of all edge counts)."""
        return sum(self._adj.values())

    def adjacency_list(self, limit: int = 400) -> list[list[float]]:
        """Traversal edges as world-coordinate pairs for 3D/map rendering.

        Returns ``[ax, az, bx, bz]`` (cell centres), most-travelled edges
        first, capped at *limit*.
        """
        edges = sorted(self._adj.items(), key=lambda kv: -kv[1])[:limit]
        out = []
        for (a, b), _c in edges:
            out.append([a[0] * self.cell_size + self.cell_size * 0.5,
                        a[1] * self.cell_size + self.cell_size * 0.5,
                        b[0] * self.cell_size + self.cell_size * 0.5,
                        b[1] * self.cell_size + self.cell_size * 0.5])
        return out

    def save_state(self, path: str | Path) -> None:
        """Persist the visited-cell map + traversal graph (pickle).

        ``recency`` is not saved — it is recomputed from visits on load so a
        restored map starts "fresh" instead of carrying stale decay weights.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {"v": 2,
                "cells": {f"{k[0]},{k[1]},{k[2]}": int(v) for k, v in self._cells.items()},
                "adj": {f"{a[0]},{a[1]},{a[2]}|{b[0]},{b[1]},{b[2]}": c for (a, b), c in self._adj.items()}}
        with open(p, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load_state(self, path: str | Path) -> int:
        """Restore a saved visit map. Returns number of cells restored."""
        p = Path(path)
        try:
            with open(p, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, dict) or data.get("v") not in (1, 2):
                return 0
            self._cells = {}
            for k, v in data["cells"].items():
                key = tuple(int(x) for x in k.split(","))
                if len(key) == 2:
                    key = (key[0], 0, key[1])  # pad v1 (x,z) → (x,y,z)
                self._cells[key] = np.uint16(v)
            self._recency = {k: 1.0 for k in self._cells}
            self._last_tick = {k: 0 for k in self._cells}
            self._adj = {}
            for s, c in data.get("adj", {}).items():
                pair = []
                for part in s.split("|"):
                    key = tuple(int(x) for x in part.split(","))
                    if len(key) == 2:
                        key = (key[0], 0, key[1])
                    pair.append(key)
                self._adj[(pair[0], pair[1])] = int(c)
            return len(self._cells)
        except Exception:
            return 0

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
        self._adj.clear()

    def reset_scene_db(self) -> None:
        """Clear the scene database (landmark signatures)."""
        self._scene_db.reset()


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

    def nearest_failure_vector(self, x: float, z: float,
                               radius_cells: float = 2.5) -> tuple[float, float] | None:
        """Unit vector toward the nearest known failure cell within radius.

        Returns None when no failure cell lies within *radius_cells* grid
        steps of (x, z).
        """
        cx = int(math.floor(x / self.cell_size))
        cz = int(math.floor(z / self.cell_size))
        best, best_d = None, radius_cells
        for (fx, fz) in self._failures:
            d = math.hypot(fx - cx, fz - cz)
            if d <= radius_cells and d < best_d:
                best, best_d = (fx, fz), d
        if best is None:
            return None
        wx = (best[0] + 0.5) * self.cell_size - x
        wz = (best[1] + 0.5) * self.cell_size - z
        n = math.hypot(wx, wz) or 1.0
        return (wx / n, wz / n)

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


# ---------------------------------------------------------------------------
# SceneDatabase — scene signature ring buffer with revisit detection
# ---------------------------------------------------------------------------

class SceneDatabase:
    """Ring buffer of 128-dim scene signatures with cosine-similarity matching.

    Stores up to *maxlen* (signature, tick) pairs. On each query computes
    the cosine similarity of the query signature against every stored
    signature (all L2-normalised) and reports the best match score and
    the count of matches above *match_threshold*.

    Attributes
    ----------
    revisit_count : int
        Number of stored signatures whose cosine similarity exceeds the
        match threshold (set by the most recent match() call).
    best_score : float
        Highest cosine similarity among all stored signatures (set by
        the most recent match() call).
    size : int
        Current number of stored signatures.
    """

    def __init__(self, maxlen: int = 500, match_threshold: float = 0.85):
        self._buffer: deque[tuple[np.ndarray, int]] = deque(maxlen=maxlen)
        self._match_threshold = match_threshold
        self._revisit_count = 0
        self._best_score = 0.0

    def add(self, sig: np.ndarray, tick: int) -> None:
        """Store a (signature, tick) pair in the ring buffer."""
        self._buffer.append((sig.copy(), tick))

    def match(self, sig: np.ndarray) -> tuple[float, int]:
        """Compute cosine similarity against all stored signatures.

        Parameters
        ----------
        sig : ndarray, shape (128,)
            L2-normalised scene signature to match.

        Returns
        -------
        best_score : float
            Highest cosine similarity found (0 if buffer empty).
        revisit_count : int
            Number of stored signatures with similarity > threshold.
        """
        best_score = 0.0
        revisit_count = 0
        n = len(self._buffer)
        if n == 0:
            self._best_score = 0.0
            self._revisit_count = 0
            return 0.0, 0

        # Vectorised: stack all stored signatures → (N, 128) @ (128,) = (N,)
        stored = np.stack([s for s, _ in self._buffer], axis=0)  # (N, 128)
        sims = stored @ sig  # cosine similarity for unit vectors → (N,)
        best_score = float(sims.max())
        revisit_count = int((sims > self._match_threshold).sum())

        self._best_score = best_score
        self._revisit_count = revisit_count
        return best_score, revisit_count

    @property
    def revisit_count(self) -> int:
        """Number of stored signatures matching the last query."""
        return self._revisit_count

    @property
    def best_score(self) -> float:
        """Highest cosine similarity from the last query."""
        return self._best_score

    @property
    def size(self) -> int:
        """Current number of stored signatures."""
        return len(self._buffer)

    def reset(self) -> None:
        """Clear the ring buffer and reset match state."""
        self._buffer.clear()
        self._revisit_count = 0
        self._best_score = 0.0

    # ── Pickle persistence ────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Serialize the buffer (signatures + ticks) to disk as pickle."""
        data = [(sig, tick) for sig, tick in self._buffer]
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: str | Path, maxlen: int = 500,
             match_threshold: float = 0.85) -> "SceneDatabase":
        """Deserialize a previously saved SceneDatabase, or return empty."""
        db = cls(maxlen=maxlen, match_threshold=match_threshold)
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            for sig, tick in data:
                db._buffer.append((sig, tick))
        except (FileNotFoundError, pickle.UnpicklingError, EOFError):
            pass
        return db


# ---------------------------------------------------------------------------
# MotionStateDetector — 5-state motion anomaly detection with majority vote
# ---------------------------------------------------------------------------

class MotionStateDetector:
    """Detect motion anomaly states with majority-vote over a sliding window.

    States detected:
      ``idle``        — no anomaly (default)
      ``stuck_ramp``  — ramp_score > 0.5 AND stuck_duration > 15 s AND heading_rate < 0.05
      ``oscillating`` — control.x alternates between ≤ -60 and ≥ +60 within 30 frames
      ``wall_stuck``  — wall_score > 0.4 AND escape_behavior AND stuck_duration > 10 s
      ``micro_loop``  — visited_cells < 5 AND loop_score > 0.5 AND stuck_duration > 30 s
      ``fallen``      — pos_y < -100 OR pos_y > 1000

    Each state is evaluated every tick. The **active state** is the one with the
    majority of votes over the last *window* frames (default 30).  Confidence is
    the fraction of frames in the window that voted for that state.  Duration is
    how long the active state has been continuously held.

    ``state_history`` keeps the last *history_size* state transitions (name →
    new name with start tick and confidence).
    """

    IDLE = "idle"
    STUCK_RAMP = "stuck_ramp"
    OSCILLATING = "oscillating"
    WALL_STUCK = "wall_stuck"
    MICRO_LOOP = "micro_loop"
    FALLEN = "fallen"
    STATES = (IDLE, STUCK_RAMP, OSCILLATING, WALL_STUCK, MICRO_LOOP, FALLEN)

    def __init__(self, window: int = 30, history_size: int = 100):
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window
        self.history_size = history_size

        # Ring of per-frame state votes — one state name per frame
        self._vote_buffer: deque[str] = deque(maxlen=window)

        # State history — list of transition records
        self._transitions: deque[dict] = deque(maxlen=history_size)

        # Active (majority) state and its continuity
        self._active_state: str = self.IDLE
        self._state_start_tick: int = 0
        self._total_ticks: int = 0
        self._latest_confidence: float = 0.0
        self._latest_duration: float = 0.0

        # Oscillation detection: history of control.x for sign-change counts
        self._ctrl_x_buf: deque[int] = deque(maxlen=window)

    # ---- per-frame detection helpers ----------------------------------------

    def _detect_stuck_ramp(self, ramp_score: float, stuck_duration: float,
                           heading_rate: float) -> bool:
        return ramp_score > 0.5 and stuck_duration > 15.0 and heading_rate < 0.05

    def _detect_oscillating(self) -> bool:
        """Detect oscillation in control.x: ≥3 alternations between ≤-60 and ≥+60."""
        if len(self._ctrl_x_buf) < 6:
            return False
        buf = list(self._ctrl_x_buf)
        alternations = 0
        prev_was_neg = None
        for v in buf:
            if v <= -60:
                if prev_was_neg is False:   # was pos, now neg
                    alternations += 1
                prev_was_neg = True
            elif v >= 60:
                if prev_was_neg is True:    # was neg, now pos
                    alternations += 1
                prev_was_neg = False
        return alternations >= 3

    def _detect_wall_stuck(self, wall_score: float, escape_behavior: bool,
                           stuck_duration: float) -> bool:
        return wall_score > 0.4 and escape_behavior and stuck_duration > 10.0

    def _detect_micro_loop(self, visited_cells: int, loop_score: float,
                           stuck_duration: float) -> bool:
        # Tier 1: classic micro-loop in small area
        if visited_cells < 5 and loop_score > 0.5 and stuck_duration > 30.0:
            return True
        # Tier 2: general stuck — any cell count, stuck > 90s (covers exploration gaps)
        if stuck_duration > 90.0 and loop_score > 0.5:
            return True
        return False

    @staticmethod
    def _detect_fallen(pos_y: float) -> bool:
        return pos_y < 50.0 or pos_y > 1000.0

    def _vote(self, *, ramp_score: float = 0.0,
              stuck_duration: float = 0.0,
              heading_rate: float = 0.0,
              wall_score: float = 0.0,
              escape_behavior: bool = False,
              visited_cells: int = 0,
              loop_score: float = 0.0,
              pos_y: float | None = None) -> str:
        """Return the per-frame state name, prioritised by severity."""
        # EVO R16 · P1-A3: pos_y validity gate.  Unknown elevation (None or
        # the historical 0.0 default) must not vote FALLEN — SM64 ground sits
        # at Y≈120, so 0.0-as-default masqueraded every anomaly as fallen.
        fallen_active = pos_y is not None and pos_y != 0.0 and self._detect_fallen(pos_y)
        if fallen_active:
            return self.FALLEN
        if self._detect_micro_loop(visited_cells, loop_score, stuck_duration):
            return self.MICRO_LOOP
        if self._detect_oscillating():
            return self.OSCILLATING
        if self._detect_wall_stuck(wall_score, escape_behavior, stuck_duration):
            return self.WALL_STUCK
        if self._detect_stuck_ramp(ramp_score, stuck_duration, heading_rate):
            return self.STUCK_RAMP
        return self.IDLE

    # ---- public API ---------------------------------------------------------

    def update(
        self,
        *,
        ramp_score: float = 0.0,
        stuck_duration: float = 0.0,
        heading_rate: float = 0.0,
        wall_score: float = 0.0,
        escape_behavior: bool = False,
        visited_cells: int = 0,
        loop_score: float = 0.0,
        pos_y: float | None = None,
        control_x: int = 0,
    ) -> dict:
        """Feed one tick; returns ``get_state()``."""
        self._total_ticks += 1
        self._ctrl_x_buf.append(control_x)

        # Per-frame vote
        vote = self._vote(
            ramp_score=ramp_score,
            stuck_duration=stuck_duration,
            heading_rate=heading_rate,
            wall_score=wall_score,
            escape_behavior=escape_behavior,
            visited_cells=visited_cells,
            loop_score=loop_score,
            pos_y=pos_y,
        )
        self._vote_buffer.append(vote)

        # Majority-vote over the window
        if len(self._vote_buffer) < self.window:
            majority_state = vote  # use latest until window fills
            confidence = 1.0
        else:
            counts: dict[str, int] = {}
            for s in self._vote_buffer:
                counts[s] = counts.get(s, 0) + 1
            max_count = max(counts.values())
            # Pick the most-frequent state; tie-break by severity order
            best = max(
                (s for s, c in counts.items() if c == max_count),
                key=lambda s: self.STATES.index(s),
            )
            majority_state = best
            confidence = round(max_count / self.window, 3)

        # Track active state continuity
        if majority_state != self._active_state:
            # Record transition
            self._transitions.append({
                "from": self._active_state,
                "to": majority_state,
                "tick": self._total_ticks,
                "confidence": confidence,
            })
            self._active_state = majority_state
            self._state_start_tick = self._total_ticks

        duration_in_state = round(
            (self._total_ticks - self._state_start_tick) * 0.020, 2
        )  # 50 Hz tick interval

        self._latest_confidence = confidence
        self._latest_duration = duration_in_state

        return {
            "state": majority_state,
            "confidence": confidence,
            "duration_in_state": duration_in_state,
            "active": majority_state != self.IDLE,
        }

    def get_state(self) -> dict:
        """Full state dict for dashboard serialization (same as last update)."""
        return {
            "state": self._active_state,
            "confidence": self._latest_confidence,
            "duration_in_state": self._latest_duration,
            "active": self._active_state != self.IDLE,
        }

    @property
    def active_state(self) -> str:
        """Current majority-vote state name."""
        return self._active_state

    @property
    def active(self) -> bool:
        """True when any anomaly is active (not idle)."""
        return self._active_state != self.IDLE

    @property
    def state_history(self) -> list[dict]:
        """Last *history_size* state transitions."""
        return list(self._transitions)

    def reset(self) -> None:
        self._vote_buffer.clear()
        self._transitions.clear()
        self._ctrl_x_buf.clear()
        self._active_state = self.IDLE
        self._state_start_tick = self._total_ticks


# ---------------------------------------------------------------------------
# ReflexController — Drosophila-inspired reflex escape circuits
# ---------------------------------------------------------------------------

class ReflexController:
    """Drosophila-inspired reflex escape circuits triggered by anomaly states.

    Four reflexes, each with configurable phase timing and cooldown:

    ``stuck_ramp``
        Random turn (±60) + full forward burst (y=70) for *stuck_ramp_duration* s.
        Overrides ramp suppression.

    ``oscillating``
        Lock direction: hold x=±69 (single direction, no alternation) for
        *oscillating_duration* s. Breaks the back-and-forth cycle.

    ``wall_stuck``
        Reverse (y=-20) for *wall_stuck_reverse_duration* s, then turn opposite
        direction for *wall_stuck_turn_duration* s.

    ``micro_loop``
        Immediately triggers ``_triggered_micro_loop`` flag so main.py can set
        forced_bold_explore = True without the normal 10 s wait.

    A reflex fires when the anomaly state matches and confidence >= threshold.
    Each reflex has a cooldown preventing re-firing within *cooldown_duration* s
    of its last activation.  Reflexes run BEFORE normal escape but AFTER cliff
    avoidance.
    """

    STUCK_RAMP = "stuck_ramp"
    OSCILLATING = "oscillating"
    WALL_STUCK = "wall_stuck"
    MICRO_LOOP = "micro_loop"
    REFLEX_TYPES = (STUCK_RAMP, OSCILLATING, WALL_STUCK, MICRO_LOOP)

    def __init__(self, confidence_threshold: float = 0.6,
                 cooldown_duration: float = 5.0,
                 stuck_ramp_duration: float = 1.5,
                 oscillating_duration: float = 2.0,
                 wall_stuck_reverse_duration: float = 0.3,
                 wall_stuck_turn_duration: float = 0.8,
                 micro_loop_duration: float = 2.0):
        self.confidence_threshold = confidence_threshold
        self.cooldown_duration = cooldown_duration
        self.stuck_ramp_duration = stuck_ramp_duration
        self.oscillating_duration = oscillating_duration
        self.wall_stuck_reverse_duration = wall_stuck_reverse_duration
        self.wall_stuck_turn_duration = wall_stuck_turn_duration
        self.micro_loop_duration = micro_loop_duration

        # Active reflex state
        self._active_reflex: str = ""
        self._reflex_phase: str = ""       # "turn" / "forward" / "reverse" / "burst"
        self._phase_timer: float = 0.0
        self._turn_direction: int = 0      # selected turn for this reflex activation

        # Cooldown timers: seconds until each reflex can fire again
        self._cooldowns: dict[str, float] = {rt: 0.0 for rt in self.REFLEX_TYPES}

        # EVO R28 · micro_loop reflex fatigue counter: tracks consecutive
        # micro_loop firings without displacement (>10u).  After 10
        # ineffective cycles, force a 5s cooldown to give the CX steering
        # a window to break the loop via idle exploration wander.
        self._micro_loop_fatigue = 0
        self._micro_loop_last_pos: tuple[float, float] | None = None
        self._last_cx_bias: float = 0.0  # EVO R28: CX steering bias for reflex turn mix

        # Aggressive mode: when health < 0.3, cooldown is halved
        self._aggressive_cooldown_factor: float = 1.0

        # Micro-loop trigger flag (consumed by main.py)
        self._triggered_micro_loop: bool = False

        # EVO R11: spin-loop fix — progress gate + mirror alternation.
        # The adaptive cooldown (EVO R6) shrank to its 0.25 s floor during
        # long stuck periods, re-firing the micro_loop reflex every ~0.3 s;
        # the reflex's turn bursts then locked the agent into continuous
        # circling (observed: anomaly=micro_loop for 973 s, heading 29°/s).
        # A biological refractory gate: the reflex re-arms with a MIRRORED
        # turn direction unless the agent has moved progress_radius units
        # since the last attempt (spontaneous-alternation behaviour).
        self._last_fire_pos: tuple[float, float] | None = None
        self._last_direction: int = 0
        self.progress_radius: float = 30.0

    # ---- helpers -----------------------------------------------------------

    # ---- public API --------------------------------------------------------

    def update(self, dt: float, anomaly_state: dict,
               rng_choice, stuck_duration: float = 0.0,
               pos: tuple[float, float] | None = None,
               breakout_hint: float = 0.0,
               wall_persist: float = 0.0) -> str:
        """Tick the reflex controller.

        Parameters
        ----------
        dt : float
            Simulation tick interval (0.020 s).
        anomaly_state : dict
            Current anomaly state from MotionStateDetector.get_state().
        rng_choice : callable
            A function ``(low, high) -> int`` for random turn selection (e.g.
            ``model.rng.integers``).
        stuck_duration : float
            Seconds the fly has been stuck — drives adaptive cooldown (EVO R6).
        wall_persist : float
            Seconds of continuous wall contact (wall_score > 0.3).  When
            > 2.0 s triggers early wall_stuck reflex BEFORE the anomaly
            detector's gate (which requires escape_behavior=True) fires.

        Returns
        -------
        active_reflex : str
            Name of currently active reflex, or empty string if none.
        """
        # Decrement cooldowns
        for rt in self.REFLEX_TYPES:
            if self._cooldowns[rt] > 0:
                self._cooldowns[rt] = max(0.0, self._cooldowns[rt] - dt)

        self._triggered_micro_loop = False

        # If a reflex is already active, advance its phase timer
        if self._active_reflex:
            self._phase_timer += dt
            self._advance_phase()
            return self._active_reflex

        # Check if a new reflex should fire
        state_name = anomaly_state.get("state", "")
        confidence = anomaly_state.get("confidence", 0.0)

        if state_name in self.REFLEX_TYPES and confidence >= self.confidence_threshold:
            if self._cooldowns[state_name] <= 0.0:
                return self._start_reflex(state_name, rng_choice,
                                          stuck_duration=stuck_duration,
                                          pos=pos,
                                          breakout_hint=breakout_hint)

        # Early wall avoidance: wall_persist > 2s triggers wall_stuck reflex
        # BEFORE the anomaly detector (which requires escape_behavior=True)
        # has a chance to fire, so the agent backs away and turns much sooner.
        if wall_persist > 2.0 and self._cooldowns[self.WALL_STUCK] <= 0.0:
            return self._start_reflex(self.WALL_STUCK, rng_choice,
                                      stuck_duration=stuck_duration,
                                      pos=pos,
                                      breakout_hint=breakout_hint)

        return ""

    def bold_direction(self) -> float:
        """Alternating breakout direction for forced bold explore (P1).

        Spontaneous alternation: mirror the last reflex/bold turn direction;
        random on first use.  Returns a normalised turn bias in [-1, 1] that
        the brain runner injects as a turn-pool current — the LIF left/right
        competition executes the manoeuvre, no direct control write.
        """
        if self._last_direction:
            self._last_direction = -self._last_direction
        else:
            self._last_direction = 69 if float(np.random.rand()) < 0.5 else -69
        return self._last_direction / 69.0

    def _start_reflex(self, reflex_type: str, rng_choice,
                      stuck_duration: float = 0.0,
                      pos: tuple[float, float] | None = None,
                      breakout_hint: float = 0.0) -> str:
        """Begin a new reflex activation.

        Adaptive cooldown (EVO R6): the longer the fly has been stuck, the
        shorter the post-reflex cooldown — prolonged stuck periods allow more
        frequent reflex attempts.  Scale: 1.0 at 0s down to 0.25 at >=90s.

        EVO R17: ``breakout_hint`` (0-1, the brain's TurnAdaptation
        oscillation signal) shifts the micro_loop reflex phase budget toward
        the forward burst — the reflex keeps ownership of the escape, but
        the brain's weave-detector biases how long the turn phase lasts.

        Returns the reflex type string.
        """
        self._active_reflex = reflex_type
        self._phase_timer = 0.0
        self._breakout_scale = 1.0 + max(0.0, min(1.0, breakout_hint))
        adaptive = max(0.25, 1.0 - stuck_duration / 120.0)
        self._cooldowns[reflex_type] = (self.cooldown_duration
                                        * self._aggressive_cooldown_factor
                                        * adaptive)

        if reflex_type == self.STUCK_RAMP:
            self._reflex_phase = "forward"
            self._turn_direction = (60 if rng_choice(0, 2) == 0 else -60)

        elif reflex_type == self.OSCILLATING:
            self._reflex_phase = "hold"
            self._turn_direction = 69 if rng_choice(0, 2) == 0 else -69

        elif reflex_type == self.WALL_STUCK:
            self._reflex_phase = "reverse"
            self._turn_direction = 60 if rng_choice(0, 2) == 0 else -60

        elif reflex_type == self.MICRO_LOOP:
            self._reflex_phase = "turn"
            # EVO R11 spin-loop fix: if the previous mirrored/random attempt
            # produced no net displacement (≥ progress_radius), flip the turn
            # direction instead of re-rolling — pure reflex-internal gating,
            # direction execution stays with the LIF motor pools.
            moved = False
            if self._last_fire_pos is not None and pos is not None:
                moved = ((pos[0] - self._last_fire_pos[0]) ** 2 +
                         (pos[1] - self._last_fire_pos[1]) ** 2) ** 0.5 >= self.progress_radius
            if self._last_direction != 0 and not moved:
                self._turn_direction = -self._last_direction
            else:
                self._turn_direction = 69 if rng_choice(0, 2) == 0 else -69
            self._last_direction = self._turn_direction
            if pos is not None:
                self._last_fire_pos = (pos[0], pos[1])

        return reflex_type

    def _advance_phase(self) -> None:
        """Advance the active reflex through its phase sequence."""
        rt = self._active_reflex
        timer = self._phase_timer

        if rt == self.STUCK_RAMP:
            # Single phase: forward burst for stuck_ramp_duration
            if timer >= self.stuck_ramp_duration:
                self._active_reflex = ""
                self._phase_timer = 0.0

        elif rt == self.OSCILLATING:
            # Single phase: hold turn for oscillating_duration
            if timer >= self.oscillating_duration:
                self._active_reflex = ""
                self._phase_timer = 0.0

        elif rt == self.WALL_STUCK:
            # Phase 1: reverse, Phase 2: opposite turn
            if self._reflex_phase == "reverse" and timer >= self.wall_stuck_reverse_duration:
                self._reflex_phase = "turn"
                self._turn_direction = -self._turn_direction  # opposite turn
                self._phase_timer = 0.0
            elif self._reflex_phase == "turn" and timer >= self.wall_stuck_turn_duration:
                self._active_reflex = ""
                self._phase_timer = 0.0

        elif rt == self.MICRO_LOOP:
            # Phase 1: turn (with CX steering bias to break heading cancellation),
            # Phase 2: forward burst.
            # EVO R28: mix cx_bias into turn direction so alternation doesn't
            # perfectly cancel the heading.
            _cx_turn = getattr(self, '_last_cx_bias', 0.0)
            # (÷ breakout scale) and hands the budget to the forward burst —
            # the reflex keeps ownership, the brain biases the mix.
            turn_dur = max(0.15, 0.5 / self._breakout_scale)
            burst_dur = max(0.5, self.micro_loop_duration - turn_dur)
            if self._reflex_phase == "turn" and timer >= turn_dur:
                self._reflex_phase = "burst"
                self._phase_timer = 0.0
            elif self._reflex_phase == "burst" and timer >= burst_dur:
                self._active_reflex = ""
                self._phase_timer = 0.0

        self._triggered_micro_loop = (rt == self.MICRO_LOOP and self._active_reflex != "")

    def get_action(self) -> dict:
        """Return the current reflex control override, or empty dict if idle.

        Returns
        -------
        dict with keys:
            ``active`` (bool)
            ``reflex`` (str) — reflex type name
            ``phase`` (str) — current phase name
            ``control_x`` (int) — stick x override
            ``control_y`` (int) — stick y override
            ``jump`` (bool) — jump request
        """
        if not self._active_reflex:
            return {"active": False, "reflex": ""}

        rt = self._active_reflex
        phase = self._reflex_phase
        cx, cy, jump = 0, 0, False

        if rt == self.STUCK_RAMP:
            if phase == "forward":
                cx = self._turn_direction
                cy = 70

        elif rt == self.OSCILLATING:
            if phase == "hold":
                cx = self._turn_direction
                cy = 70

        elif rt == self.WALL_STUCK:
            if phase == "reverse":
                cx = 0
                cy = -20
            elif phase == "turn":
                cx = self._turn_direction
                cy = 50

        elif rt == self.MICRO_LOOP:
            if phase == "turn":
                # EVO R28: mix CX steering bias into turn direction so the
                # left/right alternation is tilted, breaking perfect heading
                # cancellation while keeping the reflex in control.
                cx = self._turn_direction + int(getattr(self, "_last_cx_bias", 0.0) * 30)
                cy = 0
            elif phase == "burst":
                cx = -self._turn_direction // 3
                cy = 70

        # Clip to SM64 control range
        cx = max(-80, min(80, cx))
        cy = max(-80, min(80, cy))

        return {
            "active": True,
            "reflex": rt,
            "phase": phase,
            "control_x": cx,
            "control_y": cy,
            "jump": jump,
        }

    @property
    def active_reflex(self) -> str:
        return self._active_reflex

    @property
    def active(self) -> bool:
        return bool(self._active_reflex)

    @property
    def triggered_micro_loop(self) -> bool:
        """True for one tick when micro_loop reflex fires (consumed by main.py)."""
        return self._triggered_micro_loop

    @property
    def cooldowns(self) -> dict[str, float]:
        """Seconds remaining before each reflex can fire again."""
        return dict(self._cooldowns)

    def reset(self) -> None:
        self._active_reflex = ""
        self._reflex_phase = ""
        self._phase_timer = 0.0
        self._turn_direction = 0
        for rt in self.REFLEX_TYPES:
            self._cooldowns[rt] = 0.0
        self._triggered_micro_loop = False
        self._aggressive_cooldown_factor = 1.0

    def set_aggressive_mode(self, active: bool) -> None:
        """Halve cooldowns when aggressive mode is active (health < 0.3).

        When *active* is True, new reflex activations get half the normal
        cooldown duration, allowing more frequent reflex firings.
        """
        self._aggressive_cooldown_factor = 0.5 if active else 1.0


# ---------------------------------------------------------------------------
# MemoryController — combined navigation memory
# ---------------------------------------------------------------------------

class MemoryController:
    """Aggregate stuck detection, spatial memory, cliff detection, novelty, and
    motion anomaly detection into an ``escape_behavior`` flag.

    t26 P1: MIN_ESCAPE_DURATION — an escape runs at least this long before
    the release logic may fire (blocks 0.02s flash-releases).

    The controller combines:
    - StuckDetector (temporal, frame, rate, Y-axis signals)
    - SpatialMemoryMap (novelty, loop_score, exploration_mode)
    - FailureMemory (fallen locations for avoidance)
    - CliffDetector (multi-frame cliff confirmation with hysteresis)
    - MotionAnomalyDetector (4 anomaly types: ramp_stuck, oscillating,
      wall_facing, small_loop)
    """

    MIN_ESCAPE_DURATION = 1.5   # t26 P1: seconds before release may fire

    def __init__(self,
                 stuck: StuckDetector | None = None,
                 spatial: SpatialMemoryMap | None = None,
                 failures: FailureMemory | None = None,
                 cliff: CliffDetector | None = None,
                 anomaly: MotionStateDetector | None = None,
                 reflex: ReflexController | None = None):
        self.stuck = stuck or StuckDetector()
        self.spatial = spatial or SpatialMemoryMap()
        self.failures = failures or FailureMemory()
        self.cliff = cliff or CliffDetector()
        self.anomaly = anomaly or MotionStateDetector()
        self.reflex = reflex or ReflexController()
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
        # Forced bold explore breakout — nested loop escape
        self._scene_low_duration: float = 0.0  # seconds with scene_change_rate < 0.05
        self._forced_bold_explore: bool = False
        # EVO R28 · real-time escape release timer: when escape has been active
        # for >30s (wall clock), release unconditionally.  stuck_duration
        # accumulates too slowly when the stuck detector gates intermittently.
        self._escape_activated_at: float = float("inf")
        self._escape_released_at: float = 0.0  # EVO R28: CX steering window
        # EVO R15: cliff-edge standoff sensing — seconds spent confirmed at a
        # cliff edge while escape is active (the "parked at the edge" state).
        self._cliff_standoff_s: float = 0.0
        self._bold_explore_dt: float = 0.020  # tick interval, same as model.dt

        # Landmark memory state
        self._scene_sig = np.zeros(128, dtype=np.float32)
        self._scene_id: str = ""
        self._scene_tick: int = 0

        # Cached anomaly state
        self._latest_anomaly_conf: float = 0.0
        self._latest_anomaly_dur: float = 0.0

        # Health-scoring state
        self._stored_scene_change_rate: float = 0.0
        # EVO L2: exploration-stall tracking for health scoring — rolling
        # window of "coverage_rate ≈ 0" flags (600 ticks ≈ 12 s at 50 Hz).
        self._stall_flags: deque = deque(maxlen=600)
        # Wall persistence — tracks consecutive ticks spent pressing a wall
        # independent of escape_behavior.  Used for early wall avoidance
        # before the anomaly detector's wall_stuck gate (which requires
        # escape_behavior=True) fires.
        self._wall_persist: float = 0.0
        self._wall_persist_heading: float = 0.0  # heading at wall contact start

    def update(self, temporal_energy: float, frame_seq: int,
               forward_rate: float, x: float, z: float,
               pos_y: float = 0.0, heading: float = 0.0,
               flow_asymmetry: float = 0.0,
               flow_looming: float = 0.0,
               flow_cliff: float = 1.0,
               scene_change_rate: float = 0.0,
               ground_angle: float = 0.7,
               scene_sig: np.ndarray | None = None,
               wall_score: float = 0.0,
               ramp_score: float = 0.0,
               heading_rate: float = 0.0,
               control_x: int = 0) -> tuple:
        """Feed one tick; returns ``(stuck_score, stuck_duration, novelty,
        escape_behavior, fallen, forced_bold_explore)``."""
        self._stuck_score, self._stuck_duration, self._fallen = self.stuck.update(
            temporal_energy, frame_seq, forward_rate, pos_y
        )
        self._stuck_score, self._stuck_duration, self._fallen = self.stuck.update(
            temporal_energy, frame_seq, forward_rate, pos_y
        )
        # EVO L2 fix: the 3D grid signature is update(x, y, z) — the old
        # two-arg call landed the real z in the y-slot and recorded every
        # visit at z-cell 0, which desynchronised the memory grid from the
        # true trajectory by thousands of units.
        self._novelty = self.spatial.update(x, pos_y, z)

        # Update cliff detector with multi-frame confirmation
        self._cliff_state = self.cliff.update(flow_cliff)

        # EVO R15: cliff-edge standoff timer — detector-confirmed cliff while
        # escape is active ("cliff_detected" IS the post-window confirm flag).
        self.update_standoff(self._bold_explore_dt,
                             confirmed=bool(self._cliff_state.get("cliff_detected")),
                             escaping=self.escape_behavior)

        # Store scene_change_rate for health scoring
        self._stored_scene_change_rate = scene_change_rate
        # EVO L2: exploration-stall flag for the health formula
        stalled = self.spatial.coverage_stalled
        if stalled is not None:
            self._stall_flags.append(stalled)

        # Update motion anomaly detector
        anomaly_result = self.anomaly.update(
            ramp_score=ramp_score,
            stuck_duration=self._stuck_duration,
            heading_rate=heading_rate,
            wall_score=wall_score,
            escape_behavior=self.escape_behavior,
            visited_cells=self.spatial.visited_cells,
            loop_score=self.spatial.loop_score,
            pos_y=pos_y,
            control_x=control_x,
        )
        self._latest_anomaly_conf = anomaly_result["confidence"]
        self._latest_anomaly_dur = anomaly_result["duration_in_state"]
        self._latest_anomaly_state = anomaly_result["state"]

        # Wall persistence — track consecutive ticks pressing a wall
        # independent of escape_behavior.  Allows early hard-turn avoidance
        # before the anomaly detector's wall_stuck gate (requires escape=True)
        # fires 10+ seconds later.
        _dt = getattr(self, "_bold_explore_dt", 0.02)
        if wall_score > 0.3:
            self._wall_persist += _dt
            if abs(self._wall_persist - _dt) < 0.001:  # first tick
                self._wall_persist_heading = heading
        else:
            self._wall_persist = 0.0
            self._wall_persist_heading = 0.0

        # ---- Scene signature matching (landmark memory) ----
        if scene_sig is not None and scene_sig.size == 128:
            self._scene_sig = scene_sig.copy()
            # Match against known scenes and add current to database
            self.spatial.scene_db.match(scene_sig)
            self.spatial.scene_db.add(scene_sig, self._scene_tick)
            self._scene_tick += 1
            # EMA-smoothed signature stabilises the scene identifier hash
            # against frame-to-frame luminance/heading drift (α=0.1)
            ema = getattr(self, "_scene_sig_ema", None)
            self._scene_sig_ema = (scene_sig.copy() if ema is None
                                   else 0.9 * ema + 0.1 * scene_sig)
            stable = self._scene_sig_ema / (np.linalg.norm(self._scene_sig_ema) + 1e-8)
            # Compute a short scene identifier from stabilised signature bytes
            _hash = hashlib.md5(stable.tobytes()).hexdigest()[:12]
            self._scene_id = _hash

        # Record position for fall detection
        self._last_pos = (x, pos_y, z)

        # If fallen, record the last safe position as failure + dead-end direction
        if self._fallen and self._fall_pos == (0.0, 0.0, 0.0):
            self._fall_pos = self._last_pos
            self.failures.record_failure(x, z)
            self.failures.record_dead_end(x, z, heading)

        # ---- Forced bold explore detection ----
        # (a) Original: scene_change_rate < 0.05 AND global visited_cells < 20
        #     (confined to a tiny area) for >10 seconds.
        # (b) EVO R10 local-breakout: a micro_loop anomaly persisting > 60 s is
        #     a local deadlock regardless of global exploration history — the
        #     original gate could never fire on an experienced map (global
        #     visited_cells already in the hundreds), leaving the fly circling
        #     forever in a dead-end.
        # Coach-tunable (EVO R11 follow-up): GLM strategy advice hot-reloads
        # bold_explore_stuck_s via main.py — how long a persistent anomaly
        # must last before breakout (default 60 s).
        # t13 fix②: previously only micro_loop qualified; now ANY anomaly
        # persisting past the coach threshold also breaks out (a 100 s
        # wall_stuck is just as deadlocked as a 100 s micro_loop).
        # micro_loop keeps its original semantics via the first clause.
        _bx_stuck_s = getattr(self, "bold_explore_stuck_s", 60.0)
        micro_loop_stuck = (self._latest_anomaly_state == "micro_loop"
                            and self._latest_anomaly_dur > _bx_stuck_s)
        persistent_anomaly_stuck = (self.anomaly.active
                                    and self._latest_anomaly_state != "micro_loop"
                                    and self._latest_anomaly_dur > _bx_stuck_s)
        if ((scene_change_rate < 0.05 and self.spatial.visited_cells < 20)
                or micro_loop_stuck or persistent_anomaly_stuck):
            self._scene_low_duration += self._bold_explore_dt
        else:
            self._scene_low_duration = 0.0
        self._forced_bold_explore = self._scene_low_duration >= 10.0

        # Flow-aware escape threshold: looming lowers threshold,
        # cliff (multi-frame confirmed) forces immediate escape
        # ground_angle > 0.3 = slope or flat → suppress cliff emergency
        flow_danger = max(0.0, flow_looming - 0.3) * 2.0  # 0..1+ from looming
        is_actual_cliff = (ground_angle < 0.3)  # only true cliffs (<0.3), not slopes
        cliff_emergency = (self._cliff_state["cliff_detected"]
                           and temporal_energy > 0.005
                           and is_actual_cliff)
        adjusted_threshold = 0.8 - flow_danger * 0.4
        # Motion anomaly lowers the threshold: when any anomaly is active,
        # escape triggers at a lower stuck threshold (0.5 instead of 0.8)
        # to enable faster reflex-like response.
        anomaly_override = self.anomaly.active
        if anomaly_override:
            adjusted_threshold = min(adjusted_threshold, 0.5)
        # Coach-tunable (EVO R11 follow-up): escape.stuck_threshold_s from
        # GLM strategy advice — escape once stuck persists this many seconds
        # (e.g. 2.0 s per the locked-door lesson), regardless of score.
        _coach_stuck_s = getattr(self, "escape_stuck_threshold_s", None)
        _coach_stuck = (_coach_stuck_s is not None
                        and self._stuck_duration >= _coach_stuck_s)

        # EVO R24: release escape when it has been active without effect
        # for too long — escape just forces straight-ahead (x=0),
        # suppressing CX steering.  Release thresholds:
        #   - 60s pass (general timeout, covers fallen)
        #   - 30s + anomaly resolved + score decayed (faster release when
        #     the anomaly cleared but escape stayed on due to stale score)
        # EVO R28 · escape_in_seconds tracks real wall-clock time the escape
        # has been continuously active (not stuck_duration, which accumulates
        # erratically when the stuck detector gates intermittently).
        _now = time.monotonic()
        # t26 P1: (re)arm the activation clock on every fresh escape start —
        # the old "set once, never resets" logic kept the FIRST escape's
        # timestamp forever, so any later re-trigger inherited a huge
        # _escape_s and was flash-released within one tick.
        if self.escape_behavior and not getattr(self, "_prev_escape_behavior", False):
            self._escape_activated_at = _now
        self._prev_escape_behavior = self.escape_behavior
        if self.escape_behavior and self._escape_activated_at == float("inf"):
            self._escape_activated_at = _now  # belt & braces for legacy state

        _escape_s = _now - self._escape_activated_at if self.escape_behavior else 0.0

        # t26 P1: minimum escape duration — releases observed at a mean of
        # 0.02s (the escape flag flipped and the release logic fired on the
        # very next tick), starving the LIF pools of any steering window.
        # No release before MIN_ESCAPE_DURATION has elapsed; fallen escapes
        # keep running through this window too (recovery needs time).
        _min_dur_ok = _escape_s >= self.MIN_ESCAPE_DURATION

        _release_escape = (self.escape_behavior
                           and not cliff_emergency
                           and _min_dur_ok
                           and (_escape_s > 60
                                or (_escape_s > 30
                                    and self._latest_anomaly_state in ("idle", "micro_loop"))))

        # EVO R28 · when escape releases, give CX a steering window before
        # anomaly_override can re-activate it.
        # t23 fix①: cooldown 1800s → 60s, and a NEW anomaly activation
        # immediately clears the cooldown — a fresh anomaly is fresh
        # evidence, the old release must not mute it.  The activation clock
        # also restarts so the fresh escape isn't instantly re-released by
        # the stale _escape_s.
        if _release_escape:
            self._escape_released_at = _now
        if anomaly_override and not getattr(self, "_prev_anomaly_override", False):
            self._escape_released_at = 0.0
            self._escape_activated_at = _now
        self._prev_anomaly_override = anomaly_override
        _released_recently = _now - self._escape_released_at < 60.0

        # t23 fix②: _fallen moved OUTSIDE the release/cooldown gate — being
        # on the ground is unconditional evidence; the post-release cooldown
        # must never stop fall recovery (Ghost House lock, 30 min).
        self.escape_behavior = (
            self._fallen
            or ((not _release_escape and not _released_recently) and (
                (self._stuck_score >= adjusted_threshold
                 and self.spatial.exploration_mode)
                or cliff_emergency
                or self._forced_bold_explore
                or anomaly_override
                or _coach_stuck)))
        return (self._stuck_score, self._stuck_duration,
                self._novelty, self.escape_behavior, self._fallen,
                self._forced_bold_explore)

    def reset(self) -> None:
        self.stuck.reset()
        self.spatial.reset()
        self.failures.reset()
        self.cliff.reset()
        self.anomaly.reset()
        self.reflex.reset()
        self.escape_behavior = False
        self._stuck_score = 0.0
        self._stuck_duration = 0.0
        self._novelty = 1.0
        self._fallen = False
        self._fall_pos = (0.0, 0.0, 0.0)
        self._cliff_state = {"cliff_detected": False,
                             "cliff_confidence": 0.0,
                             "raw_lower_field_green": 1.0}
        self._scene_low_duration = 0.0
        self._forced_bold_explore = False
        self._scene_sig[:] = 0.0
        self._scene_id = ""
        self._scene_tick = 0
        self.spatial.scene_db.reset()

    @property
    def stuck_score(self) -> float: return self._stuck_score

    @property
    def stuck_duration(self) -> float: return self._stuck_duration

    @property
    def health_score(self) -> float:
        """Health score in [0, 1] — navigation-quality self assessment.

        ``health = 1.0
                   - revisit_penalty * 0.35             # scene familiarity
                   - min(stuck_duration/300, 0.3)       # stuck duration (capped)
                   - stall_ratio * 0.25                 # exploration stall (L2)
                   + scene_change_rate * 0.2            # scene change boost
                   + novelty * 0.1                      # immediate novelty (L2)``

        v2 (EVO L2): the old formula saturated at a sticky 0.5 floor and could
        not reflect recovery without a scene change.  The stall term now
        penalises circling-without-progress (coverage_rate ≈ 0), and the
        novelty term rewards escaping a loop even inside the same scene —
        giving health a recovery gradient.
        """
        revisit_cost = self.revisit_penalty * 0.35
        stuck_cost = min(self._stuck_duration / 300.0, 0.3)
        stall_cost = self.stall_ratio * 0.25
        scene_boost = self._stored_scene_change_rate * 0.2
        novelty_boost = self._novelty * 0.1
        return round(max(0.0, min(1.0,
            1.0 - revisit_cost - stuck_cost - stall_cost + scene_boost + novelty_boost
        )), 4)

    @property
    def novelty(self) -> float: return self._novelty

    @property
    def fallen(self) -> bool: return self._fallen

    @property
    def wall_persist(self) -> float:
        """Seconds of continuous wall contact independent of escape state."""
        return self._wall_persist

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
    def stall_ratio(self) -> float:
        """Fraction of recent ticks with coverage_rate ≈ 0 (0–1).

        0 = exploring new ground; 1 = coverage fully stalled (circling).
        Returns 0 during the warm-up window so startup doesn't read as stall.
        """
        if len(self._stall_flags) < 200:
            return 0.0
        return sum(self._stall_flags) / len(self._stall_flags)

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

    @property
    def forced_bold_explore(self) -> bool:
        """True when scene_change_rate < 0.05 for >10 s AND visited_cells < 20.

        Indicates the agent is in a nested loop cycle — visually stagnant in
        a tiny area — requiring a forceful breakout maneuver.
        """
        return self._forced_bold_explore

    @property
    def scene_low_duration(self) -> float:
        """Seconds that scene_change_rate has been continuously below 0.05."""
        return self._scene_low_duration

    # ---- Landmark memory properties ----

    @property
    def scene_db(self) -> SceneDatabase:
        """Scene signature database (delegated to spatial.scene_db)."""
        return self.spatial.scene_db

    @property
    def scene_id(self) -> str:
        """Short hex identifier of the current scene signature."""
        return self._scene_id

    @property
    def revisit_count(self) -> int:
        """Number of stored scene signatures matching the current scene."""
        return self.spatial.scene_db.revisit_count

    @property
    def revisit_penalty(self) -> float:
        """Scene-revisit penalty modulating novelty (0 = no penalty, up to 0.5)."""
        return self.spatial.revisit_penalty

    @property
    def scene_match(self) -> float:
        """Highest cosine similarity match score for the current scene (0-1)."""
        return self.spatial.scene_db.best_score

    # ---- Motion anomaly detector properties ----

    @property
    def anomaly_active(self) -> bool:
        """True when an anomaly state is active (not idle)."""
        return self.anomaly.active

    @property
    def anomaly_state_name(self) -> str:
        """Current anomaly state name (idle/stuck_ramp/oscillating/wall_stuck/micro_loop/fallen)."""
        return self.anomaly.active_state

    @property
    def anomaly_confidence(self) -> float:
        """Majority-vote confidence [0, 1] for the current state."""
        return self._latest_anomaly_conf if hasattr(self, '_latest_anomaly_conf') else 0.0

    @property
    def anomaly_duration(self) -> float:
        """Seconds the current anomaly state has been continuously active."""
        return self._latest_anomaly_dur if hasattr(self, '_latest_anomaly_dur') else 0.0

    @property
    def anomaly_state_history(self) -> list[dict]:
        """Last 100 anomaly state transitions."""
        return self.anomaly.state_history

    @property
    def anomaly_state(self) -> dict:
        """Full anomaly state dict for dashboard serialization."""
        return self.anomaly.get_state()

    # ---- Reflex controller properties ----

    @property
    def reflex_active(self) -> bool:
        """True when a reflex escape circuit is currently active."""
        return self.reflex.active

    @property
    def reflex_type(self) -> str:
        """Currently active reflex type name."""
        return self.reflex.active_reflex

    @property
    def reflex_action(self) -> dict:
        """Current reflex control override action dict."""
        action = self.reflex.get_action()
        # EVO R29 · desperate pit escape: when fallen for >60s with no
        # forward movement, force the reflex to include JUMP so the escape
        # cascade produces forward+JUMP instead of just forward.
        if (action.get("active")
                and self._fallen
                and self._stuck_duration > 60):
            action["jump"] = True
        return action

    @property
    def reflex_triggered_micro_loop(self) -> bool:
        """True for one tick when micro_loop reflex fires."""
        return self.reflex.triggered_micro_loop

    def update_standoff(self, dt: float, confirmed: bool, escaping: bool) -> None:
        """EVO R15: accumulate the cliff-edge standoff timer.

        Confirmed cliff + active escape = parked at the edge.  Any frame
        without that combination resets the timer (the state is a plateau
        detector, not a lifetime counter).
        """
        if confirmed and escaping:
            self._cliff_standoff_s += dt
        else:
            self._cliff_standoff_s = 0.0

    @property
    def cliff_standoff_s(self) -> float:
        """Seconds spent confirmed at a cliff edge while escape is active."""
        return self._cliff_standoff_s

    def cliff_tangent_bias(self, x: float, z: float, heading: float) -> float:
        """Tangential detour bias near known cliff/failure cells.

        EVO R15 (brain-first): this is a SENSORY gate only — it tells the
        model that a known cliff lies ahead and on which side the fresher
        ground lies.  The turn current injection and the actual heading
        decision stay with the LIF network.

        Returns
        -------
        +1.0 / -1.0 : inject turn current of this sign (edge detour)
        0.0         : not near a known failure cell, or not head-on
        """
        to_f = self.failures.nearest_failure_vector(x, z, radius_cells=2.5)
        if to_f is None:
            return 0.0
        fx, fz = to_f
        hx, hz = math.sin(heading), math.cos(heading)
        head_on = hx * fx + hz * fz
        if head_on < 0.25:
            return 0.0                       # failure is behind/beside — fine
        # tangential candidates (±90° rotation of the failure bearing)
        t1x, t1z = -fz, fx
        t2x, t2z = fz, -fx
        cs = self.spatial.cell_size

        def visits(px: float, pz: float) -> int:
            k = self.spatial._key(x + px * cs, z + pz * cs)
            return int(self.spatial._cells.get(k, 0))

        v1, v2 = visits(t1x, t1z), visits(t2x, t2z)
        if v1 < v2:
            return 1.0                       # fresher ground on tangent 1
        if v2 < v1:
            return -1.0                      # fresher ground on tangent 2
        return 1.0                           # tie → deterministic detour

    def navigation_vectors(self, x: float, z: float, heading: float,
                           novelty_direction: float) -> list[tuple[float, float, float]]:
        """EVO R20 (CX-3): goal vector sources in WORLD coordinates.

        Returns a list of ``(dx, dz, weight)`` — the CX performs the
        vector-sum competition (FB-style) and picks the dominant goal.
        Sources: away-from-failure (danger), coverage-gap centroid
        (exploration).  Novelty direction is added by the caller.
        """
        vecs: list[tuple[float, float, float]] = []
        to_f = self.failures.nearest_failure_vector(x, z, radius_cells=3)
        if to_f is not None:
            vecs.append((-to_f[0], -to_f[1], 1.2))   # away from known failure
        gap = self.spatial.coverage_gap_vector(x, z)
        if gap is not None:
            vecs.append((gap[0], gap[1], 0.7))       # toward unvisited space
        return vecs

    @property
    def reflex_cooldowns(self) -> dict[str, float]:
        """Seconds remaining before each reflex can fire again."""
        return self.reflex.cooldowns

    def reset_scene_db(self) -> None:
        """Clear the scene signature database."""
        self.spatial.reset_scene_db()
        self._scene_sig[:] = 0.0
        self._scene_id = ""
        self._scene_tick = 0

    # ── Scene signature persistence ───────────────────────────────────

    SCENE_DB_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "scene_db.pkl"
    SPATIAL_MAP_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "spatial_map.pkl"

    def save_scene_db(self, path: str | Path | None = None) -> None:
        """Persist scene signatures + the spatial visit map/traversal graph."""
        p = Path(path) if path else self.SCENE_DB_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.spatial._scene_db.save(p)
        except Exception:
            pass
        try:
            self.spatial.save_state(self.SPATIAL_MAP_PATH)
        except Exception:
            pass

    def load_scene_db(self, path: str | Path | None = None) -> int:
        """Load previously saved scene signatures + spatial map. Returns count loaded."""
        p = Path(path) if path else self.SCENE_DB_PATH
        n = 0
        try:
            db = SceneDatabase.load(p)
            self.spatial._scene_db = db
            n = db.size
        except Exception:
            return 0
        self.spatial.load_state(self.SPATIAL_MAP_PATH)
        return n