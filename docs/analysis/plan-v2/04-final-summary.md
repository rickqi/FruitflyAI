# 04 — 最终交付与决策摘要（T4）

> 任务：`t5 [T4] — 整合最终交付与决策摘要`
> 执行者：plan-writer（T2 主计划撰写者，本次为整合修订）
> 输入：`docs/analysis/plan-v2/00-facts.md`（T0）、`docs/analysis/plan-v2/01-reconciliation.md`（T1）、
> `docs/analysis/plan-v2/03-verification.md`（T3 独立验证，verdict = `needs_revision`，20 条发现项）、
> `docs/fly64_execution_plan_v2.md`（主交付，T2 产出 + T3 Captain takeover 修复 + 本次 T4 收尾修订）
> 被分析对象：`docs/fly64_export_logs_analysis_report.md`（314 行）
> 时间：2026-09-20（Windows / `sys.platform = win32`）
> 解释器：`D:\codes\flygym\.venv\Scripts\python.exe`（Python 3.11.9）
> Shell：Windows PowerShell **5.1**.26100.1591（无 pwsh 7 —— 这直接决定了 §1.2 的一处命令改写）
> git HEAD：`1badb4072d27116a967bfaa3dd1d614c133881b9`（`master`，305 commits）

---

## 0. 一页摘要

**本次交付的是「计划」，不是「实现」。** 无任何代码/测试/基线/CI 被改动（`git diff --stat` = 空）。

| 项 | 结论 |
|---|---|
| 主交付物 | `docs/fly64_execution_plan_v2.md` —— **1610 行 / 136833 bytes**（T4 收尾修订后的最终值），覆盖 12 项行动（P0×3 / P1×3 / P2×3 / P3×3），每项 8 个字段（目标与动机 / 涉及文件 / 实施步骤 / 验证命令 / 验收标准 / 前置依赖 / 预估工作量 / 风险与回滚），结构自检缺失 = **NONE ×12** |
| 事实底座 | 全部数字以 T0 实测为「当前状态」，并用 **S1–S10** 取代报告中 10 组已过期数字（§1） |
| 事实偏差处置 | 报告 32 条论断中判定 **一致 12 / 偏差 14（high 5、medium 5、low 3、info 1）/ 未验证 6**；关键根因已定位（§1.1） |
| 验证发现项处置 | 20 条（blocker 0 / high 3 / medium 10 / low 7）→ **已修 18 条、明确标注为已知限制 2 条**（§5） |
| 可立即开工 | **行动 2、3、1、5、7、9**（6 项，无阻塞；其中 2+3 需同批提交） |
| 被阻塞 | 行动 4（需行动 2）→ 行动 6（接 4）→ 行动 8（需 2 的 `--update` + 4/6 先落地）；行动 12（需行动 10 先改前端） |
| 关键路径 | `行动 2 → 行动 4 → 行动 6 → 行动 8` |
| 总量 | **18.5–33.5 人日**（1 人串行 ≈ 19–34 工作日；2 人并行 ≈ 11–19；3 人 ≈ 9–15） |
| 范围决策 | 本次仅交付文档；**代码实现须另行批准**，并须走 `requirements → implementation → verification → review → integration`（§3） |
| 本机未验证 | 5 项硬限制 + 4 项范围外（§4） |

---

## 1. 报告事实偏差摘要（哪些数字已过期、如何修正）

### 1.1 根因：两类偏差，性质完全不同

T1 的最有价值发现是：报告的偏差**大部分不是虚构，而是「快照过期」**。

| 类型 | 涉及条目 | 根因（实测） | 含义 |
|---|---|---|---|
| **A. 快照过期**（可解释、非编造） | 基线 36 条 / 13 env、基线文件名、`real-bug` 5→2、评分口径 | 报告 L228 的「36 条（13 env）」**逐位等于** `evolution_history.json` 中 `EVO-068`（2026-09-17，t15）记录原文 `environment 13 / aspirational 15 / real-bug 5 / test-drift 3`（和 = 36）。基线文件随后在 `d37c15ea92829e5934f688176b0202cf5d4c2442`（`EVO-071 follow-up`，2026-09-18 16:08）被改写为 win32 38 / linux 24。`EVO-071` 自述「修正了我自己对两处失败的误判（原记为 real-bug，实测均为 test-drift）」正好解释 `real-bug 5→2` 与新增 `unknown 3` | 报告当时**是对的**；只是它引用的现状已被后续提交改写。**修正方式 = 按实测值回填 + 注明快照时点** |
| **B. 数字错配**（无来源可解释） | 「~482 通过 / 11 基线失败」、「写 control 35→12 处 / ~12 处」、「11 条基线失败均为 Windows 环境问题」 | 仓库中**找不到**任何能拼出这两组数字的组合。`482 passed` 只在 `evolution_history.json` 一条早期记录的 `tests` 字段里作为「TestConsultFrameSnapshot 4 用例，482 passed」的局部数出现过；`EVO-068` 自身写的是 `40 failed / 881 passed / 36 skipped → 36 failed / 881 passed / 36 skipped`。**「35 处写 control」在仓库中零出处**（唯一可核验的 KPI 轨迹是 `ver_append_r24.py:37` 的「18→26 附豁免表」与 `test_p1_neural_takeover.py:229` 的 `pre-P1: 45 / 53`） | 属**不同时期数字的陈旧拼接**。修正方式 = **整组替换为实测值**，并在计划中把「35」标为「无出处」 |

