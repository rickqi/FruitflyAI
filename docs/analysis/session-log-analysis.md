# Fly64 果蝇脑模型项目 — 会话日志综合分析报告

> **生成时间**: 2026-09-24  
> **数据来源**: D:\codes\flygym\export logs 中的 12 个 DSH 会话日志（11 个唯一会话 ID）  
> **数据可靠性说明**: t1 提取的 `toolCallTotal` / `toolCalls` 聚合计数因编码缺陷误差达 122×（实测单会话 f953d3fd 即有 2443 条 `tool/call`，t1 报为 20），本报告**不引用** t1 的聚合工具计数。使用的定量数据来自：原始 jsonl 重新统计、文件变更清单、时间戳、会话大小、turn/step 数、子代理数。定性数据来自主题标签和代码审查。  
> **数据来源分级**:
>   - 🟢 **基于当前代码**: 文件存在性、file:line grep 结果（已验证的当前代码状态）、`evolution_history.json` 记录
>   - 🟡 **基于会话日志**: 会话标题、时间线、文件变更历史、turn/step 计数、子代理数量、Evo 版本标识符
>   - 🔵 **基于推断**: 主题分类、阶段划分、"机制存在、报告成功、无法生效"模式归纳、修复状态标注

---

## 1. 项目全景概览

### 1.1 会话总览（按时间线排列）

| # | 会话 ID (前8位) | 原始标题 (截取) | 日期 | 大小 | turn | 子代理 | 核心主题 |
|:-:|:---------------|:---------------|:----:|:----:|:----:|:-----:|:--------|
| 1 | f953d3fd | 安装 FlyGym v2 + 脑模型初始搭建 | 09-10 18:44 | 33.4 MB | 508 | 58 | 环境搭建/基础设施/脑模型初探 |
| 2 | d983cef5 | 仪表板视觉增强 + 门禁机制 | 09-13 12:33 | 12.7 MB | 86 | 14 | 门禁机制/仪表板/LLM 咨询 |
| 3 | 38542b1c | 脑模型能力缺陷审计报告 | 09-13 19:07 | 40.2 MB | 210 | 16 | 全面审计/CX导航/MB饱和/场景识别 |
| 4 | 90dd512b | Evo skill 状态检查与模式分析 | 09-13 20:43 | 29.5 MB | 65 | 1 | Evo闭环/本能绑定/回归检测 |
| 5 | b2eeed98 | 监控界面布局优化+轨迹可视化 | 09-14 23:26 | 17.3 MB | 58 | 0 | Dashboard UI / 可视化 |
| 6 | 1f8fbe04 | Coach 执行策略全链路验证 | 09-15 15:55 | 12.2 MB | 119 | 14 | Coach/多巴胺/策略穿透 |
| 7 | 27ed0979 | 行为→结果→多巴胺信号闭环 | 09-15 23:21 | 14.3 MB | 53 | 0 | 运动基元/神经接管/多巴胺重塑 |
| 8 | fdb47617 | 文档全面分析 → 综合指南 | 09-15 23:21 | 3.0 MB | 11 | 0 | 文档聚合/技术方案 |
| 9 | 99cab60f | 启动脑模型 (×2 次导出) | 09-16 20:28 | 2.9+2.9 MB | 7+7 | 0 | 环境启动/桥接脚本 |
| 10 | ed4b8026 | 分析导出日志报告 | 09-20 20:49 | 3.0 MB | 9 | 4 | 日志分析/会话元分析 |
| 11 | 71c21f6d | AgentTeams 会话日志分析 | 09-20 23:36 | 0.6 MB | 16 | 3 | 会话日志分析/团队治理 |

### 1.2 规模特征

| 指标 | 总量 |
|:----|:----:|
| 原始 jsonl 数据 | ~171 MB |
| 原始 jsonl 行数 | ~405,400 行 |
| 工具调用 (tool/call) | 经实测算，单会话最高 2,644 次，11 个活动会话合计 >10,000 次 |
| 文件变更 (write/edit) | 818 项（可靠字段） |
| 消息总数 | 1,805 条（可靠字段） |
| 子代理 | 110+ 个（横跨 7 个会话） |
| GitHub 工作流 CI | 1 个 (.github/workflows/ci.yml) |

---

## 2. 主题领域划分

### 领域 A：神经系统行为修复与增强 🧠
**覆盖会话**: f953d3fd, d983cef5, 38542b1c, 90dd512b, 1f8fbe04, 27ed0979, b2eeed98  
**占项目比重**: 约 60% 的消息量与文件变更

#### 核心子模块

**A1 — Central Complex 导航（CX 16-列环形吸引子）**
- **涉及会话**: 38542b1c, 90dd512b, 1f8fbe04
- **核心文件**: `central_complex.py`, `memory.py`, `model.py`
- **关键变更**:
  - `central_complex.py`: P0 修复 steering_bias 复位逻辑、goal_competition 重构、CX-3 多向量竞争
  - `memory.py`: StuckDetector 三信号检测机制、SpatialMemoryMap 新颖性衰减
  - `model.py`: 逃逸方向提交机制、前向增益自适应
- **关键决策点**:
  - P0: threshold_bug（阈值与电流签名不匹配导致 MB 无法学习）
  - P1: 接管电流注入 → 减少 `control.x` 直接写入从 34 处降至 22 处
  - CX-2 锚点积分漂移 → 视觉重定位校正方案（未完成）
