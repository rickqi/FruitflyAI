# 盲区分析：2026-09-23 09:58 → 2026-09-26（export logs 未覆盖窗口）

> **分析者**: `gap-analyst`（AgentTeams `fly64-blindspot-0923-0926` / task `t2`）
> **attempt_id**: `93bd4705-74ed-4c9e-939c-7bef2f092910`
> **分析时刻**: 2026-09-26 12:37 → 12:52 (+0800)；`date` = `2026-09-26 12:37:11 +0800`（WSL 实测）
> **基线 HEAD**: `fbcc3d7`（2026-09-26 12:28:02 +0800）
> **主数据源**: `docs/analysis/blindspot-evidence-0923-0926.md`（t1，469 行，**本报告未修改该文件**）+ 我在同一时段的**独立复现**（git / WSL 运行时 / 活体 HTTP / 代码逐行）
> **对照基准**: `docs/analysis/session-log-analysis.md`（§4.2 的 12 例模式清单、§5 的 5 项困境）、`docs/analysis/session_logs_analysis_v5.md`（§4 的 5 项困境）
> **证据纪律**: 每条标 `[实测]`（附命令与原样输出）/ `[推断]`（附推断链与置信度）/ `[未验证]`。**本报告不引用 export logs 时期已知失真的聚合计数**（`toolCallTotal`/`toolCalls` 122×）；凡涉及计数均由我在本机从 git / 文件系统 / 活体重算，并给出口径。

---

## 0. 摘要（TL;DR）

1. **窗口在解决什么**：三条线——① **运动/门控信号通路工程化**（`2f87d77` motor-pool 恢复 + gate Hz 单位契约，09-23）② **让自适应信号真正生效**（`f486ad0` 教练钳位可见性、`38c8bae` 信用分配矩阵、09-25 的 SP1–SP5-A/P0-1~P0-4）③ **运行环境与渲染**（`78b3175` 本地 vLLM、`fbcc3d7` WSLg 渲染）。窗口内 **12 个提交**，但**绝大部分产出（含 09-25 已验收交付）不在 HEAD**。
2. **模式复查（重点）**：对照已交付的 12 例「机制存在、报告成功、无法生效」清单，**本窗口再现同族缺陷 13 例**（工程侧 10 + 分析工作侧 3），归为 **7 类根因**。其中 **4 例是历史清单未覆盖的新增子型**（守护脚本缺调度、守卫脚本自身无断言、生产者键被删+消费者默认值兜底、规格承诺的验证信号从未存在），其余 9 例为同族延伸。
   > **t5 返修（M-2/RC 裁定）**：原值 **12 例（RC-4 = 1，仅 E5）→ 更正为 13 例（RC-4 = 2，+ E13 = `stuck_score`/`rate` 子信号观测层实例）**。队长已裁定计入；该例属 RC-4 的**新实例**（与 A3 是**同族症状、不同判据**），并与 RC-5 叠加（只改阈值与注释、未改 docstring 的 Hz 表述、未加运行时断言）。详见 §3.2-E13、§3.3。
3. **独立复核确认 t1 全部关键结论**，并另给出 **4 条 t1 未报的新发现**（E2 由队长补充指出、我已独立复现；E7/E8/E9 为我本轮新发现，见 §3.2）：`gate_jump` 生产者键被删而消费者 `default=False` 静默兜底；部署清单承诺的 3 个验证信号中 `burst_active` 从未发布、`evo_loop_stale` 全仓无实现；`evolution_skill.py` 工作区与活体 **md5 不同**（P0-2/P0-4 不在活体）；`flow.no_progress_gate` 与 `memory.progress_ineffective` 同一时刻取值相反。
4. **困境更新**：对两组各 5 项困境逐条判定 —— **A3 拆为两句**（① **单位标注对齐 ✅ 已解决** ② **「不再 ≡1.0」✘ 不成立**，与已交付结论仅在①上冲突，见 §4.1-A3/§4.4-C1）、**1 项未恶化**（`control.x` 写点：原报「10→12 恶化」→ **实测 10/14/16/17，窗口前后同为 10 ⇒ 未恶化**，见 §4.1-A4）、**1 项结论需更正**（CX-2「无视觉闭环校正」不成立，机制已存在）、其余仍存在或仅部分缓解；并**新增 3 条困境**（版本/记录一致性守护失效、窗口产出未入库、活体-工作区漂移）。
   > **t5 返修**：本轮按 t4 核验报告（`blindspot-review-0923-0926.md`）处置 M-1~M-5 与两处新遗漏，逐条留痕见 **§8 返修记录**。
5. **最危险的单点**：规则 8 的指定校验器 `fly64/tests/check_version.py` 是 **4 行空壳**（无比较、无 assert、不读 skills/canonical、硬编码 WSL 路径），WSL 侧**恒 exit 0**、Windows 侧**以 `ModuleNotFoundError` exit 1** —— 专门用于防版本漂移的守卫自身失效，这才是 `canonical skill 3.4.2` 未被拦截的直接原因。

---

## 1. 窗口定界与方法

### 1.1 窗口边界 `[实测]`

```bash
git log --since=2026-09-23 --until=2026-09-27 --pretty=format:'%h|%ad|%s' --date=iso | Measure-Object -Line
# → 12
```

`--since=2026-09-23` 会多带回 8 条 09:58 之前的提交（已由 export logs 分析覆盖，见 t1 §0）。**本窗口首个提交 = `78b3175`（09-23 12:42:27）**；窗口内提交分布：09-23 六 / 09-24 三 / 09-25 二 / 09-26 一。

### 1.2 本次分析方法

| 步骤 | 做法 |
|---|---|
| 复现 | 对 t1 的每条关键结论**独立跑一遍命令**，只把复现通过的写入本报告 |
| 归因 | 每条证据映射到「解决了什么问题 / 改动位置 / 验证方式 / 当前状态」四元组 |
| 模式复查 | 以 `session-log-analysis.md` §4.2 的 12 例为**清单基准**，先重定义该家族的可判定特征（§3.1），再逐条判定，最后做去重与根因分类 |
| 困境更新 | 分别对 A 组（`session-log-analysis.md` §5）与 B 组（v5 §4）逐条判定「仍存在/已缓解/已解决/新增」 |
| 交叉核对 | 凡与已交付结论冲突处单列（§4.4），并给出可复现依据 |

### 1.3 家族命名的重要澄清（避免误读）

项目内「RULE-19」有**两种用法**，本报告据实区分：

- **代码级 `RULE-19`**：`fly64/fly64/main.py:765-790` 自述的 **motor-pool rate 单位契约**（per-tick fraction ⇄ Hz，混用即静默失效），`contract_registry.json` 记有零容忍条目 `RULE-19k`。`[实测]`（我读了该注释块原文）
- **`agent.md` 规则 19**：同文件 `:38-42` 定义为「**演化证据基座不可破坏**（证据不受损）」，其分工说明明确写「规则 19 管'证据不受损'，规则 20 管'回归可探测'——共同堵住'机制存在、报告成功、无法生效'的盲区」。`[实测]`

**本报告采用的判定对象**（与团队目标一致）：**「机制存在、报告成功、无法生效」缺陷族（项目内部编号 EVO-066 族）及其 RULE-19 单位/契约子族**。历史命名链：EVO-066（09-17 契约审计，系统化命名该族）→ EVO-072（09-22，被记为「该族第 7 例」，RULE-19 契约审计发现）→ 点号死键第 8 例（`session_logs_analysis_v4.md:282`）/ `sp2-completion-report.md:18` 又把 gate 单位迁移记为「RULE-19 第 8 例」。
⚠️ **诚实标注**：项目自身对「第 N 例」的计数存在**两套并行编号**（家族例数 vs RULE-19 单位案子数），互相冲突。故本报告**不使用**「第 N 例」编号，改用**独立编号 E1–E12** 并逐条给证据，避免叠加历史编号歧义。

---

## 2. 该窗口解决的问题（逐项归因）

### 2.1 窗口内 12 个提交逐条归因

