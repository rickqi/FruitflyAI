# Fly64 实施变更规格（Change Specs）— 文件级施工规格

> **条目计数口径（唯一，F-01 固定 + t4 校正）**：
> · **标题叶子 = 32（唯一权威口径）**。推导：`### P0/P1/P2/M4-` 二级标题 = **23**（其中 `P1-b6`、`M4-d5` 是**分组容器**）；`#### P1-b6-n / M4-d5-x` 子标题 = **11** ⇒ **23 − 2 + 11 = 32**。
> · **32 的构成**：`P0-a1…a8`(8) + `P1-b1,b2,b3,b4,b5`(5) + `P1-b6-1…b6-5`(5) + `P2-c1…c4`(4) + `M4-d1,d2,d3,d4`(4) + `M4-d5-a…d5-f`(6) = **32** ✓（容器 `P1-b6`、`M4-d5` **不计**）
> · **别名（同一改动的两侧登记，**不参与计数**） = 4 对** —— `P0-a5 ≡ M4-d3`、`P0-a6 ≡ M4-d4`、`P0-a7 ≡ M4-d5-e`、`M4-d5-b ≡ P2-c2`。每对本文件只在**一侧**写完整规格、另一侧写「同 X」⇒ **不得再由 32 加减别名数**（t4 校正：先前"34 − 2 = 32"的算式把**容器**与**别名**混在一起，**作废**；别名对也不用于减法）。
> · **矩阵的归属规则（与别名块配套，用于"条目数"列）**：**每对别名只在既定一侧登记** —— `P0-a5`(≡`M4-d3`) 的 `main.py:3034-3068` 归 **`M4-d3` 行**；`P0-a6`(≡`M4-d4`) 的 `main.py:1419-1425` 与 `main.py:2798-2799`/`:3101-3102`/`:3193-3194` 归 **`P0-a6` 行**。⇒ `main.py` 格**不含 `a5`、不含 `d4`**，其 **18 = 5+6+3+4** 可由格内列举逐项导出（满足「条目数列 = 格内 ID 数之和」）。
> · **引用规则（唯一）**：凡陈述"条目数"一律写 **「32 个叶子条目」**；`P1-b6` 与 `M4-d5` **不是可施工单位**，只是分组容器。
> · **与执行计划的对接**：`docs/execution/fly64-execution-plan.md` 的 `BT0–BT9` 批次覆盖同一 **32** 个叶子条目（其 §2.1 表 33 行 − 1 行 `--history-check` 复述行 = 32）。

> **交付物**: `docs/execution/fly64-change-specs.md`
> **来源方案**: `docs/analysis/fly64-autonomy-evolution-plan.md`（1122 行，HEAD `cca66648a204043d881da502cf996b15882ad289`）
> **生成者**: execution-designer · 团队 `fly64-exec-plan-gen` · 任务 `t1`
> **attempt_id**: `15f5e26b-dd98-420a-b0d0-c51769a29545`
> **代码基线（t4 校正为双基线，见 §0.4a）**: `git rev-parse HEAD` = `cca66648a204043d881da502cf996b15882ad289`，**但本文件的行号/「改前」原文实际取自当前工作树**（`git status` 有 158 项 M/D，其中 `active_strategy.json` 与 `fix_executor.py` **与 HEAD 不一致**）。**逐文件基线来源见 §0.4a**。
> **本文件的性质**: **只写"改哪里、改成什么、怎么判定"**。不引入任何新设计条目（骨架冻结于原方案 §4–§7）；
> 凡原方案未定的取值，本文件标注 `【待标定】`并给出标定入口，**不代为断言**。
>
> **修订记录**：
> · **t3 返修**：F-01 条目计数口径（→ 见文件头口径块，**最终为 32**）；F-02 修正 §1.1 矩阵；
>   F-03 修正 `active_strategy.json` 行号（`turn_bias` 活值在 `:4`，非 `:3`；P0-a8 引用段为 `:5-8`）；
>   F-04 补齐 P0-a8 落点④的**运行期读回校验**（`main.py:1864-1878` 之后、`:1879` 之前，含锚点改前原文）
>   与测试侧扩展点的精确文件说明；F-06 重写 C6 判据（只检饱和形式 `clip(·,±70)`，`model.py:2478` 仅允许门限表达式替换）。
> · **t4 返修（本次）**：**H-1/H-2 基线一致性**（新增 §0.4a：`active_strategy.json` 与 `fix_executor.py`
>   与 HEAD 不一致，三项迁移与 M4-d1 的锚点改为**双基线记录**）；**F-01 残留**（删去"34 − 2"算式，
>   改为标题结构推导的 **32**，并声明 4 对别名**不参与计数**）；**F-02 残留**（§1.1 的
>   `main.py`/`model.py` 格与条目数按「文件·行号」实测重算：main.py **18**（不含 `a7`/`a5`）、
>   model.py **6**（不含 `a2`））；**F-03 复核**（行号修正基于**工作树**，已按 §0.4a 声明）；
>   **F-07**（新增测试文件 **18**，与执行计划一致）。
> **未改动**：全部机制设计、V/R 归属、硬约束 C1–C5/C7、证据边界与 H 假设标注。

---

## 0. 阅读约定（施工前必读）

### 0.1 每项规格的字段含义

| 字段 | 含义 | 施工要求 |
|---|---|---|
| **ID** | 稳定条目号（`P0-a2` / `P1-b1` / `P2-c1` / `M4-d3`） | 提交信息、PR 标题、回退脚本一律以 ID 定位 |
| **文件·行号** | HEAD `cca66648` 上的**行区间**（本文件已逐一打开核对） | 行号会随施工漂移；**只允许按 `改前原文` 字符串定位**，行号仅作导航 |
| **改前** | HEAD 上的**逐字原文** | 删除/替换时必须字符串精确匹配（含缩进） |
| **改后** | 目标形态 | 若含 `【待标定】`，先标定再落值 |
| **接口/常量** | 新增/改签名的函数、字段、常量 | 签名未定 ⇒ 不得进入实现 |
| **依赖** | 必须**先完成**的前序 ID | 违反 ⇒ 该条不可上线（见 §12 关键路径） |
| **V 指标** | 归属的 §10 可验证指标 | 无 V 指标 ⇒ 不得施工（硬约束 C4） |
| **R 回退** | 归属的 §11 风险条目 | 无 R 条目 ⇒ 不得施工（硬约束 C4） |
| **假设** | 依赖真实连接组/不可复现证据的部分（H5/H6/H11…） | **不得写成断言**；只能作为"通过 A/B 后确认"的待验项 |

### 0.2 全线硬约束（逐条可机检）

| # | 约束 | 机检方式 |
|---|---|---|
| **C1** | 不新增任何 `control.x` / `control.y` / `control.jump` 写入点 | `fly64/tests/test_evolution_fix_contract.py`（新增）静态断言：新增 `control.*` 赋值行数 = 0（以 `git diff -U0` 的行计数为准） |
| **C2** | M1 全部修复形态只能是"**让已有信号到达**" | 逐条复核 `改后` 是否引入新判定分支；M1 六条（§5.1–§5.6）的 `改后` 必须是"扩面/替换口径/加稳态/修死写入"之一 |
| **C3** | **不新增第 5 个 jump 门限**（用替换） | `grep -n "gate_jump" fly64/skills/brain_tunable_params.json` 仍恰好 1 个 pid；`grep -c "jump_rate >" fly64/fly64/model.py` 仍恰好 1 处 |
| **C4** | 每条改动必须带**可判定观测指标 + 阈值 + 自动回退** | 本文件每条 ID 的 `V` 与 `R` 字段非空；CI 校验本文件条目完整性 |
| **C5** | `_vote()` 的优先顺序不得改动 | §6.1.1 的 PIN 断言（`allowed is None` ⇒ 逐 tick 相同） |
| **C6** | `raw_x` / `raw_y` / `jump` 的**饱和形式**不得改动 | **只检饱和形式，不禁止引用行号**：`model.py:2282` 的 `clip((forward_rate - 0.008) * 2000.0, 0, 70)`、`model.py:2283` 的 `clip(turn_rate * 1100.0, -70, 70)`、`model.py:2473-2474` 的 `clip(raw_y, 0, 70)` / `clip(raw_x, -70, 70)` 四处**逐字不变**；`model.py:2478` **仅允许门限表达式替换**（P1-b3：绝对门 `> 0.04` → 比值门，**饱和形式不在该行**），除此之外 2478 不得出现新的门限（C3） |
| **C7** | 教练直写控制通道保留但不进自治输出面 | `param_authority` 不记录 `main.py:2279-2384` 的写入（§7.5-f） |

### 0.3 证据边界（**不得把假设写成断言**）

| 事实 | 后果 |
|---|---|
| 本机**无 `memory.json`**、**无 `.cache/malecns/manifest.json`** | 真实连接组运行点**不可离线复现**；`E-4` 层全部数值（`stuck_score=1.0`、`stuck_duration=1100.72`、`reflex_active=False`、`median_speed=0.0`）**只作被审视对象**，一律标「检测伪影」+ H1 |
| `.tmp/fly64_trajectory.json`（6000 点）与 HEAD **不相容** | 不得用它证明 HEAD 行为；只允许引用其**运动学统计**（X 效率 2.75%、Z 效率 5.35%、静止 1385/5999、`jump` 0/6000、`ctrl_x` 满量程 5330/6000） |
| 探针 `FlyModel(demo=True)` 发放退化为 100% | 一切**发放率相关阈值**（`jump_leg_current` 绝对值、`jump_pool_occupancy` 绝对值、0.18127 缺口、5.517× 稳态）**只能证明算术/接线可达性**，真实阈值须在真实连接组上 A/B 确认（**H5**） |
| 跳池 < 0.04 而前向池 ≈ 0.043 的断口 | **H6**，需真实连接组发放率读数确认；§5.3 的必要性依赖它 |
| MBON 腿是有效注入腿 | **H11**，`model.py:1787` 注入点存在 + 算术可达已证；真实增益效果未证 |
| `gain("jump")` 的 `[0.5, 2.5]` 上限是否过低 | **H12**；`JUMP_GAIN_MAX = 4.0` 为**可撤回项**（若 2.5 已足够则删除该新增常量） |
| 长窗 + 轨迹运动学 fitness 可分辨 | **H13**；A/A 门实测是唯一关闭方式 |
| `dwell_ticks = 1500` | **H14**；仅设计初值，需复现场景标定 |
| CX 环路突破"恒不可达"是条件性的 | **H7**；仅当目标向量在供时为真 |

> **本文件所有 `【H5/H6/H11】` 标注处，禁止在验收报告中改写为"已确认"。**

### 0.4 HEAD 核对后对原方案的三处 `file:line` 校正（不改结论）

| # | 原方案写法 | HEAD 实测 | 处置 |
|---|---|---|---|
| **X1** | §4 P0-a2 / §8 写"`StuckDetector` 单位对齐 `memory.py:135,206-217` ← `main.py:2650`" | `main.py:2650` 是 **`memory_ctrl.update(...)` 调用内的 `forward_rate=getattr(control,'forward_rate',0.0)` 实参行**（正确）；但**真正需要改单位的第二处在 `memory.py:135` 的 `rate_threshold=5.0` 声明**，而比较式在 `memory.py:206`。两处都要改，缺一不可 | 本文件 `P0-a2` 明确写出**两个改动点**，避免只改一处 |
| **X2** | §7.5-d 写 `instinct_bindings.py`（无路径） | 实际路径为 **`fly64/fly64/instinct_bindings.py`**（全仓唯一，408 行）；`fly64/skills/instinct_bindings.py` **不存在** | 本文件统一使用 `fly64/fly64/instinct_bindings.py` |
| **X3** | §7.1 T3 断言文件写作 `fly64/tests/test_evolution_fix_contract.py`（F15 已校正目录） | **该文件当前不存在**（`Test-Path` = False）；`fly64/tests/` 下现有 98 个 `test_*.py` | 本文件标注为**新增**文件 |

### 0.4a 基线完整性声明（**H-1 / H-2，t4 返修新增**）

> **结论**：本文件的全部行号与「改前」原文**实际取自当前工作树**，不是干净 HEAD。`git status --porcelain` 实测 **158 项 M/D**，其中**2 个被引用文件与 HEAD 不一致**。基线的**操作性选择 = 工作树**（运行时脑消费磁盘上的实际文件），但引用必须**逐文件标明来源**。

| 文件 | HEAD（`git show HEAD:<path>`） | 工作树（`Get-Content`） | 处置 |
|---|---|---|---|
| `fly64/skills/active_strategy.json`（`git status` = **`M`**） | **21 行**（`\n` 计 20）：`exploration` 段全部是**扁平点号键**；`:4 = "exploration.bold_explore_stuck_s": 47.55773365137824`、`:7 = "exploration.gate_jump_threshold": 3.082271242248696`、`:14 = "escape.commit_ticks"`、`__generation: 134`；**无 `turn_bias`、无 `navigation` 段** | **55 行**：`:4 = "turn_bias": 0.25`、`:5 = "bold_explore_stuck_s": 60.0`、`:8 = "gate_jump_threshold": 3.082271242248696`、`:33-38 = navigation`（`0.12`/`45.0`）、`__generation: 332` | §6 的 `M1`/`M2`/`M3` 与 `P1-b4` 的 `:33-38`：**「改前」取工作树**；**同处并存 HEAD 变体**（M1 的 HEAD 值是 `47.55773365137824`、键为扁平点号、门限在 `:7`）。**两值都越界注册 `[1,10]` ⇒ 静默钳位结论不变** |
| `fly64/skills/fix_executor.py`（`git status` = **`M`**） | **862 行**（**采用口径 = 物理行数 = `U+000A` + 无尾换行修正**，见下方「口径定义」）：`def execute(` = **:433**、`directives = parse_fix_template(fix_template)` = **:464**、`file_rel = directive.get("file","")` = **:483**、`def _resolve_file` = **:598**、`rel = file_rel or (…)` = **:604** | **867 行**（同口径）：同五锚点 = **:438 / :469 / :488 / :603 / :609** | `M4-d1` 的四个锚点**按所选基线给号**：工作树 = **`:438 / :469 / :488 / :603`**；HEAD = **`:433 / :464 / :483 / :598`**。**偏移量（本机字节级实测）**：总行数 **862 → 867（+5）**；五个锚点全部**净 +5**（`:433→:438`、`:464→:469`、`:483→:488`、`:598→:603`、`:604→:609`）⇒ **运行时守卫必须插在 `execute` 入口**（工作树 `:438` 之后、`parse_fix_template` 调用 `:469` 之前），锚点错位即插错位置 |

**行数计数口径定义（唯一，与执行计划 §0.5.1 逐字一致；t7 复核后按字节级实测更正）**

> **采用口径 = 物理行数 = `U+000A` 个数 + (无尾换行 ? 1 : 0)**，等价于 `[IO.File]::ReadAllLines(path).Count` / `wc -l` 行数语义。
> · **HEAD = 862**（U+000A **861** + 1，**无尾换行**）、**工作树 = 867**（U+000A **866** + 1，**无尾换行**）⇒ **差值 = +5**。
> **可复现命令（以字节级为准）**：
> ```powershell
> python -c "import subprocess,pathlib; h=subprocess.run(['git','show','HEAD:fly64/skills/fix_executor.py'],capture_output=True).stdout; w=pathlib.Path('fly64/skills/fix_executor.py').read_bytes(); print('HEAD', h.count(b'\n'), '->', h.count(b'\n')+(0 if h.endswith(b'\n') else 1)); print('WT', w.count(b'\n'), '->', w.count(b'\n')+(0 if w.endswith(b'\n') else 1))"
> # 期望：HEAD 861 -> 862 ; WT 866 -> 867
> [IO.File]::ReadAllLines((Resolve-Path 'fly64/skills/fix_executor.py')).Count   # 867
> (git show HEAD:fly64/skills/fix_executor.py).Split("`n").Length              # 862
> # ⚠ 不可用 `Get-Content <path> -split "`n"`：对无尾换行文件少计 1 行（WT 得 866）
> ```
> **易混口径对照（**本文件不采用**，仅用于识别历史数字来源）**：
> | 口径 | HEAD | 工作树 | 来源 |
> |---|---|---|---|
> | **物理行数（**采用**）** | **862** | **867** | `ReadAllLines().Count` / `wc -l` |
> | 仅数 `U+000A`（不加尾修正） | 861 | 866 | t6 一度误用 ⇒ 工作树误写 866 |
> | 非空行计数（`Measure-Object -Line`） | 746 | 751 | 旧稿「746」 |
> | `Get-Content <path> -split "\`n"` | 862 | 866 | PowerShell 对无尾换行的拆分差异 |
> ⇒ 历史数字属**口径混淆**（源自 captain 早期指导 + 我 t6 的过度更正）；**事实值为 862 / 867**。
> **偏移构成（逐区域字节级实测，t7 复核后更正）= +5 / 0 / 0**：**region1（`def execute` 之前）= 432 → 437 ⇒ +5**（新增的 5 行全部落在此处：`if extracted_file:` 卫语句 + 4 行注释）；**region2（`execute` .. `_resolve_file`−1）= 165 → 165 ⇒ +0**（与 HEAD **逐字节相同**）；**region3（`_resolve_file` .. 末尾）= 264 → 264 ⇒ +0**（与 HEAD **逐字节相同**）⇒ **总行数 +5、五锚点累计 +5**。
> **复现**：`python -c "import subprocess,pathlib; h=subprocess.run(['git','show','HEAD:fly64/skills/fix_executor.py'],capture_output=True).stdout.split(b'\n'); w=pathlib.Path('fly64/skills/fix_executor.py').read_bytes().split(b'\n'); f=lambda L,p:[i for i,l in enumerate(L,1) if p in l][0]; he,hr=f(h,b'def execute('),f(h,b'def _resolve_file'); we,wr=f(w,b'def execute('),f(w,b'def _resolve_file'); print('r1',he-1,we-1,we-he); print('r2',hr-he,wr-we,(wr-we)-(hr-he)); print('r3',len(h)-hr,len(w)-wr,(len(w)-wr)-(len(h)-hr)); print('total',len(h),len(w),len(w)-len(h))"` ⇒ 期望 `r1 432 437 +5` / `r2 165 165 +0` / `r3 264 264 +0` / `total 862 867 +5`。

**逐文件基线来源**：除上表两个文件外，本文件引用的其余文件（`main.py`、`model.py`、`memory.py`、`central_complex.py`、`gain_modulation.py`、`mushroom_body.py`、`instinct_bindings.py`、`motor_primitives.py`、`evolution_skill.py`、`brain_tunable_params.json`、`default_patterns.json`、`evolution_history.json`、`contract_registry.json`、`tests/test_gate_units.py`、`tests/test_tunable_wiring.py`、`plugin/scene_context.py`、`plugin/coach_outcomes.py`）经 `git status --porcelain` 判定为 **clean** ⇒ **HEAD 与工作树等价**，其行号对两者都成立。

**与执行计划的对接**：`docs/execution/fly64-execution-plan.md` **§0.5** 给出同一双基线声明，并把「工作树干净」从 Pre-flight 中**移除**，改为**逐文件内容自证**（行数 + 关键键值 + 锚点行号）。

**复现命令**：
```powershell
git rev-parse HEAD                                     # cca66648a204043d881da502cf996b15882ad289
git status --porcelain | Measure-Object -Line          # 158 项 M/D
git status --short fly64/skills/active_strategy.json fly64/skills/fix_executor.py   # 两条 M
git show HEAD:fly64/skills/active_strategy.json        # HEAD 变体（21 行、扁平点号键）
git show HEAD:fly64/skills/fix_executor.py | Select-String 'def execute\(|def _resolve_file'   # :433 / :598
```

### 0.4b 批次命名消歧（**R-F-05，t5 新增**）

> 本文件 §9 的批次表是**提交批次**（一次 `git commit` + 一个 tag），一律写作 **`BT0`–`BT9`**（**BT = Batch**）。
> **绝不要**与源方案 `docs/analysis/fly64-autonomy-evolution-plan.md` **§3** 的「**A 类 11 项 / B 类 5 项**」中的
> **B 类**（`B1`–`B5` = 自治缺失 5 项）混淆 —— **两者同名异义、彼此无关**：
> · 凡本文件出现 `BT#`（带 `T`）⇒ **提交批次**（§9 的 10 个批次）；
> · 凡出现 **`B1`–`B5`**（无 `T`）⇒ **源 §3 的 B 类问题标签**（B1 无行为决定变量级作用点 / B2 无竞争升级回退语义 / B3 无可判别适应度 / B4 无情景责任链 / B5 无自观测）。
> 与执行计划的对应：`docs/execution/fly64-execution-plan.md` **§0.4** 的「批次（BT）」行给出同一消歧声明；其 §5.5.2 表列出 B 类 5 项。

---

## 1. 全景变更表（按阶段）

### 1.1 文件 × 条目矩阵（施工排期用）

| 文件 | P0 | P1 | P2 | M4 | 条目数 |
|---|---|---|---|---|---|
| `fly64/fly64/memory.py` | a2,a3 | — | c1,c2,c3 | — | 5 |
| `fly64/fly64/main.py` | **a2,a3,a4,a6,a8**（**不含 `a7`**：其「文件·行号」把 `main.py:49-50` 标「不改」；**不含 `a5`**：`a5 ≡ M4-d3` 的 `main.py:3034-3068` 落点**归 M4-d3 行登记**，本格不重复） | b1,b2,b3,b4,b5,b6（含 `b6-1…b6-4`；`b6-5` 为**保留/只登记**的 no-op，不计） | c1,c2,c4（`c3` 只改 `memory.py`） | **d1,d2,d3,d5-f**（**不含 `d4`**：`d4 ≡ P0-a6` 的 `:1419-1425` 落点**归 `P0-a6` 行登记**，本格不重复；`d5-f` 改 `main.py:2279-2384`/`:2330-2348`/`:2358-2384`/`:1873-1876`；`d5-a`/`d5-b`/`d5-c`/`d5-d`/`d5-e` 的主落点不在 `main.py`） | **18** |
| `fly64/fly64/model.py` | **a3**（**不含 `a2`**：t1 P0-a2 的「文件·行号」只有 `memory.py` 三处 + `main.py:2647-2650`，**不含 `model.py`**；`model.py:2096` 是 `P0-a3` 的外溢链落点） | b1,b2,b3,b5,b6（`b6-2` 的写入落点在 `model.py`） | — | — | **6** |
| `fly64/fly64/central_complex.py` | — | b4,b5 | — | — | 2 |
| `fly64/fly64/gain_modulation.py` | — | b1 | — | — | 1 |
| `fly64/fly64/mushroom_body.py` | — | b6 | — | — | 1 |
| `fly64/fly64/arbitration.py` | — | — | c1,c4 | — | 2（**新增文件**） |
| `fly64/fly64/instinct_bindings.py` | — | — | — | d5-d | 1 |
| `fly64/plugin/scene_context.py` | — | b6-4 | — | — | 1 |
| `fly64/plugin/coach_outcomes.py` | — | — | — | d5-d | 1 |
| `fly64/skills/brain_tunable_params.json` | a8 | b1,b2,b3,b5 | — | — | 5 |
| `fly64/skills/active_strategy.json` | a8 | — | — | d1 | 2（含迁移） |
| `fly64/skills/evolution_skill.py` | a4,a7 | — | — | d1,d2,d3,d4,d5 | 7 |
| `fly64/skills/fix_executor.py` | — | — | — | d1 | 1 |
| `fly64/skills/fix_catalog.json` | — | — | — | d5-c | 1 |
| `fly64/skills/default_patterns.json` | — | b6 | c2 | d5-a,d5-b | 4 |
| `fly64/skills/param_authority.py` | a4 | — | — | — | 1（**新增文件**） |
| `fly64/skills/fix_guard.py` | — | — | — | d1 | 1（**新增文件**） |
| `fly64/skills/fitness_aa_gate.py` | — | — | — | d2 | 1（**新增文件**） |
| `fly64/skills/evo_funnel_alarm.py` | — | — | — | d4 | 1（**新增文件**） |
| `fly64/skills/change_proposals.jsonl` | — | — | — | d1 | 1（**新增产物**） |
| `fly64/skills/evolution_history.json` | a7 | — | — | — | 1 |
| `fly64/tests/test_tunable_wiring.py` | a8 | — | — | — | 1（**扩展**已有断言） |
| `fly64/tests/test_gate_units.py` | — | b3 | — | — | 1（**改写**为 ratio 契约） |
| `fly64/tests/test_evolution_fix_contract.py` | — | — | — | d1 | 1（**新增**） |
| `fly64/contract_registry.json` | — | b3 | — | — | 1 |

