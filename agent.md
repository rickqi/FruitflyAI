# FruitflyAI 项目记录

## 工作流程规则

1. 按优先级顺序执行任务（P1 → P2 → P3 → P4）
2. **每完成一个任务**，立即更新 agent.md 变更说明
3. **每完成一个任务**，立即 `git add`、`git commit`、`git push`
4. 确保 `README.md` 和 `agent.md` 同步更新
5. 脑模型需重启使网页文件生效（HTTP 缓存）
6. 保留每个 commit 的根因分析和变更内容说明
7. **每轮 EvolutionSkill 进化后**：
   - **必须重启脑模型**——这是技能进化生效的基础（相当于"睡一觉"后新能力才被加载）
   - **必须递增 `main.py` 的 `BRAIN_VERSION`**（skill/行为管线更新推送时强制）
   - **必须将本轮 skill 闭环执行总结**（触发原因、发现、修复、能力变化）**作为一次完整进化记录写入变更说明并推送**
8. **版本三处同步（强制契约）**：每次进化更新 skill 或脑模型版本时，以下三处必须同步一致，否则仪表板版本显示错误：
   - `main.py` 的 `BRAIN_VERSION`（仪表板徽章数据源，经 flow.json 显示为 "Brain vX.Y.Z"）
   - `main.py` 的 `SKILL_VERSION` 镜像常量（必须镜像 `skills/evolution_skill.py` 的 `SKILL_VERSION`）
   - `skills/skills.md` 的版本号与进化轮次表
   - 校验：`python fly64/tests/check_version.py` 必须通过（镜像一致性守护）；CONSOLIDATE 统一使用 `scripts/consolidate.sh` 智能重启（自动检测游戏进程选择完整/合成模式，禁止手工无脑 `--synthetic`）
9. **进化历史持久化**（已实现）：`/evolution.json` 迭代记录持久化到 `runtime/evolution_history.json`，脑模型启动时自动恢复（仪表板 EVO 历史不再因重启归零）
10. **二期门禁（12 小时稳定自动聘雇）**：自治服务连续稳定运行 ≥12 小时（零 ALERT/零连续失败/健康自检通过）→ `scripts/phase2_gate.sh`（cron 每分钟驱动）自动翻 GO → 开工二期薄 Cordis Tool 层（fly64_status/fly64_consult/fly64_strategy）。禁止在门禁 GO 前提前建设二期
11. 每轮进化能力需配套**回归测试**（`tests/test_evolution_capability.py`），确保进化能力可重复验证、不退化
12. **WSL↔Windows 双向同步是基本能力**：WSL `/root/fly64` 是运行时真实来源（并发进化会话可能直接推进 WSL 代码），Windows 仓库是版本化真实来源。每轮开始/结束运行 `fly64/tests/sync_inventory.sh` 盘点差异并回收（WSL→Windows 回收进化成果；Windows→WSL 下发修复）。PIN 测试断言**当前**实现形态——重构后同步更新 PIN，而不是回退代码
13. **CPU 观察**：脑模型 CPU 持续 >600% 时，检查 HRC/EMD 计算的帧沿节流是否生效（compute_flow/compute_emd 仅应在 10Hz 帧沿执行）
14. **stuck_ramp 高发地形（熔岩/斜坡）调参通道**：教官经 `escape.stuck_threshold_s` 热重载（active_strategy.json）调低 escape 触发秒数，无需改代码
15. **进化记录强制契约（evolution_history.json，强制）**：每次脑模型/Skill 进化（版本递增、能力变更、结构性修复）**必须**向 `fly64/skills/evolution_history.json` 追加一条完整记录——`round`（轮次）、`date`/`time`（时间）、`kind`（brain/skill/infra）、`brain_version`/`skill_version`（版本）、`trigger`（触发原因）、`changes`（变更清单）、`tests`（回归结果）、`source`（commit 或文档出处）——并与 agent.md 变更日志、skills.md 轮次表三处同步。EvolutionSkill 常驻循环会自动检测仪表板 `brain_version` 变化并补录 `brain_update_auto` 记录，但**自动记录只含版本变化，不豁免完整记录义务**（原因/变更/测试必须由执行进化的 agent 人工补全）。校验：`python fly64/skills/evolution_skill.py --history-check` 必须 OK（比对 main.py `BRAIN_VERSION` 与 history canonical 版本，不一致即失败）。禁止无记录的版本递增。**提交硬约束**：进化相关 `git commit` 必须包含 `evolution_history.json` 的更新（记录与代码同 commit，不允许"代码先提交、记录后补"）；README「完整进化历史档案」表通过 `python fly64/skills/evolution_skill.py --history-md` 再生成后更新（只替换 `<!-- EVOLUTION-HISTORY-TABLE -->` 标记间内容，禁止手改表格）
16. **常驻 EVO 循环单实例（跨环境，强制）**：resident 循环**只能在 WSL 运行**（贴着脑模型，规则 12 的运行时真实来源）；Windows 会话/后台任务**禁止**启动 `skills/evolution_skill.py` 循环——双环境各持文件系统锁互不可见，双写会损坏 fix_catalog/evolution_history（已发生：AUTO id 撞号、catalog 覆盖、log 交错，见 EVO-048）。锁文件 `skills/.evo_loop.lock`（跨平台 pid 活性探测、死锁自动破解）只防**同环境**重复启动；跨环境靠本规则。循环启动/重启统一走 WSL；发现 Windows 侧循环立即停止并记录
17. **版本号严格递增契约（brain/skill 双轨，强制）**：任何代码/行为变更必须严格递增对应版本号——
    - **脑模型**：`main.py` 的 `BRAIN_VERSION` —— 缺陷修复/参数调优 → **patch**（z+1）；新增能力/行为变更/新 pattern → **minor**（y+1，z 归零）；破坏性/协议/架构变更 → **major**（x+1）
    - **EVO Skill**：`skills/evolution_skill.py` 的 `SKILL_VERSION` —— 同规则独立递增。仅 brain 侧变更时 skill 不动，仅 skill 变更时 brain 不动
    - **禁止**：① 同版本复用/跨轮共用（连续两轮同版本号）；② 含糊标注（"2.11.x" 类只允许存在于历史记录，新记录/新代码禁止）；③ 版本回退；④ 无对应 evolution_history 记录的递增
    - 每次递增必须：随规则 15 记录（`brain_version`/`skill_version` 字段如实填写）+ `--history-check` OK（自动校验 main.py/skill 文件/canonical 三处一致 + **版本链无回退/无复用**）

18. **脑参数进化与 health v2 治理（Skill v3.2.0+，强制）**：
    - `BrainMutator` 参数试验**只允许**经 `EvolutionPipeline` Phase 6 触发（stuck>60s ∧ loop>0.6，2% 采样）；每次试验的 commit/rollback 与 delta 必须落在 evolution_log.jsonl
    - `skills/brain_tunable_params.json` 的参数增删、`health_score` 权重调整（v2 公式：stall_cost 0.25 / novelty 0.1 / revisit 0.35）视为 **Skill 版本变更**，走规则 15/17
    - SOS 触发条件（L2 对话习惯化 / L2a stuck_no_progress：stuck≥0.8 ∧ coverage_rate<0.01 ∧ dur>5s 持续 30s）变更须同步 README 面板文档与 `help_reason` 枚举
19. **演化证据基座不可破坏（强制）**：`skills/coach_outcomes.jsonl` / `scene_strategy_bindings.json` / `curriculum.json` 是本能固化（P4.4）、课程阶梯（P4.3）与社会指标闭环（P4.6）的**唯一证据来源**，只允许增长，必须按下列三条保护——
    - **测试隔离**：测试会话禁止写入上述生产路径。`tests/conftest.py` 在 pytest 导入期设置 `FLY64_EVIDENCE_DIR`，`plugin/coach_outcomes.py` 与 `fly64/instinct_bindings.py` 据此重定向 `PENDING_PATH`/`OUTCOMES_PATH`/`CURRICULUM_PATH`/`BINDINGS_PATH`。已发生事故：一次测试把 45 条真实 outcome 覆盖为 30 条合成行，且 `*.jsonl` 被 gitignore、无任何备份，**证据不可恢复**
    - **禁止用陈旧镜像反向覆盖**：证据只在 WSL 运行时增长，Windows 侧副本永远是陈旧镜像。跨环境同步（规则 12）**只允许 WSL→Windows** 拉取证据，禁止 Windows→WSL 推送证据文件；违反即静默丢弃运行期证据（已发生：语料 45 条→30 条，两侧 mtime 与字节数完全相同，无任何截断代码路径）
    - **缩水自动检测**：`append_outcome()` 维护高水位标记（`.hwm`）与周期快照（`.snap`），发现语料行数低于高水位即从快照恢复并告警；守卫本身必须永不抛出（耐久性记账不得打断分析循环）
    - 禁止以“制造晋级/达标”为目的放宽任何证据门槛。拒绝晋级是正确行为，须通过 `binding_status()` 的可观测差距来推进，而非降低门槛（对照：固定 goal 曾使课程 30 次尝试假晋级至 stage 9）
20. **验证基线（回归可探测，强制）**：`tests/known_failures.json` 是**受跟踪的既有失败基线**，每条必须带 `cause`（`environment` / `aspirational` / `test-drift` / `live-state` / `real-bug`）与 `note`（证据）。每轮改动验收必须执行 `python3 scripts/check_regressions.py`——
    - **只在新失败时非零退出**，因此可安全用作门禁；`--strict` 还会因“基线条目已通过”失败，防止基线腐化；修好一条后 `--update` 刷新
    - **禁止**为了让套件变绿而删除测试、放宽断言或无条件 skip。`pytest.skip` 只允许附**可测量的原因**（如“活体端点当前无求助内容”），且**连接失败/端点消失必须仍然失败**——脑挂掉是必须被看见的运行态，不是可以跳过的噪声
    - 基线是**平台作用域**的（字段 `platform`）：Windows 与 WSL 的失败集不同，跨平台使用前须各自建基线
    - 与规则 19 的分工：规则 19 管“证据不受损”，规则 20 管“回归可探测”——共同堵住“机制存在、报告成功、无法生效”的盲区


## 2026-09-23: 运动池机动动态范围恢复 + gate 单位契约统一（t1–t9 团队修复轮）

**根因（t1 只读定位；证据 `docs/analysis/motor-pool-saturation-findings.md`）**

1. **forward 池贴顶 46.15–50 Hz 的主因不是 MBON**。MBON 注入在漏电之前（`model.py` 注入 < 漏电）且放电后硬复位，单路上限仅 **8.2 Hz**（解析 T=6 tick + 离线实测）。真正的地板是 **post-leak 恒流 0.88 V/tick** = `TurnAdaptation` 的 stuck boost `0.500`（`stuck_duration > 30 s` 即全额支付，**与疲劳水平无关**）+ `tonic` `0.180` + **粘滞** `reflex_forward` `0.200`；模型对池占用率**零负反馈**（15 个 forward 写点穷举无一读占用率）。
2. **steering 池 0.000 Hz**：同一 boost 对左右池各 **−0.25 V/tick 对称钳位**；除 `escape_current`/tonic/OU 外所有 steering 驱动都是成对反号推挽项 ⇒ 两池在线实测**从不共放电**；`TurnAdaptation` 疲劳由池放电自身积分 ⇒ 双池静默时无复活电流（自锁）。
3. **`gate_jump` 恒假**：per-tick 比例（0..1）与 **Hz** 阈值（2.0 / 活体 3.082）直接比较；同一 tick 的 WS packet `gate_jump=True` 与 flow.json `gate_jump=False` 并存 26/26。

**变更清单（两条实现线，合并后无冲突）**

| 文件 | 线 | 变更 |
|---|---|---|
| `fly64/fly64/model.py` | t2 + t8（+399/−28） | ① forward 池占用率 homeostat（`forward_homeo_gain`：0.30 起抑制 / 0.60 触底 / 下限 0.25）作用于 MBON→forward 与 forward 池 intrinsic tonic；② 新增 `_aux_forward_current()`：escape_current 前向片、escape accumulator、R16 breakout 前向腿、reflex 前向桥四腿的**占用率增益 + 聚合上限 0.20 V/tick**；③ `breakout_split()`：双侧 turn 钳位乘真实交替量（静默飞行 → 0，前向突破保留 0.25 下限）；④ 反射标志**到期**（`__setattr__` 写戳 + `reflex_flag_scale()`，ttl 0.30 s / τ 0.20 s）；⑤ `_last_disp_x/_z` 死读中性化（无信号不 ramp）；⑥ `blend_reflex_control()` + `reflex_network_share=0.25`（反射期保留 LIF 份额，待 main.py 接线） |
| `fly64/fly64/main.py` | t3（+95） | `rate_per_tick_to_hz()` 单点换算 + `gate_open_hz()` 同量纲严格 `>`；flow.json 发布 `forward/turn/jump_rate_hz`、`gate_*_threshold_hz`，`gate_forward/gate_jump` 由 Hz vs Hz 得出；旧 per-tick 比较删除 |
| `fly64/skills/brain_tunable_params.json` | t3 | 两条 gate 阈值改为 **Hz** 域：forward `0.4..8.0`/默认 `2.0`；jump `2.0..20.0`/默认 `8.0`（maxima < Nyquist 50 Hz） |
| `fly64/docs/declared-not-implemented.md` | t3 | §2 未接线项 → 0 条；新增 §2b「Closed decisions」登记两个 gate pid（Hz 单位契约、真实 reader、PIN） |
| `fly64/contract_registry.json` | **t7**（v1.0.0 → v1.1.0） | flow_json 增 `rate_gate_group`（9 键）、`unit_contract`（per-tick/HZ 键、换算点、比较点、阈值单位、残留分歧）、零容忍条目 `RULE-19k`；meta.changelog 记录本轮 |
| `fly64/tests/test_motor_pool_dynamics.py` | t2 + t8 | 新增 22 测试：占用率与单调性、负反馈（纯映射 + 实跑）、视觉驱动差、steering 双侧非零、osc=1 与 live-like escape < 50%、dead-read、反射到期/归零、AST 穷举写点契约、聚合上限、无未播种 RNG |
| `fly64/tests/test_gate_units.py` | t3 | 新增单位/边界/可达性 PIN（阈值标定锚在 model.py 解码参照，禁止放宽） |
| `docs/analysis/motor-pool-saturation-findings.md` | t1/t8/t7 | t1 根因报告（538 行）+ t8 §7.4 范围映射 + **t7 §8 修复对照/集成回归/残留/待确认部署步骤** |

**测试结果（t7 集成回归）**

- `pytest tests/test_motor_pool_dynamics.py tests/test_gate_units.py tests/test_strategy_key_contract.py -q` → **44 passed，exit 0**
- `pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_cpg_priority.py tests/test_dashboard_protocol.py -q` → **66 passed，exit 0**
- `pytest tests/test_phase6_fitness_inputs.py tests/test_memory.py tests/test_optic_flow.py --deselect tests/test_optic_flow.py::test_flow_computation_performance -q` → **148 passed, 1 deselected，exit 0**
- 全量套件 + **规则 20 门禁**（`scripts/check_regressions.py` 自带运行）：`failing now 37 / still failing 35 (known) / NEW failures 2 / baseline-now-PASS 1`，**exit 1**
  - 2 条 NEW 全在 `tests/test_plugin_mhr.py`（`test_manifest_valid`、`TestCycle::test_frame_captured_into_request`），同一根因：断言要求 LLM 型号 `glm-5v-turbo`，而已提交的 `plugin/manifest.json` 为 `qwen3.8-27b-uncensored`（测试 45/169 行）
  - **非本轮引入**：`git show HEAD:tests/test_plugin_mhr.py` 原样运行同样 2 failed/44 passed（A/B 实测）；该文件不 import `fly64.model`，t2/t3/t8 diff 面不含 `fly64/plugin/**`；基线记录于 `2026-09-23T01:09`，型号切换是其后提交的 `78b3175` ⇒ **基线陈旧**（`test-drift`），需 plugin/LLM 线修期望值或基线归属方 `--update` 登记
  - 1 条基线转通过：`test_fix_executor::TestParseFixTemplate::test_manual_fallback`（他人并发改动）
- 契约审计（t7 自研探针 `fly64/.tmp/t7_contract_audit.py`，21 项检查）：**21/21 PASS**（registry 的 9 个 rate/gate 键在 producer 中全部存在；`*_hz` 键双侧存在；fallback 与 schema 默认 2.0/8.0 一致；maxima < Nyquist；docs §2b 一致；`telemetry.py` 2.0 vs schema 8.0 的残留分歧已登记在 `unit_contract.known_divergence`）
- `scripts/contract_gate.py` 现仍 **FAIL（8 blocker，全为 ZT-1）**：全部来自 `audit_contract_pairs.py` 对 `skills/scene_strategy_bindings.json` 与 `plugin/.consult_{request,response}.json` 的 DEAD-WRITE/SILENT-DEFAULT，**与 registry/单位契约无关**；A/B（HEAD registry vs 工作区 registry）显示 registry 相关检查（ZT-5 / bridge / completeness）**均为 0 findings** ⇒ 该 FAIL 为**预存状态**，非本轮引入

**版本轨判定（规则 17 / 18）**

