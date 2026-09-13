"""Dopamine-modulated Mushroom Body associative learning.

Models Drosophila Kenyon Cell sparse coding, MBON value associations,
and dopaminergic (DAN) plasticity following the FlyWire "precise match
feedback" mechanism.  Learning only modifies synapses active at the
time of the dopamine signal — inactive synapses are preserved.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np


# Default architecture
N_KENYON_CELLS = 2000          # ~2,000 KCs in Drosophila
N_MBONS = 5                     # forward, left, right, jump, explore
KC_SPARSITY = 0.05              # top 5% active (100/2000)
LEARNING_RATE = 0.001           # eta — small to prevent catastrophic forgetting
DOPAMINE_THRESHOLD = 0.3        # |dopamine| must exceed this to trigger plasticity
ELIGIBILITY_DECAY = 0.8         # per-frame decay of eligibility trace
DOPAMINE_SMOOTHING = 0.3        # alpha for exponential smoothing of dopamine signal
PLASTICITY_WINDOW = 5           # frames after dopamine pulse that plasticity is active

# Weight bounds for KC->MBON matrix
W_MIN, W_MAX = -1.0, 1.0

# Projection seed for reproducibility (independent of model's main RNG)
KC_PROJECTION_SEED = 64


class MushroomBody:
    """Dopamine-modulated associative learning module.

    Architecture:
      Scene signature (128-dim)
        -> [fixed random projection W_kc: 2000x128]
        -> Kenyon Cells (2000, top-5% sparse, binary)
        -> [plastic KC->MBON weights: 2000x5]
        -> MBON outputs (5 channels)
        ^ modulated by dopamine signal

    Learning rule (three-factor Hebbian):
        Delta_W[i,j] = eta * R(t) * KC[i] * MBON[j] * E[i,j]

    Attributes
    ----------
    kc_activity : np.ndarray, (N_KENYON_CELLS,), float
        Current Kenyon cell firing rates (sparse, ~5% nonzero).
    mbon_outputs : np.ndarray, (N_MBONS,), float
        Current MBON output values in [-1, 1].
    weights : np.ndarray, (N_KENYON_CELLS, N_MBONS), float
        KC->MBON synaptic weights (plastic).
    eligibility : np.ndarray, (N_KENYON_CELLS, N_MBONS), float
        Eligibility trace for three-factor plasticity.
    dopamine : float
        Current (smoothed) dopamine signal in [-1, 1].
    """

    MBON_NAMES = ["forward_bias", "left_bias", "right_bias",
                  "jump_bias", "explore_bias"]

    def __init__(self, n_kc: int = N_KENYON_CELLS,
                 n_mbon: int = N_MBONS,
                 sparsity: float = KC_SPARSITY,
                 learning_rate: float = LEARNING_RATE,
                 dopamine_threshold: float = DOPAMINE_THRESHOLD):
        self.n_kc = n_kc
        self.n_mbon = n_mbon
        self.sparsity = sparsity
        self.lr = learning_rate
        self.dopamine_threshold = dopamine_threshold

        # Fixed random projection: scene signature (128) -> KC layer (2000)
        _rng = np.random.default_rng(KC_PROJECTION_SEED)
        self.W_kc = _rng.normal(0, 0.1, (n_kc, 128)).astype(np.float32)

        # Plastic KC->MBON weights: initialised near-zero with small variance
        self.weights = _rng.uniform(-0.05, 0.05, (n_kc, n_mbon)).astype(np.float32)

        # State
        self.kc_activity = np.zeros(n_kc, dtype=np.float32)
        self.mbon_outputs = np.zeros(n_mbon, dtype=np.float32)
        self.eligibility = np.zeros((n_kc, n_mbon), dtype=np.float32)
        self.dopamine = 0.0
        self.dopamine_raw = 0.0        # unsmoothed for diagnostics
        self._plasticity_counter = 0   # frames remaining in plasticity window
        self.learning_enabled = True
        self.assoc_count = 0           # total plasticity events

        # History for diagnostics
        self._dopamine_history = deque(maxlen=60)  # last ~1s at 50 Hz

    def encode(self, scene_sig: np.ndarray) -> np.ndarray:
        """Encode scene signature through Kenyon Cells -> produce MBON outputs.

        Parameters
        ----------
        scene_sig : ndarray, (128,)
            L2-normalised scene signature from FlyModel.encode_retina().

        Returns
        -------
        mbon_outputs : ndarray, (N_MBONS,)
            MBON values in [-1, 1] (tanh-clipped).
        """
        # ---- Kenyon Cell sparse coding ----
        # Linear projection: KC_raw = W_kc @ scene_sig
        kc_raw = self.W_kc @ scene_sig  # (2000,)

        # Top-k sparsification: keep only top sparsity fraction active
        k = max(1, int(self.n_kc * self.sparsity))
        threshold = np.sort(kc_raw)[-k] if k < self.n_kc else kc_raw.min()
        self.kc_activity = np.where(kc_raw >= threshold, 1.0, 0.0).astype(np.float32)

        # ---- MBON integration ----
        # MBON = Sigma_i W[i,j] * KC[i] — weighted sum, tanh-clipped to [-1, 1]
        raw_mbon = self.kc_activity @ self.weights  # (N_MBONS,)
        self.mbon_outputs = np.tanh(raw_mbon).astype(np.float32)

        # ---- Eligibility trace update ----
        # E(t) = E(t-1) * decay + KC_activity . MBON_outputs^T
        if self._plasticity_counter > 0:
            # Update eligibility only during plasticity window
            hebbian = np.outer(self.kc_activity, self.mbon_outputs)
            self.eligibility = (
                self.eligibility * ELIGIBILITY_DECAY + hebbian
            ).astype(np.float32)
            self._plasticity_counter -= 1
        else:
            # Outside plasticity window: decay eligibility
            self.eligibility *= ELIGIBILITY_DECAY

        return self.mbon_outputs

    def set_dopamine(self, raw_dopamine: float) -> float:
        """Set the dopamine signal with exponential smoothing.

        Parameters
        ----------
        raw_dopamine : float
            Instantaneous dopamine value in [-1, 1].

        Returns
        -------
        smoothed : float
            Exponentially smoothed dopamine value.
        """
        self.dopamine_raw = raw_dopamine
        self.dopamine = (DOPAMINE_SMOOTHING * raw_dopamine +
                         (1 - DOPAMINE_SMOOTHING) * self.dopamine)
        self._dopamine_history.append(self.dopamine)

        # Trigger plasticity window if significant dopamine event
        # Use raw dopamine for threshold check (smoothed may be below threshold)
        if (abs(raw_dopamine) >= self.dopamine_threshold
                and self.learning_enabled):
            self._plasticity_counter = PLASTICITY_WINDOW
            self.assoc_count += 1

        return self.dopamine

    def update_weights(self) -> int:
        """Apply dopamine-gated plasticity to KC->MBON weights.

        Called once per frame (after set_dopamine).  Implements the
        three-factor learning rule:

            Delta_W[i,j] = eta * R(t) * E[i,j]

        where eta = learning rate, R(t) = dopamine signal,
        and E[i,j] = eligibility trace.

        Only synapses with non-zero eligibility (i.e. active during
        the plasticity window) are modified — this is the FlyWire
        "precise match feedback" property.

        Returns
        -------
        n_modified : int
            Number of synapses changed this frame.
        """
        if not self.learning_enabled or abs(self.dopamine) < 1e-6:
            return 0

        # Plasticity: Delta_W = eta * R * E
        delta = self.lr * self.dopamine * self.eligibility

        # Only apply where eligibility > 1e-6 (active synapses)
        active_mask = np.abs(self.eligibility) > 1e-6
        self.weights[active_mask] += delta[active_mask]
        n_modified = int(active_mask.sum())

        # Clip weights to bounds
        np.clip(self.weights, W_MIN, W_MAX, out=self.weights)

        return n_modified

    def get_mbon_value(self, name: str) -> float:
        """Get MBON output by name.

        Parameters
        ----------
        name : str
            One of 'forward_bias', 'left_bias', 'right_bias',
            'jump_bias', 'explore_bias'.

        Returns
        -------
        float
            MBON value in [-1, 1].
        """
        idx = self.MBON_NAMES.index(name)
        return float(self.mbon_outputs[idx])

    def reset(self) -> None:
        """Reset all state (but keep learned weights)."""
        self.kc_activity.fill(0.0)
        self.mbon_outputs.fill(0.0)
        self.eligibility.fill(0.0)
        self.dopamine = 0.0
        self.dopamine_raw = 0.0
        self._plasticity_counter = 0
        self._dopamine_history.clear()

    def reset_weights(self) -> None:
        """Reset learned weights to initial random values."""
        _rng = np.random.default_rng(KC_PROJECTION_SEED + 1)
        self.weights = _rng.uniform(-0.05, 0.05,
                                     (self.n_kc, self.n_mbon)).astype(np.float32)
        self.assoc_count = 0

    # -- Diagnostics ---------------------------------------------------

    @property
    def dopamine_stats(self) -> dict:
        """Current dopamine statistics."""
        return {
            "dopamine": round(self.dopamine, 4),
            "dopamine_raw": round(self.dopamine_raw, 4),
            "plasticity_active": self._plasticity_counter > 0,
            "plasticity_remaining": self._plasticity_counter,
            "assoc_count": self.assoc_count,
        }

    @property
    def kc_sparsity_actual(self) -> float:
        """Actual fraction of active Kenyon cells."""
        return float(self.kc_activity.mean())

    @property
    def weight_stats(self) -> dict:
        """Weight distribution statistics."""
        return {
            "mean": float(self.weights.mean()),
            "std": float(self.weights.std()),
            "min": float(self.weights.min()),
            "max": float(self.weights.max()),
            "n_positive": int((self.weights > 0).sum()),
            "n_negative": int((self.weights < 0).sum()),
        }