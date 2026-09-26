# SP5-A 集成报告与 SP5-B 交接文档

> **生成日期**: 2026-09-25
> **集成协调**: sp5a-integrator / attempt `53d70883-8c3c-4c8c-a64e-c5bb6fd8ea55`（task t4）
> **团队**: fly64-sp5a-execution
> **批次**: BT8 前半 —— **SP5-A** = `P2-c2`（`terminal_surrender` 终态判据 + 四机制前置解锁）+ `P2-c3`（检测窗自适应）+ `M4-d5-b`（脑侧响应）
> **回调闭环（不得只写「全部通过」）**: **t1 → t2 → t3（needs_revision, 2 high/1 medium）→ t5（返修）→ t6（needs_revision，由前序偏差触发）→ t7（前序返修）→ t8（verdict=pass）→ t4（本报告）**
> **配置基线**: 工作树脏，**不等于 HEAD**；HEAD = `ab2761c`（本报告不声称 HEAD 等价）
> **最终状态**: SP5-A 可正式交付；SP5-B 可开工（`G4` 仍未满足，见 §8）

---

## 0. 最终受检快照（t8 开始=结束，14 文件哈希全同、changed=0）

本报告的每一个实现事实都以该快照为准，并已在 t4 中**独立复算哈希**（与 t8 报告逐字一致）：

| 文件 | 前 16 位 SHA256 | 报告引用位置 |
|---|---|---|
| `fly64/fly64/central_complex.py` | `e446c23c07e7e35b` | §5.1 D2 |
| `fly64/fly64/model.py` | `3544e154b081ace5` | §5.1 D2 |
| `fly64/fly64/main.py` | `c8518decd2b92af5` | §1/§3/§5 |
| `fly64/fly64/memory.py` | `ba5c0267eb4c649d` | §1/§3/§6/§8 |
| `fly64/skills/evolution_skill.py` | `6745fa3ae5331083` | §1/§2/§5 |
| `fly64/skills/fix_executor.py` | `64ea24575e89de83` | §5.2 D1 |
| `fly64/skills/fix_guard.py` | `869a2191af419a77` | §5.2 D1 |
| `fly64/skills/default_patterns.json` | `634adeacdea3794e` | §1 |
| `fly64/tests/test_cx_loop_break.py` | `341199689aff91ba` | §5.1 |
| `fly64/tests/test_cx_loop_break_gate.py` | `f4196e5cdcb8d757` | §5.1 |
| `fly64/tests/test_instinct_bindings.py` | `ae59b598fb346e5e` | §5.3 R1 |
| `fly64/tests/test_terminal_surrender.py` | `ba20aeddcadb04b8` | §2/§4 |
| `fly64/tests/test_oscillation_window.py` | `6add59c140bc909f` | §2/§3/§4 |
| `.tmp/fly64_trajectory.json` | `638afa70f7f4d673`（837,003 B，6000 点） | §3 |

t4 本阶段复算的核心测试（**独立于 t1/t2/t5/t7 的自述**）：

```
python -m pytest tests/test_terminal_surrender.py tests/test_oscillation_window.py \
                 tests/test_cx_loop_break.py tests/test_cx_loop_break_gate.py -q
⇒ 73 passed in 12.75s        （SP5-A 面 + D2 返修面，0 failed）

python -m pytest tests/test_evolution_fix_contract.py tests/test_instinct_bindings.py \
                 tests/test_gate_units.py -q
⇒ 2 failed, 77 passed        （2 failed = test_instinct_bindings 的 R1，非 SP5-A 面；**R1 已于本轮闭合 ⇒ 现行 38 passed，见 §6 回填列**）
```

---

## (1) SP5-A 实施摘要

### 1.1 核心交付（三条）

| ID | 名称 | 落点 | 状态 |
|----|------|------|------|
| **P2-c2** | `terminal_surrender` 终态判据 + 四机制前置解锁 | `memory.py` / `main.py` / `default_patterns.json` / `evolution_skill.py` | ✅ 完成（V17 通过；V14 真机项待 BT8，见 §9） |
| **P2-c3** | 检测窗自适应于实测交替周期（对 H3） | `memory.py` / `main.py` / `evolution_skill.py` | ⚠️ **实现完成但被 R5 回退为空操作**（见 §3，不得包装成自适应能力） |
| **M4-d5-b** | pattern 集「已放弃终态」覆盖 + 脑侧响应 | `default_patterns.json` + `evolution_skill.py` | ✅ 完成（V17 通过；V14 真机项待 BT8） |

### 1.2 P2-c2 —— 终态判据 `terminal_surrender`（观测/诊断层，不写控制）

三处改动：

1. **`wall_stuck` 的 OR 支路（自锁破环）** —— `memory.py:1440-1467`：
   ```python
   return (wall_score > 0.4 and stuck_duration > 10.0
           and (escape_behavior or surrender_evidence))     # memory.py:1467
   ```
   原判据逐字保留，**新增一条独立于 `escape_behavior` 的并行 OR 支路**；`surrender_evidence=False`（默认）时行为与改前**逐位相同**。`_vote` 以 keyword-only 追加参数透传（`memory.py:1503` 定义、`:1522-1523` 消费），`update` 侧 `:1545` / `:1566`，`MemoryController.update` 在异常更新**之前**喂入 `surrender_evidence=self._terminal_surrender`（`memory.py:2282`）—— 即「放弃态」不再既是否定检测的条件、又是它的结果。
2. **新判据** `MemoryController.terminal_surrender`（property）+ `surrender_evidence`（dict）（`memory.py:2495-2571`）：
   ```
   (stuck_duration_true > T_s) AND (loop_score > L) AND (waste_ratio > W)
     AND (reflex_active = false OR escape_behavior = false)
     AND (net_displacement_rate < D)
   ```
   · **只读 P0-a2/a3 的运动学真值 `_stuck_duration_true`**；`self._stuck_duration`（伪影量）**不在求值路径上**，由 AST 断言独立反证（构造读伪影量的变体 ⇒ 断言必报错）+ 运行期属性追踪双重核验（t3 §3 / t6 / t8 三次复验）。
   · 输入缺失 ⇒ `False`（**从不猜**）。
   · `net_displacement_rate = disp_60s / SURRENDER_WINDOW_S(60 s)`。
   · 阈值 `T_s=120 s / L=0.6 / W=10 / D=0.5 u/s` 全部 **【待标定】**（`surrender_evidence["thresholds"]["calibrated"]=False`）。
   · **零 `control.*` 写入**（C1 机检）。
3. **`main.py` 单一来源**：`waste_ratio` 每发布 tick 只计算一次（`main.py:2743-2753`），交给 controller 后才 `memory_ctrl.update`（`:2756`）；旧的内联 lambda 复用同一变量 ⇒ 口径唯一，且与 HEAD 在 n=0/5/9/10/11/37/600 上**逐值相同**（t3 脚本 `c1_and_waste.py`）。

### 1.3 P2-c2 的发布面（F1 闭合后的最终状态）

| 面 | 键 | 次数 | 位置 |
|---|---|---|---|
| `flow_json` | `terminal_surrender` / `surrender_evidence` | 各 **1** 次 | `main.py:2942-2943` |
| `flow_json` | `oscillation_window_frames` / `oscillation_alt_median_s` / `oscillation_detected` / `oscillation_adaptive_enabled` | 各 **1** 次 | `main.py:2996-2999` |
| `memory_json` | 同上 6 键 | 各 **1** 次（61 keys / 61 distinct / `duplicates={}`） | `main.py:3223-3224` / `:3229-3232` |
| `evolution_log.context` | 上述键 + `oscillation_window_design`（severity=**medium**，含 R5 理由） | 单一实现 | `evolution_skill.build_evolution_log_context()`（`evolution_skill.py:3529`），调用点 `:3621` |

读侧为 **flow → memory 回退**（单一口径），t6 已实测三分支：flow 有/memory 无 ⇒ 非 None；flow 缺/memory 有 ⇒ 回退成功；双缺 ⇒ `None`。

### 1.4 四机制前置解锁（P2-c2 ③ —— 通过**搜索面**解锁，不是改写门）

`central_complex.py` 的 CX 突破门与 burst 门**属 P1-b4/b5 所有**，改写它们会是控制路径编辑。因此 P2-c2 的「解锁」落在**自适应搜索面**：`ADAPTIVE_FACE_PIDS`（`evolution_skill.py:2349`）+ `prioritise_adaptive_face()`（`:3135`）+ `maybe_start_surrender_trial()`（`:3149`）。终态判定为真时，搜索重心前移到注册过的自适应 pid（增益 / 腿权重 / CX 环路突破 / steering），**不写控制、不改门、不打 `.py` 补丁**。b1/b2 的 pid 在 P1-b1/b2 注册前被过滤掉（不伪造解锁）。

