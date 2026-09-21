# 01 — 报告论断核对与偏差清单（T1）

> 任务：t2 [T1] — 报告论断核对与偏差清单
> 执行者：repo-auditor
> 被核对对象：`docs/fly64_export_logs_analysis_report.md`（314 行，实测）
> 基准：(A) `docs/analysis/plan-v2/00-facts.md` 的 T0 实测事实；(B) 本次为 T1 新做的仓库实测
> 命令工作目录：`D:\codes\flygym`（除标注 `cwd=fly64/` 者）
> 解释器：`D:\codes\flygym\.venv\Scripts\python.exe`（Python 3.11.9 / sys.platform=win32）
> **本任务只做核对，未改动任何代码或既有文档**（唯一新增文件 = 本文件）
> 采集时间：2026-09-20

---

## 0. 核对结论摘要

| 类别 | 数量 | 说明 |
|---|---|---|
| 核对条目总数 | 32 | 覆盖任务指定的全部要点 + 逐项路径/API 验证 |
| 判定「一致」 | 12 | 包括 `agent.md` 1360 行、79 条记录、三脚本存在与 CLI、seqlock 看门狗链路 |
| 判定「偏差」 | 14 | 其中 **high 5 / medium 5 / low 3 / info 1** |
| 判定「本次未验证」 | 6 | 常驻进程存活、WSL 侧状态、会话内统计、LSP、可视化截图等 |
| 新发现（报告未覆盖，影响计划 v2） | 6 | 其中 2 项为 high（版本表漏 17 个版本；`fly64_execution_plan.md` 大量幻象 API） |

**一句话结论**：报告的数字大多**不是随手编的，而是取自更早快照后被冻结**——例如「36 条基线」精确等于 `EVO-068` 记录中的 `environment 13 / aspirational 15 / real-bug 5 / test-drift 3` 之和，而基线文件在 `EVO-071 follow-up` 那次提交里已被刷新为 win32 38 / linux 24。因此偏差清单里的 high 项，本质是**「报告快照过期」而非「报告虚构」**，但用于写计划 v2 时必须按实测值回填。唯一**真正的结构性缺陷**出现在既存的 `docs/fly64_execution_plan.md`：它围绕多处**在仓库中零实现的 API**（`CoachContract`、`learn_from_outcome`、`record_danger`、`navigate_to_goal`、`EvolutionLogger`、`control_written`、`--mode trace`）写了大段修改步骤。

---

## 1. 主偏差清单（报告声明 | 实测值 | 证据 | 等级 | 影响）

> 行号均为**实测**行号（Python `read_text().splitlines()`）。等级定义：
> **high** = 数字或路径错误会直接导致下游行动写错验收基线；**medium** = 事实性错误但不动摇主线结论；**low** = 不影响执行的表述问题；**info** = 仅记录。

### 1.1 脑版本与版本线

| ID | 报告声明 | 实测值 | 证据（文件:行 / 命令） | 等级 | 影响 |
|---|---|---|---|---|---|
| R-01 | L4「脑版本演化史（79 条记录，Brain v1.0.0→v2.23.6）」；L149「最新记录为 t17（Brain v2.23.6, Skill 3.4.2）」 | **`main.py` 的 BRAIN_VERSION = `"2.23.11"`**；`evolution_history.json` 的 canonical = `2.23.6`，其最大 `brain_version` 也是 `2.23.6` | `fly64/fly64/main.py:39`：`BRAIN_VERSION = "2.23.11"  # R31-fix12: ...`；`fly64/skills/evolution_history.json` → `canonical_versions = {"brain":"2.23.6","skill":"3.4.2","as_of":"2026-09-18T01:08:22+08:00"}`；命令 `Select-String -Path fly64\fly64\main.py -Pattern 'BRAIN_VERSION'` | **high** | 任何以「当前脑版本 2.23.6」为前提的行动/验收表都错；正确值 2.23.11 |
| R-02 | 未提及 `skills/skills.md` 的版本徽章 | `skills.md:3` 写 **2.23.7**，`skills.md:70` 写 **2.23.10**，同一文件自相矛盾，且两者都不等于 `main.py` 的 2.23.11 | `fly64/skills/skills.md:3`、`:70`（命令 `Select-String -Path fly64\skills\skills.md -Pattern 'BRAIN_VERSION \*\*'`） | **high** | agent.md 规则 8「版本三处同步（强制契约）」实测不成立；v2 若要恢复该契约，须先决定 canonical 值 |
| R-03 | L4/L149 暗示 79 条记录已覆盖到最新版本 | `2.23.7 / 2.23.8 / 2.23.9 / 2.23.10 / 2.23.11` **在 `evolution_history.json` 中零记录**（全仓库 grep 仅命中 `main.py`、`skills.md`、`docs/fly64_execution_plan.md`） | `Get-ChildItem fly64,docs,scripts -Recurse -Include *.py,*.json,*.md | Select-String -Pattern '2\.23\.(7\|8\|9\|10\|11)'`；`evolution_history.json` 中 brain ≥ 2.23.6 仅 3 条（EVO-069/070/071） | **high** | agent.md 规则 15「禁止无记录的版本递增」实测不成立（≥5 个未记录版本）；v2 的 P0/P1 应含「补记录或回退版本号」 |
| R-04 | L149「共 79 条演化记录，**51 个唯一脑版本**」 | **两数字均成立**（79 条记录；51 个唯一 `brain_version` 字面量），但 51 中含字面量字符串 `"None"`（3 条记录）与 `"1.0.x"`/`"2.11.x"`，**语义唯一版本 = 50** | `fly64/skills/evolution_history.json`（json 统计脚本，见 §4.1）；`brain_version` 取值全表见本文件 §4.2 | low | 表述精度问题；使用「50」更严谨 |
| R-05 | L109–L147 的版本总览表 | 表内 **34 个** brain 版本；`evolution_history.json` 的 51 个唯一值中**有 17 个不在报告表内**，其中 **`2.14.0`–`2.21.1` 共 14 个真实存在但被漏掉**（含 `2.15.0`/`2.16.0`/`2.17.0` Motor-P2..P4、`2.19.3` 运维收敛、`2.20.0` v2.20.0 发布、`2.20.3` R31-fix3、`2.20.4` R31-fix4、`2.21.0` t6 根因修复、`2.21.1` R31-fix5） | 命令见 §4.2；证据记录 `evolution_history.json` 中 `2.14.0 | skill 3.0.0 | brain | Motor-P1` 等 21 条 | **high** | 报告的「脑版本演化旅程」在 v2.13.3 → v2.22.0 之间**是断层的**；任何「从报告版本表推导的演化轨迹」都会遗漏 Motor-P1~P5 与 R31-fix3~5 整段 |
| R-06 | L4/L21「覆盖 ~2026-09-11 至 2026-09-20 约 9 天」 | `evolution_history.json` **无任何记录晚于 2026-09-18**（`canonical_versions.as_of = 2026-09-18T01:08:22+08:00`）；且 79 条中只有 63 条含 `date`、16 条含 `recorded_at` | json 字段频次统计（T0 §8 N2） | medium | 时间跨度被高估 2 天；「最新记录」实为 EVO-071 (2026-09-18) |
| R-07 | L160「R31 修复链（v2.22-v2.23）」 | 实测 `main.py:39` 注释为 **`R31-fix12`**，而历史记录中 R31 系列最新为 `2.21.1 = R31-fix5`、`2.22.0 = t9-A`、`2.23.2 = R31-fix6`…`2.23.6 = R31-fix9` | `fly64/fly64/main.py:39`；`evolution_history.json` 的 `round` 字段 | medium | R31 链实际延伸到 fix12，报告只到 fix9（=2.23.6），漏 3 环 |

### 1.2 测试基线（任务重点）

