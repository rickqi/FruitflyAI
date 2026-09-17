import json, urllib.request

def get(ep):
    try:
        return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))
    except Exception as e:
        return {"__error__": str(e)}

m = get("/memory.json")
f = get("/flow.json")
h = get("/help.json")
st = get("/bridge-status.json")
ev = get("/events.json")

print("== bridge ==")
print("pos =", [round(v,1) for v in (st.get("pose") or [])], "game_frame =", st.get("game_frame"), "state =", st.get("state"))
print("== memory ==")
for k in ("stuck_duration","anomaly_state","anomaly_confidence","reflex_active","reflex_type",
          "escape_behavior","forced_bold_explore","health_score","coverage_pct","disp_60s",
          "scene_name","loop_score","reflex_ineffective","cpg"):
    print(f"  {k} =", m.get(k))
print("== flow ==")
for k in ("decision_source","primitive_disp","brain_version","mb_dopamine","mb_mbon_longjump","mb_w_longjump"):
    print(f"  {k} =", f.get(k))
print("== help ==")
print(json.dumps(h, ensure_ascii=False)[:400])
print("== events ==")
cnt = (ev.get("counters") or {})
print("counters =", {k: v for k, v in cnt.items() if 'total' in k})
evs = ev.get("events") or []
print("recent events:", [(e.get("reason"), round(e.get("duration",0),1), e.get("distance_moved")) for e in evs[-6:]])
