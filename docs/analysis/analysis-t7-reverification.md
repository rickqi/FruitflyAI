# t7 复验报告：返修后方案报告的 F1–F12 闭合性与无回归核验

> **复验人**: verifier（team `fly64-autonomy-evolution`）· 任务 `t7` · attempt `6963667e-ba7a-455f-b024-e957c8bf3bea`
> **复验对象**: `docs/analysis/fly64-autonomy-evolution-plan.md`（t6 返修后：150 048 B / 1090 行，含新增 §4.7 与 §15）
> **对照基线**: `docs/analysis/analysis-t5-adversarial-verification.md`（t5，1 blocker + 1 high + 4 medium + 6 low）
> **基线代码**: `git rev-parse HEAD` = `cca66648a204043d881da502cf996b15882ad289`（未变）
> **verdict**: **pass** —— F1–F12 **全部闭合**，且 t5 已通过项**无回归**。
> 附 4 个新发现（F13 medium + F14–F17 low），**均不重开 F1–F12**，属实施前需并入变更清单的补充项。

---

## 0. 结论摘要

| 项 | 结论 |
|---|---|
| **F1（blocker）** | ✅ **闭合**。越界事实重算成立（`3.082271242248696 > 3.0`）；**等效换算表 12 个数字全部逐位复现**；**方向已纠正**（r=0.75 在实测 `forward_rate∈{0.033,0.043}` 下 **放宽 1.24×/1.62×**，在 0.008 处放宽 6.67×）；**迁移项存在且算术成立**（0.75×0.043 = 0.03225 ≤ 0.04）；**区间不变式在迁移后满足**（`clamp(live)==live` 39/39；`min<live<max` 仅剩 2 个 `default==max` 例外，与方案声明**逐个一致**）；**V6 可满足**（下界 0.1% = 6 tick 可达；上界 5% 与 0.8 s 不应期推出的 2.5% 占空比上限自洽）。 |
| **F2（high）** | ✅ **闭合**。归一化写法在标称点**逐位相同**（`np.array_equal` 为 True、最大差 0.0）；未归一化版本最大差 0.7123、均值比 1.5000（即 t5 指控的 +50%）；位精确回归断言已列为 V4① 硬前置。 |
| **F3–F12** | ✅ **10/10 闭合**（逐项见 §3）。 |
| **无回归** | ✅ **8/8 无回归**（逐项见 §4）。 |
| **新增** | F13（medium，语义翻转的变更集不完整）+ F14/F15/F16/F17（low）——见 §5。 |
| **可交付性** | **可交付**（作为实施基线）。§5 的 F13 是唯一影响落地可行性的项，须并入 P0-a8/P1-b3 的变更清单；F14–F17 为文本/断言精修。 |

---

## 1. F1（blocker）独立复算 —— 不接受文字表述

### 1.1 越界事实仍成立（capitan 问 (1)）

```
python .tmp/t7_verify_f1f2.py
active_strategy.json:8  gate_jump_threshold = 3.082271242248696
  g_live > 3.0  -> True      # 原 [0.25, 3.0] 越界，t5 指控成立
  g_live > 4.0  -> False     # t6 把上界抬到 4.0，过渡期不再被静默钳位
  clamp_old = min(3.0, max(0.25, g_live)) = 3.0                    # 旧方案：静默收紧
  clamp_new = min(4.0, max(0.25, g_live)) = 3.082271242248696      # 新方案：不被改写
  migration target 0.75 inside [0.25, 4.0] -> True
```

### 1.2 等效换算表：**方向确实已纠正**（captain 问 (2)(a)）

`r_eq(fwd) = 0.04 / max(fwd, 0.008)`，新门 `jump_rate > 0.75 · max(fwd, 0.008)`：

| `forward_rate` | `r_eq`（方案值） | 我复算 | 新门要求（方案值） | 我复算 | 神经元/20（方案值） | 我复算 | 相对旧门（方案值） | 我复算 |
|---|---|---|---|---|---|---|---|---|
| 0.008 | 5.00 | **5.0000** | 0.0060 | **0.00600** | 0.120 | **0.120** | 放宽 6.7× | **6.67×** |
| 0.0330 | 1.21 | **1.2121** | 0.0248 | **0.02475** | 0.495 | **0.495** | 放宽 1.6× | **1.62×** |
| 0.0430 | 0.93 | **0.9302** | 0.0323 | **0.03225** | 0.645 | **0.645** | 放宽 1.24× | **1.24×** |
| 0.1000 | 0.40 | **0.4000** | 0.0750 | **0.07500** | 1.500 | **1.500** | 收紧 1.9× | **1.88×** |
| 0.3000 | 0.13 | **0.1333** | 0.2250 | **0.22500** | 4.500 | **4.500** | 收紧 5.6× | **5.62×** |

