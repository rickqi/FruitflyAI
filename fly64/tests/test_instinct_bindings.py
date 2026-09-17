"""PIN tests: scene -> strategy instinct bindings (P4.4, t7/t9).

Promotion rule: >= PROMOTE_MIN_IMPROVED clean improvements *since the last
worse*, matched on a quantized SALIENT signature (not the full parameter dict —
see the module docstring and TestSalientSignature for why).  A `worse` verdict
falsifies: it demotes a promoted binding and zeroes the improvement counter.
The brain reads promoted bindings on hot-reload and applies them directly
(instinct overrides the coach for that scene).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fly64 import instinct_bindings as ib  # noqa: E402


def _keys(threshold=10.0, bias=0.8, mode="directional_climb", **extra):
    k = {
        "exploration": {"bold_explore_stuck_s": 20.0, "turn_bias": bias},
        "escape": {"stuck_threshold_s": threshold},
        "fallen_recovery": {"mode": mode},
        "what_i_see": ["irrelevant section"],
    }
    k.update(extra)
    return k


class TestSceneKey:
    def test_prefix_before_hash(self):
        assert ib.scene_key("致命熔岩地 #f3f9") == "致命熔岩地"
        assert ib.scene_key("石块堡垒") == "石块堡垒"
        assert ib.scene_key("") == ""
        assert ib.scene_key(None) == ""

    def test_extract_params_keeps_only_bound_sections(self):
        p = ib.extract_params(_keys())
        assert set(p) == {"exploration", "escape", "fallen_recovery"}
        assert "what_i_see" not in p


class TestBindingParamsCoherence:
    """The bound params must be exactly what the signature discriminates.

    Otherwise two outcomes could share a signature while implying different
    behaviour, and the brain would apply an instinct the evidence never tested.
    """

    def test_only_salient_keys_are_bound(self):
        p = ib.binding_params(_keys())
        assert set(p) == {"exploration", "escape", "fallen_recovery"}
        assert set(p["exploration"]) == {"turn_bias"}
        assert set(p["escape"]) == {"stuck_threshold_s"}
        assert set(p["fallen_recovery"]) == {"mode"}

    def test_non_salient_keys_are_not_bound(self):
        p = ib.binding_params(_keys())
        assert "reverse_seconds" not in p.get("escape", {})
        assert "bold_explore_stuck_s" not in p.get("exploration", {})

    def test_every_bound_key_is_discriminated_by_the_signature(self):
        for section, key, _q in ib.SALIENT_PARAMS:
            assert key in ib.binding_params(_keys())[section], (
                f"{section}.{key} is in SALIENT_PARAMS but not bound")

    def test_bound_keys_are_stable_across_a_signature_class(self):
        """Two inputs sharing a signature must yield identical bound params."""
        a = _keys(bias=0.81, escape={"stuck_threshold_s": 10.0,
                                     "reverse_seconds": 0.5})
        b = _keys(bias=0.79, escape={"stuck_threshold_s": 10.0,
                                     "reverse_seconds": 0.9})
        assert ib.salient_signature(a) == ib.salient_signature(b)
        assert ib.binding_params(a) == ib.binding_params(b)


class TestSalientSignature:
    """t9 root cause: the exact fingerprint can never accumulate evidence."""

    def test_episode_specific_knobs_do_not_split_the_signature(self):
        a = _keys(command={"type": "turn_and_go", "heading": 180, "duration_s": 3.0})
        b = _keys(command={"type": "turn_and_go", "heading": 270, "duration_s": 1.5})
        assert ib.salient_signature(a) == ib.salient_signature(b), (
            "command heading/duration must not fragment the signature")

    def test_low_impact_section_params_do_not_split_the_signature(self):
        a = _keys(escape={"stuck_threshold_s": 10.0, "reverse_seconds": 0.5})
        b = _keys(escape={"stuck_threshold_s": 10.0, "reverse_seconds": 0.9})
        assert ib.salient_signature(a) == ib.salient_signature(b), (
            "reverse_seconds must not fragment the signature")

    def test_small_numeric_jitter_is_absorbed(self):
        assert (ib.salient_signature(_keys(bias=0.81))
                == ib.salient_signature(_keys(bias=0.79)))

    def test_behaviour_driving_params_still_discriminate(self):
        assert (ib.salient_signature(_keys(bias=0.8))
                != ib.salient_signature(_keys(bias=0.3)))
        assert (ib.salient_signature(_keys(mode="mirror"))
                != ib.salient_signature(_keys(mode="directional_climb")))
        assert (ib.salient_signature(_keys(threshold=5.0))
                != ib.salient_signature(_keys(threshold=99.0)))

    def test_signature_is_stable_and_textual(self):
        s = ib.salient_signature(_keys())
        assert s == ib.salient_signature(_keys())
        assert "fallen_recovery.mode=directional_climb" in s

    def test_missing_sections_do_not_raise(self):
        assert ib.salient_signature({}) == ib.salient_signature({})
        assert "None" in ib.salient_signature({})


class TestPromotion:
    def test_single_improvement_does_not_promote(self, tmp_path):
        path = tmp_path / "b.json"
        row = ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        assert row["improved"] == 1 and row["promoted"] is False
        assert ib.get_binding("熔岩地 #a1", path=path) is None

    def test_two_improvements_promote(self, tmp_path):
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        row = ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        assert row["improved"] == 2 and row["promoted"] is True
        binding = ib.get_binding("熔岩地 #b2", path=path)   # hash drift ok
        assert binding is not None
        assert binding["exploration"]["turn_bias"] == 0.8

    def test_worse_demotes(self, tmp_path):
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        assert ib.get_binding("熔岩地 #a1", path=path) is not None
        ib.record_outcome("熔岩地 #a1", _keys(), "worse", {}, path=path)
        assert ib.get_binding("熔岩地 #a1", path=path) is None

    def test_worse_is_falsification_and_resets_the_counter(self, tmp_path):
        """A contradicted signature must re-earn promotion on fresh evidence."""
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        row = ib.record_outcome("熔岩地 #a1", _keys(), "worse", {}, path=path)
        assert row["improved"] == 0, "worse must zero the improvement evidence"
        assert row["worse"] == 1
        assert row["total_improved"] == 1, "audit total must be preserved"
        assert row["total_worse"] == 1

    def test_repromotes_after_fresh_clean_evidence(self, tmp_path):
        path = tmp_path / "b.json"
        for verdict in ("improved", "improved", "worse"):
            ib.record_outcome("熔岩地 #a1", _keys(), verdict, {}, path=path)
        assert ib.get_binding("熔岩地 #a1", path=path) is None
        ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        assert ib.get_binding("熔岩地 #a1", path=path) is None
        row = ib.record_outcome("熔岩地 #a1", _keys(), "improved", {}, path=path)
        assert row["promoted"] is True
        assert ib.get_binding("熔岩地 #a1", path=path) is not None

    def test_unchanged_outcomes_do_not_promote(self, tmp_path):
        path = tmp_path / "b.json"
        for _ in range(5):
            row = ib.record_outcome("熔岩地 #a1", _keys(), "unchanged", {},
                                    path=path)
        assert row["promoted"] is False and row["unchanged"] == 5

    def test_param_change_restarts_evidence(self, tmp_path):
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a1", _keys(threshold=5.0), "improved", {},
                          path=path)
        row = ib.record_outcome("熔岩地 #a1", _keys(threshold=99.0),
                                "improved", {}, path=path)
        assert row["improved"] == 1, "changed parameter set must restart evidence"
        assert row["promoted"] is False

    def test_competing_signatures_do_not_share_evidence(self, tmp_path):
        """Two parameter sets for one scene are two separate claims."""
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a1", _keys(bias=0.9), "improved", {}, path=path)
        row = ib.record_outcome("熔岩地 #a1", _keys(bias=0.8), "improved", {},
                                path=path)
        assert row["improved"] == 1, "evidence leaked across signatures"
        assert ib.get_binding("熔岩地 #a1", path=path) is None
        assert ib.binding_status(path)["signatures"] == 2

    def test_two_exact_improvements_plus_a_worse_in_the_same_run_never_promote(
            self, tmp_path):
        """Mirrors the recorded real-data candidate 2 improved / 1 worse."""
        path = tmp_path / "b.json"
        for verdict in ("improved", "improved", "worse"):
            row = ib.record_outcome("熔岩地 #a1", _keys(), verdict, {}, path=path)
        assert row["promoted"] is False
        assert ib.get_binding("熔岩地 #a1", path=path) is None

    def test_no_keys_no_binding(self, tmp_path):
        path = tmp_path / "b.json"
        assert ib.record_outcome("熔岩地 #a1", {}, "improved", {}, path=path) is None
        assert ib.record_outcome("", _keys(), "improved", {}, path=path) is None

    def test_unknown_verdict_counted_as_unchanged(self, tmp_path):
        path = tmp_path / "b.json"
        row = ib.record_outcome("x #1", _keys(), "bogus", {}, path=path)
        assert row["unchanged"] == 1 and row["promoted"] is False


class TestPersistence:
    def test_roundtrip_and_summary(self, tmp_path):
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a", _keys(), "improved", {}, path=path)
        ib.record_outcome("熔岩地 #a", _keys(), "improved", {}, path=path)
        ib.record_outcome("堡垒 #b", _keys(bias=0.3), "unchanged", {}, path=path)
        s = ib.summary(path=path)
        assert s["scenes"] == 2 and s["promoted"] == 1
        assert s["rows"][0]["scene"] == "熔岩地"

    def test_corrupt_file_yields_empty(self, tmp_path):
        path = tmp_path / "b.json"
        path.write_text("{not json", encoding="utf-8")
        assert ib.load_bindings(path) == {}
        # and a new outcome can still be recorded
        row = ib.record_outcome("x #1", _keys(), "improved", {}, path=path)
        assert row is not None

    def test_last_deltas_recorded(self, tmp_path):
        path = tmp_path / "b.json"
        row = ib.record_outcome("x #1", _keys(), "improved",
                                {"disp_60s": 1234.5}, path=path)
        assert row["last_deltas"]["disp_60s"] == 1234.5

    def test_file_is_valid_json_and_only_salient_keys_persisted(self, tmp_path):
        path = tmp_path / "b.json"
        ib.record_outcome("x #1", _keys(), "improved", {}, path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data["x"]
        bucket = next(iter(entry["buckets"].values()))
        assert set(bucket["params"]) == {"exploration", "escape", "fallen_recovery"}
        assert bucket["params"]["exploration"] == {"turn_bias": 0.8}
        assert "what_i_see" not in bucket["params"]

    def test_legacy_flat_shape_is_migrated_not_crashed(self, tmp_path):
        """A pre-t9 file must stay readable instead of silently resetting."""
        path = tmp_path / "b.json"
        path.write_text(json.dumps({
            "熔岩地": {"scene": "熔岩地", "fingerprint": "old", "params": {
                "exploration": {"turn_bias": 0.8},
                "escape": {"stuck_threshold_s": 10.0},
                "fallen_recovery": {"mode": "directional_climb"}},
                "improved": 3, "unchanged": 0, "worse": 0, "promoted": True},
        }, ensure_ascii=False), encoding="utf-8")
        assert ib.get_binding("熔岩地", path=path) is not None, (
            "legacy promoted binding was lost on migration")
        row = ib.record_outcome("熔岩地", _keys(), "improved", {}, path=path)
        assert row is not None


class TestBindingStatus:
    """Negative-result surface: why promotion is (not) happening."""

    def test_reports_distance_to_promotion(self, tmp_path):
        path = tmp_path / "b.json"
        ib.record_outcome("熔岩地 #a", _keys(), "improved", {}, path=path)
        st = ib.binding_status(path=path)
        assert st["promoted"] == 0
        row = st["rows"][0]
        assert row["improved"] == 1 and row["needed"] == 1
        assert row["qualifies"] is False

    def test_promoted_signature_is_reported(self, tmp_path):
        path = tmp_path / "b.json"
        for _ in range(ib.PROMOTE_MIN_IMPROVED):
            ib.record_outcome("熔岩地 #a", _keys(), "improved", {}, path=path)
        st = ib.binding_status(path=path)
        assert st["promoted"] == 1 and st["qualifying"] == 1
        assert st["rows"][0]["promoted"] is True

    def test_empty_file_is_not_an_error(self, tmp_path):
        st = ib.binding_status(tmp_path / "missing.json")
        assert st["scenes"] == 0 and st["rows"] == []
