"""VNC-style central pattern generator (CPG) motor primitives — Phase 2.

Design (docs/analysis/motor-expansion/cpg-motor-primitives.md):
the LIF brain emits *gate* signals; the deterministic phase scripts here own
the button timing sequences (long jump Z->A, backflip, ground pound).  This
mirrors the MaleCNS finding that VNC central pattern generators produce
rhythmic motor sequences independently of the brain.

Pure logic: no mmap, no numpy, fully unit-testable.  The runner (main.py)
feeds pose samples + gate flags each tick and applies the returned phase
outputs to the control cascade at priority 4.5 (between escape and jump).

P1 PIN compliance: this module never touches escape_toggle_timer /
bold_explore / legacy dialogue pulse patterns; it is a new, separately named
cascade layer (``cpg_primitive``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Circuit breaker: any one-shot primitive longer than this is force-aborted
# (anti-wedge: a wedged primitive must fall back to the reflex cascade).
MAX_PRIMITIVE_S = 2.0
# One pose sample window (seconds) used for the grounded/airborne inference.
POSE_WINDOW_S = 0.6
# Vertical speed (game units / s) above which Mario is considered airborne.
AIRBORNE_VZ = 120.0
# Sustained downward speed while "grounded" that means sliding on a slope.
SLIDING_VZ = 60.0
# wall_score above which a wall contact counts (matches model wall gate).
WALL_SCORE_MIN = 0.5


class MarioState(Enum):
    GROUNDED = "grounded"
    AIRBORNE = "airborne"
    # M2.2: refined states.  WALL = pressed against a vertical surface while
    # steering into it (wall-kick window); SLIDING = on a slope, altitude
    # steadily dropping (longjump is wasted there).  Priority:
    # WALL > SLIDING > GROUNDED.
    WALL = "wall"
    SLIDING = "sliding"
    UNKNOWN = "unknown"


class Primitive(Enum):
    LONG_JUMP = "longjump"          # running Z then A -> big displacement
    BACKFLIP = "backflip"           # stationary Z then A -> escape from fallen
    GROUND_POUND = "groundpound"    # airborne Z -> slam down onto platform
    PUNCH = "punch"                 # ground B (interactive targets) [Phase 3+]
    DIVE = "dive"                   # airborne B (small-target pursuit) [Phase 3+]
    SWIM_STROKE = "swim"            # water A rhythm CPG [Phase 3+]
    CRAWL = "crawl"                 # low-clearance slow move [Phase 3+]
    WALL_JUMP = "walljump"          # M2.3: A in the WALL window -> kick away
    SIDE_FLIP = "sideflip"          # M2.3: A on hard turn reversal


# Phase scripts: list of (duration_s, outputs) applied in order.
# outputs keys: x, y, jump, b, z  (missing keys -> 0/False)
PHASE_SCRIPTS: Dict[Primitive, List[Tuple[float, Dict]]] = {
    # crouch (Z held ~2 game frames) then A + full forward for the leap
    Primitive.LONG_JUMP: [
        (0.06, dict(z=True)),
        (0.65, dict(jump=True, y=70)),
    ],
    # crouch from standstill, then A (backflip pops straight up)
    Primitive.BACKFLIP: [
        (0.10, dict(z=True)),
        (0.55, dict(jump=True)),
    ],
    # Z in mid-air triggers the slam; the rest is wait time for the landing
    Primitive.GROUND_POUND: [
        (0.08, dict(z=True)),
        (1.20, dict()),
    ],
    Primitive.PUNCH: [
        (0.06, dict(b=True)),
        (0.20, dict()),
    ],
    Primitive.DIVE: [
        (0.08, dict(b=True, y=50)),
        (0.40, dict(y=50)),
    ],
    # M2.3: wall kick — A while facing the wall pops Mario away from it
    # (the game supplies the away-from-wall direction itself).
    Primitive.WALL_JUMP: [
        (0.08, dict(jump=True)),
        (0.45, dict()),
    ],
    # M2.3: side flip — A right after a hard turn reversal (showy high jump)
    Primitive.SIDE_FLIP: [
        (0.06, dict(jump=True)),
        (0.50, dict()),
    ],
}

# Loop primitives re-trigger their script until the gate turns off.
LOOP_PRIMITIVES = {Primitive.SWIM_STROKE, Primitive.CRAWL}
LOOP_SCRIPTS: Dict[Primitive, List[Tuple[float, Dict]]] = {
    # 400 ms A-stroke period (surface stroke rhythm)
    Primitive.SWIM_STROKE: [
        (0.10, dict(jump=True)),
        (0.30, dict()),
    ],
    Primitive.CRAWL: [
        (0.50, dict(z=True, y=30)),
    ],
}

# Which MarioState each primitive requires before it may start.
STATE_PRECONDITIONS: Dict[Primitive, Tuple[MarioState, ...]] = {
    Primitive.LONG_JUMP: (MarioState.GROUNDED,),
    Primitive.BACKFLIP: (MarioState.GROUNDED, MarioState.UNKNOWN),
    Primitive.GROUND_POUND: (MarioState.AIRBORNE,),
    Primitive.PUNCH: (MarioState.GROUNDED,),
    Primitive.DIVE: (MarioState.AIRBORNE,),
    Primitive.SWIM_STROKE: (MarioState.AIRBORNE, MarioState.UNKNOWN),
    Primitive.CRAWL: (MarioState.GROUNDED,),
    Primitive.WALL_JUMP: (MarioState.WALL,),
    Primitive.SIDE_FLIP: (MarioState.GROUNDED,),
}


@dataclass
class PrimitivePhase:
    """One tick of an active primitive: the cascade applies these outputs."""
    primitive: Primitive
    phase_index: int
    elapsed: float
    remaining: float
    x: int = 0
    y: int = 0
    jump: bool = False
    b: bool = False
    z: bool = False


@dataclass
class _Active:
    primitive: Primitive
    script: List[Tuple[float, Dict]]
    start: float
    elapsed: float = 0.0
    phase_index: int = 0
    phase_elapsed: float = 0.0
    runs: int = 1


class CPGController:
    """Gate-driven phase-script controller (brain gates -> CPG timing)."""

    def __init__(self, timeout_s: float = MAX_PRIMITIVE_S):
        self.timeout_s = float(timeout_s)
        self._active: Optional[_Active] = None
        self._pose: List[Tuple[float, float]] = []   # (t, z) ring
        self.state = MarioState.UNKNOWN
        # Telemetry / EVO bookkeeping
        self.completed = 0
        self.aborted = 0
        self.last_primitive: str = ""
        self.last_abort_reason: str = ""

    # ---- state machine (R-D) -------------------------------------------
    def feed_pose(self, now: float, z: float, wall_score: float = 0.0,
                  pushing: bool = False) -> MarioState:
        """Feed one pose sample; infer the fine-grained Mario state.

        Priority: WALL (grounded + wall contact + steering into it)
        > SLIDING (grounded but altitude steadily dropping on a slope)
        > AIRBORNE / GROUNDED from |dz/dt|.
        """
        self._pose.append((float(now), float(z)))
        cut = float(now) - POSE_WINDOW_S
        while self._pose and self._pose[0][0] < cut:
            self._pose.pop(0)
        if len(self._pose) >= 2:
            (t0, z0), (t1, z1) = self._pose[0], self._pose[-1]
            dt = max(t1 - t0, 1e-3)
            vz_signed = (z1 - z0) / dt
            vz = abs(vz_signed)
            if vz > AIRBORNE_VZ:
                self.state = MarioState.AIRBORNE
            elif wall_score > WALL_SCORE_MIN and pushing:
                # M2.2: wall-kick window (only meaningful while grounded)
                self.state = MarioState.WALL
            elif vz_signed < -SLIDING_VZ:
                # M2.2: sliding down a slope — altitude steadily dropping
                self.state = MarioState.SLIDING
            else:
                self.state = MarioState.GROUNDED
        return self.state

    # ---- gating ----------------------------------------------------------
    def request(self, now: float, primitive: Primitive) -> bool:
        """Brain/memory gate asks to start *primitive* (priority 4.5)."""
        if self._active is not None:
            return False                       # one primitive at a time
        if primitive not in PHASE_SCRIPTS and primitive not in LOOP_SCRIPTS:
            return False
        if self.state not in STATE_PRECONDITIONS.get(primitive, ()):
            return False                       # illegal combo rejected
        script = (LOOP_SCRIPTS if primitive in LOOP_PRIMITIVES
                  else PHASE_SCRIPTS)[primitive]
        total = sum(d for d, _ in script)
        if primitive not in LOOP_PRIMITIVES and total > self.timeout_s:
            return False
        self._active = _Active(primitive, script, float(now))
        self.last_primitive = primitive.value
        return True

    def cancel(self, reason: str = "external") -> None:
        if self._active is not None:
            self.aborted += 1
            self.last_abort_reason = reason
            self._active = None

    # ---- per-tick phase advance -----------------------------------------
    def update(self, now: float) -> Optional[PrimitivePhase]:
        """Advance the active primitive one tick; None when idle/finished."""
        if self._active is None:
            return None
        act = self._active
        prev_elapsed = act.elapsed
        act.elapsed = float(now) - act.start
        dt = max(act.elapsed - prev_elapsed, 0.0)
        act.phase_elapsed += dt
        # circuit breaker (loop primitives are exempt: gated, not timed)
        if (act.primitive not in LOOP_PRIMITIVES
                and act.elapsed > self.timeout_s):
            self.aborted += 1
            self.last_abort_reason = "timeout"
            self._active = None
            return None
        # advance phase pointer
        while act.phase_index < len(act.script):
            dur, _ = act.script[act.phase_index]
            if act.phase_elapsed < dur:
                break
            act.phase_elapsed -= dur
            act.phase_index += 1
        else:
            # script finished
            if act.primitive in LOOP_PRIMITIVES:
                act.phase_index = 0
                act.phase_elapsed = 0.0
                act.runs += 1
            else:
                self.completed += 1
                self._active = None
                return None
        dur, out = act.script[act.phase_index]
        return PrimitivePhase(
            primitive=act.primitive,
            phase_index=act.phase_index,
            elapsed=round(act.elapsed, 3),
            remaining=round(dur - act.phase_elapsed, 3),
            x=int(out.get("x", 0)),
            y=int(out.get("y", 0)),
            jump=bool(out.get("jump", False)),
            b=bool(out.get("b", False)),
            z=bool(out.get("z", False)),
        )

    # ---- introspection (telemetry /memory.json style) --------------------
    def status(self) -> Dict:
        act = self._active
        return dict(active=act.primitive.value if act else "",
                    phase=act.phase_index if act else -1,
                    state=self.state.value,
                    completed=self.completed,
                    aborted=self.aborted,
                    last=self.last_primitive,
                    last_abort=self.last_abort_reason)

    @property
    def active(self) -> Optional[Primitive]:
        return self._active.primitive if self._active else None


def apply_phase(control, phase: PrimitivePhase):
    """Apply a PrimitivePhase to a Control instance (returns the same object).

    Owning the field writes here keeps main.py's direct-control-write count
    within the P1 KPI budget while the cascade layer stays a single call.
    """
    control.x = phase.x
    control.y = phase.y
    control.jump = phase.jump
    control.b = phase.b
    control.z = phase.z
    return control