沿用线上旧值 `3.082`（t5 的原始指控）：

```
fwd=0.0330: jump_rate > 0.1017 = 2.03/20 neurons = 2.54x TIGHTER
fwd=0.0430: jump_rate > 0.1325 = 2.65/20 neurons = 3.31x TIGHTER      # 与 t5 的 2.5–3.2× 同量级
```

**判定**：① 表内 12 个数字**全部复现**（唯一差异是"1.9×""5.6×"的舍入，我得到 1.88×/5.62×，量级一致）；
② **方向问题的答案**：在**只把上界抬到 4.0、不做迁移**时，门仍然**严 2.54–3.31×**（不是放宽）——
方案自己明确写了这一点（§4.7 取舍 1："单靠它只能让线上值不被静默钳位，不能修正语义"），**没有把 max=4.0 冒充成方向修复**；
③ 真正让方向变正确的是**迁移到 0.75**（放宽 1.24–6.67×），而方案把它列为 P0-a8 的必做项，并在 §5.3 回退里写了
"迁移项失败 ⇒ **不切换语义**（保持 Hz）…**不得**带着 3.082 的越界值进入比值语义"。⇒ **F1 的核心矛盾已解决，且没有靠话术掩盖。**

### 1.3 迁移项算术（captain 问 (2)(b)）

`0.75 × 0.043 = 0.03225 ≤ 0.04`（我复算 0.03225；方案写 0.032）⇒ 迁移后新门**严于/等于旧门**的要求被满足，
且该值同时满足新注册区间 `0.25 < 0.75 < 4.0`。⇒ **成立**。

### 1.4 区间不变式（captain 问 (3)）—— 对 39 个 pid 全量审计，非只看 :5/:8

```
python .tmp/t7_verify_f1f2.py     # 审计
python .tmp/t7_verify_invariant.py # 迁移后不变式
```

| 审计项 | 我的结果 | 方案声明 | 一致性 |
|---|---|---|---|
| 注册 pid 数 | 39（39/39 有线上活值） | 39/39 有活值 | ✅ |
| 落在注册区间**外**的 pid | **1**：`exploration.bold_explore_stuck_s = 60.0`（注册 `[1,10]`） | "只有 2 个（越界 + 钉界）" | ✅ |
| **钉在注册上界**的 pid | **1**：`exploration.turn_bias = 0.25`（注册 max 0.25） | 同上（这正是第 2 个） | ✅ |
| 钉在下界的 pid | 0 | —（未声明） | ✅ 不冲突 |
| `clamp(live) != live`（迁移前） | **1**：`bold_explore_stuck_s` 60.0→10.0 | 方案要求迁移 `:5`→10.0 | ✅ |
| `clamp(live) != live`（迁移后） | **0 / 39** | P0-a8 判据 ⑥ "39/39 通过" | ✅ **可达成** |
| `default == max`（严格式恒不成立）的 pid | **2**：`turn_bias`(0.25/0.25)、`bold_explore_stuck_s`(10.0/10.0) | 方案"独立核查新增"列举的正是这 2 个 | ✅ |
| 迁移后严格式 `min<live<max` 的失败项 | **2 个，且全部被方案的例外条款覆盖**（`EXCEPTION-OK`） | 方案：例外退化为 `min<live≤max` | ✅ |

**判定**：`min<live<max` 硬断言**已对全部 39 个 pid 生效**（:5 与 :8 是其中的成员，不是仅这两个）；
`:8` 这个 t5 指出的"漏列同族反例"已被显式纳入（§4.7 + §7.1 T1 反例清单 + V21 + R11 + §14-D(j)），
且在迁移后对 `:5`/`:8` 都满足（`1.0 < 10.0 ≤ 10.0`、`0.25 < 0.75 < 4.0`）。
**另**：我独立运行了 **方案自己给的复现命令**（§14-C 的区间自查），输出 `OUT count = 1`（`bold_explore_stuck_s`），
与方案声明一致 ⇒ 方案提供的自查命令**可用且结论正确**。

