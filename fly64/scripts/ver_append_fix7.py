import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix7" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix7",
    "kind": "brain",
    "brain_version": "2.23.3",
    "skill_version": "3.3.0",
    "trigger": "fallen 状态下 Mario 卡在地图下方 y=-954，固定 1.5s 跳冲无法复位（depth too extreme）",
    "changes": [
        "main.py below-ground 逃逸：burst duration 从固定 1.5s 改为自适应（深度因子 +3s/500u + stuck 累积因子 +30s max）+ 轻微 x 摇摆找地形边缘",
        "最大持续 12s 后停止，防止永久锁定",
    ],
    "tests": "编译通过；实机验证 fallen 逃逸",
    "deployed": True,
    "source": "实机 fallen 场景触动优化",
})
d["canonical_versions"]["brain"] = "2.23.3"
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix7); canonical -> brain 2.23.3")