"""P1-3 contract tests: cross-section dot-prefixed dead keys.

THE DEFECT (EVO-062 family, 8th instance)
-----------------------------------------
``skills/active_strategy.json`` is addressed by nested sections: the brain
reads ``_active_strategy["escape"]["commit_ticks"]``.  The pre-a0208e0
``BrainMutator._inject`` put **every** pid into ``strat["exploration"]``,
using the pid itself as the key, so the file gained
``exploration["escape.commit_ticks"]`` — a key no reader can ever consume.

EVO-072 fixed the same-section case (``prefix = sec + "."``), which left
every *cross-section* key untouched: 5 of them were still on disk and each
600-tick reload carried them forward forever, because the self-heal wrote
back the very payload it had loaded.  A mechanism that reports success and
cannot take effect — exactly the family these tests exist to close.

What is pinned here
-------------------
1. ``normalize_strategy_sections`` (skills/evolution_skill.py) and
   ``normalize_strategy_dot_keys`` (fly64/main.py) are cross-section aware,
   report what they dropped (with the value), and never silently keep an
   unresolvable dotted key;
2. the two implementations agree exactly — they are duplicated on purpose
   (the brain loop must not import the skills package), so drift between
   them must fail loudly;
3. the writer routes by the pid's REGISTERED section, and three simulated
   Phase 6 rounds cannot regenerate a dotted key;
4. the read end sees the registered section's explicit value, not a
   hardcoded default (executed from main.py's real reader statements);
5. the shipped ``skills/active_strategy.json`` carries no dotted key at all.
"""
from __future__ import annotations

import ast
import copy
import json
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent          # fly64/
sys.path.insert(0, str(REPO))

from skills import evolution_skill as es               # noqa: E402
from skills.evolution_skill import (                   # noqa: E402
    BrainMutator, normalize_strategy_sections)
from fly64 import main as brain_main                   # noqa: E402

MAIN = REPO / "fly64" / "main.py"
LIVE_STRATEGY = REPO / "skills" / "active_strategy.json"

# The five keys the 2026-09 live probe found inside the exploration section,
# with the values they really held (docs/analysis P1-1 probe).
REAL_DEAD_KEYS = {
    "escape.commit_ticks": 125.04821717847143,
    "escape.forward_accum_max": 0.2066931309445445,
    "escape.forward_accum_step": 0.015757426446775843,
    "escape.commit_reinforce": 0.1820265798466096,
    "escape.commit_suppress": 0.11829571149170438,
}

REAL_ESCAPE = {
    "commit_ticks": 50,
    "forward_accum_max": 0.5,
    "fallen_forward": 0.2,
    "fallen_jump_boost": 0.35,
    "fallen_switch_s": 3.0,
    "forward_accum_step": 0.005,
    "commit_reinforce": 0.15,
    "commit_suppress": 0.1,
    "escape_jump_drive": 0.45,
    "bold_turn_drive": 0.35,
}

REAL_EXPLORATION = {
    "bold_turn_bias": 0.25,
    "turn_bias": 0.25,
    "bold_explore_stuck_s": 60.0,
    "gate_jump_threshold": 3.082271242248696,
}