| ID | 报告声明 | 实测值 | 证据 | 等级 | 影响 |
|---|---|---|---|---|---|
| R-08 | L226「总测试用例 ~482 通过 / 11 基线失败（Windows 环境）」 | **929 passed / 38 failed / 36 skipped**（216.43 s） | `cwd=fly64/`：`python scripts\check_regressions.py` → 末行 `pytest: 38 failed, 929 passed, 36 skipped in 216.43s (0:03:36)`（T0 §6） | **high** | 通过数被低估 47%，失败数被低估 71%；任何以「482/11」为验收基线的行动都不可用 |
| R-09 | L228「基线管理 tests/known_failures.json —— 36 条基线（13 env + 余下分类）」 | win32 基线 **38 条**（`count` 字段 = `len(entries)` = 38）；分布 `aspirational 16 / environment 14 / test-drift 3 / real-bug 2 / unknown 3`；linux 基线 **24 条**（`aspirational 16 / environment 1 / live-state 2 / test-drift 3 / unknown 2`） | `fly64/tests/known_failures.win32.json:4`（`"count": 38`）、`fly64/tests/known_failures.linux.json:4`（`"count": 24`）；统计命令见 T0 §3 | **high** | 「36 条 / 13 env」是冻结快照（见 §2），实测应为 38/24、env=14/1 |
| R-10 | L252「### 4.4 已知基线失败（36 条）」+ 表「Windows 环境 13」 | 同上：38 条；environment **14** | 同上 | **high** | 同上 |
| R-11 | L170「回归基线 \| v2.23.5 \| 36 条已知失败基线分类管理」 | 同上 38/24 | 同上 | medium | 里程碑表数字过期 |
| R-12 | L238「LSP 状态 \| 11 基线失败（均为 Windows 环境问题：clock_gettime_ns/invariants/retina）」 | 失败 38 条，其中 environment 类 **14** 条；且 environment 类中 **9 条在当前主机已通过**（6 条 `test_bridge.py::*` + 2 条 `test_retina.py::*` + 1 条 `test_invariants.py::test_torn_frames_*`） | `check_regressions.py` 输出的「baseline entries that now PASS」段（T0 §6）；json 交叉统计 `Counter({'environment': 9, 'unknown': 1})` | **high** | ①「11」错；②「均为 Windows 环境问题」错——基线内含 `aspirational 16 / real-bug 2 / test-drift 3 / unknown 3`，其中 **real-bug 2 条是真缺陷**（`test_launcher_lock_blocks_duplicate`、`test_flow_computation_performance`），把它归入「环境问题」会掩盖真实缺陷 |
| R-13 | L294「基线 11 失败可根治」 | 38 failed | 同 R-08 | high | 同上 |
| R-14 | L228/L249 把基线文件写作 `tests/known_failures.json` | 实际为**平台作用域双文件** `tests/known_failures.win32.json` 与 `tests/known_failures.linux.json`；**未限定名的 legacy `fly64/tests/known_failures.json` 不存在**（`Test-Path` → `False`） | `Test-Path fly64\tests\known_failures.json` → `False`；`git ls-files` 命中两个 scoped 文件；`fly64/scripts/check_regressions.py:41-54` 的 `baseline_path()` 优先 scoped | medium | 路径名过期（legacy 名在 `check_regressions.py:13` 文档串与 `test_regression_detector.py:8/62` 中同样残留）；按字面 `open('tests/known_failures.json')` 会 FileNotFoundError |

### 1.3 代码质量与基础设施声明

| ID | 报告声明 | 实测值 | 证据 | 等级 | 影响 |
|---|---|---|---|---|---|
| R-15 | L167「去 Python 化 \| v2.8.0 \| main.py 写 control **35→12 处**」；L236「main.py 直接写 control \| **~12 处**（从 35 处下降）」；L286「从 ~12 处降至 0…P1 进化轮（2.8.0）已移除 23 处」 | **36 行 / 36 处赋值**；官方 KPI 预算 `KPI_LINES = KPI_ASSIGNMENTS = 26`，当前**超标 10**，对应测试实测 **FAIL** | 判据 `fly64/tests/test_p1_neural_takeover.py:230-231`（预算 26）、`:236-239`（正则 `\bcontrol\.\w+\s*=[^=]`）；实测 `python -m pytest fly64\tests\test_p1_neural_takeover.py -k control_write_count_shrunk` → `AssertionError: write lines 36 / assert 36 <= 26` | **high** | ①「12」错 3 倍；②报告自身 L286 说「移除 23 处」→ 35−23=12，与 L167 自洽，但与实测 36 矛盾；③**行动 8「写 control 清零」的起点必须改为 36，且第一步应是"回到 26 预算内"而非直接清零** |
| R-16 | L236「~12 处（从 35 处下降）」的历史数字来源 | 仓库中**唯一**可实测的 P1 KPI 预算轨迹是 `fly64/scripts/ver_append_r24.py:37`（`P1 直写 KPI 预算化（18→26 附豁免表）`）；`test_p1_neural_takeover.py:228-229` 另记 `pre-P1: 45 / 53`、`(2026-09-14): 18 lines / 18 assignments`。**「35 处」在仓库中无可核验出处** | `Select-String` 全仓 `control.{0,20}(35\|12)\s*(处\|site\|line)` → 仅命中报告自身 L167/L236/L286 | medium | 「35」疑似引自导出会话聊天文本；v2 引用历史数字时应改用可核验的 `18 → 26` 口径 |
| R-17 | L167/L239「P1 进化轮（2.8.0）已删除 11 个 A 类旁路点」 | **成立**：`EVO-019` 记录 `["删除 11 处 A 类 Python 旁路（A1-A9/B10/C10）", ...]`，brain_version = `2.8.0` | `fly64/skills/evolution_history.json` → EVO-019 | 一致 | — |
| R-18 | L245「WSL 自治服务 \| ✅ 常驻运行（plugin.service watchdog 监控）」 | **代码层成立，运行态本次未验证**。证据：`fly64/plugin/service.py`（355 行 pwsh 计数 / 实际 16 466 bytes）存在；`fly64/plugin/watchdog.sh`（2549 bytes）实测存在，其逻辑为「pid 文件 + `kill -0` 活性探测 → `nohup` 重启 service → 连续失败计数 `MAX_FAILS=3` 后写 `ALERT`」，设计为 cron/systemd-timer 每分钟驱动；`fly64/scripts/consolidate.sh:89-119` 亦负责重启自治服务 | `Test-Path fly64\plugin\watchdog.sh` → True；`plugin/watchdog.sh` 全文（本文件 §5.1） | 部分一致 | **「✅ 常驻运行」是运行态断言，在 Windows 上无法验证**（需 WSL/进程表）；代码层已验证。v2 的验收不应照抄「✅」 |
| R-19 | L246「存活监控 \| ✅ seqlock 看门狗 + stale 徽章」 | **成立（代码层全链路打通）**：`SeqlockWatchdog`（`bridge.py:56-83`，`stale_after` 默认 5.0 s）→ `SharedBridge.stale` 属性（`:111-114`）→ `read_frame` 每 tick 喂 seq（`:145`、`:148` 龙读分支）→ `main.py:2278` 发布 `"bridge_stale": bool(bridge.stale)` → `web/index.html:4` 元素 `id="bridgeStalePill"` → `web/dashboard.js:1110-1111` 控制显隐 → `web/dashboard.css:108-109` 样式 `.stale-pill` | `fly64/fly64/bridge.py:56,65-83,103,111-114,145,148`；`fly64/fly64/main.py:2278`；`fly64/web/index.html:4`；`fly64/web/dashboard.js:1109-1111`；`fly64/web/dashboard.css:108-109`；测试 `fly64/tests/test_seqlock_watchdog.py`（103 行 / 11 个 test） | 一致 | — |
| R-20 | L215「auto-restart 为已知待办但未实现」；L269 行动 1「**实现** SM64 冻结自动重启」 | **一致——且这是本次最强的可验证结论**：`bridge.stale` 只被**发布**，不被**消费**为重启动作。逐层实测：`plugin/service.py` 全文仅 4 处匹配 `sm64\|restart\|kill\|subprocess\|popen\|pkill`，其中唯一的 `kill` 在第 28 行是**文档串里的用法示例**（`kill $(cat plugin/fly64-service.pid)`），其余 3 处为路径/配置字符串；`plugin/runner.py` 仅 7 处匹配且无一为重启逻辑；`fly64/scripts/consolidate.sh` 的重启对象是**大脑**（`pkill -f "[f]ly64\.main"` → `setsid nohup python -m fly64.main`），触发条件是「**SM64 进程存活时**选 FULL 模式」，即**它假定 SM64 还活着**；全仓无任何 `auto-restart / respawn / restart_sm64` 实现 | `plugin/service.py`（仅 4 处匹配，第 28 行系文档串）；`plugin/runner.py`（7 处，无重启）；`fly64/scripts/consolidate.sh:24-27,56-58,72-74`；全仓 grep `auto.?restart\|respawn\|restart_sm64\|kill.*sm64` | 一致 | 行动 1 的**需求成立**，且是当前最高价值缺口（检测已就绪、动作缺位）。v2 可据此把行动 1 定为 P0 并给出明确落点：`plugin/watchdog.sh` 或新增 `plugin/sm64_watchdog.sh` |
| R-21 | L248「启动契约 \| ✅ consolidate.sh + setsid nohup」 | **成立**：`fly64/scripts/consolidate.sh:4-27` 有专门注释块说明启动契约（"勿删"），`:71-74` 与 `:109-112` 两处 `setsid nohup ... < /dev/null &` + `disown` | `fly64/scripts/consolidate.sh:4-27,71-75,109-113` | 一致 | — |
| R-22 | L247「仪表板 \| ✅ P0-P3 因果链 + P4-P6 后续」 | **部分成立，P4-P6 本次未验证**。已验证：`body.causal-off` kill-switch 真实存在（`web/dashboard.js:6,16`、`web/dashboard.css:8-9`）；`web/dashboard.js` 1408 行、`web/index.html` 88 行、`web/dashboard.css` 148 行。**未验证**：P4-P6 具体面板是否齐全（需逐面板核对，超出本次范围） | `fly64/web/dashboard.js:6,16`；`fly64/web/dashboard.css:8-9` | 部分一致/未验证 | 报告 L207 引用的「section.xxx-section 类选择器」本次未逐一核验 |
| R-23 | L206 修复轮次引用的 4 个短 commit：`661b939→a30dfbb→cd555f8→d9bd246` | 本次**未验证**（未逐一 `git cat-file` 校验；报告未给出仓库/分支上下文，且 4 个短 SHA 在 305 个提交中可能存在多义） | 未执行（明确记录为未验证，见 §6 U-05） | 未验证 | 低；如需引用应先 `git cat-file -t` 消歧 |

