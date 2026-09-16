"""M1.3: VerificationEngine primitive-outcome scoring (motor expansion)."""
from pathlib import Path

import pytest

from skills.evolution_skill import FixCatalog, VerificationEngine, FixEntry


class FakeCollector:
    """Duck-typed collector returning fixed metrics."""
    def __init__(self, metrics: dict):
        self._m = metrics
    def get_metrics(self) -> dict:
        return dict(self._m)


@pytest.fixture
def engine(tmp_path: Path):
    catalog = FixCatalog(path=tmp_path / "fix_catalog.json")
    catalog.save()
    collector = FakeCollector({
        "stuck_duration": 50.0, "coverage_pct": 10.0,
        "cpg_completed": 5, "cpg_aborted": 1, "primitive_disp": 0.0})
    return VerificationEngine(collector, catalog, window=60), catalog, collector


def _start(engine_tuple):
    eng, catalog, collector = engine_tuple
    entry = catalog.record_fix(FindEntryStub())
    eng.start(entry)
    return eng, entry, collector


class FindEntryStub:
    """Minimal finding-shaped stub for record_fix."""
    pattern_id = "prim_pat"; pattern_name = "Primitive pattern"
    pattern_version = "1.0.0"; severity = "high"
    diagnosis = "d"; fix_template = "# fix"; fix_files = []


def test_no_cpg_activity_score_uses_stuck_coverage_only(engine):
    eng, entry, collector = _start(engine)
    collector._m.update({"stuck_duration": 0.0, "coverage_pct": 10.0,
                         "cpg_completed": 5, "cpg_aborted": 1,
                         "primitive_disp": 0.0})
    eng._start -= 61                       # force window expiry
    r = eng.tick()
    assert r is not None
    assert r.effectiveness_score == pytest.approx(0.5, abs=0.01)   # si=1*0.5
    assert "pi=" in r.details


def test_completion_with_displacement_boosts_score(engine):
    eng, entry, collector = _start(engine)
    # 1 new completion, no aborts, 60u displacement -> pi = min(1, 60/30) = 1
    collector._m.update({"stuck_duration": 50.0, "coverage_pct": 10.0,
                         "cpg_completed": 6, "cpg_aborted": 1,
                         "primitive_disp": 60.0})
    eng._start -= 61
    r = eng.tick()
    assert r.effectiveness_score == pytest.approx(0.3, abs=0.01)   # pi alone
    assert r.passed is True


def test_timeout_abort_cancels_primitive_term(engine):
    eng, entry, collector = _start(engine)
    collector._m.update({"stuck_duration": 50.0, "coverage_pct": 10.0,
                         "cpg_completed": 6, "cpg_aborted": 2,   # +1 abort
                         "primitive_disp": 90.0})
    eng._start -= 61
    r = eng.tick()
    assert r.effectiveness_score == 0.0
    assert r.passed is False


def test_displacement_floor_thirty_units(engine):
    eng, entry, collector = _start(engine)
    collector._m.update({"stuck_duration": 50.0, "coverage_pct": 10.0,
                         "cpg_completed": 6, "cpg_aborted": 1,
                         "primitive_disp": 30.0})                # exactly floor
    eng._start -= 61
    r = eng.tick()
    assert r.effectiveness_score == pytest.approx(0.3, abs=0.01)


def test_baseline_snapshot_contains_cpg_keys(engine):
    eng, entry, collector = _start(engine)
    assert eng._baseline["cpg_completed"] == 5
    assert eng._baseline["cpg_aborted"] == 1
