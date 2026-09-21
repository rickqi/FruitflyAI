"""VisionSource / MotorTarget abstract protocols for the Fly64 brain loop.

Defines the interface contracts that any environment (SM64, FlyGym, etc.)
must satisfy so the main loop can switch between backends without
invasive coupling.  Concrete adapters implement each protocol for the
SM64 bridge; future backends supply their own adapters.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

# Re-export constants consumed by downstream adapters.
from fly64.bridge import CHANNELS, HEIGHT, WIDTH


# ── Vision protocol ────────────────────────────────────────────────────

@runtime_checkable
class VisionSource(Protocol):
    """Protocol for a frame source consumed by the Fly64 visual pipeline.

    Every environment must provide a :meth:`read_frame` that returns a
    3-D ``np.ndarray`` of shape ``(height, width, channels)`` with dtype
    ``np.uint8``.  The default shape is ``(256, 384, 3)`` — the SM64
    atlas format.
    """

    def read_frame(self) -> np.ndarray:
        """Return the latest visual frame as a uint8 ndarray.

        Returns
        -------
        np.ndarray
            Shape ``(HEIGHT, WIDTH, CHANNELS)``, dtype ``np.uint8``.
            The contents represent the raw pixel data that the retina
            pipeline (calibration → photoreceptors → lamina → medulla)
            further processes.
        """
        ...


# ── Motor protocol ─────────────────────────────────────────────────────

@runtime_checkable
class MotorTarget(Protocol):
    """Protocol for a motor-output sink consumed by the Fly64 brain loop.

    Every environment must provide a :meth:`write_control` that accepts a
    one-dimensional ``np.ndarray`` whose interpretation is backend-specific:

    * **SM64 bridge** — 4-element vector ``[x, y, jump, z]``:
      ``x, y`` are signed 8-bit joystick axes, ``jump`` / ``z`` are
      boolean flags.
    * **FlyGym** — 3-element vector ``[forward_mod, turn_mod, duration]``
      consumed by the CPG gait generator.
    """

    def write_control(self, control: np.ndarray) -> None:
        """Write motor command to the backend.

        Parameters
        ----------
        control : np.ndarray
            Backend-specific control vector (see class docstring).
        """
        ...


# ── SM64 bridge adapters ───────────────────────────────────────────────

class SM64BridgeVisionSource:
    """Adapts a ``SharedBridge`` instance to the ``VisionSource`` protocol.

    Wraps ``bridge.read_frame()`` — which returns a ``(seq, bytes)`` pair
    and stores frame metadata — into a pure ``np.ndarray`` for the retina.
    """

    __slots__ = ("_bridge",)

    def __init__(self, bridge: Any) -> None:
        # Use Any to avoid a hard import cycle; the bridge type is
        # fly64.bridge.SharedBridge at runtime.
        self._bridge = bridge

    def read_frame(self) -> np.ndarray:
        seq, pixels = self._bridge.read_frame()
        # read_frame returns bytes(FRAME_BYTES); reshape to (H, W, 3).
        return np.frombuffer(pixels, dtype=np.uint8).reshape((HEIGHT, WIDTH, CHANNELS))


class SM64BridgeMotorTarget:
    """Adapts a ``SharedBridge`` instance to the ``MotorTarget`` protocol.

    Wraps ``bridge.write_control(x, y, jump, ...)``.  Accepts a 4-element
    control vector ``[x, y, jump, z]`` where x/y are signed 8-bit joystick
    axes, jump and z are floats (truthy → boolean True).
    """

    __slots__ = ("_bridge",)

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    def write_control(self, control: np.ndarray) -> None:
        x = int(np.clip(control[0], -128, 127))
        y = int(np.clip(control[1], -128, 127))
        jump = bool(control[2])
        z = bool(control[3]) if len(control) >= 4 else False
        self._bridge.write_control(x, y, jump, z=z)


# ── Environment adapter factory ──────────────────────────────────────

def create_environment(args: argparse.Namespace) -> dict[str, Any]:
    """Create environment adapters based on the ``--env`` CLI switch.

    Returns a dict with keys that the main loop's ``run()`` can consume
    without invasive coupling to any single backend:

    * ``bridge`` — the raw ``SharedBridge`` (or None for non-SM64 backends)
    * ``vision`` — a ``VisionSource``-compatible adapter
    * ``motor`` — a ``MotorTarget``-compatible adapter

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments (must contain ``.env`` and ``.bridge``).

    Returns
    -------
    dict[str, Any]
        Environment adapter collection.
    """
    env = getattr(args, "env", "sm64")
    bridge_path: Path = args.bridge

    if env == "flygym":
        # Lazy import to keep the dependency optional
        from fly64.environments.flygym_env import FlyGymBrainEnv

        flygym_env = FlyGymBrainEnv(render=True)
        flygym_env.reset()

        # The FlyGym env already provides read_frame-like and write_control
        # semantics; we bridge into our protocols by wrapping its step/obs
        # methods into VisionSource / MotorTarget adapters.

        # A minimal VisionSource that captures the latest observation frame
        class _FlyGymVisionSource:
            __slots__ = ("_env",)

            def __init__(self, env: FlyGymBrainEnv) -> None:
                self._env = env

            def read_frame(self) -> np.ndarray:
                # Use the latest observation dict — if vision_raw is
                # available, downsample it to retina format; otherwise
                # return a neutral-gray frame.
                obs: dict = getattr(self._env, "_last_obs", {})
                raw = obs.get("vision_raw")
                if raw is not None:
                    # raw: (2, 512, 450, 3); pick one eye and resize
                    # to (HEIGHT, WIDTH, CHANNELS) via simple slice
                    eye = np.asarray(raw[0], dtype=np.uint8)
                    h, w = eye.shape[:2]
                    scale_h = h // HEIGHT
                    scale_w = w // WIDTH
                    if scale_h > 0 and scale_w > 0:
                        down = eye[::scale_h, ::scale_w, :]
                        return down[:HEIGHT, :WIDTH, :]
                    return eye[:HEIGHT, :WIDTH, :]
                return np.full((HEIGHT, WIDTH, CHANNELS), 128, dtype=np.uint8)

        # A minimal MotorTarget that translates a 3-element control
        # [forward, turn, duration] into the FlyGym step call
        class _FlyGymMotorTarget:
            __slots__ = ("_env",)

            def __init__(self, env: FlyGymBrainEnv) -> None:
                self._env = env

            def write_control(self, control: np.ndarray) -> None:
                forward_mod = float(control[0])
                turn_mod = float(control[1])
                duration = float(control[2]) if len(control) >= 3 else 0.01
                obs = self._env.step(
                    forward_mod=forward_mod, turn_mod=turn_mod,
                    duration=duration,
                )
                # Cache the observation for the vision adapter
                self._env._last_obs = obs

        vision = _FlyGymVisionSource(flygym_env)
        motor = _FlyGymMotorTarget(flygym_env)
        return dict(bridge=None, vision=vision, motor=motor)

    # Default SM64 path
    from fly64.bridge import SharedBridge
    bridge = SharedBridge(bridge_path, create=True)
    vision = SM64BridgeVisionSource(bridge)
    motor = SM64BridgeMotorTarget(bridge)
    return dict(bridge=bridge, vision=vision, motor=motor)