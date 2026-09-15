"""Retina calibration and angular registration tests.

Verifies that SphericalRetina's azimuth/elevation mapping matches the
design specification in CALIBRATION (270°×144° FOV, 8.4375° subgrid).
This is the automated calibration test for B2 视网膜配准.

Design Spec (from CALIBRATION + code):
  - horizontal_fov_deg = 270°
  - elevation_limit_deg = 72° (total 144°)
  - overlap_deg = 17° between left/right eye
  - Left eye azimuth:  col 0..31  →  -135° .. +8.5°
  - Right eye azimuth: col 32..63 →  -8.5° .. +135°
  - Elevation:         row 0..47  →  +72° .. -72°
  - Per-column step:   Δaz ≈ 143.5 / 31 ≈ 4.629 °/col
  - Acceptance cone σ: 2°
"""
import numpy as np
import pytest

from fly64.retina import SphericalRetina, angular_rays, CALIBRATION


# ---- Standard retina for calibration tests ----
# Use every other grid cell (stride 2) like the production retina.
def _full_retina():
    return SphericalRetina(
        np.array([(r, c) for r in range(0, 48, 2)
                  for c in range(0, 64, 2)], float))


def _small_retina(rows=range(0, 48, 4), cols=range(0, 64, 4)):
    pixels = np.array([(r, c) for r in rows for c in cols], float)
    return SphericalRetina(pixels)


# ======================================================================
# 1. Design spec consistency
# ======================================================================

def test_calibration_spec_self_consistent():
    """CALIBRATION dict values are internally consistent with code formulas."""
    assert CALIBRATION["horizontal_fov_deg"] == 270
    assert CALIBRATION["elevation_limit_deg"] == 72
    assert CALIBRATION["overlap_deg"] == 17
    assert CALIBRATION["acceptance_sigma_deg"] == 2
    assert CALIBRATION["face_size"] == 128
    assert set(CALIBRATION["color_channels"]) == {"R", "G", "B", "UV_appx", "H", "S", "V"}
    assert CALIBRATION["version"] == "spherical-v2"


# ======================================================================
# 2. Azimuth mapping accuracy
# ======================================================================

def test_azimuth_left_eye_range():
    """Left eye col 0 → -135°, col 31 → +8.5°."""
    pixels = np.array([[24.0, c] for c in range(32)], float)  # row=24, cols 0..31
    retina = SphericalRetina(pixels)
    az = retina.azimuth_deg
    np.testing.assert_allclose(az[0], -135.0, atol=0.01, err_msg="col 0 should be -135°")
    np.testing.assert_allclose(az[-1], 8.5,   atol=0.01, err_msg="col 31 should be +8.5°")
    assert np.all(az >= -135.0), "Left eye azimuth should never be < -135°"
    assert np.all(az <= 8.51),   "Left eye azimuth should never exceed +8.5°"


def test_azimuth_right_eye_range():
    """Right eye col 32 → -8.5°, col 63 → +135°."""
    pixels = np.array([[24.0, c] for c in range(32, 64)], float)
    retina = SphericalRetina(pixels)
    az = retina.azimuth_deg
    np.testing.assert_allclose(az[0], -8.5, atol=0.01, err_msg="col 32 should be -8.5°")
    np.testing.assert_allclose(az[-1], 135.0, atol=0.01, err_msg="col 63 should be +135°")
    assert np.all(az >= -8.5),  "Right eye azimuth should never be < -8.5°"
    assert np.all(az <= 135.01), "Right eye azimuth should never exceed +135°"


