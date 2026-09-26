# 新增会话分析 / 盲区交叉核验 / 项目级合并 —— 独立核验报告（t5）

> **核验对象（R3 三轮产出）**
> - t2：`docs/analysis/session-analysis-0924-0926.md`（自报 563 行 / 88,823 B；**实测 562 行**）
> - t3：`docs/analysis/blindspot-crossvalidation.md`（实测 559 行 / 75,182 B）
> - t4：`docs/analysis/project-state-consolidated.md`（实测 563 行 / 76,870 B）+ `session-log-recommendations.md` 追加 §A.9（实测 1,131 行）+ `session_logs_execution_plan.md` 追加第三轮附录（实测 1,168 行）
>
> **核验人**：`verifier`（AgentTeams `fly64-newlogs-0924-0926` / task **t5** / attempt `2efce4be-017c-4290-a349-9c3e721f2f1f`）
> **核验时刻**：2026-09-26 14:0x–14:5x（本地）
> **纪律**：只读核验 + 撰写本报告。**未修改** t1–t4 任何产出、`fly64/**`、`fly64/skills/**`；所有复算脚本落在 `.tmp/t5_verify/`（非交付路径）。
> **独立方法声明**：本轮**未调用** t1 的解析器（`scripts/session_log_extract.py` / `scripts/session_summary_new_logs.py`），而是自写流式抽取器
> `.tmp/t5_verify/indep_count_t5.py`（逐行 `json.loads` + `collections.Counter`），与 t1 的产物**零代码共享**；代码事实用 `.tmp/t5_verify/code_facts2.py`、`.tmp/t5_verify/jump_sites.py`、`.tmp/t5_verify/head_scope.py` 只读复算。

---

## 0. 结论摘要（先给判定）

| # | 判定 | 数量 | 说明 |
|:--:|---|:--:|---|
| 1 | **抽样回溯通过**（结论 → 证据 → 成立） | **14 / 16** | 含计数、git、会话链路、代码事实、口径四类 |
| 2 | **必修正（blocker/high）** | **3** | F-1「重复副本 1131」、F-2「执行门引用已失效（scope 混用）」、F-3「gain("jump") 行号 + 全仓库仅此一处」 |
| 3 | **必修正（medium）** | **3** | F-4「87 处 write/edit 口径未声明」、F-5「51 个未跟踪未能复现」、F-6「t2 自报 563 行」 |
| 4 | **建议修正（low）** | **3** | F-7「§0.3 写两项实为三项」、F-8「O-/X- 编号未落表」、F-9「check_version 路径未标注」 |
| 5 | **t3 增量主张** | **8 / 9 成立** | 1 条**字面不成立**（"会话全文零处提及 EVO-072/073"），8 条逐位复现（含 38/176、115/39、4.48/4.88、inode） |
| 6 | **t4 去重** | **通过** | E1–E13 计一次、A1–A5 计一次、N1–N4→D-02/04/05/07、B01–B17=17 项、35 = 18+14+3 自洽 |
| 7 | **t4 完整性** | **基本通过（可追溯性不足）** | t3 的 10 项遗漏 / 7 项判断错误**内容已并入**（关键词逐项命中），但 **O-/X- 编号在 t4 中 0 次出现** |
| 8 | **append-only** | **本轮通过（文件整体不是字节级 append-only）** | 本轮追加块均在文末；`session-log-recommendations.md` **未被 git 跟踪**（无法用 diff 验证）；`session_logs_execution_plan.md` 对 HEAD 有 **+446/−38**（跨 ≥3 轮累积，删改全在正文区，**早于本轮**） |
| 9 | **与前两轮一致性** | **无事实冲突（1 处 scope 冲突）** | A4 口径、13 例、122×、115/39、EVO-072/073 与 R1/R2 一致；**唯一冲突** = R3 §1「真问题」用 HEAD 口径描述 `gate_jump`，而 R2 E7 / R3 D-15 用的是 ratio 口径 |
| 10 | **残留扫描 + `verify_doc_citations.py`** | **exit 0（96 警告）** | 但该脚本**不覆盖 3 份 R3 新文档**（见 §7.2），故 exit 0 对 t2/t3/t4 不构成保证 |
| 11 | **整体可信度评级** | **B+（可用，但 3 处必修正须先返修）** | 计数与 t3 增量主张的可复现性**显著优于**前两轮（38/176、115/39、L1098、inode 逐位一致）；缺陷集中在**引用 scope 与"新口径"自身** |

一句话：**t2/t3/t4 的"拿到一手会话证据"这一主目标已经达成且高度可复现；但它们自己在 §0.1 建立的"权威口径"里有一处新口径错误（1131）、一处核心代码引用在两套修订间混用（scope），以及一处行号+唯一性断言错误——这三处会直接误导"下一步"的施工。** 建议：**以本报告 §9 为返修清单，返修后无需重跑全套核验。**

---

## 1. 抽样回溯（逐条：结论 → 证据 → 判定）

> 复现命令统一前缀：`cd D:\codes\flygym; $env:PYTHONIOENCODING='utf-8'`。
> 抽取器：`.tmp/t5_verify/indep_count_t5.py`（逐快照全文件流式，主会话 + 子代理）。

### 1.1 计数类（快照 / 日期 / 去重）