> **矩阵口径**（F-02 修正后固定）：格内列出**该文件被哪些叶子条目改动**（`a8` 与 `d1` 对 `active_strategy.json` 分别为"迁移"与"有界写入"两种改法，故计 2）；**条目数列 = 格内 ID 数之和**（必须逐格核对）；**别名（同一改动的多处登记）只登记在既定的一侧，不在两侧重复列举** —— `P0-a5 ≡ M4-d3`（归 M4-d3 行）、`P0-a6 ≡ M4-d4`（归 P0-a6 行）、`P0-a7 ≡ M4-d5-e`、`M4-d5-b ≡ P2-c2` ⇒ `main.py` 格**不含 `a5` 与 `d4`**，其 **18 = `a2,a3,a4,a6,a8`(5) + `b1..b6`(6) + `c1,c2,c4`(3) + `d1,d2,d3,d5-f`(4)** 自洽；同理 `model.py` 格不含 `a2`；**只列施工要动/要新增的文件**，`fly64/tests/` 下 §7 新增的 18 个测试文件不在本矩阵（它们是验证落点，见 §7），仅列 3 个与施工同批的测试/契约文件。

### 1.2 阶段依赖与关键路径

```
P0-a1(设计冻结) ─┬─→ P0-a2(单位对齐) ─→ P0-a3(时长重算) ─┐
                 ├─→ P0-a4(A/B 判据+授权点) ──────────────┤
                 ├─→ P0-a5(观测落盘)  ─────────────────────┤
                 ├─→ P0-a6(告警+存活) ─────────────────────┤
                 ├─→ P0-a7(版本红灯) ──────────────────────┤
                 └─→ P0-a8(区间不变式+迁移) ───────────────┤
                                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │ P1-b1 ★位精确回归必须先过                        │
                    │ P1-b2 / P1-b3(依赖 a8 迁移) / P1-b4 / P1-b5 / P1-b6 │
                    │ 出口门: P1 判据④「无一条新增 control.* 写入点」  │
                    └───────────────────────┬─────────────────────────┘
                                            ▼
                    ┌─────────────────────────────────────────────────┐
                    │ P2-c1/c2/c3/c4  +  M4-d1/d2/d3/d4/d5            │
                    │ d2(A/A 门) 可在 P1 之前以 shadow 模式先行        │
                    │ 出口门: d2 A/A 门通过 ⇒ 才允许打开自动 commit    │
                    └─────────────────────────────────────────────────┘
```

**关键路径（原方案 §8）**: `P0-a2 → P0-a4 → P1-b1/b2/b3 → P2-d2(A/A 门) → P3-auto`
**阻断关系（必须机检的硬门）**:

| 门 | 判据 | 失败后果 |
|---|---|---|
| G1 | P0-a8 的 `clamp(live)==live` 对 **39/39** pid 通过 | **阻断 P1 全部条目上线** |
| G2 | P0-a4 的运行时 A/B 可用（产出 `param_wiring_ab.json`） | P1 各条无接线判据 ⇒ 全部不得进入 A/B 阶段 |
| G3 | P1-b1 的**位精确回归**通过 | 立即回滚 P1-b1，**不得进入 A/B** |
| G4 | P2-d2 的 A/A 门通过（`bootstrap_upper95(P95) ≤ σ_floor`，n≥100） | **禁止**任何 fitness 变更与自动 commit（保持 shadow） |
| G5 | P1 出口判据④：新增 `control.*` 写入点 = 0 | P1 整体不得上线 |
| G6 | P2-d1 的 T3 门禁 + 运行时守卫通过 | **阻断 P2 上线** |

---

## 2. P0 变更规格（§4 · M3 观测/口径层 — **不改行为**）

> P0 的验收标准是"**能分辨**"，不是"变好"。**P0 任何一条不得修改 `control.*`，不得修改 `model.py:2282/2283/2478`。**

### P0-a1 — 唯一口径表（设计冻结）

| 字段 | 内容 |
|---|---|
| **文件·行号** | 无代码改动；冻结产物 = `docs/execution/fly64-change-specs.md`（本文件）§2/§5/§6 + `fly64/contract_registry.json:86-105` 的 `unit_contract` 块作为登记口径 |
| **改前** | 系统内"跳"同时存在 **4 个互不一致的门限口径**（逐字引用）：<br>① LIF 解码门（`fly64/fly64/model.py:2478`，**唯一执行门**）：`        jump = jump_rate > 0.04 and now - self.last_jump >= 0.8`<br>② 遥测镜像（`fly64/fly64/main.py:3064`，只上报）：`                    "jump_not_active": getattr(control, "jump_rate", 0.0) < 0.04,`<br>③ 参数门（`fly64/skills/brain_tunable_params.json:38-43`；`fly64/skills/active_strategy.json:8`，只进 `flow.json` 与教练上下文）：`      "default": 8.0,` / `      "min": 2.0,` / `      "max": 20.0,`（Hz）；线上活值 `    "gate_jump_threshold": 3.082271242248696,`<br>④ 遥测独立门 `> 2.` Hz（`fly64/plugin/telemetry.py:94`，只上报）<br>**消费方说明（F15）**：`fly64/plugin/scene_context.py:233-234` 消费的是**布尔量** `gate_forward` / `gate_jump`（`        gate_jump=bool(_get_safe(flow, "gate_jump", default=False)),`），**不是阈值本身**；阈值在 `main.py:2894` 被读、`:2953-2954` 以 `gate_*_threshold_hz` 发布 |
| **改后** | 冻结为**两口径 + 一次声明**：<br>· **行为门（唯一）**：`jump = jump_rate > r · max(forward_rate, FWD_RATIO_FLOOR)`，`r = exploration.gate_jump_threshold`（P1-b3 落值）<br>· **遥测镜像**：与行为门**同式同源**（P1-b3⑦ 同批改 `main.py:2953-2957`）<br>· **遥测独立门 `telemetry.py:94` 的 `2.` Hz 字面量**：登记为 `known_divergence`，**本阶段只登记不改**（改它属遥测层，且它不是行为门；若改则必须与 P1-b3 同批，否则新增第 5 个口径） |
| **接口/常量** | 冻结登记项（写入 `contract_registry.json` 的 `unit_contract.threshold_unit`）：`FWD_RATIO_FLOOR = 0.008`（定义域下限）、`r ∈ [0.25, 4.0]`、`default = 0.75`、`unit = "ratio (dimensionless)"` |
| **依赖** | — |
| **V 指标** | V6、V22 |
| **R 回退** | R13（契约未同步 ⇒ 本冻结项整体不切换） |
| **假设** | **H6**（前向池 ≈0.043 / 跳池 <0.04 的断口需真实连接组确认） |

### P0-a2 — `StuckDetector` 单位对齐 + 泄放空操作修复（**伪影链切断**）

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① `fly64/fly64/memory.py:133-139`（声明）<br>② `fly64/fly64/memory.py:205-209`（比较式）<br>③ `fly64/fly64/main.py:2647-2650`（实参）<br>④ `fly64/fly64/memory.py:1985` vs `:1993-1995`（泄放空操作）<br>⑤ **同批记录（本项不改，由 P0-a3 接管）**：`fly64/fly64/main.py:2687` → `fly64/fly64/model.py:2096` 的外溢链 —— `main.py:2687` 的当前引用是 `                model.stuck_duration = memory_ctrl.stuck_duration`（P0-a2 完成后该量**仍不可信**，故**必须在 P0-a3 同批**改为 `stuck_duration_true`，否则不可信量会继续外溢到 CX） |
| **改前** | ① `memory.py:135`：`                 rate_threshold: float = 5.0,`<br>② `memory.py:206`：`        if forward_rate < self.rate_threshold:`<br>③ `main.py:2650`：`                    forward_rate=getattr(control, 'forward_rate', 0.0),`<br>④ `memory.py:1985`：`        self._stuck_score, self._stuck_duration, self._fallen = self.stuck.update(` … `:1987` `        )`<br>　 `memory.py:1993-1995`：<br>　 `        _disp_60s = getattr(self, "disp_60s", None)`<br>　 `        if _disp_60s is not None and _disp_60s > 500.0 and self._stuck_duration > 0.0:`<br>　 `            self._stuck_duration = max(0.0, self._stuck_duration - 1.0)` |
| **改后** | ① **统一到 per-tick 比例域**（与 `control.forward_rate` 同域）：<br>　 `                 rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`<br>② 比较式加**显式单位注释**并保持单口径：<br>　 `        # P0-a2: both sides are per-tick fractions ∈ [0,1] (see RULE-19).`<br>　 `        if forward_rate < self.rate_threshold:`<br>③ 实参**加钳位与显式类型**（防 None/越界）：<br>　 `                    forward_rate=float(np.clip(getattr(control, 'forward_rate', 0.0), 0.0, 1.0)),`<br>④ **泄放必须写在 `:1985` 之后但作用于本 tick 的最终值**（消除"每 tick 被覆盖"的空操作）：把泄放实现为 **`StuckDetector` 内的有状态泄放**（在 `_stuck_duration` 自增的同一处减），或把 `:1993-1995` 的泄放**移到 `:1985` 之前对 `self.stuck._stuck_duration` 生效**。**二选一，必须同步删除原 `:1993-1995` 块**（否则被覆盖，等于没改）<br>　 推荐（改动最小、无跨对象私属性写入）：在 `memory.py:226-229` 的 `currently_stuck` 分支内<br>　 `        if currently_stuck:`<br>　 `            self._stuck_duration += self._dt`<br>　 `        else:`<br>　 `            self._stuck_duration = 0.0`<br>　 之后追加**进展泄放**（由 `MemoryController` 每 tick 在调用 `stuck.update` 前写入 `self.stuck.disp_60s`） |
| **接口签名** | `StuckDetector.__init__(..., rate_threshold: float = 0.008, ...)`（**签名不变，默认值改变**：`5.0 → 0.008`）<br>`StuckDetector.update(...)` 签名不变<br>**新增属性**：`StuckDetector.disp_60s: float \| None = None`（泄放输入，由 `MemoryController.update` 在 `:1985` **之前**赋值） |
| **依赖** | P0-a1（口径冻结） |
| **V 指标** | **V1**（`stuck_score` 6000 tick 内取值 ≥ 3 个不同值；基线恒 1.0）、**V2**（真实卡死时长与轨迹运动学差 ≤ 5%） |
| **R 回退** | **R10**（不得把伪影当证据）；V2 差异 > 20% ⇒ **回退 P0-a2** |
| **假设** | 无（E-1 层：单位不匹配是可证的；`rate_threshold=5.0` vs `forward_rate ∈ [0,1]` ⇒ 条件恒真） |
| **回退触发点** | `V2` 差值 > 20% ⇒ 复原 `rate_threshold=5.0` 与 `:1993-1995` 原块；`V1` 未达标 ⇒ **阻塞 P1 全部条目** |

### P0-a3 — 解码器状态清零与真实卡死时长重算

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/fly64/memory.py:226-229`（时长累加）、`fly64/fly64/main.py:2687`（mirror）、`fly64/fly64/model.py:2096`（CX 输入）、`fly64/fly64/main.py:2056`（burst 输入） |
| **改前** | `main.py:2687`：`                model.stuck_duration = memory_ctrl.stuck_duration`<br>外溢链（原方案 §2.3 已列）：`main.py:2687 → model.py:2096 → main.py:2056 → memory.py:2186 → 反射冷却 / 测速 / burst 占空 / EVO 模式匹配` |
| **改后** | ① **新增真实量并只让"真实量"外溢**：<br>　 `main.py:2687` 改为<br>　 `                model.stuck_duration = memory_ctrl.stuck_duration_true`<br>② `MemoryController` 新增只读属性 `stuck_duration_true`，定义为**轨迹运动学量**（`net_disp_60s == 0 且 |Δpose| < 0.5 u` 的连续时长），与原 `stuck_duration`（检测量）**并存**；<br>③ `flow.json` 同时发布 `stuck_duration`（旧口径，标 `legacy`）与 `stuck_duration_true`（新口径）；`memory.json` 同步；<br>④ **`main.py:2056` 的 burst 前置暂不改**（属 P2-c2 的响应面），本项只保证"**存在一个可信的卡死时长量**" |
| **接口签名** | 新增：`MemoryController.stuck_duration_true -> float`（property，只读）<br>新增 `flow.json` 键：`"stuck_duration_true"`、`"stuck_duration_source" ∈ {"kinematic","legacy"}` |
| **依赖** | P0-a2 |
| **V 指标** | **V2**（真实卡死时长与运动学重算差 ≤ 5%） |
| **R 回退** | R10；V2 > 20% ⇒ 回退 P0-a2；V2 无法计算（无轨迹源）⇒ 置 `stuck_duration_true = None` 并**只做观测**（不驱动任何响应），写 `medium` finding |
| **假设** | 无（运动学量来自 `bridge` 的 pose，属行为面） |

### P0-a4 — 接线判定改为运行时 A/B + 参数授权点（单一写入口）

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① **新增** `fly64/skills/param_authority.py`<br>② `fly64/skills/evolution_skill.py:2238-2267`（`_inject`）与 `:1967-1968`（`wired` 过滤）<br>③ `fly64/fly64/main.py:1742-1753`（钳位回写）与 `:1756-1879`（自愈回写块）<br>④ 产物 `fly64/skills/param_wiring_ab.json`、`fly64/artifacts/param_history.jsonl` |
| **改前** | `main.py:1742-1743`：<br>`                _clamp_records, _clamp_applied = apply_strategy_clamps(`<br>`                    _expl, _clamp_raw, mtime=_clamp_mtime, now=time.time())`<br>`main.py:1756-1758`：<br>`                try:`<br>`                    _as_path = project / "skills" / "active_strategy.json"`<br>`                    _as_raw = json.loads(_as_path.read_text("utf-8"))`<br>`evolution_skill.py:1967-1968` 按注册表 `wired` 过滤（静态自证） |
| **改后** | ① `param_authority.py` **新增**（**无控制逻辑**）：<br>```python<br>AUTHORITY = {"coach": 0, "evo": 1, "operator": 2, "selfheal": 3}<br><br>class ParamAuthority:<br>    def acquire(self, owner: str, pid: str, lease_ticks: int, value: float) -> bool: ...<br>    def release(self, owner: str, pid: str) -> None: ...<br>    def snapshot(self) -> dict: ...        # {pid: (owner, lease_expiry, value, source_ts)}<br>    def restore(self, snapshot: dict) -> None: ...   # 逐 pid 精确回滚<br>```<br>② `_inject` 改为经 `acquire/release`；`wired` 过滤的**输入换成 A/B 产物**（`param_wiring_ab.json`）；<br>③ `main.py:1756-1879` 的自愈回写改为持有 `selfheal` 租约，**试验租约有效期内让行**；<br>④ **落盘字段统一为 `source`**（不新增 `owner` 字段；`ParamAuthority.owner` 仅内部记账，落盘映射到 `source`） |
| **接口签名** | `ParamAuthority.acquire(owner: str, pid: str, lease_ticks: int, value: float) -> bool`<br>`ParamAuthority.release(owner: str, pid: str) -> None`<br>`ParamAuthority.snapshot() -> dict`<br>`ParamAuthority.restore(snapshot: dict) -> None`<br>新增 `param_wiring_ab.json` 结构：`[{pid, probe_value, observed_before, observed_after, verdict, ts}]`<br>新增 `memory.json["param_authority"] = {pid: {owner, lease_expiry, value, source}}` |
| **依赖** | —（与 P0-a2/a3 并行） |
| **V 指标** | **V3**（39 参数 100% 有 A/B 判定；`wired=false` 者从搜索空间剔除） |
| **R 回退** | **R7**（参数写入权争抢）：租约冲突 / 第三方写入 ⇒ **作废该试验**<br>A/B 无法执行 ⇒ 只用**人工确认**的 `pid`<br>租约机制异常（读写异常/缺失）⇒ **退化为只读模式**：禁止所有自动写入，仅保留教练人工写入，置 `flow.json["param_authority_degraded"]=true` |
| **假设** | **H10**（`scripts/audit_contract_pairs.py` 的 "39 参数全 unreferenced" 是静态扫描盲区，非"39 个都是死键"——**两者都不足以证明接线**，故必须用运行时 A/B） |

### P0-a5 — 观测值落盘（`evolution_log.jsonl` 的 `context` 块）

> **实现规格见 M4-d3**（同一改动，原方案 §7.3 与 P0-a5 是同一落点）。此处只登记阶段归属：**P0-a5 == M4-d3**，不得重复实现两份。

| 字段 | 内容 |
|---|---|
| **依赖** | P1-b1/b2/b3/b4 的**新增观测键**须先定名（否则 `context` 块字段名与其漂移）⇒ **实现顺序：先定名（本文件 §5、§6 的 `flow.json` 新增键），再落 `context`** |
| **V 指标** | **V15** |
| **R 回退** | R9 之外，见 M4-d3 |

### P0-a6 — 漏斗告警 + 存活自检 + 数据源冗余

> **实现规格见 M4-d4**（原方案 §7.4 与 P0-a6 同一落点）。**P0-a6 == M4-d4**。

| 字段 | 内容 |
|---|---|
| **V 指标** | **V16** |
| **R 回退** | 告警通道异常 ⇒ 至少保证 `agent_state` / `memory.json` 可见（本地降级，不依赖任何外部服务） |

### P0-a7 — `--history-check` 红灯修复（SKILL 版本三元组对齐）

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① `fly64/skills/evolution_skill.py:42`<br>② `fly64/skills/evolution_history.json:3-5`（canonical_versions）<br>③ `fly64/fly64/main.py:49-50`（已对齐，**不改**）<br>④ 版本三元组落盘：`fly64/skills/evolution_skill.py:2923-2929` 的 `context.version` |
| **改前** | `evolution_skill.py:42`：`SKILL_VERSION = "3.5.0"`<br>`evolution_history.json:3-5`：`  "canonical_versions": { "brain": "2.24.0", "skill": "3.5.1" }`<br>**本机实测（E-2）**：`cd fly64; python -m skills.evolution_skill --history-check` ⇒ 末行<br>`BRAIN_VERSION(main.py)=2.24.0  SKILL_VERSION=3.5.0  canonical=(2.24.0/3.5.1)  FAIL — SKILL_VERSION 3.5.0 != canonical 3.5.1 (agent.md rules 15/17)`，`exit code = 1` |
| **改后** | `evolution_skill.py:42`：`SKILL_VERSION = "3.5.1"`<br>并在 `evolution_history.json` 的变更历史中**登记一条 skill 记录**（`kind: "skill"`、`round`、`brain_version: "2.24.0"`、`trigger` 说明"F13/RULE-19 ratio 契约迁移"）<br>② `--history-check` **纳入 M4-d4 的自检通道**：**红灯不得阻塞诊断**，但必须告警（`high` finding + `/memory.json["evo_loop_stale"]` 同级通道）<br>③ 版本三元组（`brain` / `skill` / `canonical`）作为 `context.version` 每次落盘 |
| **接口签名** | 无新签名；`evolution_history.json` 新增记录字段：`id, recorded_at, kind, round, brain_version, trigger` |
| **依赖** | — |
| **V 指标** | **V19**（`--history-check` PASS，无回退：版本必须对齐） |
| **R 回退** | **R8**（红灯：`--history-check` HEAD FAIL）：未修复前**闭环不得进入 P3** |
| **验证命令** | `cd D:\codes\flygym\fly64; $env:PYTHONIOENCODING="utf-8"; python -m skills.evolution_skill --history-check` ⇒ `exit code 0` 且末行含 `OK`（或等价 PASS 标记，以脚本实际输出为准） |

### P0-a8 — 参数语义迁移与区间不变式（**P1 上线硬门**）

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① `fly64/skills/brain_tunable_params.json:38-43`（`exploration.gate_jump_threshold`）<br>② `fly64/skills/active_strategy.json:5`、`:8`<br>③ `fly64/fly64/main.py:1102-1105`（`CLAMP_BOUNDS`，**不改**）、`:1155`（`apply_strategy_clamps`，**不改**）<br>④ **测试侧断言**（**F-04 修正：必须指明文件**）：**扩展** `fly64/tests/test_tunable_wiring.py` 内**已有的** `registry ∩ runtime clamp != empty` 断言（该文件 716 行，扩展点由该断言的既有位置决定，**不新增第 4 个自检文件**；**注意该文件 `:118-160` 是 AST 辅助函数，不是断言**）<br>⑤ **运行期读回校验**（**F-04 新增，源 §4.7 落点④ 要求**）：`fly64/fly64/main.py` 参数热重载段（块 `:1678-1881`，逐 tick 判定 `:1678` `if model.step_count - _last_strategy_tick >= 600:`），在**归因记录段 `:1864-1878` 之后**、**回写 `:1879` 之前**新增；该行改前原文为<br>`                    _as_path.write_text(json.dumps(_as_raw, indent=2, ensure_ascii=False), "utf-8")`<br>⑥ 迁移写入经 P0-a4 授权点 |
| **改前** | `brain_tunable_params.json:38-43`：<br>`    "exploration.gate_jump_threshold": {`<br>`      "default": 8.0,`<br>`      "min": 2.0,`<br>`      "max": 20.0,`<br>`      "description": "跳跃池门限（单位：Hz；RULE-19 单位契约）…",`<br>`      "wired": true`<br>`    },`<br>`active_strategy.json:5-8`（**F-03 校正：`turn_bias` 的活值在 `:4`，本段引用的是 `:5-8` 四行**）：<br>`    "bold_explore_stuck_s": 60.0,`<br>`    "revisit_penalty_scale": 0.2991790018802808,`<br>`    "gate_forward_threshold": 0.5982965029723781,`<br>`    "gate_jump_threshold": 3.082271242248696,` |
| **改后** | ① 注册项改为（**上界 3.0 → 4.0 是 F1 的第一项修法**）：<br>`    "exploration.gate_jump_threshold": {`<br>`      "default": 0.75,`<br>`      "min": 0.25,`<br>`      "max": 4.0,`<br>`      "unit": "ratio (dimensionless)",`<br>`      "description": "相对占用率门（无量纲比值；RULE-19 精神保留：单一单位、只换算一次）。… 分母下限 FWD_RATIO_FLOOR = 0.008 = model.py:2282 的解码零点",`<br>`      "wired": true`<br>`    },`<br>② 迁移（**必须经 P0-a4 授权点**，不得手工编辑后提交）：`active_strategy.json:5` `60.0 → 10.0`；`active_strategy.json:8` `3.082271242248696 → 0.75`；<br>③ **区间不变式硬断言（阻断 P1）**：<br>　 · **主判据**（对全部 39 个注册 pid）：`clamp(live) == live`（写入值经运行期钳位后**逐位不变**）<br>　 · **严格判据**：`registry_min < live < registry_max`，**可满足性例外**：`default == max` 的两个 pid 退化为 `min < live ≤ max`（`exploration.turn_bias` `(0.0, 0.25, 0.25)`、`exploration.bold_explore_stuck_s` `(1.0, 10.0, 10.0)`）<br>　 · 不等即视为"静默钳位"：写 `high` 级 finding + `/memory.json["clamped_keys"]`<br>④ **运行期读回校验（F-04 补齐的落点④，必须实现，不是可选项）**：在 `fly64/fly64/main.py:1864-1878` 的归因记录段之后、`:1879` 的回写之前插入：<br>　 · **改前原文（`:1879`，作为插入锚点）**：<br>　 `                    _as_path.write_text(json.dumps(_as_raw, indent=2, ensure_ascii=False), "utf-8")`<br>　 · **改后（在锚点前插入读回校验）**：<br>　 `                    _clamped_now = _assert_registry_live_interval_ok(`<br>　 `                        _registry_params(), _as_raw)`<br>　 `                    if _clamped_now:`<br>　 `                        _clamped_keys.extend(_clamped_now)`<br>　 `                        log_clamp_warnings(_clamped_now)`   # high 级 finding<br>　 其中 `_assert_registry_live_interval_ok(registry, live) -> list[dict]` 与 P0-a8 的**测试侧断言复用同一实现**（导入自 `fly64/tests/` 之外的共享模块或 `fly64/fly64/main.py` 内的同名函数 + 测试侧 import，**不得两份判据**，守 R3 单一口径）<br>　 · **验收**：`/memory.json["clamped_keys"]` 在新语义上线后 **6000 tick 内为空**；非空即写 `high` finding 并把新语义标记为未上线 |
| **接口签名** | 注册项新增字段 `"unit": "ratio (dimensionless)"`<br>`main.py` 新增启动自检函数（落在 `fly64/tests/` 已有的同契约测试文件内扩展；**不新增第 4 个自检文件**）：`assert_registry_live_interval_ok(registry: dict, live: dict) -> list[dict]`<br>`memory.json` 新增键：`"clamped_keys"`（列表，元素 `{key, requested, applied, source}`，字段名与 `main.py:1873-1876` 的 `param_history.jsonl` 记录**同形**） |
| **依赖** | P0-a1、P0-a4（迁移经授权点） |
| **V 指标** | **V21**（`clamp(live)==live` 对 39/39 通过；`min<live<max`（含 `default==max` 例外）；`:8` 迁移为 0.75 后同类断言通过）<br>**V6**（迁移未做 ⇒ 占空比恒 0）<br>**V22**（RULE-19 契约同批迁移） |
| **R 回退** | **R11**（语义翻转 + 越界值共存 ⇒ 静默收紧）：断言失败即**阻断 P1**；迁移项失败 ⇒ **保持语义在 Hz（不切比值）**，把 P1-b3 标记为未上线 |
| **假设** | 无（`3.082271242248696 > 3.0` 是算术事实；39 个 pid 的区间审计为本机实测） |
| **实测区间审计（本机复算，施工前基线）** | 39/39 pid 有活值；**越界/钉界者仅 2 个**：`exploration.bold_explore_stuck_s = 60.0`（越界，注册 max 10.0）、`exploration.turn_bias = 0.25`（钉上界）。`exploration.gate_jump_threshold = 3.082…` 在**当前**区间 `[2.0, 20.0]` **内**（故今天不被钳位）—— 它的问题**只**出现在新比值语义区间下，这正是必须"改区间 + 迁移 + 断言"三件套的原因 |

