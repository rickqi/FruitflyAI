"""Soak monitor: continuous process health and stability verification.

Cross-platform (Linux/WSL/Windows) process-tree tr\xacency and health
logging for long-running Fly64 brain sessions.

Usage:
    # Monitor an already-running brain (find PID via tasklist/ps)
    python scripts/monitor_soak.py <PID> [--seconds 43200] [--interval 5]

    # Auto-launch and monitor (Windows)
    python scripts/monitor_soak.py --launch "wsl bash scripts/wsl_launcher.sh launch" \\
        --seconds 43200 --interval 5

    # Auto-launch and monitor (WSL/Linux)
    python scripts/monitor_soak.py --launch "python3 -m fly64.main --bridge ..." \\
        --seconds 43200 --interval 5
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _collect_process_tree(pid: int) -> dict:
    """Cross-platform process tree snapshot.

    Returns dict with pid, children, rss_mb, cmdline, and status.
    """
    result = {
        "pid": pid,
        "alive": False,
        "children": [],
        "total_rss_mb": 0.0,
        "wall_s": None,
    }

    if sys.platform == "win32":
        return _collect_process_tree_windows(pid, result)
    else:
        return _collect_process_tree_posix(pid, result)


def _collect_process_tree_posix(pid: int, result: dict) -> dict:
    """POSIX (Linux/macOS) process tree via ps."""
    try:
        # Check parent
        os.kill(pid, 0)
        result["alive"] = True
    except (OSError, ProcessLookupError):
        result["alive"] = False
        return result

    try:
        table = subprocess.check_output(
            ["ps", "-axo", "pid=,ppid=,rss=,comm="],
            text=True, timeout=10, stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        return result

    processes = []
    for line in table.strip().split("\n"):
        parts = line.strip().split(None, 3)
        if len(parts) >= 3:
            try:
                p = int(parts[0])
                pp = int(parts[1])
                rss_kb = int(parts[2])
                cmd = parts[3] if len(parts) > 3 else ""
                processes.append((p, pp, rss_kb, cmd))
            except ValueError:
                continue

    descendants = {pid}
    while True:
        expanded = descendants | {
            p for p, pp, _, _ in processes if pp in descendants
        }
        if expanded == descendants:
            break
        descendants = expanded

    total_rss = 0.0
    children = []
    for p, pp, rss_kb, cmd in processes:
        if p in descendants and p != pid:
            total_rss += rss_kb / 1024
            children.append({"pid": p, "rss_mb": round(rss_kb / 1024, 1), "cmd": cmd})

    result["children"] = children
    result["total_rss_mb"] = round(total_rss, 1)
    return result


def _collect_process_tree_windows(pid: int, result: dict) -> dict:
    """Windows process tree via tasklist / wmic."""
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        if str(pid) in proc.stdout:
            result["alive"] = True
        else:
            result["alive"] = False
            return result
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        result["alive"] = False
        return result

    # Get children via wmic (Windows)
    children = []
    total_rss = 0.0
    try:
        wmic_out = subprocess.check_output(
            ["wmic", "process", "get", "ProcessId,ParentProcessId,WorkingSetSize,Name",
             "/FORMAT:CSV"],
            text=True, timeout=15, stderr=subprocess.DEVNULL,
        )
        rows = []
        for line in wmic_out.strip().split("\n"):
            parts = line.strip().split(",")
            if len(parts) >= 4:
                try:
                    rows.append({
                        "pid": int(parts[1]),
                        "ppid": int(parts[2]),
                        "rss": int(parts[3]) if parts[3].strip().isdigit() else 0,
                        "name": parts[4] if len(parts) > 4 else "",
                    })
                except (ValueError, IndexError):
                    continue

        descendants = {pid}
        while True:
            expanded = descendants | {
                r["pid"] for r in rows if r["ppid"] in descendants
            }
            if expanded == descendants:
                break
            descendants = expanded

        for r in rows:
            if r["pid"] in descendants and r["pid"] != pid:
                rss_mb = r["rss"] / (1024 * 1024)
                total_rss += rss_mb
                children.append({
                    "pid": r["pid"],
                    "rss_mb": round(rss_mb, 1),
                    "name": r["name"],
                })
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        # wmic not available — just report the parent
        pass

    # Get parent process memory
    try:
        proc_detail = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        for line in proc_detail.stdout.strip().split("\n"):
            if str(pid) in line:
                parts = line.strip().split(",")
                if len(parts) >= 5 and parts[4].strip().replace(".", "").replace(",", "").isdigit():
                    rss_str = parts[4].strip().replace(",", "")
                    result["rss_mb"] = round(float(rss_str), 1)
                break
    except Exception:
        pass

    result["children"] = children
    result["total_rss_mb"] = round(total_rss, 1)
    return result


def _check_replay_jsonl(runtime_dir: Path) -> dict | None:
    """Read the latest replay JSONL entry for wall_s and frame count."""
    jsonl_path = None
    for candidate in [
        runtime_dir / "artifacts" / "latest-replay.jsonl",
    ]:
        if candidate.exists():
            jsonl_path = candidate
            break

    if jsonl_path is None:
        # Search artifacts directory
        artifacts_dir = runtime_dir / "artifacts"
        if artifacts_dir.exists():
            jsonl_files = sorted(artifacts_dir.glob("*.jsonl"))
            if jsonl_files:
                jsonl_path = jsonl_files[-1]

    if jsonl_path is None:
        return None

    try:
        lines = jsonl_path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
        if not lines:
            return None
        last = json.loads(lines[-1])
        return {
            "wall_s": last.get("wall_s", 0),
            "steps": last.get("steps", 0),
            "rtf": last.get("rtf", 0),
            "rss_mb": last.get("rss_mb", 0),
            "frame_seq": last.get("frame_seq", 0),
            "dropped": last.get("dropped", 0),
        }
    except (OSError, json.JSONDecodeError, IndexError):
        return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pids", nargs="*", type=int, default=[],
                   help="PID(s) of the brain process to monitor")
    p.add_argument("--launch", type=str, default=None,
                   help="Command to launch the brain process (auto-start)")
    p.add_argument("--seconds", type=float, default=43200,
                   help="Soak duration in seconds (default 43200 = 12h)")
    p.add_argument("--interval", type=float, default=5.0,
                   help="Sampling interval in seconds (default 5)")
    p.add_argument("--project", type=str, default=None,
                   help="Fly64 project root (default: auto-detect)")
    p.add_argument("--report", type=str, default=None,
                   help="Output path for the soak report JSON")
    p.add_argument("--max-rss-mb", type=float, default=12000,
                   help="RSS threshold in MB for alert (default 12000)")
    p.add_argument("--check-service", action="store_true",
                   help="Also check plugin/service_status.json health")
    args = p.parse_args()

    # Detect project root
    if args.project:
        project = Path(args.project).resolve()
    else:
        project = Path(__file__).resolve().parent.parent

    runtime_dir = project

    # Auto-launch if requested
    launched_pids = []
    if args.launch:
        print(f"[{_now_iso()}] Launching: {args.launch}", flush=True)
        if sys.platform == "win32":
            proc = subprocess.Popen(
                args.launch, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                args.launch, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        launched_pids.append(proc.pid)
        print(f"[{_now_iso()}] Launched PID={proc.pid}", flush=True)
        time.sleep(3)  # Let it start

    pids = list(args.pids) + launched_pids
    if not pids:
        print("ERROR: provide at least one PID or --launch", flush=True)
        sys.exit(1)

    # ── Soak loop ──────────────────────────────────────────────────────────
    samples = []
    start_time = time.monotonic()
    last_status_check = 0.0
    stall_count = 0

    print(f"[{_now_iso()}] Soak monitor started: target={args.seconds}s "
          f"interval={args.interval}s pids={pids}", flush=True)
    print(f"[{_now_iso()}] RSS alert threshold: {args.max_rss_mb} MB", flush=True)

    while True:
        now = time.monotonic()
        elapsed = now - start_time

        sample = {
            "ts": _now_iso(),
            "wall_s": round(elapsed, 1),
        }

        # Check all PIDs
        any_alive = False
        for pid in pids:
            tree = _collect_process_tree(pid)
            sample[f"pid_{pid}_alive"] = tree["alive"]
            sample[f"pid_{pid}_children"] = len(tree.get("children", []))
            sample[f"pid_{pid}_tree_rss_mb"] = tree.get("total_rss_mb", 0.0)
            if tree["alive"]:
                any_alive = True

        sample["any_alive"] = any_alive

        # Read replay JSONL for brain telemetry
        replay = _check_replay_jsonl(runtime_dir)
        if replay:
            sample["replay_wall_s"] = replay["wall_s"]
            sample["replay_steps"] = replay["steps"]
            sample["replay_rtf"] = replay["rtf"]
            sample["replay_rss_mb"] = replay["rss_mb"]
            sample["replay_frame_seq"] = replay["frame_seq"]
            sample["replay_dropped"] = replay["dropped"]

        # Check service health if flag set
        if args.check_service and (elapsed - last_status_check >= 60):
            last_status_check = elapsed
            status_path = project / "plugin" / "service_status.json"
            if status_path.exists():
                try:
                    status_data = json.loads(status_path.read_text(encoding="utf-8"))
                    sample["service_status"] = status_data.get("status", "unknown")
                    sample["service_cycle"] = status_data.get("cycle", -1)
                    sample["service_degraded"] = status_data.get("health", {}).get("degraded", None)
                    sample["service_alert"] = status_data.get("health", {}).get("alert", False)
                except (json.JSONDecodeError, OSError):
                    sample["service_status"] = "unreadable"
            else:
                sample["service_status"] = "absent"

        # Memory / dashboard presence check
        mem_path = project / "artifacts" / "memory_state.json"
        if mem_path.exists():
            try:
                mem_data = json.loads(mem_path.read_text(encoding="utf-8"))
                sample["memory_visited_cells"] = mem_data.get("visited_cells", -1)
                sample["memory_coverage_pct"] = mem_data.get("coverage_pct", -1)
            except (json.JSONDecodeError, OSError):
                pass

        samples.append(sample)

        # Stall detection
        if not any_alive:
            stall_count += 1
            if stall_count >= 3:
                print(f"[{_now_iso()}] ALERT: All monitored PIDs dead for "
                      f"{stall_count * args.interval:.0f}s", flush=True)
                break
        else:
            stall_count = 0

        # Progress / alerts
        if len(samples) % 60 == 0:
            pct = elapsed / max(args.seconds, 1) * 100
            tree_rss = max(
                sample.get(f"pid_{pid}_tree_rss_mb", 0) for pid in pids
            )
            rss_alert = ""
            if tree_rss > args.max_rss_mb:
                rss_alert = " [RSS ALERT]"
                print(f"[{_now_iso()}] ALERT: Process tree RSS {tree_rss:.0f} MB "
                      f"exceeds threshold {args.max_rss_mb} MB", flush=True)
            print(f"[{_now_iso()}] {elapsed:.0f}s / {args.seconds}s "
                  f"({pct:.1f}%) alive={any_alive} "
                  f"tree_rss_mb={tree_rss:.0f}{rss_alert} "
                  f"samples={len(samples)}", flush=True)

        # Exit conditions
        if elapsed >= args.seconds:
            print(f"[{_now_iso()}] Soak target reached: {args.seconds}s", flush=True)
            break

        time.sleep(args.interval)

    # ── Generate report ────────────────────────────────────────────────────
    end_time = time.monotonic()
    duration_s = end_time - start_time

    # Compute statistics
    rss_values = [
        s.get(f"pid_{pid}_tree_rss_mb", 0)
        for pid in pids
        for s in samples
        if s.get(f"pid_{pid}_alive")
    ]
    alive_samples = [s for s in samples if s.get("any_alive")]
    dead_samples = [s for s in samples if not s.get("any_alive")]

    report = {
        "soak_duration_s": round(duration_s, 1),
        "target_s": args.seconds,
        "target_hours": args.seconds / 3600,
        "pids": pids,
        "platform": sys.platform,
        "started_at": _now_iso(),
        "total_samples": len(samples),
        "alive_samples": len(alive_samples),
        "dead_samples": len(dead_samples),
        "alive_pct": round(len(alive_samples) / max(len(samples), 1) * 100, 1),
        "process_tree_peak_rss_mb": round(max(rss_values), 1) if rss_values else 0,
        "process_tree_avg_rss_mb": round(sum(rss_values) / max(len(rss_values), 1), 1) if rss_values else 0,
        "max_rss_threshold_mb": args.max_rss_mb,
        "rss_exceeded": max(rss_values) > args.max_rss_mb if rss_values else False,
        "passed": (
            duration_s >= args.seconds * 0.95  # Allow 5% tolerance
            and len(dead_samples) / max(len(samples), 1) < 0.1  # < 10% downtime
            and (not rss_values or max(rss_values) <= args.max_rss_mb)
        ),
        "stall_count": stall_count,
    }

    # Steady-state RTF (from replay data, ignoring first 10 wall seconds)
    steady_rtfs = [
        s["replay_rtf"] for s in samples
        if s.get("replay_wall_s", 0) > 10 and s.get("replay_rtf") is not None
    ]
    if steady_rtfs:
        report["steady_rtf_min"] = round(min(steady_rtfs), 3)
        report["steady_rtf_avg"] = round(sum(steady_rtfs) / len(steady_rtfs), 3)
        report["steady_rtf_max"] = round(max(steady_rtfs), 3)

    # Output
    report_path = args.report or str(runtime_dir / "artifacts" / "soak-report.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[{_now_iso()}] Soak report: {report_path}", flush=True)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)

    # Exit with status
    if report["passed"]:
        print(f"[{_now_iso()}] SOAK PASSED: {duration_s:.0f}s >= {args.seconds * 0.95:.0f}s target",
              flush=True)
        sys.exit(0)
    else:
        print(f"[{_now_iso()}] SOAK FAILED: check report for details", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()