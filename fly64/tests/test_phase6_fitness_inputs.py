"""PIN: Phase 6's fitness must read fields the sample ACTUALLY carries.

Defect (EVO-072, measured on 34 instrumented trials): the fitness expression read
four attributes that `SensorSample` does not have —

    coverage_rate        None in 27/27 readings
    first_contact_rate   None in 27/27 readings
    novelty              None in 27/27 readings
    revisit_ratio        absent, so `getattr(..., 0.0)` returned 0.0 in 27/27

`getattr(obj, name, default)` turns a missing field into a SILENT CONSTANT, so
40% of the fitness weight (0.10 novelty + 0.10 speed + 0.10 first_contact + 0.05
revisit) could never move, and coverage_pct (0.30) moved in only 6 of 34 trials.
The pass gate `delta > 0.03` was therefore unreachable: 41-62% of trials scored a
delta of exactly 0.0 and ~94% stayed below the gate, so Phase 6 committed 3 times
in 123 trials.

These tests enforce the correction: every input is derived from a field the
sample carries, `missing_inputs` names anything that had no data, and a real
collector sample must report NO missing inputs — so a silently-defaulted field can
never come back.
"""
import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skills.evolution_skill import BrainMutator, SensorSample  # noqa: E402

#: P1-4 test isolation.  ``BrainMutator.evaluate()`` calls the REAL ``_inject()``,
#: which writes ``skills/active_strategy.json`` and bumps its ``__generation`` —
#: the file the brain hot-reloads and EVO uses to detect foreign rewrites.  Three
#: tests below drive ``evaluate()`` without stubbing the injector, so before this
#: fixture every run of this file polluted live parameter state (measured: +3
#: generations per run, 326 → 332).  The sandbox (fly64/conftest.py) redirects
#: ``SKILL_DIR`` at a temp copy: the real writer stays under test, production does
#: not move.
pytestmark = pytest.mark.usefixtures("sandboxed_skill_dir")


def _sample(**kw):
    """A SensorSample with the fields the COLLECTOR really populates."""
    fields = dict(
        timestamp=1000.0, position=(0.0, 0.0, 0.0), coverage_pct=40.0,
        stuck_duration=10.0, health_score=0.5, loop_score=0.3,
        visited_cells=500, revisit_count=50, forward_speed=0.02,
        anomaly_state="idle",
    )
    fields.update(kw)
    if not hasattr(SensorSample, "__dataclass_fields__"):
        pytest.skip("SensorSample is not a dataclass")
    names = set(SensorSample.__dataclass_fields__)
    return SensorSample(**{k: v for k, v in fields.items() if k in names})


class TestNoSilentDefaults:
    def test_real_sample_reports_no_missing_inputs(self):
        """With both ends of the window supplied, every input must have data.

        `prev` is required for the rate terms: without a previous sample there is
        no window to divide by, so `first_contact_rate(derived)` is legitimately
        absent.  Supplying it is what the trial loop does.
        """
        prev = _sample(timestamp=1000.0, visited_cells=500)
        cur = _sample(timestamp=1120.0, visited_cells=560)
        c = BrainMutator().fitness_components(cur, prev)
        assert c["missing_inputs"] == [], (
            "fitness reads inputs the SensorSample does not carry; the missing "
            "ones are silently zeroed and cannot move: %s" % c["missing_inputs"])

    def test_all_derivation_sources_exist_on_the_real_dataclass(self):
        names = set(SensorSample.__dataclass_fields__)
        for field in ("coverage_pct", "stuck_duration", "health_score",
                      "loop_score", "visited_cells", "revisit_count",
                      "forward_speed", "timestamp"):
            assert field in names, (
                "%s is a derivation source but SensorSample has no such field"
                % field)

    def test_every_field_read_is_derived_from_a_real_attribute(self):
        """Static check: the module must not getattr() the four phantom fields."""
        src = inspect.getsource(BrainMutator.fitness_components)
        for phantom in ("coverage_rate", "first_contact_rate", "novelty",
                        "revisit_ratio"):
            assert ('getattr(sample, "%s"' % phantom) not in src, (
                "%s does not exist on SensorSample; reading it with a default "
                "silently freezes that term" % phantom)

    def test_missing_inputs_are_named_not_hidden(self):
        """A sample lacking the derived sources must say so."""
        s = _sample()
        for f in ("visited_cells", "revisit_count", "loop_score", "forward_speed"):
            if hasattr(s, f):
                setattr(s, f, None)
        if hasattr(s, "visited_cells"):
            setattr(s, "visited_cells", None)
        c = BrainMutator().fitness_components(s)
        assert c["missing_inputs"], (
            "a sample with no derivation sources must report missing inputs")