---

## 3. P1 变更规格（§5 · M1 脑侧自适应作用面）

> **本节每一条都是"让已有信号到达"**（硬约束 C2）：不新增控制分支，只**扩面、加稳态、换口径、修死写入**。

### 3.0 P1 公共约定

**观测落盘（统一读同一组字段，见 M4-d3）**：`jump_leg_current`、`gain_per_pathway`、`jump_pool_occupancy`、`fwd_pool_occupancy`、`jump_rate_ratio`、`param_authority`、`ctrl_x/ctrl_y/jump`、`disp_60s`、`loop_score`、`coverage_cells`、`waste_ratio`。

**接线唯一判据 = 运行时 A/B（P0-a4）**：每条必须先证明"写入 → 消费点变化"，否则 `wired=false`。

**P1 出口门（G5）**：新增 `control.*` 写入点 = **0**（静态断言）。

---

### P1-b1 — 把 MBON→jump 腿纳入增益链（消除"增益只覆盖一条腿"）

| 字段 | 内容 |
|---|---|
| **ID** | `P1-b1`（原 §5.1） |
| **文件·行号** | ① `fly64/fly64/model.py:1787`（注入点）<br>② `fly64/fly64/model.py:639`（常量定义）与文件顶部 import（`model.py:12` 附近）<br>③ `fly64/fly64/gain_modulation.py:39-45`（`DEFAULT_GAINS`）、`:48-49`（`GAIN_MIN`/`GAIN_MAX`）<br>④ `fly64/skills/brain_tunable_params.json`（新增 `escape.jump_leg_weight`）<br>⑤ `fly64/fly64/main.py:1852-1855`（`escape.*` 接线段） |
| **改前** | `model.py:1787`：<br>`            self.v[self.jump_nodes] += mbon[3] * self.mbon_gain_jump`<br>`model.py:639`：<br>`        self.mbon_gain_jump = self.mbon_jump_weight`<br>`gain_modulation.py:39-49`：<br>`DEFAULT_GAINS = {` … `    "jump": 1.50,` … `}`<br>`GAIN_LEARNING_RATE = 0.002` / `GAIN_MIN = 0.5` / `GAIN_MAX = 2.5`<br>`main.py:1852-1853`（同段参照，用于确认接线位置与写法）：<br>`                    model._escape_jump_drive = max(0.1, min(1.0, float(`<br>`                        _esc.get("escape_jump_drive", 0.45))))` |
| **改后** | ① `model.py:1787` 改为（**F2：实现内除以 nominal**）：<br>`            self.v[self.jump_nodes] += (mbon[3] * self._jump_leg_weight`<br>`                                         * (self._pathway_gains_np[3] / self._jump_leg_nominal_gain))`<br>② `model.py:639` 附近改为<br>`        self._jump_leg_weight = 0.35`<br>`        self._jump_leg_nominal_gain = DEFAULT_GAINS["jump"]`<br>并同步 import：<br>`from .gain_modulation import DopamineGainController, DEFAULT_GAINS`（**从模块导入常量，不复制数字**）<br>③ `gain_modulation.py` 新增 **`JUMP_GAIN_MAX = 4.0`** 与按通路覆盖（跳是**事件性**动作，自带 0.8 s 不应期，不与持续通路共享 2.5 上限）；`GAIN_MIN = 0.5` **不放宽**（原方案 §9.3-5）<br>④ `brain_tunable_params.json` 新增<br>`    "escape.jump_leg_weight": {`<br>`      "default": 0.35,`<br>`      "min": 0.10,`<br>`      "max": 0.80,`<br>`      "wired": true`<br>`    },`<br>⑤ `main.py:1852-1855` 附近新增（与 `_escape_jump_drive` **同段**，同源 section `escape`）：<br>`                    model._jump_leg_weight = max(0.10, min(0.80, float(`<br>`                        _esc.get("jump_leg_weight", 0.35))))` |
| **接口/常量** | 新增属性 `FlyModel._jump_leg_weight: float = 0.35`（**名义权重**，非"乘以原始 gain 后的等效值"）<br>新增属性 `FlyModel._jump_leg_nominal_gain: float = DEFAULT_GAINS["jump"] = 1.5`<br>新增常量 `gain_modulation.JUMP_GAIN_MAX = 4.0`<br>新增注册 pid `escape.jump_leg_weight {0.35, 0.10, 0.80}`<br>`model.mbon_gain_jump`（`model.py:639`）**保留为兼容属性**，但**不再是 `:1787` 的驱动源** |
| **依赖** | **P0-a4**（A/B 判据）、**P0-a5/M4-d3**（`jump_leg_current` / `gain_per_pathway` 落盘）、P0-a8（新增 pid 须过区间不变式） |
| **V 指标** | **V4**（① 位精确回归 **先过**：`_jump_leg_weight=0.35` 且 `gain("jump")=1.5` ⇒ `v[jump_nodes]` 增量与改动前**逐位相同**（float32 `np.array_equal`，**非 `approx`**）；② `0.35→0.80` ⇒ `jump_leg_current` 升 ≈2.29×；`0.35→0.10` 降 ≈0.286×）<br>**V5**（`jump_pool_occupancy` 非零 tick 占比 ≥ 5%，且 P95 ≤ 0.20；**标定前提 = V4① 已通过**） |
| **R 回退** | ① 位精确回归失败 ⇒ **立即回滚 P1-b1 并区块化**（说明实现与标称不变式不一致，**不允许进入 A/B 阶段**）<br>② A/B 无响应 ⇒ 判 `wired=false`，自动把 `escape.jump_leg_weight` 从 `BrainMutator.live_params` **剔除**并写 `param_wiring_ab.json`，恢复 `model.py:1787` 为常数 0.35（**保留旧行注释**）<br>③ `jump_pool_occupancy` 非零比例 **> 30%**（跳变持续行为）⇒ 自动把 `_jump_leg_weight` 回落到 0.35 并置 `flow.json["jump_leg_clamped"]=true` |
| **假设** | **H5**（真实连接组运行点 ≠ demo 探针）、**H11**（跳池发放率可被 `escape.jump_leg_weight` 显著改变）、**H12**（`JUMP_GAIN_MAX = 4.0` **可撤回**：若 2.5 已足够则删除该新增常量） |
| **观测新键** | `flow.json["jump_leg_current"] = mean(abs(mbon[3])) * _jump_leg_weight * (gain("jump") / DEFAULT_GAINS["jump"])`（**与实现同式，含归一化**）、`flow.json["gain_per_pathway"]["jump"]`、`flow.json["jump_pool_occupancy"]` |

**F2 关键说明（施工时不得再走错）**

- 数学等价：`0.2333·g ≡ 0.35·(g/1.5)`，**两种写法等价**；选"实现内除以 nominal"是为了让 `jump_leg_weight` 的语义与今天 `mbon_gain_jump = 0.35` **同名同义**。
- 若改成"默认 0.2333 + 直接乘原始 gain"，则**必须同步改三处**：V4 的比例（0.35→0.80 = 2.29×、0.35→0.10 = 0.286×）、§14-A 的增益链表（`0.07749 / 0.23247 / 0.38746`）、注册项 `{0.35, 0.10, 0.80}`。**本文件选定前者，故这三处均不改。**

---

### P1-b2 — 跳池占用率自稳态 + 固有兴奋性腿

| 字段 | 内容 |
|---|---|
| **ID** | `P1-b2`（原 §5.2） |
| **文件·行号** | ① `fly64/fly64/model.py:1452-1475`（`forward_homeo_gain`，**对等参照，不改**）<br>② `fly64/fly64/model.py:649-652`（前向池稳态常量，**不改**）<br>③ `fly64/fly64/model.py:1769-1778`（前向占用率低通处，**同段追加**）<br>④ `fly64/fly64/model.py:1882-1890`（前向固有兴奋性腿，**之后追加**）<br>⑤ `fly64/fly64/model.py:696`：`        self.fwd_aux_ceiling = 0.20`（**量级参照，不改**）<br>⑥ `fly64/skills/brain_tunable_params.json`（新增 `escape.jump_intrinsic_max`）<br>⑦ `fly64/fly64/main.py`（与 `escape.*` 同段接线） |
| **改前** | `model.py:1774-1777`：<br>`        _fwd_occ_now = float(self.spikes[self.forward].mean()) if len(self.forward) else 0.0`<br>`        _occ_alpha = 1.0 - float(np.exp(-self.dt / max(self.fwd_occ_tau, 1e-6)))`<br>`        self._fwd_occupancy += _occ_alpha * (_fwd_occ_now - self._fwd_occupancy)`<br>`        self._fwd_homeo_gain = self.forward_homeo_gain()`<br>`model.py:1888-1890`：<br>`        if len(self.forward):`<br>`            self._fwd_tonic_current = self.tonic_current * self._fwd_homeo_gain`<br>`            self.v[self.forward] -= self.tonic_current * (1.0 - self._fwd_homeo_gain)`<br>**跳池当前无任何稳态/自调**（`jump_pool_homeostat_constants_today = null`） |
| **改后** | ① 新增 `FlyModel.jump_homeostat(self, occupancy: float \| None = None) -> float`（**纯映射、无 RNG、无新状态依赖**，形状对等 `forward_homeo_gain`）：<br>```python<br>def jump_homeostat(self, occupancy: float | None = None) -> float:<br>    """Occupancy → jump-pool intrinsic gain in [jump_homeo_floor, 1.0]."""<br>    occ = self._jump_occupancy if occupancy is None else float(occupancy)<br>    span = max(1e-6, self.jump_awake_full - self.jump_awake_ref)<br>    under = min(1.0, max(0.0, (self.jump_awake_ref - occ) / span))<br>    return float(1.0 - under * (1.0 - self.jump_homeo_floor))<br>```<br>② 常量（`model.py:649-652` 之后追加）：<br>`        self.jump_occ_tau = 0.20          # s: occupancy low-pass time constant`<br>`        self.jump_awake_ref = 0.02        # occupancy below which the pool is "asleep"`<br>`        self.jump_awake_full = 0.12       # occupancy at which intrinsic drive is off`<br>`        self.jump_homeo_floor = 0.25      # min intrinsic gain`<br>`        self.jump_intrinsic_max = 0.15    # **authoritative default** (== registry default)`<br>③ 在 `:1774-1777` **同一段**追加跳池低通与增益：<br>`        _jump_occ_now = float(self.spikes[self.jump_nodes].mean()) if len(self.jump_nodes) else 0.0`<br>`        self._jump_occupancy += _occ_alpha * (_jump_occ_now - self._jump_occupancy)`<br>`        self._jump_homeo_gain = self.jump_homeostat()`<br>④ 在 `:1888-1890` **之后**追加跳池固有兴奋性腿（**语义相反**：前向池"接近上限就压制"，跳池"静默太久就抬升"）：<br>`        if len(self.jump_nodes):`<br>`            self.v[self.jump_nodes] += self._jump_intrinsic * (1.0 - self._jump_homeo_gain)`<br>（`_jump_intrinsic` 由 `jump_intrinsic_max` 与 `fwd_aux_ceiling`-类预算共同界定）<br>⑤ 注册项：<br>`    "escape.jump_intrinsic_max": {`<br>`      "default": 0.15,`<br>`      "min": 0.05,`<br>`      "max": 0.25,`<br>`      "wired": true`<br>`    },`<br>**F10①：常量默认值必须 = 0.15**（与注册项、"精确算术"段一致；原稿 0.25 是矛盾值，**不得采用**）<br>⑥ `main.py` 接线（与 `escape.*` 同段）：`model.jump_intrinsic_max = max(0.05, min(0.25, float(_esc.get("jump_intrinsic_max", 0.15))))` |
| **接口签名** | `FlyModel.jump_homeostat(occupancy: float \| None = None) -> float`<br>新增状态 `FlyModel._jump_occupancy: float`、`FlyModel._jump_homeo_gain: float`、`FlyModel._jump_intrinsic: float`<br>新增注册 pid `escape.jump_intrinsic_max {0.15, 0.05, 0.25}` |
| **依赖** | **P0-a4**、**P0-a5/M4-d3**、P0-a8（新增 pid 过区间不变式）、`P1-b1`（增益链串联：跳池稳态的消费点①与 b1 串联） |
| **V 指标** | **V5**（`jump_pool_occupancy` 非零 tick 占比 ≥ 5% 且 **P95 ≤ 0.20**） |
| **R 回退** | **R1**（增益链扩面导致跳池持续发放）：`jump_pool_occupancy` P95 > 0.20 ⇒ 自动将 `escape.jump_intrinsic_max` **减半**；<br>减半后仍失败 ⇒ **置 0**（该腿完全停用）并写 `param_wiring_ab.json` 标注 `ineffective`；<br>**对偶性失败**（跳池被驱动活跃后 `_jump_homeo_gain` 不能回升至 ≥ 0.9）⇒ 判定为正反馈，**禁止**该腿进入闭环搜索空间（只保留 A/B 手动值），并向 `evolution_log` 写 `high` 级 finding |
| **假设** | **H5**（0.18127 缺口、0.13127、5.517×、`fwd_aux_ceiling` 比例的阈值**只能在真实连接组上确认**） |
| **观测新键** | `flow.json["jump_pool_occupancy"]`、`flow.json["jump_homeo_gain"]`、`flow.json["jump_rate_ratio"]`、`flow.json["fwd_homeo_gain"]`、`flow.json["fwd_pool_occupancy"]` |
| **精确算术（仅供量级判断，不构成断言）** | 单跳神经元越阈需 `I ≥ 0.18127`/tick；`escape_current` 下限 0.05 ⇒ 缺口 `0.13127`（**= 0.13 × threshold(1.0) = 0.31 × GAIN_MIN 腿的 v_ss(0.4275)**，F10②）；`fwd_aux_ceiling = 0.20`，`0.15/0.20 = 0.75` 同量级 |

---

### P1-b3 — `jump_rate` 门归一化（**替换**而非新增第 5 个口径）

| 字段 | 内容 |
|---|---|
| **ID** | `P1-b3`（原 §5.3，**本方案唯一的 jum 门口径迁移**，牵动 RULE-19 契约） |
| **文件·行号** | ① `fly64/fly64/model.py:2478`（唯一执行门）<br>② `fly64/fly64/model.py:2282`（分母下限的零点来源，**不改**）<br>③ `fly64/fly64/main.py:2892-2894`（读默认值）、`:2953-2957`（遥测发布与比较）<br>④ `fly64/skills/brain_tunable_params.json:38-43`（与 P0-a8 同一处）<br>⑤ **同批迁移（F13）**：`fly64/tests/test_gate_units.py:178-226`、`fly64/contract_registry.json:83/:98/:102`、`fly64/fly64/main.py:765-783`（RULE-19 注释块）<br>⑥ **不得改**：`fly64/fly64/main.py:3064`（`jump_not_active`，per-tick 解码镜像，**F15 校正**） |
| **改前** | `model.py:2478`：<br>`        jump = jump_rate > 0.04 and now - self.last_jump >= 0.8`<br>`main.py:2892-2894`：<br>`                _gate_forward_hz = float(`<br>`                    _expl.get("gate_forward_threshold", 2.0))`<br>`                _gate_jump_hz = float(_expl.get("gate_jump_threshold", 8.0))`<br>`main.py:2953-2957`：<br>`                    "gate_forward_threshold_hz": round(_gate_forward_hz, 4),`<br>`                    "gate_jump_threshold_hz": round(_gate_jump_hz, 4),`<br>`                    # Hz-vs-Hz comparisons (no implicit unit conversion here).`<br>`                    "gate_forward": gate_open_hz(_forward_rate_hz, _gate_forward_hz),`<br>`                    "gate_jump": gate_open_hz(_jump_rate_hz, _gate_jump_hz),`<br>`test_gate_units.py:182-183`：<br>`    assert "Hz" in meta["description"], "the unit must be declared in the schema"`<br>`    assert "RULE-19" in meta["description"], "the unit contract must be referenced"`<br>`test_gate_units.py:223-225`：<br>`    assert float(jmp["default"]) > refs["jump_event_hz"], (`<br>`        "gate_jump must be stricter than the decoder's own jump trigger")`<br>`    assert float(jmp["min"]) >= refs["jump_event_hz"]`<br>`contract_registry.json:102`：`        "threshold_unit": "Hz — skills/brain_tunable_params.json: gate_forward_threshold 0.4..8.0 default 2.0; gate_jump_threshold 2.0..20.0 default 8.0 (maxima kept below Nyquist 1/dt = 50 Hz so a declared threshold stays reachable)"` |
| **改后** | ① `model.py:2478` 改为（**比值语义**）：<br>`        jump = ((jump_rate / max(forward_rate, FWD_RATIO_FLOOR)) > self._jump_rate_ratio_gate`<br>`                and now - self.last_jump >= 0.8)`<br>② 新增模块级常量与实例字段：<br>`FWD_RATIO_FLOOR = 0.008   # model.py:2282 的 raw_y 解码零点（分母定义域下限，不是新门限）`<br>`        self._jump_rate_ratio_gate = 0.75`<br>③ `main.py` 热重载段写入（**上界随注册表改 4.0**）：<br>`                model._jump_rate_ratio_gate = max(0.25, min(4.0, float(`<br>`                    _expl.get("gate_jump_threshold", 0.75))))`<br>④ `brain_tunable_params.json:38-43` 改写 `default/min/max/description` + 新增 `unit`（**与 P0-a8 同一处，一次改完**）<br>⑤ `main.py:2892-2894` 默认值 `8.0 → 0.75`；`:2953-2957` 改读**比值口径**：发布 `gate_jump_ratio_threshold`（新名）+ `jump_rate_ratio`，并让 `gate_jump` 布尔由**比值比较**产生（`jump_rate / max(forward_rate, FWD_RATIO_FLOOR) > r`）。**`main.py:3064` 不动**（它是 per-tick 解码镜像，F15）<br>⑥ **P0-a8 迁移**：`active_strategy.json:8` → `0.75`<br>⑦ **RULE-19 契约同批迁移（F13，blocker 级）**：<br>　 · `test_gate_units.py:178-226` 改写为 **pinned ratio 契约**：`description` 须含 `"ratio"`、须点名分母下限 `FWD_RATIO_FLOOR = 0.008` 与 `model.py:2282`、`default > 0`、`min > 0`；`:223-225` 的 `jump_event_hz` 比较改为 ratio 参照；**:226 的 `max <= NYQUIST_HZ` 改为 `max <= RATIO_MAX`**（倍率上界，不再是 Nyquist）；**pinned 强度不得下调**<br>　 · `contract_registry.json:102`：`threshold_unit → "ratio (dimensionless)"`；`:83` 的 `rate_gate_group` 与 `:98` 的 `gate_jump_threshold_hz` 描述同步<br>　 · `main.py:765-783` 的 RULE-19 注释块同步为 ratio 版本 |
| **接口/常量** | 新增 `model.FWD_RATIO_FLOOR = 0.008`<br>新增 `FlyModel._jump_rate_ratio_gate: float = 0.75`<br>改注册项 `exploration.gate_jump_threshold {0.75, 0.25, 4.0}` + `unit: "ratio (dimensionless)"`（**同一 key，不新增 key**，硬约束 C3）<br>新增 `flow.json` 键：`jump_rate_ratio`、`gate_jump_ratio_threshold`、`jump_duty_burst_off`、`jump_gate_autoraise`（回退记录） |
| **依赖** | **P0-a8**（必须先完成迁移与区间断言）、**P0-a4**、**P0-a5/M4-d3**、**P2-c4 的冲突矩阵裁决**（burst 期间 `control.jump=False` ⇒ V6 统计必须排除 burst 窗口） |
| **V 指标** | **V6**（`ctrl.jump` 占空比 ∈ **[0.1%, 5%]**；基线 **0/6000 = 0.0%**，即**下界不满足**；统计窗口**排除 burst 窗口**）、**V22**（RULE-19 契约迁移完整性） |
| **R 回退** | **R2**（占空比 > 5%（burst-off 窗口统计）⇒ §5.3 自动 ×2 抬门；两次失败回落 0.75 并标 `high_risk`，从自动搜索空间剔除）<br>**R13**（F13：契约未迁移 ⇒ **§5.3 整体不上线**，保持 Hz 语义）<br>条件③失败（恒真/恒假）⇒ 判"新口径不可判别"，回退为**候选方案 A**（按下 1 秒内前向池对跳池的比值 ≥ 2 倍，用**新增只读指标**而非新门限），并在 `param_wiring_ab.json` 标注<br>迁移项失败 ⇒ **不切换语义（保持 Hz）**，把 P1-b3 标为未上线并保留原门，**不得**带着 3.082 的越界值进入比值语义 |
| **假设** | **H6**（跳池常态驱动远低于 0.04 需真实连接组确认）；等效表的 `forward_rate` 取值口径按 `forward_rate = ctrl_y/2000 + 0.008` 取 0.0330/0.0430（**轨迹反解，非当前 run 读数**） |
| **验收命令** | `cd D:\codes\flygym\fly64; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_gate_units.py -q` ⇒ 全绿（**基线已实测：15 passed**，故"全绿"是改后必须保持的状态，且断言内容须为 ratio 版） |

**等效换算表（判定"放宽/收紧"的唯一依据）**

记旧门为绝对量 `jump_rate > 0.04`；新门为 `jump_rate > r · max(forward_rate, 0.008)`。等效关系 `r_eq(forward_rate) = 0.04 / max(forward_rate, 0.008)`：

