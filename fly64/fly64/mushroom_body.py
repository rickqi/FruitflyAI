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

# Memory content parameters (t7)
KC_TRACE_DECAY = 0.85           # per-frame decay of KC activity trace
KC_HISTORY_LEN = 200            # max recent KC patterns to remember
DOPAMINE_EVENT_MEMORY = 20      # max dopamine events to remember
CONSOLIDATION_THRESHOLD = 0.6   # |dopamine| must exceed this to consolidate
CONSOLIDATED_MAX = 10           # max consolidated memories


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

        # ---- Memory content (t7) ----
        # KC activity trace: running trace of recent KC firing patterns with
        # exponential decay.  Preserves scene context across multiple frames
        # and enables familiarity computation.
        self.kc_trace = np.zeros(n_kc, dtype=np.float32)

        # KC history ring buffer: stores recent KC activity vectors for
        # familiarity matching.  Used to recognise previously seen scenes.
        self._kc_history: deque = deque(maxlen=KC_HISTORY_LEN)

        # Dopamine event memory: stores (kc_pattern, dopamine, mbon_values)
        # on strong dopamine events.  Allows recall of rewarding/punishing
        # experiences and supports memory consolidation.
        self._dopamine_events: deque = deque(maxlen=DOPAMINE_EVENT_MEMORY)

        # Consolidated memories: important associations preserved through
        # consolidation, independent of the plastic weight matrix.
        # Each entry: (kc_pattern, mbon_values, dopamine, tick)
        self.consolidated: list[tuple] = []

        # Familiarity signal (0-1): how familiar the current scene is
        # based on overlap between current KC activity and recent history.
        self.familiarity = 0.0

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

        # ---- KC trace update (t7) ----
        # Running trace preserves recent firing patterns for scene
        # familiarity and context memory.
        # Familiarity is computed from the trace BEFORE this frame's update
        # (i.e. accumulated past activity compared to current frame).
        active_mask = self.kc_activity > 0
        if active_mask.any() and len(self._kc_history) >= 2:
            mean_trace_on_active = float(self.kc_trace[active_mask].mean())
            self.familiarity = min(1.0, mean_trace_on_active)
        else:
            self.familiarity = 0.0

        self.kc_trace = (
            self.kc_trace * KC_TRACE_DECAY + self.kc_activity
        ).astype(np.float32)

        # Store current KC pattern in history ring buffer
        self._kc_history.append(self.kc_activity.copy())

        # ---- Familiarity computed from history (t7) ----
        # Alternative: how many recent history entries have overlapping
        # KC patterns with the current scene?  High overlap = familiar.
        if len(self._kc_history) >= 3:
            recent = list(self._kc_history)[-3:-1]  # last 2 before current
            current_active = set(np.flatnonzero(self.kc_activity))
            overlaps = []
            for past in recent:
                past_active = set(np.flatnonzero(past))
                if current_active:
                    jaccard = len(current_active & past_active) / len(current_active)
                    overlaps.append(jaccard)
            if overlaps:
                self.familiarity = max(self.familiarity, float(np.mean(overlaps)))

        self.familiarity = min(1.0, self.familiarity)

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

            # ---- Log dopamine event (t7) ----
            # Store the KC pattern, dopamine value, and resulting MBON
            # outputs for potential memory recall and consolidation.
            self._dopamine_events.append({
                "kc_pattern": self.kc_activity.copy(),
                "dopamine": raw_dopamine,
                "mbon_values": self.mbon_outputs.copy(),
                "tick": self.assoc_count,
            })

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

        # ---- Memory consolidation (t7) ----
        # When dopamine is strong enough, consolidate the current KC
        # pattern with its associated MBON output into a protected
        # memory store that persists independently of the weight matrix.
        # Use raw (instantaneous) dopamine for the strength check since
        # the smoothed signal may lag behind the actual event.
        if abs(self.dopamine_raw) >= CONSOLIDATION_THRESHOLD:
            self._consolidate()

        return n_modified

    def _consolidate(self) -> None:
        """Store important associations as consolidated memories.

        Consolidation preserves (kc_pattern, mbon_values, dopamine) tuples
        for strong dopamine events.  The consolidated store is independent
        of the plastic weight matrix, providing an additional memory layer
        that retains important associations even if weights later drift.
        """
        entry = (
            self.kc_activity.copy(),
            self.mbon_outputs.copy(),
            self.dopamine_raw,  # use raw (instantaneous) dopamine strength
        )
        # Avoid duplicate consolidation of near-identical patterns
        for existing_kc, _, _ in self.consolidated:
            overlap = float(np.dot(existing_kc, entry[0]))
            if overlap >= (self.n_kc * self.sparsity * 0.6):
                return  # already consolidated a very similar pattern

        self.consolidated.append(entry)
        # Keep only the most recent CONSOLIDATED_MAX entries
        if len(self.consolidated) > CONSOLIDATED_MAX:
            self.consolidated = self.consolidated[-CONSOLIDATED_MAX:]

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
        # ---- Reset memory content (t7) ----
        self.kc_trace.fill(0.0)
        self._kc_history.clear()
        self._dopamine_events.clear()
        self.familiarity = 0.0

    def reset_weights(self) -> None:
        """Reset learned weights to initial random values."""
        _rng = np.random.default_rng(KC_PROJECTION_SEED + 1)
        self.weights = _rng.uniform(-0.05, 0.05,
                                     (self.n_kc, self.n_mbon)).astype(np.float32)
        self.assoc_count = 0

    def recall(self) -> np.ndarray | None:
        """Recall MBON outputs from consolidated memories.

        Searches the consolidated memory store for the KC pattern most
        similar to the current activity and returns its associated MBON
        outputs.  Returns None when no consolidated memory exists or the
        best match is below the familiarity threshold.

        This enables the MB to drive behaviour based on past experience
        even without relying solely on the plastic weight matrix,
        increasing MB utilisation and memory content.

        Returns
        -------
        np.ndarray | None
            (N_MBONS,) MBON values from the best-matching consolidated
            memory, or None if no good match exists.
        """
        if not self.consolidated:
            return None

        # Find best-matching consolidated KC pattern
        best_overlap = 0.0
        best_mbon = None
        for kc_pat, mbon_vals, _ in self.consolidated:
            overlap = float(np.dot(self.kc_activity, kc_pat))
            if overlap > best_overlap:
                best_overlap = overlap
                best_mbon = mbon_vals

        # Only recall if overlap is significant (at least 50% of active KCs)
        if best_overlap >= (self.n_kc * self.sparsity * 0.5):
            return best_mbon
        return None

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

    # -- Memory content diagnostics (t7) -------------------------------

    @property
    def memory_stats(self) -> dict:
        """Memory content statistics."""
        return {
            "familiarity": round(self.familiarity, 4),
            "kc_history_size": len(self._kc_history),
            "kc_trace_mean": float(self.kc_trace.mean()),
            "kc_trace_nonzero": int((self.kc_trace > 0).sum()),
            "dopamine_events": len(self._dopamine_events),
            "consolidated_count": len(self.consolidated),
        }

    @property
    def recent_events(self) -> list[dict]:
        """Recent dopamine events with their MBON values and dopamine."""
        return [
            {
                "dopamine": round(e["dopamine"], 3),
                "mbon": [round(v, 3) for v in e["mbon_values"]],
                "kc_active": int(e["kc_pattern"].sum()),
                "tick": e["tick"],
            }
            for e in list(self._dopamine_events)[-5:]  # last 5
        ]

    @property
    def consolidated_stats(self) -> dict:
        """Stats about consolidated memories."""
        if not self.consolidated:
            return {"count": 0, "mean_dopamine": 0.0, "patterns": []}
        dops = [abs(e[2]) for e in self.consolidated]
        return {
            "count": len(self.consolidated),
            "mean_dopamine": round(float(np.mean(dops)), 4),
            "mean_kc_active": int(np.mean([e[0].sum() for e in self.consolidated])),
            "patterns": [
                {
                    "mbon": [round(v, 3) for v in e[1]],
                    "dopamine": round(e[2], 3),
                    "kc_active": int(e[0].sum()),
                }
                for e in self.consolidated
            ],
        }