import json, time, urllib.request

def get(ep):
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))

for i in range(5):
    st = get("/bridge-status.json")
    m = get("/memory.json")
    f = get("/flow.json")
    ev = get("/events.json")
    p = st.get("pose") or [0]*4
    print(f"--- t{i} ---")
    print(f"anomaly = {m.get('anomaly_state')} conf={m.get('anomaly_confidence')} stuck={round(m.get('stuck_duration',0),1)}s")
    print(f"scene = {m.get('scene_name')} health={round(m.get('health_score',1),3)}")
    print(f"pos = ({round(p[0],1)}, {round(p[1],1)}, {round(p[2],1)}) yaw={round(p[3],2)}")
    print(f"decision = {f.get('decision_source')} disp_60s={m.get('disp_60s')}u")
    print(f"reflex_active={m.get('reflex_active')} escape={m.get('escape_behavior')} bold={m.get('forced_bold_explore')}")
    print(f"loop_score={round(m.get('loop_score',0),3)} coverage={m.get('coverage_pct')}%")
    print(f"cpg_active={(f.get('cpg_status') or {}).get('active')} completed={(f.get('cpg_status') or {}).get('completed')}")
    print(f"mb_w_longjump={round(f.get('mb_w_longjump') or 0,5)} mb_dopamine={round(f.get('mb_dopamine') or 0,4)}")
    recent = ev.get("events") or []
    if recent:
        print(f"last_event: reason={recent[-1].get('reason')} dur={round(recent[-1].get('duration',0),1)}s dist={round(recent[-1].get('distance_moved',0),1)}u")
    print(f"game_frame={st.get('game_frame')} applied=({st.get('x')}, {st.get('y')}) jump={st.get('jump')}")
    time.sleep(6)