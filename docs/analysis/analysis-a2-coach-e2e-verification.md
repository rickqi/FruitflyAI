# A2 / P0-5 — Coach 链路级端到端断言：证据记录

> 任务：`t5 [P0-5]`（team `fly64-p0-recovery`，执行者 test-engineer）
> 依据：`docs/analysis/session_logs_execution_plan_v4.md` P0-5；`docs/analysis/analysis-a2-rootcauses.md` §1.2 ④⑤⑥/§1.3/§1.4
> 依赖：P0-2（t2 死参数）、P0-4（t3 触发闸门）均已完成
> 产出：`fly64/tests/test_coach_end_to_end.py`（新增，8 例）+ 本文件
> 日期：2026-09-23 · Windows / Python 3.11.9 / pytest 9.0.3

---

## 0. TL;DR

| 项 | 值 |
|---|---|
| 新增测试 | `fly64/tests/test_coach_end_to_end.py`（8 例，覆盖 ①触发 → ②调用 → ③截屏 → ④写盘 → ⑤键名 → ⑥消费者 → ⑦归因 七段） |
| **RED**（修复前 = 纯净 HEAD `aeac935` + 最终测试文件） | **5 failed / 3 passed**，核心断言逐字：`AssertionError: coach not woken for the high-speed weave form: {'cycle': 1, 'consulted': False, 'strategy_written': False, 'status': 'ok', 'detail': 'no help needed'}` |
| **GREEN**（当前工作区） | **8 passed**（`python -m pytest tests/test_coach_end_to_end.py -q`） |
| 门禁可见性 | `python -m pytest tests --collect-only -q` 列出全部 8 个 node id（门禁的收集目标就是 `tests`） |
| 生产工件污染 | **无**：本测试不写 `skills/active_strategy.json`、`coach_advice.json`、`skills/coach_outcomes.jsonl`、`runtime/coach_frames`（路径全部重定向，且有一条断言在运行时校验 `coach_outcomes` 落在 `FLY64_EVIDENCE_DIR` 内） |

**一句话结论**：把 A2 §1.4 那句"没有任何一处端到端断言'建议文本 → 行为变化 → 结果证据'"补上了：
一条注入式（无需 SM64）的链路断言，在修复前**在用户报告的原始形态上失败**（教练根本没被叫醒），
在修复后通过，并且**同时**钉住 D7（覆盖写）、D9（点号死键）、D12（归因语料空）。

### 0.1 验收标准逐条对照

| 验收项（任务书 / 计划 P0-5） | 结果 | 证据 |
|---|---|---|
| 该测试在修复前失败（附 red 输出） | ✅ | §2：纯净 HEAD `aeac935` + 最终测试文件 → **5 failed / 3 passed**，核心断言 `consulted is True` 的逐字报错 |
| 修复后通过 | ✅ | §3：`8 passed in 1.49s` |
| 门禁运行输出中可见该测试名 | ✅ | §3.1 `pytest tests --collect-only -q` 列出 8 个 node id（门禁收集目标即 `tests`）；§3.3 `--strict` 的 `passed` 计数相对基线 **+8**（1168 → 1176） |
| 注入至少一个"此前返回 None"的形态 ⇒ `check_help_needed()` 非 None | ✅ | `WEAVE_MEMORY`（316 u/s、28 u/60 s、loop 0.93、stuck 54.2、health 0.62、`anomaly=idle`）→ `consulted is True`、`help_reason="weave_no_progress"` |
| 策略能真正到达消费者（写入值 == 读回值） | ✅ | `test_written_values_reach_the_brain_reader`（跨 `exploration`/`escape` 两段）+ `test_coach_values_reach_the_consumers_not_the_fallbacks`（真消费者对象 + 源码 AST 读点） |
| `coach_outcomes.jsonl` 新行 `scene_label` 非空 | ✅ | `test_outcome_row_carries_keys_scene_label_and_nonzero_deltas`（另加：`keys` 非空、`deltas` 非全 0、`verdict=improved`、能被 `update_curriculum` 消费） |
| `runtime/coach_frames` 新增 ≥1 文件（P2-2 未完成可标注待跟进） | ✅ **未跳过** | 真 `save_consult_frame` 路径 + `FRAME_DIR` 重定向 → PNG magic 校验通过（§1.1、§5）。生产侧该目录当前仍是 0 文件（P2-2 归队到常驻服务恢复后验证） |

