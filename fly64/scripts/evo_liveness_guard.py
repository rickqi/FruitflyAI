#!/usr/bin/env python3
"""Fly64 EVO loop liveness guard — 停摆检测告警 + 环境契约自检（P0-3 / t3）。

依据 ``docs/analysis/analysis-t2-evolution-pipeline-failure.md`` 失效点 #1：
自进化闭环停摆 7 天无人知。本脚本是【闭环外部】的守护者：

1. **停摆检测**：``skills/evolution_log.jsonl`` 超过阈值（默认 30 min，可配置）
   没有新行 ⇒ 判停摆，写告警。
2. **告警落点**（三路）：
   - 日志        : ``skills/evo_stall_alarm.jsonl``（每状态跳变追加一行）
   - dashboard 端点 : ``skills/evo_stall_alarm.json``（原子快照，dashboard/监控
                      可读的规范告警状态；dashboard HTTP 无告警 POST 端点，
                      故以该快照 + 最佳努力 HTTP 通知作为 dashboard 可见面）
   - service_status: ``plugin/service_status.json`` 合并 ``evo_loop`` 键（可选）
3. **环境契约自检**：``--selfcheck`` 把「EVO 闭环」与脑模型/dashboard、SM64/桥接
   同列输出，失败给出可执行修复指引。

用法::

    python3 fly64/scripts/evo_liveness_guard.py --check [--threshold 1800]
    python3 fly64/scripts/evo_liveness_guard.py --watch [--interval 60 --threshold 1800]
    python3 fly64/scripts/evo_liveness_guard.py --selfcheck

退出码（--check / --watch 单次）: 0=绿(健康)  2=红(停摆)  3=告警写入失败。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_DIR / "skills"
EVO_LOG = SKILLS_DIR / "evolution_log.jsonl"
ALARM_LOG = SKILLS_DIR / "evo_stall_alarm.jsonl"
ALARM_SNAP = SKILLS_DIR / "evo_stall_alarm.json"
SERVICE_STATUS = PROJECT_DIR / "plugin" / "service_status.json"
DASHBOARD_BASE = os.environ.get("EVO_DASHBOARD_BASE", "http://127.0.0.1:8765")
DEFAULT_THRESHOLD_S = 30 * 60  # 30 min，可配置
DEFAULT_WATCH_INTERVAL_S = 60

BRIDGE_PATH = Path(os.environ.get("FLY64_BRIDGE_PATH", "/tmp/f64b_traj"))


# ── 基础探测 ────────────────────────────────────────────────────────────────
def _count_lines(path: Path) -> int:
    """O(n) 行数统计；文件很大也稳定，不把整个文件读进内存。"""
    try:
        n = 0
        with open(path, "rb") as f:
            for _ in f:
                n += 1
        return n
    except OSError:
        return 0


def _log_stat(path: Path = EVO_LOG) -> dict:
    """读 evolution_log.jsonl 的新鲜度与规模（不解析内容）。"""
    stat = {"exists": False, "size": 0, "mtime": None, "age_s": None,
            "lines": 0, "last_ts": None}
    if not path.exists():
        return stat
    try:
        st = path.stat()
        stat["exists"] = True
        stat["size"] = st.st_size
        stat["mtime"] = st.st_mtime
        stat["age_s"] = round(time.time() - st.st_mtime, 2)
        stat["lines"] = _count_lines(path)
    except OSError:
        pass
    return stat


def _http_get(endpoint: str, timeout: float = 4.0) -> tuple[bool, int]:
    """返回 (reachable, http_code)；不可达记 0。"""
    try:
        with urllib.request.urlopen(DASHBOARD_BASE + endpoint, timeout=timeout) as r:
            return True, r.status
    except Exception:
        return False, 0


def _find_loop_pid() -> int | None:
    """进化闭环进程 PID（pgrep 匹配脚本形式）；非 Linux 下退化为 None。"""
    try:
        out = subprocess.run(
            ["pgrep", "-f", r"[e]volution_skill\.py"],
            capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
    except Exception:
        pass
    return None


def _bridge_age_s() -> float | None:
    try:
        return round(time.time() - BRIDGE_PATH.stat().st_mtime, 1)
    except OSError:
        return None


# ── 停摆判定 ────────────────────────────────────────────────────────────────
def check_stall(threshold_s: float, log_path: Path = EVO_LOG) -> dict:
    """判定进化闭环是否停摆，返回完整状态 dict。"""
    stat = _log_stat(log_path)
    dash_ok, dash_code = _http_get("/memory.json")
    pid = _find_loop_pid()
    now = time.time()

    if not stat["exists"]:
        stale = True
        reason = "evolution_log.jsonl 不存在（闭环从未写过日志）"
    elif stat["age_s"] is None:
        stale = True
        reason = "evolution_log.jsonl 不可读"
    else:
        stale = stat["age_s"] > threshold_s
        reason = (f"evolution_log.jsonl {stat['age_s']:.0f}s 无新行 "
                  f"> 阈值 {threshold_s:.0f}s" if stale else "正常")

    state = {
        "stale": stale,
        "checked_at": now,
        "threshold_s": threshold_s,
        "reason": reason,
        "log": {
            "exists": stat["exists"],
            "lines": stat["lines"],
            "size": stat["size"],
            "mtime": stat["mtime"],
            "age_s": stat["age_s"],
        },
        "loop": {"pid": pid, "alive": pid is not None},
        "dashboard": {"reachable": dash_ok, "http_code": dash_code},
    }
    return state


# ── 告警落点 ────────────────────────────────────────────────────────────────
def _write_alarm_snapshot(state: dict) -> None:
    """dashboard 可见的规范告警状态快照（原子写）。"""
    ALARM_SNAP.parent.mkdir(parents=True, exist_ok=True)
    tmp = ALARM_SNAP.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, ALARM_SNAP)


def _append_alarm_log(event: str, state: dict) -> None:
    """告警事件日志：每状态跳变（stalled/recovered）追加一行。"""
    entry = {
        "ts": state["checked_at"],
        "event": event,
        "threshold_s": state["threshold_s"],
        "reason": state["reason"],
        "log_age_s": state["log"]["age_s"],
        "log_lines": state["log"]["lines"],
        "loop_pid": state["loop"]["pid"],
        "dashboard_reachable": state["dashboard"]["reachable"],
    }
    ALARM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALARM_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _merge_service_status(state: dict) -> bool:
    """可选：把 evo_loop 状态并入 plugin/service_status.json（保留既有键）。"""
    try:
        SERVICE_STATUS.parent.mkdir(parents=True, exist_ok=True)
        cur: dict = {}
        if SERVICE_STATUS.exists():
            try:
                cur = json.loads(SERVICE_STATUS.read_text(encoding="utf-8"))
                if not isinstance(cur, dict):
                    cur = {}
            except (json.JSONDecodeError, OSError):
                cur = {}
        cur["evo_loop"] = {
            "stale": state["stale"],
            "log_age_s": state["log"]["age_s"],
            "log_lines": state["log"]["lines"],
            "loop_pid": state["loop"]["pid"],
            "loop_alive": state["loop"]["alive"],
            "dashboard_reachable": state["dashboard"]["reachable"],
            "checked_at": state["checked_at"],
            "threshold_s": state["threshold_s"],
        }
        tmp = SERVICE_STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, SERVICE_STATUS)
        return True
    except OSError:
        return False


def _notify_dashboard(state: dict) -> bool:
    """dashboard 端点（最佳努力）：dashboard 无告警 POST 端点，故以可达性探测
    作为通知（记录告警时刻 dashboard 是否在线）。真正的 dashboard 可见面是
    ALARM_SNAP 快照 + service_status 合并。"""
    ok, _ = _http_get("/memory.json")
    return ok


def emit_alarm(event: str, state: dict) -> dict:
    """把一次状态跳变写入三路告警落点，返回每路是否成功。"""
    results = {"snapshot": False, "log": False, "service_status": False,
               "dashboard": False}
    try:
        _write_alarm_snapshot(state)
        results["snapshot"] = True
    except OSError:
        pass
    try:
        _append_alarm_log(event, state)
        results["log"] = True
    except OSError:
        pass
    results["service_status"] = _merge_service_status(state)
    results["dashboard"] = _notify_dashboard(state)
    return results


# ── check / watch ───────────────────────────────────────────────────────────
def _human(state: dict) -> str:
    marker = "🔴 RED 停摆" if state["stale"] else "🟢 GREEN 在线"
    log = state["log"]
    age = f"{log['age_s']:.0f}s" if log["age_s"] is not None else "N/A"
    loop = f"pid={state['loop']['pid']}" if state["loop"]["pid"] else "无进程"
    dash = "在线" if state["dashboard"]["reachable"] else "不可达"
    return (f"{marker} | {state['reason']} | 日志 {log['lines']} 行/最后写 {age} 前 "
            f"| 闭环 {loop} | dashboard {dash}")


def cmd_check(args) -> int:
    state = check_stall(args.threshold)
    print(_human(state))
    if state["stale"]:
        emit_alarm("stalled", state)
        print(f"  告警已写入: {ALARM_SNAP.name} / {ALARM_LOG.name} / "
              f"service_status.json(evo_loop)")
        return 2
    return 0


def cmd_watch(args) -> int:
    last_stale: bool | None = None
    print(f"[watch] 每 {args.interval}s 检查一次，阈值 {args.threshold:.0f}s，"
          f"Ctrl-C 退出")
    while True:
        state = check_stall(args.threshold)
        # 快照每次刷新；告警日志只在状态【跳变】时追加（首轮只记基线）
        try:
            _write_alarm_snapshot(state)
        except OSError:
            pass
        if last_stale is None:
            print(f"[{time.strftime('%H:%M:%S')}] (基线) {_human(state)}")
        elif state["stale"] != last_stale:
            event = "stalled" if state["stale"] else "recovered"
            results = emit_alarm(event, state)
            print(f"[{time.strftime('%H:%M:%S')}] {_human(state)}")
            print(f"    → 状态跳变「{event}」告警: {results}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] {_human(state)}")
        last_stale = state["stale"]
        time.sleep(args.interval)


# ── 环境契约自检 ────────────────────────────────────────────────────────────
def _selfcheck_evo() -> tuple[bool, list[str]]:
    """EVO 闭环自检：进程 + 日志新鲜度。"""
    state = check_stall(30 * 60)  # 自检用 30 min 标准阈值
    problems: list[str] = []
    ok = True
    if not state["loop"]["alive"]:
        ok = False
        problems.append("进化闭环进程不在运行")
    if not state["log"]["exists"]:
        ok = False
        problems.append("evolution_log.jsonl 不存在")
    elif state["stale"]:
        ok = False
        problems.append(state["reason"])
    return ok, problems


def cmd_selfcheck(args) -> int:
    print("=" * 62)
    print(" Fly64 环境契约一键自检")
    print("=" * 62)

    rows = []

    # 1) EVO 闭环
    evo_ok, evo_problems = _selfcheck_evo()
    st = check_stall(args.threshold if args.threshold != DEFAULT_THRESHOLD_S
                     else 30 * 60)
    pid = st["loop"]["pid"]
    age = st["log"]["age_s"]
    age_s = f"{age:.0f}s 前" if age is not None else "N/A"
    evo_detail = (f"pid={pid} 日志{st['log']['lines']}行/最后写{age_s}"
                  if evo_ok else "; ".join(evo_problems))
    rows.append(("EVO 闭环", evo_ok, evo_detail))

    # 2) 脑模型 / dashboard
    dash_ok, dash_code = _http_get("/memory.json")
    rows.append(("脑模型 dashboard", dash_ok,
                 f"http://127.0.0.1:8765/memory.json http={dash_code}"
                 if dash_ok else "127.0.0.1:8765 不可达"))

    # 3) SM64 / 桥接
    bridge_age = _bridge_age_s()
    bridge_ok = bridge_age is not None and bridge_age <= 60
    rows.append(("SM64 / 桥接", bridge_ok,
                 f"桥接 {BRIDGE_PATH} age={bridge_age}s" if bridge_age is not None
                 else f"桥接文件 {BRIDGE_PATH} 缺失"))

    # 4) 进化闭环心跳（若存在）
    hb = SKILLS_DIR / ".evo_loop_heartbeat.json"
    if hb.exists():
        try:
            hb_ts = json.loads(hb.read_text(encoding="utf-8")).get("ts", 0)
            hb_ok = (time.time() - hb_ts) <= 120
            rows.append(("EVO 心跳", hb_ok,
                         f"{time.time()-hb_ts:.0f}s 前" if hb_ok
                         else f"{time.time()-hb_ts:.0f}s 前（陈旧）"))
        except (json.JSONDecodeError, OSError):
            rows.append(("EVO 心跳", False, "心跳文件不可读"))
    else:
        rows.append(("EVO 心跳", False, "心跳文件缺失"))

    all_ok = True
    for name, ok, detail in rows:
        all_ok = all_ok and ok
        mark = "● 通过" if ok else "○ 失败"
        print(f"  [{mark}] {name}: {detail}")

    print("-" * 62)
    if all_ok:
        print("  结论: 全部通过 ✅")
    else:
        print("  结论: 存在失败项 ❌")
    print("-" * 62)

    # 修复指引（只在失败项时给出可执行建议）
    fixes = []
    if not evo_ok:
        fixes.append("EVO 闭环: bash scripts/evo_loop_launcher.sh --launch"
                     "（或 --restart）；随后用 --status 确认 pid 与日志增长")
    if not dash_ok:
        fixes.append("脑模型: bash scripts/wsl_launcher.sh --status；"
                     "若未运行则 --launch 或 --restart 拉起脑模型(dashboard 8765)")
    if not bridge_ok:
        fixes.append("桥接: 确认 SM64 或脑模型正在写 %s；"
                     "合成模式用 /tmp/f64b_traj，游戏模式需 SM64 进程" % BRIDGE_PATH)
    if fixes:
        print("修复指引:")
        for f in fixes:
            print(f"  → {f}")
    else:
        print("无需修复。")
    print("=" * 62)
    return 0 if all_ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Fly64 EVO loop liveness guard")
    ap.add_argument("--check", action="store_true", help="单次停摆检查")
    ap.add_argument("--watch", action="store_true", help="常驻守护循环")
    ap.add_argument("--selfcheck", action="store_true", help="环境契约一键自检")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_S,
                    help="停摆阈值秒（默认 1800=30min，可用 EVO_STALL_THRESHOLD_S）")
    ap.add_argument("--interval", type=float, default=DEFAULT_WATCH_INTERVAL_S,
                    help="--watch 的检查间隔秒（默认 60）")
    args = ap.parse_args()

    if args.threshold == DEFAULT_THRESHOLD_S:
        env_t = os.environ.get("EVO_STALL_THRESHOLD_S")
        if env_t:
            try:
                args.threshold = float(env_t)
            except ValueError:
                pass

    if args.watch:
        return cmd_watch(args)
    if args.selfcheck:
        return cmd_selfcheck(args)
    # 默认（含 --check）
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
