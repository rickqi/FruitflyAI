#!/usr/bin/env python3
"""Captain verification of t6 (P0-1b) + five-site version consistency."""
import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def read(p):
    return open(p, encoding="utf-8").read()


# ── A. canonical_versions contract ──────────────────────────────────────
d = json.load(open(r"fly64\skills\evolution_history.json", encoding="utf-8"))
c = d["canonical_versions"]
print("=== A. canonical_versions contract ===")
print("  canonical_versions:", json.dumps(c, ensure_ascii=False))
print("  top-level keys    :", list(d.keys()))
a_pass = (c.get("brain") == "2.23.12" and c.get("skill") == "3.5.0"
          and "as_of" in c and "as_of" not in d)
print("  A PASS            :", a_pass)
print("  records           :", len(d["records"]), "| last:", d["records"][-1]["id"])
print()

# ── B. README auto table ────────────────────────────────────────────────
rd = read(r"fly64\README.md")
print("=== B. README auto-table ===")
for m in re.finditer(r"自动生成（(\d+) 条[^）]*）", rd):
    print("  header:", m.group(0)[:90])
print("  last EVO row:", "EVO-072" in rd)
block = re.search(r"EVOLUTION-HISTORY-TABLE:START(.*?)EVOLUTION-HISTORY-TABLE:END",
                  rd, re.S)
if block:
    rows = [l for l in block.group(1).splitlines() if l.strip().startswith("| EVO-")]
    print("  rows in block:", len(rows), "| last row id:", rows[-1].split("|")[1].strip() if rows else "?")
print()

# ── Five-site version consistency ───────────────────────────────────────
print("=== five-site version consistency ===")
main = read(r"fly64\fly64\main.py")
bv = re.search(r'BRAIN_VERSION\s*=\s*"([^"]+)"', main).group(1)
sv = re.search(r'SKILL_VERSION\s*=\s*"([^"]+)"', main).group(1)
sm = read(r"fly64\skills\skills.md")
es = re.search(r'SKILL_VERSION\s*=\s*"([^"]+)"',
               read(r"fly64\skills\evolution_skill.py")).group(1)
rd_auto = sorted(set(re.findall(r"Brain v(2\.23\.\d+) / Skill v(3\.\d+\.\d+)", rd)))
sm_vers = sorted(set(re.findall(r"BRAIN_VERSION \*\*(2\.23\.\d+)\*\* / SKILL_VERSION \*\*(3\.\d+\.\d+)\*\*", sm)))

print("  1 main.py           :", bv, sv)
print("  2 skills.md badges  :", sm_vers)
print("  3 evolution_skill   :", es)
print("  4 canonical_versions:", c["brain"], c["skill"])
print("  5 README auto-table :", rd_auto)
print()
all_ok = (
    bv == "2.23.12" and sv == "3.5.0"
    and es == sv
    and c["brain"] == bv and c["skill"] == sv
    and all(b == bv and s == sv for b, s in sm_vers)
    and all(b == bv and s == sv for b, s in rd_auto)
)
print("  ALL FIVE CONSISTENT :", all_ok)
