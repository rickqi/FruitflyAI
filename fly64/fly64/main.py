from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import tempfile
import threading
import time
import webbrowser
import json
import math
import signal
try:
    import resource
except ImportError:  # POSIX-only; Windows lacks it
    resource = None
import sys
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
from .scene_recognition import SceneRecognizer

# ── Brain model version ──────────────────────────────────────────────
# MUST be incremented whenever an evolution round updates the skill /
# behaviour pipeline and is pushed (see agent.md workflow rules).
BRAIN_VERSION = "2.20.0"  # v2.20.0: micro_loop_weave自适应breakout + CPG零位移切换 + telemetry_gap补齐
SKILL_VERSION = "3.2.0"   # primitive scoring + history isolation + Phase-6 Evolve (must mirror evolution_skill)
# Evolution iteration records: one entry per skill closed-loop execution
evolution_log = deque(maxlen=50)
_evo_iter_counter = 0


def _load_evolution_history() -> None:
    """agent.md rule 9: restore evolution iteration history from disk so the
    dashboard history survives brain restarts."""
    global _evo_iter_counter
    try:
        with open("runtime/evolution_history.json", encoding="utf-8") as _ef:
            _hist = json.load(_ef)
        for _it in _hist.get("iterations", [])[-20:]:
            evolution_log.append(_it)
            _evo_iter_counter = max(_evo_iter_counter, int(_it.get("iter", 0)))
        DashboardHTTP.evolution_json = json.dumps({
            "brain_version": BRAIN_VERSION,
            "iterations": list(evolution_log)[-20:],
        }).encode()
    except (OSError, ValueError, AttributeError):
        pass  # no history yet or corrupted file — start fresh


_load_evolution_history()

class EscapeEventBuffer:
    """Ring buffer of last 200 escape events (t24 five-state schema).

    Outcome state machine:
        in_progress          — escape active
        resolved_effective   — ended, displacement >  EFFECTIVE_MIN_U
        resolved_ineffective — ended, displacement ≤ EFFECTIVE_MIN_U
        escalated            — ended but the situation re-escaped <10 s later
        aborted              — ended without a measurable displacement sample

    Each start snapshots the full behavioural context (reasons list, anomaly
    state/duration, terrain, loop_score, novelty, coach strategy keys) and
    ``post_escape_anomaly`` records the first anomaly seen after resolve.
    """

    EFFECTIVE_MIN_U = 30.0
    ESCALATE_WINDOW_S = 10.0

    def __init__(self, maxlen: int = 200):
        self._events: deque = deque(maxlen=maxlen)
        self._last_resolved_ts: float | None = None

    def start_event(self, timestamp: float, reason: str,
                    position_x: float, position_z: float, *,
                    reasons: list[str] | None = None,
                    snapshot: dict | None = None) -> dict:
        """Record the start of a new escape event.

        ``reasons`` lists ALL active trigger conditions (the primary
        ``reason`` first); ``snapshot`` merges behavioural context fields
        (anomaly_state / anomaly_duration / terrain / loop_score / novelty /
        coach_keys).
        """
        event: dict = {
            "timestamp": round(timestamp, 2),
            "reason": reason,
            "reasons": list(reasons) if reasons else [reason],
            "duration": 0.0,
            "position": {"x": round(position_x, 1), "z": round(position_z, 1)},
            "outcome": "in_progress",
            "distance_moved": 0.0,
        }
        if snapshot:
            event.update(snapshot)
        event.setdefault("anomaly_state", "")
        event.setdefault("anomaly_duration", 0.0)
        event.setdefault("terrain", "")
        event.setdefault("loop_score", 0.0)
        event.setdefault("novelty", 0.0)
        event.setdefault("coach_keys", {})
        event.setdefault("post_escape_anomaly", None)
        # escalation: the previous escape resolved moments ago and we are
        # already escaping again — the previous attempt failed to solve it.
        if (self._last_resolved_ts is not None
                and timestamp - self._last_resolved_ts <= self.ESCALATE_WINDOW_S
                and self._events
                and str(self._events[-1].get("outcome", "")).startswith("resolved")):
            self._events[-1]["outcome"] = "escalated"
        self._events.append(event)
        return event

    def update_current(self, dt: float) -> None:
        """Accumulate tick duration onto the current (latest) event."""
        if self._events:
            self._events[-1]["duration"] = round(
                self._events[-1]["duration"] + dt, 3)

    def resolve_current(self, distance_moved: float,
                        effective_min_u: float = EFFECTIVE_MIN_U,
                        aborted: bool = False) -> str:
        """Resolve the current event into an effective/ineffective/aborted
        outcome based on displacement vs the effective threshold (30u)."""
        if not self._events:
            return ""
        ev = self._events[-1]
        if aborted or distance_moved is None:
            ev["outcome"] = "aborted"
        else:
            ev["distance_moved"] = round(distance_moved, 1)
            ev["outcome"] = ("resolved_effective"
                             if distance_moved > effective_min_u
                             else "resolved_ineffective")
        # escalate window compares EVENT-relative timestamps (the same base
        # start_event uses), never wall time — keeps the buffer testable.
        self._last_resolved_ts = ev["timestamp"]
        return ev["outcome"]

    def mark_post_escape_anomaly(self, anomaly_state: str) -> bool:
        """Tag the most recent resolved event with a post-escape anomaly.

        Returns True when a resolved (non-escalated) event was tagged.
        """
        if not anomaly_state or not self._events:
            return False
        ev = self._events[-1]
        oc = ev.get("outcome", "")
        if (oc.startswith("resolved") and not ev.get("post_escape_anomaly")):
            ev["post_escape_anomaly"] = anomaly_state
            return True
        return False

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
    evolution_json = b"{}"
    help_json = b"{}"   # L2 coach-help snapshot (see /help.json)
    screen_json = b'{"screen_b64": ""}'
    signal_history = deque(maxlen=600)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            body, mime = self.html, "text/html; charset=utf-8"
        elif path == "/positions.bin":
            body, mime = self.positions, "application/octet-stream"
        elif path == "/metadata.json":
            body, mime = self.metadata, "application/json"
        elif path == "/evolution.json":
            # EVO skill findings live in evolution_history.json (written by
            # the external evolution_skill process).  Fall back to file when
            # the in-memory evolution_json is empty.
            _evo_body = self.evolution_json
            if _evo_body == b"{}" or b'"iterations"' not in _evo_body:
                _evo_path = (Path(__file__).resolve().parent.parent
                             / "runtime" / "evolution_history.json")
                try:
                    _evo_file = _evo_path.read_bytes()
                    if _evo_file.strip():
                        _evo_body = _evo_file
                except OSError:
                    pass
            body, mime = _evo_body, "application/json"
        elif path == "/help.json":
            body, mime = self.help_json, "application/json"
        elif path == "/coach_advice.json":
            # LLM coach advice written by the fly64-mhr plugin
            _coach = Path(__file__).resolve().parent.parent / "skills" / "coach_advice.json"
            try:
                body, mime = _coach.read_bytes(), "application/json"
            except OSError:
                body, mime = b'{"advice": "", "history": []}', "application/json"
        elif path == "/active_strategy.json":
            # t16 P0-2: coach strategy consumption panel — current operator
            # keys + dialogue_decision as written by the MHR plugin
            _strat = Path(__file__).resolve().parent.parent / "skills" / "active_strategy.json"
            try:
                body, mime = _strat.read_bytes(), "application/json"
            except OSError:
                body, mime = b'{"mode": "mirror"}', "application/json"
        elif path == "/coach_frames" or path.startswith("/coach_frames/"):
            # t21 wrap-up UI: read-only static endpoint for the consult
            # frame snapshots.  Directory traversal is blocked by resolving
            # against the coach_frames dir and rejecting escapes; only
            # *.png files are ever served.
            frames_dir = (Path(__file__).resolve().parent.parent
                          / "runtime" / "coach_frames")
            name = path[len("/coach_frames/"):].strip() if path != "/coach_frames" else ""
            if not name:
                try:
                    names = sorted((f.name for f in frames_dir.glob("*.png")),
                                   reverse=True)[:50]
                    body, mime = json.dumps({"frames": names}).encode(), "application/json"
                except OSError:
                    body, mime = b'{"frames": []}', "application/json"
            elif not re.fullmatch(r"[A-Za-z0-9_\-.]+\.png", name) or ".." in name:
                # t21 review hardening: strict filename allowlist — letters,
                # digits, underscore, hyphen, single dots (the save format
                # embeds a fractional timestamp); anything else (traversal,
                # separators, other extensions) is rejected outright.
                body, mime = b"forbidden", "text/plain"
                self.send_response(403)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            else:
                fp = (frames_dir / name).resolve()
                if (fp.parent == frames_dir.resolve() and fp.is_file()):
                    body, mime = fp.read_bytes(), "image/png"
                else:
                    body, mime = b"not found", "text/plain"
                    self.send_response(404)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
        elif path in self.assets:
            # Hot-reload: web assets are read from disk per request, so
            # publishing a page never requires restarting the main process.
            # Plain bytes values (measured.bin snapshot) pass through as-is.
            _src, mime = self.assets[path]
            if isinstance(_src, bytes):
                body = _src
            else:
                try:
                    body = _src.read_bytes()
                except OSError:
                    body, mime = b"", "text/plain"
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
        elif path == "/screen.json":
            body, mime = self.screen_json, "application/json"
        elif path == "/history.json":
            body, mime = self.history_json, "application/json"
        elif path == "/trajectory-list.json":
            import glob as _glob
            arts = Path(__file__).resolve().parent.parent / "artifacts"
            files = sorted(_glob.glob(str(arts / "*.trajectory.npz")))
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
        # (source path, mime) — read from disk on every request (hot-reload);
        # measured.bin stays an in-memory snapshot of the live model.
        "/dashboard.js": (project / "web/dashboard.js", "text/javascript"),
        "/dashboard.css": (project / "web/dashboard.css", "text/css"),
        "/memory-heatmap.js": (project / "web/memory-heatmap.js", "text/javascript"),
        "/trajectory.html": (project / "web/trajectory.html", "text/html"),
        "/trajectory-height.js": (project / "web/trajectory-height.js", "text/javascript"),
        "/monitor-preview.html": (project / "web/monitor-preview.html", "text/html; charset=utf-8"),
        "/layout-wireframe.html": (project / "web/layout-wireframe.html", "text/html; charset=utf-8"),
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