### 1.5 V6 可满足性（captain 问 (4)）

- 新形式：`占空比 ∈ [0.1%, 5%]`（6000 tick，**排除 burst 窗口**），基线 `0/6000 = 0.0%`。
- **下界可达性**：0.1% × 6000 = **6 tick**；即便 burst 占 200/500（40%）、有效窗 3600 tick，下界 = **3.6 tick ≈ 4 次触发**——与"每 0.8 s（40 tick）不应期"下的最稀疏触发完全相容 ⇒ **可满足**（原方案"门限 6000 tick 内真/假都出现"在 `min(3.0,·)` 钳位下实际不可满足）。
- **上界自洽性**：若门恒开，`last_jump >= 0.8 s` 使占空比上限 = 1/40 = **2.5% < 5%** ⇒ 上界不会与不应期冲突。
- **与 burst 的统计冲突**已被 F6 处置（V6 窗口排除 burst）⇒ 原"burst 期间 `control.jump=False` 污染假阴性"的隐患消除。

---

## 2. F2（high）独立复算

```
python .tmp/t7_verify_f1f2.py
nominal gain                    = 1.5
gain/nominal (float32)          = 1.0
array_equal(today, normalized)  = True            # 位精确等价
max |today - normalized|        = 0.0
max |today - UNnormalized|      = 0.7123457193374634   (mean factor = 1.5000)
0.35/1.5 = 0.2333333333333333
gain=0.5  -> leg weight 0.11667      gain=1.5 -> 0.35000      gain=2.5 -> 0.58333
```

- **首 tick +50% 已消除**：新式 `mbon·0.35·(gain/1.5)` 在标称点与旧式 `mbon·mbon_gain_jump`（0.35）**逐位相同**（`array_equal=True`，最大差 0.0，20 万样本 float32）。
- **未归一化版本确为 1.5×**（均值比 1.5000、最大绝对差 0.7123）⇒ t5 的 F2 指控被独立确证，修法有效。
- `0.35/1.5 = 0.2333333333333333`，与方案引用的"0.2333…"一致；方案选择"实现内除以 nominal"因而 **V4 比例（2.29×/0.286×）、§14-A 增益链表（0.07749/0.23247/0.38746）、注册项 {0.35,0.10,0.80} 三处无需改动**——我核对了 §14-A 的重新标注（`gain/nominal = 1/3 → 0.07749`、`1 → 0.23247`、`5/3 → 0.38746`），**与归一化公式自洽**（`leg_mean = 0.35·mean|mbon3| = 0.23247`）。
- **位精确回归断言**已写为 V4① 的**必须先过项**（`np.array_equal` 非 `approx`），并在 §5.1 失败回退里写明"① 失败 ⇒ 立即回滚 §5.1 并区块化（不允许进入 A/B）"。
- 残留依赖：`model.py` 顶部 import 需加入 `DEFAULT_GAINS`（方案已写明），且 `_jump_leg_nominal_gain` 取常量而非复制数字（已写明"从 `gain_modulation` 导入常量，不复制数字"）✅。

---

## 3. F3–F12 逐项闭合核验

