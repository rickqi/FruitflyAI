"""M2.1: coach/operator primitive strategy — prefer map + ineffective help."""
import json

import pytest

from plugin.runner import PluginRunner, STUCK_HELP_THRESHOLD


def _runner(memory, help_snap=None):
    snap = {"evolution": None, "help": help_snap,
            "memory": memory, "flow": None}
    r = PluginRunner(fetcher=lambda ep: snap.get(ep.strip("/")))
    return r, snap


def test_scene_prefer_parsed(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, ".")
    from fly64.main import load_active_strategy, ACTIVE_STRATEGY_DEFAULTS
    p = tmp_path / "strategy.json"
    p.write_text(json.dumps({"primitives": {
        "enabled": ["longjump", "punch", "dive"],
        "prefer": {"ramp": "longjump", "lava": "dive", "": "ignored"}}}),
        encoding="utf-8")
    s = load_active_strategy(p)
    assert s["primitives_prefer"] == {"ramp": "longjump", "lava": "dive"}


def test_scene_prefer_absent_gives_no_key(tmp_path):
    import sys
    sys.path.insert(0, ".")
    from fly64.main import load_active_strategy
    p = tmp_path / "strategy.json"
    p.write_text(json.dumps({"primitives": {"enabled": ["longjump"]}}),
                 encoding="utf-8")
    s = load_active_strategy(p)
    assert "primitives_prefer" not in s


def test_primitive_ineffective_after_three_zero_disp():
    mem = {"stuck_duration": 5.0, "anomaly_state": "idle",
           "reflex_active": False, "health_score": 1.0,
           "disp_60s": 5.0, "scene_name": "ramp",
           "cpg": {"completed": 0, "aborted": 0}}
    r, snap = _runner(mem)
    # 3 completion events, each with <30u displacement
    for i in (1, 2, 3):
        mem["cpg"]["completed"] = i
        ctx = r.check_help_needed(snap)
    assert ctx is not None
    assert ctx["help_reason"] == "primitive_ineffective"
    assert "wrong primitive" in ctx["diagnosis"]
    assert ctx["cpg"] == {"completed": 3, "aborted": 0}


def test_effective_displacement_resets_counter():
    mem = {"stuck_duration": 5.0, "anomaly_state": "idle",
           "reflex_active": False, "health_score": 1.0,
           "scene_name": "ramp", "cpg": {"completed": 0, "aborted": 0}}
    r, snap = _runner(mem)
    mem["cpg"]["completed"] = 1
    mem["disp_60s"] = 120.0
    assert r.check_help_needed(snap) is None
    mem["cpg"]["completed"] = 2
    mem["disp_60s"] = 5.0
    assert r.check_help_needed(snap) is None        # run=1
    mem["cpg"]["completed"] = 3
    mem["disp_60s"] = 5.0
    ctx = r.check_help_needed(snap)                 # run=2, not yet 3
    assert ctx is None or ctx.get("help_reason") != "primitive_ineffective"
    mem["cpg"]["completed"] = 4
    mem["disp_60s"] = 5.0
    ctx = r.check_help_needed(snap)                 # run=3 -> trigger
    assert ctx is not None and ctx["help_reason"] == "primitive_ineffective"


def test_high_disp_completion_resets_run():
    mem = {"stuck_duration": 5.0, "anomaly_state": "idle",
           "reflex_active": False, "health_score": 1.0,
           "scene_name": "ramp", "cpg": {"completed": 0, "aborted": 0}}
    r, snap = _runner(mem)
    for i in (1, 2):
        mem["cpg"]["completed"] = i
        mem["disp_60s"] = 5.0
        r.check_help_needed(snap)
    mem["cpg"]["completed"] = 3
    mem["disp_60s"] = 900.0                          # big jump resets run
    assert r.check_help_needed(snap) is None
    mem["cpg"]["completed"] = 4
    mem["disp_60s"] = 5.0
    assert r.check_help_needed(snap) is None         # run restarts at 1


def test_primitive_ineffective_counter_isolated_from_stuck_path():
    mem = {"stuck_duration": STUCK_HELP_THRESHOLD + 10, "anomaly_state": "stuck_ramp",
           "reflex_active": False, "health_score": 0.9,
           "disp_60s": 0.0, "scene_name": "x",
           "cpg": {"completed": 5, "aborted": 0}}
    r, snap = _runner(mem)
    ctx = r.check_help_needed(snap)
    # stuck path fires first on this tick; the completion counter still
    # registered one zero-disp run (next ticks would accumulate)
    assert ctx["help_reason"] in ("unsolvable_stuck", "reflex_ineffective_stuck")
    assert r._prim_zero_run == 1
