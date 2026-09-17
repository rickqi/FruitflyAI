import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix6" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix6",
    "kind": "brain",
    "brain_version": "2.23.2",
    "skill_version": "3.2.0",
    "trigger": "micro_loop stuck_duration 虚高：R31-fix5 的 cy=30 已产生实际位移（disp_60s>3000u），但 anomaly 分类器只看交替转向模式无视位移 → stuck_duration 持续积压",
    "changes": [
        "memory.py AnomalyDetector._detect_micro_loop: Tier 2 加 disp_60s 门控——当位移>300u 且 loop_score<0.8 时视为'之字形进展'而非微循环，返回 False",
        "disp_60s  threading: _vote → update → MemoryController.anomaly.update，全链路贯通，零新数据源依赖",
        "效果：有进展的交替转向不再被 stuck_duration 锁定，micro_loop 状态自然解除，CPG 原语层重新接管",
    ],
    "tests": "memory/test_fall/test_escape 100 passed；设计原则：简单有效——一行门控条件",
    "deployed": True,
    "source": "实机分析：applied=(-69,30) 已证明之字形推进，分类器语义脱节。",
})
d["canonical_versions"]["brain"] = "2.21.2"
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix6); canonical -> brain 2.21.2")