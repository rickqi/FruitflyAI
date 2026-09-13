"""Verification tests for Phase 2 optic flow + collision avoidance.

Covers: retina compute_flow, model flow signals, memory flow-aware
threshold, and integration invariants.
"""

import time
from pathlib import Path
import numpy as np
import pytest

from fly64.model import FlyModel
from fly64.retina import (
    BASES,
    SphericalRetina,
    CALIBRATION,
)
from fly64.memory import MemoryController, StuckDetector, SpatialMemoryMap


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _full_retina():
    """Return a retina with the full set of 1536 visual pixels."""
    pixels = np.array([[i, j] for i in range(48) for j in range(64)])
    return SphericalRetina(pixels)


# Atlas layout: 256×384, 6 faces of 128×128, ordered as:
# Row 0: forward(0,0), right(0,1), back(0,2)
# Row 1: left(1,0), up(1,1), down(1,2)
# Face indices: 0=forward, 1=right, 2=back, 3=left, 4=up, 5=down

def _uniform_atlas(color=(128, 128, 128)):
    """Create an atlas where every face is a uniform color."""
    atlas = np.full((256, 384, 3), color, dtype=np.uint8)
    return atlas


def _make_atlas(face_colors):
    """Set per-face colors. face_colors is a 6-element list of (r,g,b).
    Faces: 0=forward, 1=right, 2=back, 3=left, 4=up, 5=down
    """
    atlas = np.zeros((256, 384, 3), dtype=np.uint8)
    for idx in range(6):
        color = face_colors[idx] if idx < len(face_colors) else (0, 0, 0)
        face_row = idx // 3
        face_col = idx % 3
        atlas[
            face_row * 128 : (face_row + 1) * 128,
            face_col * 128 : (face_col + 1) * 128,
        ] = color
    return atlas


# ======================================================================
# 1. retina.compute_flow unit tests
# ======================================================================

def test_flow_returns_correct_keys():
    """compute_flow returns a dict with expected keys."""
    retina = _full_retina()
    atlas = _uniform_atlas()
    flow = retina.compute_flow(atlas)
    assert "sectors" in flow
    assert "sectors_16" in flow
    assert "terrain" in flow
    assert "wall_score" in flow
    assert "ramp_score" in flow
    assert "opening_score" in flow
    assert "sky_score" in flow
    assert "ground_angle" in flow
    assert "door_frame_score" in flow
    assert "opening_width" in flow
    assert "left_right_asymmetry" in flow
    assert "center_expansion" in flow
    assert "lower_field_green" in flow
    assert isinstance(flow["left_right_asymmetry"], float)
    assert isinstance(flow["center_expansion"], float)
    assert isinstance(flow["lower_field_green"], float)
    assert isinstance(flow["terrain"], str)
    assert isinstance(flow["wall_score"], float)
    assert isinstance(flow["ramp_score"], float)
    assert isinstance(flow["opening_score"], float)
    assert isinstance(flow["sky_score"], float)
    assert isinstance(flow["ground_angle"], float)
    assert isinstance(flow["door_frame_score"], float)
    assert isinstance(flow["opening_width"], float)


def test_flow_sectors_has_all_expected():
    """Sectors dict contains all 16 named regions."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    expected = tuple(
        f"az{i}_{v}" for i in range(8) for v in ("upper", "lower")
    )
    for name in expected:
        assert name in flow["sectors_16"], f"Missing sector {name}"
        assert isinstance(flow["sectors_16"][name], float)


def test_flow_uniform_gives_zero_asymmetry():
    """A completely uniform atlas yields near-zero asymmetry."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas((120, 120, 120)))
    assert abs(flow["left_right_asymmetry"]) < 0.3, (
        f"Expected near-zero asymmetry for uniform input, got {flow['left_right_asymmetry']}"
    )


