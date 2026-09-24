# Fly64 脑模型自治进化方案 (Autonomy Evolution Plan)
## Brain-Native Self-Evolution & Autonomy Plan — task `t4` deliverable

> **文件**: `docs/analysis/fly64-autonomy-evolution-plan.md`
> **作者**: solution-designer · 团队 `fly64-autonomy-evolution` · 任务 `t4`
> **attempt_id**: `46b5414e-6d4c-44d9-b4f0-84199452de32`
> **t6 返修（本次）**: brain-architect · attempt `c8eda485-bd26-497d-854c-61b92bb0eed1`
> **依据**: `docs/analysis/analysis-t5-adversarial-verification.md`（verdict = **needs_revision**：1 blocker + 1 high + 4 medium + 6 low）
> **返修范围**: F1–F12 逐条修复，**逐条对照表见 §15**。骨架（主因排序 M1–M4、实施顺序、三层九组拓扑）**未改动**；
> t5 核验通过项（主因判定与其 t1/t2/t3 证据引用、无新增 `control.*` 写入点、未把主因写成控制/反射层、
> 对原报告 P0.1/P0.2/P0.3/P1.1 的否定与技术理由、H1–H14 登记纪律、版本边界 H1、伪影引用纪律、
> A 类 11 项 ↔ t3 A1–A11 与 B1–B5 对应）**逐字保留**。
> **输入（全部完整通读）**:
> - `docs/analysis/fly64-trajectory-behavior-report.md`（714 行，原报告）
> - `docs/analysis/analysis-a4-autonomy-surface-inventory.md`（t1，475 行，37 表面 S1–S37）
> - `docs/analysis/analysis-t2-evolution-pipeline-failure.md`（t2，779 行，六处失效）
> - `docs/analysis/analysis-t3-primary-factor-determination.md`（t3，443 行，主因判定 M1–M4）
> - 代码基线（本机实测）：`git rev-parse HEAD` = **`cca66648a204043d881da502cf996b15882ad289`**
>   （`fly64/fly64/main.py` `BRAIN_VERSION = "2.24.0"`（:49）、`SKILL_VERSION = "3.5.1"`（:50）；
>   `fly64/skills/evolution_skill.py` `SKILL_VERSION = "3.5.0"`（:42））
> **方法**: 只读复核 + 独立探针（`.tmp/a4_plan_probe.py`，本文件外未写入除探针与产物的任何仓库文件）
> **本文件是 t4 的唯一交付物**；t6 对**同一文件**做返修（不是新增交付物），对照见 §15。

---

## 0. 证据分级与边界声明（必须最先读）

本方案使用四层证据，**每一条结论都标注所属层**。凡超出一层的断言，一律降级为待验证假设（§13）。

| 层 | 内容 | 可复现性 | 本方案中的用法 |
|---|---|---|---|
| **E-1** | 本机 `HEAD=cca6664` 的直接代码阅读（文件:行号，本报告作者逐一打开核对） | ✅ 可复现 | **判定依据**；凡涉及"当前代码结构"的结论只允许用 E-1 |
| **E-2** | t1/t2/t3 的真实命令与真实输出（探针、`DiagnosisEngine` 回放、`--phase6`、`--funnel`、`git log -S`） | ✅ 可复现 | 判定依据，注明出处 |
| **E-3** | 本报告独立探针 `.tmp/a4_plan_probe.py` → `.tmp/a4_plan_probe_out.json`（2026-09-24 t4 执行） | ✅ 可复现 | 只用于**算术/接线可达性**（见下） |
| **E-4** | 原报告公布的 `memory.json` 数值（`stuck_score` / `stuck_duration` / `anomaly_state` / `reflex_active` / `median_speed` 等） | ❌ **HEAD 上不可复现**（t1 §5.2、t2 §10.1、t3 §1.3 共四处矛盾） | 仅作**被审视对象**，并强制标注「检测伪影」+「版本边界 H1」 |

### 0.1 三条硬边界（不得越界断言）

1. **`.tmp/fly64_trajectory.json`（6000 点）与 HEAD 不相容**（t3 §1.4，本次新发现）。
   推理链全部落在可复现证据上：HEAD 下 `deadlock_burst_ready` 的前置是行为量 OR
   （`git log -S deadlock_burst_ready` → 仅 `6d0aa42` / 2026-09-23 08:36），而 `stuck_duration`
   伪造为单调增长 ⇒ **HEAD 下 burst 必触发**，占空比 200/500 tick、写 `control.y = 127`
   （`main.py:2046-2086`）；实测 `ctrl_y ∈ {70, 50}`、`127` 出现 **0/6000**。
   ⇒ **原报告描述的是一个更早修订的运行点。据其得出的 4/5/6/7 层根因不成立。**
   ⇒ **本方案的全部设计只建立在「读 HEAD 代码可直接证实」的证据上。**
2. **本机无 `.cache/malecns/manifest.json`**（t1 实测不存在）⇒ 真实连接组的运行点**无法离线复现**。
   E-3 探针使用 `FlyModel(demo=True)`（modeled graph，n=4096），其运动池发放退化为 100%
   （本次实测 `jump_pool_spike_rate_mean = 1.0`、`forward_rate_mean = 1.0`）。
   ⇒ **E-3 只证明接线、算术与阈值可达性，不代表真实运行点**；任何需要真实发放率的结论
   一律登记为假设（§13 H5/H6/H7）。
3. **仿真时间无墙钟换算**：轨迹 `t ∈ [10728.07, 12053.03] s` 是会话内时间
   ⇒ 不能断言故障发生在 t2 观测到的 2026-09-17→09-24 停摆窗口内（假设 H9）。

### 0.2 本方案自始至终遵守的四条用户硬约束

| 约束 | 本方案的落实方式 |
|---|---|
| **不得向 `main.py` 添加硬编码控制代码** | §5 全部 4 个 M1 机制 + §6 M2 状态机 + §7 M4 闭环，**没有一条新增控制分支**；所有改动都是"让已有信号到达"或"把输出面换成脑参数/增益/突触空间"。§9 逐条列出被否决的路线（含原报告 P0.1/P0.2/P0.3/P1.1/P1.3/P1.4 的替代写法）。 |
| **必须正面回答"移除闭环唯一输出面"** | §7.1 给出新输出面契约（落点 = `brain_tunable_params.json` 的脑参数空间 + 增益/通路空间）；§7.2 给出**可信适应度**的五段修复与 A/A 零假设门。 |
| **以 t1 的 5 个脑侧可改点为骨干** | §5.1–§5.5 逐一展开为可实施的条目（每项含作用机制 / 数据流 / 文件与接口 / 验证 / 回退）。 |
| **不得把伪影与假设当断言** | §2.3 伪影链、§13 假设清单、全文凡引用 `memory.json` 数值处均带「检测伪影」「H1」标注。 |

---

## 1. 执行摘要 / Executive Summary

### 1.1 中文版

Fly64 的「振荡陷阱 / 终态卡死」**不是一个控制参数问题**。本方案在 t1/t2/t3 的判定基础上，把它重新表述为一个**脑模型没有给自己留出"能起作用的作用点"、也读不出"自己有没有变好"的问题**，并据此给出一套只依赖脑模型自身机制（神经调节增益、突触可塑性、固有兴奋性稳态、仲裁状态机、参数级进化）的完善路线。

**主要因素（直接采用 t3 §5.2 的判定，本方案不另立）**

| 序 | 主因 | 性质 | 本方案对应章节 |
|---|---|---|---|
| **M3** | 观测/检测口径缺陷（单位契约、门限多口径、伪影外溢、闭环不记观测值） | **解锁条件 / 破环点** | §4（P0） |
| **M1** | 信用分配断口：决定行为的变量（`raw_x`/`raw_y`/`jump`，`model.py:2282,2283,2478`）与所有自适应面不重叠 | **决定性主因** | §5（P1） |
| **M2** | 仲裁层：`_vote()` 首命中即返回（`memory.py:1361-1373`），无竞争/无升级/无超驰；四个"升级或逃离"机制各有恒真/恒假前置 | **直接主因** | §6（P2） |
| **M4** | 进化闭环：运行性 + 诊断面 + 输出形态 + 适应度 | **必要条件，非行为成因** | §7（M4 与 M3 并行） |

**实施顺序**：M3 → M1 → M2；M4 与 M3 并行。M1↔M4 互为前提，**破环点就是 M3**。

**三条最关键的设计判断**

1. **"排除硬编码控制补丁"不是删掉几条 `if`，而是移除闭环当前唯一的输出面。** t2 已证：19 条 fix 中 16 条可执行代码行数 = 0（合计 7 行代码 vs 87 行注释），16 个 pattern 中 8 个把 `fix_files` 指向 `main.py`；唯一真正写入控制的 `fix_0013` 就是 `control.x = rng.integers(60,80); control.y = 40`，且 `effective = false`（baseline 458.98 → post 464.72 **更差**）。因此 §7.1 必须给出**新的输出面**，否则"排除补丁"等于把闭环彻底关掉。
2. **原报告 P0.1/P0.2 的技术前提是错的，不只是价值观偏好。** 报告称"jump 的 4 条路径全部阻断在 `memory.py`"，但 HEAD 上 jump 的**唯一执行门**是 LIF 解码 `jump = jump_rate > 0.04`（`model.py:2478`），它**对 `anomaly_state` 没有任何依赖**（t1 §1.6）。报告列的 4 条路径（oscillating burst / CliffDetector / force_jump / 外部 action）都是次级路径。在 `stuck_ramp` 反射里塞 jump，改的是一个**在观察 run 中从未持有操纵权的层**。
3. **闭环目前测不出任何差别，所以任何参数空间都会退化成盲搜。** `--phase6` 的 68 个唯一试验里 **41 个 delta 恰为 0.0（60.3%）**、66/68 的 `|delta| ≤ 0.03`、commit 率 1.47%（t2 §5）。本方案在 §7.2 给出五段修复，并**把 A/A 零假设门作为"允许改 fitness 之前必须先通过"的前置**。

### 1.2 English Version

Fly64's "oscillation trap / terminal freeze" **is not a control-parameter problem**. Building on the t1/t2/t3 determinations, this plan restates it as a brain-model problem: *the brain never gave itself an adaptation surface that can reach the variables which actually decide behaviour, and it cannot read out whether it has improved.* The plan therefore relies exclusively on brain-native mechanisms — neuromodulatory pathway gain, synaptic plasticity, intrinsic-excitability homeostasis, an arbitration state machine, and parameter-level evolution.

**Primary factors (adopted verbatim from t3 §5.2; not re-derived here)**

| Ord | Factor | Nature | Section |
|---|---|---|---|
| **M3** | Observation/detection semantics defects (unit contract, four competing jump thresholds, artifact spill-over, loop records no observed values) | **Unlock condition / cycle-breaker** | §4 (P0) |
| **M1** | Credit-assignment break: the behavioural decision variables (`raw_x`/`raw_y`/`jump`, `model.py:2282,2283,2478`) do not overlap any adaptive surface | **Decisive cause** | §5 (P1) |
| **M2** | Arbitration: `_vote()` returns on first hit (`memory.py:1361-1373`) — no competition, no escalation, no override; all four escape/escalation mechanisms carry an always-true/false precondition | **Direct cause** | §6 (P2) |
| **M4** | Evolution loop: liveness, diagnosis surface, output form, fitness | **Necessary condition, not a behavioural cause** | §7 (parallel with M3) |

**Order: M3 → M1 → M2; M4 in parallel with M3.** M1 ↔ M4 are mutually prerequisite; **M3 is the cycle-breaker.**

**Three decisive design judgements**

1. **Excluding hard-coded control patches removes the loop's only output surface — it is not "deleting a few `if` statements."** Of 19 fixes, 16 contain zero executable lines (7 code lines vs 87 comment lines); 8 of 16 patterns point their `fix_files` at `main.py`; the only fix that truly wrote control was `fix_0013` (`control.x = rng.integers(60,80); control.y = 40`), recorded `effective = false` (458.98 → 464.72, i.e. *worse*). §7.1 therefore specifies the replacement surface.
2. **The original report's P0.1/P0.2 rest on a factually wrong premise.** On HEAD the only executing jump gate is the LIF decode `jump = jump_rate > 0.04` (`model.py:2478`), which has **no dependence on `anomaly_state`** (t1 §1.6). Injecting jump into the `stuck_ramp` reflex edits a layer that never held authority in the observed run.
3. **The loop currently cannot resolve any difference, so every parameter space degenerates into blind search.** 41/68 unique trials had a delta of exactly 0.0 and 66/68 stayed below the 0.03 gate (commit rate 1.47%). §7.2 fixes this in five stages and gates all fitness changes behind an A/A null test.

---

## 2. 问题深化分析

### 2.1 症状与归因的三次修正（t1 → t2 → t3 → 本方案）

| 原报告主张 | t1 | t2 | t3 | 本方案采用 |
|---|---|---|---|---|
| 主因在控制层（`ctrl_x` 高频切换）/ 反射层（反射疲劳） | 提出"jump 主路径是 LIF 解码，与 anomaly 无关" | 用真引擎证明故障终态不在 pattern 可命名空间内 | **归因错**：4/5/6/7 层建立在旧修订 + 伪影上 | **不采用**。主因 = M1/M2/M3/M4 |
| `stuck_score=1.0`、`stuck_duration=1100.72` 是"卡死证据" | 判定为单位契约缺陷产物 | 判定为"检测伪影" | 补第四段（泄放被覆盖）+ 外溢链 | **强制标注「检测伪影」**（§2.3） |
| `MotionStateDetector` 优先级排序缺陷 | — | — | `_vote` 中 **`oscillating` 在 `stuck_ramp` 之前**（`memory.py:1367` 先于 `:1371`）⇒"优先级覆盖"不成立 | 真缺陷 = **检测口径与实测翻转周期同量级**（§2.4） |
| "反射疲劳"（`reflex_active=False`） | — | — | 伪影 + HEAD 分类不可复现 + 轨迹显示反射层从未取得操纵权 | **不成立**（§2.5） |
| 闭环停摆是"未自治修复"的主因 | — | 停摆 7 天、无守护 | **反证**：运行期 4.46 天 / 13728 iter / 11 fix / **0 effective**，窗口内 top pattern 已含 `ramp_trap` 5631 次 | 停摆属**组织性因**，与 fitness/输出形态并列构成 M4，**不是行为成因** |

### 2.2 重新表述的问题定义（本方案的出发点）

> **Fly64 的自治能力缺失，表现为"两断一漏"**：
> **断口一（M1）**：所有自适应面（增益、MBON 权重、教练参数、进化参数）都作用在"注入腿"，
> 而行为由三个饱和/硬门解码器决定 —— `raw_y = clip((forward_rate-0.008)·2000, 0, 70)`（`model.py:2282`）、
> `raw_x = clip(turn_rate·1100, ±70)`（`model.py:2283`）、`jump = jump_rate > 0.04`（`model.py:2478`）。
> **断口二（M2）**：仲裁层是固定判定表（`memory.py:1361-1373`），没有竞争/升级/超驰语义，
> 且四个可用于升级或逃离的原生机制各有一个恒真/恒假前置。
> **漏（M3）**：观测与门限语义成体系不一致（单位契约、4 个 jump 口径、伪影外溢、闭环不记观测值），
> 使"是否变好"无法判定。
> **后果**：闭环搜索 4.46 天 → 60.3% 试验"什么都没测到" → 只能产出硬编码补丁 → 补丁因前置被别的机制钉死而失效
> （`main.py:2040-2054` 的注释自述就是这一现象的现场记录）。

### 2.3 检测伪影链（必须与"真实卡死"分开处理）

```
memory.py:135  rate_threshold: float = 5.0            # 声明为 Hz
memory.py:206  if forward_rate < self.rate_threshold: # 传入的是 per-tick 比例 ∈ [0,1]
memory.py:217  r_score = min(1.0, self._rate_low_s / self.rate_stuck_s)   # rate_stuck_s = 3.0
               ⇒ 0 ≤ 比例 ≤ 1 < 5.0 恒真 ⇒ _rate_low_s 只增不减 ⇒ 运行 3 s 后 r_score ≡ 1.0
memory.py:223  stuck_score = max(t_score, f_score, r_score)               # ⇒ 与行为无关地钉在 1.0
（第四段，t3 本次新发现）
memory.py:1985 self._stuck_score, self._stuck_duration, self._fallen = self.stuck.update(...)
memory.py:1994 if _disp_60s > 500.0 and self._stuck_duration > 0.0:
memory.py:1995     self._stuck_duration = max(0.0, self._stuck_duration - 1.0)
               ⇒ 每 tick 被 :1985 覆盖 ⇒ 泄放是空操作 ⇒ stuck_duration 单调增长
（外溢）
main.py:2687  model.stuck_duration = memory_ctrl.stuck_duration
               ⇒ model.py:2096（CX 环路突破的前置）
               ⇒ main.py:2056（burst 前置）
               ⇒ memory.py:2186（escape_behavior 门）
               ⇒ 反射冷却 / 测速 / burst 占空 / EVO 模式匹配
```

**同型缺陷在同一个文件里被显式记录过，且只在显示侧修好**：
`main.py:765-785`（RULE-19）自述 `gate_jump` 因为"per-tick 比例永不超过 1.0 却与声明为 2.0 Hz 的阈值比较"
而在构造上永假 —— 显示侧改用 `gate_open_hz`（`main.py:804+`），**检测侧漏修**。

**"跳"在系统里同时存在 4 个互不一致的门限口径**（t1 §1.7）：

| 门限 | 值 | 单位 | 位置 | 是否决定行为 |
|---|---|---|---|---|
| LIF 解码门 | `> 0.04` | per-tick 比例（= 2.0 Hz） | `model.py:2478` | ✅ **唯一执行门** |
| 遥测镜像 | `< 0.04` | per-tick 比例 | `main.py:3064` | ❌ 只上报 |
| 参数门 `gate_jump_threshold` | 默认 `8.0` / 线上 `3.082` | Hz | `brain_tunable_params.json:38-43`；`active_strategy.json:8` | ❌ 只进 `flow.json` + 教练上下文（阈值读于 `main.py:2894` → 发布 `gate_jump_threshold_hz` `:2954` → 闭式比较 `:2956-2957`；布尔 `gate_jump` 由 `plugin/scene_context.py:233-234` 消费，**非** `:234` 消费阈值本身。**F15 校正**） |
| 遥测独立门 | `> 2.` | Hz | `telemetry.py:94` | ❌ 只上报 |

⇒ **本方案统一口径而不新增门限**（§5.3），并以此为 M3 的第一条硬约束。

### 2.4 状态分类抖动（"振荡"现象正确、机制需改写）

`_detect_oscillating`（`memory.py:1289-1317`）统计 30 帧缓冲 `_ctrl_x_buf`（`memory.py:1281`）中
`≤-60 / ≥+60` 的交替次数，返回 `alternations >= 3`（`memory.py:1317`）。
而 t3 独立重算给出：符号交替占 **57% 的采样步**（3419/5999），`run len = 1` 占 3086/3476，
采样间隔 0.21 s ⇒ **一次完整往返 ≈ 17–18 tick ≈ 0.37 s**。
⇒ 30 帧窗内只有 ≈3–3.5 次切换，**正卡在 `>= 3` 的门限上 ⇒ 检测抖动**而非锁定。
⇒ 报告观测（oscillating 未触发）**为真**，但机制**不是"优先级被 stuck_ramp 覆盖"**，
而是**检测窗与真实周期同量级**（假设 H3）。

### 2.5 "反射疲劳"不成立的三条独立理由 + 一条反证

1. 它依赖 `stuck_score = 1.0`，而该值是构造伪影（§2.3）；
2. 该 run 的分类结果在 HEAD 上不可复现（`_vote` 顺序 + `escape_behavior` 被伪影抬升）；
3. 轨迹显示**反射层从未取得操纵权**：`ctrl_y ∈ {50, 70}`，**无反射的 30、无 burst 的 127**；
   `±60/±69` **无负侧**（`-60` = 0 次、`-69` = 0 次），**正侧仅 `60`×1、`69`×7（合计 8/6000）⇒ 不构成群**
   （本次复算：`jump` 0/6000、`ctrl_x` 满量程 5330/6000、前 5455 点无 0；t1 §6 的 `control.jump` 写入者枚举 + t3 §1.2 重算）；
4. **反证（力度最强）**：若"反射在跑但放弃"，则在 `stuck_score ≡ 1.0` 的同源条件下，
   burst（`control.y = 127`，占空比 200/500 tick，`main.py:2046-2086`）**必须**出现；
   实测 **0/6000**。这同时否证"反射疲劳"并暴露版本边界 H1。

### 2.6 真实卡死的可复现度量（HEAD 无关的轨迹统计，t3 §1.2 独立重算，可直接引用）

| 量 | 值 | 说明 |
|---|---|---|
| X 方向效率 | **2.75%** | 累计 135 817.2 u / 净 3 739.0 u（净退） |
| Z 方向效率 | **5.35%** | 累计 114 174.9 u / 净 6 111.3 u |
| 静止帧（位移 < 0.5） | **1385 / 5999（23.1%）** | |
| `jump = true` | **0 / 6000** | |
| `ctrl_x` 满量程 | **5330 / 6000** | 前 **5455** 点**从未回到 0** |
| 终态 545 点控制量 | `(0,50)×480 + (0,70)×65` | 撞墙前推 |
| `ctrl_y` 取值集 | `{70, 50}` | 反解 `forward_rate ∈ {0.043, 0.033}` |

> **引用纪律**：以上是**轨迹运动学**统计（E-2/E-3 层），与本方案引用的 `memory.json` 数值无关。
> 凡 §0 表中 E-4 层的量（`stuck_score=1.0`、`stuck_duration=1100.72`、`reflex_active=False`、
> `median_speed=0.0`、`disp_60s=1080.7`），一律标注「**检测伪影**」并按 H1（版本边界）限定适用范围。

---

## 3. 主要因素判定（判定输入，不重新推导）

采用 t3 §5.2 的排序与依赖，本方案不另立。四条依赖关系的可执行含义：

| 关系 | 可执行含义（本方案的动作） |
|---|---|
| **M3 不修 ⇒ 其余无法验证** | P0 只改"观测/口径"，**不改任何行为**；P0 的验收标准是"能分辨"，不是"变好" |
| **M1 不修 ⇒ M3/M4 的修复只是无效微调** | P1 的每一条都必须在**运行时 A/B** 下证明"参数写入 → 行为量变化"，否则视为接线失败 |
| **M2 不修 ⇒ 遇新型陷阱仍无换招能力** | P2 引入升级状态机，并使四机制的恒真/恒假前置可被观测 |
| **M4 不修 ⇒ 只能靠人工发现** | M4 与 M3 并行：存活自检 + 漏斗告警 + 观测值落盘 + 适应度可分辨 |

