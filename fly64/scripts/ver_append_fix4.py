import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix4" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix4",
    "kind": "brain",
    "brain_version": "2.20.4",
    "skill_version": "3.2.0",
    "trigger": "用户指出 fall 状态判定不准确：旧谓词 pos_y<50 or pos_y>500 把合法高处（塔/平台 y 可达 600~2000+）误判为坠落、无垂直速度项、无去抖（_fall_recovery_ticks 是死代码）、单 tick 翻转——'fall' 实际语义只是高度越界",
    "changes": [
        "memory.py StuckDetector: y 历史环形缓冲（16 tick）计算垂直速度 vz",
        "状态三分：FALLING（vz<-120u/s 去抖 3 tick）/ OFF_MAP（y<50 持续 10 tick）/ 高处静止永不为 fallen",
        "fallen 标志语义修正为'真坠落/已掉出地图'；下游 BACKFLIP 触发与 escape_jump_drive 自动受益",
        "tests/test_fall_state_accuracy.py: 6 用例（高台静止/持续下坠/单 tick 去抖/持续越界/高处微动/落地恢复）",
        "tests/test_memory.py: 3 个 stuck 测试显式传 pos_y=120（新契约；顺带修复 P0-3 遗留的 4 个 pos_y=0 默认破损）",
    ],
    "tests": "fall-state 6/6；memory 87 passed（仅剩 2 个基线预存 KeyError）",
    "deployed": True,
    "source": "用户报告 fall 判定不准确 → 准确状态模型（速度+去抖+区分高处）",
})
d["canonical_versions"]["brain"] = "2.20.4"
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix4); canonical -> brain 2.20.4")
