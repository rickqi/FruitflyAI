# T1: 全量瓶颈根因分析报告

> 作者: data-analyst (瓶颈深度分析师)
> 日期: 2026-09-16
> 团队: fly64-bottleneck-roundup
> 脑模型版本: Brain v2.13.3 (SKILL 3.0.0)

---

## 一、概述

本报告系统分析 Fly64 脑模型当前存在的 **7 大瓶颈**（3项历史未解决 + 4项进化新问题）及 **2 项部分缓解项**，为后续修复实施提供精准根因定位、影响范围评估及修复建议。

---

## 二、核心瓶颈分析

### B1. 语义三缺失 (Semantic Triple Missing) — 历史未解决

#### 根因
Fly64 当前的场景理解停留在**特征级量化**而非**语义级理解**。三处结构性缺失：

1. **标签-行为映射断裂**: `scene_recognition.py` 的 `classify_terrain()` 输出 8 类地形标签，但标签仅进入 `model.scene_danger` 作为单标量 (0–1)，丢失了"具体什么在危险"的语义信息——例如 lava vs 悬崖触发同一危险信号，无法差异化响应。

2. **what_i_see 单向性**: `plugin/llm_consult.py` 的 what_i_see 是 LLM 教练的**输出**，大脑自身没有任何"我看到了什么"的内生语义表征。场景识别停留在统计匹配（P05/P50/P95 分位数），无语义推理能力（如"红色+下视野高饱和 → 熔岩 → 需要跳跃而非转向"）。

3. **多标签冲突无仲裁**: 场景可同时具备"室内+悬崖+危险"等多重属性，但当前 `_scene_name()` 只取优先级最高标签，丢失了融合信息。MBON 学习需要语义级场景上下文才能正确关联。

#### 影响范围
- **所有行为决策**: 丢失语义上下文 → 行为选择缺乏精细化
- **MBON 学习**: KC 输入缺乏语义标签 → Hebbian 可塑性无法形成语义级关联
- **EvolutionSkill 诊断**: 语义缺失使诊断模式无法区分"同类但不同语义"场景

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 语义标签编码 | `model.py` | 新增 `scene_semantics` 多标签编码器 (bitmask 或 one-hot)，从 `scene_recognition` 输出的 tags + class 融合生成 |
| 语义→KC 注入 | `model.py` step() | 语义编码向量作为附加输入注入 KC 前方 drive（非替换现有 scene_sig） |
| 语义仲裁器 | `scene_recognition.py` | 新增 `resolve_semantics(tags, features, flow)` 方法——当多标签冲突时（如 indoor+cliff），依据视觉特征置信度输出加权语义向量 |
| what_i_see 内化 | `model.py` | 新增 `model.semantic_labels` 属性将场景语义镜像为 JSON 化标签，供 flow.json 透传到仪表板 |
| 测试 | `tests/test_scene_recognition.py` | 新增语义仲裁 3 用例 |

---

### B2. 视网膜配准 (Retina Calibration/Registration) — 历史未解决

#### 根因
`retina.py` 第 3–6 行注释明确声明：**registration is engineered, NOT a measured MaleCNS optical calibration**。具体问题：

1. **Azimuth 映射是近似值**: `azimuth_deg = [-135 + col*143.5/31]` 基于列索引的线性映射，而非基于光学柱的实测角度分布。MaleCNS 的视柱定位在 Lobula 层面有非线性畸变，当前线性假设引入了 ~5–15° 的方位误差。

2. **Elevation 仅依赖行索引**: `elevation_deg = 72 - row/47*144` 假设垂直覆盖在 48 行间均匀分布，但真实果蝇复眼的垂直取样密度不均匀（赤道区密度更高）。

3. **UV 通道是工程近似**: `UV_appx = max(0, B - 0.5*(R+G))` 并非基于实际 UV 感光细胞光谱响应测量，仅为 blue-minus-luminance 启发式。

4. **无标定验证流程**: 当前无独立标定测试（test_retina.py 中无 registration 精确度验证用例）。