**A/B 两类问题（t3 §6）在本方案中的分工**：
- **A 类硬缺陷 11 项**（S19 单位契约、泄放空操作、S12/S13 死写入、S33 无消费者门限、`lr_adapt` 死代码、
  `_kc_activity` 无写入、`_last_burst_tick` 空守卫、`position_unchanged_30s` 零生产者、
  `bold_explore_stuck_s` 越界静默钳位、SKILL 版本自检红、`has_fix()` 一次性关闭 **11** 个 `pattern_id`）
  ⇒ 修它们**不属控制补丁**，**分属 §4（P0）、§5（P1）、§7（P2）**（F12① 修正；原句"§4/§7 的 P0/P2"漏掉 §5，与本文件 §5.4/§5.6 的自身归属矛盾）。逐条落点：

  | A 类项 | 落点 |
  |---|---|
  | S19 单位契约 + 泄放空操作 | **P0-a2**（§4） |
  | S33 无消费者门限（4 个 jump 口径） | 设计冻结 **P0-a1**（§4）+ 实现 **P1-b3**（§5.3） |
  | S12/S13 死写入 | **P1-b4**（§5.4） |
  | `lr_adapt` / `_kc_activity` / `_last_burst_tick` | **P1-b6**（§5.6） |
  | `bold_explore_stuck_s` 越界静默钳位 | **P0-a8**（§4.7 区间不变式）+ §7.1 T1 |
  | SKILL 版本自检红 | **P0-a7**（§7.5-e） |
  | `position_unchanged_30s` 零生产者、`has_fix()` 生命周期 | **P2-d3**（§7.5-a / §7.5-c） |
- **B 类自治缺失 5 项**（B1 无行为决定变量级作用点、B2 无竞争/升级/回退语义、B3 无可判别适应度、
  B4 无情景责任链、B5 无自观测）⇒ **方案核心**，对应 §5/§6/§7。

---

## 4. 方案架构

### 4.1 设计原则（五条）

| # | 原则 | 判据（如何判断一个改动是否合规） |
|---|---|---|
| R1 | **不新增控制分支** | 改动的输出只能是 `active_strategy.json` 的脑参数、`DopamineGainController` 的状态、或脑内电流/权重；**不得**出现 `control.x/y/jump = ...` 的新写入点 |
| R2 | **让已有信号真正到达** | 每条改动必须指名"哪个已有信号此前到不了哪里"，并给出其数据流入口 |
| R3 | **单一口径** | 同一个动作只能有一个决定行为的门限；新增门限必须**替换**一个旧口径（禁止第 5 个 jump 门） |
| R4 | **可判定** | 每条改动必须给出"观测哪个运行指标 + 阈值 + 失败回退"；无判据的改动一律不做 |
| R5 | **可回退** | 每条改动必须有**自动回退条件**（不是人工 revert），且回退不依赖人工在场 |

### 4.2 三层九组拓扑（Architecture）

```
                        ┌──────────────────────────────────────────────────────┐
                        │  M3 观测/口径层（P0）—— 解锁条件，不改行为            │
                        │  a1 唯一口径表  a2 伪影切断与剔除  a3 观测值落盘      │
                        │  a4 接线运行时 A/B  a5 漏斗告警与存活自检             │
                        └───────────────┬──────────────────────────────────────┘
                    unlocks             │
      ┌─────────────────────────────────┴─────────────────────────────────┐
      ▼                                                                    ▼
┌──────────────────────────────────────┐            ┌──────────────────────────────────────┐
│ M1 脑侧自适应作用面（P1）             │            │ M4 进化闭环（P0 并行 → P2）           │
│ b1 MBON→jump 腿纳入增益链            │            │ d1 新输出面（脑参数空间）              │
│ b2 跳池占用率自稳态（对等 homeostat）│  subject   │ d2 适应度可分辨（A/A 零假设门）        │
│ b3 jump_rate 门归一化（替换非新增）  │◀─────────▶│ d3 真回滚 + 快照 + 自愈让行            │
│ b4 两处死写入 → _goal_comp           │            │ d4 情景责任链（scene_label 与晋升边界）│
│ b5 CX 环路突破可达化（进展门）        │            │ d5 pattern 集补"已放弃终态" + 键校验   │
└───────────────┬──────────────────────┘            └─────────────────┬────────────────────┘
                │ enables                                             │ 不修 ⇒ 只能人工发现
                ▼                                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ M2 仲裁/升级语义（P2）                                                                │
│ c1 升级状态机（情形类 × 无效计数 × 已穷尽集合 × 升级记录），只升级"自适应面"不升级"控制量" │
│ c2 终态判据与四机制前置解锁  c3 检测窗自适应  c4 CPG 竞争槽                            │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 新的自治输出面（一句话契约）

> **闭环的唯一可执行输出 = 对 `fly64/skills/active_strategy.json` 中"已注册且已被运行时 A/B 证明生效"的
> 脑参数做有界写入；写入后的效果由 §4.4 的可判别适应度判定；任何需要改 `.py` 才能生效的想法，
> 一律不得进入闭环执行路径。**

### 4.4 新输出面的分类（三类，按"是否可自治"排序）

| 类 | 输出形态 | 生效路径 | 现状 | 本方案动作 |
|---|---|---|---|---|
| **T1 参数写入**（唯一自治类） | `active_strategy.json` 的已注册 `pid` | `main.py:1678-1863` 每 600 tick 热重载 → 直写 `model.*` / `memory_ctrl.*` / `mushroom.*` | ✅ 已存在（`__generation=332`）但含 4 个死写入 | §4.5 清死键 + §7.2 修适应度 |
| **T2 增益/突触状态**（自治，但今天够不到行为） | `DopamineGainController.pathway_gains` / `mushroom.weights` | `model.py:1837-1842`（唯一表达点）；MB 走 `model.py:1783-1791` | ⚠️ 生效但覆盖面错（jump 只 1/12 条腿） | §5.1/§5.2 扩面 + 稳态 |
| **T3 代码补丁**（**禁止进入闭环**） | `fix_template` 写 `.py` | 人工/agent 执行 | ❌ 100% 无效（0 effective） | §7.1 从闭环执行路径移除，降级为"变更提案"（只读产物，需人工批准） |

### 4.5 生效性判定必须改为运行时 A/B（取代静态自证）

- **现状**：`brain_tunable_params.json` 声明 39 个参数**全部** `wired: true`（`wired_audited_at = 2026-09-23T00:06:46`）。
  **该声明目前只有静态自证**：其 `wired_note` 指定的复核工具 `scripts/audit_contract_pairs.py` **不扫描注册表**
  （它扫描的是 8 个工件，含 `skills/active_strategy.json` 的 47 个键），在其中报 **38** 条 `unreferenced w=0 r=0 decl=0`
  （含 `exploration.gate_jump_threshold`、`navigation.steering_gain`、`navigation.loop_break_stuck_s` 等），
  全仓合计 `unreferenced` 85 行、`TOTAL dead-writes + silent-defaults: 8`（t5 §1.5 独立复现）。
  ⇒ **数字与对象都必须按工具的真实行为复述**（F7 修正：原文"`audit_contract_pairs.py` **对 39 个参数全部报** `unreferenced`"
  既把 38 记成 39，也指错了被扫描的文件）；且该工具自身也是扫描盲区 —— 它对 `_expl.get("turn_bias")` 这类扁平化读取无效，
  t2 §9.7 的整词核查给出的是相反结论（"39 个都有出现"）⇒ **一个静态工具无法支撑 `wired: true`**（假设 H10）。**实质结论不变**。
- **本方案的判据（唯一）**：**运行时 A/B**
  1. 选一个"有界且观测效应明显"的参数（首选 `exploration.turn_bias`、`escape.commit_ticks`、`coach.mb_learning_rate`）；
  2. 在**参数授权点**写一个在区间内但远离当前值的取值，不重启进程；
  3. 在 `artifacts/latest.jsonl` / `flow.json` 上观测**对应消费点的读数**在 ≤ 2 个热重载周期（≤1200 tick）内变化；
  4. **判据**：消费点读数变化（方向与符号一致）⇒ `wired=true`；**两个不同量级的值都无变化 ⇒ `wired=false` 并从搜索空间剔除**。
- **产物**：`fly64/skills/param_wiring_ab.json`（新增，结构见 §5.0），带 `probe_value / observed_before / observed_after / verdict / ts`。
- **失败回退**：A/B 结果与注册表不一致时，**以 A/B 为准**，并把该 `pid` 从 `BrainMutator.live_params` 中剔除（`evolution_skill.py:1967-1968` 已在按 `wired` 过滤，只需把该过滤的输入换成 A/B 产物）。

### 4.6 参数授权点（Authorization point）—— 单一写入口

**问题**：目前至少三个写入者会互相覆盖同一文件：
`main.py:1756-1879` 的钳位回写自愈、`BrainMutator._inject()`（`evolution_skill.py:2238-2267`）、
EFO/教练（`skills/active_strategy.json` 的 `__generation` 递增）。而 `main.py:1742-1753` 的钳位
与 `main.py:1769-1771` 的回写会在**试验窗口中途**改写参数（见 §7.2-2）。

**方案**：新增一个薄层 `fly64/skills/param_authority.py`（新增文件，无控制逻辑）：

```python
# 允许的写入者（枚举），与"当前持有者 + 租约"两个字段
AUTHORITY = {"coach": 0, "evo": 1, "operator": 2, "selfheal": 3}
class ParamAuthority:
    def acquire(self, owner: str, pid: str, lease_ticks: int, value: float) -> bool: ...
    def release(self, owner: str, pid: str) -> None: ...
    def snapshot(self) -> dict: ...        # 逐 pid 的 (owner, lease_expiry, value, source_ts)
    def restore(self, snapshot: dict) -> None: ...   # 逐 pid 精确回滚（非"重置为默认"）
```

| 作用脑机制 | 数据流 | 文件/接口 | 验证 | 失败回退 |
|---|---|---|---|---|
| 参数化自治的**唯一入口**；使"谁改的、改到什么时候、原值是多少"可审计 | `active_strategy.json` ← (coach/EFO/EVO/selfheal) → `main.py` 热重载 | 新增 `fly64/skills/param_authority.py`；`evolution_skill.py:2238-2267`（`_inject`）改为经 `acquire/release`；`main.py:1756-1879` 的自愈回写改为 `selfheal` 租约，**试验租约有效期内让行** | `/memory.json["param_authority"]` 暴露 `{pid: {owner, lease_expiry, value}}`；断言同一 `pid` 在任一 tick 只有一个非过期 owner；`artifacts/param_history.jsonl` 的行数与 `acquire` 次数一致 | 若租约机制异常（读写异常/缺失），退化为**只读模式**：禁止所有自动写入，仅保留教练人工写入，并置 `flow.json["param_authority_degraded"]=true` |

### 4.7 参数语义迁移与区间不变式（**F1 修复**，P0-a8）

**问题（t5 F1，blocker）**：§5.3 把 `exploration.gate_jump_threshold` 的语义从 Hz 改为无量纲比值，
原注册区间上界取 3.0，并据此写下"线上值 `3.082271242248696` 仍在同一区间内 ⇒ 参数文件无需迁移"。
这是**算术错误**：`3.082271242248696 > 3.0`（越界 0.0823）。且在新比值语义下，线上的 3.082 会把门变成
"`jump_rate > 3.082 × forward_rate`"，比今天的绝对门**严得多**（详见 §5.3 的等效换算表），与 §5.3 的目的完全相反。

**修法（两项并用，含取舍说明）**：

1. **上界改为 4.0**（`{default: 0.75, min: 0.25, max: 4.0}`）。
   *取舍*：单靠它只能让线上值**不被静默钳位**，不能修正语义 —— 3.082 作为比值仍然过严。
   它的作用是**给迁移留出安全的过渡态**：若先迁移、区间仍是 3.0，则迁移写入之前的那一次热重载会先把 3.082 钳成 3.0
   （仍是收紧）并留下一条静默记录；把上界抬到 4.0 后，**过渡期内在线值不会被改写**，语义修正完全由迁移项承担。
2. **显式迁移项（P0-a8）**：经 §4.6 授权点把 `active_strategy.json:8` 改写为 **0.75**（新语义下的默认值），
   并把它与 `:5`（`bold_explore_stuck_s = 60.0`，注册 `[1,10]`）**并列**写入 §14-D(j) 的迁移清单。
   *取舍*：迁移目标取 0.75 而不是"等效值 0.93"，因为 0.75 是 §5.3 声明的设计意图（**放宽**而非维持原严格度）：
   0.75 × 0.043 = 0.032 ≤ 0.04（见 §5.3 等效表）；若取 0.93 则等价于维持旧门（既不放宽也不收紧），与本项的设计目的不符。
3. **区间不变式硬断言（P0-a8，阻断 P1 上线）**：
   - 主判据（**对全部 39 个注册 pid**）：`clamp(live) == live`（写入值经运行期钳位后逐位不变）—— 不等即视为
     "静默钳位"，写 `high` 级 finding 并**阻断 P1 上线**。
   - 严格判据（t5 §F1-3 要求的同一断言）：`registry_min < live < registry_max`。
     **可满足性例外（本次独立核查新增）**：注册表中有两个 `default == max` 的 pid —— `exploration.turn_bias`
     `(0.0, 0.25, default 0.25)`、`exploration.bold_explore_stuck_s` `(1.0, 10.0, default 10.0)` —— 对它们严格形式
     **恒不成立**（合法目标值就等于上界）。故严格判据对 `default == max` 的 pid 退化为 `min < live ≤ max`，
     并由主判据兜底；否则该断言会把 P1 永久锁死。
   - **实测区间审计（本次独立核查，39/39 有活值）**：线上 `active_strategy.json` 中
     **落在区间外或钉在边界上的只有 2 个 pid** —— `exploration.bold_explore_stuck_s = 60.0`（**越界**，注册 max 10.0）
     与 `exploration.turn_bias = 0.25`（**钉在上界**）。`exploration.gate_jump_threshold = 3.082…` 在**当前**注册区间
     `[2.0, 20.0]` 内（故今天不被钳位），它的问题**只**出现在 §5.3 提出的新语义区间下 —— 这正是必须"改区间 + 迁移 + 断言"
     三件套，而不能只看"是否被钳位"的原因。

| 作用脑机制 | 数据流 | 文件/接口 | 验证 | 失败回退 |
|---|---|---|---|---|
| 防止"语义翻转 + 越界值"组合造成**静默收紧**（这正是 `bold_explore_stuck_s` 的同型缺陷） | `active_strategy.json` → `brain_tunable_params.json` 区间 → `main.py` 钳位/热重载 | ① `fly64/skills/brain_tunable_params.json:38-43` 的 `max` 改 4.0；② §5.3③ 的 `min(4.0, …)`；③ 迁移写入经 §4.6 授权点；④ 断言实现落在 `tests/test_tunable_wiring.py`（已有 `registry ∩ runtime clamp != empty` 断言处）扩展 + `main.py` 热重载段的运行时读回校验 | 断言 `clamp(live)==live` 对 39/39 通过；迁移后 `:8 == 0.75` 且 `:5` 落在 `[1,10]`；`/memory.json["clamped_keys"]` 在新语义上线后 6000 tick 内为空 | 断言失败 ⇒ **阻断 P1**；迁移项失败 ⇒ 保持语义在 Hz（不切比值），把 §5.3 标记为未上线 |

---

## 5. M1 — 脑侧自适应作用面（P1，决定性主因）

> **本节每一条都是"让已有信号到达"**：不新增控制分支，只扩面、加稳态、换口径、修死写入。

### 5.0 本节统一约定（数据流与验证的公共部分）

**观测落盘（M3 已建立）**：以下每条的验证都读同一组新增观测字段（见 §7.3 `context` 块）：
`jump_leg_current`、`gain_per_pathway`、`jump_pool_occupancy`、`fwd_pool_occupancy`、
`jump_rate_ratio`、`param_authority`、`ctrl_x/ctrl_y/jump`、`disp_60s`、`loop_score`、`coverage_cells`、`waste_ratio`。

**运行时 A/B（§4.5）为唯一接线判据**：每条改动都必须先在 A/B 里证明"写入 → 消费点变化"。

### 5.1 b1 — 把 MBON→jump 腿纳入增益链（消除"增益只覆盖一条腿"）

| 项 | 内容 |
|---|---|
| **作用脑机制** | 神经调节通路增益（`DopamineGainController`，三因子可塑性代理）原本只缩放"投射到跳池的连线体突触电流"（`model.py:1840-1842` 经 `_pathway_idx_map[3]`）。**池大小口径（F11① 修正）**：五个数由**本机直接测量**（`.tmp/a4_plan_probe.py` 量 `len(m.forward)`/`len(m.visual)`/…，并**由 t5 §1.3 独立复算确认**）—— jump **20**、forward 60、turn_all 80、recurrent 2400、visual 1536，n=4096；其中探针脚本里 `jump_pool = 20` 是**字面量**（不是测量值），forward/turn/visual/recurrent 为直接读取，故不能把整组数说成"探针实测映射"。承载"学到的跳倾向"的 MBON→jump 腿走**固定常数** `mbon_gain_jump = 0.35`（`model.py:1787`；常量定义 `model.py:639` ← `mbon_jump_weight`）。⇒ "学习走 MBON、增益走突触电流，二者不并联"。 |
| **数据流（改动后）** | `dop = clip(...)`（`model.py:1725-1743`）→ `dopamine_gain.set_dopamine(dop)` → `update_eligibility(pathway_activity)`（`model.py:1754-1766`）→ `apply_gain_update()`（`model.py:1767`）→ `_pathway_gains_np[3] = gain("jump")`（`model.py:1840`）→ **新增**：MBON 腿 `self.v[self.jump_nodes] += mbon[3] * self._jump_leg_weight * (self._pathway_gains_np[3] / self._jump_leg_nominal_gain)`（替换 `model.py:1787` 的固定 `mbon_gain_jump`）→ 跳池膜电位 → 13-tick 解码 `jump_rate`（`model.py:2255`）→ `raw_*`/`jump`（`model.py:2282,2283,2478`）。**归一化项 `_jump_leg_nominal_gain = gain_modulation.DEFAULT_GAINS["jump"] = 1.5`**（见"需修改/新增"② 与 F2 说明）。 |
| **需修改/新增** | ① `fly64/fly64/model.py:1787` —— 把 `mbon[3] * self.mbon_gain_jump` 改为 `mbon[3] * self._jump_leg_weight * (self._pathway_gains_np[3] / self._jump_leg_nominal_gain)`；② `fly64/fly64/model.py:639` 附近 —— `self._jump_leg_nominal_gain = DEFAULT_GAINS["jump"]`（**从 `gain_modulation` 导入常量，不复制数字**；`model.py` 顶部现有 `from .gain_modulation import DopamineGainController` 需同步加入 `DEFAULT_GAINS`），`self._jump_leg_weight = 0.35`——**此 0.35 是"名义权重"，不是"乘以原始 gain 后的等效值"**：见 F2；③ `fly64/skills/brain_tunable_params.json` —— **新增** `escape.jump_leg_weight` `{default: 0.35, min: 0.10, max: 0.80}`（新参数，不新增门限）；④ `fly64/fly64/main.py:1852-1855` 附近 —— 接线：`model._jump_leg_weight = max(0.10, min(0.80, float(_esc.get("jump_leg_weight", 0.35))))`（与 `_escape_jump_drive` 同段，同源 section `escape`）；⑤ **jump 通路的增益上限**：`gain_modulation.py:49` 的 `GAIN_MAX = 2.5` 是全局常数 ⇒ 新增 `JUMP_GAIN_MAX = 4.0`（`gain_modulation.py` 内按通路覆盖），理由：跳是**事件性**动作（自带 0.8 s 不应期），不需要与持续通路共享同一个 2.5 上限。 |
| **F2 修正：为什么不是"默认 0.35 ⇒ 行为不变"** | t5 §F2 指出：`DopamineGainController().get_gain("jump") == DEFAULT_GAINS["jump"] == 1.5`（`gain_modulation.py:39-45,331`），故**直接写** `mbon[3] * 0.35 * gain` 在标称状态下 = `0.35 × 1.5 = 0.525` ⇒ 首 tick 跳腿驱动 **+50%**，与"逐位相同、行为不变"矛盾；而且本方案自己的探针 `.tmp/a4_plan_probe.py:121` 做的正是 `leg * g / DEFAULT_GAINS["jump"]` —— **算术与拟写代码不一致**。**修法：实现内除以 nominal（采用 t5 给出的选项 2）**，即 `_jump_leg_weight × (gain / nominal)`，等价于 `W' = 0.35 / 1.5 = 0.2333…` 配上"乘以原始 gain"。*取舍说明*：两种写法在数学上**完全等价**（`0.2333·g ≡ 0.35·(g/1.5)`），差别只在该参数的含义 —— 选"除以 nominal"使 `jump_leg_weight` 的语义与今天 `mbon_gain_jump = 0.35` **同名同义**，因此 V4 的比例（0.35→0.80 = 2.29×、0.35→0.10 = 0.286×）、§14-A 的增益链表（0.07749 / 0.23247 / 0.38746）与注册项 `{0.35, 0.10, 0.80}` **全部无需改动**；选"默认改 0.2333"则三处都要跟着改，且参数含义从"名义权重"变成"绝对权重"，更易被后续误用。代价：每 tick 一次标量除法（可忽略）与一个跨模块常量依赖。**位精确回归断言（V4 新增）**：当 `_jump_leg_weight == 0.35` 且 `gain("jump") == DEFAULT_GAINS["jump"]` 时，`v[jump_nodes]` 的增量必须与改动前 `mbon[3] * mbon_gain_jump` **逐位相同**（`np.array_equal` 比较 float32 结果，不用 `approx`）；该断言同时锁定 V5 的阈值标定前提（"默认不变"）。 |
| **精确算术（本方案独立探针 E-3）** | LIF 参数 `dt = 0.020`（`model.py:403`）、`tau_m = 0.100`（`model.py:404`）、`threshold = 1.0`（`model.py:405`）⇒ 稳态 `v_ss = I / (1 - e^{-dt/tau_m}) = 5.517·I`。**单个跳神经元越过阈值需 `I ≥ 0.18127`**。跳池唯一持续驱动 `escape_current` 的下限 0.05（`model.py:1796`）⇒ `v_ss ≈ 0.2758 < 1.0`（**不够**）。把 MBON 腿接入增益链后，其电流在 `gain("jump") ∈ [0.5, 2.5]` 下可被缩放 **5×**。**口径（F2 后）**：这里的 5× 是**以 `gain/nominal` 为单位**的缩放（探针即按此计算）；`gain/nominal = 1`（标称）时腿电流与今天的 `mbon[3] × 0.35` **逐位相同**，`gain/nominal = 1/3` 与 `5/3` 分别给出 §14-A 的 0.07749 / 0.38746。 |
| **验证方式** | **运行指标**：`flow.json` 新增 `jump_leg_current = mean(abs(mbon[3])) * _jump_leg_weight * (gain("jump") / DEFAULT_GAINS["jump"])`（与实现同式，含归一化），与 `jump_pool_occupancy`。**阈值**：① **位精确回归（F2，必须先过）**：`_jump_leg_weight = 0.35` 且 `gain("jump") = 1.5` 时，`v[jump_nodes]` 增量与改动前的 `mbon[3] * mbon_gain_jump` **逐位相同**（float32 `array_equal`，非 approx）；② A/B —— 把 `escape.jump_leg_weight` 从 0.35 写到 0.80，`jump_leg_current` 必须上升 ≈2.29×，且 `jump_pool_occupancy` 出现非零（>0）tick 比例从基线 < 1% 升到 ≥ 5%；③ 把 `escape.jump_leg_weight` 写到 0.10，`jump_leg_current` 必须下降 ≈0.286×。**① 通过且 ②③ 两次方向都对**才判"接线成功"。 |
| **失败回退** | 若 ① 或 ② 无变化 ⇒ 判 `wired=false`，**自动把 `escape.jump_leg_weight` 从 `BrainMutator.live_params` 剔除**并写 `param_wiring_ab.json`，恢复 `model.py:1787` 为常数 0.35（保留旧行注释）。若 ① 位精确回归失败 ⇒ **立即回滚 §5.1 并区块化**（说明实现与标称不变式不一致，不允许进入 A/B 阶段）。若 `jump_pool_occupancy` 非零比例 > 30%（跳变成持续行为）⇒ 自动把 `_jump_leg_weight` 回落到 0.35 并置 `flow.json["jump_leg_clamped"]=true`。 |

