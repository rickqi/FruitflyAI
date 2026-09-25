#!/usr/bin/env python3
"""Extract every export-logs zip into .tmp/sessions_v5 for analysis v5."""
import io
import os
import shutil
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = r"D:\codes\flygym\export logs"
DST = r"D:\codes\flygym\.tmp\sessions_v5"

os.makedirs(DST, exist_ok=True)
zips = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".zip"))
print("zips found:", len(zips))
print()

ok = fail = skip = 0
for z in zips:
    name = z[:-4]                                   # strip .zip
    name = name.replace("dsh-session-session-", "")
    out = os.path.join(DST, name)
    if os.path.isdir(out) and any(
            f.endswith(".jsonl") for _r, _d, fs in os.walk(out) for f in fs):
        print("  skip (done)  %-46s" % name[:46])
        skip += 1
        continue
    os.makedirs(out, exist_ok=True)
    try:
        with zipfile.ZipFile(os.path.join(SRC, z)) as zf:
            zf.extractall(out)
        n = sum(1 for _r, _d, fs in os.walk(out) for f in fs)
        mb = sum(os.path.getsize(os.path.join(r, f))
                 for r, _d, fs in os.walk(out) for f in fs) / 1e6
        print("  OK  %-46s %3d files  %6.1f MB" % (name[:46], n, mb))
        ok += 1
    except Exception as e:
        print("  FAIL %-45s %s" % (name[:45], e))
        fail += 1

print()
print("extracted=%d skipped=%d failed=%d" % (ok, skip, fail))
print()

print("=== extracted dirs (jsonl count / MB) ===")
for d in sorted(os.listdir(DST)):
    full = os.path.join(DST, d)
    if not os.path.isdir(full):
        continue
    n = 0
    size = 0
    for r, _dd, fs in os.walk(full):
        for f in fs:
            if f.endswith(".jsonl"):
                n += 1
                size += os.path.getsize(os.path.join(r, f))
    print("  %-48s %3d jsonl  %7.1f MB" % (d[:48], n, size / 1e6))