### 1.2 取代清单 S1–S10（计划 §0.4 的等价摘要）

| # | 报告位置 | 报告写法（过期） | **实测真值（本计划采用）** | 复现命令要点 |
|---|---|---|---|---|
| **S1** | L4 / L149 | Brain v2.23.6（称「最新」） | **`"2.23.11"`** @ `fly64/fly64/main.py:39`（注释 `R31-fix12`） | `Select-String -Path fly64\fly64\main.py -Pattern '^BRAIN_VERSION'` |
| S1b | （报告未提） | — | **新增缺陷**：同一仓库并存 **4 种版本声明** —— `main.py:39`=2.23.11、`skills.md:3`=2.23.7、`skills.md:70`=2.23.10、`evolution_history.json` `canonical_versions.brain`=2.23.6 → `agent.md` 规则 8「版本三处同步（强制契约）」**实测不成立** | `Select-String -Path fly64\skills\skills.md -Pattern 'BRAIN_VERSION \*\*'` |
| S1c | L4/L149 暗示记录覆盖到最新 | — | **新增缺陷**：`2.23.7/8/9/10/11` 共 **5 个版本在 `evolution_history.json` 中零记录**（语义最大版本 = `2.23.6`，排除 3 条字面量 `"None"`）→ 规则 15「禁止无记录递增」**实测不成立** | 见主计划 §0.2 第二块（按 `(major,minor,patch)` 排序） |
| **S2** | L226 | ~482 通过 / 11 基线失败（Windows 环境） | **929 passed / 38 failed / 36 skipped**（T0 216.43 s；T3 独立复跑 246.36 s，逐项一致） | `cd fly64; & $py scripts\check_regressions.py` |
| **S3** | L170 / L228 / L252 | 基线 **36 条（13 env）**、`tests/known_failures.json` | **win32 `known_failures.win32.json` = 38 条**（`aspirational 16 / environment 14 / test-drift 3 / real-bug 2 / unknown 3`）；**linux `known_failures.linux.json` = 24 条**（`aspirational 16 / environment 1 / live-state 2 / test-drift 3 / unknown 2`）；两文件 `count == len(entries)`，无重复 id | 见主计划 §0.2 第一块 |
| S3b | （报告未给） | — | 跨平台：**交集 22 / win32-only 16 / linux-only 2**；`live-state` 只出现在 linux 基线（2 条 `test_coach_pipeline.py::TestServiceCycle::*`） | 同上 |
| **S4** | L238 | 11 基线失败「**均为 Windows 环境问题**」 | **38 failed**，其中 `environment` 仅 **14**；基线含 `aspirational 16 / real-bug 2 / test-drift 3 / unknown 3`。**`real-bug` 2 条是真缺陷**（`test_invariants.py::test_launcher_lock_blocks_duplicate`、`test_optic_flow.py::test_flow_computation_performance`——后者 note 实测「`compute_flow` 29.35 ms 对 5 ms 预算」）→ 归入「环境问题」会**掩盖真实缺陷** | 读 `known_failures.win32.json` 的 `cause`+`note` |
| **S5** | L294 | 「基线 **11** 失败可根治」 | **38 failed**；当日门禁退出码 **1**，其中 **NEW failures = 10**、**基线条目转为通过 = 10**（9 `environment` + 1 `unknown`，含 6 条 `test_bridge.py::*`） | `check_regressions.py` 首行 `REGRESSION CHECK (baseline win32, 38 entries)` |
| **S6** | L167 / L236 / L286 | 写 control **35→12 处 / ~12 处**，行动目标「从 ~12 降至 0」 | **36 行 / 36 处赋值**（官方 KPI 口径：`test_p1_neural_takeover.py:230-231` 预算 `KPI_LINES = KPI_ASSIGNMENTS = 26`，`:236` 正则 `\bcontrol\.\w+\s*=[^=]`）→ **超标 10，该测试实测 FAIL**（`AssertionError: write lines 36 / assert 36 <= 26`）。**行动起点改为 36，第一步目标是「回到 ≤26 预算内」而非直接清零**（护栏类与操作员指令类写入点语义上不可删） | `& $py -c "import re;…"`（见主计划行动 8 验证(1)） |
| **S7** | L228 / L249 | 基线文件 `tests/known_failures.json` | 实际为**平台作用域双文件**；未限定名的 `fly64/tests/known_failures.json` **不存在**（`Test-Path` → `False`）。按字面 `open()` 会 `FileNotFoundError` | `Test-Path fly64\tests\known_failures.json` |
| **S8** | L4 / L21 | 「全部 **7 个**已导出 DSH 会话」「覆盖 ~2026-09-11 至 09-20」 | `export logs/` 实为 **10 个 zip / 9 个不同 session id**；报告点名的 7 个短 id 中**只有 3 个**（`38542b1c`、`99cab60f`、`f953d3fd`）在文件名中可对上。且 `evolution_history.json` **无任何记录晚于 2026-09-18**（`canonical_versions.as_of = 2026-09-18T01:08:22+08:00`）→ 时间跨度被高估 2 天。⚠️ zip **未解包**，故「7 会话」内容维度**完全未验证** | 目录枚举 + 文件名正则（未解包） |
| **S9** | L107 | `gent.md`（1360 行） | 文件名拼写错误，应为 **`agent.md`**（仓库根，1360 行 / 117938 bytes 实测 —— **行数本身正确**）。⚠️ 附带警告：PowerShell `Get-Content` 对同一文件给 **921**（UTF-8 中文下的编码假象），**行数与 JSON 计数一律用 Python** | `& $py -c "from pathlib import Path;print(len(Path('agent.md').read_bytes().decode('utf-8').splitlines()))"` |
| **S10** | L109–L147 版本表（34 个版本） | — | **断层**：`evolution_history.json` 的 51 个唯一 `brain_version` 中 **17 个不在报告表内**，其中 **`2.14.0–2.21.1` 共 14 个真实存在**（Motor-P1~P5+M1、v2.20.0 发布、t6 根因修复、R31-fix3~5）→ 任何「从报告版本表推导演化轨迹」都会漏掉整段。**演化轨迹一律以 `evolution_history.json` 为准** | 见 T1 §4.1/§4.2 的差集脚本 |