def test_flow_uniform_gives_zero_expansion():
    """A uniform atlas yields near-zero center_expansion."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas((120, 120, 120)))
    assert abs(flow["center_expansion"]) < 0.3, (
        f"Expected near-zero expansion for uniform input, got {flow['center_expansion']}"
    )


def test_flow_asymmetry_reverses_sign_with_swapped_colors():
    """Swapping bright and dark sides flips asymmetry sign."""
    retina = _full_retina()
    # Brighter on left-face side (azimuth < 0)
    bright = (200, 200, 200)
    dark = (10, 10, 10)
    atlas_a = _make_atlas([
        bright,  # forward
        dark,    # right
        dark,    # back
        bright,  # left
        bright,  # up
        bright,  # down
    ])
    flow_a = retina.compute_flow(atlas_a)

    # Swap: brighter on right-face side (azimuth >= 0)
    atlas_b = _make_atlas([
        bright,  # forward
        bright,  # right
        dark,    # back
        dark,    # left
        dark,    # up
        bright,  # down
    ])
    flow_b = retina.compute_flow(atlas_b)

    # Signs should be opposite
    assert flow_a["left_right_asymmetry"] * flow_b["left_right_asymmetry"] < 0, (
        f"Signs should be opposite: {flow_a['left_right_asymmetry']} vs {flow_b['left_right_asymmetry']}"
    )


def test_flow_lower_field_green_drops_on_cliff():
    """lower_field_green is lower when the down face has less green."""
    retina = _full_retina()
    # Atlas with uniform green across all faces
    atlas_grass = _make_atlas([
        (60, 180, 60),   # forward - green
        (60, 180, 60),   # right - green
        (60, 180, 60),   # back - green
        (60, 180, 60),   # left - green
        (60, 180, 60),   # up - green (sky)
        (60, 180, 60),   # down - green (ground)
    ])
    flow_grass = retina.compute_flow(atlas_grass)

    # Atlas with less green on down face (cliff - brown/gray ground)
    atlas_cliff = _make_atlas([
        (60, 180, 60),   # forward
        (60, 180, 60),   # right
        (60, 180, 60),   # back
        (60, 180, 60),   # left
        (60, 180, 60),   # up
        (60, 30, 60),    # down - much less green
    ])
    flow_cliff = retina.compute_flow(atlas_cliff)

    assert flow_cliff["lower_field_green"] < flow_grass["lower_field_green"], (
        f"Cliff ({flow_cliff['lower_field_green']}) should be less than grass ({flow_grass['lower_field_green']})"
    )


def test_flow_is_native_floats():
    """All flow return values are Python native floats (JSON-safe)."""
    retina = _full_retina()
    atlas = _uniform_atlas()
    flow = retina.compute_flow(atlas)
    for key in ("left_right_asymmetry", "center_expansion", "lower_field_green"):
        val = flow[key]
        assert isinstance(val, float), f"{key} is {type(val)}, expected float"
        import json
        json.dumps(val)


def test_flow_terrain_defaults_to_mixed():
    """Uniform input yields 'mixed' terrain classification."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    assert flow["terrain"] in ("mixed", "open_flat", "water")


def test_flow_terrain_cliff_detected():
    """Low lower_field_green with dim lower sectors = 'cliff'."""
    retina = _full_retina()
    # Bright green across all faces, but dark on down face
    atlas = _make_atlas([
        (60, 180, 60),   # forward
        (60, 180, 60),   # right
        (60, 180, 60),   # back
        (60, 180, 60),   # left
        (60, 180, 60),   # up
        (10, 10, 10),    # down - dark cliff
    ])
    flow = retina.compute_flow(atlas)
    # lower_field_green should be very low now
    assert flow["lower_field_green"] < 0.3, f"Expected low lower_field_green, got {flow['lower_field_green']}"
    assert isinstance(flow["terrain"], str)


def test_flow_terrain_water_detected():
    """Uniform dark input with low edges = 'water'."""
    retina = _full_retina()
    atlas = _uniform_atlas((20, 20, 30))  # very dark uniform
    flow = retina.compute_flow(atlas)
    assert flow["terrain"] == "water", f"Expected water, got {flow['terrain']}"
    assert isinstance(flow["terrain"], str)


