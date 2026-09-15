## 🔗 Fly64 5级决策仲裁链因果可视化 — 保险核保与自动驾驶场景

### BPMN 决策因果链: 保险核保场景

```plantuml
@startuml
left to right direction
title 保险核保引擎 — Fly64 5级决策仲裁因果链

' Events
mxgraph.bpmn.event.start "投保申请" as start
mxgraph.bpmn.event.end "标准承保" as end_std
mxgraph.bpmn.event.end "加费承保" as end_load
mxgraph.bpmn.event.end "拒保" as end_reject
mxgraph.bpmn.event.end "升级人工" as end_manual
mxgraph.bpmn.event.messageEnd "欺诈调查" as end_fraud

' Pool: 核保全流程
rectangle "L0: 反射引擎 (50Hz)" as pool0 {
  mxgraph.bpmn.gateway2.exclusive "自动核保\n规则匹配" as gw0
  rectangle "自动通过\n规则引擎" as auto_pass
  rectangle "拒保条件\n命中检查" as reject_check
  rectangle "升级通道" as escalate
}

rectangle "L1: LIF脉冲推理" as pool1 {
  rectangle "CX 16风险因子\n概率分布" as cx_risk
  rectangle "精算惯性\nPERSISTENCE=0.90" as persistence
}

rectangle "L2: 蘑菇体联想学习" as pool2 {
  rectangle "KC-MBON\n5分类决策" as kc_mbon
  rectangle "历史案例\n记忆匹配" as memory_match
}

rectangle "L3: LLM教官" as pool3 {
  rectangle "案件综合评估\n风险报告生成" as llm_review
  rectangle "人工复核\n建议输出" as manual_review
}

rectangle "L4: 降级兜底" as pool4 {
  rectangle "默认承保策略\n保守参数" as fallback
}

' Flow
start --> gw0
gw0 --> auto_pass : "标准规则通过"
gw0 --> reject_check : "风险信号触发"
reject_check --> end_reject : "硬性拒保条件"
reject_check --> escalate : "需进一步评估"
auto_pass --> end_std

escalate --> cx_risk : "CX风险建模"
cx_risk --> persistence
persistence --> kc_mbon : "Tensor→置信度"
kc_mbon --> memory_match : "案例匹配"
memory_match --> llm_review : "置信度<0.7\n激活LLM"
memory_match --> end_load : "置信度≥0.8\n直接输出加费"
memory_match --> end_std : "置信度≥0.9\n直接标准承保"

llm_review --> manual_review
manual_review --> end_manual : "人工决定\n升级/拒保"

cx_risk --> llm_review : "波动>2σ\n异常触发"

memory_match --> fallback : "LLM不可用\n降级"
fallback --> end_load : "保守:加费"

start ..> end_fraud : "反欺诈触发器\n(信息不一致)"

@enduml
```

### BPMN 决策因果链: 自动驾驶安全场景

```plantuml
@startuml
left to right direction
title 自动驾驶感知决策 — Fly64因果链安全架构 (事故责任认定系统)

' Events
mxgraph.bpmn.event.start "传感器输入" as sensor
mxgraph.bpmn.event.end "安全通过" as safe
mxgraph.bpmn.event.errorEnd "事故记录" as accident
mxgraph.bpmn.event.signalEnd "人工接管" as takeover

' Pool: 感知层
rectangle "L0: 反射层 (50Hz)" as pool_ad0 {
  rectangle "τ估计器\n碰撞时间计算" as tau
  mxgraph.bpmn.gateway2.exclusive "AEB阈值\nτ < 1.2s?" as aeb_gw
  rectangle "AEB激活\n紧急制动" as aeb
}

rectangle "L1: LIF决策" as pool_ad1 {
  rectangle "轨迹规划\n连接组动力学" as traj
  mxgraph.bpmn.gateway2.parallel "多轨迹\n评估" as multi_traj
}

rectangle "L2-3: 学习+LLM" as pool_ad2 {
  rectangle "驾驶风格学习\n蘑菇体自适应" as style
  rectangle "LLM场景分析\n复杂交通场景" as llm_scene
}

rectangle "因果链记录" as pool_chain {
  rectangle "Monitor\n70+信号/50Hz" as monitor_chain
  rectangle "trajectory.json\n精确回放" as trace_chain
  rectangle "责任认定\n模块级归因" as liability
  mxgraph.bpmn.gateway2.exclusive "事故\n归因" as cause_gw
}

' Flow
sensor --> tau
tau --> aeb_gw
aeb_gw --> aeb : "是(τ<1.2s)"
aeb_gw --> traj : "否(安全)"
aeb --> monitor_chain : "事件触发"

traj --> multi_traj
multi_traj --> style : "正常驾驶"
multi_traj --> llm_scene : "场景复杂度>阈值"

style --> safe
llm_scene --> safe : "分析通过"

monitor_chain --> trace_chain
trace_chain --> liability
liability --> cause_gw
cause_gw --> accident : "感知失误"
cause_gw --> accident : "决策失误"
cause_gw --> accident : "控制失误"
cause_gw --> takeover : "人类干预"

aeb ..> accident : "AEB触发→事故避免\n但仍记录事件"

' Observability
rectangle "全链路可观测" as obs {
  rectangle "轨迹回放" as replay
  rectangle "时间戳对齐\n50Hz精度" as timestamp
  rectangle "种子64\n确定性复现" as seed64
}
liability --> replay : "事故后调查"
replay --> timestamp
timestamp --> seed64

@enduml
```

### 因果链决策仲裁语义图 (自动驾驶领域)

**五级安全仲裁优先级**:
```
Level 0 (最高) — 反射注入: AEB紧急制动, 50Hz直接电流注入膜电位
   ↓ 反射启动 = 所有下级层级被旁路
Level 1 — LIF脉冲网络: 基于连接组的固有轨迹规划, 持续运行
   ↓ 异常检测 > 2σ 激活快路径
Level 2 — 蘑菇体可塑性: 多巴胺门控的驾驶风格自适应学习
   ↓ 场景复杂度 > 阈值 激活LLM
Level 3 — LLM教官: 复杂交通场景分析, 10秒周期
   ↓ LLM不可用 = 降级
Level 4 (最低) — 局部降级: 默认安全策略 (减速/停车/人工接管请求)
```

**事故溯因确定性证明**:
- 每帧 50Hz 完整状态记录 (70+ telemetry signals)
- `trajectory.json` 精确回放 — 完全确定性的种子64
- 模块级因果归因: 感知模块 或 决策模块 或 控制模块 → 精确定位事故根因
- **法律合规优势**: 唯一具备 完整因果链可追溯性 的AI驾驶系统

**源数据**: t1 §1.3 决策仲裁链 + t1 §5.4 因果链安全系统 + t2 §1.2 ICU异常监控 + t2 §1.4 自我进化