### 1.5 M4-d5-b —— pattern 更新

| pattern | 改动 | 证据 |
|---|---|---|
| `circle_loop` | 排除条件 `wall_score <= 0.1` → `struggle_or_terminal: true`（**唯一的放宽项**，见 CAVEAT） | `default_patterns.json:8/10/34` |
| `micro_loop_weave_signal` | 排除条件 `escape_behavior: true` → `struggle_or_terminal: true` | `default_patterns.json:332/337/357` |
| **`terminal_surrender_stuck`（新增）** | `severity: high`、`conditions: {terminal_surrender: true}`、`fix_template` 为**自适应面解锁说明（非控制写）** | `default_patterns.json:481/486/490/502` |

**键生产者自检（无零生产者新键）**：`terminal_surrender`、`struggle_or_terminal` 均由 `DataCollector.get_metrics()` 生产（`SensorSample` 新字段读 flow→memory）。`evolution_skill.py` 的内联 `DEFAULT_PATTERNS` 镜像与 JSON 两侧 `conditions`/`severity` 全等。

### 1.6 硬约束（全程机检，t3/t5/t6/t7/t8 五次复验一致）

| 约束 | 判据 | 结果 |
|---|---|---|
| **C1 / G5** | `git diff -U0` 新增 `control.* =` 行数 = 0 | ✅ 0（严格与宽两种正则均 0） |
| **C3** | `model.py` 中 `jump_rate >` 恰 1 处 | ✅ 1 |
| **C5** | `_vote` 严重度返回序与 HEAD **完全相同**（FALLEN→MICRO_LOOP→OSCILLATING→WALL_STUCK→STUCK_RAMP→IDLE） | ✅ 未动；新增两参数均为 keyword-only 追加 |
| **C6** | 四处 `clip(·,±70)` 饱和式逐字不变且**不出现在 model.py diff 中** | ✅（`main.py:2354/2355/2545/2546`） |
| **E-4 标注纪律** | 新阈值常量逐行带【待标定】；引用 E-4 数值处 6 行内同时带「检测伪影」+「H1」 | ✅ 唯一瑕疵：`OSC_TICK_DT`**块级**有声明、**逐行**缺（见 §6 / R2） |

---

## (2) t3 finding 及逐项闭合

t3 判 **needs_revision（2 high / 1 medium）**，t5 返修，t6 复验**逐项闭合且 t3 已通过项零转红**，t8 再次确认 F1–F4 未回退。

| # | 原问题（t3 原话要点） | 最终处置（t5 实施 → t6/t8 复验） | 状态 |
|---|---|---|---|
| **F1**（high） | **发布面错锚点**：`terminal_surrender`/`surrender_evidence` 在 `memory_json` 内出现 **2 次**（同一 dict 字面量重复键）、在 `flow_json` 内 **0 次** ⇒ 键位错锚 | ① 两键加入 **flow_json**（`:2942-2943` 各 1 次）；② 删除 memory_json 的重复对，memory_json 现 61 keys / 61 distinct / `duplicates={}`，保留 1 份作回退源；③ 新增 `build_evolution_log_context()`（flow→memory 回退，单一实现）；④ 新增 `TestF1PublishSurface`（4 项：flow 各键 1 次、memory_json 无重复键、6 新键每面 1 次、读侧三分支） | ✅ **闭合**（t6 终局判据实测复现，含 `thresholds` 齐全） |
| **F2**（high） | **tick 口径 + W 设计**：`OSC_TICK_DT=0.02 s` 与真实发布门间隔（≈0.21 s）差 **10.5×**；`oscillation_alt_median_s` 因此发布错误值；且 W 在真实口径下的落地板问题未处理 | ① 口径修正为 **0.21 s**（实测发布间隔 median 0.210 / mean 0.221 / p10 0.20 / p90 0.23）；② 真实序列重推 `W = clip(6·1, 30, 300) = 30`（历史地板）；③ 按 **R5 回退**：新增 `OSC_ADAPTIVE_ENABLED=False` 闩锁 ⇒ 窗口固定 30 帧（与 HEAD **0/6000 tick 不同判定**），T_alt/W **只记录**；④ 新增 `oscillation_adaptive_enabled` 遥测 + `evolution_log.context["oscillation_window_design"]`（severity=**medium**，含 R5 理由）。**未**用 `ALT_GAP_FRAMES`/系数去凑 W | ✅ **闭合**（t6 核实 1.0×；t8 确认 W=30 地板 + 闩锁 OFF 未变） |
| **F3**（medium） | **合成样本**：V18① 用了与实测周期自相矛盾的合成序列（18 帧/次翻转 = 0.72 s，实测 0.37 s 的 2 倍）；且 t2 曾断言 `.tmp/fly64_trajectory.json` 不存在（**t3 纠正：该文件确实存在，837,003 B / 6000 点**） | ① 自相矛盾样本（`ALT_GAP_FRAMES=18`）**已删除**（全仓 0 命中）；② V18① 判据来源改为**真实轨迹回放**（`real_series` fixture，1 点 = 1 检测 tick，缺文件则 skip）；③ 仅存合成序列位于 `TestDisabledDesignMath`，标注为合成、周期自述（12×0.21 s）与实测不矛盾，且**只在 monkeypatch 打开闩锁时**验证被停用设计的算术 | ✅ **闭合** |
| **F4**（low） | **失败清单归类**：t1 的「48 项均与本任务无关」对 SP5-A 成立，但**不能读作「均为基线预存」**；其中 ≥6 项实际由他人未提交改动新增（`fix_executor.py` T3 门、`central_complex.py` P1-b5） | 全量失败清单按 **HEAD ↔ 工作树逐项归因**，三类分开表述：①预存/环境 ②环境抖动（`test_optic_flow` 单跑 41 passed）③**前序阶段有意改动新增 13 项**（其中 0 项由 SP5-A 代码引起）。见 §5.3 | ✅ **闭合（表述已纠正）** |

> **注**：t3 自带的审计脚本 `main_publish_key_audit.py` 有一处 bug（`KEYS.get("flow")` 而非 `"flow_json"`），导致其 `CONTRACT_SATISFIED` 行不可信 —— **逐键表才权威**；t6 已修正该脚本（现为 True）。建议 SP5-B 顺手同步口径。

---

## (3) P2-c3 的诚实结论（**不得包装**）

### 3.1 结论

> **P2-c3 的自适应检测窗在真实 tick 口径下是行为空操作（no-op）。**
> `W = clip(6 · T_alt, 30, 300)` 在真实序列上得出 `T_alt = 1 帧` ⇒ **W 恒落地板 30**（即历史固定窗）。
> 规格设想的 `W ≈ 110 帧` 在真实数据上**不可达**。
> 已按 **R5**（「条件①失败 ⇒ 回到固定 30 帧并只记录，另在 `evolution_log` 写 `medium` finding」）**回退**：`OSC_ADAPTIVE_ENABLED = False` 闩锁，窗口固定 30 帧，T_alt/W **只记录不驱动**。
> **本项不构成「自适应检测窗」能力交付**；它交付的是「自适应机制已实现 + 如实测量到它在当前口径下不生效 + 按 R5 回退 + medium 记录」。

### 3.2 证据链

**决定性口径事实（t3 独立实证）**：`memory_ctrl.update()` 全仓唯一调用点在 `main.py:2756`，位于发布门 `if tick_start - last_publish >= (0.2 if rtf < 0.95 else 0.1)` 之内 ⇒ **检测器一帧 = 一次发布 ≈ 0.21 s**，**不是** `OSC_TICK_DT` 旧值 0.02 s（差 10.5×）。轨迹点在同一发布块内、`update` 之前写入（`:2724` vs `:2756`）⇒ **1 轨迹点 = 1 检测 tick**。

| 回放口径 | 翻转中位间隔 | W | 600 tick 内最大翻转 | 正常段占比 | 与旧固定 30 帧窗的判定差 |
|---|---|---|---|---|---|
| **忠实回放**（1 点 = 1 tick，V18① 判据来源） | **1 帧** | **30（地板）** | 1（≤ 4 ✅） | 0%（≤ 5% ✅） | **0 / 6000 tick 不同** |
| 生产口径回放（喂 `main.py` 实际发布的 `disp_60s`/`median_speed`） | 1 帧 | 30（地板） | **48 > 4**（❌） | 0% | **0 / 6000 tick 不同** |
| （已删除的合成样本，仅存档） | 18 帧 | 108 | — | — | 该 108 来自 18 帧/次翻转 = 0.72 s 周期，是实测 0.37 s 的 **2 倍** |

