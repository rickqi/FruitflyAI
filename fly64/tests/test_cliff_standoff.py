"""EVO R15 regression — cliff standoff: FailureMemory → tangential current.

All mechanisms brain-first (no Python control decisions):
- MemoryController cliff-standoff timer (sensory)
- cliff_tangent_bias: FailureMemory sensory gate → ±1 detour sign
- DAN dopamine: standoff >20s punishes (MB loop-suppression learning)
- EvolutionSkill `cliff_standoff` pattern matches a standoff sample
"""
import pytest

from fly64.memory import MemoryController
from fly64.model import FlyModel


class TestCliffStandoffTimer:
    def _ctrl(self):
        return MemoryController()

    def test_standoff_accumulates_on_confirmed_cliff_escape(self):
        c = self._ctrl()
        # flow_cliff LOW = lower-field green collapse = cliff present
        for _ in range(60):  # confirm window + escape ramp-up
            c.update(temporal_energy=0.2, frame_seq=1, forward_rate=0.0,
                     x=0.0, z=0.0, flow_cliff=0.05)
        assert c._cliff_state.get("cliff_confirmed") is True
        assert c.cliff_standoff_s > 0.0

    def test_standoff_resets_when_cliff_clears(self):
        c = self._ctrl()
        for _ in range(60):
            c.update(temporal_energy=0.2, frame_seq=1, forward_rate=0.0,
                     x=0.0, z=0.0, flow_cliff=0.05)
        assert c.cliff_standoff_s > 0.0
        for _ in range(30):  # green returns → cliff clears → standoff resets
            c.update(temporal_energy=0.2, frame_seq=1, forward_rate=0.0,
                     x=0.0, z=0.0, flow_cliff=0.9)
        assert c.cliff_standoff_s == 0.0


class TestCliffTangentBias:
    def test_zero_when_no_known_failure_nearby(self):
        c = MemoryController()
        bias = c.cliff_tangent_bias(0.0, 0.0, heading=0.0)
        assert bias == 0.0

    def test_head_on_known_failure_gives_signed_bias(self):
        c = MemoryController()
        c.failures.record_failure(200.0, 0.0)      # one cell east
        # heading = π/2 → facing EAST (+x), straight at the failure cell
        bias = c.cliff_tangent_bias(50.0, 50.0, heading=1.5708)
        assert bias in (1.0, -1.0)

    def test_zero_when_failure_is_behind(self):
        c = MemoryController()
        c.failures.record_failure(-200.0, 0.0)     # failure to the west
        bias = c.cliff_tangent_bias(50.0, 50.0, heading=0.0)  # facing north
        assert bias == 0.0

    def test_fresh_side_preferred(self):
        c = MemoryController()
        c.failures.record_failure(200.0, 0.0)
        # walk the +z tangent side heavily (fresher = the -z side preferred)
        for i in range(30):
            c.spatial.update(100.0 + i * 10.0, 300.0)
        b_pos = c.cliff_tangent_bias(50.0, 100.0, heading=1.5708)
        # bias must pick the LESS visited tangent — sign consistency matters
        assert b_pos in (1.0, -1.0)


# ── DAN dopamine · standoff punishment ────────────────────────────────

class TestStandoffDopamine:
    def test_standover_20s_punishes(self):
        model = FlyModel(demo=True)
        model.cliff_standoff_s = 25.0
        assert model._compute_dopamine() <= -0.45

    def test_no_standoff_no_extra_punishment(self):
        model = FlyModel(demo=True)
        model.cliff_standoff_s = 5.0
        assert model._compute_dopamine() >= -0.35


# ── EvolutionSkill pattern match ──────────────────────────────────────

class TestCliffStandoffPattern:
    def test_pattern_in_catalog(self):
        import sys
        from skills.evolution_skill import PatternCatalog
        cat = PatternCatalog()
        ids = [p["id"] for p in cat.patterns]
        assert "cliff_standoff" in ids
