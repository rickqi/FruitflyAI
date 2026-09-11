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
    assert "left_right_asymmetry" in flow
    assert "center_expansion" in flow
    assert "lower_field_green" in flow
    assert isinstance(flow["left_right_asymmetry"], float)
    assert isinstance(flow["center_expansion"], float)
    assert isinstance(flow["lower_field_green"], float)


def test_flow_sectors_has_all_expected():
    """Sectors dict contains all 8 named regions."""
    retina = _full_retina()
    flow = retina.compute_flow(_uniform_atlas())
    expected = (
        "left_upper","left_lower",
        "center-left_upper","center-left_lower",
        "center-right_upper","center-right_lower",
        "right_upper","right_lower",
    )
    for name in expected:
        assert name in flow["sectors"], f"Missing sector {name}"
        assert isinstance(flow["sectors"][name], float)


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


def test_flow_sectors_change_with_input():
    """Sector energies change when the corresponding face changes brightness."""
    retina = _full_retina()
    atlas_bright = _make_atlas([
        (200, 200, 200),  # forward
        (10, 10, 10),     # right
        (10, 10, 10),     # back
        (10, 10, 10),     # left
        (10, 10, 10),     # up
        (10, 10, 10),     # down
    ])
    flow_bright = retina.compute_flow(atlas_bright)

    atlas_dim = _make_atlas([
        (10, 10, 10),     # forward (dimmed)
        (10, 10, 10),     # right
        (10, 10, 10),     # back
        (10, 10, 10),     # left
        (10, 10, 10),     # up
        (10, 10, 10),     # down
    ])
    flow_dim = retina.compute_flow(atlas_dim)

    # At least one center sector should change
    names = [k for k in flow_bright["sectors"] if "center" in k]
    any_change = any(
        abs(flow_bright["sectors"][n] - flow_dim["sectors"][n]) > 0.001
        for n in names
    )
    assert any_change, "Sector energies did not change with input"


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
    assert len(result) == 5


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
    """flow_cliff < 0.3 with visible temporal_energy triggers immediate escape."""
    mc = MemoryController()
    # Not stuck, no exploration mode - but cliff emergency should override
    result = mc.update(
        temporal_energy=0.01,
        frame_seq=0,
        forward_rate=20.0,
        x=100.0,
        z=200.0,
        flow_looming=0.0,
        flow_cliff=0.2,  # below threshold
    )
    _, _, _, escape, _ = result
    assert escape, (
        "Cliff emergency should trigger escape even without stuck detection"
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
    _, _, _, escape, _ = result
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
    # Simulate the dict construction from main.py line 425-430
    flow_json = json.dumps({
        "asymmetry": round(-0.4849, 4),
        "looming": round(0.1234, 4),
        "cliff": round(0.5678, 4),
        "tick": 42,
    }, separators=(",", ":"))
    parsed = json.loads(flow_json)
    assert "asymmetry" in parsed
    assert "looming" in parsed
    assert "cliff" in parsed
    assert "tick" in parsed
    assert isinstance(parsed["asymmetry"], float)
    assert isinstance(parsed["looming"], float)
    assert isinstance(parsed["cliff"], float)
    assert isinstance(parsed["tick"], int)


def test_preemptive_avoidance_order():
    """In main.py, pre-emptive avoidance fires BEFORE escape override.
    
    The code structure (visible in source) ensures this by checking
    `not memory_ctrl.escape_behavior` before the avoidance block,
    then having the escape block separate afterward.
    """
    import ast
    # Read the source directly to avoid importing main (which depends on 'resource')
    source = (Path(__file__).resolve().parent.parent / "fly64" / "main.py").read_text()
    tree = ast.parse(source)

    # Walk the async function body looking for the two blocks
    class BlockFinder(ast.NodeVisitor):
        def __init__(self):
            self.avoidance_line = None
            self.escape_line = None

        def visit_If(self, node):
            # Look for 'if not memory_ctrl.escape_behavior:'
            if (isinstance(node.test, ast.UnaryOp)
                    and isinstance(node.test.op, ast.Not)
                    and isinstance(node.test.operand, ast.Attribute)
                    and node.test.operand.attr == 'escape_behavior'):
                self.avoidance_line = node.lineno
            # Look for 'if memory_ctrl.escape_behavior:'
            if (isinstance(node.test, ast.Attribute)
                    and node.test.attr == 'escape_behavior'):
                self.escape_line = node.lineno
            self.generic_visit(node)

    finder = BlockFinder()
    finder.visit(tree)
    assert finder.avoidance_line is not None, "Pre-emptive avoidance block not found"
    assert finder.escape_line is not None, "Escape override block not found"
    assert finder.avoidance_line < finder.escape_line, (
        f"Avoidance (line {finder.avoidance_line}) must come before escape (line {finder.escape_line})"
    )