#!/usr/bin/env python3
"""Captain verification of disputed counts: 874 vs 959, S7 export choice, protocol noise."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r".tmp\sessions_v3"

# Protocol-noise signatures (AgentTeams auto-dispatch / enqueue notifications)
NOISE_PAT = [
    re.compile(r"AgentTeams automatic task assignment from the shared task list"),
    re.compile(r"You have joined the team"),
    re.compile(r"Wait for an automatic assignment or a captain message"),
]
NOISE_RE = re.compile("|".join(p.pattern for p in NOISE_PAT))


def scan(path):
    """Return (all_user_msgs, real_user_msgs) as lists of texts."""
    allm, real = [], []
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return allm, real
    with fh:
        for line in fh:
            if '"user/message"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "user/message":
                continue
            data = rec.get("data") or {}
            src = data.get("source") or {}
            if not (isinstance(src, dict) and (src.get("kind") == "user" or data.get("rpcId"))):
                continue
            txt = ""
            for blk in (data.get("content") or []):
                if isinstance(blk, dict) and blk.get("type") == "text":
                    txt += blk.get("text", "")
            if not txt.strip():
                continue
            allm.append(txt)
            if not NOISE_RE.search(txt):
                real.append(txt)
    return allm, real


print("=== Per session: all vs real (protocol noise removed) ===")
tot_all = tot_real = 0
for entry in sorted(os.listdir(ROOT)):
    full = os.path.join(ROOT, entry)
    if not os.path.isdir(full):
        continue
    a = r = 0
    for root, _d, files in os.walk(full):
        for fn in files:
            if fn.endswith(".jsonl") and "session" in fn:
                aa, rr = scan(os.path.join(root, fn))
                a += len(aa)
                r += len(rr)
    tot_all += a
    tot_real += r
    print("  %-46s all=%-5d real=%-5d noise=%d" % (entry[:46], a, r, a - r))
print()
print("TOTAL all=%d  real=%d  noise=%d" % (tot_all, tot_real, tot_all - tot_real))
print()

# S7 export comparison
print("=== S7 (b2eeed98) both exports ===")
for d in ("b2eeed98-1614-4a9b-846f-058bde87f475",
          "b2eeed98-1614-4a9b-846f-058bde87f475 (1)"):
    full = os.path.join(ROOT, d)
    if not os.path.isdir(full):
        print("  MISSING:", d)
        continue
    a = r = 0
    for root, _dd, files in os.walk(full):
        for fn in files:
            if fn.endswith(".jsonl") and "session" in fn:
                aa, rr = scan(os.path.join(root, fn))
                a += len(aa)
                r += len(rr)
    print("  %-48s all=%-4d real=%-4d" % (d[:48], a, r))
