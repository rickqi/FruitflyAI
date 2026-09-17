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
BASELINE = ROOT / "tests" / "known_failures.json"
FAILED_RE = re.compile(r"^FAILED\s+(\S+)", re.M)

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


def run_pytest() -> tuple[list[str], str]:
    tmp = ROOT / ".pytest-run"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["TMP"] = str(tmp)
    env["TEMP"] = str(tmp)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rf", "--basetemp", str(tmp),
         "-p", "no:cacheprovider"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    return sorted({id_of(m.group(1)) for m in FAILED_RE.finditer(out)}), out


def parse_report(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return sorted({id_of(m.group(1)) for m in FAILED_RE.finditer(text)})


def load_baseline() -> dict:
    if not BASELINE.exists():
        return {"entries": []}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--platform", default=sys.platform)
    args = ap.parse_args()

    if args.report:
        current = parse_report(Path(args.report))
        tail = ""
    else:
        print("running pytest ...", flush=True)
        current, tail = run_pytest()

    base = load_baseline()
    known = {e["id"] for e in base.get("entries", [])}

    new = [t for t in current if t not in known]
    fixed = sorted(known - set(current))
    still = sorted(set(current) & known)

    if args.update:
        entries = []
        old = {e["id"]: e for e in base.get("entries", [])}
        for t in current:
            prev = old.get(t) or {}
            entries.append({"id": t,
                            "cause": prev.get("cause", "unknown"),
                            "note": prev.get("note", "")})
        BASELINE.write_text(json.dumps({
            "platform": args.platform,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "count": len(entries),
            "entries": entries,
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("baseline updated: %d entries -> %s" % (len(entries), BASELINE))
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
