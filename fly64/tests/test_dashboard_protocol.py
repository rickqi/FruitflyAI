import json

import numpy as np
import pytest

from fly64.model import FlyModel
from fly64.telemetry import HEADER, Observatory

GAME = dict(x=0, y=0, jump=False, state=4, age_ms=300.)


def unpack(packet):
    magic, size = HEADER.unpack_from(packet)
    assert magic == b"F643"
    return json.loads(packet[8:8+size]), packet[8+size:]


def test_dashboard_packet_and_every_tick_timestamp():
    m = FlyModel(demo=True)
    obs = Observatory(m)
    frame = np.zeros((256, 384, 3), np.uint8)
    for _ in range(5):
        control, spikes = m.step(frame)
        obs.observe(frame, 1, control, spikes, GAME)
    meta, payload = unpack(obs.packet(3, rtf=1.))
    assert meta["schema"] == 3
    assert meta["seq"] == 3
    assert meta["rate_max"] == 50
    assert len(payload) == m.n + 2*256*128*3
    assert [r["t"] for r in meta["rows"]] == [0., .02, .04, .06, .08]
    assert obs.rows == []
    assert not meta["has_comparison"]


def test_observation_does_not_change_model_and_matches_decoder():
    original, instrumented = FlyModel(demo=True), FlyModel(demo=True)
    obs = Observatory(instrumented)
    rng = np.random.default_rng(33)
    expected = []
    for tick in range(60):
        frame = rng.integers(0, 256, (256, 384, 3), np.uint8)
        a, sa = original.step(frame)
        b, sb = instrumented.step(frame)
        row = obs.observe(frame, tick, b, sb, GAME)
        assert a == b
        np.testing.assert_array_equal(sa, sb)
        np.testing.assert_array_equal(original.v, instrumented.v)
        expected.append(instrumented.spikes.copy())
        np.testing.assert_array_equal(obs.counts, np.sum(expected[-13:], axis=0))
        assert row["forward"] == pytest.approx(b.forward_rate/.02, rel=1e-6)
        assert row["right"]-row["left"] == pytest.approx(b.turn_rate/.02, abs=1e-5)
        assert row["jump"] == pytest.approx(b.jump_rate/.02, rel=1e-6)
        assert row["jump_event"] == b.jump
        assert 0 <= row["cooldown"] <= .8


def test_change_is_between_new_frames_not_dashboard_ticks():
    m = FlyModel(demo=True)
    obs = Observatory(m)
    dark = np.zeros((256, 384, 3), np.uint8)
    bright = np.full_like(dark, 255)
    for frame, seq in [(dark, 1), (bright, 2)]:
        control, spikes = m.step(frame)
        obs.observe(frame, seq, control, spikes, GAME)
    assert obs.has_comparison
    assert obs.contrast == pytest.approx([1., 1.])
    saved = obs.change.copy()
    control, spikes = m.step(bright)
    obs.observe(bright, 2, control, spikes, GAME)
    np.testing.assert_array_equal(obs.change, saved)
    obs.observe(bright, 3, control, spikes, GAME)
    assert not obs.change.any()
    assert obs.contrast == [0., 0.]


def test_map_rate_quantization_has_fixed_scale():
    m = FlyModel(demo=True)
    obs = Observatory(m)
    frame = np.zeros((256, 384, 3), np.uint8)
    for i in range(15):
        control, _ = m.step(frame)
        obs.observe(frame, 1, control, np.array([0]), GAME)
    meta, payload = unpack(obs.packet(1))
    assert meta["window_ticks"] == 13
    assert payload[0] == 255
    assert payload[1:m.n] == bytes(m.n-1)


CAUSAL_SOURCES = {"steering", "jump", "escape", "anomaly_reflex", "cliff_reflex",
                  "collision", "dialogue"}
# Phase 2 motor expansion: CPG primitive cascade layer (priority 4.5)
CAUSAL_SOURCES |= {f"cpg_primitive:{p}" for p in (
    "longjump", "backflip", "groundpound", "punch", "dive", "swim", "crawl")}
