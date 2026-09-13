"""Quick scene recognition test."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fly64"))
from fly64.scene_recognition import SceneRecognizer

rec = SceneRecognizer()

class M:
    sky_score=0.3; wall_score=0.3; ramp_score=0.15; opening_score=0.2
    door_frame_score=0.0; ground_angle=0.6; sky_blue_index=0.2
    danger_red_index=0.05; uv_appx_mean=0.15; saturation_mean=0.2
    color_contrast=0.2; enclosure_score=0.1; hue_mean=90.0
    emd_horizontal=0.04; emd_vertical=0.02; emd_on_total=0.03
    emd_off_total=0.02; target_count=0; fg_fraction=0.0; terrain="mixed"
    on_raw=0.03; off_raw=0.02; sustained_raw=0.03; rh=0.25; gh=0.25; bh=0.25
    on_energy=0.03; blue_dom=0.1; color_signature=False

tests = [
    ("bob_omb", {"sky_score":0.85,"wall_score":0.05,"ground_angle":0.8,
     "sky_blue_index":0.5,"danger_red_index":0.03,"saturation_mean":0.3,
     "uv_appx_mean":0.3,"blue_dom":0.2,"on_energy":0.06,"terrain":"open_flat"}),
    ("lava", {"sky_score":0.35,"wall_score":0.05,"danger_red_index":0.75,
     "saturation_mean":0.65,"color_contrast":0.4,"uv_appx_mean":0.1,
     "blue_dom":0.05,"on_energy":0.04,"ramp_score":0.1,"hue_mean":15.0}),
    ("haunt", {"sky_score":0.02,"wall_score":0.75,"enclosure_score":0.8,
     "ramp_score":0.02,"danger_red_index":0.02,"saturation_mean":0.08,
     "uv_appx_mean":0.03,"blue_dom":0.02,"on_energy":0.02,
     "sky_blue_index":0.01,"ground_angle":0.85}),
    ("snowman", {"sky_score":0.75,"wall_score":0.05,"hue_mean":220.0,
     "saturation_mean":0.08,"danger_red_index":0.0,"color_contrast":0.1,
     "uv_appx_mean":0.35,"sky_blue_index":0.55,"blue_dom":0.4,"on_energy":0.04}),
    ("jolly", {"sky_score":0.6,"sky_blue_index":0.75,"uv_appx_mean":0.6,
     "danger_red_index":0.01,"saturation_mean":0.35,"blue_dom":0.5,
     "on_energy":0.04,"terrain":"water","wall_score":0.05}),
    ("cave", {"sky_score":0.0,"wall_score":0.82,"enclosure_score":0.88,
     "ground_angle":0.35,"ramp_score":0.02,"saturation_mean":0.08,
     "uv_appx_mean":0.02,"blue_dom":0.01,"danger_red_index":0.0,
     "on_energy":0.02,"color_contrast":0.08}),
    ("rainbow", {"sky_score":0.95,"wall_score":0.0,"enclosure_score":0.0,
     "ground_angle":0.5,"sky_blue_index":0.8,"danger_red_index":0.02,
     "color_contrast":0.6,"saturation_mean":0.55,"uv_appx_mean":0.35,
     "blue_dom":0.45,"on_energy":0.06}),
]

expect = {"bob_omb":"bob_omb_battlefield","lava":"lethal_lava_land",
          "haunt":"big_boos_haunt","snowman":"snowmans_land",
          "jolly":"jolly_roger_bay","cave":"hazy_maze_cave",
          "rainbow":"rainbow_ride"}

ok_count = 0
for name, overrides in tests:
    m = M()
    for k, v in overrides.items():
        setattr(m, k, v)
    level_id, conf, tags = rec.recognize(m, min_confidence=0.0, min_margin=0.0)
    exp = expect[name]
    ok = level_id == exp
    if ok:
        ok_count += 1
    status = "OK" if ok else f"GOT {level_id}"
    print(f"{name:8s} -> {level_id:22s} conf={conf:.2f} [{status}]")

# Save/load
tmp = tempfile.mktemp(suffix=".json")
rec.add_label("test", "test_label", ["a","b"])
rec.save(tmp)
rec2 = SceneRecognizer()
rec2.load(tmp)
assert rec2.get_label("test") == "test_label"
os.remove(tmp)
print(f"Save/Load OK")

total = len(tests)
print(f"\n{ok_count}/{total} passed ({'ALL' if ok_count==total else 'SOME FAILED'})")