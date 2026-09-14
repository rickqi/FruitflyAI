from fly64.model import TurnAdaptation
t = TurnAdaptation()
print("breakout_gain:", t.breakout_gain)
print("has breakout_drive:", hasattr(t, 'breakout_drive'))
print("has counter_drive:", hasattr(t, 'counter_drive'))
print("breakout_drive result:", t.breakout_drive())
print()

from fly64.main import BRAIN_VERSION, SKILL_VERSION
print("BRAIN_VERSION:", BRAIN_VERSION)
print("SKILL_VERSION:", SKILL_VERSION)
print()

from fly64.model import Fly64Brain
m = Fly64Brain()
for attr in ['fallen', 'cliff_confirmed', 'wall_score', 'ramp_score', 'ground_angle',
             'danger_red_index', 'emd_on_down', 'target_count',
             'dopamine_gain_avg', 'learning_progress', 'error_gradient_mean', 'gain_update_count']:
    print(f'{attr}:', getattr(m, attr, 'N/A'))
print('mushroom:', getattr(m, 'mushroom', 'N/A'))