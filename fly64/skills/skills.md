# EvolutionSkill — Self-Evolving Motion Diagnosis

> 当前版本：BRAIN_VERSION **2.23.7** / SKILL_VERSION **3.4.2**（EVO-066 契约审计（死旋钮清理、Phase 6 搜索空间 21→7）→ EVO-067 双环实测（Phase 6 提交率 2.27%、62.5% 试验精确零 delta → 已补分量与 same_sample 仪表）→ EVO-068 验证基线（回归可探测：36 条带成因，新回归以 NEW 冒头）→ EVO-071 Phase 6 根因修复（适应度 40% 权重读的是 SensorSample 上不存在的字段，被 getattr 静默归零，0.03 门槛不可达；现从真实字段派生 + missing_inputs 上报）＋两处测试误判更正＋“已声明未实现”30 项登记册。完整逐轮记录见 skills/evolution_history.json）

**Version**: 3.0.0
**Status**: Active
**Category**: Autonomous Agent / Self-Improvement + Causal Diagnostics + Social Capability

## Description

A complete closed-loop pipeline for autonomous motion diagnosis and self-improvement in the Fly64 fruit fly brain-controlled SM64 system. Monitors Mario's motion in real-time, detects behavioral anomaly patterns (circle loops, ramp traps, coverage stagnation), diagnoses root causes, applies code fixes, verifies effectiveness, and auto-updates documentation.

**v2.9.0 新增 — 自治基底常驻服务**（EVO Round 12，Brain v2.6.0）：`plugin/service.py`（10s 循环守护：pid 文件、每周期健康自检[仪表板可达/桥接 mtime≤60s/策略文件写出确认]写入 `service_status.json`，连续失败≥5 告警；LLM 咨询 http(`FLY64_LLM_*`)与 subagent 文件握手双传输，ConsultError 超时降级 `local_diagnosis` 写 coach_advice.json）；`plugin/watchdog.sh`（pid 检测自动重启、连续≥3 次启动失败 watchdog.log ALERT）；`scripts/consolidate.sh` 制度化连带重启自治循环。回归：`tests/test_service.py`（10 用例）+ `tests/test_autonomy_regression.py`（watchdog 沙箱/原子写出/consolidate 联动/版本契约/≥3 周期有界循环）。部署：`plugin/DEPLOY_AUTONOMY.md`（systemd / cron 两种模式）。

**v2.2.0 新增 — 神经因果链路诊断**：接入仪表板因果归因遥测（`decision_source` / `cliff_conf` / gate 门控 / 16 扇区活跃度，`causal_schema=1`）。目的：把"马里奥为什么这样动"从黑盒变为**逐 tick 可审计的因果链**——在线由仪表板决策解释卡/因果时间轴直观展示（视觉信号→神经元→判断→行动），离线由 `neural_viz_skill` 量化 cliff 误报、门控抖动、preempt 风暴与信号→行动延迟，为进化修复提供证据基础。

**v2.3.0 新增 — 自进化闭环制度化**（EVO Round 5，Brain v1.3.0）：

skill 具备**自我更新迭代**能力，通过受控进化循环固定能力：

```
1. EXECUTE      run_one_cycle() 实时仪表板数据
2. DETECT       目录未覆盖的新失败模式
3. LEARN        新 pattern 写入 default_patterns.json + 代码修复
4. PIN          回归测试固化（tests/test_evolution_capability.py，16 用例）
5. VERSION      强制递增 BRAIN_VERSION（main.py）
6. CONSOLIDATE  重启脑模型（"睡一觉"——新能力重启后才加载）。
                ⚠️ 必须用 scripts/consolidate.sh 智能重启：检测到 SM64 进程
                在位 → 完整模式接游戏桥（读 FLY64_BRIDGE env）；无游戏 →
                才回退 --synthetic。禁止无脑 --synthetic（EVO R8 事故教训：
                synthetic 重启导致视觉输入与游戏画面静默断连）
7. RECORD       agent.md 闭环总结 + 推送；仪表板 /evolution.json 实时展示。
                ⚠️ 强制（agent.md 规则 15）：同时向 skills/evolution_history.json
                追加完整结构化记录（round/date/time/kind/brain_version/
                skill_version/trigger/changes/tests/source）。常驻循环只自动
                补录 brain_update_auto（仅版本变化），完整记录必须人工/agent
                填写。校验：--history-check 必须 OK
```

