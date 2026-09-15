# T5: 核保与理赔分析专项实施方案 + 实施路线图

> **作者**: implementation-planner  
> **日期**: 2026-09-07  
> **依赖**: T1 (gbcost-analysys深度解构) + T2 (Fly64脑模块→保险能力映射) + T3 (DSH插件集成分析) + T4 (混合架构设计)  
> **参考**: gbcost-analysys 36 Agent / 6134+现有测试 / fly64-brain模块

---

## 目录

1. [核保引擎专项方案](#1-核保引擎专项方案)
   - 1.1 CX 16柱环形吸引子 → 16风险因子并行推理
   - 1.2 Reflex 4反射电路 → 自动核保规则引擎
   - 1.3 MushroomBody(KC-MBON) → 核保决策学习优化
   - 1.4 代码改造规格
   - 1.5 参数初始化方案
   - 1.6 DSH工具注册规约

2. [理赔分析专项方案](#2-理赔分析专项方案)
   - 2.1 6态异常检测 → 4级分层下钻
   - 2.2 空间记忆网格 → 理赔地理/医院聚类
   - 2.3 因果链 → 案件调查归因
   - 2.4 自进化 → 控费策略闭环
   - 2.5 数据流详细设计
   - 2.6 阈值配置与验证方法

3. [实施路线图: 6步12周计划](#3-实施路线图-6步12周计划)
   - W1-2: 数据适配层
   - W3-4: 脑模型保险推理
   - W5-6: DSH插件桥接
   - W7-8: 混合仲裁
   - W9-10: 验证测试
   - W11-12: 部署上线

4. [质量门禁](#4-质量门禁)
   - 每阶段3项量化门禁

5. [实验验证方案](#5-实验验证方案)
   - 5.1 gbcost测试套件回归
   - 5.2 A/B测试框架

---

## 1. 核保引擎专项方案

### 1.1 CX 16柱环形吸引子 → 16风险因子概率分布并行推理

#### 核心设计

CentralComplex 的 16 列环形吸引子罗盘是 Fly64 的"导航内核"——在保险领域映射为**16风险因子概率分布并行推理引擎**。

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

#### CX 核保推理公式适配

```python
# fly64/underwriting/cx_risk_compass.py — 16柱核保风险罗盘

class UnderwritingRiskCompass:
    """基于CX 16列环形吸引子的核保风险并行推理"""

    # 16风险因子映射列
    RISK_COLUMNS = {
        0:  'loss_ratio_deviation',      # 赔付率偏离
        1:  'loss_ratio_trend',          # 赔付率趋势
        2:  'liability_loss_ratio',      # 分责任赔付率
        3:  'seasonal_volatility',       # 季节性波动
        4:  'data_integrity',            # 数据完整性
        5:  'claim_frequency_anomaly',   # 出险频次异常
        6:  'avg_cost_anomaly',          # 次均赔款异常
        7:  'diagnosis_coding_quality',  # 诊断编码质量
        8:  'outpatient_cost_anomaly',   # 门诊费用异常
        9:  'inpatient_cost_anomaly',    # 住院费用异常
        10: 'drug_cost_deviation',       # 药品费用偏离
        11: 'provider_concentration',    # 供应商集中度
        12: 'fraud_risk_index',          # 欺诈风险指数
        13: 'abuse_waste_risk',          # 滥用/浪费风险
        14: 'moral_hazard_signal',       # 道德风险信号
        15: 'new_business_risk',         # 新业务风险
    }

    def __init__(self):
        # 16列环形吸引子状态
        self.heading = 0        # 当前bump位置 [0, 15]
        self.column_activity = np.zeros(16)  # 16列活化度
        self.persistence = 0.85  # 阻尼系数(防止抖动)
        self.goal_strength = 0.0  # 总体目标强度

    def infer_risk_profile(self, policy_data: PolicyAnalysisData) -> Dict:
        """并行推理16维风险因子概率分布"""

        # Step 1: 计算每个风险因子列的值 (并行 ← 独立计算)
        risk_scores = {}
        for col, risk_name in self.RISK_COLUMNS.items():
            risk_scores[risk_name] = self._compute_risk_factor(
                risk_name, policy_data
            )

        # Step 2: 环形吸引子更新
        # 新输入驱动bump位置 → 主导风险因子决定当前"航向"
        bump_input = np.array([risk_scores[r] for r in self.RISK_COLUMNS.values()])
        self.column_activity = (1 - self.persistence) * bump_input \
                               + self.persistence * self._diffuse(self.column_activity)

        # Step 3: bump检测 → 当前主导风险+概率分布
        self.heading = np.argmax(self.column_activity)
        self.goal_strength = self.column_activity[self.heading]

        # Step 4: 各因子概率分布 (归一化到 [0, 1] 概率)
        risk_distribution = softmax(self.column_activity)

        return {
            'compass_position': int(self.heading),
            'dominant_risk': self.RISK_COLUMNS[self.heading],
            'goal_strength': float(self.goal_strength),
            'risk_scores': risk_scores,                    # 16维原始评分
            'risk_distribution': risk_distribution.tolist(), # 16维概率分布
            'risk_profile_vector': self.column_activity.tolist(),
            'anomaly_threshold': float(np.mean(self.column_activity)
                                       + 2 * np.std(self.column_activity)),
        }

    def _compute_risk_factor(self, name: str, data: PolicyAnalysisData) -> float:
        """计算单个风险因子值 — 可被Reflex电路加速"""
        # 每种因子有独立的计算逻辑
        # 映射到gbcost现有方法:
        #   赔付率偏离 → loss_ratio - benchmark
        #   数据完整 → hdf1/hdf2/hdf3/hdf4 检查
        #   欺诈风险 → FWA 61规则命中率
        #   ...
        pass

    def _diffuse(self, activity: np.ndarray) -> np.ndarray:
        """环形邻居扩散 (CX固有机制)"""
        result = np.zeros_like(activity)
        for i in range(16):
            left = activity[(i-1) % 16] * 0.1   # 10%向左扩散
            right = activity[(i+1) % 16] * 0.1  # 10%向右扩散
            center = activity[i] * 0.8           # 80%自保持
            result[i] = center + left + right
        return result
```

#### 与gbcost现有系统的集成方式

| CX 16列 | 替代的gbcost模块 | 代码变更 |
|---------|-----------------|---------|
| 列0-3 (赔付率因子) | `hierarchical_anomaly_detector.py` L1异常 | 替换为 `underwriting_cx.compass.column_activity[0:4]` |
| 列4-7 (质量因子) | `precondition_checker.py` + `reconciliation` | 读 `stability_report` + `reconciliation` 状态 |
| 列8-11 (费用因子) | `hospital_fee_anomaly.py` + `drg_analysis` | 读现有模块输出 |
| 列12-15 (风险因子) | `fwa_engine.py` + `health_score` | 读 `fwa_result` + 现有指标 |

### 1.2 Reflex 4反射电路 → 自动核保规则引擎

#### 核心设计

Fly64 的 Reflex 电路在果蝇中负责快速逃逸/转向反射——在保险中映射为**无需LLM、无需脑模型全量推理的快速核保规则引擎**。4条反射电路分别对应4类核保决策的"极速路径"。

```
┌─────────────────────────────────────────────────────────────────────┐
│            Reflex 4-Circuit Underwriting Gate                       │
│                                                                     │
│  触发条件                                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  输入信号: risk_scores 16维 + historical_known_patterns      │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │                                        │
│          ┌────────────────┼────────────────┐                       │
│          ▼                ▼                ▼                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│  │ Reflex R1:   │ │ Reflex R2:   │ │ Reflex R3:   │                │
│  │ 数据拒绝     │ │ 快速通过     │ │ 自动升级     │                │
│  │ (StuckDetect)│ │ (ClearPass)  │ │ (AutoEscalate│                │
│  │ 数据质量不   │ │ 高风险因子   │ │ 高风险因子   │                │
│  │ 达标→拒绝   │ │ 全部≤阈值→  │ │ 部分>阈值→   │                │
│  │ 核保        │ │ 自动通过核保  │ │ 升级L3 LLM   │                │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘                │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Reflex R4: 条件通过 (ConditionalPass)                         │  │
│  │ 中等风险组合 → 自动生成附加条件(加费/免责/限额)                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  延迟: < 50ms (纯矩阵运算, 无LLM, 无脑模型全量推理)                  │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4反射电路规格

```python
# fly64/underwriting/reflex_gates.py — 4反射核保门

class ReflexUnderwritingGate:
    """基于Fly64 Reflex电路的4路快速核保决策门"""

    # ── 4条反射电路配置 ──
    REFLEX_THRESHOLDS = {
        'R1_reject': {
            'stuck_temporal_energy': 0.95,    # 数据卡住能量阈值
            'frame_still_frames': 12,          # 连续静止帧数
            'rate_low_ratio': 0.3,             # 赔付率异常低阈值
            'y_anomaly_score': 0.8,            # Y轴(退保/续保)异常
            'min_data_columns': 12,            # 最少数据列数
        },
        'R2_clear_pass': {
            'max_risk_score': 0.3,             # 所有风险因子≤0.3
            'min_familiarity': 0.7,            # 历史模式熟悉度≥0.7
            'data_completeness': 0.9,          # 数据完整度≥0.9
            'max_anomaly_count': 0,            # 异常计数=0
        },
        'R3_escalate': {
            'min_risk_score': 0.7,             # 任一风险因子≥0.7
            'fraud_signal': 0.5,               # 欺诈信号≥0.5
            'moral_hazard': 0.6,               # 道德风险≥0.6
            'novelty_direction': 0.8,          # CX novelty 方向
        },
        'R4_conditional': {
            'conditional_range': (0.3, 0.7),   # 中等风险区间
            'max_high_risk_count': 2,           # 最多2个高风险因子
            'suggested_actions': [              # 建议附加条件
                'rate_increase',               # 加费
                'exclusion_clause',            # 免责条款
                'deductible_adjust',           # 免赔额调整
                'coverage_limit',              # 限额
                'waiting_period',              # 等待期
                'medical_review',              # 医疗审查
            ]
        }
    }

    def evaluate(self, risk_profile: Dict) -> Dict:
        """4反射电路并行评估"""
        scores = risk_profile.get('risk_scores', {})
        familiarity = risk_profile.get('familiarity', 0.5)
        data_quality = risk_profile.get('data_quality', {})

        # R1: 数据拒绝 (门控)
        if self._check_r1_reject(data_quality):
            return {
                'gate': 'R1_REJECT',
                'decision': 'reject',
                'reason': 'Data quality insufficient for underwriting',
                'confidence': 0.95,
                'actions': ['request_data_correction', 'manual_review'],
                'reflex_used': True
            }

        # R2: 快速通过 (无风险)
        if self._check_r2_clear_pass(scores, familiarity):
            return {
                'gate': 'R2_CLEAR_PASS',
                'decision': 'accept',
                'reason': 'All risk factors within normal range',
                'confidence': 0.90,
                'actions': ['standard_underwriting'],
                'reflex_used': True
            }

        # R3: 自动升级 (高风险)
        if self._check_r3_escalate(scores):
            return {
                'gate': 'R3_ESCALATE',
                'decision': 'escalate',
                'reason': 'High risk factors detected, need LLM analysis',
                'confidence': 0.85,
                'actions': ['trigger_llm_primary', 'human_review_required'],
                'reflex_used': True
            }

        # R4: 条件通过 (中等风险)
        conditions = self._generate_conditions(scores)
        return {
            'gate': 'R4_CONDITIONAL',
            'decision': 'conditional_accept',
            'reason': f'Moderate risk, {len(conditions)} conditions applied',
            'confidence': 0.75,
            'actions': conditions,
            'reflex_used': True
        }
```

### 1.3 MushroomBody(KC-MBON) → 核保决策学习优化

#### 核心设计

蘑菇体通过 KC 稀疏编码进行模式识别——在核保中映射为**历史核保决策的学习与优化引擎**。

```
┌─────────────────────────────────────────────────────────────────────┐
│      MushroomBody Underwriting Learning Engine                      │
│                                                                     │
│  输入 → 128维 scene_sig (保单特征指纹)                               │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ KC Sparse Encoding (2000 KC, 5% active = ~100)              │   │
│  │                                                              │   │
│  │  KC_activity = σ(W_kc @ scene_sig)                           │   │
│  │                                                              │   │
│  │  • 每个 KC 映射一种核保模式组合:                               │   │
│  │    KC_42 = (赔付率高×门诊集中×年龄偏大)                        │   │
│  │    KC_137 = (数据完整×历史良好×新建)                           │   │
│  │    KC_888 = (欺诈风险×滥用信号×频率异常)                       │   │
│  │                                                              │   │
│  │  • 稀疏度本身 = 异常度:                                       │   │
│  │    正常保单: ~5% KC活跃 (anomaly_score ≈ 0.05)                │   │
│  │    异常保单: ~15% KC活跃 (anomaly_score ≈ 0.15)               │   │
│  └─────────────────────────┬───────────────────────────────────┘   │
│                            │                                         │
│                            ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ MBON 5 Output Channels (核保决策5维输出)                     │   │
│  │                                                              │   │
│  │  forward_bias [0,1]  → 接受核保  (准入倾向)                   │   │
│  │  left_bias    [0,1]  → 条件核保  (附加条件倾向)               │   │
│  │  right_bias   [0,1]  → 拒绝核保  (拒绝倾向)                   │   │
│  │  jump_bias    [0,1]  → 升级核保  (人工审核倾向)               │   │
│  │  explore_bias [0,1]  → 探索核保  (新业务/非常规倾向)           │   │
│  │                                                              │   │
│  │ 最终决策 = softmax([forward, left, right, jump, explore])     │   │
│  │ 置信度 = max(softmax_output)                                  │   │
│  └─────────────────────────┬───────────────────────────────────┘   │
│                            │                                         │
│                            ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 多巴胺门控学习 (ΔW = η · R · KC · MBON · E)                │   │
│  │                                                              │   │
│  │  1. 核保结果核实 → 多巴胺信号 R ∈ [-1, +1]                   │   │
│  │     • 核保准确 +1 (实际赔付与预估一致)                         │   │
│  │     • 核保偏差 -0.5 (赔付超预期)                              │   │
│  │     • 核保失误 -1 (严重漏保/过保)                             │   │
│  │                                                              │   │
│  │  2. 资格迹 E(t) = decay*E(t-1) + KC*MBON                     │   │
│  │     • 核保特征与决策的时序关联                                │   │
│  │     • 系数decay=0.9, 影响约10次核保周期                       │   │
│  │                                                              │   │
│  │  3. 权重更新: ΔW_kc = η · R · KC · MBON · E                 │   │
│  │     • 学习率 η = 0.01 (缓慢适应)                              │   │
│  │     • 巩固: |ΔW| > 0.5 → 写入 consolidated 固化记忆           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

#### 核保决策学习流程

```python
# fly64/underwriting/mb_underwriting_learner.py

class MBUnderwritingLearner:
    """基于蘑菇体三因子学习的核保决策优化器"""

    def __init__(self):
        self.kc_weights = np.random.randn(2000, 128) * 0.1
        self.mbon_weights = np.random.randn(5, 2000) * 0.1
        self.consolidated = []  # 固化记忆库
        self.eligibility = np.zeros(2000)  # 资格迹
        self.learning_rate = 0.01
        self.eligibility_decay = 0.9

    def encode_policy(self, policy_data: PolicyAnalysisData) -> np.ndarray:
        """将保单编码为128维场景签名"""
        features = np.concatenate([
            policy_data.loss_ratio_history,       # 24月赔付率
            policy_data.liability_distribution,    # 责任分布
            policy_data.disease_profile,           # 疾病分布
            policy_data.age_gender_profile,        # 人口统计
            policy_data.provider_concentration,    # 供应商集中
        ])
        return self._random_projection(features, 128)

    def infer_decision(self, scene_sig: np.ndarray) -> Dict:
        """核保决策推理"""

        # KC编码: 2000 KC → ~100活跃 (5%稀疏)
        kc_activation = self.kc_weights @ scene_sig
        kc_activation = np.maximum(0, kc_activation)  # ReLU
        kc_sparse = np.zeros_like(kc_activation)
        top_k = int(2000 * 0.05)  # top 5%
        top_indices = np.argpartition(kc_activation, -top_k)[-top_k:]
        kc_sparse[top_indices] = kc_activation[top_indices]

        # MBON 5通道输出
        mbon_output = self.mbon_weights @ kc_sparse
        decision_probs = softmax(mbon_output)

        # 资格迹更新
        self.eligibility = self.eligibility_decay * self.eligibility \
                           + kc_sparse * np.max(mbon_output)

        return {
            'scene_sig': scene_sig.tolist(),
            'kc_sparsity': float(np.count_nonzero(kc_sparse) / 2000),
            'mbon_probs': {
                'accept': float(decision_probs[0]),      # forward
                'conditional': float(decision_probs[1]), # left
                'reject': float(decision_probs[2]),      # right
                'escalate': float(decision_probs[3]),    # jump
                'explore': float(decision_probs[4]),     # explore
            },
            'confidence': float(np.max(decision_probs)),
            'dominant_decision': ['accept', 'conditional',
                                  'reject', 'escalate', 'explore'][
                int(np.argmax(decision_probs))
            ],
        }

    def learn_feedback(self, feedback: float, actual_outcome: float):
        """多巴胺门控学习 — 核保结果反馈→权重自适应"""
        dopamine = self._compute_dopamine(feedback, actual_outcome)
        # ΔW = η · R · KC · MBON · E
        delta_w = self.learning_rate * dopamine \
                  * self.kc_weights * self.mbon_weights.T @ self.eligibility
        self.kc_weights += delta_w
        # 权重限幅 [-3, 3] 防止发散
        np.clip(self.kc_weights, -3, 3, out=self.kc_weights)
        # 巩固: 大变化固化
        if np.abs(delta_w).max() > 0.5:
            self.consolidated.append({
                'weights_snapshot': self.kc_weights.copy(),
                'dopamine': dopamine,
                'timestamp': datetime.now().isoformat(),
            })
```

### 1.4 代码改造规格

#### 改造文件清单

| 文件 | 改造类型 | 改造内容 | 代码量(预估) |
|------|---------|---------|------------|
| `fly64/underwriting/cx_risk_compass.py` | **新建** | 16柱风险罗盘引擎 | ~300行 |
| `fly64/underwriting/reflex_gates.py` | **新建** | 4反射核保门 | ~200行 |
| `fly64/underwriting/mb_underwriting_learner.py` | **新建** | MB核保学习器 | ~250行 |
| `fly64/underwriting/__init__.py` | **新建** | 模块导出 | ~50行 |
| `src/agents/underwriting_agent.py` | **改造** | 接入脑模型核保 | ~150行 |
| `src/workflow.py` | **改造** | 增加核保路由节点 | ~80行 |
| `src/models/policy_data.py` | **扩展** | 增加核保相关字段 | ~50行 |
| `config/analysis.yaml` | **扩展** | 核保阈值参数 | ~30行 |
| `tests/unit/test_underwriting_brain.py` | **新建** | 核保脑模型测试 | ~200行 |
| **总计** | | | **~1310行** |

#### gbcost 现有 Agent 改造点

```python
# src/agents/underwriting_agent.py — 现有核保Agent改造

class UnderwritingAgent(BaseAgent):
    """核保Agent — 混合模式下集成脑模型推理"""

    # 新增: 脑模型集成模式
    USE_BRAIN_UNDERWRITING = True  # config.analysis.brain_underwriting

    def execute(self, state: AgentState) -> Dict:
        if self.USE_BRAIN_UNDERWRITING:
            return self._hybrid_execute(state)
        return self._rule_execute(state)

    def _hybrid_execute(self, state: AgentState) -> Dict:
        """混合核保执行"""

        # Phase 1: 16柱风险罗盘 (CX)
        policy_data = self._extract_policy_data(state)
        compass = UnderwritingRiskCompass()
        risk_profile = compass.infer_risk_profile(policy_data)

        # Phase 2: 4反射电路 (Reflex) — 快速门控
        reflex_gate = ReflexUnderwritingGate()
        gate_result = reflex_gate.evaluate(risk_profile)

        # Phase 3: 蘑菇体学习 (MB) — 决策优化
        mb_learner = MBUnderwritingLearner()
        scene_sig = mb_learner.encode_policy(policy_data)
        mb_decision = mb_learner.infer_decision(scene_sig)

        # Phase 4: 仲裁融合 (CX + Reflex + MB)
        final_decision = self._arbitrate_uw(
            gate_result, mb_decision, risk_profile
        )

        return self._format_output(final_decision, risk_profile)
```

### 1.5 参数初始化方案

#### CX 16列初始权重

```yaml
# config/analysis.yaml 新增核保参数段

underwriting:
  brain_enabled: true
  
  # CX 16柱环形吸引子参数
  cx_compass:
    persistence: 0.85           # 阻尼系数 [0.7, 0.95]
    diffusion_rate: 0.1         # 邻居扩散率 [0.05, 0.2]
    goal_integration: 0.5       # 目标积分速度
    idle_wander: 0.02           # 空闲漫游漂移
    
  # 16风险因子初始阈值 (行业基准值)
  risk_factors:
    loss_ratio_deviation:    
      threshold: 0.30            # 赔付率偏离>30%告警
      weight: 1.0                # 初始权重
      learning_rate: 0.01        # 自适应学习率
    claim_frequency_anomaly:
      threshold: 0.15            # 出险频次偏离>15%告警
      weight: 0.8
    fraud_risk_index:
      threshold: 0.50            # 欺诈风险>0.5告警
      weight: 1.2
    # ... 全16因子配置

  # Reflex 4电路阈值
  reflex_gates:
    r1_reject:
      enabled: true
      data_integrity_min: 0.7   # 数据完整度<0.7 → 拒绝
    r2_clear_pass:
      enabled: true
      max_all_risk: 0.3         # 全因子<0.3 → 通过
    r3_escalate:
      enabled: true
      any_risk_gt: 0.7          # 任一因子>0.7 → 升级
    r4_conditional:
      enabled: true
      risk_range: [0.3, 0.7]    # 中等风险区间

  # MB学习参数
  mb_learning:
    kc_count: 2000
    kc_sparsity: 0.05            # 5%稀疏
    mbon_channels: 5
    learning_rate: 0.01
    eligibility_decay: 0.9
    consolidation_threshold: 0.5  # 固化阈值
    weight_clip: 3.0              # 权重限幅
```

### 1.6 DSH工具注册规约

```javascript
// plugin/ghb-host.js — 核保专项工具注册

// 1. brain_underwrite — 调用脑模型核保推理
ctx.tools['brain_underwrite'] = {
  name: 'brain_underwrite',
  description: '调用Fly64脑模型核保引擎(CX16柱+Reflex4路+MB学习)进行智能核保',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string', description: '投保保单号' },
      mode: { 
        type: 'string', 
        enum: ['full', 'reflex_only', 'cx_only'], 
        default: 'full' 
      },
      feedback: {
        type: 'number',
        description: '可选: 历史核保反馈信号 [-1, +1] 用于MB学习'
      }
    },
    required: ['policy_id']
  },
  handler: async (args, ctx) => {
    // 1. 通过 bridge2rpc 调用脑模型核保推理
    // 2. 返回 { gate_decision, risk_scores[16], mbon_probs, 
    //          confidence, seed64 }
    return await bridge2rpc.underwrite(args.policy_id, args.mode)
  }
}

// 2. brain_risk_profile — 查询保单16维风险因子分布
ctx.tools['brain_risk_profile'] = {
  name: 'brain_risk_profile',
  description: '查询保单在CX 16柱环形吸引子上的风险因子概率分布',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string' }
    },
    required: ['policy_id']
  },
  handler: async (args, ctx) => {
    return await bridge2rpc.getRiskProfile(args.policy_id)
  }
}

// 3. brain_feedback — 提交核保反馈(触发MB学习)
ctx.tools['brain_feedback'] = {
  name: 'brain_feedback',
  description: '提交核保结果反馈, 触发蘑菇体多巴胺学习(ΔW=η·R·KC·MBON·E)',
  parameters: {
    type: 'object',
    properties: {
      policy_id: { type: 'string' },
      feedback: { type: 'number', description: '反馈信号 -1~+1' },
      actual_loss_ratio: { type: 'number' }
    },
    required: ['policy_id', 'feedback']
  },
  handler: async (args, ctx) => {
    return await bridge2rpc.train(args.policy_id, args.feedback)
  }
}

// 4. brain_visualize_risk — 核保风险可视化(前端罗盘渲染)
ctx.tools['brain_visualize_risk'] = {
  name: 'brain_visualize_risk',
  description: '获取16柱风险罗盘可视化数据',
  handler: async (_, ctx) => {
    return await bridge2rpc.getRiskVisualization()
  }
}
```

---

## 2. 理赔分析专项方案

### 2.1 6态异常检测 → 4级分层下钻

Fly64 的 anomaly_state 有 6 种异常状态——在保险理赔中映射为**6种理赔异常模式**的实时检测。CentralComplex 的 16 列环形吸引子提供**4级分层下钻**机制。

```
┌─────────────────────────────────────────────────────────────────────┐
│              6-State Anomaly Detection Pipeline                     │
│                                                                     │
│  6种异常状态 (Fly64 anomaly_state)                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  异常状态        理赔映射          检测方式                    │   │
│  │  ─────────       ─────────         ─────────                  │   │
│  │  S0: none        无异常            SceneMemory熟悉度>0.7      │   │
│  │  S1: stuck       数据卡住          stuck_detector 多信号聚合   │   │
│  │  S2: cliff       大额赔付悬崖      cliff_detector 3σ阈值       │   │
│  │  S3: anomaly     模式偏离          KC稀疏度>0.15              │   │
│  │  S4: escape      逃逸模式          控费效果逃逸               │   │
│  │  S5: novelty     新模式            CX novelty_direction       │   │
│  │                                                              │   │
│  └─────────────────────────┬───────────────────────────────────┘   │
│                            │                                         │
│  异常状态触发→进入CX 4级下钻                                          │
│                            │                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  4级分层下钻 (CX 16列 → 4组×4列)                               │   │
│  │                                                              │   │
│  │  L1: 整体趋势 (CX列0-3)                                       │   │
│  │    下钻方向: 赔付率总体异常 → 哪个月/哪个责任类型?              │   │
│  │    检测: CX compass 位置在列0-3区间内                          │   │
│  │                                                              │   │
│  │  L2: 责任类型 (CX列4-7)                                       │   │
│  │    下钻方向: 门诊/住院/牙科/生育 → 哪个类型驱动异常?            │   │
│  │    检测: 单责任类型赔付率偏离 > 2σ                             │   │
│  │                                                              │   │
│  │  L3: 疾病维度 (CX列8-11)                                      │   │
│  │    下钻方向: 哪个ICD大类/具体疾病驱动?                          │   │
│  │    检测: 疾病费用占比偏离 > 历史均值+1.5σ                       │   │
│  │                                                              │   │
│  │  L4: 关键指标 (CX列12-15)                                     │   │
│  │    下钻方向: 人次/次均/药品/检查 → 哪个指标最异常?              │   │
│  │    检测: 关键指标Z-score > 2                                  │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

#### 6态检测实现规格

```python
# fly64/claims/anomaly_pipeline.py

class ClaimsAnomalyPipeline:
    """6态异常检测 + 4级分层下钻"""

    ANOMALY_STATES = {
        'none': 0, 'stuck': 1, 'cliff': 2,
        'anomaly': 3, 'escape': 4, 'novelty': 5
    }

    def detect(self, policy_data: PolicyAnalysisData) -> Dict:
        """6态异常检测"""

        # S0: none — 借助SceneMemory熟悉度
        familiarity = self._compute_familiarity(policy_data)
        if familiarity > 0.7:
            return {'state': 'none', 'familiarity': familiarity}

        # S1: stuck — StuckDetector多信号聚合
        stuck_score = self._check_stuck(policy_data)
        if stuck_score > 0.6:
            return {'state': 'stuck', 'score': stuck_score}

        # S2: cliff — CliffDetector大额悬崖
        cliff_score = self._check_cliff(policy_data)
        if cliff_score > 0.5:
            return {'state': 'cliff', 'score': cliff_score}

        # S3: anomaly — KC稀疏度>0.15
        kc_sparsity = self._compute_kc_sparsity(policy_data)
        if kc_sparsity > 0.15:
            return {'state': 'anomaly', 'score': kc_sparsity}

        # S4: escape — 控费效果逃逸检测
        escape_score = self._check_escape(policy_data)
        if escape_score > 0.4:
            return {'state': 'escape', 'score': escape_score}

        # S5: novelty — CX novelty_direction
        novelty_score = self._check_novelty(policy_data)
        if novelty_score > 0.3:
            return {'state': 'novelty', 'score': novelty_score}

        return {'state': 'none', 'score': 0}

    def drill_down_4level(self, anomaly_state: Dict,
                          policy_data: PolicyAnalysisData) -> Dict:
        """4级分层下钻 (CX 16列组)"""
        return {
            'L1_trend': self._drill_trend(policy_data),
            'L2_category': self._drill_category(policy_data),
            'L3_disease': self._drill_disease(policy_data),
            'L4_indicator': self._drill_indicator(policy_data),
            'drill_path': self._determine_path(anomaly_state),
        }
```

### 2.2 空间记忆网格 → 理赔地理/医院聚类

Fly64 的 SceneMemory 在视觉场景中建立空间记忆网格——在保险理赔中映射为**理赔地理分布聚类 + 医院异常聚集检测**。

```python
# fly64/claims/geo_clustering.py

class ClaimGeoMemory:
    """空间记忆网格 → 理赔地理/医院聚类"""

    # 空间网格: 128×128 城市网格 (由医院地址编码)
    GRID_SIZE = 128  # 可配置
    MEMORY_FRAMES = 30  # 30观测周期

    def __init__(self):
        self.heatmap = np.zeros((self.GRID_SIZE, self.GRID_SIZE))
        self.cluster_centers = []  # 聚类中心(医院密集区)

    def update_from_claims(self, claims: List[ClaimRecord]):
        """理赔数据→空间热图更新"""
        for claim in claims:
            x, y = self._geo_encode(claim.hospital_address)
            amount = claim.claim_amount
            # 费用加权热图
            self.heatmap[y, x] += np.log1p(amount)
        # 高斯平滑 (消除随机噪声)
        self.heatmap = gaussian_filter(self.heatmap, sigma=2)

    def detect_hotspots(self) -> List[Dict]:
        """检测费用集中区域(TP99异常聚集)"""
        threshold = np.percentile(self.heatmap, 99)
        hotspots = []
        for y in range(self.GRID_SIZE):
            for x in range(self.GRID_SIZE):
                if self.heatmap[y, x] > threshold:
                    hotspots.append({
                        'x': x, 'y': y,
                        'intensity': float(self.heatmap[y, x]),
                        'nearby_hospitals': self._find_hospitals(x, y)
                    })
        return hotspots
```

### 2.3 因果链 → 案件调查归因

与 t4 的 seed-64 因果链一脉相承——在每个理赔案件中绑定可追溯的因果链。

```
┌─────────────────────────────────────────────────────────────────────┐
│             Causal Chain for Claim Investigation                    │
│                                                                     │
│  案例: 某会员3月赔付异常飙升                                        │
│                                                                     │
│  seed-64链:                                                         │
│                                                                     │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │ 原始数据 │    │ 异常检测  │    │ 分层下钻 │    │ 归因结论 │          │
│  │ seed:1A2B│──→│ seed:3C4D│──→│ seed:5E6F│──→│ seed:7G8H│          │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘          │
│       │              │              │              │               │
│       ▼              ▼              ▼              ▼               │
│  policy_hash⊕     S2: cliff     L3: 呼吸系统    XX医院单月      │
│  frame_seq       3σ检测触发    疾病偏离18%     费用+340%         │
│                                                                     │
│  可视化 (Web 🧠 Tab):                                                │
│  [原始理赔数据]──异常(S2:cliff)──[L3:呼吸系统疾病]──[XX医院集中]      │
│                                                                     │
│  归因结论: XX医院 2026年3月 呼吸科 费用突增340%                     │
│  → 原因: 季节性流感爆发 + XX医院上量营销                             │
│  → 建议: 加强XX医院呼吸科费用监控                                    │
└─────────────────────────────────────────────────────────────────────┘
```

#### 案件归因Agent改造

```python
# src/agents/case_investigation_agent.py — 脑模型增强

class CaseInvestigationAgent(BaseAgent):
    """案件调查Agent — 因果链归因增强"""

    def _brain_enhanced(self, state: AgentState) -> Dict:
        """脑模型因果链注入调查"""
        brain = state.get('brain_state', {})
        causal_chain = brain.get('causal_chain', [])

        # 因果链 → 调查线索生成
        clues = []
        for link in causal_chain:
            if link['level'] >= 2:  # L2及以上
                clues.append(self._link_to_clue(link))

        # 脑模型steering_bias引导调查重点
        steering = brain.get('brain_steering_bias', 0)
        if abs(steering) > 0.5:
            clues.insert(0, {
                'priority': 'high',
                'direction': 'focus' if steering > 0 else 'caution',
                'source': 'brain_steering',
            })

        return {
            'brain_clues': clues,
            'causal_chain_seed': brain.get('brain_seed64'),
            'investigation_path': self._build_path(causal_chain),
        }
```

### 2.4 自进化 → 控费策略闭环

Fly64 的 TurnAdaptation + 多巴胺学习提供**控费策略的自适应闭环**。

```
┌─────────────────────────────────────────────────────────────────────┐
│              Self-Evolving Cost Control Loop                        │
│                                                                     │
│  1. 策略执行 ──────────────────────────────────────────────┐       │
│     (如: 住院费用管控)                                        │       │
│        │                                                     │       │
│  2. 效果监测 (TurnAdaptation fatigue)                        │       │
│     ┌────────────────────────────────────────────────────┐   │       │
│     │  left_fatigue = 住院管控累积使用                       │   │       │
│     │  right_fatigue = 门诊管控累积使用                      │   │       │
│     │  saturation = 0.5  (50%控费空间已用)                 │   │       │
│     └──────────────────────┬─────────────────────────────┘   │       │
│                            │                                  │       │
│  3. 疲劳检测 → 是否需要轮换?                                  │       │
│     if left_fatigue > 0.7:                                    │       │
│         → counter_drive: 转向门诊管控                         │       │
│     elif saturation > 0.5:                                    │       │
│         → breakout_drive: 综合干预(全面诊断)                  │       │
│                            │                                  │       │
│  4. 效果反馈 → 多巴胺学习                                    │       │
│     ┌────────────────────────────────────────────────────┐   │       │
│     │  实际效果 = (上期赔付率 - 本期赔付率) / 上期赔付率       │   │       │
│     │  dopamine = clip(实际效果, -1, +1)                  │   │       │
│     │  Δgain = η · dopamine · eligibility · (1 - gain)   │   │       │
│     │  → 有效策略增强权重, 无效策略衰减                     │   │       │
│     └────────────────────────────────────────────────────┘   │       │
│                            │                                  │       │
│  5. 策略库更新 ←─────────────────────────────────────────┘       │
│     → consolidated[] 固化有效策略                                │
│     → 下次同场景优先选用                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.5 数据流详细设计

```
┌─────────────────────────────────────────────────────────────────────┐
│          理赔分析专项 — 完整数据流                                    │
│                                                                     │
│  Doris数仓 → ghb_doris_download → per-policy CSV                   │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 脑模型输入向量化 (178维)                                     │   │
│  │                                                              │   │
│  │  1. 月度赔付序列 → 1440帧×4通道 (60fps×24月×4责任)           │   │
│  │  2. 疾病分布 → 50维 ICD-10 大类直方图                         │   │
│  │  3. 医院分布 → 28×28 空间网格编码                            │   │
│  │  4. 会员画像 → 10年龄×2性别 = 20维                           │   │
│  │  5. 时序特征 → 24月滚动窗口统计                              │   │
│  └────────────────────┬──────────────────────────────────────┘   │
│                       │                                           │
│                       ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 并行分析管线                                                  │   │
│  │                                                              │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │   │
│  │  │ 6态异常检测       │  │ 空间记忆网格       │                  │   │
│  │  │ (anomaly_pipeline)│  │ (geo_clustering)  │                  │   │
│  │  └────────┬─────────┘  └────────┬─────────┘                  │   │
│  │           │                      │                             │   │
│  │           ▼                      ▼                             │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │   │
│  │  │ 4级分层下钻       │  │ 医院热点检测      │                  │   │
│  │  │ (CX 16列)        │  │ (TP99聚类)        │                  │   │
│  │  └────────┬─────────┘  └────────┬─────────┘                  │   │
│  │           │                      │                             │   │
│  │           ▼                      ▼                             │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │   │
│  │  │ 因果链归因        │  │ 自进化控费闭环    │                  │   │
│  │  │ (seed-64追踪)    │  │ (TurnAdaptation) │                  │   │
│  │  └────────┬─────────┘  └────────┬─────────┘                  │   │
│  └───────────┼──────────────────────┼───────────────────────────┘   │
│              │                      │                               │
│              ▼                      ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ AgentState 回写 (新增20+字段)                                 │   │
│  │                                                              │   │
│  │  claims_anomaly_state: str       # 6态异常状态               │   │
│  │  claims_drilldown: Dict          # 4级下钻结果                │   │
│  │  claims_geo_hotspots: List        # 地理/医院热区              │   │
│  │  claims_causal_chain: List        # 因果链追踪                │   │
│  │  claims_cost_control_loop: Dict   # 控费闭环状态              │   │
│  │  claims_fatigue_scores: Dict      # 策略疲劳评分              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.6 阈值配置与验证方法

```yaml
# config/analysis.yaml — 理赔分析阈值

claims:
  anomaly_pipeline:
    # 6态检测阈值 (初始化值, 自学习后通过多巴胺调整)
    stuck_threshold: 0.6        # StuckDetector
    cliff_threshold: 0.5        # CliffDetector 3σ
    kc_sparsity_threshold: 0.15  # KC稀疏度异常
    escape_threshold: 0.4       # 控费逃逸
    novelty_threshold: 0.3      # CX novelty
    
    # 3σ自适应 (可切换到动态)
    sigma_multiplier: 3.0       # 赔付率突变检测
    change_window: 10           # 变化检测窗口(月)
    
  drill_down:
    # 4级下钻阈值
    L1_trend_zscore: 1.5        # 整体趋势Z-score
    L2_category_deviation: 0.15 # 责任类型偏离
    L3_disease_deviation: 0.12  # 疾病偏离
    L4_indicator_zscore: 2.0    # 关键指标Z-score
    
  geo_clustering:
    grid_size: 128
    hotspot_percentile: 99       # TP99热区
    cluster_min_distance: 3      # 最小聚类距离(网格)
    
  cost_control_loop:
    fatigue_threshold: 0.7       # 策略疲劳阈值
    saturation_limit: 0.5        # 饱和度上限
    breakout_delay: 2            # 突破模式延迟
    learning_rate: 0.01          # 多巴胺学习率

# 验证方法
verification:
  claims:
    # A/B对比: 纯规则 vs 脑模型
    ab_test_duration: 30        # 天
    ab_test_policies: 200       # 保单数/组
    acceptance_criteria:
      recall_delta: 0.05        # 召回率差不>5%
      precision_delta: 0.05     # 精确率差不>5%
      latency_speedup: 0.5      # 延迟降低>50%
    
    # 回归测试覆盖
    regression:
      test_suite: "tests/unit/test_underwriting*.py"
      coverage_min: 0.80        # 行覆盖率
      accuracy_delta: 0.03      # 精度波动<3%
```

---

## 3. 实施路线图: 6步12周计划

### 总体6步里程碑

```
   W1-2          W3-4           W5-6           W7-8          W9-10         W11-12
  ┌────────┐   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐
  │ 数据   │   │ 脑模型  │    │ DSH     │    │ 混合   │    │ 验证   │    │ 部署   │
  │ 适配层  │→  │ 保险推理 │→  │ 插件桥接 │→  │ 仲裁   │→  │ 测试   │→  │ 上线   │
  │        │    │        │    │        │    │        │    │        │    │        │
  │ P0基础  │    │ P1核心  │    │ P2集成  │    │ P3仲裁  │    │ Q门禁   │    │ 生产   │
  └────────┘   └────────┘    └────────┘    └────────┘    └────────┘    └────────┘
```

### 详细周计划

#### W1-2: 数据适配层 (P0基础集成)

| 周 | 任务 | 产出 | 负责人 | 工时 |
|----|------|------|-------|------|
| W1 | 实现178维脑模型输入向量化管线 | `fly64/input_adapter.py` | 开发 | 3天 |
| W1 | per-policy CSV → PolicyAnalysisData 神经编码 | 编码规格文档 | 开发 | 2天 |
| W1 | Retina ON/OFF → reconciliation 替代绑定 | `fly64/adapters/reconciliation_adapter.py` | 开发 | 2天 |
| W2 | StuckDetector → stability 替代 | `fly64/adapters/stability_adapter.py` | 开发 | 2天 |
| W2 | EMD 4方向 → ramp_analysis 替代 | `fly64/adapters/ramp_adapter.py` | 开发 | 1天 |
| W2 | 数据适配层单元测试 | `tests/unit/test_input_adapter.py` | 开发 | 2天 |
| W2 | 输入数据验证工具 | `scripts/validate_brain_input.py` | 开发 | 1天 |

**配置变更**: `config/analysis.yaml` 新增 `brain_input` 段  
**依赖**: gbcost-analysys 现有 `PolicyAnalysisData` 容器 (无需修改原有ETL)

#### W3-4: 脑模型保险推理 (P1核心融合)

| 周 | 任务 | 产出 | 负责人 | 工时 |
|----|------|------|-------|------|
| W3 | CX 16柱风险罗盘实现 | `fly64/underwriting/cx_risk_compass.py` | 开发 | 3天 |
| W3 | 4反射核保门实现 | `fly64/underwriting/reflex_gates.py` | 开发 | 2天 |
| W3 | MB核保学习器实现 | `fly64/underwriting/mb_underwriting_learner.py` | 开发 | 2天 |
| W3 | CX 16列 → 4级分层异常替换 | `fly64/claims/anomaly_pipeline.py` | 开发 | 2天 |
| W4 | 空间记忆网格 → 地理/医院聚类 | `fly64/claims/geo_clustering.py` | 开发 | 2天 |
| W4 | 因果链 → 案件调查归因 | `src/agents/case_investigation_agent.py` 改造 | 开发 | 2天 |
| W4 | 自进化控费闭环 (TurnAdaptation) | `fly64/claims/cost_control_loop.py` | 开发 | 2天 |
| W4 | 脑模型推理集成测试 | `tests/integration/test_brain_inference.py` | QA | 2天 |

**配置变更**: 迁移现有 `config.yaml` 硬编码阈值到 YAML + 脑模型自适应参数  

#### W5-6: DSH插件桥接 (P2集成)

| 周 | 任务 | 产出 | 负责人 | 工时 |
|----|------|------|-------|------|
| W5 | bridge2rpc 适配器实现 | `plugin/bridge2rpc.js` | 全栈 | 3天 |
| W5 | 核保4个 brain_* 工具注册 | `plugin/ghb-host.js` 改造 | 全栈 | 2天 |
| W5 | 🧠 Web Tab 核保视图 | `plugin/ghb-client.js` 改造 | 全栈 | 3天 |
| W6 | CX 16柱罗盘前端渲染 (Vega-Lite) | 前端罗盘组件 | 前端 | 2天 |
| W6 | F643 WebSocket 0.5Hz 低速通道 | `fly64/neural_viz_skill.py` | 全栈 | 2天 |
| W6 | brain_* RPC 路由注册 | `plugin/brain-rpc-api.js` | 全栈 | 1天 |
| W6 | DSH 端到端集成测试 | 集成测试报告 | QA | 2天 |

**依赖**: W1-2 数据适配 + W3-4 脑模型推理  

#### W7-8: 混合仲裁 (P3仲裁)

| 周 | 任务 | 产出 | 负责人 | 工时 |
|----|------|------|-------|------|
| W7 | 5级仲裁链完整实现 | `src/workflow_hybrid.py` | 架构 | 3天 |
| W7 | divergence 检测 + 自动升级逻辑 | `fly64/arbitration/divergence.py` | 开发 | 2天 |
| W7 | seed-64 全链路可追溯性 | `fly64/arbitration/seed64.py` | 开发 | 1天 |
| W7 | AgentState 40脑模型字段扩展 | `fly64/state_brain.py` | 开发 | 1天 |
| W8 | WeightedVoteArbiter 实现 | `fly64/arbitration/weighted_vote.py` | 开发 | 2天 |
| W8 | L5 人类审核通知机制 | DSH Web OpsPanel 集成 | 全栈 | 2天 |
| W8 | 仲裁链集成测试 | `tests/integration/test_arbitration.py` | QA | 2天 |

**依赖**: W5-6 DSH插件桥接  

#### W9-10: 验证测试 (质量门禁)

| 周 | 任务 | 产出 | 负责人 | 工时 |
|----|------|------|-------|------|
| W9 | gbcost 6134+ 测试回归 | 回归测试报告 | QA | 3天 |
| W9 | 核保A/B测试框架 | `tests/ab_testing/` | QA | 2天 |
| W9 | 理赔分析A/B测试 | A/B测试报告 | QA | 2天 |
| W9 | 性能基准测试 (延迟/吞吐) | 性能报告 | DevOp | 1天 |
| W10 | 质量门禁逐项验证 | 门禁核查表 | QA | 2天 |
| W10 | 精度回归: 脑模型 vs 原始版 | 精度对比报告 | QA | 2天 |
| W10 | 修复+重测 | 修复记录 | 开发 | 2天 |

**依赖**: W1-8 全部代码完成  

#### W11-12: 部署上线

| 周 | 任务 | 产出 | 负责人 | 工时 |
|----|------|------|-------|------|
| W11 | 三进程部署拓扑搭建 | deployment.yaml + docs | DevOp | 2天 |
| W11 | 脑模型常驻进程 (systemd/Windows Service) | 部署脚本 | DevOp | 1天 |
| W11 | 灰度上线: 10% 流量 → 脑模型模式 | 灰度策略文档 | 架构 | 1天 |
| W11 | 🧠 Tab 完整版 + F643 WS | 前端完成 | 前端 | 2天 |
| W12 | 全量上线: 100% → 混合模式(默认) | 上线checklist | 架构 | 1天 |
| W12 | 监控面板搭建 (指标/告警) | Grafana dashboard | DevOp | 2天 |
| W12 | 运维手册 + 回滚方案 | 运维文档 | 架构 | 1天 |
| W12 | 项目总结 + 知识沉淀 | 总结报告 | 架构 | 1天 |

**依赖**: W9-10 质量门禁全部通过  

---

## 4. 质量门禁

### 4.1 每阶段3项量化门禁

```
阶段             门禁1: 精度                   门禁2: 延迟              门禁3: 覆盖率
───────────────────────────────────────────────────────────────────────────────
W1-2 数据适配    输入向量化正确率 ≥ 99%         < 100ms/保单              行覆盖率 ≥ 85%
                  (与原始数据对比)                                        

W3-4 脑模型推理  脑模型召回率 ≥ 70%             < 3s/保单                行覆盖率 ≥ 80%
                  (vs 规则引擎 baseline)       (纯神经推理, 不含LLM)     

W5-6 DSH桥接     bridge2rpc 可用性 ≥ 99.9%     < 2ms/bridge读取         集成测试 ≥ 50场景
                  (24h压力测试)                 < 500ms/HTTP RPC         

W7-8 混合仲裁     混合仲裁召回率 ≥ 90%           < 10min/全管线           因果链追溯率 100%
                  (vs 原始版 Phase2 LLM)       (Mode 3默认路径)           seed-64绑定 100%

W9-10 验证测试    脑模型仲裁一致性 ≥ 90%         性能退化 < 10%             回归测试通过率 100%
                  (与原始版Phase2共识率)        (vs 原始版 6134测试)        (6134+ 全量)

W11-12 部署上线   灰度期精度差异 < 5%            线上P99延迟 < 15min       监控覆盖率 ≥ 95%
                  (脑模型 vs 原始版)                                      异常告警覆盖
```

### 4.2 门禁检测工具

```bash
# 门禁1: 精度检测 (W1-2)
python scripts/validate_brain_input.py --policy GP123 --accuracy 0.99

# 门禁2: 脑模型召回率 (W3-4)
python tests/acceptance/test_brain_recall.py \
  --policy-set tests/fixtures/policies_200.csv \
  --min-recall 0.70

# 门禁3: bridge2rpc 可用性 (W5-6)
python tests/acceptance/test_bridge_uptime.py \
  --duration 86400 --min-uptime 0.999

# 门禁4: 混合仲裁一致性 (W7-8)
python tests/acceptance/test_arbitration_consistency.py \
  --policy-set tests/fixtures/policies_100.csv \
  --min-agreement 0.90

# 门禁5: 全量回归 (W9-10)
pytest tests/ --tb=short -x --coverage > regression_report.txt
# 验证: 100% 测试通过, 覆盖退化 < 3%

# 门禁6: 灰度监控 (W11-12)
# Grafana query: rate(brain_phase2_agreement[24h]) > 0.95
```

---

## 5. 实验验证方案

### 5.1 gbcost测试套件回归

#### 现有测试套件

gbcost-analysys 现有 **166个测试文件** (6134+ test cases):

| 测试类别 | 文件数 | 覆盖模块 |
|---------|-------|---------|
| unit/test_*.py | ~120 | 各分析模块、Agent、工具 |
| agents/test_*.py | ~15 | Agent级测试 |
| e2e/test_*.py | ~4 | 端到端工作流 |
| acceptance/ | ~7 | 验收测试 |

**回归策略**:
1. **不变测试**: 不修改脑模型的模块仍用原有测试
2. **适配测试**: 被脑模型替换的模块 (reconciliation/stability/ramp/...) → 脑模型版本需100%通过原有测试用例
3. **新增测试**: `tests/unit/test_brain_*.py` → 脑模型特有测试

#### 回归执行脚本

```python
# tests/regression/test_brain_regression.py

class TestBrainRegression:
    """脑模型回归测试 — 验证脑模型输出与原始版一致性"""

    # 被替换Agent列表
    REPLACED_AGENTS = [
        'reconciliation',      # → Retina ON/OFF
        'stability',           # → StuckDetector
        'ramp_analysis',       # → EMD 4方向
        'anomaly_detection',   # → KC稀疏编码 + CX罗盘
    ]

    @pytest.mark.parametrize('agent', REPLACED_AGENTS)
    def test_agent_replacement_consistency(self, agent, policy_fixture):
        """验证脑模型替代Agent的召回率"""

        # 原始版
        original_result = run_original_agent(agent, policy_fixture)

        # 脑模型版
        brain_result = run_brain_agent(agent, policy_fixture)

        # 召回率 >= 70% (脑模型初始版本)
        assert recall(original_result, brain_result) >= 0.70, \
            f"Agent {agent} brain recall below 70%"

        # 假阳性率 < 15%
        assert fall_out(original_result, brain_result) < 0.15

    def test_full_pipeline_regression(self, full_policy_fixture):
        """全管线回归 — 对比混合仲裁输出与原始版"""

        # Mode 3 (混合) vs 原始 Phase2
        hybrid_result = run_hybrid_pipeline(full_policy_fixture)
        original_result = run_original_pipeline(full_policy_fixture)

        # 关键指标一致性
        key_fields = [
            'health_score', 'fwa_result', 'anomaly_level',
            'cost_control_recommendations'
        ]
        for field in key_fields:
            assert agreement(hybrid_result[field], original_result[field]) >= 0.85
```

### 5.2 A/B测试框架

#### A/B测试架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                A/B Testing Framework for Brain Insurance            │
│                                                                     │
│                              ┌──────────┐                           │
│                              │ 200保单集  │                           │
│                              │ (分层抽样) │                           │
│                              └────┬─────┘                           │
│                                   │                                 │
│                     ┌─────────────────┐                            │
│                     │   随机分组       │                            │
│                     └────────┬────────┘                            │
│                              │                                     │
│              ┌───────────────┼───────────────┐                     │
│              ▼               ▼               ▼                     │
│     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│     │ Group A:     │ │ Group B:     │ │ Group C:     │             │
│     │ 纯规则(现状)  │ │ 脑模型原生   │ │ 混合模式     │             │
│     │ Mode 2       │ │ Mode 0       │ │ Mode 3       │             │
│     │ 100保单       │ │ 100保单       │ │ 100保单       │             │
│     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
│            │                │                │                      │
│            ▼                ▼                ▼                      │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │                 对比维度                                  │    │
│     │                                                         │    │
│     │  ⏱️ 延迟:  total_duration / agent_duration              │    │
│     │  🎯 精度:  recall / precision / f1 / agreement          │    │
│     │  💰 成本:  token_count / api_cost                       │    │
│     │  🔍 覆盖:  anomaly_coverage / rule_coverage             │    │
│     │  📊 稳定:  result_variance / seed_reproducibility       │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                     │
│ 输出: A/B/C 三组对比报告 (JSON + HTML)                              │
└─────────────────────────────────────────────────────────────────────┘
```

#### A/B测试实现

```python
# tests/ab_testing/ab_test_runner.py

class BrainABTestRunner:
    """脑模型 A/B 测试框架"""

    def __init__(self, policy_set_path: str):
        self.policies = self._load_policies(policy_set_path)
        self.results = {'A_rule': [], 'B_brain': [], 'C_hybrid': []}

    def run(self) -> Dict:
        """执行A/B/C三组对比测试"""

        # 分层随机分组 (按行业/规模分层)
        groups = self._stratified_split(self.policies, 3)

        for policy in groups['A_rule']:
            result = self._run_mode(policy, 'rule_only')
            self.results['A_rule'].append(result)

        for policy in groups['B_brain']:
            result = self._run_mode(policy, 'brain_native')
            self.results['B_brain'].append(result)

        for policy in groups['C_hybrid']:
            result = self._run_mode(policy, 'brain_hybrid')
            self.results['C_hybrid'].append(result)

        return self._compare_results()

    def _compare_results(self) -> Dict:
        """三组对比分析"""
        return {
            'latency': {
                'A_rule': self._avg([r['duration'] for r in self.results['A_rule']]),
                'B_brain': self._avg([r['duration'] for r in self.results['B_brain']]),
                'C_hybrid': self._avg([r['duration'] for r in self.results['C_hybrid']]),
            },
            'accuracy': {
                'A_rule': self._compute_accuracy(self.results['A_rule']),
                'B_brain': self._compute_accuracy(self.results['B_brain']),
                'C_hybrid': self._compute_accuracy(self.results['C_hybrid']),
            },
            'agreement': {
                'A_vs_B': self._pairwise_agreement(
                    self.results['A_rule'], self.results['B_brain']),
                'A_vs_C': self._pairwise_agreement(
                    self.results['A_rule'], self.results['C_hybrid']),
                'B_vs_C': self._pairwise_agreement(
                    self.results['B_brain'], self.results['C_hybrid']),
            },
            'acceptance': {
                'A_rule_pass': self._check_acceptance(self.results['A_rule']),
                'B_brain_pass': self._check_acceptance(self.results['B_brain']),
                'C_hybrid_pass': self._check_acceptance(self.results['C_hybrid']),
            }
        }

    def _check_acceptance(self, results: List) -> bool:
        """验收标准检查"""
        avg_latency = self._avg([r['duration'] for r in results])
        avg_agreement = self._avg([r.get('rule_agreement', 1) for r in results])
        return (
            avg_latency <= 600_000 and  # < 10min
            avg_agreement >= 0.85       # ≥ 85% 与规则一致
        )
```

#### 验收标准

```yaml
# tests/ab_testing/acceptance_criteria.yaml

ab_test:
  # 分组策略
  sampling: "stratified"        # 分层抽样
  strata: ["industry", "scale", "loss_ratio_range"]
  policies_per_group: 100
  
  # 验收门禁
  acceptance:
    # 延迟
    latency:
      max_total: 600_000        # ms (< 10min Mode 3)
      max_brain: 5_000          # ms (< 5s 脑模型)
    
    # 精度 (与原始版 Phase2 LLM 对比)
    accuracy:
      min_agreement: 0.85       # 决策一致率 ≥ 85%
      max_deviation: 0.05       # 关键指标偏离 < 5%
    
    # 成本
    cost:
      max_tokens_per_policy: 50000  # Mode 3 平均
      brain_only_tokens: 0          # 脑模型0 token
    
    # 稳定性
    stability:
      min_reproducibility: 0.99     # seed-64 可重现率
      max_variance: 0.10            # 结果方差
    
  # 可接受退化
  degradation:
    max_recall_drop: 0.05       # 召回率下降不超过5%
    max_precision_drop: 0.03    # 精确率下降不超过3%

  # 灰度上线检查 (W11-12)
  rollout:
    canary_ratio: 0.10          # 初始10%流量
    canary_duration: 7          # 天
    canary_acceptance:
      error_rate_inc: 0.01      # 错误率增长<1%
      latency_p99_inc: 0.20     # P99延迟增长<20%
      user_complaint: 0         # 0投诉
```

---

## 附录A: 文件变更清单总览

| 文件路径 | 变更类型 | 优先级 | 预估行数 | 依赖 |
|---------|---------|-------|---------|------|
| `fly64/underwriting/cx_risk_compass.py` | 新建 | P0 | 300 | Fly64 CX |
| `fly64/underwriting/reflex_gates.py` | 新建 | P0 | 200 | CX风险评分 |
| `fly64/underwriting/mb_underwriting_learner.py` | 新建 | P1 | 250 | MB KC/MBON |
| `fly64/underwriting/__init__.py` | 新建 | P0 | 50 | — |
| `fly64/claims/anomaly_pipeline.py` | 新建 | P0 | 350 | anomaly_state |
| `fly64/claims/geo_clustering.py` | 新建 | P1 | 200 | SceneMemory |
| `fly64/claims/cost_control_loop.py` | 新建 | P1 | 250 | TurnAdaptation |
| `fly64/input_adapter.py` | 新建 | P0 | 300 | PolicyAnalysisData |
| `fly64/adapters/reconciliation_adapter.py` | 新建 | P0 | 100 | Retina ON/OFF |
| `fly64/adapters/stability_adapter.py` | 新建 | P0 | 100 | StuckDetector |
| `fly64/adapters/ramp_adapter.py` | 新建 | P0 | 80 | EMD 4方向 |
| `fly64/arbitration/divergence.py` | 新建 | P2 | 150 | divergence |
| `fly64/arbitration/seed64.py` | 新建 | P2 | 100 | seed-64 |
| `fly64/arbitration/weighted_vote.py` | 新建 | P2 | 120 | 加权投票 |
| `fly64/state_brain.py` | 新建 | P2 | 120 | AgentState扩展 |
| `plugin/bridge2rpc.js` | 新建 | P1 | 250 | seqlock |
| `plugin/brain-rpc-api.js` | 新建 | P1 | 200 | RPC路由 |
| `plugin/ghb-host.js` | 修改 | P1 | +150 | 4 brain_* 工具 |
| `plugin/ghb-client.js` | 修改 | P1 | +200 | 🧠 Tab |
| `src/workflow_hybrid.py` | 新建 | P2 | 200 | LangGraph |
| `src/agents/underwriting_agent.py` | 修改 | P1 | +150 | 核保Agent |
| `src/agents/case_investigation_agent.py` | 修改 | P2 | +80 | 因果链 |
| `config/analysis.yaml` | 修改 | P0 | +100 | 阈值配置 |
| `tests/unit/test_brain_*.py` | 新建×6 | P1 | 600 | 全模块 |
| `tests/integration/test_brain_inference.py` | 新建 | P1 | 200 | 集成 |
| `tests/integration/test_arbitration.py` | 新建 | P2 | 200 | 仲裁 |
| `tests/ab_testing/ab_test_runner.py` | 新建 | P2 | 300 | A/B测试 |
| `tests/acceptance/*.py` | 新建×6 | P2 | 300 | 门禁 |
| **合计** | | | **~5500行** | |

## 附录B: 关键决策记录

| 决策 | 选项 | 选择理由 |
|------|------|---------|
| CX 16列→4级分层: 连续vs离散 | 连续模拟 ≠ 离散阈值 | 连续steering_bias提供强度信号, 优于原有硬阈值二元触发 |
| Reflex vs 规则引擎 | Reflex 4路独立 | Reflex仅50ms决策, 23Agent规则需5min; Reflex用作"核保门控" |
| MBON 5通道 vs 6因子 | 5通道(forward/left/right/jump/explore) | 与果蝇原生对齐; 6因子健康评分可映射到5通道+1综合 |
| bridge2rpc JS vs Python | JS (Node.js) | 直接嵌入ghb-host.js, 无需额外进程; Python版作为WSL备选 |
| A/B测试3组 vs 2组 | 3组(A规则/B脑原生/C混合) | 同时验证脑模型自身精度 + 混合仲裁增益 |
| 增量上线 vs 全量切换 | 灰度10%→50%→100% | 每阶段7天观察, 风险可控 |