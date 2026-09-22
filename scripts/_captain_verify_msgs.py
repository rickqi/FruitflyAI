#!/usr/bin/env python3
"""Locate specific user messages with timestamps across sessions (captain verification)."""
import datetime
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r".tmp\sessions_v3"
PATTERNS = ["大部分动作", "coach", "Coach", "键名归一化", "覆盖", "未生效"]

rows = []
for root, _dirs, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".jsonl"):
            continue
        p = os.path.join(root, fn)
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
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
                if not (isinstance(src, dict) and src.get("kind") == "user"):
                    continue
                txt = ""
                for blk in (data.get("content") or []):
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        txt += blk.get("text", "")
                if not txt:
                    continue
                if any(pat in txt for pat in PATTERNS):
                    ts = rec.get("time")
                    dt = datetime.datetime.fromtimestamp(ts / 1000) if ts else None
                    rows.append((dt, root.split(os.sep)[-1][:8], txt[:130].replace("\n", " ")))

rows.sort(key=lambda r: (r[0] is None, r[0]))
print("=== user messages matching key patterns (chronological) ===")
for dt, sess, txt in rows:
    stamp = dt.strftime("%m-%d %H:%M") if dt else "?"
    print("%s [%s] %s" % (stamp, sess, txt))
print()
print("TOTAL:", len(rows))
if rows:
    print("FIRST:", rows[0][0])
    print("LAST :", rows[-1][0])
