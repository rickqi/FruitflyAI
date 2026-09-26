# Fly64 执行计划（Execution Plan）— 阶段 / 依赖 / 关键路径 / 回退

> **交付物**: `docs/execution/fly64-execution-plan.md`
> **来源方案**: `docs/analysis/fly64-autonomy-evolution-plan.md`（1122 行）
> **文件级变更规格（上游）**: `docs/execution/fly64-change-specs.md`（任务 `t1`；**叶子条目 32 个 / 标题计数 34**，口径见 §0.5）
> **代码基线**: `git rev-parse HEAD` = `cca66648a204043d881da502cf996b15882ad289`，**但施工基线 = 当前工作树**（**含 2 个已修改文件**，见 §0.5 基线完整性声明 —— 本计划与 t1 的全部行号/改前字符串实际上取自工作树）
> **生成者**: phase-planner · 团队 `fly64-exec-plan-gen` · 任务 `t2`（**t4 返修**：F-01..F-09 + H-1/H-2）
> **attempt_id**: `21473782-d741-42f9-90c4-c9ef89028795`
> **本文件的性质**: **施工排期与放行判据**。不引入任何新设计条目、不改动任何 `改前/改后` 文本、不重新标定任何阈值。
> 凡 `t1` 标 `【待标定】` 的取值，本计划只登记**标定入口与批次归属**，不代为断言。

---

## 0. 阅读约定与硬约束（施工前必读）

### 0.1 三层文档的关系（索引）

| 层 | 文件 | 回答什么问题 | 本计划如何使用它 |
|---|---|---|---|
| 判定层 | `docs/analysis/fly64-autonomy-evolution-plan.md` | **为什么**（主因 M1/M2/M3/M4）、**做什么**（§4–§7）、判据 V1–V22（§10）、风险 R1–R13（§11）、假设 H1–H14（§13）、迁移清单 §14-D(j) | 阶段划分依据（§8）、里程碑阈值（§10）、回退条款（§11） |
| 规格层 | `docs/execution/fly64-change-specs.md`（t1） | **改哪一行、改成什么、怎么机检**（**叶子条目 32 个 / 标题计数 34** 的九字段规格；口径见 §0.5）、V 测试落点（§7）、R 阻断逻辑（§8）、批次建议（§9）、Pre-flight（§10） | 条目编号、文件·行号、验证命令、批次基线的**唯一事实源** |
| 执行层 | **本文件** | **按什么顺序做、每步的放行门是什么、失败怎么退** | 六阶段 + 依赖图 + 关键路径 + 回退矩阵 + 验证矩阵 + 前置清单 |

> **行号漂移纪律（继承 t1 §0.1）**：一切定位以 `改前原文` 字符串匹配为准，行号仅作导航。若 `git rev-parse HEAD` ≠ `cca66648a204043d881da502cf996b15882ad289`，**本计划与 t1 的行号必须重核后才可施工**。

### 0.2 全线硬约束（C1–C7 继承 + 本计划追加 P1–P6）

| # | 约束 | 来源 | 机检方式（可无人执行） |
|---|---|---|---|
| **C1** | 不新增任何 `control.x` / `control.y` / `control.jump` 写入点 | 原方案 §0.2 ① | `fly64/tests/test_evolution_fix_contract.py`（新增）静态断言：`git diff -U0` 中新增 `control.*` 赋值行数 = 0 |
| **C2** | M1（P1）全部修复形态只能是"**让已有信号到达**" | 原方案 §0.2 ② | 逐条复核 P1-b1…b6 的 `改后` 属"扩面 / 替换口径 / 加稳态 / 修死写入"之一，无新判定分支 |
| **C3** | **不新增第 5 个 jump 门限**（同 key 替换） | 原方案 §9.3-4 | `grep -n "gate_jump" fly64/skills/brain_tunable_params.json` 恰好 1 个 pid；`grep -c "jump_rate >" fly64/fly64/model.py` 恰好 1 处 |
| **C4** | 每条改动必须带**可判定指标 + 阈值 + 自动回退** | 原方案 §0.2 ④ | t1 每条 ID 的 `V` 与 `R` 字段非空（本计划 §7 验证矩阵反向核对） |
| **C5** | `_vote()` 的优先顺序不得改动 | 原方案 §9.3-1 | PIN：`allowed is None` ⇒ 逐 tick 与基线相同（V13①） |
| **C6** | `raw_x` / `raw_y` / `jump` 的**饱和形式**不得改动（**F-06 口径**：只检饱和形式，不禁止引用行号） | 原方案 §9.3-2 | **四处 `clip(·,±70)` 逐字不变**：`model.py:2282` 的 `clip((forward_rate - 0.008) * 2000.0, 0, 70)`、`:2283` 的 `clip(turn_rate * 1100.0, -70, 70)`、`:2473` 的 `clip(raw_y, 0, 70)`、`:2474` 的 `clip(raw_x, -70, 70)`；**`model.py:2478` 仅允许门限表达式替换**（饱和形式不在该行），且不得新增门限（C3） |
| **C7** | 教练直写控制通道保留但**不进自治输出面** | 原方案 §9.3-6 | `param_authority` 不记录 `main.py:2279-2384` 的写入；`param_history.jsonl` 统一 `source` 字段（`coach-direct` / `safety-guard`），不新增 `owner` |
| **P1（新增）** | **T3 代码补丁不得进入闭环执行路径** | 任务书硬约束 | V20 三道路径：① 门禁 ② `FixExecutor.execute` 运行时守卫 ③ 静态断言；判据覆盖 `fix_files ∪ parse_fix_template(...).file` |
| **P2（新增）** | **主因排序 M3→M1→M2，且 M4 与 M3 并行** | 原方案 §1.1 | 阶段 DAG（§4.1）必须满足：SP2 在 SP3 之前；M4（SP4）与 SP1/SP2 同期启动 |
| **P3（新增）** | 任何引用 `memory.json` 的 **E-4 层数值**（`stuck_score=1.0`、`stuck_duration=1100.72`、`reflex_active=False`、`median_speed=0.0`、`disp_60s=1080.7`）必须标注「**检测伪影**」+「**版本边界 H1**」 | 原方案 §11 R10 | 文档评审级阻断：验收报告与提交信息中出现未标注的 E-4 数值即不合格 |
| **P4（新增）** | 每批次**可独立验证**且**可独立回退**（批次 = 一个 tag） | 本计划 §5 | 批次出口门禁全过才可打 tag；`git revert <tag>` 后基线测试集恢复原状 |
| **P5（新增）** | 未过 `G1`（V21）不得开始 SP3；未过 `G4`（V9）不得开启自动 commit；`R8`/`R9` 未清零不得进入 SP6 | 原方案 §8 + t1 §1.2 | 阶段入口门禁（§3 各阶段"前置门禁"字段 + §4.4） |

### 0.3 证据边界与标注纪律

| 事实（t1 §0.3 继承） | 对本计划的约束 |
|---|---|
| 本机**无 `memory.json`**、**无 `.cache/malecns/manifest.json`** | 真实连接组运行点**不可离线复现**；SP3 的全部数值阈值（`0.18127`、`5.517×`、`fwd_aux_ceiling` 比例）**只能标 `【待标定】`**，不放行→不放行 SP3 上线 |
| `.tmp/fly64_trajectory.json`（6000 点）与 HEAD **不相容** | 只允许引用其**运动学统计**（X 效率 2.75%、Z 效率 5.35%、静止 1385/5999、`jump` 0/6000、`ctrl_x` 满量程 5330/6000），不得用它证明 HEAD 行为 |
| 探针 `FlyModel(demo=True)` 发放退化为 100% | 发放率相关阈值只能证明**算术/接线可达性**（**H5**） |
| 假设 **H5/H6/H11/H12/H13/H14** | **禁止在验收报告中改写为"已确认"**（t1 §0.3 末行）；本计划 §9.3 给出分级 |

### 0.4 术语与状态定义

| 术语 | 定义 |
|---|---|
| **阶段（SP）** | 交付粒度，含 1..n 个批次；SP 之间可有并行关系 |
| **批次（B）** | 提交粒度：一次 `git commit` + 一个 tag `fly64-<sp>-<b>`；**必须能独立验证与独立回退** |
| **硬门（G）** | 不通过即**阻断下游**的判据（G1–G6，见 §1.3） |
| **红灯（R）** | 原方案 §11 的 R8/R9/R11，未清零即阻断特定阶段 |
| **shadow** | 只落盘、不决策（`evolution_log` 同时写 `sim_fitness` 与 `legacy_fitness`） |
| **回退（rollback）** | **参数级 / 开关级**动作（写一个 `active_strategy.json` 有界值、置一个开关、恢复一个常量），**不要求改 `.py`**、**不依赖人工在场**（t1 §8.1） |
| **批次（BT）** | **⚠ 命名消歧（F-05）**：本计划一律写作 **`BT0`–`BT9`**（**BT = Batch**）。**绝不要**与源方案 §3 的「**A 类 11 项 / B 类 5 项**」中的 **B 类**（`B1`–`B5` = 自治缺失 5 项：B1 无行为决定变量级作用点、B2 无竞争/升级/回退语义、B3 无可判别适应度、B4 无情景责任链、B5 无自观测）混淆 —— **两者同名异义**。凡本计划出现 `BT#` 即为批次；凡出现 `B1`–`B5`（无 `T`）即为源 §3 的 B 类标签 |

### 0.5 基线完整性声明（**H-1 / H-2，t4 返修新增**）

> **问题**：本计划与 t1 的**全部行号与「改前」字符串**过去被笼统声明为「HEAD `cca66648` 上的行区间」。
> 实测（`git status --porcelain`）：**工作树有 158 项 M/D**，其中 **2 个被引用文件与 HEAD 不一致**。
> ⇒ 笼统的「HEAD 基线」声明**不成立**。以下为 captain 裁定后的**双基线 + 逐文件溯源**。

**基线裁定（按此执行）**：运行时脑（含教练热重载与 `FixExecutor`）消费的是**磁盘上的实际文件**，
故 **操作性基线 = 当前工作树**；但任何引用**必须逐文件标明**其「改前」原文取自 HEAD 还是工作树。

#### 0.5.1 两个不一致文件（必须分别对待）

| 文件 | HEAD（`cca66648`） | 工作树 | 差异 | 引用处置 |
|---|---|---|---|---|
| `fly64/skills/active_strategy.json` | **21 行**（`\n` 计 20）；`exploration` 段全部是**扁平点号键**；`:4 = "exploration.bold_explore_stuck_s": 47.55773365137824`、`:7 = "exploration.gate_jump_threshold": 3.082271242248696`、`:14 = "escape.commit_ticks"`、`__generation: 134`；**无 `turn_bias`、无 `navigation`/`coach`/`memory`/`reflex` 段** | **55 行**；嵌套键：`:4 = "turn_bias": 0.25`、`:5 = "bold_explore_stuck_s": 60.0`、`:8 = "gate_jump_threshold": 3.082271242248696`、`:33-38 = navigation`（`steering_gain 0.12` / `loop_break_stuck_s 45.0`）、`__generation: 332` | **结构性**（键名形态 + 段结构 + 两个值都不同） | **三项迁移 `M1/M2/M3` 与 `P1-b4` 的 `:33-38` 一律标「工作树基线」**，并**同时记录 HEAD 变体**（见下表） |
| `fly64/skills/fix_executor.py` | **862 行**（**采用口径 = 换行符计数 + 无尾换行修正**，见下方「口径定义」）；`def execute(` = **:433**、`directives = parse_fix_template(fix_template)` = **:464**、`file_rel = directive.get("file", "")` = **:483**、`def _resolve_file` = **:598**、`rel = file_rel or (fix_files[0] if fix_files else "")` = **:604** | **867 行**（同口径）；同五个锚点 = **:438 / :469 / :488 / :603 / :609** | 总行数 **862 → 867（+5）**；**五个锚点净偏移一致 = +5**（`:433→:438`、`:464→:469`、`:483→:488`、`:598→:603`、`:604→:609`） | **M4-d1 的四个锚点按所选基线给号**：工作树 = **`:438 / :469 / :488 / :603`**；HEAD = **`:433 / :464 / :483 / :598`**。**守卫必须插在 `execute` 入口**（工作树 `:438` 之后、`parse_fix_template` 调用 `:469` 之前），锚点错位即插错位置 |

**行数计数口径定义（唯一，两文档逐字一致；t7 复核后按字节级实测更正）**

