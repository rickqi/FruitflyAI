# 盲区证据清单：2026-09-23 09:58 → 2026-09-26（export logs 未覆盖窗口）

> **采集者**: evidence-engineer（AgentTeams `fly64-blindspot-0923-0926` / task `t1`）
> **采集时刻**: 2026-09-26 12:29 → 12:40 (+0800)，`Get-Date` = `2026-09-26 12:29:21 +08:00`
> **工作区**: `D:\codes\flygym`（Windows）；运行侧 WSL2 `/root/fly64`（独立副本，非 git 仓库）
> **基线 HEAD**: `fbcc3d7`（2026-09-26 12:28:02 +0800）
> **状态约定**: 每条证据标注 `[实测]`（有命令+原始输出）或 `[推断]`（由实测推导，给出推断链与置信度）。
> **快照约定**: 第 7 节的活体遥测是**单点快照**，不得当作趋势。

---

## 0. 窗口边界与"窗口"的精确定义

`git log --since=2026-09-23` 会多带回 8 个 **09:58 之前**的提交（属于已交付的 export logs 分析覆盖段）。本报告据此显式划界：

```bash
git log --since=2026-09-23T00:00 --until=2026-09-23T23:59 --pretty=format:'%h|%ad|%s' --date=iso
# 68ca39c|2026-09-23 00:43:02|fix(P0-3b): 提交在途交付物修复 HEAD 不可导入缺陷 + 收口 EVO-072 基线
# 6d0aa42|2026-09-23 08:36:08|fix(P0): 版本五处统一 + 死参数复活 + 触发闸门矛盾修复 + 回归基线转绿
# dd1f36f|2026-09-23 08:36:22|test(P0-5): Coach 链路级端到端断言（发布门禁）+ 证据记录
# d86fc9d|2026-09-23 09:17:31|fix(HOTFIX): 修复 master 上诊断目录为空的生产故障（UTF-8 BOM + 回退语义）
# 29817be|2026-09-23 09:44:36|fix(t8): FixTemplateInterpreter 契约统一（11 条 real-bug 清零）+ 基线重刷 49→36
# 250d51b|2026-09-23 09:44:51|fix(t9): 修复探针缺陷（残留不再伪装成回归）+ 消除嵌套全量跑
# 5790102|2026-09-23 09:45:06|test: PatternCatalog 加载健康回归守卫（锁定 BOM/回退修复）
# 1aeb0f8|2026-09-23 09:50:02|docs: 根 README 全面重写 + 版本/统计对齐 P0 结果
```

**结论 `[实测]`**：上述 8 条的提交时间全部 < 09:58，**不属于本窗口**；本窗口 **首个提交是 `78b3175`（09-23 12:42:27）**。
窗口内提交总数 = **12**；`--since=2026-09-23` 共 20 条，差额 8 条即上表。

---

## 1. 时间线：本窗口内 git 提交（12 条，全部实测）

**可复现命令**：`git log --since=2026-09-23 --until=2026-09-27 --stat --date=iso`

| # | 时间 (+0800) | hash | 主题（截断） | 改动 | 类型 |
|---|---|---|---|---|---|
| 1 | 09-23 12:42:27 | `78b3175` | switch coach LLM: GLM-5.3-flash → 本地 vLLM `http://10.141.157.192:8000/v1` qwen3.8-27b-uncensored | monitor 显示实调模型 | 配置/仪表板 |
| 2 | 09-23 12:52:03 | `506e87a` | dashboard layout fix: 全局 `.evo-cap` 收容（最多溢出 386px） | 2 文件 | UI |
| 3 | 09-23 12:58:12 | `5dba6fe` | dashboard adaptive layout: 固定行高 → auto，escape 表 110→400px | 2 文件 | UI |
| 4 | 09-23 20:51:22 | `2f87d77` | **feat: motor-pool recovery (t1–t9) + gate Hz 单位契约 + 版本 2.24.0/3.5.1** | `known_failures.win32.json +10`、`test_gate_units.py +404`、`test_motor_pool_dynamics.py +767`（共 1181 增） | 机制/版本 |
| 5 | 09-23 22:50:44 | `4ba5f11` | docs: P0-4 实机验证报告 + Coach 建议被钳位根因定位 | 文档 | 证据 |
| 6 | 09-23 23:59:07 | `f486ad0` | **feat(P1): 让 Coach 建议真正生效** — 钳位可见性 + 契约对齐 + 死键根治 + 测试隔离 | `fix_template_interpreter.py` 系列 | 机制 |
| 7 | 09-24 12:35:31 | `cca6664` | fix(P1): `is_manual` 启发式修复 + `_call_llm_subagent` 真实现 + 测试 | 274 增/33 删 | 修复 |
| 8 | 09-24 18:25:20 | `6655288` | fix auto/wide layout misalignment（根因：events 面板长到 1008px > 505px 行） | 26 增/3 删 | UI |
| 9 | 09-24 21:28:16 | `ab2761c` | docs: 复核 fly64 自治进化方案 — 新增 F13–F15/V22/R13 | `fly64-autonomy-evolution-plan.md +1122` | 文档 |
| 10 | 09-25 20:30:25 | `833848c` | docs(analysis): **对话日志分析 v5 + 执行方案** | 5 文件 721 增 | 文档 |
| 11 | 09-25 21:18:45 | `38c8bae` | **feat(P0): 信用分配矩阵 + EVO 闭环存活与停摆告警** | `fly64/scripts/evo_liveness_guard.py +407`、`fly64/scripts/evo_loop_launcher.sh +211`、2 报告 | 机制/运维 |
| 12 | 09-26 12:28:02 | `fbcc3d7` | **fix(WSLg): D3D12 GPU 直通渲染极慢 → vsync off + MESA swrast** | `README.md +22`、`sm64config.txt`、`evolution_history.json +154/-41`（`--stat` 图形总数；**`--numstat` 实测 115/39**，见 §11-勘误） | 运维/渲染 |

**本窗口的提交节律（实测）**：09-23 6 条 / 09-24 3 条 / 09-25 2 条 / 09-26 1 条。见 §8 的空窗清单。

### 1.1 跨环境同步与部署相关提交（任务要求标注）

只有 3 条与"同步/部署"直接相关，且**都不是自动化部署提交**：

- `78b3175`（09-23 12:42）：提交信息自述 `llm.env (gitignored, root-only) updated on deploy host` —— **部署动作本身未入库**，只在提交信息里留痕 `[实测]`。
- `38c8bae`（09-25 21:18）：提交信息记录 `WSL 重启常驻（tmux fly64-evo + setsid nohup，PID 11997）`、`captain 在 WSL 独立复核` —— 部署是手工的 `[实测]`。
- `fbcc3d7`（09-26 12:28）：提交信息记录 `WSL runtime config 同步更新`。
  **实测** Windows 与 WSL 的 `fly64/fly64/main.py` md5 一致（`a79fe51de2c7f4579be1fbe6e6c6efdf`），WSL 侧 `runtime/sm64config.txt` mtime = `2026-09-26 12:27`。

**`[实测]` WSL 侧的部署记录**（`ls -ld /root/fly64/.deploy_backup/*`）——**全部集中在 09-25，09-26 无部署**：

```
drwxr-xr-x 5 root root 4096 Sep 25 18:55 /root/fly64/.deploy_backup/20260925_185521
drwxr-xr-x 5 root root 4096 Sep 25 18:58 /root/fly64/.deploy_backup/20260925_185827
drwxr-xr-x 5 root root 4096 Sep 25 20:25 /root/fly64/.deploy_backup/20260925_202528
drwxr-xr-x 5 root root 4096 Sep 25 21:05 /root/fly64/.deploy_backup/20260925_210526   ← .deploy_backup/LATEST
```

> **`[推断]`（高置信）**：09-26 的 `fbcc3d7`（vsync/swrast 修复）只改了 `config/sm64config.txt` + `README.md` + `evolution_history.json`，**未走 `.deploy_backup` 流程**；WSL 侧 `runtime/sm64config.txt` 的 mtime 12:27 说明是**手工同步**，不是部署脚本产物。

### 1.2 证据索引总表（时间 / 来源 / 命令 / 原始输出片段 / 可复现性）

每条证据一行；`原文位置` 指向本报告中承载原始输出的章节。

