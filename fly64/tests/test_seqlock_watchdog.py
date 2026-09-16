#!/usr/bin/env python3
"""t19 regression: seqlock freeze watchdog + flow passthrough + UI pill.

Covers: SeqlockWatchdog logic (fresh / pre-threshold / stale / monotonic
reset / torn-read accrual), main.py flow.json bridge_stale passthrough,
dashboard pill wiring.  SharedBridge itself needs a POSIX mmap host so its
wiring is verified at source level (Windows-compatible).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fly64.bridge import SeqlockWatchdog  # noqa: E402


class TestSeqlockWatchdog:
    def test_fresh_seq_not_stale(self):
        w = SeqlockWatchdog(stale_after=5.0)
        assert w.update(1, 0.0) is False
        assert w.update(2, 1.0) is False
        assert w.update(3, 2.0) is False
        assert w.stale is False

    def test_stale_after_threshold(self):
        w = SeqlockWatchdog(stale_after=5.0)
        assert w.update(10, 0.0) is False
        assert w.update(10, 4.9) is False      # just under threshold
        assert w.update(10, 5.1) is True       # past threshold
        assert w.update(10, 100.0) is True     # stays stale

    def test_seq_advance_resets(self):
        w = SeqlockWatchdog(stale_after=5.0)
        assert w.update(1, 0.0) is False
        assert w.update(1, 10.0) is True       # frozen
        assert w.update(2, 10.5) is False      # producer resumed
        assert w.update(2, 12.0) is False
        assert w.update(2, 18.0) is True       # frozen again

    def test_monotonic_no_false_positive(self):
        w = SeqlockWatchdog(stale_after=5.0)
        # seq advancing steadily for a long run — never stale
        t = 0.0
        for i in range(1, 2000):
            t += 0.02  # 50 Hz frames
            assert w.update(i, t) is False

    def test_torn_read_accrues_stagnation(self):
        w = SeqlockWatchdog(stale_after=5.0)
        assert w.update(7, 0.0) is False
        # repeated same-seq reads (torn/frozen) accumulate
        assert w.update(7, 3.0) is False
        assert w.update(7, 6.0) is True

    def test_reset(self):
        w = SeqlockWatchdog(stale_after=5.0)
        w.update(1, 0.0)
        w.update(1, 9.0)
        assert w.stale is True
        w.reset()
        assert w.stale is False and w.last_seq is None


class TestWiring:
    def test_bridge_uses_watchdog_and_exposes_stale(self):
        src = (PROJECT / "fly64" / "bridge.py").read_text(encoding="utf-8")
        assert "self.seqlock_watchdog = SeqlockWatchdog()" in src
        assert "seqlock_watchdog.update(before, now)" in src
        assert "def stale" in src  # SharedBridge.stale property

    def test_main_passes_bridge_stale_to_flow(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        assert '"bridge_stale": bool(bridge.stale)' in src

    def test_dashboard_freeze_pill_wiring(self):
        html = (PROJECT / "web" / "index.html").read_text(encoding="utf-8")
        assert 'id="bridgeStalePill"' in html
        assert "SM64⛔ FROZEN" in html
        js = (PROJECT / "web" / "dashboard.js").read_text(encoding="utf-8")
        assert "bs.hidden = !d.bridge_stale" in js
        css = (PROJECT / "web" / "dashboard.css").read_text(encoding="utf-8")
        assert ".stale-pill" in css and "stalePulse" in css


class TestCoachFramesEndpoint:
    """t21 final review: strict filename allowlist on /coach_frames/<name>."""

    def test_strict_allowlist_regex_in_main(self):
        src = (PROJECT / "fly64" / "main.py").read_text(encoding="utf-8")
        assert 're.fullmatch(r"[A-Za-z0-9_\\-.]+\\.png", name)' in src
        assert '".." in name' in src          # double-dot explicitly rejected

    def test_saved_filename_matches_allowlist(self):
        # the save format must satisfy the endpoint allowlist
        import re
        name = "coach_1789458811.537_unsolvable_stuck.png"
        assert re.fullmatch(r"[A-Za-z0-9_\-.]+\.png", name)
        assert ".." not in name
