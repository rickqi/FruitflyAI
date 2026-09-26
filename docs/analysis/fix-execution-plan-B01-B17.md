# Fly64 修复执行计划（B01–B17 具体化）

> **生成**: 2026-09-26 ｜ **依据**: 三轮独立核验后的分析（`project-state-consolidated.md` §3/§4、`blindspot-analysis-0923-0926.md`、`newlogs-review-round2.md`）
> **状态**: 待授权（决策门 U1/U2 见 §5）
> **所有 file:line 均为已核验实测值**

---

## 0. 全局约束（每个任务都必须遵守）

| 约束 | 内容 |
|------|------|
| **规则 9** | 任何部署/重启/kill 操作需用户显式确认后执行 |
| **规则 15** | 每次脑模型/Skill 变更必须向 `fly64/skills/evolution_history.json` 追加完整记录 |
| **规则 12** | Windows→WSL 下发修复；证据文件禁止反向推送（**`fbcc3d7` 的 cp 事故正是违反此精神的反面教材**） |
| **用户约束** | 行为层优先依赖脑模型/EVO 机制完善，**不硬编码控制代码**（用户原话 09-24 12:28:48） |
| **双副本现实** | Windows 工作区与 WSL `/root/fly64` 是两份独立副本，一切同步先 md5 对照、只允许"校验后的定向同步" |
| **探测器纪律** | 每个新守卫必须先证明"能探测"（在坏状态上跑一遍必须失败），参照 EVO-068 |

---

## 1. 波次总览

```
Wave 0  守卫先行        B02(实现，预期FAIL) + exec位 + .gitignore     ~1h    ── 无依赖
Wave 1  记录修复        B03(回收+对齐) → B02 复跑(PASS) → B17(守卫钩子) ~0.5d  ── 依赖 Wave 0
Wave 2  运维闭环        B01(crontab + kill→自愈验证)                  ~1h    ── 依赖 Wave 1（版本对齐后再重启）
Wave 3  收口未入库      B04(四阶段分批提交)                           ~1d    ── 依赖 Wave 1（B17 钩子保护 history）
Wave 4  行为与互斥      B15(stuck_score) + B16(重启互斥)              ~1-2d  ── 依赖 Wave 2（需活体）
```

**关键顺序理由**：B02 先行且**预期失败**（当前 canonical skill 3.4.2 ≠ main.py 3.5.1）——这证明守卫"能探测"；B03 修复数据后 B02 转绿，完成"探测器-故障"闭环。

---

## 2. 任务卡

### B02 — `check_version.py` 补真断言（0.5h）

**现状证据**：`fly64/tests/check_version.py` 全文 4 行——`sys.path.insert(0, "/root/fly64")` + `from fly64.main import BRAIN_VERSION` + `print`。**无任何 assert**；WSL 恒 exit 0，Windows 因硬编码路径反而 `ModuleNotFoundError exit 1`（错因）。

**步骤**：
1. 重写为真断言脚本（纯标准库）：
   - 路径：用 `Path(__file__).resolve().parents[1]` 定位包根（替换硬编码 `/root/fly64`，跨平台）
   - 读三处版本：`main.py` 的 `BRAIN_VERSION`/`SKILL_VERSION`（正则）；`skills/evolution_history.json` 的 `canonical_versions.brain/skill`；`skills/skills.md` 的版本行（regex `BRAIN_VERSION \*\*(.+?)\*\* / SKILL_VERSION \*\*(.+?)\*\*`）
   - **断言 A**：三处 brain 一致
   - **断言 B**：三处 skill 一致
   - **断言 C**（规则 15）：`records` 中必须存在 `brain_version == canonical.brain` 的条目（版本升级必须留档）
   - 失败时打印三方对照表并 `sys.exit(1)`
2. **先在当前坏状态上运行** → 必须失败（skill 3.5.1 vs 3.4.2；EVO-073 缺失致断言 C 失败）——**这是"能探测"的证明**
3. 等 B03 完成后复跑 → 必须通过