- **当前状态**: 🟡 **部分解决** — P0/P1 已修复并部署，但 CX-2 漂移/垂直维度缺失/逃逸位移≈0 仍未完全解决

**A2 — Mushroom Body 学习与多巴胺信号**
- **涉及会话**: 38542b1c, 1f8fbe04, 27ed0979
- **核心文件**: `mushroom_body.py`, `memory.py`, `model.py`
- **关键变更**:
  - `mushroom_body.py`: MBON 饱和修复（P0-2）、DAN 塑形
  - `memory.py`: 多巴胺信号 R-P 综合计算、temporal_energy 计算
  - `model.py`: 奖励重塑（R31-fix3）
- **当前状态**: 🟢 **已解决** — 饱和问题已修正，多巴胺闭环验证通过

**A3 — 视网膜视觉处理**
- **涉及会话**: 38542b1c, d983cef5, f953d3fd
- **核心文件**: `retina.py`, `scene_recognition.py`, `optic_flow`
- **关键变更**:
  - `retina.py`: 场景识别标签 gap 修复、optic_flow 优化
  - 测试文件: `test_optic_flow.py`, `test_retina.py`
- **当前状态**: 🟡 **部分解决** — 基础视觉处理可用，但多眼视觉方案待实现

**A4 — 反射与本能行为**
- **涉及会话**: 38542b1c, 90dd512b, 27ed0979
- **核心文件**: `instinct_bindings.py`, `model.py`, `bridge.py`
- **关键变更**:
  - `instinct_bindings.py`: 新文件 — 本能行为绑定系统（evo061）
  - `bridge.py`: 桥接协议修复、WSL 通信
  - 测试: `test_instinct_bindings.py`, `test_reflex_jitter.py`
- **当前状态**: 🟢 **已解决** — 本能绑定已实现并部署

---

### 领域 B：P4 自我进化闭环 🔄
**覆盖会话**: 38542b1c, 90dd512b, 1f8fbe04, 27ed0979  
**占项目比重**: 约 20% 的文件变更

#### 核心组件

**B1 — Evolution Skill**
- **核心文件**: `skills/evolution_skill.py`, `skills/default_patterns.json`, `skills/brain_tunable_params.json`
- **关键变更**:
  - `evolution_skill.py`: 多次迭代（从 P0 到 evo071）
  - `default_patterns.json`: 模式库扩展
  - `brain_tunable_params.json`: 可调参数清单
- **关键决策点**:
  - Evo 版本演进: evo059 → evo061 → evo062 → evo064 → evo065 → evo066 → evo067 → evo068 → evo071（共 9 次迭代）
    - **来源说明**: 该列表源自会话日志中的文件创建历史（`write_evo059.py` → `write_evo071_full.py` 等临时脚本），其中 evo060/063 在会话中未独立出现。
    - **可验证性**: ✅ `fly64/skills/evolution_history.json` 确含 EVO-059 至 EVO-073 的完整记录（65 条 EVO 记录 + 16 条 AUTO 记录），EVO-059~071 均可在该文件中定位。
    - **审查证据更正（M2, 2026-09-24）**: t4 核验报告声称 `evolution_history.json` 仅 3 条（EVO-001~003）。**该审查证据有误** — 实际该文件含 **81 条总记录、65 条 EVO 记录**（EVO-001 至 EVO-073，部分序号因版本分类跳过），EVO-059 至 EVO-071 全部存在。t2 的"9 次迭代"声称**成立**，不构成缺陷。
  - Phase 6 零分问题 → 属性函数修复
  - 回归检测器: `scripts/check_regressions.py`, `tests/test_regression_detector.py`
- **当前状态**: 🟡 **运行中** — Evo 闭环已实现自动化运行，Phase 6 评分正常，但`"机制存在、报告成功、无法生效"`模式反复出现

**B2 — Coach 策略系统**
- **核心文件**: `plugin/coach_outcomes.py`, `plugin/llm_consult.py`, `plugin/runner.py`
- **关键变更**:
  - `coach_outcomes.py`: 新文件 — 策略结果记录
  - `llm_consult.py`: 咨询上下文修复（pos_y 注入 m8）、GLM 协议调整
  - `runner.py`: 多次迭代 — 守护进程管理
- **关键决策点**:
  - 策略穿透修复（fix5-fix12）
  - LLM 咨询协议修复
- **当前状态**: 🟡 **运行中** — 策略系统可运行，但存在"策略产生但无法生效"的问题

**B3 — 门禁与自治机制**
- **核心文件**: `plugin/watchdog.sh`, `plugin/service.py`, `scripts/phase2_gate.sh`
- **关键变更**:
  - Uptime 门禁（phase2_gate）
  - Watchdog 修复
  - 自治模式部署脚本
- **当前状态**: 🟢 **已解决** — 门禁与看门狗工作正常

---

### 领域 C：基础设施与部署 ⚙️
**覆盖会话**: f953d3fd, d983cef5, 99cab60f, fdb47617  
**占项目比重**: 约 10%

#### 核心组件

**C1 — 环境搭建与构建**
- **核心文件**: `start_fly64.sh`, `start_fly64_wsl.sh`, `launch_full.sh`, `scripts/*.sh`
- **关键变更**:
  - WSL ↔ Windows 桥接脚本
  - SM64 ROM 构建脚本（C 补丁）
  - 屏幕捕获管道修复（m4）
