"""RULE-19 contract tests: active_strategy.json key normalization & writer merge.

EVO-072: the "dead key" defect family (EVO-062 同族) — EVO evolved params were
written as dot-prefixed flat keys inside sections (e.g.
``exploration["exploration.gate_jump_threshold"]``) while the brain reader
consumes clean keys (``exploration["gate_jump_threshold"]``).  Mechanism
existed, reported success, could not take effect.

Pins:
  1. BrainMutator._load_active_strategy migrates dot-prefixed keys -> clean.
  2. Coach StrategyWriter.write_strategy MERGES with the on-disk file so
     EVO-owned keys (__generation, evolved params) survive coach writes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from skills.evolution_skill import BrainMutator  # noqa: E402
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
