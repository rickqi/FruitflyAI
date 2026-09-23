# FruitflyAI 🪰

**果蝇神经科学与游戏控制 —— 从生物脑到通用决策引擎**

*Drosophila neuroscience meets interactive control — from a biological brain to a general-purpose decision engine.*

> **BRAIN_VERSION:** `2.23.12` · **Skill Version:** `3.5.0` · **166,700 LIF neurons · 151.9M synapses · MaleCNS v1.0**

---

## 📋 项目一览 / Overview

FruitflyAI 是一个将果蝇（*Drosophila*）真实生物神经连接组（MaleCNS v1.0）接入数字环境的开源研究项目。核心目标是验证：**一个完整生物脑的神经计算能否在游戏控制、运动仿真、乃至商业场景中产生有意义的行为**。

项目的独特之处在于：
- 🧠 **真实连接组驱动**：使用果蝇雄性中枢神经系统完整连接组数据，166,700 个 LIF 神经元、2560 万条突触连接，非人工神经网络简化
- 🔄 **自治演化闭环**：EVO 技能系统形成「监测→诊断→修复→验证→存档」的自我进化闭环，22+ 轮持续迭代
- 📊 **完整的可解释性栈**：从复眼采样到运动输出的六级控制级联全程可归因，Web 仪表板实时呈现因果链
- 🔌 **环境抽象协议**：统一的 VisionSource / MotorTarget 接口，同时支持 Super Mario 64 和 FlyGym v2 仿真

---

## 📦 项目组成 / Project Components

| 子项目 / Module | 说明 / Description |
|----------------|-------------------|
| **Fly64** (`fly64/`) | 核心系统 — 果蝇脑控制 Super Mario 64，包含完整脑模型、视觉管道、空间记忆、运动解码、EVO 自我进化、LLM 教官层、Web 仪表板 |
| **FlyGym** (`scripts/launch_interactive_viewer.py`) | NeuroMechFly v2 果蝇身体运动仿真（MuJoCo），验证脑模型在六足机器人躯干上的行为迁移 |
| **Environments Protocol** (`fly64/environments/protocol.py`) | 环境抽象层 — `VisionSource` / `MotorTarget` 协议将主循环与具体环境解耦，支持 SM64 / FlyGym 适配器无侵入切换 |
| **Skills** (`fly64/skills/`) | EVO 自我进化系统 + Pattern 目录 + 修复目录 + 教练顾问策略 |
| **Plugin** (`fly64/plugin/`) | MHR 教官层 — LLM 多模态咨询 + 自治常驻服务 + 看门狗 |
| **Web Dashboard** (`fly64/web/`) | 实时神经活动监控面板 + 因果链可视化 + 空间记忆热力图 + 轨迹回放 |
| **Docs & Analysis** (`docs/`, `fly64/docs/`) | 35+ 篇技术文档覆盖设计/实施/评审/路线图/跨领域分析 |

---

## 🚀 快速开始 / Quick Start

### 前提条件

- **推荐方案**: Windows 10/11 + WSL2 (Ubuntu 22.04)
- **备选方案**: macOS (Apple Silicon) 或原生 Linux (Ubuntu 22.04+)
- **磁盘**: 至少 5GB 可用空间
- **内存**: 建议 8GB+
- **SM64 ROM**: 一份**未修改的美版 Super Mario 64 ROM** (`.z64`)

### 一分钟启动 (WSL)

```bash
# 1. 初始化 WSL 环境
wsl
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential libsdl2-dev libglew-dev pkg-config \
                    python3 python3-venv python3-pip curl git make

# 2. 克隆并进入项目
git clone https://github.com/rickqi/FruitflyAI.git
cd FruitflyAI/fly64

# 3. 设置 Python 环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 下载脑数据 (~1.3GB)
python -m fly64.data --prepare --cache .cache/malecns

# 5. 设置 sm64ex 并编译
git clone https://github.com/sm64pc/sm64ex.git .cache/sm64ex
cd .cache/sm64ex
git checkout d7ca2c04364a6dd0dac58b47151e04e26887e6f0
git apply ../../patches/sm64ex-fly64.patch
# 将 SM64 ROM 放入该目录
make -j$(nproc) VERSION=us BETTERCAMERA=1 NODRAWINGDISTANCE=1 EXT_OPTIONS_MENU=1

# 6. 使用 tmux 守护启动器（推荐）
cd ../..
bash scripts/wsl_launcher.sh --rom /path/to/baserom.us.z64
```

启动后浏览器访问 **http://127.0.0.1:8765/** 查看实时仪表板。

> 完整设置指南见 [`fly64/README.md`](fly64/README.md) 和 [`WSL 部署指南`](fly64/docs/wsl-launcher-deployment.md)。

---

