# A3 / P0-3 — 回归基线刷新：NEW 逐条归因 + 门禁转绿

> 任务：`t4 [P0-3]`（team `fly64-p0-recovery`，执行者 test-engineer）
> 依据：`docs/analysis/session_logs_execution_plan_v4.md` P0-3；`docs/analysis/analysis-a3-state.md` §5.1/§5.2/§5.3/§5.5
> 依赖：P0-1（版本四源统一，t1）与 P0-2（两个死参数，t2）已完成 —— 本文件的所有实测都在它们**之后**的工作区上进行。
> 日期：2026-09-23 · 平台：Windows / Python 3.11.9 / pytest 9.0.3

---

## 0. TL;DR

| 问题 | 刷新前 | 刷新后 |
|------|--------|--------|
| `check_regressions.py --strict` | **红**：23 条 NEW + 11 条“基线已通过” | **绿**：0 NEW、0 已通过（见 §7） |
| `known_failures.win32.json` 条目数 | 38（`recorded_at` 2026-09-18，早于 09-21/09-22 的 33 次提交） | **49**（= 本次实跑失败数 50 − 1 条因本次分类而转绿的条目） |
| `cause == "unknown"` | 3 | **0**（2 条转绿自动出局，1 条重新分类为 `test-drift`） |
| 空 `note` | 3 | **0**（49/49 非空） |
| 本轮 P0（t1/t2/t3/t6）是否引入新失败 | — | **没有**：A3 快照的 62 条失败中 12 条已消失、**0 条新出现**；23 条 NEW 全部被证明在 P0 之前就已失败（逐条证据见 §3/§5） |

**一句话结论**：门禁从红转绿，不是因为把失败改小，而是因为（a）38 条旧基线本来就**双向腐化**（漏收 2 条、错收 11 条）、（b）23 条 NEW 逐条查清、23 条里 12 条是**在途未提交代码**、11 条是**P0 之前就已存在的红**；（c）由此得到的 49 条新基线全部带 `cause` + 非空 `note`，`count` 与实跑失败数**相等**。此后任何一次全量运行，只要失败集合与本文件不同，门禁就会指名报出差异——"能否判定"这件事成立了。

---

## 1. 方法与证据链

### 1.1 命令

```powershell
# ① 实跑（全量，253.87 s）
cd fly64
python -m pytest tests -q -rf --junitxml=.tmp/a4_junit.xml

# ② 与旧基线比对（不重跑）
python scripts/check_regressions.py --report <本次失败清单>

# ③ 逐条归因所需的对照树（纯 HEAD、P0 之前、A3 基线当时）
git worktree add --detach .tmp\pristine_head  aeac935        # P0 开始前的 HEAD（captain 已建好）
git worktree add --detach .tmp\pre_ea509a9   5703efa        # ea509a9 之前
git worktree add --detach .tmp\baseline_era  765188d        # 旧基线 recorded_at 前 2 分钟的提交

# ④ 验收
python scripts/check_regressions.py --strict
```

### 1.2 为什么需要三个对照树

`known_failures.win32.json` 是 09-18 记录的，而 09-18 16:03 → 09-22 23:49 之间有 **33 次提交**（A3 §3.1 称之为“新鲜度证据”）。要回答“这条失败是我弄坏的还是本来就红”，只有三种可靠判据：**在纯净 HEAD 上复现**、**在两轮对照提交上复现**、**在该测试的历史上首次变红的提交上复现**。本次三者都用了，结论一致。

### 1.3 本次实跑

```
50 failed, 1167 passed, 37 skipped in 253.87s (0:04:13)      # junit: 1254 testcases
```

失败的文件分布（与 A3 §5.3 的 62 条对照，已消掉 `test_tunable_wiring.py` 8 条与
`test_version_consistency.py` 2 条）：

