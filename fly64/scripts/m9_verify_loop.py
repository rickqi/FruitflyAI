"""Verify the complete learning loop end-to-end with live data."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"

def get(ep):
    return json.load(urllib.request.urlopen(BASE + ep, timeout=5))

f = get("/flow.json")
m = get("/memory.json")
st = get("/bridge-status.json")

print("=== 全链路实证：行为→结果→多巴胺→可塑→输出变化===")
print(f"behavior (decision_source): {f.get('decision_source')}")
print(f"outcome (disp_60s): {m.get('disp_60s')}u")
print(f"outcome (health): {round(m.get('health_score',1),3)}")
print(f"outcome (coverage): {m.get('coverage_pct')}%")
print(f"dopamine (mb_dopamine): {round(f.get('mb_dopamine') or 0,4)}")
print(f"plasticity (mb_w_longjump): {round(f.get('mb_w_longjump') or 0,5)}")
print(f"mbon_output (mb_mbon_longjump): {round(f.get('mb_mbon_longjump') or 0,4)}")
print(f"behavior change (cpg gate active): {(f.get('cpg_status') or {}).get('active')}")
print(f"behavior change (M3.2 bonus): {'ACTIVE' if (f.get('mb_mbon_longjump') or 0)>0 else 'inactive'}")
print(f"\nbrain_version: {f.get('brain_version')}")
print(f"pos_y: {round((st.get('pose') or [0,0,0,0])[1],1)}")