> **采用口径 = 物理行数 = `U+000A` 个数 + (无尾换行 ? 1 : 0)**，等价于 `[IO.File]::ReadAllLines(path).Count` / `wc -l` 的行数语义。
> · **HEAD = 862**（U+000A **861** + 1，**无尾换行**）、**工作树 = 867**（U+000A **866** + 1，**无尾换行**）⇒ **差值 = +5**。
> · 两基线**均无尾换行**（已用字节级读取确认 `endswith(LF) = False`），故两者都需 +1 修正。
> **可复现命令（以字节级为准，二者互相印证）**：
> ```powershell
> # ① 字节级（最可靠，不依赖 PowerShell 的行拆分实现）
> python -c "import subprocess,pathlib; h=subprocess.run(['git','show','HEAD:fly64/skills/fix_executor.py'],capture_output=True).stdout; w=pathlib.Path('fly64/skills/fix_executor.py').read_bytes(); print('HEAD', h.count(b'\n'), '->', h.count(b'\n')+(0 if h.endswith(b'\n') else 1)); print('WT', w.count(b'\n'), '->', w.count(b'\n')+(0 if w.endswith(b'\n') else 1))"
> # 期望：HEAD 861 -> 862 ; WT 866 -> 867
>
> # ② 行数组长度（与 ① 等价）
> [IO.File]::ReadAllLines((Resolve-Path 'fly64/skills/fix_executor.py')).Count                                  # 期望 867
> (git show HEAD:fly64/skills/fix_executor.py).Split("`n").Length                                             # 期望 862
> # ⚠ 不可使用 `Get-Content <path> -split "`n"`：它对无尾换行文件少计 1 行（实测 WT 得 866），属实现差异
> ```
> **易混口径对照（供复核者识别历史数字来源，**本计划不采用**）**：
> | 口径 | HEAD | 工作树 | 说明 |
> |---|---|---|---|
> | **物理行数（**采用**）** = `U+000A` + 无尾换行修正 | **862** | **867** | `ReadAllLines().Count` / `wc -l` 行数语义 |
> | 仅数 `U+000A`（不加尾修正） | 861 | 866 | 若按此口径，两基线**同时** −1；t6 一度误用此口径 ⇒ 工作树误写 866 |
> | 非空行计数（`Measure-Object -Line`） | 746 | 751 | 旧稿「746 / 751」即此口径 ⇒ **不可作为行号基线** |
> | `Get-Content <path> -split "\`n"` | 862 | 866 | PowerShell 对无尾换行文件的拆分差异（工作树少 1） |
> ⇒ 「746 / 751」与 t6 短暂的「866」分别来自上表第三、四行口径，属**口径混淆**（该错误源自 captain 的早期指导 + 我 t6 的过度更正）；**事实值为 862 / 867**，本计划如实标注为口径问题。

**偏移构成（本机逐区域字节级实测，t7 复核后更正）**：**region1（`def execute` 之前）= 432 → 437 ⇒ +5**；**region2（`execute` .. `_resolve_file`−1）= 165 → 165 ⇒ +0**（**逐字节相同**）；**region3（`_resolve_file` .. 文件末尾）= 264 → 264 ⇒ +0**（**逐字节相同**）⇒ **总行数 +5**、**五锚点累计 +5**（`:433→:438`、`:464→:469`、`:483→:488`、`:598→:603`、`:604→:609`）。新增的 5 行**全部落在 `def execute` 之前**（`if extracted_file:` 卫语句 + 4 行注释）。复现命令：
```powershell
python -c "import subprocess,pathlib; h=subprocess.run(['git','show','HEAD:fly64/skills/fix_executor.py'],capture_output=True).stdout.split(b'\n'); w=pathlib.Path('fly64/skills/fix_executor.py').read_bytes().split(b'\n'); f=lambda L,p:[i for i,l in enumerate(L,1) if p in l][0]; he,hr=f(h,b'def execute('),f(h,b'def _resolve_file'); we,wr=f(w,b'def execute('),f(w,b'def _resolve_file'); print('r1',he-1,we-1,we-he); print('r2',hr-he,wr-we,(wr-we)-(hr-he)); print('r3',len(h)-hr,len(w)-wr,(len(w)-wr)-(len(h)-hr)); print('total',len(h),len(w),len(w)-len(h))"
# 期望：r1 432 437 +5 ; r2 165 165 +0 ; r3 264 264 +0 ; total 862 867 +5
```

**总计说明（取代旧稿的"约 120 行"）**：工作树相对 HEAD 的**总行数差为 +5**（**物理行 862 → 867**；`U+000A` 口径 **861 → 866**），且**全部增量都在 `def execute` 之前**。旧稿「工作树共比 HEAD 多约 120 行」以及中间版本自称的「+4 / +1+4−1」**均为错误表述，已作废**（正确值为 **+5，三段分解 +5 / 0 / 0**）。复现命令：
```powershell
git status --short fly64/skills/fix_executor.py
git show HEAD:fly64/skills/fix_executor.py | Select-String 'def execute\(|parse_fix_template\(fix_template\)|file_rel = directive|def _resolve_file|rel = file_rel or'
Select-String -Path fly64/skills/fix_executor.py -Pattern 'def execute\(|parse_fix_template\(fix_template\)|file_rel = directive|def _resolve_file|rel = file_rel or'
```

#### 0.5.2 `active_strategy.json` 的三项迁移：工作树基线 + HEAD 变体（**双记录**）

| 迁移 | 工作树基线（**操作性**，`改前` 字符串取此） | HEAD 变体（`cca66648`） | 说明 |
|---|---|---|---|
| `M1` `exploration.bold_explore_stuck_s` | `fly64/skills/active_strategy.json:5`：`    "bold_explore_stuck_s": 60.0,` | `:4`：`    "exploration.bold_explore_stuck_s": 47.55773365137824,`（**值不同**，**键名是扁平点号**） | 两值**都越界**注册 `[1, 10]` ⇒ 静默钳位结论**不变** |
| `M2` `exploration.gate_jump_threshold` | `:8`：`    "gate_jump_threshold": 3.082271242248696,` | `:7`：`    "exploration.gate_jump_threshold": 3.082271242248696,`（**行号不同**，**键名扁平**） | 值相同 ⇒ 算术越界结论不变 |
| `M3` `exploration.turn_bias` | `:4`：`    "turn_bias": 0.25,` | **该键在 HEAD 不存在**（HEAD 只有别名 `:3 "bold_turn_bias": 0.25` + 扁平点号键） | **HEAD 上 `_expl.get("turn_bias")` 命不中** ⇒ 该迁移在 HEAD 上**必须同时做键名归一化**（P1-3 / EVO-072 的同一族工作） |
| `P1-b4` 来源 | `:33-38` 的 `navigation` 段（`steering_gain 0.12` / `loop_break_stuck_s 45.0`） | **HEAD 无 `navigation` 段** | 同上 |

> **从干净 HEAD 开工的前置（必须写明）**：若施工起点是干净 `cca66648`，则 **`M1`/`M2`/`M3` 的「改前」字符串在该文件中不存在**（无 `turn_bias`、无 `bold_explore_stuck_s`、无 `gate_jump_threshold`，只有带 `exploration.` 前缀的扁平点号键）⇒ 必须**先建立嵌套键格式**（键名归一化）再执行三项迁移；本计划的 **操作性基线因此固定为工作树**，并在 §9.1 用**内容自证（行数 + 关键键值 + 锚点行号）**而非「工作树干净」来自证（**不采用内容哈希**）。

#### 0.5.3 逐文件基线来源表（15 个一致文件 = 两者等价）

| 文件的「改前」原文来源 | 文件 |
|---|---|
| **工作树基线（HEAD 与工作树内容一致，`git status` 为 clean，两者等价）** | `fly64/fly64/main.py`、`fly64/fly64/model.py`、`fly64/fly64/memory.py`、`fly64/fly64/central_complex.py`、`fly64/fly64/gain_modulation.py`、`fly64/fly64/mushroom_body.py`、`fly64/fly64/instinct_bindings.py`、`fly64/fly64/motor_primitives.py`、`fly64/skills/evolution_skill.py`、`fly64/skills/brain_tunable_params.json`、`fly64/skills/default_patterns.json`、`fly64/skills/evolution_history.json`、`fly64/contract_registry.json`、`fly64/tests/test_gate_units.py`、`fly64/tests/test_tunable_wiring.py`、`fly64/plugin/scene_context.py`、`fly64/plugin/coach_outcomes.py` |
| **工作树基线（与 HEAD 不一致 ⇒ 必须双记录，见 §0.5.1/§0.5.2）** | `fly64/skills/active_strategy.json`、`fly64/skills/fix_executor.py` |
| **另有 dirty 但仅作数据引用（非「改前」行号锚点）** | `fly64/skills/fix_catalog.json`（`M4-d5-c` / `M4-d1` 的计数引用） |

**证据命令（凡引用行号处均以此复现）**：
```powershell
git rev-parse HEAD                                    # cca66648a204043d881da502cf996b15882ad289
git status --porcelain                                # 判定 clean / dirty
git status --short fly64/skills/active_strategy.json  # 期望 'M'
git show HEAD:fly64/skills/active_strategy.json       # HEAD 变体（21 行、扁平点号键）
Get-Content fly64/skills/active_strategy.json         # 工作树（55 行、嵌套键）
```

---

## 1. 执行摘要

### 1.1 一句话结论

把 **32 个文件级条目**（叶子；标题计数 34，含 P1-b6、M4-d5 两个容器）组织为 **6 个实施阶段、10 个提交批次**：先用 SP1/SP2（P0-a，M3 观测与口径）**切断伪影链并冻结口径**——这一步**不改变任何行为**，是唯一的破环点；SP3（P1，M1 脑侧自适应面）是**唯一改变行为的阶段**，其全长受 `G1`（区间不变式 39/39）与 `G5`（新增 `control.*` = 0）双重夹持；SP4（M4 闭环）作为**并行轨道**贯穿全程，其 `G4`（A/A 零假设门）是 SP5-B 与 SP6 的**前置硬门**；SP5（P2，M2 仲裁）中的 c2/c3 可与 SP4 并行、c1/c4 必须等 `G4`；SP6（P3 自治运行）只在 `R8`/`R9`/`R11` 三条红灯全部清零后开启。关键路径 **SP1(a2→a4) → SP2(a8) → SP3(b1/b2/b3) → SP4(d2·A/A 门) → SP5-B(c1/c4) → SP6**，总工作量 **20.0–32.5 人·日**。

### 1.2 六阶段总览

| 阶段 | 名称（主因） | 阶段目标（一句可判定） | 包含条目 | 前置阶段 | 里程碑验证（§10 V + 阈值） | 工作量（人·日） | 风险 |
|---|---|---|---|---|---|---|---|
| **SP1** | P0-a · 冻结与观测/口径层（**M3**，不改行为） | 6000 tick 内 `stuck_score` 不再恒 1.0（≥3 个不同取值），且 `--history-check` 退出码为 0 | `P0-a1, a2, a3, a4, a5(=M4-d3 框架), a6(=M4-d4), a7(=M4-d5-e)` | — | **V1**（≥3 取值；基线恒 1.0）、**V2**（≤5%；>20% 回退）、**V3**（A/B 覆盖率 100%）、**V15**（`context` ≥25 字段，**框架**）、**V16**（≤120 s 告警）、**V19**（PASS） | 3.0–5.0 | 中 |
| **SP2** | P0-b · 语义迁移与区间不变式（**M3 硬门**） | `clamp(live) == live` 对 39/39 pid 逐位通过，且 `active_strategy.json:8` 已迁移为 0.75 | `P0-a8` + 迁移 `M1/M2/M3`（t1 §6） | SP1（a1、a4） | **V21**（39/39；`default==max` 两例外走 `min<live≤max`）、**V6**（迁移前提）、**V22**（契约前提） | 1.0–1.5 | **高** |
| **SP3** | P1 · 脑侧自适应作用面（**M1**，唯一改行为） | `ctrl.jump` 占空比落在 `[0.1%, 5%]`，且新增 `control.*` 写入点为 0 | `P1-b1, b2, b3, b4, b5, b6`（含 `b6-1..b6-5`） | **SP2**（G1）+ SP1（G2） | **V4**（位精确先行 + 2.29×/0.286×）、**V5**（非零 ≥5% 且 P95 ≤0.20）、**V6**（`[0.1%,5%]`）、**V7**（≤1200 tick，`mismatch=0`）、**V8**（burst-off ≥1 且不相交）、**V22**、**V3** 延伸 | 5.0–8.0 | **高** |
| **SP4** | M4 · 闭环输出面与可分辨性（**M4**，与 M3 并行） | `bootstrap_upper95(P95) ≤ 0.03`（n ≥ 100 A/A 窗）且 0 条 `.py` 补丁被执行 | `M4-d1, d2, d5-a, d5-b*, d5-c, d5-d, d5-f`（d3/d4/d5-e 已在 SP1） | 与 SP1/SP2 **并行启动**；d5-d 需 SP2；d5-b 需 SP5-A | **V9**（≤0.03，n ≥ 100；`aa_two_window_fpr ≤ 1%` 实测）、**V10**（≤30%；基线 60.3%）、**V11**（`[5%,30%]`；基线 1.47%）、**V12**（≥1）、**V14**（≥1 个 `high`；基线 0）、**V20**（0 条 `.py`） | 4.0–6.0 | **高** |
| **SP5** | P2 · 仲裁与升级语义（**M2**） | `arbitration.level` 在复现场景升级 ≥1 次且 6000 tick 内升降 ≤2 次，`terminal_surrender` 终态判 true、正常段判 false | `P2-c2, c3`（SP5-A）；`P2-c1, c4`（SP5-B） | SP5-A：SP2 清零；SP5-B：**SP2 + SP3(G5) + SP4(G4)** | **V13**（升级 ≥1、升降 ≤2、level ≤2；PIN `allowed is None` 逐 tick 不变）、**V17**、**V18**（600 tick 翻转 ≤4）、**V14/V20**（G6） | 2.0–4.0 | 中高 |
| **SP6** | P3 · 自治运行与泛化 | 连续 7×24 心跳无断档，且 `effective_count ≥ 1`（首个被证实的改进） | 守护/调度、shadow→auto 切换（≥1 周影子 + 2 个 A/A 窗）、参数空间扩展、跨场景泛化 | **全部前置清零**：`R8`/`R9`/`R11` + `G1/G4/G5/G6` | **V16**（7×24 无断档）、**V12**（`effective_count ≥ 1`）、同一参数在 ≥3 场景符号一致 | 5.0–8.0 | 中 |

`*` `M4-d5-b`（`terminal_surrender_stuck` pattern）依赖 `P2-c2`，故其**验收落在 SP5 收口时**（见 §5 批次 BT8）。
**合计**：**20.0–32.5 人·日**（对账见 §8.1）。

### 1.3 六个硬门（G1–G6）与三条红灯

| 门/灯 | 判据（可机检） | 阻断对象 | 关联 V / R | 放行批次 |
|---|---|---|---|---|
| **G1** | `clamp(live)==live` 对 **39/39** pid 通过；`min<live<max` 对 37 个通过，`default==max` 的 2 个走 `min<live≤max` | **SP3 全部条目不得上线** | V21 / R11 | BT3 |
| **G2** | `P0-a4` 产出 `fly64/skills/param_wiring_ab.json` 且 39 个 pid 均有 `verdict` | SP3 各条无接线判据 ⇒ 不得进入 A/B | V3 / R7 | BT1 |
| **G3** | `P1-b1` **位精确回归**：`_jump_leg_weight=0.35` 且 `gain("jump")==DEFAULT_GAINS["jump"]` ⇒ `v[jump_nodes]` 增量与改动前 float32 `np.array_equal` | 失败即**立即回滚 b1 并区块化**，不得进入 A/B | V4① / R13 邻域 | BT4 |
| **G4** | `M4-d2` **A/A 零假设门**：`bootstrap_upper95(P95) ≤ 0.03`（n ≥ 100 窗）**且** `aa_two_window_fpr ≤ 1%`（≥50 对双窗实测） | **禁止**任何 fitness 变更与自动 commit（保持 shadow）；**SP5-B 与 SP6 的前置硬门** | V9 / R6 / R12 | BT7 |
| **G5** | 新增 `control.*` 写入点 = **0**（静态断言） | SP3 整体不得上线 | C1 / R10 | BT5 |
| **G6** | `M4-d1` 的 T3 门禁 + `FixExecutor.execute` 运行时守卫 + 静态断言三者同 helper、同判据 | **阻断 SP5 上线** | V20 | BT6 |
| **R8（红灯）** | `python -m skills.evolution_skill --history-check` 退出码 ≠ 0 | **闭环不得进入 SP6**；红灯不阻塞诊断 | V19 | BT1 |
| **R9（红灯）** | pattern 自检报 `unreachable`（`position_unchanged_30s` 零生产者） | **阻断 SP6**（pattern 集不完整 ⇒ 责任链不成立） | V14 / R9 | BT6 |
| **R11（红灯）** | 语义翻转 + 越界值共存 ⇒ 静默收紧；**或**任一 pid `clamp(live) != live` | **阻断 SP3 上线** | V21 / V6 | BT3 |

> **顺序强制**：`G4` **先于**任何 fitness 变更与自动 commit；`G1` **先于** SP3 任何条目；`G6` **先于** SP5 上线。

### 1.4 与原方案 §8 的一致性声明

| §8 原文要求 | 本计划的落点 | 一致 |
|---|---|---|
| 关键路径 `P0-a2 → P0-a4 → P1-b1/b2/b3 → P2-d2（A/A 门） → P3-auto` | §4.2 关键路径**逐跳同序**（`P2-d2` 即 `M4-d2`，落在 SP4/BT7）。**F-09 修正（不得再写「逐跳相同」）**：本计划在源 §8 的**同一跳序**上插入了 **2 个额外跳**，属"同序 + 插入"，不是"逐跳相同" ——<br>　 · **插入跳 A（`P0-a4 → P0-a8`）**：源 §8 的关键路径是 `P0-a2 → P0-a4 → P1-b1/b2/b3`，**未含 `P0-a8`**；本计划把 `P0-a8`（区间不变式 + 三项迁移，**G1 硬门**）作为 `P0-a4` 与 `P1-b1/b2/b3` 之间的**必经插入跳**（依据：源 §4.7 的 G1 阻断 P1 上线）<br>　 · **插入跳 B（`SP5-A → SP5-B`）**：源 §8 只有 `P2`（`P2 6–10 人·日`）一个粒度，**未含 SP5-A/SP5-B 的拆分**；本计划把 `P2-c2/c3`（SP5-A，只需 SP2 清零）与 `P2-c1/c4`（SP5-B，需 `G4+G1+G5`）**拆成两个串行跳**（依据：源 §6.1 的失效条款「c1 条件① 失败 ⇒ 回退到 P0/P1 阶段」＋源 §7.2 的 A/A 门顺序强制）<br>　 ⇒ 结论：**跳序一致、门一致，但插入 2 跳**（`BT3=SP2` 与 `BT8=SP5-B`），故 §4.2 的跳数 = 7（源 §8 为 5） | ✅（同序 + 2 处插入，已声明） |
| 并行：M4 的 d1/d3/d4/d5-a–e 与 P0 并行；d2 的 shadow 部分可与 P0 同步上线 | SP4 作为**并行轨道**（§4.1 右侧轨道），BT6/BT7 与 BT1–BT5 同期；d2 只落盘不决策 | ✅ |
| 主因排序 M3 → M1 → M2，M4 与 M3 并行 | SP1/SP2（M3）→ SP3（M1）→ SP5（M2）；SP4（M4）与 SP1/SP2 并行 | ✅ |
| §8 各阶段工作量（P0 3–5 / P1 5–8 / P2 6–10 / P3 5–8，合计 19–31 人·日） | §8.1 逐项对账：SP1+SP2 vs P0、SP4+SP5 vs P2 完全落在区间内；总差 +1.0–1.5 人·日来自 t1 §7 新增的 **18** 个测试文件 | ✅（已披露） |
| §9.3"不改"清单 7 条 | §10.D 逐条重申，并映射到 C1–C7 | ✅ |

---

## 2. 变更规格索引（指向 t1）

### 2.1 32 个叶子条目（标题计数 34）→ t1 章节 → 阶段 → 批次（全表）

| ID（稳定条目号） | t1 章节 | 主文件 | 阶段 | 批次 | 前置 ID |
|---|---|---|---|---|---|
| `P0-a1` | §2 | （无代码；冻结产物） | SP1 | BT0 | — |
| `P0-a2` | §2 | `fly64/fly64/memory.py:133-139,205-209,1985-1995`、`main.py:2647-2650` | SP1 | BT1 | a1 |
| `P0-a3` | §2 | `memory.py:226-229`、`main.py:2687`、`model.py:2096` | SP1 | BT2 | a2 |
| `P0-a4` | §2 | **新增** `skills/param_authority.py`、`evolution_skill.py:2238-2267,1967-1968`、`main.py:1742-1753,1756-1879` | SP1 | BT1 | — |
| `P0-a5`（= `M4-d3`） | §2 / §5 | `evolution_skill.py:2923-2929`、`main.py:3034-3068` | SP1（框架）→ SP5 收口 | BT2 | 键名定名（b1–b5/c1–c4） |
| `P0-a6`（= `M4-d4`） | §2 / §5 | **新增** `skills/evo_funnel_alarm.py`、`main.py:1419-1425` | SP1 | BT1 | — |
| `P0-a7`（= `M4-d5-e`） | §2 / §5 | `evolution_skill.py:42`、`evolution_history.json:3-5`（**注**：`main.py:49-50` 的 `SKILL_VERSION` 已对齐，按 t1 a7③ 标注「**不改**」⇒ **不计入 `main.py` 的修改清单**） | SP1 | BT1 | — |
| `P0-a8` | §2 | `brain_tunable_params.json:38-43`、`active_strategy.json:5,8`（**工作树基线**，见 §0.5.2）、**扩展** `tests/test_tunable_wiring.py`、**`main.py:1678-1881` 热重载段的运行期读回校验**（插在归因段 `:1864-1878` 之后、回写 `:1879` 之前，锚点原文见 t1 a8⑤） | SP2 | BT3 | a1、a4 |
| `P1-b1` | §3 | `model.py:1787,639`、`gain_modulation.py:39-49`、`main.py:1852-1855` | SP3 | BT4 | a4、a5、a8 |
| `P1-b2` | §3 | `model.py:1769-1778,1882-1890,649-652` | SP3 | BT5 | a4、a5、a8、b1 |
| `P1-b3` | §3 | `model.py:2478`、`main.py:2892-2894,2953-2957`、`test_gate_units.py:178-226`、`contract_registry.json:83/98/102` | SP3 | BT5 | a8、a4、a5、c4 冲突矩阵裁决 |
| `P1-b4` | §3 | `main.py:1847-1851`、`central_complex.py:178,191-198,286-306` | SP3 | BT4 | a4、a5 |
| `P1-b5` | §3 | `central_complex.py:286-306`、`model.py:2082-2097`、`main.py:2746-2751` | SP3 | BT5 | b4、a5、a4 |
| `P1-b6-1` | §3 | `mushroom_body.py:350-360,116,394/396`、`main.py`（接线） | SP3 | BT4 | a4、a5 |
| `P1-b6-2` | §3 | `main.py:2693-2699`、`model.py`（写入落点） | SP3 | BT4 | a5 |
| `P1-b6-3` | §3 | `main.py:2062,2063-2066,2082,1447-1448` | SP3 | BT5 | b5、a5 |
| `P1-b6-4` | §3 | `main.py:2883-2957`、`plugin/scene_context.py:115-116,228-235` | SP3 | BT5 | b3 |
| `P1-b6-5` | §3 | `main.py:2358-2384,2279-2323,2330-2348`（**登记项，非改动**：t1 b6-5 判「保留、不进闭环输出面」⇒ **不计入 `main.py` 的修改清单**，但计入条目覆盖的 32） | SP3 | BT5 | —（保留，只登记） |
| `P2-c1` | §4 | **新增** `fly64/fly64/arbitration.py`、`memory.py:1347-1373`、`main.py:2009-2017,2018-2035` | SP5-B | BT8 | **M4-d2**、a5、b1/b2 |
| `P2-c2` | §4 | `memory.py:1319-1321`、`default_patterns.json`、`evolution_skill.py:2570-2580` | SP5-A | BT8 | a2、a3、a5、d5-a |
| `P2-c3` | §4 | `memory.py:1281,1289-1317,1394,1377-1462` | SP5-A | BT8 | a5、a4 |
| `P2-c4` | §4 | `main.py:2521-2530,2438-2511`、`arbitration.py` | SP5-B | BT8 | c1、b5 |
| `M4-d1` | §5 | `evolution_skill.py:2644,2653-2668`、`fix_executor.py:437-443,468,485-488,602-608`、**新增** `fix_guard.py`、`change_proposals.jsonl`、`tests/test_evolution_fix_contract.py` | SP4 | BT6 | — |
| `M4-d2` | §5 | `evolution_skill.py:2460,2499-2505,2490,2532,2238-2267,2325-2326,2019-2036,2119,788-829,2623-2703`、**新增** `fitness_aa_gate.py`、`fitness_aa_report.json` | SP4 | BT7 | a4、a5、c1（`meta_channel`） |
| `M4-d3` | §5 | 同 `P0-a5` | SP1（框架） | BT2 | 键名定名 |
| `M4-d4` | §5 | 同 `P0-a6` | SP1 | BT1 | — |
| `M4-d5-a` | §5 | `default_patterns.json:43-51`、`evolution_skill.py:863-867,1009,1066-1087` | SP4 | BT6 | — |
| `M4-d5-b` | §5 | `default_patterns.json`、`evolution_skill.py:2570-2580` | SP5 收口 | BT8 | c2、d5-a |
| `M4-d5-c` | §5 | `evolution_skill.py:1163-1164,2644,2736-2740`、`fix_catalog.json` | SP4 | BT6 | d4、d1 |
| `M4-d5-d` | §5 | `fly64/fly64/instinct_bindings.py:79,87,257-268,303`、`main.py:1102-1105,1155,1742`、`plugin/coach_outcomes.py:51-66` | SP4 | BT6（验收复验 BT8） | **a8**、a5 |
| `M4-d5-e` | §5 | 同 `P0-a7` | SP1 | BT1 | — |
| `M4-d5-f` | §5 | `main.py:2330-2348,2279-2323,2358-2384,1873-1876` | SP4 | BT6 | a4 |
| 迁移 `M1` | §6 | `active_strategy.json:5`（60.0 → 10.0）**（工作树基线；HEAD 变体 = `:4 "exploration.bold_explore_stuck_s": 47.55773365137824`，见 §0.5.2）** | SP2 | BT3 | a8、a4 |
| 迁移 `M2` | §6 | `active_strategy.json:8`（3.082… → 0.75）**（工作树基线；HEAD 变体 = `:7 "exploration.gate_jump_threshold"`，见 §0.5.2）** | SP2 | BT3 | a8、a4、**b3⑦ 同批** |
| 迁移 `M3` | §6 | **`active_strategy.json:4`**（`turn_bias` 不改值，只登记边界例外）**（工作树基线；HEAD 无该键 ⇒ 若从干净 HEAD 开工须先做键名归一化，见 §0.5.2）** | SP2 | BT3 | a8 |
| `--history-check` 修复 | §2 P0-a7 | `evolution_skill.py:42` = `"3.5.1"` | SP1 | BT1 | — |

**覆盖核对（F-01/F-02 修正后的唯一口径）**：本表共 **32 个叶子条目行** —— `P0-a1..a8`（8）+ `P1-b1,b2,b3,b4,b5`（5）+ `P1-b6-1..b6-5`（5）+ `P2-c1..c4`（4）+ `M4-d1..d5`（5）+ `M4-d5-a..d5-f`（6）= **33 行**，减去 1 行**非条目行**（`--history-check` 修复行，它是 `P0-a7` 的复述，**不重复计数**）⇒ **32 个叶子条目** ✓ 与 t1 §1.1 的叶子 ID 行数一致。
> **口径声明（唯一，不得再混用）**：**叶子条目 32**（= 32 个可施工改法）/ **标题计数 34**（含 `P1-b6`、`M4-d5` 两个**分组容器**，容器本身不是可施工单位）。
> **与本表一致性**：`M1/M2/M3` 三项迁移**不计入 32**（它们是 `P0-a8` 的构成部分，见 t1 §6 与 §0.5.2）。
> **别名（同一改动的多处登记）**：`P0-a5 == M4-d3`、`P0-a6 == M4-d4`、`P0-a7 == M4-d5-e`（t1 明写「同 `P0-a7`」）、`M4-d5-b ≡ P2-c2`（新 pattern 的默认集与响应面）。**这 4 对是"同一改动的两侧登记"，不是 4 个额外条目** —— 本表的 32 行**已按"每个改法只计一次"写出**（`M4-d3`/`M4-d4`/`M4-d5-e` 三行只在 §2.1 出现一次，不与 `P0-a5/a6/a7` 重复计数）；若按"行数"统计则为 **33 行 − 1 行复述 = 32**。**禁止**再出现"34−2=32"这类把容器与别名混在一起的算式。

---

## 3. 阶段计划（SP1–SP6）

> 每阶段的必填字段：**阶段目标（一句可判定）** / 包含条目 / 前置阶段与门禁 / 内部批次 / 里程碑验证 / 上线门禁 / 回退策略 / 工作量 / 风险 / 交付物。

### SP1 · P0-a 冻结与观测/口径层（M3，**不改行为**）

| 字段 | 内容 |
|---|---|
| **目标（可判定）** | 在 6000 tick 复现窗内 `stuck_score` 取值集合 `len(set(...)) ≥ 3`（基线恒 `1.0`），且 `python -m skills.evolution_skill --history-check` 退出码 = **0**（基线 FAIL/exit 1） |
| **包含条目** | `P0-a1`（口径冻结）、`a2`（伪影链切断）、`a3`（真实卡死时长）、`a4`（运行时 A/B + 授权点）、`a5`= `M4-d3`（`context` 落盘**框架**）、`a6`= `M4-d4`（存活自检 + 漏斗告警）、`a7`= `M4-d5-e`（版本三元组） |
| **前置阶段** | 无（BT0 即为本阶段第一批） |
| **内部批次** | **BT0** `a1`；**BT1** `a2, a4, a6, a7`（四条互不依赖，可并行）；**BT2** `a3, a5`（`a3` 依赖 `a2`；`a5` 只落"字段定名 + 落盘框架"，取值等 SP3/SP5 的键齐备） |
| **里程碑验证** | `V1` ≥3 取值（基线恒 1.0）· `V2` 与轨迹运动学差 ≤5%（>20% ⇒ 回退 `a2`）· `V3` 39 个 pid 100% 有 A/B 判定 · `V15` `context` ≥25 字段（**框架**；完整版在 SP5 收口） · `V16` 杀进程后 ≤120 s 置 `evo_loop_stale=true` · `V19` PASS |
| **上线门禁** | `G2`（`param_wiring_ab.json` 含 39 个 `verdict`）；**`V1` 未达标 ⇒ 阻塞 SP3 全部条目**（进 `G1a`）；`V2` 差 >20% ⇒ 自动复原 `rate_threshold=5.0` 与 `memory.py:1993-1995` 原块 |
| **回退策略** | 见 §6.1-SP1（R10 / R7 / R8 / R9 四条；回退 = 参数级 + 开关级，**行为与 HEAD 逐 tick 相同**，因为本阶段不改行为） |
| **工作量** | 3.0–5.0 人·日（含 `a1` 冻结 0.5） |
| **风险** | **中**（观测层不改变行为，风险集中在"改了观测却没改对"⇒ 由 V1/V2/V19 三个可判定指标兜底） |
| **交付物** | `param_authority.py`、`evo_funnel_alarm.py`、`.evo_loop_heartbeat.json`、`param_wiring_ab.json`、`memory.json["clamped_keys"]`（落点）、`evolution_history.json` 新记录、`SKILL_VERSION="3.5.1"` |

### SP2 · P0-b 语义迁移与区间不变式（**M3 硬门，串行**）

| 字段 | 内容 |
|---|---|
| **目标（可判定）** | `clamp(live) == live` 对 **39/39** 注册 pid 逐位通过，且 `active_strategy.json` 的 `gate_jump_threshold == 0.75`、`bold_explore_stuck_s ∈ [1, 10]` |
| **包含条目** | `P0-a8`（注册上界 3.0→4.0 + `unit` 字段 + 启动自检 `assert_registry_live_interval_ok`）+ 三项迁移 `M1`（60.0→10.0）、`M2`（3.082…→0.75）、`M3`（`turn_bias` 只登记边界例外） |
| **前置阶段** | SP1（`a1` 口径冻结、`a4` 授权点可用）；**迁移必须经 `P0-a4` 授权点写入**，不得手工编辑后提交 |
| **内部批次** | **BT3（串行，唯一批次）**：区间上界与 `unit` → 启动自检断言 → 三项迁移（经授权点）→ 迁移后机检三条 |
| **里程碑验证** | **`V21`** 主判据 39/39 + 严格判据 37 个 `min<live<max` + `default==max` 的 2 个（`exploration.turn_bias` `(0.0,0.25,0.25)`、`exploration.bold_explore_stuck_s` `(1.0,10.0,10.0)`）走 `min<live≤max`；**`V6`** 迁移前提（迁移未做 ⇒ 占空比恒 0）；**`V22`** 契约前提 |
| **上线门禁** | **`G1`**：断言失败即**阻断 SP3 全部条目**（这是 `P0-a8` 的验收）；迁移后 6000 tick 内 `memory.json["clamped_keys"]` 必须为空 |
| **回退策略** | 见 §6.1-SP2（**R11 + R13**：迁移项失败 ⇒ **保持语义在 Hz（不切比值）**，把 `P1-b3` 标记为**未上线**；`active_strategy.json` 用 `.bak.<ts>` 参数级还原；**不得带着 3.082 的越界值进入比值语义**） |
| **工作量** | 1.0–1.5 人·日 |
| **风险** | **高**（语义翻转 + 越界值共存的静默收紧；且该阶段的错误**不会**在 SP2 自身暴露，只会让 SP3 的门恒假） |
| **交付物** | `brain_tunable_params.json:38-43` 新形态、`active_strategy.json` 三项值、`tests/test_tunable_wiring.py` 扩展断言、`tests/test_gate_units.py` 的 ratio 契约**前提**（完整迁移在 BT5）、`memory.json["clamped_keys"]` |
| **迁移前备份（强制）** | `Copy-Item fly64/skills/active_strategy.json fly64/skills/active_strategy.json.bak.<ts>`，备份路径写进提交信息 |

### SP3 · P1 脑侧自适应作用面（**M1，唯一改行为**）

| 字段 | 内容 |
|---|---|
| **目标（可判定）** | 在 6000 tick（排除 burst 窗口）内 `ctrl.jump` 占空比 ∈ `[0.1%, 5%]`（基线 `0/6000 = 0.0%`），且 `git diff -U0` 的新增 `control.*` 赋值行数 = **0** |
| **包含条目** | `P1-b1`（MBON→jump 增益链）、`b2`（跳池自稳态 + 固有兴奋性腿）、`b3`（`jump_rate` 门归一化 + RULE-19 契约同批迁移）、`b4`（两处 CX 死写入）、`b5`（CX 环路突破可达化）、`b6-1..b6-5`（死代码清理五子项） |
| **前置阶段** | **SP2（`G1`）** + SP1（`G2`、`a5` 观测键落盘） |
| **内部批次** | **BT4**：`b1`（**先跑位精确回归 `G3`**）、`b4`、`b6-1`、`b6-2`（`b4` 与 `b1` 可并行；`b6-1`/`b6-2` 与 `b1` 并行）；**BT5**：`b2`、`b3`（依赖 BT3 的迁移）、`b5`（依赖 `b4`）、`b6-3`（依赖 `b5`）、`b6-4`（依赖 `b3`）、`b6-5`（只登记） |
| **里程碑验证** | `V4`（① 位精确 **先行**；② `0.35→0.80` 升 ≈2.29×、`0.35→0.10` 降 ≈0.286×）· `V5`（非零 tick 占比 ≥5% 且 P95 ≤0.20）· `V6`（`[0.1%,5%]`，**排除 burst 窗口**；门限 6000 tick 内真/假都出现）· `V7`（≤1200 tick 可见，`param_write_mismatch = 0`）· `V8`（`cx_loop_break_count_burst_off ≥ 1` 且与 `deadlock_burst_count` 时间戳**不相交**）· `V22`（ratio 契约 PIN 全绿）· `V3` 延伸（`b6-1`/`b6-4` 的 A/B） |
| **上线门禁** | **`G3`**（位精确，失败即回滚 `b1` 并区块化）· **`G5`**（新增 `control.*` = 0）· `b1` 的 A/B 双向（升/降）都通过 · `b6-1` 回归前置：`python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q` 记录基线（两处 PIN `mb.lr_adapt == 1.0`） |
| **回退策略** | 见 §6.1-SP3（**R1 · R2 · R13 · G3**；全部为参数级/常量级，不要求改 `.py`） |
| **工作量** | 5.0–8.0 人·日（§8 P1 区间） |
| **风险** | **高**（全计划**唯一改变行为**的阶段；且 `b1`/`b2` 的数值阈值全部依赖真实连接组，属 **H5/H6/H11/H12**） |
| **交付物** | `model.py`（`:1787, :639, 跳池稳态段, `:2478`）、`gain_modulation.py`（`JUMP_GAIN_MAX`）、`central_complex.py`（property + `_no_progress` 门）、`main.py`（接线段/遥测段/写端）、`brain_tunable_params.json`（新 `escape.*` 两项）、`test_gate_units.py` ratio 版、`contract_registry.json`、新增 6 个测试文件（`test_jump_leg_gain_chain.py` 等） |

