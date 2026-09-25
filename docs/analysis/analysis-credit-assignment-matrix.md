# P0-1 信用分配通路审计：变量×自适应面矩阵

> **任务**: t1 [P0-1-matrix] · **作者**: audit-engineer · **attempt_id**: 34c63b8f-f8fe-4bb2-a8fa-9547e9e58b14
> **依据**: `docs/analysis/session_logs_analysis_v5.md` §4.3 · 并行审计 `analysis-t3-primary-factor-determination.md` M1
> **性质**: 只读审计。除本交付文档与 `.tmp/` 下三个复现脚本外，未修改任何仓库文件。
> **可复现**: `.tmp/audit_matrix_extract_writes.py`（AST 提取）、`.tmp/audit_matrix_repro_clamp.py`（钳位复现）、`.tmp/audit_matrix_verify_deadwrites.py`（死写验证）

---

## 0. 摘要（TL;DR）

**M1 的"决定行为的变量与所有自适应面不重叠"在 HEAD（BRAIN 2.24.0 / SKILL 3.5.1）上已被部分修复，但断口并未消除，只是从"接线不存在"迁移为"接线存在但信号被钳位 / 被稳态钉死 / 量级不足 / 或写了无人读"。**

三类断口的精确落点：

| # | 断口 | 性质 | 影响面 |
|---|------|------|--------|
| B1 | 解码器本身是**硬编码饱和非线性**（`raw_x=turn_rate·1100`、`raw_y=(forward_rate−0.008)·2000`、`jump=ratio>r`），三个系数 1100/2000/0.008 编译期常量、无注册项 | ❌ 最深层 | 三个行为变量 |
| B2 | `escape.fallen_jump_boost` 是**死写**：写进 `model._fallen_jump_boost` 但 model.py 无任何消费（注入跳池用的是 `_escape_jump_drive`） | ❌ 新增发现 | 坠落跳增强 |
| B3 | 教练 `turn_bias`/`bold_explore_stuck_s` 被 R31-fix12 **钳位 + 自愈回写抹掉原值**（0.8→0.25、20→10） | ⚠️ 已复现 | 教练建议 |
| B4 | `exploration.gate_forward_threshold` 只进遥测（`flow.json`），**无执行侧消费者**（前向解码 `raw_y` 无门控） | ⚠️ | 前进门限 |
| B5 | 前向池被占有率稳态 `forward_homeo_gain` 钉在满速（`fwd_homeo_floor=0.25`、聚合封顶），自适应信号拉不下饱和 | ⚠️ 半通 | forward_rate |
| B6 | 转向主导腿量级差 10 倍：`cx_steering_gain_turn=0.12` vs 转向竞争主导项 ±0.18，导航/学习信号到达但打不破平局 | ⚠️ 半通 | turn_rate |

**同时确认 M1 点名的 6 处作用点缺失中，已有 4 处在 HEAD 被修复**（`navigation.steering_gain`/`loop_break_stuck_s` 死写已改到 `_goal_comp`；`jump_leg_weight` 已替换固定 0.35；`gate_jump_threshold` 已接管 jump 解码；`set_adaptive_lr` 已按 P1-b6-1 删除）。详见 §7。

---

## 1. 方法

1. **AST 提取**：用 `ast` 遍历 `fly64/fly64/main.py`，收集所有对 `model.*` / `memory_ctrl.*` / `control.*` 的属性写（Assign / AugAssign / AnnAssign / For / With / setattr），得到 **134 个写点**。
2. **反查写入者来源**：对每个写点回看右值来源——默认值字面量 / 注册表参数（`skills/brain_tunable_params.json`）/ 教练 strategy（`active_strategy.json` 热加载）/ EVO `_inject`（写 `active_strategy.json`）/ 硬编码常量。
3. **分类**：✅ 有自适应写入者且下游可达 / ❌ 只被硬编码写入或写后无人读（断路）/ ⚠️ 被写入但下游被钳位、被稳态覆盖、或量级不足以改变行为（半通）。
4. **交叉校验**：逐一把 39 个注册表参数与它们的 `main.py` 写入点 + `model.py`/`memory.py` 消费点对齐，确认无遗漏。