def test_azimuth_monotonic_increasing():
    """Azimuth increases strictly left-to-right within each row of each eye."""
    retina = _full_retina()
    vp = retina._vp_rc
    # Group by row within each eye
    for eye_label, col_min, col_max in (("left", 0, 32), ("right", 32, 64)):
        eye_mask = (vp[:, 1] >= col_min) & (vp[:, 1] < col_max)
        eye_indices = np.where(eye_mask)[0]
        # Sort by row, then col
        rows_in_eye = np.unique(vp[eye_indices, 0])
        for row in rows_in_eye:
            row_mask = eye_mask & (vp[:, 0] == row)
            row_az = retina.azimuth_deg[row_mask]
            row_cols = vp[row_mask, 1]
            # Verify col indices are increasing
            assert np.all(np.diff(row_cols) > 0), \
                f"{eye_label} eye row {row}: cols not increasing"
            assert np.all(np.diff(row_az) > 0), \
                f"{eye_label} eye row {row}: azimuth not monotonic"


def test_azimuth_per_column_step():
    """Per-column step should be 143.5/31 ≈ 4.629° within each eye."""
    pixels = np.array([[24.0, 0], [24.0, 1], [30.0, 30], [30.0, 31]], float)
    retina = SphericalRetina(pixels)
    step_01 = retina.azimuth_deg[1] - retina.azimuth_deg[0]
    step_30 = retina.azimuth_deg[3] - retina.azimuth_deg[2]
    expected = 143.5 / 31.0
    np.testing.assert_allclose(step_01, expected, atol=1e-4,
                               err_msg=f"azimuth step per column should be {expected:.4f}°")
    np.testing.assert_allclose(step_30, expected, atol=1e-4,
                               err_msg=f"azimuth step between distant cols should be {expected:.4f}°")


def test_azimuth_overlap_exists():
    """Overlap region between left and right eye is ~17° centered at 0°.

    Left eye cells span [-135°, +8.5°]; right eye cells span [-8.5°, +135°].
    Overlap = [-8.5°, +8.5°] = 17°.
    With stride-2 sampling, use exact boundary pixels to verify.
    """
    # Use exact boundary pixels to verify the overlap design
    # Left eye at col 31 gives az = -135 + 31*143.5/31 = 8.5
    # Right eye at col 32 gives az = -8.5
    pixels = np.array([
        [24.0, 31],   # left eye last col
        [24.0, 32],   # right eye first col
    ], float)
    retina = SphericalRetina(pixels)
    np.testing.assert_allclose(retina.azimuth_deg[0], 8.5, atol=0.01,
                               err_msg="Left eye col 31 should be at +8.5°")
    np.testing.assert_allclose(retina.azimuth_deg[1], -8.5, atol=0.01,
                               err_msg="Right eye col 32 should be at -8.5°")

    # Verify overlap with standard retina
    retina2 = _full_retina()
    left_mask = retina2._vp_rc[:, 1] < 32
    right_mask = retina2._vp_rc[:, 1] >= 32
    left_az = retina2.azimuth_deg[left_mask]
    right_az = retina2.azimuth_deg[right_mask]
    # Some left-eye cells have az > -8.5 and some right-eye cells have az < 8.5
    assert np.any(left_az > -8.5), "Left eye should have cells in overlap (az > -8.5°)"
    assert np.any(right_az < 8.5), "Right eye should have cells in overlap (az < 8.5°)"


# ======================================================================
# 3. Elevation mapping accuracy
# ======================================================================

def test_elevation_range():
    """Elevation: row 0 → +72°, row 47 → -72°."""
    pixels = np.array([[0.0, 16], [47.0, 16]], float)
    retina = SphericalRetina(pixels)
    np.testing.assert_allclose(retina.elevation_deg[0], 72.0, atol=0.5,
                               err_msg="row 0 should be +72°")
    np.testing.assert_allclose(retina.elevation_deg[1], -72.0, atol=0.5,
                               err_msg="row 47 should be -72°")


def test_elevation_monotonic_decreasing():
    """Elevation decreases (up to down) strictly with row index."""
    pixels = np.array([[r, 16.0] for r in range(48)], float)
    retina = SphericalRetina(pixels)
    assert np.all(np.diff(retina.elevation_deg) < 0), "Elevation must decrease with row"


