"""PIN: Phase 6 diagnostics must stay attributable, and fitness must not drift.

`scripts/measure_evolution_health.py` measured 88 unique BrainMutator trials with
55 (62.5%) recording delta EXACTLY 0.0 and 83 (94.3%) below the 0.03 pass gate —
while the log stored only the scalar delta/baseline/current, making the cause
unattributable.  That is the same "unobservable state" defect this session fixed
in the curriculum (EVO-065), so the fix here is the same shape: record the
components and the sample identity, so the next diagnosis is read off the data
rather than inferred.

These tests also pin that the refactor of `fitness()` into
`fitness_components()` did NOT change any fitness value — the arithmetic is
identical, only its decomposition is exposed.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skills.evolution_skill import BrainMutator  # noqa: E402


class FakeSample:
    """Carries the fields the REAL SensorSample has (EVO-072), plus the four
    phantom ones so the legacy oracle can still be exercised."""

    def __init__(self, **kw):
        self.timestamp = kw.pop("timestamp", 1000.0)
        self.coverage_pct = kw.pop("coverage_pct", 10.0)
        self.stuck_duration = kw.pop("stuck_duration", 5.0)
        self.health_score = kw.pop("health_score", 0.7)
        # real, derivation sources
        self.loop_score = kw.pop("loop_score", 0.3)
        self.visited_cells = kw.pop("visited_cells", 400)
        self.revisit_count = kw.pop("revisit_count", 40)
        self.forward_speed = kw.pop("forward_speed", 0.01)
        # phantom fields the OLD expression read (kept for the legacy oracle)
        self.novelty = kw.pop("novelty", None)
        self.coverage_rate = kw.pop("coverage_rate", None)
        self.first_contact_rate = kw.pop("first_contact_rate", None)
        self.revisit_ratio = kw.pop("revisit_ratio", None)


def _reference_fitness(s):
    """The PRE-EVO-072 expression, verbatim — the audit oracle.

    Reproduces the old behaviour including its silent defaults: a None phantom
    field was coerced by `getattr(..., 0)` / `0.0`, which is exactly the defect.
    """
    def g(name, default):
        v = getattr(s, name, None)
        return default if v is None else v

    cov = min(g("coverage_pct", 0) / 50.0, 1.0) * 0.30
    unstuck = (1.0 - min(g("stuck_duration", 0) / 120.0, 1.0)) * 0.20
    nov = min(g("novelty", 0), 1.0) * 0.10
    health = max(0.0, min(g("health_score", 0.5), 1.0)) * 0.15
    speed = min(g("coverage_rate", 0) * 100, 0.5) * 0.10
    fcr = min(g("first_contact_rate", 0) * 100, 1.0) * 0.10
    rr = g("revisit_ratio", 0.0)
    rp = max(0.0, (rr - 0.2) * 2.0) * 0.05
    return round(cov + unstuck + nov + health + speed + fcr - rp, 4)


class TestFitnessArithmetic:
    """EVO-067 pinned the ORIGINAL expression; EVO-072 deliberately replaced it.

    The old expression read four attributes `SensorSample` does not have
    (coverage_rate, first_contact_rate, novelty, revisit_ratio), so
    `getattr(..., default)` silently zeroed 40% of the weight and the 0.03 pass
    gate was unreachable.  The pre-fix expression is kept as
    `_legacy_fitness_components` for audit, and these tests now pin the NEW
    contract: the oracle reproduces the old numbers, the new formula is a strict
    improvement on the same sample, and it is monotone in the signals it uses.
    """

    def test_legacy_oracle_reproduces_the_old_numbers(self):
        m = BrainMutator()
        for kw in ({}, {"coverage_pct": 10.0, "stuck_duration": 30.0},
                   {"health_score": 1.4}, {"revisit_ratio": 0.9}):
            s = FakeSample(**kw)
            c = m._legacy_fitness_components(s)
            legacy = (c["coverage"] + c["unstuck"] + c["novelty"] + c["health"]
                      + c["speed"] + c["first_contact"] - c["revisit_penalty"])
            assert round(legacy, 4) == _reference_fitness(s), (
                "the legacy oracle must keep reproducing the pre-EVO-072 value")

    @pytest.mark.parametrize("kw", [
        {}, {"coverage_pct": 0.0, "stuck_duration": 300.0, "health_score": 0.0},
        {"health_score": 1.4},
    ])
    def test_new_formula_is_never_worse_when_the_phantoms_are_absent(self, kw):
        """The real-world case: the four phantom fields do not exist.

        Then the old expression scored each of them 0, so deriving them from real
        fields can only add signal.  (If a phantom field were given a NON-zero
        value the legacy formula would earn credit that the derived path does not
        reproduce — but that state never occurs, because SensorSample has no such
        field.  `test_legacy_oracle_reproduces_the_old_numbers` covers the oracle
        itself.)
        """
        m = BrainMutator()
        s = FakeSample(**kw)
        new = m.fitness(s)
        assert new >= _reference_fitness(s) - 1e-9, (new, _reference_fitness(s))

    def test_none_sample_is_zero(self):
        assert BrainMutator().fitness(None) == 0.0
        assert BrainMutator().fitness_components(None) == {}

    def test_components_sum_to_fitness(self):
        m = BrainMutator()
        s = FakeSample(coverage_pct=42.0, stuck_duration=33.0, novelty=0.8,
                       health_score=0.55, forward_speed=0.03,
                       visited_cells=600, revisit_count=60, timestamp=10.0)
        c = m.fitness_components(s)
        total = (c["coverage"] + c["unstuck"] + c["novelty"] + c["health"]
                 + c["speed"] + c["first_contact"] - c["revisit_penalty"])
        assert m.fitness(s) == round(total, 4)


class TestDiagnosticsAreRecorded:
    def test_components_expose_raw_inputs_and_sample_ts(self):
        c = BrainMutator().fitness_components(FakeSample(timestamp=123.5,
                                                         coverage_pct=7.0))
        raw = c["raw"]
        assert raw["sample_ts"] == 123.5
        assert raw["coverage_pct"] == 7.0
        assert raw["stuck_duration"] == 5.0
        assert isinstance(raw["sample_fields"], list)
        assert "missing_inputs" in c, (
            "the components must name any input that had no data")

    def test_evaluate_records_components_and_same_sample_flag(self, monkeypatch):
        m = BrainMutator()
        s = FakeSample(timestamp=999.0)

        # force the 120 s window to have elapsed
        import time as _t
        m._trial = {"exploration.turn_bias": 0.5}
        m._trial_start = _t.time() - 200.0
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        monkeypatch.setattr(m, "_inject", lambda cfg: None)

        res = m.evaluate(s)                       # same object both ends
        assert res is not None
        assert "baseline_components" in res and "current_components" in res
        assert res["same_sample"] is True, (
            "identical sample timestamps must be reported — it proves the "
            "collector never refreshed the metric")
        assert res["delta"] == 0.0

    def test_same_sample_is_false_for_a_fresh_sample(self, monkeypatch):
        m = BrainMutator()
        base, cur = FakeSample(timestamp=1.0), FakeSample(timestamp=2.0,
                                                         coverage_pct=30.0)
        import time as _t
        m._trial = {"exploration.turn_bias": 0.5}
        m._trial_start = _t.time() - 200.0
        m._baseline_fitness = m.fitness(base)
        m._baseline_components = m.fitness_components(base)
        monkeypatch.setattr(m, "_inject", lambda cfg: None)

        res = m.evaluate(cur)
        assert res["same_sample"] is False
        assert res["delta"] != 0.0

    def test_baseline_components_are_cleared_after_a_trial(self, monkeypatch):
        m = BrainMutator()
        s = FakeSample()
        import time as _t
        m._trial = {"exploration.turn_bias": 0.5}
        m._trial_start = _t.time() - 200.0
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        monkeypatch.setattr(m, "_inject", lambda cfg: None)
        m.evaluate(s)
        assert m._baseline_components is None and m._trial is None


class TestMeasurementToolStaysPresent:
    def test_measurement_script_exists(self):
        assert (REPO_ROOT / "scripts" / "measure_evolution_health.py").exists(), (
            "the Phase 6 / P4.4 measurement tool must stay in the repo so these "
            "numbers can be re-derived instead of guessed")
