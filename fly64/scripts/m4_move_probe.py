import json, time, urllib.request

def get(ep):
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))

prev = None
for i in range(6):
    st = get("/bridge-status.json")
    f = get("/flow.json")
    m = get("/memory.json")
    p = st.get("pose") or [0]*4
    row = (round(p[0],1), round(p[2],1), st.get("game_frame"),
           f.get("decision_source"), st.get("x"), st.get("y"), st.get("jump"),
           m.get("anomaly_state"), round(m.get("stuck_duration",0),1),
           round(m.get("disp_60s") or 0))
    if prev:
        d = ((p[0]-prev[0])**2 + (p[2]-prev[2])**2) ** 0.5
        print(row, f"move={d:.1f}u/8s")
    else:
        print(row)
    prev = p
    time.sleep(8)