### 1.3 已核验为真、**无需修正**的报告论断

| 报告论断 | 实测 | 说明 |
|---|---|---|
| `agent.md` = 1360 行（L4） | **1360 行 / 117938 bytes / 全 LF / 无 BOM** | 这是全文**最容易被误判为错误**的一条：PowerShell 给 921，**报告对、PowerShell 错** |
| 79 条 evolution 记录（L4/L107/L149） | **79 条** | ✅ |
| 「51 个唯一脑版本」（L149） | **51 个唯一字面量**（含 3 条字面量 `"None"` → **语义唯一 50**） | 数字成立；用「50」更严谨 |
| 三个脚本存在（L229/L230/L250） | `fly64/scripts/{check_regressions,audit_contract_pairs,measure_evolution_health}.py` **均存在**（322 / 177 / 468 行） | 但**须相对 `fly64/` 解析** |
| 「SM64 自动重启未实现」（L215）+ 行动 1 需求（L269） | **成立，且是唯一经实测确认成立的 P0 缺口** | 检测层全链路已通（`bridge.py:56/103/111-114/145/148` → `main.py:2278` → `web/index.html:4` → `dashboard.js:1109-1111` → `dashboard.css:108-109`，测试 11 项全绿）；动作层为零（`plugin/service.py` 仅 4 处匹配、唯一 `kill` 在 `:28` docstring；`consolidate.sh` 只重启大脑；全仓无 `auto.?restart/respawn/restart_sm64` 实现） | 见主计划行动 1 |
| 启动契约（L248）、合约审计工具（L229）、度量工具（L250） | **均成立**（`consolidate.sh:4-27/71-75/109-113`；`audit_contract_pairs.py` exit 0；`measure_evolution_health.py --json` exit 0） | ✅ |
| 「P1 进化轮（2.8.0）已删除 11 个 A 类旁路点」（L167/L239） | **成立**（`EVO-019` 记录原文「删除 11 处 A 类 Python 旁路（A1-A9/B10/C10）」） | ✅ |

---

## 2. 12 项行动：优先级排期总览与建议起手项

### 2.1 总览表（含阻塞状态）

「可开工」判定 = 其全部前置依赖**在本次交付时点已满足**（依赖项为「已验证的实测事实」而非「待交付物」）。

| # | 优先 | 行动 | 前置依赖 | **当前可否开工** | 工作量 | 关键落点 |
|---|---|---|---|---|---|---|
| 1 | P0-1 | SM64 冻结自动重启 | 无（仅需行动 2 提供可信基线以判「NEW ≤1」） | ✅ **可立即做**（离线部分） | 2.5–4 | 新增 `fly64/plugin/sm64_watchdog.sh` + `fly64/tests/test_sm64_watchdog.py` |
| 2 | P0-2 | 回归基线获取（分类工具 + 平台全量分类） | 无 | ✅ **可立即做 —— 全局瓶颈，建议第一个做** | 1.5–2.5 | 新增 `fly64/scripts/baseline_tool.py` + 修 3 条 `unknown` |
| 3 | P0-3 | 契约审计制度化 | 无（与行动 2 同一 YAML，**无拓扑顺序**，提交时合并） | ✅ **可立即做** | 0.5–1 | 改 `.github/workflows/ci.yml`（**不是**新建 pre-commit） |
| 4 | P1-4 | 场景识别 → MB 学习闭环 | **行动 2** | ⏳ 待行动 2 | 2–3.5 | `fly64/fly64/model.py` 多巴胺合成点（`:1461-1482`） |
| 5 | P1-5 | 课程晋级端到端验证 | **行动 2** | ✅ 可立即做（只读验证为主） | 1–2 | 新增 `fly64/scripts/replay_curriculum.py` + `fly64/tests/test_curriculum_end_to_end.py` |
| 6 | P1-6 | DAN 权重自动化 | **行动 2**；与行动 4 有接口耦合（建议 4 先落地） | ⏳ 待行动 4 | 2.5–4 | `fly64/skills/brain_tunable_params.json` + `fly64/fly64/model.py` `DAN_*` 读点 |
| 7 | P2-7 | CX 空间导航回路部署 | **行动 2** | ✅ 可立即做（**回路实测已在跑**，本项＝收敛验收 + 补契约测试） | 1.5–3 | 新增 `fly64/tests/test_cx_navigation_loop.py`（离线、无 playwright） |
| 8 | P2-8 | `main.py` 写 control 清零 | **强依赖行动 2 的 `--update`** + 须排在行动 4/6 之后（同改 `model.py`） | ⛔ **被阻塞** | 3–6（**最大项**） | `fly64/fly64/main.py`（36 → ≤26） |
| 9 | P2-9 | 教练通路契约测试 | **行动 2** | ✅ 可立即做 | 1.5–2.5 | 扩展 `fly64/tests/test_coach_contract.py` + 新增 `test_coach_roundtrip.py` |
| 10 | P3-10 | 度量看板 | **行动 2** | ✅ 可立即做（数据源已就绪；「排行榜」无口径 → 降级为趋势表） | 2.5–4 | `fly64/fly64/main.py`（新端点）+ `fly64/web/dashboard.js` |
| 11 | P3-11 | WSL 测试 CI | 与行动 2/3 同批 YAML；`male_cns` 解锁另需外部 1.3 GB 缓存 | ✅ 可立即做（补覆盖面，非新建） | 1–2 | `.github/workflows/ci.yml` |
| 12 | P3-12 | CSS 契约测试 | **行动 10 必须先改前端**（否则截图基线立刻过期） | ⏳ 待行动 10 | 2–3.5 | 扩 `fly64/scripts/layout_audit.py` + 新增 `fly64/tests/test_layout_contract.py` |