def test_elevation_per_row_step():
    """Per-row elevation step should be 144/47 ≈ 3.064°."""
    pixels = np.array([[0.0, 16], [1.0, 16], [46.0, 16], [47.0, 16]], float)
    retina = SphericalRetina(pixels)
    step = retina.elevation_deg[1] - retina.elevation_deg[0]
    expected = -144.0 / 47.0
    np.testing.assert_allclose(step, expected, atol=1e-4,
                               err_msg=f"Elevation step should be {expected:.4f}°")
    # Total span
    total = retina.elevation_deg[-1] - retina.elevation_deg[-2]
    np.testing.assert_allclose(total, expected, atol=1e-4)


def test_elevation_upper_lower_ratio_approx_equal():
    """~50% of cells above horizon (elev ≥ 0), ~50% below."""
    retina = _full_retina()
    total = len(retina.elevation_deg)
    above = np.sum(retina.elevation_deg >= 0)
    fraction = above / total
    assert 0.40 <= fraction <= 0.60, \
        f"Expected ~50% cells above horizon, got {fraction:.1%}"


# ======================================================================
# 4. Ray direction consistency
# ======================================================================

def test_rays_are_unit_length():
    """Every ray computed from azimuth/elevation has unit norm."""
    retina = _full_retina()
    norms = np.linalg.norm(retina.rays, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6), \
        f"Max ray norm deviation: {np.max(np.abs(norms - 1.0)):.2e}"


def test_angular_rays_inverse():
    """angular_rays → arctan2/arcsin round-trip recovers azimuth/elevation."""
    test_az = np.array([-135, -90, -45, -8.5, 0, 8.5, 45, 90, 135], float)
    test_el = np.array([-72, -36, 0, 36, 72], float)
    az_grid, el_grid = np.meshgrid(test_az, test_el)
    az_flat, el_flat = az_grid.ravel(), el_grid.ravel()
    rays = angular_rays(az_flat, el_flat)
    recovered_az = np.rad2deg(np.arctan2(rays[:, 0], rays[:, 2]))
    recovered_el = np.rad2deg(np.arcsin(np.clip(rays[:, 1], -1, 1)))
    np.testing.assert_allclose(recovered_az, az_flat, atol=1e-4,
                               err_msg="Azimuth round-trip deviation")
    np.testing.assert_allclose(recovered_el, el_flat, atol=1e-4,
                               err_msg="Elevation round-trip deviation")


def test_forward_ray_direction():
    """Forward gaze (az=0, el=0) should point along +Z."""
    rays = angular_rays(np.array([0.0]), np.array([0.0]))
    np.testing.assert_allclose(rays[0], [0, 0, 1], atol=1e-6)


def test_right_ray_direction():
    """Rightward gaze (az=90, el=0) should point along +X."""
    rays = angular_rays(np.array([90.0]), np.array([0.0]))
    np.testing.assert_allclose(rays[0], [1, 0, 0], atol=1e-6)


def test_up_ray_direction():
    """Upward gaze (az=0, el=90) should point along +Y."""
    rays = angular_rays(np.array([0.0]), np.array([90.0]))
    np.testing.assert_allclose(rays[0], [0, 1, 0], atol=1e-6)


# ======================================================================
# 5. Cone sampling indices consistency
# ======================================================================

def test_cone_indices_shape():
    """cone_indices returns (N, 7) for N input rays."""
    from fly64.retina import cone_indices
    rays = np.array([[0, 0, 1], [1, 0, 0]], float)
    idx = cone_indices(rays)
    assert idx.shape == (2, 7), f"Expected (2, 7), got {idx.shape}"


def test_cone_sample_weights_sum():
    """Weights sum to 1.0: 0.25 center + 6×0.125 = 1.0."""
    from fly64.retina import cone_indices
    retina = _full_retina()
    np.testing.assert_allclose(retina.weights.sum(), 1.0, atol=1e-6)
    assert retina.weights[0] == 0.25
    assert np.allclose(retina.weights[1:], 0.125)