| 文件 | 条数 | 文件 | 条数 |
|------|------|------|------|
| `test_fix_template_interpreter.py` | 11 | `test_coach_dopamine.py` | 1 |
| `test_what_i_see_protocol.py` | 10 | `test_dan_shaping.py` | 1 |
| `test_mbon_saturation.py` | 8 | `test_fix_executor.py` | 1 |
| `test_invariants.py` | 4 | `test_mbon_skill_capability.py` | 1 |
| `test_evolution_capability.py` | 3 | `test_optic_flow.py` | 1 |
| `test_coach_pipeline.py` | 2 | `test_r31fix3_reward_reshaping.py` | 1 |
| `test_p1_neural_takeover.py` | 2 | `test_retina_calibration.py` | 1 |
| `test_coach_advice_fix.py` | 1 | `test_trajectory_height.py` | 1 |

> 环境噪声（非失败）：全量运行结束时 pytest 的 atexit 清理会因
> `PermissionError: [WinError 5] ...\Temp\pytest-of-*\pytest-current` 抛异常（符号链接清理，
> 不影响汇总行与 junit）。用 `--basetemp`（`check_regressions.py` 已内置）可规避。

---

## 2. 与旧基线（09-18，38 条）的三向比对

| 比对项 | 条数 | 说明 |
|--------|------|------|
| 当前失败 | 50 | §1.3 |
| **NEW（不在旧基线中）** | **23** | 逐条归因见 §3 |
| 旧基线中仍失败 | 27 | 保留原 `cause`/`note` |
| **旧基线中已通过（基线腐化）** | **11** | 见 §4.1 |

A3 §5.2 当时的口径是 62 failed / 34 NEW / 10 条已通过。本次 23 NEW 的来源可以逐项对上：

| A3 的 34 条 NEW | 本次结果 |
|-----------------|----------|
| `test_tunable_wiring.py` 8 条 | **已修绿**（P0-2，t2） |
| `test_version_consistency.py` 2 条 | **已修绿**（P0-1，t1） |
| `test_autonomy_regression.py::TestVersionContract::test_skill_version_mirror` 1 条 | **已修绿**（P0-1，t1） |
| `test_mbon_saturation.py::TestMbonSaturationHomeostasis` 3 条 | **仍红**，但已被证明与本轮 P0 无关（§5 的 bisect：首次变红 = `c17b07a`，09-18 17:25） |
| 其余 20 条 | **仍红**，逐条归因见 §3 |

也就是说：**A3 预测“14 条应由 P0-1/P0-2 消失”中的 11 条确实消失了；另外 3 条（Homeostasis）
不是 P0 造成的，而是 09-18 当天就变红的既有回归** —— 这正是“门禁为红时任何真实回归都会被噪声淹没”
这句话的具体含义，也是本次必须逐条查而不是一句“归因：由 09-21/09-22 变更引起”了事的原因。

### 2.1 附带发现：旧基线**在它自己记录的提交上就已经不完整**

在 `765188d`（旧基线 `recorded_at 2026-09-18T08:05:26Z` 的记录来源提交，本机时间 09-18 16:03）
上运行同一批测试得到 **10 failed**，其中包含
`tests/test_evolution_capability.py::TestWallCornerPattern::test_pattern_in_catalog` 与
`::test_pattern_matches_on_mismatch` —— 但这两条**不在 38 条旧基线里**。

结论：旧基线不只是“过期”，它在 09-18 当天就**漏收了至少 2 条**。这解释了为什么
A3 §5.2 里“NEW = 34”会包含 2 条 09-18 之前就红的用例，也说明“只加不删”的 `--update` 用法
（`--update` 只把 `prev.get("cause","unknown")` 带过去）不足以维持基线完整性，**必须逐条归因**。

---

## 3. NEW 的 23 条逐条归因

三条可靠判据的结论（✔ = 已在该对照上实测复现）：

