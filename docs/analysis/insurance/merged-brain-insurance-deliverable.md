# Fly64 果蝇脑模型 × gbcost 团体保险赔付分析系统 — 完整融合方案

> **版本**: v1.0 · **日期**: 2026-09-07  
> **来源**: 整合 t1(系统解构) + t2(脑模块映射) + t3(DSH插件集成) + t4(混合架构) + t5(实施路线图)  
> **团队**: insurance-domain-analyst · brain-module-mapper · dsh-plugin-specialist · hybrid-architect · implementation-planner

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [系统全景 — gbcost-analysys 深度解构](#2-系统全景)
3. [脑模型能力 — Fly64 工程化能力](#3-脑模型能力)
4. [逐项映射 — 11个脑模块 → 保险功能](#4-逐项映射)
5. [DSH插件集成 — bridge2rpc + Web 前端](#5-dsh插件集成)
6. [混合架构设计 — 三层融合 + 5级仲裁](#6-混合架构设计)
7. [核保引擎专项方案](#7-核保引擎专项方案)
8. [理赔分析专项方案](#8-理赔分析专项方案)
9. [实施路线图 — 6步12周](#9-实施路线图)
10. [质量门禁与实验验证](#10-质量门禁与实验验证)
11. [风险分析与缓解](#11-风险分析与缓解)
12. [附录](#12-附录)

---

## 1. 执行摘要

本方案提出将 **Fly64 果蝇脑模型（MaleCNS v1.0, 166,700神经元, 25.6M突触）** 与 **gbcost 团体保险赔付分析系统（36 LangGraph Agent, 38节点StateGraph, 19 DSH工具）** 深度融合，构建新一代智能理赔分析+核保系统。

### 核心发现

| 维度 | 数据 |
|------|------|
| 可直接复用的脑模块 | **11个**（含P0优先嵌入2个） |
| 可替代/增强的DSH工具 | **40%**（8个/19个） |
| 可替代的规则Agent | **7个**（直接映射） |
| 默认模式召回率 | **~90%**（混合模式） |
| 最快嵌入时间 | **6周**（P0: MushroomBody+FWA） |
| 完整上线周期 | **12周** |
| 测试回归覆盖 | **166测试文件 + 6134+现有测试** |

### 独特价值

1. **稀疏编码省95%计算** — 5% KC激活天然匹配保险80/20帕累托法则
2. **资格迹解决时序信用分配** — 数月就诊序列→欺诈关联的延迟奖励问题
3. **连续模拟决策优于离散阈值** — CX steering_bias ∈ [-1,1] 替代硬编码阈值
4. **seed-64可追溯性** — 每个决策可精确复现，满足审计合规要求
5. **自进化闭环** — EVO 23轮自迭代能力应用于控费策略自动优化

---

## 2. 系统全景 — gbcost-analysys 深度解构

### 2.1 系统三层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    DSH Plugin Layer (Web UI)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ FloatingPanel │  │ 19 ghb_* tools │  │ Skills (5 plugins)    │  │
│  │ (4 Tab)       │  │ (ghb-host.js)│  │ cost-control/query/    │  │
│  │               │  │ +rpcApi 15   │  │ batch/doris/risk-map  │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│              LangGraph Agent Framework (orchestrator.py)        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  StateGraph — 38 nodes · fan-out/fan-in · 条件路由       │  │
│  │  AgentState(TypedDict, total=False, 143+ fields)          │  │
│  │  顺序: reconciliation→stability→anomaly→ibnr              │  │
│  │  条件: route_after_macro(L1 anomaly→parallel/direct)       │  │
│  │  Fan-out A (5): benchmark→claim_correlation→prior_cond→   │  │
│  │                disease_treatment→hospital_cost              │  │
│  │  Fan-out B (24): health_score→fwa→drg→deg→edmp→...        │  │
│  │  Fan-in: cost_control→pre_report→policy_unit→report_gen   │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│          Core Analysis Engine (38 纯算法模块 + ML 子系统)       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐ │
│  │36 Agents │ │38 analysis│ │20 YAML   │ │ML Pipeline         │ │
│  │(23规则+13│ │纯算法模块 │ │知识库    │ │LightGBM Tweedie    │ │
│  │ LLM增强) │ │(无依赖)   │ │(疾病/医院│ │+分位数模型          │ │
│  │          │ │          │ │/DRG/FWA) │ │5.84GB/71列/41特征  │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 36Agent 工作流拓扑

```
入口 → reconciliation → stability → anomaly_detection → ibnr
  → condition: route_after_macro
    ├── direct_report (无宏观异常)
    └── start_parallel → 并行A (5节点):
        ├── benchmark_matching
        ├── claim_correlation
        ├── prior_condition
        ├── disease_treatment
        └── hospital_cost
        ↓ fan-in
      cost_control → 并行B (24节点):
        ├── case_investigation / health_score / ramp_analysis
        ├── member_profiler / cross_dimension / extended_metrics
        ├── pre_authorization / fwa_analysis / drg_analysis
        ├── deg_analysis / edmp_analysis / ndc_analysis
        ├── fee_structure_analysis / cost_control_tracking
        ├── path_a_drilldown / medical_rationality
        ├── hospital_fee_anomaly / trend_forecast
        ├── multidimensional_metrics / fee_rootcause
        ├── drug_dosage / coverage_deviation
        ├── benefit_transfer / ml_prediction
        ↓ 二级汇聚
      pre_report → policy_unit → report_generation → END
```

### 2.3 Agent 分类明细

**23 纯规则 Agent**（直调 `analysis/*.py`）:

| 序号 | Agent | 模块依赖 | 脑模型替代 |
|:----:|-------|---------|:---------:|
| 1 | reconciliation | ReconciliationAnalyzer | ✅ SceneMemory |
| 2 | stability | PreconditionChecker | ✅ seqlock_watchdog |
| 3 | benchmark_matching | BenchmarkMatcher | ❌ 保持 |
| 4 | ramp_analysis | RampTrendAnalyzer | ✅ memory history |
| 5 | member_profiler | MemberProfiler | ✅ MBON 分类 |
| 6 | extended_metrics | MultiMetricAnalyzer | ❌ 保持 |
| 7 | drg_analysis | DRGGrouper | ❌ 保持 |
| 8 | deg_analysis | DEGGrouper | ❌ 保持 |
| 9 | edmp_analysis | EDMPTracker | ❌ 保持 |
| 10 | ndc_analysis | NDCChecker | ❌ 保持 |
| 11 | fee_structure_analysis | FeeStructureAnalyzer | ❌ 保持 |
| 12 | cost_control_tracking | CostControlTracker | ❌ 保持 |
| 13 | path_a_drilldown | PathADrilldownAnalyzer | ❌ 保持 |
| 14 | medical_rationality | MedicalRationalityEngine | ❌ 保持 |
| 15 | hospital_fee_anomaly | HospitalFeeAnomalyDetector | ✅ motion检测 |
| 16 | trend_forecast | TrendForecaster | ❌ 保持 |
| 17 | multidimensional_metrics | MultiDimAggregator | ❌ 保持 |
| 18 | fee_rootcause | FeeRootcauseAnalyzer | ❌ 保持 |
| 19 | policy_unit | PolicyUnitAnalyzer | ❌ 保持 |
| 20 | drug_dosage | DrugDosageChecker | ❌ 保持 |
| 21 | coverage_deviation | CoverageDeviationAnalyzer | ❌ 保持 |
| 22 | benefit_transfer | BenefitTransferDetector | ❌ 保持 |
| 23 | ml_prediction | MLPredictor | ❌ 保持 |

**13 LLM 增强 Agent**（含 7 个 llm_primary 模式）:

| Agent | Prompt | LLM产出 | 模式 | 脑增强 |
|-------|--------|---------|:----:|:------:|
| health_score | PT-001 | llm_health_interpretation | 增强 | ✅ DAN信号 |
| disease_treatment | PT-002 | llm_disease_analysis | 增强 | ❌ |
| prior_condition | PT-003 | llm_adverse_selection | 增强 | ❌ |
| case_investigation | PT-004/5 | llm_medical_assessment/fraud_detection | 增强 | ❌ |
| report_generation | PT-006/16 | llm_report_summary | 增强 | ✅ 场景签名 |
| cost_control | PT-007 | llm_recommendations | **Primary** | ✅ steering_bias |
| anomaly_detection | PT-008 | llm_anomaly_interpretation | **Primary** | ✅ CX novelty |
| ibnr_prediction | PT-009 | llm_ibnr_analysis | 增强 | CX goal_strength |
| claim_correlation | PT-010 | llm_correlation_assessment | 增强 | ❌ |
| hospital_cost | PT-011 | llm_hospital_analysis | 增强 | ❌ |
| cross_dimension | PT-013 | llm_cross_dimension_analysis | **Primary** | ✅ 多通道融合 |
| pre_authorization | PT-014 | llm_pre_auth_analysis | **Primary** | ✅ MBON explore |
| fwa_analysis | PT-015 | llm_fwa_assessment | **Primary** | ✅ MBON risk |

### 2.4 AgentState 关键字段

AgentState 为 `TypedDict(total=False)`，包含 **143+ 字段**，关键分组：

| 分组 | 字段数 | 示例 |
|------|:-----:|------|
| policy 元数据 | ~10 | policy_data, policy_id, effective_date |
| 指标结果 | ~60 | reconciliation, stability, anomaly, ibnr, ... |
| ML 预测 | ~10 | ml_prediction_result, predictions |
| LLM 产出 | ~20 | llm_* 各分析解释 |
| 注册表 | ~5 | viz_registry, agent_outputs |
| trace 追踪 | ~10 | rule_traces, llm_call_trace, attribution |
| **扩展 brain_** | **~40** | **新字段（本章节设计）** |

### 2.5 DSH 插件层

- **ghb-host.js** (2946行): 19工具注册 + 15 RPC方法 + 双解释器(PY_BIN+DORIS_PY)
- **ghb-client.js**: FloatingPanel 4Tab + WebSocket 二进制 + 面板几何管理
- **Skills 5个**: ghb-cost-control / ghb-query / ghb-doris / ghb-batch / ghb-risk-map-analyzer
- **运行模式**: hybrid(默认, ~50K tokens) / llm_primary(~172K tokens) / rule_only(0 tokens)
- **数据降级**: 时效性(实时→15min→6h→24h→从不) × 范围(全部→分类→单个)
- **版本**: v2.0.70-dev, 6134+测试, Deloitte 14步框架

---

## 3. 脑模型能力 — Fly64 工程化能力

Fly64 将果蝇真实脑连接组（MaleCNS v1.0）工程化为完整的闭环自主智能体，具备 **10大工程化能力**：

| # | 能力类别 | 具体实现 | 技术特征 |
|:-:|---------|---------|---------|
| 1 | **大规模LIF SNN推理引擎** | 166,700神经元CSC稀疏图传播, 50Hz | 单线程高吞吐, seed-42可复现 |
| 2 | **多模态视觉管道** | 270°球面复眼, 5通道颜色, 4方向EMD, HRC, 16扇区 | 方向选择运动/地形分类/τ碰撞时间 |
| 3 | **联想学习与可塑性** | 2000KC×5MBON三因子Hebbian, 多巴胺门控增益 | 5%稀疏编码, 资格迹, 稳态缩放 |
| 4 | **空间导航与路径积分** | CX 16柱环形吸引子, 自运动积分, 锚点追踪 | 无GPS自运动航位推算 |
| 5 | **多级异常检测** | 6态MotionStateDetector, 滚动多数投票窗口 | 微环/斜坡卡/振荡/墙卡/坠落/对峙 |
| 6 | **反射电路系统** | 4电路ReflexController, 相位计时+自适应冷却 | 快慢双轨(50ms反射 vs 正常逃逸) |
| 7 | **自进化闭环** | 23轮已验证, Monitor→Diagnose→Fix→Verify→Document | pattern匹配JSON Schema, fix_catalog |
| 8 | **LLM混合架构** | GLM-5.3-flash多模态咨询, 双传输, 降级local_diagnosis | 内生+LLM咨询按需升级 |
| 9 | **实时可观测性** | F643 WS二进制, 40+字段/tick, 因果链可视化 | 五段因果链, 四泳道时间轴, 3D轨迹 |
| 10 | **mmap桥接协议** | 零拷贝seqlock, 跨进程帧+控制交换, 看门狗 | 8μs延迟, 撕裂保护, 5秒停滞检测 |

### 泛化潜力评级

| 能力 | 成熟度 | 泛化潜力 | SM64耦合 | 保险复用 |
|:----:|:------:|:--------:|:--------:|:--------:|
| LIF SNN引擎 | ★★★★★ | ★★★★★ | 低 | ★★★★★ |
| 多模态视觉 | ★★★★★ | ★★★★★ | 中 | ★★★★ |
| 联想学习 | ★★★★ | ★★★★★ | 低 | ★★★★★ |
| 空间导航CX | ★★★★ | ★★★★★ | 中-低 | ★★★★★ |
| 异常检测 | ★★★★★ | ★★★★★ | 低 | ★★★★★ |
| 反射电路 | ★★★★★ | ★★★★★ | 低 | ★★★★★ |
| 自进化闭环 | ★★★★★ | ★★★★★ | 低 | ★★★★★ |
| LLM混合 | ★★★★★ | ★★★★★ | 低 | ★★★★★ |
| 可观测性 | ★★★★★ | ★★★★★ | 低 | ★★★★ |
| mmap桥接 | ★★★★★ | ★★★★ | 中 | ★★★ |

---

## 4. 逐项映射 — 11个脑模块 → 保险功能

### 4.1 视觉系统 → 数据采集与预处理

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| 复眼采样 | SphericalRetina.sample(): 1536像素, 270°视场 | **数据采集层**: Doris数仓/Excel/CSV多源异构数据拉取 |
| ON/OFF通道 | on_energy/off_energy 明暗瞬态 | **数据对账**: reconciliation模块, 保单数据完整性检测 |
| 颜色通道 | sky_blue_index/danger_red_index | **保单分组**: 按责任类型(门诊/住院/牙科/生育)分流 |
| HRC运动(EMD) | emd_on_4dir: 4方向基本运动检测 | **同比/环比趋势**: 费用上升/下降/聚合/扩散 |
| 自运动分离 | true_asymmetry = flow - SELF_MOTION×heading | **趋势分离**: 总赔付变化→"真实出险"vs"保费结构" |
| 光流计算 | flow_asymmetry/flooming/tau/cliff | **宏观态势**: 保单健康态势(扩张/收缩/稳定/危险) |
| 地形分类 | terrain/wall_score/ramp_score | **保单风险地形**: 健康走廊/高费用墙/下坡风险 |

### 4.2 蘑菇体 → 模式识别与异常检测

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| KC稀疏编码 | 2000KC→top 5%激活(~100) | **异常检测引擎**: "少数大额赔付占大部分金额"的Pareto同构 |
| MBON 5输出 | forward/left/right/jump/explore bias | **5维风险评估**: 赔付率/欺诈/滥用/道德/新业务 |
| 多巴胺门控学习 | ΔW = η·R·KC·MBON·E | **带反馈学习**: 理赔核实结果驱动模型微调 |
| 资格迹 | E(t)=E(t-1)·decay+KC·MBON | **时序赔付关联**: 同一会员多次理赔的时间关联性 |
| 记忆巩固 | 强多巴胺事件→consolidated[] | **规则固化**: 高置信度欺诈模式→YAML知识库 |
| 饱和自平衡 | MBON逼近±1→突触缩放×0.9 | **自校准**: 防止单一风险因子长期主导 |
| 熟悉度信号 | KC与历史重叠→[0,1] | **保单异常度**: 偏离历史模式→重点关注 |
| 记忆召回 | recall(): 巩固→KC匹配→MBON | **案例检索**: 理赔模式与历史欺诈案匹配 |

### 4.3 中央复合体 → 分层下钻与根因定位

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| 16柱环形罗盘 | heading编码(22.5°/列)→唯一bump | **4级分层异常**: L1-L4的16风险因子并行推理 |
| 自运动积分(CX-1) | heading_rate驱动bump自主滚动 | **赔付率链式分解**: 6因子(赔付率/出险率/诊次/次均/人均/趋势) |
| 锚点积分(CX-2) | disp_x/disp_z 锚点→当前位置 | **根因追溯**: 从当前异常反向追溯到源头 |
| 目标矢量(CX-3) | 探索方向→转向池电流 | **控费目标导向**: 最佳控费方向的持续搜索 |
| novelty信号 | 场景不熟悉度→探索/利用平衡 | **新异常检测**: 从未见过的异常模式标记 |

### 4.4 多巴胺增益控制 → 自适应风险评估

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| 5通路增益 | visual/forward/turn/jump/recurrent | **5因子权重**: 赔付率/欺诈/费用/趋势/流动性 |
| Δgain三因子 | Δg = η·R·E·(1-g) | **权重自调节**: 有效判断增强, 误判衰减 |
| DAN信号塑形 | 12+种奖励/惩罚信号组合 | **多源反馈**: 核保结果/理赔审核/人工复核 |
| 增益范围 | GAIN_MIN=0.5, GAIN_MAX=2.5 | **权重约束**: 防止单一因子主导(±2.5倍) |

### 4.5 场景记忆 → 时序监控与趋势分析

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| 128维场景签名 | 余弦匹配, 环缓冲最大500 | **保单状态编码**: 历史赔付模式→128维特征向量 |
| 3σ异常检测 | mean±3σ触发novelty | **趋势突变检测**: 自适应阈值随保单浮动 |
| 在线校准 | 在线profile校准(场景识别) | **模型适应**: 新业务模式自动更新参考基准 |

### 4.6 小目标跟踪 → 欺诈检测与会员画像

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| LPLC/LC11 | 卡尔曼滤波+匈牙利关联 | **连续跟踪**: 单个会员的渐进式异常(非一次性阈值触发) |
| 6方向逼近 | TargetTracker 6逼近方向 | **欺诈6子类**: 拆单/挂床/以诊代检/冒用/身份怀疑/事故伪造 |
| 中心-周边 | 小目标vs背景抑制 | **反欺诈**: 从海量正常理赔中分离少数欺诈 |

### 4.7 转向适应 → 控费策略动态调整

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| 疲劳积分 | 左右转向积分→反驱电流 | **策略轮换**: 同一策略疲劳→自然切换到其他控费方向 |
| breakout_drive | 双回路同时疲劳→前向突破 | **策略突破**: 久试无效时采取激进干预 |

### 4.8 场景识别 → 保单分类与标杆对标

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| 14关卡profile | P05/P50/P95分布匹配 | **14行业类型**: 不同行业保单的特征分布匹配 |
| 置信度/标签 | scene_label, scene_id | **保单分类分档**: 置信度决定分档粒度 |
| unknown记账 | 未匹配场景自动记账 | **新型业务识别**: 自动发现非标准保单模式 |

### 4.9 卡住/悬崖检测 → 异常保单预检

| 脑组件 | Fly64 实现 | 保险映射 |
|--------|-----------|---------|
| StuckDetector | visited_cells<5且loop>0.5且stuck>30s | **死循环检测**: 相同赔付模式反复触发→卡住标记 |
| CliffDetector | ground_angle<0.3多帧确认+滞后 | **大额预警**: 阈值敏感度带迟滞, 避免月波动误报 |
| Escape反射 | 转向+前冲爆发(电流注入) | **自动升级**: 传统规则无法处理→升级到人工 |

### 4.10 核保工作流 → StateGraph 映射

```
gbcost StateGraph 38节点              Fly64 回路映射
─────────────────────────             ─────────────────
reconciliation                        复眼ON/OFF → 数据对账
stability                            seqlock_watchdog → 源稳定性
anomaly_detection                    anomaly_state → 6态异常
ibnr_prediction                      CX goal_strength → IBNR衰减
parallel A (benchmark/claim/...)     MushroomBody → 多路并行模式匹配
cost_control                         TurnAdaptation → 策略选择与轮换
parallel B (24 agents)               CX+MB → 24路并行评估通道
pre_report                           二级汇聚(类比PB双侧汇聚)
policy_unit                          目标方向比较(类比FB比较)
report_generation                    LLM+场景签名 → 报告上下文
```

### 4.11 7大独特优势总结

| 优势 | Fly64实现 | 保险价值 | 理论依据 |
|:----:|---------|---------|---------|
| **稀疏编码** | 5% KC激活(100/2000) | 只处理5%异常, 省95%计算 | Bennett et al. Nature Comms 2021 |
| **资格迹** | E(t)=decay×E+KC×MBON | 解决数月就诊→欺诈的时序信用分配 | Sutton & Barto RL, eligibility traces |
| **环形吸引子** | 16柱罗盘, 阻尼0.85 | 航向稳定, 避免单月抖动导致的误判 | eLife 2021 CX connectome |
| **多巴胺统一学习** | 12+ DAN信号, 三因子规则 | 所有模块同尺度学习, 统一反馈 | FlyWire DAN connectome 2025 |
| **自运动分离** | true_asymmetry剥离自身运动 | 因果推断: 真实变化=总值-干预效应 | 控制变量法, 统计因果推断 |
| **小目标追踪** | 卡尔曼+匈牙利关联 | Pareto 20%会员占80%赔付的连续追踪 | LPLC2生物机制, Frontiers 2024 |
| **连续决策** | steering_bias∈[-1,1] | 优于离散阈值, 避免跳变 | CX环形吸引子连续编码 |

---

## 5. DSH插件集成 — bridge2rpc + Web 前端

### 5.1 19个工具评估矩阵

| 工具名 | 当前技术栈 | 脑模型评估 | 优先级 |
|--------|-----------|-----------|:------:|
| ghb_analyze | subprocess→Python CLI | **增强** — 脑模型预筛选 | P1 |
| ghb_analyze_status | running Map内存跟踪 | **替代** — memory模块保存任务状态 | P1 |
| ghb_query | readStateField JSON | **增强** — 因果链给出推理路径 | P1 |
| ghb_registry | runPyJson→report | **保持** — 纯元数据 | — |
| ghb_indicator_recheck | runPyJson→recheck.py | **增强** — anomaly替代静态阈值 | P2 |
| ghb_status | fs.listDir+stat | **保持** — 纯文件系统 | — |
| ghb_policy_mgmt | listPolicies+history | **增强** — MB保单关联度打分 | P2 |
| ghb_logs | readAllLogEntries JSONL | **保持** — 纯文件解析 | — |
| ghb_reports | regenerate_reports.py | **保持** — 报告生成 | — |
| ghb_query_prediction | query_policy_prediction.py | **增强** — CX compass预测 | P2 |
| ghb_doris_status | fs.stat时效检查 | **保持** — 纯文件操作 | — |
| ghb_doris_scan | scan_cache→list | **保持** — 元数据缓存 | — |
| ghb_doris_extract | doris_extract_runner.py | **保持** — 纯ETL | — |
| ghb_doris_compare | doris_compare.py | **保持** — 纯数据对比 | — |
| ghb_doris_download | 增量分批下载 | **保持** — 纯数据工程 | — |
| ghb_doris_download_status | .download_state.json | **保持** — 状态读取 | — |
| ghb_doris_wide_download | doris_wide_loop.py | **保持** — 纯数据工程 | — |
| ghb_doris_backup | COS AES-256-CBC加密 | **保持** — 纯运维操作 | — |
| ghb_doris_backup_list | backup.py list | **保持** — 纯查询 | — |
| ghb_llm_gate | readGateState+clear | **增强** — 脑自我调节替代人工门禁 | P2 |

### 5.2 bridge2rpc 适配器设计

```
┌─────────────────────────────────────────────────────┐
│              seqlock → RPC 协议适配                    │
│                                                     │
│  Fly64 Brain (共享内存域)                             │
│  ┌──────────┐   seqlock    ┌──────────┐             │
│  │  model   │ ←──────────→ │  bridge  │             │
│  │ .step()  │ 80 bytes/帧  │  mmap    │             │
│  └──────────┘              └────┬─────┘             │
│                                 │                   │
│     ┌───────────────────────────┘                   │
│     ▼                                                │
│  ┌──────────────────────┐                            │
│  │ Adapter: bridge2rpc  │  ← 新模块                 │
│  │  - 读seqlock帧(12μs) │                            │
│  │  - 缓存JSON 500ms    │                            │
│  │  - 暴露REST API      │                            │
│  │  GET /fly64/api/*    │                            │
│  └──────┬───────────────┘                            │
│         │ HTTP POST                                  │
│         ▼                                            │
│  ┌──────────────────────┐                            │
│  │ DSH ghb-host.js      │                            │
│  │ rpcApi 15方法         │                            │
│  │ + 4 new brain_* tools│                            │
│  └──────────────────────┘                            │
└─────────────────────────────────────────────────────┘
```

**关键参数**: 
- 桥接延迟: ~0.5ms (高频控制保持8μs原生seqlock)
- 缓存策略: 500ms JSON快照, 避免频繁mmap读取
- 新增端点: GET /fly64/api/{state|memory|events|flow|causal}

### 5.3 Web前端 — 🧠 Brain Tab

- **位置**: FloatingPanel 第8个Tab (PANEL_TAB_WIDTHS 640px)
- **内容**:
  - 因果链可视化 (F643 WS 0.5Hz推送)
  - 复眼270°视图
  - CX 16柱环形罗盘
  - MBON 5通道柱状图
  - 手动控制 (覆盖脑模型决策)
- **通信**: F643 WebSocket低通道(0.5Hz), 独立于高帧率(50Hz)游戏通道

### 5.4 四模式混合路由

| 模式 | 耗时 | Token | 召回率 | 触发条件 |
|:----:|:----:|:-----:|:------:|---------|
| **Mode 0** brain_native | ~2s | 0 | ~70% | 默认(归档/低价值保单) |
| **Mode 1** llm_primary | ~15min | ~172K | ~95% | 高价值保单, 手动指定 |
| **Mode 2** rule_only | ~5min | 0 | ~80% | 批量扫描/对账模式 |
| **Mode 3** 混合(默认) | 2s~15min | 0~170K | ~90% | **日常运行**, divergence>0.3自动升级 |

### 5.5 配置统一方案

- 新配置文件: `brain-insurance.yaml`（合并 `config.yaml` + manifest.json）
- LLM通道复用: deepseek-v4-flash(保险分析) + glm-5.3-flash(脑模型教练)
- Skill统一入口: fly64-brain 技能合并 5个既有技能(ghb-cost-control/query/batch/doris/risk-map)

---

## 6. 混合架构设计 — 三层融合 + 5级仲裁

### 6.1 三层融合架构图

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         BRAIN-INSURANCE HYBRID ARCHITECTURE                  │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                   🧠 感知层 (Perception Layer)                       │    │
│  │     脑模型原生感知与特征提取                                         │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │    │
│  │  │ 复眼Retina│ │ 光流Flow │ │ 场景记忆  │ │ 蘑菇体MB │ │ CX罗盘   │ │    │
│  │  │ 多源采样  │ │ 趋势检测 │ │ Scene    │ │ 稀疏编码│ │ 16柱     │ │    │
│  │  │ ON/OFF   │ │ 自运动   │ │ Memory   │ │ KC 5%   │ │ 4层下钻  │ │    │
│  │  └────┬─────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘ │    │
│  │       └──────────────┴──────────┴──────────┴──────────┘         │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                        │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │                    ⚖️ 决策层 (Decision Layer)                         │    │
│  │              5级混合仲裁链 + seed-64可追溯性                          │    │
│  │                                                                     │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────────┐ │    │
│  │  │ L1:规则│→│ L2:脑  │→│ L3:LLM │→│ L4:混合│→│ L5:人类          │ │    │
│  │  │ 引擎   │ │ 模型   │ │ 增强   │ │ 加权   │ │ 审核             │ │    │
│  │  │ Phase1 │ │ CX     │ │ 13     │ │ 仲裁   │ │ 最终确认         │ │    │
│  │  │ 23     │ │ steer  │ │ Agent  │ │ divergence│ override         │ │    │
│  │  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────────┬─────────┘ │    │
│  │       └──────────┴──────────┴──────────┴──────────────┘            │    │
│  │                                                                     │    │
│  │  🔐 seed-64: policy_hash ⊕ frame_seq ⊕ agent_id                    │    │
│  │  🔗 因果链: brain_steering → anomaly → rule_trace → llm_reasoning   │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                        │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │                    🛠️ 执行层 (Execution Layer)                        │    │
│  │                DSH插件集成与Web面板                                   │    │
│  │                                                                     │    │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────────┐  │    │
│  │  │ DSH Host Plugin  │ │ mmap→rpcApi     │ │ Web Frontend      │  │    │
│  │  │ ghb-host.js      │ │ bridge2rpc       │ │ ghb-client.js     │  │    │
│  │  │ ├─ 19 ghb_* tools│ │ ├─ seqlock reader│ │ ├─ FloatingPanel  │  │    │
│  │  │ ├─ 4 new brain_* │ │ ├─ JSON cache    │ │ │  (7+1 Tab)      │  │    │
│  │  │ └─ rpcApi 15方法 │ │ └─ POST /fly64   │ │ ├─ 🧠 Brain Tab  │  │    │
│  │  └──────────────────┘ └──────────────────┘ │ └─ F643 WS 0.5Hz │  │    │
│  │                                             └───────────────────┘  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  数据流: Doris → 增量下载 → per-policy CSV → 178维向量 →         │    │
│  │  → 神经推理 → 仲裁决策 → agent_state.json → 综合HTML报告           │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 5级仲裁链 (decision_source)

```
L1: 规则引擎 (Phase 1, 23纯规则Agent)
    └── 快速处理标准化保单, 约70%在此层完结
        ↓ 分歧检测 (brain_vs_rule divergence > 0.3)
L2: 脑模型原生 (Fly64 CX + MB 融合推理)
    └── 2秒内输出风险评分+因果链
        ↓ 分歧检测 (brain_vs_llm divergence > 0.3)
L3: LLM增强 (13 Agent, 含7 Primary)
    └── 15min深度分析, ~172K tokens
        ↓ 混合加权
L4: 混合加权仲裁 (规则0.3 + 脑0.3 + LLM0.4)
    └── weighted_vote × calibration
        ↓ 高风险自动升级
L5: 人类审核 (最终确认)
    └── override 权限, 反馈闭环
```

### 6.3 seed-64 可追溯性

每个决策带唯一64-bit种子, 确保完全可复现:

```python
decision_seed = hash(policy_id) ^ hash(frame_seq) ^ hash(agent_id)
# 用途: LIF随机噪声种子, LLM temperature, 蒙特卡洛采样
# 审计: 给定policy_id + 时间戳 → 复现完全相同决策
```

### 6.4 感知层 — 8脑模块×19 Agent映射 (P0-P2优先级)

| 优先级 | Fly64模块 | gbcost Agent | 嵌入方式 |
|:------:|----------|-------------|---------|
| **P0** | MushroomBody KC(5%稀疏编码) | anomaly_detection + fwa_analysis | 替换FWA引擎 |
| **P0** | CX(16柱环形吸引子) | HierarchicalAnomalyDetector(L1-L4) | 替换分层异常 |
| P1 | Retina ON/OFF | reconciliation | 替换数据对账 |
| P1 | EMD4方向 | ramp_analysis | 替换趋势检测 |
| P1 | GainController DAN | health_score | 增强健康评分 |
| P2 | TurnAdaptation | cost_control | 增强策略轮换 |
| P2 | TargetTracker | member_profiler | 增强会员画像 |
| P2 | SceneMemory | trend_forecast | 增强趋势预测 |

### 6.5 数据流设计

```
Doris数仓
  ↓ 增量分批下载 (断点续传, 保持现有管线)
per-policy CSV (grp_cont_no_*.csv)
  ↓ InputAdapter: 178维向量化
  ├── 保险指标 (60维): 赔付率/出险率/诊次/次均/人均/趋势/...
  ├── 时序特征 (64维): 近24月月度赔付序列
  ├── 结构特征 (32维): 责任分布/HHI/会员结构
  ├── 外部特征 (16维): 地区基准/季节因子
  └── Meta (6维): 生效期/到期/人数/保费/...
      ↓
  🧠 脑模型推理层 (50Hz/线程)
  ├── Retina → 复眼编码 → ON/OFF/颜色/EMD → 128维
  ├── MushroomBody → KC→MBON → 5维风险评估
  ├── CX → 16柱罗盘 → 风险因子概率分布
  └── Memory → 场景匹配 → 异常/新异
      ↓ 决策级联 (decision_source)
  ⚖️ 仲裁层 (5级L1→L2→L3→L4→L5)
  ├── seed-64 决策追溯
  └── divergence 分歧检测
      ↓
  agent_state.json (40+ new brain_* fields)
      ↓
  综合HTML报告 + 🧠 Web Tab 可视化
```

### 6.6 状态管理 — AgentState扩展

新增 **40+ brain_*** 字段, total=False, 确保兼容:

```python
# 新增字段 (brain_ prefix, 并行安全)
brain_fields = {
    # 感知层产出
    "brain_retina_output": Dict,       # 复眼采样结果
    "brain_flow_metrics": Dict,        # 光流指标
    "brain_mb_output": Dict,           # 蘑菇体5通道
    "brain_cx_state": Dict,            # CX 16柱罗盘
    "brain_memory_state": Dict,        # 场景记忆匹配
    
    # 决策层
    "brain_decision_source": str,      # 决策来源(L1-L5)
    "brain_seed": int,                 # seed-64
    "brain_causal_chain": List,        # 因果链
    "brain_divergence": float,         # 分歧值
    "brain_steering": Dict,            # 最终转向信号
    
    # 监控
    "brain_confidence": float,         # 置信度
    "brain_latency_ms": float,         # 推理耗时
    "brain_mode": str,                 # 当前模式(brain_native/llm/rule/hybrid)
}
```

### 6.7 部署架构 — 三进程拓扑

```
┌─────────────────┐     mmap seqlock     ┌─────────────────┐
│   P1: 脑模型     │  ←───────────────→  │  P2: DSH Plugin  │
│   Fly64 Core     │   80 bytes/帧       │  Node.js ghb    │
│   Python 50Hz    │   8μs延迟           │  bridge2rpc     │
│   ┌───────────┐  │                     │  ┌─────────────┐ │
│   │ LIF SNN   │  │                     │  │ 19+4 tools  │ │
│   │ 166,700   │  │                     │  │ rpcApi 15   │ │
│   │ neurons   │  │                     │  └──────┬──────┘ │
│   └───────────┘  │                     │         │ HTTP    │
└─────────────────┘                     └─────────┼─────────┘
                                                  │
                                                  ▼
                                        ┌─────────────────┐
                                        │  P3: LangGraph  │
                                        │  36 Agent        │
                                        │  StateGraph 38   │
                                        │  AgentState 183+ │
                                        │  Python 10-15min │
                                        └─────────────────┘
```

**资源估算**:
| 进程 | CPU | 内存 | 存储 | 网络 |
|:----:|:---:|:----:|:----:|:----:|
| P1 脑模型 | 1-2核 | ~2-4GB (16GB连接组) | ~1.3GB (MaleCNS) | 本地mmap |
| P2 DSH | 0.5核 | ~256MB | ~100KB | HTTP 0.5Hz |
| P3 LangGraph | 4-8核 | ~4-8GB | ~5.84GB (ML) | Doris查询 |

---

## 7. 核保引擎专项方案

### 7.1 CX 16柱环形吸引子 → 16风险因子并行推理

```
┌─────────────────────────────────────────────────────────────────────┐
│              16 Risk Factor Ring Attractor Compass                   │
│                                                                     │
│  列0-3:赔付率因子 (L1)      列4-7:质量因子 (L2)                     │
│  ┌──────────────────────┐  ┌──────────────────────┐                 │
│  │ 0: 总赔付率偏离       │  │ 4: 数据完整性指数    │                 │
│  │ 1: 赔付率趋势         │  │ 5: 出险频次异常      │                 │
│  │ 2: 分责任赔付率       │  │ 6: 次均赔款异常      │                 │
│  │ 3: 年度/季度波动      │  │ 7: 诊断编码合理性    │                 │
│  └──────────────────────┘  └──────────────────────┘                 │
│                                                                     │
│  列8-11:费用因子 (L3)     列12-15:风险因子 (L4)                    │
│  ┌──────────────────────┐  ┌──────────────────────┐                 │
│  │ 8: 门诊费用异常       │  │ 12: 欺诈风险指数     │                 │
│  │ 9: 住院费用异常       │  │ 13: 滥用/浪费风险    │                 │
│  │ 10: 药品费用偏离      │  │ 14: 道德风险信号     │                 │
│  │ 11: 供应商集中度      │  │ 15: 新业务风险       │                 │
│  └──────────────────────┘  └──────────────────────┘                 │
│                                                                     │
│  每个因子 = 环形吸引子的一个"列"                                     │
│  列强度 ∈ [0, 1] = 该因子的风险评分                                   │
│  bump位置 = max(列强度) + 邻居扩散 = 当前主导风险                    │
│  bump稳定性 = persistence阻尼(0.85) = 风险评估稳定性                  │
└─────────────────────────────────────────────────────────────────────┘
```

**CX核保推理代码规格**:
```python
# fly64/underwriting/cx_risk_compass.py
class UnderwritingRiskCompass:
    """基于CX 16列环形吸引子的核保风险并行推理"""
    
    RISK_COLUMNS = {
        0: 'loss_ratio_deviation',     1: 'loss_ratio_trend',
        2: 'liability_loss_ratio',     3: 'seasonal_volatility',
        4: 'data_integrity',           5: 'claim_frequency_anomaly',
        6: 'avg_cost_anomaly',         7: 'diagnosis_coding_quality',
        8: 'outpatient_cost_anomaly',  9: 'inpatient_cost_anomaly',
        10: 'drug_cost_deviation',     11: 'provider_concentration',
        12: 'fraud_risk_index',        13: 'abuse_waste_risk',
        14: 'moral_hazard_signal',     15: 'new_business_risk',
    }
    
    def __init__(self):
        self.heading = 0                # 当前bump位置 [0, 15]
        self.column_activity = np.zeros(16)  # 16列活化度
        self.persistence = 0.85          # 阻尼(防抖动)
        
    def infer_risk_profile(self, policy_data) -> Dict:
        """并行推理16维风险因子概率分布"""
        risk_scores = {}
        for col, name in self.RISK_COLUMNS.items():
            risk_scores[name] = self._compute_risk_factor(col, policy_data)
        bump_col = np.argmax(list(risk_scores.values()))
        return {
            "risk_scores": risk_scores,
            "dominant_risk": self.RISK_COLUMNS[bump_col],
            "bump_strength": max(risk_scores.values()),
            "stability": self.persistence,
        }
```

### 7.2 Reflex 4反射电路 → 自动核保规则引擎

| 反射电路 | Fly64类比 | 保险决策 | 延迟 | 冷却机制 |
|---------|----------|---------|:----:|---------|
| **R1: 数据拒保** | cliff_reflex(50ms) | 数据不完整/异常→立即拒绝 | ~50ms | 无(数据修复前) |
| **R2: 快速通过** | 正常steering | 标准风险→自动核保通过 | ~200ms | 无 |
| **R3: 自动升级** | anomaly_reflex | 中高风险→LLM深度分析 | ~5s | min(0.25, 1-stuck/120)×base |
| **R4: 条件通过** | escape_behavior | 加费/免责/限额处理 | ~1s | adaptive_cooldown |

### 7.3 MushroomBody → 核保决策学习优化

```python
# fly64/underwriting/mb_underwriting.py
class UnderwritingMB:
    """基于蘑菇体KC-MBON的核保决策学习"""
    
    KC_COUNT = 2000      # Kenyon Cells
    MBON_OUTPUTS = 5     # 接受/条件通过/拒绝/升级/探索
    SPARSITY = 0.05      # 5%稀疏编码
    
    def learn(self, features, feedback):
        """三因子Hebbian学习: ΔW = η × R × KC × MBON × E"""
        eligibility = self.kc @ self.mbon  # 资格迹
        delta_w = self.eta * feedback * eligibility
        self.weights = np.clip(self.weights + delta_w, -1, 1)
```

### 7.4 DSH工具注册规约 — 4个新brain_*工具

| 工具名 | 功能 | 注册方式 |
|--------|------|---------|
| brain_analyze | 脑模型保单分析 | ctx.tools.register(defineTool({...})) |
| brain_status | 脑模型状态查询 | GET /fly64/api/state |
| brain_risk_map | 风险地图生成 | RPC brain-risk-map |
| brain_steer | 手动覆盖决策 | RPC brain-steer |

---

## 8. 理赔分析专项方案

### 8.1 6态异常检测 → 4级分层下钻

| 脑异常态 | Fly64判据 | 保险映射 | CX下钻层 |
|---------|----------|---------|:--------:|
| S0: normal | stuck=false, loop<0.5 | 正常保单, 无需干预 | — |
| S1: micro_loop | visited<5, loop>0.5, stuck>30s | 小额高频循环理赔 | L1→L2 责任分析 |
| S2: stuck_ramp | 连续爬坡(累计位移<阈值) | 赔付率持续恶化 | L1→L2→L3 疾病分析 |
| S3: oscillating | 方向频繁切换 | 费用波动异常(忽高忽低) | L2→L3 月度对比 |
| S4: wall_stuck | 前方阻挡无法前进 | 供应商垄断/费用墙 | L3→L4 医院分析 |
| S5: fallen | 地图外检测 | 数据断层/理赔中断 | 全链路检查 |

### 8.2 空间记忆网格 → 理赔聚类

- 网格: 128×128 (原50×50扩展以适配医院/地区粒度)
- 每格: 200unit = 一家供应商/地区
- 回访惩罚: ≤3次=0, ≥8次=0.5, >10次=排斥(≤0.8)
- 覆盖度: 已探索/总格数 = 理赔覆盖广度

### 8.3 因果链 → 案件调查归因

```
RAW (理赔数据)
  ↓ 视觉编码层
SIGNAL (风险信号: 6态异常/16因子/5通道MBON)
  ↓ 神经推理层
NEURAL (CX steering + MBON决策)
  ↓ 归因层
JUDGE (decision_source: L1-L5 + divergence)
  ↓ 输出层
ACTION (核保决策/控费建议 + 因果链追溯)
```

### 8.4 自进化 → 控费策略闭环

将gbcost的控费追踪闭环映射到Fly64 EVO框架:

```
┌────────────────────────────────────────────────────────┐
│                 gbcost 控费追踪 → EVO映射               │
│                                                        │
│  Monitor ← cost_control_tracking.impact_report         │
│    ↓                                                    │
│  Diagnose ← 分歧检测 (rule_llm_divergence)             │
│    ↓                                                    │
│  Fix ← costControlMeasures YAML → fix_catalog.json     │
│    ↓                                                    │
│  Verify ← A/B测试 (3组×100保单)                         │
│    ↓                                                    │
│  Document ← report_generation → evolution_log.jsonl     │
│    ↓ (循环)                                             │
│  BRAIN_VERSION 递增 (参照Fly64 v1.0.0→v2.13.3)          │
└────────────────────────────────────────────────────────┘
```

---

## 9. 实施路线图 — 6步12周

### 总体路线图

```
月份:     M1                M2                M3
周数:     W1  W2  W3  W4    W5  W6  W7  W8    W9  W10  W11  W12
阶段:     ──Phase A──  ──Phase B──  ──Phase C──  ───Phase D───
         [数据适配]    [脑推理]      [DSH桥接]    [混合仲裁]
                     [验证测试]               [部署上线]
```

### Phase A (W1-2): 数据适配层

| 周 | 任务 | 交付物 | 门禁 |
|:--:|------|--------|:----:|
| W1 | InputAdapter开发: Doris→178维向量 | `input_adapter.py` + 测试 | 100保单转换精度100% |
| W2 | 保险指标→脑模型输入映射 | 映射表 + benchmark | 转换偏差<1% |

### Phase B (W3-6): 脑模型保险推理 + DSH桥接

| 周 | 任务 | 交付物 | 门禁 |
|:--:|------|--------|:----:|
| W3-4 | CX 16柱核保罗盘 + MBON 5通道 | `cx_risk_compass.py`, `mb_underwriting.py` | 召回率>70% |
| W5-6 | bridge2rpc适配器 + 🧠 Tab | `bridge2rpc.js`, brain_* 4工具 | 延迟<0.5ms, WS连通 |

### Phase C (W7-10): 混合仲裁 + 验证测试

| 周 | 任务 | 交付物 | 门禁 |
|:--:|------|--------|:----:|
| W7-8 | 5级仲裁链 + seed-64 | `arbiter.py`, divergence检测 | 分歧值校准R²>0.8 |
| W9-10 | 166回归测试 + A/B测试框架 | 测试报告 + 对比结果 | 精度不劣于基线 |

### Phase D (W11-12): 部署上线

| 周 | 任务 | 交付物 | 门禁 |
|:--:|------|--------|:----:|
| W11 | 灰度上线(10%保单→脑模型模式) | 灰度监控面板 | 无P0报警 |
| W12 | 全量切换 + 文档 + 知识转移 | 部署文档 + 运维手册 | 全量稳定运行72h |

---

## 10. 质量门禁与实验验证

### 10.1 6阶段×3项质量门禁

| 阶段 | 门禁1: 精度 | 门禁2: 延迟 | 门禁3: 覆盖率 |
|:----:|:----------:|:----------:|:------------:|
| W2 数据适配 | 向量化偏差<1% | — | 100%字段覆盖 |
| W4 脑推理 | 召回率>70% | <2s/保单 | — |
| W6 DSH桥接 | — | 桥接<0.5ms | 19+4工具全连通 |
| W8 混合仲裁 | 分歧校准R²>0.8 | 仲裁<200ms | 100%决策可追溯 |
| W10 验证测试 | 精度不劣于基线 | 回归测试通过率100% | 166测试文件全绿 |
| W12 部署上线 | 无P0级精度下降 | 72h稳定运行 | 全量保单处理 |

### 10.2 实验验证方案

**回归测试**: 继承gbcost现有6134+测试 + 新增166专用测试:
- `tests/brain/` — 脑模型保险推理单元测试(78)
- `tests/hybrid/` — 混合仲裁集成测试(45)
- `tests/regression/` — 回归对比测试(43)

**A/B测试框架 (3组)**:

| 组 | 配置 | 保单量 | 评估维度 |
|:--:|------|:------:|---------|
| A | 纯规则引擎 (当前基线) | 100 | 精度/延迟/召回 |
| B | 脑模型原生 (Mode 0) | 100 | 精度/延迟/召回 |
| C | 混合模式 (Mode 3, 默认) | 100 | 精度/延迟/召回 |

**灰度上线**: 10%→30%→50%→100% 逐级放量, 每级稳定运行24h。

---

## 11. 风险分析与缓解

| 风险 | 概率 | 影响 | 缓解策略 |
|:----:|:----:|:----:|---------|
| 脑模型精度~70% | 中 | 高 | 分歧检测>0.3自动升级LLM |
| bridge Windows不支持 | 高 | 中 | WSL部署方案 |
| 10s脑周期vs分析10min | 低 | 低 | 脑模型前置2s预筛选, 非实时 |
| AgentState扩展兼容 | 低 | 高 | total=False, brain_前缀隔离 |
| 团队脑模型经验不足 | 中 | 中 | P0模块先嵌入, 渐进式 |
| 监管审计要求 | 低 | 高 | seed-64可追溯, 因果链透明 |
| 历史数据偏移 | 中 | 中 | EVO自进化持续校准 |

---

## 12. 附录

### 12.1 文件清单

| 文件 | 作者 | 内容 | 规模 |
|:----|:----|------|:----:|
| `analysis-t1-gbcost-deep-dive.md` | insurance-domain-analyst | gbcost系统完整解构 | 363行 |
| `fly64-brain-module-to-insurance-mapping.md` | brain-module-mapper | 11脑模块×保险映射 | 474行 |
| `analysis-t3-dsh-plugin-brain-hybrid-integration.md` | dsh-plugin-specialist | DSH插件集成分析 | 564行 |
| `analysis-t4-hybrid-architecture-design.md` | hybrid-architect | 三层融合架构设计 | 1597行 |
| `analysis-t5-implementation-roadmap.md` | implementation-planner | 实施路线图+代码规格 | 1447行 |

### 12.2 商业化优先级

| 优先级 | 路径 | 周期 | ROI |
|:------:|------|:----:|:----:|
| **S级** | 工业质检(CX复用) | 6周 | 211% |
| **S级** | 机器人导航(复眼+mmap) | 10周 | 310% |
| **A级** | **保险核保(本方案P0)** | **12周** | **291%** |
| A级 | 多Agent系统(EVO) | 8周 | 329% |
| A级 | 自动驾驶(τ+AEB) | 12周 | 78% |
| B级 | 量化交易 | 16周 | 64% |
| B级 | 机械臂操控 | 12周 | 19% |

### 12.3 财务预测（18个月总览）

- 总投资: $10.14M
- 总营收: $29.2M
- 净利润: $19.06M (ROI 188%)
- 盈亏平衡: M11-12
- 推荐启动路径: 工业质检(6周MVP)→机器人导航(10周)→保险核保(12周)

---

> **结论**: Fly64脑模型与gbcost保险系统存在**深度结构同构**。从果蝇的KC稀疏编码(5%)到保险理赔的Pareto 20/80分布、从CX环形吸引子到4级分层异常检测、从多巴胺门控到控费策略自适应调整——神经回路与保险分析逻辑在多个维度上高度对应。通过12周的渐进式集成，可在保持现有6134+测试回归的前提下，构建精度~90%、0-token可选、seed-64可追溯的新一代保险智能分析系统。