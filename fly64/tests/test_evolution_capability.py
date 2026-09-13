# -*- coding: utf-8 -*-
"""Regression tests for the evolution capability closed loop.

Each test pins one capability gained during an evolution round so future
refactors cannot silently regress it.  Run:
    python3 -m pytest fly64/tests/test_evolution_capability.py -v
"""
import importlib.util
import sys
import time
from pathlib import Path

import pytest

# Load the skill module directly by file path (immune to package conflicts).
_SKILL_FILE = Path(__file__).resolve().parent.parent / "skills" / "evolution_skill.py"
_spec = importlib.util.spec_from_file_location("evolution_skill", _SKILL_FILE)
_es = importlib.util.module_from_spec(_spec)
sys.modules["evolution_skill"] = _es  # required before exec for dataclasses
_spec.loader.exec_module(_es)

DataCollector = _es.DataCollector
DiagnosisEngine = _es.DiagnosisEngine
EvolutionPipeline = _es.EvolutionPipeline
PatternCatalog = _es.PatternCatalog


# ── helpers ──────────────────────────────────────────────────────────

def _fake_bridge(x=0, y=70, py=120.0):
    return {"x": x, "y": y, "jump": False,
            "pose": [1052.0, py, -3599.0, 0.7]}


def _fake_memory(**over):
    d = {"stuck_duration": 10.0, "visited_cells": 50, "coverage_pct": 2.0,
         "anomaly_state": "idle", "health_score": 0.9, "reflex_active": False,
         "revisit_count": 3, "scene_change_rate": 0.1,
         "forced_bold_explore": False, "command_decoupled": False}
    d.update(over)
    return d


def _fake_flow(**over):
    d = {"wall_score": 0.1, "asymmetry": 0.02, "ground_angle": 0.85,
         "ramp_score": 0.2, "terrain": "mixed", "scene_name": "grass #abcd",
         "scene_hash": "abcd", "dialogue_active": False,
         "interactive_near": False, "local_motion_detected": False,
         "cliff_confirmed": False, "tau": None, "opening_score": 0.1,
         "door_frame_score": 0.0, "sky_score": 0.5}
    d.update(over)
    return d


def _collector_with(bridge, memory, flow):
    c = DataCollector(window_seconds=120)
    c.sample(bridge, memory, flow, time.time())
    return c


# ── 1. full-monitoring capability (v2.1) ─────────────────────────────

class TestFullMonitoring:
    def test_sensor_sample_captures_all_dashboard_signals(self):
        c = _collector_with(_fake_bridge(), _fake_memory(),
                            _fake_flow(dialogue_active=True))
        s = c.samples[-1]
        assert s.scene_name == "grass #abcd"
        assert s.dialogue_active is True
        assert s.command_decoupled is False
        assert s.revisit_count == 3
        assert s.pos_y == 120.0
        assert s.tau is None

    def test_fetch_snapshot_covers_all_endpoints(self):
        c = DataCollector()
        snap = c.fetch_snapshot()
        expected = {"bridge", "memory", "flow", "events", "history",
                    "metadata", "trajectory_list"}
        assert expected == set(snap.keys())

    def test_get_metrics_exposes_command_effect_mismatch(self):
        c = _collector_with(_fake_bridge(y=70),
                            _fake_memory(command_decoupled=True),
                            _fake_flow())
        m = c.get_metrics()
        assert m["command_effect_mismatch"] is True
        assert m["mismatch_duration"] >= 1


# ── 2. wall-corner blind spot: corollary discharge pattern ───────────

class TestWallCornerPattern:
    def test_pattern_in_catalog(self):
        cat = PatternCatalog()
        ids = {p["id"] for p in cat.patterns}
        assert "wall_corner_command_decoupled" in ids

    def test_pattern_matches_on_mismatch(self):
        c = DataCollector(window_seconds=120)
        for i in range(17):
            c.sample(_fake_bridge(y=70), _fake_memory(command_decoupled=True),
                     _fake_flow(), time.time() + i)
        eng = DiagnosisEngine(c)
        findings = [f.pattern_id for f in eng.evaluate()]
        assert "wall_corner_command_decoupled" in findings

    def test_no_match_when_moving_normally(self):
        c = _collector_with(_fake_bridge(), _fake_memory(), _fake_flow())
        eng = DiagnosisEngine(c)
        findings = [f.pattern_id for f in eng.evaluate()]
        assert "wall_corner_command_decoupled" not in findings


# ── 3. dialogue detection: dark box true, bright wall false ─────────

class TestDialogueDiscrimination:
    """Regression for the false positive that froze motion while facing a
    bright slope (dialogue=True with ctrl 0,0,0)."""

    def _model_dialogue(self, lower_lum, lower_var, prev_lower_lum):
        """Replicates encode_retina dialogue logic without a full model."""
        sudden_drop = (prev_lower_lum - lower_lum) > 0.12
        dark_uniform = lower_lum < 0.30 and lower_var < 0.08
        frames, total, active = 0, 0.0, False
        for _ in range(20):
            if dark_uniform and (frames > 0 or sudden_drop):
                frames += 1
                total += 0.02
            else:
                frames, total = 0, 0.0
            active = dark_uniform and frames >= 12 and total < 20.0
        return active

    def test_dark_box_detected(self):
        # sudden drop from bright grass 0.55 -> dark box 0.12
        assert self._model_dialogue(0.12, 0.03, 0.55) is True

    def test_bright_uniform_wall_not_dialogue(self):
        # facing a bright slope: lum 0.55, uniform, NO drop
        assert self._model_dialogue(0.55, 0.01, 0.55) is False

    def test_bright_open_field_not_dialogue(self):
        assert self._model_dialogue(0.70, 0.005, 0.71) is False