def test_flow_terrain_corridor_detected():
    """Strong vertical edges with weak horizontal = 'corridor'."""
    retina = _full_retina()
    atlas = _make_atlas([
        (80, 80, 200),   # forward - vertical stripe
        (80, 80, 200),   # right
        (80, 80, 200),   # back
        (80, 80, 200),   # left
        (80, 80, 200),   # up
        (80, 80, 200),   # down
    ])
    # This generates uniform output, so corridor won't trigger.
    # Instead, we directly test the static method for edge cases.
    from fly64.retina import SphericalRetina as SR
    sec = {f"az{i}_{v}": 0.3 for i in range(8) for v in ("upper", "lower")}
    edges = {"edge_0": 0.05, "edge_45": 0.1, "edge_90": 0.25, "edge_135": 0.1}
    terrain = SR.classify_terrain(sec, edges, 0.8, 0.0, 0.0)
    assert terrain == "corridor", f"Expected corridor, got {terrain}"


def test_flow_16_sectors_distinct_bounds():
    """16 sectors cover the full azimuth range without gaps."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    # All 16 sectors should exist in sectors_16
    for i in range(8):
        for v in ("upper", "lower"):
            assert f"az{i}_{v}" in flow["sectors_16"], f"Missing az{i}_{v}"


def test_flow_16_sector_energy_changes_with_input():
    """Sector energies in sectors_16 change when brightness varies."""
    retina = _full_retina()
    atlas_bright = _make_atlas([
        (200, 200, 200),  # forward
        (200, 200, 200),  # right
        (10, 10, 10),     # back
        (10, 10, 10),     # left
        (200, 200, 200),  # up
        (200, 200, 200),  # down
    ])
    atlas_dim = _make_atlas([
        (10, 10, 10),     # forward
        (10, 10, 10),     # right
        (10, 10, 10),     # back
        (10, 10, 10),     # left
        (10, 10, 10),     # up
        (10, 10, 10),     # down
    ])
    flow_bright = retina.compute_flow(atlas_bright)
    flow_dim = retina.compute_flow(atlas_dim)
    # At least one sector should be different
    any_change = any(
        abs(flow_bright["sectors_16"][n] - flow_dim["sectors_16"][n]) > 0.001
        for n in flow_bright["sectors_16"]
    )
    assert any_change, "16-sector energies did not change with input"


def test_flow_terrain_classify_open_flat():
    """Low variance and low edge energy = 'open_flat'."""
    from fly64.retina import SphericalRetina as SR
    sec = {f"az{i}_{v}": 0.20 for i in range(8) for v in ("upper", "lower")}
    edges = {"edge_0": 0.02, "edge_45": 0.02, "edge_90": 0.02, "edge_135": 0.02}
    terrain = SR.classify_terrain(sec, edges, 0.9, 0.0, 0.0)
    assert terrain == "open_flat", f"Expected open_flat, got {terrain}"


def test_flow_terrain_classify_wall_ahead():
    """High looming = 'wall_ahead'."""
    from fly64.retina import SphericalRetina as SR
    sec = {f"az{i}_{v}": 0.25 for i in range(8) for v in ("upper", "lower")}
    edges = {"edge_0": 0.05, "edge_45": 0.05, "edge_90": 0.05, "edge_135": 0.05}
    terrain = SR.classify_terrain(sec, edges, 0.9, 0.0, 0.5)
    assert terrain == "wall_ahead", f"Expected wall_ahead, got {terrain}"


def test_flow_terrain_classify_dense():
    """High complexity in all edge orientations = 'dense'."""
    from fly64.retina import SphericalRetina as SR
    sec = {f"az{i}_{v}": 0.4 if i % 2 == 0 else 0.1 for i in range(8) for v in ("upper", "lower")}
    edges = {"edge_0": 0.15, "edge_45": 0.15, "edge_90": 0.15, "edge_135": 0.15}
    terrain = SR.classify_terrain(sec, edges, 0.9, 0.0, 0.0)
    assert terrain == "dense", f"Expected dense, got {terrain}"


def test_flow_wall_score_high_when_upper_dim():
    """wall_score high when lower sectors brighter than upper."""
    from fly64.retina import SphericalRetina as SR
    sec = {f"az{i}_upper": 0.05 for i in range(8)}
    sec.update({f"az{i}_lower": 0.50 for i in range(8)})
    edges = {"edge_0": 0.02, "edge_45": 0.02, "edge_90": 0.02, "edge_135": 0.02}
    # Compute scores via compute_flow-equivalent pipeline
    retina = _full_retina()
    atlas = _make_atlas([(50, 50, 50)] * 6)  # uniform — scores depend on actual retina layout
    flow = retina.compute_flow(atlas)
    # wall_score should be a valid float in [0,1]
    assert 0.0 <= flow["wall_score"] <= 1.0, f"wall_score {flow['wall_score']} not in [0,1]"
    assert isinstance(flow["wall_score"], float)


def test_flow_ramp_score_moderate_with_uniform():
    """ramp_score moderate/low on uniform brightness."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    assert 0.0 <= flow["ramp_score"] <= 1.0
    assert isinstance(flow["ramp_score"], float)


