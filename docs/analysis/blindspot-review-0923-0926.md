# 盲区分析独立核验报告：2026-09-23 09:58 → 09-26 盲区（t2/t3 事实性 · 时效性 · 数字准确性）

> **核验者**: `verifier`（AgentTeams `fly64-blindspot-0923-0926` / task `t4`）
> **attempt_id**: `b0f9f1a4-f4cd-4872-9059-123823d5ab43`
> **核验时刻**: 2026-09-26 12:44 → 13:08 (+0800)；最后一次活体采样 `13:02:10`；WSL 侧最后一次取证 `12:56–13:03`
> **核验对象**: `docs/analysis/blindspot-analysis-0923-0926.md`（t2）、`docs/analysis/blindspot-evidence-0923-0926.md`（t1）、`docs/analysis/session-log-recommendations.md` + `docs/analysis/session_logs_execution_plan.md`（t3）
> **对照基准**: `docs/analysis/session-log-analysis.md`（已交付，09-24）、`docs/analysis/session_logs_analysis_v5.md`
> **基线 HEAD**: `fbcc3d7`（工作树与 HEAD 同指针；未提交改动仍在）
> **方法**: **不采信转述**。每条结论回到 git 对象、当前代码、WSL 活体或 HTTP 遥测重跑一遍；凡复现失败的，先给出**核验者自己的命令与原始输出**，再判定。**未修改 t1/t2/t3 任何文件**（仅新建本报告）。
> **纪律**: 严格区分 **已复现 / 未复现（≠ 不成立） / 不成立 / 证据不足**；`[实测]` 附命令，`[推断]` 附链条。

---

## 0. 结论摘要

| 项 | 判定 |
|---|---|
| **整体可信度评级** | **中高（可信，需修 5 处必修正项）** — 结构性结论（窗口定界、E1/E2/E3/E5/E7/E9、未入库规模、活体停摆、版本回退）**逐条独立复现通过**；缺陷集中在**数字口径**（A4 计数、行号清单）与**一条被推翻的闭环结论**（A3「已解决」的部分表述、B3「构造伪影已消除」）。 |
| **必修正项** | **5 条**（M-1 ~ M-5，见 §7）。其中 **2 条阻塞**（M-1、M-2）。 |
| **返修归属** | **M-1 / M-3 / M-4 → 返修 t2**（其产出 `blindspot-analysis-0923-0926.md`，属于 t4 的 out-of-scope，由 captain 决定是否重开）；**M-2 / M-5 → 由 t3 以 append-only 补充说明**（两文件均在 t3 的 in-scope，但其自身结论已被 t3 主动标注为观察项，故不是"错误"而是"时效性升级"）。 |
| **A4 `control.x` 队长裁定** | **裁定：t2 的「恶化 10→12（生产口径 14→16）」不成立**——12/16/18 是正则把 `control.x == 0` **比较**计入的伪影。应统一为 **`main.py` 10 / 生产 14 / 含 tests 17**（≠队长口述的 16，见 §4.2-N4）。队长提供的 `re.findall(r"control\.x\s*=(?!=)", …)` **可复现 10**，但队长口述的"命令：`control\.x\s*=`"**不可复现 10，实测 12**。 |
| **`stuck_score` 活体矛盾裁定** | **现象成立且已离线复现**（`stuck_score` 可达 1.0 而同刻 `stuck_duration == 0.0`）；但 t2 的 A3「✅ 已解决」**在单位口径上成立、在可观测性口径上不成立**；**B3「构造伪影已消除」必须改写**（不是"需撤回的观察项"，而是"已复现的假绿"）。详见 §6。 |
| **t1「本窗口无相关 commit/记录」抽查** | **抽查 4 条，3 条完全属实、1 条口径需收紧**（P0-1~P0-4 记录数为 0 ✔；`agent.md` 09-24/25/26 零条目 ✔；09-25 21:15→09-26 11:47 无提交/无部署 ✔；`git stash` 未被使用需补查，已补：**`git stash list` 为空**，见 §5.3）。 |

---

## 1. 核验方法（与 t2 独立在哪里）

| 维度 | 本次做法 | 与 t2 的差别 |
|---|---|---|
| 数据源 | 只用 `git show/rev-parse/status/numstat`、当前工作区文件字节、WSL `/root/fly64` 文件系统、`http://127.0.0.1:8765/{memory,flow}.json` | 不复述 t1/t2 的任何命令输出，全部重跑 |
| 定义 | 计数一律**先冻结正则/口径，再计数**，并把正则打印出来 | t2 的 A4 计数未打印正则（导致 `==` 混入） |
| 时间戳 | 一律用 `ls -l --time-style=+…` 与 `date -d @epoch` 双方换算 | t1 部分用 mtime 推断 |
| 判据 | 结论分四档：**已复现 / 未复现 / 不成立 / 证据不足** | t2 只分 `[实测]/[推断]/[未验证]` |
| 反例优先 | 对每条"已解决/已消除"结论主动构造反例（离线仿真 + 活体长采样） | t2 对 A3 只做了单点采样 (`0.08`) |

---

## 2. 抽样回溯：≥6 条 t2 结论 → 原始证据逐条核验

> 判定档：✔ **已复现**（成立）｜✘ **不成立**｜？ **证据不足/无法核验**