| # | 结论（出处） | 我的独立证据 | 判定 |
|:--:|---|---|:--:|
| **A1** | 快照合计 `tool/call` = **1826**（6 份主会话相加）；子代理 **12782**；合计 **14608**；**118** 个子代理目录（t1/t2/t4） | `python .tmp/t5_verify/indep_count_t5.py` → `main tool/call TOTAL = 1826` / `sub tool/call TOTAL = 12782` / `combined = 14608` / `subagent dirs total = 118`；逐快照 `726 / 58 / 304 / 350 / 152 / 236` 与 t1 逐位一致 | **成立** |
| **A2** | 逐日快照口径 09-24 = **665**、09-25 = **391**、09-26 = **153**（t1） | 同上脚本 `per-date (all snapshots, main)`：`2026-09-24 665` `2026-09-25 391` `2026-09-26 153`；且 99cab60f-latest 在 09-25 为 **0** 次（逐快照打印 `99cab60f-latest {'2026-09-24': 65, '2026-09-26': 44}` 无 09-25 键） | **成立** |
| **A3** | 去重口径 09-24 = **336**、09-25 = **206**、09-26 = **153**，合计 **695**（t3 §A.2 / t4 §0.1） | 按 `callId` 去重：`per-date dedup (distinct callId)` → `336 / 206 / 153`，窗口合计 `695`；**并且**可解释 185 的错因：`6c53f724-v2` 09-25 恰为 **174**（`per-date per-snapshot` 行），v3 为 **195**，差 **21** | **成立** |
| **A4** | **「重复副本 1131」**（t3 §A.2 ⇒ t4 §0.1「权威」⇒ recommendations §A.9.1-C13 ⇒ plan 第三轮附录 共 6 处） | 我的去重：全局 distinct callId = **1312**，总额 1826 ⇒ **重复副本 = 514**；窗口口径同样 = `1209 − 695 = 514`。`1826 − 695 = 1131` 的减数与被减数**不同域**：1826 含 **617** 次 09-19→09-23 的调用（只存在于 99cab60f-latest，**根本不存在副本**）。617 = 224+35+53+196+109 正是**窗口外**日合计 | **不成立 —— F-1（blocker）** |
| **A5** | 文件变更 **87** 处 write/edit（t1 ⇒ t4 §0.1 引用） | 我的三方复算：**原始 write/edit 调用 = 126**（逐快照 `65/0/16/29/5/11`）；**Σ 逐快照 distinct(工具,路径) = 87**（`37/0/12/23/5/10`）；**全局 distinct 路径 = 63**、全局 distinct(工具,路径) = **69**。⇒ 87 是"逐快照去重后再相加"，**既非原始调用数也非全局唯一数** | **成立但口径未声明 —— F-4（medium）** |
| **A6** | t2 §5.2-**U8**「窗口内 **26** 个已跟踪文件被改 + **51** 个未跟踪」 | 前半：`git status` 中 M 项且 `LastWriteTime ∈ [09-24, 09-27)` = **27**（现测，晚约 1 小时，±1 可解释）；总量 `98 M + 43 D + 74 ??`（**本报告落盘后 `?? = 75`**）；**剔除本轮 3 份新文档后 `?? = 71`**，与 t2 的另一处 71 自洽。后半：**51 不是 `git status` 计数**（全量 74；`fly64/` 下 30；docs 下 30；无 `.pytest-run` 项），U8 正文实为**手工枚举的窗口产出子集**且未写判据 | 前半**成立**；后半**判据缺失 —— F-5（medium）** |

### 1.2 git / 提交事实

| # | 结论（出处） | 我的独立证据 | 判定 |
|:--:|---|---|:--:|
| **B1** | `evolution_history.json` 改动量 **115/39**；`+137/−41` 是 `git commit` 自身的**三文件汇总行**（t3 §2.7 / t4 §2.2 / recommendations §A.9.1） | `git show fbcc3d7 --numstat` → `115 39 fly64/skills/evolution_history.json`；`git show fbcc3d7 --stat` → `3 files changed, 137 insertions(+), 41 deletions(-)`（其中 `README.md 21/1`、`sm64config.txt 1/1`） | **成立** |
| **B2** | 该汇总行出现在 **`51f62457-v2` 12:28:03 `L1098`**（t3） | 直接读该文件第 1098 行：`tool/result` → `"[master fbcc3d7] … 3 files changed, 137 insertions(+), 41 deletions(-)"`，`time=1790396883028` ⇒ **12:28:03**，行号/时刻/内容**三者逐位一致** | **成立（强）** |
| **B3** | `fbcc3d7` 的 `added=[AUTO-0017..0023, EVO-074]`、`removed=[EVO-072, EVO-073]`、`canonical skill 3.5.1→3.4.2`、`as_of=2026-09-24T18:00:00`（t3 三条独立判据） | `git show HEAD~1:…` → 81 条、含 EVO-072/073、`canonical_versions.skill=3.5.1`、`as_of=2026-09-24T00:00:00`；`HEAD`/工作区 → **87 条**、两条均缺、含 EVO-074、`skill=3.4.2`、`as_of=2026-09-24T18:00:00`；集合运算输出 `added=[AUTO-0017…0023, EVO-074]`、`removed=[EVO-072, EVO-073]` | **成立（强，逐位）** |
| **B4** | 性质 = **"意外覆盖"（`cp` 事故）**，作者会话 = `51f62457-v2`；11 步链路（t3 §2.7） | 全量导出的 pwsh 工具调用：12:25:30 读工作区（结果 `records count: 81 / last id: EVO-073`）→ 12:25:40 对**工作区**追加 EVO-074 → 12:26:17 `write fix_evo.py` + 12:26:23 在 **WSL** 执行 → 12:27:19 `ls -la /root/fly64/.git`（输出 `No such file or directory`）+ grep vsync（WSL 仍 `true`）→ 12:27:28 `stat --format=%i` → 12:27:29 结果 **`296` / `125256364637215400`** → **12:27:34 `cp /root/fly64/skills/evolution_history.json /mnt/d/codes/flygym/fly64/skills/evolution_history.json`**（`L1077`）→ 12:27:53 `git add` → 12:28:03 commit → 12:28:19 回同步 WSL；文件 mtime 恰为 **12:27:35**（`cp` 落盘） | **成立（强）**，2 处措辞需精确化（见 F-7/§4） |
| **B5** | 提交信息只写"新增 EVO-074"，未提删除（t3） | `L1097` 命令原文含 `- skills/evolution_history.json: 新增EVO-074记录WSLg渲染瓶颈分析与修复`；全文**无**删除表述 | **成立** |
| **B6** | t2「`cca6664`/`6655288`/`833848c`/`38c8bae` 在 6 份 jsonl 中 **0 次命中**」；t3 更正为 **38 / 176** | 我的逐文件计数：`833848c` → **38**（99cab60f 36 + 51f62457-v2 2）；`38c8bae` → **176**（99cab60f 171 + 51f62457-v2 5）—— **与 t3 的数字完全一致** | t2 **不成立**；t3 **成立（逐位）** |

### 1.3 会话链路 / 归因（t3 增量）