| `forward_rate` | 旧门等效比值 `r_eq` | `r = 0.75` 时新门要求 `jump_rate >` | 神经元数（/20） | 相对旧门 |
|---|---|---|---|---|
| 0.008（解码零点，下限） | 5.00 | 0.0060 | 0.120 | **放宽 6.7×** |
| 0.0330（`ctrl_y = 50` 实测） | 1.21 | 0.0248 | 0.495 | **放宽 1.6×** |
| 0.0430（`ctrl_y = 70` 实测/饱和） | 0.93 | 0.0323 | 0.645 | **放宽 1.24×** |
| 0.1000 | 0.40 | 0.0750 | 1.500 | 收紧 1.9× |
| 0.3000 | 0.13 | 0.2250 | 4.500 | 收紧 5.6× |

> **若沿用线上 3.082**：在 0.033/0.043 两处分别是 **2.54× / 3.31× 收紧**，与目的相反且 **V6 不可满足**。这正是 P0-a8 必须同批执行的原因。

**V6 判定形式（必须写成可判定，含下界）**

| 判定项 | 阈值 | 基线 |
|---|---|---|
| ① A/B | `gate_jump_threshold` `0.75→0.25` ⇒ `ctrl.jump` 占空比上升；`0.75→2.5` ⇒ 下降 | 无 |
| ② 有界性 | 连续 6000 tick 内 `ctrl.jump` 占空比 ∈ `[0.1%, 5%]`（**排除 burst 窗口**） | **0/6000 = 0.0%（下界不满足）** |
| ③ 不复现旧缺陷 | 门限在 6000 tick 内**同时出现过真与假** | 恒假 |
| ④ 等效性抽样 | 任取 100 tick，断言 `jump_rate_ratio > r ⇔ jump_rate > r·max(forward_rate,0.008)` 与实现逐 tick 一致 | 无 |

---

### P1-b4 — 修复两处 CX 导航旋钮死写入（写端改到 `_goal_comp`）

| 字段 | 内容 |
|---|---|
| **ID** | `P1-b4`（原 §5.4） |
| **文件·行号** | ① `fly64/fly64/main.py:1847-1851`（死写入两行）<br>② `fly64/fly64/central_complex.py:178`（类名）、`:191-198`（`__init__` 内 `self.steering_gain`）、`:286-306`（`_no_goal` 与读取端 `:297`）、`:369-373`（实例挂在 `cx._goal_comp`）<br>③ `fly64/fly64/main.py` 热重载段（写入后读回校验）<br>④ 来源：`fly64/skills/active_strategy.json:33-38`（线上 `steering_gain = 0.12`、`loop_break_stuck_s = 45.0`） |
| **改前** | `main.py:1847-1851`：<br>`                    # ── Navigation steering / drives ──`<br>`                    model.cx.steering_gain = max(0.01, min(0.5, float(`<br>`                        _nav.get("steering_gain", 0.12)))`<br>`                    model.cx._loop_break_stuck_s = max(10.0, min(120.0, float(`<br>`                        _nav.get("loop_break_stuck_s", 45.0))))`<br>`central_complex.py:178`：<br>`class MultiSourceGoalCompetition:`<br>`central_complex.py:198`：`        self.steering_gain = steering_gain`<br>`central_complex.py:286`：`        _no_goal = self._ext_goal_strength < 0.05`<br>`central_complex.py:297`：<br>`        if (stuck > getattr(self, '_loop_break_stuck_s', CX_LOOP_BREAK_STUCK_S)`<br>**实测（E-1/E-3）**：`hasattr(cx, 'steering_gain') = False` 时写 `cx.steering_gain = 0.5`，而 `_goal_comp.steering_gain` 仍为 **0.12** ⇒ 写落在**影子属性**上 |
| **改后** | ① `main.py:1848-1851` 写端改为 `_goal_comp`：<br>`                    model.cx._goal_comp.steering_gain = max(0.01, min(0.5, float(`<br>`                        _nav.get("steering_gain", 0.12)))`<br>`                    model.cx._goal_comp._loop_break_stuck_s = max(10.0, min(120.0, float(`<br>`                        _nav.get("loop_break_stuck_s", 45.0))))`<br>**并保留**对 `model.cx` 的属性写入 + 加 `assert`/`grep` 断言"影子属性不得被任何消费者读取"<br>② `central_complex.py` 为 **`MultiSourceGoalCompetition`**（**F9：不是 `GoalComparator`——该类全仓 0 命中**）增加 `property`，使 `cx.steering_gain` 与 `cx._goal_comp.steering_gain` **同源**（消除"写在哪一处"的**类别错误**，而非只改一处）：<br>```python<br>    @property<br>    def steering_gain(self) -> float:<br>        return self._goal_comp.steering_gain<br><br>    @steering_gain.setter<br>    def steering_gain(self, value: float) -> None:<br>        self._goal_comp.steering_gain = float(value)<br>```<br>（`_loop_break_stuck_s` 同法）<br>③ `main.py` 热重载段增加**写入后读回校验**：<br>`                    assert model.cx.steering_gain == model.cx._goal_comp.steering_gain`<br>不等则写 `high` 级 finding 到 `/memory.json["param_write_mismatch"]` |
| **接口签名** | `CentralComplex.steering_gain` → property（getter/setter，委托 `_goal_comp`）<br>`CentralComplex._loop_break_stuck_s` → 同法<br>`MultiSourceGoalCompetition` 保持现有 `steering_gain: float`、`_loop_break_stuck_s`（`getattr` 读取端在 `:297`）<br>新增 `memory.json["param_write_mismatch"]: int`<br>新增 `flow.json` 键：`cx_effective_steering_gain`、`cx_effective_loop_break_s`（**从 `_goal_comp` 读**） |
| **依赖** | **P0-a4**、**P0-a5/M4-d3**、**P1-b5**（b5 的旋钮 A/B 依赖 b4 先生效） |
| **V 指标** | **V7**（写 `navigation.steering_gain = 0.40` ⇒ `cx_effective_steering_gain` 在 ≤ 1200 tick 内变为 0.40；`loop_break_stuck_s = 20.0` 同法；`param_write_mismatch` 在 6000 tick 内 = 0；基线：写 0.5 无效、`_goal_comp` 仍 0.12） |
| **R 回退** | 条件 ①/② 失败 ⇒ 判 `wired=false`，把两个 pid 从**搜索空间**剔除（**但不从注册表删除**，保留为"待修"）<br>条件 ③ 失败（`param_write_mismatch ≠ 0`）⇒ **立即回滚 P1-b4 的写端改动到原行为**（保留原写入），并**中止 P1 其余项的闭环接入** |
| **假设** | 无（E-1：`MultiSourceGoalCompetition` 无 `steering_gain` 影子问题的证据 = 属性存在性与探针实测） |
| **注意（写在此处防止误读）** | 本项**不改** `central_complex.py:286` 的 `_no_goal` 判定式（那是 **P1-b5** 的落点）；本项只修**写端可达性** |

---

### P1-b5 — CX 环路突破（EVO-057）可达化：把"无目标"门换成"无进展"门

| 字段 | 内容 |
|---|---|
| **ID** | `P1-b5`（原 §5.5，含 **F6 冲突矩阵**） |
| **文件·行号** | ① `fly64/fly64/central_complex.py:286-306`（`_no_goal` 与 `_loop_break` 前置）<br>② `fly64/fly64/main.py:2746-2751`（`model.cx_goal_vectors` 组装处）<br>③ `fly64/fly64/model.py:2082-2097`（`cx.update(...)` 调用，**需新增传参**）、`:2096`（`stuck_duration` 入口）、`:2100-2101`（转向电流注入，**不改**）<br>④ `fly64/skills/brain_tunable_params.json:241-247`（`navigation.loop_break_stuck_s`，**同 key 改语义**）<br>⑤ **互锁对象（既有信号，不新增写入点）**：`fly64/fly64/main.py:1447`（`_deadlock_burst_remaining`）、`:2055-2062`（burst 前置）、`:2075-2084`（burst 体）<br>⑥ **可分辨观测**：`flow.json` 新增计数 |
| **改前** | `central_complex.py:286-299`：<br>`        _no_goal = self._ext_goal_strength < 0.05`<br>（…）<br>`        stuck = float(stuck_duration or 0.0)`<br>`        self._ticks_since_jump += 1`<br>`        if (stuck > getattr(self, '_loop_break_stuck_s', CX_LOOP_BREAK_STUCK_S)`<br>`                and _no_goal`<br>`                and self._ticks_since_jump >= CX_LOOP_BREAK_COOLDOWN_TICKS):`<br>`main.py:2748-2751`：<br>`                    model.cx_goal_vectors = memory_ctrl.navigation_vectors(`<br>`                        pose[0], pose[2], pose[3], model.cx_novelty_direction)`<br>`                    except Exception:`<br>`                        model.cx_goal_vectors = None`<br>`model.py:2096`：`            stuck_duration=getattr(self, "stuck_duration", 0.0),`<br>`main.py:2075-2084`：<br>`            if _deadlock_burst_remaining > 0:`<br>`                # Steer toward the chosen frontier heading`<br>`                if abs(_burst_heading) > 5:`<br>`                    control.x = int(max(-80, min(80, _burst_heading * 1.5)))`<br>`                else:`<br>`                    control.x = 0`<br>`                control.y = 127`<br>`                control.jump = False`<br>`                reflex_override = True`<br>`                _deadlock_burst_remaining -= 1`<br>**实测**：`_ext_goal_strength = min(1, norm/1.5) ≥ 0.05` **恒成立**（覆盖率 15% 时恒在供）⇒ `_no_goal` 恒假 ⇒ **突破永不触发**（t1 探针 4000 tick / `stuck_duration = 1000 s` 实测 **0 次**；仅 `norm < 0.075` 或无向量时触发 3 次）—— **H7**（条件性，非绝对） |
| **改后** | ① `central_complex.py:286-306`：改前置，`_no_goal` **保留为幅度项**，新增 `_no_progress` 门：<br>```python<br>_no_goal     = self._ext_goal_strength < 0.05           # 幅度调制（不再是门）<br>_no_progress = bool(progress_ineffective) or loop_score > loop_breakout_threshold<br>_burst_ok    = not burst_active<br>if (stuck > self._loop_break_stuck_s<br>        and _no_progress and _burst_ok<br>        and self._ticks_since_jump >= CX_LOOP_BREAK_COOLDOWN_TICKS):<br>```<br>`_ext_goal_strength ≥ 0.05` **从触发条件降级为幅度调制**（目标向量越强，突破后朝目标方向的偏置越大）<br>**⚠ R3 实测更正（SP5-A / t8，本行以下逐字保留规格意图，但实现与规格有偏差）**：`_no_goal` 的"降级为幅度项"**只落了赋值，未落读取** —— 实测 `central_complex.py:333` 赋值一次、**全模块零读取**（死赋值）；上文"保留为幅度项"应读作**规格意图**而非已实现行为。代码注释已同步更正并标注**待清理**（见 `central_complex.py` 的 "R3 correction" 段；`tests/test_cx_loop_break_gate.py::TestR3NoGoalIsADeadAssignment` 固定该判定）。<br>② `main.py:2746-2751` 段：把 `progress_ineffective`（`memory_ctrl.progress_is_ineffective`，**单一进展账本**，`memory.py:1135-1160`）与 `loop_score` 传入 CX；<br>③ `model.py:2082-2097` 的 `cx.update(...)` 新增两个关键字参数（**`_lif_motion` 无关**）：<br>`            progress_ineffective=<bool>,`<br>`            loop_score=<float>,`<br>`            burst_active=<bool>,`<br>④ 注册项 `navigation.loop_break_stuck_s` **语义从"卡死且无目标"改写为"卡死且无进展"**（**同 key，区间 `[10, 120]` 不变**）；<br>⑤ **不新增**任何控制写入点（突破仍由 CX 转向电流经 `model.py:2100-2101` 表达）<br>⑥ **F6 互锁三件**：<br>　 · **互锁**：`burst_active`（`main.py:2075-2084` 的 `_deadlock_burst_remaining > 0`，**已有信号**）作为突破的**抑制前置**（`breakout_ok AND NOT burst_active`）——把已有信号接进已有判定，**不新增 `control.*` 写入点、不新增门限**<br>　 · **可分辨观测**：新增 `flow.json["cx_loop_break_count_burst_off"]`（只在 `burst_active == false` 的 tick 累加）与 `flow.json["deadlock_burst_count"]`（对照量），并在 M4-d3 的 `context` 里**同时落盘两者**<br>　 · **冲突矩阵四条裁决（附表见下）** |
| **接口签名** | `CentralComplex.update(..., progress_ineffective: bool = False, loop_score: float = 0.0, burst_active: bool = False)`（**追加关键字参数，默认值保持零行为变化**）<br>新增 `flow.json` 键：`cx_loop_break_count`、`cx_loop_break_count_burst_off`、`cx_loop_break_last_ts`、`no_progress_gate`、`deadlock_burst_count` |
| **依赖** | **P1-b4**（旋钮 A/B 必须先生效）、**P0-a5/M4-d3**（计数落盘）、P0-a4 |
| **V 指标** | **V8**（在 `stuck_duration` 递增 + `progress_is_ineffective = true` + `loop_score > 0.6` 的复现场景下，**`cx_loop_break_count_burst_off` 在 4000 tick 内 ≥ 1**，对照改前 = 0；正常探索段 = 0；且与 `deadlock_burst_count` 的时间戳集合**不相交**） |
| **R 回退** | 条件 ② 失败（旋钮无效）⇒ 说明 **P1-b4 未生效**，先回退 P1-b5（保持触发条件不变），待 b4 通过后再试<br>条件 ③ 失败（正常探索段误触发）⇒ 自动将 `loop_breakout_threshold` 抬到 **0.9** 并收紧 `_loop_break_stuck_s ≥ 45`；仍失败则置 `cx_loop_break_enabled=false`（**只读遥测保留**）<br>**条件 ④ 失败（仍无法把 CX 突破与 burst 分开归因）⇒ 明确放弃归因**：V8 降级为"非归因观测指标"（只记录 `cx_loop_break_count*`，**不作为通过判据**），§5.5 验收改为"b4 旋钮 A/B 通过 + 突破计数在 burst-off 窗口内非零"；若连这一条也无法满足，则 **P1-b5 判未通过**（**不得用 burst 的行为冒充 CX 的功劳**） |
| **假设** | **H7**（恒不可达是**条件性**的，仅在目标向量在供时为真）、**H1'**（0.37 s 级转向变号的生成者是 R14/R16 转向疲劳/反驱动环路 ⇒ 影响突破的**幅度调制权重**，非触发条件） |
| **对 `main.py:2082` 的处置声明** | `control.jump = False`（burst 期间主动抑制跳）**保留**（burst 是有意的"先冲再跳"序列），但 V6 的占空比统计**必须排除 burst 窗口**（`jump_duty_burst_off`） |

**F6 冲突矩阵（逐对裁决，施工时四条都要落）**

| 交互对 | 现象 | 裁决（施工动作） |
|---|---|---|
| burst ↔ P1-b3 门归一化 | burst 期间 `control.jump = False`（`main.py:2082`）**主动抑制跳**，而 b3 想把跳变成可触发 | **保留** burst 的抑制；V6 占空比统计**必须排除 burst 窗口**（新增 `jump_duty_burst_off`） |
| burst ↔ P1-b5 CX 突破 | 两者都在"卡死 + 无进展"下触发，且 burst 直接写 `control.x/y` | **互锁**：`burst_active ⇒ CX 不复位`；V8 只数 burst-off 的窗口 |
| burst ↔ P2-c4 CPG 权威 | CPG 取权条件与 burst 的 `reflex_override = True` 重叠 | 权威优先级固定为 **`burst > primitive > lif`**，由 P2-c1 的仲裁状态机持有；**burst 期间不授予 primitive** |
| P1-b3 ↔ P2-c4 | 门归一化后跳更易触发，而 CPG 的 `longjump` 也会写跳 | 两者**不叠加**：primitive 授予期间 b3 的门**仍照常计算（只读）**，跳的最终写入者仍是原路径（`bridge.write_control(control.x, control.y, control.jump, ...)`，`main.py:2579-2581`），**不新增写入者** |

---

### P1-b6 — 死代码清理（"机制存在、报告成功、无法生效"家族）

> **A 类，不属控制补丁**。四条独立处置，逐条给出 "改前原文 / 改后 / 验证"。