| # | t2 结论（位置） | 核验者证据来源（命令 + 原始输出） | 判定 |
|:-:|---|---|:-:|
| **V1** | 窗口内 **12 个提交**，首个 `78b3175`（09-23 12:42:27），分布 6/3/2/1（§1.1） | `git log --since="2026-09-23 00:00" --until="2026-09-27 00:00" --pretty=format:"%h %ad %s" --date=format:"%Y-%m-%d %H:%M:%S"` → 12 行；首行末 `fbcc3d7 2026-09-26 12:28:02`，第 12 行 `78b3175 2026-09-23 12:42:27`；其余 8 条均 ≤ 09-23 09:50:02（与 t2「多带回 8 条」一致） | **✔ 已复现** |
| **V2** | 「窗口末提交 `fbcc3d7` 删除 EVO-072/073」（E3，§3.2） | ① `git log --oneline -S'"EVO-072"' -- fly64/skills/evolution_history.json` → `fbcc3d7` + `6d0aa42`；`-S'"EVO-073"'` → `fbcc3d7` + `2f87d77`（**双向确认**）② HEAD~1 解析：`records 81`、含 EVO-072/073=True、含 EVO-074=False；HEAD：`records 87`、EVO-072/073 不存在 ③ `canonical_versions`: HEAD~1 `skill 3.5.1` → HEAD `skill 3.4.2` ④ `git show fbcc3d7 --numstat -- …/evolution_history.json` → `115  39` | **✔ 已复现（含 3 个独立视角）** |
| **V3** | `memory.py:135` = `0.008 per-tick`，`:207-208` 带单位注释（A3/C1） | 逐行打印：`135 rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`；`207 # P0-a2: both sides are per-tick fractions ∈ [0,1] (see RULE-19).`；`208 if forward_rate < self.rate_threshold:` | **✔ 行号与内容精确命中**（结论本身见 §6，需拆分） |
| **V4** | E7：HEAD 发布 `"gate_jump": gate_open_hz(...)`，工作区删键，消费者 `scene_context.py:234` `default=False`（§3.2） | `git show HEAD:fly64/fly64/main.py` 含 `"gate_jump": gate_open_hz(_jump_rate_hz, _gate_jump_hz),`；工作区同文件**只含** `"gate_jump_threshold_ratio"` 与 `"gate_jump_ratio"`；`fly64/plugin/scene_context.py:234` = `gate_jump=bool(_get_safe(flow, "gate_jump", default=False)),`；活体 `flow.json` **无 `gate_jump` 键**（122 键） | **✔ 已复现** |
| **V5** | E8：`burst_active`「无发布点」、`evo_loop_stale`「全仓 .py 零命中」（§3.2） | `evo_loop_stale`：全仓 `.py` 命中 **0**（只在 8 份 md/team.json 里出现）✔。`burst_active`：**工作区 `main.py:2206 model.burst_active = _deadlock_burst_active…` 存在**，但**不写入任何 HTTP 端点**（活体 `flow.json`/`memory.json` 均无该键）⇒ 表述应精确为「无 **flow/memory 发布点**」，t2 原文「全仓仅出现在函数形参与读取处，无发布点」**与实测不符**（存在 `model.burst_active =` 赋值） | **✔ 结论成立 / 表述需收紧** |
| **V6** | 未入库规模：36 文件 +4890/−469；未跟踪 ~62–63 项（§2.2） | `git diff --shortstat -- . ':(exclude)fly64/.pytest-run' ':(exclude).tmp-pytest'` → **`37 files changed, 4995 insertions(+), 481 deletions(-)`**（t2 之后 t3 又写了 2 份文档：+105/−12 恰为差额 4995−4890=105、481−469=12）；`git status --porcelain | ?^\?\? |` → **65** 行；`docs/analysis` 窗口内 md **28 份 = 19 未跟踪 + 1 `M` + 6 已提交干净**（§4.5） | **✔ 已复现（t2 时点数字自洽：减去 t3 两份即 36/4890/469）** |
| **V7** | 规则 8 守卫 `check_version.py` 4 行空壳（E2） | 逐行读出 4 行：`import sys` / `sys.path.insert(0, "/root/fly64")` / `from fly64.main import BRAIN_VERSION` / `print(...)`；正则扫描：**无 assert、无 `==`/`!=`、无 canonical、无 skills.md**；WSL 实跑输出 `loaded BRAIN_VERSION: 2.24.0` | **✔ 已复现** |
| **V8** | E1：守护未接调度、告警器不运行、闭环停摆（§3.2） | WSL：`crontab -l` → **仅** `watchdog.sh` / `phase2_gate.sh`；`scripts/evo_liveness_guard.py` 存在（15863 B，**09-25 20:58:52**），`skills/evo_liveness_guard.py` 不存在 ⇒ **t2 写作 `fly64/skills/evo_liveness_guard.py`，实际在 `fly64/scripts/`**（t1 同错）；`skills/evo_stall_alarm.json` mtime **2026-09-25 21:01:25**，内容 `"stale": false, "checked_at": 1790341285.88`（`date -d` = 09-25 21:01:25 +0800）；`bash scripts/evo_loop_launcher.sh --status` → `tmux [fly64-evo]: ○ 未运行 / 进化闭环: ○ 未运行 / evolution_log.jsonl 最后写入 4134s 前`；`skills/evolution_log.jsonl` mtime **11:47:29**、200186422 B | **✔ 已复现（1 处路径需更正）** |
| **V9** | 活体 `clamped_keys ∈ flow.json` ✔ / `∈ memory.json` ✘（E5） | 活体：`flow.json` **122 键**、`memory.json` **61 键**；`'clamped_keys' in flow → True`，`in memory → False` | **✔ 已复现** |
| **V10** | 活体 `evolution_skill.py` 工作区 `97b178298e88` ≠ 活体 `fd1ccd56af24`（E9） | WSL `md5sum`：`skills/evolution_skill.py = fd1ccd56af2498e4ace97574fce3df8f`；本地同路径 `97b178298e88…`（t2 数值命中）；同批 `fly64/memory.py = 3f9dc7f82a14…`、`fly64/main.py = a79fe51de2c7…`（**与工作区逐一相同**） | **✔ 已复现** |
| **V11** | 活体 `evolution_history.json` 两侧 md5 相同 `d98c46f96e7d`（E3 同步结论） | WSL `md5sum skills/evolution_history.json` = `d98c46f96e7d58128c5707e182ef4be2`；Windows 同路径 md5 相同 ⇒ **删除确实已同步进活体** | **✔ 已复现** |
| **V12** | 窗口内 gate 单位契约生效：`forward_rate_hz` 不再恒 46–50、`gate_jump_ratio` 可达（§2.1 #4） | 我 54 点活体采样（12:56–13:02，5–6 s 间隔）：`forward_rate_hz ∈ {0, 3.85, 5.77, 7.69, 9.62, 11.54, 13.46, 15.38, 19.23, 23.08}`；`flow.gate_jump_ratio` 键存在、`gate_jump_threshold_ratio = 0.75`（采样窗口内 `None` 与数值交替） | **✔ 已复现（方向一致；样本少于 t2 的 6 点门控判定，未逐点复核 4/6>0.75）** |

**抽样小结**：12 条抽样中 **11 条成立**、**1 条（V5）表述需收紧**；**2 处路径/口径错误**（E1 的 guard 路径、A4 的正则）。

---

## 3. 时效性核验：「已修复 / 已闭环」声明在当前工作区可确认性

