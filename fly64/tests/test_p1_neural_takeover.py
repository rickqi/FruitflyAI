#!/usr/bin/env python3
"""P1 neural-takeover PIN regression tests (Brain v2.8.0, agent.md rule 8).

P1 deleted 11 A-class Python bypasses + B10 sigmoid + C10 constant split.
These tests pin that each deleted behaviour is now owned by the neural
substrate (or a documented safety guardrail), entirely offline via
importlib.util.spec_from_file_location loading.

Covers:
1. A-point deletions really gone from main.py (escape five-stage FSM,
   bold-explore override, health<0.3 boost, legacy dialogue pulse,
   corollary-discharge mirror turn, duplicate flow modulation).
2. Neural takeovers present in model.py (adaptive escape_current,
   CX steering injection, sigmoid novelty gain — monotonic & bounded).
3. Dialogue behaviour ownership: LLM pause-wait + habituation guardrail
   only; no legacy pulse-A fallback on either side.
4. C10: sensory vs behavioural enclosure constants are separate names.
5. KPI baseline: behaviour-level direct control-write count in main.py.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parent.parent
MAIN_PATH = PROJECT / "fly64" / "main.py"
MODEL_PATH = PROJECT / "fly64" / "model.py"
RETINA_PATH = PROJECT / "fly64" / "retina.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def main_src():
    return MAIN_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def model_src():
    return MODEL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def retina_src():
    return RETINA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def brain_main():
    pkg = "fly64_p1_brain"
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [str(PROJECT / "fly64")]
        sys.modules[pkg] = m
    name = pkg + ".main"
    if name not in sys.modules:
        _load_module(name, MAIN_PATH)
    return sys.modules[name]


# ── 1. A-class deletions really gone ────────────────────────────────────

def _code_only(src: str) -> str:
    """Strip comments so deleted-symbol checks look at code, not docs."""
    out = []
    for line in src.splitlines():
        # crude but sufficient: cut at first # not inside a string literal
        cut = len(line)
        in_str = None
        for i, ch in enumerate(line):
            if in_str:
                if ch == in_str:
                    in_str = None
            elif ch in "\"'":
                in_str = ch
            elif ch == "#":
                cut = i
                break
        out.append(line[:cut])
    return "\n".join(out)


class TestAClassDeletions:
    def test_escape_five_stage_fsm_deleted(self, main_src):
        code = _code_only(main_src)
        assert "escape_toggle_timer" not in code
        assert "escape_x" not in code

    def test_bold_explore_override_deleted(self, main_src):
        code = _code_only(main_src)
        assert "bold_override" not in code
        # forced_bold_explore survives only as a neural drive flag /
        # telemetry — never as a direct control write
        for m in re.finditer(r".*forced_bold_explore.*", code):
            line = m.group(0)
            assert "control." not in line, line

    def test_health_boost_branch_deleted(self, main_src):
        code = _code_only(main_src)
        assert "_health < 0.3" not in code
        assert "control.x * 1.5" not in code

    def test_legacy_dialogue_pulse_deleted(self, main_src, model_src):
        assert "_dialogue_pulse" not in _code_only(model_src)
        assert "_dlg_t" not in _code_only(main_src)

    def test_corollary_discharge_mirror_turn_deleted(self, main_src):
        code = _code_only(main_src)
        assert "_cmd_fail_frames" not in code
        assert "// 30) % 2" not in code
        # any step_count//20 alternation left must be the habituation
        # guardrail (dialogue_blocked_until), not a movement bypass
        for m in re.finditer(r".*// 20\) % 2.*", code):
            ctx = code[:m.start()][-500:]
            assert "dialogue_blocked_until" in ctx

    def test_duplicate_flow_modulation_deleted(self, main_src):
        code = _code_only(main_src)
        assert "flow_looming > 0.4" not in code
        assert "min(control.x" not in code and "max(control.x" not in code

    def test_motion_asym_legacy_fallback_deleted(self, main_src):
        # true_asymmetry may remain only for telemetry (escape reason
        # label), never driving a control write
        code = _code_only(main_src)
        for m in re.finditer(r".*true_asymmetry.*", code):
            assert "control." not in m.group(0), m.group(0)


# ── 2. Neural takeovers present ─────────────────────────────────────────

class TestNeuralTakeover:
    def test_adaptive_escape_current_present(self, model_src):
        assert "self.escape_current" in model_src
        # adaptive ramp-up/decay, not a constant kick
        assert re.search(r"escape_current \* 1\.0[0-9]", model_src)
        assert re.search(r"escape_current \* 0\.9[0-9]", model_src)

    def test_escape_current_drives_motor_pool(self, model_src):
        assert re.search(r"v\[self\.motor_nodes\] \+= self\.escape_current",
                         model_src)

    def test_cx_steering_injection_present(self, model_src):
        assert "cx.update(" in model_src
        assert re.search(r"v\[self\.turn_left\] \+= cx_bias", model_src)
        assert re.search(r"v\[self\.turn_right\] -= cx_bias", model_src)

    def test_novelty_feeds_cx(self, model_src):
        assert re.search(r"cx\.update\([^)]*novelty", model_src, re.DOTALL)

    def test_sigmoid_replaces_piecewise(self, model_src):
        # B10: tanh-sigmoid novelty gain, no piecewise branches left
        assert "np.tanh" in model_src
        assert "0.10 if novelty" not in model_src
        assert "-0.10 if novelty" not in model_src

    def test_sigmoid_monotonic_and_bounded(self, model_src):
        m = re.search(r"novelty_gain\s*=\s*(.+)", model_src)
        assert m, "novelty_gain formula not found"
        expr = m.group(1).strip()
        novelty = np.linspace(0.0, 1.0, 101)
        gains = np.array([eval(expr, {"np": np, "novelty": float(n)})
                          for n in novelty])
        assert np.all(np.diff(gains) <= 1e-12), "gain must be monotonic down"
        assert gains.min() >= 0.8 and gains.max() <= 1.2, "bounded gain"
        assert gains[0] == pytest.approx(1.10, abs=0.01)   # novel → boost
        assert gains[-1] == pytest.approx(0.90, abs=0.01)  # familiar → damp


# ── 3. Dialogue ownership (LLM branch + guardrail only) ────────────────

class TestDialogueOwnership:
    def test_llm_pause_wait_branch_kept(self, main_src, brain_main):
        assert brain_main.DIALOGUE_LLM_WAIT_S == 600.0
        assert "write_dialogue_decision" in main_src
        assert "consult_dialogue" in main_src

    def test_habituation_guardrail_kept(self, main_src):
        assert "dialogue_blocked_until" in main_src
        assert "dialogue_engagements >= 3" in main_src

    def test_no_python_dialogue_a_pulse(self, main_src, model_src):
        # The A press now comes only from the LLM decision (press ticks)
        # or the 600s belt-and-braces fallback — never a blind Python pulse.
        assert "_dialogue_pulse" not in _code_only(model_src)
        assert "_dlg_t" not in _code_only(main_src)


# ── 4. C10 constant split ───────────────────────────────────────────────

class TestC10ConstantSplit:
    def test_two_named_constants(self, retina_src):
        assert "ENCLOSURE_INDOOR_SENSORY_THRESHOLD" in retina_src
        assert "ENCLOSURE_INDOOR_OVERRIDE_THRESHOLD" in retina_src

    def test_sensory_flag_separate_from_override(self, retina_src):
        assert re.search(r"enclosure_sensory\s*=.*SENSORY_THRESHOLD", retina_src)
        assert re.search(r"OVERRIDE_THRESHOLD", retina_src)

    def test_behaviour_unchanged_same_values(self, retina_src):
        # P1 pins both at the historical 0.35 — pure refactor, zero drift
        vals = re.findall(r"(?:SENSORY|OVERRIDE)_THRESHOLD = ([0-9.]+)",
                          retina_src)
        assert vals and all(v == "0.35" for v in vals)


# ── 5. KPI baseline (t9 metric: behaviour-level control writes) ─────────

class TestKpiBaseline:
    # Sanctioned post-P1 increments (each landed via an EVO round with its own
    # tests + history record; see skills/evolution_history.json):
    #   2.4.0  MHR-1  dialogue LLM decision press paths        (+4)
    #   R28/EVO below-ground safety guardrail (jump burst)     (+4)
    #   2.15.0 CPG primitive cascade apply (apply_phase)       (+1)
    # P1 baseline (2026-09-14): 18 lines / 18 assignments
    # (down from pre-P1 45 / 53); budget raised accordingly.
    KPI_LINES = 26
    KPI_ASSIGNMENTS = 26

    def test_control_write_count_shrunk(self, main_src):
        lines = main_src.splitlines()
        write_lines = [i + 1 for i, l in enumerate(lines)
                       if re.search(r"\bcontrol\.\w+\s*=[^=]", l)]
        assignments = re.findall(r"\bcontrol\.\w+\s*=[^=]", main_src)
        assert len(write_lines) <= self.KPI_LINES, f"write lines {len(write_lines)}"
        assert len(assignments) <= self.KPI_ASSIGNMENTS, f"assignments {len(assignments)}"
        print(f"\n[KPI] main.py direct control writes after P1: "
              f"{len(write_lines)} lines / {len(assignments)} assignments "
              f"(pre-P1: 45 / 53; sanctioned budget: {self.KPI_LINES})")

    def test_remaining_writes_are_guardrails_or_llm(self, main_src):
        # Every remaining write site must sit inside a documented safety
        # branch: cliff reflex, dialogue blocked/Llm branch, reflex control.
        lines = main_src.splitlines()
        for n in (i + 1 for i, l in enumerate(lines)
                  if re.search(r"\bcontrol\.\w+\s*=[^=]", l)):
            ctx = "\n".join(lines[max(0, n - 60):n])
            assert any(k in ctx for k in (
                "dialogue_blocked_until", "llm_decision", "cliff",
                "reflex", "escape", "LLM pause-wait", "cpg_phase",
                "below-ground", "below_ground")), (
                f"line {n}: control write outside a known branch")


# ── 6. Version forward-compat ───────────────────────────────────────────

class TestVersion:
    def test_brain_version_at_least_2_8(self, brain_main):
        parts = [int(p) for p in brain_main.BRAIN_VERSION.split(".")]
        assert parts >= [2, 8, 0], brain_main.BRAIN_VERSION


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