| # | 结论（出处） | 我的独立证据 | 判定 |
|:--:|---|---|:--:|
| **C1** | 09-26 崩溃可 **PID 级归因**：12:02:59 起唯一执行 `pkill -f fly64.main` 的会话是 `6c53f724-v3`，其余会话（含 `99cab60f`）**未执行**（t3 附录 A.1） | 全 6 快照**只取 `type=tool/call` 且 `name=pwsh`** 的**实际执行**命令：09-26 命中 4 条 —— `6c53f724-v3` 11:55:30 / 11:57:24 / 12:02:47 三条 `pkill`，`99cab60f-latest` 仅 12:31:17 一条 **grep**（子代理读 launcher 源码，非 pkill）。`51f62457-v2` **0 条**（它用 `kill -9 <PID>`）。⇒ 杀掉 51f62457 的 PID 2505 的动作**只可能来自 6c53f724-v3** | **成立（强）**；"12:02:59 起"与"连续 6 轮"为口径用词（见 §4-M1） |
| **C2** | 两会话"**同刻**矛盾"实为**不同时刻**（t4 D-10 / t3） | `51f62457-v2` 11:48:31 输出「✅ 检查、清理、重启完成」（脑 PID 2505 运行中）；`6c53f724-v3` **11:51:59** 读到 `stuck_score = 1.0 / stuck_duration_true = 4.48 / anomaly_state = idle`（同一 PID 2505）；二者相差 **3.5 分钟**，不是同一时刻 | **成立**（t2 的"同一时刻"用词不精确，t3 的更正有据） |
| **C3** | E13 反判据键 `stuck_duration_true` = **4.48 / 4.88**（11:51 / 11:54）（t3 §2.6 / t4 D-06） | 一手读数：11:51:59 `stuck_duration_true = 4.48`；11:54:03 `stuck_duration = 0.0 / stuck_duration_true = 4.88 / stuck_score = 1.0 / anomaly_state = idle` | **成立（强）** |
| **C4** | 会话当场把该现象判为"真卡死/伪影已消"（t3 / t4） | 11:52:22 assistant 原文：`"Hmm, stuck_score = 1.0 but stuck_duration = 0.0? That's contradictory. … stuck_score = 1.0 is the old artifact value. But wait - the artifact was fixed by P0-a2"` ⇒ **当场自相矛盾且未收敛**；会话确实给出了相反归因 | **成立** |
| **C5** | `evo_liveness_guard` / `evo_loop_launcher` / `analysis-evo-loop-liveness` 三个字符串**只出现在 99cab60f**（导出覆盖缺口，t3 X-1/O-1） | 计数：`evo_liveness_guard` = 311（**100%** 在 99cab60f）、`evo_loop_launcher` = 345（100%）、`analysis-evo-loop-liveness` = 71（100%）；`6c53f724*` / `51f62457*` **0 命中** | **成立（强）** |
| **C6** | `check_version.py` 在 `6c53f724`/`51f62457` 中**零运行零修改**（t3 §2.2） | 该名字在 6c53f724/51f62457 共 22 处命中，**全部是 `ls`/`git` 输出与文档目录索引里的文件名**；**实际执行**（pwsh 调用）共 19 条，**全部在 99cab60f-latest**（09-23 20:49 ×3、09-26 12:37–12:56 若干） | **成立**（可加强：执行全部同源） |
| **C7** | `HAS_EVO_LIVENESS=False` 静默失效（t3 X-7/O-3） | 计数 400 次命中，集中在 `6c53f724-v2/v3`（各 200）——与 t3 所指 09-25 12:16–12:27 段落同源 | **成立（存在性）**；具体行号 `L1978/L1986/L2002` **未逐行复核**（见 §8 证据不足项） |

### 1.4 代码事实（当前工作区）

| # | 结论（出处） | 我的独立证据（当前工作区） | 判定 |
|:--:|---|---|:--:|
| **D1** | `control.x` 写点四级口径 **10 / 14 / 16 / 17**，赋值口径 `control\.x\s*=(?!=)`（t2 / t4 A4） | `main.py` 赋值口径 = **10**，行号逐位一致 `[760,2060,2077,2141,2190,2192,2406,2414,2466,2492]`；朴素口径 = **12**（多出 `2618`/`2959` 两处 `==` 比较）；生产（排除 `fly64/tests`）= **14**；含 `fly64/tests` = **16**；含根 `tests/` 增量 = 1（`tests/test_memory_avoidance.py:296`）⇒ **17** | **成立（逐位）** |
| **D2** | `stuck_score` 恒真：`memory.py:213-225` 三子信号取 `max` + `:234-235` 泄放；`:127` docstring 仍写 `< 5 Hz`；全文 `assert` = **0**（t3/t4） | `:213-219` 三子信号与 `t_score/f_score/r_score`、`:225 stuck_score = max(...)`；`:234 if self.disp_60s is not None and … > 500.0 and self._stuck_duration > 0.0`、`:235 self._stuck_duration = max(0.0, … − 1.0)`；`:127` = `- forward_rate collapses (< 5 Hz for >3 s)`；`^\s*assert\b` 命中 **0** | **成立（逐位）** |
| **D3** | 版本三元组断裂：`evolution_history.json.canonical_versions.skill = 3.4.2` vs `main.py:50 = 3.5.1` vs `skills.md:3/L70 = 3.5.1`（t4 D-03/B03） | 三处实测一致：文件 `skill=3.4.2`（工作区 mtime 12:27:35，未再变动）；`main.py:50 SKILL_VERSION = "3.5.1"`；`skills.md:3`、`:70` 均为 `SKILL_VERSION **3.5.1**` | **成立（强，且"未修复"时效成立）** |
| **D4** | `check_version.py` = **4 行**空壳（t3 §2.2） | `fly64/tests/check_version.py` 实测 **4 行**：`import sys` / `sys.path.insert(0,"/root/fly64")` / `from fly64.main import BRAIN_VERSION` / `print("loaded BRAIN_VERSION:", BRAIN_VERSION)`；不比较、无 assert | **成立**；但**路径未标注**（见 F-9） |
| **D5** | `relocalize()` 机制已在：`central_complex.py:128-140` + 调用点 `:529`/`:673` + 测试 `test_cx_navigation.py:174` 起（t4 §6 / recommendations §A.8-E-9「已交付文档回改」项；t2 只在 U15 的"未验证项"里提到 `relocalize 活体命中率`） | `:128 def relocalize(...)`、`:529`、`:673` 两调用点、`test_cx_navigation.py:174 def test_visual_relocalize_stores_scene`（`:179`/`:204` 调用）全部逐位命中 | **成立（逐位）** |
| **D6** | `gate_jump` 消费者静默兜底 + 夹具补键（t3 §2.10） | `fly64/plugin/scene_context.py:234` = `gate_jump=bool(_get_safe(flow, "gate_jump", default=False))`；`fly64/tests/test_what_i_see_protocol.py:68` = `"gate_jump": False,`；`test_gate_units.py:300` 已断言新键 `gate_jump_threshold_ratio` —— 三者逐位命中 | **成立（逐位）** |
| **D7** | `telemetry.py:94` 是"第 4 个互不一致的门限口径"（t3 §4-9） | `telemetry.py:94` = `gate_jump=bool(rates["jump"] is not None and rates["jump"] > 2.)` ⇒ **`>2 Hz`**，与 ratio 语义、absolute 0.04、面板文案均不同 | **成立** |
| **D8** | `burst_active` 无 flow/memory 发布点（仅属性赋值）；`evo_loop_stale` 全仓 `.py` 零命中（t3 §2.5） | `main.py:2206` = `model.burst_active = _deadlock_burst_remaining > 0`（属性赋值）；`evo_loop_stale` 在 `fly64/**/*.py` 命中 **0** | **成立** |
| **D9** | `gain("jump")` **只缩放一条腿**（`model.py:1842`，**全仓库仅此一处**） | 工作区 `model.py:1842` = `# ---- MBON-to-motor current injection ----`（**注释行**）；该块的增益调用在 **1849**，另有 **1875**（记忆回放→jump 同样乘 `_jump_leg_nominal_gain`）、**1335**（`_jump_leg_weight_effective`）、**1906**（`_pathway_gains_np[3]`）；`main.py:3212` 另有遥测读取 ⇒ **"仅此一处"在代码层面不成立** | **不成立（引用面）—— F-3（high）**；"注入腿只有一条带增益"这一**子命题未被推翻**（属 a4 §1.3 的"12 条注入腿"清单，本轮未复算） |
| **D10** | "**唯一的执行门** `jump = jump_rate > 0.04`（`model.py:2478`）与前向池满速 0.043 同量级"（t2 §1.3/§7.3、t4 §1.2） | **两套修订**：`git show HEAD:fly64/fly64/model.py` **2492 行**，`:2478` = `jump = jump_rate > 0.04 and now - self.last_jump >= 0.8` ✔（HEAD 成立）；**当前工作区** 2580 行，`:2478` = 无关注释，真正的门在 **`:2562-2566`**：`jump = ((jump_rate / max(forward_rate, FWD_RATIO_FLOOR)) > getattr(self,'_jump_rate_ratio_gate',0.75) ...)`，并带注释 `"P1-b3: … replaces absolute occupancy threshold (jump_rate > 0.04)"`；工作区 `0.043` 在 `model.py` **0 命中** | **仅对 HEAD 成立；对当前工作区不成立 —— F-2（high）** |