| 声明（来源） | 当前工作区可确认性 | 判定 |
|---|---|:--:|
| **P1-N1**「StuckDetector 单位文档化 **+ 运行时断言**」（t3 §A.1/§A.2，标 ✅ 本窗口闭环） | **单位文档化 ✔**：`memory.py:135` 注释 + `:207` 单位说明 + `:142` 赋值，逐行确认。**运行时断言 ✘**：`memory.py` 内 `rate_threshold` 出现处仅 `135/142/208`（我 grep 全文件），**无任何 assert/量级校验** ⇒ 任务标题的"断言"这一半**从未实现** | **⚠️ 状态存疑 → 必修正 M-3**（"闭环"仅成立于"文档化"一半） |
| **A3（困境 3）✅ 已解决**（t2 §4.1-A3、§4.4-C1；t3 并入 P1-N1 关闭） | 单位对齐**可确认**；但**可观测性未解决**：`StuckDetector.rate_threshold` 是 **per-tick 比例**，而活体 `flow.forward_rate` 是**每 tick 位移比例（0–0.46）**、`flow.forward_rate_hz` 是**Hz（0–23）**——`memory_ctrl.update(forward_rate=…)` 收到的确实是 per-tick 比例（`main.py:2787` clip 到 [0,1]）⇒ 量纲**自洽**，但 docstring `memory.py:127`「forward_rate collapses (< 5 Hz for >3 s)」**仍写着 Hz**，`rate_threshold=0.008` **永不与"<5 Hz"等价** | **⚠️ 部分不成立 → 必修正 M-1**（详见 §6） |
| **B3「`stuck_score ≡ 1.0` 构造伪影已消除」**（t2 §4.2-B3；t3 §A.3 第 9 行标"部分缓解"） | **可确认未消除**：离线仿真 + 活体长采样双向证实 `stuck_score` 仍可饱和到 **1.0**，并可出现在 `stuck_duration == 0.0` 的同一快照中 | **✘ 不成立 → 必修正 M-2** |
| **R6/建议 2「把 EVO 守护接入调度」**（t2 §7-2） | 当前 **未接入**：`crontab -l` 仅 2 条；`evo_stall_alarm.json` 停在 09-25 21:01:25 ⇒ 建议仍待执行（与 t2 一致，**无过时问题**） | ✔ 一致 |
| **E9「P0-2/P0-4 不在活体」** | 可确认：`evolution_skill.py` 两侧 md5 不同（V10）；`deploy-manifest.md` §3.1 记录的 `f895171ee477` 与两侧均不等 | ✔ 一致 |
| **t3「P1-N1 完成时间：本窗口内（≥09-23），具体提交时间不可定位」** | 可确认不可定位：`memory.py` 未提交（`git status` 中为 ` M`），且 `git log -p -- fly64/fly64/memory.py` 的最后提交早于窗口 | ✔ 一致 |

---

## 4. 数字与行号独立复算（重点防范三类历史失真）

### 4.1 numstat vs `--stat`（防"图形总数当改动量"）

| 对象 | 队长曾报 | t2 报 | **核验者实测** | 判定 |
|---|---|---|---|---|
| `fbcc3d7 -- evolution_history.json` | +137/−41 | 115/39 | `git show fbcc3d7 --numstat` → **`115  39`**；`--shortstat` → `1 file changed, 115 insertions(+), 39 deletions(-)` | **115/39 正确**；137/41 无法用 git 复现 ⇒ t2 §6-U11 的处置正确 |

### 4.2 `control.x` 写点计数（队长指定必裁定项）

**A. 正则定义与复现（逐字命令）**

```python
# 队长口述口径（无 lookahead）
naive  = r'control\.x\s*='
# 赋值口径（排除 == / != / <= / >=）
assign = r'control\.x\s*=(?!=)'
```

**B. 三口径实测（2026-09-26 12:45，工作区 = HEAD 对 main.py 无差异）**

| 口径 | `fly64/fly64/main.py` | 生产（排除 `tests/`、`.venv`、`.pytest_cache`、`.tmp`） | 含 `tests/` |
|---|:-:|:-:|:-:|
| `control\.x\s*=(?!=)`（**赋值**，正确口径） | **10** | **14** | **17** |
| `control\.x\s*=`（**朴素**，队长口述的命令） | **12** | 16 | 19 |
| 差值来源 | `main.py:2618 and control.x == 0 and control.y < 8`、`main.py:2959 "control_x_zero": control.x == 0,`（**比较**，非写点） | 同源 | 同源 |

**C. 赋值口径的 10 个写点（当前行号，实测）**

`[760, 2060, 2077, 2141, 2190, 2192, 2406, 2414, 2466, 2492]`
→ `760 control.x = int(np.clip(round(control.x + dx), -80, 80))`（reflex）｜`2060 control.x = turn_dir`｜`2077 = int(cliff_turn_bias)`｜`2141 = action["control_x"]`（LLM）｜`2190/2192`（burst/结束）｜`2406/2414`（test mode）｜`2466/2492`（nav）

**D. 窗口前后对比（防"恶化"误判）**

| 版本 | 赋值口径 | 朴素口径 |
|---|:-:|:-:|
| `2f87d77^`（窗口前） | **10** | 12 |
| `HEAD` `fbcc3d7` | **10** | 12 |
| 工作区（未提交） | **10** | 12 |

⇒ **窗口内既无新增也无减少；仅行号漂移**（见 E）。

**E. 行号漂移实测（防"~1000 行漂移"）**

`session-log-analysis.md`（09-24 交付）§困境 4 列出的 10 个写点行号 vs 当前实测：

| 文档行号（09-24） | 当前实测行号 | 漂移 |
|:-:|:-:|:-:|
| L760 | 760 | 0 |
| L1948 | 2060 | +112 |
| L1965 | 2077 | +112 |
| L2029 | 2141 | +112 |
| L2078 | 2190 | +112 |
| L2080 | 2192 | +112 |
| L2286 | 2406 | +120 |
| L2294 | 2414 | +120 |
| L2346 | 2466 | +120 |
| L2372 | 2492 | +120 |

⇒ **漂移 +112 ~ +120 行**。**已交付文档 `session-log-analysis.md` §4/§困境 4 的行号清单已过时**（该文件不在 t4 in-scope，仅记录；t2 未提，属**遗漏项 O-3**）。t3 已在 `session-log-recommendations.md` L341/L355/L475 用当前行号替换，**修正正确**（我逐条比对 10 处，全部命中）。

**F. 裁定**

