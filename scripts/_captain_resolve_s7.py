#!/usr/bin/env python3
"""Decisive check: are the two b2eeed98 (S7) exports superset/subset, and what is the
true de-duplicated real question count across the canonical 11 sessions?"""
import hashlib
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r".tmp\sessions_v3"
NOISE_RE = re.compile(
    r"AgentTeams automatic task assignment from the shared task list"
    r"|You have joined the team"
    r"|Wait for an automatic assignment or a captain message")


def msg_key(txt):
    t = txt.strip()
    return hashlib.sha1(t.encode("utf-8", "replace")).hexdigest()[:16]


def collect(dirname):
    """Return list of (key, text) for kind=user messages in one extracted dir."""
    out = []
    full = os.path.join(ROOT, dirname)
    if not os.path.isdir(full):
        return out
    for root, _d, files in os.walk(full):
        for fn in files:
            if not (fn.endswith(".jsonl") and "session" in fn):
                continue
            fh = open(os.path.join(root, fn), encoding="utf-8", errors="replace")
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
                    if not (isinstance(src, dict) and
                            (src.get("kind") == "user" or data.get("rpcId"))):
                        continue
                    txt = ""
                    for blk in (data.get("content") or []):
                        if isinstance(blk, dict) and blk.get("type") == "text":
                            txt += blk.get("text", "")
                    if txt.strip():
                        out.append((msg_key(txt), txt))
    return out


LEGACY = "b2eeed98-1614-4a9b-846f-058bde87f475"
NEWER = "b2eeed98-1614-4a9b-846f-058bde87f475 (1)"
a = collect(LEGACY)
b = collect(NEWER)
ka, kb = {k for k, _ in a}, {k for k, _ in b}

print("legacy  (no suffix): %d msgs, %d unique" % (len(a), len(ka)))
print("newer   (1)       : %d msgs, %d unique" % (len(b), len(kb)))
print()
print("only in legacy : %d" % len(ka - kb))
print("only in (1)    : %d" % len(kb - ka))
print("union unique   : %d" % len(ka | kb))
print()
if kb - ka:
    print("--- 4 msgs present only in (1) ---")
    seen = set()
    for k, t in b:
        if k in (kb - ka) and k not in seen:
            seen.add(k)
            print("  * %s" % t[:150].replace("\n", " "))
if ka - kb:
    print("--- msgs present only in legacy (would be LOST if using (1) alone) ---")
    seen = set()
    for k, t in a:
        if k in (ka - kb) and k not in seen:
            seen.add(k)
            print("  ! %s" % t[:150].replace("\n", " "))
