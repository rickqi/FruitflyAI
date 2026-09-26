# Fly64 精选部署清单（2026-09-25 自治进化工作）

> **目的**: 把本次自治进化工作（SP1–SP5-A + 收尾修复）**精选**同步到运行实例，
> 避免把工作区 **469 项脏改动**（含他人未提交的 WIP）一起带上运行系统。
>
> - **开发侧**: `D:\codes\flygym\fly64`（Windows，git `ab2761c`，工作树脏）
> - **运行侧**: WSL2 Ubuntu-22.04 `/root/fly64`（**独立副本，非 git 仓库，非 `/mnt/d` 链接**）
> - **运行进程**: PID 63 `/usr/bin/python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0`（tmux 会话 `fly64`，09-25 11:22 启动）
> - **Dashboard**: WSL 内 8765，经 `wslrelay.exe` 转发

---

## 1. 背景：这不是新问题

项目文档中**多处**已记录同一缺陷 ——「改了源码但没同步到 WSL 运行实例」：

| 文档 | 原话 |
|------|------|
| `docs/analysis/motor-pool-review-t2.md` | 「**活体未部署修复**（deployed `model.py` md5 = HEAD = 修复前）本报告所有 post 读数均为**工作区代码的离线实测**」 |
| `docs/analysis/motor-pool-review-t3.md` | 「**活体未部署**：deployed `main.py` 仍是修复前版本」 |
| `docs/analysis/motor-pool-review-t8.md` | 「**活体未部署**（deployed `model.py` 仍是修复前）」 |
| `docs/analysis/motor-pool-saturation-findings.md` | 「live 大脑实际跑在 WSL（`/root/fly64`）」 |

⇒ 本清单是对该系统性流程缺陷的一次性修复尝试。

---

## 2. 版本落差（部署前实测）

| 项 | 工作区 | WSL `/root/fly64` |
|----|--------|------------------|
| `SKILL_VERSION` | **3.5.1** | **3.4.2** |
| `BRAIN_VERSION` | 2.24.0 | 2.24.0（一致） |
| `skills/evolution_skill.py` | **5109 行** | **2735 行** |
| `fly64/main.py` | 3430 行 | 2856 行 |
| git HEAD 对应 | 2941 行 | — |

新机制命中数在 WSL 侧**全为 0**：`terminal_surrender` / `surrender_evidence` / `AAReportScheduler` / `_bootstrap_upper95`。

---

## 3. ✅ 部署集（17 个文件）

### 3.1 覆盖（11 个已存在，md5 全不一致）

| # | 路径 | 工作区 md5 | 承担的机制 |
|---|------|-----------|-----------|
| 1 | `fly64/main.py` | `15ed27d3fef5` | P0-a2 单位对齐 / P0-a8 迁移 / P1-b3 门 / P1-b4 死写入 / P2-c2 发布 / F-04 读回校验 |
| 2 | `fly64/memory.py` | `9ff0c34872f4` | P0-a2 泄放 / P2-c2 `terminal_surrender` / P2-c3 检测窗 |
| 3 | `fly64/model.py` | `7b222dbdb451` | **P1-b1 增益链**（`_jump_leg_weight`）/ P1-b2 稳态 / P1-b3 门 / P1-b5 三 kwargs |
| 4 | `fly64/central_complex.py` | `e66d65b63fa4` | **P1-b5 CX 环路突破可达化**（`_no_progress`/`_burst_ok`） |
| 5 | `fly64/instinct_bindings.py` | `54b0639b90b5` | M4-d5-d / R1 拒绝+`reject_reason` |
| 6 | `fly64/mushroom_body.py` | `c7a05141131a` | P1-b6-1 死代码清除（`set_adaptive_lr`） |
| 7 | `skills/evolution_skill.py` | `f895171ee477` | **主模块**：A/A 收集器 + 调度器 + `AANoiseFloorEstimator` + G-1/G-2/W1–W3 |
| 8 | `skills/default_patterns.json` | `eb2aae79e02b` | P2-c2 pattern 排除条件 → `struggle_or_terminal` |
| 9 | `skills/brain_tunable_params.json` | `d8699a0a6d05` | P0-a8 注册表（`gate_jump_threshold` → ratio） |
| 10 | `skills/active_strategy.json` | `684003b04170` | **P0-a8 三项迁移**（见 §5 风险） |
| 11 | `plugin/strategy_writer.py` | `2c0c6df15629` | M4-d5-f 教练直写记录 `source="coach"` |