> **「t2 称 A4 恶化 10→12（生产 14→16）」→ 不成立。**
> ① t2 未打印正则（我的报告在此补上）② 12/16/18 恰好等于**朴素正则**的匹配数（把 2 个 `==` 比较计入）③ 在正确赋值口径下，窗口前/HEAD/工作区**三处均为 10**，生产口径 **14**。
> **应采用数字：`main.py` = 10（行号如上）／生产 = 14／含 `tests/` = 17。**
> ⚠️ 队长口述的「含测试 = 16」**少 1**：生产 14 + `fly64/tests/test_evolution_capability.py` 1 + `fly64/tests/test_fix_template_interpreter.py` 1 + 根 `tests/test_memory_avoidance.py` 1 = **17**。若把"含测试"限定为 `fly64/tests/` 则 = **16** —— 两种口径都成立，**报告必须写明限定**（这正是本项目反复出现的口径事故）。

### 4.3 记录数账（防"计数失真"）

| 对象 | t2/t1 报 | 核验者实测 | 判定 |
|---|---|---|---|
| `evolution_history.json` HEAD `records` | 87 | **87** | ✔ |
| HEAD~1 `records` | 81（+2 删 −? 增） | **81**；`EVO-072/073` 存在、`EVO-074` 不存在 | ✔ |
| 窗口内记录（`date ≥ 2026-09-23`） | 仅 `EVO-074`（09-24, ops） | **仅 `EVO-074` 1 条** | ✔ |
| `AUTO-0023` | 占位、无 `date` 字段，`recorded_at=2026-09-23T12:54:49Z` | 确认：`date=None`、`recorded_at=2026-09-23T12:54:49.422547+00:00`、`kind=brain_update_auto` | ✔ |
| `canonical_versions` | `skill 3.4.2` vs `main.py:50` `3.5.1` | `{'brain': '2.24.0', 'skill': '3.4.2', 'as_of':'2026-09-24T18:00:00+08:00'}`；`main.py:49 BRAIN_VERSION="2.24.0"`、`:50 SKILL_VERSION="3.5.1"` | ✔ |

### 4.4 行号抽查（10 处，全部指向当前代码）

| 引用 | 核验者读到的内容 | 判定 |
|---|---|:--:|
| `main.py:1316` | `"overridden by the safety clamp; see /memory.json clamped_keys",` | ✔（"观测点指向 memory.json"成立） |
| `main.py:2867` | `model.progress_ineffective = (` | ✔ |
| `main.py:3265` | `"no_progress_gate": bool(` | ✔ |
| `main.py:795` | `def rate_per_tick_to_hz(rate_per_tick: float, dt: float) -> float:` | ✔ |
| `central_complex.py:128` / `:529` / `:673` | `def relocalize(self, scene_id: int | None, confidence: float) -> None:` / `self._path_integrator.relocalize(scene_id, confidence)` / `…relocalize(scene_id, scene_confidence)` | ✔ |
| `scene_context.py:234` | `gate_jump=bool(_get_safe(flow, "gate_jump", default=False)),` | ✔ |
| `test_what_i_see_protocol.py:68` | `"gate_jump": False,` | ✔ |
| `test_gate_units.py:300` | `for key in ("gate_forward_threshold_hz", "gate_jump_threshold_ratio"):` | ✔ |
| `memory.py:135 / :207 / :208` | 见 V3 | ✔ |
| t2 §2.2「`evolution_skill.py` 2555 行变动」 | 我无法用 `git diff --numstat` 复现该单文件数字（t2 的 2485/−70 属 `git diff` 口径；`git status` 显示该文件仍在工作区），**文件当前总行数 5357**（t2 §2.3 称 4911 行，WSL 侧 wc 未复核） | ？ **证据不足**（不影响结论） |

### 4.5 入库/未入库计数（口径必须写清）

| 口径 | 实测 |
|---|---|
| `git diff --shortstat`（排除 `.pytest-run`/`.tmp-pytest`） | **37 文件 / +4995 / −481**（t2 时点 = 36 / +4890 / −469，差值 = t3 两份文档） |
| `git status --porcelain \| grep '^??'` | **65 行**（t2 说「63 项」、t3 说「65」；按 `^\?\?` 行数**当前确为 65**） |
| `git status --porcelain -uall \| grep '^??'` | 354 个文件（**未跟踪目录展开后的真实文件数**） |
| `docs/analysis/**` 窗口内 md | **28 份** = 19 未跟踪 + 1 `M` + **6 已提交干净** |
| t1「只有 4 个文件进了 git / 19 未跟踪」 | **不成立**：索引口径为 7 份（6 committed clean + 1 `M`），未跟踪 19 份（t2 说 18 份，差 1 份 = 其自身文档，**t2 的口径更自洽**） |

---

## 5. 一致性核验（对照已交付文档）+ 「无证据」声明抽查

### 5.1 t2 §4.4 七点冲突/更新逐点裁定

| 点 | t2 声称 | 核验者独立结论 | 哪一方有据 |
|:-:|---|---|---|
| **C1** A3 单位「已解决」 | 与 09-24「单位混淆风险仍存在」冲突 | **部分有据**：`memory.py:135` 已改（09-24 的 `5.0` 确实不存在）⇒ 已交付文档的"代码位置"过时；**但** 09-24 的核心担忧（"不同帧率下可能误判"）**在新量纲下仍成立**（docstring 仍写 Hz、`rate_threshold` 在 per-tick 域语义为"几乎完全静止"）。**t2 在此点上过头**：应表述为"单位标注已对齐，语义与文档仍不一致，且 rate 子信号易被 idle 误触发" | t2 对"行号已变"有据；t2 对"已解决"**过头**（见 M-1） |
| **C2** CX-2「无视觉闭环校正」不成立 | 需回改已交付文档 §5 困境 2 | **有据**：`relocalize()` 定义 + 2 个调用点 + 测试都在（V 表 §4.4 已验）。已交付 `session-log-analysis.md:378` 的表述确已过时 | **t2 有据；建议回改已交付文档**（`session-log-analysis.md` §困境 2 的"无视觉闭环校正"） |
| **C3** #5 策略穿透「仍部分」 | 更新为"缺口精确化" | **有据**（活体 `source="unknown"` 部分我于 12:56 采样 `clamped_keys = []`，该键在无钳位时为空列表 ⇒ 无法在同一时刻复核 `source`；但 `memory.json` 无该键、`flow.json` 有此键的结构性事实已复现） | **t2 有据（结构层）；"source 恒 unknown"本次未复现（窗口内该时刻无钳位事件）→ 标注为"未复现 ≠ 不成立"** |
| **C4** §4.4 持续性风险「已升级为事实」 | 新增 E2/E7/E8 + 守护无调度 | **有据**（E7/E2 已复现；E8 结论成立但表述需收紧；E1 路径需更正） | t2 有据 |
| **C5** v5「已缓解」需降级 | 机制上线 ≠ 可判定 | **部分有据**：观测点错位已复现；`source/归因`本次未复现（见 C3） | 部分有据 |
| **C6** A1 常量未抽取 | `model.py 0.12×7 / 0.15×20` | **符号正确**（未逐值复跑 60/162 的全仓口径） | ✔ 未反驳 |
| **C7** P1-4/P1-5 未收敛 | 磁盘 134GB / 78% | `du -sh /tmp` → **135G**；`ls /tmp/f64r_traj-*.npz \| wc -l` → **3435**；`df -h /` → `744G/1007G 78%` | ✔（134→135 为同一量级的滚动值） |

