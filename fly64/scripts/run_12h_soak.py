#!/usr/bin/env python3
"""12-hour soak run orchestrator for the Fly64 brain.

Starts the brain process (--synthetic mode or real SM64 bridge), monitors
it with monitor_soak.py, and produces a soak report.

Usage:
    # 12h soak with synthetic world (no SM64 needed):
    python scripts/run_12h_soak.py --synthetic

    # 12h soak with real SM64 bridge:
    python scripts/run_12h_soak.py

    # Quick 10-minute pre-check:
    python scripts/run_12h_soak.py --synthetic --duration 600

    # With existing PID:
    python scripts/run_12h_soak.py --pid 12345

Output:
    artifacts/soak-report.json     — structured pass/fail result
    artifacts/soak-samples.jsonl   — every sample from the monitor
    runtime/soak_{ts}.log          — combined log
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration", type=float, default=43200,
                   help="Soak duration in seconds (default 43200 = 12h)")
    p.add_argument("--interval", type=float, default=5.0,
                   help="Sampling interval in seconds (default 5)")
    p.add_argument("--synthetic", action="store_true",
                   help="Use synthetic world (no SM64 bridge needed)")
    p.add_argument("--bridge", type=str, default=None,
                   help="Bridge path (default: auto)")
    p.add_argument("--pid", type=int, default=None,
                   help="Monitor an existing PID instead of launching")
    p.add_argument("--http-port", type=int, default=8765,
                   help="Dashboard HTTP port")
    p.add_argument("--ws-port", type=int, default=8766,
                   help="WebSocket port")
    p.add_argument("--max-rss-mb", type=float, default=12000,
                   help="RSS alert threshold in MB")
    p.add_argument("--check-service", action="store_true",
                   help="Also check plugin service health")
    p.add_argument("--output", type=str, default=None,
                   help="Output directory for report (default: project/artifacts/)")
    args = p.parse_args()

    project = Path(__file__).resolve().parent.parent

    # Create temp paths
    bridge_path = args.bridge or str(project / "runtime" / "soak_bridge.bin")
    record_path = str(project / "runtime" / "soak_record")
    Path(bridge_path).parent.mkdir(parents=True, exist_ok=True)

    # Build launch command
    launch_cmd = None
    launched_proc = None

    if args.pid is not None:
        # Monitor existing process
        pids = [args.pid]
        print(f"[{_now_iso()}] Monitoring existing PID {args.pid}", flush=True)
    else:
        # Launch brain process
        brain_cmd = [
            sys.executable, "-m", "fly64.main",
            "--bridge", bridge_path,
            "--record", record_path,
            "--http-port", str(args.http_port),
            "--ws-port", str(args.ws_port),
            "--duration", str(args.duration + 60),  # allow extra time
            "--no-browser",
        ]
        if args.synthetic:
            brain_cmd.append("--synthetic")

        launch_cmd = " ".join(brain_cmd)
        pids = []
        print(f"[{_now_iso()}] Launching brain: {launch_cmd}", flush=True)
        print(f"[{_now_iso()}] Using bridge: {bridge_path}", flush=True)

        # Start the brain process
        launched_proc = subprocess.Popen(
            brain_cmd,
            cwd=str(project),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pids = [launched_proc.pid]
        print(f"[{_now_iso()}] Brain started: PID={launched_proc.pid}", flush=True)

        # Wait for the dashboard to come up
        import urllib.request
        dashboard_url = f"http://127.0.0.1:{args.http_port}/"
        deadline = time.monotonic() + 30
        dashboard_ok = False
        while time.monotonic() < deadline:
            if launched_proc.poll() is not None:
                print(f"[{_now_iso()}] Brain exited prematurely! "
                      f"Return code: {launched_proc.returncode}", flush=True)
                break
            try:
                resp = urllib.request.urlopen(dashboard_url, timeout=2)
                if resp.status == 200:
                    dashboard_ok = True
                    print(f"[{_now_iso()}] Dashboard reachable at {dashboard_url}", flush=True)
                    break
            except Exception:
                pass
            time.sleep(1)

        if not dashboard_ok and launched_proc.poll() is None:
            print(f"[{_now_iso()}] Dashboard not reachable within 30s, "
                  f"but process seems alive — continuing", flush=True)

    # Wait a moment for initialisation
    time.sleep(2)

    # ── Run the soak monitor ───────────────────────────────────────────────
    output_dir = Path(args.output or (project / "artifacts"))
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "soak-report.json"
    samples_path = output_dir / "soak-samples.jsonl"

    monitor_args = [
        sys.executable, str(project / "scripts" / "monitor_soak.py"),
        *[str(pid) for pid in pids],
        "--seconds", str(args.duration),
        "--interval", str(args.interval),
        "--project", str(project),
        "--report", str(report_path),
        "--max-rss-mb", str(args.max_rss_mb),
    ]
    if args.check_service:
        monitor_args.append("--check-service")

    print(f"[{_now_iso()}] Starting soak monitor: {' '.join(monitor_args)}", flush=True)
    print(f"[{_now_iso()}] Soak target: {args.duration}s ({args.duration/3600:.1f}h)", flush=True)

    # Run monitor as subprocess and capture its output
    start_time = time.monotonic()
    monitor_proc = subprocess.Popen(
        monitor_args,
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Write samples to JSONL as they arrive
    sample_count = 0
    for line in monitor_proc.stdout or []:
        # Write to samples file
        if samples_path and line.strip():
            try:
                data = json.loads(line)
                with open(samples_path, "a", encoding="utf-8") as sf:
                    sf.write(json.dumps(data, ensure_ascii=False) + "\n")
                sample_count += 1
            except (json.JSONDecodeError, OSError):
                pass
        sys.stdout.write(line)
        sys.stdout.flush()

    monitor_proc.wait()
    elapsed = time.monotonic() - start_time
    print(f"[{_now_iso()}] Monitor finished: return code={monitor_proc.returncode}, "
          f"duration={elapsed:.0f}s, samples={sample_count}", flush=True)

    # Cleanup launched process
    if launched_proc is not None and launched_proc.poll() is None:
        print(f"[{_now_iso()}] Cleaning up brain process PID={launched_proc.pid}", flush=True)
        if sys.platform == "win32":
            launched_proc.terminate()
        else:
            os.kill(launched_proc.pid, signal.SIGTERM)
        try:
            launched_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            launched_proc.kill()
            launched_proc.wait()

    # Read and display final report
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        print("=" * 70, flush=True)
        print("SOAK RESULT SUMMARY", flush=True)
        print("=" * 70, flush=True)
        print(f"  Duration:      {report.get('soak_duration_s', '?')}s / {args.duration}s target", flush=True)
        print(f"  Target hours:  {report.get('target_hours', '?'):.1f}h", flush=True)
        print(f"  Alive samples: {report.get('alive_pct', '?')}%", flush=True)
        print(f"  Peak RSS:      {report.get('process_tree_peak_rss_mb', '?')} MB", flush=True)
        print(f"  RSS exceeded:  {report.get('rss_exceeded', '?')}", flush=True)
        print(f"  Passed:        {'✅ YES' if report.get('passed') else '❌ NO'}", flush=True)
        print(f"  Report file:   {report_path}", flush=True)
        print("=" * 70, flush=True)

        if report.get("passed"):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        print(f"[{_now_iso()}] No report file produced at {report_path}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()