- **当前状态**: 🟢 **已解决** — 环境可正常启动运行

**C2 — CI/CD**
- **文件**: `.github/workflows/ci.yml`
- **关键变更**: CI 工作流建立（含 WSL 兼容性检测）
- **当前状态**: 🟢 **已解决**

**C3 — 部署脚本体系**
- **数量**: 50+ 个脚本（`scripts/`, `tests/`, `.tmp/`）
- **模式**: fixN_deploy_restart.sh / ver_append_fixN.py / mN_deploy_restart.sh
- **典型流程**: 问题检测 → 追加补丁脚本 → 部署重启 → 验证
- **当前状态**: 🟡 **维护中** — 脚本体系庞大但缺乏统一治理

---

### 领域 D：仪表板与可视化 📊
**覆盖会话**: d983cef5, b2eeed98, f953d3fd  
**占项目比重**: 约 8%

#### 核心组件

**D1 — Web Dashboard**
- **核心文件**: `web/index.html`, `web/dashboard.css`, `web/dashboard.js`
- **关键变更**:
  - 布局优化（session-b2eeed98）
  - 监控预览面板新增
  - 因果链可视化
  - Evo 参数面板（evo-params.html）
- **当前状态**: 🟢 **已解决** — 仪表板正常工作

**D2 — 轨迹可视化**
- **核心文件**: `web/trajectory.html`
- **关键变更**: 轨迹 HTML 页面创建与修复
- **当前状态**: 🟢 **已解决**

---

### 领域 E：系统诊断与工具链 🔍
**覆盖会话**: 全部 11 个会话  
**占项目比重**: 约 5%

#### 核心组件

**E1 — 诊断工具**
- **工具文件**: 30+ 个临时诊断脚本（`.tmp/` 目录）
- **典型用途**: 脑模型状态检查、桥接诊断、ML 性能分析
- **当前状态**: 🟡 **维护中**

**E2 — 回归检测**
- **文件**: `scripts/check_regressions.py`, `tests/test_regression_detector.py`
- **功能**: Linux/Windows 基准线分类、桥接大小监控
- **当前状态**: 🟢 **已解决**

---

### 领域 F：文档与知识管理 📝
**覆盖会话**: fdb47617, ed4b8026, 71c21f6d  
**占项目比重**: 约 5%

#### 核心组件
- `docs/analysis/fly64_brain_model_comprehensive_guide.md` — 综合技术指南
- `docs/analysis/insurance/` — 保险领域分析（8 份文档）
- `docs/analysis/motor-expansion/` — 运动扩展分析（5 份文档）
- `agent.md` — 代理配置文件
- **当前状态**: 🟢 **已建立** — 但需持续更新

---

### 领域 G：AgentTeams 协作治理 🤝
**覆盖会话**: 71c21f6d, ed4b8026（以及本分析团队）  
**占项目比重**: 约 3%

- 多代理团队协作模式（captain + 多个 worker）
- 依赖链管理（t1 → t2 → t3）
- **当前状态**: 🟢 **新建立** — 2 个专门的治理会话

---

## 3. 阶段演化分析

### 阶段 1: 奠基期（09-10 → 09-13 中午）
**代表会话**: f953d3fd (第一会话)

- **核心活动**: FlyGym 环境安装、SM64 桥接搭建、脑模型骨架创建
- **产出**:
  - brain model Python 包 (`fly64/`)
  - Web dashboard 第一版
  - 技能系统 (`skills/`) 原型
  - CI 工作流
- **元特征**: 单会话 508 turns / 58 子代理，体现"从零搭建"的密集开发
- **转折点**: 环境搭建完成后转向脑模型能力探索 → 进入审计阶段

### 阶段 2: 全面审计期（09-13 中午 → 09-14 凌晨）
**代表会话**: d983cef5 → 38542b1c → 90dd512b

- **核心活动**: 系统性缺陷审计、视觉增强、门禁机制
- **关键发现**:
  - MBON 饱和问题（P0-2）
  - Threshold bug（P0-3）
  - 11 层逃逸嵌套但位移≈0
  - CX 导航锚点漂移
- **产出**:
  - `docs/analysis/insurance/brain-code-audit-report.md`
  - `docs/analysis/insurance/brain-comprehensive-review.md`
  - P0-P4 修复路线图
- **元特征**: 连续 3 个高强度会话（40+29+12 MB），产生 284 项文件变更
- **转折点**: 审计报告定稿 → 转向分阶段修复执行

### 阶段 3: 修复迭代期（09-14 → 09-16）
**代表会话**: b2eeed98 → 1f8fbe04 → 27ed0979 → fdb47617

- **核心活动**: Dashboard UI 优化、Coach 策略全链路验证、多巴胺信号闭环、运动基元扩展
- **修复迭代序列**:
  - fix1-fix5: 桥接/多巴胺/屏幕/坠落/探针（session-27ed0979）
  - fix6-fix12: 卡坡/教练/pos_y/循环/策略穿透（session-1f8fbe04）
  - evo059-evo071: 进化技能版本迭代
- **元特征**: 3 个深度修复会话，产生 49+146+22 项文件变更
- **转折点**: fix12 部署完成 → 转向文档汇总和知识沉淀