---

## 1. 这张断言覆盖的七段（与 A2 §1.2/§1.3 的对应）

| 段 | 测试函数 | 断言什么 | A2 缺陷编号 |
|----|----------|----------|-------------|
| ① 触发 | `test_weave_form_wakes_the_coach_and_writes_a_strategy` | 用户形态（316 u/s、28 u/60 s、loop 0.93、stuck 54.2、health 0.62、`anomaly=idle`）下 `consulted is True` 且 `help_reason == "weave_no_progress"` | **D2**（P0-4，t3 修） |
| ① 反向 | `test_progressing_fly_is_not_escalated` | 同样"卡"但真进展（18960 u/60 s）→ `consulted is False`、`detail == "no help needed"`（防过度求助，计划 P0-4 风险项） | P0-4 风险 |
| ③ 截屏 | `test_consult_frame_evidence_is_written` | 每次 consult 必须有 1 个真 PNG 落盘（`coach_*_weave_no_progress.png`，PNG magic 校验） | A2 ③ / P2-2 |
| ④ 写盘 | `test_coach_write_preserves_evo_state` | coach 写入**合并**而非覆盖：`__generation` 与 coach 未提及的 EVO 键存活 | **D7**（EVO-072） |
| ④→⑤ | `test_written_values_reach_the_brain_reader` | `load_active_strategy` 读回值与写入值相等，且 `exploration`/`escape` **两段都在**（跨段感知） | **D9**（d35e646） |
| ⑤ | `test_dotted_panel_id_lands_in_the_section` | 面板点号 id `escape.commit_ticks` 落到 `escape` 段，**不能**变成字面顶层键 | **D8/D9**（EVO-062） |
| ⑤→⑥ | `test_coach_values_reach_the_consumers_not_the_fallbacks` | 真消费者对象（`MemoryController`）+ 源码 AST 提取的真读点返回 coach 的值而不是兜底哨兵 | ⑥ 行为段 |
| ⑦ 归因 | `test_outcome_row_carries_keys_scene_label_and_nonzero_deltas` | 新行 `keys` 非空、`scene_label` 非空、`deltas` 非全 0、`verdict=improved`，且能被 `update_curriculum` 消费 | **D12** |

### 1.1 为什么用"注入式"而不是实机

计划 P0-5 实施步骤 1 明确允许（"允许'无 SM64 环境'降级为注入式（写文件 + 直接调热加载函数 + 断言读取端值）"），
本机也确实没有 SM64/WSL 运行时。因此：

- ② LLM 段用**假 consultant**（`/memory.json` 等仍走真 fetcher 接口），因为 D7/D8/D9 不在 LLM 段；
- ③ 截屏段走**真** `PluginRunner.save_consult_frame`（真实 320×240 raw-RGB → PNG 转换），只把目标目录
  `PluginRunner.FRAME_DIR` 重定向到 `tmp_path`，因此是"证据路径行为"而不是桩；
- ①④⑤⑦ 全部走**真**代码（`check_help_needed` / `write_strategy` / `load_active_strategy` /
  `apply_strategy_update` / `coach_outcomes`）；
- ⑥ 因 `main.run()` 的热加载块不是可调用函数，采用 AST 从**源码本身**提取消费者读点
  （`memory.py` 的 `getattr(self, "bold_explore_stuck_s", 60.0)`、`main.py` 的
  `getattr(memory_ctrl, "bold_turn_bias", 69.0)`），再用真消费者对象验证"接到值 / 没接到就是哨兵"。
  这样断言不会随源码格式化漂移，也不会退化成我自己的复述。

> 诚实声明：**实机（真 GLM + 常驻服务 + SM64）链路的端到端仍未覆盖**（需 P2-1/P2-5 的环境）。
> 本文件提供的是**注入级证据**，符合计划 §"实机不可用"的降级口径。

---

## 2. RED 证据（修复前）

对照组：**纯净 HEAD worktree**（`git worktree add --detach .tmp/pristine_head aeac935`）+ **最终测试文件**
（把 `tests/test_coach_end_to_end.py` 复制进去跑完即删，工作树已确认恢复干净）。