### 2.2 建议起手项（按「投入产出比 × 可立即性」排序）

**第一批（本次交付后即可开工，建议 2 人并行）**

| 顺序 | 行动 | 为什么先做它 | 立即闭环的验收信号（可客观判定） |
|---|---|---|---|
| 1 | **行动 2** | 全局瓶颈：12 项里 11 项需要「无回归」判定。且它含一个**现成红灯**可直接闭环 | `baseline_tool.py --check` 双平台 exit 0；`--list-unknown` 为空；`test_regression_detector.py` 从 **1 failed/5 passed → 6 passed** |
| 2 | **行动 3**（与 2 同批提交 YAML） | 成本极低（0.5–1 人日），且能立刻暴露 8 处真实 dead-write | CI 出现 `audit_contract_pairs`；本地 exit 0、`TOTAL = 8` 被记录 |
| 3 | **行动 1**（并行开发，P0 缺口） | **唯一经实测确认成立的 P0 需求**，且旧执行计划把它整条丢了 | `test_sm64_watchdog.py` ≥5 全绿；`test_seqlock_watchdog.py` 仍 **11 passed** |
| 4 | **行动 7** | 工作量小且**结论已改判**（回路实测在跑）→ 交付物从「实现」降为「契约测试」，零风险 | 新增测试 ≥6 全绿；`cx.heading_column` / `cx.anchor_distance`（**property，不带括号**）取值合法 |
| 5 | **行动 5** | 只读验证为主，工作量小，能把「晋级证据被 reset 清空」这件事变成可复现的结论 | `replay_curriculum.py --from-jsonl` 与 `curriculum.json` 现值一致（或产出可复现差异报告）；`--synthetic` 三组断言全过 |
| 6 | **行动 9** | 已有 `test_coach_contract.py` 地基（8 passed），只需补「写→读往返」 | 新增往返测试 ≥5 全绿；既有 4 个相邻测试文件全绿 |

**第二批（行动 2 完成后解锁）**：行动 4 → 行动 6（串行）→ 行动 8（独占排期，B4 批次）→ 行动 10 → 行动 12；行动 11 与行动 10/12 同批 YAML 收口。

### 2.3 被阻塞项与阻塞解除条件（明确列出）

| 被阻塞项 | 阻塞原因 | 解除条件 |
|---|---|---|
| **行动 4** | 需要可信基线 | 行动 2 的 `baseline_tool.py --check` 双平台 exit 0 + `--list-unknown` 为空 |
| **行动 6** | 与行动 4 的接口耦合（若行动 4 选方案 B 则强耦合），且需行动 2 | 行动 4 的 `scene_danger → dopamine` 注入点定稿（方案 A 落地） |
| **行动 8**（最大项） | ①必须**先**用 `check_regressions.py --update` 吸收当前 10 条 NEW，否则「减少写点」会让 KPI 测试的基线状态漂移；②行动 4/6 也改 `fly64/fly64/model.py`，需避免同文件冲突 | 行动 2 的 `--update` 完成 **且** 行动 4、6 已合入 |
| **行动 12** | 截图/文本基线必须在 UI 冻结后建立 | 行动 10 的前端改动（`web/index.html` / `dashboard.js` / `dashboard.css`）合入 |
| **行动 11 的 `male_cns` 解锁** | 需外部 ~1.3 GB 缓存 `.cache/malecns/weights.npz`（本机不存在；ci.yml:3 自述） | CI 侧配置缓存（属外部前置，未解锁不构成缺陷） |

> ⚠️ **行动 2 与行动 3 不是「谁先谁后」**：二者改同一个 `.github/workflows/ci.yml`，因此关系是「**同批提交，无拓扑顺序**」。
> T3 曾判定二者构成循环依赖（F3），已在主计划中统一为单向措辞并扩展到行动 11。

---

## 3. 范围决策点：本次仅交付计划文档，实现需另行批准

### 3.1 本次交付边界（明确不含代码实现）

| 类别 | 本次（T0–T4） | 说明 |
|---|---|---|
| ✅ 已交付 | 事实核验（`00-facts.md`）、论断核对（`01-reconciliation.md`）、独立验证（`03-verification.md`）、执行计划（`fly64_execution_plan_v2.md`）、本摘要（`04-final-summary.md`） | 全部为**文档与审计**产物 |
| ⛔ **明确未做** | 12 项行动中的**任何实现**：新增脚本/测试、改 `main.py`/`model.py`、改基线 JSON、改 `.github/workflows/ci.yml`、新增 `sm64_watchdog.sh`、装 playwright、改 web 前端 | 需**另行批准** |
| ✅ 保证 | 未改动任何被跟踪文件：`git diff --stat` = 空、`git diff --cached --stat` = 空；仅新增 5 个未跟踪文件/目录（4 个 `docs/` 文档 + `.omo/`） | 每个任务执行后均 `git restore` + `git clean -fd` 复原被 pytest 污染的工作树 |