### 阶段 4: 总结沉淀期（09-16 → 09-20）
**代表会话**: 99cab60f → ed4b8026 → 71c21f6d

- **核心活动**: 环境验证、日志分析、AgentTeams 治理
- **产出**:
  - `docs/analysis/fly64_brain_model_comprehensive_guide.md`
  - `docs/analysis/session-log-summary.json`（t1，待修正计数）
- **元特征**: 低强度会话（2.9-3.0 MB），关注知识沉淀和元分析
- **转折点**: 从功能开发转向治理反思 → 当前日志分析（本任务）

### 演化总图

```
奠基期 ──→ 全面审计期 ──→ 修复迭代期 ──→ 总结沉淀期
09-10       09-13          09-14→09-16    09-16→09-20
  │            │               │               │
  │     MBON饱和发现     P0-P4修复      文档聚合
  │     CX漂移发现       fix1-fix12      AgentTeams治理
  │     逃逸嵌套发现     evo059-071     日志元分析
  ↓            ↓               ↓               ↓
[环境搭建]  [缺陷图谱]      [迭代修正]      [知识固化]
```

---

## 4. 核心模式识别：机制存在、报告成功、无法生效

### 4.1 模式定义

一种反复出现的缺陷类型，其特征为：
1. **机制存在**：代码中实现了某个功能模块
2. **报告成功**：运行日志/测试报告显示"成功"
3. **无法生效**：实际行为不符合预期（位移=0、信号被覆盖、常量不一致）

### 4.2 出现频率与分布

基于项目文档和代码审查，识别出 **12 个** 典型案例：

| # | 模式实例 | 涉及文件 | 会话引用 | 修复状态 |
|:-:|---------|:--------:|:--------:|:--------:|
| 1 | **逃逸位移≈0**：11 层脱困嵌套但左右转向抵消 | `model.py`, `memory.py` | 38542b1c | 🔄 方向提交已实现，需端到端验证 |
| 2 | **MBON 饱和**：学习报告成功但权重无法更新 | `mushroom_body.py`, `model.py` | 38542b1c | ✅ P0-2 已修复 |
| 3 | **Threshold 签名不匹配**：阈值检测存在但不生效 | `model.py` | 38542b1c | ✅ P0-3 已修复 |
| 4 | **Phase 6 零分**：Evo 评分报告成功但实际 fitness=0 | `skills/evolution_skill.py` | 90dd512b | ✅ 属性函数修复 |
| 5 | **策略穿透失败**：Coach 产生策略但 control 不生效 | `plugin/coach_outcomes.py`, `main.py` | 1f8fbe04 | 🔄 fix5-fix12 部分修复 |
| 6 | **桥接读取空数据**：bridge 报告连接成功但无数据 | `bridge.py` | f953d3fd | ✅ 桥接协议修复 |
| 7 | **场景标签 gap**：scene_recognition 报告识别但标签错位 | `scene_recognition.py` | 38542b1c | ✅ 已修复 |
| 8 | **StuckDetector fallen 钉死**：fallen 信号=1 持续不衰减 | `memory.py` | 90dd512b | ✅ t23 fix③ |
| 9 | **GLM 咨询空上下文**：LLM 咨询成功但无 pos_y 信息 | `llm_consult.py` | 90dd512b | ✅ m8 已修复 |
| 10 | **Loop score 饱和**：spin loop 检测报告成功但分数停滞 | `memory.py` | 90dd512b | ✅ 循环检测修复 |
| 11 | **骨架技能空数据**：skill 加载成功但数据为空 | `skills/` | 1f8fbe04 | ✅ evo 版本修复 |
| 12 | **Screen capture 空帧**：截图报告成功但返回空白 | `bridge.py` (m4) | 27ed0979 | ✅ 屏幕补偿修复 |

### 4.3 典型修复路径

对 12 个案例的修复模式总结：

```
1. 检测阶段（日志审查 + 测试断言）
   ↓
2. 根因定位（信号链追查 → 发现"报告层"与"执行层"解耦）
   ↓
3. 修复方案（添加跨层校验、统一常量源、添加 fallback）
   ↓
4. 部署验证（ver_append + deploy_restart + live_check）
```

> **特殊案例 — 逃逸方向提交（#1, M5 勘误 2026-09-24）**: 
> - 代码中已实现方向提交机制：`model.py` L791-799（初始化 `_escape_commit_timer`/`_escape_commit_dir`/`_escape_commit_ticks`）、L1941-1953（commit 逻辑：选择方向 → 保持 1s → 增强同侧压制对侧）
> - 但**缺乏可独立验证该机制端到端生效的测试**（当前测试套件中无 `test_escape_direction_commit` 或类似用例）
> - 当前状态更准确的表述为：**"方向提交已实现（代码可见），但端到端生效验证待确认"**

**常见根因分类**：

| 根因类型 | 出现次数 | 示例 |
|:---------|:--------:|------|
| 常量/签名不匹配 | 3 次 | MBON threshold, telemetry keys, steering bias |
| 信号层解耦 | 4 次 | control.x bypass, Coach→control gap, 桥接空数据 |
| 状态未复位 | 2 次 | StuckDetector fallen pin, Loop score saturated |
| 数据未传递 | 2 次 | GLM context, Scene label gap |
| 方向互消 | 1 次 | 逃逸位移≈0 |