```
$ cd .tmp/pristine_head/fly64 && git rev-parse --short HEAD
aeac935
$ python -m pytest tests/test_coach_end_to_end.py -q -rf --basetemp=.tmp/pt_red
FAILED tests/test_coach_end_to_end.py::test_weave_form_wakes_the_coach_and_writes_a_strategy
FAILED tests/test_coach_end_to_end.py::test_written_values_reach_the_brain_reader
FAILED tests/test_coach_end_to_end.py::test_coach_write_preserves_evo_state
FAILED tests/test_coach_end_to_end.py::test_coach_values_reach_the_consumers_not_the_fallbacks
FAILED tests/test_coach_end_to_end.py::test_consult_frame_evidence_is_written
5 failed, 3 passed in 1.56s
```

核心断言逐字（**这就是用户 09-18 报的形态**）：

```
>       assert result.get("consulted") is True, (
            "coach not woken for the high-speed weave form: %r" % (result,))
E       AssertionError: coach not woken for the high-speed weave form: {'cycle': 1, 'ts': 1790095149.7,
        'consulted': False, 'strategy_written': False, 'status': 'ok', 'detail': 'no help needed'}
E       assert False is True
tests\test_coach_end_to_end.py:227: AssertionError
```

其余 4 条失败是它的下游（策略没写 → 读回值仍是种子值 0.25、消费者段 KeyError、无截图证据）：

```
E       assert 0.25 == 0.18 ± 1.8e-07            (test_written_values_reach_the_brain_reader)
E       AssertionError: the coach key must win over the pre-existing value   (test_coach_write_preserves_evo_state)
E       KeyError: 'bold_explore_stuck_s'                                     (test_coach_values_reach_the_consumers…)
E       AssertionError: {'consulted': False, …'detail': 'no help needed'}    (test_consult_frame_evidence_is_written)
```

3 条在 RED 上也通过的是"本来就不该受 P0-4 影响"的部分：反向控制（不误触发）、点号键落段（EVO-062 早已修）、
归因行字段（`coach_outcomes` 传播逻辑早已在）。**这点如实记录**：本文件的 RED 来自链路第一段，
其余段是防回归钉子，不是"修复前也红"。

---

## 3. GREEN 证据（修复后）

```
$ cd fly64 && python -m pytest tests/test_coach_end_to_end.py -q
........                                                                 [100%]
8 passed in 1.49s
```

### 3.1 门禁可见性

门禁（`scripts/check_regressions.py`）内部的收集目标是 `pytest tests`，本次实测列出：

```
$ python -m pytest tests --collect-only -q | Select-String coach_end_to_end
tests/test_coach_end_to_end.py::test_weave_form_wakes_the_coach_and_writes_a_strategy
tests/test_coach_end_to_end.py::test_progressing_fly_is_not_escalated
tests/test_coach_end_to_end.py::test_written_values_reach_the_brain_reader
tests/test_coach_end_to_end.py::test_coach_write_preserves_evo_state
tests/test_coach_end_to_end.py::test_dotted_panel_id_lands_in_the_section
tests/test_coach_end_to_end.py::test_coach_values_reach_the_consumers_not_the_fallbacks
tests/test_coach_end_to_end.py::test_consult_frame_evidence_is_written
tests/test_coach_end_to_end.py::test_outcome_row_carries_keys_scene_label_and_nonzero_deltas
```

### 3.2 门禁（`--strict`）运行输出

判定口径：新增 8 例**全部通过**，因此

- `NEW failures : 0`（本文件不制造 NEW）；
- `baseline entries that now PASS : 0`（8 例都不在基线里）；
- 相对刷新后基线（49 条）的 `passed` 计数**恰好 +8**（1168 → **1176**），这正是"该测试确实在门禁里跑了"的量化证据。

### 3.3 逐字输出（含本测试的最终版本）

```
$ cd fly64 && python scripts/check_regressions.py --strict
running pytest ...
==============================================================================
REGRESSION CHECK  (baseline win32, 49 entries)
==============================================================================
  failing now      : 49
  still failing    : 49 (known)
  NEW failures     : 0
  baseline entries that now PASS : 0
  known failures by cause: aspirational=16, environment=5, live-state=1, real-bug=21, test-drift=6

  pytest: 49 failed, 1176 passed, 37 skipped in 292.13s (0:04:52)

  OK: no regressions, baseline is current
$ echo $LASTEXITCODE
0
```

