# T4: 混合架构设计方案 — 脑模型+DSH插件+36 Agent三层融合

> **作者**: hybrid-architect  
> **日期**: 2026-09-07  
> **依赖**: T1 (gbcost-analysys深度解构) + T2 (Fly64脑模块→保险能力映射) + T3 (DSH插件集成分析)  
> **参考**: gbcost-analysys 36 Agent / LangGraph StateGraph / 19 DSH tools / Fly64 166,700神经元脑模型

---

## 目录

1. [总体架构概述](#1-总体架构概述)
2. [感知层 — Fly64脑模型取代/增强](#2-感知层--fly64脑模型取代增强)
3. [决策层 — 5级混合仲裁链](#3-决策层--5级混合仲裁链)
4. [执行层 — DSH插件与Web集成](#4-执行层--dsh插件与web集成)
5. [数据流设计](#5-数据流设计)
6. [状态管理 — AgentState扩展](#6-状态管理--agentstate扩展)
7. [部署架构 — 三进程拓扑](#7-部署架构--三进程拓扑)
8. [组件接口规格](#8-组件接口规格)
9. [实施路线图与里程碑](#9-实施路线图与里程碑)
10. [风险与缓解](#10-风险与缓解)

---

## 1. 总体架构概述

### 1.1 三层融合架构图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            BRAIN-INSURANCE HYBRID ARCHITECTURE                       │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                          🧠 感知层 (Perception Layer)                         │    │
│  │                         脑模型原生感知与特征提取                               │    │
│  │                                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │    │
│  │  │ 复眼Retina │  │ 光流Flow  │  │场景记忆    │  │蘑菇体MB   │  │ 中央复合体CX │ │    │
│  │  │ 多源采样   │  │ 趋势检测  │  │ Scene     │  │ 稀疏编码  │  │ 环形罗盘    │ │    │
│  │  │ ON/OFF通道│  │ 自运动分离│  │ Memory   │  │ KC 5%激活│  │ 4层下钻    │ │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘ │    │
│  │       │              │             │             │               │         │    │
│  │       └──────────────┴─────────────┴─────────────┴───────────────┘         │    │
│  └──────────────────────────────────┬─────────────────────────────────────────────┘    │
│                                     │                                                  │
│  ┌──────────────────────────────────▼─────────────────────────────────────────────┐    │
│  │                         ⚖️ 决策层 (Decision Layer)                              │    │
│  │                         5级混合仲裁链 + seed-64可追溯性                          │    │
│  │                                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │    │
│  │  │ L1:规则   │  │ L2:脑模型 │  │ L3:LLM   │  │ L4:混合  │  │ L5:人类     │ │    │
│  │  │ 引擎     │→│ 原生     │→│ 增强     │→│ 加权融合 │→│ 审核       │ │    │
│  │  │ Phase 1  │  │ CX决策   │  │ 13 Agent │  │仲裁投票  │  │ 最终确认    │ │    │
│  │  │ 23 Agent │  │ steering │  │ 7 Primary│  │ divergence│  │ override   │ │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘ │    │
│  │       │              │             │             │               │         │    │
│  │       └──────────────┴─────────────┴─────────────┴───────────────┘         │    │
│  │                                                                             │    │
│  │  🔐 seed-64: 每个决策带 64-bit 种子 (policy_hash ⊕ frame_seq ⊕ agent_id)   │    │
│  │  🔗 因果链: brain_steering → anomaly_signals → rule_traces → llm_reasoning  │    │
│  └──────────────────────────────────┬─────────────────────────────────────────────┘    │
│                                     │                                                  │
│  ┌──────────────────────────────────▼─────────────────────────────────────────────┐    │
│  │                         🛠️ 执行层 (Execution Layer)                              │    │
│  │                        DSH插件集成与Web面板                                    │    │
│  │                                                                             │    │
│  │  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐  │    │
│  │  │ DSH Host Plugin   │  │ mmap→rpcApi Bridge  │  │ Web Frontend        │  │    │
│  │  │ ghb-host.js       │  │ bridge2rpc          │  │ ghb-client.js       │  │    │
│  │  │ ├─ 19 ghb_* tools  │  │ ├─ seqlock reader   │  │ ├─ FloatingPanel    │  │    │
│  │  │ ├─ 4 new brain_*   │  │ ├─ JSON cache       │  │ │  (7+1 Tab)        │  │    │
│  │  │ └─ rpcApi 15方法   │  │ └─ POST /fly64/api  │  │ ├─ 🧠 Brain Tab     │  │    │
│  │  └────────────────────┘  └────────────────────┘  │ └─ F643 WS (0.5Hz)  │  │    │
│  │                                                   └──────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                          📊 数据流 (Data Flow)                               │    │
│  │                                                                             │    │
│  │  Doris数仓 → 增量分批下载 → per-policy CSV → 脑模型输入向量化 →             │    │
│  │  → 神经推理(LIF) → 仲裁决策 → 结果回写 agent_state.json → 综合HTML报告       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 架构分层与职责

| 层 | 核心组件 | 技术栈 | 响应时间 | 置信度 |
|---|---------|--------|---------|-------|
| 🧠 **感知层** | Fly64 Retina/Flow/MB/CX/SceneMemory | Python LIF SNN, NumPy | ~2s/保单 | ~70% |
| ⚖️ **决策层** | 5级仲裁链 + seed-64 + 因果链 | LangGraph + 加权投票 | ~2s-15min | ~70-95% |
| 🛠️ **执行层** | DSH Host/Client + bridge2rpc | Node.js, seqlock, HTTP | ~0.5ms-500ms | N/A(基础设施) |

### 1.3 执行模式矩阵

| 模式 | 感知层 | 决策层仲裁 | 执行层 | 耗时 | Token | 召回率 | 场景 |
|------|-------|----------|-------|------|-------|-------|------|
| **Mode 0** 原生脑模型 | Fly64全量推理 | L1→L2(规则跳过) | 桥接写入 | ~2s | 0 | ~70% | 快速筛查/归档保单 |
| **Mode 1** LLM增强 | Fly64提供context | L1→L2→L3(全量LLM) | 标准DSH | ~15min | ~170K | ~95% | 高价值/深度分析 |
| **Mode 2** 纯规则 | 跳过 | L1(23 Agent) | 标准DSH | ~5min | 0 | ~80% | 批量扫描/对账 |
| **Mode 3** 混合(默认) | Fly64先行2s | L1→L2分歧→按需L3 | 自适应桥接 | ~2-15min | 0-170K | ~90% | **日常运行** |

---

## 2. 感知层 — Fly64脑模型取代/增强

### 2.1 感知层组件架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       🧠 感知层内部架构 (Perception Layer)                      │
│                                                                             │
│   ┌──────────────────┐  ┌────────────────────────────────────────────┐      │
│   │ 输入适配器        │  │  Fly64 Neural Engine                        │      │
│   │ (Input Adapter)   │  │                                            │      │
│   │                   │  │  ┌──────────────────────────────────────┐ │      │
│   │  Doris CSV →      │  │  │ Retina (复眼)                       │ │      │
│   │  PolicyAnalysisData│  │  │  ├─ SphericalRetina.sample()       │ │      │
│   │  → 脑模型输入向量  │  │  │  │   1536像素/270°视场             │ │      │
│   │                   │  │  │  ├─ ON/OFF 能量通道                 │ │      │
│   │                   │  │  │  │   → 数据对账(reconciliation)      │ │      │
│   │  输出:            │  │  │  ├─ 4通道颜色编码                  │ │      │
│   │  - scene_sig(128) │  │  │  │   → 责任类型分流(门诊/住院/牙科) │ │      │
│   │  - policy_vector  │  │  │  └─ HRC EMD 4方向运动检测          │ │      │
│   │  - temporal_seq   │  │  │      → 同比/环比趋势(ramp_analysis) │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ Flow (光流)                          │ │      │
│   │                   │  │  │  ├─ compute_flow() → flow_asymmetry  │ │      │
│   │                   │  │  │  │   → 宏观态势感知                  │ │      │
│   │                   │  │  │  ├─ self_motion_separation           │ │      │
│   │                   │  │  │  │   → 赔付率分解(控制变量法)        │ │      │
│   │                   │  │  │  ├─ flooming/tau                    │ │      │
│   │                   │  │  │  │   → 费用集中度/消耗速度          │ │      │
│   │                   │  │  │  └─ terrain classification           │ │      │
│   │                   │  │  │      → 保单风险地形映射             │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ SceneMemory (场景记忆)               │ │      │
│   │                   │  │  │  ├─ 30帧环形缓冲(→12月滚动窗口)     │ │      │
│   │                   │  │  │  ├─ 3σ 场景变化检测                 │ │      │
│   │                   │  │  │  │   → 赔付率突变预警               │ │      │
│   │                   │  │  │  ├─ scene_sig 128维随机投影         │ │      │
│   │                   │  │  │  │   → 保单特征指纹                 │ │      │
│   │                   │  │  │  └─ familiarity [0,1]               │ │      │
│   │                   │  │  │      → 历史模式匹配度               │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ MushroomBody (蘑菇体)                │ │      │
│   │                   │  │  │  ├─ W_kc @ scene_sig → 2000 KC      │ │      │
│   │                   │  │  │  │   稀疏编码(5%活跃=~100)          │ │      │
│   │                   │  │  │  │   → 异常模式识别(替换FWA引擎)     │ │      │
│   │                   │  │  │  ├─ MBON 5输出通道                  │ │      │
│   │                   │  │  │  │   → 5维风险评估(替换health_score)│ │      │
│   │                   │  │  │  ├─ 多巴胺门控学习 ΔW=η·R·KC·MBON·E│ │      │
│   │                   │  │  │  │   → 自适应规则学习               │ │      │
│   │                   │  │  │  └─ eligibility trace               │ │      │
│   │                   │  │  │      → 时序赔付关联(跨月追踪)       │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ CentralComplex (中央复合体)          │ │      │
│   │                   │  │  │  ├─ 16列环形吸引子罗盘              │ │      │
│   │                   │  │  │  │   → 4级分层异常(L1→L2→L3→L4)    │ │      │
│   │                   │  │  │  ├─ 自运动积分(6通道分组扩展)       │ │      │
│   │                   │  │  │  │   → 赔付率6因子链式分解          │ │      │
│   │                   │  │  │  ├─ 锚点路径积分(disp_x/disp_z)     │ │      │
│   │                   │  │  │  │   → 根因追溯(锚点=标杆期)        │ │      │
│   │                   │  │  │  └─ steering_bias输出               │ │      │
│   │                   │  │  │      → 控费优先级排序               │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ TargetTracker (小目标跟踪)           │ │      │
│   │                   │  │  │  ├─ 卡尔曼预测+匈牙利匹配           │ │      │
│   │                   │  │  │  │   → 会员-案件关联/跨期识别       │ │      │
│   │                   │  │  │  ├─ hit_count/missed_count/age      │ │      │
│   │                   │  │  │  │   → 会员活跃度画像               │ │      │
│   │                   │  │  │  └─ time_to_intercept               │ │      │
│   │                   │  │  │      → 最高风险会员预警             │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ GainControl (增益控制)               │ │      │
│   │                   │  │  │  ├─ 5通路增益[0.5,2.5]              │ │      │
│   │                   │  │  │  │   → 健康评分因子动态权重         │ │      │
│   │                   │  │  │  └─ 三因子学习Δgain=η·R·E·(1-gain)  │ │      │
│   │                   │  │  │      → 反馈驱动权重校准             │ │      │
│   │                   │  │  ├──────────────────────────────────────┤ │      │
│   │                   │  │  │ TurnAdaptation (转向适应)            │ │      │
│   │                   │  │  │  ├─ left/right fatigue tau=3s       │ │      │
│   │                   │  │  │  │   → 控费策略疲劳检测             │ │      │
│   │                   │  │  │  ├─ counter_drive/breakout_drive    │ │      │
│   │                   │  │  │  │   → 控费手段轮换/综合控费        │ │      │
│   │                   │  │  │  └─ saturation=0.5                  │ │      │
│   │                   │  │  │      → 策略饱和度评估               │ │      │
│   │                   │  │  └──────────────────────────────────────┘ │      │
│   │                   │                                             │      │
│   └──────────────────┘  └────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 感知层→gbcost Agent 逐项映射

| Fly64脑模块 | 替代/增强的gbcost Agent | 映射方式 | 优先级 |
|------------|------------------------|---------|-------|
| **Retina ON/OFF** | reconciliation (规则) | 替代 — ON/OFF能量通道 → 数据完整性检测 | P0 |
| **Retina EMD 4方向** | ramp_analysis (规则) | 替代 — EMD方向检测 → 爬坡/下降趋势 | P0 |
| **Retina 颜色通道** | extended_metrics (规则) | 替代 — 4通道编码 → 责任类型分流统计 | P1 |
| **Flow self_motion** | fee_rootcause (规则) | 替代 — 自运动分离 → 赔付率6因子分解 | P0 |
| **Flow flooming** | hospital_fee_anomaly (规则) | 增强 — 中心扩张类比 → 费用集中检测 | P2 |
| **Flow terrain** | coverage_deviation (规则) | 增强 — 风险地形 → 保障结构偏离 | P2 |
| **SceneMemory 3σ** | trend_forecast (规则) | 替代 — 30帧环形缓冲 → 12月滚动异常 | P1 |
| **SceneMemory scene_sig** | benchmark_matching (规则) | 增强 — 保单特征指纹 → 标杆匹配 | P1 |
| **MushroomBody KC** | anomaly_detection (LLM Primary) | 替代 — 2000 KC稀疏编码 → L1异常检测 | **P0** |
| **MushroomBody KC** | fwa_analysis (LLM Primary) | 替代 — KC→MBON → 欺诈模式识别(替换61规则) | **P0** |
| **MushroomBody MBON 5** | health_score (LLM增强) | 替代 — 5通道MBON → 5维健康评分 | P1 |
| **MB eligibility trace** | claim_correlation (LLM增强) | 增强 — 资格迹 → 时序赔付关联 | P2 |
| **MB dopamine learning** | 规则LLM_divergence (新增) | 增强 — ΔW学习 → 自适应规则更新 | P1 |
| **CX 16列罗盘** | anomaly_detection (LLM Primary) | 替代 — 4级分层下钻(连续模拟vs离散阈值) | **P0** |
| **CX disp/disp_z** | path_a_drilldown (规则) | 替代 — 锚点路径积分 → 根因追溯 | P1 |
| **CX steering_bias** | cost_control (LLM Primary) | 增强 — 转向偏置 → 控费优先级排序 | P1 |
| **TargetTracker KF** | case_investigation (LLM增强) | 增强 — 卡尔曼跟踪 → 最高风险聚焦 | P2 |
| **TargetTracker Hungarian** | benefit_transfer (规则) | 增强 — 匈牙利匹配 → 利益输送 | P2 |
| **GainController 5通路** | health_score权重 (静态) | 替代 — 动态权重 → 自适应因子调优 | P1 |
| **TurnAdaptation fatigue** | cost_control_tracking (规则) | 替代 — 策略疲劳 → 措施轮换建议 | P1 |
| **StuckDetector** | stability (规则) | 替代 — 多信号卡住 → 数据质量预检 | P0 |
| **CliffDetector** | precondition_checker (规则) | 替代 — 悬崖检测 → 大额赔付预警 | P0 |

### 2.3 感知层关键神经计算公式 (保险适配版)

```
1. 保险数据→Retina采样
   I(t) = normalize(policy_data.monthly_claims[t])   // 月赔付向量
   ON  = I(t) - I(t-1) > 0 ? I(t) - I(t-1) : 0       // 增长通道
   OFF = I(t-1) - I(t) > 0 ? I(t-1) - I(t) : 0       // 下降通道
   color = encode_liability_type(I(t))                 // 责任类型编码

2. EMD 4方向趋势 (替代 ramp_analysis)
   emd_up    = Σ(I(t) - I(t-1))  for positive deltas  // 整体上升
   emd_down  = Σ(I(t-1) - I(t)) for negative deltas   // 整体下降
   emd_left  = Σ(I_门诊(t) - I_门诊(t-1))              // 门诊集中
   emd_right = Σ(I_住院(t) - I_住院(t-1))              // 住院集中

3. 自运动分离 (替代 fee_rootcause)
   true_change = raw_change - β * intervention_rate
   其中 β = self_motion_coefficient (g GainController学习)

4. KC稀疏编码 → 异常检测 (替代 FWA 61规则)
   scene_sig = random_projection(policy_features)      // 128维
   KC_activity = σ(W_kc @ scene_sig)                   // 2000→100活跃
   anomaly_score = ||KC_activity||_0 / 2000             // 稀疏度=异常度
   # 正常保单: ~5% KC活跃, anomaly_score ≈ 0.05
   # 异常保单: 更多KC激活 → anomaly_score > 0.15

5. CX 16列罗盘 → 4级分层 (替代 hierarchical_anomaly_detector)
   heading = bump_position (0-15)                       // 16列环形吸引子
   L1_anomaly = heading in [0-3] ? trend_high : normal  // 整体趋势
   L2_anomaly = heading in [4-7] ? category_issue       // 责任类型
   L3_anomaly = heading in [8-11] ? disease_focus       // 疾病维度
   L4_anomaly = heading in [12-15] ? key_indicator      // 关键指标

6. 多巴胺学习信号 (规则自适应更新)
   dopamine = correct_classification? +1 : -1           // 核实反馈
   Δgain = η * dopamine * eligibility * (1 - gain)      // 增益更新
   ΔW_kc = η * dopamine * KC * MBON * eligibility       // KC权重更新
```

---

## 3. 决策层 — 5级混合仲裁链

### 3.1 5级仲裁链架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ⚖️ 5级决策仲裁链 (Decision Arbitration Chain)            │
│                                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ L1:规则   │──→│ L2:脑模型 │──→│ L3:LLM   │──→│ L4:混合  │──→│ L5:人类  │  │
│  │ 引擎     │   │ 原生     │   │ 增强     │   │ 加权融合 │   │ 审核    │  │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘  │
│       │               │              │              │              │       │
│       ▼               ▼              ▼              ▼              ▼       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ 23规则   │   │ Fly64    │   │ 13 LLM   │   │加权投票  │   │人工      │ │
│  │ Agent    │   │ 脑推理   │   │ Agent    │   │仲裁器    │   │确认/驳回│ │
│  │ 0 token  │   │ 0 token  │   │ ~170K tok│   │ divergence│   │          │ │
│  │ ~5min    │   │ ~2s      │   │ ~15min   │   │ < 0.5ms  │   │ 可选     │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│                                                                             │
│  🔐 每个决策绑定 seed-64 可追溯种子:                                        │
│  seed = (policy_hash[0:32] XOR frame_seq) << 32 | agent_id                  │
│  ───────────────────────────────────────────────────────────────────        │
│  因果链追踪: 所有仲裁步骤记录到一个不可变的因果链                               │
│  causal_chain = [                                                            │
│    {level:1, agent:"reconciliation", output:{...}, seed:0xA1B2},            │
│    {level:2, module:"CX", output:{steering:0.7}, seed:0xC3D4},              │
│    {level:3, agent:"cost_control", output:{...}, seed:0xE5F6},              │
│    {level:4, arbiter:"weighted_vote", result:{final:0.85}, seed:0xG7H8},    │
│  ]                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 L1: 规则引擎 (Phase 1)

| 属性 | 值 |
|------|-----|
| **执行者** | 23 纯规则 Agent (reconciliation/stability/benchmark/ramp/...) |
| **触发器** | 任何分析请求的强制第一级 |
| **耗时** | ~5s (并行执行, 由_GroupB的24Agent决定总时间) |
| **Token消耗** | 0 (纯Python规则) |
| **产出** | `agent_state` 的规则引擎字段 + `{name}_rule_traces` |
| **升级条件** | 规则引擎置信度 < 0.6 → 自动触发L2 |

```
L1状态检查:
  if state.rule_confidence > 0.85 and state.anomaly_count == 0:
      → 直接输出 (跳过L2-L4)
  else:
      → 传递到 L2 脑模型层
```

### 3.3 L2: 脑模型原生 (Fly64 CX)

| 属性 | 值 |
|------|-----|
| **执行者** | Fly64 CentralComplex + MushroomBody |
| **触发器** | L1 置信度不足 或 配置为 Mode 0/3 |
| **耗时** | ~2s (20ms/tick × 100 tick) |
| **Token消耗** | 0 (纯神经计算) |
| **核心输出** | `steering_bias[-1,+1]`, `anomaly_score[0,1]`, `confidence[0,1]` |
| **升级条件** | `confidence < 0.6` 或 `anomaly_score > 0.7` → L3 |

```
L2仲裁逻辑:
  brain_result = fly64_infer(policy_data)
  state.brain_state = brain_result
  
  # 分歧检测: 脑模型 vs 规则引擎
  divergence = |brain_result.steering_bias - rule_consensus.steering|
  if divergence > THRESHOLD (0.3):
      → 触发 L3 LLM增强 (分歧调解)
  elif brain_result.confidence > 0.8:
      → 直接输出 (脑模型高置信)
  else:
      → 传递到 L3
```

### 3.4 L3: LLM增强 (13 Agent)

| 属性 | 值 |
|------|-----|
| **执行者** | 13 LLM Agent (7 Primary + 6 增强) |
| **触发器** | L2分歧 > 0.3 或 配置为 Mode 1 |
| **耗时** | ~15min |
| **Token消耗** | ~170K |
| **脑模型上下文注入** | `scene_sig(128维)`, `steering_bias`, `MBON outputs`, `CX compass` |
| **升级条件** | LLM置信度 < 0.5 → L4 仲裁 |

```
L3注入格式:
  prompt_context = f"""
  [Brain Model State]
  - steering_bias: {brain.steering_bias:.3f}   // 方向偏置 [-1,+1]
  - anomaly_score: {brain.anomaly_score:.3f}    // 异常评分 [0,1]
  - familiarity: {brain.familiarity:.3f}         // 历史模式熟悉度
  - scene_sig: [{brain.scene_sig[:8]}...]        // 128维保单指纹(前8)
  - cx_compass: {brain.compass_position}          // 当前罗盘位置 0-15
  - mb_risk: {brain.mbon_risk}                   // MBON风险评分
  - gain_weights: {brain.gain_weights}            // 当前动态权重
  """
```

### 3.5 L4: 混合加权融合 (Weighted Arbiter)

| 属性 | 值 |
|------|-----|
| **执行者** | `WeightedVoteArbiter` — 基于历史精度的加权投票 |
| **输入** | L1规则输出 + L2脑模型输出 + L3 LLM输出 |
| **算法** | 加权平均, 权重 = `historical_accuracy` |
| **耗时** | <0.5ms |
| **产出** | `final_decision`, `confidence_score`, `arbitration_trace` |

```
加权投票公式:
  FINAL = (W_rule * RULE + W_brain * BRAIN + W_llm * LLM) / (W_rule + W_brain + W_llm)
  
  权重更新 (在线学习):
  W_i(t+1) = W_i(t) + α * (correct - W_i * prediction)  # 权重漂移校正
  
  默认权重:
  W_rule = 0.3 (历史精度 ~80%)
  W_brain = 0.2 (历史精度 ~70%, 但速度快)
  W_llm = 0.5 (历史精度 ~95%, 但成本高)
```

### 3.6 L5: 人类审核 (Human Review)

| 属性 | 值 |
|------|-----|
| **触发器** | 仲裁结果 `confidence < 0.7` 或 `escalation_level > 2` |
| **通知方式** | DSH Web FloatingPanel 🧰 Tab → 审核队列 |
| **审核动作** | 确认(override) / 驳回(back to L3) / 修改(新seed) |
| **seed-64 绑定** | 每次审核操作产生新seed, 链上追加 |

### 3.7 seed-64 可追溯性保证

```
seed-64 生成与追踪规范:

┌──────────────────────────────────────────────────────────────┐
│ seed = (policy_hash[0:32] XOR frame_seq) << 32 | agent_id   │
│                                                              │
│ policy_hash = SHA256(policy_id)[:32]  // 保单32位哈希        │
│ frame_seq   = brain_model.step_count   // 脑模型帧序号       │
│ agent_id    = 0-255  (每个决策节点唯一ID)                     │
│                                                              │
│ 存储: agent_state.causal_chain[] 每个条目含:                  │
│   {level, source, seed, timestamp, output_hash}              │
│                                                              │
│ 验证: causal_chain[-1].seed ==                               │
│       verify_chain(causal_chain[:-1], policy_id, final_seed) │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. 执行层 — DSH插件与Web集成

### 4.1 执行层组件架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🛠️ 执行层集成架构 (DSH Plugin + Web)                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    DSH Host Plugin (ghb-host.js)                     │    │
│  │                                                                     │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                   │    │
│  │  │ 现有 ghb_* 工具(19)  │  │ 新增 brain_* 工具(4) │                   │    │
│  │  │                     │  │                     │                   │    │
│  │  │ ghb_analyze         │  │ brain_infer         │ ← 调用脑模型推理    │    │
│  │  │ ghb_query           │  │ brain_state         │ ← 查询脑模型状态    │    │
│  │  │ ghb_status          │  │ brain_train         │ ← 触发多巴胺学习    │    │
│  │  │ ghb_reports         │  │ brain_visualize     │ ← 神经活动可视化    │    │
│  │  │ ghb_policy_mgmt     │  │                     │                   │    │
│  │  │ ...                 │  └─────────────────────┘                   │    │
│  │  └─────────────────────┘                                            │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  rpcApi (15方法 + 新4路由)                                    │   │    │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │    │
│  │  │  │ read-state   │  │ run-analysis  │  │ brain-state     │←新增│   │    │
│  │  │  │ job-progress │  │ rich-render   │  │ brain-control   │←新增│   │    │
│  │  │  │ list-policies│  │ ops-status    │  │ brain-telemetry │←新增│   │    │
│  │  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  bridge2rpc 适配器 (新模块)                                    │   │    │
│  │  │  ├─ 读取 Fly64 seqlock 共享内存帧 (128B header)               │   │    │
│  │  │  ├─ 缓存为 JSON 对象 (1.5ms timeout)                          │   │    │
│  │  │  ├─ 暴露 /fly64/api/state 和 /fly64/api/control 路由          │   │    │
│  │  │  └─ 写入控制命令回 seqlock 写端                               │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   DSH Client Plugin (ghb-client.js)                  │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────┐       │    │
│  │  │  FloatingPanel (7+1 Tab)                                 │       │    │
│  │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌───┐ │ ┌───┐│    │
│  │  │  │ 📊  │ │ 📄 │ │ 🗺️ │ │ 🤖 │ │ 🖼️ │ │ 🔮 │ │ 🧰│ │ │🧠 ││    │
│  │  │  │指标 │ │保单 │ │风险 │ │ML   │ │影像 │ │预测 │ │操作│ │ │脑  ││    │
│  │  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └───┘ │ └───┘│    │
│  │  └──────────────────────────────────────────────────────────┘       │    │
│  │                                                                     │    │
│  │  🧠 Brain Tab 内容:                                                 │    │
│  │  ├─ 因果链可视化: steering_bias → anomaly_state → escape_mode      │    │
│  │  ├─ 复眼视图: 384×256 Retina 伪彩色 (模拟合成, 非真实像素)          │    │
│  │  ├─ 神经元活动: 166,700神经元分8区聚合热图                          │    │
│  │  ├─ MBON 5通道: forward/left/right/jump/explore 关联条图            │    │
│  │  ├─ CX Compass: 16列环形吸引子方向罗盘                              │    │
│  │  ├─ Motor池: forward/turn_left/turn_right/jump 解码值              │    │
│  │  └─ 控制面板: 手动 steering override + 分析触发按钮                 │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────┐       │    │
│  │  │  F643 WebSocket 低速数据通道 (0.5Hz)                      │       │    │
│  │  │  ws://localhost:8766/ws                                    │       │    │
│  │  │  → 推送: {neurons, spikes, motor, cx, mb, scene_sig}      │       │    │
│  │  │  → 聚合降采样: 166K→8区域热图 (原始数据留在服务端)          │       │    │
│  │  └──────────────────────────────────────────────────────────┘       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 mmap→rpcApi 协议桥 (bridge2rpc)

#### 桥接架构

```
┌─────────────────────┐          seqlock共享内存          ┌─────────────────────┐
│   Fly64 脑模型进程   │  ←────────── 128B帧 ───────────→  │   bridge2rpc 适配器   │
│                     │  80 bytes header + pixels         │                     │
│  model.step()       │                                   │  adapter.js/py     │
│  bridge.write_ctl() │  ←────── 控制指令 ────────────────  │  POST /fly64/api/* │
└─────────────────────┘                                   └────────┬────────────┘
                                                                    │ HTTP JSON
                                                                    ▼
                                                            ┌─────────────────────┐
                                                            │   DSH ghb-host.js    │
                                                            │   rpcApi            │
                                                            │   ctx.tools          │
                                                            └─────────────────────┘
```

#### 协议转换

| 操作 | Seqlock 原生 | RPC 封装 | 额外延迟 |
|------|-------------|---------|---------|
| 读脑模型状态 | 12μs (mmap) | `POST /fly64/api/state` → JSON | +0.5ms |
| 写控制指令 | 8μs (mmap) | `POST /fly64/api/control` → seqlock写 | +0.3ms |
| 批量遥测 | N/A | `POST /fly64/api/telemetry` | +2-5ms |
| 训练触发 | N/A | `POST /fly64/api/train` | +10-100ms |

#### bridge2rpc 核心逻辑

```javascript
// fly64/plugin/bridge2rpc.js — seqlock→RPC 适配器
const BRIDGE_PATH = process.env.FLY64_BRIDGE_PATH || '/tmp/f64b'
const HEADER_SIZE = 128
const MAGIC = 'FLY64V2'
const POLL_INTERVAL = 100  // ms

class Bridge2RpcAdapter {
  constructor() {
    this.cache = null        // 最后一次帧缓存的JSON
    this.lastSeq = 0         // 上次读取的帧序号
    this.pollTimer = null
  }

  // 非阻塞读seqlock帧 (1.5ms timeout)
  readFrame() {
    try {
      const fd = fs.openSync(BRIDGE_PATH, 'r')
      const buf = Buffer.alloc(HEADER_SIZE)
      fs.readSync(fd, buf, 0, HEADER_SIZE, 0)
      fs.closeSync(fd)
      if (buf.toString('utf8', 0, 8) !== MAGIC) return null
      return {
        frameSeq: buf.readUInt32LE(12),
        controlSeq: buf.readUInt32LE(16),
        enabled: buf.readUInt32LE(20),
        heartbeatNs: buf.readBigUInt64LE(24),
        steeringBias: buf.readFloatLE(36),   // CX steering_bias
        anomalyScore: buf.readFloatLE(40),   // 综合异常评分
        confidence: buf.readFloatLE(44),     // 脑模型置信度
        compassPos: buf.readUInt32LE(48),    // CX罗盘位置
        mbonOutput: [                         // MBON 5通道
          buf.readFloatLE(52), buf.readFloatLE(56),
          buf.readFloatLE(60), buf.readFloatLE(64),
          buf.readFloatLE(68)
        ],
        gainWeights: [                        // 增益控制5通路
          buf.readFloatLE(72), buf.readFloatLE(76),
          buf.readFloatLE(80), buf.readFloatLE(84),
          buf.readFloatLE(88)
        ],
        poseX: buf.readFloatLE(92),
        poseY: buf.readFloatLE(96),
        poseZ: buf.readFloatLE(100),
        poseH: buf.readFloatLE(104),
        renderMs: buf.readFloatLE(108)
      }
    } catch (e) { return null }
  }

  // RPC: 获取脑模型当前状态
  async getState() {
    if (!this.cache) return { ok: false, error: 'bridge not initialized' }
    return { ok: true, ...this.cache }
  }

  // RPC: 发送控制指令 (写seqlock控制域)
  async sendControl(action, value) { /* ... */ }

  // 轮询更新缓存 (100ms间隔)
  startPolling() {
    this.pollTimer = setInterval(() => {
      const frame = this.readFrame()
      if (frame && frame.frameSeq !== this.lastSeq) {
        this.cache = frame
        this.lastSeq = frame.frameSeq
      }
    }, POLL_INTERVAL)
  }
}
```

### 4.3 新增 brain_* 工具规范

```javascript
// ghb-host.js 新增4个工具注册

// 1. brain_infer — 调用脑模型对保单进行神经推理
ctx.tools['brain_infer'] = {
  name: 'brain_infer',
  description: '调用Fly64果蝇脑模型对保单数据进行神经推理分析',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string', description: '保单号' },
      mode: { type: 'string', enum: ['native', 'hybrid'], default: 'hybrid' }
    },
    required: ['policy_id']
  },
  handler: async (args, ctx) => {
    // 1. 通过bridge2rpc 发送推理请求
    // 2. 等待脑模型完成 ~2s 推理
    // 3. 返回 { steering_bias, anomaly_score, confidence, ... }
  }
}

// 2. brain_state — 查询脑模型当前状态快照
ctx.tools['brain_state'] = {
  name: 'brain_state',
  description: '查询Fly64脑模型当前状态快照',
  parameters: { type: 'object', properties: {} },
  handler: async (_, ctx) => {
    // 返回完整脑模型状态 (seqlock最新帧解析)
  }
}

// 3. brain_train — 触发多巴胺学习 (规则自适应更新)
ctx.tools['brain_train'] = {
  name: 'brain_train',
  description: '以核实反馈触发脑模型多巴胺学习, 自适应更新规则权重',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string' },
      feedback: { type: 'number', description: '反馈信号 -1~+1' },
      target_module: { type: 'string', enum: ['mb', 'gain', 'all'] }
    }
  }
  // handler 通过 seqlock 写反馈信号
  // 脑模型下次 tick 时 ΔW = η·R·KC·MBON·E 进行更新
}

// 4. brain_visualize — 神经活动可视化数据
ctx.tools['brain_visualize'] = {
  name: 'brain_visualize',
  description: '获取神经活动可视化数据用于前端渲染',
  // 返回聚合后的8区热图数据 + 关键指标
}
```

### 4.4 Web前端 🧠 Tab 集成

```javascript
// ghb-client.js — FloatingPanel 新增 🧠 Tab

// 在 PANEL_TABS 追加
const PANEL_TABS = [
  { key: 'explorer', label: '📊', name: '指标探索' },
  { key: 'policies', label: '📄', name: '保单列表' },
  { key: 'riskmap', label: '🗺️', name: '风险地图' },
  { key: 'mltrain', label: '🤖', name: 'ML训练' },
  { key: 'images', label: '🖼️', name: '理赔影像' },
  { key: 'prediction', label: '🔮', name: '预测查询' },
  { key: 'ops', label: '🧰', name: '操作指引' },
  { key: 'brain', label: '🧠', name: '脑模型状态', width: 640 },  // ← 新增
]

// BrainPanel 组件
function BrainPanel() {
  const [brainState, setBrainState] = useState(null)
  const ws = useRef(null)

  useEffect(() => {
    // 连接 F643 WebSocket (0.5Hz)
    ws.current = new WebSocket('ws://localhost:8766/ws')
    ws.current.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      setBrainState({
        ...data,
        // 聚合166K→8区 (前端只接收聚合数据)
        heatmap: aggregateRegions(data.spikes, 8),
      })
    }
    return () => ws.current?.close()
  }, [])

  if (!brainState) return '等待脑模型连接...'

  return html`
    <div class="brain-panel" style="display:grid; grid-template-columns:1fr 1fr; gap:8px">
      <${CausalChain} data=${brainState.causalChain} />
      <${RetinaView} retina=${brainState.retina} />
      <${Compass} position=${brainState.cx.compass} />
      <${MBONBar} channels=${brainState.mb.mbon} />
      <${MotorPool} motor=${brainState.motor} />
      <${ControlPanel} onControl=${handleControl} />
    </div>
  `
}
```

### 4.5 DSH Skill 集成

新增 `fly64-brain` skill, 与现有5个skill合并统一入口:

```yaml
# skills/unified-brain-insurance/manifest.yaml
name: "brain-insurance-analysis"
version: "1.0.0"
skills:
  - ghb-cost-control    # 36 Agent分析引擎
  - ghb-query           # 107项指标查询
  - ghb-batch           # 批量保单分析管线
  - ghb-doris           # Doris数仓操作
  - risk-map-analyzer   # 风险地图4×23
  - fly64-brain         # Fly64脑模型引擎 (新增)
routing:
  default: hybrid
  priority: brain_native > rule_only > hybrid > llm_primary
  divergence_threshold: 0.3
```

---

## 5. 数据流设计

### 5.1 完整数据流图

```
Doris数仓                           gbcost-analysys
   │                                      │
   │ ghb_doris_download                   │
   │ (增量分批断点续传)                     │
   ▼                                      │
per-policy CSV ───────────────────────────┤
(wide_{gc}.csv)                            │
   │                                      │
   ├──────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  脑模型输入向量化 (Input Vectorization)                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PolicyAnalysisData → 神经编码管线                              │   │
│  │                                                              │   │
│  │  1. 结构化字段编码:                                            │   │
│  │     - 月度赔付率 → 亮度通道 (I(t) ∈ [0, 1])                   │   │
│  │     - 门诊/住院/牙科/生育 → 4通道颜色编码                      │   │
│  │     - 诊断代码 → 疾病分布直方图                                 │   │
│  │     - 医院/供应商 → 供应商分布编码                               │   │
│  │     - 会员年龄/性别 → 人口统计编码                              │   │
│  │                                                              │   │
│  │  2. 时序编码:                                                  │   │
│  │     - 24个月赔付序列 → 1440帧×4通道 (60fps×24mo×4)            │   │
│  │     - 12个月滚动窗口 → 30帧环形缓冲                             │   │
│  │                                                              │   │
│  │  3. 场景签名:                                                  │   │
│  │     - 128维 random projection: scene_sig = R @ features       │   │
│  │     - 5通道彩色增强: (128, 7680) = 5×128@brightness+4color    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Fly64 神经推理 (Neural Inference)                                  │
│  166,700 神经元 / 25.6M 突触                                        │
│  dt = 20ms / tick                                                   │
│                                                                     │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌────────────┐ │
│  │Retina│→│ Flow │→│Scene │→│ MB   │→│ CX  │→│GainCtrl    │ │
│  │      │  │      │  │Memory│  │KC    │  │ 16  ││+TurnAdapt  │ │
│  └──────┘  └──────┘  └──────┘  └──────┘  └──┬───┘└────────────┘ │
│                                               │                    │
│                                         steering_bias              │
│                                         anomaly_score              │
└───────────────────────────────────────────────┬────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  仲裁决策 (Arbitration) → 5级仲裁链                                │
│                                                                     │
│  L1规则 → L2脑模型 → L3 LLM → L4加权 → L5人类                     │
│       ↓           ↓          ↓         ↓         ↓                 │
│  rule_traces brain_state llm_reasoning final_dec human_override     │
│                                                                     │
│  seed-64 因果链记录所有决策步骤                                     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  结果回写 agent_state.json                                          │
│                                                                     │
│  新增字段:                                                          │
│  - brain_state: { steering_bias, anomaly_score, confidence, ... }   │
│  - brain_traces: [{module, timestamp, value}, ...]                  │
│  - brain_neural_activity: { region_summary, spike_rate, ... }       │
│  - arbitration_chain: [{level, source, seed, output}, ...]          │
│  - seed64_policy: current_seed                                       │
│  - brain_divergence: { rule_vs_brain, brain_vs_llm, resolved }       │
│                                                                     │
│  → 综合HTML报告 (32章)                                             │
│  → 风险地图 Q&A                                                    │
│  → ML预测更新                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 数据流关键路径

| 路径 | 输入 | 处理 | 输出 | 延迟 |
|------|------|------|------|------|
| **快速路径** (Mode 3默认) | per-policy CSV | 脑模型2s → divergence<0.3 → 规则5min | agent_state | ~5-7min |
| **深度路径** (分歧>0.3) | per-policy CSV | 脑模型2s → 规则5min → LLM 15min | agent_state | ~20min |
| **纯脑路径** (Mode 0) | per-policy CSV minimal | 脑模型2s → 输出粗略评分 | agent_state(brain_only) | ~2s |
| **实时流** (WebSocket) | 脑模型帧(20ms/tick) | bridge2rpc → JSON cache → WS推送 | 前端可视化 | ~100ms |

### 5.3 向量化规格

| 字段 | 类型 | 维度 | 编码方式 | 对应脑输入 |
|------|------|------|---------|-----------|
| 月赔付率 | float[] | 24 | 归一化[0,1] | Retina亮度通道 |
| 门诊费用占比 | float[] | 24 | 各月占比 | 颜色通道1 |
| 住院费用占比 | float[] | 24 | 各月占比 | 颜色通道2 |
| 牙科费用占比 | float[] | 24 | 各月占比 | 颜色通道3 |
| 生育费用占比 | float[] | 24 | 各月占比 | 颜色通道4 |
| 疾病分布 | float[] | 50 | ICD-10大类直方图 | SceneMemory特征 |
| 年龄分布 | float[] | 10 | 年龄段占比 | 人口统计特征 |
| 性别比 | float | 1 | M/F ratio | 辅助输入 |
| 供应商集中度 | float[] | 20 | HHI各月 | Flow输入 |
| 保单类型 | int | 1 | 14类编码 | SceneRecognition |

**总输入维度**: 24×4 + 50 + 10 + 1 + 20 + 1 = **178维** → 嵌入128维 scene_sig

---

## 6. 状态管理 — AgentState扩展

### 6.1 当前 AgentState (TypedDict, total=False, 143+字段)

现有状态见 T1 分析: 输入(1) → Step1-3(6) → Step4-6(8) → LLM增强(15+) → 扩展指标(8) → Phase B(15+) → Phase C/D(20+) → 告警元数据(10+) → ML+注册表(5+)

### 6.2 新增脑模型状态字段 (40字段)

```
# fly64/state_brain.py — 脑模型状态扩展
# 所有字段使用 total=False, .get() 安全访问

class BrainState(TypedDict, total=False):
    """Fly64 脑模型推理状态 — 新增字段组"""

    # ── 脑模型总体状态 (6字段) ──
    brain_steering_bias: float          # [-1, +1] CX转向偏置
    brain_anomaly_score: float          # [0, 1] 异常评分
    brain_confidence: float             # [0, 1] 脑模型置信度
    brain_familiarity: float            # [0, 1] 历史模式熟悉度
    brain_computation_ms: float         # 脑推理耗时(ms)
    brain_tick_count: int               # 脑模型执行tick数

    # ── 感知层状态 (12字段) ──
    brain_scene_sig: List[float]        # 128维保单特征指纹
    brain_retina_on: List[float]        # ON通道能量序列
    brain_retina_off: List[float]       # OFF通道能量序列
    brain_flow_asymmetry: float         # 光流不对称度
    brain_flow_self_motion: float       # 自运动分量
    brain_flow_looming: float           # 中心扩张率
    brain_memory_change_rate: float     # 场景变化率
    brain_memory_stability: float       # 场景稳定度
    brain_kc_activity: List[float]      # 2000 KC活跃度(稀疏)
    brain_kc_sparsity: float            # KC稀疏度(活跃比例)
    brain_mbon_forward: float           # MBON 前向通道
    brain_mbon_left: float              # MBON 左转通道
    brain_mbon_right: float             # MBON 右转通道
    brain_mbon_jump: float              # MBON 跳跃通道
    brain_mbon_explore: float           # MBON 探索通道

    # ── 决策层状态 (8字段) ──
    brain_cx_compass: int               # 罗盘位置 0-15
    brain_cx_goal_strength: float       # 目标强度
    brain_cx_heading_rate: float        # 航向变化率
    brain_cx_steering: float            # steering_bias
    brain_cx_disp_x: float              # 锚点X积分(根因追溯)
    brain_cx_disp_z: float              # 锚点Z积分(程度)
    brain_gain_visual: float            # 视觉通路增益[0.5,2.5]
    brain_gain_forward: float           # 前向通路增益
    brain_gain_turn: float              # 转向通路增益
    brain_gain_jump: float              # 跳跃通路增益
    brain_gain_recurrent: float         # 递归通路增益

    # ── 仲裁状态 (6字段) ──
    brain_arbitration_level: int        # 当前仲裁层级 1-5
    brain_divergence_rule: float        # 规则vs脑模型分歧度
    brain_divergence_llm: float         # 脑模型vs LLM分歧度
    brain_escalation_count: int         # 升级次数
    brain_arbitration_result: str       # 仲裁结果 verbatim
    brain_human_override: Optional[str] # 人类覆写记录

    # ── seed-64 可追溯性 (4字段) ──
    brain_seed64: str                   # 当前决策种子(hex)
    brain_causal_chain: List[Dict]      # 因果链 [{level,source,seed,timestamp}]
    brain_seed_parent: str              # 父seed(可追溯)
    brain_policy_hash: str              # 保单32位哈希

    # ── 神经活动汇总 (4字段) ──
    brain_region_activity: Dict[str, float]  # 8区域平均活跃度
    brain_spike_rate: float                 # 整体发放率
    brain_region_heatmap: str               # 8区域热图(base64)
    brain_neural_snapshot: Dict             # 神经活动快照
```

### 6.3 字段分组与兼容策略

```
现有AgentState字段 (143+)
  ├── 保持原样: reconciliation, stability, health_score, fwa_result, ...
  ├── 降级:    anomaly_detection → brain_anomaly_score (当脑模型启用)
  ├── 增强:    cost_control → brain_steering_bias 注入 LLM 上下文
  └── 标记:    {name}_meta.brain_enabled = True/False

新增脑模型字段 (40)
  ├── 感知层:     scene_sig, retina, flow, memory (15)
  ├── 决策层:     CX compass, gain, steering (13)
  ├── 仲裁层:     divergence, escalation, arbitration (6)
  ├── 追溯层:     seed64, causal_chain (4)
  └── 活动层:     region_activity, spike_rate (2)

并行安全:
  - brain_* 字段使用单独的 delta 返回 (遵循 _make_parallel_safe)
  - causal_chain 使用 ANNOTATED[List, add] reducer (类似 alerts)
  - 脑模型写 brain_* 前缀, 36 Agent 写原有字段, 不重叠
```

### 6.4 状态可观测性

```python
# 脑模型状态注册表 — 接入现有 ghb_registry 体系
BRAIN_REGISTRY_KEYS = {
    "brain_steering_bias": {
        "display": "CX转向偏置",
        "type": "float", "range": [-1, 1],
        "unit": "score",
        "chart": "gauge",
        "category": "brain_decision",
        "threshold_ref": "config.brain.steering_warn > 0.7",
        "generator": "central_complex",
        "fellback_to": None
    },
    "brain_anomaly_score": {
        "display": "脑模型异常评分",
        "type": "float", "range": [0, 1],
        "unit": "score",
        "chart": "gauge",
        "category": "brain_perception",
        "threshold_ref": "config.brain.anomaly_warn > 0.3",
        "generator": "mushroom_body + cx",
        "fellback_to": None
    },
    # ... (全部40字段注册)
}

# 指标回检 (复用现有 ghb_indicator_recheck)
# brain_* 字段同样纳入回检框架
# 回检方式: 
# 1. 重新读取 policy_data 重建输入
# 2. 重跑脑模型 (确定性推理, 同 seed)
# 3. 对比 brain_steering_bias 等字段值
```

---

## 7. 部署架构 — 三进程拓扑

### 7.1 三进程部署拓扑

```
┌────────────────────────────────────────────────────────────────────────┐
│                          部署环境: Windows Server / Linux              │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │ Process 1: Fly64 脑模型常驻进程 (brain-insurance-engine)    │       │
│  │                                                             │       │
│  │  ├─ 技术栈: Python 3.11+ / NumPy / LIF SNN                  │       │
│  │  ├─ 资源: CPU ~15W / 内存 ~500MB                            │       │
│  │  ├─ 周期: dt=20ms (50Hz tick)                               │       │
│  │  ├─ 核心: fly64/model.py → model.step()                     │       │
│  │  ├─ 输入:                                                 │       │
│  │  │  - seqlock 读: sensor帧 (retina/scene/game state)       │       │
│  │  │  - file 读: per-policy CSV (批量分析触发)                │       │
│  │  ├─ 输出:                                                 │       │
│  │  │  - seqlock 写: 128B header + 遥测JSON                   │       │
│  │  │  - seqlock 读: 控制指令 (steering/train/reset)          │       │
│  │  ├─ 持久化:                                               │       │
│  │  │  - runtime/telemetry.json (遥测缓存)                    │       │
│  │  │  - runtime/consolidated.npz (巩固记忆)                  │       │
│  │  │  - runtime/kc_weights.npz (蘑菇体权重)                  │       │
│  │  └─ 进程守护: systemd / Windows Service                    │       │
│  │                                                             │       │
│  │  ┌───────────────────────┐  ┌───────────────────────────┐   │       │
│  │  │ 共享内存: /tmp/f64b   │  │ Python subprocess:        │   │       │
│  │  │ seqlock 128B header   │  │ bridge2rpc (可选Python版)  │   │       │
│  │  │ 80 bytes pixels       │  │ 轮询seqlock → HTTP JSON   │   │       │
│  │  └───────────────────────┘  └───────────────────────────┘   │       │
│  └─────────────────────┬────────────────────────────────────────┘       │
│                        │ mmap seqlock (共享内存)                         │
│  ┌─────────────────────▼────────────────────────────────────────┐       │
│  │ Process 2: DSH 插件进程 (Node.js ghb-host.js)                 │       │
│  │                                                             │       │
│  │  ├─ 技术栈: Node.js 20+ / DSH SDK                            │       │
│  │  ├─ 资源: CPU ~5W / 内存 ~200MB                              │       │
│  │  ├─ 核心: plugin/ghb-host.js                                  │       │
│  │  ├─ 模块:                                                  │       │
│  │  │  ├─ bridge2rpc.js (seqlock→HTTP JSON 适配器)              │       │
│  │  │  ├─ ghb_* tools (19现有 + 4新增 brain_*)                  │       │
│  │  │  ├─ rpcApi (15现有方法 + 4新路由)                         │       │
│  │  │  └─ webServer ( /ghb/api/* + /fly64/api/* )              │       │
│  │  ├─ 进程通信:                                             │       │
│  │  │  - mmap seqlock: 读脑模型帧 (100ms轮询)                  │       │
│  │  │  - HTTP: 调用 Process 3 的 LangGraph API                 │       │
│  │  └─ 重启策略: DSH 自动重加载                                 │       │
│  │                                                             │       │
│  │  ┌──────────────────────────────────────────────────────┐   │       │
│  │  │  bridge2rpc 内部状态:                                 │   │       │
│  │  │  cache = {                                           │   │       │
│  │  │    frameSeq, steeringBias, anomalyScore,              │   │       │
│  │  │    confidence, compassPos, mbonOutput, gainWeights,  │   │       │
│  │  │    ... (每100ms更新)                                  │   │       │
│  │  │  }                                                    │   │       │
│  │  └──────────────────────────────────────────────────────┘   │       │
│  └─────────────────────┬────────────────────────────────────────┘       │
│                        │ HTTP (subprocess)                               │
│  ┌─────────────────────▼────────────────────────────────────────┐       │
│  │ Process 3: 36 Agent LangGraph 进程 (orchestrator.py)          │       │
│  │                                                             │       │
│  │  ├─ 技术栈: Python 3.11+ / LangGraph 1.2+ / DSH subprocess   │       │
│  │  ├─ 资源: CPU ~30W / 内存 ~2GB                               │       │
│  │  ├─ 核心: workflow.py → create_analysis_workflow()           │       │
│  │  ├─ 38节点 StateGraph                                       │       │
│  │  ├─ 输入: subprocess 参数 (policy_id, mode, options)         │       │
│  │  ├─ 输出: agent_state.json (写入 output/{pid}_*/)            │       │
│  │  ├─ 脑模型集成:                                           │       │
│  │  │  - 读脑模型输出: 通过 Process 2 bridge2rpc HTTP 获取      │       │
│  │  │  - 脑模型场景签名注入: scene_sig 作为 LLM prompt 上下文   │       │
│  │  │  - divergence 检测: 规则结果 vs brain_state 对比          │       │
│  │  └─ 进程生命周期: 每次分析请求启动 → 完成后退出               │       │
│  │                                                             │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │ 共享文件系统 (Shared Filesystem)                            │       │
│  │                                                             │       │
│  │  data/doris/policies/     ← per-policy CSV (Process 2 写)   │       │
│  │  output/{pid}_*/          ← agent_state.json (Process 3 写) │       │
│  │  logs/                    ← 执行日志 (Process 2/3 写)       │       │
│  │  runtime/                 ← 脑模型持久化 (Process 1 写)     │       │
│  │  predictions/             ← ML预测 (Process 3 写)           │       │
│  └─────────────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────────┘
```

### 7.2 进程间通信矩阵

| 源进程 | 目标进程 | 协议 | 频率 | 数据量 | 延迟要求 |
|-------|---------|------|------|-------|---------|
| P1 (脑模型) | P2 (DSH插件) | mmap seqlock | 50Hz | 128B + 80B | <20μs |
| P2 (DSH插件) | P1 (脑模型) | mmap seqlock | 按需 | 8B 控制指令 | <10μs |
| P2 (DSH插件) | P3 (LangGraph) | HTTP POST | 按分析请求 | ~10KB JSON | <100ms |
| P3 (LangGraph) | P2 (DSH插件) | HTTP GET | 仲裁时 | ~5KB JSON | <50ms |
| P2 (DSH插件) | Web UI | WebSocket | 0.5Hz | ~2KB JSON | <500ms |
| P3 (LangGraph) | 文件系统 | file I/O | 分析完成 | ~2MB agent_state | N/A |

### 7.3 资源估算

| 场景 | P1 (脑模型) | P2 (DSH插件) | P3 (36 Agent) | 总计 |
|------|-----------|------------|-------------|------|
| **空闲** | CPU 5%, 300MB | CPU 2%, 150MB | — | CPU 7%, 450MB |
| **Mode 0 (快速)** | CPU 30%, 500MB | CPU 10%, 200MB | — | CPU 40%, 700MB |
| **Mode 2 (规则)** | CPU 10%, 400MB | CPU 5%, 200MB | CPU 60%, 1.5GB | CPU 75%, 2.1GB |
| **Mode 3 (混合)** | CPU 30%, 500MB | CPU 15%, 200MB | CPU 60%, 2GB | CPU 85%, 2.7GB |
| **Mode 1 (LLM)** | CPU 20%, 500MB | CPU 10%, 200MB | CPU 90%, 3GB | CPU 95%, 3.7GB |

**硬件需求**: 8核 CPU, 16GB RAM, 无 GPU (脑模型和规则无需GPU, LLM通过远程API调用)

### 7.4 部署配置

```yaml
# fly64/config/deployment.yaml
deployment:
  topology: "three_process"
  
process_brain:
  engine: "python3.11"
  entry: "fly64/run.py"
  interval_seconds: null  # 常驻50Hz
  memory_mb: 500
  cpu_limit: 2
  restart: "always"
  shared_memory:
    path: "/tmp/f64b"
    size_kb: 256
    seqlock: true

process_plugin:
  engine: "node"
  entry: "plugin/ghb-host.js"
  dsh_reload: true
  memory_mb: 200
  bridge2rpc:
    interval_ms: 100
    timeout_ms: 1.5

process_langgraph:
  engine: "python3.11"
  entry: "src/workflow.py"
  mode: "subprocess"  # DSH 启动时创建
  memory_mb: 2000
  timeout_min: 30
```

---

## 8. 组件接口规格

### 8.1 感知层接口 (Fly64 → 决策层)

```python
# fly64/interface.py — 脑模型统一接口规格

@dataclass
class BrainInferenceResult:
    """脑模型推理结果 — 感知层→决策层"""
    # 元数据
    policy_id: str
    tick_count: int
    compute_ms: float
    
    # 核心决策输出
    steering_bias: float           # [-1, +1] 总体控费方向
    anomaly_score: float           # [0, 1] 异常置信度
    confidence: float              # [0, 1] 推理置信度
    
    # 感知输出
    scene_sig: List[float]         # 128维保单指纹
    familiarity: float             # 历史模式熟悉度
    flow_asymmetry: float          # 光流不对称度
    flow_self_motion: float        # 自运动分量(保费结构变化)
    
    # 蘑菇体输出
    kc_sparsity: float             # KC稀疏度
    mbon_scores: Dict[str, float]  # {forward, left, right, jump, explore}
    
    # 中央复合体输出
    cx_compass: int                # 罗盘位置 0-15
    cx_steering: float             # 转向偏置
    cx_disp_x: float               # 锚点X(根因距离)
    cx_disp_z: float               # 锚点Z(严重程度)
    
    # 神经活动汇总
    region_activity: Dict[str, float]  # 8区域活跃度
    spike_rate: float
    
    # seed-64追溯
    seed64: str


# 仲裁器输入
@dataclass
class ArbitrationInput:
    """5级仲裁链输入"""
    rule_result: Optional[Dict]          # L1: 23 Agent 规则输出
    brain_result: Optional[BrainInferenceResult]  # L2: 脑模型输出
    llm_result: Optional[Dict]           # L3: 13 Agent LLM输出
    config: Dict                         # 仲裁配置(阈值/权重)
    policy_id: str
    
@dataclass
class ArbitrationResult:
    """仲裁决策输出"""
    final_decision: Dict                  # 最终决策
    confidence: float                     # 决策置信度
    arbitration_chain: List[Dict]         # 因果链
    seed64: str                           # 最终seed
    human_required: bool                  # 是否需要人类审核
```

### 8.2 执行层接口 (DSH → 外部)

```javascript
// plugin/brain-rpc-api.js — RPC接口规格

const brainRpcApi = {
  // ── 脑模型状态查询 ──
  'brain-status': {
    method: 'GET',
    path: '/fly64/api/state',
    response: {
      ok: 'boolean',
      steeringBias: 'float(-1..1)',
      anomalyScore: 'float(0..1)',
      confidence: 'float(0..1)',
      compassPos: 'int(0..15)',
      mbonOutput: 'float[5]',
      gainWeights: 'float[5]',
      regionActivity: '{region: float}',
      spikeRate: 'float',
      seed64: 'string',
      timestamp: 'ISO8601'
    },
    cache: '100ms',
    deprecated: false
  },

  // ── 脑模型控制 ──
  'brain-control': {
    method: 'POST', 
    path: '/fly64/api/control',
    body: {
      action: 'string',       // steer | train | reset | override
      value: 'float',
      seed64: 'string(optional)'
    },
    response: {
      ok: 'boolean',
      controlSeq: 'int',
      applied: 'boolean'
    }
  },

  // ── 脑模型推理(触发一次完整分析) ──
  'brain-infer': {
    method: 'POST',
    path: '/fly64/api/infer',
    body: {
      policyId: 'string',
      mode: 'native | hybrid',
      seed64: 'string(optional)'
    },
    response: {
      ok: 'boolean',
      result: 'BrainInferenceResult',
      durationMs: 'int'
    },
    timeout: '5000ms'
  },

  // ── 神经活动遥测 ──
  'brain-telemetry': {
    method: 'GET',
    path: '/fly64/api/telemetry',
    response: {
      ok: 'boolean',
      telemetry: {
        spikeRates: 'float[8]',        // 8区域发放率
        regionNames: 'string[8]',
        energyUsage: 'float',
        uptime: 'int',
        totalTicks: 'int'
      }
    },
    deprecated: false
  },

  // ── 多巴胺学习(自适应更新) ──
  'brain-train': {
    method: 'POST',
    path: '/fly64/api/train',
    body: {
      policyId: 'string',
      feedback: 'float(-1..1)',  // 学习信号
      module: 'mb | gain | all',
      targetKey: 'string(optional)'
    },
    response: {
      ok: 'boolean',
      learningUpdate: {
        deltaW: 'float',
        newWeights: 'float[5]'
      }
    },
    timeout: '2000ms',
    deprecated: false
  }
}
```

### 8.3 工具注册接口 (DSH ghb-host.js)

```javascript
// plugin/ghb-host.js — 新增 brain_* 工具

// brain_infer
ctx.tools['brain_infer'] = {
  name: 'brain_infer',
  description: '调用Fly64果蝇脑模型对保单进行神经推理分析',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string', description: '保单号' },
      mode: { type: 'string', enum: ['native', 'hybrid'], default: 'hybrid' }
    },
    required: ['policy_id']
  },
  handler: async (args, ctx) => {
    return await bridge2rpc.infer(args.policy_id, args.mode || 'hybrid')
  }
}

// brain_state
ctx.tools['brain_state'] = {
  name: 'brain_state',
  description: '查询Fly64脑模型实时状态快照 (含 steering_bias/anomaly_score 等)',
  parameters: { type: 'object', properties: {} },
  handler: async (_, ctx) => {
    return await bridge2rpc.getState()
  }
}

// brain_train
ctx.tools['brain_train'] = {
  name: 'brain_train',
  description: '以核实反馈触发Fly64脑模型多巴胺学习, 自适应更新规则权重',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string' },
      feedback: { type: 'number', description: '反馈信号 -1~+1' },
      target_module: { type: 'string', enum: ['mb', 'gain', 'all'], default: 'all' }
    },
    required: ['policy_id', 'feedback']
  },
  handler: async (args, ctx) => {
    return await bridge2rpc.train(args.policy_id, args.feedback, args.target_module)
  }
}

// brain_visualize
ctx.tools['brain_visualize'] = {
  name: 'brain_visualize',
  description: '获取神经活动可视化数据',
  parameters: { type: 'object', properties: {} },
  handler: async (_, ctx) => {
    return await bridge2rpc.getTelemetry()
  }
}
```

### 8.4 LangGraph 集成接口

```python
# src/workflow_hybrid.py — 脑模型注入 LangGraph 工作流

def create_hybrid_workflow(config: Dict) -> CompiledStateGraph:
    """创建包含脑模型的混合工作流"""
    
    # 1. 标准 LangGraph builder
    builder = StateGraph(AgentState)
    
    # 2. 原有节点 (规则引擎)
    add_standard_nodes(builder, config)
    
    # 3. 新增: 脑模型推理节点
    builder.add_node('brain_inference', brain_inference_node)
    
    # 4. 新增: 分歧检测节点
    builder.add_node('divergence_detector', divergence_detector_node)
    
    # 5. 新增: 加权仲裁节点
    builder.add_node('weighted_arbiter', weighted_arbiter_node)
    
    # 6. Modified: 条件路由
    builder.add_conditional_edges(
        'brain_inference',
        route_hybrid,  # 分歧>0.3 → LLM; 否则直接仲裁
        {
            'llm_enhanced_path': 'start_parallel',  # 走原有LLM Agent
            'direct_arbitration': 'weighted_arbiter', # 跳过LLM
            'rule_engine_path': 'start_parallel'      # 走规则
        }
    )
    
    # 7. 仲裁输出
    builder.add_edge('weighted_arbiter', 'pre_report')
    
    return builder.compile()


def brain_inference_node(state: AgentState) -> Dict:
    """脑模型推理节点 — 通过 bridge2rpc 调用"""
    policy_data = state.get('_policy_data') or {}
    
    # 调用 bridge2rpc
    brain_result = requests.post(
        'http://localhost:3080/fly64/api/infer',
        json={'policyId': policy_data.get('policy_id'), 'mode': 'native'}
    ).json()
    
    return {
        'brain_steering_bias': brain_result['steeringBias'],
        'brain_anomaly_score': brain_result['anomalyScore'],
        'brain_confidence': brain_result['confidence'],
        'brain_scene_sig': brain_result['sceneSig'],
        'brain_seed64': brain_result['seed64'],
        # ... 传递到 seed-64 链
    }


def route_hybrid(state: AgentState) -> str:
    """分歧检测路由"""
    brain_conf = state.get('brain_confidence', 0)
    anomaly = state.get('brain_anomaly_score', 0)
    
    if brain_conf < 0.5 and anomaly > 0.7:
        return 'llm_enhanced_path'  # 需要LLM深度分析
    elif brain_conf > 0.75:
        return 'direct_arbitration'  # 脑模型高置信
    else:
        return 'rule_engine_path'    # 规则引擎补充
```

---

## 9. 实施路线图与里程碑

### 9.1 四阶段实施路线图

```
Phase A: 基础集成 (P0, Week 1-3)
  ┌────────────────────────────────────────────────────────────────┐
  │ milestone A1: bridge2rpc 适配器 + seqlock 读通                  │
  │ milestone A2: 3项 P0 规则 Agent 被脑模型替代                    │
  │   - reconciliation → Retina ON/OFF                             │
  │   - stability → StuckDetector                                  │
  │   - ramp_analysis → EMD 4方向                                  │
  │ milestone A3: MushroomBody KC → 替换 anomaly_detection         │
  │ milestone A4: 🧠 Web Tab 基础版 (CX罗盘+MBON+因果链)            │
  │ 验证: 脑模型召回率 > 60%, bridge2rpc < 2ms                    │
  └────────────────────────────────────────────────────────────────┘

Phase B: 核心融合 (P1, Week 4-6)
  ┌────────────────────────────────────────────────────────────────┐
  │ milestone B1: CentralComplex 16列罗盘 → 替换 4级分层异常       │
  │ milestone B2: MBON 5通道 → 替换 health_score                   │
  │ milestone B3: TargetTracker → 增强 FWA 引擎 (61规则+卡尔曼)     │
  │ milestone B4: GainController → 动态权重 (替换静态6因子)         │
  │ milestone B5: TurnAdaptation → 控费策略疲劳检测                 │
  │ 验证: 召回率 > 80%, divergence < 0.3                          │
  └────────────────────────────────────────────────────────────────┘

Phase C: 混合仲裁 (P2, Week 7-9)
  ┌────────────────────────────────────────────────────────────────┐
  │ milestone C1: 5级仲裁链完整实现 (L1-L5)                        │
  │ milestone C2: seed-64 可追溯性全链路                           │
  │ milestone C3: divergence 检测 + 自动升级 (Mode 3 核心)         │
  │ milestone C4: brain_* 4个 DSG 工具注册                        │
  │ milestone C5: AgentState 40字段扩展 + 注册表注册              │
  │ 验证: 混合仲裁模式召回率 > 90%, 因果链可追溯                    │
  └────────────────────────────────────────────────────────────────┘

Phase D: 生产就绪 (P3, Week 10-12)
  ┌────────────────────────────────────────────────────────────────┐
  │ milestone D1: 三进程部署拓扑 + 进程守护                        │
  │ milestone D2: 完整 Web 🧠 Tab + F643 WS 0.5Hz                 │
  │ milestone D3: 多巴胺在线学习 (核实反馈→规则自适应)              │
  │ milestone D4: 性能调优 (脑模型推理 < 1s, 全管线<10min)         │
  │ milestone D5: 回归测试: 6134 测试 + 脑模型版本通过              │
  │ 验证: 全管线通过, 脑模型仲裁 > 90% 与原始版一致                │
  └────────────────────────────────────────────────────────────────┘
```

### 9.2 组件依赖关系

```
P0 (Week 1-3)         P1 (Week 4-6)          P2 (Week 7-9)        P3 (Week 10-12)
─────────────         ─────────────          ─────────────         ──────────────

bridge2rpc ─────────→ TargetTracker ───────→ 5级仲裁链 ──────────→ 三进程部署
     │                      │                     │                      │
     ├→ Retina ON/OFF       │                     │                      │
     │       │              ├→ GainController     │                      │
     │       └→ reconci-    │       │             │                      │
     │          liation      │       └→ 动态权重    │                      │
     │                      │                      │                      │
     ├→ StuckDetector      ├→ TurnAdaptation     ├→ seed-64 追溯        │
     │       │              │       │              │                      │
     │       └→ stability   │       └→ 策略疲劳    │                      │
     │                                             │                      │
     ├→ EMD 4方向          └→ CX 16列罗盘        ├→ divergence 检测     │
     │       │                      │              │                      │
     │       └→ ramp         └→ 4级分层异常        │                      │
     │                                             │                      │
     ├→ MB KC ─────────────→ MBON 5通道 ────────→ brain_* tools          │
     │       │                      │              │                      │
     │       └→ anomaly_     └→ health_score       │                      │
     │          detection                            │                      │
     │                                              │                      │
     └→ 🧠 Tab 基础版 ────→ 🧠 Tab 完整版 ──────  → WebSocket + 控制面板  │
```

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| **脑模型精度不足** (< 60%) | 中 | 高 — 误报/漏报 | divergence 检测自动升级到LLM; 灰度上线与原始版A/B对比 |
| **seqlock跨平台兼容** (Windows无mmap) | 高 | 中 — 无法运行 | bridge2rpc Python版用`mmap`模块替代(Windows支持); WSL备选 |
| **三进程同步死锁** | 低 | 高 — 系统挂起 | seqlock超时机制(1.5ms); 看门狗进程自动重启 |
| **40字段扩展冲突** (36 Agent并行写) | 中 | 中 — 状态不一致 | brain_* 前缀不重叠; delta返回模式; ANNOTATED reducer |
| **Web前端渲染166K神经元** | 中 | 低 — 卡顿 | 降采样到8区域聚合热图; F643 WS 0.5Hz 低频推送 |
| **多巴胺学习收敛不良** | 低 | 中 — 权重漂移 | learning_rate η 衰减(0.01→0.001); 权重范围[0.5,2.5]硬限幅 |
| **LangGraph fan-in深度不一致** (已知问题) | 低 | 高 — 节点重复执行 | 复用现有二级汇聚 pre_report 修复; 脑模型节点不参与fan-in |
| **脑模型确定性vs LLM非确定性** | 中 | 中 — 重现困难 | seed-64确保脑模型部分确定性; LLM部分记录完整prompt |

---

## 附录A: 完整组件拓扑图

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                    BRAIN-INSURANCE HYBRID — 完整组件拓扑 (166,700神经元 / 25.6M突触)        │
│                                                                                           │
│     ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│     │  Process 1: Fly64 脑模型 (Python, 50Hz)                                        │   │
│     │                                                                                 │   │
│     │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │   │
│     │  │ Retina   │  │ Flow     │  │SceneMem  │  │TargetTrk │  │ GainController  │  │   │
│     │  │ 1536 px  │  │ 光流     │  │ 30帧缓冲  │  │卡尔曼    │  │ 5通路增益       │  │   │
│     │  │ 270°视场  │  │ 自运动分离│  │ 3σ变化   │  │匈牙利匹配│  │ Δgain学习      │  │   │
│     │  │ ON/OFF   │  │ terrain  │  │场景签名  │  │航迹管理  │  │                 │  │   │
│     │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬────────┘  │   │
│     │       │              │             │             │                 │           │   │
│     │       └──────┬───────┴─────────────┴─────────────┴─────────────────┘           │   │
│     │              │                                                                 │   │
│     │       ┌──────▼──────┐  ┌───────────────┐  ┌────────────────────────────────┐  │   │
│     │       │ MushroomBody │  │CentralComplex │  │ TurnAdaptation                │  │   │
│     │       │ 2000 KC(5%)  │  │ 16列环形吸引子  │  │ left/right fatigue           │  │   │
│     │       │ MBON 5通道   │  │ 6通道自运动积分  │  │ counter/breakout drive      │  │   │
│     │       │ 多巴胺学习    │  │ 锚点路径积分   │  │ saturation=0.5              │  │   │
│     │       │ 资格迹追踪    │  │ steering_bias │  │                             │  │   │
│     │       └──────┬───────┘  └──────┬────────┘  └─────────────────────────────┘  │   │
│     │              │                 │                                             │   │
│     │              └────────┬────────┘                                             │   │
│     │                       │                                                     │   │
│     │                       ▼                                                     │   │
│     │              ┌────────────────┐                                             │   │
│     │              │ Motor Decoder  │  → steering_bias, anomaly_score             │   │
│     │              │ forward/turn   │  → confidence, seed64                       │   │
│     │              │ jump/explore   │  → scene_sig, region_activity              │   │
│     │              └────────┬───────┘                                             │   │
│     │                       │ seqlock 128B帧                                      │   │
│     └───────────────────────┼─────────────────────────────────────────────────────┘   │
│                             │                                                         │
│     ┌───────────────────────▼─────────────────────────────────────────────────────┐   │
│     │  Process 2: DSH Plugin (Node.js)                                            │   │
│     │                                                                             │   │
│     │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐     │   │
│     │  │ bridge2rpc     │  │ ghb-host.js    │  │ ghb-client.js              │     │   │
│     │  │ seqlock→JSON   │  │ 19 ghb_* tools │  │ FloatingPanel 7+1 Tab      │     │   │
│     │  │ 100ms缓存      │  │ 4 brain_* tools │  │ 🧠 Brain Tab               │     │   │
│     │  │ /fly64/api/*   │  │ rpcApi 19+4    │  │ F643 WS 0.5Hz              │     │   │
│     │  └────────┬───────┘  └───────┬────────┘  └──────────────┬─────────────┘     │   │
│     │           │                  │                           │                  │   │
│     └───────────┼──────────────────┼───────────────────────────┼──────────────────┘   │
│                 │                  │                           │                      │
│                 │ HTTP(仲裁)        │ DSH插件协议                │ WebSocket            │
│                 ▼                  ▼                           ▼                      │
│     ┌─────────────────────────────────────────────────────────────────────────────┐   │
│     │  Process 3: LangGraph (Python)                  Web UI: DSH 3080             │   │
│     │                                                                             │   │
│     │  36 Agent → StateGraph → agent_state.json       🌐 http://127.0.0.1:3080    │   │
│     │  38 nodes → fan-out/fan-in → ...                📊 📄 🗺️ 🤖 🖼️ 🔮 🧰 🧠   │   │
│     │                                                                             │   │
│     └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                       │
│     ┌─────────────────────────────────────────────────────────────────────────────┐   │
│     │  共享文件系统: data/doris/ → output/{pid}_*/agent_state.json                  │   │
│     └─────────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 附录B: 关键设计决策记录 (ADR)

| ADR | 决策 | 备选 | 理由 |
|-----|------|------|------|
| ADR-001 | 三进程拓扑 (非单体) | 单进程集成 | 隔离脑模型确定性推理与LLM非确定性推理; 独立进程可各自重启 |
| ADR-002 | seqlock作为脑模型通信基元 | HTTP/消息队列 | 微秒级延迟, 与Fly64现有设计一致 |
| ADR-003 | bridge2rpc 适配器 (非直连) | 直接seqlock到DSH | DSH是Node.js, seqlock用mmap+Python; 适配器解耦 |
| ADR-004 | brain_* 前缀字段 (非复用现有) | 复用/修改现有字段 | 避免与36 Agent并行写冲突; 清晰的责任边界 |
| ADR-005 | mode=hybrid为默认 (Mode 3) | mode=brain_native | 平衡速度与精度; divergence自动升级保证可靠性 |
| ADR-006 | 5级仲裁链 (非2级) | 3级(L1规则+L2 LLM) | 脑模型提供中间层(2s, 0 token), 在规则与LLM之间架桥 |
| ADR-007 | seed-64 可追溯性 (非UUID) | UUID/v4 | 纯整数运算, 可嵌入seqlock帧; policy_hash确保保单关联 |
| ADR-008 | 40字段扩展保持 total=False | 强类型校验 | 与现有TypedDict设计一致; .get()安全访问 |

---

*报告生成: hybrid-architect (Hybrid Architecture Designer)*  
*依赖: T1 (gbcost-analysys解构) + T2 (Fly64脑模块映射) + T3 (DSH插件集成分析)*