class TestDerivedTermsActuallyMove:
    def test_coverage_and_health_still_drive_the_score(self):
        m = BrainMutator()
        low = m.fitness(_sample(coverage_pct=10.0, health_score=0.2))
        high = m.fitness(_sample(coverage_pct=45.0, health_score=0.9))
        assert high > low

    def test_revisit_ratio_is_derived_from_real_counters(self):
        m = BrainMutator()
        clean = m.fitness_components(_sample(visited_cells=1000,
                                             revisit_count=0))
        dirty = m.fitness_components(_sample(visited_cells=100,
                                             revisit_count=900))
        assert clean["novelty"] > dirty["novelty"], (
            "novelty must fall as revisits dominate")
        assert dirty["revisit_penalty"] > clean["revisit_penalty"], (
            "the revisit penalty must rise with the derived ratio")

    def test_forward_speed_drives_the_speed_term(self):
        m = BrainMutator()
        slow = m.fitness_components(_sample(forward_speed=0.0))
        fast = m.fitness_components(_sample(forward_speed=0.5))
        assert fast["speed"] > slow["speed"]

    def test_visited_cell_growth_drives_the_rate_term(self):
        m = BrainMutator()
        prev = _sample(timestamp=1000.0, visited_cells=100)
        cur = _sample(timestamp=1120.0, visited_cells=300)
        static = _sample(timestamp=1120.0, visited_cells=100)
        grown = m.fitness_components(cur, prev)
        flat = m.fitness_components(static, prev)
        assert grown["first_contact"] > flat["first_contact"], (
            "gaining visited cells over the window must raise the rate term")
        assert grown["first_contact"] > 0.0

    def test_loop_score_is_the_novelty_fallback(self):
        m = BrainMutator()
        s = _sample()
        c = m.fitness_components(s)
        # revisit counters present -> derived ratio path; loop fallback still ok
        s2 = _sample()
        setattr(s2, "visited_cells", None)
        setattr(s2, "revisit_count", None)
        c2 = m.fitness_components(s2)
        assert c2["novelty"] >= 0.0 and "novelty(derived)" not in c2["missing_inputs"], (
            "loop_score must serve as the novelty fallback")


class TestEvaluateUsesBothSamples:
    def test_evaluate_passes_the_baseline_sample_as_prev(self, monkeypatch):
        import time
        m = BrainMutator()
        base = _sample(timestamp=1000.0, visited_cells=100)
        cur = _sample(timestamp=1120.0, visited_cells=400)
        m._trial = {"exploration.turn_bias": 0.5}
        m._trial_start = time.time() - 200.0
        m._baseline_fitness = m.fitness(base)
        m._baseline_components = m.fitness_components(base)
        m._baseline_sample = base
        monkeypatch.setattr(m, "_inject", lambda cfg: None)

        res = m.evaluate(cur)
        assert res is not None
        raw = res["current_components"]["raw"]
        assert raw.get("prev_visited_cells") == 100, (
            "evaluate must pass the baseline sample so rates can be derived")
        assert raw.get("visited_cells_gained") == 300

    def test_baseline_sample_is_released_with_the_trial(self, monkeypatch):
        import time
        m = BrainMutator()
        s = _sample()
        m._trial = {"exploration.turn_bias": 0.5}
        m._trial_start = time.time() - 200.0
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        m._baseline_sample = s
        monkeypatch.setattr(m, "_inject", lambda cfg: None)
        m.evaluate(s)
        assert m._baseline_sample is None


