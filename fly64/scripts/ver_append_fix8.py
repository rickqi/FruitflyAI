#!/usr/bin/env python3
"""Append R31-fix8 EVO record."""
import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix8" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix8",
    "kind": "brain",
    "brain_version": "2.23.5",
    "skill_version": "3.3.0",
    "trigger": "教练建议的 command.turn_and_go 是死键码——prompt 要求教练输出但脑模型从未消费；y=-954 虚空场景教练不知高度",
    "changes": [
        "main.py: 读取 active_strategy.command 实现 P-I 转向+前冲（heading→yaw_diff→x, y 持续, 限时, 虚空让位于护栏）",
        "plugin/runner.py: consult context +pos_y（优先 memory_json.pos_y → position.y），三次求助路径一致",
        "main.py memory_json: +pos_y 键——教练 consulter 可读",
    ],
    "tests": "autonomy 17 passed; 编译全检查",
    "deployed": True,
    "source": "实机 fallen 虚空场景教练建议无效分析→双修复",
})
d["canonical_versions"]["brain"] = "2.23.5"
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix8); canonical -> brain 2.23.5")