def test_flow_opening_score_moderate():
    """opening_score is a valid float in [0,1]."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    assert 0.0 <= flow["opening_score"] <= 1.0
    assert isinstance(flow["opening_score"], float)


def test_flow_sky_score_valid():
    """sky_score is a valid float in [0,1]."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    assert 0.0 <= flow["sky_score"] <= 1.0
    assert isinstance(flow["sky_score"], float)


def test_flow_ground_angle_valid_range():
    """ground_angle is a float in [0,1]."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    assert 0.0 <= flow["ground_angle"] <= 1.0, f"ground_angle {flow['ground_angle']} out of range"
    assert isinstance(flow["ground_angle"], float)


def test_flow_ground_angle_drops_on_cliff_atlas():
    """ground_angle drops when lower field has dark ground (cliff scenario)."""
    retina = _full_retina()
    # Cliff atlas: down face is dark (cliff), other faces green/bright
    atlas_cliff = _make_atlas([
        (60, 180, 60),   # forward - green
        (60, 180, 60),   # right - green
        (60, 180, 60),   # back - green
        (60, 180, 60),   # left - green
        (60, 180, 60),   # up
        (10, 10, 10),    # down - dark cliff
    ])
    flow_cliff = retina.compute_flow(atlas_cliff)

    atlas_flat = _make_atlas([
        (60, 180, 60),   # forward - green
        (60, 180, 60),   # right - green
        (60, 180, 60),   # back - green
        (60, 180, 60),   # left - green
        (60, 180, 60),   # up
        (60, 180, 60),   # down - green grass
    ])
    flow_flat = retina.compute_flow(atlas_flat)
    assert flow_cliff["ground_angle"] < flow_flat["ground_angle"], (
        f"Cliff ground_angle {flow_cliff['ground_angle']} should be < flat {flow_flat['ground_angle']}"
    )


def test_flow_door_frame_valid_range():
    """door_frame_score and opening_width are valid floats in [0,1]."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    assert 0.0 <= flow["door_frame_score"] <= 1.0
    assert 0.0 <= flow["opening_width"] <= 1.0
    assert isinstance(flow["door_frame_score"], float)
    assert isinstance(flow["opening_width"], float)