class TestLegacyOracleIsKept:
    def test_the_pre_fix_expression_is_retained_for_audit(self):
        assert hasattr(BrainMutator, "_legacy_fitness_components"), (
            "keep the pre-EVO-072 expression so the change stays auditable")

    def test_legacy_and_new_agree_when_the_phantom_fields_exist(self):
        """Where the old inputs exist, both formulas must still be comparable."""
        m = BrainMutator()
        s = _sample()
        legacy = m._legacy_fitness_components(s)
        new = m.fitness_components(s)
        # the legacy version zeroes the four phantom terms; the new one derives
        # them, so the new score must be >= the legacy score for the same sample
        legacy_total = (legacy["coverage"] + legacy["unstuck"] + legacy["novelty"]
                        + legacy["health"] + legacy["speed"]
                        + legacy["first_contact"] - legacy["revisit_penalty"])
        new_total = (new["coverage"] + new["unstuck"] + new["novelty"]
                     + new["health"] + new["speed"] + new["first_contact"]
                     - new["revisit_penalty"])
        assert new_total >= legacy_total - 1e-9


# ── Phase 6 EVO-067/071: behavioral fitness + Bayesian opt + short-circuit ──

class TestBehavioralFitnessTerms:
    """EVO-067: displacement coverage and exploration entropy drive fitness."""

    def test_exploration_entropy_in_components(self):
        m = BrainMutator()
        s = _sample(exploration_entropy=0.8)
        c = m.fitness_components(s)
        assert "exploration_entropy" in c, (
            "exploration_entropy term must exist in fitness_components")
        assert c["exploration_entropy"] > 0

    def test_displacement_coverage_in_components(self):
        m = BrainMutator()
        s = _sample(displacement_coverage=0.9)
        c = m.fitness_components(s)
        assert "displacement_coverage" in c, (
            "displacement_coverage term must exist in fitness_components")
        assert c["displacement_coverage"] > 0

    def test_behavioral_terms_respond_to_input(self):
        m = BrainMutator()
        high = _sample(exploration_entropy=1.0, displacement_coverage=1.0)
        low = _sample(exploration_entropy=0.0, displacement_coverage=0.0)
        ch = m.fitness_components(high)
        cl = m.fitness_components(low)
        assert ch["exploration_entropy"] > cl["exploration_entropy"]
        assert ch["displacement_coverage"] > cl["displacement_coverage"]

    def test_behavioral_terms_affect_total_fitness(self):
        m = BrainMutator()
        high = _sample(exploration_entropy=1.0, displacement_coverage=1.0)
        low = _sample(exploration_entropy=0.0, displacement_coverage=0.0)
        assert m.fitness(high) > m.fitness(low)

    def test_components_sum_to_fitness_with_behavioral_terms(self):
        m = BrainMutator()
        s = _sample(exploration_entropy=0.7, displacement_coverage=0.5)
        c = m.fitness_components(s)
        total = (c["coverage"] + c["unstuck"] + c["novelty"] + c["health"]
                 + c["speed"] + c["first_contact"] - c["revisit_penalty"]
                 + c["exploration_entropy"] + c["displacement_coverage"])
        assert m.fitness(s) == round(total, 4), (
            "fitness must equal the sum of ALL components including behavioral terms")


class TestSameSampleShortCircuit:
    """EVO-071: same-sample trial is immediately failed."""

    def test_same_sample_short_circuits(self):
        import time
        m = BrainMutator()
        s = _sample(timestamp=100.0)
        m._trial = {"exploration.turn_bias": 0.3}
        m._trial_start = time.time() - 200.0  # expired window
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        m._baseline_sample = s
        res = m.evaluate(s)  # same object -> same_sample=True
        assert res is not None
        assert res.get("short_circuit") is True, (
            "same-sample must short-circuit the trial")
        assert res.get("delta") == 0.0
        assert res.get("committed") is False

    def test_short_circuit_clears_trial_state(self):
        import time
        m = BrainMutator()
        s = _sample(timestamp=200.0)
        m._trial = {"exploration.turn_bias": 0.3}
        m._trial_start = time.time() - 200.0
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        m._baseline_sample = s
        m.evaluate(s)
        assert m._trial is None
        assert m._baseline_sample is None

    def test_different_sample_does_not_short_circuit(self):
        import time
        m = BrainMutator()
        base = _sample(timestamp=100.0)
        cur = _sample(timestamp=200.0, coverage_pct=50.0)
        m._trial = {"exploration.turn_bias": 0.3}
        m._trial_start = time.time() - 200.0
        m._baseline_fitness = m.fitness(base)
        m._baseline_components = m.fitness_components(base)
        m._baseline_sample = base
        res = m.evaluate(cur)
        assert res is not None
        assert res.get("short_circuit") is None or res.get("short_circuit") is False, (
            "different samples must NOT short-circuit")
        assert res.get("same_sample") is False


