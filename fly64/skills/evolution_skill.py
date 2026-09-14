#!/usr/bin/env python3
"""
Fly64 EvolutionSkill v2.0.0 — Industry-standard self-evolving skill.

5-phase closed-loop pipeline:
  Monitor -> Diagnose -> Fix -> Verify -> Document

Key features:
  1. Complete closed-loop pipeline
  2. Self-documentation (auto-updates README with fix history and metrics)
  3. Structured fix catalog with versioning and effectiveness tracking
  4. Configurable pattern definitions with JSON Schema validation
"""

from __future__ import annotations

import json, math, os, sys, time, argparse, textwrap, urllib.request, urllib.error
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Callable

try:
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    ValidationError = type("ValidationError", (Exception,), {})

SKILL_VERSION = "3.0.0"
SKILL_NAME = "evolution_skill"
SKILL_DIR = Path(__file__).resolve().parent
WORKSPACE = SKILL_DIR.parent.parent
DASHBOARD_BASE = "http://127.0.0.1:8765"
FIX_CATALOG_PATH = SKILL_DIR / "fix_catalog.json"
DEFAULT_PATTERNS_PATH = SKILL_DIR / "default_patterns.json"
EVOLUTION_LOG_PATH = SKILL_DIR / "evolution_log.jsonl"
SKILL_README_PATH = SKILL_DIR / "README.md"
FIX_LOG_PATH = SKILL_DIR / "fix_log.json"

PATTERN_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["patterns", "$schema_version"],
    "properties": {
        "$schema_version": {"type": "string", "enum": ["2.0"]},
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "version", "conditions", "diagnosis", "fix_template", "severity"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]+$"},
                    "name": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                    "description": {"type": "string"},
                    "conditions": {
                        "type": "object",
                        "minProperties": 1,
                        "additionalProperties": {
                            "oneOf": [
                                {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}, "eq": {"type": ["boolean", "number", "string"]}}},
                                {"type": "boolean"}
                            ]
                        }
                    },
                    "diagnosis": {"type": "string", "minLength": 1},
                    "fix_template": {"type": "string", "minLength": 1},
                    "fix_code": {"type": "string", "description": "Alternative to fix_template for code-only fixes"},
                    "fix_files": {"type": "array", "items": {"type": "string"}},
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "threshold_justification": {"type": "string", "description": "Explanation of why each threshold value was chosen"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "rollback_strategy": {"type": "string"},
                }
            }
        }
    }
}

