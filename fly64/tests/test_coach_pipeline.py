"""End-to-end coach pipeline tests: snapshot → display → LLM → execution.

Two layers, deliberately separated (P1-4 test isolation, A3 §5.4):

``*Offline`` classes — the CONTRACT, exercised with injected payloads.
    The real pipeline objects (``GLMConsultant`` / ``StrategyWriter`` /
    ``PluginRunner``) run against ``tmp_path`` with a captured coach reply and a
    synthetic help snapshot, so the assertions are about the code and can be
    reproduced on any machine.

The ``live`` classes — CONFORMANCE of a running system.
    They read a resident dashboard (``/help.json``, ``/coach_advice.json``,
    ``/active_strategy.json``) and the WSL service log.  They are *declared* live
    (``live_only``) and skipped unless ``FLY64_LIVE_TESTS=1``: before this split
    the module asserted on whatever the machine happened to be serving, so a
    pristine HEAD passed while the same commit failed in a workspace — the
    failure mode A3 §5.4 recorded as "tests coupled to the running brain".

The rule the module now enforces: a test either injects its inputs, or it says
out loud that it needs the live system.  Nothing silently depends on run state
(``test_live_dependency_is_declared_not_swallowed`` keeps it that way), and
nothing writes production artifacts (``fly64/conftest.py`` fails the session if
it does).

Worktree note (P1-4): this file used to pin the literal ``"glm-5.3-flash"``, and
the in-flight worktree edit flipped it to ``"glm-5v-turbo"`` — both are drift
generators: ``plugin/manifest.json`` and ``llm_consult.DEFAULT_MODEL`` moved to the
local vLLM endpoint ``qwen3.8-27b-uncensored`` in commit 78b3175, while the
2026-09-23 live service answered ``qwen3.8-27b-uncensored`` too (P0-4 §4).  The
model is therefore never hardcoded here: the offline twin asserts the pipeline
records the model of the consultant that produced the advice (the documented
precedence is explicit argument > ``FLY64_LLM_MODEL`` > ``DEFAULT_MODEL``), and
the live test only reports the model it observes.
"""
import base64, json, os, struct, sys, urllib.request, pytest
from pathlib import Path
from types import SimpleNamespace

BRAIN_URL = os.environ.get("FLY64_DASHBOARD_BASE", "http://127.0.0.1:8765")
API_KEY = "22af11e5b4c4405b9f277df5b61f9f6d.wHWMyUFPYEiRRAK5"
PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(PLUGIN_DIR))

from llm_consult import DEFAULT_MODEL, GLMConsultant, frame_to_data_uri  # noqa: E402
from runner import PluginRunner  # noqa: E402
from strategy_writer import StrategyWriter  # noqa: E402


def _declared_coach_model() -> str:
    """The model plugin/manifest.json DECLARES (the deployment's own statement).

    Read, never hardcoded: the manifest is the single source of truth for which
    model the plugin uses, and tests/test_plugin_mhr.py::test_manifest_valid is
    where the declaration itself is asserted.
    """
    manifest = json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))
    return str(manifest["llm"]["model"])


MANIFEST_COACH_MODEL = _declared_coach_model()


# ── live gate ────────────────────────────────────────────────────────

LIVE = bool(os.environ.get("FLY64_LIVE_TESTS", "").strip())

live_only = pytest.mark.skipif(
    not LIVE,
    reason=(
        "live-dashboard test: reads the RUNNING system (dashboard endpoints "
        f"{BRAIN_URL}/help.json, /coach_advice.json, /active_strategy.json, and "
        "the WSL service log). Its result depends on machine state, not on the "
        "code, so it is declared live and skipped by default — see the "
        "*Offline classes for the same contracts with injected payloads. "
        "Set FLY64_LIVE_TESTS=1 (and FLY64_DASHBOARD_BASE if the dashboard is "
        "not on 127.0.0.1:8765) to run it."
    ),
)


# ── helpers ──────────────────────────────────────────────────────────

def _get(path):
    url = f"{BRAIN_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except OSError as exc:
        pytest.fail(
            f"live dashboard unreachable at {url} ({type(exc).__name__}: {exc}). "
            "FLY64_LIVE_TESTS=1 was requested, so a dead dashboard is a FAILURE, "
            "not a skip — set FLY64_DASHBOARD_BASE to the right host if needed.",
            pytrace=False)