### 5.2 未发现矛盾的要点（与已交付一致）

- 已交付 §4.2 的 **12 例清单**（我逐条读了 307–318 行，与 t2 §3.1 引用一致，**未移动基线**）✔
- 已交付 §4.4 的定性（"缺乏契约审计 / 测试只验触发不验生效 / 集成验证缺失"）在本窗口被 E1/E2/E7/E8 再次证实 ✔
- **唯一需要回改的已交付文本**：`session-log-analysis.md:378`（CX-2 无视觉闭环校正）与 `:388–394`（`rate_threshold = 5.0` 行号/取值）。**这两处已交付文档过时属事实，建议 captain 决定是否回改**（T4 in-scope 外）。

### 5.3 t1「本窗口无相关 commit/记录」抽查（防止把遗漏误报为不存在）

| t1 声明 | 核验者交叉验证 | 判定 |
|---|---|:--:|
| 「09-25 的 P0-1~P0-4 **无 evolution_history 记录**」 | `records` 中 `date ≥ 09-23` 仅 `EVO-074`；`AUTO-0023` 的 `date=None`（`recorded_at` 在窗口内但**不是** P0 记录）⇒ **确为 0 条 P0 记录** | **✔ 属实** |
| 「`agent.md` 09-24/25/26 零条目」 | `git log -1 --date=short -- agent.md` → `2f87d77 2026-09-23`；`agent.md` mtime **2026/9/23 20:50:31** ⇒ 窗口内三天零写入 | **✔ 属实** |
| 「09-25 21:15 → 09-26 11:47 无 commit / 无部署 / 无 EVO 心跳」 | 无提交（V1 列表）；WSL `.deploy_backup` 快照全在 09-25（t1 报，我未复核）；`evolution_log.jsonl` mtime `11:47:29`、`runtime/evolution_history.json` mtime `12:56`（**运行时会话每轮重写**，不算窗口"事件"） | **✔ 属实（"无部署"一列未独立复核）** |
| 补充抽查：是否存在被**隐藏**的工作（stash/其他分支/其他 worktree） | `git stash list` → **空**；`git branch -a` 与 `git worktree list` **未在本次执行**（列为 U） | **✔ 已补 1 项；仍有 2 项未查** |

---

## 6. 必须裁定的活体回归：`stuck_score` 爬升到满值 vs `stuck_duration=0.0`/`idle`

### 6.1 我自己的重采（可复现）

命令（每一轮取 `/memory.json` + `/flow.json`，间隔 5–6 s）：

```powershell
python -c "import json,urllib.request as u,time;
for i in range(6):
 m=json.load(u.urlopen('http://127.0.0.1:8765/memory.json',timeout=4))
 f=json.load(u.urlopen('http://127.0.0.1:8765/flow.json',timeout=4))
 print(m.get('stuck_score'),m.get('stuck_duration'),m.get('stuck_duration_true'),f.get('forward_rate'),f.get('forward_rate_hz'),m.get('disp_60s'));time.sleep(6)"
```

**第一组（12:54:31–12:55:01，6 点，全部命中 1.0）**：

```
12:54:31 stuck_score=1.0 stuck_duration=0.0 anomaly=idle progress_ineff=True
12:54:37 stuck_score=1.0 stuck_duration=0.0 anomaly=idle progress_ineff=True
12:54:43 stuck_score=1.0 stuck_duration=0.0 anomaly=idle progress_ineff=True
12:54:49 stuck_score=1.0 stuck_duration=0.0 anomaly=idle progress_ineff=True
12:54:55 stuck_score=1.0 stuck_duration=0.0 anomaly=idle progress_ineff=True
12:55:01 stuck_score=1.0 stuck_duration=0.0 anomaly=idle progress_ineff=True
```

**第二组（12:55:36–12:57:38，爬升形态复现）**：

```
12:55:36 ss=0.00 sd=0.0 fr=0.3077 (15.38 Hz) disp=1314.7
12:55:42 ss=0.17 sd=0.0 fr=0.3077
12:55:48 ss=0.00 sd=0.0 fr=0.1538
12:56:52 ss=0.06 sd=0.0 fr=0.0000 (0.00 Hz) disp=3011.8
12:57:28 ss=0.44 sd=0.0 fr=0.1154 disp=2927.5
12:57:33 ss=0.67 sd=0.0 fr=0.1538 disp=3000.9
12:57:38 ss=0.15 sd=0.0 fr=0.0000 disp=2642.6
```

**第三组：13:00:04–13:00:14** `ss 0.23 → 0.46 → 0.70`（同类爬升-复位）。
**长采样统计**：12:56:32–13:02:10 共 **54 点**，`stuck_duration` **恒为 0.0**；`stuck_score` 峰值 **0.70**（未再出现 1.0，说明它是**相位相关**的：仅在 `forward_rate` 连续 0 且 `temporal_energy` 连续 < 0.05 的窗口出现）。

⇒ **裁定 1：现象可复现（12:54 我独立取得 6 连 1.0），但它是"驻留片段"而非单向趋势**——同一分钟已回落到 0.0。**t3「单点不可当趋势」的判断正确**，队长"5 连爬升"的形态也复现（0.44→0.67、0.23→0.46→0.70）。

### 6.2 `stuck_score` 构成（代码走查）

`fly64/fly64/memory.py:213-225`：

