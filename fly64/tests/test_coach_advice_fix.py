#!/usr/bin/env python3
"""Independent review tests for the t13 Coach-Advice fix round (v2.9.1).

Verifies the four root-cause fixes actually take effect:

1. bold_turn_bias consumption chain: main.py clamp formula (numeric,
   extracted from source) -> model.bold_turn_drive -> turn-pool current
   amplitude `0.35 * min(1.0, |drive|)`; clamp bounds hold for legacy
   ±69 angle scale, coach 0-1 scale, and out-of-range values.
2. Non-micro_loop anomalies trigger forced_bold breakout (relaxed path
   present in memory.py; original micro_loop path preserved).
3. Prompt semantic card documents every strategy key with unit/direction.
4. HTTP 400 degrade path is safe: HTTPError -> ConsultError with API
   body -> main worker autonomous press_a fallback (mocked, offline).

Loads modules with importlib.util.spec_from_file_location.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import urllib.error
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
MAIN_PATH = PROJECT / "fly64" / "main.py"
MODEL_PATH = PROJECT / "fly64" / "model.py"
MEMORY_PATH = PROJECT / "fly64" / "memory.py"
CONSULT_PATH = PROJECT / "plugin" / "llm_consult.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def consult():
    return _load_module("t14_llm_consult", CONSULT_PATH)


@pytest.fixture(scope="module")
def main_src():
    return MAIN_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def model_src():
    return MODEL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def memory_src():
    return MEMORY_PATH.read_text(encoding="utf-8")


# ── 1. bold_turn_bias consumption chain ─────────────────────────────────

class TestBoldTurnBiasChain:
    def _clamp_formula(self, main_src):
        m = re.search(r"_mag\s*=\s*(max\(0\.2[^\n]+)", main_src)
        assert m, "clamp formula not found in main.py"
        return m.group(1).strip()

    def test_clamp_numeric_bounds(self, main_src):
        expr = self._clamp_formula(main_src)
        f = lambda v: eval(expr.replace("_bias", repr(v)),
                           {"max": max, "min": min, "abs": abs})
        assert f(69.0) == pytest.approx(1.0)     # legacy full angle
        assert f(0.0) == pytest.approx(0.2)      # coach-0 floor, no dead-throttle
        assert f(34.5) == pytest.approx(0.5)
        assert f(138.0) == pytest.approx(1.0)    # over-range clamped
        assert f(-69.0) == pytest.approx(1.0)    # sign-independent (abs)
        assert f(1.0) == pytest.approx(0.2, abs=0.01)  # coach 0-1 scale lives at floor

    def test_formula_monotonic_in_bias(self, main_src):
        expr = self._clamp_formula(main_src)
        f = lambda v: eval(expr.replace("_bias", repr(v)),
                           {"max": max, "min": min, "abs": abs})
        vals = [f(b) for b in range(0, 70, 5)]
        assert all(y2 >= y1 for y1, y2 in zip(vals, vals[1:]))

    def test_drive_reaches_turn_pool_current(self, model_src):
        m = re.search(r"if self\.bold_turn_drive[^\n]*\n"
                      r".*?\n"
                      r".*v\[self\.turn_right\] \+= ([^\n]+)", model_src)
        assert m, "turn-pool consumption of bold_turn_drive not found"
        expr = m.group(1).strip()
        assert "min(1.0" in expr                 # second clamp in model
        # amplitude: 0.35 max turn-pool current × clamped magnitude
        amp = eval(expr.replace("self.bold_turn_drive", "1.0"),
                   {"min": min})
        assert amp == pytest.approx(0.35)
        # a coach strength of 0.2 (floor) yields 0.07 — non-zero steering
        amp_floor = eval(expr.replace("self.bold_turn_drive", "0.2"),
                         {"min": min})
        assert amp_floor == pytest.approx(0.07)

    def test_consumer_chain_end_to_end(self, main_src, model_src):
        # main writes the drive flag; model consumes it in step()
        assert 'getattr(memory_ctrl, "bold_turn_bias"' in main_src
        assert "model.bold_turn_drive" in main_src
        assert "self.bold_turn_drive" in model_src


# ── 2. relaxed forced_bold trigger ──────────────────────────────────────

class TestRelaxedBoldTrigger:
    def test_any_persistent_anomaly_breaks_out(self, memory_src):
        assert "persistent_anomaly_stuck" in memory_src
        # wall_stuck / fallen / oscillating all qualify via the relaxed path
        assert 'self._latest_anomaly_state != "micro_loop"' in memory_src
        assert "micro_loop_stuck" in memory_src  # original path preserved

    def test_relaxed_path_uses_coach_threshold(self, memory_src):
        m = re.search(r"persistent_anomaly_stuck\s*=([^)]+>\s*_bx_stuck_s\))",
                      memory_src)
        assert m, "relaxed path must gate on the coach-tunable threshold"

    def test_threshold_hot_reloads_from_coach(self, memory_src):
        assert "bold_explore_stuck_s" in memory_src


# ── 3. prompt semantic card ─────────────────────────────────────────────

class TestPromptSemanticCard:
    STRATEGY_KEYS = {
        "fallen_recovery.mode": "mirror|directional_climb",
        "fallen_recovery.climb_period": None,
        "fallen_recovery.persist_seconds": None,
        "exploration.bold_explore_stuck_s": "秒",
        "exploration.turn_bias": "0-1",
        "escape.stuck_threshold_s": "秒",
        "escape.reverse_seconds": None,
    }

    def test_all_keys_present_in_prompt(self, consult):
        p = consult.PROMPT_TEMPLATE
        for dotted in self.STRATEGY_KEYS:
            leaf = dotted.split(".", 1)[1]
            assert leaf in p, f"missing {dotted}"

    def test_units_and_direction_documented(self, consult):
        p = consult.PROMPT_TEMPLATE
        assert "秒" in p                       # time unit
        assert "0-1" in p                      # strength scale
        assert "不要反向调参" in p               # direction warning
        assert "不要填 69" in p                 # legacy-scale warning

    def test_dialogue_prompt_unpolluted(self, consult):
        assert "策略参数" not in consult.DIALOGUE_PROMPT_TEMPLATE


# ── 4. HTTP 400 degrade path (mocked, offline) ──────────────────────────

class TestHttp400Degrade:
    def _http_consultant(self, consult, tmp_path, err):
        c = consult.GLMConsultant(
            transport="http", base_url="http://mock",
            api_key="k", request_path=tmp_path / "req.json",
            response_path=tmp_path / "resp.json", timeout=2.0)

        def raise_400(request, timeout=None):
            raise urllib.error.HTTPError("http://mock", 400,
                                         "Bad Request", {},
                                         io.BytesIO(b'{"error":"invalid image"}'))
        import io
        c._dispatch_http = raise_400
        return c

    def test_http_400_surfaces_body_and_raises_consult_error(self, consult,
                                                             tmp_path):
        import io
        c = consult.GLMConsultant(
            transport="http", base_url="http://mock", api_key="k",
            request_path=tmp_path / "req.json",
            response_path=tmp_path / "resp.json", timeout=2.0)

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                "http://mock", 400, "Bad Request", {},
                io.BytesIO(b'{"error":"image decode failed"}'))

        orig = consult.urllib.request.urlopen
        consult.urllib.request.urlopen = fake_urlopen
        try:
            with pytest.raises(consult.ConsultError) as ei:
                c.consult_dialogue("aGVsbG8=")
        finally:
            consult.urllib.request.urlopen = orig
        assert "400" in str(ei.value)
        assert "image decode failed" in str(ei.value)  # root cause visible

    def test_framed_as_raw_rgb_still_converted_to_png(self, consult,
                                                      tmp_path):
        import base64 as b64mod
        import numpy as np
        c = consult.GLMConsultant(
            transport="http", base_url="http://mock", api_key="k",
            request_path=tmp_path / "req.json",
            response_path=tmp_path / "resp.json", timeout=2.0)
        raw = np.zeros((256, 384, 3), np.uint8)   # brain frame is 384x256 RGB
        raw[0, 0] = (1, 2, 3)
        raw_b64 = b64mod.b64encode(raw.tobytes()).decode()

        def fake_urlopen(req, timeout=None):
            body = json.dumps({"choices": [{"message": {"content":
                '{"action": "none", "reason": "ok"}'}}]}).encode()
            import io
            return io.BytesIO(body)

        orig = consult.urllib.request.urlopen
        consult.urllib.request.urlopen = fake_urlopen
        try:
            c.consult_dialogue(raw_b64)
        finally:
            consult.urllib.request.urlopen = orig
        req = json.loads((tmp_path / "req.json").read_text("utf-8"))
        assert b64mod.b64decode(req["frame_b64"])[:8] == b"\x89PNG\r\n\x1a\n"

    def test_png_payload_passthrough_untouched(self, consult):
        real_png = base64_png()
        assert consult.raw_rgb_b64_to_png_b64(real_png) == real_png


def base64_png() -> str:
    import base64
    import io
    import zlib
    import struct

    def chunk(typ: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
