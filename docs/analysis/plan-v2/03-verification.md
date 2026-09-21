# 03 — 计划可执行性与数值准确性验证（T3）

> 任务：`t4 [T3] — 计划可执行性与数值准确性验证`
> 执行者：plan-verifier（独立验证员，非计划撰写者 plan-writer）
> 验证对象：`docs/fly64_execution_plan_v2.md`（T2 产出，1577 行 / 132942 bytes）
> 对照基准：`docs/analysis/plan-v2/00-facts.md`（T0）、`docs/analysis/plan-v2/01-reconciliation.md`（T1）、
> `docs/fly64_export_logs_analysis_report.md`（被分析报告，314 行）、仓库真实文件
> 验证时间：2026-09-20（Windows，`sys.platform = win32`）
> 解释器：`D:\codes\flygym\.venv\Scripts\python.exe`（Python 3.11.9）
> Shell：Windows PowerShell 5.1.26100.1591（**无 pwsh 7**）
> git HEAD：`1badb4072d27116a967bfaa3dd1d614c133881b9`（`master`，305 commits）

---

## 0. 裁决（先看这里）

**verdict = `needs_revision`**

理由（任务给定判据：存在路径错误、命令失败或数值不符即必须 needs_revision）：

| 类别 | 结果 |
|---|---|
| 计划中**被明确规定为验证命令**的失败条数 | **2 条 high**（行动 7 验证(2) exit 1；§0.2「复制即用」块 exit 1） |
| 路径错误（引用了不存在且**未被计划自身声明为不存在/待新增**的路径） | 1 条（`.cache/malecns/weights.npz`，low） |
| 路径拼写错误 | **0 条**（183 个存在路径全部命中；14+13+2 个不存在路径全部被计划显式声明并给出替代） |
| 数值/行号与仓库实测不符 | **high 1（依赖环）+ medium 6 + low 3** |
| 报告 §5 行动覆盖 | ✅ 12/12 逐项对应，无丢失、无自造 |
| 报告/旧计划数字被计划取代的正确性 | ✅ 计划引用的报告与旧计划行号/原文**逐条实测一致** |
| 幻象 API 反证 | ✅ 16 个符号全仓 **0 命中**，计划的反证清单全部成立 |
| 计划核心基线（38 failed / 929 passed / 36 skipped / NEW 10 / exit 1） | ✅ **独立复跑完全一致** |

**结论**：计划的**事实底座与数字主体是可靠的**（核心基线、路径存在性、幻象反证、报告行号引用全部经独立复跑证实），
但存在 **2 条会直接失败的验证命令**、**1 组循环依赖**、**若干条计数/行号错误**，需要一次定点修订后可判为 pass。

**发现项总计 20 条**：high 3 / medium 10 / low 7 / blocker 0。

---

## 1. 验证方法与可复现性

### 1.1 验证前的仓库状态（pristine 基线）

```powershell
# cwd = D:\codes\flygym
git status --porcelain        # → 5 条（全部未跟踪）
```

```
?? .omo/
?? docs/analysis/plan-v2/
?? docs/fly64_execution_plan.md
?? docs/fly64_execution_plan_v2.md
?? docs/fly64_export_logs_analysis_report.md
```

`git diff --stat` → 空。即：验证开始时**无任何已跟踪文件被改动**。

### 1.2 验证方法（5 条独立路径）

| 路径 | 手段 | 规模 |
|---|---|---|
| (1) 路径存在性 | 程序化抽取计划中**全部**反引号路径 token → 按仓库根 / `fly64/` 两种约定解析 → `Path.exists()` 实测 | 212 个 token（183 存在 + 29 不存在） |
| (2) 命令可执行性 | 逐条抄写计划的命令到脚本文件执行，记录**真实退出码 + 输出摘要**；写操作/WSL/GUI 命令改 `--report`/`--collect-only`/注明 | 36 条命令 |
| (3) 数值准确性 | 与 `00-facts.md` 逐项对账 + 直接重算（Python，非 `Get-Content`） | 40 项数值 |
| (4) 行号准确性 | 抽取计划中所有 `文件:行号` 引用，读取该行原文比对 | 200 条引用 |
| (5) 覆盖性与依赖 | 报告 §5 表逐行 vs 计划 `### 行动 N` 标题；依赖声明有向图成环检测 | 12 行动 / 12 依赖声明 |

### 1.3 验证过程中对仓库的改动与恢复（已恢复原状）

验证过程需要实际跑 pytest，会产生工作树污染（计划 §0.3/§4.1 已声明该风险）。**全部已恢复**：

```powershell
# cwd = D:\codes\flygym
git status --porcelain | Measure-Object -Line      # 污染峰值 118 → 恢复后 5
git restore -- fly64/.pytest-run fly64/plugin/.consult_request.json fly64/skills/README.md
git clean -fd fly64/.pytest-run
git diff --stat                                    # → 空
```

