"""A2 rootcause analysis helper: extract REAL user messages from DSH session jsonl exports.

Reads export logs/_extracted_*/session*.jsonl (+ subagents), keeps only records whose
data.source.kind == 'user' and whose text is not an injected system/plugin snapshot.
Writes a compact TSV-ish text file per session to .tmp/a2/.

Usage: python scripts/_a2_extract_user_msgs.py
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, "export logs")
OUT = os.path.join(ROOT, ".tmp", "a2")
os.makedirs(OUT, exist_ok=True)

CN = timezone(timedelta(hours=8))

# substrings that mark injected (non-human) user-role messages
INJECT_MARKERS = (
    "Current runtime context.",
    "<system-reminder>",
    "AgentTeams automatic task assignment",
    "Team goal:",
    "You are an AgentTeams member",
    "Profile protocol:",
    "Working rules:",
    "<skill_content>",
    "A skill is a reusable",
    "AgentTeams task assignment",
    "You are a subagent",
)


def clean(text):
    t = text.replace("\r\n", "\n").strip()
    return t


def is_human(msg):
    src = msg.get("source") or {}
    if src.get("kind") != "user":
        return False
    content = msg.get("content") or []
    texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    if not texts:
        return False
    joined = "\n".join(texts)
    for m in INJECT_MARKERS:
        if m in joined:
            return False
    return True


def iter_sessions():
    for d in sorted(os.listdir(EXPORT)):
        full = os.path.join(EXPORT, d)
        if not os.path.isdir(full):
            continue
        for base, _dirs, files in os.walk(full):
            for fn in files:
                if fn.startswith("session") and fn.endswith(".jsonl"):
                    yield d, os.path.join(base, fn)


def main():
    index = []
    for sid, path in iter_sessions():
        rel = os.path.relpath(path, EXPORT).replace("\\", "/")
        tag = sid + "__" + rel.replace("/", "_").replace(".jsonl", "")
        out_lines = []
        n_user = 0
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("type") != "user/message":
                    continue
                data = rec.get("data") or {}
                if not is_human(data):
                    continue
                t = (rec.get("time") or 0) / 1000.0
                ts = datetime.fromtimestamp(t, CN).strftime("%Y-%m-%d %H:%M:%S") if t else "?"
                seq = rec.get("seq")
                content = data.get("content") or []
                text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
                n_user += 1
                out_lines.append("### [%s] seq=%s %s" % (tag, seq, ts))
                out_lines.append(clean(text))
                out_lines.append("")
        if n_user:
            op = os.path.join(OUT, tag + ".txt")
            with open(op, "w", encoding="utf-8") as fh:
                fh.write("\n".join(out_lines))
            index.append((tag, n_user, path))
            print("%-90s %4d msgs" % (tag, n_user))
    with open(os.path.join(OUT, "_index.txt"), "w", encoding="utf-8") as fh:
        for tag, n, path in index:
            fh.write("%s\t%d\t%s\n" % (tag, n, path))
    print("total sessions with human msgs:", len(index), "total msgs:", sum(i[1] for i in index))


if __name__ == "__main__":
    main()