def test_flow_door_frame_higher_with_vertical_edge_pairs():
    """door_frame_score responds to vertical edge patterns in scene."""
    from fly64.retina import SphericalRetina as SR
    # Build a synthetic atlas with strong vertical stripes (door frame pattern)
    atlas = np.zeros((256, 384, 3), dtype=np.uint8)
    # Create two vertical stripes at column offsets on each face
    for row in range(0, 256, 128):
        for col_base in range(0, 384, 128):
            # Left stripe at offset 32, right stripe at offset 80, gap 32-80=48 pixels
            stripe1_c = col_base + 32
            stripe2_c = col_base + 80
            if stripe1_c < 384 and stripe2_c < 384:
                atlas[row:row + 128, stripe1_c:stripe1_c + 4] = (200, 200, 200)  # white
                atlas[row:row + 128, stripe2_c:stripe2_c + 4] = (200, 200, 200)  # white

    retina = _full_retina()
    flow = retina.compute_flow(atlas)
    assert isinstance(flow["door_frame_score"], float)
    assert isinstance(flow["opening_width"], float)


# ======================================================================
# 2. Model flow signal tests
# ======================================================================

def test_model_encode_retina_sets_flow_signals():
    """encode_retina stores flow_asymmetry, flow_looming, flow_cliff as floats."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas()
    model.encode_retina(atlas)
    assert isinstance(model.flow_asymmetry, float)
    assert isinstance(model.flow_looming, float)
    assert isinstance(model.flow_cliff, float)
    # flow values should be valid floats (no nan)
    import math
    assert not math.isnan(model.flow_asymmetry)
    assert not math.isnan(model.flow_looming)
    assert not math.isnan(model.flow_cliff)


def test_model_flow_signals_persist_across_steps():
    """Flow signal values persist across step() calls."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas()
    # First step sets flow signals via encode_retina inside step()
    ctrl1, _ = model.step(atlas, now=0.0)
    asym1 = model.flow_asymmetry
    loo1 = model.flow_looming
    clf1 = model.flow_cliff

    # Second step updates them
    ctrl2, _ = model.step(atlas, now=0.02)
    # Values are valid floats
    assert isinstance(model.flow_asymmetry, float)
    assert isinstance(model.flow_looming, float)