- **判定：行为变更（minor）**。运动池注入结构、反射腿到期、以及反射期 LIF 份额语义都是**行为变更/新增能力**，按规则 17 取 minor。
- **建议递增**：`BRAIN_VERSION` **2.23.12 → 2.24.0**（main.py）；t3 的 `skills/brain_tunable_params.json` 属规则 18 的 Skill 版本变更（参数域修正、无新能力）→ `SKILL_VERSION` **3.5.0 → 3.5.1**（`skills/evolution_skill.py` 与 main.py 镜像同步）。
- ⚠️ **本轮 t7 未执行递增**：`fly64/fly64/main.py`、`fly64/skills/*` 均在 t7 的 out-of-scope 内（改动由 t3 持有、合并由 captain 裁定）。因此上述递增与规则 15 记录**必须由持有 main.py/skills 的任务线或 captain 执行**；**禁止**只递增版本不补记录（`python fly64/skills/evolution_skill.py --history-check` 会失败，现基线为 `BRAIN_VERSION=2.23.12 / SKILL_VERSION=3.5.0 OK`）。
- **规则 15 记录要求**：向 `fly64/skills/evolution_history.json` 追加一条完整记录（`round`=本轮团队修复、`date`/`time`、`kind`=`brain`（含 skill 侧变更时另记一条 `skill`）、`brain_version`=2.24.0、`skill_version`=3.5.1、`trigger`（t1 三条根因）、`changes`（上表清单）、`tests`（上述命令与结果）、`source`（本文件本节 + `docs/analysis/motor-pool-saturation-findings.md` §8）），并与 `agent.md`、`skills/skills.md` 轮次表三处同步；README 的进化历史表用 `python fly64/skills/evolution_skill.py --history-md` 再生成（只替换标记间内容）。规则 8 的三处版本同步校验：`python fly64/tests/check_version.py` 必须通过。

**待用户确认的部署步骤（t7 产出，未执行；详见 `docs/analysis/motor-pool-saturation-findings.md` §8.5）**

1. 记录 WSL 现状 md5 作为回滚锚点；2. `rsync` 同步 `model.py`/`main.py`/`brain_tunable_params.json` 到 `/root/fly64`（规则 12 方向：Windows→WSL 下发修复；证据文件禁止反向推送）；3. `scripts/launch_full.sh`（或 `consolidate.sh`）重启脑模型+SM64；4. `python scripts/probe_pools.py` 复测 `forward/left/right/jump` Hz + `GET /flow.json` 检查 `*_hz` 键；5. 判据：forward 稳态占用率 < 0.5（目标 ≈20–22 Hz，修复前恒 50 Hz）、定向驱动下 left/right 均非零、gate 两路同量纲；6. 异常即按第 1 步回滚。
**注意**：规则 9——部署/重启需显式用户确认；本页只给清单，**未执行**。git 提交亦未执行（由用户决定）。

### 应勘误

- **t2 台账 `acceptanceResults[1].evidence`** 原文本"model 侧注入不粘滞（main 侧待接线）"与 t8 实况不符。正确描述：`reflex_flag_scale()` 就地实现（ttl 0.30 s / τ 0.20 s，`step_count·dt` 计时，回放安全）；一次性写入 eff 70→3.97；刷新恒 70；raw attr ∞（不越权改生产者）。该文本因 t2 已终态无法更新，以本条为准。
- **t9 二轮审查**确认 round-1 的 F1 blocker / F2 high 全部闭合。审查详情见 `docs/analysis/motor-pool-review-t8.md`。
- **`check_regressions.py` 基线更新**（#1 门禁登记）：`tests/test_plugin_mhr.py` 两 FAIL（`test_glm_returns_advice_text` / `test_fallen_recovery_has_params`）因 plugin/manifest.json 模型字符串 `glm-5v-turbo→qwen3.8-27b-uncensored` 漂移（他人 commit `78b3175`），已登记为 `cause=test-drift`。A/B 对照：HEAD 版同文件原样运行 = 同 2 FAIL / 44 PASS。

## 2026-09-19: WSL 完整全链路启动（脑模型 + SM64 WSLg 显示）

**目标**：在 WSL2 中完整启动 Fly64 神经系统闭环——脑模型（MaleCNS 166,700 神经元）对接 SM64 游戏，通过共享内存桥接实现视觉→神经→运动控制。

### 启动方式对比与修复

**问题**：`wsl -e bash -c` 中 `setsid nohup` 启动的后台进程会被 WSL 会话退出时连带干掉，SM64 始终无法持久运行。

**修复**：改用 `Start-Process wsl -d Ubuntu-22.04 /bin/bash /root/fly64/scripts/launch_full.sh` 启动，进程组正确脱离。

**显示方案**：

| 方案 | 窗口可见 | 帧数据 | 前提 |
|------|---------|--------|------|
| **xvfb**（虚拟帧缓冲） | ❌ 无窗口 | ✅ Frame Seq 持续增长，93%+ 非零像素 | 无 |
| **WSLg**（DISPLAY=:0） | ✅ 应有窗口 | ✅ 桥接延迟 0.56ms，game_frame 1632 | 需 `apt install x11-xserver-utils`（提供 xrandr） |

**WSLg 屏幕尺寸修复**：安装 `xrandr` 前 SDL2 报 `your 131072x1 screen size is bogus` 无法运行。安装后 SDL 正确检测 `976x1560` 分辨率，SM64 正常启动并通过 `SDL_VIDEODRIVER=x11` 环境变量强制 X11 后端。

### 验证指标（实测读数）

| 指标 | xvfb 方案 | WSLg 方案 |
|------|-----------|-----------|
| **桥接延迟** | 0.46 ms | 0.56 ms |
| **帧序列号** | 3900+ | 1082+ |
| **像素非零率** | 96.8% | 93.2% |
| **渲染耗时** | 5.73 ms/帧 | 10.5 ms/帧 |
| **桥接状态** | state=1 | state=1 |
| **脑健康评分** | 0.70 | 0.63 |
| **场景识别** | 山坡·天空 | 山坡·天空 |

### 遗留问题
- WSLg 下 SDL 窗口仍报 `your 131072x1 screen size is bogus`（仅 stderr 警告，不影响 cubemap 渲染管线）
- `wsl -e bash -c` + `setsid nohup` 无法可靠持久化后台进程；通过 `Start-Process wsl /bin/bash script.sh` 绕过

### 新建文件
- `fly64/scripts/launch_full.sh` — 一键全链路启动（脑模型 + SM64）
- `fly64/scripts/check_bridge.py` / `check_bridge_v2.py` — 桥接帧数据检查脚本
- `scripts/check_dashboard.py` — 仪表板多端点状态检查

## 2026-09-17: EVO-059 — Brain v2.23.1（修复生产启动崩溃）

**脑进程在生产环境完全无法启动**，而全部单元测试通过。

`main.py` 在模块级第 64 行调用 `_load_evolution_history()`，该函数写入 `DashboardHTTP.evolution_json`，但 `DashboardHTTP` 定义在第 176 行 → 导入期 `NameError: name 'DashboardHTTP' is not defined`。`except (OSError, ValueError, AttributeError)` **不包含 NameError**，异常直接抛出终止导入。

为什么躲过了所有本地验证：文件 `runtime/evolution_history.json` 缺失时函数走 `OSError` 分支提前 `return`，所以**干净检出导入正常、测试全绿**；而该文件由常驻 EVO 循环在 WSL 运行时恒常写入——**每次生产启动必崩**。本次同步新代码后脑进程连续两次启动失败（`/tmp/fly64_run.log`）才暴露。

修复：移除模块级调用，改在 `main()` 开头调用（此时 `DashboardHTTP` 已定义、HTTP 服务尚未启动），并在原位置留下显式注释禁止移回。新增 `tests/test_brain_startup_regression.py` **5 条**——关键是最后一条在**填充了 runtime/evolution_history.json 的真实子进程**中导入，复现触发条件而非仅导入模块（只导入模块的测试永远发现不了这个缺陷）。

同时修复部署脚本的路径映射缺陷：`SRC` 取仓库根（`D:\codes\flygym`）而 `DEP` 取项目目录（`/root/fly64`），目标路径因此多出一层 `fly64/`，文件被写到 `/root/fly64/fly64/fly64/` 而真实文件从未更新——脚本却仍逐行打印 `ok`（无校验）。现改为 `SRC=/mnt/d/codes/flygym/fly64`、`DEP=/root/fly64` 的对齐映射，并在复制后逐个 **md5 逐字节校验**，任一不符即 ABORT。

**教训**：任何触及 `main.py` 导入期的改动，必须**在 WSL 实机重启脑进程**验证，单元测试通过不构成证据。另需注意 `active_strategy.json` 会被其他写入方以**扁平点号键**形式覆写（`"escape.commit_ticks"`），一旦如此 `load_active_strategy()` 的段透传（EVO-054 修复）会再次静默失效——写入方审计为开放项。
## 2026-09-17: EVO-062 — Brain v2.23.4（操作面板“死控件” + 教练上下文 NameError）

### ① 面板滑块从未到达行为层

`web/evo-params.html` 直接把 `skills/brain_tunable_params.json` 的参数 id POST 出去，而**这些 id 是点号路径**：

```js
fetch('/active_strategy-update', {..., body: JSON.stringify({[pid]: Number(value)})})
// pid = "escape.commit_ticks"  ->  {"escape.commit_ticks": 125}
```

`/active_strategy-update` 的处理器把该键当**字面顶层键**写入文件：

```python
cur["escape.commit_ticks"] = 125      # 死键
```

而脑的热加载读取的是 `_active_strategy["escape"]["commit_ticks"]`。于是：滑块显示 ✓、UI 回显新值、接口返回 `{"status":"ok"}`，**行为层零变化**。21 个可调 id 中有 **15 个**本就精确映射到脑会读取的路径（`exploration.turn_bias`、`escape.commit_ticks`、`escape.forward_accum_max`…），整个特性**只差一次点号展开**。

修复：新增模块级 `apply_strategy_update()` 展开点号路径为嵌套写入；接口响应新增 `applied`（每个键解析到的真实路径）与 `rejected`（被拒的键），把死写入从“裸 ok”变成可见事实；中间层已是标量时**拒绝而非覆盖**。

### ② 每条求助路径都抛 NameError

补丁脚本 `scripts/m8_add_posy_to_consult.py` 向三处上下文写入 `"pos_y": pos_y_ctx`，但其“插入定义”的 `str.replace` **未匹配源码**——它按 12 空格缩进搜索 `stuck = float(...)` 并假设 `no_reflex` 紧随其后，而实际 `stuck` 为 8 空格缩进且中间隔着 `if self._prim_zero_run >= 3:` 块。`str.replace` 不匹配时静默返回原串，脚本照常打印成功并退出 0。

后果：`pos_y_ctx` 从未定义，`reflex_ineffective_stuck` / `unsolvable_stuck` / `multi_signal_stuck` 三条路径全部抛 `NameError`——即**飞行器卡住时教练恰好崩溃**，而卡住正是教练唯一的被调用时机。本次在部署前拦截。

修复：按脚本原意补上定义（`mem["pos_y"]` 优先，回退 `position.y`）；并把该脚本改为锚定真实源码、幂等、定义缺失时**非零退出**。

### 测试

`tests/test_strategy_update_endpoint.py` 的关键断言走**真实消费者 API** `load_active_strategy`，而非“文件里有这个键”——旧实现恰好满足后者。另有 AST 守卫确保 `do_POST` 必须调用 helper 并上报 `applied`/`rejected`。
`tests/test_consult_context_pos_y.py` 覆盖四条求助路径 + 静态守卫“定义先于首次使用”（**跳过注释行**：解释性注释引用同一字符串会让朴素 `str.index` 误报顺序违规）。

**活体端到端验证**（脑 v2.23.4）：基线 `turn_bias=0.8` / `escape_stuck_threshold_s=5.0` → POST `{"exploration.turn_bias":0.37,"escape.stuck_threshold_s":77.7}` → 落盘嵌套、顶层无点号死键 → 600-tick 热加载后遥测读到 **0.37 / 77.7**。

> 同类缺陷至此累计五例：t6 段透传、CX 死代码、P4.4 全参数指纹、启动期 NameError、本轮点号键。共同形态均为“**机制存在、报告成功、无法生效**”——规则 19 已就此立规：拒绝生效必须是可观测的，而非沉默。
## 2026-09-17: EVO-066 — Skill v3.4.0（系统性契约审计：死旋钮清理）

本次会话此前靠人工偶然发现了**六个**同族缺陷，于是改为**系统性审计**：新增 `scripts/audit_contract_pairs.py`，对每个跨组件 JSON 工件的每个键（含嵌套路径）在其管线模块内做 AST 级写入点/读取点统计，标记**只写不读**（死写）与**只读不写**（静默默认）。首轮即机械地找出三组此前未知的缺陷。

### ① 三个教练死旋钮

`escape.reverse_seconds`、`fallen_recovery.climb_period`、`fallen_recovery.persist_seconds` 被 `SECTION_SPECS` 白名单校验、被 GLM prompt **明确要求输出**、被写入 `active_strategy.json`——而**全仓零消费者**。脑只读 `escape.stuck_threshold_s` 与 `fallen_recovery.mode`。代码中唯一的"反向"属于 wall_stuck 反射的 `wall_stuck_reverse_duration`（另一机制、另一归属）；`git log -S` 证实自插件首次提交起从未接线（消费教练键的 EVO R11 提交只列了 `bold_explore_stuck_s` / `turn_bias` / `escape.stuck_threshold_s`）。

处置：从 SPEC 与 prompt 中移除（`ACTIVE_STRATEGY_DEFAULTS` 与加载器保持原样，故输出形状与行为不变），只停止向教练宣传无法生效的旋钮。

### ② 更严重：面板 21 个可调参数中 14 个完全惰性

`brain_tunable_params.json` 向操作面板宣传 21 个参数，其中 **14 个在整个 `fly64/` 与 `plugin/` 源码中零出现**（AST 读取点抽取 + 全仓标识符 grep 双重确认）：`escape.commit_reinforce/commit_suppress/forward_accum_step`、`exploration.breakout_forward_bias/cliff_tangent_gain/dopamine_revisit_cost/gate_forward_threshold/gate_jump_threshold/loop_breakout_threshold/revisit_penalty_scale/stuck_ramp_cooldown/visual_gain_novelty_boost`、`reflex.adaptive_cooldown_scale/cooldown_min`。它们是**先于实现写下的愿景名**——反射的真实概念是 `cooldown_duration`，而 `gate_*` 阈值在 `model.py` 中根本不存在。

后果远超 UI 观感：**BrainMutator / Phase 6 对这 21 个全部做高斯变异**，即约 **2/3 的搜索维度是纯噪声**，试验的适应度增量无法归因，可能提交一个"活维度其实没动"的候选——自进化循环的效率与可解释性同时受损。

处置：schema → v1.1.0，为 21 个参数逐一标注 `wired`（7 true / 14 false）并写入 `wired_note`；`BrainMutator` 新增 `live_params`，`param_paths`/`generate_candidate`/`_inject` 全部改用之，**搜索空间 21 维 → 7 维**；面板读取标志，未接线参数**禁用**并标注"未接线"，计数显示为"总数 (n 未接线)"。

### ③ 把一次性修复变成机制

- `tests/test_coach_contract.py`：`SECTION_SPECS` 宣传的**每个**键必须在脑中有读取点——死旋钮无法回归
- `tests/test_tunable_wiring.py`：每个参数必须显式声明 `wired`；`wired=true` 必须有消费者；集合必须精确等于已验证的 7 个；Phase 6 只含 wired；`_inject` 不写入 unwired；面板必须禁用惰性滑块
- 同时修正两处**把死旋钮写成期望行为**的测试（`test_coach_advice_fix` 的硬编码键表改为从 `SECTION_SPECS` 派生；`test_plugin_mhr::test_sanitize_strategy` 改为断言死键被丢弃）——它们此前正是"测试维持死机制存活"

> **审计价值**：六个此前靠人工偶然发现的同族缺陷，本次由工具在首轮机械地找出三组（含此前完全未知的 14 个惰性参数）。结论：**系统性契约审计优于逐个碰**，工具已留存于仓中以供每次改动后复核。

**版本轨**：skill 3.3.0 → **3.4.0**（规则 18：`brain_tunable_params.json` 参数集变更属 Skill 变更；Phase 6 搜索空间收敛属行为变更 → minor）。脑侧仅同步 `SKILL_VERSION` 镜像常量，**BRAIN_VERSION 保持 2.23.5**。
## 2026-09-17: EVO-067 — Skill v3.4.1（双环实测 + Phase 6 归因仪表）

执行建议"度量 Phase 6 收益 / 跟踪 P4.4 晋级"。新增只读工具 `scripts/measure_evolution_health.py`，从既有运行时数据（`evolution_log.jsonl` 15521 行去重、绑定库、outcome 语料）算出两个自进化环的真实产出。

### Phase 6 实测（88 次去重试验）

| 指标 | 实测值 |
|---|---|
| 提交 / 回滚 | **2 / 86（提交率 2.27%）** |
| 增量分布 | min −0.0576 · **p50 0.0** · max 0.25 · mean 0.0003 |
| **delta 恰好为 0.0** | **55 / 88 = 62.5%**（两端适应度逐位相同） |
| **\|delta\| ≤ 0.03**（低于门槛） | **83 / 88 = 94.3%** |
| 非零增量的中位数 \|delta\| | 0.0059（仅 2 次越过门槛） |
| 惰维度占全部维度移动 | **73.3%** |

**我的尖锐假设被证伪**：我曾断言 Phase 6 会"提交一个活维度其实没动的候选"——实测 **0/2 提交存在零活维度移动**（两次提交分别移动了 4 个与 7 个活维度）。因此 EVO-066 的 21→7 收敛应定性为**卫生与可解释性改进**（每轮少写 14 个无用键、试验记录可读），**而非**已观测错误提交的修复。

**冻结输入假设仅弱支持**：零 delta 组 baseline 均值 0.186 vs 非零组 0.208，中位数几乎相同（0.1131 vs 0.1190），不足以断言"卡住导致适应度冻结"。

**真正的缺陷是失败不可归因**：日志只存标量 `delta`/`baseline`/`current`，62.5% 的精确零值无法区分"输入未变 / 字段缺失 / 权重相消"——与 EVO-065 同族的**不可观测状态**。已把 `fitness()` 重构为 `fitness_components()`（七项加权分量 + 原始输入 + 样本时间戳）+ `fitness()`（对分量求和，**算术逐字不变**，并有等价性测试逐例钉住），并让 `evaluate()` 记录两端分量与 **`same_sample`** 标志（两端样本时间戳相同即证明采集器从未刷新指标）。

### P4.4 实测（10 签名 / 6 场景，0 晋级）

