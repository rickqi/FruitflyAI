"""P1-1 (t1): clamp visibility — coach_applied + clamped_keys.

Live evidence (docs/analysis/analysis-p0-4-live-verification.md §3): the coach
wrote exploration.turn_bias=0.8 / bold_explore_stuck_s=20.0, the brain's
R31-fix12 safety clamp applied 0.25 / 10 and the "P0 self-heal" wrote the
clamped values back to active_strategy.json.  Nothing anywhere said the
suggestion had been dropped — /memory.json had no coach_applied and no
clamped_keys — so "coach 建议未生效" was invisible for days (the EVO-066
family: mechanism exists, reports success, cannot take effect).

These tests pin the visibility contract:

  1. in-range values produce NO clamp record (no false positives)
  2. out-of-range values are reported with requested AND applied
     (0.8 -> 0.25, 20.0 -> 10.0)
  3. coach_applied reports the APPLIED value, never the requested one
  4. each clamp raises a WARNING (never silent)
  5. the report outlives the self-heal that rewrites the file
  6. the /memory.json publish block actually wires both fields in
"""
import json
import logging
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fly64.main import (                                            # noqa: E402
    CLAMP_BOUNDS,
    CLAMP_REPORT_TTL_S,
    CLAMP_SOURCE_WINDOW_S,
    apply_strategy_clamps,
    build_coach_applied,
    clamp_report_update,
    load_active_strategy,
    log_clamp_warnings,
    strategy_writer_source,
)

MAIN_PY = Path(__file__).resolve().parent.parent / "fly64" / "main.py"

TURN_BIAS_KEY = "exploration.turn_bias"
BOLD_KEY = "exploration.bold_explore_stuck_s"


def fake_memory_ctrl(turn_bias, bold_s, escape_s=2.0):
    """Minimal stand-in for MemoryController's coach-facing attributes."""
    return SimpleNamespace(bold_turn_bias=turn_bias,
                           bold_explore_stuck_s=bold_s,
                           escape_stuck_threshold_s=escape_s)


def fake_model(fallen_forward=0.20, fallen_jump_boost=0.60):
    return SimpleNamespace(_fallen_forward=fallen_forward,
                           _fallen_jump_boost=fallen_jump_boost)


def by_key(records):
    return {r["key"]: r for r in records}


# ---------------------------------------------------------------------------
# 1. No false positives
# ---------------------------------------------------------------------------


class TestNoFalsePositive:

    def test_in_range_values_are_not_reported(self):
        section = {"turn_bias": 0.2, "bold_explore_stuck_s": 5}
        records, applied = apply_strategy_clamps(section)
        assert records == []
        assert applied == {"turn_bias": 0.2, "bold_explore_stuck_s": 5}
        # and the values are untouched
        assert section == {"turn_bias": 0.2, "bold_explore_stuck_s": 5}

    @pytest.mark.parametrize("value", [0.0, 0.25, 0.1])
    def test_turn_bias_upper_limit_is_legal(self, value):
        records, applied = apply_strategy_clamps({"turn_bias": value})
        assert records == [], f"{value} is within [0, 0.25] — must not be clamped"
        assert applied["turn_bias"] == value

    @pytest.mark.parametrize("value", [1, 10, 7.5])
    def test_bold_explore_stuck_s_upper_limit_is_legal(self, value):
        records, _ = apply_strategy_clamps({"bold_explore_stuck_s": value})
        assert records == [], f"{value} is within [1, 10] — must not be clamped"

    def test_absent_keys_report_nothing_and_are_not_invented(self):
        section = {}
        records, applied = apply_strategy_clamps(section)
        assert records == []
        assert applied == {}
        assert section == {}, "the clamp must not create keys the file lacks"

    def test_non_numeric_value_does_not_crash_and_is_not_a_clamp(self):
        # A malformed operator file must not take the tick loop down; the
        # caller's .get(key, default) fallback stays in charge.
        section = {"turn_bias": "spin-fast"}
        records, applied = apply_strategy_clamps(section)
        assert records == []
        assert "turn_bias" not in applied
        assert section["turn_bias"] == "spin-fast"


# ---------------------------------------------------------------------------
# 2. Out-of-range values are reported with requested + applied
# ---------------------------------------------------------------------------