---

## 2. 时效性核验（"已修复 / 已闭环"声明能否在当前工作区确认）

| 声明 | 出处 | 当前工作区核验 | 判定 |
|---|---|---|---|
| 版本三元组**未对齐**（3.5.1 vs 3.4.2） | t4 D-03/B03 | `evolution_history.json` 仍 `skill=3.4.2`（mtime 12:27:35 之后未变） | **未修复（声明成立）** |
| `stuck_score` 代码**未修**（仅定位） | t2 §5.2-U11、t4 D-06/B15 | `memory.py:213-225/234-235` 原样；`assert` = 0；`:127` 仍写 `< 5 Hz` | **未修复（声明成立）** |
| EVO 守护**未接入调度**、告警器不运行 | t3 §2.9、t4 D-09 | 本机无法复现 WSL live 读数（见 §8 边界）；但**代码/仓库侧**可确认：两脚本在 `fly64/scripts/`（`fly64/skills/` 下**不存在**），未见 crontab 清单文件入库 | **状态存疑（依赖 WSL 活体，未复算）** |
| 9 条"已交付文档回改"（`session-log-analysis.md` 附录 C） | recommendations §A.8-E-9 | 该文件在 `??`（未跟踪）、文末确有「附录 C：t5 返修勘误汇总」；10 个 `control.x` 写点行号与我的复算**逐位一致** | **确认** |
| `339/179` 已废弃（改用 407/211） | t7 更正链（R2 已闭环） | 实测：`fly64/scripts/evo_liveness_guard.py` = **407** 行 / 15,863 B；`evo_loop_launcher.sh` = **211** 行 / 7,889 B；`Measure-Object -Line` 分别得 **339 / 179**（漏计口径可复现） | **确认（且解释了 339/179 的来历）** |
| `P1-N1`"单位文档化 + 运行时断言"= 闭环 | 既有 18 项 | **半闭环**：`:135 rate_threshold = 0.008` + `:207-208` 注释 ✔；运行时断言 ❌（`assert` = 0） | **t4 已改写为"半闭环"，判对** |
| 渲染修复（`fbcc3d7`）有效 | 盲区 §2.1 | 提交含 `sm64config.txt (1/1)` + `README.md (21/1)`；本轮**未做活体渲染复测** | **证据不足（超出只读核验范围）** |

---

## 3. 数字与口径核验：本项目四类历史事故的复查 + 新发现第 5 类

### 3.1 ① 122× 计数失真（只读文件头 / 按类别去重）
- 复查对象：R3 是否再次引用失真聚合值。
- 结果：R3 三轮文档中"122×"只作为**历史缺陷**被引用（E10 / D-14），**未发现任何以失真聚合值支撑结论**的段落；本轮 6 快照的每一个计数我都能从原始 `type=="tool/call"` 记录复现（§1.1）。t1 自身也保留了 `independentToolCallCount = 726` 与 `toolCallCountMatchesIndependent: true` 双路径。
- 判定：**未复发**。

### 3.2 ② 行号漂移（引用指向别的修订/别的行）
- 复查对象：R3 的 `file:line` 是否对**某一明确修订**为真。
- 结果：**发现系统性 scope 混用**（这是本轮最重要的口径问题）：
  - `memory.py:213-225` + `:234-235`（stuck_score 取 max / 泄放）→ **对工作区（2,998 行）成立**；对 HEAD（2,541 行）不成立（HEAD 的泄放在 `:1993-1995`）。
  - `memory.py:1985/1993-1995`（伪影链第四段）→ **对 HEAD 成立**（HEAD `:1985` = `self._stuck_score, …, self.stuck.update(`，`:1993-1995` = `_disp_60s` 泄放）；对工作区不成立（工作区 `:1985` 是 `_turn_direction`、`:1993-1995` 是 reflex 阶段推进）。
  - `main.py:2957/2894`（gate_jump 生产者）→ **只对 HEAD 成立**（HEAD `:2957` = `"gate_jump": gate_open_hz(...)`、`:2894` = `_gate_jump_hz = float(_expl.get("gate_jump_threshold", 8.0))`）；工作区对应行是别的代码。**t4 的 B07 行明确写了"（HEAD 为 `:2957`）"，t2 的旧引用未标 scope。**
  - `model.py:1842 / 2478` → 见 F-2/F-3。
- 判定：**复发（未被 R2 的三次教训覆盖的新形态）**：同一文档内**混用 HEAD 与工作区行号**且不标注修订，读者无法判断"当前系统"到底跑哪一套。→ **F-2 / F-3 / F-9**。

### 3.3 ③ `--stat` 图形总数被当 numstat 改动量
- 复查：`fbcc3d7` 的 `137/41` 与 `115/39`。实测 `--stat` = `3 files changed, 137 insertions(+), 41 deletions(-)`；`--numstat` = `21/1`、`1/1`、`115/39`。
- 判定：**未复发；t3 的更正（137 = 3 文件合计，含 README 21+sm64config 1）完全正确，且比 R2 的"无法复现"更进一步。**

### 3.4 ④ 工具口径差异（`Measure-Object -Line` vs `wc -l`）
- 我的实测：`evo_loop_launcher.sh` → PS **179** / Python **211**；`evo_liveness_guard.py` → PS **339** / Python **407**；字节数两侧一致（7,889 / 15,863）。
- **注意**：t4 转述中的"两文件差值恒为 **11**"**不成立** —— 实际差值分别为 **32**（211−179）与 **68**（407−339）。11 这个数字在 `blindspot-review-round2.md:396` 出现过；本报告未在 t2/t3/t4 中检出该数字，故不列为 R3 缺陷，但**建议随 R2 文档一并更正**（本项目正在引用一个未标注来源的"恒为 11"）。
- 判定：**口径差异事实成立；"恒为 11"的说法不能复现。**