| # | 测试 | cause | 判据 |
|---|------|-------|------|
| 1–11 | `test_fix_template_interpreter.py`（11 条） | `real-bug` | 在途未跟踪工作：纯净 HEAD 上 `skills` 包**根本无法导入**（collection ERROR） |
| 12 | `test_fix_executor.py::TestParseFixTemplate::test_manual_fallback` | `real-bug` | 同上（同一在途模块的 `advisory` vs `manual` 契约变化） |
| 13 | `test_coach_advice_fix.py::TestBoldTurnBiasChain::test_drive_reaches_turn_pool_current` | `test-drift` | ✔ 765188d 通过 / ✔ 5703efa 失败 / ✔ HEAD 失败 |
| 14 | `test_coach_pipeline.py::TestGLMReceivesSnapshot::test_glm_returns_advice_text` | `live-state` | ✔ 纯净 HEAD（用**已提交**的测试文件）通过；失败只因工作区里 `test_coach_pipeline.py` 有 P0 之前的未提交改动 |
| 15 | `test_dan_shaping.py::TestDanShaping::test_lowered_reward_weakens_mbon_saturation` | `real-bug` | ✔ 765188d 通过 / ✔ 5703efa 失败；bisect 首次变红 = `c17b07a` |
| 16–17 | `test_evolution_capability.py::TestWallCornerPattern`（2 条） | `real-bug` | ✔ 765188d 已失败（旧基线漏收）；根因 = 文件 BOM 让目录加载**必然回退**（§3.2） |
| 18–20 | `test_mbon_saturation.py::TestMbonSaturationHomeostasis`（3 条） | `real-bug` | ✔ 765188d 通过 / ✔ 5703efa 失败；bisect 首次变红 = `c17b07a` |
| 21 | `test_p1_neural_takeover.py::TestNeuralTakeover::test_sigmoid_monotonic_and_bounded` | `test-drift` | ✔ 765188d 通过 / ✔ `61e1e0d` 仍通过 / ✔ 5703efa 失败 |
| 22 | `test_retina_calibration.py::test_emd_pairs_stay_within_eye` | `real-bug` | ✔ 765188d 通过 / ✔ `1badb40` 仍通过 / ✔ `cd9a5a7` 失败 |
| 23 | `test_regression_detector.py::TestBaselineIsWellFormed::test_every_entry_has_a_cause_and_note` | — | 由**本次分类**直接转绿，故从基线中移除（见 §4.2） |

### 3.1 在途未跟踪工作（第 1–12 条）——需要 captain 决策，本次未擅自处理

`git status` 显示：

```
?? fly64/skills/fix_template_interpreter.py
?? fly64/tests/test_fix_template_interpreter.py
?? fly64/tests/test_trigger_conflict.py          # t3 的新测试，已通过，同样未提交
```

关键事实（纯净 HEAD 上的实测）：

```
ERROR collecting tests/test_fix_executor.py
  tests\test_fix_executor.py:26: from skills.fix_executor import (...)
  skills\__init__.py:36: from .fix_template_interpreter import (...)
  E   ModuleNotFoundError: No module named 'skills.fix_template_interpreter'
```

**HEAD 的 `skills/__init__.py:36` 已经 `import` 了这个未跟踪模块**，所以
(a) 没有它，HEAD 连 `skills` 包都导入不了（`test_fix_executor.py` 直接 collection ERROR）；
(b) 有了它，11 条 `test_fix_template_interpreter` + 1 条 `test_fix_executor::test_manual_fallback` 失败。

也就是说：**这不是“多余的脏文件”，而是“已提交代码依赖、但尚未完成且未提交”的半成品**。
删除会立刻打断 HEAD 的导入链；提交则会把 11 条红测试带进主干。

- **本次决定（在 inScope 之外，不动代码）**：把 12 条按 `real-bug` 记入基线，
  note 写明“在途未跟踪 + HEAD 依赖 + 两条出路”，并在交付里请 captain 派单。
- **建议出路**：另开任务把 `fix_template_interpreter.py` 做到 24/24 绿（差异集中在
  `change-to` 动作名 `replace`→`change`、多文件注册丢目标、`add after <anchor>` 解析为 0 条、
  退化模式重写仍为 `manual`、以及 `parse_fix_template` 的 `advisory` vs `manual` 回退），
  然后**连同 `tests/test_fix_template_interpreter.py` 与 `test_trigger_conflict.py` 一起提交**。

### 3.2 主因：`skills/default_patterns.json` 的 **UTF-8 BOM** 让目录加载**注定回退**（第 16–17 条）

先给结论：**这不是“断言过时”，而是一条“磁盘目录永远加载不进来、且回退对调用方不可见”的加载路径缺陷。**

实测（逐字）：