| F | 严重度 | 修法是否落地 | 我的独立核验证据 | 闭合判定 |
|---|---|---|---|---|
| **F3** | medium | ✅ | §7.1 已重写：判据 = `f.fix_files ∪ parse_fix_template(f.fix_template)` 的全部 `directive["file"]`；**并在唯一写盘点 `FixExecutor.execute` 加同一 helper 的运行时守卫**（未持批准令牌 ⇒ `manual_action_needed=True` + 零写盘）；静态断言降为**第三道（防回归）**；门禁插点 `evolution_skill.py:2644` 之后 / `FixExecutor` 调用 `:2655` 之前（行号核对无误）；`fix_executor.py:438/469/487/488/603-609` 全部核对为真（模板内 `# File:` 优先、`fix_files` 仅回退）。legacy 结论见 F14（结论成立、证据行不准）。 | **闭合** |
| **F4** | medium | ✅ | §6.4 改为"**权威谓词替换**"：`authority ∈ {lif, primitive}`，`main.py:2521` 的 `_lif_motion` 与 `:2529` 的取权分支改读 `authority`，原表达式**移动**而非追加 OR；执行落点仍是既有 `control = cpg_apply_phase(control, cpg_phase)`（`main.py:2530`，我核对为真）⇒ **不新增 `control.*` 赋值位置**；并明确"若只能用 OR 支路 ⇒ 判本项不可行并从 P2 移除，不做折中"。静态断言设计有一处需精修（见 F16）。 | **闭合** |
| **F5** | medium | ✅ | §7.2 拆成 F5-①~④：门 `bootstrap_upper95(P95) ≤ σ_floor` 与 commit 阈值 `max(0.03, k·P95_noise)`（k ≥ 2）**脱钩**；样本 **n ≥ 100** + bootstrap（B=2000）**置信上界**判据；原"≤10%"降为次要一致性检查（≤5%）；双窗 FPR **实测**（≥50 对，`aa_two_window_fpr ≤ 1%`，明写"不得按 0.05² 估计"）；补齐"噪声降不下来 ⇒ 逐维 `unmeasurable` 移出搜索空间（含降级顺序 meta_channel→…→net_disp_rate）⇒ 轨迹项也不可分辨则判 H13 不成立、P2/P3 阻塞"。V9/V11/R6/R12 同步更新。方案自身接受"未声明 FPR/功效的检验不接受"。 | **闭合** |
| **F6** | medium | ✅ | §5.5 新增互锁（`burst_active` 为抑制前置，取 `main.py:2075` 已有的 `_deadlock_burst_remaining > 0` 信号，**不新增 `control.*` 写入点/门限**）；新增 `cx_loop_break_count_burst_off` + `deadlock_burst_count` 并要求时间戳集合**不相交**；给出 **4 条冲突矩阵**（burst↔§5.3/§5.5/§6.4、§5.3↔§6.4）逐对裁决（权威优先级 `burst > primitive > lif`）；V8 改为可归因形式；**并写明条件 ④ 失败 ⇒ 明确放弃归因**（V8 降为非归因观测、§5.5 判未通过，"不得用 burst 的行为冒充 CX 的功劳"）。我核对 `main.py:2075` `if _deadlock_burst_remaining > 0:` 与 `:2082` `control.jump = False` 均存在且语义相符。 | **闭合** |
| **F7** | low | ✅ | §4.5 改为"**不扫描注册表**（扫描 8 个工件，含 `active_strategy.json` 的 47 键），报 **38** 条 `unreferenced w=0 r=0 decl=0`；全仓合计 unreferenced **85** 行、`TOTAL dead-writes + silent-defaults: 8`（t5 §1.5 独立复现）"。我 t5 的计数（38/85/8）与之一致；V3 与 §14-C 措辞同步。 | **闭合** |
| **F8** | low | ✅ | §3/§7.5-c 改为"未回滚 **11** 条 ⇒ 按 `has_fix()` 判据 **11** 个 `pattern_id`；按实际被关闭的 pattern 计 **10** 个（`telemetry_gap` 不是 pattern）"。**我独立复算：11 个 distinct pattern_id，其中 10 个在 `default_patterns.json`，不在的那个正是 `telemetry_gap`** ⇒ 两个口径都对。 | **闭合** |
| **F9** | low | ✅ | §5.4 已改名 **`MultiSourceGoalCompetition`**（`central_complex.py:178`），注明实例 `cx._goal_comp`（`:369`）与读取端（`:198` 的 `self.steering_gain`、`:297` 的 `getattr(self,'_loop_break_stuck_s',…)`）。我核对类名与行号全部为真，且全仓无 `GoalComparator`。 | **闭合** |
| **F10** | low | ✅ | §5.2 常量默认统一为 **0.15**（与注册项 `{default:0.15}` 与"精确算术"段一致），并显式标注"唯一权威默认值 = 0.15"；比值改写为 **"0.13 × threshold（1.0）" = "0.31 × GAIN_MIN 腿的 v_ss（0.4275）"**（我复算 0.13127/1.0 = 0.13127、/0.4275 = 0.3070 ⇒ 两式都对）。 | **闭合** |
| **F11** | low | ✅ | ① §5.1/§14-A 改为三分口径（脚本字面量 `jump_pool = 20` / 直接测量 `forward·turn·visual·recurrent` / t5 §1.3 独立复算）——与我 t5 §1.3 的实测（1536/60/80/20/2400, n=4096）一致；② §2.5 与 §9.1(P0.1) 同步为"**无 `-60/-69`**；正侧 `60`×1、`69`×7（8/6000）⇒ 不构成群"——与我复算逐位一致；③ §5.3 该句已补"（H6，需真实连接组确认）"。 | **闭合** |
| **F12** | low | ✅ | ① §3 改为"**分属 §4（P0）、§5（P1）、§7（P2）**"并补 11 项→落点对照表（S19+泄放→P0-a2、S33→P0-a1+P1-b3、S12/S13→P1-b4、`lr_adapt`/`_kc_activity`/`_last_burst_tick`→P1-b6、`bold_explore_stuck_s`→P0-a8、SKILL 版本→P0-a7、`position_unchanged_30s`+`has_fix`→P2-d3）；② §7.5-f 统一为 **`source`**（明细写到 `{"ts","key","from","to","source":"self-heal"}`，直写记 `source="coach-direct"`，**不新增 `owner` 字段**，`ParamAuthority` 的 `owner` 仅内部租约记账）。 | **闭合** |