| # | 提交（时间 +0800） | 解决了什么问题 | 改动位置 | 验证方式 | 当前状态 |
|:-:|---|---|---|---|---|
| 1 | `78b3175` 09-23 12:42 | Coach LLM 后端从 GLM-5.3-flash 切到本地 vLLM `qwen3.8-27b-uncensored`；monitor 恒显实调模型（型号不可见问题） | `plugin/manifest.json`（DEFAULT_MODEL）、monitor 标签；`llm.env`(gitignored, root-only) | 提交信息自述「verified chat OK」`[实测]`；**侧证**：`agent.md:77-78` 记录型号串 `glm-5v-turbo→qwen3.8-27b-uncensored` 漂移导致 `test_plugin_mhr` 2 条 NEW 失败（登记 `cause=test-drift`）`[实测]` | **已闭环**（配置）。⚠️ 部署动作本身**未入库**，只在提交信息留痕 |
| 2 | `506e87a` 09-23 12:52 | dashboard 全局 `.evo-cap` 溢出（两列模式最多溢出 386px） | web/ dashboard 2 文件 | 提交信息逐分辨率自述 0 overflow `[实测-文]` | **已闭环**（无自动化断言） |
| 3 | `5dba6fe` 09-23 12:58 | 固定行高裁剪内容（163–300px）；escape 表 110→400px | 同上 2 文件 | 同上（1920/1400/1100/800/640 五档）`[实测-文]` | **已闭环** |
| 4 | `2f87d77` 09-23 20:51 | **forward 池贴顶 46–50Hz / steering 池恒 0Hz / `gate_jump` 恒假** 三病；并把 gate 阈值统一到 Hz 域 | `model.py`(+399/−28)、`main.py`(+95)、`brain_tunable_params.json`、`contract_registry.json`(v1.1.0 + `RULE-19k`)、`evolution_history.json`(EVO-073)、`known_failures.win32.json`(+10 = 2 条 test-drift) | 分模块 44+66+148 passed；契约审计 21/21 PASS；规则 20 门禁 exit 1（2 条 test-drift，非本轮引入）`[实测-文]`。**我的活体复核**：`forward_rate_hz` 3.85–15.38（不再恒 46–50）、`gate_jump_ratio` 6 次采样中 **4 次 > 阈值 0.75**（2.25/1.0/1.0/1.0）`[实测]` | **机制已闭环（活体确认 gate 可达）**；行为改善部分见 §6-U3 |
| 5 | `4ba5f11` 09-23 22:50 | 「教练建议被钳掉且全程无遥测可见」的根因定位（P0-4 实机验证） | `docs/analysis/analysis-p0-4-live-verification.md` | 文档内实测：`/memory.json` 无 `coach_applied` `[实测-文]` | **已闭环**（定位）；修复落到 #6 |
| 6 | `f486ad0` 09-23 23:59 | P1-1 钳位可见性 + P1-2 契约对齐 + 死键根治 + 测试隔离 | `fix_template_interpreter.py` 系列、`main.py` 钳位发布 | 提交含测试 `[实测-文]`；**我的活体复核 → 部分生效**（见 §3.2-E5/E6） | **部分**（3 项承诺未达成） |
| 7 | `cca6664` 09-24 12:35 | `is_manual` 启发式误判 + `_call_llm_subagent` 空实现 | 274 增/33 删（含测试） | 提交含测试 `[实测-文]` | **已闭环**（提交级；活体路径未复核） |
| 8 | `6655288` 09-24 18:25 | auto/wide 布局错位根因：events 面板内容涨到 1008px 撑破 505px 行 | 26 增/3 删 | 5 分辨率 + 0 overflow 自述 `[实测-文]` | **已闭环** |
| 9 | `ab2761c` 09-24 21:28 | 自治进化方案复核新增 F13–F15/V22/R13：**F13 为 blocker 级** —— 方案把 `gate_jump_threshold` 由 Hz 改 ratio 却漏列 RULE-19 契约影响面（至少 4 条 PIN 必红） | `fly64-autonomy-evolution-plan.md` +1122 | 基于 HEAD `cca6664` 逐行核对 `[实测-文]` | **已闭环**（文档）；其修法在 09-25 落地（#10、未入库交付） |
| 10 | `833848c` 09-25 20:30 | 日志分析 v5 + 执行方案：三条独立工作线收敛到同一根因，并生成 P0-1~P0-4 | 5 文件 721 增 | 文档 + 下游交付 `[实测-文]` | **已闭环**（文档）；其 §4.4/4.5 困境仍活跃（§4.2） |
| 11 | `38c8bae` 09-25 21:18 | P0-1 信用分配矩阵 + P0-3 EVO 闭环存活与停摆告警（+`_captain_verify_t3.sh`） | `evo_liveness_guard.py`(+407)、`evo_loop_launcher.sh`(+211)、2 报告 | 矩阵 134 写点/6 断口（AST）；守护 4/4 验收（手工 kill→red→green，`--threshold 30`）`[实测-文]` | **P0-1 已闭环；P0-3 部分**（守护未接调度 → 见 E1） |
| 12 | `fbcc3d7` 09-26 12:28 | WSLg D3D12 GPU 直通渲染极慢 → vsync off + MESA swrast | `sm64config.txt`、`README.md`、**`evolution_history.json`(+115/−39)** | **我的活体快照**：`render_ms = 6.118`、`bridge age_ms = 16.59` `[实测-单点]` → 修复有效 | **渲染修复已闭环**；⚠️ **同提交引入历史/版本回归**（E3，另见 §4.4）。数字口径更正：`git show fbcc3d7 --numstat` = **115 / 39**（t1 的「+154/−41」中 154 是 `--stat` 图形总数=115+39，口径不同不算矛盾；队长补充的「+137/−41」我**无法复现**，见 §6-U11） |

### 2.2 未进入提交的产出线（窗口的真实工作量）

`[实测]`（`git status --porcelain` 与服务同一时点）

- **已跟踪但未提交**：**36 个文件，+4890/−469**（剔除 `fly64/.pytest-run`、`.tmp-pytest`）。最大项：`fly64/skills/evolution_skill.py` **+2485/−70（合计 2555 行变动）**、`memory.py` +482/−25、`instinct_bindings.py` +262/−17、`main.py` +240/−35。
- **未跟踪**：**63 项**（其中路径含 `tests/` 者 19 项，含 `?? tests/` 整目录）。含 `docs/execution/**` 11 份、`docs/analysis/**` 18 份（+2 份 blindspot 文档 = 20）、`fly64/skills/{fix_executor.py, fix_guard.py, param_authority.py, evo_funnel_alarm.py, param_wiring_ab.json}` 等。
- **产出清单（我重算，含对 t1 的三处数字更正）**：`docs/analysis/**` 窗口内产出 **25 份**（+ t1 证据文档与本报告 2 份 = 27 份；t1 的 25 份统计**不含**其自身与本报告）。25 份的入库状态实测：**18 份未跟踪**、**1 份已跟踪但未提交**（`session_logs_execution_plan.md`，` M`）、**6 份已提交且干净**（`analysis-p0-4-live-verification.md`、`fly64-autonomy-evolution-plan.md`、`session_logs_analysis_v5.md`、`session_logs_execution_plan_v5.md`、`analysis-credit-assignment-matrix.md`、`analysis-evo-loop-liveness.md`）⇒ **索引中共 7 份**。
  ⚠️ **更正 t1**：t1 §2.1 写「只有 4 个文件进了 git / 其余 19 个未跟踪」却列出 5 个路径；实测为 **索引 7 份（6 已提交 + 1 未提交 `M`）/ 未跟踪 18 份**（t1 的"25"含其自身文档时计数口径亦需按 27 理解）。
  `docs/execution/**` **11 份**（**整目录未跟踪**），含 `fly64-execution-plan.md`(126KB)、`fly64-change-specs.md`(166KB)、`sp1~sp5a` 完成报告、`g4-noise-diagnosis-and-decision.md`、`w1-w4-closeout-and-h13-verdict.md`、`deploy-manifest.md`。

### 2.3 部署与跨环境同步归因（我的 md5 对照，12:37–12:45 `[实测]`）

| 文件 | Windows 工作区 | WSL `/root/fly64` | 判定 |
|---|---|---|---|
| `fly64/main.py` | `a79fe51de2c7` | `a79fe51de2c7` | ✅ 一致 |
| `memory.py` / `model.py` / `central_complex.py` / `instinct_bindings.py` / `mushroom_body.py` | `3f9dc7f82a14` / `7b222dbdb451` / `e66d65b63fa4` / `54b0639b90b5` / `c7a05141131a` | 同左，**逐一相同** | ✅ 一致（09-25 精选部署已落地） |
| `skills/default_patterns.json` / `contract_registry.json` | `0758f4791d16` / `d9653438959e` | 同左 | ✅ 一致 |
| `skills/evolution_history.json` | `d98c46f96e7d` | `d98c46f96e7d` | ✅ 一致 —— **即删除 EVO-072/073 的历史已同步进活体** |
| **`skills/evolution_skill.py`** | `97b178298e88`（4911 行） | `fd1ccd56af24` | ❌ **不一致** |
| `skills/active_strategy.json`（运行态） | `684003b04170` | `9e1893bf6f3f` | ⚠️ 预期不同（每轮重写） |
| `skills/{fix_executor,fix_guard,param_authority,evo_funnel_alarm}.py` | 存在 | 存在（09-25 21:05 部署） | ✅ 已下发 |

**新发现（t1 未报）E9**：`deploy-manifest.md` §3.1 记录的 `evolution_skill.py` md5 = `f895171ee477`，**现在工作区与活体两侧都不等于它** ⇒ 该部署清单的核验证据**已失效**（既不能证明"部署了什么"，也不能证明"活体等于工作区"）。结合 `evolution_skill.py` 两侧 md5 不同 ⇒ **09-25 的 P0-2（可执行 fix）/P0-4（has_fix 生命周期）改动不在活体**（`evolution_skill.py` 是它们唯一载体，见 `fly64-execution-plan.md:309`）。这与 `deploy-manifest.md` §1 自列的三条「改了源码但没同步到 WSL」同族。

部署时间线 `[实测]`：WSL `.deploy_backup/` 四个快照全部在 **09-25**（18:55 / 18:58 / 20:25 / 21:05），**09-26 无部署**；09-26 的 `runtime/sm64config.txt`（mtime 12:27）属手工同步，非部署脚本产物。

### 2.4 本窗口内**没有证据**的时段与主题（任务要求显式声明）

`[实测]`（沿用 t1 §8 并经我抽验一致）

| 无证据对象 | 依据 |
|---|---|
| **09-23 09:58 → 12:42**（2h44m） | 相邻提交 09:50:02 → 12:42:27；该区间无 commit / 无文档 mtime / 无教练帧 |
| **09-24 01:00 → 11:34**（~10.5h） | 同上 + `coach_frames` 09-23 23:50 → 09-24 11:34 空档 |
| **09-24 13:39 → 16:38**（~3h） | 相邻文件 mtime |
| **09-25 21:15 → 09-26 11:47**（~14.5h） | 五路时间戳交叉：无 commit、无部署、无 pytest 缓存更新、无 EVO 心跳、无教练帧 |
| **09-26 12:28 → 12:40** | 工作树无变化 |
| 09-25 的 P0-1~P0-4 **无 `evolution_history.json` 记录** | 我重算：`records` 中 `date ≥ 2026-09-23` 仅 **EVO-074**（09-24, kind=ops, 渲染修复）1 条；`AUTO-0023` 的 date 字段不带窗口日期（t1 按 `recorded_at` 计）`[实测]` |
| `agent.md` 09-24/25/26 **零条目** | `git log -1 -- agent.md` = `2f87d77`（09-23 20:51）；`^## 2026-09-2*` 唯一命中第 50 行（09-23 章）`[实测]` |
| `fly64/skills/skills.md` **无窗口章节** | mtime 停 09-23 20:49:25 `[实测]` |
| 09-25 P0-3 的停摆告警**无任何自动触发记录** | crontab 未挂载（见 E1）；`evo_stall_alarm.json` 仅 09-25 21:01:25 的人工自检 |
| **09-23 20:42 之后无按 test 落盘的运行产物** | `fly64/.pytest-run/**` 最后一次写入 = `test_map_persistence_roundtrip0/map.pkl` @ 09-23 20:42:16（`[实测]`，同 t1）；`.pytest_cache` 最后更新 09-25 21:08/21:15 |
| **窗口内无 CI/门禁产物落盘** | 本轮为 glob/grep 级检查，**非穷尽** → 属「未证实」而非「已证伪」 |
| 教练链路 09-24 12:04 后无文件产出 | `coach_outcomes.jsonl` Sep 24 11:35、`coach_advice.json` Sep 24 12:04（WSL 实测）；而 `flow.json.llm_decision.ts = 1790396036.32`（≈12:13）仍在更新 → 矛盾未解（§6-U7） |

### 2.5 补录（t5：t4 核验指出的两处此前**全部报告都遗漏**的事实）