| 时间 (+0800) | 来源 | 命令 | 原始输出片段（截断） | 可复现性 | 实测/推断 |
|---|---|---|---|---|---|
| 09-23 12:42:27 | git | `git log --since=2026-09-23 --until=2026-09-27 --stat --date=iso` | `78b3175\|…\|switch coach LLM: GLM-5.3-flash → 本地 vLLM…` | 高（HEAD 不变即一致） | 实测 |
| 09-23 17:01–18:56 | fs | `Get-ChildItem docs/analysis \| Sort LastWriteTime` | `motor-pool-saturation-findings.md 65465 2026/9/23 18:56:57` | 高（mtime 随 checkout 变，内容级可查 git） | 实测 |
| 09-23 20:42:16 | fs | `Get-ChildItem fly64/.pytest-run -Recurse \| Sort LastWriteTime -Desc` | `test_map_persistence_roundtrip0/map.pkl 2026/9/23 20:42:16` | 中（需保留该目录） | 实测 |
| 09-23 20:51:22 | git | `git show 2f87d77 --numstat -- fly64/tests/known_failures.win32.json` | `10  0  fly64/tests/known_failures.win32.json` | 高 | 实测 |
| 09-23 21:01–23:32 | fs | mtime 扫描 | `current_state_analysis_v3.md 21:01:22` … `analysis-p0-4-live-verification.md 23:32:01` | 高 | 实测 |
| 09-23 23:23:05–23:50:28 | fs | `Get-ChildItem fly64/runtime/coach_frames -File` | 09-23 共 75 帧，first 23:23:05 / last 23:50:28 | 中 | 实测 |
| 09-23 23:59:07 | git | `git log --stat` | `feat(P1): 让 Coach 建议真正生效 … 274 +/33 -` | 高 | 实测 |
| 09-24 11:34:25 | fs | coach_frames 遍历 | 09-23 23:50:28 → 09-24 11:34:25 空档 **11.73h** | 中 | 实测 |
| 09-24 12:35–13:39 | fs（未跟踪） | `git status --porcelain` → `??` | `?? docs/analysis/analysis-t2-evolution-pipeline-failure.md 09-24 12:39` … `t7 13:39` | 高 | 实测 |
| 09-24 16:38–17:04 | fs（未跟踪） | 同上 | `?? docs/analysis/session-log-summary.json 150233 09-24 16:38:55` 等 5 件 | 高 | 实测 |
| 09-24 18:04–23:17 | fs（未跟踪） | `Get-ChildItem docs/execution -Recurse` | `fly64-execution-plan.md 126085 09-24 18:04:14` … `sp4-completion-report.md 09-24 23:17:32` | 高 | 实测 |
| 09-24 19:30:21/47 | fs（`M`） | `git status --porcelain` | `M fly64/skills/brain_tunable_params.json`、`M fly64/skills/active_strategy.json` | 中（工作树状态易变） | 实测 |
| 09-24 21:28:16 | git | `git show ab2761c --stat` | `fly64-autonomy-evolution-plan.md \| 1122 ++++` | 高 | 实测 |
| **09-25 18:55–21:05** | **WSL 部署** | `ls -ld /root/fly64/.deploy_backup/*` | `20260925_185521 / 185827 / 202528 / 210526 ← LATEST` | 中（备份目录可被清理） | 实测 |
| 09-25 15:28:00 | fs | coach_frames 遍历 | 教练帧**整体止于此**，其后 21.2h 零新帧 | 中 | 实测 |
| 09-25 18:40:19 | fs（未跟踪） | 读文件 | `w1-w4-closeout-and-h13-verdict.md`：「**H13…在真实运行数据下不成立**」「P2/P3 整体阻塞…SP5-B 与 SP6 不可开工」 | 高（文件在库） | 实测 |
| 09-25 19:01:09 | fs（未跟踪） | 读文件 | `deploy-manifest.md`：「**活体未部署修复**（deployed model.py md5 = HEAD = 修复前）」 | 高 | 实测 |
| 09-25 20:30:25 | git | `git show 833848c --stat` | `session_logs_analysis_v5.md +244` 等 5 文件 721 增 | 高 | 实测 |
| 09-25 21:01:25/53 | WSL | `stat -c '%y %n' …` | `evo_stall_alarm.json 2026-09-25 21:01:25`、`.evo_loop.lock 21:01:53`（内容 `11997`）——两文件均在 **`/root/fly64/skills/`** 下（t5 补注） | 中 | 实测 |
| 09-25 21:01:56 | WSL | `tail -c 900 /tmp/evo_loop_launcher.log` | `进化闭环已启动 (PID: 11997, 日志: /tmp/evo_loop.log)` | 中（/tmp 可被清） | 实测 |
| 09-25 21:08:59 / 21:15:55 | fs | `Get-ChildItem fly64/.pytest_cache -Recurse` | `v/cache/lastfailed 9288 …`、`v/cache/nodeids 176346 …` | 中 | 实测 |
| 09-25 21:18:45 | git | `git show 38c8bae --stat` | `evo_liveness_guard.py +407`、`evo_loop_launcher.sh +211`、`_captain_verify_t3.sh +44` | 高 | 实测 |
| **09-26 11:47:29** | WSL | `cat /root/fly64/skills/.evo_loop_heartbeat.json` | `{"ts":1790394449.67,"pid":null,"state":{"iteration":9859,…}}` | 中（滚动覆盖） | 实测 |
| 09-26 11:47:44 / 12:03:29 / 12:05:29 | WSL | `cat /tmp/fly64_launcher.log` | `[11:47:44] 创建 tmux 会话 fly64…`、`[12:03:29] 脑模型已启动 (PID: 7037)`、`[12:05:29] 停止 Fly64 进程…` | 中 | 实测 |
| 09-26 12:05:35 / 12:05:40 | WSL | `ps -eo pid,lstart,etime,cmd` | `7401 Sat Sep 26 12:05:35 … python3 -m fly64.main …`、`7418 … sm64.us.f3dex2e …` | 中（进程会变） | 实测 |
| 09-26 12:27 / 12:28 | WSL/fs | `ls -la /root/fly64/runtime/`、`ls -la /root/fly64/skills/` | `sm64config.txt 800 Sep 26 12:27`、`active_strategy.json 1761 Sep 26 12:28` | 中 | 实测 |
| 09-26 12:28:02 | git | `git show fbcc3d7 --stat` | `evolution_history.json \| 154 ++++---`、`README.md +22`、`sm64config.txt` | 高 | 实测 |
| 09-26 12:28 / 12:34 | WSL | `cat /root/fly64/runtime/evolution_history.json` | `{"brain_version":"2.24.0","iterations":[{"iter":16502,"time":"09-26 12:18:24",…` … `16521 12:28:08` | 中（滚动缓冲仅 ~19 条） | 实测 |
| 09-26 12:30:47 | WSL | `ps -ef \| head -30` | 仅 `/init`、`/init`、`fly64.main`、`sm64`、`ps/head` —— **无 evolution_skill** | 中 | 实测 |
| 09-26 ~12:31 | WSL | `bash scripts/evo_loop_launcher.sh --status` | `• tmux 会话 [fly64-evo]: ○ 未运行` / `• 进化闭环: ○ 未运行` / `• evolution_log.jsonl: 58594 行, 最后写入 2644s 前` | **高（项目自带工具）** | 实测 |
| 09-26 ~12:31 | WSL | `crontab -l` | 仅 `watchdog.sh`、`phase2_gate.sh` 两条 —— 无 guard/launcher | 高 | 实测 |
| 09-26 12:29 / 12:35 | 活体 HTTP | `curl -s http://127.0.0.1:8765/bridge-status.json` | `{"seq":35430,…,"age_ms":16.59,"render_ms":6.118}` | **低（快照，非趋势）** | 实测快照 |
| 09-26 12:30 / 12:35 | 活体 HTTP | `curl -s http://127.0.0.1:8765/flow.json` | `"clamped_keys":[{"key":"exploration.turn_bias","requested":0.7,"applied":0.25,"source":"unknown",…}]`、`"clamped_keys_age_s":35.1` | 低（快照） | 实测快照 |
| 09-26 12:30 / 12:35 | 活体 HTTP | `curl -s http://127.0.0.1:8765/memory.json` | 61 键；`"clamped_keys" in memory.json → False` | 低（快照） | 实测快照 |
| 09-26 12:33:18 | WSL | `cat /tmp/fly64.log`（26 行） | `[fly64] strategy clamp: exploration.turn_bias requested=0.7 -> applied=0.25 (source=unknown, advice_age=Nones) …` | 中 | 实测 |

---

## 2. 时间线：非 git 证据（文件系统 mtime / 运行时工件）

### 2.1 窗口内 `docs/analysis/**` 产出（25 个文件，`[实测]`）

```bash
python -c "import os,datetime; ... walk('docs/analysis') ... mtime >= 2026-09-23 09:58"
```