#### 影响范围
- **方位判断误差**: 5–15° 方位误差 → CX 导航 / escape 转向方向偏差
- **地形分类降级**: 扇区边界偏移导致 terrain 错误分类（如室内边界误判为墙）
- **EMD/HRC 方向选择性**: 邻接对依赖正确的空间邻居映射，角度误差弱化方向选择性
- **小目标追踪**: `compute_small_targets()` 的网格结构依赖精确的视网膜映射

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 角度映射替换 | `retina.py` CALIBRATION + `SphericalRetina.__init__` | 加载实测 MaleCNS 光学柱角度 CSV 替换线性假设；保留 `spherical-v2` 作为降级键 |
| UV 通道校准 | `retina.py` `encode_color()` | UV 通道改用 `max(0, B - 0.4*R - 0.6*G)` 或可加载的另一个启发式权重集 |
| 垂直采样密度校正 | `retina.py` evelation_deg 计算 | 按 MaleCNS 赤道放大因子引入权重映射，赤道区同角距采更多点 |
| 标定验证用例 | `tests/test_retina.py` | 新增 registration 精确度测试（合成靶标 → 测量 vs 期望角度偏差） |

---

### B3. P2 KPI 复测 (P2 KPI Retest) — 历史未解决

#### 根因
Phase 2 引入的关键 KPI（小目标追踪 `compute_small_targets()`、4 方向 EMD `compute_emd()`）自 Brain v2.0.0 (EVO R7) 以来没有独立的**端到端性能基准测试**。现有测试仅覆盖单元级别的功能正确性：

1. **无在线 KPI 基准**: `test_mushroom_body.py` 的 27 用例只测单元功能，未在模拟器环境中测量"平台跳跃成功率"（目标 65%）或"躲避距离"（目标 6 体长）。
2. **无回归门禁**: 代码演进可能悄然降级 P2 性能（如 R17 MBON 稳态缩放对探索逻辑的间接影响），但无指标阈值防护。
3. **KPI 口径漂移**: 原始目标指标（"平台跳跃 30%→65%"）缺乏可复现的测量脚本——`test_small_target.py` 不存在，目标追踪测试混在 `test_mushroom_body.py` 中。

#### 影响范围
- **平台跳跃成功率不可知**: 无法判断卡尔曼滤波拦截是否仍然有效
- **小目标追踪退化风险**: 结构重构（如 P1 A 类旁路删除）可能无意中移除追踪依赖 -> 无测试发现
- **逃脱指标无量化基准**: stuck_duration 中位数、coverage_rate 等行为级 KPI 无持续跟踪

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 独立 KPI 测试模块 | `tests/test_p2_kpi.py` (新建) | 包含：a) 合成场景测量平台跳跃拦截成功率；b) 运动目标追踪的卡尔曼滤波精度；c) EMD 方向选择性 S/N 比 |
| KPI 回归门禁 | `tests/test_invariants.py` 或新文件 | 在 CI 中自动运行 P2 KPI 基准，偏离 >10% 标记 FAIL |
| 在线 KPI 遥测 | `main.py` + `telemetry.py` | flow.json 新增 `target_lock_pct` / `em_direction_accuracy` 等 KPI 键 |

---

### B4. MBON 饱和拉锯 (MBON Saturation Tug-of-War) — 进化新问题

#### 根因
R17 (Brain v2.11.0) 引入的稳态突触缩放（homeostatic scaling）与 DAN 持续正多巴胺之间存在**结构性对抗**：

```
正向循环:
  DAN 正信号 → MBON 柱膨胀 → |output| → 1.0 (饱和)
    → homeostatic ×0.9 收缩 → 收缩后 DAN 再膨胀 → 再次饱和
```

具体机制链：
1. `mushroom_body.py` `encode()` 中, `scale_factor=0.9` 每次饱和均 reduce 10%
2. 但 R18 (DAN shaping) 设定 `DAN_REWARD_EXPLORATION=0.30` / `DAN_REWARD_PROGRESS=0.30`，即使收缩后这些奖励也会**重新膨胀**该柱
3. 平衡点落在 tanh 天花板附近（`|output|≈0.98`），柱处于**持续的饱和/收缩交替**——这不是健康的学习稳态
4. **无收敛剂量**: homeostatic 是开放循环——没有"此柱已稳定在动态范围内"的退出条件