### 1.4 路径有效性（任务重点）

| ID | 报告声明 | 实测值 | 证据 | 等级 | 影响 |
|---|---|---|---|---|---|
| R-24 | L229 `scripts/check_regressions.py`；L230 `scripts/audit_contract_pairs.py`；L250 `scripts/measure_evolution_health.py`；L228/L249 `tests/known_failures.json` | 三个脚本路径**全部有效**——但**须相对 `fly64/` 解析**（仓库根为 `D:\codes\flygym`，代码子树为 `fly64/`）。即 `fly64/scripts/check_regressions.py`（177 行）、`fly64/scripts/audit_contract_pairs.py`（322 行）、`fly64/scripts/measure_evolution_health.py`（468 行）均存在。基线路径失效见 R-14 | `Test-Path fly64\scripts\<name>` → 三个 True；行数用 Python `splitlines()` | 一致（脚本）/ 偏差（基线名） | 报告**未给出路径解析规则**；v2 必须显式写明「`scripts/…` 与 `tests/…` 相对 `fly64/`」，否则照抄会在仓库根下找不到目录 |
| R-25 | 报告未声明脚本 CLI | 实测 CLI（详见 T0 §5）：`audit_contract_pairs.py` 仅 `--json/--all`（**无 `--mode`/`--target`**）；`check_regressions.py` 为 `--report/--strict/--update/--platform`；`measure_evolution_health.py` 为 `--phase6/--p44/--snapshot/--trend/--json` | 三个 `--help` 输出（T0 §5.1–5.3） | 未声明 | v2 引用脚本时必须附真实 CLI |

### 1.5 会话与里程碑

| ID | 报告声明 | 实测值 | 证据 | 等级 | 影响 |
|---|---|---|---|---|---|
| R-26 | L4/L21「全部 **7 个**已导出 DSH 会话」 | `export logs/` 实为 **10 个 zip / 9 个不同 session id**；报告点名的 7 个短 id 中，**只有 3 个在文件名中可对上**（`38542b1c`、`99cab60f`、`f953d3fd`），另 4 个（`a909a5cd`、`9e9d4023`、`047eec9d`、`493fe29d`）**不出现在文件名中** | 目录枚举 + 文件名正则（T0 §8 N1）；文件名里的 9 个完整 id：`1f8fbe04…`、`27ed0979…`、`38542b1c…`、`90dd512b…`、`99cab60f…`（2 个文件）、`b2eeed98…`、`d983cef5…`、`f953d3fd…`、`fdb47617…` | medium | 会话维度无法仅凭文件名复核；**未解包 zip**（解包会扩大范围并污染工作树） |
| R-27 | L107 「…和 gent.md（1360 行）提取…」 | 文件名拼写错误：应为 `agent.md`；**行数 1360 正确** | `fly64…\agent.md` 实测 1360 行 / 117938 bytes / 全 LF / 无 BOM（T0 §4）；仓库内仅此一份 `agent.md` | low | 拼写问题；⚠️ 但连同 R-28 一起说明：**用 PowerShell `Get-Content` 测同一文件会得到 921**，下游若用 PowerShell 复核会误判报告错误 |
| R-28 | L4「agent.md 规则体系（1360 行）」 | **成立**（1360 行） | 同上 | 一致 | 这是报告**最容易被误判为错误**的一条：T0 实测 PowerShell `Get-Content agent.md | Measure-Object -Line` = 921，Python `splitlines()` = 1360。差 439 行源于 UTF-8 中文在默认编码下的行识读。**结论：报告对，PowerShell 错** |
| R-29 | L226「新测试（自查）：test_spin_loop_fix 7、test_cliff_standoff 9、test_mbon_saturation 6、test_brain_alternation 9」 | 这几个文件的**存在性**本次未逐一核验（与报告主线不冲突）；但**与之相关的实测反证更强**：`test_mbon_saturation.py` 当前有 **3 条 NEW failures**（`TestMbonSaturationHomeostasis::test_mbon_returns_to_dynamic_range_after_scaling` / `test_saturated_column_scaling_fires` / `test_saturation_events_counter_increments`） | `check_regressions.py` 的 NEW FAILURES 段（T0 §6） | 未验证/存在反向证据 | 「新测试自查通过」的叙述与当前 3 条 NEW 失败并存；v2 应把 mbon_saturation 稳态测试列为**待归因项** |
| R-30 | L277 行动 4「场景识别→MB 学习闭环」参考「EVO R19 雏形已就」 | **部分可验证**：`MushroomBody`（`fly64/fly64/mushroom_body.py:42`）存在但其公开方法中**没有** `learn_from_outcome`（实测方法表：`encode / set_dopamine / set_adaptive_lr / update_weights / consolidate_anomaly_resolution / recall / …`）；全仓 grep `learn_from_outcome` **零命中** | 方法枚举脚本 + `Select-String -Pattern 'learn_from_outcome'`（全仓 0 命中，见 §6 U-04 相关说明） | medium | 行动 4 若照 `fly64_execution_plan.md` 的写法（在 `learn_from_outcome()` 末尾写信号）会直接不存在该函数；**必须先查明 MB 的真实学习入口再写计划** |
| R-31 | L245–L250「基础设施」整表 | 逐项见 R-18~R-22：**代码层 3 项一致（seqlock 看门狗、启动契约、度量工具）、1 项部分（仪表板）、1 项运行态未验证（自治服务常驻）、1 项路径名过期（基线）** | 见各条 | 混合 | 「✅」标记应改为「代码层已验证 / 运行态未验证」二分 |
| R-32 | L247「Phase 6」等术语表（L299–L314） | 术语定义与仓库用词一致（CX=CentralComplex 存在于 `fly64/fly64/central_complex.py:47`；Phase 6 = BrainMutator 管线，`measure_evolution_health.py:81 measure_phase6`）；**但 L312「P4.4 本能固化+课程晋级」中「课程晋级」在代码里称 stage/curriculum**（`skills/curriculum.json` 存在） | `fly64/fly64/central_complex.py:47`；`fly64/scripts/measure_evolution_health.py:81,162`；`Test-Path fly64\skills\curriculum.json` | 一致 | — |