> 证据纪律：本机无 `.cache/malecns/manifest.json`（真实连接组不可离线复现），故凡涉及"量级/饱和"的结论以**静态代码可达性**为准，并沿用 t3 的 H 系列待验证假设口径；不把假设写成断言。

---

## 2. 决定行为的变量全集

### 2.1 最终执行变量（唯一发布点）

`bridge.write_control(control.x, control.y, control.jump, b, z)` —— `main.py:2699`。
这三个量是行为的地面真值。它们的**写入者是最后一个胜出者**（last-writer-wins），`main.py` 中有约 20 处硬编码分支会覆写 `model.step()` 的输出：

| 写入分支 | 位置 | 写 x/y/jump |
|---|---|---|
| `model.step()` 返回 | `main.py:1640` | ✅（网络解码，唯一携带自适应面的写者） |
| 悬崖反射 | `main.py:2060-2061` | ✅ |
| 异常反射 | `main.py:2141-2143` | ✅ |
| 死锁爆发 burst | `main.py:2190-2194` | ✅（`y=127`、占空比 200/500） |
| 对话 override | `main.py:2406-2416` | ✅ |
| 教练 `command` 直控 | `main.py:2466-2468` | ✅ |
| 地下自愈 | `main.py:2489-2493, 2502-2504` | ✅ |
| 动作熵 t28 | `main.py:760-761` | ✅ |
| CPG 原语 | `main.py:2650`（`cpg_apply_phase`） | ✅ |

> 结构性要点：**决定行为的 `control.x/y/jump` 是约 20 个硬编码分支 + 1 个网络解码分支的"竞争写"结果**。自适应面只能影响其中 `model.step()` 这一个写者的输入，其余分支全是硬编码。

### 2.2 解码器（M1 的"决定行为的三解码器"，HEAD 行号）

| 解码量 | 表达式 | 位置 |
|---|---|---|
| forward_rate | LIF 前向池 13-tick 均值 | `model.py:2339` |
| turn_rate | `right_rate − left_rate` | `model.py:2353` |
| jump_rate | LIF 跳池 13-tick 均值 | `model.py:2339` |
| **raw_y** | `np.clip((forward_rate − 0.008) * 2000.0, 0, 70)` | `model.py:2366` |
| **raw_x** | `np.clip(turn_rate * 1100.0, −70, 70)` | `model.py:2367` |
| **jump** | `(jump_rate / max(forward_rate, FWD_RATIO_FLOOR)) > _jump_rate_ratio_gate and cooldown` | `model.py:2564-2566` |
| 发布 | `Control(int(filtered_x)…, int(filtered_y)…, jump, …)` | `model.py:2577-2579` |

> 行号与 M1/t3 报告（`model.py:2282-2283 / 2478`）有漂移：HEAD 上为 `2366-2367 / 2564`（P1-b3 已把 jump 从 `jump_rate>0.04` 改为比值门控）。

---

## 3. 五个自适应面

| 面 | 机制 | 写点 | 作用对象 |
|---|---|---|---|
| **学习** | 蘑菇体 MBON（`mbon[0..3]` → 前向/左转/右转/跳池） | `model.py:1842-1889` | 四个运动池电流 |
| **增益** | 多巴胺三因子增益（visual/forward/turn/jump/recurrent 五通路） | `model.py:1898-1908`、`gain_modulation.py` | 突触电流 × 通路增益 |
| **参数** | 注册表 39 项（`brain_tunable_params.json`，全 `wired=true`） | `main.py:1833-1966` 热加载 | `model._*` / `memory_ctrl.*` |
| **教练** | `active_strategy.json`（turn_bias/bold/command/dopamine） | `main.py:1833-2045` | 同上 + `control.*` 直控 |
| **EVO fix** | `_inject`（写 39 参数进 strategy）+ `fix_executor`（fix_template 补丁） | `evolution_skill.py:3533`、`fix_executor` | strategy / 源码文件 |

---