#### 影响范围
- **MBON 输出不可靠**: 饱和柱的输出 ≈ 1.0 或 -1.0，无法表达微妙的偏好差异
- **学习效率下降**: KC→MBON 权重在饱和/缩放间震荡，三元因子 Hebbian 的增量被周期性抹除
- **forward 行为劣化**: `mb_mbon_forward` 持续性饱和意味着"前进"建议始终最强，大脑不会学到"某些场景不应前进"

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 饱和退出条件 | `mushroom_body.py` `encode()` | 新增 `_recovery_counter`——homeostatic 缩放后若连续 N 帧柱保持在 |output|<0.85，标记"已恢复"并禁止再次触发饱和缩放（上阈值 0.95）|
| DAN 自适应缩放 | `model.py` `_compute_dopamine()` | 当 `model.mb_mbon_forward` 饱和 (≥0.95) 时，正 DA 增益衰减 50%（自适应门控——MBON 饱和→"学习已够"）|
| 饱和事件遥测 | `main.py` flow.json | 已存在 `mb_saturation_events`，但需新增 `mb_saturation_last`/`mb_saturation_rate` 用于趋势分析 |
| 测试 | `tests/test_mbon_saturation.py` | 新增饱和拉锯稳态测试——验证 DA 注入下 MBON 最终收敛而非持续震荡 |

---

### B5. 计算纪律 (Computational Discipline) — 进化新问题

#### 根因
Fly64 的视觉/推理流水线持续增加新特征通道，但**无正式的计算预算管理**：

1. **核心问题**: `retina.py` 的 `compute_flow()` 每帧执行~30 项独立计算（16扇区亮度、8 类 terrain、ON/OFF/sustained、HRC、EMD、color_encode、edge_orientation、ground_angle、door_frame、tau、small_targets...）。无单帧总耗时预算约束。

2. **帧速率过冲风险**: 在 50fps (20ms/帧) 目标下，脑模型 main loop 需在 ~5ms 内完成所有神经计算 + HTTP/WS 处理。若 `compute_flow` + `encode` + `step` + `mushroom_body.encode` 总时间 > 5ms，帧率将不可逆地下降。

3. **增量退化历史**:
   - EVO R7 (v2.0.0): 新增颜色/EMD/small_targets → 约+40μs
   - EVO R8 (v2.1.0): 新增 HRC → 约+20μs
   - R16-R19: 多次神经注入增量 → 每步约+15μs
   - 当前无性能基准，无法判断是否已接近临界值

#### 影响范围
- **帧率稳定性**: 在低端部署（WSL 模拟器端）可能帧率不达标
- **实时性劣化**: 计算超时积累→遥测延迟→教练咨询滞后
- **电池/功耗**: 持续 CPU 满负荷运行

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 性能基准测试 | `tests/test_performance_budget.py` (新建) | 使用合成帧测量每个模块的耗时（μs），与预设预算对比——未超=pass，单模块超=warning，总超=fail |
| 帧率监控遥测 | `telemetry.py` `observe()` | 新增 `frame_compute_ms` 字段（`time.perf_counter` 环绕 process_frame），flow.json 透传 |
| 按帧节流机制 | `retina.py` `compute_flow()` | 引入 `skip_layers` 参数——当帧率 <45fps 时自动跳过 expendable 层（color_azimuth / door_frame / small_targets） |

---

### B6. 遥测漂移回归 (Telemetry Drift Regression) — 进化新问题

#### 根因
`telemetry.py` `Observatory.observe()` 的 row 数据存在**低幅漂移 + 偶发回归**：

1. **浮点精度漂移**: `flow_asymmetry` / `flow_looming` / `hrc_asymmetry` 等标量通过多次 Python 均值计算（`float(x.mean().item())`），受 numpy 批次均值精度和浮点舍入模式影响，相同输入在相邻 tick 间可能产生 ±1e-6 的微小差异。

2. **状态镜像延迟**: `model.flow_asymmetry` 是 `step()` 内计算的瞬时值，但 `observe()` 在 `step()` 完成后读取——当 main.py 在误解码先写再读 `flow_json` 时有 1 tick 延迟。R16 修复了"先写后读"但未彻底消除所有键的延迟匹配。