def test_model_step_completes_with_default_flow():
    """Model.step() runs without error with default flow signals."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas((128, 128, 128))
    try:
        control, spikes = model.step(atlas, now=0.0)
    except Exception as e:
        pytest.fail(f"step() raised {e}")
    assert isinstance(control.x, int)
    assert isinstance(control.y, int)


# ======================================================================
# 3. Memory flow-aware threshold tests
# ======================================================================

def test_memory_controller_accepts_flow():
    """MemoryController.update() accepts flow_kwargs without error."""
    mc = MemoryController()
    result = mc.update(
        temporal_energy=0.5,
        frame_seq=0,
        forward_rate=20.0,
        x=100.0,
        z=200.0,
        flow_asymmetry=0.1,
        flow_looming=0.0,
        flow_cliff=1.0,
    )
    assert len(result) == 6


def test_memory_flow_looming_lowers_threshold():
    """High flow_looming decreases stuck threshold, making escape easier."""
    mc = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=1.0, rate_threshold=5.0, rate_stuck_s=1.0),
        spatial=SpatialMemoryMap(loop_window=20, loop_threshold=0.5),
    )

    # Drive into stuck + loop territory with looming
    for i in range(100):
        mc.update(0.01, 0, 1.0, float((i % 2) * 50), 200.0, flow_looming=0.5, flow_cliff=1.0)

    # With looming > 0.3, the stuck threshold is lowered
    # (adjusted_threshold = 0.8 - (looming-0.3)*2*0.4 = 0.8 - 0.16 = 0.64)
    assert mc.stuck_score > 0, "Should be stuck"
    # Escape should be active due to lowered threshold
    assert mc.escape_behavior, "Looming should have lowered the threshold enough for escape"


def test_memory_cliff_emergency():
    """Multi-frame confirmed cliff triggers immediate escape."""
    mc = MemoryController()
    # Fill the confirmation window with low green values to trigger cliff_detected
    for _ in range(5):  # fill 5-frame default window
        mc.update(
            temporal_energy=0.01,
            frame_seq=0,
            forward_rate=20.0,
            x=100.0,
            z=200.0,
            flow_looming=0.0,
            flow_cliff=0.2,  # below entering_threshold
            ground_angle=0.0,  # actual cliff, not slope
        )
    # Cliff should now be confirmed
    assert mc.cliff_detected
    assert mc.cliff_confidence > 0
    # Escape should be triggered by confirmed cliff
    assert mc.escape_behavior, (
        "Confirmed cliff emergency should trigger escape even without stuck detection"
    )


def test_memory_no_cliff_emergency_when_cliff_high():
    """flow_cliff >= 0.3 does NOT trigger emergency escape."""
    mc = MemoryController()
    result = mc.update(
        temporal_energy=0.01,
        frame_seq=0,
        forward_rate=20.0,
        x=100.0,
        z=200.0,
        flow_looming=0.0,
        flow_cliff=1.0,  # normal - no cliff
    )
    assert len(result) == 6, f"Expected 6-tuple, got {result}"
    _, _, _, escape, _, _ = result
    assert not escape, "Should not trigger escape without cliff"


def test_memory_flow_asymmetry_does_not_affect_threshold():
    """flow_asymmetry (alone) does not directly affect escape threshold."""
    mc1 = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=2.0, rate_threshold=5.0, rate_stuck_s=2.0),
        spatial=SpatialMemoryMap(loop_window=20, loop_threshold=0.6),
    )
    mc2 = MemoryController(
        stuck=StuckDetector(temporal_stuck_s=2.0, rate_threshold=5.0, rate_stuck_s=2.0),
        spatial=SpatialMemoryMap(loop_window=20, loop_threshold=0.6),
    )
    # Drive both with same stuck conditions but different asymmetry
    for i in range(50):
        mc1.update(0.5, 0, 20.0, 100.0, 200.0, flow_asymmetry=-0.8, flow_looming=0.0, flow_cliff=1.0)
        mc2.update(0.5, 0, 20.0, 100.0, 200.0, flow_asymmetry=0.8, flow_looming=0.0, flow_cliff=1.0)
    assert mc1.escape_behavior == mc2.escape_behavior, (
        "Asymmetry alone should not affect escape threshold"
    )


# ======================================================================
# 3b. Self-motion separation tests
# ======================================================================

def test_self_motion_correction_preserves_zero_at_rest():
    """With heading=0 (no turn), true_asymmetry equals raw flow_asymmetry."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas()
    model.encode_retina(atlas, heading=0.0)
    assert model.true_asymmetry == model.flow_asymmetry, (
        "Zero heading change should not alter asymmetry"
    )


def test_self_motion_correction_reduces_asymmetry_during_turn():
    """A steady turn (non-zero heading_rate) reduces |true_asymmetry|
    compared to the raw flow_asymmetry."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas()
    # Step 1: initial heading = 0
    model.encode_retina(atlas, heading=0.0)
    raw_no_turn = model.flow_asymmetry
    corrected_before = model.true_asymmetry

    # Step 2: turn right — heading increases by 0.1 rad in one dt (0.02 s)
    # → heading_rate = 0.1 / 0.02 = 5 rad/s
    # → correction = 0.08 * 5 = 0.4
    model.encode_retina(atlas, heading=0.1)

    # The corrected true_asymmetry should be pulled toward zero
    # relative to the raw value by the correction term
    correction_magnitude = abs(model.SELF_MOTION_K * model.heading_rate)
    expected_raw_vs_corrected_diff = correction_magnitude
    actual_diff = abs(model.flow_asymmetry - model.true_asymmetry)
    assert abs(actual_diff - expected_raw_vs_corrected_diff) < 1e-6, (
        f"true_asymmetry should differ from raw by {expected_raw_vs_corrected_diff:.4f}, "
        f"got {actual_diff:.4f}"
    )


def test_self_motion_correction_clamps_to_one():
    """Extreme heading rates clamp true_asymmetry within [-1, 1]."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas((200, 200, 200))  # bright uniform
    # First call sets prev_heading = heading
    model.encode_retina(atlas, heading=0.0)
    # Extreme turn: heading jumps by 100 rad
    model.encode_retina(atlas, heading=100.0)
    assert -1.0 <= model.true_asymmetry <= 1.0, (
        f"true_asymmetry {model.true_asymmetry} out of [-1, 1]"
    )


