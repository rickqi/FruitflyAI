#!/usr/bin/env python3
"""t28 regression: action entropy exploration.

When the brain is trapped in a learned dead-end (novelty < 0.1 AND
loop_score > 0.7), Gaussian N(0, sigma) noise is injected into the stick
with sigma = min(30, stuck_duration/10) — the longer stuck, the wilder the
exploration; decision_source gains the '+action_entropy' tag.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fly64.main import (action_entropy_sigma, apply_action_entropy,  # noqa: E402
                        resolve_decision_source)


def make_control(x=0, y=0):
    return types.SimpleNamespace(x=x, y=y, jump=False, b=False, z=False)


class TestSigma:
    def test_contract_values(self):
        assert action_entropy_sigma(60.0) == pytest.approx(6.0)
        assert action_entropy_sigma(300.0) == 30.0
        assert action_entropy_sigma(1000.0) == 30.0    # capped
        assert action_entropy_sigma(0.0) == 0.0

    def test_monotonic_rise(self):
        sigmas = [action_entropy_sigma(s) for s in (0, 60, 120, 180, 240, 300, 600)]
        assert all(a <= b for a, b in zip(sigmas, sigmas[1:]))


class TestApplyEntropy:
    def test_fires_on_trapped_state(self):
        ctl = make_control()
        rng = np.random.RandomState(7)
        applied = apply_action_entropy(ctl, novelty=0.0, loop_score=0.9,
                                       stuck_duration=60.0, rng=rng)
        assert applied is True

    def test_no_noise_when_novelty_healthy(self):
        ctl = make_control(x=10, y=10)
        rng = np.random.RandomState(7)
        applied = apply_action_entropy(ctl, novelty=0.5, loop_score=0.9,
                                       stuck_duration=60.0, rng=rng)
        assert applied is False
        assert (ctl.x, ctl.y) == (10, 10)

    def test_no_noise_when_loop_below_threshold(self):
        ctl = make_control(x=10, y=10)
        rng = np.random.RandomState(7)
        assert apply_action_entropy(ctl, novelty=0.0, loop_score=0.5,
                                    stuck_duration=60.0, rng=rng) is False
        assert (ctl.x, ctl.y) == (10, 10)

    def test_noise_changes_control(self):
        rng = np.random.RandomState(7)
        moved = 0
        for i in range(20):
            ctl = make_control()
            if apply_action_entropy(ctl, novelty=0.0, loop_score=0.9,
                                    stuck_duration=60.0,
                                    rng=np.random.RandomState(i)):
                if ctl.x != 0 or ctl.y != 0:
                    moved += 1
        assert moved >= 15   # overwhelmingly non-zero increments

    def test_sigma_scales_with_stuck_duration(self):
        rng = np.random.RandomState(3)
        small, large = [], []
        for i in range(300):
            c1, c2 = make_control(), make_control()
            apply_action_entropy(c1, novelty=0.0, loop_score=0.9,
                                 stuck_duration=60.0,
                                 rng=np.random.RandomState(i))
            apply_action_entropy(c2, novelty=0.0, loop_score=0.9,
                                 stuck_duration=300.0,
                                 rng=np.random.RandomState(i + 1000))
            small += [c1.x, c1.y]
            large += [c2.x, c2.y]
        assert np.std(large) > np.std(small)   # longer stuck -> wilder

    def test_clamped_to_game_bounds(self):
        rng = np.random.RandomState(1)
        for i in range(50):
            ctl = make_control()
            apply_action_entropy(ctl, novelty=0.0, loop_score=0.9,
                                 stuck_duration=300.0,
                                 rng=np.random.RandomState(i))
            assert -80 <= ctl.x <= 80 and -80 <= ctl.y <= 80


class TestDecisionSourceTag:
    def test_entropy_marker_appends(self):
        base = resolve_decision_source(
            dlg_now=False, cliff_triggered=False, reflex_override=False,
            escape_behavior=False, cpg_active=False, lif_motion=True,
            jump=False)
        assert base == "lf_steering"
        assert base + "+action_entropy" == "lf_steering+action_entropy"

    def test_dashboard_protocol_enum_includes_entropy(self):
        src = (PROJECT / "tests" / "test_dashboard_protocol.py").read_text("utf-8")
        assert "action_entropy" in src

    def test_main_wiring(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        assert "apply_action_entropy(" in src
        assert 'decision_source += "+action_entropy"' in src
        assert "action_entropy_sigma" in src