class TestBayesianOptimization:
    """EVO-071: generate_candidate uses BO when enough history exists."""

    def test_exploration_phase_gives_uniform_random(self):
        m = BrainMutator()
        c = m.generate_candidate()
        assert isinstance(c, dict)
        assert len(c) > 0
        assert m._bo_exploration_phase is True, (
            "first call with no history must be in exploration phase")

    def test_bo_phase_activates_with_sufficient_history(self):
        m = BrainMutator()
        pids = list(m.live_params.keys())
        for i in range(20):
            params = {pid: 0.1 + 0.8 * (i % 5) / 4.0 for pid in pids}  # varied history
            m._trial_history.append({
                "params": params, "delta": 0.02 * (i % 3),
                "passed": (i % 3) == 0,
            })
        c = m.generate_candidate()
        assert isinstance(c, dict)
        assert len(c) > 0

    def test_candidates_stay_within_param_bounds(self):
        # EVO-072 update: generate_candidate mutates a random SUBSET (k=5 of
        # 39 wired dims); unlisted dims intentionally keep their current
        # active_strategy values.  Assert bounds only for dims the candidate
        # actually mutates — the old full-dim assertion predates subset
        # sampling and KeyError'd on every unselected dim.
        m = BrainMutator()
        for _ in range(10):
            c = m.generate_candidate()
            assert len(c) > 0, "candidate must mutate at least one dim"
            for pid, val in c.items():
                meta = m.live_params[pid]
                mn, mx = meta.get("min", 0.0), meta.get("max", 1.0)
                assert mn <= val <= mx, (
                    "%s value %.4f outside [%.4f, %.4f]" % (pid, val, mn, mx))

    def test_history_is_recorded_after_trial(self):
        import time
        m = BrainMutator()
        before = len(m._trial_history)
        s = _sample(timestamp=300.0)
        m._trial = {"exploration.turn_bias": 0.3}
        m._trial_start = time.time() - 200.0
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        m._baseline_sample = s
        m.evaluate(s)  # same-sample -> short-circuit -> records to history
        assert len(m._trial_history) == before + 1, (
            "trial must be recorded in _trial_history even when short-circuited")


# ── P1-4 (t4): this file must not write production parameter state ──────────

class TestNoProductionStrategyWrites:
    def test_real_injector_writes_the_sandbox_not_production(self, sandboxed_skill_dir):
        """Pin for the write path that used to pollute live EVO state.

        ``evaluate()`` calls the REAL ``_inject()``; before P1-4 that write went
        to ``skills/active_strategy.json`` and bumped its ``__generation`` by one
        per trial — measured live as 326 → 332 (three trials per run of this
        file).  The module-level ``sandboxed_skill_dir`` fixture redirects
        ``SKILL_DIR``, and this test asserts BOTH ends: the injector still writes
        (to the sandbox), and the production file's bytes are untouched.
        """
        import time
        live = REPO_ROOT / "skills" / "active_strategy.json"
        before = live.read_bytes() if live.exists() else None

        m = BrainMutator()
        s = _sample(timestamp=300.0)
        m._trial = {"exploration.turn_bias": 0.3}
        m._trial_start = time.time() - 200.0
        m._baseline_fitness = m.fitness(s)
        m._baseline_components = m.fitness_components(s)
        m._baseline_sample = s
        m.evaluate(s)  # real _inject() runs on this path

        assert (sandboxed_skill_dir / "active_strategy.json").is_file(), (
            "the injector did not write at all — the sandbox is not exercising "
            "the real write path")
        after = live.read_bytes() if live.exists() else None
        assert after == before, (
            "the test modified the LIVE skills/active_strategy.json — production "
            "parameter state (including __generation) must never move in a test")