class TestClampReported:

    def test_turn_bias_0_8_reports_requested_and_applied(self):
        section = {"turn_bias": 0.8}
        records, applied = apply_strategy_clamps(section)
        rec = by_key(records)[TURN_BIAS_KEY]
        assert rec["requested"] == pytest.approx(0.8)
        assert rec["applied"] == pytest.approx(0.25)
        assert rec["requested"] != rec["applied"]
        # in place: the value the rest of the reload consumes
        assert section["turn_bias"] == pytest.approx(0.25)
        assert applied["turn_bias"] == pytest.approx(0.25)

    def test_bold_explore_stuck_s_20_reports_requested_and_applied(self):
        section = {"bold_explore_stuck_s": 20.0}
        records, applied = apply_strategy_clamps(section)
        rec = by_key(records)[BOLD_KEY]
        assert rec["requested"] == pytest.approx(20.0)
        assert rec["applied"] == pytest.approx(10.0)
        assert applied["bold_explore_stuck_s"] == pytest.approx(10.0)

    def test_both_coach_values_of_the_live_incident(self):
        """Exactly the t=+35 s overwrite from §3.1."""
        section = {"turn_bias": 0.8, "bold_explore_stuck_s": 20.0}
        records, applied = apply_strategy_clamps(section)
        assert len(records) == 2
        assert by_key(records)[TURN_BIAS_KEY]["applied"] == pytest.approx(0.25)
        assert by_key(records)[BOLD_KEY]["applied"] == pytest.approx(10.0)
        assert applied == {"turn_bias": 0.25, "bold_explore_stuck_s": 10.0}

    def test_lower_bounds_are_reported_too(self):
        section = {"turn_bias": -0.5, "bold_explore_stuck_s": 0.2}
        records, _ = apply_strategy_clamps(section)
        recs = by_key(records)
        assert recs[TURN_BIAS_KEY]["applied"] == pytest.approx(0.0)
        assert recs[BOLD_KEY]["applied"] == pytest.approx(1.0)

    def test_thresholds_are_the_production_ones(self):
        """P1-1 must not move the thresholds (that is P1-5's task)."""
        assert CLAMP_BOUNDS[TURN_BIAS_KEY] == (0.0, 0.25)
        assert CLAMP_BOUNDS[BOLD_KEY] == (1.0, 10.0)

    def test_untouched_keys_are_not_reported(self):
        section = {"turn_bias": 0.8, "loop_breakout_threshold": 0.9}
        records, _ = apply_strategy_clamps(section)
        assert [r["key"] for r in records] == [TURN_BIAS_KEY]
        assert section["loop_breakout_threshold"] == 0.9


# ---------------------------------------------------------------------------
# 3. Coach vs EVO/panel attribution (advice_ts + write timing)
# ---------------------------------------------------------------------------


class TestSourceAttribution:

    def test_fresh_advice_ts_identifies_the_coach(self):
        ts = time.time()
        source, age = strategy_writer_source({"advice_ts": ts}, mtime=ts + 0.5)
        assert source == "coach"
        assert age == pytest.approx(0.5, abs=0.01)

    def test_rewrite_after_the_coach_leaves_advice_ts_stale(self):
        """§3.1: values changed at t=+35 s, advice_ts still t=+5 s."""
        ts = time.time() - 35.0
        source, age = strategy_writer_source({"advice_ts": ts},
                                             mtime=time.time())
        assert source == "evo_or_panel"
        assert age == pytest.approx(35.0, abs=0.5)

    def test_window_boundary(self):
        ts = 1_000_000.0
        assert strategy_writer_source({"advice_ts": ts},
                                      mtime=ts + CLAMP_SOURCE_WINDOW_S)[0] == "coach"
        assert strategy_writer_source(
            {"advice_ts": ts},
            mtime=ts + CLAMP_SOURCE_WINDOW_S + 1)[0] == "evo_or_panel"

    def test_missing_advice_ts_is_unknown(self):
        assert strategy_writer_source({})[0] == "unknown"
        assert strategy_writer_source(None)[0] == "unknown"
        assert strategy_writer_source({"advice_ts": "yesterday"})[0] == "unknown"

    def test_now_used_when_mtime_unavailable(self):
        now = time.time()
        source, _ = strategy_writer_source({"advice_ts": now}, now=now)
        assert source == "coach"

    def test_records_carry_the_attribution(self):
        ts = time.time() - 40.0
        records, _ = apply_strategy_clamps(
            {"turn_bias": 0.8}, {"advice_ts": ts}, mtime=time.time())
        assert records[0]["source"] == "evo_or_panel"
        # a fresh coach write is attributed to the coach
        now = time.time()
        records, _ = apply_strategy_clamps(
            {"turn_bias": 0.8}, {"advice_ts": now}, mtime=now)
        assert records[0]["source"] == "coach"
        assert records[0]["advice_age_s"] is not None


