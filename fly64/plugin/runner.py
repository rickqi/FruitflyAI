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

import base64
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

try:  # package-relative (fly64 on sys.path)
    from plugin.llm_consult import (ConsultError, GLMConsultant,
                                    build_consult_request,
                                    raw_rgb_b64_to_png_b64)
    from plugin.strategy_writer import StrategyWriter
    from plugin import coach_outcomes as co
except ImportError:  # direct execution from fly64/
    from llm_consult import (ConsultError, GLMConsultant, build_consult_request,
                             raw_rgb_b64_to_png_b64)
    from strategy_writer import StrategyWriter
    import coach_outcomes as co

PLUGIN_DIR = Path(__file__).resolve().parent
DEFAULT_DASHBOARD = "http://127.0.0.1:8765"
DEFAULT_INTERVAL = 10.0
STUCK_HELP_THRESHOLD = 60.0  # t20: lowered from 120s — coach intervenes earlier

# P1-2.3: multi-signal weighted trigger.  The 60s scalar stays as the hard
# floor (never delays intervention past t20 behaviour); the weighted score
# lets strong multi-signal evidence escalate EARLIER (e.g. stuck 50s +
# reflex ineffective + active MBON saturation + danger scene).
HELP_SCORE_THRESHOLD = 0.60
HELP_SCORE_WEIGHTS = {"stuck": 0.40, "reflex_ineffective": 0.25,
                      "saturation_rate": 0.20, "scene_danger": 0.15}