| 时间 | 大小 | 文件 |
|---|---|---|
| 09-23 17:01:25 | 35350 | `motor-pool-verification-report.md` |
| 09-23 17:23:55 | 33212 | `motor-pool-review-t2.md` |
| 09-23 17:29:29 | 27831 | `motor-pool-review-t3.md` |
| 09-23 18:18:46 | 19151 | `motor-pool-review-t8.md` |
| 09-23 18:56:57 | 65465 | `motor-pool-saturation-findings.md` |
| 09-23 21:01:22 | 7875 | `current_state_analysis_v3.md` |
| 09-23 21:02:41 | 4775 | `execution_plan_v3.md` |
| 09-23 23:32:01 | 11004 | `analysis-p0-4-live-verification.md` |
| 09-24 11:57:20 | 35299 | `fly64-trajectory-behavior-report.md` |
| 09-24 12:39:14 | 45513 | `analysis-t2-evolution-pipeline-failure.md` |
| 09-24 12:59:06 | 41510 | `analysis-a4-autonomy-surface-inventory.md` |
| 09-24 13:03:52 | 52942 | `analysis-t3-primary-factor-determination.md` |
| 09-24 13:21:17 | 33104 | `analysis-t5-adversarial-verification.md` |
| 09-24 13:39:29 | 27882 | `analysis-t7-reverification.md` |
| 09-24 16:38:55 | 150233 | `session-log-summary.json` |
| 09-24 16:49:33 | 17095 | `session-log-analysis-review.md` |
| 09-24 16:57:36 | 27939 | `session-log-analysis.md` |
| 09-24 16:57:54 | 29436 | `session-log-recommendations.md` |
| 09-24 17:01:36 | 36768 | `session_logs_execution_plan.md`（**该文件在 git 中为 `M` 未提交**） |
| 09-24 17:02:02 | 158273 | `fly64-autonomy-evolution-plan.md` |
| 09-24 17:04:07 | 11882 | `session-log-analysis-review-round2.md` |
| 09-25 20:29:57 | 13408 | `session_logs_analysis_v5.md` |
| 09-25 20:30:13 | 7141 | `session_logs_execution_plan_v5.md` |
| 09-25 20:57:48 | 25933 | `analysis-credit-assignment-matrix.md` |
| 09-25 21:03:21 | 10783 | `analysis-evo-loop-liveness.md` |

> **入库状态 `[实测]`**：上表中 **只有 4 个**文件进了 git（`fly64-autonomy-evolution-plan.md`→`ab2761c`；`session_logs_analysis_v5.md` / `session_logs_execution_plan_v5.md`→`833848c`；`analysis-credit-assignment-matrix.md` / `analysis-evo-loop-liveness.md`→`38c8bae`；`session_logs_execution_plan.md` 仍是未提交 `M`）。**其余 19 个是未跟踪文件**（含 motor-pool 5 份、t2/t3/t5/t7/a4 五份、session-log 全套 5 份）。

### 2.2 另一条**完全未入库**的产出线：`docs/execution/**`（任务书未点名的重大证据）

```bash
Get-ChildItem docs/execution -Recurse -File | Sort-Object LastWriteTime
```

| 时间 | 大小 | 文件 |
|---|---|---|
| 09-24 18:04:14 | 126085 | `fly64-execution-plan.md` |
| 09-24 18:30:04 | 14096 | `sp1-completion-report.md` |
| 09-24 19:38:54 | 11153 | `sp2-completion-report.md` |
| 09-24 22:02:06 | 14924 | `sp3-completion-report.md` |
| 09-24 23:17:32 | 17941 | `sp4-completion-report.md` |
| 09-25 11:17:04 | 165958 | `fly64-change-specs.md` |
| 09-25 12:04:59 | 54884 | `sp5a-closure-and-aa-wiring-report.md` |
| 09-25 15:24:27 | 57679 | `sp5a-completion-report.md` |
| 09-25 16:20:27 | 44555 | `g4-noise-diagnosis-and-decision.md` |
| 09-25 18:40:19 | 9181 | `w1-w4-closeout-and-h13-verdict.md` |
| 09-25 19:01:09 | 13525 | `deploy-manifest.md` |

`git status --porcelain` 显示 `?? docs/execution/` —— **整目录未跟踪 `[实测]`**。

**`[实测]` 该目录承载了窗口内最重要的两个判断**：

1. `deploy-manifest.md`（09-25 19:01）第 1 节自述"这不是新问题"，并**逐条列举项目文档中已记录的同族缺陷**：
   > `motor-pool-review-t2.md`：「**活体未部署修复**（deployed `model.py` md5 = HEAD = 修复前）本报告所有 post 读数均为**工作区代码的离线实测**」
   > `motor-pool-review-t3.md`：「**活体未部署**：deployed `main.py` 仍是修复前版本」
   > `motor-pool-review-t8.md`：「**活体未部署**（deployed `model.py` 仍是修复前）」
   第 5 节记录 `active_strategy.json` 的 `gate_jump_threshold` 语义断裂（工作区 0.75 ratio vs WSL 旧值 3.082 → "门几乎不开，jump 仍恒 0"）。
2. `w1-w4-closeout-and-h13-verdict.md`（09-25 18:40）对 H13 作出**否定裁定**：
   > 「**H13（噪声基底 ≤ 0.03 适应度分辨率）在真实运行数据下不成立。**」
   > 「按方案 §11 R6 / M4-d2：**P2/P3 整体阻塞，SP5-B 与 SP6 不可开工；闭环保持永久 shadow。**」
   > §4.2 自承前一轮报告 W4 用了**合成数据**，两个数字均不成立（"与它用于结论的 0.0302 相差约 7 倍，构成报告内部矛盾"）。
   > §5 未完项：**F1 未修**（`_h13_assessment` 缺 `pool_floor(1/√n)` 双重条件）；§7 证据边界：`memory.json` 与 `.cache/malecns/manifest.json` 不存在（**H5/H6/H11 未关闭**）。

### 2.3 WSL 运行时工件时间戳（`[实测]`）

```bash
wsl -e bash -c "ls -la /root/fly64/skills/ /root/fly64/runtime/"
```

| 文件（WSL `/root/fly64/...`） | mtime | 大小 | 备注 |
|---|---|---|---|
| `runtime/evolution_history.json` | **09-26 12:34** | 7134 | brain 侧滚动迭代记录（仅保留最近 ~19 条）。⚠️ **t5 补录**：与 `skills/evolution_history.json` 是**两份不同文件**（后者 99101 B 为 canonical 契约）；本文件**每轮被重写**（13:04 实测 7110 B），消费方 `fly64/fly64/main.py:61`（读）/`:220`/`:2360`（写）。**本报告 §4.3 的"记录纪律"结论只核对了 `skills/` 那一份**，`runtime/` 那份的易失性此前未被分析 |
| `runtime/sm64config.txt` | 09-26 12:27 | 800 | 窗口末手工同步 |
| `skills/active_strategy.json` | **09-26 12:28** | 1761 | 每轮被重写（自愈） |
| `skills/evolution_history.json` | 09-26 12:28 | 99101 | 与 Windows 侧 **md5 完全一致**（`d98c46f9…`） |
| `skills/evolution_log.jsonl` | **09-26 11:47** | 200186422 | 58594 行 |
| `skills/evolution_health_trend.jsonl` | **09-26 11:47** | 12146668 | — |
| `skills/.evo_loop_heartbeat.json` | **09-26 11:47:29** | 94 | `{"ts":1790394449.67,"pid":null,"state":{"iteration":9859,...}}` |
| `skills/.evo_loop.lock`（绝对路径 `/root/fly64/skills/.evo_loop.lock`） | 09-25 21:01:53 | 5 | 内容 `11997`（**PID 已不存在**） |
| `skills/evo_stall_alarm.json` | **09-25 21:01:25** | 348 | `{"stale": false, ..., "reason": "正常"}` |
| `skills/verify_state.json` | 09-25 21:15:00 | 185 | — |
| `skills/default_patterns.json` | 09-25 21:03:18 | 26948 | — |
| `skills/coach_outcomes.jsonl` | 09-24 11:35 | 1067681 | 教练结果流**停止于 09-24 11:35** |
| `skills/coach_advice.json` | 09-24 12:04 | 108155 | 同上 |
| `skills/evo_loop.log` | **09-17 18:35** | 1954764 | 旧循环日志，9 天未写 |
| `skills/fix_catalog.json` | **09-17 01:45** | 21310 | **与 Windows 侧不同**（Win: 09-21 10:14, 21679B, `M`） |

**时间戳换算校验 `[实测]`**：`1790394449.674` → `2026-09-26 11:47:29 +0800`（快照脚本实测一致）。

> **注意（跨环境漂移 `[实测]`）**：`fix_catalog.json` 在 Windows 工作树是 09-21 10:14 / 21679 B 且为未提交 `M`，而 WSL 运行侧仍是 09-17 01:45 / 21310 B —— 两侧**不是同一份**。

---

