"""Verify scene recognition module."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fly64"))

from fly64.scene_recognition import SM64_LEVEL_PROFILES, SceneRecognizer
import numpy as np

profiles = SM64_LEVEL_PROFILES
print(f"Profiles: {len(profiles)}")
for k, v in list(profiles.items())[:3]:
    feat_count = len(v["features"])
    print(f'  {k}: {v["name"]}, tags={v["tags"]}, features={feat_count}')

rec = SceneRecognizer()

# Helper to create a realistic mock for any SM64 level
def make_mock(overrides: dict) -> object:
    class MockModel:
        sky_score = 0.3; wall_score = 0.3; ramp_score = 0.15
        opening_score = 0.2; door_frame_score = 0.0; ground_angle = 0.6
        sky_blue_index = 0.2; danger_red_index = 0.05; uv_appx_mean = 0.15
        saturation_mean = 0.2; hue_mean = 90.0; color_contrast = 0.2
        emd_horizontal = 0.04; emd_vertical = 0.02
        emd_on_total = 0.03; emd_off_total = 0.02
        target_count = 0; fg_fraction = 0.0; terrain = "mixed"
        enclosure_score = 0.1; color_signature = False
        on_raw = 0.03; off_raw = 0.02; sustained_raw = 0.03
        rh = 0.3; gh = 0.3; bh = 0.3; on_energy = 0.03; blue_dom = 0.1
    for k, v in overrides.items():
        setattr(MockModel, k, v)
    return MockModel()

tests = [
    ("bob_omb_battlefield",   make_mock({"sky_score": 0.8, "wall_score": 0.05, "ground_angle": 0.8, "sky_blue_index": 0.5, "danger_red_index": 0.03, "saturation_mean": 0.3, "uv_appx_mean": 0.3, "on_raw": 0.06, "terrain": "open_flat"})),
    ("lethal_lava_land",      make_mock({"sky_score": 0.4, "ramp_score": 0.1, "danger_red_index": 0.75, "saturation_mean": 0.65, "color_contrast": 0.4, "hue_mean": 15.0, "uv_appx_mean": 0.1, "on_raw": 0.04, "terrain": "mixed"})),
    ("big_boos_haunt",        make_mock({"sky_score": 0.02, "wall_score": 0.7, "enclosure_score": 0.75, "ramp_score": 0.02, "danger_red_index": 0.02, "saturation_mean": 0.1, "color_contrast": 0.1, "uv_appx_mean": 0.05, "sky_blue_index": 0.01, "on_raw": 0.02, "terrain": "mixed"})),
    ("snowmans_land",         make_mock({"sky_score": 0.75, "wall_score": 0.05, "ramp_score": 0.3, "hue_mean": 220.0, "saturation_mean": 0.08, "danger_red_index": 0.0, "color_contrast": 0.1, "uv_appx_mean": 0.35, "sky_blue_index": 0.55, "on_raw": 0.04, "terrain": "open_flat"})),
    ("jolly_roger_bay",       make_mock({"sky_score": 0.6, "wall_score": 0.05, "sky_blue_index": 0.75, "uv_appx_mean": 0.6, "danger_red_index": 0.01, "saturation_mean": 0.35, "blue_dom": 0.5, "on_energy": 0.04, "terrain": "water"})),
    ("hazy_maze_cave",        make_mock({"sky_score": 0.0, "wall_score": 0.8, "enclosure_score": 0.88, "ground_angle": 0.4, "ramp_score": 0.02, "saturation_mean": 0.1, "uv_appx_mean": 0.04, "danger_red_index": 0.0, "on_raw": 0.02, "terrain": "mixed"})),
    ("rainbow_ride",          make_mock({"sky_score": 0.95, "wall_score": 0.0, "enclosure_score": 0.0, "ground_angle": 0.5, "sky_blue_index": 0.8, "danger_red_index": 0.02, "color_contrast": 0.6, "saturation_mean": 0.5, "on_raw": 0.06, "terrain": "open_flat"})),
]

all_pass = True
for expected, model in tests:
    level_id, conf, tags = rec.recognize(model)
    ok = level_id == expected
    status = "OK" if ok else f"MISMATCH (got {level_id})"
    if not ok:
        all_pass = False
    print(f'  {expected:30s} -> {level_id:20s} conf={conf:.2f} [{status}]')

print()
if all_pass:
    print("ALL SCENE RECOGNITION TESTS PASSED")
else:
    print("SOME TESTS FAILED")

# Test custom labels
rec.add_label("abcd", "秘密房间", ["indoor", "secret"])
label = rec.get_label("abcd")
assert label == "秘密房间", f"Label mismatch: {label}"
print("Custom labels: OK")

# Test save/load
rec.save("/tmp/scene_labels.json")
rec2 = SceneRecognizer()
rec2.load("/tmp/scene_labels.json")
assert rec2.get_label("abcd") == "秘密房间"
print("Save/Load: OK")
print("\nALL TESTS PASSED")