#!/usr/bin/env python3
"""DETECT automation (P2): cluster recurring findings into pattern drafts.

Reads the resident loop's ``skills/evolution_log.jsonl`` and the fix catalog,
finds patterns that (a) fire persistently and (b) have never produced a
verified-effective fix, and emits structured draft proposals to
``skills/pattern_drafts/drafts.json`` for an agent to review and turn into
real patterns / coach escalations.

Usage::

    python3 skills/pattern_drafts.py [--window 2000] [--min-presence 0.10]
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
LOG_PATH = SKILL_DIR / "evolution_log.jsonl"
CATALOG_PATH = SKILL_DIR / "fix_catalog.json"
OUT_DIR = SKILL_DIR / "pattern_drafts"

STUBBORN_PRESENCE = 0.10
STUBBORN_MIN_HITS = 20
COMBO_MIN = 15


def _load_log(window: int) -> tuple:
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if window > 0:
        rows = rows[-window:]
    counts = Counter()
    combos = Counter()
    for row in rows:
        ids = sorted({f.get("id") for f in row.get("findings", []) if isinstance(f, dict)})
        for pid in ids:
            counts[pid] += 1
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                combos[(a, b)] += 1
    return len(rows), counts, combos


def _catalog_status() -> dict:
    status = {}
    path = CATALOG_PATH
    if not path.exists():
        return status
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return status
    for f in data.get("fixes", []):
        pid = f.get("pattern_id")
        st = status.setdefault(pid, {"attempted": 0, "effective": 0})
        if not f.get("reverted"):
            st["attempted"] += 1
            if f.get("effective") is True:
                st["effective"] += 1
    return status


def build_drafts(window: int = 2000, min_presence: float = STUBBORN_PRESENCE) -> dict:
    iterations, counts, combos = _load_log(window)
    status = _catalog_status()
    drafts = []
    if iterations:
        for pid, hits in counts.most_common():
            presence = hits / iterations
            if presence < min_presence or hits < STUBBORN_MIN_HITS:
                continue
            st = status.get(pid, {"attempted": 0, "effective": 0})
            if st["effective"] > 0:
                continue
            drafts.append({
                "type": "stubborn_pattern",
                "pattern_id": pid,
                "occurrences": hits,
                "presence": round(presence, 3),
                "fix_attempts": st["attempted"],
                "suggested_action": ("threshold/parameter revisit - pattern fires "
                                     "persistently and no effective fix exists"),
            })
        for (a, b), n in combos.most_common():
            if n < COMBO_MIN:
                continue
            drafts.append({
                "type": "co_occurring_pair",
                "pair": [a, b],
                "co_occurrences": n,
                "suggested_action": ("counter-pattern candidate: the two findings "
                                     "reinforce each other - consider a combined "
                                     "pattern or a coach escalation"),
            })
            if len([d for d in drafts if d["type"] == "co_occurring_pair"]) >= 5:
                break
    return {"generated_at": round(time.time(), 1),
            "window_iterations": iterations, "drafts": drafts}


def main() -> None:
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", type=int, default=2000)
    ap.add_argument("--min-presence", type=float, default=STUBBORN_PRESENCE)
    args = ap.parse_args()
    result = build_drafts(window=args.window, min_presence=args.min_presence)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "drafts.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    n_stubborn = sum(1 for d in result["drafts"] if d["type"] == "stubborn_pattern")
    n_pairs = sum(1 for d in result["drafts"] if d["type"] == "co_occurring_pair")
    print(f"drafts: {len(result['drafts'])} "
          f"(stubborn={n_stubborn}, pairs={n_pairs}) -> {out}")
    for d in result["drafts"]:
        label = d.get("pattern_id") or "+".join(d.get("pair", []))
        print(f"  {d['type']}: {label} ({d.get('occurrences') or d.get('co_occurrences')} hits)")


if __name__ == "__main__":
    main()