### 3.5 新发现（第 5 类）：**"新权威口径"自身的算术域错误**
- F-1（`1826 − 695 = 1131`）与 §0.1 的"去重 695"叠加后，形成一条**看起来最权威、实则域混用**的口径：1826 是**全快照**，695 是**窗口内去重**。正确写法：
  - 全局：`朴素相加 1826 / 去重 1312 / 重复副本 514`；
  - 窗口（09-24→09-26）：`快照合计 1209 / 去重 695 / 重复副本 514`；
  - 窗口外（09-19→09-23，仅在 99cab60f-latest）：`617，无副本`。
- 该类与历史第 ① 类同源（"口径与数字不同域"），但方向相反：历史是**漏计**，本次是**多算**（把 617 次非重复调用算进了"重复副本"）。→ **建议写入契约模板："任何减法必须声明两项同域"。**

---

## 4. t3 增量主张的独立核验（哪些被证伪/修正、哪些只有会话能揭示）

| # | t3 主张 | 我的独立检索结果 | 判定 |
|:--:|---|---|:--:|
| M1 | 附录 A.1：崩溃"**12:02:59 起**唯一执行 `pkill -f fly64.main` 的会话是 `6c53f724-v3`（**连续 6 轮** pkill + rm）" | 实际执行序列：`6c53f724-v3` 11:55:30 / 11:57:24 / 12:02:47（**3 条** pwsh 调用含 pkill）；**另有 6 次 `write` 落盘脚本**（11:54:25 / 11:55:39 / 11:57:39 / 11:59:05 / 12:01:04 / 12:02:59）内容含 `pkill -f 'fly64.main'` + `rm -f /tmp/…` ⇒ "6 轮"在"脚本轮次"口径下成立，"3 条执行"在工作区口径下成立 | **成立但须标口径**（low） |
| M2 | §2.7 判据③："会话全文**零处提及** EVO-072/073 或 canonical skill" | `51f62457-v2` 全文命中 **3 处**：12:24:27（工具结果显示一份"锚点表"里含 `| EVO-072 | 2026-09-22 | …`）、12:25:31（读文件输出 `last record id: EVO-073`）、12:25:40（"The last record is EVO-073"） | **字面不成立**；实质（提交者**不知道**自己在删两条记录）**成立**：3 处全是**回显他人文档 / 自己刚读出的文件内容**，无一处把它当作"将被删除的对象" ⇒ 建议改为「**会话从未把 EVO-072/073 识别为"将被删除的记录"**」 |
| M3 | §A.2："重复副本 = 1131" | 见 F-1 | **不成立** |
| M4 | §A.3："`833848c`/`38c8bae` 0 次命中不成立，实测 38/176" | 我复现 **38 / 176**（逐位一致） | **成立** |
| M5 | §2.2：`check_version.py` 在 6c53f724/51f62457 零运行零修改 | 复现（22 处均为文件名回显；19 条执行全在 99cab60f） | **成立** |
| M6 | §2.6 / §A.4：E13 有 11:51/11:54/11:55 三连读数，反判据 `stuck_duration_true = 4.48/4.88`，且会话当场误判 | 复现 4.48（11:51:59）/ 4.88（11:54:03）+ 11:52:22 的自相矛盾原文 | **成立** |
| M7 | §2.7 / §4-2："3.082 在 [0.25,3.0] 内"被队长以 `3.082 > 3.0` 当场证伪 | 未在导出集内直接检索到 09-24 13:13:14 原文（见 §8 边界）；`active_strategy.json` 相关值在旧轮文档中记为 `3.082271242248696` | **部分成立（会话原文未复现，间接证据一致）** |
| M8 | §2.9 / X-1：guard 三字符串只在 99cab60f，作者会话不在导出集，覆盖缺口 09-25 21:00–21:18 | 复现（311/345/71 全部同源；6c53f724/51f62457 零命中） | **成立（强）** |
| M9 | §4-4 / O-2："`evolution_skill.py` 2485 行改动中约 2450 行属另一 DSH 会话" | 我复现了 `git diff` 侧规模（该文件在 M 列表、当前 5,357 行），但 **"2450 行归属"需读会话中的收口自述原文**，本轮未逐字定位 | **证据不足（未复核）** |

> **小结**：t3 的 9 条核心增量中 **6 条逐位复现、2 条成立但需标口径/改写措辞、1 条不成立（1131）、1 条未复核**。"哪些是 git 看不出的"这一分类（意外覆盖、被证伪的方案、被否决方案、2450 行归属、反判据键的存在）**方向正确**，其中"意外覆盖"与"137/41 出处"两条经我独立复现确认为**git 无法单独得出、只有会话能给出**。

---

## 5. t4 去重与完整性 + append-only 纪律

### 5.1 去重（无重复计数）
| 核对项 | 结果 |
|---|---|
| E1–E13 | t4 §0.3 明确"只计入 13 例一次"；§2.1 与附录 A 各出现一次；性质变更（E3 事故化 / E8 改写 / E9 过度推断 / E13 部分成立+反判据）集中在一处 | **通过** |
| A1–A5 | 仅 D-08 一处（"已闭环 1 / 修订 2 / 未缓解 2"），未在别处重复计 | **通过** |
| N1–N4 | 分别 → D-02（N1）/ D-04（N2）/ D-05（N3）/ D-07（N4），附录 A 逐条给了来源 | **通过** |
| 建议编号 | `B01–B14` 保留 + `B15/B16/B17` 新增；§4.2 自述"35 项 = 18 + 14 + 3"= **35 ✔**（我按表格 ID 计数：B01…B17 全部出现，无重号） | **通过** |
| t2 的 23 项未闭环（U1–U20 / I1–I4） | t4 正文只显式出现 `U1/U2/U5/U7/U11` 与覆盖缺口/I 类；但**关键词级覆盖检查通过**：`check_version` 11 次、`双根` 3 次、`relocalize` 5 次、`教练` 3 次、`3.4.2` 3 次、`EVO-072` 8 次、`命中率` 5 次、`时间戳` 2 次均出现在 consolidated 或两份 append 文档中 | **通过（但见 F-8 可追溯性）** |

