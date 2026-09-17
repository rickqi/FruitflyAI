"""CONTRACT GUARD: every advertised coach parameter must have a consumer.

Why this file exists
--------------------
The systematic write->read audit (scripts/audit_contract_pairs.py) found that
`escape.reverse_seconds` was advertised by `SECTION_SPECS` in plugin/llm_consult.py
and explicitly demanded by the GLM prompt, was validated and persisted into
`skills/active_strategy.json` — and was read by NO component.  The brain's escape
hot-reload consumes only `stuck_threshold_s`, and the codebase's only reversal
belongs to the wall_stuck REFLEX (`ReflexController.wall_stuck_reverse_duration`),
a different mechanism with a different owner.  Git history agrees: the EVO Round 11
commit that wired the coach's keys lists bold_explore_stuck_s / turn_bias /
escape.stuck_threshold_s — never this one.

Effect while it lived: the coach spent prompt budget and reasoning tuning a knob
that could not change behaviour, and the operator panel offered a slider with no
effect.  That is the same "mechanism exists, reports success, cannot take effect"
family this session hit seven times.

Rather than fixing that one key by hand, this module converts the finding into an
enforced contract: `SECTION_SPECS` is the list of parameters the coach is TOLD it
may tune, so every key in it must appear in a READ context in the brain.  A future
dead knob now fails here instead of silently wasting the coach's attention.
"""
import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from plugin.llm_consult import SECTION_SPECS  # noqa: E402

#: modules that consume coach-tuned strategy parameters
CONSUMER_MODULES = [
    REPO_ROOT / "fly64" / "main.py",
    REPO_ROOT / "fly64" / "memory.py",
    REPO_ROOT / "fly64" / "model.py",
]

#: keys that may be advertised without a *literal* read site because their
#: consumer looks them up through a loop variable over an explicit name tuple.
#: Each entry must name the file and the tuple; verify with the audit tool.
LOOP_CONSUMED = {
    # ("section", "key"): "why",
}


def _read_keys(path):
    """String literals used in a READ position inside one module."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))

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
        parent = v.parents.get(node)
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute):
            if parent.func.attr == "get" and node in parent.args:
                found.add(node.value)
        elif isinstance(parent, ast.Subscript) and parent.slice is node:
            if isinstance(parent.ctx, ast.Load):
                found.add(node.value)
        elif isinstance(parent, ast.Compare) and node in parent.comparators:
            found.add(node.value)
    return found


@pytest.fixture(scope="module")
def consumed():
    keys = set()
    for m in CONSUMER_MODULES:
        if m.exists():
            keys |= _read_keys(m)
    return keys


class TestEveryAdvertisedKeyHasAConsumer:
    def test_no_dead_knob_is_advertised(self, consumed):
        dead = []
        for section, spec in SECTION_SPECS.items():
            for key in spec:
                if key in consumed:
                    continue
                if (section, key) in LOOP_CONSUMED:
                    continue
                dead.append("%s.%s" % (section, key))
        assert not dead, (
            "SECTION_SPECS advertises parameter(s) the brain never reads: %s — "
            "the coach would be asked to tune a no-op. Either wire the consumer "
            "or remove the key (see escape.reverse_seconds, EVO-066)." % dead)

    def test_reverse_seconds_is_gone(self):
        """The specific dead knob that motivated this guard."""
        assert "reverse_seconds" not in SECTION_SPECS.get("escape", {}), (
            "escape.reverse_seconds has no consumer; re-adding it without a "
            "consumer re-opens the dead-knob defect")

    def test_prompt_example_matches_the_spec(self):
        """The prompt's example JSON must not advertise keys the spec rejects."""
        src = (REPO_ROOT / "plugin" / "llm_consult.py").read_text(encoding="utf-8")
        assert '"reverse_seconds"' not in src, (
            "the prompt still asks the coach for reverse_seconds")

    def test_each_section_retains_its_wired_keys(self):
        """Guard against over-removal: only consumed keys stay advertised."""
        expected = {
            # `mode` is the only fallen_recovery key the behaviour reads;
            # climb_period / persist_seconds have no consumer (see SPEC comment)
            "fallen_recovery": {"mode"},
            "exploration": {"bold_explore_stuck_s", "turn_bias"},
            "escape": {"stuck_threshold_s"},
        }
        for section, keys in expected.items():
            assert set(SECTION_SPECS[section]) == keys, (
                "%s spec drifted: %s" % (section, sorted(SECTION_SPECS[section])))

    def test_the_known_dead_knobs_are_all_gone(self):
        """The three knobs the audit found with no consumer, in one place."""
        dead = {"reverse_seconds", "climb_period", "persist_seconds"}
        advertised = {k for spec in SECTION_SPECS.values() for k in spec}
        assert not (advertised & dead), (
            "dead knob(s) advertised again: %s" % sorted(advertised & dead))


class TestSanitizerDropsTheDeadKey:
    def test_incoming_reverse_seconds_is_dropped(self):
        from plugin.llm_consult import sanitize_strategy
        out = sanitize_strategy({"escape": {"stuck_threshold_s": 12.0,
                                           "reverse_seconds": 0.9}})
        assert "reverse_seconds" not in out.get("escape", {}), (
            "a stale coach response could reintroduce the dead key")
        assert out["escape"]["stuck_threshold_s"] == 12.0

    def test_existing_strategy_file_self_cleans_on_rewrite(self):
        """The next write drops the key, so no migration is needed."""
        from plugin.llm_consult import sanitize_strategy
        out = sanitize_strategy({"escape": {"stuck_threshold_s": 5.0,
                                           "reverse_seconds": 0.5},
                                 "exploration": {"turn_bias": 0.7}})
        assert set(out["escape"]) == {"stuck_threshold_s"}
        assert set(out["exploration"]) == {"bold_explore_stuck_s", "turn_bias"}


class TestAuditToolIsPresent:
    def test_audit_script_exists(self):
        assert (REPO_ROOT / "scripts" / "audit_contract_pairs.py").exists(), (
            "the systematic write->read auditor must stay in the repo so this "
            "class of defect is found mechanically rather than by hand")
