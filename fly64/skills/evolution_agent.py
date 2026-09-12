#!/usr/bin/env python3
"""
Fly64 Evolution Agent — Autonomous motion diagnosis & self-improvement skill.

监视 → 诊断 → 修复生成 → 效果跟踪 闭环。
每秒采集运动数据，检测异常模式，分析根因，生成代码修复，验证效果。

用法:
  python3 -m fly64.skills.evolution_agent [--interval 5] [--auto-fix] [--max-iterations 10]
"""

import json
import time
import urllib.request
import urllib.error
import sys
import os
import argparse
from pathlib import Path
from collections import deque
from typing import Optional

DASHBOARD_BASE = "http://127.0.0.1:8765"
WORKSPACE = Path(__file__).resolve().parent.parent.parent  # flygym root
SKILL_DIR = Path(__file__).resolve().parent
FIX_LOG = SKILL_DIR / "evolution_fixes.json"

# ── Problem patterns ──────────────────────────────────────────────────

PROBLEM_PATTERNS = [
    {
        "id": "circle_loop",
        "name": "Circle loop — 无障碍转圈",
        "conditions": {
            "wall_score": {"max": 0.1},
            "asymmetry_magnitude": {"max": 0.05},
            "stuck_duration": {"min": 120},
            "ground_angle": {"min": 0.3},
        },
        "contradiction": "terrain=cliff but ground_angle>0.3 (not a cliff)",
        "diagnosis": "Terrain classifier false-positive 'cliff'; cliff avoidance overrides straight-forward escape.",
        "fix_template": """# Fix: Add ground_angle gate before cliff avoidance
# File: fly64/fly64/main.py
# Find: {cliff_trigger_line}
# Replace: {cliff_trigger_replace}
""",
        "fix_files": ["fly64/fly64/main.py"],
    },
    {
        "id": "ramp_trap",
        "name": "Ramp trap — 斜坡上无法脱困",
        "conditions": {
            "ramp_score": {"min": 0.5},
            "stuck_duration": {"min": 180},
            "position_unchanged_60s": True,
        },
        "diagnosis": "Ramp suppression blocks turning; Mario stays on slope.",
        "fix_template": """# Fix: Add ramp escape override when stuck >180s on slope
# File: fly64/fly64/main.py
# Add after slope detection:
if ramp_score > 0.5 and stuck_duration > 180:
    control.x = rng.integers(60, 80) * (-1 if rng.random() < 0.5 else 1)
    control.y = 40
""",
        "fix_files": ["fly64/fly64/main.py"],
    },
    {
        "id": "reflex_cooldown_gap",
        "name": "Reflex cooldown — 冷却期内无效 escape",
        "conditions": {
            "anomaly_state_not_idle": True,
            "reflex_active": False,
            "stuck_duration": {"min": 60},
        },
        "diagnosis": "Reflex correctly detects anomaly but cooldown prevents re-trigger; normal escape ineffective.",
        "fix_template": """# Fix: Reduce reflex cooldown during persistent anomaly
# File: fly64/fly64/memory.py  
# Change: cooldown_duration = 10.0 → cooldown_duration = 5.0
# Or: Make cooldown adaptive based on stuck_duration progression
""",
        "fix_files": ["fly64/fly64/memory.py"],
    },
    {
        "id": "low_coverage_stagnation",
        "name": "Coverage stagnation — 覆盖率长期不增长",
        "conditions": {
            "coverage_stagnant_120s": True,
            "visited_cells": {"max": 50},
        },
        "diagnosis": "Mario trapped in small area; exploration strategy insufficient.",
        "fix_template": """# Fix: Trigger forced_bold_explore immediately when coverage stagnant
# File: fly64/fly64/main.py
# Add before normal escape:
if coverage_stagnant_120s and visited_cells < 50:
    forced_bold_explore = True
""",
        "fix_files": ["fly64/fly64/main.py"],
    },
]


# ── Data Collection ───────────────────────────────────────────────────

def fetch_json(endpoint: str) -> Optional[dict]:
    url = f"{DASHBOARD_BASE}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return None


class MotionBuffer:
    """Maintains rolling window of motion data for pattern detection."""

    def __init__(self, window_seconds: int = 120):
        self.window_seconds = window_seconds
        self.positions: deque[tuple[float, float, float, float]] = deque()  # (t, x, z, y)
        self.controls: deque[tuple[float, float, float]] = deque()  # (t, x, y)
        self.stuck_history: deque[tuple[float, float]] = deque()   # (t, stuck_duration)
        self.coverage_history: deque[tuple[float, float]] = deque()  # (t, pct)

    def add(self, bridge: dict, memory: dict, t: float):
        pose = bridge.get("pose", [0, 0, 0])
        self.positions.append((t, pose[0], pose[2], pose[1]))
        self.controls.append((t, bridge.get("x", 0), bridge.get("y", 0)))
        self.stuck_history.append((t, memory.get("stuck_duration", 0)))
        self.coverage_history.append((t, memory.get("coverage_pct", 0)))
        self._trim()

    def _trim(self):
        cutoff = time.time() - self.window_seconds
        for dq in [self.positions, self.controls, self.stuck_history, self.coverage_history]:
            while dq and dq[0][0] < cutoff:
                dq.popleft()

    def position_unchanged_60s(self) -> bool:
        if len(self.positions) < 10:
            return False
        recent = list(self.positions)[-10:]
        x_vals = [p[1] for p in recent]
        z_vals = [p[2] for p in recent]
        dx = max(x_vals) - min(x_vals)
        dz = max(z_vals) - min(z_vals)
        return dx < 50 and dz < 50

    def coverage_stagnant_120s(self) -> bool:
        if len(self.coverage_history) < 5:
            return False
        first = self.coverage_history[0][1]
        last = self.coverage_history[-1][1]
        return abs(last - first) < 0.5