### SP4 · M4 闭环输出面与可分辨性（**与 M3 并行轨道**）

| 字段 | 内容 |
|---|---|
| **目标（可判定）** | A/A 报告中 `bootstrap_upper95(P95) ≤ 0.03` 且 `n_windows ≥ 100`、`aa_two_window_fpr ≤ 1%`；同时 `.py` 补丁被执行条数 = **0**（全部落 `change_proposals.jsonl`） |
| **包含条目** | `M4-d1`（T1/T2/T3 + T3 降级三道理）、`d2`（五段修复 + A/A 零假设门）、`d5-a`（pattern 键生产者）、`d5-b`（`terminal_surrender_stuck`，**收口在 SP5**）、`d5-c`（`has_fix` 生命周期）、`d5-d`（本能晋升边界，**需 `a8`**）、`d5-f`（教练直写边界）；`d3`/`d4`/`d5-e` 已在 SP1 |
| **前置阶段** | 与 SP1/SP2 **并行启动**（`d3`/`d4`/`d5-e` 与 `a5`/`a6`/`a7` 同落点，不重复实现）；`d5-d` 需 SP2 的 `a8`；`d5-b` 需 SP5-A 的 `c2` |
| **内部批次** | **BT6**：`d1`、`d5-a`、`d5-c`、`d5-f`（`d1` 可与 M4 其他并行）；**BT7**：`d2`（**shadow 先行**，可与 BT1–BT5 **全程并行**，只落盘不决策） |
| **里程碑验证** | `V9`（`bootstrap_upper95(P95) ≤ 0.03`，n ≥ 100；`aa_commit_threshold = max(0.03, 2·P95_noise)` 与门**脱钩**；`aa_two_window_fpr ≤ 1%` **实测**）· `V10`（`delta_exact_zero_rate ≤ 30%`，基线 60.3%）· `V11`（`commit_rate ∈ [5%,30%]`，基线 1.47%）· `V12`（`effective_count ≥ 1`，基线 0）· `V14`（真引擎回放命中 `high` pattern ≥ 1，基线 0）· `V20`（0 条 `.py` 被执行；`fix_files=[]` 但模板含 `# File: …main.py` 的用例必须被拦下） |
| **上线门禁** | **`G4`**（A/A 门：未过 ⇒ 禁止 fitness 变更与自动 commit，保持 shadow）· **`G6`**（T3 门禁 + 运行时守卫同 helper）· **`R9`** 清零（pattern 自检无 `unreachable`）· `R12`（n < 100 或按 `0.05²` 估 FPR ⇒ 不达标不得打开自动 commit） |
| **回退策略** | 见 §6.1-SP4（**R6 · R12 · R9 · R3**；回退后状态 = **保持 shadow**（有 finding、无 commit）；逐维 `unmeasurable` 剔除顺序固定） |
| **工作量** | 4.0–6.0 人·日 |
| **风险** | **高**（若 `net_disp_rate` 亦不可分辨 ⇒ 判 **H13 不成立**，SP5-B 与 SP6 **整体阻塞**） |
| **交付物** | `fix_guard.py`、`fitness_aa_gate.py`、`fitness_aa_report.json`、`change_proposals.jsonl`、`evolution_skill.py`（fitness 五段 + `has_fix` + `_check` 缺键告警）、`default_patterns.json`、`instinct_bindings.py`、新增 8 个测试文件 |

### SP5 · P2 仲裁与升级语义（**M2**）

| 字段 | 内容 |
|---|---|
| **目标（可判定）** | 复现卡死场景下 `ineffective_ticks > dwell_ticks` 后 `arbitration.level` 从 0 升至 ≥1 且 `upgrade_history` 非空；6000 tick 内 `level` 升降次数 ≤ 2；`terminal_surrender` 在终态回放判 `true`、正常探索段判 `false` |
| **包含条目** | **SP5-A（可与 SP4/SP3 并行，只需 SP2 清零）**：`P2-c2`（`terminal_surrender` + 四机制前置解锁）、`P2-c3`（检测窗自适应）；**SP5-B（必须 `G4` + `G1` + `G5` 全过）**：`P2-c1`（升级状态机 + `_vote_all`/`allowed` 契约）、`P2-c4`（CPG 竞争槽 · 权威谓词替换）；收口：`M4-d5-b`（`terminal_surrender_stuck` pattern） |
| **前置阶段** | SP5-A：SP2 清零 + SP1 的 `a2`/`a3`/`a5` + `d5-a`；SP5-B：**`G4`（A/A 门）** + `G1` + `G5` + `b1`/`b2`（升级对象） |
| **内部批次** | **BT8**：`c2`、`c3`（`c3` 可与 `c1` 并行）、`d5-b`（`c2` 之后）、`c1`、`c4`（`c4` 依赖 `c1` 与 `b5` 冲突矩阵） |
| **里程碑验证** | `V13`（升级 ≥1 次、6000 tick 升降 ≤2、`level ≤ 2`、达 2 后写入数 0；**PIN**：`allowed is None` ⇒ `_vote` 逐 tick 与基线相同）· `V17`（终态 `true`/正常段 `false`；**源码断言**：`terminal_surrender` 求值路径**不出现** `self._stuck_duration`）· `V18`（600 tick 内翻转 ≤4；正常段占比 ≤5%）· `V14`（真引擎回放 ≥1 个 `high`）· `V20`（`G6`） |
| **上线门禁** | **`G6`**（`d1` T3 门禁 + 运行时守卫通过）· `c1` 的前置 = `M4-d2` 的成效分**可分辨**（未达 ⇒ 回退到 SP1/SP3，不得进入 SP6）· `c4`：若"授予 → 执行"只能靠给 `_lif_motion` 追加 OR 支路 ⇒ **按 t5 §F4 直接判定不可行，从 P2 移除 c4**，只保留 `primitive_granted_count` 恒 0 的观测 + 一条 `medium` finding，**不做折中实现** |
| **回退策略** | 见 §6.1-SP5（**R4 · R5 · R3 · F4 判不可行**；回退后状态 = 状态机停用但**只读遥测保留**） |
| **工作量** | 2.0–4.0 人·日 |
| **风险** | **中高**（`c1` 的接口语义是"该阶段最大返工点"；`c4` 有明确的"不可行 ⇒ 移除"通道） |

### SP6 · P3 自治运行与泛化

| 字段 | 内容 |
|---|---|
| **目标（可判定）** | 连续 7×24 运行期间 `.evo_loop_heartbeat.json` 心跳间隔始终 ≤120 s（无断档），且 `fix_catalog.json` 的 `effective_count ≥ 1`（基线 0） |
| **包含条目** | 闭环守护与调度（计划任务/守护进程）· shadow → auto 切换（**≥1 周影子 + 2 个 A/A 窗**）· 参数空间扩展（仅纳入**已通过 A/B** 的新 `pid`）· 跨场景泛化（本能晋升在边界修好后重新评估） |
| **前置阶段** | **全部前置清零**：`R8`（`V19` PASS）· `R9`（`V14` ≥1）· `R11`（`V21` 39/39）· `G1`/`G4`/`G5`/`G6` 全通过；SP3/SP4/SP5 均已达里程碑 |
| **内部批次** | **BT9**：守护与调度 → 影子观察（≥1 周）→ auto 切换；`M4-d5-e` 已含于 BT1，此处只做复验 |
| **里程碑验证** | `V16`（7×24 无断档）· `V12`（`effective_count ≥ 1`，**首次**产出被证实的改进）· 同一参数在 ≥3 个场景上的符号一致 |
| **上线门禁** | **`R8`/`R9`/`R11` 任一未清零 ⇒ SP6 整体不可开始**；auto 切换前必须满足 `aa_two_window_fpr ≤ 1%` **实测**（R12） |
| **回退策略** | 见 §6.1-SP6（**auto → shadow 回退（参数级开关）**、停用守护、`param_authority_degraded=true`、`arbitration_enabled=false`；**V12 长期为 0 ⇒ 回到 SP3**，说明作用面仍未打通） |
| **工作量** | 5.0–8.0 人·日（§8 P3 区间） |
| **风险** | **中**（不再引入新机制；风险来自"7×24 运行性"与"跨场景泛化"的统计充分性） |

---

## 4. 依赖图与关键路径

### 4.1 阶段 DAG（ASCII）

