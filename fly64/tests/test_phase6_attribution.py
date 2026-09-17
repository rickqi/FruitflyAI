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
    def __init__(self, **kw):
        self.timestamp = kw.pop("timestamp", 1000.0)
        self.coverage_pct = kw.pop("coverage_pct", 10.0)
        self.stuck_duration = kw.pop("stuck_duration", 5.0)
        self.novelty = kw.pop("novelty", 0.5)
        self.health_score = kw.pop("health_score", 0.7)
        self.coverage_rate = kw.pop("coverage_rate", 0.01)
        self.first_contact_rate = kw.pop("first_contact_rate", 0.002)
        self.revisit_ratio = kw.pop("revisit_ratio", 0.1)


def _reference_fitness(s):
    """The pre-refactor expression, verbatim — the equivalence oracle."""
    cov = min(getattr(s, "coverage_pct", 0) / 50.0, 1.0) * 0.30
    unstuck = (1.0 - min(getattr(s, "stuck_duration", 0) / 120.0, 1.0)) * 0.20
    nov = min(getattr(s, "novelty", 0), 1.0) * 0.10
    health = max(0.0, min(getattr(s, "health_score", 0.5), 1.0)) * 0.15
    speed = min(getattr(s, "coverage_rate", 0) * 100, 0.5) * 0.10
    fcr = min(getattr(s, "first_contact_rate", 0) * 100, 1.0) * 0.10
    rr = getattr(s, "revisit_ratio", 0.0)
    rp = max(0.0, (rr - 0.2) * 2.0) * 0.05
    return round(cov + unstuck + nov + health + speed + fcr - rp, 4)


class TestFitnessIsUnchangedByTheRefactor:
    @pytest.mark.parametrize("kw", [
        {},
        {"coverage_pct": 0.0, "stuck_duration": 300.0, "health_score": 0.0},
        {"coverage_pct": 100.0, "novelty": 1.0, "coverage_rate": 0.5,
         "first_contact_rate": 0.2, "revisit_ratio": 0.9},
        {"novelty": -0.3, "health_score": 1.4, "revisit_ratio": 0.2},
        {"revisit_ratio": 0.2000001},
    ])
    def test_matches_the_pre_refactor_expression(self, kw):
        m = BrainMutator()
        s = FakeSample(**kw)
        assert m.fitness(s) == _reference_fitness(s)

    def test_none_sample_is_zero(self):
        assert BrainMutator().fitness(None) == 0.0
        assert BrainMutator().fitness_components(None) == {}

    def test_components_sum_to_fitness(self):
        m = BrainMutator()
        s = FakeSample(coverage_pct=42.0, stuck_duration=33.0, novelty=0.8,
                       health_score=0.55, coverage_rate=0.03,
                       first_contact_rate=0.004, revisit_ratio=0.35)
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