## 4. 核心矩阵：三解码器 × 五自适应面

> 判定对象是"该面能否**改变**该解码器的输出"。✅=可达且有效；⚠️=可达但被钳/钉/量级不足；❌=不可达或写后无人读。

| 解码器 | 学习(MBON) | 增益(gain) | 参数(39) | 教练(coach) | EVO fix |
|---|---|---|---|---|---|
| **forward_rate → raw_y** | ✅ `mbon[0]` `model.py:1845` | ✅ forward 通路 `model.py:1904` | ✅ `breakout_forward_bias`/`forward_accum_*`/`fallen_forward` | ⚠️ 无直接前向键 | ✅ 经 strategy |
| | ⚠️ 被 `forward_homeo_gain` 稳态 + 聚合封顶钉在满速（§7-B5） | ⚠️ 只缩放 MBON 腿，拉不下饱和 | ⚠️ `gate_forward_threshold` 只进遥测（§7-B4） | | |
| **turn_rate → raw_x** | ✅ `mbon[1]/[2]` `model.py:1847-1848` | ✅ turn 通路 `model.py:1905` | ✅ `turn_bias`/`bold_turn_drive`/`commit_*` | ⚠️ turn_bias 被钳 0.8→0.25（§7-B3） | ✅ 经 strategy |
| | ⚠️ 主导腿量级差 10 倍，信号打不破平局（§7-B6） | ⚠️ 同上 | ⚠️ steering_gain 已修复但 `cx_steering_gain_turn=0.12` 仍小 | | |
| **jump_rate → jump** | ✅ `mbon[3]` × `_jump_leg_weight`（已修复） `model.py:1850-1851` | ✅ jump 通路 `model.py:1906` + jump 腿增益 | ✅ `gate_jump_threshold`/`escape_jump_drive`/`jump_intrinsic_max` | ✅ `command.jump` 直控 | ✅ 经 strategy |
| | ✅ jump 稳态 `jump_homeostat` 已补（P1-b2） | ✅ | ❌ `fallen_jump_boost` 死写（§7-B2） | | |

**矩阵结论**：三个解码器现在**都**有自适应写入者（M1 的"不重叠"字面表述已不成立），但 forward/turn 两条腿的写入者被**稳态钉死 / 量级不足**，jump 腿有一条**死写**。断口已从"接线不存在"升级为"接线存在但到不了行为"。

---

## 5. 完整变量清单分类（model.* / memory_ctrl.* / control.*）

> 完整 134 写点见 `python .tmp/audit_matrix_extract_writes.py` 输出。下表按"是否行为相关"与"写入者来源"归类，标出所有 ❌/⚠️。

### 5.1 control.*（最终执行，全部为硬编码写者 + 1 网络解码写者）

| 字段 | 写入者来源 | 判定 |
|---|---|---|
| `control.x` / `control.y` / `control.jump` | `model.step()`（网络解码）+ ~20 硬编码分支 | ⚠️ 网络解码是唯一自适应写者，其余分支硬编码 |
| `control.forward_rate/turn_rate/jump_rate` | `model.step()` 返回（只读遥测） | ✅（承载解码量） |
| `control.b` / `control.z` / `control._cmd_*` / `_below_ground_*` | 硬编码（对话/地下） | ❌ 硬编码（非自适应面对象） |

### 5.2 model.*（参数面写入点 + 网络内部状态）

