#!/usr/bin/env python3
"""30-min stability trend: stuck, loop, disp, health, anomaly swings."""
import json, time, urllib.request

def get(ep):
    try:
        return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))
    except Exception:
        return {}

def snapshot():
    m = get("/memory.json")
    f = get("/flow.json")
    st = get("/bridge-status.json")
    pose = st.get("pose") or [0]*4
    return {
        "ts": time.time(),
        "stuck": round(m.get("stuck_duration", 0), 1),
        "anomaly": m.get("anomaly_state", "?"),
        "loop": round(m.get("loop_score", 1), 3),
        "disp": m.get("disp_60s"),
        "health": round(m.get("health_score", 1), 3),
        "decision": f.get("decision_source", "?"),
        "x": round(pose[0], 1),
        "z": round(pose[2], 1),
    }

samples = []
start = time.time()
end = start + 1800  # 30 min
print(f"Tracking {end-start:.0f}s — {'' if time.time() < end else ''}sample every 30s...")
while time.time() < end:
    s = snapshot()
    samples.append(s)
    elapsed = time.time() - start
    print(f"  [{elapsed:6.0f}s] stuck={s['stuck']:6.1f} {s['anomaly']:12s} loop={s['loop']:.3f} disp={str(s['disp']):>6s} hp={s['health']:.3f} {s['decision'][:18]:18s}")
    time.sleep(30)

# Summary
print("\n=== 30min Stability Report ===")
stucks = [s["stuck"] for s in samples if s["stuck"] is not None]
loops = [s["loop"] for s in samples if s["loop"] is not None]
disps = [s["disp"] for s in samples if s["disp"] is not None]
healths = [s["health"] for s in samples if s["health"] is not None]
anomalies = set(s["anomaly"] for s in samples)

print(f"stuck:   {stucks[0]:.0f} → {stucks[-1]:.0f} (min={min(stucks):.0f} max={max(stucks):.0f})")
print(f"loop:    {loops[0]:.3f} → {loops[-1]:.3f} (min={min(loops):.3f} max={max(loops):.3f})")
print(f"disp:    {disps[0]} → {disps[-1]}")
print(f"health:  {healths[0]:.3f} → {healths[-1]:.3f}")
print(f"anomalies seen: {anomalies}")
trend = "STABLE" if stucks[-1] < 120 and anomal != "idle" else "WATCH" if stucks[-1] < 300 else "ISSUE"
print(f"verdict: {trend}")