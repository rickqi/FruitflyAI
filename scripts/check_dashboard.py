import urllib.request, json, sys

print("=== Bridge Status ===")
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/bridge-status.json', timeout=5)
    bs = json.loads(r.read())
    for k, v in bs.items():
        print(f"  {k}: {v}")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=== Memory ===")
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/memory.json', timeout=5)
    mem = json.loads(r.read())
    for k in ['scene_label', 'health_score', 'coverage_pct', 'stuck_duration',
              'anomaly_state', 'loop_score', 'scene_id']:
        print(f"  {k}: {mem.get(k, 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=== Neural Flow ===")
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/flow.json', timeout=5)
    flow = json.loads(r.read())
    for k in ['decision_source', 'forward_rate', 'turn_rate', 'jump_rate',
              'wall_score', 'ramp_score', 'gate_forward', 'gate_jump',
              'mb_mbon_forward', 'game_frame']:
        if k in flow:
            print(f"  {k}: {flow[k]}")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=== Events ===")
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/events.json', timeout=5)
    ev = json.loads(r.read())
    if isinstance(ev, dict):
        for k in ['total_escapes', 'effective_count', 'ineffective_count',
                  'total_falls', 'total_cliff_escapes', 'total_stuck_escapes']:
            print(f"  {k}: {ev.get(k, 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")