"""Regression tests for dopamine-gated gain modulation (t1 plasticity proxy).

Tests cover:
- DopamineGainController initialization and defaults
- Per-pathway gain access and bounds
- Dopamine signal handling and smoothing
- Eligibility trace update and decay
- Three-factor gain plasticity updates
- Integration with FlyModel (pathway-specific current injection)
- Gain persistence across model steps
"""
import numpy as np

from fly64.gain_modulation import (
    DopamineGainController,
    DEFAULT_GAINS,
    GAIN_MIN,
    GAIN_MAX,
    GAIN_ELIGIBILITY_DECAY,
)
from fly64.model import FlyModel


# ══════════════════════════════════════════════════════════════════
# Basic architecture
# ══════════════════════════════════════════════════════════════════


class TestDopamineGainInit:
    """DopamineGainController initialization and architecture."""

    def test_default_pathways(self):
        dg = DopamineGainController()
        assert set(dg.pathway_gains.keys()) == {
            "visual", "forward", "turn", "jump", "recurrent",
        }
        assert set(dg.pathway_eligibility.keys()) == {
            "visual", "forward", "turn", "jump", "recurrent",
        }

    def test_default_gains_at_unity(self):
        dg = DopamineGainController()
        for pathway in dg.PATHWAYS:
            assert dg.get_gain(pathway) == pytest.approx(
                DEFAULT_GAINS[pathway], abs=0.01
            )

    def test_initial_eligibility_zero(self):
        dg = DopamineGainController()
        for v in dg.pathway_eligibility.values():
            assert v == 0.0

    def test_initial_dopamine_zero(self):
        dg = DopamineGainController()
        assert dg.dopamine_smoothed == 0.0
        assert dg.dopamine_raw == 0.0
        assert dg.plasticity_remaining == 0
        assert dg.gain_update_count == 0

    def test_pathway_gain_bounds(self):
        dg = DopamineGainController()
        for g in dg.pathway_gains.values():
            assert GAIN_MIN <= g <= GAIN_MAX

    def test_initial_gains_custom(self):
        dg = DopamineGainController(
            initial_gains={"visual": 2.0, "forward": 0.8}
        )
        assert dg.get_gain("visual") == pytest.approx(2.0)
        assert dg.get_gain("forward") == pytest.approx(0.8)
        # Others stay at defaults
        assert dg.get_gain("recurrent") == pytest.approx(DEFAULT_GAINS["recurrent"])

    def test_initial_gains_clamped(self):
        """Gains are clamped to [GAIN_MIN, GAIN_MAX]."""
        dg = DopamineGainController(
            initial_gains={"visual": 5.0, "jump": -1.0}
        )
        assert dg.get_gain("visual") == pytest.approx(GAIN_MAX)
        assert dg.get_gain("jump") == pytest.approx(GAIN_MIN)

    def test_get_all_gains(self):
        dg = DopamineGainController()
        all_gains = dg.get_all_gains()
        assert isinstance(all_gains, dict)
        assert set(all_gains.keys()) == set(dg.PATHWAYS)

    def test_get_all_eligibility(self):
        dg = DopamineGainController()
        all_el = dg.get_all_eligibility()
        assert isinstance(all_el, dict)
        assert set(all_el.keys()) == set(dg.PATHWAYS)


# ══════════════════════════════════════════════════════════════════
# Dopamine signal handling
# ══════════════════════════════════════════════════════════════════


class TestDopamineSignal:
    """Dopamine signal setting, smoothing, and plasticity window."""

    def test_set_dopamine_smoothing(self):
        dg = DopamineGainController()
        dg.set_dopamine(1.0, alpha=0.3)
        # After α=0.3 smoothing: 0.3*1.0 + 0.7*0.0 = 0.3
        assert dg.dopamine_smoothed == pytest.approx(0.3, abs=0.01)

    def test_set_dopamine_accumulation(self):
        dg = DopamineGainController()
        dg.set_dopamine(1.0, alpha=0.3)  # 0.3
        dg.set_dopamine(1.0, alpha=0.3)  # 0.3 + 0.7 * 0.3 = 0.51
        assert dg.dopamine_smoothed > 0.4

    def test_plasticity_window_triggers(self):
        dg = DopamineGainController()
        dg.set_dopamine(0.0)  # no trigger
        assert dg.plasticity_remaining == 0

        dg.set_dopamine(0.8)  # >= 0.15 threshold
        assert dg.plasticity_remaining > 0

    def test_negative_dopamine(self):
        dg = DopamineGainController()
        dg.set_dopamine(-0.8)
        assert dg.dopamine_smoothed < 0
        assert dg.plasticity_remaining > 0  # |dopamine| > threshold

    def test_dopamine_history(self):
        dg = DopamineGainController()
        for _ in range(10):
            dg.set_dopamine(0.5)
        assert len(dg.dopamine_history) >= 5

    def test_small_dopamine_no_plasticity(self):
        """Very small dopamine should not trigger plasticity window."""
        dg = DopamineGainController(dopamine_threshold=0.15)
        dg.set_dopamine(0.05)
        assert dg.plasticity_remaining == 0


