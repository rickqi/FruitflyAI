#!/usr/bin/env python3
"""Measure the health of the two self-evolution loops that this session repaired.

Two independent questions, both answered from existing runtime data:

  --phase6   Did the BrainMutator's trials attribute fitness to dimensions that
             could actually change behaviour?  Until EVO-066 the mutator searched
             all 21 schema params, but only 7 have a consumer — so a committed
             candidate could have moved nothing that affects the fly.

  --p44      How far is scene->strategy instinct consolidation (P4.4) from its
             first promotion, and why?  The gate refuses below >=2 clean
             improvements in one (scene, salient-signature) bucket.

Usage:
    python3 scripts/measure_evolution_health.py [--phase6] [--p44] [--json]

Both sections are read-only.  Re-run them after changes; the numbers are the
evidence, not the prose.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVO_LOG = ROOT / "skills" / "evolution_log.jsonl"
SCHEMA = ROOT / "skills" / "brain_tunable_params.json"
BINDINGS = ROOT / "skills" / "scene_strategy_bindings.json"
OUTCOMES = ROOT / "skills" / "coach_outcomes.jsonl"


def load_schema():
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    params = d.get("params") or {}
    return {pid: m for pid, m in params.items() if isinstance(m, dict)}


def load_unique_evolutions():
    """Unique BrainMutator results.

    The log appends the LAST evolution result to every iteration line, so the
    same trial appears in hundreds of consecutive records; dedupe on the content
    that identifies a trial's outcome.
    """
    if not EVO_LOG.exists():
        return []
    seen = set()
    out = []
    with EVO_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            ev = rec.get("evolution")
            if not isinstance(ev, dict) or not ev.get("params"):
                continue
            params = ev["params"]
            key = (ev.get("passed"), ev.get("delta"), ev.get("baseline"),
                   ev.get("current"),
                   tuple(sorted((k, round(float(v), 6)) for k, v in params.items()
                                if isinstance(v, (int, float)))))
            if key in seen:
                continue
            seen.add(key)
            ev = dict(ev)
            ev["_iteration"] = rec.get("iteration")
            ev["_timestamp"] = rec.get("timestamp")
            out.append(ev)
    return out


def measure_phase6(schema, out):
    wired = {p for p, m in schema.items() if m.get("wired")}
    inert = {p for p, m in schema.items() if not m.get("wired")}

    def moved(pid, val):
        meta = schema.get(pid) or {}
        default = meta.get("default", 0.0)
        mn, mx = meta.get("min", 0.0), meta.get("max", 1.0)
        rng = (mx - mn) or 1.0
        try:
            return abs(float(val) - float(default)) / rng > 0.01
        except (TypeError, ValueError):
            return False

    trials = load_unique_evolutions()
    out["trials_unique"] = len(trials)
    if not trials:
        out["note"] = "no BrainMutator trial records found"
        return

    out["params_total"] = len(schema)
    out["params_wired"] = len(wired)
    out["params_inert"] = len(inert)
    out["inert_fraction"] = round(len(inert) / max(1, len(schema)), 4)

    commits = [t for t in trials if t.get("passed")]
    out["commits"] = len(commits)
    out["rollbacks"] = len(trials) - len(commits)
    out["commit_rate"] = round(len(commits) / len(trials), 4)

    deltas = [float(t.get("delta") or 0.0) for t in trials]
    deltas_sorted = sorted(deltas)
    out["delta"] = {
        "min": round(deltas_sorted[0], 4),
        "p50": round(deltas_sorted[len(deltas_sorted) // 2], 4),
        "max": round(deltas_sorted[-1], 4),
        "mean": round(sum(deltas) / len(deltas), 4),
    }
    # A delta of EXACTLY 0.0 means baseline and current fitness were identical —
    # i.e. the trial measured nothing.  Since `fitness()` is computed from live
    # telemetry (coverage / stuck / novelty / health), an exact tie over a 120 s
    # window is suspicious and would make the pass/fail decision a coin flip on
    # a motionless metric.
    exact_zero = sum(1 for d in deltas if d == 0.0)
    out["delta_exactly_zero"] = exact_zero
    out["delta_exactly_zero_fraction"] = round(exact_zero / max(1, len(deltas)), 4)
    out["delta_abs_lt_threshold"] = sum(1 for d in deltas if abs(d) <= 0.03)
    out["delta_abs_lt_threshold_fraction"] = round(
        out["delta_abs_lt_threshold"] / max(1, len(deltas)), 4)

    # The decisive metric: a COMMITTED trial whose live dimensions never moved
    # cannot have improved anything — the fitness delta was noise.
    commit_wired_moved = Counter()
    commit_inert_moved = Counter()
    noise_commits = []
    for t in commits:
        params = t.get("params") or {}
        w = sum(1 for p in wired if moved(p, params.get(p)))
        i = sum(1 for p in inert if moved(p, params.get(p)))
        commit_wired_moved[w] += 1
        commit_inert_moved[i] += 1
        if w == 0:
            noise_commits.append({"iteration": t.get("_iteration"),
                                  "delta": t.get("delta"),
                                  "inert_moved": i})
    out["commits_by_wired_dims_moved"] = dict(sorted(commit_wired_moved.items()))
    out["commits_by_inert_dims_moved"] = dict(sorted(commit_inert_moved.items()))
    out["noise_commits"] = len(noise_commits)
    out["noise_commit_fraction"] = round(len(noise_commits) / max(1, len(commits)), 4)
    out["noise_commit_examples"] = noise_commits[:5]

    # Movement volume: how much of a candidate is inert by construction
    tot_w = tot_i = 0
    for t in trials:
        params = t.get("params") or {}
        tot_w += sum(1 for p in wired if moved(p, params.get(p)))
        tot_i += sum(1 for p in inert if moved(p, params.get(p)))
    out["moved_dimensions_total"] = {"wired": tot_w, "inert": tot_i,
                                     "inert_share": round(tot_i / max(1, tot_w + tot_i), 4)}


def measure_p44(out):
    if not BINDINGS.exists():
        out["note"] = "no binding store yet"
        return
    store = json.loads(BINDINGS.read_text(encoding="utf-8"))
    rows = []
    for scene, entry in store.items():
        if not isinstance(entry, dict):
            continue
        for sig, b in (entry.get("buckets") or {}).items():
            if not isinstance(b, dict):
                continue
            rows.append({
                "scene": scene,
                "signature": sig,
                "improved": int(b.get("improved", 0) or 0),
                "unchanged": int(b.get("unchanged", 0) or 0),
                "worse": int(b.get("worse", 0) or 0),
                "total_improved": int(b.get("total_improved", 0) or 0),
                "promoted": bool(b.get("promoted")),
                "needed": max(0, 2 - int(b.get("improved", 0) or 0)),
            })
    rows.sort(key=lambda r: (-r["improved"], r["scene"]))
    out["scenes"] = len({r["scene"] for r in rows})
    out["signatures"] = len(rows)
    out["promoted"] = sum(1 for r in rows if r["promoted"])
    out["by_improved"] = dict(sorted(Counter(r["improved"] for r in rows).items()))
    out["rows"] = rows
    out["best"] = rows[0] if rows else None

    # Why no promotion?  Split outcomes into "created a NEW signature" vs
    # "added evidence to an existing one".  If nearly every outcome is new, the
    # coach is exploring fresh parameter sets and no bucket can reach 2.
    if OUTCOMES.exists():
        seen = set()
        new_sig = repeated = 0
        per_scene = defaultdict(set)
        verdicts = Counter()
        skipped_no_scene = skipped_no_keys = 0
        total = 0
        for line in OUTCOMES.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            total += 1
            verdicts[r.get("verdict", "?")] += 1
            label = str(r.get("scene_label") or "").split("#")[0].strip()
            keys = r.get("keys") or {}
            if not label:
                skipped_no_scene += 1
                continue
            if not isinstance(keys, dict) or not keys:
                skipped_no_keys += 1
                continue
            sig = (label,
                   (keys.get("fallen_recovery") or {}).get("mode"),
                   (keys.get("exploration") or {}).get("turn_bias"),
                   (keys.get("escape") or {}).get("stuck_threshold_s"))
            per_scene[label].add(sig)
            if sig in seen:
                repeated += 1
            else:
                seen.add(sig)
                new_sig += 1
        out["outcomes_total_lines"] = total
        out["outcomes"] = sum(verdicts.values())
        out["outcome_verdicts"] = dict(verdicts)
        out["usable_for_signature"] = new_sig + repeated
        out["skipped_no_scene_label"] = skipped_no_scene
        out["skipped_no_keys"] = skipped_no_keys
        out["distinct_signatures_from_outcomes"] = new_sig
        out["outcomes_reusing_an_existing_signature"] = repeated
        out["signature_reuse_rate"] = round(repeated / max(1, new_sig + repeated), 4)
        out["signatures_per_scene"] = {k: len(v) for k, v in
                                       sorted(per_scene.items(), key=lambda kv: -len(kv[1]))}
        # How large is the signature space the quantisation defines?  If the
        # coach samples within it, collisions should eventually occur; a reuse
        # rate of 0 over a small sample is weak evidence, not proof.
        out["signature_space_note"] = (
            "salient signature = mode (2 values) x turn_bias quantised 0.1 x "
            "stuck_threshold_s bucketed 5.0; collisions become likely only well "
            "above a few dozen usable outcomes")


def append_trend_snapshot(report) -> Path:
    """Append one timestamped row so the loops become a TIME SERIES.

    Recommendation #1 from the EVO-067 round was "observe whether `promoted`
    keeps growing and whether signature_reuse_rate rises".  A single reading
    cannot answer that, and eyeballing telemetry is not evidence.  This appends a
    compact row per invocation to skills/evolution_health_trend.jsonl, so the
    trend is a file that can be diffed, plotted and cited.
    """
    path = ROOT / "skills" / "evolution_health_trend.jsonl"
    p44 = report.get("p44", {})
    ph6 = report.get("phase6", {})
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "scenes": p44.get("scenes"),
        "signatures": p44.get("signatures"),
        "promoted": p44.get("promoted"),
        "qualifying": p44.get("qualifying"),
        "by_improved": p44.get("by_improved"),
        "usable_outcomes": p44.get("usable_for_signature"),
        "signature_reuse_rate": p44.get("signature_reuse_rate"),
        "outcomes_total": p44.get("outcomes_total_lines"),
        "phase6_trials": ph6.get("trials_unique"),
        "phase6_commits": ph6.get("commits"),
        "phase6_delta_exact_zero": ph6.get("delta_exactly_zero"),
        "phase6_instrumented": report.get("phase6_instrumented_trials"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def show_trend():
    path = ROOT / "skills" / "evolution_health_trend.jsonl"
    if not path.exists():
        print("no trend yet — run with --snapshot")
        return
    rows = []
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    print("=" * 78)
    print("SELF-EVOLUTION TREND (%d snapshots)" % len(rows))
    print("=" * 78)
    print("  %-20s %-6s %-6s %-8s %-8s %-7s %s"
          % ("when", "scenes", "sigs", "promoted", "usable", "reuse", "phase6 trials/commits"))
    for r in rows[-20:]:
        print("  %-20s %-6s %-6s %-8s %-8s %-7s %s/%s"
              % (str(r.get("ts"))[:19], r.get("scenes"), r.get("signatures"),
                 r.get("promoted"), r.get("usable_outcomes"),
                 r.get("signature_reuse_rate"), r.get("phase6_trials"),
                 r.get("phase6_commits")))
    if len(rows) >= 2:
        a, b = rows[0], rows[-1]
        print()
        print("  change over the series:")
        for k in ("promoted", "signatures", "scenes", "usable_outcomes",
                  "signature_reuse_rate", "phase6_trials", "phase6_commits"):
            va, vb = a.get(k), b.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                print("    %-22s %s -> %s  (%+g)" % (k, va, vb, vb - va))


def count_instrumented_trials() -> int:
    """UNIQUE trials recorded with the EVO-067 component diagnostics.

    Must dedupe exactly like `load_unique_evolutions`: the resident loop appends
    the LAST evolution result to every iteration line, so a single instrumented
    trial appears in hundreds of consecutive records (raw counting reported 2709
    for what is really a handful of trials — a false "ready to decide").
    """
    if not EVO_LOG.exists():
        return 0
    seen = set()
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
            if not isinstance(ev, dict) or not ev.get("params"):
                continue
            key = (ev.get("passed"), ev.get("delta"), ev.get("baseline"),
                   ev.get("current"),
                   tuple(sorted((k, round(float(v), 6))
                                for k, v in ev["params"].items()
                                if isinstance(v, (int, float)))))
            seen.add(key)
    return len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase6", action="store_true")
    ap.add_argument("--p44", action="store_true")
    ap.add_argument("--snapshot", action="store_true",
                    help="append a trend row (implies both sections)")
    ap.add_argument("--trend", action="store_true",
                    help="print the accumulated trend and exit")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.trend:
        show_trend()
        return 0
    if not (args.phase6 or args.p44 or args.snapshot):
        args.phase6 = args.p44 = True
    if args.snapshot:
        args.phase6 = args.p44 = True

    schema = load_schema()
    report = {"generated_at": datetime.now(timezone.utc).isoformat()}
    if args.phase6:
        report["phase6"] = {}
        measure_phase6(schema, report["phase6"])
        report["phase6_instrumented_trials"] = count_instrumented_trials()
    if args.p44:
        report["p44"] = {}
        measure_p44(report["p44"])

    if args.snapshot:
        p = append_trend_snapshot(report)
        print("trend row appended -> %s" % p)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    if "phase6" in report:
        p = report["phase6"]
        print("=" * 78)
        print("PHASE 6 (BrainMutator) ATTRIBUTION")
        print("=" * 78)
        if p.get("note"):
            print("  %s" % p["note"])
        else:
            print("  schema params      : %d total | %d wired | %d inert (%.1f%% inert)"
                  % (p["params_total"], p["params_wired"], p["params_inert"],
                     p["inert_fraction"] * 100))
            print("  unique trials      : %d" % p["trials_unique"])
            print("  commits / rollbacks: %d / %d  (commit rate %.2f%%)"
                  % (p["commits"], p["rollbacks"], p["commit_rate"] * 100))
            print("  fitness delta      : min=%s p50=%s max=%s mean=%s"
                  % (p["delta"]["min"], p["delta"]["p50"], p["delta"]["max"],
                     p["delta"]["mean"]))
            print("  delta EXACTLY 0.0  : %d / %d (%.1f%%)  <- trial measured"
                  " nothing"
                  % (p["delta_exactly_zero"], p["trials_unique"],
                     p["delta_exactly_zero_fraction"] * 100))
            print("  |delta| <= 0.03    : %d / %d (%.1f%%)  <- below the pass"
                  " threshold"
                  % (p["delta_abs_lt_threshold"], p["trials_unique"],
                     p["delta_abs_lt_threshold_fraction"] * 100))
            print("  moved dims (total) : wired=%d inert=%d  (inert share %.1f%%)"
                  % (p["moved_dimensions_total"]["wired"],
                     p["moved_dimensions_total"]["inert"],
                     p["moved_dimensions_total"]["inert_share"] * 100))
            print("  commits by # wired dims moved : %s"
                  % p["commits_by_wired_dims_moved"])
            print("  commits by # INERT dims moved : %s"
                  % p["commits_by_inert_dims_moved"])
            print("  >>> commits with ZERO live-dim movement: %d / %d (%.1f%%)"
                  % (p["noise_commits"], p["commits"],
                     p["noise_commit_fraction"] * 100))
            for e in p["noise_commit_examples"]:
                print("        iter=%-6s delta=%-8s inert_moved=%s"
                      % (e["iteration"], e["delta"], e["inert_moved"]))
            print("  MEASURED 2026-09-17 on the pre-EVO-066 corpus: 0 of 2 commits")
            print("  moved only inert dims, so that hypothesis was REFUTED — the")
            print("  inert dimensions diluted interpretability and wrote 14 useless")
            print("  keys per trial, but produced no demonstrably false commit.")
            print("  The dominant problem is the fitness signal itself: a delta of")
            print("  exactly 0.0 means the trial measured nothing, and most trials")
            print("  stay below the pass gate.  Both are printed above.")

    if "p44" in report:
        q = report["p44"]
        print()
        print("=" * 78)
        print("P4.4 INSTINCT CONSOLIDATION")
        print("=" * 78)
        if q.get("note"):
            print("  %s" % q["note"])
        else:
            print("  scenes / signatures : %d / %d" % (q["scenes"], q["signatures"]))
            print("  promoted            : %d" % q["promoted"])
            print("  signatures by improved count : %s" % q["by_improved"])
            for r in q["rows"][:8]:
                print("    %-12s imp=%s unch=%s worse=%s needed=%s | %s"
                      % (r["scene"], r["improved"], r["unchanged"], r["worse"],
                         r["needed"], r["signature"][:58]))
            if "outcomes" in q:
                print("  outcome lines      : %d  %s"
                      % (q["outcomes_total_lines"], q["outcome_verdicts"]))
                print("  usable for a signature : %d  (skipped: %d without scene"
                      " label, %d without keys)"
                      % (q["usable_for_signature"], q["skipped_no_scene_label"],
                         q["skipped_no_keys"]))
                print("  distinct signatures : %d | outcomes reusing one: %d"
                      % (q["distinct_signatures_from_outcomes"],
                         q["outcomes_reusing_an_existing_signature"]))
                print("  signature REUSE rate: %.1f%%"
                      % (q["signature_reuse_rate"] * 100))
                print("  (signature space: %s)" % q.get("signature_space_note", ""))
                print("  signatures per scene: %s" % q["signatures_per_scene"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