**验收**：坏状态 FAIL（含对照表输出）；B03 后 PASS；Windows 与 WSL 两侧均可运行。
**回滚**：`git checkout fly64/tests/check_version.py`（但保留会丢失守卫——不建议回滚）。

---

### B03 — 回收 EVO-072/073 + 版本三元组对齐（0.5d）

**现状证据**：HEAD = 87 条，**缺 EVO-072/073**，canonical skill=**3.4.2**；`HEAD~1` = 81 条**含两条**且 skill=**3.5.1**；added=[AUTO-0017..0023, EVO-074]、removed=[EVO-072,073]（两集合不相交 → 可无损并集）。

**步骤**：
1. `git show HEAD~1:fly64/skills/evolution_history.json > .tmp/evh_head1.json`
2. 写合并脚本：HEAD(87) ∪ HEAD~1(81) 按 `id` 并集 → **89 条**（87 + EVO-072/073）；按 `date` 插回时间线位置（两条为 09-22/09-24，应位于 AUTO-* 块之前）
3. `canonical_versions` = `{brain: "2.24.0", skill: "3.5.1", as_of: <当前时刻>}`（与 main.py 对齐）
4. 运行 B02 守卫 → 必须 PASS
5. 跑 `tests/test_evolution_history.py`（12 PIN：持久化/损坏恢复/版本变化去重/fix+verification 记录/schema 校验）→ 全过
6. **WSL 侧同步**（规则 9：需确认；与 B01 重启打包执行）：停脑 → 同步合并版到 `/root/fly64/skills/evolution_history.json` → 起脑。注意活体可能在跑并追加 AUTO-* 记录，同步前先读一次 WSL 侧做最终并集

**验收**：ids 含 EVO-072/073/074 + AUTO-0017..0023；三处版本一致；B02 PASS；PIN 12/12。
**回滚**：`git checkout fly64/skills/evolution_history.json`（但会再次丢记录——回滚点应在合并脚本产物上做 `.bak`）。

---

### B01 — EVO 守护接入调度 + kill→自愈验证（1h）

**现状证据**：`fly64/scripts/evo_liveness_guard.py`（407 行）/ `evo_loop_launcher.sh`（211 行）均为 **100644（无执行位）**；`crontab -l` 只有 watchdog/phase2_gate；`evo_stall_alarm.json` 停在 09-25 21:01（**告警器自身未运行**）。

**步骤**：
1. `git update-index --chmod=+x fly64/scripts/evo_liveness_guard.py fly64/scripts/evo_loop_launcher.sh`
2. WSL crontab 追加（间隔 5 分钟）：`*/5 * * * * cd /root/fly64 && python3 scripts/evo_liveness_guard.py >> runtime/evo_guard.log 2>&1`
3. **自愈验证（规则 9 需确认）**：kill EVO 循环进程 → 等待 ≤1 个间隔 → `bash scripts/evo_loop_launcher.sh --status` 显示"运行中"且 PID 更新；`evo_stall_alarm.json` 时间戳刷新
4. 记录到 evolution_history（规则 15）

**验收**：crontab 可见条目；人为 kill 后一个间隔内自动拉起；告警文件刷新。
**回滚**：删除 crontab 条目。

---

### B04 — 收口未入库交付（1d，四阶段）

**现状证据**：全局 98 M / 43 D / 71 ??；**09-25 18:55 首次部署因两处未提交回归崩溃**（风险已兑现）；未入库 2485 行中约 2450 行属**另一 DSH 会话**（需协调，勿代提交他人工作）。

**阶段与步骤**：
| 阶段 | 内容 | 命令/动作 |
|:--:|------|----------|
| 4a | 43 项 D 全在 `fly64/.pytest-run/**`（pytest 夹具） | `.gitignore` 追加 `fly64/.pytest-run/`；`git rm -r --cached fly64/.pytest-run` |
| 4b | 本轮分析产出 | 提交 `docs/analysis/*`（两轮全部报告）+ `scripts/session_log_extract.py` / `extract_new_sessions.py` / `session_summary_new_logs.py` |
| 4c | **生产代码（最高风险）** | **先跑双根 pytest 收集 + 全套测试**（此项至今未验证）→ 按逻辑单元分批提交 `main.py` / `memory.py` / `evolution_skill.py`（2555 行改动）；每个 brain/skill 变更配规则 15 记录 |
| 4d | 其余未跟踪 71 项 | 逐一分类：`docs/execution/**`(11) 提交；`.tmp/**` 进 gitignore；脚本按用途归位 |