```python
temporal_stuck = self._temporal_low_s >= self.temporal_stuck_s   # 2.0 s
frame_stuck    = self._frame_still_s  >= self.frame_stuck_s      # 5.0 s
rate_stuck     = self._rate_low_s     >= self.rate_stuck_s       # 3.0 s
t_score = min(1.0, self._temporal_low_s / self.temporal_stuck_s)
f_score = min(1.0, self._frame_still_s  / self.frame_stuck_s)
r_score = min(1.0, self._rate_low_s     / self.rate_stuck_s)
stuck_score = max(t_score, f_score, r_score)          # ← 三者取最大
currently_stuck = temporal_stuck or frame_stuck or rate_stuck or self._fallen
if currently_stuck: self._stuck_duration += self._dt   # +0.02
else:               self._stuck_duration = 0.0
if self.disp_60s is not None and self.disp_60s > 500.0 and self._stuck_duration > 0.0:
    self._stuck_duration = max(0.0, self._stuck_duration - 1.0)   # ← :234-235 泄放
```

**哪个子信号在 `idle` 时恒真**：不是 `temporal`（需要 `temporal_energy < 0.05` 连续 2 s），也不是 `frame`（需要 `frame_seq` 连续 5 s 不变），而是 **`rate` 子信号**：只要 `control.forward_rate` 连续 3 s 为 0（`flow.forward_rate` 实测在 idle/受阻片段**确为 0.0000**，见第二/三组采样），`_rate_low_s ≥ 3.0` ⇒ `r_score = 1.0` ⇒ `stuck_score = 1.0`。

**为什么同刻 `stuck_duration` 仍是 0.0**：`:234-235` 的泄放条件 `disp_60s > 500` 在活体**常驻满足**（实测 1314–8645），而泄放是 **−1.0/次**、增长是 **+0.02/tick** ⇒ 只要该 tick 的 `disp_60s > 500`，`_stuck_duration` 被一次性抹回 0（`max(0.0, ·)` 兜底）。**离线复现（我的仿真，非 t2 数据）**：

```
# 模拟：fr=0 与 fr=0.3 交替、disp_60s=1090（>500，泄放生效）
tick=299  te=0.0 fr=0.0 score=1.000 dur_published=0.000 rate_low_s=2.00 temporal_low_s=2.00 raw_dur=0.0000
tick=499  te=0.0 fr=0.0 score=1.000 dur_published=0.000 ...
总命中数：3000 tick 内 14 次 (score==1.0 且 dur==0.0)
对照：disp_60s=None（泄放失效）时 score=1.000 且 dur=2.020（一致，无矛盾）
```

### 6.3 裁定

1. **矛盾成立，且是"观测层"缺陷而非"检测层"缺陷**：`stuck_score` 与 `stuck_duration` 由**同一次调用**算出（`memory.py:2273`），二者却给出相反语义（"满分卡死"/"零秒卡死"）——**这是可复现的假绿/假红源**（下游 `deadlock_burst_ready`、`anomaly.update`、`health_score` 都读这两个量）。
2. **A3「✅ 已解决」需拆成两句**：① **单位标注对齐** = 已解决（可确认）② **"不再 ≡1.0"** = **不成立**（活体 12:54 我独立取到 6 连 1.0）。t2 §4.1-A3 的判据 `活体 stuck_score = 0.08（不再 ≡1.0）` 是**单点**，属**取样偏差**。
3. **B3「构造伪影已消除」→ 必须改写**（不是观察项）。建议文本：
   > **B3（修订，2026-09-26 13:05 复核）**：`stuck_score ≡ 1.0` 的**构造伪影未消除，只是改变了触发相位**：`memory.py:234-235` 的 `disp_60s > 500 ⇒ _stuck_duration -= 1.0` 泄放使 `stuck_duration` 在移动片段被清零，而 `rate` 子信号（`forward_rate == 0` 连续 3 s）仍把 `stuck_score` 拉到 1.0 ⇒ **同刻快照可读作"满分卡死 + 0 秒卡死 + anomaly=idle"**。复现：12:54:31–12:55:01 六连 `stuck_score=1.0 / stuck_duration=0.0`；慢采样峰值 12:54:31 = 1.0、12:56–13:02 峰值 0.70。⇒ **观测层口径缺陷（RC-4 观测点/归因未接线）**，须与 B06 同批处理。
4. **受影响文档确切位置与应改文本**：
   | 文档 | 位置 | 现状 | 应改 |
   |---|---|---|---|
   | `blindspot-analysis-0923-0926.md` | §4.1 表 **L195**（A3 行） | 「✅ 已解决」+ 判据 `stuck_score = 0.08（不再 ≡1.0）` | 改为「**单位标注已对齐；`stuck_score ≡ {0,1}` 未消除**」，判据换为 12:54 六连采样 + 离线复现 |
   | 同上 | **L222**（§4.4-C1） | 「已在窗口内解决」 | 同上拆分表述 |
   | 同上 | **L203**（§4.2-B3 行） | 「缓解：`stuck_score ≡ 1.0` 构造伪影已消除」 | 删除"已消除"，补入 6.3-3 的机制与复现 |
   | 同上 | **L252**（§6.1 实测清单） | 「`memory.py:135` 单位修复」 | 补「`stuck_score` 仍可达 1.0（12:54 六连）/ `stuck_duration` 恒 0」 |
   | 同上 | **L269**（§6.3-U?）/ §6 表 | 未列该矛盾 | 新增一条"**已复现**"条目（不属于"无法验证"） |
   | `session-log-recommendations.md` | **L200**（P1-N1 提示） | 「单点不可当趋势…若持续则撤回」 | 改为「**已复现（6 连 + 离线仿真）**；B3 措辞须撤回并改写为观测层缺陷」 |
   | 同上 | **L810**（A3 行，标 ✅ 关闭） | 「P1 → 关闭（保留记录）」+「⚠️ 12:47 单点」 | 保留关闭（单位口径），但把 ⚠️ 升级为「**B3 需改写**」 |
   | 同上 | **L865**（B3 行） | 「部分缓解 + 新增子项…若持续需撤回」 | 改为「**未缓解：`stuck_score` 可达 1.0（12:54 六连）**」 |
   | `session_logs_execution_plan.md` | P1-N1 横幅（L≈849 附近） | ✅ 闭环 | 加一句"单位口径闭环 / 可观测性未闭环" |

