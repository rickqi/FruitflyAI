import json, time, urllib.request

def get(ep):
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))

for i in range(6):
    m = get("/memory.json")
    f = get("/flow.json")
    st = get("/bridge-status.json")
    p = st.get("pose") or [0]*4
    app_x, app_y = st.get("x"), st.get("y")
    print(f"--- t{i} ---")
    print(f"anomaly={m.get('anomaly_state')} conf={m.get('anomaly_confidence')} stuck={round(m.get('stuck_duration',0),1)}s")
    print(f"pos=({round(p[0],1)},{round(p[2],1)}) yaw={round(p[3],2)} y={round(p[1],1)}")
    print(f"applied=({app_x},{app_y}) jump={st.get('jump')} frame={st.get('game_frame')}")
    print(f"decision={f.get('decision_source')} disp={m.get('disp_60s')}u health={round(m.get('health_score',1),3)}")
    print(f"reflex={m.get('reflex_active')} escape={m.get('escape_behavior')} loop={round(m.get('loop_score',3),3)}")
    print(f"cpg=({(f.get('cpg_status') or {}).get('completed')}) scene={m.get('scene_name')}")
    time.sleep(5)