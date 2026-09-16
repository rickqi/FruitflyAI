"""
Tests for fallen recovery improvement:
- Forward drive maintained during fallen state
- CPG retry with alternating primitives
"""

import sys
sys.path.insert(0, '.')

import numpy as np
from fly64.model import FlyModel


class TestFallenRecovery:

    def _atlas(self):
        """Minimal valid six-face cube atlas (384x256 RGB)."""
        return np.zeros((256, 384, 3), dtype=np.uint8)

    def test_fallen_forward_drive(self):
        """Fallen state maintains forward drive, not just jump."""
        model = FlyModel(demo=True)
        model.escape_jump_drive = True
        v_before = model.v[model.forward].copy()
        model.step(self._atlas())
        v_after = model.v[model.forward]
        mean_delta = float(np.mean(v_after - v_before))
        assert mean_delta > 0.05, "Forward drive should be present, got %.4f" % mean_delta

    def test_fallen_jump_boost(self):
        """Jump pool receives additional current during fallen."""
        model = FlyModel(demo=True)
        model.escape_jump_drive = True
        v_before = model.v[model.jump_nodes].copy()
        model.step(self._atlas())
        v_after = model.v[model.jump_nodes]
        mean_delta = float(np.mean(v_after - v_before))
        assert mean_delta > 0.3, "Jump boost should be present, got %.4f" % mean_delta

    def test_escape_commit_active_during_fallen(self):
        """Direction commit timer should reset during fallen escape mode."""
        model = FlyModel(demo=True)
        model.escape_mode = True
        model._escape_commit_timer = 0
        model.step(self._atlas())
        assert model._escape_commit_timer > 0, "Escape commit should activate"
        assert abs(model._escape_commit_dir) > 0, "Commit direction should be non-zero"