- 7 个签名 `improved=1`（距晋级差 1）、3 个为 0、1 个被 `worse` 证伪；42 条 outcome：17 improved / 22 unchanged / 3 worse
- **关键更正**：42 条里 31 条无场景标签被丢弃，但**全部集中在 22:58–18:27**（脑进程不可达窗口）；**18:31 脑重启后 11/11 全部带标签** → 该缺口是历史遗留，**无需改代码**
- 因此我先前"签名复用 0% 是结构性的"论断**证据不足**：可用样本仅 11 条、跨约 2.5 小时，不足以断言教练从不重复参数集

**结论**：P4.4 当前的阻塞是**证据量**，而非签名粒度或场景身份（后者已在 EVO-064 实测排除）。应跟踪 `signature_reuse_rate` 与可用 outcome 数量。

> 方法论收获：度量不仅是"确认改动有效"，**它证伪了我自己的假设并给出了更重要的缺陷**。建议今后每轮改动后运行 `scripts/measure_evolution_health.py` 与 `scripts/audit_contract_pairs.py`——两者都是只读的。

**版本轨**：仅 skill 3.4.0 → **3.4.1**（patch，诊断仪表化；适应度算术经等价测试验证未变）。脑行为未变，BRAIN_VERSION 保持 2.23.5。
## 2026-09-17: EVO-068（Infra — 验证基线：让回归可探测）

### 问题：项目无法把进展与噪声分开

Windows 套件长期带约 **40 个未分类失败**。为回答唯一重要的问题——"我是否弄坏了什么"——本轮不得不派子代理对照 pristine HEAD 副本做一次基线归属；代价高、不可复用，而且同一套件多次运行的失败数在 39/40 间漂移。**当所有失败同样响亮时，真实回归就藏起来了。**

### 处置

**1. 受跟踪的基线 `tests/known_failures.json`（36 条，0 未分类）**

| cause | 条数 | 含义与实例 |
|---|---|---|
| `environment` | 13 | 平台/依赖缺口：Windows 无 `time.clock_gettime_ns`、gbk 解码、缺 `.cache/malecns/weights.npz` |
| `aspirational` | 15 | **测试断言的功能在全仓零实现**：`ENHANCED_PROMPT_TEMPLATE` 整套未实现（10 条）；`MushroomBody._saturation_recovery_counter` / `_saturation_recovered` 全仓零出现（5 条） |
| `real-bug` | 5 | 行为与期望**真实不符**：`loop_score` 在 200 个新格后仍为 1.0；`compute_flow` 29.35 ms vs 5 ms 预算；"视觉→运动池无直连"不变量被违反 |
| `test-drift` | 3 | 功能仍在但断言过时：`decision_source` 已重构为 `resolve_decision_source(...)`，测试仍在 grep 旧的字面赋值 |

**2. 探测器 `scripts/check_regressions.py`**——跑套件后与基线比对，输出 NEW / 仍失败 / 基线中已通过；**只在新失败时非零退出**（可安全作门禁），`--strict` 还会因"基线条目已通过"失败以防腐化，`--update` 刷新。

**3. 探测器必须被证明能探测**——`tests/test_regression_detector.py` **注入一个故意失败的测试**，断言报告 `NEW ≥ 1` 且非零退出，并在 `finally` 中清理探针。**无法探测的探测器毫无价值。**

**4. 顺手修掉设计性 flaky**：4 条快照测试在 `/help.json` 无内容时失败（实测形态既有 `{}` 也有 `{"help_reason": null}`）。新增 `_get_live()`：**无求助内容时 skip 并给出可测原因，连接失败仍然失败**（脑挂掉必须被看见），有内容时照常断言——因此畸形快照无法靠 skip 蒙混。

**5. 规则 20**：每轮验收必须跑探测器；**禁止**为让套件变绿而删测试、放宽断言或无条件 `skip`；`skip` 只允许附可测量原因；基线是平台作用域的。

### 结果

`40 failed / 881 passed / 36 skipped` → **`36 failed / 881 passed / 36 skipped`**：4 条 flaky 失败转为有据可查的 skip，**通过数不变**（证明它们从来不是在测代码）；其余 36 条全部带成因与证据，新的回归会立刻以 `NEW` 冒头并非零退出。

> 累计发现："先写愿景、未实现"模式的条目已达 **29 项**（`aspirational` 测试 15 + EVO-066 的未接参数 14）。建议后续做成一张"已声明未实现"清单，逐项决定**实现**或**正式废弃**。

**版本轨**：仅测试质量、脚本与文档，不改生产代码，故**不递增版本**（沿用 brain 2.23.5 / skill 3.4.1）。

## 2026-09-18: EVO-071 — Skill v3.4.2（Phase 6 适应度根因修复 + 四条建议执行）

### Phase 6 根因：适应度函数 40% 权重读的是不存在的字段

EVO-067 上线的 `fitness_components` 仪表在 34 条唯一试验中暴露出**决定性的归因数据**（`scripts/attribute_phase6_failures.py`）：四个字段（`coverage_rate` / `first_contact_rate` / `novelty` / `revisit_ratio`）在 34 次试验中**零次变化**——因为 `SensorSample` **根本没有它们**，`getattr(sample, name, default)` 静默归零。40% 的适应度权重因此永远是常量，123 次试验仅 3 次提交。

修复：全部从 `visited_cells` / `revisit_count` / `forward_speed` / `loop_score` 派生，新增 `missing_inputs` 上报，`evaluate()` 传入基线样本算窗口内速率。

### 四条建议落地

- **本能趋势跟踪**：`--snapshot` / `--trend` 已就绪。当前趋势：`promoted 1→2`、`signature_reuse_rate 8.3%→11.9%`。
- **两处误判更正**：`test_spin_loop_fix`（update 签名误用）与 `test_optic_flow`（缺 `pos_y`）均非 real-bug，实为 test-drift。
- **登记册**：31 项（16 愿景测试 + 14 未接参数 + 1 架构愿景），见 `docs/declared-not-implemented.md`。
- **架构审计**：`model.py` 66 处运动池电流注入，`test_no_visual_motor_shortcut` 不变量按设计不成立 → aspirational。

## 2026-09-17: EVO-057 — Brain v2.22.0（CX 持续环路确定性破解）

`circle_loop` 可持续数分钟不破：CX 的探索游走是 ~10s 正弦扫掠，频率远低于紧致轨道。工作树中另有一段"强制随机跳列"代码试图解决它，但**从未生效**——两个各自独立的死因，加上一个契约破坏：

1. 它读 `getattr(self, "stuck_duration", 0.0)`，而该属性属于 `StuckDetector`/`FlyModel`，`CentralComplex` **从未拥有**，判据恒为 `0.0 > 300`；
2. 它的守卫 `goal_strength < 0.10` 求值于游走块**之后**，而游走块恰好把 `goal_strength` 抬到 `0.30`——"需要它成立时它必不成立"；该类以 `goal_strength` 表述的守卫会被一切合成写入（游走、破环自身）自我毒化；
3. 它调用未播种的 `np.random.default_rng()`，即便生效也会破坏 `replay.py` 的精确回放契约。

修复：`cx.update()` 新增 `stuck_duration` 形参并由 `model.py` 传入真实信号；新增 `_ext_goal_strength`（**仅**由 goal_vectors/novelty 分支写入的"真实目标"信号）取代一切 `goal_strength` 守卫；`CX_LOOP_BREAK_STUCK_S = 45.0` 对齐既有 30/60s 逃逸档位；`CX_LOOP_BREAK_COOLDOWN_TICKS = 1500` 防止每 tick 重瞄；跳列下标改用 `_jump_seq` 乘法散列，确定性可回放；`compass_stats` 暴露 `loop_breaks`/`stuck_time`。PIN 套件 `tests/test_cx_loop_break.py` 15 条逐条钉住每个死因（含"源码中禁止出现未播种 RNG"）。回归：CX/导航/memory **122 passed**。

## 2026-09-17: EVO-058 — Brain v2.23.0 / Skill v3.3.0（P4.4 本能固化可达化 + 证据基座加固）

P4.4"场景→策略本能固化"此前是**已实现但结构上不可能达成**，四重独立死因：

1. 指纹要求**全参数精确一致**，而教练每次咨询都重调参数——真实 45 条 outcome 里同一场景产生 **13 个互不相同**的指纹，证据永远重启，晋级阈值不可达；
2. `get_binding` 返回整段参数，其中多数字段签名并不区分 → 签名与"被绑定行为"**不自洽**（两个 outcome 可同签名却隐含不同行为）；
3. 记录侧 `scene_label` 依赖 `memory.json`，而**脑进程当时已死**，30 条新记录场景全为空；
4. 测试直接写生产证据路径，把 45 条真实 outcome 覆盖为 30 条合成行，且 `*.jsonl` 被 gitignore、Windows 侧为陈旧镜像且反向同步过一次——**不可恢复**。

课程侧同族问题：固定 goal 使晋级形同虚设（曾 30 次尝试冲到 stage 9）。

修复：显著**量化**签名（`mode` 类别 + `turn_bias` 量化 0.1 + `stuck_threshold_s` 分桶 5.0），刻意排除逐集变化且无因果内容的旋钮；`binding_params()` 只绑定签名所区分的参数并取量化规范值（自洽）；晋级改为"自上次 worse 以来的干净 improved ≥ 2"，`worse` 视为**证伪**（既降级也清零，须凭新证据重新赢得晋级）；`binding_status()` 把"拒绝晋级"从沉默变为可观测；`main.py` 热加载接入 `get_binding(scene_key(scene))`，`coach_applied` 暴露 `instinct_scene`/`instinct_applied`；课程改用 `STAGE_GOALS` 渐进阶梯。

**活体受控端到端验证**（脑 v2.23.0 运行中）：基线 `instinct_scene='致命熔岩地'` / `instinct_applied=False` / `turn_bias=0.8` → 注入晋级绑定（`turn_bias=0.33`、`stuck_threshold_s=7.77`、`mode=directional_climb`）→ 热加载后 `instinct_applied=True` 且三个特征值**全部出现在行为层** `coach_applied`，随后清除合成绑定。

**负结果（就地记录，勿重试）**：以现有 45 条真实 outcome 复算，最粗显著签名下最佳候选为 `improved=2/worse=1`，`mode+turn_bias` 视图为 `2 improved/2 worse`，**合格签名数 0**——晋级拒绝是正确行为而非缺陷。禁止为制造晋级而降低门槛。

**开放缺陷**：`scene_key` 取 `#` 前的前缀，而该前缀随飞行变化（天空·山坡/通道·山坡/山坡），绑定只在同前缀期间生效——场景身份稳定性待解决。
## 2026-09-17: EVO-049 — Skill v3.2.0（L2 导航质量与自我进化闭环）

- **SOS 缩略图**：raw RGB→PNG 转换 + flipY + screen_b64 优先（此前面板永远空白）
- **L2a 求助触发器**：stuck_no_progress（绕圈 30s 即产出含缩略图快照，生产已命中）；reflex_ineffective 补绕圈分支
- **health v2**：+stall_cost 0.25、+novelty 0.1、revisit 0.35——同场景恢复有梯度，绕圈无进展有惩罚
- **六阶段进化**：Phase 6 Evolve（BrainMutator 十参数高斯变异 + 120s 试验 + 适应度提交/回滚）
- **轨迹回放**：Live 增量合并/时间基准播放/抽稀+Chaikin 平滑/内存网格热力地毯/会话存档闭环（File 下拉不再为空）
- **规则 18** 新增（脑参数进化与 health 治理）

## 项目结构

```
D:\codes\flygym\
├── fly64/                    # Fly64 果蝇脑控制 Mario 项目
│   ├── fly64/                # Python 核心源码
│   │   ├── main.py           # 主循环 + HTTP API
│   │   ├── memory.py         # 空间记忆 + 卡住检测 (Phase 1)
│   │   ├── bridge.py         # 共享内存桥接 (Linux/macOS)
│   │   ├── model.py          # LIF 神经元模型
│   │   ├── retina.py         # 球面复眼采样
│   │   ├── telemetry.py      # 仪表板遥测
│   │   ├── data.py           # MaleCNS 数据下载/预处理
│   │   └── replay.py         # 回放录制
│   ├── web/                  # Web 仪表板
│   │   ├── index.html        # 主仪表板
│   │   ├── memory-heatmap.js # 空间记忆热力图
│   │   ├── dashboard.js      # 仪表板 JS
│   │   ├── dashboard.css     # 仪表板样式
│   │   └── trajectory.html   # 3D 轨迹回放 (Three.js)
│   ├── scripts/              # 安装/运行脚本
│   ├── patches/              # sm64ex Fly64 补丁
│   ├── tests/                # 测试
│   │   └── test_memory.py    # memory.py 单元测试 (19 tests)
│   ├── docs/                 # 文档
│   └── README.md             # 完整安装指南
├── scripts/                  # FlyGym 相关
├── agent.md                  # 项目记录 (本文件)
└── README.md                 # 项目总览
```

## 环境

- **Windows**: WSL2 Ubuntu-22.04
- **Python**: 3.10 (WSL) / 3.11 (Windows venv)
- **SM64**: sm64ex (patched) - sm64.us.f3dex2e
- **Brain Data**: MaleCNS v1.0 (166,700 neurons)
- **GitHub**: https://github.com/rickqi/FruitflyAI.git

## 运行状态

| 组件 | 位置 | 状态 |
|------|------|------|
| 脑模型 | WSL 常驻 | **v2.19.0**（R31 motor expansion complete / skill 3.1.0；历史全记录 50 条见 fly64/skills/evolution_history.json）|
| SM64 游戏 | WSL PID # | 运行中 |
| 仪表板 | http://127.0.0.1:8765/ | ✅ |
| 3D 轨迹 | http://127.0.0.1:8765/trajectory.html | ✅ |
| 空间记忆 | http://127.0.0.1:8765/memory.json | ✅ |
| 轨迹 API | /trajectory.json /trajectory-list.json /trajectory-load | ✅ |

### 启动契约（t18 结构修复，强制）

**大脑与 SM64 必须用 `setsid nohup … &` 脱离宿主 shell 常驻**，输出重定向且 `</dev/null`：

```bash
# 大脑
cd /root/fly64
setsid nohup python3 -m fly64.main --bridge /tmp/f64b_traj \
  --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64.log 2>&1 < /dev/null &
# SM64
cd /root/fly64/.cache/sm64ex
setsid nohup env FLY64_BRIDGE=/tmp/f64b_traj \
  ./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/sm64.log 2>&1 < /dev/null &
```

**禁止**在托管后台 job（pwsh `run_in_background` / agent 后台 job / 交互终端前台）中直接启动：宿主会话结束或 job 被回收时，SM64 与大脑作为前台子进程被连带 kill → 共享内存桥冻结 → 仪表板显示卡死。此事故已发生两次。规范化入口：`scripts/consolidate.sh`（已内置 setsid 启动）。

---

# 变更日志

## 2026-09-15: t28 P1 动作熵探索 — Brain v2.23.10（卡住时高斯噪声破死循环）

**触发**：novelty≈0 且 loop_score>0.7 时大脑在既定模式死循环，需要噪声触发新动作组合。

**修复**（main.py）：
- 纯函数 `apply_action_entropy(control, novelty, loop_score, stuck_duration, rng)`：触发条件 novelty<0.1 且 loop_score>0.7；`σ = min(30, stuck_duration/10)`（60s→σ6，300s→σ30 封顶）；control.x/y 注入 N(0,σ) 并钳位 ±80
- run_loop 在 write_control 前调用；命中时 decision_source 追加 `+action_entropy`（dashboard 协议枚举同步扩展）
- `action_entropy_sigma()` 抽出便于验证单调性

**回归**：`tests/test_action_entropy.py` 7 用例（σ 契约 60s→6/300s→30/封顶/单调、触发与非触发分支、300 样本统计 σ(stuck300)>σ(stuck60)、±80 钳位、decision_source 标记、main.py 接线断言）；test_dashboard_protocol 枚举扩展 +5 entropy 组合；全量与 HEAD worktree 基线失败集逐项一致（44 项既有，零新增）。

**版本**：Brain 2.23.9→**2.23.10**（SKILL 3.4.2 镜像不变）。

---

## 2026-09-15: t26 P1 最小逃逸持续时间 1.5s — Brain v2.20.2（防 0.02s 瞬放）

**触发**：逃逸平均 0.02s 即被释放（effectiveness_rate=1.4%）——根因是 `_escape_activated_at` "set once, never resets"：首次逃逸的时间戳永久保留，任何后续重触发都继承巨大 `_escape_s`，释放逻辑下一 tick 即闪放。

**修复**（memory.py）：
1. **每次新逃逸激活重新武装激活时钟**（False→True 上升沿 `_escape_activated_at=_now`），`_escape_s` 变为真实 episode 时长；
2. **`MIN_ESCAPE_DURATION=1.5s` 类常量**：`_release_escape` 增加 `_min_dur_ok` guard——不足 1.5s 禁止任何释放（60s 超时/30s+异常清除两条路都被挡）；期间 fallen 走 t23 旁路保持逃脱，不因 stuck_score 波动中断；
3. 正常 resolve（逃逸真正结束后的 outcome 标记）不受影响。

**回归**：test_escape_release.py 新增 TestMinEscapeDuration 4 用例（<1s 释放被锁、released_at 保持 0；>60s 窗口下 min-dur 满足后正常释放且 fallen 旁路保持；长间隔重触发不再瞬放且连续 tick 不释放；常量=1.5），11/11；全量与 HEAD worktree 基线失败集一致（差异均为 3D 网格 WIP 抖动，零真实新增）。

**版本**：Brain 2.20.1→**2.20.2**（SKILL 3.2.0 镜像不变）。

---

## 2026-09-15: t25 P0 LIF 竞争优先 — Brain v2.20.1（CPG 原语降级为零输出 fallback）

**触发**：decision_source=cpg_primitive 无条件覆盖 LIF 网络竞争输出——CPG 阶段激活时 `cpg_apply_phase` 直接改写 stick，所有运动决策走硬编码原语，网络变摆设。

