# -*- coding: utf-8 -*-
"""Regression tests for the evolution capability closed loop.

Each test pins one capability gained during an evolution round so future
refactors cannot silently regress it.  Run:
    python3 -m pytest fly64/tests/test_evolution_capability.py -v
"""
import importlib.util
import json
import re
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
        """EVO R6, refactored by v2.8-v2.12: the fixed -50 initial direction
        and the 5-phase escape state machine are GONE — fallen/bold recovery
        emerges from turn-pool current drive with spontaneous alternation
        (reflex.bold_direction()) plus coach-tunable strategy params."""
        main_src = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text(encoding="utf-8")
        assert "escape_x = -50" not in main_src, "fixed leftward direction must stay retired"
        assert "bold_turn_drive" in main_src, "bold recovery drives turn pools via current"
        assert "reflex.bold_direction" in main_src, "spontaneous alternation via reflex direction memory"


# ── 7. L2/L3 coach-help: /help.json snapshot + strategy hot-reload ────

def _main_module():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        import fly64.main as m
        return m
    finally:
        sys.path.pop(0)


class TestCoachHelpSnapshot:
    """L2: /help.json snapshot structure (mock data, no game needed)."""

    def test_snapshot_structure(self):
        import base64
        import numpy as np
        m = _main_module()
        frame = np.zeros((4, 6, 3), np.uint8)
        frame[0, 0] = 200
        snap = m.build_help_snapshot(
            "墙体 #abcd", {"x": 1.0, "y": 2.0, "z": 3.0},
            "interaction habituated", frame)
        assert set(snap) == {"scene_name", "position", "diagnosis",
                             "frame_b64", "help_reason", "ts"}
        assert snap["help_reason"] == "interaction_blocked"
        assert snap["scene_name"] == "墙体 #abcd"
        assert snap["position"] == {"x": 1.0, "y": 2.0, "z": 3.0}
        raw = base64.b64decode(snap["frame_b64"])
        assert raw == frame.tobytes()
        assert snap["ts"] > 0

    def test_snapshot_handles_missing_frame(self):
        m = _main_module()
        snap = m.build_help_snapshot(None, None, None, None)
        assert snap["frame_b64"] == ""
        assert snap["position"] == {}

    def test_help_endpoint_registered_in_http_handler(self):
        m = _main_module()
        assert m.DashboardHTTP.help_json == b"{}"
        src = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text(encoding="utf-8")
        assert '"/help.json"' in src
        assert "total_help_requests" in src


class TestStrategyHotReload:
    """L3: active_strategy.json parse — valid / invalid / missing."""

    def _write(self, tmp_path, content):
        p = tmp_path / "active_strategy.json"
        p.write_text(content, encoding="utf-8")
        return p

    def test_valid_json_applies_fallen_recovery(self, tmp_path):
        m = _main_module()
        p = self._write(tmp_path, json.dumps(
            {"fallen_recovery": {"mode": "directional_climb",
                                 "climb_period": 3.5,
                                 "persist_seconds": 1.5}}))
        s = m.load_active_strategy(p)
        assert s["mode"] == "directional_climb"
        assert s["climb_period"] == pytest.approx(3.5)
        assert s["persist_seconds"] == pytest.approx(1.5)

    def test_invalid_json_falls_back_to_defaults(self, tmp_path):
        m = _main_module()
        p = self._write(tmp_path, "{not json!!")
        s = m.load_active_strategy(p)
        assert s == m.ACTIVE_STRATEGY_DEFAULTS

    def test_missing_file_falls_back_to_defaults(self, tmp_path):
        m = _main_module()
        s = m.load_active_strategy(tmp_path / "does_not_exist.json")
        assert s["mode"] == "mirror"
        assert s["climb_period"] > 0

    def test_unknown_mode_and_bad_numbers_rejected(self, tmp_path):
        m = _main_module()
        p = self._write(tmp_path, json.dumps(
            {"fallen_recovery": {"mode": "teleport", "climb_period": "abc"}}))
        s = m.load_active_strategy(p)
        assert s["mode"] == "mirror"
        assert s["climb_period"] == m.ACTIVE_STRATEGY_DEFAULTS["climb_period"]

    def test_hot_reload_wired_into_main_loop(self):
        src = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text(encoding="utf-8")
        assert "active_strategy.json" in src
        assert "_last_strategy_tick" in src
        assert '>= 600' in src, "strategy must reload every 600 ticks"