## 3. 运行时证据：**EVO 闭环在窗口末停摆（重复缺陷模式再现）**

### 3.1 实测：闭环进程不存在

```bash
wsl -e bash -c "ps -ef | head -30"
# root  7358  1  0 12:05 ?  /init
# root  7401  7358 99 12:05 ?  python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0
# root  7418  7358 25 12:05 ?  ./build/us_pc/sm64.us.f3dex2e --skip-intro --configfile /root/fly64/runtime/sm64config.txt
# ← 没有 evolution_skill.py 进程
```

```bash
wsl -e bash -c "pgrep -af evolution_skill"     # 只匹配到执行该命令的 bash 自身
wsl -e bash -c "tmux ls"                       # no server running on /tmp/tmux-0/default
```

```bash
wsl -e bash -c "cd /root/fly64 && bash scripts/evo_loop_launcher.sh --status"
# ==========================================
#  Fly64 EVO Loop Launcher — Status
# ==========================================
# • tmux 会话 [fly64-evo]: ○ 未运行
# • 进化闭环: ○ 未运行
# • evolution_log.jsonl: 58594 行, 最后写入 2644s 前
```

**结论 `[实测]`**：`/root/fly64` 上只有 brain（PID 7401，12:05:35 启动）+ SM64（PID 7418）。**EVO 常驻闭环进程不存在**；**`/root/fly64/skills/.evo_loop.lock`**（t5 补注：在 `skills/` 下，非 `/root/fly64/` 根）记录的 PID 11997 是**陈旧锁**；心跳/日志最后写入 11:47，距快照 **≥ 45 分钟**。

### 3.2 实测：09-25 交付的"守护 + 停摆告警"没有生效

```bash
wsl -e bash -c "crontab -l"
# * * * * * /root/fly64/plugin/watchdog.sh >> /root/fly64/plugin/watchdog.log 2>&1
# * * * * * /root/fly64/scripts/phase2_gate.sh >> /root/fly64/plugin/phase2_gate.log 2>&1
```

- **crontab 中没有 `fly64/scripts/evo_liveness_guard.py`，也没有 `fly64/scripts/evo_loop_launcher.sh`** `[实测]`（t5 补注：二者**均位于 `fly64/scripts/`**；`fly64/skills/evo_liveness_guard.py` 实测不存在）。
- `watchdog.sh`（实测源码）只守护 `plugin/service.py`（`SERVICE_ARGS="--interval 10"`），**不管 EVO 闭环**。
- `evo_stall_alarm.json` 最后一次检查 = **09-25 21:01:25**（快照前 ~13.5 小时），报 `reason: "正常"` —— 告警器最后一次输出之后就没再运行过 `[实测]`。
- 09-25 `38c8bae` 承诺的 `kill→告警 red→green` 复核是**手工一次性验证**；**没有任何自动拉起（cron/systemd/timer）承接它** `[实测 + 推断(高)]`。

**→ 这是"闭环停摆 7 天"（v5 分析六失效点之一）在窗口内**原样复现**：09-25 21:18 刚宣布"重启并守护"，09-26 11:47 闭环再次死亡，**告警没响**（因为告警器本身不在运行）。**同族形态 = "机制存在、报告成功、无法生效"**。**

### 3.3 `[推断]`（中高置信）：闭环死亡时点与一次非脚本化的重启同刻

`/tmp/fly64_launcher.log` 原文（实测）：

```
[11:47:44] 创建 tmux 会话 fly64...
[11:47:47] 脑模型已启动 (PID: 2505, 日志: /tmp/fly64.log)
[11:47:52] Fly64 启动完成
[12:03:29] 脑模型已启动 (PID: 7037, ...)      ← 12 分钟后又启了一次
[12:05:29] 停止 Fly64 进程...
[12:05:34] 全部停止完成
```

而闭环的最后心跳 `11:47:29`、最后一行闭环日志 `11:46:44`。`ps` 显示当前 brain 是 **12:05:35** 启动、**PPID 7358（/init）**，与 `wsl_launcher.sh` 的 tmux 路径不同。

> **推断链**：闭环死于 11:46:44–11:47:44 之间，紧接着 11:47:44 出现一次完整 restart，且此后 12:03/12:05 又发生 start/stop/start。`wsl_launcher.sh` 的 `cmd_launch()`/`cmd_stop()`（实测源码）只处理自己的 tmux 会话 `fly64` 与 SM64/brain PID，**既不启动也不守护 `fly64-evo` 会话**。因此：重启走了**不含 EVO 闭环的路径**，闭环没有被一并拉起。**置信度：中高**（缺少 11:47 那一刻的进程审计日志，无法给出直接因果）。

### 3.4 `[实测]` 窗口内的 P0-4/钳位红线仍在触发，且**归因字段失效**

```bash
wsl -e bash -c "cat /tmp/fly64.log"      # mtime 2026-09-26 12:33:18，26 行
# [fly64] strategy clamp: exploration.turn_bias requested=0.7 -> applied=0.25 (source=unknown, advice_age=Nones) — the coach/panel value was overridden by the safety clamp; see /memory.json clamped_keys
# [fly64] strategy clamp: exploration.turn_bias requested=0.9 -> applied=0.25 (source=unknown, advice_age=Nones) ...
# （共 26 行，全部是同一类告警）
```

活体端点上取到的实际记录（12:35 快照）：

```bash
python -c "urllib.request.urlopen('http://127.0.0.1:8765/flow.json')"
# "clamped_keys": [
#   {"key":"exploration.turn_bias","requested":0.7,"applied":0.25,"source":"unknown","advice_age_s":null,"tick":19200,"wall_time":1790397132.31},
#   {"key":"exploration.turn_bias","requested":0.7,"applied":0.25,"source":"unknown","advice_age_s":null,"tick":19800,"wall_time":1790397198.42}]
# "clamped_keys_age_s": 35.1
```

三个**实测**问题：

1. **P1-1 的核心能力（区分 `source="coach"` vs `"evo_or_panel"`）在实机上是 `source="unknown"`** —— 归因通路没有真正生效。
2. **`requested=0.7 / 0.9` 仍在持续到达** —— 09-23 23:59 `f486ad0` 的 P1-2"契约对齐（只接受 0–0.25，prompt 写明填 0.8 会被钳到 0.25）"**没有拦住写入方**。
3. **日志/文档把观测点指向了错误端点**：`main.py:1316` 的 WARNING 文本与 `build_coach_applied` docstring 都说 `see /memory.json clamped_keys`，但 `clamped_keys` 实际发布在 **`/flow.json`**；实测 `"clamped_keys" in memory.json → False`（memory.json 仅 61 键），`in flow.json → True`（122 键）。**这是 P1-1 自身引入的"观测点错位"**。

**`[实测]` 写入方定位**：`coach_applied` 报 `{"instinct_scene":"致命熔岩地","instinct_applied":true, "turn_bias":0.25, ...}`，而 WSL `skills/scene_strategy_bindings.json` 中该场景**已晋级(promoted=True)** 的绑定签名含 `exploration.turn_bias=0.7`（另有 `mirror|turn_bias=0.9`、`directional_climb|turn_bias=0.9` 等多条 promoted 桶）。
**→ 请求值 0.7/0.9 来自本能绑定注入，被 `(0, 0.25)` 安全钳位压回 0.25；钳位路径不认识这个写入方，于是记成 `unknown`。** 这正是 v5/信用分配矩阵指出的根因"**自适应信号到不了决定行为的变量**"的**活体复现**。

---

## 4. 版本与历史记录一致性（窗口末提交引入的**回归**）

### 4.1 `[实测]` canonical skill 版本被回退，且与代码不一致

```bash
grep -n 'BRAIN_VERSION = \|SKILL_VERSION = ' fly64/fly64/main.py
# 49: BRAIN_VERSION = "2.24.0"
# 50: SKILL_VERSION = "3.5.1"
```

```bash
python -c "json.load(open('fly64/skills/evolution_history.json'))['canonical_versions']"
# {'brain': '2.24.0', 'skill': '3.4.2', 'as_of': '2026-09-24T18:00:00+08:00'}
```

```bash
git show HEAD~1:fly64/skills/evolution_history.json | ... canonical_versions
# {'brain': '2.24.0', 'skill': '3.5.1', 'as_of': '2026-09-24T00:00:00+08:00'}
```

**结论 `[实测]`**：`fbcc3d7`（提交信息只写"新增 EVO-074"）**把 `canonical_versions.skill` 从 `3.5.1` 回退成 `3.4.2`**，与 `main.py:50` 的 `SKILL_VERSION="3.5.1"` 冲突，`as_of` 也一并改动。同类"版本五处统一"问题曾在 09-23 08:36（`6d0aa42`，窗口外）修过。