**修复**（main.py）：
- 决策分相：LIF 运动池实际驱动时（`|x|>8 or |y|>8`，`LIF_MOTION_MIN=8`）**网络保留 stick 所有权**——phase 仅经 strike/crouch 神经门（电流注入）影响网络，不写字段；decision_source=`lf_escape`（escape+驱动）/`lf_steering`（驱动）
- CPG 原语**仅在 LIF 输出≈零时**接管 stick（`cpg_apply_phase`），decision_source=`cpg_primitive:*`；CPG gate 两条路径都保持（合并不静音）
- 归因逻辑抽为纯函数 `resolve_decision_source()`（main.py 模块级，Node/py 均可单测）；`_lif_motion` 在 phase 应用前采样（顺序断言防回归）

**回归**：`tests/test_cpg_priority.py` 9 用例——LIF 驱动胜过 CPG/lf_escape 优先/零输出 CPG 接管/零输出且无 CPG 落 jump/steering/安全反射最高级/阈值=8/相位块保 stick 采样顺序断言；test_dashboard_protocol 枚举加入 lf_steering/lf_escape；全量与 HEAD worktree 基线失败集一致（差异为 3D 网格 WIP 测试污染抖动，零真实新增）。

**版本**：Brain 2.20.0→**2.20.1**（SKILL 3.2.0 镜像不变）。

---

## 2026-09-15: t24 Escape Events 五态 outcome + 复合快照 + 效率着色 — Brain v2.19.3

**变更**：
- `EscapeEventBuffer` schema 扩充：`reasons`（全部激活条件列表，首项为主原因）、快照字段 `anomaly_state`/`anomaly_duration`/`terrain`/`loop_score`/`novelty`/`coach_keys`（bold_explore_stuck_s/turn_bias/escape_stuck_threshold_s）、`post_escape_anomaly`（逃逸结束后首个再激活异常标注）
- **outcome 五态**：in_progress / resolved_effective(>30u) / resolved_ineffective(≤30u) / escalated(<10s 内再逃逸，前次自动升级) / aborted；`resolve_current(distance, effective_min_u=30, aborted=False)` 阈值参数化；升级窗口使用事件相对时间戳（可测性）
- main.py 逃逸起点采集复合 reasons（reflex_/fallen/stuck/cliff/flow 并列非互斥）+ 快照注入；resolve 处 effective/ineffective 计数 + effectiveness_rate；事件起点若异常已再激活则回标前次事件
- 仪表板：事件表新增 **Eff（u/s 效率比=distance/duration）** 与 **Outcome** 列（绿=effective/红=ineffective/金=escalated/cyan=in_progress/灰=aborted），reason 列 "+N" 提示复合原因，行 title 含 post_escape_anomaly；头部新增质量统计 `✓eff ✗ineff · eff rate`
- counters 新增：total_cliff_escapes / total_fallen_escapes / total_stuck_escapes / effective_count / ineffective_count / effectiveness_rate

**回归**：新增 `tests/test_escape_outcomes.py` 11 用例（五态各分支、复合 reasons、快照字段、post_escape_anomaly 标注与去重、效率比输入、escalate 窗口内外、计数器契约）；escape 套件 18/18、plugin 45/45；全量 45 failed 与 HEAD 基线逐项一致（零新增）。修复：升级窗口改用事件相对时间戳（原混用墙钟导致窗口判断失真）。

**版本**：Brain 2.19.2→**2.19.3**（SKILL 3.1.1 镜像不变）。

---

## 2026-09-15: t23 逃逸释放锁死三合一修复 — Brain v2.19.2

**触发**：幽灵公馆场景 fallen→escape 被释放冷却锁死 30 分钟，loop_score 饱和不回落，突围失败。

**三重根因与修复**（memory.py）：
1. **冷却 1800s→60s**：`_released_recently` 阈值下调；且**新异常激活（anomaly_override 上升沿）立即重置 `_escape_released_at=0` 并重启 `_escape_activated_at`**——新鲜证据不被旧释放冷却消音（否则 fresh escape 会被残留 `_escape_s>60` 瞬间再释放，实测发现）。
2. **fallen 越过冷却闸门**：`_fallen` 移到 `(not _release_escape and not _released_recently)` 括号外侧 OR——坠落恢复是生存刚需，冷却永不阻断。
3. **stuck_score 去 fallen 钉死**：`StuckDetector` 删除 `max(..., 1.0 if fallen)`（update 与 property 两处）——fallen 不再把 stuck_score 钉在 1.0，位移恢复后分数正常回落，loop_score 随之解除饱和。

**回归**：新增 `tests/test_escape_release.py` 7 用例（FakeClock 快进冷却；fallen 即刻逃逸；释放后 fallen 越过闸门仍逃逸；60s 冷却过期恢复；+19s 新异常立即恢复；stuck_score 位移回落不钉死；端到端 stuck_score 归零）。测试隔离：替换 `mem.time` 模块引用防其他用例泄漏的 time.monotonic 污染。全量与 HEAD worktree 基线失败集一致，零新增。

**版本**：Brain 2.19.1→**2.19.2**（SKILL 3.1.1 镜像不变）；skills.md 当前版本行同步。

---

## 2026-09-15: t22 轨迹 3D 高度可视化（纯前端 trajectory.html，不 bump 版本）

**变更**（全部在 web/ 端）：
- 新增 `web/trajectory-height.js` 纯函数模块（three-free，Node 可单测）：heightColor(t) 蓝→红渐变、verticalSegmentCount/verticalStep（每 N 点一条垂线，全 buffer ≤~300 段 GPU 高效）、autoGroundY(首点高度，回退基线 120)
- trajectory.html：①路径线/点改 BufferGeometry color attribute + vertexColors:true，按实际高度蓝(低Y)→红(高Y)渐变，pushPts 单趟 O(n) 写入；②新增 LineSegments 垂直参考线——每第 N 点垂到 SM64 地面基线 y=120（预分配 1500 段，drawRange 控制）；③GridHelper 从硬编码 y=0 平移到首轨迹点高度 autoGroundY(pts)（回退 120）；④recent_path 记忆路径改 yAt(x,z) 真实地面高度采样（原固定 y0+4）
- 诊断钩子 `window.__heightState()`（minY/maxY/colored/vertSegments/gridY）

**回归**：`tests/test_trajectory_height.py`——Node 实跑 helpers（mock 400 点高度 50→200：蓝/红主导端点、红蓝通道单调、垂线段数契约 400→400 段/6000→300 段/空 0）+ trajectory.html 结构断言（color attribute/vertexColors/LineSegments/GROUND_Y/autoGroundY/yAt 采样/诊断钩子）；node --check 通过；dashboard 测试无回归。后端零改动（/trajectory.json 字段不变，版本不 bump）。

---

## 2026-09-15: t21 验收追加 — /coach_frames 文件名白名单硬化 + 3D 键崩溃热修（Brain v2.18.1）

**变更**：
- `/coach_frames/<name>` 文件名校验升级为严格白名单 `re.fullmatch(r"[A-Za-z0-9_\-.]+\.png", name)` 且显式拒绝 `..`（此前为黑名单式过滤）；+2 PIN 用例（白名单正则在场、保存格式文件名满足白名单）
- **WSL 崩溃热修**：同步最新在途 3D 网格升级（`SpatialMap._key` 返回 (x,y,z) 三元组）后大脑启动即崩——`_get_repulsion` 仍按 2 元组解包。修复为 x/z 足迹匹配（兼容 2/3 元组，3D 键按同 y 层找邻居）。该 8 个 test_memory 失败为在途轮既有（HEAD worktree 对照一致），非本次引入
- 版本 2.18.0→**2.18.1**；部署后大脑恢复在线、`/coach_frames` 系列端点核验通过（见 t21 验收清单）

---

## 2026-09-15: EVO R29 — CCL 8-连通修复 + 小目标追踪 KPI 基线（Brain v2.14.0）
**触发**：t5 视网膜标定发现 stride-2 采样阻塞 4-连通 CCL——`compute_small_targets()` 始终返回 `target_count=0`，P2 小目标追踪功能形同虚设。

**修复（纯 retina.py 内部，零接口变更）**：
- `_connected_components()` scipy 路径：`ndi.generate_binary_structure(2, 1)` → `structure(2, 2)`
- union-find 回退路径：增加 4 个对角邻居检查（左上/右上/左下/右下）
- 测试：`tests/test_ccl_connectivity.py` 5 用例全绿

**版本**：Brain 2.14.0（SKILL 3.0.0 不变）

## 2026-09-15: EVO Round 27 — 全量瓶颈攻破（Brain v2.13.3→2.14.0，集成轮）

**AgentTeams 团队"fly64-bottleneck-roundup"系统攻破 7 大瓶颈 + 2 项部分缓解。**

### 集成输出

**修复实施（6 项门禁发现全部修复）：**

1. **llm_consult.py** — `prompt is PROMPT_TEMPLATE` 身份比较改为值比较 `==`（#1 Low）
2. **mushroom_body.py** — 自适应 LR 加速公式 `min(1.0, ...)` → `min(2.0, ...)`，修复场景变化率 20% 时 LR 翻倍预期不生效问题（#2 Medium）
3. **main.py** — `build_telemetry_audit_section` 集成到主循环（每 100 ticks 自动运行），audit 结果写入 flow_json `"audit"` 键，DeadValueDetector 报告与 FlowKeyValidator 运行时校验实时可见（#3 Medium）
4. **main.py** — 启动 key validation 从空 `{}` 改为延迟到首次真实 flow_json 发布时执行，修复"0 present"误报（#4 Medium）
5. **test_p2_kpi.py** — stride-1/sttride-2 采样差异文档增强，引用 B2 根因分析和 t5 报告（#5 Medium）
6. **mushroom_body.py** — 同步调整 `lr_adapt` 上界 2.0（对应文档"20%场景变化率时 LR 加倍"）

**版本递增**：Brain **2.13.3→2.14.0**（SKILL_VERSION 3.0.0 不变）。三处同步（main.py / skills.md / agent.md）。

**全量测试**（结果见下方回归）：
- T2 what_i_see 语义接口：40 项测试全绿
- T3 MBON 塑形+可塑性+光流：53 项测试全绿，全量 484/498
- T4 计算纪律+自检+死值：`compute_discipline.py` + `telemetry_audit.py` 集成验证
- T5 视网膜标定：26 项测试 / P2 KPI 复测：13 项测试
- T6 审查通过（6 项发现本轮全部修复）
- **全量回归套件：零新增失败**

### 产出来源

| 任务 | 负责 | 产出 |
|------|------|------|
| T1 | data-analyst | `analysis/t1-bottleneck-root-cause-analysis.md`（7 大瓶颈 + 2 项缓解分析） |
| T2 | semantic-engineer | `docs/what_i_see_protocol.md` / `plugin/scene_context.py` / 40 测试 |
| T3 | neural-engineer | MBON 饱和恢复 / 层归一化 / 自适应 LR / flow_quality / 53 测试 |
| T4 | systems-engineer | `compute_discipline.py` / `telemetry_audit.py` / 集成到 main.py |
| T5 | vision-engineer | `tests/test_retina_calibration.py` (26) / `tests/test_p2_kpi.py` (13) |
| T6 | reviewer | 全量技术审核报告（6 项发现） |
| **T7** | **integrator** | **合并 PR + 6 项修复 + 文档 + 版本 v2.14.0 + 全量测试** |

**版本**：Brain **2.13.3→2.14.0**；Skill **3.0.0**（不变）。记录：`evolution_history.json` EVO-034。

---

## 2026-09-15: R22-skill — 进化记录强制契约落地（EvolutionHistory + 遥测补盲，Brain 2.13.3 不变）

**触发**：①并发会话致记录源三处矛盾（README 停在 R17/v2.11.0、skills.md 版本行过期、轮次双编号）；②常驻循环首轮 telemetry_gap 自诊断抓到真实回归——`mbon_saturation` pattern 所需 `mb_mbon_forward` 在 main.py 已暴露但 skill 采集层漏收；③进化过程本身无强制记录载体。

**变更**：
- `skills/evolution_history.json`（新）：进化权威记录，回填 **32 条**（R1→R21 + t/MHR 全量，含双编号 `numbering_notes`）
- `skills/evolution_skill.py`：`EvolutionHistory` 记录器——brain_version 变化自动补录 `brain_update_auto`、`record_fix`/`record_verification`、损坏隔离+原子写出；CLI `--history-check` 强制校验（canonical vs main.py，不一致非零退出）；SensorSample/get_metrics 补 `mb_mbon_forward` 映射（telemetry_gap 归零）
- `agent.md` 规则 **15**：进化记录强制契约（完整记录义务 + 三处同步 + `--history-check` 必须 OK + 禁止无记录的版本递增）；`skills.md` RECORD 步骤与版本行（2.13.1→2.13.3）同步；README EVO 章节更新至 R1–21/v2.13.3 并新增"进化记录强制契约"小节

**回归**：`tests/test_evolution_history.py` 12/12；`--history-check` OK；`check_version.py` OK（2.13.3 三处一致）。**live 实证**：AUTO-0002 = `mbon_saturation` 首次真实触发（forward MBON 饱和贴顶）——检测链路修复→pattern 复活→首次命中→自动记录，同一小时闭环。

**版本**：Brain **2.13.3** 不变（本轮纯 skill/infra）；Skill 3.0.0。记录：`evolution_history.json` EVO-033。

---

## 2026-09-14: t21 收尾补丁 — Brain v2.13.3（consult 截图快照留存 runtime/coach_frames/）

**变更**：`plugin/runner.py` 新增 `save_consult_frame()`——每次 consult 前（capture_frame 之后、consult 之前）将帧保存为 `runtime/coach_frames/coach_{ts}_{help_reason}.png`（help_reason 文件名安全化，缺省 none；裸 RGB 经 PNG 编码器转换；best-effort 失败不阻塞 consult）。service.py 经 PluginRunner 自动覆盖。回溯查询"教练当时看到了什么画面"自此可行。

**回归**：新增 TestConsultFrameSnapshot 4 用例（PNG 魔数/文件名格式/reason 清洗与缺省/None 帧透传/run_cycle 接线断言）；test_plugin_mhr 45/45；全量 482 passed / 11 基线零新增。

**版本**：Brain 2.13.2→**2.13.3**。

---

## 2026-09-14: t21 读屏能力 — Brain v2.13.2（GLM 教练显式屏幕文字读取 what_i_see）

**变更**：
- `plugin/llm_consult.py` PROMPT_TEMPLATE 新增第 0 条读屏指令（"特别注意屏幕上的文字：读出所有可见英文/中文文字……逐条列在 what_i_see"）+ JSON 格式示例加 what_i_see 字段 + "根据屏幕看到的+下方状态数据"措辞；`parse_response()` 归一化 what_i_see（list[str]，缺失/畸形→[] 不崩溃）；`sanitize_strategy` 透传 what_i_see；`consult()` 将读出内容嵌入 advice（"👁 屏幕: …"）并随 strategy 写入 active_strategy.json
- `plugin/strategy_writer.py`：write_strategy/write_advice 新增 what_i_see 参数，落盘 coach_advice.json 顶层+history 条目
- 面板效果：教练面板 advice 文本现含 "👁 屏幕: …" 行——操作员可验证 GLM 是否真在看屏幕

**回归**：新增 TestWhatISee 6 用例（prompt 指令/解析保留/缺失与畸形降级/sanitize 透传/consult 嵌入/双文件落盘）；test_plugin_mhr 41/41；全量 478 passed / 11 基线失败零新增。

**版本**：Brain 2.13.1→**2.13.2**（SKILL 3.0.0 镜像不变）。WSL 实测见部署记录（coach_advice.json 含 what_i_see 实证）。

---

## 2026-09-14: t20 阈值下调 — Brain v2.13.1（教练咨询阈值 120s→60s）

**变更**：`plugin/runner.py` `STUCK_HELP_THRESHOLD` 120.0→**60.0**（service.py 无同常量，经 PluginRunner 复用），GLM 顾问在卡住 60s 后即介入而非 120s；runner 文档字符串同步。

**回归**：`test_stuck_threshold_boundary` 更新为 59/61 边界 + 新增 `test_stuck_help_threshold_60_contract`（70s→consult、50s→不触发、110s[旧 120s 界内]→consult）；test_plugin_mhr 35/35；全量 472 passed / 11 failed 均为基线既有（bridge/invariants/retina/版本文档已同步修复）。

**版本**：Brain 2.13.0→**2.13.1**；skills.md 当前版本行同步。

---

## 2026-09-14: EVO Round 20 启动 — 空间导航回路（CX 升级，核心能力）

**触发**：监控分析确认马里奥"运动中转圈"的行为本质——**270° 复眼已全向采样，运动策略却在用物理旋转采集已有信息**（无效动作）。机制根因：CX 环吸引子罗盘是外部航向副本（无自运动积分）、零路径积分（无"我在锚点系哪里"表征）、目标向量单源（novelty 枯竭→方向感归零）。

**任务清单**（README「空间导航回路」待办同步勾选）：
- CX-1 罗盘自主化：转向池放电差→角速度→bump 自主滚动 + hue_az 天空方位软校正 + 外部 heading 降级弱校正
- CX-2 锚点路径积分：场景锚定→位移向量积分→距锚距离/方向角
- CX-3 多源目标向量竞争：novelty+覆盖空隙质心+反失败格+锚点返回→向量和→目标列

能力边界：全部为 CX 内神经状态/电流（自运动积分、向量加法竞争），转向执行走既有 turn 池通路，零 Python 控制判断。版本随各部分递增（CX-1→2.13.0 / CX-2→2.14.0 / CX-3→2.15.0），README 待办逐项勾选。

---

## 2026-09-14: t19 结构修复一 — Brain v2.12.1（seqlock 停更看门狗：SM64 冻结检测 + 仪表板告警）

**触发**：SM64 被宿主 shell 连带 kill 后共享内存桥停更，但脑继续 tick、监控面板视觉画布静默冻结——SM64 存活无监护。