### 5.2 b2 — 给跳池一个对等的"占用率自稳态 + 固有兴奋性腿"

| 项 | 内容 |
|---|---|
| **作用脑机制** | 前向池有一个**占用率负反馈**（`forward_homeo_gain()`，`model.py:1452-1475`；常量 `fwd_occ_tau=0.15 / fwd_occ_ref=0.30 / fwd_occ_full=0.60 / fwd_homeo_floor=0.25`，`model.py:649-652`；其**固有兴奋性腿**在 `model.py:1882-1890` 缩放前向池的 tonic current），跳池**没有任何稳态/自调**（t1 §1.4 对照）。⇒ 跳池要么全静默、要么被别的腿偶然推过头，没有自我寻址（self-addressing）能力。 |
| **数据流（改动后）** | 每 tick：`jump_occ` ← 低通(`jump_nodes` 发放率)（复用 `_fwd_occupancy` 的形状）→ `_jump_homeo_gain = jump_homeostat()` → **两处消费**：① 缩放 MBON→jump 腿（与 §5.1 串联）；② 作为**固有兴奋性**叠加到跳池 tonic：`v[jump_nodes] += _jump_intrinsic * (1 - _jump_homeo_gain)`（形状对等 `model.py:1888-1890`，但语义相反：前向池是"接近上限就压制"，跳池是"静默太久就抬升"，两者都是"把池拉回可用工作区间"的同一类负反馈）。 |
| **需修改/新增** | ① `fly64/fly64/model.py` —— 新增 `jump_homeostat()`（对等 `forward_homeo_gain`，纯映射、无 RNG、无新状态依赖）、`_jump_occupancy` 低通状态、常量 `jump_occ_tau=0.20 / jump_awake_ref=0.02 / jump_awake_full=0.12 / jump_intrinsic_max=0.15`（**F10① 修正：此处默认值必须与 ④ 的注册项一致，原写 0.25 与 ④ 的 `default: 0.15`、与"精确算术"段按 0.15 的论证三处矛盾**）；② 在 `model.py:1774-1778`（前向占用率低通处）的**同一段**追加跳池低通与增益计算；③ 在 `model.py:1888-1890` 之后追加跳池固有兴奋性腿（并受 `fwd_aux_ceiling`-类预算约束，见验证）；④ `fly64/skills/brain_tunable_params.json` —— 新增 `escape.jump_intrinsic_max` `{default: 0.15, min: 0.05, max: 0.25}`（唯一权威默认值 = **0.15**）；⑤ `fly64/fly64/main.py` 接线（与 `escape.*` 同段）。 |
| **精确算术（E-3）** | 使**单个**跳神经元越过阈值需注入 `0.18127`/tick；`escape_current` 下限提供 0.05 ⇒ 现有缺口 = **0.13127**/tick（**= 0.13 × threshold（1.0）/ = 0.31 × GAIN_MIN 腿的 v_ss（0.4275）**；F10② 修正：原句"= 0.31·threshold"把两个不同基准混写，`0.13127/1.0 = 0.131` 才是对 threshold 的比值）。故 `jump_intrinsic_max` 的可用区间下界取 0.05（不足）、上界 0.25（远超需求）——**0.15 的默认值落在"接近但不超过单神经元阈值"的区间**，与"抬升到可用工作区间而非保证发放"的设计意图一致。参考量：`fwd_aux_ceiling = 0.20`（`model.py:696`），本次新增的 `jump_intrinsic_max` 与它同量级（0.15/0.20 = 0.75）。 |
| **验证方式** | **运行指标**：`jump_pool_occupancy`、`_jump_homeo_gain`、`jump_rate_ratio`。**阈值**：① **静默诱导**：在"跳池连续 300 tick 占用率 < 0.02"的场景下，`_jump_homeo_gain` 必须单调下降至 ≤ 0.5（即固有电流被抬起），且 `jump_pool_occupancy` 从 0 变为非零；② **不失控**：连续 3000 tick 内 `jump_pool_occupancy` 的 **P95 ≤ 0.20**（占空比 ≤ 20%，远低于"持续跳"）；③ **对偶性**：跳池被驱动活跃后 `_jump_homeo_gain` 必须回升至 ≥ 0.9（稳态具有负反馈，不是单向抬升）。 |
| **失败回退** | 条件 ② 失败（P95 > 0.20）⇒ 自动将 `escape.jump_intrinsic_max` 减半；若减半后仍失败 ⇒ 置 0（该腿完全停用），并写 `param_wiring_ab.json` 标注 `ineffective`。条件 ③ 失败（无回升）⇒ 判定为"正反馈"，**禁止**该腿进入闭环搜索空间（只保留 A/B 手动值），并向 `evolution_log` 写 `high` 级 finding。 |

### 5.3 b3 — `jump_rate` 门归一化（**替换**而非新增第 5 个口径）

| 项 | 内容 |
|---|---|
| **作用脑机制** | 当前唯一执行门是**绝对占用率** `jump = jump_rate > 0.04`（`model.py:2478`）⇒ 需要 13-tick 窗内平均 **0.8/20 神经元**同时发放（0.04×20 = 0.8）。这是一个与驱动分布强耦合的标定，而跳池的常态驱动远低于该水平（**H6，需真实连接组确认**）。改为**相对占用率**后，门限变成无量纲量，自动适应驱动/连接组/时间尺度的变化。**本项的目的是"放宽"而不是"收紧"**（F1 明确化）。 |
| **选定的实现口径（唯一）** | **将 `gate_jump_threshold` 这一个既有 pid 的定义整体改写为"相对占用率"**，`model.py:2478` 改为 `jump = (jump_rate / max(forward_rate, FWD_RATIO_FLOOR)) > _jump_rate_ratio_gate and now - self.last_jump >= 0.8`；`_jump_rate_ratio_gate` 从 `active_strategy.json` 的 `exploration.gate_jump_threshold` 读入（**沿用同一个 key，不新增 key**）。registry 改为 `{default: 0.75, min: 0.25, max: 4.0}`（**F1(a)：上界由 3.0 改为 4.0**，理由见 §4.7），`unit` 字段显式改写为 `"ratio (dimensionless)"`，旧 Hz 标定的 `description` 整体替换。**分母下限 `FWD_RATIO_FLOOR`**：取前向解码器自身的零点 `0.008`（`model.py:2282` 的 `raw_y = clip((forward_rate - 0.008)·2000, 0, 70)`）—— 低于 0.008 时前向池不产生任何前进指令，"与前向池之比"在此处无定义，故必须把分母钳在下限。它不是新门限，而是**比值语义的定义域边界**（只影响换算，不新增判定）。 |
| **为什么是"替换"而不是"新增"** | 今天"跳"已有 **4 个互不一致的口径**（§2.3）。任何新门限都会变成第 5 个。此处**复用同一个 key**，语义从 Hz 变为比值，这同时消除了 t1 §1.7 的 4 个口径中的 2 个（参数门与遥测镜像随之对齐，`main.py:3064` 改读同一比值）。**F1 修正（blocker）**：原文写"`active_strategy.json:8` 的线上值 `3.082271242248696` 仍在同一区间内（3.082 ∈ [0.25, 3.0]）⇒ **参数文件无需迁移**"，这是**算术错误**（`3.082271242248696 > 3.0`，越界 0.0823）。正确结论：① 在新比值语义下 3.082 会要求 `jump_rate > 3.082 × forward_rate`，即 **0.102~0.133 / 2.03~2.65 个神经元**，比今天的绝对门 0.04（0.8/20）**严 2.54~3.31 倍**（t5 §F1 记 2.5–3.2×，同量级；差异仅来自 `forward_rate` 取值口径：本文按 `forward_rate = ctrl_y/2000 + 0.008` 取 0.0330/0.0430）；② 因此**必须有迁移**（§4.7 P0-a8：经授权点把 `:8` 改写为 0.75）；③ 上界改 4.0 的作用只是让过渡期不被静默钳位。三项缺一不可。 |
**等效换算表（F1-4：新门 vs 旧门，明确"放宽/收紧"）**：记旧门为绝对量 `jump_rate > 0.04`；新门为 `jump_rate > r · max(forward_rate, 0.008)`。两者的等效关系为 `r_eq(forward_rate) = 0.04 / max(forward_rate, 0.008)`：

| `forward_rate` | 旧门等效比值 `r_eq` | 默认 `r = 0.75` 时新门要求 `jump_rate >` | 神经元数（/20） | 相对旧门 |
|---|---|---|---|---|
| 0.008（解码零点，下限） | 5.00 | 0.0060 | 0.120 | **放宽 6.7×** |
| 0.0330（`ctrl_y = 50` 实测） | 1.21 | 0.0248 | 0.495 | **放宽 1.6×** |
| 0.0430（`ctrl_y = 70` 实测/饱和） | 0.93 | 0.0323 | 0.645 | **放宽 1.24×** |
| 0.1000 | 0.40 | 0.0750 | 1.500 | 收紧 1.9× |
| 0.3000 | 0.13 | 0.2250 | 4.500 | 收紧 5.6× |

> 读法：**在前向池安静的区间（本 run 的实测区间 0.033–0.043）新门是放宽的**，这正是 §5.3 的目的；
> 当前向池本身很活跃（≥0.10）时新门反而更严 —— 因为此时"跳"应当比"继续前冲"更强才值得触发。
> 若沿用线上 3.082：在 0.033/0.043 两处分别是 **2.54× / 3.31× 收紧**，与目的相反且 V6 不可满足。

| 项 | 内容 |
|---|---|
| **需修改/新增** | ① `fly64/fly64/model.py:2478`（并按上表改用 `FWD_RATIO_FLOOR = 0.008`）；② `fly64/fly64/model.py` —— 新增 `self._jump_rate_ratio_gate = 0.75` 与 `FWD_RATIO_FLOOR`；③ `fly64/fly64/main.py` —— 在参数热重载段写入 `model._jump_rate_ratio_gate`（取值 `max(0.25, min(4.0, float(_expl.get("gate_jump_threshold", 0.75))))`，**F1：上界随注册表改 4.0**）；④ `fly64/skills/brain_tunable_params.json:38-43` —— 改写 `exploration.gate_jump_threshold` 的 `default/min/max/description`（`max: 4.0`）与新增 `unit: "ratio (dimensionless)"`；⑤ `fly64/fly64/main.py:2892-2894` —— 读取默认值随注册表改 `0.75`，遥测发布 `:2953-2954`（`gate_jump_threshold_hz`）与 Hz 比较 `:2956-2957` 同步改读比值口径（**F15 校正：原写 `main.py:3064` 有误，该行是 per-tick 解码镜像 `jump_not_active`，不属本项**）；⑥ **P0-a8 迁移**（§4.7）：经 §4.6 授权点把 `active_strategy.json:8` 写为 `0.75`；⑦ **RULE-19 单位契约迁移（F13，新增）**：`gate_jump_threshold` 由 Hz 门迁移为 ratio 门，须同批改写 `fly64/tests/test_gate_units.py:178-226`（pinned 契约由「Hz」改为「ratio」，`description` 须含 `"ratio"` 及分母下限 `FWD_RATIO_FLOOR = 0.008`、`model.py:2282`，`default>0`、`min>0`；**pinned 强度不下调**）、`fly64/contract_registry.json:102`（`threshold_unit` → `"ratio (dimensionless)"`，`:83/:98` 的 `rate_gate_group` 注释同步）与 `fly64/fly64/main.py:777-783`（RULE-19 注释同步为 ratio 版本）；验收 = `python -m pytest fly64/tests/test_gate_units.py -q` 全绿。 |
| **验证方式** | **运行指标**：新增 `flow.json["jump_rate_ratio"] = jump_rate / max(forward_rate, 0.008)`（与 `flow.json["jump_leg_current"]` 同段发布）。**阈值（F1-4：改写为可判定形式）**：① **A/B**：把 `gate_jump_threshold` 从 0.75 写到 0.25 ⇒ `ctrl.jump` 占空比上升；写到 2.5 ⇒ 下降；② **有界性**：连续 6000 tick 内 `ctrl.jump` **占空比 ∈ [0.1%, 5%]**（下界≥0.1% 表示"确实会触发"，上界 5% 与 `last_jump >= 0.8 s` 不应期一致；**基线对照：改前 = 0/6000 = 0.0%，即下界不满足**）；③ **不复现旧缺陷**：门限在 6000 tick 内必须**同时出现过真与假**（恒真/恒假即标定失败）；④ **等效性抽样**：任取 100 个 tick，断言 `jump_rate_ratio > r ⇔ jump_rate > r·max(forward_rate,0.008)` 与实现逐 tick 一致（防止把下限写错位置）。 |
| **失败回退** | 条件 ② 失败（占空比 > 5%）⇒ 自动把门限 ×2（并记录 `jump_gate_autoraise`）；连续两次仍失败 ⇒ 回落到 0.75 并把该 `pid` 标记为 `high_risk`（从自动搜索空间剔除）。条件 ③ 失败 ⇒ 判"新口径不可判别"，回退为 §5.3 的候选方案 A（按下 1 秒内 **前向池对跳池的比值 ≥ 2 倍**，用一个**新增的只读指标**而非新门限），并在 `param_wiring_ab.json` 标注。**迁移项（⑥）失败** ⇒ 不切换语义（保持 Hz），把 §5.3 标为未上线并保留原门，**不得**带着 3.082 的越界值进入比值语义。**契约迁移（⑦，F13）失败** ⇒ 不得上线 §5.3：保持 `gate_jump_threshold` 的 Hz 语义不变（本项整体不切换），并在 §10 V6 标注「未上线」。 |

### 5.4 b4 — 修复两处旋钮死写入（写端改到 `_goal_comp`）

| 项 | 内容 |
|---|---|
| **作用脑机制** | 教练/EFO 通过 `active_strategy.json` 调整 CX 导航，但写入落在一个**影子属性**上：`main.py:1848-1849` 写 `model.cx.steering_gain`，而 `CentralComplex` **本没有这个属性**，参与运算的是 `cx._goal_comp.steering_gain`（t1 探针实测：写入前 `hasattr(cx,'steering_gain')=False`、`_goal_comp.steering_gain = 0.12`；写入后 `cx.steering_gain=0.5` 而 `_goal_comp.steering_gain` 仍是 **0.12**）。同理 `main.py:1850-1851` 写 `model.cx._loop_break_stuck_s`，而读取端在 `goal_comp` 内（`central_complex.py:297`），回退常量 **45.0**。⇒ **CX 的两个导航旋钮对教练/EFO 完全无效**，而 CX 转向输出经两级小增益后 ≤ 0.018 V/tick，仅为转向竞争主导项（±0.18 V/tick）的 **1/10**。 |
| **数据流** | `active_strategy.json.navigation.{steering_gain, loop_break_stuck_s}`（`active_strategy.json:33-38`，线上 0.12 / 45.0）→ `main.py:1848-1851` →（**修正后**）`model.cx._goal_comp.steering_gain` / `model.cx._goal_comp._loop_break_stuck_s` → `central_complex.py:192,198,314`（运算）与 `central_complex.py:294-306`（环路突破前置）。 |
| **需修改/新增** | ① `fly64/fly64/main.py:1848-1851` —— 写端改为 `_goal_comp`，并**保留**对 `model.cx` 的属性写入但加 `assert` 断言"影子属性不得被任何消费者读取"（`grep` 断言）；② `fly64/fly64/central_complex.py` —— 为 **`MultiSourceGoalCompetition`**（`central_complex.py:178` 的真实类名；实例挂在 `cx._goal_comp`，`central_complex.py:369`）增加 `steering_gain` / `_loop_break_stuck_s` 的 `property`，使 `cx.steering_gain` 与 `cx._goal_comp.steering_gain` **同源**（消除"写在哪一处"的类别错误，而不是只改一处）。**F9 修正**：原文写 `GoalComparator` —— 该类在仓库中**不存在**（`grep GoalComparator` 全仓 0 命中），且 property 必须落在这个类上（`central_complex.py:198` 的 `self.steering_gain` 与 `:297` 的 `getattr(self,'_loop_break_stuck_s',…)` 都在该类的命名空间内）；③ `fly64/fly64/main.py` —— 热重载段增加"写入后读回校验"：`assert model.cx.steering_gain == model.cx._goal_comp.steering_gain`，不等则写 `high` 级 finding 到 `/memory.json["param_write_mismatch"]`。 |
| **验证方式** | **运行指标**：`flow.json` 新增 `cx_effective_steering_gain` 与 `cx_effective_loop_break_s`（从 `_goal_comp` 读）。**阈值**：① A/B —— 写 `navigation.steering_gain = 0.40`，`cx_effective_steering_gain` 必须在 ≤ 1200 tick 内变为 0.40（允许一次 600-tick 重载延迟）；② 同法验证 `loop_break_stuck_s = 20.0`；③ `param_write_mismatch` 在 6000 tick 内必须为 0。 |
| **失败回退** | 条件 ①/② 失败 ⇒ 判 `wired=false`，把两个 `pid` 从搜索空间剔除（**但不从注册表删除**，保留为"待修"）。条件 ③ 失败 ⇒ 立即回滚 §5.4 的写端改动到原行为（保留原写入），并中止 P1 其余项的闭环接入。 |

### 5.5 b5 — CX 环路突破（EVO-057）可达化：把"无目标"门换成"无进展"门

| 项 | 内容 |
|---|---|
| **作用脑机制** | CX 环路突破是**唯一为"持续环行"设计的脑原生机制**（`central_complex.py:294-306`），但其前置 `_no_goal` 依赖 `_ext_goal_strength`：只要覆盖率缺口向量或危险向量在供（覆盖率 15% 时恒在供），`_ext_goal_strength = min(1, norm/1.5) ≥ 0.05` **恒成立** ⇒ `_no_goal` 恒假 ⇒ **永不触发**（t1 探针 4000 tick / `stuck_duration=1000 s` 实测触发 **0** 次；仅在向量 `norm < 0.075` 或无向量时触发 3 次）。即"仍有未探索格子"这一信号**锁死了最该处理"环行"的机制**。 |
| **设计（用进展而非有无所致）** | 把前置从"有没有目标向量"改为"**有没有进展**"，复用系统里已有的单一进展口径 `progress_is_ineffective`（`memory.py:1113-1160`，`efficiency < 0.25`，已被 L2a/anomaly/burst/plugin 共用 ⇒ 改它不新增语义）：<br>`breakout_ok = (stuck_duration > _loop_break_stuck_s) AND (progress_is_ineffective OR loop_score > loop_breakout_threshold) AND cooldown_ok`<br>并把 `_ext_goal_strength ≥ 0.05` 从**触发条件**降级为**幅度调制**（目标向量越强，突破后朝目标方向的偏置越大；目标向量不作为"能不能突破"的门）。 |
| **数据流** | `memory_ctrl.progress_is_ineffective`（单一进展账本）→ `main.py:2748-2751`（现有目标向量组装处）→ 新增传参 → `central_complex.py:294-306`（`_loop_break` 前置）→ `model.py:2096-2101`（`stuck_duration` 输入与转向电流注入）。 |
| **需修改/新增** | ① `fly64/fly64/central_complex.py:286-306` —— 改 `_no_goal` 的判定式（`_no_goal` 保留为**幅度**项，新增 `_no_progress` 门）；② `fly64/fly64/main.py:2748-2751` —— 把 `progress_ineffective` 与 `loop_score` 传入 CX；③ `fly64/skills/brain_tunable_params.json` —— `navigation.loop_break_stuck_s` 的语义从"卡死且无目标"改写为"卡死且无进展"（同 key，区间 `[10, 120]` 不变）；④ **不新增**任何控制写入点（突破仍由 CX 的转向电流经 `model.py:2100-2101` 表达）。 |
| **与既有 deadlock burst 的互锁（F6 修复）** | t5 §F6：既有 `deadlock_burst_ready`（`memory.py:1189-1220`）的前置是 `loop_score > threshold` **OR** `stuck_duration > 60` **OR**（`stuck ≥ 45` 且无进展）——与本项"卡死 + 无进展"在几乎同一场景下**同时成立**，占空比 200/500 tick 且**直接写** `control.x / control.y = 127`（`main.py:2063-2084`）。若不互锁，V8 的观测**无法归因给 CX**。**处置（三件）**：① **互锁**：`burst_active`（`main.py:2075-2084` 的 `_deadlock_burst_remaining > 0`，**已有信号**）作为 §5.5 突破的**抑制前置**——burst 激活期间 CX 不复位目标（`breakout_ok AND NOT burst_active`）。这是把已有信号接进已有判定，**不新增 `control.*` 写入点**，也不新增门限；② **可分辨观测**：新增 `flow.json["cx_loop_break_count_burst_off"]`（只在 `burst_active == false` 的 tick 累加）与 `flow.json["deadlock_burst_count"]`（对照量），并在 §7.3 的 `context` 里同时落盘两者；③ **冲突矩阵**（把 §5.6 对 `main.py:2082` 的审查扩展为下表，逐对给出裁决）： |

| 交互对 | 现象 | 裁决 |
|---|---|---|
| burst ↔ §5.3 门归一化 | burst 期间 `control.jump = False`（`main.py:2082`）**主动抑制跳**，而 §5.3 想把跳变成可触发 | **保留** burst 的抑制（burst 是有意的"先冲再跳"序列），但 §5.3 的 V6 占空比统计**必须排除 burst 窗口**（否则 V6 被 burst 的必然假阴性污染）；new: `jump_duty_burst_off` |
| burst ↔ §5.5 CX 突破 | 两者都在"卡死 + 无进展"下触发，且 burst 直接写 `control.x/y` | **互锁**：burst 激活 ⇒ CX 不复位（见上）；V8 只数 burst-off 的窗口 |
| burst ↔ §6.4 CPG 权威 | CPG 取权条件与 burst 的 `reflex_override=True` 重叠 | **权威优先级固定为 `burst > primitive > lif`**，由 §6.1 的仲裁状态机持有；burst 期间不授予 primitive |
| §5.3 ↔ §6.4 | 门归一化后跳更易触发，而 CPG 的 `longjump` 也会写跳 | 两者**不叠加**：primitive 授予期间 §5.3 的门仍照常计算（只读），跳的最终写入者仍是原路径（`bridge.write_control(control.x, control.y, control.jump)`，`main.py:2579-2581`），不新增写入者 |