### 4.2 `[实测]` 两条 EVO 记录在最后提交中被删除（历史丢失）

```bash
git log --oneline -S'"EVO-073"' -- fly64/skills/evolution_history.json
# fbcc3d7   ← 删除（当前文件中不存在）
# 2f87d77   ← 引入（09-23 20:51）
git log --oneline -S'"EVO-072"' -- fly64/skills/evolution_history.json
# fbcc3d7   ← 删除
# 6d0aa42   ← 引入（09-23 08:36）
```

```bash
python -c "records 对比"
# 当前 HEAD  : 87 条记录，EVO-072=False, EVO-073=False
# HEAD~1..~4 : 81 条记录，EVO-072=True,  EVO-073=True
# 记录数账：81 + AUTO-0017..0023(7) + EVO-074(1) - EVO-072 - EVO-073 = 87  ✔
```

被删内容（从 `git show HEAD~1:…` 取回，原文摘录）：

- **EVO-073**（date 2026-09-24，kind=brain，`BRAIN 2.23.12→2.24.0 / SKILL 3.5.0→3.5.1`，**`"deployed": false`**，source 末尾 `Commit tbd.`）—— **这是唯一记录当前 canonical 版本升级理由的条目**，删掉后 `canonical_versions` 的 2.24.0/3.5.1 失去依据。
- **EVO-072**（date 2026-09-22，kind=skill，点号死键归一化 + coach 合并写入，`"deployed": true`，notes 明确"本条为 P0-1 补录"）—— 删除后 `agents.md` 规则 15 要求的"键名归一化"修复在演进史中消失。

**`[实测]` 同步影响**：Windows 侧与 WSL 运行侧 `skills/evolution_history.json` **md5 完全相同**（`d98c46f96e7d58128c5707e182ef4be2`），即**这次历史删除已同步进活体运行副本**。

### 4.3 `[实测]` 窗口内 `skills/evolution_history.json` 的新增记录

只有 **2 条** date/recorded_at ≥ 2026-09-23：

| id | 日期 | 说明 |
|---|---|---|
| `AUTO-0023` | 2026-09-23 | `brain_update_auto`，2.23.12→2.24.0，`source: resident skill loop`，changes 为占位文本 |
| `EVO-074` | 2026-09-24 | kind=ops，WSLg D3D12 渲染修复（vsync off + swrast），`source: 本次会话：WSLg渲染瓶颈分析 -> vsync修复 -> 软件渲染验证 -> README更新` |

**→ 窗口内 09-25 的 P0-1/P0-2/P0-3/P0-4 四条交付（信用分配矩阵、可执行 fix、闭环守护、has_fix 语义）在 `evolution_history.json` 中**没有任何 EVO 记录** `[实测]`（`AUTO-0023` 是自动占位，`EVO-074` 是渲染修复）。**

### 4.4 `[实测]` `agent.md` / `skills.md` 的窗口章节缺失

```bash
Get-ChildItem agent.md            # D:\codes\flygym\agent.md  mtime 2026-09-23 20:50:31
git log -1 --format='%h|%ad|%s' --date=iso -- agent.md
# 2f87d77|2026-09-23 20:51:22|feat: motor-pool recovery (t1-t9) + gate Hz unit contract + version 2.24.0/3.5.1
Select-String -Path agent.md -Pattern '2026-09-2[3-6]'
# Line 50: ## 2026-09-23: 运动池机动动态范围恢复 + gate 单位契约统一（t1–t9 团队修复轮）
# Line 78: - **非本轮引入**：`git show HEAD:tests/test_plugin_mhr.py` ... 基线陈旧（test-drift）...
```

- `agent.md` 的**最后一章停在 2026-09-23**；09-24 / 09-25 / 09-26 三天**无 `agent.md` 条目**，尽管这三天有 6 个提交（含 2 个 feat/机制提交）。
- `fly64/skills/skills.md` mtime = **2026-09-23 20:49:25**，`Select-String '2026-09'` 只命中第 72 行的历史行（2026-09-14 决策）——**无窗口章节**。

> **`[实测]`**：这构成"规则 15 / 规则 20 在同一窗口内被弃守"的证据：**能查到代码提交，查不到对应的进化史与手册条目**。

---

## 5. 测试产物与基线（窗口内）

### 5.1 `known_failures*.json`（`[实测]`）

```bash
Get-ChildItem fly64/tests -Filter 'known_failures*'
# known_failures.linux.json  8928  2026/9/23  0:20:30
# known_failures.win32.json 16729  2026/9/23 20:46:37
git log --pretty=format:'%h|%ad|%s' --date=iso -- fly64/tests/known_failures.win32.json
# 2f87d77|2026-09-23 20:51:22|feat: motor-pool recovery ...   ← 窗口内唯一一次变更
# 29817be|09-23 09:44:36 ... (窗口外)
# 68ca39c|09-23 00:43:02 ... (窗口外)
git show 2f87d77 --numstat -- fly64/tests/known_failures.win32.json
# 10  0  fly64/tests/known_failures.win32.json        ← 仅 +10 行（+2 条 test-drift：plugin_mhr model string）
```

**基线在窗口内只增 2 条 test-drift，无删减、无 `--update` 重刷**；`known_failures.linux.json` 在窗口内**零变更**（mtime 09-23 00:20，早于窗口）。

### 5.2 pytest 缓存与运行产物（`[实测]`）

```bash
Get-ChildItem fly64/.pytest_cache -Recurse -File
# v/cache/lastfailed   9288  2026/9/25 21:08:59
# v/cache/nodeids    176346  2026/9/25 21:15:55
# v/randomly_seed        10  2026/9/17 11:06:20

python -c "len(json.load(open('fly64/.pytest_cache/v/cache/lastfailed')))"   # 94
python -c "len(json.load(open('fly64/.pytest_cache/v/cache/nodeids')))"      # 1924
```

失败模块 Top（`lastfailed` 聚合）：

```
 11  tests/test_telemetry_completeness.py
 11  tests/_t7_head_test_plugin_mhr.py
 10  tests/test_what_i_see_protocol.py
  9  tests/test_mbon_saturation.py
  7  tests/test_phase6_attribution.py
  6  tests/test_optic_flow.py
  6  tests/test_tunable_wiring.py
```

```bash
Get-ChildItem fly64/.pytest-run -Recurse -File | Sort LastWriteTime -Desc | Select -First 1
# fly64/.pytest-run/test_map_persistence_roundtrip0/map.pkl   2026/9/23 20:42:16
```

**结论 `[实测]`**：
- `fly64/.pytest-run/**` 最后一次落盘 = **09-23 20:42**，`.tmp-pytest/**` 目录 mtime = **09-23 18:56** —— 即 **`.pytest-run` 基线最后一次被写入后，窗口内**（09-23 20:42 → 09-26）**没有新的按 test 落盘**。
- `.pytest_cache` 最后两次落盘 = **09-25 21:08 / 21:15**，此后（09-25 21:15 → 09-26 12:40，约 15.4h）**没有任何 pytest 缓存更新** `[实测]`。

### 5.3 `[实测]` 未跟踪的新测试文件（窗口产出，未入库）

`git status --porcelain` 中 `??` 的测试/脚本（节选，共 15 个测试 + 15 个脚本）：

```
?? fly64/tests/test_aa_report_integrity.py          09-25 17:50
?? fly64/tests/test_aa_trim_clock.py                09-25 12:28
?? fly64/tests/test_aa_window_wiring.py             09-25 11:47
?? fly64/tests/test_coach_consult.py                09-24 14:10
?? fly64/tests/test_cx_loop_break_gate.py           09-25 11:15
?? fly64/tests/test_evo_liveness.py                 09-25 12:27
?? fly64/tests/test_evolution_fix_contract.py       09-25 11:19
?? fly64/tests/test_f4_aa_gate_cost.py              09-25 17:50
?? fly64/tests/test_fix_retry_semantics.py          09-25 21:14
?? fly64/tests/test_g2_aa_report_persistence.py     09-25 12:56
?? fly64/tests/test_jump_leg_gain_chain.py          09-24 21:36
?? fly64/tests/test_jump_pool_homeostat.py          09-24 21:47
?? fly64/tests/test_m4d2_aa_gate.py                 09-25 17:50
?? fly64/tests/test_oscillation_window.py           09-25 11:14
?? fly64/tests/test_param_wiring.py                 09-24 18:23
?? fly64/tests/test_pattern_producer_contract.py    09-25 21:04
?? fly64/tests/test_terminal_surrender.py           09-25 00:27
?? tests/test_memory_avoidance.py                   09-25 19:50   ← 仓库根，非 fly64/tests
```

> `?? tests/`（仓库根）与 `?? fly64/tests/` 并存 → **存在同一套件被两个根收集**的风险 `[推断，中]`（需跑一次 `pytest --collect-only` 确认，本轮未执行）。