#### P1-b6-1 `lr_adapt` 恒 1.0（`set_adaptive_lr()` 无调用点）→ **选"接线"**

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/fly64/mushroom_body.py:350-360`（定义）、`:116`（`self.lr_adapt: float = 1.0`）、`:394/:396`（消费点 `self.lr * self.lr_adapt * ...`）；接线落点 `fly64/fly64/main.py`（`scene_change_rate` 可用处，`:2656` 附近的内存更新段） |
| **改前** | `mushroom_body.py:350-360`：<br>`    def set_adaptive_lr(self, scene_change_rate: float) -> None:`<br>`        """Map scene-change rate to a plasticity multiplier.` …<br>`        self.lr_adapt = float(np.clip(0.5 + r / 0.3, 0.45, 2.0))`<br>**全仓无生产调用点**（`grep set_adaptive_lr` 仅命中定义 + 3 个测试） |
| **改后** | 在 `main.py` 的每 tick 段（`model.scene_change_rate` 可用处）接入：<br>`                model.mushroom.set_adaptive_lr(model.scene_change_rate)`<br>并把它接到 `coach.mb_learning_rate` 的**自适应调制**上（三因子学习率是 M1 的有效作用点之一） |
| **接口签名** | 无新签名（复用现有 `set_adaptive_lr(scene_change_rate: float) -> None`）<br>新增 `flow.json` 键：`mb_effective_lr` |
| **依赖** | P0-a4、P0-a5/M4-d3 |
| **V 指标** | 归入 **V3**（A/B 判定覆盖）+ 本节本地判据：A/B 写 `coach.mb_learning_rate` ⇒ `mb_effective_lr` 必须变化；**`lr_adapt != 1.0` 至少在 1% 的 tick 出现** |
| **R 回退** | 无 A/B 响应 ⇒ 把 `coach.mb_learning_rate` 从搜索空间剔除（写 `param_wiring_ab.json`）；`mb_effective_lr` 无变化 ⇒ 判 `wired=false` |
| **⚠ 回归风险（施工必检）** | `fly64/tests/test_mushroom_body.py:411` 与 `fly64/tests/test_mbon_saturation.py:229` **PIN 断言 `mb.lr_adapt == 1.0`**（均为 `MushroomBody()` 默认构造，非运行实例）。接线后若这些测试仍自建实例则**不受影响**；若被改为共享实例则**必然转红**。⇒ **施工时先跑 `python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q`，记录基线后再改** |

#### P1-b6-2 `_kc_activity` 无写入点（异常消解记忆守卫恒假）→ **选"写入"**

| 字段 | 内容 |
|---|---|
| **文件·行号** | 消费点 `fly64/fly64/main.py:2693-2699`；守卫实现 `fly64/fly64/mushroom_body.py:513-539`（`consolidate_anomaly_resolution`）；写入落点 `fly64/fly64/model.py`（`step()` 内，`mushroom.encode()` 的中间量处） |
| **改前** | `main.py:2693-2699`：<br>`                # P0: anomaly resolution → consolidate scene+action memory`<br>`                # so the brain learns which motor output breaks each anomaly.`<br>`                if memory_ctrl.anomaly._anomaly_resolved:`<br>`                    _kc_sig = getattr(model, "_kc_activity", None)`<br>`                    if _kc_sig is not None:`<br>`                        model.mushroom.consolidate_anomaly_resolution(`<br>`                            _kc_sig, control.x, control.y)`<br>**实测（本机 grep 全仓）**：`_kc_activity` 的**唯一命中是 `main.py:2696` 的读取**；**无任何写入点** ⇒ `_kc_sig` 恒 `None` ⇒ 该路径永不执行 |
| **改后** | 在 `model.py` 的 `step()` 内（KC 稀疏活动向量产生处）写入：<br>`        self._kc_activity = <KC sparse activity vector, float32>`<br>（恢复"场景+动作 → 召回"的记忆成因；**不得**改动 `consolidate_anomaly_resolution` 的语义） |
| **接口签名** | 新增 `FlyModel._kc_activity: np.ndarray \| None`（**dtype float32，与 `kc_sig` 消费方一致**） |
| **依赖** | P0-a5/M4-d3（`mb_consolidated_anomaly_count` 落盘） |
| **V 指标** | 本节本地判据：`mb_consolidated_anomaly_count > 0`，且 A/B 变更场景后召回次数变化 |
| **R 回退** | 计数恒 0 ⇒ 判路径仍不通，**删除该路径分支**并把 `_kc_activity` 登记为 `unreachable`（不得保留"看着像生效"的死路径） |

#### P1-b6-3 `_last_burst_tick` 只读不写（防重入守卫恒真）

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/fly64/main.py:2062`（守卫读）、`:2063-2066`（burst 启动处 **= 写入落点**）、`:2082`（`control.jump = False`）、`:1447-1448`（burst 状态声明） |
| **改前** | `main.py:2055-2066`：<br>`            if (deadlock_burst_ready(`<br>`                    stuck_duration=memory_ctrl.stuck_duration,`<br>`                    loop_score=memory_ctrl.spatial.loop_score,`<br>`                    disp_60s=getattr(memory_ctrl, "disp_60s", None),`<br>`                    median_speed=getattr(memory_ctrl, "median_speed", None),`<br>`                    loop_breakout_threshold=float(`<br>`                        _expl.get("loop_breakout_threshold", 0.90)))`<br>`                    and not getattr(memory_ctrl, '_last_burst_tick', 0) == model.step_count):`<br>`                if _deadlock_burst_cooldown <= 0:`<br>`                    _deadlock_burst_remaining = 200  # ~4s forward burst`<br>`                    _deadlock_burst_cooldown = 300`<br>**实测**：`_last_burst_tick` 全仓**只在此处被读**，**无写入** ⇒ `getattr(...,0) == model.step_count` 在正常 tick 恒假 ⇒ **守卫恒真（形同不存在）** |
| **改后** | 在 burst 启动块内写入实际 burst tick：<br>`                    memory_ctrl._last_burst_tick = model.step_count`<br>**并同时**处置 `main.py:2082` 的 `control.jump = False`：**按 P1-b5 的"冲突矩阵"四条裁决执行**（F6 扩展：该审查不止与 b3 有关，还与 CX 突破、CPG 权威两两相关） |
| **接口签名** | `MemoryController._last_burst_tick: int`（由"只读属性"变为"有状态字段"） |
| **依赖** | **P1-b5**（冲突矩阵先裁决）、P0-a5/M4-d3 |
| **V 指标** | 本节本地判据：6000 tick 内 `deadlock_burst_count` 与占空比（应 ≈ **200/500 tick**）一致；`_last_burst_tick` **单调递增**；`cx_loop_break_count_burst_off` 与 `deadlock_burst_count` 时间戳集合**不相交** |
| **R 回退** | 占空比偏离 200/500 ⇒ 回退本项（恢复原守卫形态）并写 `medium` finding；时间戳集合相交 ⇒ 按 F6 放弃归因（见 P1-b5 回退条款） |

#### P1-b6-4 `gate_forward` / `gate_jump` 无执行侧消费者

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/fly64/main.py:2883-2957`、`:3064`；`fly64/plugin/scene_context.py:115-116`、`:228-235` |
| **改前** | `scene_context.py:233-234`：<br>`        gate_forward=bool(_get_safe(flow, "gate_forward", default=False)),`<br>`        gate_jump=bool(_get_safe(flow, "gate_jump", default=False)),`<br>**消费形态**：消费的是**布尔量** `gate_forward`/`gate_jump`，**不是阈值本身**（F15 校正：原方案 §2.3 表把消费者记为 `scene_context.py:234`，实际 `:234` 消费布尔 `gate_jump`） |
| **改后** | 由 **P1-b3** 统一口径后，`gate_jump_threshold` **获得真实消费者**（比值门直接决定 `model.py:2478` 的行为；遥测镜像随之对齐）；`gate_forward_threshold` **同法接到 P0-a4 的 A/B**（不作为本项独立改动） |
| **接口签名** | 无新签名（消费者形态不变，仍是布尔 `gate_*`） |
| **依赖** | **P1-b3** |
| **V 指标** | **V3**（A/B 两个 pid 均须改变行为量） |
| **R 回退** | 见 P1-b3 的 R2 / R13 |

#### P1-b6-5 深坑/地下跳跃护栏与对话/教练直写 jump → **保留**

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/fly64/main.py:2358-2384`（护栏）、`:2279-2323`（对话）、`:2330-2348`（教练命令消费者） |
| **处置** | **保留**（安全与人工通道不受本方案约束），但**不进入闭环输出面** |
| **判据** | `param_authority` **不记录**这些写入（硬约束 C7）；`param_history.jsonl` 中直写记 `source = "coach-direct"`、安全通道记 `source = "safety-guard"`（**统一到 `source` 字段，不新增 `owner`**） |
| **归属** | 与 **M4-d5-f** 同一处置，本处只作 P1 侧的登记 |

---

## 4. P2 变更规格（§6 · M2 仲裁与升级语义）

### P2-c1 — 升级状态机（c1）+ `_vote`/`ArbitrationState` 接口契约（F14）

| 字段 | 内容 |
|---|---|
| **ID** | `P2-c1`（原 §6.1 + §6.1.1） |
| **文件·行号** | ① **新增** `fly64/fly64/arbitration.py`<br>② `fly64/fly64/memory.py:1347-1373`（`_vote`，**结构替换为 `_vote_all` + `_vote(allowed=...)`，不改优先顺序**）<br>③ `fly64/fly64/main.py:2009-2017`（反射 update 处）、`:2018-2035`（状态多数票处） |
| **改前** | `memory.py:1347-1373`（**扁平首命中，无严重度分层**）：<br>`    def _vote(self, *, ramp_score: float = 0.0,` … `              median_speed: float | None = None) -> str:`<br>`        """Return the per-frame state name, prioritised by severity."""`<br>`        fallen_active = pos_y is not None and pos_y != 0.0 and self._detect_fallen(pos_y)`<br>`        if fallen_active:`<br>`            return self.FALLEN`<br>`        if self._detect_micro_loop(visited_cells, loop_score, stuck_duration,`<br>`                                   disp_60s=disp_60s, median_speed=median_speed):`<br>`            return self.MICRO_LOOP`<br>`        if self._detect_oscillating(disp_60s=disp_60s, median_speed=median_speed):`<br>`            return self.OSCILLATING`<br>`        if self._detect_wall_stuck(wall_score, escape_behavior, stuck_duration):`<br>`            return self.WALL_STUCK`<br>`        if self._detect_stuck_ramp(ramp_score, stuck_duration, heading_rate):`<br>`            return self.STUCK_RAMP`<br>`        return self.IDLE`<br>**实测顺序**：`fallen`(:1362) → `micro_loop`(:1364) → `oscillating`(:1367) → `wall_stuck`(:1369) → `stuck_ramp`(:1371) → `idle`(:1373) |
| **改后** | ① `memory.py` 结构替换（**仅内部，默认输出逐 tick 相同**）：<br>```python<br>def _vote_all(self, *, ramp_score=0.0, stuck_duration=0.0, ...) -> list[str]:<br>    """全部命中类别，按现有严重度顺序；不做首命中短路。无副作用、无新状态。"""<br>def _vote(self, *, ..., allowed: set[str] | None = None) -> str:<br>    hits = self._vote_all(...)<br>    if allowed is None:<br>        return hits[0] if hits else self.IDLE      # ← 与改动前逐 tick 相同（PIN）<br>    return next((c for c in hits if c in allowed), self.IDLE)<br>```<br>② **新增** `fly64/fly64/arbitration.py`（**只做状态记账与升级决策，不写 `control.*`**）：<br>· `intervention`：当前落点（`param_scope`）<br>· `ineffective_ticks`：本次干预累计无效时长<br>· `exhausted_params`：已穷尽的参数集合（来自 P0-a4 的 A/B 结论）<br>· `upgrade_level ∈ {0 参数 → 1 增益 → 2 仲裁}`<br>· `upgrade_history`：每次升级的 `(ts, from, to, trigger, outcome)`<br>**触发**：`ineffective_ticks > dwell_ticks`（**H14，初值 1500 tick**，由 M4-d3 的观测标定）且本次干预成效分（M4-d2）未改善 ⇒ 升级一级<br>**升级动作只允许两类**：`level 0→1` = 搜索重心从"参数值"移到"通路增益/腿权重"（b1/b2 的参数）；`level 1→2` = 切换仲裁类别（如 `stuck_ramp → oscillating`，或允许 CX 环路突破接管）并固化 `exhausted_params`<br>③ `main.py:2009-2017` 与 `:2020-2035` 挂接 `ArbitrationState.update(...)`；<br>④ `memory.py:1347-1373` **不改优先顺序**（严重度排序语义正确），而是让 `ArbitrationState` 持有"本次允许的类别集合"并**在同一严重度层内引入竞争力**（同层多命中时按成效分选择） |
| **接口签名** | `MotionStateDetector._vote_all(self, *, ramp_score: float = 0.0, stuck_duration: float = 0.0, heading_rate: float = 0.0, wall_score: float = 0.0, escape_behavior: bool = False, visited_cells: int = 0, loop_score: float = 0.0, pos_y: float \| None = None, disp_60s: float \| None = None, median_speed: float \| None = None) -> list[str]`<br>`MotionStateDetector._vote(self, *, ..., allowed: set[str] \| None = None) -> str`（**新增关键字参数，默认 `None`**）<br>新增 `ArbitrationState.update(...) -> dict`、`ArbitrationState.state -> dict`<br>新增 `flow.json["arbitration"] = {situation_key, level, ineffective_ticks, exhausted_params, last_upgrade_ts, candidates}`<br>新增 `situation_key = (scene_key, anomaly_class)` |
| **禁止（写进断言）** | 改 `_vote_all` 的严重度顺序；写 `control.*`；覆盖更高优先级机制（`burst > primitive > lif`，见 P1-b5） |
| **依赖** | **M4-d2**（成效分必须可分辨，否则"无效"无定义）、**P0-a5/M4-d3**（`arbitration` 落盘）、P1-b1/b2（增益升级的对象） |
| **V 指标** | **V13**（复现卡死场景下 `ineffective_ticks` 越过 `dwell_ticks` 后 `level` 从 0 升到 ≥1 且 `upgrade_history` 非空；6000 tick 内 `level` **升降次数 ≤ 2**；`level` 上界 2，达 2 后不再产生写入）<br>**PIN（F14）**：① `allowed is None` 时 `_vote` 输出与基线**逐 tick 相同**；② 复现场景 `level` 从 0 升 ≥1、6000 tick 内升降 ≤2 |
| **R 回退** | **R4**（抖动或无界搜索）：`arbitration.level` 升降 > 2 次/6000 tick ⇒ `dwell_ticks` ×2（**最多 ×4**）；仍失败 ⇒ **停用状态机**（`arbitration_enabled=false`），**只保留只读遥测**<br>条件 ① 失败（升级未发生）⇒ 说明 M4-d2 的成效分仍不可分辨，**回退到 P0/P1 阶段，不得进入 P3** |
| **假设** | **H14**（`dwell_ticks = 1500` 仅为设计初值；可能过长或过短，需复现场景下 `ineffective_ticks` 分布标定） |

---

### P2-c2 — `terminal_surrender` 终态判据 + 四机制前置解锁

| 字段 | 内容 |
|---|---|
| **ID** | `P2-c2`（原 §6.2） |
| **文件·行号** | ① `fly64/fly64/memory.py:1319-1321`（`_detect_wall_stuck`）<br>② `fly64/skills/default_patterns.json`（`circle_loop` / `micro_loop_weave_signal` 的排除条件 + 新增 pattern）<br>③ `fly64/skills/evolution_skill.py:2570-2580` 附近（新 pattern 的脑侧响应）<br>④ 输入量：`memory.py:1135-1160`（`progress_is_ineffective`）、M4-d2 的 `waste_ratio`、净位移率 |
| **改前** | `memory.py:1319-1321`：<br>`    def _detect_wall_stuck(self, wall_score: float, escape_behavior: bool,`<br>`                           stuck_duration: float) -> bool:`<br>`        return wall_score > 0.4 and escape_behavior and stuck_duration > 10.0`<br>**自锁证据**：<br>· `_detect_wall_stuck` 要求 `escape_behavior AND stuck_duration > 10.0`<br>· pattern `circle_loop` 要求 `wall_score ≤ 0.1`（贴墙时 `wall_score > 0.4` ⇒ 排除）<br>· pattern `micro_loop_weave_signal` 要求 `escape_behavior = true`（放弃时 `false` ⇒ 排除）<br>⇒ **"放弃"既是否定检测的条件、又是结果** |
| **改后** | ① `memory.py:1319-1321` 增加**独立于 `escape_behavior`** 的并行判据（**保留原判据，新增一条 OR 支路，不删除**）：<br>`        return (wall_score > 0.4 and stuck_duration > 10.0`<br>`                and (escape_behavior or surrender_evidence))`<br>② 新增判据 `terminal_surrender`（**观测/诊断层，不写控制**）：<br>`(stuck_duration_true > T_s) AND (loop_score > L) AND (waste_ratio > W) AND (reflex_active = false OR escape_behavior = false) AND (net_displacement_rate < D)`<br>**关键：`stuck_duration` 必须用 P0-a2/a3 重建后的真实量或轨迹运动学量，不得使用伪影值**<br>初值 `T_s = 120 s`、`L = 0.6`、`W = 10`、`D = 0.5 u/s`（**由 M4-d3 的观测标定 ⇒ 【待标定】**）<br>③ `default_patterns.json`：`circle_loop` / `micro_loop_weave_signal` 的排除条件改为"挣扎态 **或** 终态"（即排除条件**只排除"正常探索"**），并新增 `terminal_surrender_stuck` pattern（`severity: high`）<br>④ `evolution_skill.py:2570-2580` 附近为 `terminal_surrender_stuck` 提供"脑侧响应"（见 M4-d5-b） |
| **接口签名** | 新增 `MemoryController.terminal_surrender -> bool`（property）<br>新增 `MemoryController.surrender_evidence -> dict`（各分量：`stuck_duration_true`、`loop_score`、`waste_ratio`、`reflex_active`、`escape_behavior`、`net_displacement_rate`）<br>新增 `flow.json["terminal_surrender"]`（bool）、`flow.json["surrender_evidence"]`（dict）<br>新增 pattern id `terminal_surrender_stuck`（`severity: high`） |
| **依赖** | **P0-a2 + P0-a3**（真实时长）、**M4-d3**（观测标定阈值）、**M4-d5-a**（pattern 键生产者） |
| **V 指标** | **V17**（终态回放 = `true`；正常探索段 = `false`）<br>③ **真引擎回放**：t2 §2.2 的报告故障快照在改后必须至少命中一个 `high` 级 pattern（对照改前 **0 个 high**）⇒ 与 **V14** 合并验收 |
| **R 回退** | 条件 ② 失败（正常段误判终态）⇒ 提高 `T_s` 与 `D`（更保守）；**连续两次失败 ⇒ 把该 pattern 降为 `medium` 并只记录 finding**（不触发任何响应） |
| **假设** | **H2**（报告 `anomaly_state="stuck_ramp"` 在 HEAD 上不可复现 ⇒ 阈值标定需该 run 的 `exploration_mode` + `anomaly_state_history`） |

---

### P2-c3 — 检测窗自适应于实测交替周期（对 H3）

| 字段 | 内容 |
|---|---|
| **ID** | `P2-c3`（原 §6.3） |
| **文件·行号** | ① `fly64/fly64/memory.py:1281`（`_ctrl_x_buf` 的 `maxlen`）、`:1289-1317`（`_detect_oscillating`）<br>② `fly64/fly64/memory.py:1394`（`_ctrl_x_buf.append`）附近<br>③ `fly64/fly64/memory.py:1377-1462`（`update` / 多数票，窗口在 `_vote` 前计算并传入） |
| **改前** | `memory.py:1280-1281`：<br>`        # Oscillation detection: history of control.x for sign-change counts`<br>`        self._ctrl_x_buf: deque[int] = deque(maxlen=window)`<br>`memory.py:1291`：<br>`        """Detect oscillation in control.x: ≥3 alternations between ≤-60 and ≥+60.`<br>`memory.py:1317`：<br>`        return alternations >= 3`<br>**实测**：符号交替占 57% 采样步（3419/5999）、`run len = 1` 占 3086/3476、采样间隔 0.21 s ⇒ 一次完整往返 ≈ **17–18 tick ≈ 0.37 s** ⇒ 30 帧窗内仅 ≈3–3.5 次切换 ⇒ **正卡在 `>= 3` 门限上 ⇒ 抖动** |
| **改后** | ① **窗口由被测系统自身的交替周期确定**（**不新增门限，改的是"窗口的确定方式"**）：<br>`W = clip(6 · T_alt, 30, 300)` 帧，其中 `T_alt` = `_ctrl_x_buf` 的**最近符号切换间隔的中位数**（帧）；**门限 `alternations >= 3` 不变**<br>物理含义："以 6 个真实周期为观察窗"：0.37 s 周期 ⇒ `W ≈ 110` 帧（2.2 s）；慢速交替 ⇒ 窗口自动变短<br>② `memory.py:1281` 的 `maxlen` 改为**上界 300**（`deque(maxlen=OSC_WINDOW_MAX)`），实际窗口由 `W` 截取；<br>③ `memory.py:1394` 附近记录符号切换时间戳；<br>④ `memory.py:1377-1462` 的 `update`/多数票在 `_vote` 前计算 `W` 并传入 |
| **接口签名** | 新增常量 `OSC_WINDOW_MIN = 30`、`OSC_WINDOW_MAX = 300`、`OSC_CYCLES_PER_WINDOW = 6`<br>`MotionStateDetector._detect_oscillating(self, disp_60s=None, median_speed=None, window: int \| None = None) -> bool`（**追加关键字参数，默认 `None` ⇒ 用 `W`**）<br>新增 `flow.json` 键：`oscillation_window_frames`、`oscillation_alt_median_s`、`oscillation_detected` |
| **依赖** | **M4-d3**（三个观测键落盘）、P0-a4（A/B） |
| **V 指标** | **V18**（复现交替场景下连续 600 tick 内 `oscillation_detected` 翻转次数 ≤ 4，而改前是逐 tick 抖动；② 可标定：A/B 把窗长系数 6 改为 3/12 ⇒ `oscillation_window_frames` 随之改变；③ 正常探索段 `oscillation_detected` 占比 ≤ 5%） |
| **R 回退** | **R5**（检测窗自适应把正常探索判为振荡）：正常段占比 > 5% ⇒ 收紧为 `alternations >= 5`（**提高而非降低门槛**）<br>条件 ① 失败（仍抖动）⇒ 回到**固定 30 帧并只记录**（该检测不再驱动反射），另在 `evolution_log` 写 `medium` finding |
| **假设** | **H3**（oscillating 检测在真实 run 中抖动；支持证据 = 门限 `memory.py:1317` vs 实测周期 ≈0.37 s；需原始 `ctrl_x` 序列才能最终关闭） |

---

### P2-c4 — CPG 运动原语的竞争槽（`_lif_motion` 恒真的处置，**F4 权威谓词替换**）

| 字段 | 内容 |
|---|---|
| **ID** | `P2-c4`（原 §6.4） |
| **文件·行号** | ① `fly64/fly64/main.py:2521-2530`（取权条件 + 执行点）<br>② `fly64/fly64/main.py:2438-2511`（CPG 请求处）<br>③ `fly64/fly64/arbitration.py`（新增 `primitive` 候选与 `authority` 字段）<br>④ `fly64/fly64/motor_primitives.py:62-123`（**不变**） |
| **改前** | `main.py:2519-2530`：<br>`            # The hardcoded primitive takes the stick ONLY on ~zero LIF`<br>`            # output.  decision_source records lf_steering / lf_escape.`<br>`            _lif_motion = (abs(control.x) > LIF_MOTION_MIN`<br>`                           or abs(control.y) > LIF_MOTION_MIN)`<br>`            if cpg_phase is not None:`<br>（…）<br>`                if not _lif_motion:`<br>`                    control = cpg_apply_phase(control, cpg_phase)`<br>**实测**：`_lif_motion` 在当前运行点**恒真**（`control.y = 70 > 8`）⇒ 运动原语（longjump / backflip …）**结构性不可达**（t1 S29） |
| **改后** | ① **不改 `_lif_motion` 的数值判据**（`LIF_MOTION_MIN = 8` 仍是"LIF 是否在动"的传感量），而是把**持有运动权威者**从"隐含的 `not _lif_motion`"改为由 P2-c1 仲裁状态机维护的**单一谓词** `authority ∈ {lif, primitive}`：<br>`            def _has_motion_authority(): return self._authority == "lif"`<br>**原表达式被"移入" `authority` 的判定里，不是在它后面 `or` 一条**（R3 单一口径）：<br>`            _lif_motion = (abs(control.x) > LIF_MOTION_MIN or abs(control.y) > LIF_MOTION_MIN)`（**保留为传感量**）<br>`            self._arbitration.register_candidate("primitive", score=...)`<br>`            self._authority = self._arbitration.resolve_authority(lif_motion=_lif_motion)`<br>`            if self._authority == "primitive":`<br>`                control = cpg_apply_phase(control, cpg_phase)`<br>② `main.py:2438-2511` 的 CPG 请求改为**注册到 `ArbitrationState`**（**不直接取操纵权**）<br>③ `arbitration.py` 增加 `primitive` 候选类型与 `authority` 字段（`burst > primitive > lif`，与 P1-b5 冲突矩阵一致）<br>④ `motor_primitives.py:62-123` **不变**<br>⑤ **静态断言（并入 M4-d1 的 T3 断言文件）**：<br>　 · **禁止**在 `main.py:2521` 的表达式上追加 `or` 支路（正则检查"含 `_lif_motion` 的行不得出现 `or <新标识符>`"）<br>　 · 断言任何 `control.` 赋值的新增行数为 **0** |
| **接口签名** | 新增 `ArbitrationState.register_candidate(kind: str, score: float) -> None`<br>新增 `ArbitrationState.resolve_authority(lif_motion: bool) -> str`（返回 `"lif"` / `"primitive"`）<br>新增 `flow.json["motion_authority"] ∈ {"lif","primitive"}`、`flow.json["primitive_granted_count"]`、`flow.json["arbitration"]["candidates"]` |
| **依赖** | **P2-c1**（仲裁状态机必须先有）、P1-b5（冲突矩阵：`burst > primitive > lif`） |
| **V 指标** | **V13** 的扩展 + 本节判据：① 在 `stuck_duration`/`loop_score` 高且 LIF 解码成效分低的场景下 `primitive_granted_count ≥ 1`（对照改前 **0**）且 `motion_authority` 至少出现过一次 `"primitive"`；② 正常前进段必须为 0；③ 授予后 **300 tick 内 `net_displacement_rate` 不下降**；④ **权威唯一性**：任一 tick 的 `motion_authority` 只有一个取值，且 `burst_active ⇒ authority != "primitive"` |
| **R 回退** | 条件 ③ 失败 ⇒ 提高 `primitive` 候选的入场门槛（成效分需高于 LIF 解码 **1.5×**）；连续两次失败 ⇒ **停用该候选类型**（`primitive_candidate_enabled=false`）<br>**若实现时发现"授予 → 执行"只能靠给 `_lif_motion` 追加 OR 支路（即无法用权威谓词替换实现）⇒ 按 t5 §F4 直接判定本项不可行**：从 P2 **移除 P2-c4**，只保留"`primitive_granted_count` 恒 0"的观测与一条 `medium` finding（**诚实标注 CPG 在当前运行点不可达**），**不做折中实现** |
| **假设** | 无（E-1：`_lif_motion` 判据与 `control.y = 70` 的实测值可直接证实恒真） |
| **执行落点声明（施工必读）** | 仍由**既有**的 `control = cpg_apply_phase(control, cpg_phase)`（`main.py:2530`）写控制量 —— 这是一个**已存在的调用点**，本项**不新增任何 `control.*` 赋值位置**（满足 R1/R2/R3） |

---

## 5. M4 变更规格（§7 · 进化闭环）

### M4-d1 — 新输出面 T1/T2/T3 + T3 降级（F3 门禁 + 运行时守卫 + 静态断言）

| 字段 | 内容 |
|---|---|
| **ID** | `M4-d1`（原 §7.1） |
| **文件·行号** | ① `fly64/skills/evolution_skill.py:2644`（门禁插入点）、`:2653-2668`（`FixExecutor` 调用，实际调用 `:2655`）<br>② `fly64/skills/fix_executor.py:437-443`（`execute` 入口）、`:468`（`parse_fix_template` 调用）、`:485-488`（`directive.get("file")`）、`:602-608`（`_resolve_file`，模板优先）<br>③ **新增** `fly64/skills/fix_guard.py`<br>④ **新增** `fly64/skills/change_proposals.jsonl`<br>⑤ **新增** `fly64/tests/test_evolution_fix_contract.py`<br>⑥ T1/T2 落点：`fly64/skills/active_strategy.json` + `fly64/fly64/main.py:1678-1863`（热重载） |
| **改前** | `fix_executor.py:485-488`：<br>`        for directive in directives:`<br>`            action = directive.get("action", "")`<br>`            file_rel = directive.get("file", "")`<br>`            file_path = self._resolve_file(file_rel, fix_files)`<br>`fix_executor.py:602-608`：<br>`    def _resolve_file(self, file_rel: str, fix_files: Optional[list[str]] = None) -> Optional[Path]:`<br>`        """Resolve a relative file path against the workspace root.`<br>（…）<br>`        rel = file_rel or (fix_files[0] if fix_files else "")`<br>`evolution_skill.py:2643-2655`：<br>`            for f in result.findings:`<br>`                if not self.fix_catalog.has_fix(f.pattern_id) and self.auto_fix:`<br>`                    entry = self.fix_catalog.record_fix(f)`<br>（…）<br>`                        if self.fix_executor is not None:`<br>`                            exec_report = self.fix_executor.execute(`<br>**风险（F3）**：`_resolve_file` 的实际目标是**模板内的 `# File:` 优先**，`fix_files` 只作回退 ⇒ 只判 `fix_files` 会被"`fix_files: []`（或非 `.py`）但模板里写着 `# File: fly64/fly64/main.py`"的 fix 绕过 |
| **改后** | **T1/T2/T3 三层分级**：<br>· **T1**（唯一自治类）：对 `active_strategy.json` 中**已注册 + 已通过运行时 A/B** 的 `pid` 有界写入（`min/max` 来自 `brain_tunable_params.json`，且实际钳位与注册区间**必须相交**）<br>· **T2**：增益/腿权重/稳态参数（`escape.jump_leg_weight`、`escape.jump_intrinsic_max`、`DopamineGainController` 初始增益）— **A/B 通过后**允许<br>· **T3**：**代码补丁（`fix_template` 写 `.py`）禁止进入闭环执行路径** ⇒ 降级为**只读变更提案**（写 `change_proposals.jsonl`，需人工批准后才可落地）<br>**T3 降级实现要点（双道 + 第三道）**：<br>① **门禁判据必须覆盖两处来源**：`f.fix_files` **∪** `parse_fix_template(f.fix_template)` 返回的全部 directive 的 `directive["file"]`<br>② **门禁落点**：`evolution_skill.py:2644` 的 `if not self.fix_catalog.has_fix(...) and self.auto_fix:` **之后**、`FixExecutor` 调用（`:2653-2668`）**之前**加执行门禁：命中 `.py` 且未获批准 ⇒ **只写提案，不执行**<br>③ **运行时守卫（第二道，且是唯一能阻止运行期旁路的那道）**：在**唯一写盘点** `FixExecutor.execute`（`fix_executor.py:437` 起，`parse_fix_template` 在 `:468`）**入口**用**同一 helper** 重新计算"本次是否命中 `.py`"，命中且未持批准令牌（`approved_proposal_ids`）⇒ 立即返回 `FixExecutionReport(manual_action_needed=True)` 且**不产生任何写盘动作**<br>④ **同一 helper 复用**：门禁与守卫**必须调用同一个函数** ⇒ **新增** `fly64/skills/fix_guard.py:is_py_patch(fix_template: str, fix_files: list[str] \| None) -> bool`（避免两处判据漂移，R3 单一口径）<br>⑤ **静态断言（第三道，防回归）**，落在**新增** `fly64/tests/test_evolution_fix_contract.py`：<br>　 · 禁止 `fix_template` 中出现 `control.x` / `control.y` / `control.jump` 的**赋值**<br>　 · "`FixExecutor.execute` 是唯一允许写 `.py` 的函数"（`grep -n "\.write_text(" fly64/skills/*.py` 白名单化）<br>　 · 新增 `control.*` 赋值行数 = 0<br>⑥ 提案文件必须带 `proposed_by / pattern_id / rationale / expected_metric / verification_window` |
| **接口签名** | `fix_guard.is_py_patch(fix_template: str, fix_files: list[str] \| None) -> bool`<br>`FixExecutor.execute(..., approved_proposal_ids: set[str] \| None = None) -> FixExecutionReport`（**新增可选参数**）<br>新增 JSONL 记录字段：`proposed_by, pattern_id, rationale, expected_metric, verification_window, ts, proposal_id` |
| **legacy 路径处置** | 旧副本是 `fly64/skills/evolution_agent.py`（**t5 写作 `fly64/fly64/evolution_agent.py`，该路径不存在**）。本机核查：其 `--auto-fix` 分支（`:357-360`）**只 `record_fix` + `print`，不调用 `FixExecutor`、不写 `.py`** ⇒ 判定为**不是第三条执行路径**；但处置上仍要求"任何未来的写入者都必须经同一 helper" |
| **依赖** | —（可与 P0 并行） |
| **V 指标** | **V20**（① 门禁（`evolution_skill.py:2644` 之后）② **`FixExecutor.execute` 内运行时守卫** ③ 静态断言 `test_evolution_fix_contract.py` ④ `change_proposals.jsonl`）<br>判据：**0 条 `.py` 补丁被执行；全部落提案；判据同时覆盖 `fix_files ∪ parse_fix_template(...).file`**；运行时守卫**可被独立注入测试**（构造 `fix_files=[]` 但模板含 `# File: …main.py` 的用例**必须被拦下**） |
| **R 回退** | 断言/守卫失败 ⇒ **阻断 P2 上线**（G6）；门禁与守卫必须是**同一 helper**（不得两处判据漂移） |
| **假设** | 无（F3 证据为 `fix_executor.py:488-489`、`:603-609` 的逐行读取） |
| **附：现状计数（施工前基线，本机复算）** | `fix_catalog.json` `meta`：`total_fixes 19 / effective_count 0 / ineffective_count 11 / reverted_count 8`；按 `reverted == false` 过滤得 **11** 条，覆盖 **11** 个 distinct `pattern_id`（`below_ground_stuck, circle_loop, cliff_standoff, fallen_recovery_stuck, low_coverage_stagnation, mbon_saturation, micro_loop_weave, primitive_zero_disp, ramp_trap, suspended_animation, telemetry_gap`）；其中 **10 个**是 `default_patterns.json` 的 pattern，`telemetry_gap` 不是 pattern（属诊断/遥测类 finding） |

