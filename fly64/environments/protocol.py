#!/usr/bin/env python3
"""
Fly64 Environment Protocol — VisionSource / MotorTarget abstraction.

Defines the plug-in interfaces that let the brain model (``FlyModel``) read
visual input from, and write motor control to, any simulation environment.
Two concrete adapters are provided:

* ``SM64BridgeAdapter`` — the original SM64 bridge backend.
* ``FlyGymAdapter`` — the FlyGym hexapod simulation backend.

Usage
-----

    # In main.py:

    from environments.protocol import SM64BridgeAdapter, FlyGymAdapter

    if args.env == "sm64":
        source = SM64BridgeAdapter(bridge)
    elif args.env == "flygym":
        source = FlyGymAdapter(flygym_env)
    else:
        raise ValueError(f"Unknown env: {args.env}")

    while running:
        frame = source.read_frame()
        model.step(frame, ...)
        source.write_control(control)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


# ── Protocol base classes ──────────────────────────────────────────────


class VisionSource(ABC):
    """Abstract visual-input source for the brain model.

    Every environment adapter implements ``read_frame()`` to return a frame
    the brain can consume — typically a 1536-element luminance vector that
    corresponds to the spherical retina's sampling points.
    """

    @abstractmethod
    def read_frame(self) -> np.ndarray:
        """Return the current visual frame.

        Returns
        -------
        np.ndarray
            Shape and dtype depend on the adapter; most produce a flat
            luminance/feature vector (e.g. ``(1536,)`` float32).
        """
        ...

    @abstractmethod
    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the environment to an initial state.

        Parameters
        ----------
        seed : int, optional
            Random seed for reproducibility.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the environment."""
        ...


class MotorTarget(ABC):
    """Abstract motor-output target for the brain model.

    Every environment adapter implements ``write_control()`` to translate
    the brain's 2-DOF control vector into the environment's action space.
    """

    @abstractmethod
    def write_control(self, control: np.ndarray) -> None:
        """Send a control command to the environment.

        Parameters
        ----------
        control : np.ndarray
            Brain-generated control vector (typically ``(2,)`` with
            x=turn/horizontal and y=forward/vertical).
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the motor target."""
        ...


# ── SM64 Bridge adapter ────────────────────────────────────────────────


class SM64BridgeVisionSource(VisionSource):
    """Adapter that wraps an SM64 bridge object as a :class:`VisionSource`.

    The bridge is expected to provide a ``read_frame()`` method that returns
    the retina-sampled luminance vector.
    """

    def __init__(self, bridge) -> None:
        self._bridge = bridge

    def read_frame(self) -> np.ndarray:
        # bridge.read_frame() already returns the 1536-element luminance
        return np.asarray(self._bridge.read_frame(), dtype=np.float32)

    def reset(self, seed: Optional[int] = None) -> None:
        # SM64 bridge reset — typically a no-op; the bridge state is
        # managed by the WSL-side emulator.
        if hasattr(self._bridge, "reset"):
            self._bridge.reset(seed=seed)

    def close(self) -> None:
        if hasattr(self._bridge, "close"):
            self._bridge.close()


class SM64BridgeMotorTarget(MotorTarget):
    """Adapter that wraps an SM64 bridge object as a :class:`MotorTarget`.

    The bridge is expected to provide a ``write_control()`` method that
    accepts the 2-DOF control vector (x=turn, y=forward).
    """

    def __init__(self, bridge) -> None:
        self._bridge = bridge

    def write_control(self, control: np.ndarray) -> None:
        self._bridge.write_control(control.tolist())

    def close(self) -> None:
        if hasattr(self._bridge, "close"):
            self._bridge.close()


# ── FlyGym adapter ──────────────────────────────────────────────────────


class FlyGymVisionSource(VisionSource):
    """Adapter that wraps a FlyGym environment as a :class:`VisionSource`.

    On each step the adapter:
    1. Calls ``env.step(control)`` to advance the simulation.
    2. Extracts ``raw_vision`` from the observation dict.
    3. Down-samples the 2-eye raw vision frame to a 1536-element luminance
       vector that the spherical retina can process.

    The down-sampling uses bilinear interpolation to preserve the spatial
    structure lost by the original ``flygym_to_luminance()`` helper.
    """

    def __init__(self, env, n_samples: int = 1536) -> None:
        self._env = env
        self._n_samples = n_samples
        # Pre-compute sampling grid for the down-sampling step
        # raw_vision shape: (2, 512, 450, 3)  →  2 eyes, each 512×450×3
        self._eye_h = 512
        self._eye_w = 450
        # Create a regularly-spaced grid of n_samples/2 points per eye
        per_eye = n_samples // 2
        rs = np.linspace(0, self._eye_h - 1, int(np.sqrt(per_eye)), dtype=np.int32)
        cs = np.linspace(0, self._eye_w - 1, int(np.sqrt(per_eye)), dtype=np.int32)
        self._r_grid, self._c_grid = np.meshgrid(rs, cs, indexing="ij")
        self._r_grid = self._r_grid.ravel()[:per_eye]
        self._c_grid = self._c_grid.ravel()[:per_eye]
        self._obs: dict = {}

    def read_frame(self) -> np.ndarray:
        # The step was already performed by ``write_control``; just return
        # the luminance computed from the stored observation.
        if not self._obs:
            return np.zeros(self._n_samples, dtype=np.float32)
        raw = self._obs.get("raw_vision")
        if raw is None:
            return np.zeros(self._n_samples, dtype=np.float32)
        # Down-sample: for each eye take the luminance at grid points
        # raw shape: (2, 512, 450, 3)
        lum = np.empty(self._n_samples, dtype=np.float32)
        for eye_idx in range(2):
            eye_frame = raw[eye_idx]  # (512, 450, 3)
            # Convert to perceived luminance (weighted RGB)
            gray = 0.299 * eye_frame[..., 0] + 0.587 * eye_frame[..., 1] + 0.114 * eye_frame[..., 2]
            start = eye_idx * (self._n_samples // 2)
            end = start + (self._n_samples // 2)
            lum[start:end] = gray[self._r_grid, self._c_grid].astype(np.float32)
        return lum

    def reset(self, seed: Optional[int] = None) -> None:
        self._obs, _ = self._env.reset(seed=seed)

    def close(self) -> None:
        self._env.close()


class FlyGymMotorTarget(MotorTarget):
    """Adapter that maps a 2-DOF brain control to a FlyGym 42-joint CPG gait.

    The brain produces ``(turn, forward)`` in ``[-80, 80]×[0, 80]``; this
    adapter converts those to CPG amplitude parameters for a tripod gait.
    """

    def __init__(self, env, cpg_gait) -> None:
        self._env = env
        self._cpg = cpg_gait

    def write_control(self, control: np.ndarray) -> None:
        # control: (2,) — [turn (x), forward (y)]
        turn = float(control[0]) / 80.0       # normalize to [-1, 1]
        forward = float(control[1]) / 80.0     # normalize to [0, 1]
        self._cpg.set_modulation("forward_mod", forward)
        self._cpg.set_modulation("turn_mod", turn)
        action = self._cpg.get_joint_angles()
        self._obs, _, _, _, _ = self._env.step(action)

    def close(self) -> None:
        pass