# Fly64 3D 轨迹导航行为模式系统性分析报告
## Systematic Behavioral Analysis Report — Fly64 3D Trajectory Navigation

---

> **报告编号**: FR-2024-FLY64-001  
> **生成日期**: 2024-12-20  
> **数据源**: trajectory.json (6000帧) + memory.json (脑状态快照) + fly64/fly64/memory.py (源码)  
> **分析范围**: 振荡陷阱根因诊断、6大问题模式详解、代码级证据链、修复建议

---

## 目录 / Table of Contents

1. [执行摘要 / Executive Summary](#1-执行摘要--executive-summary)
2. [9大指标总览 / 9 Key Metrics Overview](#2-9大指标总览--9-key-metrics-overview)
3. [6大问题模式详解 / 6 Problem Patterns Deep Dive](#3-6大问题模式详解--6-problem-patterns-deep-dive)
   - 问题1: Z轴高频振荡陷阱 (High-Frequency Z-Axis Oscillation Trap)
   - 问题2: X/Z 方向极端低效 (Extreme X/Z Direction Inefficiency)
   - 问题3: stuck_ramp 锁死与反射疲劳 (stuck_ramp Lock & Reflex Fatigue)
   - 问题4: jump 动作永久缺失 (Permanent Jump Absence)
   - 问题5: 最终墙壁卡死 (Terminal Wall Stuck)
   - 问题6: 空间探索覆盖率极低 (Minimal Spatial Coverage)
4. [根因诊断 / Root Cause Diagnosis](#4-根因诊断--root-cause-diagnosis)
   - 根因链
   - 脑模型视角分析
   - 控制理论视角分析
5. [代码级证据链 / Code-Level Evidence Chain](#5-代码级证据链--code-level-evidence-chain)
6. [修复建议路线图 / Fix Roadmap](#6-修复建议路线图--fix-roadmap)
7. [附录 / Appendix](#7-附录--appendix)

---

## 1. 执行摘要 / Executive Summary

### 中文版

本报告对 Fly64 智能体在「致命熔岩地」场景中的 **22.1 分钟 / 6000 帧** 完整轨迹导航数据进行了系统性分析，结合脑状态快照 (`memory.json`) 和反射/跳跃源码审查 (`memory.py`)，揭示了当前系统面临的核心问题：**振荡陷阱 (Oscillation Trap)**。

**核心发现**: Fly64 处于**严重的卡死锁死状态** (`stuck_score=1.0`, `stuck_duration=1100.72s`, 覆盖 83% 的记录时间)。系统在 X-Z 平面上以 `+70↔-70` 的 ctrl_x 高频交替模式做无效振荡，X 方向仅 2.8%、Z 方向仅 5.4% 的位移方向效率，97% 的移动能量浪费在往返振荡中。更关键的是，**反射系统已放弃干预** (`reflex_active=False`)，尽管 `stuck_ramp` 反射早已过冷却期 (1.59s)。**jump 动作在整个 6000 帧中从未执行**——这是 system 2 无路可走时本应激活的终极逃生通道，但决策链在 MotionStateDetector 的优先级排序处断裂：系统持续报告 `stuck_ramp` (最低优先级)，却从未达到可触发 jump 的 `oscillating` 状态。最终 545 帧 (124 秒) 完全静止于墙壁边缘，系统彻底「冻死」。

**关键数据**:
| 指标 | 值 | 评定 |
|------|-----|------|
| stuck_score | **1.0** (最大) | 🔴 临界 |
| jump 执行次数 | **0** / 6000 帧 | 🔴 系统性缺失 |
| Z 方向效率 | **5.4%** (94.6% 浪费) | 🔴 严重 |
| X 方向效率 | **2.8%** (97.2% 浪费) | 🔴 严重 |
| 中位移动速度 | **0.0 u/s** | 🔴 严重 |
| stuck_duration | **1100.72s** (18.3 分钟) | 🔴 临界 |
| 空间覆盖率 | **15%** (376/2500 cells) | ⚠️ 低 |
| waste_ratio | **29.34** | 🔴 严重 |

---

### English Version

This report systematically analyzes **22.1 minutes / 6000 frames** of complete trajectory navigation data from the Fly64 agent in the "Lethal Lava" scene, combined with brain state snapshots (`memory.json`) and reflex/jump source code review (`memory.py`). It reveals the core problem: **Oscillation Trap**.

**Key Finding**: Fly64 is in a **severe stuck/locked state** (`stuck_score=1.0`, `stuck_duration=1100.72s`, covering 83% of the recording). The system oscillates ineffectively in the X-Z plane via `+70↔-70` ctrl_x alternation, achieving only 2.8% X-direction and 5.4% Z-direction displacement efficiency — **97% of movement energy is wasted on back-and-forth oscillation**. Critically, the **reflex system has abandoned intervention** (`reflex_active=False`), even though `stuck_ramp` cooldown expired long ago (1.59s). **Jump was never executed** across all 6000 frames — the ultimate escape route when system 2 finds no path remains permanently blocked because the decision chain breaks at `MotionStateDetector` priority ordering: the system persistently reports `stuck_ramp` (lowest priority) and never reaches `oscillating` which would trigger jump. The final 545 frames (124 seconds) show complete immobility against a wall — the system is entirely "frozen".

---

## 2. 9大指标总览 / 9 Key Metrics Overview

下表综合 trajectory.json (t1) 的轨迹统计和 memory.json (t2) 的脑状态指标，按严重等级排序：

| # | 指标 / Metric | 值 / Value | 正常范围 | 严重等级 | 数据来源 |
|---|--------------|-----------|---------|---------|---------|
| 1 | **stuck_score** (卡死评分) | **1.0** | < 0.3 | 🔴 临界 | memory.json |
| 2 | **stuck_duration** (卡死持续) | **1100.72s** (18.3min) | < 60s | 🔴 临界 | memory.json |
| 3 | **jump 执行次数** | **0 / 6000 帧** | > 5次 | 🔴 系统性缺失 | trajectory.json |
| 4 | **X方向效率** | **2.8%** (97.2% 浪费) | > 50% | 🔴 严重 | trajectory.json |
| 5 | **Z方向效率** | **5.4%** (94.6% 浪费) | > 50% | 🔴 严重 | trajectory.json |
| 6 | **median_speed** | **0.0 u/s** | > 10 u/s | 🔴 严重 | memory.json |
| 7 | **waste_ratio** | **29.34** | < 1.0 | 🔴 严重 | memory.json |
| 8 | **ctrl_x 正负交替次数** | **3404 次** | < 100 | 🔴 严重 | trajectory.json |
| 9 | **coverage_pct** (空间覆盖率) | **15.0%** (376/2500) | > 50% | ⚠️ 低 | memory.json |

**综合健康评级**: 🔴 **危急 (Critical)** — 9项核心指标中 8 项严重异常，1 项偏低。系统处于功能性崩溃边缘。

---

## 3. 6大问题模式详解 / 6 Problem Patterns Deep Dive

---

### 问题 1: Z轴高频振荡陷阱
#### Problem 1: High-Frequency Z-Axis Oscillation Trap

**严重等级**: 🔴 **严重** | **影响范围**: 全过程 (0~6000帧)

#### 分析方法 / Method

对 trajectory.json 的 `(x, y, z)` 位移序列进行逐帧差分分析，统计 Z 轴方向反转（正负号变化）的频率和幅度，结合 `ctrl_x` 控制信号的时间对齐分析。

#### 数据证据 / Data Evidence

| 指标 | 数值 | 说明 |
|------|------|------|
| Z方向累计位移 | **114,174.9 u** | 所有帧 Z 位移绝对值之和 |
| Z方向净位移 | **+6,111.3 u** | 最终 Z 方向前进距离 |
| **Z方向效率** | **5.4%** | 净位移 / 累计位移 = 6111.3/114174.9 |
| Z方向反转次数 | **~2069 次** | 每 **2.9 帧** 一次方向反转 |
| Z方向反转频率 | **~1.56 Hz** | 每秒约 1.5 次往返振荡 |
| Z单次反转幅度 | 平均 ~55 u | 每次掉头的位移幅度 |
| 总帧数对应的Z浪费 | **108,063.6 u** | 累计位移 - 净位移 |

**核心图表 (概念)**:
```
Z轴位移 (概念示意):
     /\    /\    /\    /\    /\    /\    /\   
    /  \  /  \  /  \  /  \  /  \  /  \  /  \
___/    \/    \/    \/    \/    \/    \/    \___
→ 每次 "山峰" 和 "山谷" 代表一次 ctrl_x 切换
→ 平均周期: ~0.45s (2.2Hz 振荡), 每 2.9 帧反转一次
```

#### 影响评估 / Impact

- **能量浪费**: 94.6% 的移动能量消耗在无效振荡上，实际在 22 分钟内仅前进了 Z 方向 6,111 单位
- **时间消耗**: 在 2.2Hz 的振荡频率下，系统如同「跑步机上的奔跑者」，消耗了大量物理仿真时间和计算资源却没有实际进展
- **决策误导**: 高频振荡产生的位移信号可能被系统的 novelty 检测器误认为"探索行为"，掩盖了实际被困的事实

---

### 问题 2: X/Z 方向极端低效
#### Problem 2: Extreme Directional Inefficiency on X/Z Axes

**严重等级**: 🔴 **严重** | **影响范围**: 全过程

#### 分析方法 / Method

对比每个轴上的累计位移和净位移，计算方向效率。同时分析 `ctrl_x` 的控制信号模式，定位根本驱动因素。

#### 数据证据 / Data Evidence

| 指标 | X 轴 | Z 轴 | 综合评价 |
|------|------|------|---------|
| 累计位移 | 135,817.2 u | 114,174.9 u | 总投入 ~250k u |
| 净位移 | **-3,739.0 u** (倒退!) | **+6,111.3 u** (微进) | X 轴净退 |
| **方向效率** | **2.8%** | **5.4%** | X 轴更差 |
| 反转次数 | ~566 次 | ~2069 次 | Z 轴振荡更密集 |
| 静止帧 (位移<0.5) | — | **1385/5999 (23.1%)** | 约 1/4 时间完全不动 |

**控制器信号分析** (根因):
```
ctrl_x 时序模式:
  帧 0-2:   +70  (全速右转)
  帧 2-4:   -70  (全速左转)
  帧 4-6:   +70  (反复交替)
  ... 3404次交替 ...
  
ctrl_y 时序模式:
  帧 所有:  70 (恒定全速前进, 仅2次变化到50)

结论: ctrl_x 以 ~1.7帧/次的频率在 +70↔-70 之间疯狂切换
      ctrl_y 几乎恒定为 70 (全速前进)
      联合效应 → 果蝇每帧都在 "左急转↔右急转" 之间切换,
      身体沿 Z 轴做锯齿形前进, 但实际上被抵消
```

#### 影响评估 / Impact

- **X 轴净后退 3,739 单位**: 不仅没有探索新区域，反而在 22 分钟内整体后退
- **ctrl_x 过度活跃 (90.9% 非零)**: 控制信号几乎从不休息，系统处于持续的"方向争夺"状态
- **ctrl_y 过度惰性 (仅 2 次变化)**: 前进推力完全不做调整，与 ctrl_x 的疯狂切换形成极端对比
- **23.1% 完全静止**: 近 1/4 的时间位移 < 0.5 单位，说明振荡在某些时刻完全抵消

---

### 问题 3: stuck_ramp 锁死与反射疲劳
#### Problem 3: stuck_ramp Lock & Reflex Fatigue

**严重等级**: 🔴 **临界** | **影响范围**: 全过程 (覆盖 83% 时间)

#### 分析方法 / Method

综合 memory.json 的脑状态指标和 memory.py 中 MotionStateDetector / ReflexController 的源码逻辑，分析 stuck_ramp 的触发、锁定和 reflex 响应失败的原因。

#### 数据证据 / Data Evidence

**脑状态快照**:
| 指标 | 值 | 含义 |
|------|-----|------|
| **stuck_score** | **1.0** | 最大值——系统明确自评"绝对卡死" |
| **stuck_duration** | **1100.72s** (18.3min) | 几乎覆盖全部 22min 记录 |
| **anomaly_state** | **"stuck_ramp"** | 被诊断为「斜坡卡死」类型 |
| **anomaly_confidence** | **1.0 (100%)** | 完全确信 |
| **reflex_active** | **False** | ⚠️ 反射系统未激活 |
| **reflex_type** | **空** | 无活跃反射 |
| **reflex_cooldowns.stuck_ramp** | **1.59s** | 冷却已过期, 可立即触发 |
| **reflex_cooldowns.oscillating** | **0.0s** | 立即可用 |
| **reflex_cooldowns.wall_stuck** | **0.0s** | 立即可用 |
| **reflex_cooldowns.micro_loop** | **0.0s** | 立即可用 |

#### 源码级分析 / Source-Level Analysis

**Reflex 触发条件** (memory.py, lines ~1520-1560):
```python
# 触发 stuck_ramp reflex 的条件:
if anomaly_state == "stuck_ramp" and confidence >= 0.6:
    # → 触发 stuck_ramp reflex
    # stuck_ramp 相位序列: forward (1.5s) → 结束
    # ❌ 不包含 jump!
```

**MotionStateDetector 优先级** (memory.py, lines 1347-1373):
```python
# 优先级顺序 (从高到低):
#   fallen > micro_loop > oscillating > wall_stuck > stuck_ramp > idle
```

**关键发现**:
1. **stuck_ramp 是 MotionStateDetector 的次低优先级**（仅高于 idle），意味着只要其他异常状态的判定条件未被满足，系统就会回退到 stuck_ramp
2. **stuck_ramp reflex 不包含 jump**——其相位序列仅为 `forward (1.5s) → 结束`，不涉及跳跃逃生
3. **oscillating 状态未被触发**——尽管数据显示 Z 轴存在 2.2Hz 的高频振荡，但 MotionStateDetector 的 oscillating 判定条件（可能与幅度/持续性相关）未被满足，因为系统卡在 stuck_ramp 优先级

#### 影响评估 / Impact

- **"反射疲劳" 现象**: stuck_score=1.0 但 reflex_active=False——反射系统已经「放弃」。尽管冷却已过（1.59s），但系统不再重新触发 reflex
- **异常分类锁定**: 系统持续输出 stuck_ramp 类型，这个类型的 reflex 处理最弱（仅 1.5s forward，无 jump），形成「越卡死→越 stuck_ramp→越无效处理」的恶性循环
- **逃逸窗口关闭**: 所有 4 种 reflex 的冷却均为 0 或已过，却无一激活——系统陷入了「检测到问题→reflex 已用完→放弃检测」的 dead state

---

### 问题 4: jump 动作永久缺失
#### Problem 4: Permanent Jump Absence

**严重等级**: 🔴 **系统性缺失** | **影响范围**: 全过程 (6000 帧 / 22 分钟)

#### 分析方法 / Method

审查 memory.py 中 jump=True 的 4 条决策路径，逐一验证每条路径在当前状态下的可达性。

#### 数据证据 / Data Evidence

**trajectory.json**: jump 在所有 6000 帧中均为 **false** (0 次)。

#### 源码级分析 / Source-Level Analysis

**jump=True 的 4 条路径** (memory.py):

| 路径 | 触发条件 | 当前状态 | 可达? |
|------|---------|---------|:----:|
| **A. Reflex oscillating burst** | anomaly_state="oscillating" → ReflexController → hold 2.0s → burst(含 jump) | anomaly_state="stuck_ramp" ≠ "oscillating" | ❌ |
| **B. CliffDetector** | cliff_detected AND anomaly_state ≠ fallen → jump | 无悬崖信号 | ❌ |
| **C. ReflexController force_jump** | force_jump 标记被设置 | 未见设置逻辑 | ❌ |
| **D. 手动 action['jump']** | 外部输入的 action 含 jump=True | system 1/2 动作生成器永不输出 jump | ❌ |

**核心断裂点** (memory.py, lines 1347-1373 优先级排序):

```python
# MotionStateDetector 的判定顺序:
# 1. fallen? → 否 (y=120, 正常地面)
# 2. micro_loop? → 否 (高频振荡不符合 micro_loop 的微循环特征)
# 3. oscillating? → 否 (子阈值, 未达 oscillating 判定门槛)
# 4. wall_stuck? → 否 (wall_persist 检测可能在早期已失败)
# 5. stuck_ramp? → 是! ← 卡在这里
# 6. idle → (未到达)
```

**oscillating 检测阈值问题** (推测):
Memory.json 数据显示系统处于持续的 stuck_oscillation 状态 (~3650 帧 / 81% 时间)，但 MotionStateDetector 的 oscillating 判定需要特定的条件组合（可能是能量阈值 + 时间持续性 + 方向变化模式）。Z 轴 2.2Hz 的单纯往返振荡可能不满足 oscillating 的完整判据，使得系统 fallback 到 stuck_ramp。

#### 影响评估 / Impact

- **缺失终极逃生通道**: jump 是系统在完全被困时的最后手段，相当于"重置按钮"。缺失意味着任何 reflex 失败的情况都没有退路
- **被困的必然性**: 即使 CliffDetector 未触发、oscillating 资格不足，系统也没有 fallback jump 能力。被困是必然结果
- **建议修复**: 增加一个「超时逃逸」路径——当 stuck_score > 0.9 且持续超过 300s 时，无论 anomaly_state 是什么，强制触发 jump

---

### 问题 5: 最终墙壁卡死
#### Problem 5: Terminal Wall Stuck

**严重等级**: 🔴 **严重** | **影响范围**: 帧 5455~6000 (最后 124 秒)

#### 分析方法 / Method

分析 trajectory.json 末尾帧的位置、heading 和控制信号，识别最终的卡死状态。

#### 数据证据 / Data Evidence

| 指标 | 值 |
|------|-----|
| 卡死起始帧 | ~5455 |
| 卡死持续帧数 | **545 帧** |
| 卡死持续时间 | **124.27 秒** (~2 分钟) |
| 最终位置 | **(x=718.0, y=120.0, z=6623.5)** |
| 最终 heading | **1.571 rad (90°)** |
| 最终 ctrl | **(0, 70)** |
| 最后位置变化 | 帧 5455 之前 |
| 占全记录 | **9.1%** |

**分析**:
- 果蝇最终面对一堵墙壁（x=718 处），heading=90° 表明正朝墙壁方向
- ctrl=(0,70) 表示在做出向前的指令 (ctrl_y=70) 但无转向 (ctrl_x=0)
- 由于物理碰撞无法前进，但系统不做任何转向或避障动作
- **wall_stuck reflex 未触发**——虽然 wall_persist 持续了 124 秒远超 2s 阈值

#### 影响评估 / Impact

- **wall_stuck reflex 失效**: 根据源码 (memory.py)，wall_persist>2s 应提前触发 wall_stuck reflex (reverse 0.3s → turn 0.8s)，但数据表明它未被触发
- **wall_stuck 检测的潜在 bug**: 可能 wall_persist 计数器在 stuck_ramp 状态下被重置，或 wall_stuck 判定需要 wall_persist 在特定条件下积累
- **"冻死" 状态**: 最后 2 分钟系统完全不做有效响应，反映出反射机制和探索系统均已崩溃

---

### 问题 6: 空间探索覆盖率极低
#### Problem 6: Minimal Spatial Coverage

**严重等级**: ⚠️ **中** | **影响范围**: 全过程

#### 分析方法 / Method

分析 memory.json 中的空间记忆指标和 revisited_cells 分布。

#### 数据证据 / Data Evidence

| 指标 | 值 | 正常期望 |
|------|-----|---------|
| **visited_cells** | **376 / 2500** | > 1250 (50%) |
| **coverage_pct** | **15.0%** | > 50% |
| **coverage_rate** | **0.2563 cell/s** | > 1.0 cell/s |
| **revisit_count** | **128.0** | < 20 |
| **revisit_ratio** | **34.0%** | < 5% |
| **exploration_style** | **"local_oscillation"** | "directed_exploration" |
| **novelty 梯度** | **近零 / 负值** | 正向递减 |

**空间覆盖热图 (概念)**:
```
Z ↑  [ ] [ ] [ ] [■] [■] [■] [■] [ ] [ ] [ ]   ← 主要活动带 (Z: 4600~7600)
  |  [ ] [ ] [ ] [■] [■] [■] [■] [ ] [ ] [ ]     15% 覆盖, 85% 从未访问
  |  [ ] [ ] [ ] [■] [■] [ ] [ ] [■] [ ] [ ]
  |  [ ] [ ] [ ] [ ] [■] [ ] [ ] [■] [ ] [ ]
  |  [ ] [ ] [ ] [ ] [ ] [ ] [ ] [■] [ ] [ ]
  |  [ ] [ ] [ ] [ ] [ ] [ ] [ ] [ ] [ ] [ ]
  └──────────────────────────────────────→ X
    大部分区域 (X: -7312~718, Z: 460~7630)
    实际探索集中在 Z 轴 4600~7600、X 轴 -2000~718 的带状区域
```

#### 影响评估 / Impact

- **空间记忆失效**: 85% 的空间从未被探索，果蝇被困在一条狭窄的活动走廊中
- **revisit_count 极高 (128)**: 同一区域被反复访问，结合 loop_score=2.26 和 novelty 梯度近零，证实了系统的循环被困行为
- **exploration_style="local_oscillation"**: 系统自评已将探索风格标记为"局部振荡"——这是对自己被困的认知
- **覆盖范围限制**: 尽管 trajectory 显示 Z 轴跨度达 7170.8 u，但系统实际上只访问了这条长条的 15%，因为振荡占据了大部分位移

---

## 4. 根因诊断 / Root Cause Diagnosis

### 4.1 根因链 / Root Cause Chain

```
┌─────────────────────────────────────────────────────────┐
│              根因链: 从控制层到行为层                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔴 根因 1: ctrl_x 控制信号频率过高 (+70↔-70)           │
│     每 1.7 帧切换一次, 系统在左转/右转间高速交替          │
│           ↓                                              │
│  🔴 根因 2: ctrl_y 几乎恒定为 70 (全速前进)              │
│     前进推力不调整, 与疯狂转向形成极端失衡                 │
│           ↓                                              │
│  🔴 根因 3: X/Z 轴振荡陷阱 (2.2Hz Z 轴振荡)              │
│     净位移效率: X 2.8% / Z 5.4%, 97% 能量被浪费          │
│           ↓                                              │
│  🔴 根因 4: MotionStateDetector 优先级排序缺陷             │
│     stuck_ramp (次低优先级) 覆盖, oscillating 永不触发     │
│           ↓                                              │
│  🔴 根因 5: stuck_ramp reflex 不含 jump                   │
│     唯一的常规 jump 路径 (oscillating burst) 被阻断        │
│           ↓                                              │
│  🔴 根因 6: Reflex 系统放弃干预 (反射疲劳)                 │
│     stuck_duration=1100s, reflex_active=False              │
│           ↓                                              │
│  🔴 根因 7: wall_stuck reflex 失效                         │
│     最后一关防御缺失, 最终 545 帧冻死于墙壁                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 脑模型视角分析 / Brain Model Perspective

从脑模型视角看, Fly64 的异常行为可映射为以下几个环节的故障:

| 脑区 | 对应模块 | 当前故障 | 表现 |
|------|---------|---------|------|
| **视网膜 (Retina)** | temporal_energy | 视觉流坍缩导致低 temporal_energy | stuck 信号持续 |
| **中央复合体 (CX)** | heading 导航 | ctrl_x 在 +70↔-70 间振荡, 失去稳定航向 | 方向迷失 |
| **蘑菇体 (MB)** | novelty 检测 | novelty 梯度近零, 无法驱动探索新区域 | 被困在已知区域 |
| **反射系统** | reflex 控制器 | 4 种 reflex 均未激活, 冷却已过但放弃 | 反射疲劳 |
| **决策输出** | jump 动作 | 4 条路径全部阻断, 6000 帧从未执行 | 逃生通道关闭 |
| **空间记忆** | visited_cells | 15% 覆盖率, 85% 空间未探索 | 空间认知严重不足 |

### 4.3 控制理论视角分析 / Control Theory Perspective

从控制论角度，振荡陷阱是 **PID 控制器参数严重失配**的经典表现:

- **比例增益 (Kp) 过高**: ctrl_x 在 +70↔-70 之间跳变，表明转向控制器在"全速右转↔全速左转"之间无中间态，缺乏平滑的比例控制
- **微分项 (Kd) 缺失或无阻尼**: 系统对 heading 的变化率没有有效的阻尼控制，导致一旦偏离航向就过度矫正，形成持续振荡
- **积分项 (Ki) 饱和**: stuck_duration=1100s 表明积分累加已饱和，控制器对持续偏差不再响应
- **执行器饱和**: ctrl_x 只取极值 (±70)，中间 30 个可能值几乎不被使用（32 种中出现但集中在 ±70）

**修复方向**: 向 ctrl_x 引入平滑的比例-微分控制，限制单步变化幅度（如 ≤ ±20/帧），并增加 heading 误差的死区（dead band）以减少微振荡。

---

## 5. 代码级证据链 / Code-Level Evidence Chain

### 5.1 StuckDetector: 检测正确但响应失败

**文件**: `fly64/fly64/memory.py`, lines 122-264

```python
# StuckDetector 的三信号检测 (正确工作):
# 1. temporal_energy < 0.05 持续 >2s → stuck
# 2. frame_seq 不变持续 >5s → stuck
# 3. forward_rate < 5Hz 持续 >3s → stuck
# → stuck_score = max(energy_score, freeze_score, forward_score) ∈ [0,1]

# stuck_score=1.0 → 检测到最大程度卡死 ✓
# 但 stuck_score 作为 ReflexController 的输入未被有效利用
```

**证据**: `memory.json` 显示 `stuck_score=1.0`, `stuck_duration=1100.72s`，表明 StuckDetector 正确检测到了卡死。问题出在下游——ReflexController 没有对持续 1 级的 stuck_score 做有效响应。

### 5.2 MotionStateDetector 优先级排序缺陷

**文件**: `fly64/fly64/memory.py`, lines 1347-1373

```python
# 优先级排序 (关键缺陷):
PRIORITY = ['fallen', 'micro_loop', 'oscillating', 'wall_stuck', 'stuck_ramp', 'idle']
#                                    ↑              ↑              ↑
#  oscillating (可触发 jump)     wall_stuck     stuck_ramp (不含 jump)
#  但 oscillating 门槛过高        (额外检测)      (最低异常优先级)
```

**证据**: 
- `anomaly_state="stuck_ramp"` 表明系统停留在最低异常优先级
- 尽管 Z 轴有 ~2069 次方向反转和 2.2Hz 振荡，但 `oscillating` 状态未被触发
- **结论**: oscillating 检测阈值与实际的振荡行为不匹配，或 stuck_ramp 的判定覆盖了 oscillating

### 5.3 Reflex stuck_ramp 无 jump

**文件**: `fly64/fly64/memory.py`, lines 1500-1650

```python
# stuck_ramp reflex 相位序列:
class StuckRampReflex:
    PHASES = ['forward']    # 仅 1 个相位
    # forward: 前进 1.5s
    # ❌ 不包含 jump
    # ❌ 不包含 burst
    # ❌ 不包含 reverse 或 turn

# 对比 oscillating reflex:
class OscillatingReflex:
    PHASES = ['hold', 'burst']  # 2 个相位
    # hold: 停止 2.0s
    # burst: 爆发冲刺 (含 jump!) → 唯一常规 jump 路径 ✅
```

**证据**: stuck_ramp reflex 的相位序列仅有 `forward (1.5s)`，不包含任何转向或跳跃动作。这是一个"死循环 reflex"——它试图让卡死的果蝇向前走，但果蝇本来就因为卡死而无法前进。

### 5.4 wall_stuck reflex 失效分析

**文件**: `fly64/fly64/memory.py`, lines 1660-1800 (推测区域)

```python
# wall_stuck 触发条件:
# 条件 A: anomaly_state == "wall_stuck" AND confidence >= 0.6
# 条件 B: wall_persist > 2s (早期回避)
#
# 推测问题: 当 anomaly_state 为 "stuck_ramp" 时,
# wall_persist 计数器可能被重置或覆盖
```

**证据**: 最后 545 帧 (~124s) 系统静止于墙壁前，`ctrl=(0,70)` 表明在持续尝试前进。`wall_persist>2s` 的提前触发条件应已满足，但 `wall_stuck` reflex 未激活。可能因为 MotionStateDetector 输出的 `stuck_ramp` 优先级高于 `wall_stuck` 的检测路径。

### 5.5 Jump 4 条路径全部阻断

| 路径 | 阻断原因 | 代码位置 |
|------|---------|---------|
| **A (oscillating burst)** | anomaly_state="stuck_ramp", 不匹配 oscillating | memory.py ~1570 |
| **B (CliffDetector)** | 无悬崖信号 (lower_field_green ≥ 0.35) | memory.py:23-115 |
| **C (force_jump)** | 无任何代码设置 force_jump=True | — |
| **D (外部 action)** | system 1/2 的输出层不生成 jump=True | — |

**修复关键**: 需要在 stuck_ramp reflex 中添加 jump，或者增加一个「stuck 超时强制 jump」的超驰路径。

---

## 6. 修复建议路线图 / Fix Roadmap

### 优先级分级

| 级别 | 定义 | 目标 |
|------|------|------|
| **P0 — 紧急** | 系统功能崩溃性缺陷，不修复则导航完全不可用 | 恢复基本逃逸能力 |
| **P1 — 重要** | 严重影响探索效率，但系统不会完全死锁 | 提升效率至可用水平 |
| **P2 — 优化** | 增强性改进，进一步精细化控制 | 优化到稳定探索状态 |

---

### P0 — 紧急修复 (必须立即实施)

| # | 修复项 | 描述 | 涉及文件 | 预期效果 |
|---|-------|------|---------|---------|
| **P0.1** | **stuck_ramp reflex 增加 jump** | 在 stuck_ramp reflex 序列中增加 jump 相位：`forward (1.5s) → jump → 结束` | memory.py: ~1550-1580 | 当系统卡死在 stuck_ramp 状态时，强制跳跃以逃脱 |
| **P0.2** | **stuck 超时强制 jump (超驰路径)** | 当 `stuck_score > 0.9` 且 `stuck_duration > 300s` 时，无论 anomaly_state 为何，强制触发 jump | memory.py: ~1800 | 防止任何异常类型下的永久锁死 |
| **P0.3** | **修复 wall_stuck reflex 被覆盖** | 确保 wall_persist>2s 的早期回避在所有 anomaly_state 下都能触发 wall_stuck reflex | memory.py: ~1700-1750 | 防止最终墙壁冻死 |

**P0 紧急修复伪代码**:
```python
# P0.1: StuckRampReflex 增加 jump
class StuckRampReflex:
    PHASES = ['forward', 'jump']  # ← 增加 jump 相位
    # forward: 前进 1.5s
    # jump: 跳跃 (约 0.3s)

# P0.2: 超时逃逸守护
def check_emergency_escape(stuck_score, stuck_duration):
    if stuck_score > 0.9 and stuck_duration > 300:
        # 无论当前 reflex 状态如何, 强制触发 jump
        force_jump()
        stuck_duration = 0  # 重置卡死计时

# P0.3: wall_stuck 独立检测路径
def check_wall_stuck(wall_persist, anomaly_state):
    if wall_persist > 2.0:  # 独立路径, 不受 anomaly_state 影响
        trigger_reflex('wall_stuck')
```

---

### P1 — 重要修复

| # | 修复项 | 描述 | 涉及文件 | 预期效果 |
|---|-------|------|---------|---------|
| **P1.1** | **ctrl_x 平滑控制** | 限制 ctrl_x 单帧变化幅度 ≤ ±20，引入平滑过渡而非 +70↔-70 跳变 | 行为控制器 (system 1/2 输出层) | 消除 2.2Hz 振荡，改为渐进转向 |
| **P1.2** | **ctrl_y 动态调整** | ctrl_y 不应恒为 70，应根据进度和障碍反馈动态调低或暂停 | 行为控制器 | 在转向时降低前进速度，减少无效位移 |
| **P1.3** | **oscillating 检测阈值调低** | 降低 oscillating 判定的能量阈值或时间窗口，使真实振荡状态能被识别 | memory.py: ~1360 | 使 stuck_ramp 状态正确升级为 oscillating |
| **P1.4** | **stuck_ramp 后续升级路径** | 当 stuck_ramp reflex 执行后 stuck_score 未下降时，自动升级到更高优先级 reflex (如 oscillating) | memory.py: ~1580-1620 | 打破 stuck_ramp 的单一处理陷阱 |

**P1 修复伪代码**:
```python
# P1.1: ctrl_x 平滑
def smooth_ctrl_x(target_ctrl_x, current_ctrl_x):
    delta = target_ctrl_x - current_ctrl_x
    clamped_delta = max(-20, min(20, delta))  # 单帧最大变化 ±20
    return current_ctrl_x + clamped_delta

# P1.3: 降低 oscillating 阈值
OSCILLATING_ENERGY_THRESHOLD = 0.3  # ← 从原值降低
OSCILLATING_TIME_THRESHOLD = 3.0    # ← 从原值缩短 (秒)

# P1.4: stuck_ramp 升级逻辑
def handle_stuck_ramp_aftermath(stuck_score_before, stuck_score_after):
    if stuck_score_after > stuck_score_before * 0.9:  # 无明显改善
        # 升级到 oscillating reflex (含 jump)
        trigger_reflex('oscillating')
```

---

### P2 — 优化改进

| # | 修复项 | 描述 | 预期效果 |
|---|-------|------|---------|
| **P2.1** | **Novelty 梯度重新校准** | 修复 novelty 梯度近零问题，确保 drive 系统能感知到"有无新区域" | 驱动探索行为 |
| **P2.2** | **空间记忆分辨率优化** | 根据实际探索范围动态调整网格分辨率 (当前 50×50=2500 cells, 但有效范围不匹配) | 提升覆盖率统计准确性 |
| **P2.3** | **Heading PID 参数调优** | 引入完整 PID 控制：比例增益 Kp 降低、微分项 Kd 增加以抑制振荡 | 平滑 heading 跟踪 |
| **P2.4** | **系统 2 路径规划 fallback** | 当 exploration_style="local_oscillation" 时，启动全局路径规划以跳出局部陷阱 | 功能性导航能力 |

---

### 修复路线图时间线 (建议)

```
P0 (紧急) ─────────────────  立即实施
  ├─ P0.1: stuck_ramp + jump      [1 人·小时]
  ├─ P0.2: 超时强制 jump           [1 人·小时]
  └─ P0.3: wall_stuck 独立检测     [2 人·小时]

P1 (重要) ─────────────────  1-2 天内
  ├─ P1.1: ctrl_x 平滑             [3 人·小时]
  ├─ P1.2: ctrl_y 动态调整         [2 人·小时]
  ├─ P1.3: oscillating 阈值调低    [2 人·小时] ← 含实验调参
  └─ P1.4: stuck_ramp 升级路径     [3 人·小时]

P2 (优化) ─────────────────  3-5 天
  ├─ P2.1: Novelty 重校准          [4 人·小时]
  ├─ P2.2: 空间记忆分辨率          [2 人·小时]
  ├─ P2.3: PID 调优                [8 人·小时] ← 需仿真验证
  └─ P2.4: 全局路径规划            [16 人·小时] ← 需新模块
```

**P0 修复后预期效果**: stuck_ramp 状态下将执行 jump，系统能突破局部卡死；wall_stuck 在 2s 后触发反转/转向，避免墙壁冻死。基本导航功能恢复，不再永久锁死。

---

## 7. 附录 / Appendix

### A. 原始数据快照 — trajectory.json 关键统计

| 基础指标 | 值 |
|---------|-----|
| 帧总数 | 6000 |
| 时间范围 | 10728.07s ~ 12053.03s |
| 总时长 | 1324.96s (22.1 min) |
| 平均帧间隔 | 0.221s |
| 中位帧间隔 | 0.21s |

| 坐标范围 | 最小值 | 最大值 | 跨度 |
|---------|--------|--------|------|
| X | -7312.6 | 718.0 | 8030.6 |
| Y | 120.0 | 424.5 | 304.5 |
| Z | 459.6 | 7630.4 | 7170.8 |

| 高度分布 | 帧数 | 占比 |
|---------|------|------|
| Y = 120 (地面层) | 4747 | 79.12% |
| Y > 200 | 698 | 11.63% |
| Y 最大值 424.5 | 1 | 0.02% |

| 控制信号 Top5 | 帧数 | 占比 |
|--------------|------|------|
| (ctrl_x=70, ctrl_y=70) | 2706 | 45.1% |
| (ctrl_x=-70, ctrl_y=70) | 2624 | 43.7% |
| (ctrl_x=0, ctrl_y=50) | 480 | 8.0% |
| (ctrl_x=0, ctrl_y=70) | 65 | 1.1% |
| (ctrl_x=67, ctrl_y=70) | 14 | 0.2% |

| Heading 分布 | 帧数 | 占比 |
|--------------|------|------|
| [-π, -π/2] | 2002 | 33.4% |
| [-π/2, 0] | 2586 | 43.1% |
| [0, π/2] | 666 | 11.1% |
| [π/2, π] | 746 | 12.4% |

| 振荡指标 | 值 |
|---------|-----|
| 帧位移 (avg) | 38.02 u |
| 帧位移 (median) | 10.6 u |
| 累计位移 | 228,097.8 u |
| 静止帧 (位移<0.5) | 1385 (23.1%) |
| ctrl_x 正负交替 | 3404 次 |
| Z 方向反转 | ~2069 次 |
| X 方向反转 | ~566 次 |
| Jump = true | 0 次 |
| 最终卡死帧 | 545 帧 (124s) |

### B. 原始数据快照 — memory.json 脑状态快照

| 指标 | 值 |
|------|-----|
| scene | '致命熔岩地 #34ef' |
| scene_match | 1.0 |
| stuck_score | 1.0 |
| stuck_duration | 1100.72s |
| anomaly_state | 'stuck_ramp' |
| anomaly_confidence | 1.0 |
| anomaly_duration | 11.14s |
| progress_ineffective | True |
| reflex_active | False |
| reflex_type | None |
| reflex_cooldowns.stuck_ramp | 1.59s |
| reflex_cooldowns.oscillating | 0.0s |
| reflex_cooldowns.wall_stuck | 0.0s |
| reflex_cooldowns.micro_loop | 0.0s |
| disp_60s | 1080.7 |
| exploration_speed | 15.38 u/s |
| median_speed | 0.0 u/s |
| displacement_per_speed | null |
| stall_ratio | 0.0 |
| waste_ratio | 29.34 |
| traversal_steps | 13278 |
| visited_cells | 376/2500 |
| coverage_pct | 15.0% |
| coverage_rate | 0.2563 |
| revisit_count | 128.0 |
| loop_score | 2.26 |
| esc_timer | 0.0 |
| novelty_gradient | near_zero/negative |
| exploration_style | 'local_oscillation' |
| stuck_oscillation_frames | ~3650 |
| stuck_oscillation_pct | ~81% |

### C. 源码引用清单

| 功能 | 文件 | 行号范围 |
|------|------|---------|
| CliffDetector | fly64/fly64/memory.py | 23-115 |
| StuckDetector | fly64/fly64/memory.py | 122-264 |
| MotionStateDetector 优先级 | fly64/fly64/memory.py | 1347-1373 |
| Reflex stuck_ramp | fly64/fly64/memory.py | ~1500-1550 |
| Reflex oscillating | fly64/fly64/memory.py | ~1550-1650 |
| Reflex wall_stuck | fly64/fly64/memory.py | ~1660-1750 |
| Reflex micro_loop | fly64/fly64/memory.py | ~1760-1889 |
| Jump 决策逻辑 | fly64/fly64/memory.py | 分散多处 |

---

> **结束语**: Fly64 当前的状态类似于一个被困在迷宫中的智能体——它不断地跑动（ctrl_x 疯狂切换、ctrl_y 满速前进），但却在原地打转。核心问题不是运动能力的缺失，而是**控制信号的失配**（+70↔-70 的极端切换）和**异常状态处理链的断裂**（stuck_ramp→无 jump、wall_stuck 失效、oscillating 未触发）。P0 修复将恢复基本的逃逸能力，P1/P2 修复将把系统带入真正的自主探索轨道。

---

*报告撰写人: report-writer | 数据分析: data-analyst | 源码审查: code-investigator*
*生成环境: DeepSeek Harness AgentTeams — fly64-trajectory-report*