---

## 2. 为什么报告会给出「36 条」——偏差根因（实测溯源）

这是本任务最有价值的发现：**报告的 36 不是编造的，而是一次真实快照的精确残留**。

`evolution_history.json` 中 `EVO-068` 记录（brain 2.23.5 / skill 3.4.1 / 2026-09-17，t15 验证基线）原文：

```
新增 tests/known_failures.json：36 条基线，**每条标注 cause 与证据 note**。
分类为 environment 13 / aspirational 15 / real-bug 5 / test-drift 3（0 未分类）
```

对照关系：

| 来源 | 总数 | environment | aspirational | real-bug | test-drift | unknown | live-state |
|---|---|---|---|---|---|---|---|
| `EVO-068` 记录（报告引用的快照） | **36** | **13** | 15 | 5 | 3 | 0 | — |
| `known_failures.win32.json`（当前实测） | **38** | **14** | **16** | **2** | 3 | **3** | — |
| `known_failures.linux.json`（当前实测） | **24** | 1 | 16 | 0 | 3 | 2 | **2** |

- **报告 L228 的「36 条基线（13 env）」= EVO-068 记录的数字，逐位相同**（36 = 13+15+5+3；13 env 亦相同）。⇒ 报告是**引用了一个当时的真实现状**，但该现状已被后续提交改写。
- 改写发生在 `d37c15ea92829e5934f688176b0202cf5d4c2442`（2026-09-18 16:08:05，`EVO-071 follow-up: compute_flow dead-code removal + performance threshold update`）——该提交同时改写了 `known_failures.win32.json` 与 `.linux.json`（`git log -1 --format=... -- <file>` 对两文件返回同一 commit）。
- `EVO-071` 记录自述的因果也吻合：**「修正了我自己对两处失败的误判（原记为 real-bug，实测均为 test-drift）」** —— 这正好解释 real-bug 由 5 降到 2，以及新增 `unknown 3`（引用 test 目录变更后待归类）。
- 另外 EVO-068 记录里的 `40 failed / 881 passed / 36 skipped → 36 failed / 881 passed / 36 skipped` 与报告 L226 的「~482 通过」也不一致；仓库中 `482 passed` 只在 `evolution_history.json` 更早的一条 `tests` 字段里出现过（`"TestConsultFrameSnapshot 4 用例，482 passed"`）。⇒ **L226 的「~482 / 11」是若干不同时期数字的拼接**，属**真正的时间错配**，不是快照残留。

**结论**：偏差分两类——
1. **快照过期**（可解释、非虚构）：R-09/R-10/R-11/R-14/R-04。
2. **数字错配或陈旧拼接**（无来源可解释）：R-08「482/11」、R-15「35→12」、R-12「11 且均为环境问题」。

---

## 3. `docs/fly64_execution_plan.md` 与报告 12 项行动的映射与冲突

### 3.1 先修正两个前置事实

| 项 | 任务描述给的写法 | 实测值 | 证据 |
|---|---|---|---|
| 行数 | 「v2.23.11，670 行」 | **676 行 / 20766 bytes**（Python）；PowerShell `Get-Content` 给 670 | `Path('docs/fly64_execution_plan.md')` 实测（T0 §4 同一现象） |
| 版本 | v2.23.11 ✅ | 一致（L4 与 L109 均写 `2.23.11`，并正确指向 `main.py` 第 39 行） | `docs/fly64_execution_plan.md:4,109` |
| 基线路径 | 任务描述称「其引用的 `fly64/tests/known_failures/` 路径并不存在」 | **正确地说是"部分引用"**：P2-9 的**文件路径标题**（L543-544）是**正确的** `fly64/tests/known_failures.{win32,linux}.json`，且**条数也正确**（L538 写「`.win32.json`（38 条）和 `.linux.json`（24 条）」）；**失效的是 L570 的验证命令**里那个目录式路径 `fly64/tests/known_failures/` | `docs/fly64_execution_plan.md:538,543,544,570,575,576`；实测 `python -m pytest fly64/tests/known_failures/ --collect-only -q` → `ERROR: file or directory not found` + **exit 4** |

> ⚠️ 因此对任务描述里的这条断言需要**收窄**：不是「该文档引用的 known_failures 路径不存在」，而是「**该文档的 P2-9 验证命令**用了不存在的目录路径」。**不应把一个正确的路径说成失效的**——这正是核对工作要挡住的错误。

### 3.2 12 项行动 → 映射关系（`docs/fly64_execution_plan.md` 自定义编号，与报告编号不同）

`fly64_execution_plan.md` **没有沿用报告的 1–12 编号**，而是自建 `P0-1/P0-2/P0-3/P1-4/P1-5/P1-6/P2-7/P2-8/P2-9/P3-10/P3-11/P3-12`（位置序号 1..12），且其中 2 项是该文档**自行提出**、报告中不存在的问题。