> 来源：`blindspot-review-0923-0926.md` §8.2-1/2。两处均由我在 2026-09-26 13:1x 独立复现。

**(a) `evo_loop_launcher.sh` 在 git 中**无执行位**（`100644`，非 `100755`）**`[实测]`

```bash
git ls-files --stage -- fly64/scripts/evo_loop_launcher.sh fly64/scripts/evo_liveness_guard.py
# 100644 51adacdaf809995b8bdaca6f1c677c335ffc199d 0  fly64/scripts/evo_loop_launcher.sh
# 100644 ba194a7c877e6ec0ca665af6f216313b3a93fea5 0  fly64/scripts/evo_liveness_guard.py
```

- **影响**：在 WSL 上只能靠 `bash scripts/evo_loop_launcher.sh …` 显式调用；直接 `./scripts/evo_loop_launcher.sh` 会 `Permission denied`。而 `analysis-evo-loop-liveness.md` 的启动契约（`tmux new-session` + `setsid nohup`）本身要求一个**可被计划任务/启动器直接执行**的入口 —— **"部署/运行契约"缺陷，与 E1（守护未接调度）同族**，此前 t1/t2/t3 均未记录。
- ⚠️ 同时更正：`evo_liveness_guard.py` **也是 100644**（t4 只点名了 launcher；两者都没有执行位）。

**(b) `runtime/evolution_history.json` 与 `skills/evolution_history.json` 是两份不同的历史文件**`[实测]`

| 文件 | 位置 | 体积（2026-09-26 13:04 实测） | 结构与消费方 |
|---|---|---|---|
| `skills/evolution_history.json` | Windows 工作区 + WSL 各一份（两侧 md5 相同 `d98c46f96e7d`） | **99,101 B**（1600 行） | **canonical 进化契约**：`{$schema, canonical_versions, records[87]}`。消费方：`skills/evolution_skill.py:202`（`EvolutionHistory`，规则 15 写入）、`tests/test_version_consistency.py:28`（规则 8 的 brain 徽章比对）、`scripts/ver_append_*.py`。⚠️ **t7 记录数复核（2026-09-26 13:24:50 Windows / 13:24:58 WSL）**：**Windows 87 / WSL 87**，两侧 md5 均为 `d98c46f96e7d58128c5707e182ef4be2`（相同）⇒ **87 为权威读数**；**另有时点观测到 86 条**（过时读数，已作废）。该文件**随运行时追加**，任何引用都必须**注明测量时刻** |
| `runtime/evolution_history.json` | **仅 WSL 运行时**（`/root/fly64/runtime/`；Windows 工作区**不存在**） | **7,110–7,116 B**（**每轮被重写**：12:56 时 7,124 B → 13:04 时 7,110 B → 13:0x 7,116 B） | **brain 侧滚动迭代记录**：`{brain_version:"2.24.0", iterations:[…最近 ~19 条…]}`。消费方：`fly64/fly64/main.py:61`（启动时读入恢复）、`:220`/`:2360`（**写入**）、`tests/test_brain_startup_regression.py`（断言该写入形态） |

- **为何重要**：① 规则 9（进化历史持久化）与规则 15（进化记录契约）落在**两个不同文件**上，而此前 t1/t2/t3 的"记录纪律"结论**只核对了 `skills/` 那一份**；② `runtime/` 那份**每轮被覆写**（仅保留 ~19 条），意味着 **brain 侧历史是易失的、无法作为审计依据**；③ 它也解释了历史上同类事故的触发条件（`fly64/.tmp/write_evo059.py:109` 记录过"干净检出导入正常、测试全绿，而生产恒有 `runtime/evolution_history.json` ⇒ 每次启动必崩"）⇒ **该文件是"运行时独有、仓库不可见"的一类真实依赖**。

---

## 3. 重复缺陷模式复查（重点）

### 3.1 判定基准：家族特征与历史清单

**家族可判定特征**（摘自 `session-log-analysis.md` §4.1，我沿用不改）：① 机制**存在**（代码/脚本/流水线在位）；② **报告成功**（日志/测试/验收/文档声明为通过）；③ **无法生效**（实际行为、调度或数据与声明不符），且失败是**静默**的（无报错、无告警）。

**历史清单（基线，不得移动）**：`session-log-analysis.md` §4.2 的 **12 例**（逃逸位移≈0、MBON 饱和、threshold 签名、Phase6 零分、策略穿透、桥接空数据、场景标签 gap、StuckDetector fallen 钉死、GLM 空上下文、loop score 饱和、骨架技能空数据、screen capture 空帧），其根因分类为：常量/签名不匹配 3、信号层解耦 4、状态未复位 2、数据未传递 2、方向互消 1。另 `session_logs_analysis_v4.md:282`、`analysis-a3-state.md:375` 把「点号死键」记为**家族第 8 例**（`active_strategy.json` 的 `escape.*` 跨段键永不被 `prefix = sec + "."` 迁移逻辑清除）。

### 3.2 本窗口内再现的实例清单（E1–E13）

> 判定口径：只有**机制在位 + 有成功声明 + 静默失效**三者齐备才计入。凡证据不足者放入 §6「未验证」，不凑数。

| ID | 实例 | 「机制存在」 | 「报告成功」 | 「无法生效」 | 强度 | 来源 |
|:--:|---|---|---|---|:--:|---|
| **E1** | **EVO 闭环守护未接入任何调度** | **`fly64/scripts/evo_liveness_guard.py`**（**407 行** / 15,863 B；⚠️ t5 更正：**不在 `fly64/skills/`**，实测 `Test-Path fly64/skills/evo_liveness_guard.py` = False）+ **`fly64/scripts/evo_loop_launcher.sh`**（**211 行** / 7,889 B）已交付（`38c8bae`；t1/t2 原写的「+407/+211」是 `git show --stat` 的**新增行数**——因两文件在该提交**新建**，新增行数 == 文件总行数，与 `wc -l` 双向印证 ⇒ **407 / 211**；⚠️ **t7 更正**：此前写的 339/179 来自 PowerShell `Measure-Object -Line` 的漏计口径，已废弃） | `analysis-evo-loop-liveness.md` 4/4 验收 ✅（手工 kill→red→green，30s 阈值） | 09-26 11:47 闭环再次死亡；`crontab -l` **只有 watchdog.sh / phase2_gate.sh**；`evo_stall_alarm.json` 最后一次检查停在 **09-25 21:01:25**（无自动运行）→ **告警没响** | 实测·高 | t1 §3.2 + 我复核 |
| **E2** | **规则 8 的版本守卫是空壳**（队长补充，我已独立复现） | `fly64/tests/check_version.py` 被 `agent.md:88` 指定为「规则 8 三处版本同步校验」的执行体 | 从未失败即被视为通过 | 全文 **4 行**：不比较、无 assert、不读 `SKILL_VERSION`、不读 canonical，且硬编码 `sys.path.insert(0,"/root/fly64")`。**WSL 实跑** `loaded BRAIN_VERSION: 2.24.0` → **exit 0**；**Windows 实跑** → `ModuleNotFoundError: No module named 'fly64'` → **exit 1（错因）** | 实测·高 | 我复现（队长指出） |
| **E3** | **进化记录被删除**（≠ 从未记录） | `evolution_history.json` 是规则 15 的强制契约载体（`agent.md:26`） | `fbcc3d7` 提交信息只写「新增 EVO-074」类渲染修复 | 同提交删除 **EVO-072/EVO-073**（`git log -S` 双向确认）并把 `canonical_versions.skill` 由 `3.5.1` 回退为 `3.4.2`；删除已同步活体（两侧 md5 相同 `d98c46f96e7d`） | 实测·高 | t1 §4 + 我复核 |
| **E4** | **09-25 四条 P0 交付从未记录 + 不在 HEAD**（≠ 记录被删） | P0-1 矩阵/P0-2 fix/P0-3 守护/P0-4 has_fix 均已交付并验收 | 各完成报告标 ✅（`analysis-credit-assignment-matrix.md`、`analysis-evo-loop-liveness.md`、`sp4-completion-report.md`、`sp5a-*`） | `date ≥ 09-23` 的记录只有 EVO-074 一条（0 条对应 P0）；且交付物在 36 个未提交文件 / 63 个未跟踪文件里 | 实测·高 | t1 §4.3 + 我重算 |
| **E5** | **钳位可见但归因未接线 + 观测点错位** | P1-1 实现了 `clamped_keys` 发布 + WARNING 日志 | `f486ad0` 声明「让 Coach 建议真正生效」 | 活体 `flow.json.clamped_keys` 的 `source` **恒为 `"unknown"`**（无法区分 coach vs evo/panel）；`main.py:1316` WARNING 与 `build_coach_applied` docstring 都指向 `/memory.json`，而实测 `clamped_keys ∈ flow.json` ✔ / `∈ memory.json` ✘（61 键） | 实测·高 | t1 §3.4 + 我复核 |
| **E6** | **契约对齐没有拦住写入方** | P1-2 声明「只接受 0–0.25，prompt 写明填 0.8 会被钳到 0.25」 | 该契约作为修复成果提交（`f486ad0`） | 12:37/12:42 两次采样 `requested=0.7` 仍持续到达（`tick` 21000/21600 递增）；写入方实测为本能绑定 promoted 桶（`scene_strategy_bindings.json` 中「致命熔岩地」的 `exploration.turn_bias=0.7` 已 `promoted=True`，`coach_applied.instinct_applied=true`） | 实测·高（写入方归因为实测+推断·高） | t1 §3.4 + 我复核 |
| **E7** | **生产者键被删、消费者默认值静默兜底**（**新发现**） | HEAD `fbcc3d7` 发布 `"gate_jump": gate_open_hz(...)` | P1-b3 的守卫测试 `test_gate_units.py:300` 已迁移并断言新键名（全绿） | 工作区（=活体）把该键**删除**，改为 `gate_jump_threshold_ratio`+`gate_jump_ratio`；消费者 `plugin/scene_context.py:234` 仍 `_get_safe(flow,"gate_jump",default=False)` ⇒ **恒 False**；测试夹具 `test_what_i_see_protocol.py:68` 自带 `"gate_jump": False` ⇒ 测试永不失败 | 实测·高（**影响面判定为低**，见下） | 我实测（git diff + 活体 + 代码） |
| **E8** | **部署清单承诺的验证信号从未存在**（**新发现**） | `deploy-manifest.md` §6 列 6 条"部署后必须验证的信号"，含 `flow.json 含 burst_active` / `memory.json 含 evo_loop_stale` | 部署报告声明成功（§11/§12 给出 0 traceback、jump 0→12/600） | 活体 `flow.json` 与 `memory.json` **均无 `burst_active`** ⇒ 精确表述为「**无 flow/memory 发布点**」（⚠️ t5 更正：原写「全仓仅出现在函数形参与读取处，**无发布点**」**与实测不符**——`main.py:2206 model.burst_active = _deadlock_burst_remaining > 0` 是**属性赋值**，但**不写入任何 HTTP 端点**）；`evo_loop_stale` **全仓 `.py` 零命中**（`fly64-change-specs.md:296` 承诺的 `high` finding 通道未实现）。同时 `terminal_surrender`/`surrender_evidence`/`stuck_duration_true`/`oscillation_adaptive_enabled` **均已发布** ⇒ 6 条中实际可达 4 条 | 实测·高 | 我实测 |
| **E9** | **`evolution_skill.py` 未同步活体，且部署清单 md5 已失效**（**新发现**） | `deploy-manifest.md` 以 md5 清单证明"已精选部署" | 09-25 四次部署 + §11/§12 前后对照 | 工作区 `97b178298e88` ≠ 活体 `fd1ccd56af24`；清单记录的 `f895171ee477` **两侧都不匹配** ⇒ 部署证据链断裂，P0-2/P0-4 不在活体 | 实测·高 | 我实测 |
| **E10** | **分析工作自身：t1 聚合计数 122× 失真** | `session-log-summary.json`（t1 抽取产物，150KB）存在 | 曾作为分析数据源 | 单会话实测 2443 条 `tool/call` 被报为 20；修复版 `session-log-summary.json`（09-24 16:38，**窗口内**）已取代该数据 | 实测·高（历史 + 窗口内修复） | `session-log-analysis.md:5` |
| **E11** | **分析工作自身：审查方 M2 错误发现（GBK 编码）** | `docs/analysis/session-log-analysis-review.md` 的审查流程在位 | round-1 逐条给出「M2 高」判定 | 其证据「`evolution_history.json` 仅 3 条记录」**不成立**（实际含 81 条，65 EVO + 16 AUTO）；根因是审查脚本用 GBK 读 UTF-8 文件，只读到了测试夹具副本。二轮已更正（`session-log-analysis-review-round2.md:26,182`） | 实测·高（已更正） | 二轮审查文档 |
| **E12** | **分析工作自身：引用校验器精度缺陷（S1/S2）** | `scripts/verify_doc_citations.py` 在位并报「15/15 通过、0 失败」 | 报告写「校验器机制可探测错误引用」✅ | 队长复测发现：S1 裸 L 计数膨胀（报 166 条，实际 `L<num>` 总数 88）；S2 符号一致性 WARN 假阳性（`memory.py` L135 被要求匹配 `central_complex.py`）⇒ **计数指标不可信、告警被淹没**；两项均不阻塞门禁而放行 | 实测·高（文档自记） | `session-log-analysis-review-round2.md` §4.3 |
| **E13** | **`stuck_score` 可达 1.0 而同刻 `stuck_duration == 0.0`（观测层假绿）**（**t5 新增**，队长裁定计入本 13 例） | `StuckDetector` 三子信号取 `max`（`memory.py:213-225`）+ 状态泄放（`:234-235`），均已在位 | P1-N1「单位文档化 + 运行时断言」被记为 ✅ 闭环；A3 判据用**单点** `stuck_score = 0.08`（＝"不再 ≡1.0"） | ① **`rate` 子信号恒真路径**：`control.forward_rate == 0` 连续 3 s ⇒ `_rate_low_s ≥ 3.0` ⇒ `r_score = 1.0` ⇒ `stuck_score = 1.0`（`:208-219`）；② **duration 被抹零**：`:234-235` 的 `disp_60s > 500 ⇒ _stuck_duration = max(0, dur − 1.0)`，而增长仅 `+0.02/tick`（`:229`）⇒ 移动片段一次泄放即抹回 0，**同刻可读作"满分卡死 + 0 秒卡死 + anomaly=idle"**；③ **离线仿真（我独立复算，参数全给出）**：150 tick 连续 `fr=0` / 64 tick `fr=0.3`、`disp_60s=1090`、`te=0.5`、`frame_seq` 每 tick 前进、`pos_y=120`、n=3000 ⇒ **`score==1.0` 恰 14 次，且 14 次全部 `dur==0.0`**（命中 tick 列表见紧随表后的说明段）；**对照组 `disp_60s=None`（泄放失效）同样 14 次命中但 `dur=0.02 ≠ 0`** ⇒ 抹零确由泄放造成；④ 活体侧 t4 独立取得 12:54:31–12:55:01 **六连** `stuck_score=1.0 / stuck_duration=0.0` | 实测·高（我的独立仿真 + t4 活体采样） | t4 §6（我独立复算） |

