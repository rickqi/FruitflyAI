#!/usr/bin/env python3
"""Verification-baseline regression detector.

WHY
---
The Windows suite carries ~40 failures that predate this work.  Because nothing
distinguished them, every round needed a manual (once, subagent-assisted)
baseline attribution to answer the only question that matters: "did I break
anything?"  A suite whose failures are all equally loud hides real regressions.

This tool turns that noise into a signal:

    tests/known_failures.json   the tracked baseline, each entry with a CAUSE
    scripts/check_regressions.py  compare a fresh run against it

Exit status is non-zero only when a NEW failure appears, so it is safe to use as
a gate.  `--strict` also fails when a baseline entry starts passing, so the
baseline cannot rot silently.

Usage:
    python3 scripts/check_regressions.py                 # run pytest itself
    python3 scripts/check_regressions.py --report r.txt   # parse an existing run
    python3 scripts/check_regressions.py --strict
    python3 scripts/check_regressions.py --update         # rewrite the baseline
    python3 scripts/check_regressions.py --only tests/test_x.py

`--only TARGET` (repeatable) restricts the pytest run to those paths/node ids.
It exists for ONE caller: ``tests/test_regression_detector.py``, which must
prove this detector end-to-end (spawn it -> it runs pytest -> it counts the
injected failure as NEW -> it exits non-zero) WITHOUT re-running the whole suite
inside the suite; that nesting made a single test cost as much as the entire
gate.  The gate itself never passes ``--only``, so its coverage is unchanged.
``--update`` is refused together with ``--only``: rewriting the tracked baseline
from a restricted run would silently drop every entry outside the restriction.

Before the pytest run, stale ``tests/test_zz_regression_detector_probe*.py``
scratch files (left by an interrupted run of the detector's own self-test) are
deleted with a warning.  Without that sweep such a leftover is collected by the
suite and counted as a NEW failure — see ``sweep_stale_probes``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILED_RE = re.compile(r"^FAILED\s+(\S+)", re.M)


def baseline_path(platform: str | None = None) -> Path:
    """Platform-scoped baseline: the two suites have genuinely different
    failure sets (e.g. the clock_gettime_ns tests pass on Linux and fail on
    Windows Python 3.11), so a single shared file would be wrong on one side.

    `tests/known_failures.<platform>.json` is preferred; the legacy unqualified
    `tests/known_failures.json` is still honoured for backwards compatibility.
    """
    plat = platform or sys.platform
    scoped = ROOT / "tests" / ("known_failures.%s.json" % plat)
    if scoped.exists():
        return scoped
    legacy = ROOT / "tests" / "known_failures.json"
    return scoped if not legacy.exists() else legacy

CAUSES = {
    "environment": "platform/dependency gap, not a code defect",
    "aspirational": "test asserts a feature that is not implemented anywhere",
    "test-drift": "the feature exists but the assertion is stale after a refactor",
    "live-state": "asserts on the running brain's telemetry, so it depends on the "
                  "external system's current state rather than on the code",
    "real-bug": "code and expectation genuinely disagree; needs a decision",
    "unknown": "not yet classified",
}


def id_of(nodeid: str) -> str:
    return nodeid.split(" ")[0].strip()


#: Scratch file the detector's own self-test used to create at a FIXED path
#: (see ``tests/test_regression_detector.py``).  One interrupted run left one
#: behind, every later suite run collected it, and its injected failure is not in
#: the baseline — so the gate reported ``NEW = 1`` forever: a leftover wearing
#: the costume of a regression, which is exactly what this baseline exists to
#: make impossible.  Swept before pytest starts, with a warning, so the poison
#: can never reach the baseline comparison.
STALE_PROBE_GLOB = "test_zz_regression_detector_probe*.py"


def sweep_stale_probes() -> list[str]:
    """Delete stale self-test probes; warn instead of failing. Best effort."""
    removed = []
    for path in sorted((ROOT / "tests").glob(STALE_PROBE_GLOB)):
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            pass
    if removed:
        print("swept stale probe file(s) left by an interrupted self-test run: %s"
              % ", ".join(removed), file=sys.stderr)
    return removed


def run_pytest(only: list[str] | None = None) -> tuple[list[str], str]:
    """Run the suite (or only the given targets) and return its FAILED ids.

    ``only`` is a restriction used by the detector's own self-test; the gate
    calls this with no arguments and therefore still runs everything.
    """
    tmp = ROOT / ".pytest-run"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["TMP"] = str(tmp)
    env["TEMP"] = str(tmp)
    cmd = [sys.executable, "-m", "pytest", "-q", "-rf", "--basetemp", str(tmp),
           "-p", "no:cacheprovider"]
    cmd.extend(only or [])
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    return sorted({id_of(m.group(1)) for m in FAILED_RE.finditer(out)}), out


def parse_report(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return sorted({id_of(m.group(1)) for m in FAILED_RE.finditer(text)})


def load_baseline(platform: str | None = None) -> dict:
    p = baseline_path(platform)
    if not p.exists():
        return {"entries": []}
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--platform", default=sys.platform)
    ap.add_argument("--only", action="append", default=[], metavar="TARGET",
                    help="restrict the pytest run to these targets (repeatable); "
                         "for the detector's self-test only — the gate runs the "
                         "whole suite")
    args = ap.parse_args()

    if args.only and args.update:
        print("refusing --update together with --only: rewriting the baseline "
              "from a restricted run would drop every entry outside it",
              file=sys.stderr)
        return 2

    if args.report:
        current = parse_report(Path(args.report))
        tail = ""
    else:
        print("running pytest ...", flush=True)
        sweep_stale_probes()
        current, tail = run_pytest(args.only)

    base = load_baseline(args.platform)
    known = {e["id"] for e in base.get("entries", [])}

    new = [t for t in current if t not in known]
    fixed = sorted(known - set(current))
    still = sorted(set(current) & known)

    target = baseline_path(args.platform)
    if args.update:
        entries = []
        old = {e["id"]: e for e in base.get("entries", [])}
        for t in current:
            prev = old.get(t) or {}
            entries.append({"id": t,
                            "cause": prev.get("cause", "unknown"),
                            "note": prev.get("note", "")})
        target.write_text(json.dumps({
            "platform": args.platform,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "count": len(entries),
            "entries": entries,
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("baseline updated: %d entries -> %s" % (len(entries), target))
        return 0

    by_cause: dict[str, int] = {}
    for e in base.get("entries", []):
        if e["id"] in current:
            by_cause[e.get("cause", "unknown")] = by_cause.get(e.get("cause", "unknown"), 0) + 1

    print("=" * 78)
    print("REGRESSION CHECK  (baseline %s, %d entries)"
          % (base.get("platform", "?"), len(known)))
    print("=" * 78)
    print("  failing now      : %d" % len(current))
    print("  still failing    : %d (known)" % len(still))
    print("  NEW failures     : %d" % len(new))
    print("  baseline entries that now PASS : %d" % len(fixed))
    if by_cause:
        print("  known failures by cause: %s"
              % ", ".join("%s=%d" % kv for kv in sorted(by_cause.items())))
    if args.only:
        print("  NOTE: restricted run (--only) — 'baseline entries that now PASS' "
              "here only means 'not part of this restricted run'.")

    if new:
        print("\n  !!! NEW FAILURES (a regression, or an unclassified pre-existing one):")
        for t in new:
            print("      %s" % t)
    if fixed:
        print("\n  baseline entries that now pass (refresh with --update):")
        for t in fixed:
            print("      %s" % t)
    if tail:
        summary = [l for l in tail.splitlines() if "passed" in l or "failed" in l]
        if summary:
            print("\n  pytest: %s" % summary[-1])

    rc = 1 if new else 0
    if args.strict and fixed:
        rc = 1
    if not new and not fixed:
        print("\n  OK: no regressions, baseline is current")
    return rc


if __name__ == "__main__":
    sys.exit(main())
