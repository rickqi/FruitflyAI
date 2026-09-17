import json, urllib.request

def get(ep):
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))

for i in range(6):
    m = get("/memory.json")
    f = get("/flow.json")
    st = get("/bridge-status.json")
    pose = st.get("pose") or []
    print(f"--- t{i} ---")
    print("anomaly =", m.get("anomaly_state"), "conf =", m.get("anomaly_confidence"),
          "stuck =", round(m.get("stuck_duration",0),1), "loop =", round(m.get("loop_score",0),3))
    print("scene =", m.get("scene_name"), "health =", round(m.get("health_score",1),3),
          "disp_60s =", m.get("disp_60s"), "coverage =", m.get("coverage_pct"))
    print("pose(y高度) =", [round(v,1) for v in pose], "decision =", f.get("decision_source"))
    print("cpg =", f.get("cpg_status"))
    keys = [k for k in m if "fallen" in k.lower() or "fall" in k.lower()]
    print("fallen keys:", {k: m.get(k) for k in keys})
    time.sleep(8)