def dotted_keys(obj, prefix=""):
    """Every key containing '.' anywhere in the payload (root included)."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and "." in key:
                found.append(prefix + key)
            found.extend(dotted_keys(value, prefix + str(key) + "."))
    return found


def dirty_payload():
    """The exact on-disk shape the probe found (5 cross-section dead keys)."""
    strat = {
        "exploration": dict(REAL_EXPLORATION, **REAL_DEAD_KEYS),
        "escape": dict(REAL_ESCAPE),
        "__generation": 320,
    }
    return strat


def corpus():
    """Payloads covering every rule the normalizer must implement."""
    return [
        dirty_payload(),
        # EVO-072 case: same-section prefix
        {"exploration": {"exploration.gate_jump_threshold": 3.08,
                         "turn_bias": 0.25}},
        # registered-section value wins over the dead copy
        {"escape": {"commit_ticks": 50},
         "exploration": {"escape.commit_ticks": 999}},
        # literal top-level dotted key (pre-fix panel handler, D9)
        {"escape.commit_ticks": 125},
        # unresolvable prefix and a multi-dot key
        {"exploration": {"nope.foo": 1.5, "escape.a.b": 2.5}},
        # a scalar occupies the section slot
        {"exploration": {"escape.commit_ticks": 1}, "escape": 7},
        # nothing to migrate
        {"exploration": {"turn_bias": 0.25}, "__generation": 1},
    ]


SECTIONS = es.registered_sections() | {"exploration", "escape"}


# ══════════════════════════════════════════════════════════════════════
# 1. the migration rule itself
# ══════════════════════════════════════════════════════════════════════

class TestCrossSectionMigrationRule:
    def test_foreign_prefixed_key_moves_into_its_registered_section(self):
        strat = {"exploration": {"escape.commit_ticks": 125.0}}
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert strat["escape"]["commit_ticks"] == pytest.approx(125.0), (
            "the cross-section key was not moved into the section its prefix "
            "names — this is the EVO-072 blind spot")
        assert not dotted_keys(strat)
        assert report["migrated"] == ["exploration::escape.commit_ticks=125.0"]

    def test_registered_section_value_wins_and_dead_key_is_dropped(self):
        strat = {"exploration": {"escape.commit_reinforce": 0.182},
                 "escape": {"commit_reinforce": 0.15}}
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert strat["escape"]["commit_reinforce"] == pytest.approx(0.15), (
            "the dead copy overwrote the value the reader actually consumes")
        assert not dotted_keys(strat)
        assert report["dropped"] == ["exploration::escape.commit_reinforce=0.182"], (
            "the discarded value must be reported — a silent drop is how the "
            "original defect stayed invisible")

    def test_unresolvable_prefix_is_reported_and_removed_not_kept(self):
        strat = {"exploration": {"nope.foo": 1.5, "escape.a.b": 2.5}}
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert not dotted_keys(strat), (
            "a key no reader can resolve must be removed, not carried "
            "forward 'just in case'")
        assert len(report["rejected"]) == 2
        assert any("nope.foo=1.5" in e for e in report["rejected"])
        assert any("escape.a.b=2.5" in e for e in report["rejected"])

    def test_root_level_dotted_key_is_migrated_too(self):
        strat = {"escape.commit_ticks": 125}
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert strat["escape"]["commit_ticks"] == 125
        assert "escape.commit_ticks" not in strat
        assert report["migrated"] == ["<root>::escape.commit_ticks=125"]

    def test_scalar_section_slot_is_rejected_not_clobbered(self):
        strat = {"exploration": {"escape.commit_ticks": 1}, "escape": 7}
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert strat["escape"] == 7, "a scalar section slot must not be lost"
        assert not dotted_keys(strat)
        assert report["rejected"] == ["exploration::escape.commit_ticks=1"]

    def test_clean_payload_reports_nothing(self):
        strat = {"exploration": {"turn_bias": 0.25}, "__generation": 1}
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert report == {"migrated": [], "dropped": [], "rejected": []}
        assert strat == {"exploration": {"turn_bias": 0.25}, "__generation": 1}

    def test_registered_sections_are_derived_from_the_registry(self):
        sections = es.registered_sections()
        assert {"exploration", "escape", "reflex", "navigation", "coach",
                "memory"} <= sections, (
            "the section set must come from brain_tunable_params.json, not a "
            "hardcoded list, or a new section's dead keys go unseen")
        assert brain_main.strategy_section_names(REPO) == sections, (
            "the brain and the EVO writer derived different section sets")

    def test_real_probe_payload_is_cleaned_and_escape_values_survive(self):
        strat = dirty_payload()
        report = normalize_strategy_sections(strat, sections=SECTIONS)
        assert not dotted_keys(strat)
        for key, value in REAL_DEAD_KEYS.items():
            assert key not in strat["exploration"]
            assert any(key in e for e in report["dropped"]), (
                "each removed key must appear in the log with its value")
        assert strat["escape"] == REAL_ESCAPE, (
            "the escape section's explicit (registered) values must win")


# ══════════════════════════════════════════════════════════════════════
# 2. the two implementations must not drift apart
# ══════════════════════════════════════════════════════════════════════

class TestBothImplementationsAgree:
    def test_brain_and_skill_normalizers_are_equivalent(self):
        for payload in corpus():
            skill_in = copy.deepcopy(payload)
            brain_in = copy.deepcopy(payload)
            skill_report = normalize_strategy_sections(skill_in, sections=SECTIONS)
            brain_report = brain_main.normalize_strategy_dot_keys(
                brain_in, sections=SECTIONS)
            assert skill_in == brain_in, (
                "fly64/main.py and skills/evolution_skill.py migrated the "
                "same payload differently: %r vs %r" % (skill_in, brain_in))
            assert skill_report == brain_report, (
                "the two normalizers report different losses for %r" % payload)
            assert not dotted_keys(brain_in)

    def test_brain_normalizer_uses_the_registry_by_default(self):
        strat = {"exploration": {"escape.commit_ticks": 125.0}}
        report = brain_main.normalize_strategy_dot_keys(strat)
        assert strat["escape"]["commit_ticks"] == pytest.approx(125.0)
        assert report["migrated"] == ["exploration::escape.commit_ticks=125.0"]


# ══════════════════════════════════════════════════════════════════════
# 3. the writer: route by the pid's registered section, never regenerate
# ══════════════════════════════════════════════════════════════════════

def _midpoint(meta):
    lo, hi = float(meta["min"]), float(meta["max"])
    return lo if hi <= lo else lo + (hi - lo) / 2.0


class TestWriterRoutesByRegisteredSection:
    def test_registered_section_is_registry_driven(self):
        m = BrainMutator()
        assert m.registered_section("escape.commit_ticks") == "escape"
        assert m.registered_section("exploration.turn_bias") == "exploration"
        # a dotless pid is matched by leaf against the registry
        assert m.registered_section("commit_ticks") == "escape"

    def test_param_paths_are_section_qualified(self):
        m = BrainMutator()
        for pid, path in m.param_paths.items():
            assert "." in path, (
                "%s maps to a bare alias %r, which names no section — the "
                "write path cannot be re-targeted by an alias" % (pid, path))
            assert path.split(".", 1)[0] == m.registered_section(pid)
        # the exploration alias must not escape its own section
        assert m.param_paths["exploration.turn_bias"] == "exploration.turn_bias"

    def test_inject_lands_every_pid_in_its_registered_section(
            self, tmp_path, monkeypatch):
        monkeypatch.setattr(es, "SKILL_DIR", tmp_path)
        m = BrainMutator()
        strategy = {}
        monkeypatch.setattr(m, "_load_active_strategy", lambda: strategy)
        monkeypatch.setattr(m, "_write_active_strategy", lambda cfg: None)
        m._inject({pid: 1.0 for pid in m.live_params})
        assert not dotted_keys(strategy), (
            "the writer produced a dotted key: %s" % dotted_keys(strategy))
        for pid in m.live_params:
            section, leaf = pid.split(".", 1)
            assert strategy[section][leaf] == 1.0, (
                "%s did not land in its registered section" % pid)

    def test_three_phase6_rounds_cannot_regenerate_a_dotted_key(
            self, tmp_path, monkeypatch):
        """The acceptance form: run Phase 6's inject three times and assert the
        file never carries a '.' key again, while every pid still round-trips
        into its own section."""
        monkeypatch.setattr(es, "SKILL_DIR", tmp_path)
        target = tmp_path / "active_strategy.json"
        target.write_text(json.dumps(dirty_payload()), "utf-8")

        m = BrainMutator()
        pids = list(m.live_params)
        for round_no in range(1, 4):
            candidate = {pid: _midpoint(m.live_params[pid]) for pid in pids}
            m._inject(candidate)

            on_disk = json.loads(target.read_text("utf-8"))
            assert dotted_keys(on_disk) == [], (
                "round %d regenerated dead keys: %s"
                % (round_no, dotted_keys(on_disk)))
            assert on_disk["__generation"] == 320 + round_no
            for pid in pids:
                section, leaf = pid.split(".", 1)
                assert on_disk[section][leaf] == pytest.approx(candidate[pid]), (
                    "round %d: %s is not readable from %s[%s]"
                    % (round_no, pid, section, leaf))

    def test_inject_purges_the_dead_keys_it_inherited(self, tmp_path, monkeypatch):
        monkeypatch.setattr(es, "SKILL_DIR", tmp_path)
        target = tmp_path / "active_strategy.json"
        target.write_text(json.dumps(dirty_payload()), "utf-8")

        m = BrainMutator()
        # the Phase 6 rollback form: an empty candidate means "keep what the
        # file already holds", so the registered escape values must survive.
        m._inject({})

        on_disk = json.loads(target.read_text("utf-8"))
        assert not dotted_keys(on_disk), (
            "_inject carried the inherited dead keys forward instead of "
            "purging them")
        assert on_disk["escape"]["commit_ticks"] == 50, (
            "the escape section's explicit value must survive the migration "
            "(and must not be replaced by the 125.048 dead copy)")


# ══════════════════════════════════════════════════════════════════════
# 4. the read end
# ══════════════════════════════════════════════════════════════════════

class TestReadEndIsCrossSectionAware:
    def test_mutator_load_purges_cross_section_keys(self, tmp_path, monkeypatch):
        (tmp_path / "active_strategy.json").write_text(
            json.dumps(dirty_payload()), "utf-8")
        monkeypatch.setattr(es, "SKILL_DIR", tmp_path)

        strat = BrainMutator._load_active_strategy()
        assert not dotted_keys(strat)
        assert strat["escape"] == REAL_ESCAPE

    def test_brain_load_purges_cross_section_keys(self, tmp_path):
        path = tmp_path / "active_strategy.json"
        path.write_text(json.dumps(dirty_payload()), "utf-8")

        loaded = brain_main.load_active_strategy(path)
        assert not dotted_keys(loaded), (
            "the brain's loader still hands dotted keys to its readers")
        assert loaded["escape"] == REAL_ESCAPE
        assert loaded["exploration"]["turn_bias"] == pytest.approx(0.25)


# ── the real reader statements, exec'd exactly as main.py writes them ──

@lru_cache(maxsize=None)
def _main_source():
    return MAIN.read_text(encoding="utf-8")


def _statements_mentioning(*needles):
    hits = []
    for node in ast.walk(ast.parse(_main_source())):
        if not isinstance(node, (ast.Assign, ast.AugAssign)):
            continue
        text = ast.unparse(node)
        if any(needle in text for needle in needles):
            hits.append((node.lineno, text))
    return tuple(text for _lineno, text in sorted(hits))


class TestEscapeReadersUseTheEscapeSection:
    """Acceptance: escape.commit_reinforce / commit_suppress /
    forward_accum_step must read the ESCAPE section's explicit value.

    The dead keys lived in ``exploration``; a normalizer that "migrated" them
    into the section that held them would leave the reader on its default.
    Each case uses three distinct numbers — the dead copy, the registered
    value, and the reader's hardcoded fallback — so the assertion cannot pass
    by accident.
    """

    CASES = [
        # leaf, dead copy in exploration, registered escape value,
        # model attribute, reader fallback
        ("forward_accum_step", 0.0157574, 0.011, "_forward_accum_step", 0.005),
        ("commit_reinforce", 0.1820266, 0.21, "_commit_reinforce", 0.15),
        ("commit_suppress", 0.1182957, 0.13, "_commit_suppress", 0.10),
    ]

    def _loaded(self, tmp_path, escape_overrides):
        strat = dirty_payload()
        strat["escape"].update(escape_overrides)
        path = tmp_path / "active_strategy.json"
        path.write_text(json.dumps(strat), "utf-8")
        return brain_main.load_active_strategy(path)

    @pytest.mark.parametrize("leaf,dead,explicit,attr,fallback", CASES)
    def test_reader_receives_the_registered_value(
            self, tmp_path, leaf, dead, explicit, attr, fallback):
        assert explicit != dead and explicit != fallback, "test values collide"
        loaded = self._loaded(tmp_path, {leaf: explicit})
        statements = _statements_mentioning(leaf)
        assert statements, "the %s reader disappeared from main.py" % leaf

        namespace = {"_esc": loaded["escape"],
                     "_expl": loaded["exploration"],
                     "model": SimpleNamespace()}
        for statement in statements:
            exec(statement, namespace)

        got = getattr(namespace["model"], attr)
        assert got == pytest.approx(explicit), (
            "%s reached the reader as %r: the escape section holds %r but the "
            "reader used the dead copy (%r) or its fallback (%r)"
            % (leaf, got, explicit, dead, fallback))

    def test_the_dead_value_never_reaches_a_reader(self, tmp_path):
        """Negative control: with the dead keys present and the escape section
        left at its registered defaults, no reader may pick up 0.182."""
        loaded = self._loaded(tmp_path, {})
        namespace = {"_esc": loaded["escape"],
                     "_expl": loaded["exploration"],
                     "model": SimpleNamespace()}
        for statement in _statements_mentioning("commit_reinforce"):
            exec(statement, namespace)
        assert namespace["model"]._commit_reinforce == pytest.approx(0.15)
        assert namespace["model"]._commit_reinforce != pytest.approx(0.1820266)


# ══════════════════════════════════════════════════════════════════════
# 5. the shipped file
# ══════════════════════════════════════════════════════════════════════

class TestShippedStrategyFileIsClean:
    def test_no_dotted_key_in_any_section(self):
        data = json.loads(LIVE_STRATEGY.read_text("utf-8"))
        assert dotted_keys(data) == [], (
            "skills/active_strategy.json still carries dead keys: %s"
            % dotted_keys(data))

    def test_the_probed_cross_section_keys_are_gone(self):
        data = json.loads(LIVE_STRATEGY.read_text("utf-8"))
        for key in REAL_DEAD_KEYS:
            assert key not in data.get("exploration", {}), (
                "%s is still in the exploration section" % key)
            leaf = key.split(".", 1)[1]
            assert leaf in data["escape"], (
                "escape.%s vanished from the file — the migration lost the "
                "registered value instead of keeping it" % leaf)

    def test_reloading_the_shipped_file_changes_nothing(self):
        data = json.loads(LIVE_STRATEGY.read_text("utf-8"))
        report = brain_main.normalize_strategy_dot_keys(copy.deepcopy(data))
        assert report == {"migrated": [], "dropped": [], "rejected": []}, (
            "the shipped file is not yet normalized: %r" % report)