**A/B 分类一致性（回归项之一）**：§3 的 A 类**仍是 11 项**（与 t3 A1–A11 一一对应），B1–B5 一字未变；第 11 项内部的计数文字按 F8 修正为 11/10，**未改变分类本身**。✅

---

## 4. 无回归核验

| 回归项 | 结论 | 证据 |
|---|---|---|
| 主因判定与排序（M3→M1→M2，M4 并行） | ✅ 未变 | §3、§1.1/§1.2 摘要表一致 |
| 主因的 t1/t2/t3 证据引用 | ✅ 未变 | `model.py:2282,2283,2478`；`memory.py:1361-1373,1319-1321`；`memory.py:135,206-217,223` ← `main.py:2650`；`evolution_skill.py:2460/2505/2325-2326` 全部仍为 HEAD 真值（t5 已核，本轮抽查未改） |
| **无新增 `control.*` 写入点** | ✅ 成立 | 全文 grep `control.(x\|y\|jump)\s*=` 的命中全部是**既有代码引用**（`main.py:2081-2082` burst、`fix_0013`、`main.py:2521,2530`）或"保留/统计排除"的裁决，**无一条是新增写入点**；T1/T2 输出面仍是参数/增益空间 |
| 未把主因写成控制层/反射层 | ✅ 未变 | §9.2 七层继承/否定表逐字保留（层 4/6 仍为"否定"） |
| 仍否定原报告 P0.1/P0.2/P0.3/P1.1 且说明技术前提错误 | ✅ 未变且更精确 | §9.1 的 P0.1 行保留"技术前提错误（`model.py:2478` 对 `anomaly_state` 无依赖）+ 反射层从未取得操纵权"，并把 F11② 的 ±60/±69 修正同步进来；P0.2/P0.3/P1.1 行未见删改 |
| H1–H14 全部登记、无假设被当断言 | ✅ 未变 | §13 的 15 行（H1–H9 + H1' + H10–H14）逐行核对存在；H13 仍写成"若不过门 ⇒ P2/P3 阻塞"的**待测门**而非已验证前提（§7.2 F5-④ 进一步明确） |
| 版本边界 H1 合规 | ✅ 未变 | §0.1 三条硬边界逐字保留；本轮新增事实（F1/F2 复算）全部来自 HEAD 代码与可读工件，无越界断言 |
| 伪影引用纪律 | ✅ 未变 | §2.6 的引用纪律段与 E-4 标注保留；§4.7/§5.1/§5.3 的新增数字均为代码/工件可读量 |
| A 类 11 项 ↔ t3 A1–A11、B1–B5 | ✅ 未变 | §3 对照表；B1–B5 文字与 t3 §6.1 一致 |
| t5 §5 的证据边界 | ✅ 原样继承 | §15 明写"无 `memory.json` / 无 `.cache` / 66-68 未复现 / `DiagnosisEngine` 回放未重跑"，并声明"不越界" |

---

## 5. 新发现（F13–F17；**不重开 F1–F12**）

### F13 — medium · 语义翻转（Hz→比值）的变更集不完整，按方案清单实施会留下红灯测试与自相矛盾的契约

