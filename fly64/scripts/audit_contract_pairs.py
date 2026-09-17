#!/usr/bin/env python3
"""Audit write->read contract pairs for the JSON artifacts that carry state
between components.

WHY
---
This session found SIX instances of one failure family by hand: a mechanism is
implemented, wired, tested — and structurally cannot take effect.  Examples: the
coach's strategy sections were never passed through (every parameter silently
fell back to a default); a CX loop-break block read an attribute its own object
never had; the instinct fingerprint could never repeat; a module-level call
raised NameError only in production; the operator panel wrote dotted ids as
literal keys the brain does not read; a lesson goal read an unobservable metric
as a failure.

Finding those ad hoc does not scale.  This auditor does it mechanically: for
every key of every producer/consumer artifact, count WRITE and READ sites across
the modules that participate in that artifact's pipeline, and flag

    * DEAD WRITE      — written somewhere, read nowhere  (the dotted-key bug)
    * SILENT DEFAULT  — read somewhere, written nowhere  (the t6 passthrough bug)

Nested containers are recursed because the highest-value defects live one level
down (`exploration.turn_bias` was read while the writer emitted
`exploration.bold_turn_bias`).

PRECISION NOTES (learned from the first run, which was ~90% false positives)
--------------------------------------------------------------------------
* A key read through a loop variable — `for key in ("climb_period",
  "persist_seconds"): section.get(key, ...)` — has NO string-literal read site.
  Such tuple/list/set members are recorded as `decl` and a `decl` occurrence
  SUPPRESSES both flags.  Without this, every loop-driven read looked like a
  dead write.
* Browser consumers live in .js/.html, so those are scanned with regexes too;
  otherwise dashboard-only keys look dead.
* Pure schema/metadata fields (`$schema`, `version`, `description`, `aliases`,
  `min`, `max`) are not producer/consumer keys and are skipped.
* Declarative schema files (`brain_tunable_params.json`) are not producer/
  consumer artifacts and are excluded from the contract check.

Usage:  python3 scripts/audit_contract_pairs.py [--json] [--all]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

READ_ATTRS = {"get", "pop"}
WRITE_ATTRS = {"update", "setdefault", "__setitem__"}
SERIALIZERS = {"dumps", "dump", "write_text", "write_bytes", "write"}

SKIP_DIRS = {".git", "__pycache__", ".pytest-run", "venv", "node_modules",
             ".cache", "build", "artifacts", "output"}

#: not producer/consumer keys — schema or bookkeeping metadata
METADATA_KEYS = {
    "$schema", "version", "description", "aliases", "min", "max", "note",
    "notes", "ts", "at", "time", "date", "source", "model", "recorded_at",
    "first_seen", "last_seen", "updated_at", "created_at", "as_of",
    "canonical_versions", "records", "history",
}


def iter_files(paths, exts):
    seen = []
    for p in paths:
        p = ROOT / p
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix in exts and not any(x in SKIP_DIRS for x in f.parts):
                    seen.append(f)
        elif p.exists() and p.suffix in exts:
            seen.append(p)
    return seen


class Classifier(ast.NodeVisitor):
    def __init__(self):
        self.parents = {}

    def generic_visit(self, n):
        for child in ast.iter_child_nodes(n):
            self.parents[child] = n
            self.visit(child)


def classify(node, parent, grand):
    if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute):
        attr = parent.func.attr
        if attr in READ_ATTRS and node in parent.args:
            return "read"
        if attr in WRITE_ATTRS or attr in SERIALIZERS:
            return "write"
    if isinstance(parent, ast.Subscript) and parent.slice is node:
        if isinstance(parent.ctx, ast.Load):
            return "read"
        if isinstance(parent.ctx, (ast.Store, ast.Del)):
            return "write"
    if isinstance(parent, ast.Compare) and node in parent.comparators:
        return "read"
    if isinstance(parent, ast.Dict) and node in parent.keys:
        return "write"
    if isinstance(parent, (ast.Set, ast.List, ast.Tuple)):
        return "decl"
    if isinstance(parent, ast.arguments):
        return "decl"
    return None


def scan_py(files):
    out = defaultdict(lambda: {"read": [], "write": [], "decl": []})
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        v = Classifier()
        v.visit(tree)
        try:
            rel = f.relative_to(ROOT).as_posix()
        except ValueError:
            rel = f.as_posix()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue
            parent = v.parents.get(node)
            grand = v.parents.get(parent) if parent is not None else None
            role = classify(node, parent, grand)
            if role:
                out[node.value][role].append("%s:%d" % (rel, node.lineno))
    return out


def scan_js(files):
    """Coarse read detection for browser consumers."""
    out = defaultdict(lambda: {"read": [], "write": [], "decl": []})
    pat_read = re.compile(r"""(?:\.get\(\s*|\[\s*)['"]([A-Za-z_$][\w$.]*)['"]""")
    pat_prop = re.compile(r"""\.([A-Za-z_$][\w$]*)\s*(?!\()""")
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            rel = f.relative_to(ROOT).as_posix()
        except ValueError:
            rel = f.as_posix()
        for m in pat_read.finditer(text):
            out[m.group(1)]["read"].append("%s" % rel)
        for m in pat_prop.finditer(text):
            out[m.group(1)]["read"].append("%s" % rel)
    return out


#: artifact -> modules that participate in its pipeline (+ browser consumers)
ARTIFACTS = {
    "skills/active_strategy.json": {
        "files": ["fly64/fly64/main.py", "plugin/strategy_writer.py",
                  "plugin/runner.py", "plugin/service.py", "plugin/llm_consult.py",
                  "plugin/scene_context.py", "skills/evolution_skill.py",
                  "fly64/fly64/instinct_bindings.py", "plugin/coach_outcomes.py"],
        "web": ["web"],
    },
    "skills/curriculum.json": {
        "files": ["plugin/coach_outcomes.py"],
        "web": [],
    },
    "skills/coach_outcomes.jsonl": {
        "files": ["plugin/coach_outcomes.py", "plugin/runner.py",
                  "fly64/fly64/instinct_bindings.py"],
        "web": [],
    },
    "skills/scene_strategy_bindings.json": {
        "files": ["fly64/fly64/instinct_bindings.py", "fly64/fly64/main.py",
                  "plugin/runner.py"],
        "web": [],
    },
    "plugin/.pending_outcome.json": {
        "files": ["plugin/coach_outcomes.py", "plugin/runner.py",
                  "plugin/service.py"],
        "web": [],
    },
    "plugin/.consult_request.json": {
        "files": ["plugin/llm_consult.py", "plugin/scene_context.py"],
        "web": [],
    },
    "plugin/.consult_response.json": {
        "files": ["plugin/llm_consult.py", "plugin/strategy_writer.py"],
        "web": [],
    },
    "skills/coach_advice.json": {
        "files": ["plugin/llm_consult.py", "plugin/strategy_writer.py",
                  "fly64/fly64/main.py"],
        "web": ["web"],
    },
    "plugin/service_status.json": {
        "files": ["plugin/service.py"],
        "web": ["web"],
    },
}


def live_keys(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        if rel.endswith(".jsonl"):
            with p.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        return json.loads(line)
            return {}
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def flatten(obj, prefix=""):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = "%s.%s" % (prefix, k) if prefix else str(k)
            out.append(path)
            if isinstance(v, dict) and len(v) <= 40:
                out.extend(flatten(v, path))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="also print keys classified ok")
    args = ap.parse_args()

    report = {}
    for rel, cfg in ARTIFACTS.items():
        obj = live_keys(rel)
        if obj is None:
            report[rel] = {"status": "absent"}
            continue
        pyf = iter_files(cfg["files"], {".py"})
        jsf = iter_files(cfg.get("web", []), {".js", ".html"})
        sites = scan_py(pyf)
        for k, v in scan_js(jsf).items():
            for role in ("read", "write", "decl"):
                sites[k][role].extend(v[role])
        rows = []
        for key in flatten(obj):
            leaf = key.split(".")[-1]
            if leaf in METADATA_KEYS:
                continue
            s = sites.get(leaf) or sites.get(key)
            w = len(s["write"]) if s else 0
            r = len(s["read"]) if s else 0
            d = len(s["decl"]) if s else 0
            if not s:
                cls = "unreferenced"
            elif w and not r and not d:
                cls = "DEAD-WRITE"
            elif r and not w and not d:
                cls = "SILENT-DEFAULT"
            elif d and not w and not r:
                cls = "loop-read-only"
            else:
                cls = "ok"
            rows.append({"key": key, "w": w, "r": r, "d": d, "class": cls,
                         "w_sites": (s["write"][:3] if s else []),
                         "r_sites": (s["read"][:3] if s else [])})
        report[rel] = {"status": "ok", "py": len(pyf), "js": len(jsf),
                       "rows": rows}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0

    total_flags = 0
    print("=" * 78)
    print("WRITE -> READ CONTRACT AUDIT")
    print("=" * 78)
    for rel, info in report.items():
        print("\n### %s" % rel)
        if info["status"] != "ok":
            print("    %s" % info["status"])
            continue
        print("    scanned %d .py + %d web file(s), %d keys"
              % (info["py"], info["js"], len(info["rows"])))
        flagged = [r for r in info["rows"]
                   if r["class"] in ("DEAD-WRITE", "SILENT-DEFAULT",
                                     "loop-read-only", "unreferenced")]
        total_flags += len([r for r in info["rows"]
                            if r["class"] in ("DEAD-WRITE", "SILENT-DEFAULT")])
        if not flagged:
            print("    clean")
        for r in flagged:
            print("    [%-16s] %-44s w=%d r=%d decl=%d"
                  % (r["class"], r["key"], r["w"], r["r"], r["d"]))
            for s in r["w_sites"]:
                print("        W %s" % s)
            for s in r["r_sites"]:
                print("        R %s" % s)
        if args["all"] if isinstance(args, dict) else args.all:
            for r in info["rows"]:
                if r["class"] == "ok":
                    print("    [ok              ] %s" % r["key"])
    print("\n%s" % ("=" * 78))
    print("TOTAL dead-writes + silent-defaults: %d" % total_flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