**修复**：
- `bridge.py` 新增 `SeqlockWatchdog`（纯逻辑类，无 mmap 依赖可单测）：每次 `read_frame` 喂入帧 seq，**同一 even seq 停滞 >5s → `bridge.stale=True`**；seq 前进即复位（单调性防误报）；撕裂读（3 次校验失败）也喂入 last seq 让停滞累计
- `main.py` flow.json 透出 `bridge_stale` 字段
- 仪表板 header 状态栏新增红色脉冲徽章 **SM64⛔ FROZEN**（`.stale-pill` + stalePulse 动画），条件 `flow.bridge_stale`
- 可选 auto-restart 未做（按任务书先检测与展示；restart 契约已由 t18 consolidate.sh 固化）

**版本**：Brain 2.12.0→**2.12.1**（SKILL 3.0.0 镜像不变）。

**回归**：新增 `tests/test_seqlock_watchdog.py` 9 用例（新鲜帧不误报/4.9s 临界不触发/5.1s 触发/单调推进 2000 帧零误报/撕裂读累计/seq 复位恢复/bridge·main·dashboard 三处接线）；9/9 通过；py_compile 通过；test_bridge 2 失败为已知 Windows 环境基线。部署后 WSL 实测双态：SM64 存活 stale=false；`kill -STOP` 冻结游戏 >5s 后 stale=true、恢复 CONT 后复位。

---

## 2026-09-14: t18 结构修复二 — 启动契约固化（consolidate.sh + 文档，纯文档/脚本）

**触发**：SM64 与大脑曾两次作为托管后台 job（pwsh `run_in_background` / agent 后台 job）的前台子进程被连带 kill → 共享内存桥冻结 → 仪表板显示卡死。属结构性知识缺口，需固化防复发。

**变更（零 .py 代码）**：
- `fly64/scripts/consolidate.sh`：头部新增「启动契约」注释块（大脑/SM64 规范 setsid nohup 命令 + 托管 job 跑路风险明示）；大脑与 autonomy 服务的实际启动行升级为 `setsid nohup … < /dev/null &`
- `agent.md` 运行状态章节新增「启动契约（强制）」：大脑与 SM64 必须 setsid 脱离宿主 shell，禁止托管后台 job 直接启动
- `fly64/README.md` 手动启动章节补充同样的契约警示

**回归**：bash -n consolidate.sh 语法通过；无 .py 改动，测试套件不受影响。

## 2026-09-14: EVO Round 19 — Brain v2.12.0（躁动电流 + 识别→行为闭环 + 遥测小补）

**触发**：监控实况——马里奥在识别为"致命熔岩地"的悬崖边驻留 61s（escape 级联、novelty 0.001、loop 0.97），识别结果未驱动行为、静息状态下突破电流失效（TurnAdaptation 只响应转弯，静息凝视时疲劳衰减→breakout→0）。

**变更（全神经注入，零 Python 控制判断）**：
- `model.py` `restlessness_level()`：对峙时间/环路压力累积为 **forward 躁动电流**（standoff/30s 与 (loop−0.8)×5 取最大封顶 1.0；对应"逃逸动机随困留时间累积"）；step 内 spike 前注入 forward 池 ×0.12
- `scene_recognition.py` `danger_level()` + `model.scene_danger` 镜像：识别 tags 含 danger/lava/hell → forward 谨慎抑制 −0.06——**识别从命名变为功能**（识别→行为闭环）
- `main.py`：镜像 `loop_score`/`scene_danger`；flow.json 补 `fg_fraction/mb_weight_std/mb_saturation_events`（OPT-4）
- 版本：Brain → **2.12.0**

**PIN**：`tests/test_restlessness.py` 6 用例（对峙满值/环路压力/静息为零/danger 识别/良性不触发/forward 抑制量），6/6；全量 398 passed、5 failed 均为既有问题。

---

## 2026-09-14: EVO Round 18 — Brain v2.11.x（DAN 信号塑形：奖励权重常量化 + 探索奖励 0.50→0.30 压低 MBON 饱和平衡点）

**触发**：R17 部署后实测 `mb_mbon_forward=1.0`——正多巴胺再膨胀与稳态缩放的平衡点停留在 tanh 天花板。探索奖励 0.5 的持续 +DA 是膨胀主因。

**变更（DAN 信号塑形，一处可调）**：`model.py` 新增类级 `DAN_*` 常量（探索 0.50→**0.30** / 前进 0.30 / fallen 0.80 / cliff 0.40 / looming 0.30 / revisit 0.20 / 环行态 0.35 / 对峙 0.45），`_compute_dopamine` 全部改引常量——DAN 权重单点调参，检测逻辑零改动。

**验证**：实测 mb_dopamine=0.3032（塑形后奖励生效）；`tests/test_dan_shaping.py` 5/5（探索奖励=0.30/常量单点/低 DA 驱动下 MBON 膨胀减弱对比）；全量 391 passed。

---

## 2026-09-14: EVO Round 17 — Brain v2.11.0（MBON 饱和稳态缩放 + breakout_hint 反射移相 + mbon_saturation 模式）

**触发**：R16 部署后健康检查发现：① `mb_mbon_forward=1.0` 饱和（正多巴胺持续再膨胀，forward 关联过拟合）；② anomaly_reflex 级联改写 control 使脑内 breakout 突破电流无法体现（heading 恒 ±29.45°/s 回归）。

**能力边界判定**：
- ✅ 稳态突触缩放 → 纯神经机制（/postsynaptic scaling），MBON 柱自缩回动态范围
- ✅ breakout_hint → 反射层感知门控（脑的编织检测信号调制反射相位预算），反射保留所有权、决策不移 Python
- ✅ `mbon_saturation` 模式 → 填补"饱和持续"检测盲区

**变更**：
- `mushroom_body.py`：`_saturation_frames`/`saturation_events`/`saturation_frames_threshold=50`/`scale_factor=0.9`——|MBON|≥0.98 持续 50 帧 → 该柱活跃突触 ×0.9（encode 内自动）
- `memory.py` ReflexController：`breakout_hint` 参数（0-1）→ `_breakout_scale`——micro_loop 转向相位 ÷scale（最短 0.15s）、前进取余；hint 来自脑的 TurnAdaptation 归一化 breakout 电平
- `main.py`：反射调用点传入 breakout_hint；`skills/default_patterns.json`+`DEFAULT_PATTERNS` 新增 `mbon_saturation`
- 测试：`tests/test_mbon_saturation.py` 6 用例（饱和缩放触发/事件计数/动态范围回归/原始相位预算保持/hint 满偏缩短转向相/交替涌现）

**PIN**：`test_mbon_saturation` 6/6 + 全量 384 passed 零新增失败。R17 部署后 dashboards 可观测：`mb_mbon_*` 饱和时 homeostatic scaling 自动收缩、反射转向相位在脑报告编织时自动缩短。

---

## 2026-09-14: t16 监控界面优化轮 — Brain v2.10.1（P0+P1 可见性与布局 + P2 首项）

**触发**：t15 监控界面布局分析（纯分析）发现的 P0 可见性缺口与 P1 层级问题。

**变更**：
- **P0-1/P1-1**：状态 pill 条（brainVer/evoIter/health/anomaly/help/llmDecision）整体迁移至 header 全局状态栏；llmDecision 等待态显示倒计时 `Xs / 600s`，title 带原因与超时策略
- **P0-2**：新增 `/active_strategy.json` HTTP 端点（读 skills/active_strategy.json）+ "Coach Strategy Consumption" 折叠面板——展示 bold_explore_stuck_s / turn_bias / stuck_threshold_s 当前值（含单位与方向提示）、dialogue_decision、最后写入时间与来源，补齐教练建议→生效闭环可视
- **P0-3**：因果链 PRIORITY 增加 dialogue=5，judgeText 对话分支——暂停期显示 `⏸ DIALOGUE PAUSED · awaiting coach decision (Xs/600s)`，已决策显示动作；不再误报 neutral steering
- **P0-4**：memory note-stats 新增 forced_bold_explore（🏃 BOLD breakout）/ reflex_ineffective（⚠）徽章
- **P1-2**：scene 行新增 terrain / underwater / interactive_near chip
- **P1-3**：help / coach 面板折叠为 `<details class="fold-panel">`
- **P1-4**：新增 `@media(max-width:800px)` 单列断点（main 改 block、区纵向堆叠、pill 条换行前置）
- **P2-1**：flow.json 双定时器重复拉取合并为共享 `fetchFlowOnce()`（updateSceneDisplay/updateEvolutionDisplay 共用 latestFlow）

**版本**：Brain 2.10.0→**2.10.1**（SKILL 3.0.0 镜像不变）；check_version.py 通过。

**回归与部署**：py_compile main.py、node --check dashboard.js、test_dashboard_js+test_dashboard_protocol 8/8 通过；commit 5a7a845 push；WSL 同步后重启大脑，人工核验清单（curl 级）：各静态端点 200、flow.json llm_decision/terrain 字段在位、/active_strategy.json 返回 coach 三键——详见 t16 任务输出。

---

## 2026-09-14: EVO Round 16 — Brain v2.10.0（震荡突破电流 + skill 层复明 + 常驻 EVO 循环）

**触发**：缺陷审计（R15 后）：① TurnAdaptation 交替把"恒向转圈"变为"原地编织"——loop_score 仍饱和 1.0，缺 forward 突破机制；② flow.json 缺 5 个因果键（decision_source/cliff_conf/gate_forward/hrc_asymmetry/emd_on_total）→ EvolutionSkill 新检测模式永不命中（0/876 因果行可分析）；③ DiagnosisEngine 对缺失字段静默跳过。

**变更（脑优先，零新 Python 控制判断）**：
- `model.py` TurnAdaptation：新增 `breakout_drive()`——双侧转向回路同时疲劳（原地编织特征）→ forward 池突破电流（gain 0.15）+ 双侧 turn 池轻度抑制；step 内 spike 前注入
- `main.py` flow_json：新增 `decision_source/cliff_conf/gate_forward/gate_jump/hrc_asymmetry/emd_on_total/emd_off_total/mb_dopamine/mb_mbon_forward/mb_mbon_jump`（skill 层复明 + MB 可观测）
- `evolution_skill.py`：SensorSample 新增 `loop_score` 字段并接入 get_metrics；`micro_loop_weave` 新模式（micro_loop + loop≥0.8 + stuck>60 → 加大 breakout_gain）；`DiagnosisEngine.evaluate` 显式 **telemetry_gap** finding（缺失条件字段不再静默跳过）；`--max-iterations 0` = 常驻模式
- `main.py` `_scene_name`：未匹配场景计入 `note_unknown_scene`（C3 在线聚类种子）
- `scene_recognition.py`：`adapt_enabled/adapt_lr/note_unknown_scene`——识别命中且 conf≥0.6 时画像 P50 以 η=0.01 向实测漂移（P2-C1 在线校准），P05/P95 护栏随中心平移

**PIN**：`tests/test_brain_alternation.py` 9/9（含 alternation 涌现）、`test_cliff_standoff.py` 8/8、`test_spin_loop_fix.py` 7/7；全量 384 passed / 5 failed 均为既有问题，**零新增失败**。

**常驻闭环**：WSL 常驻 `evolution_skill --auto-fix --max-iterations 0`（`/tmp/evo.log`）——Fix/Verify 阶段首次真实参与在线闭环。

---

## 2026-09-14: t13 修复轮 — Brain v2.9.1（LLM Coach Advice 生效性：死键接线 + 触发放宽 + prompt 语义卡 + HTTP 400 根修）

**触发**：本轮分析确认 Coach Advice"说了就算"承诺四处断点——GLM 建议四个环节中三个不生效。

**四项根因与修复**：
1. **死键接线**：`memory_ctrl.bold_turn_bias`（main.py 热重载写入）无任何消费者。修复：接入 `model.bold_turn_drive` 转向池电流幅度——单位换算 `|bias|/69`（兼容 legacy ±69 角度制与 coach 0-1 强度制），钳位 **[0.2, 1.0]**（0.2 下限防 coach-0 死锁突围），模型侧按 `0.35×|drive|` 注入脉冲前电流，LIF 竞争执行方向。
2. **触发链放宽**：`bold_explore_stuck_s` 原仅对 `anomaly_state=="micro_loop"` 生效（memory.py）。修复：新增 `persistent_anomaly_stuck`——**任意持续异常**（anomaly.active 且 dur 超阈值）均触发突围；micro_loop 原语义保留。
3. **prompt 语义卡**：`PROMPT_TEMPLATE` 增加策略参数语义说明（bold_explore_stuck_s=秒，越小越快突围；turn_bias=0-1 转向强度，禁止填 69 类角度值；stuck_threshold_s=秒，越小越快逃逸），杜绝 LLM 反向调参。
4. **HTTP 400 根修**：根因是 main.py `frame_to_b64` 上送的是**裸 RGB 字节**，而请求体标注 `data:image/png` ——GLM 解码失败回 400。修复：`llm_consult.raw_rgb_b64_to_png_b64()` 纯 stdlib（zlib+struct）PNG 编码器，`build_consult_request` 内自动转换（非 384×256×3 裸帧原样透传）；`_dispatch_http` 捕获 HTTPError 并透出 API 错误体（原裸"HTTP 400"掩盖根因一轮）。

**版本**：Brain 2.9.0→**2.9.1**（SKILL 3.0.0 镜像不变）；skills.md 当前版本行同步。

**回归**：新增 `TestCoachAdviceEffectiveness` 6 用例（PNG 转换 magic/IEND、非裸帧透传、请求体 PNG 化、语义卡三键+单位+方向、turn_bias 消费点+钳位、触发放宽+micro_loop 保留）；py_compile 4 模块 OK；全量 403 passed / 23 failed（与基线一致，零新增，含 R14 在途轮既有失败）。

---

## 2026-09-14: EVO Round 15 — Brain v2.9.0（悬崖对峙修复：FailureMemory 切向电流 + DAN 强化 + cliff_standoff 模式）

**触发**：R14 自发交替消除持续转圈后，暴露下一层问题——**悬崖边缘对峙驻留**：terrain=cliff + cliff_confirmed + escape=True + loop_score=1.0（窗口全重访），马里奥停在已知坠崖边界。EvolutionSkill Findings=0（无对应模式）。

**能力边界判定**：三项修复全部为**感知/学习**性质（standoff 计时=感觉、切向符号选择=novelty 择优感知、DAN=误差信号），转向执行仍由 LIF 竞争决定——零 Python 控制判断新增。

**变更**：
- `memory.py` FailureMemory：`nearest_failure_vector(x,z,radius)`（半径内最近失败格单位向量）
- `memory.py` MemoryController：`_cliff_standoff_s` 计时（cliff_detected 确认 + escape）、`cliff_standoff_s` 属性、`cliff_tangent_bias(x,z,heading)`（FailureMemory 失败格→±90° 切向候选→novelty 择优→±1 感知符号；平局确定性取 +1）
- `model.py`：镜像字段 + step 内**切向电流注入**（confirmed cliff 且 bias≠0 → turn 池 ±0.15 + forward −0.08，spike 前）+ `_compute_dopamine` 对峙>20s → 惩罚 0.45（DAN→MB 学习"该场景+前进→坏"）+ reset_scene 清零
- `main.py`：镜像 standoff/tangent + flow.json 暴露 `danger_red_index/sky_blue_index/emd_on_down/target_count/mb_assoc_count/cliff_standoff_s`
- `evolution_skill.py`：SensorSample 新增 `cliff_standoff_s/danger_red_index/emd_on_down/target_count/assoc_count` + DEFAULT_PATTERNS 新增 `cliff_standoff`；`default_patterns.json` 同步
- 测试修缮：`test_mushroom_body` 种子化去 flaky；`test_preemptive_avoidance_order` 对齐 audit A1 删除语义；`skills.md` 版本 3.0.0

**PIN**：`tests/test_cliff_standoff.py` 9 用例（对峙累积/清零/无失败格=0/正对=±1/背后=0/fresh 择优/DAN 惩罚/无对峙不罚/模式入目录），9/9；全量 361 passed、14 failed 均为既有问题，**零新增失败**。

**教训**：`cliff.update` 返回 dict 的确认标志是 `cliff_detected`（无 `cliff_confirmed` 键）——用错键使 standoff 恒 0，是首轮调试的主要根因。

---

## 2026-09-14: P1 进化轮 — Brain v2.8.0（去 Python 化：删除 11 个 A 类旁路点，行为决策回归 LIF 网络）

**触发**：脑模型替代判断分支审计轮（t7 审计 + t8 逐项核实）。根因=**双轨旁路**：main.py 在 LIF 解码后直接改写 control（~35 处）、model.py 解码后符号调制绕过池竞争——五大神经基质（HRC/LC4、反射四电路、CX 环吸引子、MB、多巴胺增益）均已在但被旁路。

**变更清单（按 t8 修正行号执行）**：
- A1 main.py（原 893-904）：运动不对称>0.3 强转 / looming>0.4 减速的 Python 覆盖删除——model 电流注入路径已实现同源调制
- A2 model.py（原 1387-1389）：flow_cliff<0.3 随机 ±40 转向删除——崖壁避让归 main 崖壁反射（cliff_confirmed 路径保留），LC4 注入列入 P3
- A3 main.py（原 918-1023）：逃逸五阶段硬编码状态机（escape_toggle_timer/escape_x/0.4-2.5s 定时器）删除。接管路径：model.escape_mode 逃逸电流注入（已验证注入 model.py escape_mode 块无死区）+ 反射四电路（先于逃逸写 control）+ CX opening 转向。新增两根系：`escape_jump_drive`（fallen→jump 池 +0.45）与 `bold_turn_drive`（forced_bold→镜像交替转向池电流 ±0.35，方向由 ReflexController.bold_direction() 自发交替记忆给出）
- A4 main.py（原 1000-1006）：novelty_bias>0.2 转向分支删除——CX.update(novelty_direction) 目标导航接管
- A5 main.py（原 874-882）：health<0.3 的 control.x×1.5 增幅删除——保留 set_aggressive_mode 神经调质（冷却减半），紧迫性归增益通路
- A6 main.py（原 906-909）：场景突变抑制逃逸分支删除——stuck 检测器自身滞回把关，MB 学习门控列入 P4
- A7 main.py（原 715-724+1114-1121）：corollary-discharge 帧计数器与 un-corner 覆盖删除——楔入几何逃逸归反射电路；位移数据通路备注保留供 P3 递归神经元
- A8 main.py（原 1159-1163）+ model.py（原 1313-1323）：legacy 脉冲-A 与 model 对话脉冲块双删——对话行为归 LLM 暂停等待编排（BRAIN 2.4.0 契约）+ 习惯化安全护栏
- A9 memory.py（原 492-501）：novelty_direction 8 方向网格离散化（±0.3 死区）→ 连续 heading→最近格映射，CX 输入成为连续群体向量
- B10 model.py（原 1111）：novelty 增益分段阈值 → 平滑 sigmoid `1+0.10*tanh((0.5-n)*4)`（同 ±0.10 值域，消除断点）
- C10 retina.py（原 1124）：enclosure 0.35 单一魔数拆分为 SENSORY/OVERRIDE 两常数（同值，行为不变，感知/行为可独立调参）