**已完成的进化轮次**：

| 轮 | Brain v | 获得能力 | 触发场景 |
|:--:|:-------:|:---------|:---------|
| 1 | 1.0.0 | circle_loop 地形门控 | 无障碍转圈 |
| 2 | 1.0.x | 斜坡脱困覆盖 | 斜坡卡死 |
| 3 | 1.1.0 | 伴发放电比较器（视觉盲区）| 墙角卡死 |
| 4 | 1.2.0 | 双区对话检测 + 交互习惯化 + 场景命名 v2 + 全监控 | 钥匙门提示 |
| 5 | 1.3.0 | 交互习惯化 + 上置框双区检测制度化 | 钥匙门上置提示框 |
| 6 | 1.4.0 | 自适应反射冷却（stuck 越久冷却越短，下限 25%）+ 坠落恢复初始方向随机化（镜像交替保留）| fallen 恢复循环固定左转失效 |
| **7** | **2.0.0** | **🎨 颜色/UV 视觉 + 🌀 4方向 EMD + 🎯 小目标追踪 + 🧠 多巴胺学习**（35 新信号，覆盖 38%→90%）| FlyWire 差距分析 → AgentTeams 方案 |
| **8** | **2.1.0** | **🧭 T4/T5 式 HRC 方向选择运动检测（真运动真值）+ LC4 looming 种群化**（`hrc_asymmetry`/`hrc_right/left/up/down`/`true_hrc_asymmetry` + 16扇区×上下×左右 32键 `sector_loom`，escape 决策优先 HRC motion-truth）| MaleCNS-TrackMania 参照：亮度差分光流无方向选择性，真果蝇 T4/T5 经 Hassenstein-Reichardt 相关器实现方向选择 |
| **9** | **2.2.0** | **🏠 室内围闭度检测 + 天空蓝色度门控**（`enclosure_score`/`upper_blue` 新字段，terrain 新增 `indoor` 类，场景名新增"室内"标签，sky_score 蓝色主导门控）| 实测在建筑物内被误识别为"天空·山坡"（天花板亮度误判为天空、墙面渐变误判为斜坡）|
| **10** | **2.3.0** | **🚪 局部突围机制（local_breakout）**：micro_loop 持续 >60s → 强制 forced_bold_explore（原门控用全局 visited_cells<20 永不触发）+ bold 期间覆盖反射级联 + 门控低置信悬崖转向 + 新增 `decision_source=bold_explore` 归因 | 转圈死循环分析：497.9s micro_loop 位移 0u，突围被全局计数器锁死 |
| **11** | **2.5.0** | **🔌 神经化重构（neural refactor）**：方向性开口信号 `opening_left/right/asymmetry` → 转向池电流注入（LIF 左右竞争决策突围方向，替代 escape_x 随机）+ 位移奖励 API `report_movement()` 接入 MB 多巴胺（零位移场景被网络学习为惩罚）+ 退役低置信悬崖符号转向分支 | 转圈分析结论：用脑模型能力（感觉电流注入+MB 学习）替代继续堆叠符号判断分支 |
| **12** | **2.6.0** | **🕸️ 自治基底落成（autonomy substrate）**：plugin/service.py 10s 循环 WSL 常驻服务（pid 文件/健康自检/service_status.json 心跳/连续失败≥5 告警）+ plugin/watchdog.sh 存活监控（自动重启/连续≥3 失败 ALERT）+ LLM 咨询双传输（http 无需 DSH / subagent 文件握手，ConsultError 降级 local_diagnosis）+ consolidate.sh 制度化连带重启自治循环；自治不依赖 DSH 会话存活 | 团队 autonomy-substrate：果蝇自身能力群自治 + 教官层按需介入分层架构 |
| **13** | **2.7.0** | **🏠 对话暂停场景标签 + 蘑菇体挫折多巴胺**：`_scene_name` 优先返回"对话暂停等待 #hash"；`model.add_setback()` 外部挫折 → PPL1 式负多巴胺脉冲（新对话 episode 0.5 / 重复交互 +0.3 / 习惯化封锁 0.8），下一个 tick 由蘑菇体消费抑制 KC→MBON，学会"该场景被堵" | 锁门场景：对话发现即挫折注入，未来重访 recall 回放回避价值 |
| **14** | **2.9.0** | **🌀 自发交替 TurnAdaptation + 反射进度门控/镜像交替 + loop_score 感官卫生**（R13）| 转圈死循环：micro_loop 973s / loop_score 病态 104.9 |
| **15** | **2.9.x** | **🧱 悬崖对峙修复**：FailureMemory 切向电流 + DAN 对峙惩罚 + `cliff_standoff` 模式（R15）| 悬崖边缘驻留：转圈消除后暴露对峙层 |
| **16** | **2.10.0** | **⚡ 震荡→前进突破电流 + skill 层复明（flow.json 因果/塑形遥测）+ telemetry_gap 显式 finding + 常驻 EVO 循环（--max-iterations 0）** | 原地编织：交替消除转圈后 loop_score 仍饱和、新模式字段缺失永不命中 |
| **17** | **2.11.0** | **⚖️ MBON 饱和稳态突触缩放 + breakout_hint 反射相位调制 + DAN 信号塑形常量化**（探索奖励 0.50→0.30 压低饱和平衡点）| mb_mbon_forward=1.0 饱和 + 反射级联遮蔽突破电流 |
| **18** | **2.11.x** | **🎚️ DAN 信号塑形常量化**：多巴胺权重提升为 `DAN_*` 类级常量（单点调参），探索奖励 0.50→0.30 压低 forward MBON 饱和平衡点 | mb_mbon_forward=1.0 持续：正多巴胺再膨胀 vs 稳态缩放失衡 |
| **19** | **2.12.0** | **🔥 躁动电流 restlessness_level + 识别→行为闭环（danger_level 谨慎电流）+ 遥测小补**（fg_fraction/mb_weight_std/mb_saturation_events 入 flow.json）| 监控实况：识别"致命熔岩地"但行为无反应、悬崖边驻留 61s、novelty 枯竭 |
| **20** | **2.8.0** | **🧹 P1 神经接管（Neural Takeover）**：删除 11 个 A 类 Python 判断分支（逃逸五阶段状态机 → 反射电流+CX 转向；legacy 对话脉冲 → LLM 路径；重复流调制/novelty 网格/bold-explore/health boost 等旁路），行为回归 LIF 网络竞争决策 | 审计结论（t7-t9）：双轨并行——神经基质全部已在但被代码旁路，KPI 45→18 写入行 |
| **21** | **2.9.1** | **🤖 Coach Advice 端到端闭环**：dead key bold_turn_bias → 转向池电流接线；触发放宽（任意异常皆可突围）；prompt 语义卡（7 键单位/方向/范围）；HTTP 400 根修（裸 RGB 标 PNG→stdlib PNG 编码器）| "教练说了就算"对操作员是黑盒 → coach 链路全通 |
| **22** | **2.10.1** | **🖥️ 监控界面 P0+P1 优化**：教练策略消费折叠面板（/active_strategy.json 端点）；LLM 倒计时全局状态栏；dialogue 因果分支（⏸ DIALOGUE PAUSED）；forced_bold/reflex_ineffective 徽章；@media 800px 响应式；flow.json 双拉取合并 | t15 UI 审计：55 字段仅展示 21、llmDecisionPill 埋页尾 9-pill 堆 |
| **23** | **2.12.1** | **🛡️ 结构修复**：seqlock 停更看门狗（同帧停滞 >5s → SM64⛔ FROZEN 红色脉冲徽章）；启动契约 setsid 固化（consolidate.sh + agent.md/README.md 警示）| SM64 被托管后台 job 连带 kill → 桥冻结 → 仪表板静默卡死（事后分析发现）|

