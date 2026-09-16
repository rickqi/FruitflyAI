"""PIN tests: multi-signal weighted help trigger (P1-2.3).

The 60s scalar floor is preserved unchanged; the weighted score lets strong
combined evidence escalate EARLIER (e.g. stuck 50s + reflex ineffective +
saturation growth + danger scene).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin.runner import PluginRunner, HELP_SCORE_WEIGHTS  # noqa: E402

MEM_BASE = {"stuck_duration": 0.0, "anomaly_state": "idle", "health_score": 1.0,
            "reflex_active": False, "reflex_ineffective": False,
            "scene_name": "s", "cpg": {}, "disp_60s": 60.0}


def _runner(tmp_path):
    from plugin import coach_outcomes as co
    r = PluginRunner(fetcher=lambda ep: {})
    co.clear_pending(co.PENDING_PATH)
    return r


class TestHelpScore:
    def test_components_sum_to_weight_total(self):
        r = _runner(None)
        mem = dict(MEM_BASE, stuck_duration=120.0, reflex_ineffective=True)
        r.help_score(mem, {"mb_saturation_events": 0})   # prime prev=0
        score, comp = r.help_score(mem, {"mb_saturation_events": 999,
                                         "scene_danger": 1.0})
        assert 0.99 <= score <= 1.0
        assert comp["stuck"] == 1.0 and comp["reflex_ineffective"] == 1.0

    def test_healthy_brain_scores_zero(self):
        r = _runner(None)
        score, comp = r.help_score(dict(MEM_BASE), {})
        assert score == 0.0 and sum(comp.values()) == 0.0

    def test_below_60s_can_trigger_when_signals_stack(self, tmp_path):
        """The whole point of P1-2.3: stuck 50s (< 60s floor) but three
        supporting signals → escalate earlier than the scalar would."""
        r = _runner(tmp_path)
        mem = dict(MEM_BASE, stuck_duration=50.0, anomaly_state="micro_loop",
                   reflex_ineffective=True)
        flow = {"mb_saturation_events": 5}
        r.help_score(mem, flow)                       # prime saturation prev=5
        flow2 = {"mb_saturation_events": 25}          # +20 events in 10s → rate maxed
        import time
        time.sleep(0.05)
        ctx = r.check_help_needed({"memory": mem, "flow": flow2, "help": {}})
        assert ctx and ctx["help_reason"] == "multi_signal_stuck"
        assert ctx["help_components"]["stuck"] > 0.3

    def test_floor_still_triggers_at_65s_without_other_signals(self, tmp_path):
        r = _runner(tmp_path)
        mem = dict(MEM_BASE, stuck_duration=65.0, anomaly_state="micro_loop",
                   reflex_ineffective=False)
        ctx = r.check_help_needed({"memory": mem, "flow": {}, "help": {}})
        assert ctx and ctx["help_reason"] == "unsolvable_stuck"

    def test_threshold_env_override(self, tmp_path, monkeypatch):
        from plugin import runner as R
        monkeypatch.setenv("FLY64_HELP_SCORE_THRESHOLD", "0.99")
        r = PluginRunner(fetcher=lambda ep: ({}))
        assert r.help_score_threshold == 0.99
