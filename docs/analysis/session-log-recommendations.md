# Fly64 脑模型项目 — 执行建议与优先级路线图

> **生成时间**: 2026-09-24  
> **数据来源**: `docs/analysis/session-log-analysis.md`（t2 综合分析与主题模式识别）  
> **方法论**: 基于 12 个 DSH 会话日志（11 个唯一会话 ID）、462 行综合分析、5 个当前困境、12 个"机制存在、报告成功、无法生效"模式案例  
> **数据可信度约束**: 本建议**不引用** t1 的聚合工具调用计数（已证实失真）；工作量估计基于代码复杂度与改动面（file:line、diff 规模）  
> **前置依赖**: 已完成 `fly64-comprehensive-fix` 团队的 5 项治理性修复（WSL 启动器、SM64 显示、Phase 6 进化效率、契约审计制度化、门禁冲刺）  
> **数据来源分级**:
>   - 🟢 **基于当前代码**: 当前 `file:line` 引用（标注为"当前实测"的行号）、文件存在性
>   - 🟡 **基于会话日志**: 引用来源标注为"基于 09-13 会话日志"的行号（**⚠️ 当前代码已漂移，需重新定位**）
>   - 🔵 **基于推断**: 工作量估计、优先级排序、技术方案描述
>
> **🆕 2026-09-26 合并更新（盲区并入）**: 本节以下的正文为 09-24 基线，**保持原样**（条目一条不删、不放宽）；盲区结论已并入文末 **「2026-09-26 合并更新：盲区结论并入（去重 · 闭环标注 · 困境重排）」**。合并来源：`docs/analysis/blindspot-analysis-0923-0926.md`（t2）· `docs/analysis/blindspot-evidence-0923-0926.md`（t1）。
> **⚠️ 代码状态基准**: Windows 工作区 @ `fbcc3d7`（2026-09-26 12:28:02 +0800），实测时刻 **2026-09-26 12:47 (+0800)**。文末合并节的**所有行号均为该基准下的当前实测值**（复现命令见 §A.7）；凡沿用 09-24 旧口径处一律显式标注。

---

## 目录