# ---------------------------------------------------------------------------
# 4. WARNING on every clamp (never silent)
# ---------------------------------------------------------------------------


class TestWarningLog:

    def test_clamp_logs_one_warning_per_key(self, caplog):
        records, _ = apply_strategy_clamps(
            {"turn_bias": 0.8, "bold_explore_stuck_s": 20.0},
            {"advice_ts": time.time()}, mtime=time.time())
        assert len(records) == 2, "precondition: both values are out of range"
        with caplog.at_level(logging.WARNING, logger="fly64.main"):
            log_clamp_warnings(records)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert any(TURN_BIAS_KEY in r.getMessage() for r in warnings)
        assert any(BOLD_KEY in r.getMessage() for r in warnings)
        joined = "\n".join(r.getMessage() for r in warnings)
        assert "0.25" in joined and "0.8" in joined
        assert "clamped_keys" in joined

    def test_log_helper_is_silent_for_no_records(self, caplog):
        with caplog.at_level(logging.WARNING, logger="fly64.main"):
            log_clamp_warnings([])
            log_clamp_warnings(None)
        assert [r for r in caplog.records if r.levelno == logging.WARNING] == []

    def test_reload_block_is_wired_to_the_warning(self):
        """Wiring guard: the reload only logs when something was clamped."""
        text = MAIN_PY.read_text(encoding="utf-8")
        assert "if _clamp_records:\n                    log_clamp_warnings(" in text
        assert "_clamp_records, _clamp_applied = apply_strategy_clamps(" in text


# ---------------------------------------------------------------------------
# 5. The report outlives the self-heal / reload cycle
# ---------------------------------------------------------------------------


class TestClampReport:

    def test_record_gets_tick_and_wall_time(self):
        records, _ = apply_strategy_clamps({"turn_bias": 0.8})
        report = clamp_report_update([], records, wall_time=1000.0, tick=600)
        assert len(report) == 1
        assert report[0]["tick"] == 600
        assert report[0]["wall_time"] == pytest.approx(1000.0)

    def test_survives_the_reload_that_applies_the_self_heal(self):
        """Reload 1 clamps -> self-heal rewrites 0.25 -> reload 2 sees nothing.

        The *file* no longer holds the coach's request; the report must.
        """
        section = {"turn_bias": 0.8}
        records, applied = apply_strategy_clamps(section)
        report = clamp_report_update([], records, wall_time=1000.0, tick=600)
        # the P0 self-heal writes the clamped value back to the file
        assert section["turn_bias"] == applied["turn_bias"] == pytest.approx(0.25)
        # reload 2: nothing left to clamp ...
        second, _ = apply_strategy_clamps(dict(section))
        assert second == []
        report = clamp_report_update(report, second, wall_time=1012.0, tick=1200)
        # ... but the coach's request is still visible
        assert len(report) == 1
        assert report[0]["requested"] == pytest.approx(0.8)
        assert report[0]["applied"] == pytest.approx(0.25)

    def test_stale_entries_are_dropped(self):
        records, _ = apply_strategy_clamps({"turn_bias": 0.8})
        report = clamp_report_update([], records, wall_time=1000.0, tick=600)
        fresh = clamp_report_update(
            report, [], wall_time=1000.0 + CLAMP_REPORT_TTL_S, tick=1200)
        assert len(fresh) == 1, "an entry right at the TTL is still reported"
        stale = clamp_report_update(
            report, [], wall_time=1000.0 + CLAMP_REPORT_TTL_S + 1, tick=1800)
        assert stale == []

    def test_report_is_capped(self):
        records, _ = apply_strategy_clamps({"turn_bias": 0.8})
        report = []
        for i in range(80):
            report = clamp_report_update(report, records,
                                         wall_time=1000.0 + i, tick=i)
        assert len(report) == 50

    def test_empty_inputs_are_safe(self):
        assert clamp_report_update(None, None, wall_time=1.0, tick=0) == []
        assert clamp_report_update([None, "junk"], [], wall_time=1.0, tick=0) == []