5. **与历史缺陷、RC 分类的关系**：
   - 与历史「StuckDetector 单位」缺陷是**同一变量的两次不同失效**：09-24 那次是**量纲错配**（`5.0 Hz` vs per-tick 比例 ⇒ 比较永真 ⇒ 恒 1.0）；本次是**量纲修好后暴露的语义/泄放缺陷**（`0.008` ⇒ rate 子信号等价于"forward_rate 恰为 0"，被 idle 频繁触发；同时泄放抹掉 duration）——属于 **"修好了单位、没修好可判定性"**。
   - **RC 归属**：**RC-4（观测点/归因字段未接线）** 的新实例，并与 **RC-5（迁移只做一半：只改 `:135` 阈值与注释，未改 docstring `:127` 的 Hz 表述、未加运行时断言）** 叠加。**不构成 RC 分类之外的新子型**。
   - ⚠️ 因此 t2 §3.3「7 类根因、12 例、RC-4 = 1 例（仅 E5）」**需 +1**：若把本项计入，则 **RC-4 = 2 例、总数 13 例**；若按 t2 的写法（本项归入 E5/B3 已存在的观测层家族）则可维持 12 —— **建议 captain 明确口径**（这属"计数定义"问题，正是 RC-7 的家族）。**本报告不擅自改数**。

---

## 7. 必修正条目清单（含归属）

| ID | 级别 | 问题 | 证据 | 应改成 | 归属 |
|:-:|:--:|---|---|---|---|
| **M-1** | **阻塞** | t2 A3「✅ 已解决」+ 判据「活体 `stuck_score = 0.08`（不再 ≡1.0）」**过头**：单位已对齐，但 `stuck_score` 仍可饱和 1.0 且与 `stuck_duration=0.0`/`idle` 同刻矛盾 | §6.1 六连 1.0；§6.2 代码走查 + 离线复现 14/3000 tick | 按 §6.3-2 拆分表述；判据换成 6 连采样 | **t2 返修**（或 t3 append-only 更正 §A.1/§A.3） |
| **M-2** | **阻塞** | B3「`stuck_score ≡ 1.0` 构造伪影已消除」**不成立**；t3 仍写"若持续则需撤回" | §6.1/§6.2/§6.3 | 按 §6.3-3/6.3-4 改 7 处文本 | **t2 + t3** |
| **M-3** | 高 | A4 `control.x` 计数「恶化 10→12（生产 14→16）」**不成立**（朴素正则把 2 处 `==` 计入） | §4.2 B/D/F | 全文统一 **10 / 14 / 含 `fly64/tests` 16、含根 `tests/` 17**，并**必须写明限定** | **t2 返修**（t3 §A.6-C8 已正确，无需改） |
| **M-4** | 中 | 两处路径/引用错误：① `evo_liveness_guard.py` 不在 `fly64/skills/` 而在 **`fly64/scripts/`** ② `.evo_loop.lock` 不在 `/root/fly64/` 而在 **`/root/fly64/skills/`** ③ E8 措辞「`burst_active` 无发布点」与实测（`main.py:2206 model.burst_active = …`）不符，应写「无 **flow.json/memory.json** 发布点」 | §2 V5/V8 命令与输出 | 改路径；改措辞 | **t2（及 t1，同错）** |
| **M-5** | 中 | t3 保留的"运行断言"承诺未实现（P1-N1 标题含"断言"，落地证据只到注释） | §3 第 1 行核验 | 标题/结论改为「单位文档化 ✅ / **运行时断言 ❌ 未实现**」 | **t3 append-only** |
| **O-1** | 建议 | t2 未报告：已交付 `session-log-analysis.md` §困境 4 的 **10 个写点行号已整体漂移 +112~+120** | §4.2-E | 补一条"已交付文档行号过时"的说明（该文件不在 in-scope，由 captain 决定是否回改） | t2 / captain |
| **O-2** | 建议 | 未核验项"根 `tests/` 与 `fly64/tests/` 双根收集"（t2 §6-U4）本轮仍**未执行**（只读核验，我未跑 pytest） | 未执行 | 保留在未验证清单 | — |
| **O-3** | 建议 | 未跟踪计数存在**三套口径**（65 条 `??` 行 / 354 展开文件 / "~62 产物"），报告未声明口径 | §4.5 | 后续统一为"`??` 条目数 / `-uall` 文件数"两列 | 全员 |

---

## 8. 遗漏与推断审计

### 8.1 无据推断（t2 的推断项复核）

| t2 推断 | 复核 | 判定 |
|---|---|:--:|
| I1 闭环死于 11:46:44–11:47:44（缺进程审计） | 我确认 `evolution_log.jsonl` mtime **11:47:29**、`/tmp/fly64_launcher.log` 未复核 ⇒ **t2 自己已标"中高"，无新增反例** | 证据不足（保留） |
| I2 钳位写入方 = 本能绑定 promoted 桶 | 本次采样期 `clamped_keys = []`（无钳位事件）⇒ **本轮无法复现，不构成反例** | 证据不足（保留） |
| I4 `no_progress_gate` vs `progress_ineffective` 同源不同 tick | 我 54 点采样实测：`no_progress_gate` **恒 False**；`progress_ineffective` 在 True/False 间切换（12:58:33/12:58:48/12:59:24/12:59:29/12:59:34/12:59:39/12:59:44 为 False）⇒ **不一致确实存在**，且 `npr=False` 时 `pie` 可为 True **或** False ⇒ t2 的"同刻相反"是**片段现象**而非恒态 | **✔ 现象成立，措辞应收紧为"片段不一致"** |
| I5 `sm64config.txt` 属手工同步 | `runtime/sm64config.txt` mtime **12:27:48**，提交 12:28:02 ⇒ 佐证；未查部署脚本 | 证据不足（保留） |

### 8.2 未被 t1/t2/t3 覆盖的重要事项（本轮新增）

1. **`evo_liveness_guard.py` 与 `evo_loop_launcher.sh` 均在仓库中但 `evo_loop_launcher.sh` 缺少可执行位**：`git ls-files --stage` → `100644`（非 `100755`）⇒ 在 WSL 上依赖 `bash scripts/…` 显式调用；**这本身是"部署/运行契约"缺陷**（与 E1 同族，未被任何报告记录）。
2. **`runtime/evolution_history.json`（7124 B）与 `skills/evolution_history.json`（99101 B）** 是两份不同的"进化历史"文件，t1/t2/t3 **只核对了后者**；前者 mtime 每轮更新（12:56:12/12:56:24），**是运行时会话的独立副本** ⇒ 进一步证实"记录可被运行侧覆盖"的风险面比报告描述的更大。
3. **`FWD_RATIO_FLOOR = 0.008` 定义在 `fly64/fly64/model.py:18`**（不在 `memory.py`），t2 §4.1-A1 称其为"模块级命名常量 1 个"但未给位置 —— 该常量与 `StuckDetector.rate_threshold = 0.008` **数值相同、来源不同**，属"常量抽取未统一"的直接证据（A1 结论加强）。
4. **`test_gate_units.py:167/228/259` 断言的是 `FWD_RATIO_FLOOR` 的文档串与默认值**，不覆盖 `scene_context.py:234` 的消费者 ⇒ t2 对 E7 的"消费者无测试覆盖"判定**成立且可加一条更硬的证据**。