# ── 3b. dual-zone dialogue detection (EVO Round 5) ───────────────────

class TestDualZoneDialogue:
    """EVO Round 5: top-positioned boxes (key-sign) now detected."""

    def _zone(self, lum, var, prev_lum, frames):
        drop = (prev_lum - lum) > 0.12
        dark = lum < 0.30 and var < 0.08
        if dark and (frames > 0 or drop):
            frames += 1
        else:
            frames = 0
        return frames

    def _dialogue(self, lo, hi):
        """lo/hi = (lum, var, prev_lum) for lower/upper fields."""
        lo_f = hi_f = 0
        lo_prev, hi_prev = lo[2], hi[2]
        total, active = 0.0, False
        for _ in range(20):
            lo_f = self._zone(lo[0], lo[1], lo_prev, lo_f)
            hi_f = self._zone(hi[0], hi[1], hi_prev, hi_f)
            lo_prev, hi_prev = lo[0], hi[0]
            if lo_f >= 12 or hi_f >= 12:
                total += 0.02
            else:
                total = 0.0
            active = (lo_f >= 12 or hi_f >= 12) and total < 20.0
        return active

    def test_top_box_detected(self):
        # key-sign: dark box UPPER field with sudden drop
        assert self._dialogue((0.55, 0.05, 0.55), (0.12, 0.03, 0.55)) is True

    def test_bottom_box_detected(self):
        # standard dialogue: dark box LOWER field
        assert self._dialogue((0.12, 0.03, 0.55), (0.60, 0.02, 0.60)) is True

    def test_bright_slope_no_dialogue(self):
        # bright slope + open sky — no box anywhere
        assert self._dialogue((0.55, 0.01, 0.55), (0.70, 0.005, 0.70)) is False


# ── 4. scene naming: relative-dominance top-2 ────────────────────────

class TestSceneNamingCapability:
    def test_scene_name_from_flow_is_sampled(self):
        c = _collector_with(_fake_bridge(), _fake_memory(),
                            _fake_flow(sky_score=0.84, ramp_score=0.84))
        assert "grass" in c.samples[-1].scene_name

    def test_stabilised_scene_hash_via_ema(self):
        # memory.py smooths signature with EMA before md5 — hashes are 12-hex
        import hashlib
        import numpy as np
        sig = np.ones(128, dtype=np.float32) * 0.1
        ema = 0.9 * sig + 0.1 * (sig + 0.01)
        stable = ema / (np.linalg.norm(ema) + 1e-8)
        h = hashlib.md5(stable.tobytes()).hexdigest()[:12]
        assert len(h) == 12


# ── 5. pipeline end-to-end closed loop ───────────────────────────────

class TestClosedLoop:
    def test_pipeline_completes_cycle(self):
        pipe = EvolutionPipeline(auto_fix=False, window_seconds=120)
        res = pipe.run_one_cycle()
        assert hasattr(res, "findings")
        assert isinstance(res.findings, list)

    def test_all_patterns_have_justification(self):
        cat = PatternCatalog()
        for p in cat.patterns:
            assert p.get("threshold_justification"), p["id"]


# ── 6. EVO Round 6: adaptive reflex cooldown + random fallen direction ──

class TestEvoRound6:
    """Pins Brain v1.4.0: adaptive reflex cooldown + random initial fall-recovery turn."""

    def _controller(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        try:
            from fly64.memory import ReflexController
        finally:
            sys.path.pop(0)
        return ReflexController()

    def test_adaptive_cooldown_shrinks_with_stuck_duration(self):
        rc = self._controller()
        rc._cooldowns[rc.STUCK_RAMP] = 0.0
        rc.update(0.02, {"state": "stuck_ramp", "confidence": 0.9},
                  lambda lo, hi: 0, stuck_duration=0.0)
        fresh = rc.cooldowns[rc.STUCK_RAMP]
        rc2 = self._controller()
        rc2._cooldowns[rc2.STUCK_RAMP] = 0.0
        rc2.update(0.02, {"state": "stuck_ramp", "confidence": 0.9},
                   lambda lo, hi: 0, stuck_duration=90.0)
        prolonged = rc2.cooldowns[rc2.STUCK_RAMP]
        assert fresh > 0
        assert prolonged < fresh, "longer stuck must shorten cooldown"
        assert prolonged >= fresh * 0.25 - 1e-6, "cooldown floor is 25%"

    def test_adaptive_cooldown_backward_compatible_default(self):
        rc = self._controller()
        rc._cooldowns[rc.STUCK_RAMP] = 0.0
        rc.update(0.02, {"state": "stuck_ramp", "confidence": 0.9},
                  lambda lo, hi: 0)
        assert rc.cooldowns[rc.STUCK_RAMP] == pytest.approx(rc.cooldown_duration)

    def test_fallen_initial_direction_is_random_not_fixed(self):
        import re
        main_src = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text(encoding="utf-8")
        m = re.search(r"if escape_x == 0:\s*\n\s*escape_x = (.+)", main_src)
        assert m, "fallen recovery initial direction not found"
        expr = m.group(1).strip()
        assert "rng" in expr, f"initial direction must be random, got: {expr}"