- **问题**：§5.3④ / §4.7 列出的落点只有 `brain_tunable_params.json`、`model.py:2478`、`main.py`（热重载 + 3064）。
  我全仓扫描 `gate_jump_threshold`，发现**另有 4 类工件把该 pid 钉在 Hz 语义上**，方案未列入变更集：
  1. `fly64/tests/test_gate_units.py`（5 处引用，13 个测试；下列断言**已逐行核对**）：
     · `test_thresholds_are_calibrated_against_the_decoder_not_the_test`：`:223 assert float(jmp["default"]) > refs["jump_event_hz"]`（要求 **default > 2.0**，新 default 0.75 ⇒ **失败**）、
       `:225 assert float(jmp["min"]) >= refs["jump_event_hz"]`（要求 **min ≥ 2.0**，新 min 0.25 ⇒ **失败**）、`:214` 固定 `jump_event_hz == 2.0`；
     · `test_schema_declares_hz_with_a_reachable_range`：`:182 assert "Hz" in meta["description"]`、`:183 assert "RULE-19" in meta["description"]` ⇒ 改成 `ratio (dimensionless)` 后**失败**（其余 `0.0<lo<=dflt<=hi`、`hi<=NYQUIST` 在新区间下成立）；
     · `test_schema_description_names_both_sides_of_the_comparison`：`:195 assert "每-tick" in desc`、`:196 assert "1/dt" in desc`、`:197 assert "telemetry.py" in desc` ⇒ 纯比值描述下**失败**；
     · `test_register_marks_both_gate_pids_implemented_in_hz`：`:390 assert any("implemented" in ln and "Hz" in ln for ln in rows)`（读 `docs/declared-not-implemented.md`）⇒ **失败**；
     · `test_gates_compare_hz_against_hz_and_republish_the_threshold_unit`（`:256-268`）与 `test_no_per_tick_rate_is_compared_against_a_hz_threshold`（`:277-290`、`:294-295` 断言字面量）以"main.py 在 Hz 上比较"为前件。
  2. `fly64/contract_registry.json`（5 处）：`"threshold_unit": "Hz — skills/brain_tunable_params.json: gate_forward_threshold 0.4..8.0 default 2.0; gate_jump_threshold 2.0..20.0 default 8.0 (maxima kept below Nyquist …)"`
     ⇒ 翻转后与实现直接矛盾（R3"单一口径"在**文档层**被打破）。
  3. `fly64/docs/declared-not-implemented.md:49`（2 处）：声明该 pid 以 **Hz、`2.0..20.0`、default `8.0`** 实现。
  4. `fly64/scripts/verify_motor_pools.py:1011`（4 处）：断言"…**NOT the same unit** as `gate_jump_threshold_hz`" ⇒ 与新语义冲突。
     另 `tests/test_strategy_key_contract.py`（20 处）与 `tests/test_cross_section_keys.py`（2 处）以 `3.082271242248696`/`3.08` 作夹具值，需一并复核。
- **影响**：不补这些，P1-b3 落地时 **测试套件变红**（这与方案自身把 `--history-check` 红灯列为 R8"阻断级"的标准不一致），
  且契约注册表/文档仍宣称 Hz ⇒ "统一口径"（§5.3 的核心卖点）在可审计层面不成立。
- **必须修正**：把下列文件加入 §5.3④ / §4.7 的变更集（并同步 §15 的落点列）：
  ① `fly64/tests/test_gate_units.py` —— 重写"Hz 单位契约"类断言为"比值契约"（`unit == "ratio (dimensionless)"`、
  `min/max` 与换算表一致、`jump_rate_ratio` 与实现逐 tick 一致；原 `jump_event_hz/forward_onset_hz` 参照改为"等效换算表的锚点"）；
  ② `fly64/contract_registry.json` 的 `threshold_unit` 与 `rate_gate_group` 说明；③ `fly64/docs/declared-not-implemented.md:49`；
  ④ `fly64/scripts/verify_motor_pools.py:1011` 的"不同单位"断言；⑤ 复核两个 strategy-key 测试的夹具值；
  ⑥ 验收加一条："语义翻转后 `pytest fly64/tests/test_gate_units.py` 全绿 + `contract_registry` 与注册表单位一致"。

### F14 — low · F3 的 legacy 路径证据行不准确（结论仍成立）