DEFAULT_PATTERNS = {
    "$schema_version": "2.0",
    "patterns": [
        {"id": "circle_loop", "name": "Circle loop - Circling on flat ground", "version": "1.0.0",
         "description": "Mario circles in place on flat ground, cliff avoidance blocking forward movement.",
         "conditions": {"wall_score": {"max": 0.1}, "asymmetry_magnitude": {"max": 0.06}, "stuck_duration": {"min": 120}, "ground_angle": {"min": 0.3}},
         "diagnosis": "Terrain classifier false-positive cliff; cliff avoidance overrides forward escape.",
         "fix_template": "# Add ground_angle gate before cliff avoidance\n# File: fly64/fly64/main.py\n# Find: cliff_trigger section\n# Replace: Add if ground_angle < 0.3: skip cliff avoidance",
         "fix_files": ["fly64/fly64/main.py"],
         "severity": "high", "tags": ["navigation", "cliff"], "rollback_strategy": "revert_line",
         "threshold_justification": "wall_score<0.1=flat terrain, asymmetry<0.06=symmetrical movement (tuned from 0.05 based on real measured values), stuck>120s=abnormal duration, ground_angle>0.3=not a cliff edge"},
        {"id": "ramp_trap", "name": "Ramp trap - Stuck on slope", "version": "1.0.0",
         "description": "Mario stuck on a ramp, suppression blocks turning.",
         "conditions": {"ramp_score": {"min": 0.5}, "stuck_duration": {"min": 180}, "position_unchanged_60s": True},
         "diagnosis": "Ramp suppression blocks turning on slope.",
         "fix_template": "# Add ramp escape override when stuck >180s\n# File: fly64/fly64/main.py\n# Add after slope detection: override control when stuck",
         "fix_files": ["fly64/fly64/main.py"],
         "severity": "high", "tags": ["navigation", "ramp"], "rollback_strategy": "revert_added_block",
         "threshold_justification": "ramp_score>0.5=strong slope signal, stuck>180s=3min threshold, position_unchanged=no progress despite effort"},
        {"id": "reflex_cooldown_gap", "name": "Reflex cooldown - Ineffective escape during cooldown (adaptive)", "version": "2.0.0",
         "description": "Reflex correctly detects anomaly but fixed cooldown prevents re-trigger during prolonged stuck.",
         "conditions": {"anomaly_state_not_idle": True, "reflex_active": False, "stuck_duration": {"min": 60}},
         "diagnosis": "Fixed reflex cooldown (10s) prevents re-trigger during prolonged stuck; cooldown should be adaptive — scale inversely with stuck_duration so longer stuck periods allow more frequent reflex attempts.",
         "fix_template": "# Make reflex cooldown adaptive based on stuck_duration\n# File: fly64/fly64/memory.py\n# In ReflexController._start_reflex: cooldown = max(2.0, base_cooldown - stuck_duration * 0.05)\n# This ensures: at 60s stuck -> cooldown=7.0s, at 120s -> cooldown=4.0s, at 160s+ -> cooldown=2.0s (minimum)",
         "fix_files": ["fly64/fly64/memory.py"],
         "severity": "medium", "tags": ["reflex", "cooldown", "adaptive"], "rollback_strategy": "revert_value",
         "threshold_justification": "anomaly_state_not_idle=anomaly active, reflex_active=False=cooldown period, stuck>60s=1min without effective escape; adaptive cooldown formula derived from stuck_duration to allow more frequent reflex firings as stuck persists"},
        {"id": "low_coverage_stagnation", "name": "Coverage stagnation - Exploration stuck", "version": "1.0.0",
         "description": "Mario trapped in small area; exploration insufficient.",
         "conditions": {"coverage_stagnant_120s": True, "visited_cells": {"max": 50}},
         "diagnosis": "Mario trapped in small area; exploration insufficient.",
         "fix_template": "# Trigger forced_bold_explore when coverage stagnant\n# File: fly64/fly64/main.py\n# Add check before normal escape logic",
         "fix_files": ["fly64/fly64/main.py"],
         "severity": "medium", "tags": ["exploration", "coverage"], "rollback_strategy": "revert_added_block",
         "threshold_justification": "coverage_stagnant_120s=no new cells in 2min, visited_cells<50=very small explored area"},
        {"id": "below_ground_stuck", "name": "Below ground stuck - Y anomaly prevents movement", "version": "1.0.0",
         "description": "Mario below normal ground level (Y<50) but above fallen threshold (-100), stuck with zero control.",
         "conditions": {"pos_y": {"min": -99, "max": 49}, "stuck_duration": {"min": 30}, "control_magnitude": {"max": 10}},
         "diagnosis": "Fallen detection threshold (Y<-100) too permissive. SM64 ground=120, Y<50=below ground.",
         "fix_template": "# Fix: Lower fallen threshold from -100 to 50\n# File: fly64/fly64/memory.py\n# Change: fallen = pos_y < -100\n# To: fallen = pos_y < 50",
         "fix_files": ["fly64/fly64/memory.py"],
         "severity": "high", "tags": ["fallen", "y_coordinate", "threshold"], "rollback_strategy": "revert_value",
         "threshold_justification": "pos_y between -99 and 49=abnormal (SM64 ground=120), stuck>30s, ctrl<10=no movement"},
        {"id": "fallen_recovery_stuck", "name": "Fallen recovery stuck - Recovery cycles ineffective", "version": "1.0.0",
         "description": "Agent is in fallen anomaly state and recovery cycles (jump+burst+turn) are not making progress.",
         "conditions": {"anomaly_state": {"eq": "fallen"}, "stuck_duration": {"min": 30}},
         "diagnosis": "Always turning -50 (left) fails. Fix: mirror turn, extend burst to 2s with y=80, reverse-before-jump when stuck>30s.",
         "fix_template": "# Fix: Fallen recovery - mirror turn, extend burst, add reverse\n# File: fly64/fly64/main.py",
         "fix_files": ["fly64/fly64/main.py"],
         "severity": "high", "tags": ["fallen", "recovery", "stuck", "escape"], "rollback_strategy": "revert_block",
         "threshold_justification": "anomaly_state='fallen'=fall zone, stuck_duration>30s=persistent stuck despite recovery"},
        {"id": "suspended_animation", "name": "Suspended animation - Zero control signals", "version": "1.0.0",
         "description": "All controls zero (x=0,y=0,jump=0) while stuck increases. Brain outputs no movement.",
         "conditions": {"control_x_zero": True, "control_y_zero": True, "stuck_duration": {"min": 15}, "jump_not_active": True},
         "diagnosis": "Brain outputs zero control while receiving neural control. Possible bridge/visual disconnection.",
         "fix_template": "# Investigate: Zero control with state=1\n# Check: bridge connectivity, model.visual_connected flag",
         "fix_files": ["fly64/fly64/main.py"],
         "severity": "high", "tags": ["control", "dead_state", "bridge"], "rollback_strategy": "investigate",
         "threshold_justification": "x=0 and y=0=no movement, stuck>15s=not transient, jump=False=no escape attempt"},
        # ── P1-P3 Visual Capability patterns (Brain v2.0.0, EVO Round 7) ──
        {"id": "color_nav_blind", "name": "Color navigation blind - Mario ignores color signals", "version": "1.0.0",
         "description": "P1a color vision active but Mario repeatedly walks into red hazards (lava) or ignores blue-sky open areas.",
         "conditions": {"danger_red_index": {"min": 0.5}, "stuck_duration": {"min": 30}, "forward_speed": {"max": 5}},
         "diagnosis": "danger_red_index high but avoidance not triggering. Color modulation gain (0.15 red, 0.10 uv) may need tuning in step() color modulation rules.",
         "fix_template": "# Tune color modulation gains in model.py step()\n# File: fly64/fly64/model.py\n# Find: '# 6a. High danger_red_index' block\n# Adjust: raw_x += 30.0 -> raw_x += 45.0 (stronger red avoid)",
         "fix_files": ["fly64/fly64/model.py"],
         "severity": "medium", "tags": ["color", "visual", "p1a", "navigation"], "rollback_strategy": "revert_value",
         "threshold_justification": "danger_red_index>0.5=strong red hazard ahead, stuck>30s=persistent, speed<5=no effective avoid"},
        {"id": "emd_vertical_blind", "name": "Vertical EMD blind - Missing elevator/platform motion", "version": "1.0.0",
         "description": "P1b 4-direction EMD active but Mario fails to detect vertical motion (elevators, terrain drops), missing jump timing.",
         "conditions": {"emd_on_down": {"min": 0.02}, "jump_rate": {"max": 0.01}, "stuck_duration": {"min": 15}},
         "diagnosis": "Vertical EMD detecting motion but jump injection not triggering. Check pre-spike jump_nodes injection at EMD section.",
         "fix_template": "# Boost vertical EMD jump trigger in model.py step()\n# File: fly64/fly64/model.py\n# Find: '5a. Strong vertical EMD' block\n# Add: self.v[self.jump_nodes] += self.emd_on_down * 0.25",
         "fix_files": ["fly64/fly64/model.py"],
         "severity": "medium", "tags": ["emd", "vertical", "p1b", "jump"], "rollback_strategy": "revert_added_block",
         "threshold_justification": "emd_on_down>0.02=detectable downward motion, jump_rate<0.01=no jump attempt, stuck>15s=persistent"},
        {"id": "target_tracking_inactive", "name": "Small target tracking inactive - No intercept behavior", "version": "1.0.0",
         "description": "P2 moving platform detection active but Mario does not intercept, missing jump timing.",
         "conditions": {"target_count": {"min": 1}, "jump_rate": {"max": 0.01}, "stuck_duration": {"min": 10}},
         "diagnosis": "Targets detected by center-surround but jump injection not activating. Check target_approaching gate in step() and Kalman filter prediction tuning.",
         "fix_template": "# Validate TargetTracker intercept timing in model.py\n# File: fly64/fly64/model.py\n# Find: target_approaching and target_intercept_time\n# Check: pre-spike injection at line 497 zone",
         "fix_files": ["fly64/fly64/model.py"],
         "severity": "medium", "tags": ["target", "tracking", "p2", "intercept"], "rollback_strategy": "revert_value",
         "threshold_justification": "target_count>=1=objects detected, jump_rate<0.01=no jump, stuck>10s=missed opportunity"},
        {"id": "mb_learning_stalled", "name": "Mushroom body learning stalled - No weight change", "version": "1.0.0",
         "description": "P3 mushroom body active but no associations formed after extended running (assoc_count not increasing).",
         "conditions": {"assoc_count": {"max": 0}, "stuck_duration": {"min": 120}},
         "diagnosis": "No dopamine events triggering plasticity window. Check _compute_dopamine() signals: fallen, stuck, scene_change_rate may all be below threshold.",
         "fix_template": "# Debug MB learning signals in model.py _compute_dopamine()\n# File: fly64/fly64/model.py\n# Check: dopamine sources (fallen, stuck_duration, scene_change_rate) reaching correct threshold",
         "fix_files": ["fly64/fly64/model.py", "fly64/fly64/mushroom_body.py"],
         "severity": "low", "tags": ["mushroom", "learning", "p3", "dopamine"], "rollback_strategy": "revert_value",
         "threshold_justification": "assoc_count=0=no learning events after extended run, stuck>120s=sufficient run time"},
        # ── Plasticity monitoring patterns (t4, Brain v2.4.0) ──
        {"id": "dopamine_plateau", "name": "Dopamine gain plateau — Learning saturation detected", "version": "1.0.0",
         "description": "Dopamine-gated gain has reached a maximum plateau without further improvement in error gradient. The plasticity proxy may be saturated — suggests exploring a new strategy or resetting gains.",
         "conditions": {"dopamine_gain_avg": {"min": 2.0}, "learning_progress": {"max": 0.05}, "stuck_duration": {"min": 60}},
         "diagnosis": "Dopamine gain saturated at ceiling (>=2.0) while learning_progress (mean abs error gradient) stagnates below 0.05. The gain modulation cannot further improve motor adaptation — consider resetting gains or switching to a new exploration strategy.",
         "fix_template": "# Reset dopamine gains to break plateau\n# File: fly64/fly64/model.py\n# In step(): if dopamine_gain plateau detected, reset pathway gains\n# model.dopamine_gain.reset_gains() to restart adaptation",
         "fix_files": ["fly64/fly64/model.py"],
         "severity": "medium", "tags": ["plasticity", "dopamine", "plateau", "t4"], "rollback_strategy": "revert_value",
         "threshold_justification": "dopamine_gain_avg>=2.0=near ceiling (GAIN_MAX=2.5), learning_progress<0.05=minimal error gradient (converged), stuck>60s=sufficient run time"},
    ]
}