⇒ **V18②（可标定：系数 6→3/12 使 `oscillation_window_frames` 随之变化）仍然成立**（机制接线在位），但**V18①「W ≈ 110」条目在真实口径下不可达**，已转为「W = 30 且与 HEAD 逐 tick 同判定」的记录。

### 3.3 R5 回退的**解释性边界**（t5 提出、t6 核实、t8 确认，captain 需知晓）

t5 曾建议把 R5 解释为「振荡判定不再驱动反射」，但该解释**本轮实测不成立**（忠实回放最大 1 次翻转 / 600 tick，判定稳定，不抖动）。若强行实现更强的「不再驱动」，需删除 `_vote` 的 `OSCILLATING` 分支 —— 那会相对 HEAD 构成**新的行为回归**、破坏 4 个既有测试，并抽掉 P2-c1 规格明确要用的仲裁类别（`stuck_ramp → oscillating`）。故实际采用的最强可辩护解释是：

> **新自适应机制不驱动任何东西（record-only）；HEAD 原有的「检测 → 反射」驱动面逐位未动。**

t6 用 HEAD 的 `memory.py` 抽为独立模块做差分，4 条序列（真实 6000 / gap18 / gap1 / mixed）上 `update()` 状态、`_vote()`、`_detect_oscillating()` **全部 0 差分**；`_vote` 的 `OSCILLATING` 分支**保留且仍活**（gap=1 时 1995/2000 tick、真实序列 5490 tick 判 oscillating）。

---

## (4) F2 附带的**独立真缺陷**：`oscillation_alt_median_s` 的 10.5× 遥测口径错误（单列）

这是 F2 调查过程中发现的一条**独立于 W 设计**的遥测正确性缺陷，与自适应窗是否生效无关，且**即使自适应窗永久停用也必须修**。

| 项 | 内容 |
|---|---|
| **缺陷** | `oscillation_alt_median_s` 发布值以 `OSC_TICK_DT = 0.02 s` 换算帧→秒，而真实检测器帧间隔是**发布门间隔 ≈ 0.21 s** ⇒ 发布于真实半周期的 **1/10.5** |
| **实测** | 真实半周期 **0.21 s**；错误发布 **0.02 s** ⇒ **10.5×** |
| **发现** | **t3**（F2 调查中的附带发现，`v18_real_replay.py`） |
| **修复** | **t5**：`OSC_TICK_DT` 0.020 → **0.21 s**（基于实测分布 p10 0.20 / median 0.210 / mean 0.221 / p90 0.23，**【待标定】**） |
| **核实** | **t6**：`oscillation_alt_median_s` 实测发布 **0.21 s** = 真实半周期，标定为 **1.0×**（t3 脚本复跑自证 "1.0x smaller"） |
| **约束** | 该修正是**口径修正**，不改变任何门限（`alternations >= 3` / `OSC_ALT_MIN=3` 逐字未动，只升不降） |
| **残留** | R2（low）：`OSC_TICK_DT` 行**缺逐行【待标定】**（块级已声明） |
| **对 SP5-B 的影响** | 无阻断。但 SP5-B/收口在使用 `oscillation_alt_median_s` 做标定时，必须知道它现在才是**真秒**；任何此前基于 0.02 s 的推算需作废 |

---

## (5) 前序阶段偏差及返修（**本阶段最重要的产出**）

> t3/t6 的 needs_revision 有 **2 项来自前序 SP3/SP4 交付物的偏差**，与 SP5-A 本体无关。它们是本次集成最值得复盘的结论：**SP5-A 的验证动作反过来发现了前序阶段的真回归与规格偏差**。

### 5.1 D2 —— `P1-b5`（SP3 交付物）= **非预期回归**（high，已闭合）

| 项 | 内容 |
|---|---|
| **规格要求（§5.5）** | `_no_progress = progress_ineffective or loop_score > loop_breakout_threshold` + `_burst_ok = not burst_active`；`update()` 新增 `progress_ineffective/loop_score/burst_active` 三个 kwargs；门条件 `stuck > stuck_s and _no_progress and _burst_ok and cooldown`；发布五个观测键 |
| **交付实况（偏差）** | 工作树里是 `_no_goal = stuck_duration > 0`（首命中即跳）；`progress_ineffective`/`burst_active`/`_no_progress`/`_burst_ok`/`loop_breakout_threshold` **在 `central_complex.py` 与 `model.py` 完全不存在**；`model.py:2154` 的 `cx.update` 无三 kwargs；`flow.json` 无 P1-b5 五键 |
| **回归判据（HEAD 差分，t6 定性）** | 同场景（真实 goal vector + stuck）：**HEAD `_jump_seq = 0`，工作树 `= 1`**，而 §5.5 改前/改后**都保持「有目标 / 有进展 ⇒ 不跳」** ⇒ `test_cx_loop_break::test_active_goal_is_never_overridden` 属**非预期回归**（不是「有意变更 ⇒ 旧断言过时」） |
| **根因（必须如实记录）** | **当时未被 SP3 的验证套件捕获 ⇒ 属验证范围缺口**：SP3 的 `test_cx_loop_break_gate.py` 在偏差发生时尚不存在，`test_cx_loop_break.py` 的 4 项既有测试中「有目标时不得跳」这一条当时未覆盖到「有目标 + 长 stuck」组合；直到 SP5-A 的失败清单归因（t5 F4）才把它从 13 项中分离出来 |
| **返修（t7）** | `central_complex.py`：`:50` 新增 `CX_LOOP_BREAKOUT_THRESHOLD = 0.6`；`:203-212` 新增 `loop_breakout_threshold`（注册键 `navigation.loop_breakout_threshold`）；`:233-236` 观测镜像 `_last_burst_active`/`_last_no_progress`；`update()` 新三 kwargs；`:344-352` 判据重写（`_no_goal` 降级为幅度项**保留名与语义**）；`:363-365` 门条件；`:377-378`/`:402-403` 记录与 reset；`:461-464`/`:536-538` `CentralComplex` 镜像与 `_sync_cx3_backrefs`。`model.py:2176-2180` 传三 kwargs。`main.py`：`:1524` 计数器、`:2193` `burst_active` 镜像、`:2190-2191` burst 计数、`:2846-2854` `progress_ineffective`、`:3047-3053` burst-off 归因、`:3249-3254` **五个观测键各恰 1 处**。新增 `test_cx_loop_break_gate.py`（16 项） |
| **t7 自证（before/after，同场景）** | 把判据临时改回 `_no_goal = stuck_duration > 0` ⇒ `TestLoopBreakDoesNotOverfire` **1 failed / 2 passed**（`assert 1 == 0`）；修复后同命令 **3 passed**，整文件 **15 passed** |
| **t8 复验（决定性）** | ① `test_cx_loop_break.py` **15 passed**，同场景 `_jump_seq` 现行 = 0 = HEAD；② **独立反证**：把当前文件判据在 `.tmp` **副本**里改回 `_no_progress = stuck>0`（不动仓库）⇒ 副本 `_jump_seq=1`、现行 = 0 ⇒ **测试是真闸门**，与实现者自述一致；③ 未接线调用方差分矩阵 7 场景 × 200 tick：转向 bias 逐位 0 差分、`_jump_seq` 0 差分 ⇒ 未改掉旧行为 |
| **§5.5 的一个字面歧义及处置（t7 登记，captain 已认可，t8 复核）** | §5.5 字面把 `progress_ineffective` 默认写成 `False`；照字面取 False 会让「未接线调用方」（不传该 kwarg）从「卡死且无目标 ⇒ 跳」变为「永不跳」，使 4 项既有测试转红。故实现为 **三态 `progress_ineffective: bool | None = None`**：`None` = 未给裁决 ⇒ 保持 HEAD 行为；非 None ⇒ 裁决权威。该解释性选择**书面登记**于 t7 报告（`team.json` t7.output），非仅代码注释 |
| **F6 互锁输入可用性** | ✅ `main.py:2193 model.burst_active = _deadlock_burst_remaining > 0`（**读镜像，非控制写**）；t8 行为验证：`burst=True` 时无论 progress/loop 取值**均不触发**，burst 结束后可触发 |
| **状态** | ✅ **闭合**（t8 verdict=pass 的主要依据） |

### 5.2 D1 —— `M4-d1`（SP4 交付物）= **规格偏差（V20 残留）**（medium，5/5 已处置）