**连带清理**：decision_source 归因级联移除 bold_explore/collision 分支；escape_toggle_timer/escape_x/_cmd_fail_frames 变量全删；command_decoupled 遥测键保留（恒 False，兼容面板）。

**版本**：Brain 2.7.0→**2.8.0**（SKILL_VERSION 3.0.0 不变，evolution_skill.py 本轮未动，镜像一致，check_version.py 通过）

**回归**：py_compile 4 模块通过；全量 tests（除 live 测试）25 failed / 355 passed —— 25 项失败与 HEAD 基线（git worktree 对照）**逐项一致，零新增失败**。

**KPI 基线口径**：main.py 直接写 control 点数 35→**约 12**（剩：崖壁反射、反射动作写回、对话暂停/习惯化护栏、LLM 按键执行）；行为级 Python 分支随 P2-P4 继续收敛。

---

## 2026-09-14: EVO R11 完成轮 — 教练策略键接入行为管线（commit f0d86f7）

**变更**：coach 下发的策略键真正被行为管线消费——`bold_explore_stuck_s` → micro_loop 突破阈值、`turn_bias` → bold 转向幅度、`escape.stuck_threshold_s` → memory.py 时长型教练逃脱条件（经 main.py 热重载推送）；skills.md 记录 Brain 2.6.1 / Skill 2.9.1 当前版本；并发更新后复验 R11 接线完好（opening injection / report_movement / bold_override 均在场）。

---

## 2026-09-14: LLM 教练链路 T1/T2/T3（commit 8ec44b2）

- **T1**：dialogue consult 携带实时上下文（原为空 `{}`）；local_diagnosis 产出可执行建议（bold 占空比、零位移 90° 转向、室内 cliff 脱敏）
- **T2**：GLM http 传输经 root-only `plugin/llm.env` 配置（consolidate.sh source，永不入库），实测 GLM-5.3-flash 返回可执行 coach 建议+策略
- **T3**：subagent 文件握手并发应答者验证（过期响应 unlink 拒绝为设计行为）；`.gitignore` 加入 `llm.env`

---

## 2026-09-14: MHR 插件 LLM 按键决策 + main.py 对话暂停等待模式（commit 1d00cac，Brain 2.4.0，团队 fly64-mhr-llm-button t1-t4 全通过）

**功能**：对话出现→暂停大脑→worker 线程截屏→GLM `consult_dialogue(frame_b64)` 决策（上限 600s）→执行 press_a/press_b/none；超时/异常双保险回退自主按 A。

**变更**：
- `plugin/llm_consult.py`：`consult_dialogue()` → `{"action","reason"}`，6 类非法输出安全降级 none；`plugin/strategy_writer.py`：`write_dialogue_decision()` 原子合并 `dialogue_decision`
- `main.py`：对话分支暂停等待状态机（episode 一次性消费、12 tick 按键保持、600s belt-and-braces 强制 A）；`/flow.json` 新增 `llm_decision{status,action,reason,episode,wait_s}`
- `bridge.py`/`model.py`：B 键传输 `B_BUTTON=0x4000`（模拟器未识别时优雅降级）；web 面板 `llmDecisionPill` 三态显示
- **测试**：`test_plugin_mhr.py` 28 + `test_dialogue_llm_decision.py` 31（解析/超时回退/原子写/状态机/telemetry 全覆盖，离线 mock）；t3 审查 pass + t4 独立复核 pass（59/59 复跑）

---

## 2026-09-14: EVO Round 13 — Brain v2.6.1（转圈死循环修复：进度门控 + 镜像交替 + loop_score 感官卫生）

**触发**：马里奥 stuck=1063s / anomaly=micro_loop conf=1.0 持续 973s / heading 29.5°/s 持续转向 / loop_score 病态值 104.976。EvolutionSkill Findings=0（模式目录盲区）+ neural_viz 因果字段缺失（0/876 行），由人工遥测快照定位根因。

**根因（自增强反射风暴）**：EVO R6 自适应冷却 `max(0.25, 1-stuck/120)` 在 stuck>90s 后触底 0.25s → micro_loop 反射每 ~0.3s 重触发 → 转向爆发无前进时间窗 → 原地绕圈 → stuck 永不复位 ♻️

**能力边界判定（本能不外包原则）**：
- ✅ 进度门控 + 镜像交替 → 反射回路内部修缮（等价生物不应期 + 自发性交替），归果蝇能力群
- ✅ loop_score 精确计数 → 感官卫生（喂给脑的输入正确性），归神经元侧
- ✅ 破环方向由反射/LIF 执行，Python 仅做感知门控（传入 pose）——未新增非脑控制层
- ❌ 拒绝方案：Python 计算上坡方向强制 control.x/y（教官层式干预下沉，违反分层原则）

**变更**：
- `memory.py` SpatialMemoryMap.update：loop_score 精确滚动窗口计数（窗口驱逐递减 `_revisit_count` + `_window_counts`/`_window_flags` 辅助结构，修复 104.9 → [0,1]）
- `memory.py` ReflexController：新增 `_last_fire_pos`/`_last_direction`/`progress_radius=30u`——micro_loop 重触发时若位移<30u 则**镜像翻转转向**（自发性交替），有进展则保持随机；`update()`/`_start_reflex()` 新增 `pos` 感知参数
- `main.py`：反射调用点传入 pose(x,z)
- 版本：Brain 2.6.0→**2.6.1**，Skill 2.9.0→**2.9.1**

**PIN**：`tests/test_spin_loop_fix.py` 7 用例（loop_score 有界/纯重访=1.0/界内新探索=0/无移动镜像/连续交替/有进展重随机/首触发随机），7/7 通过；全量回归 313 passed、16 failed 均为既有问题（15 Windows 兼容 + 1 过期版本断言），**零新增失败**。

**待办（本轮发现的检测盲区）**：
- 新增进化模式 `slope_micro_loop`（micro_loop + ramp>0.5 + visited>50 → 上坡方向偏置修复）
- neural_viz 因果字段在部署链路缺失（WS 876 行均无 decision_source）——排查 telemetry.py 部署同步

---

## 2026-09-14: 清理轮 — 版本线收敛 2.6.1 + WSL 目录结构修复 + F1-F4 遗留项

**说明**：任务书原定"收敛到 2.5.0（以 WSL 为准）"，执行时双侧（Windows 工作区与 WSL /root/fly64）均已演进至 **2.6.1**（EVO R13 转圈修复），遂按超集收敛于 2.6.1，不做版本回退。

**变更**：
- **F2' 版本收敛**：Windows `fly64/main.py` BRAIN_VERSION 2.6.1 = WSL 2.6.1（含 EVO R13 spin-loop 修复一并 commit），check_version.py 通过
- **WSL `~/fly64/fly64/plugin/` 恢复**：此前 rsync `--delete`（排除规则只写 `.venv` 未写 `venv`/`__pycache__`）误删包内容仅剩 `__pycache__`；已从顶层 `/root/fly64/plugin/` 回填 `__init__.py / llm_consult.py / manifest.json / runner.py / strategy_writer.py / service.py / watchdog.sh` 并清 `__pycache__`；`python -c "import fly64.plugin.runner"` 验证通过（两种布局并存：顶层 `plugin.*` 供大脑 sys.path 导入，内层 `fly64.plugin.*` 供 `python3 -m fly64.plugin.runner`）
- **F3**：`tests/test_dialogue_llm_decision.py` + 更新后的 `test_plugin_mhr.py` 同步至 WSL tests/
- **F1**：WSL venv 补装 scipy 1.15.3
- **版本断言前向化**：`test_plugin_mhr.py` 与 `test_dialogue_llm_decision.py` 中 `BRAIN_VERSION == "2.4.0"` 硬编码改为 ≥[2,4,0] 前向兼容断言（版本线只前进）
- **WSL 测试**：venv pytest test_plugin_mhr.py + test_dialogue_llm_decision.py **59/59 通过**；Windows 侧 66/66（+spin_loop 7）

**F4 结论（WSL git 化评估：不 git init）**：`/root/fly64` 是部署目标而非源码权威——含 venv、artifacts、runtime 状态、service 日志/pid 与 root-only 秘密 `plugin/llm.env`（git 化需精细 .gitignore 且有泄密风险），且唯一事实源已在 Windows `D:\codes\flygym`（git 管理）。维护方式维持：Windows commit → rsync 增量同步（**禁用 --delete**，或排除规则必须同时覆盖 `venv`、`__pycache__`、`runtime`、`artifacts`、`plugin/llm.env`）→ WSL 重启大脑。

**部署证据**：大脑重启（setsid 常驻，PID 见本轮报告），flow.json brain_version=2.6.1、tick 持续递增。

---

## 2026-09-14: EVO Round 12 — Brain v2.6.0（自治基底落成：WSL 常驻自治服务 + 存活监控，自治不依赖 DSH 会话）

**背景**：AgentTeams 团队 autonomy-substrate 落地推荐架构 A——果蝇自身能力群自治 + 教官层（LLM/DSH）按需介入的分层原则。此前 10s 循环（plugin/runner.py）依赖 DSH 会话驱动，会话结束即停。

**变更**（AUTONOMY）：
- `plugin/service.py`（新）：常驻服务入口。10s 循环包装 PluginRunner；每周期健康自检（仪表板可达 / 桥接 mtime≤60s 新鲜度 / 策略文件写出确认）写入 `plugin/service_status.json` 心跳，连续失败≥5 输出 ALERT；LLM 咨询双传输——http（`FLY64_LLM_*` 环境变量，无需 DSH）与 subagent 文件握手（依赖 DSH 会话，120s 硬超时）；ConsultError 降级 `local_diagnosis` 本地诊断写 coach_advice.json，自治永不因 LLM 不可用而停摆
- `plugin/watchdog.sh`（新）：存活监控。pid 检测自动重启（venv 可 import 才用 venv，与 consolidate.sh 同策略）；连续≥3 次启动失败写 watchdog.log ALERT 求教官介入。支持 cron `* * * * *` 或 systemd timer 驱动（部署见 `plugin/DEPLOY_AUTONOMY.md`）
- `scripts/consolidate.sh`（制度化）：重启脑模型时连带重启自治循环（先 kill 旧 pid 再拉起 `plugin.service`），自治视角永不落后于脑重启
- **PIN**：`tests/test_service.py`（10 用例：健康自检/降级咨询/失败计数/心跳落盘）+ `tests/test_autonomy_regression.py`（13 用例：VERSION 三处同步契约 / StrategyWriter 原子写出[无 .tmp 残留/重复写始终可解析/历史上限] / watchdog 沙箱[死亡重启/连续失败 ALERT/健康不扰] / consolidate 联动契约 / run_forever ≥3 周期有界循环），23 用例全绿
- VERSION：BRAIN_VERSION 2.5.0→**2.6.0**；SKILL_VERSION 2.8.0→**2.9.0**（check_version 镜像一致；skills.md 轮次表 +12）
- 修复 t1 遗留：plugin 脚本 CRLF 行尾（WSL bash `set -o pipefail` 报错根因），统一转 LF

**回归基线对照**：全量 334 用例 320 过 / 14 失败。将本轮版本改动 revert 后重跑失败子集，14 个失败逐一复现——全部为既存基线失败（memory/optic_flow/invariants/evolution_capability R10/plugin_mhr 版本断言过期等），**本轮零新增失败**。

**CONSOLIDATE**：同步 WSL /root/fly64 → `consolidate.sh` 智能重启（检测到游戏 pid FULL 模式接 /tmp/f64b_traj）→ `brain_version=2.6.0` 仪表板在线 + 自治服务重启（nohup 模式，pid 见 `plugin/fly64-service.pid`）。实测常驻存活 **120s+ 连续 25+ 循环周期**（status=ok，consecutive_failures=0）；watchdog 沙箱验证死亡重启/连续失败 ALERT/健康不扰；live 写出验证：subagent 握手咨询 → `skills/active_strategy.json` + `skills/coach_advice.json` 原子写出成功（`tests/_live_writeout_probe.py`）。注意：`pgrep -af fly64` 匹配不到自治服务（cmdline 为 `python3 -m plugin.service`），请用 `pgrep -af plugin.service` 或 pid 文件。

**遗留发现（转下轮修复建议）**：① consolidate.sh 拉起自治服务未传 `--bridge-path "$BRIDGE"`，服务健康自检监控默认 /tmp/f64b 而实际游戏桥为 /tmp/f64b_traj → bridge 新鲜度误报 stale；② HealthChecker.check_dashboard 对返回 `{}` 的 /evolution.json 显示 ok/detail 不一致（`{}` 非 None 记 ok=True 但 detail=unreachable），detail 判据建议改 `bool(data)`。

**二期待评估**：薄 Cordis Tool 层（fly64_status / fly64_consult / fly64_strategy 动态 Tool）。

---
## 2026-09-14: EVO Round 11 — Brain v2.5.0（神经化重构：电流注入 + 位移奖励，规则做减法）

**背景**：转圈修复评审指出 R10/R11 早期提案仍在堆叠符号判断分支。参照 MaleCNS-TrackMania 方案（视叶算流、蘑菇体学价值、DN 出命令，无 if/else）重构为神经化方案。

**变更**（LEARN，"判断"降维为"电流"）：
- `retina.py`：新增方向性开口信号 `opening_left/right/asymmetry`（外侧方位带 az0,1/az6,7 相对中央变暗 = 该侧有开口；正值=开口在左）
- `model.py`：① escape 期间开口不对称 → 转向池**电流注入**（`v[turn_left/right] += _open_inj`），LIF 左右竞争决策突围方向，取代 escape_x 随机；② 新增 `report_movement(displacement)` API——main.py 每 2.4s 窗口测净位移喂入，零位移=多巴胺惩罚，蘑菇体 KC→MBON 学到"该情境面朝墙无价值"（网络自己停止撞墙）；③ **退役**低置信悬崖符号转向分支（`x*1.5 / y-20`，转圈主贡献者）
- BRAIN_VERSION 2.4.0→2.5.0；SKILL_VERSION 2.7.0→2.8.0

**PIN**：4 新用例（开口注入接线/位移奖励 API/分支退役/归因顺序），46 全绿（capability+protocol+js）；retina 2 tmp_path 沙箱既存失败。

**CONSOLIDATE（两次实战修正 consolidate.sh）**：①进程清理模式改为 `[f]ly64.main`（任意解释器）+ pkill -9 兜底；②游戏检测遍历 us_pc 进程读 FLY64_BRIDGE env（修复抓到 bash 包装进程导致桥错位）。最终实测：`brain_version=2.5.0`、`frame_age 60ms`、`decision_source: steering` ✅。

---

## 2026-09-13: EVO Round 10 — Brain v2.3.0（局部突围机制 local_breakout）

**触发**：转圈分析发现 497.9s micro_loop 事件位移 0u。根因：forced_bold_explore 突围门控用**全局** visited_cells<20（已 400 格，永不触发）——检测用局部窗口、解药却用全局计数器，制度性死锁。

**变更**（LEARN）：
- `memory.py`：突围门控新增 `micro_loop 异常持续>60s` 条件（`_latest_anomaly_state/_latest_anomaly_dur` 透传）
- `main.py`：①bold 期间覆盖活跃反射（`not reflex_override or bold_override`——micro_loop 反射本身就是转圈，覆盖才能突围）；②低置信悬崖转向分支加 `not forced_bold_explore` 门控（转圈主贡献者）；③decision_source 新增 `bold_explore`（优先于 anomaly_reflex）
- BRAIN_VERSION 2.2.0→2.3.0；SKILL_VERSION 2.6.0→2.7.0

**PIN**：test_evolution_capability.py 新增 4 用例（突围门控含 micro_loop 持久条件/原路径保留、bold 覆盖反射、悬崖分支门控、独立归因通道），31→35 用例全绿（含修复 re 未导入）。

**CONSOLIDATE**：consolidate.sh 自动检测到**新游戏实例**（PID 10539，桥 /tmp/f64b_traj）→ 正确接新桥 → `brain_version=2.3.0` 在线。智能重启在游戏桥变化场景下再次验证有效。

---

## 2026-09-13: EVO Round 9 — Brain v2.2.0（室内围闭度检测 + 天空蓝色度门控）

**触发**：实测在建筑物内（蓝地毯/深色格纹天花板/立柱）场景被识别为"天空·山坡"。根因：sky_score 仅测上视野亮度（天花板灯/亮格纹误判为天空 0.46-0.82），ramp_score 把墙面明暗渐变当斜坡（0.41），classify_terrain 无室内类别。

**变更**（LEARN）：
- `retina.py` compute_flow 新增 `enclosure_score`（围闭度 = 0.6×天花板信号[(1-蓝色度)×上视野结构边缘×8] + 0.4×墙边缘[|edge_90|+|edge_0|]×3）与 `upper_blue`（上视野蓝色主导度）；sky_score 乘蓝色门控 `min(1, upper_blue×4)`；`enclosure>0.35` 时 terrain 覆盖为 `indoor`
- `model.py` 透传 `enclosure_score`；`main.py` 场景名新增"室内"标签（优先级最高）+ flow.json 两处新增字段；`telemetry.py` 每 tick 行携带 `enclosure_score`
- BRAIN_VERSION 2.1.0→2.2.0；SKILL_VERSION 2.5.0→2.6.0

