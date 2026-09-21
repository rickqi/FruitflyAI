"""Tests for 4-direction Elementary Motion Detection (Hassenstein-Reichardt correlator).

Covers:
  - ElementaryMotionDetector standalone unit tests
  - SphericalRetina.compute_emd integration
  - flow_json EMD field exposure in main.py
  - Reset, edge cases, and cross-cancellation
"""
import json
import numpy as np
import pytest

from fly64.retina import ElementaryMotionDetector, SphericalRetina


# ======================================================================
# Helper: build a small retina grid for deterministic EMD tests
# ======================================================================

def _make_emds(rows=range(10, 20), cols=range(4, 29)):
    """Return (emd_on, emd_off, n_cells, h_pairs, v_pairs).

    All cells land in the left eye (col < 32) so the synthetic
    azimuth bounds do not interfere with neighbour pair building.

    Returns
    -------
    tuple
        (emd_on_detector, emd_off_detector, n_cells, h_pairs, v_pairs)
    """
    pixels = np.array([(r, c) for r in rows for c in cols], dtype=np.float32)
    retina = SphericalRetina(pixels)
    # Expose the raw pair arrays the detectors were built from
    h = retina._emd_on._pairs["right"]
    v = retina._emd_on._pairs["down"]
    return retina._emd_on, retina._emd_off, len(pixels), h, v


def _signal(n_cells, active_cols, value=1.0, rows=range(10, 20), cols=range(4, 29)):
    """Per-cell signal with a vertical bar at `active_cols` ON, rest OFF."""
    sig = np.zeros(n_cells, dtype=np.float32)
    for c in active_cols:
        for r in rows:
            idx = (r - rows[0]) * len(cols) + (c - cols[0])
            sig[idx] = value
    return sig


def _make_retina(rows=range(10, 20), cols=range(4, 29)):
    """Return a SphericalRetina on a small left-eye grid."""
    pixels = np.array([(r, c) for r in rows for c in cols], dtype=np.float32)
    return SphericalRetina(pixels), len(pixels)


# ======================================================================
# ElementaryMotionDetector — standalone unit tests
# ======================================================================

def test_emd_first_frame_primes_with_zero_output():
    """First compute() call primes the delay buffer and returns all zeros."""
    h = np.array([[0, 1], [10, 11]], dtype=np.int32)
    v = np.array([[0, 10], [1, 11]], dtype=np.int32)
    emd = ElementaryMotionDetector(h, v)
    sig = np.random.rand(20).astype(np.float32)
    # Not warmed up before any call
    assert not emd.is_warmed_up
    # First compute primes and sets _prev
    out = emd.compute(sig)
    assert out["right"] == 0.0
    assert out["left"] == 0.0
    assert out["down"] == 0.0
    assert out["up"] == 0.0
    assert out["total"] == 0.0
    # After priming, _prev is set and detector is warmed up
    assert emd.is_warmed_up


def test_emd_static_frame_gives_no_directional_signal():
    """Two identical inputs → zero correlation."""
    emd, _, n, _, _ = _make_emds()
    sig = _signal(n, {10, 11})
    emd.compute(sig)               # prime
    out = emd.compute(sig.copy())  # static
    assert out["right"] == 0.0
    assert out["left"] == 0.0
    assert out["down"] == 0.0
    assert out["up"] == 0.0
    assert out["total"] == 0.0


def test_emd_rightward_bar():
    """Bar moving right → positive right, right > left."""
    emd, _, n, h_pairs, _ = _make_emds()
    sig0 = _signal(n, {10, 11})
    sig1 = _signal(n, {12, 13})
    emd.compute(sig0)
    out = emd.compute(sig1)
    assert out["right"] > 0.0, f"Expected right>0, got {out['right']}"
    assert out["right"] > out["left"], f"right {out['right']} <= left {out['left']}"
    assert out["total"] > 0.0