| 项 | 内容 |
|---|---|
| **偏差实况（t6 核实）** | 规格要求的新增共享 helper `fly64/skills/fix_guard.py:is_py_patch` **不存在**、`is_py_patch` 全仓 **0 命中**，门被**内联**在 `fix_executor.py:469-506` |
| **是否漂移** | **无漂移**：全仓只有这一处判据（单点写盘前拦截）⇒ **T3 不变量成立**（0 条 `.py` 被执行 + 全部落提案）。规格要求的「同 helper」是**单一性**要求，内联单点**不违反**其安全语义，但**违反其字面接口契约** |
| **残留规格项（t6 列出）** | 共享 helper；`evolution_skill` 侧前置门；`approved_proposal_ids` 令牌；V20③ 白名单断言与 V20④「同一 helper（mock 调用次数）」；T3 拦截未置 `manual_action_needed=True`（导致被记成「执行失败」而非「提案」） |
| **对 G6 的影响** | G6 判据 = 「T3 门禁 + `FixExecutor.execute` 运行时守卫 + 静态断言**三者同 helper、同判据**」。**安全语义（0 条 `.py` 执行）当时已成立**，但**字面契约（同 helper）未成立** ⇒ 当时**不能声称 G6 通过** |
| **返修（t7，5/5）** | ① 新增 `fly64/skills/fix_guard.py`（`is_py_patch` = `fix_files ∪ parse_fix_template` 指令；`patch_scope` / `blocked_py_targets` / `py_patch_gate` / `write_change_proposal` / `load_approved_proposal_ids` / `approve_proposal`）；`fix_executor.py:41-48` 导入，原内联判据整体改为调用 `py_patch_gate`（`:490`）+ `write_change_proposal`（`:512`）；② `evolution_skill.py:97` `py_patch_pre_gate` 在 `:3257` **先于** `:3265 record_fix` 调用并 `continue`（被拦的 fix 不再进 `fix_catalog`、不再被记成「已应用」）；③ `approved_proposal_ids` 令牌（`artifacts/approved_proposal_ids.json`，ledger 记 `approved` + `status`）；④ V20③/V20④ 测试补齐（`test_evolution_fix_contract.py` **33 passed**）；⑤ 拦截时置 `manual_action_needed=True`（`fix_executor.py:531`） |
| **关键设计决定（值得单列，见 §5.4）** | 初版让令牌**解除** `blocked`，其自身的 V20 测试当场抓到 **approved 提案真的执行了 `.py`**（`while True:` → `while False:`）。已改为 **`blocked` 恒 True**（T3 是**作用域不变量**，不是许可），令牌**仅改变上报状态** |
| **t8 复验** | `is_py_patch` 存在且被两侧引用（`fix_executor.py:490` / `evolution_skill.py:106`）；`py_patch_gate` 内**恰一次**调 helper；`blocked = is_py and blocked_targets`，与 `approved` 正交；**令牌不放行 `.py`（独立复现）**：批准后 `FixExecutor` 对 `.py` 目标 sha256 前后相同（`7ced5f7798a6`）、`manual_action_needed=True`、仅写提案，批准谓词全仓仅 `fix_guard` 内部读取 ⇒ **无绕过路径**；5/5 子项落实 |
| **对 G6 的最终结论** | G6 的**字面契约已可声称成立**（同 helper、同判据、唯一写盘点、静态断言）；t8 曾登记 4 条 low 残留（R2/R3/R4：`OSC_TICK_DT` 逐行标注、`_no_goal` 表述更正、`fix_guard` 降级导入分支缺 `py_patch_gate`/`PY_PATCH_BLOCK_REASON`）⇒ **这批残留已在本轮全部 done**（见 §6 回填列）⇒ **G6 的收口判定不再被它们阻塞**（均不阻断 SP5-B） |

### 5.3 **13 项失败的真实构成**（区分「有意变更 ⇒ 旧断言需更新」与「真回归」）

**结论：13 项中 0 项由 SP5-A 引起。** 构成（t6 纠正 / t8 复核）：

| 归因 | 数量 | 明细 | 定性 |
|---|---|---|---|
| `M4-d1`（T3 门，SP4 交付物） | **10** | `test_fix_executor` ×7 + `test_fix_template_interpreter` ×3 —— `.py` 目标被执行门拦下、文件未改、提案已写 ⇒ **旧断言编码的是 T3 之前的契约** | **有意变更 ⇒ 旧断言需更新**（t7 已连带把执行类集成测试的目标改为 `.txt`，见 §5.4） |
| `M4-d5-d`（钳位，SP4 交付物） | **2** | `test_instinct_bindings` —— 树把 `turn_bias` 钳到 **0.25**，旧断言期待 **0.8** | **有意变更**；**已于本轮闭合**（选项 A：拒绝 + `reject_reason`，38 passed）⇒ 见 **R1** |
| `P1-b5`（CX 环路突破，SP3 交付物） | **1** | `test_cx_loop_break::test_active_goal_is_never_overridden` | **真回归**（D2）⇒ t7 修复、t8 复验回绿 |

**去向**：t7 修复 + 连带测试改动后，t8 全量 **37 failed / 1544 passed / 42 skipped**，与 t6 的 47 项 Compare-Object：**10 项转绿**（`cx_loop_break` 1 + `fix_executor` 7 + `fix_template_interpreter` 2）、**0 项新增**。残余 37 = **34 预存/环境**（`what_i_see` 10、`mbon_saturation` 8、`invariants` 4、GBK 3、`p1_neural_takeover` 2、`plugin_mhr` 2、其余 5）+ **2 × `test_instinct_bindings`**（R1，**已于本轮闭合 ⇒ 现行 38 passed**）+ **1 × `test_allow_llm_false`**（隔离 1 passed / 整文件 48 passed ⇒ **flaky**，非需修复）。

> t4 本阶段独立复算（见 §0）：`test_evolution_fix_contract.py` + `test_gate_units.py` 全绿，**唯二**失败即 `test_instinct_bindings` 的 R1 两项，错误信息与 t8 报告逐字一致：`assert {'turn_bias': 0.25} == {'turn_bias': 0.8}`。

### 5.4 工程亮点（供收口与复盘）

1. **令牌不解除 `blocked`**（设计决定，t7 实施 / t8 独立复现）：初版让令牌放行 `.py`，被其**自身 V20 测试**当场抓到（`while True:` → `while False:`）。改为「**T3 是作用域不变量，不是许可**：`blocked` 恒 True，令牌只改上报状态」，并由 `test_approval_does_not_make_py_executable` **锁死**。这是「测试先于实现意图」的正面案例。
2. **`.py` → `.txt` 连带改动**（t7 实施 / t8 核实**必要且未削弱验证强度**）：SP4 的内联门引入后，`test_fix_executor` 9 项 + `test_fix_template_interpreter` 1 项执行类集成测试用 `.py` 目标，必然被 T3 拦下 ⇒ 长期 RED。已把这些**执行类集成测试**的 fixture/模板目标改为 `.txt`（**锚点内容不变**，仍断言 `all_applied`、写入内容、insert/replace/rollback/rewrite **真落盘**）；解析类 `.py` 断言**保留**（`test_fix_executor` 4 处、`test_fix_template_interpreter` 18 处仍为 `.py`）。t8 结论：**未发现以改测试掩盖问题**。
3. **exit code 1 的真实原因**（t7 报告 / t8 独立判定）：默认 Windows Temp 下，pytest 进度 100% 后 `pytest_sessionfinish → tmp_path_factory._exit_stack.close → cleanup_dead_symlinks` **PermissionError**，**无汇总行、exit 1**。把 `TMPDIR` 指向工作区 ⇒ **143 passed, exit 0** ⇒ **退出码 1 纯属 pytest atexit cleanup 的 Windows Temp 权限问题，无隐藏测试失败**。
   · **t4 复现**：本报告全部 pytest 命令均设 `TMPDIR=<workspace>/.tmp/t4_tmp`，**全部 exit 0**。
   · **收口建议**：固定 `TMPDIR`（或在 CI/收口脚本里显式设置），避免后续把 exit 1 误判为测试失败。

### 5.5 未做项（如实登记，不得默默省略）

* **`_ext_goal_strength` 的「幅度调制」未落地**：§5.5 只描述语义、**未给公式**，且不存在可判定的验收指标；改动会改变**全部 CX 转向量**（回归面大）。按最小风险原则不实施。
* **R3（low）表述更正**：t7 曾写「`_no_goal` 仍作为幅度项被保留使用，未变成死变量」；t8 实测**与源码不符** —— 它仅 `central_complex.py:333` 赋值、**全模块无读取**（死赋值）。**本报告采用 t8 的更正结论。**
* **`M4-d5-d` 的 D4 已闭合** ⇒ 见 R1（选项 A：拒绝 + `reject_reason`；38 passed）。

---

## (6) t8 残留 R1–R5（**均不阻断 SP5-B，但需明确归属与关闭时机**）