```
$ python -c "import json; json.load(open('fly64/skills/default_patterns.json', encoding='utf-8'))"
json.decoder.JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1

$ python -c "... 首字节 ..."
first bytes: b'\xef\xbb\xbf{'          # ← UTF-8 BOM 在文件开头（HEAD 与工作区都是）
```

`PatternCatalog._load`（`fly64/skills/evolution_skill.py`，class `PatternCatalog`）是这样读的：

```python
def _load(self):
    if self.path and self.path.exists():
        try:
            raw = json.loads(self.path.read_text("utf-8"))        # ← BOM 让这里必然抛异常
            ...
            return
        except Exception as e:
            logging.getLogger("PatternCatalog").warning(
                "Failed to load patterns from %s: %s. Falling back to DEFAULT_PATTERNS.",
                self.path, e)
    self._raw = DEFAULT_PATTERNS; self.patterns = DEFAULT_PATTERNS["patterns"]; ...
```

运行期实测（`stderr` 逐字）：

```
Failed to load patterns from D:\codes\flygym\fly64\skills\default_patterns.json:
Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0). Falling back to DEFAULT_PATTERNS.
```

后果（实测计数）：

| | 条目数 | 含 `wall_corner_command_decoupled` |
|---|---|---|
| 磁盘（utf-8-sig 读） | 16 | **有**（`default_patterns.json:207`） |
| 运行期 `PatternCatalog.patterns`（内嵌回退） | 16 | **无** |

**两处条数相同、集合不同** —— 所以只看“目录里有几条”完全看不出回退发生了；只有比对 id
（或跑 `TestWallCornerPattern`）才会发现。这就是这两条测试红了的直接原因。

额外事实（同一文件上的第二处、独立的损坏，**已在 HEAD 里**）：

```
HEAD 的 blob（git show HEAD:fly64/skills/default_patterns.json）：
  - BOM ✔
  - 第 47 行把 \n 当文本写进了 JSON：  "stuck_duration": {\n      "min": 60\n     },\n     "position_unchanged_30s": true
  - utf-8-sig 解析仍然失败：Expecting property name enclosed in double quotes: line 47 column 24
工作区副本：这一行已被改成真换行（未提交，git diff = 4 insertions / 1 deletion，
  mtime 2026-09-23 00:17:03，作者不在本任务范围内），但 **BOM 仍在**，所以加载照样失败。
```

结论：**修 BOM（读取用 `utf-8-sig`，或去掉 BOM 并修好 JSON）+ 把回退暴露给调用方**，
两点都做才能真正修好；只修第 47 行不解决问题。两条测试在 `765188d` 与纯净 HEAD `aeac935`
上都是红的（已实测），属 P0 之前既有红。

### 3.3 一处与 captain 口述分类的差异（需要 captain 知晓）

captain 交办的分类里建议用 `cause="test-couples-live-state"`。这个标签**不在**
`scripts/check_regressions.py::CAUSES` 的六个取值里，而
`tests/test_regression_detector.py::TestBaselineIsWellFormed::test_causes_are_from_the_known_vocabulary`
会断言 `cause ⊆ CAUSES` —— 直接用会让**门禁重新变红**。

本次按语义等价使用既有标签 **`live-state`**（其定义就是“断言运行中系统的实时遥测状态，而非代码”），
并在该条 note 中写明 captain 要求的标签名与 P1-4 归属。

---

## 4. 基线腐化的清理

### 4.1 11 条“基线已通过”确认转绿（因此必须移出基线）

| 测试 | 旧 cause | 说明 |
|------|----------|------|
| `test_bridge.py`（6 条） | environment | 旧 note 说“Windows 无 `time.clock_gettime_ns`”，现已通过（窗口内加了回退） |
| `test_retina.py`（2 条） | environment | 同上（seqlock/clean-break） |
| `test_invariants.py::test_torn_frames_return_last_good_frame` | environment | 同上 |
| `test_autonomy_regression.py::TestVersionContract::test_brain_version_in_skills_md_round_table` | **unknown** | 由 P0-1 修绿（`skills.md` 圆桌表已写 2.23.12） |
| `test_regression_detector.py::TestDetectorDetects::test_reports_clean_against_its_own_baseline` | **unknown** | 它把 `.tmp/current_failures.txt`（09-18 捕获的 37 条）喂给 `check_regressions.py --report` 并断言 `NEW = 0`；**基线一换，这份捕获就跟着失效**（那 37 条里 bridge / retina / 版本圆桌等已转绿，会被算成 NEW）→ 见 §7.1 与 §7.5 |