**PIN**：test_retina.py 新增 3 用例（室内/室外合成场景 enclosure 分离、indoor terrain 标签+sky 抑制、加法键），全绿；修复 _hv_pair_ab 数组拼接 bug（int32 数组误用 +）；dashboard/evolution 套件 35 全绿；memory 8 失败既存。

**CONSOLIDATE**：首次使用制度化的 `scripts/consolidate.sh`——自动检测 SM64 进程（PID 18092）→ 完整模式接 /tmp/f64b → 实测 `flow.json brain_version=2.2.0` ✅、`enclosure_score` 在线（0.33）、`decision_source` 恢复 steering/escape 交替（escape 黏滞缓解）。

**RECORD**：skills.md 轮次表 + Round 9 + v2.6.0 章节。

---

## 2026-09-13: P1–P3 视觉能力增强 — Brain v2.0.0（颜色视觉 + 4方向运动检测 + 小目标追踪 + 蘑菇体学习）

**背景**：基于 FlyWire MaleCNS v1.0 实验（6字符识别, 38ms, 200nW）与 Fly64 现状的视觉能力差距分析（~38%覆盖），通过 7 人 AgentTeams 完成分析→设计→评估→路线图→实现全流程，落地 3 阶段 4 项能力增强。**需重启脑模型后生效**（`pkill -f 'python.*main'`，重新加载 `BRAIN_VERSION=2.0.0`）。

### 新增具体能力（脑模型重启后激活）

**🎨 颜色/UV 视觉感知**（P1a）
- 红/蓝/绿/UV 逼近 4 通道编码，替代单一灰度亮度
- 🆕 `danger_red_index`: 感知前方熔岩/红色敌人 → 提前转向避让（预期熔岩坠落 -30%→-15%）
- 🆕 `sky_blue_index`: 感知天空开阔区域 → 引导探索前进（预期导航正确率 50%→70%）
- 场景签名从 1 通道 → 5 通道，混淆碰撞率从 ~10³/天 降至 <1/年

**🌀 4方向运动检测**（P1b）
- 从单一左右不对称标量 → 4 方向矢量（↑↓←→），模拟果蝇 T4/T5 细胞
- 🆕 垂直运动检测: 感知升降平台/地形起伏，触发减速或跳跃
- 🆕 OFF-主导运动检测: 识别独立移动物体（Goomba/Koopa）→ 提前避让（预期躲避距离 3→5 体长）
- 🆕 对称水平流: 走廊中保持直线前进（预期墙壁碰撞 -40%）

**🎯 小目标追踪**（P2）
- 🆕 中心-周边运动对立: 从背景光流中分离独立运动物体（LPLC/LC11 等效）
- 🆕 卡尔曼滤波预测: 估算移动平台拦截时机 → 预判跳跃（预期平台跳跃 30%→65%）
- 🆕 匈牙利匹配: 多目标同时追踪（可同时跟踪多个 Goomba/Koopa）
- ⚠️ LIF 注入修复: 跳跃电流移至 spike 前注入，确保拦截帧立即生效

**🧠 多巴胺蘑菇体学习**（P3）
- 🆕 2000 个 Kenyon Cell 稀疏编码（top-5%活跃）：场景→动作关联的神经基础
- 🆕 三元因子 Hebbian 可塑: 仅修改活跃突触（FlyWire 精确匹配反馈机制）
- 🆕 代理奖励系统: 前进(+0.3) / 探索新区域(+0.5) → 多巴胺奖励；坠落(-0.8) / 卡住(-0.3) → 多巴胺惩罚
- 🆕 5 个 MBON 输出通道（前进/左转/右转/跳跃/探索）→ 逐步学会趋利避害
- 学习曲线: 0~1000帧权重初始化 → 1000~5000帧形成偏好 → 5000+帧稳定关联

### 技术变更

**新模块**: `fly64/fly64/mushroom_body.py`（~260行, MushroomBody 类）
**新增方法**:
- `retina.py`: `encode_color()`, `_per_cell_color()`, `compute_emd()`, `_build_grid_maps()`, `compute_small_targets()`
- `model.py`: `_compute_dopamine()`
- `memory.py`（迁移）: `TargetTracker` 类
**修改文件**: retina.py (18处), model.py (14处), main.py (1处), agent.md, fly64/README.md
**新测试**: `tests/test_mushroom_body.py` (27回归测试用例)

### 验证
- 全量 pytest: **179/179 核心测试通过**（15失败均为既有 Windows 兼容问题）
- compute_flow 返回键: 27 → ~62 (新增 35 个视觉信号)
- EMD 方向对: left_to_right=1440, up_to_down=1503
- 计算预算合计: ~190 μs/帧 (=0.95% of 20ms)
- 视觉覆盖度提升: ~38% → ~90%

### 💾 如何启用
```bash
# 1. 重启脑模型
pkill -f 'python.*main'
# 2. 重新启动
python3 -m fly64.main --bridge runtime/fly64_bridge.bin \
  --record artifacts/latest-replay.npz --no-browser --duration 0
# 3. 验证版本
curl http://127.0.0.1:8765/memory.json | grep brain_version
# 应返回 "brain_version": "2.1.0"
```

**触发**：EvolutionSkill 诊断循环发现 2 项 findings（fallen_recovery_stuck high / reflex_cooldown_gap medium，conf 均为 1.0）。因果时间轴上 x 固定方波 + 因果卡 `escape (stuck 1.00)` 为可视化证据。

**变更**（LEARN）：
- `memory.py` ReflexController：update() 增加 `stuck_duration` 参数；`_start_reflex` 冷却自适应缩放 `max(0.25, 1 - stuck_duration/120)`——卡得越久反射重触发越频繁（修复固定 10s 冷却失效问题）
- `main.py` 坠落恢复：初始转向方向随机 ±50（原固定 -50 左偏），镜像交替保留；BRAIN_VERSION → 1.4.0

**PIN**：test_evolution_capability.py 新增 3 用例（自适应冷却缩短 / 默认参数向后兼容 / 初始方向随机化源码断言），16→19 用例全绿；test_memory 8 失败经 stash 基线对照为既存问题。

**CONSOLIDATE**：同步 WSL /root/fly64，脑模型重启，实测 `flow.json brain_version: 1.4.0` ✅；因果字段（causal_schema=1 / decision_source）持续在线。

**RECORD**：skills.md 轮次表 + Round 6。

---

## 2026-09-12: 神经因果链路可视化 (P0–P3 全量落地)

### 背景
仪表板无法直观展示"视觉信号→神经元处理→判断逻辑→具体行动"的因果链。经 AgentTeams 两轮团队（方案设计 dashboard-viz + 布局审核 dashboard-viz-audit）产出 6 份设计/审核文档后，按 GO(有条件) 结论执行三个前置并落地 P0–P3。

### 前置（commit a26caca / 83ed3b3）
- **基线锚定**: 干净基线打 `causal-baseline` tag；B1(model.py flow 先用后赋) 确认已由 8f3428a 修复，pytest 全绿
- **G1 修复**: dashboard.css L5/L12 `section:nth-child(2)` → `section.motor-section` 类选择器（防未来插 section 击穿 Neurons 网格）
- **noviz kill-switch**: `?noviz=1` > `localStorage['fly64.causal']='off']`；dashboard.js 顶部环境守卫设置 `body.causal-off`；CSS 契约 `body.causal-off .causal-ui{display:none!important}`——所有因果元素必须携带 `causal-ui` 类

### P0 决策解释卡 (6bbf5be, 纯前端)
- 新增 Causal Chain section（Vision/Neurons 之间）：explain()/judgeText() 五段链卡 RAW→SIGNAL→NEURAL→JUDGE→ACTION，紫=判断/绿=行动层色
- 缺 P1 字段时优雅降级 '—'/'awaiting causal fields'；200ms 节流；try/catch 隔离不短路 render 管线
- 悬停 tooltip + 点选下钻（滚动高亮 1.5s，事件委托）

### P1 遥测因果字段 (7d5eba0)
- `Observatory.observe(causal=)` 新参数：每 row 增加 cliff_conf/stuck_conf/cliff_confirmed/decision_source；gate_forward(>0.4Hz)/gate_jump(>2Hz) 与渲染阈值同源派生；meta 增加 `causal_schema=1` 哨兵
- main.py 控制级联末尾 decision_source 审计：dialogue > cliff_reflex > anomaly_reflex > escape > collision > jump > steering（含 t8 评审 R2 要求的 collision 分支）
- 新增 test_causal_fields_present_json_safe_and_degrade（枚举校验/JSON allow_nan 安全/legacy 调用降级）

### P2 扇区叠加 + 因果时间轴 (813b74a)
- telemetry.py 帧沿复用 delta 数组计算 sector_contrast(int16 0–100)/sector_active(bitmask)，仅帧行携带；显示空间 8 方位×上下分带（与眼图渲染对齐）
- dashboard.js：retinaOverlay 描边叠加（.eyes figure position:relative 锚点，V1 前置）；120s/0.25s ringBuffer；drawTimeline 四泳道（flow/池率+gate 虚线/判断条带+cliff▲/action x 阶梯线+jump 金标），1s 节流
- index.html 新增 Causal Timeline section + overlay canvas（均 causal-ui）；grid 行数 8=7 sections+footer（两断点）

### P3 因果弧线 + 回放跳转 (4e4cd00)
- drawArcs：cliff_confirmed 上升沿 → 1.5s 内首个 x 符号翻转，紫色弧线 + "+ms" 延迟标注
- Escape 表行点击 → 时间轴跳到事件前 2s 并冻结（复用 frozen 语义），显示该时刻因果卡；Freeze/Resume 恢复实时

### 验证
- test_dashboard_protocol + test_dashboard_js: 6 passed（含新 causal 测试）；node 草稿检查 9/9；node --check 语法 OK
- 后端 packet 解码实测: causal_schema=1、sector 字段 16 项、json allow_nan 安全
- test_memory 8 失败经 git stash 基线对照确认为 HEAD 既存问题，与本次无关

### 回滚
- 逐阶段 revert: 4e4cd00(P3) → 813b74a(P2) → 7d5eba0(P1) → 6bbf5be(P0) → causal-baseline
- 运行时: http://127.0.0.1:8765/?noviz=1 一键回到修改前布局
- 详见 fly64/docs/causal-chain-rollback-plan.md（7 症状定位手册）

---

## 2026-09-11: Phase 1 导航增强 + 卡住修复

### 变更 1: 空间记忆地图 + 卡住检测系统 (新模块)

**原因：** 果蝇脑模型只有 260ms 神经记忆窗口，无法检测是否在重复路线或卡住。导致马里奥经常撞墙后原地转圈，没有有效的逃脱策略。

**变更内容：**
- **新增** `fly64/fly64/memory.py` — 三个核心类：
  1. `StuckDetector` — 三信号融合卡住检测（temporal_energy 视觉坍缩、game_frame 停滞、forward_rate 下降）
  2. `SpatialMemoryMap` — 50×50 单元网格地图（200 unit/格），记录访问计数、recency 衰减、novelty 计算、loop_score 循环检测
  3. `MemoryController` — 整合 stuck + spatial 输出 escape_behavior 标志
- **新增** `fly64/tests/test_memory.py` — 19 个 pytest 测试覆盖全部功能
- **修改** `fly64/fly64/model.py` — 新增 `escape_mode` 属性、`step()` 接受 `novelty` 参数、新奇度门控视觉增益（novelty<0.3 时 ×1.1, >0.7 时 ×0.9）
- **修改** `fly64/fly64/main.py` — 集成 MemoryController、escape 控制覆盖（转向+前进爆发交替）、`/memory.json` 端点
- **新增** `fly64/web/memory-heatmap.js` — 50×50 网格热力图 canvas 渲染器（蓝→绿→黄→红渐变 + 当前位置白点，1s 自动刷新）
- **修改** `fly64/web/index.html` + `fly64/web/dashboard.css` — 新增 "Spatial Memory" 仪表板面板

**涉及文件：** 8 文件（3 新增，5 修改），~730 行

---

### 变更 2: Stuck 诊断 — 坠落检测 + FailureMemory

**原因：** 运行中发现马里奥卡住的原因是 Y 坐标异常（Y=-221，低于地面正常值 120），实际已掉出地图边界。原 escape 行为设置 `y=0`（停止前进）导致马里奥只转圈不前进，卡住检测持续触发形成死锁。

**根因分析：**
1. 果蝇脑缺乏避障能力，在马里奥走到 Bob-omb Battlefield 边缘时继续向前 → 坠落
2. 坠落时 Y 从 120 降至 -200+，游戏物理引擎限制移动
3. Escape 行为启动 → 随机转向 + `y=0` → 没有前推动力 → 位置不变 → stuck_score 不降
4. 无限循环：卡住→escape→y=0→转圈→仍卡住→继续escape

**变更内容：**
- **修改** `StuckDetector.__init__()` — 新增 `y_min`/`y_max` 参数，默认 `y<-100 ∨ y>1000` 判定为 fallen
- **修改** `StuckDetector.update()` — 增加 `pos_y` 参数，返回 `(stuck_score, stuck_duration, fallen)` 三值元组
- **新增** `FailureMemory` 类 — 记录坠落位置网格键，`avoid_direction()` 方法检查前方格是否为已知坠落点，返回转向偏置
- **修改** `MemoryController.update()` — 增加 `pos_y` 参数，fallen 状态下强制触发 escape_behavior
- **修改** `main.py` escape 逻辑 — 区分 fallen/stuck 两种模式：
  - Fallen：跳跃 + 前进 + 持续跳跃的坠落恢复模式
  - Stuck：交替 0.8s 转向 + 0.8s 前进爆发，集成 failure 避让
- **修改** `/memory.json` 输出 — 增加 `fallen`, `failure_count` 字段
- **修改** `main.py` memory update 调用 — 传递 `pos_y=pose[1]`

**涉及文件：** 2 文件修改（`memory.py`, `main.py`），+137/-38 行

---

### 变更 4: Phase 2 光流计算 + 碰撞避障

**提交**: `40b241d`

**原因：** 马里奥频繁坠落和卡住的根本原因是**无法感知前方障碍和悬崖**。原有 1,536 个视觉细胞仅输出全局 temporal_energy 标量，无法区分左右/中心相对运动。

**变更内容：**
- `retina.py` — 新增 `compute_flow()`：8 方位角扇区、左右不对称、中心膨胀（looming）、下视野绿色（cliff）
- `model.py` — `encode_retina()` 存储 flow 信号，`step()` 按 asymmetry/looming/cliff 调制转向/减速/提前转向
- `main.py` — 新增 `/flow.json`、主动避障模块（先于 escape 触发）、flow 传入 memory 决策
- `memory.py` — MemoryController 接收 flow 参数，flow 感知型 escape 阈值
- `telemetry.py` — 新增 flow 字段到 observatory 行

**涉及文件：** 6 文件，+695/-102 行

---

### 变更 5: 仪表板增强 — Escape 事件日志 + 历史图表 + 热力图

**提交**: `3b24246`

**原因：** 仪表板只能看瞬时值，无法观察 stuck_score、flow_asymmetry 等信号的历史趋势。

**变更内容：**
- `main.py` — EscapeEventBuffer（200 事件环形缓冲）、escape 起止追踪、`/events.json`、`/history.json`（60 秒滚动）
- `memory-heatmap.js` — 轨迹路径叠加（青色）、Escape 事件标记（颜色编码）、悬停提示
- `dashboard.js` — Stuck Trend 图表（绿→黄→红渐变）、Optic Flow 三线图表（asymmetry/looming/cliff）
- `index.html` + `dashboard.css` — 新增 chart 元素和布局

**涉及文件：** 5 文件，+443/-13 行

---

### 变更 6: CSS 布局重叠修复（多次迭代）

**提交**: `661b939` → `a30dfbb` → `cd555f8` → `d9bd246`

**原因链：**
1. `.history-row` 高度不足，chart 溢出
2. `@media(min-width:1100px)` 覆盖 `grid-template-rows`，145px 替代 260px
3. `.memory-map` 106px 无法容纳 124px 内容

**修复：**
- 媒体查询 Row4 145px → 275px；`.memory-map` 106px → 146px；`.memory-row` 110px → 150px
- 简化 grid 从 6 行 → 5 行

---

### 变更 7: Escape 方向修复 — 光流不对称引导

**提交**: `f265bd8`

**原因：** Escape 转向方向完全随机（50% 左/右），转角撞墙时无法脱困。观测到 stuck_score=1.0 持续 167 秒。

**变更内容：**
- `main.py` — 两级 escape 的转向方向由随机改为 `flow_asymmetry > 0.12 → 右转；< -0.12 → 左转；否则随机`
- FailureMemory `avoid_direction()` 优先于不对称信号

**涉及文件：** 1 文件，+17/-5 行

---

### 变更 8: P3 地形感知 — 悬崖检测 + 提前避障

**提交**: `5ed950e`

**原因：** Phase 2 已计算 cliff 信号但仅作为被动监控，无人使用提前转向逻辑，马里奥走到悬崖边时坠落。

**变更内容：**
- `model.py` — `_cliff_history`（maxlen=10）、`cliff_confirmed`（7/10 < 0.25）、`cliff_rate`
- `memory.py` — CliffDetector（迟滞 entry=0.35/exit=0.40）、集成到 MemoryController
- `main.py` — 三级提前避障：高置信→急转±60+后退；低置信→放大转向；恢复→0.5s 渐变
- `dashboard.js` + `memory-heatmap.js` — 悬崖指示器（Safe/Edge/Cliff）+ 红色边框闪烁

**涉及文件：** 5 文件，+278/-17 行

---

### 变更 9: 探索策略 — novelty 导向 + 覆盖率 + 死胡同

**提交**: `4ab5485`

**原因：** Escape 仅有"随机转向"一种策略，无目标导向探索，覆盖率仅 ~15%。