**验收**：`git status` 只剩有意保留项；全套测试结果已知并记录；每笔提交信息含规则 15 引用。
**回滚**：分批提交天然可 revert；4c 前打 tag。

---

### B15 — `stuck_score` 恒真修复（1-2d，行为耦合，EVO 优先）

**根因（双重独立验证）**：
```
memory.py:213-225  stuck_score = max(rate, temporal, frame)
                   rate 子信号恒真：forward_rate==0 连续 3s ⇒ r_score=1.0
memory.py:227-231  duration 增长 +0.02/tick
memory.py:234-235  disp_60s > 500 ⇒ duration −1.0（泄放抹零）
实验 A: score==1.0 恰 14 次、14/14 dur==0.0；对照 B（disp=None）: dur=0.020
```

**步骤**：
1. **传感器修复（非控制代码，符合用户约束）**：
   - rate 子信号加"指令上下文"门：仅当模型正在**试图移动**（指令非零/意图激活）时才累计 rate-low 时间——"不动"只有在"想动"时才是卡住
   - 泄放改为**衰减**而非清零：`duration = max(0, duration − k·dt)`（k 为参数），或泄放只阻止增长不抹历史
2. **参数化**：`rate_threshold` / `rate_stuck_s` / `temporal_stuck_s` / 泄放阈值 k 全部进 `brain_tunable_params.json`（EVO 可调域）
3. **测试**（把核验实验固化为回归）：隔离实验（纯 rate 路径）+ 对照组（disp=None）+ 断言「score==1.0 ⇒ stuck_duration_true > 0」
4. 用 EVO 闭环回归验证（而非手工调参）：部署后观察 `stuck_score`/`stuck_duration` 一致性
5. 版本：BRAIN 2.24.0 → **2.25.0**（行为耦合）；规则 15 记录；规则 9 部署确认

**验收**：离线仿真 0 次「score==1.0 且 dur==0.0」；活体 5 连采样一致；全套测试无新增 FAIL。
**回滚**：参数回退（ tunable params 恢复旧值）+ git revert。

---

### B16 — 「brain+SM64 重启」互斥与告警（0.5-1d）

**现状证据**：09-26 11:47–12:05 两会话互相拆实例（`6c53f724-v3` 执行 3 条 `pkill -f fly64.main` + `rm -f /tmp/f64b_traj`，杀掉 `51f62457` 的脑 2505 及后续 4 个 PID）；`locked_launcher.py` 只防 `run-fly64` 重复启动（不识 SM64）；`.evo_loop.lock` 只锁 EVO 循环；`brain_wrapper` 自动重启还需 `pkill -f brain_wrapper` 才能摆脱。

**步骤**：
1. 新增 `runtime/brain_restart.lock`（PID + host + 时间戳 + 心跳），**任何**要 pkill/重启 `fly64.main` 或 `sm64.us` 的动作先取锁；陈旧判定（>60s 无心跳）可破坏锁
2. 把散落的 `.tmp/restart_*.sh`（9 个）收敛为一个**规范入口** `scripts/restart_brain.sh`（内部取锁）；`locked_launcher.py` 增加对 SM64 的感知
3. 抢锁失败 → 写入 `evo_stall_alarm.json` 同类告警文件（跨会话可见）
4. 验证：两个终端同时执行 restart → 只有一个成功，另一个收到"held by PID x"告警

**验收**：并发重启测试互斥生效；告警文件落盘；正常单会话重启不受影响。
**回滚**：删除锁文件与入口脚本（回到现状）。

---

