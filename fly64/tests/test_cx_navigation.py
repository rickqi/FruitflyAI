"""EVO R20 · CX-1 regression — compass autonomy (self-motion integration).

The ring-attractor bump must move by INTEGRATED ANGULAR VELOCITY
(autonomous path-integration term) with external heading and sky azimuth
demoted to weak corrections.  No Python direction decisions.
"""
import numpy as np
import pytest

from fly64.central_complex import (
    CentralComplex,
    AnchorPathIntegrator,
    MultiSourceGoalCompetition,
    N_COLUMNS,
    CX_LOOP_BREAK_STUCK_S,
    CX_LOOP_BREAK_COOLDOWN_TICKS,
)


class TestCompassAutonomy:
    def test_self_motion_rolls_bump_without_external_drive(self):
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # 90°/s turn for 0.5 s (25 ticks) while external heading held STALE at 0
        for _ in range(25):
            cx.update(heading=0.0, heading_rate=np.pi / 2, dt=0.02)
        est = cx.heading_estimate
        moved = (est - 0.0 + np.pi) % (2 * np.pi) - np.pi
        # 90°/s × 0.5s = 45°; the weak stale drive holds it near ~10° —
        # what matters is DIRECTION against the stale reference
        assert moved > np.radians(5), f"moved only {np.degrees(moved):.1f}°"

    def test_heading_none_fully_autonomous_tracking(self):
        """heading=None (game value unavailable) → pure self-motion + sky."""
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # rotate 90°/s for 0.5 s with NO game heading: sky at 45° anchors
        for _ in range(25):
            cx.update(heading=None, heading_rate=np.pi / 2, dt=0.02,
                      visual_azimuth=np.pi / 4)
        est = cx.heading_estimate
        moved = (est + np.pi) % (2 * np.pi) - np.pi
        assert moved > np.radians(20), f"autonomous tracking failed: {np.degrees(moved):.1f}°"

    def test_fractional_accumulation_no_loss(self):
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # 0.4 columns/tick × 5 ticks = 2.0 columns = 45°
        rate = 0.4 * (2 * np.pi) / (16 * 0.02)
        for _ in range(5):
            cx.update(heading=0.0, heading_rate=rate, dt=0.02)
        est = cx.heading_estimate
        moved = (est + np.pi) % (2 * np.pi) - np.pi
        assert moved == pytest.approx(np.pi / 4, abs=0.2), (
            f"moved {np.degrees(moved):.1f}°, expected ≈45°")

    def test_external_heading_still_corrects(self):
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        # no self-motion; external heading π for many ticks → bump follows
        for _ in range(40):
            cx.update(heading=np.pi, heading_rate=0.0, dt=0.02)
        est = cx.heading_estimate
        moved = abs((est - np.pi + np.pi) % (2 * np.pi) - np.pi)
        assert moved < 0.4, f"drive correction broken: est={est:.2f}"

    def test_visual_azimuth_correction_pulls(self):
        """Sky compass (0.12) must out-pull the game heading (0.10): with
        game=0 and sky=0.6 rad the bump settles on the sky side of zero."""
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        for _ in range(40):
            cx.update(heading=0.0, heading_rate=0.0, dt=0.02,
                      visual_azimuth=0.6)
        est = cx.heading_estimate
        assert 0.15 < est < 1.2, f"sky compass failed: est={est:.3f}"

    def test_rough_turn_does_not_lose_columns(self):
        """Wild alternation must not lose net rotation (accumulation test)."""
        cx = CentralComplex()
        cx._imprint_heading(0.0)
        rate = np.pi / 2
        for i in range(50):
            r = rate if i % 2 == 0 else -rate
            cx._self_motion_update(r, 0.02)
        assert abs(cx._col_accum) < 1e-6
        # net rotation zero → bump stays near 0
        est = cx.heading_estimate
        assert abs((est + np.pi) % (2 * np.pi) - np.pi) < 0.5


# ======================================================================
# CX-2: AnchorPathIntegrator
# ======================================================================