---

### M4-d2 — 适应度可分辨性（五段修复 + A/A 零假设门，**F5**）

| 字段 | 内容 |
|---|---|
| **ID** | `M4-d2`（原 §7.2） |
| **文件·行号** | ① `fly64/skills/evolution_skill.py:2460`（`run_time = 120.0`）、`:2499-2505`（窗口与 `delta > 0.03`）、`:2490`/`:2532`（`self._inject({})` 回滚）、`:2238-2267`（`_inject`）、`:2325-2326`（`_subset_k`）、`:2019-2036`（`unstuck` 项）、`:2119`（`missing_inputs`）、`:788-829`（`DataCollector.sample`）、`:2623-2703`（`run_one_cycle`）<br>② `fly64/fly64/main.py:1678`（热重载周期）、`:1742-1753`（钳位回写，需让行）<br>③ **新增** `fly64/skills/fitness_aa_gate.py`、**新增** `fly64/skills/fitness_aa_report.json` |
| **改前** | `evolution_skill.py:2460`：`        run_time = 120.0  # trial window: 120 s from start`<br>`evolution_skill.py:2499-2505`：<br>`        if time.time() - self._trial_start < run_time:`<br>`            return None`<br>`        current_fitness = (self.fitness(metrics, self._baseline_sample)`<br>`                           if metrics else 0.0)`<br>`        delta = current_fitness - self._baseline_fitness`<br>`        passed = delta > 0.03  # 3% improvement threshold`<br>`evolution_skill.py:2325`：`        _subset_k = min(5, ndim)`<br>`evolution_skill.py:2490` / `:2532`：`            self._inject({})  # resets to defaults only`<br>`evolution_skill.py:2021` / `:2033` / `:2036`：`        stuck = num("stuck_duration", 0.0)` … `            unstuck = (1.0 - min(stuck / 120.0, 1.0)) * 0.20`<br>**四个可复现的失效原因（E-1/E-2）**：<br>1. 试验窗固定 **120 s 墙钟**，与"参数热重载每 600 tick"和"仿真时间"都未对齐<br>2. **基线静默漂移**：`main.py:1742-1753` 每 600 tick 钳位并回写；而回滚是 `_inject({})`，**实际把"当前文件值"写回去，不是注入前的快照**<br>3. **一次试验 ≤5 维同时变** ⇒ 多维变更不可归因<br>4. fitness 的 `unstuck` 项读 `stuck_duration` —— 该量在 HEAD 上正是伪影 ⇒ 顶层行为项建立在失真量上 |
| **改后** | **五段修复**：<br>1. **窗口对齐**：试验窗改为 `max(600 ticks, 60 s 仿真时间)` 的**整倍数**，并要求窗口内**参数未被第三方改写**（用 P0-a4 的租约保证）。落点 `:2460` 与 `run_one_cycle`（`:2623-2703`）<br>2. **真回滚**：`_inject` 前用 `ParamAuthority.snapshot()` 取快照；失败时 `restore(snapshot)`（**逐 pid 精确恢复**），并在租约有效期内让 `main.py` 的自愈回写**让行**。落点 `:2238-2267, :2490, :2532`；`main.py:1742-1753`<br>3. **单维/低维归因**：`_subset_k` 从 **5 降到 1–2**，并记录"本次移动的维"与其**在 A/B 语义下的消费点**。落点 `:2325-2326`<br>4. **剔除伪影输入**：`unstuck` 项不再读 `stuck_duration`，改用 P0 重建后的真实量或**轨迹运动学量**（`net_displacement_rate` / `net_disp_60s`），并把 `missing_inputs` 变为**硬门**（非空 ⇒ 本次试验作废）。落点 `:2019-2036, :2119`<br>5. **适应度定义（可分辨量的长窗均值，权重和为 1）**：<br><br>| 项 | 定义 | 权重 | 为什么可分辨 |<br>|---|---|---|---|<br>| `net_disp_rate` | 窗口内**净位移 / 累计路径**（方向效率，无量纲） | 0.30 | 直接来自轨迹运动学，不依赖任何脑内派生量；对照实测 2.75%/5.35% 有巨大动态范围 |<br>| `coverage_gain` | `(visited_cells_end - visited_cells_start) / window_s` | 0.20 | 整数格数，量化误差小；15% 覆盖率下有充足增长空间 |<br>| `loop_penalty` | `-min(loop_score/3, 1)` | 0.15 | `loop_score` 由空间记忆直接计算 |<br>| `waste_penalty` | 现有 `waste_ratio` 惩罚（`:2099-2105`） | 0.10 | 已有实现 |<br>| `learning_progress` | `Δgain_update_count` 与 `Δmb_assoc_count` 的归一化 | 0.10 | **区分"参数改了但没学到"与"学到了"** |<br>| `meta_channel` | `Δ(intervention 成效分)`，即 P2-c1 的升级成效 | 0.15 | 使"换招是否有效"成为可搜索的目标 | |
| **接口签名** | **新增** `fly64/skills/fitness_aa_gate.py`（**复用 `BrainMutator.fitness_components`，只做统计**）<br>**新增产物** `fly64/skills/fitness_aa_report.json`：`{n_windows, p95, bootstrap_ci, k, threshold, aa_two_window_fpr, unmeasurable_dims}`<br>`EvolutionPipeline` 新增 `sigma_floor: float = 0.03`、`aa_k: int = 2`、`dwell_ticks: int = 1500`（供 P2-c1 使用） |
| **A/A 零假设门（**关键新增，F5 四项**）** | **F5-① 门与 commit 阈值必须脱钩，且 commit 阈值随噪声标定**：门 `P95(\|delta_A/A\|) ≤ σ_floor`（σ_floor 初值 0.03）；commit 阈值 `threshold = max(0.03, k · P95_noise)`（`k ≥ 2`，默认 2，`P95_noise` 取自最近一次 A/A 报告）。**原设计把门与 commit 阈值都写成 0.03 ⇒ 由构造决定最多 5% 的零假设窗口会越过 commit 阈值（假阳性下界 = 门分位数本身）**。若改用显式显著性检验（置换 / paired t）也可以，但**必须同时声明目标 FPR 与功效**（如 FPR ≤ 1%、power ≥ 0.8 @ 效应 0.05），并把该 FPR 作为验收量；**不接受"未声明 FPR/功效"的检验**<br>**F5-② 最小样本量与分位数可靠性**：n = 20 的"P95"统计上≈最大值，置信区间极宽 ⇒ **最小 A/A 样本量提高到 ≥ 100 个窗口**，并给出 `P95` 的 **bootstrap 95% 置信区间**（B = 2000 重采样）；判据用**置信上界**而非点估计（`bootstrap_upper95(P95) ≤ σ_floor`）。原第二条判据（"20 次中 \|delta\| ≥ 0.03 的比例 ≤ 10%"）**降级为次要一致性检查**（样本 ≥ 100 且比例 ≤ 5%），**不再作为门**<br>**F5-③ 双窗确认的假阳性率必须实测，不得按独立性估计**：相邻窗口共享参数、策略与噪声自相关 ⇒ 联合 FPR **不是** 0.05²。要求在同一噪声、同一窗口长度下跑 **≥ 50 对 A/A 双窗**，直接测出"双窗同号且两窗 \|delta\| 均 > 阈值"的比例，记为 `aa_two_window_fpr`；**该值 ≤ 1% 才允许打开自动 commit**<br>**F5-④ 噪声降不下来时的回退（原设计缺失）**：若窗口 ×2 后 `bootstrap_upper95(P95)` **仍 > σ_floor** ⇒ 该 **fitness 维度**标记 `unmeasurable`，**从搜索空间移除该维度**（不是继续盲搜，也不是放宽门）；逐维降级顺序 = `meta_channel → learning_progress → coverage_gain → waste_penalty → loop_penalty → net_disp_rate`；若 `net_disp_rate`（轨迹运动学量）也**不可分辨** ⇒ **判 H13 不成立，P2/P3 整体阻塞**并写 `high` 级 finding<br>**顺序强制**：**任何 fitness 变更、任何自动 commit 都不得先于该门通过**。未通过 ⇒ 延长窗口（×2，最多 ×2 次）/ 多窗平均 / 切换到 M4-d3 的轨迹运动学量 |
| **试验流程（改后）** | ```<br>[开始试验] snapshot = ParamAuthority.snapshot(); lease(owner='evo', pid, ticks=window)<br>   ↓ 单/双维变异（≤2 维），写入 active_strategy.json<br>   ↓ 等满窗口（≥600 tick 且 ≥ 60 s 仿真时间），其间自愈回写让行<br>   ↓ 计算 fitness（长窗均值，五项可分辨量；missing_inputs 非空 ⇒ 作废）<br>   ↓ delta = cur - base<br>   ├─ delta > threshold（threshold = max(0.03, 2·P95_noise)）且 A/A 门已通过 ⇒ commit（续租约）；<br>   │     **双窗确认**：再跑一个等长窗口，两窗同号且 \|delta\| 均 > threshold，且 `aa_two_window_fpr ≤ 1%`（实测值）才 commit<br>   └─ 否则 ⇒ ParamAuthority.restore(snapshot)（逐 pid 精确回滚）<br>``` |
| **依赖** | **P0-a4**（租约/快照）、**M4-d3**（观测值落盘）、`P2-c1`（`meta_channel` 输入） |
| **V 指标** | **V9**（`aa_p95_abs_delta` + `bootstrap_upper95`，n ≥ 100 窗 ⇒ `bootstrap_upper95(P95) ≤ 0.03`；`aa_commit_threshold = max(0.03, 2·P95_noise)` 与门**脱钩**；`aa_two_window_fpr ≤ 1%`（≥50 对 A/A 双窗**实测**））<br>**V10**（`delta_exact_zero_rate ≤ 30%`，基线 **60.3%**）<br>**V11**（`commit_rate ∈ [5%, 30%]`，基线 **1.47%**）<br>合并判据：`attribution_ok_rate ≥ 90%`（单维试验占比）、`unmeasurable_dims = ∅` |
| **R 回退** | **R6**（A/A 门不通过却强行启用新 fitness ⇒ 盲搜继续）：**硬门** ⇒ 禁止 fitness 变更与自动 commit，保持 shadow；噪声地板降不下 ⇒ 按 F5-④ 逐维 `unmeasurable` 剔除<br>**R12**（A/A 样本不足 ⇒ P95 不可靠、假阳性率被低估）：n < 100 窗，或按 `0.05²` 估计双窗 FPR ⇒ **不达标不得打开自动 commit**<br>阈值 < 0.03 ⇒ 用 0.03 兜底并记录<br>`commit_rate > 30%` ⇒ 说明门槛过低，按 `max(0.03, k·P95_noise)` 重算阈值并复测 A/A<br>`attribution_ok_rate` 未达标 ⇒ 强制降到 **1 维**<br>`net_disp_rate` 进 `unmeasurable_dims` ⇒ **判 H13 不成立，P2/P3 阻塞**并写 `high` finding |
| **上线策略（shadow）** | 新 fitness **先只落盘不决策**（`evolution_log` 同时写 `sim_fitness` 与 `legacy_fitness`），连续 **≥ 2 个 A/A 窗 + ≥ 1 周影子记录**后，才允许切换为决策量 |
| **假设** | **H13**（长窗 + 轨迹运动学的 fitness 在真实运行中可分辨）—— A/A 门实测是唯一关闭方式 |

---

### M4-d3 — 观测值落盘（`context` 块，**B5 自观测**）

| 字段 | 内容 |
|---|---|
| **ID** | `M4-d3`（原 §7.3；**= P0-a5**） |
| **文件·行号** | ① `fly64/skills/evolution_skill.py:2923-2929`（日志写入）<br>② `fly64/skills/evolution_skill.py:788-829`（`DataCollector.sample`）与 `SensorSample` 字段定义处<br>③ `fly64/fly64/main.py:3034-3068`（遥测发布段，已在发布 `dopamine_gain` / `gain_update_count`，**扩容即可**）<br>④ `fly64/fly64/main.py:2798-2799` / `:3101-3102` / `:3193-3194`（`memory.json` 的 `stuck_score`/`stuck_duration` 发布点，用于 `stuck_duration_true` 的同段发布） |
| **改前** | `evolution_skill.py:2922-2930`：<br>`        try:`<br>`            with open(EVOLUTION_LOG_PATH, "a", encoding="utf-8") as lf:`<br>`                lf.write(json.dumps({"timestamp": t, "iteration": i+1,`<br>`                    "findings": [{"id": f.pattern_id, "severity": f.severity} for f in result.findings],`<br>`                    "fixes": [f.id for f in result.applied_fixes],`<br>`                    "verifications": [{"id": v.fix_id, "passed": v.passed} for v in result.verifications],`<br>`                    "evolution": list(pipe._evolution_results)[-1] if pipe._evolution_results else None,`<br>`                    "errors": result.errors}, ensure_ascii=False) + "\n")`<br>`        except: pass`<br>**现状**：每行只有 `finding` 的 `id` 与 `severity`，**从不记录任何传感器数值** ⇒ 事后无法证明闭环当时看到了什么 |
| **改后** | 在 `:2923-2929` 的日志写入中增加 `context` 块（字段清单**必须与 P1/P2 的新增观测键逐名一致**）：<br>```json<br>{"timestamp": ..., "iteration": ..., "findings": [...], "fixes": [...],<br> "verifications": [...], "evolution": ..., "errors": [...],<br> "context": {<br>   "stuck_duration_true": 0.0, "net_disp_60s": 0.0, "loop_score": 0.0,<br>   "coverage_cells": 0, "revisit_count": 0, "waste_ratio": 0.0, "forward_speed": 0.0,<br>   "ctrl": [0, 0, false], "anomaly_state": "", "escape_behavior": false, "reflex_active": false,<br>   "gain_per_pathway": {"visual": 0, "forward": 0, "turn": 0, "jump": 0, "recurrent": 0},<br>   "gain_update_count": 0, "mb_assoc_count": 0, "life_adapt_lr": 0, "rewrite_delta": 0,<br>   "jump_leg_current": 0.0, "jump_pool_occupancy": 0.0, "fwd_pool_occupancy": 0.0,<br>   "jump_rate_ratio": 0.0, "fwd_homeo_gain": 0.0, "jump_homeo_gain": 0.0,<br>   "cx_effective_steering_gain": 0.0, "cx_loop_break_count": 0,<br>   "cx_loop_break_count_burst_off": 0, "deadlock_burst_count": 0,<br>   "oscillation_window_frames": 0, "oscillation_detected": false,<br>   "terminal_surrender": false, "motion_authority": "lif",<br>   "arbitration": {...}, "param_authority": {...},<br>   "param_write_mismatch": 0, "clamped_keys": [],<br>   "version": {"brain": "2.24.0", "skill": "3.5.1", "canonical": "2.24.0/3.5.1"}<br> }}<br>```<br>② `DataCollector.sample`（`:788-829`）读取新字段（**缺失一律记 `None` 并纳入 `missing_inputs`，不得静默填 0**）<br>③ `main.py:3034-3068` 遥测扩容发布上述新键 |
| **接口签名** | `SensorSample` 新增字段（**与 `context` 键同名同序**）：`stuck_duration_true, net_disp_60s, waste_ratio, jump_leg_current, jump_pool_occupancy, fwd_pool_occupancy, jump_rate_ratio, fwd_homeo_gain, jump_homeo_gain, cx_effective_steering_gain, cx_effective_loop_break_s, cx_loop_break_count, cx_loop_break_count_burst_off, deadlock_burst_count, oscillation_window_frames, oscillation_alt_median_s, oscillation_detected, terminal_surrender, surrender_evidence, arbitration, param_authority, param_write_mismatch, clamped_keys, motion_authority, primitive_granted_count, mb_effective_lr, mb_consolidated_anomaly_count, fwd_homeo_gain, version_triple`<br>`DataCollector.sample(bridge: dict, memory: dict, flow: dict, t: float) -> SensorSample`（**签名不变**） |
| **依赖** | **必须先定名**：P1-b1/b2/b3/b4/b5、P2-c1/c2/c3/c4 的 `flow.json` 新增键（否则字段名漂移） |
| **V 指标** | **V15**（`evolution_log.jsonl` 每行 `context` 非空且**字段数 ≥ 25**；任取一行的 `context.stuck_duration_true` 与同 tick 的 `flow.json` 读数**一致**；事后复盘：给定任一 finding，能用**同一行的 `context`** 复现判定，**不需要外部文件**） |
| **R 回退** | 写入异常 ⇒ **不得阻塞主循环**（`try/except` 包裹，与现有风格一致）；连续 **100 行** `context` 为空 ⇒ 写 `high` 级 finding 并按 M4-d4 告警 |
| **假设** | 无 |

---

### M4-d4 — 闭环存活自检与漏斗告警（**= P0-a6**）

| 字段 | 内容 |
|---|---|
| **ID** | `M4-d4`（原 §7.4；**= P0-a6**） |
| **文件·行号** | ① `fly64/skills/evolution_skill.py:270`（`compute_funnel`）、`~7xx` 的 `fetch_json` / `DASHBOARD_BASE`<br>② `fly64/fly64/main.py:1419-1425`（`EvolutionPipeline(auto_fix=False, window_seconds=120)`）<br>③ **新增** `fly64/skills/evo_funnel_alarm.py`；**新增** `fly64/skills/.evo_loop_heartbeat.json`<br>④ `fly64/artifacts/latest.jsonl`（数据源冗余的回退读取目标） |
| **改前** | `main.py:1419-1425`：<br>`    # EvolutionSkill: on-demand diagnosis when escape states trigger`<br>`    try:`<br>`        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`<br>`        from fly64.skills.evolution_skill import EvolutionPipeline`<br>**现状（t2）**：闭环最后写入 `evolution_log.jsonl` 是 **2026-09-17T10:22:55**，审计时（09-24 12:33）已停摆 **7 天**；无 python 进程、无 `.evo_loop.lock`、无计划任务；唯一数据源 dashboard `127.0.0.1:8765` **不可达**；4.46 天内 iteration 归零重启 **≥9 次**；漏斗 `13728 iter → 44159 findings → 11 fixes → 11 verified → **0 effective**`，`effective=0` **却无任何告警** |
| **改后** | ① **存活心跳**：每轮把 `{"iteration", "ts"}` 写入 `fly64/skills/.evo_loop_heartbeat.json`<br>② **存活自检**：`main.py` 内已有的 `EvolutionPipeline(auto_fix=False, window_seconds=120)` 在读 heartbeat 时若 `now - ts > 120 s` ⇒ 在 `/memory.json["evo_loop_stale"]` 暴露并写 `high` 级 finding<br>③ **漏斗告警**：**新增** `fly64/skills/evo_funnel_alarm.py`，对 `compute_funnel`（`:270`）的四个转化率设置告警：`rate_finding_to_fix == 0`（连续 **3 天**）、`rate_verified_to_effective == 0`（连续 **7 天**）、`iterations` 增量 = 0（**1 小时**）、`errors` 行占比 **> 5%**<br>④ **数据源冗余**：`DASHBOARD_BASE` 单点（`fetch_json`）增加**文件回退** —— dashboard 不可达时直接读 `fly64/artifacts/latest.jsonl` 尾部与 `flow.json` 落盘文件，使"数据源不在 ⇒ 连 finding 都不产生"**不再成立** |
| **接口签名** | **新增** `evo_funnel_alarm.check(funnel: dict, now: float \| None = None) -> list[dict]`（返回告警记录）<br>**新增** `evo_funnel_alarm` 的告警记录字段：`{rule, value, threshold, first_seen_ts, consecutive_s}`<br>新增 `memory.json["evo_loop_stale"]: bool`<br>新增 heartbeat 文件字段：`{"iteration": int, "ts": float}`<br>`DataCollector.fetch_json` 新增文件回退分支（**签名不变**） |
| **依赖** | —（与 P0-a2/a3 并行） |
| **V 指标** | **V16**（① **杀死闭环**：手动停止守护进程，`evo_loop_stale` 必须在 **≤120 s** 内为 true 且产生 `high` finding；② **漏斗**：把 `fixes_recorded` 人为置 0（测试夹具），告警必须触发；③ **数据源冗余**：关闭 dashboard，`run_one_cycle` 必须仍能产出 finding（对照：改前 `Waiting for dashboard...`））<br>并作为 **P0-a7** 的红灯通道（`--history-check` FAIL ⇒ 告警但不阻塞诊断） |
| **R 回退** | 告警通道异常 ⇒ **至少保证 `agent_state` / `memory.json` 可见**（本地降级，不依赖任何外部服务） |
| **假设** | **H8**（auto-fix 熔断（连续 3 次失败 → `auto_fix = False`，`evolution_skill.py:2736-2740`）**未**在本次日志中触发；熔断行**无持久化** ⇒ 无法排除）⇒ 熔断与 `effective=0` 一律进告警通道 |

---

### M4-d5 — 责任链、pattern 集与终止条件