```
                    ┌────────────────────────── SP4 · M4 闭环（并行轨道，全程） ──────────────────────────┐
                    │  BT6  d1(T1/T2/T3) · d5-a · d5-c · d5-f        d5-d ◀── 需 SP2(G1)                    │
                    │  BT7  d2 shadow（只落盘，不决策）──▶  G4: A/A 门 (V9/V11, n≥100, fpr≤1%)            │
                    │  d3/d4/d5-e 与 SP1 的 a5/a6/a7 是同一落点，不重复实现                              │
                    │  d5-b ◀── 需 SP5-A 的 c2                                                          │
                    └───────────┬───────────────────────────────────────────────┬───────────────────────┘
                                │                                               │ G4(V9) 是 SP5-B / SP6 的前置硬门
                                ▼                                               ▼
SP1 ──────────▶ SP2 ──────────▶ SP3 ──────────────────────▶ SP5-A ──▶ SP5-B ──────────────▶ SP6
P0-a 观测层      P0-b 迁移/不变式  P1 脑侧自适应面(M1)          P2 仲裁(M2)                  P3 自治运行
a1 a2 a3 a4      a8 + M1/M2/M3    b1 b2 b3 b4 b5 b6-1..-5      c2 c3 (并行可行)  c1 c4       守护/shadow→auto
a5 a6 a7         【串行硬门】                                          【需 G4+G1+G5】
   │                  │                    │                          │
   │ G1a: V1          │ G1: V21 39/39      │ G3: b1 位精确             │ G6: V20 (T3 三道理)
   │ G2 : V3          │ （未过 ⇒ 阻断 SP3）│ G5: 新增 control.* = 0    │ V13: 升级≥1 且升降≤2
   └──────────────────┴────────────────────┴──────────────────────────┘
                        ▲                                    ▲
                        │                                    │
                    【M3 = 解锁条件 / 破环点】          【G4(V9) + V13 = P2/P3 前置硬门】
              SP1+SP2 不改变任何行为，只切断伪影链、       未过则保持 shadow：禁止 fitness 变更
              冻结口径、修区间不变式                       与自动 commit，SP5-B/SP6 整体阻塞

红灯（未清零即阻断）：R8 --history-check FAIL（V19）／R9 pattern unreachable（V14）／R11 区间不变式（V21）
                      └────────────── 三灯全清 ⇒ 才可进入 SP6 ──────────────┘
```

### 4.2 关键路径（逐跳可核对，与 §8 完全一致）

| 跳 | 从 | 到 | 依赖类型 | 门 | 说明 |
|---|---|---|---|---|---|
| 1 | `P0-a2` | `P0-a4` | 并行→汇合 | `G1a`（V1）、`G2`（V3） | 两者互不依赖，但都必须先于 SP3；V1 未达标即阻塞 SP3 全部条目 |
| 2 | `P0-a4` | `P0-a8` | **串行** | — | 迁移必须经授权点；`a8` 依赖 `a1`+`a4` |
| 3 | `P0-a8` | `P1-b1/b2/b3` | **串行硬门** | **`G1`（V21 39/39）** | 未过 ⇒ SP3 全部不可上线 |
| 4 | `P1-b1` | `P1-b2/b3` | 串行 | `G3`（位精确先行） | `b2` 的消费点与 `b1` 串联；`b3` 的门与 `b1`/`b2` 的池占用同源 |
| 5 | `P1-b1/b2/b3` | **`M4-d2`（A/A 门）** | **并行→汇合** | **`G4`** | §8 原文的 `P2-d2` 即 `M4-d2`；`d2` 的 shadow 段可与 `P0` 同步上线 |
| 6 | `M4-d2`（`G4` 通过） | `P2-c1/c4` | **串行硬门** | `G4` + `G1` + `G5` | `c1` 的"无效"定义依赖 `d2` 的可分辨成效分 |
| 7 | `P2-c1/c4` | `P3-auto` | 串行 | `R8`/`R9`/`R11` 清零 | 三红灯 + 四硬门 |

**关键路径总长**：`SP1(a2→a4) → SP2(a8) → SP3(b1→b2→b3) → SP4(d2·A/A 门) → SP5-B(c1→c4) → SP6`。

### 4.3 边表（串行 / 并行裁决）

| 边 | 类型 | 判据 |
|---|---|---|
| `a2 ↔ a4 ↔ a6 ↔ a7` | **可并行** | 四条互不依赖（t1 §9 BT1） |
| `a3 → a2` | **必须串行** | `a3` 的真实时长重用 `a2` 的单位契约与泄放修复 |
| `a5 → {b1,b2,b3,b4,b5,c1,c2,c3,c4}` 的**键名** | **必须先行（定名）** | 否则 `context` 字段名与 `flow.json` 漂移（t1 P0-a5 依赖字段） |
| `a8 → b1/b2/b3` | **必须串行** | 新 `pid`（`escape.jump_leg_weight`、`escape.jump_intrinsic_max`）必须过区间不变式 |
| `a8 ↔ d5-d` | **必须串行**（d5-d 验收后移） | 候选值必须落在"注册区间 ∩ 钳位"之内 |
| `b1 ↔ b4` | **可并行** | 不同文件段（`model.py` 增益链 vs `central_complex.py` property）；BT4 同批 |
| `b6-1 / b6-2 ↔ b1` | **可并行** | 不同文件（`mushroom_body.py` / `model.py`） |
| `b4 → b5` | **必须串行** | `b5` 的旋钮 A/B 依赖 `b4` 先生效 |
| `b5 → b6-3` | **必须串行** | `b6-3` 要按 `b5` 的 F6 冲突矩阵四条裁决处置 `main.py:2082` |
| `b3 → b6-4` | **必须串行** | `gate_*` 的"无执行侧消费者"由 `b3` 统一口径后解决 |
| `b3 ↔ c4` | **必须同批裁决** | F6 冲突矩阵第 4 条：primitive 授予期间 `b3` 的门仍照常计算（只读），跳的最终写入者不变 |
| `d1 ↔ d2/d3/d4/d5` | **可并行** | `d1` 只需 `fix_guard` + 门禁/守卫，不依赖 fitness |
| `d2` 的 shadow 段 ↔ SP1/SP2/SP3 | **可并行（全程）** | 只落盘不决策 |
| `d2（G4） → c1/c4` | **必须串行（硬门）** | 未过 ⇒ 禁止 fitness 变更与自动 commit |
| `c2 / c3 ↔ SP4` | **可并行** | 只需 SP2 清零 + `d3`/`d5-a`；不依赖成效分 |
| `c2 → d5-b` | **必须串行** | pattern 条件键 `terminal_surrender` 由 `c2` 生产 |
| `c1 → c4` | **必须串行** | `c4` 的运动权威由 `c1` 的仲裁状态机持有 |

### 4.4 M3 是解锁条件/破环点；A/A 门是 P2/P3 的前置硬门

| 论点 | 依据 | 执行含义 |
|---|---|---|
| **M3 = 破环点** | 原方案 §1.1："**M3 是解锁条件 / 破环点**"；`_vote` 的输入（`stuck_score`/`stuck_duration`）当前是构造伪影；fitness 的 `unstuck` 项直接读伪影量 | SP1+SP2 **不改变任何行为**（P0 验收标准是"**能分辨**"）；`V1` 未达标 ⇒ SP3 全部条目不得开工；`G1` 未过 ⇒ SP3 不得上线 |
| **A/A 门（V9/V13）= P2/P3 前置硬门** | 原方案 §10 **V9**（`bootstrap_upper95(P95) ≤ 0.03`，n ≥ 100；`aa_two_window_fpr ≤ 1%`，≥50 对双窗**实测**）与 **V13**（`arbitration.level` 升级 ≥1 次且 6000 tick 升降 ≤2，PIN `allowed is None` 逐 tick 不变）／§11 R6·R12；`G4` 判据即 V9 | `G4` 未过 ⇒ ① 禁止任何 fitness 变更；② 禁止自动 commit；③ **`P2-c1`（`V13` 的承载者，"无效"定义依赖可分辨成效分）不得开工**；④ `P3` 的 shadow→auto 切换不可执行。`V13` 未达标（升级未发生 / 抖动）⇒ `arbitration_enabled=false`（只读遥测保留）且 **SP6 不可开始** |
| **顺序强制** | 原方案 §7.2："**任何 fitness 变更、任何自动 commit 都不得先于该门通过**" | 在批次表（§5）中，BT7 的出口门 = `G4`，且 BT8/BT9 的入口门包含 `G4` |

### 4.5 并行度的同文件写冲突表（并行施工必须遵守）

| 文件 | 并发批次 | 冲突点 | 裁决 |
|---|---|---|---|
| `fly64/fly64/main.py` | BT1（`a2,a4`）· BT1（`a6`，`:1419-1425`）· BT2（`a3`）· BT3（`a8` 热重载段读回校验）· BT4（`b1,b4`）· BT5（`b2,b3,b5`）· BT6（`d1,d2,d3` 的遥测/发布段 + `d5-f`）· BT8（`c1,c2,c4`） | **18 个条目**落在同一文件 —— **ID 集（逐字）**：`a2,a3,a4,a6,a8`(5) + `b1,b2,b3,b4,b5,b6`(6，`b6` 顶层计) + `c1,c2,c4`(3) + `d1,d2,d3,d5-f`(4) = **18**；**排除** `a7`（t1 a7③ 标 `main.py:49-50`「不改」）与 `b6-5`（t1 判「保留、只登记」，no-op）；**别名不算两次**：`a5`(≡`M4-d3`，`:3034-3068`) 归 M4 列、`d4`(≡`P0-a6`，`:2798-2799`/`:3101-3102`/`:3193-3194`) 归 `P0-a6` 行 ⇒ 二者**不在本 ID 集内** | **同批次内串行合并**；跨批次用 tag 隔离；`main.py` 的每一处改动必须落在**不同函数/不同段**（BT1 落内存更新段 `:2647-2650`/`:2687` 与启动段 `:1419-1425`；BT2 落遥测发布段 `:3034-3068`（`a5`≡`M4-d3`）；BT3 落热重载段 `:1678-1881`；BT4/BT5 落接线段 `:1852-1855`/`:1847-1851`/`:2746-2751`/`:2892-2894`/`:2953-2957`/`:2009-2035`/`:2062-2066`；BT6 落教练直写段与 `memory.json` 发布点 `:1873-1876`/`:2279-2384`/`:2330-2348`/`:2358-2384`/`:2798-2799`/`:3101-3102`/`:3193-3194`；BT8 落 CPG 段 `:2521-2530`/`:2438-2511`） |
| `fly64/fly64/model.py` | BT2（`a3`）· BT4（`b1`）· BT5（`b2,b3,b5`） | `:1787`/`:639`/`:2478`/`:2096` 相互靠近 | `b1` 与 `b2` 均落在 `step()` 内 ⇒ **BT4 与 BT5 之间必须串行合并**（`b1` 先合并，`b2` 再 rebase） |
| `fly64/skills/brain_tunable_params.json` | BT3（`a8`）· BT4（`b1`）· BT5（`b2,b3`） | 同一注册表文件 | **BT3 独占该文件**；BT4/BT5 的新增 `pid` 必须在 BT3 之后 rebase，并重跑区间不变式 |
| `fly64/skills/active_strategy.json` | BT3（三项迁移）· BT4/BT5（A/B 试验写值） | 同一活值文件 | **BT3 期间禁止任何 A/B 试验**（迁移必须先完成并打 tag）；A/B 试验全部经 `P0-a4` 授权点持租约写入 |
| `fly64/skills/fix_executor.py`（**工作树基线，H-2**） | BT6（`d1` 的运行时守卫） | 工作树 `def execute(` = **:438**（HEAD = `:433`，整体 +5） | 守卫必须插在 **`execute` 入口**（工作树 `:438` 之后、`parse_fix_template` 调用 `:469` 之前）；**锚点错位即插错位置** ⇒ 施工前先 `git status --short` + 内容自证（§9.1） |
| `fly64/skills/evolution_skill.py` | BT1（`a7`）· BT4（`b6-1`）· BT6（`d1,d5-a,d5-c`）· BT7（`d2`）· BT8（`c2,d5-b`） | 7 个条目 | `d1` 与 `d2` **可并行**（`:2644` 门禁段 vs `:2460/:2499-2505` fitness 段）；同批内按条目拆 commit 并逐个验证 |

---

## 5. 施工顺序与提交批次

### 5.1 批次表（BT0–BT9，每批可独立验证 + 独立回退）

| 批次 | 阶段 | 条目 | 可并行 | 出口门禁（必须全过） | 验证命令（详见 §10.A） |
|---|---|---|---|---|---|
| **BT0** | SP1 | `P0-a1`（口径冻结；产物 = 本计划 + t1 §2/§5/§6 + `contract_registry.json` 的 `unit_contract` 登记） | — | t1 §2/§5/§6 冻结口径获放行 | 文档评审 |
| **BT1** | SP1 | `P0-a2`、`P0-a4`、`P0-a6`、`P0-a7` | ✅ 四条互不依赖 | **V1**（≥3 取值）· **V2**（≤5%）· **G2**（`param_wiring_ab.json` 39 个 `verdict`）· **V16**（≤120 s 告警）· **V19**（exit 0） | `pytest tests/test_memory_units.py tests/test_param_wiring_ab.py tests/test_evo_liveness.py -q`；`python -m skills.evolution_skill --history-check` |
| **BT2** | SP1 | `P0-a3`、`P0-a5`（`= M4-d3` 框架：字段定名 + 落盘框架，取值待键齐备） | ✅（`a3` 依赖 `a2`，即 BT1） | **V2**（真实时长 ≤5%）· **V15**（`context` ≥25 字段，**框架**） | `pytest tests/test_stuck_duration_true.py tests/test_evolution_log_context.py -q` |
| **BT3** | SP2 | `P0-a8` + 迁移 `M1/M2/M3`（经授权点，迁移前备份） | ❌ **串行硬门** | **G1：`clamp(live)==live` 39/39** · V21 严格判据（37 + 2 例外）· `clamped_keys` 6000 tick 内为空 · **运行期读回校验已接入 `main.py:1678-1881` 热重载段（插在 `:1864-1878` 之后、`:1879` 之前）且 `clamped_keys` 首窗为空**（F-04 补入） | 区间自查命令（§10.A-3）；`pytest tests/test_tunable_wiring.py -q`；`git diff -U0 -- fly64/fly64/main.py` 断言读回校验已插入 |
| **BT4** | SP3 | `P1-b1`（**先跑 `G3` 位精确**）、`P1-b4`、`P1-b6-1`、`P1-b6-2` | ✅ `b4` 与 `b1` 可并行 | **G3**（b1 位精确）· **G2**（A/B 可用）· **V4①** · 回归前置：`test_mushroom_body.py` / `test_mbon_saturation.py` 基线未转红 | `pytest tests/test_jump_leg_gain_chain.py tests/test_cx_goal_comp_writes.py tests/test_mushroom_body.py tests/test_mbon_saturation.py -q` |
| **BT5** | SP3 | `P1-b2`、`P1-b3`（含 RULE-19 契约同批迁移）、`P1-b5`、`P1-b6-3`、`P1-b6-4`、`P1-b6-5`（登记） | ⚠ `b3` 依赖 BT3；`b5` 依赖 BT4 的 `b4`；`b6-3` 依赖 `b5` | **V5**（≥5% 且 P95 ≤0.20）· **V6**（`[0.1%,5%]`）· **V7**（≤1200 tick，`mismatch=0`）· **V8**（burst-off ≥1 且不相交）· **V22**（ratio 契约 PIN 全绿）· **G5**（新增 `control.*` = 0） | `pytest tests/test_jump_homeostat.py tests/test_jump_gate_ratio.py tests/test_cx_loop_break_gate.py tests/test_gate_units.py -q` |
| **BT6** | SP4 | `M4-d1`、`M4-d5-a`、`M4-d5-c`、`M4-d5-f`；`M4-d5-d`（实现落地，**验收复验于 BT8**） | ✅（`d1` 可与 M4 其他并行） | **V20**（0 条 `.py`；绕过用例被拦下；门禁与守卫同 helper）· **V14**（≥1 个 `high`）· **V12**（`effective_count ≥ 1`）· **R9** 清零 | `pytest tests/test_evolution_fix_contract.py tests/test_pattern_reachability.py tests/test_fix_lifecycle.py -q` |
| **BT7** | SP4 | `M4-d2`（**shadow 先行**，可与 BT1–BT5 **全程并行**） | ✅ | **G4**：`bootstrap_upper95(P95) ≤ 0.03`（**n ≥ 100**）**且** `aa_two_window_fpr ≤ 1%`（≥50 对双窗**实测**）；`V10` ≤30%；`V11` ∈ `[5%,30%]` | `pytest tests/test_fitness_aa_gate.py tests/test_fitness_window_alignment.py -q` + 影子记录 ≥1 周 |
| **BT8** | SP5 | `P2-c2`、`P2-c3`（SP5-A）；`P2-c1`、`P2-c4`、`M4-d5-b`（SP5-B） | `c3` 可与 `c1` 并行；`c2/c3` 可与 SP4 并行 | **G4 已过** · **G6**（`V20`）· **V13**（升级 ≥1、升降 ≤2、`level ≤2`；PIN `allowed is None` 逐 tick 不变）· **V17** · **V18**（600 tick 翻转 ≤4）· **V14** | `pytest tests/test_arbitration_state.py tests/test_terminal_surrender.py tests/test_oscillation_window.py -q` |
| **BT9** | SP6 | `M4-d5-e` 复验 + 守护/调度 + shadow→auto（≥1 周影子 + 2 个 A/A 窗）+ 参数空间扩展 + 跨场景泛化 | — | **`R8`/`R9`/`R11` 三灯清零** · **`G4`（V9）已过且 `V13` 达标** · 7×24 心跳无断档 · `effective_count ≥ 1` · 同一参数在 ≥3 场景符号一致 | 心跳巡检 + `ghb` 式长跑巡检脚本 + `fix_catalog.json` 的 `effective_count` |

### 5.2 每批次的上线门禁：必须通过的 V + 必须先清零的阻断条件

