"""Comprehensive trajectory and navigation analysis."""
import json, time, urllib.request
import math

def get(ep):
    return json.load(urllib.request.urlopen("http://127.0.0.1:8765" + ep, timeout=5))

# Sample trajectory over 40 seconds
traj = []
for i in range(10):
    st = get("/bridge-status.json")
    m = get("/memory.json")
    f = get("/flow.json")
    ev = get("/events.json") if i == 0 else None
    
    p = st.get("pose") or [0,0,0,0]
    traj.append((p[0], p[1], p[2], p[3], f.get("decision_source"), 
                 m.get("anomaly_state"), round(m.get("stuck_duration",0),1),
                 round(m.get("loop_score",0),3), round(m.get("disp_60s") or 0),
                 st.get("x"), st.get("y"), m.get("health_score")))
    time.sleep(4)

print("=== 轨迹采样 (10点 × 4s = 40s) ===")
print(f"{'x':>8} {'z':>8} {'y':>6} {'yaw':>5} {'decision':>18} {'anomaly':>14} {'stuck':>6} {'loop':>5} {'disp':>6} {'cx':>4} {'cy':>4} {'hp':>5}")
total_d = 0
for i, (x,z,y,yaw,ds,an,st,lo,dp,cx,cy,hp) in enumerate(traj):
    if i > 0:
        dx = traj[i][0] - traj[i-1][0]
        dz = traj[i][2] - traj[i-1][2]
        d = math.hypot(dx, dz)
        total_d += d
    else:
        d = 0
    print(f"{x:>8.0f} {z:>8.0f} {y:>6.0f} {yaw:>5.1f} {ds:>18} {an:>14} {st:>6.1f} {lo:>5.3f} {dp:>6.0f} {cx:>4} {cy:>4} {hp:>5.3f}")
print(f"\n=== 汇总 ===")
print(f"总位移 (40s): {total_d:.0f}u = {total_d/40:.0f}u/s")
print(f"坐标系跨度: X [{min(p[0] for p in traj):.0f}, {max(p[0] for p in traj):.0f}]  Z [{min(p[2] for p in traj):.0f}, {max(p[2] for p in traj):.0f}]")
print(f"决策分布: {set(p[4] for p in traj)}")
print(f"异常分布: {set(p[5] for p in traj)}")

# Coverage / stuck / loop trend
print(f"\n=== 遥测趋势 ===")
print(f"stuck: {traj[0][6]:.1f}s → {traj[-1][6]:.1f}s (Δ={traj[-1][6]-traj[0][6]:+.1f})")
print(f"loop: {traj[0][7]:.3f} → {traj[-1][7]:.3f}  (Δ={traj[-1][7]-traj[0][7]:+.3f})")
print(f"disp: {traj[0][8]:.0f} − {traj[-1][8]:.0f}u/60s")
print(f"health: {traj[0][11]:.3f} → {traj[-1][11]:.3f}")