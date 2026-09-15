# T1: gbcost-analysys 团体保险赔付分析系统深度解构

> 作者: insurance-domain-analyst
> 日期: 2026-09-07
> 目的: 为后续 Fly64 脑模型映射提供完整的系统架构基准

---

## 一、系统总体架构 (三层)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DSH Plugin Layer (Web UI)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ FloatingPanel │  │ 19 ghb_* tools │  │ Skills (5 plugins)    │  │
│  │ (4 Tab)       │  │ (host.js)    │  │ cost-control/query/    │  │
│  │               │  │              │  │ batch/doris/risk-map  │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│              LangGraph Agent Framework (orchestrator.py)        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  StateGraph — 38 nodes · fan-out/fan-in · 条件路由       │  │
│  │  AgentState(TypedDict, total=False, 143+ fields)          │  │
│  │  Sequential: reconciliation→stability→anomaly→ibnr       │  │
│  │  Conditional: route_after_macro(L1 anomaly→parallel/direct)│  │
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

---

## 二、36 Agent 系统深度分析

### 2.1 核心架构设计模式

每个 Agent 继承自 `BaseAgent`（`src/agents/base.py`），模板方法模式：

```
execute(state) → AgentState
  ├── validate_input()    ← 子类可选重写
  ├── execute()           ← 子类必须实现 (核心逻辑)
  ├── validate_output()   ← #25 OPT-2B: Schema验证
  │   └── _handle_validation_failure()
  │       ├── _reprompt_on_schema_failure() (1次结构化重提示)
  │       └── 失败→标记不可信+降级到规则
  └── execution_log记录
```

### 2.2 Agent 分类 (36 = 23 纯规则 + 13 LLM增强)

