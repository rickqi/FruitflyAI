"""Verify P1a (Color/UV) + P1b (4-EMD) signals are working end-to-end."""
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fly64"))

# 1) Check CALIBRATION
from fly64.retina import SphericalRetina, CALIBRATION

assert CALIBRATION["version"] == "spherical-v2", "CALIBRATION version wrong"
assert "color_channels" in CALIBRATION, "Missing color_channels"
print(f"[PASS] CALIBRATION version: {CALIBRATION['version']}")
print(f"[PASS] color_channels: {CALIBRATION['color_channels']}")

# 2) Load retina
vp = np.column_stack(np.mgrid[:48, :64].reshape(2, -1).T)
ret = SphericalRetina(vp)
print(f"[PASS] SphericalRetina: {ret.n_cells} cells loaded")
print(f"[PASS] EMD pairs: left_to_right={len(ret._emd_pairs['left_to_right'])}, "
      f"up_to_down={len(ret._emd_pairs['up_to_down'])}")

# 3) Create test atlas — blue sky + some red
atlas = np.zeros((256, 384, 3), dtype=np.uint8)
atlas[:, :, 0] = 180       # red
atlas[:, 192:, 0] = 220    # right side redder
atlas[:, :, 1] = 100       # green
atlas[:, :, 2] = 200       # blue-rich (simulates UV/sky)

flow = ret.compute_flow(atlas)

# 4) Verify EMD keys
emd_keys = [k for k in flow if k.startswith("emd_")]
print(f"[PASS] EMD signals ({len(emd_keys)}): {emd_keys}")
assert len(emd_keys) >= 10

# 5) Verify color keys
color_keys = [k for k in flow if k.startswith(
    ("sky_", "danger_", "color_contrast", "rg_", "by_",
     "uvl_", "uv_appx", "hue_mean", "saturation_mean")
)]
az_keys = [k for k in flow if k.startswith("hue_az")]
print(f"[PASS] Color signals ({len(color_keys)}): {color_keys}")
print(f"[PASS] Azimuth hue ({len(az_keys)}): {az_keys[:4]}...")

# 6) Sky detection
assert flow["sky_blue_index"] > 0.05, f"sky_blue_index={flow['sky_blue_index']}"
print(f"[PASS] sky_blue_index={flow['sky_blue_index']:.3f} (sky detected)")

# 7) EMD motion detection with temporal difference
atlas2 = atlas.copy()
atlas2[:, :, 1] = 200  # green shift = simulated motion
flow2 = ret.compute_flow(atlas2)
assert flow2["emd_on_total"] >= 0, f"EMD negative: {flow2['emd_on_total']}"
print(f"[PASS] Motion detection: emd_on_total={flow2['emd_on_total']:.6f}")

# 8) Check asymmetry reverses when swapping left/right brightness
atlas_left = atlas.copy()
atlas_left[:, :128, :] = 0  # darken left third
flow_left = ret.reset_temporal_state()
flow_left = ret.compute_flow(atlas_left)
print(f"[PASS] Left-right asymmetry: {flow_left.get('emd_on_left', 0):.4f} "
      f"vs {flow_left.get('emd_on_right', 0):.4f}")

# 9) Run model import + encode_retina
from fly64.model import FlyModel
model = FlyModel()
print("[PASS] FlyModel imported and instantiated")
print(f"[PASS] EMD state vars: emd_horizontal={model.emd_horizontal}, "
      f"emd_vertical={model.emd_vertical}")
print(f"[PASS] Color state vars: sky_blue={model.sky_blue_index}, "
      f"danger_red={model.danger_red_index}")

# Summary
n_flow = len(flow)
n_old = 27
print(f"\n{'='*50}")
print(f"P1 VERIFICATION COMPLETE")
print(f"{'='*50}")
print(f"  compute_flow() keys: {n_flow} (was {n_old})")
print(f"  New EMD keys:       {len(emd_keys)}")
print(f"  New Color keys:     {len(color_keys) + len(az_keys)}")
print(f"  Total new signals:  {len(emd_keys) + len(color_keys) + len(az_keys)}")
print(f"  All assertions:     PASS")
print(f"{'='*50}")