3. **history 行漂移**: `Observatory.observe()` 采用 `self.rows.append(row)` + 在 `packet()` 中 `self.rows = []` 的清空模式——如果 `packet()` 抛出异常（如 JSON 序列化错误），rows 积压不清空 = 后续 packet 包含旧行 → 仪表板时间轴断点。

4. **EVO R22 发现 `mb_mbon_forward` 曾经缺失的遥测盲区已在 R22 补全，但**每轮新键引入都可能带来新的漂移源**。

#### 影响范围
- **仪表板数据不一致**: 用户看到的 field value 与脑内实际值有微小偏差
- **EvolutionSkill 误判**: DiagnosisEngine 读取遥测诊断时可能被漂移误导
- **教练决策基于偏数据**: coach 的 advice 基于有延迟的 flow.json → 策略参数可能偏旧

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 遥测一致性检查 | `tests/test_invariants.py` | 新增遥测字段轮询——对所有 flow.json 键验证 `isinstance(v, (int, float, bool, str)) or v is None`（排除 numpy 类型泄漏） |
| packet 安全清空 | `telemetry.py` `packet()` | `try-finally` 包裹 `self.rows=[]`，确保异常时 rows 不被清空导致丢失，或者用 `self.rows, snapshot = [], self.rows` 原子交换 |
| 漂移检测自检 | `telemetry.py` 或独立模块 | 每 600 tick 对已知常量 field（当场景不变时）检查 std-dev 是否 < 1e-4，超过即记录 `telemetry_drift` 事件 |
| 延迟匹配审计 | `main.py` test helper | 新增 `--audit-telemetry-lag` 模式——检查 flow.json 中 `frame_age` 是否恒定 >1 tick |

---

### B7. 死值遥测 (Dead-value Telemetry) — 进化新问题

#### 根因
某些遥测键在脑模型运行期间**从不更新**或**更新但值恒常**。

1. **已知死键**: R20 审计发现 `decision_source` 在非 escape 时期恒为 `"steering"`——这可能是正确的，但 `gate_forward` / `gate_jump` 在大多数时间保持 bool 恒常，仪表板用户无法区分"系统正常工作"和"遥测卡住"。

2. **机械死值**: `enclosure_score` 等组合指标在场景不变时输出恒定值——这是设计正确的，但 EvolutionSkill 的诊断引擎 **无法区分正常死值和遥测故障**。

3. **Numpy 类型泄漏**: `sector_contrast` 为 `int` 列表（Python 原生）但 `sector_loom` 为 dict——当 `json.dumps(allow_nan=False)` 处理时，异常的 NaN/Inf 会引发 `ValueError` 被 `packet()` 吞掉 → rows 静默丢失。

4. **pattern 死值**: EVO 中 `default_patterns.json` 的 `mbon_saturation` 模式在 R22 前命中 0 次——不是因为没有饱和，而是因为检测链路本身不完整。

#### 影响范围
- **EvolutionSkill 诊断盲区**: 死值导致 `SensorSample` 在时间窗口内检测不到有效变化 → 无限等待
- **仪表板误导**: 用户看到恒定的 `gate_forward` = True 以为系统活跃，实际该字段已凝固
- **诊断轮次浪费**: EvolutionSkill 常驻循环在遇到死值遥测时进入空转

#### 修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 死值检测器 | `evolution_skill.py` SensorSample | 新增 `_dead_key_detector`——对每个采样字段跟踪最近 N 次值的变化率；如果 100 tick 内变化 < 1% 且字段非静态（如 not `decision_source`），标记 `dead_telemetry` 事件 |
| 遥测心跳 | `main.py` flow.json | 新增 `seq` 单调序列号和 `watchdog_seq` 每 100 tick 自增——仪表板/EvolutionSkill 可据此判断遥测流是否活跃 |
| numpy 类型守卫 | `telemetry.py` `packet()` | 增加 `json.JSONEncoder` 子类或 `default=str` 但不丢失信息——可将异常值替换为 `null` 而非崩溃 |
| 死值自检 | `main.py` + `telemetry.py` | 每 3000 tick 运行一次自检——对所有非静态字段检查 std-dev，全部 < 1e-6 则记录 `telemetry_stall` 告警 |