## 🧠 技术架构 / System Architecture

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐
│  环境层       │───▶│  VisionSource    │───▶│ Fly64 脑模型                    │
│  SM64 /       │◀───│  MotorTarget     │◀───│ 166,700 神经元 / 151.9M 突触   │
│  FlyGym       │    │  协议桥          │    │ LIF 网络 + CX + 蘑菇体          │
└──────────────┘    └──────────────────┘    └──────────────────────────────┘
       │                     ▲                          │
       │ 渲染六面体贴图       │ 读取游戏帧                │ 计算控制信号
       ▼                     │                          ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Web Dashboard (http://127.0.0.1:8765)  +  WS 8766 (F643 packet)           │
│  • 复眼视图 (270° + 16扇区叠加)  • 神经活动图表  • 全脑热力图                 │
│  • 决策解释卡 (decision_source 归因)  • 四泳道因果时间轴 (120s)              │
│  • 空间记忆/轨迹回放  • Escape 事件表  • 覆盖度与健康评分                     │
│  • Coach 面板 (教官建议)  • EVO/Brain 版本胶囊                              │
└───────────────────────────────────────────────────────────────────────────┘
       ▲                                        ▲
       │ 只读遥测 (JSON)                         │ 状态/建议
┌──────┴───────────────────┐          ┌─────────┴──────────────────────┐
│ EvolutionSkill v3.5.0    │          │ MHR 教官层插件 (10s 周期)        │
│ Monitor→Diagnose→Fix→    │          │ runner → check_help_needed →    │
│ Verify→Document          │          │ LLM 多模态咨询 →                │
│ 16 patterns · fix_catalog │          │ active_strategy.json (热加载)   │
│ 常驻循环 (auto-fix)       │          │ + coach_advice.json (展示)      │
└──────────────────────────┘          └────────────────────────────────┘
       ▲                                        ▲
       └──────── scripts/consolidate.sh（制度化重启，含自治服务）──────────┘
```

---

## 🏆 近期关键交付 / Key Achievements

### AgentTeams 治理任务包 — `fly64-comprehensive-fix` (5 项)

系统性治理 Fly64 基础设施瓶颈与契约缺陷：

| # | 交付 | 关键成果 |
|---|------|---------|
| 1 | **FixExecutor 模板覆盖** | 自然语言修复模板 → LLM 辅助结构化解释器，8 个降级 pattern 全部可自动执行 |
| 2 | **写入锁与竞态防护** | `fcntl.flock()` 进程级写入锁 + Git 式冲突检测，杜绝双 EVO 实例数据竞争 |
| 3 | **历史记录旋转归档** | `EvolutionHistory` 超阈值自动旋转 + 增量 README 更新，24h+ 运行零退化 |
| 4 | **契约审计与死旋钮清理** | `audit_contract_pairs.py` AST 级写入/读取点分析，清理 12+ 条死JSON 键，验证全部 `brain_tunable_params.json` 可消耗 |
| 5 | **回归基线可探测** | `known_failures.json` 36 条基线 + `check_regressions.py` 回归探测，回归不再淹没于噪声 |

### 执行交付包 — `fly64-plan-exec` (10 项)

大规模脑模型能力扩展：

| # | 交付 | 关键成果 |
|---|------|---------|
| 1 | **R22 Motor Expansion P1** | Z 触发解锁 + 拳击/俯冲/砸地/长跳/后空翻/爬行物理通路 |
| 2 | **R23 Motor Expansion P2** | VNC 式 CPG 运动原语层 + pose 状态机 + 2s 超时熔断 |
| 3 | **R24 Motor Expansion P3** | strike/crouch 双 20 神经元解码池 + MBON 5→9 列扩展 |
| 4 | **R24 Motor Expansion P4/5** | 监控可视化 + EVO pattern 收编 + 惰性种子修复 |
| 5 | **R29 视觉修复** | CCL 8 连通性修复，小目标检测 stride-2 采样恢复正常 |
| 6 | **R31-fix2 截屏保真修复** | 帧捕获从观察者通道尾部 → `end_frame` 完成点，保真度回归套件 |
| 7 | **R31-fix3 熔岩地修复** | 掉血检测 + 受击格写入失败记忆 + 覆盖度进展门控位移奖励 |
| 8 | **R31-fix4 Fall 判定** | 垂直速度环形缓冲 + 三态模型，消除高处误判 |
| 9 | **R31-fix5 micro_loop 相位** | 交替纯旋转 → 之字形推进，产生实际位移 |
| 10 | **R31-fix6 stuck_duration 治理** | 异常分类器增加 `disp_60s` 门控，有进展不再被 stuck 锁定 |

### 深度根因分析 — `fly64-challenge-analysis` (3 项)

三项并行深度分析，系统性识别剩余瓶颈：

| # | 分析域 | 关键发现 | 文档 |
|---|--------|---------|------|
| 1 | **P0-A: EVO auto-fix 常驻运行** | 8 项阻塞级问题（66.7% pattern 降级、竞态条件、行号漂移、无界历史记录、日志爆满等） | [`next_challenge_analysis_report.md`](docs/analysis/next_challenge_analysis_report.md) |
| 2 | **P0-B: FlyGym 端到端集成** | 视觉适配器压缩比 691,200:1 → 完全失能，缺少 VisionSource 抽象层，8 项集成测试缺口 | 同上 |
| 3 | **P1-A: 视觉覆盖度提升** | 颜色/UV ≈95% 已完成可直接启用，小目标追踪 ≈80% 需验证修复，多巴胺学习 ≈85% 需修复阻塞性缺陷 | 同上 |

### 下一个执行包 — `fly64-next-execution` (6 项)

即将交付的 P0/P1 实施项：

| # | 项 | 预估工作量 | 状态 |
|---|------|----------|------|
| 1 | **P0-A1: LLM 辅助 FixTemplateInterpreter** | 1-2 天 | 待开始 |
| 2 | **P0-A2: 写入锁 + Git 式冲突检测** | 0.5 天 | 设计中 |
| 3 | **P0-B1: VisionSource 抽象层 + SM64 适配器** | 3-4 天 | 待开始 |
| 4 | **P0-B2: FlyGym 适配器（空间降采样视觉）** | 3-4 天 | 待开始 |
| 5 | **P1-A: 颜色/UV 通道验证与启用** | 1 天 | 待开始 |
| 6 | **P1: 小目标追踪行为验证 + 多巴胺学习全栈测试** | 5-8 天 | 待开始 |

---

## 📊 当前状态 / Current Status

| 指标 | 数值 |
|------|------|
| **BRAIN_VERSION** | `2.23.12` |
| **Skill Version** | `3.5.0` |
| **测试套件** | 1,278 项 (`pytest --collect-only`) |
| **测试文件** | 92 个 (`tests/test_*.py`) |
| **核心模块行数** | `main.py` ~2,280 · `model.py` ~1,538 · `memory.py` ~1,610 · `retina.py` ~1,269 |
| **EVO 进化轮次** | 80 条权威记录（R1–R31 + 运维 + t 系列 + EVO-072） |
| **Pattern 目录** | 16 条可检测 pattern |
| **文档数量** | 35+ 篇技术文档（设计/实施/评审/路线图/跨领域） |
| **FlyGym 版本** | v1.2.1（与 SM64 双后端就绪） |
| **运行平台** | Windows 10/11 + WSL2（主推）· macOS Apple Silicon · Linux x86_64 |
| **自治服务** | MHR 插件 10s 闭环 · 看门狗自动重启 · consolidate.sh 制度化重启 |

### 当前测试分类

| 类别 | 主要测试文件 | 覆盖范围 |
|------|------------|---------|
| 神经模型 | `test_model.py`, `test_retina.py`, `test_mushroom_body.py`, `test_gain_modulation.py`, `test_brain_alternation.py`, `test_mbon_saturation.py`, `test_dan_shaping.py` | LIF 动力学、复眼采样、蘑菇体可塑、增益调制、转向交替、饱和守卫 |
| 记忆与感知 | `test_memory.py`, `test_optic_flow.py`, `test_cliff_standoff.py` | 空间网格/反射/光流/悬崖对峙 |
| 桥接与仪表板 | `test_bridge.py`, `test_dashboard_protocol.py`, `test_dashboard_js.py` | mmap 协议、WS packet 字段契约、前端渲染 |
| EVO 与自治 | `test_evolution_capability.py`, `test_service.py`, `test_autonomy_regression.py`, `test_plugin_mhr.py` | Pattern 判定、修复记录、服务心跳、看门狗、原子写出 |
| 神经接管 PIN | `test_p1_neural_takeover.py`, `test_spin_loop_fix.py` | Python 旁路回归（11 处 A 类旁路必须保持删除） |
| 环境协议 | `test_environment_protocol.py`, `test_flygym_adapter.py` | VisionSource / MotorTarget 适配器 + FlyGym 集成（20 项） |
| 在线检查 | `check_live_version.py`, `check_bridge_mismatch.sh`, `ws_probe.py`, `evo_status_report.py` | 运行中实例的版本/桥接/遥测/EVO 状态抽查 |

---

## 🔭 下一步 / Next Steps

### P0 — 立即处理（阻塞项）

- **🔴 EVO auto-fix 常驻运行**：实现 LLM 辅助修复模板解释器 + 写入锁 + Git 式冲突检测 + 历史记录旋转归档 + 迭代级健康看门狗（预估 3-5 天）
- **🔴 FlyGym 端到端集成**：VisionSource/MotorTarget 抽象层 → SM64 适配器 → FlyGym 适配器（空间降采样视觉）→ 8 项集成测试（预估 8-11 天）

### P1 — 短周期（1-3 天）

- **🟡 颜色/UV 通道启用**：验证 `encode_color()` 管道，默认启用 `color_signature=True`，场景签名兼容性测试
- **🟡 小目标追踪行为验证**：修复验证后启用 LIF 分裂注入通路
- **🟡 多巴胺学习全栈测试**：修复 MBON 饱和 + 阈值错误后启用全栈测试
- **🟡 备份目录隔离**：`.bak` 写入单独 `.evo_backups/` 目录，统一清理策略

### P2 — 中期（1-2 周）

- **🟢 本能固化晋级量化**：P4.4 场景→策略本能绑定，度量工具化
- **🟢 课程三态判定扩展**：不可观测 ≠ 失败，三态判定已实现，等待端到端验证
- **🟢 动作熵与抖动检测**：防止反射相位的无效旋转抖动积累
- **🟢 回归检测自动化**：`check_regressions.py` 集成到 CI 管道
- **🟢 24h+ 长时间运行压力测试**：历史记录旋转、看门狗自动暂停、写放大治理

> 详细路线图见 [`next_challenge_analysis_report.md`](docs/analysis/next_challenge_analysis_report.md)

---

## 📚 文档索引 / Documentation

### 项目文档

| 文档 | 说明 |
|------|------|
| [`fly64/README.md`](fly64/README.md) | Fly64 完整技术文档 — 安装/架构/进化历史/全部参数 |
| [`docs/analysis/next_challenge_analysis_report.md`](docs/analysis/next_challenge_analysis_report.md) | P0/P1 挑战根因分析与综合路线图 |
| [`docs/analysis/session_logs_analysis_report.md`](docs/analysis/session_logs_analysis_report.md) | 11 个 Session 对话日志全面分析报告 |
| [`docs/analysis/t6_final_comprehensive_report.md`](docs/analysis/t6_final_comprehensive_report.md) | 跨领域能力最终综合报告 |

### Fly64 关键文档 (`fly64/docs/`)

| 文档 | 主题 |
|------|------|
| `causal-chain-ui-design.md`, `causal-chain-implementation.md`, `causal-chain-final-review-t8.md` | 因果链设计/实施/终审全套 |
| `layout-optimization.md`, `layout-audit-t5.md` | 仪表板布局优化与逐区审核 |
| `color_uv_vision_design.md`, `emd_4direction_design.md`, `small_target_tracking_design.md`, `dopamine_mushroom_body_design.md` | P1a/P1b/P2/P3 视觉与学习能力设计 |
| `implementation_roadmap.md`, `visual-enhancement-plan.md` | 能力增强规划与路线图 |
| `what_i_see_protocol.md` | 教官层视觉协议定义 |
| `evolution-coach-roadmap.md` | EVO 进化 + Coach 教官双系统路线图 |
| `wsl-setup-guide.md`, `wsl-launcher-deployment.md` | WSL 部署与守护启动器 |
| `thin-plugin-design-analysis.md`, `lif_injection_feasibility_report.md` | 薄插件设计与 LIF 注入可行性论证 |

### 运动扩展文档 (`docs/analysis/motor-expansion/`)

| 文档 | 主题 |
|------|------|
| `bridge-bz-unlock.md` | 桥接 Z 触发解锁设计 |
| `cpg-motor-primitives.md` | CPG 运动原语层架构 |
| `neural-pools-extension.md` | 神经池扩展方案 |
| `dashboard-impact-assessment.md` | 仪表板影响评估 |
| `execution-plan.md` | 执行计划与阶段划分 |
| `next-optimization-plan.md` | 下一优化步骤 |
| `mbon-learning-evaluation.md` | MBON 学习评估 |

---

## 🧪 快速验证 / Run Tests

```bash
cd fly64
python -m pytest -q                          # 全量套件 (1,221 项)
python -m pytest tests/test_invariants.py -q  # 不变量（连接组/LIF 数值契约）
python -m pytest tests/test_evolution_capability.py -q  # EVO 能力回归
python -m pytest tests/test_service.py tests/test_autonomy_regression.py -q  # 自治服务与看门狗
python -m pytest tests/test_environment_protocol.py tests/test_flygym_adapter.py -q  # 环境协议
```

---

## 🤝 贡献 / Contributing

本项目以开放科学精神进行果蝇全脑连接组计算神经科学研究。欢迎：
- 🐛 报告行为瓶颈与异常 pattern
- 🧪 贡献测试用例与回归基线
- 📝 改进文档与可视化
- 🧠 提出新的神经计算假设

**许可**: 见仓库根目录 LICENSE 文件。

---

> **FruitflyAI** — 从果蝇的 166K 神经元到通用决策智能。  
> *From 166K fruitfly neurons toward general-purpose decision intelligence.*