# t25: LIF-competition-first — the network's own decision attribution
CAUSAL_SOURCES |= {"lf_steering", "lf_escape"}


def test_causal_fields_present_json_safe_and_degrade():
    m = FlyModel(demo=True)
    obs = Observatory(m)
    frame = np.zeros((256, 384, 3), np.uint8)
    # 1) No causal dict (legacy callers): fields degrade, never NaN/None crash.
    control, spikes = m.step(frame)
    row = obs.observe(frame, 1, control, spikes, GAME)
    assert row["decision_source"] == "steering"
    assert row["cliff_conf"] is None and row["stuck_conf"] is None
    assert row["cliff_confirmed"] is False
    assert row["gate_forward"] == (row["forward"] > .4)
    assert row["gate_jump"] == (row["jump"] > 2.)
    meta, _ = unpack(obs.packet(1))
    assert meta["causal_schema"] == 1
    json.dumps(meta, allow_nan=False)  # must stay JSON-safe
    # 2) With causal dict: values pass through, enum validated, still JSON-safe.
    for i in range(3):
        control, spikes = m.step(frame)
        obs.observe(frame, 2, control, spikes, GAME,
                    causal=dict(cliff_conf=.91, stuck_conf=.42,
                                cliff_confirmed=True, decision_source="cliff_reflex"))
    meta, _ = unpack(obs.packet(2))
    row = meta["rows"][-1]
    assert row["cliff_conf"] == .91 and row["stuck_conf"] == .42
    assert row["cliff_confirmed"] is True
    assert row["decision_source"] in CAUSAL_SOURCES
    json.dumps(meta, allow_nan=False)


# ── EVO R7: HRC motion-truth fields (additive protocol evolution) ──

def test_hrc_fields_present_and_json_safe():
    """Every WS row carries hrc_asymmetry; frame rows carry the LC4 sector
    looming population.  Additive: legacy fields unchanged, JSON-safe."""
    m = FlyModel(demo=True)
    obs = Observatory(m)
    rng = np.random.default_rng(7)
    for tick in range(4):
        frame = rng.integers(0, 256, (256, 384, 3), np.uint8)
        control, spikes = m.step(frame)
        row = obs.observe(frame, tick, control, spikes, GAME)
        assert "hrc_asymmetry" in row
        assert -1. <= row["hrc_asymmetry"] <= 1.
        assert "flow_asymmetry" in row  # legacy field preserved
    meta, _ = unpack(obs.packet(4))
    assert meta["schema"] == 3  # additive evolution: schema unchanged
    json.dumps(meta, allow_nan=False)
    frame_rows = [r for r in meta["rows"] if "sector_loom" in r]
    assert frame_rows, "at least one frame row must carry sector_loom"
    loom = frame_rows[-1]["sector_loom"]
    assert len(loom) == 32  # 16 azimuth sectors x upper/lower x L/R
    for k, v in loom.items():
        assert k.startswith("hrc_looming_az")
        assert v >= 0.


def test_hrc_self_motion_separation_matches_flow_formula():
    """true_hrc_asymmetry = clamp(hrc_asymmetry - 0.08*heading_rate), same
    separation formula as the flow true_asymmetry."""
    m = FlyModel(demo=True)
    rng = np.random.default_rng(11)
    for _ in range(3):
        frame = rng.integers(0, 256, (256, 384, 3), np.uint8)
        prev_heading = m.heading  # per-step rate, mirroring model.step
        m.step(frame, heading=float(rng.uniform(-1., 1.)))
    rate = (m.heading - prev_heading) / m.dt
    expected = max(-1., min(1., m.hrc_asymmetry - m.SELF_MOTION_K * rate))
    assert m.true_hrc_asymmetry == pytest.approx(expected, abs=1e-3)
    assert m.hrc_available  # warmed up after 3 frames
    cache = m.self_motion
    assert cache["true_hrc_asymmetry"] == pytest.approx(m.true_hrc_asymmetry)
    # Correlator not warmed up on a fresh model -> flow fallback semantics.
    m2 = FlyModel(demo=True)
    assert not m2.hrc_available
    assert m2.true_hrc_asymmetry == 0.