def _scene_name(model, memory_ctrl, recognizer=None) -> str:
    """Human-readable scene identification via profile matching + feature dominance.

    Pipeline:
      1. If a ``SceneRecognizer`` is provided and its confidence exceeds 0.4,
         return the SM64 level name with the short scene hash.
      2. If a custom label exists for this scene hash, return that.
      3. Fall back to the existing feature-based naming (top-2 dominant features).
    """
    # EVO R13: dialogue pause-wait is its own scene state — visual feature
    # dominance (bright ceiling → "sky", walls → "slope") must not mask it.
    if getattr(model, "dialogue_active", False):
        h = (memory_ctrl.scene_id or "")[:4]
        return f"对话暂停等待 #{h}" if h else "对话暂停等待"
    t = getattr(model, "terrain", "mixed")

    # Step 1: SM64 profile-based recognition (highest priority)
    if recognizer is not None:
        level_id, confidence, tags = recognizer.recognize(model)
        if confidence > 0.35 and level_id:
            profile = recognizer.profiles.get(level_id)
            level_name = profile["name"] if profile else level_id
            h = (memory_ctrl.scene_id or "")[:4]
            return f"{level_name} #{h}" if h else level_name
        # EVO R16 · C3: account for scenes that matched no profile (the
        # unknown-scene counter seeds future online clustering).
        recognizer.note_unknown_scene((memory_ctrl.scene_id or "")[:6])

    # Step 2: Custom label (if user assigned one for this scene hash)
    h = (memory_ctrl.scene_id or "")[:4]
    if recognizer and h:
        custom = recognizer.get_label(h)
        if custom:
            return f"{custom} #{h}" if h else custom

    # Step 3: Indoor/enclosed detection (EVO R9 override)
    if getattr(model, "enclosure_score", 0.0) > 0.5:
        return f"室内 #{h}" if h else "室内"

    # Step 4: Feature-based naming (existing logic)
    feats = {
        "墙体": getattr(model, "wall_score", 0.0),
        "山坡": getattr(model, "ramp_score", 0.0),
        "通道": getattr(model, "opening_score", 0.0),
        "门洞": getattr(model, "door_frame_score", 0.0),
        "天空": getattr(model, "sky_score", 0.0),
    }
    ground = getattr(model, "ground_angle", 1.0)
    if t == "water":
        base = "水域"
    elif t == "cliff" and ground < 0.3:
        base = "悬崖边缘"
    elif t == "open_flat":
        base = "开阔草原"
    elif t == "wall_ahead":
        base = "墙体"
    elif t == "forest_edge":
        base = "密林边缘"
    else:
        ranked = sorted(feats.items(), key=lambda kv: kv[1], reverse=True)
        parts = [name for name, v in ranked if v >= 0.25][:2]
        base = "·".join(parts) if parts else "混合地形"
    return f"{base} #{h}" if h else base


# ── L2 coach-help snapshot ───────────────────────────────────────────

def build_help_snapshot(scene_name, position, diagnosis, frame,
                        help_reason="interaction_blocked",
                        screen_bytes: bytes | None = None) -> dict:
    """Build the /help.json payload: full context for a human coach.

    The frame received here is a 384×256 cubemap (6 faces).  For the GLM
    coach we extract the FORWARD face (128×128) — the most interpretable
    single view for an LLM trained on human images.  The full cubemap is
    never sent to the LLM directly.

    SM64 actual game-screen capture (third-person camera showing Mario)
    is NOT available through the current bridge protocol — only the
    cubemap is.  A future fly64_vision.c extension could write the game's
    frame buffer to a second shared-memory slot.
    """
    import base64
    frame_b64 = ""
    if frame is not None:
        arr = np.ascontiguousarray(np.asarray(frame, np.uint8))
        # Extract the forward face (first 128×128 block) from the
        # 384×256 cubemap — the most useful view for a GLM.
        if arr.shape == (256, 384, 3):
            forward = arr[:128, :128, :].copy()
            fwd_b64 = base64.b64encode(forward.tobytes()).decode("ascii")
            frame_b64 = fwd_b64
    screen_b64 = ""
    if screen_bytes is not None:
        screen_b64 = base64.b64encode(
            np.ascontiguousarray(screen_bytes).tobytes()).decode("ascii")
    return {
        "scene_name": scene_name or "",
        "position": position or {},
        "diagnosis": diagnosis or "",
        "frame_b64": frame_b64,
        "screen_b64": screen_b64,
        "help_reason": help_reason,
        "ts": round(time.time(), 2),
    }


# ── LLM dialogue decision (pause-wait mode) ──────────────────────────
# When a dialogue box appears the brain pauses and asks the MHR plugin's
# GLM LLM for a press_a / press_b / none decision.  Wait at most 10
# minutes, then fall back to the autonomous A-press reflex.
DIALOGUE_LLM_WAIT_S = 600.0
DIALOGUE_PRESS_TICKS = 12   # ~0.2s of held button per executed press


def frame_to_b64(frame) -> str:
    """Base64-encode an HxWxC uint8 frame (raw, channel-last, row-major)."""
    import base64
    if frame is None:
        return ""
    arr = np.ascontiguousarray(np.asarray(frame, np.uint8))
    return base64.b64encode(arr.tobytes()).decode("ascii")


# ── L3 operator strategy (active_strategy.json hot-reload) ───────────

ACTIVE_STRATEGY_DEFAULTS = {
    "mode": "mirror",          # mirror (alternate direction) | directional_climb
    "climb_period": 2.0,       # seconds of forward burst after jump phase
    "persist_seconds": 2.0,    # seconds of reduced-forward persistence phase
    # M1.2: CPG primitive whitelist (hot-reload).  Names are Primitive.value.
    "primitives_enabled": ["longjump", "backflip", "groundpound", "punch", "dive"],
}

# M2.3: last applied turn sign for the side-flip reversal detector.
_CPG_PREV_XSIGN = 0
_CPG_FALLEN_TOGGLE = 0    # alternates between LONG_JUMP and BACKFLIP
_CPG_FALLEN_SWITCH_S = 3.0  # switch primitive every 3 seconds when fallen