| # | 级别 | 问题 | 归属 / 关闭时机 | BT8 收口前必须关闭？ | 收口状态（**t4 回填，2026-09-25**，团队 `fly64-aa-wiring`） |
|---|---|---|---|---|---|
| **R1** | **medium** | **D4 未闭合**：`M4-d5-d` 仍是**静默钳位**（`turn_bias` 0.8 → 0.25），且**无 `reject_reason`**；`test_instinct_bindings` **两处旧断言未更新**（断言 0.8、实得 0.25，**2 failed**） | 关法**由 captain 决定**：(a) 改为「拒绝 + `reject_reason`」（符合 §M4-d5-d「候选值必须满足 `registry_min ≤ v ≤ registry_max` 且 `clamp_min ≤ v ≤ clamp_max`，否则 `return None` 并记 `reason`」的**规格字面**）；或 (b) **书面确认**钳位并改断言（`0.25` 为新契约） | ✅ **是** | ✅ **已闭合（选项 A：拒绝 + `reject_reason`）** —— 走 (a)：越界**不钳位、不晋升**，记结构化原因。证据：`test_instinct_bindings` **2 failed → 38 passed**；NEG 探针（0.8 ×3 improved）`promoted=False` / `reason=out_of_registry_interval` / `stored_params={'turn_bias': 0.8}` **未被改写为 0.25** / `get_binding=None`；POS 探针（0.2 ×2）`promoted=True` 正当路径未破。落点 `fly64/fly64/instinct_bindings.py:100-128/172-233/468-493/520-526/593-603`；测试 `tests/test_instinct_bindings.py:123/211-333/360` + `tests/test_evolution_fix_contract.py:718-760`。独立复核：t3 §5、t6 §9（无回归） |
| **R2** | low | `OSC_TICK_DT` 行**缺逐行【待标定】**（块级已声明） | 实现者/收口顺手 | ⛔ 否（建议同期） | ✅ **done** —— `fly64/fly64/memory.py:1267-1276`：`OSC_TICK_DT` 行补**逐行【待标定】**并注明「数值是实测来源、常量本身属待标定类」；PIN `tests/test_oscillation_window.py:175`（逐行 tag 缺失即红）。复核：t3 §6 |
| **R3** | low | 更正「`_no_goal` 未变成死变量」表述（实为**死赋值**） | 文档/注释 | ⛔ 否 | ✅ **done** —— `fly64/fly64/central_complex.py:334-346`：改为明确「**DEAD ASSIGNMENT：本行赋值一次、全模块零读取**」+ 保留原因 + **待清理**；文档同步 `docs/execution/fly64-change-specs.md` P1-b5「改后」行（⚠ R3 实测更正）；PIN `tests/test_cx_loop_break_gate.py:266`。复核：t3 §6 |
| **R4** | low | `fix_guard` **降级导入分支**缺 `py_patch_gate` / `PY_PATCH_BLOCK_REASON`（不可达路径） | 实现者 | ⛔ 否 | ✅ **done** —— `fly64/skills/evolution_skill.py:68-142`：降级 `except ImportError` 分支补齐 `PY_PATCH_BLOCK_REASON`（`:74`，与 `fix_guard` 逐字一致）与 `py_patch_gate`（`:100-140`，契约同构、`degraded=True`、**恒不因批准令牌放行 `.py`**）；PIN `tests/test_evolution_fix_contract.py:217`（**真跑**该 except 体，非只读源码）。复核：t3 §6 |
| **R5** | low | **归因更正**：t7 称 `test_bold_explore_decision_source` 由「他人 `main.py` 改动引入」；t8 实测该行 **HEAD 与工作树逐行相同** ⇒ 实为**预存陈旧断言**（v2.12 重构遗留），**非他人引入**。建议断言改写到 `resolve_decision_source` | 归属 decision_source 改造者 / 收口 | ⛔ 否 | ✅ **done** —— `tests/test_evolution_capability.py:438` 改写为断言 `resolve_decision_source` 的**返回通道集合** + 运行循环**必须委托**该函数；新增 `:471` 行为型优先级用例（dialogue > cliff_reflex > anomaly_reflex > escape > steering）；docstring 记录 t8 归因（预存陈旧断言）。复核：t3 §6 |

> **R1–R5 收口终态（t4 回填）**：**R1 done（选项 A）/ R2 done / R3 done / R4 done / R5 done —— remaining：0 项。**
> 实现与复核链：**t2（实现）→ t3（独立复核，§5/§6）→ t5（F4 等返修）→ t6（复验 verdict=pass）**；本轮回归集 **292 passed / exit 0**。
> 详细证据与「拒绝但保留证据」的精确边界见 `docs/execution/sp5a-closure-and-aa-wiring-report.md` §7。

> **「3 项转绿」的如实更正（captain 要求；t4 收口时更新）**：t8 当时记为「『3 项 P1-b5/M4-d5-d 失败已转绿』实际只兑现 **1/3** —— `test_cx_loop_break` 1 项已转绿；`test_instinct_bindings` 2 项仍未绿（= R1）」。**该 1/3 的表述现已过时**：R1 于本轮闭合（t2 实现 / t3·t6 独立复验）后，**3/3 已全部兜现** —— `test_cx_loop_break` **1** 项（t7 修复、t8 复验）+ `test_instinct_bindings` **2** 项（R1 闭合，**38 passed**）。三项中**不存在尚未兜现的项**。

---

## (7) 阈值标定状态

**全部为规格给定初值或实测初值，均为【待标定】；M4-d3 负责标定。**

| 阈值 | 当前值 | 位置 | 状态 |
|---|---|---|---|
| `T_s`（kinematic stuck seconds） | 120.0 s | `memory.py:2134` | 【待标定】（规格初值） |
| `L`（`loop_score` floor） | 0.6 | `memory.py:2135` | 【待标定】（规格初值） |
| `W`（`waste_ratio` floor） | 10.0 | `memory.py:2136` | 【待标定】（规格初值） |
| `D`（net disp rate ceiling） | 0.5 u/s | `memory.py:2137` | 【待标定】（规格初值） |
| `SURRENDER_WINDOW_S`（`disp_60s` 窗长） | 60.0 s | `memory.py:1122` | 口径常量（非待标定项） |
| **`T_alt` / W（自适应窗）** | **W 恒 30（地板）**；`T_alt` 只记录 | `memory.py:1266-1275` / `:1437` | **【待标定】** + **R5 闩锁 OFF**（`OSC_ADAPTIVE_ENABLED=False`） |
| `OSC_TICK_DT` | 0.21 s（实测 median） | `memory.py:1272`（块 `:1267-1276`） | 【待标定】（**R2 ✅ 已 done**：逐行标注已补，PIN `test_oscillation_window.py:175`） |
| `OSC_WINDOW_MIN / MAX / CYCLES_PER_WINDOW` | 30 / 300 / 6 | `memory.py:1266-1268` | 【待标定】 |
| `OSC_ALT_MIN`（交替门限） | 3（只升不降） | `memory.py`（字面量未改） | 规格给定 |
| **`CX_LOOP_BREAKOUT_THRESHOLD`** | **0.6** | `central_complex.py:50`（注册键 `navigation.loop_breakout_threshold`） | **【待标定】**（规格初值） |
| `CX_LOOP_BREAK_STUCK_S` | 45.0 s | `central_complex.py:40` | 【待标定】（规格初值） |
| `CX_LOOP_BREAK_COOLDOWN_TICKS` | 1500 ticks | `central_complex.py:44` | 【待标定】（规格初值） |
| `dwell_ticks`（P2-c1 升级） | 1500 ticks | 规格（H14） | 【待标定】—— **SP5-B 施工项** |
| `commit_threshold` k 因子 | 1.5 | `evolution_skill.py:2182` | 【待标定】（规格要求 `k ≥ 2`，见下） |

**证据缺口（未关闭）**：

| 缺口 | 状态 | 影响 |
|---|---|---|
| **H5**（`memory.json` 运行态持久化） | 🔶 **仍不存在** | 同 SP1–SP4，未关闭 |
| **H6**（`.cache/malecns` 连接组缓存） | 🔶 **仍不存在** | 未关闭 |
| **H11**（真实 SM64 连接组验证） | 🔶 **仍不存在** | 未关闭 |
| **H2**（E-4 报告快照不可复现） | ⚠️ 保持 | V14 真机复验的前置（§9） |
| **H3**（oscillating 抖动） | ⚠️ **部分关闭**：抖动实测≤1 翻转/600 tick（稳定）；但「自适应窗带来收益」**不成立** | 见 §3 |
| **H13**（长窗 fitness 可分辨） | 🔶 **恶化/未决** | 见 §7 附（A/A 面） |

---

## (8) A/A 窗累积状态（**含 t4 新发现，需 captain 处置**）

