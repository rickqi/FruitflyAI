"""R31-fix3: brain-native reward reshaping — damage RPE + coverage gate.

Design principle (user): all motion actions ultimately aim to be SIMPLE and
EFFECTIVE.  Damage must punish, motion without progress must not pay, and
the mechanisms stay single-rule simple.
"""
import numpy as np
import pytest

from fly64.model import FlyModel


@pytest.fixture(scope="module")
def model():
    return FlyModel(demo=True)


# ── C: coverage-gated movement reward ─────────────────────────────────

def test_circling_in_known_area_reduced_reward(model):
    """High displacement + no coverage progress -> reward scaled to 1/4."""
    model.report_movement(120.0, coverage_rate=0.0)
    circling = model.movement_reward
    model.report_movement(120.0, coverage_rate=0.05)
    exploring = model.movement_reward
    assert exploring > circling
    assert circling == pytest.approx(exploring * 0.25)


def test_negative_reward_not_scaled(model):
    """The gate only dampens positive (circling) reward, never punishment."""
    model.report_movement(0.0, coverage_rate=0.0)
    assert model.movement_reward < 0            # stuck stays fully negative


def test_progress_none_keeps_legacy_behaviour(model):
    model.report_movement(120.0, coverage_rate=None)
    model.report_movement(120.0, coverage_rate=None)
    # legacy path: deterministic same value, unscaled
    r1 = model.movement_reward
    model.report_movement(120.0, coverage_rate=None)
    assert model.movement_reward == r1


# ── A: damage -> PPL1-like negative RPE ───────────────────────────────

def test_damage_accumulates_via_add_setback(model):
    model._pending_dopamine = 0.0
    model.add_setback(0.3)
    assert model._pending_dopamine == -0.3
    model.add_setback(0.5)
    assert model._pending_dopamine == pytest.approx(-0.8)


def test_damage_rate_limited_in_main_wiring():
    """Source contract: the main-loop damage path is rate-limited and marks
    the damaged cell into FailureMemory (A+B wiring)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text()
    assert "_dmg_accum > 0.02" in src                      # accumulation gate
    assert "_last_dmg_setback >= 2.0" in src               # 2s rate limit
    assert "failures.record_failure" in src                # B: cell marking
    assert "add_setback(min(0.5, 0.2 + _dmg_accum))" in src  # bounded strength


# ── B: damaged cell feeds FailureMemory ───────────────────────────────

def test_failure_memory_marks_and_reports(model, tmp_path):
    from fly64.memory import FailureMemory
    fm = FailureMemory()
    fm.record_failure(-4200.0, -1400.0)
    assert fm.is_failure_cell(-4200.0, -1400.0)
    assert not fm.is_failure_cell(100.0, 100.0)
    vec = fm.nearest_failure_vector(-4200.0, -1400.0)
    assert vec is not None                  # CX anti-failure vector gets data
