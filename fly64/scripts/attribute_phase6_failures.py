#!/usr/bin/env python3
"""Attribute Phase 6's failures using the EVO-067 component instrumentation.

The scalar log could only say "62.5% of trials had delta exactly 0.0".  With
`baseline_components` / `current_components` / `same_sample` recorded, the cause
is now decidable from data instead of inferred:

  A. same_sample=True            -> the collector handed back the SAME sample at
                                    both ends; the metric never refreshed
  B. components identical, ts differs
                                 -> the fitness inputs genuinely did not move over
                                    the (>=120 s) window
  C. some component differs but the weighted total cancels
                                 -> threshold/signal design problem
  D. components differ and so does delta
                                 -> a working trial (the interesting ones)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts.measure_evolution_health import EVO_LOG  # noqa: E402

TERMS = ("coverage", "unstuck", "novelty", "health", "speed", "first_contact",
         "revisit_penalty")


def load():
    seen, out = set(), []
    with EVO_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or "baseline_components" not in line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            ev = rec.get("evolution")
            if not isinstance(ev, dict) or not isinstance(
                    ev.get("baseline_components"), dict):
                continue
            key = (ev.get("passed"), ev.get("delta"), ev.get("baseline"),
                   ev.get("current"),
                   tuple(sorted((k, round(float(v), 6))
                                for k, v in (ev.get("params") or {}).items()
                                if isinstance(v, (int, float)))))
            if key in seen:
                continue
            seen.add(key)
            out.append(ev)
    return out


def main():
    trials = load()
    print("=" * 78)
    print("PHASE 6 FAILURE ATTRIBUTION (instrumented trials: %d)" % len(trials))
    print("=" * 78)
    if not trials:
        print("  no instrumented trials yet")
        return 0

    zero = [t for t in trials if float(t.get("delta") or 0) == 0.0]
    nonzero = [t for t in trials if float(t.get("delta") or 0) != 0.0]
    print("  delta == 0.0        : %d / %d (%.1f%%)"
          % (len(zero), len(trials), len(zero) / len(trials) * 100))
    print("  delta != 0.0        : %d" % len(nonzero))
    print("  passed              : %d" % sum(1 for t in trials if t.get("passed")))
    print()

    cause = Counter()
    for t in trials:
        base = t.get("baseline_components") or {}
        cur = t.get("current_components") or {}
        same = bool(t.get("same_sample"))
        bs, cs = base.get("raw", {}), cur.get("raw", {})
        terms_same = all(abs(float(base.get(k) or 0) - float(cur.get(k) or 0)) < 1e-9
                         for k in TERMS)
        if float(t.get("delta") or 0) != 0.0:
            cause["D: delta moved (working trial)"] += 1
        elif same:
            cause["A: same_sample=True (metric never refreshed)"] += 1
        elif bs.get("sample_ts") == cs.get("sample_ts"):
            cause["A2: identical sample_ts"] += 1
        elif terms_same:
            cause["B: inputs did not move over the window"] += 1
        else:
            cause["C: terms moved but the weighted total cancelled"] += 1
    print("  attribution:")
    for k, v in cause.most_common():
        print("    %-46s %d" % (k, v))
    print()

    # Which raw inputs actually vary between the two readings?
    varies = Counter()
    identical = Counter()
    for t in trials:
        bs = (t.get("baseline_components") or {}).get("raw", {})
        cs = (t.get("current_components") or {}).get("raw", {})
        for k in ("coverage_pct", "stuck_duration", "novelty", "health_score",
                  "coverage_rate", "first_contact_rate", "revisit_ratio"):
            a, b = bs.get(k), cs.get(k)
            if a is None and b is None:
                identical[k] += 1
            elif a == b:
                identical[k] += 1
            else:
                varies[k] += 1
    print("  per-input movement across the window:")
    for k in sorted(set(varies) | set(identical)):
        print("    %-22s varies=%-4d identical=%-4d" % (k, varies[k], identical[k]))
    print()

    print("  sample_ts present in raw: %d / %d"
          % (sum(1 for t in trials
                 if (t.get("baseline_components") or {}).get("raw", {}).get("sample_ts")
                 is not None), len(trials)))
    ex = [t for t in trials if float(t.get("delta") or 0) == 0.0][:2]
    for t in ex:
        b = (t.get("baseline_components") or {}).get("raw", {})
        c = (t.get("current_components") or {}).get("raw", {})
        print("  example zero-delta trial: delta=%s same_sample=%s"
              % (t.get("delta"), t.get("same_sample")))
        print("    baseline raw: %s" % json.dumps(
            {k: b.get(k) for k in ("coverage_pct", "stuck_duration", "health_score",
                                   "sample_ts")}, ensure_ascii=False))
        print("    current  raw: %s" % json.dumps(
            {k: c.get(k) for k in ("coverage_pct", "stuck_duration", "health_score",
                                   "sample_ts")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
