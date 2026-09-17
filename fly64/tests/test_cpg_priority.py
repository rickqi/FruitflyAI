#!/usr/bin/env python3
"""t25 regression: LIF-competition-first decision priority.

The CPG primitive cascade must NOT override the LIF network's movement
decision: when the motor pools drive (|x|>8 or |y|>8) decision_source is
lf_steering / lf_escape; the hardcoded primitive takes the stick only on
~zero LIF output.  Also verifies the run-loop phase block keeps its stick
when the LIF is driving (merge, not clobber).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fly64.main import LIF_MOTION_MIN, resolve_decision_source  # noqa: E402

BASE = dict(dlg_now=False, cliff_triggered=False, reflex_override=False,
            escape_behavior=False, cpg_active=True,
            cpg_primitive="longjump", jump=False)


class TestLifPriority:
    def test_lif_steering_beats_cpg(self):
        out = resolve_decision_source(**BASE, lif_motion=True)
        assert out == "lf_steering"

    def test_lif_escape_beats_cpg_and_steering(self):
        out = resolve_decision_source(**{**BASE, "escape_behavior": True},
                                      lif_motion=True)
        assert out == "lf_escape"

    def test_zero_lif_output_cpg_takes_over(self):
        out = resolve_decision_source(**BASE, lif_motion=False)
        assert out.startswith("cpg_primitive:")
        assert "longjump" in out

    def test_zero_lif_no_cpg_falls_through(self):
        base = {k: v for k, v in BASE.items() if k != "jump"}
        base["cpg_active"] = False
        out = resolve_decision_source(**base, lif_motion=False, jump=True)
        assert out == "jump"
        out2 = resolve_decision_source(**base, lif_motion=False)
        assert out2 == "steering"

    def test_safety_reflexes_outrank_everything(self):
        assert resolve_decision_source(**{**BASE, "dlg_now": True},
                                       lif_motion=True) == "dialogue"
        assert resolve_decision_source(**{**BASE, "cliff_triggered": True},
                                       lif_motion=True) == "cliff_reflex"
        assert resolve_decision_source(**{**BASE, "reflex_override": True},
                                       lif_motion=True) == "anomaly_reflex"

    def test_escape_with_zero_lif_reports_plain_escape(self):
        out = resolve_decision_source(**{**BASE, "escape_behavior": True},
                                      lif_motion=False)
        assert out == "escape"

    def test_threshold_constant(self):
        assert LIF_MOTION_MIN == 8


class TestRunLoopWiring:
    def test_phase_block_keeps_stick_when_lif_drives(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        # LIF priority: phase application is gated on ~zero LIF output
        assert "if not _lif_motion:" in src
        assert "control = cpg_apply_phase(control, cpg_phase)" in src
        # gates fire whenever a phase is active (single call, both paths)
        assert src.count("model.set_cpg_gate(") >= 2
        # attribution delegates to the pure helper
        assert "resolve_decision_source(" in src
        assert "_lif_motion = (abs(control.x) > LIF_MOTION_MIN" in src

    def test_decision_source_before_phase_sampled(self):
        # _lif_motion must be sampled BEFORE cpg_apply_phase can clobber
        # control — source order assertion (sample < apply).
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        sample = src.index("_lif_motion = (abs(control.x) > LIF_MOTION_MIN")
        apply_ = src.index("control = cpg_apply_phase(control, cpg_phase)")
        assert sample < apply_