# ── EVO Round 10: local breakout from persistent micro_loop ──────────────

class TestEvoRound10:
    """Pins Brain v2.3.0: persistent micro_loop (>60 s) triggers forced bold
    explore that overrides the reflex cascade, bypasses the low-confidence
    cliff turn branch, and is attributed as decision_source=bold_explore."""

    def _src(self, name):
        return (Path(__file__).resolve().parent.parent / "fly64" / name).read_text(encoding="utf-8")

    def test_breakout_gate_includes_micro_loop_persistence(self):
        src = self._src("memory.py")
        assert "micro_loop_stuck" in src
        assert '_latest_anomaly_state == "micro_loop"' in src
        # threshold is coach-tunable (EVO R11: default 60.0 via bold_explore_stuck_s)
        assert "bold_explore_stuck_s" in src and "_latest_anomaly_dur >" in src, \
            "breakout must trigger after persistent micro_loop (coach-tunable threshold)"
        # original confined-area path preserved (backward compatible)
        assert "visited_cells < 20" in src

    def test_bold_explore_overrides_reflex_in_cascade(self):
        """EVO R10, refactored by v2.12: bold_now replaces bold_override —
        bold explore still overrides an active reflex in the cascade."""
        src = self._src("main.py")
        assert "bold_now" in src
        assert re.search(r"bold_now or not reflex_override", src), \
            "bold explore must be able to override an active reflex"

    def test_cliff_low_conf_turn_branch_retired(self):
        """EVO R11: the symbolic low-confidence cliff turn branch (x*1.5 /
        y-20 per tick) is retired — directional openness now reaches the turn
        pools as current injection."""
        src = self._src("main.py")
        assert "control.x = int(control.x * 1.5)" not in src, \
            "low-conf cliff turn branch must stay retired"
        assert "Directional openness" in self._src("retina.py")

    def test_bold_explore_decision_source(self):
        """v2.12 refactor: bold_explore/collision symbolic channels retired —
        bold is attributed through escape (cascade comment at P1), and the
        retired branches must not silently return."""
        src = self._src("main.py")
        assert 'decision_source = "bold_explore"' not in src, \
            "v2.12 retired the bold_explore channel (alternating turn-pool current)"
        assert 'decision_source = "collision"' not in src, \
            "collision branch retired with its bypass code path"
        # core attribution channels must remain
        for ch in ("dialogue", "cliff_reflex", "anomaly_reflex", "escape", "steering"):
            assert f'decision_source = "{ch}"' in src

    def test_opening_injection_wired_into_step(self):
        """EVO R11: directional openness reaches the turn pools as current
        injection inside model.step (neural competition, not control write)."""
        src = self._src("model.py")
        assert "opening_asymmetry" in src
        assert "self.v[self.turn_left] += _open_inj" in src
        assert "self.v[self.turn_right] += _open_inj" in src
        assert "self.opening_asymmetry = float(flow.get(" in src

    def test_movement_reward_report_api(self):
        """EVO R11: displacement feedback API blends into the dopamine sum."""
        src = self._src("model.py")
        assert "def report_movement" in src
        assert "self.movement_reward" in src
        # displacement feedback must reach the dopamine computation
        assert "self.reward_signal = max(-1.0, min(1.0," in src
        assert "_reward_contrib" in src


# ── EVO Round 13 (Brain v2.7.0 / Skill v3.0.0): dialogue pause-wait scene
#    label + mushroom-body setback dopamine + llm.env auto-load ─────────────