def load_active_strategy(path) -> dict:
    """Read skills/active_strategy.json fallen_recovery section.

    Missing file, invalid JSON, or malformed sections fall back to the
    built-in defaults — a bad operator file can never brick recovery.
    """
    defaults = dict(ACTIVE_STRATEGY_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    section = data.get("fallen_recovery", data)
    if not isinstance(section, dict):
        return defaults
    strategy = dict(defaults)
    mode = section.get("mode", defaults["mode"])
    if mode in ("mirror", "directional_climb"):
        strategy["mode"] = mode
    for key in ("climb_period", "persist_seconds"):
        try:
            strategy[key] = max(0.1, float(section.get(key, defaults[key])))
        except (TypeError, ValueError):
            pass
    # M1.2: primitives whitelist — operator may enable/disable individual
    # motor primitives live (e.g. disable dive while tuning).
    prim = data.get("primitives", None)
    if isinstance(prim, dict) and isinstance(prim.get("enabled"), list):
        names = [str(x) for x in prim["enabled"] if isinstance(x, str)]
        if names:
            strategy["primitives_enabled"] = names
    # M2.1: scene-preference map {scene_tag_substring: primitive_name} —
    # coach/operator hints which primitive fits which terrain (e.g.
    # {"ramp": "longjump"}).  Invalid entries dropped.
    if isinstance(prim, dict) and isinstance(prim.get("prefer"), dict):
        prefer = {}
        for tag, name in prim["prefer"].items():
            if (isinstance(tag, str) and tag
                    and isinstance(name, str) and name):
                prefer[tag] = name
        if prefer:
            strategy["primitives_prefer"] = prefer
    return strategy


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
    # Phase 2 motor expansion: VNC-style CPG motor primitives (priority 4.5)
    from .motor_primitives import CPGController, Primitive
    from .motor_primitives import apply_phase as cpg_apply_phase
    cpg = CPGController()
    _cpg_last_completed = 0
    _cpg_last_aborted = 0
    # Restore previously explored scene signatures (landmark persistence)
    _loaded_sigs = memory_ctrl.load_scene_db()
    if _loaded_sigs:
        print(f"Scene database restored: {_loaded_sigs} signatures")
    # Initialise SM64 scene recogniser with persistent custom labels
    _labels_path = project / "artifacts" / "scene_labels.json"
    _labels_path.parent.mkdir(parents=True, exist_ok=True)
    scene_recognizer = SceneRecognizer(profiles_path=_labels_path)
    scene_save_counter = 0
    # Interaction loop breaker: a prompt that keeps re-appearing despite
    # A-presses (e.g. locked door) is an unrewarded stimulus — habituate.
    dialogue_engagements = 0
    dialogue_last_pos = None
    dialogue_blocked_until = 0.0
    prev_dialogue_active = False
    # LLM dialogue decision (pause-wait mode): on each new dialogue episode
    # the brain pauses and a worker thread asks GLM for press_a/press_b/none.
    dialogue_episode = 0
    llm_decision = None            # {"action","reason","ts"} once decided
    llm_decision_episode = -1      # episode the current decision applies to
    llm_decision_consumed = False
    llm_wait_started = 0.0
    llm_decision_status = "idle"   # idle | waiting | decided | timeout
    llm_press_hold = 0             # ticks of remaining held button press
    llm_press_b = False            # which button the held press is
    _dialogue_writer = None
    _dialogue_consultant = None
    try:
        from plugin.llm_consult import GLMConsultant as _DlgConsultant
        from plugin.strategy_writer import StrategyWriter as _DlgWriter
        _dialogue_consultant = _DlgConsultant()
        _dialogue_writer = _DlgWriter()
    except Exception as _exc:   # pragma: no cover - plugin optional
        print(f"[fly64] LLM dialogue consultant unavailable: {_exc}")

    def _request_dialogue_decision(ep: int, frame) -> None:
        """Worker thread: screenshot -> GLM -> dialogue_decision, <=10 min."""
        nonlocal llm_decision, llm_decision_episode, llm_decision_status
        try:
            # EVO R11/T1: pass live context so the LLM decision has the
            # diagnostic data (was empty {} — request without context is
            # unanswerable even for a perfect model).
            _dlg_ctx = {
                "kind": "dialogue_decision",
                "episode": ep,
                "scene_name": getattr(model, "scene_name", "") or "",
                "stuck_duration": round(memory_ctrl.stuck_duration, 1),
                "anomaly_state": memory_ctrl.anomaly_state_name,
                "habituated": dialogue_engagements >= 3,
                "terrain": model.terrain,
            }
            parsed = _dialogue_consultant.consult_dialogue(
                frame_to_b64(frame), context=_dlg_ctx,
                timeout=DIALOGUE_LLM_WAIT_S)
            llm_decision = {"action": parsed.get("action", "none"),
                            "reason": parsed.get("reason", ""),
                            "ts": round(time.time(), 2)}
            llm_decision_status = "decided"
            timed_out = False
        except Exception as exc:
            llm_decision = {"action": "press_a",
                            "reason": f"LLM timeout/error, autonomous fallback: {exc}",
                            "ts": round(time.time(), 2)}
            llm_decision_status = "timeout"
            timed_out = True
        llm_decision_episode = ep
        llm_decision_consumed = False
        wait_s = time.monotonic() - llm_wait_started
        try:
            _dialogue_writer.write_dialogue_decision(
                llm_decision["action"], llm_decision["reason"],
                source="glm-5.3-flash", wait_seconds=wait_s,
                timed_out=timed_out)
        except Exception:
            pass

    # L2 coach-help: one snapshot per habituation blocking episode
    dialogue_help_sent = False
    # L2a: stuck/circling help trigger — catches the fast-looping case
    # (loop>0.8, coverage≈0, stuck>5s) that the displacement-based
    # reflex_ineffective (R12) cannot detect.
    _stuck_no_coverage_start = None
    _stuck_no_coverage_help_sent = False
    # L3 operator strategy, hot-reloaded every 600 ticks
    _active_strategy = dict(ACTIVE_STRATEGY_DEFAULTS)
    _last_strategy_tick = 0
    # EvolutionSkill: on-demand diagnosis when escape states trigger
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from fly64.skills.evolution_skill import EvolutionPipeline
        _evo_pipe = EvolutionPipeline(auto_fix=False, window_seconds=120)
    except Exception:
        _evo_pipe = None
    _evo_last_run = 0.0
    _evo_findings = []
    # P1 (audit A7): corollary-discharge frame counter deleted.  Displacement
    # history note kept: _last_cmp_pose retained for the escape event buffer.
    _last_cmp_pose = None
    escape_buffer = EscapeEventBuffer()
    event_counters = {"total_escapes": 0, "total_falls": 0,
                      "total_flow_avoid": 0, "total_help_requests": 0,
                      "current_stuck_duration": 0.0,
                      # t24: per-reason breakdown + outcome quality
                      "total_cliff_escapes": 0, "total_fallen_escapes": 0,
                      "total_stuck_escapes": 0, "effective_count": 0,
                      "ineffective_count": 0, "effectiveness_rate": 0.0}
    current_escape_event = None
    previous_escape: bool = False
    event_last_pos = (0.0, 0.0)
    previous_cliff_confirmed: bool = False
    cliff_recovery_timer: float = 0.0
    cliff_turn_bias: float = 0.0
    previous_anomaly_state: str = ""
    # EVO R11: displacement feedback window (~2.4 s at 50 Hz) — feeds the
    # mushroom body's dopamine signal so zero-displacement escape contexts
    # are learned as punishers (network-level fix for circling).
    _pose_hist: list = []
    # EVO R12: 60 s displacement samples for reflex-ineffective escalation —
    # a reflex that stays active while displacement stays ~zero is by
    # definition not solving the problem and must escalate to the coach.
    _disp_trace: list = []
    # ---- Plasticity monitoring buffer (t4) ----
    _error_gradient_buffer = deque(maxlen=100)
    _plasticity_metrics = {
        "learning_progress": 0.0,
        "dopamine_gain_avg": 0.0,
        "mushroom_weight_changes": 0,
        "reward_trend": 0.0,
        "error_gradient_mean": 0.0,
        "gain_update_count": 0,
    }
    _plasticity_tick = 0

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
            # EVO R11: displacement feedback for the mushroom body — a burst
            # window (~2.4 s) of near-zero displacement becomes a dopamine
            # punishment, teaching the MB that this scene/action context is
            # unproductive (network-level circling fix).
            _pose_hist.append((model.step_count * model.dt, pose_ev[0], pose_ev[2]))
            if len(_pose_hist) >= 120:
                _t0, _x0, _z0 = _pose_hist[0]
                _disp = ((pose_ev[0] - _x0) ** 2 + (pose_ev[2] - _z0) ** 2) ** 0.5
                model.report_movement(_disp)
                _pose_hist.clear()
            # EVO R12: 60 s rolling displacement → reflex-ineffective flag.
            # A reflex that stays active while 60 s displacement stays ~zero
            # is not solving the problem; this escalates to coach consult.
            _disp_trace.append((model.step_count * model.dt, pose_ev[0], pose_ev[2]))
            while _disp_trace and _disp_trace[-1][0] - _disp_trace[0][0] > 60.0:
                _disp_trace.pop(0)
            if _disp_trace and _disp_trace[-1][0] - _disp_trace[0][0] >= 55.0:
                _t0, _x0, _z0 = _disp_trace[0]
                _disp60 = ((pose_ev[0] - _x0) ** 2 + (pose_ev[2] - _z0) ** 2) ** 0.5
                # reflex_ineffective also fires when the agent is circling
                # fast (loop>0.8, coverage≈0) — the displacement-based check
                # alone misses this class (fast loop → large disp60 → never
                # flagged, yet no progress = no new cells).
                _circling = (memory_ctrl.spatial.loop_score > 0.8
                            and memory_ctrl.spatial.coverage_rate < 0.01
                            and memory_ctrl.stuck_duration > 30.0)
                memory_ctrl.reflex_ineffective = bool(
                    (memory_ctrl.reflex_active and _disp60 < 30.0)
                    or _circling)
                memory_ctrl.disp_60s = round(_disp60, 1)
            else:
                memory_ctrl.reflex_ineffective = False
                memory_ctrl.disp_60s = None
            heading = pose_ev[3]
            control, spikes = model.step(frame, model.step_count * model.dt,
                                         novelty=memory_ctrl.novelty,
                                         heading=heading)

            # ---- Corollary discharge: action-effect comparator ----
            # Forward command issued but position static = pushing into
            # geometry (wall corner). Vision cannot see this; the motor
            # vs measured displacement mismatch can.
            _cur_cmp = (pose_ev[0], pose_ev[2])
            _last_cmp_pose = _cur_cmp
            # P1 (BRAIN 2.7.0): Python corollary-discharge frame counter and
            # un-corner override deleted (audit A7) — the displacement signal
            # remains available for a future efference-copy neuron (roadmap
            # P3).  Telemetry key kept for dashboard compatibility.
            command_decoupled = False

            # ---- Dialogue episode tracking (habituation counter) ----
            # Final dialogue control override happens just before
            # bridge.write_control so telemetry still publishes every tick.
            dlg_now = getattr(model, "dialogue_active", False)
            if dlg_now and not prev_dialogue_active:
                # New dialogue episode: pause the brain and ask the LLM.
                dialogue_episode += 1
                # EVO R13: dialogue discovery is a setback signal — dopamine
                # pulse teaches the mushroom body that THIS scene context is
                # blocked/negative (PPL1-like), so its MBON value steers the
                # fly away on future visits without any new Python branch.
                model.add_setback(0.5)
                if dialogue_engagements >= 2:
                    model.add_setback(0.3)  # repeat engagement deepens it
                llm_decision = None
                llm_decision_consumed = False
                llm_decision_status = ("waiting" if _dialogue_consultant
                                       else "timeout")
                llm_wait_started = time.monotonic()
                if _dialogue_consultant is not None:
                    threading.Thread(
                        target=_request_dialogue_decision,
                        args=(dialogue_episode, frame),
                        daemon=True, name="llm-dialogue-decision").start()
                px, pz = pose_ev[0], pose_ev[2]
                if (dialogue_last_pos is not None
                        and abs(px - dialogue_last_pos[0]) < 150
                        and abs(pz - dialogue_last_pos[1]) < 150):
                    dialogue_engagements += 1
                else:
                    dialogue_engagements = 1
                    dialogue_last_pos = (px, pz)
                if dialogue_engagements >= 3:
                    dialogue_blocked_until = time.monotonic() + 120.0
                    dialogue_engagements = 0
                    model.add_setback(0.8)  # habituation lock = strong setback
            prev_dialogue_active = dlg_now

            # ---- L2 coach-help snapshot (while habituation blocks) ----
            if time.monotonic() < dialogue_blocked_until:
                if not dialogue_help_sent:
                    dialogue_help_sent = True
                    event_counters["total_help_requests"] += 1
                    DashboardHTTP.help_json = json.dumps(build_help_snapshot(
                        _scene_name(model, memory_ctrl, scene_recognizer),
                        {"x": round(pose_ev[0], 1), "y": round(pose_ev[1], 1),
                         "z": round(pose_ev[2], 1)},
                        (f"interaction habituated: dialogue re-engaged >=3x near "
                         f"{dialogue_last_pos}; anomaly="
                         f"{memory_ctrl.anomaly_state_name}"),
                        frame,
                        screen_bytes=bridge.read_screen())).encode()
            elif dialogue_help_sent:
                dialogue_help_sent = False
                DashboardHTTP.help_json = json.dumps(
                    {"help_reason": None}).encode()

            # ---- L2a: stuck/circling help trigger — fast-looping case ----
            _now = time.monotonic()
            _stuck_no_progress = (memory_ctrl.stuck_score >= 0.8
                                  and memory_ctrl.spatial.coverage_rate < 0.01
                                  and memory_ctrl.stuck_duration > 5.0)
            if _stuck_no_progress:
                if _stuck_no_coverage_start is None:
                    _stuck_no_coverage_start = _now
                elif (_now - _stuck_no_coverage_start >= 30.0
                      and not _stuck_no_coverage_help_sent):
                    _stuck_no_coverage_help_sent = True
                    event_counters["total_help_requests"] += 1
                    DashboardHTTP.help_json = json.dumps(build_help_snapshot(
                        _scene_name(model, memory_ctrl, scene_recognizer),
                        {"x": round(pose_ev[0], 1), "y": round(pose_ev[1], 1),
                         "z": round(pose_ev[2], 1)},
                        (f"stuck_no_progress: stuck={memory_ctrl.stuck_score:.2f} "
                         f"dur={memory_ctrl.stuck_duration:.0f}s "
                         f"loop={memory_ctrl.spatial.loop_score:.2f} "
                         f"cov={memory_ctrl.coverage_pct:.1f}%"),
                        frame,
                        help_reason="stuck_no_progress",
                        screen_bytes=bridge.read_screen())).encode()
            elif _stuck_no_coverage_help_sent:
                _stuck_no_coverage_help_sent = False
                _stuck_no_coverage_start = None
                DashboardHTTP.help_json = json.dumps(
                    {"help_reason": None}).encode()
            elif _stuck_no_coverage_start is not None and not _stuck_no_progress:
                _stuck_no_coverage_start = None  # brief recovery reset

            # ---- L3 strategy hot-reload (every 600 ticks) ----
            if model.step_count - _last_strategy_tick >= 600:
                _last_strategy_tick = model.step_count
                _active_strategy = load_active_strategy(
                    project / "skills" / "active_strategy.json")
                # EVO R11 follow-up: push coach-tunable keys into the memory
                # controller so GLM strategy advice tunes the escape/breakout
                # behaviour (consumed in memory.py + bold breakout below).
                _expl = _active_strategy.get("exploration", {}) or {}
                _esc = _active_strategy.get("escape", {}) or {}
                memory_ctrl.bold_explore_stuck_s = float(
                    _expl.get("bold_explore_stuck_s", 60.0))
                memory_ctrl.bold_turn_bias = float(
                    _expl.get("turn_bias", 69.0))
                memory_ctrl.escape_stuck_threshold_s = float(
                    _esc.get("stuck_threshold_s", 2.0))
                # P2: Escape parameter hot-loading from active_strategy
                model._escape_commit_ticks = int(
                    _esc.get("commit_ticks", 50))
                model._escape_forward_accum = float(
                    _esc.get("forward_accum_max", 0.50))
                model._fallen_forward = float(
                    _esc.get("fallen_forward", 0.20))
                model._fallen_jump_boost = float(
                    _esc.get("fallen_jump_boost", 0.60))
                model._explore_commit_ticks = int(
                    _expl.get("commit_ticks_explore", 250))
                model._explore_commit_strength = float(
                    _expl.get("commit_strength", 0.10))
                # Fallen toggle rate from active_strategy
                global _CPG_FALLEN_SWITCH_S
                _CPG_FALLEN_SWITCH_S = float(
                    _esc.get("fallen_switch_s", 3.0))

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
                    # P4-1: Cliff reflex through LIF bridge
                    model.reflex_turn = turn_dir
                    model.reflex_forward = -10
                    control.x = turn_dir
                    control.y = -10  # brief reverse in SM64
                    cliff_triggered = True
                    cliff_turn_bias = float(turn_dir)
                    cliff_recovery_timer = 0.0
                # 2. Low-confidence cliff branch RETIRED (EVO R11): its
                #    per-tick x*1.5 / y-20 turning was the main contributor to
                #    the circling dead-loop.  Directional openness now reaches
                #    the turn pools as current injection (model.step), so the
                #    LIF competition steers away from dark/chasm fields
                #    without a symbolic override.  See agent.md EVO R11.
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
                # Also correct terrain name to avoid misleading telemetry
                # that triggers EVO circle_loop pattern false alarms
                if model.terrain == "cliff":
                    model.terrain = "open_flat"

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
            _pose_r = bridge.frame_metadata.get("pose", [0, 0, 0, 0])
            # EVO R17: the brain's weave-detector (TurnAdaptation breakout
            # level, normalised 0-1) biases the reflex phase mix toward the
            # forward burst — sensory gating, decision stays reflex/brain.
            _ta = getattr(model, "_turn_adapt", None)
            _hint = 0.0
            if _ta is not None:
                _hint = min(1.0, _ta.breakout_drive() / max(_ta.breakout_gain, 1e-6))
            # EVO R28: pass CX steering bias to reflex so micro_loop turn
            # phase mixes it in, breaking the heading cancellation.
            memory_ctrl.reflex._last_cx_bias = getattr(model, "cx_bias", 0.0)
            reflex_active = memory_ctrl.reflex.update(
                model.dt,
                memory_ctrl.anomaly_state,
                model.rng.integers,
                stuck_duration=memory_ctrl.stuck_duration,
                pos=(_pose_r[0], _pose_r[2]),
                breakout_hint=_hint,
            )
            if reflex_active:
                action = memory_ctrl.reflex_action
                if action["active"]:
                    # P4-1: Reflex→LIF bridge — set flags on model instead of
                    # writing control.x/y/jump directly. The model.step() will
                    # convert these to LIF current injection, giving the network
                    # a shared vote in the motor decision.
                    model.reflex_turn = action.get("control_x", 0)
                    model.reflex_forward = action.get("control_y", 0)
                    model.reflex_jump = action.get("jump", False)
                    # Still write control for the SM64 bridge (phase 1 compat)
                    control.x = action["control_x"]
                    control.y = action["control_y"]
                    control.jump = action["jump"]
                    reflex_override = True
                    # EVO R29: suppress escape when below ground — it sets
                    # x=0 which kills the forward+JUMP needed to climb out.
                    _py_ = pose_ev[1] if len(pose_ev) > 1 else 0.0
                    if _py_ >= -200:
                        memory_ctrl.escape_behavior = True

            # ---- Aggressive mode (P1, audit A5): only the neuromodulatory
            # pathway remains — reflex cooldowns halve via the reflex's own
            # aggressive gate.  The Python control.x×1.5 bypass is deleted;
            # urgency is expressed as motor-pool gain, not symbolic scaling.
            memory_ctrl.reflex.set_aggressive_mode(
                memory_ctrl.health_score < 0.3)

            # P1 (audit A1): Python pre-emptive collision override deleted.
            # Direction-selective HRC motion truth already modulates the
            # turn/forward pools at current-injection level (model.step);
            # the LIF competition owns collision avoidance now.

            # P1 (audit A6): scene-change escape suppression branch deleted.
            # The stuck detector's own hysteresis gates escape entry; MB
            # familiarity (roadmap P4) will supply the learned gate.

            # ---- P1 (audit A3): escape 5-phase state machine deleted ----
            # Behaviour now emerges from: escape-mode motor current
            # injection (model.step), the four reflex circuits (writing
            # control above), and CX opening steering.  fallen adds a
            # jump-pool drive; forced_bold_explore becomes an alternating
            # turn-pool current whose sign mirrors the reflex's own
            # refractory memory (spontaneous alternation).
            bold_now = (memory_ctrl.escape_behavior
                        and memory_ctrl.forced_bold_explore)
            if memory_ctrl.escape_behavior and (bold_now or not reflex_override):
                model.escape_jump_drive = memory_ctrl.fallen
                if bold_now:
                    # t13 fix①: the coach key exploration.turn_bias was a dead
                    # write (no consumer).  Unit conversion + clamp: legacy
                    # ±69 angle scale and coach 0-1 strength both normalise
                    # to a [0.2, 1.0] fraction of the max turn-pool current
                    # (0.2 floor prevents a coach-0 from dead-throttling the
                    # breakout; the LIF competition still steers).
                    _bias = float(getattr(memory_ctrl, "bold_turn_bias", 69.0))
                    _mag = max(0.2, min(1.0, abs(_bias) / 69.0))
                    model.bold_turn_drive = (memory_ctrl.reflex.bold_direction()
                                             * _mag)
                else:
                    model.bold_turn_drive = 0.0
            else:
                model.escape_jump_drive = False
                model.bold_turn_drive = 0.0

            # ---- Scene-change suppression removed (P1, audit A6) ----

            # P1 (audit A1): the pre-emptive collision override that lived
            # here (motion_asym > 0.3 forced turn / looming > 0.4 slowdown)
            # is deleted; the model's current-injection pathway already
            # implements both effects inside the network.

            # P1 (audit A3): the escape 5-phase state machine that lived
            # here (escape_toggle_timer / escape_x phase timers writing
            # control.x/y/jump directly) is deleted.  See the replacement
            # drive flags above — no symbolic control writes remain.

            # ---- Python→neuron error gradient bridge (t3) ----
            # When Python escape logic makes a turn decision, compare it with
            # the neural network's preferred turn bias.  The error is fed back
            # as corrective current injection into the underperforming motor
            # pool, gated by the reward signal (strongest when reward is low).
            if memory_ctrl.escape_behavior and abs(control.x) > 8:
                model.set_python_correction(control.x, model.reward_signal)

            # ---- Escape event tracking ----
            currently_escaping = memory_ctrl.escape_behavior
            if currently_escaping and not previous_escape:
                # Escape just started — collect ALL active trigger reasons
                reasons = []
                if reflex_override:
                    reasons.append(f"reflex_{memory_ctrl.reflex_type}"
                                   if memory_ctrl.reflex_type else "reflex")
                if memory_ctrl.fallen:
                    reasons.append("fallen")
                    event_counters["total_falls"] += 1
                if memory_ctrl.stuck_score > 0.8:
                    reasons.append("stuck")
                if memory_ctrl.cliff_detected:
                    reasons.append("cliff")
                    event_counters["total_cliff_escapes"] += 1
                if model.true_asymmetry > 0.3:
                    reasons.append("flow")
                if not reasons:
                    reasons.append("stuck")
                reason = reasons[0]
                # primary-class counter (t24): cliff / fallen / stuck
                if reason == "cliff":
                    pass  # counted above
                elif reason == "fallen":
                    pass
                else:
                    event_counters["total_stuck_escapes"] += 1
                current_escape_event = escape_buffer.start_event(
                    round(tick_start - started, 2), reason,
                    pose_ev[0], pose_ev[2],
                    reasons=reasons,
                    snapshot={
                        "anomaly_state": memory_ctrl.anomaly_state_name,
                        "anomaly_duration": round(memory_ctrl.anomaly_duration, 2),
                        "terrain": model.terrain,
                        "loop_score": round(memory_ctrl.spatial.loop_score, 4),
                        "novelty": round(memory_ctrl.novelty, 4),
                        "coach_keys": {
                            "bold_explore_stuck_s": getattr(
                                memory_ctrl, "bold_explore_stuck_s", 60.0),
                            "turn_bias": getattr(
                                memory_ctrl, "bold_turn_bias", 0.5),
                            "escape_stuck_threshold_s": getattr(
                                memory_ctrl, "escape_stuck_threshold_s", 2.0),
                        },
                    })
                # t24: a resolved event followed by immediate re-escape means
                # the previous attempt escalated (counters + outcome already
                # handled inside the buffer via the escalate window).
                event_counters["total_escapes"] += 1
                event_last_pos = (pose_ev[0], pose_ev[2])
                # t24: tag the previous resolved event when the anomaly is
                # already active again — evidence the last escape failed.
                if memory_ctrl.anomaly_state_name:
                    escape_buffer.mark_post_escape_anomaly(
                        memory_ctrl.anomaly_state_name)
                # ---- EvolutionSkill: on-demand diagnosis on escape trigger ----
                if _evo_pipe is not None and tick_start - _evo_last_run > 10:
                    _evo_last_run = tick_start
                    try:
                        _res = _evo_pipe.run_one_cycle()
                        _evo_findings = [f"{f.pattern_id}({f.confidence:.0%})"
                                         for f in _res.findings]
                        for _f in _res.findings:
                            print(f"[EvolutionSkill] {_f.severity}: "
                                  f"{_f.pattern_id} conf={_f.confidence:.0%} "
                                  f"during escape reason={reason}")
                        # Record this evolution iteration for the dashboard
                        global _evo_iter_counter
                        _evo_iter_counter += 1
                        evolution_log.append({
                            "iter": _evo_iter_counter,
                            "time": time.strftime("%m-%d %H:%M:%S"),
                            "brain_version": BRAIN_VERSION,
                            "trigger": reason,
                            "findings": _evo_findings,
                            "capabilities": sorted({
                                _fid.split("(")[0] for _fid in _evo_findings}),
                            "plasticity": dict(_plasticity_metrics),
                        })
                        DashboardHTTP.evolution_json = json.dumps({
                            "brain_version": BRAIN_VERSION,
                            "iterations": list(evolution_log)[-20:],
                        }).encode()
                        # EVO history persistence (agent.md rule 9): survive
                        # brain restarts so the dashboard history survives too.
                        try:
                            with open("runtime/evolution_history.json", "w",
                                      encoding="utf-8") as _ef:
                                json.dump({
                                    "brain_version": BRAIN_VERSION,
                                    "iterations": list(evolution_log)[-20:],
                                }, _ef, ensure_ascii=False)
                        except OSError:
                            pass
                    except Exception:
                        pass
            if currently_escaping:
                escape_buffer.update_current(model.dt)
            elif previous_escape:
                # Escape just ended — resolve into effective/ineffective by
                # displacement vs the 30u threshold (t24 five-state outcome)
                dx = pose_ev[0] - event_last_pos[0]
                dz = pose_ev[2] - event_last_pos[1]
                dist = math.sqrt(dx * dx + dz * dz)
                outcome = escape_buffer.resolve_current(dist)
                if outcome == "resolved_effective":
                    event_counters["effective_count"] += 1
                elif outcome == "resolved_ineffective":
                    event_counters["ineffective_count"] += 1
                _den = (event_counters["effective_count"]
                        + event_counters["ineffective_count"])
                event_counters["effectiveness_rate"] = (
                    round(event_counters["effective_count"] / _den, 3)
                    if _den else 0.0)
                current_escape_event = None
            previous_escape = currently_escaping
            event_counters["current_stuck_duration"] = round(memory_ctrl.stuck_duration, 3)
            if model.flow_asymmetry > 0.3 or model.flow_cliff < 0.3:
                if not current_escape_event and not currently_escaping:
                    event_counters["total_flow_avoid"] += 1

            latest_control = control
            # P1 (audit A7): the corollary-discharge un-corner override that
            # lived here (60-frame no-motion counter → mirrored ±60 turn) is
            # deleted; wall/loop reflex circuits own wedged-geometry escape.
            # ---- Dialogue final override (after all other logic, so telemetry
            # still publishes every tick — no continue/skip) ----
            if dlg_now:
                if time.monotonic() < dialogue_blocked_until:
                    # Unrewarded stimulus — withdraw and turn away
                    model.reflex_turn = int(60 * (1 if (model.step_count // 20) % 2 else -1))
                    model.reflex_forward = -60
                    control.x = int(60 * (1 if (model.step_count // 20) % 2 else -1))
                    control.y = -60
                    control.jump = False
                elif _dialogue_consultant is not None:
                    # ---- LLM pause-wait mode (BRAIN 2.4.0) ----
                    # Brain paused: hold still while waiting for the GLM
                    # decision (max DIALOGUE_LLM_WAIT_S, then the worker
                    # falls back to autonomous press_a).
                    control.x = 0
                    control.y = 0
                    control.jump = False
                    control.b = False
                    if (llm_decision is not None
                            and llm_decision_episode == dialogue_episode
                            and not llm_decision_consumed):
                        action = llm_decision.get("action", "none")
                        if action in ("press_a", "press_b"):
                            llm_press_hold = DIALOGUE_PRESS_TICKS
                            llm_press_b = action == "press_b"
                        llm_decision_consumed = True
                    if llm_press_hold > 0:
                        llm_press_hold -= 1
                        if llm_press_b:
                            control.b = True
                        else:
                            control.jump = True
                    elif (llm_decision is None
                            and time.monotonic() - llm_wait_started
                            >= DIALOGUE_LLM_WAIT_S):
                        # Belt & braces: worker should already have timed
                        # out, but never hang the brain on a lost thread.
                        control.jump = True   # autonomous A fallback
                # P1 (audit A8): the legacy pulse-A fallback (_dlg_t < 0.25)
                # is deleted together with the model's dialogue pulse block —
                # with no LLM consultant the habituation breaker below is the
                # only dialogue behaviour (safety guardrail, kept).
            else:
                llm_press_hold = 0
                control.b = False
            # EVO R28 · below-ground auto-reset: when Mario is trapped
            # below the terrain (Y < -500) or at the origin (0,0,0) with
            # a live bridge, send a sustained jump burst to reset physics.
            _py = pose_ev[1] if len(pose_ev) > 1 else 0.0
            _at_origin = (abs(pose_ev[0]) < 10 and abs(pose_ev[2]) < 10
                          and abs(_py) < 10)
            _below_ground = _py < -200
            if not bridge.stale and (_below_ground or _at_origin):
                if not getattr(control, "_below_ground_jumping", False):
                    control._below_ground_jump_start = time.monotonic()
                    control._below_ground_jumping = True
                _jump_elapsed = time.monotonic() - control._below_ground_jump_start
                if _jump_elapsed < 1.5:
                    control.jump = True
                    control.x = 0
                    control.y = 70
                else:
                    control._below_ground_jumping = False
            # Escape suppression when below ground: force the escape flag
            # off so the control cascade doesn't set x=0.  The forward+JUMP
            # from the guardrail below then has uninterrupted effect.
            if _below_ground and not bridge.stale:
                memory_ctrl.escape_behavior = False
            # Hard safety guardrail: uninterrupted forward+JUMP below ground.
            if not bridge.stale and pose_ev[1] < -200:
                control.y = max(control.y, 70)
                control.jump = True
            # ---- Phase 2 · CPG motor primitives (cascade priority 4.5,
            # between escape and jump).  Gates reuse existing memory/model
            # signals; deterministic phase scripts own the Z→A button timing
            # (no symbolic FSM patterns from the P1 PIN list). ----
            cpg.feed_pose(tick_start, pose_ev[1] if len(pose_ev) > 1 else 0.0,
                          wall_score=float(getattr(model, "wall_score", 0.0) or 0.0),
                          pushing=abs(control.x) >= 40)
            # M2.3: hard turn-reversal detector (side-flip window).  A sign
            # flip of the applied turn at |x|>=40 marks a deliberate reversal.
            global _CPG_PREV_XSIGN
            _xsign = 1 if control.x > 40 else (-1 if control.x < -40 else 0)
            model._sideflip_reversal = bool(
                _xsign != 0 and _CPG_PREV_XSIGN != 0 and _xsign != _CPG_PREV_XSIGN)
            _CPG_PREV_XSIGN = _xsign
            # C9: gate CPG behind LIF confidence.  If the LIF motor pools are
            # producing meaningful output (forward >= 10 or turn >= 10) the
            # neural network wins — CPG only activates when the brain has no
            # opinion (motor dead zone).  This prevents hardcoded primitives
            # from overriding an active LIF output that may be better suited
            # to the current terrain (e.g. climbing a slope vs LONG_JUMP into
            # a wall while fallen).
            if cpg.active is None and not dlg_now and not reflex_override \
                    and not (control.y > 10 or abs(control.x) > 10):
                # is_ramp is only assigned inside the cliff block (step>10);
                # recompute locally so early ticks never hit an unbound name.
                _cpg_ramp = (getattr(model, "ramp_score", 0.0) > 0.5
                             or getattr(model, "ground_angle", 0.0) > 0.3)
                # M1.2: operator whitelist (active_strategy.json hot-reload)
                _wl = set(_active_strategy.get("primitives_enabled")
                          or ACTIVE_STRATEGY_DEFAULTS["primitives_enabled"])
                # M3.2: MBON-assisted longjump gating.  The longjump_bias
                # column learns scene-action payoff; while positive it halves
                # the stuck threshold (self-paced — with the column still
                # negative the rule gate behaves exactly as before).
                _lj_stuck_need = 3.0
                if len(getattr(model.mushroom, "mbon_outputs", [])) > 8 \
                        and float(model.mushroom.mbon_outputs[8]) > 0:
                    _lj_stuck_need = 1.5
                # M2.1: coach/operator scene-preference hint wins first —
                # subject to whitelist + CPG state preconditions (request()
                # rejects illegal combos itself).
                _scene_label = str(getattr(model, "scene_name", "")
                                   or getattr(model, "scene_label", "") or "")
                _pref = _active_strategy.get("primitives_prefer") or {}
                _requested = False
                for _tag, _prim_name in _pref.items():
                    if _prim_name not in _wl or not _tag:
                        continue
                    if _tag.lower() in _scene_label.lower():
                        try:
                            _requested = cpg.request(
                                tick_start, Primitive(_prim_name))
                        except ValueError:
                            _requested = False
                        if _requested:
                            break
                if not _requested and ("longjump" in _wl and _cpg_ramp
                        and memory_ctrl.stuck_duration > _lj_stuck_need
                        and control.y > 40):
                    # Check if last primitive was ineffective - rotate
                    _last_disp = getattr(memory_ctrl, "disp_60s", 0) or 0
                    if _last_disp < 30 and memory_ctrl.stuck_duration > 60:
                        _alt_prim = Primitive.SIDE_FLIP if "sideflip" in _wl else Primitive.LONG_JUMP
                        cpg.request(tick_start, _alt_prim)
                    else:
                        cpg.request(tick_start, Primitive.LONG_JUMP)
                elif memory_ctrl.fallen:
                    # Fallen recovery with alternating primitives
                    global _CPG_FALLEN_TOGGLE
                    _CPG_FALLEN_TOGGLE += model.dt
                    if "longjump" in _wl and (_CPG_FALLEN_TOGGLE % (_CPG_FALLEN_SWITCH_S * 2) < _CPG_FALLEN_SWITCH_S):
                        cpg.request(tick_start, Primitive.LONG_JUMP)
                    elif "backflip" in _wl:
                        cpg.request(tick_start, Primitive.BACKFLIP)
                elif ("groundpound" in _wl
                      and cpg.state.value == "airborne"
                      and getattr(model, "cliff_confirmed", False)):
                    cpg.request(tick_start, Primitive.GROUND_POUND)
                # M1.2: punch — interactive target near + grounded + stationary
                elif ("punch" in _wl and cpg.state.value == "grounded"
                      and getattr(model, "interactive_near", False)
                      and control.x == 0 and control.y < 8):
                    cpg.request(tick_start, Primitive.PUNCH)
                # M1.2: dive — airborne with a locked small target
                elif ("dive" in _wl and cpg.state.value == "airborne"
                      and getattr(model, "target_count", 0) > 0):
                    cpg.request(tick_start, Primitive.DIVE)
                # M2.3: wall jump — WALL window + still wedged (stuck active)
                elif ("walljump" in _wl and cpg.state.value == "wall"
                      and memory_ctrl.stuck_duration > 2.0):
                    cpg.request(tick_start, Primitive.WALL_JUMP)
                # M2.3: side flip — hard turn reversal while grounded
                elif ("sideflip" in _wl and cpg.state.value == "grounded"
                      and getattr(model, "_sideflip_reversal", False)):
                    cpg.request(tick_start, Primitive.SIDE_FLIP)
            cpg_phase = cpg.update(tick_start)
            # t25 P0 (LIF competition first): the CPG phase used to clobber
            # the stick unconditionally, so every active primitive overrode
            # the network's decision.  Now: when the LIF motor pools are
            # actually driving (|x|>8 or |y|>8) the network keeps ownership —
            # only the strike/crouch neural gates stay active (primitive
            # influence flows through current injection, not field writes).
            # The hardcoded primitive takes the stick ONLY on ~zero LIF
            # output.  decision_source records lf_steering / lf_escape.
            _lif_motion = abs(control.x) > 8 or abs(control.y) > 8
            if cpg_phase is not None:
                _strike_gates = ("punch", "dive")
                _crouch_gates = ("longjump", "backflip", "groundpound", "crawl")
                model.set_cpg_gate(
                    strike=1.0 if cpg_phase.primitive.value in _strike_gates else 0.0,
                    crouch=1.0 if cpg_phase.primitive.value in _crouch_gates else 0.0)
                if not _lif_motion:
                    control = cpg_apply_phase(control, cpg_phase)
            else:
                model.set_cpg_gate(0.0, 0.0)
                if cpg.completed > _cpg_last_completed:
                    model.add_primitive_outcome(cpg.last_primitive, True)
                    # M3.3/S2: record a completion event (distance filled by
                    # the next memory update cycle; escape table renders it).
                    escape_buffer.start_event(
                        tick_start, f"cpg_{cpg.last_primitive}",
                        pose_ev[0] if len(pose_ev) > 0 else 0.0,
                        pose_ev[2] if len(pose_ev) > 2 else 0.0)
                    escape_buffer.resolve_current(
                        float(getattr(memory_ctrl, "disp_60s", 0) or 0))
                elif cpg.aborted > _cpg_last_aborted:
                    model.add_primitive_outcome(cpg.last_primitive, False)
                    escape_buffer.start_event(
                        tick_start, f"cpg_abort_{cpg.last_primitive}",
                        pose_ev[0] if len(pose_ev) > 0 else 0.0,
                        pose_ev[2] if len(pose_ev) > 2 else 0.0)
                    escape_buffer.resolve_current(
                        float(getattr(memory_ctrl, "disp_60s", 0) or 0))
            _cpg_last_completed, _cpg_last_aborted = cpg.completed, cpg.aborted
            bridge.write_control(control.x, control.y, control.jump,
                                 b=getattr(control, "b", False),
                                 z=getattr(control, "z", False))
            # ---- Decision attribution audit (read-only, telemetry only) ----
            # Priority mirrors the control cascade.  P1: bold_explore and
            # collision branches retired with their bypass code paths.
            if dlg_now:
                decision_source = "dialogue"
            elif cliff_triggered:
                decision_source = "cliff_reflex"
            elif reflex_override:
                decision_source = "anomaly_reflex"
            elif memory_ctrl.escape_behavior:
                decision_source = "escape"
            elif cpg_phase is not None:
                decision_source = f"cpg_primitive:{cpg_phase.primitive.value}"
            elif control.jump:
                decision_source = "jump"
            else:
                decision_source = "steering"
            replay.add((model.step_count - 1) * model.dt, frame, control, spikes, bridge.frame_metadata)
            observatory.observe(frame, seq, control, spikes, bridge.game_status(),
                                causal=dict(cliff_conf=round(memory_ctrl.cliff_confidence, 3),
                                            stuck_conf=round(memory_ctrl.stuck_score, 3),
                                            cliff_confirmed=bool(model.cliff_confirmed),
                                            decision_source=decision_source))
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
                    rss_mb=(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e6
                            if resource else 0.0))
                packet_queue.put_nowait(packet)
                log.write(json.dumps(dict(wall_s=tick_start-started, steps=model.step_count, rtf=rtf,
                    latency_ms=latency_ms,
                    rss_mb=(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e6
                            if resource else 0.0),
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
                # Serve the FULL retained buffer (6000 pts ≈ whole session) so
                # the trajectory page window matches the dashboard session,
                # not just the last ~500 publishes.
                DashboardHTTP.trajectory = json.dumps(DashboardHTTP.trajectory_points, default=str).encode()

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
                # Mirror memory controller state onto model for dopamine computation
                model.stuck_duration = memory_ctrl.stuck_duration
                model.fallen = memory_ctrl._fallen
                model._revisit_penalty = memory_ctrl.revisit_penalty
                # EVO R14: anomaly-state mirror — DAN dopamine input for the
                # mushroom body's loop-suppression learning.
                model.anomaly_state_name = memory_ctrl.anomaly_state
                # EVO R15: cliff-standoff mirror — standoff duration + the
                # FailureMemory tangential detour bias (sensory gate only;
                # the LIF network decides the actual heading).
                model.cliff_standoff_s = memory_ctrl.cliff_standoff_s
                model.cliff_tangent_bias = memory_ctrl.cliff_tangent_bias(
                    pose[0], pose[2], pose[3])
                # L1 spatial-memory → CX: sample the visit map in the 4
                # directions relative to heading and hand the CX goal columns a
                # turn bias toward fresher ground.  Brain-first sensory gate
                # only — the LIF network still owns the heading decision.
                try:
                    model.cx_novelty_direction = memory_ctrl.spatial.novelty_direction(
                        pose[0], pose[2], pose[3],
                        dead_end_keys=set(memory_ctrl.dead_end_cells),
                        scene_change_rate=model.scene_change_rate,
                        forced_bold_explore=bool(getattr(memory_ctrl, "forced_bold_explore", False)))
                except Exception:
                    pass
                # EVO R19: restlessness inputs (loop pressure) + recognition
                model.loop_score = memory_ctrl.spatial.loop_score
                model.scene_danger = scene_recognizer.danger_level()
                # EVO R30: mirror pose_y for below-ground forward boost
                model.pose_y = pose_ev[1] if len(pose_ev) > 1 else 0.0
                # EVO R22: mirror MBON forward for spontaneous recovery
                model.mb_mbon_forward = round(
                    float(getattr(model.mushroom, "mbon_outputs", [0])[0]), 4)
                # EVO R20 (CX-2): feed forward speed + scene re-anchor on
                # scene change (the CX integrates displacement from anchor)
                model.forward_units_per_tick = getattr(control, "forward_rate", 0.0) * 1.2
                if getattr(model, "scene_change", False):
                    model.cx.set_anchor(pose[0], pose[2])
                # EVO R20 (CX-1): sky azimuth from blue-dominant hue bands —
                # visual compass correction for the CX ring attractor
                _sx = _sy = 0.0
                for _i in range(8):
                    _hue = (model.color_azimuth or {}).get(f"hue_az{_i}")
                    if _hue is None:
                        continue
                    _w = max(0.0, math.cos(math.radians(_hue - 230.0)))
                    _baz = -135.0 + (_i + 0.5) * 33.75
                    _sx += _w * math.cos(math.radians(_baz))
                    _sy += _w * math.sin(math.radians(_baz))
                model.visual_azimuth = (math.atan2(_sy, _sx)
                                        if (_sx or _sy) else None)
                # EVO R20 (CX-3): multi-source goal vectors (sensory) — the
                # CX does the vector competition and picks the heading.
                try:
                    model.cx_goal_vectors = memory_ctrl.navigation_vectors(
                        pose[0], pose[2], pose[3], model.cx_novelty_direction)
                except Exception:
                    model.cx_goal_vectors = None
                # Periodic scene-database persistence (every ~600 ticks ≈ 12s)
                scene_save_counter += 1
                if scene_save_counter >= 600:
                    scene_save_counter = 0
                    memory_ctrl.save_scene_db()
                    scene_recognizer.save(_labels_path)
                    # L2: periodic trajectory snapshot for the replay page.
                    # The old code only saved .trajectory.npz on graceful exit,
                    # which never happens under consolidate restarts — so the
                    # replay page's File list stayed empty forever.
                    try:
                        _tp = DashboardHTTP.trajectory_points
                        if len(_tp) >= 2:
                            _arr = dict(
                                t=np.array([p["t"] for p in _tp]),
                                x=np.array([p["x"] for p in _tp]),
                                y=np.array([p["y"] for p in _tp]),
                                z=np.array([p["z"] for p in _tp]),
                                heading=np.array([p["heading"] for p in _tp]),
                                ctrl_x=np.array([p["ctrl_x"] for p in _tp], dtype=int),
                                ctrl_y=np.array([p["ctrl_y"] for p in _tp], dtype=int),
                                game_frame=np.array([p.get("game_frame", 0) for p in _tp], dtype=int))
                            _arts = project / "artifacts"
                            _arts.mkdir(parents=True, exist_ok=True)
                            np.savez_compressed(_arts / "latest-session.trajectory.npz", **_arr)
                            if scene_save_counter % 10 == 1:   # ≈ every 10 min, timestamped
                                np.savez_compressed(
                                    _arts / f"session-{time.strftime('%Y%m%d-%H%M')}.trajectory.npz", **_arr)
                                _snaps = sorted(_arts.glob("session-*.trajectory.npz"))
                                for _old in _snaps[:-20]:
                                    _old.unlink(missing_ok=True)
                    except Exception:
                        pass
                xs, zs, heats = memory_ctrl.spatial.get_heatmap()
                DashboardHTTP.memory_json = json.dumps({
                    # visited-cell heat grid (same source as the 2D heatmap) +
                    # traversal topology, for the 3D trajectory map overlay
                    "heat_cells": [[round(float(x), 1), round(float(z), 1), round(float(h), 3)]
                                   for x, z, h in zip(xs, zs, heats)],
                    "adjacency": memory_ctrl.spatial.adjacency_list(400),
                    "stuck_score": round(memory_ctrl.stuck_score, 3),
                    "stuck_duration": round(memory_ctrl.stuck_duration, 3),
                    "cliff_standoff_s": round(memory_ctrl.cliff_standoff_s, 1),
                    "novelty": round(memory_ctrl.novelty, 3),
                    "escape_behavior": memory_ctrl.escape_behavior,
                    "cpg": cpg.status(),
                    "loop_score": round(memory_ctrl.spatial.loop_score, 3),
                    "exploration_mode": memory_ctrl.spatial.exploration_mode,
                    "visited_cells": memory_ctrl.spatial.visited_cells,
                    "coverage_pct": round(memory_ctrl.coverage_pct, 1),
                    "coverage_rate": round(memory_ctrl.coverage_rate, 4),
                    "exploration_speed": round(memory_ctrl.coverage_rate * 60, 2),
                    "dead_end_count": memory_ctrl.dead_end_count,
                    "dead_end_cells": [[k[0], k[1]] for k in memory_ctrl.dead_end_cells][:50],
                    "cx_novelty_direction": round(getattr(model, "cx_novelty_direction", 0.0), 3),
                    "adjacency_edges": memory_ctrl.spatial.adjacency_count,
                    "traversal_steps": memory_ctrl.spatial.traversal_steps,
                    "recent_path": memory_ctrl.spatial.recent_path(80),
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
                    # EVO R12: reflex-ineffective escalation flag
                    "reflex_ineffective": bool(getattr(memory_ctrl, "reflex_ineffective", False)),
                    "disp_60s": getattr(memory_ctrl, "disp_60s", None),
                    # EVO R13: dialogue pause-wait scene observability
                    "dialogue_active": bool(getattr(model, "dialogue_active", False)),
                    "scene_label": _scene_name(model, memory_ctrl, scene_recognizer),
                    # EVO R21: coach layer reads memory_json["scene_name"] —
                    # was missing, runner.py fell back to "?" every time.
                    "scene_name": _scene_name(model, memory_ctrl, scene_recognizer),
                    # Health scoring
                    "health_score": round(memory_ctrl.health_score, 4),
                    "stall_ratio": round(memory_ctrl.stall_ratio, 3),
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
                    "blue_dom": round(getattr(model, "blue_dom", 0.0), 4),
                    "underwater": getattr(model, "underwater", False),
                    # Scene naming: human-readable scene identification
                    "scene_name": _scene_name(model, memory_ctrl, scene_recognizer),
                    "scene_hash": (memory_ctrl.scene_id or "")[:6],
                    "skill_version": SKILL_VERSION,
                    "brain_version": BRAIN_VERSION,
                    # EVO R15: expose P1-P3 signal heads for the skill layer
                    "danger_red_index": round(getattr(model, "danger_red_index", 0.0), 4),
                    "sky_blue_index": round(getattr(model, "sky_blue_index", 0.0), 4),
                    "emd_on_down": round(model.emd_on_down, 4),
                    "target_count": model.target_count,
                    "mb_assoc_count": getattr(model.mushroom, "assoc_count", 0),
                    "cliff_standoff_s": round(getattr(model, "cliff_standoff_s", 0.0), 1),
                    # EVO R16: causal + plasticity telemetry for the skill layer
                    "decision_source": decision_source,
                    # Phase 4/M4: displacement after a CPG primitive, for EVO
                    # primitive_zero_disp / primitive_timeout pattern checks.
                    "primitive_disp": getattr(memory_ctrl, "disp_60s", None),
                    "cpg_status": cpg.status(),
                    "cliff_conf": round(memory_ctrl.cliff_confidence, 3),
                    "gate_forward": getattr(control, "forward_rate", 0.0) > 0.4,
                    "gate_jump": getattr(control, "jump_rate", 0.0) > 2.0,
                    "hrc_asymmetry": round(getattr(model, "true_hrc_asymmetry", 0.0), 4),
                    "emd_on_total": round(model.emd_on_total, 4),
                    "emd_off_total": round(model.emd_off_total, 4),
                    "mb_dopamine": round(getattr(model.mushroom, "dopamine", 0.0), 4),
                    "mb_mbon_forward": round(float(model.mushroom.mbon_outputs[0]), 4),
                    "mb_mbon_jump": round(float(model.mushroom.mbon_outputs[3]), 4),
                    # Phase 3 primitive columns (punch/dive/groundpound/longjump)
                    "mb_mbon_punch": round(float(model.mushroom.mbon_outputs[5]), 4),
                    "mb_mbon_dive": round(float(model.mushroom.mbon_outputs[6]), 4),
                    "mb_mbon_groundpound": round(float(model.mushroom.mbon_outputs[7]), 4),
                    "mb_mbon_longjump": round(float(model.mushroom.mbon_outputs[8]), 4),
                    # M3.1: per-column weight means — scene-independent
                    # learning-direction metric (outputs vary with scene KC).
                    "mb_w_punch": round(float(model.mushroom.weights[:, 5].mean()), 5),
                    "mb_w_dive": round(float(model.mushroom.weights[:, 6].mean()), 5),
                    "mb_w_groundpound": round(float(model.mushroom.weights[:, 7].mean()), 5),
                    "mb_w_longjump": round(float(model.mushroom.weights[:, 8].mean()), 5),
                    "fg_fraction": round(getattr(model, "fg_fraction", 0.0), 4),
                    "mb_weight_std": round(float(getattr(model.mushroom, "weights").std()), 4),
                    "mb_saturation_events": getattr(model.mushroom, "saturation_events", 0),
                    "local_motion": round(model.local_motion_energy, 4),
                    "local_motion_detected": model.local_motion_detected,
                    "dialogue_active": getattr(model, "dialogue_active", False),
                    "llm_decision": {
                        "status": llm_decision_status,
                        "action": (llm_decision or {}).get("action"),
                        "reason": (llm_decision or {}).get("reason", ""),
                        "episode": dialogue_episode,
                        "wait_s": (round(time.monotonic() - llm_wait_started, 1)
                                   if llm_decision_status == "waiting" else None),
                        "ts": (llm_decision or {}).get("ts"),
                    },
                    "interactive_near": getattr(model, "interactive_near", False),
                    "evo_findings": _evo_findings,
                    "brain_version": BRAIN_VERSION,
                    "evo_iter": _evo_iter_counter,
                    "command_decoupled": command_decoupled,
                    "wall_score": round(model.wall_score, 4),
                    "ramp_score": round(model.ramp_score, 4),
                    "opening_score": round(model.opening_score, 4),
                    "sky_score": round(model.sky_score, 4),
                    "enclosure_score": round(getattr(model, "enclosure_score", 0.0), 4),
                    "ground_angle": round(model.ground_angle, 4),
                    "door_frame_score": round(model.door_frame_score, 4),
                    "opening_width": round(model.opening_width, 4),
                    "tick": model.step_count,
                    # t19: SM64 freeze watchdog — seqlock frame seq stagnant
                    # >5 s means the game producer is dead/frozen while the
                    # brain keeps ticking; dashboard shows a red pill.
                    "bridge_stale": bool(bridge.stale),
                    # Multi-channel retina summary values
                    "on": round(model.on_energy, 4),
                    "off": round(model.off_energy, 4),
                    "sustained": round(model.sustained_energy, 4),
                    "edge_0": round(model.edge_0, 4),
                    "edge_45": round(model.edge_45, 4),
                    "edge_90": round(model.edge_90, 4),
                    "edge_135": round(model.edge_135, 4),
                    "scene_match": round(memory_ctrl.scene_match, 4),
                    # Dopamine-gated gain modulation (plasticity proxy)
                    "dopamine_gain": {
                        "visual": round(model.dopamine_gain.get_gain("visual"), 4),
                        "forward": round(model.dopamine_gain.get_gain("forward"), 4),
                        "turn": round(model.dopamine_gain.get_gain("turn"), 4),
                        "jump": round(model.dopamine_gain.get_gain("jump"), 4),
                        "recurrent": round(model.dopamine_gain.get_gain("recurrent"), 4),
                    },
                    "reward_signal": round(getattr(model, "reward_signal", 0.0), 4),
                    "cumulative_reward": round(getattr(model, "_cumulative_reward", 0.0), 4),
                    # Python→neuron error gradient bridge (t3)
                    "error_gradient": getattr(model, "_last_error_gradient", {}),
                    "corrective_current": list(getattr(model, "_corrective_current_applied", (0.0, 0.0))),
                    # EVO: plasticity summary fields (used by EvolutionSkill pattern matching)
                    "dopamine_gain_avg": round(_plasticity_metrics["dopamine_gain_avg"], 4),
                    "learning_progress": round(_plasticity_metrics["learning_progress"], 4),
                    "mushroom_weight_changes": _plasticity_metrics["mushroom_weight_changes"],
                    "reward_trend": round(_plasticity_metrics["reward_trend"], 4),
                    "error_gradient_mean": round(_plasticity_metrics["error_gradient_mean"], 4),
                    "gain_update_count": _plasticity_metrics["gain_update_count"],
                    # EVO telemetry_gap fix: expose all pattern-required fields
                    "anomaly_state": memory_ctrl.anomaly_state_name or "idle",
                    "reflex_active": memory_ctrl.reflex_active,
                    "escape_behavior": memory_ctrl.escape_behavior,
                    "pos_y": round(pose_ev[1], 1) if len(pose_ev) > 1 else 0.0,
                    "cpg_completed": cpg.completed if hasattr(cpg, 'completed') else 0,
                    "cpg_aborted": cpg.aborted if hasattr(cpg, 'aborted') else 0,
                    "visited_cells": memory_ctrl.spatial.visited_cells,
                    "jump_not_active": getattr(control, "jump_rate", 0.0) < 0.04,
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
                    "enclosure_score": round(getattr(model, "enclosure_score", 0.0), 4),
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
                import base64 as _b64
                _raw_scr = bridge.read_screen() if hasattr(bridge, "read_screen") else None
                if _raw_scr:
                    DashboardHTTP.screen_json = json.dumps(
                        {"screen_b64": _b64.b64encode(_raw_scr).decode()}).encode()
                DashboardHTTP.history_json = json.dumps(
                    list(DashboardHTTP.signal_history),
                    separators=(",", ":")).encode()

                # ---- Plasticity monitoring (t4) ----
                # Track error gradient over a rolling window of ~100 ticks
                _err = getattr(model, "_last_error_gradient", {}).get("error", 0.0)
                _error_gradient_buffer.append(abs(_err))
                _plasticity_tick += 1
                if _plasticity_tick % 100 == 0:
                    gains = model.dopamine_gain.get_all_gains()
                    avg_gain = sum(gains.values()) / max(len(gains), 1)
                    _plasticity_metrics.update({
                        "learning_progress": round(
                            sum(_error_gradient_buffer) / max(len(_error_gradient_buffer), 1), 4),
                        "dopamine_gain_avg": round(avg_gain, 4),
                        "mushroom_weight_changes": getattr(
                            model.mushroom, "assoc_count", 0),
                        "reward_trend": round(
                            getattr(model, "_cumulative_reward", 0.0), 4),
                        "error_gradient_mean": round(
                            sum(_error_gradient_buffer) / max(len(_error_gradient_buffer), 1), 4),
                        "gain_update_count": model.dopamine_gain.gain_update_count,
                    })

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
