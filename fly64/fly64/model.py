from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import time

import numpy as np
from scipy import sparse
from .retina import SphericalRetina
from .mushroom_body import MushroomBody
from .gain_modulation import DopamineGainController
from .central_complex import CentralComplex


def synaptic_current(w, spikes):
    """Synaptic current into all neurons from spiking presynaptic cells.

    Adaptive selection: boolean-mask column selection below ~10% fired,
    fancy-index above.  MEASURED (interleaved medians, real 25.6M-edge
    connectome): no reliable speedup over plain fancy-index — both branches
    are equivalent math and the cost is memory-bound on the selected nnz
    (0.95-1.38x, inside load noise).  Kept for the low-fraction branch's
    slight edge and as the documented baseline; see the P1-2 negative
    result at the call site before attempting further micro-optimization.
    """
    n = w.shape[0]
    fired = np.flatnonzero(spikes)
    if fired.size == 0:
        return np.zeros(n, dtype=np.float32)
    if fired.size <= 0.10 * n:
        return np.asarray(
            w[:, spikes.astype(bool)].sum(axis=1)).ravel().astype(np.float32)
    return np.asarray(w[:, fired].sum(axis=1)).ravel().astype(np.float32)


@dataclass
class Control:
    x: int
    y: int
    jump: bool
    forward_rate: float
    turn_rate: float
    jump_rate: float
    b: bool = False   # B button (LLM dialogue decisions; emulator may ignore)
    z: bool = False   # Z trigger (crouch / long-jump combos; bridge v2.14.0)


class SceneMemory:
    """Visual short-term memory: ring buffer of mean brightness with scene change detection.

    Maintains a 30-frame (~600 ms at 50 Hz) circular buffer of per-frame mean
    retina brightness (a scalar per frame).  Computes the mean and standard
    deviation of the buffer, and flags a scene change when the current frame
    deviates from the buffer mean by more than 3σ (three standard deviations).

    Attributes
    ----------
    scene_buffer : deque[float], maxlen=30
        Ring buffer of per-frame mean brightness values.
    scene_mean : float
        Mean of the buffer values.
    scene_var : float
        Variance of the buffer values.
    scene_change : bool
        True when ``|current_drive_mean − scene_mean| > 3σ``.
    scene_change_rate : float
        Fraction of the last 10 frames that were flagged as scene changes (0–1).
    """

    def __init__(self, buffer_size: int = 30, sigma_threshold: float = 3.0):
        self.buffer_size = buffer_size
        self.sigma_threshold = sigma_threshold

        # Ring buffer of per-frame mean brightness
        self.scene_buffer: deque[float] = deque(maxlen=buffer_size)

        self.scene_mean = 0.0       # mean of buffer
        self.scene_var = 0.0        # variance of buffer
        self.scene_change = False   # |current − mean| > 3σ

        # Rolling window for scene_change_rate
        self._change_history: deque[bool] = deque(maxlen=10)

    def update(self, drive_mean: float) -> dict:
        """Feed one frame's mean retina brightness; return scene-detection state.

        Parameters
        ----------
        drive_mean : float
            Mean brightness of the retina drive for the current frame.

        Returns
        -------
        dict with keys:
            scene_mean        — mean of buffer values
            scene_var         — variance of buffer values
            scene_change      — True when |drive_mean − scene_mean| > 3σ
            scene_change_rate — fraction of last 10 frames that were changes (0–1)
            buffer_fill       — number of frames currently in the buffer
        """
        self.scene_buffer.append(drive_mean)

        if len(self.scene_buffer) >= 2:
            arr = np.array(self.scene_buffer, dtype=np.float64)
            self.scene_mean = float(np.mean(arr))
            self.scene_var = float(np.var(arr))
            sigma = np.sqrt(self.scene_var) if self.scene_var > 0 else 0.0
            self.scene_change = bool(
                abs(drive_mean - self.scene_mean) > self.sigma_threshold * sigma
            )
        else:
            self.scene_mean = drive_mean
            self.scene_var = 0.0
            self.scene_change = False

        self._change_history.append(self.scene_change)

        return {
            "scene_mean": round(self.scene_mean, 6),
            "scene_var": round(self.scene_var, 6),
            "scene_change": self.scene_change,
            "scene_change_rate": round(float(np.mean(self._change_history)), 3),
            "buffer_fill": len(self.scene_buffer),
        }

    @property
    def scene_change_rate(self) -> float:
        """Fraction of the last 10 frames that were scene changes (0–1)."""
        h = self._change_history
        return float(np.mean(h)) if h else 0.0

    @property
    def buffer_as_array(self) -> np.ndarray | None:
        """Return buffer values as (N,) array or None if empty."""
        if not self.scene_buffer:
            return None
        return np.array(self.scene_buffer, dtype=np.float64)

    def reset(self) -> None:
        """Clear the buffer and reset all statistics."""
        self.scene_buffer.clear()
        self._change_history.clear()
        self.scene_mean = 0.0
        self.scene_var = 0.0
        self.scene_change = False


@dataclass
class TrackState:
    """Single target track state for small target tracking."""
    track_id: int
    centroid: tuple[float, float]    # (row, col) in grid coordinates
    velocity: tuple[float, float]    # pixels/frame
    age: int                          # frames since track creation
    hit_count: int                    # number of successful detections
    missed_count: int                 # consecutive misses
    approaching: bool                 # is target on approach trajectory?
    time_to_intercept: float          # estimated frames until interception


class TargetTracker:
    """Multi-target tracker with Kalman filter and Hungarian association.

    Maintains a set of tracks, performs prediction-update cycles, and
    estimates interception timing for moving platforms and enemies.
    """

    def __init__(self, dt: float = 0.02):
        self.dt = dt
        self.tracks: list[TrackState] = []
        self.next_id = 0
        self.MISSED_THRESHOLD = 10        # drop track after 10 misses
        self.INTERCEPTION_MIN_FRAMES = 5  # minimum frames for interception
        self.VELOCITY_DECAY = 0.9         # velocity low-pass filter
        self.MAX_ASSOC = 15.0             # max association distance in pixels

    def update(self, detections: list[tuple[float, float]],
               sizes: list[int],
               directions: list[str]) -> list[TrackState]:
        """Update tracks with new detections using Hungarian matching.

        Parameters
        ----------
        detections : list[(r, c)]
            Centroid positions from compute_small_targets().
        sizes : list[int]
            Target sizes in cells.
        directions : list[str]
            Target direction labels.

        Returns
        -------
        list[TrackState]
            Active tracks after matching.
        """
        if not detections:
            for t in self.tracks:
                t.missed_count += 1
            self._prune_tracks()
            return self.tracks

        # Predict new positions (constant velocity)
        predicted = []
        for t in self.tracks:
            pr = t.centroid[0] + t.velocity[0]
            pc = t.centroid[1] + t.velocity[1]
            predicted.append((pr, pc))

        n_tracks = len(predicted)
        n_det = len(detections)
        assigned_tracks: set[int] = set()
        assigned_dets: set[int] = set()

        if n_tracks > 0 and n_det > 0:
            # Build cost matrix
            cost = np.zeros((n_tracks, n_det), dtype=np.float32)
            for i, (pr, pc) in enumerate(predicted):
                for j, (dr, dc) in enumerate(detections):
                    cost[i, j] = np.hypot(pr - dr, pc - dc)

            # Hungarian or greedy matching
            hungarian_used = False
            if 4 <= n_tracks <= 15 and n_det <= 15:
                from scipy.optimize import linear_sum_assignment
                row_idx, col_idx = linear_sum_assignment(cost)
                for i, j in zip(row_idx, col_idx):
                    if cost[i, j] < self.MAX_ASSOC:
                        assigned_tracks.add(i)
                        assigned_dets.add(j)
                hungarian_used = True
            else:
                # Greedy nearest-neighbor for small/large sets
                for j in range(n_det):
                    best_dist = self.MAX_ASSOC
                    best_i = -1
                    for i in range(n_tracks):
                        dist = cost[i, j]
                        if dist < best_dist and i not in assigned_tracks:
                            best_dist = dist
                            best_i = i
                    if best_i >= 0:
                        assigned_tracks.add(best_i)
                        assigned_dets.add(j)

            # Update matched tracks
            if hungarian_used:
                # Direct Hungarian assignment: each i mapped to exactly one j
                for match_i in range(len(row_idx)):
                    i, j = row_idx[match_i], col_idx[match_i]
                    if cost[i, j] >= self.MAX_ASSOC:
                        self.tracks[i].missed_count += 1
                        continue
                    self._update_track(i, j, detections, directions)
            else:
                # Greedy assignment: update via the pairs in assigned sets
                track_to_det = {}
                for i in assigned_tracks:
                    for j in assigned_dets:
                        if cost[i, j] < self.MAX_ASSOC:
                            track_to_det[i] = j
                            break
                for i, j in track_to_det.items():
                    self._update_track(i, j, detections, directions)

            # Unassigned tracks → increment miss
            for i in range(n_tracks):
                if i not in assigned_tracks:
                    self.tracks[i].missed_count += 1

            # Unassigned detections → new tracks
            for j in range(n_det):
                if j not in assigned_dets:
                    new_track = TrackState(
                        track_id=self.next_id,
                        centroid=detections[j],
                        velocity=(0.0, 0.0),
                        age=0, hit_count=1, missed_count=0,
                        approaching=False,
                        time_to_intercept=float("inf"),
                    )
                    self.tracks.append(new_track)
                    self.next_id += 1
        else:
            if n_tracks > 0:
                for t in self.tracks:
                    t.missed_count += 1
            for j in range(n_det):
                new_track = TrackState(
                    track_id=self.next_id,
                    centroid=detections[j],
                    velocity=(0.0, 0.0),
                    age=0, hit_count=1, missed_count=0,
                    approaching=False,
                    time_to_intercept=float("inf"),
                )
                self.tracks.append(new_track)
                self.next_id += 1

        self._prune_tracks()
        return self.tracks

    def _prune_tracks(self):
        """Remove tracks that have been missing too long."""
        self.tracks = [t for t in self.tracks
                       if t.missed_count < self.MISSED_THRESHOLD]

    def nearest_approaching_target(self) -> TrackState | None:
        """Return the approaching track with smallest time_to_intercept."""
        approaching = [t for t in self.tracks
                       if t.approaching and np.isfinite(t.time_to_intercept)]
        if not approaching:
            return None
        return min(approaching, key=lambda t: t.time_to_intercept)

    def reset(self):
        """Clear all tracks."""
        self.tracks.clear()
        self.next_id = 0

    def _update_track(self, track_idx: int, det_idx: int,
                      detections: list, directions: list):
        """Update a single track from a matched detection."""
        t = self.tracks[track_idx]
        dr = detections[det_idx][0] - t.centroid[0]
        dc = detections[det_idx][1] - t.centroid[1]
        t.velocity = (
            t.velocity[0] * self.VELOCITY_DECAY + dr * (1 - self.VELOCITY_DECAY),
            t.velocity[1] * self.VELOCITY_DECAY + dc * (1 - self.VELOCITY_DECAY),
        )
        t.centroid = detections[det_idx]
        t.age += 1
        t.hit_count += 1
        t.missed_count = 0
        drc = directions[det_idx] if det_idx < len(directions) else "stationary"
        t.approaching = (drc == "approaching")
        speed = np.hypot(t.velocity[0], t.velocity[1])
        if speed > 0.5 and t.approaching:
            dist_to_center = np.hypot(t.centroid[0] - 24, t.centroid[1] - 32)
            t.time_to_intercept = dist_to_center / speed
        else:
            t.time_to_intercept = float("inf")


