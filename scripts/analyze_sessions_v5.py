#!/usr/bin/env python3
"""Comprehensive DSH session-log analyzer — v5.

Builds on v3/v4 methodology: canonical (largest) export per session, real human
messages only, AgentTeams protocol noise removed, topic hit counts, tool usage,
and per-session time spans.
"""
from __future__ import annotations

import datetime
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"D:\codes\flygym\.tmp\sessions_v5"
OUT_JSON = r"D:\codes\flygym\.tmp\sessions_v5_analysis.json"

# canonical = the export with the most jsonl bytes per session id
CANONICAL = {
    "1f8fbe04": "1f8fbe04-52eb-4dc8-9b63-b0f497c48b23",
    "27ed0979": "27ed0979-15ec-4711-bd47-c8cf63b109b8",
    "38542b1c": "38542b1c-45e7-4c96-b615-94875cd2bd0e",
    "71c21f6d": "71c21f6d-cb76-4baf-9afb-822765a043e4",           # 51.2 MB (was 9.0/3.5)
    "90dd512b": "90dd512b-6955-4848-9216-3c3c94c35b41",
    "99cab60f": "99cab60f-fada-4a9e-9d10-ababdd0f4373 (3)",
    "b2eeed98": "b2eeed98-1614-4a9b-846f-058bde87f475 (2)",       # 19.5 MB
    "d983cef5": "d983cef5-3f9c-4b97-9eac-820390a38bbd",
    "ed4b8026": "ed4b8026-6bfe-40ee-9be8-b5fb3b59e612",
    "f953d3fd": "f953d3fd-dcea-430f-9bee-461b8d73943e",
    "fdb47617": "fdb47617-7c9a-46b3-8cc0-80588409602c",
}
LABELS = {
    "1f8fbe04": "S1 跨领域能力分析",
    "27ed0979": "S2 Mario 运动能力扩展",
    "38542b1c": "S3 视觉系统深度分析",
    "71c21f6d": "S12 AgentTeams 执行（含 P0/P1 团队）",
    "90dd512b": "S4 EVO 进化系统",
    "99cab60f": "S5 脑模型启动 + SM64（最新）",
    "b2eeed98": "S7 监控仪表板 / 教练链",
    "d983cef5": "S8 神经活动可视化",
    "ed4b8026": "S9 日志分析执行计划",
    "f953d3fd": "S10 FlyGym 集成 + Bridge",
    "fdb47617": "S11 技术文档生成",
}
NOISE_RE = re.compile(
    r"AgentTeams automatic task assignment from the shared task list"
    r"|You have joined the team"
    r"|Wait for an automatic assignment or a captain message")
TOOL_FILE_ARGS = {"edit": "file_path", "write": "file_path", "read": "file_path",
                  "grep": "path", "glob": "path"}
TOPICS = {
    "运行环境/桥接/SM64": ["bridge", "sm64", "wsl", "启动", "显示", "frozen", "窗口"],
    "Coach/教官": ["coach", "教官", "glm", "advice", "active_strategy", "教练"],
    "EVO 进化": ["evo", "evolution", "pattern", "fix_template", "进化", "auto-fix"],
    "运动质量（卡死/转圈/动作）": ["stuck", "circle_loop", "micro_loop", "loop_score",
                          "卡死", "转圈", "循环", "动作", "oscillat"],
    "视觉系统": ["vision", "retina", "emd", "视觉", "复眼", "光流", "optic"],
    "探索/逃离/覆盖": ["escape", "explore", "coverage", "novelty", "探索", "覆盖率", "逃离"],
    "参数/钳位/注册表": ["clamp", "钳位", "参数", "registry", "tunable", "turn_bias", "wired"],
    "仪表板/UI/轨迹": ["dashboard", "仪表板", "面板", "trajectory", "轨迹", "监控"],
    "测试/门禁/基线": ["pytest", "test", "测试", "regression", "基线", "baseline", "守卫"],
    "AgentTeams/团队": ["agent_teams", "agentteams", "captain", "团队"],
    "版本/发布": ["version", "版本", "brain_version", "发布"],
    "文档/报告": ["readme", "docs", "文档", "报告", "report"],
}


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
            parts.append(b["text"])
        elif isinstance(b, str):
            parts.append(b)
    return "\n".join(parts)


