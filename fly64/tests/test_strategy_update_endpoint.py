"""EVO-061 · PIN: the operator parameter sliders must reach the brain.

The defect: `web/evo-params.html` posts the parameter ids straight out of
`skills/brain_tunable_params.json`, which are DOTTED PATHS:

    JSON.stringify({[pid]: Number(value)})   ->  {"escape.commit_ticks": 125}

The `/active_strategy-update` handler wrote that as a literal top-level key:

    cur["escape.commit_ticks"] = 125

while the brain's hot-reload reads `_active_strategy["escape"]["commit_ticks"]`.
So the slider showed a check mark, the UI echoed the new value, the endpoint
returned `{"status":"ok"}` — and NOTHING reached behaviour.  15 of the 21
tunable ids already map onto paths the brain reads, so the whole feature was
one dot-expansion away from working.

These tests therefore assert through the REAL consumer API
(`load_active_strategy`) and not merely that a key exists in the file — a
"the file contains it" assertion is exactly what the broken version satisfied.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = REPO_ROOT / "fly64" / "main.py"
sys.path.insert(0, str(REPO_ROOT))

from fly64.main import apply_strategy_update, load_active_strategy  # noqa: E402


#: dotted paths the brain's hot-reload block actually reads (main.py ~1164-1192)
BRAIN_CONSUMED = [
    "exploration.bold_explore_stuck_s",
    "exploration.turn_bias",
    "escape.stuck_threshold_s",
    "escape.commit_ticks",
    "escape.forward_accum_max",
    "escape.fallen_forward",
    "escape.fallen_jump_boost",
    "escape.fallen_switch_s",
]


class TestDottedPathsAreExpanded:
    def test_dotted_key_lands_nested(self):
        cur = {}
        applied, rejected = apply_strategy_update(cur, {"escape.commit_ticks": 125})
        assert rejected == []
        assert cur == {"escape": {"commit_ticks": 125}}, cur
        assert applied["escape.commit_ticks"] == "escape.commit_ticks"

    def test_the_brain_consumer_actually_sees_it(self, tmp_path):
        """The decisive test: payload -> file -> load_active_strategy()."""
        path = tmp_path / "active_strategy.json"
        cur = {"fallen_recovery": {"mode": "mirror"}}
        apply_strategy_update(cur, {"escape.commit_ticks": 125,
                                   "exploration.turn_bias": 0.33})
        path.write_text(json.dumps(cur), encoding="utf-8")

        strategy = load_active_strategy(path)
        assert strategy["escape"]["commit_ticks"] == 125, (
            "the value did not reach the path the brain reads — the slider "
            "would report success while changing nothing")
        assert strategy["exploration"]["turn_bias"] == 0.33

    def test_every_brain_consumed_path_is_reachable(self):
        cur = {}
        updates = {p: 1 for p in BRAIN_CONSUMED}
        applied, rejected = apply_strategy_update(cur, updates)
        assert rejected == [], rejected
        for path in BRAIN_CONSUMED:
            node = cur
            for part in path.split("."):
                assert isinstance(node, dict) and part in node, (
                    f"{path} is not placeable — the brain would read its default")
                node = node[part]
        assert set(applied) == set(BRAIN_CONSUMED)

    def test_deep_path_is_created(self):
        cur = {}
        apply_strategy_update(cur, {"a.b.c": 7})
        assert cur == {"a": {"b": {"c": 7}}}

    def test_existing_sections_are_preserved(self):
        cur = {"escape": {"stuck_threshold_s": 10.0, "reverse_seconds": 0.8}}
        apply_strategy_update(cur, {"escape.commit_ticks": 77})
        assert cur["escape"] == {"stuck_threshold_s": 10.0,
                                "reverse_seconds": 0.8, "commit_ticks": 77}


class TestNoRegressions:
    def test_plain_key_still_written(self):
        cur = {"mode": "mirror"}
        apply_strategy_update(cur, {"mode": "directional_climb"})
        assert cur["mode"] == "directional_climb"

    def test_nested_payload_still_merges(self):
        cur = {"exploration": {"turn_bias": 0.6}}
        apply_strategy_update(cur, {"exploration": {"turn_bias": 0.9}})
        assert cur["exploration"] == {"turn_bias": 0.9}

    def test_new_section_is_created(self):
        cur = {}
        apply_strategy_update(cur, {"command": {"type": "turn_and_go"}})
        assert cur["command"] == {"type": "turn_and_go"}


class TestDeadWritesAreReported:
    def test_scalar_clobber_is_rejected_not_silent(self):
        cur = {"escape": 5}          # malformed file: a scalar where a map goes
        applied, rejected = apply_strategy_update(cur, {"escape.commit_ticks": 9})
        assert applied == {} and rejected == ["escape.commit_ticks"]
        assert cur == {"escape": 5}, "existing data was destroyed"

    def test_non_string_key_is_rejected(self):
        cur = {}
        _, rejected = apply_strategy_update(cur, {1: 2})
        assert rejected and cur == {}

    def test_non_dict_payload_is_rejected(self):
        cur = {}
        applied, rejected = apply_strategy_update(cur, ["nope"])
        assert applied == {} and rejected


class TestHandlerIsWired:
    """The handler must use the helper, so the two cannot drift apart."""

    def _do_post_source(self):
        tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "do_POST":
                return ast.get_source_segment(
                    MAIN_PY.read_text(encoding="utf-8"), node)
        raise AssertionError("do_POST not found")

    def test_do_post_calls_apply_strategy_update(self):
        src = self._do_post_source()
        assert "apply_strategy_update(" in src, (
            "do_POST no longer uses apply_strategy_update — dotted slider ids "
            "would silently become dead top-level keys again")

    def test_do_post_reports_applied_and_rejected(self):
        src = self._do_post_source()
        assert "applied" in src and "rejected" in src, (
            "the endpoint must report where each key landed and which were "
            "refused, so a dead write is visible instead of a bare 'ok'")

    def test_helper_is_defined_at_module_level(self):
        tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        assert "apply_strategy_update" in names


class TestRealTunableIds:
    """Every id the panel renders must be applicable."""

    def test_all_tunable_ids_from_the_schema_apply(self):
        p = REPO_ROOT / "skills" / "brain_tunable_params.json"
        if not p.exists():
            pytest.skip("tunable schema not present")
        schema = json.loads(p.read_text(encoding="utf-8"))
        ids = list((schema.get("params") or {}).keys())
        assert ids, "tunable schema is empty"
        cur = {}
        applied, rejected = apply_strategy_update(
            cur, {i: 1.0 for i in ids})
        assert rejected == [], f"unapplicable tunable ids: {rejected}"
        assert set(applied) == set(ids)

    def test_panel_payload_shape_is_the_dotted_form(self):
        """Pins the payload the panel actually sends (single dotted key)."""
        cur = {}
        pid = "escape.commit_ticks"
        payload = {pid: 125}                     # JSON.stringify({[pid]: v})
        apply_strategy_update(cur, payload)
        assert cur["escape"]["commit_ticks"] == 125