### 4.4 持续性风险

"机制存在、报告成功、无法生效"模式的**高复发率**提示架构性问题：

- **缺乏契约审计**：报告的"成功"不一定对应实际行为正确
- **测试覆盖不足**：测试通常验证"机制触发"而非"行为生效"
- **集成验证缺失端到端断言**：各模块独立测试通过后，组合运行时可能有互消

**改进建议**: 实施 `契约审计`（如 `tests/test_coach_contract.py` 所示范的写法），每个模块除单元测试外增加端到端行为断言。

---

## 5. 当前困境清单

以下 5 个问题来自最新会话和代码审查，按紧迫程度排序：

### 困境 1 🔴: Telemetry 常量分歧（magic numbers 散落）

- **证据**:
  - `remaining-issues-analysis.md` 详细列出 8 组 magic numbers，如 0.12（8 次出现，至少 4 种语义）、0.15（14 次出现）
  - 具体位置：`model.py` 中预尖峰电流注入系数散落于 CX 转向/Target 转向/sky_jump/restlessness 等多处
- **影响**: 可维护性灾难。调参需逐行理解语义，极易引入不匹配。**虽不产生运行时错误，但长期将导致 drift**
- **会话引用**: session-38542b1c（脑模型能力缺陷审计报告）
- **代码位置**: `fly64/fly64/model.py` — 多处 `0.12`, `0.15`, `0.20`, `0.25`, `0.35` 等硬编码浮点
- **建议**: 抽取为类常量（CX_STEERING_GAIN, TARGET_TURN_GAIN, SKY_JUMP_GAIN 等），预计 1 小时纯重构

### 困境 2 🔴: CX-2 锚点积分漂移 — 导航在 60 秒后失效

- **证据**:
  - `central_complex.py` 中 `_self_motion_update()` 使用 heading_rate 开环积分。
  - 🔧 **t5 勘误（2026-09-26，M-6）**：本条原文写「**无视觉闭环校正**」——**该表述对当前代码已过时**。实测 `AnchorPathIntegrator.relocalize(scene_id, confidence)` **已存在**（`fly64/fly64/central_complex.py:128-140`，`relocalize_gate=0.8` / `relocalize_strength=0.3`，维护场景记忆 `scene_id → (disp_x, disp_z, confidence)`），**调用点两处**（`:529`、`:673`），并有测试 `fly64/tests/test_cx_navigation.py:179-204`。⇒ 结论应更新为「**机制已存在（代码可见 + 有测试）；活体生效（命中率、`scene_id` 类型匹配）尚未验证**」，而不是"无机制"。
  - 漂移推导：heading_rate 误差 ~0.05 rad/s → 60 秒后漂移 3000u（SM64 世界 ~8000u 的 37.5%）
- **影响**: 长时间导航不可靠。30 秒后开始明显偏离，60 秒后方向感基本失效
- **会话引用**: session-38542b1c（`remaining-issues-analysis.md` 第 3 节）
- **代码位置**: `fly64/fly64/central_complex.py` → `_self_motion_update()` 方法
- **建议**: 实现视觉重定位校正（场景识别匹配 → heading/bias 校正），需修改 `scene_recognition.py` + `central_complex.py`

### 困境 3 🟡: StuckDetector `rate_threshold` 单位混淆风险

- **证据**:
  - `memory.py` L135（**2026-09-24 时点**）: `rate_threshold: float = 5.0` — 单位标注为 `Hz`。🔧 **t5 勘误（2026-09-26，M-6）**：当前代码该行已改为 **`rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`**，`:207-208` 比较式亦带显式单位注释「both sides are per-tick fractions ∈ [0,1] (see RULE-19)」⇒ **"单位标注/量纲"这一半已解决**。⚠️ **但可观测性未解决**：`docstring:127` **仍写**「forward_rate collapses (**< 5 Hz** for >3 s)」（半迁移）；且 `rate` 子信号（`forward_rate < 0.008` 连续 3 s）在 idle 片段即可把 `stuck_score` 拉满 —— 实测 12:54:31–12:55:01 **六连** `stuck_score = 1.0` 而同刻 `stuck_duration = 0.0`（根因：`memory.py:234-235` 的 `disp_60s > 500` 泄放把 `_stuck_duration` 一次抹回 0，而增长仅 `+0.02/tick`）。
  - 但实际使用中，`forward_rate` 的物理含义存在歧义：是"动作频率"还是"位移速率"？
  - 不同测试用例中使用不同阈值：`test_memory.py` 中 `rate_threshold=5.0` vs `rate_stuck_s=3.0`
  - 与 `StuckDetector` 文档字符串（L127）的描述"forward_rate collapses (< 5 Hz for >3 s)"一致吗？