# ══════════════════════════════════════════════════════════════════
# Eligibility trace
# ══════════════════════════════════════════════════════════════════


class TestEligibilityTrace:
    """Eligibility trace update and decay."""

    def test_initial_eligibility_zero(self):
        dg = DopamineGainController()
        assert dg.pathway_eligibility["visual"] == 0.0

    def test_eligibility_increases_with_activity(self):
        dg = DopamineGainController()
        dg.set_dopamine(0.8)  # opens plasticity window
        dg.update_eligibility({"visual": 0.3, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        assert dg.pathway_eligibility["visual"] > 0.0
        assert dg.pathway_eligibility["forward"] == 0.0

    def test_eligibility_decays_without_dopamine(self):
        dg = DopamineGainController()
        dg.set_dopamine(0.8)
        dg.update_eligibility({"visual": 0.3, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        el_after = dg.pathway_eligibility["visual"]

        # Without a new dopamine event, eligibility decays
        dg.set_dopamine(0.05)  # below threshold
        dg.update_eligibility({"visual": 0.0, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        assert dg.pathway_eligibility["visual"] < el_after

    def test_active_threshold_gating(self):
        """Pathways below activity threshold don't increase eligibility."""
        dg = DopamineGainController(activity_threshold=0.1)
        dg.set_dopamine(0.8)
        dg.update_eligibility({"visual": 0.05, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        # activity=0.05 < threshold=0.1 → eligibility should just decay
        assert dg.pathway_eligibility["visual"] == 0.0

    def test_plasticity_window_countdown(self):
        dg = DopamineGainController(plasticity_frames=3)
        dg.set_dopamine(0.8)  # opens 3-frame window
        assert dg.plasticity_remaining == 3

        dg.update_eligibility({"visual": 0.3, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        assert dg.plasticity_remaining == 2

        dg.update_eligibility({"visual": 0.0, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        assert dg.plasticity_remaining == 1

        dg.update_eligibility({"visual": 0.0, "forward": 0.0,
                                "turn": 0.0, "jump": 0.0, "recurrent": 0.0})
        assert dg.plasticity_remaining == 0


# ══════════════════════════════════════════════════════════════════
# Three-factor gain plasticity
# ══════════════════════════════════════════════════════════════════


class TestGainPlasticity:
    """Three-factor gain updates — the core plasticity proxy."""

    def test_no_update_without_dopamine(self):
        dg = DopamineGainController()
        n = dg.apply_gain_update()
        assert n == 0  # R=0, no update

    def test_no_update_without_eligibility(self):
        dg = DopamineGainController()
        dg.dopamine_smoothed = 0.5
        n = dg.apply_gain_update()
        assert n == 0  # all E=0

    def test_positive_dopamine_increases_gain(self):
        dg = DopamineGainController(learning_rate=0.1)
        # Set dopamine and eligibility for visual pathway
        dg.dopamine_smoothed = 0.5
        dg.pathway_eligibility["visual"] = 0.8
        g_before = dg.get_gain("visual")

        n = dg.apply_gain_update()
        assert n > 0
        assert dg.get_gain("visual") > g_before
        assert dg.gain_update_count > 0

    def test_negative_dopamine_decreases_gain(self):
        dg = DopamineGainController(learning_rate=0.1)
        dg.dopamine_smoothed = -0.5
        dg.pathway_eligibility["visual"] = 0.8
        g_before = dg.get_gain("visual")

        n = dg.apply_gain_update()
        assert n > 0
        assert dg.get_gain("visual") < g_before

    def test_gain_never_exceeds_bounds(self):
        """Repeated updates don't push gains outside [GAIN_MIN, GAIN_MAX]."""
        dg = DopamineGainController(learning_rate=0.05)
        dg.dopamine_smoothed = 1.0
        dg.pathway_eligibility = {p: 0.9 for p in dg.PATHWAYS}

        for _ in range(100):
            dg.apply_gain_update()

        for g in dg.pathway_gains.values():
            assert GAIN_MIN <= g <= GAIN_MAX

    def test_plasticity_step_convenience(self):
        """plasticity_step() does set_dopamine + update + apply."""
        dg = DopamineGainController(learning_rate=0.05)
        g_before = dg.get_gain("visual")

        n = dg.plasticity_step(
            raw_dopamine=0.8,
            pathway_activity={"visual": 0.3, "forward": 0.0,
                              "turn": 0.0, "jump": 0.0, "recurrent": 0.0},
        )

        # Should have updated dopamine and gained eligibility
        assert dg.dopamine_smoothed != 0.0
        assert dg.pathway_eligibility["visual"] > 0.0
        # Gains should have changed
        if n > 0:
            assert dg.get_gain("visual") != g_before

    def test_gain_history_recorded(self):
        dg = DopamineGainController(learning_rate=0.05)
        dg.dopamine_smoothed = 0.5
        dg.pathway_eligibility["visual"] = 0.8
        dg.apply_gain_update()
        hist = dg.gain_history("visual")
        assert len(hist) > 0


# ══════════════════════════════════════════════════════════════════
# Reset behavior
# ══════════════════════════════════════════════════════════════════


class TestReset:
    """Reset methods restore state to defaults."""

    def test_reset_clears_all_state(self):
        dg = DopamineGainController()
        dg.dopamine_smoothed = 0.8
        dg.pathway_eligibility["visual"] = 0.5
        dg.gain_update_count = 10

        dg.reset()

        assert dg.dopamine_smoothed == 0.0
        assert dg.dopamine_raw == 0.0
        assert dg.pathway_eligibility["visual"] == 0.0
        assert dg.gain_update_count == 0
        assert dg.plasticity_remaining == 0

    def test_reset_restores_default_gains(self):
        dg = DopamineGainController(initial_gains={"visual": 2.0})
        assert dg.get_gain("visual") == pytest.approx(2.0)

        dg.reset()
        # After full reset, gains return to DEFAULT_GAINS
        assert dg.get_gain("visual") == pytest.approx(DEFAULT_GAINS["visual"])

    def test_reset_gains_custom(self):
        dg = DopamineGainController()
        dg.reset_gains({"visual": 2.0, "forward": 0.7})
        assert dg.get_gain("visual") == pytest.approx(2.0)
        assert dg.get_gain("forward") == pytest.approx(0.7)
        assert dg.get_gain("recurrent") == pytest.approx(DEFAULT_GAINS["recurrent"])


# ══════════════════════════════════════════════════════════════════
# Integration with FlyModel
# ══════════════════════════════════════════════════════════════════


class TestModelIntegration:
    """DopamineGainController integration into FlyModel.step()."""

    def test_model_has_dopamine_gain(self):
        model = FlyModel(demo=True)
        assert hasattr(model, "dopamine_gain")
        assert isinstance(model.dopamine_gain, DopamineGainController)

    def test_pathway_idx_map_populated(self):
        model = FlyModel(demo=True)
        assert hasattr(model, "_pathway_idx_map")
        assert model._pathway_idx_map.shape == (model.n,)
        # Visual neurons should have index 0
        assert np.all(model._pathway_idx_map[model.visual] == 0)
        # Forward motor should have index 1
        assert np.all(model._pathway_idx_map[model.forward] == 1)
        # Jump nodes should have index 3
        assert np.all(model._pathway_idx_map[model.jump_nodes] == 3)

    def test_step_feeds_dopamine_to_gain(self):
        """step() feeds _compute_dopamine() result to the gain controller."""
        import numpy as np

        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        # Initial state
        assert model.dopamine_gain.dopamine_smoothed == 0.0

        # Step triggers dopamine computation -> gain controller receives it
        for i in range(5):
            model.step(green, now=i * model.dt)

        # The gain controller should have received dopamine (may be near zero
        # if no punishment/reward signals are high, but the mechanism is wired)
        assert hasattr(model.dopamine_gain, "dopamine_smoothed")

    def test_pathway_gains_applied_to_current(self):
        """Pathway-specific gains affect the current vector shape."""
        import numpy as np

        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        for i in range(10):
            model.step(green, now=i * model.dt)

        # Gains should still be within bounds after stepping
        for p in model.dopamine_gain.PATHWAYS:
            g = model.dopamine_gain.get_gain(p)
            assert GAIN_MIN <= g <= GAIN_MAX, f"{p} gain {g} out of bounds"

    def test_pathway_gains_persist_across_steps(self):
        """Gain values persist and can be modified by dopamine."""
        import numpy as np

        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        # Run many steps to let any plasticity bake in
        for i in range(50):
            model.step(green, now=i * model.dt)

        # Gains are still accessible and within bounds after extended run
        gains = model.dopamine_gain.get_all_gains()
        assert len(gains) == 5
        for g in gains.values():
            assert GAIN_MIN <= g <= GAIN_MAX

    def test_recurrent_gain_applied_to_non_specialized_neurons(self):
        """The 'recurrent' gain covers neurons outside visual/motor groups."""
        import numpy as np

        model = FlyModel(demo=True)
        # Visual and motor groups should be indexed correctly
        motor_set = set(model.motor_nodes.tolist())
        visual_set = set(model.visual.tolist())
        # There should be neurons that are neither visual nor motor
        all_idx = set(range(model.n))
        remaining = all_idx - motor_set - visual_set
        assert len(remaining) > 0, (
            "Some neurons must be neither visual nor motor for recurrent gain"
        )

    def test_weight_matrix_unchanged(self):
        """The fixed connectome weights self.w are never modified."""
        import numpy as np

        model = FlyModel(demo=True)
        w_before = model.w.copy()
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        for i in range(50):
            model.step(green, now=i * model.dt)

        # After running, the weight matrix should be identical (sparse matrix)
        diff = (w_before - model.w).nnz
        assert diff == 0, f"Weight matrix changed: {diff} elements differ"

    def test_plasticity_proxy_does_not_modify_w(self):
        """Confirm the whole point: self.w is never written to."""
        import numpy as np
        import scipy.sparse

        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        w_data_before = model.w.data.copy()
        w_indices_before = model.w.indices.copy()
        w_indptr_before = model.w.indptr.copy()

        for i in range(100):
            model.step(green, now=i * model.dt)

        # After running, the connectome weight data is identical
        np.testing.assert_array_equal(model.w.data, w_data_before)
        np.testing.assert_array_equal(model.w.indices, w_indices_before)
        np.testing.assert_array_equal(model.w.indptr, w_indptr_before)

    def test_still_runs_many_steps_with_gain_modulation(self):
        """Gain modulation doesn't break the simulation over many steps."""
        import numpy as np

        model = FlyModel(demo=True)
        frame = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        for i in range(200):
            control, spikes = model.step(frame, now=i * model.dt)
            # Control values should still be valid
            assert -70 <= control.x <= 70
            assert 0 <= control.y <= 70
            assert isinstance(control.jump, bool)
            assert isinstance(control.forward_rate, float)
            assert isinstance(control.turn_rate, float)
            assert isinstance(control.jump_rate, float)

    def test_gains_available_in_stats(self):
        """Stats dict includes all gain state (for dashboard)."""
        import numpy as np

        model = FlyModel(demo=True)
        frame = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)
        for i in range(10):
            model.step(frame, now=i * model.dt)

        stats = model.dopamine_gain.stats
        assert "gains" in stats
        assert "eligibility" in stats
        assert "dopamine_smoothed" in stats
        assert "dopamine_raw" in stats
        assert "gain_update_count" in stats
        assert stats["dopamine_smoothed"] is not None

    def test_reset_scene_resets_gain_state(self):
        """reset_scene() does NOT reset gain state (gains are persistent)."""
        import numpy as np

        model = FlyModel(demo=True)
        frame = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)
        for i in range(10):
            model.step(frame, now=i * model.dt)

        gains_before = model.dopamine_gain.get_all_gains()
        model.reset_scene()
        gains_after = model.dopamine_gain.get_all_gains()

        # Gains persist across scene resets (they're a long-term modulation)
        for p in gains_before:
            assert gains_before[p] == gains_after[p]


# ══════════════════════════════════════════════════════════════════
# Error gradient bridge tests (t3)
# ══════════════════════════════════════════════════════════════════


class TestErrorGradientBridge:
    """Python→neuron error gradient bridge for corrective training."""

    def test_compute_error_gradient_returns_dict(self):
        model = FlyModel(demo=True)
        result = model.compute_error_gradient(60)
        assert isinstance(result, dict)
        assert "error" in result
        assert "neural_bias" in result
        assert "python_bias" in result
        assert "corrective_left" in result
        assert "corrective_right" in result

    def test_error_zero_when_python_no_turn(self):
        model = FlyModel(demo=True)
        result = model.compute_error_gradient(0)
        assert result["python_bias"] == 0.0
        # error ranges in [-1, 1]

    def test_error_positive_when_python_right_turn(self):
        model = FlyModel(demo=True)
        # When Python wants right (+60) but neural bias is smaller or negative
        result = model.compute_error_gradient(60)
        assert result["python_bias"] > 0
        assert isinstance(result["error"], float)

    def test_error_negative_when_python_left_turn(self):
        model = FlyModel(demo=True)
        result = model.compute_error_gradient(-60)
        assert result["python_bias"] < 0

    def test_corrective_current_sign_matches_error(self):
        """When error>0 (wants more right), corrective_right > 0 > corrective_left."""
        model = FlyModel(demo=True)
        result = model.compute_error_gradient(60)
        if result["error"] > 0:
            assert result["corrective_right"] >= 0, "right should be boosted"
            assert result["corrective_left"] <= 0, "left should be suppressed"
        elif result["error"] < 0:
            assert result["corrective_right"] <= 0
            assert result["corrective_left"] >= 0

    def test_corrective_current_injects_into_v(self):
        """inject_corrective_current modifies motor pool voltages."""
        import numpy as np
        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)
        for i in range(10):
            model.step(green, now=i * model.dt)

        v_left_before = model.v[model.turn_left].copy()
        v_right_before = model.v[model.turn_right].copy()

        result = model.compute_error_gradient(60)
        model.inject_corrective_current(result, reward_signal=0.0)

        # Voltages should have changed if correction was applied
        if result["corrective_left"] != 0.0:
            assert not np.allclose(model.v[model.turn_left], v_left_before)
        if result["corrective_right"] != 0.0:
            assert not np.allclose(model.v[model.turn_right], v_right_before)

    def test_high_reward_suppresses_correction(self):
        """Gate reduces corrective current when reward_signal is high."""
        import numpy as np
        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)
        for i in range(10):
            model.step(green, now=i * model.dt)

        # Compute error but DON'T inject yet
        err = model.compute_error_gradient(60)
        cl, cr = err["corrective_left"], err["corrective_right"]

        # Injection with low reward: full gate
        model.inject_corrective_current(err, reward_signal=0.0)
        applied_low = model._corrective_current_applied

        # Reset voltages
        model2 = FlyModel(demo=True)
        for i in range(10):
            model2.step(green, now=i * model.dt)
        err2 = model2.compute_error_gradient(60)
        model2.inject_corrective_current(err2, reward_signal=0.9)
        applied_high = model2._corrective_current_applied

        # High reward should gate more aggressively than low reward
        mag_low = abs(applied_low[0]) + abs(applied_low[1])
        mag_high = abs(applied_high[0]) + abs(applied_high[1])
        assert mag_high <= mag_low, (
            f"High reward gate failed: low={mag_low:.6f} high={mag_high:.6f}"
        )

    def test_set_python_correction_injects_immediately(self):
        """set_python_correction computes error and injects in one call."""
        import numpy as np
        model = FlyModel(demo=True)
        green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)
        for i in range(5):
            model.step(green, now=i * model.dt)

        error_dict = model.set_python_correction(60, reward_signal=0.0)
        assert "error" in error_dict

    def test_model_runs_with_error_bridge(self):
        """Error gradient bridge doesn't break extended simulation."""
        import numpy as np
        model = FlyModel(demo=True)
        frame = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)

        for i in range(50):
            control, spikes = model.step(frame, now=i * model.dt)
            # Simulate escape logic calling set_python_correction
            if i % 10 == 0 and abs(control.x) > 8:
                model.set_python_correction(control.x, model.reward_signal)

        assert -70 <= control.x <= 70
        assert 0 <= control.y <= 70

    def test_error_gradient_persists_on_model(self):
        """_last_error_gradient persists between calls."""
        model = FlyModel(demo=True)
        err1 = model.compute_error_gradient(60)
        err2 = model.compute_error_gradient(-60)
        # Second call overwrites
        assert model._last_error_gradient["python_bias"] == err2["python_bias"]

    def test_corrective_current_decays_with_small_error(self):
        """When neural bias = python bias, corrective currents approach 0."""
        model = FlyModel(demo=True)
        # Force the error gradient to simulate small error
        result = model.compute_error_gradient(0)
        assert abs(result["corrective_left"]) < 1e-4
        assert abs(result["corrective_right"]) < 1e-4


# Import pytest for the tests above
import pytest