### 4.2 3 条 `cause == "unknown"` 的归零

| 条目 | 处理 | 依据 |
|------|------|------|
| `test_autonomy_regression.py::...::test_brain_version_in_skills_md_round_table` | **转绿出局** | P0-1 已统一版本四源（实测通过） |
| `test_regression_detector.py::TestDetectorDetects::test_reports_clean_against_its_own_baseline` | **出局**（且它把“配套 fixture 必须一起刷新”这条隐性契约暴露出来） | 见 §4.1 最后一行、§7.1、§7.5：它本身不红也不绿，取决于 `.tmp/current_failures.txt` 与新基线是否同步 |
| `test_coach_pipeline.py::TestStrategyExecution::test_fallen_recovery_has_params` | **重新分类为 `test-drift`** | `climb_period`/`persist_seconds` 已被认定为“零消费者死旋钮”并从 coach SPEC 移除（`plugin/llm_consult.py` SECTION_SPECS 注释；`tests/test_coach_contract.py:122` 钉住同一事实），断言仍要求实时 advice 携带它们 ⇒ 只能靠“重新广告一个空操作”才能通过；且它读的是常驻服务的 `coach_advice.json`（A3 §5.4 / P1-4） |

### 4.3 新基线的构成（49 条）

| cause | 条数 | 含义 |
|-------|------|------|
| `real-bug` | 21 | 12 条在途未提交（`fix_template_interpreter` 族）+ 9 条已确认的真实行为/契约红（MBON 族 4 + `wall_corner` 2 + `retina::_emd_pairs` 1 + `optic_flow` 性能 1 + 启动器锁 1） |
| `aspirational` | 16 | 断言的功能全仓零实现（`ENHANCED_PROMPT_TEMPLATE` 10 条 + `_saturation_recovery_*` 5 条 + `test_no_visual_motor_shortcut`） |
| `test-drift` | 6 | 断言钉住源码文本形状/过时契约（含 §4.2 重新分类的 1 条） |
| `environment` | 5 | gbk 解码 3 条 + `.cache/malecns/weights.npz` + 原生桥二进制 |
| `live-state` | 1 | 读常驻服务实时产物 |
| `unknown` | **0** | — |

> `environment` 由 14 条降为 5 条，纯粹是因为其中 9 条（`clock_gettime_ns` 族）已在窗口内
> 变成“能通过”，属于 §4.1 的基线腐化清理，不是本次把失败重新贴标签。

---

## 5. 逐条对照矩阵：A3 快照（62）→ 本次（50）

| 分组 | 条数 | 证据 |
|------|------|------|
| A3 的 62 条中**已消失** | 12 | 8 `test_tunable_wiring` + 2 `test_version_consistency` + `test_autonomy_regression::test_skill_version_mirror` + `test_autonomy_regression::...round_table`；全部由 P0-1（t1）/P0-2（t2）修绿 |
| A3 的 62 条中**仍失败** | 50 | 与本次实跑集合**逐 id 相等** |
| 本次相对 A3 **新出现** | **0** | 即本轮 P0（含 t3 闸门、t6 版本收口）未引入任何新失败 |

**结论（门禁的核心诉求）**：P0-1/P0-2/P0-4/P0-1b 的改动**没有**引入新的红；
A3 快照里那些“由 09-21/09-22 变更引起”的红，证据指向的引入点都在 **P0 之前**：