#### M4-d5-a — pattern 条件键零生产者的静默失效

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① `fly64/skills/default_patterns.json:43-51`（`ramp_trap` 的 conditions）<br>② `fly64/skills/evolution_skill.py:863-867`（`position_unchanged_60s` 生产者）、`:1009`（注入点）、`:1066-1087`（`_check`）<br>③ `fly64/skills/evolution_skill.py:489`（**内建** pattern 里同名键的用法，用于确认命名一致性） |
| **改前** | `default_patterns.json:43-51`：<br>`    "conditions": {`<br>`     "ramp_score": {`<br>`      "min": 0.5`<br>`     },`<br>`     "stuck_duration": {`<br>`      "min": 60`<br>`     },`<br>`      "position_unchanged_30s": true`<br>`    },`<br>`evolution_skill.py:1066-1070`：<br>`    def _check(self, pattern: dict, metrics: dict) -> Optional[tuple[dict, float]]:`<br>`        cond = pattern["conditions"]`<br>`        values, total, passed = {}, 0, 0`<br>`        for key, threshold in cond.items():`<br>`            total += 1`<br>`            val = metrics.get(key)`<br>`            if val is None: continue`<br>**实测（本机 grep）**：`position_unchanged_30s` 的**唯一命中是 `default_patterns.json:50`**；**无任何生产者**（生产者只有 `position_unchanged_60s`，`evolution_skill.py:863` 与 `:1009`）<br>**失效机制**：`_check` **先 `total += 1` 再 `if val is None: continue`** ⇒ 缺 1 键即 `passed < total` ⇒ **永久不命中**，唯一痕迹是 4773 次 `low` 级 `telemetry_gap` |
| **改后** | ① 为 `ramp_trap` **补生产者**（**不改回 60 s**，尊重 commit `048fd16` 的收紧意图）：在 `evolution_skill.py` 的 `DataCollector` 新增 `position_unchanged_30s()` 并在 `:1009` 同段注入 `vals["position_unchanged_30s"] = ...`<br>② `_check()`（`:1066-1087`）改为"**缺键 ⇒ 该 pattern 标记 `unreachable` 并告警**"，而不是静默继续：<br>`            val = metrics.get(key)`<br>`            if val is None:`<br>`                unreachable.append(key); continue   # 新增：收集缺键`<br>③ 启动时做 **pattern × 生产者 集合差自检**，任一 `unreachable` pattern 必须进 **`high` 级 finding**（对照现状：**2/16 不可达却无人知**） |
| **接口签名** | 新增 `DataCollector.position_unchanged_30s() -> bool`（**形状对等 `position_unchanged_60s`，窗口 30 s**）<br>新增 `flow.json["pattern_unreachable"]: list[str]`、`flow.json["pattern_missing_keys"]: dict[str, list[str]]` |
| **依赖** | — |
| **V 指标** | **V14**（真引擎回放命中 `high` pattern 数 **≥ 1**，基线 **0 个 high**；0 ⇒ 检查本项的键生产者） |
| **R 回退** | **R9**（红灯：commit `048fd16` 把 `ramp_trap` 改瞎）：pattern 自检必须报出 `unreachable`；未修复前不得进入 P3 |
| **假设** | 无（E-1：`_check` 的 `total`/`passed` 语义与 grep 结果可直接证实） |

#### M4-d5-b — pattern 集的"已放弃终态"覆盖

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/skills/default_patterns.json`（新增 pattern 项）；响应面 `fly64/skills/evolution_skill.py:2570-2580` |
| **改前** | 无 `terminal_surrender_stuck` pattern；`circle_loop` / `micro_loop_weave_signal` 的排除条件把"放弃态"排除在外 |
| **改后** | 新增 `terminal_surrender_stuck`（`severity: high`），其"脑侧响应"是**允许 P1/P2 的自适应面被激活**（例如提高 `escape.jump_leg_weight` 的搜索权重、解锁 CX 环路突破），**不是**写控制量（P2-c2 的验证条件③已覆盖） |
| **接口签名** | 新增 pattern 字段：`id: "terminal_surrender_stuck"`、`severity: "high"`、`conditions: {terminal_surrender: true}` |
| **依赖** | **P2-c2**（`terminal_surrender` 判据）、**M4-d5-a**（键生产者自检） |
| **V 指标** | **V17**、**V14**（真引擎回放 ≥ 1 个 `high`） |
| **R 回退** | 同 P2-c2（连续两次误判 ⇒ 降为 `medium` 并只记录 finding） |

#### M4-d5-c — `has_fix()` 生命周期缺陷

| 字段 | 内容 |
|---|---|
| **文件·行号** | `fly64/skills/evolution_skill.py:1163-1164`（`has_fix`）、`:2644`（消费点）、`:2736-2740`（熔断）；数据 `fly64/skills/fix_catalog.json`（`meta` + 19 条 fix） |
| **改前** | `evolution_skill.py:1163-1164`：<br>`    def has_fix(self, pid: str) -> bool:`<br>`        return any(f.pattern_id == pid and not f.reverted for f in self.fixes)`<br>⇒ **一条无效 fix 永久关闭该 pattern**（**F8：现关闭 11 个 `pattern_id`，不是 13 个**）<br>`evolution_skill.py:2736-2740`：<br>`        if self._consecutive_fix_failures >= 3:`<br>`            result.errors.append(`<br>`                f"⚠ Watchdog: {self._consecutive_fix_failures} consecutive "`<br>`                f"fix failures — auto-fix paused until next restart")`<br>`            self.auto_fix = False  # pause auto-fix to prevent cascading damage`<br>**统计口径（本机独立复算）**：`fix_catalog.json` 共 **19** 条 fix、`meta` 记 `effective_count 0 / ineffective_count 11 / reverted_count 8`；按 `reverted == false` 过滤得 **11 条**，覆盖 **11 个 distinct `pattern_id``**——其中 **10 个**是 `default_patterns.json` 的 pattern，`telemetry_gap` 不是 pattern（属诊断/遥测类 finding）⇒ **两个数都写出**（按"实际被关闭的 pattern"计 **10**；按 `has_fix()` 判据计 **11**），避免口径歧义 |
| **改后** | 把 fix 生命周期改为 `proposed → measuring → effective \| ineffective \| reverted`；<br>**仅 `effective` 长期关闭该 pattern**，`ineffective` **允许重开**（并且重开必须使用**不同的响应形态**，避免重复同一条无效补丁）；<br>熔断与 `effective=0` **一律进告警通道**（M4-d4） |
| **接口签名** | 新增状态枚举：`FixLifecycle = {"proposed","measuring","effective","ineffective","reverted"}`<br>`FixCatalog.has_fix(pid: str) -> bool` 语义收窄为"仅 `effective` 关闭"（**签名不变，语义变更**）<br>新增 `FixCatalog.append_proposal(...)`（与 M4-d1 的 `change_proposals.jsonl` 对接） |
| **依赖** | **M4-d4**（告警通道）、**M4-d1**（提案通道） |
| **V 指标** | **V12**（`effective_count ≥ 1`（首个被证实的改进），基线 **0**）；长期为 0 ⇒ 回到 P1（说明作用面仍未打通） |
| **R 回退** | 熔断与 `effective=0` 必须触发告警；告警通道异常 ⇒ 至少本地可见（同 M4-d4） |
| **假设** | **H8** |

#### M4-d5-d — 本能晋升的边界与责任链

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① `fly64/fly64/instinct_bindings.py:79`（`PROMOTE_MIN_IMPROVED = 2`）、`:87`（`SALIENT_PARAMS`）、`:257-268`（`record_outcome` 的 `return None`）、`:303`（晋升判定）<br>② `fly64/fly64/main.py:1102-1105`（`CLAMP_BOUNDS`）、`:1155`（`apply_strategy_clamps`）、`:1742`（自愈回写）<br>③ `fly64/plugin/coach_outcomes.py:51-66`（`snapshot_outcome`）<br>④ 数据：`fly64/skills/scene_strategy_bindings.json`、`fly64/skills/coach_outcomes.jsonl` |
| **改前** | `instinct_bindings.py:79`：`PROMOTE_MIN_IMPROVED = 2`<br>`instinct_bindings.py:264-268`：<br>`    scene = scene_key(scene_label)`<br>`    params = binding_params(keys)`<br>`    if not scene or not params:`<br>`        return None`<br>`main.py:1102-1105`：<br>`CLAMP_BOUNDS = {`<br>`    "exploration.turn_bias": (0.0, 0.25),`<br>`    "exploration.bold_explore_stuck_s": (1.0, 10.0),`<br>`}`<br>`plugin/coach_outcomes.py:60-62`：<br>`        "scene_id": (flow or {}).get("scene_hash")`<br>`                    or (memory or {}).get("scene_id", ""),`<br>`        "scene_label": (memory or {}).get("scene_label", ""),`<br>**现状（t1 S14）**：线上 `scene_strategy_bindings.json` 有 **2** 个 bucket，各 `improved = 1` < `PROMOTE_MIN_IMPROVED = 2` ⇒ `promoted = false` ⇒ `get_binding()` 恒 `None`；候选 `turn_bias = 0.6 / 0.7` **落在 `CLAMP_BOUNDS["exploration.turn_bias"] = (0.0, 0.25)` 之外** ⇒ 一旦晋升会被自愈**静默改写**（`main.py:1742`）；同时 `coach_outcomes.jsonl` **30/30 行 `scene_label` 为空** ⇒ `record_outcome` 直接 `return None` |
| **改后** | ① **先修边界再谈晋升**：把候选参数限制在**注册区间 ∩ 运行期钳位**之内（`turn_bias ∈ [0, 0.25]`），否则**不得进入绑定库**；<br>② 修复 `scene_label` 生产（`plugin/coach_outcomes.py:51-66`）与防截断侧车（`.hwm` / `.snap` 必须存在）；<br>③ `instinct_bindings.py` 的 docstring 已明确要求"**不得降低门禁来制造晋升**" ⇒ **不降低 `PROMOTE_MIN_IMPROVED`**，只修上游证据链 |
| **接口签名** | `instinct_bindings.record_outcome(...)` **签名不变**，新增前置校验：候选值必须满足 `registry_min ≤ v ≤ registry_max` **且** `clamp_min ≤ v ≤ clamp_max`（否则 `return None` 并记 `reason`）<br>新增 `scene_strategy_bindings.json` 记录的 `reject_reason` 字段 |
| **依赖** | **P0-a8**（注册区间已修）、**M4-d3**（`scene_label` 与 `context` 同源可复盘） |
| **V 指标** | 归入 **V21**（区间不变式）的本地延伸：绑定库中**不得出现** `turn_bias > 0.25` 的候选 |
| **R 回退** | **R3**（本能晋升在边界未修好前被激活，锁死错误本能）：绑定库出现 `turn_bias > 0.25` 的候选 ⇒ 候选必须落在注册区间 ∩ 钳位之内；`promoted` 前**人工复核** |
| **假设** | **H4**（`forced_bold_explore` 可达性取决于"钳位后阈值（≤10）+ 单一异常标签稳定性"，**不判为结构不可达**）—— 本条**不作为**任何回退条件 |

#### M4-d5-e — 版本链自检（红灯）

> **实现规格见 P0-a7**（同一改动：`evolution_skill.py:42` + `evolution_history.json` + 自检通道 + `context.version`）。**P0-a7 == M4-d5-e**。

#### M4-d5-f — 教练直写控制的边界

| 字段 | 内容 |
|---|---|
| **文件·行号** | ① `fly64/fly64/main.py:2330-2348`（教练命令消费者，**直写 `control.x/y/jump`**）<br>② `fly64/fly64/main.py:2279-2323`（对话）、`:2358-2384`（护栏）<br>③ `fly64/fly64/main.py:1873-1876`（`param_history.jsonl` 的字段名 = **`source`**） |
| **改前** | `main.py:1873-1876`：<br>`                                with open(_ph, "a", encoding="utf-8") as _f:`<br>`                                    _f.write(json.dumps({"ts": time.time() * 1000,`<br>`                                        "key": _k, "from": float(_old), "to": float(_new),`<br>`                                        "source": "self-heal"}, ensure_ascii=False) + "\n")`<br>**冲突**：`main.py:2330-2348` 的教练命令消费者**直接写 `control.x/y/jump`**（t1 S32），与本方案"排除硬编码控制补丁"正面冲突 |
| **改后** | **不删除**（人工介入通道必须保留），但：<br>① 明确它**不在自治闭环输出面内**（M4-d1 的 T1/T2 之外）；<br>② 把教练的**非安全类**建议改为经参数授权点写入（P0-a4）；<br>③ 安全类（防坠落/防深坑）保留直写并标注为"人工/安全通道"；<br>④ 所有直写必须在 `param_history.jsonl` 留一条归因记录 —— **F12②：字段名是 `source`，不是 `owner`**<br>**统一口径（R3）**：直写记 `source = "coach-direct"`，安全通道记 `source = "safety-guard"`；**不新增第二套来源字段**（不得同时存在 `owner` 与 `source`）；P0-a4 的 `ParamAuthority` 内部持有 `owner` **仅作租约记账**，落盘时一律映射到 `source` |
| **接口签名** | `param_history.jsonl` 记录字段冻结为 `{ts, key, from, to, source}`（**不新增字段**）<br>`source` 取值集合：`{"self-heal", "coach-direct", "safety-guard", "evo", "operator"}` |
| **依赖** | **P0-a4**（授权点） |
| **V 指标** | 归入 **V3**（`param_authority` 不记录这些写入 ⇒ 可判定） |
| **R 回退** | 无（保留通道是本项的目的；回退方式 = 若发现直写进入了自治输出面 ⇒ 立即从闭环移除并写 `high` finding） |
| **硬约束** | **C7**（教练直写控制通道保留但不进自治输出面） |

---

## 6. §14-D(j) 参数迁移清单（三项，逐项可执行）

> 迁移**必须经 P0-a4 的授权点**写入，不得手工编辑后提交。迁移前先做一次**只读备份**（`active_strategy.json.bak.<ts>`）并把备份路径写进提交信息。
>
> **基线：工作树（HEAD 变体见 §0.4a）** —— 本表三行的「文件·行号」与「改前（逐字）」**全部取自当前工作树**；`active_strategy.json` 与 HEAD **不一致**（HEAD 21 行、扁平点号键、无 `turn_bias` 键）。**HEAD 变体双记录见下表（§6.1）**；若从干净 HEAD 开工，须先做键名归一化（扁平点号键 → 嵌套键）再执行本表。

| # | pid | 文件·行号 | 改前（逐字） | 改后 | 理由 | 依赖 | V | R |
|---|---|---|---|---|---|---|---|---|
| **M1** | `exploration.bold_explore_stuck_s` | `fly64/skills/active_strategy.json:5` | `    "bold_explore_stuck_s": 60.0,` | `    "bold_explore_stuck_s": 10.0,` | 注册区间 `[1.0, 10.0]`；`60.0` **越界**，运行期被 `main.py:1104` 的 `CLAMP_BOUNDS` 静默钳到 10.0 ⇒ 迁移 = **等价于运行期钳位后的行为**，但消除"静默钳位"这一可观测缺陷 | P0-a8、P0-a4 | **V21** | **R11** |
| **M2** | `exploration.gate_jump_threshold` | `fly64/skills/active_strategy.json:8` | `    "gate_jump_threshold": 3.082271242248696,` | `    "gate_jump_threshold": 0.75,` | 新比值语义下 `3.082 > 3.0`（**算术越界**），且 3.082 会要求 `jump_rate > 3.082 × forward_rate` ⇒ 在 0.033/0.043 两处 **严 2.54× / 3.31×**，与"放宽"目的相反且 V6 不可满足。取 `0.75`（而非"等效值 0.93"）因为 0.75 是 §5.3 声明的设计意图（**放宽**）：`0.75 × 0.043 = 0.032 ≤ 0.04` | P0-a8、P0-a4、**P1-b3⑦（RULE-19 契约同批迁移）** | **V6**、**V22** | **R11**、**R13** |
| **M3** | `exploration.turn_bias` | `fly64/skills/active_strategy.json:4` | `    "turn_bias": 0.25,` | **不改值**；只做**边界例外登记与复核** | 注册 `(min 0.0, max 0.25, default 0.25)` ⇒ **`default == max` 边界例外**：严格判据 `min < live < max` 对它**恒不成立**（合法目标值就等于上界）。故严格判据对它**退化为 `min < live ≤ max`**，并由**主判据 `clamp(live) == live` 兜底**。**若不写此例外，断言会把 P1 永久锁死** | P0-a8 | **V21** | **R11** |

### 6.1 三项迁移 + `P1-b4` 的「工作树基线 ↔ HEAD 变体」双记录表（**L-01，t5 新增；与执行计划 §0.5.2 同构**）

> 可复现命令：`git show HEAD:fly64/skills/active_strategy.json`（HEAD 变体）与 `Get-Content fly64/skills/active_strategy.json`（工作树）；`git status --short fly64/skills/active_strategy.json` ⇒ **`M`**。

| 项 | 工作树基线（**操作性**，本文件 §6 的「改前」字符串取此） | HEAD 变体（`cca66648`） | 差异性质 | 处置 |
|---|---|---|---|---|
| `M1` `exploration.bold_explore_stuck_s` | `fly64/skills/active_strategy.json:5`：`    "bold_explore_stuck_s": 60.0,` | `:4`：`    "exploration.bold_explore_stuck_s": 47.55773365137824,` | **键名形态**（嵌套 vs 扁平点号）+ **值不同**（60.0 vs 47.55773365137824） | 两值**都越界**注册 `[1, 10]` ⇒ **静默钳位结论不变**；迁移目标 `10.0` 对两者都成立 |
| `M2` `exploration.gate_jump_threshold` | `:8`：`    "gate_jump_threshold": 3.082271242248696,` | `:7`：`    "exploration.gate_jump_threshold": 3.082271242248696,` | **行号**（:8 vs :7）+ **键名形态**；**值相同** | 算术越界（`3.082 > 3.0`）与"严 2.54×/3.31×"结论对两者都成立 |
| `M3` `exploration.turn_bias` | `:4`：`    "turn_bias": 0.25,` | **该键在 HEAD 不存在**（HEAD 只有别名 `:3 "bold_turn_bias": 0.25` 与扁平点号键） | **键缺失** | HEAD 上 `_expl.get("turn_bias")`**命不中** ⇒ 从干净 HEAD 开工**必须先做键名归一化**（P1-3 / EVO-072 同族工作） |
| `P1-b4` 的两旋钮来源 | `:33-38` 的 `navigation` 段（`steering_gain 0.12` / `loop_break_stuck_s 45.0`） | **HEAD 无 `navigation` 段** | **段缺失** | 同 `M3`：HEAD 上先建立段结构再落写端修复 |
| `active_strategy.json` 整体 | **55 行**、`__generation: 332` | **21 行**、`__generation: 134` | 结构性 | §6 的只读自查基线（"39/39 有活值、越界仅 2 个"）**基于工作树**；若改用干净 HEAD 须重跑该命令 |

**与执行计划的对接**：同一双表见 `docs/execution/fly64-execution-plan.md` **§0.5.2**；其 §2.1 的 `M1/M2/M3` 三行亦已补「工作树基线 + HEAD 变体」行内标注。

**迁移后必须机检的三条（缺一不可）**

1. `clamp(live) == live` 对**全部 39 个注册 pid** 通过（主判据）；
2. `min < live < max` 对 37 个 pid 通过；`exploration.turn_bias` 与 `exploration.bold_explore_stuck_s` 两个 `default == max` 的 pid 走 `min < live ≤ max`；
3. 迁移后 `/memory.json["clamped_keys"]` 在新语义上线后 **6000 tick 内为空**。

**只读自查命令（本机可跑，施工前后各跑一次并留存输出）**

```powershell
cd D:\codes\flygym; $env:PYTHONIOENCODING="utf-8"; python -c "import json,pathlib as P; r=json.loads(P.Path('fly64/skills/brain_tunable_params.json').read_text(encoding='utf-8'))['params']; s=json.loads(P.Path('fly64/skills/active_strategy.json').read_text(encoding='utf-8')); [print(p, s.get(p.split('.')[0],{}).get(p.split('.')[1]), r[p]['min'], r[p]['max'], 'OUT' if not (r[p]['min']<=s.get(p.split('.')[0],{}).get(p.split('.')[1])<=r[p]['max']) else 'ok') for p in r]"
```

> **基线预期输出（本机已核）**：**39/39 有活值**；越界/钉界者仅 **2** 个 —— `exploration.bold_explore_stuck_s`（`OUT`）、`exploration.turn_bias`（钉上界，`ok`）；`exploration.gate_jump_threshold` 在**当前**区间 `[2.0, 20.0]` **内**（`ok`，故今天不被钳位）。

---

## 7. V1–V22 自动化测试落点（文件 / 断言 / 命令）

