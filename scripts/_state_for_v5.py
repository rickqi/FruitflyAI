#!/usr/bin/env python3
"""Collect current project state facts for the v5 report."""
import io
import json
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def read(p):
    return open(p, encoding="utf-8", errors="replace").read()


print("=== versions ===")
m = read(r"fly64\fly64\main.py")
print("  main.py BRAIN_VERSION :", re.search(r'BRAIN_VERSION\s*=\s*"([^"]+)"', m).group(1))
print("  main.py SKILL_VERSION :", re.search(r'SKILL_VERSION\s*=\s*"([^"]+)"', m).group(1))
e = read(r"fly64\skills\evolution_skill.py")
mm = re.search(r'^SKILL_VERSION\s*=\s*"([^"]+)"', e, re.M)
print("  evolution_skill.py    :", mm.group(1) if mm else "?")

h = json.load(open(r"fly64\skills\evolution_history.json", encoding="utf-8"))
print("  canonical_versions    :", json.dumps(h["canonical_versions"], ensure_ascii=False))
print("  records               :", len(h["records"]), "| last:", h["records"][-1].get("id"))

b = json.load(open(r"fly64\tests\known_failures.win32.json", encoding="utf-8"))
print("  baseline (win32)      :", b.get("count"), "entries")
from collections import Counter
print("  cause distribution    :", dict(Counter(x.get("cause") for x in b.get("entries", []))))

print()
print("=== tests ===")
import glob
files = glob.glob(r"fly64\tests\test_*.py")
print("  test files            :", len(files))

print()
print("=== git ===")
log = subprocess.run(["git", "log", "--oneline", "-5"], capture_output=True, text=True).stdout
print(log.strip())
st = subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout
lines = [l for l in st.splitlines() if ".pytest-run/" not in l]
print("  uncommitted entries   :", len(lines))

print()
print("=== new analysis doc inventory ===")
import os
for f in sorted(os.listdir(r"docs\analysis")):
    if f.endswith(".md") and ("session_logs" in f or f.startswith("analysis-")):
        p = os.path.join(r"docs\analysis", f)
        print("  %-52s %6.1f KB" % (f, os.path.getsize(p) / 1024))