# ═══════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SensorSample:
    timestamp: float
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    control: tuple[float, float, bool] = (0.0, 0.0, False)
    stuck_duration: float = 0.0
    visited_cells: int = 0
    coverage_pct: float = 0.0
    anomaly_state: str = "idle"
    health_score: float = 1.0
    wall_score: float = 0.0
    asymmetry: float = 0.0
    ground_angle: float = 1.0
    ramp_score: float = 0.0
    terrain: str = "?"
    reflex_active: bool = False
    forward_speed: float = 0.0
    # ── Full-monitoring extension (v2.1): every dashboard signal ──
    scene_name: str = "?"
    scene_hash: str = ""
    command_decoupled: bool = False
    dialogue_active: bool = False
    interactive_near: bool = False
    local_motion_detected: bool = False
    revisit_count: int = 0
    scene_change_rate: float = 0.0
    forced_bold_explore: bool = False
    cliff_confirmed: bool = False
    cliff_standoff_s: float = 0.0
    danger_red_index: float = 0.0
    target_count: int = 0
    assoc_count: int = 0
    emd_on_down: float = 0.0
    tau: Optional[float] = None
    opening_score: float = 0.0
    door_frame_score: float = 0.0
    sky_score: float = 0.0
    pos_y: float = 0.0
    # ── Plasticity monitoring (t4) ──
    dopamine_gain_avg: float = 1.5
    learning_progress: float = 0.0
    mushroom_weight_changes: int = 0
    reward_trend: float = 0.0
    error_gradient_mean: float = 0.0
    gain_update_count: int = 0

    def to_dict(self) -> dict: return asdict(self)

@dataclass
class Finding:
    pattern_id: str; pattern_name: str; pattern_version: str; severity: str
    diagnosis: str; contradiction: str; fix_template: str; fix_files: list[str]
    current_values: dict; confidence: float; timestamp: float

@dataclass
class FixEntry:
    id: str; pattern_id: str; pattern_name: str; pattern_version: str
    diagnosis: str; fix_template: str; severity: str; applied_at: str
    version: int = 1
    baseline_stuck: Optional[float] = None; baseline_coverage: Optional[float] = None
    post_fix_stuck: Optional[float] = None; post_fix_coverage: Optional[float] = None
    effective: Optional[bool] = None; effectiveness_score: Optional[float] = None
    reverted: bool = False; reverted_at: Optional[str] = None; notes: str = ""
    def to_dict(self) -> dict: return asdict(self)

@dataclass
class VerificationResult:
    fix_id: str; pattern_id: str; passed: bool; stuck_reduction_pct: float
    coverage_change_pct: float; effectiveness_score: float; observation_seconds: float; details: str

class CycleResult:
    def __init__(self):
        self.timestamp: float = time.time()
        self.findings: list[Finding] = []
        self.applied_fixes: list[FixEntry] = []
        self.verifications: list[VerificationResult] = []
        self.documented: bool = False
        self.errors: list[str] = []

# ═══════════════════════════════════════════════════════════════════════
# Phase 1: Monitor - DataCollector
# ═══════════════════════════════════════════════════════════════════════