### 5.2 append-only
| 文件 | 基线（独立来源） | 本轮动作 | 核验方法 | 判定 |
|---|---|---|---|---|
| `session-log-recommendations.md` | `blindspot-review-round2.md:6`（13:30，**早于 t4**）记 **981 行** | +150 行 → **1,131 行** | ① 文件**未被 git 跟踪**（`git ls-files --error-unmatch` → pathspec 不存在）⇒ **无法用 diff 验证**；② 用"追加不移动既有行号"的性质反证：A.8 块内被 R2 引用的 **L771 / L785 / L972 / L973** 内容与 R2 的期望值**逐位一致**（含 407/211 更正）；③ A.8 尾部 E-10 说明与 `---` 分隔仍在（L979-983），A.9 头在 **L985** | **本轮通过（方法受限）** |
| `session_logs_execution_plan.md` | R2 记 **1,046 行**；t4 记 1,045 | +122~123 行 → **1,168 行** | ① 第三轮块头在 **L1049**，其前 3 行为 `空行 / --- / 空行`（与 recommendations 的分隔风格一致）；② 18 项建议表（L68-85）与 E-1…E-6（L1040-1045）**全部仍在**；③ `git diff --numstat`（vs HEAD，HEAD 为老提交 `cd9a5a7`）**= +446/−38**，删除行全部落在**正文区**（旧行号 417/419/421/430/432/434/447/666/692/695/702/706/712/716/722/732/734/760），**属于 09-24→09-26 的多轮就地更正，早于本轮**，第三轮块（新行号 1046-1168）为**纯尾部追加** | **本轮通过；但该文件整体不是字节级 append-only（须如实登记）** |
| t4 是否改动 t2/t3 产出 | t3 自述"未修改"，t4 自述"未触碰 out-of-scope" | `session-analysis-0924-0926.md` mtime 13:47:09、`blindspot-crossvalidation.md` 13:50:14、`project-state-consolidated.md` 13:55:31；t4 的两份追加文档 mtime 13:54:55 / 13:55:14 ⇒ **顺序与声明一致** | **通过** |

> **更正一处**：t4 在 reco 文档里写"t2，**562 行** / t3，**559 行**"（与我的实测一致 ✔），但 **t2 自己的交付语写"563 行"**（实测 562 行：`count('\n') = 562`、`splitlines() = 562`）⇒ **t2 自报行数 +1（F-6）**。

---

## 6. 与前两轮已交付结论的一致性

| 主题 | 前两轮（R1 `session-log-analysis.md` / R2 `blindspot-analysis-0923-0926.md`） | R3（t2/t3/t4） | 冲突裁定 |
|---|---|---|---|
| `control.x` 写点 | R2：`main.py` 10 / 生产 14 / 含 `fly64/tests` 16 / 含根 `tests/` 17，且**未恶化** | 同（逐位一致） | **一致**（我用独立脚本复算，四点全部命中） |
| 13 例缺陷家族 | R2：13 例（E1–E13） | t3：13 例逐条裁定；t4：仍 13 例 | **一致**；t2 的"13/13 都能找到明确记载"**与 t3 的"10/13 直接证据"冲突** —— 我判定 **t3 更精确**：E1（311 命中全在 99cab60f 同源）、E2 的"声称面"确实不可验证；t2 的表述对"现象面"成立、对"声称面"过度。→ **建议 t2 改为"13/13 现象有记载；其中 2 例的声称面不可验证"** |
| 122× 计数 | R1 声明不引用失真聚合值；R2 E10 | R3 同 | **一致（未复发）** |
| `fbcc3d7` 改动量 | R2：`--numstat` = 115/39；137/41 记为"无法复现"（U11） | t3：137/41 = `git commit` 三文件汇总行 | **一致且前进**（我复现：`--stat` 3 文件 = 137/41，其中该文件 115/39） |
| EVO-072/073 被删 | R2 E3 | t3：性质改为"意外覆盖" | **一致**（我以 `HEAD~1` vs HEAD 集合运算逐位复现 added/removed） |
| `gate_jump` | R2 E7："生产者键被删、改为 ratio 键、消费者 default 兜底"（ratio 语义） | t4 §1.2 却写"**唯一的执行门** `jump = jump_rate > 0.04`（`model.py:2478`）"，同时 §3 D-15 又按 ratio 语义讨论 | **冲突，且 R3 内部亦冲突** → 裁定 **R2 E7 与 R3 D-15 有据（ratio 语义为工作区/活体版本）；R3 §1.2/§7.3 的引用须加 scope 或改写（F-2）** |
| `stuck_score` 假绿 | R2 E13（含 14 次仿真） | t3：部分成立 + 反判据、会话误判 | **一致（t3 更细）** |
| 未跟踪/脏树规模 | R2 未给统一数 | t2：26 M + 51 ?? | 26 **可复现（现测 27）**；**51 未复现（F-5）** |
| 工具口径（`Measure-Object`） | R2/t7：339/179 已废弃、改 407/211（**正确**） | R3 引用 407/211 | **一致**；但"两文件差值恒为 11"（R2 文档）**不成立（32 / 68）**，建议随 R2 更正 |

---

## 7. 残留扫描与引用校验

### 7.1 旧口径残留
全文（R1/R2/R3 共 5 份文档）扫描 `1826 / 1209 / 695 / 674 / 617 / 185 / 1131 / 当日工作量 / 339 / 179 / 137`：

| 旧值 | 出现语境 | 判定 |
|---|---|---|
| `185` / `617` | 只出现在"旧口径"列或明文更正语境（含引用禁令） | **已标注 ✔** |
| `674` | 作为"t2 口径合计"被引用 | **已标注 ✔** |
| `339 / 179` | 只出现在"⚠️ t7 更正：……已废弃"语境 | **已标注 ✔** |
| `137/41` | 均注明"`git commit` 三文件汇总行" | **已标注 ✔** |
| `1131` | **15 处，全部标为"权威"（4 份文档）** | **未标注且错误 → F-1（blocker）** |
| `model.py:2478` / `model.py:1842` | 分别 5 处 / 3 处，均为**无 scope 标注**的现时陈述 | **未标注且仅在 HEAD 成立 → F-2/F-3** |
| t2 自报 `563 行` | t2 交付语 | **与实测 562 不符 → F-6** |

### 7.2 `python scripts/verify_doc_citations.py`
```
EXIT=0
总计: 98 条引用 (含 632 裸 L)
通过: 98   警告: 96   失败: 0
[PASS] 所有引用校验通过！
```
- **通过（exit 0）** ✔ 满足验收项。
- **但必须登记一个覆盖边界**：该脚本的 `DOCS` 列表**只含 3 份文件**（`session-log-analysis.md`、`session-log-recommendations.md`、`session_logs_execution_plan.md`）。**R3 的三份新文档（t2/t3/t4 正文）不在其中** ⇒ `exit 0` 对它们**零保证**。
- 因此我对其中的关键引用做了**人工抽样复核**（§1.4 / §3.2）：`scene_context.py:234`、`test_what_i_see_protocol.py:68`、`memory.py:127/229/1541`、`main.py:61/220/2360/1316/3212`、`evolution_skill.py:202`、`test_version_consistency.py:28`、`test_gate_units.py:300`、`telemetry.py:94`、`central_complex.py:128/529/673` —— **全部逐位命中**；**失败的是 `model.py:1842`（注释行）、`model.py:2478`（工作区不符）、`memory.py:1985/1993-1995`（仅 HEAD 成立）**。
- 残留的 96 条 WARN 中，绝大部分是"符号就近一致性"的**假阳性**（`telemetry.py` 被要求匹配 `model.py` 的行、`scene_recognition.py` 被要求匹配 `main.py` 的行）——即 **R2 已记录的 S2 缺陷仍未修**（本轮 t4 的 B10 把它列为 P2 建议，方向正确）。

