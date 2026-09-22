#!/usr/bin/env python3
"""Comprehensive DSH session-log analyzer for Fly64 project (v3).

Walks every extracted session under .tmp/sessions_v3, parses both the
legacy (session.jsonl, v1/v2) and v3 (session.v3.jsonl) formats, and
extracts:

  * real user questions (source.kind == "user", not plugin-injected)
  * assistant text messages
  * tool call names + counts
  * file paths touched via edit / write / read tools
  * per-session time span and message counts

Outputs a JSON aggregate plus a human-readable markdown summary.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = r"D:\codes\flygym\.tmp\sessions_v3"
OUT_JSON = r"D:\codes\flygym\.tmp\sessions_v3_analysis.json"
OUT_MD = r"D:\codes\flygym\.tmp\sessions_v3_analysis.md"

# Sessions that are re-exports of the same conversation: keep the LARGEST.
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

# Short human labels for each session
LABELS = {
    "1f8fbe04": "S1 跨领域能力分析",
    "27ed0979": "S2 Mario 运动能力扩展",
    "38542b1c": "S3 视觉系统深度分析",
    "90dd512b": "S4 EVO 进化系统",
    "99cab60f": "S5 脑模型启动 + SM64",
    "b2eeed98": "S7 监控仪表板布局",
    "d983cef5": "S8 神经活动可视化",
    "ed4b8026": "S9 日志分析执行计划",
    "f953d3fd": "S10 FlyGym 集成 + Bridge",
    "fdb47617": "S11 技术文档生成",
    "71c21f6d": "S12 AgentTeams 执行",
}

TOOL_FILE_ARGS = {
    "edit": "file_path", "write": "file_path", "read": "file_path",
    "grep": "path", "glob": "path",
}

TOPIC_KEYWORDS = {
    "卡死/循环": ["stuck", "circle_loop", "micro_loop", "loop_score", "卡死", "打转", "循环"],
    "EVO 进化": ["evo", "evolution", "pattern", "fix_template", "fix_catalog", "auto-fix", "进化"],
    "视觉系统": ["vision", "retina", "emd", "visual", "视觉", "复眼", "光流", "optic"],
    "Coach/教官": ["coach", "教官", "llm", "glm", "advice", "active_strategy", "咨询"],
    "逃离/探索": ["escape", "explore", "coverage", "novelty", "逃离", "覆盖率", "探索"],
    "停滞/坠落": ["fallen", "fall", "ground", "坠落", "跌倒", "below_ground"],
    "CX 导航": ["cx", "central_complex", "compass", "anchor", "导航", "罗盘", "heading"],
    "蘑菇体/学习": ["mbon", "mushroom", "dopamine", "kc", "多巴胺", "蘑菇体", "学习"],
    "仪表板/UI": ["dashboard", "ui", "web", "仪表板", "面板", "layout"],
    "测试": ["test", "pytest", "测试", "assert", "regression"],
    "Bridge/启动": ["bridge", "sm64", "launch", "启动", "wsl", "seqlock"],
    "AgentTeams": ["agent_teams", "agentteams", "team", "captain", "团队"],
    "版本": ["version", "brain_version", "版本"],
    "文档": ["readme", "docs", "文档", "报告", "report"],
}


def extract_texts(content) -> str:
    """Pull plain text out of a DSH content block list (or string)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for blk in content:
        if isinstance(blk, dict):
            if blk.get("type") == "text" and blk.get("text"):
                parts.append(blk["text"])
        elif isinstance(blk, str):
            parts.append(blk)
    return "\n".join(parts)


def is_real_user_message(data: dict) -> bool:
    """Filter plugin/system injected messages; keep genuine human turns."""
    src = data.get("source") or {}
    kind = src.get("kind") if isinstance(src, dict) else None
    if kind == "user":
        return True
    # rpcId present == came from the Web UI client
    if data.get("rpcId"):
        return True
    return False


def analyze_file(path: str, sess: dict) -> None:
    """Parse one session jsonl file, accumulating into sess."""
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("type", "")
            data = rec.get("data") or {}
            ts = rec.get("time")
            if ts:
                if sess["first_ts"] is None or ts < sess["first_ts"]:
                    sess["first_ts"] = ts
                if sess["last_ts"] is None or ts > sess["last_ts"]:
                    sess["last_ts"] = ts

            sess["event_types"][t] += 1

            if t == "user/message":
                txt = extract_texts(data.get("content"))
                if not txt:
                    txt = data.get("text", "") or ""
                txt = txt.strip()
                if not txt:
                    continue
                if is_real_user_message(data):
                    sess["user_msgs"].append({"ts": ts, "text": txt})
                else:
                    sess["injected_msgs"] += 1

            elif t == "assistant/message":
                msg = data.get("message") or {}
                content = msg.get("content")
                txt = extract_texts(content)
                if txt.strip():
                    sess["assistant_msgs"] += 1
                    sess["assistant_chars"] += len(txt)

            elif t == "tool/call":
                name = data.get("name", "") or ""
                if name:
                    sess["tools"][name] += 1
                    sess["tool_calls"] += 1
                    # capture file paths
                    argk = TOOL_FILE_ARGS.get(name)
                    if argk:
                        raw = data.get("arguments")
                        fp = None
                        if isinstance(raw, str):
                            try:
                                parsed = json.loads(raw)
                                fp = parsed.get(argk)
                            except Exception:
                                m = re.search(r'"%s"\s*:\s*"([^"]+)"' % argk, raw)
                                if m:
                                    fp = m.group(1)
                        elif isinstance(raw, dict):
                            fp = raw.get(argk)
                        if fp:
                            sess["files"][fp] += 1