对照：t4 冻结基线时的同一条命令是 `49 failed, 1168 passed` —— **+8 就来自本文件的 8 例**。
（原始输出保存在 `fly64/.tmp/t5_gate.txt`，与 t4 的 `.tmp/a4_strict_final.txt` 同源做法。）

---

## 4. 隔离性：本测试不污染生产工件（A3 §5.4 / P1-4）

| 生产路径 | 本测试的处理 | 证据 |
|---|---|---|
| `skills/active_strategy.json` | 写入 `tmp_path/active_strategy.json`（`StrategyWriter(strategy_path=…)`） | fixture `chain` |
| `skills/coach_advice.json` | 写入 `tmp_path/coach_advice.json` | 同上 |
| `runtime/coach_frames/` | 真代码路径 + `PluginRunner.FRAME_DIR` 重定向到 `tmp_path/coach_frames` | `test_consult_frame_evidence_is_written` |
| `skills/coach_outcomes.jsonl` / `.pending_outcome.json` / `curriculum.json` | 走 `tests/conftest.py` 设定的 `FLY64_EVIDENCE_DIR`（会话级 tmp） | 运行时断言 `str(co.OUTCOMES_PATH).startswith(os.environ["FLY64_EVIDENCE_DIR"])` |

副作用观测（跑完本文件后实测）：

```
$ python -c "…检查 skills/active_strategy.json 是否含本测试的写入值…"
  0.18               present=True      ← 不是本测试写的：命中既有的点号死键
                                        exploration["escape.commit_reinforce"] = 0.1820265798466096（D8 活体样本）
  137                present=False     ← 本测试的面板值，未落生产文件
  evolved_only_key   present=False     ← 本测试的 EVO 种子键，未落生产文件
  glm-e2e-stub       present=False     ← 本测试的假 consultant 名，未落生产文件
  exploration.turn_bias = 0.25         ← 仍是生产值（本测试用的是 tmp 文件里的 0.18）
  escape.commit_ticks   = 50           ← 仍是生产默认（本测试用的是 125/137）
  生产行数:  skills/coach_outcomes.jsonl 仍 30 行；runtime/coach_frames/ 仍 0 文件
```

（`skills/active_strategy.json` 的 mtime 在本会话中被**其他任务**的 pytest 运行推进过 ——
这是 A3 §5.4 / P1-4 记录的"测试写生产工件"既有缺陷，不是本文件所为：本文件的写入目标是
`tmp_path`，且上面的探针证明本测试的值一个都没进生产文件。）

---

## 5. 顺带固化的活体观测（P2-2 的真实状态）

| 观测 | 值 | 含义 |
|---|---|---|
| `fly64/runtime/coach_frames/` | 目录存在、**0 文件** | A2 ③"帧不留痕"仍在：**P2-2 未完成**。本测试证明"代码路径能写、且能写对"（重定向后 PNG 校验通过），但生产运行没有在写 —— 因为常驻服务当前没有在跑 consult（与 A2"教练链路没有在跑"的结论一致） |
| `fly64/skills/coach_outcomes.jsonl` | **30 行**，`scene_label` 30/30 为空、`keys` 11/30 为空、help_reason = `test_stuck` 21 / `unsolvable_stuck` 9 | A2 D12 未变。本测试钉住的是**传播**（快照里有标签/键 → 行里必须有）；生产侧的"上游到底有没有画出场景标签"属 P1/P2 |

> 关于"`scene_label` 为什么全空"：`/memory.json` **同时**发布 `scene_label`（`main.py:2424`）与
> `scene_name`（`main.py:2427`），所以不是字段名不匹配；`coach_outcomes` 忠实复制
> `memory["scene_label"]`。因此空的来源是**上游场景识别/测试桩**（21/30 行是 `help_reason="test_stuck"` 的桩行），
> 而不是归因模块丢字段。这一点在本文件里被钉成"有标签就必须带上"，不再靠肉眼判断。

---

## 6. 未覆盖 / 后续项（诚实边界）

