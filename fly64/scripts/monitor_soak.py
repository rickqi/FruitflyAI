"""Measure the running project's process tree and native acknowledgements."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from fly64.bridge import SharedBridge

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("pids", nargs="+", type=int)
p.add_argument("--seconds", type=float, default=610)
args = p.parse_args()
root = Path(__file__).resolve().parent.parent
samples = []
with SharedBridge(root / "runtime/fly64_bridge.bin", create=False) as bridge:
    while True:
        lines = (root / "artifacts/latest-replay.jsonl").read_text().splitlines()
        if not lines:
            time.sleep(1); continue
        last = json.loads(lines[-1])
        table = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss="], text=True)
        processes = [tuple(map(int, line.split())) for line in table.splitlines()]
        descendants = set(args.pids)
        while True:
            expanded = descendants | {pid for pid, parent, rss in processes if parent in descendants}
            if expanded == descendants: break
            descendants = expanded
        total = sum(rss for pid, parent, rss in processes if pid in descendants) / 1024
        status = bridge.game_status()
        samples.append(dict(wall_s=last["wall_s"], tree_rss_mib=total, **status))
        if last["wall_s"] >= args.seconds:
            logs = [json.loads(line) for line in lines]
            steady = [r for r in logs if r["wall_s"] > 10]
            report = dict(duration_s=last["wall_s"], neural_steps=last["steps"],
                final_real_time_factor=last["rtf"],
                minimum_steady_real_time_factor=min(r["rtf"] for r in steady),
                simulator_peak_rss_mb=max(r["rss_mb"] for r in logs),
                sampled_process_tree_peak_rss_mib=max(s["tree_rss_mib"] for s in samples),
                process_tree_sampling_start_s=samples[0]["wall_s"],
                dropped_dashboard_updates=last["dropped"],
                requested_jump_updates=sum(r["jump"] for r in logs),
                forward_updates=sum(r["y"] > 0 for r in logs),
                steering_range=[min(r["x"] for r in logs), max(r["x"] for r in logs)],
                native_ack_samples=len(samples),
                native_live_samples=sum(s["state"] == 1 for s in samples),
                frames_captured=last["frame_seq"] // 2,
                passed=last["wall_s"] >= 600 and last["frame_seq"] > 10000 and
                    max(s["tree_rss_mib"] for s in samples) < 12000 and status["state"] == 1)
            (root / "artifacts/soak-report.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2)); break
        if not any(pid == args.pids[0] for pid, _, _ in processes):
            raise RuntimeError("Simulator exited before soak target")
        time.sleep(1)