def main() -> None:
    sessions = {}
    entries = sorted(os.listdir(ROOT))
    for entry in entries:
        full = os.path.join(ROOT, entry)
        if not os.path.isdir(full):
            continue
        # map to canonical key
        key = None
        for k, canon in CANONICAL.items():
            if entry == canon:
                key = k
                break
        if key is None:
            continue  # duplicate re-export, skip
        sess = sessions.setdefault(key, {
            "key": key, "label": LABELS.get(key, key), "dirs": [],
            "user_msgs": [], "injected_msgs": 0, "assistant_msgs": 0,
            "assistant_chars": 0, "tool_calls": 0,
            "tools": Counter(), "files": Counter(), "event_types": Counter(),
            "first_ts": None, "last_ts": None,
        })
        sess["dirs"].append(entry)
        for root, _dirs, fnames in os.walk(full):
            for fn in fnames:
                if fn.endswith(".jsonl") and "session" in fn:
                    analyze_file(os.path.join(root, fn), sess)

    # ── aggregate ───────────────────────────────────────────────────────
    total_tools = Counter()
    total_files = Counter()
    topic_counts = Counter()
    out = []
    for key, s in sessions.items():
        total_tools.update(s["tools"])
        total_files.update(s["files"])
        blob = " ".join(m["text"] for m in s["user_msgs"]).lower()
        topics = []
        for topic, kws in TOPIC_KEYWORDS.items():
            hits = sum(blob.count(kw.lower()) for kw in kws)
            if hits:
                topics.append((topic, hits))
                topic_counts[topic] += hits
        topics.sort(key=lambda x: -x[1])
        out.append({
            "key": key,
            "label": s["label"],
            "dirs": s["dirs"],
            "user_msg_count": len(s["user_msgs"]),
            "injected_count": s["injected_msgs"],
            "assistant_msgs": s["assistant_msgs"],
            "tool_calls": s["tool_calls"],
            "first_ts": s["first_ts"],
            "last_ts": s["last_ts"],
            "top_topics": topics[:8],
            "top_tools": s["tools"].most_common(10),
            "top_files": s["files"].most_common(15),
            "user_msgs": [m["text"][:500] for m in s["user_msgs"]],
        })

    out.sort(key=lambda x: x["key"])
    result = {
        "sessions": out,
        "total_tools": total_tools.most_common(40),
        "total_files": total_files.most_common(50),
        "topic_totals": topic_counts.most_common(),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ── markdown summary ────────────────────────────────────────────────
    lines = ["# Fly64 Session 日志分析 v3", ""]
    lines.append("## 总览")
    lines.append("")
    lines.append("| Session | 用户问题 | 注入 | 助手消息 | 工具调用 |")
    lines.append("|---|---:|---:|---:|---:|")
    for s in out:
        lines.append("| %s | %d | %d | %d | %d |" % (
            s["label"], s["user_msg_count"], s["injected_count"],
            s["assistant_msgs"], s["tool_calls"]))
    lines.append("")
    lines.append("## 话题热度（按用户提问命中次数）")
    lines.append("")
    for topic, n in result["topic_totals"]:
        lines.append("- %s: %d" % (topic, n))
    lines.append("")
    lines.append("## 工具总调用")
    lines.append("")
    for name, n in result["total_tools"]:
        lines.append("- %s: %d" % (name, n))
    lines.append("")
    lines.append("## 各 Session 主题")
    for s in out:
        lines.append("")
        lines.append("### %s (%d 问题)" % (s["label"], s["user_msg_count"]))
        lines.append("")
        lines.append("Top topics: " + ", ".join("%s(%d)" % (t, n) for t, n in s["top_topics"]))
        lines.append("")
        lines.append("Top files: " + ", ".join(f for f, _ in s["top_files"][:8]))
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("wrote", OUT_JSON)
    print("wrote", OUT_MD)
    print()
    print("=== SESSION SUMMARY ===")
    for s in out:
        print("%-28s user=%-5d inject=%-4d asst=%-5d tools=%-6d" % (
            s["label"], s["user_msg_count"], s["injected_count"],
            s["assistant_msgs"], s["tool_calls"]))
    print()
    print("=== TOPIC TOTALS ===")
    for topic, n in result["topic_totals"]:
        print("  %-16s %d" % (topic, n))
    print()
    print("=== TOP TOOLS ===")
    for name, n in result["total_tools"][:20]:
        print("  %-28s %d" % (name, n))


if __name__ == "__main__":
    main()
