"""M2.2/M2.3: refined MarioState (WALL/SLIDING) + wall-jump/side-flip."""
import pytest

from fly64.motor_primitives import (AIRBORNE_VZ, CPGController, MarioState,
                                    PHASE_SCRIPTS, Primitive,
                                    STATE_PRECONDITIONS, WALL_SCORE_MIN)


def _ground(cpg, t=100.0):
    for i in range(10):
        cpg.feed_pose(t + i * 0.02, 50.0)
    return cpg


def test_wall_state_when_contact_and_pushing():
    cpg = _ground(CPGController())
    cpg.feed_pose(100.3, 50.0, wall_score=0.9, pushing=True)
    assert cpg.state is MarioState.WALL


def test_wall_requires_pushing():
    cpg = _ground(CPGController())
    cpg.feed_pose(100.3, 50.0, wall_score=0.9, pushing=False)
    assert cpg.state is MarioState.GROUNDED


def test_wall_requires_score_above_min():
    cpg = _ground(CPGController())
    cpg.feed_pose(100.3, 50.0, wall_score=WALL_SCORE_MIN - 0.1, pushing=True)
    assert cpg.state is MarioState.GROUNDED


def test_sliding_when_sustained_descent():
    cpg = CPGController()
    t = 100.0
    for i in range(10):
        cpg.feed_pose(t + i * 0.06, 50.0 - i * 5.0)   # ~-83 u/s, < AIRBORNE_VZ
    assert cpg.state is MarioState.SLIDING


def test_sliding_suppresses_longjump():
    cpg = CPGController()
    t = 100.0
    for i in range(10):
        cpg.feed_pose(t + i * 0.06, 50.0 - i * 5.0)
    assert cpg.request(100.7, Primitive.LONG_JUMP) is False


def test_wall_jump_precondition_and_script():
    assert STATE_PRECONDITIONS[Primitive.WALL_JUMP] == (MarioState.WALL,)
    cpg = CPGController()
    for i in range(10):
        cpg.feed_pose(100.0 + i * 0.02, 50.0, wall_score=0.9, pushing=True)
    assert cpg.state is MarioState.WALL
    assert cpg.request(100.3, Primitive.WALL_JUMP)
    phase = cpg.update(100.3)
    assert phase is not None and phase.jump is True
    # completes within the breaker budget
    t = 100.3
    while cpg.active is not None and t < 103.0:
        cpg.update(t); t += 0.02
    assert cpg.active is None and cpg.aborted == 0


def test_side_flip_precondition_and_script():
    assert STATE_PRECONDITIONS[Primitive.SIDE_FLIP] == (MarioState.GROUNDED,)
    cpg = _ground(CPGController())
    assert cpg.request(100.3, Primitive.SIDE_FLIP)
    phase = cpg.update(100.3)
    assert phase is not None and phase.jump is True


def test_walljump_rejected_when_grounded():
    cpg = _ground(CPGController())
    assert cpg.request(100.3, Primitive.WALL_JUMP) is False


def test_new_primitives_in_scripts_and_budget():
    for prim in (Primitive.WALL_JUMP, Primitive.SIDE_FLIP):
        total = sum(d for d, _ in PHASE_SCRIPTS[prim])
        assert total <= 2.0
