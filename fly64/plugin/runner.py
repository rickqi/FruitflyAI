#!/usr/bin/env python3
"""Fly64 MHR plugin runner — the 10s periodic skill cycle.

Each cycle executes the closed loop:

    poll evolution/memory  ->  check_help_needed  ->  frame capture
        ->  llm_consult (GLM-5.3-flash multimodal)  ->  strategy write

Data comes from the Fly64 dashboard HTTP endpoints (same sources the
EvolutionSkill uses).  When the brain model is in an unsolvable state
(stuck > 60s, anomaly active, no reflex), the plugin escalates to
GLM-5.3-flash with the current game frame and writes the recommendation
to ``skills/active_strategy.json`` for hot-reload by the brain, plus
``skills/coach_advice.json`` for the dashboard.

Run standalone::

    python -m plugin.runner            # uses manifest defaults
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

try:  # package-relative (fly64 on sys.path)
    from plugin.llm_consult import (ConsultError, GLMConsultant,
                                    build_consult_request)
    from plugin.strategy_writer import StrategyWriter
except ImportError:  # direct execution from fly64/
    from llm_consult import ConsultError, GLMConsultant, build_consult_request
    from strategy_writer import StrategyWriter

PLUGIN_DIR = Path(__file__).resolve().parent
DEFAULT_DASHBOARD = "http://127.0.0.1:8765"
DEFAULT_INTERVAL = 10.0
STUCK_HELP_THRESHOLD = 60.0  # t20: lowered from 120s — coach intervenes earlier

HELP_TRIGGER_ENV = "FLY64_HELP_TRIGGER"  # optional JSON file to force consult


def fetch_json(base: str, endpoint: str, timeout: float = 5.0) -> Optional[dict]:
    """Fetch a dashboard JSON endpoint; None on any failure."""
    try:
        with urllib.request.urlopen(base.rstrip("/") + endpoint,
                                    timeout=timeout) as r:
            data = json.loads(r.read())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


class PluginRunner:
    """Periodic 10s skill cycle driver (first-class DSH plugin entry)."""

    def __init__(self, dashboard_base: Optional[str] = None,
                 interval: float = DEFAULT_INTERVAL,
                 consultant: Optional[GLMConsultant] = None,
                 writer: Optional[StrategyWriter] = None,
                 fetcher: Optional[Callable[[str], Optional[dict]]] = None):
        import os
        self.dashboard_base = (dashboard_base
                               or os.environ.get("FLY64_DASHBOARD_BASE")
                               or DEFAULT_DASHBOARD)
        self.interval = float(interval)
        self.consultant = consultant or GLMConsultant()
        self.writer = writer or StrategyWriter()
        self._fetcher = fetcher or (lambda ep: fetch_json(self.dashboard_base, ep))
        self.cycles = 0
        self.consultations = 0
        self.last_error: Optional[str] = None

    # ── data sources ─────────────────────────────────────────────────
    def fetch_snapshot(self) -> dict:
        """Poll evolution/memory (+flow for context) from the dashboard."""
        return {
            "evolution": self._fetcher("/evolution.json"),
            "memory": self._fetcher("/memory.json"),
            "flow": self._fetcher("/flow.json"),
            "help": self._fetcher("/help.json"),
        }

    def check_help_needed(self, snapshot: dict) -> Optional[dict]:
        """Decide whether the brain is in an unsolvable state.

        Trigger: dashboard /help.json has an active help_reason, OR
        (stuck > 60s AND anomaly active AND no reflex active) — the same
        CoachConsult escalation conditions.  Returns the consult context.
        """
        help_snap = snapshot.get("help")
        if isinstance(help_snap, dict) and help_snap.get("help_reason"):
            mem = snapshot.get("memory") or {}
            return {
                "help_reason": help_snap.get("help_reason"),
                "scene_name": help_snap.get("scene_name")
                              or mem.get("scene_name", "?"),
                "position": help_snap.get("position") or {},
                "diagnosis": help_snap.get("diagnosis", ""),
                "stuck_duration": float(mem.get("stuck_duration", 0.0)),
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": float(mem.get("health_score", 1.0)),
            }
        mem = snapshot.get("memory")
        if not isinstance(mem, dict):
            return None
        stuck = float(mem.get("stuck_duration", 0.0))
        no_reflex = not mem.get("reflex_active", False)
        anomaly = mem.get("anomaly_state", "idle") != "idle"
        # EVO R12: an ACTIVE reflex with ~zero 60 s displacement is by
        # definition not solving the problem — active reflex must not mask
        # the escalation (the 497.9s / 0u incident).
        reflex_ineffective = bool(mem.get("reflex_ineffective", False))
        if stuck > STUCK_HELP_THRESHOLD and anomaly and (no_reflex or reflex_ineffective):
            return {
                "help_reason": ("reflex_ineffective_stuck" if reflex_ineffective
                                else "unsolvable_stuck"),
                "scene_name": mem.get("scene_name", "?"),
                "position": mem.get("position") or {},
                "diagnosis": "",
                "stuck_duration": stuck,
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": float(mem.get("health_score", 1.0)),
                "disp_60s": mem.get("disp_60s"),
            }
        return None

    def capture_frame(self) -> Optional[str]:
        """Fetch the current game frame (base64) for multimodal input."""
        frame = self._fetcher("/frame.json")
        if isinstance(frame, dict) and frame.get("frame_b64"):
            return frame["frame_b64"]
        return None

    # ── one cycle ────────────────────────────────────────────────────
    def run_cycle(self) -> dict:
        """Execute one full 10s skill cycle. Returns a cycle summary."""
        self.cycles += 1
        result = {"cycle": self.cycles, "ts": round(time.time(), 2),
                  "consulted": False, "strategy_written": False}
        try:
            snapshot = self.fetch_snapshot()
            context = self.check_help_needed(snapshot)
            if context is None:
                result["status"] = "ok"
                result["detail"] = "no help needed"
                self.last_error = None
                return result
            result["context"] = context
            frame_b64 = self.capture_frame()
            parsed = self.consultant.consult(context, frame_b64)
            result["consulted"] = True
            self.consultations += 1
            strategy = parsed.get("strategy") or {}
            self.writer.write_strategy(strategy, advice=parsed.get("advice", ""),
                                       source=self.consultant.model)
            self.writer.write_advice(parsed.get("advice", ""), context=context,
                                     strategy=strategy,
                                     model=self.consultant.model)
            result["strategy_written"] = True
            result["advice"] = parsed.get("advice", "")
            result["status"] = "ok"
            self.last_error = None
        except ConsultError as exc:
            result["status"] = "consult_failed"
            result["error"] = str(exc)
            self.last_error = str(exc)
        except Exception as exc:  # keep the loop alive no matter what
            result["status"] = "error"
            result["error"] = f"{type(exc).__name__}: {exc}"
            self.last_error = result["error"]
        return result

    # ── periodic loop ────────────────────────────────────────────────
    def run_forever(self, max_cycles: Optional[int] = None) -> None:
        """Run the 10s periodic loop until interrupted."""
        n = 0
        while max_cycles is None or n < max_cycles:
            summary = self.run_cycle()
            print(f"[fly64-mhr] cycle {summary.get('cycle')} "
                  f"status={summary.get('status')} "
                  f"consulted={summary.get('consulted')}")
            n += 1
            if max_cycles is None or n < max_cycles:
                time.sleep(self.interval)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Fly64 MHR DSH plugin runner")
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    p.add_argument("--max-cycles", type=int, default=None)
    p.add_argument("--dashboard", type=str, default=None)
    args = p.parse_args()
    PluginRunner(dashboard_base=args.dashboard,
                 interval=args.interval).run_forever(args.max_cycles)


if __name__ == "__main__":
    main()