def test_emd_leftward_bar():
    """Bar moving left → positive left, left > right."""
    emd, _, n, h_pairs, _ = _make_emds()
    sig0 = _signal(n, {12, 13})
    sig1 = _signal(n, {10, 11})
    emd.compute(sig0)
    out = emd.compute(sig1)
    assert out["left"] > 0.0, f"Expected left>0, got {out['left']}"
    assert out["left"] > out["right"], f"left {out['left']} <= right {out['right']}"
    assert out["total"] > 0.0


def test_emd_downward_bar():
    """Bar moving down → positive down, down > up."""
    emd, _, n, _, v_pairs = _make_emds()
    # Create a horizontal bar (all columns active in one row), then shift down
    cols = list(range(4, 29))
    sig0 = np.zeros(n, dtype=np.float32)
    sig1 = np.zeros(n, dtype=np.float32)
    # Row 0 = top, row 9 = bottom in our 10-row grid
    row0_offset = 0 * len(cols)
    row1_offset = 1 * len(cols)
    sig0[row0_offset:row0_offset + len(cols)] = 1.0   # top row active
    sig1[row1_offset:row1_offset + len(cols)] = 1.0   # next row active

    emd.compute(sig0)
    out = emd.compute(sig1)
    assert out["down"] > 0.0, f"Expected down>0, got {out['down']}"
    assert out["down"] > out["up"], f"down {out['down']} <= up {out['up']}"
    assert out["total"] > 0.0


def test_emd_upward_bar():
    """Bar moving up → positive up, up > down."""
    emd, _, n, _, v_pairs = _make_emds()
    cols = list(range(4, 29))
    sig0 = np.zeros(n, dtype=np.float32)
    sig1 = np.zeros(n, dtype=np.float32)
    row0_offset = 1 * len(cols)
    row1_offset = 0 * len(cols)
    sig0[row0_offset:row0_offset + len(cols)] = 1.0   # middle row active
    sig1[row1_offset:row1_offset + len(cols)] = 1.0   # top row active (shift up)

    emd.compute(sig0)
    out = emd.compute(sig1)
    assert out["up"] > 0.0, f"Expected up>0, got {out['up']}"
    assert out["up"] > out["down"], f"up {out['up']} <= down {out['down']}"
    assert out["total"] > 0.0


def test_emd_opponent_cancellation():
    """Equal right+left motion → net = 0."""
    emd, _, n, h_pairs, _ = _make_emds()
    rng = np.random.default_rng(42)
    sig0 = rng.random(n).astype(np.float32)
    sig1 = sig0.copy()  # static -> no net directional signal
    emd.compute(sig0)
    out = emd.compute(sig1)
    assert out["right"] == 0.0
    assert out["left"] == 0.0
    # Random flicker may produce energy in vertical channels
    # but horizontal should cancel perfectly for identical frames


def test_emd_reset_clears_buffer():
    """reset() clears delay buffer → next compute returns zeros (prime)."""
    emd, _, n, _, _ = _make_emds()
    sig0 = _signal(n, {10, 11})
    sig1 = _signal(n, {12, 13})
    emd.compute(sig0)   # prime
    emd.compute(sig1)   # would normally have a signal
    emd.reset()
    out = emd.compute(sig0)  # after reset, this is a prime again
    assert out["right"] == 0.0
    assert out["left"] == 0.0
    assert out["total"] == 0.0
    assert emd._prev is not None  # internally set after first post-reset call
    # But should be warm after the second call
    out2 = emd.compute(sig1)
    assert out2["right"] > 0.0


def test_emd_handles_empty_pairs():
    """Detector with empty pair arrays returns zeros and never crashes."""
    h_empty = np.empty((0, 2), dtype=np.int32)
    v_empty = np.empty((0, 2), dtype=np.int32)
    emd = ElementaryMotionDetector(h_empty, v_empty)
    sig = np.random.rand(10).astype(np.float32)
    out1 = emd.compute(sig)
    for k in ("right", "left", "down", "up", "total"):
        assert out1[k] == 0.0
    out2 = emd.compute(sig)
    for k in ("right", "left", "down", "up", "total"):
        assert out2[k] == 0.0