# ── Diagnosis Engine ──────────────────────────────────────────────────

class DiagnosisEngine:
    """Analyzes motion data and identifies problem patterns."""

    def __init__(self, buffer: MotionBuffer):
        self.buffer = buffer

    def evaluate(self, memory: dict, flow: dict) -> list[dict]:
        findings = []
        t = time.time()

        for pattern in PROBLEM_PATTERNS:
            match = self._check_pattern(pattern, memory, flow, t)
            if match:
                findings.append({
                    "pattern_id": pattern["id"],
                    "pattern_name": pattern["name"],
                    "diagnosis": pattern["diagnosis"],
                    "contradiction": pattern.get("contradiction", ""),
                    "fix_template": pattern["fix_template"],
                    "fix_files": pattern["fix_files"],
                    "current_values": match,
                    "timestamp": t,
                })
        return findings

    def _check_pattern(self, pattern: dict, memory: dict, flow: dict, t: float) -> Optional[dict]:
        cond = pattern["conditions"]
        values = {}

        # Numeric threshold checks
        for key, threshold in cond.items():
            if key == "asymmetry_magnitude":
                val = abs(flow.get("asymmetry", 1))
            elif key == "position_unchanged_60s":
                if not self.buffer.position_unchanged_60s():
                    return None
                values[key] = True
                continue
            elif key == "coverage_stagnant_120s":
                if not self.buffer.coverage_stagnant_120s():
                    return None
                values[key] = True
                continue
            elif key == "anomaly_state_not_idle":
                if memory.get("anomaly_state", "idle") == "idle":
                    return None
                values[key] = memory.get("anomaly_state", "?")
                continue
            elif key == "reflex_active":
                if memory.get("reflex_active", False):
                    return None
                values[key] = False
                continue
            elif key == "ground_angle":
                val = flow.get("ground_angle", 1)
            elif key == "wall_score":
                val = flow.get("wall_score", 1)
            elif key == "ramp_score":
                val = flow.get("ramp_score", 0)
            elif key == "stuck_duration":
                val = memory.get("stuck_duration", 0)
            elif key == "visited_cells":
                val = memory.get("visited_cells", 100)
            else:
                val = memory.get(key, flow.get(key, 0))

            values[key] = val

            # Check min/max
            if "min" in threshold and val < threshold["min"]:
                return None
            if "max" in threshold and val > threshold["max"]:
                return None

        return values


# ── Fix Application ──────────────────────────────────────────────────

class FixManager:
    """Tracks applied fixes and their effectiveness."""

    def __init__(self):
        self.fixes = self._load()

    def _load(self) -> list[dict]:
        if FIX_LOG.exists():
            try:
                return json.loads(FIX_LOG.read_text())
            except:
                return []
        return []

    def save(self):
        FIX_LOG.parent.mkdir(parents=True, exist_ok=True)
        FIX_LOG.write_text(json.dumps(self.fixes, indent=2))

    def record_fix(self, pattern_id: str, diagnosis: str, fix_code: str):
        entry = {
            "id": f"fix_{len(self.fixes) + 1}",
            "pattern_id": pattern_id,
            "diagnosis": diagnosis,
            "fix_code": fix_code,
            "applied_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "baseline_stuck": None,
            "post_fix_stuck": None,
            "effective": None,
        }
        self.fixes.append(entry)
        self.save()
        return entry

    def record_baseline(self, entry: dict, stuck: float):
        entry["baseline_stuck"] = stuck
        self.save()

    def record_outcome(self, entry: dict, stuck: float):
        entry["post_fix_stuck"] = stuck
        if entry["baseline_stuck"] and stuck < entry["baseline_stuck"] * 0.5:
            entry["effective"] = True
        else:
            entry["effective"] = False
        self.save()

    def has_fix(self, pattern_id: str) -> bool:
        return any(f["pattern_id"] == pattern_id for f in self.fixes)


