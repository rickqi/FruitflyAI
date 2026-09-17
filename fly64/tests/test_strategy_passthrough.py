"""PIN tests: coach strategy -> behavior pass-through (t6 root fix).

load_active_strategy() used to return ONLY the fallen_recovery-derived keys,
so the behavior pipeline's
    _expl = _active_strategy.get("exploration", {})
    _esc  = _active_strategy.get("escape", {})
always saw {} and every coach-tuned parameter fell back to a hardcoded
default.  These tests lock the pass-through so GLM advice actually reaches
behavior.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fly64.main import load_active_strategy  # noqa: E402


def _write(tmp_path, data):
    p = tmp_path / "active_strategy.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


class TestStrategyPassThrough:
    def test_exploration_and_escape_reach_the_caller(self, tmp_path):
        path = _write(tmp_path, {
            "fallen_recovery": {"mode": "directional_climb", "climb_period": 2.5},
            "exploration": {"bold_explore_stuck_s": 30, "turn_bias": 0.6},
            "escape": {"stuck_threshold_s": 1.5, "fallen_forward": 0.42},
        })
        s = load_active_strategy(path)
        assert s["mode"] == "directional_climb"
        assert s["climb_period"] == 2.5
        # the behaviour-pipeline keys MUST be present (regression guard)
        assert s["exploration"]["bold_explore_stuck_s"] == 30
        assert s["exploration"]["turn_bias"] == 0.6
        assert s["escape"]["stuck_threshold_s"] == 1.5
        assert s["escape"]["fallen_forward"] == 0.42

    def test_command_section_passed_through(self, tmp_path):
        path = _write(tmp_path, {
            "command": {"type": "turn_and_go", "heading": 90, "y": 70, "ts": 123},
        })
        s = load_active_strategy(path)
        assert s["command"]["type"] == "turn_and_go"
        assert s["command"]["ts"] == 123

    def test_missing_sections_absent_not_crashing(self, tmp_path):
        path = _write(tmp_path, {"fallen_recovery": {"mode": "mirror"}})
        s = load_active_strategy(path)
        assert s["mode"] == "mirror"
        assert "exploration" not in s      # absent, caller's .get default applies
        assert "escape" not in s

    def test_malformed_sections_ignored(self, tmp_path):
        path = _write(tmp_path, {
            "exploration": "not-a-dict",
            "escape": [1, 2, 3],
            "fallen_recovery": {"mode": "bogus-mode"},
        })
        s = load_active_strategy(path)
        assert s["mode"] == "mirror"        # invalid mode -> default
        assert "exploration" not in s
        assert "escape" not in s

    def test_broken_file_falls_back_to_defaults(self, tmp_path):
        p = tmp_path / "active_strategy.json"
        p.write_text("{not json", encoding="utf-8")
        s = load_active_strategy(p)
        assert s["mode"] == "mirror"
        assert s["climb_period"] == 2.0