| 字段 | 写入者来源 | 判定 | 消费点 |
|---|---|---|---|
| `model.strategy_turn_bias` | 教练/参数（`turn_bias`） | ⚠️ 被钳位（§7-B3） | `model.py:1983-1988` → turn 池 |
| `model.bold_turn_drive` | 参数（`escape.bold_turn_drive` × `bold_turn_bias`） | ⚠️ 幅度受钳位后 `bold_turn_bias` 影响 | `model.py:2006-2011` → turn 池 |
| `model.escape_jump_drive` | 参数（`escape.escape_jump_drive`） | ✅ | `model.py:1992-1994` → 跳池 |
| `model._escape_commit_ticks` / `_escape_forward_accum` / `_commit_reinforce` / `_commit_suppress` / `_forward_accum_step` / `_max_escape_forward` | 参数 | ✅ | `model.py:2015-2065` → turn/forward 池 |
| `model._fallen_forward` | 参数（`escape.fallen_forward`） | ✅ | `model.py:2005` → forward 池 |
| **`model._fallen_jump_boost`** | 参数（`escape.fallen_jump_boost`） | ❌ **死写**（§7-B2） | **无消费** |
| `model._jump_leg_weight` / `_jump_rate_ratio_gate` / `_jump_intrinsic_max` | 参数 | ✅（P1-b1/b2/b3 修复） | `model.py:1850-1851`/`2565`/`1961` |
| `model._coach_reward_gain` / `_dan_*` / `_dopamine_revisit_cost` / `_revisit_punish_threshold` / `_visual_novelty_boost` | 参数（coach.*/exploration.*/memory.*） | ✅ | `model.py:1690-1783` → 多巴胺/学习 |
| `model.mushroom.learning_rate` / `dopamine_threshold` | 参数（coach.mb_*） | ✅ | `mushroom_body.py` |
| `model.cx._goal_comp.steering_gain` / `_loop_break_stuck_s` | 参数（navigation.*） | ✅（A3 死写已修） | `central_complex.py:399`/`376` |
| `model.coach_turn_bias` / `coach_forward_bias` / `coach_timer` / `coach_active` | 教练 `command` | ✅（直控） | `model.py` coach 通道 |
| `model._coach_dopamine_bias` | 教练 `dopamine.bias` | ✅ | `model.py:1798` |
| `model.reflex_turn/forward/jump` | 反射桥（`memory_ctrl.reflex`） | ⚠️ 反射自身是硬编码仲裁（M2），非学习面 | `model.py:2067-2094` |
| `model.stuck_duration` | 检测层（`memory_ctrl.stuck_duration`） | ⚠️ 伪影外溢（M3，t3 §1.3） | `model.py:2277` 等 |
| `model.burst_active` / `cliff_tangent_bias` / `terrain` 等 | 内部状态镜像 | ✅ 遥测/内部 | — |

### 5.3 memory_ctrl.*（检测/仲裁/导航状态）

| 字段 | 写入者来源 | 判定 | 消费点 |
|---|---|---|---|
| `memory_ctrl.bold_turn_bias` | 教练/参数（`turn_bias`，**已钳**） | ⚠️ 被钳位（§7-B3） | `main.py:2242-2245` → `model.bold_turn_drive` |
| `memory_ctrl.bold_explore_stuck_s` | 教练/参数（**已钳**） | ⚠️ 被钳位（§7-B3） | `memory.py:2406` 强制突围门限 |
| `memory_ctrl.navigation_danger_weight` / `frontier_weight` / `repulsion_weight` | 参数（navigation.*） | ✅ | `memory.py:2919-2938` → CX 目标向量 |
| `memory_ctrl._revisit_penalty_scale` / `spatial.recency_decay` / `_failure_radius_cells` | 参数（exploration.*/memory.*） | ✅ | `memory.py:2657`/`437`/`2919` |
| `memory_ctrl.reflex.cooldown_duration` / `_adaptive_cooldown_scale` | 参数（reflex.*/stuck_ramp_cooldown） | ✅ | `memory.py:1955` 反射冷却 |
| `memory_ctrl.escape_stuck_threshold_s` | 教练/参数（escape.*） | ✅ | `memory.py:2437` |
| `memory_ctrl.escape_behavior` / `reflex_*` / `disp_60s` / `median_speed` / `waste_ratio` / `stuck_duration` | 检测层（硬编码 + 伪影） | ⚠️ 观测口径（M3） | 仲裁/遥测 |

---

## 6. 39 参数交叉校验（无遗漏）

> 39 项全部 `wired=true`。下表每项给出"注册 pid → main.py 写入点 → 下游消费点 → 判定"。✅=真正可达行为；⚠️/❌ 见 §7。

