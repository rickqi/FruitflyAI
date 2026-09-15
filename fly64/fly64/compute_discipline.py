"""
Computational discipline: per-frame CPU profiling, frame-budget management,
and dynamic downsampling (skip expensive layers) when frame time exceeds
the budget.

Part of t4 B5 (computational discipline).

Design:
  - FrameBudgetController tracks the elapsed wall time of the main tick.
  - When the rolling average exceeds the target budget (default 5 ms),
    it sets ``skip_layers`` flags for the next frame.
  - ``skip_layers`` tells ``retina.compute_flow()`` to skip expensive but
    expendable layers: door_frame, color_azimuth, small_targets, etc.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional


# Target: 50 fps → 20 ms total frame budget.  The brain main loop needs
# ~5 ms for neural compute + HTTP/WS.  Budget in seconds.
DEFAULT_BUDGET_S = 0.005    # 5 ms


class FrameBudgetController:
    """Monitors tick duration and decides which expensive layers to skip.

    Usage::

        budget = FrameBudgetController(budget_s=0.005)
        ...
        tick_start = time.monotonic()
        # ... do work ...
        budget.record_tick(time.monotonic() - tick_start)
        skip = budget.get_skip_layers()
        flow = retina.compute_flow(atlas, skip_layers=skip)
    """

    def __init__(self, budget_s: float = DEFAULT_BUDGET_S,
                 window: int = 30,
                 downsample_factor: float = 0.85):
        self.budget_s = budget_s
        self.window = window
        self.downsample_factor = downsample_factor

        # Rolling window of tick durations (seconds)
        self._durations: deque[float] = deque(maxlen=window)
        # Consecutive frames over budget
        self._over_budget_count = 0
        # Current skip layers bitmask (0 = none)
        self._skip_bitmask = 0
        # Total call count
        self._total_ticks = 0

    # Bitmask flags for expensive layers
    SKIP_DOOR_FRAME = 1 << 0      # door_frame detection (heavy)
    SKIP_COLOR_AZIMUTH = 1 << 1   # color_azimuth distribution
    SKIP_SMALL_TARGETS = 1 << 2   # small target tracking (connected components)
    SKIP_HRC_LOOMING = 1 << 3     # HRC looming population (16 sectors)
    SKIP_COLOR = 1 << 4           # full color encode (per-cell)
    SKIP_EDGE_ORIENT = 1 << 5     # edge orientation (4 directions)

    #: Ordered escalation: cheaper skips first, then heavier ones.
    ESCALATION_ORDER = [
        SKIP_HRC_LOOMING,
        SKIP_EDGE_ORIENT,
        SKIP_COLOR_AZIMUTH,
        SKIP_DOOR_FRAME,
        SKIP_SMALL_TARGETS,
        SKIP_COLOR,
    ]

    def record_tick(self, duration_s: float) -> None:
        """Record one tick's total wall time (retina + model.step + telemetry)."""
        self._durations.append(duration_s)
        self._total_ticks += 1

        avg = self.average_duration()
        if avg > self.budget_s:
            self._over_budget_count += 1
        else:
            self._over_budget_count = max(0, self._over_budget_count - 1)

        # Recompute skip bitmask
        self._update_skip_bitmask()

    def average_duration(self) -> float:
        """Rolling mean tick duration in seconds (0 if no data)."""
        if not self._durations:
            return 0.0
        return sum(self._durations) / len(self._durations)

    def get_skip_layers(self) -> int:
        """Current skip-layer bitmask (0 = skip nothing)."""
        return self._skip_bitmask

    def get_skip_names(self) -> list[str]:
        """Human-readable list of currently-skipped layer names."""
        names = []
        if self._skip_bitmask & self.SKIP_DOOR_FRAME:
            names.append("door_frame")
        if self._skip_bitmask & self.SKIP_COLOR_AZIMUTH:
            names.append("color_azimuth")
        if self._skip_bitmask & self.SKIP_SMALL_TARGETS:
            names.append("small_targets")
        if self._skip_bitmask & self.SKIP_HRC_LOOMING:
            names.append("hrc_looming")
        if self._skip_bitmask & self.SKIP_COLOR:
            names.append("color_encode")
        if self._skip_bitmask & self.SKIP_EDGE_ORIENT:
            names.append("edge_orientation")
        return names

    def _update_skip_bitmask(self) -> None:
        """Update bitmask based on average duration vs budget and history."""
        avg = self.average_duration()
        if avg <= 0:
            self._skip_bitmask = 0
            return

        # How much over budget?
        ratio = avg / self.budget_s

        if ratio <= 0.8:
            # Well within budget → clear skips progressively
            self._skip_bitmask = 0
        elif ratio <= 1.0:
            # Slightly under budget — keep current skips but don't add
            pass
        elif ratio <= 1.5:
            # 1-1.5x over budget: enable 1 cheap skip
            self._skip_bitmask = self.ESCALATION_ORDER[0]
        elif ratio <= 2.0:
            # 1.5-2x: enable 2 skips
            self._skip_bitmask = self.ESCALATION_ORDER[0] | self.ESCALATION_ORDER[1]
        elif ratio <= 3.0:
            # 2-3x: enable 4 skips
            self._skip_bitmask = (self.ESCALATION_ORDER[0] | self.ESCALATION_ORDER[1]
                                  | self.ESCALATION_ORDER[2] | self.ESCALATION_ORDER[3])
        else:
            # >3x over budget: skip everything expendable
            for flag in self.ESCALATION_ORDER:
                self._skip_bitmask |= flag

    def reset(self) -> None:
        """Reset all state."""
        self._durations.clear()
        self._over_budget_count = 0
        self._skip_bitmask = 0
        self._total_ticks = 0


# ── Convenience profiling timer ───────────────────────────────────────

class PerfTimer:
    """Lightweight wall-clock timer for annotating sections.

    Usage::

        timer = PerfTimer()
        timer.start("compute_flow")
        flow = retina.compute_flow(...)
        timer.stop("compute_flow")
        data = timer.get_report()
    """

    def __init__(self):
        self._starts: dict[str, float] = {}
        self._totals: dict[str, float] = {}
        self._counts: dict[str, int] = {}

    def start(self, label: str) -> None:
        self._starts[label] = time.monotonic()

    def stop(self, label: str) -> float:
        elapsed = time.monotonic() - self._starts.get(label, 0.0)
        self._totals[label] = self._totals.get(label, 0.0) + elapsed
        self._counts[label] = self._counts.get(label, 0) + 1
        return elapsed

    def get_report(self) -> dict:
        """Return per-section summary: total_s, avg_ms, count."""
        report = {}
        for label in self._totals:
            total = self._totals[label]
            cnt = self._counts[label]
            report[label] = {
                "total_s": round(total, 6),
                "avg_ms": round(total / max(cnt, 1) * 1000, 3),
                "count": cnt,
            }
        return report

    def reset(self) -> None:
        self._starts.clear()
        self._totals.clear()
        self._counts.clear()