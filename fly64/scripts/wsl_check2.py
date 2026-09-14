"""Check FlyModel attributes for pattern compatibility."""
import inspect, sys
sys.path.insert(0, '/root/fly64')
from fly64.model import FlyModel, TurnAdaptation
from fly64.main import BRAIN_VERSION, SKILL_VERSION

print(f"BRAIN_VERSION={BRAIN_VERSION} SKILL_VERSION={SKILL_VERSION}")

t = TurnAdaptation()
print(f"TurnAdaptation: breakout_gain={t.breakout_gain} has_breakout_drive={hasattr(t,'breakout_drive')} has_counter_drive={hasattr(t,'counter_drive')}")

m = FlyModel()
key_attrs = [
    'fallen', 'cliff_confirmed', 'wall_score', 'ramp_score', 'ground_angle',
    'danger_red_index', 'emd_on_down', 'target_count',
    'dopamine_gain_avg', 'learning_progress', 'error_gradient_mean',
    'gain_update_count', 'mushroom', 'scene_change_rate',
    'flow_asymmetry', 'true_asymmetry', 'heading_rate',
    'step_count', 'terrain', 'reward_signal', 'command_decoupled',
]
for attr in key_attrs:
    val = getattr(m, attr, 'N/A')
    print(f"  {attr}: {val}")

# Check dopamine gain
if hasattr(m, 'dopamine_gain'):
    print(f"  dopamine_gain type: {type(m.dopamine_gain).__name__}")
    dg = m.dopamine_gain
    for sub in ['get_gain', 'get_gains', 'gain']:
        print(f"  dopamine_gain has {sub}: {hasattr(dg, sub)}")
if hasattr(m, 'mushroom'):
    mb = m.mushroom
    print(f"  mushroom type: {type(mb).__name__}")
    for attr in ['assoc_count', 'dopamine', 'mbon_outputs']:
        print(f"  mushroom has {attr}: {hasattr(mb, attr)}")