HELP_SCORE_ENV = "FLY64_HELP_SCORE_THRESHOLD"

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
        # M2.1: consecutive primitive completions with ~zero displacement
        self._prim_zero_run = 0
        self._prim_last_completed = 0
        # P1: pending coach-strategy outcome (attribution window)
        self._pending_outcome = co.load_pending()
        # P1-2.3: previous MBON saturation-event counter for rate estimation
        self._sat_prev: Optional[tuple] = None
        import os as _os
        try:
            self.help_score_threshold = float(
                _os.environ.get(HELP_SCORE_ENV, HELP_SCORE_THRESHOLD))
        except ValueError:
            self.help_score_threshold = HELP_SCORE_THRESHOLD

    def help_score(self, mem: dict, flow: Optional[dict]) -> tuple:
        """Multi-signal weighted escalation score in [0, 1] + components.

        stuck（归一 120s 封顶）0.4 · reflex_ineffective 0.25 ·
        MBON 饱和事件增速（≥10/min 封顶）0.2 · 场景 danger 0.15
        """
        mem = mem or {}
        flow = flow or {}
        components = {}
        stuck_norm = min(float(mem.get("stuck_duration", 0.0)) / 120.0, 1.0)
        components["stuck"] = round(stuck_norm, 3)
        score = HELP_SCORE_WEIGHTS["stuck"] * stuck_norm
        if mem.get("reflex_ineffective", False):
            components["reflex_ineffective"] = 1.0
            score += HELP_SCORE_WEIGHTS["reflex_ineffective"]
        events = float((flow.get("mb_saturation_events")) or 0.0)
        now = time.time()
        prev = self._sat_prev
        if prev is not None:
            d_events = max(0.0, events - prev[0])
            dt_min = max((now - prev[1]) / 60.0, 1e-6)
            sat = min(d_events / dt_min / 10.0, 1.0)
            components["saturation_rate"] = round(sat, 3)
            score += HELP_SCORE_WEIGHTS["saturation_rate"] * sat
        self._sat_prev = (events, now)
        danger = min(float(flow.get("scene_danger") or 0.0), 1.0)
        if danger > 0:
            components["scene_danger"] = round(danger, 3)
            score += HELP_SCORE_WEIGHTS["scene_danger"] * danger
        return round(min(score, 1.0), 3), components
        # M2.1: consecutive primitive completions with ~zero displacement
        self._prim_zero_run = 0
        self._prim_last_completed = 0

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
        mem = snapshot.get("memory") or {}
        # Y position for consult context (R31-fix8): extract early so all
        # return paths can include it.  memory.json now has an explicit
        # "pos_y" key; fall back to the y of "position" when absent.
        pos_y_ctx = (mem.get("pos_y", None)
                     or (mem.get("position") or {}).get("y", None))
        if isinstance(help_snap, dict) and help_snap.get("help_reason"):
            return {
                "help_reason": help_snap.get("help_reason"),
                "scene_name": help_snap.get("scene_name")
                              or mem.get("scene_name", "?"),
                "position": help_snap.get("position") or {},
                "pos_y": pos_y_ctx,
                "diagnosis": help_snap.get("diagnosis", ""),
                "stuck_duration": float(mem.get("stuck_duration", 0.0)),
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": float(mem.get("health_score", 1.0)),
            }
        mem = snapshot.get("memory")
        if not isinstance(mem, dict):
            return None
        # M2.1: primitive_ineffective — 3 consecutive completions that each
        # moved <30u mean the wrong primitive (or wrong timing) is being used
        # for this terrain; escalate to the coach with the primitive stats.
        cpg = mem.get("cpg") or {}
        completed = int(cpg.get("completed", 0) or 0)
        disp = mem.get("disp_60s")
        if completed > self._prim_last_completed:
            self._prim_last_completed = completed
            if isinstance(disp, (int, float)) and disp < 30.0:
                self._prim_zero_run += 1
            else:
                self._prim_zero_run = 0
        stuck = float(mem.get("stuck_duration", 0.0))
        # Y position for the consult context: prefer an explicit mem["pos_y"],
        # else the y of mem["position"].
        #
        # NOTE: scripts/m8_add_posy_to_consult.py added the three
        # `"pos_y": pos_y_ctx` entries below but its definition-insertion
        # replace silently failed to match (it searched for `stuck = ...` at
        # 12-space indent and assumed `no_reflex` followed on the next line,
        # whereas in this file `stuck = ...` is at 8 spaces and an
        # `if self._prim_zero_run >= 3:` block sits between them).  The result
        # was a NameError on every help-escalation path — i.e. the coach would
        # crash exactly when the fly is stuck.  The line below is the
        # definition that script intended to insert.
        pos_y_ctx = mem.get("pos_y", None) or (mem.get("position") or {}).get("y", None)
        if self._prim_zero_run >= 3:
            self._prim_zero_run = 0
            return {
                "help_reason": "primitive_ineffective",
                "scene_name": mem.get("scene_name", "?"),
                "position": mem.get("position") or {},
                "pos_y": pos_y_ctx,
                "diagnosis": (f"CPG primitive completed {cpg.get('completed', 0)}x "
                              f"but 3 consecutive runs moved <30u "
                              f"(last disp_60s={disp}) — wrong primitive or "
                              f"timing for this terrain"),
                "stuck_duration": stuck,
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": float(mem.get("health_score", 1.0)),
                "cpg": cpg,
                "disp_60s": disp,
            }
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
                "pos_y": pos_y_ctx,
                "diagnosis": "",
                "stuck_duration": stuck,
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": float(mem.get("health_score", 1.0)),
                "disp_60s": mem.get("disp_60s"),
                # M2.1: primitive stats so the coach can suggest a different
                # primitive via strategy {"primitives": {"prefer": {...}}}
                "cpg": mem.get("cpg") or {},
            }
        # P1-2.3: multi-signal weighted escalation — strong combined evidence
        # escalates EARLIER than the 60s floor (e.g. stuck 50s + reflex
        # ineffective + active saturation + danger scene).
        score, components = self.help_score(mem, snapshot.get("flow"))
        if score >= self.help_score_threshold and anomaly:
            return {
                "help_reason": "multi_signal_stuck",
                "scene_name": mem.get("scene_name", "?"),
                "position": mem.get("position") or {},
                "pos_y": pos_y_ctx,
                "diagnosis": f"weighted help score {score} ≥ "
                             f"{self.help_score_threshold}: {components}",
                "stuck_duration": stuck,
                "anomaly_state": mem.get("anomaly_state", "?"),
                "health_score": float(mem.get("health_score", 1.0)),
                "disp_60s": mem.get("disp_60s"),
                "cpg": mem.get("cpg") or {},
                "help_components": components,
            }
        # P0-4 / A2 §1.2 D2 (U1): HIGH-SPEED WEAVE — motion is not progress.
        # The two branches above both require an `anomaly` verdict or a >60 s
        # stuck clock; in the reported form (median speed 316 u/s, 60 s
        # displacement 28-2100 u, loop_score 0.93-0.99, stuck 54.2 s, health
        # 0.62) the classifier says idle — the same displacement misreading
        # pins it there — so the coach was never woken.  The question is now
        # decided by the ONE unit convention documented in fly64/memory.py's
        # progress-ledger block:
        #   displacement_per_speed = disp_60s / (median_speed * 60).
        weave = self._weave_escalation(mem, stuck, pos_y_ctx)
        if weave is not None:
            return weave
        return None

    def _weave_escalation(self, mem: dict, stuck: float,
                          pos_y_ctx) -> Optional[dict]:
        """P0-4: high-speed weave escalation — the coach's wake-up call that
        the classifier-gated branches cannot deliver (A2 §1.2 D2 / §5 U1).

        Contract (units in fly64/memory.py's progress-ledger block):
          * ``stuck_duration >= WEAVE_STUCK_DURATION`` (45 s, the relaxation the
            user proposed on 09-17: ``loop_score >= 0.95 AND escape AND
            stuck >= 45``), and
          * ``progress_is_ineffective(disp_60s, median_speed)`` — motion alone
            never counts as progress.

        ``reflex_active`` and ``anomaly_state`` are deliberately NOT consulted:
        an active reflex that weaves is the incident itself (EVO R12), and no
        field polluted by the old displacement gate may veto the escalation.
        Returns ``None`` when the prong does not apply (or when the brain
        package is not importable — the coach must never crash, D1).
        """
        try:
            from fly64.memory import (WEAVE_STUCK_DURATION,
                                      displacement_per_speed,
                                      progress_is_ineffective)
        except ImportError:  # pragma: no cover — never break the escalation path
            return None
        disp = mem.get("disp_60s")
        if stuck < WEAVE_STUCK_DURATION:
            return None
        if not progress_is_ineffective(disp, mem.get("median_speed")):
            return None
        return {
            "help_reason": "weave_no_progress",
            "scene_name": mem.get("scene_name", "?"),
            "position": mem.get("position") or {},
            "pos_y": pos_y_ctx,
            "diagnosis": (
                f"weave_no_progress: stuck={stuck:.1f}s ≥ "
                f"{WEAVE_STUCK_DURATION:.0f}s while the 60 s window shows no "
                f"real progress (disp_60s={disp}, median_speed="
                f"{mem.get('median_speed')}, displacement_per_speed="
                f"{displacement_per_speed(disp, mem.get('median_speed'))}); "
                f"anomaly_state={mem.get('anomaly_state', '?')} and "
                f"reflex_active={mem.get('reflex_active')} "
                f"(classifier/reflex disagree with behaviour)"),
            "stuck_duration": stuck,
            "anomaly_state": mem.get("anomaly_state", "?"),
            "health_score": float(mem.get("health_score", 1.0)),
            "disp_60s": disp,
            "median_speed": mem.get("median_speed"),
            "displacement_per_speed": displacement_per_speed(
                disp, mem.get("median_speed")),
            "cpg": mem.get("cpg") or {},
        }

    def capture_frame(self) -> Optional[str]:
        """Fetch the SM64 game screen (base64) for GLM multimodal input.

        Priority:
          1. ``/screen.json`` ``screen_b64`` → game frame (320×240, higher res).
          2. ``/help.json`` ``frame_b64`` → cubemap forward face (128×128, fallback).
          3. ``None`` when nothing is available.
        """
        screen = self._fetcher("/screen.json")
        if screen and isinstance(screen, dict) and screen.get("screen_b64"):
            return screen["screen_b64"]
        help_ = self._fetcher("/help.json")
        if help_ and isinstance(help_, dict) and help_.get("frame_b64"):
            return help_["frame_b64"]
        return None

    # ── consult frame snapshot (t21 wrap-up) ─────────────────────────
    FRAME_DIR = PLUGIN_DIR.parent / "runtime" / "coach_frames"

    @staticmethod
    def save_consult_frame(frame_b64: Optional[str],
                           help_reason: Optional[str] = None,
                           ts: Optional[float] = None,
                           frame_dir: Optional[Path] = None) -> Optional[str]:
        """Persist the consult frame as PNG under runtime/coach_frames/.

        Filename: ``coach_{ts}_{help_reason}.png`` (help_reason sanitised to
        filename-safe characters, default ``none``).  Best-effort: returns
        the written path or None; callers must not let failures block the
        consult.  Raw-RGB payloads are converted to real PNG via
        ``llm_consult.raw_rgb_b64_to_png_b64``.
        """
        if not frame_b64:
            return None
        # P0-fix: the screen.json frame is 320×240×3 raw RGB — the t21 code
        # called raw_rgb_b64_to_png_b64 with the DEFAULT 384×256 dims, the
        # size check failed and the frame was passed through unconverted, so
        # the PNG magic check silently dropped EVERY snapshot.  Reuse
        # frame_to_data_uri's dimension detection instead.
        try:
            from plugin.llm_consult import frame_to_data_uri
        except ImportError:
            from llm_consult import frame_to_data_uri
        try:
            uri = frame_to_data_uri(frame_b64)
        except Exception:
            return None
        if not uri or not uri.startswith("data:image/png;base64,"):
            return None  # unrecognised payload — still not an encoded image
        try:
            raw = base64.b64decode(uri.split(",", 1)[1], validate=True)
        except Exception:
            return None
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        stamp = round(float(ts if ts is not None else time.time()), 3)
        safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_",
                      str(help_reason or "none")).strip("_") or "none"
        target_dir = Path(frame_dir) if frame_dir else PluginRunner.FRAME_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"coach_{stamp}_{safe}.png"
        path.write_bytes(raw)
        return str(path)

    # ── one cycle ────────────────────────────────────────────────────
    def run_cycle(self) -> dict:
        """Execute one full 10s skill cycle. Returns a cycle summary."""
        self.cycles += 1
        result = {"cycle": self.cycles, "ts": round(time.time(), 2),
                  "consulted": False, "strategy_written": False}
        try:
            snapshot = self.fetch_snapshot()
            # P1: resolve a pending strategy-outcome window if due
            try:
                self._resolve_pending_outcome(snapshot, result)
            except Exception:
                pass  # attribution is best-effort, never break the cycle
            context = self.check_help_needed(snapshot)
            if context is None:
                result["status"] = "ok"
                result["detail"] = "no help needed"
                self.last_error = None
                return result
            result["context"] = context
            # P4.3: inject the lesson plan so the coach teaches with state
            try:
                curriculum = co.load_curriculum()
                if curriculum:
                    context["curriculum"] = curriculum
            except Exception:
                pass
            frame_b64 = self.capture_frame()
            # t21 wrap-up: snapshot the frame the coach is about to see, so
            # "what did the coach look at" is retroactively answerable.
            try:
                self.save_consult_frame(frame_b64, context.get("help_reason"))
            except Exception:
                pass  # snapshot is best-effort; never block the consult
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
            # P1: open the outcome-attribution window for this strategy
            try:
                self._pending_outcome = co.snapshot_outcome(
                    strategy, snapshot.get("memory") or {},
                    snapshot.get("flow") or {}, cycle=self.cycles,
                    help_reason=str(context.get("help_reason") or ""))
                co.save_pending(self._pending_outcome)
                result["outcome_pending"] = True
            except Exception:
                pass
        except ConsultError as exc:
            result["status"] = "consult_failed"
            result["error"] = str(exc)
            self.last_error = str(exc)
        except Exception as exc:  # keep the loop alive no matter what
            result["status"] = "error"
            result["error"] = f"{type(exc).__name__}: {exc}"
            self.last_error = result["error"]
        return result

    # ── P1: strategy outcome attribution ─────────────────────────────
    def _resolve_pending_outcome(self, snapshot: dict, result: dict) -> None:
        pending = self._pending_outcome or co.load_pending()
        if not pending:
            return
        outcome = co.resolve_outcome(pending, snapshot.get("memory") or {})
        if outcome is None:
            return  # window still open
        co.append_outcome(outcome)
        curriculum = co.update_curriculum(co.load_curriculum(), outcome,
                                          snapshot.get("memory") or {})
        if curriculum:
            co.save_curriculum(curriculum)
        # P4.4 (t7): feed the scene->strategy instinct binding.  Repeated
        # improvements for one scene promote the parameter set to an instinct
        # that the brain applies directly (no further consult for that scene).
        try:
            from fly64.instinct_bindings import record_outcome as _record_binding
            row = _record_binding(outcome.get("scene_label"),
                                  outcome.get("keys") or {},
                                  outcome.get("verdict", "unchanged"),
                                  outcome.get("deltas"))
            if row:
                result["binding"] = {"scene": row.get("scene"),
                                     "improved": row.get("improved"),
                                     "promoted": row.get("promoted")}
        except Exception:
            pass  # binding is best-effort
        co.clear_pending()
        self._pending_outcome = None
        result["outcome"] = {"verdict": outcome.get("verdict"),
                             "scene": outcome.get("scene_label")}

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