| # | pid | 写入点 (main.py) | 消费点 | 判定 |
|---|---|---|---|---|
| 1 | exploration.turn_bias | 1835-1836 / 1996-1997 | `model.py:1983-1988`、`main.py:2242-2245`→`model.py:2006-2011` | ⚠️ 钳位 |
| 2 | exploration.bold_explore_stuck_s | 1833-1834 | `memory.py:2406` | ⚠️ 钳位 |
| 3 | exploration.revisit_penalty_scale | 1860-1861 | `memory.py:2657` | ✅ |
| 4 | exploration.gate_forward_threshold | 3053-3054 | `main.py:3130`（仅遥测） | ⚠️ 无执行消费者 |
| 5 | exploration.gate_jump_threshold | 1872-1873 | `model.py:2565`（jump 解码） | ✅ P1-b3 |
| 6 | exploration.cliff_tangent_gain | 1857-1858 / 2834-2836 | `model.py:2258-2263` → turn 池 | ✅ |
| 7 | exploration.loop_breakout_threshold | 2172-2173 | `deadlock_burst_ready`（burst 前置） | ✅ |
| 8 | exploration.stuck_ramp_cooldown | 1876-1877 / 1905-1908 | 反射冷却 | ✅ |
| 9 | exploration.visual_gain_novelty_boost | 1863-1864 | `model.py:1745` | ✅ |
| 10 | exploration.dopamine_revisit_cost | 1866-1867 | `model.py:1717` | ✅ |
| 11 | exploration.breakout_forward_bias | 1886-1887 | `model.py:2050` | ✅ |
| 12 | escape.commit_ticks | 2001-2002 | `model.py:2019` | ✅ |
| 13 | escape.forward_accum_max | 2003-2004 | `model.py:2049-2061` | ✅ |
| 14 | escape.forward_accum_step | 1889-1890 | `model.py:2051-2060` | ✅ |
| 15 | escape.commit_reinforce | 1891-1892 | `model.py:2023` | ✅ |
| 16 | escape.commit_suppress | 1893-1894 | `model.py:2024` | ✅ |
| 17 | escape.fallen_forward | 2005-2006 | `model.py:2005` | ✅ |
| 18 | **escape.fallen_jump_boost** | 2007-2008 | **无** | ❌ 死写 |
| 19 | escape.fallen_switch_s | 2015-2016 | `main.py:2606-2610`（CPG fallen toggle） | ✅ |
| 20 | reflex.cooldown_min | 1905-1908 | 反射冷却下限 | ✅ |
| 21 | reflex.adaptive_cooldown_scale | 1897-1898 | `memory.py:1955` | ✅ |
| 22 | navigation.danger_weight | 1911-1912 | `memory.py:2922` | ✅ |
| 23 | navigation.frontier_weight | 1913-1914 | `memory.py:2926/2932` | ✅ |
| 24 | coach.reward_gain | 1925-1926 | `model.py:1783` | ✅ |
| 25 | coach.dan_punish_stuck | 1927-1928 | `model.py:1690` | ✅ |
| 26 | coach.dan_punish_loop | 1929-1930 | `model.py:1727` | ✅ |
| 27 | coach.dan_reward_exploration | 1932-1933 | `model.py:1695` | ✅ |
| 28 | coach.dan_reward_progress | 1934-1935 | `model.py:1695` | ✅ |
| 29 | coach.dan_punish_fallen | 1936-1937 | `model.py:1709` | ✅ |
| 30 | coach.dan_punish_cliff | 1938-1939 | `model.py:1709` | ✅ |
| 31 | coach.mb_learning_rate | 1940-1941 | `mushroom_body` 学习率 | ✅ |
| 32 | coach.mb_dopamine_threshold | 1942-1943 | `mushroom_body` 门限 | ✅ |
| 33 | navigation.steering_gain | 1948-1949 | `central_complex.py:399` | ✅ A3 已修 |
| 34 | navigation.loop_break_stuck_s | 1950-1951 | `central_complex.py:376` | ✅ A3 已修 |
| 35 | escape.escape_jump_drive | 1952-1953 | `model.py:1992-1994` | ✅ |
| 36 | escape.bold_turn_drive | 1954-1955 | `model.py:2006-2011` | ✅ |
| 37 | memory.recency_decay | 1961-1962 | `memory.py:437` | ✅ |
| 38 | memory.failure_radius_cells | 1963-1964 | `memory.py:2919` | ✅ |
| 39 | memory.revisit_punish_threshold | 1965-1966 | `model.py:1715` | ✅ |