| 项 | 内容 |
|---|---|
| **验证方式** | **运行指标**：`flow.json` 新增 `cx_loop_break_count`、`cx_loop_break_count_burst_off`、`cx_loop_break_last_ts`、`no_progress_gate`、`deadlock_burst_count`。**阈值**：① **可达性（V8 修正后）**：在"`stuck_duration` 递增 + `progress_is_ineffective=true` + `loop_score > 0.6`"的复现场景下，**`cx_loop_break_count_burst_off` 在 4000 tick 内 ≥ 1**（对照：改前 = 0）；用**整段** `cx_loop_break_count` 不作为验收量，只作并列观测；② **复发抑制**：A/B 把 `navigation.loop_break_stuck_s` 写到 20 ⇒ 突破次数上升；写到 120 ⇒ 下降；③ **不误伤**：在正常探索段（`progress_is_ineffective=false`）突破次数必须为 **0**；④ **归因自证**：在 4000 tick 内同时报告 `cx_loop_break_count_burst_off ≥ 1` 与 `deadlock_burst_count ≥ 1`，并断言两者的时间戳集合**不相交**（即每个 CX 突破都落在 burst-off 窗口内）。 |
| **失败回退** | 条件 ② 失败（旋钮无效）⇒ 说明 §5.4 未生效，**先回退 §5.5**（保持触发条件不变），待 §5.4 通过后再试。条件 ③ 失败（正常探索段误触发）⇒ 自动将 `loop_breakout_threshold` 抬到 0.9 并收紧 `_loop_break_stuck_s ≥ 45`；仍失败则置 `cx_loop_break_enabled=false`（只读遥测保留）。**条件 ④ 失败（仍无法把 CX 突破与 burst 分开归因）⇒ 按 t5 §F6 的要求明确放弃归因**：V8 降级为"非归因观测指标"（只记录 `cx_loop_break_count*`，不作为 §5.5 的通过判据），并把 §5.5 的验收改为"§5.4 的旋钮 A/B 通过 + 突破计数在 burst-off 窗口内非零"；若连这一条也无法满足，则 §5.5 判**未通过**（不得用 burst 的行为冒充 CX 的功劳）。 |

### 5.6 b6 — 死代码清理（A 类，不属控制补丁；**清理即消除"机制存在、报告成功、无法生效"家族**）

| 项 | 位置（E-1 已核对） | 处置 | 验证 |
|---|---|---|---|
| `lr_adapt` 恒 1.0（`set_adaptive_lr()` 全仓库无调用点，仅测试） | `fly64/fly64/mushroom_body.py:350-360` | 二选一：**接线**（把它接到 `coach.mb_learning_rate` 的自适应调制上）或**删除**。本方案选**接线**，因为三因子学习率是 M1 的有效作用点之一 | A/B：写 `coach.mb_learning_rate` ⇒ `flow.json` 新增 `mb_effective_lr` 必须变化；`lr_adapt != 1.0` 至少在 1% 的 tick 出现 |
| 异常消解记忆守卫读 `_kc_activity`，该属性**全仓库无写入点** | `fly64/fly64/mushroom_body.py:513-539` ← `fly64/fly64/main.py:2693-2699` | 要么在 `model.step()` 内写 `_kc_activity`（KC 稀疏活动向量，本就是 `encode()` 的中间量），要么删除该路径。本方案选**写入**（恢复"场景+动作→召回"的记忆成因） | `mb_consolidated_anomaly_count > 0`，且 A/B 变更场景后召回次数变化 |
| `_last_burst_tick` 只读不写（防重入守卫恒真） | `fly64/fly64/main.py:2062` | **修守卫**（写入实际 burst tick），并**同时**处置 `main.py:2082` 的 `control.jump=False`（burst 期间主动抑制跳）与 §5.3/§5.5/§6.4 的相互作用 —— **按 §5.5 的"冲突矩阵"四条裁决执行**（F6 扩展：该审查不止与 §5.3 有关，还与 CX 突破、CPG 权威两两相关） | 6000 tick 内 `deadlock_burst_count` 与占空比（应 ≈ 200/500）一致；`_last_burst_tick` 单调递增；`cx_loop_break_count_burst_off` 与 `deadlock_burst_count` 时间戳集合不相交 |
| `position_unchanged_30s` **零生产者**（`ramp_trap` 因此永不可达） | `fly64/skills/default_patterns.json:50` ← 生产者仅 `position_unchanged_60s`（`fly64/skills/evolution_skill.py:863,1009`） | 见 §7.5-a（补生产者，**不改回 60s**，因为 048fd16 的意图是收紧） | §7.5 的键覆盖自检 |
| `gate_forward`/`gate_jump` 无执行侧消费者 | `fly64/fly64/main.py:2883-2957,3064`；`fly64/plugin/scene_context.py:115-116,233-234` | 由 §5.3 统一口径后，`gate_jump_threshold` 获得真实消费者；`gate_forward_threshold` 同法接到 §4.5 的 A/B | A/B 两个 `pid` 均须改变行为量 |
| 深坑/地下跳跃护栏与对话/教练直写 jump | `fly64/fly64/main.py:2358-2384,2279-2323,2330-2348` | **保留**（安全与人工通道不受本方案约束），但**不进入闭环输出面**（§9.4） | `param_authority` 不记录这些写入 |

---

## 6. M2 — 仲裁与升级语义（P2，直接主因）

### 6.1 c1 — 升级状态机（用"情形类 × 无效计数 × 已穷尽集合"替代固定判定表）

| 项 | 内容 |
|---|---|
| **作用脑机制** | 今天的仲裁是 `_vote()`（`fly64/fly64/memory.py:1347-1373`）的**首命中即返回**：`fallen`(:1362) → `micro_loop`(:1364) → `oscillating`(:1367) → `wall_stuck`(:1369) → `stuck_ramp`(:1371) → `idle`(:1373)。**没有竞争（无对比）、没有升级（处理无效不会换招）、没有超驰（`escape_behavior` 同时是两个检测的前置）**。需注意：`oscillating` 在 `stuck_ramp` **之前**被判 ⇒ 原报告"stuck_ramp 覆盖了 oscillating"在代码上不成立（§2.4）。 |
| **状态机定义** | 为每个"情形类"（`situation_key = (scene_key, anomaly_class)`）维护：<br>· `intervention`：当前落点（`param_scope`）<br>· `ineffective_ticks`：本次干预累计无效时长<br>· `exhausted_params`：已穷尽的参数集合（来自 §4.5 的 A/B 结论）<br>· `upgrade_level ∈ {0 参数 → 1 增益 → 2 仲裁}`<br>· `upgrade_history`：每次升级的 `(ts, from, to, trigger, outcome)`<br>**触发**：`ineffective_ticks > dwell_ticks`（`dwell_ticks` 由 §7.3 的观测判定，初值 1500 tick）且本次干预的成效分（§7.2）未改善 ⇒ 升级一级。<br>**升级动作只允许两类**：<br>· `level 0→1`：把该 `(situation, pid)` 的搜索重心从"参数值"移到"通路增益/腿权重"（`b1/b2` 的参数）；<br>· `level 1→2`：切换**仲裁类别**（例如 `stuck_ramp → oscillating`、或允许 CX 环路突破接管），并把 `exhausted_params` 固化。 |
| **数据流** | `memory_ctrl`（情形类与无效计数）→ 新增 `ArbitrationState` → ① `active_strategy.json` 的写入（参数升级）② `DopamineGainController` 的初始增益（增益升级）③ `memory_ctrl` 的状态允许集合（仲裁升级）。 |
| **需修改/新增** | ① 新增 `fly64/fly64/arbitration.py`（**只做状态记账与升级决策，不写 `control.*`**）；② `fly64/fly64/main.py:2009-2017`（反射 update 处）与 `main.py:2020-2035`（状态多数票处）挂接 `ArbitrationState.update(...)`；③ `fly64/fly64/memory.py:1347-1373` —— **不改 `_vote` 的优先顺序**（那是严重度排序，语义正确），而是让 `ArbitrationState` 持有"本次允许的类别集合"并**在同一严重度层内引入竞争力**（同层多命中时按成效分选择）。 |
| **验证方式** | **运行指标**：`flow.json` 新增 `arbitration = {situation_key, level, ineffective_ticks, exhausted_params, last_upgrade_ts}`。**阈值**：① **升级确实发生**：在复现的卡死场景（`stuck_duration` 递增 + `progress_is_ineffective`）下，`ineffective_ticks` 越过 `dwell_ticks` 后 `level` 必须从 0 升到 ≥1，且 `upgrade_history` 非空；② **升级不是抖动**：6000 tick 内 `level` 的**升降次数 ≤ 2**（禁止来回振荡）；③ **升级有界**：`level` 上界为 2，且达 2 后不再产生写入（防止无界搜索）。 |
| **失败回退** | 条件 ② 失败（抖动）⇒ 把 `dwell_ticks` ×2 直到满足条件 ②（最多 ×4）；仍失败 ⇒ 停用状态机（`arbitration_enabled=false`），只保留只读遥测。条件 ① 失败 ⇒ 说明 §7.2 的成效分仍不可分辨，**回退到 P0/P1 阶段**，不得进入 P3。 |

### 6.1.1 `ArbitrationState` 与 `_vote` 的接口契约（F14，落地前置）

**背景（实测）**：`MotionStateDetector._vote`（`fly64/fly64/memory.py:1347-1373`）为**扁平首命中**：`fallen`(:1362) → `micro_loop`(:1364) → `oscillating`(:1367) → `wall_stuck`(:1369) → `stuck_ramp`(:1371) → `idle`(:1373)，**无严重度分层**（与 §6.1③「不改优先顺序」一致）。新状态机若直接改写 `_vote` 会破坏该不变式；故先定义**纯函数式接口**（无副作用、默认零行为变化）。

**接口（默认输出逐 tick 不变）**：

```python
# fly64/fly64/memory.py —— 结构替换（仅内部），默认输出与改动前逐 tick 相同
def _vote_all(self, *, ramp_score=0.0, stuck_duration=0.0, ...) -> list[str]:
    """全部命中类别，按现有严重度顺序；不做首命中短路。无副作用、无新状态。"""
def _vote(self, *, ..., allowed: set[str] | None = None) -> str:
    hits = self._vote_all(...)
    if allowed is None:
        return hits[0] if hits else self.IDLE      # ← 与改动前逐 tick 相同（PIN）
    return next((c for c in hits if c in allowed), self.IDLE)
```

**`ArbitrationState`（新增 `fly64/fly64/arbitration.py`）消费协议**：
- 输入：`_vote_all(...)` 的有序命中集 + 各命中的**成效分**（§7.2）；
- 决策：**同层多命中 ⇒ 按成效分选**；把结果作为「允许集合」写回 `detector._vote(..., allowed=...)`；
- **禁止**：改 `_vote_all` 的严重度顺序、写 `control.*`、覆盖更高优先级机制（`burst > primitive > lif`，§5.5）。

**数据流**：`memory_ctrl`（情形类/无效计数）→ `ArbitrationState.update(...)` → `allowed` → `_vote(...)` → `memory_ctrl.anomaly_state`。

**验收（PIN）**：① `allowed is None` 时 `_vote` 输出与基线逐 tick 相同；② 复现场景下 `level` 从 0 升 ≥1、6000 tick 内升降 ≤2（对齐 V13）。

### 6.2 c2 — "已放弃终态"判据与四机制前置解锁（B2 + t2 §2.2 的自锁）

| 项 | 内容 |
|---|---|
| **作用脑机制** | 现有三个判据都以"还在挣扎"为前提，而故障终态恰好是"已放弃"，形成**自锁**：<br>· `_detect_wall_stuck`（`fly64/fly64/memory.py:1319-1321`）要求 `wall_score > 0.4 AND escape_behavior AND stuck_duration > 10.0`；<br>· pattern `circle_loop` 要求 `wall_score ≤ 0.1`（贴墙时 wall_score > 0.4 ⇒ 排除）；<br>· pattern `micro_loop_weave_signal` 要求 `escape_behavior = true`（放弃时 false ⇒ 排除）。<br>⇒ **"放弃"既是否定检测的条件、又是结果**。 |
| **新增判据（观测/诊断层，不写控制）** | `terminal_surrender`：`(stuck_duration 真实量 > T_s) AND (loop_score > L) AND (waste_ratio > W) AND (reflex_active = false OR escape_behavior = false) AND (net_displacement_rate < D)`。<br>**关键：`stuck_duration` 用 §4 重建后的真实量或轨迹运动学量，不得使用伪影值**（§2.3）。初值 `T_s = 120 s`、`L = 0.6`、`W = 10`、`D = 0.5 u/s`（由 §7.3 的观测标定）。 |
| **需修改/新增** | ① `fly64/fly64/memory.py:1319-1321` —— 增加"独立于 `escape_behavior`"的并行判据（保留原判据，新增一条 OR 支路，**不删除**）：`return (wall_score > 0.4 and stuck_duration > 10.0 and (escape_behavior or surrender_evidence))`；② `fly64/skills/default_patterns.json` —— `circle_loop` / `micro_loop_weave_signal` 的排除条件改为"挣扎态 **或** 终态"（即排除条件只排除"正常探索"），并新增 `terminal_surrender_stuck` pattern（`severity: high`）；③ `fly64/skills/evolution_skill.py:2570-2580` 附近 —— 为 `terminal_surrender_stuck` 提供"脑侧响应"（见 §7.5-b）。 |
| **验证方式** | **运行指标**：`flow.json` 新增 `terminal_surrender`（bool）、`surrender_evidence`（各分量）。**阈值**：① 用**轨迹运动学**构造的终态回放（末 545 点：`ctrl = (0,50)×480 + (0,70)×65`、静止、`loop_score` 高）必须使 `terminal_surrender = true`；② 正常探索段（`progress_is_ineffective=false`、净位移率 > 1 u/s）必须为 `false`；③ t2 §2.2 的真引擎回放（报告故障快照）在改后必须至少命中一个 `high` 级 pattern（对照：改前 0 个 high）。 |
| **失败回退** | 条件 ② 失败（正常段误判为终态）⇒ 提高 `T_s` 与 `D`（更保守）；连续两次失败 ⇒ 把该 pattern 降为 `medium` 并只记录 finding（不触发任何响应）。 |

### 6.3 c3 — 检测窗自适应于实测交替周期（对 t1 §5.4 / 假设 H3）

| 项 | 内容 |
|---|---|
| **作用脑机制** | `_detect_oscillating`（`fly64/fly64/memory.py:1289-1317`）用固定 30 帧窗（`_ctrl_x_buf` 的 `maxlen` 定义于 `memory.py:1281`）统计 `≤-60 / ≥+60` 的切换，返回 `alternations >= 3`。实测翻转周期 ≈17–18 tick（≈0.37 s）⇒ 30 帧窗内只有 ≈3–3.5 次切换 ⇒ **正卡在门限上 ⇒ 抖动**（唯一携带 jump 的反射因此拿不到触发条件）。 |
| **设计（不新增门限，改的是"窗口的确定方式"）** | 把固定窗口改为**由被测系统自身的交替周期确定**：用 `_ctrl_x_buf` 的最近符号切换间隔的**中位数** `T_alt` 定义窗口 `W = clip(6·T_alt, 30, 300)` 帧，并要求 `alternations >= 3`（门限不变）。物理含义："以 6 个真实周期为观察窗"，在 0.37 s 周期下 `W ≈ 110` 帧（2.2 s），在慢速交替下窗口自动变短。 |
| **需修改/新增** | ① `fly64/fly64/memory.py:1281`（`_ctrl_x_buf` 的 `maxlen`）与 `:1289-1317`（`_detect_oscillating`）—— 窗口自适应；② `fly64/fly64/memory.py:1394`（`_ctrl_x_buf.append`）附近 —— 记录符号切换时间戳；③ `fly64/fly64/memory.py:1377-1462`（`update`/多数票）—— 窗口由 `_vote` 前计算并传入。 |
| **验证方式** | **运行指标**：`flow.json` 新增 `oscillation_window_frames`、`oscillation_alt_median_s`、`oscillation_detected`。**阈值**：① **锁定而非抖动**：在复现交替场景下，连续 600 tick 内 `oscillation_detected` 的**翻转次数 ≤ 4**（每 600 tick 最多 4 次翻转），而改前是逐 tick 抖动；② **可标定**：A/B 把 `check` 的窗长系数 6 改为 3 / 12，`oscillation_window_frames` 必须随之改变；③ **不误伤**：正常探索段（`progress_is_ineffective=false`）`oscillation_detected` 占比 ≤ 5%。 |
| **失败回退** | 条件 ① 失败 ⇒ 回到固定 30 帧并**只记录**（该检测不再驱动反射），另在 `evolution_log` 写 `medium` finding。条件 ③ 失败 ⇒ 收紧为 `alternations >= 5`（提高门槛而非降低，避免把正常探索判为振荡）。 |

### 6.4 c4 — CPG 运动原语的竞争槽（`_lif_motion` 恒真的处置）

| 项 | 内容 |
|---|---|
| **作用脑机制** | `main.py:2521-2530` 的 CPG 取操纵权条件是 `not _lif_motion`，而 `_lif_motion` 在当前运行点**恒真**（`control.y = 70 > 8`）⇒ 运动原语（longjump / backflip …）**结构性不可达**（t1 S29）。 |
| **设计** | 不改 `_lif_motion` 的**数值判据**（`LIF_MOTION_MIN = 8` 仍是"LIF 是否在动"的传感量），而是把**持有运动权威者**从"隐含的 `not _lif_motion`"改为由 §6.1 仲裁状态机维护的**单一谓词** `authority ∈ {lif, primitive}`：CPG 请求注册为候选，只有**胜出**（成效分优于 LIF 解码）才把 `authority` 置为 `primitive`；`main.py:2521` 的 `_lif_motion` 与 `:2529` 的取权分支改为读 `authority == "lif"` / `authority == "primitive"`。⇒ 把"恒真的门"换成"可竞争的候选"，且**用替换而非追加**：`def _has_motion_authority(): return self._authority == "lif"`（原表达式被**移入** `authority` 的判定里，不是在它后面 `or` 一条）。 |
| **F4 修正：为什么必须写清"授予 → 执行"的落点** | t5 §F4：原文只写"把 CPG 请求变成竞争槽"，**没有说明授予的 primitive 如何越过 `main.py:2521` 的 `not _lif_motion`**（该判据在观察运行点恒真）。若实现时在 `_lif_motion` 后面追加 `or granted`，那就是**新增控制分支**，违反 R1。**本项采用"权威谓词替换"**（见上），满足 R2/R3；**执行落点不变**：仍由既有的 `control = cpg_apply_phase(control, cpg_phase)`（`main.py:2530`）写控制量 —— 这是一个**已存在的调用点**，本项不新增任何 `control.*` 赋值位置。 |
| **需修改/新增** | ① `fly64/fly64/main.py:2521-2530` —— 取权条件由 `not _lif_motion` 改为仲裁持有的 `authority`（表达式**移动**而非追加）；② `fly64/fly64/main.py:2438-2511` —— 请求改为注册到 `ArbitrationState`（不直接取操纵权）；③ `fly64/fly64/arbitration.py` —— 增加 `primitive` 候选类型与 `authority` 字段（`burst > primitive > lif`，与 §5.5 冲突矩阵一致）；④ `fly64/fly64/motor_primitives.py:62-123` 不变；⑤ 静态断言（并入 §7.1 T3 的断言文件）：**禁止**在 `main.py:2521` 的表达式上追加 `or` 支路（正则检查"`_lif_motion` 定义行不得含 `or`"），并断言任何 `control.` 赋值的新增行数为 0。 |
| **验证方式** | **运行指标**：`flow.json["arbitration"]["candidates"]` 包含 `primitive`；`flow.json["motion_authority"] ∈ {"lif","primitive"}`；`primitive_granted_count`。**阈值**：① 在 `stuck_duration`/`loop_score` 高且 LIF 解码成效分低的场景下，`primitive_granted_count ≥ 1`（对照：改前 0）且 `motion_authority` 至少出现过一次 `"primitive"`；② 在正常前进段必须为 0；③ 授予后 300 tick 内 `net_displacement_rate` 不下降（否则成效分为负，自动退出）；④ **权威唯一性**：任一 tick 的 `motion_authority` 只有一个取值，且 `burst_active ⇒ authority != "primitive"`。 |
| **失败回退** | 条件 ③ 失败 ⇒ 提高 `primitive` 候选的入场门槛（成效分需高于 LIF 解码 1.5×）；连续两次失败 ⇒ 停用该候选类型（`primitive_candidate_enabled=false`）。**若实现时发现"授予 → 执行"只能靠给 `_lif_motion` 追加 OR 支路（即无法用权威谓词替换实现）⇒ 按 t5 §F4 的要求直接判定本项不可行**：从 P2 移除 §6.4，只保留"`primitive_granted_count` 恒 0"的观测与一条 `medium` finding（诚实标注 CPG 在当前运行点不可达），**不做折中实现**。 |

---

## 7. M4 — 进化闭环：新输出面、可分辨适应度、运行性与责任链

### 7.1 d1 — 新输出面（正面回答"移除闭环唯一输出面"之后是什么）

**新的输出面分三层，按"是否允许闭环自动执行"严格分级**：

| 层 | 内容 | 允许自动执行 | 落点 |
|---|---|---|---|
| **T1** | 对 `active_strategy.json` 中**已注册 + 已通过运行时 A/B** 的 `pid` 有界写入（`min/max` 来自 `brain_tunable_params.json`，且实际钳位与注册区间**必须相交**——当前反例有 **2 个**：`active_strategy.json:5` 的 `bold_explore_stuck_s = 60.0` vs 注册 `[1.0, 10.0]`（越界），以及 `exploration.turn_bias = 0.25` vs 注册 `[0.0, 0.25]`（钉在上界）；**区间不变式与例外见 §4.7**） | ✅ 允许 | `fly64/skills/active_strategy.json`；`main.py:1678-1863` 热重载 |
| **T2** | 增益/腿权重/稳态参数（§5.1/§5.2 新增的 `escape.jump_leg_weight`、`escape.jump_intrinsic_max`，以及 `DopamineGainController` 的初始增益） | ✅ 允许（在 A/B 通过后） | 同 T1（经参数热重载） |
| **T3** | **代码补丁（`fix_template` 写 `.py`）** | ❌ **禁止进入闭环执行路径** | 降级为**只读变更提案**：写入 `fly64/skills/change_proposals.jsonl`（新增），需人工批准后才可落地 |

