#!/usr/bin/env python3
"""Fly64 autonomy resident service (WSL daemon entry).

Wraps :class:`plugin.runner.PluginRunner`'s 10s cycle into a long-lived
process that can be managed by systemd or ``nohup`` + pid file, and adds:

Health self-check (written to ``plugin/service_status.json`` every cycle)
    * ``dashboard_ok``      — dashboard HTTP reachable this cycle
    * ``bridge_fresh``      — bridge file mtime within ``--bridge-stale``
    * ``strategy_written``  — last consult produced a fresh strategy file
    * ``degraded``          — LLM consult unavailable, running local only

LLM consultation availability
    * ``http`` transport (``FLY64_LLM_*`` env) works without DSH.
    * ``subagent`` file-handshake transport depends on a live DSH session;
      it has a hard timeout and on failure the service **degrades**: it
      writes a local-diagnosis advice (from the dashboard snapshot) via
      StrategyWriter so EvolutionSkill/brain keep operating autonomously.
      Autonomy never depends on a DSH session being alive.

Run::

    python3 -m plugin.service                # foreground (systemd)
    python3 -m plugin.service --daemonize    # nohup + pid file mode

Stop::

    kill $(cat plugin/fly64-service.pid)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

try:  # package-relative (fly64 on sys.path)
    from plugin.llm_consult import ConsultError, GLMConsultant
    from plugin.runner import DEFAULT_DASHBOARD, DEFAULT_INTERVAL, PluginRunner, fetch_json
    from plugin.strategy_writer import StrategyWriter
except ImportError:  # direct execution from fly64/
    from llm_consult import ConsultError, GLMConsultant
    from runner import DEFAULT_DASHBOARD, DEFAULT_INTERVAL, PluginRunner, fetch_json
    from strategy_writer import StrategyWriter

PLUGIN_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PLUGIN_DIR.parent
STATUS_PATH = PLUGIN_DIR / "service_status.json"
PID_PATH = PLUGIN_DIR / "fly64-service.pid"
LOG_PATH = PLUGIN_DIR / "service.log"

DEFAULT_BRIDGE_PATH = os.environ.get("FLY64_BRIDGE_PATH", "/tmp/f64b")
DEFAULT_BRIDGE_STALE = 60.0  # seconds of bridge mtime age before unhealthy
MAX_CONSECUTIVE_FAILURES = 5  # alert threshold in the status heartbeat

LOCAL_DIAGNOSIS_SOURCE = "local_diagnosis"


class HealthChecker:
    """Cycle health self-check for the resident autonomy service."""

    def __init__(self, dashboard_base: str,
                 bridge_path: str = DEFAULT_BRIDGE_PATH,
                 bridge_stale: float = DEFAULT_BRIDGE_STALE,
                 strategy_path: Optional[Path] = None,
                 fetcher: Optional[callable] = None):
        self.dashboard_base = dashboard_base
        self.bridge_path = Path(bridge_path)
        self.bridge_stale = float(bridge_stale)
        self.strategy_path = Path(strategy_path) if strategy_path \
            else PROJECT_DIR / "skills" / "active_strategy.json"
        self._fetcher = fetcher or (lambda ep: fetch_json(dashboard_base, ep))
        self._last_strategy_mtime: Optional[float] = None

    def check_dashboard(self) -> dict:
        data = self._fetcher("/evolution.json")
        # evolution.json is legitimately `{}` between evolution rounds
        # (in-memory iteration log) — only None/exception means unreachable.
        ok = data is not None
        return {"ok": ok, "detail": "reachable" if ok else "unreachable"}

    def check_bridge(self) -> dict:
        try:
            age = time.time() - self.bridge_path.stat().st_mtime
        except OSError:
            return {"ok": False, "detail": "missing", "age": None}
        return {"ok": age <= self.bridge_stale, "detail": f"age={age:.0f}s",
                "age": round(age, 1)}

    def check_strategy_write(self) -> dict:
        """Confirm the strategy file is being written out after consults."""
        try:
            mtime = self.strategy_path.stat().st_mtime
        except OSError:
            return {"ok": True, "detail": "no strategy yet (no consult)"}
        if self._last_strategy_mtime is None:
            self._last_strategy_mtime = mtime
            return {"ok": True, "detail": "observed"}
        wrote = mtime > self._last_strategy_mtime
        self._last_strategy_mtime = max(self._last_strategy_mtime, mtime)
        return {"ok": True, "detail": "written" if wrote else "unchanged since last consult"}


def local_diagnosis(context: dict) -> dict:
    """Degraded-mode advice built purely from the dashboard snapshot.

    Keeps autonomy alive when both LLM transports are unavailable (no
    FLY64_LLM_* env and no live DSH session for the file handshake).
    EVO T1: advice now includes concrete, actionable suggestions derived
    from the context instead of a bare "LLM unavailable" note.
    """
    stuck = float(context.get("stuck_duration", 0.0))
    anomaly = context.get("anomaly_state", "?")
    scene = context.get("scene_name", "?")
    disp = context.get("disp_60s")
    actions: list[str] = []
    if anomaly == "micro_loop" or (stuck > 90):
        actions.append("保持 forced_bold_explore 突围（转向0.5s/直行2.5s 占空比），"
                       "突围朝向取 opening_score 高的扇区方位")
    if disp is not None and disp < 30.0:
        actions.append("60s 位移 <30u：连续 2 个突围循环零位移后跳转+转向90°换面")
    if str(scene).startswith("室内") or "室内" in str(scene):
        actions.append("室内态：悬崖规避降敏（绿地缺失正常），改为沿墙缘直行")
    if not actions:
        actions.append("维持当前 steering/escape 级联，10s 后复诊")
    advice = (f"[local] scene={scene} stuck={stuck:.0f}s anomaly={anomaly}"
              + (f" disp60={disp}u" if disp is not None else "")
              + f"; LLM 不可用，本地处置建议: " + "；".join(actions) + ".")
    return {"advice": advice, "strategy": {}}


class ServiceRunner:
    """Resident supervisor around PluginRunner's 10s cycle."""

    def __init__(self, dashboard_base: Optional[str] = None,
                 interval: float = DEFAULT_INTERVAL,
                 bridge_path: str = DEFAULT_BRIDGE_PATH,
                 bridge_stale: float = DEFAULT_BRIDGE_STALE,
                 consultant: Optional[GLMConsultant] = None,
                 writer: Optional[StrategyWriter] = None,
                 status_path: Path = STATUS_PATH,
                 log=None):
        self.runner = PluginRunner(dashboard_base=dashboard_base,
                                   interval=interval, consultant=consultant,
                                   writer=writer)
        self.health = HealthChecker(self.runner.dashboard_base,
                                    bridge_path=bridge_path,
                                    bridge_stale=bridge_stale,
                                    strategy_path=writer.strategy_path
                                    if writer else None)
        self.status_path = Path(status_path)
        self.log = log or print
        self.consecutive_failures = 0
        self.degraded = False
        self._stop = False

    # ── signals ──────────────────────────────────────────────────────
    def request_stop(self, signum, _frame) -> None:
        self.log(f"[service] signal {signum} -> stopping")
        self._stop = True

    # ── degraded consult ─────────────────────────────────────────────
    def _consult_with_fallback(self, context: dict, frame_b64: Optional[str]) -> dict:
        """Consult LLM; degrade to local diagnosis on ConsultError."""
        try:
            parsed = self.runner.consultant.consult(context, frame_b64)
            self.degraded = False
            return parsed
        except ConsultError as exc:
            self.degraded = True
            self.log(f"[service] LLM unavailable ({exc}) -> local diagnosis")
            return local_diagnosis(context)

    # ── one supervised cycle ─────────────────────────────────────────
    def run_cycle(self) -> dict:
        # Supervised cycle: same flow as PluginRunner.run_cycle but consult
        # goes through the degradation fallback and health is reported.
        r = self.runner
        r.cycles += 1
        result = {"cycle": r.cycles, "ts": round(time.time(), 2),
                  "consulted": False, "strategy_written": False}
        dash = {"ok": False, "detail": "not run"}
        bridge = {"ok": False, "detail": "not run"}
        strategy_check = {"ok": True, "detail": "no consult this cycle"}
        try:
            snapshot = r.fetch_snapshot()
            context = r.check_help_needed(snapshot)
            dash = self.health.check_dashboard()
            bridge = self.health.check_bridge()
            if context is None:
                result["status"] = "ok"
                result["detail"] = "no help needed"
                r.last_error = None
            else:
                result["context"] = context
                frame_b64 = r.capture_frame()
                parsed = self._consult_with_fallback(context, frame_b64)
                result["consulted"] = True
                r.consultations += 1
                strategy = parsed.get("strategy") or {}
                r.writer.write_strategy(strategy, advice=parsed.get("advice", ""),
                                        source=(LOCAL_DIAGNOSIS_SOURCE
                                                if self.degraded else r.consultant.model))
                r.writer.write_advice(parsed.get("advice", ""), context=context,
                                      strategy=strategy,
                                      model=(LOCAL_DIAGNOSIS_SOURCE
                                             if self.degraded else r.consultant.model))
                result["strategy_written"] = True
                result["advice"] = parsed.get("advice", "")
                strategy_check = self.health.check_strategy_write()
                result["status"] = "ok"
                r.last_error = None
        except Exception as exc:  # never die on a single cycle failure
            result["status"] = "error"
            result["error"] = f"{type(exc).__name__}: {exc}"
            r.last_error = result["error"]
        if result["status"] == "ok":
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
        result["health"] = {
            "dashboard": dash,
            "bridge": bridge,
            "strategy_write": strategy_check,
            "degraded": self.degraded,
            "consecutive_failures": self.consecutive_failures,
            "alert": self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES,
        }
        self._write_status(result)
        if result["health"]["alert"]:
            self.log(f"[service][ALERT] {self.consecutive_failures} consecutive "
                     f"failures; last error: {result.get('error')}")
        return result

    def _write_status(self, result: dict) -> None:
        try:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.status_path)
        except OSError as exc:
            self.log(f"[service] cannot write status: {exc}")

    # ── main loop ────────────────────────────────────────────────────
    def run_forever(self, max_cycles: Optional[int] = None) -> None:
        n = 0
        while not self._stop and (max_cycles is None or n < max_cycles):
            summary = self.run_cycle()
            self.log(f"[service] cycle {summary.get('cycle')} "
                     f"status={summary.get('status')} "
                     f"consulted={summary.get('consulted')} "
                     f"degraded={self.degraded}")
            n += 1
            if not self._stop and (max_cycles is None or n < max_cycles):
                self._sleep(self.runner.interval)

    def _sleep(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while not self._stop and time.time() < deadline:
            time.sleep(min(0.5, max(0.0, deadline - time.time())))


def write_pid(path: Path = PID_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Fly64 autonomy resident service")
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    p.add_argument("--dashboard", type=str, default=None)
    p.add_argument("--bridge-path", type=str, default=DEFAULT_BRIDGE_PATH)
    p.add_argument("--bridge-stale", type=float, default=DEFAULT_BRIDGE_STALE)
    p.add_argument("--max-cycles", type=int, default=None)
    p.add_argument("--pid-file", type=str, default=str(PID_PATH))
    p.add_argument("--log-file", type=str, default=str(LOG_PATH))
    args = p.parse_args()

    pid_path = Path(args.pid_file)
    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        log_fh.write(line + "\n")
        log_fh.flush()

    write_pid(pid_path)
    service = ServiceRunner(dashboard_base=args.dashboard,
                            interval=args.interval,
                            bridge_path=args.bridge_path,
                            bridge_stale=args.bridge_stale,
                            log=log)
    signal.signal(signal.SIGTERM, service.request_stop)
    signal.signal(signal.SIGINT, service.request_stop)
    log(f"[service] started pid={os.getpid()} dashboard={service.runner.dashboard_base}")
    try:
        service.run_forever(args.max_cycles)
    finally:
        log("[service] stopped")
        log_fh.close()
        try:
            if pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                pid_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