### 3.2 若要启动实现：必须进入的执行质量模式

建议**按行动拆成独立任务**，每个任务走完整五段式，**不得跳段**：

```
requirements → implementation → verification → review → integration
```

| 阶段 | 本项目的具体落点 | 门禁产物 |
|---|---|---|
| **requirements** | 从 `docs/fly64_execution_plan_v2.md` 的行动 N 抽出「目标与动机 + 涉及文件 + 实施步骤 + 可客观判定的验收标准」；**verdict=pass 必须提交 `findings` 为空** | 该行动的验收标准清单（须逐条可客观判定，禁止「行为正常」这类不可判定表述） |
| **implementation** | 只改该行动声明的「受控改动」文件；**必须提交 `changedPaths`（限定在行动的文件表内）与 `acceptanceResults`/`commandsRun`** | 改动文件集 ⊆ 行动「涉及文件」表；`git diff --stat` 只含该集合 |
| **verification** | 逐条跑行动的「验证命令」，记录**真实退出码 + 原始输出**；对照行动「验收标准」 | 每条命令的 exit code 与输出摘要；**含 pytest 的行动必须附 §4.1 强制清理四行**并证明 `git diff --stat` 已复原 |
| **review** | 由**非实现者**独立复核：路径是否真实存在、命令是否真能跑通、数字是否与仓库实测一致（照 T3 的 5 条独立路径方法） | verdict=pass 才放行；`needs_revision`/`reject` 必须**失败该任务并提交结构化 findings** |
| **integration** | 合入后复跑门禁：`check_regressions.py` 的 `NEW failures = 0`（或仅 KPI 那 1 条，直至行动 8 完成）；CI 绿；`git status` 回到「原始未跟踪 + 本批次产出」 | 最终 `git diff --stat` 与该行动「涉及文件」表一致；无夹带改动 |

**两条必须写入每个实现任务的硬约束**：

1. **禁止提高 KPI 预算**：`fly64/tests/test_p1_neural_takeover.py` 的 `KPI_LINES` / `KPI_ASSIGNMENTS` **必须保持 26**。为让测试变绿而提高预算 = 作弊（行动 8 验收标准 6 已列为禁止项）。
2. **禁止把真缺陷降级为环境问题**：基线里的 `real-bug` 2 条（`test_launcher_lock_blocks_duplicate`、`test_flow_computation_performance`）在 `--update` 时**必须保留「真缺陷」note**，不得改写为 `environment`。

### 3.3 建议的实现启动顺序（与 §2.2 一致）

```
批 1（可并行）：行动 2 ∥ 行动 3（同批提交 YAML）∥ 行动 1 ∥ 行动 7 ∥ 行动 5 ∥ 行动 9
批 2（串行）：  行动 4 → 行动 6
批 3（独占）：  行动 8（3–4 个子批次，每批 ≤6 处写点）
批 4（并行）：  行动 10 → 行动 12 ∥ 行动 11
```

**建议最小配置 2 人**：一人负责 P0（批 1 的行动 2/3/1）+ 行动 8；另一人负责行动 5/7/9/4/6/10/12/11。

### 3.4 一个不在 12 项内、但强烈建议单独立项的事项

`fly64/.pytest-run/` 有 **132 个文件被 git 跟踪**且未被 `.gitignore` 忽略 → **跑一次 pytest 会让 `git status` 从 3–5 条涨到 102–118 条**。
它是本计划**每一个**「跑测试」类验收的可复现性障碍。根治成本极低（从 index 移除 + 写入 `fly64/.gitignore`），但属仓库卫生改动，**本轮仅记录，不实施**（避免范围混淆）。
另：`fly64/.tmp/` 下有 **59 个一次性 `.sh`** 诊断脚本，属历史噪声，可一并评估归档。

---

## 4. 本次未验证 / 未覆盖的事项（明确列出，禁止外推）

### 4.1 硬限制：本机（Windows）**无法**验收 —— 共 5 项

| # | 项 | 为什么不能 | 由谁/如何验收 | 计划是否已自我声明 |
|---|---|---|---|---|
| U1 | 行动 1 的**运行态**：kill SM64 后 ≤60 s 自动重启、`bridge_stale` ≤30 s 转 `false` | 无 WSL/SM64 进程；`bash` 在 Windows 默认不可用 | **WSL 侧**：`pkill -f "sm64.us.f3dex2e"` 后观察 `pgrep -f "us_pc.*skip-intro"` 与 `/flow.json` 的 `bridge_stale` | ✅ 已声明「待 WSL 验证」 |
| U2 | 行动 8 的**真实运动行为不退化**（撞墙/卡死/不跳/跌落） | 需 WSL 实机 ≥10 min 会话观察 | WSL 侧跑 ≥10 min 会话，对比改动前后的速度/跳/跌落/卡死计数 | ✅ 已声明 |
| U3 | 行动 10 的 `/evolution-health.json` 返 **200**、主循环 tick **不被阻塞** | 需大脑进程在跑 | 启动大脑后 `GET` 该端点 + 观察 tick 计数 | ✅ 已声明 |
| U4 | 行动 11 的 **CI 实际执行**（GitHub Actions 上的 linux 门禁结果、`--ignore` 解禁后的耗时） | 无法从本机触发 CI | 触发一次 push/PR，附 CI 日志链接 | ✅ 已声明 |
| U5 | 行动 12 的 **Playwright 渲染级门禁与截图 diff**（4 视口 G1–G4、像素比对） | `playwright` **未安装**（实测 `find_spec` = False；需网络 ~150 MB） | 安装后跑 `layout_audit.py`；本机可先交付**文本级契约层**（零依赖） | ✅ 已声明 |

