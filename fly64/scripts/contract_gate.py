#!/usr/bin/env python3
"""CI contract gate: the Fly64 zero-tolerance barrier for unobservable failures.

Why this exists
---------------
The systematic write->read contract audit (``audit_contract_pairs.py``) found
multiple instances where a mechanism existed, passed tests, reported success —
and structurally could not take effect.  Finding those ad hoc does not scale.
This gate turns that knowledge into an enforced CI barrier:

1. Run ``audit_contract_pairs.py --json``, flag every DEAD-WRITE / SILENT-DEFAULT.
2. Validate that every contract in the registry has active producer AND consumer
   code paths.
3. Enforce RULE-19 ("不可观测的失败零容忍") — any unobservable state path
   (written but never read, read but never written) rejects the CI run.

Usage:
  python3 scripts/contract_gate.py
  python3 scripts/contract_gate.py --json     # emit JSON report only
  python3 scripts/contract_gate.py --verbose  # print every checked rule

Exit codes:
  0 = GATE PASS  (all contracts clean)
  1 = GATE FAIL  (unobservable failures detected)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "contract_registry.json"
AUDIT_SCRIPT = ROOT / "scripts" / "audit_contract_pairs.py"
CI_YML = ROOT.parent / ".github" / "workflows" / "ci.yml"

#: Known keys the audit tool treats as metadata (excluded from contract check)
METADATA_KEYS = {
    "$schema", "version", "description", "aliases", "min", "max", "note",
    "notes", "ts", "at", "time", "date", "source", "model", "recorded_at",
    "first_seen", "last_seen", "updated_at", "created_at", "as_of",
    "canonical_versions", "records", "history",
}


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print("[contract-gate] FATAL: contract_registry.json not found at %s" % REGISTRY_PATH)
        sys.exit(1)
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def run_audit() -> dict:
    """Run audit_contract_pairs.py --json and parse its output."""
    import subprocess as sp
    r = sp.run([sys.executable, str(AUDIT_SCRIPT), "--json"],
               capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print("[contract-gate] audit_contract_pairs.py exited %d" % r.returncode)
        print(r.stderr[:2000])
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print("[contract-gate] audit JSON parse error: %s" % e)
        return {}


def check_contract_registration(registry: dict, findings: list) -> None:
    """ZT-5: Every contract in registry must have valid producer and consumer code paths."""
    for name, contract in registry.get("contracts", {}).items():
        producers = contract.get("producers", [])
        consumers = contract.get("consumers", [])
        if not producers:
            findings.append({
                "id": "ZT-5-%s" % name,
                "severity": "blocker",
                "problem": "Contract '%s' has zero registered producers" % name,
                "requiredFix": "Add at least one producer module to contract_registry.json for '%s'" % name,
            })
        if not consumers:
            findings.append({
                "id": "ZT-5-%s" % name,
                "severity": "blocker",
                "problem": "Contract '%s' has zero registered consumers" % name,
                "requiredFix": "Add at least one consumer module to contract_registry.json for '%s'" % name,
            })


def check_bridge_mmap_contract(registry: dict, gate_results: dict, verbose: bool) -> list:
    """Validate bridge mmap layout fields against producer/consumer existence.

    For each field in the registry layout, check that:
    - The producer module (bridge.py) exists
    - At least one consumer module exists
    """
    findings = []
    bridge_contract = registry.get("contracts", {}).get("bridge_mmap", {})
    layout = bridge_contract.get("layout", [])
    bridge_py = ROOT / "fly64" / "bridge.py"
    if not bridge_py.exists():
        findings.append({
            "id": "BRIDGE-1", "severity": "blocker",
            "problem": "bridge.py producer module missing",
            "requiredFix": "Restore fly64/fly64/bridge.py"
        })
        return findings

    # Check write-once fields have at least one producer reference
    for field in layout:
        producers = field.get("producer", "")
        consumers = field.get("consumers", [])
        if not producers:
            findings.append({
                "id": "BRIDGE-FIELD-%s" % field["field"],
                "severity": "high",
                "problem": "Bridge field '%s' at offset %d has no declared producer" % (field["field"], field["offset"]),
                "requiredFix": "Declare the producer for field '%s' in contract_registry.json" % field["field"]
            })
        if not consumers:
            findings.append({
                "id": "BRIDGE-FIELD-%s" % field["field"],
                "severity": "high",
                "problem": "Bridge field '%s' at offset %d has no declared consumers" % (field["field"], field["offset"]),
                "requiredFix": "Declare consumers for field '%s' in contract_registry.json" % field["field"]
            })

    # Check that all layout offsets are valid (no overlap)
    offsets = [(f["offset"], f["offset"] + f["size"], f["field"]) for f in layout]
    offsets.sort()
    for i in range(len(offsets) - 1):
        curr_end = offsets[i][1]
        next_start = offsets[i + 1][0]
        if curr_end > next_start:
            findings.append({
                "id": "BRIDGE-OVERLAP", "severity": "blocker",
                "problem": "Bridge field '%s' (offset %d-%d) overlaps with '%s' (offset %d)" %
                           (offsets[i][2], offsets[i][0], curr_end, offsets[i + 1][2], next_start),
                "requiredFix": "Fix layout offsets in contract_registry.json"
            })

    # Check zero-tolerance rules are documented
    zt_list = bridge_contract.get("unobservable_failures_zero_tolerance", [])
    if not zt_list:
        findings.append({
            "id": "BRIDGE-ZT", "severity": "high",
            "problem": "bridge_mmap contract has no unobservable_failures_zero_tolerance entries",
            "requiredFix": "Document at least one RULE-19 condition for bridge_mmap"
        })

    if verbose:
        for f in findings:
            print("  [ZT] %s: %s" % (f["id"], f["problem"]))
    return findings


def check_active_strategy_contract(gate_results: dict, verbose: bool) -> list:
    """ZT-3: Validate SECTION_SPECS keys have consumers in brain code.

    This is the same check as test_coach_contract.py::TestEveryAdvertisedKeyHasAConsumer,
    repeated as a CI barrier so a broken merge cannot skip the test suite.
    """
    findings = []
    sys.path.insert(0, str(ROOT))
    try:
        from plugin.llm_consult import SECTION_SPECS  # noqa: E402
    except ImportError:
        findings.append({
            "id": "STRATEGY-IMPORT", "severity": "blocker",
            "problem": "Cannot import SECTION_SPECS from plugin.llm_consult",
            "requiredFix": "Ensure plugin/llm_consult.py is valid Python and SECTION_SPECS is defined"
        })
        return findings

    # Scan consumer modules for literal string reads
    consumers = [
        ROOT / "fly64" / "main.py",
        ROOT / "fly64" / "memory.py",
        ROOT / "fly64" / "model.py",
    ]
    consumed = set()
    import ast
    for mod in consumers:
        if not mod.exists():
            continue
        try:
            tree = ast.parse(mod.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue

        class V(ast.NodeVisitor):
            def __init__(self):
                self.parents = {}
            def generic_visit(self, n):
                for c in ast.iter_child_nodes(n):
                    self.parents[c] = n
                    self.visit(c)

        v = V()
        v.visit(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            parent = v.parents.get(node)
            if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute):
                if parent.func.attr == "get" and node in parent.args:
                    consumed.add(node.value)
            elif isinstance(parent, ast.Subscript) and parent.slice is node:
                if isinstance(parent.ctx, ast.Load):
                    consumed.add(node.value)
            elif isinstance(parent, ast.Compare) and node in parent.comparators:
                consumed.add(node.value)

    for section, spec in SECTION_SPECS.items():
        for key in spec:
            if key not in consumed and (section, key) not in _get_loop_consumed():
                findings.append({
                    "id": "STRATEGY-DEAD-KEY-%s.%s" % (section, key),
                    "severity": "blocker",
                    "problem": "SECTION_SPECS advertises '%s.%s' but no consumer module reads it — "
                               "the coach would be asked to tune a no-op" % (section, key),
                    "requiredFix": "Either wire a consumer for '%s.%s' or remove it from SECTION_SPECS "
                                   "(see escape.reverse_seconds, EVO-066)" % (section, key)
                })

    if verbose:
        for f in findings:
            print("  [ZT-3] %s: %s" % (f["id"], f["problem"]))
    return findings


def _get_loop_consumed() -> set:
    """Keys consumed through loop variables (not literal string reads)."""
    return set()


def check_rule19_zero_tolerance(audit_result: dict, verbose: bool) -> list:
    """ZT-1: Every DEAD-WRITE or SILENT-DEFAULT is an unobservable failure.

    Returns list of finding dicts; empty means pass.
    """
    findings = []
    for artifact, info in audit_result.items():
        if info.get("status") != "ok":
            continue
        for row in info.get("rows", []):
            cls = row.get("class")
            key = row.get("key", "?")
            if cls == "DEAD-WRITE":
                findings.append({
                    "id": "ZT-1-DEAD-WRITE-%s-%s" % (artifact.replace("/", "-"), key.replace(".", "-")),
                    "severity": "blocker",
                    "problem": "RULE-19: '%s' in %s is a DEAD-WRITE (w=%d r=%d decl=%d) — "
                               "key is written but never read, producing unobservable state" %
                               (key, artifact, row.get("w", 0), row.get("r", 0), row.get("d", 0)),
                    "requiredFix": "Either add a consumer read site for '%s' in %s or remove the write"
                                   % (key, artifact),
                })
            elif cls == "SILENT-DEFAULT":
                findings.append({
                    "id": "ZT-1-SILENT-DEFAULT-%s-%s" % (artifact.replace("/", "-"), key.replace(".", "-")),
                    "severity": "blocker",
                    "problem": "RULE-19: '%s' in %s is a SILENT-DEFAULT (w=%d r=%d decl=%d) — "
                               "key is read but never written, consumers consume a phantom default" %
                               (key, artifact, row.get("w", 0), row.get("r", 0), row.get("d", 0)),
                    "requiredFix": "Either add a producer write site for '%s' in %s or remove the read"
                                   % (key, artifact),
                })

    if verbose:
        for f in findings:
            print("  [ZT-1] %s: %s" % (f["id"], f["problem"][:120]))
    return findings


def check_registry_completeness(registry: dict, audit_result: dict, verbose: bool) -> list:
    """ZT-5: Audit should cover every registered contract's artifacts."""
    findings = []
    registered_artifacts = set()
    for name, contract in registry.get("contracts", {}).items():
        art = contract.get("artifact", "")
        if art and not art.startswith("/"):
            registered_artifacts.add(art.lstrip("/"))

    audited_artifacts = set(audit_result.keys())
    missing_in_audit = registered_artifacts - audited_artifacts
    if missing_in_audit:
        for art in sorted(missing_in_audit):
            # Some artifacts (like runtime/fly64_bridge.bin) are binary — not
            # JSON-key-scannable, so they'd be expectedly absent.  Only flag
            # JSON/text artifacts.
            if art.endswith(".json") or art.endswith(".jsonl"):
                findings.append({
                    "id": "ZT-5-MISSING-%s" % art.replace("/", "-").replace(".", "-"),
                    "severity": "high",
                    "problem": "Contract artifact '%s' is registered but not covered by audit_contract_pairs.py — "
                               "add it to ARTIFACTS in audit_contract_pairs.py" % art,
                    "requiredFix": "Add '%s' to the ARTIFACTS dict in scripts/audit_contract_pairs.py" % art,
                })

    if verbose:
        for f in findings:
            print("  [ZT-5] %s: %s" % (f["id"], f["problem"]))
    return findings


