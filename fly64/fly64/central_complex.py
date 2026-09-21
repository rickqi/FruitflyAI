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
#: EVO-057 · P1-1: continuous stuck time (seconds) after which, with no active
#: goal, the CX goal column is jumped to break a persistent circular orbit.
#: Aligned with the 30-60 s rungs already used by the escape/recall machinery;
#: the previous block used 300 with a self-contradictory "300 ticks ~6s" note
#: and could never fire anyway (see update()).
CX_LOOP_BREAK_STUCK_S = 45.0
#: Minimum ticks between two loop breaks (~30 s at 50 Hz).  Without it the
#: guard, which no longer depends on the synthetically raised goal_strength,
#: would re-aim the heading on every single tick while stuck.
CX_LOOP_BREAK_COOLDOWN_TICKS = 1500


class AnchorPathIntegrator:
    """CX-2: Anchor-based path integration with displacement tracking.

    Maintains a world-frame anchor point and integrates displacement using
    the CX's own heading estimate and forward speed.  Supports visual
    relocalization to correct drift when familiar scenes are re-encountered.

    The displacement vector represents the brain's belief of how far the
    agent has travelled since the anchor was set — an egocentric "where
    am I relative to where I started" signal consumed by spatial memory
    and goal selection.
    """

    def __init__(self, speed_to_units: float = 1.6,
                 displacement_decay: float = 0.9995,
                 relocalize_gate: float = 0.8,
                 relocalize_strength: float = 0.3):
        self.SPEED_TO_UNITS = speed_to_units
        self.DISPLACEMENT_DECAY = displacement_decay
        self._relocalize_gate = relocalize_gate
        self._relocalize_strength = relocalize_strength

        self.anchor: tuple[float, float] | None = None
        self.disp_x: float = 0.0
        self.disp_z: float = 0.0

        # Visual relocalization: scene_id → (disp_x, disp_z, confidence)
        self._scene_positions: dict[int, tuple[float, float, float]] = {}
        self._last_scene_id: int | None = None

    def set_anchor(self, x: float, z: float) -> None:
        """Set a new world anchor and reset displacement to zero.

        Parameters
        ----------
        x, z : float
            World-frame anchor position.
        """
        self.anchor = (x, z)
        self.disp_x = 0.0
        self.disp_z = 0.0

    def reset(self) -> None:
        """Clear anchor, displacement, and scene memory."""
        self.anchor = None
        self.disp_x = 0.0
        self.disp_z = 0.0
        self._scene_positions.clear()
        self._last_scene_id = None

    def integrate(self, heading_estimate: float, forward_speed: float,
                  dt: float) -> None:
        """Integrate displacement from forward speed along heading estimate.

        Parameters
        ----------
        heading_estimate : float
            Current heading in radians (CX compass estimate).
        forward_speed : float
            Forward speed in game units/s.
        dt : float
            Simulation tick interval (seconds).
        """
        if self.anchor is None:
            return
        if forward_speed > 0.0:
            self.disp_x += (np.sin(heading_estimate) * forward_speed
                            * self.SPEED_TO_UNITS * dt)
            self.disp_z += (np.cos(heading_estimate) * forward_speed
                            * self.SPEED_TO_UNITS * dt)
        else:
            # Slow decay when stationary to prevent infinite drift
            self.disp_x *= self.DISPLACEMENT_DECAY
            self.disp_z *= self.DISPLACEMENT_DECAY

    def relocalize(self, scene_id: int | None, confidence: float) -> None:
        """Correct path integration drift on familiar scene re-exposure.

        When the same scene is encountered with high confidence, pull
        disp_x/disp_z toward the remembered displacement for that scene.
        """
        if scene_id is None or confidence < self._relocalize_gate:
            self._last_scene_id = scene_id
            return
        if scene_id in self._scene_positions:
            mem_x, mem_z, mem_conf = self._scene_positions[scene_id]
            w = (self._relocalize_strength * confidence
                 * (1.0 - mem_conf * 0.5))
            self.disp_x += (mem_x - self.disp_x) * w
            self.disp_z += (mem_z - self.disp_z) * w
            self._scene_positions[scene_id] = (
                mem_x, mem_z, min(1.0, mem_conf + 0.05))
        elif self.anchor is not None:
            self._scene_positions[scene_id] = (
                self.disp_x, self.disp_z, confidence)
        self._last_scene_id = scene_id

    @property
    def distance(self) -> float:
        """Distance from anchor (game units)."""
        if self.anchor is None:
            return 0.0
        return float(np.hypot(self.disp_x, self.disp_z))

    @property
    def return_bearing(self) -> float | None:
        """World-frame bearing FROM current position BACK TO anchor.

        Returns None when at anchor or no anchor is set.
        """
        if self.anchor is None or (abs(self.disp_x) < 1e-8
                                   and abs(self.disp_z) < 1e-8):
            return None
        return float(np.arctan2(-self.disp_x, -self.disp_z))

    @property
    def displacement(self) -> tuple[float, float]:
        """Current displacement vector (dx, dz) from anchor."""
        return (self.disp_x, self.disp_z)

    @property
    def is_anchored(self) -> bool:
        """True when an anchor has been set."""
        return self.anchor is not None

    @property
    def scene_count(self) -> int:
        """Number of distinct scenes remembered for relocalization."""
        return len(self._scene_positions)