def main() -> None:
    sessions = {}
    for key, dirname in CANONICAL.items():
        full = os.path.join(ROOT, dirname)
        if not os.path.isdir(full):
            print("MISSING", dirname)
            continue
        s = sessions.setdefault(key, {
            "key": key, "label": LABELS[key], "all_user": [], "real_user": [],
            "asst": 0, "tools": Counter(), "files": Counter(),
            "first": None, "last": None,
        })
        for root, _d, files in os.walk(full):
            for fn in files:
                if not (fn.endswith(".jsonl") and "session" in fn):
                    continue
                fh = open(os.path.join(root, fn), encoding="utf-8", errors="replace")
                with fh:
                    for line in fh:
                        ts = None
                        m = re.search(r'"time":(\d{13})', line)
                        if m:
                            ts = int(m.group(1))
                        if '"user/message"' in line:
                            try:
                                rec = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if rec.get("type") != "user/message":
                                continue
                            d = rec.get("data") or {}
                            src = d.get("source") or {}
                            if not (isinstance(src, dict) and
                                    (src.get("kind") == "user" or d.get("rpcId"))):
                                continue
                            txt = extract_text(d.get("content"))
                            if not txt.strip():
                                continue
                            s["all_user"].append(txt)
                            if not NOISE_RE.search(txt):
                                s["real_user"].append(txt)
                            if ts:
                                s["first"] = ts if s["first"] is None else min(s["first"], ts)
                                s["last"] = ts if s["last"] is None else max(s["last"], ts)
                        elif '"tool/call"' in line:
                            try:
                                rec = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if rec.get("type") != "tool/call":
                                continue
                            d = rec.get("data") or {}
                            nm = d.get("name") or ""
                            if nm:
                                s["tools"][nm] += 1
                            ak = TOOL_FILE_ARGS.get(nm)
                            if ak:
                                raw = d.get("arguments")
                                fp = None
                                if isinstance(raw, str):
                                    mm = re.search(r'"%s"\s*:\s*"([^"]+)"' % ak, raw)
                                    fp = mm.group(1) if mm else None
                                elif isinstance(raw, dict):
                                    fp = raw.get(ak)
                                if fp:
                                    s["files"][fp] += 1
                        elif '"assistant/message"' in line:
                            s["asst"] += 1

    total_tools = Counter()
    topic_totals = Counter()
    out = []
    for key, s in sessions.items():
        total_tools.update(s["tools"])
        blob = " ".join(s["real_user"]).lower()
        tops = []
        for t, kws in TOPICS.items():
            h = sum(blob.count(k.lower()) for k in kws)
            if h:
                tops.append([t, h])
                topic_totals[t] += h
        tops.sort(key=lambda x: -x[1])
        out.append({
            "key": key, "label": s["label"],
            "all": len(s["all_user"]), "real": len(s["real_user"]),
            "noise": len(s["all_user"]) - len(s["real_user"]),
            "asst": s["asst"], "tools": sum(s["tools"].values()),
            "first": s["first"], "last": s["last"],
            "topics": tops[:8],
            "top_files": s["files"].most_common(10),
            "real_msgs": s["real_user"],
        })
    out.sort(key=lambda x: x["key"])

    json.dump({"sessions": out,
               "total_tools": total_tools.most_common(30),
               "topic_totals": topic_totals.most_common()},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def dt(v):
        return datetime.datetime.fromtimestamp(v / 1000).strftime("%m-%d %H:%M") if v else "?"

    print("=== SESSION SUMMARY (canonical, noise-removed) ===")
    print("%-34s %6s %6s %6s %8s  %s -> %s" %
          ("SESSION", "USER", "noise", "REAL", "TOOLS", "FIRST", "LAST"))
    ta = tr = tn = 0
    for s in out:
        ta += s["all"]; tr += s["real"]; tn += s["noise"]
        print("%-34s %6d %6d %6d %8d  %s -> %s" %
              (s["label"][:34], s["all"], s["noise"], s["real"], s["tools"],
               dt(s["first"]), dt(s["last"])))
    print("%-34s %6d %6d %6d" % ("TOTAL", ta, tn, tr))
    print()
    print("=== TOPIC TOTALS (noise-removed) ===")
    for t, n in topic_totals.most_common():
        print("  %-28s %d" % (t, n))
    print()
    print("=== TOP TOOLS ===")
    for t, n in total_tools.most_common(18):
        print("  %-30s %d" % (t, n))
    print()
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