**交叉校验结论**：39 项中 **34 ✅ / 3 ⚠️ / 1 ❌ / 1 ⚠️（gate_forward 无执行消费者）**。无遗漏，无"注册了但 main.py 未读"的项（`wired=true` 的"读点存在"契约成立），但存在 1 项"读了却写入无人读的字段"（`fallen_jump_boost`）—— 这是 `wired` 契约的**盲区**：它只校验"读点存在"，不校验"读点写出的值有下游消费者"。

---

## 7. 断路清单（❌/⚠️）附 file:line 与验证命令

### B1 ❌ 解码器硬编码饱和非线性（最深层，M1 结构本体）

- `raw_y = np.clip((forward_rate - 0.008) * 2000.0, 0, 70)` —— `model.py:2366`
- `raw_x = np.clip(turn_rate * 1100.0, -70, 70)` —— `model.py:2367`
- `FWD_RATIO_FLOOR = 0.008` —— `model.py:18`
- 系数 `2000 / 1100 / 0.008` 均为编译期常量，**无注册表项、无任何自适应面可写**。

**后果**：`|turn_rate| ≥ 0.0636` 即把 `raw_x` 打满 ±70（t3 §2.1-#1），净输入近零的转向竞争被放大成正负满量程。自适应面只能改变 `turn_rate`（输入），改不动解码非线性本身 → 输入小幅变化时输出仍饱和 → "改了很多但马里奥还是转圈"。

**验证**：
```powershell
python -c "import ast; s=open('fly64/fly64/model.py',encoding='utf-8').read(); t=ast.parse(s); [print(n.lineno, ast.get_source_segment(s,n)) for n in ast.walk(t) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in ('FWD_RATIO_FLOOR',) for x in n.targets)]"
# 确认 1100/2000/0.008 无任何 getattr(..., default) 形式，均为字面量
```

### B2 ❌ `escape.fallen_jump_boost` 死写（新增独立发现）

- 写入点：`main.py:2007-2008` → `model._fallen_jump_boost = float(_esc.get("fallen_jump_boost", 0.60))`
- `model.py` 中 `_fallen_jump_boost` 仅 1 处出现且是 `__init__` 默认赋值 `model.py:810`，**无任何读点注入跳池**。
- 真正的坠落跳注入在 `model.py:1992-1994` 用的是 `_escape_jump_drive`（pid `escape.escape_jump_drive`），与 `fallen_jump_boost` 无关。

**验证**：
```powershell
grep -rn "_fallen_jump_boost" fly64/fly64/
# → main.py:1350（遥测读回）、main.py:2007（写）、model.py:810（默认赋值，无消费）
python .tmp/audit_matrix_verify_deadwrites.py
```

### B3 ⚠️ 教练 turn_bias / bold_explore_stuck_s 被钳位 + 自愈回写抹掉（已复现，captain 实测同源）

- 钳位表 `CLAMP_BOUNDS`：`main.py:1172-1175`（`turn_bias → [0.0, 0.25]`、`bold_explore_stuck_s → [1.0, 10.0]`）
- 钳位函数 `apply_strategy_clamps`：`main.py:1225-1272`
- 消费点（用钳后值）：`main.py:1833-1836`
- 自愈回写（把钳后值写回文件，教练原值被永久抹掉）：`main.py:1852-1858`

**验证（方法自证，见 §9）**：
```powershell
python .tmp/audit_matrix_repro_clamp.py
# → turn_bias 0.8→0.25、bold 20.0→10.0、source=coach；self-heal 回写后原值不可恢复
```

### B4 ⚠️ `exploration.gate_forward_threshold` 只进遥测、无执行侧消费者