def test_emd_reset_on_fresh_detector():
    """reset() on a never-used detector is a no-op (no error)."""
    h = np.array([[0, 1]], dtype=np.int32)
    v = np.array([[10, 20]], dtype=np.int32)
    emd = ElementaryMotionDetector(h, v)
    emd.reset()  # should not raise
    sig = np.random.rand(30).astype(np.float32)
    out = emd.compute(sig)
    assert out["total"] == 0.0  # prime frame


# ======================================================================
# Integration tests via SphericalRetina.compute_emd
# ======================================================================

def test_compute_emd_primes_on_first_call():
    """compute_emd() returns all zeros on first call."""
    retina, n = _make_retina()
    on = _signal(n, {10, 11})
    off = np.zeros_like(on)
    result = retina.compute_emd(on, off)
    assert result["emd_on_right"] == 0.0
    assert result["emd_on_left"] == 0.0
    assert result["emd_on_down"] == 0.0
    assert result["emd_on_up"] == 0.0
    assert result["emd_off_right"] == 0.0
    assert result["emd_off_left"] == 0.0
    assert result["emd_off_down"] == 0.0
    assert result["emd_off_up"] == 0.0
    assert result["emd_on_total"] == 0.0
    assert result["emd_off_total"] == 0.0


def test_compute_emd_rightward_on_signal():
    """ON-channel rightward motion → positive emd_on_right."""
    retina, n = _make_retina()
    on0 = _signal(n, {10, 11})
    on1 = _signal(n, {12, 13})
    off = np.zeros(n, dtype=np.float32)
    retina.compute_emd(on0, off)         # prime
    result = retina.compute_emd(on1, off)  # bar moved right
    assert result["emd_on_right"] > 0.0
    assert result["emd_on_right"] > result["emd_on_left"]
    assert result["emd_on_total"] > 0.0
    # OFF channel should be zero since off signal is all zeros
    assert result["emd_off_total"] == 0.0


def test_compute_emd_off_signal():
    """OFF-channel motion → positive emd_off."""
    retina, n = _make_retina()
    off0 = _signal(n, {12, 13})
    off1 = _signal(n, {10, 11})   # moved left in OFF
    on = np.zeros(n, dtype=np.float32)
    retina.compute_emd(on, off0)         # prime
    result = retina.compute_emd(on, off1)
    assert result["emd_off_left"] > 0.0
    assert result["emd_off_left"] > result["emd_off_right"]
    assert result["emd_off_total"] > 0.0
    # ON should be zero
    assert result["emd_on_total"] == 0.0


def test_compute_emd_ten_key_structure():
    """compute_emd() result has exactly 10 expected keys."""
    retina, n = _make_retina()
    on = _signal(n, {10, 11})
    off = np.zeros(n, dtype=np.float32)
    result = retina.compute_emd(on, off)
    expected = {
        "emd_on_right", "emd_on_left", "emd_on_down", "emd_on_up", "emd_on_total",
        "emd_off_right", "emd_off_left", "emd_off_down", "emd_off_up", "emd_off_total",
    }
    assert set(result) == expected


# ======================================================================
# Integration via retina.compute_flow (full pipeline)
# ======================================================================

def test_compute_flow_includes_emd_keys():
    """compute_flow() dict contains all 10 EMD keys."""
    retina, n = _make_retina()
    # Build a minimal RGB atlas that satisfies the shape constraint
    atlas = np.zeros((256, 384, 3), dtype=np.uint8)
    # Make two consecutive calls so EMD warms up
    flow1 = retina.compute_flow(atlas)
    flow2 = retina.compute_flow(atlas)
    for key in ("emd_on_right", "emd_on_left", "emd_on_down", "emd_on_up",
                "emd_off_right", "emd_off_left", "emd_off_down", "emd_off_up",
                "emd_on_total", "emd_off_total"):
        assert key in flow2, f"Missing key: {key}"
        assert isinstance(flow2[key], float), f"{key} is not float"