> ⚠️ **U5 已部分提前验证**：T3 实跑 `layout_audit.py` → exit 1、`ModuleNotFoundError: No module named 'playwright'`（`:52`）。**这确认了「未安装」这一前置事实本身**，但不构成渲染级验收。

### 4.2 范围外：本次**未覆盖** —— 共 4 项

| # | 项 | 原因 | 影响 |
|---|---|---|---|
| N1 | `export logs/` 下 **10 个 zip 的内容**（会话身份、`211 条 CJK 消息`、`41 MB`、`16 个子代理背书`） | **未解包**（10 个 zip，解包会显著扩大范围并污染工作树） | 报告「7 会话」的内容维度**完全未验证**；只能确认文件名层面 10 zip / 9 session id |
| N2 | 报告 7 个会话的**短 id 归属**（`a909a5cd / 9e9d4023 / 047eec9d / 493fe29d`） | 同上（这 4 个 id 不出现在任何文件名中） | 会话维度无法仅凭文件名复核 |
| N3 | **P4-P6 仪表板面板**是否齐全、报告 L206 的 4 个短 commit（`661b939→a30dfbb→cd555f8→d9bd246`） | 需逐面板核对 + `git cat-file` 消歧（未给出仓库/分支上下文） | 报告的「P4-P6 后续」无法证实/证伪 |
| N4 | 报告的 **LSP 状态**（L238） | 全仓库（排除 `.venv`/`.git`/`node_modules`）穷举 `pyright\|ruff\|mypy\|\.lsp\|pylsp\|basedpyright` **命中数为 0** | 判定为**表述问题**（「LSP」疑为「测试」之误），该行**不可验证** |

### 4.3 交付物本身尚未可验证的部分

| # | 项 | 说明 |
|---|---|---|
| D1 | 表 C 的 **13 项「待新增」资产的可运行性** | `sm64_watchdog.sh`、`baseline_tool.py`、`replay_curriculum.py`、`test_*` 等**尚不存在**（T3 已逐条 `Path.exists()` = False 确认）→ 属**交付物**，不是验证对象。其可运行性只能在**各自实现任务**中验收 |
| D2 | 行动 11 验证(1) 的 `--report` 对**含失败行**报告的解析 | T3 预演时报告文件 **0 失败行**，只验证了参数与路径可用（exit 0）。`FAILED_RE = ^FAILED\s+(\S+)` 的匹配能力**未用真实失败行验证** → 建议在实现任务中补一次含失败行的预演 |
| D3 | `fly64/scripts/layout_baseline/` 截图基线 | 待新增，且其内容依赖 U5（playwright） |
| D4 | 本次 T4 的 18 条修订**未经独立复核** | 按团队规则「不得自审」，本摘要的修订有效性**应由 reviewer 独立复核**（复核方式见 §5.3） |

---

## 5. T3 验证发现项处置（20 条逐条）

### 5.1 处置汇总

| 严重度 | 条数 | 已修 | 标注为已知限制 | 备注 |
|---|---|---|---|---|
| blocker | 0 | — | — | — |
| **high** | 3 | **3** | 0 | F1 / F2 / F3 由 Captain takeover 修复，**本次 T4 全部端到端复跑确认** |
| **medium** | 10 | **8** | 2 | F4/F7/F10/F11/F12 由 Captain 修；**F5/F6/F8/F9/F13/F14 中 F13/F14 由 Captain 修、F5/F6/F8/F9 由本次 T4 修** |
| **low** | 7 | **7** | 0 | F15–F20 由 Captain/本次修完（含 T4 新修 F16/F17/F18/F19/F20） |
| **合计** | **20** | **18** | **2** | 见 §5.2 的两条已知限制 |

### 5.2 逐条处置表

