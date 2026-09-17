import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("R31-fix3" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix3",
    "kind": "brain",
    "brain_version": "2.20.3",
    "skill_version": "3.1.1",
    "trigger": "熔岩地移动型困境分析：位移奖励误指定（493u/60s 高速绕圈拿正奖励、coverage 4.1% 纹丝不动、掉血无负 RPE、受击格不在失败记忆）——教练求助门被位移口径正确关闭，但脑模型自身必须学会自治解决；设计原则：运动动作终极目标是简单有效，重复无效受罚、多样尝试受奖、coach 仅兜底",
    "changes": [
        "A: main.py 掉血检测（health 斜率>0 累积>0.02、2s 限速）→ model.add_setback（PPL1 样负 RPE，上限 0.5）——熔岩地绕圈产生负 RPE",
        "B: 受击格写入 FailureMemory.record_failure——自动接入 CX 反失败目标向量与切向绕行",
        "C: report_movement 增加 coverage_rate 进展门控——无新探索的位移奖励 ×0.25（修正奖励误指定根因）",
        "tests/test_r31fix3_reward_reshaping.py: 6 用例（绕圈降奖/负向不缩放/legacy 兼容/累积限速/接线契约/FailureMemory）",
    ],
    "tests": "新用例 6/6 全过；设计原则：所有机制保持单规则简单有效，coach 保持兜底不前置",
    "deployed": True,
    "source": "用户提问'如何用脑模型强化学习机制解决移动型困境'→ R31-fix3 脑机制修复（非教官层规则）",
})
d["canonical_versions"] = {"brain": "2.20.3", "skill": "3.1.1",
                           "as_of": now.isoformat()}
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix3); canonical -> brain 2.20.3")