| ID | 指标 | 测试落点（文件） | 断言（可机检） | 命令 |
|---|---|---|---|---|
| **V1** | `stuck_score` 非常量性 | `fly64/tests/test_memory_units.py`（**新增**） | 合成 6000 tick 序列（含低/中/高 `forward_rate`）后 `stuck_score` 取值集合 `len(set(...)) >= 3`；且 `forward_rate >= rate_threshold` 的 tick 上 `r_score` **不递增** | `cd fly64; python -m pytest tests/test_memory_units.py -q` |
| **V2** | 真实卡死时长与轨迹一致 | 同上 + `fly64/tests/test_stuck_duration_true.py`（**新增**） | 用 `.tmp/fly64_trajectory.json` 的末 545 点（`ctrl = (0,50)×480 + (0,70)×65`）回放，`stuck_duration_true` 与运动学独立重算差 ≤ **5%** | 同上（两文件） |
| **V3** | `param_wiring_ab` 判定覆盖率 | `fly64/tests/test_param_wiring_ab.py`（**新增**） | 注册表 39 个 pid **每个**在 `param_wiring_ab.json` 中有 `verdict`；`wired == false` 的 pid **不在** `BrainMutator.live_params` | `python -m pytest tests/test_param_wiring_ab.py -q` |
| **V4** | `jump_leg_current` 对 `jump_leg_weight` 的响应 | `fly64/tests/test_jump_leg_gain_chain.py`（**新增**） | ① **位精确**：构造 `FlyModel`，设 `_jump_leg_weight = 0.35` 且 `gain("jump") == DEFAULT_GAINS["jump"]`，比较 `v[jump_nodes]` 增量与 `mbon[3] * 0.35`（改动前式）**float32 `np.array_equal`**（**非 `approx`**）；② 比例：0.35→0.80 ⇒ `jump_leg_current` 比值 ≈ **2.29**（`rel=1e-3`）；0.35→0.10 ⇒ ≈ **0.286** | `python -m pytest tests/test_jump_leg_gain_chain.py -q` |
| **V5** | `jump_pool_occupancy` P95 | `fly64/tests/test_jump_homeostat.py`（**新增**） | ① 静默诱导：`_jump_occupancy` 连续 300 tick < 0.02 ⇒ `jump_homeostat()` 单调下降至 **≤ 0.5**；② 不失控：连续 3000 tick `jump_pool_occupancy` **P95 ≤ 0.20**；③ 对偶性：`_jump_occupancy` 升高后 `_jump_homeo_gain` 回升至 **≥ 0.9**（纯函数测试，无 RNG） | `python -m pytest tests/test_jump_homeostat.py -q` |
| **V6** | `ctrl.jump` 占空比 | `fly64/tests/test_jump_gate_ratio.py`（**新增**） | ① 等效性抽样：任取 100 tick 断言 `jump_rate_ratio > r ⇔ jump_rate > r·max(forward_rate, 0.008)` **与实现逐 tick 一致**；② 占空比公式在给定合成序列上 ∈ `[0.001, 0.05]`；③ 门限在序列内**同时出现真与假** | `python -m pytest tests/test_jump_gate_ratio.py -q`；运行时验收另跑 6000 tick（见 §8） |
| **V7** | `cx_effective_steering_gain` 写读一致 | `fly64/tests/test_cx_goal_comp_writes.py`（**新增**） | ① `CentralComplex.steering_gain` 是 **property**：`cx.steering_gain = 0.40` 后 `cx._goal_comp.steering_gain == 0.40`；② `_loop_break_stuck_s` 同法；③ `grep` 断言：`main.py` 中 `_goal_comp.steering_gain` 的写点数 ≥ 1，`model.cx.steering_gain =` 的**影子写点**要么被删除要么被断言覆盖 | `python -m pytest tests/test_cx_goal_comp_writes.py -q` |
| **V8** | `cx_loop_break_count_burst_off` | `fly64/tests/test_cx_loop_break_gate.py`（**新增**） | ① `progress_ineffective=True` + `loop_score > 0.6` + `stuck > _loop_break_stuck_s` + `burst_active=False` ⇒ `_jump_seq` 递增；② `burst_active=True` ⇒ **不**递增；③ `progress_ineffective=False` ⇒ **不**递增（不误伤）；④ 时间戳集合不相交 = 构造两组 tick 断言交集为空 | `python -m pytest tests/test_cx_loop_break_gate.py -q` |
| **V9** | `aa_p95_abs_delta` | `fly64/tests/test_fitness_aa_gate.py`（**新增**） | ① 用固定合成噪声（已知 P95）跑 `fitness_aa_gate`，断言 `bootstrap_upper95(P95)` 落在 A/A 报告内且与解析值差 ≤ 10%；② `n < 100` ⇒ 报 `insufficient_samples`；③ `threshold = max(0.03, 2*P95_noise)` 与门**脱钩**（改 `k` 不改门）；④ `aa_two_window_fpr` 必须由 ≥ 50 对双窗**实测**得出（构造假实现直接返回 `0.05**2` ⇒ 断言失败） | `python -m pytest tests/test_fitness_aa_gate.py -q` |
| **V10** | `delta_exact_zero_rate` | `fly64/tests/test_fitness_window_alignment.py`（**新增**） | 窗口长度是 `max(600 ticks, 60 s)` 的整倍数；`missing_inputs` 非空 ⇒ 该试验 `delta = None`（作废，不计入统计） | `python -m pytest tests/test_fitness_window_alignment.py -q` |
| **V11** | `commit_rate` | 同 V10 文件 | `_subset_k ∈ {1, 2}`（**不再等于 `min(5, ndim)`**）；`threshold` 取自 `max(0.03, k*P95_noise)`；`commit_rate > 30%` ⇒ 重算路径被触发（mock 断言） | 同上 |
| **V12** | `effective_count` | `fly64/tests/test_fix_lifecycle.py`（**新增**） | `has_fix(pid)` 对 `ineffective` 返回 **False**（允许重开）；对 `effective` 返回 **True**；`reverted` 返回 False；生命周期枚举含 `proposed/measuring` | `python -m pytest tests/test_fix_lifecycle.py -q` |
| **V13** | `arbitration.level` | `fly64/tests/test_arbitration_state.py`（**新增**） | **PIN**：① `allowed is None` ⇒ `_vote` 输出与 `_vote_all()[0]`/`IDLE` **逐 tick 相同**（对随机 1000 tick 参数化）；② `ineffective_ticks > dwell_ticks` ⇒ `level` 升 1；③ `level ≤ 2`；④ `level` 达 2 后 `write_count == 0`；⑤ 6000 tick 内升降次数 ≤ 2 | `python -m pytest tests/test_arbitration_state.py -q` |
| **V14** | 真引擎回放命中 `high` pattern 数 | `fly64/tests/test_pattern_reachability.py`（**新增**） | ① 启动自检：每个 pattern 的每个 condition key 都有生产者（集合差为空）；② `ramp_trap` 的 `position_unchanged_30s` **有生产者**；③ 缺键 ⇒ `unreachable` 非空且产生 `high` finding（构造缺键 pattern 断言） | `python -m pytest tests/test_pattern_reachability.py -q` |
| **V15** | `context` 完整度 | `fly64/tests/test_evolution_log_context.py`（**新增**） | ① 对一行 `evolution_log.jsonl` 断言 `len(context) >= 25`；② `context` 键集合 ⊇ `SensorSample` 新字段集合；③ `context.stuck_duration_true` 与同 tick `flow.json["stuck_duration_true"]` 一致；④ 缺失的输入列为 `None`（**不得静默填 0**） | `python -m pytest tests/test_evolution_log_context.py -q` |
| **V16** | 闭环存活 | `fly64/tests/test_evo_liveness.py`（**新增**） | ① 写一个 `ts = now - 121` 的 heartbeat ⇒ `evo_loop_stale is True` 且产生 `high` finding；② `ts = now - 60` ⇒ `False`；③ 漏斗夹具 `fixes_recorded = 0` ⇒ `rate_finding_to_fix == 0` 告警触发；④ dashboard 不可达时 `run_one_cycle` 仍产出 finding（文件回退） | `python -m pytest tests/test_evo_liveness.py -q` |
| **V17** | `terminal_surrender` 判定正确性 | `fly64/tests/test_terminal_surrender.py`（**新增**） | ① 构造终态回放（末 545 点、静止、`loop_score` 高）⇒ `True`；② 正常探索段（`progress_is_ineffective=False`、净位移率 > 1 u/s）⇒ `False`；③ **不得**使用伪影 `stuck_duration`（源码断言：`terminal_surrender` 求值路径中不出现 `self._stuck_duration`） | `python -m pytest tests/test_terminal_surrender.py -q` |
| **V18** | `oscillation_detected` 稳定性 | `fly64/tests/test_oscillation_window.py`（**新增**） | ① 用 `.tmp/fly64_trajectory.json` 的 `ctrl_x` 序列构造 0.37 s 周期 ⇒ `oscillation_window_frames ∈ [30, 300]` 且 ≈ **110**；② 窗口系数 6→3/12 ⇒ 窗口随之改变；③ 门限仍是 `alternations >= 3`（源码/常量断言） | `python -m pytest tests/test_oscillation_window.py -q` |
| **V19** | `--history-check` | 无新测试文件；**CLI 自检** | `SKILL_VERSION(evolution_skill.py:42) == canonical.skill(evolution_history.json:5) == SKILL_VERSION(main.py:50) == "3.5.1"` | `cd fly64; python -m skills.evolution_skill --history-check` ⇒ `exit 0`（**基线已实测 FAIL，exit 1**） |
| **V20** | T3 提案不进入执行 | **新增** `fly64/tests/test_evolution_fix_contract.py` | ① **绕过用例必须被拦下**：`fix_files=[]` 但模板含 `# File: fly64/fly64/main.py` ⇒ 门禁 + 运行时守卫**都不执行**，只写提案；② `fix_template` 中 `control.x/y/jump` 赋值 ⇒ 断言失败；③ `FixExecutor.execute` 是唯一允许写 `.py` 的函数（白名单化 `grep -n "\.write_text(" fly64/skills/*.py`）；④ 门禁与守卫调用**同一** `fix_guard.is_py_patch`（mock 断言调用次数） | `python -m pytest tests/test_evolution_fix_contract.py -q` |
| **V21** | 区间不变式 | **扩展** `fly64/tests/test_tunable_wiring.py`（**已有 `registry ∩ runtime clamp != empty` 断言处**） | ① `clamp(live) == live` 对 **39/39** pid 通过；② `min < live < max` 对 37 个 pid 通过；③ `default == max` 的 2 个 pid（`exploration.turn_bias`、`exploration.bold_explore_stuck_s`）走 `min < live ≤ max`；④ `active_strategy.json` 的 `gate_jump_threshold == 0.75` 且 `bold_explore_stuck_s ∈ [1, 10]` | `cd fly64; python -m pytest tests/test_tunable_wiring.py -q` |
| **V22** | RULE-19 契约迁移完整性 | **改写** `fly64/tests/test_gate_units.py:178-226`（+ `:226` 的 `max <= NYQUIST_HZ` 改 `max <= RATIO_MAX`） | ① `description` 含 `"ratio"` 且点名 `FWD_RATIO_FLOOR`/`model.py:2282`；② `default > 0`、`min > 0`；③ `contract_registry.json:102` 的 `threshold_unit` 含 `"ratio"`；④ `main.py:2892-2894` 默认值与注册表一致；⑤ **新增 PIN**：`allowed is None ⇒ _vote 逐 tick 不变`（F14 的 PIN 落在这里或 `test_arbitration_state.py`，**二者之一且不得缺失**） | `cd fly64; python -m pytest tests/test_gate_units.py -q`（**基线已实测：15 passed**，改后须保持全绿且断言为 ratio 版） |

### 7.1 测试基线（施工前实测，用于判断"转红"）

| 命令 | 基线结果 |
|---|---|
| `cd fly64; python -m pytest tests/test_gate_units.py -q` | **15 passed in 1.82s** |
| `cd fly64; python -m skills.evolution_skill --history-check` | **FAIL**，`exit code 1`，末行 `BRAIN_VERSION(main.py)=2.24.0  SKILL_VERSION=3.5.0  canonical=(2.24.0/3.5.1)  FAIL — SKILL_VERSION 3.5.0 != canonical 3.5.1` |
| `fly64/tests/test_evolution_fix_contract.py` | **不存在**（需新增） |
| `fly64/fly64/instinct_bindings.py` | 存在（408 行）；`fly64/skills/instinct_bindings.py` **不存在** |
| `fly64/tests/` 下 `test_*.py` 数量 | **98** |

> **回归风险提示（P1-b6-1）**：`fly64/tests/test_mushroom_body.py:411` 与 `fly64/tests/test_mbon_saturation.py:229` **PIN 断言 `mb.lr_adapt == 1.0`**（均用 `MushroomBody()` 默认构造）。接线前先跑 `python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q` 记录基线，接线后复跑确认未转红。

---

## 8. R1–R13 阻断逻辑与回退触发点

| ID | 风险 | 触发条件（**可判定**） | 阻断逻辑 | 回退触发点（**自动**，不依赖人工在场） | 关联 ID / V |
|---|---|---|---|---|---|
| **R1** | 增益链扩面导致跳池持续发放（跳变常态，动量浪费/卡死） | `jump_pool_occupancy` **P95 > 0.20** | 不阻断整体，只回退该腿 | ① `escape.jump_intrinsic_max` **减半**；② 减半后仍失败 ⇒ **置 0**（该腿完全停用）并写 `param_wiring_ab.json` 标 `ineffective`；③ 对偶性失败（`_jump_homeo_gain` 不能回升至 ≥ 0.9）⇒ **禁止**该腿进闭环搜索空间（只保留 A/B 手动值）+ `high` finding（`evolution_log`） | P1-b2；V5 |
| **R2** | 门限归一化后门恒真，跳占空比失控 | `ctrl.jump` 占空比 **> 5%**（**burst-off 窗口统计**） | 不阻断整体；连续两次失败则把该 pid 移出自动搜索空间 | ① 门限 **×2**（记录 `jump_gate_autoraise`）；② 连续两次仍失败 ⇒ 回落 **0.75** 并标 `high_risk`（从自动搜索空间剔除） | P1-b3；V6 |
| **R3** | 本能晋升在边界未修好前被激活，锁死错误本能 | 绑定库出现 `turn_bias > 0.25` 的候选 | **阻断晋升**（`promoted` 保持 false） | 候选必须落在**注册区间 ∩ 运行期钳位**之内，否则不得进入绑定库；`promoted` 前**人工复核** | M4-d5-d；V21 |
| **R4** | 升级状态机抖动或产生无界搜索 | `arbitration.level` **升降 > 2 次 / 6000 tick** | 抖动 ⇒ 不阻断，先调参；无界 ⇒ 阻断 | ① `dwell_ticks` **×2**（最多 ×4）；② `level` 上界 **2**；③ 仍失败 ⇒ **停用**（`arbitration_enabled=false`），只保留只读遥测 | P2-c1；V13 |
| **R5** | 检测窗自适应把正常探索判为振荡 | 正常段（`progress_is_ineffective=false`）`oscillation_detected` 占比 **> 5%** | 不阻断；门限**提高**（非降低） | 收紧为 `alternations >= 5`；仍抖动 ⇒ 回到固定 30 帧**并只记录**（该检测不再驱动反射）+ `medium` finding | P2-c3；V18 |
| **R6** | A/A 门不通过却强行启用新 fitness ⇒ 盲搜继续 | `bootstrap_upper95(P95) > 0.03`（n ≥ 100）**或** `aa_two_window_fpr > 1%` | **硬门：阻断**所有 fitness 变更与自动 commit | 保持 **shadow**；噪声地板降不下 ⇒ 按 F5-④ 逐维 `unmeasurable` 剔除（顺序 `meta_channel → learning_progress → coverage_gain → waste_penalty → loop_penalty → net_disp_rate`）；`net_disp_rate` 也不可分辨 ⇒ 判 **H13 不成立**，P2/P3 整体阻塞 + `high` finding | M4-d2；V9/V11 |
| **R7** | 参数写入权争抢导致试验被污染 | 租约冲突 / 第三方写入（同一 `pid` 在任一 tick 有多于一个非过期 owner） | 试验作废（**不阻断**其他条目） | §4.6 授权点：试验期内自愈**让行**；冲突即**作废该试验**；租约机制异常 ⇒ 退化为**只读模式**，置 `flow.json["param_authority_degraded"]=true` | P0-a4；V3 |
| **R8** | **红灯：`--history-check` HEAD FAIL** | **每次启动**（CLI 退出码 ≠ 0） | **闭环不得进入 P3**；但红灯**不阻塞诊断** | 必须修复（P0-a7）；未修复前 P3 整体不可开始；红灯必须进告警通道（M4-d4） | P0-a7；V19 |
| **R9** | **红灯：commit `048fd16` 把 `ramp_trap` 改瞎**（`position_unchanged_30s` 零生产者，落地于闭环死亡后 1 天） | **pattern 自检**报出 `unreachable` | **阻断 P3**（pattern 集不完整则责任链不成立） | ① 补生产者（**不改回 60 s**）；② 缺键 ⇒ 该 pattern 标 `unreachable` **并告警**；③ 启动自检任一 `unreachable` ⇒ `high` finding | M4-d5-a；V14 |
| **R10** | 把检测伪影当故障证据再次误导方案 | **任何引用 E-4 层数值处**（`stuck_score=1.0` / `stuck_duration=1100.72` / `reflex_active=False` / `median_speed=0.0` / `disp_60s=1080.7`） | 文档/代码评审级阻断 | 强制标注「**检测伪影**」+ 假设 **H1**；`terminal_surrender` 等判据**必须**用 P0 重建后的真实量（源码断言：求值路径不出现 `self._stuck_duration`） | P0-a2/a3、P2-c2；V2/V17 |
| **R11** | **红灯（F1）：语义翻转 + 越界值共存 ⇒ 静默收紧** | `active_strategy.json:8 = 3.082…` 在比值语义下 ⇒ 门严 **2.5–3.3×**；**或**任一 pid 的 `clamp(live) != live` | **阻断 P1 上线**（这是 P0-a8 的验收） | §4.7 P0-a8：上界 **4.0** + 显式迁移到 **0.75** + `min<live<max`（含 `default==max` 例外）硬断言；断言失败即**阻断 P1**；迁移项失败 ⇒ 保持语义在 **Hz**（不切比值），把 P1-b3 标为**未上线** | P0-a8、P1-b3；V21/V6 |
| **R12** | **新增（F5）：A/A 样本不足 ⇒ P95 不可靠、假阳性率被低估** | **n < 100** 窗，**或**按 `0.05²` 估计双窗 FPR | **阻断自动 commit** | n ≥ 100 + **bootstrap 置信上界**判据 + **≥50 对 A/A 双窗实测** `aa_two_window_fpr`；不达标**不得**打开自动 commit | M4-d2；V9 |
| **R13** | **F13：§5.3 语义替换未迁移既有单位契约 ⇒ PIN 转红 / CI 阻断** | `pytest fly64/tests/test_gate_units.py` 失败，**或** `contract_registry.json` 与注册表 unit 不一致 | **§5.3 整体不上线** | 同批迁移 `test_gate_units.py` + `contract_registry.json` + `main.py:765-783/2891-2894`；**未迁移则回退 P1-b3 到 Hz 语义** | P1-b3；V22 |

### 8.1 自动回退的"可机检"实现要求（每条回退都必须能在无人时执行）

| 要求 | 实现方式 |
|---|---|
| 回退是**参数级**而非"人工 revert" | 所有回退动作 = 写 `active_strategy.json` 的一个有界值 / 置一个开关 / 恢复一个常量；**不得**要求改 `.py` |
| 回退有**触发点**与**记录点** | 触发点写 `flow.json`（`jump_leg_clamped` / `jump_gate_autoraise` / `param_authority_degraded` / `arbitration_enabled` / `cx_loop_break_enabled`）；记录点写 `param_wiring_ab.json` 与 `evolution_log` finding |
| 回退**不依赖外部服务** | 告警通道异常 ⇒ 至少 `agent_state` / `memory.json` / `flow.json` 本地可见（M4-d4） |
| 回退**幂等** | 同一条件重复触发不改变结果（如 `jump_intrinsic_max` 已为 0 则不再减半） |

---

## 9. 施工顺序与并行度（可直接排期）

| 批次 | 条目 | 可并行 | 出口门（必须全过） |
|---|---|---|---|
| **BT0** | P0-a1（口径冻结，本文件即产物） | — | 本文件 §2/§5/§6 冻结口径获 captain 认可 |
| **BT1** | P0-a2、P0-a4、P0-a6、P0-a7 | ✅ 四条互不依赖 | V1、V2、V3、V16、V19 |
| **BT2** | P0-a3、P0-a5（= M4-d3 的**字段定名 + 落盘框架**） | ✅ | V2、V15（框架） |
| **BT3** | **P0-a8**（区间不变式 + 三项迁移） | ❌ **串行，硬门** | **G1：`clamp(live)==live` 39/39** |
| **BT4** | P1-b1（先跑位精确回归）、P1-b4、P1-b6 | ✅ b4 与 b1 可并行；b6-1/b6-2 可并行 | **G3：b1 位精确回归**、G2（A/B 可用）、G5 |
| **BT5** | P1-b2、P1-b3（含 RULE-19 契约同批迁移）、P1-b5 | ⚠️ b3 依赖 BT3；b5 依赖 b4 | V5、V6、V22、V8 |
| **BT6** | M4-d1、M4-d4、M4-d5-a/c/d/f | ✅（d1 可与 M4 其他并行） | V20、V16、V14、V12、V21 |
| **BT7** | M4-d2（**shadow 先行**，可与 BT1–BT5 全程并行） | ✅ | **G4：A/A 门通过** 才允许 auto commit |
| **BT8** | P2-c1、P2-c2（依赖 c1/d5-a）、P2-c3、P2-c4（依赖 c1） | c3 可与 c1 并行 | V13、V17、V18、V14 |
| **BT9** | M4-d5-e（= P0-a7 已含）、P3（自治运行与泛化） | — | 连续 7×24 无停摆、`effective_count ≥ 1`、同一参数在 ≥3 场景符号一致 |

---

## 10. 施工前检查清单（Pre-flight，逐条勾选）

- [ ] `git rev-parse HEAD` == `cca66648a204043d881da502cf996b15882ad289`（否则本文行号需重核）
- [ ] `cd fly64; python -m pytest tests/test_gate_units.py -q` 记录基线（预期 **15 passed**）
- [ ] `cd fly64; python -m pytest tests/test_mushroom_body.py tests/test_mbon_saturation.py -q` 记录基线（P1-b6-1 回归风险）
- [ ] `cd fly64; python -m skills.evolution_skill --history-check` 记录基线（预期 **FAIL / exit 1**）
- [ ] 跑 §6 的**只读区间自查命令**并留存输出（预期 39/39 有活值，越界/钉界 2 个）
- [ ] 确认 `.tmp/fly64_trajectory.json` 存在（V2/V18 的输入）；若缺失 ⇒ 这两条 V 只能标记 `unmeasurable` 并**不得**用伪影替代
- [ ] 确认本机**无** `memory.json`、**无** `.cache/malecns/manifest.json` ⇒ 所有 `【H5/H6/H11】` 标注保留
- [ ] 备份 `fly64/skills/active_strategy.json`（迁移前）
- [ ] 确认 `fly64/skills/instinct_bindings.py` **不存在**（正确路径 = `fly64/fly64/instinct_bindings.py`）

---

## 11. 覆盖自检表（对照任务书的 7 组来源 + 硬约束 + 证据边界）

| 任务书要求 | 本文件落点 | 覆盖 |
|---|---|---|
| (1) §4 的 P0 各项（a1 设计冻结、a2 单位对齐、伪影链修复、观测字段落盘、a8 区间不变式与迁移、`--history-check`） | §2 P0-a1/a2/a3/a5/a6/a7/a8 | ✅ |
| (2) §5 P1 M1：b1（含 F2 归一化与**位精确回归**）、b2 跳池 homeostat、b3 门口径替换（同 key / 上界 4.0 / `FWD_RATIO_FLOOR=0.008`）、b4 两处死写入、b5 CX 可达化、b6 死代码清理 | §3 P1-b1…b6（b6 拆 5 子项） | ✅ |
| (3) §6 P2 M2：c1 升级状态机（含 §6.1.1 接口契约）、c2 `terminal_surrender`、c3 检测窗自适应、c4 CPG 竞争槽 authority 谓词替换 | §4 P2-c1…c4 | ✅ |
| (4) §7 M4：d1 T1/T2/T3、d2 五段修复 + A/A 零假设门、d3 `context` 落盘、d4 存活自检与漏斗告警、d5 接线/验证/晋升/迁移 | §5 M4-d1…d5（d5 拆 6 子项） | ✅ |
| (5) §14-D(j) 三项参数迁移 | §6 M1/M2/M3 表格（含 `turn_bias` 的 `default==max` 边界例外） | ✅ |
| (6) §10 的 V1–V22 每项测试落点（文件/断言/命令） | §7 全表（含基线结果与回归风险） | ✅ |
| (7) §11 的 R1–R13 每项阻断逻辑与回退触发点 | §8 全表 + §8.1 自动回退实现要求 | ✅ |
| 硬约束：不新增 `control.*` 写入点 | C1 + P1 出口门 G5 + M4-d1 静态断言 | ✅ |
| 硬约束：M1 修复形态只能"让已有信号到达" | C2 + §3.0 声明 + 逐条复核 | ✅ |
| 硬约束：不新增第 5 个 jump 门限（用替换） | C3 + P1-b3（同 key + 机检命令） | ✅ |
| 硬约束：每条带观测指标 + 阈值 + 自动回退 | C4 + 每条 ID 的 `V`/`R` 字段 + §8.1 | ✅ |
| 证据边界：无 `memory.json`/`.cache`、真实连接组不可复现 | §0.3 + 逐条 `假设` 字段 | ✅ |
| 证据边界：H5/H6/H11 标注，不写成断言 | §0.3 表 + P1-b1/b2/b3 的 `假设` 字段 | ✅ |
| （附加）HEAD 核对中的 `file:line` 校正 | §0.4 X1/X2/X3 | ✅ |

---

## 12. 本文件明确**不**做的事（防误读为遗漏）

1. **不重新设计任何机制**（骨架冻结于原方案 §4–§7）：本文只做"文件级落点 + 逐字改前/改后 + 判据 + 回退"的转写。
2. **不替代 M4-d2 的 A/A 实测**：`σ_floor`、`dwell_ticks`、`T_s/L/W/D`、`OSC_CYCLES_PER_WINDOW` 的最终取值一律由实测标定，本文只给初值与标定入口。
3. **不把 demo 探针的数值当真实阈值**（H5）：`0.18127`、`5.517×`、`0.13127`、跳池 20 等只用于**量级/可达性判断**。
4. **不改 `_vote` 优先顺序、不改 `raw_x`/`raw_y`/`jump` 的饱和形式、不降低 `PROMOTE_MIN_IMPROVED`、不删除教练直写通道、不在闭环执行路径执行任何 `.py` 补丁**（原方案 §9.3 七条"不改"）。
5. **不动 `main.py:3064`**（per-tick 解码镜像 `jump_not_active`，F15 校正）与 `fly64/plugin/telemetry.py:94` 的 `2.` Hz 字面量（登记为 `known_divergence`，非行为门）。