| 批次 | 必须通过的 V（阈值） | 必须先清零的阻断条件 | 未清零的后果 |
|---|---|---|---|
| BT1 | V1（≥3 取值）、**V2（≤5%）**、V3（100%）、V16（≤120 s）、V19（**PASS**） | **R8**（`--history-check` FAIL / exit 1）；`V1` 未达标 | R8 未清 ⇒ **SP6 不可开始**（但不阻塞诊断）；V1 未达标 ⇒ **SP3 全部条目阻塞**；**V2 差 >20% ⇒ 回退 `P0-a2`（本批内）** —— 故 V2 必须在本批出口门禁内闭合（F-08） |
| BT2 | **V2（≤5%）**、**V15（≥25 字段，框架）** | 无（`context` 写入异常不得阻塞主循环，`try/except` 包裹） | **V2 二次闭合**（`a3` 的真实时长复用 `a2` 的契约，故 V2 横跨 BT1/BT2，须在 BT2 出口再次判定）；**V15 框架未达 ⇒ 不阻塞 BT2，但必须在 BT8 完整闭合**（F-08） |
| BT3 | **V21（39/39）**、V6（前提）、V22（前提） | **R11**（区间不变式 / 语义翻转 + 越界值共存）；`clamped_keys` 必须为空 | **阻断 SP3 上线**；迁移项失败 ⇒ 保持 Hz 语义并把 `b3` 标未上线 |
| BT4 | **V4①（位精确）**、**V3（A/B 可用）**、回归基线未转红 | **G3**（位精确）；`test_mushroom_body.py`/`test_mbon_saturation.py` 的 `mb.lr_adapt == 1.0` PIN | G3 失败 ⇒ 立即回滚 `b1` 并区块化，**不得进入 A/B**；**V3 必须在本批首次闭合**（`b6-1`/`b6-4` 的 A/B 覆盖率，F-08） |
| BT5 | V5、V6、V7、V8、**V3（延伸闭合：`b6-1`/`b6-4` 的 A/B）**、V22 | **G5**（新增 `control.*` = 0）；`R13`（契约未迁移 ⇒ `b3` 整体不上线）；`R2`（占空比 >5%） | `G5` 未过 ⇒ SP3 整体不上线；`R13` 未清 ⇒ 回退 `b3` 到 Hz 语义；**V3 未闭合 ⇒ SP3 不得整体上线**（F-08） |
| BT6 | V20、V14、V12 | **R9**（pattern `unreachable`）；`G6`（T3 三道理同 helper） | `V20` 断言/守卫失败 ⇒ **阻断 SP5 上线** |
| BT7 | V9（≤0.03，n ≥ 100；fpr ≤1% 实测）、V10（≤30%）、V11（`[5%,30%]`） | **R6**（A/A 门不过 ⇒ 禁止 fitness 变更与自动 commit）；**R12**（n < 100 或按 `0.05²` 估 FPR） | 未过 ⇒ 保持 **shadow**；逐维 `unmeasurable` 剔除；`net_disp_rate` 也不可分辨 ⇒ **H13 不成立 ⇒ SP5-B/SP6 整体阻塞** |
| BT8 | V13、V17、V18、V14、V20、**V15（完整闭合：`context` ≥25 字段且与 `flow.json` 一致）** | **G4**（已过）、**G6**、`R4`、`R5`、`R3` | `c1` 的"无效"仍不可定义 ⇒ 回退 SP1/SP3，**不得进入 SP6**；`c4` 只能靠 OR 支路实现 ⇒ **移除 c4**；**V15 未完整闭合 ⇒ SP5 不得收口**（F-08：`d5-b` 的 `context` 依赖本批） |
| BT9 | V16（7×24）、V12（≥1）、跨场景符号一致（≥3 场景） | **R8 / R9 / R11** 三灯全清 + `G1/G4/G5/G6` 全过 + **`V13` 达标** | 任一红灯未清或 `V13` 未达标 ⇒ **SP6 整体不可开始** |

### 5.3 提交与 tag 约定、批次回退命令

```
# 批次提交（一条 commit = 一个批次的一个条目子集）
# tag 命名（F-05 消歧后的唯一样式）：fly64-sp<sp>-bt<bt>   ← 小写 bt，与批次标签 BT# 对应
git tag -a fly64-sp1-bt1 -m "SP1/BT1: P0-a2 单位对齐+泄放修复; P0-a4 授权点; P0-a6 存活自检; P0-a7 版本三元组"
# 条目级 tag（细粒度回退）
git tag -a fly64-p0-a2 -m "P0-a2 StuckDetector unit alignment + discharge no-op fix"

# 批次回退（代码级）
git revert --no-commit fly64-sp2-bt3..HEAD   # 逆序回退到目标批次

# 参数级回退（优先，符合 §8.1「回退是参数级而非人工 revert」）
Copy-Item fly64/skills/active_strategy.json.bak.<ts> fly64/skills/active_strategy.json -Force
# 开关级回退
#   flow.json["param_authority_degraded"] = true   （退化为只读模式）
#   flow.json["arbitration_enabled"] = false       （停用状态机，保留只读遥测）
#   flow.json["cx_loop_break_enabled"] = false     （停用 CX 突破）
#   flow.json["jump_leg_clamped"] = true           （跳腿回落 0.35）
#   active_strategy.json["escape.jump_intrinsic_max"] = 0  （该腿完全停用）
```

**提交信息纪律**：每条 commit 必须写 `条目 ID + 阶段/批次 + 依 V 判据 + 依 R 回退条款`；涉及迁移的 commit 必须附 `.bak.<ts>` 路径。

### 5.4 V × 批次闭合表（**F-08 新增**：消除 V2 / V15 / V3 与批次出口门禁不闭合）

> **问题（t3 F-08）**：`V2`（`P0-a2`+`P0-a3`）、`V15`（`P0-a5` 框架 → 完整）、`V3`（`P0-a4` + `b6-1`/`b6-4`）的**承载条目横跨多个批次**，而 §5.1 的出口门禁未把"在哪一批闭合"写明 ⇒ 存在"两个批次都以为对方在管"的漏洞。

| V | 承载条目 | 首次判定批次 | **完全闭合批次（必须写在出口门禁内）** | 闭合判据 | 未闭合后果 |
|---|---|---|---|---|---|
| **V1** | `P0-a2` | **BT1** | **BT1** | `stuck_score` 6000 tick 内取值 ≥3 个不同值 | 未达 ⇒ **SP3 全部条目阻塞**（G1a） |
| **V2** | `P0-a2` + `P0-a3` | **BT1**（`a2` 单位契约） | **BT2**（`a3` 的真实时长重算后**再判一次**） | 真实卡死时长与轨迹运动学重算差 **≤5%** | **>20% ⇒ 回退 `P0-a2`**（BT1 的产物），BT2 不得打 tag |
| **V3** | `P0-a4`（39 pid 框架）+ `b6-1`/`b6-4`（延伸） | **BT1**（框架） | **BT5**（延伸闭合） | 39 个 pid **100%** 有 A/B 判定；`b6-1`/`b6-4` 的 A/B 有读数；`wired=false` 者已从搜索空间剔除 | 未闭合 ⇒ **SP3 不得整体上线** |
| **V4** | `P1-b1` | **BT4**（① 位精确，**先行**） | **BT5**（② 双向比例） | ① float32 `np.array_equal`；② `0.35→0.80` ≈2.29×、`0.35→0.10` ≈0.286× | ① 失败 ⇒ 立即回滚 `b1` 并区块化，不进 A/B |
| **V5** | `P1-b2`（+`b1` 前提） | **BT5** | **BT5** | 非零 tick 占比 ≥5% 且 P95 ≤0.20 | P95 >0.20 ⇒ `jump_intrinsic_max` 减半 → 置 0 |
| **V6** | `P0-a8`（前提）+ `P1-b3` | **BT3**（前提：迁移已做） | **BT5** | 占空比 ∈ `[0.1%, 5%]`（**排除 burst 窗口**）；门限真/假都出现 | 恒真/恒假 ⇒ 回退 `b3` 候选 A；迁移未做 ⇒ 先执行 `P0-a8` |
| **V7** | `P1-b4` | **BT4** | **BT4** | 写入值 ≤1200 tick 内可见；`param_write_mismatch = 0` | 不一致 ⇒ 回退 `b4` 写端 |
| **V8** | `P1-b5`（+`b6-3`） | **BT5** | **BT5** | `cx_loop_break_count_burst_off` ≥1 且与 `deadlock_burst_count` 时间戳不相交 | 无法归因 ⇒ 放弃归因（V8 降为非归因观测） |
| **V9** | `M4-d2` | **BT7** | **BT7** | `bootstrap_upper95(P95) ≤0.03`（n ≥100）且 `aa_two_window_fpr ≤1%` 实测 | 未过 ⇒ **禁止 fitness 变更与自动 commit**，保持 shadow |
| **V10** | `M4-d2` | **BT7** | **BT7** | `delta_exact_zero_rate ≤30%`（基线 60.3%） | 未达 ⇒ 窗口 ×2 复测 |
| **V11** | `M4-d2` | **BT7** | **BT9**（滚动复测；BT7 只判首次） | `commit_rate ∈ [5%,30%]`（基线 1.47%） | >30% ⇒ 按 `max(0.03, k·P95_noise)` 重算并复测 A/A |
| **V12** | `M4-d5-c` | **BT6** | **BT9**（长跑后判定） | `effective_count ≥1`（基线 0） | 长期为 0 ⇒ **回到 SP3** |
| **V13** | `P2-c1`（+`c4`） | **BT8** | **BT8** | 升级 ≥1；6000 tick 升降 ≤2；`level ≤2`；PIN `allowed is None` 逐 tick 不变 | 抖动 ⇒ `dwell_ticks` ×2（≤×4）；仍失败 ⇒ 停用（只读遥测保留） |
| **V14** | `M4-d5-a`（+`d5-b`/`c2`） | **BT6** | **BT8**（复验） | 真引擎回放命中 `high` pattern **≥1**（基线 0） | 0 ⇒ 检查 `d5-a` 的键生产者 |
| **V15** | `P0-a5` = `M4-d3` | **BT2**（**框架**：字段定名 + 落盘框架） | **BT8**（**完整**：`context` ≥25 字段且与 `flow.json` 一致；缺失列 `None`） | 每行 `context` 非空、字段数 ≥25、与同 tick `flow.json` 一致 | 框架未达不阻塞 BT2；**完整未达 ⇒ SP5 不得收口**（`d5-b` 的 `context` 依赖本批） |
| **V16** | `P0-a6` = `M4-d4` | **BT1** | **BT9**（7×24 长跑） | 心跳 ≤120 s；断档即告警 | 告警通道异常 ⇒ 至少本地可见 |
| **V17** | `P2-c2`（+`d5-b`） | **BT8** | **BT8** | 终态回放 = `true`；正常段 = `false`；源码断言不出现 `self._stuck_duration` | 正常段误判 ⇒ 提高阈值；两次失败 ⇒ 降为 `medium` 仅记录 |
| **V18** | `P2-c3` | **BT8** | **BT8** | 600 tick 内翻转 ≤4；正常段占比 ≤5% | 失败 ⇒ 回固定 30 帧并只记录 |
| **V19** | `P0-a7` = `M4-d5-e` | **BT1** | **BT1** | `--history-check` exit 0 | 无（版本必须对齐）；未修复 ⇒ P3 不可开始 |
| **V20** | `M4-d1` | **BT6** | **BT8**（复验） | 0 条 `.py` 被执行；判据覆盖 `fix_files ∪ parse_fix_template(...).file` | 失败 ⇒ **阻断 SP5 上线** |
| **V21** | `P0-a8` + 迁移 `M1/M2/M3`；`M4-d5-d` | **BT3** | **BT8**（`d5-d` 复验） | `clamp(live)==live` 39/39；`min<live<max` 37 个；2 个例外走 `min<live≤max` | 任一失败 ⇒ **阻断 SP3 上线** |
| **V22** | `P0-a8`（前提）+ `P1-b3`⑦ | **BT3**（前提） | **BT5**（完整） | ratio 契约 PIN 全绿；`threshold_unit` 已迁移；`main.py:2892-2894` 默认值一致 | 未同步 ⇒ `b3` 整体不上线（保持 Hz 语义） |

**闭合规则（机检）**：每个 V 在表中**恰好有一个「完全闭合批次」**；该批次打 tag 前必须满足该行判据，否则**不得打 tag**。上表 22 行对应 V1–V22，**无缺无重**。

### 5.5 A 类 11 项 / B 类 5 项覆盖对照表（**F-05 新增**）

> **来源**：原方案 `docs/analysis/fly64-autonomy-evolution-plan.md` **§3**（「A/B 两类问题」）。**本节不引入新条目**，只把源 §3 的两类清单映射到本计划的条目/批次，用于交叉核对**无遗漏**。
> **命名消歧（强制）**：**A 类**与**B 类**是**问题分类**；`BT0`–`BT9` 是**提交批次**（见 §0.4）。**B 类 ≠ BT#**。

#### 5.5.1 A 类硬缺陷 11 项 → 落点 → 批次

| # | A 类项（源 §3 表） | 落点条目 | 阶段 | 批次 | 判据 |
|---|---|---|---|---|---|
| A-1 | S19 单位契约（`rate_threshold` 声明为 Hz、比较的是 per-tick 比例） | **`P0-a2`** | SP1 | BT1 | V1 |
| A-2 | 泄放空操作（`memory.py:1985` 每 tick 覆盖 `:1994-1995`） | **`P0-a2`** | SP1 | BT1 | V2（BT2 闭合） |
| A-3 | S33 无消费者门限（**4 个 jump 口径**） | 设计冻结 **`P0-a1`** + 实现 **`P1-b3`** | SP1 / SP3 | BT0 / BT5 | V6、V22 |
| A-4 | S12/S13 死写入（CX 两旋钮） | **`P1-b4`** | SP3 | BT4 | V7 |
| A-5 | `lr_adapt` 死代码（无调用点） | **`P1-b6-1`** | SP3 | BT4 | V3 延伸 |
| A-6 | `_kc_activity` 无写入 | **`P1-b6-2`** | SP3 | BT4 | 计数 >0 + 召回变化 |
| A-7 | `_last_burst_tick` 空守卫 | **`P1-b6-3`** | SP3 | BT5 | 占空比 ≈200/500 |
| A-8 | `position_unchanged_30s` 零生产者 | **`M4-d5-a`** | SP4 | BT6 | V14 |
| A-9 | `bold_explore_stuck_s` 越界静默钳位 | **`P0-a8`**（区间不变式）+ **§6 迁移 `M1`** | SP2 | BT3 | V21 |
| A-10 | SKILL 版本自检红 | **`P0-a7`** = `M4-d5-e` | SP1 | BT1 | V19 |
| A-11 | `has_fix()` 一次性关闭 11 个 `pattern_id` | **`M4-d5-c`** | SP4 | BT6 | V12 |

**计数（源 §3 口径）**：A 类 **11 项** ⇒ 上表 11 行；**每一项都有唯一落点条目 + 批次** ✓（源 §3 的落点对照表即本表的上游；本表把「P2-d3」更正为 `M4-d5-a`/`M4-d5-c`，见 5.5.3）。

#### 5.5.2 B 类自治缺失 5 项 → 落点 → 批次

| # | B 类项（源 §3 表） | 含义 | 落点条目 | 阶段 | 批次 |
|---|---|---|---|---|---|
| B1 | 无**行为决定变量级**作用点（信用分配断口，M1） | 决定行为的 `raw_x`/`raw_y`/`jump` 与所有自适应面不重叠 | **`P1-b1`**（MBON→jump 增益链）、**`P1-b2`**（跳池稳态）、**`P1-b3`**（门归一化）、**`P1-b4`**（CX 旋钮可达）、**`P1-b5`**（CX 突破可达） | SP3 | BT4 / BT5 |
| B2 | 无**竞争 / 升级 / 回退**语义（M2） | `_vote()` 首命中即返回；四个升级/逃离机制有恒真恒假前置 | **`P2-c1`**（升级状态机）、**`P2-c2`**（终态判据 + 前置解锁）、**`P2-c3`**（检测窗自适应）、**`P2-c4`**（CPG 竞争槽） | SP5 | BT8 |
| B3 | 无**可判别适应度**（M4） | 闭环测不出任何差别（60.3% delta 恰为 0） | **`M4-d2`**（五段修复 + A/A 零假设门）+ **`M4-d3`**（观测落盘） | SP4 / SP1 | BT7 / BT2·BT8 |
| B4 | 无**情景责任链** | 无"当时看到了什么"的复盘链；晋升边界未修 | **`M4-d3`**（`context` 块）、**`M4-d5-a`**（键生产者）、**`M4-d5-b`**（终态 pattern）、**`M4-d5-d`**（本能晋升边界） | SP1 / SP4 / SP5 | BT2·BT8 / BT6 / BT8 / BT6 |
| B5 | 无**自观测** | `evolution_log.jsonl` 从不记录传感器数值 | **`M4-d3`**（`context` ≥25 字段）、**`M4-d4`**（存活自检 + 漏斗告警） | SP1 | BT2·BT8 / BT1·BT9 |

**计数（源 §3 口径）**：B 类 **5 项** ⇒ 上表 5 行；**每一项都有落点条目 + 批次** ✓。**与 BT# 的区分**：本表只出现 `B1`–`B5`（**问题类别**）；批次一律写 `BT#`。

#### 5.5.3 更正登记（源 §3 的 `P2-d3` 笔误）

| 项 | 源 §3 原文 | 更正后 | 依据 |
|---|---|---|---|
| `P2-d3` | 源 §3 A 类表把「`position_unchanged_30s` 零生产者、`has_fix()` 生命周期」的落点写作 **`P2-d3`** | **`M4-d5-a`（`position_unchanged_30s` 零生产者）** + **`M4-d5-c`（`has_fix()` 一次性关闭 11 个 `pattern_id`）** | 本方案的条目编号体系里**不存在 `P2-d3`**（`P2` 只有 `c1`–`c4`）；两项的规格分别在 t1 的 `M4-d5-a`（§5.5-a）与 `M4-d5-c`（§5.5-c） |

---

## 6. 回退矩阵

> **§8.1 的硬要求**：回退必须是**参数级**（写 `active_strategy.json` 的一个有界值 / 置一个开关 / 恢复一个常量），**不得要求改 `.py`**；必须有**触发点**（写 `flow.json`）与**记录点**（`param_wiring_ab.json` / `evolution_log` finding）；**不依赖外部服务**；**幂等**。

### 6.1 阶段级回退（触发条件 / 回退动作 / 回退后状态）

#### SP1 · P0-a（观测层；**回退后行为与 HEAD 逐 tick 相同**）

| 触发条件（可判定） | 回退动作（参数级/常量级） | 回退后状态 | 关联 R / V |
|---|---|---|---|
| **R10**：任何位置引用 E-4 层数值且未标「检测伪影」+ H1 | 文档/评审级阻断：补标注；**不修改任何代码** | 文档合规；E-4 数值继续只作"被审视对象" | R10 |
| `V2` 差值 **> 20%** | 复原 `memory.py:135` 的 `rate_threshold = 5.0`（带注释 `# reverted: P0-a2`）与 `memory.py:1993-1995` 原块 | **回到 HEAD 的检测语义**；`V1` 复测为"恒 1.0"（伪影仍在，但**已在文档中登记为伪影**） | R10 / V2 |
| `V1` 未达标（<3 个取值） | **不自动回退**（不是失败而是"未达门"）：写 `high` finding + `memory.json["stuck_score_degenerate"]=true` | 观测层按原样保留；**SP3 全部条目阻塞**（`G1a`） | V1 |
| **R7**：租约冲突 / 第三方写入同一 `pid` | ① 试验期内自愈**让行**；② 冲突即**作废该试验**；③ 租约机制异常（读写异常/缺失）⇒ **退化为只读模式** | `flow.json["param_authority_degraded"]=true`；**禁止所有自动写入**，仅保留教练人工写入 | R7 / V3 |
| `A/B` 无法执行（无真实连接组、探针退化） | 只用**人工确认**的 `pid`；其余 `pid` 在 `param_wiring_ab.json` 记 `verdict="unmeasured"` | SP3 的 A/B 阶段只能对已确认 `pid` 执行；**其余条目不得声称"已验证"** | R7 / V3 / H10 |
| **R8**：`--history-check` 红灯（每次启动 exit ≠ 0） | ① 必须修复（`SKILL_VERSION` → `3.5.1`）；② 未修复前红灯**进入告警通道**（`high` finding + `/memory.json["evo_loop_stale"]` 同级），**不阻塞诊断** | 诊断照常；**SP6 整体不可开始** | R8 / V19 |
| **R9**：pattern 自检报 `unreachable` | ① 补生产者（**不改回 60 s**）；② 缺键 ⇒ 该 pattern 标 `unreachable` **并告警**；③ 任一 `unreachable` ⇒ `high` finding | pattern 集不完整 ⇒ **P3 阻断** | R9 / V14 |

#### SP2 · P0-b（迁移与区间不变式；**回退后保持 Hz 语义，等同未上线**）