class MultiSourceGoalCompetition:
    """CX-3: Multi-source goal vector synthesis and steering competition.

    Accepts goal vectors from multiple sources (spatial memory, novelty,
    scene recognition, LLM advice) and produces a single steering bias
    through weighted vector competition in the FB (fan-shaped body).

    Each goal vector is a tuple (dx, dz, weight) where dx and dz are
    world-frame direction components and weight is the source's credibility.
    The resultant vector norm sets the goal strength; its direction sets
    the goal column on the compass ring.
    """

    def __init__(self, n_columns: int = N_COLUMNS,
                 steering_gain: float = STEERING_GAIN,
                 optic_flow_gain: float = OPTIC_FLOW_GAIN,
                 goal_update_rate: float = GOAL_UPDATE_RATE,
                 goal_memory_decay: float = GOAL_MEMORY_DECAY,
                 max_steering: float = MAX_STEERING):
        self.n_columns = n_columns
        self.steering_gain = steering_gain
        self.optic_flow_gain = optic_flow_gain
        self.goal_update_rate = goal_update_rate
        self.goal_memory_decay = goal_memory_decay
        self.max_steering = max_steering

        # Goal state
        self.goal_column: int = 0
        self.goal_strength: float = 0.0
        self._goal_float: float = 0.0

        # Steering output
        self.steering_bias: float = 0.0

        # Idle exploration wander
        self._idle_wander_phase: float = 0.0
        self._idle_wander_rate: float = 0.006

        # Loop-break state
        self._jump_seq: int = 0
        self._ticks_since_jump: int = CX_LOOP_BREAK_COOLDOWN_TICKS
        self._ext_goal_strength: float = 0.0

    def update(self, goal_vectors: list[tuple[float, float, float]] | None,
               heading_column: int, heading_estimate: float,
               novelty: float = 0.5,
               novelty_direction: float = 0.0,
               heading: float | None = None,
               flow_asymmetry: float = 0.0,
               stuck_duration: float = 0.0,
               n_columns: int | None = None) -> float:
        """One timestep of goal competition and steering computation.

        Parameters
        ----------
        goal_vectors : list of (dx, dz, weight) or None
            Multi-source goal vectors in world frame.
        heading_column : int
            Current compass heading column (0..n-1).
        heading_estimate : float
            Continuous heading estimate in radians.
        novelty : float, optional
            Novelty signal (0-1).
        novelty_direction : float, optional
            Direction component of novelty.
        heading : float or None, optional
            External game heading for legacy fallback.
        flow_asymmetry : float, optional
            Optic flow left-right imbalance.
        stuck_duration : float, optional
            Seconds stuck (for loop-break).

        Returns
        -------
        float
            Steering bias in [-1, 1]; positive = steer right.
        """
        n = n_columns if n_columns is not None else self.n_columns

        # ---- Goal vector competition ----
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
                self._ext_goal_strength = self.goal_strength
        elif (abs(novelty_direction) > 0.1 or abs(novelty - 0.5) > 0.3):
            # Legacy fallback: novelty-only goal
            h_ref = heading if heading is not None else heading_estimate
            column_idx = int((h_ref % (2 * np.pi)) / (2 * np.pi) * n) % n
            col_offset = novelty_direction * n * 0.25
            desired = (self._goal_float * (1.0 - self.goal_update_rate)
                       + (column_idx + col_offset) * self.goal_update_rate)
            self._goal_float = desired
            self.goal_column = int(round(desired)) % n
            self.goal_strength = min(1.0, self.goal_strength + self.goal_update_rate)
            self._ext_goal_strength = min(1.0, self._ext_goal_strength + self.goal_update_rate)
        else:
            self.goal_strength *= self.goal_memory_decay
            self._ext_goal_strength *= self.goal_memory_decay

        # ---- Idle exploration wander ----
        _no_goal = self._ext_goal_strength < 0.05
        if self.goal_strength < 0.05:
            self._idle_wander_phase += self._idle_wander_rate
            wander = np.sin(self._idle_wander_phase) * 8.0
            self._goal_float = (self._goal_float + wander * 0.05 + 0.002) % n
            self.goal_column = int(round(self._goal_float)) % n
            self.goal_strength = 0.30

        # ---- Loop-break jump ----
        stuck = float(stuck_duration or 0.0)
        self._ticks_since_jump += 1
        if (stuck > CX_LOOP_BREAK_STUCK_S and _no_goal
                and self._ticks_since_jump >= CX_LOOP_BREAK_COOLDOWN_TICKS):
            self._jump_seq += 1
            _h = (self._jump_seq * 2654435761) & 0xFFFFFFFF
            jump = _h % n
            self._goal_float = float(jump)
            self.goal_column = jump
            self.goal_strength = 0.60
            self._ticks_since_jump = 0

        # ---- Steering signal ----
        offset = (self.goal_column - heading_column) % n
        if offset > n / 2:
            offset -= n
        heading_steer = offset / (n / 2.0)
        flow_bias = flow_asymmetry * self.optic_flow_gain
        raw = (heading_steer * self.steering_gain * self.goal_strength
               + flow_bias)
        self.steering_bias = float(np.clip(raw, -self.max_steering, self.max_steering))
        return self.steering_bias

    def reset(self) -> None:
        """Clear goal state, wander phase, and loop-break counters."""
        self.goal_column = 0
        self.goal_strength = 0.0
        self._goal_float = 0.0
        self.steering_bias = 0.0
        self._idle_wander_phase = 0.0
        self._jump_seq = 0
        self._ticks_since_jump = CX_LOOP_BREAK_COOLDOWN_TICKS
        self._ext_goal_strength = 0.0