进化迭代历史在仪表板实时可见（`/evolution.json`：Brain 版本徽章、EVO 计数、每轮能力列表）。

> 当前版本：BRAIN_VERSION **2.20.4** / SKILL_VERSION **3.2.0**（… → 2.19.1 R31-fix：成功 tick 多巴胺保底 → 2.19.2 t23 逃逸释放锁死三合一修复：释放冷却 1800s→60s + 新异常立即清冷却 + fallen 越过冷却闸门 + stuck_score 去 fallen 钉死 → 2.20.3 R31-fix3：伤害负 RPE + 受击格失败记忆 + coverage 门控位移奖励（移动型困境脑机制自治修复）。完整逐轮记录见 **skills/evolution_history.json**）。

## 二期门禁：12 小时稳定自动聘雇（2026-09-14 决策）

自治服务（plugin/service.py）**连续稳定运行 ≥12 小时**（uptime 达标 + 零 watchdog ALERT + 零连续失败 + 三项健康自检通过）→ 门禁自动翻 GO → **自动开工二期薄 Cordis Tool 层**（fly64_status / fly64_consult / fly64_strategy 三个动态 Tool）。评估脚本 `scripts/phase2_gate.sh` 由 cron 每分钟驱动，结果写 `runtime/phase2_gate.json` 与 `plugin/phase2_gate.log`。取代原"稳定 1 周"门禁。