class DataCollector:
    def __init__(self, window_seconds: int = 120):
        self.window_seconds = window_seconds
        self.latest_snapshot: dict = {}
        self._decoupled_run = 0
        self.samples: deque[SensorSample] = deque()
        self._positions: deque[tuple[float, float, float, float]] = deque()
        self._controls: deque[tuple[float, float, float]] = deque()
        self._stuck_hist: deque[tuple[float, float]] = deque()
        self._cov_hist: deque[tuple[float, float]] = deque()

    @staticmethod
    def fetch_json(endpoint: str) -> Optional[dict]:
        try:
            with urllib.request.urlopen(f"{DASHBOARD_BASE}{endpoint}", timeout=5) as r:
                return json.loads(r.read())
        except Exception: return None

    #: ALL monitoring endpoints served by the dashboard
    ALL_ENDPOINTS = ("/bridge-status.json", "/memory.json", "/flow.json",
                     "/events.json", "/history.json", "/metadata.json",
                     "/trajectory-list.json")

    def fetch_all(self) -> tuple:
        return (self.fetch_json("/bridge-status.json"), self.fetch_json("/memory.json"),
                self.fetch_json("/flow.json"), self.fetch_json("/events.json"))

    def fetch_snapshot(self) -> dict:
        """Fetch EVERY monitoring endpoint; the skill's understanding of the
        motion state comes exclusively from this dashboard data."""
        snap: dict = {}
        for tag, ep in zip(("bridge", "memory", "flow", "events", "history",
                            "metadata", "trajectory_list"), self.ALL_ENDPOINTS):
            snap[tag] = self.fetch_json(ep)
        h = snap.get("history")
        if isinstance(h, dict):
            pts = h.get("points") or h.get("rows") or []
            snap["history_len"] = len(pts)
        self.latest_snapshot = snap
        return snap

    def sample(self, bridge: dict, memory: dict, flow: dict, t: float) -> SensorSample:
        pose = bridge.get("pose", [0, 0, 0])
        s = SensorSample(timestamp=t, position=(pose[0], pose[1], pose[2]),
            control=(bridge.get("x", 0), bridge.get("y", 0), bool(bridge.get("jump", False))),
            stuck_duration=memory.get("stuck_duration", 0),
            visited_cells=memory.get("visited_cells", 0),
            coverage_pct=memory.get("coverage_pct", 0.0),
            anomaly_state=memory.get("anomaly_state", "idle"),
            health_score=memory.get("health_score", 1.0),
            wall_score=flow.get("wall_score", 0.0),
            asymmetry=flow.get("asymmetry", 0.0),
            ground_angle=flow.get("ground_angle", 0.0),
            ramp_score=flow.get("ramp_score", 0.0),
            terrain=flow.get("terrain", "?"),
            reflex_active=memory.get("reflex_active", False),
            forward_speed=bridge.get("y", 0),
            scene_name=flow.get("scene_name", "?"),
            scene_hash=flow.get("scene_hash", ""),
            command_decoupled=bool(memory.get("command_decoupled", False)),
            dialogue_active=bool(flow.get("dialogue_active", False)),
            interactive_near=bool(flow.get("interactive_near", False)),
            local_motion_detected=bool(flow.get("local_motion_detected", False)),
            revisit_count=int(memory.get("revisit_count", 0)),
            scene_change_rate=memory.get("scene_change_rate", 0.0),
            forced_bold_explore=bool(memory.get("forced_bold_explore", False)),
            cliff_standoff_s=float(memory.get("cliff_standoff_s", 0.0)),
            cliff_confirmed=bool(flow.get("cliff_confirmed", False)),
            tau=flow.get("tau"),
            opening_score=flow.get("opening_score", 0.0),
            door_frame_score=flow.get("door_frame_score", 0.0),
            sky_score=flow.get("sky_score", 0.0),
            pos_y=pose[1],
            # Plasticity monitoring (t4)
            dopamine_gain_avg=flow.get("dopamine_gain_avg", 1.5),
            learning_progress=flow.get("learning_progress", 0.0),
            mushroom_weight_changes=flow.get("mushroom_weight_changes", 0),
            reward_trend=flow.get("reward_trend", 0.0),
            error_gradient_mean=flow.get("error_gradient_mean", 0.0),
            gain_update_count=flow.get("gain_update_count", 0))
        # Track consecutive motor-vs-motion mismatch frames (wall corners)
        self._decoupled_run = self._decoupled_run + 1 if s.command_decoupled else 0
        self.samples.append(s)
        self._positions.append((t, pose[0], pose[2], pose[1]))
        self._controls.append((t, s.control[0], s.control[1]))
        self._stuck_hist.append((t, s.stuck_duration))
        self._cov_hist.append((t, s.coverage_pct))
        self._trim()
        return s

    def _trim(self):
        cutoff = time.time() - self.window_seconds
        while self.samples and self.samples[0].timestamp < cutoff: self.samples.popleft()
        for dq in [self._positions, self._controls, self._stuck_hist, self._cov_hist]:
            while dq and dq[0][0] < cutoff: dq.popleft()

    def position_unchanged_60s(self) -> bool:
        if len(self._positions) < 10: return False
        recent = list(self._positions)[-10:]
        return (max(p[1] for p in recent) - min(p[1] for p in recent)) < 50 and \
               (max(p[2] for p in recent) - min(p[2] for p in recent)) < 50

    def coverage_stagnant_120s(self) -> bool:
        if len(self._cov_hist) < 5: return False
        return abs(self._cov_hist[0][1] - self._cov_hist[-1][1]) < 0.5

    def motion_entropy(self) -> float:
        if len(self._controls) < 5: return 1.0
        recent = list(self._controls)[-20:]
        x_vals = [abs(c[1]) for c in recent]
        if not x_vals or max(x_vals) == 0: return 0.0
        mx = max(x_vals)
        hist = [0]*10
        for v in x_vals: hist[min(int(v / (mx+1e-6) * 10), 9)] += 1
        total = sum(hist)
        if total == 0: return 0.0
        probs = [h/total for h in hist if h > 0]
        return -sum(p * math.log2(p) for p in probs)

    def get_metrics(self) -> dict:
        vals: dict = {}
        if self.samples:
            s = self.samples[-1]
            vals.update(stuck_duration=s.stuck_duration, visited_cells=s.visited_cells,
                coverage_pct=s.coverage_pct, health_score=s.health_score,
                wall_score=s.wall_score, asymmetry_magnitude=abs(s.asymmetry),
                ground_angle=s.ground_angle, ramp_score=s.ramp_score,
                terrain=s.terrain, anomaly_state=s.anomaly_state,
                reflex_active=s.reflex_active,
                anomaly_state_not_idle=s.anomaly_state != "idle",
                # ── full-monitoring metrics (v2.1) ──
                scene_name=s.scene_name, scene_hash=s.scene_hash,
                command_decoupled=s.command_decoupled,
                command_effect_mismatch=s.command_decoupled,
                mismatch_duration=self._decoupled_run,
                dialogue_active=s.dialogue_active,
                interactive_near=s.interactive_near,
                local_motion_detected=s.local_motion_detected,
                revisit_count=s.revisit_count,
                scene_change_rate=s.scene_change_rate,
                forced_bold_explore=s.forced_bold_explore,
                cliff_confirmed=s.cliff_confirmed,
                tau=s.tau,
                opening_score=s.opening_score,
                door_frame_score=s.door_frame_score,
                sky_score=s.sky_score,
                pos_y=s.pos_y,
                # ── Plasticity metrics (t4) ──
                dopamine_gain_avg=s.dopamine_gain_avg,
                learning_progress=s.learning_progress,
                mushroom_weight_changes=s.mushroom_weight_changes,
                reward_trend=s.reward_trend,
                error_gradient_mean=s.error_gradient_mean,
                gain_update_count=s.gain_update_count)
        vals["position_unchanged_60s"] = self.position_unchanged_60s()
        vals["coverage_stagnant_120s"] = self.coverage_stagnant_120s()
        vals["motion_entropy"] = self.motion_entropy()
        return vals