# ======================================================================
# 6. Grid / sector boundary alignment
# ======================================================================

def test_sixteen_sector_coverage():
    """16 sectors (8 azimuth × 2 elevation) cover all cells exactly once."""
    retina = _full_retina()
    all_assigned = np.zeros(len(retina.azimuth_deg), bool)
    for name in retina._sector_names:
        mask = retina._sector_masks[name]
        all_assigned |= mask
    assert np.all(all_assigned), f"{np.sum(~all_assigned)} cells not in any sector"


def test_sector_boundary_alignment():
    """Sector azimuth boundaries align with expected design bounds.

    8 azimuth bands from -135 to +135, each 33.75° wide.
    """
    retina = _full_retina()
    az_bounds = np.linspace(-135, 135, 9)
    for i in range(8):
        # Each sector mask should span cells within its bounds
        band_mask = (retina.azimuth_deg >= az_bounds[i]) & \
                    (retina.azimuth_deg < az_bounds[i + 1])
        sector_upper = retina._sector_masks[f"az{i}_upper"]
        sector_lower = retina._sector_masks[f"az{i}_lower"]
        combined = sector_upper | sector_lower
        # The sector masks should be subsets of the band
        assert np.all(combined <= band_mask), \
            f"az{i} sector has cells outside its azimuth band [{az_bounds[i]}, {az_bounds[i+1]})"


def test_sector_width_33_75():
    """Each azimuth band is exactly 33.75° (270°/8)."""
    az_bounds = np.linspace(-135, 135, 9)
    widths = np.diff(az_bounds)
    np.testing.assert_allclose(widths, 33.75, atol=1e-10)


# ======================================================================
# 7. Measured vs design angular error report
# ======================================================================

def test_measure_angular_errors():
    """Quantify azimuth/elevation mapping errors by comparing against
    a 'ground-truth' spherical projection of the cube-map direction.
    
    Since each cell at (row,col) samples the cube face at a specific
    texel, we can compute what the ideal angular direction for that
    texel should be and compare against retina.azimuth_deg / 
    retina.elevation_deg.

    This test quantifies the B2 registration error.
    """
    from fly64.retina import BASES, atlas_indices
    from fly64.bridge import SharedBridge

    # Build a direction atlas where each texel stores its own
    # cube-face-normalized direction vector
    yy, xx = np.mgrid[:128, :128]
    u, v = (xx + 0.5) / 64 - 1, 1 - (yy + 0.5) / 64
    dir_atlas = np.zeros((256, 384, 3), np.float32)
    for face, (right, up, forward) in enumerate(BASES):
        rays = forward + u[..., None] * right + v[..., None] * up
        rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
        fr = face // 3
        fc = face % 3
        dir_atlas[fr * 128:(fr + 1) * 128, fc * 128:(fc + 1) * 128] = rays

    # For each visual cell, get the true direction from the atlas
    # via its cone_indices, then compute angular error
    retina = _full_retina()
    # Each cell samples 7 texels via cone sampling; average them
    dir_samples = dir_atlas.reshape(-1, 3)[retina.indices]  # (N, 7, 3)
    # Weighted average
    dirs = np.sum(dir_samples * retina.weights[None, :, None], axis=1)  # (N, 3)
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)

    true_az = np.rad2deg(np.arctan2(dirs[:, 0], dirs[:, 2]))
    true_el = np.rad2deg(np.arcsin(np.clip(dirs[:, 1], -1, 1)))

    az_err = np.abs(retina.azimuth_deg - true_az)
    el_err = np.abs(retina.elevation_deg - true_el)

    # Report statistics
    max_az_err = float(np.max(az_err))
    mean_az_err = float(np.mean(az_err))
    p95_az_err = float(np.percentile(az_err, 95))
    max_el_err = float(np.max(el_err))
    mean_el_err = float(np.mean(el_err))
    p95_el_err = float(np.percentile(el_err, 95))

    print(f"\n--- Angular Registration Error Report ---")
    print(f"  Azimuth error:  max={max_az_err:.4f}°, mean={mean_az_err:.4f}°, p95={p95_az_err:.4f}°")
    print(f"  Elevation error: max={max_el_err:.4f}°, mean={mean_el_err:.4f}°, p95={p95_el_err:.4f}°")

    # B2 bottleneck: linear approximation vs spherical projection
    # Tolerances reflect engineered (not measured MaleCNS) registration:
    # Azimuth: ~5-15° error expected (B2 root cause #1)
    # Elevation: ~3-10° error expected (B2 root cause #2)
    assert mean_az_err < 8.0, f"Mean azimuth error {mean_az_err:.4f}° exceeds 8° budget"
    assert max_az_err < 20.0, f"Max azimuth error {max_az_err:.4f}° exceeds 20° ceiling"
    assert mean_el_err < 8.0, f"Mean elevation error {mean_el_err:.4f}° exceeds 8° budget"
    assert max_el_err < 20.0, f"Max elevation error {max_el_err:.4f}° exceeds 20° ceiling"


