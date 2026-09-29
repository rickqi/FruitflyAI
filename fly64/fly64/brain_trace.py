"""Fly64 brain decision-trace loader for the dashboard replay page.

Pure stdlib; no fly64-package imports so the dashboard HTTP thread stays light.
Sources (both optional):
  fly64/runtime/mbon_eval.csv        - tick-level MBON channels + dopamine + decisions
  fly64/skills/coach_outcomes.jsonl  - coach anomaly events (fallen / unsolvable_stuck ...)
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

#: directory that contains fly64/ (i.e. D:\codes\flygym\fly64)
_FLY64_ROOT = Path(__file__).resolve().parent.parent
MBON_CSV = _FLY64_ROOT / "runtime" / "mbon_eval.csv"
#: rolling daily trace dir written by the in-brain TraceRecorder
MBON_ROLL_DIR = _FLY64_ROOT / "runtime" / "mbon_eval"
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


def _iter_trace_files():
    """Yield trace CSV paths oldest-first: rolling daily dir preferred,
    legacy single mbon_eval.csv as fallback."""
    files = []
    if MBON_ROLL_DIR.exists():
        files = sorted(MBON_ROLL_DIR.glob("mbon_eval_*.csv"))
    if files:
        return files
    return [MBON_CSV] if MBON_CSV.exists() else []


#: replay payload cap — the page merges live anyway, older rows are history
MAX_TICKS = 6000


def load_mbon_ticks():
    ticks = []
    for path in _iter_trace_files():
        try:
            with path.open(newline="", encoding="utf-8") as fh:
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
                            "goal_source": row.get("cx_goal_source") or None,
                        } if row.get("cx_heading_column") not in (None, "") else None,
                    })
        except OSError:
            continue
    ticks.sort(key=lambda x: x["t"])
    if len(ticks) > MAX_TICKS:
        ticks = ticks[-MAX_TICKS:]
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


# ── in-brain persistent recorder ─────────────────────────────────────────

#: row schema — identical to scripts/m3_mbon_eval.py sample output so
#: brain_trace.load_mbon_ticks / the offline analyse mode read both.
_COLUMNS = (["ts", "decision_source", "cpg_active", "completed", "aborted",
             "event", "primitive", "disp_60s", "dopamine"]
            + [f"mb_mbon_{m}" for m in ("punch", "dive", "groundpound", "longjump")]
            + [f"mb_w_{m}" for m in ("punch", "dive", "groundpound", "longjump")]
            + CX_COLS
            + ["cx_heading_column", "cx_goal_column", "cx_steering_bias",
               "cx_entropy", "cx_peak", "cx_goal_source"])

INTERVAL_S = 2.0      # sample cadence (matches the external sampler)
KEEP_DAYS = 7         # rolling retention


class TraceRecorder:
    """Throttled rolling-daily CSV writer fed from the live flow dict.

    Called from the brain's telemetry loop (main.py) every tick; internally
    throttled to one row per ``INTERVAL_S``.  Opens/appends/closes per row
    (~0.5 Hz) so an external tail or the replay page always sees fresh data
    without the writer holding a handle.
    """

    def __init__(self, roll_dir: Path = MBON_ROLL_DIR,
                 interval: float = INTERVAL_S, keep_days: int = KEEP_DAYS):
        self.roll_dir = roll_dir
        self.interval = interval
        self.keep_days = keep_days
        self._last_ts = 0.0
        self._last_prune = 0.0
        self.rows_written = 0

    def maybe_record(self, flow: dict, now: float | None = None) -> bool:
        """Write one row if ``interval`` elapsed since the previous one."""
        now = now if now is not None else time.time()
        if now - self._last_ts < self.interval:
            return False
        self._last_ts = now
        try:
            self.roll_dir.mkdir(parents=True, exist_ok=True)
            day = time.strftime("%Y%m%d", time.localtime(now))
            path, new_file = self._resolve_target(day)
            with path.open("a", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                if new_file:
                    w.writerow(_COLUMNS)
                w.writerow(self._row(flow, now))
            self.rows_written += 1
            if now - self._last_prune > 3600:
                self._prune(now)
            return True
        except Exception:
            # tracing must never break the brain loop
            return False

    def _resolve_target(self, day: str) -> tuple[Path, bool]:
        """Pick today's target file; if an existing file's header does not
        match the current schema (e.g. legacy external-sampler rows), rotate
        to a versioned file so DictReader never sees mixed headers."""
        header = ",".join(_COLUMNS)
        path = self.roll_dir / f"mbon_eval_{day}.csv"
        for suffix in ("", "_v2", "_v3", "_v4"):
            path = self.roll_dir / f"mbon_eval_{day}{suffix}.csv"
            if not path.exists():
                return path, True
            try:
                with path.open(encoding="utf-8") as fh:
                    if fh.readline().strip() == header:
                        return path, False
            except OSError:
                break
        # all versioned slots mismatched: append to the last one anyway
        return path, False

    @staticmethod
    def _row(f: dict, now: float) -> list:
        cpg = f.get("cpg_status") or {}
        cs = f.get("cx_stats") or {}
        cx = f.get("cx_compass") or []
        mbons = ("punch", "dive", "groundpound", "longjump")
        return [round(now, 2),
                f.get("decision_source") or "",
                cpg.get("active") or "",
                int(cpg.get("completed", 0) or 0),
                int(cpg.get("aborted", 0) or 0),
                "", "",  # event/primitive: filled by event observers later
                f.get("primitive_disp"), f.get("mb_dopamine"),
                *[f.get(f"mb_mbon_{m}") for m in mbons],
                *[f.get(f"mb_w_{m}") for m in mbons],
                *[cx[i] if i < len(cx) else None for i in range(16)],
                cs.get("heading_column"), cs.get("goal_column"),
                cs.get("steering_bias"), cs.get("compass_entropy"),
                cs.get("compass_peak"), cs.get("goal_source")]

    def _prune(self, now: float) -> None:
        self._last_prune = now
        cutoff = now - self.keep_days * 86400
        for p in self.roll_dir.glob("mbon_eval_*.csv"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass


_recorder: TraceRecorder | None = None


def get_recorder() -> TraceRecorder:
    global _recorder
    if _recorder is None:
        _recorder = TraceRecorder()
    return _recorder