**23 纯规则 Agent** (直接调用 analysis/*.py 模块):
| Agent | 模块依赖 | 产出 |
|-------|---------|------|
| reconciliation | ReconciliationAnalyzer | 数据对账结果+rule_traces |
| stability | PreconditionChecker | StabilityReport |
| benchmark_matching | BenchmarkMatcher | benchmark_matches+metadata |
| ramp_analysis | RampTrendAnalyzer | ramp_analysis |
| member_profiler | MemberProfiler | member_profile |
| extended_metrics | MultiMetricAnalyzer | incidence_rates/claim_proportions/... |
| drg_analysis | DRGGrouper | drg_result/coverage_rate/over_budget_rate |
| deg_analysis | DEGGrouper | deg_result/statistics/distribution |
| edmp_analysis | EDMPTracker | edmp_result/chronic_disease_rate/... |
| ndc_analysis | NDCChecker | ndc_result/violations/overcharge_estimate |
| fee_structure_analysis | FeeStructureAnalyzer | fee_structure_analysis |
| cost_control_tracking | CostControlTracker | cost_control_tracking/impact_report |
| path_a_drilldown | PathADrilldownAnalyzer | path_a_drilldown+meta |
| medical_rationality | MedicalRationalityEngine | medical_rationality |
| hospital_fee_anomaly | HospitalFeeAnomalyDetector | hospital_fee_anomaly |
| trend_forecast | TrendForecaster | trend_forecast |
| multidimensional_metrics | MultiDimAggregator | multidimensional_metrics |
| fee_rootcause | FeeRootcauseAnalyzer | fee_rootcause_analysis |
| policy_unit | PolicyUnitAnalyzer | policy_unit_analysis/yoy/peer |
| drug_dosage | DrugDosageChecker | drug_dosage_issues |
| coverage_deviation | CoverageDeviationAnalyzer | coverage_deviation |
| benefit_transfer | BenefitTransferDetector | benefit_transfer_result |
| ml_prediction | MLPredictor | ml_prediction_result |

**13 LLM 增强 Agent** (LLM Primary或Hybrid模式启用):
| Agent | Prompt模板 | LLM产出 | E/D模式 |
|-------|-----------|---------|---------|
| health_score | PT-001 | llm_health_interpretation | 增强 |
| disease_treatment | PT-002 | llm_disease_analysis | 增强 |
| prior_condition | PT-003 | llm_adverse_selection | 增强 |
| case_investigation | PT-004/5 | llm_medical_assessment/fraud_detection | 增强 |
| report_generation | PT-006/16 | llm_report_summary/executive_summary | 增强 |
| cost_control | PT-007 | llm_recommendations | **Primary** |
| anomaly_detection | PT-008 | llm_anomaly_interpretation | **Primary** |
| claim_correlation | PT-009 | llm_correlation_assessment | 增强 |
| ibnr_prediction | PT-010 | llm_ibnr_assessment | **Primary** |
| hospital_cost | PT-011 | llm_hospital_analysis | 增强 |
| cross_dimension | PT-013 | llm_cross_dimension_assessment | **Primary** |
| pre_authorization | PT-014 | llm_preauth_enhancement | **Primary** |
| fwa_analysis | PT-015 | llm_fwa_assessment | **Primary** |

注: Primary(E/D)=LLM先行+规则验证, 共7个; 增强=规则先行+LLM补充。

### 2.3 AgentState 全局状态 (TypedDict, total=False, 143+字段)

关键设计: `total=False` 使所有字段可选，每个Agent只填充负责子集。

**字段分组**: 输入(1)→Step1-3(6)→Step4-6(8)→LLM增强(15+)→扩展指标(8)→Phase B(15+)→Phase C/D(20+)→告警/执行元数据(10+)→ML+注册表(5+)

**并行安全机制**: `_make_parallel_safe()` 包装器:
1. 快照执行前共享列表长度
2. 替换可变列表为独立副本
3. 执行`_safe_execute`
4. 提取增量(delta)返回
5. `ANNOTATED[LIST, add]` 的 reducer 自动拼接

### 2.4 LLM 调用架构 (三提供商路由)

```
Provider A: LiteLLM网关 deepseek-v4-flash (主, 联网搜索+深度思考)
Provider B: deepseek-v4-flash-huawei (次, 同网关)
Provider C: 腾讯云LKEAP deepseek-v3.2 (备用)
```

**三种运行模式:**
| 模式 | 语义 | Token量级 | 适用场景 |
|------|------|-----------|---------|
| hybrid(默认) | 规则先行, LLM按需增强 | ~50K | 日常分析 |
| llm_primary | LLM先行+规则验证+精化重试 | ~144-172K | 深度校正 |
| rule_only | 纯规则, 0 tokens | 0 | 快速扫描 |

**精化重试**: 仅 `llm_primary` 模式启用, `max_rounds=2` 封顶, 小保单跳过。

---

## 三、LangGraph StateGraph 工作流架构

### 3.1 图结构 (38 节点)

```
Entry → reconciliation → stability → anomaly_detection → ibnr_prediction
                                                              │
                                                    conditional route
                                                    (always→parallel)
                                                         │
                                                    start_parallel (no-op)
                                                    ┌──────┼──────────┐
                                                    │      │          │
                                               [Group A: 5 Agents]
                                          benchmark_matching  claim_correlation
                                          prior_condition     disease_treatment
                                          hospital_cost
                                                    │
                                                    │
                                               cost_control (fan-in)
                                                    │
                                          ┌─────────┼─────────────────┐
                                          │         │                  │
                                     [Group B: 24 Agents]
                              case_inv  health_score  ramp  member_profiler
                              cross_dim  extended_met  pre_auth  fwa  drg
                              deg  edmp  ndc  fee_struct  cc_tracking
                              path_a  med_rationality  hfa  trend  multi_dim
                              fee_root  drug_dosage  coverage_dev  benefit_transfer
                              ml_prediction
                                          │
                                          │
                                     pre_report (二级汇聚, 解决深度不一致)
                                          │
                                     policy_unit (依赖 fwa_result)
                                          │
                                     report_generation → END
```

### 3.2 关键工作流设计细节

1. **二级汇聚 pre_report (2026-08-18 修复)**: 解决 langgraph 1.2.2 fan-in 深度不一致导致 report_generation 被调度两次的问题。
2. **条件路由 `route_after_macro()`**: 检查 L1 异常决定是否跳过深度分析(需 config.yaml 启用)。
3. **并行安全 delta 模式**: `_make_parallel_safe()` 包装确保并行执行不冲突。
4. **`_AGENT_OUTPUTS` 映射表**: 从 agent_name → {state keys} 的精确声明, 构成数据流契约。
5. **共享 add-reducer 键保护**: `_SHARED_ADD_KEYS = {"alerts", "llm_reasoning_chain", "llm_call_trace"}` 防止并行时重复拼接。

### 3.3 配置注入

`create_analysis_workflow_with_config()` 执行:
1. config.yaml `analysis.*` 阈值注入各 Agent
2. `health_score` 顶层配置合并
3. 清除 Agent 缓存后重建实例

---

## 四、DSH 插件集成分析

### 4.1 分层插件架构

```
DSH Web UI (http://127.0.0.1:3080)
  │
  ├── Host 半区 (skills/ghb-cost-control/plugin/ghb-host.js → lib/index.js)
  │   ├── 19 个 ghb_* 工具注册
  │   ├── Python 解释器自动发现 (3.12/3.11/虚拟环境)
  │   ├── 子进程管理 (ghb_runner 守护队列)
  │   └── 工具分类: 分析/注册表/保单/Doris下载/门禁/运维
  │
  └── Client 半区 (skills/ghb-cost-control/plugin/ghb-client.js → lib/client.js)
      ├── FloatingPanel (4 Tab: 📊📄🗺️🧰)
      ├── 右下角聚合 badge (毛玻璃效果)
      ├── 对话列礼让/互斥机制
      └── 5 个 slot 嵌入点
```

### 4.2 19 个工具注册

```javascript
// 分析类
ghb_analyze, ghb_analyze_status, ghb_query, ghb_status, ghb_logs, ghb_reports
ghb_registry                            // 注册表
ghb_query_prediction                    // ML预测查询

// 保单管理
ghb_policy_mgmt                         // list/history/qa

// Doris 数据管理
ghb_doris_scan, ghb_doris_extract, ghb_doris_status
ghb_doris_compare, ghb_doris_download, ghb_doris_download_status
ghb_doris_wide_download                 // 宽表全量更新
ghb_doris_backup, ghb_doris_backup_list // COS加密备份

// LLM门禁
ghb_llm_gate                            // status/approve/clear
```

### 4.3 业务逻辑定位策略

Python 环境自动发现链 (Windows): `.venv313 > .venv > .venv312off > Program Files Python312 > PATH`
双解释器: PY_BIN (分析/渲染) + DORIS_PY (Doris工具链)

项目根定位: `workspaceRegistry.resolveByPath()` → `D:/codes/gbcost-analysys`

### 4.4 数据降级体系

每个 ghb_* 工具实现 `_safe_execute()` 三阶段: 时效性(实时→15min→6h→24h→从不), 范围(全部→分类→单个), 状态(available/fallback/failed)。

---

## 五、数据流与数据处理管线

### 5.1 ETL管线

```
OCR双引擎 → 描述字段解析 → 福利计划 → CSV加载器 → Doris连接器
  │                                                      │
  └── OCR引擎 (LlamaParse+PyMuPDF4LLM)                  │
       └── claim_image_query (v2.0.70)                  │
                                                        │
Doris数仓 → ghb_doris_download → per-policy CSV →     │
  (增量分批断点续传)    (wide_{gc}.csv)                │
                                                        │
  ←── ghb_doris_wide_download ───                     │
  (c001宽表, 块级断点续传)                               │
                                                        │
  └──→ ghb_doris_extract → data/doris/policies/       │
       (per-policy CSV)                                 │
                                                        │
  └──→ ghb_doris_compare → 远程-本地差异清单            │
```

### 5.2 数据容器 PolicyAnalysisData

`src/models/policy_data.py` 包含 6 个 dataclass:
- `PolicyAnalysisData` (统一容器) — 格式化接口:
  - `to_stability_check_format()` → PreconditionChecker
  - `to_hierarchical_detector_format()` → HierarchicalAnomalyDetector
  - `to_ibnr_format()` → IBNRPredictor
  - `to_benchmark_format()` → BenchmarkMatcher
  - `to_cost_control_format(anomalies)` → CostControlGenerator
  - `to_prior_condition_format()` → PriorConditionAnalyzer

### 5.3 ML 预测子系统 (独立)

- 框架: LightGBM Tweedie + 分位数模型
- 数据: 5.84GB/71列/41特征/11分类
- 评估: Gini/MAPE/总量误差
- Walk-Forward时序回测
- 三入口: train/predict/evaluate

---

## 六、知识库与规则引擎

### 6.1 20 个 YAML 知识库文件

| 类别 | 内容 |
|------|------|
| 医院标杆 | cost_standards.yaml, hospital_benchmarks.yaml |
| 疾病治疗 | disease_treatment_rules.yaml, icd10_mapping.yaml |
| DRG/DIP | drg_rules.yaml, drg_procedure_map.yaml |
| DEG | deg_rules.yaml |
| FWA 61条 | 22欺诈+18浪费+21滥用 |
| IBNR | ibnr_parameters.yaml |
| 药品剂量 | drug_dosage_rules.yaml (50+药品) |
| 医疗合理性 | medical_rationality_rules.yaml |
| Cigna临床指南 | clinical_guidelines/ (10组疾病) |
| 职业疾病 | occupational_disease_rules.yaml |
| 利益输送 | benefit_transfer_rules.yaml |

### 6.2 FWA 61 条规则分类

- 欺诈 (22): 拆单/挂床/以诊代检/冒用/身份怀疑/事故伪造
- 浪费 (18): 过度检查/重复开药/非必要住院
- 滥用 (21): 高频就诊/跨院开药/诊断升级

---

## 七、系统版本与关键里程碑

| 版本 | 关键特性 |
|------|---------|
| v1.9.71 | ComPilot优化前基线 |
| v2.0.0-dev~v2.0.70 | 三模式LLM / 精化重试 / 注册表 / 规则trace / 指标回检 / 理赔影像查询 |
| v2.0.26 | 默认 hybrid 模式 |
| v2.0.53 | 风险地图 8 Tab 45 chips / 指标回检3项漂移修复 |
| v2.0.69 | ML predict静默回退修复 / LLM token统计加锁 / provider_key配置化 |
| v2.0.70 | 理赔影像查询 P0 (ClaimQueryService + images Tab) |

---

## 八、Deloitte 14步分析框架对应

| 德勤14步 | 对应Agent(s) | LangGraph位置 |
|----------|-------------|--------------|
| Step 1: 数据对账 | reconciliation | 顺序节点1 |
| Step 2: 稳定性检查 | stability | 顺序节点2 |
| Step 3: 异常检测 | anomaly_detection | 顺序节点3 |
| Step 4: IBNR预测 | ibnr_prediction | 顺序节点4 |
| Step 5: 标杆匹配 | benchmark_matching | 并行组A |
| Step 6: 关联分析 | claim_correlation | 并行组A |
| Step 7: 控费建议 | cost_control | 汇聚节点 |
| Step 8: 既往症 | prior_condition | 并行组A |
| Step 9: 疾病-治疗 | disease_treatment | 并行组A |
| Step 10: 医院分析 | hospital_cost | 并行组A |
| Phase B: 规则扩展 | fwa/drg/deg/edmp/ndc | 并行组B |
| Phase C: 功能完善 | fee_structure/tracking | 并行组B |
| Phase D: LLM增强 | health_score/case_inv/etc | 并行组B |
| Phase E: 报告生成 | report_generation | 最终节点 |

---

## 九、关键设计决策摘要

1. **total=False TypedDict**: 所有字段可选, .get() 安全访问, 支撑灵活局部更新
2. **fan-out/fan-in 二级汇聚**: 解决 langgraph 1.2.2 深度不一致导致的重复执行
3. **增量 delta 模式**: 并行安全的 state 更新机制, 避免 LangGraph channel 冲突
4. **三模式 LLM 决策链**: 显式 > recommended_mode > config.yaml hybrid
5. **规则 trace 体系**: 每个关键 Agent 独立输出 `{name}_rule_traces`, 可审计可归因
6. **显式降级元信息**: `{name}_meta = {data_available, reason}` 沿每个关键路径声明
7. **DSH 静态化部署**: 从动态 `harness.registerTool` 迁移为 npm 包, 重启持久化
8. **Python 双解释器**: 分析(PY_BIN) + Doris工具链(DORIS_PY) 独立验证依赖