---

## 6. 工作树未提交改动：本窗口产生 vs 更早遗留

**可复现命令**：

```powershell
git status --porcelain -- . ':(exclude)fly64/.pytest-run' ':(exclude).tmp-pytest'
git diff --stat -- . ':(exclude)fly64/.pytest-run'
```

`git diff --stat`（剔除 `.pytest-run` 噪声后）共 **36 个文件，4890 增 / 469 删**，其中 `fly64/skills/evolution_skill.py` 独占 **2555 增**。
`git status --porcelain`（含未跟踪）共 **203 行**；剔除 `fly64/.pytest-run/**`（~105 行）与 `.tmp-pytest/**` 后剩 **98 个条目**。

### 6.1 `[实测]` 按"最后一次修改时间"切分（依据：`git log -1 --format=%ci` vs 文件 mtime）

**A. 本窗口产生（mtime ≥ 2026-09-23 09:58，28 个已跟踪文件被改）**

```
09-23 21:17  fly64/tests/test_retina.py
09-23 23:20  fly64/plugin/.consult_request.json
09-24 17:01  docs/analysis/session_logs_execution_plan.md
09-24 19:29  fly64/tests/test_tunable_wiring.py
09-24 19:30  fly64/skills/active_strategy.json
09-24 19:30  fly64/skills/brain_tunable_params.json
09-24 19:32  fly64/contract_registry.json
09-24 19:33  fly64/docs/declared-not-implemented.md
09-24 21:33  fly64/fly64/mushroom_body.py
09-24 21:34  fly64/tests/test_motor_pool_dynamics.py
09-24 21:53  fly64/tests/test_gate_units.py
09-24 22:29  fly64/plugin/strategy_writer.py
09-24 23:05  fly64/tests/test_phase6_fitness_inputs.py
09-24 23:07  fly64/tests/test_phase6_attribution.py
09-25 00:58  fly64/fly64/model.py
09-25 01:03  fly64/tests/test_fix_executor.py
09-25 01:04  fly64/tests/test_fix_template_interpreter.py
09-25 11:12  fly64/tests/test_instinct_bindings.py
09-25 11:14  fly64/tests/test_evolution_capability.py
09-25 11:15  fly64/fly64/central_complex.py
09-25 11:45  fly64/fly64/instinct_bindings.py
09-25 21:00  fly64/skills/fix_executor.py
09-25 21:03  fly64/skills/default_patterns.json
09-25 21:04  fly64/fly64/memory.py
09-25 21:05  fly64/fly64/main.py
09-25 21:13  fly64/skills/evolution_skill.py
09-25 21:14  fly64/skills/README.md
```

**B. 更早遗留（mtime 早于窗口，8 个已跟踪文件被改）**

```
09-20 23:44  fly64/docs/causal-chain-ui-design.md
09-21 10:14  fly64/skills/fix_catalog.json
09-21 14:14  fly64/tests/_live_writeout_check.sh
09-21 14:14  fly64/tests/_live_writeout_probe.py
09-21 14:14  fly64/tests/test_plugin_mhr.py
09-21 14:14  fly64/tests/write_llm_env.sh
09-22 00:19  fly64/environments/protocol.py
09-22 00:26  fly64/tests/test_environment_protocol.py
```

28 + 8 = 36 ✔（与 `git diff --stat` 的文件数一致）

**C. 未跟踪但窗口内产出（`??`，去噪后 ~62 项）**：`docs/execution/**`(11)、`docs/analysis/**`(19)、`fly64/tests/**`(17)、`fly64/scripts/{autonomy_deploy_restart.sh, verify_motor_pools.py}`、`fly64/skills/{fix_guard.py, param_authority.py, param_wiring_ab.json, evo_funnel_alarm.py, verify_state.json, .evo_loop.lock, .evo_loop_heartbeat.json}`、`scripts/{probe_pools.py, verify_motor_pools.py, session_log_extract.py, verify_session_summary.py, verify_doc_citations.py, analyze_sessions_v5.py, _extract_v5.py, _state_for_v5.py, _captain_verify_*}`、根目录 `_audit_catalog.py`、`session-ses_f381.md`、`tests/`。

> **`[实测]` 关键点**：`fly64/skills/evolution_skill.py` 的 **2555 行未提交 diff，其中仅 31 行带本团队标记**（`38c8bae` 提交信息自述）。这意味着 **09-25 的 P0-2/P0-4 两条已验收交付至今不在 HEAD 里**；其依赖测试 `test_pattern_producer_contract.py` / `test_fix_retry_semantics.py` 同样未跟踪。

---

## 7. 活体遥测快照（**单点快照，非趋势**）

**采集时刻**：`2026-09-26 12:29–12:36 +0800`

| 端点 | 采集时刻 | 关键字段（原始） |
|---|---|---|
| `GET http://127.0.0.1:8765/bridge-status.json` | 12:29:2x | `{"seq": 35430, "x": 18, "y": 64, "jump": false, "b": false, "z": false, "age_ms": 16.59, "state": 1, "pose": [-4944.83, 236.22, 4177.03, -2.144], "game_frame": 42753, "render_ms": 6.118}` |
| `GET http://127.0.0.1:8765/flow.json` | 12:30 / 12:35 | 122 键。`brain_version:"2.24.0"`, `skill_version:"3.5.1"`, `scene_name:"致命熔岩地 #244a"`, `scene_hash:"244afa"`, `decision_source:"lf_steering"`, `forward_rate_hz:15.38`, `turn_rate_hz:0.0`, `jump_rate_hz:13.46`, `gate_forward_threshold_hz:0.598`, `gate_jump_threshold_ratio:0.75`, `gate_jump_ratio:0.875`, `gate_forward:true`, `mb_dopamine:-0.3408`, `mb_mbon_forward:0.6881`, `mb_saturation_events:0`, `cpg_state:"grounded"`, `coach_applied.instinct_scene:"致命熔岩地"`, `coach_applied.instinct_applied:true`, `coach_applied.turn_bias:0.25`, `clamped_keys:[…2 条…]`, `clamped_keys_age_s:35.1` |
| `GET http://127.0.0.1:8765/memory.json` | 12:30 / 12:35 | 61 键。`pos_y:120.0`→`218.8`, `scene_label:"致命熔岩地 #c9f1"`→`"#a845"`, `disp_60s:2285.7`→`2126.9`, `stuck_duration:0.0`, `loop_score:0.556`→`0.34`, `health_score:0.9267`→`0.9467`, `visited_cells:608`→`664`, `coverage_pct:22.1`, `anomaly_state:"idle"`, `clamped_keys` **不存在** |

**WSL `/root/fly64/runtime/evolution_history.json`（brain 侧滚动迭代，12:34 快照，仅最近 19 条）**：

```
{"brain_version":"2.24.0","iterations":[
 {"iter":16502,"time":"09-26 12:18:24","trigger":"fallen","findings":["telemetry_gap(100%)"]},
 {"iter":16514,"time":"09-26 12:24:10","trigger":"stuck", "findings":["telemetry_gap(100%)"]},
 {"iter":16521,"time":"09-26 12:28:08","trigger":"fallen","findings":["telemetry_gap(100%)"]}]}
```

- **全部 19 条 iteration 的 `findings` 都是 `telemetry_gap(100%)`、`capabilities` 都是 `telemetry_gap`** `[实测]` —— 即 brain 侧自诊断在**过去 10 分钟内**持续报"条件字段缺失"。
- `plasticity.reward_trend` 在 19 条内从 `-1.35` 摆到 `+8.15`、再到 `-20.67`（**单快照，禁止当作趋势**）。
- `train`/`stuck` 触发交替，`learning_progress` 多次达 `1.0`。

**Liveness 交叉核对（`[实测]`）**：

```
skills/.evo_loop_heartbeat.json : iteration 9859, ts 1790394449.674  (09-26 11:47:29)
runtime/evolution_history.json  : iter 16502..16521               (09-26 12:18..12:28)
```

> 两个计数器不同源（心跳来自 EVO skill 闭环，已死；16502+ 来自 `main.py` 的 brain 主循环），**因此"心跳 9859"不能用于推断 brain 是否活跃** —— 这是遥测口径的一个混淆点，值得下游注意。`main.py` 是 `runtime/evolution_history.json` 的写入方（`grep -rln 'runtime/evolution_history' /root/fly64 --include=*.py` 命中 `fly64/main.py`）。

**快照期进程（12:30:47）**：`python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0`（PID 7401, 起于 12:05:35, CPU 99%）；`./build/us_pc/sm64.us.f3dex2e --skip-intro --configfile /root/fly64/runtime/sm64config.txt`（PID 7418, 起于 12:05:40, CPU 25%）。
`render_ms = 6.12` 与 `bridge age_ms = 16.6` 说明窗口末 `fbcc3d7` 的 vsync/swrast 修复**在活体上有效** `[实测，单点]`。