### 8.3 「无证据」声明的防漏（任务点 5）

- `git stash list` → **空**（已补查，无隐藏工作）。
- `git branch -a` / `git worktree list` → **本次未执行**（列为本报告 O-2 的一部分，属"未证实非证伪"）。
- **结论**：t1 抽查的 3 条"无 commit/无记录"声明**全部属实**，未发现把"遗漏"误报为"不存在"的情形。

---

## 9. 整体可信度评级与返修建议

**评级：中高（结构可信、数字需修）**

- **可信部分（独立复现通过）**：窗口定界（12 提交/6-3-2-1）、`fbcc3d7` 删 EVO-072/073 + canonical skill 3.5.1→3.4.2、`check_version.py` 4 行空壳、E1 守护未接调度与告警器停摆、E5 观测点错位、E7 生产者删键/消费者默认值/夹具补键、E9 活体-工作区 md5 分叉、未入库规模、WSL 磁盘/日志/锁、`--numstat` 115/39。
- **需修部分**：**A3/B3 的闭环与"伪影已消除"结论**（阻塞）、**A4 计数与正则口径**（阻塞）、**3 处路径/措辞错误**、**"运行时断言"未实现仍写进闭环标题**、**已交付文档行号漂移未报**。
- **数字纪律评价**：本项目三次历史失真中，**t2 成功避开了 (a) 122× 计数与 (c) `--stat` 当 numstat**（115/39 判定正确、并主动把 137/41 标为未复现）；**但在 (b) 行号漂移上仍有漏报**（已交付文档行号），**并新增一次正则口径事故**（A4 的 `==` 混入）——该事故本身即 **RC-7（分析工具链口径）** 的第 3 个实例。
- **返修路由建议**：M-1/M-2 → **t2 修订 + t3 append-only**；M-3/M-4 → **t2**（修订其 §4.1/§6.1 与 §3.2 措辞）；M-5 → **t3**。**若 captain 只允许 append-only**，则至少必须在 `session-log-recommendations.md` 与 `session_logs_execution_plan.md` 的落地区加**勘误块**，把上述 5 条与 §6.3-4 的 6 处文本一次性写清（本报告可直接摘用）。

---

## 附录 A：核验者全部复现命令（逐条可跑）

```bash
# --- 窗口与提交 ---
git log --since="2026-09-23 00:00" --until="2026-09-27 00:00" --pretty=format:"%h %ad %s" --date=format:"%Y-%m-%d %H:%M:%S"

# --- E3 记录删除 + 版本回退（双向） ---
git log --oneline -S'"EVO-072"' -- fly64/skills/evolution_history.json
git log --oneline -S'"EVO-073"' -- fly64/skills/evolution_history.json
git show fbcc3d7 --numstat -- fly64/skills/evolution_history.json      # → 115 39
python -c "import subprocess,json;d=json.loads(subprocess.run(['git','show','HEAD~1:fly64/skills/evolution_history.json'],capture_output=True).stdout);print(len(d['records']),d['canonical_versions'])"

# --- A4 control.x（两种正则，结果不同） ---
python -c "import re,io;t=io.open('fly64/fly64/main.py',encoding='utf-8').read();print('naive',len(re.findall(r'control\.x\s*=',t)));print('assign',len(re.findall(r'control\.x\s*=(?!=)',t)))"
# → naive 12 / assign 10 ；12 多出的两处 = main.py:2618 `control.x == 0`、:2959 `"control_x_zero": control.x == 0`

# --- A3/B3 StuckDetector（离线安全，只读） ---
# 见 §6.2 代码块；核心：disp_60s>500 时 `_stuck_duration` 每次 −1.0，而 `rate` 子信号 3 s 到顶 ⇒ score=1.0 & duration=0.0

# --- 活体遥测（HTTP） ---
python -c "import json,urllib.request as u;f=json.load(u.urlopen('http://127.0.0.1:8765/flow.json'));m=json.load(u.urlopen('http://127.0.0.1:8765/memory.json'));print(len(f),len(m),'clamped_keys_in_flow',('clamped_keys' in f),'in_memory',('clamped_keys' in m));print('ss',m['stuck_score'],'sd',m['stuck_duration'],'fr',f['forward_rate'],f['forward_rate_hz'])"

# --- WSL 侧（E1/E9/路径） ---
wsl -e bash -c 'cd /root/fly64 && crontab -l; ls -l --time-style=+%Y-%m-%d_%H:%M:%S skills/evo_stall_alarm.json skills/evolution_log.jsonl scripts/evo_liveness_guard.py; cat skills/.evo_loop.lock; md5sum fly64/memory.py fly64/main.py skills/evolution_skill.py skills/evolution_history.json'
wsl -e bash -c 'cd /root/fly64 && bash scripts/evo_loop_launcher.sh --status'

# --- 未入库规模（口径三连） ---
git diff --shortstat -- . ':(exclude)fly64/.pytest-run' ':(exclude).tmp-pytest'   # 37 files, 4995(+), 481(-)
git status --porcelain | grep -c '^??'                                            # 65
git status --porcelain -uall | grep -c '^??'                                      # 354
```

## 附录 B：本次核验未做/不能做的（明确边界）

| # | 未做项 | 原因 |
|:-:|---|---|
| U1 | 未跑 pytest / `--collect-only`（双测试根、规则 20 基线） | 只读核验，不改变工作区状态 |
| U2 | 未执行 `scripts/_captain_verify_t3.sh` | 同上 |
| U3 | 未复核 t2 的 `evolution_skill.py` 5357 vs 4911 行差异 | t2 引用 WSL 侧 wc，未复跑 |
| U4 | 未统计 `relocalize()` 活体命中率 | 需人工定义"命中"判据 |
| U5 | 未复核 `.deploy_backup/` 四个快照时间 | t1 单方证据，未交叉 |
| U6 | 未做 `git branch -a` / `git worktree list` | 时间预算；`git stash list` 已查（空） |
| U7 | `frequencies/百分比` 类派生量（如 60.3%、1.47%） | 属 `analysis-t3/t5` 议题，不在 t4 范围 |
