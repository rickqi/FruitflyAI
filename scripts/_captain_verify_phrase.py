#!/usr/bin/env python3
"""Precise classification of the '大部分动作没有尝试' evidence in the canonical corpus."""
import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r".tmp/sessions_v3"
CANON = [
    "1f8fbe04-52eb-4dc8-9b63-b0f497c48b23",
    "27ed0979-15ec-4711-bd47-c8cf63b109b8",
    "38542b1c-45e7-4c96-b615-94875cd2bd0e",
    "71c21f6d-cb76-4baf-9afb-822765a043e4 (1)",
    "90dd512b-6955-4848-9216-3c3c94c35b41",
    "99cab60f-fada-4a9e-9d10-ababdd0f4373 (3)",
    "b2eeed98-1614-4a9b-846f-058bde87f475 (1)",
    "d983cef5-3f9c-4b97-9eac-820390a38bbd",
    "ed4b8026-6bfe-40ee-9be8-b5fb3b59e612",
    "f953d3fd-dcea-430f-9bee-461b8d73943e",
    "fdb47617-7c9a-46b3-8cc0-80588409602c",
]
VARIANTS = {
    "大部分动作没有尝试": 0,   # exact phrase
    "大部分没有尝试": 0,       # shorter variant
}

rows = []
for entry in CANON:
    full = os.path.join(ROOT, entry)
    for root, _d, files in os.walk(full):
        for fn in files:
            if not (fn.endswith(".jsonl") and "session" in fn):
                continue
            fh = open(os.path.join(root, fn), encoding="utf-8", errors="replace")
            with fh:
                for line in fh:
                    for v in VARIANTS:
                        if v not in line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        t = rec.get("type", "?")
                        data = rec.get("data") or {}
                        src = (data.get("source") or {}) if isinstance(data.get("source"), dict) else {}
                        is_human = src.get("kind") == "user"
                        rows.append((v, t, is_human, rec.get("seq"), entry[:8]))

print("=== all events containing either variant (canonical corpus) ===")
cnt = Counter()
for v, t, human, seq, sess in sorted(rows, key=lambda r: r[3] or 0):
    cnt[(v, t, human)] += 1
    print("  %-22s %-22s human=%-5s seq=%s [%s]" % (v, t, human, seq, sess))
print()
print("=== summary ===")
tot = Counter()
for (v, t, human), n in cnt.items():
    tot[v] += n
for v, n in tot.items():
    print("  variant %-22s raw events = %d" % (v, n))
print()
human_exact = sum(1 for v, t, h, _s, _e in rows if v == "大部分动作没有尝试" and t == "user/message" and h)
print("  '大部分动作没有尝试' as genuine user/message =", human_exact)
