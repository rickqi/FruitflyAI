#!/usr/bin/env python3
"""Strategy hot-reload writer for the Fly64 MHR plugin.

Writes two files consumed elsewhere:

``skills/active_strategy.json``
    Hot-reloaded by the brain model (``fly64.main.load_active_strategy``)
    every 600 ticks.  Contains the ``fallen_recovery`` section understood
    by the brain plus optional ``exploration`` / ``escape`` threshold
    sections for other consumers.

``skills/coach_advice.json``
    Latest LLM coach advice text + capped consultation history, served by
    the dashboard at ``/coach_advice.json`` and rendered by
    ``web/dashboard.js``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills"
STRATEGY_PATH = SKILL_DIR / "active_strategy.json"
ADVICE_PATH = SKILL_DIR / "coach_advice.json"
HISTORY_LIMIT = 20


class StrategyWriter:
    """Atomically persist LLM strategy + advice for hot-reload consumers."""

    def __init__(self, strategy_path: Path = STRATEGY_PATH,
                 advice_path: Path = ADVICE_PATH,
                 history_limit: int = HISTORY_LIMIT):
        self.strategy_path = Path(strategy_path)
        self.advice_path = Path(advice_path)
        self.history_limit = max(1, int(history_limit))

    # ── atomic JSON helper ────────────────────────────────────────────
    def _atomic_write(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        os.replace(tmp, path)  # atomic on POSIX & Windows

    # ── strategy ──────────────────────────────────────────────────────
    def write_strategy(self, strategy: dict, advice: str = "",
                       source: str = "glm-5v-turbo",
                       what_i_see: Optional[list] = None) -> dict:
        """Write active_strategy.json (brain hot-reloads every 600 ticks).

        ``strategy`` may carry ``fallen_recovery`` / ``exploration`` /
        ``escape`` sections; ``advice`` (the coach_advice text) is embedded
        so the dashboard can show why the strategy changed.  t21: pass
        ``what_i_see`` (explicit screen-text readout) to persist it at the
        payload top level.

        P1-2: ``strategy["command"]`` is the coach's direct-control channel and
        ``strategy["coach_acceptance"]`` is the requested-vs-accepted record
        produced by ``llm_consult.acceptance_report``; both ride through
        unchanged.  A ``command`` written here is timestamped (``ts``) when the
        producer did not do it, because main.py's telemetry reports
        ``coach_applied.command_ts`` — without a stamp that field was always
        empty, so "command 有没有被消费" was unobservable.
        """
        payload = dict(strategy or {})
        # RULE-19 contract fix (EVO-072): merge with the on-disk strategy
        # instead of wholesale replace, so EVO-owned state survives a coach
        # write — previously the coach erased `__generation` and any evolved
        # param the coach's strategy dict did not mention, silently resetting
        # the Phase 6 search (机制存在、报告成功、无法生效).
        try:
            with open(self.strategy_path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if isinstance(existing, dict):
                merged = dict(existing)
                for sec, body in payload.items():
                    if (isinstance(body, dict) and isinstance(merged.get(sec), dict)):
                        # section merge: coach keys win, EVO keys preserved
                        merged[sec] = {**merged[sec], **body}
                    else:
                        merged[sec] = body
                payload = merged
        except (OSError, ValueError):
            pass  # no existing file / corrupt — coach payload stands alone
        if what_i_see:
            payload["what_i_see"] = list(what_i_see)
        # P1-2: stamp the direct-control command so coach_applied.command_ts
        # (main.py telemetry) can prove it was written and when.  Idempotent:
        # a producer-supplied ts wins.
        cmd = payload.get("command")
        if isinstance(cmd, dict) and cmd.get("type"):
            payload["command"] = {**cmd, "ts": cmd.get("ts") or round(time.time(), 2)}
        payload["coach_advice"] = advice
        payload["advice_ts"] = round(time.time(), 2)
        payload["source"] = source
        self._atomic_write(self.strategy_path, payload)
        return payload

    def write_dialogue_decision(self, action: str, reason: str = "",
                                source: str = "glm-5v-turbo",
                                wait_seconds: Optional[float] = None,
                                timed_out: bool = False) -> dict:
        """Merge a ``dialogue_decision`` block into active_strategy.json.

        ``action`` is ``press_a`` | ``press_b`` | ``none`` (``timeout``
        fallback writes ``press_a`` with ``timed_out=True``).  Existing
        strategy sections (fallen_recovery / exploration / escape) are
        preserved so the brain's hot-reload keeps working unchanged.
        """
        payload = self.load_strategy() or {}
        decision = {
            "action": str(action or "none"),
            "reason": str(reason or ""),
            "source": source,
            "timed_out": bool(timed_out),
            "ts": round(time.time(), 2),
        }
        if wait_seconds is not None:
            decision["wait_seconds"] = round(float(wait_seconds), 1)
        payload["dialogue_decision"] = decision
        self._atomic_write(self.strategy_path, payload)
        return payload

    def load_strategy(self) -> Optional[dict]:
        try:
            return json.loads(self.strategy_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    # ── advice / history ──────────────────────────────────────────────
    def load_advice(self) -> dict:
        try:
            data = json.loads(self.advice_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {"advice": "", "history": []}

    def write_advice(self, advice: str, context: Optional[dict] = None,
                     strategy: Optional[dict] = None,
                     model: str = "glm-5v-turbo",
                     what_i_see: Optional[list] = None) -> dict:
        """Update coach_advice.json with the latest advice + history entry.

        t21: ``what_i_see`` (explicit screen-text readout) is stored at the
        payload top level when provided; it also rides inside ``strategy``
        when the caller passes the sanitised strategy dict.

        P1-2: when ``strategy`` carries the ``coach_acceptance`` record
        (``llm_consult.acceptance_report``), it is also surfaced at the entry
        and payload top level so an operator can compare "what the coach asked
        for" against "what the pipeline accepted" — including the effective
        value the brain's clamp will use — without reading the raw reply.
        """
        data = self.load_advice()
        history = data.get("history")
        if not isinstance(history, list):
            history = []
        entry = {
            "advice": str(advice or ""),
            "context": context or {},
            "strategy": strategy or {},
            "model": model,
            "ts": round(time.time(), 2),
        }
        if what_i_see:
            entry["what_i_see"] = list(what_i_see)
        acceptance = (strategy or {}).get("coach_acceptance") \
            if isinstance(strategy, dict) else None
        if isinstance(acceptance, dict):
            entry["coach_acceptance"] = acceptance
        history.append(entry)
        history = history[-self.history_limit:]
        payload = {
            "advice": entry["advice"],
            "model": model,
            "ts": entry["ts"],
            "strategy": strategy or {},
            "history": history,
        }
        if what_i_see:
            payload["what_i_see"] = list(what_i_see)
        if isinstance(acceptance, dict):
            payload["coach_acceptance"] = acceptance
        self._atomic_write(self.advice_path, payload)
        return payload
