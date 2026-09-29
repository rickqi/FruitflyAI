"""Fly64 brain decision-trace loader for the dashboard replay page.

Pure stdlib; no fly64-package imports so the dashboard HTTP thread stays light.
Sources (both optional):
  fly64/runtime/mbon_eval.csv        - tick-level MBON channels + dopamine + decisions
  fly64/skills/coach_outcomes.jsonl  - coach anomaly events (fallen / unsolvable_stuck ...)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

#: directory that contains fly64/ (i.e. D:\codes\flygym\fly64)
_FLY64_ROOT = Path(__file__).resolve().parent.parent
MBON_CSV = _FLY64_ROOT / "runtime" / "mbon_eval.csv"
COACH_JSONL = _FLY64_ROOT / "skills" / "coach_outcomes.jsonl"

MBON_KEYS = ["mb_mbon_punch", "mb_mbon_dive", "mb_mbon_groundpound", "mb_mbon_longjump"]
#: mb_w_* weight-mean telemetry columns (present when the sampler is recent)
WEIGHT_KEYS = ["mb_w_punch", "mb_w_dive", "mb_w_groundpound", "mb_w_longjump"]
CX_COLS = [f"cx_col_{i}" for i in range(16)]

#: human-readable explanations surfaced by the replay page's field guide
FIELD_HELP = {
    "mb_mbon_punch": "蘑菇体 MBON『拳击』动作通道读数：>0 支持该本能动作，<0 抑制",
    "mb_mbon_dive": "MBON『俯冲』动作通道读数",
    "mb_mbon_groundpound": "MBON『砸地』动作通道读数",
    "mb_mbon_longjump": "MBON『远跳』动作通道读数",
    "dopamine": "多巴胺奖励信号：负值=惩罚/失败（动作被抑制加权），正值=奖励（动作被强化）",
    "decision_source": "当前决策来源：cpg_primitive:* = 本能CPG直出；steering = CX+MBON 综合转向决策",
    "primitive": "当前执行的动作基元（longjump/punch/…）",
    "event": "离散事件标记：complete=动作完成，abort=动作中断",
    "cpg_active": "CPG（中央模式发生器）是否激活：1=本能反射驱动，0=脑模型自主决策",
    "completed": "累计完成的动作数",
    "aborted": "累计中断的动作数",
    "disp_60s": "过去60秒位移（速度代理）：长期≈0 说明卡死，是 escape/coach 触发依据",
    "mb_w_*": "MBON 对应动作列的权重均值（场景无关的学习方向度量）：成功后应上升、失败后应下降",
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_mbon_ticks():
    ticks = []
    if not MBON_CSV.exists():
        return ticks
    with MBON_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ts = _f(row.get("ts"))
            if ts is None:
                continue
            ticks.append({
                "t": ts,
                "decision_source": row.get("decision_source") or "",
                "primitive": row.get("primitive") or "",
                "event": row.get("event") or "",
                "cpg_active": _f(row.get("cpg_active")),
                "completed": int(_f(row.get("completed")) or 0),
                "aborted": int(_f(row.get("aborted")) or 0),
                "disp_60s": _f(row.get("disp_60s")),
                "dopamine": _f(row.get("dopamine")),
                "mbon": {k: _f(row.get(k)) for k in MBON_KEYS},
                "mbw": {k: _f(row.get(k)) for k in WEIGHT_KEYS if row.get(k) not in (None, "")},
                "cx_compass": [_f(row.get(c)) for c in CX_COLS] if row.get("cx_col_0") not in (None, "") else None,
                "cx_stats": {
                    "heading_column": _f(row.get("cx_heading_column")),
                    "goal_column": _f(row.get("cx_goal_column")),
                    "steering_bias": _f(row.get("cx_steering_bias")),
                    "compass_entropy": _f(row.get("cx_entropy")),
                    "compass_peak": _f(row.get("cx_peak")),
                } if row.get("cx_heading_column") not in (None, "") else None,
            })
    ticks.sort(key=lambda x: x["t"])
    return ticks


def load_coach_events():
    events = []
    if not COACH_JSONL.exists():
        return events
    with COACH_JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = _f(rec.get("resolved_at"))
            if t is None:
                continue
            events.append({
                "t": t,
                "kind": "coach",
                "anomaly": rec.get("anomaly") or "",
                "verdict": rec.get("verdict") or "",
                "help_reason": rec.get("help_reason") or "",
                "age_s": _f(rec.get("age_s")),
            })
    events.sort(key=lambda x: x["t"])
    return events


def build_trace() -> dict:
    ticks = load_mbon_ticks()
    coach = load_coach_events()
    return {
        "schema": "fly64-brain-replay/1",
        "mbon_channels": MBON_KEYS,
        "weight_keys": [k for k in WEIGHT_KEYS],
        "field_help": FIELD_HELP,
        "tick_count": len(ticks),
        "event_count": len(coach),
        "t0": ticks[0]["t"] if ticks else None,
        "ticks": ticks,
        "events": coach,
    }
