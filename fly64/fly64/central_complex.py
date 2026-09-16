"""Central Complex (CX) — heading compass, goal steering, and navigation.

Models the insect Central Complex as a ring-attractor heading compass
with goal-direction memory and steering-signal output.  Implements
functional equivalents of:

  - Ellipsoid Body (EB) — ring attractor for heading direction
  - Fan-shaped Body (FB) — goal-direction storage and steering comparison
  - Protocerebral Bridge (PB) — bilateral heading representation

The CX receives heading, optic-flow asymmetry, and novelty signals,
and produces a steering bias injected into the turn motor pools.
"""

from __future__ import annotations

from collections import deque

import numpy as np


# Default architecture
N_COLUMNS = 16                  # heading columns (22.5° each)
COMPASS_PERSISTENCE = 0.85      # ring-attractor persistence per frame
LOCAL_EXCITATION = 1.2          # local neighbour excitation strength
GLOBAL_INHIBITION = 0.25        # subtractive global inhibition
HEADING_DRIVE_WEIGHT = 0.18     # how fast heading pulls the bump
EPS = 1e-8                      # numerical stability

STEERING_GAIN = 0.12            # compass→goal comparison → turn bias
OPTIC_FLOW_GAIN = 0.08          # flow_asymmetry → turn bias
GOAL_UPDATE_RATE = 0.2          # how fast goal tracks novelty direction
MAX_STEERING = 0.15             # maximum turn-bias magnitude
GOAL_MEMORY_DECAY = 0.999       # per-frame decay of goal strength