# ═══════════════════════════════════════════════════════════════════════
# Phase 2: Diagnose - DiagnosisEngine
# ═══════════════════════════════════════════════════════════════════════

class DiagnosisEngine:
    def __init__(self, collector: DataCollector, catalog: Optional[PatternCatalog] = None):
        self.collector = collector
        self.catalog = catalog or PatternCatalog()

    def evaluate(self) -> list[Finding]:
        metrics = self.collector.get_metrics()
        findings: list[Finding] = []
        t = time.time()
        for pattern in self.catalog.patterns:
            result = self._check(pattern, metrics)
            if result:
                values, conf = result
                findings.append(Finding(pattern_id=pattern["id"], pattern_name=pattern["name"],
                    pattern_version=pattern.get("version", "1.0.0"), severity=pattern.get("severity", "medium"),
                    diagnosis=pattern["diagnosis"], contradiction=pattern.get("contradiction", ""),
                    fix_template=pattern["fix_template"], fix_files=pattern.get("fix_files", []),
                    current_values=values, confidence=conf, timestamp=t))
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: (sev_order.get(f.severity, 99), -f.confidence))
        return findings

    def _check(self, pattern: dict, metrics: dict) -> Optional[tuple[dict, float]]:
        cond = pattern["conditions"]
        values, total, passed = {}, 0, 0
        for key, threshold in cond.items():
            total += 1
            val = metrics.get(key)
            if val is None: continue
            values[key] = val
            if isinstance(threshold, dict):
                if "min" in threshold and val < threshold["min"]: continue
                if "max" in threshold and val > threshold["max"]: continue
                if "eq" in threshold and val != threshold["eq"]: continue
                passed += 1
            elif isinstance(threshold, bool):
                if bool(val) == threshold: passed += 1
                else: continue
            else:
                if val == threshold: passed += 1
                else: continue
        if passed == 0: return None
        if passed >= total: return values, passed / max(total, 1)
        return None

# ═══════════════════════════════════════════════════════════════════════
# Phase 3: Fix - FixCatalog (versioned)
# ═══════════════════════════════════════════════════════════════════════

class FixCatalog:
    def __init__(self, path: Path = FIX_CATALOG_PATH):
        self.path = path
        self.fixes: list[FixEntry] = self._load()
        self._vc = max((f.version for f in self.fixes), default=0)

    def _load(self) -> list[FixEntry]:
        if not self.path.exists(): return []
        try:
            data = json.loads(self.path.read_text("utf-8"))
            return [FixEntry(**item) for item in data.get("fixes", [])]
        except: return []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "$catalog_version": "2.0", "meta": {"skill_name": SKILL_NAME, "skill_version": SKILL_VERSION,
                "total_fixes": len(self.fixes),
                "effective_count": sum(1 for f in self.fixes if f.effective is True),
                "ineffective_count": sum(1 for f in self.fixes if f.effective is False),
                "pending_count": sum(1 for f in self.fixes if f.effective is None),
                "last_updated": datetime.now(timezone.utc).isoformat()},
            "fixes": [f.to_dict() for f in self.fixes]}, indent=2, ensure_ascii=False), "utf-8")

    def record_fix(self, finding: Finding) -> FixEntry:
        self._vc += 1
        entry = FixEntry(id=f"fix_{self._vc:04d}", pattern_id=finding.pattern_id,
            pattern_name=finding.pattern_name, pattern_version=finding.pattern_version,
            diagnosis=finding.diagnosis, fix_template=finding.fix_template,
            severity=finding.severity, applied_at=datetime.now(timezone.utc).isoformat(),
            version=self._vc)
        self.fixes.append(entry)
        self.save()
        return entry

    def record_baseline(self, entry: FixEntry, stuck: float, coverage: float = 0.0):
        entry.baseline_stuck = stuck; entry.baseline_coverage = coverage; self.save()

    def record_outcome(self, entry: FixEntry, stuck: float, coverage: float = 0.0):
        entry.post_fix_stuck = stuck; entry.post_fix_coverage = coverage
        si = max(0, (entry.baseline_stuck - stuck) / max(entry.baseline_stuck or 1, 1)) if entry.baseline_stuck else 0.0
        ci = max(0, (coverage - entry.baseline_coverage) / max(entry.baseline_coverage or 1, 1)) if entry.baseline_coverage else 0.0
        entry.effectiveness_score = min(1.0, si * 0.7 + ci * 0.3)
        entry.effective = entry.effectiveness_score >= 0.3
        self.save()

    def has_fix(self, pid: str) -> bool:
        return any(f.pattern_id == pid and not f.reverted for f in self.fixes)

    def revert_fix(self, entry: FixEntry, notes: str = ""):
        entry.reverted = True; entry.reverted_at = datetime.now(timezone.utc).isoformat()
        entry.notes = notes; self.save()

    def get_statistics(self) -> dict:
        total = len(self.fixes)
        effective = sum(1 for f in self.fixes if f.effective is True)
        ineffective = sum(1 for f in self.fixes if f.effective is False)
        pending = sum(1 for f in self.fixes if f.effective is None)
        reverted = sum(1 for f in self.fixes if f.reverted)
        scores = [f.effectiveness_score for f in self.fixes if f.effectiveness_score is not None]
        return {"total_fixes": total, "effective": effective, "ineffective": ineffective,
            "pending": pending, "reverted": reverted,
            "effectiveness_rate": effective / max(total - pending, 1),
            "average_effectiveness_score": round(sum(scores)/len(scores), 3) if scores else 0.0}

    def save_to_fix_log(self, path: Optional[Path] = None):
        """Save fix history to fix_log.json for persistence (fix_log.json format).
        
        This provides an additional persistence format alongside the main fix_catalog.json.
        """
        target = path or FIX_LOG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "$schema": "fly64/evolution-fix-log/1.0",
            "skill_name": SKILL_NAME,
            "skill_version": SKILL_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fix_count": len(self.fixes),
            "fixes": [f.to_dict() for f in self.fixes]
        }, indent=2, ensure_ascii=False), "utf-8")

    def load_from_fix_log(self, path: Optional[Path] = None) -> int:
        """Load fix history from fix_log.json. Returns count of fixes loaded."""
        target = path or FIX_LOG_PATH
        if not target.exists():
            return 0
        try:
            data = json.loads(target.read_text("utf-8"))
            items = data.get("fixes", [])
            loaded = 0
            for item in items:
                entry = FixEntry(**{k: v for k, v in item.items() if k in FixEntry.__dataclass_fields__})
                if not any(f.id == entry.id for f in self.fixes):
                    self.fixes.append(entry)
                    loaded += 1
            self._vc = max((f.version for f in self.fixes), default=self._vc)
            return loaded
        except: return 0

