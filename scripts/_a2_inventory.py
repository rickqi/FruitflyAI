"""A2: dump per-session user-role message inventory (all source kinds) to .tmp/a2/_inventory.txt

Usage: python scripts/_a2_inventory.py
"""
import glob
import json
import os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, "export logs")
OUT = os.path.join(ROOT, ".tmp", "a2")
os.makedirs(OUT, exist_ok=True)
CN = timezone(timedelta(hours=8))


def main():
    lines = []
    for f in sorted(glob.glob(os.path.join(EXPORT, "**", "*.jsonl"), recursive=True)):
        rel = os.path.relpath(f, EXPORT).replace("\\", "/")
        lines.append("===== %s" % rel)
        n = 0
        for line in open(f, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("type") != "user/message":
                continue
            d = r.get("data") or {}
            src = d.get("source") or {}
            txt = " ".join(
                c.get("text", "") for c in (d.get("content") or []) if isinstance(c, dict) and c.get("type") == "text"
            )
            t = (r.get("time") or 0) / 1000.0
            ts = datetime.fromtimestamp(t, CN).strftime("%m-%d %H:%M") if t else "?"
            n += 1
            lines.append("%s | seq=%s | %s | %s | %s" % (ts, r.get("seq"), src.get("kind"), src.get("plugin") or "", txt.replace("\n", " ")[:400]))
        lines.append("(%d user/message records)" % n)
        lines.append("")
    with open(os.path.join(OUT, "_inventory.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote", os.path.join(OUT, "_inventory.txt"))


if __name__ == "__main__":
    main()
