from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import time

import numpy as np
from scipy import sparse
from .retina import SphericalRetina


@dataclass
class Control:
    x: int
    y: int
    jump: bool
    forward_rate: float
    turn_rate: float
    jump_rate: float


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
        self.history = deque(maxlen=13)
        self.motor_nodes = np.concatenate((self.forward, self.turn_left, self.turn_right, self.jump_nodes))
        self.motor_splits = np.cumsum([len(self.forward), len(self.turn_left), len(self.turn_right)])
        self.filtered_x = 0.0
        self.filtered_y = 0.0
        self.last_jump = -10.0
        self.step_count = 0
        self.mean_luminance = 0.0
        self.temporal_energy = 0.0
        self.visual_connected = True
        self.tonic_current = 0.180
        self.synaptic_gain = 1.50
        # Ornstein-Uhlenbeck noise for physiological motor fluctuations
        self.ou_state = np.zeros(4, dtype=np.float32)  # [fwd, left, right, jump]
        self.ou_theta = 2.0   # mean reversion rate (higher = faster decay)
        self.ou_sigma = 0.12  # noise amplitude
        self.ou_mu = 0.0      # mean
        # Novelty-driven modulation and escape
        self.escape_mode = False
        self.escape_current = 0.15  # extra depolarisation during escape
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

        # ---- Cliff detection (multi-frame confirmation) ----
        self._cliff_history = deque(maxlen=10)  # last 10 lower_field_green values
        self.CLIFF_THRESHOLD = 0.25
        self.CLIFF_RAPID_DROP = 0.15
        self.CLIFF_CONFIRM_FRAMES = 7

        # ---- Terrain classification from 16-sector optic flow ----
        self.terrain = "mixed"  # one of: cliff, water, corridor, wall_ahead,
                                # open_flat, dense, forest_edge, mixed
        self.wall_score = 0.0   # 0-1: vertical surface ahead
        self.ramp_score = 0.0   # 0-1: sloping surface
        self.opening_score = 0.0  # 0-1: passage/opening ahead
        self.sky_score = 0.0    # 0-1: open sky above
        self.ground_angle = 0.7  # 0=cliff, 0.3-0.7=slope, >0.7=flat
        self.door_frame_score = 0.0  # 0-1: doorway detected
        self.opening_width = 0.0  # 0-1: opening width

        # ---- Tau (time-to-contact) for collision avoidance ----
        self.tau = float("inf")  # seconds until contact; inf = no collision risk
        self.TAU_SHARP_TURN = 0.5   # τ below this → emergency sharp turn
        self.TAU_DECELERATE = 1.0   # τ below this → reduce speed
        self.TAU_NEAR = 2.0         # τ below this → cautious modulation

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

    def encode_retina(self, rgb: np.ndarray, heading: float = 0.0) -> np.ndarray:
        frame = self.retina.sample(rgb)
        lum = frame @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        prev_lum = self.previous_rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        temporal = np.abs(lum - prev_lum)
        color = np.maximum(frame[..., 1] - 0.5 * (frame[..., 0] + frame[..., 2]), 0)
        drive = np.clip(0.45 * lum + 1.6 * temporal + 0.25 * color, 0, 1)
        self.previous_rgb = frame
        self.mean_luminance = float(lum.mean())
        self.temporal_energy = float(temporal.mean())
        # --- Optic flow signals ---
        flow = self.retina.compute_flow(rgb)
        self.tau = float(flow.get("tau", float("inf")))
        self.flow_asymmetry = float(flow["left_right_asymmetry"])  # RAW (backward compat)
        self.flow_looming = float(flow["center_expansion"])
        self.flow_cliff = float(flow["lower_field_green"])
        self.terrain = str(flow.get("terrain", "mixed"))
        self.wall_score = float(flow.get("wall_score", 0.0))
        self.ramp_score = float(flow.get("ramp_score", 0.0))
        self.opening_score = float(flow.get("opening_score", 0.0))
        self.sky_score = float(flow.get("sky_score", 0.0))
        self.ground_angle = float(flow.get("ground_angle", 0.7))
        self.door_frame_score = float(flow.get("door_frame_score", 0.0))
        self.opening_width = float(flow.get("opening_width", 0.0))

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
        self._self_motion_cache = {
            "heading_rate": round(self.heading_rate, 4),
            "true_asymmetry": round(true_asym, 4),
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

        # --- Multi-frame cliff history ---
        self._cliff_history.append(self.flow_cliff)

        # --- Visual short-term memory (scene change detection) ---
        drive_mean = float(drive.mean())
        scene_state = self.scene_memory.update(drive_mean)
        self.scene_mean = scene_state["scene_mean"]
        self.scene_var = scene_state["scene_var"]
        self.scene_change = scene_state["scene_change"]
        self.scene_change_rate = scene_state["scene_change_rate"]

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

    def step(self, rgb: np.ndarray, now: float | None = None,
             novelty: float = 0.5, heading: float = 0.0) -> tuple[Control, np.ndarray]:
        now = self.step_count * self.dt if now is None else now
        sensory = self.encode_retina(rgb, heading=heading)

        # Novelty-driven visual modulation:
        # Low novelty (familiar) → boost sensory to seek variety
        # High novelty (unexplored) → slight suppression for caution
        novelty_gain = 1.0 + (0.10 if novelty < 0.3 else -0.10 if novelty > 0.7 else 0.0)

        current = np.asarray(self.w[:, np.flatnonzero(self.spikes)].sum(axis=1)).ravel()
        current *= self.synaptic_gain
        baseline = self.rng.random(self.n) < (1.2 * self.dt)
        self.v *= np.exp(-self.dt / self.tau_m)
        self.v += current + baseline.astype(np.float32) * 0.22 + self.tonic_current
        if self.visual_connected:
            self.v[self.visual] += sensory * 0.62 * novelty_gain

        # Escape-mode depolarisation of motor neurons
        if self.escape_mode:
            self.v[self.motor_nodes] += self.escape_current
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
        forward_rate, left_rate, right_rate, jump_rate = [float(pool.mean()) for pool in np.split(recent, self.motor_splits)]
        turn_rate = right_rate - left_rate

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

            # 3. Low cliff → force pre-emptive turn away from edge
            # Only when scene is visible (not in dark/initial state)
            if self.flow_cliff < 0.3 and self.mean_luminance > 0.02:
                turn_dir = 1.0 if self.rng.random() < 0.5 else -1.0
                raw_x += turn_dir * 40.0

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
        # Increase jump likelihood during looming (only with active synapses)
        if self.visual_connected and self.w.nnz > 0 and self.flow_looming > 0.4 and jump_rate > 0.02 and now - self.last_jump >= 0.6:
            jump = True
        # High ON + low OFF = object appearing ahead → boost jump probability
        if self.visual_connected and self.w.nnz > 0 and self.on_energy > 0.04 and self.off_energy < 0.01 and jump_rate > 0.02 and now - self.last_jump >= 0.6:
            jump = True
        if jump:
            self.last_jump = now
        return Control(int(self.filtered_x) if abs(self.filtered_x) >= 8 else 0,
                       int(self.filtered_y) if self.filtered_y >= 8 else 0,
                       jump, forward_rate, turn_rate, jump_rate), np.flatnonzero(fired)
