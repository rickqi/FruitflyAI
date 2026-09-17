#!/usr/bin/env python3
"""Append R31-fix9 EVO record — coach→dopamine pathway."""
import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix9" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix9",
    "kind": "brain",
    "brain_version": "2.23.6",
    "skill_version": "3.4.1",
    "trigger": "教练建议完全无法影响多巴胺系统——coach 看见虚空跳冲无效但无法传入奖惩信号",
    "changes": [
        "main.py: load_active_strategy 透传 dopamine 键；主循环将 dopamine.bias → model._coach_dopamine_bias（限幅 ±0.3），setback → add_setback（单次消耗）",
        "model.py: init _coach_dopamine_bias；dopamine 求和时加 bias（clamp [-1,1]）",
        "tests/test_coach_dopamine.py: 7 用例（解析/模型/接线契约）",
    ],
    "tests": "coach_dopamine 7/7 + autonomy 17/17",
    "deployed": True,
    "source": "用户要求教练建议影响训练 → R31-fix9",
})
d["canonical_versions"]["brain"] = "2.23.6"
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix9); canonical -> brain 2.23.6")