class CentralComplex:
    """Central Complex navigation module.

    Architecture
    ------------
    16-column ring attractor (heading compass)
      -> CX-2 AnchorPathIntegrator (displacement tracking)
      -> CX-3 MultiSourceGoalCompetition (vector synthesis → steering)

    Attributes
    ----------
    compass : np.ndarray, (N_COLUMNS,), float
        Ring-attractor activity for each heading column.
    heading_column : int
        Index of the most active compass column (0-15).
    path_integrator : AnchorPathIntegrator
        CX-2 sub-module for anchor-based displacement tracking.
    goal_comp : MultiSourceGoalCompetition
        CX-3 sub-module for multi-source goal vector competition.
    """

    MBON_NAMES = []  # no MBONs — CX outputs directly to motor pools

    def __init__(self, n_columns: int = N_COLUMNS,
                 steering_gain: float = STEERING_GAIN,
                 optic_flow_gain: float = OPTIC_FLOW_GAIN):
        self.n_columns = n_columns

        # CX-1: Heading compass (ring attractor)
        self.compass = np.ones(n_columns, dtype=np.float32) / n_columns
        self._imprint_heading(0.0)
        self._col_accum = 0.0
        self._compass_history = deque(maxlen=60)

        # CX-2: Anchor-based path integration
        self._path_integrator = AnchorPathIntegrator()

        # CX-3: Multi-source goal competition and steering
        self._goal_comp = MultiSourceGoalCompetition(
            n_columns=n_columns,
            steering_gain=steering_gain,
            optic_flow_gain=optic_flow_gain,
        )

        # Backward-compatible attribute references (delegated)
        self.anchor = None                    # → _path_integrator.anchor
        self.disp_x = 0.0                     # → _path_integrator.disp_x
        self.disp_z = 0.0                     # → _path_integrator.disp_z
        self.goal_column = 0                  # → _goal_comp.goal_column
        self.goal_strength = 0.0              # → _goal_comp.goal_strength
        self.steering_bias = 0.0              # → _goal_comp.steering_bias
        self.SPEED_TO_UNITS = 1.6
        self._goal_float = 0.0
        self._ext_goal_strength = 0.0
        self._jump_seq = 0
        self.stuck_time = 0.0
        self._ticks_since_jump = CX_LOOP_BREAK_COOLDOWN_TICKS
        self._idle_wander_phase = 0.0
        self._idle_wander_rate = 0.006
        self._loop_break_at: int | None = None

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
        """CX-1: move the bump by integrated angular velocity (rad/s)."""
        cols = heading_rate * dt / (2.0 * np.pi) * self.n_columns
        self._col_accum += cols
        whole = int(np.floor(self._col_accum))
        if whole != 0:
            self._roll_fractional(whole)
            self._col_accum -= whole

    # ── CX-2 delegation ──

    def set_anchor(self, x: float, z: float) -> None:
        """EVO R20 (CX-2): re-anchor path integration at the current pose."""
        self._path_integrator.set_anchor(x, z)
        self._sync_cx2_backrefs()

    @property
    def anchor_distance(self) -> float:
        """Integrated distance from the scene anchor (game units)."""
        return self._path_integrator.distance

    @property
    def anchor_return_bearing(self) -> float | None:
        """World-frame bearing FROM current position BACK TO the anchor."""
        return self._path_integrator.return_bearing

    def visual_relocalize(self, scene_id: int | None,
                          confidence: float,
                          scene_count: int) -> None:
        """Correct path integration drift by matching scene signatures."""
        self._path_integrator.relocalize(scene_id, confidence)
        self._sync_cx2_backrefs()

    def _sync_cx2_backrefs(self) -> None:
        """Sync backward-compatible anchor/disp references."""
        self.anchor = self._path_integrator.anchor
        self.disp_x = self._path_integrator.disp_x
        self.disp_z = self._path_integrator.disp_z

    def _sync_cx3_backrefs(self) -> None:
        """Sync backward-compatible goal/steering references."""
        self.goal_column = self._goal_comp.goal_column
        self.goal_strength = self._goal_comp.goal_strength
        self.steering_bias = self._goal_comp.steering_bias
        self._goal_float = self._goal_comp._goal_float
        self._ext_goal_strength = self._goal_comp._ext_goal_strength
        self._jump_seq = self._goal_comp._jump_seq
        self._ticks_since_jump = self._goal_comp._ticks_since_jump

    # ── CX internal methods ──

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
        """Create a normalised Gaussian heading-drive vector."""
        h_norm = heading % (2 * np.pi)
        column_frac = h_norm / (2 * np.pi) * self.n_columns
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
               scene_total: int = 0,
               stuck_duration: float = 0.0) -> float:
        """One timestep of CX processing: compass → path integration → steering.

        Parameters
        ----------
        heading : float or None
            External heading in radians (SM64) — weak correction.
        heading_rate : float
            Angular velocity in rad/s (positive = right) — SELF-MOTION.
        flow_asymmetry : float, optional
            Optic flow left-right imbalance for collision avoidance.
        novelty : float, optional
            Sensory novelty in [0, 1].
        novelty_direction : float, optional
            Directional component of novelty.
        dt : float, optional
            Simulation tick interval.
        visual_azimuth : float or None, optional
            Sky azimuth in radians for drift correction.
        forward_speed : float, optional
            Forward speed in game units/s.
        goal_vectors : list of (dx, dz, weight) or None, optional
            Multi-source goal vectors for CX-3 vector competition.
        scene_id : int or None, optional
            Scene identity for visual relocalization.
        scene_confidence : float, optional
            Confidence of current scene match.
        scene_total : int, optional
            Total scene count (unused, kept for signature compat).
        stuck_duration : float, optional
            Seconds stuck (for loop-break).

        Returns
        -------
        float
            Steering bias in [-1, 1]; positive = steer right.
        """
        n = self.n_columns

        # ── CX-1: Heading compass ──
        self._self_motion_update(heading_rate, dt)
        roll_left = np.roll(self.compass, 1)
        roll_right = np.roll(self.compass, -1)
        local = (roll_left + self.compass * 2.0 + roll_right) / 4.0
        mean_activity = float(self.compass.mean())
        drive = (self._heading_drive(heading) * 0.10
                 if heading is not None else 0.0)
        if visual_azimuth is not None:
            drive += self._heading_drive(visual_azimuth) * 0.12
        raw = (self.compass * COMPASS_PERSISTENCE
               + local * LOCAL_EXCITATION
               - mean_activity * GLOBAL_INHIBITION
               + drive)
        raw = np.maximum(raw, 0)
        total = raw.sum() + EPS
        self.compass = (raw / total).astype(np.float32)
        self._compass_history.append(self.compass.copy())

        # ── CX-2: Anchor-frame path integration ──
        self._path_integrator.integrate(
            self.heading_estimate, forward_speed, dt)
        self._path_integrator.relocalize(scene_id, scene_confidence)
        self._sync_cx2_backrefs()

        # ── CX-3: Multi-source goal competition → steering ──
        steering = self._goal_comp.update(
            goal_vectors=goal_vectors,
            heading_column=self.heading_column,
            heading_estimate=self.heading_estimate,
            novelty=novelty,
            novelty_direction=novelty_direction,
            heading=heading,
            flow_asymmetry=flow_asymmetry,
            stuck_duration=stuck_duration,
        )
        self._sync_cx3_backrefs()
        self.stuck_time = float(stuck_duration or 0.0)

        return steering

    def reset(self) -> None:
        """Reset compass, path integrator, and goal competition."""
        self.compass.fill(1.0 / self.n_columns)
        self._imprint_heading(0.0)
        self._compass_history.clear()
        self._path_integrator.reset()
        self._goal_comp.reset()
        self._sync_cx2_backrefs()
        self._sync_cx3_backrefs()
        self.stuck_time = 0.0
        self._loop_break_at = None
        self.SPEED_TO_UNITS = 1.6

    # ── Diagnostics ──

    @property
    def heading_estimate(self) -> float:
        """Estimated heading in radians from compass activity.

        Weighted-average from ring-attractor activity, providing a smooth
        heading estimate even when direct game heading is unavailable.
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
            "loop_breaks": self._jump_seq,
            "stuck_time": round(self.stuck_time, 2),
            "anchor_distance": round(self.anchor_distance, 2),
            "scene_count": self._path_integrator.scene_count,
        }