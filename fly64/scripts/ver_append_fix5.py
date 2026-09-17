import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix5" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix5",
    "kind": "brain",
    "brain_version": "2.21.1",
    "skill_version": "3.2.0",
    "trigger": "用户反馈 Mario 在 micro_loop 反射期间看起来不动 → 分析发现反射相位的交替纯旋转（x=±69,y=0，左右抵消），spin-in-place 的方式虽然走位但不是线性位移",
    "changes": [
        "memory.py ReflexController: MICRO_LOOP 反射 turn 相位 cy=0→cy=30（前向分量）——旋转变成之字形前进",
        "tests/test_memory.py: test_reflex_micro_loop_triggers 期望值 cy=0→30",
    ],
    "tests": "memory 114 passed（仅剩 2 个基线预存 KeyError）；fall-state/escape-release 全绿",
    "deployed": True,
    "source": "用户观察 + captain 实机采样定位到 cy=0 导致的现象",
})
d["canonical_versions"]["brain"] = "2.21.1"
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix5); canonical -> brain 2.21.1")