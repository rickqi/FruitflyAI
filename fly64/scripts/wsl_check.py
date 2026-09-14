"""Check brain 2.10.0 compatibility for pattern conditions."""
import sys, inspect

sys.path.insert(0, '/root/fly64')

# 1. Model class
import fly64.model as M
print("=== Brain classes ===")
for n, o in inspect.getmembers(M, inspect.isclass):
    if 'rain' in n.lower() or 'odel' in n.lower() or 'model' in n.lower():
        print(f"  {n}")

# Try each candidate to find the main one
main_brain = None
for candidate in ['FlyBrain', 'Fly64Brain', 'Fly64Model', 'BrainModel', 'Brain']:
    if hasattr(M, candidate):
        main_brain = getattr(M, candidate)
        print(f"Found main brain class: {candidate}")
        break

if main_brain:
    print(f"  methods: {[m for m in dir(main_brain) if not m.startswith('_')][:30]}")
    try:
        inst = main_brain()
        for attr in ['fallen', 'cliff_confirmed', 'wall_score', 'ramp_score', 'ground_angle',
                     'danger_red_index', 'emd_on_down', 'target_count',
                     'dopamine_gain_avg', 'learning_progress', 'error_gradient_mean',
                     'gain_update_count', 'mushroom']:
            val = getattr(inst, attr, 'N/A')
            print(f"  {attr}: {val}")
    except Exception as e:
        print(f"  Cannot instantiate: {e}")

# 2. Dopamine gain
if hasattr(M, 'DopamineGain'):
    dg = getattr(M, 'DopamineGain')
    print(f"  DopamineGain: has get_gain={hasattr(dg, 'get_gain') or (any('get_gain' in m for m in dir(dg)))}")

# 3. Memory
import fly64.memory as MM
print("=== Memory classes ===")
for n, o in inspect.getmembers(MM, inspect.isclass):
    if 'Memory' in n or 'Reflex' in n or 'Controller' in n:
        print(f"  {n}")

# 4. Check main.py for SKILL_VERSION
import fly64.main as MAIN
print(f"BRAIN_VERSION: {MAIN.BRAIN_VERSION}")
print(f"SKILL_VERSION: {MAIN.SKILL_VERSION}")