---

## 8. **本窗口内没有证据的时段或主题**（任务书要求单列）

### 8.1 无任何证据的时间段

| 时段 | 长度 | 缺失的证据种类 | 依据 |
|---|---|---|---|
| **09-23 09:58 → 12:42** | 2h44m | 无 commit、无 `docs/analysis` 产出、无未提交文件 mtime、无 `fly64/runtime/coach_frames` 新帧 | `git log` 相邻提交为 09:50:02 / 12:42:27；全仓 mtime 扫描在该区间无命中 |
| **09-24 01:00 → 11:34** | ~10.5h | 无 commit、无文档产出、**无教练帧**（`coach_frames` 最后一批 09-23 23:50，下一批 09-24 11:34） | mtime 扫描 + `coach_frames` 目录遍历 |
| **09-24 13:39 → 16:38** | ~3h | 无 commit、无文件产出 | 相邻文件 mtime 12:39→13:39 与 16:38 |
| **09-25 21:15 → 09-26 11:47** | ~14.5h | **无 commit、无部署（`.deploy_backup` 最新 09-25 21:05）、无 pytest 缓存更新（最新 21:15）、无 EVO 心跳、无教练帧**（`coach_frames` **整体**止于 09-25 15:28，其后 21h 无新帧） | 五路时间戳交叉一致 |
| **09-26 12:28 → 12:40（快照）** | 12min | 窗口末提交之后无新证据 | `git status` 工作树无变化 |

### 8.2 有"未入库工作"但**在 git 中无对应提交**的时段（任务书要求显式指出）

| 时段 | 实际发生的工作（文件证据） | 为何"无 commit" |
|---|---|---|
| 09-24 12:35 → 18:25（5h50m） | `analysis-t2/t3/t5/t7/a4` 五份审计报告（12:39–13:39）、`session-log-*` 全套 + `session-log-summary.json`（16:38–17:04）、`session_logs_execution_plan.md`（17:01）、`docs/execution/fly64-execution-plan.md`（18:04）、`sp1-completion-report.md`（18:30） | 全部未跟踪或未提交；该时段**唯一**提交是 21:28 的 `ab2761c`（只含 `fly64-autonomy-evolution-plan.md`） |
| 09-24 21:28 → 09-25 20:30（23h02m） | `sp2/sp3/sp4-completion-report.md`（19:38/22:02/23:17）、`fly64-change-specs.md`（09-25 11:17）、`sp5a-*`（12:04/15:24）、`g4-noise-diagnosis-and-decision.md`（16:20）、`w1-w4-closeout-and-h13-verdict.md`（18:40）、`deploy-manifest.md`（19:01）、**4 次部署（18:55/18:58/20:25/21:05）**、17 个新测试文件 | 该时段提交 0 条；下游交付全部停留在未跟踪文件 |
| 09-25 21:18 → 09-26 12:28（15h09m） | 09-26 11:47/12:03/12:05 三次 brain+SM64 启停、12:27 WSL `sm64config.txt` 手工同步、`fbcc3d7` 前的排障过程 | 只有 12:28 一条提交；**排障过程无日志留档**（`/tmp/fly64_run.log` 仅 2 行、无时间戳） |

### 8.3 主题级"无证据"

1. **09-25 的四条 P0 交付（P0-1~P0-4）没有 `evolution_history.json` 记录**（§4.3 实测）；`AUTO-0023` 是自动占位文本，`EVO-074` 是渲染修复。
2. **`agent.md` 无 09-24 / 09-25 / 09-26 章节**（§4.4 实测）——3 天 6 个提交零手册留痕。
3. **`skills.md` 无窗口章节**（mtime 停在 09-23 20:49）。
4. **09-25 P0-3 的"停摆告警"没有任何一次自动触发记录**（crontab 未挂载，`evo_stall_alarm.json` 只有 09-25 21:01 的人工自检结果）。
5. **窗口内没有 CI/门禁产物的落盘证据**：仓库内除 `.pytest_cache` 外未见窗口内 CI 报告（本轮只做了 glob/grep 级检查，**未做全仓穷尽**，属"未证实"而非"已证伪"）。
6. **教练链路在 09-24 12:04 之后没有产出文件证据**：`fly64/skills/fix_catalog.json` / `coach_outcomes.jsonl` / `coach_advice.json` 分别停在 09-21 10:14 / 09-24 11:35 / 09-24 12:04；`fly64/runtime/coach_frames/` 共 190 帧，分布为 09-23 75 帧（23:23:05–23:50:28）、09-24 55 帧（11:34:25–23:59:02）、09-25 60 帧（00:03:17–**15:28:00**），其后至快照（**21.2h**）**零新帧** `[实测]`。而活体 `flow.json` 的 `llm_decision.ts = 1790396036.32`（= 12:13:56）仍在刷新——**"教练帧/结果文件"与"对话决策时间戳"两条链路的活跃度互相矛盾，需下一阶段核实**（可能链路更名/写入路径变更，或帧保存条件在 09-25 部署后不再满足）`[推断，中]`。
   （`coach_frames` 内 >2h 空档共 6 段：09-23 23:50→09-24 11:34 (11.73h)、12:48→15:16 (2.46h)、15:16→21:38 (6.37h)、21:38→23:43 (2.08h)、09-25 01:20→11:16 (9.93h)、13:00→15:28 (2.47h)）

---

## 9. 证据强度自评

| 结论 | 判定 | 强度 |
|---|---|---|
| 窗口内 12 个提交、清单与时间 | 实测 | 高（`git log` 可复现） |
| 首个窗口内提交 = 09-23 12:42 | 实测 | 高 |
| EVO 闭环在 09-26 11:47 后停摆 | 实测 | 高（三路独立：`ps`、`--status`、心跳/日志 mtime） |
| 停摆告警未自动运行 | 实测 | 高（crontab + 告警文件 mtime） |
| 闭环死亡原因 = 一次不含 EVO 的重启 | 推断 | 中高（缺直接因果日志） |
| `clamped_keys` 发布在 flow.json 而非 memory.json | 实测 | 高（两端点同刻对比） |
| 钳位 `source="unknown"`，写入方为本能绑定 | 实测+推断 | 高（记录+绑定签名双向佐证） |
| `EVO-072/073` 被 `fbcc3d7` 删除 | 实测 | 高（`-S` + 记录数账 + HEAD~n 对比） |
| `canonical_versions.skill` 3.5.1→3.4.2 回归 | 实测 | 高 |
| 09-25 P0-1~P0-4 无 EVO 记录、agent.md 缺 3 天 | 实测 | 高 |
| 根目录 `tests/` 与 `fly64/tests/` 双根收集风险 | 推断 | 中（未跑 `--collect-only`） |
| 窗口内无 CI 产物 | 未证实 | 低（非穷尽检查） |

---

## 10. 给后续分析的 6 条要点（不重复已交付日志分析的结论）

1. **重复缺陷模式在窗口内明确再现**：09-25 21:18 交付"闭环守护 + 停摆告警"，09-26 11:47 闭环再次死亡且**告警器根本不在运行** —— 与 v5 六失效点中的"闭环停摆"同族，且**新增一条**：守护脚本未接入任何调度（cron 只有 watchdog/phase2_gate）。
2. **P1-1/P1-2（09-23 交付）在活体上只完成了一半**：钳位**能被看见**（数值对），但**归因是 `unknown`**、**观测点指向错误端点**（日志说 memory.json，实际在 flow.json）、**契约约束没有拦住写入方**（0.7/0.9 持续到达，来自本能绑定 promoted 桶）。
3. **最后一条提交引入了版本/历史回归**：`EVO-072`/`EVO-073` 被删、`canonical_versions.skill` 回退到 3.4.2，与 `main.py` 的 3.5.1 冲突；且该删除已同步到**活体运行副本**（md5 相同）。
4. **窗口的绝大部分产出不在 git 里**：36 个已跟踪文件未提交（其中 28 个是本窗口改的，含 `evolution_skill.py` 的 2555 行）+ ~62 个未跟踪产物（含 `docs/execution/**` 11 份、`docs/analysis/**` 19 份、17 个新测试）。09-25 的 P0-2/P0-4 已验收交付**至今不在 HEAD**。
5. **当前真实困境（实测 + 已入库文档）**：H13 在真实数据下**不成立** → `w1-w4-closeout` 裁定 **P2/P3 阻塞、SP5-B/SP6 不可开工、闭环保持永久 shadow**；F1 未修、H5/H6/H11 未关闭。同时活体 brain 每 600 tick 报一次 `telemetry_gap(100%)`。
6. **下一阶段最该验的三件事**：(a) 把 EVO 守护接入 cron/systemd 并验证一次真实 kill→自动拉起（当前"守护"只有脚本没有调度）；(b) 修钳位归因（识别 instinct-binding 写入方）并统一观测点（flow.json vs memory.json 的文档/代码不一致）；(c) 核实教练咨询链路 09-24 12:04 后无文件产出的同时 `llm_decision.ts` 仍在更新这一矛盾。