| 触发条件 | 回退动作 | 回退后状态 | 关联 R / V |
|---|---|---|---|
| **R11**：任一 `pid` 的 `clamp(live) != live`，或严格判据对 37 个 pid 不成立 | **串行回退**：用 `active_strategy.json.bak.<ts>` 还原三项迁移值 + 把注册项恢复原区间；**不切换语义** | 语义仍在 **Hz**；`P1-b3` 标记为**未上线** | R11 / V21 |
| **R11**：`active_strategy.json:8 = 3.082…` 在比值语义下 ⇒ 门严 **2.5–3.3×** | **不得**带着该值进入比值语义：先完成 `M2` 迁移（`→ 0.75`）再切语义；未完成则回退到 Hz | 同上一行 | R11 / V6 |
| **R13**：`pytest tests/test_gate_units.py` 转红，或 `contract_registry.json` 与注册表 `unit` 不一致 | 同批迁移 `test_gate_units.py` + `contract_registry.json` + `main.py:765-783/2891-2894`；未迁移 ⇒ **回退 `b3` 到 Hz 语义** | `b3` 未上线；`V22` 记 `failed` | R13 / V22 |
| 迁移项失败（`M1`/`M2` 中任一项） | 经授权点回写原值；登记 `high` finding；保留 `.bak.<ts>` | `bold_explore_stuck_s` 仍越界（`V21` 严格判据失败）⇒ **阻断 SP3** | R11 / V21 |
| 迁移后 6000 tick 内 `clamped_keys` 非空 | 逐键对比 `{key, requested, applied, source}`，把该 `pid` 移出自动搜索空间 | 该 `pid` 只接受人工值；`V21` 记 `failed` | R11 / V21 |

#### SP3 · P1（唯一改行为；**回退后行为回到 HEAD 的池/门/旋钮形态**）

| 触发条件 | 回退动作 | 回退后状态 | 关联 R / V |
|---|---|---|---|
| **G3**：`b1` 位精确回归失败（float32 `array_equal` 不成立） | **立即回滚 `b1` 并区块化**：恢复 `model.py:1787` 为 `mbon[3] * self.mbon_gain_jump`，删除 `_jump_leg_weight` 接线；写 `high` finding | 增益链回到单腿形态；**不允许进入 A/B 阶段** | G3 / V4① |
| `b1` 的 A/B 无响应 | ① 判 `wired=false`，把 `escape.jump_leg_weight` 从 `BrainMutator.live_params` **剔除**并写 `param_wiring_ab.json`；② 恢复 `model.py:1787` 为常数 0.35（**保留旧行注释**） | 跳腿增益链未启用；闭环搜索空间不含该 `pid` | R1 / V4② |
| `b1` 的 `jump_pool_occupancy` 非零比例 **> 30%**（跳变持续行为） | 自动把 `_jump_leg_weight` 回落 **0.35** 并置 `flow.json["jump_leg_clamped"]=true` | 跳腿回到名义权重；该腿**不进**闭环搜索空间 | R1 / V5 |
| **R1**：`jump_pool_occupancy` **P95 > 0.20** | ① `escape.jump_intrinsic_max` **减半**（`0.15 → 0.075`）；② 减半后仍失败 ⇒ **置 0**（该腿完全停用）并写 `param_wiring_ab.json` 标 `ineffective`；③ **对偶性失败**（`_jump_homeo_gain` 不能回升至 ≥0.9）⇒ **禁止**该腿进闭环搜索空间（只保留 A/B 手动值）+ `high` finding | 跳池固有兴奋性腿停用；稳态映射保留（无害） | R1 / V5 |
| **R2**：`ctrl.jump` 占空比 **> 5%**（burst-off 窗口统计） | ① 门限 **×2**（`0.75 → 1.5`，记录 `jump_gate_autoraise`）；② 连续两次仍失败 ⇒ 回落 **0.75** 并标 `high_risk`（从自动搜索空间剔除） | 跳门回到 0.75（`high_risk` 标记）；该 `pid` 不再被自动搜索 | R2 / V6 |
| `V6` 条件③失败（门限恒真/恒假） | 判"新口径不可判别"⇒ 回退为**候选方案 A**（按下 1 秒内前向池对跳池的比值 ≥2 倍，用**新增只读指标**而非新门限），并在 `param_wiring_ab.json` 标注 | 跳门口径未切换；只读指标登记 | R2 / V6 |
| `b4` 的 `param_write_mismatch ≠ 0` | **立即回滚 `b4` 的写端改动到原行为**，并**中止 SP3 其余项的闭环接入** | CX 旋钮回到死写入形态；`b4` 判 `wired=false`（**不从注册表删除**，保留为"待修"） | R7 邻域 / V7 |
| `b5` 条件②失败（旋钮无效） | 先回退 `b5`（保持触发条件不变），待 `b4` 通过后再试 | CX 突破保持恒不可达；`V8` 记 `failed` | R2 邻域 / V8 |
| `b5` 条件③失败（正常探索段误触发） | 自动将 `loop_breakout_threshold` 抬到 **0.9** 并收紧 `_loop_break_stuck_s ≥ 45`；仍失败 ⇒ 置 `cx_loop_break_enabled=false`（**只读遥测保留**） | 突破停用但计数保留；`V8` 降为非归因观测 | R2 邻域 / V8 |
| `b6-1` 无 A/B 响应 / `b6-2` 计数恒 0 | `b6-1`：把 `coach.mb_learning_rate` 从搜索空间剔除；`b6-2`：判路径仍不通 ⇒ **删除该路径分支**并把 `_kc_activity` 登记为 `unreachable` | 死代码路径被显式标注，**不得保留"看着像生效"的死路径** | R10 邻域 / V3 |
| `b6-3` 占空比偏离 **200/500 tick** | 回退本项（恢复原守卫形态）并写 `medium` finding | 防重入守卫回到恒真形态（已登记为缺陷） | R2 邻域 / V8 |
| **G5**：出现新增 `control.*` 写入点 | **SP3 整体不上线**：逐条定位并移除该写入点；`git revert` 到上一批次 tag | 回到上一批次行为 | C1 / G5 |

#### SP4 · M4（闭环；**回退后保持 shadow：有 finding、无 commit**）

| 触发条件 | 回退动作 | 回退后状态 | 关联 R / V |
|---|---|---|---|
| **R6**：`bootstrap_upper95(P95) > 0.03`（n ≥ 100）**或** `aa_two_window_fpr > 1%` | **硬门**：禁止所有 fitness 变更与自动 commit；保持 shadow；窗口 ×2（最多 2 次）/ 多窗平均 / 切换到轨迹运动学量 | 闭环只落盘 `sim_fitness` 与 `legacy_fitness`，**不产生 commit**；`SP5-B`/`SP6` 阻塞 | R6 / V9 |
| **R6-F5④**：窗口 ×2 后置信上界仍 > σ_floor | 该 fitness 维度标 `unmeasurable` 并**移出搜索空间**（顺序固定：`meta_channel → learning_progress → coverage_gain → waste_penalty → loop_penalty → net_disp_rate`） | 该维度不再参与 fitness；其余维度继续标定 | R6 / V9 / V11 |
| `net_disp_rate`（轨迹运动学量）也**不可分辨** | **判 H13 不成立**，`P2/P3` 整体阻塞 + `high` finding | 闭环永久 shadow；SP5-B/SP6 不再开工 | R6 / H13 |
| **R12**：n < 100 窗，或按 `0.05²` 估计双窗 FPR | **不达标不得打开自动 commit**：补足 n ≥ 100 + ≥50 对 A/A 双窗**实测** `aa_two_window_fpr` | 自动 commit 保持关闭；`V9` 记 `insufficient_samples` | R12 / V9 |
| `commit_rate > 30%` | 按 `max(0.03, k·P95_noise)` **重算阈值**并复测 A/A | 阈值上调；`V11` 复测 | R6 / V11 |
| `attribution_ok_rate` 未达标（单维试验占比 < 90%） | 强制降到 **1 维** | `_subset_k = 1`；归因可判定性恢复 | R6 / V10 |
| `V10` `delta_exact_zero_rate > 30%` | 窗口 **×2** 复测；`missing_inputs` 非空 ⇒ 该试验 `delta = None`（作废，不计入统计） | 作废试验不污染统计 | R6 / V10 |
| **R9**：pattern 自检报 `unreachable` | ① 补生产者（**不改回 60 s**）；② 缺键 ⇒ 标 `unreachable` + 告警；③ 任一 `unreachable` ⇒ `high` finding | pattern 集不完整 ⇒ **SP6 阻断** | R9 / V14 |
| **R3**：绑定库出现 `turn_bias > 0.25` 的候选 | **阻断晋升**（`promoted` 保持 false）：候选必须落在**注册区间 ∩ 运行期钳位**之内；`promoted` 前**人工复核** | 晋升通道关闭（与改前一致），但**原因已可判定并记录 `reject_reason`** | R3 / V21 |
| `V20` 断言/守卫失败 | **阻断 SP5 上线**；门禁与守卫必须收敛到**同一 helper**（`fix_guard.is_py_patch`） | T3 提案全落 `change_proposals.jsonl`，零执行 | G6 / V20 |
| `V15` 连续 100 行 `context` 为空 | 写 `high` finding + 按 M4-d4 告警；**不得阻塞主循环** | 主循环照常；`V15` 记 `failed` | R9 邻域 / V15 |

#### SP5 · P2（仲裁；**回退后状态机停用但只读遥测保留**）

| 触发条件 | 回退动作 | 回退后状态 | 关联 R / V |
|---|---|---|---|
| **R4**：`arbitration.level` **升降 > 2 次 / 6000 tick** | ① `dwell_ticks` **×2**（最多 ×4，`1500 → 3000 → 6000`）；② `level` 上界 **2**；③ 仍失败 ⇒ **停用状态机**（`arbitration_enabled=false`），**只保留只读遥测** | 升级不动作，`arbitration` 仍落盘可观测 | R4 / V13 |
| `c1` 条件①失败（升级未发生） | 说明 `M4-d2` 的成效分仍不可分辨 ⇒ **回退到 SP1/SP3**，**不得进入 SP6** | 仲裁保持只读；`V13` 记 `failed` | R4 / V13 / G4 |
| **R5**：正常段（`progress_is_ineffective=false`）`oscillation_detected` 占比 **> 5%** | 收紧为 `alternations >= 5`（**提高而非降低门槛**）；仍抖动 ⇒ 回到**固定 30 帧并只记录**（该检测不再驱动反射）+ `medium` finding | 振荡检测只记录不驱动；`V18` 记 `failed` | R5 / V18 |
| `c3` 条件①失败（仍逐 tick 抖动） | 回固定 30 帧 + 只记录 + `medium` finding | 同上一行 | R5 / V18 |
| `c2` 条件②失败（正常段误判终态） | 提高 `T_s` 与 `D`（更保守）；**连续两次失败 ⇒ 把该 pattern 降为 `medium` 并只记录 finding**（不触发任何响应） | 终态判据只记录；`V17` 记 `medium` | R10 邻域 / V17 |
| **F4 判不可行**：`c4` 的"授予 → 执行"只能靠给 `_lif_motion` 追加 OR 支路 | **从 P2 移除 `c4`**；只保留"`primitive_granted_count` 恒 0"的观测与一条 `medium` finding（**诚实标注 CPG 在当前运行点不可达**），**不做折中实现** | CPG 原语仍不可达但**已被显式登记** | F4 / V13 |
| `c4` 条件③失败（授予后 300 tick 内 `net_displacement_rate` 下降） | 提高 `primitive` 候选的入场门槛（成效分需高于 LIF 解码 **1.5×**）；连续两次失败 ⇒ **停用该候选类型**（`primitive_candidate_enabled=false`） | 权威固定为 `lif`；观测保留 | R4 / V13 |
| **G6**：`V20` 未通过 | **阻断 SP5 上线**（回到 BT6 修复 T3 三道理） | SP5 全部条目不上线 | G6 / V20 |

#### SP6 · P3（自治运行；**回退 = auto → shadow + 停用守护**）

| 触发条件 | 回退动作 | 回退后状态 | 关联 R / V |
|---|---|---|---|
| 心跳间隔 **> 120 s**（断档） | 立即告警（`high` finding + `/memory.json["evo_loop_stale"]`），并**暂停 auto commit** | 回到 shadow；守护进程重启后自动续 | V16 / R6 |
| `commit_rate > 30%` 或 `aa_two_window_fpr > 1%`（滚动复测） | 关闭 auto commit（参数级开关）+ 重算阈值 + 复测 A/A | 回到 shadow；有 finding、无 commit | R6 / R12 / V11 |
| `effective_count` 长期为 **0** | **回到 SP3**（说明作用面仍未打通）+ `high` finding；同时把 `param_authority_degraded=true` | 闭环退回"只诊断 + 只落盘" | V12 / R7 |
| 任一红灯复亮（`R8`/`R9`/`R11`） | 立即 **auto → shadow**；恢复 `active_strategy.json.bak.<ts>`（若涉及迁移） | 后序阶段（BT9 的 auto 切换）暂停 | R8/R9/R11 |
| 连续 3 次 fix 失败熔断（`auto_fix=False`） | 熔断**必须进告警通道**（不得只在内存里）；重启后仍须告警 | `auto_fix=false` 且**告警可见** | H8 / R9 邻域 |

### 6.2 条目级回退总表（R1–R13 完整复用，**不得只写"人工回滚"**）

| R | 触发条件（可判定） | 阻断逻辑 | 自动回退动作 | 回退后状态 | 关联 ID / V |
|---|---|---|---|---|---|
| **R1** | `jump_pool_occupancy` P95 > 0.20 | 不阻断整体，只回退该腿 | `escape.jump_intrinsic_max` 减半 → 置 0 → 标 `ineffective`；对偶性失败 ⇒ 禁止进搜索空间 + `high` finding | 跳池固有腿停用；稳态映射保留 | P1-b2 / V5 |
| **R2** | `ctrl.jump` 占空比 > 5%（burst-off 统计） | 不阻断整体；连续两次失败把该 `pid` 移出自动搜索空间 | 门限 ×2（记 `jump_gate_autoraise`）→ 回落 0.75 并标 `high_risk` | 跳门回 0.75（`high_risk`），不可被自动搜索 | P1-b3 / V6 |
| **R3** | 绑定库出现 `turn_bias > 0.25` 的候选 | **阻断晋升**（`promoted` 保持 false） | 候选必须落在注册区间 ∩ 钳位之内；`promoted` 前人工复核 | 晋升关闭但原因可判定（`reject_reason`） | M4-d5-d / V21 |
| **R4** | `arbitration.level` 升降 > 2 次 / 6000 tick | 抖动 ⇒ 不阻断先调参；无界 ⇒ 阻断 | `dwell_ticks` ×2（≤×4）→ `level` 上界 2 → 停用（`arbitration_enabled=false`） | 状态机停用，**只读遥测保留** | P2-c1 / V13 |
| **R5** | 正常段 `oscillation_detected` 占比 > 5% | 不阻断；门限**提高**（非降低） | `alternations >= 5` → 固定 30 帧**只记录** + `medium` finding | 振荡检测不驱动反射 | P2-c3 / V18 |
| **R6** | `bootstrap_upper95(P95) > 0.03`（n ≥ 100）或 `aa_two_window_fpr > 1%` | **硬门：阻断**所有 fitness 变更与自动 commit | 保持 shadow；窗口 ×2；逐维 `unmeasurable` 剔除；`net_disp_rate` 亦不可分辨 ⇒ H13 不成立、P2/P3 阻塞 | 闭环永久/临时 shadow | M4-d2 / V9·V11 |
| **R7** | 租约冲突 / 第三方写入（同一 `pid` 多 owner） | 试验作废（**不阻断**其他条目） | 自愈让行；冲突即作废该试验；机制异常 ⇒ 只读模式 | `param_authority_degraded=true`，禁止自动写入 | P0-a4 / V3 |
| **R8** | `--history-check` 退出码 ≠ 0（每次启动） | **闭环不得进入 P3**；红灯**不阻塞诊断** | 必须修复；未修复前进告警通道 | 诊断照常；SP6 不可开始 | P0-a7 / V19 |
| **R9** | pattern 自检报 `unreachable` | **阻断 P3** | 补生产者（不改回 60 s）；缺键标 `unreachable` + 告警；启动自检任一 `unreachable` ⇒ `high` finding | pattern 集不完整 ⇒ 责任链不成立 | M4-d5-a / V14 |
| **R10** | 任何引用 E-4 层数值处 | 文档/代码评审级阻断 | 强制标注「**检测伪影**」+ 假设 **H1**；判据必须用 P0 重建后的真实量（源码断言：求值路径不出现 `self._stuck_duration`） | E-4 数值仅作被审视对象 | P0-a2/a3、P2-c2 / V2·V17 |
| **R11** | `active_strategy.json:8 = 3.082…` 在比值语义下 ⇒ 门严 2.5–3.3×；**或**任一 `pid` 的 `clamp(live) != live` | **阻断 P1 上线**（P0-a8 的验收） | 上界 4.0 + 显式迁移到 0.75 + `min<live<max`（含 `default==max` 例外）硬断言；断言失败即阻断；迁移项失败 ⇒ 保持 Hz 语义 | 语义不切换；`b3` 标未上线 | P0-a8、P1-b3 / V21·V6 |
| **R12** | n < 100 窗，或按 `0.05²` 估双窗 FPR | **阻断自动 commit** | n ≥ 100 + bootstrap 置信上界判据 + ≥50 对双窗**实测** | 自动 commit 关闭 | M4-d2 / V9 |
| **R13** | `pytest tests/test_gate_units.py` 失败，或 `contract_registry.json` 与注册表 `unit` 不一致 | **§5.3 整体不上线** | 同批迁移 `test_gate_units.py` + `contract_registry.json` + `main.py:765-783/2891-2894`；未迁移则回退 `b3` 到 Hz 语义 | `b3` 未上线；`V22` 记 `failed` | P1-b3 / V22 |

### 6.3 全局熔断（kill switch，人工可一键回到"只诊断"）

| 开关 | 落点 | 生效后状态 | 恢复方式 |
|---|---|---|---|
| `param_authority_degraded = true` | `flow.json` | 禁止**所有**自动参数写入（含 A/B 试验与自愈回写），只保留教练人工写入 | 修复租约机制后置回 `false` |
| `arbitration_enabled = false` | `flow.json` | 升级状态机停用，`arbitration` 只读落盘 | 调参后重启 |
| `cx_loop_break_enabled = false` | `flow.json` | CX 环路突破停用，`cx_loop_break_count*` 只读保留 | 收紧阈值后重启 |
| `auto_fix = false` 且 `auto commit` 关闭 | `evolution_skill` 运行态 + `active_strategy.json` 不写 | 闭环只诊断 + 只落盘（**shadow**） | A/A 门复测通过后开启 |
| `escape.jump_intrinsic_max = 0` | `active_strategy.json` | 跳池固有兴奋性腿完全停用（幂等：已为 0 不再减半） | A/B 通过后恢复 |
| **总闸**：`git revert` 到上一批次 tag + 还原 `active_strategy.json.bak.<ts>` + 重启 | git + 文件 | 回到上一批次行为 | 重新排期 |

---

## 7. 验证矩阵（V1–V22 ↔ 阶段 ↔ 条目 ↔ 阈值 ↔ 落点）