class TurnAdaptation:
    """Homeostatic turn-circuit adaptation — spontaneous alternation.

    Drosophila spontaneously alternates turn direction: a sustained turn in
    one direction fatigues the dominant turning circuit and progressively
    recruits the competitor.  Implemented as paired low-pass fatigue states
    over the LIF turn-pool firing; the fatigue feeds back as a COUNTER-DRIVE
    current injected pre-spike, so direction selection remains inside the
    network dynamics — no Python direction decision is involved.
    """

    def __init__(self, tau: float = 3.0, saturation: float = 0.5,
                 gain: float = 0.18, breakout_gain: float = 0.35):
        self.tau = tau                # fatigue integration window (s)
        self.saturation = saturation  # pool activity (fraction) at full fatigue
        self.gain = gain              # max counter-drive current (V)
        self.breakout_gain = breakout_gain  # oscillation → forward breakthrough
        self.left = 0.0               # fatigue of left-turn circuit
        self.right = 0.0              # fatigue of right-turn circuit

    def update(self, act_left: float, act_right: float, dt: float) -> None:
        """Integrate one step of turn-pool activity (fractions in [0, 1])."""
        decay = float(np.exp(-dt / max(self.tau, 1e-6)))
        self.left = self.left * decay + max(0.0, act_left) * dt
        self.right = self.right * decay + max(0.0, act_right) * dt

    def counter_drive(self) -> tuple[float, float]:
        """Return (drive_right, drive_left) counter currents in [0, gain]."""
        nl = min(1.0, self.left / max(self.saturation, 1e-6))
        nr = min(1.0, self.right / max(self.saturation, 1e-6))
        return nl * self.gain, nr * self.gain

    def breakout_drive(self, stuck_duration: float = 0.0) -> float:
        """Oscillation-in-place detector → forward breakthrough current.

        BOTH circuits fatigued ≈ left/right alternation with no net heading —
        the weave-in-place signature.  Returns a forward-pool current that
        scales with the balanced fatigue level and adapts to stuck duration.
        Longer stuck → higher gain (max at 120s+).
        """
        nl = min(1.0, self.left / max(self.saturation, 1e-6))
        nr = min(1.0, self.right / max(self.saturation, 1e-6))
        base = self.breakout_gain * min(nl, nr)
        # Adaptive boost: stuck longer → more aggressive breakout
        if stuck_duration > 30:
            boost = min(0.50, self.breakout_gain * (stuck_duration / 120.0))
            return base + boost
        return base

    def reset(self) -> None:
        """Clear both fatigue states (scene change / new exploration)."""
        self.left = 0.0
        self.right = 0.0