---

### 附：本报告用到的全部可复现命令

```bash
# 1) 窗口内提交
git log --since=2026-09-23 --until=2026-09-27 --stat --date=iso
git log --since=2026-09-23T00:00 --until=2026-09-23T23:59 --pretty=format:'%h|%ad|%s' --date=iso
# 2) 工作树
git status --porcelain -- . ':(exclude)fly64/.pytest-run' ':(exclude).tmp-pytest'
git diff --stat -- . ':(exclude)fly64/.pytest-run'
git log -1 --format=%ci -- <file>          # 逐文件最后提交时间 vs mtime
# 3) 演进史 / 记录删除
git log --oneline -S'"EVO-073"' -- fly64/skills/evolution_history.json
git show HEAD~1:fly64/skills/evolution_history.json    # 取回被删记录
# 4) 运行时（WSL）
wsl -e bash -c "ps -ef | head -30"
wsl -e bash -c "cd /root/fly64 && bash scripts/evo_loop_launcher.sh --status"
wsl -e bash -c "crontab -l"
wsl -e bash -c "ls -la /root/fly64/skills/ /root/fly64/runtime/"
wsl -e bash -c "ls -ld /root/fly64/.deploy_backup/*"
wsl -e bash -c "cat /root/fly64/runtime/evolution_history.json"
wsl -e bash -c "cat /tmp/fly64.log"; wsl -e bash -c "cat /tmp/fly64_launcher.log"
wsl -e bash -c "md5sum /root/fly64/skills/evolution_history.json /root/fly64/fly64/main.py"
# 5) 测试基线
Get-ChildItem fly64/.pytest_cache -Recurse -File
Get-ChildItem fly64/.pytest-run -Recurse -File | Sort-Object LastWriteTime -Descending
git show 2f87d77 --numstat -- fly64/tests/known_failures.win32.json
# 6) 活体快照（单点）
curl -s http://127.0.0.1:8765/flow.json
curl -s http://127.0.0.1:8765/memory.json
curl -s http://127.0.0.1:8765/bridge-status.json
```

*报告结束。所有 `[实测]` 项均可在 12:40 的快照状态下按上述命令复现；`[推断]` 项已给出推断链与置信度，请勿当作实测使用。*

---

## 11. 勘误与补录（t5 返修，2026-09-26 13:0x–13:2x；依据 t4 核验报告）

> **纪律**：本节的更正**就地写入上文（带「t5 补注/补录」痕迹）**，并在此集中留痕；**不删除任何既有条目、不放宽任何表述**。凡本节未列者，原结论不变。

| # | 项目 | 原文（t5 前） | 更正后（实测） | 复现 |
|:-:|---|---|---|---|
| 1 | **守护脚本路径（M-4a）** | §1 表第 11 行、§1.2 索引表、§6-C 等处只写 `evo_liveness_guard.py`，**未标注目录** | **`fly64/scripts/evo_liveness_guard.py`**；`fly64/skills/evo_liveness_guard.py` **实测不存在** | `Test-Path fly64/skills/evo_liveness_guard.py` → False；`git ls-files --stage` 命中 `fly64/scripts/…` |
| 2 | **`+407 / +211` 的口径** | §1 表第 11 行写「`evo_liveness_guard.py +407`、`evo_loop_launcher.sh +211`」，易被读成文件行数；t5 的更正曾据此另立「文件总行数 = 339 / 179」 | 这是 `git show --stat` 的**新增行数**——两文件在 `38c8bae` **新建** ⇒ **新增行数 == 文件总行数**：**407 行（15,863 B）** 与 **211 行（7,889 B）**。（⚠️ **t7 更正**：t5 写的 339 行 / 179 行来自此行曾用的 `Get-Content … \| Measure-Object -Line` **漏计口径**，已废弃；可靠口径见右列） | `git show 38c8bae --stat` → `407 +++++` / `211 +++`；`python -c "print(open('fly64/scripts/evo_liveness_guard.py',encoding='utf-8').read().count(chr(10)))"` → **407**（launcher 同法 → **211**） |
| 3 | **锁文件路径（M-4b）** | §1.2 表、§2.3 表、§3.1 结论只写 `.evo_loop.lock`，**未标注目录** | **`/root/fly64/skills/.evo_loop.lock`**（在 `skills/` 下，**不是** `/root/fly64/` 根），内容 `11997` = 陈旧 PID | `wsl cat /root/fly64/skills/.evo_loop.lock` |
| 4 | **`evolution_history.json` 改动量** | §1 表第 12 行写「`+154/-41`」（`--stat` 图形总数） | **`git show fbcc3d7 --numstat` = 115 / 39**；154 = 115+39（口径不同，**非矛盾**，但不应写作插入/删除数） | `git show fbcc3d7 --numstat -- fly64/skills/evolution_history.json` |
| 5 | **`AUTO-0023` 的日期口径** | §4.3 写「`AUTO-0023`｜2026-09-23」 | 精确化：该记录 **`date` 字段为 `None`**，窗口内时间来自 **`recorded_at = 2026-09-23T12:54:49Z`**；结论（窗口内无 P0 记录）**不变** | t4 §4.3 复核；`json.load(...)` 读 `date`/`recorded_at` |

### 11.1 补录（t4 核验指出的两处遗漏）

**(a) 两个新脚本在 git 中均无执行位**`[实测]`

```bash
git ls-files --stage -- fly64/scripts/evo_loop_launcher.sh fly64/scripts/evo_liveness_guard.py
# 100644 51adacdaf809995b8bdaca6f1c677c335ffc199d 0  fly64/scripts/evo_loop_launcher.sh   ← 非 100755
# 100644 ba194a7c877e6ec0ca665af6f216313b3a93fea5 0  fly64/scripts/evo_liveness_guard.py  ← 非 100755
```

⇒ WSL 上必须 `bash scripts/…` 显式调用；这与 `analysis-evo-loop-liveness.md` 的"可被 cron/启动器直接执行"的运行契约冲突，**与 §3.2 的 E1（守护未接调度）同族**，本报告此前未记录。t4 只点名了 launcher，**实测两者都缺执行位**。

**(b) 两份"进化历史"是不同文件，本报告的记录纪律结论只覆盖其中一份**`[实测]`

- `skills/evolution_history.json`：**99,101 B / 1600 行**，结构 `{$schema, canonical_versions, records[87]}`；消费方 `skills/evolution_skill.py:202`（规则 15 写入）、`tests/test_version_consistency.py:28`（规则 8 的 brain 徽章比对）、`scripts/ver_append_*.py`。**§4.3 的全部结论针对此文件。**
  - ⚠️ **t7 记录数复核（2026-09-26 13:24:50 Windows / 13:24:58 WSL）**：**Windows 87 / WSL 87（md5 `d98c46f96e7d58128c5707e182ef4be2` 相同）**；**另有时点观测到 86 条**（过时读数，已作废——md5 逐字节相同即两侧必然同条数，故 87 为权威读数）。该文件**随运行时追加**，**任何引用都必须注明测量时刻**，避免"86 vs 87"式歧义再被引用。
- `runtime/evolution_history.json`：**7,110–7,134 B（滚动重写；13:04 实测 7,110 B）**，结构 `{brain_version, iterations[…~19 条…]}`；**仅存在于 WSL**（Windows 工作区无此文件）；消费方 `fly64/fly64/main.py:61`（启动读入）/`:220`/`:2360`（写入）、`tests/test_brain_startup_regression.py`。**本报告仅在 §2.3 列出其存在，未分析其后果** —— 更正为：它是**易失的运行时副本**，不能作为审计依据；且它与规则 9（历史持久化）绑定，与规则 15（记录契约）**分属不同文件**。
- 历史事故佐证：`fly64/.tmp/write_evo059.py:109` 记录「干净检出导入正常、测试全绿，而生产恒有 `runtime/evolution_history.json` ⇒ 每次生产启动必崩」⇒ 该文件属"运行时独有、仓库不可见"的真实依赖。

**(c) t1 未涉及的 t4 措辞项（无需更正，仅声明）**：M-4c（`burst_active`「无发布点」）**本报告未作此声明**（该措辞出现在 t2 §3.2-E8，已由 t5 更正为「无 flow/memory 发布点」）。