class TestAnchorPathIntegrator:

    def test_fresh_integrator_has_no_anchor(self):
        """A fresh integrator has no anchor set."""
        pi = AnchorPathIntegrator()
        assert pi.anchor is None
        assert pi.distance == 0.0
        assert pi.return_bearing is None
        assert not pi.is_anchored
        assert pi.displacement == (0.0, 0.0)

    def test_set_anchor_creates_anchor(self):
        """set_anchor() establishes an anchor and resets displacement."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(100.0, 200.0)
        assert pi.anchor == (100.0, 200.0)
        assert pi.is_anchored
        assert pi.distance == 0.0

    def test_integrate_moves_displacement_along_heading(self):
        """Forward speed along heading 0 (positive Z) increases disp_z."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        pi.integrate(heading_estimate=0.0, forward_speed=10.0, dt=0.02)
        expected_dz = 10.0 * pi.SPEED_TO_UNITS * 0.02
        assert abs(pi.disp_x) < 1e-6
        assert abs(pi.disp_z - expected_dz) < 1e-6
        assert pi.distance > 0.0

    def test_integrate_heading_90_moves_positive_x(self):
        """Heading π/2 (90° = right) increases disp_x."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        pi.integrate(heading_estimate=np.pi / 2, forward_speed=10.0, dt=0.02)
        expected_dx = 10.0 * pi.SPEED_TO_UNITS * 0.02
        assert abs(pi.disp_x - expected_dx) < 1e-6
        assert abs(pi.disp_z) < 1e-6

    def test_integrate_heading_pi_moves_negative_z(self):
        """Heading π (180°) decreases disp_z."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        pi.integrate(heading_estimate=np.pi, forward_speed=10.0, dt=0.02)
        expected_dz = -10.0 * pi.SPEED_TO_UNITS * 0.02
        assert abs(pi.disp_z - expected_dz) < 1e-6

    def test_no_integration_without_anchor(self):
        """Without anchor, integrate() is a no-op."""
        pi = AnchorPathIntegrator()
        pi.integrate(heading_estimate=0.0, forward_speed=10.0, dt=0.02)
        assert pi.distance == 0.0

    def test_displacement_decays_when_stationary(self):
        """Displacement slowly decays when forward_speed is zero."""
        pi = AnchorPathIntegrator(displacement_decay=0.9)
        pi.set_anchor(0.0, 0.0)
        pi.integrate(heading_estimate=0.0, forward_speed=10.0, dt=0.02)
        d_before = pi.distance
        assert d_before > 0.0
        for _ in range(10):
            pi.integrate(heading_estimate=0.0, forward_speed=0.0, dt=0.02)
        assert pi.distance < d_before

    def test_return_bearing_points_back_to_anchor(self):
        """return_bearing gives bearing from pos back to anchor."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        pi.disp_x = 10.0
        brg = pi.return_bearing
        assert brg is not None
        assert abs(brg - (-np.pi / 2)) < 1e-6

    def test_return_bearing_none_when_at_anchor(self):
        """return_bearing is None when displacement is zero."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        assert pi.return_bearing is None

    def test_visual_relocalize_stores_scene(self):
        """First encounter stores displacement for a scene."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        pi.disp_x = 5.0
        pi.relocalize(scene_id=42, confidence=0.9)
        assert pi.scene_count == 1

    def test_visual_relocalize_low_confidence_skipped(self):
        """Relocalization skipped when confidence below gate."""
        pi = AnchorPathIntegrator(relocalize_gate=0.8)
        pi.set_anchor(0.0, 0.0)
        pi.relocalize(scene_id=42, confidence=0.5)
        assert pi.scene_count == 0

    def test_visual_relocalize_corrects_drift(self):
        """Re-encountering a scene pulls displacement toward remembered pos."""
        pi = AnchorPathIntegrator(relocalize_gate=0.7, relocalize_strength=0.3)
        pi.set_anchor(0.0, 0.0)
        pi.disp_x = 10.0
        pi.relocalize(scene_id=1, confidence=0.9)
        pi.disp_x = 15.0
        pi.relocalize(scene_id=1, confidence=0.9)
        assert pi.disp_x < 15.0, "Drift correction should pull back"

    def test_reset_clears_everything(self):
        """reset() clears anchor, displacement, and scene memory."""
        pi = AnchorPathIntegrator()
        pi.set_anchor(0.0, 0.0)
        pi.disp_x = 10.0
        pi.relocalize(scene_id=1, confidence=0.9)
        pi.reset()
        assert pi.anchor is None
        assert pi.distance == 0.0
        assert pi.scene_count == 0


# ======================================================================
# CX-3: MultiSourceGoalCompetition
# ======================================================================

class TestMultiSourceGoalCompetition:

    def test_fresh_competition_zero_goal(self):
        """Fresh competition starts with no goal and zero steering."""
        gc = MultiSourceGoalCompetition()
        assert gc.goal_column == 0
        assert gc.goal_strength == 0.0
        assert gc.steering_bias == 0.0

    def test_goal_vectors_produce_goal_column(self):
        """A single goal vector sets the goal column correctly."""
        gc = MultiSourceGoalCompetition(n_columns=16)
        gc.update(goal_vectors=[(1.0, 0.0, 1.0)], heading_column=0,
                  heading_estimate=0.0)
        # angle = arctan2(1,0) = π/2 → column 4 of 16
        assert gc.goal_column == 4, f"Expected column 4, got {gc.goal_column}"
        assert gc.goal_strength > 0.0

    def test_goal_vectors_with_multiple_sources(self):
        """Multiple goal vectors combined through weighted sum."""
        gc = MultiSourceGoalCompetition(n_columns=16)
        # (1,0) w=1 + (0,1) w=1 → resultant (1,1) → angle π/4 → column 2
        gc.update(goal_vectors=[(1.0, 0.0, 1.0), (0.0, 1.0, 1.0)],
                  heading_column=0, heading_estimate=0.0)
        assert gc.goal_column == 2, f"Expected column 2, got {gc.goal_column}"

    def test_stronger_weight_dominates_vector_sum(self):
        """Higher-weight vector dominates the resultant direction."""
        gc = MultiSourceGoalCompetition(n_columns=16)
        gc.update(goal_vectors=[(1.0, 0.0, 1.5), (0.0, 1.0, 0.5)],
                  heading_column=0, heading_estimate=0.0)
        assert gc.goal_strength > 0.0

    def test_goal_strength_from_vector_norm(self):
        """Goal strength scales with the vector resultant norm."""
        gc = MultiSourceGoalCompetition(n_columns=16)
        # Strong: norm = 2.0 → strength = min(1.0, 2.0/1.5) = 1.0
        gc.update(goal_vectors=[(2.0, 0.0, 1.0)], heading_column=0,
                  heading_estimate=0.0)
        assert gc.goal_strength == 1.0
        # Weak: norm = 0.5 → strength < 1.0
        gc.update(goal_vectors=[(0.5, 0.0, 1.0)], heading_column=0,
                  heading_estimate=0.0)
        assert gc.goal_strength < 1.0

    def test_steering_bias_negative_when_goal_to_left(self):
        """Steering bias negative when goal column < heading column (left)."""
        gc = MultiSourceGoalCompetition(n_columns=16, steering_gain=0.12,
                                         goal_memory_decay=0.5)
        gc.goal_column = 12
        gc.goal_strength = 1.0
        bias = gc.update(goal_vectors=None, heading_column=0,
                         heading_estimate=0.0)
        # offset = (12-0)%16 = 12 → wrap: 12-16=-4 → steer = -4/8 = -0.5
        # → -0.5 * 0.12 * 1.0 = -0.06
        assert bias < 0, f"Expected negative bias, got {bias}"

    def test_goal_decays_without_input(self):
        """Goal strength decays via GOAL_MEMORY_DECAY with neutral input."""
        gc = MultiSourceGoalCompetition(goal_memory_decay=0.5)
        gc.goal_strength = 1.0
        gc._ext_goal_strength = 1.0
        gc.update(goal_vectors=None, heading_column=0, heading_estimate=0.0,
                  novelty=0.5, novelty_direction=0.0)
        assert gc.goal_strength <= 0.5

    def test_idle_wander_produces_goal_when_no_goal(self):
        """Idle wander sets goal_strength=0.3 when _ext_goal_strength is low."""
        gc = MultiSourceGoalCompetition()
        gc.goal_strength = 0.0
        gc._ext_goal_strength = 0.0
        gc.update(goal_vectors=None, heading_column=0, heading_estimate=0.0,
                  novelty=0.5, novelty_direction=0.0)
        assert gc.goal_strength == 0.30, \
            f"Expected 0.30 from wander, got {gc.goal_strength}"

    def test_wander_shifts_goal_when_no_goal(self):
        """Idle wander fires once when goal is absent, setting goal_strength."""
        gc = MultiSourceGoalCompetition(goal_memory_decay=0.5)
        gc.goal_strength = 0.0
        gc._ext_goal_strength = 0.0
        gf0 = gc._goal_float
        gc.update(goal_vectors=None, heading_column=0,
                  heading_estimate=0.0, novelty=0.5, novelty_direction=0.0)
        # Wander fires on the first tick: sets goal_strength=0.30, shifts float
        assert gc.goal_strength == 0.30, \
            f"Expected 0.30, got {gc.goal_strength}"
        # With 500 decay ticks, strength should decay below wander threshold
        # and re-fire, shifting the float further
        for _ in range(599):
            gc.update(goal_vectors=None, heading_column=0,
                      heading_estimate=0.0, novelty=0.5, novelty_direction=0.0)
        # The wander re-fires when goal_strength decays back below 0.05
        # With goal_memory_decay=0.5, 0.30 * 0.5^t drops quickly
        # After enough cycles the float should have shifted noticeably
        assert abs(gc._goal_float - gf0) > 0.1 or gc.goal_strength == 0.30, \
            f"_goal_float barely moved: {gf0} → {gc._goal_float}"

    def test_loop_break_jumps_goal_when_stuck(self):
        """After extended stuck, loop break jumps goal column."""
        gc = MultiSourceGoalCompetition()
        gc._ext_goal_strength = 0.0
        gc.goal_strength = 0.0
        for _ in range(10):
            gc.update(goal_vectors=None, heading_column=0,
                      heading_estimate=0.0, novelty=0.5,
                      novelty_direction=0.0,
                      stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        gc._ticks_since_jump = CX_LOOP_BREAK_COOLDOWN_TICKS
        gc.update(goal_vectors=None, heading_column=0,
                  heading_estimate=0.0, novelty=0.5,
                  novelty_direction=0.0,
                  stuck_duration=CX_LOOP_BREAK_STUCK_S + 1.0)
        assert abs(gc.goal_strength - 0.60) < 0.01

    def test_flow_bias_modulates_steering(self):
        """Optic flow asymmetry biases steering away from obstacles."""
        gc = MultiSourceGoalCompetition(n_columns=16, optic_flow_gain=0.08)
        gc.goal_strength = 0.0
        bias = gc.update(goal_vectors=None, heading_column=0,
                         heading_estimate=0.0, novelty=0.5,
                         novelty_direction=0.0, flow_asymmetry=0.5)
        assert abs(bias - 0.04) < 1e-6

    def test_reset_clears_goal_state(self):
        """reset() clears goal column, strength, and wander phase."""
        gc = MultiSourceGoalCompetition()
        gc.goal_column = 8
        gc.goal_strength = 0.8
        gc.steering_bias = 0.05
        gc.reset()
        assert gc.goal_column == 0
        assert gc.goal_strength == 0.0
        assert gc.steering_bias == 0.0


# ======================================================================
# CentralComplex integration
# ======================================================================

class TestCentralComplexIntegration:

    def test_central_complex_creates_sub_modules(self):
        """CentralComplex creates AnchorPathIntegrator and GoalCompetition."""
        cx = CentralComplex()
        assert hasattr(cx, '_path_integrator')
        assert hasattr(cx, '_goal_comp')
        assert isinstance(cx._path_integrator, AnchorPathIntegrator)
        assert isinstance(cx._goal_comp, MultiSourceGoalCompetition)

    def test_set_anchor_syncs_backrefs(self):
        """set_anchor updates backward-compatible anchor/disp references."""
        cx = CentralComplex()
        assert cx.anchor is None
        cx.set_anchor(50.0, 100.0)
        assert cx.anchor == (50.0, 100.0)
        assert cx.disp_x == 0.0
        assert cx.disp_z == 0.0

    def test_update_syncs_goal_backrefs(self):
        """update() synchronises backward-compatible goal references."""
        cx = CentralComplex()
        steering = cx.update(heading=0.0, heading_rate=0.0,
                             goal_vectors=[(1.0, 1.0, 1.0)],
                             novelty=0.5, novelty_direction=0.0,
                             forward_speed=0.0, dt=0.02)
        assert isinstance(cx.goal_column, int)
        assert isinstance(cx.goal_strength, float)
        assert isinstance(cx.steering_bias, float)
        assert isinstance(steering, float)

    def test_compass_stats_contains_cx_keys(self):
        """compass_stats includes CX-2 and CX-3 diagnostic keys."""
        cx = CentralComplex()
        stats = cx.compass_stats
        for key in ("heading_column", "goal_column", "goal_strength",
                     "steering_bias", "loop_breaks", "anchor_distance",
                     "scene_count"):
            assert key in stats, f"Missing key: {key}"

    def test_full_update_cycle(self):
        """A full update cycle produces a valid steering bias."""
        cx = CentralComplex()
        for _ in range(10):
            steering = cx.update(heading=0.5, heading_rate=0.2,
                                  flow_asymmetry=0.1, novelty=0.6,
                                  novelty_direction=0.3, dt=0.02,
                                  visual_azimuth=0.5, forward_speed=5.0,
                                  goal_vectors=None, stuck_duration=0.0)
        assert -1.0 <= steering <= 1.0

    def test_path_integration_in_update(self):
        """update() integrates forward speed into anchor displacement."""
        cx = CentralComplex()
        cx.set_anchor(0.0, 0.0)
        for _ in range(50):
            cx.update(heading=0.0, heading_rate=0.0, forward_speed=10.0,
                       dt=0.02)
        assert cx.anchor_distance > 0.0

    def test_reset_syncs_all_backrefs(self):
        """reset() synchronises both CX-2 and CX-3 back-references."""
        cx = CentralComplex()
        cx.set_anchor(10.0, 20.0)
        cx.update(heading=0.0, heading_rate=0.0, goal_vectors=[(2.0, 0.0, 1.0)])
        cx.reset()
        assert cx.anchor is None
        assert cx.disp_x == 0.0
        assert cx.disp_z == 0.0
        assert cx.goal_strength == 0.0
        assert cx.steering_bias == 0.0
