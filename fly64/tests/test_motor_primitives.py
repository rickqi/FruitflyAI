"""Phase 2 motor-expansion tests: CPG motor primitives + cascade gates."""
import time

import pytest

from fly64.motor_primitives import (AIRBORNE_VZ, CPGController, MarioState,
                                    PHASE_SCRIPTS, Primitive,
                                    STATE_PRECONDITIONS)


def advance(cpg, start, seconds, step=0.02):
    """Helper: tick the controller forward, collecting phases."""
    phases = []
    t = start
    while t < start + seconds + 1e-9:
        phase = cpg.update(t)
        if phase is not None:
            phases.append(phase)
        t += step
    return phases


# ---- state machine (R-D) -------------------------------------------------

def test_feed_pose_grounded_when_stable():
    cpg = CPGController()
    t = 100.0
    for _ in range(20):
        cpg.feed_pose(t, 50.0)
        t += 0.02
    assert cpg.state is MarioState.GROUNDED


def test_feed_pose_airborne_when_rising():
    cpg = CPGController()
    t = 100.0
    for i in range(20):
        cpg.feed_pose(t, 50.0 + i * 5.0)   # 250 u/s >> AIRBORNE_VZ
        t += 0.02
    assert cpg.state is MarioState.AIRBORNE
    assert AIRBORNE_VZ == 120.0


# ---- gating ---------------------------------------------------------------

def test_request_rejects_when_active():
    cpg = CPGController()
    for _ in range(10):
        cpg.feed_pose(100.0 + len(cpg._pose) * 0.02, 50.0)
    assert cpg.state is MarioState.GROUNDED
    assert cpg.request(100.5, Primitive.LONG_JUMP) is True
    assert cpg.request(100.5, Primitive.BACKFLIP) is False   # one at a time


def test_request_rejects_illegal_state_combo():
    cpg = CPGController()
    # GROUND_POUND requires AIRBORNE; controller starts UNKNOWN
    assert cpg.request(100.0, Primitive.GROUND_POUND) is False
    # LONG_JUMP requires GROUNDED
    assert cpg.request(100.0, Primitive.LONG_JUMP) is False


def test_state_preconditions_cover_all_primitives():
    for primitive in Primitive:
        assert primitive in STATE_PRECONDITIONS


# ---- phase scripts ----------------------------------------------------------

def test_long_jump_phase_sequence_z_then_a():
    cpg = CPGController()
    for i in range(10):
        cpg.feed_pose(100.0 + i * 0.02, 50.0)
    assert cpg.request(100.5, Primitive.LONG_JUMP)
    phases = advance(cpg, 100.5, 0.75)
    assert phases, "LONG_JUMP must emit phases"
    assert phases[0].z is True and phases[0].jump is False   # crouch first
    leap = [p for p in phases if p.jump]
    assert leap, "leap phase with A press must follow"
    assert all(p.y == 70 for p in leap)                      # full forward
    assert cpg.completed == 1


def test_long_jump_completes_within_timeout():
    cpg = CPGController()
    for i in range(10):
        cpg.feed_pose(100.0 + i * 0.02, 50.0)
    cpg.request(100.5, Primitive.LONG_JUMP)
    advance(cpg, 100.5, 3.0)
    assert cpg.active is None
    assert cpg.aborted == 0          # finished normally, not by breaker


def test_backflip_sequence():
    cpg = CPGController()
    for i in range(10):
        cpg.feed_pose(100.0 + i * 0.02, 50.0)
    assert cpg.request(100.5, Primitive.BACKFLIP)
    phases = advance(cpg, 100.5, 0.8)
    assert phases[0].z is True and phases[0].y == 0   # stationary crouch
    assert any(p.jump for p in phases)
    assert cpg.completed == 1


def test_ground_pound_requires_airborne():
    cpg = CPGController()
    for i in range(20):
        cpg.feed_pose(100.0 + i * 0.02, 50.0 + i * 5.0)   # airborne
    assert cpg.request(100.5, Primitive.GROUND_POUND)
    phases = advance(cpg, 100.5, 1.4)
    assert phases[0].z is True
    assert cpg.completed == 1


def test_ground_pound_rejected_grounded():
    cpg = CPGController()
    for i in range(20):
        cpg.feed_pose(100.0 + i * 0.02, 50.0)             # grounded
    assert cpg.request(100.5, Primitive.GROUND_POUND) is False


# ---- circuit breaker --------------------------------------------------------

def test_timeout_circuit_breaker_aborts_wedged_primitive():
    cpg = CPGController(timeout_s=2.0)
    # Force an active primitive with a huge fake elapsed via internal start.
    cpg._pose = [(99.9, 50.0), (100.0, 50.0)]
    cpg.state = MarioState.GROUNDED
    assert cpg.request(100.0, Primitive.LONG_JUMP)
    # Jump far past the script duration -> breaker must abort, return None.
    assert cpg.update(103.0) is None
    assert cpg.active is None
    assert cpg.aborted == 1
    assert cpg.last_abort_reason == "timeout"


def test_cancel_records_reason():
    cpg = CPGController()
    cpg._pose = [(99.9, 50.0), (100.0, 50.0)]
    cpg.state = MarioState.GROUNDED
    cpg.request(100.0, Primitive.LONG_JUMP)
    cpg.cancel("reflex_preempt")
    assert cpg.active is None
    assert cpg.aborted == 1
    assert cpg.last_abort_reason == "reflex_preempt"


def test_status_dict_shape():
    cpg = CPGController()
    status = cpg.status()
    assert set(status) == {"active", "phase", "state", "completed",
                           "aborted", "last", "last_abort"}
    assert status["active"] == ""


# ---- script integrity --------------------------------------------------------

def test_all_one_shot_scripts_within_timeout():
    for primitive, script in PHASE_SCRIPTS.items():
        total = sum(d for d, _ in script)
        assert total <= 2.0, f"{primitive} exceeds MAX_PRIMITIVE_S"