class CentralComplex:
    """Central Complex navigation module.

    Architecture
    ------------
    16-column ring attractor (heading compass)
      -> goal-direction comparison
      -> steering bias (turn_left/turn_right)

    Attributes
    ----------
    compass : np.ndarray, (N_COLUMNS,), float
        Ring-attractor activity for each heading column.
    heading_column : int
        Index of the most active compass column (0-15).
    goal_column : int
        Stored goal-direction column index.
    goal_strength : float
        Strength of the current goal (decays without reinforcement).
    steering_bias : float
        Current steering output in [-1, 1]; positive = turn right.
    """

    MBON_NAMES = []  # no MBONs — CX outputs directly to motor pools

    def __init__(self, n_columns: int = N_COLUMNS,
                 steering_gain: float = STEERING_GAIN,
                 optic_flow_gain: float = OPTIC_FLOW_GAIN):
        self.n_columns = n_columns
        self.steering_gain = steering_gain
        self.optic_flow_gain = optic_flow_gain

        # Ring attractor (heading compass) — one bump of activity
        self.compass = np.ones(n_columns, dtype=np.float32) / n_columns
        # Imprint initial heading = column 0 with a Gaussian bump
        self._imprint_heading(0.0)

        # Goal direction
        self.goal_column = 0
        self.goal_strength = 0.0
        self._goal_float = 0.0  # continuous float tracking for smooth updates

        # Steering output
        self.steering_bias = 0.0

        # History for diagnostics
        self._compass_history = deque(maxlen=60)

        # EVO R20 · CX-1 罗盘自主化: the bump integrates self-motion
        # (turn-pool angular velocity) autonomously; external heading and
        # visual azimuth act as WEAK corrections, not the primary drive.
        self._col_accum = 0.0   # fractional column drift awaiting rollover

        # EVO R20 · CX-2 锚点路径积分: displacement vector integrated in the
        # anchor frame using the CX's own compass heading — gives the brain
        # an egocentric "where am I relative to where I entered" signal.
        self.anchor = None            # (x, z) world anchor
        self.disp_x = 0.0             # integrated displacement from anchor
        self.disp_z = 0.0
        self.SPEED_TO_UNITS = 1.6     # forward_rate(Hz) → game-units/s calib

        # EVO R23 · idle exploration wander: when no goal vectors are
        # available and goal strength decays, a slow sinusoidal drift
        # biases the heading — natural search pattern when no target
        # is present (avoids CX steering collapsing to zero).
        self._idle_wander_phase = 0.0
        self._idle_wander_rate = 0.006     # ~530 frames (10s) per full cycle

        # P3-2: Visual relocalization — corrects path integration drift
        # by matching scene signatures against remembered positions.
        self._scene_positions: dict[int, tuple[float, float, float]] = {}
        self._relocalize_gate = 0.8
        self._relocalize_strength = 0.3
        self._last_scene_id: int | None = None

    def _roll_fractional(self, columns: float) -> None:
        """Rotate the compass bump by a fractional number of columns.

        Positive = clockwise (turning right).  Implemented as integer roll
        plus linear blend into the adjacent column for the fractional part.
        """
        i = int(np.floor(columns))
        frac = columns - i
        if i == 0 and abs(frac) < 1e-9:
            return
        a = np.roll(self.compass, i)
        b = np.roll(self.compass, i + (1 if columns >= 0 else -1))
        self.compass = ((1.0 - abs(frac)) * a + abs(frac) * b).astype(np.float32)
        self.compass /= (self.compass.sum() + EPS)

    def _self_motion_update(self, heading_rate: float, dt: float) -> None:
        """CX-1: move the bump by integrated angular velocity (rad/s).

        Positive heading_rate (turning right) rotates the bump clockwise.
        The fractional remainder accumulates so slow turns are not lost.
        """
        cols = heading_rate * dt / (2.0 * np.pi) * self.n_columns
        self._col_accum += cols
        whole = int(np.floor(self._col_accum))
        if whole != 0:
            self._roll_fractional(whole)
            self._col_accum -= whole

    def set_anchor(self, x: float, z: float) -> None:
        """EVO R20 (CX-2): re-anchor path integration at the current pose."""
        self.anchor = (x, z)
        self.disp_x = 0.0
        self.disp_z = 0.0

    @property
    def anchor_distance(self) -> float:
        """Integrated distance from the scene anchor (game units)."""
        return float(np.hypot(self.disp_x, self.disp_z))

    @property
    def anchor_return_bearing(self) -> float | None:
        """World-frame bearing FROM current position BACK TO the anchor."""
        if self.anchor is None or (self.disp_x == 0 and self.disp_z == 0):
            return None
        return float(np.arctan2(-self.disp_x, -self.disp_z))

    # ── P3-2: Visual relocalization ──
    def visual_relocalize(self, scene_id: int | None,
                          confidence: float,
                          scene_count: int) -> None:
        """Correct path integration drift by matching scene signatures.

        When the same scene is re-encountered with high confidence,
        pull disp_x/disp_z toward the remembered position for that scene,
        providing a weak visual closure on the open-loop path integration.
        """
        if scene_id is None or confidence < self._relocalize_gate:
            return
        if scene_id in self._scene_positions:
            mem_x, mem_z, mem_conf = self._scene_positions[scene_id]
            # Weight correction by confidence and recency
            w = self._relocalize_strength * confidence * (1.0 - mem_conf * 0.5)
            self.disp_x += (mem_x - self.disp_x) * w
            self.disp_z += (mem_z - self.disp_z) * w
            # Decay memory confidence slightly (re-exposure refreshes)
            self._scene_positions[scene_id] = (mem_x, mem_z, min(1.0, mem_conf + 0.05))
        elif self.anchor is not None:
            # First encounter: store current displacement for this scene
            self._scene_positions[scene_id] = (self.disp_x, self.disp_z, confidence)

    def _weak_correction(self, azimuth_rad: float, weight: float) -> None:
        """Weakly pull the bump toward an azimuth (visual/sky compass)."""
        drive = self._heading_drive(azimuth_rad) * weight
        self.compass = ((self.compass + drive) /
                        (self.compass.sum() + drive.sum() + EPS)).astype(np.float32)

    def _imprint_heading(self, column_idx: float) -> None:
        """Set compass to a Gaussian bump centred at *column_idx*."""
        cols = np.arange(self.n_columns, dtype=np.float32)
        dist = np.minimum(
            np.abs(cols - column_idx),
            self.n_columns - np.abs(cols - column_idx),
        )
        bump = np.exp(-dist * dist * 1.5).astype(np.float32)
        self.compass = bump / (bump.sum() + EPS)

    @property
    def heading_column(self) -> int:
        """Index of the most active compass column (0-15)."""
        return int(np.argmax(self.compass))

    def _heading_drive(self, heading: float) -> np.ndarray:
        """Create a normalised Gaussian heading-drive vector.

        Maps *heading* (radians, 0 = +Z) onto the 16-column ring with
        a Gaussian bump (sigma ~1 column) at the corresponding column.
        """
        h_norm = heading % (2 * np.pi)
        column_frac = h_norm / (2 * np.pi) * self.n_columns  # [0, n)
        cols = np.arange(self.n_columns, dtype=np.float32)
        dist = np.minimum(
            np.abs(cols - column_frac),
            self.n_columns - np.abs(cols - column_frac),
        )
        drive = np.exp(-dist * dist * 1.5).astype(np.float32)
        return drive / (drive.sum() + EPS)

    def update(self, heading: float | None, heading_rate: float,
               flow_asymmetry: float = 0.0,
               novelty: float = 0.5,
               novelty_direction: float = 0.0,
               dt: float = 0.02,
               visual_azimuth: float | None = None,
               forward_speed: float = 0.0,
               goal_vectors: list[tuple[float, float, float]] | None = None,
               scene_id: int | None = None,
               scene_confidence: float = 0.0,
               scene_total: int = 0) -> float:
        """One timestep of CX processing.

        EVO R20 (CX-1): the ring attractor integrates SELF-MOTION — the
        bump rolls by angular velocity (heading_rate × dt) autonomously.
        The external SM64 heading and the visual sky azimuth act as WEAK
        corrections pulling the bump back when they disagree, so the
        compass is an internal state corrected by vision, not a copy of
        the game's heading value.

        Parameters
        ----------
        heading : float
            External heading in radians (SM64 game state) — weak correction.
        heading_rate : float
            Angular velocity in rad/s (positive = turning right) — SELF-MOTION.
        dt : float
            Simulation tick interval.
        visual_azimuth : float | None
            Sky azimuth in radians (from hue_az bands) — drift correction.
        """
        # ---- 1. Ring-attractor heading compass ----
        # The compass maintains a stable activity bump through local
        # excitation (neighbouring columns) and global inhibition.
        # A heading drive pulls the bump toward the current heading.

        n = self.n_columns

        # ---- CX-1: self-motion integration (autonomous bump roll) ----
        # The bump moves by angular velocity FIRST, autonomously — this is
        # the path-integration term that makes the compass an internal
        # state rather than a copy of the external heading.
        self._self_motion_update(heading_rate, dt)

        # Local excitation: each column receives input from its neighbours
        # using a [1, 2, 1] kernel (centre-weighted).
        roll_left = np.roll(self.compass, 1)
        roll_right = np.roll(self.compass, -1)
        local = (roll_left + self.compass * 2.0 + roll_right) / 4.0

        # Global inhibition: mean activity suppresses all columns equally
        mean_activity = float(self.compass.mean())

        # External heading drive: WEAK correction (EVO R20 demoted from
        # primary drive — was the only bump mover before CX-1).
        # EVO R20 tuning: game heading 0.10 < sky compass 0.12 — the fly's
        # own visual compass outranks the game-provided value (brain-first).
        # heading=None (game value unavailable) → no game drive at all:
        # fully autonomous integration (sky compass still corrects).
        drive = (self._heading_drive(heading) * 0.10
                 if heading is not None else 0.0)

        # Visual azimuth correction: sky compass, slightly stronger
        if visual_azimuth is not None:
            drive = drive + self._heading_drive(visual_azimuth) * 0.12

        # Ring attractor update (divisive normalisation).
        # NOTE: drive weights above already include their gain — the legacy
        # HEADING_DRIVE_WEIGHT multiplier is intentionally dropped here.
        raw = (
            self.compass * COMPASS_PERSISTENCE
            + local * LOCAL_EXCITATION
            - mean_activity * GLOBAL_INHIBITION
            + drive
        )
        # Ensure non-negative; divisive normalisation.
        raw = np.maximum(raw, 0)
        total = raw.sum() + EPS
        self.compass = (raw / total).astype(np.float32)

        # Record history
        self._compass_history.append(self.compass.copy())

        # ---- 2b. CX-2: anchor-frame path integration ----
        # Displacement is integrated along the CX's OWN compass heading —
        # the brain's belief of travel, not the game's ground truth.
        if self.anchor is not None and forward_speed > 0.0:
            est_h = self.heading_estimate
            self.disp_x += float(np.sin(est_h) * forward_speed
                                 * self.SPEED_TO_UNITS * dt)
            self.disp_z += float(np.cos(est_h) * forward_speed
                                 * self.SPEED_TO_UNITS * dt)

        # P3-2: Visual relocalization — correct path integration drift
        # by pulling disp_x/disp_z toward remembered scene positions.
        self.visual_relocalize(scene_id, scene_confidence, scene_total)

        # ---- 2. Goal-direction update (EVO R20 CX-3) ----
        # Multi-source goal-VECTOR competition (FB vector arithmetic):
        # each source contributes a world-frame vector; the resultant
        # defines the goal column and strength.  A single exhausted source
        # no longer zeroes the compass's sense of direction.
        if goal_vectors:
            sx = sz = 0.0
            for dx, dz, w in goal_vectors:
                sx += w * dx
                sz += w * dz
            norm = np.hypot(sx, sz)
            if norm > 1e-6:
                goal_angle = float(np.arctan2(sx, sz))
                self._goal_float = goal_angle / (2 * np.pi) * n
                self.goal_column = (int(round(self._goal_float)) % n + n) % n
                self.goal_strength = min(1.0, norm / 1.5)
        elif abs(novelty_direction) > 0.1 or abs(novelty - 0.5) > 0.3:
            # Legacy fallback: novelty-only goal (when no goal vectors given).
            # novelty_direction > 0 → want to steer right
            # In SM64, +x = turn right, which is positive heading_rate.
            # novelty_direction > 0 → steer right → goal is right of current,
            # which is a positive column offset.
            h_ref = heading if heading is not None else self.heading_estimate
            column_idx = int((h_ref % (2 * np.pi)) / (2 * np.pi) * n) % n
            col_offset = novelty_direction * n * 0.25
            desired_goal_float = (
                self._goal_float * (1.0 - GOAL_UPDATE_RATE)
                + (column_idx + col_offset) * GOAL_UPDATE_RATE
            )
            self._goal_float = desired_goal_float
            self.goal_column = int(round(desired_goal_float)) % n
            self.goal_strength = min(1.0, self.goal_strength + GOAL_UPDATE_RATE)
        else:
            # Decay goal strength when no strong signal
            self.goal_strength *= GOAL_MEMORY_DECAY

        # ---- EVO R23 · idle exploration wander ----
        # When goal strength is negligible (no target available), a slow
        # sinusoidal drift biases the heading — natural "search mode"
        # that prevents CX steering from collapsing to zero in explored
        # areas.  The drift gradually sweeps the heading across the
        # environment, breaking position loops over time.
        if self.goal_strength < 0.05:
            self._idle_wander_phase += self._idle_wander_rate
            wander = np.sin(self._idle_wander_phase) * 2.0
            self._goal_float = (self._goal_float + wander * 0.05 + 0.002) % n
            self.goal_column = int(round(self._goal_float)) % n
            self.goal_strength = 0.30

        # ---- 3. Steering signal ----
        # Compare current heading column against goal column.
        # Positive offset = goal is to the right → steer right (positive bias).
        offset = (self.goal_column - self.heading_column) % n
        if offset > n / 2:
            offset -= n  # wrap to [-n/2, n/2]
        heading_steer = offset / (n / 2)  # [-1, 1], positive = steer right

        # Optic flow modulation: strong asymmetry biases steering
        # away from the side with more motion (collision avoidance).
        flow_bias = flow_asymmetry * self.optic_flow_gain

        # Combine: heading-to-goal steering * strength + flow bias
        raw_steering = (
            heading_steer * self.steering_gain * self.goal_strength
            + flow_bias
        )

        # Clamp
        self.steering_bias = float(np.clip(
            raw_steering, -MAX_STEERING, MAX_STEERING
        ))

        return self.steering_bias

    def reset(self) -> None:
        """Reset compass to initial state (column 0, no goal)."""
        self.compass.fill(1.0 / self.n_columns)
        self._imprint_heading(0.0)
        self.goal_column = 0
        self.goal_strength = 0.0
        self._goal_float = 0.0
        self.steering_bias = 0.0
        self._compass_history.clear()

    # -- Diagnostics ---------------------------------------------------

    @property
    def heading_estimate(self) -> float:
        """Estimated heading in radians from compass activity.

        Returns a weighted-average heading based on the ring-attractor
        activity, providing a smooth heading estimate useful even when
        the direct game heading is unavailable.
        """
        angles = np.linspace(0, 2 * np.pi, self.n_columns, endpoint=False)
        sin_sum = float(np.sum(self.compass * np.sin(angles)))
        cos_sum = float(np.sum(self.compass * np.cos(angles)))
        return float(np.arctan2(sin_sum, cos_sum)) % (2 * np.pi)

    @property
    def compass_stats(self) -> dict:
        """Compass diagnostic statistics."""
        return {
            "heading_column": self.heading_column,
            "goal_column": self.goal_column,
            "goal_strength": round(self.goal_strength, 4),
            "steering_bias": round(self.steering_bias, 4),
            "compass_entropy": float(
                -np.sum(self.compass * np.log(self.compass + EPS))
            ),
            "compass_peak": float(self.compass.max()),
        }