| 报告 # | 报告行动（L269–L295） | 执行计划条目 | 映射判定 | 冲突 / 事实问题（实测） |
|---|---|---|---|---|
| 1 | 实现 SM64 冻结自动重启 | **无对应条目** | ❌ **丢失** | 执行计划把它的两个"P0 槽位"给了自造的 P0-1/P0-2；报告唯一的 P0 行动（且实测需求成立，见 R-20）**在执行计划中完全消失** |
| 2 | 扩展回归基线（基线标记工具 + CI 环境全量分类） | 无直接条目（P2-9 仅"在 known_failures 中标记演化条目"） | ⚠️ 部分替代 | 报告的「扩展基线工具」被替换为「往基线里加 2 条演化条目」，**目标不同** |
| 3 | 契约审计制度化（audit 加入 WSL 部署后步骤） | P3-11「CI 集成 — 审计脚本加入 pre-commit」 | ⚠️ 部分对应 | P3-11 要求注册到 `pyproject.toml` 或 `.pre-commit-config.yaml` —— **两者实测均不存在**（`Test-Path` → False / False；`fly64/pyproject.toml` 亦不存在）。实际存在的是 `.github/workflows/ci.yml`（66 行，ubuntu-latest + Python 3.12，`working-directory: fly64`，且**未调用** `audit_contract_pairs.py`） |
| 4 | 场景识别→MB 学习闭环 | P1-4「场景→MB 学习闭环 — Pipeline 验证」+ P0-3「场景记忆交互」 | ✅ 对应（被拆成 2 条，且升为 P0） | **依赖幻象 API**：P1-4 要求在 `SceneMemory.record_danger()` 中实现、在 `scene_recognition.py:783` 附近调用 —— `record_danger` 全仓 **0 命中**；P0-3 要求在 `MushroomBody.learn_from_outcome()`（称 `mushroom_body.py:42`）末尾写合约 —— `learn_from_outcome` 全仓 **0 命中**（类号 42 正确，方法不存在） |
| 5 | 课程晋级端到端验证 | **无对应条目** | ❌ **丢失** | 报告称该里程碑"t16 已完成正向验证"（`EVO-070` 记录确实含 `improved=2 / qualifying=1 / stage 1→5` 实测），但执行计划未承接 |
| 6 | DAN 权重自动化 | **无对应条目** | ❌ **丢失** | — |
| 7 | CX 空间导航回路部署 | P2-7「CX 导航回路部署 — CentralComplex → MemoryController」 | ✅ 对应 | **依赖幻象 API**：`CentralComplex.navigate_to_goal()`、`MemoryController.store_navigation_hint()/recall_navigation_hint()`、`bridge.inject_navigation()` 全部 **0 命中**。（`CentralComplex`=`central_complex.py:47`、`MemoryController`=`memory.py:1733` 号数正确） |
| 8 | main.py 写 control 清零（从 ~12 处降至 0） | 无对应条目 | ❌ **丢失** | 且其前提数字「~12」实测为 **36**（R-15） |
| 9 | 教练通路契约测试 | P2-8「教练合约测试扩增」 | ⚠️ 对应但**建立在幻象上** | 要求写 `CoachContract()`、`coach.contract.is_active("implicit_advice")`、`coach.serialize()/deserialize()`、`scene_memory.set_danger(...)`、`contract.emit(...)`、`@contract.on(...)` —— 实测 `CoachContract` / `contract.emit` / `is_active` / `serialize` **全部 0 命中**；报告 L287 说的"t13 资产可复用"实际资产是 `plugin/strategy_writer.py` + `fly64/scripts/audit_contract_pairs.py` |
| 10 | 度量看板（Phase 6 收益仪表 + 排行榜） | 无对应条目 | ❌ **丢失** | 注：`measure_evolution_health.py` 已存在且可跑（T0 §5.3 实测 JSON），但"排行榜"未验证存在 |
| 11 | WSL 测试 CI | 无对应条目 | ❌ **丢失** | 实测已有 `.github/workflows/ci.yml`（ubuntu-latest/3.12），但**明确 `--ignore` 了 6 个测试文件并 `-k "not male_cns and not sm64"`**（L51-58）→ 与报告 L294「含 Windows 不可测项」的目标**并不等价** |
| 12 | CSS 契约测试 | 无对应条目 | ❌ **丢失** | — |
| — | （报告无此项） | **P0-1「SeqlockWatchdog.data_race — 空响应恢复」** | 🚫 幻象 | 该文件 L6-10 的 WARNING 块**已自我否证**："P0-1 描述的 `SeqlockWatchdog` API（`shutdown()`、`_state`、`SEQLOCK_HEALTHY`）在 `bridge.py` 实际实现中不存在"。本次独立复核**确认该自我否证正确**：`bridge.py` 中 `SeqlockWatchdog` 在 **56-83 行**，只有 `__init__`（65）、`update`（71）、`reset`（80）三个方法；`SEQLOCK_DEAD` / `SEQLOCK_ERROR` / `SEQLOCK_HEALTHY` / `ShutdownBridge` / `_state` **全仓 0 命中**；"第 103–135 行"引用的代码块实际是 `SharedBridge.__init__` 与 `stale` 属性 |
| — | （报告无此项） | **P0-2「`control` 写入点被跳过 — 主循环审计」** | 🚫 幻象 | 依赖 `bridge.control_written.is_set()`（**0 命中**）与命令 `python scripts/audit_contract_pairs.py --mode trace --target control`（实测 **exit 2**，`error: unrecognized arguments: --mode trace --target control`）。该文档 L9 亦已自我否证 |
| — | （报告无此项） | **P1-6「内存泄漏防护 — 演化日志累积」** | 🚫 幻象 | 目标文件 `fly64/plugin/evolution_logs.py` **不存在**（`Test-Path` → False；`fly64/plugin/` 实有 8 个 .py：`coach_outcomes / llm_consult / runner / scene_context / service / strategy_writer / __init__`）；`class EvolutionLogger` 全仓 **0 命中**（实有的相近类是 `skills/evolution_skill.py:199 class EvolutionHistory`，且它并**非**"把事件追加到无上限内存列表"的形态——`evolution_skill.py:1852` 用了 `deque(maxlen=20)`） |
| — | （报告无此项） | P1-5 / P3-12 的落点 `fly64/config/color_profiles.json` | 目标不存在（预期内） | `fly64/config/` 目录**存在**，但没有 `color_profiles.json`；属"待新增文件"，不算幻象。`SM64_COLOR_PROFILES` 真实存在于 `scene_recognition.py:394`（`self.color_profiles = SM64_COLOR_PROFILES` 在 `:619`） |

### 3.3 执行计划中「已失效 / 需重写」的内容清单（可直接进 v2 的修订单）

**A. 幻象 API（必须重写或删除）**

| 条目 | 引用的不存在物 | 实测反证 |
|---|---|---|
| L6-54（P0-1） | `SeqlockWatchdog.shutdown()`、`._state`、`SEQLOCK_HEALTHY/DEAD/ERROR`、`ShutdownBridge`；"`bridge.py` 第 103–135 行" | `bridge.py:56-83` 只有 3 个方法；4 个符号全仓 0 命中 |
| L94-141（P0-2） | `bridge.control_written`；`audit_contract_pairs.py --mode trace --target control` | `control_written` 0 命中；该命令实测 exit 2 |
| L144-194（P0-3） | `MushroomBody.learn_from_outcome()`、`contract.emit(...)`、`@contract.on(...)`、`CoachContract` | 4 个符号全仓 0 命中 |
| L200-261（P1-4） | `scene_recognition` 的 `self.scene_memory.record_danger(...)`、`SceneMemory.record_danger()` | `record_danger` 0 命中 |
| L329-396（P1-6） | `fly64/plugin/evolution_logs.py`、`class EvolutionLogger`、`self._logs: list[dict]` | 文件不存在；类名 0 命中 |
| L402-468（P2-7） | `CentralComplex.navigate_to_goal()`、`MemoryController.store_navigation_hint()/recall_navigation_hint()`、`bridge.inject_navigation()` | 4 个符号全仓 0 命中 |
| L472-524（P2-8） | `CoachContract`、`coach.contract.is_active()`、`coach.serialize()/deserialize()`、`scene_memory.set_danger()` | 全仓 0 命中 |
| L604-624（P3-11） | `pyproject.toml`、`.pre-commit-config.yaml` | 两者均不存在（实际为 `.github/workflows/ci.yml`） |

**B. 失效命令（会直接报错）**

| 位置 | 命令 | 实测结果 |
|---|---|---|
| L570 | `python -m pytest fly64/tests/known_failures/ --collect-only` | `ERROR: file or directory not found: fly64/tests/known_failures/`，**exit 4**（`known_failures` 不是目录） |
| L128 | `python scripts/audit_contract_pairs.py --mode trace --target control` | **exit 2**，`unrecognized arguments` |
| L597 | `grep -rn 'print(' fly64/fly64/ fly64/plugin/ --include='*.py'` | 在 Windows 默认 shell 下不可用（无 grep）；且该命令的 cwd 语义与文档其它命令不一致（其它命令假定 `cd fly64`）。**本次未执行**（避免无意义的全量输出）；仅指出可移植性问题 |

**C. 数字/前提失效**

