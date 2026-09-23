"""RULE-19 contract tests: active_strategy.json key normalization & writer merge.

EVO-072: the "dead key" defect family (EVO-062 同族) — EVO evolved params were
written as dot-prefixed flat keys inside sections (e.g.
``exploration["exploration.gate_jump_threshold"]``) while the brain reader
consumes clean keys (``exploration["gate_jump_threshold"]``).  Mechanism
existed, reported success, could not take effect.

P1-3 (defect family #8): the EVO-072 migration used ``prefix = sec + "."`` and
therefore only ever saw a *same-section* dead key.  A key written by the
pre-a0208e0 writer — which put every pid into the exploration section —
carries a FOREIGN prefix (``exploration["escape.commit_ticks"]``) and was
never migrated and never deleted.  The migration is now cross-section aware
(``normalize_strategy_sections``) and reports what it drops; the exhaustive
matrix lives in ``test_cross_section_keys.py``.

Pins:
  1. BrainMutator._load_active_strategy migrates dot-prefixed keys -> clean.
  2. Cross-section keys move into the section their prefix names, and the
     registered section's explicit value wins.
  3. Coach StrategyWriter.write_strategy MERGES with the on-disk file so
     EVO-owned keys (__generation, evolved params) survive coach writes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from skills.evolution_skill import (  # noqa: E402
    BrainMutator, normalize_strategy_sections)
from plugin.strategy_writer import StrategyWriter  # noqa: E402


class TestEvoKeyNormalization:
    """BrainMutator._load_active_strategy must migrate dot-prefixed dead keys."""

    def test_dot_prefixed_key_migrated_to_clean(self, tmp_path, monkeypatch):
        raw = {
            "exploration": {
                "exploration.gate_jump_threshold": 3.08,
                "turn_bias": 0.25,
            },
            "__generation": 142,
        }
        target = tmp_path / "active_strategy.json"
        target.write_text(json.dumps(raw), "utf-8")
        monkeypatch.setattr(
            "skills.evolution_skill.SKILL_DIR", tmp_path)

        strat = BrainMutator._load_active_strategy()
        expl = strat["exploration"]
        # clean key present with the evolved value
        assert expl["gate_jump_threshold"] == pytest.approx(3.08)
        # dead key removed
        assert "exploration.gate_jump_threshold" not in expl
        # untouched sibling keys survive
        assert expl["turn_bias"] == pytest.approx(0.25)
        assert strat["__generation"] == 142

    def test_clean_key_wins_over_dead_key(self, tmp_path, monkeypatch):
        raw = {
            "exploration": {
                "exploration.gate_jump_threshold": 3.08,  # dead
                "gate_jump_threshold": 1.5,               # live
            },
        }
        target = tmp_path / "active_strategy.json"
        target.write_text(json.dumps(raw), "utf-8")
        monkeypatch.setattr("skills.evolution_skill.SKILL_DIR", tmp_path)

        strat = BrainMutator._load_active_strategy()
        assert strat["exploration"]["gate_jump_threshold"] == pytest.approx(1.5)
        assert "exploration.gate_jump_threshold" not in strat["exploration"]

    def test_corrupt_file_falls_back(self, tmp_path, monkeypatch):
        target = tmp_path / "active_strategy.json"
        target.write_text("{not json", "utf-8")
        monkeypatch.setattr("skills.evolution_skill.SKILL_DIR", tmp_path)
        strat = BrainMutator._load_active_strategy()
        assert strat == {"exploration": {}}

    def test_inject_writes_clean_key_readable_by_brain(self, tmp_path, monkeypatch):
        """End-to-end: _inject must produce a file whose gate_jump_threshold is
        readable by the brain's _expl.get("gate_jump_threshold") consumer."""
        raw = {
            "exploration": {
                "exploration.gate_jump_threshold": 3.08,
            },
        }
        target = tmp_path / "active_strategy.json"
        target.write_text(json.dumps(raw), "utf-8")
        monkeypatch.setattr("skills.evolution_skill.SKILL_DIR", tmp_path)

        mutator = BrainMutator()  # real schema: gate_jump_threshold is wired
        assert "exploration.gate_jump_threshold" in mutator.live_params
        mutator._inject({"exploration.gate_jump_threshold": 0.8})

        on_disk = json.loads(target.read_text("utf-8"))
        # brain consumer path: _expl.get("gate_jump_threshold")
        expl = on_disk["exploration"]
        assert expl.get("gate_jump_threshold") == pytest.approx(0.8)
        assert "exploration.gate_jump_threshold" not in expl


