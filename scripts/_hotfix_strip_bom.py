#!/usr/bin/env python3
"""Hotfix: strip UTF-8 BOM from default_patterns.json so plain utf-8 also parses.

Root cause of the master regression:
  - evolution_skill.PatternCatalog._load reads with read_text("utf-8") on master
  - default_patterns.json carries a UTF-8 BOM (EF BB BF)
  - json.loads raises "Unexpected UTF-8 BOM"
  - the except branch sets self.patterns = []  => EMPTY diagnostic catalog in production
"""
import io
import json
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = r"fly64\skills\default_patterns.json"
with open(P, "rb") as f:
    raw = f.read()

print("before: first 3 bytes =", " ".join("%02X" % b for b in raw[:3]))

# Verify the payload parses once the BOM is removed
if raw.startswith(b"\xef\xbb\xbf"):
    body = raw[3:]
    print("BOM detected -> stripping")
else:
    body = raw
    print("no BOM")

# Sanity: body must be valid UTF-8 JSON with 16 patterns
data = json.loads(body.decode("utf-8"))
print("patterns after BOM strip:", len(data["patterns"]))
ids = {p.get("id") for p in data["patterns"]}
print("wall_corner_command_decoupled present:", "wall_corner_command_decoupled" in ids)

# Write back without BOM (preserve trailing newline if present)
shutil.copy2(P, P + ".bom_bak")
with open(P, "wb") as f:
    f.write(body)
with open(P, "rb") as f:
    check = f.read()
print("after : first 3 bytes =", " ".join("%02X" % b for b in check[:3]))
print("after : parses with plain utf-8:", end=" ")
try:
    d2 = json.loads(check.decode("utf-8"))
    print("yes, patterns =", len(d2["patterns"]))
except Exception as e:
    print("NO ->", e)
