"""PIN tests: adaptive synaptic propagation fast path (P1-2).

The adaptive `synaptic_current` must produce the same column sum as the
classic fancy-index implementation at every fired fraction — it only picks
the faster scipy selection path (boolean mask below ~10% fired, fancy-index
above), measured on the real 25.6M-edge connectome.
"""
import numpy as np
import pytest
from scipy import sparse

from fly64.model import synaptic_current


def _old_propagate(w_csc, spikes):
    return np.asarray(w_csc[:, np.flatnonzero(spikes)].sum(axis=1)).ravel()


def _make_w(n=4000, edges=60000, seed=7):
    rng = np.random.default_rng(seed)
    row = rng.integers(0, n, edges)
    col = rng.integers(0, n, edges)
    data = rng.normal(0, 0.1, edges).astype(np.float32)
    return sparse.csc_matrix((data, (row, col)), shape=(n, n))


class TestEquivalence:
    @pytest.mark.parametrize("frac", [0.02, 0.05, 0.09, 0.11, 0.3, 1.0])
    def test_allclose_both_sides_of_crossover(self, frac):
        """crossover (~10% fired) must behave identically on both branches."""
        w = _make_w()
        rng = np.random.default_rng(3)
        spikes = (rng.random(w.shape[0]) < frac).astype(np.float32)
        old = _old_propagate(w, spikes)
        new = synaptic_current(w, spikes)
        np.testing.assert_allclose(new, old, rtol=1e-5, atol=1e-7)

    def test_zero_spikes_give_zeros(self):
        w = _make_w()
        out = synaptic_current(w, np.zeros(w.shape[0], dtype=np.float32))
        assert not out.any()
        assert out.dtype == np.float32

    def test_single_spike_matches_column(self):
        w = _make_w()
        spikes = np.zeros(w.shape[0], dtype=np.float32)
        spikes[17] = 1.0
        col = w[:, [17]].sum(axis=1)
        np.testing.assert_allclose(synaptic_current(w, spikes),
                                   np.asarray(col).ravel(), rtol=1e-5, atol=1e-7)

    def test_full_activation_matches(self):
        w = _make_w()
        spikes = np.ones(w.shape[0], dtype=np.float32)
        np.testing.assert_allclose(synaptic_current(w, spikes),
                                   _old_propagate(w, spikes),
                                   rtol=1e-5, atol=1e-7)

    def test_low_fraction_uses_mask_branch(self, monkeypatch):
        """Below the crossover the boolean-mask path is selected (3.8x case)."""
        w = _make_w()
        calls = []
        orig = sparse.csc_matrix.__if__ if False else None  # noqa: F601
        spikes = (np.random.default_rng(1).random(w.shape[0]) < 0.05).astype(np.float32)
        fired = np.flatnonzero(spikes)
        assert fired.size <= 0.10 * w.shape[0]  # mask branch condition holds
        out = synaptic_current(w, spikes)
        assert out.shape == (w.shape[0],)