---

## 三、部分缓解项到位程度

### M1. 静息光流 R19 (Resting Optical Flow R19)

#### 缓解描述
EVO R19 (Brain v2.12.0) 通过 **restlessness 电流** 解决了"静息状态（无动作）时光流无效 → 突破电流失效"的问题——对峙时间/环路压力积累为 forward 躁动电流，在视觉信号无效时提供行为驱动力。

#### 到位程度评估: **65%** (部分缓解)

**已到位**:
- ✅ `model.py` `restlessness_level()`: 对峙时间 (standoff/30s) + 环路压力 (loop−0.8)×5 → [0,1] 标量
- ✅ 电流注入: forward 池 ×0.12 (spike 前)
- ✅ `model.scene_danger` → forward 谨慎抑制 −0.06 (识别→行为闭环)
- ✅ 测试: `tests/test_restlessness.py` 6 用例

**未到位** (35%):
- ❌ **静息光流本身未检测**: R19 处理的是"静息状态无动作后果"，但**未检测静息时光流信号的噪声特性**——静止画面上 `flow_asymmetry` 应有 |值|<0.02（噪声），但当前无品质门控
- ❌ **无 optic_flow_quality 指标**: 当 `temporal_energy` < 阈值时，flow 信号不可靠，但无 `flow_quality` 字段告警下游消费者
- ❌ **静息 HRC 抑制**: HRC 在静止时对纹理噪声产生虚假方向信号，R19 未处理 HRC 噪声抑制
- ❌ **测试未覆盖静息→运动切换**: 6 用例集中在 restlessness 累积本身，未测试"静息→运动恢复"的转换延迟和过冲

#### 补充修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| 光流质量门控 | `retina.py` `compute_flow()` | 新增 `flow_quality = min(1.0, temporal_energy / threshold)` → quality<0.3 时信号降权 |
| HRC 静止抑制 | `retina.py` `compute_hrc()` | temporal_energy 低时 HRC 输出归零（或乘以 quality) |
| 切换延迟测试 | `tests/test_restlessness.py` | 新增 2 用例—A)静息→前进的响应延迟 ≤200ms; B)恢复运动后 restlessness 衰减 ≤500ms |

---

### M2. 可塑性等效 (Plasticity Equivalence)

#### 缓解描述
参考 `docs/lif_injection_feasibility_report.md` 中描述的 LIF 电流注入等效框架——通过将学习驱动的行为偏向转化为 LIF 网络的多巴胺-塑形规则，实现**无 Python 判断控制**的行为学习。

#### 到位程度评估: **50%** (部分缓解)

**已到位**:
- ✅ **三元因子 Hebbian 可塑性**: `mushroom_body.py` `update_weights()` 实现 `ΔW = η·R(t)·E[i,j]`（活性/多巴胺门控）
- ✅ **奖励/惩罚通路的 DAN 塑形**: `model.py` `_compute_dopamine()` 通过 `DAN_*` 常量塑形
- ✅ **无 Python 控制原则**: EVO R18 吨位降低后，MBON 学习在前向/回避决策中的影响力使用电流注入（`model.py` step() 内多巴胺后注入）
- ✅ **前馈一致性**: `mushroom_body.py` 的 `encode()` + `set_dopamine()` + `update_weights()` 实现外侧蘑菇体（als）→ MBON 通路

**未到位** (50%):
- ❌ **ON/MBON 到电机池的电流权重不可调**: 当前 MBON 输出 → motor pool 的映射为固定幅度（tanh 后直接作为增益），无独立的**突触强度参数**——对应生物学中 Mushroom Body Output Neuron→Motor 前馈权重
- ❌ **无经验性权重归一化**: MBON 输出在跳跃后未归一化，导致 DA 积累→正反馈→饱和（B4）这一结构性问题的根本原因之一——若 MBON 输出经层归一化再注入，饱和对抗会自然消失
- ❌ **回顾遮蔽行为**: 在熟悉场景中，MBON 的 revisit_penalty 生效较慢（需 >0.5），且 KC 签名在大场景中混淆——对应生物学上的"回忆→遮蔽"能力未建模
- ❌ **无学习率自适应**: LEARNING_RATE = 0.001 固定，场景变化率低时应加速，场景不稳定时应减速——缺自适应

