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

    def update(self, heading: float, heading_rate: float,
               flow_asymmetry: float = 0.0,
               novelty: float = 0.5,
               novelty_direction: float = 0.0) -> float:
        """One timestep of CX processing.

        Parameters
        ----------
        heading : float
            Current heading in radians (from SM64 game state).
        heading_rate : float
            Angular velocity in rad/s (positive = turning right).
        flow_asymmetry : float
            Left/right optic flow imbalance in [-1, 1].
        novelty : float
            Scene novelty in [0, 1] (0=familiar, 1=novel).
        novelty_direction : float
            Direction bias from novelty in [-1, 1]; positive = steer
            right, negative = steer left.

        Returns
        -------
        steering_bias : float
            Steering output in [-1, 1]; positive = turn right,
            negative = turn left.  Injected into turn motor pools.
        """
        # ---- 1. Ring-attractor heading compass ----
        # The compass maintains a stable activity bump through local
        # excitation (neighbouring columns) and global inhibition.
        # A heading drive pulls the bump toward the current heading.

        n = self.n_columns

        # Local excitation: each column receives input from its neighbours
        # using a [1, 2, 1] kernel (centre-weighted).
        roll_left = np.roll(self.compass, 1)
        roll_right = np.roll(self.compass, -1)
        local = (roll_left + self.compass * 2.0 + roll_right) / 4.0

        # Global inhibition: mean activity suppresses all columns equally
        mean_activity = float(self.compass.mean())

        # Heading drive: Gaussian bump at the current heading
        drive = self._heading_drive(heading)

        # Ring attractor update (divisive normalisation)
        raw = (
            self.compass * COMPASS_PERSISTENCE
            + local * LOCAL_EXCITATION
            - mean_activity * GLOBAL_INHIBITION
            + drive * HEADING_DRIVE_WEIGHT
        )
        # Ensure non-negative; divisive normalisation.
        raw = np.maximum(raw, 0)
        total = raw.sum() + EPS
        self.compass = (raw / total).astype(np.float32)

        # Record history
        self._compass_history.append(self.compass.copy())

        # ---- 2. Goal-direction update ----
        # The goal tracks where novelty signals suggest steering.
        # Convert novelty_direction into a desired goal column offset.
        h_norm = heading % (2 * np.pi)
        column_idx = int(h_norm / (2 * np.pi) * n) % n

        if abs(novelty_direction) > 0.1 or abs(novelty - 0.5) > 0.3:
            # novelty_direction > 0 → want to steer right
            # In SM64, +x = turn right, which is positive heading_rate.
            # novelty_direction > 0 → steer right → goal is right of current,
            # which is a positive column offset.
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