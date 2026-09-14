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
                       source: str = "glm-5.3-flash") -> dict:
        """Write active_strategy.json (brain hot-reloads every 600 ticks).

        ``strategy`` may carry ``fallen_recovery`` / ``exploration`` /
        ``escape`` sections; ``advice`` (the coach_advice text) is embedded
        so the dashboard can show why the strategy changed.
        """
        payload = dict(strategy or {})
        payload["coach_advice"] = advice
        payload["advice_ts"] = round(time.time(), 2)
        payload["source"] = source
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
                     model: str = "glm-5.3-flash") -> dict:
        """Update coach_advice.json with the latest advice + history entry."""
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
        history.append(entry)
        history = history[-self.history_limit:]
        payload = {
            "advice": entry["advice"],
            "model": model,
            "ts": entry["ts"],
            "strategy": strategy or {},
            "history": history,
        }
        self._atomic_write(self.advice_path, payload)
        return payload