- **问题**：§7.1 / §15 写"全仓无启动引用（`grep evolution_agent` 仅命中它自身、`README.md:368`、`skills/skills.md` 与 `contract_registry.json` 的文字引用）"。
  我实测 **≥15 个文件命中**，其中含**代码**（`fly64/skills/neural_viz_skill.py:13`）、`fly64/docs/causal-chain-review.md`、`agent.md`、`session-ses_f381.md`，
  以及 `.agent-teams/archive/*/team.json` 与 `.tmp/a1_themes/questions.json:3101`、`.tmp/sessions_v3_analysis.json:2420` ——
  **后两处是真实的任务派发文本**（"Use the Fly64 evolution agent … The agent is at /root/fly64/skills/evolution_agent.py on WSL …"），
  说明它**历史上被当作工具入口调用过**；`evolution_agent.py:7` 自身也宣传 `python3 -m fly64.skills.evolution_agent [--interval 5] [--auto-fix] …`。
  另：§7.1/§15 描述"`--auto-fix` 分支（`:359-364`）**只打印** 'To apply fix'"，实际 `:357 if args.auto_fix:` → `:358 fix_mgr.record_fix(...)` 写入
  `evolution_fixes.json`（`FIX_LOG = SKILL_DIR/"evolution_fixes.json"`，`:26,252`），**"To apply fix"打印是 `else` 分支（`:361-362`）**。
  最后，§7.1/§15 引 `fix_executor.py:488-489` 取 `directive.get("file","")`，实际该行是 `:487`（`:488` 是 `_resolve_file` 调用）。
- **结论不变**：`evolution_agent.py` **不调用 `FixExecutor`、不写任何 `.py`**（只写 `evolution_fixes.json`），故"不是第三条 `.py` 执行路径"成立；
  且 t5 §5.7 写的路径 `fly64/fly64/evolution_agent.py` 确实不存在 —— **t6 纠正了我的错误，这一点我确认并致谢**。
- **必须修正**：把证据行改为"grep 命中 15+ 处（含 `neural_viz_skill.py` 注释、文档、归档团队状态与 `.tmp` 派发文本），
  但**无任何 `import`/`subprocess` 启动引用**；`--auto-fix` 分支仅把 fix 记入 `evolution_fixes.json`（`FIX_LOG`），
  打印模板的是 else 分支；两处均不调用 `FixExecutor`"；并把 `:488-489` 更正为 `:487-488`。

### F15 — low · P0-a8 的三件套（注册区间 / `:8` 取值 / `model.py:2478` 语义）缺"原子性与顺序"说明

- **问题**：方案只说"迁移失败 ⇒ 不切换语义"，未规定三者（§4.7 的 registry 区间改写 + §5.3 的 `:8` 迁移 + §5.3 的 `model.py:2478` 语义翻转）
  的执行顺序/原子性。我用**只迁移取值而不改区间**的模拟复现了后果：
  此时线上 `gate_jump_threshold = 0.75` 而注册仍是 `[2.0, 20.0]` ⇒ 方案自己的严格不变式
  `min < live < max` **失败（0.75 < 2.0）**，P0-a8 判据 ⑥ 会把 **P1 永久阻断**（`t7_verify_invariant.py` 的对照实验：先按方案改区间则为 `EXCEPTION-OK`，不改区间则为 `UNCOVERED`）。
  另一个方向（先翻转语义、后迁移取值）则会短暂运行在 2.54–3.31× 收紧态。
- **必须修正**：在 §4.7 P0-a8 明确"**三件套必须原子执行**：同一次部署内完成 ① `brain_tunable_params.json` 的
  `{default 0.75, min 0.25, max 4.0}` 与 `unit` 改写 ② `active_strategy.json:8 → 0.75` ③ `model.py:2478` 语义翻转；
  任一缺失则回退到 Hz 语义（保留原门与 `:8` 原值）"，并把它写进 §8 的 P0→P1 门（判据 ⑥ 补一句"三件套必须同时可见"）。

### F16 — low · F4 的静态断言按字面实现会在**未改动的既有代码**上直接失败

