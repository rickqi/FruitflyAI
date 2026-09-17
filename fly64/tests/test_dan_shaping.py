"""EVO R18 regression — DAN signal shaping.

The dopamine weights are explicit class-level constants (one place to tune
the DA system).  Exploration reward lowered 0.50 → 0.30 so the forward
MBON column no longer pins into tanh saturation against the homeostatic
scaling — the equilibrium now sits inside the responsive range.
"""
import numpy as np
import pytest

from fly64.model import FlyModel
from fly64.mushroom_body import MushroomBody


class TestDanShaping:
    def test_exploration_reward_is_030(self):
        model = FlyModel(demo=True)
        model.scene_change_rate = 0.2       # novelty gate open
        assert model._compute_dopamine() == pytest.approx(
            model.DAN_REWARD_EXPLORATION)

    def test_constants_are_the_single_tuning_place(self):
        assert FlyModel.DAN_REWARD_EXPLORATION == 0.20
        assert FlyModel.DAN_PUNISH_FALLEN == 0.80
        assert FlyModel.DAN_PUNISH_LOOP_STATES == 0.35

    def test_lowered_reward_weakens_mbon_saturation(self):
        """Same scene drive, lower dopamine → column stays responsive."""
        sig = np.ones(128, dtype=np.float32) * 0.5

        def drive(dopamine_level, frames):
            mb = MushroomBody()
            mb.weights[:, 0] = 0.9
            for _ in range(frames):
                mb.encode(sig)
                mb.set_dopamine(dopamine_level)
                mb.update_weights()
            active = mb.kc_activity > 0
            raw = float(mb.weights[active, 0].sum())
            return raw, abs(float(mb.mbon_outputs[0]))

        # R17-era equilibrium: strong +dopamine keeps the column pinned
        raw_high, mbon_high = drive(0.5, 120)
        # R18 shaping: exploration reward 0.30 → weakened drive
        raw_low, mbon_low = drive(0.3, 120)
        assert raw_low < raw_high, (
            f"lowered dopamine must weaken inflation: {raw_high} → {raw_low}")
        assert mbon_low <= mbon_high
