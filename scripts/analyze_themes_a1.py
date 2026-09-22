#!/usr/bin/env python3
"""A1 theme-mainline analyzer for Fly64 session logs — v2 (independent of v3).

Adds over v1 of this script:
  * utterance-type axis: 真问句 / 诊断指令 / 续作指令 / 粘贴回流(agent 文本被贴回)
  * 4-group taxonomy (产品行为 / 工程平台 / 交付协作 / 知识战略)
  * concurrency: how many side conversations were active on the same day
  * gap analysis inside a session (>=2h silence = a new work block)
  * export-diff: exactly which questions the smaller re-export dropped
  * representative verbatim quotes per mainline

Outputs -> .tmp/a1_themes/{questions.json,quant.json,quant.md,quotes.md}
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

ROOT = r"D:\codes\flygym\.tmp\sessions_v3"
OUT_DIR = r"D:\codes\flygym\.tmp\a1_themes"
CST = timezone(timedelta(hours=8))
INJ_KINDS = Counter()

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

# (id, name, group, patterns)
MAINLINES = [
    # ── 产品行为：让"果蝇脑驱动的马里奥"表现更好 ──────────────────
    ("P1", "运动质量：不卡死、不转圈、真能动", "product", [
        r"(?<![a-z])circle_loop", r"micro_loop", r"loop_score", r"(?<![a-z])stuck",
        r"打转", r"转圈", r"转小圈", r"原地", r"卡死", r"卡住", r"僵住", r"(?<![a-z])frozen",
        r"震颤", r"抖动", r"不动", r"(?<![a-z])jump", r"跳", r"动作单调", r"运动", r"移动",
        r"位移", r"(?<![a-z])motion", r"(?<![a-z])motor", r"locomot", r"(?<![a-z])weave",
        r"(?<![a-z])ramp", r"速度",
    ]),
    ("P2", "探索与脱困：覆盖率、逃离率、路径多样性", "product", [
        r"(?<![a-z])escape", r"(?<![a-z])explor", r"coverage", r"覆盖率", r"脱困", r"逃离",
        r"逃逸", r"探索", r"novelty", r"frontier", r"(?<![a-z])novel", r"路径重复", r"重复路径",
        r"开拓", r"(?<![a-z])frontier", r"网格", r"(?<![a-z])grid",
    ]),
    ("P3", "Coach/LLM 教官闭环：建议能否真正改变行为", "product", [
        r"(?<![a-z])coach", r"教官", r"(?<![a-z])glm", r"active_strategy", r"(?<![a-z])advis",
        r"建议", r"咨询", r"求助", r"(?<![a-z])seek[_-]?help", r"(?<![a-z])snapshot", r"截屏",
        r"截图", r"(?<![a-z])consult", r"(?<![a-z])sos", r"对话", r"(?<![a-z])llm",
    ]),
    ("P4", "EVO 自我进化闭环：修复能否真正落地", "product", [
        r"(?<![a-z])evo(?![a-z])", r"evolution", r"进化", r"fix_template", r"fix_catalog",
        r"auto[_-]?fix", r"自愈", r"自进化", r"闭环", r"自我迭代", r"(?<![a-z])pattern",
    ]),
    ("P5", "视觉与感知：复眼、光流、语义识别", "product", [
        r"(?<![a-z])vision", r"(?<![a-z])retina", r"(?<![a-z])emd(?![a-z])", r"visual",
        r"视觉", r"复眼", r"光流", r"(?<![a-z])optic", r"颜色", r"(?<![a-z])uv(?![a-z])",
        r"感知", r"(?<![a-z])ocr(?![a-z])", r"语义", r"小目标", r"(?<![a-z])scene", r"场景",
        r"扇区", r"视场", r"眼", r"图像", r"(?<![a-z])frame", r"像素",
    ]),
    ("P6", "导航与空间记忆：CX 罗盘、锚点、路径", "product", [
        r"(?<![a-z])cx(?![a-z])", r"central_complex", r"compass", r"(?<![a-z])anchor",
        r"heading", r"导航", r"罗盘", r"方位", r"朝向", r"(?<![a-z])imu", r"记忆",
        r"(?<![a-z])memory", r"空间", r"地图", r"寻路", r"目标点", r"(?<![a-z])landmark",
        r"地标", r"路径",
    ]),
    ("P7", "脑模型与神经学习机制：MBON、多巴胺、LIF", "product", [
        r"(?<![a-z])mbon", r"mushroom", r"dopamine", r"(?<![a-z])kc(?![a-z])", r"多巴胺",
        r"蘑菇体", r"神经元", r"(?<![a-z])lif(?![a-z])", r"学习率", r"可塑性", r"plastic",
        r"突触", r"reward", r"奖惩", r"奖励", r"惩罚", r"脑模型", r"(?<![a-z])brain",
        r"神经", r"(?<![a-z])cns", r"反射",
    ]),
    # ── 工程平台：让上面这条链路跑得起来 ──────────────────────────
    ("E1", "可观测性：仪表板、轨迹图、神经可视化", "platform", [
        r"dashboard", r"仪表板", r"面板", r"(?<![a-z])web(?![a-z])", r"(?<![a-z])html",
        r"trajectory", r"轨迹", r"可视化", r"监控", r"图表", r"曲线", r"(?<![a-z])ui(?![a-z])",
        r"显示", r"布局", r"页面", r"播放", r"缩略图", r"前端", r"画", r"线框",
    ]),
    ("E2", "运行环境与桥接：SM64 启动、WSL、显示、服务可用性", "platform", [
        r"(?<![a-z])bridge", r"(?<![a-z])sm64", r"(?<![a-z])wsl", r"(?<![a-z])wslg", r"窗口",
        r"(?<![a-z])xvfb", r"seqlock", r"游戏", r"(?<![a-z])rom(?![a-z])", r"模拟器", r"进程",
        r"重启", r"启动", r"服务", r"端口", r"8765", r"访问", r"无法访问", r"(?<![a-z])404",
        r"报错", r"(?<![a-z])error", r"(?<![a-z])gpu", r"实机", r"部署",
    ]),
    ("E3", "工程治理：参数契约、测试回归、代码缺陷审计", "platform", [
        r"(?<![a-z])test", r"pytest", r"测试", r"(?<![a-z])assert", r"回归", r"参数",
        r"(?<![a-z])param", r"契约", r"(?<![a-z])parity", r"一致性", r"(?<![a-z])lint", r"重构",
        r"(?<![a-z])wired", r"接线", r"缺陷", r"(?<![a-z])bug", r"审计", r"magic number",
        r"死参数", r"代码检查", r"覆盖率", r"(?<![a-z])ci(?![a-z])", r"质量",
    ]),
    # ── 交付与协作 ───────────────────────────────────────────────
    ("D1", "交付纪律：变更说明、提交推送、版本号", "delivery", [
        r"变更说明", r"提交", r"推送", r"(?<![a-z])git", r"(?<![a-z])commit", r"脱敏",
        r"门禁", r"版本号", r"(?<![a-z])release", r"发布", r"(?<![a-z])push",
    ]),
    ("D2", "Skill 系统与自治服务：技能标准、常驻闭环", "delivery", [
        r"(?<![a-z])skill", r"技能", r"自治", r"常驻", r"值守", r"定时", r"调度器", r"看门狗",
    ]),
    ("D3", "AgentTeams 编排与任务执行", "delivery", [
        r"agent[_-]?teams", r"agentteams", r"(?<![a-z])team(?![a-z])", r"团队", r"captain",
        r"队长", r"调度", r"任务没有执行", r"任务未执行", r"成员", r"(?<![a-z])subagent",
        r"派发", r"并行", r"任务",
    ]),
    # ── 知识战略 ─────────────────────────────────────────────────
    ("K1", "知识沉淀：报告、README、指南", "knowledge", [
        r"(?<![a-z])readme", r"(?<![a-z])docs?(?![a-z])", r"文档", r"报告", r"指南",
        r"(?<![a-z])guide", r"白皮书", r"总结", r"ppt", r"演示", r"(?<![a-z])agent\.md",
        r"记录",
    ]),
    ("K2", "跨领域迁移与商业化：保险核保、产品化", "knowledge", [
        r"保险", r"理赔", r"核保", r"跨领域", r"迁移", r"商业化", r"产品化", r"市场",
        r"robomaster", r"质检", r"领域", r"能力边界", r"(?<![a-z])business",
    ]),
]

GROUP_NAME = {
    "product": "产品行为（生物能力）",
    "platform": "工程平台（运行支撑）",
    "delivery": "交付与协作",
    "knowledge": "知识与战略",
}
GROUP_ORDER = ["product", "platform", "delivery", "knowledge"]
ML_ORDER = [m[0] for m in MAINLINES]
ML_NAME = {m[0]: m[1] for m in MAINLINES}
ML_GROUP = {m[0]: m[2] for m in MAINLINES}
ML_PAT = {m[0]: [re.compile(p, re.I) for p in m[3]] for m in MAINLINES}

# ── utterance-type rules ────────────────────────────────────────────────
DIRECTIVE_EXACT = {
    "继续", "继续。", "执行", "修复", "开始", "实施", "推送", "提交", "要", "是", "好", "需要",
    "实现", "改进", "记录", "显示进化就", "下一步", "检查状态", "确认", "可以", "对", "嗯",
    "记录", "提交推送", "推送。", "继续修复", "继续执行", "开始。", "先a", "先b", "先c",
    "继续推进", "执行。", "实施。", "全面深入分析", "所有", "记录", "重试", "再试",
}
RE_QUESTION = re.compile(
    r"为什么|为何|如何|是否|吗[？?。]?$|什么|哪些|怎么|能不能|可否|是不是|多少|"
    r"(?<![a-z])(why|how|what|which)\b|[？?]")
RE_MD = re.compile(r"\*\*|\|.*\||^#|^\s*[-*]\s|✅|🔴|🟡|📋|🎯|⚠️|<summary>|```")


def utterance_type(txt: str) -> str:
    t = txt.strip()
    if t in DIRECTIVE_EXACT or (len(t) <= 6 and re.fullmatch(r"[\u4e00-\u9fa5A-Za-z0-9]{1,6}", t)):
        return "续作指令"
    if RE_QUESTION.search(t):
        return "真问句"
    if len(t) > 120 and len(RE_MD.findall(t)) >= 2:
        return "粘贴回流"
    if RE_MD.search(t) and len(t) > 200:
        return "粘贴回流"
    return "陈述/指令"


def is_paste_back(txt: str) -> bool:
    return len(txt) > 120 and len(RE_MD.findall(txt)) >= 2


def extract_texts(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text")


def is_real_user_message(data: dict) -> bool:
    src = data.get("source") or {}
    kind = src.get("kind") if isinstance(src, dict) else None
    if kind == "user":
        return True
    if data.get("rpcId"):
        return True
    return False


AUTO_MARKERS = ("AgentTeams automatic task assignment",
                "You are executing as configured member")

# AgentTeams membership notices are injected as user-role turns but are not
# human input at all (81 occurrences, ~33% of all user-message characters).
TEAM_JOIN_RE = re.compile(r"You have joined the team .*?as a member", re.S)


def is_auto_dispatch(txt: str) -> bool:
    if TEAM_JOIN_RE.search(txt):
        return True
    return any(mk in txt for mk in AUTO_MARKERS)


def dstr(ts):
    return datetime.fromtimestamp(ts / 1000.0, CST).strftime("%Y-%m-%d") if ts else ""


def hstr(ts):
    return datetime.fromtimestamp(ts / 1000.0, CST).strftime("%m-%d %H:%M") if ts else ""


def classify(txt):
    hits = {}
    for mid, _n, _g, _p in MAINLINES:
        n = 0
        for rx in ML_PAT[mid]:
            n += len(rx.findall(txt))
        if n:
            hits[mid] = n
    return hits


def norm_key(txt):
    t = txt.lower()
    t = re.sub(r"[\s\u3000]+", "", t)
    t = re.sub(r"[，。！？、,.!?;:：；\"'“”‘’()（）\[\]【】<>《》/\\|*`~\-_+=%$#@^&]+", "", t)
    t = re.sub(r"\d+", "#", t)
    return t


def scan(path):
    """Return (real questions, injected count, auto count)."""
    qs, inj, auto = [], 0, 0
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return qs, 0, 0
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "user/message":
                continue
            data = rec.get("data") or {}
            src = data.get("source") if isinstance(data.get("source"), dict) else {}
            txt = (extract_texts(data.get("content")) or data.get("text") or "").strip()
            if not txt:
                continue
            if src.get("kind") != "user":
                inj += 1
                INJ_KINDS["kind=" + str(src.get("kind") or "none")] += 1
                continue
            if is_auto_dispatch(txt):
                auto += 1
                continue
            qs.append({"ts": rec.get("time"), "text": txt, "file": path,
                       "rpc": bool(src.get("rpcId"))})
    return qs, inj, auto


def scan_dir(full):
    files = []
    for root, _d, fnames in os.walk(full):
        for fn in fnames:
            if fn.endswith(".jsonl") and "session" in fn:
                files.append(os.path.join(root, fn))
    files.sort()
    qs, inj, auto, perfile = [], 0, 0, []
    for p in files:
        f_qs, f_inj, f_auto = scan(p)
        qs.extend(f_qs)
        inj += f_inj
        auto += f_auto
        perfile.append({"file": os.path.relpath(p, full).replace("\\", "/"),
                        "real": len(f_qs), "injected": f_inj, "auto": f_auto})
    return {"q": qs, "inj": inj, "auto": auto, "files": perfile}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    by_key = defaultdict(list)
    for entry in sorted(os.listdir(ROOT)):
        full = os.path.join(ROOT, entry)
        if not os.path.isdir(full):
            continue
        key = entry.split("-")[0].split(" ")[0]
        if key in LABELS:
            by_key[key].append(entry)

    dup_report, chosen = [], {}
    for key, dirs in sorted(by_key.items()):
        variants = []
        for d in dirs:
            INJ_KINDS.clear()
            st = scan_dir(os.path.join(ROOT, d))
            variants.append({"dir": d, "n": len(st["q"]), "keys": [norm_key(q["text"]) for q in st["q"]],
                             "st": st, "kinds": dict(INJ_KINDS)})
        base = max(variants, key=lambda v: v["n"])
        superset = all(set(v["keys"]).issubset(set(base["keys"])) for v in variants)
        # what did the SMALLER export drop?
        dropped = []
        for v in variants:
            if v is base:
                continue
            b = Counter(base["keys"])
            for k in v["keys"]:
                b[k] -= 1
            dropped += [k for k in v["keys"] if b[k] < 0]
            # keys present in base but not in this variant
            vb = set(v["keys"])
            dropped += [k for k in base["keys"] if k not in vb]
        dup_report.append({
            "key": key, "label": LABELS[key],
            "variants": [{"dir": v["dir"], "questions": v["n"], "injected": v["st"]["inj"],
                          "auto": v["st"]["auto"]} for v in variants],
            "chosen": base["dir"], "max_questions": base["n"],
            "smaller_are_subsets": superset,
            "dropped_keys": dropped[:40],
        })
        chosen[key] = base

    INJ_KINDS.clear()
    for key, v in chosen.items():
        for k, n in v["kinds"].items():
            INJ_KINDS[k] += n

    all_q = []
    per_session = {}
    for key, v in chosen.items():
        st = v["st"]
        qs_sorted = sorted(st["q"], key=lambda q: (q["ts"] or 0))
        sess_q = []
        for i, q in enumerate(qs_sorted, 1):
            hits = classify(q["text"])
            sess_q.append({
                "session": key, "label": LABELS[key], "idx": i, "ts": q["ts"],
                "date": dstr(q["ts"]), "time": hstr(q["ts"]), "text": q["text"],
                "hits": hits, "n_hits": len(hits), "chars": len(q["text"]),
                "utype": utterance_type(q["text"]),
                "paste_back": is_paste_back(q["text"]),
                "rpc": q.get("rpc", False),
            })
        per_session[key] = sess_q
        all_q.extend(sess_q)

    all_q.sort(key=lambda q: (q["ts"] or 0))
    for i, q in enumerate(all_q, 1):
        q["gidx"] = i

    # ── aggregates ──────────────────────────────────────────────────────
    ml_q, ml_hits = Counter(), Counter()
    ml_first, ml_last = {}, {}
    ml_days, ml_sess = defaultdict(Counter), defaultdict(Counter)
    group_q = Counter()
    group_cov = Counter()
    prim_days = defaultdict(Counter)
    utype_q = Counter()
    day_total = Counter()
    multi = Counter()
    sess_day = defaultdict(Counter)
    hour_hist = Counter()

    for q in all_q:
        d = q["date"]
        day_total[d] += 1
        sess_day[q["session"]][d] += 1
        multi[q["n_hits"]] += 1
        utype_q[q["utype"]] += 1
        if q["ts"]:
            hour_hist[hstr(q["ts"])[:5].split(" ")[-1][:2]] += 1
        for mid, n in q["hits"].items():
            ml_q[mid] += 1
            ml_hits[mid] += n
            ml_days[mid][d] += 1
            ml_sess[mid][q["session"]] += 1
            t = q["ts"]
            if t:
                ml_first[mid] = min(ml_first.get(mid, t), t)
                ml_last[mid] = max(ml_last.get(mid, t), t)
        # primary mainline = the one with most keyword hits (tie -> ML_ORDER)
        if q["hits"]:
            q["primary"] = max(q["hits"].items(),
                               key=lambda kv: (kv[1], -ML_ORDER.index(kv[0])))[0]
            for g in set(ML_GROUP[m] for m in q["hits"]):
                group_cov[g] += 1
            group_q[ML_GROUP[q["primary"]]] += 1
        else:
            q["primary"] = ""
            group_q["unclassified"] += 1
            group_cov["unclassified"] += 1
        prim_days[q["date"]][q["primary"] or "UNCL"] += 1

    # per-session table
    sess_table = []
    for key in sorted(per_session, key=lambda k: min((q["ts"] or 0) for q in per_session[k])):
        qs = per_session[key]
        tss = [q["ts"] for q in qs if q["ts"]]
        cov = Counter()
        for q in qs:
            for mid in q["hits"]:
                cov[mid] += 1
        # contiguous work blocks: gap >= 2h starts a new block
        blocks, prev = 0, None
        gaps = []
        for t in sorted(tss):
            if prev is not None:
                if t - prev >= 2 * 3600 * 1000:
                    blocks += 1
                    gaps.append(round((t - prev) / 3600000.0, 1))
            prev = t
        sess_table.append({
            "key": key, "label": LABELS[key], "questions": len(qs),
            "first": dstr(min(tss)), "last": dstr(max(tss)),
            "days": len(set(q["date"] for q in qs if q["date"])),
            "blocks": blocks + 1, "big_gaps_h": gaps, "injected": chosen[key]["st"]["inj"],
            "auto": chosen[key]["st"]["auto"],
            "top": [[k, v] for k, v in cov.most_common(5)],
            "coverage": {m: cov.get(m, 0) for m in ML_ORDER},
            "unclassified": sum(1 for q in qs if not q["hits"]),
            "utypes": dict(Counter(q["utype"] for q in qs)),
            "paste_back": sum(1 for q in qs if q["paste_back"]),
            "median_chars": sorted(q["chars"] for q in qs)[len(qs) // 2] if qs else 0,
        })

    # concurrency per day
    concurrency = []
    for d in sorted(day_total):
        act = [k for k, v in sess_day.items() if v.get(d)]
        concurrency.append({"date": d, "questions": day_total[d], "sessions": len(act),
                            "which": sorted(act)})

    # recurring prompts
    dupq = defaultdict(list)
    for q in all_q:
        dupq[norm_key(q["text"])].append(q)
    recurring = sorted(({"n": len(v), "text": v[0]["text"][:160], "utype": v[0]["utype"],
                        "refs": ["%s:%d(%s)" % (x["session"], x["idx"], x["date"]) for x in v]}
                        for k, v in dupq.items() if len(v) > 1), key=lambda x: -x["n"])

    # representative quotes per mainline
    quotes = {}
    for mid in ML_ORDER:
        cand = [q for q in all_q if mid in q["hits"]]
        informative = [q for q in cand if q["utype"] == "真问句" and 15 <= q["chars"] <= 260]
        informative.sort(key=lambda q: -q["chars"])
        firsts = cand[:3]
        lasts = cand[-3:]
        by_sess = {}
        for q in cand:
            by_sess.setdefault(q["session"], q)
        quotes[mid] = {
            "count": len(cand),
            "earliest": [["%s:%d" % (q["session"], q["idx"]), q["date"], q["text"][:200]] for q in firsts],
            "latest": [["%s:%d" % (q["session"], q["idx"]), q["date"], q["text"][:200]] for q in lasts],
            "top_informative": [["%s:%d" % (q["session"], q["idx"]), q["date"], q["text"][:220]]
                                for q in informative[:12]],
        }

    # ── theme lifecycle: onset / peak / phase shares ────────────────────
    PHASES = [("早期 09-10→09-13", ("2026-09-10", "2026-09-13")),
              ("中期 09-14→09-17", ("2026-09-14", "2026-09-17")),
              ("晚期 09-18→09-22", ("2026-09-18", "2026-09-22"))]

    def phase_of(d):
        for name, (a, b) in PHASES:
            if a <= d <= b:
                return name
        return "?"

    lifecycle = []
    for mid in ML_ORDER:
        dd = dict(ml_days[mid])
        onset = next((d for d, _n in sorted(dd.items()) if dd[d] >= 3), "")
        peak = max(dd.items(), key=lambda kv: kv[1])[0] if dd else ""
        ph = Counter()
        for d, n in dd.items():
            ph[phase_of(d)] += n
        lifecycle.append({
            "id": mid, "name": ML_NAME[mid], "group": ML_GROUP[mid],
            "questions": ml_q.get(mid, 0), "active_days": len(dd),
            "onset_ge3": onset, "peak_day": peak, "peak_n": dd.get(peak, 0) if peak else 0,
            "phases": [ph.get(name, 0) for name, _ in PHASES],
        })
    phase_totals = Counter()
    phase_group = defaultdict(Counter)
    for q in all_q:
        p = phase_of(q["date"])
        phase_totals[p] += 1
        g = ML_GROUP[q["primary"]] if q["primary"] else "unclassified"
        phase_group[p][g] += 1

    out = {
        "totals": {
            "real_questions": len(all_q),
            "sessions": len(per_session),
            "injected_total": sum(s["injected"] for s in sess_table),
            "auto_dispatch_filtered": sum(s["auto"] for s in sess_table),
            "unmatched": sum(1 for q in all_q if not q["hits"]),
            "chars_total": sum(q["chars"] for q in all_q),
            "paste_back": sum(1 for q in all_q if q["paste_back"]),
            "client_typed_rpc": sum(1 for q in all_q if q.get("rpc")),
            "no_rpc_turns": sum(1 for q in all_q if not q.get("rpc")),
            "injected_kinds": sorted(INJ_KINDS.items(), key=lambda x: -x[1]),
            "v3_reported": 959,
        },
        # 959 (v3) reconciliation -> 874 human-authored questions
        "reconciliation": {
            "v3_headline": 959,
            "minus_auto_dispatch": 8,
            "minus_team_join_protocol": 81,
            "plus_s7_larger_export": 4,
            "human_questions": len(all_q),
            "note": "959 - 8 - 81 + 4 = 874；v3 未过滤 AgentTeams 自动派发与入队通知，"
                    "对 S7 又用了较小的那次导出（少 4 条）。",
        },
        "utypes": sorted(utype_q.items(), key=lambda x: -x[1]),
        "dup_report": dup_report,
        "mainlines": [{
            "id": mid, "name": ML_NAME[mid], "group": ML_GROUP[mid],
            "group_name": GROUP_NAME[ML_GROUP[mid]],
            "questions": ml_q.get(mid, 0),
            "share_pct": round(100.0 * ml_q.get(mid, 0) / max(len(all_q), 1), 1),
            "raw_hits": ml_hits.get(mid, 0),
            "first": dstr(ml_first.get(mid)), "last": dstr(ml_last.get(mid)),
            "active_days": len(ml_days[mid]),
            "per_session": {k: ml_sess[mid].get(k, 0) for k in sorted(per_session)},
        } for mid in ML_ORDER],
        "groups": [{"group": g, "label": GROUP_NAME[g], "questions": group_q.get(g, 0),
                    "share_pct": round(100.0 * group_q.get(g, 0) / max(len(all_q), 1), 1),
                    "coverage": group_cov.get(g, 0),
                    "coverage_pct": round(100.0 * group_cov.get(g, 0) / max(len(all_q), 1), 1)}
                   for g in GROUP_ORDER] + [{"group": "unclassified", "label": "未命中",
                                             "questions": group_q.get("unclassified", 0),
                                             "share_pct": round(100.0 * group_q.get("unclassified", 0) / max(len(all_q), 1), 1),
                                             "coverage": group_cov.get("unclassified", 0),
                                             "coverage_pct": round(100.0 * group_cov.get("unclassified", 0) / max(len(all_q), 1), 1)}],
        "primary_by_day": sorted((d, sorted(c.items(), key=lambda x: -x[1])) for d, c in prim_days.items()),
        "phase_totals": sorted(phase_totals.items()),
        "phase_groups": {p: sorted(c.items(), key=lambda x: -x[1]) for p, c in phase_group.items()},
        "lifecycle": lifecycle,
        "primary_totals": sorted(Counter(q["primary"] for q in all_q).items(), key=lambda x: -x[1]),
        "sessions": sess_table,
        "concurrency": concurrency,
        "day_total": sorted(day_total.items()),
        "day_matrix": {mid: sorted(ml_days[mid].items()) for mid in ML_ORDER},
        "hour_hist": sorted(hour_hist.items()),
        "hits_distribution": sorted(multi.items()),
        "recurring_requests": recurring[:150],
        "quotes": quotes,
    }
    with open(os.path.join(OUT_DIR, "quant.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "questions.json"), "w", encoding="utf-8") as f:
        json.dump(all_q, f, ensure_ascii=False, indent=1)

    L = ["# A1 量化表（scripts/analyze_themes_a1.py 生成）\n", "## 总量\n"]
    for k, v in out["totals"].items():
        L.append("- %s: %s" % (k, v))
    L.append("\n## 959 → 874 口径对账\n")
    for k, v in out["reconciliation"].items():
        L.append("- %s: %s" % (k, v))
    L.append("\n## 话语类型\n")
    for k, v in out["utypes"]:
        L.append("- %s: %d (%.1f%%)" % (k, v, 100.0 * v / len(all_q)))
    L.append("\n## 主线热度（提问数=去重命中；raw=原始词命中次数）\n")
    L.append("| 主线 | 名称 | 组 | 命中提问 | 占比 | raw | 首现 | 末现 | 活跃天 | " + " | ".join(sorted(per_session)) + " |")
    L.append("|---|---|---|---:|---:|---:|---|---|---:|" + "---:|" * len(per_session))
    for m in out["mainlines"]:
        L.append("| %s | %s | %s | %d | %.1f%% | %d | %s | %s | %d | %s |" % (
            m["id"], m["name"], m["group"], m["questions"], m["share_pct"], m["raw_hits"],
            m["first"], m["last"], m["active_days"],
            " | ".join(str(m["per_session"][k]) for k in sorted(per_session))))
    L.append("\n## 组热度（primary=按命中词数取主归属；coverage=至少命中该组一条主线）\n")
    for g in out["groups"]:
        L.append("- %s: primary %d (%.1f%%) | coverage %d (%.1f%%)" % (
            g["label"], g["questions"], g["share_pct"], g["coverage"], g["coverage_pct"]))
    L.append("\n## 每日主归属分布\n")
    L.append("| 日期 | 提问 | 主归属 Top3 |")
    L.append("|---|---:|---|")
    for d, pairs in out["primary_by_day"]:
        L.append("| %s | %d | %s |" % (d, sum(v for _, v in pairs),
                                        ", ".join("%s:%d" % (k, v) for k, v in pairs[:3])))
    L.append("\n## Session 表\n")
    L.append("| Session | 提问 | 注入 | 自动派发 | 起 | 止 | 天 | 工作块 | 中位长度 | 粘贴回流 | 未命中 | 主归属Top3 | " + " | ".join(ML_ORDER) + " |")
    L.append("|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|" + "---:|" * len(ML_ORDER))
    for s in out["sessions"]:
        L.append("| %s | %d | %d | %d | %s | %s | %d | %d | %d | %d | %d | %s | %s |" % (
            s["label"], s["questions"], s["injected"], s["auto"], s["first"], s["last"], s["days"],
            s["blocks"], s["median_chars"], s["paste_back"], s["unclassified"],
            ", ".join("%s:%d" % (k, v) for k, v in s["top"][:3]),
            " | ".join(str(s["coverage"][m]) for m in ML_ORDER)))
    L.append("\n## 主线生命周期（onset=首个≥3条提问的日子）\n")
    L.append("| 主线 | 名称 | 命中提问 | 活跃天 | onset | 峰值日 | 峰值 | 早期 | 中期 | 晚期 |")
    L.append("|---|---|---:|---:|---|---|---:|---:|---:|---:|")
    for m in out["lifecycle"]:
        L.append("| %s | %s | %d | %d | %s | %s | %d | %d | %d | %d |" % (
            m["id"], m["name"], m["questions"], m["active_days"], m["onset_ge3"],
            m["peak_day"], m["peak_n"], *m["phases"]))
    L.append("\n## 阶段总量（早期 09-10→09-13 / 中期 09-14→09-17 / 晚期 09-18→09-22）\n")
    for p, n in out["phase_totals"]:
        gs = dict(out["phase_groups"][p])
        tot = sum(gs.values()) or 1
        L.append("- %s: 提问 %d | %s" % (
            p, n, ", ".join("%s %.0f%%" % (GROUP_NAME.get(k, k), 100.0 * v / tot)
                            for k, v in out["phase_groups"][p])))
    L.append("\n## 每日并发\n")
    L.append("| 日期 | 提问 | 活跃会话数 | 会话 |")
    L.append("|---|---:|---:|---|")
    for c in out["concurrency"]:
        L.append("| %s | %d | %d | %s |" % (c["date"], c["questions"], c["sessions"], ",".join(c["which"])))
    L.append("\n## 每日 × 主线\n")
    dm = {m: dict(v) for m, v in out["day_matrix"].items()}
    L.append("| 日期 | 提问 | " + " | ".join(ML_ORDER) + " |")
    L.append("|---|---:|" + "---:|" * len(ML_ORDER))
    for d, n in out["day_total"]:
        L.append("| %s | %d | %s |" % (d, n, " | ".join(str(dm[m].get(d, 0)) for m in ML_ORDER)))
    L.append("\n## 重复原话 Top\n")
    for r in recurring[:60]:
        L.append("- x%d [%s] %s" % (r["n"], r["utype"], r["text"].replace("\n", " ")[:120]))
        L.append("  - " + ", ".join(r["refs"][:10]))
    L.append("\n## 重复导出对账\n")
    for d in out["dup_report"]:
        L.append("- %s %s variants=%s chosen=%s superset=%s dropped=%d" % (
            d["key"], d["label"], d["variants"], d["chosen"], d["smaller_are_subsets"],
            len(d["dropped_keys"])))
    with open(os.path.join(OUT_DIR, "quant.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    Q = ["# A1 典型提问原文（自动候选，报告内人工筛选）\n"]
    for mid in ML_ORDER:
        qq = quotes[mid]
        Q.append("\n## %s %s — 命中 %d 条\n" % (mid, ML_NAME[mid], qq["count"]))
        Q.append("### 最早出现")
        for ref, d, t in qq["earliest"]:
            Q.append("- `%s` %s | %s" % (ref, d, t.replace("\n", " / ")))
        Q.append("### 最近出现")
        for ref, d, t in qq["latest"]:
            Q.append("- `%s` %s | %s" % (ref, d, t.replace("\n", " / ")))
        Q.append("### 信息量最高的问句")
        for ref, d, t in qq["top_informative"]:
            Q.append("- `%s` %s | %s" % (ref, d, t.replace("\n", " / ")))
    with open(os.path.join(OUT_DIR, "quotes.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(Q) + "\n")

    t = out["totals"]
    print("real_questions=%d (v3 said %d) sessions=%d injected=%d auto=%d unmatched=%d paste_back=%d" % (
        t["real_questions"], t["v3_reported"], t["sessions"], t["injected_total"],
        t["auto_dispatch_filtered"], t["unmatched"], t["paste_back"]))
    for m in out["mainlines"]:
        print("  %-3s %-40s q=%-4d raw=%-5d %s..%s days=%d" % (
            m["id"], m["name"][:40], m["questions"], m["raw_hits"], m["first"], m["last"], m["active_days"]))
    for g in out["groups"]:
        print("  GROUP %-22s q=%-4d %.1f%%" % (g["label"], g["questions"], g["share_pct"]))
    print("  UTYPE", out["utypes"])
    print("wrote", OUT_DIR)


if __name__ == "__main__":
    main()