### 3.2 新建（6 个，WSL 侧**完全不存在**）

| # | 路径 | 工作区 md5 | 说明 |
|---|------|-----------|------|
| 12 | `skills/fix_executor.py` | `961361538e87` | M4-d1 T3 门禁 + 运行时守卫（923 行） |
| 13 | `skills/fix_guard.py` | `926ce7b693ed` | D1 共享 helper `is_py_patch`（与 12 互引） |
| 14 | `skills/param_authority.py` | `142369d49794` | P0-a4 参数授权点（仅 stdlib） |
| 15 | `skills/evo_funnel_alarm.py` | `6aacd74a91aa` | P0-a6 心跳/漏斗告警（仅 stdlib） |
| 16 | `skills/param_wiring_ab.json` | `9d8a8b545d57` | P0-a4 运行时 A/B 判据账本 |
| 17 | `contract_registry.json` | `d9653438959e` | P0-a1/a8 单位契约（RULE-19 ratio 迁移） |

**依赖闭合性已核实**：
- `fix_guard` ⟷ `fix_executor` 互引（双向 import 回退，同 G-1 模式）
- `param_authority` / `evo_funnel_alarm` **仅用 stdlib**
- `fly64/main.py` **不依赖**任何新 skills 模块（对 `param_authority`/`evo_funnel_alarm`/`fix_guard`/`fix_executor` grep 命中 **0**）
- `fix_executor.py` **自带** `parse_fix_template`（:103），**不需要** `fix_template_interpreter.py`

---

## 4. ❌ 排除集（他人 WIP / 运行态 / 会话前文件）

| 路径 | mtime | 排除理由 |
|------|-------|---------|
| `skills/__init__.py` | 09-21 | 会话前；Python 子模块导入不依赖其列举 |
| `skills/curriculum.json` | 09-17 | 会话前 |
| `skills/fix_catalog.json` | 09-21 | 会话前 |
| `skills/scene_strategy_bindings.json` | 09-17 | 会话前（本能绑定语料） |
| `skills/fix_template_interpreter.py` | 09-24 12:09 | **会话前**；且部署集不依赖它 |
| `skills/evolution_history.json` | 09-23 | **运行侧权威历史**；工作区版非我方改动 |
| `plugin/llm_consult.py` | 09-23 | 会话前（他人 WIP） |
| `plugin/runner.py` | 09-23 | 会话前（他人 WIP） |
| `plugin/.consult_request.json` | 09-23 | **运行态** |
| `plugin/.pending_outcome.json` | 09-17 | **运行态** |
| `skills/.evo_loop_heartbeat.json` | 09-25 18:36 | **本地运行产物**（含已死 PID），绝不可部署 |

### ⚠️ 已知风险：`evolution_skill.py` 无法纯净切分

工作区 `evolution_skill.py`（5109 行）**同时包含**：
- 本次工作（A/A + 调度器 + W1–W3 + G-1/G-2）
- git HEAD 与 WSL 之间的**他人已提交**改动
- 工作树中**他人未提交**的改动

**无法从文件层面分离** ⇒ 部署该文件 = 连带部署其中的一切。这是本清单**最大的残余风险**，只能靠：
1. 部署前备份（可回滚）
2. 部署后跑测试与 dashboard 冒烟
3. 出现异常立即 `--rollback`

---

## 5. ⚠️ 关于 `active_strategy.json`（运行态文件）

它是**运行态**而非源码：教练/进化循环会写它。工作区版已应用 P0-a8 三项迁移：

| 键 | 工作区值 | 为什么必须部署 |
|----|---------|--------------|
| `gate_jump_threshold` | **0.75** | 新注册表为 ratio 语义 `[0.25, 4.0]`；若保留 WSL 的旧值 **3.082**，在新语义下要求 `jump_rate > 3.082×forward_rate` ≈ 2× 前向池 ⇒ **门几乎不开**，`jump` 仍恒 0 |
| `bold_explore_stuck_s` | **10.0** | 旧值 60.0 越出新区间 `[1,10]`，会被静默钳位 |
| `turn_bias` | 0.25 | 边界登记 |