#### 补充修复建议

| 修复项 | 涉及文件 | 修复方式 |
|--------|---------|---------|
| MBON→motor 权重层 | `model.py` step() | 新增 `mbon_forward_weight` / `mbon_turn_weight` 参数（可调，初始 0.35），分离 MBON 对 motor pool 电流注入的独立缩放 |
| MBON 层归一化 | `mushroom_body.py` encode() | MBON 输出在 tanh 后增加 `layer_norm` 步骤——`outputs = tanh(raw) / sqrt(1 + var(raw))` -> 饱和自动抵消 |
| 自适应学习率 | `mushroom_body.py` update_weights() | `lr_adapt = LR * min(1.0, scene_change_rate * 5)`——场景变化快时学习加速，稳定时保守 |
| 测试覆盖 | `tests/test_mushroom_body.py` | 新增 MBON→motor 权重独立 2 用例 + 层归一化 2 用例 + 自适应 lr 2 用例 |

---

## 四、瓶颈依赖关系与修复优先级

```
B1 (语义三缺失) ──→ B2 (视网膜配准)
  │                    │
  ├──→ B4 (MBON饱和) ←─┤ (饱和依赖语义精确度)
  │                    │
  ├──→ B6/B7 (遥测问题) │ (遥测偏/死值影响所有下游)
  │                    │
  └──→ M2 (可塑性等效)  └──→ M1 (静息光流)

B3 (P2 KPI) ──→ B5 (计算纪律) ──→ 全系统稳定
```

**建议修复顺序**:
1. **B7 (死值遥测)** + **B6 (遥测漂移)** — Priority 0, 无阻塞依赖, 修复快速, 是所有其他瓶颈检测的前提
2. **B4 (MBON饱和拉锯)** — Priority 0, 影响 DAN 学习和行为
3. **B5 (计算纪律)** + **M1 (静息光流补充)** — Priority 1, 系统稳定性基础
4. **B1 (语义三缺失)** — Priority 2, 依赖遥测修复 (B6/B7) 作为前序
5. **B2 (视网膜配准)** — Priority 2, 独立可并行
6. **M2 (可塑性等效)** — Priority 2, 依赖 B4 修复后
7. **B3 (P2 KPI 复测)** — Priority 3, 持续性基准

---

## 五、跨瓶颈共享修复模式

### 5.1 归一化层 (Normalization Layer)
B4 (MBON饱和) 与 M2 (可塑性等效) 共享相同修复模式——**MBON 输出层归一化**。建议在 `mushroom_body.py` `encode()` 中一次实现，同时解决两个瓶颈。

### 5.2 遥测品质门控 (Telemetry Quality Gate)
B6 (漂移) + B7 (死值) + M1 (静息光流) 共享"**信号质量指示器**"模式。建议在 `telemetry.py` 中新增 `signal_quality` 计算模块，为每个关键信号附置信度字段。

### 5.3 自适应参数化 (Adaptive Parameterization)
B4 (饱和退出条件) + M2 (自适应学习率) 共享"**场景感知参数自适应**"模式。建议在 `model.py` 或 `mushroom_body.py` 中统一实现。

---

## 六、风险提示

1. **B2 视网膜配准** 的修复依赖 MaleCNS 实测角度映射数据——如果数据未就绪，应使用**半合成矫正**（拟合多项式的近似最优映射）作为过渡，并在 CALIBRATION 中标记 `registration="polynomial-v1"`，与 `spherical-v2` 共存
2. **B4 MBON 饱和** 的两项修复（退出条件 + DAN 自适应缩放）必须**协同实施**——单独加退出条件而无 DA 缩放，退出后 DA 立即再膨胀
3. **B5 计算纪律** 需要建立在 `test_performance_budget.py` 基准上——该测试本身需先于 B5 修复创建
4. **B6/B7 遥测修复** 必须在其他瓶颈修复之前完成——所有下游修复依赖可靠的遥测数据

---

*本报告基于 Brain v2.13.3 代码基分析完成，所有文件路径均相对于 `D:\codes\flygym\` 工作空间根目录。*