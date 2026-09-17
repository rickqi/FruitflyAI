#!/usr/bin/env python3
"""Coach outcome attribution + curriculum state machine (roadmap P1).

Closes the advice→behavior→outcome attribution gap:

  1. When a strategy is written, ``snapshot_outcome`` captures the strategy
     keys plus a context baseline (scene / anomaly / stuck / health / disp).
  2. After a measurement window (default 30s = 3 runner cycles), ``resolve``
     compares memory deltas and emits an outcome record.
  3. Records accumulate in ``skills/coach_outcomes.jsonl`` — the
     场景 × 策略键 → 效果 table that powers instinct consolidation (P4.4)
     and the social metric loop (P4.6).
  4. ``curriculum`` persists a course/stage/goal state so the coach teaches
     with a lesson plan instead of one-shot answers (P4.3).

Pure functions + jsonl/json persistence; no dashboard access (the runner
supplies snapshots).  All failures are contained by callers.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

PLUGIN_DIR = Path(__file__).resolve().parent
SKILLS_DIR = PLUGIN_DIR.parent / "skills"
PENDING_PATH = PLUGIN_DIR / ".pending_outcome.json"
OUTCOMES_PATH = SKILLS_DIR / "coach_outcomes.jsonl"
CURRICULUM_PATH = SKILLS_DIR / "curriculum.json"
DEFAULT_WINDOW_S = 30.0

_BASELINE_KEYS = ("stuck_duration", "health_score", "disp_60s", "loop_score")


# ── snapshot / resolve ────────────────────────────────────────────────
def snapshot_outcome(strategy: dict, memory: dict, flow: dict,
                     cycle: int = 0, window_s: float = DEFAULT_WINDOW_S,
                     help_reason: str = "") -> dict:
    """Capture a pending outcome when a coach strategy is written."""
    return {
        "ts": time.time(),
        "cycle": int(cycle),
        "window_s": float(window_s),
        "keys": dict(strategy or {}),
        "scene_id": (flow or {}).get("scene_hash")
                    or (memory or {}).get("scene_id", ""),
        "scene_label": (memory or {}).get("scene_label", ""),
        "anomaly": (memory or {}).get("anomaly_state", "?"),
        "help_reason": str(help_reason or ""),
        "baseline": {k: _num((memory or {}).get(k)) for k in _BASELINE_KEYS},
    }


def resolve_outcome(pending: dict, memory: dict) -> Optional[dict]:
    """Resolve a pending outcome against current memory.

    Returns None while the measurement window is still open, or when the
    memory snapshot is degraded (missing baseline keys — a zero-delta record
    would be worthless for attribution, so we keep waiting for a real one).
    """
    if not pending:
        return None
    if "stuck_duration" not in (memory or {}):
        return None  # degraded snapshot — do not emit a junk record
    age = time.time() - float(pending.get("ts", 0))
    if age < float(pending.get("window_s", DEFAULT_WINDOW_S)):
        return None
    base = pending.get("baseline") or {}
    deltas = {k: round(_num((memory or {}).get(k)) - _num(base.get(k)), 3)
              for k in _BASELINE_KEYS}
    # verdict: dispersion up + health up (or stuck down) = improved
    improved = deltas.get("disp_60s", 0) > 0 or deltas.get("stuck_duration", 0) < 0
    worse = (deltas.get("stuck_duration", 0) > 30
             or deltas.get("health_score", 0) < -0.05)
    verdict = "improved" if improved and not worse else ("worse" if worse else "unchanged")
    return {
        "resolved_at": time.time(),
        "age_s": round(age, 1),
        "keys": pending.get("keys", {}),
        "scene_id": pending.get("scene_id", ""),
        "scene_label": pending.get("scene_label", ""),
        "anomaly": pending.get("anomaly", "?"),
        "baseline": base,
        "deltas": deltas,
        "verdict": verdict,
        "help_reason": pending.get("help_reason", ""),
    }


def append_outcome(record: dict, path: Path = OUTCOMES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_outcomes(path: Path = OUTCOMES_PATH) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue  # skip torn tail lines
    return out


# ── pending persistence ───────────────────────────────────────────────
def save_pending(pending: dict, path: Path = PENDING_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load_pending(path: Path = PENDING_PATH) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_pending(path: Path = PENDING_PATH) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


# ── curriculum state machine (P4.3) ───────────────────────────────────
def _goal_met(goal: dict, memory: dict) -> bool:
    metric = goal.get("metric", "")
    value = _num((memory or {}).get(metric))
    target = _num(goal.get("target"))
    op = goal.get("op", "gt")
    if op == "gt":
        return value > target
    if op == "lt":
        return 0 < value < target or (target == 0 and value == 0)
    if op == "le":
        return value <= target
    return False


def load_curriculum(path: Path = CURRICULUM_PATH) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_curriculum(curriculum: dict, path: Path = CURRICULUM_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(curriculum, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


DEFAULT_CURRICULUM = {
    "course": "general-escape",
    "stage": 1,
    "goal": {"metric": "disp_60s", "op": "gt", "target": 30},
}


def update_curriculum(curriculum: Optional[dict], outcome: dict,
                      memory: dict, ok_streak: int = 2,
                      fail_streak: int = 3) -> Optional[dict]:
    """Advance/retreat the lesson plan from one resolved outcome.

    goal format: {"metric": "disp_60s", "op": "gt", "target": 30}
    ok_streak consecutive goal-met outcomes → stage += 1 (lesson learned);
    fail_streak consecutive not-met outcomes → stage -= 1 (floor 1).
    Seeds DEFAULT_CURRICULUM when absent (P1 bugfix: without seeding the
    state machine could never start).  Returns the updated curriculum.
    """
    if curriculum is None:
        curriculum = json.loads(json.dumps(DEFAULT_CURRICULUM))
    goal = curriculum.get("goal") or {}
    met = _goal_met(goal, memory)
    curriculum["attempts"] = int(curriculum.get("attempts", 0)) + 1
    curriculum["consecutive_ok"] = int(curriculum.get("consecutive_ok", 0) or 0)
    curriculum["consecutive_fail"] = int(curriculum.get("consecutive_fail", 0) or 0)
    if met:
        curriculum["consecutive_ok"] += 1
        curriculum["consecutive_fail"] = 0
    else:
        curriculum["consecutive_fail"] += 1
        curriculum["consecutive_ok"] = 0
    curriculum.setdefault("history", []).append({
        "at": round(time.time(), 1), "verdict": outcome.get("verdict", "?"),
        "met": met, "stage": curriculum.get("stage", 1)})
    curriculum["history"] = curriculum["history"][-20:]
    if curriculum["consecutive_ok"] >= ok_streak:
        curriculum["stage"] = int(curriculum.get("stage", 1)) + 1
        curriculum["consecutive_ok"] = 0
        curriculum["stage_advanced_at"] = round(time.time(), 1)
    elif curriculum["consecutive_fail"] >= fail_streak and curriculum.get("stage", 1) > 1:
        curriculum["stage"] = int(curriculum.get("stage", 1)) - 1
        curriculum["consecutive_fail"] = 0
        curriculum["stage_retreated_at"] = round(time.time(), 1)
    return curriculum


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