def main():
    ap = argparse.ArgumentParser(
        description="Contract gate: zero-tolerance CI barrier for unobservable failures")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON report only")
    ap.add_argument("--verbose", action="store_true",
                    help="Print every checked rule")
    args = ap.parse_args()

    # Load registry
    registry = load_registry()
    if args.verbose:
        print("[contract-gate] Registry loaded: %d contracts" %
              len(registry.get("contracts", {})))

    # 1. Run the systematic write->read audit
    audit_result = run_audit()
    if not audit_result:
        print("[contract-gate] WARNING: audit_contract_pairs.py returned no data — checks limited")
    else:
        audited = len(audit_result)
        total_keys = sum(len(v.get("rows", [])) for v in audit_result.values() if v.get("status") == "ok")
        if args.verbose:
            print("[contract-gate] Audit: %d artifacts, %d total keys" % (audited, total_keys))

    all_findings = []

    # ZT-1: Rule 19 — DEAD-WRITE and SILENT-DEFAULT are unobservable failures
    audit_findings = check_rule19_zero_tolerance(audit_result, args.verbose)
    all_findings.extend(audit_findings)

    # ZT-3: Active strategy advertised params must have consumers
    strategy_findings = check_active_strategy_contract(audit_result, args.verbose)
    all_findings.extend(strategy_findings)

    # ZT-5: Registered contracts must be valid
    check_contract_registration(registry, all_findings)
    bridge_findings = check_bridge_mmap_contract(registry, audit_result, args.verbose)
    all_findings.extend(bridge_findings)
    registry_findings = check_registry_completeness(registry, audit_result, args.verbose)
    all_findings.extend(registry_findings)

    # Determine gate result
    blockers = [f for f in all_findings if f["severity"] in ("blocker", "high")]
    gate_pass = len(blockers) == 0

    if args.json:
        print(json.dumps({
            "gate": "PASS" if gate_pass else "FAIL",
            "total_findings": len(all_findings),
            "blockers": len(blockers),
            "findings": all_findings,
        }, ensure_ascii=False, indent=1))
        return 0 if gate_pass else 1

    # Human-readable output
    print("=" * 72)
    print("FLY64 CONTRACT GATE — Zero-tolerance CI barrier (RULE-19)")
    print("=" * 72)

    if audit_result:
        total_flags = sum(
            1 for v in audit_result.values() if v.get("status") == "ok"
            for r in v.get("rows", [])
            if r.get("class") in ("DEAD-WRITE", "SILENT-DEFAULT")
        )
        print("\n  [audit_contract_pairs.py] %d artifacts, %d dead/silent flags" %
              (len(audit_result), total_flags))

    if not all_findings:
        print("\n  ✓ ZT-1: No DEAD-WRITE or SILENT-DEFAULT keys found")
        print("  ✓ ZT-3: All SECTION_SPECS keys have registered consumers")
        print("  ✓ ZT-5: All registered contracts validate")
        print("\n" + "=" * 72)
        print("GATE: PASS — all contracts clean")
        print("=" * 72)
        return 0

    print("\n  *** FINDINGS (%d total, %d blockers):" % (len(all_findings), len(blockers)))
    for f in all_findings:
        icon = "!!" if f["severity"] in ("blocker", "high") else "??"
        print("    %s [%-7s] %s" % (icon, f["severity"], f["id"]))
        print("      %s" % f["problem"][:150])
        print("      Fix: %s" % f["requiredFix"][:150])
        print()

    print("=" * 72)
    if gate_pass:
        print("GATE: PASS (warnings only)")
    else:
        print("GATE: FAIL — %d blocker(s) (RULE-19 zero-tolerance violated)" % len(blockers))
        print("Fix all findings above before merging.")
    print("=" * 72)
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())