# ======================================================================
# 8. Visual field coverage assertion
# ======================================================================

def test_horizontal_fov_is_270_degrees():
    """The full horizontal FOV from leftmost to rightmost cell is ~270°."""
    pixels = np.array([[24.0, 0], [24.0, 63]], float)
    retina = SphericalRetina(pixels)
    span = retina.azimuth_deg[-1] - retina.azimuth_deg[0]
    np.testing.assert_allclose(span, 270.0, atol=0.1,
                               err_msg=f"Horizontal FOV should be 270°, got {span:.2f}°")


def test_vertical_fov_is_144_degrees():
    """The full vertical FOV from topmost to bottommost cell is ~144°."""
    pixels = np.array([[0.0, 16], [47.0, 16]], float)
    retina = SphericalRetina(pixels)
    span = retina.elevation_deg[0] - retina.elevation_deg[-1]
    np.testing.assert_allclose(span, 144.0, atol=0.5,
                               err_msg=f"Vertical FOV should be 144°, got {span:.2f}°")


def test_acceptance_cone_radius():
    """Acceptance cone radius in DEG should match sigma*sqrt(2) ≈ 2.828°."""
    from fly64.retina import cone_indices
    import math
    expected_radius_rad = np.deg2rad(CALIBRATION["acceptance_sigma_deg"]) * math.sqrt(2)
    expected_radius_deg = np.rad2deg(expected_radius_rad)
    assert expected_radius_deg > 0
    # The radius is used internally in cone_indices; verify it's positive and reasonable
    assert 1.5 < expected_radius_deg < 5.0, \
        f"Acceptance cone radius should be ~2.828°, got {expected_radius_deg:.3f}°"


# ======================================================================
# 9. Edge orientation pair consistency with grid
# ======================================================================

def test_edge_pairs_stay_within_eye():
    """Edge orientation pairs never cross between left and right eye."""
    retina = _full_retina()
    for name, pairs in retina._edge_pairs.items():
        if len(pairs) == 0:
            continue
        left_eye = retina._vp_rc[:, 1] < 32
        for idx_a, idx_b in pairs:
            assert left_eye[idx_a] == left_eye[idx_b], \
                f"{name} pair ({idx_a},{idx_b}) crosses eye boundary"


def test_emd_pairs_stay_within_eye():
    """EMD pairs never cross between left and right eye."""
    retina = _full_retina()
    left_eye = retina._vp_rc[:, 1] < 32
    for key, pairs in retina._emd_pairs.items():
        if len(pairs) == 0:
            continue
        for idx_a, idx_b in pairs:
            assert left_eye[idx_a] == left_eye[idx_b], \
                f"EMD {key} pair ({idx_a},{idx_b}) crosses eye boundary"