**T3 降级的实现要点（F3 修正：门禁判据 + 运行时守卫）**：
- **门禁判据必须覆盖两处来源（都算"命中 `.py`"）**：`f.fix_files` **∪** `parse_fix_template(f.fix_template)` 返回的全部
  directive 的 `directive["file"]`。理由（t5 §F3）：`FixExecutor._resolve_file` 的实际目标是
  **模板内的 `# File: …` 优先**，`fix_files` 只作回退 —— `fix_executor.py:488-489` 取 `directive.get("file","")`、
  `:603-609` 是 `rel = file_rel or (fix_files[0] if fix_files else "")`。故只判 `fix_files` 会被
  "`fix_files: []`（或非 `.py`）但模板里写着 `# File: fly64/fly64/main.py`"的 fix 绕过。
- **门禁落点**：`fly64/skills/evolution_skill.py:2644` 的 `if not self.fix_catalog.has_fix(f.pattern_id) and self.auto_fix:` 之后、
  `FixExecutor` 调用（`evolution_skill.py:2653-2668`，实际调用 `:2655`）之前加**执行门禁**：命中 `.py` 且未获批准 ⇒
  **只写提案，不执行**。
- **运行时守卫（第二道，且是唯一能阻止运行期旁路的那道）**：在**唯一写盘点**
  `FixExecutor.execute`（`fix_executor.py:438` 起，`parse_fix_template` 调用在 `:469`）内加**同一判据**的守卫：
  `execute()` 入口即用同一 helper 重新计算"本次是否命中 `.py`"，命中且**未持有批准令牌**（`approved_proposal_ids`）⇒
  立即返回 `FixExecutionReport(manual_action_needed=True)` 且**不产生任何写盘动作**。
  ⇒ "静态断言"只能事后告警，**不能阻止运行时执行**，故必须是"门禁 + 运行时守卫"双道。
- **同一 helper 复用**：门禁与守卫必须调用**同一个函数**（建议 `fly64/skills/fix_guard.py:is_py_patch(fix_template, fix_files)`），
  避免两处判据漂移（R3 单一口径）。
- **legacy 路径处置（t5 §5.7 的开放风险）**：旧副本是 `fly64/skills/evolution_agent.py`
  （**注意 t5 写作 `fly64/fly64/evolution_agent.py`，该路径不存在**）。本次核查：它的 `--auto-fix` 分支
  （`:359-364`）**只打印 "To apply fix: {fix_template}"**，不调用 `FixExecutor`、不写 `.py`；
  全仓无启动引用（`grep evolution_agent` 仅命中它自身、`README.md:368`、`skills/skills.md` 与 `contract_registry.json` 的文字引用）。
  ⇒ 判定为**不是第三条执行路径**，但处置上仍要求：**任何未来的写入者都必须经同一 helper**，
  并在 §7.1 的断言里加一条"`FixExecutor.execute` 是唯一允许写 `.py` 的函数"（`grep -n "\.write_text(" fly64/skills/*.py` 白名单化）。
- **禁止** `fix_template` 中出现 `control.x` / `control.y` / `control.jump` 的赋值（静态断言，落在 `fly64/tests/test_evolution_fix_contract.py`，新增）。
  该断言是**第三道（防回归）**，与上面的门禁/守卫并列，不是门禁本身。
- 提案文件必须带 `proposed_by / pattern_id / rationale / expected_metric / verification_window`，供人工审阅。

**为什么这不是"把闭环关掉"**：T1/T2 已经存在且**真正生效**（S1/S16/S35 判"✅ 生效"），
只是覆盖面错（`navigation.*` 两处死写入、jump 只 1/12 条腿）。§5 把覆盖面修好之后，
闭环的**搜索维度全部落在能改变行为的量上** —— 它从"只能写 `main.py`"变成"能写决定行为的脑参数"。

### 7.2 d2 — 适应度可分辨性（五段修复 + A/A 零假设门）

**现状的四个可复现原因（E-1/E-2 层）**：

| # | 原因 | 位置 |
|---|---|---|
| 1 | 试验窗固定 **120 s 墙钟**，与"参数热重载每 600 tick"和"仿真时间"都未对齐；同一窗口内参数可能被重载多次 | `fly64/skills/evolution_skill.py:2460`（`run_time = 120.0`）；`main.py:1678` |
| 2 | **基线静默漂移**：`main.py:1742-1753` 每 600 tick 钳位并回写 `active_strategy.json`（"P0 self-heal"，`main.py:1756-1879`），而回滚是 `self._inject({})`（`evolution_skill.py:2490,2532`），注释写明"resets to defaults only"——**实际把"当前文件值"写回去，不是注入前的快照** | `evolution_skill.py:2238-2267, 2490, 2532` |
| 3 | **一次试验 ≤5 维同时变**（`_subset_k = min(5, ndim)`，`evolution_skill.py:2325-2326`）⇒ 多维变更不可归因 | 同上 |
| 4 | fitness 的 `unstuck` 项读 `stuck_duration`（`evolution_skill.py:2021,2033,2036`）—— 该量在 HEAD 上正是伪影（§2.3）⇒ 顶层行为项建立在失真量上 | `evolution_skill.py:2019-2036, 2186-2193` |

**五段修复**：

1. **窗口对齐**：试验窗改为 `max(600 ticks, 60 s 仿真时间)` 的**整倍数**，并要求窗口内**参数未被第三方改写**（用 §4.6 的租约保证）。
   落点：`evolution_skill.py:2460` 与 `run_one_cycle`（`:2623-2703`）。
2. **真回滚**：`_inject` 前用 `ParamAuthority.snapshot()` 取快照；失败时 `restore(snapshot)`（**逐 pid 精确恢复**），
   并在租约有效期内让 `main.py` 的自愈回写让行。落点：`evolution_skill.py:2238-2267, 2490, 2532`；`main.py:1742-1753`。
3. **单维/低维归因**：`_subset_k` 从 5 降到 **1–2**，并记录"本次移动的维"与其**在 A/B 语义下的消费点**。落点：`evolution_skill.py:2325-2326`。
4. **剔除伪影输入**：`unstuck` 项不再读 `stuck_duration`，改用 §4 重建后的真实量或轨迹运动学量
   （`net_displacement_rate` / `net_disp_60s`），并把 `missing_inputs` 变为**硬门**（有 `missing_inputs` 即本次试验作废）。落点：`evolution_skill.py:2019-2036, 2119`。
5. **适应度定义（可分辨量的长窗均值）**，权重和为 1：

| 项 | 定义 | 权重 | 为什么可分辨 |
|---|---|---|---|
| `net_disp_rate` | 窗口内**净位移 / 累计路径**（方向效率，无量纲） | 0.30 | 直接来自轨迹运动学，不依赖任何脑内派生量；对照实测 2.75%/5.35% 有巨大动态范围 |
| `coverage_gain` | `(visited_cells_end - visited_cells_start) / window_s` | 0.20 | 整数格数，量化误差小；15% 覆盖率下有充足增长空间 |
| `loop_penalty` | `-min(loop_score/3, 1)` | 0.15 | `loop_score` 由空间记忆直接计算 |
| `waste_penalty` | 现有 `waste_ratio` 惩罚（`evolution_skill.py:2099-2105`） | 0.10 | 已有实现 |
| `learning_progress` | `Δgain_update_count` 与 `Δmb_assoc_count` 的归一化 | 0.10 | **区分"参数改了但没学到"与"学到了"** |
| `meta_channel` | `Δ(intervention 成效分)`，即 §6.1 的升级成效 | 0.15 | 使"换招是否有效"成为可搜索的目标 |

**A/A 零假设门（本方案的关键新增；F5 修正：统计设计 + 样本量 + 回退）**：
- 方法：构造 A/A 试验（候选参数 = 当前值，**不做任何变异**），跑满窗口，记录 `|delta|` 的分布。
- **F5-①：门与 commit 阈值必须脱钩，且 commit 阈值随噪声标定。**
  原设计把门写成 `P95(|delta_A/A|) ≤ 0.03`，而 commit 阈值恰是 `delta > 0.03`（`evolution_skill.py:2505`）⇒
  **由构造决定最多 5% 的零假设窗口会越过 commit 阈值**（假阳性下界 = 门分位数本身）。
  修正为：**门** `P95(|delta_A/A|) ≤ σ_floor`（σ_floor 为目标噪声地板，初值 0.03）；
  **commit 阈值** `threshold = max(0.03, k · P95_noise)`（`k ≥ 2`，默认 k = 2，`P95_noise` 取自最近一次 A/A 报告）。
  ⇒ 当噪声 P95 = 0.02 时阈值 = 0.04；噪声 P95 = 0.05（> 地板）时门先失败，阈值不参与。
  若改用显式显著性检验（置换检验 / paired t 检验）也可以，但**必须同时声明目标 FPR 与功效**（例如 FPR ≤ 1%、power ≥ 0.8 @ 效应 0.05），
  并把该 FPR 作为验收量；**不接受"未声明 FPR/功效"的检验**。
- **F5-②：最小样本量与分位数可靠性。**
  n = 20 的"P95"在统计上约等于最大值，置信区间极宽 ⇒ **最小 A/A 样本量提高到 ≥ 100 个窗口**，
  并给出 `P95` 的 **bootstrap 95% 置信区间**（B = 2000 重采样）；判据用**置信上界**而非点估计
  （`bootstrap_upper95(P95) ≤ σ_floor`）。原设计的第二条判据（"20 次中 |delta| ≥ 0.03 的比例 ≤ 10%"）
  比第一条更弱、**永远不会先失败**，降级为**次要一致性检查**（样本 ≥ 100 且比例 ≤ 5%），不再作为门。
- **F5-③：双窗确认的假阳性率必须实测，不得按独立性估计。**
  相邻窗口共享参数、策略与噪声自相关 ⇒ 联合 FPR **不是** 0.05²。要求：在**同一噪声、同一窗口长度**下
  跑 **≥ 50 对 A/A 双窗**，直接测出"双窗同号且两窗 |delta| 均 > 阈值"的比例，并把它记为
  `aa_two_window_fpr`；该值 ≤ 1% 才允许打开自动 commit（否则继续 shadow）。
- **顺序强制**：**任何 fitness 变更、任何自动 commit 都不得先于该门通过**。
  未通过 ⇒ 延长窗口（×2，最多 ×2 次）/ 多窗平均 / 切换到 §7.3 的轨迹运动学量。
- **F5-④：噪声降不下来时的回退（原设计缺失）。**
  若窗口 ×2 后 `bootstrap_upper95(P95)` **仍 > σ_floor** ⇒ 该 **fitness 维度**标记 `unmeasurable`，
  **从搜索空间移除该维度**（不是继续盲搜，也不是放宽门）：逐维降级顺序 =
  `meta_channel` → `learning_progress` → `coverage_gain` → `waste_penalty` → `loop_penalty` → `net_disp_rate`；
  若 `net_disp_rate`（轨迹运动学量）也不可分辨，则**判 H13 不成立，P2/P3 整体阻塞**并写 `high` 级 finding。
- 落点：新增 `fly64/skills/fitness_aa_gate.py`（复用 `BrainMutator.fitness_components`，只做统计），
  产物 `fly64/skills/fitness_aa_report.json`（含 `n_windows / p95 / bootstrap_ci / k / threshold / aa_two_window_fpr / unmeasurable_dims`）。

**试验流程（改后）**：

```
[开始试验] snapshot = ParamAuthority.snapshot(); lease(owner='evo', pid, ticks=window)
   ↓ 单/双维变异（≤2 维），写入 active_strategy.json
   ↓ 等满窗口（≥600 tick 且 ≥ 60 s 仿真时间），其间自愈回写让行
   ↓ 计算 fitness（长窗均值，五项可分辨量；missing_inputs 非空 ⇒ 作废）
   ↓ delta = cur - base
   ├─ delta > threshold（threshold = max(0.03, 2·P95_noise)）且 A/A 门已通过 ⇒ commit（续租约）；
   │     **双窗确认**：再跑一个等长窗口，两窗同号且 |delta| 均 > threshold，且 `aa_two_window_fpr ≤ 1%`（实测值）才 commit
   └─ 否则 ⇒ ParamAuthority.restore(snapshot)（逐 pid 精确回滚）
```

**验证方式与失败回退（F5 修正后）**：

| 指标 | 阈值 | 失败回退 |
|---|---|---|
| `aa_p95_abs_delta`（+ `bootstrap_upper95`，n ≥ 100 窗） | `bootstrap_upper95(P95) ≤ 0.03` | 未过门 ⇒ **禁止** fitness 变更与自动 commit（仅 shadow 记录） |
| `aa_commit_threshold` | `= max(0.03, 2 · P95_noise)`（与门**脱钩**，k ≥ 2） | 阈值为负或 < 0.03 ⇒ 用 0.03 兜底并记录 |
| `aa_two_window_fpr`（≥ 50 对 A/A 双窗**实测**） | ≤ 1% | > 1% ⇒ 关闭自动 commit，保持 shadow（不得按 0.05² 估计） |
| `delta_exact_zero_rate` | ≤ 30%（对照 60.3%） | 未达标 ⇒ 延长窗口到 2 倍并复测 |
| `commit_rate` | ≥ 5%（对照 1.47%）且 ≤ 30% | > 30% ⇒ 说明门槛过低，按 `max(0.03, k·P95_noise)` 重算阈值并复测 A/A |
| `attribution_ok_rate`（单维试验占比） | ≥ 90% | 未达标 ⇒ 强制降到 1 维 |
| `unmeasurable_dims` | = ∅（逐维降级后仍不可分辨的维度集合） | 非空 ⇒ 该维度移出搜索空间；若 `net_disp_rate` 也进集合 ⇒ 判 H13 不成立，P2/P3 阻塞并写 `high` finding |

**shadow 模式（上线策略）**：新 fitness **先只落盘不决策**（`evolution_log` 同时写 `sim_fitness` 与 `legacy_fitness`），
连续 ≥ 2 个 A/A 窗 + ≥ 1 周影子记录后，才允许切换为决策量。

### 7.3 d3 — 观测值落盘（B5：闭环必须能复盘"当时看到了什么"）

**现状**：`evolution_log.jsonl` 每行只有 `finding` 的 `id` 与 `severity`，**从不记录任何传感器数值**
（t2 §1.3）⇒ 事后无法证明闭环当时看到了什么。

**方案**：在 `evolution_skill.py:2923-2929` 的日志写入中增加 `context` 块：

```json
{"timestamp": ..., "iteration": ..., "findings": [...], "fixes": [...],
 "verifications": [...], "evolution": ..., "errors": [...],
 "context": {
   "stuck_duration_true": 0.0, "net_disp_60s": 0.0, "loop_score": 0.0,
   "coverage_cells": 0, "revisit_count": 0, "waste_ratio": 0.0, "forward_speed": 0.0,
   "ctrl": [0, 0, false], "anomaly_state": "", "escape_behavior": false, "reflex_active": false,
   "gain_per_pathway": {"visual": 0, "forward": 0, "turn": 0, "jump": 0, "recurrent": 0},
   "gain_update_count": 0, "mb_assoc_count": 0, "life_adapt_lr": 0, "rewrite_delta": 0,
   "jump_leg_current": 0.0, "jump_pool_occupancy": 0.0, "fwd_pool_occupancy": 0.0,
   "jump_rate_ratio": 0.0, "fwd_homeo_gain": 0.0, "jump_homeo_gain": 0.0,
   "cx_effective_steering_gain": 0.0, "cx_loop_break_count": 0,
   "arbitration": {...}, "param_authority": {...}, "terminal_surrender": false,
   "param_write_mismatch": 0, "version": {"brain": "2.24.0", "skill": "3.5.0"}
 }}
```

| 项 | 内容 |
|---|---|
| **作用脑机制** | 自观测（系统必须能读到自己），是 M3 与 M4 的交界 |
| **数据流** | `model.*` / `memory_ctrl.*` / `DopamineGainController` / `ArbitrationState` → `flow.json` + `/memory.json` → `DataCollector.sample`（`evolution_skill.py:788-829`）→ `evolution_log.jsonl` |
| **需修改/新增** | ① `fly64/skills/evolution_skill.py:2923-2929`（写 `context`）；② `evolution_skill.py:788-829`（`DataCollector.sample` 读取新字段）；③ `fly64/fly64/main.py:3034-3068`（遥测发布段，已在发布 `dopamine_gain` / `gain_update_count`，扩容即可） |
| **验证方式** | ① `evolution_log.jsonl` 每行 `context` 非空且字段数 ≥ 25；② 任取一行的 `context.stuck_duration_true` 与同 tick 的 `flow.json` 读数一致；③ 事后复盘：给定任一 finding，能用**同一行的 `context`** 复现判定（不需要外部文件） |
| **失败回退** | 写入异常 ⇒ 不得阻塞主循环（`try/except` 包裹，与现有风格一致）；连续 100 行 `context` 为空 ⇒ 写 `high` 级 finding 并按 §7.4 告警 |

### 7.4 d4 — 闭环存活自检与漏斗告警（组织性成因的处置）

| 项 | 内容 |
|---|---|
| **现状（t2）** | 闭环最后写入 `evolution_log.jsonl` 是 **2026-09-17T10:22:55**，审计时（09-24 12:33）已停摆 **7 天**；无 python 进程、无 `.evo_loop.lock`、无计划任务；唯一数据源 dashboard `127.0.0.1:8765` **不可达**（"无法连接到远程服务器"）；4.46 天内 iteration 归零重启 **≥9 次**；此后 `evolution_history.json` 靠人手更新到 `EVO-073`。漏斗 `13728 iter → 44159 findings → 11 fixes → 11 verified → 0 effective`，**effective=0 却无任何告警**。 |
| **方案** | ① **存活心跳**：每轮把 `{"iteration", "ts"}` 写入 `fly64/skills/.evo_loop_heartbeat.json`；② **存活自检**：`main.py` 内已有的 `EvolutionPipeline(auto_fix=False, window_seconds=120)`（`main.py:1419-1425`）在读 heartbeat 时若 `now - ts > 120 s` ⇒ 在 `/memory.json["evo_loop_stale"]` 暴露并写 `high` 级 finding；③ **漏斗告警**：新增 `fly64/skills/evo_funnel_alarm.py`，对 `compute_funnel`（`evolution_skill.py:270`）的四个转化率设置告警：`rate_finding_to_fix == 0`（连续 3 天）、`rate_verified_to_effective == 0`（连续 7 天）、`iterations` 增量 = 0（1 小时）、`errors` 行占比 > 5%；④ **数据源冗余**：`DASHBOARD_BASE` 单点（`evolution_skill.py:7xx` 的 `fetch_json`）增加**文件回退**——dashboad 不可达时直接读 `fly64/artifacts/latest.jsonl` 尾部与 `flow.json` 落盘文件，使"数据源不在 ⇒ 连 finding 都不产生"不再成立 |
| **验证方式** | ① **杀死闭环**：手动停止守护进程，`evo_loop_stale` 必须在 **≤120 s** 内为 true 且产生 `high` finding；② **漏斗**：把 `fixes_recorded` 人为置 0（测试夹具），告警必须触发；③ **数据源冗余**：关闭 dashboard，`run_one_cycle` 必须仍能产出 finding（对照：改前 `Waiting for dashboard...`） |
| **失败回退** | 告警通道异常 ⇒ 至少保证 `agent_state`/`/memory.json` 可见（本地降级，不依赖任何外部服务） |

### 7.5 d5 — 责任链、pattern 集与终止条件

**(a) pattern 条件键零生产者的静默失效**
- `ramp_trap` 的条件键 `position_unchanged_30s` **全仓库无生产者**（只有 `position_unchanged_60s`，`evolution_skill.py:863,1009`；该键由 commit `048fd16`（2026-09-18）引入，**比闭环死亡晚 1 天**）。
- 失效机制：`_check()`（`evolution_skill.py:1066-1087`）**先 `total += 1` 再 `if val is None: continue`** ⇒ 缺 1 键即 `passed < total` ⇒ **永久不命中**，唯一痕迹是 4773 次 `low` 级 `telemetry_gap`。
- 处置：① 为 `ramp_trap` **补生产者**（新增 `position_unchanged_30s` 的观测，**不改回 60 s**，尊重 048fd16 的收紧意图）；
  ② `_check()` 改为"缺键 ⇒ 该 pattern 标记 `unreachable` 并告警"，而不是静默继续；
  ③ 启动时做 **pattern × 生产者 集合差自检**，任一 `unreachable` pattern 必须进 `high` 级 finding（对照现状：2/16 不可达却无人知）。

**(b) pattern 集的"已放弃终态"覆盖**
- 新增 `terminal_surrender_stuck`（`severity: high`），其"脑侧响应"是**允许 §5/§6 的自适应面被激活**（例如提高 `escape.jump_leg_weight` 的搜索权重、解锁 CX 环路突破），
  **不是**写控制量（§6.2 的验证条件 ③ 已覆盖）。

**(c) `has_fix()` 生命周期缺陷**
- 现状：`has_fix()`（`evolution_skill.py:1163-1164`）= "存在未回滚 fix" ⇒ **一条无效 fix 永久关闭该 pattern**
  （**F8 修正：现关闭 11 个 `pattern_id`，不是 13 个**）。**统计口径（本次独立复算）**：`fix_catalog.json` 共 19 条 fix、
  `meta` 记 `effective 0 / ineffective 11 / reverted 8`；按 `reverted == false` 过滤得 **11 条**，
  它们覆盖 **11 个 distinct `pattern_id`** —— `below_ground_stuck, circle_loop, cliff_standoff, fallen_recovery_stuck,
  low_coverage_stagnation, mbon_saturation, micro_loop_weave, primitive_zero_disp, ramp_trap, suspended_animation, telemetry_gap`。
  其中 **10 个**是 `default_patterns.json` 的 pattern（16 个之一），`telemetry_gap` 不是 pattern（属诊断/遥测类 finding）
  ⇒ 若按"实际被关闭的 pattern"计是 **10**，按 `has_fix()` 的判据（只比 `pattern_id`）计是 **11**。两个数都写出，避免再次出现口径歧义。
  `auto-fix` 默认关闭（`evolution_skill.py:2795` 的 `--auto-fix` 为 `action="store_true"`）且有"连续 3 次失败 → `auto_fix = False`"熔断（`evolution_skill.py:2739-2740`），**只在 `errors` 里留一行**。
- 处置：把 fix 生命周期改为 `proposed → measuring → effective | ineffective | reverted`；
  仅 `effective` 长期关闭该 pattern，`ineffective` **允许重开**（并且重开必须使用**不同的响应形态**，避免重复同一条无效补丁）；
  熔断与 `effective=0` 一律进告警通道（§7.4）。