**v2.7.0 新增 — 局部突围机制 local_breakout**（EVO Round 10，Brain v2.3.0）：

memory.py forced_bold_explore 门控新增条件：`micro_loop 异常持续 >60s` 即触发突围（原条件 `全局 visited_cells<20` 在有探索史的地图上永不成立，导致死循环无解）。main.py 级联：bold 期间可覆盖活跃反射（`not reflex_override or bold_override`）、门控低置信悬崖转向分支（转圈主要贡献者）、决策归因新增 `bold_explore` 通道（优先于 anomaly_reflex）。

**v2.6.0 新增 — 室内围闭度检测**（EVO Round 9，Brain v2.2.0）：

retina.py compute_flow 新增：`enclosure_score`（围闭度：0.6×天花板信号[(1-蓝色度)×上视野结构边缘能量×8] + 0.4×墙边缘[|edge_90|+|edge_0|]×3）、`upper_blue`（上视野蓝色主导度）；`sky_score` 乘以蓝色主导门控（`min(1, upper_blue×4)`，室内天花板失去"天空"标签）；terrain 判定 `enclosure_score>0.35` 时覆盖为 `indoor`。model/main/telemetry 加法透传；场景名新增"室内"标签。实测：室内眼图（蓝地毯+深色格纹天花板+立柱）enclosure 0.39-0.42 vs 室外 0.03，分离度 13 倍。

**v2.8.0 新增 — 教官策略键消费（coach strategy keys）**（EVO Round 11，Brain v2.5.0）：

LLM 教官建议中的 strategy 参数现在直接调控行为管线（经 main.py 热重载推入 memory_ctrl）：`exploration.bold_explore_stuck_s`（micro_loop 持续多久触发突围，默认 60s）、`exploration.turn_bias`（突围转向幅度，40-80 钳位）、`escape.stuck_threshold_s`（卡住多少秒即 escape，与分数阈值并列 OR 条件）。GLM 咨询的每条建议都能落到动作参数——"说了就算"。

**v2.5.0 新增 — T4/T5 式 HRC 方向选择运动真值**（EVO Round 8，Brain v2.1.0）：
retina.py 新增 `compute_hrc()`：按 `_edge_pairs` 邻接对复用上一帧逐细胞亮度，逐对计算 Hassenstein-Reichardt 相关 `corr = lum_a(t-1)·lum_b(t) − lum_b(t-1)·lum_a(t)`，方向汇聚为 `hrc_right/left/up/down`（右移亮条 → `hrc_right>0`）与 `hrc_asymmetry`（正=左向运动多，与 `flow_asymmetry` 同号）；LC4 式 16 扇区×上/下×左/右 looming 种群 32 键（`sector_loom`）。model.py 新增 `true_hrc_asymmetry`（减去 `SELF_MOTION_K×heading_rate` 自运动分量，与 flow 同公式）与 `hrc_available`（≥2 视网膜帧预热）；main.py escape 判定在 HRC 预热后优先采用 HRC motion-truth；telemetry.py 每个 WS 行携带 `hrc_asymmetry`，帧边携带 `sector_loom`。全部加法接入，旧键未删改。