| id | 严重度 | 问题摘要 | 处置 | 复核证据 |
|---|---|---|---|---|
| **F1** | high | 行动 7 验证(2) exit 1：`heading_column()`/`anchor_distance()`/`anchor_return_bearing()` 是 `@property`，带括号报 `TypeError: 'int' object is not callable`（6 处扩散） | ✅ **已修**（Captain，6 处去括号） | **T4 端到端复跑**：`cx ok 12 0.0`，**exit 0**；全文不再出现三者的 `()` 形式 |
| **F2** | high | §0.2「复制即用」块 exit 1：PS 5.1 的 `@'…'@` here-string 向原生程序传参时剥离双引号 → Python `SyntaxError` | ✅ **已修**（Captain，改 `Set-Content` 临时文件 + 加 PS 5.1 注记） | **T4 端到端复跑该块原文**：输出 `38/38/38`、`24/24/24`、`intersection 22 / win32-only 16 / linux-only 2`，**exit 0** |
| **F3** | high | 行动 2 与行动 3 循环依赖（2→3 且 3→2） | ✅ **已修**（Captain，改「同批次提交，无拓扑顺序」） | **T4 复跑**：`'依赖行动 3' in doc` → **False**；并**扩展修复行动 11 的同源措辞**（原仍写「依赖行动 3」） |
| **F4** | medium | `fly64/plugin/` `.py` 数与实测不符（写 8，实为 7） | ✅ 已修（Captain） | 文内已为「实有 7 个 .py」 |
| **F5** | medium | `fly64/.tmp/` 的 `.sh` 数与实测不符（写 55，实为 59） | ✅ **本次 T4 已修** | 实测 `(Get-ChildItem fly64/.tmp -Filter *.sh -File).Count` = **59**；文内已改为 59 并附采集命令 |
| **F6** | medium | 「`brain_tunable_params.json` 中**没有任何** `DAN_*`/dopamine 键」被仓库否证（含 `exploration.dopamine_revisit_cost`） | ✅ **本次 T4 已修** | 改为「**无任何 `DAN_*` 键**；dopamine 相关键**仅 1 个** `exploration.dopamine_revisit_cost`（`wired: false`，且 `default 0.5` 越界 `[0, 0.4]`）」 |
| **F7** | medium | §4.2 表 A 标题「共 76 条」与表体 84 行不符 | ✅ 已修（Captain） | 文内已为「共 84 条」 |
| **F8** | medium | §0.1 称 `brain_version` 最大值 = `2.23.6`，但 §0.2 命令实测输出 `max: None`（3 条字面量 `"None"`；字典序最大为 `None`/`2.9.1`） | ✅ **本次 T4 已修** | §0.1 改为「**语义最大值 = 2.23.6**（排除 3 条 `None`，须按 `(major,minor,patch)` 排序）」；§0.2 命令改为 `re.fullmatch(r"\d+\.\d+\.\d+")` 过滤 + 元组排序，**端到端复跑 exit 0**：`records 79 / unique 51 / None 3 / semantic max 2.23.6 / >=2.23.7 []` |
| **F9** | medium | 行动 8 写点区间 `1336-1338` 展开为 37 项，与「36 行」矛盾（1337 实为 `if control.y < 8:`） | ✅ **本次 T4 已修** | 改写为 `1336, 1338`（2 处：涉及文件表 + 决策类清单），并补注「1337 非写入行」；实测 `main.py:1336/1337/1338` 原文确认 |
| **F10** | medium | `DopamineGainController` 行号错（写 `:84`，类定义在 `:56`） | ✅ 已修（Captain） | 文内已为 `@ :56` |
| **F11** | medium | B7b 的 gitignore 结论错误：称 `plugin/*.log` 未被忽略（实测 `*.log` 已忽略） | ✅ Captain 修了一半，**本次 T4 补修另一半** | 实测：`git check-ignore -v fly64/plugin/watchdog.log` → **rc=0 命中根 `.gitignore:23 *.log`**（`service.log` 同）；但 `*.pid` → **rc=1（未被忽略）**。Captain 版仍写「`*.pid` 同理/无须额外配置」= 与实测相反，**已改写为「`.pid` 实测 rc=1，行动 1 应在 `fly64/.gitignore` 增加 `plugin/*.pid`」** |
| **F12** | medium | 工作量上限之和 38.0 与合计 36.5 不符 | ✅ 已修（Captain，改 18.5–33.5） | 文内合计为 **18.5–33.5 人日**（与各项和 21.5 下限/38.0 上限的**并集口径**差异**保留为已知限制**，见下） |
| **F13** | medium | §3.1 关键路径把行动 8 排在行动 4/6 **之前**，与其紧邻说明及批次表相反 | ✅ 已修（Captain） | **T4 复跑**：全文「关键路径」仅 1 处，现为 `行动 2 → 行动 4 → 行动 6 → 行动 8`，并附「必须排在行动 4/6 之后」的理由 |
| **F14** | medium | §4.1 称 `--basetemp` 可限污染（实测 **不成立**），且清理模板被写作「降级方案」 | ✅ 已修（Captain） | 文内已写明根因（`test_regression_detector.py` → `check_regressions.py --run_pytest` **硬编码 `ROOT/.pytest-run`**），并把四行清理模板标为「**强制执行，不可跳过**」 |
| **F15** | low | `apply_strategy_update` 行号差 1（写 `:758`，实为 `:757`） | ✅ **本次 T4 已修** | 实测 `Select-String`：`:757 def apply_strategy_update`、`:807 def load_active_strategy` |
| **F16** | low | `test_p1_neural_takeover.py:228` 的 `pre-P1: 45 / 53` 实为 `:229` | ✅ **本次 T4 已修** | 改为 `:229`（并注明 `:228` 是 `P1 baseline (2026-09-14): 18 lines / 18 assignments`） |
| **F17** | low | 称 `service.py:94` 是 `bridge_fresh` 健康检查；实为 `check_bridge()`（`:89`），`bridge_fresh` 仅是 `:9` docstring 里的键名 | ✅ **本次 T4 已修** | 实测：`:9 * ``bridge_fresh`` …`、`:89 def check_bridge(self) -> dict:`；文内改为「`service.py:89-95 check_bridge()`（键名 `bridge_fresh`，见 `:9` docstring）」 |
| **F18** | low | 行动 10 验证(1) 用管道且要求判 exit 0（`Select-Object -First` 使 `$LASTEXITCODE = -1`） | ✅ **本次 T4 已修** | 改为 `& $py scripts\measure_evolution_health.py --json > $null; "EXIT=$LASTEXITCODE"` 作判定，管道版另列仅用于查看；**端到端复跑 exit 0** |
| **F19** | low | `.cache/malecns/weights.npz` 未纳入 §4.2 核对表 | ✅ **本次 T4 已修** | 新增 **B7c** 行（本机 `Test-Path fly64/.cache` → `False`，属 CI 侧外部前置）；表 B 现 13 行、标签唯一性已校验 |
| **F20** | low | §0 路径约定称「所有路径一律仓库根相对、可直接复制进命令」，与 33 个仅在 `fly64/` 语义下存在的 token 矛盾 | ✅ **本次 T4 已修** | 改写为「**两套并存**」并显式分开：正文/表格用仓库根相对，**命令块内**用 `fly64/` 相对（因命令块 cwd 已固定）；加「复制命令必须连同 `# cwd = …` 一起复制」的警示 |

