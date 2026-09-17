"""CONTRACT GUARD: the tunable-parameter schema must separate wired from inert.

The systematic audit found that 14 of the 21 parameters advertised by
`skills/brain_tunable_params.json` have ZERO occurrences anywhere in fly64/ or
plugin/ source — verified both by AST read-site extraction and by a repo-wide
identifier grep:

    escape.commit_reinforce, escape.commit_suppress, escape.forward_accum_step,
    exploration.breakout_forward_bias, exploration.cliff_tangent_gain,
    exploration.dopamine_revisit_cost, exploration.gate_forward_threshold,
    exploration.gate_jump_threshold, exploration.loop_breakout_threshold,
    exploration.revisit_penalty_scale, exploration.stuck_ramp_cooldown,
    exploration.visual_gain_novelty_boost, reflex.adaptive_cooldown_scale,
    reflex.cooldown_min

They are aspirational names authored ahead of the implementation (the reflex
actually has `cooldown_duration`; the gate thresholds do not exist at all).

Impact while unmarked:
  * the operator panel offered 21 sliders, 14 of which could not do anything,
    and reported a check mark when they were moved;
  * BrainMutator/Phase 6 mutated all 21, so roughly two thirds of its search
    dimensions were pure noise and a trial's fitness delta could not be
    attributed to the parameters that actually moved behaviour.

These tests pin the separation and prevent an unwired knob from silently
re-entering the search space or the UI.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "skills" / "brain_tunable_params.json"
CONSUMERS = ["fly64/main.py", "fly64/memory.py", "fly64/model.py",
             "fly64/central_complex.py"]

sys.path.insert(0, str(REPO_ROOT))


def _schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _read_string_keys(rel):
    p = REPO_ROOT / rel
    if not p.exists():
        return set()
    tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))

    class V(ast.NodeVisitor):
        def __init__(self):
            self.parents = {}

        def generic_visit(self, n):
            for c in ast.iter_child_nodes(n):
                self.parents[c] = n
                self.visit(c)

    v = V()
    v.visit(tree)
    found = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        par = v.parents.get(node)
        if isinstance(par, ast.Call) and isinstance(par.func, ast.Attribute):
            if par.func.attr in ("get", "pop") and node in par.args:
                found.add(node.value)
        elif isinstance(par, ast.Subscript) and par.slice is node:
            if isinstance(par.ctx, ast.Load):
                found.add(node.value)
    return found


@pytest.fixture(scope="module")
def consumed():
    keys = set()
    for rel in CONSUMERS:
        keys |= _read_string_keys(rel)
    return keys


class TestSchemaMarksWiring:
    def test_every_param_declares_wiring(self):
        missing = [pid for pid, m in _schema()["params"].items()
                   if not isinstance(m, dict) or "wired" not in m]
        assert not missing, (
            "param(s) without an explicit wired flag: %s — the BrainMutator "
            "and the panel both read it" % missing)

    def test_schema_documents_the_meaning(self):
        note = _schema().get("wired_note", "")
        assert "wired" in note and "active_strategy" in note


class TestWiredFlagMatchesReality:
    def test_every_wired_param_has_a_consumer(self, consumed):
        bad = []
        for pid, meta in _schema()["params"].items():
            if not meta.get("wired"):
                continue
            leaf = pid.split(".")[-1]
            aliases = meta.get("aliases") or []
            if leaf in consumed or any(a in consumed for a in aliases):
                continue
            bad.append(pid)
        assert not bad, (
            "param(s) marked wired=true have no reader in the brain: %s — "
            "either the flag is wrong or the consumer was lost" % bad)

    def test_the_known_unwired_set_is_marked_unwired(self):
        params = _schema()["params"]
        still_wired = [pid for pid in KNOWN_UNWIRED if params.get(pid, {}).get("wired")]
        assert not still_wired, (
            "these were verified to have no consumer; flipping them to wired "
            "requires adding a real consumer first: %s" % still_wired)

    def test_wired_set_is_exactly_the_verified_seven(self):
        params = _schema()["params"]
        wired = {pid for pid, m in params.items() if m.get("wired")}
        assert wired == KNOWN_WIRED, (
            "the wired set changed: %s" % sorted(wired ^ KNOWN_WIRED))


KNOWN_WIRED = {
    "escape.commit_ticks",
    "escape.fallen_forward",
    "escape.fallen_jump_boost",
    "escape.fallen_switch_s",
    "escape.forward_accum_max",
    "exploration.bold_explore_stuck_s",
    "exploration.turn_bias",
}
KNOWN_UNWIRED = {
    "escape.commit_reinforce", "escape.commit_suppress",
    "escape.forward_accum_step", "exploration.breakout_forward_bias",
    "exploration.cliff_tangent_gain", "exploration.dopamine_revisit_cost",
    "exploration.gate_forward_threshold", "exploration.gate_jump_threshold",
    "exploration.loop_breakout_threshold", "exploration.revisit_penalty_scale",
    "exploration.stuck_ramp_cooldown", "exploration.visual_gain_novelty_boost",
    "reflex.adaptive_cooldown_scale", "reflex.cooldown_min",
}


class TestMutatorSearchSpaceIsWiredOnly:
    def test_live_params_excludes_unwired(self):
        from skills.evolution_skill import BrainMutator
        live = set(BrainMutator().live_params)
        assert live == KNOWN_WIRED, (
            "Phase 6 would search over non-wired params: %s"
            % sorted(live ^ KNOWN_WIRED))

    def test_generate_candidate_only_emits_wired(self):
        from skills.evolution_skill import BrainMutator
        cand = BrainMutator().generate_candidate()
        assert set(cand) == KNOWN_WIRED, (
            "candidate includes params that cannot affect behaviour: %s"
            % sorted(set(cand) - KNOWN_WIRED))

    def test_param_paths_only_covers_wired(self):
        from skills.evolution_skill import BrainMutator
        assert set(BrainMutator().param_paths) == KNOWN_WIRED

    def test_inject_does_not_write_unwired_into_the_strategy(self, tmp_path,
                                                             monkeypatch):
        from skills import evolution_skill as es
        m = es.BrainMutator()
        strategy = {}
        monkeypatch.setattr(m, "_load_active_strategy", lambda: strategy)
        monkeypatch.setattr(m, "_write_active_strategy", lambda cfg: None)
        m._inject({pid: 1.0 for pid in KNOWN_WIRED})
        written = {f"{s}.{k}" for s, sec in strategy.items()
                   if isinstance(sec, dict) and s != "__generation"
                   for k in sec}
        assert not (written & KNOWN_UNWIRED), (
            "unwired params were written into active_strategy: %s"
            % sorted(written & KNOWN_UNWIRED))
        assert written == KNOWN_WIRED, sorted(written)


class TestPanelMarksInertSliders:
    def test_panel_reads_the_wired_flag(self):
        src = (REPO_ROOT / "web" / "evo-params.html").read_text(encoding="utf-8")
        assert "meta.wired" in src, (
            "the panel ignores the wired flag, so it would again offer inert "
            "sliders that report success")

    def test_panel_disables_inert_sliders(self):
        src = (REPO_ROOT / "web" / "evo-params.html").read_text(encoding="utf-8")
        assert "range.disabled=true" in src.replace(" ", ""), (
            "inert params must be disabled, not silently draggable")

    def test_panel_surfaces_the_inert_count(self):
        src = (REPO_ROOT / "web" / "evo-params.html").read_text(encoding="utf-8")
        assert "未接线" in src, "the panel must label inert params for the operator"