**v2.4.0 新增 — P1-P3 视觉能力体系 + 4 个新检测模式**：

进化闭环新增 4 个针对新视觉能力的检测模式：

| Pattern | 检测条件 | 诊断 | 对应能力 |
|---------|---------|------|---------|
| `color_nav_blind` | danger_red_index>0.5 + stuck>30s | 颜色调制增益不足 | P1a 颜色/UV |
| `emd_vertical_blind` | emd_on_down>0.02 + 无跳跃 | 垂直 EMD→jump 未注入 | P1b 4方向EMD |
| `target_tracking_inactive` | target_count>=1 + 无跳跃 | 拦截跳跃未触发 | P2 小目标追踪 |
| `mb_learning_stalled` | assoc_count=0 + 运行>120s | 多巴胺门限未达到 | P3 蘑菇体学习 |

新能力描述：
- **颜色感知**: 红/蓝/绿/UV 4通道, `danger_red_index` 熔岩避让, `sky_blue_index` 引导探索, 场景签名碰撞 10³/天→<1/年
- **4方向EMD**: Hassenstein-Reichardt 相关器模拟 T4/T5, 上下左右方向选择性 + OFF主导外部运动检测
- **小目标追踪**: LPLC1/2中心-周边运动对立 + 卡尔曼滤波 + Hungarian匹配, 移动平台拦截 30%→65%
- **蘑菇体学习**: 2000 KC稀疏编码 + 5 MBON三因子Hebbian可塑, >5000帧形成稳定经验关联

**v2.4.0 新增 — 社交能力（寻助）维度，可自我训练**：

进化闭环的第 0 步是**能力边界判定**：DETECT 发现的失败模式若属训练教官层能力（语义理解/任务规划/道具获取——果蝇自身能力群之外），不得硬解，应转入 `SEEK-HELP` 分支：

```
0. BOUNDARY     失败模式属内生能力群？否 → SEEK-HELP
   SEEK-HELP     生成结构化求助单四要素：
                 能力缺口(需要什么) / 证据(decision_source+因果链+指标) /
                 已试方案(内生尝试及失败原因) / 期望交付(明确能力/参数/知识)
   TRAIN-SOCIAL  每次求助作为社交样本进入进化循环，量化三指标：
                 时机(该问才问，避免过早求助/硬解延误) /
                 请求质量(结构完整度、证据充分性、教官一次响应率) /
                 成果转化(获得能力是否真正修复问题)
```

社交能力与其他能力一样在 patterns 进化循环中被训练——训练目标：**求助更少但更准**（内生能力边界随教学成果外推，社交调用频率下降而单次价值上升）。求助单写入 `seek_help/` 目录，响应结果回填评分；因果可视化（`decision_source` 分布异常）即"超出内生能力"的客观触发信号。

## When to Use

Use this skill when:
- Mario is stuck in a behavioral loop (circling, ramp trap, oscillation)
- Coverage rate is stagnating
- Health score consistently low
- You need automated diagnosis of motion problems
- You want the system to self-improve over time

## How to Use

### Quick Start
```bash
# Run one diagnosis cycle manually
python3 -m fly64.skills.evolution_skill

# Continuous monitoring with auto-fix
python3 -m fly64.skills.evolution_skill --auto-fix --interval 5 --max-iterations 100
```

### Python API
```python
from fly64.skills.evolution_skill import EvolutionPipeline

pipeline = EvolutionPipeline(
    dashboard_url="http://127.0.0.1:8765",
    patterns_path="default_patterns.json",
    auto_fix=True
)
result = pipeline.run_one_cycle()
print(f"Findings: {len(result.findings)}")
print(f"Fix applied: {result.fix_applied}")
```

### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--interval` | 5 | Poll interval in seconds |
| `--window` | 120 | Rolling window in seconds |
| `--auto-fix` | false | Auto-apply generated fixes |
| `--max-iterations` | 10 | Max cycles before stopping |
| `--dashboard` | http://127.0.0.1:8765 | Dashboard URL |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                 EvolutionPipeline.run_one_cycle()          │
├──────────┬──────────┬──────┬──────────┬──────────────────┤
│ Monitor  │ Diagnose │ Fix  │ Verify   │ Document         │
│ Phase 1  │ Phase 2  │ P3   │ Phase 4  │ Phase 5          │
├──────────┼──────────┼──────┼──────────┼──────────────────┤
│Fetch all │ Match    │Save  │Measure   │Auto-update       │
│endpoints │patterns  │fix   │effect    │README.md         │
│Rolling   │JSON      │with  │≥30%      │with fix history  │
│window    │Schema    │meta  │threshold │+ metrics table   │
└──────────┴──────────┴──────┴──────────┴──────────────────┘
```

## Pipeline Phases

| Phase | Component | Description |
|-------|-----------|-------------|
| 1️⃣ **Monitor** | `DataCollector` | Polls /memory.json, /flow.json, /bridge-status.json every `interval` seconds. Maintains rolling window of positions, controls, stuck_duration, coverage. |
| 2️⃣ **Diagnose** | `DiagnosisEngine` | Evaluates 4 anomaly patterns against collected data. Each pattern has JSON Schema-validated conditions with threshold justification. Confidence scoring via condition match ratio. |
| 3️⃣ **Fix** | `FixCatalog` | Logs fix with unique ID, timestamp, pattern reference, baseline stuck_duration. Supports auto-fix and manual-approval modes. Persisted to `fix_log.json`. |
| 4️⃣ **Verify** | `VerificationEngine` | After fix applied, monitors for N cycles. Effectiveness = 70% stuck_duration improvement + 30% coverage gain. Threshold: ≥30% score = effective. |
| 5️⃣ **Document** | `SelfDocumenter` | Auto-updates `README.md` with latest fix entry, effectiveness metrics table, cycle findings summary. |

## Pattern Catalog (4 Patterns)

### 🔴 high: Circle Loop
- **Detection**: wall_score<0.1, asymmetry<0.05, stuck>120s, ground_angle>0.3
- **Contradiction**: terrain=cliff but ground_angle>0.3 (not actually a cliff)
- **Root Cause**: Terrain classifier false-positive "cliff"; cliff avoidance overrides straight-forward escape
- **Fix**: Add ground_angle gate to suppress false cliff triggers

### 🔴 high: Ramp Trap
- **Detection**: ramp_score>0.5, stuck>180s, position unchanged 60s
- **Root Cause**: Ramp suppression blocks turning; Mario stays on slope indefinitely
- **Fix**: Add ramp escape override with sharp turn when stuck >180s

### 🟡 medium: Reflex Cooldown Gap
- **Detection**: anomaly_state≠idle, reflex_active=False, stuck>60s
- **Root Cause**: Reflex correctly detects anomaly but cooldown prevents re-trigger; normal escape ineffective during cooldown
- **Fix**: Reduce reflex cooldown or make adaptive

### 🟡 medium: Coverage Stagnation
- **Detection**: coverage stagnant 120s, visited_cells<50
- **Root Cause**: Mario trapped in small area; exploration strategy insufficient
- **Fix**: Force bold explore when coverage stagnates

## Effectiveness Metrics

| Metric | Description |
|--------|-------------|
| stuck_duration_ratio | Post-fix stuck_duration / baseline stuck_duration (lower = better) |
| coverage_gain | Post-fix coverage_pct - baseline coverage_pct (higher = better) |
| effectiveness_score | 0.70 × (1 - stuck_duration_ratio) + 0.30 × coverage_gain, clamped [0,1] |
| effectiveness_threshold | Score ≥0.30 = fix is effective |

## Data Flow

```
SM64 Game → Shared Memory Bridge → Fly64 Brain Model
                                       ↓
                              Web Dashboard API
                              (memory/flow/bridge/events)
                                       ↓
                              EvolutionSkill Pipeline
                              Monitor → Diagnose → Fix → Verify → Document
                                       ↓
                              fix_log.json ←→ README.md (auto-update)
                                       ↓
                              Git Commit (suggested)