**E13 离线仿真的命中 tick（自表内移出，内容未删）**：`[149, 363, 577, 791, 1005, 1219, 1433, 1647, 1861, 2075, 2289, 2503, 2717, 2931]`（相邻命中间隔恒为 214 = 150 tick `fr=0` + 64 tick `fr=0.3`；共 14 次，与正文一致）。

**E13 的归属（t5，队长裁定）**：属 **RC-4（观测点/归因字段未接线）的新实例**，**与 A3 的关系是「同族症状、不同判据」**——A3 的历史症状是 `rate_threshold = 5.0 Hz` 与 per-tick 比例**量纲错配**导致结构恒真（09-24 那次）；本次是**量纲修好后暴露的语义 + 泄放缺陷**（`0.008` 使 rate 子信号等价于"forward_rate 恰为 0"，被 idle 频繁触发；同时泄放抹掉 duration），即"**修好了单位、没修好可判定性**"。同时与 **RC-5 叠加**：迁移只做一半（只改 `:135` 阈值与注释，未改 `docstring:127` 仍写「`< 5 Hz`」，也未加任何运行时断言）。**不构成 RC 分类之外的新子型。**

**E7 影响面的诚实收敛**：`gate_jump` 唯一消费者 `scene_context.py:234` 的产物经 `scene_context_to_dict()` 序列化，而该函数在全仓**零调用者**（`grep` 实测）；`build_scene_context_summary()`（真正注入 LLM 的文本）**不含** `gate_jump`。故 E7 是**真实但低危**的契约断裂：语义静默错误，尚未污染决策变量（`neural_viz_skill.py:153` 的 `("gate_forward","gate_jump")` 为第二处受影响消费者，同样只剩一半键）。**不得**把它夸大为"决策链失效"。

### 3.3 例数与根因分类

**本窗口同族实例：13 例**（工程侧 10：E1–E9 + **E13**；分析工作侧 3：E10–E12）。`（t5 更正：原值 12 例 → 实测口径 13 例）`

| 根因类 | 例数 | 实例 | 说明 |
|---|:-:|---|---|
| **RC-1 任务边界切分**：把"生效所必需的一环"留在 inScope 之外 | 1 | E1 | `analysis-evo-loop-liveness.md` §5-4/§6-1 **自述**「未把它焊进 `evo_loop_launcher.sh`（避免超出 inScope）」，把 cron 一行作为"后续建议"⇒ 守护按报告口径"完成"，按功能口径"未生效"。这是**根因位于验收标准**的典型：验收只覆盖"机制触发"，不覆盖"持续生效" |
| **RC-2 守卫/校验器自身无断言** | 2 | E2、E12 | 防漂移的守卫自己不产生可失败断言（`check_version.py` 4 行；引用校验器计数口径错误 + 假阳性放行）⇒ 守卫从"安全网"退化为"通过仪式" |
| **RC-3 生产者-消费者契约断裂且被测试夹具掩盖** | 2 | E7、E8 | 键名迁移只做生产者侧 + PIN 测试侧，消费者侧靠 `default=False` 静默降级；规格承诺的信号从未实现却列入验收清单 |
| **RC-4 观测点/归因字段未接线** | **2**（t5：原 1） | E5、**E13** | 能力（看见钳位）达成，归因（谁写的）与观测点（哪个端点）未接线，且**文档与代码指向不同端点**。**E13（t5 新增）**：`stuck_score` 与 `stuck_duration` 由**同一次调用**算出却给出相反语义（"满分卡死"/"零秒卡死"），是**可复现的假绿源**（下游 `deadlock_burst_ready`/`anomaly.update`/`health_score` 都读这两个量）；**与 A3 同族症状、不同判据**，并与 RC-5 叠加（见 §3.2-E13 归属说明） |
| **RC-5 迁移只做一半** | 2 | E6、E9 | 契约约束未约束写入方；代码改动只落在工作区/未同步活体。（E13 亦与 RC-5 叠加：只改 `:135` 阈值与注释，未改 `docstring:127` 的赫兹表述、未加运行时断言） |
| **RC-6 记录与证据纪律** | 2 | E3、E4 | 需区分两类失效：**记录被删除**（E3，可追溯、可由 `HEAD~1` 回收）vs **从未记录**（E4，需重新补齐）。另有 `w1-w4` §4.2 自承用合成数据形成结论（**未计入本 13 例**，原文已自我作废，见 §6-U1） |
| **RC-7 分析工具链编码/口径缺陷** | 2 | E10、E11 | 122× 计数失真与 GBK 误读同属"分析工具未受与被分析代码同等纪律约束" |
| | **合计** | **13** | 1+2+2+2+2+2+2 = 13 ✔（E4 只归 RC-6，E12 只归 RC-2，E13 只归 RC-4，无重复计数） |

**根因分布特征**：**13 例中 5 例的根因不在技术正确性，而在"边界/守卫/记录"**（RC-1 1 + RC-2 2 + RC-6 2）。这与历史 12 例（根因全为常量/信号/状态/数据/方向等技术层）形成**明显结构差异**：历史族是"代码写错了"，本窗口族多出「**代码写对了但没被接上、没被验证、没被记录**」这一类（RC-1/RC-2/RC-6 共 5 例）。

### 3.4 与历史 12 例的关系：同族延伸 or 新增？

**结论：9 例同族延伸 + 4 例新增子型。**`（t5 更正：原值 8 + 4 = 12 → 实测 9 + 4 = 13）`