# ── Main Loop ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fly64 Evolution Agent")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument("--auto-fix", action="store_true", help="Auto-apply generated fixes")
    parser.add_argument("--max-iterations", type=int, default=10, help="Max fix iterations before stopping")
    args = parser.parse_args()

    print("╔═══════════════════════════════════════════╗")
    print("║  Fly64 Evolution Agent — Active           ║")
    print("║  Monitoring + Diagnosis + Self-Improve    ║")
    print("╚═══════════════════════════════════════════╝")
    print(f"   Interval: {args.interval}s | Auto-fix: {args.auto_fix}")
    print(f"   Dashboard: {DASHBOARD_BASE}")
    print(f"   Workspace: {WORKSPACE}")
    print()

    buffer = MotionBuffer(window_seconds=120)
    engine = DiagnosisEngine(buffer)
    fix_mgr = FixManager()
    iteration = 0
    stuck_trend = deque(maxlen=12)  # 1 min trend

    while iteration < args.max_iterations:
        iteration += 1
        t = time.time()

        # ── Sample ──
        bridge = fetch_json("/bridge-status.json")
        memory = fetch_json("/memory.json")
        flow = fetch_json("/flow.json")
        events = fetch_json("/events.json")

        if not all([bridge, memory, flow, events]):
            print(f"[{time.strftime('%H:%M:%S')}] ⚠ Waiting for dashboard...")
            time.sleep(args.interval)
            continue

        buffer.add(bridge, memory, t)
        stuck_trend.append((t, memory.get("stuck_duration", 0)))

        # ── Status ──
        pose = bridge.get("pose", [0, 0, 0])
        x, y, j = bridge.get("x", 0), bridge.get("y", 0), bridge.get("jump", False)
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"pos=({pose[0]:.0f},{pose[1]:.0f},{pose[2]:.0f}) "
              f"ctrl=({x},{y},{int(j)}) "
              f"stuck={memory.get('stuck_duration',0):.0f}s "
              f"cells={memory.get('visited_cells',0)} "
              f"coverage={memory.get('coverage_pct',0):.1f}% "
              f"anomaly={memory.get('anomaly_state','?')} "
              f"health={memory.get('health_score',1):.2f} "
              f"wall={flow.get('wall_score',0):.2f} "
              f"asym={flow.get('asymmetry',0):.3f} "
              f"ground={flow.get('ground_angle',0):.2f} "
              f"terrain={flow.get('terrain','?')} "
              f"reflex={memory.get('reflex_active',False)}")

        # ── Diagnose ──
        findings = engine.evaluate(memory, flow)

        if findings:
            for f in findings:
                pid = f["pattern_id"]
                if fix_mgr.has_fix(pid):
                    continue  # already applied

                print(f"\n  🔍 DETECTED: {f['pattern_name']}")
                print(f"     {f['diagnosis']}")
                if f.get("contradiction"):
                    print(f"     Contradiction: {f['contradiction']}")
                print(f"     Values: {f['current_values']}")

                if args.auto_fix:
                    entry = fix_mgr.record_fix(pid, f["diagnosis"], f["fix_template"])
                    fix_mgr.record_baseline(entry, memory.get("stuck_duration", 0))
                    print(f"  ✅ Fix recorded (id={entry['id']}). Effect pending...")
                else:
                    print(f"  💡 To apply fix:\n{f['fix_template']}")
        else:
            print(f"     ✅ No known patterns")

        # ── Monitor fix effectiveness ──
        for fix in fix_mgr.fixes:
            if fix.get("effective") is None and fix.get("baseline_stuck"):
                stuck = memory.get("stuck_duration", 0)
                if stuck < fix["baseline_stuck"] * 0.5:
                    fix_mgr.record_outcome(fix, stuck)
                    print(f"  ✅ Fix {fix['id']} EFFECTIVE! stuck {fix['baseline_stuck']:.0f}→{stuck:.0f}s")
                elif len(stuck_trend) == stuck_trend.maxlen:
                    all_lower = all(s[1] < fix["baseline_stuck"] * 0.8 for s in stuck_trend)
                    if all_lower:
                        fix_mgr.record_outcome(fix, stuck)
                        print(f"  ✅ Fix {fix['id']} trending effective")

        # Log summary
        summary = {
            "timestamp": t,
            "position": {"x": pose[0], "y": pose[1], "z": pose[2]},
            "control": {"x": x, "y": y, "jump": j},
            "stuck_duration": memory.get("stuck_duration", 0),
            "visited_cells": memory.get("visited_cells", 0),
            "coverage_pct": memory.get("coverage_pct", 0),
            "anomaly_state": memory.get("anomaly_state", "idle"),
            "health_score": memory.get("health_score", 1),
            "wall_score": flow.get("wall_score", 0),
            "asymmetry": flow.get("asymmetry", 0),
            "ground_angle": flow.get("ground_angle", 1),
            "terrain": flow.get("terrain", "?"),
            "reflex_active": memory.get("reflex_active", False),
            "findings": [f["pattern_id"] for f in findings],
        }
        log_file = SKILL_DIR / "evolution_log.jsonl"
        with open(log_file, "a") as lf:
            lf.write(json.dumps(summary) + "\n")

        time.sleep(args.interval)

    print(f"\n{'='*50}")
    print(f"Evolution Agent completed {args.max_iterations} iterations.")
    print(f"Fixes applied: {len(fix_mgr.fixes)}")
    print(f"Fix log: {FIX_LOG}")
    print(f"Data log: {SKILL_DIR / 'evolution_log.jsonl'}")


if __name__ == "__main__":
    main()