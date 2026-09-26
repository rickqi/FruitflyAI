# SP5-A 收口报告 + A/A 接线闭环 + SP5-B 开工交接文档

> **生成日期**: 2026-09-25
> **集成协调**: closure-integrator / attempt `52b831b5-73d5-4084-9ca4-391c3ef5109c`（task **t4**）
> **团队**: `fly64-aa-wiring` —— 目标：解除 SP5-B 的**机制性**阻塞并收口 SP5-A 残留
> **闭环（不得只写「全部通过」）**: **t1（接线 + 保护标定数据）→ t2（R1 闭合 + R2–R5）→ t3（独立复核 = `needs_revision`：F1 high / F3 medium / F2·F4–F7 low）→ t5（返修 + 两处被证伪表述的更正）→ t6（复验 = `verdict: pass`，七项全闭合、两条主判据无回归）→ t4（本报告）**
> **配置基线**: `git HEAD = ab2761c`（`ab2761cbf358f1d36cc24029ff87dfaabecec84e`）；**工作树脏、不等于 HEAD**（含他人未提交改动），本报告不声称 HEAD 等价
> **本报告的性质**: 汇总 + 独立复算 + 交接。所有数值分三类标注：**【实测-本轮】**（本报告独立跑出）、**【复核-t3/t6】**（引用独立复核报告，非采信实现者自述）、**【待实测/待标定】**（未测项，禁止读成已验证）
> **三句结论（不可合并）**:
> 1. **A/A 接线：机制已通 —— 窗口真的闭、跨度真的 60.0 s、运动学真的齐备；但 G4 尚未通过（真实 n = 0、pairs = 0、`value = None`）。**
> 2. **R1 已闭合（选项 A：拒绝 + `reject_reason`），R2–R5 全部 done；`test_instinct_bindings` 2 failed → 38 passed。**
> 3. **SP5-B 的 `P2-c1` 按规格字面仍不可开工（硬门 `G4` 未过）；可开工的前置动作是「跑 ~100–110 min 常驻循环」，不是再改代码。**

---

## 0. 受检快照与本报告的独立复算

### 0.1 独立复算命令与结果（**【实测-本轮】**，全部 exit 0）

```powershell
cd D:\codes\flygym\fly64 ; $env:TMPDIR="D:/codes/flygym/.tmp/t4_tmp"
python -m pytest tests/test_gate_units.py tests/test_tunable_wiring.py tests/test_param_wiring.py `
  tests/test_evo_liveness.py tests/test_evolution_fix_contract.py tests/test_mushroom_body.py `
  tests/test_m4d2_aa_gate.py tests/test_terminal_surrender.py tests/test_oscillation_window.py `
  tests/test_cx_loop_break.py tests/test_cx_loop_break_gate.py tests/test_aa_window_wiring.py `
  tests/test_aa_report_integrity.py tests/test_jump_leg_gain_chain.py tests/verify_v_indicators.py `
  tests/test_instinct_bindings.py -q
⇒ 292 passed in 104.08s   (exit 0)          # t6 基线 = 292 passed；t3 基线 = 281 passed（t5 新增 11 项）
```

> **TMPDIR 纪律**（沿用 SP5-A §5.4-3）：Windows 默认 Temp 下 pytest atexit 的
> `cleanup_dead_symlinks` 会 `PermissionError` ⇒ **无汇总行、exit 1**。本报告全部 pytest 命令固定
> `TMPDIR=<workspace>/.tmp/t4_tmp` ⇒ 一律 exit 0。**exit 1 不得被读成测试失败。**

### 0.2 磁盘态（**【实测-本轮】**，报告写作前）

| 项 | 值 |
|---|---|
| `fly64/skills/fitness_aa_report.json` | **不存在**（`Test-Path` False） |
| `artifacts/fitness_aa_report.json`（`AA_REPORT_PATH`） | **不存在**（False） |
| `artifacts/aa_wiring/quarantine/fitness_aa_report.synthetic_25windows.json` | 711 B / mtime `2026-09-25 01:29:28` / SHA256 `290702F43D45F342…` |
| `artifacts/aa_wiring/quarantine/fitness_aa_report.t1-midversion_mislabeled.json` | 1356 B / mtime `2026-09-25 11:12:07` / SHA256 **`CEE85DD2DF128DBA493E466C2DC6079D1C2E80E07E4DD1A14C90637D6F98D822`**（与 t3 记录前 16 位一致） |
| `fly64/skills/active_strategy.json` | 1530 B / mtime `2026-09-24 19:30:47` / SHA256 `ED84B2F523DF1E7F…`（**本项目全程未变**） |

### 0.3 真实运行态（**【实测-本轮】**，真实 `EvolutionPipeline(auto_fix=False, window_seconds=120)`）

```
n_windows = 0            has_enough = False        g4_pass = False
wired = False            wired_declared = True     g4_reachable = False
n_windows_span_aligned = 0     n_windows_kinematics_ok = 0
data_source = "no_windows_collected"
aa_two_window_fpr = {value: null, measured: false, n_pairs: 0, min_pairs_required: 50,
                     status: "待实测(insufficient_pairs)"}
auto_commit_enabled = False    shadow = True
blockers[] = [样本不足 n=0 < min_windows_required=100,
              等长窗不足 0/100, 运动学齐备窗不足 0/100,
              data_source=no_windows_collected ≠ runtime_aa_windows,
              aa_two_window_fpr 待实测 (0/50 对双窗),
              observe_aa_window 尚未闭合任何运行态窗（接线未经运行证据，wired=False）,
              auto_commit 保持关闭 (shadow) — 直到上述全部清零]
```

---

## (1) A/A 接线的真实状态

### 1.1 接线前 → 接线后（**【复核-t3】** + 本报告代码定位）

| | 接线前（t1 之前） | 接线后（现在） |
|---|---|---|
| `_aa_window_collector` 全仓命中 | **1 处** = 构造（`evolution_skill.py`） | 构造 + `observe_aa_window` 内 `record` / `record_two_window_pair` + `gate_status`/`report`/`blockers` 读取面 |
| `record()` / `report()` 运行时调用 | **无任何一处** | `run_one_cycle` 内部每个 ≥60 s 无注入区间闭 1 窗 |
| 真实 `n` | **恒 0**（与运行多久无关 ⇒ G4 的 n≥100 **机制上不可达**） | **可增长**；当前仍为 0，原因是「**尚无运行累积**」而非「未被喂数」 |
| 门 | shadow | shadow（**未变**，`auto_commit_enabled` 恒 False） |

### 1.2 接线位置：`EvolutionPipeline.run_one_cycle` **内部**

```
evolution_skill.py:3977   def run_one_cycle(self, bridge=None, memory=None, flow=None)
evolution_skill.py:4068-4084  # ── M4-d2 / G4 (t1)：喂 A/A 噪声基底累加器
    aa_obs = self.brain_mutator.observe_aa_window(sample) if sample else None
        └─ evolution_skill.py:3520  BrainMutator.observe_aa_window(...)
             ├─ :3636  collector.record(observation)              # source=AA_RUNTIME_SOURCE
             └─ :3643  collector.record_two_window_pair(prev, cur) # F5-③ 双窗实测钩子
