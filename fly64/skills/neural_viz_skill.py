#!/usr/bin/env python3
"""
Fly64 Neural-Viz Skill — 离线神经因果链路分析与报告 (v1.0.0)

基于 t3 实施方案（fly64/docs/causal-chain-implementation.md）暴露的因果遥测字段，
从 dashboard HTTP 端点（/history.json，P1 落地后含 decision_source / cliff_conf /
stuck_conf / gate_forward / gate_jump / escape_behavior 等）或本地 JSONL 录制文件
做离线分析，产出 Markdown 因果链路报告。

设计约束：
- 只读：仅消费 dashboard 端点与录制文件，绝不回写模型状态（与 Observatory 同原则）。
- 兼容：所有新字段用 .get() 容错访问；字段缺失时（P0 未上线）分析自动降级为
  "partial data" 并在报告中标注 —— evolution_agent.py / evolution_skill.py 的
  DataCollector 不受任何影响（它只读取自己关心的键，新增键对旧消费者透明）。
- 复用 evolution_skill 的端点轮询与日志风格，不引入新依赖。

用法:
  # 轮询 dashboard 120s 后出报告
  python3 -m fly64.skills.neural_viz_skill --duration 120
  # 离线分析录制文件
  python3 -m fly64.skills.neural_viz_skill --input causal_log.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections import Counter, deque
from pathlib import Path
from typing import Optional

DASHBOARD_BASE = "http://127.0.0.1:8765"
SKILL_DIR = Path(__file__).resolve().parent

# decision_source 优先级（与 main.py 控制级联一致，t3 §1.3）
PRIORITY = {"cliff_reflex": 4, "anomaly_reflex": 3, "escape": 2, "jump": 1, "steering": 0}
PREEMPTABLE = ("jump", "steering")


def fetch_json(endpoint: str, base: str = DASHBOARD_BASE) -> Optional[dict]:
    """与 evolution_skill.DataCollector.fetch_json 相同的容错风格。"""
    try:
        with urllib.request.urlopen(f"{base}{endpoint}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── Phase 1: Collect ─────────────────────────────────────────────────────

class CausalRecorder:
    """轮询 /history.json，保留滚动窗口内的因果行（仅新字段存在时计入 causal 行）。"""

    def __init__(self, window_seconds: int = 300, base: str = DASHBOARD_BASE):
        self.window_seconds = window_seconds
        self.base = base
        self.rows: deque[dict] = deque()

    def poll_once(self) -> int:
        data = fetch_json("/history.json", self.base)
        if not data:
            return 0
        added = 0
        for row in data if isinstance(data, list) else data.get("rows", []):
            if self.rows and row.get("t", 0) <= self.rows[-1].get("t", 0):
                continue  # 只增不重（t 单调）
            self.rows.append(row)
            added += 1
        self._trim()
        return added

    def _trim(self):
        cutoff = (self.rows[-1]["t"] if self.rows else 0) - self.window_seconds
        while self.rows and self.rows[0].get("t", 0) < cutoff:
            self.rows.popleft()

    @classmethod
    def from_jsonl(cls, path: str) -> "CausalRecorder":
        rec = cls()
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec.rows.append(json.loads(line))
        return rec

    def to_jsonl(self, path: str):  # 供长时录制，之后可离线重放
        with open(path, "w", encoding="utf-8") as f:
            for row in self.rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")


# ── Phase 2: Analyze ─────────────────────────────────────────────────────

class CausalAnalyzer:
    """对因果行做离线统计与问题检测。全部容错：缺字段 -> 跳过该项统计。"""

    def __init__(self, rows: list[dict]):
        self.rows = rows

    @property
    def causal_rows(self):
        return [r for r in self.rows if "decision_source" in r]

    def source_distribution(self) -> Counter:
        return Counter(r["decision_source"] for r in self.causal_rows)

    def preempt_events(self) -> list[dict]:
        """被仲裁压制事件：decision_source 优先级 > steering/jump。"""
        return [dict(t=r.get("t"), source=r["decision_source"],
                     cliff_conf=r.get("cliff_conf"), stuck_conf=r.get("stuck_conf"))
                for r in self.causal_rows if PRIORITY.get(r["decision_source"], 0) >= 2]

    def gate_flap_rate(self, gate: str = "gate_forward") -> float:
        """门控抖动率：gate 翻转次数 / 可比样本数（高抖动 -> 阈值滞回缺失）。"""
        vals = [bool(r[gate]) for r in self.causal_rows if gate in r]
        if len(vals) < 2:
            return 0.0
        return sum(a != b for a, b in zip(vals, vals[1:])) / (len(vals) - 1)

    def cliff_false_positives(self) -> list[dict]:
        """与 evolution_skill circle_loop 同源的矛盾检测：
        decision_source=cliff_reflex 但 cliff_conf 低（<0.5）或未 confirmed。"""
        return [dict(t=r.get("t"), cliff_conf=r.get("cliff_conf"),
                     cliff_confirmed=r.get("cliff_confirmed"))
                for r in self.causal_rows
                if r["decision_source"] == "cliff_reflex"
                and (r.get("cliff_conf", 1.0) < 0.5 or not r.get("cliff_confirmed", True))]

    def signal_to_action_latency(self) -> Optional[float]:
        """近似信号->行动延迟：cliff_confirmed 上升沿到首个 x 翻转的 tick 数 × dt(0.02s)。"""
        pending = None
        for r in self.causal_rows:
            confirmed = r.get("cliff_confirmed")
            if pending is None and confirmed:
                pending = r.get("t")
            elif pending is not None and confirmed is False:
                pending = None
            elif pending is not None and r.get("x", 0) != 0:
                dt = 0.02
                return (r["t"] - pending) if r.get("t") else None
        return None

    def findings(self) -> list[dict]:
        out = []
        fp = self.cliff_false_positives()
        if len(fp) >= 3:
            out.append(dict(severity="high", id="cliff_false_positive",
                            detail=f"{len(fp)} cliff_reflex events with conf<0.5 or unconfirmed, "
                                   f"e.g. t={fp[0]['t']} — 地形分类器疑似误报（对照 circle_loop 模式）"))
        for gate in ("gate_forward", "gate_jump"):
            rate = self.gate_flap_rate(gate)
            if rate > 0.4:
                out.append(dict(severity="medium", id=f"{gate}_flap",
                                detail=f"{gate} flip rate {rate:.0%} — 建议加滞回(hysteresis)"))
        dist = self.source_distribution()
        if self.causal_rows and dist["steering"] / len(self.causal_rows) < 0.3:
            out.append(dict(severity="medium", id="preempt_storm",
                            detail=f"steering only {dist['steering']}/{len(self.causal_rows)} ticks — "
                                   f"反射/逃脱占用过高，检查异常态黏滞"))
        lat = self.signal_to_action_latency()
        if lat is not None and lat > 0.5:
            out.append(dict(severity="low", id="slow_reflex",
                            detail=f"cliff signal -> action latency ≈ {lat:.2f}s"))
        return out


# ── Phase 3: Report ──────────────────────────────────────────────────────

def render_report(rows: list[dict], findings: list[dict], path: str):
    a = CausalAnalyzer(rows)
    n_total, n_causal = len(rows), len(a.causal_rows)
    dist = a.source_distribution()
    preempt = a.preempt_events()
    lines = [
        "# Fly64 Neural Causal Chain Report",
        f"",
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Rows: {n_total} (causal-annotated: {n_causal}"
        + ("" if n_causal else " — P1 遥测字段未上线，报告为 partial data)") + ")",
        f"- Signal→action latency: {a.signal_to_action_latency()}",
        "",
        "## decision_source distribution",
        "",
        "| source | ticks | share |",
        "|---|---|---|",
    ]
    for src, cnt in dist.most_common():
        lines.append(f"| {src} | {cnt} | {cnt / max(n_causal, 1):.0%} |")
    lines += ["", f"## Preempt events ({len(preempt)})", ""]
    lines += [f"- t={e['t']} {e['source']} (cliff_conf={e['cliff_conf']}, stuck_conf={e['stuck_conf']})"
              for e in preempt[-20:]]
    lines += ["", f"## Findings ({len(findings)})", ""]
    lines += [f"- [{f['severity']}] {f['id']}: {f['detail']}" for f in findings] or ["- none"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Fly64 neural causal chain offline analysis")
    ap.add_argument("--dashboard", default=DASHBOARD_BASE)
    ap.add_argument("--duration", type=int, default=120, help="poll seconds (live mode)")
    ap.add_argument("--interval", type=float, default=1.0, help="poll interval seconds")
    ap.add_argument("--input", help="offline JSONL rows instead of live polling")
    ap.add_argument("--record", help="also save polled rows to JSONL for later replay")
    ap.add_argument("--report", default=str(SKILL_DIR / "neural_viz_report.md"))
    args = ap.parse_args()

    if args.input:
        rec = CausalRecorder.from_jsonl(args.input)
    else:
        rec = CausalRecorder(base=args.dashboard)
        deadline = time.time() + args.duration
        while time.time() < deadline:
            rec.poll_once()
            time.sleep(args.interval)
        if args.record:
            rec.to_jsonl(args.record)

    rows = list(rec.rows)
    findings = CausalAnalyzer(rows).findings()
    path = render_report(rows, findings, args.report)
    print(f"report: {path} | rows={len(rows)} findings={len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
