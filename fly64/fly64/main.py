from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import tempfile
import threading
import time
import webbrowser
import json
import math
import signal
import resource
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from websockets.asyncio.server import serve

from .bridge import CHANNELS, HEIGHT, WIDTH, SharedBridge
from .model import FlyModel
from .retina import BASES, CALIBRATION
from .telemetry import Observatory
from .memory import MemoryController

class EscapeEventBuffer:
    """Ring buffer of last 200 escape events.

    Each event records: timestamp, reason (stuck/fallen/flow/cliff),
    duration, position (x,z), outcome (resolved/still_escaping).
    """

    def __init__(self, maxlen: int = 200):
        self._events: deque = deque(maxlen=maxlen)

    def start_event(self, timestamp: float, reason: str,
                    position_x: float, position_z: float) -> dict:
        """Record the start of a new escape event."""
        event: dict = {
            "timestamp": round(timestamp, 2),
            "reason": reason,
            "duration": 0.0,
            "position": {"x": round(position_x, 1), "z": round(position_z, 1)},
            "outcome": "still_escaping",
            "distance_moved": 0.0,
        }
        self._events.append(event)
        return event

    def update_current(self, dt: float) -> None:
        """Accumulate tick duration onto the current (latest) event."""
        if self._events:
            self._events[-1]["duration"] = round(
                self._events[-1]["duration"] + dt, 3)

    def resolve_current(self, distance_moved: float) -> None:
        """Mark the current event as resolved and record distance covered."""
        if self._events:
            self._events[-1]["outcome"] = "resolved"
            self._events[-1]["distance_moved"] = round(distance_moved, 1)

    def get_recent(self, n: int = 100) -> list[dict]:
        """Return the last *n* events as a list."""
        events = list(self._events)
        return events[-n:]

    def clear(self) -> None:
        self._events.clear()


