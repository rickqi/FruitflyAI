#!/usr/bin/env python3
"""M3.1: MBON primitive-column learning evaluation.

Two modes:
  sample  -- poll /flow.json at an interval, log primitive events (completions,
             aborts, mb_mbon_* levels, dopamine) to CSV for offline analysis.
  analyse -- read a CSV and report per-primitive weight-direction statistics:
             does the corresponding mb_mbon column rise after successes and
             fall after failures (Bennett-style RPE direction check)?

Usage:
  python3 scripts/m3_mbon_eval.py sample --minutes 60 --interval 5 \
      [--out runtime/mbon_eval.csv]
  python3 scripts/m3_mbon_eval.py analyse [--csv runtime/mbon_eval.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.request

FLOW = "http://127.0.0.1:8765/flow.json"
MBONS = ("punch", "dive", "groundpound", "longjump")
DISP_FLOOR = 30.0   # same as reflex_ineffective threshold


def fetch_flow() -> dict:
    try:
        with urllib.request.urlopen(FLOW, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def sample(minutes: float, interval: float, out: str) -> None:
    end = time.time() + minutes * 60
    last_completed = last_aborted = None
    rows = 0
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "decision_source", "cpg_active", "completed", "aborted",
                    "event", "primitive", "disp_60s", "dopamine",
                    *[f"mb_mbon_{m}" for m in MBONS]])
        while time.time() < end:
            f = fetch_flow()
            if f:
                cpg = f.get("cpg_status") or {}
                comp, ab = int(cpg.get("completed", 0) or 0), int(cpg.get("aborted", 0) or 0)
                src = str(f.get("decision_source") or "")
                active = str(cpg.get("active") or "")
                event, prim = "", ""
                if last_completed is not None:
                    if comp > last_completed:
                        event, prim = "complete", str(cpg.get("last") or "")
                    elif ab > last_aborted:
                        event, prim = "abort", str(cpg.get("last") or "")
                last_completed, last_aborted = comp, ab
                w.writerow([round(time.time(), 2), src, active, comp, ab,
                            event, prim,
                            f.get("primitive_disp"), f.get("mb_dopamine"),
                            *[f.get(f"mb_mbon_{m}") for m in MBONS]])
                rows += 1
                if event:
                    fh.flush()
            time.sleep(interval)
    print(f"sampled {rows} rows -> {out}")


def analyse(csv_path: str) -> None:
    with open(csv_path) as fh:
        rows = [r for r in csv.DictReader(fh)]
    events = [r for r in rows if r["event"]]
    print(f"rows={len(rows)} primitive_events={len(events)}")
    if not events:
        print("no primitive events captured yet — sample longer")
        return
    ok = True
    for m in MBONS:
        col = f"mb_mbon_{m}"
        suc = [float(r[col]) for r in events
               if r["event"] == "complete" and r["primitive"] == m
               and _disp(r) >= DISP_FLOOR]
        fail = [float(r[col]) for r in events
                if r["event"] == "abort" and r["primitive"] == m]
        zero = [float(r[col]) for r in events
                if r["event"] == "complete" and r["primitive"] == m
                and _disp(r) < DISP_FLOOR]
        line = f"{m:12s} ok_n={len(suc):3d} mean={_mean(suc):+.3f} | " \
               f"zero_n={len(zero):3d} mean={_mean(zero):+.3f} | " \
               f"abort_n={len(fail):3d} mean={_mean(fail):+.3f}"
        print(line)
        # direction check: success mean should exceed failure mean
        if suc and (fail or zero):
            ref = _mean(fail) if fail else _mean(zero)
            if _mean(suc) <= ref:
                ok = False
    verdict = "PASS: columns rise on success vs failure (RPE direction correct)" if ok \
        else "INCONCLUSIVE/WRONG DIRECTION: inspect dopamine sign path in add_primitive_outcome"
    print(verdict)


def _disp(r) -> float:
    try:
        return float(r["disp_60s"] or 0)
    except (TypeError, ValueError):
        return 0.0


def _mean(xs):
    return statistics.mean(xs) if xs else 0.0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("sample", "analyse"))
    p.add_argument("--minutes", type=float, default=60)
    p.add_argument("--interval", type=float, default=5)
    p.add_argument("--csv", default="runtime/mbon_eval.csv")
    a = p.parse_args()
    if a.mode == "sample":
        sample(a.minutes, a.interval, a.csv)
    else:
        analyse(a.csv)