### B17 — 消除双份 `evolution_history.json` 分叉 + 一致性守卫（0.5d）

**现状证据**：工作区与 WSL 的 `skills/evolution_history.json` 是两份独立文件（inode 296 vs 125256364637215400），**B03 只修一次数据、B05 只加 md5 门禁，都不消除分叉本身** ⇒ cp 事故结构上可复发。

**步骤**：
1. **写向守卫（最关键）**：pre-commit 钩子（或并入 B02）——拒绝任何使 `EVO-*` id 从 HEAD~1 消失的 `evolution_history.json` 变更（对 EVO-* 追加只允许增不允许减）。**该钩子可直接拦截 fbcc3d7 类事故**
2. **同步守卫**：提供唯一规范同步命令 `scripts/sync_evo_history.ps1/.sh`——同步前自动做"id 集合差"检查（只允许纯追加），非追加需 `--force-merge` 并输出差异明细
3. 文档声明权威方向：**git 侧为已提交历史的权威；WSL 侧为活体追加源**；两侧定期用同一合并脚本对账（复用 B03 的合并脚本）
4. `runtime/evolution_history.json`（dashboard 用，结构不同）与 skills 侧是**不同文件**——文档中已注明消费方（`main.py:61/220/2360` vs `evolution_skill.py:202`），保持现状但命名上避免混淆

**验收**：模拟一次"cp 旧副本再提交"→ 钩子拒绝；正常追加 → 通过。
**回滚**：移除钩子。

---

## 3. 后续小项（P3，可搭车执行）

| 项 | 内容 | 工时 |
|:--:|------|:--:|
| F-a | `scripts/verify_doc_citations.py` 的 DOCS 扩展到 5 份（当前不含 R3 三份新文档） | 0.5h |
| F-b | 修正 `docs/analysis/blindspot-review-round2.md:396`「差值同为 11」→ 实测 68/32 | 10min |
| F-c | 为 12 处历史值 1131 加 grep 白名单说明（避免未来扫描误报） | 10min |
| F-d | `evo_liveness_guard.py`/`evo_loop_launcher.sh` 执行位（已并入 B01 步骤 1） | — |

---

## 4. 决策门（需用户裁定）

| 门 | 问题 | 影响 |
|:--:|------|------|
| **U1** | **是否授权执行本计划？**（选项：我直接执行 / 另建修复团队 / 仅执行 Wave 0–2 / 暂缓） | 决定 Wave 0–4 是否开工 |
| **U2** | **H13 阻塞是否维持？**（H13: `noise_p95=0.1777 ≫ 0.03` ⇒ P2/P3 整体阻塞、闭环永久 shadow） | 决定 P2/P3 与闭环转正式是否解冻 |
| **Gate-9** | 每个 Wave 内的 WSL 操作（重启/kill/crontab/同步）执行前逐项确认 | 规则 9 |

## 5. 风险与回滚总表

| 风险 | 缓解 |
|------|------|
| B03 合并破坏 schema | 合并脚本产出先过 `test_evolution_history.py` 12 PIN 再落盘；保留 `.bak` |
| B04 提交他人会话的在途工作 | 2450/2485 行归属另一会话——**只提交自己可负责的逻辑单元**，他方的先协调 |
| B15 改坏卡住判定（漏报真卡死） | 保留 `stuck_duration_true` 反判据；隔离实验+对照组进回归；参数化后可即时回退 |
| B01 crontab 误伤 | 守卫脚本先 `--dry-run` 模式验证一轮再启用 |
| 双副本再次分叉 | B17 钩子在 B04 提交生产代码**之前**生效 |

## 6. 总工作量

| Wave | 内容 | 估时 |
|:--:|------|:--:|
| 0 | B02 + 杂项 | ~1h |
| 1 | B03 + B17 | ~0.5d |
| 2 | B01 | ~1h |
| 3 | B04 | ~1d |
| 4 | B15 + B16 | ~1-2d |
| **合计** | | **~3-4 天**（单人串行；Wave 0-2 可在半天内完成，立刻消除三个已兑现的风险） |