### 5.3 两条保留为「已知限制」的条目（非阻塞，已文档化）

| id | 保留原因 | 已知限制的准确表述 | 建议 |
|---|---|---|---|
| **F12（口径）** | 修订后的合计 **18.5–33.5** 是「批次并集/最长线」口径下的收敛值；若按 12 项工作量**逐项相加**则下限 21.5、上限 38.0。两种口径都成立，但**不能混用** | 「合计 18.5–33.5 人日为**并行批次口径**（按批次最长线）；逐项相加口径为 21.5–38.0 人日。两者分别回答『日历工期』与『总人力投入』两个不同问题」 | 实现启动时按实际人力配置复核一次；若单线串行则用 **21.5–38.0** |
| **D4（自审限制）** | 本摘要的 18 条修订**由计划撰写者执行**，按团队规则「不得自审」**未经独立复核** | 「§5.2 的 18 条修订由 plan-writer 自验（每条附实测命令与输出），**尚缺独立的第三方复核**」 | **reviewer 独立复核的最小集**：① 复跑行动 7 验证(2) 与 §0.2 两块（确认 F1/F2/F8 的 exit 0）；② `grep '依赖行动 3'` 应为空（F3）；③ `Select-String -Path fly64\main.py -Pattern '^def apply_strategy_update'` 应为 `:757`（F15）；④ `git check-ignore -v fly64/plugin/x.pid` 应为 rc=1（F11） |

---

## 6. 交付物清单（可点击路径）

| # | 文件 | 规模 | 角色 |
|---|---|---|---|
| **主交付** | `docs/fly64_execution_plan_v2.md` | **1610 行 / 136833 bytes**（T4 修订后实测） | **Fly64 下一步执行计划 v2**（12 项行动，P0–P3，含路径/命令/验收/依赖/排期） |
| 支撑 1 | `docs/analysis/plan-v2/00-facts.md` | 788 行 / 40472 bytes | T0 仓库事实核验与基线采集（每个数字带命令+原始输出） |
| 支撑 2 | `docs/analysis/plan-v2/01-reconciliation.md` | 435 行 / 52409 bytes | T1 报告论断核对与偏差清单（32 条 + 8 项基础设施 + 8 项未验证） |
| 支撑 3 | `docs/analysis/plan-v2/03-verification.md` | 580 行 / 48001 bytes | T3 独立验证（212 路径 / 36 命令 / 40 数值 / 200 行号；20 条发现项） |
| 支撑 4 | `docs/analysis/plan-v2/04-final-summary.md` | 本文件 | T4 最终交付与决策摘要（偏差摘要 / 排期与起手项 / 范围与质量模式 / 未验证项 / 发现项处置） |
| 历史版本 | `docs/fly64_execution_plan.md` | 676 行 | **保留为历史版本，不删除、不修改**；已被 v2 取代（v2 文首注明） |
| 被分析对象 | `docs/fly64_export_logs_analysis_report.md` | 314 行 | 原始分析报告（其 §5 的 12 项行动表已被 v2 取代） |

> 所有交付物均为**未跟踪新文件**（`??`）。本次 T0–T4 全流程未改动任何被跟踪文件：`git diff --stat` = 空、`git diff --cached --stat` = 空。

---

## 7. 结语与建议的下一步

1. **计划已可执行**：路径经 145–212 个 token 实测核查、命令经 36 条实测、数字经 40 项对账、行号经 200 条比对、覆盖性 12/12 无丢失。T3 的 3 条 high 已全部修复并端到端复跑通过。
2. **建议立即启动批 1 的 6 项**（行动 2、3、1、5、7、9），其中**行动 2 先行**（全局瓶颈），**行动 3 与 2 同批提交 YAML**。
3. **建议单独立项**（不在 12 项内、但成本极低收益极大）：`fly64/.pytest-run/` 的 index 清理与 `.gitignore` 补丁 —— 它会一次性消除本计划**所有**「跑测试」类验收的可复现性障碍。
4. **实现阶段的两条红线**：不得提高 `KPI_LINES`/`KPI_ASSIGNMENTS`（保持 26）；不得把基线中的 2 条 `real-bug` 降级为 `environment`。
5. **本摘要的 18 条修订单（T4）尚缺独立复核**（§5.3 D4）——建议 reviewer 按 §5.3 给出的 4 条最小命令集复核后，再转入实现阶段。

---

*文件结束。本摘要整合 T0/T1/T2/T3 四份产物与 20 条验证发现项，处置结果：已修 18 条、明确标注已知限制 2 条、blocker 0 条。*