# ---------------------------------------------------------------------------
# 6. One hot-reload cycle end to end (file -> clamp -> consumers -> payload)
# ---------------------------------------------------------------------------


class TestHotReloadCycle:
    """Simulates the 600-tick reload using the real production helpers."""

    @staticmethod
    def _one_reload(tmp_path, strategy, mtime_shift=0.0, tick=600):
        path = tmp_path / "active_strategy.json"
        path.write_text(json.dumps(strategy, ensure_ascii=False),
                        encoding="utf-8")
        # what the reload actually consumes: load_active_strategy() applies
        # the mode/period defaults and passes the sections through
        loaded = load_active_strategy(path)
        raw = json.loads(path.read_text("utf-8"))
        expl = dict(loaded.get("exploration") or {})
        mtime = path.stat().st_mtime + mtime_shift
        records, applied = apply_strategy_clamps(expl, raw, mtime=mtime,
                                                now=time.time())
        # exactly what the reload does with `applied`
        ctrl = fake_memory_ctrl(applied.get("turn_bias", 69.0),
                                applied.get("bold_explore_stuck_s", 60.0))
        payload = {
            "coach_applied": build_coach_applied(loaded, ctrl, fake_model()),
            "clamped_keys": clamp_report_update([], records,
                                                wall_time=time.time(),
                                                tick=tick),
        }
        return expl, applied, payload

    def test_coach_write_of_0_8_is_visible_in_the_payload(self, tmp_path):
        strategy = {
            "exploration": {"turn_bias": 0.8, "bold_explore_stuck_s": 20.0},
            "advice_ts": time.time(),
            "source": "glm-5v-turbo",
            "coach_advice": "爬上右侧岸边",
        }
        expl, _, payload = self._one_reload(tmp_path, strategy)

        clamped = by_key(payload["clamped_keys"])
        assert set(clamped) == {TURN_BIAS_KEY, BOLD_KEY}
        assert clamped[TURN_BIAS_KEY]["requested"] == pytest.approx(0.8)
        assert clamped[TURN_BIAS_KEY]["applied"] == pytest.approx(0.25)
        assert clamped[BOLD_KEY]["requested"] == pytest.approx(20.0)
        assert clamped[BOLD_KEY]["applied"] == pytest.approx(10.0)
        assert clamped[TURN_BIAS_KEY]["source"] == "coach"

        # acceptance: coach_applied reflects what took effect (0.25 / 10),
        # never the coach's original request
        applied_view = payload["coach_applied"]
        assert applied_view["turn_bias"] == pytest.approx(0.25)
        assert applied_view["bold_explore_stuck_s"] == pytest.approx(10.0)
        assert applied_view["turn_bias"] != pytest.approx(0.8)
        assert applied_view["strategy_mode"] == "mirror"   # loader default
        # the file section the rest of the reload consumes is clamped too
        assert expl["turn_bias"] == pytest.approx(0.25)

    def test_in_range_coach_write_is_not_flagged(self, tmp_path):
        strategy = {"exploration": {"turn_bias": 0.2,
                                    "bold_explore_stuck_s": 8.0},
                    "advice_ts": time.time()}
        _, _, payload = self._one_reload(tmp_path, strategy)
        assert payload["clamped_keys"] == []
        assert payload["coach_applied"]["turn_bias"] == pytest.approx(0.2)
        assert payload["coach_applied"]["bold_explore_stuck_s"] == pytest.approx(8.0)

    def test_panel_rewrite_after_the_coach_is_attributed_to_the_panel(
            self, tmp_path):
        strategy = {"exploration": {"turn_bias": 0.8},
                    "advice_ts": time.time() - 100.0}
        _, _, payload = self._one_reload(tmp_path, strategy)
        assert payload["clamped_keys"][0]["source"] == "evo_or_panel"

    def test_missing_advice_ts_is_reported_as_unknown_source(self, tmp_path):
        strategy = {"exploration": {"turn_bias": 0.8}}
        _, _, payload = self._one_reload(tmp_path, strategy)
        assert payload["clamped_keys"][0]["source"] == "unknown"

    def test_memory_json_publish_block_wires_both_fields(self):
        """Wiring guard for the /memory.json site (main.py publish block)."""
        text = MAIN_PY.read_text(encoding="utf-8")
        assert '"coach_applied": build_coach_applied(' in text
        assert '"clamped_keys": _clamped_keys,' in text
        # initialized before the loop so the first publish cannot NameError
        assert "_clamped_keys: list = []" in text