| 失败族 | 首次变红的提交（bisect/对照实测） | 提交信息 |
|--------|-----------------------------------|----------|
| `test_dan_shaping` + `TestMbonSaturationHomeostasis`（4 条） | **`c17b07a`**（09-18 17:25；`7d878b1` 绿、`c17b07a` 红） | `t27 P0: MBON steep homeostatic scaling - hard-saturation channels recover (Brain v2.23.9)` |
| `test_retina_calibration::test_emd_pairs_stay_within_eye` | `1badb40`（09-20 18:21）绿 → **`cd9a5a7`（09-21 13:36）红** | 窗口内 retina 属性改名/移除，测试未同步 |
| `test_p1_neural_takeover::test_sigmoid_monotonic_and_bounded` + `test_coach_advice_fix::...test_drive_reaches_turn_pool_current` | `61e1e0d`（09-21 22:23）绿 → **`1badb40`…`5703efa` 之间的某次提交红**（已收窄到 09-21 22:23 → 09-22 17:21） | 两处都是“断言钉住源码文本形状”，被 `model.py` 的换行/系数绑定重构打破 |

> 这三族都不属于本轮 P0 的范围，但**都是真实的行为/契约红**，建议按 §8 派单；不要在
> “门禁绿了”之后把它们遗忘。

---

## 6. 归因报告的一处诚实声明：本次没有 Linux 运行

`tests/known_failures.linux.json` 本次**只做静态核对**（inScope 原文：仅静态核对）。核对结果：

- 条目数 24、`count` 一致、id 形式合法；
- **2 条 `cause="unknown"` 且 `note` 为空**（与 win32 完全同源）：
  `test_autonomy_regression.py::TestVersionContract::test_brain_version_in_skills_md_round_table`、
  `test_coach_pipeline.py::TestStrategyExecution::test_fallen_recovery_has_params`。

处理：**只补分类、不动条目集合**（

- 前者：测试只解析 `skills/skills.md` 与 `main.BRAIN_VERSION`，**与平台无关**，P0-1 之后在
  win32 上已通过，因此 Linux 上也应通过 —— 但“删除条目”等价于断言一次 Linux 实跑，
  本次没有 Linux 运行，故**保留条目**，note 里写明“下一次 Linux 刷新应删除它”；
- 后者：与 win32 同一归因（死旋钮 + 读常驻服务状态），补 `test-drift` + note。

结果：两个基线的 `unknown` 均为 0、空 note 均为 0。**剩余风险**：Linux 基线里那条版本圆桌测试
大概率已经转绿，Linux 上的 `--strict` 仍会报“1 条基线已通过”，需要一次 Linux 实跑
（`python scripts/check_regressions.py --update` + 归因）收口 —— 列 P2 后续项。

---

## 7. 验收证据

### 7.1 `python scripts/check_regressions.py --strict`（两次实测，过程可见）

门禁不是“一次就绿”的，第一次实测**指出了我漏掉的一处耦合**，这也正是它该做的事：

**第一次（新基线 49 条已写入，但配套 fixture `.tmp/current_failures.txt` 还是 09-18 的 37 条）**

```
==============================================================================
REGRESSION CHECK  (baseline win32, 49 entries)
==============================================================================
  failing now      : 50
  still failing    : 49 (known)
  NEW failures     : 1
  baseline entries that now PASS : 0

  !!! NEW FAILURES (a regression, or an unclassified pre-existing one):
      tests/test_regression_detector.py::TestDetectorDetects::test_reports_clean_against_its_own_baseline
  pytest: 50 failed, 1167 passed, 37 skipped in 254.25s
```

归因：该用例把 `.tmp/current_failures.txt` 喂给 `check_regressions.py --report` 并断言 `NEW = 0`；
旧捕获里的 bridge / retina / 版本圆桌等 id 已经转绿，于是被算成 NEW。**不是代码回归，是刷新基线
必须同步刷新的配套 fixture** —— 处理见 §7.5（第一次实测把这条“隐性契约”暴露出来，属于本任务的价值之一）。

**第二次（fixture 同步后）**：`EXIT=0`，**0 NEW、0 “基线已通过”**，逐字输出见 §7.3。

### 7.2 基线静态检查（`stdout`）