- **影响**: 若单位混淆不解决，在不同环境中（不同帧率）可能产生误判
- **会话引用**: session-90dd512b, session-38542b1c
- **代码位置**: `fly64/fly64/memory.py` L135-L143, L206-L217（🔧 **t5 勘误**：当前实测关键行为 L135 定义 / L142 赋值 / L208 比较 / L213-225 三子信号取 `max` / L228-231 duration ±dt / L234-235 泄放；`rate_threshold` 全文件仅出现于 **135/142/208** 三处）
- **建议**: 添加明确的单位注释 + 运行时断言验证 `forward_rate` 的量级范围。🔧 **t5 勘误（M-2c/M-5）**：① **单位注释 ✅ 已实现**（L135 与 L207-208）；② **运行时断言 ❌ 未实现** —— `memory.py` 全文 **`assert` 计数 = 0**（`rate_threshold` 仅 135/142/208 三处）⇒ 该项应记为「半闭环：单位口径闭环 / 可观测性未闭环」；③ 真正的待办是修 `rate` 子信号语义与 `disp_60s` 泄放，使「`stuck_duration == 0` 时 `stuck_score` 不得为 1.0」可被断言

### 困境 4 🟡: `control.x` 直接写入 — Python 旁路（当前实测 10 处字面赋值/main.py）

> **勘误（M1, 2026-09-24）**: 原始版本引用「22 处」来自历史文档 `remaining-issues-analysis.md` 的逻辑分类计数（按 bypass 场景：Reflex 6 + LLM 11 + Fallen 6），其行号指向 09-13 版本的 main.py，**当前代码已漂移**。以下使用当前代码（2026-09-24）实测数据。

> 🔧 **t5 勘误（2026-09-26，M-6）— 两处必须先读**：
> ① **计数正则必须带"非比较"守卫**：本节的写点口径应为 **`control\.x\s*=(?!=)`（赋值口径）**。若用朴素正则 `control\.x\s*=`，会把 `main.py:2618`（`and control.x == 0 and control.y < 8`）与 `main.py:2959`（`"control_x_zero": control.x == 0,`）两处**比较**计入，得 **12** 而非 10 —— 这正是此前 t2 误判「A4 恶化 10→12」的伪影来源（本文件下方 L415 的复现代码已同步更正）。
> ② **行号已整体漂移 +112~+120**：本文 09-24 版列出的 10 个写点行号与当前实测行号不同（见下表 t5 列）。**窗口前后（`2f87d77^` = `HEAD` = 工作区）三处均为 10 处 ⇒ A4 未恶化**。

- **"旁路"的可复现定义**: `control.x` **写点（赋值）** — 即 Python 代码中直接给 `control.x` 赋值的表达式，绕过 LIF 神经网络的电流注入竞争。旁路与引用是不同的集合：
  - **写点（赋值）**: `re.findall(r'control\.x\s*=', text)` — 字面左值赋值
  - **读点/比较/遥测**: `re.findall(r'control\.x\b', text)` — 任意出现（含赋值、比较、JSON 序列化、注释）
  - **"旁路"指代**: 本文指**写点（赋值）**，因为只有赋值才构成"绕过神经决策链"的行为语义
- **当前代码实测（2026-09-24）**:
  | 口径 | main.py | 全仓（排除 .venv/.pytest/.tmp） |
  |:----|:-------:|:-----------------------------:|
  | **写点（赋值）** `control.x\s*=(?!=)` | **10 处** | **14 处**（+motor_primitives.py 1 + evolution_agent.py 1 + fix_template_interpreter.py 2） |
  | **写点（赋值）** 含 `fly64/tests` | 10 处 | **16 处**（+test_evolution_capability.py 1 + test_fix_template_interpreter.py 1）；**含根 `tests/` = 17 处**（t5 补） |
  | **含写点的行数** | 10 行 | 14 行 |
  | **引用出现次数** `control.x\b` | **32 次** | **71 次** |
  | **含引用的行数** | **30 行** | **65 行**（含注释/docstring 15 行） |
  - **复现命令**:
    ```python
    import re, pathlib
    rx_assign = re.compile(r'control\.x\s*=(?!=)')   # t5 勘误：必须排除 == / != / <= / >=
    rx_ref = re.compile(r'control\.x\b')
    for f in ['fly64/fly64/main.py']:  # 或全仓
        text = pathlib.Path(f).read_text(encoding='utf-8')
        print(f'{f}: 赋值 {len(rx_assign.findall(text))} 处')
        print(f'{f}: 引用 {len(rx_ref.findall(text))} 次')
    ```
  - 🔧 **t5 实测（2026-09-26，赋值口径）**：`main.py` **10** / 生产（排除 `fly64/tests`）**14** / 含 `fly64/tests` **16** / 含根 `tests/` **17**；朴素口径（含 `==`）分别为 12 / 16 / 18 / 19。
  - 🔧 **t5 引用计数口径说明**：`main.py` 的 `control\.x\b` 引用 **32 次 / 30 行仍准确**；但原表「全仓 71 次 / 65 行」我按同一文字口径实测为 **76 次 / 70 行（含 `fly64/tests`）** 与 **52 次 / 49 行（排除 `fly64/tests`）**，**均不等于 71/65** ⇒ 该聚合数的范围与时点不可复现，后续引用请**写明限定口径**（沿用本文件 `control.x` 引用计数的同名事故，属"口径未冻结"一类）。
