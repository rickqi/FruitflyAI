import json, time, urllib.request

def mem():
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json", timeout=5))

a = mem()
h0, cov0, x0 = a["health_score"], a["coverage_pct"], (a.get("cell_x"), a.get("cell_z"))
time.sleep(45)
b = mem()
print(f"health: {h0:.3f} -> {b['health_score']:.3f}  ({b['health_score']-h0:+.4f}/45s)")
print(f"coverage: {cov0}% -> {b['coverage_pct']}%")
print(f"stuck: {a['stuck_duration']:.0f}s -> {b['stuck_duration']:.0f}s")
print(f"cell: {x0} -> {(b.get('cell_x'), b.get('cell_z'))}")
print(f"anomaly: {b['anomaly_state']} loop={b['loop_score']}")