```
fresh run failures: 50 (junit), expected baseline: 49 (minus 1 now-passing entries)
== known_failures.win32.json (win32)
   recorded_at      : 2026-09-22T16:29:18.328718+00:00
   count field      : 49  entries: 49  MATCH
   malformed ids    : none
   cause=unknown    : 0
   cause not in CAUSES vocabulary: none
   empty notes      : 0
   ids == real run  : True (baseline 49, run 49, only-in-baseline=none, only-in-run=none)
== known_failures.linux.json (linux)
   count field      : 24  entries: 24  MATCH
   cause=unknown    : 0
   cause not in CAUSES vocabulary: none
   empty notes      : 0
OK: both baselines are well-formed; win32 entry set == real run failure set
```

### 7.3 验收命令逐字输出（最终，基线冻结后）

```
$ python scripts/check_regressions.py --strict
running pytest ...
==============================================================================
REGRESSION CHECK  (baseline win32, 49 entries)
==============================================================================
  failing now      : 49
  still failing    : 49 (known)
  NEW failures     : 0
  baseline entries that now PASS : 0
  known failures by cause: aspirational=16, environment=5, live-state=1, real-bug=21, test-drift=6

  pytest: 49 failed, 1168 passed, 37 skipped in 265.86s (0:04:25)

  OK: no regressions, baseline is current
$ echo $LASTEXITCODE
0
```

对照：刷新前同一命令为红（23 NEW + 11 “基线已通过”）；A3 §5.2 的口径（62 failed / 34 NEW / 10 已通过）
对应的是更早的工作区状态。

### 7.4 未改动的东西（避免误读）

- `scripts/check_regressions.py`：**未改**（门禁逻辑与 `--strict` 语义保持原样）。
- `tests/*.py`：**未改**（含 `test_regression_detector.py`、`test_coach_pipeline.py` 里那份
  P0 之前就在工作区的未提交改动 —— 归因里点名，但不动它）。
- 除 `known_failures.win32.json`（重写）与 `known_failures.linux.json`（2 条补分类）之外，
  **仓库内只有本文件是新增/修改**。

### 7.4.1 会话期间主工作区仍有第三方写入（协调事实，需 captain 知晓）

归因过程中记录到一处**不是本任务所为**的主工作区改动：

| 文件 | 变化 | mtime | 影响 |
|------|------|-------|------|
| `fly64/skills/default_patterns.json` | HEAD 里第 47 行的文本化 `\n` 被改成真换行（`git diff` = 4 insertions / 1 deletion），BOM 未动 | 2026-09-23 **00:17:03** | **不改变**这两条 `wall_corner` 测试的红/绿（BOM 仍在，加载依旧失败）；本任务未触碰该文件 |

也就是说：多 agent 并行时主工作区在本会话期间**仍在被改动**（当时四个成员均显示 idle，
改动来源不在本任务的命令里，我不做归属猜测，只如实记录 mtime 与内容）。
对本任务结论的影响有限，原因有二：

1. 该改动落在 §3.2 的次要缺陷上，**主因（BOM）依旧存在**，两条测试的判定不变（§7.3 最终实测仍为 49 条红）；
2. 本任务两次全量实跑（第一次 junit 写于 00:13:22，最终 `--strict` 写于 00:33:51）得到的失败 id 集合
   **完全一致**（50 → 本次分类修绿 1 条后 49），没有出现“跑一半集合变了”的情况；
3. 该改动写入时刻（00:17:03）之后，本任务**没有**再动过任何源码文件（只重写基线 JSON 与新增本文件）。

### 7.5 一处必须一起刷新的配套 fixture（本次已刷新，理由如下）

`fly64/.tmp/current_failures.txt`（**gitignored**，`fixture` 性质）是
`TestDetectorDetects::test_reports_clean_against_its_own_baseline` 解析的输入：该用例把这份
“上一次捕获的失败清单”喂给 `check_regressions.py --report`，断言 `NEW failures : 0`。

- 它是 09-18 16:01 捕获的 37 条；其中的 bridge / retina / 版本圆桌等 id **已经转绿**，
  因此在新基线（49 条）下会被算成 NEW；
- 第一次 `--strict` 实测正是因此报出 1 条 NEW
  （`test_reports_clean_against_its_own_baseline` 自身失败）——即“基线刷新后必须同步刷新这份清单”；
- 处理：按新基线逐 id 重写为 49 行 `FAILED <id>`（与 `pytest -q -rf` 的输出同形）。
  纯 id 行即可 —— `parse_report` 只取 `FAILED <id>` 的首段。