> **【本批次更正（t1，2026-09-25）—— 只更正被取代的注释，不改本节结论与证据链】**
> §8.1 / §8.2 记录的是 **t1 接线之前**的快照；其中三条断言**已被本批次取代（现为假）**：
> ① 「磁盘上『已发布』的窗数 **25**」② 「收集器**创建后从未 `record()`、从未 `report()`**」
> ③ 「报告文件**可被测试覆写**」。逐条新旧对照见
> `docs/execution/sp5a-closure-and-aa-wiring-report.md` **§12 O-2**；现行事实见该报告 §0/§1/§2/§4。
> **本节未变的结论**：`G4` 仍未通过（**真实 n = 0**）、`auto_commit_enabled=false`、阈值仍【待标定】。
> **行号口径**：更正块中的行号是本批次（t1）实测值，**随代码变动会漂移**，引用时以**符号名**为准（同 §12 O-4 的口径）。

### 8.1 当前 n 值与距 G4 差距

| 项 | 值 | 来源 |
|---|---|---|
| 磁盘上「已发布」的窗数 | ~~**25**（`min_windows_required: 20`）~~ ⇒ **0（文件已不存在）**（**【t1 更正】**） | **旧**：`fly64/skills/fitness_aa_report.json`（711 B，mtime `2026/9/25 01:29` —— t4 复跑测试后重写）；**现**：该文件已不在仓库，原文件隔离为 `artifacts/aa_wiring/quarantine/fitness_aa_report.synthetic_25windows.json`（711 B）；规范产物路径现为 `artifacts/fitness_aa_report.json`（`AA_REPORT_PATH`），**当前亦不存在** |
| **真实累积窗数** | **0**（结论未变，**原因已变**）**【t1 更正】** | ~~`EvolutionPipeline._aa_window_collector`：**创建后从未 `record()`、从未 `report()`**（全仓 `_aa_window_collector` 仅 1 处命中 = `evolution_skill.py:2387` 构造）~~ ⇒ **已接线**：`run_one_cycle` → `BrainMutator.observe_aa_window` → `AAWindowCollector.record` / `record_two_window_pair`（本批次实测 `evolution_skill.py:4115`（调用点）、`observe_aa_window` `:3562`、`collector.record` `:3678`、`record_two_window_pair` `:3685`）；n 仍为 0 的原因**由「从未被喂数」变为「尚无运行累积」** |
| **G4 门要求** | `bootstrap_upper95(P95) ≤ 0.03`（**n ≥ 100 窗**）**且** `aa_two_window_fpr ≤ 1%`（≥50 对双窗**实测**） | 规格 §1.3 G4 / 执行计划 |
| **差距** | n 真实值 **0 / 100**；即便按 SP4 的「20+ 窗」宽松门宽，**真实值亦为 0** | — |
| `auto_commit_enabled` | **`false`（硬编码）** | ~~`evolution_skill.py:2258`~~ ⇒ **`AAWindowCollector.gate_status()` 内硬编码（`evolution_skill.py:2628`）与 `report()` 内硬编码（`:2855`）；同处 `"shadow": True` 见 `:2627` / `:2856`**（**【t3 更正，2026-09-25】** O-4 行号漂移：t1/G-2 与 t3/F4 的插入先后落在 `:2258` 之上，该引用早已失效；按本节「行号口径」，行号随版本漂移，**引用时以符号名 `gate_status()` / `report()` 为准**） |

### 8.2 t4 新发现（**独立观察，非 SP5-A 缺陷，需派单**）

**发现 1 —— 磁盘上的 A/A 报告是"测试伪影"，且测试会覆写它。**

* `test_m4d2_aa_gate.py` 中 6 个用例调用 `AAWindowCollector.report()`；`report()` **无条件落盘**到 `SKILL_DIR / "fitness_aa_report.json"`（`evolution_skill.py:2263-2267`），而 `SKILL_DIR = Path(__file__).resolve().parent`（`:135`）⇒ **写进仓库的 `fly64/skills/`**。
* t4 实测复现：跑 `pytest tests/test_m4d2_aa_gate.py`（11 passed）后该文件 mtime 被重写，内容为**合成 25 窗**（`delta_stats` 恒 0.05、`std 0.0`、`bootstrap B=200`、`min_windows_required=20`）。
* **后果**：任何**真实**标定数据都会被随后的测试运行**静默覆盖**；反之，任何读者（含收口人）会把它读成「已有 25 个真实 A/A 窗」。
* **建议**（SP5-B / 收口派单）：① 测试用 `tmp_path` 或 monkeypatch `SKILL_DIR` 的落盘路径；② 报告写入目标改为 `artifacts/` 或加 `"synthetic": true` 标记；③ 在 SP4 报告中已声明「25 = 演示数据」，但**磁盘文件本身没有该标记**。

> **【t1 更正（2026-09-25）—— 本发现的机制已闭合，上述「报告可被测试覆写」已为假】**
> * `report()` 的落盘目标现为**可注入**且**默认指向 `artifacts/fitness_aa_report.json`**（`AA_REPORT_PATH`，本批次实测 `evolution_skill.py:213`；解析处 `_resolve_report_path` `:2784`），并**拒写源码树 `fly64/skills/`**（`_persist_blocked_reason`，`:2792`）⇒ 不再是「无条件落盘到 `SKILL_DIR`」。
> * `test_m4d2_aa_gate.py` 中的 `report()` 调用（**本轮实测 4 处**）现已**逐个显式传入 `tmp_path` 目标**（该文件头部即写明这一隔离契约）⇒ 「跑测试覆写仓库报告」的副作用已不存在。
> * 此外 `report()` **拒写样本未满（n < min_windows）**的数据，并在**规范路径**（`artifacts/`）上**拒收非 `runtime_aa_windows` 来源**的数据，落盘自带 `data_source` / `format_keys` / `_schema_version` 供识别陈旧写入者（`tests/test_aa_report_integrity.py` 对 F1/F3 逐条钉住；**【本轮实测】** 规范路径未被写入）。
> * **【本轮实测】** `fly64/skills/fitness_aa_report.json` **不存在**、`artifacts/fitness_aa_report.json` **不存在**；旧文件隔离于 `artifacts/aa_wiring/quarantine/`。

**发现 2 —— A/A 收集器在运行时从未被喂数（G4 的真实阻塞点）。**

* `main.py:1491-1496` 确实创建 `EvolutionPipeline(auto_fix=False, window_seconds=120)`；但 `self._aa_window_collector` 在整条 pipeline 中**只有构造、没有任何消费**（无 `record`/`report`/`has_enough` 调用）。
* ⇒ 即使长跑，n 也**恒为 0**；G4 的 `n ≥ 100` **在机制上不可达**，与"等运行时间"无关。
* **建议**：为 `P2-c1/P2-c4` 开工（= G4 通过）单列一张工单：① 把 A/A 窗（无参数变更的等长窗口）接到 `_aa_window_collector.record()`；② 接 `report()` 到非测试路径；③ 补 `aa_two_window_fpr` 的 ≥50 对实测。

> **【t1 更正（2026-09-25）—— 上述「从未被喂数 / 机制上不可达」已为假】**
> 收集器**已接线**：`EvolutionPipeline.run_one_cycle` 调用 `BrainMutator.observe_aa_window`，
> 后者调用 `AAWindowCollector.record` 与 `record_two_window_pair`（本批次实测
> `evolution_skill.py:4115`（调用点）、`:3678`、`:3685`）；
> `aa_gate_status()["wired"]` 由**真实闭窗**派生（`n_windows_runtime_sourced > 0`，`:3727`），
> 静态代码事实另存 `wired_declared`。⇒ **机制阻塞已解除**，`n ≥ 100` 现在**只取决于运行累积时长**。
> **但 `G4` 仍未通过**（真实 n = 0，见 §8.1 与 `sp5a-closure-and-aa-wiring-report.md` §4.3）——
> 这是**本节的既有结论，未变**。

> 上述两点**不在 SP5-A 范围**（SP5-A 不依赖 A/A 门的成效分，规格明确 c2/c3 可与 A/A 累积并行），故**不影响本阶段的交付判定**；但它们直接决定 **SP5-B 能否开工**，必须由 captain 处置。

---

## (9) SP5-B 前置与硬约束

### 9.1 P2-c1 / P2-c4 的开工条件（**G4 尚未满足**）