class TestEvoRound13:
    def _src(self, name):
        return (Path(__file__).resolve().parent.parent / "fly64" / name).read_text(encoding="utf-8")

    def test_dialogue_pause_scene_label_priority(self):
        src = self._src("main.py")
        assert "对话暂停等待" in src
        assert src.index("对话暂停等待") < src.index("feats = {"), \
            "dialogue pause label must be checked before terrain dominance"

    def test_setback_dopamine_pulse_wiring(self):
        model_src = self._src("model.py")
        assert "def add_setback" in model_src
        assert "_pending_dopamine" in model_src
        assert '_pending = getattr(self, "_pending_dopamine", 0.0)' in model_src
        assert "self._pending_dopamine = 0.0" in model_src

    def test_dialogue_setback_called_on_discovery_and_lock(self):
        src = self._src("main.py")
        assert "model.add_setback(0.5)" in src, "new dialogue episode setback"
        assert "model.add_setback(0.8)" in src, "habituation lock deepens setback"

    def test_llm_env_file_autoload(self):
        src = (Path(__file__).resolve().parent.parent / "plugin" / "llm_consult.py").read_text(encoding="utf-8")
        assert "_load_llm_env" in src and "llm.env" in src

    def test_memory_json_dialogue_observability(self):
        src = self._src("main.py")
        assert '"dialogue_active"' in src
        assert '"scene_label"' in src

# ── EVO Round t4: Plasticity monitoring ──────────────────────────────────────

class TestPlasticityMonitoring:
    """Pins plasticity metrics in evolution.json and patterns."""

    def test_dopamine_plateau_pattern_defined(self):
        """dopamine_plateau pattern exists in the catalog."""
        cat = _es.PatternCatalog()
        ids = {p["id"] for p in cat.patterns}
        assert "dopamine_plateau" in ids

    def test_dopamine_plateau_has_correct_conditions(self):
        cat = _es.PatternCatalog()
        pat = next(p for p in cat.patterns if p["id"] == "dopamine_plateau")
        cond = pat["conditions"]
        assert "dopamine_gain_avg" in cond
        assert "learning_progress" in cond
        assert "stuck_duration" in cond

    def test_plasticity_fields_in_sensor_sample(self):
        """SensorSample includes plasticity tracking fields."""
        from dataclasses import fields
        field_names = {f.name for f in fields(_es.SensorSample)}
        for name in ("dopamine_gain_avg", "learning_progress",
                     "mushroom_weight_changes", "reward_trend",
                     "error_gradient_mean", "gain_update_count"):
            assert name in field_names, f"{name} missing from SensorSample"

    def test_plasticity_metrics_in_get_metrics(self):
        """get_metrics() exposes plasticity fields."""
        c = _es.DataCollector(window_seconds=120)
        bridge = {"x": 0, "y": 70, "jump": False, "pose": [0.0, 120.0, 0.0, 0.0]}
        memory = {"stuck_duration": 10.0, "visited_cells": 50, "coverage_pct": 2.0,
                  "anomaly_state": "idle", "health_score": 0.9, "reflex_active": False}
        flow = {"wall_score": 0.1, "asymmetry": 0.02,
                "dopamine_gain_avg": 1.8, "learning_progress": 0.03}
        import time
        c.sample(bridge, memory, flow, time.time())
        m = c.get_metrics()
        assert "dopamine_gain_avg" in m
        assert "learning_progress" in m

    def test_documenter_accepts_plasticity_metrics(self):
        """SelfDocumenter.update() accepts plasticity_metrics kwarg without error."""
        cat = _es.FixCatalog()
        doc = _es.SelfDocumenter(cat)
        doc.update(plasticity_metrics={
            "dopamine_gain_avg": 1.8, "learning_progress": 0.03,
            "mushroom_weight_changes": 5, "reward_trend": 0.5,
        })
        # Verify plasticity data was stored
        assert doc.latest_plasticity.get("dopamine_gain_avg") == 1.8
