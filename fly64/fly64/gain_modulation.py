"""Dopamine-gated gain modulation — plasticity proxy for the fixed connectome.

The MaleCNS connectome weight matrix ``self.w`` is read-only (fixed wiring
diagram).  Instead of modifying synaptic weights, this module provides a
neuromodulatory pathway gain controller that *scales* the effective synaptic
current injection per pathway under dopamine control.

Architecture
------------
The connectome is partitioned into functional *pathways*, each with a scalar
gain that multiplies the current injected into those target neurons during
``step()``.  Pathway gains are adjusted by a dopamine-gated three-factor rule:

    Δgain_p = η · R(t) · E_p · (1 − gain_p)    for R > 0  (potentiation)
    Δgain_p = η · R(t) · E_p · (gain_p − 0)    for R < 0  (depression)

where η = learning rate, R(t) = smoothed dopamine signal,
E_p = eligibility trace for pathway p (decaying history of pathway activity).

Pathways
--------
- ``visual``      — sensory→interneuron synapses (drive from retina)
- ``forward``     — forward motor pool (DNa02/DNg13 subset)
- ``turn``        — left/right turn motor pools
- ``jump``        — jump motor pool (DNp01/DNp10)
- ``recurrent``   — interneuron↔interneuron recurrent connections
"""

from __future__ import annotations

from collections import deque

import numpy as np


# ── Default parameters ────────────────────────────────────────────────

# Per-pathway default gains (initial scalars applied at each tick)
DEFAULT_GAINS = {
    "visual": 1.50,
    "forward": 1.50,
    "turn": 1.50,
    "jump": 1.50,
    "recurrent": 1.50,
}

GAIN_LEARNING_RATE = 0.002        # η — small, gradual gain adaptation
GAIN_MIN = 0.5                    # floor — cannot go below 50% of nominal
GAIN_MAX = 2.5                    # ceiling — cannot exceed 250% of nominal
GAIN_ELIGIBILITY_DECAY = 0.85     # per-frame decay of pathway eligibility
DOPAMINE_GAIN_THRESHOLD = 0.15    # |dopamine| must exceed this for gain update
PLASTICITY_FRAMES = 5             # frames dopamine pulse opens plasticity window
ACTIVITY_THRESHOLD = 0.05         # fraction of pathway neurons firing → "active"