class DashboardHTTP(BaseHTTPRequestHandler):
    html = b""
    positions = b""
    metadata = b"{}"
    bridge = None
    assets = {}
    memory_json = b"{}"
    flow_json = b"{}"
    events_json = b"{}"
    history_json = b"[]"
    signal_history = deque(maxlen=600)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            body, mime = self.html, "text/html; charset=utf-8"
        elif path == "/positions.bin":
            body, mime = self.positions, "application/octet-stream"
        elif path == "/metadata.json":
            body, mime = self.metadata, "application/json"
        elif path in self.assets:
            body, mime = self.assets[path]
        elif path == "/bridge-status.json" and self.bridge is not None:
            body, mime = json.dumps(self.bridge.game_status()).encode(), "application/json"
        elif path == "/trajectory.json":
            body, mime = self.trajectory, "application/json"
        elif path == "/memory.json":
            body, mime = self.memory_json, "application/json"
        elif path == "/flow.json":
            body, mime = self.flow_json, "application/json"
        elif path == "/events.json":
            body, mime = self.events_json, "application/json"
        elif path == "/history.json":
            body, mime = self.history_json, "application/json"
        elif path == "/trajectory-list.json":
            import glob as _glob
            arts = Path(__file__).resolve().parent.parent / "artifacts"
            files = sorted(_glob.glob(str(arts / "*.trajectory.npz")) + _glob.glob(str(arts / "latest-replay.trajectory.npz")))
            listing = []
            for f in files:
                p = Path(f)
                size = p.stat().st_size
                mtime = p.stat().st_mtime
                import datetime as _dt
                listing.append({"name": p.name, "size": size, "time": _dt.datetime.fromtimestamp(mtime).isoformat()})
            body, mime = json.dumps(listing, default=str).encode(), "application/json"
        elif path == "/trajectory-load":
            from urllib.parse import parse_qs as _pq
            qs = _pq(urlsplit(self.path).query)
            fname = qs.get("file", [None])[0]
            if fname:
                tpath = Path(__file__).resolve().parent.parent / "artifacts" / fname
                if tpath.exists():
                    import numpy as _np
                    data = _np.load(tpath)
                    pts = [{"t": float(t), "x": float(x), "y": float(y), "z": float(z), "heading": float(h),
                            "ctrl_x": int(cx), "ctrl_y": int(cy), "game_frame": int(gf)}
                           for t, x, y, z, h, cx, cy, gf in zip(data["t"], data["x"], data["y"], data["z"], data["heading"], data["ctrl_x"], data["ctrl_y"], data["game_frame"])]
                    body, mime = json.dumps(pts, default=str).encode(), "application/json"
                else:
                    body, mime = json.dumps({"error": "file not found"}).encode(), "application/json"
            else:
                body, mime = json.dumps({"error": "no file specified"}).encode(), "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class LocalHTTPServer(ThreadingHTTPServer):
    """HTTP server that avoids macOS's blocking reverse-DNS lookup at bind time."""

    def server_bind(self):
        self.socket.setsockopt(__import__("socket").SOL_SOCKET, __import__("socket").SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


class SyntheticWorld:
    """ROM-free closed-loop visual source used for integration tests."""

    def __init__(self):
        self.heading = 0.0
        self.distance = 0.0
        self.jump_phase = 0.0

    def frame(self, x: int, y: int, jump: bool) -> np.ndarray:
        self.heading += x / 70.0 * 0.035
        self.distance += y / 70.0 * 0.05
        if jump and self.jump_phase == 0:
            self.jump_phase = 0.01
        if self.jump_phase:
            self.jump_phase += 0.12
            if self.jump_phase > np.pi:
                self.jump_phase = 0
        image = np.empty((HEIGHT, WIDTH, 3), np.uint8)
        yy, xx = np.mgrid[0:128, 0:128]
        u, v = (xx+.5)/64-1, 1-(yy+.5)/64
        for face, (right, up, forward) in enumerate(BASES):
            rays = forward + u[...,None]*right + v[...,None]*up
            az = np.arctan2(rays[...,0], rays[...,2]) + self.heading
            el = rays[...,1]/np.linalg.norm(rays,axis=-1)
            ground = el < .04*np.sin(self.jump_phase)
            color = np.where(ground[...,None], [70,155,72], [80,165,245]).astype(np.uint8)
            stripe = (np.sin(az*8+self.distance)>.8) & (np.abs(el)<.6)
            color[stripe] = [82,48,25]
            image[(face//3)*128:(face//3+1)*128,(face%3)*128:(face%3+1)*128] = color
        return image


class Replay:
    def __init__(self, path: Path, seed=64, fixture=False, parameters=None):
        self.path = path
        self.seed = seed
        self.fixture = fixture
        self.parameters = parameters or dict(tonic_current=.180, synaptic_gain=1.50)
        self.chunks = []
        self.writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="replay")
        self.writes = []
        self.times: list[float] = []
        self.frames: list[np.ndarray] = []
        self.controls: list[tuple[int, int, int]] = []
        self.spikes: list[np.ndarray] = []
        self.frame_indices: list[int] = []
        self.camera: list[tuple] = []

    def add(self, timestamp, frame, control, spikes, camera=None):
        self.times.append(timestamp)
        if not self.frames or not np.array_equal(frame, self.frames[-1]):
            self.frames.append(frame.copy())
        self.frame_indices.append(len(self.frames)-1)
        self.camera.append(tuple((camera or {}).get("pose", [0.,0.,0.,0.])) +
                           ((camera or {}).get("game_frame", 0),))
        self.controls.append((control.x, control.y, int(control.jump)))
        self.spikes.append(spikes.astype(np.uint32))
        if len(self.times) >= 500:
            self.save()

    def save(self):
        if not self.frames:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        offsets = np.zeros(len(self.spikes) + 1, np.uint64)
        for i, values in enumerate(self.spikes):
            offsets[i + 1] = offsets[i] + len(values)
        flat = np.concatenate(self.spikes) if offsets[-1] else np.empty(0, np.uint32)
        target = self.path.with_name(f"{self.path.stem}-{len(self.chunks):05d}.npz")
        payload = dict(timestamps=np.asarray(self.times), frames=np.asarray(self.frames),
            frame_indices=np.asarray(self.frame_indices, np.uint32), camera=np.asarray(self.camera),
            controls=np.asarray(self.controls, np.int8), spike_offsets=offsets, spikes=flat,
            seed=np.int64(self.seed), fixture=np.bool_(self.fixture), schema=np.int64(3),
        )
        self.chunks.append(target.name)
        manifest = dict(schema=3, retina=CALIBRATION,
            seed=self.seed, fixture=self.fixture, parameters=self.parameters,
            chunks=list(self.chunks))
        self.writes.append(self.writer.submit(self._write_chunk, target, payload, manifest))
        self.times.clear(); self.frames.clear(); self.controls.clear(); self.spikes.clear()
        self.frame_indices.clear(); self.camera.clear()

    def _write_chunk(self, target, payload, manifest):
        # Publish only complete archives; readers never see a half-written NPZ.
        temporary = target.with_suffix(".npz.partial")
        with temporary.open("wb") as output:
            np.savez_compressed(output, **payload)
        temporary.replace(target)
        index = self.path.with_suffix(".index.json")
        temporary_index = index.with_suffix(".json.partial")
        temporary_index.write_text(json.dumps(manifest, indent=2))
        temporary_index.replace(index)

    def close(self):
        self.save()
        self.writer.shutdown(wait=True)
        for future in self.writes:
            future.result()


def start_http(project: Path, model, port: int, ws_port: int) -> ThreadingHTTPServer:
    DashboardHTTP.html = (project / "web" / "index.html").read_bytes()
    DashboardHTTP.positions = model.positions.astype("<f4", copy=False).tobytes()
    DashboardHTTP.assets = {
        "/dashboard.js": ((project / "web/dashboard.js").read_bytes(), "text/javascript"),
        "/dashboard.css": ((project / "web/dashboard.css").read_bytes(), "text/css"),
        "/memory-heatmap.js": ((project / "web/memory-heatmap.js").read_bytes(), "text/javascript"),
        "/trajectory.html": ((project / "web/trajectory.html").read_bytes(), "text/html"),
        "/measured.bin": (model.position_measured.astype(np.uint8).tobytes(), "application/octet-stream"),
    }
    DashboardHTTP.metadata = json.dumps(dict(n=model.n, ws=ws_port, label=model.label,
        region_names=model.region_names.tolist(), retina=CALIBRATION,
        measured=int(model.position_measured.sum()),
        groups={key: ids.tolist() for key, ids in Observatory(model).groups.items()})).encode()
    server = LocalHTTPServer(("127.0.0.1", port), DashboardHTTP)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def open_dashboard(url: str, project: Path):
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome):
        profile = Path(tempfile.mkdtemp(prefix="chrome-dashboard-", dir=project / "runtime"))
        process = subprocess.Popen([
            chrome, f"--app={url}", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check",
            "--window-size=840,900", "--window-position=620,38",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (project / "runtime/dashboard.pid").write_text(str(process.pid))
        return process
    else:
        webbrowser.open(url)
        return None


async def run(args) -> None:
    project = Path(__file__).resolve().parent.parent
    cache = project / ".cache" / "malecns"
    model = FlyModel(cache, demo=args.demo_model)
    bridge = SharedBridge(args.bridge, create=True)
    DashboardHTTP.bridge = bridge
    replay = Replay(args.record, model.seed, args.demo_model,
                    dict(tonic_current=model.tonic_current, synaptic_gain=model.synaptic_gain))
    clients: set = set()
    packet_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)
    started = time.monotonic()
    synthetic = SyntheticWorld() if args.synthetic else None
    latest_control = None
    last_frame_seq = -1
    dropped = 0
    observatory = Observatory(model)
    pending_jump = False
    dash_seq = 0
    DashboardHTTP.trajectory_points = []
    DashboardHTTP.memory_json = b"{}"
    memory_ctrl = MemoryController()
    escape_x = 0
    escape_toggle_timer = 0.0
    escape_buffer = EscapeEventBuffer()
    event_counters = {"total_escapes": 0, "total_falls": 0,
                      "total_flow_avoid": 0, "current_stuck_duration": 0.0}
    current_escape_event = None
    previous_escape: bool = False
    event_last_pos = (0.0, 0.0)
    previous_cliff_confirmed: bool = False
    cliff_recovery_timer: float = 0.0
    cliff_turn_bias: float = 0.0
    previous_anomaly_state: str = ""

    async def ws_handler(socket):
        clients.add(socket)
        try:
            await socket.wait_closed()
        finally:
            clients.discard(socket)

    async def broadcaster():
        while True:
            packet = await packet_queue.get()
            if clients:
                await asyncio.gather(*(c.send(packet) for c in tuple(clients)), return_exceptions=True)

    http = start_http(project, model, args.http_port, args.ws_port)
    ws_server = await serve(ws_handler, "127.0.0.1", args.ws_port, max_size=None)
    url = f"http://127.0.0.1:{args.http_port}/"
    print(f"Fly64 dashboard: {url}")
    print(f"Fly64 model: {model.label}; {model.n:,} neurons; {model.w.nnz:,} edges")
    dashboard_process = open_dashboard(url, project) if not args.no_browser else None
    broadcast_task = asyncio.create_task(broadcaster())
    stopping = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stopping.set)
    log_path = args.record.with_suffix(".jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("w", buffering=1)

    try:
        next_tick = time.monotonic()
        last_publish = 0.0
        frame = np.zeros((HEIGHT, WIDTH, CHANNELS), np.uint8)
        while not stopping.is_set() and (args.duration <= 0 or time.monotonic() - started < args.duration):
            tick_start = time.monotonic()
            if synthetic is not None:
                x = latest_control.x if latest_control else 0
                y = latest_control.y if latest_control else 0
                jump = latest_control.jump if latest_control else False
                frame = synthetic.frame(x, y, jump)
                bridge.write_frame(frame.tobytes())
            seq, pixels = bridge.read_frame()
            if seq != last_frame_seq:
                frame = np.frombuffer(pixels, np.uint8).reshape(HEIGHT, WIDTH, CHANNELS).copy()
                last_frame_seq = seq
            model.escape_mode = memory_ctrl.escape_behavior
            pose_ev = bridge.frame_metadata.get("pose", [0, 0, 0, 0])
            heading = pose_ev[3]
            control, spikes = model.step(frame, model.step_count * model.dt,
                                         novelty=memory_ctrl.novelty,
                                         heading=heading)

            # ---- Pre-emptive cliff avoidance (fires BEFORE escape, highest priority) ----
            cliff_triggered = False
            if model.step_count > 10:
                # Ramp suppression: if ground_angle > 0.3 (slope or flat), don't trigger cliff
                is_ramp = model.ramp_score > 0.5 or model.ground_angle > 0.3
                # Ramp stuck override: if stuck on ramp >30s, allow turning
                ramp_stuck_override = is_ramp and memory_ctrl.stuck_duration > 30.0
                # 1. High-confidence cliff: cliff_confirmed AND rapid green drop
                if (not is_ramp or ramp_stuck_override) and model.cliff_confirmed and model.cliff_rate < -0.03:
                    turn_dir = -60 if model.rng.random() < 0.5 else 60
                    control.x = turn_dir
                    control.y = -10  # brief reverse in SM64
                    escape_toggle_timer = 0.5  # shorten next turn cycle
                    cliff_triggered = True
                    cliff_turn_bias = float(turn_dir)
                    cliff_recovery_timer = 0.0
                # 2. Low-confidence cliff: raw cliff low but no rapid drop (suppressed on ramps)
                elif (not is_ramp or ramp_stuck_override) and model.flow_cliff < 0.25:
                    control.x = int(control.x * 1.5)
                    control.y = max(0, control.y - 20)
                    cliff_triggered = True
                    cliff_turn_bias = control.x * 0.3
                    cliff_recovery_timer = 0.0
                # 3. Cliff recovery: was True, now False
                elif previous_cliff_confirmed and not model.cliff_confirmed:
                    cliff_recovery_timer += model.dt
                    fade = min(1.0, cliff_recovery_timer / 0.5)
                    if abs(cliff_turn_bias) > 1:
                        cliff_turn_bias *= (1.0 - fade * 0.8)
                        control.x = int(cliff_turn_bias)
                    if control.y < 8:
                        control.y = 8
                else:
                    if cliff_recovery_timer > 0:
                        cliff_recovery_timer = min(cliff_recovery_timer + model.dt, 0.5)
                        if cliff_recovery_timer >= 0.5:
                            cliff_turn_bias = 0.0
                            cliff_recovery_timer = 0.0

            # Ground angle gate: if terrain says cliff but ground_angle says flat,
            # override cliff_triggered — the classifier is wrong
            if cliff_triggered and model.ground_angle > 0.3:
                cliff_triggered = False

            # If cliff triggered, suppress escape behavior for this tick
            if cliff_triggered:
                if not previous_escape and not current_escape_event:
                    current_escape_event = escape_buffer.start_event(
                        round(tick_start - started, 2), "cliff",
                        pose_ev[0], pose_ev[2])
                    event_counters["total_escapes"] += 1
                    event_counters["total_flow_avoid"] += 1
                memory_ctrl.escape_behavior = False

            previous_cliff_confirmed = model.cliff_confirmed

            # ---- Reflex escape circuits (after cliff, before normal escape) ----
            reflex_override = False
            reflex_active = memory_ctrl.reflex.update(
                model.dt,
                memory_ctrl.anomaly_state,
                model.rng.integers,
            )
            if reflex_active:
                action = memory_ctrl.reflex_action
                if action["active"]:
                    control.x = action["control_x"]
                    control.y = action["control_y"]
                    control.jump = action["jump"]
                    reflex_override = True
                    memory_ctrl.escape_behavior = True
                    escape_toggle_timer = 0.0  # reset normal escape timer

            # ---- Health-score aggressive mode (after reflex, before collision) ----
            _health = memory_ctrl.health_score
            if _health < 0.3:
                # 1.5x turn multiplier + halved reflex cooldowns
                if not reflex_override:
                    control.x = int(np.clip(control.x * 1.5, -80, 80))
                memory_ctrl.reflex.set_aggressive_mode(True)
            else:
                memory_ctrl.reflex.set_aggressive_mode(False)

            # ---- Pre-emptive collision avoidance (fires when NOT escaping/reflex) ----
            if not memory_ctrl.escape_behavior and not cliff_triggered:
                # 1. Strong asymmetry > 0.3: bias turn AWAY from obstacle
                if model.flow_asymmetry > 0.3:
                    control.x = min(control.x if control.x < 0 else -max(abs(control.x), 8) - 10, -8)
                elif model.flow_asymmetry < -0.3:
                    control.x = max(control.x if control.x > 0 else max(abs(control.x), 8) + 10, 8)
                # 2. Looming > 0.4: reduce forward speed
                if model.flow_looming > 0.4:
                    control.y = int(control.y * 0.3)

            # ---- Scene-change suppression: new area, give it time before escaping ----
            if model.scene_change and memory_ctrl.stuck_score < 0.5:
                memory_ctrl.escape_behavior = False
                escape_toggle_timer = 0.0

            # Escape control: override when stuck & looping (skip when reflex active)
            pose_ev = bridge.frame_metadata.get("pose", [0, 0, 0, 0])
            if memory_ctrl.escape_behavior and not reflex_override:
                escape_toggle_timer += model.dt
                model.escape_mode = True
                if memory_ctrl.fallen:
                    # Fall recovery: jump + forward burst
                    # Initialize turn direction on first fallen cycle
                    if escape_x == 0:
                        escape_x = -50
                    if escape_toggle_timer < 0.4:
                        # Phase 1: Jump, no movement
                        control.x = 0; control.y = 0; control.jump = True
                    elif escape_toggle_timer < 2.4:
                        # Phase 2: Extended forward burst (2s) with alternating turn direction
                        control.x = escape_x; control.y = 80; control.jump = True
                    else:
                        escape_toggle_timer = 0.0
                        # Mirror turn direction for next cycle
                        escape_x = -escape_x
                        # Reverse-before-jump when stuck-in-fall >30s
                        if memory_ctrl.stuck_duration > 30:
                            control.x = -escape_x  # reverse away from obstacle
                            control.y = -40        # backward burst
                        # else: brief reset tick, next cycle starts immediately
                elif memory_ctrl.forced_bold_explore:
                    # ---- forced_bold_explore breakout ----
                    # Force large turn (x=±69) + extended forward burst (y=70 for 2s)
                    # to break out of nested loop cycles where the agent is visually
                    # stagnant in a tiny area (scene_change_rate<0.05 for >10s,
                    # visited_cells<20). Dead-end penalty is already reduced in
                    # novelty_direction() via the forced_bold_explore flag.
                    if escape_toggle_timer < 0.5:
                        # Phase 1: Sharp turn to maximum angle, no forward
                        if escape_toggle_timer < model.dt:
                            # Choose max turn, alternating sign from previous bold cycle
                            if escape_x == 0:
                                escape_x = 69
                            escape_x = 69
                            if model.rng.random() < 0.5:
                                escape_x = -escape_x
                        control.x = escape_x; control.y = 0
                    elif escape_toggle_timer < 2.5:
                        # Phase 2: Extended forward burst (2s) with slight counter-steer
                        control.x = -escape_x // 3; control.y = 70
                    else:
                        escape_toggle_timer = 0.0; control.jump = True
                else:
                    # ---- Open-area stuck override ----
                    # When wall≈0 && asymmetry≈0 && stuck>120s, force straight forward
                    _open_stuck = (model.wall_score < 0.1 and
                                   abs(model.flow_asymmetry) < 0.05 and
                                   memory_ctrl.stuck_duration > 120)
                    # ---- Revisit-penalty escape modulation ----
                    _revisit_boost = 1.0 + max(0.0, memory_ctrl.revisit_penalty - 0.3) * 1.0
                    if escape_toggle_timer < 0.8:
                        if escape_toggle_timer < model.dt:
                            avoid = memory_ctrl.failures.avoid_direction(pose_ev[0], pose_ev[2], pose_ev[3])
                            asym = model.true_asymmetry  # self-motion corrected
                            # Novelty-biased escape: prefer high-novelty directions
                            novelty_bias = memory_ctrl.spatial.novelty_direction(
                                pose_ev[0], pose_ev[2], pose_ev[3],
                                dead_end_keys=memory_ctrl.dead_end_cells,
                                scene_change_rate=model.scene_change_rate,
                                forced_bold_explore=memory_ctrl.forced_bold_explore)
                            if avoid > 0:
                                escape_x = int(60 * _revisit_boost)
                            elif asym > 0.12:
                                escape_x = int(60 * _revisit_boost)
                            elif asym < -0.12:
                                escape_x = int(-60 * _revisit_boost)
                            elif abs(novelty_bias) > 0.2:
                                # Novelty bias takes priority (>0.2 threshold)
                                escape_x = int(novelty_bias * 70 * _revisit_boost)
                            else:
                                escape_x = model.rng.integers(int(40 * _revisit_boost), int(70 * _revisit_boost))
                                if model.rng.random() < 0.5:
                                    escape_x = -escape_x
                        control.x = int(np.clip(escape_x // (4 if _open_stuck else 1), -80, 80))
                        control.y = 0
                    elif escape_toggle_timer < 1.6:
                        # Open-area stuck: no obstacles, just stuck → go straight
                        if _open_stuck:
                            # Ramp escape: if stuck on ramp >180s, sharp turn instead
                            if model.ramp_score > 0.5 and memory_ctrl.stuck_duration > 180:
                                control.x = model.rng.integers(60, 80) * (-1 if model.rng.random() < 0.5 else 1)
                                control.y = 40
                            else:
                                control.x = 0
                                control.y = 80
                        else:
                            control.x = int(-escape_x // 2)
                            control.y = int(70 * _revisit_boost)
                    else:
                        escape_toggle_timer = 0.0; control.jump = True
            else:
                escape_toggle_timer = 0.0

            # ---- Escape event tracking ----
            currently_escaping = memory_ctrl.escape_behavior
            if currently_escaping and not previous_escape:
                # Escape just started — determine reason
                if reflex_override:
                    reason = f"reflex_{memory_ctrl.reflex_type}" if memory_ctrl.reflex_type else "reflex"
                elif memory_ctrl.fallen:
                    reason = "fallen"
                    event_counters["total_falls"] += 1
                elif memory_ctrl.stuck_score > 0.8:
                    reason = "stuck"
                elif memory_ctrl.cliff_detected:
                    reason = "cliff"
                elif model.true_asymmetry > 0.3:
                    reason = "flow"
                else:
                    reason = "stuck"
                current_escape_event = escape_buffer.start_event(
                    round(tick_start - started, 2), reason,
                    pose_ev[0], pose_ev[2])
                event_counters["total_escapes"] += 1
                event_last_pos = (pose_ev[0], pose_ev[2])
            if currently_escaping:
                escape_buffer.update_current(model.dt)
            elif previous_escape:
                # Escape just ended — resolve
                dx = pose_ev[0] - event_last_pos[0]
                dz = pose_ev[2] - event_last_pos[1]
                dist = math.sqrt(dx * dx + dz * dz)
                escape_buffer.resolve_current(dist)
                current_escape_event = None
            previous_escape = currently_escaping
            event_counters["current_stuck_duration"] = round(memory_ctrl.stuck_duration, 3)
            if model.flow_asymmetry > 0.3 or model.flow_cliff < 0.3:
                if not current_escape_event and not currently_escaping:
                    event_counters["total_flow_avoid"] += 1

            latest_control = control
            bridge.write_control(control.x, control.y, control.jump)
            replay.add((model.step_count - 1) * model.dt, frame, control, spikes, bridge.frame_metadata)
            observatory.observe(frame, seq, control, spikes, bridge.game_status())
            pending_jump |= control.jump
            latency_ms = (time.monotonic() - tick_start) * 1000
            rtf = model.step_count * model.dt / max(time.monotonic() - started, .02)

            if tick_start - last_publish >= (0.2 if rtf < 0.95 else 0.1):
                last_publish = tick_start
                dash_seq += 1
                if packet_queue.full():
                    try:
                        packet_queue.get_nowait()
                        dropped += 1
                    except asyncio.QueueEmpty:
                        pass
                packet = observatory.packet(dash_seq, rtf=rtf, latency_ms=latency_ms, dropped=dropped,
                    rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e6)
                packet_queue.put_nowait(packet)
                log.write(json.dumps(dict(wall_s=tick_start-started, steps=model.step_count, rtf=rtf,
                    latency_ms=latency_ms, rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e6,
                    x=control.x, y=control.y, jump=pending_jump, frame_seq=int(last_frame_seq),
                    dropped=dropped, visual_contrast=float(model.temporal_energy),
                    camera=bridge.frame_metadata, game=bridge.game_status()), default=str) + "\n")
                pending_jump = False
                # Record trajectory
                pose = bridge.frame_metadata.get("pose", [0,0,0,0])
                gm = bridge.game_status()
                DashboardHTTP.trajectory_points.append({
                    "t": round(tick_start - started, 2),
                    "x": round(pose[0], 1), "y": round(pose[1], 1), "z": round(pose[2], 1),
                    "heading": round(pose[3], 3),
                    "ctrl_x": control.x, "ctrl_y": control.y, "jump": control.jump,
                    "game_frame": bridge.frame_metadata.get("game_frame", 0),
                })
                if len(DashboardHTTP.trajectory_points) > 6000:
                    DashboardHTTP.trajectory_points = DashboardHTTP.trajectory_points[-6000:]
                DashboardHTTP.trajectory = json.dumps(DashboardHTTP.trajectory_points[-500:], default=str).encode()

                # Update spatial memory
                memory_ctrl.update(
                    temporal_energy=model.temporal_energy,
                    frame_seq=last_frame_seq,
                    forward_rate=getattr(control, 'forward_rate', 0.0),
                    x=pose[0], z=pose[2], pos_y=pose[1],
                    heading=pose[3],
                    flow_asymmetry=model.flow_asymmetry,
                    flow_looming=model.flow_looming,
                    flow_cliff=model.flow_cliff,
                    scene_change_rate=model.scene_change_rate,
                    ground_angle=model.ground_angle,
                    scene_sig=model.scene_sig,
                    wall_score=model.wall_score,
                    ramp_score=model.ramp_score,
                    heading_rate=model.heading_rate,
                    control_x=control.x,
                )
                xs, zs, heats = memory_ctrl.spatial.get_heatmap()
                DashboardHTTP.memory_json = json.dumps({
                    "stuck_score": round(memory_ctrl.stuck_score, 3),
                    "stuck_duration": round(memory_ctrl.stuck_duration, 3),
                    "novelty": round(memory_ctrl.novelty, 3),
                    "escape_behavior": memory_ctrl.escape_behavior,
                    "loop_score": round(memory_ctrl.spatial.loop_score, 3),
                    "exploration_mode": memory_ctrl.spatial.exploration_mode,
                    "visited_cells": memory_ctrl.spatial.visited_cells,
                    "coverage_pct": round(memory_ctrl.coverage_pct, 1),
                    "coverage_rate": round(memory_ctrl.coverage_rate, 4),
                    "exploration_speed": round(memory_ctrl.coverage_rate * 60, 2),
                    "dead_end_count": memory_ctrl.dead_end_count,
                    "dead_end_cells": [[k[0], k[1]] for k in memory_ctrl.dead_end_cells][:50],
                    "cell_x": int(pose[0]),
                    "cell_z": int(pose[2]),
                    "xs": [round(float(v), 1) for v in xs[:2500]],
                    "zs": [round(float(v), 1) for v in zs[:2500]],
                    "heats": [round(float(v), 3) for v in heats[:2500]],
                    "scene_change_rate": round(model.scene_change_rate, 3),
                    "forced_bold_explore": memory_ctrl.forced_bold_explore,
                    "scene_low_duration": round(memory_ctrl.scene_low_duration, 2),
                    # Landmark memory fields
                    "scene_id": memory_ctrl.scene_id,
                    "revisit_count": memory_ctrl.revisit_count,
                    "revisit_penalty": round(memory_ctrl.revisit_penalty, 3),
                    "scene_match": round(memory_ctrl.scene_match, 4),
                    # Anomaly state
                    "anomaly_state": memory_ctrl.anomaly_state_name,
                    "anomaly_confidence": round(memory_ctrl.anomaly_confidence, 3),
                    "anomaly_duration": round(memory_ctrl.anomaly_duration, 3),
                    # Reflex state
                    "reflex_active": memory_ctrl.reflex_active,
                    "reflex_type": memory_ctrl.reflex_type,
                    "reflex_cooldowns": memory_ctrl.reflex_cooldowns,
                    # Health scoring
                    "health_score": round(memory_ctrl.health_score, 4),
                }, separators=(",", ":")).encode()
                DashboardHTTP.flow_json = json.dumps({
                    "asymmetry": round(model.flow_asymmetry, 4),
                    "true_asymmetry": round(model.true_asymmetry, 4),
                    "heading_rate": round(model.heading_rate, 4),
                    "looming": round(model.flow_looming, 4),
                    "cliff": round(model.flow_cliff, 4),
                    "cliff_detected": memory_ctrl.cliff_detected,
                    "cliff_confidence": round(memory_ctrl.cliff_confidence, 3),
                    "cliff_confirmed": model.cliff_confirmed,
                    "cliff_rate": round(model.cliff_rate, 4),
                    # Tau (time-to-contact) estimation
                    "tau": round(model.tau, 4) if model.tau != float("inf") else None,
                    "terrain": model.terrain,
                    "wall_score": round(model.wall_score, 4),
                    "ramp_score": round(model.ramp_score, 4),
                    "opening_score": round(model.opening_score, 4),
                    "sky_score": round(model.sky_score, 4),
                    "ground_angle": round(model.ground_angle, 4),
                    "door_frame_score": round(model.door_frame_score, 4),
                    "opening_width": round(model.opening_width, 4),
                    "tick": model.step_count,
                    # Multi-channel retina summary values
                    "on": round(model.on_energy, 4),
                    "off": round(model.off_energy, 4),
                    "sustained": round(model.sustained_energy, 4),
                    "edge_0": round(model.edge_0, 4),
                    "edge_45": round(model.edge_45, 4),
                    "edge_90": round(model.edge_90, 4),
                    "edge_135": round(model.edge_135, 4),
                    "scene_match": round(memory_ctrl.scene_match, 4),
                }, separators=(",", ":")).encode()
                # Log anomaly state transitions to events buffer
                current_anomaly = memory_ctrl.anomaly_state_name
                if current_anomaly and current_anomaly != previous_anomaly_state and current_anomaly != "idle":
                    escape_buffer.start_event(
                        round(tick_start - started, 2),
                        f"anomaly_{current_anomaly}",
                        pose_ev[0],
                        pose_ev[2],
                    )
                previous_anomaly_state = current_anomaly if current_anomaly else previous_anomaly_state
                DashboardHTTP.events_json = json.dumps({
                    "events": escape_buffer.get_recent(100),
                    "counters": event_counters,
                }, separators=(",", ":")).encode()
                # Push signal history
                DashboardHTTP.signal_history.append({
                    "t": round(tick_start - started, 2),
                    "coverage_pct": round(memory_ctrl.coverage_pct, 1),
                    "stuck_score": round(memory_ctrl.stuck_score, 3),
                    "stuck_duration": round(memory_ctrl.stuck_duration, 3),
                    "asymmetry": round(model.flow_asymmetry, 4),
                    "true_asymmetry": round(model.true_asymmetry, 4),
                    "heading_rate": round(model.heading_rate, 4),
                    "looming": round(model.flow_looming, 4),
                    "cliff": round(model.flow_cliff, 4),
                    "cliff_detected": memory_ctrl.cliff_detected,
                    "cliff_confidence": round(memory_ctrl.cliff_confidence, 3),
                    "cliff_confirmed": model.cliff_confirmed,
                    "cliff_rate": round(model.cliff_rate, 4),
                    # Tau (time-to-contact)
                    "tau": round(model.tau, 4) if model.tau != float("inf") else None,
                    "terrain": model.terrain,
                    "wall_score": round(model.wall_score, 4),
                    "ramp_score": round(model.ramp_score, 4),
                    "opening_score": round(model.opening_score, 4),
                    "sky_score": round(model.sky_score, 4),
                    "ground_angle": round(model.ground_angle, 4),
                    "door_frame_score": round(model.door_frame_score, 4),
                    "opening_width": round(model.opening_width, 4),
                    # Multi-channel retina
                    "on": round(model.on_energy, 4),
                    "off": round(model.off_energy, 4),
                    "sustained": round(model.sustained_energy, 4),
                    "edge_0": round(model.edge_0, 4),
                    "edge_45": round(model.edge_45, 4),
                    "edge_90": round(model.edge_90, 4),
                    "edge_135": round(model.edge_135, 4),
                    "scene_match": round(memory_ctrl.scene_match, 4),
                    # Anomaly state
                    "anomaly_state": memory_ctrl.anomaly_state_name,
                    "anomaly_confidence": round(memory_ctrl.anomaly_confidence, 3),
                    "anomaly_duration": round(memory_ctrl.anomaly_duration, 3),
                    "reflex_active": memory_ctrl.reflex_active,
                    "reflex_type": memory_ctrl.reflex_type,
                    "health_score": round(memory_ctrl.health_score, 4),
                })
                DashboardHTTP.history_json = json.dumps(
                    list(DashboardHTTP.signal_history),
                    separators=(",", ":")).encode()

            next_tick += model.dt
            delay = next_tick - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                next_tick = time.monotonic()
                await asyncio.sleep(0)
    finally:
        bridge.write_control(0, 0, False, enabled=False)
        replay.close()
        log.close()
        broadcast_task.cancel()
        ws_server.close()
        await ws_server.wait_closed()
        http.shutdown()
        bridge.close()
        # Save memory state
        try:
            mem_path = project / "artifacts" / "memory_state.json"
            mem_path.parent.mkdir(parents=True, exist_ok=True)
            mem_path.write_text(json.dumps({
                "visited_cells": memory_ctrl.spatial.visited_cells,
                "coverage_pct": round(memory_ctrl.coverage_pct, 1),
                "stuck_score": memory_ctrl.stuck_score,
                "stuck_duration": memory_ctrl.stuck_duration,
                "total_ticks": memory_ctrl.spatial.total_ticks,
                "dead_end_count": memory_ctrl.dead_end_count,
            }))
        except Exception:
            pass
        if dashboard_process and dashboard_process.poll() is None:
            dashboard_process.terminate()


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Fly64 neural closed loop")
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--demo-model", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--duration", type=float, default=0, help="seconds; zero runs until interrupted")
    parser.add_argument("--http-port", type=int, default=8765)
    parser.add_argument("--ws-port", type=int, default=8766)
    return parser.parse_args()


def main():
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
