"""FlyGym-based verification environment for the Fly64 brain model.

P3-2: second verification scenario.  Wraps a FlyGym SingleFlySimulation
with vision and provides an interface through which the brain model's
visual processing (retina → optic flow → CX steering) and motor output
can be verified independently of the SM64 game bridge.

The environment creates a fruit fly walking on flat terrain with a
simple CPG gait.  The brain model receives camera images, processes
them through its visual pipeline, and its steering output modulates
the CPG to produce direction-biased walking.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import numpy as np


# ── CPG gait pattern generator ──────────────────────────────────────────

class CpgGait:
    """Simple Central Pattern Generator for hexapod walking.

    Generates per-leg joint targets using a modified sine-wave oscillator
    with phase offsets for tripod gait.  The command signal (forward/turn)
    modulates amplitude and bias to steer the fly.
    """

    # Joint names per leg in the standard 42-element array
    LEG_JOINTS = {
        "LF": slice(0, 7),     # left front:  7 joints
        "LM": slice(7, 14),    # left mid:    7 joints
        "LH": slice(14, 21),   # left hind:   7 joints
        "RF": slice(21, 28),   # right front: 7 joints
        "RM": slice(28, 35),   # right mid:   7 joints
        "RH": slice(35, 42),   # right hind:  7 joints
    }
    # Default coxa + femur + tibia indices within each 7-joint block
    COX_IDX = 0      # joint_LXCoxa
    FEMUR_IDX = 3    # joint_LXFemur
    TIBIA_IDX = 5    # joint_LXTibia

    def __init__(self, amplitude: float = 0.3, frequency: float = 2.0,
                 step_phase: float = 0.0):
        self.amplitude = amplitude
        self.frequency = frequency
        self.step_phase = step_phase
        self.time = 0.0
        # Baseline (stance) joint angles
        self._baseline = np.zeros(42, dtype=np.float32)
        self._baseline[[self.COX_IDX + s.start for s in self.LEG_JOINTS.values()]] = 0.1
        self._baseline[[self.FEMUR_IDX + s.start for s in self.LEG_JOINTS.values()]] = -0.5
        self._baseline[[self.TIBIA_IDX + s.start for s in self.LEG_JOINTS.values()]] = 1.5
        # Tripod groups: LF+RH+LM on one phase, RF+LH+RM on opposite
        self._tripod_a = ("LF", "RH", "LM")
        self._tripod_b = ("RF", "LH", "RM")

    def reset(self) -> None:
        self.time = 0.0

    def step(self, dt: float, forward_mod: float = 1.0,
             turn_mod: float = 0.0) -> np.ndarray:
        """Generate joint targets for one time step.

        Parameters
        ----------
        dt : float
            Simulation time step (seconds).
        forward_mod : float, optional
            Forward speed modifier (0-1).  Default 1.0.
        turn_mod : float, optional
            Turning bias (-1 to 1, negative=left, positive=right).

        Returns
        -------
        ndarray, shape (42,)
            Joint position targets.
        """
        self.time += dt
        phase = self.time * self.frequency * 2 * np.pi + self.step_phase
        joints = self._baseline.copy()

        for leg in self._tripod_a:
            s = self.LEG_JOINTS[leg]
            swing = np.sin(phase) * self.amplitude * forward_mod
            joints[s.start + self.COX_IDX] = ( 0.15 + turn_mod * 0.1
                                               if leg.startswith("L")
                                               else 0.15 - turn_mod * 0.1)
            joints[s.start + self.FEMUR_IDX] = -0.5 + swing
            joints[s.start + self.TIBIA_IDX] = 1.5 - swing * 0.5

        for leg in self._tripod_b:
            s = self.LEG_JOINTS[leg]
            swing = np.sin(phase + np.pi) * self.amplitude * forward_mod
            joints[s.start + self.COX_IDX] = ( 0.15 + turn_mod * 0.1
                                               if leg.startswith("L")
                                               else 0.15 - turn_mod * 0.1)
            joints[s.start + self.FEMUR_IDX] = -0.5 + swing
            joints[s.start + self.TIBIA_IDX] = 1.5 - swing * 0.5

        return joints


# ── Vision adapter ──────────────────────────────────────────────────────

def flygym_to_luminance(raw_vision: np.ndarray) -> np.ndarray:
    """Convert FlyGym raw vision array to a per-cell luminance array.

    FlyGym ``info['raw_vision']`` has shape ``(2, 512, 450, 3)`` — two eye
    views at 512×450 RGB.  This function downsamples each eye to a single
    luminance value (mean across the visible field), returning a 2-element
    array simulating a two-ommatidium retina readout.

    For more detailed visual processing, the raw_vision can be resized to
    the fly64 retina's expected atlas format (256×384), but the full 6-face
    atlas is specific to SM64's cubemap rendering.
    """
    raw = np.asarray(raw_vision, dtype=np.float32)
    if raw.ndim == 4 and raw.shape[-1] == 3:
        # Per-eye mean luminance (BT.709 weights)
        lum = raw[..., 0] * 0.2126 + raw[..., 1] * 0.7152 + raw[..., 2] * 0.0722
        return np.array([lum[i].mean() for i in range(min(2, raw.shape[0]))],
                        dtype=np.float32)
    return np.zeros(2, dtype=np.float32)


# ── Main environment class ──────────────────────────────────────────────

class FlyGymBrainEnv:
    """FlyGym verification environment for the Fly64 brain model.

    Wraps a FlyGym ``SingleFlySimulation`` with a hexapod CPG gait,
    providing step/observation interfaces that the brain model can consume.

    Parameters
    ----------
    timestep : float, optional
        FlyGym physics timestep (default 0.0001 s — 10 kHz).
    cpg_amplitude : float, optional
        CPG step amplitude (default 0.3).
    cpg_frequency : float, optional
        CPG step frequency in Hz (default 2.0).
    render : bool, optional
        Enable camera rendering (default False for CI).
    """

    def __init__(self, timestep: float = 0.0001,
                 cpg_amplitude: float = 0.3,
                 cpg_frequency: float = 2.0,
                 render: bool = False):
        self.timestep = timestep
        self.render = render
        self._step_count = 0
        self._sim = None
        self._fly = None
        self._arena = None
        self._cpg = CpgGait(amplitude=cpg_amplitude, frequency=cpg_frequency)
        self._prev_lum = deque(maxlen=2)

    # ── Lifecycle ────────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        """Initialize or reset the FlyGym simulation.

        Returns the initial observation dict.
        """
        import flygym
        import flygym.arena

        self._step_count = 0

        # Create arena and fly with vision
        self._arena = flygym.arena.FlatTerrain()

        vision_on = self.render
        self._fly = flygym.Fly(enable_vision=vision_on,
                                render_raw_vision=vision_on)

        # SingleFlySimulation wraps fly + physics
        self._sim = flygym.SingleFlySimulation(
            fly=self._fly, arena=self._arena, timestep=self.timestep)

        obs, info = self._sim.reset(seed=seed)

        # Compute initial observation
        result = self._build_observation(obs, info)
        self._prev_lum.append(result.get("luminance", 0.0))
        return result

    def step(self, forward_mod: float = 1.0,
             turn_mod: float = 0.0,
             duration: float = 0.01) -> dict[str, Any]:
        """Advance the simulation by *duration* seconds of physics time.

        Parameters
        ----------
        forward_mod : float, optional
            Forward speed modifier (0-1).  Default 1.0.
        turn_mod : float, optional
            Turning bias (-1 left, +1 right).  Default 0.0.
        duration : float, optional
            Physics seconds to simulate.  Default 0.01 (10 ms).

        Returns
        -------
        dict with keys: joints, fly, vision_raw (if render=True),
        luminance, mean_luminance, cpg_phase, step_count, info.
        """
        if self._sim is None:
            raise RuntimeError("Call reset() before step()")

        n_substeps = max(1, int(round(duration / self.timestep)))
        last_obs = None
        last_info = {}

        for _ in range(n_substeps):
            joint_targets = self._cpg.step(
                self.timestep, forward_mod=forward_mod, turn_mod=turn_mod)
            action = {"joints": joint_targets}
            last_obs, reward, terminated, truncated, last_info = \
                self._sim.step(action)
            self._step_count += 1
            if terminated or truncated:
                break

        result = self._build_observation(last_obs, last_info)
        self._prev_lum.append(result.get("luminance", 0.0))
        return result

    # ── Internal helpers ─────────────────────────────────────────────

    def _build_observation(self, obs: dict,
                           info: dict[str, Any]) -> dict[str, Any]:
        """Build a structured observation dict from FlyGym outputs."""
        result: dict[str, Any] = {
            "joints": obs.get("joints", np.zeros((3, 42))),
            "fly": obs.get("fly", np.zeros((4, 3))),
            "step_count": self._step_count,
            "cpg_phase": self._cpg.time,
        }

        # Vision (only if render=True)
        raw_vision = info.get("raw_vision")
        if raw_vision is not None and self.render:
            result["vision_raw"] = raw_vision
            lum_per_eye = flygym_to_luminance(raw_vision)
            result["luminance"] = float(lum_per_eye.mean())
        else:
            result["luminance"] = 0.0

        result["mean_luminance"] = float(
            np.mean(list(self._prev_lum)) if self._prev_lum else 0.0)

        # Fly state
        fly_pos = obs.get("fly", np.zeros((4, 3)))
        result["position"] = (float(fly_pos[0, 0]),
                              float(fly_pos[0, 2]))
        result["orientation"] = float(
            np.arctan2(fly_pos[1, 0], fly_pos[1, 2]))

        result["info"] = info
        return result

    def close(self) -> None:
        """Clean up the simulation resources."""
        if self._sim is not None:
            self._sim.close()
            self._sim = None
            self._fly = None
            self._arena = None

    @property
    def is_open(self) -> bool:
        """True when the simulation is active."""
        return self._sim is not None

    @property
    def step_count(self) -> int:
        return self._step_count