**同族延伸（形态与历史 12 例同类，只是换载体）**：
- E3/E4（记录纪律）↔ 历史 #11「骨架技能空数据」（都是"契约载体在位而内容不成立"）
- E5/E6（钳位/契约半通）↔ 历史 #5「策略穿透失败：Coach 产生策略但 control 不生效」（`session-log-analysis.md` §4.2 #5 原判「🔄 fix5-fix12 部分修复」，本窗口 `f486ad0` 后仍是"部分"）
- E10/E11（分析工具链）↔ 历史 #6「桥接读取空数据」/ #9「GLM 咨询空上下文」（同属"接口报成功、数据不成立"）
- E9（部署不同步）↔ 项目文档已多次记录的同族（`motor-pool-review-t2/t3/t8` 三处「活体未部署」，见 `deploy-manifest.md` §1）⇒ **并非新问题**，但**在窗口内再次发生**，且这次连部署清单的 md5 证据也失效（升级形态）
- E12（校验器精度）↔ 历史 #3「Threshold 签名不匹配」
- **E13（观测层假绿，t5 新增）** ↔ 历史 #2「MBON 饱和」/ #10「Loop score 饱和」——同属"**指标读数为真、语义与行为无关**"；更直接地，它与历史「StuckDetector 单位」缺陷是**同一变量的两次不同失效**（09-24：量纲错配 ⇒ 恒 1.0；本次：量纲修好后暴露的语义 + 泄放缺陷）⇒ **同族延伸，非新子型**

**新增子型（历史 12 例的根因分类未覆盖）**：
1. **E1 调度缺口**：历史族的"无法生效"都发生在 **数据/信号/代码路径**上；本例发生在 **运维调度层**——脚本正确、执行正确、**从未被计划任务调用**。（`deploy-manifest.md` §1 的"未部署"是另一类：部署了但目标错；E1 是**根本没部署守护进程**。）
2. **E2 守卫自身无断言**：历史清单中"守卫/基线/契约"是**期望能发现问题**的工具；本例是**工具本身不产生信号**，且作为规则 8 的指定执行体被写进 `agent.md`。这是"元层"复发（守卫的守卫）。
3. **E7 生产者删键 + 消费者默认值兜底 + 测试夹具补键**：三重静默（无异常、无警告、测试绿）叠加，历史 12 例无此组合（历史 #3 是"存在但不生效"，非"被删后由默认值接管"）。
4. **E8 规格承诺的验证信号从未实现**：验收清单把"应当存在的观测键"当作"部署后验证项"，而 producer 从未发布该键 —— 这让**验收清单本身成为假绿来源**。

---

## 4. 当前真实困境（更新版）

### 4.1 A 组：`docs/analysis/session-log-analysis.md` §5 的 5 项困境

| # | 已交付结论 | 本次判定 | 依据（可复现） |
|:-:|---|:--:|---|
| A1 | Telemetry 常量分歧（已交付口径：`0.12` 8 次≥4 种语义、`0.15` 14 次，**扫描范围未在已交付文本中限定**） | **仍存在（量级未减）** | 我按**显式限定范围**重算并给出全部口径（与已交付的 8/14 不可直接 1:1 对比，因原口径不可复现）：`model.py` 中 `0.12` **7 次** / `0.15` **20 次**；`main.py` 中 **3 / 4**；`fly64/**/*.py`（排除 `__pycache__`）**60 / 162**。模块级命名常量仅 `FWD_RATIO_FLOOR = 0.008` **1 个**（P1-b3 新增）⇒ **常量抽取几乎未发生**。**局部改善**：gate 阈值统一到注册表 + 单一换算点 `rate_per_tick_to_hz()`（`main.py:795`）✔ |
| A2 | CX-2 锚点漂移：`_self_motion_update()` 开环积分，**无视觉闭环校正** | **⚠️ 结论需更正（冲突）+ 生效未验证** | 实测 `central_complex.py` 已有 `AnchorPathIntegrator.relocalize(scene_id, confidence)`（`:128-140`，`relocalize_gate=0.8`/`strength=0.3`，场景记忆 `scene_id → (disp_x,disp_z,confidence)`），**调用点 `:529`、`:673`**，测试 `test_cx_navigation.py:179-204`。「无视觉闭环校正」对当前代码**不成立**（所引 `remaining-issues-analysis.md` 基于 09-13 版本）。但**活体是否真正命中**未验证（`scene_id` 形参为 `int|None`，而 main.py 侧 `memory_ctrl.scene_id` 是字符串标签，需核对传入与命中率）⇒ 见 §6-U5 |
| A3 | `StuckDetector.rate_threshold` 单位混淆（`5.0 Hz`） | **① ✅ 已解决（仅"单位标注"）／② ✘ 不成立（"不再 ≡1.0"）**`（t5 拆分；原值：单句「✅ 已解决」）` | ① **单位标注对齐 ✔ 已解决**：`memory.py:135`：`rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`；`:207-208` 比较式加显式单位注释「both sides are per-tick fractions ∈ [0,1] (see RULE-19)」。② **「不再 ≡1.0」✘ 不成立**：t2 原判据「活体 `stuck_score = 0.08`」是**单点取样偏差**；t4 于 12:54:31–12:55:01 独立取得 **六连** `stuck_score = 1.0` 且同刻 `stuck_duration = 0.0`；我用**离线仿真**独立复算（150 tick 连续 `fr=0` / 64 tick `fr=0.3`、`disp_60s=1090`、`te=0.5`、n=3000 ⇒ **14 次 `score==1.0`，全部 `dur==0.0`**；对照组 `disp_60s=None` 时 `dur=0.02`）⇒ 机制与判据见 §3.2-E13。③ 另有**半迁移**：`docstring:127` **仍写**「forward_rate collapses (**< 5 Hz** for >3 s)」 |
| A4 | `control.x` 直接写入（已交付实测：`main.py` 10 处 / 全仓生产 14 处，口径 `control\.x\s*=`） | **仍存在，但未恶化**`（t5 更正；原值：「仍存在且恶化」）` | **冻结正则后再计数**（赋值口径 `control\.x\s*=(?!=)`）：`main.py` **10** / 生产（排除 `fly64/tests`）**14** / 含 `fly64/tests` **16** / 含根 `tests/` **17**。**窗口前后对比**：`2f87d77^` = `HEAD` = 工作区 **均为 10**（朴素口径均 12）⇒ **窗口内既无新增也无减少，仅行号漂移 +112~+120**。原报「10→12（生产 14→16）」的 **12/16/18 来自朴素正则 `control\.x\s*=` 把 2 处 `control.x == 0` 比较计入**（`main.py:2618`、`main.py:2959`）—— 该口径事故本身即 **RC-7（分析工具链口径）的第 3 个实例** |
| A5 | Steering 预算次序（CX 优先 vs Reflex 优先）未定义 | **仍存在** | `memory.py:1541 def _vote(...)` 仍是唯一判定函数，**无 `ArbitrationState`、无竞争/升级/超驰语义**（P2-c1 未实现）；`fly64-autonomy-evolution-plan.md` §6 把 c1 列为 P2，而 H13 裁定使 P2 阻塞（§4.3） |

### 4.2 B 组：`docs/analysis/session_logs_analysis_v5.md` §4 的 5 项困境

| # | 已交付结论 | 本次判定 | 依据 |
|:-:|---|:--:|---|
| B1 | 自进化闭环**结构上**无法自治修复（六失效点） | **部分缓解，未解决**（且新增三点恶化） | 缓解：P0-2 可执行 fix（`fix_executor.py` 823 行，自带 `parse_fix_template`）、P0-4 `has_fix` 生命周期均已实现并验收。恶化：① **不在 HEAD**（36 未提交）② **不在活体**（`evolution_skill.py` md5 不同，E9）③ 闭环 09-26 11:47 **再次停摆且告警未响**（E1）④ H13 裁定「真实 `noise_p95=0.1777` 超门限 5.9×」⇒ 适应度无法分辨改进 ⇒ `w1-w4` 明文：**P2/P3 整体阻塞、SP5-B 与 SP6 不可开工、闭环保持永久 shadow** |
| B2 | 自适应信号到不了"决定行为的变量"（M1） | **部分缓解：断口形态迁移** | `analysis-credit-assignment-matrix.md`（AST 134 写点）判定 M1 的"不重叠"字面表述已不成立 ⇒ 断口变为 **B1 解码器硬编码饱和（1100/2000/0.008 编译期常量）/ B2 `escape.fallen_jump_boost` 死写 / B3 钳位+自愈抹原值 / B4 `gate_forward_threshold` 无执行消费者 / B5 forward 稳态钉满速 / B6 转向主导腿量级差 10×**。活体侧佐证：`clamped_keys.requested=0.7` 被 `applied=0.25`（E6）⇒ **信号仍在半路被吃掉** |
| B3 | 观测层口径缺陷使"是否生效"无法判定 | **未缓解**`（t5 改写；原值：「部分缓解 + 新增子项…」中的"缓解"部分不成立）` | **原写「缓解：`stuck_score ≡ 1.0` 构造伪影已消除（活体 `0.08`）」✘ 不成立**：t4 于 12:54 取到**六连** `stuck_score=1.0 / stuck_duration=0.0`；我用**离线仿真**独立复算得 3000 tick 内 **14 次 `score==1.0` 且全部 `dur==0.0`**（`disp_60s=None` 对照组 `dur=0.02`）⇒ **伪影未消除，只是改变了触发相位**（`rate` 子信号 —— `forward_rate == 0` 连续 3 s —— 仍可把 `stuck_score` 拉到 1.0；`:234-235` 的 `disp_60s > 500` 泄放把 `_stuck_duration` 一次抹回 0）。**新增子项（保留）**：① 钳位观测点错位（文档说 `/memory.json`，实际在 `/flow.json`，E5）② 归因恒 `unknown` ③ `no_progress_gate` 与 `progress_ineffective` **片段**不一致（t4 54 点采样：前者恒 False，后者在 True/False 间切换 ⇒ 措辞由 t2 原写的"同刻相反"收紧为"**片段不一致**"）④ **E13（本表新例）**。⇒ 观测层缺陷须与 B06 同批处理 |
| B4 | 多会话并发写入同一仓库 | **仍存在** | 12 个提交分属 ≥2 条独立会话线（`2f87d77`/`6655288`/`cca6664`/`ab2761c`/`78b3175` vs `4ba5f11`/`f486ad0`/`833848c`/`38c8bae`）；`deploy-manifest.md` §4 明确列入「他人 WIP」排除集；`agent.md:27`（规则 16）明令常驻 EVO 循环**只能在 WSL 单实例**。窗口内新后果：`evolution_history.json`（运行侧权威历史）被工作区提交覆盖并同步回活体（E3） |
| B5 | 运维性负担 | **仍存在且加重** | WSL 实测：`/tmp` = **≥134 GB（滚动值：13:19 实测 135 G、13:24 复测 136 G）**、`/tmp/f64r_traj-*.npz` = **3435 个**、根分区 **78% 使用**（745G/1007G）；`skills/evolution_log.jsonl` = **200 MB** 无轮转；`active_strategy.json` 仍存三份（工作区/WSL/备份，md5 已知不同）。v5 记录为 130GB/3000+ ⇒ 两周内继续增长 |

