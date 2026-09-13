import asyncio, json, struct, urllib.request, collections
import websockets

def get(ep):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:8765/{ep}", timeout=5))

async def sample(duration=8.0):
    srcs = collections.Counter()
    xs = collections.Counter()
    rows_seen = []
    async with websockets.connect("ws://127.0.0.1:8766/") as ws:
        t_end = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < t_end:
            data = await asyncio.wait_for(ws.recv(), 15)
            magic, size = struct.unpack_from("<4sI", data)
            meta = json.loads(data[8:8+size])
            for r in meta["rows"]:
                srcs[r.get("decision_source")] += 1
                xs[r.get("x")] += 1
                if len(rows_seen) < 4:
                    rows_seen.append({k: r.get(k) for k in
                        ("t","forward","left","right","jump","x","y",
                         "flow_asymmetry","flow_looming","flow_cliff","tau" if "tau" in r else "frame_age",
                         "stuck_conf","gate_forward","decision_source")})
    print("decision_source distribution:", dict(srcs))
    print("x distribution (top):", xs.most_common(8))
    for r in rows_seen:
        print("sample:", json.dumps(r, ensure_ascii=False))

m = get("memory.json")
print("memory:", json.dumps({k: m.get(k) for k in
    ("stuck_score","stuck_duration","loop_score","novelty","escape_behavior","fallen",
     "health_score","anomaly_state","visited_cells","coverage_pct","coverage_rate")}, ensure_ascii=False))
f = get("flow.json")
print("flow:", json.dumps({k: f.get(k) for k in
    ("flow_asymmetry","flow_looming","flow_cliff","tau","terrain","wall_score","ramp_score",
     "ground_angle","sky_score","door_frame_score","scene_name")}, ensure_ascii=False, default=str))
ev = get("history.json")
events = ev if isinstance(ev, list) else ev.get("events", [])
print("recent escapes:", json.dumps(events[:5], ensure_ascii=False))
asyncio.run(sample())
