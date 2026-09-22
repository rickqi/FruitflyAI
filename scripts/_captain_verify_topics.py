#!/usr/bin/env python3
"""Captain verification: topic counts with and without AgentTeams protocol noise."""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r".tmp\sessions_v3"
CANON = {
    "1f8fbe04-52eb-4dc8-9b63-b0f497c48b23",
    "27ed0979-15ec-4711-bd47-c8cf63b109b8",
    "38542b1c-45e7-4c96-b615-94875cd2bd0e",
    "71c21f6d-cb76-4baf-9afb-822765a043e4 (1)",
    "90dd512b-6955-4848-9216-3c3c94c35b41",
    "99cab60f-fada-4a9e-9d10-ababdd0f4373 (3)",
    "b2eeed98-1614-4a9b-846f-058bde87f475 (1)",   # larger export
    "d983cef5-3f9c-4b97-9eac-820390a38bbd",
    "ed4b8026-6bfe-40ee-9be8-b5fb3b59e612",
    "f953d3fd-dcea-430f-9bee-461b8d73943e",
    "fdb47617-7c9a-46b3-8cc0-80588409602c",
}
NOISE_RE = re.compile(
    r"AgentTeams automatic task assignment from the shared task list"
    r"|You have joined the team"
    r"|Wait for an automatic assignment or a captain message")

TOPICS = {
    "AgentTeams(团队/编排)": ["agent_teams", "agentteams", "captain", "团队", "team"],
    "Coach/教官": ["coach", "教官", "glm", "advice", "active_strategy"],
    "卡死/循环/运动质量": ["stuck", "circle_loop", "micro_loop", "loop_score", "卡死", "转圈", "循环", "动作"],
    "EVO 进化": ["evo", "evolution", "pattern", "fix_template", "进化"],
    "视觉系统": ["vision", "retina", "emd", "视觉", "复眼", "光流"],
    "探索/逃离/覆盖": ["escape", "explore", "coverage", "novelty", "探索", "覆盖率", "逃离"],
    "Bridge/启动/SM64": ["bridge", "sm64", "启动", "wsl", "显示"],
    "仪表板/UI/轨迹": ["dashboard", "仪表板", "面板", "trajectory", "轨迹", "监控"],
}

msgs = []
for entry in sorted(os.listdir(ROOT)):
    if entry not in CANON:
        continue
    full = os.path.join(ROOT, entry)
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
                        msgs.append(txt)

real = [m for m in msgs if not NOISE_RE.search(m)]
print("canonical user msgs (all)  = %d" % len(msgs))
print("canonical user msgs (real) = %d" % len(real))
print()
print("=== Topic hit counts: ALL vs REAL ===")
print("%-26s %8s %8s" % ("TOPIC", "ALL", "REAL"))
for topic, kws in TOPICS.items():
    a = sum(sum(m.lower().count(k.lower()) for k in kws) for m in msgs)
    r = sum(sum(m.lower().count(k.lower()) for k in kws) for m in real)
    print("%-26s %8d %8d" % (topic, a, r))
print()
# Real "task not executed" complaints
pat = re.compile(r"任务没有执行|任务未执行|未启动|为什么没有执行|依然未启动|任务为什么没有")
hits = [m for m in real if pat.search(m)]
print('=== genuine "task not executed" complaints ===')
print("count = %d" % len(hits))
for h in hits:
    print("  - %s" % h[:110].replace("\n", " "))