```

## Files

| File | Description |
|------|-------------|
| `fly64/skills/evolution_skill.py` | Core skill module (~730 lines) |
| `fly64/skills/default_patterns.json` | 4 patterns with JSON Schema |
| `fly64/skills/README.md` | Auto-generated documentation |
| `fly64/skills/__init__.py` | Package exports (13 symbols) |
| `fly64/skills/evolution_agent.py` | v1 legacy agent |

## Dependencies

- Python 3.10+
- `jsonschema` (optional, for pattern validation)
- Fly64 dashboard at http://127.0.0.1:8765

---

# 附：神经因果链路遥测扩展（v2.2.0，P0–P3 已全量上线）

> 来源：`fly64/docs/causal-chain-implementation.md` + `docs/causal-chain-final-review-t8.md`（GO 评审）。**当前状态：已部署生效**（commits 6bbf5be P0 / 7d5eba0 P1 / 813b74a P2 / 4e4cd00 P3，基线 tag `causal-baseline`）。telemetry row 新增字段为 **schema=3 加法演进**（meta 携带 `causal_schema=1` 哨兵），对现有 `DataCollector` / `evolution_agent.py` 完全透明（旧代码用 `.get()` 只取自己关心的键，新增键不破坏任何既有断言）。

## 已上线的遥测字段（实测验证）

### WebSocket packet rows（每 tick 行，仪表板主数据通道）
| 字段 | 类型 | 含义 |
|---|---|---|
| `decision_source` | str | 控制级联胜出者，与当 tick 实际下发的 control 严格一致：`dialogue > cliff_reflex > anomaly_reflex > escape > collision > jump > steering` |
| `cliff_conf` / `stuck_conf` | float 0–1 | cliff/stuck 判断置信度（透传 `memory_ctrl`） |
| `cliff_confirmed` | bool | 多帧悬崖确认（`model.cliff_confirmed`） |
| `gate_forward` / `gate_jump` | bool | 门控判定（0.4 Hz / 2.0 Hz，与渲染阈值同源） |

### WebSocket packet rows（仅新帧行，10Hz 帧沿）
`sector_contrast` (int[16] 0–100，显示空间 8 方位×上下分带)、`sector_active` (uint16 bitmask，阈值 >2/255)；meta 新增 `causal_schema=1` 哨兵键（特性检测用）。

> 注意：`/history.json` 端点是独立的 1Hz 内存端点，**不携带**上述因果字段；因果数据在 WS packet（`ws://127.0.0.1:8766/`，F643 二进制）中。实时探针：`python3 tests/ws_probe.py 8766 /`。

## DataCollector 采集配置示例（Monitor Phase 增强）

```python
# evolution_skill.DataCollector：因果字段走 WS packet rows（不走 /history.json）。
# 容错透传（缺字段默认值保证旧 packet 不抛错）：
s = SensorSample(...,
    decision_source=row.get("decision_source", "steering"),
    cliff_conf=row.get("cliff_conf", 0.0))
# 特性检测：meta.get("causal_schema") >= 1 即因果字段可用
```

新技能 `neural_viz_skill` 的采集配置（独立运行，不侵入 EvolutionPipeline）：

```python
from fly64.skills.neural_viz_skill import CausalRecorder
rec = CausalRecorder(window_seconds=300)     # 每 interval 调 rec.poll_once()
# 或命令行： python3 -m fly64.skills.neural_viz_skill --duration 120 --record causal_log.jsonl
```

## neural_viz_skill — 离线因果链路分析与报告

**Version**: 1.0.0 · **Status**: Active · **Category**: Offline Analysis / Causal Diagnostics