---

## 8. 诚实边界（本报告未能独立判定的项）

1. **WSL 活体读数**（crontab、`evo_stall_alarm.json` mtime、`evo_loop_launcher.sh --status`、`gate_jump_ratio` 采样、双份 `runtime/evolution_history.json`）——本轮**只做只读文件/git 核验，未执行 WSL 命令**，故 t3 §2.9 / §A.4 的活体结论**未复算**（状态存疑，不判错）。
2. **`2450 / 2485` 行归属**（t3 §4-4、O-2）——需定位会话中收口自述原文，本轮未做逐字定位（证据不足）。
3. **09-24 13:13:14 队长证伪 `3.082 > 3.0` 的原文**——未在导出集内直接检索到该时间戳的原文（M7 判为"部分成立"）。
4. **`HAS_EVO_LIVENESS=False` 的具体行号**（t3 给的 `L1978/L1986/L2002`）——存在性成立（400 次命中），**行号未逐行复核**。
5. **`0.043/tick`**——该数字不在当前 `model.py` 中（0 命中），属**派生量**（`raw_y = clip((forward_rate−0.008)*2000,0,70)` + `ctrl_y=70` 反解），来源为旧轮文档 `analysis-a4-autonomy-surface-inventory.md:145`。**作为"派生量"使用没问题，但与 §3.2 的 gate 引用叠加后指向了旧代码路径。**
6. **渲染修复的活体验证、`P0-a~d` 是否已施工**——超出只读范围。
7. 本轮**未运行 pytest**（不在验收项内）。

---

## 9. 必修正清单（含复现命令与建议改法）

| ID | 级别 | 问题 | 位置 | 复现命令 | 建议改法 |
|---|---|---|---|---|---|
| **F-1** | **blocker** | "重复副本 = 1131" 域混用：1826（全快照）− 695（窗口去重）。正确值 = **514**（= 1826 − 1312 = 1209 − 695） | **共 15 处**：`blindspot-crossvalidation.md:533,534,554`（3）；`project-state-consolidated.md:27,43,44,48,164,290,492`（7）；`session-log-recommendations.md:998,1000,1109`（4）；`session_logs_execution_plan.md:1062`（1） | `python .tmp/t5_verify/indep_count_t5.py` → `distinct callIds = 1312` / `redundant copies = 514` | 统一改写为三段式：**全局** `1826 / 去重 1312 / 重复副本 514`；**窗口** `快照合计 1209 / 去重 695 / 重复副本 514`；**窗口外** `617（无副本）`。并在 §0.1 增加一句"任何减法必须两项同域" |
| **F-2** | **high** | "唯一的执行门 `jump = jump_rate > 0.04`（`model.py:2478`）与前向池满速 0.043 同量级"**只对 HEAD 成立**；当前工作区 `:2478` 是无关注释，真实门在 `:2562-2566`，且已改为 **ratio 语义**（注释自述"replaces absolute occupancy threshold (jump_rate > 0.04)"） | **共 5 处**：`session-analysis-0924-0926.md:83,209,452`；`project-state-consolidated.md:109`；`blindspot-crossvalidation.md:271`（引用块内"LIF 解码门 \| `> 0.04` \| … \| `model.py:2478` \| ✅ 唯一的执行门"） | `git show HEAD:fly64/fly64/model.py \| Select-Object -Index 2477` → `jump = jump_rate > 0.04 …`；`Get-Content fly64/fly64/model.py \| Select-Object -Index 2477` → 注释；工作区 `:2562-2566` = ratio gate | ① 每条 `file:line` 标注 **`@HEAD`** 或 **`@工作区`**；② 现时结论改用工作区行号并写 ratio 语义（`jump_rate / max(forward_rate, FWD_RATIO_FLOOR) > 0.75`，`_jump_rate_ratio_gate = 0.75` at `model.py:678`），0.04-vs-0.043 的论证降级为"**迁移前（HEAD）的历史论据**" |
| **F-3** | **high** | `gain("jump")` **全仓库仅此一处**（`model.py:1842`）：工作区 `:1842` 是注释；实际 `get_gain("jump")` 有 **4 处**（`:1335`、`:1849`、`:1875`、`:1906`）+ `main.py:3212` 遥测 | `session-analysis-0924-0926.md:83,452`；`project-state-consolidated.md:108` | `python .tmp/t5_verify/jump_sites.py` | 改为「`get_gain("jump")` 共 4 个代码位点（`model.py:1335/1849/1875/1906`）；其中**把增益乘进电流注入**的只有 `:1849`（MBON→jump）与 `:1875`（记忆回放→jump），其余跳池注入腿为固定常数」并删除"全仓库仅此一处" |
| **F-4** | medium | "**87 处** write/edit 变更"未声明口径：原始调用 **126**、Σ 逐快照 unique(工具,路径) **87**、全局唯一路径 **63**、全局 unique(工具,路径) **69** | `project-state-consolidated.md:45`；源头 t1 `aggregatedStats.totalFileChanges` | `.tmp/t5_verify/indep_count_t5.py`（`write/edit main total = 126`）+ 逐快照 distinct 复算 | 写为「write/edit **调用 126**（逐快照取唯一 (工具,路径) 得 **87**，全局唯一路径 **63**）」 |
| **F-5** | medium | "**51** 个未跟踪"**作为 git 计数不可复现**：现测 `?? = 74`（剔除本轮 3 份新文档 **71**；`fly64/` 下 30；docs 下 30；无 `.pytest-run` 项）。看 t2 §5.2-**U8** 的正文，51 是**手工枚举**的"窗口内产出"子集（`docs/execution/` 目录 + 19 份 `docs/analysis/*.md` + 2 个 `fly64/scripts/*` + 3 个 `fly64/skills/*.py` + 20 个新测试 ≈ 45 项 + 目录项），**筛选判据未写出** | `session-analysis-0924-0926.md` §5.2-U8 | `git status --porcelain=v1 \| Where-Object {$_ -match '^\?\?'}` ⇒ 74 / 71 | 明写筛选判据（如"仅计窗口内新增、排除 pytest/缓存/本轮产出"）或改为 71（本轮前）/74（现测） |
| **F-6** | medium | t2 自报 **563 行**，实测 **562 行**（t4 转引的 562 正确） | t2 交付语 / 文档头 | `python -c "print(len(open(r'docs/analysis/session-analysis-0924-0926.md',encoding='utf-8').read().splitlines()))"` → 562 | 改 562 并写明计数方法（`splitlines()`） |
| **F-7** | low | §0.3 写"R3 新增**两项**（`B15`/`B16`）"，实际为 **三项**（`B15/B16/B17`） | `project-state-consolidated.md:79` | 文档内自检（§4.1/§4.2 列 B15/B16/B17） | 改"三项（B15/B16/B17）" |
| **F-8** | low | t3 的 **10 项遗漏（O-1…O-10）/ 7 项判断错误（X-1…X-7）** 编号在 t4 中 **0 次出现**（内容已并入，可追溯性不足） | `project-state-consolidated.md`（附录 A） | `python -c "import re,io;t=io.open('docs/analysis/project-state-consolidated.md',encoding='utf-8').read();print(len(re.findall(r'\bO-\d+\b',t)),len(re.findall(r'\bX-\d+\b',t)))"` → `0 0` | 附录 A 增加一列 `t3 O-/X- 编号`（内容可追溯） |
| **F-9** | low | `check_version.py` 未标路径（实际在 **`fly64/tests/`**，而 E1/E2 的语境常在 `fly64/skills/`） | t3 §2.2、t4 D-02、recommendations §A.9 | `Get-ChildItem -Recurse -Filter check_version*.py` → `fly64\tests\check_version.py` | 首次出现处写全路径 `fly64/tests/check_version.py` |
| **F-10** | low（跨文档） | "`Measure-Object -Line` 与 `wc -l` 两文件**差值恒为 11**"不成立（实际 32 / 68） | `blindspot-review-round2.md:396`（**非 R3 产出**，但被本轮链条引用） | `(Get-Content fly64/scripts/evo_liveness_guard.py \| Measure-Object -Line).Lines` = 339 vs 407；launcher 179 vs 211 | 更正为"差值分别为 32 / 68；机制属 PowerShell 行计数语义，不影响 407/211 的结论" |