| 位置 | 执行计划写法 | 实测 |
|---|---|---|
| L204（P2-9) | 「`known_failures.win32.json`（38 条）和 `.linux.json`（24 条）」 | ✅ **正确**（比报告 L228 的 36 条更准） |
| L512/L524 | 「参考 `known_failures.win32.json` 中的 **contract 相关条目**补充负向测试」 | ⚠️ 实测 win32 基线 38 条中 id 含 `contract` 的**只有 1 条**，且含义不符：`tests/test_autonomy_regression.py::TestVersionContract::test_brain_version_in_skills_md_round_table`（**版本契约**，cause=`unknown`，note 为空）。与"教练合约"相关的条目数 = **0**（`test_plugin_mhr` 在基线中出现 **0** 次）。⇒ 该"参考"指引**实质上指向空集 / 错误对象** |
| L538 | 「缺少演化相关条目，无法标记已知的 MB 学习 / CX 导航问题」 | ✅ 成立（基线 38+24 条中确无 MB/CX 条目） |
| L555/L561 | 新增条目用 `expected_fix_version: "2.24.0"` | ⚠️ 与 `main.py` 当前 2.23.11 的关系未说明；且**新增条目 schema（`test_id/platform/reason/expected_fix_version`）与基线真实 schema（`id/cause/note`）不一致** —— 照此写入会破坏 `check_regressions.py:114` 的 `e["id"]` 读取与 `test_regression_detector.py::test_every_entry_has_a_cause_and_note`（该测试**当前正在 NEW FAILURES 列表中失败**） |
| L648/L651/L656/L658 | 执行顺序图里 P0-3 的依赖写「依赖 P1-4, P1-5, P1-6」，而 P0-3 自身排在 Day 3-5、P1-4 也排 Day 3-5 | ⚠️ 循环依赖表述（P0 依赖 P1，而 P1-4 又「前置依赖 P0-3」，L206）——**P0-3 ⇄ P1-4 互为前置**，无法拓扑排序 |

**D. 结构性问题**

- **报告的 P0 唯一的行动（SM64 自动重启）在执行计划中缺失**，而执行计划自造了 2 个幻象 P0 并已自我否证 → 实际结果是：**当前没有任何一份文档在推进"SM64 冻结自动重启"这个唯一经实测确认成立的 P0 缺口**。这是 v2 最重要的修复点。
- 执行计划的 `风险矩阵`（L668-676）与 `执行顺序建议`（L642-664）均建立在上述幻象条目上，需整体重算。

### 3.4 两份文档对同一事物的数字对照（供 v2 取真值）

| 事项 | 报告 | 执行计划 | 实测（T0/T1） |
|---|---|---|---|
| 基线条数 | 36（win32 语义，单文件） | **38 / 24**（双文件）✅ | **38 / 24** |
| 基线文件名 | `tests/known_failures.json` | `fly64/tests/known_failures.{win32,linux}.json` ✅ | `fly64/tests/known_failures.{win32,linux}.json` |
| 脑版本 | 2.23.6 | **2.23.11** ✅ | **2.23.11** |
| 写 control 处数 | ~12（从 35） | 未提 | **36**（预算 26，测试 FAIL） |
| 测试结果 | ~482 passed / 11 failed | 未提 | **929 passed / 38 failed / 36 skipped** |
| agent.md 行数 | 1360 ✅ | 未提 | **1360** |
| 文件自身行数 | 314 | 676（任务描述写 670） | **314 / 676** |

> 结论：**在"可核实的具体数字"上，`fly64_execution_plan.md` 比报告更准确**（版本号、基线条数与文件名都对）；它的问题不在数字，而在**围绕幻象 API 展开的修改步骤**。这一区分对 v2 很重要——不应因为执行计划有幻象 API 就否定它的数字。

---

## 4. 本次核对所用的新增实测（命令 + 原始输出）

### 4.1 版本表与历史记录的差集

```powershell
# cwd = D:\codes\flygym
$py -c "
import json, re
from pathlib import Path
t = Path('docs/fly64_export_logs_analysis_report.md').read_text(encoding='utf-8')
table_vers = set(re.findall(r'^\| v([0-9.]+[0-9x]*) \|', t, re.M))
d = json.load(open('fly64/skills/evolution_history.json', encoding='utf-8'))
hist = {str(r.get('brain_version')) for r in d['records']}
print('report table brain versions:', len(table_vers))
print('history distinct brain_version:', len(hist))
..."
```

原始输出：

```
report table brain versions: 34
history distinct brain_version: 51
in history but NOT in report table (17):
    None
    1.0.x
    1.1.0
    2.14.0
    2.15.0
    2.16.0
    2.17.0
    2.18.0
    2.19.0
    2.19.1
    2.19.2
    2.19.3
    2.20.0
    2.20.3
    2.20.4
    2.21.0
    2.21.1
in report table but NOT in history (0): []
report-missing versions in 2.14.0-2.21.1: 14 ['2.14.0','2.15.0','2.16.0','2.17.0','2.18.0','2.19.0','2.19.1','2.19.2','2.19.3','2.20.0','2.20.3','2.20.4','2.21.0','2.21.1']
```

### 4.2 历史记录中 2.14–2.22 段的真实内容（报告缺失段）

```
  2.14.0    | skill 3.0.0  | brain        | Motor-P1
  2.15.0    | skill 3.0.0  | brain        | Motor-P2
  2.16.0    | skill 3.0.0  | brain        | Motor-P3
  2.17.0    | skill 3.0.0  | brain        | Motor-P4/P5+M1
  2.17.0    | skill 3.0.0  | analysis     | P1-2 perf
  2.19.3    | skill 3.1.0  | infra        | 运维收敛
  2.20.0    | skill 3.1.1  | brain+skill  | v2.20.0 发布
  2.20.0    | skill 3.2.0  | skill_update_auto | None
  2.21.0    | skill 3.2.0  | brain        | t6 根因修复
  2.14.0    | skill 3.0.0  | brain        | R23
  2.18.0    | skill 3.0.0  | brain_update_auto | None
  2.18.0    | skill 3.0.0  | skill_fix    | None
  2.19.0    | skill 3.0.0  | brain_update_auto | None
  2.19.1    | skill 3.0.0  | brain_update_auto | None
  2.19.2    | skill 3.0.0  | brain_update_auto | None
  2.19.3    | skill 3.0.0  | brain_update_auto | None
  2.20.0    | skill 3.2.0  | skill        | L2 导航质量与自我进化闭环
  2.20.3    | skill 3.1.1  | brain        | R31-fix3
  2.20.4    | skill 3.2.0  | brain        | R31-fix4
  2.21.1    | skill 3.2.0  | brain        | R31-fix5
  2.22.0    | skill 3.2.0  | brain        | t9-A P1-1 环路破解
```

### 4.3 版本号连续复用（agent.md 规则 17 实测反证）

```powershell
$py -c "...for x in records: if bv==prev and bv not in ('None',): print('REUSE consecutive:', x['id'], bv)..."
```

原始输出：

```
79 records: 79
REUSE consecutive: EVO-016 2.6.0
REUSE consecutive: EVO-032 2.13.3
REUSE consecutive: EVO-039 2.17.0
REUSE consecutive: EVO-050 2.20.0
REUSE consecutive: AUTO-0002 2.13.3
REUSE consecutive: AUTO-0003 2.13.3
REUSE consecutive: AUTO-0005 2.13.3
REUSE consecutive: AUTO-0007 2.18.0
REUSE consecutive: EVO-066 2.23.5
REUSE consecutive: EVO-067 2.23.5
REUSE consecutive: EVO-068 2.23.5
REUSE consecutive: EVO-070 2.23.6
REUSE consecutive: EVO-071 2.23.6
```