class DopamineGainController:
    """Dopamine-gated per-pathway gain modulation for the fixed connectome.

    Maintains a scalar gain per neural pathway, an eligibility trace per
    pathway (decaying history of recent activity), and applies three-factor
    gain updates when dopamine exceeds threshold.

    Attributes
    ----------
    pathway_gains : dict[str, float]
        Current gain per pathway, bounded to [GAIN_MIN, GAIN_MAX].
    pathway_eligibility : dict[str, float]
        Eligibility trace per pathway [0, 1], decaying each frame.
    dopamine_smoothed : float
        Exponentially smoothed dopamine from the last update call.
    plasticity_remaining : int
        Frames remaining in the current plasticity window.
    gain_update_count : int
        Total number of dopamine-gated gain updates applied.
    """

    # Pathway names in priority order (for iteration)
    PATHWAYS = ("visual", "forward", "turn", "jump", "recurrent")

    def __init__(
        self,
        initial_gains: dict[str, float] | None = None,
        learning_rate: float = GAIN_LEARNING_RATE,
        dopamine_threshold: float = DOPAMINE_GAIN_THRESHOLD,
        eligibility_decay: float = GAIN_ELIGIBILITY_DECAY,
        plasticity_frames: int = PLASTICITY_FRAMES,
        activity_threshold: float = ACTIVITY_THRESHOLD,
    ):
        self.lr = learning_rate
        self.dopamine_threshold = dopamine_threshold
        self.eligibility_decay = eligibility_decay
        self.plasticity_frames = plasticity_frames
        self.activity_threshold = activity_threshold

        # Per-pathway state
        merged = dict(DEFAULT_GAINS)
        if initial_gains:
            merged.update(initial_gains)
        self.pathway_gains: dict[str, float] = {
            p: float(np.clip(merged.get(p, DEFAULT_GAINS[p]), GAIN_MIN, GAIN_MAX))
            for p in self.PATHWAYS
        }
        self.pathway_eligibility: dict[str, float] = {p: 0.0 for p in self.PATHWAYS}

        # Dopamine state
        self.dopamine_smoothed = 0.0
        self.dopamine_raw = 0.0

        # Plasticity window
        self.plasticity_remaining = 0
        self.gain_update_count = 0

        # History for diagnostics
        self._gain_history: dict[str, deque[float]] = {
            p: deque(maxlen=60) for p in self.PATHWAYS
        }
        self._dopamine_history: deque[float] = deque(maxlen=60)

    # ── Public API ────────────────────────────────────────────────────

    def set_dopamine(self, raw_dopamine: float, alpha: float = 0.3) -> float:
        """Set the dopamine signal with exponential smoothing.

        Parameters
        ----------
        raw_dopamine : float
            Instantaneous dopamine value in [-1, 1] (from _compute_dopamine).
        alpha : float
            Smoothing factor (0=no update, 1=instant). Default 0.3.

        Returns
        -------
        smoothed : float
            Exponentially smoothed dopamine value.
        """
        self.dopamine_raw = raw_dopamine
        self.dopamine_smoothed = (
            alpha * raw_dopamine + (1 - alpha) * self.dopamine_smoothed
        )
        self._dopamine_history.append(self.dopamine_smoothed)

        # Open plasticity window if significant dopamine event
        if abs(raw_dopamine) >= self.dopamine_threshold:
            self.plasticity_remaining = self.plasticity_frames

        return self.dopamine_smoothed

    def update_eligibility(self, pathway_activity: dict[str, float]) -> None:
        """Update eligibility traces based on pathway firing activity.

        Call this *after* ``set_dopamine()`` and *before* ``apply_gain_update()``
        in each frame where the plasticity window is open.

        Parameters
        ----------
        pathway_activity : dict[str, float]
            Recent firing fraction per pathway [0, 1], e.g.
            ``{"visual": 0.12, "forward": 0.0, ...}``.
        """
        for p in self.PATHWAYS:
            activity = pathway_activity.get(p, 0.0)
            is_active = activity > self.activity_threshold
            if self.plasticity_remaining > 0 and is_active:
                # During plasticity window, increase eligibility for active pathways
                self.pathway_eligibility[p] = min(
                    1.0,
                    self.pathway_eligibility[p] * self.eligibility_decay + activity,
                )
            else:
                # Outside window or inactive: decay
                self.pathway_eligibility[p] *= self.eligibility_decay

        if self.plasticity_remaining > 0:
            self.plasticity_remaining -= 1

    def apply_gain_update(self) -> int:
        """Apply dopamine-gated three-factor gain update.

        Three-factor rule:

            Δgain_p = η · R(t) · E_p · scale_p

        where:
            η = learning rate
            R(t) = smoothed dopamine (sign determines direction)
            E_p = eligibility trace for pathway p
            scale_p = (GAIN_MAX − gain_p) for R > 0  (room to grow)
                      (gain_p − GAIN_MIN) for R < 0  (room to shrink)

        Returns
        -------
        n_modified : int
            Number of pathways whose gain was modified this frame.
        """
        R = self.dopamine_smoothed
        if abs(R) < 1e-6:
            return 0

        n_modified = 0
        for p in self.PATHWAYS:
            E_p = self.pathway_eligibility[p]
            if E_p < 1e-6:
                continue  # skip pathways with no recent activity

            # Scale factor: how much room to move toward the bound
            if R > 0:
                scale = GAIN_MAX - self.pathway_gains[p]
            else:
                scale = self.pathway_gains[p] - GAIN_MIN

            delta = self.lr * R * E_p * scale
            if abs(delta) > 1e-8:
                old = self.pathway_gains[p]
                self.pathway_gains[p] = float(
                    np.clip(old + delta, GAIN_MIN, GAIN_MAX)
                )
                self._gain_history[p].append(self.pathway_gains[p])
                n_modified += 1

        if n_modified > 0:
            self.gain_update_count += 1

        return n_modified

    def get_gain(self, pathway: str) -> float:
        """Return the current gain for a pathway.

        Parameters
        ----------
        pathway : str
            One of ``'visual'``, ``'forward'``, ``'turn'``, ``'jump'``,
            ``'recurrent'``.

        Returns
        -------
        float
            Current gain in [GAIN_MIN, GAIN_MAX].
        """
        return self.pathway_gains.get(pathway, 1.0)

    def get_all_gains(self) -> dict[str, float]:
        """Return current gains for all pathways."""
        return dict(self.pathway_gains)

    def get_all_eligibility(self) -> dict[str, float]:
        """Return current eligibility traces for all pathways."""
        return dict(self.pathway_eligibility)

    # ── Plasticity update convenience ─────────────────────────────────

    def plasticity_step(
        self,
        raw_dopamine: float,
        pathway_activity: dict[str, float],
        alpha: float = 0.3,
    ) -> int:
        """Convenience: full plasticity update in one call.

        Equivalent to calling ``set_dopamine()``, ``update_eligibility()``,
        then ``apply_gain_update()`` in sequence.

        Parameters
        ----------
        raw_dopamine : float
            Instantaneous dopamine value in [-1, 1].
        pathway_activity : dict[str, float]
            Recent firing fraction per pathway [0, 1].
        alpha : float
            Dopamine smoothing factor (default 0.3).

        Returns
        -------
        n_modified : int
            Number of pathways whose gain was modified.
        """
        self.set_dopamine(raw_dopamine, alpha=alpha)
        self.update_eligibility(pathway_activity)
        return self.apply_gain_update()

    # ── Diagnostics ───────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """Current statistics for dashboard / telemetry."""
        return {
            "gains": self.get_all_gains(),
            "eligibility": self.get_all_eligibility(),
            "dopamine_smoothed": round(self.dopamine_smoothed, 4),
            "dopamine_raw": round(self.dopamine_raw, 4),
            "plasticity_remaining": self.plasticity_remaining,
            "gain_update_count": self.gain_update_count,
        }

    def gain_history(self, pathway: str) -> list[float]:
        """Return gain history for a pathway (last ~60 frames)."""
        return list(self._gain_history.get(pathway, []))

    @property
    def dopamine_history(self) -> list[float]:
        """Last ~60 smoothed dopamine values."""
        return list(self._dopamine_history)

    # ── Reset ─────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all state to defaults (gains return to initial values)."""
        merged = dict(DEFAULT_GAINS)
        self.pathway_gains = {p: float(merged[p]) for p in self.PATHWAYS}
        self.pathway_eligibility = {p: 0.0 for p in self.PATHWAYS}
        self.dopamine_smoothed = 0.0
        self.dopamine_raw = 0.0
        self.plasticity_remaining = 0
        self.gain_update_count = 0
        for dq in self._gain_history.values():
            dq.clear()
        self._dopamine_history.clear()

    def reset_gains(self, gains: dict[str, float] | None = None) -> None:
        """Reset gains to specified values or defaults.

        Parameters
        ----------
        gains : dict[str, float] | None
            Per-pathway gains to set.  Unspecified pathways revert to
            DEFAULT_GAINS.
        """
        base = dict(DEFAULT_GAINS)
        if gains:
            base.update(gains)
        self.pathway_gains = {
            p: float(np.clip(base.get(p, DEFAULT_GAINS[p]), GAIN_MIN, GAIN_MAX))
            for p in self.PATHWAYS
        }
        self.pathway_eligibility = {p: 0.0 for p in self.PATHWAYS}
        self.gain_update_count = 0