**代价**：会覆盖 WSL 侧教练积累的状态（`__generation` 工作区为 332）。**已纳入备份**。

---

## 6. 部署后必须验证的信号

| 检查 | 期望 |
|------|------|
| 进程存活 | `pgrep -af fly64.main` 有新 PID |
| **`flow.json` 含 `terminal_surrender`** | ✅ 出现 ⇒ P2-c2 已生效 |
| **`flow.json` 含 `burst_active`** | ✅ 出现 ⇒ P1-b5/F6 互锁输入可用 |
| `flow.json` 含 `oscillation_adaptive_enabled` | ✅ 出现 ⇒ P2-c3 已生效 |
| `memory.json` 含 `stuck_duration_true` | ✅ 出现 ⇒ P0-a3 已生效 |
| `SKILL_VERSION` | 3.5.1 |
| `--history-check` | 若因 `evolution_history.json` 未部署而 FAIL ⇒ **已知且可接受**（仅影响该自检，不影响运行时） |

---

## 7. 诚实的功能预期

**会生效（不依赖已证伪的自治闭环）**：

| 机制 | 预期作用 |
|------|---------|
| **P1-b2 跳池 homeostat** | 跳池固有兴奋性可调 ⇒ **可能让 `jump` 真的触发**（当前 0/6000） |
| **P1-b5 CX 环路突破可达化** | 「无进展」可触发换招 —— **直接针对振荡陷阱** |
| **P1-b3 `jump_rate` 门归一化** | 消除 `0.04` 与池占用 0.043 的同量级堵塞 |
| **P1-b4 CX 旋钮死写入修复** | 转向增益真正可调 |
| P0-a2 / P2-c2 / P2-c3 | 检测层变诚实（`stuck_score` 不再被构造钉死 1.0） |

**不会生效（依赖自治闭环）**：

| 机制 | 原因 |
|------|------|
| P1-b1 增益链 + 闭环进化 | **H13 不成立**（真实 `noise_p95 = 0.1777`，超门限 **5.9×**）⇒ 适应度无法分辨改进 ⇒ 学习不会发生 |

---

## 8. 执行方式

使用配套脚本 `fly64/scripts/autonomy_deploy_restart.sh`（**默认 dry-run**）：

```bash
# 1) 预览（不做任何改动）
wsl -e bash /mnt/d/codes/flygym/fly64/scripts/autonomy_deploy_restart.sh --dry-run

# 2) 实际部署（自动备份 → 复制 → 重启 → 冒烟验证）
wsl -e bash /mnt/d/codes/flygym/fly64/scripts/autonomy_deploy_restart.sh --deploy

# 3) 只验证当前 dashboard
wsl -e bash /mnt/d/codes/flygym/fly64/scripts/autonomy_deploy_restart.sh --verify

# 4) 回滚（从最近一次备份恢复并重启）
wsl -e bash /mnt/d/codes/flygym/fly64/scripts/autonomy_deploy_restart.sh --rollback
```

**备份位置**：`/root/fly64/.deploy_backup/<YYYYmmdd_HHMMSS>/`（完整保留目录结构）

**回滚能力**：脚本记录每次部署的备份目录；`--rollback` 使用最近一次（或指定 `<timestamp>`）。

---

## 9. 部署后的前后对照（回答「解决到什么程度」）

部署并重启后，**用同一个 `trajectory.html`** 采集 ≥6000 帧，与本文档 §2 的基线对照：

| 指标 | 基线（未部署） | 本次实测（未部署） | 部署后 |
|------|--------------|-----------------|--------|
| X 方向效率 | 2.8% | 0.75% | ? |
| Z 方向效率 | 5.4% | 0.12% | ? |
| Z 活动跨度 | 7170.8 | 518.0 | ? |
| 静止帧占比 | 23.1% | 31.6% | ? |
| **jump 帧数** | 0 / 6000 | 0 / 6000 | ? |
| `coverage_pct` | 13.5% | 8.3% | ? |
| `stuck_duration` | 1066.8 s | 2476.5 s | ? |
| `waste_ratio` | 19.11 | 266.95 | ? |

⇒ **这是整个项目第一次能对「部署是否改善运动问题」给出真实答案。**

---

## 10. 证据边界