- 唯一消费：`main.py:3130` `"gate_forward": gate_open_hz(_forward_rate_hz, _gate_forward_hz)` —— 只写入 `flow.json` 遥测。
- 前向解码 `raw_y`（`model.py:2366`）**没有任何门控**，`gate_forward` 的布尔结果从不参与 `control.y` 的生成。
- 对比：`gate_jump_threshold` 已被 P1-b3 改成 jump 解码的真执行门（`model.py:2564-2566`），前向侧未做同等迁移（A4 的前向半程仍缺）。

**验证**：
```powershell
grep -n "gate_forward" fly64/fly64/main.py
# → 全部落在 RULE-19 注释、flow_json 遥测；无 control.y / write_control 附近的执行分支
python .tmp/audit_matrix_verify_deadwrites.py
```

### B5 ⚠️ 前向池被占有率稳态钉在满速（半通）

- `forward_homeo_gain`（`model.py:1486-1509`）+ `fwd_homeo_floor=0.25`（`model.py:660`）只压制 MBON→forward 腿，且封底 0.25"永不静默"。
- 前向池的 escape/reflex/accum 三条辅助腿还要过 `_aux_forward_current` + 聚合封顶（`model.py:877`、`1973-1977`、`2063`、`2091`）。
- 净效果（t1 §1.4）：前向池被自身稳态钉在满速，`raw_y≈70` 满量程，自适应信号**无法把 forward 从饱和拉下来**——只能在"更饱和"方向微调。

### B6 ⚠️ 转向主导腿量级差 10 倍（半通）

- `cx_steering_gain_turn = 0.12`（`model.py:769`），导航/学习信号经此注入转向池（`model.py:2184-2185`）。
- 转向竞争主导项 ±0.18 V/tick（M1 §2.2 / t1 S28，`model.py:345-392,1477-1520,2132-2166`）——差一个数量级，CX/学习信号**到达但打不破平局**。
- `navigation.steering_gain` 的注册区间 [0.01, 0.5] 作用在 `_goal_comp.steering_gain`（`central_complex.py:399`），但它下游还要乘 `goal_strength` 与 `cx_steering_gain_turn=0.12`，两处衰减后仍不足量级。

### B7 ⚠️ 检测伪影外溢污染四个自适应门（M3，继承 t3）

- `model.stuck_duration = memory_ctrl.stuck_duration`（`main.py:2687`），而 `stuck_duration` 因单位契约缺陷单调增长（t3 §1.3）→ 污染 `model.py:2277`（pit 振荡）、`main.py:2056`（burst 前置）、`memory.py:2186`（逃逸门）、EVO 模式匹配。这些"自适应门"读的是**伪影**，不是真实卡死。

---

## 8. 断路影响排序（哪些断口最影响实际行为）

| 排序 | 断口 | 理由 | 修复形态（供下游参考，非本任务范围） |
|---|---|---|---|
| **1** | **B1 解码器硬编码饱和非线性** | 三个行为变量是饱和解码，近零输入即满量程输出；不改它，任何上游信号都只能做"无效微调"（60.3% delta=0 的结构解释） | 把 1100/2000 系数与 `FWD_RATIO_FLOOR` 升格为可注册量，或把 `turn_rate` 归一化到前向占用率 |
| **2** | **B5+B6 forward/turn 稳态与量级** | forward 被稳态钉满、turn 主导腿 10 倍量级差，两个主行为通道的自适应信号到不了 | 让 homeostat 作用于全腿而非仅 MBON 腿；`cx_steering_gain_turn` 进入增益/注册空间 |
| **3** | **B3 教练钳位吞掉建议** | 用户可感知的"coach 未生效"本体；已实机抓到 | 让钳位对教练来源可见（`clamped_keys` 已上线）+ prompt 取值范围对齐 |
| **4** | **B2 `fallen_jump_boost` 死写** | 唯一一条"注册了却无人读"的硬死写，坠落恢复少一条跳增强腿 | 接进跳池注入，或从注册表摘除 `wired` |
| **5** | **B4 `gate_forward_threshold` 无执行消费者** | "机制存在、报告成功、无法生效"（EVO-066）典型；jump 侧已修、前向侧漏 | 前向侧做 P1-b3 同等迁移 |
| **6** | **B7 伪影外溢** | 四个自适应门读伪影；但它是 M3 口径问题，排序低于 B1-B6 | 统一单位契约 + 切断 `main.py:2687` 外溢 |