```

两条真实入口都经过这条链（**【复核-t3】**，本报告核对了调用点行号）：

* **常驻循环**（可靠通道，见 §5）：`evolution_skill.py` `_run_loop` 每轮 `collector.sample(...)` → `run_one_cycle(bridge=…, memory=…, flow=…)`。
* **escape 事件路径**（不可靠通道，见 §5）：`main.py:1494` 构造 `EvolutionPipeline(auto_fix=False, window_seconds=120)`；`main.py:2317-2320` 在 escape 触发且 `tick_start - _evo_last_run > 10` 时调 `_evo_pipe.run_one_cycle()`（无参 ⇒ 内部自行取 `samples[-1]`）。

### 1.3 窗口闭合条件（逐条，**【复核-t3/t6】** + 本报告源码核对）

一个 A/A 窗**只在下列全部成立时**闭合（`evolution_skill.py:3559-3644`）：

1. `sample is not None` 且 `sample.timestamp` 存在；
2. **相邻采样间隔 ≥ `aa_window_s = 60.0 s`**（`span < span_target` ⇒ 记 `skipped_short` 并返回 None）；
3. **区间内无 `active_strategy` 写入**：本进程的 `_inject()` / 回滚置 `_aa_interval_tainted` ⇒ 该区间作废并重新锚定（记 `skipped_tainted`）；
4. **区间内 `active_strategy.json` 的 `__generation` 未变**（t5/F5，外部写入检测；文件消失/键缺失亦判变 ⇒ fail-closed）；
5. 闭合后**仍可能被 G4 守卫排除**：`aligned = (span ≤ 2×60 s)`；`kinematics_ok` = **两次读数都带** `net_disp_60s`。二者**只延后门、不放松门**。

> **关键语义（必须保留）**：运动学缺失的读数**仍然记录**（丢弃会让 n 因与被测门无关的原因恒 0 —— 这正是 t1 之前那类缺陷），但打 `fitness_valid: False`
> ⇒ 出现在 `n_windows_kinematics_ok` / `blockers[]` 里，**不会被静默平均进噪声基底**。

---

## (2) 仓库污染修复的前后证据

### 2.1 缺陷（SP5-A §8.2 发现 1，**【复核-t4】原始归因**）

`AAWindowCollector.report()` 曾**无条件**落盘到 `SKILL_DIR / "fitness_aa_report.json"`，而
`SKILL_DIR = fly64/skills/` ⇒ **每跑一次 `pytest tests/test_m4d2_aa_gate.py` 就用合成 25 窗覆盖真实标定数据**，
且磁盘文件**本身没有**任何「这是演示数据」的标记。

### 2.2 修复内容（**【复核-t3/t6】** + 本报告源码核对）

| 修复 | 落点 | 机检结果 |
|---|---|---|
| 输出路径**可注入** | `report(extra=None, output_path=None)`（`:2623`）；构造器 `report_path=`（`:2292-2304`）；`_resolve_report_path()`（`:2742`） | `output_path` 优先于构造器 `report_path` |
| **默认写 `artifacts/`** | `AA_REPORT_PATH = <repo>/artifacts/fitness_aa_report.json`（`:198`） | **【实测-本轮】** `_resolve_report_path(None).parent.name == "artifacts"` |
| **写 `SKILL_DIR` 被拒** | `_persist_blocked_reason()`（`:2750`）+ `allow_repo_write` 默认 False | **【实测-本轮】** `report(output_path=<SKILL_DIR>/fitness_aa_report.json)` ⇒ `persisted=False`、`file_created=False`、reason = `refusing to write the A/A calibration report under the skill source directory …` |
| **规范产物路径拒收非运行数据** | `report()`（`:2703-2711`）：`n < min_windows` ⇒ 拒写；目标 == `AA_REPORT_PATH` 且 `data_source ≠ runtime_aa_windows` ⇒ 拒写 | **【实测-本轮】** 裸 `record()` 喂 3 窗（min=3，凑满）⇒ `persisted=False`、reason = `non_runtime_source: data_source=unattributed_synthetic_or_replay …`、无文件 |
| **落盘自带格式指纹** | `_schema_version="1.2"` + `format_keys`（`:2658`/`:2724`） | 陈旧/部分写入者**按键可识别**，不靠信任 |
| 测试侧不再碰仓库 | `tests/test_m4d2_aa_gate.py` 4 处 `report()` 显式 `tmp_path`；全仓**唯一**无参 `report()` 在 `test_aa_window_wiring.py:267`，其 collector 的 `report_path` 指向 tmp | **【复核-t3】** 无测试写 `AA_REPORT_PATH` |

### 2.3 活体证据（**【实测-本轮】**，比 t1 的原始观察更强）

**重跑 `pytest tests/test_m4d2_aa_gate.py` → `11 passed in 0.44s`（exit 0），仓库文件一个字节都没动：**

| `fly64/skills/*.json` | 长度 | mtime 跑前 | mtime 跑后 |
|---|---|---|---|
| active_strategy.json | 1530 | 2026-09-24 19:30:47 | **同** |
| brain_tunable_params.json | 15606 | 2026-09-24 19:30:21 | **同** |
| curriculum.json | 2224 | 2026-09-17 20:44:13 | **同** |
| default_patterns.json | 26726 | 2026-09-24 23:39:29 | **同** |
| evolution_history.json | 99869 | 2026-09-23 20:47:53 | **同** |
| fix_catalog.json | 21679 | 2026-09-21 10:14:52 | **同** |
| param_wiring_ab.json | 180 | 2026-09-24 18:20:30 | **同** |
| scene_strategy_bindings.json | 1746 | 2026-09-17 18:35:20 | **同** |

* `fly64/skills/fitness_aa_report.json`：跑前 False → **跑后仍 False**；
* `artifacts/fitness_aa_report.json`：跑前 False → **跑后仍 False**；
* `active_strategy.json` SHA256：`ED84B2F523DF1E7F…` 跑前 = 跑后；
* **并且**：同一批文件在经过完整的 **292 项**回归套件后再次比对，mtime/哈希**逐项不变**。

> 结论：**「测试静默覆写真实标定数据」这条路径已被机制性阻断**，活体证据为「跑测试前后仓库文件 mtime 逐项相同 + 规范路径始终不存在」。

---

## (3) ❗ F1 事件完整记录（**不得隐瞒**）

> 这是本轮**唯一的高severity 缺陷**，也是**最值得复盘**的一条：它不是代码错，而是**「产物存在、但自述为假，且两份交付物断言它不存在」**。

### 3.1 事实（**【复核-t3 发现 / t6 逐项复核】** + 本报告独立读取产物全文）

* **时间线**：t1 中途版本的写入器在 **2026-09-25 11:12:07** 把一份产物写到**新指定的「真实产物路径」** `artifacts/fitness_aa_report.json`（1356 B）。
* **产物自述与内容的矛盾**（本报告读取了全文 47 行）：

| 字段 | 值 | 判定 |
|---|---|---|
| `data_source` | **`"runtime_aa_windows"`** | **假自述**：内容是合成 25 窗的重放 |
| `persisted` | **`true`** | 假自述：它确实被写出了，但不是运行标定 |
| `aa_window_count` | 25 | 合成编造 |
| `min_windows_required` | **20** | 合成用例参数，**不是 G4 的 100** |
| `enough` | **`true`** | 读者会读成「样本已够」 |
| `noise_p95` / `noise_p95_source` | 0.05 / `bootstrap B=200` | 合成用例参数（生产 B=2000） |
| `delta_stats.std` | **0.0** | 所有 delta 完全相同 ⇒ 确定合成 |
| `h13_triggered` / `noise_exceeds_gate` | true / true | 却被放在「真实产物路径」上 |
| `_schema_version` | `"1.1"` | 缺当前 `report()` 的 `span_stats` / `n_windows_kinematics_ok` / `g4_pass` / `blockers` ⇒ t1 中途版本产物 |

* **两份 t1 交付物断言该文件「不存在」**（后被 t3 证伪）：
  `artifacts/aa_wiring/aa-wiring-report.md:81`、`artifacts/aa_wiring/quarantine/README.md:22-23`
  —— 两文件 mtime（11:29:56 / 11:14:47）**都晚于**产物的 11:12:07，即**断言写出来的那一刻产物已经在盘上**。
* **为什么没被发现**：`artifacts/` 被 `.gitignore` 忽略 ⇒ `git status` 看不见；断言写的是「该文件不存在」而不是「该路径未被非运行数据占据」；读者不会去 `Test-Path` 一个「自己刚断言过不存在」的路径。

### 3.2 处置（t5，**【复核-t6】** + 本报告复核哈希）

**选择：移入 quarantine（重命名、内容不改）而非删除。** 理由：它是 F1 缺陷**唯一的在盘证据**；t3 已铉定其 SHA256 前 16 位，保留原文件使该验证可复现；`artifacts/` 被 git 忽略，不污染仓库。

```
artifacts/fitness_aa_report.json
  → artifacts/aa_wiring/quarantine/fitness_aa_report.t1-midversion_mislabeled.json
    尺寸 1356 B、mtime 11:12:07 **均保留**
    SHA256 前 = 后 = CEE85DD2DF128DBA493E466C2DC6079D1C2E80E07E4DD1A14C90637D6F98D822   ⇒ 内容未改
Test-Path artifacts/fitness_aa_report.json = False   （t5 移动后 / 回归套件跑完后 / 结束 三次均 False；本报告 §0.2 复核仍 False）
```

### 3.3 表述更正（逐字，**【复核-t6】** 已核实改正）

* `artifacts/aa_wiring/aa-wiring-report.md:81-86`
  * 改前：「真实产物路径 = `artifacts/fitness_aa_report.json`（`AA_REPORT_PATH`），当前**不存在** ⇒ 真实窗数 `n = 0`（未被任何合成数据冒充）…」
  * 改后：「…**本节 t1 原文在此断言该文件「不存在」——该断言被 t3 复核证伪并已在 t5 更正**（2026-09-25 11:12:07 确有一份 1356 B 的产物，内容为合成 25 窗重放却自述 `runtime_aa_windows`…）。当前状态：该路径**不存在**（t5 复核时移动后确认）…」
* `artifacts/aa_wiring/quarantine/README.md:22-28`：同样改写为「t1 原文断言不存在 → 被 t3 证伪 → t5 更正」+ 处置去向 + 新增「### 现状（t5 处置后）」节。
* 被证伪的表述（「未被任何合成数据冒充」式）**已不再作为事实出现**。

### 3.4 新增的防再犯机制（三管齐下 + 反向守卫；**【复核-t6】** 独立复现 / 本报告部分复现）

| 机制 | 语义 | 独立证据 |
|---|---|---|
| (a) **来源可辨识** | `data_source()` 由 **provenance 计数**派生：只有 `observe_aa_window` 打的 `source=AA_RUNTIME_SOURCE`（`runtime_observe_aa_window`）窗才算 `runtime_aa_windows`；裸 `record()` 喂的 ⇒ `unattributed_synthetic_or_replay`；混合 ⇒ `mixed_runtime_and_unattributed` | **【实测-本轮】** 裸 `record()` 3 窗 ⇒ `unattributed_synthetic_or_replay`；**【复核-t6】** 把 quarantine 那份 25 窗序列重放进裸 `record()` ⇒ 同一结论（`runtime_sourced=0/25`） |
| (b) **样本未满拒写** | `n < min_windows_required` ⇒ `persisted=False` + `insufficient_windows…` | **【复核-t6】** n=25/min=100 拒写、n=99 亦拒写、文件未创建 |
| (c) **规范路径拒收非运行数据** | 目标 == `AA_REPORT_PATH` 且 `data_source ≠ runtime_aa_windows` ⇒ 拒写 | **【实测-本轮】** 合成来源 ⇒ `non_runtime_source…`、无文件；**【复核-t6】** 混合来源 ⇒ 同 |
| (d) **格式指纹** | 落盘带 `_schema_version="1.2"` + `format_keys` | **【实测-本轮】** 见 §2.2 |
| **反向守卫（未被过度阻断）** | runtime 来源 + n ≥ min ⇒ 规范路径**仍可写**（落盘含 `g4_pass`/`blockers`/schema 1.2） | **【复核-t6】** 已实测 |

### 3.5 复盘结论（写给后续批次）

1. **「产物存在但自述为假」是一类独立缺陷**：代码全绿、测试全绿、断言全绿，**磁盘上却有一份自称运行态标定的合成文件**。它只在「跨步骤读产物」时爆炸（收口文档、P2-c1 规划、仪表盘都会读到 `noise_p95=0.05`、`h13_triggered=true`）。
2. **交付物里的「不存在」断言必须当场复检**：`Test-Path` 一行就能拦住本次事件；两份交付物都写了未经复检的否定式断言。
3. **git-忽略目录不是「无证据区」**：`artifacts/` 不在 `git status` 里，所以更需要显式机检（本批次已把 `data_source`/`format_keys`/`schema_version` 做成**文件自述的指纹**）。
4. **读取纪律（已写进 `aa-wiring-report.md:120-122`，必须被消费）**：读任何 A/A 报告文件，**先读 `calibration_usable`、`calibration_note`、`data_source` 三个字段**，再读 `noise_p95`。

---

## (4) G4 结论（**最关键**）

### 4.1 一句话

> **机制已通、待运行累积 —— 不是「机制仍不通」，但也绝对不是「G4 已通过」。**

### 4.2 「机制已通」的证据：**假时钟悬臂**（只用真实 `run_one_cycle`）

**【复核-t3/t6】的原始结论 + 本报告独立复现**。本报告自建悬臂：把 `evolution_skill` 命名空间里的
`time` 绑定替换为假时钟（**只此一处**），循环只用**真实** `EvolutionPipeline.run_one_cycle`，沙箱 `SKILL_DIR`：

| interval(s) | 轮数 | 闭窗数 | 轮/窗 | span(s) min=max | aligned | kin-ok | 全盲 | pairs | `data_source` | `g4_pass` |
|---|---|---|---|---|---|---|---|---|---|---|
| **5** | 400 | **33** | **12.12** | **60.0** | 33/33 | **32/33** | 1（启动首锚点窗） | 32 | `runtime_aa_windows` | **false** |
| 12 | 400 | 79 | 5.06 | 60.0 | 79/79 | 78 | 1 | 78 | `runtime_aa_windows` | false |
| 30 | 400 | 199 | 2.01 | 60.0 | 199/199 | 196 | 3 | 198 | `runtime_aa_windows` | **true（悬臂伪通过，见 §12 O-1）** |
| 31 | 300 | 149 | 2.01 | **62.0** | 149/149 | **0** | **149（全盲）** | 148 | `runtime_aa_windows` | false |
| 61 | 300 | 299 | 1.00 | 61.0 | 299/299 | **0** | **299（全盲）** | 298 | `runtime_aa_windows` | false |

与 t3 悬臂表（interval=5 ⇒ 33 窗/400 轮、跨度 60.0、aligned 33/33、kin-ok 32/33；interval=31/61 ⇒ 全盲）
**逐项一致**；与 t6 §9 的复核值（interval=5 ⇒ n=33、span min=max=mean=60.0、kin-ok 32/33、pairs=32）**逐项一致**。

> **口径脚注（必须随表引用）**：`interval = 5 / 30 / 31 / 61` 四行取自**模块级 `time` 替换**的悬臂（与 t3 明示方法一致，`kin-ok` 数字**只在该层次可比**，见 §12 O-1）；
> `interval = 12` 行的 `kin-ok` 取自「只包 `sample` 时钟」的另一种悬臂（该层次不裁剪位置缓冲 ⇒ `kin-ok` 会被高估）。
> **闭窗数 / 宽度 / aligned / pairs 两层次一致**（只取决于采样时间戳），**`kin-ok` 与 `g4_pass` 不一致**。

> ⇒ **机制层面成立**：窗口真的闭合、跨度恒为 `ceil(60/interval)×interval`、运动学真的齐备（`interval ≤ 30 s`）、
> 双窗配对真的累积。**`interval=5` ⇒ 每 12 轮闭 1 窗、跨度恒 60.0 s、kin-ok 32/33（仅启动首个锚点窗为盲）。**

### 4.3 「G4 尚未通过」的证据：**真实盘上态**（**【实测-本轮】**）

```
真实 n = 0 / 100          pairs = 0 / 50          fpr.value = None（measured=false）
aligned = 0 / 100         kin-ok = 0 / 100        g4_pass = False
data_source = "no_windows_collected"             wired = False（派生态）
```

四个判据**没有一项有实测数据**：`n ≥ 100`（否）、`bootstrap_upper95(P95) ≤ 0.03`（无样本 ⇒ 保守值 0.0/不可用）、
`aa_two_window_fpr ≤ 1%`（**待实测**）、等长窗 ≥100 且运动学齐备 ≥100（否）。

### 4.4 量化条件与时长（给 captain 做排期用）

| 项 | 值 | 依据 |
|---|---|---|
| 可靠命令 | `python fly64/skills/evolution_skill.py --max-iterations 0 --interval 5` | `--max-iterations` **默认 10**（非驻留）⇒ **必须显式传 0**；`--interval` 默认 5；`--window` 默认 120（`evolution_skill.py:4206/4208/4210`）；`resident = args.max_iterations <= 0` |
| 每窗轮数 / 跨度 | **12 轮 / 60.0 s** | 悬臂（§4.2） |
| 单轮 `run_one_cycle` 真实 wall-clock | **0.007 s（t3）/ 0.008 s（本报告 400 轮实测均值）** | 冻结时钟下的纯计算耗时 |
| 每窗真实时间 | **60–65 s**（12×(5 s sleep + ε)） | 代码一致 |
| **100 窗所需连续时间** | **≈100–110 min（保守；约 1.7–1.9 h）** | 12×5 s×100 = 6000 s 下限 |
| 双窗 FPR（≥50 对） | 100 窗 ⇒ 99 对 ⇒ **随之免费满足** | 配对为相邻闭窗 |
| 前置：运动学齐备 | 采样节奏 **≤ 30 s**（`interval=5` ✓；`120/5=24 s` 是更保守的充分条件，**【待标定】**） | 悬臂真边界（§4.2）；`window_seconds=120` 的 `_trim` 内需 ≥5 个位置样本 |
| 会被作废的情形 | 任一 trial 注入/回滚；**外部**写 `active_strategy.json`（`__generation` 变化） | `_aa_interval_tainted` / F5 外部写检测 |
| 跨重启 | **n 归零**（收集器为内存态） | 本批次刻意不引入新的运行时写入点（守 C1/C4 最小面）⇒ 跨重启累计是后续工单 |

> **排期结论**：**开工的前置动作是「运行 ~2 h」，不是「再改代码」。** 这 ~2 h
> 需要基本「无 trial、无注入、无外部策略写入」的连续时间窗。

---

## (5) 可靠通道的修正（**不得沿用 t1 的「两条入口都可靠」**）

| 通道 | 位置 | 可靠性 | 证据 |
|---|---|---|---|
| **常驻循环** | `evolution_skill.py` `_run_loop`（每轮 `sample` + `run_one_cycle`） | ✅ **唯一可靠累积通道** | 悬臂以同节奏驱动真实 `run_one_cycle` ⇒ 稳定闭窗、60.0 s 等长、运动学齐备（§4.2） |
| **escape 事件路径** | `main.py:2317-2320`（`tick_start - _evo_last_run > 10`） | ❌ **不可靠** | 只有 `>10 s` **下限、无上限**；实测 61 s 节奏 ⇒ **399/399 全盲**（t3；本报告 299/299 全盲复现）；跨度 >120 s 还会被判 **unaligned**（`g4_pass` 要求 aligned ≥100）⇒ **即使 n 涨了也不能作为标定来源** |

> **写作纪律**：aa-wiring-report.md:94 的表述已由 t5 更正为「**仅常驻循环是可靠通道**」，
> 并明写 escape 路径的 61 s / 399-399 全盲与 >120 s 判 unaligned（**【复核-t6】§8 已核实**）。

---

## (6) 标定安全阑（防止「估算值/盲窗」冒充实测）

| 阑 | 语义 | 证据 |
|---|---|---|
| **FPR 未满 50 对恒为 None** | `aa_two_window_fpr.value` 在 `n_pairs < 50` 时**恒为 `null`**、`measured=false`、`status=待实测(insufficient_pairs)`；`0.05²=0.0025` 被**明文禁止**（相邻窗共享参数/策略/自相关噪声，联合 FPR ≠ 边缘乘积） | **【实测-本轮】** n_pairs=0/10/49 ⇒ `value=null`；第 50 对 ⇒ `value=0.0, measured=true`。`0.05**2` 全仓仅出现在注释/docstring/note（**:200/:2318/:2460/:2491**），**代码无该计算** |
| **`provisional_value` 只作诊断、不落盘** | 1–49 对时的 `hits/n` 保留在**返回 dict**，`report()` 落盘副本**剥除该键**（t5/F6） | **【复核-t6】** 10 对 ⇒ 返回含 `provisional_value`、落盘文件不含 |
| **判据与文件同源** | `report()` 落盘携带 `g4_pass` / `blockers[]` / `calibration_usable` / `calibration_note`，全部由 `gate_status()` **同一个**来源生成（不会漂移） | **【复核-t6】** 149 窗全盲 ⇒ 文件里 `noise_p95=0.0` **但** `g4_pass=false`、`calibration_usable=false`、`calibration_note` 以「**【不可用】**」开头、`blockers[]` 点名「运动学齐备窗不足 0/100（149 窗缺 `net_disp_60s`；F5-④…）」 |
| **盲窗风险与防护** | 盲窗（缺 `net_disp_60s`）噪声偏低，**会看起来像「零噪声」** ⇒ 必须同时读 `n_windows_kinematics_ok` 与 `blockers[]`；G4 另加两条**只延后**的守卫（aligned ≥100、kin-ok ≥100） | 同上；**【复核-t3】** 201 窗（100 kin + 101 盲）⇒ `g4_pass=false` 且 blockers 点名 101 盲窗 |
| **`wired` 是派生态** | `wired = n_windows_runtime_sourced > 0`；静态声明拆到 `wired_declared`；证据计数在 `wired_evidence` | **【实测-本轮】** 全新 mutator ⇒ `wired=false` + blockers「未经运行证据」；**【复核-t6】** 闭合 2 窗后 `wired=true` |
| **FPR=0.0 的自相矛盾已消除** | `gate_blockers()` 改为 `value is not None and value > 0.01`（不再 `(value or 1.0)`） | **【复核-t6】** FPR=0.0 ⇒ blockers 中**无** `aa_two_window_fpr=` 行；FPR=1.0 ⇒ 诚实输出 `1.0000 > 0.01` |

---

## (7) R1 闭合记录（M4-d5-d：**拒绝 + `reject_reason`**）

### 7.1 captain 裁决（选项 A）与理由

R1（medium）的两种关法：(a) 改为**拒绝 + `reject_reason`**（符合 §M4-d5-d「接口签名」的规格字面）；
(b) 书面确认钳位并把断言改成 0.25。**本轮采纳 (a)**。理由（含实现者登记的规格取舍）：

1. **规格内部存在两句互相拉扯的话**：`改后①` 说候选「限制在注册区间 ∩ 运行期钳位之内」（字面可读成**钳位**）；
   `接口签名` 说「候选值必须满足 `registry_min ≤ v ≤ registry_max` **且** `clamp_min ≤ v ≤ clamp_max`
   （**否则 `return None` 并记 `reason`**）」并**新增 `reject_reason` 字段**。
   **实现者取「接口签名」这一句**，三条理由：①接口签名是**逐字契约**，`reject_reason` 字段**只在「拒绝」语义下才有意义**
   （钳位路径没人需要 reason）；②本项目已把**静默钳位**定性为缺陷（P0-a8 / R11），继续钳位等于在同一类缺陷上再留口；
   ③拒绝路径**完全满足**「候选须落在 registry ∩ clamp 内」的强要求（越界值永不落地为 binding）。
2. **落地差异（如实说明）**：实现选择「**拒绝但不丢证据**」——越界候选不进入晋升路径、
   不写 `promoted_signature`、`get_binding()` 返回 `None`，但把**越界候选值**保留在 `promotion_reject.params`，
   并在 `binding_status` 里可查（`reject_reason` / `rejected` / `rejected_params`）。
   **这是对「否则 return None」的可观测性升级，不是折中**：晋升通道已关闭，只是关闭的原因可见。
   > ⚠️ **一处精确化（本报告新增）**：`record_outcome` 用的是 `binding_params()` **量化后**的候选
   > （`turn_bias` quantum = 0.1）。落在 0.1 网格上的值（如 0.8）是**逐字**保留；
   > **不在网格上的值（如 0.26）保存的是其量化代表 0.3**。因此「逐字越界值」只对网格值成立 ——
   > 判定与留证用的是**同一个**（量化后的）观察值，二者自洽；但**不得**据此声称「原始输入逐字可复原」。见 §12 **O-3**。

### 7.2 落地位置（**【复核-t3/t6】** + 本报告源码核对）

| 位置 | 内容 |
|---|---|
| `fly64/fly64/instinct_bindings.py:100-128` | `_PROMOTION_CLAMP`（runtime clamp 镜像）+ `_REGISTRY_FALLBACK` + `_REGISTRY_CACHE`；注释指明**越界=拒绝非钳位** |
| `:119-120` | 结构化原因常量 `REJECT_OUT_OF_REGISTRY_INTERVAL="out_of_registry_interval"`、`REJECT_VIOLATES_CLAMP_BOUNDS="violates_clamp_bounds"` |
| `:131-157` | `_clamp_bounds` / `_registry_bounds`（真读 `skills/brain_tunable_params.json`，读失败回退静态镜像，进程内缓存） |
| `:172-179` / `:194-212` / `:214-233` | `_out_of_bounds` / `promotion_reject_reason` / `promotion_bounds`（registry ∩ clamp 对外可读，供 V21） |
| `:247-278` | `_clamp_for_promotion` 降级为 **DEPRECATED**「审计用区间投影」helper；**晋升路径不再调用**（t5/F4 改为**非破坏性投影**，不再原地改写入参） |
| `:468-493` | `record_outcome` 前置检查：越界 ⇒ 不钳位、不进晋升路径，写 `bucket["promotion_reject"]={reason, params(观察值/量化后), bounds, rejected, last_rejected_at}`；区间内才落 `params` 并清旧拒绝记录 |
| `:520-526` / `:593-603` | 晋升门（越界 tick 直接关闭晋升路径）；`binding_status` 行新增 `reject_reason`/`rejected`/`rejected_params` + `promotion_bounds`；**被拒候选 `qualifies=False`** |
| 测试侧 | `tests/test_instinct_bindings.py:123`（改为 **R1 正向用例** bias=0.2 仍晋升）、`:360`（**仍以 0.8 为期望**，断言「未被钳位 + `promoted False` + reason」）、`:211-333` 新增 `TestPromotionIntervalRefusal` 6 项、`:321` 反回归「`record_outcome` 内不得再出现 `_clamp_for_promotion(`」；`tests/test_evolution_fix_contract.py:718-760` 合同测试同步改写 |

### 7.3 证据（**【复核-t3/t6】+ 本报告独立探针**）

* **测试**：`test_instinct_bindings` **2 failed（改前）→ 38 passed（改后）**；【实测-本轮】回归集 292 passed / exit 0 已含该文件。
* **本报告独立探针**（真实 API、tmp 存储，不采信自述）：

| 探针 | 结果 |
|---|---|
| `promotion_bounds()` | `{"exploration.turn_bias": {min: 0.0, max: 0.25, registry: [0.0,0.25], clamp: [0.0,0.25]}}` |
| **NEG**（`turn_bias=0.8` ×3 improved） | `promoted=False`、`reason=out_of_registry_interval`、`rejected=3`、**`params` 逐字保留 0.8（未被改写为 0.25）**、`get_binding=None`、`binding_status.rejected=1`、`qualifying=0` |
| **POS**（`turn_bias=0.2` ×2 improved） | `promoted=True`、`binding={'exploration': {'turn_bias': 0.2}}`、无 `promotion_reject`、`rejected=0` |
| **边界（helper 原值层）** | `0.0 / 0.1 / 0.2 / 0.25` 合法 ⇒ `reason=None`；`0.250000001 / 0.26 / 0.3 / 0.8 / -0.01` 拒绝 ⇒ `out_of_registry_interval`；`None` / `"boom"` **不误判为拒绝** |
| `record_outcome` 函数体 | **不含** `_clamp_for_promotion(`（反回归成立） |

> **必须知道的一个刻度细节（本报告新增）**：`record_outcome` 先在 `binding_params()` 里按
> **quantum 0.1 量化**（`turn_bias`），**再**做区间判定 ⇒ 端到端判定用的是签名类的**正则代表值**。
> 实测：`0.25` 量化为 `0.2` ⇒ **合法、晋升（落库 `turn_bias=0.2`）**；`0.26` 量化为 `0.3` ⇒ **拒绝**
> （`promotion_reject.params` 保存的是量化后的 `0.3`，即端到端判定所见的代表值）。
> 这与「闭区间 `[0.0, 0.25]` 合法」**不矛盾**，但**不能**把「0.25 晋升」读成「库里出现 0.25」—— 见 §12 **O-3**。

* **两处旧断言不是「改成 0.25 凑绿」**（**【复核-t3】** 逐字核对）：一处**仍以 0.8 为期望**并改为断言「未被钳位 + `promoted False` + reason」；
  另一处改为**正向**用例（bias=0.2 仍晋升、无 reject）。

### 7.4 R2–R5（low）：**全部 done**

| 项 | 状态 | 改动位置（**【复核-t3】** 逐项所见） |
|---|---|---|
| **R2** | ✅ done | `fly64/fly64/memory.py:1267-1276`：`OSC_TICK_DT` 行**补逐行【待标定】**，并注明「数值是实测来源、常量本身属待标定类」；PIN `tests/test_oscillation_window.py:175`（逐行 tag 缺失即红） |
| **R3** | ✅ done | `fly64/fly64/central_complex.py:334-346`：删「保留为幅度项…未变成死变量」的错误表述，改为明确「**DEAD ASSIGNMENT：本行赋值一次、全模块零读取**」+ 保留原因 + **待清理**；文档同步 `docs/execution/fly64-change-specs.md` P1-b5「改后」行（⚠ R3 实测更正）；PIN `tests/test_cx_loop_break_gate.py:266` |
| **R4** | ✅ done | `fly64/skills/evolution_skill.py:68-142`：降级 `except ImportError` 分支补齐 `PY_PATCH_BLOCK_REASON`（`:74`，与 `fix_guard` 逐字一致）与 `py_patch_gate`（`:100-140`，契约同构、`degraded=True`、**恒不因批准令牌放行 `.py`**）⇒ 修复前该分支一旦生效会在「`.py` 被拦」这一刻抛 `NameError`（不变式仍成立但报告死掉）；PIN `tests/test_evolution_fix_contract.py:217`（隔离命名空间**真跑**该 except 体） |
| **R5** | ✅ done | `tests/test_evolution_capability.py:438`：保留「已退役字符串不得回归」的源码断言，把「核心归因通道仍在」改为断言 `resolve_decision_source` 的**返回通道集合** + 运行循环**必须委托**该函数；新增 `:471` 行为型优先级用例；docstring 记录 t8 归因（HEAD 与工作树逐行相同 ⇒ **预存陈旧断言**，非他人引入） |

> **R1–R5 的本轮终态：`R1 done（选项 A）/ R2 done / R3 done / R4 done / R5 done` —— remaining：0 项。**
> `docs/execution/sp5a-completion-report.md` 的 R1–R5 状态列已由本任务回填（见 §14 变更记录）。

---

## (8) SP5-B 开工前置判定

### 8.1 逐项判定（**明确「可 / 不可 + 依据」**）

| 条目 | 判定 | 依据 |
|---|---|---|
| **`P2-c1`**（升级状态机 + `_vote`→`_vote_all` + `allowed` 契约） | ❌ **不可开工（按规格字面）** | 规格硬门 = **`G4` + `G1` + `G5`**（`docs/execution/fly64-execution-plan.md:381`「串行硬门 `G4` + `G1` + `G5`」、`:316`「SP5-B：**必须 `G4` + `G1` + `G5` 全过**」、`:443` BT8 前置「**G4 已过**」）。`G1`/`G5`/`b1`/`b2` 已具备，**`G4` 未过**（`g4_pass=False`，真实 n=0、pairs=0、`value=None`）⇒ 不得开工。`c1` 的「无效」定义依赖**可分辨成效分**（§4.4 / R6 / R12） |
| **`P2-c4`**（CPG 运动原语竞争槽 · 权威谓词替换） | ❌ **不可开工（传递性）** | 依赖 `P2-c1`（`authority` 谓词由 c1 的仲裁状态机持有）⇒ `c1` 不可开工则 `c4` 不可开工（**【复核-t6】** §11(c)）。**规格预置的诚实出口仍可用**：若「授予 → 执行」只能靠给 `_lif_motion` 追加 OR 支路 ⇒ **按 t5 §F4 直接判定不可行、从 P2 移除 `c4`**，只保留「`primitive_granted_count` 恒 0」的观测 + 一条 `medium` finding，**不做折中实现** |
| **`M4-d5-b` 验收** | ⚠️ 不属本批次 | 实现已交付；`V15`（`context` ≥25 字段且与 `flow.json` 一致）完整闭合归 **BT8** |
| **`F6` 互锁输入可用性** | ✅ 已可用 | `main.py:2193 model.burst_active = _deadlock_burst_remaining > 0`（**读镜像、非控制写**）→ `model.py:2176-2180` → `central_complex.py:352`；t8 行为验证 `burst=True` 时**无论** progress/loop 取值**均不触发**环路突破 |

### 8.2 「可开工的前置动作」= 运行，不是改代码

```
python fly64/skills/evolution_skill.py --max-iterations 0 --interval 5      # 约 100–110 min
⇒ 目标：n ≥ 100、aligned ≥ 100、kin-ok ≥ 100、P95 ≤ 0.03、实测 FPR ≤ 1%
```

### 8.3 G4 豁免登记（**本项目默认不豁免**）

**本项目默认：不豁免。** 若 captain 决定以「机制可达」豁免 `G4`：

* **必须书面登记豁免**（在 team task 或本文件追加一条 `evidence_note`），写明**豁免范围**（仅 `P2-c1`？是否含 `P2-c4`？）、
  **豁免人**、**豁免日期**、**复评触发条件**（例如「真实 n 达到 X 后必须复评」）；
* **必须同步 `docs/execution/sp5a-completion-report.md` §8.1 的 n = 0 事实**（见 §12 O-2：该节当前仍描述 **t1 之前**的状态，需与本文档 §0.3 对齐）；
* 豁免不解除任何其它硬门（`G1`/`G5`/`C1`/`C5`/`V13`），也不得把 `shadow`/`auto_commit_enabled` 打开。

> **当前登记状态：`NOT GRANTED`（未登记豁免）。** 本报告不代为豁免。

---

## (9) 硬约束与无回归证据

| 约束 | 判定 | 机检（**【实测-本轮】**；命令与 t3/t6 同口径） |
|---|---|---|
| **C1**（不新增 `control.*` 写入点） | ✅ **0 命中** | `git diff -U0 -- fly64 ':(exclude)fly64/.pytest-run'` 过滤 `^\+.*control\.[A-Za-z_]+ *=` ⇒ **0 hits**（全仓，不限本批次文件） |
| **C3**（`model.py` 的 `jump_rate >` 恰 1 处） | ✅ **1** | `Select-String fly64/fly64/model.py -Pattern 'jump_rate >'` ⇒ 1 |
| **C5**（`_vote` 严重度返回序未动） | ✅ **逐行未动** | `memory.py:1517-1531`：`FALLEN → MICRO_LOOP → OSCILLATING → WALL_STUCK → STUCK_RAMP → IDLE`（`_vote` 定义在 `:1497`）；`git diff -- memory.py` 仅新增 docstring/调用实参，**严重度返回行 0 改动** |
| **C6**（四处 `clip(·, ±70)` 位精确） | ✅ **4/4 逐字相同** | `model.py:2366/2367/2557/2558`（**注**：SP5-A §9 报告写的 `main.py:2354/…` 系**陈旧定位**，值不变） |
| **keyword-only 两参数保留** | ✅ | `memory.py:1507`（`surrender_evidence`）、`:1508`（`osc_window`）—— **均在 `*` 之后**（见 §11） |
| **`shadow` / `auto_commit_enabled`** | ✅ | 恒 `True` / 恒 `False`，全仓**无置反路径**（**【实测-本轮】** 真实态与三类 fixture 态均 False/True） |
| **回归集** | ✅ **零新增** | **292 passed / exit 0**（t3 基线 281；t5 新增 11 项）；一条未转红 |
| **G3 位精确门** | ✅ 全绿 | `tests/test_jump_leg_gain_chain.py` + `tests/verify_v_indicators.py::TestG3Gate` 含在 292 内 |
| **R1 语义** | ✅ 无回归 | 见 §7.3（NEG/POS/边界/反回归四项独立复现） |
| **接线真实性** | ✅ 无回归 | 见 §4.2（interval=5 与 t3/t6 逐项一致） |

> **未做（如实登记）**：**未重跑全量 ~1,577 项**。t3 已抽样复核 36 项既有失败中的 24 项归因（`model.py` 缺
> `_saturation_recovery_counter`、`default_patterns.json` GBK、`StrategyWriter` 无 `scene_tags`、Windows 无 `fcntl`、
> native bridge 产物缺失、`main.py` 写行 40 > KPI 26），责任代码均**不在**本批次 `changedPaths` 且 mtime 早于本批次；
> 全仓引用 `AAWindowCollector` 的**3 个**测试文件（`test_aa_report_integrity` / `test_aa_window_wiring` / `test_m4d2_aa_gate`）**均绿**。

---

## (10) 阈值标定状态

**A/A 面（本批次新增/相关）—— 全部【待标定】或【待实测】：**

| 阈值 | 当前值 | 位置 | 状态 |
|---|---|---|---|
| `aa_window_s`（A/A 窗长 = trial 窗长） | **60.0 s** | `evolution_skill.py:212` | 口径常量（与 `evaluate()` 的 60 s 对齐）；**窗长本身非待标定项** |
| `min_windows_required`（G4 的 n 门） | **100** | `AAWindowCollector.__init__` 默认 | 规格给定（V9） |
| `AA_TWO_WINDOW_MIN_PAIRS` | **50** | `:202` | 规格给定（F5-③） |
| `bootstrap B` | 2000 | `:2293` | 规格给定 |
| FPR 门 | **≤ 0.01（1%）** | `aa_two_window_fpr()["gate"]` | 规格给定 |
| `sigma_floor`（静态噪声地板） | **0.03** | `gate_status()["sigma_floor"]` | 规格给定（V9） |
| `commit_threshold` k 因子 | **1.5**（规格要求 `k ≥ 2`） | `:2294` / `evolution_skill.py:2182` | **【待标定】** |
| 等长窗守卫 | `span ≤ 2×aa_window_s`（≤120 s），aligned ≥ 100 | `:3613` / `:2528` | **【待标定】**（本批次新增，只延后门） |
| 运动学齐备守卫 | kin-ok ≥ 100；采样节奏真边界 **≤30 s**（`120/5=24 s` 更保守） | `:2529` / `:1140` | **【待标定】** |
| 噪声基底 `noise_p95` | **未测**（n=0 ⇒ bootstrap 返回保守值） | `report()["noise_p95"]` | **【待实测】** |
| `aa_two_window_fpr` | **待实测**（`measured=false`、`value=None`、`n_pairs=0`） | `:2448` | **【待实测】** |
| 检测伪影 (d)：A/A delta 复刻 trial 的非对称 `prev` 约定 | 速率项只在 current 侧 ⇒ delta 带系统性正偏移 | `evolution_skill.py:3328`、`aa-wiring-report.md:99` | **【待标定】**（E-4 层引用一律标注**检测伪影**+**版本边界 H1**） |

**P2-c3 / M4 面（沿用 SP5-A §7，未被本批次改变）：**

| 阈值 | 当前值 | 位置 | 状态 |
|---|---|---|---|
| `T_s` / `L` / `W` / `D` | 120.0 s / 0.6 / 10.0 / 0.5 u/s | `memory.py:2134-2137` | 【待标定】（规格初值） |
| `T_alt` / `W`（自适应窗） | **W 恒 30（地板）**；`T_alt` 只记录 | `memory.py:1266-1275` / `:1437` | **【待标定】** + **R5 闩锁 OFF**（`OSC_ADAPTIVE_ENABLED=False`） |
| `OSC_TICK_DT` | 0.21 s（实测 median） | `memory.py:1272`（R2 后 :1267-1276 块） | 【待标定】（**R2 已补逐行标注**） |
| `OSC_WINDOW_MIN/MAX/CYCLES_PER_WINDOW` | 30 / 300 / 6 | `memory.py:1266-1268` | 【待标定】 |
| `CX_LOOP_BREAKOUT_THRESHOLD` / `_STUCK_S` / `_COOLDOWN_TICKS` | 0.6 / 45.0 s / 1500 ticks | `central_complex.py:50/40/44` | 【待标定】（规格初值） |
| `dwell_ticks`（P2-c1 升级） | 1500 ticks | 规格（H14） | 【待标定】—— **SP5-B 施工项** |

**证据缺口（未关闭）**：

| 缺口 | 状态 | 影响 |
|---|---|---|
| **H5**（`memory.json` 运行态持久化） | 🔶 **仍不存在** | 未关闭（**【实测-本轮】** 复核） |
| **H6**（`.cache/malecns` 连接组缓存） | 🔶 **仍不存在** | 未关闭 |
| **H11**（真实 SM64 连接组验证） | 🔶 **仍不存在** | 未关闭 |
| **H2**（E-4 报告快照不可复现） | ⚠️ 保持 | V14 真机复验前置 |
| **H3**（oscillating 抖动） | ⚠️ 部分关闭 | 抖动 ≤1 翻转/600 tick；「自适应窗带来收益」**不成立** |
| **H13**（长窗 fitness 可分辨） | 🔶 **未决** | A/A 面 n=0 ⇒ 无数据可判 |
| **H1**（版本边界） | ⚠️ 保持 | 一切 E-4 层数值引用须同时标注**检测伪影** + **版本边界 H1** |

> **写作纪律（本节自带）**：以上任何一项**不得**被写成「已验证」。`noise_p95` / FPR / 阈值初值全部是
> **待标定/待实测**；标定归 **M4-d3**。

---

## (11) SP5-B 必须携带的硬约束（否则 SP5-A 成果静默丢失）

> ### ⚠️ `P2-c1` 把 `_vote` 结构替换为 `_vote_all` + `_vote(allowed=...)` 时，**必须保留以下两个 keyword-only 参数**，并在 `_vote_all` 与 `_vote` **两侧继续透传**：
>
> * **`surrender_evidence: bool = False`** —— **P2-c2（SP5-A 交付）的唯一注入通道**
> * **`osc_window: int | None = None`** —— **P2-c3（SP5-A 交付）的唯一窗口通道**

**当前落点（**【实测-本轮】** 逐行核对；**注意行号已随本批次改动前移**）：**

| 项 | 位置 |
|---|---|
| 定义（**均为 `*` 之后 keyword-only**） | `memory.py:1507`（`surrender_evidence`）、`memory.py:1508`（`osc_window`） |
| `_vote` 内消费 | `surrender_evidence` → `:1526-1527`（`_detect_wall_stuck` OR 支路）；`osc_window` → `:1523-1524`（`_detect_oscillating(window=...)`） |
| `update()` 形参 | `:1549`（`surrender_evidence`；**注意**：`update()` **不接受** `osc_window`，它由实例态 `self._osc_window` 提供） |
| `update` 内透传 | `:1570`（`surrender_evidence=`）、`:1571`（`osc_window=self._osc_window`） |
| 实例态来源 | `:1349 self._osc_window: int = OSC_WINDOW_MIN`；`:1442-1446` 跟踪（**`OSC_ADAPTIVE_ENABLED=False` ⇒ 恒 30**） |
| 上游注入 | `memory.py:2286`（`surrender_evidence=self._terminal_surrender`） |

> **判定（C5 PIN）**：`allowed is None` 时 `_vote` 输出必须与基线**逐 tick 相同**；新增两参数为
> **keyword-only 追加**，不得改变原有参数的语义或顺序。
> **风险**：若 `_vote_all` 拆分时漏掉这两项，`_detect_wall_stuck` 的 OR 支路与 P2-c3 的自适应窗会
> **静默回退到默认值**（`surrender_evidence=False` / `osc_window=None`）—— **没有任何测试会红**，能力静默消失。
> 本项已由 t2/t3 两次独立登记，并在 SP5-A §9.3 显著登记。

---

## (12) 集成期观察项（**本报告新增，不改变任何既有 verdict**）

### O-1（low）悬臂的「假时钟」必须声明替换层次；否则悬臂本身能造出 `g4_pass=True`

* **机制**：`DataCollector._trim()`（`evolution_skill.py:1067-1071`）用 `cutoff = time.time() - self.window_seconds` 裁剪位置缓冲，
  **读的是模块级 `time.time()`，不是传给 `sample()` 的 `t` 参数**。
* **后果 A（证据口径）**：若只把 `sample(t=…)` 包一层假时钟（如 `test_aa_window_wiring.py` 的做法），
  位置缓冲**不会被裁剪**（时间戳是未来）⇒ `_compute_kinematics()` 的「≥5 个位置样本」**恒满足**，
  无论节奏多慢都得到 kin-ok 窗。**本报告实测**：同一悬臂在 interval=61、**200 轮**、**3.3 s wall-clock** 内得到
  `n=199`、kin-ok 194、**`g4_pass=True`** —— 与 t3/t6「61 s 全盲」的结论**看似矛盾，实为替换层次不同**。
* **后果 B（口径对齐 + 悬臂也能「通过」G4）**：**只有**替换 `evolution_skill` 命名空间的 `time` 绑定（t3 明示的方法），
  裁剪才会跟随假时钟 ⇒ 才复现出 `interval ≤ 30 s 齐备 / 31 s 起全盲` 的真边界。**本报告按此方法复现，与 t3/t6 逐项一致**（§4.2）。
  **但该层次同样能造出通过**：`interval=30`、400 轮、**≈4 s wall-clock** ⇒ `n=199`、aligned 199、kin-ok 196、
  pairs 198、**`g4_pass=True`**（四项判据全部由「全部 delta ≈ 0 的常数样本 × 假时间」满足）。
  ⇒ **悬臂的 `g4_pass=True` 在任何替换层次下都不是真实标定证据**；`g4_pass` 只能由**真实运行时长**背书。
* **建议（给 captain 决定，非本批次 inScope）**：
  1. 任何悬臂证据**必须写明替换层次**，`kin-ok` 数字只在「模块级时钟替换」下可比；
  2. **不要把任何悬臂的 `g4_pass=True` 当作真实标定** —— 生产路径用真实时间，故**不是生产风险**；
     但「`data_source=runtime_aa_windows` + n≥min ⇒ 可写规范路径」这一守卫**拦不住假时钟**，
     若需更强，得加「采样时钟与真实时钟一致性」检查（新机制 ⇒ 需单独工单）。

### O-2（低）SP5-A 报告 §8.1/§8.2 已被本批次取代，但**不在本次授权编辑范围**（须 captain 处置）

`docs/execution/sp5a-completion-report.md` §8.1/§8.2 描述的是 **t1 之前**的事实，现已过时（逐条给出新旧对照）：

| §8.1/§8.2 原文 | 现行事实（本报告 §0.2 / §0.3 / §1 / §2） |
|---|---|
| 「磁盘上『已发布』的窗数 **25**（`fly64/skills/fitness_aa_report.json`）」 | 该文件**已不存在**，原文件隔离为 `quarantine/fitness_aa_report.synthetic_25windows.json`（711 B） |
| 「**真实累积窗数** 0：`_aa_window_collector` **创建后从未 `record()`、从未 `report()`**」 | 该定性**已被 t1 修复**：接线在 `run_one_cycle` 内部，`record`/`record_two_window_pair` 运行时调用存在；**n 仍为 0 的原因已从「从未被喂数」变为「尚无运行累积」** |
| §8.2 发现 1「报告文件可被测试覆写」 | **已闭合**（§2.3 活体证据：重跑测试后仓库 mtime 逐项未变 + 规范路径拒收非运行数据） |
| §8.2 发现 2「收集器在运行时从未被喂数（G4 的真实阻塞点）」 | **机制阻塞已解除**（§1）；**G4 仍未通过**（§4.3） |
| 建议 ①②③（测试用 tmp / 报告改 `artifacts/` / 加 `synthetic` 标记） | ①②已落地；③以更强的形式落地（`data_source` provenance + `format_keys` + `_schema_version`） |
| 附录 A 复跑注释「`python -m pytest tests/test_m4d2_aa_gate.py -q` # 11 passed，**但会覆写 fitness_aa_report.json**」 | **该副作用已不存在**：**【实测-本轮】** 重跑后 `fly64/skills/*.json` mtime 逐项未变、规范路径仍不存在（§2.3）。该注释行**不在本次授权编辑范围**，请 captain 一并处置 |

> **处置建议（须 captain 决定，本任务未授权改 §8）**：把上表作为 `evidence_note` 附到 SP5-A 报告，
> 或在 SP5-A 报告 §8 顶部加一条「**§8.1/§8.2 为 t1 之前快照；现行事实见 …/sp5a-closure-and-aa-wiring-report.md §0/§1/§4**」的**指针**（不改其结论与证据链）。

### O-3（低）「0.25 合法」与「落库 0.25」不是一回事（量化刻度）

`record_outcome` 先用 `binding_params()` 按 quantum **0.1** 量化 `turn_bias`，再做区间判定 ⇒
端到端判定用**正则代表值**：`0.25 → 0.2`（合法、晋升落库 **0.2**）、`0.26 → 0.3`（拒绝）。
属既有签名定义（`SALIENT_PARAMS`）而非 R1 缺陷；**读 V21 断言时不要写成「库里出现 0.25」**。

### O-4（低）SP5-A §9.3 的行号已陈旧

SP5-A §9.3 写「`memory.py:1503` / `:1504`」为 keyword-only 定义处；
**【实测-本轮】** 现为 **`:1507` / `:1508`**（消费 `:1523-1524` / `:1526-1527`，透传 `:1570`/`:1571`，上游 `:2286`）。
§11 已给出当前落点；SP5-A §9.3 的行号**不改**（不在授权范围），引用时以 §11 为准。

---

## (13) 证据边界（不得越过的线）

1. **工作树 ≠ HEAD**：HEAD = `ab2761c`；工作树含他人未提交改动。本报告一切结论都以**当前工作树**为准，不声称 HEAD 等价。
2. **未重跑全量 ~1,577 项**：回归证据口径 = 16 文件 **292 passed / exit 0**（+ t3 对全量 36 项既有失败的 24 项抽样归因）。t3 明确未逐条复核剩余 12 项。
3. **H5/H6/H11 未关闭**：`memory.json` 与 `.cache` 仍不存在（**【实测-本轮】** 复核）。
4. **E-4 层数值引用**：一律标注「**检测伪影**」+「**版本边界 H1**」（本批次 `evolution_skill.py:3328`、`aa-wiring-report.md:99` 在位）；E-4 图形值（`stuck_score=1.0` / `stuck_duration=1100.72` / `reflex_active=False` / `median_speed=0.0` / `disp_60s=1080.7`）**不得**用作阈值或证据。
5. **未实测项不得写成已验证**：`noise_p95`、`aa_two_window_fpr`（`value=None`）、所有【待标定】阈值、`V14` 真机回放、`V15` `context` 完整性。
6. **悬臂证据的口径**：所有 `kin-ok` / `g4_pass` 数字均来自**假时钟悬臂**，且仅在「模块级 `time` 替换」下可比（§12 O-1）。
7. **未做**：跨重启 n 持久化（后续工单）；`V14` 真机复验（归 BT8）；SP5-A 报告 §8 的正文改写（未授权，见 §12 O-2）。

---

## (14) 本轮变更记录（文件级）

| 文件 | 变更 | 归属 |
|---|---|---|
| `fly64/skills/evolution_skill.py` | A/A 接线（`run_one_cycle` 内部）+ `AAWindowCollector`（可注入路径 / 源码目录拒写 / 样本未满与规范路径拒收非运行数据 / provenance `data_source()` / `gate_blockers()` / `calibration_usable()` / `calibration_note()` / 双窗 FPR 钩子）+ `BrainMutator.observe_aa_window`（provenance 标签 + `__generation` 外部写检测）+ `wired` 派生态；R4 降级导入分支补齐 | t1 / t5 |
| `fly64/fly64/instinct_bindings.py` | R1：拒绝 + `reject_reason`（非钳位）；`_clamp_for_promotion` 降级为**非破坏性**审计投影（t5/F4） | t2 / t5 |
| `fly64/fly64/memory.py` | R2：`OSC_TICK_DT` 行补**逐行【待标定】**（块 `:1267-1276`）；本批次**未再改动**本文件 | t2 |
| `fly64/fly64/central_complex.py` | R3：`_no_goal` 表述更正为 DEAD ASSIGNMENT + 待清理 | t2 |
| `fly64/tests/test_m4d2_aa_gate.py` | 4 处 `report()` 改为显式 `tmp_path` 目标 | t1 |
| `fly64/tests/test_aa_window_wiring.py` | **新增**：接线证明 / taint / 路径注入与拒写 / n 门 / 双窗实测 / shadow 不变 | t1 |
| `fly64/tests/test_aa_report_integrity.py` | **新增（t5）**：F1 来源可辨识与两处拒写、F2 实测 0.0 不自相矛盾、F3 盲窗报告自述不可用、F4 clamp 无副作用、F5 外部 `__generation` 改动作废区间、F6 `provisional_value` 不落盘、F7 `wired` 派生态 | t5 |
| `fly64/tests/test_instinct_bindings.py`、`fly64/tests/test_evolution_fix_contract.py`、`fly64/tests/test_evolution_capability.py`、`fly64/tests/test_cx_loop_break_gate.py`、`fly64/tests/test_oscillation_window.py` | R1 正/反用例与合同测试；R3/R4/R5 的 PIN 用例 | t2 |
| `docs/execution/fly64-change-specs.md` | P1-b5「改后」行插入 ⚠ R3 实测更正 | t2 |
| `artifacts/aa_wiring/*`（git-ignored） | `aa-wiring-report.md`（含 t5 §3 更正、§6 返修表）、`t3-independent-verification.md`、`t6-reverification.md`、`quarantine/`（两份污染产物 + README） | t1/t3/t5/t6 |
| **`docs/execution/sp5a-closure-and-aa-wiring-report.md`** | **本报告（新增）** | **t4** |
| **`docs/execution/sp5a-completion-report.md`** | **R1–R5 状态列回填 + 「3 项转绿」更正（限定为状态相关行）** | **t4** |

---

## (15) 附录：可复跑命令

```powershell
cd D:\codes\flygym
# 0) 真实运行态（n=0 / g4_pass=false / FPR value=null / 规范路径不存在）
python .tmp/t4_probe.py

# 1) A/A 接线悬臂（模块级假时钟；interval=5 ⇒ 33 窗/400 轮、span 60.0、kin-ok 32/33）
python .tmp/t4_arm2.py

# 2) R1 正/负/边界探针（真实 API、tmp 存储）
python .tmp/t4_probe_bound.py

# 3) 仓库污染活体证据（跑前/跑后逐项比对 fly64/skills/*.json 的 mtime）
cd fly64 ; $env:TMPDIR="D:/codes/flygym/.tmp/t4_tmp"
python -m pytest tests/test_m4d2_aa_gate.py -q          # 11 passed, exit 0
Test-Path skills/fitness_aa_report.json                 # False
Test-Path ../artifacts/fitness_aa_report.json           # False

# 4) 无回归集 + G3 + R1（292 passed / exit 0）
python -m pytest tests/test_gate_units.py tests/test_tunable_wiring.py tests/test_param_wiring.py `
  tests/test_evo_liveness.py tests/test_evolution_fix_contract.py tests/test_mushroom_body.py `
  tests/test_m4d2_aa_gate.py tests/test_terminal_surrender.py tests/test_oscillation_window.py `
  tests/test_cx_loop_break.py tests/test_cx_loop_break_gate.py tests/test_aa_window_wiring.py `
  tests/test_aa_report_integrity.py tests/test_jump_leg_gain_chain.py tests/verify_v_indicators.py `
  tests/test_instinct_bindings.py -q

# 5) 硬约束机检
git diff -U0 -- fly64 ':(exclude)fly64/.pytest-run' | Select-String '^\+.*control\.[A-Za-z_]+ *='
Select-String fly64/fly64/model.py -Pattern 'jump_rate >' | Measure-Object
Select-String fly64/fly64/model.py -Pattern 'clip\(.*70'
```

---

*报告生成: closure-integrator · 团队 `fly64-aa-wiring` · task **t4** · attempt `52b831b5-73d5-4084-9ca4-391c3ef5109c`*
*闭环: **t1 → t2 → t3（needs_revision）→ t5（返修）→ t6（verdict=pass）→ t4（本报告）***
*最终状态：**A/A 接线机制已通、G4 待运行累积（≈100–110 min 常驻循环）；R1–R5 全部闭合；SP5-B 的 P2-c1/P2-c4 按规格字面仍不可开工（G4 未过，默认不豁免）。***