> 说明：其中 `EVO-064/065/066/067/068`（2.23.5）与 `EVO-070/071`（2.23.6）等属 agent.md 规则 15 明示的「仅测试/文档/infra 变更不递增版本」情形，**不算违规**；但 `AUTO-0002/0003/0005` 连续三条 2.13.3 与 `EVO-032/EVO-050/EVO-039` 的复用需按规则 17 逐条判定。**此表仅列出事实，不做违规裁定**（裁定需要每条记录变更性质，超出 T1 范围）。

### 4.4 幻象 API 批量核查（全仓 0 命中清单）

命令：`grep`（DSH grep 工具）`path=fly64`、`include=*.py`、模式
`control_written|SEQLOCK_DEAD|SEQLOCK_ERROR|SEQLOCK_HEALTHY|ShutdownBridge|contract\.emit|CoachContract|record_danger|store_navigation_hint|_nav_hints|navigate_to_goal|reload_color_profiles|memory_footprint|record_brain_version\(`

原始输出（**仅 6 条命中，且全部是 `record_brain_version`，属另一功能**）：

```
fly64\skills\evolution_skill.py
Line 258:     def record_brain_version(self, new_version: str, old_version,
Line 1886:         rec = self.history.record_brain_version(v, self._last_brain_version)
fly64\tests\test_evolution_history.py
Line 53: ... Line 72: (5 处调用)
```

⇒ `control_written / SEQLOCK_DEAD / SEQLOCK_ERROR / SEQLOCK_HEALTHY / ShutdownBridge / contract.emit / CoachContract / record_danger / store_navigation_hint / _nav_hints / navigate_to_goal / reload_color_profiles / memory_footprint` **全部 0 命中**。

第二条同口径查询（模式 `class EvolutionLogger|class MushroomBody|def learn_from_outcome|SM64_COLOR_PROFILES|class CentralComplex|class MemoryController|def _compute_heading|def danger_level|class SceneMemory|def get_danger`）原始输出：

```
fly64\fly64\central_complex.py    Line 47: class CentralComplex:
fly64\fly64\memory.py             Line 1733: class MemoryController:
fly64\plugin\scene_context.py     Line 93: class SceneMemory:
fly64\fly64\model.py              Line 49: class SceneMemory:
fly64\fly64\mushroom_body.py      Line 42: class MushroomBody:
fly64\fly64\scene_recognition.py  Line 394: SM64_COLOR_PROFILES: dict[str, QuantileProfile] = {
fly64\fly64\scene_recognition.py  Line 619: self.color_profiles: dict[str, QuantileProfile] = SM64_COLOR_PROFILES
fly64\fly64\scene_recognition.py  Line 783: def danger_level(self) -> float:
```

⇒ 要点：`class EvolutionLogger` 与 `def learn_from_outcome` **0 命中**；`class SceneMemory` **有两处**（`plugin/scene_context.py:93` 与 `fly64/fly64/model.py:49`，后者是"视觉短期记忆/亮度环形缓冲"），二者**同名异物** —— 执行计划 L154/L211/L220 在"场景→危险关联"语境下引用 `plugin/scene_context.py:93` 是**正确的**，但阅读时必须区分，否则会把 model.py 的 SceneMemory 当成危险关联存储。

### 4.5 重启能力核查（R-20 的判别证据）

```powershell
$py -c "
from pathlib import Path; import re
for p in ('fly64/plugin/service.py','fly64/plugin/runner.py'):
    t=Path(p).read_text(encoding='utf-8')
    hits=[(i+1,l.strip()) for i,l in enumerate(t.splitlines()) if re.search(r'sm64|SM64|restart|kill|Popen|pkill', l)]
    print('===', p, 'matches:', len(hits))
"
```

原始输出：

```
=== fly64/plugin/service.py matches: 4
  18| StrategyWriter so EvolutionSkill/brain keep operating autonomously.
  28| kill $(cat plugin/fly64-service.pid)                      <-- 文档串中的用法示例
  78| else PROJECT_DIR / "skills" / "active_strategy.json"
 140| active = json.loads(Path(PLUGIN_DIR.parent / "skills" / "active_strategy.json").read_text())
=== fly64/plugin/runner.py matches: 7
  2| """Fly64 MHR plugin runner — the 10s periodic skill cycle.
  10/13/14/72/264/329| （均为文档串/路径/取屏函数，无重启逻辑）
```

⇒ **`plugin/service.py` 与 `plugin/runner.py` 均无任何 SM64 重启动作**；`consolidate.sh` 只重启大脑。R-20 成立。

### 4.6 既存 CI 的真实覆盖面（R-11/R-22 相关）

```powershell
$py -c "from pathlib import Path; t=Path('.github/workflows/ci.yml').read_text(encoding='utf-8'); ..."
```

原始输出（CI 关键段）：

```
 49|       - name: Run tests (non-GUI subset, skip MaleCNS-dependent)
 51|           python -m pytest tests/ -q --tb=short \
 52|             --ignore=tests/test_bridge.py \
 53|             --ignore=tests/test_dashboard_protocol.py \
 54|             --ignore=tests/test_dashboard_js.py \
 55|             --ignore=tests/test_plugin_mhr.py \
 56|             --ignore=tests/test_service.py \
 57|             --ignore=tests/test_autonomy_regression.py \
 58|             -k "not male_cns and not sm64" 2>&1 | tail -20
```

⇒ 报告 L294「WSL 测试 CI …（含 Windows 不可测项）」：CI **已存在**（`.github/workflows/ci.yml`，66 行，ubuntu-latest + Python 3.12，`working-directory: fly64`），但**排除 6 个测试文件 + 排除 male_cns/sm64 关键字**，且**不运行** `check_regressions.py`、`audit_contract_pairs.py`。⇒ 报告的行动 11 应改为「**补齐既有 CI 的覆盖面**（去掉 6 个 ignore、把基线门禁接进 CI）」，而非「新建 WSL CI」。

---

## 5. 基础设施声明的代码层可验证性（任务指定的三项 + 附带）

判定口径：**代码层可验证** = 能在仓库文件里给出 `文件:行`；**运行态** = 需要进程表/WSL/活体端点，Windows 上不可验证；**未验证** = 本次未做。