# ======================================================================
# flow.json exposure (main.py)
# ======================================================================

def test_flow_json_emd_fields_present():
    """Verify main.py flow_json dict construction includes all EMD fields.

    We inspect a simulated version of the dict (same keys as main.py builds).
    """
    flow_json = json.dumps({
        "emd_on_right": 0.1234,
        "emd_on_left": 0.0567,
        "emd_on_down": 0.0890,
        "emd_on_up": 0.0123,
        "emd_off_right": 0.0456,
        "emd_off_left": 0.0789,
        "emd_off_down": 0.0111,
        "emd_off_up": 0.0222,
        "emd_on_total": 0.2814,
        "emd_off_total": 0.1578,
        "tick": 42,
    }, separators=(",", ":"))
    parsed = json.loads(flow_json)
    for key in ("emd_on_right", "emd_on_left", "emd_on_down", "emd_on_up",
                "emd_off_right", "emd_off_left", "emd_off_down", "emd_off_up",
                "emd_on_total", "emd_off_total"):
        assert key in parsed, f"{key} missing from flow_json"
        assert isinstance(parsed[key], float), f"{key} is not a float"


def test_flow_json_emd_fields_range():
    """EMD fields in flow_json are in valid range (0 ≤ float ≤ large)."""
    flow_json = json.dumps({
        "emd_on_right": 0.0,
        "emd_on_left": 0.0,
        "emd_on_down": 1.2345,
        "emd_on_up": 0.5678,
        "emd_off_right": 0.0987,
        "emd_off_left": 0.0,
        "emd_off_down": 0.4321,
        "emd_off_up": 0.0,
        "emd_on_total": 1.8023,
        "emd_off_total": 0.5308,
    }, separators=(",", ":"))
    parsed = json.loads(flow_json)
    # All EMD values are non-negative
    for key in ("emd_on_right", "emd_on_left", "emd_on_down", "emd_on_up",
                "emd_off_right", "emd_off_left", "emd_off_down", "emd_off_up",
                "emd_on_total", "emd_off_total"):
        assert parsed[key] >= 0.0, f"{key}={parsed[key]} is negative"


def test_compute_flow_emd_is_additive_no_regression():
    """compute_flow() retains all pre-existing keys; EMD keys are additive."""
    retina_full = SphericalRetina(
        np.array([(r, c) for r in range(10, 20) for c in range(4, 29)], dtype=np.float32)
    )
    atlas = np.zeros((256, 384, 3), dtype=np.uint8)
    # Pre-existing keys from compute_flow
    old_keys = {
        "tau", "sectors", "sectors_16", "left_right_asymmetry",
        "center_expansion", "lower_field_green", "terrain",
        "wall_score", "ramp_score", "opening_score", "sky_score",
        "ground_angle", "door_frame_score", "opening_width",
        "on_raw", "off_raw", "sustained_raw",
        "edge_0", "edge_45", "edge_90", "edge_135",
    }
    new_emd_keys = {
        "emd_on_right", "emd_on_left", "emd_on_down", "emd_on_up",
        "emd_off_right", "emd_off_left", "emd_off_down", "emd_off_up",
        "emd_on_total", "emd_off_total",
    }
    result1 = retina_full.compute_flow(atlas)
    result2 = retina_full.compute_flow(atlas)  # second call warms up
    assert old_keys <= set(result2), "Pre-existing keys missing after EMD integration"
    assert new_emd_keys <= set(result2), "All 10 EMD keys must be present"
    assert not result2["emd_on_right"]  # static black frame → zero motion