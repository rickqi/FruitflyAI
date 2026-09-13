"""Regression tests for Mushroom Body associative learning (P3).

Tests cover:
- MushroomBody initialization and architecture
- Kenyon Cell sparse coding (top-5% activation)
- MBON integration (tanh-clipped outputs)
- Three-factor Hebbian plasticity (eligibility trace, dopamine gating)
- Weight clipping and saturation prevention
- Reset behavior
- Integration with FlyModel encoder
"""
import numpy as np
import pytest

from fly64.mushroom_body import MushroomBody, N_KENYON_CELLS, N_MBONS, KC_SPARSITY


# ══════════════════════════════════════════════════════════════════
# Basic architecture
# ══════════════════════════════════════════════════════════════════

class TestMushroomBodyInit:
    """MushroomBody initialization and architecture."""

    def test_default_architecture(self):
        mb = MushroomBody()
        assert mb.n_kc == N_KENYON_CELLS  # 2000
        assert mb.n_mbon == N_MBONS       # 5
        assert mb.sparsity == KC_SPARSITY  # 0.05
        assert mb.weights.shape == (N_KENYON_CELLS, N_MBONS)
        assert mb.W_kc.shape == (N_KENYON_CELLS, 128)

    def test_weight_initialisation(self):
        mb = MushroomBody()
        # Weights initialised near-zero with small variance
        assert abs(mb.weights.mean()) < 0.02
        assert mb.weights.std() < 0.03
        # All within [-1, 1]
        assert mb.weights.min() >= -1.0
        assert mb.weights.max() <= 1.0

    def test_initial_state(self):
        mb = MushroomBody()
        assert np.all(mb.kc_activity == 0.0)
        assert np.all(mb.mbon_outputs == 0.0)
        assert np.all(mb.eligibility == 0.0)
        assert mb.dopamine == 0.0
        assert mb.dopamine_raw == 0.0
        assert mb._plasticity_counter == 0
        assert mb.assoc_count == 0
        assert mb.learning_enabled is True

    def test_mbon_names(self):
        mb = MushroomBody()
        expected = ["forward_bias", "left_bias", "right_bias",
                    "jump_bias", "explore_bias"]
        assert list(mb.MBON_NAMES) == expected


# ══════════════════════════════════════════════════════════════════
# Kenyon Cell sparse coding
# ══════════════════════════════════════════════════════════════════

class TestKCSparseCoding:
    """Kenyon Cell encoding with top-k sparsification."""

    def test_scene_sig_projection(self):
        mb = MushroomBody()
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        _ = mb.encode(scene_sig)
        # KC activity should be sparse binary
        assert mb.kc_activity.dtype == np.float32
        assert np.all(np.isin(mb.kc_activity, [0.0, 1.0]))

    def test_top_5_percent_activation(self):
        mb = MushroomBody()
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        _ = mb.encode(scene_sig)
        # Exactly ~5% should be active (100 out of 2000)
        n_active = int(mb.kc_activity.sum())
        expected = max(1, int(N_KENYON_CELLS * KC_SPARSITY))
        assert n_active == expected, f"Expected {expected} active KCs, got {n_active}"

    def test_different_scenes_different_kc(self):
        mb = MushroomBody()
        sig1 = np.random.normal(0, 0.1, 128).astype(np.float32)
        sig2 = np.random.normal(0.3, 0.1, 128).astype(np.float32)

        mb.encode(sig1)
        kc1 = mb.kc_activity.copy()
        mb.encode(sig2)
        kc2 = mb.kc_activity.copy()

        # Different scenes should activate different KCs
        overlap = int((kc1 * kc2).sum())
        assert overlap < 50, f"KC overlap too high: {overlap} shared"

    def test_same_scene_same_kc(self):
        mb = MushroomBody()
        rng = np.random.default_rng(42)
        sig = rng.normal(0, 0.1, 128).astype(np.float32)

        mb.encode(sig)
        kc1 = mb.kc_activity.copy()
        mb.encode(sig)
        kc2 = mb.kc_activity.copy()

        # Same scene should activate the same KCs (deterministic)
        assert np.all(kc1 == kc2)

    def test_kc_sparsity_property(self):
        mb = MushroomBody()
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        _ = mb.encode(scene_sig)
        assert abs(mb.kc_sparsity_actual - KC_SPARSITY) < 0.001