---

## 9. 方法自证：独立复现 captain 的 turn_bias 钳位

脚本 `.tmp/audit_matrix_repro_clamp.py` 用 AST 从 `main.py` 提取**真实的** `CLAMP_BOUNDS` + `apply_strategy_clamps` + `strategy_writer_source`（非重实现），回放 captain 的实机输入（`analysis-p0-4-live-verification.md` §3.1：教练写 `turn_bias=0.8 / bold=20.0`）：

```
CLAMP_BOUNDS from main.py AST: {'exploration.turn_bias': (0.0, 0.25),
                                'exploration.bold_explore_stuck_s': (1.0, 10.0)}
applied: {'turn_bias': 0.25, 'bold_explore_stuck_s': 10.0}
records: [{'key': 'exploration.turn_bias', 'requested': 0.8, 'applied': 0.25,
           'source': 'coach', 'advice_age_s': 1.0}, ...]
self-heal write-back: persisted turn_bias=0.25 (coach's 0.8 is gone)
registry alignment: turn_bias [0.0, 0.25] / bold [1.0, 10.0]  ← 与钳位一致
ALL ASSERTIONS PASSED
```

与 captain 实测逐位吻合（0.8→0.25、20→10），且额外证实两点：① `source=coach` 归属来自 `advice_ts` 新鲜度（`main.py:1189-1222`）；② 自愈回写（`main.py:1852-1858`）确实用**钳后值**覆写文件，教练原值不可恢复——与报告 §3.4 机制⑤完全一致。

---

## 10. 结论与对 M1 判定的修正

1. **M1 的"决定行为的变量与所有自适应面不重叠"在 HEAD 上已被部分打通**：三个解码器现在都有自适应写入者（学习/增益/参数/教练四面对 forward/turn/jump 三池均有注入腿）。M1 点名 6 处作用点缺失中 4 处已修复（§7 摘要），1 处（`gate_forward`）只修了 jump 侧，1 处（`set_adaptive_lr`）被 P1-b6-1 移除而非修复。

2. **但断口并未消除，而是"下沉"为三类残余**：
   - **深度层**（B1）：解码器本身硬编码，信号改的是输入、改不动饱和非线性；
   - **传导层**（B5/B6）：forward 稳态钉满、turn 量级差 10 倍，信号到不了行为；
   - **契约层**（B2/B4/B3）：死写、只上报不执行、钳位吞建议。

3. **本审计的增量贡献**：独立发现 `escape.fallen_jump_boost` 死写（B2）——这是 `wired=true` 契约的盲区（校验"读点存在"、不校验"读点写出的值有消费者"），建议把该契约升级为"读点 → 消费点"两级校验（供下游 P0-2/P0-4 参考，非本任务范围）。

4. **对下游的影响**：P0-2（EVO 可执行 fix）与 P0-4（has_fix 语义）的修复空间必须落在 B1/B5/B6 的"让已有信号真正到达"形态上，而非再新增控制分支——否则即便 EVO 产出可执行 fix、has_fix 不再永久堵死，搜索空间里的参数仍够不到决定行为的饱和解码量。

---

> **生成**: audit-engineer · 2026-09-24 · 只读审计，未修改仓库文件（除本交付文档与 `.tmp/` 三个复现脚本）
> **复现命令**: `python .tmp/audit_matrix_extract_writes.py` · `python .tmp/audit_matrix_repro_clamp.py` · `python .tmp/audit_matrix_verify_deadwrites.py`
> **交叉引用**: `analysis-t3-primary-factor-determination.md`（M1）· `analysis-p0-4-live-verification.md`（钳位实测）· `analysis-t2-evolution-pipeline-failure.md`（六失效点）