**(d) 本能晋升的边界与责任链**
- 现状：线上 `scene_strategy_bindings.json` 有 2 个 bucket，各 `improved = 1` < `PROMOTE_MIN_IMPROVED = 2` ⇒ `promoted = false` ⇒ `get_binding()` 恒 `None`（t1 S14）。
  且候选 `turn_bias = 0.6 / 0.7` **落在 `CLAMP_BOUNDS["exploration.turn_bias"] = (0.0, 0.25)` 之外**（`main.py:1102-1105`）⇒ 一旦晋升会被自愈**静默改写**（`main.py:1742`）。
  同时 `coach_outcomes.jsonl` **30/30 行 `scene_label` 为空** ⇒ `record_outcome` 直接 `return None`（`instinct_bindings.py:265-268`）。
- 处置：① **先修边界再谈晋升**：把候选参数限制在**注册区间 ∩ 运行期钳位**之内（`turn_bias ∈ [0, 0.25]`），否则不得进入绑定库；
  ② 修复 `scene_label` 生产（`plugin/coach_outcomes.py:51-66`）与防截断侧车（`.hwm` / `.snap` 必须存在）；
  ③ `instinct_bindings.py` 的 docstring 已明确要求"**不得降低门禁来制造晋升**" ⇒ 本方案**不降低 `PROMOTE_MIN_IMPROVED`**，只修上游证据链。

**(e) 版本链自检（红灯）**
- 现状：`python -m skills.evolution_skill --history-check` 在 **HEAD 上 FAIL**：`SKILL_VERSION 3.5.0`（`evolution_skill.py:42`）≠ canonical **3.5.1**（`evolution_history.json.canonical_versions.skill`）；而 `main.py:50` 已写 `SKILL_VERSION = "3.5.1"`。
- 处置：① 把 `evolution_skill.py:42` 对齐为 `3.5.1`（在其自身的变更历史中登记）；② `--history-check` 纳入 §7.4 的自检通道，**红灯不得阻塞诊断**但必须告警；③ 版本三元组（`brain`/`skill`/`canonical`）作为 `context.version` 每次落盘（§7.3）。

**(f) 教练直写控制的边界**
- 现状：`main.py:2330-2348` 的教练命令消费者**直接写 `control.x/y/jump`**（t1 S32），与本方案"排除硬编码控制补丁"正面冲突。
- 处置：**不删除**（人工介入通道必须保留），但 ① 明确它**不在自治闭环输出面内**（§7.1 的 T1/T2 之外）；
  ② 把教练的**非安全类**建议改为经参数授权点写入（§4.6）；③ 安全类（防坠落/防深坑）保留直写并标注为"人工/安全通道"；
  ④ 所有直写必须在 `param_history.jsonl` 留一条归因记录 —— **F12② 修正：字段名是 `source`，不是 `owner`**
  （`main.py:1873-1876` 的实际写入为 `{"ts", "key", "from", "to", "source": "self-heal"}`）。
  **统一口径（R3）**：直写记 `source = "coach-direct"`（安全通道 `source = "safety-guard"`），
  **不新增第二套来源字段**（不得同时存在 `owner` 与 `source`）；§4.6 的 `ParamAuthority` 内部持有 `owner` 仅作租约记账，
  落盘时一律映射到 `source`。

---

## 8. 实施优先级与路线图

| 阶段 | 条目 | 依赖 | 交付判据（全部通过才进入下一阶段） | 预估工作量 |
|---|---|---|---|---|
| **P0 · 观测/口径（M3）** — 不改行为 | a1 唯一口径表（含 §5.3 的口径替换设计冻结）<br>a2 伪影切断（`StuckDetector` 单位对齐 `memory.py:135,206-217` ← `main.py:2650`；`memory.py:1994-1995` 泄放空操作）<br>a3 解码器状态清零与真实卡死时长重算<br>a4 接线运行时 A/B（§4.5）+ 参数授权点（§4.6）<br>a5 观测值落盘（§7.3）<br>a6 漏斗告警 + 存活自检 + 数据源冗余（§7.4）<br>a7 `--history-check` 红灯修复（§7.5-e）<br>**a8 参数语义迁移与区间不变式（§4.7，F1）** | — | ① 6000 tick 内 `stuck_score` 不再恒 1.0；② 真实卡死时长与轨迹运动学一致（±5%）；③ `evolution_log.jsonl` 每行 `context` 非空；④ 杀进程后 ≤120 s 内告警；⑤ `--history-check` PASS；⑥ **a8：`clamp(live)==live` 对 39/39 pid 通过，且 `active_strategy.json:8` 已迁移为 0.75、`:5` 落在 `[1,10]`（此断言不通过即阻断 P1 上线）** | 3–5 人·日 |
| **P1 · 脑侧自适应面（M1）** | b1 MBON→jump 增益链（§5.1）<br>b2 跳池稳态（§5.2）<br>b3 jump 门归一化（§5.3，**替换非新增**）<br>b4 两处死写入（§5.4）<br>b5 CX 环路突破可达化（§5.5）<br>b6 死代码清理（§5.6） | **P0-a8（区间不变式）与 P0-a4（A/B 判据）都必须先可用** | ① §5.1–§5.4 每条的 A/B 双向（升/降）都通过，且 §5.1 的**位精确回归断言**先过（F2）；② §5.5 的 `cx_loop_break_count_burst_off ≥ 1`（F6：burst-off 窗口内计数，且与 `deadlock_burst_count` 时间戳不相交）；③ 跳占空比 ∈ [0.1%, 5%] 且**确实出现过一次触发**（F1：含下界）；④ 无一条新增 `control.*` 写入点（静态断言） | 5–8 人·日 |
| **P2 · 适应度与仲裁（M4 主体 + M2）** — 与 P1 后半并行度低 | d1 新输出面与 T3 降级（§7.1）<br>d2 适应度五段修复 + A/A 门（§7.2）<br>d3 pattern 集与终止条件（§7.5-a/b/c）<br>d4 本能边界与责任链（§7.5-d）<br>c1 升级状态机（§6.1）<br>c2 终态判据（§6.2）<br>c3 检测窗自适应（§6.3）<br>c4 CPG 竞争槽（§6.4） | P1 必须先行（否则 fitness 仍测不到东西）；**d2 可在 P1 之前**以 shadow 模式先行 | ① `aa_p95_abs_delta ≤ 0.03`；② `delta_exact_zero_rate ≤ 30%`；③ 复现场景下 `arbitration.level` 升级发生且 6000 tick 内升降 ≤ 2 次；④ t2 真引擎回放至少命中 1 个 `high` pattern；⑤ T3 提案不进入执行路径（静态断言） | 6–10 人·日 |
| **P3 · 自治运行与泛化** | 闭环守护与调度（计划任务/守护进程）<br>shadow → auto 切换（≥1 周影子 + 2 个 A/A 窗）<br>参数空间扩展（A/B 通过的新 `pid`）<br>跨场景泛化（本能晋升在修好边界后重新评估） | P0/P1/P2 全绿 | ① 连续 7×24 无停摆（心跳无断档）；② `effective_count ≥ 1`（**首次**产出被证实的改进）；③ 同一参数在 ≥3 个场景上的符号一致 | 5–8 人·日 |

**关键路径**：P0-a2 → P0-a4 → P1-b1/b2/b3 → P2-d2（A/A 门） → P3-auto。
**并行**：M4 的 d1/d3/d4/d5-a-e 与 P0 并行；d2 的 shadow 部分可与 P0 同步上线（只落盘不决策）。

---

## 9. 与原报告修复路线的差异对照（含逐条否决理由）

### 9.1 被否决的原报告条目

| 原报告条目 | 原主张 | **否决理由（技术论据优先）** | 本方案的脑原生替代 |
|---|---|---|---|
| **P0.1** | 在 `stuck_ramp` reflex 序列里加 jump 相位（`memory.py ~1550-1580`） | ① **技术前提错误**：jump 的唯一执行门是 LIF 解码 `model.py:2478`，**对 `anomaly_state` 无依赖**；报告列出的 4 条路径都是次级路径（t1 §1.6）；② 该 run 中反射层**从未取得操纵权**（`ctrl_y ∈ {50,70}`，无 30/127；`-60/-69` 均为 0，正侧仅 `60`×1、`69`×7 共 8/6000，**不构成群**）⇒ 改它不改变该运行点；③ 属被排除的硬编码控制补丁 | §5.1 + §5.2 + §5.3：让跳池的"学习表达腿"经过增益、给跳池稳态、门限归一化 ⇒ **跳跃脱困成为学得的能力** |
| **P0.2** | `stuck_score > 0.9 且 stuck_duration > 300 s` 时强制 jump | ① `stuck_score` 是构造伪影（`memory.py:135 vs main.py:2650`）⇒ 触发条件本身失真；② "强制 jump"是 `force_jump()` 硬编码写入；③ 它与 t2 查到的 `fix_0013` 是同一路线的两个实例，**且后者已被数据否证**（`effective=false`，458.98 → 464.72 更差） | §6.2 的 `terminal_surrender` 只做**判据**（观测层），其响应是**解锁脑侧自适应面**，不写控制量 |
| **P0.3** | 让 `wall_persist > 2 s` 独立于 `anomaly_state` 触发 `wall_stuck` reflex | 方向正确（"放弃"不应是否定检测的条件），但实现形态是"再加一条反射触发路径"= 控制分支；且报告称其被 `stuck_ramp` 覆盖，而代码顺序相反（`memory.py:1369` 先于 `:1371`） | §6.2：改**判据**而非新增反射 —— `_detect_wall_stuck` 加一条独立于 `escape_behavior` 的 OR 支路（`memory.py:1319-1321`） |
| **P1.1** | 钳制 `ctrl_x` 单帧变化 ≤ ±20 + 加入死区 | ① 这是**输出层限速** = 硬编码控制补丁；② 归因错：`raw_x = clip(turn_rate·1100, ±70)` 在 `abs(turn_rate) ≥ 0.0636` 即饱和，实测前 5455 点**从未回到 0**、满量程 5330/6000 ⇒ "疯狂切换"是**饱和非线性对近零净输入的放大**，不是"控制器频率过高"；③ 它作用于**症状**，而症状是时域积分的结果，无独立因果力 | 不改输出层：§5.4 修 CX 导航旋钮死写入 + §5.5 让 CX 环路突破可达 + §6.1 让"换招"成为显式转移 ⇒ 改变净输入的**分布**（导航量级从 ≤0.018 V/tick 的 1/10 提升到可竞争） |
| **P1.2** | `ctrl_y` 动态调整（转向时降速） | 同类：输出层直接改写。实测 `ctrl_y = 70` 占 5519/6000（`forward_rate ≥ 0.043` 满速），而前向池**恰有** `forward_homeo_gain`（`model.py:1452-1475`）把它钉在饱和 —— 真问题是"稳态上限与解码门同量级"，不是"推力不调整" | §5.2 给跳池**对等**稳态 ⇒ 两个池的工作区间一致，前向池不再独占满速 |
| **P1.3** | 降低 `oscillating` 能量/时间阈值（常量改写） | 改写常量不是控制补丁，但**阈值仍与真实周期同量级（同量级问题不因改常量而消失）**，且没有判据能分辨"改对还是改坏" | §6.3：**窗口自适应于实测交替周期**（`W = clip(6·T_alt, 30, 300)`），门限次数不变 |
| **P1.4** | `stuck_ramp` 执行后无改善 ⇒ 自动升级到 `oscillating` | ① 该"升级"是 `trigger_reflex('oscillating')` = 又一次控制补丁；② **没有判据能定义"无效"** —— fitness 不可分辨（60.3% delta 恰为 0） | §6.1 的升级状态机把"无效"定义为可计算的成效分（§7.2 的 `meta_channel`）与 `ineffective_ticks`，并**只升级自适应面** |
| **P2.3** | 引入完整 PID（Kp 降低 / Kd 增加） | 控制补丁；且振荡是饱和解码的表象 | 不采用。真实调节面是 §5 的脑侧作用面 |
| **P2.4** | 启动全局路径规划 fallback | 引入**新模块**取代脑的导航（与外置控制器同源），且路径规划不共享脑的可塑性 | 不采用。§5.5 把"环行破锁"交回 CX 原生机制 |
| **P2.1/P2.2** | novelty 重校准 / 空间记忆分辨率 | 方向与 M1 同向（都属"作用点"问题）但与 §5 重复 | 合并入 §5（novelty 经 `exploration.visual_gain_novelty_boost` 与 CX 目标权重，已有 §5.4/§5.5 覆盖） |

### 9.2 原报告 7 层根因链的继承与否定

| 原报告层 | 本方案处置 |
|---|---|
| 1 `ctrl_x ±70` | **继承为症状**（数据可复现：满量程 5330/6000、前 5455 点无一次 0）；**否定归因**（"控制器增益过高"） |
| 2 `ctrl_y` 恒 70 | **继承为症状**；**否定归因**（"前进推力不调整"）→ 真因是前向池稳态把池钉在饱和 |
| 3 X/Z 效率 2.8%/5.4% | **继承为症状**（t3 重算 2.75%/5.35%）；**否定"有独立因果力"** |
| 4 优先级排序缺陷 | **否定**：`_vote` 中 `oscillating`(:1367) 在 `stuck_ramp`(:1371) **之前**；真缺陷是检测口径（§6.3） |
| 5 `stuck_ramp` reflex 不含 jump | **事实为真但非主路径**（`model.py:2478` 是主路径）；报告的 4 条路径是次级路径 |
| 6 反射疲劳 | **否定**（伪影 + 分类不可复现 + 反射层从未取得操纵权 + burst 必现却 0/6000） |
| 7 `wall_stuck` 失效 | **现象继承、归因修正**：代码顺序相反；真因是 `escape_behavior` 自锁（§6.2） |

### 9.3 "不改"的清单（明确声明不做，防止误读为遗漏）

1. **不改 `_vote()` 的优先顺序**（严重度排序语义正确）。
2. **不改 `raw_x`/`raw_y`/`jump` 的饱和形式**（那是症状生成器，改它=控制补丁）。
3. **不降低 `PROMOTE_MIN_IMPROVED`**（`instinct_bindings.py` 的负结果记录明确禁止）。
4. **不新增第 5 个 jump 门限**（§5.3 用替换）。
5. **不放宽 `GAIN_MIN = 0.5`**（只对 jump 通路单独设 `JUMP_GAIN_MAX = 4.0`，且这一项也需 A/B 通过）。
6. **不删除教练直写控制通道**（安全/人工通道；只把它移出自治输出面）。
7. **不在闭环执行路径上执行任何 `.py` 补丁**（T3 降级为提案）。

---

## 10. 可验证指标总表

| ID | 指标 | 落点（新增观测） | 基线（现状） | 目标阈值 | 失败回退 |
|---|---|---|---|---|---|
| V1 | `stuck_score` 非常量性 | `memory.json` | 恒 1.0（构造伪影） | 6000 tick 内取值 ≥ 3 个不同值 | 未达标 ⇒ 阻塞 P1 全部条目 |
| V2 | 真实卡死时长与轨迹一致 | `flow.json` | 无 | 与运动学重算差 ≤ 5% | 差异 > 20% ⇒ 回退 P0-a2 |
| V3 | `param_wiring_ab` 判定覆盖率 | `fly64/skills/param_wiring_ab.json` | 39 参数**均只有注册表自称** `wired: true`（静态自证；`audit_contract_pairs.py` 不扫注册表 —— F7） | 100% 有 A/B 判定；`wired=false` 者从搜索空间剔除 | A/B 无法执行 ⇒ 只用人工确认的 `pid` |
| V4 | `jump_leg_current` 对 `escape.jump_leg_weight` 的响应 | `flow.json` | 无（腿绕过增益） | **① 位精确回归（F2，先过）**：默认权重 + 标称增益 ⇒ `v[jump_nodes]` 增量与改动前**逐位相同**；② 0.35→0.80 时升 ≈2.29×；0.35→0.10 时降 ≈0.286× | ① 失败 ⇒ 立即回滚 §5.1（不进 A/B）；② 无响应 ⇒ 剔出搜索空间并恢复常量 0.35 |
| V5 | `jump_pool_occupancy` P95 | `flow.json` | 0（跳池静默） | 非零 tick 占比 ≥ 5% 且 P95 ≤ 0.20（标定前提：V4① 已通过） | P95 > 0.20 ⇒ `jump_intrinsic_max` 减半 → 置 0 |
| V6 | `ctrl.jump` 占空比（**F1 改写为可判定形式**） | `bridge`/`flow` | **0/6000 = 0.0%** | **占空比 ∈ [0.1%, 5%]**（下界 = 确实会触发，上界 = 与 0.8 s 不应期一致），且门限 6000 tick 内真/假都出现；统计窗口**排除 burst 窗口**（F6：burst 期间 `control.jump=False`） | 恒真/恒假或越界 ⇒ 回退 §5.3 候选 A；若因迁移未做导致占空比为 0 ⇒ 先执行 §4.7 P0-a8 |
| V7 | `cx_effective_steering_gain` 写读一致 | `flow.json` | 0.12（写 0.5 无效） | 写入值 ≤ 1200 tick 内在 `_goal_comp` 可见；`param_write_mismatch = 0` | 不一致 ⇒ 回退 §5.4 |
| V8 | `cx_loop_break_count_burst_off`（**F6 改写为可归因形式**） | `flow.json` | 0（4000 tick / stuck 1000 s） | **burst-off 窗口内**复现场景 4000 tick 内 ≥ 1；正常探索段 = 0；且与 `deadlock_burst_count` 的时间戳集合**不相交** | 旋钮无效 ⇒ 回退 §5.5 等 §5.4；**仍无法归因 ⇒ 按 t5 §F6 放弃归因**：V8 降为非归因观测，§5.5 判未通过 |
| V9 | `aa_p95_abs_delta`（**F5 修正**） | `fly64/skills/fitness_aa_report.json` | 未测（等价于背景噪声未标定） | `bootstrap_upper95(P95) ≤ 0.03`，**n ≥ 100 个 A/A 窗**；`aa_commit_threshold = max(0.03, 2·P95_noise)`；`aa_two_window_fpr ≤ 1%`（≥50 对 A/A 双窗**实测**） | 未过门 ⇒ 禁止 fitness 变更与自动 commit；噪声地板降不下 ⇒ 按 §7.2 F5-④ 逐维 `unmeasurable` 剔除 |
| V10 | `delta_exact_zero_rate` | `evolution_log.jsonl` | 60.3% | ≤ 30% | 未达标 ⇒ 窗口 ×2 复测 |
| V11 | `commit_rate` | 同上 | 1.47% | 5% ~ 30% | > 30% ⇒ 按 `max(0.03, k·P95_noise)` 重算阈值（F5）并复测 A/A |
| V12 | `effective_count` | `fix_catalog.json` | 0（19 条 fix 全无效） | ≥ 1（首个被证实的改进） | 长期为 0 ⇒ 回到 P1（说明作用面仍未打通） |
| V13 | `arbitration.level` 升级发生且不抖动 | `flow.json` | 无状态机 | 升级 ≥ 1 次；6000 tick 内升降 ≤ 2 次 | 抖动 ⇒ `dwell_ticks` ×2（≤ ×4）；仍失败 ⇒ 停用 |
| V14 | 真引擎回放命中 `high` pattern 数 | `DiagnosisEngine` 回放 | 0 个 high（只 medium+low） | ≥ 1 个 high | 0 ⇒ 检查 §7.5-a 的键生产者 |
| V15 | `evolution_log.jsonl` 的 `context` 完整度 | 日志 | 0 字段（只记 finding id） | 每行 ≥ 25 字段且与 `flow.json` 一致 | 连续 100 行为空 ⇒ `high` finding + 告警 |
| V16 | 闭环存活 | `.evo_loop_heartbeat.json` | 停摆 7 天无告警 | 心跳间隔 ≤ 120 s；断档即告警 | 告警通道异常 ⇒ 至少本地可见 |
| V17 | `terminal_surrender` 判定正确性 | `flow.json` | 无此判据 | 终态回放 = true；正常段 = false | 正常段误判 ⇒ 提高阈值；两次失败 ⇒ 降为 `medium` 仅记录 |
| V18 | `oscillation_detected` 稳定性 | `flow.json` | 逐 tick 抖动（窗与周期同量级） | 600 tick 内翻转 ≤ 4 次；正常段占比 ≤ 5% | 失败 ⇒ 回固定 30 帧并只记录 |
| V19 | `--history-check` | CLI | **FAIL**（3.5.0 vs 3.5.1） | PASS | 无（版本必须对齐） |
| V20 | T3 提案不进入执行（**F3 修正**） | ① 门禁（`evolution_skill.py:2644` 之后）② **`FixExecutor.execute` 内运行时守卫** ③ 静态断言 `fly64/tests/test_evolution_fix_contract.py` ④ `change_proposals.jsonl` | 8/16 pattern 指向 `main.py`；且**模板内 `# File:` 优先于 `fix_files`**（`fix_executor.py:488-489,603-609`）⇒ 只判 `fix_files` 可被绕过 | 0 条 `.py` 补丁被执行；全部落提案；**判据同时覆盖 `fix_files ∪ parse_fix_template(...).file`**；运行时守卫可被独立注入测试（构造 `fix_files=[]` 但模板含 `# File: …main.py` 的用例必须被拦下） | 断言/守卫失败 ⇒ 阻塞 P2 上线；门禁与守卫必须是同一 helper（不得两处判据漂移） |
| V21 | **区间不变式（F1 新增）** | `memory.json["clamped_keys"]` + 启动自检 | 线上 2 个 pid 越界/钉界（`bold_explore_stuck_s=60` 越界、`turn_bias=0.25` 钉上界） | `clamp(live)==live` 对 **39/39** pid 通过；`min<live<max`（`default==max` 的两个 pid 退化为 `min<live≤max`；见 §4.7）；`:8` 迁移为 0.75 后同类断言通过 | 任一失败 ⇒ **阻断 P1 上线**（这是 P0-a8 的验收） |
| V22 | **RULE-19 契约迁移完整性（F13 新增）** | `fly64/tests/test_gate_units.py` + `fly64/contract_registry.json` | `gate_jump_threshold` 被 4+ 条 PIN 断言为 Hz（`default>2.0`、`min>=2.0`、`description` 含 `"Hz"`/`"RULE-19"`/`"1/dt"`/`"telemetry.py"`） | ratio 契约 PIN 全绿；`contract_registry` 的 `threshold_unit` 已迁移；`main.py:2891-2894` 默认值与注册表一致；且新增「`allowed is None` ⇒ `_vote` 逐 tick 不变」PIN | 迁移未同步 ⇒ **§5.3 整体不上线**（保持 Hz 语义） |

---

## 11. 风险、红灯与治理