---

## 10. 整体可信度评级

| 维度 | 评级 | 依据 |
|---|:--:|---|
| **事实可复现性** | **A−** | 计数（1826/12782/118/665/391/153/336/206/153/695）、git（115/39、HEAD~1 81 条、added/removed、38/176）、会话逐条（L1098、`cp` L1077、inode 296 vs 125256364637215400、4.48/4.88、4.48→4.88 的两分钟序列）**全部由我独立复现，无一处偏差** |
| **口径纪律** | **B** | "1826 ≠ 当日工作量"与"137/41 的出处"处理得**优于前两轮**；但**新权威口径 1131 自身域错**（F-1）、**87 处 write/edit 未声明口径**（F-4）、**51 未复现**（F-5） |
| **引用时效性** | **C+** | 16 条抽样里 **3 条**引用了**非当前工作区**的代码（`model.py:1842/2478` 无 scope 标注；`memory.py:1985/1993-1995` 为 HEAD 口径），其中 F-2 直接落在项目级"真问题"的核心句上 |
| **与上游一致性** | **A−** | 与 R1/R2 无事实冲突；对 t2 的 617/185/0 命中等缺陷的更正**方向与数值均正确** |
| **append-only 纪律** | **B+** | 本轮追加块均为尾部纯追加；两文件写入顺序与声明一致；但 reco **未被 git 跟踪**、plan 对 HEAD 有 38 行删除（跨轮累积）⇒ 严格"可审计 append-only"不可得 |
| **诚实标注** | **A** | t3/t4 主动划出"不可判定/证据不足"边界（O-1/X-1/X-6、§6.3"未做二次复算"），且会话权威缺口（09-25 21:00–21:18）被主动披露 |
| **综合** | **B+** | **可用于决策，但 F-1/F-2/F-3 必须先返修**——它们分别是"引用规则"本身、项目级"真问题"的核心代码句、以及一个会被引用的唯一性断言 |

**返修建议优先级**：F-1（口径规则，15 处）→ F-2（核心结论 scope，5 处）→ F-3（唯一性断言，3 处）→ F-4/F-5/F-6 → F-7/F-8/F-9（可与下一次同轮处理）。返修后**不必重跑全套**：只需 (a) 重跑 `.tmp/t5_verify/indep_count_t5.py` 确认 514 与 1312；(b) 抽查 `model.py` 两处新行号与 scope 标注；(c) `scripts/verify_doc_citations.py` exit 0。

---

## 附录 A：本轮复现脚本与命令清单（全部只读）

| 脚本（`.tmp/t5_verify/`） | 作用 | 关键输出 |
|---|---|---|
| `indep_count_t5.py` | 自写流式抽取器：逐快照 `tool/call`、子代理、write/edit、日期、callId 去重 | `1826 / 12782 / 14608 / 118 / 126 / 1312 / 514`；逐日 `665 / 391 / 153`；去重 `336 / 206 / 153` |
| `grep_jsonl.py` | 全文件正则定位（主会话 + 子代理），带本地时间与行号 | `EVO-072/073`、`833848c`、`38c8bae`、`evo_liveness_guard`、`HAS_EVO_LIVENESS`、`stuck_duration_true` 计数 |
| `exec_cmds.py` | 只统计**真实执行的命令**（`type=tool/call` + `name∈{pwsh,pwsl}` + arguments 命中） | `pkill`（09-26 仅 6c53f724-v3 ×3）、`check_version`（执行全在 99cab60f ×19）、`cp …evolution_history.json`（12:27:34） |
| `window.py` | 导出某会话某时间窗内的全部工具调用（时间/行号/description/命令前缀） | `fbcc3d7` 11 步链路全表（11:48:32→12:28:32） |
| `window2.py` | 定点检索两个会话在崩溃窗内的读数 | 11:48:31「重启完成」vs 11:51:59 `stuck_score=1.0 / stuck_duration_true=4.48`；11:54:03 `4.88` |
| `code_facts2.py` | 当前工作区代码事实复算 | 版本三元组、`memory.py` 213-225/234-235/127、`assert=0`、`control.x` 10/14/16/17、`burst_active`、`evo_loop_stale=0` |
| `jump_sites.py` | `get_gain("jump")` 全位点 + gate 现场 | `1335/1849/1875/1906`；工作区 gate `2562-2566` |
| `head_scope.py` | HEAD vs 工作区同号对照 | HEAD `model.py:2478` = absolute gate、HEAD `memory.py:1993-1995` = 泄放、HEAD `main.py:2957` = `"gate_jump": gate_open_hz(...)` |
| `cites_check.py` | R3 新文档引用的逐行落地检查 | 全部命中，除 `model.py:1842`、`model.py:2478`（工作区）、`memory.py:1985/1993-1995`（工作区） |

`scripts/verify_doc_citations.py` → **exit 0**（98/98 引用通过，96 警告；**不覆盖 R3 三份新文档**，见 §7.2）。
