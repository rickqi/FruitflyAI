#!/usr/bin/env python3
"""Export Fly64 brain decision traces into a single JSON the replay browser can read.

Sources (all optional, merged when present):
  fly64/runtime/mbon_eval.csv        - tick-level MBON channels + dopamine + decisions
  fly64/skills/coach_outcomes.jsonl  - coach anomaly events (fallen / unsolvable_stuck ...)

Usage:
  python export_trace.py [--out web/trace.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # D:\codes\flygym
MBON_CSV = ROOT / "fly64" / "runtime" / "mbon_eval.csv"
COACH_JSONL = ROOT / "fly64" / "skills" / "coach_outcomes.jsonl"

MBON_KEYS = ["mb_mbon_punch", "mb_mbon_dive", "mb_mbon_groundpound", "mb_mbon_longjump"]


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_mbon_ticks():
    ticks = []
    if not MBON_CSV.exists():
        return ticks
    with MBON_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ts = f(row.get("ts"))
            if ts is None:
                continue
            ticks.append(
                {
                    "t": ts,
                    "decision_source": row.get("decision_source") or "",
                    "primitive": row.get("primitive") or "",
                    "event": row.get("event") or "",
                    "cpg_active": f(row.get("cpg_active")),
                    "completed": int(f(row.get("completed")) or 0),
                    "aborted": int(f(row.get("aborted")) or 0),
                    "disp_60s": f(row.get("disp_60s")),
                    "dopamine": f(row.get("dopamine")),
                    "mbon": {k: f(row.get(k)) for k in MBON_KEYS},
                }
            )
    ticks.sort(key=lambda x: x["t"])
    return ticks


def load_coach_events(t0: float | None):
    events = []
    if not COACH_JSONL.exists():
        return events
    with COACH_JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = f(rec.get("resolved_at"))
            if t is None:
                continue
            events.append(
                {
                    "t": t,
                    "kind": "coach",
                    "anomaly": rec.get("anomaly") or "",
                    "verdict": rec.get("verdict") or "",
                    "help_reason": rec.get("help_reason") or "",
                    "age_s": f(rec.get("age_s")),
                }
            )
    events.sort(key=lambda x: x["t"])
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent / "web" / "trace.json"))
    args = ap.parse_args()

    ticks = load_mbon_ticks()
    t0 = ticks[0]["t"] if ticks else None
    coach = load_coach_events(t0)

    trace = {
        "schema": "fly64-brain-replay/1",
        "mbon_channels": MBON_KEYS,
        "tick_count": len(ticks),
        "event_count": len(coach),
        "t0": t0,
        "ticks": ticks,
        "events": coach,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
    print(f"exported {len(ticks)} ticks + {len(coach)} events -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