### 4.3 新增困境（已交付分析未覆盖）

| ID | 困境 | 依据 | 严重度 |
|:--:|---|---|:--:|
| **N1** | **版本/记录一致性守护失效（规则 8 守卫无断言）**  | `check_version.py` 4 行空壳（WSL exit 0 恒过 / Windows 因硬编码路径 `ModuleNotFoundError` exit 1，**错因**）；`skills.md` 3.5.1 ≠ canonical 3.4.2 **无人拦**；规则 15 的 `--history-check` 亦未拦下 EVO-072/073 的删除。**t5 补充（精确化）**：规则 8 实际有**两个**守卫 —— `tests/check_version.py`（空壳）与 `tests/test_version_consistency.py`（真断言，但**只覆盖 `BRAIN_VERSION`**：main.py ↔ skills.md 徽章 ↔ `canonical_versions.brain`，**不读 `SKILL_VERSION`、不比对 `skills/evolution_skill.py`**）⇒ **skill 侧 3.4.2 vs 3.5.1 的不一致属"结构性无人覆盖"**，不只是"守卫坏了" | **高** |
| **N2** | **窗口产出未入库，交付不可复现** | 36 个已跟踪文件未提交（+4890/−469，含 `evolution_skill.py` 2555 行变动 + `memory.py` 507 行）+ 63 个未跟踪项；09-25 的 P0-2/P0-4「已验收」不在 HEAD；19 份 `docs/analysis` 中仅 4 份入库。⇒ **git 不能作为"该窗口解决了什么"的事实源** | **高** |
| **N3** | **活体-工作区漂移且部署证据链断裂** | `evolution_skill.py` 两侧 md5 不同；`deploy-manifest.md` 记录的 `f895171ee477` 两侧均不匹配；09-26 的 `sm64config.txt` 为手工同步（非部署脚本） | 中高 |
| **N4** | **同族新形态：验收清单成为假绿来源** | `deploy-manifest.md` §6 六条"必须验证的信号"中 `burst_active`（**无 flow/memory 发布点**；`main.py:2206` 只有属性赋值）与 `evo_loop_stale`（全仓无实现）**结构上不可能通过**；部署报告以其余信号宣称成功。**t5 补录**：同族还有 (a) `evo_loop_launcher.sh`/`evo_liveness_guard.py` **无执行位（100644）**、(b) `runtime/evolution_history.json` 为**易失的运行时副本、此前未被任何报告核对**（见 §2.5） | 中 |

### 4.4 与已交付分析的一致性 / 冲突点（逐条给依据）

| ID | 冲突/更新点 | 已交付结论 | 本次结论 | 依据 |
|:--:|---|---|---|---|
| **C1** | 困境 A3（StuckDetector 单位） | 「🟡 **单位混淆风险**」仍存在（§5 困境 3） | **拆分后"部分冲突"**`（t5 更正；原值：单句「已在窗口内解决」）`：① **单位标注** —— 已交付的「仍存在」**过时、已解决**（`memory.py:135` 现为 `0.008 per-tick`，`5.0` 已不存在）② **可观测性** —— 已交付的核心担忧（"不同帧率下可能误判"）**在新量纲下仍成立**：`docstring:127` 仍写「`< 5 Hz`」、`rate` 子信号被 idle 频繁触发、`stuck_score` 仍可达 1.0（12:54 六连）⇒ t2 原写「已在窗口内解决」**过头**，现明确为「**单位对齐 ✔ / 可观测性 ✘**」 | `memory.py:135`（`0.008 per-tick fraction; was 5.0 Hz`）+ `:207-208` 显式注释；反向证据：`docstring:127`、t4 12:54 六连、我的离线仿真 14/3000 |
| **C2** | 困境 A2（CX-2 无视觉闭环校正） | 「`_self_motion_update()` 使用 heading_rate **开环积分，无视觉闭环校正**」 | **该表述对当前代码不成立**；应改为「机制已存在（`relocalize()`），**活体生效未验证**」 | `central_complex.py:128-140`、`:529`、`:673` + `test_cx_navigation.py:179-204` |
| **C3** | §4.2 #5 策略穿透 | 「🔄 fix5-fix12 部分修复」 | **更新为"仍为部分，且缺口已精确化"**：`source` 归因、观测点错位、契约未约束写入方（0.7/0.9 持续到达）。⚠️ **t4 复现边界**：t4 于 12:56 采样 `clamped_keys = []`（该时刻无钳位事件）⇒ **"`source` 恒 `unknown`"本轮未复现＝未复现，≠ 不成立**（结构性事实 `clamped_keys ∈ flow.json` / `∉ memory.json` 已复现） | 活体 `flow.json`（t2 12:37/12:42 两次采样含 `source:"unknown"`）+ `/tmp/fly64.log`（26 行同类告警）+ `scene_strategy_bindings.json` promoted 桶 |
| **C4** | §4.4 持续性风险（缺契约审计、测试只验"触发"不验"生效"） | 原文为**建议**（"实施契约审计"） | **已升级为事实**：窗口内新增 3 例同型（E2 守卫空壳、E7 夹具补键掩盖、E8 验收信号不存在），并新增"守护无调度"子型 | §3.2 E1/E2/E7/E8 |
| **C5** | v5 §3「参数'注册了但不生效'：🟡 **已有机制** —— `clamped_keys` 已上线；注册区间与钳位已对齐」 | 判为已缓解 | **需降级**：机制上线 ≠ 可判定 —— 观测点与文档不一致（实测在 `/flow.json`）、契约对齐仍未拦住写入方；`source/归因` 一项按 t4 复现边界标注为**未复现≠不成立** | 活体 `clamped_keys`（t2 两次采样含 `source:"unknown"`；t4 12:56 为空列表）+ 版本键对照 |
| **C6** | v5 §5「P0-1 常量提取」 | 措施未实施 | **A1 仍存在**：`model.py` `0.12`×7 / `0.15`×20（全仓 .py 60/162）、模块级命名常量 1 个；窗口把工作量投在 gate 单位契约与信用分配矩阵上，**未做常量抽取** | 我重算 |
| **C7** | v5 §4.6 / §5「P1-4 部署世系收敛、P1-5 磁盘轮转」 | 待办 | **未收敛**：磁盘 **≥134 GB（滚动；13:19 = 135 G / 13:24 = 136 G）/78%**；`evolution_skill.py` 世系分叉（E9） | WSL 实测 |

**无冲突但需强调的一致性**：`session-log-analysis.md` §4 对该族的定性（"高复发率提示架构性问题：缺乏契约审计 / 测试覆盖不足 / 集成验证缺失端到端断言"）**在本窗口被完整证实** —— 本窗口 **13 例**中 **5 例**的根因落在"边界/守卫/记录"而非技术层（§3.3），正是该定性的**机制化版本**。

---

## 5. 遗留风险

| ID | 风险 | 触发条件 / 后果 | 建议动作 |
|:--:|---|---|---|
| **R1** | **进化史发生不可逆丢失** | EVO-072/073 已删**且删除已同步活体**（两侧 md5 相同）。活体 `/root/fly64` 非 git 仓库 ⇒ 若工作区副本再被覆盖，只能靠 `git show HEAD~1` 回收 | 立即从 `HEAD~1` 回收两条记录（`git show HEAD~1:fly64/skills/evolution_history.json`），修正 `canonical_versions.skill` 为 3.5.1 或把 `main.py` 对齐，并把恢复动作本身写成一条 EVO 记录 |
| **R2** | **规则 8/15/17 三契约同时失效的乘性效应** | 无人拦（E2）+ 记录删（E3）+ 未记录（E4）叠加 ⇒ 版本链与记录链**同时不可信**，`agent.md:32` 声称的 `--history-check`「比对三处一致」未产生任何红灯 | 给 `check_version.py` 补真实断言（读 `main.py` / `skills/evolution_skill.py` / `evolution_history.json.canonical_versions` / `skills.md` 四处并 `exit 1` on mismatch），并把"无断言即规则未生效"写入规则 8 的验收 |
| **R3** | **P0-a8/P1-b1..b5 的未入库改动滞留工作区** | H13 裁定使 P2/P3 阻塞，09-25 交付又不在 HEAD ⇒ 长期滞留 → 并行会话双写丢失（`deploy-manifest.md` §4.1「`evolution_skill.py` 无法纯净切分」已自述） | 至少把 `main.py`/`memory.py`/`central_complex.py`/`instinct_bindings.py`/`model.py` 与 `fix_executor.py`/`fix_guard.py`/`contract_registry.json` 分批提交（可保留未验证项为文档标注） |
| **R4** | **回归门禁口径不可信（双测试根）** | 未跟踪的 `?? tests/` 与 `fly64/tests/` 并存；若真被双收集，`lastfailed=94` / `nodeids=1924` 与规则 20 基线不可比 | 跑一次 `pytest --collect-only -q`（我未执行，见 §6-U4）确认；若双收集立即收敛到单根 |
| **R5** | **行为改善证据不足**（jump 0→12/600） | 该数字为 `deploy-manifest.md` §12 自述，我 30 次稀疏采样 0 次命中（样本量不足以证伪），全仓无 `jump_count` 累计计数器 | 按 §9 定义的口径（同一 `trajectory.html`、≥6000 帧）复采并落盘；考虑新增累计 jump 计数器以便遥测侧长期监督 |
| **R6** | **EVO 闭环停摆 → 自适应面全灭** | 闭环死 ⇒ `fix` 不生成、`fitness` 不产生、告警不响；`evolution_log.jsonl` 最后写入 11:47（快照时 2982s 前） | 把 `evo_liveness_guard.py --check` 接入 crontab（报告 §6-1 已给现成一行），并**验证一次真实 kill→自动拉起**（当前只有脚本无调度） |
| **R7** | **教练链路与对话决策时间戳互相矛盾** | `coach_outcomes.jsonl` 停 09-24 11:35、`coach_advice.json` 停 09-24 12:04，而 `flow.llm_decision.ts` ≈12:13 仍更新 ⇒ 要么链路更名/改路径，要么帧保存条件在 09-25 部署后不再满足 | 下一阶段第一条排查项（链路口径核查） |

---

## 6. 诚实边界

### 6.1 实测（有命令 + 原样输出，可复现）

