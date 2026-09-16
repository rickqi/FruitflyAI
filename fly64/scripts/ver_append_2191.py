#!/usr/bin/env python3
"""Append the 2.19.1 dopamine-floor fix record (dynamic EVO id)."""
import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("dopamine floor" in str(r.get("trigger", "")) for r in recs):
    print("record already present; skipping")
    raise SystemExit(0)
max_n = max((int(m.group(1)) for r in recs
             for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
record = {
    "id": f"EVO-{max_n + 1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix",
    "kind": "brain",
    "brain_version": "2.19.1",
    "skill_version": "3.1.0",
    "trigger": "M3.2 采样发现：原语完成时刻 dopamine 均值 -0.55（+0.6 成功脉冲被并发行为 setback 淹没），成功联想被负信号压制",
    "changes": [
        "model.py add_primitive_outcome: 成功脉冲设置 _success_pulse_floor=0.2",
        "model.py step(): 完成 tick 的总 dopamine 下限抬到 +0.2（单发消费）——成功联想不再因并发 setback 被学成负值",
        "tests/test_m32_dopamine_floor.py: 4 用例（保底/失败通路/单发/端到端列不 depressed）",
    ],
    "tests": "test_m32_dopamine_floor 4/4 + 神经池/门控回归 14/14",
    "deployed": True,
    "source": "M3.2 数据驱动修复（40min 采样分析）",
}
recs.append(record)
d["canonical_versions"] = {"brain": "2.19.1", "skill": "3.1.0",
                           "as_of": now.isoformat()}
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"{record['id']} appended; canonical -> brain 2.19.1")