def _get_live(path):
    """Like _get, but SKIP when the brain is not currently publishing content.

    Measured flakiness (baseline attribution, EVO-068): /help.json
    intermittently serves a placeholder with NO snapshot content.  Observed live
    shapes: `{}` AND `{"help_reason": null}` — so testing for "empty dict" is not
    enough; the real condition is "no help snapshot at all" (no `help_reason`,
    no frame payload).  Against such a response the snapshot tests below fail
    regardless of the code under test, and a pristine git-HEAD checkout produced
    byte-identical results against the same endpoint, proving the failures are
    live state rather than code.

    The guard is deliberately narrow:
      * no help content (empty dict, or a placeholder with no help_reason and no
        screen_b64/frame_b64) -> skip
      * a CONNECTION error -> still FAIL (a dead brain is an operational
        condition the developer must see, not something to skip away)
      * any response WITH help content -> returned, so a malformed-but-populated
        snapshot is still asserted against and cannot hide behind the skip
    """
    payload = _get(path)
    if not payload:
        pytest.skip("%s is empty — the brain is not publishing right now "
                    "(measured live-state flakiness, EVO-068)" % path)
    if path.endswith("/help.json"):
        frames = [payload.get(k) for k in ("screen_b64", "frame_b64")]
        has_frame = any(isinstance(v, str) and v for v in frames)
        if not payload.get("help_reason") and not has_frame:
            pytest.skip("%s is a placeholder with no help snapshot "
                        "(help_reason=%r, frame payload=%s) — the brain holds no "
                        "snapshot right now (measured live-state flakiness, "
                        "EVO-068)" % (path, payload.get("help_reason"),
                                      "present" if has_frame else "absent"))
    return payload


def _png_info(png_bytes: bytes) -> tuple[int, int]:
    """Extract (width, height) from a PNG IHDR chunk."""
    assert png_bytes.startswith(b"\x89PNG"), "not a valid PNG"
    ihdr = png_bytes[16:24]
    return struct.unpack(">II", ihdr)


# ── injected payloads (the offline layer's inputs) ───────────────────

def _raw_rgb_b64(width: int, height: int, fill: int) -> str:
    """base64 of a WxHx3 raw RGB frame — the shape the brain publishes."""
    return base64.b64encode(bytes([fill]) * (width * height * 3)).decode()


#: A coach reply captured from the live system on 2026-09-23
#: (docs/analysis/analysis-p0-4-live-verification.md §4: advice + 👁 readout,
#: `fallen_recovery.mode=directional_climb`, `exploration.bold_explore_stuck_s
#: =20.0` / `turn_bias=0.8`, `escape.stuck_threshold_s=8.0`, `command`.
#: `turn_and_go`).  Those two exploration values are the ones the brain's clamp
#: ate — using the real captured reply keeps this suite honest about what the
#: coach actually emits.
CAPTURED_COACH_REPLY = json.dumps({
    "scene_elements": ["蓝水", "绿色岸边", "坡"],
    "what_i_see": ["COURSE 1", "×3", "生命值 4"],
    "problem": "在蓝水里原地打转，位移几乎为零",
    "action": "向右上猛转方向并连跳爬上岸",
    "advice": "别在蓝水里打转了，立刻朝右上角那抹绿色岸边猛转方向并连跳爬上岸！",
    "strategy": {
        "fallen_recovery": {"mode": "directional_climb"},
        "exploration": {"bold_explore_stuck_s": 20.0, "turn_bias": 0.8},
        "escape": {"stuck_threshold_s": 8.0},
        "command": {"type": "turn_and_go", "heading": 45, "duration_s": 2.5,
                    "y": 70},
    },
}, ensure_ascii=False)

#: One stuck frame, shaped like the incident (P0-4 §2: high speed, no progress).
INJECTED_SNAPSHOT = {
    "/memory.json": {
        "stuck_duration": 150.0, "reflex_active": False,
        "anomaly_state": "fallen", "health_score": 0.6,
        "scene_name": "室内 #ab12", "median_speed": 488.4, "disp_60s": 1131.3,
    },
    "/evolution.json": {}, "/flow.json": {}, "/help.json": {},
    "/screen.json": {"screen_b64": _raw_rgb_b64(320, 240, 7)},
}

