#!/usr/bin/env python3
"""Generate the "declared but not implemented" register.

WHY
---
Two independent audits found the same pattern: things are DECLARED that are not
IMPLEMENTED, and nothing tracks them.

  * 15 `aspirational` tests (from tests/known_failures.<platform>.json) assert
    features that exist nowhere in the source — e.g. ENHANCED_PROMPT_TEMPLATE and
    the whole enhanced-prompt protocol, or MushroomBody._saturation_recovery_counter.
  * 14 unwired tunable parameters (from skills/brain_tunable_params.json) are
    advertised to the operator panel and were, until EVO-066, mutated by Phase 6,
    while no component reads them.
  * 1 architectural aspiration: `test_no_visual_motor_shortcut` demands that
    vision cannot reach the motor pools except through the connectome, while
    fly64/model.py injects current into motor pools from 66 sites (79% of them
    conditionally guarded, 7 gated on a visual feature).

Each was found separately and would be re-discovered separately. This tool emits
ONE register so each entry can be decided once — implement it or formally retire
it — instead of being rediscovered and re-argued.

The register is generated, never hand-maintained: re-run this script after any
audit. Read-only w.r.t. everything except the generated document.

Usage:
    python3 scripts/build_unimplemented_register.py [--out docs/...]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT if (ROOT / "fly64").exists() else ROOT
BASELINE_DIR = PROJ / "tests"
SCHEMA = PROJ / "skills" / "brain_tunable_params.json"
DEFAULT_OUT = PROJ / "docs" / "declared-not-implemented.md"


def load_baseline():
    for name in ("known_failures.%s.json" % sys.platform, "known_failures.json"):
        p = BASELINE_DIR / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), p.name
    return {"entries": []}, "(none)"


def aspirational_entries():
    data, name = load_baseline()
    out = defaultdict(list)
    for e in data.get("entries", []):
        if e.get("cause") == "aspirational":
            out[e["id"].split("::")[0]].append(e)
    return out, name


def unwired_params():
    if not SCHEMA.exists():
        return []
    d = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return [(pid, m) for pid, m in (d.get("params") or {}).items()
            if isinstance(m, dict) and m.get("wired") is False]


def injection_summary():
    script = PROJ / "scripts" / "audit_motor_injections.py"
    if not script.exists():
        return None
    try:
        r = subprocess.run([sys.executable, str(script), "--json"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    asp, baseline_name = aspirational_entries()
    unwired = unwired_params()
    inj = injection_summary()

    n_asp = sum(len(v) for v in asp.values())
    lines = []
    A = lines.append
    A("# Declared but not implemented — decision register")
    A("")
    A("> **Generated** by `scripts/build_unimplemented_register.py` from the audit")
    A("> tools.  Do not hand-edit: re-run the script after changing a baseline, the")
    A("> tunable schema, or the motor-injection audit.  Record a decision in the")
    A("> `Decision` column by editing the *source* audit (a baseline entry's `note`,")
    A("> a schema `wired` flag), then regenerate.")
    A("")
    A("Each row is something the project **declares** (a test asserts it, a schema")
    A("advertises it, an invariant demands it) that **no code implements**.  They")
    A("were each found by a separate investigation; the point of this file is that")
    A("each is decided ONCE — *implement* or *formally retire* — instead of being")
    A("rediscovered, re-argued and worked around.")
    A("")
    A("Sources: `%s` (aspirational tests), `skills/brain_tunable_params.json`" % baseline_name)
    A("(`wired: false`), `scripts/audit_motor_injections.py` (architecture).")
    A("")
    A("---")
    A("")
    A("## 1. Tests asserting unimplemented features — %d entries" % n_asp)
    A("")
    A("| test file | # | what is declared | evidence | Decision |")
    A("|---|---|---|---|---|")
    for f, ents in sorted(asp.items(), key=lambda kv: -len(kv[1])):
        note = ents[0].get("note", "").replace("\n", " ")
        A("| `%s` | %d | %s | %s | _implement / retire_ |"
          % (f, len(ents), ents[0]["id"].split("::")[-1], note[:150]))
    A("")
    A("## 2. Unwired tunable parameters — %d entries" % len(unwired))
    A("")
    A("Advertised by `skills/brain_tunable_params.json`; since EVO-066 the panel")
    A("renders them disabled and Phase 6 excludes them from its search.  Each needs a")
    A("real consumer before `wired` may be set to `true` (a guard test enforces it).")
    A("")
    A("| parameter | declared range | default | documented intent | Decision |")
    A("|---|---|---|---|---|")
    for pid, meta in sorted(unwired):
        A("| `%s` | %s .. %s | %s | %s | _implement / retire_ |"
          % (pid, meta.get("min"), meta.get("max"), meta.get("default"),
             (meta.get("description") or "")[:110]))
    A("")
    A("## 3. Architectural aspirations")
    A("")
    if inj:
        A("### 3.1 `test_no_visual_motor_shortcut` — %d motor-pool injection sites"
          % inj["injection_sites"])
        A("")
        A("The test asserts that with the connectome zeroed, a black frame and a white")
        A("frame produce **identical** motor commands.  Measured (EVO-071): they differ")
        A("from tick 2, and disabling the two documented sensory gates does not change")
        A("that — because with the connectome zeroed those direct injections are the")
        A("only path.")
        A("")
        A("| measure | value |")
        A("|---|---|")
        A("| motor-pool injection sites in `fly64/model.py` | %d |"
          % inj["injection_sites"])
        A("| conditionally guarded (decided by a Python branch) | %d (%.0f%%) |"
          % (inj["guarded_sites"], inj["guarded_fraction"] * 100))
        A("| gated on a visual feature | %d (%.0f%%) |"
          % (inj["visually_gated_sites"], inj["visually_gated_fraction"] * 100))
        A("")
        A("Visually gated sites:")
        A("")
        for d in inj["visually_gated_detail"]:
            A("- `model.py:%d` → `%s` via `%s`" % (d["line"], d["pool"],
                                                   ", ".join(d["features"])))
        A("")
        A("**The honest framing**: P1 \"neural takeover\" retired some symbolic")
        A("branches, but %d direct injections remain and %d of them are decided by a"
          % (inj["injection_sites"], inj["guarded_sites"]))
        A("condition.  Either the invariant is retired as too strong (the documented")
        A("sensory-gate design is intentional), or the injections are progressively")
        A("replaced by network-resolved competition.")
        A("Decision: _retire invariant / continue takeover_.")
    else:
        A("_motor-injection audit unavailable (run scripts/audit_motor_injections.py)_")
    A("")
    A("---")
    A("")
    A("## Summary")
    A("")
    A("| source | entries |")
    A("|---|---|")
    A("| aspirational tests | %d |" % n_asp)
    A("| unwired tunable parameters | %d |" % len(unwired))
    A("| architectural aspirations | %d |" % (1 if inj else 0))
    A("| **total awaiting a decision** | **%d** |"
      % (n_asp + len(unwired) + (1 if inj else 0)))
    A("")
    A("Note: this register deliberately lists only things with **zero**")
    A("implementation.  Partially implemented items (e.g. the 3 `test-drift` and the")
    A("remaining `real-bug` entries in the verification baseline) are tracked")
    A("separately by `scripts/check_regressions.py`.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s" % out)
    print("  aspirational tests        : %d" % n_asp)
    print("  unwired tunable parameters: %d" % len(unwired))
    print("  architectural aspirations : %d" % (1 if inj else 0))
    print("  total awaiting a decision : %d"
          % (n_asp + len(unwired) + (1 if inj else 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
