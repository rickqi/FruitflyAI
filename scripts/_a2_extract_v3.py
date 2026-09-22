"""A2 (rev 2): extract REAL user messages from the AUTHORITATIVE corpus.

The first A2 run read ``export logs/_extracted_*/`` — a STALE partial unpack
(9 sessions; the 38542b1c / f953d3fd directories are empty leftovers).  The
authoritative corpus is ``.tmp/sessions_v3/`` (16 re-export dirs, 11 unique
sessions, ~351 MB), which the captain re-unpacked from the 16 zips.

This script uses the same 11-session CANONICAL dedupe as
``scripts/analyze_sessions_v3.py`` so counts are comparable, and applies the
same "real human message" filter as ``scripts/_a2_extract_user_msgs.py``
(source.kind == "user" minus injected snapshot markers).

Usage: python scripts/_a2_extract_v3.py
"""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, ".tmp", "sessions_v3")
OUT = os.path.join(ROOT, ".tmp", "a2")
os.makedirs(OUT, exist_ok=True)
CN = timezone(timedelta(hours=8))

#: Same canonical map as scripts/analyze_sessions_v3.py — one dir per session,
#: chosen as the LARGEST re-export.
CANONICAL = {
    "1f8fbe04": "1f8fbe04-52eb-4dc8-9b63-b0f497c48b23",
    "27ed0979": "27ed0979-15ec-4711-bd47-c8cf63b109b8",
    "38542b1c": "38542b1c-45e7-4c96-b615-94875cd2bd0e",
    "71c21f6d": "71c21f6d-cb76-4baf-9afb-822765a043e4 (1)",
    "90dd512b": "90dd512b-6955-4848-9216-3c3c94c35b41",
    "99cab60f": "99cab60f-fada-4a9e-9d10-ababdd0f4373 (3)",
    "b2eeed98": "b2eeed98-1614-4a9b-846f-058bde87f475",
    "d983cef5": "d983cef5-3f9c-4b97-9eac-820390a38bbd",
    "ed4b8026": "ed4b8026-6bfe-40ee-9be8-b5fb3b59e612",
    "f953d3fd": "f953d3fd-dcea-430f-9bee-461b8d73943e",
    "fdb47617": "fdb47617-7c9a-46b3-8cc0-80588409602c",
}

LABELS = {
    "1f8fbe04": "S1 跨领域能力分析", "27ed0979": "S2 Mario 运动能力扩展",
    "38542b1c": "S3 视觉系统深度分析", "90dd512b": "S4 EVO 进化系统",
    "99cab60f": "S5 脑模型启动 + SM64", "b2eeed98": "S7 监控仪表板布局",
    "d983cef5": "S8 神经活动可视化", "ed4b8026": "S9 日志分析执行计划",
    "f953d3fd": "S10 FlyGym 集成 + Bridge", "fdb47617": "S11 技术文档生成",
    "71c21f6d": "S12 AgentTeams 执行",
}

INJECT_MARKERS = (
    "Current runtime context.", "<system-reminder>",
    "AgentTeams automatic task assignment", "Team goal:",
    "You are an AgentTeams member", "Profile protocol:", "Working rules:",
    "<skill_content>", "A skill is a reusable", "AgentTeams task assignment",
    "You are a subagent",
)


def texts_of(data):
    out = []
    for blk in (data.get("content") or []):
        if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text"):
            out.append(blk["text"])
    return "\n".join(out)


def main():
    index = []
    for key, dirname in CANONICAL.items():
        full = os.path.join(CORPUS, dirname)
        if not os.path.isdir(full):
            print("MISSING", dirname)
            continue
        rows = []
        for root, _d, fnames in os.walk(full):
            for fn in sorted(fnames):
                if not (fn.endswith(".jsonl") and "session" in fn):
                    continue
                for line in io.open(os.path.join(root, fn), encoding="utf-8", errors="replace"):
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
                    src = data.get("source") or {}
                    if src.get("kind") != "user":
                        continue
                    txt = texts_of(data).strip()
                    if not txt:
                        continue
                    if any(m in txt for m in INJECT_MARKERS):
                        continue
                    t = (rec.get("time") or 0) / 1000.0
                    rows.append((t, rec.get("seq"), txt))
        rows.sort(key=lambda r: (r[0] == 0, r[0]))
        op = os.path.join(OUT, "v3_%s_%s.txt" % (key, LABELS[key].split()[0]))
        with io.open(op, "w", encoding="utf-8") as fh:
            for t, seq, txt in rows:
                ts = datetime.fromtimestamp(t, CN).strftime("%m-%d %H:%M") if t else "?"
                fh.write("### %s seq=%s\n%s\n\n" % (ts, seq, txt))
        span = "?"
        if rows:
            span = "%s -> %s" % (
                datetime.fromtimestamp(rows[0][0], CN).strftime("%m-%d %H:%M"),
                datetime.fromtimestamp(rows[-1][0], CN).strftime("%m-%d %H:%M"))
        index.append((key, LABELS[key], len(rows), span))
        print("%-9s %-24s %4d   %s" % (key, LABELS[key], len(rows), span))
    # write a single merged chronological file for cross-session search
    merged = []
    for key, _lbl, _n, _s in index:
        p = os.path.join(OUT, "v3_%s_%s.txt" % (key, LABELS[key].split()[0]))
        if not os.path.exists(p):
            continue
        body = io.open(p, encoding="utf-8").read()
        for chunk in body.split("### ")[1:]:
            head, _, rest = chunk.partition("\n")
            merged.append((head.strip(), key, rest.strip()))
    merged.sort(key=lambda r: r[0])
    with io.open(os.path.join(OUT, "v3_merged_user_msgs.txt"), "w", encoding="utf-8") as fh:
        for head, key, body in merged:
            fh.write("[%s] %s\n%s\n\n" % (key, head, body))
    with io.open(os.path.join(OUT, "v3_index.txt"), "w", encoding="utf-8") as fh:
        for key, lbl, n, span in index:
            fh.write("%s\t%s\t%d\t%s\n" % (key, lbl, n, span))
    print("\nTOTAL real user messages: %d across %d sessions" % (
        sum(i[2] for i in index), len(index)))


if __name__ == "__main__":
    main()
