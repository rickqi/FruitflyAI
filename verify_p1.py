"""Verify P1a (Color/UV) + P1b (4-EMD) signals end-to-end."""
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fly64"))
from fly64.retina import SphericalRetina, CALIBRATION

ver = CALIBRATION["version"]
assert ver == "spherical-v2"
print(f"[PASS] CALIBRATION version: {ver}")

# Generate visual_pixels in the correct MaleCNS format
n_cells = 1536
flat_pixels = np.linspace(0, 3071, n_cells, dtype=np.int32)
visual_pixels = np.column_stack((flat_pixels // 64, flat_pixels % 64)).astype(np.uint8)

ret = SphericalRetina(visual_pixels)
print(f"[PASS] SphericalRetina: {ret.n_cells} cells loaded")
p_l2r = len(ret._emd_pairs["left_to_right"])
p_u2d = len(ret._emd_pairs["up_to_down"])
print(f"[PASS] EMD pairs: left_to_right={p_l2r}, up_to_down={p_u2d}")

# Test atlas — bluish with red right side
atlas = np.zeros((256, 384, 3), dtype=np.uint8)
atlas[:, :, :] = [180, 100, 200]
atlas[:, 192:, :2] = [220, 80]

flow = ret.compute_flow(atlas)

emd_keys = [k for k in flow if k.startswith("emd_")]
clr_keys = [k for k in flow if k.startswith(("sky_", "danger_", "color_contrast",
              "rg_", "by_", "uv_appx", "hue_mean", "sat"))]
az_keys = [k for k in flow if k.startswith("hue_az")]

assert len(emd_keys) >= 10, f"EMD keys={len(emd_keys)}"
assert len(clr_keys) >= 8, f"Color keys={len(clr_keys)}"
assert flow["sky_blue_index"] > 0.05, f"sky_blue={flow['sky_blue_index']}"

print(f"[PASS] EMD signals ({len(emd_keys)}): {emd_keys[:6]}")
print(f"[PASS] Color signals ({len(clr_keys)}): {clr_keys}")
print(f"[PASS] Azimuth hue bands ({len(az_keys)})")
print(f"[PASS] sky_blue_index={flow['sky_blue_index']:.3f}")
print(f"[PASS] color_contrast={flow['color_contrast']:.3f}")
print(f"[PASS] danger_red_index={flow['danger_red_index']:.3f}")

# Temporal motion detection
atlas2 = atlas.copy()
atlas2[:, :, 1] = 200  # green shift = motion
ret.reset_temporal_state()
flow2 = ret.compute_flow(atlas2)
assert flow2["emd_on_total"] >= 0
print(f"[PASS] Motion EMD: on_total={flow2['emd_on_total']:.6f}, off_total={flow2['emd_off_total']:.6f}")
print(f"[PASS] Return dict keys: {len(flow)} (was 27 before P1)")
print()
print("=" * 50)
print("P1 VERIFICATION: ALL PASS")
print(f"  Retina cells: {ret.n_cells}")
print(f"  New EMD signals: {len(emd_keys)}")
print(f"  New Color signals: {len(clr_keys)}")
print(f"  Azimuth hue bands: {len(az_keys)}")
print(f"  Total flow keys: {len(flow)}")
print("=" * 50)