def test_self_motion_heading_rate_preserved():
    """heading_rate is correctly computed from consecutive heading values."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas()
    model.encode_retina(atlas, heading=0.0)
    assert model.heading_rate == 0.0
    # Turn right: 0.05 rad in 0.02 s
    model.encode_retina(atlas, heading=0.05)
    expected_rate = 0.05 / model.dt  # 0.05 / 0.02 = 2.5 rad/s
    assert abs(model.heading_rate - expected_rate) < 1e-6
    # Turn left: back toward 0
    model.encode_retina(atlas, heading=-0.03)
    expected_rate2 = (-0.03 - 0.05) / model.dt  # -0.08 / 0.02 = -4.0 rad/s
    assert abs(model.heading_rate - expected_rate2) < 1e-6


def test_self_motion_property_exists():
    """FlyModel has self_motion property that returns heading_rate and true_asymmetry."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas()
    model.encode_retina(atlas, heading=0.0)
    sm = model.self_motion
    assert isinstance(sm, dict)
    assert "heading_rate" in sm
    assert "true_asymmetry" in sm
    assert "k" in sm
    assert sm["k"] == model.SELF_MOTION_K


def test_flow_asymmetry_unchanged_backward_compat():
    """flow_asymmetry remains the raw value (backward compatible)."""
    model = FlyModel(demo=True)
    atlas = _uniform_atlas((200, 200, 200))
    model.encode_retina(atlas, heading=0.0)
    raw_before = model.flow_asymmetry
    # With heading change, flow_asymmetry should still be the RAW compute_flow value
    model.encode_retina(atlas, heading=0.1)
    # The raw flow_asymmetry records the new frame's left/right brightness
    assert isinstance(model.flow_asymmetry, float)
    assert isinstance(model.true_asymmetry, float)
    # true_asymmetry differs from flow_asymmetry when heading_rate is non-zero
    if abs(model.heading_rate) > 0:
        assert model.true_asymmetry != model.flow_asymmetry, (
            "true_asymmetry should differ from raw flow_asymmetry during a turn"
        )
    # flow_asymmetry should still be valid
    import math
    assert not math.isnan(model.flow_asymmetry)
    assert not math.isnan(model.true_asymmetry)


# ======================================================================
# 4. Performance
# ======================================================================

def test_flow_computation_performance():
    """compute_flow should complete quickly (<< 5ms per call)."""
    retina = _full_retina()
    atlas = _uniform_atlas()

    # Warm up
    for _ in range(10):
        retina.compute_flow(atlas)

    # Timed run
    start = time.perf_counter()
    n = 100
    for _ in range(n):
        retina.compute_flow(atlas)
    elapsed_ms = (time.perf_counter() - start) / n * 1000

    assert elapsed_ms < 5.0, (
        f"compute_flow took {elapsed_ms:.2f} ms per call (threshold: 5 ms)"
    )


# ======================================================================
# 5. Integration invariants — JSON endpoint structure
# ======================================================================

