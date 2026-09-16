"""M3-default: EvolutionSkill built-in MBON learning analysis (slopes)."""
import pytest

from skills.evolution_skill import DataCollector, SensorSample


def _collector_with_samples():
    c = DataCollector(window_seconds=600)
    t0 = 1000.0
    for i in range(10):                      # 10 samples over 5 minutes
        s = SensorSample(
            timestamp=t0 + i * 30.0,
            position=(0, 0, 0), control=(0, 0, False),
            stuck_duration=0, visited_cells=0, coverage_pct=0,
            anomaly_state="idle", health_score=1.0, wall_score=0.0,
            asymmetry=0.0, ground_angle=1.0, ramp_score=0.0, terrain="open",
            reflex_active=False, escape_behavior=False,
            scene_name="t", scene_hash="h",
            command_decoupled=False, dialogue_active=False,
            interactive_near=False, local_motion_detected=False,
            revisit_count=0, scene_change_rate=0.0, forced_bold_explore=False,
            cliff_confirmed=False, tau=None, opening_score=0.0,
            door_frame_score=0.0, sky_score=0.0, pos_y=0.0,
            mb_w_punch=0.001 + 0.001 * i,        # +0.001 per 0.5 min = +0.002/min
            mb_w_dive=0.001 - 0.0005 * i,        # -0.001/min
            mb_w_groundpound=0.001,              # flat
            mb_w_longjump=0.002)
        c.samples.append(s)
    return c


def test_slope_per_column_computed():
    c = _collector_with_samples()
    m = c.get_metrics()
    assert m["mb_w_punch_slope_per_min"] == pytest.approx(0.002, abs=1e-4)
    assert m["mb_w_dive_slope_per_min"] == pytest.approx(-0.001, abs=1e-4)
    assert m["mb_w_groundpound_slope_per_min"] == 0.0


def test_min_slope_hook_exposes_worst_column():
    c = _collector_with_samples()
    m = c.get_metrics()
    assert m["mbon_w_min_slope_prim"] == "dive"
    assert m["mbon_w_min_slope"] == pytest.approx(-0.001, abs=1e-4)


def test_slope_none_without_enough_samples():
    c = DataCollector(window_seconds=600)
    c.samples.append(SensorSample(
        timestamp=0, position=(0, 0, 0), control=(0, 0, False),
        stuck_duration=0, visited_cells=0, coverage_pct=0,
        anomaly_state="idle", health_score=1.0, wall_score=0.0,
        asymmetry=0.0, ground_angle=1.0, ramp_score=0.0, terrain="t",
        reflex_active=False, escape_behavior=False, scene_name="t",
        scene_hash="h", command_decoupled=False, dialogue_active=False,
        interactive_near=False, local_motion_detected=False,
        revisit_count=0, scene_change_rate=0.0, forced_bold_explore=False,
        cliff_confirmed=False, tau=None, opening_score=0.0,
        door_frame_score=0.0, sky_score=0.0, pos_y=0.0,
        mb_w_punch=0.001))
    m = c.get_metrics()
    assert m["mb_w_punch_slope_per_min"] is None
    assert "mbon_w_min_slope" not in m


def test_pattern_file_contains_mbon_wrong_direction():
    import json
    d = json.load(open("skills/default_patterns.json"))
    p = next(p for p in d["patterns"] if p["id"] == "mbon_wrong_direction")
    assert p["conditions"]["mbon_w_min_slope"]["max"] == -0.0005