- **问题**：§6.4 的断言写"正则检查'`_lif_motion` 定义行**不得含 `or`**'"。但既有代码就是两行 OR：
  `main.py:2521-2522` = `_lif_motion = (abs(control.x) > LIF_MOTION_MIN` / `or abs(control.y) > LIF_MOTION_MIN)`。
  ⇒ 该断言在**任何**改动前即失败（要么造成假阻断，要么迫使改动者去重构一段与需求无关的既有表达式）。
- **必须修正**：把断言目标改为"**不得给运动权威条件新增析取项**"的形式，例如：
  ① 冻结 `authority` 判定所在表达式，断言其析取项数 == 基线值；或② 断言"取权分支读的是 `authority` 单一谓词"
  （`assert re.search(r'if\s+authority\s*==\s*"primitive"', src)`），并保留"新增 `control.` 赋值行数 == 0"的独立断言。

### F17 — low · §8 的阶段判据未与 F3/F5 同步（局部残留旧措辞）

- **问题**：§8 P2 判据 ① 仍写 `aa_p95_abs_delta ≤ 0.03`（V9/R6 已改为 `bootstrap_upper95(P95) ≤ 0.03` 且 n ≥ 100），
  判据 ⑤ 仍写"T3 提案不进入执行路径（**静态断言**）"（§7.1/V20 已明确静态断言是第三道，**运行时守卫**才是决定性的那道）。
- **必须修正**：P2 判据 ① 改为 `bootstrap_upper95(P95) ≤ 0.03`（n ≥ 100 且 `aa_two_window_fpr ≤ 1%`）；
  判据 ⑤ 改为"门禁 + **`FixExecutor.execute` 运行时守卫**（同一 helper）+ 静态断言三层同时成立，且注入用例（`fix_files=[]` + 模板含 `# File: …main.py`）被拦下"。

---

## 6. 对最终交付物的可交付性判断

| 问题 | 判断 |
|---|---|
| 是否可作为**实施基线**交付？ | **可以**。F1（blocker）与 F2（high）已实质闭合且经算术复算证实；F3–F12 全部落地；t5 已通过项无回归；方案自我声明的证据边界未被突破。 |
| 交付前必须补什么？ | **F13**（语义翻转变更集：`test_gate_units.py` / `contract_registry.json` / `docs/declared-not-implemented.md` / `scripts/verify_motor_pools.py` + 两条 strategy-key 测试夹具）——这是唯一可能让 P1-b3 "落地即红灯"的项，建议直接并入 §5.3④/§4.7 的文件清单（一处清单 + 一条验收即可）。 |
| 建议同步精修 | F14（F3 证据行与 `--auto-fix` 分支描述、`:487` 行号）、F15（三件套原子性）、F16（F4 断言形式）、F17（§8 判据措辞）。均为**文本/断言**级别，不改设计。 |
| 是否存在"未闭合的 blocker/high"？ | **不存在**。 |

---

## 7. 证据边界（沿用 t5，未突破）

1. **本机无 `memory.json`**（t5 已递归查找）⇒ E-4 层数值（`stuck_score`/`stuck_duration`/`reflex_active`/`median_speed`/`disp_60s`）仍**无法证实亦无法否证**；本轮只验证"标注纪律"（合规）。
2. **本机无 `.cache` 目录（更无 `.cache/malecns/manifest.json`）** ⇒ 真实连接组不可复现；
   H5/H6/H11 与 §5.1/§5.2 的定量阈值（0.18127、5.517×、增益链表、`jump_intrinsic_max` 标定）**仍不可确认**。
   本轮 F1 的等效换算表只依赖**轨迹运动学量**（`forward_rate ∈ {0.033, 0.043}`，H1 边界内）与**算术**，不依赖真实连接组。
3. **F2 的位精确性结论**只在 float32（`np.float32`）路径上成立，与实现中 `_pathway_gains_np` 的 `dtype=np.float32` 一致；
   若实现改用 float64 路径，结论需重算（方案未改该 dtype，故不影响）。
4. 未重跑 `--phase6` / `DiagnosisEngine` 回放（与 t5 相同）；`66/68` 仍未独立复现。
5. 本复验为**只读静态/离线**验证：新增物仅 `.tmp/t7_verify_{f1f2,f8_f13,invariant}.py` 与本报告；未改动任何仓库代码或团队状态。

---

*复验人: verifier · 任务 `t7` · attempt `6963667e-ba7a-455f-b024-e957c8bf3bea` · 全部数值为本机真实命令输出*