class FlyModel:
    """Connectome-derived LIF approximation with explicit engineered I/O maps."""

    dt = 0.020
    tau_m = 0.100
    threshold = 1.0
    reset = 0.0
    SELF_MOTION_K = 0.08  # maps heading_rate (rad/s) → flow_asymmetry correction
    scene_mean = 0.0       # class-level default for hasattr checks
    scene_var = 0.0
    scene_change = False
    scene_change_rate = 0.0
    # Named injection coefficients (P2-2: extracted from magic numbers)
    ESCAPE_JUMP_DRIVE = 0.45      # jump-pool burst when fallen
    BOLD_TURN_DRIVE = 0.35        # forced-bold escape turn current
    PIT_FORWARD_HOP = 0.40        # pit escape forward oscillator amplitude
    PIT_JUMP_HOP = 0.80           # pit escape jump oscillator amplitude
    PIT_SWAY_AMP = 0.05           # pit escape lateral sway amplitude
    TAU_JUMP_INJECTION = 0.35     # max tau collision jump drive
    TARGET_JUMP_CLOSE = 0.50      # target jump strength when <=2 frames
    CLIFF_TANGENT_TURN = 0.15     # cliff edge tangential detour turn
    INTERACTIVE_FORWARD = 0.10    # interactive target approach bias
    ESCAPE_CURRENT_SCALE = 0.30   # interactive mode escape suppression
    TAU_JUMP_INJ_MAX = 0.35

    def __init__(self, cache: Path | None = None, demo: bool = False, seed: int = 64):
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        if demo:
            self._load_demo()
            self.label = "DEMO FIXTURE — modeled graph"
        else:
            if cache is None or not (cache / "manifest.json").exists():
                raise FileNotFoundError("Prepared MaleCNS model missing; run ./run-fly64 --prepare-data")
            self._load_cache(cache)
            self.label = "MaleCNS v1.0 — measured wiring, modeled dynamics"
        self.v = np.zeros(self.n, dtype=np.float32)
        # CSC event propagation traverses every outgoing edge of each spiking
        # cell. Zero-spike columns contribute exactly zero; no graph pruning.
        self.w = self.w.tocsc()
        self.spikes = np.zeros(self.n, dtype=np.float32)
        self.activity = np.zeros(self.n, dtype=np.float32)
        self.retina = SphericalRetina(self.visual_pixels)
        self.previous_rgb = np.zeros((len(self.visual), 3), dtype=np.float32)

        # ---- Landmark memory: random projection of retina output to scene signatures ----
        # Project 1536-dim retina drive → 128-dim scene signature using a random
        # matrix drawn from N(0, scale=0.1) with PROJECTION_SEED=42 for cross-run
        # reproducibility (independent of the model's main RNG seeding).
        PROJECTION_SEED = 42
        _proj_rng = np.random.default_rng(PROJECTION_SEED)
        self.projection = _proj_rng.normal(
            0.0, 0.1, (128, len(self.visual))
        ).astype(np.float32)
        # 5-channel color projection for color-enhanced scene signature
        # Shape: (128, 1536 * 5) = (128, 7680), same distribution as above
        self.color_projection = _proj_rng.normal(
            0.0, 0.1, (128, len(self.visual) * 5)
        ).astype(np.float32)
        self.scene_sig = np.zeros(128, dtype=np.float32)
        self.scene_sig_valid = False
        self.history = deque(maxlen=13)
        # Phase 3 motor expansion: strike (B) / crouch (Z) decode pools.
        # _select_io_pools() fills these after the connectome is loaded.
        self.strike_nodes = np.array([], dtype=np.int32)
        self.crouch_nodes = np.array([], dtype=np.int32)
        self._cpg_gate_strike = 0.0
        self._cpg_gate_crouch = 0.0
        self.last_strike = -10.0
        self.motor_nodes = np.concatenate((self.forward, self.turn_left, self.turn_right, self.jump_nodes))
        self.motor_splits = np.cumsum([len(self.forward), len(self.turn_left), len(self.turn_right)])
        self._select_io_pools()
        self.motor_nodes = np.concatenate((self.motor_nodes, self.strike_nodes, self.crouch_nodes))
        self.motor_splits = np.cumsum([len(self.forward), len(self.turn_left), len(self.turn_right),
                                       len(self.jump_nodes), len(self.strike_nodes)])
        self.filtered_x = 0.0
        self.filtered_y = 0.0
        self.last_jump = -10.0
        self.step_count = 0
        self.mean_luminance = 0.0
        self.temporal_energy = 0.0
        self.visual_connected = True
        self.tonic_current = 0.180
        self.synaptic_gain = 1.50
        # Reward signal (for gain modulation plasticity proxy)
        self.reward_signal = 0.0
        self.movement_reward = 0.0  # EVO R11: displacement-based dopamine feedback
        self._pending_dopamine = 0.0  # EVO R13: external setback pulses (PPL1-like)
        self._success_pulse_floor = 0.0  # M3.2: success-tick dopamine floor
        self._prev_stuck_duration = 0.0
        self._cumulative_reward = 0.0
        # Local motion detection: moving objects when Mario is stationary
        self.local_motion_energy = 0.0
        self.local_motion_detected = False
        # Ornstein-Uhlenbeck noise for physiological motor fluctuations
        self.ou_state = np.zeros(4, dtype=np.float32)  # [fwd, left, right, jump]
        self.ou_theta = 2.0   # mean reversion rate (higher = faster decay)
        self.ou_sigma = 0.12  # noise amplitude
        self.ou_mu = 0.0      # mean

        # ---- Passive propagation enhancement ----  # t6: improve LIF utilisation
        # Synaptic current buffer: slow temporal integration modelling
        # neurotransmitter persistence and passive cable spread.  Improves
        # signal propagation through deeper network layers without task-
        # specific gating or shunting.
        self.synaptic_buf_decay = 0.65           # per-frame decay (tau ~ 3 frames)
        self._synaptic_buf = np.zeros(self.n, dtype=np.float32)

        # Global OU noise for all neurons (replaces sparse Bernoulli kicks).
        # Continuous correlated subthreshold fluctuations improve utilisation
        # of every neuron in the connectome, not just motor populations.
        self.ou_global_theta = 2.0               # mean reversion rate
        self.ou_global_sigma = 0.10              # noise amplitude
        self.ou_global_state = np.zeros(self.n, dtype=np.float32)

        # Novelty-driven modulation and escape
        self.escape_mode = False
        self.escape_current = 0.15  # extra depolarisation during escape
        # P1 (BRAIN 2.7.0): escape sub-drives set by the brain runner —
        # jump-burst drive during falls, alternating breakout turn drive.
        self.escape_jump_drive = False
        self.bold_turn_drive = 0.0
        # EVO R14: homeostatic turn-circuit adaptation (spontaneous
        # alternation) — sustained one-direction turning fatigues that
        # circuit and counter-drives the competitor, all pre-spike.
        self._turn_adapt = TurnAdaptation()
        # EVO R14: anomaly-state mirror (sensory input for the DAN dopamine
        # signal; set by main.py each tick from the memory controller).
        self.anomaly_state_name = "idle"
        # EVO R15: cliff-standoff sensory mirror (s from the memory
        # controller; tangential detour bias from FailureMemory).
        self.cliff_standoff_s = 0.0
        self.cliff_tangent_bias = 0.0
        # EVO R30: pose_y for below-ground detection in rate boost
        self.pose_y = 0.0
        # EVO R19: restlessness inputs (loop pressure + scene danger)
        self.loop_score = 0.0
        self.scene_danger = 0.0
        # EVO R20 (CX-1): sky azimuth for compass drift correction
        self.visual_azimuth = None
        # Visual short-term memory (scene change detection)
        self.scene_memory = SceneMemory(buffer_size=30)
        self.scene_mean = 0.0
        self.scene_var = 0.0
        self.scene_change = False
        self.scene_change_rate = 0.0

        # Optic flow signals (set by encode_retina, consumed in step)
        self.flow_asymmetry = 0.0   # RAW left/right motion imbalance (-1..1), NOT self-motion corrected
        self.flow_looming = 0.0     # center expansion index (-1..1)
        self.flow_cliff = 1.0       # lower-field green ratio (1=grass, 0=void)

        # ---- Self-motion separation: heading tracking for optic-flow correction ----
        self.heading = 0.0          # current heading (yaw) in radians
        self.prev_heading = 0.0     # previous-frame heading for rate computation
        self.heading_rate = 0.0     # angular velocity (rad/s), positive = turning right
        self._self_motion_cache = {
            "heading_rate": 0.0, "true_asymmetry": 0.0, "k": self.SELF_MOTION_K,
        }  # backing store for self_motion and true_asymmetry properties

        # ---- Multi-channel retina signals (6-channel encoding) ----
        self.on_energy = 0.0        # ON channel: positive luminance transients
        self.off_energy = 0.0       # OFF channel: negative luminance transients
        self.sustained_energy = 0.0 # Sustained: slow contrast change
        self.edge_0 = 0.0           # Horizontal edge energy
        self.edge_45 = 0.0          # Diagonal (45°) edge energy
        self.edge_90 = 0.0          # Vertical edge energy
        self.edge_135 = 0.0         # Anti-diagonal (135°) edge energy

        # ---- Color vision channels ----
        self.sky_blue_index = 0.0       # 0-1: open sky above
        self.danger_red_index = 0.0     # 0-1: lava/enemy below
        self.color_contrast = 0.0       # 0-1: hue diversity
        self.rg_opponent_mean = 0.0     # red-green opponent balance
        self.by_opponent_mean = 0.0     # blue-yellow opponent balance
        self.uv_appx_mean = 0.0         # mean UV approximation
        self.saturation_mean = 0.0      # mean color saturation
        self.color_azimuth = {}          # per-band dominant hue dict

        # ---- Color-enhanced scene signature ----
        # EVO R14: enabled.  The 5-channel (luminance + red/UV/green
        # salience + mean RGB) projection feeds both the Kenyon Cells of the
        # mushroom body and the scene database, giving the brain colour-
        # discriminative scene codes (collision rate 10³/day → <1/yr).
        # Persisted scene signatures rebuild within one loop_window.
        self.color_signature = True

        # ---- 4-direction EMD (T4/T5 equivalent) ----
        self.emd_on_right = 0.0   # T4 rightward motion energy
        self.emd_on_left = 0.0    # T4 leftward motion energy
        self.emd_on_down = 0.0    # T4 downward motion energy
        self.emd_on_up = 0.0      # T4 upward motion energy
        self.emd_off_right = 0.0  # T5 rightward motion energy
        self.emd_off_left = 0.0   # T5 leftward motion energy
        self.emd_off_down = 0.0   # T5 downward motion energy
        self.emd_off_up = 0.0     # T5 upward motion energy
        self.emd_on_total = 0.0   # T4 summed energy
        self.emd_off_total = 0.0  # T5 summed energy
        # Derived compound signals
        self.emd_horizontal = 0.0  # emd_on_right + emd_on_left + emd_off_right + emd_off_left
        self.emd_vertical = 0.0    # emd_on_up + emd_on_down + emd_off_up + emd_off_down
        self.emd_net_lateral = 0.0 # (right - left) / (right + left + eps) — signed lateral bias
        self.emd_net_vertical = 0.0 # (down - up) / (down + up + eps) — signed vertical bias

        # ---- Cliff detection (multi-frame confirmation) ----
        self._cliff_history = deque(maxlen=10)  # last 10 lower_field_green values
        self.CLIFF_THRESHOLD = 0.25
        self.CLIFF_RAPID_DROP = 0.15
        self.CLIFF_CONFIRM_FRAMES = 7

        # ---- Terrain classification from 16-sector optic flow ----
        self.terrain = "mixed"  # one of: cliff, water, corridor, wall_ahead,
                                # open_flat, dense, forest_edge, indoor, mixed
        self.wall_score = 0.0   # 0-1: vertical surface ahead
        self.ramp_score = 0.0   # 0-1: sloping surface
        self.opening_score = 0.0  # 0-1: passage/opening ahead
        self.sky_score = 0.0    # 0-1: open sky above (blue-dominance gated, EVO R9)
        self.enclosure_score = 0.0  # 0-1: indoor/enclosed probability (EVO R9)
        self.ground_angle = 0.7  # 0=cliff, 0.3-0.7=slope, >0.7=flat
        self.door_frame_score = 0.0  # 0-1: doorway detected
        self.opening_width = 0.0  # 0-1: opening width
        self.opening_asymmetry = 0.0  # -1..1: opening toward left(<0) / right(>0) field (EVO R11)

        # ---- Tau (time-to-contact) for collision avoidance ----
        self.tau = float("inf")  # seconds until contact; inf = no collision risk
        self.TAU_SHARP_TURN = 0.5   # τ below this → emergency sharp turn
        self.TAU_DECELERATE = 1.0   # τ below this → reduce speed
        self.TAU_NEAR = 2.0         # τ below this → cautious modulation

        # ---- Mushroom Body associative learning ----
        self.mushroom = MushroomBody()
        self.mbon_gain_forward = 0.15
        self.mbon_gain_turn = 0.12
        self.mbon_gain_jump = 0.20
        self.mbon_gain_explore = 0.10

        # ---- Dopamine-gated gain modulation (plasticity proxy) ----
        # Per-pathway gains modulate connectome current injection without
        # modifying the fixed connectome weights self.w.
        self.dopamine_gain = DopamineGainController()

        # Pre-compute per-neuron pathway index for vectorised gain application
        # 0=visual, 1=forward, 2=turn, 3=jump, 4=recurrent (default)
        self._pathway_idx_map = np.full(self.n, 4, dtype=np.uint8)
        if len(self.visual) > 0:
            self._pathway_idx_map[self.visual] = 0
        if len(self.forward) > 0:
            self._pathway_idx_map[self.forward] = 1
        self._turn_all = np.concatenate((self.turn_left, self.turn_right))
        if len(self._turn_all) > 0:
            self._pathway_idx_map[self._turn_all] = 2
        if len(self.jump_nodes) > 0:
            self._pathway_idx_map[self.jump_nodes] = 3
        # Pre-allocated gain lookup array (updated each step)
        self._pathway_gains_np = np.ones(5, dtype=np.float32)

        # ---- Central Complex navigation module ----
        self.cx = CentralComplex()
        self.cx_steering_gain_turn = 0.12   # CX steering → turn motor pool
        self.cx_novelty_direction = 0.0     # from memory controller

        # ---- Small target tracking (LPLC/LC11 equivalent) ----
        self.target_tracker = TargetTracker(dt=self.dt)
        self.target_count = 0
        self.target_approaching = False
        self.target_intercept_time = float("inf")
        self.target_nearest_centroid = (0.0, 0.0)
        self.target_nearest_velocity = (0.0, 0.0)
        self.fg_fraction = 0.0
        self.max_target_energy = 0.0

        # ---- Python→neuron error gradient bridge (t3) ----
        self._last_error_gradient = {
            "error": 0.0, "neural_bias": 0.0, "python_bias": 0.0,
            "corrective_left": 0.0, "corrective_right": 0.0,
        }
        self._corrective_current_applied = (0.0, 0.0)
        # Pending Python turn correction for t3 error gradient bridge
        self._pending_python_turn = 0

        # P4-1: Reflex→LIF bridge — reflex circuit sets flags, model
        # converts to current injection so the LIF network shares the
        # motor-pool decision with the reflex (instead of Python bypassing
        # the network entirely with a direct control.x write).
        self.reflex_turn = 0
        self.reflex_forward = 0
        self.reflex_jump = False

        # Fallen recovery: persistent forward + jump when fallen
        self._fallen_forward = 0.20       # forward current during fallen
        self._fallen_jump_boost = 0.60    # jump boost during fallen (above ESCAPE_JUMP_DRIVE)
        self._fallen_share_forward = 0.5  # EVO R32: fallen forward duty cycle (time-share with steering)

        # Navigation: exploration direction commitment + frontier
        self._explore_bias = 0.0          # current commit direction [-1,1]
        self._explore_commit_timer = 0     # frames remaining in commit
        self._explore_commit_ticks = 250   # 5s at 50Hz
        self._explore_commit_strength = 0.10  # turn bias during commit

        # Escape displacement improvement: direction commit + adaptive gain
        self._escape_commit_timer = 0      # frames remaining in commit
        self._escape_commit_dir = 0         # +1=right, -1=left
        self._escape_commit_ticks = 50      # commit duration (1s at 50Hz)
        self._escape_forward_accum = 0.15   # base forward gain during escape
        self._last_escape_pos = (0.0, 0.0)  # last position for displacement check

    def _load_demo(self):
        self.n = 4096
        row = self.rng.integers(0, self.n, 65536, dtype=np.int32)
        col = self.rng.integers(0, self.n, 65536, dtype=np.int32)
        weight = self.rng.lognormal(-2.7, 0.5, len(row)).astype(np.float32)
        inhibitory = self.rng.random(self.n) < 0.22
        weight *= np.where(inhibitory[col], -1.0, 1.0)
        self.visual = np.arange(0, 1536, dtype=np.int32)
        flat_pixels = np.linspace(0, 48 * 64 - 1, len(self.visual)).astype(np.int32)
        self.visual_pixels = np.column_stack((flat_pixels // 64, flat_pixels % 64)).astype(np.uint8)
        self.forward = np.arange(3600, 3660, dtype=np.int32)
        self.turn_left = np.arange(3660, 3700, dtype=np.int32)
        self.turn_right = np.arange(3700, 3740, dtype=np.int32)
        self.jump_nodes = np.arange(3740, 3760, dtype=np.int32)
        relay = np.arange(1800, 2400, dtype=np.int32)
        fixture_pre = self.rng.choice(self.visual, 12000)
        fixture_post = self.rng.choice(relay, 12000)
        motor_pre = self.rng.choice(relay, 5000)
        motor_post = self.rng.choice(
            np.concatenate((self.forward, self.turn_left, self.turn_right, self.jump_nodes)), 5000
        )
        row = np.concatenate((row, fixture_post, motor_post))
        col = np.concatenate((col, fixture_pre, motor_pre))
        weight = np.concatenate(
            (weight, np.full(12000, 0.18, np.float32), np.full(5000, 0.22, np.float32))
        )
        self.w = sparse.csr_matrix((weight, (row, col)), shape=(self.n, self.n))
        phi = self.rng.uniform(0, 2 * np.pi, self.n)
        cost = self.rng.uniform(-1, 1, self.n)
        rad = np.sqrt(1 - cost * cost)
        self.positions = np.column_stack((rad * np.cos(phi), cost * 0.65, rad * np.sin(phi))).astype(np.float32)
        self.position_measured = np.zeros(self.n, dtype=bool)
        self.regions = (np.arange(self.n) % 8).astype(np.uint8)
        self.region_names = np.array([f"fixture group {i}" for i in range(8)])

    def _load_cache(self, cache: Path):
        meta = np.load(cache / "model.npz", allow_pickle=False)
        self.n = int(meta["n"])
        self.w = sparse.load_npz(cache / "weights.npz").astype(np.float32)
        for name in ("visual", "forward", "turn_left", "turn_right", "jump_nodes", "positions", "regions"):
            setattr(self, name, meta[name])
        self.region_names = meta["region_names"]
        self.position_measured = meta["position_measured"]
        if "visual_pixels" in meta:
            self.visual_pixels = meta["visual_pixels"]
        else:
            flat_pixels = np.linspace(0, 48 * 64 - 1, len(self.visual)).astype(np.int32)
            self.visual_pixels = np.column_stack((flat_pixels // 64, flat_pixels % 64)).astype(np.uint8)

    def _select_io_pools(self) -> None:
        """Phase 3: pick 20-neuron strike (B) and crouch (Z) decode pools.

        flyGNN low-dimensional-readout principle: the connectome is frozen, so
        new motor channels come from *choosing* readout populations, not from
        training weights.  Selection is deterministic (fixed seed) so the
        BRAIN_VERSION invariants and replay stay reproducible.
        """
        if getattr(self, "n", 0) <= 4096:      # demo fixture: reserved range
            self.strike_nodes = np.arange(3760, 3780, dtype=np.int32)
            self.crouch_nodes = np.arange(3780, 3800, dtype=np.int32)
            return
        used = np.concatenate((self.visual, self.forward, self.turn_left,
                               self.turn_right, self.jump_nodes))
        candidates = np.setdiff1d(np.arange(self.n, dtype=np.int32), used)
        # Rank by out-degree (evolved wiring: well-connected neurons make
        # informative readouts) and take the top 40 deterministically.
        out_degree = np.diff(self.w.indptr)          # CSR: row nnz counts
        order = np.lexsort((candidates, -out_degree[candidates]))
        chosen = candidates[order[:40]]
        self.strike_nodes = np.sort(chosen[:20]).astype(np.int32)
        self.crouch_nodes = np.sort(chosen[20:]).astype(np.int32)

    def set_cpg_gate(self, strike: float = 0.0, crouch: float = 0.0) -> None:
        """CPG gate -> LIF current injection (Phase 3 interface, no bypass).

        The cascade never writes control.b/z directly from Python for neural
        intent; it raises these gates, the pools fire, and the standard
        decode path turns rates into buttons (P1 PIN compliant).
        """
        self._cpg_gate_strike = float(np.clip(strike, 0.0, 1.0))
        self._cpg_gate_crouch = float(np.clip(crouch, 0.0, 1.0))

    def add_primitive_outcome(self, primitive: str, success: bool) -> None:
        """Dopamine pulse on CPG primitive success/failure -> MBON plasticity.

        MBON columns 5..8 (punch/dive/groundpound/longjump) learn which
        contexts pay off for each primitive (Bennett-style RPE shaping).

        M3.2 fix: a success pulse sets ``_success_pulse_floor`` so the
        completion tick's total dopamine is floored at +0.2 — concurrent
        behavioral setbacks (ramp/door) were swamping the +0.6 one-shot and
        netting the tick negative, suppressing the very association the
        primitive column needs to learn.
        """
        if success:
            self._pending_dopamine += 0.6    # rewarding pulse
            self._success_pulse_floor = 0.2
        else:
            self.add_setback(0.4)            # aversive pulse
        self._last_primitive_outcome = (primitive, bool(success))

    def encode_retina(self, rgb: np.ndarray, heading: float = 0.0) -> np.ndarray:
        frame = self.retina.sample(rgb)
        lum = frame @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        prev_lum = self.previous_rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        temporal = np.abs(lum - prev_lum)
        color = np.maximum(frame[..., 1] - 0.5 * (frame[..., 0] + frame[..., 2]), 0)
        # ---- Color-enhanced drive ----
        # Original components
        drive_lum = 0.45 * lum
        drive_temp = 1.6 * temporal
        # Color-salient components
        # Red salience: objects with R >> G (enemies, switches, mushrooms)
        red_sal = np.maximum(frame[..., 0] - frame[..., 1], 0)
        # UV salience: sky/water rich in short wavelengths
        uv_sal = np.maximum(frame[..., 2] - 0.5 * (frame[..., 0] + frame[..., 1]), 0)
        # Green boost (existing color term, preserved)
        green_sal = np.maximum(frame[..., 1] - 0.5 * (frame[..., 0] + frame[..., 2]), 0)
        drive_color = (
            0.15 * red_sal +
            0.10 * uv_sal +
            0.25 * green_sal       # original color term, kept
        )
        drive = np.clip(drive_lum + drive_temp + drive_color, 0, 1)
        self.previous_rgb = frame
        self.mean_luminance = float(lum.mean())
        self.temporal_energy = float(temporal.mean())
        # --- Local motion detection: external moving objects when Mario is still ---
        # Self-motion produces global temporal energy; when stationary (low heading
        # rate), residual temporal energy must come from external moving objects.
        self_motion_est = abs(self.heading_rate) * 0.5
        self.local_motion_energy = max(0.0, self.temporal_energy - self_motion_est)
        self.local_motion_detected = self.local_motion_energy > 0.30
        # --- Dialogue box detection: lower visual field suddenly covered by a
        # large uniform block — DUAL ZONE: SM64 places standard dialogue at the
        # BOTTOM (key-sign at top). Detect dark+uniform+drop in either half.
        def _zone_state(region, prev_attr, frames_attr):
            lum = float(region[..., 1].mean()) if region.ndim == 3 else float(region.mean())
            var = float(region[..., 1].var()) if region.ndim == 3 else 0.0
            prev = getattr(self, prev_attr, lum)
            setattr(self, prev_attr, lum)
            drop = (prev - lum) > 0.12
            dark = lum < 0.30 and var < 0.08
            frames = getattr(self, frames_attr, 0)
            if dark and (frames > 0 or drop):
                frames += 1
            else:
                frames = 0
            setattr(self, frames_attr, frames)
            return dark and frames >= 12

        half = frame.shape[0] // 2
        _lower = frame[half:, ...]
        _upper = frame[:half, ...]
        lo_hit = _zone_state(_lower, "_prev_lower_lum", "_dialogue_frames_lo")
        hi_hit = _zone_state(_upper, "_prev_upper_lum", "_dialogue_frames_hi")
        self._dialogue_total = getattr(self, "_dialogue_total", 0.0)
        if lo_hit or hi_hit:
            self._dialogue_total += self.dt
        else:
            self._dialogue_total = 0.0
        self.dialogue_active = ((lo_hit or hi_hit)
                                and self._dialogue_total < 20.0)
        # --- Optic flow signals ---
        flow = self.retina.compute_flow(rgb)
        self.tau = float(flow.get("tau", float("inf")))
        self.flow_asymmetry = float(flow["left_right_asymmetry"])  # RAW (backward compat)
        self.flow_looming = float(flow["center_expansion"])
        self.flow_cliff = float(flow["lower_field_green"])
        self.terrain = str(flow.get("terrain", "mixed"))
        # Underwater/void: below ground + strong blue dominance in view
        self.blue_dom = float(flow.get("blue_dom", 0.0))
        self.underwater = bool(self.terrain == "water"
                               or (self.blue_dom > 0.25))
        self.wall_score = float(flow.get("wall_score", 0.0))
        self.ramp_score = float(flow.get("ramp_score", 0.0))
        self.opening_score = float(flow.get("opening_score", 0.0))
        self.sky_score = float(flow.get("sky_score", 0.0))
        self.enclosure_score = float(flow.get("enclosure_score", 0.0))
        self.ground_angle = float(flow.get("ground_angle", 0.7))
        self.door_frame_score = float(flow.get("door_frame_score", 0.0))
        self.opening_asymmetry = float(flow.get("opening_asymmetry", 0.0))
        # --- Interactive object proximity: isolated vertical structure being
        # approached (door/sign frame, or lone vertical edge without a wall) ---
        self.interactive_near = (
            (self.door_frame_score > 0.5
             or (float(flow.get("edge_90", 0.0)) > 0.15 and self.wall_score < 0.3))
            and self.tau != float("inf") and self.tau < 2.0
        )
        self.opening_width = float(flow.get("opening_width", 0.0))

        # ---- HRC (T4/T5) direction-selective motion signals (EVO R7) ----
        # hrc_asymmetry is motion-truth from the Hassenstein-Reichardt
        # correlator (sign-matched with flow_asymmetry).  Raw values kept on
        # the model; self-motion separation applied below.
        self.hrc_asymmetry = float(flow.get("hrc_asymmetry", 0.0))
        self.hrc_right = float(flow.get("hrc_right", 0.0))
        self.hrc_left = float(flow.get("hrc_left", 0.0))
        self.hrc_up = float(flow.get("hrc_up", 0.0))
        self.hrc_down = float(flow.get("hrc_down", 0.0))
        self.hrc_sector_looming = {
            k: float(v) for k, v in flow.items() if k.startswith("hrc_looming_az")}
        if "hrc_asymmetry" in flow:
            self._hrc_frames = getattr(self, "_hrc_frames", 0) + 1

        # ---- Self-motion separation ----
        # Subtract turning-induced visual motion from the raw asymmetry to
        # obtain true_asymmetry (world motion only).  When Mario turns
        # (positive heading_rate = turning right), the world sweeps leftward
        # across the retina, injecting a bias into the raw left-right
        # asymmetry.  We estimate this component as  SELF_MOTION_K * heading_rate
        # and remove it.
        self.prev_heading = self.heading
        self.heading = heading
        self.heading_rate = (self.heading - self.prev_heading) / self.dt
        correction = self.SELF_MOTION_K * self.heading_rate
        true_asym = max(-1.0, min(1.0, self.flow_asymmetry - correction))
        # Same separation applied to the HRC motion-truth asymmetry.
        true_hrc_asym = max(-1.0, min(1.0, self.hrc_asymmetry - correction))
        self._self_motion_cache = {
            "heading_rate": round(self.heading_rate, 4),
            "true_asymmetry": round(true_asym, 4),
            "true_hrc_asymmetry": round(true_hrc_asym, 4),
            "k": self.SELF_MOTION_K,
        }

        # --- Multi-channel retina signals (extracted from compute_flow) ---
        self.on_energy = float(flow.get("on_raw", 0.0))
        self.off_energy = float(flow.get("off_raw", 0.0))
        self.sustained_energy = float(flow.get("sustained_raw", 0.0))
        self.edge_0 = float(flow.get("edge_0", 0.0))
        self.edge_45 = float(flow.get("edge_45", 0.0))
        self.edge_90 = float(flow.get("edge_90", 0.0))
        self.edge_135 = float(flow.get("edge_135", 0.0))

        # ---- 4-direction EMD signals ----
        self.emd_on_right = float(flow.get("emd_on_right", 0.0))
        self.emd_on_left = float(flow.get("emd_on_left", 0.0))
        self.emd_on_down = float(flow.get("emd_on_down", 0.0))
        self.emd_on_up = float(flow.get("emd_on_up", 0.0))
        self.emd_off_right = float(flow.get("emd_off_right", 0.0))
        self.emd_off_left = float(flow.get("emd_off_left", 0.0))
        self.emd_off_down = float(flow.get("emd_off_down", 0.0))
        self.emd_off_up = float(flow.get("emd_off_up", 0.0))
        self.emd_on_total = float(flow.get("emd_on_total", 0.0))
        self.emd_off_total = float(flow.get("emd_off_total", 0.0))

        # ---- Color channel signals ----
        self.sky_blue_index = float(flow.get("sky_blue_index", 0.0))
        self.danger_red_index = float(flow.get("danger_red_index", 0.0))
        self.color_contrast = float(flow.get("color_contrast", 0.0))
        self.rg_opponent_mean = float(flow.get("rg_opponent_mean", 0.0))
        self.by_opponent_mean = float(flow.get("by_opponent_mean", 0.0))
        self.uv_appx_mean = float(flow.get("uv_appx_mean", 0.0))
        self.saturation_mean = float(flow.get("saturation_mean", 0.0))
        self.color_azimuth = {k: v for k, v in flow.items() if k.startswith("hue_az")}

        # ---- Derived compound EMD signals ----
        eps = 1e-8
        self.emd_horizontal = (
            self.emd_on_right + self.emd_on_left +
            self.emd_off_right + self.emd_off_left
        )
        self.emd_vertical = (
            self.emd_on_up + self.emd_on_down +
            self.emd_off_up + self.emd_off_down
        )
        _lat_denom = self.emd_horizontal + eps
        self.emd_net_lateral = (
            (self.emd_on_right + self.emd_off_right) -
            (self.emd_on_left + self.emd_off_left)
        ) / _lat_denom
        _vert_denom = self.emd_vertical + eps
        self.emd_net_vertical = (
            (self.emd_on_down + self.emd_off_down) -
            (self.emd_on_up + self.emd_off_up)
        ) / _vert_denom

        # ---- Small target tracking signals (LPLC/LC11 equivalent) ----
        self.target_count = int(flow.get("target_count", 0))
        self.fg_fraction = float(flow.get("fg_fraction", 0.0))
        self.max_target_energy = float(flow.get("max_target_energy", 0.0))

        # Self-motion gating: suppress target detection during fast turns
        _heading_rate_mag = abs(getattr(self, "heading_rate", 0.0))
        if _heading_rate_mag > 1.0:
            self.fg_fraction *= 0.3

        # Update tracker with detections
        detections = flow.get("target_centroids", [])
        sizes = flow.get("target_sizes", [])
        directions = flow.get("target_directions", [])
        tracks = self.target_tracker.update(detections, sizes, directions)

        # Find nearest approaching target
        nearest = self.target_tracker.nearest_approaching_target()
        if nearest is not None:
            self.target_approaching = True
            self.target_intercept_time = nearest.time_to_intercept
            self.target_nearest_centroid = nearest.centroid
            self.target_nearest_velocity = nearest.velocity
        else:
            self.target_approaching = False
            self.target_intercept_time = float("inf")

        # --- Multi-frame cliff history ---
        self._cliff_history.append(self.flow_cliff)

        # --- Visual short-term memory (scene change detection) ---
        drive_mean = float(drive.mean())
        scene_state = self.scene_memory.update(drive_mean)
        self.scene_mean = scene_state["scene_mean"]
        self.scene_var = scene_state["scene_var"]
        self.scene_change = scene_state["scene_change"]
        self.scene_change_rate = scene_state["scene_change_rate"]

        # ---- Scene signature: random projection of 1536-dim retina drive ----
        # Color-enhanced signature (5-channel) when color_signature flag is True
        if getattr(self, "color_signature", False):
            # Build 5-channel input: drive, red_sal, uv_sal, green_sal, mean RGB
            color_input = np.column_stack([
                drive,                         # luminance drive (existing)
                red_sal,                       # red salience
                uv_sal,                        # UV salience
                green_sal,                     # green salience
                frame.mean(axis=1),            # mean RGB (neutral)
            ])  # (N, 5)
            self.scene_sig = (self.color_projection @ color_input.ravel()).astype(np.float32)
        else:
            # Original single-channel projection for backward compat
            self.scene_sig = (self.projection @ drive).astype(np.float32)
        norm = float(np.linalg.norm(self.scene_sig))
        if norm > 1e-8:
            self.scene_sig /= norm  # L2-normalize to unit length
        self.scene_sig_valid = True

        # ---- Mushroom Body encoding ----
        if self.scene_sig_valid and hasattr(self, "mushroom"):
            try:
                self.mushroom.encode(self.scene_sig)
            except Exception:
                pass  # graceful degradation

        return drive

    @property
    def cliff_history(self) -> list:
        """Last 10 lower_field_green values (oldest first)."""
        return list(self._cliff_history)

    @property
    def cliff_confirmed(self) -> bool:
        """True when CLIFF_CONFIRM_FRAMES out of last 10 frames are below CLIFF_THRESHOLD."""
        if len(self._cliff_history) < self.CLIFF_CONFIRM_FRAMES:
            return False
        below = sum(1 for v in self._cliff_history if v < self.CLIFF_THRESHOLD)
        return below >= self.CLIFF_CONFIRM_FRAMES

    @property
    def cliff_rate(self) -> float:
        """Rate of change of lower_field_green over the last 5 frames (per frame).
        Negative means green is dropping (approaching edge)."""
        if len(self._cliff_history) < 5:
            return 0.0
        recent = list(self._cliff_history)[-5:]
        return (recent[-1] - recent[0]) / max(len(recent) - 1, 1)

    @property
    def self_motion(self) -> dict:
        """Self-motion separation state.

        Returns a dict with:
            heading_rate (float) — angular velocity in rad/s
            true_asymmetry (float) — self-motion corrected flow asymmetry (-1..1)
            k (float) — scale factor applied to heading_rate
        """
        return self._self_motion_cache

    @property
    def true_asymmetry(self) -> float:
        """Self-motion corrected flow asymmetry (world motion only), in [-1, 1].
        
        Raw flow_asymmetry minus the estimated self-motion component
        (SELF_MOTION_K * heading_rate).  When Mario is not turning this
        equals the raw asymmetry.
        """
        return self._self_motion_cache.get("true_asymmetry", self.flow_asymmetry)

    @property
    def true_hrc_asymmetry(self) -> float:
        """Self-motion corrected HRC (motion-truth) asymmetry, in [-1, 1].

        Raw hrc_asymmetry minus the same SELF_MOTION_K * heading_rate
        component used for flow.  Falls back to the raw HRC value (which is
        0.0) before the correlator has produced any output.
        """
        return self._self_motion_cache.get("true_hrc_asymmetry",
                                           getattr(self, "hrc_asymmetry", 0.0))

    @property
    def hrc_available(self) -> bool:
        """True once the HRC correlator is warmed up (>= 2 retina frames).

        The first compute_hrc call has no previous-frame cell luminance, so
        its output is all zeros; only after a second frame do the signed
        correlations become meaningful motion truth.
        """
        return getattr(self, "_hrc_frames", 0) >= 2

    @property
    def scene_signature(self) -> np.ndarray:
        """128-dim L2-normalised scene signature from random projection of retina drive.

        This is a compressed, viewpoint-invariant fingerprint of the current
        visual scene, suitable for cosine-similarity matching against known
        scenes in the landmark memory database.
        """
        return self.scene_sig

    def reset_scene(self) -> None:
        """Clear the scene memory buffer and reset statistics.

        Call this when switching to a completely new visual environment
        to avoid false scene-change signals from the previous scene's
        statistics.
        """
        self.scene_memory.reset()
        self.scene_mean = 0.0
        self.scene_var = 0.0
        self.scene_change = False
        self.scene_change_rate = 0.0
        self.scene_sig[:] = 0.0
        self.scene_sig_valid = False
        self.target_tracker.reset()
        self._turn_adapt.reset()
        self.cliff_standoff_s = 0.0
        self.cliff_tangent_bias = 0.0
        self.loop_score = 0.0
        self.scene_danger = 0.0
        if hasattr(self, "mushroom"):
            try:
                self.mushroom.reset()
            except Exception:
                pass
        if hasattr(self, "cx"):
            try:
                self.cx.reset()
            except Exception:
                pass

    # ---- Python→neuron error gradient bridge (t3) ----

    def compute_error_gradient(self, python_turn_x: int) -> dict:
        """Compare Python escape turn decision with neural network's preferred bias.

        The 'neural bias' is the decoded turn preference from the motor pool
        rolling-window firing rates (right_rate − left_rate, in [-1, 1]).

        Parameters
        ----------
        python_turn_x : int
            The Python escape turn direction (positive = right, negative = left).

        Returns
        -------
        dict with keys:
            error           — signed error in [-1, 1] (positive = Python wants
                              more right-turn than the network)
            neural_bias     — the network's turn bias in [-1, 1]
            python_bias     — signed Python turn direction in [-1, 1]
            corrective_left — current to inject into turn_left pool
            corrective_right — current to inject into turn_right pool
        """
        # Neural bias from the decoded motor firing rates
        neural_bias = getattr(self, "turn_rate", 0.0)  # right_rate − left_rate

        # Python's intended turn direction, normalised to [-1, 1]
        if abs(python_turn_x) > 8:
            python_bias = np.clip(python_turn_x / 70.0, -1.0, 1.0)
        else:
            python_bias = 0.0

        # Error = what Python wants − what the network provided
        error = python_bias - neural_bias

        # Corrective currents: amplify the under-performing motor pool,
        # suppress the over-performing one.  Magnitude decays as |error| shrinks.
        amp = min(0.06, abs(error) * 0.08)  # max 0.06 per tick
        if error > 0:  # Python wants MORE right / LESS left
            corrective_left = -amp * 0.6   # suppress left
            corrective_right = amp         # boost right
        elif error < 0:  # Python wants MORE left / LESS right
            corrective_right = -amp * 0.6  # suppress right
            corrective_left = amp          # boost left
        else:
            corrective_left = 0.0
            corrective_right = 0.0

        result = {
            "error": round(error, 4),
            "neural_bias": round(neural_bias, 4),
            "python_bias": round(python_bias, 4),
            "corrective_left": round(corrective_left, 4),
            "corrective_right": round(corrective_right, 4),
        }
        # Store for telemetry / flow.json exposure
        self._last_error_gradient = result
        return result

    def inject_corrective_current(self, error_dict: dict,
                                   reward_signal: float = 0.0) -> None:
        """Inject error-signed corrective currents into turn motor pools.

        Currents are gated by the reward signal — correction is strongest when
        the reward is low/negative (the network's decision led to a poor
        outcome).  High reward means the network is doing well and corrections
        are suppressed.

        Parameters
        ----------
        error_dict : dict
            Output of compute_error_gradient().
        reward_signal : float
            Current reward signal from t1 (positive = good outcome).
        """
        # Gate: only correct when reward is low/negative (needs improvement)
        gate = 1.0 if reward_signal < 0.3 else max(0.0, 1.0 - reward_signal)
        if gate < 0.01:
            return

        cl = error_dict.get("corrective_left", 0.0) * gate
        cr = error_dict.get("corrective_right", 0.0) * gate
        if abs(cl) < 1e-6 and abs(cr) < 1e-6:
            return

        self.v[self.turn_left] += cl
        self.v[self.turn_right] += cr
        self._corrective_current_applied = (cl, cr)

    def set_python_correction(self, python_turn_x: int,
                              reward_signal: float = 0.0) -> dict:
        """One-call convenience: compute error gradient and enqueue injection.

        Called from main.py after the Python escape logic has made a decision.
        The computed error is stored and will be applied as corrective current
        on the *next* call to step().

        Parameters
        ----------
        python_turn_x : int
            The Python escape turn direction (positive = right, negative = left).
        reward_signal : float
            Current reward signal for gating.

        Returns
        -------
        dict
            The error gradient dict (for telemetry / flow.json).
        """
        error_dict = self.compute_error_gradient(python_turn_x)
        self._pending_python_turn = python_turn_x
        # Gate and inject immediately into the current voltage state
        self.inject_corrective_current(error_dict, reward_signal)
        return error_dict

    def report_movement(self, displacement: float, expected: float = 40.0) -> None:
        """EVO R11: displacement-based dopamine feedback for the mushroom body.

        main.py feeds observed net displacement (game units over the last
        ~2.4 s burst window).  Moving ≈ reward, being stuck ≈ punishment:
        the MB depresses KC→MBON synapses for scene/action contexts that keep
        producing zero displacement — the network learns to stop choosing
        'face the wall' without any new Python branch.
        """
        self.movement_reward = max(-1.0, min(1.0, displacement / max(expected, 1e-6) - 0.25))
        # Blend into the reward signal consumed by the existing dopamine sum.
        self.reward_signal = max(-1.0, min(1.0,
            self.reward_signal * 0.5 + self.movement_reward * 0.5))

    def add_setback(self, strength: float = 0.6) -> None:
        """EVO R13: external setback discovered by supervision (e.g. dialogue
        interaction blocked, locked door) → negative dopamine pulse consumed
        by the mushroom body at the next tick, teaching the KC→MBON pathway
        that THIS scene context carries negative value (PPL1-like)."""
        self._pending_dopamine = max(-1.0, self._pending_dopamine - abs(strength))

    # ── DAN signal shaping (EVO R18) ─────────────────────────────────────
    # Explicit, single-place dopamine weights.  The exploration reward was
    # lowered 0.50 → 0.30 (EVO R18), then 0.30 → 0.20 (P0-2): persistent
    # +dopamine kept re-inflating the forward MBON column into tanh saturation
    # against the homeostatic scaling — the equilibrium now sits deeper inside
    # the responsive range.
    DAN_REWARD_EXPLORATION = 0.20   # scene novelty (scene_change_rate > 0.1)
    DAN_REWARD_PROGRESS = 0.30      # sustained forward movement
    DAN_PUNISH_STUCK = 0.30         # per-5s stuck (capped)
    DAN_PUNISH_FALLEN = 0.80
    DAN_PUNISH_CLIFF = 0.40
    DAN_PUNISH_LOOMING = 0.30
    DAN_PUNISH_REVISIT = 0.20
    DAN_PUNISH_LOOP_STATES = 0.35   # micro_loop / stuck_ramp / wall_stuck / oscillating
    DAN_PUNISH_STANDOFF = 0.45      # cliff-edge standoff > 20s

    def restlessness_level(self) -> float:
        """EVO R19: escape-motivation build-up in [0, 1].

        Driven by cliff-edge standoff time and loop pressure — the
        motivational current that converts standoff/weave stillness into
        forward displacement (biological: escape motivation builds with
        entrapment time).
        """
        loop_pressure = max(0.0, (self.loop_score - 0.8) * 5.0)
        standoff = min(1.0, self.cliff_standoff_s / 30.0)
        return min(1.0, max(standoff, loop_pressure))

    def _compute_dopamine(self) -> float:
        """Compute the dopaminergic-neuron (DAN) signal.

        Weights are the class-level ``DAN_*`` shaping constants — tune the
        DA system in one place without touching the detection logic.
        """
        reward = 0.0
        punishment = 0.0
        # Positive: scene novelty
        if self.scene_change_rate > 0.1:
            reward = max(reward, self.DAN_REWARD_EXPLORATION)
        # Positive: forward progress
        fwd = getattr(self, "filtered_y", 0.0)
        if fwd > 20.0:
            reward = max(reward, self.DAN_REWARD_PROGRESS)
        # Negative: stuck
        if getattr(self, "stuck_duration", 0.0) > 5.0:
            punishment = max(punishment, min(self.DAN_PUNISH_STUCK,
                                             self.stuck_duration / 50.0))
        # Negative: fallen
        if getattr(self, "fallen", False):
            punishment = max(punishment, self.DAN_PUNISH_FALLEN)
        # Negative: cliff
        if getattr(self, "cliff_confirmed", False):
            punishment = max(punishment, self.DAN_PUNISH_CLIFF)
        # Negative: looming
        if self.tau < 1.0 and np.isfinite(self.tau):
            punishment = max(punishment, self.DAN_PUNISH_LOOMING)
        # Negative: revisit
        revisit = getattr(self, "_revisit_penalty", 0.0)
        if revisit > 0.5:
            punishment = max(punishment, self.DAN_PUNISH_REVISIT)
        # EVO R14 · Negative: circling-family anomaly states.  This is the
        # dopaminergic-neuron (DAN) input for loop suppression — the mushroom
        # body's three-factor rule then weakens the scene→turn associations
        # that produced the loop.  Detection lives in the memory controller
        # (mirrored here each tick); the LEARNING is purely neural.
        if getattr(self, "anomaly_state_name", "idle") in (
                "micro_loop", "stuck_ramp", "wall_stuck", "oscillating"):
            punishment = max(punishment, self.DAN_PUNISH_LOOP_STATES)
        # EVO R15 · Negative: cliff-edge standoff (>20s parked at the edge).
        # Teaches the mushroom body "this scene + forward → bad", biasing
        # subsequent MBON output toward lateral exploration.
        if getattr(self, "cliff_standoff_s", 0.0) > 20.0:
            punishment = max(punishment, self.DAN_PUNISH_STANDOFF)
        return reward - punishment

    def step(self, rgb: np.ndarray, now: float | None = None,
             novelty: float = 0.5, heading: float = 0.0) -> tuple[Control, np.ndarray]:
        now = self.step_count * self.dt if now is None else now
        sensory = self.encode_retina(rgb, heading=heading)

        # Novelty-driven visual modulation:
        # Low novelty (familiar) → boost sensory to seek variety
        # High novelty (unexplored) → slight suppression for caution
        # B10 (P1): piecewise branches replaced by a smooth sigmoid — same
        # ±0.10 range, no discontinuities at the old 0.3 / 0.7 breakpoints.
        novelty_gain = 1.0 + 0.10 * float(np.tanh((0.5 - novelty) * 4.0))

        # ---- Reward signal from stuck_duration changes (for gain modulation) ----
        # When stuck_duration drops significantly (escape succeeded) → reward=+1
        # When stuck increases → reward=-0.1; when fallen → reward=-0.5
        _prev_stuck = self._prev_stuck_duration
        _cur_stuck = getattr(self, "stuck_duration", 0.0)
        self._prev_stuck_duration = _cur_stuck
        if _prev_stuck > 5.0 and _cur_stuck < _prev_stuck * 0.3:
            self.reward_signal = 1.0  # escaped!
        elif _cur_stuck > _prev_stuck + 5.0:
            self.reward_signal = -0.1  # getting more stuck
        elif getattr(self, "fallen", False):
            self.reward_signal = -0.5  # fallen
        else:
            self.reward_signal *= 0.95  # decay toward zero
        self._cumulative_reward = 0.99 * self._cumulative_reward + self.reward_signal

        # ---- Per-pool gain update based on active motor command ----
        # When reward arrives, increase gain of the motor pool that was active.
        if abs(self.reward_signal) > 0.05:
            if float(self.spikes[self.forward].mean()) > 0.01:
                self.dopamine_gain.pathway_eligibility["forward"] = min(
                    1.0, self.dopamine_gain.pathway_eligibility["forward"] + 0.3)
            if float(self.spikes[self._turn_all].mean()) > 0.01:
                self.dopamine_gain.pathway_eligibility["turn"] = min(
                    1.0, self.dopamine_gain.pathway_eligibility["turn"] + 0.3)
            if float(self.spikes[self.jump_nodes].mean()) > 0.01:
                self.dopamine_gain.pathway_eligibility["jump"] = min(
                    1.0, self.dopamine_gain.pathway_eligibility["jump"] + 0.3)

        # ---- Dopamine signal and Mushroom Body plasticity ----
        # Combine the existing behavioral dopamine with the t1 reward_signal
        # (stuck_duration-based escape success/failure signal) so that the
        # mushroom body learns from both scene-driven and escape-driven signals.
        _behavioral_dop = self._compute_dopamine()
        _reward_contrib = max(-0.3, min(0.5, self.reward_signal)) * 0.4
        # EVO R13: external setback pulses (dialogue blocked, locked door …)
        # join the dopamine sum — one-shot, consumed after this tick.
        _pending = getattr(self, "_pending_dopamine", 0.0)
        dop = max(-1.0, min(1.0, _behavioral_dop + _reward_contrib + _pending))
        self._pending_dopamine = 0.0
        # M3.2 fix: a primitive success this tick floors the total dopamine —
        # the completion must never be learned as negative just because a
        # behavioral setback coincided with it.
        if getattr(self, "_success_pulse_floor", 0.0) > 0.0:
            dop = max(dop, self._success_pulse_floor)
            self._success_pulse_floor = 0.0
        try:
            self.mushroom.set_dopamine(dop)
            n_syn = self.mushroom.update_weights()
        except Exception:
            n_syn = 0  # graceful degradation if mushroom unavailable

        # ---- Dopamine-gated gain modulation (plasticity proxy) ----
        # Feed the same dopamine signal to the gain controller for
        # pathway-specific gain updates.  Track pathway activity from the
        # current (pre-reset) spike vector for eligibility computation.
        self.dopamine_gain.set_dopamine(dop)
        pathway_activity = {
            "visual": float(self.spikes[self.visual].mean()),
            "forward": float(self.spikes[self.forward].mean()),
            "turn": float(self.spikes[self._turn_all].mean()),
            "jump": float(self.spikes[self.jump_nodes].mean()),
        }
        # All other neurons are "recurrent" (interneurons)
        _other_mask = np.ones(self.n, dtype=bool)
        _other_mask[self.visual] = False
        _other_mask[self.motor_nodes] = False
        pathway_activity["recurrent"] = float(self.spikes[_other_mask].mean())
        self.dopamine_gain.update_eligibility(pathway_activity)
        n_gain = self.dopamine_gain.apply_gain_update()

        # ---- MBON-to-motor current injection ----
        try:
            mbon = self.mushroom.mbon_outputs
            self.v[self.forward] += mbon[0] * self.mbon_gain_forward
            self.v[self.turn_left] += mbon[1] * self.mbon_gain_turn
            self.v[self.turn_right] += mbon[2] * self.mbon_gain_turn
            self.v[self.jump_nodes] += mbon[3] * self.mbon_gain_jump
            # Phase 3: primitive columns shape the strike/crouch pools.
            if len(self.strike_nodes):
                self.v[self.strike_nodes] += 0.4 * (mbon[5] + mbon[6])
            if len(self.crouch_nodes):
                self.v[self.crouch_nodes] += 0.4 * (mbon[7] + mbon[8])
            if mbon[4] > 0.2:
                self.escape_current = min(0.25, self.escape_current * 1.02)
            elif mbon[4] < -0.2:
                self.escape_current = max(0.05, self.escape_current * 0.98)

            # ---- Consolidated memory recall (t7) ----
            # If the current scene matches a consolidated (important) memory,
            # replay its associated MBON outputs as an additional bias.  This
            # increases MB utilisation by providing a direct memory-to-behaviour
            # pathway independent of the plastic weight matrix.
            _recalled = self.mushroom.recall()
            if _recalled is not None:
                self.v[self.forward] += _recalled[0] * self.mbon_gain_forward * 0.5
                self.v[self.turn_left] += _recalled[1] * self.mbon_gain_turn * 0.5
                self.v[self.turn_right] += _recalled[2] * self.mbon_gain_turn * 0.5
                self.v[self.jump_nodes] += _recalled[3] * self.mbon_gain_jump * 0.5

            # ---- Scene familiarity modulation (t7) ----
            # Familiar scenes (high familiarity) → reduce escape tendency
            # (the agent is in known territory).  Novel scenes (low familiarity)
            # → slight increase in exploratory escape tendency.
            _familiarity = self.mushroom.familiarity
            if _familiarity > 0.5:
                self.escape_current *= 0.90  # calm in familiar territory
            elif _familiarity < 0.1 and novelty < 0.5:
                self.escape_current = min(0.25, self.escape_current * 1.05)
        except Exception:
            pass  # graceful degradation if mushroom body unavailable

        # ---- Synaptic propagation (P1-2) ----
        # Adaptive selection helper.  MEASURED NEGATIVE RESULT (2026-09-16,
        # interleaved medians on the real connectome): boolean-mask vs
        # fancy-index vs gather+bincount all land within load noise
        # (0.95-1.38x) — the cost is inherent memory traffic over the
        # selected nnz.  Real options: dense-core split, GPU batch, or edge
        # reduction.  Do NOT retry selection-path tweaks.
        current = synaptic_current(self.w, self.spikes)
        # Pathway-specific gain modulation (plasticity proxy)
        # Instead of one scalar, each pathway gets its own gain from the
        # dopamine-gated controller — this mimics plasticity without
        # modifying the fixed connectome weights self.w.
        self._pathway_gains_np[0] = self.dopamine_gain.get_gain("visual")
        self._pathway_gains_np[1] = self.dopamine_gain.get_gain("forward")
        self._pathway_gains_np[2] = self.dopamine_gain.get_gain("turn")
        self._pathway_gains_np[3] = self.dopamine_gain.get_gain("jump")
        self._pathway_gains_np[4] = self.dopamine_gain.get_gain("recurrent")
        current *= self._pathway_gains_np[self._pathway_idx_map]

        # ---- Passive propagation enhancement: synaptic current buffer ----
        # Accumulate synaptic current with a slower decay, modelling temporal
        # integration of post-synaptic potentials (passive cable spread) and
        # neurotransmitter persistence.  Improves LIF neuron utilisation by
        # allowing signals to propagate through deeper network layers without
        # task-specific shunting.
        self._synaptic_buf = (
            self._synaptic_buf * self.synaptic_buf_decay + current
        )

        # ---- Adaptive global OU noise (replaces sparse Bernoulli kicks) ----
        # Continuous correlated subthreshold fluctuations improve utilisation
        # of every neuron in the connectome, not just motor populations.
        # Optimised: only fully update neurons that are recently active
        # (spikes or membrane potential > 0.5*threshold); inactive neurons
        # regress toward zero with minimal compute.
        dt = self.dt
        _active_noise = (self.spikes > 0) | (self.v > 0.5 * self.threshold)
        _n_active = int(_active_noise.sum())
        if _n_active > 0 and _n_active < self.n * 0.3:
            # Sparse update: only actively spiking/borderline neurons
            self.ou_global_state[_active_noise] += (
                self.ou_global_theta * (-self.ou_global_state[_active_noise]) * dt
                + self.ou_global_sigma * np.sqrt(dt)
                * self.rng.normal(size=_n_active).astype(np.float32)
            )
            # Inactive neurons slowly regress toward zero
            self.ou_global_state[~_active_noise] *= 0.999
        else:
            # Full update: many neurons are active, no shortcut benefit
            self.ou_global_state += (
                self.ou_global_theta * (-self.ou_global_state) * dt
                + self.ou_global_sigma * np.sqrt(dt)
                * self.rng.normal(size=self.n).astype(np.float32)
            )

        self.v *= np.exp(-self.dt / self.tau_m)
        self.v += self._synaptic_buf + self.ou_global_state * 0.22 + self.tonic_current
        if self.visual_connected:
            _vis_gain = self.dopamine_gain.get_gain("visual")
            self.v[self.visual] += sensory * 0.62 * novelty_gain * _vis_gain

        # Escape-mode depolarisation of motor neurons
        if self.escape_mode:
            self.v[self.motor_nodes] += self.escape_current
        # P1 (audit A3): fallen → jump-pool burst drive; forced bold breakout
        # → mirrored turn-pool current.  The LIF competition — not a Python
        # control write — executes the escape manoeuvre.
        if self.escape_jump_drive:
            self.v[self.jump_nodes] += self.ESCAPE_JUMP_DRIVE
            # EVO R32: time-share fallen forward with steering.  Constant
            # forward current suppresses turn-pool competition (counterfactual
            # report #1: |x| -95% at 2.5x amplitude — pushing harder straight
            # into the void).  Forward duty-cycle phase lets spontaneous
            # alternation / CX steering express between bursts.
            _phase_len = 25  # 0.5s per phase at 50Hz
            _duty = float(getattr(self, "_fallen_share_forward", 0.5))
            _cycle = max(1, int(round(1.0 / max(_duty, 0.05))))
            _forward_phase = (self.step_count // _phase_len) % _cycle == 0
            if _forward_phase:
                self.v[self.forward] += self._fallen_forward
        if self.bold_turn_drive:
            if self.bold_turn_drive > 0:
                self.v[self.turn_right] += self.BOLD_TURN_DRIVE * min(1.0, self.bold_turn_drive)
            else:
                self.v[self.turn_left] += self.BOLD_TURN_DRIVE * min(1.0, -self.bold_turn_drive)

        # P1 escape direction commit: choose a turn direction and hold it
        # for ~1s instead of alternating every tick, producing net displacement.
        if self.escape_mode:
            if self._escape_commit_timer <= 0:
                # Pick a direction and commit
                self._escape_commit_dir = 1 if self.rng.random() < 0.5 else -1
                self._escape_commit_timer = self._escape_commit_ticks
            else:
                self._escape_commit_timer -= 1
                # Reinforce committed direction, suppress opposite
                if self._escape_commit_dir > 0:
                    self.v[self.turn_right] += 0.15
                    self.v[self.turn_left] -= 0.10
                else:
                    self.v[self.turn_left] += 0.15
                    self.v[self.turn_right] -= 0.10
            # Adaptive forward gain: scale up when displacement is near-zero
            # to help break out of weave/circle patterns.
            _dx = getattr(self, "_last_disp_x", 0.0)
            _dz = getattr(self, "_last_disp_z", 0.0)
            _disp = (_dx ** 2 + _dz ** 2) ** 0.5
            if _disp < 0.5:
                self._escape_forward_accum = min(0.50, self._escape_forward_accum + 0.005)
            else:
                self._escape_forward_accum = max(0.15, self._escape_forward_accum - 0.01)
            self.v[self.forward] += self._escape_forward_accum

        # P4-1: Reflex→LIF bridge — convert reflex flags into current injection
        # so the LIF network (not Python control.x write) decides motor output.
        # Reflex turn/forward are moderate-strength biases; jump is a gate.
        if self.reflex_turn:
            if self.reflex_turn > 0:
                self.v[self.turn_right] += min(0.25, abs(self.reflex_turn) * 0.004)
            else:
                self.v[self.turn_left] += min(0.25, abs(self.reflex_turn) * 0.004)
        if self.reflex_forward:
            self.v[self.forward] += min(0.20, self.reflex_forward * 0.003)
        if self.reflex_jump:
            self.v[self.jump_nodes] += 0.30

        # ---- Tau (time-to-contact) → jump motor pool current injection ----
        # Imminent collision → depolarise jump nodes directly so the neural
        # network drives the jump response instead of Python escape logic.
        if self.tau < self.TAU_NEAR and np.isfinite(self.tau):
            _tau_inj = max(0.0, (self.TAU_NEAR - self.tau) / self.TAU_NEAR) * self.TAU_JUMP_INJECTION
            self.v[self.jump_nodes] += _tau_inj

        # ---- Small target tracking: approaching target → jump & turn injection (pre-spike) ----
        if self.target_approaching and self.target_intercept_time < 10.0:
            _frames_to_intercept = self.target_intercept_time
            if 2.0 < _frames_to_intercept < 6.0:
                _jump_strength = max(0.3, min(0.6, (6.0 - _frames_to_intercept) * 0.1))
                self.v[self.jump_nodes] += _jump_strength
            elif _frames_to_intercept <= 2.0:
                self.v[self.jump_nodes] += 0.50

            # Turn toward the approaching target
            _tgt_r, _tgt_c = self.target_nearest_centroid
            _lateral_bias = (_tgt_c - 32.0) / 32.0  # [-1, 1]
            if abs(_lateral_bias) > 0.15:
                self.v[self.turn_left] -= _lateral_bias * 0.12
                self.v[self.turn_right] += _lateral_bias * 0.12

        # ---- Sky_score → jump motor pool current injection ----
        # Open sky above signals a launch/escape opportunity; inject current
        # into jump motor nodes to bias toward an upward jump.
        if self.sky_score > 0.5:
            self.v[self.jump_nodes] += self.sky_score * 0.12

        # ---- Opening azimuth → steering pool current injection (EVO R11) ----
        # Directional openness drives the turn pools through the same current
        # pathway as every other sensory channel; the LIF left/right
        # competition — not a Python branch — decides which way to steer while
        # escaping.  This replaces the earlier random escape_x symbolic choice.
        if self.escape_mode and getattr(self, "opening_score", 0.0) > 0.2:
            _open_inj = (min(0.20, self.opening_score * 0.3)
                         * min(1.0, abs(self.opening_asymmetry) * 2.0))
            if self.opening_asymmetry > 0:      # opening toward the left field
                self.v[self.turn_left] += _open_inj
            elif self.opening_asymmetry < 0:    # opening toward the right field
                self.v[self.turn_right] += _open_inj

        # ---- Central Complex (CX) steering ----
        # The CX module maintains a heading compass, integrates optic flow,
        # tracks goal direction from novelty signals, and produces a unified
        # steering bias injected into turn motor pools.  Replaces the earlier
        # simple novelty-based turn bias with proper compass+goal steering.
        cx_bias = self.cx.update(
            heading=self.heading,
            heading_rate=self.heading_rate,
            flow_asymmetry=self.flow_asymmetry,
            novelty=novelty,
            novelty_direction=self.cx_novelty_direction,
            dt=self.dt,
            visual_azimuth=getattr(self, "visual_azimuth", None),
            forward_speed=getattr(self, "forward_units_per_tick", 0.0),
            goal_vectors=getattr(self, "cx_goal_vectors", None),
        )
        self.cx_bias = cx_bias  # EVO R28: mirror for reflex turn mix
        self.anchor_distance = self.cx.anchor_distance
        self.v[self.turn_left] += cx_bias * self.cx_steering_gain_turn
        self.v[self.turn_right] -= cx_bias * self.cx_steering_gain_turn

        # Navigation: exploration direction inertia — commit a direction and
        # hold it for ~5s to produce sustained movement instead of jittery
        # local exploration.  Only active outside escape mode.
        if not self.escape_mode:
            if self._explore_commit_timer <= 0:
                # Pick a new direction when commit expires
                self._explore_bias = (self.rng.random() - 0.5) * 1.5
                self._explore_commit_timer = self._explore_commit_ticks
            else:
                self._explore_commit_timer -= 1
            if abs(self._explore_bias) > 0.1:
                self.v[self.turn_right] += self._explore_bias * self._explore_commit_strength
                self.v[self.turn_left] -= self._explore_bias * self._explore_commit_strength

        # P1 (audit A8): the dialogue neural pulse block is deleted together
        # with the runner's legacy pulse-A fallback — dialogue behaviour is
        # owned by the LLM pause-wait orchestration plus the habituation
        # safety breaker in the runner (BRAIN 2.4.0 contract).
        # ---- CX interactive-mode gating ----
        # Interactive target near (door/sign) → CX enters interaction mode:
        # suppress escape circuitry current so the agent approaches, not flees.
        if getattr(self, "interactive_near", False) and not getattr(self, "dialogue_active", False):
            self.escape_current *= self.ESCAPE_CURRENT_SCALE
            self.v[self.forward] += 0.10          # gentle approach bias

        # EVO R14 · spontaneous alternation: turn-circuit fatigue counter-drive.
        # Sustained one-sided turning fatigues that circuit (TurnAdaptation)
        # and progressively recruits the competitor — pre-spike, so direction
        # selection stays inside the LIF network dynamics.
        _ad_l, _ad_r = self._turn_adapt.counter_drive()
        if _ad_l > 0.0:
            self.v[self.turn_right] += _ad_l      # left fatigue → drive right
        if _ad_r > 0.0:
            self.v[self.turn_left] += _ad_r       # right fatigue → drive left

        # EVO R16 · oscillation → forward breakthrough.  BOTH turn circuits
        # fatigued = the weave-in-place signature (alternation with no net
        # heading).  A forward-pool current plus mild bilateral turn
        # inhibition converts the weave into straight displacement.
        _brk = self._turn_adapt.breakout_drive(
            stuck_duration=getattr(self, "stuck_duration", 0.0))
        if _brk > 0.0:
            self.v[self.forward] += _brk
            self.v[self.turn_left] -= _brk * 0.5
            self.v[self.turn_right] -= _brk * 0.5
            # Jump injection during strong breakout to help clear obstacles
            if _brk > 0.25:
                self.v[self.jump_nodes] += (_brk - 0.25) * 0.5

        # EVO R15 · cliff-edge tangential detour (FailureMemory → CX pathway).
        # When parked at a CONFIRMED cliff edge and FailureMemory knows a
        # failure cell ahead, inject an ALONG-EDGE turn current (sign chosen
        # by ground freshness) and slightly suppress forward — head-on into a
        # known cliff is replaced by edge-following.  The LIF network still
        # decides the actual heading through its own competition.
        if self.cliff_confirmed and self.cliff_tangent_bias:
            _t = abs(self.cliff_tangent_bias) * 0.15
            if self.cliff_tangent_bias > 0:
                self.v[self.turn_right] += _t
            else:
                self.v[self.turn_left] += _t
            self.v[self.forward] -= 0.08          # ease off head-on drive

        # EVO R19 · restlessness: standoff/loop pressure builds forward drive
        # (escape motivation accumulates with entrapment time).
        _rest = self.restlessness_level()
        if _rest > 0.0:
            self.v[self.forward] += _rest * 0.12

        # EVO R29 · pit escape oscillator: when trapped below ground with the
        # forward MBON suppressed to near-zero (learned helplessness), inject
        # a 2.5 Hz alternating push-forward + jump-hop current into the LIF
        # pools.  The network chooses the exact timing; the oscillator just
        # biases the pool toward a climbing rhythm.
        _pit = (getattr(self, "stuck_duration", 0.0) > 60
                and getattr(self, "mb_mbon_forward", 0.0) < 0.2
                and self.anomaly_state_name in ("fallen", "idle"))
        if _pit:
            _phase = (self.step_count % 10) / 10.0  # 0-1 saw at ~5Hz
            _hop = abs(_phase - 0.5) * 2.0           # triangle wave
            self.v[self.forward] += 0.40 * _hop
            self.v[self.jump_nodes] += 0.80 * (1.0 - _hop)  # 0.80 > LIF decay, guarantees spike
            self.v[self.turn_left] += 0.05 * np.sin(self.step_count * 0.5)

        # EVO R21 · recognition → behaviour closure: a recognised DANGEROUS
        # scene (lava/hell tags) suppresses forward drive — caution current.
        # Direction selection stays with the turn-pool competition.
        if self.scene_danger > 0.0:
            self.v[self.forward] -= self.scene_danger * 0.06

        # EVO R22 · spontaneous forward recovery when learner helplessness
        # has suppressed the forward MBON but the fly is still stuck.
        # This provides a mild "trying again" current that decays quickly
        # if movement produces no result, but may trigger forward once.
        _stuck = getattr(self, "stuck_duration", 0.0)
        _mb_fwd = getattr(self, "mb_mbon_forward", 0.0)
        if _stuck > 30.0 and _mb_fwd < 0.05:
            _rec = min(1.0, (_stuck - 30.0) / 30.0)
            self.v[self.forward] += _rec * 0.08

        fired = self.v >= self.threshold
        self.v[fired] = self.reset
        self.spikes[:] = fired
        self.activity *= 0.82
        self.activity[fired] = 1.0
        # Ornstein-Uhlenbeck noise adds correlated fluctuations to motor neuron voltage
        # Each motor group gets slow-varying OU noise simulating E-I balance fluctuations
        dt = self.dt
        theta = self.ou_theta
        sigma = self.ou_sigma
        self.ou_state += theta * (self.ou_mu - self.ou_state) * dt + \
            sigma * np.sqrt(dt) * self.rng.normal(size=self.ou_state.shape).astype(np.float32)
        offset = 0
        n_fwd = len(self.forward)
        self.v[self.motor_nodes[offset:offset+n_fwd]] += self.ou_state[0] * 0.15
        offset += n_fwd
        n_left = len(self.turn_left)
        self.v[self.motor_nodes[offset:offset+n_left]] += self.ou_state[1] * 0.15
        offset += n_left
        n_right = len(self.turn_right)
        self.v[self.motor_nodes[offset:offset+n_right]] += self.ou_state[2] * 0.15
        offset += n_right
        self.v[self.motor_nodes[offset:offset+len(self.jump_nodes)]] += self.ou_state[3] * 0.15
        # Re-check firing after OU noise injection
        refired = self.v >= self.threshold
        newly_fired = refired & ~fired
        self.v[newly_fired] = self.reset
        self.spikes[newly_fired] = 1.0
        self.activity[newly_fired] = 1.0
        fired = self.spikes.copy()
        self.history.append(fired[self.motor_nodes].copy())
        self.step_count += 1

        # Decode a rolling ~250 ms spike-rate window, matching the documented
        # descending-neuron interface instead of reacting to a single tick.
        recent = np.stack(tuple(self.history), axis=0).mean(axis=0)
        forward_rate, left_rate, right_rate, jump_rate, strike_rate, crouch_rate = [
            float(pool.mean()) for pool in np.split(recent, self.motor_splits)]
        # EVO R30 · direct forward boost when stuck below ground with
        # suppressed MBON — bypass learned helplessness, feeds through
        # the normal decode path (smoothing, clamping, filtering).
        _stuck_below = (getattr(self, "stuck_duration", 0.0) > 60
                        and getattr(self, "pose_y", 0.0) < -150)
        if _stuck_below and forward_rate < 0.01:
            forward_rate = 0.06
            jump_rate = max(jump_rate, 0.3)  # also boost jump
        turn_rate = right_rate - left_rate
        # EVO R14 · integrate turn-circuit fatigue from the decoded pool rates
        self._turn_adapt.update(left_rate, right_rate, self.dt)

        # EVO R29 · pit escape rate override: when stuck below ground with
        # suppressed MBON output, boost jump_rate directly (LIF injection is
        # insufficient because the fast time constant dissipates voltage
        # between ticks before it can accumulate to threshold).
        _pit = (getattr(self, "stuck_duration", 0.0) > 60
                and getattr(self, "anomaly_state_name", "idle") in ("fallen", "idle"))
        if _pit:
            jump_rate = max(jump_rate, 0.3)

        raw_y = np.clip((forward_rate - 0.008) * 2000.0, 0, 70)
        raw_x = np.clip(turn_rate * 1100.0, -70, 70)

        # ---- Optic flow modulation (pre-emptive collision avoidance) ----
        # Only apply when synapses are active (no connectome shortcut test)
        if self.visual_connected and self.w.nnz > 0:
            # 1. Asymmetry → bias turn toward the side with more motion
            if abs(self.flow_asymmetry) > 0.05:
                raw_x -= self.flow_asymmetry * 20.0

            # 2. Looming → reduce forward drive, shorten jump cooldown
            if self.flow_looming > 0.15:
                looming_factor = 1.0 - min(self.flow_looming * 1.2, 0.8)
                raw_y *= looming_factor

            # P1 (audit A2): the flow_cliff < 0.3 random ±40 turn branch is
            # deleted.  Cliff avoidance is owned by the runner's cliff reflex
            # (cliff_confirmed path) and, on the roadmap, by an LC4-derived
            # turn-pool injection — a coin-flip write is not a neural policy.

            # ---- Multi-channel retina modulation ----
            # 4a. High ON + low OFF = object appearing ahead → increase jump probability
            #     (handled via jump_rate boost below, not raw_x/raw_y here)
            # 4b. High OFF = something passing → possible obstacle on that side → bias turn
            if self.off_energy > 0.03 and self.on_energy < 0.01:
                # Strong OFF without ON suggests lateral motion (object passing)
                # Bias turn toward the side with less asymmetry
                bias = self.off_energy * 30.0
                if self.flow_asymmetry > 0:
                    raw_x += bias  # already turning right, reinforce
                elif self.flow_asymmetry < 0:
                    raw_x -= bias  # already turning left, reinforce
                else:
                    # No asymmetry — random direction
                    raw_x += bias * (1.0 if self.rng.random() < 0.5 else -1.0)

            # 4c. High sustained = approaching a stationary object → reduce forward speed
            if self.sustained_energy > 0.03:
                sustain_brake = 1.0 - min(self.sustained_energy * 1.5, 0.6)
                raw_y *= sustain_brake

            # 4d. Dominant edge orientation → bias turn direction
            edges = [self.edge_0, self.edge_45, self.edge_90, self.edge_135]
            max_edge = max(edges)
            if max_edge > 0.05:
                dominant_idx = edges.index(max_edge)
                if dominant_idx == 0:   # horizontal edges → turn less (open space)
                    raw_x *= 0.85
                elif dominant_idx == 2: # vertical edges → corridor, turn less
                    raw_x *= 0.70
                elif dominant_idx == 1: # diagonal (45°) → bias turn away
                    raw_x += 8.0
                elif dominant_idx == 3: # anti-diagonal (135°) → bias turn opposite
                    raw_x -= 8.0

            # ---- 5. 4-direction EMD modulation ----
            # The EMD provides true direction-selective motion energy, replacing the
            # coarse left_right_asymmetry for fine-grained behaviour.
            _emd_h = self.emd_horizontal
            _emd_v = self.emd_vertical
            _emd_net_lat = self.emd_net_lateral
            _emd_net_vert = self.emd_net_vertical

            # 5a. Strong vertical EMD (up/down) → terrain change detected: reduce speed
            if _emd_v > 0.03 and _emd_h < 0.01:
                # Pure vertical motion = elevator/terrain drop → slight caution
                raw_y *= max(0.6, 1.0 - _emd_v * 3.0)

            # 5b. Asymmetric horizontal EMD → precise turn bias
            # Unlike flow_asymmetry (global brightness), this is true direction-selective
            if abs(_emd_net_lat) > 0.1 and _emd_h > 0.02:
                lat_bias = _emd_net_lat * 15.0
                raw_x -= lat_bias  # net rightward motion → turn right to steer into flow

            # 5c. Strong symmetric horizontal EMD → passing through corridor/opening
            if _emd_h > 0.05 and abs(_emd_net_lat) < 0.15:
                # Optic flow on both sides equally → reduce turn (straighten)
                raw_x *= max(0.5, 1.0 - _emd_h * 2.0)

            # 5d. OFF-dominant EMD → external moving object detected
            # (high off_total without on_total = passing dark edge, e.g. a Goomba passing)
            if (self.emd_off_total > self.emd_on_total * 2.0
                and self.emd_off_total > 0.02):
                # Possible moving threat on one side
                threat_bias = self.emd_off_total * 20.0
                if self.emd_off_right > self.emd_off_left:
                    raw_x += threat_bias  # turn left away from right-side threat
                else:
                    raw_x -= threat_bias  # turn right away from left-side threat

            # ---- 6. Color vision modulation ----
            # 6a. High danger_red_index → avoid (lava = bad, red switch = interesting)
            #     Use contextual gating: red + high temperature (tau near) = avoid
            if self.danger_red_index > 0.4 and self.tau < 3.0:
                # Red hazard near → turn away
                if self.rg_opponent_mean > 0:
                    raw_x += 30.0  # left side is redder → turn right
                else:
                    raw_x -= 30.0  # right side is redder → turn left
                raw_y *= 0.6  # slow down approaching hazard

            # 6b. High sky_blue_index → open area detected: explore forward
            if self.sky_blue_index > 0.5 and self.danger_red_index < 0.3:
                raw_y = min(70, raw_y * 1.15)  # slight forward boost in open areas

            # 6c. High color_contrast + high saturation → interactive objects nearby
            #     (coins, switches have saturated colors against neutral backgrounds)
            if self.color_contrast > 0.3 and self.saturation_mean > 0.25:
                # Interesting scene: reduce random turns, keep heading
                raw_x *= 0.7

            # ---- 7. Small target tracking: peripheral avoidance (post-spike, raw_x/raw_y level) ----
            # 7a. Strong figure-ground energy without approaching → lateral object avoidance
            if (self.max_target_energy > 0.05
                and self.fg_fraction < 0.08
                and not self.target_approaching):
                # Object in periphery — mild avoidance bias
                if self.target_count > 0:
                    _tgt_r, _tgt_c = self.target_nearest_centroid
                    _lateral_bias = (_tgt_c - 32.0) / 32.0
                    _avoid = self.max_target_energy * 20.0
                    if abs(_lateral_bias) > 0.3:
                        if _lateral_bias > 0:  # target on right → turn left
                            raw_x -= _avoid * 0.10
                        else:                   # target on left → turn right
                            raw_x += _avoid * 0.10

            # 7b. High fg_fraction (>15%) = wide-field disturbance → suppress target tracking
            #     (defer to existing optic flow navigation)
            if self.fg_fraction > 0.15:
                pass  # wide-field motion — let existing rules handle it

            # ---- Tau-based collision avoidance ----
            tau = self.tau
            if tau < self.TAU_SHARP_TURN:
                # Imminent collision: emergency sharp turn away from motion
                turn_dir = 1.0 if self.rng.random() < 0.5 else -1.0
                raw_x = turn_dir * 60.0
                raw_y *= 0.2
            elif tau < self.TAU_DECELERATE:
                # Approaching: reduce forward speed, bias turn
                urgency = 1.0 - tau / self.TAU_DECELERATE
                raw_y *= max(1.0 - urgency * 0.7, 0.1)
                turn_bias = urgency * 30.0
                if self.flow_asymmetry > 0:
                    raw_x -= turn_bias  # turn left (away from rightward flow)
                else:
                    raw_x += turn_bias  # turn right (away from leftward flow)
            elif tau < self.TAU_NEAR:
                # Nearby: slight caution
                raw_y *= max(0.5, tau / self.TAU_NEAR)
                raw_x += self.rng.uniform(-5.0, 5.0)  # exploratory turn noise

            # ---- Terrain modulation (between optic flow and escape) ----
            # 5a. High wall_score > 0.5 → wall ahead: increase turn away from wall
            #     (wall creates motion asymmetry on the side it occupies)
            if self.wall_score > 0.5:
                # Turn away from the side with more visual motion (the wall)
                wall_turn = self.wall_score * 25.0
                if self.flow_asymmetry > 0:  # more motion on left → wall left → turn right
                    raw_x += wall_turn
                else:  # more motion on right → wall right → turn left
                    raw_x -= wall_turn

            # 5b. High ramp_score > 0.5 → slope, not cliff: suppress random cliff turns
            if self.ramp_score > 0.5:
                # Cancel any previous random cliff turn by pulling x toward zero
                raw_x *= 0.3
                # Maintain forward drive (slopes are traversable)
                raw_y = max(raw_y, 30)

            # 5c. High opening_score > 0.5 → passage/opening ahead: explore toward it
            if self.opening_score > 0.5:
                # Opening ahead — reduce turn rate to aim for the opening
                raw_x *= 0.5
                # Slight forward boost
                opening_boost = 1.0 + self.opening_score * 0.3
                raw_y = min(70, raw_y * opening_boost)

            # 5d. door_frame_score > 0.5 → doorway detected: priority turn toward it
            if self.door_frame_score > 0.5:
                # Doorway = turn toward the side with less visual energy (the opening)
                # Use asymmetry inverted: turning toward the quieter side
                door_turn = self.door_frame_score * 35.0
                if self.flow_asymmetry < 0:  # more motion on right → door on left → turn left
                    raw_x -= door_turn
                else:  # more motion on left → door on right → turn right
                    raw_x += door_turn
                # Reduce forward speed approaching the door
                raw_y *= max(0.5, 1.0 - self.door_frame_score * 0.3)

        raw_y = np.clip(raw_y, 0, 70)
        raw_x = np.clip(raw_x, -70, 70)

        self.filtered_y = 0.78 * self.filtered_y + 0.22 * raw_y
        self.filtered_x = 0.78 * self.filtered_x + 0.22 * raw_x
        jump = jump_rate > 0.04 and now - self.last_jump >= 0.8
        if jump:
            self.last_jump = now
        # Phase 3: strike (B, pulse w/ cooldown) and crouch (Z, level) decode.
        strike = strike_rate > 0.05 and now - self.last_strike >= 1.0
        if strike:
            self.last_strike = now
        crouch = crouch_rate > 0.03
        return Control(int(self.filtered_x) if abs(self.filtered_x) >= 8 else 0,
                       int(self.filtered_y) if self.filtered_y >= 8 else 0,
                       jump, forward_rate, turn_rate, jump_rate,
                       b=strike, z=crouch), np.flatnonzero(fired)