### When to Use
- 需要回答"某次 escape/cliff_reflex 是由什么信号触发的"（事后取证）
- 统计 decision_source 分布、preempt 风暴、门控抖动、cliff 误报
- 录制因果行 JSONL 供离线重放（无需 dashboard 在线）

### Quick Start
```bash
python3 -m fly64.skills.neural_viz_skill --duration 120 --record causal_log.jsonl
python3 -m fly64.skills.neural_viz_skill --input causal_log.jsonl --report report.md
```

### Analysis Capabilities
| 分析项 | 方法 | 判据 |
|---|---|---|
| cliff 误报 | `cliff_false_positives()` | `decision_source=cliff_reflex` 且 conf<0.5 / 未 confirmed（与 circle_loop 模式同源矛盾检测） |
| 门控抖动 | `gate_flap_rate()` | 翻转率 >40% → 建议加滞回 |
| preempt 风暴 | `source_distribution()` | steering 占比 <30% → 反射/逃脱黏滞 |
| 信号→行动延迟 | `signal_to_action_latency()` | cliff 上升沿到首个 x 翻转 >0.5s |

输出 Markdown 报告（`neural_viz_report.md`）：分布表、preempt 事件列表、findings（severity/id/detail）。

### Verification（与 evolution_agent.py 兼容性验证）
```bash
# 1. 新技能自检：用 mock JSONL 离线跑通（无需 dashboard）
python3 -m fly64.skills.neural_viz_skill --input mock_causal.jsonl --report /tmp/r.md && echo OK

# 2. 兼容性：新增字段不破坏既有技能 —— 旧消费者逐键 .get()，键集只增不减；
#    回归跑一轮 evolution 管线确认 findings 数量与 fix_log 行为不变
python3 -m fly64.skills.evolution_skill --max-iterations 1

# 3. 字段契约（已落地的 pytest）：
#    tests/test_dashboard_protocol.py::test_causal_fields_present_json_safe_and_degrade
#    断言 decision_source ∈ 枚举(含 collision/dialogue) / 仅帧行携带 sector_* / allow_nan=False JSON 安全

# 4. 在线探针（仪表板运行时）：
python3 tests/ws_probe.py 8766 /      # 打印 causal_schema / decision_source / sector_active
```

## 仪表板因果组件降级开关（回滚保障）

全部因果组件携带 `causal-ui` CSS 类。`?noviz=1`（或 `localStorage['fly64.causal']='off'`）一键隐藏决策解释卡/时间轴/扇区叠加/回放控件，恢复基础布局；`dashboard.js` 渲染入口 try/catch 隔离，因果异常不短路既有 render() 管线。详见 `docs/causal-chain-rollback-plan.md`（7 症状→嫌疑文件→回退命令）。

## Files（更新）

| File | Description |
|------|-------------|
| `fly64/skills/evolution_skill.py` | Core skill module (~730 lines) |
| `fly64/skills/default_patterns.json` | 4 patterns with JSON Schema |
| `fly64/skills/README.md` | Auto-generated documentation |
| `fly64/skills/__init__.py` | Package exports (13 symbols) |
| `fly64/skills/evolution_agent.py` | v1 legacy agent |
| `fly64/skills/neural_viz_skill.py` | **新增**：离线神经因果链路分析与报告（CausalRecorder / CausalAnalyzer / Markdown 报告） |
| `fly64/web/dashboard.js` | 因果链前端：explain()/judgeText() 决策解释卡、drawSectors 扇区叠加、drawTimeline 四泳道时间轴 + ringBuffer、因果弧线、`?noviz=1` 降级开关 |
| `fly64/tests/ws_probe.py` | WS packet 实时探针（验证 causal_schema/decision_source/sector 字段上线） |

## Trigger Keywords（追加）

- neural viz, causal chain, decision source, preempt, cliff false positive, causal timeline, noviz, 因果链路, 神经可视化, 离线分析, 决策溯源, 因果时间轴, 回放

---

## Trigger Keywords

- evolution, self-improve, diagnose motion, stuck analysis, circle loop problem
- Mario stuck, behavioral analysis, auto-fix, motion health
- 进化, 自改进, 运动诊断, 卡住分析, 闭环优化