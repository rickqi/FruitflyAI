#!/usr/bin/env python3
"""Version discipline: append complete manual record EVO-034 (R24, motor
expansion M1-M3) and update canonical versions to brain 2.19.0 / skill 3.1.0."""
import json
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
# Dynamic id: concurrent sessions append records, so take max(EVO-NNN)+1
import re
max_n = 0
for r in recs:
    mm = re.match(r"EVO-(\d+)$", str(r.get("id", "")))
    if mm:
        max_n = max(max_n, int(mm.group(1)))
new_id = f"EVO-{max_n + 1:03d}"
if any(r.get("trigger", "").startswith("运动原语扩展") for r in recs):
    print("motor expansion record already present; skipping")
    raise SystemExit(0)

now = datetime.now(timezone(timedelta(hours=8)))
record = {
    "id": new_id,
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31",
    "kind": "brain",
    "brain_version": "2.19.0",
    "skill_version": "3.1.0",
    "trigger": "运动原语扩展（motor expansion M1-M3）：B/Z 桥接解锁 + CPG 运动原语层 + strike/crouch 神经池 + MBON 9 列 + 教官原语策略 + WALL/SLIDING 状态 + 踢墙跳/侧空翻 + EVO 原语效果量化 + MBON 学习方向实证与自适应门控",
    "changes": [
        "2.14.0 R-A: 桥接 Z 触发解锁（Z_TRIG 全链路 + b/z 脉冲事件计数，extension 区双向兼容）",
        "2.15.0 R-C/D: motor_primitives.py CPG 运动原语层（级联优先级 4.5）+ pose 状态机 + decision_source=cpg_primitive 归因 + 2s 超时熔断",
        "2.16.0 R-B: strike/crouch 双 20 神经元解码池（motor_splits 4→6 段）+ MBON 5→9 列（原语成败多巴胺塑形）+ set_cpg_gate 电流注入（P1 无旁路 PIN 合规）",
        "2.16.0 Phase4/5: 监控 M1-M4（strike/crouch 曲线/cpg 归因/primitive_disp 遥测）+ EVO primitive_timeout/primitive_zero_disp pattern（13→15 条）+ evolution_skill 惰性种子修复（跨文件版本污染）+ R21 热修回写仓库补丁",
        "2.17.0 M1.1: fix_catalog.json JSON 修复 + EvolutionPipeline history_path 隔离 + P1 直写 KPI 预算化（18→26 附豁免表）",
        "2.17.0 M1.2/1.3: PUNCH/DIVE 门控 + primitives 白名单热开关 + VerificationEngine 原语效果评分（si*0.5+ci*0.2+pi*0.3）",
        "2.18.0 M2.1-2.3: primitives.prefer 场景偏好 + primitive_ineffective 求助触发 + WALL/SLIDING 状态精化 + 踢墙跳/侧空翻原语",
        "2.18.0 M3.1/3.3: mb_w_* 权重均值遥测（场景无关学习方向度量）+ m3_mbon_eval 评估器 + 时间轴 B/Z 刻度 + Escape 表 cpg 事件 + Coach 面板 primitives 展示",
        "2.19.0 M3.2: MBON 辅助长跳门控（longjump_bias>0 时 stuck 阈值 3.0→1.5s，self-paced）",
        "skill 3.1.0: VerificationEngine 原语评分 + EvolutionPipeline history_path + 惰性种子版本追踪 + 惰性种子跨文件污染修复",
    ],
    "tests": "全量回归套件每阶段基线对照零新增失败；新增测试：桥接 6 + CPG 14 + 神经池/MBON 11 + M2 教官/状态机 17 + M3.2 门控 3 + 评分 5；实机验收：ramp_trap 逃逸位移 0u→3797u，MBON longjump 列权重过零转正（-0.00474→+0.00211 单调上行），M3.2 门控激活（3100+ 完成/0 熔断）",
    "deployed": True,
    "source": "AgentTeams fly64-motor-expansion + captain 接管执行（成员 unspawned 降级）",
}
recs.append(record)
d["canonical_versions"] = {"brain": "2.19.0", "skill": "3.1.0",
                           "as_of": now.isoformat()}
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"{new_id} appended; canonical -> brain 2.19.0 / skill 3.1.0; total {len(recs)} records")
