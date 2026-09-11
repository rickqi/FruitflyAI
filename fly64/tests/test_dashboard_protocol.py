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