class TestCrossSectionDeadKeys:
    """P1-3: a dead key whose prefix names ANOTHER section must not survive.

    The live probe (docs/analysis P1-1) found five of them in the exploration
    section; because the EVO-072 migration only stripped ``sec + "."`` they
    were never migrated and never deleted.  These pin the read end (the
    loader) and the reporting contract (the migration must be visible).
    """

    DEAD = {
        "escape.commit_ticks": 125.04821717847143,
        "escape.forward_accum_max": 0.2066931309445445,
        "escape.forward_accum_step": 0.015757426446775843,
        "escape.commit_reinforce": 0.1820265798466096,
        "escape.commit_suppress": 0.11829571149170438,
    }

    def _write(self, tmp_path, raw):
        target = tmp_path / "active_strategy.json"
        target.write_text(json.dumps(raw), "utf-8")
        return target

    def test_load_moves_cross_section_key_into_its_registered_section(
            self, tmp_path, monkeypatch):
        raw = {"exploration": {"escape.commit_ticks": 125.0},
               "__generation": 320}
        self._write(tmp_path, raw)
        monkeypatch.setattr("skills.evolution_skill.SKILL_DIR", tmp_path)

        strat = BrainMutator._load_active_strategy()
        assert strat["escape"]["commit_ticks"] == pytest.approx(125.0), (
            "the cross-section key was not routed to the section its prefix "
            "names (reader: _esc.get('commit_ticks'))")
        assert "escape.commit_ticks" not in strat["exploration"]
        assert strat["__generation"] == 320

    def test_registered_section_value_wins_over_the_dead_copy(
            self, tmp_path, monkeypatch):
        raw = {"exploration": {"escape.commit_reinforce": 0.182},
               "escape": {"commit_reinforce": 0.15}}
        self._write(tmp_path, raw)
        monkeypatch.setattr("skills.evolution_skill.SKILL_DIR", tmp_path)

        strat = BrainMutator._load_active_strategy()
        assert strat["escape"]["commit_reinforce"] == pytest.approx(0.15), (
            "the dead copy overwrote the value the reader consumes")
        assert "escape.commit_reinforce" not in strat["exploration"]

    def test_no_section_keeps_a_dotted_key_after_loading(
            self, tmp_path, monkeypatch):
        self._write(tmp_path, {
            "exploration": dict(self.DEAD, turn_bias=0.25),
            "escape": {"commit_ticks": 50},
        })
        monkeypatch.setattr("skills.evolution_skill.SKILL_DIR", tmp_path)

        strat = BrainMutator._load_active_strategy()
        leftovers = [k for sec in strat.values() if isinstance(sec, dict)
                     for k in sec if isinstance(k, str) and "." in k]
        assert leftovers == [], "dotted keys survived the load: %s" % leftovers

    def test_the_five_probe_keys_are_reported_with_their_values(self):
        """The migration must be visible: each dropped key is logged with the
        value it held, never silently discarded."""
        # the shipped escape section already carries all five leaves, so the
        # probe's dead copies are discarded (not migrated) — the reader keeps
        # reading the registered value.
        raw = {"exploration": dict(self.DEAD),
               "escape": {"commit_ticks": 50, "forward_accum_max": 0.5,
                          "forward_accum_step": 0.005,
                          "commit_reinforce": 0.15,
                          "commit_suppress": 0.1}}
        report = normalize_strategy_sections(raw)

        assert report["migrated"] == []
        assert len(report["dropped"]) == len(self.DEAD)
        for key, value in self.DEAD.items():
            expected = "exploration::%s=%r" % (key, value)
            assert expected in report["dropped"], (
                "the dropped value %r is not in the log: %s"
                % (expected, report["dropped"]))
        assert "escape.commit_ticks" not in raw["exploration"]
        assert raw["escape"]["commit_ticks"] == 50
        assert raw["escape"]["commit_reinforce"] == pytest.approx(0.15)


class TestCoachMergePreservesEvo:
    """Coach write_strategy must merge, not wholesale-replace."""

    def _writer(self, tmp_path):
        return StrategyWriter(
            strategy_path=tmp_path / "active_strategy.json",
            advice_path=tmp_path / "coach_advice.json",
        )

    def test_evo_generation_survives_coach_write(self, tmp_path):
        existing = {
            "exploration": {"gate_jump_threshold": 0.8, "turn_bias": 0.25},
            "__generation": 143,
        }
        (tmp_path / "active_strategy.json").write_text(
            json.dumps(existing), "utf-8")

        w = self._writer(tmp_path)
        # coach only mentions turn_bias — EVO's gate_jump must survive
        w.write_strategy({"exploration": {"turn_bias": 0.10}},
                         advice="lower turn bias")

        on_disk = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        assert on_disk["__generation"] == 143
        assert on_disk["exploration"]["gate_jump_threshold"] == pytest.approx(0.8)
        # coach key wins in the merged section
        assert on_disk["exploration"]["turn_bias"] == pytest.approx(0.10)
        # coach metadata present
        assert "coach_advice" in on_disk
        assert on_disk["source"].startswith("glm")

    def test_new_section_from_coach_is_added(self, tmp_path):
        (tmp_path / "active_strategy.json").write_text(
            json.dumps({"__generation": 1}), "utf-8")
        w = self._writer(tmp_path)
        w.write_strategy({"escape": {"commit_ticks": 50}}, advice="x")
        on_disk = json.loads(
            (tmp_path / "active_strategy.json").read_text("utf-8"))
        assert on_disk["escape"]["commit_ticks"] == 50

    def test_no_existing_file_coach_stands_alone(self, tmp_path):
        w = self._writer(tmp_path)
        out = w.write_strategy({"exploration": {"turn_bias": 0.2}}, advice="a")
        assert out["exploration"]["turn_bias"] == pytest.approx(0.2)