| ID | 风险 | 触发条件 | 处置 |
|---|---|---|---|
| R1 | 增益链扩面导致跳池持续发放（跳变常态，动量浪费/卡死） | `jump_pool_occupancy` P95 > 0.20 | §5.2 的自动回退（`jump_intrinsic_max` 减半 → 置 0） |
| R2 | 门限归一化后门恒真，跳占空比失控 | `ctrl.jump` 占空比 > 5%（burst-off 窗口统计） | §5.3 自动 ×2 抬门；两次失败回落 0.75 并标 `high_risk` |
| R3 | 本能晋升在边界未修好前被激活，锁死错误本能 | 绑定库出现 `turn_bias > 0.25` 的候选 | §7.5-d：候选必须落在注册区间 ∩ 钳位之内；`promoted` 前人工复核 |
| R4 | 升级状态机抖动或产生无界搜索 | `arbitration.level` 升降 > 2 次/6000 tick | `dwell_ticks` ×2；`level` 上界 2；仍失败则停用 |
| R5 | 检测窗自适应把正常探索判为振荡 | 正常段 `oscillation_detected` 占比 > 5% | 收紧 `alternations >= 5`（提高而非降低门槛） |
| R6 | A/A 门不通过却强行启用新 fitness ⇒ 盲搜继续 | `bootstrap_upper95(P95) > 0.03`（n ≥ 100）或 `aa_two_window_fpr > 1%` | **硬门**：禁止 fitness 变更与自动 commit，保持 shadow；噪声地板降不下 ⇒ 逐维 `unmeasurable` 剔除（§7.2 F5-④） |
| R7 | 参数写入权争抢导致试验被污染 | 租约冲突 / 第三方写入 | §4.6 授权点：试验期内自愈让行；冲突即作废该试验 |
| R8 | **红灯：`--history-check` HEAD FAIL** | 每次启动 | 必须修复（§7.5-e）；未修复前**闭环不得进入 P3** |
| R9 | **红灯：commit 048fd16 把 `ramp_trap` 改瞎**（`position_unchanged_30s` 零生产者，落地于闭环死亡后 1 天） | pattern 自检 | §7.5-a：补生产者 + 缺键告警 + 启动自检 |
| R10 | 把检测伪影当故障证据再次误导方案 | 任何引用 E-4 层数值处 | 强制标注「检测伪影」+ 假设 H1（§0.1） |
| R11 | **红灯（F1）：语义翻转 + 越界值共存 ⇒ 静默收紧** | `active_strategy.json:8 = 3.082…` 在比值语义下 ⇒ 门严 2.5–3.3×；或任一 pid 的 `clamp(live) != live` | §4.7 P0-a8：上界 4.0 + 显式迁移到 0.75 + `min<live<max`（含 `default==max` 例外）硬断言；断言失败即**阻断 P1** |
| R12 | **新增（F5）：A/A 样本不足 ⇒ P95 不可靠、假阳性率被低估** | n < 100 窗，或按 `0.05²` 估计双窗 FPR | §7.2：n ≥ 100 + bootstrap 置信上界判据 + ≥50 对 A/A 双窗**实测** `aa_two_window_fpr`；不达标不得打开自动 commit |
| R13 | **F13：§5.3 语义替换未迁移既有单位契约 ⇒ PIN 转红 / CI 阻断** | `pytest fly64/tests/test_gate_units.py` 失败，或 `contract_registry.json` 与注册表 unit 不一致 | 同批迁移 `test_gate_units.py` + `contract_registry.json` + `main.py:777-783/2891-2894`；未迁移则回退 §5.3 到 Hz 语义 |

---

## 12. 与原报告"预期效果"的差异

原报告称"**P0 修复后预期效果**：`stuck_ramp` 状态下将执行 jump，系统能突破局部卡死；`wall_stuck` 在 2 s 后触发反转/转向"。
本方案的差异是**可判定性**：

| 维度 | 原报告 P0 | 本方案 |
|---|---|---|
| 是否改变行为 | 会（立刻看到 jump） | **P0 阶段不改行为**（只修观测），P1 起才改变 |
| 是否可判定 | ❌ 判据（`stuck_score`）是伪影；fitness 不可分辨 | ✅ 每条都有独立观测指标 + 阈值 + A/B 双向验证（§10） |
| 是否可积累 | ❌ 0 effective / 4.46 天 | ✅ 以 `effective_count ≥ 1` 与 `commit_rate ≥ 5%` 为硬门 |
| 是否遇到新型陷阱有效 | ❌ 只解决"墙壁+stuck_ramp"这一种形态 | ✅ M2 的升级语义覆盖未知情形 |
| 与脑模型的关系 | 绕过脑（外置控制器） | 全部经脑机制（增益 / 突触 / 稳态 / 仲裁 / 参数） |

---

## 13. 待验证假设清单（供 t5 按级验证；**不得当作断言**）

> 沿用 t3 §9 的编号，并新增本方案引入的假设（H10–H14）。

| ID | 假设 | 支持证据 | 反证/风险 | 关闭它需要什么 | 影响本方案的哪一条 |
|---|---|---|---|---|---|
| **H1** | `.tmp/fly64_trajectory.json` 产自 `6d0aa42`（2026-09-23 08:36）之前的修订 | HEAD 下 burst 必触发（`main.py:1447-1448,2046-2086`）；实测 `ctrl_y ∈ {70,50}`、`127` = 0/6000；`git log -S deadlock_burst_ready` 仅 1 次 | 无（多源一致） | 该 run 的墙钟 provenance 或 dashboard 运行日志 | §0.1（全局约束，不修则所有基于该 run 的归因无效） |
| **H2** | 报告 `anomaly_state="stuck_ramp"` 在 HEAD 上不可复现 | `memory.py:1369` 先于 `:1371`；`escape_behavior` 被伪影抬升（`memory.py:2183-2191`） | 需要 `exploration_mode` 的运行值 | 该 run 的 `exploration_mode` + `anomaly_state_history` | §6.2（终态判据的阈值标定） |
| **H3** | oscillating 检测在真实 run 中抖动 | 门限 `memory.py:1317` vs 实测周期 ≈0.37 s（t3 §1.2） | 需原始 `ctrl_x` 序列 | `/flow.json` 的 `ctrl_x` 原序列 + `anomaly_state_history` | §6.3（窗口自适应的系数 6） |
| **H1'** | 0.37 s 级转向变号的生成者是 R14/R16 转向疲劳/反驱动环路 | `model.py:345-392,1477-1520,2132-2166` 是唯一具备符号反转结构且量级主导（±0.18）的腿 | 也可能是别的竞争项 | 各驱动腿在真实 run 的分解 | §5.5（CX 突破的幅度调制权重） |
| **H4** | `forced_bold_explore` 可达性取决于"钳位后阈值（≤10）+ 单一异常标签稳定性"，**不判为结构不可达** | `memory.py:2094-2105`；`bold_explore_stuck_s` 活值 60 vs 注册 [1,10]（`active_strategy.json:5`） | t1 S24 的依据（`anomaly_duration=11.14 s`）不可复现 | 运行时读回钳位后的实际值 + 异常标签持续时长分布 | §7.5-d（本能边界）；本条**不作为**任何回退条件 |
| **H5** | 真实连接组运行点与 t1/t4 探针（`demo=True`）不同 | 本机无 `.cache/malecns/manifest.json`（t1 §8.7）；本次探针实测 `jump_pool_spike_rate_mean = 1.0`、`forward_rate_mean = 1.0`（发放退化） | 无 | 真实连接组 cache + 同一探针 | §5.1/§5.2 的全部数值（`0.18127`、5.517×、`fwd_aux_ceiling` 比例）**只能在真实连接组上确认阈值** |
| **H6** | M1 的断口在真实连接组上同样成立（跳池 < 0.04 而前向池 ≈ 0.043） | 轨迹反解（t3 §1.2）与代码结构（`model.py:1787` 无稳态 vs `1452-1475` 有稳态） | 无 | 真实连接组下跳池/前向池的发放率读数 | §5.2/§5.3 的必要性 |
| **H7** | CX 环路突破的"恒不可达"是**条件性**的（仅当目标向量在供时为真） | `central_complex.py:286-306` + t1 探针矩阵（弱目标/无向量时触发 3 次） | 无 | 真实 run 的 `goal_vectors` 日志 | §5.5（进展门替换有无门的必要性） |
| **H8** | auto-fix 熔断（连续 3 次失败 → `auto_fix=False`）**未**在本次日志中触发 | `evolution_skill.py:2740`；t2 §4-C6（140 行 errors 全为别的类型） | 熔断行无持久化 ⇒ 无法排除 | 熔断行的持久化与告警（§7.4） | §7.5-c（生命周期改造） |
| **H9** | 停摆窗口（2026-09-17→09-24）内**是否**发生过该故障无法判定 | t2 §10.2；仿真时间无墙钟换算 | 无 | 导出的运行日志原件 | 不影响 M4 判定（无论在哪，闭环都修不了它） |
| **H10** | `scripts/audit_contract_pairs.py` 的 "39 参数全 unreferenced" 是**静态扫描盲区**（对 `_expl.get("turn_bias")` 这类扁平化读取无效），而非"39 个都是死键" | t2 §4-C4:该工具报 39 行 `w=0 r=0 decl=0`；t2 §9.7 的整词核查给出"0 个零出现" | 两者都不足以证明接线 ⇒ 需要确定性判据 | §4.5 的运行时 A/B | §4.5（A/B 取代静态自证） |
| **H11** | 跳池的发放率在真实连接组上**可被 `escape.jump_leg_weight` 显著改变**（即 MBON 腿是有效注入腿） | `model.py:1787` 的注入点存在；本次探针证明算术可达（0.18127 阈值 vs 腿电流量级） | demo 探针不能证明真实连接组 | 真实连接组上的 A/B（§5.1 V4） | §5.1 的全部阈值 |
| **H12** | `gain("jump")` 的 `[0.5, 2.5]` 上限在**事件性动作**上过低（5× 动态范围不足） | 本次探针：`GAIN_MIN` 与 `GAIN_MAX` 相差 5×，而单神经元阈值需求 0.18127 与 `escape_current` 下限 0.05 的缺口为 0.13127 | 也可能 2.5 足够（若 MBON 腿本身够强） | 真实连接组上 `gain("jump")` 在 [0.5, 2.5] 两端下的跳池占用率 | §5.1 的 `JUMP_GAIN_MAX = 4.0`（**可撤回**：若 2.5 已足够则删除该项） |
| **H13** | 长窗 + 轨迹运动学的 fitness 在真实运行中**可分辨**（A/A 门可通过） | t2 §5 的 60.3% 零 delta 已被证明来自"读不存在的字段 + 120 s 瞬时窗 + 伪影输入" | 真实噪声可能仍淹没有效信号 | §7.2 的 A/A 门实测 | §7.2（若不过门，P2/P3 整体阻塞） |
| **H14** | 升级状态机的 `dwell_ticks`（初值 1500 tick）在真实运行中合适 | 无实测依据，仅为设计初值 | 可能过长（错过升级）或过短（抖动） | 复现场景下的 `ineffective_ticks` 分布 | §6.1 的唯一标定参数 |

---

## 14. 附录

### A. 本方案独立探针与产物

| 项 | 路径 | 说明 |
|---|---|---|
| 探针脚本（本次新增） | `.tmp/a4_plan_probe.py` | 只读；`FlyModel(demo=True)` 三场景 ×1200 tick + LIF 算术 |
| 探针产物（本次新增） | `.tmp/a4_plan_probe_out.json` | 结构化结果（见下） |
| 复现命令 | `cd D:\codes\flygym; $env:PYTHONIOENCODING="utf-8"; python .tmp/a4_plan_probe.py` | |

**探针关键输出（E-3，仅算术/接线可达性）**：

> **归属澄清（F11①，F2 相关）**：下表是**本方案探针的真实输出**（`.tmp/a4_plan_probe.py` → `.tmp/a4_plan_probe_out.json`），
> 但其中 `jump_pool_size = 20` 是**脚本里的字面量**，不是探针测出来的；`forward_pool_size = 60` 才是 `len(m.forward)` 的直接读取。
> **五个池大小由本机直接测量 + 由 t5 §1.3 独立复算确认为真**（jump 20 / forward 60 / turn_all 80 / recurrent 2400 / visual 1536, n=4096），
> 因此结论无害，但表述必须区分"探针实测"与"字面量/独立复算"，不能整组称为"探针实测映射"（已在 §5.1 同步修正）。
> 另：`C_mbon_leg_and_gain_chain` 的 0.07749 / 0.23247 / 0.38746 是**按 `gain / DEFAULT_GAINS["jump"]` 归一化**算出的
> （与 §5.1 F2 修正后的实现同式）；若实现时不归一化，标称值会变成 0.525 而非 0.35 —— 这正是 F2 要消除的不一致。

```
environment.dt = 0.02   tau_m = 0.10   threshold = 1.0
v_ss_per_unit_current = 5.517   ( = 1/(1-exp(-dt/tau_m)) )
jump_pool_size = 20 (脚本字面量；独立复算为真)   forward_pool_size = 60 (len(m.forward) 实测)
decode_gate = jump_rate > 0.04  (model.py:2478)
decode_gate_neuron_equivalent_in_13_tick_window = 0.8   ( = 0.04*20 )

A_scenarios (demo=True — 发放退化, 仅证明接线):
  calm   jump_pool_spike_rate_mean = 1.0  forward_rate_mean = 1.0  ctrl_jump_true = 25/1000
  stuck  jump_pool_spike_rate_mean = 1.0  forward_rate_mean = 1.0  ctrl_jump_true = 25/1000
  fallen jump_pool_spike_rate_mean = 1.0  forward_rate_mean = 1.0  ctrl_jump_true = 25/1000
  ⇒ demo 模式下运动池发放饱和为 100%: 该表**不能**代表真实连接组运行点

B_decode_gate_arithmetic:
  current_for_one_jump_neuron_to_reach_threshold = 0.18127
  observed_escape_current_floor                 = 0.05    (model.py:1796)
  escape_floor_v_ss                             = 0.2758  < 1.0  ⇒ 不够
  order_of_magnitude_current_for_4_of_20        = 0.7251

C_mbon_leg_and_gain_chain  (单位 = gain / DEFAULT_GAINS["jump"]，见上):
  mbon_gain_jump_constant = 0.35   (model.py:639,1787 — 增益盲；F2：作为"名义权重"直接乘原始 gain 会变 0.525)
  gain_chain: gain/nominal = 1/3  ⇒ leg 0.07749 ⇒ v_ss 0.4275 (不足)
              gain/nominal = 1    ⇒ leg 0.23247 ⇒ v_ss 1.2825 (可达单神经元阈值)
              gain/nominal = 5/3  ⇒ leg 0.38746 ⇒ v_ss 2.1375 (可达)
  gain_constants: DEFAULT_GAINS.jump = 1.5, GAIN_MIN = 0.5, GAIN_MAX = 2.5,
                  DOPAMINE_GAIN_THRESHOLD = 0.15, ACTIVITY_THRESHOLD = 0.05

D_proposed_homeostat_and_gate:
  forward_pool_homeostat_constants: tau 0.15 / ref 0.30 / full 0.60 / floor 0.25
  jump_pool_homeostat_constants_today: null
  tonic_current_needed_for_threshold = 0.18127  (= 0.906 x fwd_aux_ceiling 0.20)
```

> **诚实声明**：`mbon_leg_current_estimate`（0.23247）是用 demo 模型的 `|mbon[3]|` 均值 × 0.35 得到的**量级估计**，
> 不能用于真实连接组的定量结论（H5）。本方案引用它的唯一用途是**证明增益链的算术可达性**（GAIN_MIN 与 GAIN_MAX 之间存在跨越单神经元阈值的区间）。

### B. 一手证据位置索引

| 主张 | 一手证据（E-1 层，本机已核对） |
|---|---|
| `StuckDetector` 单位契约 | `fly64/fly64/memory.py:135,206-209,217,223` ← `fly64/fly64/main.py:2650`；同型自述 `main.py:765-785` |
| 泄放空操作（伪影第四段） | `fly64/fly64/memory.py:1985` vs `:1994-1995` |
| 伪影外溢 | `fly64/fly64/main.py:2687` → `model.py:2096`；`main.py:2056`；`memory.py:2186` |
| 三解码器决定行为 | `fly64/fly64/model.py:2282,2283,2478` |
| `raw_x` 饱和阈值 | `model.py:2283`（`abs(turn_rate) ≥ 0.0636` 即饱和）；`model.py:2473-2474`（clip） |
| jump 池唯一执行门与不应期 | `model.py:2478`（`> 0.04` 且 `now - last_jump >= 0.8`） |
| 增益唯一表达点 | `model.py:1837-1842`；`_pathway_idx_map[3]` = jump 神经元（本次实测 20 个） |
| MBON→jump 腿（增益盲） | `model.py:1787`；常量 `model.py:639`；`DEFAULT_GAINS` 在 `gain_modulation.py:39-45` |
| LIF 常数 | `model.py:403,404,405`；稳态推导 `v_ss = I/(1-e^{-dt/tau_m})` |
| 前向池稳态 | `model.py:1452-1475`（`forward_homeo_gain`）、`model.py:649-652`（常量）、`model.py:1882-1890`（固有兴奋性腿）、`model.py:696`（`fwd_aux_ceiling = 0.20`） |
| `escape_current` 下限 / `escape_jump_drive` | `model.py:1793-1796`；`model.py:1920-1922` |
| 两处死写入 | `main.py:1848-1851` ↔ `central_complex.py:192,198,297,314` |
| `_vote` 首命中即返回 | `memory.py:1361-1373`（`oscillating` :1367 先于 `stuck_ramp` :1371） |
| `_detect_wall_stuck` 自锁 | `memory.py:1319-1321` |
| `_detect_oscillating` 固定窗 | `memory.py:1281`（`maxlen`）、`memory.py:1289-1317`（`>= 3`） |
| `forced_bold_explore` | `memory.py:2088-2105`；`main.py:1102-1105`（钳位）；`active_strategy.json:5` |
| `bold_direction` 逐 tick 翻号 | `memory.py:1662-1674`；调用点 `main.py:2124-2125` |
| burst 前置与体 | `main.py:1447-1448,2046-2086`；注释自述 `main.py:2040-2054` |
| `_last_burst_tick` 空守卫 | `main.py:2062` |
| CPG 不可达 | `main.py:2438-2511,2521-2530`；`motor_primitives.py:62-123` |
| 参数热重载段 | `main.py:1678-1863`（含 `steering_gain`/`loop_break_stuck_s` 死写入、钳位回写、`param_history.jsonl`） |
| 闭环诊断-only | `main.py:1419-1425`（`EvolutionPipeline(auto_fix=False, window_seconds=120)`） |
| fitness 与试验窗 | `evolution_skill.py:1960-2193`（`fitness`/`fitness_components`）、`:2460`（`run_time = 120.0`）、`:2505`（`delta > 0.03`） |
| 基线漂移 / 回滚语义 | `evolution_skill.py:2238-2267`（`_inject`）、`:2490,2532`（`_inject({})` "resets to defaults only"） |
| 试验维度 | `evolution_skill.py:2325-2326`（`_subset_k = min(5, ndim)`） |
| `has_fix` 一次性 | `evolution_skill.py:1163-1164,2644` |
| 日志只记 finding id | `evolution_skill.py:2923-2929` |
| 漏斗 | `evolution_skill.py:270`（`compute_funnel`） |
| `_check()` 缺键静默 | `evolution_skill.py:1066-1087` |
| 熔断 | `evolution_skill.py:2740`（`auto_fix = False`） |
| 版本 | `main.py:49`（`BRAIN_VERSION="2.24.0"`）、`main.py:50`（`SKILL_VERSION="3.5.1"`）、`evolution_skill.py:42`（`"3.5.0"`） |
| registry | `brain_tunable_params.json`（39 参数；`gate_jump_threshold` :38-43；`navigation.steering_gain` :234-240；`navigation.loop_break_stuck_s` :241-247） |
| 活参数 | `active_strategy.json:5`（越界 `60.0`）、`:8`（3.082）、`:16`（`__generation=332`）、`:33-38`（navigation） |
| pattern 集 | `default_patterns.json:50`（`position_unchanged_30s`）；生产者仅 `evolution_skill.py:863,1009` |
| 本能库 | `fly64/skills/scene_strategy_bindings.json`（2 bucket、`improved=1`、`promoted=false`）；`fly64/fly64/instinct_bindings.py`（`PROMOTE_MIN_IMPROVED`、`SALIENT_PARAMS`、`record_outcome` 的 `return None`、晋升规则） |
| 钳位表 | `main.py:1102`（`CLAMP_BOUNDS`）、`main.py:1155`（`apply_strategy_clamps`） |
| CPG 门 | `main.py:2521`（`_lif_motion = (abs(control.x) > LIF_MOTION_MIN ...)`） |
| 教练直写控制 | `main.py:2330-2348`；`main.py:2279-2323`（对话）；`main.py:2358-2384`（护栏） |

### C. 复现命令

```powershell
# 基线
cd D:\codes\flygym; git rev-parse HEAD            # cca66648a204043d881da502cf996b15882ad289

# 本方案探针（只读）
$env:PYTHONIOENCODING="utf-8"; python .tmp/a4_plan_probe.py

# 闭环自检（当前红灯）
cd D:\codes\flygym\fly64; python -m skills.evolution_skill --history-check

# 漏斗（当前最后一节为 0）
cd D:\codes\flygym\fly64; python -m skills.evolution_skill --funnel

# Phase6 归因（当前 60.3% delta 恰为 0）
cd D:\codes\flygym; python fly64\scripts\measure_evolution_health.py --phase6 --p44

# 接线静态工具（**不扫注册表**；对 active_strategy.json 的 47 键报 38 条 unreferenced ⇒ 无效判据，F7）
python fly64\scripts\audit_contract_pairs.py

# 区间不变式自查（F1）：39 个注册 pid 的 default/min/max 与线上活值（本机已跑，见 §4.7）
$env:PYTHONIOENCODING="utf-8"; python -c "import json,pathlib as P; r=json.loads(P.Path('fly64/skills/brain_tunable_params.json').read_text(encoding='utf-8'))['params']; s=json.loads(P.Path('fly64/skills/active_strategy.json').read_text(encoding='utf-8')); [print(p, s.get(p.split('.')[0],{}).get(p.split('.')[1]), r[p]['min'], r[p]['max'], 'OUT' if not (r[p]['min']<=s.get(p.split('.')[0],{}).get(p.split('.')[1])<=r[p]['max']) else 'ok') for p in r]"

# 版本边界证据
git log -S 'deadlock_burst_ready' --format='%h %ad %s' --date=short -- fly64/fly64/main.py
git log -5 --format='%h %ad %s' --date=short -- fly64/skills/default_patterns.json
```

### D. 本方案对 12 项"必纳入约束"的落点对照（逐条回应任务书）