# ═══════════════════════════════════════════════════════════════════════
# Phase 4: Verify - VerificationEngine
# ═══════════════════════════════════════════════════════════════════════

class VerificationEngine:
    def __init__(self, collector: DataCollector, catalog: FixCatalog, window: int = 60):
        self.collector = collector; self.catalog = catalog; self.window = window
        self._active: Optional[FixEntry] = None; self._start: Optional[float] = None
        self._baseline: Optional[dict] = None

    def start(self, entry: FixEntry):
        self._active = entry; self._start = time.time()
        m = self.collector.get_metrics()
        self._baseline = {"stuck": m.get("stuck_duration", 0), "coverage": m.get("coverage_pct", 0)}
        self.catalog.record_baseline(entry, self._baseline["stuck"], self._baseline["coverage"])

    def tick(self) -> Optional[VerificationResult]:
        if not self._active or not self._start: return None
        elapsed = time.time() - self._start
        if elapsed < self.window: return None
        m = self.collector.get_metrics()
        cs, cc = m.get("stuck_duration", 0), m.get("coverage_pct", 0)
        bs = self._baseline.get("stuck", 0) if self._baseline else 0
        bc = self._baseline.get("coverage", 0) if self._baseline else 0
        sr = max(0, (bs - cs) / max(bs, 1)) * 100 if bs > 0 else 0.0
        si = max(0, (bs - cs) / max(bs, 1))
        ci = max(0, (cc - bc) / max(bc, 1))
        es = min(1.0, si * 0.7 + ci * 0.3)
        self.catalog.record_outcome(self._active, cs, cc)
        r = VerificationResult(fix_id=self._active.id, pattern_id=self._active.pattern_id,
            passed=es >= 0.3, stuck_reduction_pct=round(sr, 1),
            coverage_change_pct=round((cc-bc)/max(bc,1)*100 if bc>0 else 0, 1),
            effectiveness_score=round(es, 3), observation_seconds=round(elapsed, 1),
            details="Effective" if es >= 0.3 else "Not effective")
        self._active = None; self._start = None; self._baseline = None
        return r

# ═══════════════════════════════════════════════════════════════════════
# Phase 5: Document - SelfDocumenter
# ═══════════════════════════════════════════════════════════════════════

class SelfDocumenter:
    def __init__(self, catalog: FixCatalog, path: Path = SKILL_README_PATH,
                 pattern_catalog: Optional[PatternCatalog] = None):
        self.catalog = catalog; self.path = path; self.pattern_catalog = pattern_catalog
        self.latest_plasticity: dict = {}

    def update(self, extra: Optional[str] = None,
               plasticity_metrics: Optional[dict] = None) -> str:
        if plasticity_metrics:
            self.latest_plasticity = plasticity_metrics
        content = self._generate(extra, plasticity_metrics or self.latest_plasticity)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, "utf-8")
        return content

    def _generate(self, extra: Optional[str] = None,
                  plasticity_metrics: Optional[dict] = None) -> str:
        stats = self.catalog.get_statistics()
        fixes = self.catalog.fixes
        patterns = self.pattern_catalog.patterns if self.pattern_catalog else []
        lines = [
            f"# EvolutionSkill - Self-Evolving Motion Diagnosis",
            "",
            f"**Version**: {SKILL_VERSION} | **Catalog Version**: 2.0",
            "",
            "A complete closed-loop pipeline for autonomous motion diagnosis in Fly64.",
            "",
            "## Architecture",
            "",
            "```",
            "Monitor -> Diagnose -> Fix -> Verify -> Document",
            "```",
            "",
            "| Phase | Component | Description |",
            "|-------|-----------|-------------|",
            "| 1 Monitor | DataCollector | Rolling window sensor data from dashboard endpoints |",
            "| 2 Diagnose | DiagnosisEngine + PatternCatalog | Pattern matching with JSON Schema validation |",
            "| 3 Fix | FixCatalog | Versioned fix entries with baseline/outcome tracking |",
            "| 4 Verify | VerificationEngine | Post-fix effectiveness measurement (30% threshold) |",
            "| 5 Document | SelfDocumenter | Auto-updates this README with metrics and history |",
            "",
            "---",
            "",
            "## Effectiveness Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Fixes Applied | {stats['total_fixes']} |",
            f"| Effective | {stats['effective']} |",
            f"| Ineffective | {stats['ineffective']} |",
            f"| Pending Verification | {stats['pending']} |",
            f"| Reverted | {stats['reverted']} |",
            f"| Effectiveness Rate | {stats['effectiveness_rate']:.1%} |",
            f"| Avg Score | {stats['average_effectiveness_score']} |",
            "",
        ]
        if plasticity_metrics:
            lines += [
                "## Plasticity Metrics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Dopamine Gain Avg | {plasticity_metrics.get('dopamine_gain_avg', 'N/A')} |",
                f"| Learning Progress (mean |error| over 100 ticks) | {plasticity_metrics.get('learning_progress', 'N/A')} |",
                f"| Mushroom Weight Changes (assoc_count) | {plasticity_metrics.get('mushroom_weight_changes', 'N/A')} |",
                f"| Reward Trend (cumulative) | {plasticity_metrics.get('reward_trend', 'N/A')} |",
                f"| Error Gradient Mean | {plasticity_metrics.get('error_gradient_mean', 'N/A')} |",
                f"| Gain Update Count | {plasticity_metrics.get('gain_update_count', 'N/A')} |",
                "",
            ]
        if patterns:
            lines += [
                "## Pattern Catalog",
                "",
                f"The following {len(patterns)} patterns are loaded from `default_patterns.json` and validated against JSON Schema (draft-07).",
                "",
                "| ID | Name | Severity | Conditions |",
                "|----|------|----------|------------|",
            ]
            for p in patterns:
                conds = "; ".join(f"{k}: {v}" for k, v in p.get("conditions", {}).items())
                tj = p.get("threshold_justification", "")
                if tj:
                    conds += f" ({tj})"
                lines.append(f"| {p['id']} | {p['name']} | {p.get('severity','')} | {conds} |")
            lines.append("")
        if fixes:
            lines += [
                f"## Fix History (Last {min(10, len(fixes))})",
                "",
                "| ID | Pattern | Severity | Applied | Baseline | Post-Fix | Effective | Score |",
                "|----|---------|----------|---------|----------|----------|-----------|-------|",
            ]
            for fix in reversed(fixes[-10:]):
                eff = "Yes" if fix.effective is True else ("No" if fix.effective is False else "Pending")
                sc = f"{fix.effectiveness_score:.2f}" if fix.effectiveness_score is not None else "-"
                ap = fix.applied_at[:10] if fix.applied_at else "-"
                bs = f"{fix.baseline_stuck:.0f}s" if fix.baseline_stuck is not None else "-"
                ps = f"{fix.post_fix_stuck:.0f}s" if fix.post_fix_stuck is not None else "-"
                lines.append(f"| {fix.id} | {fix.pattern_name} | {fix.severity} | {ap} | {bs} | {ps} | {eff} | {sc} |")
            lines.append("")
        if extra:
            lines += ["---", "", extra, ""]
        lines += [
            "---",
            "",
            f"*Auto-generated by EvolutionSkill v{SKILL_VERSION} on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
        ]
        return "\n".join(lines)

    def cycle_summary(self, findings: list[Finding], verifications: list[VerificationResult]) -> str:
        lines = [f"### Last Cycle Summary", "",
            f"**Time**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", ""]
        if findings:
            lines.append(f"**Findings**: {len(findings)} pattern(s)")
            for f in findings:
                lines.append(f"- [{f.severity.upper()}] {f.pattern_name} (conf={f.confidence:.0%})")
        else: lines.append("**Findings**: No patterns detected")
        lines.append("")
        if verifications:
            lines.append(f"**Verifications**: {len(verifications)} fix(es)")
            for v in verifications:
                lines.append(f"- {v.fix_id}: {'Passed' if v.passed else 'Failed'} (stuck -{v.stuck_reduction_pct:.0f}%, score={v.effectiveness_score})")
            lines.append("")
        return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════