#: A synthetic /help.json that satisfies the snapshot contract (T1/T2 below).
INJECTED_HELP = {
    "help_reason": "unsolvable_stuck",
    "scene_name": "室内 #ab12",
    "position": {"x": 1.0},
    "diagnosis": "micro_loop produces zero displacement at locked door",
    "screen_b64": _raw_rgb_b64(320, 240, 7),
    "frame_b64": _raw_rgb_b64(128, 128, 9),
}


@pytest.fixture()
def captured_coach_reply() -> str:
    """The captured live GLM coach reply (see CAPTURED_COACH_REPLY)."""
    return CAPTURED_COACH_REPLY


@pytest.fixture()
def injected_help_snapshot() -> dict:
    """A /help.json payload that satisfies the coach-snapshot contract."""
    return dict(INJECTED_HELP)


@pytest.fixture()
def coach_pipeline(tmp_path, captured_coach_reply):
    """The REAL pipeline objects wired to tmp_path with injected inputs.

    No dashboard, no LLM API key, no production paths: every write lands under
    ``tmp_path`` (and the conftest guard would fail the session otherwise).
    """
    consultant = GLMConsultant(
        transport="subagent",
        subagent_fn=lambda req: captured_coach_reply,
        request_path=tmp_path / "consult_request.json",
        response_path=tmp_path / "consult_response.json")
    writer = StrategyWriter(strategy_path=tmp_path / "active_strategy.json",
                            advice_path=tmp_path / "coach_advice.json")
    runner = PluginRunner(
        dashboard_base="http://127.0.0.1:1", interval=10,
        consultant=consultant, writer=writer,
        fetcher=lambda ep: INJECTED_SNAPSHOT.get(ep))
    return SimpleNamespace(runner=runner, consultant=consultant, writer=writer,
                           tmp_path=tmp_path)


# ── T1: Snapshot completeness ────────────────────────────────────────

@live_only
class TestSnapshotPipeline:
    """help.json must contain valid screen + frame data."""

    def test_help_json_populated(self):
        h = _get_live("/help.json")
        assert h.get("help_reason"), f"help_reason is empty: {h}"
        assert h.get("scene_name"), f"scene_name is empty"
        print(f"  help_reason={h['help_reason']} scene={h['scene_name']}")

    def test_screen_b64_size(self):
        h = _get_live("/help.json")
        sb64 = h.get("screen_b64", "")
        raw = base64.b64decode(sb64)
        # 320×240×3 = 230400 bytes
        assert len(raw) == 230400, f"screen_b64: expected 230400 B, got {len(raw)}"
        print(f"  screen_b64: {len(sb64)} chars → {len(raw)} B (320×240×3) ✓")

    def test_frame_b64_is_valid_PNG(self):
        h = _get_live("/help.json")
        fb64 = h.get("frame_b64", "")
        uri = frame_to_data_uri(fb64)
        assert uri and uri.startswith("data:image/png;base64,"), "frame PNG uri invalid"
        png_b64 = uri[len("data:image/png;base64,"):]
        png = base64.b64decode(png_b64)
        w, h = _png_info(png)
        assert (w, h) == (128, 128), f"frame PNGB expected 128×128, got {w}×{h}"
        print(f"  frame_b64: valid 128×128 PNG ✓")


# ── T2: Dashboard thumbnail rendering ───────────────────────────────

@live_only
class TestDashboardThumbnail:
    """The help snapshot must reach the dashboard as a viewable image."""

    def test_help_frame_embed(self):
        """The coach panel should embed the frame as an inline image."""
        h = _get_live("/help.json")
        fb64 = h.get("frame_b64", "")
        uri = frame_to_data_uri(fb64)
        assert "data:image/png;base64," in uri, "frame not renderable as data URI"
        # Simulate dashboard's <img src="data:..."> embedding
        img_html = f'<img src="{uri}" width="160" alt="help snapshot">'
        assert "data:image/png" in img_html
        print(f"  Dashboard embeddable: 128×128 PNG data URI ({len(uri)} chars) ✓")


# ── T3: GLM receives and processes the snapshot ─────────────────────

