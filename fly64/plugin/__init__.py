#!/usr/bin/env python3
"""Fly64 MHR — DSH dynamic plugin package.

Integrates the EvolutionSkill closed loop with CoachConsult LLM escalation:

  * ``runner.PluginRunner``    — 10s periodic skill cycle
    (poll evolution/memory -> check_help_needed -> frame capture ->
     llm_consult -> strategy write).
  * ``llm_consult.GLMConsultant`` — GLM-5.3-flash multimodal consultation
    (DSH subagent transport or OpenAI-compatible HTTP transport).
  * ``strategy_writer.StrategyWriter`` — atomic writes of
    ``skills/active_strategy.json`` (brain hot-reloads every 600 ticks)
    and ``skills/coach_advice.json`` (dashboard display).

Plugin metadata lives in ``manifest.json`` next to this file.
"""

from __future__ import annotations

import json
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_NAME = "fly64-mhr"
PLUGIN_VERSION = "1.0.0"
CYCLE_INTERVAL_SECONDS = 10

__all__ = [
    "PLUGIN_DIR",
    "PLUGIN_NAME",
    "PLUGIN_VERSION",
    "CYCLE_INTERVAL_SECONDS",
    "load_manifest",
]


def load_manifest(path: Path | None = None) -> dict:
    """Load and minimally validate the plugin manifest."""
    p = path or (PLUGIN_DIR / "manifest.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("name") != PLUGIN_NAME:
        raise ValueError(f"manifest name mismatch: {data.get('name')!r}")
    if data.get("entry") != "plugin.runner:PluginRunner":
        raise ValueError(f"manifest entry mismatch: {data.get('entry')!r}")
    interval = data.get("runtime", {}).get("interval_seconds")
    if interval != CYCLE_INTERVAL_SECONDS:
        raise ValueError("manifest runtime.interval_seconds must be 10")
    return data
