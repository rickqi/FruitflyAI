#!/usr/bin/env python3
"""
Extract NEW/updated DSH session exports (09-24 -> 09-26 window) into
.tmp/sessions-new/ WITHOUT touching .tmp/sessions/ (old sessions) or
.tmp/sessions_v3|v5/ (previous rounds' products).

Zip members may contain ':' (from sha256 media names), which is illegal on
Windows, so member names are sanitized (':' -> '_').

Usage:
    python scripts/extract_new_sessions.py
"""
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXPORT_DIR = os.path.join(ROOT, "export logs")
DEST = os.path.join(ROOT, ".tmp", "sessions-new")

# label -> zip filename (in export logs)
TARGETS = [
    ("99cab60f-latest", "dsh-session-session-99cab60f-fada-4a9e-9d10-ababdd0f4373.zip"),
    ("6c53f724-v1",     "dsh-session-session-6c53f724-fab1-4db1-b7d5-5d00fff36265.zip"),
    ("6c53f724-v2",     "dsh-session-session-6c53f724-fab1-4db1-b7d5-5d00fff36265 (1).zip"),
    ("6c53f724-v3",     "dsh-session-session-6c53f724-fab1-4db1-b7d5-5d00fff36265 (2).zip"),
    ("51f62457-v1",     "dsh-session-session-51f62457-87fc-458d-ba9d-7d117ca67156.zip"),
    ("51f62457-v2",     "dsh-session-session-51f62457-87fc-458d-ba9d-7d117ca67156 (1).zip"),
]


def sanitize(name: str) -> str:
    return name.replace(":", "_")


def extract_one(label: str, zip_name: str) -> dict:
    src = os.path.join(EXPORT_DIR, zip_name)
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    out_dir = os.path.join(DEST, label)
    os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(src) as z:
        members = z.namelist()
        written = 0
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = sanitize(info.filename)
            target = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.isfile(target) and os.path.getsize(target) == info.file_size:
                continue
            with z.open(info) as fsrc, open(target, "wb") as fdst:
                while True:
                    chunk = fsrc.read(1 << 20)
                    if not chunk:
                        break
                    fdst.write(chunk)
            written += 1

    mtime = os.path.getmtime(src)
    meta = {
        "label": label,
        "zipName": zip_name,
        "zipSizeBytes": os.path.getsize(src),
        "zipMtime": datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "zipMtimeEpoch": int(mtime * 1000),
        "zipMtimeLocal": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "members": len([m for m in members if not m.endswith("/")]),
        "subagentJsonls": len([m for m in members if m.startswith("subagents/") and m.endswith(".jsonl")]),
        "filesWritten": written,
        "extractDir": os.path.relpath(out_dir, ROOT).replace("\\", "/"),
        "topLevelJsonl": sorted({m for m in members if "/" not in m and m.endswith(".jsonl")}),
    }
    return meta


def main():
    metas = []
    for label, zip_name in TARGETS:
        m = extract_one(label, zip_name)
        metas.append(m)
        print(f"[ok] {label}: {m['members']} members, {m['subagentJsonls']} subagent jsonl, "
              f"{m['filesWritten']} extracted, top={m['topLevelJsonl']}")

    with open(os.path.join(DEST, "_extract_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=2)
    print(f"\nManifest -> {os.path.join(DEST, '_extract_manifest.json')}")
    return metas


if __name__ == "__main__":
    main()