窗口 12 提交与时间；`git diff --shortstat` 36 文件/+4890/−469；`evolution_skill.py` +2485/−70；`git log -S 'EVO-072'/'EVO-073'` 双向；`records=87` 且 EVO-072/073 不存在；`canonical_versions.skill=3.4.2` vs `main.py:50 SKILL_VERSION="3.5.1"`；`check_version.py` 4 行且 WSL exit 0 / Windows exit 1（错因）；`crontab -l` 仅 2 条；`evo_loop_launcher.sh --status` 报「闭环 ○ 未运行 / 最后写入 2982s 前」；**`/root/fly64/skills/.evo_loop.lock`=11997（t5 更正：在 `skills/` 下，非 `/root/fly64/` 根）为陈旧锁**；`evo_stall_alarm.json` mtime 09-25 21:01:25；活体 `flow.json` 122 键 / `memory.json` 61 键且 `clamped_keys ∈ flow ✔ ∈ memory ✘`；`clamped_keys` 两次采样 `requested=0.7 → applied=0.25, source=unknown`；`gate_jump_ratio` 6 采样 4 次 > 0.75；`gate_jump` 键在活体不存在而 HEAD 发布过、消费者 `scene_context.py:234` `default=False`；**`burst_active` 无 flow/memory 发布点（`main.py:2206 model.burst_active = …` 为属性赋值）**；`evo_loop_stale` 全仓 `.py` 零命中；`anchor.relocalize()` 与调用点；`memory.py:135` 单位修复（`0.008 per-tick`）；**`stuck_score` 仍可达 1.0 且与 `stuck_duration=0.0` 同刻**（t4 12:54 六连 + 我的离线仿真 3000 tick 内 14 次 `score==1.0` 且全部 `dur==0.0`；`memory.py:213-225` 三子信号 `max` + `:234-235` 泄放；`memory.py` 全文 `assert` = 0）；**`control.x` 写点 = 10（`main.py`）/ 14（生产）/ 16（含 `fly64/tests`）/ 17（含根 `tests`），且 `2f87d77^`=`HEAD`=工作区均为 10 ⇒ 未恶化**；**`git ls-files --stage` 显示 `fly64/scripts/evo_loop_launcher.sh` 与 `evo_liveness_guard.py` 均为 `100644`（无执行位）**；**`runtime/evolution_history.json`（7,110–7,116 B，每轮重写，仅 WSL 存在）与 `skills/evolution_history.json`（99,101 B）是两份不同文件**；`model.py` 中 `0.12`×7、`0.15`×20（全仓 .py 60/162）；WSL `/tmp` ≥134GB（滚动；13:19 = 135G / 13:24 = 136G）/ 3435 npz / 磁盘 78%；md5 对照表（§2.3）。

### 6.2 推断（给出链条与置信度）

| ID | 推断 | 链条 | 置信度 |
|:--:|---|---|:--:|
| I1 | EVO 闭环死于 11:46:44–11:47:44 间，紧随一次**不含 `fly64-evo` 的**重启 | 心跳 11:47:29 / 日志 11:46:44 + `/tmp/fly64_launcher.log` 11:47:44 创建 `tmux fly64` + `wsl_launcher.sh` 只处理自身会话 | 中高（缺 11:47 那一刻的进程审计） |
| I2 | 钳位请求 `0.7/0.9` 的写入方是**本能绑定 promoted 桶** | `coach_applied.instinct_applied=true` + `scene_strategy_bindings.json` 中「致命熔岩地」promoted 签名含 `exploration.turn_bias=0.7` | 高 |
| I3 | E7 的根因是"P1-b3 迁移只改生产者与 PIN 测试，未同步消费者" | `git diff` 显示删除发布行、`test_gate_units.py:300` 断言改为新键名、消费者仍读旧键 | 高（对事实）；"无测试覆盖消费者"为实测 |
| I4 | `flow.no_progress_gate=False` 与 `memory.progress_ineffective=True` 不一致源于**同源不同 tick 或不同变量传入 `cx.update()`** | `main.py:3265` 发布的是 `model.cx._last_no_progress`（**上一 tick**，`central_complex.py:234`/`:391` 自述），而 `progress_ineffective` 是 `main.py:2867` 的当 tick 值 | 中（需读 `:2867` 与 `cx.update()` 实参对照确认） |
| I5 | 09-26 `sm64config.txt` 属手工同步而非部署脚本产物 | 非 `.deploy_backup` 时点 + mtime 12:27 紧邻提交 12:28 | 中高 |

### 6.3 无法验证的声明（明确列出，禁止下游当实测使用）

> **t5 补注**：t4 核验要求的「`stuck_score` 矛盾」**不属于本表** —— 它已从"未验证/观察项"升级为**已复现**，列入 §6.1 实测清单与 §3.2-E13。本表保持不变（不删条目）。

| ID | 无法验证的声明 | 原因 |
|:--:|---|---|
| **U1** | `w1-w4-closeout` §4.2 自承：原 W4 结案报告用**合成数据**（`N(0,0.025)+10% outlier`）形成结论，真实 `noise_p95=0.1777`（差 5.9×）；原文结论"超门限 0.6%"已作废 | 合成数据报告在 `.tmp/`（临时目录，可被清理）；我只能读到 `w1-w4` 的**更正**，**无法独立复核原始 W4 的合成过程**。该例计入根因 RC-6（证据纪律），但**未计入 §3.3 的 12 例**（原文已自我作废） |
| **U2** | "jump 帧 0/6000 → 12/600（项目首次观测到 jump）" | 部署报告自述；我 30 次稀疏采样 0 命中（2% 占空比下期望 0.6 次，样本量不足以证伪）；活体无 `jump_count` 累计计数器 |
| **U3** | motor-pool 修复的**行为改善幅度**（X/Z 效率、静止帧 23%→0.5%、`waste_ratio`） | 需按 §9 口径采集 ≥6000 帧；我只取得单点：`render_ms 6.12`（渲染修复有效）、`forward_rate_hz` 不再饱和、`gate_jump_ratio` 可达 |
| **U4** | 根目录 `tests/` 与 `fly64/tests/` 是否被双根收集 | 未执行 `pytest --collect-only`（本轮为只读分析，未跑套件） |
| **U5** | CX-2 `relocalize()` 在活体上的命中率/有效性 | 未核对 `scene_id`/`scene_confidence` 的实际来源与类型是否匹配 `int|None`；未统计命中次数 |
| **U6** | `no_progress_gate` vs `progress_ineffective` 不一致的确切根因 | 未读全 `main.py:2867` 与 `cx.update()` 实参链（见 I4）。**t4 补正**：其 54 点采样显示 `no_progress_gate` 恒 False 而 `progress_ineffective` 在 True/False 间切换 ⇒ 现象**片段存在**（t2 原文"同刻相反"已在 §4.2-B3 收紧为"片段不一致"），但**"不一致"不构成两者必冲突**：`main.py:3265` 发布的是 `cx._last_no_progress`（**上一 tick**），与当 tick 的 `progress_ineffective` 本就可不同 ⇒ 根因仍未定论 |
| **U7** | 教练链路 09-24 12:04 后无文件产出却 `llm_decision.ts` 仍更新的矛盾 | 未定位写入方；t1 亦仅列为"需下一阶段核实" |
| **U8** | H5/H6/H11 未关闭、`memory.json` / `.cache/malecns/manifest.json` 缺失 | 文档（`w1-w4` §7、`deploy-manifest` §10）自述；我没有独立确认这些假设的完整定义与验收条件 |
| **U9** | "窗口内无 CI/门禁产物落盘" | 非穷尽检查（glob/grep 级）⇒ **未证实**，非已证伪 |
| **U10** | `38c8bae` 的 `_captain_verify_t3.sh` 是否真跑过 | 我未执行该脚本（只读分析），仅确认其入库 |
| **U11** | 队长补充证据中「`evolution_history.json` **+137/−41**」这一改动量 | `git show fbcc3d7 --numstat -- fly64/skills/evolution_history.json` 实测为 **115 / 39**；`--shortstat`/`--stat` 图总数 154（=115+39）。137/41 **我无法用 git 复现**（可能是"两版本文件行差"而非 commit diff）。本报告采用 **115/39** 并把 137/41 记为未复现 |

---

## 7. 下一步建议（按"阻塞关系"排序，非按工作量）

1. **恢复记录 + 让守卫有断言**（R1+R2，半天）：从 `HEAD~1` 回收 EVO-072/073；给 `check_version.py` 补四处比对与 `exit 1`；补测该守卫能真正失败（注入一处不一致→必须红）。检查手段：`python fly64/tests/check_version.py`（Windows/WSL 两侧都必须可失败，不得依赖 `/root/fly64` 硬编码）。
2. **把 EVO 守护真正接入调度**（E1/R6，1 小时）：`*/1 * * * * .../evo_liveness_guard.py --check`（报告 §6-1 已给现成一行）；随后做一次**真实 kill → 自动拉起/告警**验证（当前"守护"只有脚本+手工验证）。
3. **收口未入库交付**（N2/R3，半天）：分批提交 09-25 交付与 `main.py`/`memory.py`/`central_complex.py`/`instinct_bindings.py`；对 `evolution_skill.py` 的 2485 行按 `deploy-manifest.md` §4.1 的已知风险**分批+标注**提交。
4. **修观测点与归因**（E5+C5，半天）：把 `clamped_keys` 的文档/代码统一到同一端点（现为 `flow.json`）；识别 instinct-binding 写入方以消掉 `source="unknown"`；顺手修 `no_progress_gate`/`progress_ineffective` 口径（U6）。
5. **补/撤验收清单里的假绿项**（E8/N4，2 小时）：`burst_active` 要么发布要么从清单删除；`evo_loop_stale` 要么实现（`main.py` 读 `evo_stall_alarm.json` 暴露 `stale`）要么从 M4-d4 计划中移除。
6. **E7 的低成本收口**（1 小时）：`scene_context.py:234` 改为读 `gate_jump_ratio > gate_jump_threshold_ratio`（或恢复生产者布尔），并**在测试里删掉夹具中的 `gate_jump` 键**让契约真被验证。
7. **按已定义口径复采 ≥6000 帧**（U2/U3/R5，1 次运行）：出"部署是否改善运动问题"的第一份真实答案（`deploy-manifest.md` §9 已给出对照表与判据）。
8. **（t5 新增，最高优先）修正 `stuck_score`/`stuck_duration` 的观测语义**（E13/B3，0.5 天）：`rate` 子信号与 `disp_60s` 泄放必须至少一项改口径（例如把 `rate_threshold` 的语义从"forward_rate 恰为 0"改为"低于前进阈值且伴随无位移"，或让泄放按 delta 而非一次性 −1.0）；并在 `check`-级断言里钉住"`stuck_duration == 0` 时 `stuck_score` 不得为 1.0"。