- **main.py 写点清单（10 处）**（🔧 t5 勘误：**行号已更新为 2026-09-26 实测值**，末列给出 09-24→09-26 漂移；代码文本逐行核对未变）:
  | 行号（t5 实测） | 代码 | 语义分类 | 09-24 行号 → 漂移 |
  |:----:|------|:--------:|:----:|
  | L760 | `control.x = int(np.clip(round(control.x + dx), -80, 80))` | reflex 电流融合 | L760 → 0 |
  | **L2060** | `control.x = turn_dir` | escape 方向提交 | L1948 → +112 |
  | **L2077** | `control.x = int(cliff_turn_bias)` | cliff 转向 | L1965 → +112 |
  | **L2141** | `control.x = action["control_x"]` | LLM 策略 | L2029 → +112 |
  | **L2190** | `control.x = int(max(-80, min(80, _burst_heading * 1.5)))` | fallen burst | L2078 → +112 |
  | **L2192** | `control.x = 0` | fallen 结束 | L2080 → +112 |
  | **L2406** | `control.x = int(60 * (1 if (model.step_count // 20) % 2 else -1))` | 测试模式 | L2286 → +120 |
  | **L2414** | `control.x = 0` | 测试模式结束 | L2294 → +120 |
  | **L2466** | `control.x = int(max(-70, min(70, _yaw_diff * 40)))` | 导航 | L2346 → +120 |
  | **L2492** | `control.x = int(30.0 * (_phase / 3.14159 - 1.0))` | 导航 | L2372 → +120 |
- **历史分类**（来自 `docs/analysis/insurance/remaining-issues-analysis.md`，基于 09-13 版本的 main.py，以**逻辑场景**分类而非字面赋值计数）:
  | 类别 | 数量 | 旧行号 | 当前对应代码 |
  |:----|:----:|:------:|:-----------:|
  | A: Reflex 控制 | 6 | L939-940, L956-958, L1011-1013 | L760(1处) — reflex 电流融合；其余5处已被重构或改道 |
  | B: 对话 LLM 控制 | 11 | L1168-1179, L1191-1199, L1206 | **L2141**(1处) — `action["control_x"]` 来自 LLM 策略；其余已被重构（t5：原写 L2029） |
  | C: 坠落恢复 | 6 | L1220-1229 | **L2060**(1处 escape)、**L2190-2192**(2处 fallen burst)；其余已重构（t5：原写 L1948、L2078-2080） |
- **影响**: 神经决策可被 Python 层无条件覆盖，破坏闭环学习的完整性。当前代码中字面赋值 10 处，其中 `escape`/`fallen` 4 处、`nav`/`coach test` 3 处为已知旁路，`reflex` 1 处、`LLM` 1 处为架构性旁路
- **会话引用**: session-38542b1c, session-1f8fbe04
- **当前代码位置（t5 实测，2026-09-26）**: `fly64/fly64/main.py` L760, **L2060, L2077, L2141, L2190, L2192, L2406, L2414, L2466, L2492**（**原值（09-24）**: L760, L1948, L1965, L2029, L2078, L2080, L2286, L2294, L2346, L2372 —— 除 L760 外整体漂移 +112~+120）
- **复现命令**（🔧 t5 勘误：加 `(?!=)` 守卫，否则会把 `==` 比较计入得 12）:
  ```bash
  # 字面赋值计数（生产）—— 赋值口径：排除 == / != / <= / >=
  grep -rnP 'control\.x\s*=(?!=)' fly64/fly64/main.py fly64/fly64/motor_primitives.py fly64/skills/evolution_agent.py fly64/skills/fix_template_interpreter.py | grep -v '__pycache__'
  # 全仓含 tests（赋值口径）
  grep -rnP 'control\.x\s*=(?!=)' fly64/ --include='*.py' | grep -v '__pycache__'
  # 任意引用（全仓）
  grep -rn 'control\.x' fly64/ --include='*.py' | grep -v '__pycache__' | wc -l
  # 不可用 -P 时的可移植替代：'control\.x\s*=[^=]'
  ```
- **建议**: P3 优先级 — Reflex 仅设 flag → LIF 竞争；P4 — 对话 LLM 输出转向 LIF 池

### 困境 5 🟡: Steering 预算次序 — CX 优先 vs Reflex 优先

- **证据**:
  - `central_complex.py` L210: `self.steering_bias: float = 0.0`
  - `model.py` L2094 注释暗示 CX steering_bias 与 reflex 之间的优先级竞争关系
  - 在 `escape_mode` 下的方向提交机制与 CX 导航 steering_bias 存在潜在冲突：escape 需要坚持方向，但 CX 新颖性引导可能产生相反偏置
- **影响**: 逃逸时方向提交与 CX 导航竞争 steering_bias，可能导致逃逸被打断
- **会话引用**: session-1f8fbe04, session-38542b1c
- **代码位置**: `fly64/fly64/central_complex.py` L210-L316, `fly64/fly64/model.py`（escape 相关逻辑）
- **建议**: 明确定义 Steering 优先级链：Reflex > Escape > CX Exploration > Default，在代码中显式实现优先级仲裁

---

## 6. 下一阶段行动建议

### 短期（优先处理）

| 优先级 | 行动 | 预期工时 | 关联困境 |
|:------:|------|:--------:|:--------:|
| P0 | Telemetry 常量提取为命名常量 | 1 小时 | 困境 1 |
| P0 | CX-2 视觉重定位校正实现 | 3 天 | 困境 2 |
| P1 | StuckDetector rate_threshold 单位文档化+断言 | 0.5 天 | 困境 3 |
| P1 | Steering 优先级链显式实现 | 2 天 | 困境 5 |

### 中期