| V | 指标 | 阶段 / 批次 | 条目 | 目标阈值（基线） | 断言落点（t1 §7） | 失败回退 |
|---|---|---|---|---|---|---|
| **V1** | `stuck_score` 非常量性 | SP1 / BT1 | `P0-a2` | 6000 tick 内取值 **≥3 个不同值**（基线恒 `1.0`） | `tests/test_memory_units.py`（新增） | 未达标 ⇒ **阻塞 SP3 全部条目** |
| **V2** | 真实卡死时长与轨迹一致 | SP1 / BT1·BT2 | `P0-a2, a3` | 与运动学重算差 **≤5%**（无基线） | `test_memory_units.py` + `test_stuck_duration_true.py`（新增） | 差 **>20%** ⇒ 回退 `P0-a2` |
| **V3** | `param_wiring_ab` 判定覆盖率 | SP1 / BT1（框架）→ SP3 / BT4·BT5（延伸） | `P0-a4`；`b6-1, b6-4` | **100%** 有 A/B 判定；`wired=false` 者从搜索空间剔除 | `test_param_wiring_ab.py`（新增） | A/B 无法执行 ⇒ 只用**人工确认**的 `pid` |
| **V4** | `jump_leg_current` 对 `jump_leg_weight` 的响应 | SP3 / **BT4（①先行）**· BT5 | `P1-b1` | ① **位精确**（float32 `np.array_equal`，非 `approx`）；② `0.35→0.80` 升 **≈2.29×**；`0.35→0.10` 降 **≈0.286×** | `test_jump_leg_gain_chain.py`（新增） | ① 失败 ⇒ **立即回滚 `b1`**，不进 A/B；② 无响应 ⇒ 剔出搜索空间并恢复常量 0.35 |
| **V5** | `jump_pool_occupancy` P95 | SP3 / BT4·BT5 | `P1-b1, b2` | 非零 tick 占比 **≥5%** 且 **P95 ≤0.20**（前提：V4① 已过） | `test_jump_homeostat.py`（新增） | P95 >0.20 ⇒ `jump_intrinsic_max` 减半 → 置 0 |
| **V6** | `ctrl.jump` 占空比 | SP2 / BT3（前提）→ SP3 / BT5 | `P0-a8`（前提）、`P1-b3` | **∈ [0.1%, 5%]**，门限 6000 tick 内真/假都出现；**排除 burst 窗口**（基线 **0/6000 = 0.0%**） | `test_jump_gate_ratio.py`（新增）+ 6000 tick 运行时验收 | 恒真/恒假或越界 ⇒ 回退 `b3` 候选 A；迁移未做 ⇒ 先执行 `P0-a8` |
| **V7** | `cx_effective_steering_gain` 写读一致 | SP3 / BT4 | `P1-b4` | 写入值 **≤1200 tick** 内可见；`param_write_mismatch = 0`（基线：写 0.5 无效、`_goal_comp` 仍 0.12） | `test_cx_goal_comp_writes.py`（新增） | 不一致 ⇒ 回退 `b4` 写端 |
| **V8** | `cx_loop_break_count_burst_off` | SP3 / BT5 | `P1-b5`（+`b6-3`） | **burst-off 窗口** 4000 tick 内 **≥1**；正常段 = 0；与 `deadlock_burst_count` 时间戳**不相交**（基线 0） | `test_cx_loop_break_gate.py`（新增） | 旋钮无效 ⇒ 回退 `b5` 等 `b4`；**仍无法归因 ⇒ 放弃归因**（V8 降为非归因观测，`b5` 判未通过） |
| **V9** | `aa_p95_abs_delta`（**G4**） | SP4 / BT7 | `M4-d2` | `bootstrap_upper95(P95) ≤ 0.03`，**n ≥ 100 窗**；`aa_commit_threshold = max(0.03, 2·P95_noise)`；`aa_two_window_fpr ≤ 1%`（≥50 对**实测**） | `test_fitness_aa_gate.py`（新增） | 未过门 ⇒ 禁止 fitness 变更与自动 commit；噪声降不下 ⇒ 逐维 `unmeasurable` 剔除 |
| **V10** | `delta_exact_zero_rate` | SP4 / BT7 | `M4-d2` | **≤30%**（基线 **60.3%**） | `test_fitness_window_alignment.py`（新增） | 未达标 ⇒ 窗口 ×2 复测 |
| **V11** | `commit_rate` | SP4 / BT7 | `M4-d2` | **∈ [5%, 30%]**（基线 **1.47%**） | 同 V10 文件 | >30% ⇒ 按 `max(0.03, k·P95_noise)` 重算阈值并复测 A/A |
| **V12** | `effective_count` | SP4 / BT6 → SP6 / BT9 | `M4-d5-c` | **≥1**（首个被证实的改进；基线 0，19 条 fix 全无效） | `test_fix_lifecycle.py`（新增） | 长期为 0 ⇒ **回到 SP3**（作用面仍未打通） |
| **V13** | `arbitration.level` 升级且不抖动 | SP5-B / BT8 | `P2-c1`（+`c4`） | 升级 **≥1** 次；6000 tick 内升降 **≤2**；`level ≤2`；**PIN**：`allowed is None` ⇒ `_vote` 逐 tick 不变 | `test_arbitration_state.py`（新增） | 抖动 ⇒ `dwell_ticks` ×2（≤×4）；仍失败 ⇒ 停用（只读遥测保留） |
| **V14** | 真引擎回放命中 `high` pattern 数 | SP4 / BT6 → 复验 SP5 / BT8 | `M4-d5-a`（`d5-b`、`c2`） | **≥1 个 `high`**（基线 0 个 high，只 medium+low） | `test_pattern_reachability.py`（新增） | 0 ⇒ 检查 `d5-a` 的键生产者 |
| **V15** | `context` 完整度 | SP1 / BT2（**框架**）→ **SP5 / BT8（完整）** | `P0-a5` = `M4-d3` | 每行 **≥25 字段**且与 `flow.json` 一致；缺失列 `None`（**不得静默填 0**） | `test_evolution_log_context.py`（新增） | 连续 100 行为空 ⇒ `high` finding + 告警（不阻塞主循环） |
| **V16** | 闭环存活 | SP1 / BT1 → SP6 / BT9 | `P0-a6` = `M4-d4` | 心跳间隔 **≤120 s**；断档即告警（基线：停摆 7 天无告警） | `test_evo_liveness.py`（新增） | 告警通道异常 ⇒ **至少本地可见**（`agent_state`/`memory.json`） |
| **V17** | `terminal_surrender` 判定正确性 | SP5-A / BT8 | `P2-c2`（`d5-b`） | 终态回放 = `true`；正常段 = `false`；源码断言：求值路径**不出现** `self._stuck_duration` | `test_terminal_surrender.py`（新增） | 正常段误判 ⇒ 提高阈值；两次失败 ⇒ 降为 `medium` 仅记录 |
| **V18** | `oscillation_detected` 稳定性 | SP5-A / BT8 | `P2-c3` | 600 tick 内翻转 **≤4** 次；正常段占比 **≤5%**（基线逐 tick 抖动） | `test_oscillation_window.py`（新增） | 失败 ⇒ 回固定 30 帧并只记录 |
| **V19** | `--history-check`（**红灯 R8**） | SP1 / BT1 | `P0-a7` = `M4-d5-e` | **PASS**（`SKILL_VERSION == canonical.skill == "3.5.1"`，exit 0）（基线 **FAIL / exit 1**） | CLI 自检（无新测试文件） | 无（版本必须对齐）；未修复 ⇒ **P3 不可开始** |
| **V20** | T3 提案不进入执行 | SP4 / BT6（**G6**）→ 复验 SP5 / BT8 | `M4-d1` | **0 条 `.py` 补丁被执行**；判据覆盖 `fix_files ∪ parse_fix_template(...).file`；守卫可被独立注入测试拦下 | `test_evolution_fix_contract.py`（**新增**） | 断言/守卫失败 ⇒ **阻断 SP5 上线**；门禁与守卫必须同一 helper |
| **V21** | 区间不变式（**G1 / 红灯 R11**） | SP2 / BT3 → 复验 SP4 / BT6（`d5-d`）、SP5 / BT8 | `P0-a8` + 迁移 `M1/M2/M3`；`M4-d5-d` | `clamp(live)==live` **39/39**；`min<live<max` **37 个**；`default==max` 的 2 个走 `min<live≤max`；`:8` 迁移 0.75 后同类断言通过 | 扩展 `tests/test_tunable_wiring.py` | 任一失败 ⇒ **阻断 SP3 上线** |
| **V22** | RULE-19 契约迁移完整性（**红灯 R13**） | SP2 / BT3（前提）→ SP3 / BT5（完整） | `P0-a8`、`P1-b3`⑦ | ratio 契约 PIN 全绿；`contract_registry.json` 的 `threshold_unit` 已迁移；`main.py:2891-2894` 默认值与注册表一致；新增 PIN `allowed is None ⇒ _vote` 逐 tick 不变 | 改写 `tests/test_gate_units.py:178-226`（**基线 15 passed，改后须全绿且断言为 ratio 版**） | 迁移未同步 ⇒ **`b3` 整体不上线**（保持 Hz 语义） |

**反向核对**：`V1–V22` 共 22 项，全部有唯一阶段归属；`§10` 的每一行都在上表出现一次（无遗漏、无重复）。本计划**不新增**任何 V 指标。

---

## 8. 工作量与风险

### 8.1 阶段工作量估算与对账（vs 原方案 §8）

| 阶段 | 本计划（人·日） | §8 对应区间 | 对账说明 |
|---|---|---|---|
| SP1 | 3.0–5.0 | P0 合计 **3–5** | 含 `a1` 冻结 0.5；`a2/a3` 各 0.5–1.0；`a4` 1.0–1.5（新增 `param_authority.py` + 自愈让行）；`a5/a6/a7` 0.5–1.0 |
| SP2 | 1.0–1.5 | （并入 P0） | **超区间 1.0–1.5 人·日**：t1 §7 新增的区间不变式断言 + 三项迁移的授权点写入与复验，原 §8 未单列 |
| SP3 | 5.0–8.0 | P1 **5–8** | 完全落在区间内；含 18 个新增测试文件中的 6 个（BT4/BT5） |
| SP4 | 4.0–6.0 | P2 合计 **6–10** | 与 SP5 合计 = 6.0–10.0，**完全落在 §8 的 P2 区间内** |
| SP5 | 2.0–4.0 | （同上） | 同上 |
| SP6 | 5.0–8.0 | P3 **5–8** | 完全落在区间内 |
| **合计** | **20.0–32.5** | 19–31 | 差值 **+1.0–1.5 人·日**，全部来自 t1 §7 新增的 **18 个测试文件**与断言改写（`test_gate_units.py` ratio 版）；**已披露，不隐藏** |

**并行压缩后的日历估算**：若 SP4 作为并行轨道（BT6/BT7）与 SP1/SP2/SP3 同期执行，且 BT1 内部四条并行、BT4 与 BT1 可错峰，则**墙钟 ≈ SP1+2+3+4+5+6 的关键路径串行部分（SP1 3–5 + SP2 1–1.5 + SP3 5–8 + BT8 2–4 + BT9 5–8 ≈ 16–26.5 人·日）**，其余由并行消化。

### 8.2 风险登记与缓解

| 风险 | 等级 | 触发点 | 缓解 | 残余风险 |
|---|---|---|---|---|
| **SP2 语义翻转静默收紧**（R11） | **高** | `3.082 > 3.0` 的算术越界 + 严格判据对 `default==max` 恒不成立 | 上界 4.0 + 显式迁移 0.75 + `min<live<max`（含例外）+ 启动自检 | 例外清单写错 ⇒ P1 永久锁死（已由 `clamp(live)==live` 主判据兜底） |
| **SP3 数值阈值依赖真实连接组**（H5/H6/H11/H12） | **高** | 无 `.cache/malecns/manifest.json`；探针发放退化 100% | 全部阈值标 `【待标定】`；A/B 双向验证；`JUMP_GAIN_MAX` 标**可撤回项** | 真实连接组上 `H11` 可能不成立 ⇒ `b1` 的 A/B 无响应 ⇒ 剔出搜索空间并恢复常量 0.35 |
| **SP3 `b3` 的 RULE-19 契约迁移**（R13，F13） | **高** | 4+ 条 PIN 断言硬编码 Hz 语义 | 同批迁移测试 + 注册登记表 + 注释块；pinned 力度不下调 | 迁移不彻底 ⇒ `b3` 整体不上线（可接受） |
| **SP3 位精确回归失败**（G3，F2） | 中高 | `0.35 × 1.5 = 0.525` 的归一化写法易错 | 实现内除以 nominal + float32 `array_equal`（非 `approx`） | 失败 ⇒ 立即回滚 `b1` 并区块化（不进 A/B） |
| **SP4 A/A 门不通过**（H13，G4） | **高** | 真实噪声可能淹没有效信号 | n ≥ 100 + bootstrap 置信上界 + 双窗 FPR 实测；逐维 `unmeasurable` 剔除 | `net_disp_rate` 也不可分辨 ⇒ **H13 不成立，P2/P3 整体阻塞**（这是设计内的诚实出口） |
| **SP5 `c1` 接口语义返工**（F14） | 中高 | `_vote` 是扁平首命中，无"严重度层" | 定义为纯函数式 `_vote_all` + `allowed` 参数；PIN `allowed is None` 逐 tick 不变 | 返工只影响 `c1` 内部实现，不触 `_vote` 语义 |
| **SP5 `c4` 结构性不可行**（F4） | 中 | `_lif_motion` 恒真（`control.y = 70 > 8`） | 权威谓词替换（不追加 OR）；**不可行即移除**，不折中 | 移除 ⇒ CPG 原语仍不可达，但已显式登记为 `medium` finding |
| **闭环停摆/熔断无持久化**（H8） | 中 | `evolution_skill.py:2736-2740` 熔断行无持久化 | 熔断与 `effective=0` **一律进告警通道**（M4-d4）；heartbeat ≤120 s | 停摆期间的历史故障窗口仍无法判定（H9，记录不阻断） |
| **18 个新增测试文件的维护成本** | 中 | 原 §8 未计 | 已在 §8.1 对账中显式计入 +1.0–1.5 人·日 | 无 |
| **并行施工的同文件写冲突**（`main.py` 16 条 / `evolution_skill.py` 7 条） | 中 | §4.5 冲突表 | 同批内串行合并 + tag 隔离 + 每处落不同函数段 | rebase 冲突需人工裁决（不改变逻辑） |

---

## 9. 前置准备清单（Pre-flight）

### 9.1 开工前必须完成（阻断级，逐条勾选）

- [ ] `git rev-parse HEAD` == `cca66648a204043d881da502cf996b15882ad289`（否则本计划与 t1 的行号全部重核）
- [ ] **基线自证（H-1/H-2，取代原「工作树干净」条目）** —— 工作树**不干净是既成事实**（`git status --porcelain` 实测 **158 项 M/D**），因此**不得**以「工作树干净」作为前置。改为**逐文件内容比对**：
  - [ ] `git status --short fly64/skills/active_strategy.json fly64/skills/fix_executor.py` ⇒ 两条都必须是 **`M`**（**若为 clean ⇒ 说明该文件已被他人同步到 HEAD，本计划 §0.5.2 的 HEAD 变体口径与 M4-d1 锚点须重核**）
  - [ ] **内容自证（记录到开工记录里）**：`fly64/skills/active_strategy.json` 行数 = **55**、`:4 = "turn_bias": 0.25`、`:5 = "bold_explore_stuck_s": 60.0`、`:8 = "gate_jump_threshold": 3.082271242248696`、`__generation = 332`；`fly64/skills/fix_executor.py` 的 `def execute(` 在 **:438**、`def _resolve_file` 在 **:603**
  - [ ] **HEAD 变体留证**：`git show HEAD:fly64/skills/active_strategy.json`（**21 行、扁平点号键**）与 `git show HEAD:fly64/skills/fix_executor.py | Select-String 'def execute\('`（**:433**）各跑一次并留存输出 ⇒ 与本计划 §0.5.1 的双基线表对齐
  - [ ] 建立集成分支 + 打基准 tag（**命名**：`fly64-base-cca66648`；**注意**：由于工作树非干净，该 tag 只标记**集成分支的起点 commit**，不表示"工作树 == HEAD"）
  - [ ] 若决定改为**从干净 HEAD 开工**：必须先完成 `active_strategy.json` 的**键名归一化**（建立嵌套键格式）再执行 `M1/M2/M3`，并按 §0.5.1 重算 `fix_executor.py` 的四个锚点（`433/464/483/598`）
- [ ] **备份** `fly64/skills/active_strategy.json` → `active_strategy.json.bak.<ts>`，路径写进提交信息
- [ ] 记录 **基线**：`cd fly64; python -m pytest tests/test_gate_units.py -q` ⇒ **15 passed**（本计划已实测：`15 passed in 1.62s`）
- [ ] 记录 **基线**：`cd fly64; python -m skills.evolution_skill --history-check` ⇒ **FAIL / exit 1**，末行 `SKILL_VERSION 3.5.0 != canonical 3.5.1`（本计划已实测，exit code = 1）
- [ ] 记录 **基线**：`cd fly64; python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q`（`b6-1` 的两处 `mb.lr_adapt == 1.0` PIN 回归风险）
- [ ] 记录 **基线**：**全量** `cd fly64; python -m pytest tests/ -q`（98 个 `test_*.py`）⇒ 保存输出，"转红"判断以此为唯一依据
- [ ] 跑 t1 §6 的**只读区间自查命令**并留存输出：预期 **39/39 有活值**，越界/钉界仅 **2** 个（`exploration.bold_explore_stuck_s` 标 `OUT`；`exploration.turn_bias` 钉上界）；`gate_jump_threshold` 在当前区间内
- [ ] 跑 t1 §14-A 的**只读接线静态工具**（`scripts/audit_contract_pairs.py`）并留存输出：预期 38 条 `unreferenced w=0 r=0 decl=0`（**不扫注册表**，F7；**不能**据此判 `wired: false`）
- [ ] 确认 `.tmp/fly64_trajectory.json` **存在**（V2/V18 的输入；本计划已实测 = True）；若缺失 ⇒ 这两条 V 只能标 `unmeasurable`，**不得用伪影替代**
- [ ] 确认 `fly64/skills/instinct_bindings.py` **不存在**、`fly64/fly64/instinct_bindings.py` **存在**（本计划已实测：False / True）
- [ ] 确认 `fly64/tests/test_evolution_fix_contract.py` **不存在**（需新增；本计划已实测 = False）
- [ ] 确认 `fly64/skills/param_wiring_ab.json`、`fly64/skills/fitness_aa_report.json`、`fly64/skills/.evo_loop_heartbeat.json`、`fly64/skills/change_proposals.jsonl` **均不存在**（将为新增产物）
- [ ] 确认 `fly64/fly64/arbitration.py`、`fly64/skills/param_authority.py`、`fly64/skills/fix_guard.py`、`fly64/skills/fitness_aa_gate.py`、`fly64/skills/evo_funnel_alarm.py` **均不存在**（5 个新增源文件）
- [ ] 六个硬门 `G1–G6` 与三条红灯 `R8/R9/R11` 的**责任人**与**告警通道**已指定（谁的 mailbox / 哪个落盘文件）

### 9.2 阶段级前置（未满足则该阶段不得开工）