# PatternCatalog - JSON Schema validated patterns
# ═══════════════════════════════════════════════════════════════════════

class PatternCatalog:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_PATTERNS_PATH
        self._raw: dict = {}
        self.patterns: list[dict] = []
        self.schema_version: str = "2.0"
        self._load()

    def _load(self):
        if self.path and self.path.exists():
            try:
                raw = json.loads(self.path.read_text("utf-8"))
                if HAS_JSONSCHEMA: validate(instance=raw, schema=PATTERN_SCHEMA)
                self._raw = raw; self.patterns = raw["patterns"]
                self.schema_version = raw.get("$schema_version", "2.0")
                return
            except: pass
        self._raw = DEFAULT_PATTERNS; self.patterns = DEFAULT_PATTERNS["patterns"]; self.schema_version = "2.0"

    @classmethod
    def from_dict(cls, data: dict) -> PatternCatalog:
        if HAS_JSONSCHEMA: validate(instance=data, schema=PATTERN_SCHEMA)
        c = cls.__new__(cls); c.path = None; c._raw = data; c.patterns = data["patterns"]; c.schema_version = data.get("$schema_version", "2.0")
        return c

    def get_pattern(self, pid: str) -> Optional[dict]:
        return next((p for p in self.patterns if p["id"] == pid), None)

    def add_pattern(self, pattern: dict):
        if HAS_JSONSCHEMA: validate(instance={"$schema_version": self.schema_version, "patterns": [pattern]}, schema=PATTERN_SCHEMA)
        self.patterns.append(pattern)
        if self.path: self._save()

    def remove_pattern(self, pid: str) -> bool:
        before = len(self.patterns)
        self.patterns = [p for p in self.patterns if p["id"] != pid]
        if len(self.patterns) < before and self.path: self._save()
        return len(self.patterns) < before

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"$schema_version": self.schema_version, "patterns": self.patterns}, indent=2, ensure_ascii=False), "utf-8")

    def get_pattern_count(self) -> int: return len(self.patterns)


# ═══════════════════════════════════════════════════════════════════════
# Coach Consult — LLM visual analysis for unsolvable situations
# ═══════════════════════════════════════════════════════════════════════