- 由于该文件被 `.gitignore` 覆盖，**新克隆的机器上它不存在**，该用例会走 `pytest.skip` 分支，
  因此不影响门禁在别的机器上的语义（skip 不是失败）。

这一条已写进 §8 的 P3（基线刷新应把配套 fixture 一起刷新，或让该用例自己捕获一次运行）。

---

## 8. 未解决 / 后续项（按建议优先级）

| 优先级 | 事项 | 依据 |
|--------|------|------|
| **P1** | 在途未跟踪工作收口：`skill/fix_template_interpreter.py` 做到 24/24 绿，然后提交它与 `tests/test_fix_template_interpreter.py`、`tests/test_trigger_conflict.py`（HEAD 的 `skills/__init__.py:36` 已依赖前者） | §3.1 |
| **P1** | 修 `skills/default_patterns.json` 的 BOM（读取改 `utf-8-sig`，或去 BOM 并修好 HEAD 里第 47 行的文本化 `\n`），并让 `PatternCatalog._load` 的回退对调用方可见（现在只有一条 `logging.warning`） | §3.2 |
| **P1** | 测试隔离（A3 §5.4 / P1-4）：重定向 `plugin/.consult_request.json`、`.consult_response.json`、`skills/active_strategy.json`；`test_t3_handshake.py` 加 `__main__` 守卫；决定 `test_coach_pipeline.py` 里 `glm-5v-turbo` 那份未提交改动是否提交 | §3/§4.1 |
| **P2** | 修 6 条真实行为红：MBON 陡峭稳态缩放族（4，起于 `c17b07a`）、`SphericalRetina._emd_pairs`（起于 09-21 窗口）、`optic_flow` 性能（23.6 ms vs 7 ms 预算）、启动器锁 | §5 |
| **P2** | 修 2 条“钉住源码文本形状”的断言（`model.py:1434-1435` 换行、`model.py:1648-1651` 系数绑定行）—— 改成 AST/行为断言而不是行正则 | §5 |
| **P2** | Linux 基线刷新：在 Linux 上跑 `check_regressions.py --update` + 归因，删掉已转绿的版本圆桌条目 | §6 |
| **P3** | 基线的 `--update` 语义加固：`--update` 只继承旧 `cause`、把新条目写成 `unknown` 且 `note` 为空，**本次的红就是这么产生的**；建议让它拒绝写出未分类条目（或直接引用本文件的归因方式）。另建议让 `test_reports_clean_against_its_own_baseline` 自己捕获一次运行，而不是依赖 gitignored 的 `.tmp/current_failures.txt`（§7.5） | §2.1、§4.2、§7.5 |

---

## 9. 复现清单

```powershell
cd fly64
# 刷新前的实跑（本次基线的数据来源）：50 failed / 1167 passed / 37 skipped
python -m pytest tests -q -rf --junitxml=.tmp/a4_junit.xml
# 刷新后再跑同一条命令应为 49 failed / 1168 passed / 37 skipped —— 少掉的那一条是
#   TestBaselineIsWellFormed::test_every_entry_has_a_cause_and_note，它自己就是被“3 条 unknown”
#   弄红的，分类后转绿（本次未重复该命令；等价证据见 §7.3：--strict 内部跑的就是同一个全量套件，
#   汇总行 49 failed / 1168 passed / 37 skipped）

python scripts/check_regressions.py --strict                     # 期望 rc=0
python -c "import json;d=json.load(open('tests/known_failures.win32.json',encoding='utf-8'));print(d['count'])"
git -C .. diff --stat -- fly64/tests/known_failures.win32.json
```

对照树：`.tmp/pristine_head`（aeac935，captain 建立，保留）；本任务为归因临时建立的
`.tmp/pre_ea509a9`（5703efa）与 `.tmp/baseline_era`（765188d，bisect 用）**已在收尾时用
`git worktree remove --force` 清理**，需要复核时可按下文重建：

```powershell
git worktree add --detach .tmp/pre_ea509a9  5703efa
git worktree add --detach .tmp/baseline_era 765188d
```