| 任务书项 | 落点 |
|---|---|
| (a) `StuckDetector` 单位对齐（P0） | §4 P0-a2 |
| (b) CX 环路突破可达化 | §5.5 |
| (c) 两处旋钮死写入 | §5.4 |
| (d) MBON→jump 纳入增益链 + `jump_rate` 门归一化 | §5.1 + §5.3 |
| (e) 死代码清理（`set_adaptive_lr` / `consolidate_anomaly_resolution` / `_last_burst_tick`） | §5.6 |
| (f) "已放弃终态"判据 | §6.2 + §7.5-b |
| (g) 接线判定改为运行时 A/B | §4.5 |
| (h) 闭环存活自检 + 漏斗告警 | §7.4 |
| (i) 日志记录观测值 | §7.3 |
| (j) 参数越界不再静默钳位 | **§4.7（P0-a8：上界 4.0 + 显式迁移 + `min<live<max` 硬断言，含 `default==max` 例外）+ §7.1 T1 的区间相交断言**；**迁移清单（F1 补全，与被 §7.1 点名的 `:5` 并列）**：<br>① `active_strategy.json:5` `exploration.bold_explore_stuck_s = 60.0` → **10.0**（注册 `[1,10]`，等价于运行期钳位后的行为）<br>② `active_strategy.json:8` `exploration.gate_jump_threshold = 3.082271242248696` → **0.75**（新比值语义；等效占用率 `0.75×0.043 = 0.032 ≤ 0.04`，见 §5.3 等效表；并须同批迁移 RULE-19 单位契约，见 §5.3 ⑦ / F13）<br>③ 复核 `exploration.turn_bias = 0.25`（钉在注册上界 0.25，属 `default==max` 例外，由 `clamp(live)==live` 兜底） |
| (k) pattern 条件键零生产者 | §7.5-a |
| (l) `has_fix()` 语义缺陷 | §7.5-c |
| (m) 不新增第 5 个 jump 门限 | §5.3（替换口径） |
| (n) oscillating 检测口径与周期同量级 | §6.3 |
| (o) 本能晋升休眠 + 边界 | §7.5-d |
| (p) CPG 结构性不可达 | §6.4 |

---

## 15. t5 验证发现与修复对照（F1–F12）

> **验证来源**: `docs/analysis/analysis-t5-adversarial-verification.md`（verdict = **needs_revision**；1 blocker + 1 high + 4 medium + 6 low）
> **返修人**: brain-architect · 任务 `t6` · attempt `c8eda485-bd26-497d-854c-61b92bb0eed1`
> **第三方复核（本次，独立于 t5/t6）**: 基于 HEAD `cca66648` 的逐行核对，新增 **F13–F15**（F13 = RULE-19 单位契约迁移漏列，**blocker 级**；F14 = `_vote`/`ArbitrationState` 接口语义欠定义；F15 = 三处 `file:line` 引用校正），见本表末三行；骨架与 F1–F12 未改动。
> **纪律**: 逐条给出"问题 → 修法（含取舍）→ 落点 → 状态"；**骨架与 t5 核验通过项未改动**（见文件头 t6 返修说明）。
> t5 §5 的证据边界（本机无 `memory.json`、无 `.cache`、66/68 未复现、`DiagnosisEngine` 回放未重跑）**原样继承**：
> 本节的复算只覆盖可读的代码/工件（`active_strategy.json`、`brain_tunable_params.json`、`fix_catalog.json`、
> `default_patterns.json`、`.tmp/fly64_trajectory.json`、`evolution_skill.py`、`fix_executor.py`），**不越界**。

| F | 严重度 | t5 指出的问题 | 修法（含取舍说明） | 落点 | 状态 |
|---|---|---|---|---|---|
| **F1** | **blocker** | §5.3/§7.1 写"线上 `3.082271242248696 ∈ [0.25, 3.0] ⇒ 参数文件无需迁移"是**算术错误**（3.082 > 3.0）；按 `min(3.0,·)` 会静默钳到 3.0，新比值语义下门严 2.5–3.3×，与目的相反且 V6 不可满足；§7.1 只对 `:5` 提了区间断言，`:8` 是漏列的同族反例 | **两项并用**：(a) 注册上界 3.0 → **4.0**；(b) 新增 **P0-a8 显式迁移**：`active_strategy.json:8` → **0.75**，与 `:5` 并列进 §14-D(j) 迁移清单；(c) 新增 **硬断言**：对 39 个 pid 断言 `clamp(live)==live`（主判据）+ `min<live<max`（t5 要求的形式），**断言失败即阻断 P1**；(d) §5.3 增加**等效换算表**、声明"目的是放宽"、V6 改写为可判定形式 `占空比 ∈ [0.1%, 5%]` + 基线 0.0%。<br>**取舍**：(a) 单独用只是"过渡期不被静默钳位"，不修正语义，故必须配 (b)；(b) 单独用则迁移前的重载会先把 3.082 钳到 3.0（仍收紧），故必须配 (a)。<br>**独立核查新增（t5 未覆盖）**：严格形式 `min<live<max` 对 `default==max` 的两个 pid（`exploration.turn_bias` 0.25/0.25、`exploration.bold_explore_stuck_s` 10.0/10.0）**恒不成立** ⇒ 断言必须写明该例外，否则 P1 永远无法上线。39/39 pid 的实测区间审计：当前只有 `:5`（越界）与 `turn_bias`（钉界）两个例外。 | **§4.7（新增）**、§5.3、§7.1 T1、§8 P0-a8、§10 V6/**V21（新增）**、§11 **R11（新增）**、§14-D(j)、§14-C | ✅ 已修 |
| **F2** | high | §5.1 称 `_jump_leg_weight = 0.35` "逐位相同 ⇒ 行为不变"，但 `get_gain('jump') = 1.5` ⇒ 新版 `0.35×1.5 = 0.525`，首 tick 跳腿驱动 **+50%**；方案自己的探针第 121 行已做 `g / DEFAULT_GAINS['jump']` 归一化 ⇒ 算术与拟写代码不一致 | **采用"实现内除以 nominal"**（t5 选项 2）：`mbon[3] * _jump_leg_weight * (_pathway_gains_np[3] / _jump_leg_nominal_gain)`，其中 `_jump_leg_nominal_gain = gain_modulation.DEFAULT_GAINS["jump"]`（`model.py:12` 的 import 需同步加入 `DEFAULT_GAINS`）。<br>**取舍**：两写法数学等价（`0.2333·g ≡ 0.35·(g/1.5)`）；选归一化可让参数语义与今天 `mbon_gain_jump = 0.35` 同名同义，**V4 的比例、§14-A 的增益链表、注册项 `{0.35, 0.10, 0.80}` 全部无需改动**；选"默认改 0.2333"要同步改三处且语义从"名义权重"变为"绝对权重"。代价只是一次标量除法 + 一个跨模块常量依赖。<br>**回归断言**：`_jump_leg_weight == 0.35` 且 `gain('jump') == 1.5` 时 `v[jump_nodes]` 增量与改动前**逐位相同**（float32 `array_equal`，非 approx）；该断言列为 V4① 必须先过，失败即回滚 §5.1 不进 A/B。 | §5.1（新增 **F2 修正行** + 数据流/需修改/精确算术/验证/回退五处同步）、§10 V4/V5、§14-A 的 `C_mbon_leg_and_gain_chain` 单位说明 | ✅ 已修 |
| **F3** | medium | T3 门禁可绕过：`_resolve_file` **优先**用模板 `directive['file']`，`fix_files` 仅作回退（`fix_executor.py:488-489,603-609`）；静态测试不能阻止运行时执行 | ① 门禁判据改为 `f.fix_files` **∪** `parse_fix_template(f.fix_template)` 的全部 `directive["file"]` 命中 `.py` ⇒ 拒绝执行；② 在**唯一写盘点** `FixExecutor.execute`（`fix_executor.py:438,469`）加**同一判据的运行时守卫**（未持批准令牌 ⇒ 返回 `manual_action_needed=True` 且零写盘）；③ 明确 V20 的静态断言是**第三道（防回归）**，不是门禁本身；④ 门禁与守卫必须调用**同一 helper**（`fix_guard.is_py_patch`），避免判据漂移；⑤ 处置 t5 §5.7 的 legacy 开放风险：旧副本是 `fly64/skills/evolution_agent.py`（t5 写的 `fly64/fly64/evolution_agent.py` **不存在**），它 `--auto-fix` 只打印模板（`:359-364`）、无启动引用 ⇒ **不是第三条执行路径**，但仍要求"`FixExecutor.execute` 是唯一允许写 `.py` 的函数"进断言 | §7.1 T3 实现要点（重写）、§10 V20 | ✅ 已修 |
| **F4** | medium | §6.4 未说明授予的 primitive 如何越过 `not _lif_motion`（`LIF_MOTION_MIN = 8`，观察点恒真）；若加 OR 支路即新增控制分支，违反 R1 | **权威谓词替换**（不追加 OR）：把"持有运动权威者"从隐含的 `not _lif_motion` 改为 §6.1 持有的 `authority ∈ {lif, primitive}`；`main.py:2521/2529` 改读 `authority`，原表达式**移动**进 `authority` 的判定；**执行落点不变** —— 仍由既有 `cpg_apply_phase(control, cpg_phase)`（`main.py:2530`）写控制量，**不新增任何 `control.*` 赋值位置**。增设静态断言：禁止在 `_lif_motion` 上追加 `or`，并断言新增 `control.` 赋值行数为 0。<br>**若实现时只能用 OR 支路 ⇒ 按 t5 要求直接判定本项不可行并从 P2 移除**（只保留"`primitive_granted_count` 恒 0"的观测与一条 `medium` finding），不做折中。 | §6.4（设计/需修改/验证/回退四处重写）、§5.5 冲突矩阵（`burst > primitive > lif`） | ✅ 已修 |
| **F5** | medium | A/A 门与 commit 阈值同为 0.03 ⇒ 构造性 5% 假阳性；n=20 估 P95 不可靠；后一条判据更弱永不会先失败；缺"噪声降不下来"的回退 | ① **脱钩 + 随噪声标定**：`threshold = max(0.03, k·P95_noise)`（k ≥ 2）；若改用显著性检验则**必须声明目标 FPR 与功效**；② 最小 **n ≥ 100 窗** + `P95` 的 bootstrap 95% 置信区间，判据用**置信上界**；原"≤10%"降为次要一致性检查（≤5%）；③ 双窗确认的联合 FPR **实测**（≥50 对 A/A 双窗得 `aa_two_window_fpr`，≤1% 才允许自动 commit），**不得按 0.05² 估计**；④ **回退**：窗口 ×2 后置信上界仍 > σ_floor ⇒ 该 fitness 维度标 `unmeasurable` 并**移出搜索空间**（逐维降级顺序：`meta_channel → learning_progress → coverage_gain → waste_penalty → loop_penalty → net_disp_rate`）；若轨迹运动学项也不可分辨 ⇒ 判 H13 不成立、P2/P3 阻塞 | §7.2（A/A 门段落重写 + 试验流程 + 验证表）、§10 V9/V11、§11 R6/**R12（新增）** | ✅ 已修 |
| **F6** | medium | §5.5 CX 突破与既有 deadlock burst（`stuck>60` 即触发、直接写 `control.x/y=127`）条件重叠，**V8 无法归因** | ① **互锁**：把已有信号 `burst_active` 作为 CX 突破的抑制前置（`breakout_ok AND NOT burst_active`），不新增 `control.*` 写入点、不新增门限；② **可分辨观测**：`cx_loop_break_count_burst_off` + `deadlock_burst_count`，并要求两者时间戳集合**不相交**；③ 把 §5.6 对 `main.py:2082` 的审查扩展为 **4 条冲突矩阵**（burst↔§5.3、burst↔§5.5、burst↔§6.4、§5.3↔§6.4），逐对裁决；④ V6 的占空比统计**排除 burst 窗口**；⑤ **若仍无法归因 ⇒ 按 t5 要求明确放弃归因**：V8 降为非归因观测，§5.5 判未通过，不得用 burst 的行为冒充 CX 的功劳 | §5.5（互锁/冲突矩阵/验证/回退）、§5.6（审查行）、§8 P1 判据②、§10 V6/V8、§11 R2 | ✅ 已修 |
| **F7** | low | §4.5 称 `audit_contract_pairs.py` "对 39 个参数全部报 unreferenced"，与工具真实行为不符（不扫注册表；对 `active_strategy.json` 47 键报 **38** 条） | 按工具真实行为复述：**不扫描注册表**，在 8 个工件中报 38 条 `unreferenced w=0 r=0 decl=0`（含 `gate_jump_threshold`、`navigation.*`），全仓合计 85 行、`TOTAL dead-writes + silent-defaults: 8`；**实质结论不变**（静态工具不能支撑 `wired: true`，只用运行时 A/B）。V3 与 §14-C 的措辞同步（"39 参数均只有注册表自称 `wired: true`"） | §4.5、§10 V3、§14-C | ✅ 已修 |
| **F8** | low | `has_fix()` "现关闭 13 个 pattern" 实为 **11** 个 | 改为 **11**，并写明口径：`fix_catalog.json` 19 条 fix、`reverted 8` ⇒ 未回滚 11 条，覆盖 **11 个 distinct `pattern_id`**；其中 **10 个**是 `default_patterns.json` 的 pattern，`telemetry_gap` 不是 pattern（诊断类）。两个数都写出以消除口径歧义 | §3（A 类清单）、§7.5-c | ✅ 已修 |
| **F9** | low | §5.4 要求给 `GoalComparator` 加 property，但该类**不存在** | 改名 **`MultiSourceGoalCompetition`**（`central_complex.py:178`；实例 `cx._goal_comp`，`:369`），并注明 property 必须落在该类命名空间（读取端 `:198` 的 `self.steering_gain`、`:297` 的 `getattr(self,'_loop_break_stuck_s',…)`） | §5.4 需修改② | ✅ 已修 |
| **F10** | low | §5.2 `jump_intrinsic_max` 三处取两个默认值（常量 0.25 vs 注册 0.15）；"0.13127 = 0.31·threshold" 量纲混写 | ① 常量默认统一为 **0.15**（与注册项、与"精确算术"段一致）；② 比值改写为 **"0.13 × threshold（1.0）" = "0.31 × GAIN_MIN 腿的 v_ss（0.4275）"** | §5.2 需修改①、§5.2 精确算术 | ✅ 已修 |
| **F11** | low | ① §5.1/§14-A 把 `jump_pool = 20` 等说成"探针实测"（该值是脚本字面量；五个数经 t5 独立复算为真）；② §2.5 的"无 CPG 的 ±60/±69 群"过强（实为 `-60/-69` 均 0、正侧 `60`×1、`69`×7）；③ §5.3 的 H6 派生句无行内标注 | ① 改为三分口径："字面量（`jump_pool`）/直接测量（`forward/turn/visual/recurrent`）/t5 §1.3 独立复算确认"；② 改为"**无 `-60/-69`**；正侧仅 `60`×1、`69`×7（8/6000），**不构成群**"，并同步修正 §9.1 P0.1 行内的同一措辞；③ 在 §5.3 该句补"（H6，需真实连接组确认）" | §5.1 作用脑机制、§14-A、§2.5、§9.1(P0.1)、§5.3 | ✅ 已修 |
| **F12** | low | ① §3 称 A 类"是 §4/§7 的 P0/P2 条目"，与本文件自身 §5.4/§5.6（P1）矛盾；② §7.5-f 要求 `owner="coach-direct"`，而 `param_history.jsonl` 的字段名是 **`source`** | ① 改为"**分属 §4（P0）、§5（P1）、§7（P2）**"并补一张 11 项 → 落点对照表；② 统一为 **`source`**（直写记 `source="coach-direct"`，安全通道 `"safety-guard"`），明确**不新增** `owner` 字段（`ParamAuthority` 内部 `owner` 仅作租约记账，落盘一律映射到 `source`，守 R3 单一口径） | §3、§7.5-f | ✅ 已修 |
| **F13** | **high** | §5.3 把 `exploration.gate_jump_threshold` 语义由 Hz 改为无量纲比值，但**未列入该 key 既有的 RULE-19 单位契约影响面**。实测：`fly64/tests/test_gate_units.py:178-226` 硬断言该 pid 的 `description` 含 `"Hz"`(:182)、含 `"RULE-19"`(:183)、含 `"ÿ-tick"`/`"1/dt"`/`"telemetry.py"`(:195-197)，且 `default > 2.0 Hz`(:223)、`min >= 2.0 Hz`(:225)、`max <= NYQUIST`(:226)；`fly64/contract_registry.json:83,98,102,183` 将其登记进 `rate_gate_group` 并声明 `threshold_unit="Hz"`；`main.py:777-783` 有配套 RULE-19 契约注释、`:2894` 读参数、`:2953-2957` 以 Hz-vs-Hz 计算并发布布尔 `gate_jump`（消费方 `plugin/scene_context.py:233-234`）。按现文实施，**至少 4 条 PIN 断言必然转红**。 | **两项并用**：(a) 把受影响文件补进 §5.3 影响面（见 §5.3 ⑦）；(b) 给出 RULE-19 契约的迁移形态——`gate_jump_threshold` 由 Hz 门迁移为 ratio 门，但**保留 RULE-19 的精神（单一单位、只换算一次）**：`test_gate_units.py` 改写为 pinned ratio 契约（`description` 须含 `"ratio"`、点名分母下限 `FWD_RATIO_FLOOR = 0.008` 与 `model.py:2282`、`default>0`、`min>0`），`contract_registry.json:102` 的 `threshold_unit` 改 `"ratio (dimensionless)"`，`main.py:2891-2894` 默认值 `8.0 → 0.75`。**取舍**：**不采用**「新增第 5 个 key」（违反 R3），只能「替换 + 同步迁移契约」，代价是必须动测试与注册登记表（原稿漏列）；pinned 力度不得下调，只把被 pin 的物理量由 Hz 换成 ratio。 | §5.3 需修改/新增⑦、§10 **V22（新增）**、§11 **R13（新增）**、§14-D(j) | ✅ 已修 |
| **F14** | medium | §6.1③ 要求「不改 `_vote` 优先顺序」，又要求 `ArbitrationState`「持有本次允许的类别集合、在同一严重度层内引入竞争力」；但实测 `_vote`（`memory.py:1347-1373`）是**扁平首命中**（`fallen :1362 → micro_loop :1364 → oscillating :1367 → wall_stuck :1369 → stuck_ramp :1371 → idle :1373`，逐行核对一致），**无「严重度层」结构**。接口语义未定义 ⇒ 该阶段最大返工点。 | **定义单一、纯函数式接口（无副作用、默认零行为变化）**：① 新增 `_vote_all(...) -> list[str]`（全部命中、按现有顺序、不短路）；② `_vote(...)` 改为「首个满足 `allowed` 的命中，否则 `IDLE`」，新增可选参数 `allowed`（类型 `set[str]`，默认 `None`）；③ **不变式（PIN）**：`allowed is None` 时 `_vote` 输出与改动前逐 tick 相同；④ `ArbitrationState` 只消费 `_vote_all` 输出（同层多命中按成效分选）并写回 `allowed`。**取舍**：把「竞争力」落在**类别选择**层而非「改变优先级」层，避免触碰 `_vote` 的严重度语义；代价是多跑若干纯计算检测器，可忽略。 | §6.1.1（新增）、§10 V13 追加判据 | ✅ 已修 |
| **F15** | low | 三处 `file:line` 引用与实测不符（均轻微）：**D1** §2.3 表把 `gate_jump_threshold` 消费者记为 `plugin/scene_context.py:234`——实际该行消费布尔 `gate_jump`；阈值本身在 `main.py:2894` 被读、`:2954` 以 `gate_jump_threshold_hz` 发布。**D2** §5.3⑤ 写「`main.py:3064` 改读同一比值」——`:3064` 是 per-tick 解码镜像 `jump_not_active`；Hz 镜像在 `:2894`/`:2954`/`:2956-2957`。**D3** §7.1 新测试写 `tests/…`——真实测试目录是 `fly64/tests/`（顶层 `tests/` 为空）。 | 逐处改正引用（§2.3 表 / §5.3⑤ / §7.1 T3 及 §10 V20）；**不改任何结论**（「该参数不决定行为」仍成立）。 | §2.3、§5.3⑤、§7.1、§10 V20 | ✅ 已修 |

**返修后的自我核验（可复现命令见 §14-C）**：

1. **F1**：`3.082271242248696 > 3.0`（本机读出 `active_strategy.json:8` 原文）⇒ 原句为算术错误，已删并替换为等效换算表；
   等效性数字由 `0.04 / max(forward_rate, 0.008)` 与 `r·forward_rate` 直算（0.008→5.00 / 0.033→1.21 / 0.043→0.93；0.75 对应 0.0060 / 0.0248 / 0.0323）；
   34 位精度下 3.082 在 0.033/0.043 两处给出 0.1017/0.1325 ⇒ **2.54× / 3.31× 收紧**。
2. **F2**：`DEFAULT_GAINS["jump"] = 1.5`（`gain_modulation.py:39-45`）⇒ 未归一化时 `0.35×1.5 = 0.525`，与"逐位相同"矛盾；已改为归一化写法 + 位精确断言。
3. **F3**：`fix_executor.py:488-489` 与 `:603-609` 的两行即为"模板优先"的确证；legacy 路径纠正为 `fly64/skills/evolution_agent.py`。
4. **F7/F8**：工具行为与 fix 目录计数均由本机独立复算（38 / 85 / 8；19 fixes / reverted 8 / 未回滚 11 / distinct `pattern_id` 11）。
5. **F11②**：`.tmp/fly64_trajectory.json` 复算 `ctrl_x`：`-60`=0、`-69`=0、`60`=1、`69`=7；`ctrl_y` ∈ {70: 5519, 50: 481}；`jump=true` 0/6000。
6. **区间审计**：39 个注册 pid 全部能取到活值，其中越界/钉界者仅 2 个（`bold_explore_stuck_s` 越界、`turn_bias` 钉上界）。

**未修 / 明确不修（说明理由，防止误读为遗漏）**：

- **t5 §5.7 的 legacy 双写风险**：结论是"不是第三条执行路径"（证据：`evolution_agent.py:359-364` 只打印模板、全仓无启动引用），
  故不引入新门禁，只把"唯一写盘点"写进断言。若将来该文件被重新启用，必须经同一 helper。
- **t5 §5.3/§5.4（`66/68`、`DiagnosisEngine` 回放）**：属证据边界，本机无对应数据/环境，**不越界断言**，也不据此修文。
- **t5 §6 的 F1–F12 之外**：本轮只返修 t5 列出的 12 项；未新增设计条目（骨架冻结）。

---

> **结语**：Fly64 需要的不是"在卡死时补一个 jump"，而是**让脑自己拥有一个能到达行为的调节面、
> 一套能换招的仲裁、一份能读完就判定的适应度、以及一条能复盘的责任链**。
> 本方案的 P0 阶段刻意不改变任何行为 —— 因为在一个"读不出自己有没有变好"的系统里，
> 任何行为改动都无法被证明是改进。**先让自己看得见，再让自己学得动。**
>
> *撰人: solution-designer · 团队 `fly64-autonomy-evolution` · 任务 `t4` · attempt `46b5414e-6d4c-44d9-b4f0-84199452de32`*
> *t6 返修: brain-architect · attempt `c8eda485-bd26-497d-854c-61b92bb0eed1` · 依 t5 verdict=needs_revision 修 F1–F12（对照见 §15）*
> *证据形态: §0 分级；§14-B 全部 `文件:行号` 均经本机逐一核对；§14-A 为本次独立探针的真实输出（归属已在 F11 澄清）。*