class CoachConsult:
    """When the brain model hits an unsolvable situation, capture the game
    frame + context snapshot and escalate to the DSH LLM (GLM-5.3-flash
    multimodal) for scene analysis and strategy recommendation.

    The brain model marks help_needed in evolution.json; the skill (running
    inside the DSH agent environment where GLM-5.3-flash is available) picks
    it up, sends the screenshot via the subagent tool, and writes the
    recommendation to active_strategy.json for hot-reload by the brain.
    """

    PROMPT_TEMPLATE = (
        "你是 SM64 果蝇脑控制系统的教练。分析当前游戏截屏和状态，回答：\n"
        "1. 场景中有什么元素（门/坡/敌人/金币/平台/水体）？\n"
        "2. 马里奥当前面临什么障碍或问题？\n"
        "3. 建议的下一步行动（转向方向、速度、是否跳跃、目标位置）？\n"
        "以 JSON 回复: {\"scene_elements\": [...], \"problem\": \"...\", "
        "\"action\": \"...\", \"strategy\": {\"mode\": \"...\", \"param\": ...}}"
    )

    def __init__(self, dashboard_base: str = DASHBOARD_BASE):
        self.dashboard_base = dashboard_base

    def check_help_needed(self) -> Optional[dict]:
        """Check if the brain model flagged an unsolvable situation."""
        evo = DataCollector.fetch_json("/evolution.json")
        if not evo:
            return None
        mem = DataCollector.fetch_json("/memory.json")
        if not mem:
            return None
        # Trigger conditions: habituation blocked, or stuck>120s with no
        # reflex active and no findings from existing patterns
        blocked = mem.get("stuck_duration", 0) > 120
        no_reflex = not mem.get("reflex_active", False)
        anomaly = mem.get("anomaly_state", "idle") != "idle"
        if blocked and no_reflex and anomaly:
            return {
                "scene_name": mem.get("scene_name", "?"),
                "position": mem.get("cell_x", 0),
                "stuck_duration": mem.get("stuck_duration", 0),
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": mem.get("health_score", 1.0),
                "help_reason": "unsolvable_stuck",
            }
        return None

    def get_frame_b64(self) -> Optional[str]:
        """Fetch current game frame as base64 for multimodal LLM input."""
        frame = DataCollector.fetch_json("/frame.json")
        if frame and frame.get("frame_b64"):
            return frame["frame_b64"]
        return None

    def format_consult_request(self, context: dict, frame_b64: Optional[str]) -> str:
        """Format the escalation request text for the DSH LLM subagent."""
        lines = [
            "🆘 Coach Help Request — Fly64 brain model is stuck",
            f"Scene: {context.get('scene_name', '?')}",
            f"Stuck duration: {context.get('stuck_duration', 0):.0f}s",
            f"Anomaly: {context.get('anomaly_state', '?')}",
            f"Health: {context.get('health_score', 1.0):.2f}",
            "",
            "Please analyze the game screenshot and recommend:",
            "1. What scene elements are visible?",
            "2. What is blocking Mario?",
            "3. What action should the brain model take next?",
            "4. Write a strategy for active_strategy.json",
        ]
        if frame_b64:
            lines.append("[Screenshot attached]")
        return "\n".join(lines)

    def write_strategy(self, strategy: dict, path: Optional[Path] = None):
        """Write the LLM's recommended strategy for brain model hot-reload."""
        p = path or (SKILL_DIR / "active_strategy.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), "utf-8")

# ═══════════════════════════════════════════════════════════════════════
# EvolutionPipeline - 5-phase orchestrator
# ═══════════════════════════════════════════════════════════════════════

class EvolutionPipeline:
    def __init__(self, auto_fix: bool = False, window_seconds: int = 120,
                 verification_window: int = 60, patterns_path: Optional[Path] = None,
                 fix_catalog_path: Path = FIX_CATALOG_PATH, readme_path: Path = SKILL_README_PATH):
        self.auto_fix = auto_fix
        self.collector = DataCollector(window_seconds=window_seconds)
        self.pattern_catalog = PatternCatalog(path=patterns_path)
        self.diagnosis_engine = DiagnosisEngine(self.collector, self.pattern_catalog)
        self.fix_catalog = FixCatalog(path=fix_catalog_path)
        self.verification_engine = VerificationEngine(self.collector, self.fix_catalog, window=verification_window)
        self.documenter = SelfDocumenter(self.fix_catalog, readme_path, pattern_catalog=self.pattern_catalog)

    def run_one_cycle(self, bridge=None, memory=None, flow=None) -> CycleResult:
        result = CycleResult()
        t = time.time()
        try:
            if bridge is None: bridge, memory, flow, _ = self.collector.fetch_all()
            if not all([bridge, memory, flow]):
                result.errors.append("Data unavailable"); return result
            self.collector.sample(bridge, memory, flow, t)
        except Exception as e: result.errors.append(f"Monitor: {e}"); return result
        try: result.findings = self.diagnosis_engine.evaluate()
        except Exception as e: result.errors.append(f"Diagnose: {e}"); return result
        try:
            for f in result.findings:
                if not self.fix_catalog.has_fix(f.pattern_id) and self.auto_fix:
                    entry = self.fix_catalog.record_fix(f)
                    self.verification_engine.start(entry)
                    result.applied_fixes.append(entry)
        except Exception as e: result.errors.append(f"Fix: {e}")
        try:
            v = self.verification_engine.tick()
            if v: result.verifications.append(v)
        except Exception as e: result.errors.append(f"Verify: {e}")
        try:
            s = self.documenter.cycle_summary(result.findings, result.verifications)
            # Extract plasticity metrics from flow data for documentation
            _plasticity = {}
            if flow:
                for _k in ("dopamine_gain_avg", "learning_progress",
                           "mushroom_weight_changes", "reward_trend",
                           "error_gradient_mean", "gain_update_count"):
                    if _k in flow:
                        _plasticity[_k] = flow[_k]
            self.documenter.update(extra=s, plasticity_metrics=_plasticity)
            result.documented = True
        except Exception as e: result.errors.append(f"Document: {e}")
        return result

    @property
    def fix_statistics(self) -> dict: return self.fix_catalog.get_statistics()

# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def format_status(sample: SensorSample) -> str:
    return (f"[{datetime.fromtimestamp(sample.timestamp).strftime('%H:%M:%S')}] "
        f"pos=({sample.position[0]:.0f},{sample.position[1]:.0f},{sample.position[2]:.0f}) "
        f"stuck={sample.stuck_duration:.0f}s cells={sample.visited_cells} "
        f"coverage={sample.coverage_pct:.1f}% anomaly={sample.anomaly_state} "
        f"health={sample.health_score:.2f} wall={sample.wall_score:.2f} "
        f"asym={sample.asymmetry:.3f} ground={sample.ground_angle:.2f} terrain={sample.terrain}")

def on_cycle(result: CycleResult):
    print(f"  Findings: {len(result.findings)}")
    for f in result.findings:
        print(f"    [{f.severity.upper()}] {f.pattern_name} (conf={f.confidence:.0%})")
    for fix in result.applied_fixes: print(f"    Fix {fix.id}: {fix.pattern_name}")
    for v in result.verifications: print(f"    Verify {v.fix_id}: {'OK' if v.passed else 'FAIL'} (score={v.effectiveness_score})")
    if result.documented: print(f"    README updated")
    for e in result.errors: print(f"    Warning: {e}")

def main():
    p = argparse.ArgumentParser(description="Fly64 EvolutionSkill v" + SKILL_VERSION)
    p.add_argument("--interval", type=int, default=5)
    p.add_argument("--auto-fix", action="store_true")
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--window", type=int, default=120)
    p.add_argument("--verify-window", type=int, default=60)
    p.add_argument("--patterns", type=str)
    args = p.parse_args()

    print(f"Fly64 EvolutionSkill v{SKILL_VERSION}")
    print("5-Phase: Monitor -> Diagnose -> Fix -> Verify -> Document")
    print(f"Interval: {args.interval}s | Auto-fix: {args.auto_fix}\n")

    pipe = EvolutionPipeline(auto_fix=args.auto_fix, window_seconds=args.window,
        verification_window=args.verify_window,
        patterns_path=Path(args.patterns) if args.patterns else None)

    for i in range(args.max_iterations):
        bridge, memory, flow, events = pipe.collector.fetch_all()
        if not all([bridge, memory, flow, events]):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for dashboard...")
            time.sleep(args.interval); continue
        t = time.time()
        sample = pipe.collector.sample(bridge, memory, flow, t)
        print(format_status(sample))
        result = pipe.run_one_cycle(bridge=bridge, memory=memory, flow=flow)
        on_cycle(result)
        try:
            with open(EVOLUTION_LOG_PATH, "a", encoding="utf-8") as lf:
                lf.write(json.dumps({"timestamp": t, "iteration": i+1,
                    "findings": [{"id": f.pattern_id, "severity": f.severity} for f in result.findings],
                    "fixes": [f.id for f in result.applied_fixes],
                    "verifications": [{"id": v.fix_id, "passed": v.passed} for v in result.verifications],
                    "errors": result.errors}, ensure_ascii=False) + "\n")
        except: pass
        time.sleep(args.interval)

    stats = pipe.fix_statistics
    print(f"\nCompleted {args.max_iterations} iterations.")
    print(f"Fixes: {stats['total_fixes']} (effective: {stats['effective']}, pending: {stats['pending']})")
    print(f"Rate: {stats['effectiveness_rate']:.1%}")

if __name__ == "__main__":
    main()