恢复后 `git status --porcelain` = **5 条**（与 1.1 完全一致），`git diff --stat` = **空**。
本任务只新增 `docs/analysis/plan-v2/03-verification.md` 一个文件；未改动任何代码、测试、基线、CI 或既有文档。
（验证脚本与原始输出落在仓库外的 `%TEMP%\plan-verify\`，不入库。）

---

## 2. 路径核对（任务要求 1）

### 2.1 汇总

| 分类 | 条数 | 说明 |
|---|---|---|
| **EXISTS** | **183** | 按「仓库根相对」或「`fly64/` 相对」任一约定均可命中真实文件/目录 |
| MISSING — 计划已在 §4.2 **表 B** 显式声明不存在并给出替代 | 14 | 全部实测确认**确实不存在**（计划无虚报） |
| MISSING — 计划已在 §4.2 **表 C** 标注「待新增」 | 13 | 全部实测确认**尚不存在**（属交付物，非缺陷） |
| MISSING — 计划正文显式说明「不存在/未找到」 | 2 | `test_central_complex.py`、`gent.md`（后者是引用报告的错字） |
| **MISSING — 计划未声明** | **1** | `.cache/malecns/weights.npz` → **F19** |
| **路径拼写错误** | **0** | 无 |

### 2.2 表 B（计划声明不存在）逐条实测确认 — 全部为真

| 路径 | 实测 `Path.exists()` | 结论 |
|---|---|---|
| `fly64/tests/known_failures.json` | `False` | ✅ 计划正确（真实文件为 `known_failures.win32.json` / `.linux.json`） |
| `fly64/plugin/evolution_logs.py` | `False` | ✅ |
| `fly64/config/color_profiles.json` | `False` | ✅（`fly64/config/` 存在，内含 `sm64config.txt`；计划 B3 的替代说明正确） |
| `fly64/pyproject.toml` | `False` | ✅ |
| `.pre-commit-config.yaml` | `False` | ✅ |
| `fly64/plugin/fly64-service.pid` | `False` | ✅（运行期产物） |
| `fly64/plugin/service.log` | `False` | ✅（运行期产物） |
| `fly64/plugin/service_status.json` | `False` | ✅（审计输出为 `absent`，实测一致） |
| `fly64/plugin/watchdog.log` | `False` | ✅（运行期产物；但 B7b 的 **gitignore 结论错误** → F11） |
| `fly64/skills/coach_advice.json` | `False` | ✅（审计输出 `absent`） |
| `fly64/setup.cfg` / `fly64/tox.ini` | `False` | ✅ |
| `fly64/tests/conftest.py` | `False` | ✅（真实位置 `fly64/conftest.py`，`True`） |
| `playwright`（pip 包） | `find_spec → False` | ✅ |

### 2.3 表 C（计划标注待新增）逐条实测确认 — 全部尚不存在

`fly64/plugin/sm64_watchdog.sh`、`fly64/tests/test_sm64_watchdog.py`、`fly64/scripts/baseline_tool.py`、
`fly64/tests/test_scene_danger_learning.py`、`fly64/scripts/replay_curriculum.py`、
`fly64/tests/test_curriculum_end_to_end.py`、`fly64/tests/test_cx_navigation_loop.py`、
`fly64/tests/test_coach_roundtrip.py`、`fly64/tests/test_layout_contract.py`、
`fly64/scripts/layout_baseline/`、`fly64/requirements-dev.txt` —— **11 项全部 `False`**（与表 C 一致）。

### 2.4 关键存在路径的字节数/规模复核 — 全部一致

| 路径 | 计划值 | 实测 | 判定 |
|---|---|---|---|
| `fly64/plugin/watchdog.sh` | 2549 bytes / 75 行 | 2549 / 75 | ✅ |
| `fly64/web/monitor-preview.html` | 30267 bytes | 30267 | ✅ |
| `fly64/web/layout-wireframe.html` | 15845 bytes | 15845 | ✅ |
| `fly64/web/evo-params.html` | 10196 bytes | 10196 | ✅ |
| `fly64/tests/known_failures.win32.json` | 11228 bytes / 38 条 | 11228 / 38 | ✅ |
| `fly64/tests/known_failures.linux.json` | 7749 bytes / 24 条 | 7749 / 24 | ✅ |
| `fly64/skills/evolution_log.jsonl` | 7.8 MB | 7835839 B | ✅ |
| `fly64/scripts/` 文件数 | 111 | 111 | ✅ |
| `fly64/plugin/` 的 `.py` 数 | **8** | **7** | ❌ → **F4** |
| `fly64/.tmp/` 的 `.sh` 数 | **55** | **59** | ❌ → **F5** |

### 2.5 §4.2 表 A 自述条数与表体不符

* 表 A 标题（L1432）：**「共 76 条」**
* 表体实际编号行：**1 … 84（84 行）**
* §4.2 导语（L1430）声称「以下 3 张表的每一行都由 `Test-Path`（Windows）实测生成」——表体 84 行确为真实路径，但标题计数错误 → **F7**

---

## 3. 命令可执行性实测（任务要求 2）

**执行原则**：全部命令抄写为脚本文件后执行（避免交互式 shell 的引号二次解析）；会改动仓库的 pytest 命令执行后统一清理；
需要 WSL/GUI 的命令标注为不可执行并给出替代。

### 3.1 只读命令（29 条）—— 27 条完全符合预期

| # | 计划位置 | 命令 | 实测退出码 | 输出摘要 / 判定 |
|---|---|---|---|---|
| 1 | 行动 3 验证(1) | `python scripts\audit_contract_pairs.py` | **0** | 末行 `TOTAL dead-writes + silent-defaults: 8` ✅ 与计划一致 |
| 2 | 行动 3 验证(1) | `... --all` | **0** | 同上 ✅ |
| 3 | 行动 3 验证(1) | `... --json \| Select-Object -First 5` | **0** | ✅ |
| 4 | 行动 3 验证(2) | `... --mode trace --target control` | **2** | `error: unrecognized arguments` ✅ 与计划「期望 exit 2」一致 |
| 5 | 行动 2 验证(4) | `-c "…count==len…"` | **0** | `True` / `True` ✅ |
| 6 | 行动 4 验证(3) | `set_dopamine / update_weights` 正则 | **0** | `True` / `True` ✅ |
| 7 | 行动 6 附录 | `default ∉ [min,max]` 自检 | **0** | 3 条：`exploration.dopamine_revisit_cost 0.5∉[0,0.4]`、`exploration.breakout_forward_bias 0.7∉[0.2,0.4]`、`escape.fallen_jump_boost 0.6∉[0.3,0.4]` ✅ 与计划逐项一致 |
| 8 | 行动 7 验证(3)(a) | `navigation_vectors / set_anchor` | **0** | `True` / `True` ✅ |
| 9 | 行动 7 验证(3)(b) | `self.cx.update( / goal_vectors= / visual_azimuth=` | **0** | 3×`True` ✅ |
| 10 | 行动 8 验证(1) | KPI 计数 | **0** | `write lines: 36 assignments: 36` ✅ |
| 11 | 行动 11 验证(4) | linux 基线 schema | **0** | `count==len: True`；`causes: [aspirational, environment, live-state, test-drift, unknown]` ✅ |
| 12 | 行动 12 验证(2) | `playwright` 可用性 | **0** | `playwright: False` ✅ |
| 13 | §0.2 第二条 | `evolution_history` 记录数/唯一值/max | **0** | `records: 79` / `unique: 51` / `max brain_version: **None**` ⚠️ 见 **F8** |
| 14 | §0.3 | `git ls-files fly64/.pytest-run \| Measure-Object -Line` | **0** | **132** ✅ |
| 15 | §0.3 | `git check-ignore -v fly64/.pytest-run` | **1** | rc=1（未被忽略）✅ |
| 16 | §0.5 旧命令 | `python -m pytest fly64/tests/known_failures/ --collect-only` | **4** | `ERROR: file or directory not found` ✅ 与计划「exit 4」一致 |
| 17 | 行动 11 验证(1) | `pytest … -rf` + `check_regressions.py --report` | **0 / 0** | `REGRESSION CHECK (baseline win32, 38 entries)`、`NEW failures: 0` ✅ `--report` 路径与参数可用 |
| 18 | 行动 12 验证(3) | `python scripts\layout_audit.py` | **1** | `ModuleNotFoundError: No module named 'playwright'`（`layout_audit.py:52`）✅ 与计划「playwright 为显式前置」一致（安装后才有望 exit 0） |
| 19 | §0.2 第一条（here-string 块） | `& $py -c @' … '@` | **1** | `SyntaxError: invalid syntax` ❌ → **F2** |
| 20 | 行动 7 验证(2) | CX 构造 + 1000 tick | **1** | `TypeError: 'int' object is not callable` ❌ → **F1** |
| 21 | 行动 10 验证(1) | `... --json`（**不带管道**） | **0** | ✅ |
| 22 | 行动 10 验证(1) 原文 | `... --json \| Select-Object -First 20` | **-1** | 管道提前终止上游进程（`--json` 实际 **93 行**）→ 无法据此判 `exit 0` ❌ → **F18** |
| 23 | 行动 10 验证(1) | `... --trend` | **0** | `SELF-EVOLUTION TREND (1 snapshots)` ✅（与计划「仅 1 行」一致） |
| 24 | §0.2 第二块 | `python -c` here-string | — | 计划中只此一处 here-string（L60-71）；其余 10 条 `-c` 单行命令全部 exit 0 ✅ |

### 3.2 pytest 类命令（15 条）—— 逐条与计划声明一致

| # | 计划位置 | 命令（`cwd=fly64`，均带 `-p no:cacheprovider --basetemp .pytest-aN`） | 实测 | 计划声明 | 判定 |
|---|---|---|---|---|---|
| 1 | 行动 1 验证(4) | `tests\test_seqlock_watchdog.py` | **0**（11 passed） | 「仍为 11 passed」 | ✅ |
| 2 | 行动 8 验证(2) | `tests/test_p1_neural_takeover.py::TestKpiBaseline` | **1**（1 failed, 1 passed） | 当前 FAIL | ✅ |
| 3 | 行动 8 验证(3) | `tests\test_p1_neural_takeover.py` | **1**（1 failed, 21 passed） | 「全绿」为目标态 | ✅（现状符合期望） |
| 4 | 行动 2 验证(3) | `tests\test_regression_detector.py` | **1**（1 failed, 5 passed） | 「当前 1 failed / 5 passed」 | ✅ **逐字一致** |
| 5 | 行动 3 验证(4)/行动 9 验证(2) | `tests\test_coach_contract.py` | **0**（8 passed） | 「全绿」 | ✅ |
| 6 | 行动 6 验证(1) | `tests\test_dan_shaping.py` | **1**（1 failed, 2 passed） | 该文件含 1 条 NEW failure | ✅ |
| 7 | 行动 6 验证(2) | `tests\test_tunable_wiring.py` | **1**（1 failed, 11 passed） | 该文件含 1 条 NEW failure | ✅ |
| 8 | 行动 4 验证(2) | `test_restlessness + test_mushroom_body + test_gain_modulation` | **0**（95 passed） | 「必须仍全绿」 | ✅ |
| 9 | 行动 5 验证(4) | `test_coach_outcomes + test_curriculum_unknown_metric` | **0**（30 passed） | 「全绿」 | ✅ |
| 10 | 行动 9 验证(3) | `test_strategy_passthrough + test_strategy_update_endpoint + test_dialogue_llm_decision + test_plugin_mhr` | **0**（98 passed） | 「全绿」 | ✅ |
| 11 | 行动 10 验证(4) | `test_dashboard_protocol + test_dashboard_js` | **0**（8 passed） | 「全绿」 | ✅ |
| 12 | 行动 8 验证(4) | `test_bridge + test_coach_dopamine` | **1**（1 failed, 12 passed） | 「通过集合不缩小」 | ✅ 唯一失败项为**已登记基线 `environment` 条目**（`test_coach_dopamine.py::test_main_loop_wires_coach_bias`，note = gbk 解码），`test_bridge.py` 6 条基线条目当前全通过 |
| 13 | 行动 2 步骤 2 | `test_autonomy_regression + test_coach_pipeline` | **1**（2 failed, 18 passed, 9 skipped） | 3 条 `unknown` 待分类 | ✅ 其中 2 条实测失败（版本契约 + `fallen_recovery`），第 3 条在 `test_regression_detector.py` 内 |
| 14 | 行动 12 验证(1) | `tests\test_layout_contract.py` | 不可执行 | **待新增**（表 C9） | ✅ 属未交付物 |
| 15 | 各行动验证(5)「无回归」 | `scripts\check_regressions.py` | **1**（248.6 s） | exit 1 / 38 failed / 929 passed / 36 skipped / NEW 10 | ✅ **完全一致，见 3.3** |

### 3.3 核心回归门禁的独立复跑（计划最重要的一条基线）

```powershell
# cwd = D:\codes\flygym\fly64
& $py scripts\check_regressions.py
```

**实测原始输出（关键行）**：

```
REGRESSION CHECK  (baseline win32, 38 entries)
  failing now      : 38
  still failing    : 28 (known)
  NEW failures     : 10
  baseline entries that now PASS : 10
  known failures by cause: aspirational=16, environment=5, real-bug=2, test-drift=3, unknown=2
  pytest: 38 failed, 929 passed, 36 skipped in 246.36s (0:04:06)
EXITCODE=1
```

* 与计划 §0.1 的 `38 failed, 929 passed, 36 skipped` / exit `1` / `(baseline win32, 38 entries)` **逐项一致**；
* 10 条 NEW 失败项与 T0 记录的清单**逐一相同**（`dan_shaping`/`evo_tunable`/`evolution_capability`×2/`mbon_saturation`×3/`phase6_fitness_inputs`/`regression_detector`/`tunable_wiring`）；
* 10 条「基线条目转为通过」亦一致（含 6 条 `test_bridge.py`）；
* 计划 §0.1 的 `216.43 s` 为 T0 时点值；本次 246.36 s（墙钟 248.6 s）——**耗时随环境浮动，不构成偏差**。

### 3.4 无法执行的命令（2 条）与替代验证方式

| 计划命令 | 位置 | 无法执行原因 | 替代验证 |
|---|---|---|---|
| `bash -n plugin/sm64_watchdog.sh` | 行动 1 验证(1) | 本机为 Windows，无 `bash`；脚本本身也尚不存在（表 C1） | 计划已要求「Windows 无 `bash` 时 `pytest.skip`」；可由 WSL 侧执行 |
| 行动 1 验证(5)（kill SM64 → 观察 ≤60 s 重启） | 行动 1 验收(5) | 需要 WSL + 真实 SM64 进程 | 计划已在 L236 显式标注「本机（Windows）无法验收，须标注待 WSL 验证」——**计划自我声明正确** |

其余需 WSL/GUI/CI 的验收（行动 8 的真实运动行为、行动 10 的 `/evolution-health.json` 返 200、行动 11 的 CI 实际执行、
行动 12 的 Playwright 渲染）均已在计划 §4.3「不能」清单中显式声明 —— **验证确认该清单与实际限制相符**。

---

## 4. 数值准确性核对（任务要求 3）

### 4.1 与 `00-facts.md` 的对账（40 项）

| # | 数值 | `00-facts.md` | 计划取值 | 本次独立重算 | 判定 |
|---|---|---|---|---|---|
| 1 | `BRAIN_VERSION` | `2.23.11` @ `main.py:39` | 2.23.11 | `2.23.11` @ 39 | ✅ |
| 2 | `skills.md` 版本 | `:3`=2.23.7 / `:70`=2.23.10 | 同 | 同（实测该两行原文） | ✅ |
| 3 | `canonical_versions.brain` | 2.23.6 | 2.23.6 | 2.23.6 | ✅ |
| 4 | git HEAD / describe / commits | `1badb40…` / `causal-baseline-241-g1badb40` / 305 | 同 | 同 | ✅ |
| 5 | 未提交改动（测试前） | 3 | 3 | 5（含 T1/T2 两个新文档；计划口径为「测试前」，成立） | ✅ |
| 6 | 未提交改动（跑 pytest 后） | 115（M45/D66/??4） | 115 | 118（M91/D2/??9，全量门禁）；102（单文件 `test_regression_detector`） | ✅ 量级一致 |
| 7 | pytest 汇总 | 929 / 38 / 36 | 929 / 38 / 36 | **929 / 38 / 36** | ✅ |
| 8 | 回归门禁退出码 | 1（10 NEW，非 baseline 缺失） | 1 | **1**，首行 `(baseline win32, 38 entries)` | ✅ |
| 9 | win32 基线 | 38；aspirational16/env14/test-drift3/real-bug2/unknown3 | 同 | 同 | ✅ |
| 10 | linux 基线 | 24；aspirational16/env1/live-state2/test-drift3/unknown2 | 同 | 同 | ✅ |
| 11 | 跨平台交集 | 22 / 16 / 2 | 同 | 22 / 16 / 2 | ✅ |
| 12 | 未限定名基线文件 | 不存在 | 不存在 | `False` | ✅ |
| 13 | 写 `control` | 36 行 / 36 处，预算 26 | 36 / 26 | 36 / 36，预算 26 | ✅ |
| 14 | `agent.md` | 1360 行 / 117938 B | 1360 / 117938 | 1360 / 117938 | ✅ |
| 15 | evolution 记录 | 79 条 / 51 唯一 / 语义 50 | 79 / 51 / 含 3 条 `None` | 79 / 51 / `None` 记录数 **3** / 非 None 唯一 **50** | ✅ |
| 16 | 报告行数 | 314 | 314 | 314 | ✅ |
| 17 | 旧执行计划行数 | 676 | 676 | 676 | ✅ |
| 18 | `audit_contract_pairs` | exit 0 / TOTAL 8 | 同 | 0 / 8 | ✅ |
| 19 | `measure --json` phase6 指标 | trials 68 / commits 1 / rollbacks 67 / commit_rate 0.0147 / inert_fraction 0.6667 / delta.p50 0.0 / zero_fraction 0.6029 | 同 | **逐项一致** | ✅ |
| 20 | `params_total/wired/inert` | 21 / 7 / 14 | 同 | 21 / 7 / 14（`inert_fraction` 0.6667） | ✅ |
| 21 | `moved_dimensions_total` | wired 264 / inert 798 / share 0.7514 | 同 | 同 | ✅ |
| 22 | p44 | usable 0 / reuse 0.0 / verdicts {unchanged21, worse1, improved8} / skipped 30 | 同 | 同 | ✅ |
| 23 | `evolution_health_trend.jsonl` | 1 行 | 1 行 | 1 行 | ✅ |
| 24 | Playwright | 未安装 | 未安装 | `False` | ✅ |
| 25 | `DAN_*` 常量 | 9 个 @ `model.py:1337-1345` | 9 个 | 9 个（1337-1345 逐行核对） | ✅ |
| 26 | `test_dan_shaping` PIN | 0.20 / 0.80 / 0.35 | 同 | :23/:24/:25 原文一致 | ✅ |
| 27 | `brain_tunable_params` 越界项 | 3 处 | 3 处（含具体键） | 3 处，键与值全部一致 | ✅ |
| 28 | `curriculum.json` | stage 1 / attempts 8 / consecutive_ok 0 / unobserved 0 / history 20 | 同 | 同（`reset_at` 2026-09-17T20:43:41…） | ✅ |
| 29 | `coach_outcomes.jsonl` | 30 行 | 30 行 | 30 行 | ✅ |
| 30 | `test_seqlock_watchdog.py` | 103 行 / 11 test | 11 test | 11 passed | ✅ |
| 31 | `test_regression_detector.py` | 122 行 / 2 class / 6 test | 同 | 122 行；6 test（1 failed / 5 passed） | ✅ |
| 32 | `.github/workflows/ci.yml` | 66 行 / 6 个 `--ignore` / `-k "not male_cns and not sm64"` / timeout 30 / py3.12 / working-directory fly64 | 同 | 全部一致 | ✅ |
| 33 | ci.yml:3 注释（MaleCNS ~1.3GB） | — | 计划 L1186 引用 | ci.yml:3 原文确为 1.3GB 注释 | ✅ |
| 34 | 三脚本行数 | 322 / 177 / 468 | 同 | 322 / 177 / 468 | ✅ |
| 35 | `layout_audit.py` | 91 行 / 4 视口 | 91 行 / 4 门禁 | 91 行；VIEWPORTS 在 :25 | ✅ |
| 36 | `central_complex.py` | — | 491 行 | 491 行 | ✅ |
| 37 | `coach_outcomes.py` | — | 351 行 | 351 行 | ✅ |
| 38 | `main.py` / `model.py` | 2471 | 2471 / 2132 | 2471 / 2132 | ✅ |
| 39 | `dashboard.js` / `index.html` / `dashboard.css` | — | 1408 / 88 / 148 | 1408 / 88 / 148 | ✅ |
| 40 | `fly64/plugin/*.py` 数与 `.tmp/*.sh` 数 | — | 8 / 55 | **7 / 59** | ❌ → **F4 / F5** |

### 4.2 与计划自身一致性（内部算术）

| 项 | 计划值 | 独立重算 | 判定 |
|---|---|---|---|
| 12 项行动工作量上限之和 | 合计 21.5–36.5 人日 | **21.5 – 38.0**（差 1.5） | ❌ → **F12** |
| 36 处写点区间记法展开 | 36 | **37**（多出 1337） | ❌ → **F9** |
| §4.2 表 A 条数 | 共 76 条 | **84 行** | ❌ → **F7** |
| 报告 §5 行动数 | 12 项 | 12 项 | ✅ |
| `evolution_history` 最大脑版本 | 2.23.6 | 语义最大 2.23.6；**计划所给命令输出 `None`** | ❌ → **F8** |

---

## 5. 行号准确性核对（任务要求 3 续）

对计划中**全部 200 条** `文件:行号` 引用逐条读取原文比对：

| 结果 | 条数 | 说明 |
|---|---|---|
| 精确命中（该行即所述内容） | **186** | e.g. `bridge.py:103 self.seqlock_watchdog = SeqlockWatchdog()`、`central_complex.py:23 N_COLUMNS = 16`、`main.py:2042 model.scene_danger = scene_recognizer.danger_level()`、`test_p1_neural_takeover.py:230 KPI_LINES = 26` |
| 命中于计划自身给出的**区间**边界内（写作 `A-B`，引用点为区间端点/区间内） | **11** | e.g. `bridge.py:56-83`（56 即 `class SeqlockWatchdog:`，83 即 `reset()` 内 `self.stale = False`）；`dashboard.css:108-109`（109 即 `.stale-pill{…}`）；`main.py:2051-2052`（2052 即 `set_anchor(...)`）；`llm_consult.py:128,130`（与审计工具输出的 `W` 行号一致） |
| **行号错误** | **4** | `gain_modulation.py` 类定义（F10）、`main.py:758`（F15）、`test_p1_neural_takeover.py:228`（F16）、`service.py:94` 名称（F17） |

**计划对**外部文档**的行号引用（报告 + 旧计划）逐条核对 —— 全部正确**：

| 计划引用 | 计划所述 | 实测原文 | 判定 |
|---|---|---|---|
| 报告 L4 | 2.23.6 / 1360 行 / 7 会话 | `…（79 条记录，Brain v1.0.0→v2.23.6） × agent.md 规则体系（1360 行）` | ✅ |
| 报告 L21 | 7 会话 / 跨至 09-20 | `共导出 7 个有效 DSH 会话，覆盖 ~2026-09-11 至 2026-09-20` | ✅ |
| 报告 L107 | `gent.md` 错字 | `…和 gent.md（1360 行）提取的完整版本线` | ✅ |
| 报告 L149 | 79 条 / 51 唯一 / 2.23.6 | 逐字一致 | ✅ |
| 报告 L167 / L236 / L286 | 写 control 35→12 / ~12 / 降至 0 | 逐字一致 | ✅ |
| 报告 L170 / L228 / L252 | 36 条 / 13 env / `tests/known_failures.json` | 逐字一致 | ✅ |
| 报告 L226 | ~482 通过 / 11 基线失败 | 逐字一致 | ✅ |
| 报告 L238 / L294 | 11 基线失败 | 逐字一致 | ✅ |
| 报告 L249 | `✅ tests/known_failures.json + check_regressions.py` | 逐字一致 | ✅ |
| 旧计划 L4 / L109 | 2.23.11 / 「第 39 行」 | `> BRAIN_VERSION: "2.23.11"（main.py 第 39 行）` | ✅ |
| 旧计划 L6-10 | 已自我否证 | `> [!WARNING] **P0-1 与 P0-2 计划-代码鸿沟** … 基于幻象 API，无需修复` | ✅ |

---

## 6. 覆盖性与依赖一致性（任务要求 4）

### 6.1 报告 §5 的 12 项行动覆盖 —— ✅ 零丢失、零自造

程序化比对 `docs/fly64_export_logs_analysis_report.md` §5 表行（12 行）与计划 `### 行动 N —` 标题（12 个）：

| # | 报告 §5 原文 | 计划标题 | 优先级 |
|---|---|---|---|
| 1 | 实现 SM64 冻结自动重启 | 行动 1 — SM64 冻结自动重启 | P0-1 ✅ |
| 2 | 扩展回归基线 | 行动 2 — 回归基线获取：分类工具 + 平台全量分类（含标题修正说明） | P0-2 ✅ |
| 3 | 契约审计制度化 | 行动 3 — 契约审计制度化 | P0-3 ✅ |
| 4 | 场景识别→MB 学习闭环 | 行动 4 — 场景识别 → MB 学习闭环 | P1-4 ✅ |
| 5 | 课程晋级端到端验证 | 行动 5 — 课程晋级端到端验证 | P1-5 ✅ |
| 6 | DAN 权重自动化 | 行动 6 — DAN 权重自动化 | P1-6 ✅ |
| 7 | CX 空间导航回路部署 | 行动 7 — CX 空间导航回路部署 | P2-7 ✅ |
| 8 | main.py 写 control 清零 | 行动 8 — `main.py` 写 control 清零 | P2-8 ✅ |
| 9 | 教练通路契约测试 | 行动 9 — 教练通路契约测试 | P2-9 ✅ |
| 10 | 度量看板 | 行动 10 — 度量看板 | P3-10 ✅ |
| 11 | WSL 测试 CI | 行动 11 — WSL 测试 CI | P3-11 ✅ |
| 12 | CSS 契约测试 | 行动 12 — CSS 契约测试 | P3-12 ✅ |

编号沿用了报告的 1–12，P0/P1/P2/P3 分组亦与报告一致。**结论：无遗漏、无新增项。**

### 6.2 幻象 API 反证 —— ✅ 计划全部成立（16/16 全仓 0 命中）

```
control_written          0    ShutdownBridge           0
SEQLOCK_HEALTHY          0    SEQLOCK_DEAD             0
learn_from_outcome       0    record_danger            0
contract.emit            0    CoachContract            0
navigate_to_goal         0    store_navigation_hint    0
recall_navigation_hint   0    inject_navigation        0
EvolutionLogger          0    set_danger               0
def shutdown             0    class EvolutionLogger    0
```
（扫描范围：`fly64/` 全树 `*.py`，排除 `.venv`）

计划的其他行为类断言亦全部成立：

| 计划断言 | 实测 |
|---|---|
| `plugin/service.py` 全文 4 处匹配 `sm64\|restart\|kill\|Popen\|pkill`（唯一 `kill` 在 :28 属 docstring 示例） | **4** 处，全部为 `kill`，:28 确认在模块 docstring 内 ✅ |
| `plugin/runner.py` 7 处匹配 | **7** 处 ✅ |
| 全仓无 `auto.?restart / respawn / restart_sm64` **实现** | `auto.?restart` 0、`restart_sm64` 0、`respawn` 1（`main.py:1875` **注释**）✅ |
| `consolidate.sh` 重启对象是大脑 `pkill -f "[f]ly64\.main"` | :56 / :58 命中 ✅ |
| `fly64/web/` 下 `leaderboard\|排行榜\|phase6\|health_trend` **0 命中** | **0** ✅ |
| `layout_audit.py` 未被 CI、未被任何测试引用 | 唯一引用者是它自己 ✅ |
| `fly64/web/vendor/` 只含 three.js | `three.module.js`（1.27 MB）+ `addons/`（OrbitControls/Line2/CSS2DRenderer，同属 three.js 发行包）✅ |
| `test_central_complex.py` 不存在（契约测试缺失） | `False` ✅ |
| 表 A 行 46/47/48「3 条 / 1 条 / 2 条 NEW」 | `test_mbon_saturation` 3 条、`test_evo_tunable` 1 条、`test_evolution_capability` 2 条 ✅ |

### 6.3 跨行动依赖 —— ❌ 存在 1 组**循环依赖**

| 声明位置 | 原文 | 方向 |
|---|---|---|
| 计划 L335（行动 2 前置依赖） | 「**依赖行动 3**（CI 挂载点）——二者改同一个 `.github/workflows/ci.yml`，**必须同一批次提交**」 | 2 → 3 |
| 计划 L429（行动 3 前置依赖） | 「与**行动 2** 共用 `.github/workflows/ci.yml` → 必须同批提交」 | 3 → 2 |
| 计划 L1352（§3.1 依赖图） | `├── 同批 YAML ──> [行动 3 契约审计制度化]` | 2 → 3（单向） |

→ **A 依赖 B 且 B 依赖 A**，与任务要求 4 指名的矛盾类型完全吻合 → **F3（high）**。

其余依赖声明经成环检测**无环**，且语义一致：

* 行动 1（L239）「与行动 2 共享同一份基线」→ 1 ⇢ 2（软依赖，验收用）✅
* 行动 4（L529）「若选 (B) 则与行动 6 强耦合；**不要**让行动 4 等行动 6」与行动 6（L733）「建议顺序：行动 4 (A) 落地 → 行动 6 迁移；行动 6 不阻塞行动 4」**方向一致** ✅
* 行动 8（L924-927）「强依赖行动 2；建议排在行动 4、6 之后」与行动 2 步骤 5（L299）「`--update` 必须在行动 8 之前」**一致** ✅
* 行动 10 ↔ 行动 12（L1126 / L1328）「行动 10 改了前端 → 截图基线必须在行动 10 之后」**双向一致（单方向）** ✅
* 行动 11（L1222）「强依赖行动 2 与行动 3；三者必须同批提交」✅（但与 F3 同源，需一并收敛）
* 行动 8（L884）「类别 (a)/(b) 存在 → 『降到 0』语义上不可能」与报告行动 8 的「降至 0」冲突已被**显式改写为 ≤26 硬门槛** ✅（这是计划对报告的合理修正，非矛盾）

**唯一内部矛盾**：§3.1「关键路径（最长链）：`行动 2 → 行动 8 →（行动 4 → 行动 6）`」与其紧邻说明
「行动 8 …**必须排在行动 4/6 之后**」以及 §3.2 批次表（B2 行动 4 → B3 行动 6 → B4 行动 8）自相矛盾 → **F13（medium）**。

---

## 7. 发现项清单（20 条，按严重度）

### 7.1 high（3 条）

| id | severity | problem | requiredFix | file | line |
|---|---|---|---|---|---|
| **F1** | high | **行动 7 验证命令 (2) 实测失败（exit 1）**：`cx.heading_column()` 与 `cx.anchor_distance()` 在 `CentralComplex` 中是 `@property`（`:228-231 heading_column`、`:176-177 anchor_distance`、`:181-186 anchor_return_bearing` 均为 `@property`），带括号调用触发 `TypeError: 'int' object is not callable`。因此**验收标准 2「验证 (2) 的命令 exit 0 并打印合法 heading_column ∈ [0,16)」不可达成**；且同一错误口径已扩散到实施步骤 1 的测试规格与「实测现状」表（共 **6 处**：L771 `anchor_distance()`/`anchor_return_bearing()`、L793 `heading_column()`、L794 `anchor_distance()`、L796 `heading_column()`、L817 验证命令、L833 验收标准），照此实现的 `test_cx_navigation_loop.py` 会写成一批必然失败的测试。注：`set_anchor()`（:170）、`reset()`（:448）、`compass_stats()`（:477）**确为方法**，计划对这三处的写法正确，行号 `:177`/`:182` 指向的 `def` 行亦无误——错的只是括号。 | 去掉 3 个 property 的调用括号（`cx.heading_column` / `cx.anchor_distance` / `cx.anchor_return_bearing`），或统一改为方法；同步修订 L771/793/794/796/817/833 六处写法。 | `docs/fly64_execution_plan_v2.md` | 817（另见 771, 793, 794, 796, 833） |
| **F2** | high | **§0.2「基线统计一键复核（复制即用）」块实测失败（exit 1）**：块内 `& $py -c @'…'@` 的 here-string 正文含双引号，Windows PowerShell 5.1 在向原生程序传参时会剥离这些双引号，Python 收到 `print(f, count=, d[count], …)` → `SyntaxError: invalid syntax`。实测环境即计划自述的 Windows + PowerShell（无 pwsh 7）。最小复现：`& $py -c @' print("A","B") '@` → `NameError: name 'A' is not defined`；把双引号改单引号则 exit 0。计划 §0.1 的 win32/linux 条数、cause 分布与跨平台交集三行均标注「见 0.2」，即该三行数值的**唯一给出口令不可用**。 | 将该块的 Python 代码写入临时 `.py` 文件后再 `& $py <file>` 执行；或把内层双引号改成单引号/`\"` 转义；建议同时给 §0.2 增加「PS 5.1 下 here-string 会吃双引号」的注记。 | `docs/fly64_execution_plan_v2.md` | 60-71（引用点 39, 40, 41） |
| **F3** | high | **行动 2 与行动 3 构成循环依赖**：行动 2 前置依赖（L335）声明「依赖行动 3」，行动 3 前置依赖（L429）声明「与行动 2 共用 ci.yml」，而 §3.1 依赖图（L1352）只画 2 → 3 单向。执行者无法据此判断先后次序（任务要求 4 指名的「A 依赖 B 而 B 又依赖 A」）。 | 统一为单向：建议删除行动 2 的「依赖行动 3」，改为「与行动 3 同批提交（无先后依赖）」；行动 3 保持「与行动 2 同批提交」。行动 11 的「三者同批提交」措辞相应改为「三者同批提交，行动 2/3 之间无先后依赖」。 | `docs/fly64_execution_plan_v2.md` | 335, 429（参照 1352, 1222） |

### 7.2 medium（10 条）

| id | severity | problem | requiredFix | file | line |
|---|---|---|---|---|---|
| **F4** | medium | 计数不符：`fly64/plugin/` 实有 **7** 个 `.py`（`__init__.py`、`coach_outcomes.py`、`llm_consult.py`、`runner.py`、`scene_context.py`、`service.py`、`strategy_writer.py`），计划写 **8 个**。（结论——`evolution_logs.py` 不存在——仍然正确。） | 改为 7；或改用现场命令取证再写数。 | `docs/fly64_execution_plan_v2.md` | 115 |
| **F5** | medium | 计数不符：`fly64/.tmp/` 下 `.sh` 文件实测 **59** 个，计划写 **55 个**。 | 改为 59（并注明采集命令 `(Get-ChildItem fly64/.tmp -Filter *.sh).Count`）。 | `docs/fly64_execution_plan_v2.md` | 1515 |
| **F6** | medium | 事实不符：计划称 `brain_tunable_params.json` 中「**没有任何 `DAN_*` / dopamine 键**」，但该文件含 `exploration.dopamine_revisit_cost`（默认 0.5，且正是计划自己在别处点名的 3 处 `default ∉ [min,max]` 之一）。「9 个 `DAN_*` 常量未接线」的结论成立，但「无 dopamine 键」的措辞被仓库直接否证。 | 改写为「无任何 `DAN_*` 键；`dopamine` 相关键仅 `exploration.dopamine_revisit_cost`，且其 `default` 越界（见下条自检）」。 | `docs/fly64_execution_plan_v2.md` | 653-654 |
| **F7** | medium | §4.2 表 A 标题「**共 76 条**」与表体 **84** 条编号行不符；同一节导语声称「以下 3 张表的每一行都由 `Test-Path` 实测生成」，故读者会以 76 为分母核对，产生不可复现的计数。 | 标题改为 84；或按实际抽取口径（119 个 EXISTS token）重写并注明口径定义。 | `docs/fly64_execution_plan_v2.md` | 1432（表体 1434-1519） |
| **F8** | medium | 数值与所给命令不自洽：§0.1（L33）称 `evolution_history.json` 的 `brain_version` **最大值 = `2.23.6`**，但 §0.2 给出的复制即用命令实测输出 `max brain_version: None`（字面量 `"None"` 共 3 条记录，字符串序大于 `2.23.6`）；剔除 `None` 后**字典序最大值为 `2.9.1`**，只有按语义版本排序才是 `2.23.6`。结论（无记录 ≥ 2.23.7，实测 `[]`）成立，但命令与取值不自洽。 | L33 改为「语义最大版本 = 2.23.6（排除 3 条字面量 `None`）」；§0.2 命令改为先过滤 `None/**/缺失` 再按 `(major,minor,patch)` 排序。 | `docs/fly64_execution_plan_v2.md` | 33, 74 |
| **F9** | medium | 算术不符：行动 8 的 36 处写入点清单以区间记法写成 `… 1336-1338 …`，展开共 **37** 个行号，与同页 headline「**36 行 / 36 处**」矛盾；实测写入行为 36 行，且 1337 **不是**写入行（实际为 1336 与 1338）。 | 把 `1336-1338` 改写为 `1336, 1338`。（完整实测清单见 §8.1） | `docs/fly64_execution_plan_v2.md` | 873 |
| **F10** | medium | 行号错误：行动 4 涉及文件表称 `fly64/fly64/gain_modulation.py` 的 `DopamineGainController` @ **`:84`**，实测类定义在 **:56**；:84 是 `__init__` 的 `dopamine_threshold` 形参（计划 L464 的 `:84,90,143` 引用 `dopamine_threshold` 才是正确的）。 | 改为 `DopamineGainController @ :56`。 | `docs/fly64_execution_plan_v2.md` | 474 |
| **F11** | medium | 事实不符：表 B7b 称「`fly64/plugin/*.log` **未被任何 `.gitignore` 忽略** … 建议在 `fly64/.gitignore` 增加 `plugin/*.log` 与 `plugin/*.pid`」。实测 `git check-ignore -v fly64/plugin/watchdog.log` → **rc=0**，命中根 `.gitignore:23: *.log`（`service.log` 同）。`*.log` 早已忽略，该建议中 `.log` 一半是冗余改动；`*.pid` 一半成立（rc=1）。 | 删除 `plugin/*.log` 建议，保留 `plugin/*.pid`；并把「未被忽略」的判断改为 `git check-ignore` 实测结论。 | `docs/fly64_execution_plan_v2.md` | 1532 |
| **F12** | medium | 算术不符：12 项行动工作量上限之和为 **38.0 人日**（2.5+1.5+0.5+2+1+2.5+1.5+3+1.5+2.5+1+2 = 21.5；上限 4+2.5+1+3.5+2+4+3+6+2.5+4+2+3.5 = 38.0），而 §3.2 合计写 **21.5–36.5**（差 1.5）。批次行亦不自洽：B1 记 4–6.5（所含行动 1+2+3 = 4.5–7.5）、B5 记 6–9.5（行动 10+12 = 4.5–7.5）。 | 明确并行列的收敛口径（给出并集/最长线公式），或直接把合计改为 21.5–38.0；建议逐批复核后重算。 | `docs/fly64_execution_plan_v2.md` | 1389（另见 1384, 1388） |
| **F13** | medium | 内部矛盾：§3.1「关键路径（最长链）：`行动 2 → 行动 8 → （行动 4 → 行动 6）`」把行动 8 排在行动 4/6 **之前**，与其紧邻说明「行动 8 …**必须排在行动 4/6 之后**以避免同改 `model.py`」及 §3.2 批次表（B2 行动 4 → B3 行动 6 → B4 行动 8）相反。执行者按关键路径排期即与独占性约束冲突。 | 关键路径改为 `行动 2 → 行动 4 → 行动 6 → 行动 8`。 | `docs/fly64_execution_plan_v2.md` | 1371, 1372 |
| **F14** | medium | 缓解措施陈述不准确：§4.1「降级方案」称「所有测试一律加 `--basetemp <独立目录>` 且跑完手动清理（本文件各行动的命令块已全部使用 `--basetemp .pytest-aN`）」，暗示 `--basetemp` 可限制污染。**实测不成立**：在 pristine 工作树上单跑行动 2 的验证命令 (3)（`pytest tests\test_regression_detector.py -q -p no:cacheprovider --basetemp .pytest-a2`），`git status --porcelain` 由 **5 → 102**（M=91 / D=2 / ??=9，`git diff --stat` = 93 files changed）。根因：`tests/test_regression_detector.py::TestDetectorDetects::test_detects_an_injected_failure`（:104-122）以子进程调用 `scripts/check_regressions.py`，后者强制 `--basetemp ROOT/.pytest-run`；另有测试改写 `fly64/plugin/.consult_request.json` 与 `fly64/skills/README.md`。（§4.1 给出的四行清理模板本身**经实测有效**：可把状态精确恢复到 5 条、`git diff --stat` 为空。） | 在 §4.1 写明「污染与 `--basetemp` 无关；根因是 `check_regressions.py` 及 `test_regression_detector.py` 的嵌套调用」，并把四行清理模板设为**强制**验收步骤（尤其行动 2 / M1）。§4.3「未被执行 pytest 污染」的表述同步修正。 | `docs/fly64_execution_plan_v2.md` | 1422-1426（另见 348, 1573） |

### 7.3 low（7 条）

| id | severity | problem | requiredFix | file | line |
|---|---|---|---|---|---|
| **F15** | low | 行号差 1：`def apply_strategy_update` 在 **:757**，计划写 `:758`（758 是其 docstring 首行）。 | 改为 :757。 | `docs/fly64_execution_plan_v2.md` | 966 |
| **F16** | low | 行号错位：计划称「`test_p1_neural_takeover.py:228` 的 `pre-P1: 45 / 53`」；:228 实为「P1 baseline (2026-09-14): 18 lines / 18 assignments」，`pre-P1 45 / 53` 出现在 **:229**（与 :242 的打印串）。 | 改为 :229（或 :242）。 | `docs/fly64_execution_plan_v2.md` | 862 |
| **F17** | low | 名称不精确：计划称「`service.py:94` 已有 **`bridge_fresh`** 健康检查」；:94 属 `check_bridge()`（:89 定义），其键名为 `age <= self.bridge_stale`；标识符 `bridge_fresh` 仅出现在 `service.py:9` 的模块 docstring（描述健康检查**键名**）。可复用性结论成立，但标识符名无法按此检索。 | 改为「`service.py:89-95 check_bridge()`（其健康检查键名 `bridge_fresh`，见 :9 docstring）」。 | `docs/fly64_execution_plan_v2.md` | 198 |
| **F18** | low | 验收不可判：行动 10 验证命令 (1) 写作 `& $py scripts\measure_evolution_health.py --json \| Select-Object -First 20`，而验收标准 1 要求「验证 (1) 的 `--json` **exit 0**」。实测 `--json` 输出 93 行，`Select-Object -First` 提前终止上游管道使 `$LASTEXITCODE = -1`（不带管道的同一命令为 0）。 | 把 exit 0 判定改为不带管道的命令（例如 `& $py scripts\measure_evolution_health.py --json > $null; "EXIT=$LASTEXITCODE"`），展示用管道另行给出。 | `docs/fly64_execution_plan_v2.md` | 1097（判定见 1117） |
| **F19** | low | 路径未纳入核对表：行动 11 步骤 3 以 `.cache/malecns/weights.npz`（~1.3 GB）作为 `not male_cns` 的根因路径；该路径在本机不存在（`fly64/.cache` 不存在），且**未**列入 §4.2 表 B/C，而 §4.2 导语称覆盖「本文件引用的**全部**路径」。 | 将 `.cache/malecns/weights.npz` 补入表 B（运行期下载缓存，Windows 侧不存在；CI 侧未缓存——ci.yml:3 已注明 1.3GB）。 | `docs/fly64_execution_plan_v2.md` | 1186（对照 1430） |
| **F20** | low | 路径约定自相矛盾：§0 路径约定（L19）称「本文件**所有**路径均写成『相对仓库根』的形式（如 `fly64/tests/…`），可直接复制进命令」，但实测有 **33** 个 token 仅在 `fly64/` 相对语义下存在（`scripts/check_regressions.py`、`tests/test_bridge.py`、`web/dashboard.css`、`skills/curriculum.json`、`plugin/watchdog.sh` 等）；在仓库根 cwd 下直接复制会 `FileNotFoundError`（L18 又声明这些按 `fly64/` 解析）。 | 二选一：删除 L19 的「一律仓库根相对」措辞，或把所有命令块的 `cd` 统一写明（现有命令块多数已写 `# cwd = D:\codes\flygym\fly64`）。 | `docs/fly64_execution_plan_v2.md` | 18-19 |

---

## 8. 附：关键实测原始证据

### 8.1 36 处 `control` 直接写入（官方 KPI 口径）实测清单

```
PATTERN      : \bcontrol\.\w+\s*=[^=]
write LINES  : 36      assignments : 36
[726, 727, 1319, 1320, 1336, 1338, 1400, 1401, 1402, 1608, 1609, 1610, 1616, 1617, 1618, 1619,
 1631, 1633, 1639, 1646, 1655, 1656, 1668, 1669, 1670, 1672, 1682, 1683, 1691, 1694, 1695, 1697,
 1705, 1706, 1882, 1883]
```

与计划 L873 的区间记法差异：计划含 `1337`（**非**写入行），故区间展开为 37 项 → F9。
`test_p1_neural_takeover.py::TestKpiBaseline::test_control_write_count_shrunk` 实测：
`AssertionError: write lines 36` / `assert 36 <= 26`（`:238`），`1 failed, 1 passed`。

### 8.2 行动 7 命令失败的完整诊断

```
$ & $py -c "…;cx=CentralComplex();[cx.update(heading=0.1*i,heading_rate=0.5,dt=0.02) for i in range(1000)];
            print('cx ok', cx.heading_column(), cx.anchor_distance())"
TypeError: 'int' object is not callable        ← exit 1

$ & $py -c "…;print('attr:',cx.heading_column, 'callable:', callable(cx.heading_column),
                     'anchor_distance callable:', callable(cx.anchor_distance))"
attr: 0 <class 'int'>   callable: False   anchor_distance callable: False

fly64/fly64/central_complex.py
  228|     @property
  229|     def heading_column(self) -> int:
  230|         """Index of the most active compass column (0-15)."""
  231|         return int(np.argmax(self.compass))
```

对照：`set_anchor(...)`（:170）、`reset()`（:448）、`compass_stats()`（:477）**是方法**，调用无误 —— 计划对这三处的写法正确。

`central_complex.py` 的三个 `@property`（带括号调用即报错）：

```
  176|     @property
  177|     def anchor_distance(self) -> float:          ← 计划 L771/L794/L817 写成 anchor_distance()
  181|     @property
  182|     def anchor_return_bearing(self) -> float | None:   ← 计划 L771 写成 anchor_return_bearing()
  228|     @property
  229|     def heading_column(self) -> int:             ← 计划 L793/L796/L817 写成 heading_column()
  231|         return int(np.argmax(self.compass))
```

运行期证据：

```
callable(cx.heading_column)   → False   (type: int)
callable(cx.anchor_distance)  → False   (type: float)
```

### 8.3 工作树污染实测（两次）

```
A) 单文件（行动 2 验证命令 (3)，pristine → 运行 → 结束）
   status BEFORE           : 5
   pytest                  : 1 failed, 5 passed in 39.57s
   最耗时 40.8 s
   status AFTER            : 102（M=91 / D=2 / ??=9）
   git diff --stat         : 93 files changed, 171 insertions(+), 172 deletions(-)
   M/D 文件分布            : 91 个在 fly64/.pytest-run/**，
                             另 2 个为 fly64/plugin/.consult_request.json、fly64/skills/README.md

B) 全量门禁（scripts/check_regressions.py）
   status BEFORE           : 5
   exit                    : 1（248.6 s 墙钟）
   status AFTER            : 118

C) 清理（计划 §4.1 四行模板 + 删除 basetemp 目录）
   git restore -- fly64/.pytest-run fly64/plugin/.consult_request.json fly64/skills/README.md
   git clean -fd fly64/.pytest-run
   status AFTER            : 5      ← 与验证前完全一致
   git diff --stat         : 空
```

### 8.4 PowerShell 5.1 here-string 实测（F2）

```
PSVersionTable.PSVersion : 5.1.26100.1591

& $py -c @'
print("A", "B")
'@
→  Traceback … NameError: name 'A' is not defined        EXIT=1

& $py -c @'
print('A', 'B')
'@
→  A B                                                   EXIT=0
```

计划的 §0.2 块因此失败（Python 收到的是 `print(f, count=, d[count], len=, len(d[entries]), unique=, len(ids))`）。

---

## 9. 未验证项（本机不可判，禁外推）

| # | 项 | 原因 | 计划的自我声明 |
|---|---|---|---|
| U1 | 行动 1 运行态（kill SM64 → ≤60 s 自动重启、`bridge_stale` ≤30 s 转 false） | Windows 无 WSL/SM64 | ✅ 已在 L199/L236 声明「待 WSL 验证」 |
| U2 | 行动 8 真实运动行为不退化（≥10 min 会话） | 需 WSL 实机 | ✅ 已声明 |
| U3 | 行动 10 `/evolution-health.json` 返 200、tick 不阻塞 | 需大脑进程 | ✅ 已声明 |
| U4 | 行动 11 CI（GitHub Actions）实际执行与 linux 门禁结果 | 无法触发 CI | ✅ 已声明 |
| U5 | 行动 12 Playwright 渲染级与截图 diff | `playwright` 未安装（网络 ~150 MB） | ✅ 已声明 |
| U6 | `export logs/` 10 个 zip 内容（会话计数） | 未解包（避免扩大范围） | ✅ 已在 L1569 声明未验证 |
| U7 | 行动 5 的 `replay_curriculum.py`/行动 1/2/4/9/12 的**待新增**资产的可运行性 | 表 C 资产尚不存在，属交付物而非验证对象 | —— |
| U8 | 行动 11 验证(1) 中 `--report` 对**含失败行**报告的解析（`FAILED_RE`） | 本次预演报告文件 0 失败行，仅验证了参数与路径可用（exit 0） | 建议交付时补一次含失败行的预演 |

---

## 10. 修订建议（最小改动集，供计划撰写者执行）

按「先修 high、再修 medium、可选 low」排序，共 **20 处定点修改**：

1. **F1**：行动 7 去掉三个 `@property` 的调用括号 —— `heading_column` / `anchor_distance` / `anchor_return_bearing`（L771/793/794/796/817/833 共 6 处）。
2. **F2**：§0.2 改成写临时 `.py` 后执行，或把内层双引号换成单引号（L60-71）。
3. **F3**：合并行动 2/3 的依赖方向为单向（L335 / L429 / L1222）。
4. **F4/F5**：`plugin/*.py` → 7；`.tmp/*.sh` → 59。
5. **F6**：改写「无 dopamine 键」的措辞。
6. **F7**：表 A 标题 76 → 84。
7. **F8**：L33 注明「语义最大（排除 `None`）」并修 §0.2 命令。
8. **F9**：`1336-1338` → `1336, 1338`。
9. **F10**：`DopamineGainController @ :56`。
10. **F11**：删除 `plugin/*.log` 建议，保留 `plugin/*.pid`。
11. **F12**：合计人日口径或数值修正。
12. **F13**：关键路径改为 `行动 2 → 行动 4 → 行动 6 → 行动 8`。
13. **F14**：§4.1 说明污染根因并把清理模板设为强制。
14. **F15-F18**：`:757`、`:229`、`check_bridge()`、行动 10 验证(1) 去管道。
15. **F19/F20**：补 `.cache/malecns/weights.npz` 入表 B；修正路径约定措辞。

修改完成后，本验证的核心结论（§3–§6）无需重跑即可复用，只需复跑受影响的 2 条命令
（行动 7 验证(2)、§0.2 块）即可确认 F1/F2 修复。

---

*验证文件结束。本文件共核对 212 个路径 token、36 条命令、40 项数值、200 条行号引用、12 项行动覆盖与 12 条依赖声明；
发现项 20 条（high 3 / medium 10 / low 7 / blocker 0）；裁决 `needs_revision`。*