---

## 8. 返修记录（t5，2026-09-26 13:0x–13:2x；依据 t4 核验报告）

> **纪律**：本节是 t4 核验（`blindspot-review-0923-0926.md`）M-1~M-5 与本文件就地更正的**对照清单**；每条给出「原值 → 实测值」，不删除任何既有条目、不放宽任何表述。**t3 两份文档以 append-only 勘误块处置**（见 `session-log-recommendations.md` / `session_logs_execution_plan.md` 文末勘误块）。

| ID | 原值（t5 前） | 实测/更正后 | 依据（可复现） |
|:--:|---|---|---|
| **M-1** | §4.1-A3「**✅ 已解决**」，判据「活体 `stuck_score = 0.08`（不再 ≡1.0）」 | 拆为两句：① **单位标注对齐 ✅ 已解决** ② **「不再 ≡1.0」✘ 不成立**（`0.08` 是**单点取样偏差**；t4 12:54 六连 = 1.0） | `memory.py:135/207-208`；t4 §6.1（12:54:31–12:55:01）；我的离线仿真（§3.2-E13） |
| **M-2** | §4.2-B3「**部分缓解**：`stuck_score ≡ 1.0` 构造伪影**已消除**」 | 改写为「**未缓解**：伪影**未消除，只是改变触发相位**」+ 机制（`rate` 子信号恒真 + `disp_60s>500` 泄放抹零）与复现 | `memory.py:208-235`；离线仿真 3000 tick 内 **14 次** `score==1.0` 且 14 次 `dur==0.0`（对照组 `disp=None` → `dur=0.02`） |
| **M-2b** | §4.4-C1 单句「**已在窗口内解决**」 | 改为「**单位对齐 ✔ / 可观测性 ✘**」；并说明已交付的核心担忧（不同帧率下误判）在新量纲下**仍成立** | 同上 + `docstring:127` 仍写「`< 5 Hz`」 |
| **M-2c / M-5** | t3 P1-N1 标题「单位文档化 **+ 运行时断言**」、执行方案「添加运行时断言验证 `0 < forward_rate < 100 Hz`」 | 更正为「**单位文档化 ✅ / 运行时断言 ❌ 未实现**」——`memory.py` 内 `rate_threshold` 出现处仅 **135/142/208** 三处，**全文 `assert` 计数 = 0** | `Select-String -Path fly64/fly64/memory.py -Pattern 'rate_threshold'`（3 处）；`-Pattern '^\s*assert\b'`（0 处）；t3 侧以文末勘误块处置 |
| **M-3** | §4.1-A4「**仍存在且恶化**：`main.py` 12（10→12）/ 生产 16（14→16）/ 含 tests 18」 | 更正为 **`main.py` 10 / 生产 14 / 含 `fly64/tests` 16 / 含根 `tests` 17**（赋值口径 `control\.x\s*=(?!=)`），且 **`2f87d77^`=`HEAD`=工作区均为 10 ⇒ 未恶化**；12/16/18 系朴素正则把 `main.py:2618`、`:2959` 两处 `control.x == 0` **比较**计入 | 逐字命令见 §6.1 与附录；三版本 `git show …:fly64/fly64/main.py` 同法计数均得 10 |
| **M-4a** | 全报告**未写明路径**（t4 记为"写错为 `fly64/skills/`"） | 显式更正为 **`fly64/scripts/evo_liveness_guard.py`**（**407 行** / 15,863 B）与 **`fly64/scripts/evo_loop_launcher.sh`**（**211 行** / 7,889 B）；实测 `Test-Path fly64/skills/evo_liveness_guard.py` = **False**；并在 §3.2-E1 注明「+407/+211 是 `--stat` 新增行数，非文件行数」 | `Test-Path`；`git ls-files --stage`；`Get-Content … \| Measure-Object -Line` |
| **M-4b** | 未写明路径（t4 记为"写成 `/root/fly64/` 根"） | 显式更正为 **`/root/fly64/skills/.evo_loop.lock`**（**在 `skills/` 下**，内容 11997，陈旧锁） | `wsl cat /root/fly64/skills/.evo_loop.lock` |
| **M-4c** | §3.2-E8「`burst_active` … **无发布点**」 | 更正为「**无 flow/memory 发布点**」——`main.py:2206 model.burst_active = _deadlock_burst_remaining > 0` **存在属性赋值**，但不写入任何 HTTP 端点 | `Select-String main.py -Pattern 'burst_active'`；活体 `flow.json`/`memory.json` 均无该键 |
| **RC 裁定** | 12 例（RC-4 = 1） | **13 例（RC-4 = 2，+ E13）**；并标注 E13 **与 A3 同族症状、不同判据**，与 **RC-5 叠加**，**不构成新子型**（§3.2-E13 / §3.3 / §3.4） | 队长裁定；我的离线仿真 + t4 六连采样 |
| **补录 1** | 全部报告未记录 | `evo_loop_launcher.sh` **与** `evo_liveness_guard.py` 在 git 中均为 **100644（无执行位）** | `git ls-files --stage` |
| **补录 2** | t1/t2/t3 只核对 `skills/evolution_history.json` | 补录 **`runtime/evolution_history.json`（7,110–7,116 B，每轮重写，仅 WSL）与 `skills/…`（99,101 B）是两份不同文件**，各自消费方与结构见 §2.5 | WSL `ls -l` + `head -c`；`main.py:61/220/2360` vs `evolution_skill.py:202`、`test_version_consistency.py:28` |
| **O-1（已闭环，t5 attempt 2）** | t2 未报：已交付 `session-log-analysis.md` §困境 4 的 10 个写点行号已整体漂移 **+112~+120** | 本报告 §4.1-A4 已记录该漂移；**该文件已按 M-6 就地回改**（attempt 2 起纳入 t5 in-scope）：§困境 2「无视觉闭环校正」→「机制已在、活体生效未验证」；§困境 3 →「单位口径闭环 / 断言未实现 / 可观测性未闭环」；§困境 4 十个行号 → `[760,2060,2077,2141,2190,2192,2406,2414,2466,2492]` 且复现正则加 `(?!=)` 守卫；文末新增「附录 C：t5 返修勘误汇总」 | t4 §4.2-E；`session-log-analysis.md` 附录 C |
| **O-2/O-3（保留）** | — | 双根 pytest 收集仍未执行（§6-U4）；未跟踪计数三套口径（`??` 条目 65 / `-uall` 354 / "产物 ~62"）未统一 —— 本报告用**条目数**口径 | t4 §7-O-2/O-3 |

**t5 自评未闭环项（诚实声明；attempt 2 更新）**：① `session-log-analysis.md` 的三处过时（CX-2「无视觉闭环校正」、`rate_threshold = 5.0` 取值/行号、§困境 4 的 10 个写点行号）**已按 M-6 就地回改**（见该文件「附录 C」；attempt 2 起该文件纳入 t5 in-scope）；② 双根收集、`relocalize()` 活体命中率、教练链路矛盾仍未验证（§6-U4/U5/U7）；③ `t4` 报告裁定的「队长提供的 `re.findall(r'control\.x\s*=(?!=)')` 得 10」我已复现，而**队长的口述命令 `control\.x\s*=` 实测 12**（伪影来源 `main.py:2618`/`:2959` 已定位，非文档错误）。

---

## 附录：本报告全部可复现命令（与 t1 附录互补，非重复）

```bash
# 1) 窗口与提交
git log --since=2026-09-23 --until=2026-09-27 --pretty=format:'%h|%ad|%s' --date=iso
# 2) 记录删除 / 版本回归
git log --oneline -S'"EVO-072"' -- fly64/skills/evolution_history.json
python -c "import json;d=json.load(open('fly64/skills/evolution_history.json',encoding='utf-8'));print(d['canonical_versions'],len(d['records']))"
Select-String -Path fly64/fly64/main.py -Pattern 'SKILL_VERSION'
# 3) 规则 8 守卫（空壳）
Get-Content fly64/tests/check_version.py          # 4 行
python fly64/tests/check_version.py               # Windows → ModuleNotFoundError, exit 1
wsl -e bash -c 'cd /root/fly64 && python3 tests/check_version.py'   # → exit 0（恒过）
# 4) 工作树规模
git diff --shortstat -- . ':(exclude)fly64/.pytest-run' ':(exclude).tmp-pytest'
git diff --numstat -- fly64/skills/evolution_skill.py
# 5) E7 生产者/消费者契约
git show HEAD:fly64/fly64/main.py | Select-String '"gate_jump'
git diff -U0 -- fly64/fly64/main.py | Select-String 'gate_jump'
Select-String -Path fly64/plugin/scene_context.py -Pattern 'gate_jump'
Select-String -Path fly64/tests/test_what_i_see_protocol.py -Pattern 'gate_jump'
# 6) 活体遥测（单点/短采样）
python -c "import json,urllib.request as u;f=json.load(u.urlopen('http://127.0.0.1:8765/flow.json'));print([k for k in sorted(f) if 'gate' in k or 'burst' in k]);print(f['clamped_keys'])"
python -c "import json,urllib.request as u;m=json.load(u.urlopen('http://127.0.0.1:8765/memory.json'));print('clamped_keys' in m,'progress_ineffective',m.get('progress_ineffective'))"
# 7) WSL 运行时与部署世系
wsl -e bash -c 'cd /root/fly64 && md5sum fly64/main.py skills/evolution_skill.py skills/evolution_history.json'
wsl -e bash -c 'cd /root/fly64 && bash scripts/evo_loop_launcher.sh --status; crontab -l'
wsl -e bash -c 'ls /tmp/f64r_traj-*.npz | wc -l; du -sh /tmp; df -h / | tail -1'
# 8) 困境 A1/A4/A5 的代码口径
Select-String -Path fly64/fly64/memory.py -Pattern 'rate_threshold'
Select-String -Path fly64/fly64/main.py -Pattern 'control\.x\s*=' -AllMatches
Select-String -Path fly64/fly64/central_complex.py -Pattern 'relocalize'
```

*报告结束。所有 `[实测]` 项可在 2026-09-26 12:37–12:52 的快照状态下按上述命令复现；活体条目为**单点/短采样**，不得当趋势使用。`[推断]`、`[未验证]` 项请勿当作实测转引。*