# ══════════════════════════════════════════════════════════════════
# MBON integration
# ══════════════════════════════════════════════════════════════════

class TestMBONIntegration:
    """MBON output computation and tanh-clipping."""

    def test_mbon_output_shape(self):
        mb = MushroomBody()
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        out = mb.encode(scene_sig)
        assert out.shape == (N_MBONS,)
        assert out.dtype == np.float32

    def test_mbon_outputs_clipped(self):
        mb = MushroomBody()
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        out = mb.encode(scene_sig)
        # Tanh → outputs in [-1, 1]
        assert np.all(out >= -1.0) and np.all(out <= 1.0)

    def test_mbon_initial_near_zero(self):
        """Initially MBON outputs should be near zero (unlearned)."""
        mb = MushroomBody()
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        out = mb.encode(scene_sig)
        # With ±0.05 uniform init, small bias is expected. Check magnitude is reasonable.
        assert np.all(np.abs(out) < 0.6), f"MBON initial outputs too large: {out}"


# ══════════════════════════════════════════════════════════════════
# Dopamine signal
# ══════════════════════════════════════════════════════════════════

class TestDopamineSignal:
    """Dopamine signal setting, smoothing, and plasticity window."""

    def test_dopamine_smoothing(self):
        mb = MushroomBody()
        mb.set_dopamine(1.0)
        # After α=0.3 smoothing: 0.3*1.0 + 0.7*0.0 = 0.3
        assert mb.dopamine == pytest.approx(0.3, abs=0.01)

    def test_dopamine_accumulation(self):
        mb = MushroomBody()
        mb.set_dopamine(1.0)   # 0.3
        mb.set_dopamine(1.0)   # 0.3 + 0.7 * 0.3 = 0.51
        assert mb.dopamine > 0.4

    def test_plasticity_window_triggers(self):
        mb = MushroomBody()
        mb.set_dopamine(0.0)   # no trigger
        assert mb._plasticity_counter == 0

        mb.set_dopamine(0.8)   # >= 0.3 threshold
        assert mb._plasticity_counter > 0
        assert mb.assoc_count == 1

    def test_dopamine_history(self):
        mb = MushroomBody()
        for _ in range(10):
            mb.set_dopamine(0.5)
        assert len(mb._dopamine_history) >= 5

    def test_negative_dopamine(self):
        mb = MushroomBody()
        mb.set_dopamine(-0.8)
        assert mb.dopamine < 0
        assert mb._plasticity_counter > 0  # |dopamine| > threshold


# ══════════════════════════════════════════════════════════════════
# Three-factor Hebbian plasticity
# ══════════════════════════════════════════════════════════════════