- 本清单基于**文件系统实物比对**（md5 + mtime + 存在性）与依赖 grep，非记忆
- `memory.json` / `.cache/malecns/manifest.json` 在工作区不存在（H5/H6/H11 未关闭）
- 源文件 mtime 归属为本会话任务报告的 `changedPaths` 与本机实测交叉得出；**未**读取 `.agent-teams` 状态文件
- 逐文件比对脚本留存于 `.tmp/deploy_compare.sh`、`.tmp/deploy_fullscan.sh`、`.tmp/deploy_precheck.sh`（可复跑）

---

## 11. 🔴 首次部署暴露的三处未提交回归（已修复并重部署）

首次 `--deploy`（时间戳 `20260925_185521`）后实例**立即崩溃**：

```
AttributeError: 'MemoryController' object has no attribute '_last_burst_tick'
```

`pyflakes` 全文件扫描进一步查出**同一代码块（`main.py` 探索死锁爆发块）共 3 处缺陷**：

| # | 位置 | 缺陷 | 修法 | 性质 |
|---|------|------|------|------|
| 1 | `main.py` 爆发块守卫 | 裸访问 `memory_ctrl._last_burst_tick`；**HEAD 版是安全的 `getattr(memory_ctrl, '_last_burst_tick', 0)`** | 还原 HEAD 的 `getattr(..., 0)` 形式 | **未提交回归**（安全模式被改坏） |
| 2 | `main.py` 状态初始化区 | `_burst_heading` **只读不写**：仅在开爆发时赋值，但爆发**持续期间**每 tick 都读 ⇒ 必然 `NameError` | 在状态块补 `_burst_heading: float = 0.0`（符合"爆发期间保持朝向"的原意） | **未提交新增代码缺初始化** |
| 3 | `main.py` 爆发块 `frontier_direction` 调用 | 传参 `pose[0], pose[1], pose[2]`，而 `pose` 在 `_request_dialogue_decision` 内**未定义** | 改用同函数内在作用域、且顺序在前的 `_pose_r[0..2]`（`:2102` 绑定） | **变量重命名后漏改** |

### 为什么本地测试从未发现

`fly64/main.py` 的**主循环从未在本地运行过** —— 本地只跑 `skills/evolution_skill.py` 进化环（它读取 dashboard，不驱动大脑）。
因此这 3 处缺陷只在**真实 WSL 运行时**才暴露。

**这正是"部署并实测"不可替代的价值**：292/292 本地测试全绿，而运行时 3 行内连崩。

### 验证

```bash
python -m pyflakes fly64/{main,memory,model,central_complex,instinct_bindings,mushroom_body}.py
# ⇒ 6/6 无 undefined name（修复后）
```

重新部署（时间戳 `20260925_185827`，`main.py` md5 `3a609c958478`）后：

| 检查 | 结果 |
|------|------|
| `traceback` / `NameError` / `AttributeError` 次数 | **0 / 0 / 0** |
| `deadlock_burst_count` | **3** ⇒ 曾三处报错的爆发块**确认真正执行** |

---

## 12. 部署后首轮实测（600 帧，全部为部署后数据）

| 指标 | 基线（未部署） | 部署前实测 | **部署后** |
|------|--------------|-----------|-----------|
| **`jump` 帧数** | **0 / 6000** | **0 / 6000** | **12 / 600（2.0%）** ← **项目首次观测到 jump** |
| 静止帧占比 | 23.1% | 31.6% | **0.5%** |
| x 跨度 | 8030.6 | 2078.3 | 4807.9 |
| z 跨度 | 7170.8 | 518.0 | 7199.3 |
| `stuck_score` | 1.0 | 1.0 | **0.01** |
| `stuck_duration` | 1066.8 s | 2476.5 s | **0.0 s** |
| `anomaly_state` | oscillating | oscillating | **idle** |
| `progress_ineffective` | True | True | **False** |

⚠️ **两部分必须区分**：
- `stuck_*` 的剧变**主要是检测层修正**（P0-a2 修掉了把 `stuck_score` 钉死在 1.0 的单位错配伪影），不直接等于行为改善
- **`jump` 0→12 与静止帧 23%→0.5% 是真实的行为变化**

完整 ≥6000 帧对照由 `.tmp/analyze_post_deploy.py` 采集（§9 口径）。