| 条目 | 前置 | 现状 |
|---|---|---|
| **P2-c1**（升级状态机 + `_vote`→`_vote_all` + `allowed` 契约） | **`G4`（A/A 门）** + `G1` + `G5` + `b1`/`b2` | ❌ **G4 未满足**（真实 n = 0 / 100，且见 §8.2 机制阻塞）；`G1`/`G5` 已通过；`b1`/`b2` 已交付 |
| **P2-c4**（CPG 运动原语竞争槽 · 权威谓词替换） | **P2-c1**（必须先有）+ `P1-b5` 冲突矩阵（`burst > primitive > lif`） | ❌ 依赖 P2-c1；**且规格已预置诚实出口**：若「授予 → 执行」只能靠给 `_lif_motion` 追加 OR 支路 ⇒ **按 t5 §F4 直接判定不可行、从 P2 移除 c4**，只保留「`primitive_granted_count` 恒 0」的观测 + 一条 `medium` finding，**不做折中实现** |
| **M4-d5-b 的验收** | SP5 收口（依赖 `context` 完整性 V15） | ⚠️ 实现已交付（§1.5）；**V15（`context` ≥25 字段且与 `flow.json` 一致）的完整闭合在 BT8，尚未声称通过** |

> 规格明文的顺序强制：「**任何 fitness 变更、任何自动 commit 都不得先于该门通过**」；`c1` 的「无效」定义依赖可分辨成效分 ⇒ **G4 未过时 P2-c1 不得开工**（否则违反 §4.4 与 R6/R12）。

### 9.2 **F6 互锁的输入可用性**（t8 结论）

✅ **可用**：`main.py:2193 model.burst_active = _deadlock_burst_remaining > 0`（**读镜像、非控制写**，不新增 `control.*` 写入点）→ `model.py:2176-2180` 传入 `cx.update(...)` → `central_complex.py:352 _burst_ok = not burst_active` 消费。t8 行为验证：`burst=True` 时**无论** progress/loop 取值**均不触发**环路突破；burst 结束后可触发。**互锁语义已恢复**。

### 9.3 【显著登记】**P2-c1 重构 `_vote` 时的硬约束（否则 t1/t2 成果静默丢失）**

> **⚠️ P2-c1 把 `_vote` 结构替换为 `_vote_all` + `_vote(allowed=...)` 时，必须保留以下两个 keyword-only 参数并在 `_vote_all` 与 `_vote` 两侧继续透传：**
>
> * `surrender_evidence: bool = False` —— **P2-c2（t1）的唯一注入通道**
> * `osc_window: int | None = None` —— **P2-c3（t2）的唯一窗口通道**
>
> **当前落点（实现基准，最终快照 `memory.py ba5c0267eb4c649d`）**：
> * 定义：`memory.py:1503`（`surrender_evidence`）、`:1504`（`osc_window`）—— **均为 `*` 之后的 keyword-only**
> * `_vote` 内消费：`surrender_evidence` → `:1522-1523`（`_detect_wall_stuck` OR 支路）；`osc_window` → `:1519-1520`（`_detect_oscillating(window=...)`）
> * `update()` 形参：`:1545`（`surrender_evidence`）；`update` 内透传：`:1566`（`surrender_evidence=`）、`:1567`（`osc_window=self._osc_window`）
> * 上游注入：`memory.py:2282`（`MemoryController.update` 喂 `surrender_evidence=self._terminal_surrender`）
>
> **判定（C5 PIN）**：`allowed is None` 时 `_vote` 输出必须与基线**逐 tick 相同**；新增两参数为 **keyword-only 追加**，不得改变原有参数的语义或顺序（FALLEN→MICRO_LOOP→OSCILLATING→WALL_STUCK→STUCK_RAMP→IDLE）。
> **风险**：若 `_vote_all` 拆分时漏掉这两项，`_detect_wall_stuck` 的 OR 支路与 P2-c3 的自适应窗会**静默回退到默认值**（`surrender_evidence=False` / `osc_window=None`）—— **没有任何测试会红**，能力静默消失。这条已由 t2/t3 两次独立登记。

---

## (10) V14 待真机复验（真引擎回放 ≥1 个 `high`，离线无法闭合）

| 项 | 内容 |
|---|---|
| **V14 判据** | 真引擎回放命中 `high` 级 pattern **≥ 1**（基线 **0 个 high**，只有 medium+low） |
| **当前可证的边界** | **生产者链可达性已证**：`flow.json["terminal_surrender"]` → `DataCollector.get_metrics()` → `DiagnosisEngine` ⇒ `terminal_surrender_stuck`（`severity: high`）。即「键有生产者、pattern 可被匹配」**已离线证毕** |
| **仍不可离线闭合的部分** | **真引擎回放本身**：需要报告故障快照（t2 §2.2 的 `anomaly_state="stuck_ramp"` run）的真实回放。**H1/H2 证据边界**：该快照在 HEAD 上不可复现（H2），且 `memory.json` / `.cache` 仍不存在（H5/H6/H11）；E-4 的图形值（`stuck_score=1.0`、`stuck_duration=1100.72`、`reflex_active=False`、`median_speed=0.0`、`disp_60s=1080.7`）属**检测伪影**，**不得**用作阈值或证据 |
| **处置** | 已**登记为 BT8 真机复验项**（SP5 收口时执行）。**SP5-A 不声称 V14 通过**；规格原文 `V14（真引擎回放 ≥1 个 high）` 与 V17 合并验收，落在 BT8 |
| **V14 的归属连带** | `M4-d5-a`（键生产者）+ `M4-d5-b` / `P2-c2`（pattern）—— **生产者侧**由 SP5-A 闭合；**真机侧**归 BT8 |

---

## (11) 已完成且无需重新验证的前序交付物清单（SP1–SP4，**已扣除 D1/D2 返修部分**）

### SP1（M3 观测与口径）

| ID | 名称 | 状态 |
|---|---|---|
| P0-a2 / P0-a3 | 真实 `stuck_duration` 重建（P2-c2 的输入依赖） | ✅ 无需复验 |
| P0-a4 | `ParamAuthority` 租约 / 快照 | ✅ 无需复验 |
| P0-a5 ≡ M4-d3 | 观测落盘（`context` 块） | ⚠️ **框架已完成**；V15 完整闭合（≥25 字段且与 `flow.json` 一致）**归 BT8** |
| P0-a6 ≡ M4-d4 | 存活告警 | ✅ 无需复验 |
| P0-a7 | 时序感知 | ✅ 无需复验（`main.py:49-50` 不改，no-op 登记） |

### SP2（P0-a8 + 区间不变式）

| ID | 名称 | 状态 |
|---|---|---|
| P0-a8 | 区间不变式 + 三项迁移（**G1**） | ✅ 39/39 `clamp(live)==live` 通过，无需复验 |
| M4-d5-d | 避险触发实现（SP2 落地） | ✅ **已闭合**（R1，选项 A：拒绝 + `reject_reason`；`test_instinct_bindings` 2 failed → **38 passed**，t2 实现 / t3·t6 复验） |

### SP3（P1，M1 脑侧自适应面）

| ID | 名称 | 状态 |
|---|---|---|
| P1-b1 | 增益链（**G3** 位精确门 4/4） | ✅ 无需复验 |
| P1-b2 | 跳池稳态 homeostat（16/16） | ✅ 无需复验 |
| P1-b3 | 门归一化（`test_gate_units` 15/15） | ✅ 无需复验 |
| P1-b4 | CX 死写入修复（V7 写读一致） | ✅ 无需复验 |
| **P1-b5** | **CX 环路突破** | ⚠️ **曾经退回**：D2 非预期回归 ⇒ **t7 返修 / t8 复验闭合**（§5.1）；**连同新增的 `test_cx_loop_break_gate.py`（15–16 项）一起视为已重新验证** |
| P1-b6 | 死代码清理（5 子项） | ✅ 无需复验 |

### SP4（M4 闭环输出面）

| ID | 名称 | 状态 |
|---|---|---|
| **M4-d1** | T3 门禁 + 运行时守卫 + 静态断言（**G6** / V20） | ⚠️ **曾经欠交**：`fix_guard.is_py_patch` 不存在、门内联（**规格偏差、无漂移**） ⇒ **t7 返修（5/5）/ t8 复验闭合**（§5.2）。**4 条 low 残留（R2/R3/R4）已于本轮 done** ⇒ G6 的字面契约不再被残留阻塞（安全语义此前即成立） |
| M4-d2 | A/A 零假设门 + fitness 五段修复 | ⚠️ **框架 11/11 通过**；**但**：① `G4` 未过（真实 n = 0，见 §8）；② 自动 commit 未接线；③ **报告文件可被测试覆写**（§8.2 发现 1）⇒ 不列入"无需重新验证"（**【t1 更正】③ 的副作用已闭合：报告目标改注入式且默认落 `artifacts/`、源码树拒写、测试逐个传 `tmp_path`，见 §8.2 发现 1 更正块；本行「不列入」判定不变**） |
| M4-d5-a | `_check()` 缺失键惩罚修复 | ✅ 无需复验 |
| M4-d5-c | `has_fix()` 生命周期 | ✅ 无需复验 |
| M4-d5-f | coach 参数日志 | ✅ 无需复验 |
| **M4-d5-d** | 本能晋升边界与责任链 | ✅ **已闭合**（R1，选项 A：拒绝 + `reject_reason`；见 §6 回填列） |