- [优先级总览](#优先级总览)
- [P0 阻塞项](#p0-阻塞项)
- [P1 高优先级](#p1-高优先级)
- [P2 中优先级](#p2-中优先级)
- [P3 改进项](#p3-改进项)
- [已知残留项收口计划](#已知残留项收口计划)
- [长期架构方向评估](#长期架构方向评估)
- [执行顺序建议](#执行顺序建议)
- [2026-09-26 合并更新：盲区结论并入（去重 · 闭环标注 · 困境重排）](#2026-09-26-合并更新盲区结论并入去重--闭环标注--困境重排)

---

## 优先级总览

| 优先级 | 行动 | 估计工作量 | 状态 | 涉及文件 |
|--------|------|-----------|------|---------|
| **P0-N1** | Telemetry 魔数提取为命名常量 | 1 小时 | 🆕 新增 | `fly64/fly64/model.py`, `telemetry.py` |
| **P0-N2** | CX-2 锚点积分视觉重定位校正 | 3 天 | 🆕 新增 | `central_complex.py`, `scene_recognition.py` |
| **P0-1** | EVO auto-fix 闭环：记录型→自动执行型 | 2-3 天 | 🔄 已有 | `main.py`, `evolution_skill.py`, `fix_catalog.json` |
| **P0-2** | Mario stuck 模式根治 | 2-3 天 | 🔄 已有 | `memory.py`, `main.py`, `default_patterns.json` |
| **P1-N1** | StuckDetector rate_threshold 单位文档化+断言 | 0.5 天 | 🆕 新增 | `memory.py` |
| **P1-N2** | Steering 优先级链显式实现 | 2 天 | 🆕 新增 | `central_complex.py`, `model.py` |
| **P1-1** | Telemetry 缺口补全（5 字段） | 0.5 天 | 🔄 已有 | `main.py`, `telemetry.py`, `default_patterns.json` |
| **P1-2** | fallen recovery 修复验证 | 1 天 | 🔄 已有 | `memory.py`, `main.py` |
| **P1-3** | 视觉系统 MVP（4 方向 EMD） | 3-4 天 | 🔄 已有 | `retina.py`, `model.py`, `default_patterns.json` |
| **P2-N1** | control.x 旁路（**10 处** `main.py` 写点 / 生产 14 / 含 tests 16；2026-09-26 实测，替代过时的「22 处」）迁移至 LIF 电流注入 | 3-5 天 | 🔄 修订（口径更正） | `main.py`, `model.py` |
| **P2-N2** | 端到端契约审计测试套件增量 | 2 天 | 🆕 新增 | `tests/test_*_contract.py` |
| **P2-1** | 版本声明对齐 | 0.5 天 | 🔄 已有 | `main.py`, `skills/skills.md` |
| **P2-2** | CX 导航回路完成（CX-2 + CX-3） | 3-5 天 | 🔄 已有 | `central_complex.py`, `model.py`, `memory.py` |
| **P2-3** | EVO 健康度量自动化 | 1-2 天 | 🔄 已有 | `evolution_skill.py`, `evolution_health_trend.jsonl` |
| **P3-N1** | 对话 LLM 策略输出迁移至 LIF 池 | 3-5 天 | 🆕 新增 | `main.py`, `plugin/llm_consult.py` |
| **P3-N2** | 部署脚本体系治理（50+ 脚本统一管理） | 1 天 | 🆕 新增 | `scripts/`, `.tmp/` |
| **P3-1** | 过时文档标记与清理 | 1 天 | 🔄 已有 | `docs/analysis/` |
| **P3-2** | 第二个验证场景搭建 | 5-7 天 | 🔄 已有 | `scripts/`, `fly64/` |

> **2026-09-26 状态增量（详见文末合并节，本表本身不改）**:
> - **`P1-N1` → ✅ 本窗口闭环**（`memory.py` L135 已改为 `0.008` per-tick fraction，L208 比较式带单位注释；改动未入库，见 §A.1）。
> - **`P2-1`（版本声明对齐）→ 升级为 P0**，并入新增困境 A/B（`canonical_versions.skill` = `3.4.2` ≠ `main.py` L50 / `skills.md` L3 的 `3.5.1`）。
> - **`P2-N1` 行内「22 处」为过时口径** → 当前实测 `main.py` **10** 写点 / 生产 **14** / 含 `tests/` **16**（§A.6-C8；t2 的「12」是正则把 `==` 比较计入所致）。
> - 本表实测为 **18 条**（保留 10 + 新增 8），L724 原文的「16 项」漏计 2 条（§A.0-K1）。

---

## P0 阻塞项

### P0-N1: Telemetry 魔数提取为命名常量 🔴

> **来源**: 困境 1（t2 分析第 353-361 行）  
> **分析会话**: session-38542b1c（脑模型能力缺陷审计报告）  
> **所属主题**: 领域 A（🧠 神经系统行为修复与增强）

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | 🟡 MEDIUM — 虽不产生运行时错误，但常量散落导致调参需逐行理解语义，长期必然引入 drift |
| **前置依赖** | 无 |
| **估计工作量** | 1 小时 |

#### 问题描述

`fly64/fly64/model.py` 中存在至少 8 组 magic numbers：

| 魔数 | 出现次数 | 至少语义数 | 示例位置 |
|------|---------|:----------:|---------|
| `0.12` | 8 次 | 4 种 | CX 转向、Target 转向等 |
| `0.15` | 14 次 | 多种 | 电流注入系数、权重因子 |
| `0.20` | 多处 | — | sky_jump 增益等 |
| `0.25` | 多处 | — | restlessness 系数等 |
| `0.35` | 多处 | — | 逃逸相关增益 |

#### 技术方案

```python
# fly64/fly64/model.py — 新增命名常量区（约 20 行）
# ── Telemetry 命名常量 ──
CX_STEERING_GAIN: float = 0.12        # CX 转向电流注入增益
TARGET_TURN_GAIN: float = 0.12        # Target 转向电流注入增益
SKY_JUMP_GAIN: float = 0.20           # 天空跳跃方向增益
RESTLESS_GAIN: float = 0.25           # Restlessness 行为增益
ESCAPE_BURST_GAIN: float = 0.35       # 逃逸突发增益
# ... 其余类推
```

**步骤**:
1. 逐行扫描 `model.py` 识别所有硬编码浮点常量（20+ 处）
2. 按语义分组映射为命名类常量
3. 替换所有引用
4. 添加注释说明物理含义与单位

> **注意**: 纯重构，不改变运行时行为。需关注扩散到 `test_*.py` 中的同值魔数。

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `fly64/fly64/model.py` | ~20 行常量声明 + 替换 20+ 处引用 | 核心改动 |
| `fly64/fly64/telemetry.py`（如存在） | 少量 | 若 telemetry keys 也含魔数 |

---

### P0-N2: CX-2 锚点积分漂移 — 视觉重定位校正 🔴

> **来源**: 困境 2（t2 分析第 363-371 行）  
> **分析会话**: session-38542b1c  
> **所属主题**: 领域 A1（Central Complex 导航）

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | 🔴 HIGH — 60 秒后方向失效 37.5%（导航基本不可用） |
| **前置依赖** | 无（与 P2-2 CX 导航回路完成互补，但不阻塞） |
| **估计工作量** | 3 天 |

#### 问题描述

`central_complex.py` 的 `_self_motion_update()` 使用 heading_rate 开环积分，**无视觉闭环校正**。推导：

- heading_rate 误差 ~0.05 rad/s
- 60 秒后漂移 3000u（SM64 世界 ~8000u → 37.5%）
- 30 秒后开始明显偏离

#### 技术方案

实现视觉重定位校正，核心链路：

```
场景帧 → scene_recognition (场景标签 + 方位估计)
  → 匹配已知场景锚点 (SpatialMemoryMap)
  → 估计 heading 偏差 δ_heading
  → 校正 CX 罗盘 bump_center (epg_bump)
↓
central_complex.py:
  _self_motion_update() 后插入：
  if scene_match := scene_recognition.match_current_scene():
      δ_heading = scene_match.expected_heading - epg_angle
      self.epg_bump = self.epg_bump.roll(-int(δ_heading / COLUMN_ANGLE))
```

**步骤**:
1. **场景识别增强**（`scene_recognition.py`，1 天）：当前场景识别返回标签 + 置信度；需增加方位估计输出（当前帧 → 估计的全局罗盘方位）
2. **锚点记忆**（`memory.py` SpatialMemoryMap，0.5 天）：已有所见场景的地标锚点；需扩展存储每个场景的参考 heading
3. **重定位校正器**（`central_complex.py`，1 天）：实现上述校正链路
4. **集成测试**（`tests/test_cx_visual_relocation.py`，0.5 天）

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `fly64/fly64/central_complex.py` | ~30 行 | 插入重定位校正逻辑 |
| `fly64/fly64/scene_recognition.py` | ~40 行 | 增加方位估计输出 |
| `fly64/fly64/memory.py` | ~20 行 | 锚点扩展 |
| `tests/test_cx_visual_relocation.py` | ~80 行 | 集成测试 |

---

### P0-1: EVO auto-fix 闭环（已有计划保留）

> 来自原执行计划，详见 `session_logs_execution_plan.md` P0-1 节  
> 工作量: 2-3 天 | 状态: 🔄 待执行 | 关键文件: `skills/fix_executor.py`（新增）

**保留理由**: 此问题不依赖 t2 的新发现，但仍是 EVO 闭环的核心阻塞项。

---

### P0-2: Mario stuck 模式根治（已有计划保留）

> 来自原执行计划，详见 `session_logs_execution_plan.md` P0-2 节  
> 工作量: 2-3 天 | 状态: 🔄 待执行 | 关键文件: `memory.py`, `main.py`

**保留理由**: 与 P0-N1/P0-N2 正交，独立阻塞项。

---

## P1 高优先级

### P1-N1: StuckDetector rate_threshold 单位文档化 + 运行时断言 🟡

> ### ✅ **本窗口闭环（2026-09-26 复核确认）**
> 完成时间：**本窗口内（≥09-23）**；**具体提交时间不可定位**——该改动属 37 个「已跟踪未提交」文件之一（`memory.py` 处于 ` M` 状态），见 §A.1 与 §A.2-N04。
> 落地证据（**当前实测**）：`memory.py` L135 `rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`；L208 比较式已带显式单位注释（per-tick fraction ∈ [0,1]，见 RULE-19）；L142 `self.rate_threshold = rate_threshold`。依据 t2 §4.1-A3 / §4.4-C1（该结论与 09-24 交付的「单位混淆风险仍存在」冲突，已更正）。
> ⚠️ 遗留一点需复验：我 2026-09-26 12:47 活体单点采样 `memory.json.stuck_score = 1.0`（t2 在 12:37 采样为 0.08）——**单点不可当趋势**，若持续为 1.0 则 B3「构造伪影已消除」需撤回（见 §A.3-B3）。
> 本节以下 09-24 原文**保留为历史记录**（其行号 `L135` 当时的值为 `5.0`，现已改为 `0.008`）。

> **来源**: 困境 3（t2 分析第 373-383 行）  
> **分析会话**: session-90dd512b, session-38542b1c  
> **代码位置**: `fly64/fly64/memory.py` L135-L143 (`StuckDetector.__init__`)

| 属性 | 值 |
|------|-----|
| **优先级** | P1 — 高 |
| **风险** | 🟡 MEDIUM — 若单位混淆，不同帧率下可能产生误判 |
| **前置依赖** | 无 |
| **估计工作量** | 0.5 天 |

#### 问题描述

```python
# memory.py L135
rate_threshold: float = 5.0  # 标注为"Hz"
```

但 `forward_rate` 的物理含义存在歧义：是"动作频率"还是"位移速率"？
- 测试 `test_memory.py` 中使用 `rate_threshold=5.0` vs `rate_stuck_s=3.0`（不同单位假设）
- 无运行时断言验证量级范围

#### 技术方案

```python
# memory.py — StuckDetector
def __init__(self, rate_threshold: float = 5.0, ...):
    # 明确单位注释
    """rate_threshold: 动作频率阈值 (Hz)，forward_rate < 此值持续 rate_stuck_s 秒视为 stuck"""
    
def _update_stuck_state(self, forward_rate: float, dt: float):
    # 运行时断言：forward_rate 应在合理范围内
    if self._debug_assert and (forward_rate < 0 or forward_rate > 100):
        logger.warning(f"forward_rate out of expected range: {forward_rate} Hz")
```

**步骤**:
1. 更新文档字符串（L127），明确 `rate_threshold` 的单位是 Hz，物理含义是"动作频率"
2. 添加运行时 `assert` 验证量级范围（0-100 Hz）
3. 统一测试常量命名（`RATE_THRESHOLD_Hz` vs `RATE_STUCK_DURATION_S`）

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `fly64/fly64/memory.py` | ~10 行 | 文档字符串 + 运行时断言 |
| `tests/test_memory.py` | ~5 行 | 常量命名对齐 |

---

### P1-N2: Steering 优先级链显式实现 🟡

> **来源**: 困境 5（t2 分析第 397-405 行）  
> **分析会话**: session-1f8fbe04, session-38542b1c  
> **代码位置**（**2026-09-26 实测**）: `fly64/fly64/central_complex.py` L220-L542（`steering_bias` 定义/写点/复位/镜像）, `fly64/fly64/model.py` L1972-L2190（escape 分支与 cx_bias 镜像）

| 属性 | 值 |
|------|-----|
| **优先级** | P1 — 高 |
| **风险** | 🟡 MEDIUM — 逃逸时方向提交与 CX 导航竞争 steering_bias，可能导致逃逸被打断 |
| **前置依赖** | 无 |
| **估计工作量** | 2 天 |

#### 问题描述

当前 steering_bias 的竞争关系无显式优先级定义：

- `central_complex.py` L220: `self.steering_bias: float = 0.0`（写点 L401、复位 L409/L469、镜像 L542）
- 实际 steering 竞争体现在 `model.py` L1972 / L2015 / L2141（`escape_mode` 分支）与 L2154（`cx.update(...)` 产出 `cx_bias`）、L2182-L2185（`cx_bias` 镜像用于 reflex turn mix）
- ⚠️ **2026-09-26 复核**: 本节此前引用的 `central_complex.py` L210、`model.py` L1941-1953 / L2094-2095 / L2098 均为 **09-24 旧口径，现行代码已漂移**（`central_complex.py` L210 现为 P1-b5 `loop_score` 注释）⇒ **实施时必须按符号检索，不得沿用旧行号**
- 在 `escape_mode` 下，方向提交机制与 CX 新颖性引导可能产生相反偏置
- 无仲裁逻辑 → 实际行为不确定

#### 技术方案

明确定义并实现 Steering 优先级链：

```
优先级链（高→低）:
  Reflex (本能反射) > Escape (逃逸方向) > CX Exploration (探索) > Default (默认前行)

实现:
  steering_bias = 0.0
  if reflex_active:          steering_bias = reflex_bias       # 最高优先级
  elif escape_mode_active:   steering_bias = escape_bias       # 逃逸方向坚持
  elif cx_explore_active:    steering_bias = cx_novelty_bias   # CX 新颖性引导
  else:                      steering_bias = default_bias      # 默认前行
```

**步骤**:
1. 提取当前所有 steering_bias 赋值点（`central_complex.py`, `model.py`），识别各处的语义角色
2. 在 `central_complex.py` 中创建 `SteeringArbiter` 类，实现优先级仲裁逻辑
3. 将所有 steering_bias 写入点改为向 arbiter 注册信号
4. 在 `model.py` 中替换直接 steering_bias 赋值为通过 arbiter 输出
5. 添加单元测试验证抢占行为

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `fly64/fly64/central_complex.py` | ~60 行 | 新增 `SteeringArbiter` 类 |
| `fly64/fly64/model.py` | ~30 行 | 替换直接 steering_bias 写入 |
| `tests/test_steering_arbiter.py` | ~100 行 | 优先级抢占测试 |

---

### P1-1: Telemetry 缺口补全（已有计划保留）

> 工作量: 0.5 天 | 状态: 🔄 待执行 | **前置依赖**: 无

**保留理由**: 5 个缺失字段导致 3 条 pattern 失效。仍为高优先级。

---

### P1-2: fallen recovery 修复验证（已有计划保留）

> 工作量: 1 天 | **前置依赖**: P1-1（telemetry）

**保留理由**: R31-fix7 部署后需确认极端场景有效性。

---

### P1-3: 视觉系统 MVP（4 方向 EMD）（已有计划保留）

> 工作量: 3-4 天 | 状态: 🔄 待执行

**保留理由**: 视觉覆盖度仅 ~38%，EMD 可提升至 ~50%。

---

## P2 中优先级

### P2-N1: control.x 旁路迁移至 LIF 电流注入 🟡

> **来源**: 困境 4（t2 分析第 386-394 行）  
> **分析会话**: session-38542b1c, session-1f8fbe04  
> **代码位置**（**2026-09-26 实测**；下方「基于会话日志」一行为 09-13 历史留档，**不得当作现行行号**）:
>   - ⚠️ **基于会话日志（09-13 版本，已过时）**: `fly64/fly64/main.py` L939-940, L956-958, L1011-1013, L1168-1179, L1191-1199, L1206, L1220-1229
>   - 🟢 **当前实测（10 处写点，正则 `control\.x\s*=(?!=)`）**: `main.py` L760(reflex flex), L2060(escape_dir), L2077(cliff_turn), L2141(LLM policy), L2190-L2192(escape_burst), L2406+L2414(test modes), L2466+L2492(nav)

| 属性 | 值 |
|------|-----|
| **优先级** | P2 — 中 |
| **风险** | 🟡 MEDIUM — 神经决策可被 Python 层无条件覆盖，破坏闭环学习完整性 |
| **前置依赖** | 无 |
| **估计工作量** | 3-5 天 |

#### 问题描述

> **勘误（M3+M4, 2026-09-24；**2026-09-26 复核更新**）**: 原始版本引用的 **22 处** 计数与 **6+11+6** 分类来自历史文档 `docs/analysis/insurance/remaining-issues-analysis.md`（基于 09-13 版本的 main.py）。该文档以"逻辑 bypass 场景"分类：Reflex 控制 6 处（旧 L939-1013）、对话 LLM 11 处（旧 L1168-1206）、坠落恢复 6 处（旧 L1220-1229）。
> 
> **当前代码实测**（**2026-09-26 12:47**，Windows 工作区 @ `fbcc3d7`；正则须排除 `==` 比较，即 `control\.x\s*=(?!=)`）：
> - main.py 写点（赋值）: **10 处**（`main.py` L760 reflex / L2060+L2141 escape+LLM policy / L2077 cliff / L2190-L2192 escape_burst / L2406+L2414 test modes / L2466+L2492 nav）
> - 全仓生产写点: **14 处**（含 `motor_primitives.py` 1 + `evolution_agent.py` 1 + `fix_template_interpreter.py` 2）
> - 含 `tests/`: **16 处**
> - control.x 引用出现次数: main.py **32 次**
> - ⚠️ **口径告警（t3 复核新增）**: 若用朴素正则 `control\.x\s*=`，会把 `main.py` L2618、L2959 两处 **`control.x == 0` 比较**计入，得到 **12 / 16 / 18**。t2 报告的「10→12（恶化）」即由此产生；**HEAD 与工作区实测均为 10 处，窗口内 diff 未新增任何写点 ⇒ A4 未恶化**（见文末 §A.6-C8）。
> - 由于代码重构，原 6+11+6 分类中有 17 处旧行号已不再对应 `control.x` 字面赋值。本节以下的"22 处"引用已更新为当前实测 **10 处写点**（main.py），并注明"写点（赋值）"口径。

当前代码中直接 `control.x` 写入的 Python 旁路（**写点**，即 `control\.x\s*=(?!=)` 赋值；**注意排除 `control.x == 0` 比较**）分为以下类别：

| 类别 | 数量（当前实测） | 风险等级 |
|------|:----------------:|:--------:|
| **Reflex/本能** | 1 处 (L760) | 🟢 低风险 — reflex 电流融合，可视为有意保留 |
| **Escape/Fallen 急救** | 4 处 (L2060, L2077, L2190, L2192) | 🟡 中风险 — 应急场景可接受但应有限 |
| **对话 LLM 策略** | 1 处 (L2141) | 🔴 高风险 — LLM 输出跳过整个神经决策链 |
| **导航/测试模式** | 4 处 (L2406, L2414, L2466, L2492) | 🟡 中风险 — 调试/测试场景可接受但应标记 |

#### 技术方案

分两阶段执行（仅第一阶段在 P2 范围）：

**Phase 1（P2-N1，3 天）**: Escape + fallen + nav 旁路（行号为 2026-09-26 实测）
- Escape/Fallen 4 处（L2060/L2077/L2190/L2192）：改为注入 escape LIF 电流 → 神经决策链接管
- Nav 2 处（L2466/L2492）：设为 CX steering_bias 到 LIF 池
- 测试模式 2 处（L2406/L2414）：标记为 test-only 并加上 `__debug__` 保护
- Reflex 1 处（L760）：保留 — 属有意设计（reflex 电流融合）
- 保留应急降级（安全网）：若 LIF 注入后 1.5s 仍无响应，fallback 到直接写入

**Phase 2（P3-N1，移入 P3）**: 对话 LLM 策略迁移（另见 P3-N1）

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `fly64/fly64/main.py` | ~80 行 | 10 处旁路改为 LIF 注入（基于当前代码实测） |
| `fly64/fly64/model.py` | ~30 行 | 添加 Reflex/LIF 竞争逻辑 |
| `tests/test_control_bypass.py` | ~80 行 | 回归测试 |

---

### P2-N2: 端到端契约审计测试套件增量

> **来源**: t2 分析第 12 个"机制存在、报告成功、无法生效"模式案例的改进建议  
> **所属主题**: 领域 E（系统诊断）

| 属性 | 值 |
|------|-----|
| **优先级** | P2 — 中 |
| **风险** | 🟢 LOW — 契约审计门禁（ZT-1/3/5）已由 `fly64-comprehensive-fix` 实现 |
| **前置依赖** | 无 |
| **估计工作量** | 2 天 |

#### 问题描述

契约审计制度化（P1-G4 已完成）建立了 `contract_registry.json` 和 `contract_gate.py` CI 门禁，但：
- 当前契约注册表仅 4 项契约（18-80+ 字段）
- 尚未覆盖 t2 分析识别的 12 个"死机制"模式中的多数

#### 技术方案

为以下模式新增契约测试（参考 `test_coach_contract.py` 写法）：

| 模式实例 | 契约测试重点 |
|---------|-------------|
| 逃逸位移 > 0 | 方向提交 → control.x ≠ 0 断言 |
| StuckDetector fallen 衰减 | fallen 信号应在 3s 内衰减到 < 0.5 |
| Loop score 不饱和 | spin loop 检测 → score 在 60s 内 |
| 策略穿透 | Coach steering_bias → control.x 关联 |
| CX steering_bias 竞争 | escape 模式下 CX bias 被抑制 |

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `contract_registry.json` | ~40 行 | 新增 5 项契约注册 |
| `tests/test_stuck_contract.py` | ~100 行 | StuckDetector 契约 |
| `tests/test_escape_contract.py` | ~80 行 | 逃逸契约 |
| `tests/test_steering_contract.py` | ~80 行 | Steering 竞争契约 |
| `tests/test_coach_contract.py` | ~50 行 | 已有扩展 |

---

### P2-1: 版本声明对齐（已有计划保留）

> 工作量: 0.5 天

**保留理由**: 4 处版本不一致仍需对齐。

---

### P2-2: CX 导航回路完成（CX-2 + CX-3）（已有计划保留）

> 工作量: 3-5 天

**保留理由**: 与 P0-N2（视觉重定位校正）互补但不同。P0-N2 解决漂移问题，P2-2 实现完整的锚点积分与目标竞争。

---

### P2-3: EVO 健康度量自动化（已有计划保留）

> 工作量: 1-2 天 | **前置依赖**: P0-1

**保留理由**: `evolution_health_trend.jsonl` 仅 1 行数据。

---

## P3 改进项

### P3-N1: 对话 LLM 策略输出迁移至 LIF 池

> **来源**: 困境 4 的第二阶段（t2 分析第 391-393 行）

| 属性 | 值 |
|------|-----|
| **优先级** | P3 — 改进 |
| **风险** | 🟢 LOW — LLM 策略当前可正常运行 |
| **前置依赖** | P2-N1（Reflex/坠落完成迁移）|
| **估计工作量** | 3-5 天 |

#### 技术方案

当前对话 LLM 的旁路（**当前实测仅 L2141 1 处** `action["control_x"]`；09-24 口径为 L2029）是架构性最严重的问题。迁移策略：

1. 在 `model.py` 中新增 `LIF_PolicyPool`（~50 行），接收来自 Coach/LLM 的策略输入
2. 修改 `llm_consult.py` 输出格式：从 `control.x = ...` 改为 `policy_pool.submit("llm", steering_bias, duration)`
3. 在 `main.py` 主循环中添加 `policy_pool.resolve()` 调用，将 LIF 池中的策略注入神经决策链
4. 保留降级：若 LLM 策略未产生有效输出（超时），fallback 到 CX 自主导航

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `fly64/fly64/model.py` | ~50 行 | LIF_PolicyPool 类 |
| `fly64/plugin/llm_consult.py` | ~30 行 | 输出格式改造 |
| `fly64/fly64/main.py` | ~20 行 | 主循环集成 |
| `tests/test_policy_pool.py` | ~80 行 | 测试 |

---

### P3-N2: 部署脚本体系治理

> **来源**: t2 分析第 149-153 行（领域 C3 — 部署脚本体系）

| 属性 | 值 |
|------|-----|
| **优先级** | P3 — 改进 |
| **风险** | 🟢 LOW — 不影响运行 |
| **前置依赖** | 无 |
| **估计工作量** | 1 天 |

#### 问题描述

`scripts/` 和 `.tmp/` 目录下 50+ 个脚本（fixN_deploy_restart.sh / ver_append_fixN.py / mN_deploy_restart.sh），缺乏统一治理：

- 版本命名混乱（fixN / mN / ver_append 各有体系）
- 重复逻辑（部署重启脚本大量重复）
- 临时脚本（`.tmp/`）未清理

#### 技术方案

1. 整理 `scripts/` 目录：分类为 `deploy/`, `diagnostics/`, `monitoring/` 子目录
2. 合并重复的部署重启逻辑为统一 `deploy.sh`（带参数）
3. 清理 `.tmp/` 中已经过时的诊断脚本
4. 添加 `scripts/README.md` 说明各脚本用途

#### 涉及文件

| 文件 | 改动量 | 说明 |
|------|:------:|------|
| `scripts/` 目录 | 50+ 文件 | 重分类 + 合并 |
| `scripts/README.md` | ~30 行 | 新增目录说明 |
| `.tmp/` 目录 | 清理 ~20 个临时文件 | 删除过时诊断脚本 |

---

### P3-1: 过时文档标记与清理（已有计划保留）

> 工作量: 1 天

**保留理由**: `docs/analysis/` 下大量文档需标记状态。

---

### P3-2: 第二个验证场景搭建（已有计划保留）

> 工作量: 5-7 天 | **前置依赖**: P1-3（视觉 MVP）

**保留理由**: SM64 单一场景仍是泛化能力的根本瓶颈。

---

## 已知残留项收口计划

以下 3 个残留项来自 t2 分析的"当前困境清单"，分别在 P0/P1/P2 已有覆盖：

### R1: Telemetry 魔数常量化 🔴 → P0-N1
| 维度 | 值 |
|------|-----|
| **收口目标** | 抽取 8+ 组魔数为命名常量 |
| **方案** | `model.py` 新增常量区，替换所有引用 |
| **验收标准** | 代码中无裸浮点常量；常量命名含物理单位 |
| **预计工时** | 1 小时 |
| **涉及文件** | `fly64/fly64/model.py` |

### R2: StuckDetector rate 单位 🟡 → P1-N1
| 维度 | 值 |
|------|-----|
| **收口目标** | 明确 `forward_rate`（Hz）语义 + 运行时范围断言 |
| **方案** | 更新 docstring + 添加 `0 < rate < 100` 断言 |
| **验收标准** | 文档字符串标明单位；单元测试覆盖边界值 |
| **预计工时** | 0.5 天 |
| **涉及文件** | `fly64/fly64/memory.py` |

### R3: Steering budget 优先序 🟡 → P1-N2
| 维度 | 值 |
|------|-----|
| **收口目标** | 实现显式 Steering 优先级链 |
| **方案** | 新增 `SteeringArbiter` 类，优先级: Reflex > Escape > CX > Default |
| **验收标准** | 优先级测试通过；escape 模式 steering_bias 不被 CX 覆盖 |
| **预计工时** | 2 天 |
| **涉及文件** | `fly64/fly64/central_complex.py` |

---

## 长期架构方向评估

### 方向 1: 二期门禁推进条件

> **条件评估**: 当前不宜启动二期门禁

**理由**:
- 契约审计门禁（ZT-1/3/5）已由 `fly64-comprehensive-fix` 交付
- 但当前 P0 阻塞项（CX-2 漂移、EVO auto-fix）尚未解决
- "机制存在、报告成功、无法生效"模式仍然活跃（5 个困境中有 3 个归于此模式）
- **建议**: 待 P0-N2（CX-2 视觉重定位）+ P0-1（EVO auto-fix）+ P0-2（stuck 根治）均完成后，再评估门禁二期

**触发条件**:
1. P0 阻塞项清零
2. 契约注册表从 4 项扩展至 10+ 项（见 P2-N2）
3. 连续 1 周无新的"死机制"报告

### 方向 2: CX 导航完成状态

> **状态评估**: ~40% 完成

**已完成**:
- ✅ CX-1 罗盘自主化（v2.13.0）
- ✅ CX 16-列环形吸引子实现
- ✅ steering_bias 复位修复（P0 已修复）
- ✅ goal_competition 重构

**待完成**:
- ❌ CX-2 锚点路径积分（P2-2，~50% 已有 code）
- ❌ CX-2 视觉重定位校正（P0-N2，纯新增）
- ❌ CX-3 多源目标向量竞争（P2-2，~40% 已有 code）
- ❌ 垂直维度(Y) 3D 网格扩展（未规划）

**建议优先级**: P0-N2（视觉重定位）→ P2-2（锚点积分+目标竞争）→ 垂直维度（P3 后）

### 方向 3: 视觉 MVP 启动评估

> **条件评估**: 已具备启动条件

**有利条件**:
- 视网膜处理已在 `retina.py` 实现（场景识别 + optic_flow）
- 4 方向 EMD 设计方案已在 `docs/emd_4direction_design.md` 完成
- 仪表板已有视觉面板预留位

**风险**:
- 视觉增量依赖 P0 阻塞项不受影响：EMD 实现是独立的 `retina.py` 增强
- 但集成验证（视觉→LIF 驱动→控制）需 `model.py` 稳定

**建议**: 可在 P0-N1（1 小时重构）完成后立即启动 P1-3（EMD MVP），与 P0-N2（CX 视觉校正）并行。两者使用不同的视觉通道（EMD 用亮度差分 → 运动；场景识别用特征匹配 → 方位）。

### 方向 4: 多场景验证

> **条件评估**: 依赖视觉 MVP 完成

P3-2（第二验证场景）不应早于 P1-3（视觉 MVP）。因为多场景验证需要视觉感知能力支持导航泛化。

### 方向 5: "死机制"模式改善路径

> 这是最值得关注的持续性风险

**当前状态**: 12 个案例 → 8 个已修复，4 个部分修复（逃逸位移、策略穿透仍在）

**建议演化路径**:
1. **短期**（P1-N1, P1-N2）: 消除还在活跃的 3 个困境（rate 单位、steering 优先级）
2. **中期**（P2-N2）: 扩展契约审计注册表覆盖剩余模式
3. **长期**: 在 CI 中增加"契约覆盖率"门禁（CI 契约覆盖所有模块）

---

## 执行顺序建议

### 依赖关系图

```
P0-N1 (魔数常量)     ← 无前置，独立
P0-N2 (CX-2 视觉校正) ← 无前置，独立
P0-1 (EVO auto-fix)  ← 无前置
P0-2 (stuck 根治)     ← 依赖 P0-1

P1-N1 (StuckDetector) ← 无前置，可独立执行
P1-N2 (Steering 仲裁) ← 无前置，可独立执行
P1-1 (telemetry 补全) ← 无前置，可独立执行
P1-2 (fallen)         ← 依赖 P1-1
P1-3 (视觉 MVP)       ← 无前置，可独立执行

P2-N1 (control.x 迁移) ← 无前置，但建议在 P1-N2 后（Steering 仲裁先确定）
P2-N2 (契约扩展)       ← 无前置，可并行
P2-1 (版本对齐)        ← 无前置，0.5 天
P2-2 (CX 导航完成)     ← 建议在 P0-N2 后（先解决漂移再实现完整导航）
P2-3 (EVO 度量)        ← 依赖 P0-1

P3-N1 (LLM→LIF)       ← 依赖 P2-N1
P3-N2 (脚本治理)       ← 无前置
P3-1 (文档清理)        ← 无前置
P3-2 (第二场景)        ← 依赖 P1-3
```

### 第一波：独立先行（可高度并行）

```
Day 1 (并行):
  ├── P0-N1 (魔数常量化)     0.5h  ← 纯重构，15 分钟即可完成
  ├── P1-N1 (StuckDetector)  0.5天 ← 文档+断言，0.5 天
  ├── P1-1 (telemetry 补全)  0.5天 ← 5 字段暴露
  ├── P1-3 (视觉 MVP)        3-4天 ← 独立长任务
  ├── P2-1 (版本对齐)        0.5天 ← 简单对齐
  ├── P2-N2 (契约扩展)       2天   ← 独立
  ├── P3-N2 (脚本治理)       1天   ← 独立
  └── P3-1 (文档清理)        1天   ← 独立
```

### 第二波：就绪后

```
Day 2-4:
  ├── P0-1 (EVO auto-fix)    2-3天  ← 最关键，优先启动
  ├── P0-N2 (CX 视觉校正)    3天    ← 与 P0-1 并行
  ├── P1-N2 (Steering 仲裁)  2天    ← 与上面并行
  └── P1-2 (fallen)          1天    ← 依赖 P1-1
```

### 第三波：依赖就绪后

```
Day 4-7:
  ├── P0-2 (stuck 根治)      2-3天  ← 依赖 P0-1
  ├── P2-N1 (control.x 迁移) 3-5天  ← 建议在 P1-N2 后
  ├── P2-2 (CX 导航完成)     3-5天  ← 建议在 P0-N2 后
  └── P2-3 (EVO 度量)        1-2天  ← 依赖 P0-1
```

### 第四波：收尾

```
Day 7-10:
  ├── P3-N1 (LLM→LIF)        3-5天  ← 依赖 P2-N1
  └── P3-2 (第二场景)        5-7天  ← 依赖 P1-3
```

### 工作量估算

| 波次 | 时间 | 并行人数 | 说明 |
|------|------|:--------:|------|
| 第一波（独立先行） | 1 天 | 3-5 | 8 个无依赖项可高度并行 |
| 第二波（核心修复） | 3 天 | 3 | P0-1 + P0-N2 + P1-N2 + P1-2 |
| 第三波（依赖就绪） | 3 天 | 2-3 | P0-2 + P2-N1 + P2-2 + P2-3 |
| 第四波（收尾） | 3 天 | 1-2 | P3-N1 + P3-2 |
| **合计（较原计划新增）** | **~10 天** | **2-4** | **保留 10 项 + 新增 8 项 = 18 项**（09-24 原文误记为「新增 6 项…= 16 项」；漏计 `P2-N2`、`P3-N1`，见 §A.0-K1） |
| **原计划合计** | **~7-8 天** | **2-3** | **原 10 项（不含治理修复）** |

> **增量说明**: 新增 8 项中（原表仅列 6 项，**漏计 `P2-N2`、`P3-N1`** —— 这正是「16 项」口径误差的来源，见 §A.0-K1），P0-N1（1h）、P1-N1（0.5天）、P3-N2（1天）为轻量任务，P0-N2（3天）+ P1-N2（2天）+ P2-N1（3-5天）+ P2-N2（2天）+ P3-N1（3-5天）为主要增量。

---

> **生成**: 2026-09-24 · 基于 t2 综合分析 + t1 摘要（剔除失真工具计数）  
> **数据来源**: 12 个 DSH 会话日志、462 行综合报告、12 个模式案例、5 个当前困境  
> **取代关系**: 本文件是 `session_logs_execution_plan.md` 的补充建议档，两者合并使用  
> **保存位置**: `docs/analysis/session-log-recommendations.md`

---

# 2026-09-26 合并更新：盲区结论并入（去重 · 闭环标注 · 困境重排）

> **合并人**: `strategist`（AgentTeams `fly64-blindspot-0923-0926` / task `t3`）
> **合并来源**: `docs/analysis/blindspot-analysis-0923-0926.md`（t2，328 行，未修改）· `docs/analysis/blindspot-evidence-0923-0926.md`（t1，469 行，未修改）
> **代码状态基准**: Windows 工作区 @ `fbcc3d7`（2026-09-26 12:28:02 +0800）；**实测时刻 2026-09-26 12:47 (+0800)**
> **行号纪律**: 本节所有 `` `file` Lnnn `` 引用均按该基准**重新实测**（复现命令见 §A.7）；凡属 09-24 旧口径者一律显式标注「旧口径」并保留原文。
> **不可删除原则**: 本合并**不移除、不放宽**任何既有条目；已闭环项仅追加「✅ 本窗口闭环」标注与完成时间。

## A.0 基线校正（先声明，再合并）

| # | 项 | 旧口径 | 本次实测 | 处置 |
|:-:|---|---|---|---|
| **K1** | 既有建议条目数 | 正文 L724 **原文**「新增 6 项 + 保留原 10 项 = **16 项**」（已就地更正为 18 条） | 优先级总览 L35–L52 实为 **18 条**（保留 10 + 新增 8）；L727 的增量说明只列了 6 项 ⇒ 漏计 `P2-N2`、`P3-N1` | 以 **18 条为基线**；任务书所称「16 项」按 18 条处理；**一条不删** |
| **K2** | `control.x` 写点 | 摘要表原文「**22 处**」→ 09-24 实测 10 处 → t2「10→**12**（恶化）」 | `` `main.py` L760 `` 起共 **10** 处赋值；生产口径 **14**；含 `tests/` **16**。**必须排除 `==` 比较**：`control\.x\s*=(?!=)`。t2 的朴素正则把 `` `main.py` L2618 ``、`` `main.py` L2959 `` 两处 `control.x == 0` 计入 ⇒ 得 12/16/18 | 全文统一为 **10 / 14 / 16**；见 §A.6-C8 |

## A.1 既有 18 项逐条标注（去重结果，无静默移除）

| 编号 | 行动（保持原文语义） | 本次标注 | 完成时间 / 现状（2026-09-26 实测） | 依据 |
|---|---|---|---|---|
| **P0-N1** | Telemetry 魔数提取为命名常量 | **保留 → 修订**（补范围限定） | 仍存在：`` `model.py` `` 中 `0.12`×7 / `0.15`×20；模块级命名常量仅 1 个（`FWD_RATIO_FLOOR`）⇒ 窗口把工作量投在 gate 单位契约与信用分配矩阵上，**常量抽取未发生** | t2 §4.1-A1、§4.4-C6 |
| **P0-N2** | CX-2 锚点积分视觉重定位校正 | **修订（结论更正，降级 P0→P1）** | 机制**已存在**：`` `central_complex.py` L128 `` `relocalize()`（gate 0.8 / strength 0.3），调用点 `` `central_complex.py` L529 ``、`` `central_complex.py` L673 ``，测试 `` `test_cx_navigation.py` L174 ``–`` L204 ``；**活体命中率未验证** | t2 §4.1-A2、§4.4-C2、§6.3-U5 |
| **P0-1** | EVO auto-fix 闭环：记录型→自动执行型 | **修订（部分完成，未闭环）** | 25-P0-2（可执行 fix，`` `fix_executor.py` `` 未跟踪）与 25-P0-4（`has_fix` 有界重试）已实现并验收，但①**不在 HEAD** ②**不在活体** ③**记录未补** | t2 §3.2-E4/E9、§4.2-B1；`38c8bae` 提交信息自述 |
| **P0-2** | Mario stuck 模式根治 | **修订（部分完成，未闭环）** | 同上；载体 `evolution_skill.py`（+2485/−70）仍滞留工作区，另一 DSH 会话在途 | 同上 |
| **P1-N1** | StuckDetector rate_threshold 单位文档化 + 断言 | ✅ **本窗口闭环** | 完成时间：**本窗口内（≥09-23）**；**具体提交时间不可定位**（改动属 37 个已跟踪未提交文件之一，`` `memory.py` `` 处于 ` M` 状态）。证据：`` `memory.py` L135 `` `rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`；`` `memory.py` L208 `` 比较式带 per-tick 单位注释 | t2 §4.1-A3、§4.4-C1（与 09-24 结论冲突，已更正） |
| **P1-N2** | Steering 优先级链显式实现 | **保留（并标注路线阻塞）** | 仍存在：`` `memory.py` L1541 `` `_vote(...)` 仍是唯一判定函数，**无** `ArbitrationState`；其 P2-c1 路线被 H13 裁定阻塞 | t2 §4.1-A5；`w1-w4-closeout-and-h13-verdict.md`（未跟踪） |
| **P1-1** | Telemetry 缺口补全（5 字段） | **保留（并裁定编号冲突，见 §A.4）** | 窗口无证据表明 5 字段已补（属 t1「本窗口无证据主题」）；⚠️ 与 09-23 交付线的 `P1-1(clamp)` **同号不同事项** | t1 §8；§A.4 |
| **P1-2** | fallen recovery 修复验证 | **保留** | 行为证据仍不足：`jump 0→12/600` 为部署报告自述，t2 30 次稀疏采样 0 命中，无法独立复核 | t2 §5-R5、§6.3-U2/U3 |
| **P1-3** | 视觉系统 MVP（4 方向 EMD） | **保留** | 窗口内无提交触及 `retina.py` 的 EMD 实现 | t1 §8 |
| **P2-N1** | control.x 旁路迁移至 LIF 电流注入 | **修订（数字更正 22→10；恶化结论撤回）** | 当前实测 `` `main.py` `` **10** 写点 / 生产 **14** / 含 `tests/` **16**；**HEAD 与工作区写点数相同**，窗口 diff 未新增写点 ⇒ **A4 未恶化** | §A.6-C8；t2 §4.1-A4（数字更正） |
| **P2-N2** | 端到端契约审计测试套件增量 | **修订（升级 P2→P1）** | 窗口新增 3 例同型：守卫空壳（E2）、生产者删键+夹具补键（E7）、验收信号从未存在（E8）⇒ 契约注册表仍未覆盖，且「契约审计」自身存在盲点 | t2 §3.2-E2/E7/E8、§4.4-C4 |
| **P2-1** | 版本声明对齐 | **修订（升级 P2→P0，并入新增困境 A/B）** | 仍不一致：`` `main.py` L49 `` `BRAIN_VERSION = "2.24.0"` / `` `main.py` L50 `` `SKILL_VERSION = "3.5.1"`；`` `skills.md` L3 ``、`` `skills.md` L70 `` 均 3.5.1；`evolution_history.json` 的 `canonical_versions` = `{"brain": "2.24.0", "skill": "3.4.2", "as_of": "2026-09-24T18:00:00+08:00"}` ⇒ **skill 落后一版** | t2 §3.2-E3、§4.3-N1 |
| **P2-2** | CX 导航回路完成（CX-2 + CX-3） | **修订** | CX-2 视觉重定位部分已存在（同 P0-N2）；CX-3 与 c1 仲裁被 H13 阻塞 | t2 §4.1-A2/A5 |
| **P2-3** | EVO 健康度量自动化 | **修订（部分完成）** | 25-P0-3 已交付 `` `evo_liveness_guard.py` ``（**407 行** / 15,863 B）+ `` `evo_loop_launcher.sh` ``（**211 行** / 7,889 B），4/4 验收通过（⚠️ **t7 更正**：原写 339 行 / 179 行 —— 来自 PowerShell `Measure-Object -Line` 的漏计口径，已废弃；`wc -l` 与 `git show --stat` 新增行数双向印证 407/211）；**但未接调度**，告警器最后一次检查停在 **09-25 21:01:25** ⇒ 度量自动化仍未成立 | t2 §3.2-E1、§4.2-B1；t1 §3.2 |
| **P3-N1** | 对话 LLM 策略输出迁移至 LIF 池 | **保留** | 窗口无证据；依赖 P2-N1；钳位契约未拦住写入方（`requested=0.7` 仍到达） | t2 §3.2-E6、§4.2-B2 |
| **P3-N2** | 部署脚本体系治理（50+ 脚本） | **修订** | 新增缺口：`` `evolution_skill.py` `` 工作区 `97b178298e88` ≠ 活体 `fd1ccd56af24`；部署清单记录的 `f895171ee477` **两侧都不匹配** ⇒ 部署证据链断裂 | t2 §2.3-E9、§4.3-N3 |
| **P3-1** | 过时文档标记与清理 | **保留** | 窗口产出 `docs/analysis/**` 25 份（+2 份盲区文档）；索引中仅 7 份 ⇒ **清理前须先入库** | t2 §2.2、§4.3-N2 |
| **P3-2** | 第二个验证场景搭建 | **保留** | 依赖 P1-3；窗口无证据 | t1 §8 |

**去重结论**: 18 条既有条目**全部保留**，其中 **1 条标记「✅ 本窗口闭环」（P1-N1）**、**10 条标注「修订」**（P0-N1、P0-N2、P0-1、P0-2、P2-N1、P2-N2、P2-1、P2-2、P2-3、P3-N2）、**7 条「保留」**（P1-N2、P1-1、P1-2、P1-3、P3-N1、P3-1、P3-2）；无任何条目被合并删除，无同一事项出现两种编号（编号冲突裁定见 §A.4）。

## A.2 新增建议（B01–B14，全部有盲区证据支撑）

> 新增编号统一使用 **`B` 前缀**，与既有 `P#-N#` 编号空间隔离，避免「同号两事项」。

| 编号 | 优先级 | 工时 | 行动 | 涉及文件（file:line，2026-09-26 实测） | 技术方案 | 证据出处 |
|---|:--:|:--:|---|---|---|---|
| **B01** | **P0** | **1 小时** | EVO 守护接入调度 | `` `evo_liveness_guard.py` ``（**407 行**）· `` `evo_loop_launcher.sh` ``（**211 行**）· WSL crontab | 在 WSL crontab 追加 `*/1 * * * * cd /root/fly64 && python3 scripts/evo_liveness_guard.py --check >> /root/fly64/plugin/evo_guard.log 2>&1`；随后做一次**真实 kill → 自动拉起/告警** red→green 验证；把 `evo_stall_alarm.json.checked_at` 新鲜度纳入 M4-d4 观测 | t2 §3.2-E1、§5-R6；t1 §3.2（crontab 实测仅 2 条） |
| **B02** | **P0** | **0.5 天** | `fly64/tests/check_version.py` 改为真断言 | `` `check_version.py` L1 ``–`` L4 `` · `` `agent.md` L19 `` · `` `agent.md` L88 `` · `` `main.py` L49 ``–`` L50 `` · `evolution_history.json`（`canonical_versions`）· `` `skills.md` L3 `` | 读四处（main.py 两个版本常量 / history canonical / skills.md 版本行 / skill 侧常量）并逐一比对，任一不一致或版本链回退 ⇒ `exit 1`；去掉硬编码 `/root/fly64`，改用 `Path(__file__).resolve().parents[2]`；新增「注入一处不一致必须变红」自测；纳入 CI 与 `--history-check` 路径 | t2 §3.2-E2、§4.3-N1、§5-R2；队长独立复现（WSL `exit 0` 恒过 / Windows `ModuleNotFoundError` exit 1 属**错因**） |
| **B03** | **P0** | **0.5 天** | 恢复 EVO-072/EVO-073 + 对齐版本三元组 | `evolution_history.json` · `` `main.py` L50 `` · `` `skills.md` L3 ``、`` `skills.md` L70 `` | `git show HEAD~1:fly64/skills/evolution_history.json`（**实测 HEAD~1 = 81 条，含 EVO-072/EVO-073，`canonical_versions.skill = 3.5.1`**）取回两条按 `id` 去重追加；canonical `skill` 由 `3.4.2` 对齐为 `3.5.1`；恢复动作本身追加一条 EVO 记录；新增守护「禁止非记录类提交改动 `evolution_history.json`」 | t2 §3.2-E3、§4.3-N1、§5-R1；git 实测（当前 87 条且两条均不存在；`fbcc3d7` numstat 115/39） |
| **B04** | **P1** | **0.5–1 天** | 未入库交付分批收口 | 37 个已跟踪未提交 / 65 个未跟踪项；重点 `evolution_skill.py`、`` `memory.py` ``、`` `central_complex.py` ``、`instinct_bindings.py`、`` `fix_executor.py` `` | 按 `docs/execution/deploy-manifest.md` §4.1「他人 WIP 无法纯净切分」风险分批提交（代码 / 测试 / 文档三类），白名单化路径；每批提交前跑规则 20 门禁；**先提交后清理** | t2 §2.2、§4.3-N2、§5-R3 |
| **B05** | **P1** | **0.5 天** | 跨环境部署一致性门禁（md5 manifest） | `evolution_skill.py`（工作区 `97b178298e88` ≠ 活体 `fd1ccd56af24`）· `autonomy_deploy_restart.sh` · `deploy_evo072.sh` · `docs/execution/deploy-manifest.md` §1/§3.1 | 新增 `verify_deploy_parity.py`：对清单内文件计算工作区/WSL 两侧 md5 并断言一致；09-26 的手工同步（`sm64config.txt`）改为部署脚本产物；清单 md5 与实测不符时报「清单过期」而非静默通过 | t2 §2.3-E9、§4.3-N3 |
| **B06** | **P1** | **0.5 天** | 钳位观测点与归因接线 | `` `main.py` L1316 `` · `` `main.py` L1330 `` · `` `main.py` L3177 `` | ① 把 `` `main.py` L1316 `` 的 WARNING 与 `build_coach_applied` docstring 统一指向**实测端点** `/flow.json["clamped_keys"]`（活体实测：`flow.json` 含该键 ✔ / `memory.json` 不含 ✘）；② 消掉 `source="unknown"`，把本能绑定 promoted 桶接成可识别写入方；③ 复核 `flow.no_progress_gate` 与 `memory.progress_ineffective` 同刻相反 | t2 §3.2-E5/E6、§4.2-B3、§4.4-C5、§6.2-I2/I4 |
| **B07** | **P2** | **1 小时** | 契约消费者侧补测 + 删除夹具补键（E7 收口） | `` `scene_context.py` L234 `` · `` `test_what_i_see_protocol.py` L68 `` · `` `main.py` L3124 ``、`` `main.py` L3127 ``（HEAD 为 `` `main.py` L2957 ``） | 消费者改读 `gate_jump_ratio > gate_jump_threshold_ratio`（或恢复生产者布尔键）；删除测试夹具中自带的 `"gate_jump": False`；新增「生产者键集合 ⊆ 消费者键集合」契约测试 | t2 §3.2-E7、§6.2-I3；我实测 |
| **B08** | **P2** | **2 小时** | 验收清单假绿项收口 | `docs/execution/deploy-manifest.md` §6 | `burst_active` 要么在 `flow.json` 增加发布点、要么从清单删除（实测 `flow.json` 122 键中无该键）；`evo_loop_stale` 要么实现（读 `evo_stall_alarm.json` 暴露 `stale`）要么从 M4-d4 移除（全仓 `.py` 零命中）；清单增加「信号必须有发布点」的静态断言 | t2 §3.2-E8、§4.3-N4；我实测 |
| **B09** | **P2** | **0.5 天** | 引用校验器精度改进（S1/S2） | `` `verify_doc_citations.py` L163 ``–`` L170 `` · `` `verify_doc_citations.py` L222 `` · `docs/analysis/session-log-analysis-review-round2.md` §4.3 | ① `unresolved_count` 在 `` `verify_doc_citations.py` L164 `` 与 `` `verify_doc_citations.py` L170 `` **重复自增** ⇒ 计数膨胀（报 166 条，实际 `L<num>` 88 条），删去其一；② `` `verify_doc_citations.py` L222 `` 用 `content.find(file_rel)`（全文首处）而非当前匹配位置取符号 ⇒ 跨文件假阳性 WARN，改为传入 match 起点；③ 让「计数异常」成为失败而非静默 | t2 §3.2-E12（RC-2 / RC-7） |
| **B10** | **P2** | **0.5 天** | 分析工具链编码与口径纪律 | `session_log_extract.py` · `verify_session_summary.py` · `` `verify_doc_citations.py` `` | 统一 `encoding="utf-8"`（禁止 GBK 读 UTF-8 造成「记录仅 3 条」类误判）；计数类结论强制附口径与正则原文；新增「口径声明缺失即失败」的文档检查 | t2 §3.2-E10/E11；**§A.6-C8（本次新发现的口径漂移）** |
| **B11** | **P2** | **2 小时** | 运维负担轮转 | WSL `/tmp`（**≥134 G，滚动值：13:19 = 135 G / 13:24 = 136 G**）· `/tmp/f64r_traj-*.npz`（3435 个）· 根分区 78% · `evolution_log.jsonl`（200 MB 无轮转） | 对 `f64r_traj-*.npz` 设保留策略（按天数或容量清理）；`evolution_log.jsonl` 按大小轮转 + 归档；纳入定时任务与告警 | t2 §4.2-B5、§4.4-C7；t7 滚动值复核 |
| **B12** | **P1** | **1 天** | 按已定义口径复采 ≥6000 帧验证行为改善 | `docs/execution/deploy-manifest.md` §9 | 按 §9 对照表在同一 `trajectory.html` 上采 ≥6000 帧并落盘；新增累计 jump 计数器（`jump_count`）供遥测长期监督；未复采前**不得声称**运动问题已解决 | t2 §6.3-U2/U3、§5-R5 |
| **B13** | **P2** | **0.5 天** | 双测试根收敛确认 | 根 `tests/` 与 `fly64/tests/` | 跑 `pytest --collect-only -q` 确认是否双收集；若双收集立即收敛单根并重算规则 20 基线（`lastfailed=94` / `nodeids=1924` 不可与基线直接比较） | t2 §5-R4、§6.3-U4 |
| **B14** | **P2** | **0.5 天** | 教练链路口径核查 | `coach_outcomes.jsonl`（活体 mtime 09-24 11:35）· `coach_advice.json`（09-24 12:04）· `flow.llm_decision.ts` | 定位 `llm_decision` 写入方，判定教练链路是更名/改路径，还是 09-25 部署后帧保存条件不再满足 | t2 §5-R7、§6.3-U7 |

**新增建议合计**: 14 条（P0 ×3 / P1 ×4 / P2 ×7）；**P0 三条为「守卫与记录」类，总工时 2 小时 + 1 天**，属本窗口最高性价比收口项。

## A.3 困境重排（依据 t2 逐条判定）

### A.3.1 原 5 项困境（= `session-log-analysis.md` §5 / 本文件「困境 1–5」）优先级变更

| 排序 | 困境（原编号 → 建议项） | 现状（2026-09-26 实测） | 优先级 旧 → 新 | 变更理由 |
|:-:|---|---|:--:|---|
| **1** | **A1 Telemetry 常量分歧**（困境 1 → P0-N1） | **仍存在，量级未减**：`` `model.py` `` 中 `0.12`×7 / `0.15`×20；模块级命名常量仅 1 个（`FWD_RATIO_FLOOR`）。局部改善：gate 阈值已统一到注册表 + 单一换算点 | **P0 → P0（不变）** | 无任何缓解证据；本窗口未投入常量抽取 |
| **2** | **A2 CX-2「无视觉闭环校正」**（困境 2 → P0-N2） | **结论需更正**：`` `central_complex.py` L128 `` `relocalize()` 已存在，`` `central_complex.py` L529 ``、`` `central_complex.py` L673 `` 为调用点，`` `test_cx_navigation.py` L174 `` 起有测试；**活体命中率未验证** | **P0 → P1（降级）** | 「纯新增 3 天」不成立；实际工作是**验证 + 接线**（0.5–1 天）。降级不等于关闭：U5 未验证前不得声称已生效 |
| **3** | **A3 StuckDetector 单位混淆**（困境 3 → P1-N1） | ✅ **本窗口已解决**：`` `memory.py` L135 `` 为 `0.008` per-tick（注释 `was 5.0 Hz`），`` `memory.py` L208 `` 比较式带单位注释 | **P1 → 关闭（保留记录）** | 与 09-24「单位混淆风险仍存在」冲突，已更正。⚠️ 但 12:47 活体单点 `stuck_score = 1.0`（B3 观察项） |
| **4** | **A4 `control.x` 直写**（困境 4 → P2-N1） | **仍存在，但未恶化**：`` `main.py` `` **10** 写点 / 生产 **14** / 含 `tests/` **16**；窗口 diff 未新增写点。其中对话 LLM 旁路 1 处（`` `main.py` L2141 ``）仍跳过整条神经决策链 | **P2 → P1（升级）** | 恶化结论撤回（见 C8），但**架构性问题本身未解**：LLM 策略仍跳过决策链，且钳位契约未拦住写入方（`` `main.py` L3177 `` 的 `clamped_keys` 观测点错位） |
| **5** | **A5 Steering 预算次序未定义**（困境 5 → P1-N2） | **仍存在**：`` `memory.py` L1541 `` `_vote(...)` 仍是唯一判定函数，**无** `ArbitrationState`、无竞争/升级/超驰语义 | **P1 → P1（不变）** | c1 方案被 H13 裁定阻塞（P2/P3 整体阻塞）⇒ 无缓解路径，优先级不降 |

**结论（哪些已缓解/解决、哪些仍阻塞）**: **已解决 1 项（A3）**；**结论更正 1 项（A2，降级为「验证」）**；**数字更正 1 项（A4，恶化撤回但问题仍在）**；**完全未缓解 2 项（A1、A5）**。**仍阻塞**：A1（常量抽取）、A5（仲裁）与 A2（活体验证）在 H13 否定的前提下都无法转为「可验收闭环」，A4 的 LLM 旁路仍为架构级隐患。

### A.3.2 新增困境 A / B（队长已独立复现，本文独立实测）

#### 新增困境 A：版本/记录一致性守护失效（规则 8 的校验器不产生断言）

| 维度 | 值 |
|---|---|
| **严重度** | 🔴 **高（P0）** |
| **机制在位** | `` `agent.md` L19 `` 与 `` `agent.md` L88 `` 把 `` `check_version.py` `` 指定为「规则 8 三处版本同步校验」的执行体 |
| **实际内容（实测）** | `` `check_version.py` L1 ``–`` L4 `` 全文仅 4 行：`import sys` / `sys.path.insert(0, "/root/fly64")` / `from fly64.main import BRAIN_VERSION` / `print(...)`。**无任何 assert、不读 `SKILL_VERSION`、不读 history canonical、不读 `skills.md`** |
| **失效形态** | **WSL 恒 exit 0**（实测）：`wsl -e bash -c 'cd /root/fly64 && python3 tests/check_version.py; echo exit=$?'` → `loaded BRAIN_VERSION: 2.24.0` + `exit=0`；**Windows 以错因 exit 1**（`ModuleNotFoundError: No module named 'fly64'`，因硬编码 Linux 路径） |
| **后果** | 专门防版本漂移的守卫自身**永远不会失败** ⇒ `canonical_versions.skill = 3.4.2` 与 `` `main.py` L50 `` / `` `skills.md` L3 `` 的 `3.5.1` 不一致**无人拦截**；`--history-check` 亦未拦下 EVO-072/073 的删除 |
| **归属** | 与 t2 §4.3-N1 同一困境；根因归 RC-2（守卫自身无断言）+ RC-6（记录纪律） |
| **建议** | **B02**（改为真断言 + 纳入 CI/`--history-check`） |
| **证据** | t2 §3.2-E2、§4.3-N1、§5-R2；t1 §4；本次实测（4 行、WSL exit 0） |

#### 新增困境 B：进化记录被删除且版本回退

| 维度 | 值 |
|---|---|
| **严重度** | 🔴 **高（P0）** |
| **触发提交** | `fbcc3d7`（2026-09-26 12:28，WSLg 渲染修复）——**非记录类提交改动了 `evolution_history.json`** |
| **实测账目** | `git show fbcc3d7 --numstat -- fly64/skills/evolution_history.json` = **+115 / −39**；当前 `records` = **87**，`EVO-072` / `EVO-073` **均不存在**，tail = `AUTO-0019…AUTO-0023` + `EVO-074` |
| **可回收性（实测）** | `git show HEAD~1:fly64/skills/evolution_history.json` → **81 条，`EVO-072`/`EVO-073` 均在，`canonical_versions.skill = 3.5.1`** ⇒ **可完整回收** |
| **版本回退** | 当前 `canonical_versions` = `{"brain": "2.24.0", "skill": "3.4.2", "as_of": "2026-09-24T18:00:00+08:00"}` ⇒ skill 由 `3.5.1` **回退为 `3.4.2`**，与 `` `main.py` L50 `` 和 `` `skills.md` L3 ``/`` L70 `` 的 `3.5.1` 不一致 |
| **已扩散** | 删除**已同步进活体**：Windows 与 WSL 的 `evolution_history.json` md5 相同（`d98c46f96e7d`，两侧实测）⇒ 活体侧无 git 可回溯，只能靠工作区 `HEAD~1` 回收 |
| **归属** | t2 §3.2-E3、§4.3-N1、§5-R1；与「从未记录」（25-P0-1~25-P0-4 零记录）分列两类失效 |
| **建议** | **B03**（回收两条记录 + 三处版本对齐 + 新增守护） |
| **证据** | t2 §3.2-E3；本次实测（numstat 115/39、records 87、HEAD~1 81；⚠️ 队长补充的「+137/−41」t2 无法用 git 复现，本文采用 **115/39**，见 §A.6-C9） |

#### 另两条盲区新增困境（t2 §4.3-N2/N4，随本合并一并纳入）

| ID | 困境 | 现状（实测） | 严重度 | 归属建议 |
|:--:|---|---|:--:|---|
| **新增困境 C** | **窗口产出未入库，交付不可复现** | **37** 个已跟踪文件未提交（+4890/−469）+ **65** 个未跟踪项；25-P0-2/25-P0-4「已验收」不在 HEAD；`docs/analysis/**` 索引中仅 7 份 | 🔴 高（P0） | **B04** |
| **新增困境 D** | **活体-工作区漂移且部署证据链断裂** | `evolution_skill.py` 工作区 `97b178298e88` ≠ 活体 `fd1ccd56af24`；清单记录的 `f895171ee477` 两侧均不匹配；09-26 `sm64config.txt` 为手工同步 | 🟠 中高（P1） | **B05** |
| **新增困境 E** | **验收清单成为假绿来源** | `deploy-manifest.md` §6 六条「必须验证的信号」中 `burst_active` 无发布点（实测 `flow.json` 122 键中无该键，`main.py` 仅作为属性读取）、`evo_loop_stale` 全仓 `.py` 零命中 ⇒ **结构上不可能通过** | 🟠 中高（P1） | **B08** |

### A.3.3 合并后的优先级排序（现行）

| 顺序 | 层级 | 项 | 状态 | 下一步 |
|:-:|:--:|---|:--:|---|
| 1 | **P0** | **新增困境 A** 版本/记录一致性守护失效 | 未缓解 | 建议 **B02** |
| 2 | **P0** | **新增困境 B** 记录被删除 + 版本回退 | 未缓解，可回收 | 建议 **B03** |
| 3 | **P0** | **B1 自进化闭环（v5 §4.1）** | 部分缓解**未解决**，三点恶化：① 25-P0-2/25-P0-4 不在 HEAD/活体 ② 闭环 09-26 再接停摆（`evolution_log.jsonl` 活体最后写入 **09-26 11:47**；`evo_loop_launcher.sh --status` 报「闭环 ○ 未运行 / 最后写入 3538s 前」）③ 告警器最后自检 **09-25 21:01:25**（≈15.8 h 前）④ H13「真实 `noise_p95 = 0.1777` 超门限 5.9×」⇒ **P2/P3 阻塞、闭环保持永久 shadow** | 建议 **B01** + 队长裁定 |
| 4 | **P0** | **新增困境 C** 窗口产出未入库 | 未缓解 | 建议 **B04** |
| 5 | **P0** | **A1** Telemetry 常量分歧 | 未缓解 | **P0-N1** |
| 6 | **P1** | **A4** `control.x` 直写（含 LLM 旁路） | 未恶化但未解 | **P2-N1** + **B06** |
| 7 | **P1** | **A2** CX-2 视觉重定位「验证」 | 结论更正 | **P0-N2**（降级为验证 0.5–1 天）+ **B12** |
| 8 | **P1** | **B2 断口形态迁移**（v5 §4.2） | 部分缓解 | 断口已下沉为 B1 解码器硬编码饱和（`` `model.py` L2366 ``–`` L2367 ``：`np.clip((forward_rate-0.008)*2000, 0, 70)` / `np.clip(turn_rate*1100, -70, 70)`）/ B2 死写 / B3 钳位抹原值 / B4 无消费者 / B5 稳态钉满 / B6 量级差 10× | 队长裁定（H13 阻塞） |
| 9 | **P1** | **B3 观测层口径**（v5 §4.3） | 部分缓解 + 新增子项 | 新增：观测点错位（**B06**）、`source="unknown"`、`no_progress_gate` vs `progress_ineffective` 同刻相反；⚠️ **本次新单点风险**：12:47 活体 `stuck_score = 1.0`（t2 12:37 为 0.08）⇒ 若持续，「构造伪影已消除」需撤回 |
| 10 | **P1** | **新增困境 D** 活体-工作区漂移 | 未缓解 | 建议 **B05** |
| 11 | **P1** | **新增困境 E** 验收清单假绿 | 未缓解 | 建议 **B08** |
| 12 | **P1** | **P2-N2** 契约审计增量 | 升级 | **P2-N2** + **B07** + **B09** |
| 13 | **P1** | **P2-1** 版本声明对齐 | 升级 | 并入 **新增困境 A/B**（**B02**+**B03**） |
| 14 | **P2** | **A5** Steering 预算次序（v5 §4.4） | 仍存在 | **P1-N2**（被 H13 阻塞） |
| 15 | **P2** | **B4** 多会话并发写同一仓库（v5 §4.4） | 仍存在 | **B04** + 规则 16 单实例约束 |
| 16 | **P2** | **B5** 运维负担（v5 §4.5） | 仍存在且加重 | **B11** |
| — | 关闭 | **A3** StuckDetector 单位 | ✅ **本窗口闭环** | 保留记录（P1-N1） |

**变更理由摘要**: ① **升级**：版本/记录守护（新增 A、B）、契约审计（P2-N2）、版本对齐（P2-1）——窗口用三条实测证据证明「守卫不产生断言 + 记录可被非记录类提交删除」已构成**乘性失效**（RC-2 + RC-6），比原 P2 定位严重；② **降级**：A2（机制已存在，工作量 3 天 → 0.5–1 天）、A4（恶化撤回，但问题仍在）；③ **关闭**：A3；④ **不变的保留**：A1、A5、B4、B5 ——窗口内**没有任何缓解证据**。

## A.4 编号冲突裁定（「不得出现同一事项两种编号」）

窗口内存在**编号空间混用**，裁定如下（不改既有历史文本，仅建立映射）：

| 冲突编号 | 空间 1（本文件 / 执行计划） | 空间 2（09-23 交付线 / 09-25 交付线） | 裁定 |
|---|---|---|---|
| `P1-1` | **Telemetry 缺口补全（5 字段）** | `f486ad0`「P1-1 **钳位可见性**」（`clamped_keys` / `CLAMP_BOUNDS`） | 保留 `P1-1` 给计划项；09-23 线统一写作 **`P1-1(clamp)`**，其内容并入 **B06** |
| `P1-2` | **fallen recovery 修复验证** | `f486ad0`「P1-2 **契约对齐**」 | 保留 `P1-2` 给计划项；09-23 线写作 **`P1-2(contract)`**，内容并入 **B06/B07** |
| `P0-1`…`P0-4` | 本文件仅有 `P0-1`（EVO auto-fix）、`P0-2`（stuck 根治） | 09-25 线 `P0-1` 信用分配矩阵 / `P0-2` 可执行 fix / `P0-3` 闭环守护 / `P0-4` has_fix | 09-25 线统一加来源前缀 **`25-P0-1`…`25-P0-4`**（本文已如此使用） |
| `P2-N1` 计数 | 「22 处」→「10 处」→「12 处」三种口径 | — | 统一为 **10 / 14 / 16**（§A.0-K2、§A.6-C8） |
| `N1`–`N4` | 既有建议后缀 `P0-N1`…`P3-N2` | t2 困境表 `N1`–`N4` | 新增建议改用 **`B01`–`B14`**；困境用 **新增困境 A/B/C/D/E**，避免与建议后缀混淆 |

## A.5 更新后的执行波次（增量，不替换原文波次）

```
Wave-0（立即，总 2 小时 + 1 天，P0 三条）
  ├── B02 check_version.py 真断言（0.5 天）      ← 守卫先能失败，其余验证才有意义
  ├── B03 回收 EVO-072/073 + 三处版本对齐（0.5 天）
  └── B01 EVO 守护接入 crontab（1 小时）          ← 报告 §6-1 已给现成一行

Wave-1（可并行，P1）
  ├── B04 未入库交付分批提交（0.5–1 天）          ← 先入库再谈其他收口
  ├── B05 跨环境部署一致性门禁（0.5 天）
  ├── B06 钳位观测点/归因接线（0.5 天）
  ├── B12 复采 ≥6000 帧（1 天，需 SM64 可跑）
  └── P2-N2 契约审计增量（2 天，含 B07）

Wave-2（P2，与 Wave-1 并行）
  ├── B07 E7 收口（1 小时）   ├── B08 假绿项收口（2 小时）
  ├── B09 校验器精度（0.5 天）├── B10 工具链编码/口径纪律（0.5 天）
  ├── B11 磁盘/日志轮转（2 小时）├── B13 双测试根确认（0.5 天）
  └── B14 教练链路口径核查（0.5 天）

阻塞项（不由本计划解除）
  └── H13 裁定 ⇒ P2/P3 整体阻塞（含 A5、B2 断口、闭环转正式）：需队长重新裁定
```

## A.6 口径勘误（t3 复核新增，全部可复现）

| ID | 勘误 | 旧 | 新（2026-09-26 实测） | 复现命令 |
|:--:|---|---|---|---|
| **C8** | `control.x` 写点计数被正则伪影放大 | 「10→12（A4 恶化）」，以及「生产 14→16 / 含 tests 18」 | `` `main.py` `` **10** / 生产 **14** / 含 `tests/` **16**；**HEAD 与工作区同为 10** ⇒ 未恶化。t2 的「12/16/18」来自朴素正则把 `` `main.py` L2618 ``、`` `main.py` L2959 `` 两处 `control.x == 0` **比较**计入 | `Select-String -Path fly64/fly64/main.py -Pattern 'control\.x\s*=(?!=)'`（得 10）；`git show HEAD:fly64/fly64/main.py` 同法（得 10）；`git diff -U0 -- fly64/fly64/main.py` 中无新增写点 |
| **C9** | `evolution_history.json` 改动量 | 队长补充「**+137 / −41**」 | **+115 / −39**（`git show fbcc3d7 --numstat` 实测）；`--stat` 图总数 154 = 115+39。137/41 无法用 git 复现（t2 §6.3-U11 同结论） | `git show fbcc3d7 --numstat -- fly64/skills/evolution_history.json` |
| **C10** | 既有条目数 | 「16 项」 | **18 条**（10 保留 + 8 新增） | `Select-String -Path docs/analysis/session-log-recommendations.md -Pattern '^\| \*\*P[0-3]'` 计 18 行 |
| **C11** | 未跟踪项数 | 63（t2 时点） | **65**（+2 = t1/t2 两份盲区文档） | `git status --porcelain \| Select-String '^\?\?'` |

## A.7 复现命令（本节全部结论）

```powershell
# 1) 基线
git log -1 --pretty='%h %ad %s' --date=iso              # fbcc3d7 2026-09-26 12:28:02
# 2) 新增困境 A：守卫无断言
Get-Content fly64/tests/check_version.py               # 4 行，无 assert
wsl -e bash -c 'cd /root/fly64 && python3 tests/check_version.py; echo exit=$?'   # exit=0（恒过）
# 3) 新增困境 B：记录删除 + 版本回退
python -c "import json;d=json.load(open('fly64/skills/evolution_history.json',encoding='utf-8'));print(d['canonical_versions'],len(d['records']),'EVO-072' in [r.get('id') for r in d['records']])"
git show fbcc3d7 --numstat -- fly64/skills/evolution_history.json      # 115 39
git show HEAD~1:fly64/skills/evolution_history.json > $env:TEMP\h.json # 81 条且含 EVO-072/073、skill=3.5.1
# 4) 版本三处
Select-String -Path fly64/fly64/main.py -Pattern 'BRAIN_VERSION\s*=|SKILL_VERSION\s*='   # L49 / L50
Select-String -Path fly64/skills/skills.md -Pattern '3\.5\.1'                            # L3 / L70
# 5) A3 闭环 / A2 机制 / A5 未定义
Select-String -Path fly64/fly64/memory.py -Pattern 'rate_threshold'                      # L135 = 0.008 per-tick
Select-String -Path fly64/fly64/central_complex.py -Pattern 'relocalize'                 # L128 / L529 / L673
Select-String -Path fly64/fly64/memory.py -Pattern 'def _vote'                           # L1541
# 6) C8 口径
Select-String -Path fly64/fly64/main.py -Pattern 'control\.x\s*=(?!=)'                   # 10
Select-String -Path fly64/fly64/main.py -Pattern 'control\.x\s*='                        # 12（含 2 处 ==）
# 7) E1/E8/漂移
wsl -e bash -c 'crontab -l'                                                              # 仅 watchdog.sh / phase2_gate.sh
wsl -e bash -c 'cd /root/fly64 && bash scripts/evo_loop_launcher.sh --status'
wsl -e bash -c 'cd /root/fly64 && md5sum skills/evolution_skill.py skills/evolution_history.json'
python -c "import json,urllib.request as u;f=json.load(u.urlopen('http://127.0.0.1:8765/flow.json'));print('clamped_keys' in f,'burst_active' in f,len(f))"
# 8) 文档自洽
python scripts/verify_doc_citations.py                                                   # 必须 exit 0
```

---

> **合并说明**: 本节由 t3（strategist）写入，**不改动 t1/t2 文档**；对既有 18 项建议与 5 项困境只做「标注 + 排序 + 增补」，**未删除、未放宽**任何条目。
> **配套文档**: `docs/analysis/session_logs_execution_plan.md` 的对应增量见其「2026-09-26 盲区合并更新」附录，两文档数字口径一致（可由 `scripts/verify_doc_citations.py` 校验）。

---

## A.8 t5 返修勘误块（append-only，2026-09-26 13:1x；依据 t4 核验报告 M-1~M-5）

> 依据 `docs/analysis/blindspot-review-0923-0926.md`（t4 独立核验）。**本块只追加，不修改上文任何条目**（纪律：不得删除条目或放宽表述）。凡与下文冲突的上文表述，**以本块为准**。

| # | 上文位置 | 原表述（被本块更正） | 更正后（实测） | 依据 |
|:-:|---|---|---|---|
| **E-1** | P1-N1 标题（L195）「单位文档化 **+ 运行时断言** 🟡」；L223/L234/L248 落地清单含「运行时断言」 | P1-N1 记为 ✅ 本窗口闭环（含"断言"这一半） | **单位文档化 ✅ 已实现 / 运行时断言 ❌ 未实现**：`memory.py` 内 `rate_threshold` 仅 `135`（定义，注释 `was 5.0 Hz`）/`142`（赋值）/`208`（比较）三处，**全文 `assert` 计数 = 0** ⇒ P1-N1 应记为「**半闭环**：单位口径闭环 / 可观测性未闭环」 | `Select-String -Path fly64/fly64/memory.py -Pattern 'rate_threshold'`（3 处）；`-Pattern '^\s*assert\b'`（0 处） |
| **E-2** | L200「⚠️ 遗留一点需复验：12:47 单点 `stuck_score = 1.0` … **单点不可当趋势**，若持续为 1.0 则 B3 需撤回」 | 以"单点 / 观察项"处置 | **已复现（不再只是观察项）**：t4 于 12:54:31–12:55:01 取到 **六连** `stuck_score = 1.0 / stuck_duration = 0.0`；我用**离线仿真**独立复算 **3000 tick 内 14 次 `score==1.0` 且 14 次 `dur==0.0`**（对照组 `disp_60s=None` → `dur=0.02`）⇒ **B3「构造伪影已消除」必须撤回并改写为观测层缺陷** | t4 §6.1/§6.2；`memory.py:208-235`；t2 §3.2-E13（t5 新增第 13 例） |
| **E-3** | L865「B3 观测层口径（v5 §4.3）｜**部分缓解** + 新增子项；⚠️ 本次新单点风险…若持续需撤回」 | 「部分缓解」 | **未缓解**（"缓解"部分不成立）：`stuck_score ≡ {0,1}` **未消除，只是改变了触发相位** —— `rate` 子信号（`forward_rate == 0` 连续 3 s）仍把 `stuck_score` 拉到 1.0；`:234-235` 的 `disp_60s > 500` 泄放把 `_stuck_duration` 一次性抹回 0 | 同上 |
| **E-4** | L810「3 ｜ A3 StuckDetector 单位混淆 ｜ ✅ **本窗口已解决** ｜ **P1 → 关闭（保留记录）**」；L875「③ **关闭**：A3」 | 单句"已解决 / 关闭" | 拆为两句：① **单位标注对齐 ✅ 已解决**（`memory.py:135` = `0.008` per-tick，`5.0` 已不存在）② **「不再 ≡1.0」✘ 不成立**（`0.08` 是**单点取样偏差**）③ 另有**半迁移**：`docstring:127` 仍写「`< 5 Hz`」。⇒ **A3 只在"单位口径"上关闭；可观测性未闭环** | `memory.py:127/135/207-208`；t4 §3 第 1 行与 §6 |
| **E-5** | L851「新增困境 E … `burst_active` **无发布点**（实测 `flow.json` 122 键中无该键，`main.py` 仅作为属性读取）」 | 「无发布点」 | 更正为「**无 flow/memory 发布点**」：`main.py:2206 model.burst_active = _deadlock_burst_remaining > 0` **存在属性赋值**，但不写入任何 HTTP 端点 | `Select-String -Path fly64/fly64/main.py -Pattern 'burst_active'`；活体 `flow.json`/`memory.json` 均无该键 |
| **E-6** | L771/L785「`` `evo_liveness_guard.py` ``（**写作 339 行 / 179 行**）」（**未标注目录**） | 未写路径；且行数用了 `Measure-Object -Line` 的漏计口径 | 补明路径：**`fly64/scripts/evo_liveness_guard.py`**（**407 行** / 15,863 B；行数口径 **339 → 407**）与 **`fly64/scripts/evo_loop_launcher.sh`**（**211 行** / 7,889 B；行数口径 **179 → 211**）；`fly64/skills/evo_liveness_guard.py` **实测不存在**。（t2 报告的「+407 / +211」是 `git show --stat` 的**新增行数**——两文件在 `38c8bae` **新建**，新增行数 == 文件总行数 ⇒ 与 `wc -l` 双向印证） | `Test-Path fly64/skills/evo_liveness_guard.py`；`git ls-files --stage`；`git show 38c8bae --stat`；`python -c "print(open(p,encoding='utf-8').read().count(chr(10)))"`（407 / 211） |
| **E-7** | 全文**未记录** | — | **补录 1**：上述两脚本在 git 中均为 **100644（无执行位）** ⇒ WSL 上必须 `bash scripts/…` 显式调用，与"可被 cron/启动器直接执行"的运行契约冲突（与 B01/E1 同族）。**补录 2**：`runtime/evolution_history.json`（7,110–7,134 B，**每轮重写，仅 WSL**；消费方 `fly64/fly64/main.py:61/220/2360`）与 `skills/evolution_history.json`（99,101 B，canonical；`skills/evolution_skill.py:202` + `tests/test_version_consistency.py:28`）是**两份不同历史文件** ⇒ 恢复/一致性动作必须**分别处置**，不能只修一份 | `git ls-files --stage`；WSL `ls -l` + `head -c` |
| **E-8** | 全文**未用**"家族例数"口径；本块仅作跨文档一致声明 | — | **RC 例数口径由 12 → 13**（RC-4 由 1 → 2；新增实例 = `stuck_score`/`rate` 子信号观测层假绿）。该例**与 A3 是同族症状、不同判据**（A3 历史症状 = 量纲错配；本次 = 量纲修好后暴露的语义+泄放缺陷），并**与 RC-5 叠加**（只改阈值与注释、未改 docstring、未加断言）；**不构成新子型** | 队长裁定；t2 §3.2-E13 / §3.3 / §3.4 |
| **E-9** | 全文**未记录**（M-6，t5 attempt 2） | — | **已交付文档回改完成**：`docs/analysis/session-log-analysis.md` 已就地更正三处过时事实 —— ① §困境 2「**无视觉闭环校正**」→「`relocalize()` 机制已在（`central_complex.py:128-140` + 调用点 `:529`/`:673` + 测试）、**活体生效未验证**」；② §困境 3 →「单位口径已闭环（`rate_threshold = 0.008` per-tick）/ **运行时断言未实现（0 assert）** / 可观测性未闭环（`stuck_score` 12:54 六连 1.0 且 `dur=0.0`）」；③ §困境 4 的 10 个写点行号 → `[760,2060,2077,2141,2190,2192,2406,2414,2466,2492]`，复现正则加 `(?!=)` 守卫，并补「含 `fly64/tests` 16 / 含根 `tests/` 17」。该文件文末新增「附录 C：t5 返修勘误汇总」留痕 |
| **E-10** | **L120–L161（P0-N2 小节：问题描述 L135 + 技术方案 L137–L152 + 涉及文件）**；另 **L918（C8 行）** 的 A4 口径 | ① 基线正文写「`_self_motion_update()` 使用 heading_rate **开环积分，无视觉闭环校正**」（L135）并按「**纯新增 3 天**」给出实现方案；② C8 行只给到「`main.py` 10 / 生产 14 / 含 `tests/` 16」三级 | ① ⚠️ **过时（与 M-6 同源）**：`AnchorPathIntegrator.relocalize(scene_id, confidence)` **已存在**（`` `central_complex.py` L128 ``，gate 0.8 / strength 0.3）+ **调用点 2 处**（`` `central_complex.py` L529 ``、`` `central_complex.py` L673 ``）+ 测试 `` `test_cx_navigation.py` L174 ``–`` L204 `` ⇒ 本小节应从「实现（3 天）」改为「**验证/接线（0.5–1 天）**」（与 §A.1-P0-N2、§A.3.1 第 2 行一致）；② **A4 补第 4 级口径**：`` `main.py` `` **10** / 生产 **14** / 含 `fly64/tests` **16** / 含根 `tests/` **17**（赋值口径 `control\.x\s*=(?!=)` 全仓合计 = 17：`fly64/tests` 贡献 +2、根 `tests/` 贡献 +1） | `Select-String -Path fly64/fly64/central_complex.py -Pattern 'relocalize'`（→ L128/L529/L673）；`Select-String -Path fly64/tests/test_cx_navigation.py -Pattern 'relocalize'`（→ L174 起）；全仓 `control\.x\s*=(?!=)` 计数（→ 17） | `docs/analysis/session-log-analysis.md` 附录 C；`Select-String -Path fly64/fly64/main.py -Pattern 'control\.x\s*=(?!=)'`（10） |

**与 t2 的一致性**：以上更正与 t5 返修后的 `docs/analysis/blindspot-analysis-0923-0926.md` **逐条一致** —— 其 §4.1-A3 已拆分、§4.1-A4 已改为「`main.py` 10 / 生产 14 / 含 `fly64/tests` 16 / 含根 `tests` 17，且**未恶化**」、§4.2-B3 已改为「未缓解」、§4.3-N1 已补「规则 8 的第二个守卫 `test_version_consistency.py` 只覆盖 `BRAIN_VERSION`」、§3.2-E13 为新增第 13 例、§2.5 为两处补录。
**未改动项（明确不放宽）**：本文件 A1/A2/A4/A5、B01–B14 建议、C1–C11 口径表**均未放宽**；A4 数字（`main.py` 10 / 生产 14 / 含 `fly64/tests` 16）在 L359 与 L918（C8）已正确，**无需更正**。

> **E-10 追加说明（append-only）**：A4 的第 4 级口径（含根 `tests/` = **17**）本轮经 E-10 补入，属**口径补全而非推翻** —— L359 与 L918（C8）的三级数字（10 / 14 / 16）**仍然正确**，只是不完整。同理，E-10 对 P0-N2 小节（L120–L161）的更正**不修改**该小节原文，仅以本块声明其「无视觉闭环校正」与「3 天纯新增」两处表述**已过时**。

---

# A.9 2026-09-26 第三轮（一手会话）合并更新块（append-only）

> **合并人**: `strategist`（AgentTeams `fly64-newlogs-0924-0926` / task **t4** / attempt `888b5c07-6410-4a62-a12e-94c031222603`）
> **合并来源（第三轮 R3）**: `docs/analysis/session-analysis-0924-0926.md`（t2，**562 行 @t5 核验时点**）· `docs/analysis/blindspot-crossvalidation.md`（t3，**559 行 @t5 核验时点**）
> ⚠️ **时点/修改声明（t6 补）**：本块写入时二者均未改动；**t6 返修已对 t2/t3 就地更正**（F-1/F-2/F-3/F-5/F-9/F-10 + t3 措辞与 pkill 口径）⇒ 现测 **t2 = 569 行 / t3 = 564 行**，引用行数须注明"t5 核验时点"。细则见 **§A.9.10**。
> **项目级合并结论**: `docs/analysis/project-state-consolidated.md`（t4）
> **纪律**: 本块**只追加**，**不删除、不放宽**上文任何条目（含 A.0–A.8 与正文 18 项）；凡本块与上文冲突者，**以本块为准**（本块为最新）。
> **性质限定**: 本块**不含任何新一轮实测** —— 所有 `file:line` 与活体数值均**转引自** t2/t3/blindspot 文档，不再二次复算。

## A.9.1 计数口径更正（**C12–C13**）

| ID | 上文位置 | 原表述 | 更正后（R3 权威） | 依据 |
|:--:|---|---|---|---|
| **C12** | §A.2「本报告复算」行的**上游依据** A.0 未记；t2 §0.1 的日度去重口径 | 09-25 去重 = **185** | **09-25 = 206**（09-24 = 336、09-26 = 153，合计 **695**）。**185 有误**：取 `6c53f724-v2`（09-25 = 174），**漏掉只存于 v3 的 21 次真实调用**（v2 的导出时刻就是 09-25 20:28，结构上不可能包含之后的调用） | t3 §A.2 独立复算（逐快照 726/58/304/350/152/236 与 t1 一致）；队长 09-26 更正确认 |
| **C13** | t2 §0.1 的「**1826 − 1209 = 617** 次切片重叠重复」；**本块初版曾写「重复副本 = 1131」（t6／F-1 已更正）** | 重复副本 = 617（t2）→ 1131（本块初版，**跨域相减**） | **重复副本 = 514**（**窗口域**：`快照合计 1209 − 去重 695`；**全快照域**：`1826 − 全局去重 1312`，两域一致）。**`617` 的真实身份 = 窗口外（09-19→09-23，仅存于 `99cab60f-latest`）调用量，无副本**；`1826` 只能与 `1312` 相减 | t3 §A.2 复算 + **t5 §1.1-A4／§9-F-1 域更正**（`distinct callId = 1312`） |

> **引用规则（本块起生效；t6／F-1 修订）**：主会话 `tool/call` 一律**三段式且声明域**——
> **全快照域**：`1826 / 去重 1312 / 重复副本 514`；**窗口域（09-24→09-26）**：`快照合计 1209（665/391/153）/ 去重 695（336/206/153）/ 重复副本 514`；**窗口外**：`617（无副本）`。
> **`1826` 不得写成「当日工作量」**；**`617` 不得再被引用为「重复数」**；**任何减法必须两项同域**（本块初版的 `1826 − 695 = 1131` 即为反例）。

## A.9.2 困境与结论的**性质修订**（**G-1…G-10**，逐条对应上文条目）

| ID | 上文位置 | 原表述（被本块改性质，**原文保留**） | 更正后（R3） | 依据 |
|:--:|---|---|---|---|
| **G-1** | §A.3.2「新增困境 B」的**触发提交**行（L836「`fbcc3d7`…**非记录类提交改动了 `evolution_history.json`**」） | 未判性质；队长原假设作者会话是 `6c53f724` | **性质 = 意外覆盖（`cp` 事故），作者会话 = `51f62457-v2`**。11 步链路：12:25:31 读工作区（81 条 / skill 3.5.1 / 末条 EVO-073）→ 12:25:40 append EVO-074（82 条）→ 12:26:17 对 WSL 副本同样 append → 12:27:19–29 **主动确认两侧是不同文件**（无 `.git`；inode `296` vs `125256364637215400`）→ **12:27:34 `cp /root/fly64/skills/evolution_history.json /mnt/d/codes/flygym/fly64/skills/evolution_history.json`** → 12:27:53 `git add` 三文件 → 12:28:03 commit → 12:28:20 回同步 WSL → 12:28:38 收尾**仅称"新增 EVO-074"**。三条判据：① 提交后 `as_of` 恰为脚本写入的常量 `2026-09-24T18:00:00`；② `added=[AUTO-0017..0023, EVO-074]` / `removed=[EVO-072,073]`；③ **该会话从未把 EVO-072/073 识别为"待删对象"**。**【t6／t5-M2 措辞更正】本块初版作"③ 会话全文零处提及 EVO-072/073 或 canonical skill"——字面不成立**：全导出集命中 **3 处**（12:24:27 锚点表回显 `/ 12:25:31 读文件输出 \`last record id: EVO-073\` / 12:25:40 自述 "The last record is EVO-073"`），但**均属回显、无一处把它当作待删对象** ⇒ **实质结论（提交者不知情）不变**。**根因 = 工作区/WSL 双份 history 分叉**（见 A.9.3-困境 G） | t3 §2.7；t5 §1.2-B4/M2（`cp` 链路 + mtime 12:27:35 逐位复现）；`git show fbcc3d7 --numstat` = 115/39 |
| **G-2** | §A.3.2「新增困境 D」（L850） | 「清单记录的 `f895171ee477` 两侧均不匹配」→ 推论 **P0-2/P0-4 不在活体**（§A.1-P0-1 与 P0-2 的「不在活体」） | **「P0-2/P0-4 不在活体」是过度推断，降级为待验证**。会话自述「部署它 = **连带部署其中一切**」（09-25 18:54:50）⇒ 活体 = 09-25 部署时的**整文件工作区版本**；此后工作区又被并行会话修改，md5 才分叉 ⇒ **md5 差集不能推出缺项**，须做**符号存在性**核对 | t3 §2.4、§6-B-2 |
| **G-3** | §A.3.2「新增困境 E」（L851） | 「`burst_active` **无发布点** / `evo_loop_stale` **全仓无实现** ⇒ 结构上不可能通过」 | **性质改写**：「**承诺过 + 派过单 + 未落到发布点**」。`evo_loop_stale` = SP1/P0-a6 **设计键** + V16 判据（"杀进程后 ≤120s 置 true"）；`burst_active` = **09-25 00:54 的 D2 high 返修单**明确要求"发布五个 `flow.json` 观测键"（当时判定 `_no_progress`/`_burst_ok`/`progress_ineffective`/`burst_active` 在 `central_complex.py`/`model.py` 完全不存在）。**新增同族更早实例**：`HAS_EVO_LIVENESS=False`（相对导入失败 → 三符号被替换为空桩 ⇒ 心跳永不写入），09-25 12:18:58/12:19:11/12:19:49 发现，12:27:10 修复 | t3 §2.5 |
| **G-4** | §A.8-E-2 / E-3（`stuck_score`） | 「已复现（六连）」+ 机制 `rate` 子信号 + `disp_60s` 泄放 | **部分成立，须补两点**：① **同一读数里有反判据键 `stuck_duration_true`（11:51 = 4.48 / 11:54 = 4.88）**，会话**正是用它消歧**的 ⇒ "假绿"**只对只读 `stuck_score`/`stuck_duration` 两键的消费者成立**；② **会话当时的归因是错的**：09-26 11:52:22 判「**伪影已消**但被**短时真卡死触发** / 监测器正确捕获」，**从未提及** `rate` 子信号与泄放 ⇒ 机制归因**是本窗口会话之后才提出的新解释** | t3 §2.6；`6c53f724-v3` 11:51:59 / 11:54:02 / 11:55:14 |
| **G-5** | §A.3.3 第 3 行（B1）与 E1 相关表述 | 「闭环 09-26 11:47 再停摆（`evolution_log.jsonl` 活体最后写入 **09-26 11:47**）；告警器最后自检 **09-25 21:01:25**（≈15.8 h 前）」 | **事实面保留，时间语义必须写对**：**11:47 是心跳末次写入（现象时间戳）**，「**14.5h 无告警**」是 **09-26 12:36** 由查询方算出的跨度 ⇒ 窗口内（**09-25 21:15 → 09-26 11:47**）**没有任何会话记录过这次停摆或告警缺失**。**E1 无法从会话验证**：`evo_liveness_guard`（311 次命中）/ `evo_loop_launcher`（345 次命中）/ `analysis-evo-loop-liveness` **全部只出现在 99cab60f**（同源）⇒ `38c8bae` 的**作者会话不在导出集**，RC-1 引文**降级为待补证**；**导出覆盖仍有洞（09-25 21:00–21:18）** | t3 §2.9、附录 A.4 |
| **G-6** | §A.2-B07（E7 收口）的上游判定 | 盲区判 E7 为完整实例 | **部分成立**：生产者侧 + `test_gate_units.py` 迁移**可见**，**消费者侧改动未见**；"迁移只做一半是否属规格缺口"**无法从会话验证**（变更矩阵**含** `plugin/scene_context.py` 行，但读到片段不含其条目号）。**影响面低危的限定必须保留**（唯一序列化器零调用者、LLM 摘要不含该键） | t3 §2.10 |
| **G-7** | 全文未记录（R2 §6.3-U「导出覆盖缺口」） | t2 §6.3 曾称 `833848c`/`38c8bae` **0 次命中**、43 项 `D` **0 次对应** | **两者均不成立**：① `833848c` **38 次命中**、`38c8bae` **176 次命中**（均为 `git log`/`push` 输出行）；② 43 项 `D` **原样出现在会话**（12:27:55 的 `git status --short`），且**性质是 `fly64/.pytest-run/**` 的 pytest 夹具目录**（测试副产物），**不是源码被删**。**但结论方向成立**：两者的**内容产出**（`session_logs_analysis_v5` 57 次 / `session_logs_execution_plan_v5` 30 次）**全部位于 99cab60f** ⇒ 正确表述是「**提交号可见，产生它们的会话不在导出集内**」= **未覆盖** | t3 §A.3 |
| **G-8** | §A.4 编号冲突裁定表 | 未含 `gate_jump_threshold` 语义断裂 | **补一条被明确警告却未闭环的迁移**（成因链）：同 key Hz→ratio 换语义是**有意设计**（09-24 13:12:44）→ 其前提「线上 3.082 仍在 `[0.25,3.0]` 内 ⇒ 无需迁移」**被队长 09-24 13:13:14 当场以 `3.082 > 3.0` 证伪**（F1 blocker）→ t7 迁移清单（`active_strategy.json:8` → 0.75）→ 09-25 18:54 部署清单**明文警告**「否则 WSL 旧值 3.082 在新 ratio 语义下要求 `jump_rate > 3.082`」→ **仍未闭环**（工作区 0.75 vs WSL 3.082）。**归属 RC-5（迁移只做一半）** | t3 §2.8 |
| **G-9** | §A.3.2「新增困境 C」（L849） | 「37 个已跟踪文件未提交（+4890/−469）+ 65 个未跟踪项」= 单一原因（未入库） | **补因（不推翻）**：除脏树外新增「**有意搁置**」——「为不把他方半成品一并入库，本轮**不提交**该文件及其两个新测试…**待并行会话提交后**一并落地」（含**解除条件**）；且未入库的 2485 行中**约 2450 行属另一 DSH 会话**的在途工作 ⇒「本团队忘提交」这一读法**不准确** | t3 §2.3、§4-4 |
| **G-10** | §A.3.1 第 4 行（A4） | 「**P2 → P1（升级）**」 | **保留**（问题本身未解：LLM 策略仍跳过决策链、钳位契约未拦住写入方）；**新增口径**：赋值口径 `control\.x\s*=(?!=)` 全仓合计 **17**（`main.py` 10 / 生产 14 / 含 `fly64/tests` 16 / 含根 `tests/` 17），**`2f87d77^`=`HEAD`=工作区均 10 ⇒ 未恶化** | t3 §A.6-C8、§A.8-E-10 |

## A.9.3 新增困境（**F / G**；与既有 N1–N4 / A–E 的归属已核对，无重复计数）

#### 新增困境 F：**跨会话 / 跨进程的「重启无互斥」**（09-26 11:47–12:05 两会话并发处置同一故障）

| 维度 | 值 |
|---|---|
| **严重度** | 🟠 中高（**P1**） |
| **事件（PID 级可回放）** | 11:47:05 用户令 `51f62457-v2`「清理旧任务，重启」→ 11:47:32 `kill 15040 11997 236` + `tmux kill-session` + `rm -f /tmp/f64b_traj …` → 11:47:44 起脑 **2505** / SM64 **2566** → 11:48:31 自述"全部正常、稳定运行"。**同期** `6c53f724-v3` 11:48 读到 2505（`stuck_score=0.06`）→ 11:51:59 / 11:54:02 / 11:55:14 读到 `stuck_score=1.0` 且 `stuck_duration=0.0` → **11:55:30 / 11:55:46 判"需同时重启 brain+SM64"并 `pkill -f 'fly64.main'` + `pkill -f 'sm64.us.f3dex2e'`（杀掉 2505）** → 11:57:45–12:03:06 **共 6 次 `write` 脚本轮次（11:54:25→12:02:59），其中实际执行 `pkill -f 'fly64.main'` 共 3 条（11:55:30 / 11:57:24 / 12:02:47）** + `rm -f /tmp/f64b_traj`（杀 6024/6203/6444/6572）→ 12:02:59–12:03:16 `51f62457-v2` 读到 `Connection refused`、`ps` 无任何 `fly64.main` ⇒ 报"脑模型崩溃、桥文件消失、SM64 孤立运行" → 12:04:42 设 `FLY64_BRIDGE` 重启后恢复。**【t6／t5-M1 口径更正：原文"连续 6 轮 `pkill`"应读作"6 次脚本轮次 / 3 条实际执行"，两口径不可互替；归因结论不变。】** |
| **判定** | ① **可 PID 级归因**：12:02:59 起**唯一**执行 `pkill -f fly64.main` 的会话是 `6c53f724-v3`；② **R3 更正**：「两会话对同一时刻描述矛盾」**不成立** —— 两者描述的是**不同时刻**（11:52 vs 12:03），**同刻比对时读数一致**；③ 「第一因」是两个会话共同造成（51f62457 的清理是用户要求的、正确的），且**两会话自始至终无任何交叉引用** |
| **机制缺口** | `fly64/scripts/locked_launcher.py`（`runtime/launcher.lock`）**只防同一个 `run-fly64` 入口被重复启动**，**对 SM64 一无所知、不拦 `pkill`**；`skills/.evo_loop.lock`（PID 11997）**只锁 EVO 循环单例**；`brain_wrapper.sh`（脑死即自动重启）**与人工重启竞争且无协调** ⇒ **三者均不覆盖「brain+SM64 重启」** |
| **归属** | 与 **E1（守护未接入调度）同族但根因不同**（E1 = 调度缺失；本项 = **并发写者互不可见**）；并入 **B4（多会话并发写同一仓库）**家族并**上调严重度**（已从"提交分线"演化为"同一文件内无法分离的混合改动 + 同一运行实例被互相拆掉"） |
| **建议** | **B16**（见 A.9.4） |
| **证据** | t3 **附录 A.1**（事件重建 + 三机制覆盖性判定表）；t2 §5.3-I2 |

#### 新增困境 G：**工作区 / WSL 双份 `evolution_history.json` 分叉**

| 维度 | 值 |
|---|---|
| **严重度** | 🔴 高（**P1**） |
| **事实** | `fly64/skills/evolution_history.json`（**99,101 B / 87 条 / md5 `d98c46f96e7d…`**，工作区与 WSL 同 md5）与 `fly64/runtime/evolution_history.json`（**7,110–7,134 B / 2 键 / 20 iterations / 每轮重写 / 仅 WSL 存在**）是**两份不同的历史文件**，消费方不同（`main.py:61/220/2360` vs `evolution_skill.py:202` + `test_version_consistency.py:28`） |
| **后果（两个，均已兑现）** | ① **D-03 / 本文件新增困境 B**：`51f62457-v2` 的 `cp` WSL→工作区 `evolution_history.json` ⇒ 删 EVO-072/073 + skill 3.5.1→3.4.2（**G-1**）；② **D-05 / 新增困境 D 的根因**：活体与工作区分叉、部署证据链断裂（md5 两侧不匹配） |
| **为何单列而不并入既有条目** | 上文 **B03** 只治"回收两条记录 + 对齐版本"，**B05** 只治"md5 门禁"——**两者都不消除分叉本身**，因此事故在结构上**仍可复发**（与 **`fly64/tests/check_version.py`** 空壳同族：**无断言/无单一权威**） |
| **可回收性** | `git show HEAD~1:fly64/skills/evolution_history.json` → **81 条、含 EVO-072/073、`skill=3.5.1`** ⇒ **可完整回收**；⚠️ 删除**已同步进活体**（两侧 md5 相同）⇒ 活体侧无 git 可回溯 |
| **建议** | **B17**（见 A.9.4） |
| **证据** | t3 §2.7、§2.4、§4-9/§4-10；本文件 §A.8-E-7 补录 2 |

## A.9.4 新增建议（**B15 / B16 / B17**）与口语编号映射

| 编号 | 优先级 | 工时 | 行动 | 涉及文件（file:line） | 证据出处 |
|---|:--:|:--:|---|---|---|
| **B15** | **P1** | 0.5 天 | **`stuck_score` 恒真代码修复**：`rate` 子信号与 `disp_60s` 泄放**至少一项改口径**（例：`rate_threshold` 语义由"`forward_rate` 恰为 0"改为"低于前进阈值且伴随无位移"，或泄放按 delta 而非一次性 `−1.0`）；并在 check 级断言钉住「**`stuck_duration == 0` 时 `stuck_score` 不得为 1.0**」 | `memory.py:213-225`（取 `max`）、`memory.py:227-231`（`±0.02`）、`memory.py:234-235`（泄放抹零）、`memory.py:127`（docstring 仍写 `< 5 Hz`） | t2 §5.2-U11 / §7.3；t3 §2.6；本文件 §A.8-E-1/E-2/E-3 |
| **B16** | **P1** | 0.5 天 | **为「brain+SM64 重启」补锁/互斥与告警**：新增"实例归属锁"，覆盖 `wsl_launcher.sh` / `setsid python3 -m fly64.main` / `pkill` 三条路径；重启前检查锁持有者与"另一会话在重启"信号；把 `brain_wrapper.sh` 的自愈重启纳入同一协调；至少做到"第二个会话 `pkill` 前必须看到归属告警" | `fly64/scripts/locked_launcher.py`、`skills/.evo_loop.lock`（PID 11997 陈旧锁）、`scripts/wsl_launcher.sh`、`brain_wrapper.sh` | t3 附录 A.1；t2 §5.3-I2；新增困境 F |
| **B17** | **P1** | 0.5 天 | **消除工作区/WSL 双份 `evolution_history.json` 分叉 + 加一致性守卫**：显式化两份文件的关系（canonical 单一权威 + 运行侧只读派生），或加"分叉检测"门禁；提交前断言"两侧同源或差异可解释" | `fly64/skills/evolution_history.json`、`fly64/runtime/evolution_history.json`、`main.py:61/220/2360`、`evolution_skill.py:202` | t3 §2.7、§2.4；新增困境 G |

**口语编号 → 本文件编号映射（消除"同事项两编号"）**：

| 上游口语编号 | 本文件编号 | 事项 |
|---|---|---|
| **P0-a** | **B03** | 回收 EVO-072/073 + 版本三元组对齐（0.5 天） |
| **P0-b** | **B02** | `check_version.py` 补真断言（0.5 天） |
| **P0-c** | **B01** | EVO 守护入 crontab/systemd + kill→自愈验证（1 小时） |
| **P0-d** | **B04** | 收口未入库交付（0.5–1 天） |
| **P1** | **B15**（新） | `stuck_score` 恒真代码修复 |
| **P1-new** | **B16**（新） | 「brain+SM64 重启」补锁/互斥 + 告警 |
| **P1-new2** | **B17**（新） | 双份 `evolution_history.json` 分叉消除 + 一致性守卫 |

## A.9.5 既有 18 项的**状态增量**（不替代 §A.1，只追加）

| 编号 | R3 后的状态 | 依据 |
|---|---|---|
| **P0-1** | **部分完成、未闭环**（`25-P0-2` 可执行 fix / `25-P0-4` `has_fix` 已验收，但**不在 HEAD / 不在活体 / 无记录**）；"不在活体"依 **G-2** 降级为**待验证** | t3 §2.0-E4、§2.4 |
| **P0-2** | 同上（载体 `evolution_skill.py` 2485 行中约 **2450 行属另一 DSH 会话**） | t3 §2.3 |
| **P2-3** | **部分完成**：两脚本已交付（**407 / 211 行**）、**未接调度**、且 git 中均 **`100644`（无执行位）** | 本文件 §A.8-E-6；t3 §2.9 |
| **P1-N1** | **半闭环**：单位口径 ✅ / 运行时断言 ❌（`assert` 计数 = 0）/ 可观测性未闭环（`stuck_score` → **B15**） | 本文件 §A.8-E-1 |
| **P2-2 / P1-N2** | **未缓解**，且 c1 仲裁路线**被 H13 阻塞** | 本文件 §A.3.1 第 5 行 |
| **P2-N2** | **升级 P2→P1**（窗口新增 3 例同型：守卫空壳、删键+夹具、验收信号未落到发布点） | 本文件 §A.1 |
| **P2-1** | **升级 P2→P0**（并入新增困境 A/B，即 **B02 + B03**） | 本文件 §A.3.3 变更理由① |
| **P0-N2 / A2** | **降级 P0→P1**：机制已在，工作改为「验证/接线 0.5–1 天」；**活体命中率仍未验证**（t3 §6-B-5） | 本文件 §A.3.1 第 2 行 |
| **A3** | **半闭环**（单位口径关闭 / 可观测性未闭环）—— **不撤销 §A.3.1 的"关闭"记录，只限定其范围** | 本文件 §A.8-E-4 |
| **B3（v5 §4.3）** | **未缓解**（"构造伪影已消除"不成立）；并新增反判据 **`stuck_duration_true`** 的限定（**G-4**） | 本文件 §A.8-E-3；t3 §2.6 |
| **B4（v5 §4.4）** | **严重度上调**：从"提交分线"演化为"**同一文件内无法分离的混合改动**"+"**同一运行实例被互相拆掉**" ⇒ 对策新增 **B16** | t3 §2.12、附录 A.1 |
| **P0-N1 / A1** | **未缓解**（量级未减；本窗口未投入常量抽取） | 本文件 §A.3.1 第 1 行 |

## A.9.6 真实成效（**反向证据**，避免"只列困境"；R3 增补）

| 成效 | 数值 | 可信度与限定 |
|---|---|---|
| gate 单位契约生效 | `gate_jump_ratio` 6 采样 **4 次 > 0.75**（2.25/1.0/1.0/1.0）；`forward_rate_hz` **3.85–15.38**（不再恒 46–50） | 🟢 实测（`blindspot-review` V12 的 54 点采样方向一致） |
| WSLg 渲染修复有效 | `render_ms = 6.118`、`bridge age_ms = 16.59` | 🟢 实测**单点**（非趋势） |
| **首次观测到 `jump`**（R3 新增，解开 R2 的 U2） | `0/6000 → 113/6000 = 1.88%`（09-25 19:23 用户消息转述）；独立读数 `jump=24/1146 = 2.1%`（09-26 11:51）、`26/1722 = 1.51%`（11:54）、`10/318 = 3.1%`（12:04） | 🟡 **有会话侧支撑**（"12/600" 与 "113/6000" 同源同量级）；**精确对照仍需 B12 复采** |
| 振荡陷阱缓解（部署后对照） | `ctrl_x` 交替 **3404 → 43**；静止帧 **31.6% → 6.4%**；`stuck_score` **1.0 → 0.17**；`anomaly_state` oscillating → idle；`coverage_pct` **8.3% → 28.4%** | 🟠 **对照非同场景**（致命熔岩地 → 石块堡垒 #d1e3）；X/Z 效率与 `waste_ratio` 仍劣于基线 |
| 记忆与路径避免（初步） | **来回振荡 0 次**；新细胞率 **41.4%** | 🟠 另一面：**回访率 48%**、覆盖平台期 **40–60% 时间无增长** ⇒ "具备基础空间记忆，但程度有限" |
| 25-P0-1 信用分配矩阵 | AST **134 写点 / 6 断口** | 🟢 |
| 工程基础设施完成度 | 会话自述"已完成并经 **292/292** 验证" | 🟠 只反映**工作区**；09-25 18:42 前"**部署到运行系统 0%**" |

> **三项必须保留的反向保留**：① 场景不严格可比；② **`stuck_score` 假绿使"stuck 已消除"不可靠**（先过 **B15**）；③ **B12 未完成前不得声称运动问题已解决**。

## A.9.7 未闭环线索的处置增量（U2 / U7 / U11 / I2 等）

| ID | 上文状态 | R3 处置 |
|:--:|---|---|
| **U2**（"jump 0/6000 → 12/600 无法验证"） | 记为无法验证 | **部分可解**：09-25 19:23:08 用户消息（`6c53f724-v2 L3063`）载明「**`jump` 帧数：0/6000 → 113/6000（1.88%）**」，且 09-26 11:51/11:54 独立读数同量级 ⇒ **"项目确实开始出现 jump"有会话侧支撑**；精确对照仍需按 §9 口径复采（→ **B12**） |
| **U11**（"+137/−41 无法复现"） | 记为无法复现 | **已解**：该数字是 `git commit` 自身的**三文件汇总行**（`51f62457-v2` 12:28:03 `L1098`：`3 files changed, 137 insertions(+), 41 deletions(-)`）；该文件 `--numstat` 确为 **115/39**（→ **G-1**） |
| **U7**（教练链路口径） | 未定位写入方 | **部分**：归因逻辑**靠 `advice_ts` + 文件 mtime**（解释了日志中 `advice_age=None`）；**仍未定位** 09-24 12:04 后停更的直接原因（→ **B14**） |
| **I2**（钳位请求写入方） | 推断·高 | **会话侧更强**：09-24 12:58:07 已**预测**"库内候选 `turn_bias=0.6/0.7` 落在 `CLAMP_BOUNDS["exploration.turn_bias"]=(0.0,0.25)` 之外…晋升后被钳位改写并回写磁盘 ⇒『被记录的本能』与『实际生效的参数』不一致"，09-25 活体三度观测到 `requested=0.7/0.6/0.9 → applied=0.25` ⇒ **"被预测 → 被观测"闭环完整** |
| **U3 / U4 / U16 / U17 / U18 / U19 / U20** | 未闭环 | **不变**（未施工）；其中 U4/U17 已由 §A.9.5 的 P2-3 行吸收；U19 由**新增困境 G** 承接 |

## A.9.8 与本文档其它块的冲突裁定

| 冲突点 | 以谁为准 |
|---|---|
| 09-25 去重口径 185 vs 206 | **以本块 C12 = 206 为准**（t3 §A.2 已定位差异来源） |
| "重复 617" vs "重复 1131"（本块初版值） | **以 C13 更正后 = 514 为准**（窗口域 `1209 − 695`；全快照域 `1826 − 1312`）。`617` = 窗口外无副本调用量；`1131` = 跨域相减，已作废（t6／F-1） |
| `fbcc3d7` 是否"有意回退" | **以本块 G-1 = 意外覆盖（`cp` 事故）为准** |
| 「P0-2/P0-4 不在活体」 | **以本块 G-2 = 过度推断、降级为待验证为准** |
| 「E8 规格承诺从未存在」 | **以本块 G-3 = 承诺过 + 派过单 + 未落到发布点为准** |
| 「E13 可复现假绿源」 | **以本块 G-4 = 部分成立（有反判据 `stuck_duration_true`）为准** |
| 「E1 在窗口内已记录」 | **以本块 G-5 = 09-26 12:36 发现时刻、窗口内无会话记录为准** |
| `833848c`/`38c8bae`/43 项 D「0 次命中」 | **以本块 G-7 为准**（38/176 次命中；43 项 D = pytest 夹具） |
| 既有条目是否被删除或放宽 | **没有**。§A.0–A.8 与正文 18 项**一条未删、一条未放宽**；本块只**追加**状态与性质声明 |

## A.9.9 复现与校验

```powershell
# 本文档自洽（连同执行计划与分析文档一起校验，必须 exit 0）
python scripts/verify_doc_citations.py

# 本块引用的 R3 证据源（只读）
#   docs/analysis/session-analysis-0924-0926.md      （t2，562 行 @t5 核验时点；t6 后就地更正，现 569 行）
#   docs/analysis/blindspot-crossvalidation.md       （t3，559 行 @t5 核验时点，7 节 + 附录 A；t6 后就地更正，现 564 行）
# 项目级合并结论
#   docs/analysis/project-state-consolidated.md      （t4）
```

## A.9.10 t6 返修勘误块（append-only；依据 `docs/analysis/newlogs-review.md` 的 F-1～F-10）

> **纪律**：本小节**只追加**，不改写 §A.9.1–A.9.9 的条目结构；上文与本节冲突者，**以本节为准**（本节最新）。**未删除任何条目、未放宽任何表述**。

| # | 级别 | t5 finding | 本节处置 | 落点 |
|:--:|:--:|---|---|---|
| **1** | **blocker** | **F-1**：`1826`（全快照）与 `695`（窗口去重）跨域相减 ⇒「重复副本 1131」错误，正确值 **514** | §A.9.1-C13 与引用规则已就地改写为**三段式（全快照域 / 窗口域 / 窗口外）+ 每段声明域**；并加入硬约束「**任何减法必须两项同域**」 | §A.9.1-C13、§A.9.8 |
| **2** | high | **F-2**：`model.py:2478` 只对 **@HEAD** 成立；当前工作区真实门在 **`model.py:2562-2566`** 且已 ratio 语义（`_jump_rate_ratio_gate=0.75` @ `model.py:678`） | 本文件正文（R1/R2 章节）**不含该引用**；更正落在 `project-state-consolidated.md` §1.2 与 `session-analysis-0924-0926.md`、`blindspot-crossvalidation.md`（各加 scope 标注 + 工作区口径） | 见 §A.9.10-依据列 |
| **3** | high | **F-3**：`gain("jump")` 实为 **4 处**（`model.py:1335/1849/1875/1906`）+ `main.py:3212`；`1842` 是注释行 | 同上（本文件正文无该引用）；**保留未推翻的子命题**"注入腿只有一条带增益" | `project-state-consolidated.md` §1.2、`session-analysis-0924-0926.md` §1.3/§8.1 |
| **4** | medium | **F-4**：87 处 write/edit 未声明口径 | 更正为「**调用 126**（逐快照唯一 (工具,路径) = **87**；全局唯一路径 **63**；全局唯一 (工具,路径) **69**）」，落在 t4 文档 §0.1 | `project-state-consolidated.md` §0.1 |
| **5** | medium | **F-5**：51 个未跟踪不可复现 | 更正为「**51 = 手工枚举的窗口产出子集**（判据缺失）；`git status ??` 实测 **74**，剔除本轮 3 份新文档后 **71**；命令 `git status --porcelain=v1 \| Where-Object {$_ -match '^\?\?'}`；测量时刻 2026-09-26 14:0x」 | `session-analysis-0924-0926.md` §5.2-U8/§6.2 + `project-state-consolidated.md` D-04/§4.2-B04 + 本计划附录 |
| **6** | medium | **F-6**：t2 自报 563 行 → 实测 **562** | **正文无需改写**（当时全文检索 `563` 的唯一命中是 inode `125256364637215400` 的片段，文档从未声明自报行数）。**权威值 = 562 行 @t5 核验时点**（`splitlines()` 与 `count("\n")` 两口径一致）；⚠️ **t6 对 t2 就地补注后现为 569 行** ⇒ 本文件对 t2 篇幅的引用一律写 **"562 行（t5 核验时点）"** | `project-state-consolidated.md` §6.3-7 |lidated.md` §6.3-7 |
| **7** | low | **F-7**：§0.3 误记"两项 B15/B16" | 更正为 **三项（`B15`/`B16`/`B17`）** | `project-state-consolidated.md` §0.3-4 |
| **8** | low | **F-8**：t3 的 O-1…O-10 / X-1…X-7 编号在 t4 中 0 次出现 | 新增 **附录 A.2 编号映射表**（17 条逐条 → 本文落点） | `project-state-consolidated.md` 附录 A.2 |
| **9** | low | **F-9**：`check_version.py` 未标路径 | 关键处补全 **`fly64/tests/check_version.py`**（t3 §2.0/§2.2、t4 D-02/B02/B-3/事件索引、本块 §A.9.3-困境 G） | 见 §A.9.10-依据列 |
| **10** | low（跨文档） | **F-10**：「差值恒为 11」不成立（实测 **68 / 32**） | 原文出现在 **`docs/analysis/blindspot-review-round2.md:396`（非 R3 产出、且**不在本任务 in-scope**）** ⇒ 仅在 t4 §6.3 登记更正 + 在 `session-analysis-0924-0926.md` §6.3 就地更正；**未修改该文件**，如需回改请另开任务 | `project-state-consolidated.md` §6.3-8、`session-analysis-0924-0926.md` §6.3 |
| **11** | — | **t3 措辞修正**：「会话全文零处提及 EVO-072/073」 | 改写为「**提及 3 处（12:24:27 锚点表回显 / 12:25:31 读文件 / 12:25:40 自述），但均未识别为待删对象**」；实质结论不变 | §A.9.2-G1、t3 §2.7、t4 D-03 |
| **12** | — | **pkill 计数修正**：「连续 6 轮 pkill」 | 改写为「**6 次 `write` 脚本轮次（11:54:25→12:02:59），实际执行 `pkill` 共 3 条（11:55:30 / 11:57:24 / 12:02:47）**」；崩溃归因结论不变（09-26 全天仅 `6c53f724-v3` 执行过 `pkill -f fly64.main`） | §A.9.3-困境 F、t3 §A.1、t4 D-10 |

> **本块结束**。本块为 2026-09-26 第三轮（一手会话）的 **append-only** 同步块，依据 t2/t3 的交付；**本块自身**未修改 t1/t3 产物，未触碰 `fly64/` 下任何源码与技能。**t6 返修见 §A.9.10**——其中对 t2/t3 的**就地更正**（F-1/F-2/F-3/F-5/F-9/F-10 + t3 措辞与 pkill 口径）是 t6 的动作，不计入本块。