- **P3**: Reflex control.x 旁路迁移至 LIF 电流注入
- **P4**: 对话 LLM 策略输出迁移至 LIF 池
- **P4**: 垂直维度(Y) 3D 网格扩展（SpatialMemoryMap y_layers）
- **实施端到端契约审计**：每个模块增加 `test_*_contract.py` 风格的行为断言

### 长期

- **导航闭环**：实现视觉重定位 + 地标记忆 + 拓扑地图
- **多模态感知**：多眼视觉方案
- **自适应 curriculum**：基于 Evo Phase 6 评分动态调整训练难度

---

## 附录 A：受影响的文件索引

| 文件路径 | 相关的主题领域 | 困境引用 |
|---------|:-------------:|:--------:|
| `fly64/fly64/model.py` | A1, A2, A4 | 困境 1, 4, 5 |
| `fly64/fly64/memory.py` | A1, A2 | 困境 3 |
| `fly64/fly64/central_complex.py` | A1 | 困境 2, 5 |
| `fly64/fly64/mushroom_body.py` | A2 | — |
| `fly64/fly64/scene_recognition.py` | A3 | 困境 2 |
| `fly64/fly64/main.py` | A4, B2 | 困境 4 |
| `fly64/fly64/retina.py` | A3 | — |
| `fly64/fly64/instinct_bindings.py` | A4 | — |
| `fly64/fly64/bridge.py` | C1 | — |
| `fly64/plugin/coach_outcomes.py` | B2 | — |
| `fly64/plugin/llm_consult.py` | B2 | — |
| `fly64/plugin/runner.py` | B2, B3 | — |
| `fly64/skills/evolution_skill.py` | B1 | — |
| `fly64/skills/default_patterns.json` | B1 | — |
| `fly64/web/dashboard.js` | D1 | — |

## 附录 B：核心模式检测清单（供后续任务 t3/t4 参考）

每个新修复 PR 应回答以下 4 个问题以防范"机制存在、报告成功、无法生效"模式：

1. ✅ **代码中是否实现了目标功能？** — 静态代码审查
2. ✅ **测试是否报告通过？** — 单元测试
3. ✅ **实际行为是否符合预期？** — 端到端行为断言（新增 `test_*_contract.py`）
4. ✅ **跨组件集成后是否仍生效？** — 集成验证（部署后 probe）

---

## 附录 C：t5 返修勘误汇总（2026-09-26，M-6；本附录只追加）

> 依据 `docs/analysis/blindspot-review-0923-0926.md`（t4 独立核验）。**本附录只追加，不删除任何既有条目、不放宽任何表述**；上文已在相应位置就地更正并留「原值 → 实测值」痕迹，此处集中索引。

| # | 位置 | 原值（09-24 交付时） | 实测值（2026-09-26） | 更正类型 |
|:-:|---|---|---|---|
| 1 | §困境 2 证据（L378 附近） | 「`_self_motion_update()` 使用 heading_rate 开环积分，**无视觉闭环校正**」 | **机制已存在**：`AnchorPathIntegrator.relocalize()`（`central_complex.py:128-140`，gate 0.8 / strength 0.3）+ **调用点 2 处**（`:529`、`:673`）+ 测试 `test_cx_navigation.py:179-204` ⇒ 结论改为「**机制在、活体生效未验证**」 | 结论过时（就地更正 + 痕迹保留） |
| 2 | §困境 3 证据与建议 | `rate_threshold: float = 5.0`（Hz）；建议「添加单位注释 **+ 运行时断言**」 | 当前为 **`0.008`（per-tick fraction，注释 `was 5.0 Hz`）+ `:207-208` 单位注释** ⇒ **单位口径已闭环**；但 **`assert` 计数 = 0（运行时断言未实现）**、`docstring:127` 仍写「`< 5 Hz`」（半迁移）、且 `stuck_score` 仍可达 1.0 而同刻 `stuck_duration = 0.0`（12:54 六连；`memory.py:234-235` 泄放抹零）⇒ **可观测性未闭环** | 半闭环（就地更正 + 痕迹保留） |
| 3 | §困境 4 写点清单 / 当前代码位置 / 复现命令 | 10 个写点行号 = L760, L1948, L1965, L2029, L2078, L2080, L2286, L2294, L2346, L2372；复现正则 `control\.x\s*=` | 行号 = **L760, L2060, L2077, L2141, L2190, L2192, L2406, L2414, L2466, L2492**（除 L760 外**整体漂移 +112~+120**）；正则改为 **`control\.x\s*=(?!=)`**（朴素式会把 `main.py:2618`、`:2959` 两处 `==` 比较计入 ⇒ 得 12 而非 10，即此前 t2「A4 恶化 10→12」的伪影来源）；**窗口前后（`2f87d77^`=`HEAD`=工作区）三处均为 10 ⇒ 未恶化**；口径全量：`main.py` 10 / 生产 14 / 含 `fly64/tests` 16 / 含根 `tests/` 17 | 行号漂移 + 正则口径 |

**未改动项（明确不放宽）**：本文件 §1–§4 的主题分类、12 例模式清单（§4.2）、§5 五项困境的**问题本身**、§6 建议与附录 A/B 全部**保持原样**；本次仅更正 3 处**过时的代码事实**（行号、取值、机制存在性），其中「困境 2/3/4」的问题定性**未被撤回**（CX-2 漂移风险、单位语义歧义、`control.x` 旁路均仍成立）。