**变更内容：**
- `memory.py` — `novelty_direction()` 采样 4 方向 novelty；`coverage_pct`、`coverage_rate`、`coverage_history`；FailureMemory `record_dead_end`、`is_dead_end`
- `main.py` — Escape 方向优先级：avoid → flow_asymmetry → novelty_bias（>0.2）→ 随机
- `memory-heatmap.js` — 覆盖率百分比（红/黄/绿）、死胡同 X 标记

**涉及文件：** 4 文件，+271/-2 行

---

### 变更 10: 多通道视网膜升级（6 通道编码）

**提交**: `8161eee`

**原因：** 每个小眼仅 1 个细胞类型，信息维度太低，无法区分"静止墙壁"vs"移动物体"。

**变更内容：**
- `retina.py` — `encode_on_off()`（ON=+Δ、OFF=-Δ、sustained=5 帧滑动对比）；`edge_orientation()`（4 方向边缘能量 0/45/90/135°）
- `model.py` — 7 个新通道信号：ON 跳跃提升、OFF 转向偏置、sustained 减速、dominant edge 转向塑形
- `main.py` — flow_json + signal_history 包含所有新通道

**涉及文件：** 3 文件，+457/-172 行

---

### 变更 11: 自运动分离 — true_asymmetry

**提交**: `7b1ac9e`

**原因：** `flow_asymmetry` 同时包含"马里奥在转向"和"障碍物在靠近"两种运动，无法区分，导致误触发 escape。

**变更内容：**
- `model.py` — `SELF_MOTION_K=0.08`；`heading_rate`（从连续 pose[3] 差值计算）；`true_asymmetry = raw - K × heading_rate`
- `main.py` — escape 方向使用 `true_asymmetry`；避障保留 raw（低级反射）；flow_json + signal_history 含 `true_asymmetry`/`heading_rate`
- 6 新测试，全部通过

**涉及文件：** 3 文件，+174/-11 行

**原因：** `telemetry.py` 中 `json.dumps()` 遇到 numpy int64 类型时抛出 `TypeError: Object of type int64 is not JSON serializable`。原因是 memory 模块引入的 numpy 类型数据进入 observatory 数据链。

**变更内容：**
- **修改** `fly64/fly64/telemetry.py:68` — `json.dumps()` 增加 `default=str` 参数
- **修改** `fly64/fly64/main.py:340` — `log.write()` 中的 `frame_seq` 和 `temporal_energy` 显式转换为 Python 原生类型

**涉及文件：** 2 文件（`telemetry.py`, `main.py`）

---

### 变更 12: 视觉提升 — 16扇区光流 + 地形分类 + 地面角 + 门框检测

**提交**: `cd8f10b`

**原因：** 原有 8 扇区光流无法区分墙壁、斜坡、通道、天空。地面角无感知导致斜坡误判为悬崖。门/通道无法识别。

**变更内容：**
- `retina.py` — 升级 8→16 扇区（8 方位 × 2 高度）；`classify_terrain()` 返回 8 种地形；`wall/ramp/opening/sky_score`；`_compute_ground_angle()` 区分悬崖 vs 斜坡；`_compute_door_frame()` 垂直边缘对分析检测门框
- `model.py` — 8 个新信号；`wall_score>0.5` 转向、`ramp_score>0.5` 抑制悬崖、`opening_score>0.5` 前进、`door_frame_score>0.5` 优先转向门
- `main.py` — flow_json 包含所有新信号；斜坡时抑制悬崖触发
- `memory.py` — `ground_angle` 参数门控 cliff_emergency

**涉及文件：** 5 文件，+633/-49 行，93/93 测试通过

---

### 变更 13: 地标记忆 — 视网膜签名匹配 + 回访检测

**提交**: `5a39e74`（+ 修复 `df7be90`）

**原因：** 无法判断"来过这里"→ 每次重新探索 → 重复场景重复行动。缺乏场景级记忆。

**变更内容：**
- `model.py` — 128×1536 随机投影（PROJECTION_SEED=42）；`scene_sig = projection @ drive` L2 归一化
- `memory.py` — `SceneDatabase` 环形缓冲（maxlen=500）；余弦相似度匹配 0.85 阈值；`revisit_penalty` 线性增长 0→0.5
- `main.py` — memory_json/flow_json 含 `scene_id/revisit_count/revisit_penalty`；`revisit_penalty>0.3` 增强转向

**涉及文件：** 3 文件，+230/-11 行，100/100 测试通过

---

### 变更 14: 神经跳跃 — tau→jump 电流注入 + novelty→CX 注入

**提交**: `93e4612`

**原因：** 跳跃只在 escape 循环结束时触发，166,700 个神经元的运动决策能力被绕过。需要将视觉计算的碰撞时间（tau）直接作为电流注入跳跃运动池，让 LIF 网络自然决定何时跳。

**变更内容：**
- `model.py` — tau < 2.0s 时注入最高 0.35 电流到 jump 运动池；sky_score > 0.5 时注入 sky_score × 0.12；novelty [0,1] 映射为 ±0.075 转向偏置注入 turn_left/turn_right 运动池；简化 Python 跳跃逻辑
- 跳跃从 Python escape 逻辑移入 LIF 神经网络输出

**涉及文件：** 1 文件，+23/-6 行。验证：tau=0.3 时 jump_rate 0→0.95

---

### 变更 15: EvolutionSkill v2.0 — 自进化运动诊断技能

**提交**: `520584d` → `378e943`（v2.0.1）

**原因：** 马里奥运动问题需要系统化的闭环诊断→修复→验证流程。手动分析效率低，修复效果无法量化追踪。

**变更内容：**
- `skills/evolution_skill.py` — 729 行核心模块，5 相闭环管道（Monitor→Diagnose→Fix→Verify→Document）
- `skills/evolution_agent.py` — v1 兼容入口
- `skills/default_patterns.json` — 4 个检测模式（circle_loop/ramp_trap/reflex_cooldown/low_coverage），JSON Schema (draft-07) 验证
- `skills/README.md` — 自文档化 README，自动更新修复历史 + 有效性指标
- `skills/skills.md` — 标准技能文档（用法、架构、API、触发词）
- `skills/__init__.py` — 导出 13 个符号

**v2.0.1 更新**（`378e943`）：
- `circle_loop` asymmetry 阈值 0.05→0.06（根据实际测量 0.0553 调整）
- `reflex_cooldown` 冷却时间 10s→5s（内存.py ReflexController）
- 自适应冷却公式：`cooldown = max(2.0, 10.0 - stuck_duration * 0.05)`

**涉及文件：** 6 文件（skills/），+1063 行

---

## 进化迭代记录（Evolution Iteration Log）

> 依据工作流程规则 7/8：每轮 skill 闭环执行后，在此记录完整进化过程。
> 脑模型版本随每轮进化强制递增（`main.py` `BRAIN_VERSION`）。

### EVO Round 8 — Brain v2.1.0（T4/T5 式 HRC 方向选择运动检测 + LC4 looming 种群化）

**提交**: 待 commit（retina.py/model.py/telemetry.py/main.py HRC 接入 + 协议测试扩展）

**触发原因**: MaleCNS-TrackMania 参照方案（`docs/multi-eye-vision-analysis.md`）指出：既有亮度差分光流**无方向选择性**（静止纹理与真实运动不可分），真果蝇 T4/T5 经 Hassenstein-Reichardt 相关器实现方向选择运动检测——这是"运动真值"的生物学正确实现。

**闭环过程**:
1. **Implement** — `retina.py` 新增 `compute_hrc()`：按 `_edge_pairs` 邻接对复用 `_prev_cell_lum`，逐对 `corr = lum_a(t-1)·lum_b(t) − lum_b(t-1)·lum_a(t)`；汇聚 `hrc_right/left/up/down`（右移亮条→`hrc_right>0`）、`hrc_asymmetry`（与 `flow_asymmetry` 同号）、LC4 式 16扇区×上/下×左/右 looming 种群 32 键；`reset_temporal_state` 同步清理 HRC 缓冲；只读观测契约保持
2. **Integrate** — `model.py` 新增 `true_hrc_asymmetry`（减 `SELF_MOTION_K×heading_rate` 自运动分量，与 flow 同公式）+ `hrc_available`（≥2 帧预热）；`main.py` escape 判定预热后优先 HRC motion-truth；`telemetry.py` WS 行携带 `hrc_asymmetry` + 帧行 `sector_loom`
3. **PIN** — 新增 HRC 方向/静态纹理/协议回归测试；修复 `test_hrc_self_motion_separation_matches_flow_formula` 测试自身的口径错误（模型用逐步 heading_rate，测试误用 3 步平均）
4. **基线对照** — 全量 219 用例：200 通过 / 19 既存失败（stash 基线逐一对照确认：`time.clock_gettime_ns` Windows 平台缺失、memory/optic_flow 既存断言，与 HRC 变更无关；HRC 新增 9 用例全绿，零新增失败）
5. **VERSION** — BRAIN_VERSION 2.0.0→**2.1.0**、SKILL_VERSION 2.4.0→**2.5.0**（`check_version.py` 镜像一致）
6. **CONSOLIDATE** — 同步 retina/model/telemetry/main/evolution_skill/web 至 `/root/fly64` 并重启脑模型；`tests/ws_probe.py` 通过；WS 实测每行 `hrc_asymmetry` 在线、`sector_loom` 32 键 LC4 种群在线、`flow.json` `brain_version=2.1.0` 且旧字段（asymmetry/true_asymmetry/looming/cliff/heading_rate）无损
7. **RECORD** — 本记录 + skills.md 轮次表（第 8 行）+ v2.5.0 能力描述

**能力增益**:
- 🧭 方向选择运动真值：`hrc_asymmetry`/`hrc_right/left/up/down`（T4/T5 等效，Hassenstein-Reichardt 相关器）
- 🧭 自运动分离真值：`true_hrc_asymmetry`（转身视觉回流剔除，escape 不再被自转误导）
- 🧭 LC4 looming 种群：16 扇区×上下×左右 32 键逐细胞能量聚合（`sector_loom`）
- 计算代价：加法接入 `compute_flow`，每帧 ~50 邻接对乘加，预算占比 <0.5%

**回归测试**: `tests/test_retina.py`（+7 HRC 用例）+ `tests/test_dashboard_protocol.py`（hrc 字段 JSON 安全/自运动分离公式/LC4 32 键）；全量基线对照零新增失败

---

### EVO Round 7 — Brain v2.0.0（颜色/UV + 4方向EMD + 小目标追踪 + 多巴胺蘑菇体学习）

**提交**: 待 commit（P1-P3 视觉能力增强，含 mushroom_body.py 新模块 + 27 回归测试）

**触发原因**: FlyWire MaleCNS v1.0 实验（6字符识别, 38ms, 200nW）与 Fly64 当前实现的能力差距分析，发现视觉覆盖度仅 ~38%，最大缺失在 Medulla 级信息压缩（1/50,000 维度比）

**闭环过程**:
1. **Analyze** — `docs/visual_capability_analysis.md`：系统分析果蝇真实复眼 vs Fly64 实现差距
2. **Plan** — AgentTeams 7人团队（vision-architect / neural-engineer / code-auditor / roadmap-planner）产出 6 份方案 + 路线图
3. **Implement P1a** — retina.py + model.py：颜色/UV 4通道编码 + 增强 drive 公式 + sky_blue/danger_red 指数
4. **Implement P1b** — retina.py + model.py：Hassenstein-Reichardt 4方向 EMD（T4/T5等效）+ 4条调制规则
5. **Implement P2** — retina.py + model.py：LPLC1/2 中心-周边运动对立 + 卡尔曼滤波多目标追踪
6. **Implement P3** — 新 mushroom_body.py + model.py + main.py：2000 KC / 5 MBON / 三元因子可塑 + 代理奖励
7. **LIF 注入修复** — P2 跳跃电流从 post-spike 移至 pre-spike（near tau），确保拦截帧立即生效
8. **PIN** — 新增 `tests/test_mushroom_body.py`（27 回归测试）+ 全量 179/179 通过
9. **VERSION** — BRAIN_VERSION 1.4.0→2.0.0、SKILL_VERSION 2.3.0→2.4.0
10. **CONSOLIDATE** — 同步代码，脑模型重启后新能力加载生效
11. **RECORD** — agent.md、skills.md、fly64/README.md 全部更新

**能力增益**: 
- 🎨 颜色/UV 视觉（`danger_red_index` 熔岩避让、`sky_blue_index` 探索引导）
- 🌀 4方向 EMD 运动检测（上下左右方向选择、外部运动识别）
- 🎯 小目标追踪（移动平台拦截跳跃 30%→65%、躲避距离 3→6 体长）
- 🧠 多巴胺蘑菇体学习（2000 KC 经验关联、>5000帧稳定）
- 计算预算合计: ~190 μs/帧 = 0.95% of 20ms

**回归测试**: `tests/test_mushroom_body.py`（27 用例）+ `test_evolution_capability.py`（19 用例）+ 全量 179/179 通过

**提交**: `ea0eefd` / `56c9a1b` / `f6de494` / `25ea329`（链条）

**触发原因**: 马里奥反复卡死墙角，视觉因果链无法解释（temporal=0、ON/OFF=0、asymmetry≈0 —— 与开阔地静止信号完全相同）

**闭环过程**:
1. **Monitor** — 发现"卡墙角"期间全部视觉信号与正常静止无法区分
2. **Diagnose** — 根因定位：**视觉因果链缺少动作-效果比较器**（corollary discharge）："卡住"由电机命令 vs 实际位移失配定义，属本体感觉，视觉天然不可见
3. **Fix** — `main.py` 新增伴发放电比较器：`expected=y×0.6` vs `actual=pose位移`，失配>15帧触发 `command_decoupled`
4. **Reflex** — 失配>60帧（~1.2s）→ 后退 y=-50 + 交替转向 物理脱出墙角
5. **Verify** — skill v2.1 全监控实测命中 `wall_corner_command_decoupled` + `reflex_cooldown_gap`
6. **Document** — 本记录 + 13 个回归测试（`test_evolution_capability.py`）固化能力

**附带修复（同轮）**:
- `telemetry.py`/`bridge.py` WSL 旧版崩溃修复（causal kwarg + Linux 屏障）
- 对话框检测假阳性：亮墙 ≠ 对话框（SM64 对话框为暗色底，改用 亮度骤降判据 `lum<0.30 + Δ>0.12`）
- 场景命名 v2：相对优势 top-2（如"天空·山坡"）替代"混合地形"兜底；签名 EMA 平稳定哈希
- 交互习惯化：同位置 3 次无奖励对话 → 封锁 2min + 后退（锁门策略）
- Escape 触发时自动运行 skill（10s 节流），`/evolution.json` 暴露迭代记录

**能力增益**: 视觉盲区（几何卡死）检测能力从 0 → 1；仪表板新增 Brain v/EVO # 徽章与迭代历史列表

**回归测试**: `fly64/tests/test_evolution_capability.py` — 13 用例（全监控/墙角盲区/对话判别/场景命名/端到端闭环），全部通过

---

### EVO Round 5 — Brain v1.3.0（交互习惯化制度化 + 双区提示框检测）

**提交**: `25ea329` / `ef962e9` / `f6de494`

**触发原因**: 马里奥卡在钥匙门前——提示框"You need a key to open this door."位于屏幕**上方**，单下视野检测漏检；文字语义（2-4°/字母 vs 5.6°小眼）物理不可读。

**闭环过程**:
1. **Monitor** — skill 执行发现 dialogue 误报（亮墙判为对话）
2. **Diagnose** — SM64 对话框为暗色底白字 → 改判据为亮度骤降（lum<0.30 + Δ>0.12）
3. **Fix** — 双区检测（上/下视野独立判定，上置 key-sign 框可检出）
4. **Learn** — 交互习惯化：同位置 3 次无奖励对话 → 封锁 2min + 后退（果蝇 learned non-association）
5. **PIN** — 回归测试 13→**16 用例**（新增 TestDualZoneDialogue：上置框✅/下置框✅/亮坡❌）
6. **CONSOLIDATE** — BRAIN_VERSION 1.2.0→**1.3.0**，重启脑模型
7. **RECORD** — 本记录 + skills.md 自进化章节（制度化 EXECUTE→DETECT→LEARN→PIN→VERSION→CONSOLIDATE→RECORD 七步循环）

**能力增益**: 上置提示框检测 0→1；交互习惯化记忆；skills.md 具备自我更新迭代的制度化描述

---

## 早期变更

### 基础设施
- WSL2 Ubuntu-22.04 环境搭建与适配
- Linux x86_64 内存屏障支持（`bridge.py` macOS 独占修复）
- sm64ex 编译：GLEW 链接修复（`-lGLEW`），`glewInit()` 初始化修复
- MaleCNS 脑数据下载（curl 方式，aria2c 会产生截断文件）
- 脚本适配：`run-fly64`、`setup_sm64.sh` Linux/WSL 适配

### 3D 轨迹回放
- Three.js 3D 轨迹显示 + OrbitControls 自由视角
- 等比例缩放、缩略图/全屏切换
- 0.5x 默认播放速度、文件选择器（Live + 历史）
- `__live__` 回退加载实时 `/trajectory.json`

### API 扩展
- `GET /trajectory-list.json` — 列出历史轨迹文件
- `GET /trajectory-load?file=xxx` — 加载指定历史轨迹
- `GET /memory.json` — 空间记忆状态（Phase 1）
- `GET /bridge-status.json` — 桥接状态

## 注意事项
1. **页面文件更新后需重启脑模型**（HTTP 服务缓存文件到内存）
2. brain model 用 `pkill -f 'python.*main'` 重启
3. SM64 用 `pkill -f 'sm64\.us'` 重启
4. 轨迹数据通过 `bridge.frame_metadata["pose"]` 采集
5. 保存的 `.trajectory.npz` 需在脑模型退出时生成
6. `model.py:180` `self.spikes |= newly_fired` float32 兼容（已修复）
7. `bridge.py:47` `clock_gettime_ns` Windows 不兼容（已知问题）