| # | 报告声明（行） | 可验证性 | 证据 | 判定 |
|---|---|---|---|---|
| 5.1 | 「WSL 自治服务 ✅ 常驻运行（plugin.service watchdog 监控）」（L245） | 代码层 ✅ / 运行态 ❌ | `fly64/plugin/service.py`（16466 bytes，`DEFAULT_BRIDGE_STALE = 60.0` @ `:60`，健康检查含 `bridge_fresh` @ `:94`）；`fly64/plugin/watchdog.sh`（2549 bytes）—— 逻辑：`is_alive()` 用 pid 文件 + `kill -0`；`start_service()` 以 `nohup ... -m plugin.service --interval 10 --bridge-path $BRIDGE` 重启；连续失败 `MAX_FAILS=3` 后 `ALERT`；`resolve_bridge()` 从游戏进程 `/proc/<pid>/environ` 读真实 `FLY64_BRIDGE`；设计由 cron `* * * * *` 或 systemd timer 驱动 | **代码层一致；"常驻运行"本次未验证**（需 WSL） |
| 5.2 | 「存活监控 ✅ seqlock 看门狗 + stale 徽章」（L246） | 代码层 ✅（全链路） | `fly64/fly64/bridge.py:56` class / `:65` `stale_after=5.0` / `:71` `update(seq,now)->bool` / `:76-77` 判据 / `:80` `reset` / `:103` 实例化 / `:111-114` `SharedBridge.stale` / `:145` 正常帧喂 seq / `:148` 龙读分支喂旧 seq；`fly64/fly64/main.py:2278` `"bridge_stale": bool(bridge.stale)`；`fly64/web/index.html:4` `id="bridgeStalePill"`（class `stale-pill`，文案 `SM64⛔ FROZEN`，默认 `hidden`）；`fly64/web/dashboard.js:1109-1111`；`fly64/web/dashboard.css:108-109`；测试 `fly64/tests/test_seqlock_watchdog.py`（103 行，11 个 test，含 `test_dashboard_freeze_pill_wiring`） | **一致** |
| 5.3 | 「SM64 自动重启为已知待办但未实现」（L215）；行动 1「**实现** SM64 冻结自动重启」（L269） | 代码层 ✅（缺失可证） | §4.5 的判别证据：`plugin/service.py` 仅 4 处匹配且第 28 行是文档串；`plugin/runner.py` 7 处无重启逻辑；`consolidate.sh` 的重启对象是大脑；全仓无 `auto-restart/respawn/restart_sm64` 实现 | **一致**（"未实现"这一声明成立；同时证明行动 1 的需求成立） |
| 5.4 | 「启动契约 ✅ consolidate.sh + setsid nohup」（L248） | 代码层 ✅ | `fly64/scripts/consolidate.sh:4-27`（契约注释块）、`:56-58`（停旧大脑）、`:71-75`（`setsid nohup` + `disown`）、`:89-119`（自治服务重启 + setsid） | **一致** |
| 5.5 | 「度量工具 ✅ scripts/measure_evolution_health.py」（L250） | 代码层 ✅ + 可运行 ✅ | `fly64/scripts/measure_evolution_health.py`（468 行）；`--help` exit 0；`--json` 实跑 exit 0 并产出完整 JSON（T0 §5.3） | **一致** |
| 5.6 | 「回归基线 ✅ tests/known_failures.json + check_regressions.py」（L249） | 代码层 ✅ / 状态 ❌ | 工具与 scoped 基线均存在，但 `check_regressions.py` **当前 exit 1（10 条 NEW failures）**；且基线文件名写错（R-14） | **部分一致（"✅"与实测红状态冲突）** |
| 5.7 | 「仪表板 ✅ P0-P3 因果链 + P4-P6 后续」（L247）；「body.causal-off kill-switch + section.xxx-section」（L207） | 部分可验证 | `web/dashboard.js:6,16`（`causal-off` 逻辑）与 `web/dashboard.css:8-9`（`body.causal-off .causal-ui{display:none!important}`）**已验证**；P4-P6 面板与 `section.xxx-section` 选择器**本次未逐项核验** | **部分一致 / 部分未验证** |
| 5.8 | 「LSP 状态 \| 11 基线失败」（L238） | ❌ 无法验证 | **全仓库（排除 `.venv`/`.git`/`node_modules`）穷举文件名的 `pyright\|ruff\|mypy\|\.lsp\|pylsp\|basedpyright` 命中数为 0**，即无任何 LSP/类型检查工具链配置或结果产物。报告此处应是"测试基线"的笔误（"LSP"疑为"测试"之误）；且其数字 11 本身也不成立（见 R-12） | **报告表述不可验证**（见 §6 U-06） |

---

## 6. 本次未验证项（明确列出，禁止外推）

| ID | 未验证项 | 为什么 | 已尝试的动作 |
|---|---|---|---|
| U-01 | 「WSL 自治服务**正在**常驻运行」 | 需 WSL 进程表 / `/root/fly64` | 仅做代码层核验（§5.1）；未执行任何 WSL 命令 |
| U-02 | 报告 7 个会话的**身份与内容**（含 L184/L189 的"出现会话"归属） | 需解包 `export logs/*.zip`（10 个 zip，含 1 个重复 id） | 仅做目录枚举 + 文件名正则；**未解包**（避免扩大范围与污染工作树） |
| U-03 | 报告 L84「docs/analysis/t1-bottleneck-root-cause-analysis.md，329 行」等文档行数 | 与报告主线结论无关，本次未逐份核 | 未执行（如需可一次性批量统计） |
| U-04 | 「P4-P6 仪表板存在」与 L206 的 4 个 CSS commit 引用 `661b939/a30dfbb/cd555f8/d9bd246` | 前者需逐面板核对；后者需 `git cat-file` 消歧（4 个短 SHA 未给出仓库上下文） | 未执行 |
| U-05 | L226「新测试（自查）test_spin_loop_fix 7 / test_cliff_standoff 9 / test_brain_alternation 9」的**条数** | 与主线不冲突；但**反向证据已实测**：`test_mbon_saturation` 家族当前有 3 条 NEW failures | 仅引用 `check_regressions.py` 的 NEW FAILURES 列表 |
| U-06 | L238「**LSP** 状态」的确切所指 | 仓库内无任何 LSP 工具链产物 | grep 未命中；判定为表述问题 |
| U-07 | 报告 L166「视觉能力覆盖 38%→90%」的度量口径 | 无对应度量文件/脚本证据；未找到该百分比的产出脚本 | 未执行（明确标为无证据，不作推测） |
| U-08 | 执行计划 L597 的 `grep -rn 'print(' ...` | Windows 默认 shell 无 grep；且输出量与主线无关 | 未执行（仅指出可移植性问题） |

---

## 7. 给下游（计划 v2）的修订要点

1. **数字一律取实测真值**：脑版本 2.23.11、基线 38/24（env 14/1）、测试 929 passed/38 failed/36 skipped、写 control 36 处（预算 26）、agent.md 1360 行、报告 314 行、执行计划 676 行。
2. **「36 条」若需保留，须注明是 `EVO-068`（2026-09-17）快照**，并给出当前值。
3. **报告版本表有断层**：`2.14.0–2.21.1` 共 14 个真实版本（Motor-P1~P5+M1、v2.20.0 发布、t6 根因修复、R31-fix3~5）缺失，v2 若要引用演化轨迹须以 `evolution_history.json` 为准而非报告表。
4. **执行计划的幻象 API 必须重写**（8 个条目，见 §3.3-A），其中 P0-1/P0-2 已被该文档自我否证、本次独立复核确认；**P1-6 的目标文件 `plugin/evolution_logs.py` 不存在，属最危险的一条（容易被当成"待修的真实模块"而白白投入）**。
5. **找回被丢失的报告行动**：报告 12 项里 **7 项在执行计划中无对应**（#1 SM64 自动重启、#5 课程晋级验证、#6 DAN 权重自动化、#8 写 control 清零、#10 度量看板、#11 WSL/CI、#12 CSS 契约测试）。其中 **#1 是唯一经实测确认成立的 P0 缺口**（检测就绪、动作缺位），应在 v2 中恢复并设为 P0。
6. **行动 8 的起点改为 36**，第一步目标是「回到 26 预算内」，而非直接清零；且该 KPI 测试当前为 FAIL，属可立即验收的闭环。
7. **行动 6（CI）改为"补齐既有 CI 覆盖面"**：`.github/workflows/ci.yml` 已存在但排除 6 个测试文件 + `-k "not male_cns and not sm64"`，且未接 `check_regressions.py`。
8. **任何"跑测试作为验收"的行动必须处理 `fly64/.pytest-run/` 污染**（132 个被跟踪文件，T0 §6.3）。
9. **基线扩展行动（报告 #2）要注意 schema 一致**：基线真实 schema 是 `{id, cause, note}`（顶层 `platform/recorded_at/count/entries`），执行计划 P2-9 拟用的 `{test_id, platform, reason, expected_fix_version}` 会破坏 `check_regressions.py:114` 与 `test_regression_detector.py` 的校验（后者当前就在失败列表中）。
10. **`SceneMemory` 同名异物**：`plugin/scene_context.py:93`（场景上下文 dataclass）与 `fly64/fly64/model.py:49`（视觉短期记忆）不是同一个东西，v2 描述"场景→MB 闭环"时必须写全路径。