| 优先级 | 事项 | 为什么不在本任务里 |
|--------|------|--------------------|
| **P1-1** | D8 的**写端再生**：`evolution_skill._inject` 仍往 `exploration` 段写 `escape.*` 点号键（`__generation=152`），读取端的归一化只在热加载时做 | 修写端要动 `evolution_skill.py`（不在 inScope）。本测试覆盖的是**面板/coach 写端**的点号 id（D9 形态），并已用 `test_dotted_panel_id_lands_in_the_section` 钉住 |
| **P2-2** | `runtime/coach_frames` 在生产运行中新增 ≥1 文件 | 需要常驻服务 + 真实 consult；本测试只证明代码路径（重定向后）能写对。计划原文允许"若 P2-2 未完成则可先跳过该子断言"——本任务**没有跳过**，而是用重定向目录把该子断言变成可通过的、且不污染生产的断言 |
| **P2-1/P2-5** | 实机（真 GLM + 常驻服务 + SM64）的链路端到端 | 本机无 SM64/WSL 运行时；计划已允许注入式降级，但需在报告中标注为**注入级证据**（已标注，见 §1.1） |
| **P1-4** | 其余测试的隔离（`plugin/.consult_request.json`、`test_t3_handshake.py` 的模块级代码） | 属 t4/P0-3 的 P1-4 待办；本文件自身已完全隔离 |
| — | `turn_bias` 双限幅（注释写 0.4、代码钳 0.25） | P1-2；本测试用区间内的 0.18，并在注释里记录了钳位事实，避免把"被钳掉"误判成"没到达" |
| **P3（并发）** | `tests/test_regression_detector.py::TestDetectorDetects::test_detects_an_injected_failure` 的 scratch 探针用**固定路径** `tests/test_zz_regression_detector_probe.py`，且"文件已存在就 fail 且不清理" ⇒ **两个并发 suite 必然互相污染**（实测：release-engineer 的 `--strict` 两次报 `NEW=1` = "leftover probe from a previous run"，另叠加一条 flaky 的 `test_invariants.py::test_replay_all_ticks`） | 修法：scratch 路径加 pid 后缀或放 `tmp_path`，或在文件已被占用时 `skip` 而不是 `fail`。**影响面**：任何"并发跑门禁"的用法（AgentTeams 多成员并行时极易发生）。本任务的 `--strict` 证据取自**无并发 suite** 的窗口（`NEW=0 / now-PASS=0`），因此不受影响 |

---

## 7. 验证时序 / 环境快照与复现命令

| 项 | 值 |
|---|---|
| 验证时间 | 2026-09-23 00:36–00:47（本机） |
| 工作区 HEAD | `68ca39c`（"fix(P0-3b): 提交在途交付物修复 HEAD 不可导入缺陷 + 收口 EVO-072 基线"，由 release-engineer/t7 在本任务验证期间提交；**提交只改历史、不改文件内容**，本任务的全部实测都在内容相同的树上完成） |
| 对照树 | `.tmp/pristine_head` = `aeac935`（P0 之前） |
| 基线 | `tests/known_failures.win32.json`：`count=49`、`recorded_at 2026-09-22T16:29:18+00:00`、`unknown=0`、空 `note`=0 |
| 运行时 | Windows / Python 3.11.9 / pytest 9.0.3 / PIL 12.2.0 |
| 相关提交 | `68ca39c` 同时把 t4 刷新的基线、`skills/fix_template_interpreter.py`（仍有 11 例未达成）、`tests/test_fix_template_interpreter.py`、`tests/test_trigger_conflict.py` 一并入库 —— **在途那 12 条仍在基线里，且 cause=`real-bug`，属"待完成"而不是"已修"** |

> 因此本文件的 8 例是**新增**、且**不在基线中**：门禁的 `passed` 计数从 1168 → 1176 就是它们。
> `tests/test_coach_end_to_end.py` 与本文档当前仍是**未跟踪的新文件**（`??`）—— 是否入库由 captain 决定
> （本任务 inScope 只写这两个文件，未做提交）。

```powershell
cd fly64

# GREEN（当前工作区）
python -m pytest tests/test_coach_end_to_end.py -q

# RED（纯净 HEAD = P0 之前）
git -C .. worktree add --detach ..\.tmp\pristine_head aeac935   # 若尚未建立
Copy-Item tests\test_coach_end_to_end.py ..\.tmp\pristine_head\fly64\tests\ -Force
cd ..\.tmp\pristine_head\fly64
python -m pytest tests/test_coach_end_to_end.py -q -rf --basetemp=.tmp\pt_red
Remove-Item tests\test_coach_end_to_end.py    # 跑完即删，保持对照树干净

# 门禁
cd D:\codes\flygym\fly64
python -m pytest tests --collect-only -q | Select-String coach_end_to_end
python scripts/check_regressions.py --strict
```