| 阶段 | 必须先满足 | 理由 | 当前状态（本机实测） |
|---|---|---|---|
| **SP3** | ① **真实连接组 cache 可用**（`.cache/malecns/manifest.json` + 同一探针）⇒ 解除 **H5/H6/H11**；② `gain("jump")` 在 `[0.5, 2.5]` 两端下的跳池占用率读数 ⇒ 关闭 **H12**（决定 `JUMP_GAIN_MAX = 4.0` 是保留还是撤回）；③ `V1` 与 `G1` 已通过 | 否则 SP3 的全部数值阈值只是"算术可达性"，**不能上线** | `.cache/malecns/manifest.json` = **不存在** ⇒ **H5/H6/H11 保持未关闭**；SP3 的数值项停在 `【待标定】` |
| **SP4** | A/A 标定的**观测源**就绪：`flow.json`/`memory.json` 可读、`ParamAuthority` 租约可用（BT1 产物）、单个 A/A 窗的墙钟/仿真时长确定 | 否则 n ≥ 100 窗无法积累 | `memory.json` = **不存在** ⇒ 需先由 BT1/BT2 建立落盘 |
| **SP5-B** | **`G4` 通过**（`V9`：n ≥ 100 + `fpr ≤ 1%` 实测） | `c1` 的"无效"定义依赖可分辨成效分；R6 为硬门 | 未开始（依赖 SP4） |
| **SP6** | **`R8`/`R9`/`R11` 三条红灯全清** + `G1/G4/G5/G6` 全过 + **≥1 周影子记录 + 2 个 A/A 窗** | 原方案 §8 P3 交付判据 | `R8` 当前 **FAIL**（实测）；另两灯需 BT3/BT6 清零 |

### 9.3 假设分级清单（H1–H14，**不得当作断言**）

| 级别 | 含义 | 假设 | 关闭它需要什么 | 影响 |
|---|---|---|---|---|
| **A 级（不关闭则该阶段不得上线）** | 阻断级 | **H5**（真实连接组运行点 ≠ demo 探针，发放退化 100%）、**H6**（跳池 <0.04 而前向池 ≈0.043 的断口）、**H11**（MBON 腿是有效注入腿）、**H12**（`[0.5,2.5]` 上限过低 ⇒ `JUMP_GAIN_MAX = 4.0` **可撤回**） | 真实连接组 cache + 同一探针 + A/B 双向读数 | **SP3 上线**；`b1`/`b2` 的全部阈值 |
| **A 级** | 阻断级 | **H13**（长窗 + 轨迹运动学 fitness 可分辨） | **A/A 门实测**（唯一关闭方式） | **`G4`**；未关闭 ⇒ SP5-B/SP6 整体阻塞 |
| **B 级（阶段内标定项，影响初值不阻断整体）** | 标定 | **H2**（`anomaly_state="stuck_ramp"` 在 HEAD 不可复现）、**H3**（oscillating 抖动，需原始 `ctrl_x`）、**H14**（`dwell_ticks = 1500` 仅为设计初值） | 该 run 的 `exploration_mode` + `anomaly_state_history` / `/flow.json` 的 `ctrl_x` 原序列 / `ineffective_ticks` 分布 | `c2` 的 `T_s/D/W`、`c3` 的系数 6、`c1` 的 `dwell_ticks` |
| **B 级（明示"不作为回退条件"）** | 记录 | **H4**（`forced_bold_explore` 可达性取决于"钳位后阈值 + 单一异常标签稳定性"，**不判为结构不可达**） | 运行时读回钳位后的实际值 + 异常标签持续时长分布 | `M4-d5-d` 的边界；**本条不作为任何回退条件** |
| **C 级（记录，不阻断）** | 记录 | **H1**（轨迹产自 `6d0aa42` 之前）、**H1'**（0.37 s 转向变号的生成者）、**H7**（CX 恒不可达是**条件性**的）、**H8**（auto-fix 熔断未触发但无持久化）、**H9**（停摆窗口内是否发生故障无法判定）、**H10**（`audit_contract_pairs.py` 的 39 参数全 unreferenced 是**静态扫描盲区**） | 墙钟 provenance / 各驱动腿分解 / 真实 run 的 `goal_vectors` 日志 / 熔断行持久化 / 运行日志原件 | 影响归因口径与观测，不阻断阶段 |

> **标注纪律（P3，强制）**：本计划及后续一切验收报告中，凡引用 `memory.json` 的 **E-4 层数值**（`stuck_score=1.0`、`stuck_duration=1100.72`、`reflex_active=False`、`median_speed=0.0`、`disp_60s=1080.7`）**必须**同处标注「**检测伪影**」+「**版本边界 H1**」；**禁止**改写为"已确认"。

---

## 10. 附录

### A. 命令清单

> 统一前缀：`cd D:\codes\flygym\fly64; $env:PYTHONIOENCODING="utf-8"`

**A-1 基线（施工前，§9.1 逐条执行并留证）**

```powershell
# 版本边界
git rev-parse HEAD                     # 期望 cca66648a204043d881da502cf996b15882ad289
# 契约基线（已实测 15 passed in 1.62s）
python -m pytest tests/test_gate_units.py -q
# 回归风险基线（b6-1 的两处 PIN）
python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q
# 红灯基线（已实测 FAIL / exit 1）
python -m skills.evolution_skill --history-check
# 全量基线（98 个 test_*.py；"转红"判断的唯一依据）
python -m pytest tests/ -q
```

**A-2 批次验证**

```powershell
# BT1
python -m pytest tests/test_memory_units.py tests/test_param_wiring_ab.py tests/test_evo_liveness.py -q
python -m skills.evolution_skill --history-check            # 期望 exit 0
# BT2
python -m pytest tests/test_stuck_duration_true.py tests/test_evolution_log_context.py -q
# BT3
python -m pytest tests/test_tunable_wiring.py -q
# BT4
python -m pytest tests/test_jump_leg_gain_chain.py tests/test_cx_goal_comp_writes.py -q
python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q
# BT5
python -m pytest tests/test_jump_homeostat.py tests/test_jump_gate_ratio.py tests/test_cx_loop_break_gate.py tests/test_gate_units.py -q
# BT6
python -m pytest tests/test_evolution_fix_contract.py tests/test_pattern_reachability.py tests/test_fix_lifecycle.py -q
# BT7
python -m pytest tests/test_fitness_aa_gate.py tests/test_fitness_window_alignment.py -q
# BT8
python -m pytest tests/test_arbitration_state.py tests/test_terminal_surrender.py tests/test_oscillation_window.py -q
```

**A-3 区间不变式自查（只读，施工前后各跑一次）**

```powershell
python -c "import json,pathlib as P; r=json.loads(P.Path('skills/brain_tunable_params.json').read_text(encoding='utf-8'))['params']; s=json.loads(P.Path('skills/active_strategy.json').read_text(encoding='utf-8')); [print(p, s.get(p.split('.')[0],{}).get(p.split('.')[1]), r[p]['min'], r[p]['max'], 'OUT' if not (r[p]['min']<=s.get(p.split('.')[0],{}).get(p.split('.')[1])<=r[p]['max']) else 'ok') for p in r]"
```
**基线预期**：39/39 有活值；`OUT` 仅 `exploration.bold_explore_stuck_s`；`exploration.turn_bias` 为 `ok`（钉上界）；`exploration.gate_jump_threshold` 为 `ok`。

**A-4 硬约束机检（C1/C3/C5/C6/C7）**

```powershell
# C1 / G5：新增 control.* 赋值行数必须为 0
git diff -U0 -- fly64/ | Select-String '^\+.*\bcontrol\.(x|y|jump)\s*=' | Measure-Object | Select-Object -ExpandProperty Count
#   ↑ 注意：工作树本身有 158 项 M/D，故必须先 `git stash` 到干净起点或限定 diff 范围（见 §9.1）
# C3：不新增第 5 个 jump 门限
(Select-String -Path skills/brain_tunable_params.json -Pattern 'gate_jump').Count   # 期望 1
(Select-String -Path fly64/model.py -Pattern 'jump_rate >').Count                  # 期望 1
# C6：只检"饱和形式"四处逐字不变（F-06 口径：不是"2478 不出现"，而是 2478 仅做门限表达式替换）
git diff -U0 -- fly64/model.py | Select-String 'clip\('    # 期望无输出（2282/2283/2473/2474 四处 clip 不得改动）
git diff -U0 -- fly64/model.py | Select-String '2478' -Context 0,3   # 期望：仅门限表达式一行，clip 形态不变
# C7：教练直写不进自治输出面
Select-String -Path skills/param_history.jsonl -Pattern '"source":\s*"(coach-direct|safety-guard)"' | Measure-Object | Select-Object -ExpandProperty Count
# V20：唯一允许写 .py 的函数
Select-String -Path skills/*.py -Pattern '\.write_text\('
# H-2 基线自证（工作树 vs HEAD 锚点，期望 +5 偏移）
git show HEAD:fly64/skills/fix_executor.py | Select-String 'def execute\(|def _resolve_file'   # 期望 :433 / :598
Select-String -Path fly64/skills/fix_executor.py -Pattern 'def execute\(|def _resolve_file'     # 期望 :438 / :603
```

**A-5 回退命令**：见 §5.3。

### B. 文件清单（按阶段分组）

**修改（16 个文件，17 行含表头）**

> **计数口径（F-02 唯一规则）**：本节按**文件行**计数（本表 16 行 = 16 个被修改文件）；**每条"条目"列内的 ID 一律取 `P0-a#` / `P1-b#`（`b6` 顶层，不展开 `b6-n`）/ `P2-c#` / `M4-d#` 级**，容器不计、别名不计。
> **`main.py` 的修改清单条目数 = 18（唯一口径，三处表述一致，**R-F-02 修正后**）** —— 判据 = 「条目规格的 `文件·行号` 行中 `main.py` 出现，**未被标注为「不改 / 保留、只登记」**，且**别名对只在其中一侧登记**」：
> · **计入（18）**：`a2,a3,a4,a6,a8`(5) + `b1,b2,b3,b4,b5,b6`(6) + `c1,c2,c4`(3) + `d1,d2,d3,d5-f`(4) = **18**
> · **排除（2，no-op）**：`a7`（t1 a7③ 明写 `main.py:49-50`「**不改**」）、`b6-5`（t1 判「**保留、只登记**」，no-op）
> · **别名不重复登记（2，与 t1 §1.1 同规则）**：`a5 ≡ M4-d3`（`:3034-3068` 落点归 **M4-d3** 行）、`d4 ≡ P0-a6`（`:2798-2799`/`:3101-3102`/`:3193-3194` 发布点归 **P0-a6** 行）⇒ 二者**不在本 ID 集内**。**该规则与 t1 §0.4 的 4 对别名声明一致**（每对只在**一侧**写完整规格，另一侧写「同 X」）。
> · **与 §2.1（`P0-a7` 行注）/§4.5 完全一致**（三处均写 **18**）。
> **基线**：`active_strategy.json` 与 `fix_executor.py` 为**工作树基线**（见 §0.5）；其余 14 个文件 HEAD ≡ 工作树（两者等价）。

| 文件 | 阶段 | 条目 |
|---|---|---|
| `fly64/fly64/memory.py` | SP1·SP5 | `a2`（`:133-139,205-209,1985-1995`）、`a3`（`:226-229`）、`c1`（`:1347-1373`）、`c2`（`:1319-1321`）、`c3`（`:1281,1289-1317,1394,1377-1462`） |
| `fly64/fly64/main.py` | SP1·SP3·SP4·SP5 | **`a2,a3,a4`【BT1】+ `a6`（`:1419-1425`，t1 P0-a6，BT1）+ `a8`（`:1678-1881` 热重载段读回校验，BT3）+ `b1,b2,b3,b4,b5,b6`【BT4·BT5】+ `d1,d2,d3`（`memory.json` 发布点 `:2798-2799`·`:3101-3102`·`:3193-3194`，BT6）+ `d5-f`（教练直写边界 `:2279-2384`/`:2330-2348`/`:2358-2384`/`:1873-1876`，BT6）+ `c1,c2,c4`【BT8】 = **18 条**（**不含 `a7`、`b6-5`**；**`a5` 归 `M4-d3` 行、`d4` 归 `P0-a6` 行**，别名不重复登记）** |
| `fly64/fly64/model.py` | SP1·SP3 | **`a3`（`:2096`，t1 P0-a3；`P0-a2` 的「文件·行号」不含 `model.py` ⇒ 不计 `a2`）** / `b1`（`:1787,639`）、`b2`（`:1769-1778,1882-1890,649-652`）、`b3`（`:2478`）、`b5`（`:2082-2097`）、**`b6-2`（`step()` 内写入 `_kc_activity`）** = **6 条** |
| `fly64/fly64/central_complex.py` | SP3 | `b4`（property）、`b5`（`_no_progress` 门） |
| `fly64/fly64/gain_modulation.py` | SP3 | `b1`（`JUMP_GAIN_MAX`） |
| `fly64/fly64/mushroom_body.py` | SP3 | `b6-1`（`set_adaptive_lr` 接线）、`b6-2`（`_kc_activity` 消费者） |
| `fly64/skills/brain_tunable_params.json` | SP2·SP3 | `a8`、`b1`、`b2`、`b3`、`b5` |
| `fly64/skills/active_strategy.json` | SP2 | `a8` + 迁移 `M1/M2/M3` |
| `fly64/skills/evolution_skill.py` | SP1·SP3·SP4·SP5 | `a7` / `b6` / `d1,d2,d5-a,d5-c` / `c2` |
| `fly64/skills/fix_executor.py` | SP4 | `d1` |
| `fly64/skills/default_patterns.json` | SP3·SP4·SP5 | `b6` / `d5-a` / `c2` |
| `fly64/fly64/instinct_bindings.py` | SP4 | `d5-d` |
| `fly64/tests/test_gate_units.py` | SP3 | `b3`⑦（ratio 版改写） |
| `fly64/tests/test_tunable_wiring.py` | SP2 | `a8`（区间不变式断言） |
| `fly64/contract_registry.json` | SP3 | `b3`（`threshold_unit → ratio`） |
| `fly64/skills/evolution_history.json` | SP1 | `a7`（skill 记录） |

**新增（源/产物）（5 + 4）**

| 文件 | 阶段 | 说明 |
|---|---|---|
| `fly64/fly64/arbitration.py` | SP5 | `ArbitrationState`（`c1` 接口契约 + `c4` 候选/权威） |
| `fly64/skills/param_authority.py` | SP1 | 授权点（租约 + snapshot/restore）；**无控制逻辑** |
| `fly64/skills/fix_guard.py` | SP4 | `is_py_patch(...)`（门禁与守卫**唯一** helper） |
| `fly64/skills/fitness_aa_gate.py` | SP4 | A/A 统计（复用 `BrainMutator.fitness_components`） |
| `fly64/skills/evo_funnel_alarm.py` | SP1 | 漏斗四转化率告警 |
| `fly64/skills/param_wiring_ab.json` | SP1 | A/B 判定产物（`G2`/`V3`） |
| `fly64/skills/fitness_aa_report.json` | SP4 | `{n_windows, p95, bootstrap_ci, k, threshold, aa_two_window_fpr, unmeasurable_dims}` |
| `fly64/skills/change_proposals.jsonl` | SP4 | T3 提案（**不进执行路径**） |
| `fly64/skills/.evo_loop_heartbeat.json` | SP1 | 存活心跳（`{iteration, ts}`） |

**新增测试（18）**：`test_memory_units.py`(SP1) · `test_stuck_duration_true.py`(SP1) · `test_param_wiring_ab.py`(SP1) · `test_evo_liveness.py`(SP1) · `test_evolution_log_context.py`(SP1·SP5) · `test_jump_leg_gain_chain.py`(SP3) · `test_cx_goal_comp_writes.py`(SP3) · `test_jump_homeostat.py`(SP3) · `test_jump_gate_ratio.py`(SP3) · `test_cx_loop_break_gate.py`(SP3) · `test_evolution_fix_contract.py`(SP4) · `test_pattern_reachability.py`(SP4) · `test_fix_lifecycle.py`(SP4) · `test_fitness_aa_gate.py`(SP4) · `test_fitness_window_alignment.py`(SP4) · `test_arbitration_state.py`(SP5) · `test_terminal_surrender.py`(SP5) · `test_oscillation_window.py`(SP5) —— **共 18 个 `test_*.py`**（上列即 18 项，逐项点名；`test_evolution_log_context.py` 跨 SP1/SP5）。
> **F-07 口径说明**：**本枚举 = 18 个**（t1 §7 的全部"（新增）"测试落点）；t1 §7 中另被引用但**非新增**的 4 个文件为 `test_gate_units.py`（**改写**）、`test_tunable_wiring.py`（**扩展**）、`test_mushroom_body.py` / `test_mbon_saturation.py`（**既有回归基线**）⇒ 不计入"新增 18"。**全文凡"新增测试文件"一律写 18**（原写 17 为漏计 `test_cx_loop_break_gate.py`，本行修正）。

**`memory.json` 新增键（落点，非独立文件）**：`param_authority`、`clamped_keys`、`param_write_mismatch`、`evo_loop_stale`、`stuck_duration_true`、`stuck_score_degenerate`。

### C. 交付物与后续任务

| 项 | 内容 |
|---|---|
| 本计划 | `docs/execution/fly64-execution-plan.md`（本文件） |
| 上游规格 | docs/execution/fly64-change-specs.md（	1，**叶子条目 32 个**（标题计数 34）的九字段规格） |
| 源方案 | `docs/analysis/fly64-autonomy-evolution-plan.md`（判定层 + V/R/H 三张表） |
| 后续任务（建议） | ① 真实连接组 cache 就位后**关闭 H5/H6/H11/H12**（SP3 上线前置）；② `G4` 的 A/A 标定实验（≥100 窗 + ≥50 对双窗）单独成任务；③ SP7（P3）的守护与调度实现单独成任务；④ 本计划**不包含**任何代码实现 |

### D. 本计划明确**不**做的事（防误读为遗漏）

1. **不重新设计任何机制**（骨架冻结于原方案 §4–§7，条目冻结于 t1 的 **32 个叶子条目**（标题计数 34））。
2. **不改 `_vote()` 的优先顺序**（C5；PIN 由 `V13①` 保证）。
3. **不改 `raw_x` / `raw_y` / `jump` 的饱和形式**（C6）：四处 `clip(·,±70)` 逐字不变（`model.py:2282`、`:2283`、`:2473`、`:2474`）；`model.py:2478` **仅做门限表达式替换**（绝对门 `> 0.04` → 比值门）。
4. **不降低 `PROMOTE_MIN_IMPROVED`**（`instinct_bindings.py` 的负结果记录明确禁止；只修上游证据链）。
5. **不新增第 5 个 jump 门限**（C3：同 key 替换 + `grep` 计数判据）。
6. **不放宽 `GAIN_MIN = 0.5`**（只对 jump 通路单独设 `JUMP_GAIN_MAX = 4.0`，且该常量标**可撤回**，需 A/B 通过）。
7. **不删除教练直写控制通道**（C7：只把它移出自治输出面，`source` 统一记为 `coach-direct` / `safety-guard`）。
8. **不在闭环执行路径上执行任何 `.py` 补丁**（P1 硬约束；T3 降级为提案，V20 三道理）。
9. **不新增任何 V 指标**（V1–V22 是 §10 的完整集合）。
10. **不代为标定任何 `【待标定】` 取值**（`σ_floor`、`dwell_ticks`、`T_s/L/W/D`、`OSC_CYCLES_PER_WINDOW`、`jump_awake_*`、`jump_homeo_floor`、`jump_intrinsic_max` 的最终取值一律由实测标定）。

---

**（完）** 本文件共 **6 个实施阶段 / 10 个提交批次 / 6 个硬门 / 3 条红灯 / 22 项 V 指标 / 13 条 R 回退 / 14 项假设分级**，与 docs/execution/fly64-change-specs.md 的 **32 个叶子条目**（标题计数 34）一一对应。
