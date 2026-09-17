#!/usr/bin/env python3
"""GLM-5.3-flash multimodal consultation for Fly64 CoachConsult.

Sends the current game frame (base64) plus a context snapshot to
GLM-5.3-flash and parses the JSON recommendation into a strategy dict.

Transports
----------
``subagent`` (default)
    The plugin writes a consult request (frame b64 + context) to
    ``plugin/.consult_request.json``.  The DSH host agent running
    GLM-5.3-flash reads it, analyzes the screenshot and writes the raw
    model reply to ``plugin/.consult_response.json``.  This keeps the
    actual LLM call inside the DSH agent environment where the model and
    its credentials live.

``http``
    Direct OpenAI-compatible chat-completions call with a multimodal
    ``image_url`` data-URI part.  Configured via ``FLY64_LLM_BASE_URL``
    and ``FLY64_LLM_API_KEY`` environment variables.

Both transports return the raw assistant text; ``parse_response`` turns
it into a strategy dict, tolerating fenced JSON or surrounding prose.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

DIALOGUE_PROMPT_TEMPLATE = (
    "你是 SM64 果蝇脑控制系统的对话决策器。屏幕上出现了游戏对话/交互对话框。\n"
    "分析当前截屏，判断马里奥应该如何应对这个对话框：\n"
    "- press_a: 按 A 键（推进对话/确认/翻页）\n"
    "- press_b: 按 B 键（取消/跳过/关闭对话框）\n"
    "- none: 暂不按键（例如对话框仍在展开、需要先等待）\n"
    "只回复一个 JSON 对象，格式:\n"
    '{"action": "press_a|press_b|none", "reason": "一句中文理由"}'
)

DIALOGUE_ACTIONS = ("press_a", "press_b", "none")
DEFAULT_DIALOGUE_TIMEOUT = 60.0

PLUGIN_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "glm-5.3-flash"
DEFAULT_TRANSPORT = "subagent"
REQUEST_PATH = PLUGIN_DIR / ".consult_request.json"
RESPONSE_PATH = PLUGIN_DIR / ".consult_response.json"
SUBAGENT_TIMEOUT_SECONDS = 120.0
LLM_ENV_FILE = PLUGIN_DIR / "llm.env"


def _load_llm_env() -> None:
    """Load plugin/llm.env (KEY=VALUE, optional 'export ' prefix) into
    os.environ as DEFAULTS.  Makes the GLM http transport work even when the
    brain was started by an external workflow that did not source the env
    file (EVO R12 follow-up: externally-restarted brains had no FLY64_LLM_*)."""
    try:
        if not LLM_ENV_FILE.exists():
            return
        for line in LLM_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass


_load_llm_env()

PROMPT_TEMPLATE = (
    "你是 SM64 果蝇脑控制系统的教练。分析当前游戏截屏和状态，回答：\n"
    "0. **特别注意屏幕上的文字**：读出所有可见的英文/中文文字"
    "（对话框内容、UI 标签、金币数 ×××、生命值、星星数、菜单项等），"
    "逐条列在 what_i_see 字段中——这是验证你确实在看屏幕的依据。\n"
    "1. 场景中有什么元素（门/坡/敌人/金币/平台/水体）？\n"
    "2. 马里奥当前面临什么障碍或问题？\n"
    "3. 根据屏幕看到的 + 下方状态数据，给出建议的下一步行动"
    "（转向方向、速度、是否跳跃、目标位置）？\n"
    "只回复一个 JSON 对象，格式:\n"
    '{"scene_elements": ["..."], "what_i_see": ["屏幕文字1", "屏幕文字2"], '
    '"problem": "...", "action": "...", '
    '"advice": "给马里奥的一句中文建议", '
    '"strategy": {"fallen_recovery": {"mode": "mirror|directional_climb", '
    '"climb_period": 2.0, "persist_seconds": 2.0}, '
    '"exploration": {"bold_explore_stuck_s": 60.0, "turn_bias": 0}, '
    '"escape": {"stuck_threshold_s": 30.0, "reverse_seconds": 0.5}, '
    '"command": {"type": "turn_and_go", "heading": 90, "duration_s": 2.0, '
    '"y": 70, "primitive": null}}}\n'
    '策略参数语义卡（严格遵守单位与方向，不要反向调参）:\n'
    '- exploration.bold_explore_stuck_s: 秒。异常持续该秒数后触发突围，'
    '越小越快突围（建议 20-120）。\n'
    '- exploration.turn_bias: 0-1 转向强度（占最大转向电流的比例），'
    '越大转向越猛（建议 0.3-1.0；不要填 69 这类角度值）。\n'
    '- escape.stuck_threshold_s: 秒。持续卡住该秒数后强制逃逸，'
    '越小越快逃逸（建议 1-60）。\n'
)

# Keys allowed per strategy section (name -> (type, default))
SECTION_SPECS = {
    "fallen_recovery": {
        "mode": (str, "mirror"),
        "climb_period": (float, 2.0),
        "persist_seconds": (float, 2.0),
    },
    "exploration": {
        "bold_explore_stuck_s": (float, 60.0),
        "turn_bias": (float, 0.0),
    },
    "escape": {
        "stuck_threshold_s": (float, 30.0),
        "reverse_seconds": (float, 0.5),
    },
}


class ConsultError(RuntimeError):
    """Raised when a consultation cannot be completed."""


def build_consult_request(context: dict, frame_b64: Optional[str],
                          prompt: str = PROMPT_TEMPLATE) -> dict:
    """Build the multimodal consult request payload."""
    req = {
        "model": os.environ.get("FLY64_LLM_MODEL", DEFAULT_MODEL),
        "prompt": prompt,
        "context": context,
        "ts": round(time.time(), 2),
    }
    if frame_b64:
        # t13 fix④: the brain runner hands us RAW RGB bytes (base64 of the
        # shared-memory frame), not a PNG.  Labeling raw bytes as
        # image/png made the GLM API reject the request with HTTP 400.
        png_b64 = raw_rgb_b64_to_png_b64(frame_b64)
        req["frame_b64"] = png_b64
        req["image"] = "data:image/png;base64," + png_b64
    return req


def raw_rgb_b64_to_png_b64(frame_b64: str,
                           width: int = 384, height: int = 256) -> str:
    """Convert base64(raw RGB bytes, HxWx3 row-major) to base64(PNG).

    Pure stdlib (zlib + struct) so the plugin needs no imaging dependency.
    If the payload is not exactly WxHx3 raw bytes it is returned unchanged —
    it is then assumed to already be an encoded image.
    """
    import struct
    import zlib
    try:
        raw = base64.b64decode(frame_b64, validate=True)
    except Exception:
        return frame_b64
    if len(raw) != width * height * 3:
        return frame_b64  # not raw RGB — assume already-encoded image

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    stride = width * 3
    rows = b"".join(b"\x00" + raw[y * stride:(y + 1) * stride]
                    for y in range(height))
    idat = zlib.compress(rows, 6)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def frame_to_data_uri(frame_b64: Optional[str]) -> Optional[str]:
    if not frame_b64:
        return None
    if frame_b64.startswith("data:"):
        return frame_b64
    # Detect dimensions from raw RGB data length:
    #   320×240×3 = 230400 B → 307200 base64 chars (screen.json)
    #   384×256×3 = 294912 B → 393216 base64 chars (help.json frame_b64)
    try:
        raw_len = len(base64.b64decode(frame_b64, validate=True))
    except Exception:
        return "data:image/png;base64," + frame_b64
    if raw_len == 230400:
        w, h = 320, 240
    elif raw_len == 294912:
        w, h = 384, 256
    elif raw_len == 49152:
        w, h = 128, 128  # forward face of cubemap
    else:
        return "data:image/png;base64," + frame_b64  # assume already encoded
    png_b64 = raw_rgb_b64_to_png_b64(frame_b64, w, h)
    return "data:image/png;base64," + png_b64


class GLMConsultant:
    """Consult GLM-5.3-flash with the game frame + context snapshot."""

    def __init__(self, transport: Optional[str] = None,
                 base_url: Optional[str] = None, api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 request_path: Path = REQUEST_PATH,
                 response_path: Path = RESPONSE_PATH,
                 subagent_fn: Optional[Callable[[dict], str]] = None,
                 timeout: float = SUBAGENT_TIMEOUT_SECONDS):
        env_transport = os.environ.get("FLY64_LLM_TRANSPORT", "").strip()
        self.transport = transport or env_transport or DEFAULT_TRANSPORT
        if self.transport not in ("subagent", "http"):
            raise ValueError(f"unknown transport: {self.transport!r}")
        self.base_url = base_url or os.environ.get("FLY64_LLM_BASE_URL", "")
        self.api_key = api_key or os.environ.get("FLY64_LLM_API_KEY", "")
        self.model = model or os.environ.get("FLY64_LLM_MODEL", DEFAULT_MODEL)
        self.request_path = Path(request_path)
        self.response_path = Path(response_path)
        self.subagent_fn = subagent_fn
        self.timeout = timeout
        self.last_request: Optional[dict] = None
        self.last_raw_response: Optional[str] = None

    # ── public API ────────────────────────────────────────────────────
    def consult(self, context: dict, frame_b64: Optional[str] = None) -> dict:
        """Run one consultation; returns the parsed strategy dict.

        The returned dict always contains ``advice`` (str) and, when the
        model produced one, a ``strategy`` section dict.
        """
        request = build_consult_request(context, frame_b64)
        request["model"] = self.model
        self.last_request = request
        self.request_path.parent.mkdir(parents=True, exist_ok=True)
        self.request_path.write_text(
            json.dumps(request, ensure_ascii=False), encoding="utf-8")
        raw = self._dispatch(request)
        self.last_raw_response = raw
        parsed = parse_response(raw)
        # t21: explicit screen-text readout — embed into the advice so the
        # operator sees "what the coach actually read from the screen" in
        # the dashboard coach panel and in coach_advice.json history.
        if parsed.get("what_i_see"):
            parsed["advice"] = (str(parsed.get("advice", "")).rstrip()
                                + "\n👁 屏幕: " + "；".join(parsed["what_i_see"]))
        parsed.setdefault("advice", "")
        if isinstance(parsed.get("strategy"), dict):
            parsed["strategy"] = sanitize_strategy(parsed["strategy"])
            # t21: ride the readout into active_strategy.json (the runner
            # writes strategy=parsed["strategy"] unchanged).
            if parsed.get("what_i_see"):
                parsed["strategy"]["what_i_see"] = list(parsed["what_i_see"])
        return parsed

    # ── dialogue decision API ─────────────────────────────────────────
    def consult_dialogue(self, frame_b64: Optional[str],
                         context: Optional[dict] = None,
                         timeout: Optional[float] = None) -> dict:
        """Ask the LLM how to handle an on-screen dialogue box.

        Sends the current game frame with the dialogue prompt and returns
        ``{"action": "press_a"|"press_b"|"none", "reason": str}``.  Raises
        :class:`ConsultError` when no reply arrives in time.  The caller
        (brain dialogue pause-wait mode) owns the overall wait budget and
        passes it via ``timeout``.
        """
        saved_timeout = self.timeout
        if timeout is not None:
            self.timeout = float(timeout)
        try:
            request = build_consult_request(context or {}, frame_b64,
                                            prompt=DIALOGUE_PROMPT_TEMPLATE)
            request["model"] = self.model
            request["kind"] = "dialogue_decision"
            self.last_request = request
            self.request_path.parent.mkdir(parents=True, exist_ok=True)
            self.request_path.write_text(
                json.dumps(request, ensure_ascii=False), encoding="utf-8")
            raw = self._dispatch(request)
            self.last_raw_response = raw
            return parse_dialogue_response(raw)
        finally:
            self.timeout = saved_timeout

    # ── transports ────────────────────────────────────────────────────
    def _dispatch(self, request: dict) -> str:
        if self.transport == "subagent":
            return self._dispatch_subagent(request)
        return self._dispatch_http(request)

    def _dispatch_subagent(self, request: dict) -> str:
        """Hand the request to the DSH host agent (GLM-5.3-flash)."""
        if self.subagent_fn is not None:
            return str(self.subagent_fn(request))
        # File-based exchange with the DSH agent.
        self.response_path.unlink(missing_ok=True)
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self.response_path.exists():
                try:
                    text = self.response_path.read_text(encoding="utf-8")
                    if text.strip():
                        return text
                except OSError:
                    pass
            time.sleep(1.0)
        raise ConsultError(
            f"subagent response not produced within {self.timeout:.0f}s "
            f"(request at {self.request_path})")

    def _dispatch_http(self, request: dict) -> str:
        """Direct OpenAI-compatible multimodal chat completion."""
        if not self.base_url:
            raise ConsultError("http transport requires FLY64_LLM_BASE_URL")
        content: list[dict] = [{"type": "text", "text": request["prompt"]}]
        ctx = json.dumps(request.get("context", {}), ensure_ascii=False)
        content.append({"type": "text", "text": "状态上下文: " + ctx})
        uri = frame_to_data_uri(request.get("frame_b64"))
        if uri:
            content.append({"type": "image_url", "image_url": {"url": uri}})
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            # t13 fix④: surface the API error body — the bare "HTTP Error
            # 400" hid the raw-RGB-labelled-as-PNG root cause for a round.
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            raise ConsultError(
                f"GLM API HTTP {exc.code}: {body}") from exc
        return data["choices"][0]["message"]["content"]


# ── response parsing ─────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_text(raw: str) -> Optional[str]:
    """Extract the outermost JSON object from a raw LLM reply."""
    if not raw:
        return None
    text = raw.strip()
    # Prefer fenced code blocks when present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    for cand in filter(None, (candidate, text)):
        try:
            json.loads(cand)
            return cand
        except ValueError:
            continue
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            json.loads(m.group(0))
            return m.group(0)
        except ValueError:
            pass
    return None


def sanitize_strategy(strategy: dict) -> dict:
    """Clamp the LLM's strategy to the known sections and safe values.

    Mirrors the brain model's own defensive parsing (``load_active_strategy``):
    unknown keys are dropped, bad numbers fall back to defaults, and
    ``mode`` must be one of the supported recovery modes.
    """
    clean: dict = {}
    for section, spec in SECTION_SPECS.items():
        raw_section = strategy.get(section)
        if not isinstance(raw_section, dict):
            continue
        out: dict = {}
        for key, (typ, default) in spec.items():
            val = raw_section.get(key, default)
            try:
                if typ is float:
                    out[key] = max(0.1, float(val))
                else:
                    out[key] = typ(val)
            except (TypeError, ValueError):
                out[key] = default
        if section == "fallen_recovery" and out.get("mode") not in (
                "mirror", "directional_climb"):
            out["mode"] = "mirror"
        clean[section] = out
    # t21: preserve the explicit screen-text readout so it reaches
    # active_strategy.json through the runner's strategy write.
    wise = normalize_what_i_see(strategy.get("what_i_see"))
    if wise:
        clean["what_i_see"] = wise
    # M2.1: primitives section — enabled list & scene→prefer map.
    raw_prim = strategy.get("primitives")
    if isinstance(raw_prim, dict):
        clean_p = {}
        enabled = raw_prim.get("enabled")
        if isinstance(enabled, list):
            valid = [str(p) for p in enabled if isinstance(p, str)
                     and p in ("longjump","backflip","groundpound","punch","dive")]
            if valid:
                clean_p["enabled"] = valid
        prefer = raw_prim.get("prefer")
        if isinstance(prefer, dict):
            p = {str(k): str(v) for k,v in prefer.items()
                 if isinstance(k,str) and isinstance(v,str) and k}
            if p:
                clean_p["prefer"] = p
        if clean_p:
            clean["primitives"] = clean_p
    # Command section — one-shot behavioral directive.
    cmd = strategy.get("command")
    if isinstance(cmd, dict) and cmd.get("type") in ("turn_and_go",):
        out = {"type": cmd["type"]}
        if "heading" in cmd and isinstance(cmd["heading"], (int, float)):
            out["heading"] = int(cmd["heading"]) % 360
        if "duration_s" in cmd:
            out["duration_s"] = max(0.5, min(10.0, float(cmd.get("duration_s", 2.0))))
        if "y" in cmd:
            out["y"] = max(0, min(127, int(cmd.get("y", 70))))
        if cmd.get("primitive") in ("longjump","backflip","groundpound","punch","dive"):
            out["primitive"] = cmd["primitive"]
        clean["command"] = out
    return clean


def normalize_what_i_see(value) -> list:
    """Normalise the what_i_see field to a list of non-empty strings.

    Accepts a list (any items), a single string, or anything else; missing
    or malformed input degrades to [] without raising (t21 contract).
    """
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


def parse_dialogue_response(raw: str) -> dict:
    """Parse a GLM dialogue reply into ``{action, reason}``.

    ``action`` is always one of ``press_a`` / ``press_b`` / ``none`` —
    unknown, missing, or malformed actions degrade to ``none`` (hold).
    """
    reason = ""
    action = "none"
    text = extract_json_text(raw)
    if text is not None:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                reason = str(data.get("reason", "") or "")
                action = str(data.get("action", "none") or "none").strip().lower()
        except ValueError:
            pass
    if action not in DIALOGUE_ACTIONS:
        action = "none"
    if not reason:
        reason = (raw or "").strip()[:200]
    return {"action": action, "reason": reason}


def parse_response(raw: str) -> dict:
    """Parse a GLM reply into ``{advice, what_i_see?, strategy?, ...}``.

    t21: the explicit screen-text readout ``what_i_see`` is normalised to a
    list of non-empty strings and always present (missing/malformed → [])
    so downstream consumers never crash on it.
    """
    text = extract_json_text(raw)
    if text is None:
        # Free-form advice is still useful — keep it as the advice text.
        return {"advice": (raw or "").strip(), "what_i_see": []}
    data = json.loads(text)
    if not isinstance(data, dict):
        return {"advice": str(data), "what_i_see": []}
    out = dict(data)
    advice = out.get("advice") or out.get("action") or ""
    out["advice"] = str(advice)
    out["what_i_see"] = normalize_what_i_see(out.get("what_i_see"))
    return out


# ── module-level convenience ─────────────────────────────────────────────

_default_consultant: Optional[GLMConsultant] = None


def consult_dialogue(frame_b64: Optional[str],
                     timeout: float = DEFAULT_DIALOGUE_TIMEOUT) -> dict:
    """One-shot dialogue decision via the shared default consultant.

    Returns ``{"action": "press_a"|"press_b"|"none", "reason": str}``;
    raises :class:`ConsultError` on timeout/transport failure.
    """
    global _default_consultant
    if _default_consultant is None:
        _default_consultant = GLMConsultant()
    return _default_consultant.consult_dialogue(frame_b64, timeout=timeout)