> **说明**：以上"无需重新验证"仅指 **SP5-A 未触碰其代码路径**。`P1-b5`、`M4-d1`、`M4-d5-d`、`M4-d2` 四项例外，原因已在表内逐条注明。

---

## (12) 交付判定汇总

| 维度 | 判定 | 依据 |
|---|---|---|
| **P2-c2**（终态判据 + OR 支路 + 四机制前置解锁） | ✅ **通过** | V17 由 t3 独立复核通过、t6/t8 无回退；纯观测层（AST + 运行期追踪双证）；C1 = 0 |
| **P2-c3**（检测窗） | ⚠️ **机制完成，能力为空操作（R5 已回退）** | 见 §3；`OSC_ADAPTIVE_ENABLED=False`、W 恒 30、0/6000 判定差、medium 记录已写 |
| **M4-d5-b**（pattern + 脑侧响应） | ✅ **通过（实现层）** | 新 pattern `severity: high`、键有生产者、脑侧解锁为搜索面 |
| **V17** | ✅ **通过** | 终态 True / 正常段 False / 边界单调 / 缺输入 False / AST 仅读 `_stuck_duration_true` |
| **V18** | ⚠️ **部分** | ①(稳定) ③(占比 0%) 达成；**①(W≈110) 不可达 ⇒ 按 R5 回退为固定窗 + 只记录**；②（可标定）机制在位 |
| **V14** | 🔶 **待真机复验（BT8）** | 生产者链已证；真引擎回放受 H1/H2 边界阻塞（§10） |
| **V20 / G6** | ✅ **安全语义通过；字面契约的 low 残留已清零** | 0 条 `.py` 执行、同 helper、令牌不放行（独立复现）；**R2/R3/R4 均已 done**（§6 回填列） |
| **F1 / F2 / F3 / F4** | ✅ **全部闭合** | t6 逐项复验 + t8 无回退 |
| **D1（M4-d1，medium）** | ✅ **处置完成（5/5）** | t7 实施、t8 复验 |
| **D2（P1-b5，high）** | ✅ **闭合** | t7 修复、t8 复验（含独立反证 + 7 场景差分矩阵） |
| **C1 / C3 / C5 / C6** | ✅ 全通过 | 五次复验一致 |
| **回归** | ✅ **零新增** | t8 全量 37 failed（34 预存/环境 + 2 R1 + 1 flaky；**其中 2 × R1 已于本轮闭合，见 §6 回填列；全量套件本轮未重跑**）；t4 复算核心面 73 passed；本轮相关回归集 **292 passed / exit 0** |
| **R1（medium）** | ✅ **已闭合（选项 A：拒绝 + `reject_reason`）** | 越界候选**不钳位、不晋升**、记结构化原因；`test_instinct_bindings` **2 failed → 38 passed**；NEG 探针 `stored_params={'turn_bias': 0.8}` **未被改写为 0.25**、`reason=out_of_registry_interval`；POS 探针正当路径未破（t2 实现 / t3·t6 独立复验） |
| **G4** | ❌ **未满足** | 真实 n = 0 / 100（§8） |
| **H5 / H6 / H11** | 🔶 **未关闭** | `memory.json` / `.cache` 仍不存在 |
| **阈值标定（T_s/L/W/D、T_alt、W、0.6、45 s、1500 tick）** | 🔶 **全部【待标定】** | 规格初值（§7） |

> ## ✅ **最终判定：SP5-A 可正式交付；SP5-B 有条件开工**
>
> **SP5-A 本体**（P2-c2 终态判据 + 四机制前置解锁、P2-c3 检测窗/R5 回退、M4-d5-b pattern + 脑侧响应）**验收通过、可交付**：
> * 闭环完整且**未包装**：t3（needs_revision）→ t5（返修）→ t6（needs_revision，**由前序偏差触发**）→ t7（前序返修）→ **t8（verdict=pass）**；
> * F1–F4 全闭合、D1 5/5、D2 闭合、失败集**只减不增**、快照 14 文件哈希**开始=结束**、零 SP5-A 引起的失败。
>
> **必须带到收口的未闭合项**（均已登记，不阻断 SP5-B 施工）：
> * **R1（medium）**：D4 **已闭合**（选项 A：拒绝 + `reject_reason`；2 failed → 38 passed）—— t4 收口时已关闭，不再列为未闭合项；
> * R2/R3/R4/R5（low）：**全部 done**（改动位置见 §6 回填列）；
> * **V14 真机复验**、**V15 `context` 完整性**、**G6 的 low 残留（R2/R3/R4）—— 已全部 done**；
> * **G4 未过** + **A/A 收集器未被喂数 / 报告可被测试覆写**（§8.2，需派单）；**【t1 更正】后两项的机制均已解除**（收集器已接线 / 报告拒写源码树且默认落 `artifacts/`，见 §8.2 两个更正块）；**`G4` 未过不变**；
> * 阈值全部【待标定】、H5/H6/H11 未关闭。
>
> **SP5-B 开工条件**：**`P2-c1` 必须等 `G4` 通过**（当前不满足；**【t1 更正】§8.2 的「机制上未接线」已解除，未满足的原因现为「尚无运行累积」，`G4` 未过的结论不变**）；`P2-c4` 依赖 `P2-c1`，并保留规格预置的「移除 c4」诚实出口。**F6 互锁输入已可用**（§9.2）。**P2-c1 重构 `_vote` 时必须保留 `surrender_evidence` 与 `osc_window` 两个 keyword-only 参数**（§9.3，`memory.py:1503-1504`，透传 `:1519-1520`/`:1522-1523`/`:1566-1567`，上游 `:2282`）。

---

## 附录 A：证据脚本与可复跑命令

| 来源 | 路径 | 内容 |
|---|---|---|
| t3 | `.tmp/t3_verify/` | `v18_real_replay.py`、`v18_addendum_noop.py`、`v17_replay.py`、`v17_ast_independent.py`、`main_publish_key_audit.py`、`pattern_key_producers.py`、`e4_labelling.py`、`c1_and_waste.py`、`findingA_impact.py`、`full_suite.txt`、`hashes.py` |
| t5 | `.tmp/t5_verify/f4_attribute.py` | HEAD↔工作树失败逐项归因 |
| t6 | `.tmp/t6_verify/` | F1 终局判据（flow 真实 / memory `{}` ⇒ 非 None）、F2 差分（HEAD `memory.py` 抽模块 4 序列 0 差分） |
| t8 | `.tmp/t8_verify/` | `p1b5_differential.py`、`v20_token_lock.py`、`degraded_path_check.py`、`end_hashes.py`、`full_suite.txt`、`t7_output.md` |
| t4（本报告） | `.tmp/t4_scan_spec.py`、`.tmp/t4_aa_scope.py`、`.tmp/task_outputs_sp5a.md` | 规格定位、A/A 接线范围核查、任务报告全文归档 |

**复跑（固定 TMPDIR 规避 Windows Temp 权限导致的假 exit 1）**：

```powershell
cd fly64
$env:TMPDIR="$PWD/../.tmp/t4_tmp"
python -m pytest tests/test_terminal_surrender.py tests/test_oscillation_window.py `
                 tests/test_cx_loop_break.py tests/test_cx_loop_break_gate.py -q      # 73 passed
python -m pytest tests/test_evolution_fix_contract.py tests/test_gate_units.py -q     # 48 passed
python -m pytest tests/test_terminal_surrender.py tests/test_oscillation_window.py `
                 tests/test_cx_loop_break.py tests/test_cx_loop_break_gate.py `
                 tests/test_evolution_fix_contract.py tests/test_gate_units.py -q     # 121 passed, exit 0
python -m pytest tests/test_instinct_bindings.py -q                                   # 38 passed（R1 已闭合；t8 时曾为 2 failed）
python -m pytest tests/test_m4d2_aa_gate.py -q                                        # 11 passed；**【t1 更正】不再覆写任何仓库文件** —— 旧注释「但会覆写 fitness_aa_report.json」已为假：report() 目标可注入且默认落 artifacts/、测试逐个显式传 tmp_path、源码树拒写（见 §8.2 发现 1 更正块）
```

---

*报告生成: sp5a-integrator · SP5-A→SP5-B 交接 · Team fly64-sp5a-execution · task t4 · 依赖闭环 t1→t2→t3→t5→t6→t7→t8*