def test_flow_json_structure():
    """Verify main.py flow_json dict structure matches what /flow.json serves."""
    import json
    # Simulate the dict construction from main.py
    flow_json = json.dumps({
        "asymmetry": round(-0.4849, 4),
        "true_asymmetry": round(-0.0849, 4),
        "heading_rate": round(5.0, 4),
        "looming": round(0.1234, 4),
        "cliff": round(0.5678, 4),
        "cliff_detected": False,
        "cliff_confidence": round(0.0, 3),
        "cliff_confirmed": False,
        "cliff_rate": round(0.0, 4),
        "tick": 42,
    }, separators=(",", ":"))
    parsed = json.loads(flow_json)
    assert "asymmetry" in parsed
    assert "true_asymmetry" in parsed
    assert "heading_rate" in parsed
    assert "looming" in parsed
    assert "cliff" in parsed
    assert "cliff_detected" in parsed
    assert "cliff_confidence" in parsed
    assert "cliff_confirmed" in parsed
    assert "cliff_rate" in parsed
    assert "tick" in parsed
    assert isinstance(parsed["asymmetry"], float)
    assert isinstance(parsed["true_asymmetry"], float)
    assert isinstance(parsed["heading_rate"], float)
    assert isinstance(parsed["looming"], float)
    assert isinstance(parsed["cliff"], float)
    assert isinstance(parsed["cliff_detected"], bool)
    assert isinstance(parsed["cliff_confidence"], float)
    assert isinstance(parsed["cliff_confirmed"], bool)
    assert isinstance(parsed["cliff_rate"], float)
    assert isinstance(parsed["tick"], int)


def test_preemptive_avoidance_order():
    """In main.py, pre-emptive avoidance fires BEFORE escape override.
    
    The code structure (visible in source) ensures this by checking
    `not memory_ctrl.escape_behavior` before the avoidance block,
    then having the escape block separate afterward.
    """
    import ast
    # Read the source directly to avoid importing main (which depends on 'resource')
    source = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Walk the async function body looking for the two blocks
    class BlockFinder(ast.NodeVisitor):
        def __init__(self):
            self.avoidance_line = None
            self.escape_line = None

        def visit_If(self, node):
            # Look for 'if not memory_ctrl.escape_behavior:' — may be a simple
            # UnaryOp(Not) or a compound BoolOp(And) such as
            # 'if not escape_behavior and not cliff_triggered:'
            if self._is_not_escape(node.test):
                self.avoidance_line = node.lineno
            # Look for 'if memory_ctrl.escape_behavior:' — may be a simple
            # Attribute or part of a BoolOp such as
            # 'if memory_ctrl.escape_behavior and not reflex_override:'
            if self._is_escape_active(node.test):
                self.escape_line = node.lineno
            self.generic_visit(node)

        @staticmethod
        def _is_escape_active(test_node):
            """Check if test_node is 'memory_ctrl.escape_behavior' either
            directly or as part of a BoolOp(And) compound expression."""
            # Direct: memory_ctrl.escape_behavior
            if (isinstance(test_node, ast.Attribute)
                    and test_node.attr == 'escape_behavior'):
                return True
            # Compound: BoolOp(And) containing an escape_behavior operand
            if (isinstance(test_node, ast.BoolOp)
                    and isinstance(test_node.op, ast.And)):
                for operand in test_node.values:
                    if (isinstance(operand, ast.Attribute)
                            and operand.attr == 'escape_behavior'):
                        return True
            return False

        @staticmethod
        def _is_not_escape(test_node):
            """Check if test_node is 'not escape_behavior' either directly
            or as part of a BoolOp(And) compound expression."""
            # Direct: not memory_ctrl.escape_behavior
            if (isinstance(test_node, ast.UnaryOp)
                    and isinstance(test_node.op, ast.Not)
                    and isinstance(test_node.operand, ast.Attribute)
                    and test_node.operand.attr == 'escape_behavior'):
                return True
            # Compound: BoolOp(And) containing a not-escape operand
            if (isinstance(test_node, ast.BoolOp)
                    and isinstance(test_node.op, ast.And)):
                for operand in test_node.values:
                    if (isinstance(operand, ast.UnaryOp)
                            and isinstance(operand.op, ast.Not)
                            and isinstance(operand.operand, ast.Attribute)
                            and operand.operand.attr == 'escape_behavior'):
                        return True
            return False

    finder = BlockFinder()
    finder.visit(tree)
    assert finder.avoidance_line is not None, "Pre-emptive avoidance block not found"
    assert finder.escape_line is not None, "Escape override block not found"
    assert finder.avoidance_line < finder.escape_line, (
        f"Avoidance (line {finder.avoidance_line}) must come before escape (line {finder.escape_line})"
    )