class TestPlasticity:
    """Three-factor learning rule and weight changes."""

    def test_no_learning_when_disabled(self):
        mb = MushroomBody()
        mb.learning_enabled = False
        scene_sig = np.random.normal(0, 0.1, 128).astype(np.float32)
        _ = mb.encode(scene_sig)
        mb.set_dopamine(0.9)
        n = mb.update_weights()
        assert n == 0  # no changes

    def test_weights_change_after_learning(self):
        mb = MushroomBody()
        scene_sig = np.random.normal(0.5, 0.1, 128).astype(np.float32)

        w_before = mb.weights.copy()
        for _ in range(5):
            _ = mb.encode(scene_sig)
            mb.set_dopamine(0.8)
            mb.update_weights()

        w_after = mb.weights
        diff = np.abs(w_after - w_before).max()
        assert diff > 0, "Weights should change after learning"

    def test_only_active_synapses_change(self):
        """Only synapses with non-zero eligibility are modified."""
        mb = MushroomBody()
        scene_sig = np.random.normal(0.5, 0.1, 128).astype(np.float32)

        w_before = mb.weights.copy()
        _ = mb.encode(scene_sig)
        mb.set_dopamine(0.8)
        mb.update_weights()
        w_after = mb.weights

        # Changes should be sparse — only KC-active entries
        changed = np.abs(w_after - w_before) > 1e-8
        kc_active = mb.kc_activity > 0
        # All changes should be in rows where KC was active
        changed_rows = np.where(changed.any(axis=1))[0]
        for r in changed_rows:
            assert kc_active[r], f"Weight changed for inactive KC {r}"

    def test_weight_clipping(self):
        """Weights should stay within [-1, 1]."""
        mb = MushroomBody()
        # Set one weight to near-bound and reinforce
        mb.weights[0, 0] = 0.95
        # Force a strong scene to activate KC 0
        scene = np.zeros(128, dtype=np.float32)
        scene[0] = 10.0  # strong activation for KC 0

        for _ in range(20):
            _ = mb.encode(scene)
            mb.set_dopamine(0.9)
            mb.update_weights()

        assert mb.weights[0, 0] >= -1.0
        assert mb.weights[0, 0] <= 1.0

    def test_negative_dopamine_weakens(self):
        mb = MushroomBody()
        # Use a strong, consistent scene to produce measurable weight change
        sig = np.ones(128, dtype=np.float32) * 0.5

        w_before = mb.weights.copy()
        n_iter = 20
        for i in range(n_iter):
            mb.encode(sig)
            mb.set_dopamine(-0.8)  # triggers plasticity window
            mb.update_weights()
        w_after = mb.weights

        diff = w_after - w_before
        active_entries = np.abs(w_before) > 1e-8
        if active_entries.any():
            mean_change = diff[active_entries].mean()
            assert mean_change < 0, (
                f"Negative dopamine should decrease weights, got {mean_change:.6f}")

    def test_positive_dopamine_strengthens(self):
        mb = MushroomBody()
        sig = np.ones(128, dtype=np.float32) * 0.5

        w_before = mb.weights.copy()
        for i in range(20):
            mb.encode(sig)
            mb.set_dopamine(0.8)
            mb.update_weights()
        w_after = mb.weights

        diff = w_after - w_before
        active_entries = np.abs(w_before) > 1e-8
        if active_entries.any():
            mean_change = diff[active_entries].mean()
            assert mean_change > 0, (
                f"Positive dopamine should increase weights, got {mean_change:.6f}")


# ══════════════════════════════════════════════════════════════════
# Reset behavior
# ══════════════════════════════════════════════════════════════════

class TestReset:
    """Reset methods preserve or reset state as expected."""

    def test_reset_clears_state_keeps_weights(self):
        mb = MushroomBody()
        sig = np.random.normal(0.5, 0.1, 128).astype(np.float32)
        for _ in range(5):
            _ = mb.encode(sig)
            mb.set_dopamine(0.8)
            mb.update_weights()

        w_before_reset = mb.weights.copy()
        mb.reset()

        assert np.all(mb.kc_activity == 0.0)
        assert np.all(mb.mbon_outputs == 0.0)
        assert np.all(mb.eligibility == 0.0)
        assert mb.dopamine == 0.0
        assert mb._plasticity_counter == 0
        # Weights preserved
        assert np.allclose(mb.weights, w_before_reset)

    def test_reset_weights_reinitializes(self):
        mb = MushroomBody()
        sig = np.random.normal(0.5, 0.1, 128).astype(np.float32)
        for _ in range(5):
            _ = mb.encode(sig)
            mb.set_dopamine(0.8)
            mb.update_weights()

        w_before = mb.weights.copy()
        mb.reset_weights()
        w_after = mb.weights

        # Weights should be different (reinitialized)
        assert not np.allclose(w_before, w_after)
        assert mb.assoc_count == 0
        # Still within bounds
        assert w_after.min() >= -1.0
        assert w_after.max() <= 1.0


# ══════════════════════════════════════════════════════════════════
# Diagnostic properties
# ══════════════════════════════════════════════════════════════════

class TestDiagnostics:
    """Diagnostic properties and stats."""

    def test_dopamine_stats(self):
        mb = MushroomBody()
        mb.set_dopamine(0.6)
        stats = mb.dopamine_stats
        assert "dopamine" in stats
        assert "dopamine_raw" in stats
        assert "plasticity_active" in stats
        assert "assoc_count" in stats

    def test_weight_stats(self):
        mb = MushroomBody()
        stats = mb.weight_stats
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats
        assert "n_positive" in stats
        assert "n_negative" in stats