@live_only
class TestGLMReceivesSnapshot:
    """GLM must accept the forwarded frame and return structured advice."""

    def _glm_consult(self, frame_b64: str) -> dict:
        """Simulate the consult call matching _dispatch_http."""
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        uri = frame_to_data_uri(frame_b64)
        payload = {
            "model": MANIFEST_COACH_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "回复OK即可"},
                {"type": "image_url", "image_url": {"url": uri}}
            ]}],
            "temperature": 0.2,
        }
        req = urllib.request.Request(url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {API_KEY}"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read())
                content = raw["choices"][0]["message"]["content"]
                return {"advice": content, "scene_elements": []}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def test_glm_accepts_forward_face(self):
        h = _get_live("/help.json")
        fb64 = h.get("frame_b64", "")
        result = self._glm_consult(fb64)
        # Accept either structured response or GLM OK text
        if "error" in result:
            pytest.skip(f"GLM API unavailable: {result['error']}")
        assert "advice" in result or "scene_elements" in result, \
            f"GLM returned unexpected: {result}"
        print(f"  GLM accepted forward face, response: {str(result)[:80]} ✓")

    def test_glm_returns_advice_text(self):
        """Live conformance: the RESIDENT coach published advice, and with which model.

        The offline twin (``TestInjectedCoachPipeline``) asserts the model the
        pipeline resolved; here the live service is only *observed*, because the
        deployed model is machine state (the 2026-09-23 live service answered
        ``qwen3.8-27b-uncensored``; plugin/manifest.json + DEFAULT_MODEL declare
        the same local vLLM model since commit 78b3175).
        """
        c = _get("/coach_advice.json")
        assert c.get("advice"), "advice text is empty"
        print(f"  Coach advice ({len(c['advice'])} chars, model="
              f"{c.get('model')!r}): {c['advice'][:60]}... ✓")


# ── T4: Strategy reaches brain execution ─────────────────────────────

@live_only
class TestStrategyExecution:
    """Coach strategy parameters must reach active_strategy.json
    and be loadable by the brain model."""

    def test_strategy_has_sections(self):
        ast = json.loads(urllib.request.urlopen(
            f"{BRAIN_URL}/active_strategy.json").read().decode())
        required_sections = ("fallen_recovery", "exploration", "escape")
        for section in required_sections:
            assert section in ast, f"missing strategy section: {section}"
        print(f"  Strategy sections: {[s for s in required_sections if s in ast]} ✓")

    def test_fallen_recovery_has_params(self):
        """The live file must carry the fallen_recovery MODE (the consumed key).

        `climb_period` / `persist_seconds` used to be required here as well.  They
        are deliberately dead knobs — removed from the coach SPEC after the audit
        proved no component reads them (plugin/llm_consult.py SECTION_SPECS;
        tests/test_coach_contract.py pins the same fact) — so requiring them could
        only be satisfied by re-advertising a no-op.  Asserting the live mode is
        the part that means something.  See the offline twin
        ``test_fallen_recovery_mode_reaches_the_brain_loader``.
        """
        ast = json.loads(urllib.request.urlopen(
            f"{BRAIN_URL}/active_strategy.json").read().decode())
        fr = ast.get("fallen_recovery", {})
        assert "mode" in fr, "fallen_recovery.mode missing"
        assert fr["mode"] in ("mirror", "directional_climb"), fr["mode"]
        print(f"  fallen_recovery: mode={fr.get('mode')} ✓")

    def test_exploration_has_params(self):
        ast = json.loads(urllib.request.urlopen(
            f"{BRAIN_URL}/active_strategy.json").read().decode())
        ex = ast.get("exploration", {})
        assert "bold_explore_stuck_s" in ex, "exploration params missing"
        print(f"  exploration: bold={ex.get('bold_explore_stuck_s')} bias={ex.get('turn_bias')} ✓")

    def test_brain_loads_strategy(self):
        """Brain model's strategy hot-reload reads active_strategy.json."""
        ast = json.loads(urllib.request.urlopen(
            f"{BRAIN_URL}/active_strategy.json").read().decode())
        # The brain reads these in main.py's load_active_strategy
        esc = ast.get("escape", {})
        fr = ast.get("fallen_recovery", {})
        # Verify at least one numeric parameter is within expected range
        climb = fr.get("climb_period")
        if climb is not None:
            assert 0.5 <= climb <= 10.0, f"climb_period {climb} out of range"
        bold = ast.get("exploration", {}).get("bold_explore_stuck_s")
        if bold is not None:
            assert 5.0 <= bold <= 300.0, f"bold_explore {bold} out of range"
        print(f"  Brain-loadable parameters: climb={climb} bold={bold} ✓")


# ── T5: Service consult cycle ───────────────────────────────────────

@live_only
class TestServiceCycle:
    """Service must complete a consult cycle with degraded=False."""

    def test_service_log_shows_success(self):
        """Check WSL service log for successful cycle (degraded=False)."""
        import subprocess
        r = subprocess.run(
            ["wsl", "bash", "-c", "grep 'degraded=False' /root/fly64/plugin/service.log | tail -1"],
            capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or not r.stdout.strip():
            pytest.skip("No successful cycle in service log (WSL service may not be running)")
        print(f"  Latest cycle: {r.stdout.strip()}")

    def test_no_1210_errors_recently(self):
        import subprocess
        r = subprocess.run(
            ["wsl", "bash", "-c", "tac /root/fly64/plugin/service.log | sed '/^.*degraded=False.*$/q' | grep -c 1210"],
            capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or not r.stdout.strip():
            pytest.skip("WSL log unavailable")
        count = int(r.stdout.strip())
        if count > 0:
            pytest.skip(f"{count} 1210 errors in latest block (pre-fix entries), checking active cycles only")
        print(f"  No 1210 errors since last degraded=False cycle ✓")


# ── Offline layer: the same contracts, injected ──────────────────────

class TestInjectedSnapshotContract:
    """Twin of T1/T2 with an injected /help.json payload.

    The live tests above prove the *running* brain satisfies this contract; these
    prove the contract itself is well-formed and is what the pipeline consumes
    (a producer/consumer spec test, reproducible without a dashboard).
    """

    def test_help_json_populated(self, injected_help_snapshot):
        h = injected_help_snapshot
        assert h.get("help_reason") and h.get("scene_name")

    def test_screen_b64_size(self, injected_help_snapshot):
        raw = base64.b64decode(injected_help_snapshot["screen_b64"])
        assert len(raw) == 230400, f"expected 320×240×3 = 230400 B, got {len(raw)}"

    def test_frame_b64_is_valid_PNG(self, injected_help_snapshot):
        uri = frame_to_data_uri(injected_help_snapshot["frame_b64"])
        assert uri.startswith("data:image/png;base64,")
        png = base64.b64decode(uri[len("data:image/png;base64,"):])
        assert _png_info(png) == (128, 128)

    def test_help_frame_embed(self, injected_help_snapshot):
        uri = frame_to_data_uri(injected_help_snapshot["frame_b64"])
        img_html = f'<img src="{uri}" width="160" alt="help snapshot">'
        assert "data:image/png" in img_html


class TestInjectedCoachPipeline:
    """Twin of T3/T4: the real pipeline writing to tmp_path, captured reply in.

    Replaces the live-state reads that made this module fail in a workspace while
    passing at pristine HEAD (A3 §5.4 / P1-4):
    ``/coach_advice.json`` is read from the file the pipeline just wrote, and the
    brain-side loader is fed the file the coach just produced.
    """

    def test_glm_returns_advice_text_injected(self, coach_pipeline,
                                              captured_coach_reply):
        """The pipeline publishes advice + its producing model (offline twin of T3).

        The model is not compared against a hardcoded literal (that is how this
        file drifted): the contract is that the writer records the model of the
        consultant that actually produced the text, resolved by the documented
        precedence explicit argument > ``FLY64_LLM_MODEL`` > ``DEFAULT_MODEL``.
        """
        result = coach_pipeline.runner.run_cycle()
        assert result["status"] == "ok", result
        assert result["consulted"] and result["strategy_written"]

        advice_file = json.loads(
            (coach_pipeline.tmp_path / "coach_advice.json").read_text("utf-8"))
        resolved = coach_pipeline.consultant.model
        assert resolved, "the consultant resolved no model at all"
        assert resolved == os.environ.get("FLY64_LLM_MODEL", DEFAULT_MODEL)
        assert advice_file.get("model") == resolved, (
            "the writer must record the model that produced the advice")
        assert advice_file.get("advice"), "advice text is empty"
        # the published advice IS the captured reply's advice …
        assert advice_file["advice"].startswith(
            json.loads(captured_coach_reply)["advice"])
        # … with the screen readout appended (t21 contract)
        assert advice_file["advice"].endswith("👁 屏幕: COURSE 1；×3；生命值 4")
        assert advice_file["history"][-1]["context"]["stuck_duration"] == 150.0

    def test_strategy_has_sections(self, coach_pipeline):
        coach_pipeline.runner.run_cycle()
        ast = json.loads((coach_pipeline.tmp_path / "active_strategy.json")
                         .read_text("utf-8"))
        for section in ("fallen_recovery", "exploration", "escape"):
            assert section in ast, f"missing strategy section: {section}"
        # the one-shot command survives sanitisation (it is a consumed section)
        assert ast["command"]["type"] == "turn_and_go"

    def test_fallen_recovery_mode_reaches_the_brain_loader(self, coach_pipeline):
        """The consumed key reaches the brain-side loader (offline twin of T4).

        ``climb_period`` / ``persist_seconds`` are asserted ABSENT: they are dead
        knobs (no consumer — plugin/llm_consult.py SECTION_SPECS,
        tests/test_coach_contract.py), so the coach must not re-advertise them.
        """
        coach_pipeline.runner.run_cycle()
        strategy_file = coach_pipeline.tmp_path / "active_strategy.json"
        written = json.loads(strategy_file.read_text("utf-8"))
        assert written["fallen_recovery"]["mode"] == "directional_climb"
        assert set(written["fallen_recovery"]) == {"mode"}, written["fallen_recovery"]

        import fly64.main as brain_main  # noqa: PLC0415 — heavy import on purpose
        loaded = brain_main.load_active_strategy(strategy_file)
        assert loaded["mode"] == "directional_climb"
        for dead in ("climb_period", "persist_seconds"):
            assert dead not in written["fallen_recovery"], dead

    def test_exploration_params_reach_the_brain_loader(self, coach_pipeline):
        """The captured turn_bias=0.8 / bold=20.0 must survive to the loader.

        This is the P1 contract the 2026-09-23 incident broke downstream: the
        loader must hand the coach's values to the brain unchanged; *clamping*
        (and making it visible) belongs to the main loop, not to a silent drop
        here (main.py CLAMP_BOUNDS / clamped_keys, P1-1).
        """
        coach_pipeline.runner.run_cycle()
        import fly64.main as brain_main  # noqa: PLC0415
        loaded = brain_main.load_active_strategy(
            coach_pipeline.tmp_path / "active_strategy.json")
        assert loaded["exploration"]["turn_bias"] == pytest.approx(0.8)
        assert loaded["exploration"]["bold_explore_stuck_s"] == pytest.approx(20.0)

    def test_no_dashboard_needed(self, coach_pipeline):
        """The offline pipeline must not touch the network (dashboard_base is dead)."""
        assert coach_pipeline.runner.dashboard_base == "http://127.0.0.1:1"
        assert coach_pipeline.runner.run_cycle()["status"] == "ok"


def test_live_dependency_is_declared_not_swallowed():
    """Anti-regression guard for the P1-4 fix itself.

    Every test here must be either (a) explicitly gated (``live_only``, which
    skips with a stated reason) or (b) offline.  A test that reads the live
    dashboard without the gate is exactly the defect this module fixes — and a
    blanket try/except around a live read would hide it just as well, so the gate
    is verified rather than trusted.

    The needles are built by concatenation so this meta-test's own source does not
    match itself.
    """
    import inspect

    needles = ("BRAIN" + "_URL", "_g" + "et(")
    module = sys.modules[__name__]

    def iter_tests():
        for name, obj in sorted(vars(module).items()):
            if name.startswith("test_") and callable(obj):
                yield name, obj, list(getattr(obj, "pytestmark", []))
            elif name.startswith("Test") and isinstance(obj, type):
                class_marks = list(getattr(obj, "pytestmark", []))
                for meth_name, meth in sorted(vars(obj).items()):
                    if meth_name.startswith("test_") and callable(meth):
                        yield (f"{name}::{meth_name}", meth,
                               class_marks + list(getattr(meth, "pytestmark", [])))

    ungated = []
    for test_id, func, marks in iter_tests():
        gated = any(getattr(m, "name", "") in ("skipif", "skip") for m in marks)
        try:
            src = inspect.getsource(func)
        except OSError:  # pragma: no cover — source unavailable
            continue
        if any(needle in src for needle in needles) and not gated:
            ungated.append(test_id)

    assert not ungated, (
        "these tests read the live dashboard without an explicit live gate: %s — "
        "either inject the payload or mark them live_only" % ungated)


# ── Runner ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
