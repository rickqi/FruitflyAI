# FruitflyAI — Fly64: 果蝇大脑控制 Super Mario 64

[![Fly64 Neural Observatory](https://img.shields.io/badge/Fly64-Neural%20Observatory-6cdaed)](https://github.com/rickqi/FruitflyAI)

将果蝇（Drosophila）真实神经连接组（MaleCNS v1.0，**166,700 神经元，2,560 万突触连接**）接入 Super Mario 64，实现完整的视觉→神经→运动控制闭环。

## 🖥️ 支持平台

| 平台 | 状态 | 说明 |
|------|------|------|
| **macOS** (原始) | ✅ | Apple Silicon (M1/M2), Homebrew |
| **WSL2 Ubuntu 22.04** | ✅ **推荐部署方案** | **已验证** — 原生 POSIX 兼容，WSLg GPU 加速 GUI |
| **Linux (Ubuntu 22.04+)** | ✅ | 需 x86_64 + NVIDIA/Intel GPU |
| **原生 Windows** | ❌ | 需要 MSYS2 + Win32 mmap 重写，不推荐 |

### 部署建议

> **推荐方案：WSL2 (Windows Subsystem for Linux)**
>
> 本项目最初仅支持 macOS（Apple Silicon + Homebrew）。我们全面解决了在 **Windows 10/11 上通过 WSL2 运行** 的所有技术障碍，验证了完整的视觉→神经→运动控制闭环。WSL2 提供了与原生 Linux 几乎一致的 POSIX 环境，同时无缝集成 Windows 文件系统和网络。
>
> 相比原生 macOS 方案的不足，WSL 方案提供了更高的硬件可用性和可扩展性。不建议在原生 Windows（MSYS2/MinGW）上运行，因 mmap 共享内存桥接等 POSIX 依赖需大量移植。

## 📋 前置要求

- **操作系统**: Windows 10 2004+ / Windows 11（WSL2 方案）
- **WSL2**: 已启用（`wsl --install -d Ubuntu`）
- **磁盘空间**: 至少 5GB 可用
- **内存**: 建议 8GB+
- **SM64 ROM**: 需要一份**未修改的美版 Super Mario 64 ROM** (`.z64`)

## 🚀 快速开始 (WSL)

### 1. 初始化 WSL 环境

```bash
# 启动 WSL
wsl

# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装工具链
sudo apt install -y build-essential libsdl2-dev libglew-dev pkg-config \
                    python3 python3-venv python3-pip curl git make
```

### 2. 克隆项目

```bash
git clone https://github.com/rickqi/FruitflyAI.git
cd FruitflyAI/fly64
```

### 3. 设置 Python 环境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. 下载脑数据（~1.3GB）

MaleCNS 果蝇连接组数据来自 Google Cloud Storage（中国大陆下载较慢，约 40-60 分钟）：

```bash
# 重要：使用 curl 下载（aria2c 会产生截断文件）
python -m fly64.data --prepare --cache .cache/malecns
```

> **下载慢？** Google Cloud Storage 在中国大陆有带宽限制。如果下载缓慢，可尝试：
> - 使用代理/VPN
> - 夜间下载（速度可能提升）

### 5. 设置 sm64ex 并编译

```bash
# 克隆 sm64ex（如果 GitHub 直连慢，可用 ghfast.top 代理）
git clone https://ghfast.top/https://github.com/sm64pc/sm64ex.git .cache/sm64ex

# 进入目录并切换到指定 commit
cd .cache/sm64ex
git checkout d7ca2c04364a6dd0dac58b47151e04e26887e6f0

# 应用 Fly64 补丁
git apply ../../patches/sm64ex-fly64.patch

# 将 SM64 ROM 放入目录
# cp /path/to/baserom.us.z64 .

# 编译（注意：需要 -lGLEW 链接）
make -j$(nproc) VERSION=us BETTERCAMERA=1 NODRAWINGDISTANCE=1 EXT_OPTIONS_MENU=1

# 如果编译报 GLEW 链接错误，先运行：
sed -i 's/BACKEND_LDFLAGS += -lGL/BACKEND_LDFLAGS += -lGLEW -lGL/' Makefile

cd ../..
```

### 6. 修复桥接兼容性

```bash
# bridge.py 默认仅支持 macOS（Apple Silicon 内存屏障）
# Linux/WSL 需要打补丁（仓库版本已包含此修复）
```

### 7. 运行

#### 合成模式（无需 ROM，展示脑模型）

```bash
source venv/bin/activate
python3 -m fly64.main --bridge /tmp/f64b --record /tmp/f64r.npz \
  --synthetic --demo-model --no-browser --duration 600
```

浏览器打开 **http://127.0.0.1:8765/** 查看仪表板。

#### 完整模式（需要 SM64 ROM）

```bash
source venv/bin/activate
./run-fly64 --rom /path/to/baserom.us.z64
```

或手动启动脑模型 + 游戏：

```bash
# 终端1：启动脑模型
source venv/bin/activate
mkdir -p runtime artifacts
python3 -m fly64.main --bridge runtime/fly64_bridge.bin \
  --record artifacts/latest-replay.npz --no-browser --duration 0

# 终端2：启动 SM64
cd .cache/sm64ex
FLY64_BRIDGE=../runtime/fly64_bridge.bin ./build/us_pc/sm64.us.f3dex2e --skip-intro
```

## 🎮 操作说明

| 按键 | 功能 |
|------|------|
| **F8** | 切换果蝇脑神经控制 |
| **方向键** | 手动控制马里奥 |
| **A / 空格** | 跳跃 |
| **ESC** | 退出游戏 |

## 🌐 仪表板

游戏/模型运行时访问 **http://127.0.0.1:8765/**。

![监控面板总览](docs/screenshots/dashboard-main.png)

### 实测运行截图说明（Brain v2.11.0 · 单列布局 · 斜坡卡住现场）

![Fly64 监控面板实测：复眼视野 + 神经活动图表 + 全脑热力图 + 空间记忆 + 四泳道因果时间轴 + Escape 事件表 + 健康度/覆盖率仪表](docs/screenshots/dashboard-live-monitoring.jpg)

该截图取自 Brain v2.11.0 实机运行（马里奥卡在斜坡、`micro_loop` 异常态期间），是仪表板**全部 8 个区块的完整读数样例**：

| 区块 | 截图读数 | 说明 |
|------|---------|------|
| **状态条（header）** | `Brain v2.11.0` · `EVO #0` · `Health 50%` · `micro_loop` · `LLM none` · `Layout: Single` | 版本/健康度/当前异常态/LLM 通道状态/布局模式一览；`micro_loop` 胶囊亮起即当前被判为"原地编织"异常 |
| **Vision** | `Δ light L 6.6% · R 4.2%` · `R1–R8 10.5 Hz` · `Local motion: 0.000 (clear)` · `First person - RGB - 270°` | 左为游戏画面 + 果蝇 270° 复眼双视图，中为帧差异图；`Local motion 0.000` = 画面静止（与卡住状态一致） |
| **Causal Chain · why this action** | 五段链 RAW→SIGNAL→NEURAL→JUDGE→ACTION | 回答"为什么现在这个动作"，被高优先级抢占的段显示删除线 |
| **Neurons → controls** | Forward pool `17.1Hz ± 7.2Hz`、Steering `1.4Hz ± 1.5Hz`、Jump pool `16.1Hz ± 20.0Hz`；gate 虚线 0.4/2Hz；`A: gold spot or open overhead ✓` | 四路神经活动实时曲线 + 门控阈值；跳跃池爆发但控制输出 `x=-23 y=5` —— 神经在动、位移为零 |
| **Activity map** | `Mean 2.91Hz` · `143,638 located · 32,062 unlocated` | 全脑 WebGL 热力图（亮度=rolling rate） |
| **Spatial memory** | `Stuck 1 · 2589.8s`、`Loop 1`、`Novelty 0`、`ESCAPE 15 active · 813 cells`、`1 escapes · 0 falls · 837 avoids`、`Coverage 32.5% 14.51 cells/min`、`Cliff 0 Safe rate 0.003` | 50×50 网格（200 u/cell）+ Stuck/Fall/Flow/Dead-end 标记 + 轨迹；**15 次逃逸活动却有 0 falls** 说明逃脱在原地打转 |
| **Causal Timeline · 120s** | 四泳道：Optic flow / Pool rates / Judge / Action | 悬停回看因果卡、点击冻结回放、cliff→转向的 `+ms` 延迟弧线 |
| **Escape Events** | 5 条 `anomaly_stuck_ramp`：`72.8s` / `29.1s` / `164.4s` / `32.0s` / `107.1s`，**DIST 全部 `0u`** | 逃逸事件表（行可点击跳转回放）；**零位移**是"逃逸无效"最直接的证据，也是 EVO pattern 的触发土壤 |
| **Health / Coverage / Coach** | 健康圈环 `50%`；`Coverage Trend 33%`（60s）；折叠面板 `LLM Coach Advice - glm-5.3-flash`、`turn bias = 1 / steering`、`stuck_threshold ≤ 10 s`；页脚 `21863.3 s · 0.80x real-time · step 25.7 ms · 0 dropped` | 健康评分、覆盖率趋势、教官建议与运行性能（0.80× 实时、无丢帧） |

> **截图解读**：这张图是"可解释性成立、能力边界暴露"的典型现场——归因（`anomaly_stuck_ramp`）、空间记忆（死端/回访）、健康度（50%）全部如实记录，但 5 次逃逸的位移都是 `0u`，说明**斜坡语义下的逃脱电流未能产生有效位移**；这正是 EVO 层 `ramp_trap` / `reflex_cooldown_gap` / `micro_loop_weave` 等 pattern 要捕获并寻求修复的目标现象（见下文「技能自我进化闭环」）。

### 布局与响应式

- **单列布局**（<1400px）：8 个区块按固定行高纵向排列，滚动浏览；
- **宽屏两列布局**（≥1400px 或手动切换）：grid areas 双栏——左栏 Vision→Causal→Motor→Activity map，右栏 Memory→Timeline→Events，footer 横跨双栏，总滚动高度压缩约 40%；
- **Layout 切换按钮**（header）：`Auto`（跟随窗口宽度）/ `Wide`（强制两列）/ `Single`（强制单列）三态循环，选择持久化在 `localStorage['fly64.layout']`；
- 行高单一来源：`dashboard.css` `:root` 的 `--row-*` CSS 变量，媒体查询只覆盖变量值。

### 面板明细

| 面板 | 功能 |
|------|------|
| **Vision** | 果蝇 270° 复眼视野预览 + 帧差异 + **16 扇区活跃度叠加**（活跃扇区青色描边） |
| **Causal Chain · why this action** | **决策解释卡**：五段因果链 RAW→SIGNAL→NEURAL→JUDGE→ACTION，实时归因当前动作由哪级控制级联生效（`decision_source`），悬停看判据、点选下钻 |
| **Neurons → controls** | 神经活动实时图表（前进/转向/跳跃/摇杆），gate 阈值虚线（0.4/2 Hz），溢出以 ▲ 标注而非截断 |
| **Activity map** | 全脑 WebGL 热力图（亮度=rolling rate，暗点=context） |
| **Spatial memory** | 空间记忆热力图（128/138px，50×50 grid）+ Stuck/Fall/Flow/Dead-end 标记 + 轨迹 + Stuck/Optic Flow 60s 趋势 |
| **Causal Timeline · 120 s** | **四泳道因果时间轴**（光流/池率+门控/判断条带+cliff▲/动作 x 线+jump 标记），泳道高度随 CSS 等比伸缩，悬停回看历史因果卡，点击跳转冻结回放，紫色弧线标注 cliff→转向响应的 **+ms 延迟** |
| **Escape Events & Coverage** | 逃逸事件表（行可点击 → 时间轴跳到事件前 2s 回放）+ 健康仪表圆环 + 覆盖率趋势 + Brain/EVO/Coach pills |

### 配套页面

| 页面 | 地址 | 说明 |
|------|------|------|
| **布局预览** | `/monitor-preview.html` | 模拟数据驱动的实时面板演示：单列/两列手动切换、区块标注（`--row-*` 变量与数值）、causal-off 模拟复选框；500ms 动画刷新，可暂停 |
| **布局线框图** | `/layout-wireframe.html` | 全部 8 个组件区块的线框图：双布局模式 + 四档响应式断点条（<650 / 650–1100 / 1100–1400 / ≥1400）+ grid-template-areas 原文 |
| **轨迹回放** | `/trajectory.html` | 马里奥运动轨迹回放 |

![布局预览页](docs/screenshots/monitor-preview.png)

![布局线框图](docs/screenshots/layout-wireframe.png)

**降级开关**：`http://127.0.0.1:8765/?noviz=1`（或 `localStorage['fly64.causal']='off'`）一键隐藏全部因果组件（`.causal-ui`），恢复基础布局；因果组件异常不会影响既有面板渲染（try/catch 隔离）。

**资产热更新**：`web/` 下的静态资产（css/js/预览/线框图页）为每请求即时读取——修改后刷新浏览器即生效，无需重启主进程；仅面板 `index.html` 本体与 `metadata.json`/`measured.bin` 仍是启动时快照。

### API 端点

仪表板与 EVO skill 共用同一组只读端点（全部为 JSON，`fetch_json()` 直读）：

| 端点 | 内容 | 主要消费方 |
|------|------|-----------|
| `/bridge-status.json` | 桥接状态（`pose`/`x`/`y`/`jump`/`age_ms`/`game_frame`） | 仪表板、EVO Monitor 阶段 |
| `/memory.json` | 空间记忆与异常态（`stuck_duration`/`loop_score`/`coverage_pct`/`anomaly_state`/`reflex_*`/`escape_behavior`/`health_score`/`scene_label`） | 仪表板、EVO pattern 条件 |
| `/flow.json` | 视觉与神经信号（`wall_score`/`ramp_score`/`ground_angle`/`tau`/`danger_red_index`/`emd_on_down`/`target_count`/`mb_*`/`dopamine_gain`/`decision_source`/门控/`evo_iter` + **6 项 plasticity 汇总**） | 仪表板、EVO pattern 条件 |
| `/events.json` | Escape 事件缓冲 + 计数器 | Escape 事件表 |
| `/history.json` | 信号历史（stuck/coverage/光流时序） | 60s 趋势图 |
| `/evolution.json` | EVO 轮次与 findings | 仪表板 EVO 胶囊 |
| `/help.json` | 求助快照（SEEK-HELP 分支） | Coach 面板 |
| `/active_strategy.json` | 教官写入的策略（脑模型热加载） | Coach 策略消费 |
| `/metadata.json` · `/trajectory.json` · `/trajectory-list.json` | 元数据 / 实时轨迹 / 轨迹清单 | 轨迹回放页 |
| `ws://127.0.0.1:8766/` | F643 二进制 packet（`causal_schema=1`；tick 行含 `decision_source`/`cliff_conf`/`stuck_conf`/`gate_forward`/`gate_jump`，帧行含 `sector_active`/`sector_contrast`） | 仪表板实时渲染 |

详见 [`docs/causal-chain-ui-design.md`](docs/causal-chain-ui-design.md)（设计）、[`docs/causal-chain-implementation.md`](docs/causal-chain-implementation.md)（实施）、[`docs/causal-chain-rollback-plan.md`](docs/causal-chain-rollback-plan.md)（回滚手册）。

## 🧠 技术架构

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│  SM64 Game   │───▶│  Shared Memory   │───▶│ Fly64 脑模型 │
│  (sm64ex)    │◀───│  Bridge (mmap)   │◀───│ 166,700 神经元│
│  渲染 3D画面 │    │  seqlock 协议    │    │ LIF 网络     │
└──────────────┘    └──────────────────┘    └──────────────┘
       │                     ▲                     │
       │ 写入 6面体贴图       │ 读取游戏帧          │ 计算控制信号
       ▼                     │                     ▼
┌──────────────────────────────────────────────────────────┐
│  Web Dashboard (http://127.0.0.1:8765)                   │
│  • 果蝇复眼视图 (270°) + 16扇区活跃叠加                  │
│  • 神经活动图表 • 全脑热力图 • 轨迹回放                  │
│  • 决策解释卡 (decision_source 实时归因)                 │
│  • 四泳道因果时间轴 (120s 回放 + 因果弧线)               │
│  • Escape 事件表 • 覆盖率趋势 • 健康评分仪表盘           │
└──────────────────────────────────────────────────────────┘
```

### 关键组件

| 组件 | 说明 |
|------|------|
| `fly64/main.py` | 主循环：视觉→脑模型→控制闭环 |
| `fly64/bridge.py` | 共享内存桥接（跨进程通信） |
| `fly64/model.py` | LIF 神经元模型 + 连接组加载 |
| `fly64/retina.py` | 球面复眼采样（270° 视野） |
| `fly64/memory.py` | 空间记忆 + 异常检测 + 反射回路 + 健康评分 |
| `fly64/data.py` | MaleCNS 脑数据下载与预处理 |
| `fly64/mushroom_body.py` | **P3** 多巴胺蘑菇体学习 (2000 KC, 5 MBON, 三元因子Hebbian可塑) + **R17** MBON 饱和稳态突触缩放 |
| `fly64/gain_modulation.py` | 多巴胺门控增益调制（visual/forward/turn/jump/recurrent 五通路，GAIN_MAX=2.5） |
| `fly64/telemetry.py` | 只读观测仪：F643 packet 发布（池率/流信号/扇区叠加/因果归因字段，`causal_schema=1`） |
| `skills/evolution_skill.py` | **EVO v3.0.0**：Monitor→Diagnose→Fix→Verify→Document 五阶段闭环 + 常驻循环 + pattern 匹配 + fix 效果量化 |
| `skills/default_patterns.json` | pattern 目录（13 条，JSON Schema draft-07 校验），含遥测自诊断 pattern |
| `skills/fix_catalog.json` · `skills/evolution_log.jsonl` | 修复条目（基线/结果/effective 判定）与逐轮执行日志 |
| `web/dashboard.js` | 仪表板前端：渲染 + `explain()` 因果链派生 + 四泳道时间轴 + `?noviz=1` 降级开关 |
| `skills/neural_viz_skill.py` | 离线因果链路分析技能（cliff 误报/门控抖动/preempt 风暴/信号→行动延迟检测 + Markdown 报告） |
| `web/trajectory.html` | 马里奥运动轨迹回放页面 |

## 🧠 视觉→运动控制机制详解

### 视觉能力增强路线图 (P1–P3)

| 阶段 | 新增能力 | 生物学基础 | 信号数 | 计算开销 | 关键效果 |
|------|---------|-----------|:------:|:--------:|---------|
| **P1a** | 颜色/UV通道 | R7 UV + R8 蓝/绿 + 对立通道 | +18 | +45 μs | 场景签名碰撞 10³/天→<1/年 |
| **P1b** | 4方向EMD运动检测 | T4(ON)/T5(OFF) Hassenstein-Reichardt | +10 | +35 μs | 运动覆盖 25%→80% |
| **P2** | 小目标追踪 | LPLC1/2 + LC11 中心-周边 | +7 | +80 μs | 平台跳跃 30%→65% |
| **P3** | 多巴胺蘑菇体学习 | Kenyon Cells + MBON + DAN | — | +30 μs | 经验关联学习 |
| | **合计** | | **+35** | **190 μs (0.95%)** | 视觉覆盖 ~38%→~90% |

### 完整闭环流程

```
┌─────────────────────────────────────────────────────────────┐
│  SM64 游戏引擎                                               │
│  渲染 3D 世界 → 六面体贴图 (384×256) @ 10Hz                  │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌────────────────────────┴────────────────────────────────────┐
│  ① 果蝇复眼采样 (SphericalRetina)                            │
│  1,536个小眼 × 7锥形采样 → 亮度/运动/颜色 三维编码            │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌────────────────────────┴────────────────────────────────────┐
│  ② 视网膜编码 (encode_retina)                                │
│  drive = 0.45×亮度 + 1.6×运动 + 0.25×颜色                    │
│  v[visual] += drive × 0.62                                  │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌────────────────────────┴────────────────────────────────────┐
│  ③ MaleCNS 连接组处理 (25.6M 突触)                           │
│  视觉细胞 → 中间神经元 → 运动指令层 (LIF 模型)                 │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌────────────────────────┴────────────────────────────────────┐
│  ④ 运动解码                                                 │
│  forward_rate → y轴 (前进) / right-left → x轴 (转向)         │
│  jump_rate → A键 (跳跃) / 250ms窗口 + 低通滤波                │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌────────────────────────┴────────────────────────────────────┐
│  ⑤ 共享内存桥接 → SM64 读取 → 马里奥移动                       │
└─────────────────────────────────────────────────────────────┘
```

### 视觉处理管道

#### 1. 六面体图集渲染
SM64 游戏通过 `fly64_vision.c` 以 10Hz 频率渲染六面立方体贴图，覆盖马里奥周围 **270° 水平视野**：
```
        [上]
  [左] [前] [右] [后]
        [下]
```
每个面 128×128 像素，拼为 **256×384 RGB 图集**，通过共享内存桥接传递给 Python 脑模型。

#### 2. 果蝇复眼采样
果蝇复眼不是"看整张图片"，而是**稀疏采样**：

| 参数 | 值 |
|------|-----|
| 视觉细胞数 | 1,536 个（MaleCNS `visual` 组） |
| 视野范围 | 270° 水平 × 144° 垂直 |
| 每小眼采样 | 7 加权点（1 中心 + 6 环形高斯锥） |
| 空间映射 | 基于 MaleCNS 实测 optic-column 排列 |

每个视觉细胞从图集中采样 7 个点，加权平均得到亮度值。采样方向基于 MaleCNS 数据集中的实际 optic-column 排列（`visual_pixels`），映射到约 270° 的球形视野。

#### 3. 视网膜编码
每个视觉细胞输出六维融合信号：
```python
brightness = frame @ [0.2126, 0.7152, 0.0722]     # 亮度 (luminance)
temporal   = abs(current_lum - prev_lum)            # 时域运动 (权重最高)
red_sal    = max(R - G, 0)                          # P1a 红色显著
uv_sal     = max(B - 0.5×(R+G), 0)                  # P1a UV逼近 (短波长)
green_sal  = max(G - 0.5×(R+B), 0)                  # P1a 绿色显著(原color项)

drive = np.clip(0.45×brightness + 1.6×temporal + 0.15×red_sal + 0.10×uv_sal + 0.25×green_sal, 0, 1)
```
**运动信号权重最高（1.6×）**，反映果蝇对运动的高度敏感。

### LIF 神经元模型详解

所有 166,700 个神经元使用 **Leaky Integrate-and-Fire** 模型：

#### 模型方程

```math
τ_m dv/dt = -v(t) + I_syn(t) + I_tonic + I_noise
```

离散化形式（dt = 20ms）：
```python
# 膜电位更新
v *= exp(-dt / τ_m)                # 漏电项 (τ_m = 100ms)
v += Σ(synaptic_input) × gain      # 突触输入
v += random_baseline × 0.22        # 背景噪声
v += tonic_current (0.18)          # 持续背景兴奋
v[visual] += sensory × 0.62        # 视觉驱动（仅视觉细胞）

# 放电判断
if v >= threshold (1.0):
    spike()
    v = reset (0.0)
```

#### 参数分析

| 参数 | 值 | 物理意义 | 影响 |
|------|:---:|:---------|:-----|
| `dt` | 20ms | 仿真步长 | 模型以 50Hz 运行，与游戏帧率解耦 |
| `τ_m` | 100ms | 膜时间常数 | 决定电位衰减速度，5个步长衰减到 36.8% |
| `threshold` | 1.0 | 放电阈值 | 电位超过此值则发放 spike |
| `reset` | 0.0 | 复位电位 | 放电后电位归零 |
| `tonic_current` | 0.18 | 背景兴奋 | 恒定的兴奋性驱动，维持基础活动 |
| `synaptic_gain` | 1.5 | 突触增益 | 放大突触输入强度 |

#### 单神经元动力学

```
膜电位 v
  ▲
1.0┤———— ║ ← 阈值 (threshold) 
  │       ║
  │   ╱╲  ║  ← 放电 (spike) → v = reset
  │  ╱  ╲ ║
  │ ╱    ╲║
0.0┤══════════════════════════════→ 时间
  │ ╲ ╱ ╲ ╱    ← 漏电 (leak)
  │  ╲╱  ╲╱     ← 突触输入累积
```

大约每 5 步（100ms）电位衰减到 36.8%，需要持续的突触输入才能达到阈值。

#### 突触传播

使用 **CSC (Compressed Sparse Column)** 稀疏矩阵进行高效的突触事件传播：
```python
current = w[:, fired].sum(axis=1)    # 所有放电神经元 × 突触权重
current *= synaptic_gain             # 增益放大
```

25.6M 突触连接，每次传播使用 CSC 格式，只遍历放电神经元对应的列，计算复杂度与放电率成正比。

### 运动解码机制

#### 运动神经元分组

| 组 | MaleCNS ID | 数量 | 功能 |
|:---|:----------|:----:|:-----|
| **forward** (DNg100) | 下行神经元 | 60 | 前进速度 |
| **turn_left** (DNa02/DNg13) | 下行神经元 | 40 | 左转强度 |
| **turn_right** | 下行神经元 | 40 | 右转强度 |
| **jump** (DNp01/DNp10) | 下行神经元 | 20 | 跳跃触发 |

#### 从放电率到控制信号

```python
# 1. 250ms 滑动窗口
recent = mean(history[last_13_steps])
forward_rate = mean(recent[forward_cells])
turn_rate = right_rate - left_rate

# 2. 编码为游戏摇杆
raw_y = clip((forward_rate - 0.008) × 2000, 0, 70)
raw_x = clip(turn_rate × 1100, -70, 70)

# 3. 低通滤波（平滑）
filtered_y = 0.78 × filtered_y + 0.22 × raw_y
filtered_x = 0.78 × filtered_x + 0.22 × raw_x

# 4. 死区判断（防抖动）
output_x = abs(filtered_x) >= 8 ? filtered_x : 0
output_y = filtered_y >= 8 ? filtered_y : 0

# 5. 跳跃门控
jump = jump_rate > 0.04 AND 距离上次跳跃 >= 800ms
```

#### 信号映射表

| 神经信号 | 范围 | 映射方式 | 游戏效果 |
|:---------|:----:|:---------|:---------|
| forward_rate | 0~50Hz | (rate - 0.008)×2000 | y=0~70 前进 |
| turn_rate | -50~50Hz | rate×1100 | x=-70~70 转向 |
| jump_rate | 0~50Hz | >0.04 触发 | A键跳跃 |

### Located vs Unlocated 神经元

仪表板显示 `140,638 located · 26,062 unlocated`，含义：

| 状态 | 数量 | 含义 |
|:----|:----:|:------|
| **Located** | 140,638 | 有实测三维空间坐标（soma位置），可在脑图谱上精确定位 |
| **Unlocated** | 26,062 | 只有连接组数据，无实测细胞体位置 |

#### 按种类分布

| 种类 | 定位率 | 未定位原因 |
|:----|:-----:|:----------|
| **cb_intrinsic** (脑内中间神经元) | 99.7% | 中央脑核心回路，标注最完整 |
| **visual_projection** (视觉投射) | 99.8% | 视叶→中央脑通路 |
| **ol_intrinsic** (视叶内部) | 91.4% | 大部分定位，小部分因密集难分辨 |
| **cb_sensory** (脑感觉神经元) | 0% | **细胞体外周**，不在 CNS 成像范围内 |
| **ol_sensory** (视叶感光细胞) | 0.5% | **光感受器在视网膜**，不在 CNS EM 数据中 |
| **vnc_sensory** (VNC感觉) | 0.03% | 外周感觉神经元，soma 在外周 |
| **sensory_ascending** (上行感觉) | 0% | 从外周→CNS，细胞体在外周 |
| **ENS** (内分泌) | 2% | 内分泌细胞分散，难以追踪 |
| **tbc** (未分类) | — | 功能尚未完全确定 |

**对运行的影响**：神经活动计算（LIF动力学、突触传播）完全正常，仅脑图谱可视化中外周感觉神经元用随机位置占位显示。

### 神经元定位统计

```python
Total: 166,700 neurons
Located (measured soma): 140,638 (84.4%)
Unlocated: 26,062 (15.6%)

主要未定位来源:
  cb_sensory + ol_sensory + vnc_sensory + sensory_* ≈ 17,843 (68.5% of unlocated)
  ol_intrinsic (low confidence): 7,718 (29.6% of unlocated)
  其他: ≈501 (1.9% of unlocated)
```

## 🔍 决策级联与因果归因（Neural Causal Chain）

马里奥的每一步动作由六级控制级联按优先级覆盖产生。仪表板新增的因果链组件让这条链路**全程可解释**：

### 控制级联优先级（每 tick，高→低）

| 优先级 | `decision_source` | 触发条件 | 动作 |
|:----:|:------------------|:---------|:-----|
| 1 | `dialogue` | 对话框激活（受限刺激） | 停止/交互/回避 |
| 2 | `cliff_reflex` | `cliff_confirmed` + 快速绿幕跌落 | 急转 ±60 + 短暂后退 |
| 3 | `anomaly_reflex` | 异常运动态（stuck_ramp/oscillating/wall_stuck/micro_loop） | 反射动作 |
| 4 | `escape` | 卡住/循环/坠落 | 相位式转向+前冲爆发 |
| 5 | `collision` | 光流不对称>±0.3 或 looming>0.4 | 转离障碍/减速 |
| 6 | `jump` | tau 接近/sky 触发跳跃池 | A 键 |
| 7 | `steering` | 其余 | 纯神经解码转向/前进 |

`main.py` 在级联末端写入 `decision_source`（与实际下发的 control 严格一致），`telemetry.py` 将其连同 `cliff_conf`/`stuck_conf`/`gate_forward`/`gate_jump` 注入每个 WS packet tick 行（`causal_schema=1`）。

### 仪表板因果组件

- **决策解释卡**：五段链 RAW(视觉帧)→SIGNAL(光流)→NEURAL(池率+门控)→JUDGE(判断文本)→ACTION(x/y/ack)。被高优先级抢占的段显示删除线降饱和——直观回答"**为什么现在这个动作**"
- **16 扇区叠加**：眼图上活跃扇区描边（帧间对比度 bit 掩码），显示视觉信号的空间来源
- **因果时间轴**：120s 四泳道（光流/池率+gate 虚线/判断条带+cliff▲/动作），悬停回看、点击冻结回放、Escape 表行点击跳转事件前 2s
- **因果弧线**：cliff 确认 → 转向响应的紫色弧线 + `+ms` 延迟标注——量化"**看到→反应**"用时
- **离线分析**：`python3 -m fly64.skills.neural_viz_skill`（cliff 误报/门控抖动/preempt 风暴/延迟分布报告）

### 兼容性与回滚

- 协议为 **schema=3 加法演进**（`causal_schema=1` 哨兵），旧客户端 `.get()` 取键不受影响；发布增量 <4KB/s
- 全部因果组件携带 `causal-ui` 类，`?noviz=1` 一键隐藏；渲染 try/catch 隔离，因果异常不拖垮既有面板
- git 逐阶段提交（P0→P3），可独立 revert；基线 tag `causal-baseline`

### 已知局限：语义场景无法识别与利用（当前实测）

**实测监控截图**（2026，锁门卡住现场，因果可视化运行中）：

![锁门场景监控：因果卡显示 escape 归因、时间轴四泳道、空间记忆死端标记](docs/screenshots/locked-door-stuck-monitoring.webp)

截图现场读数与解读：

| 仪表板读数 | 值 | 解读 |
|-----------|-----|------|
| 画面 | 对话框 *"You need a key to open this door"*，马里奥面对锁门 | **语义任务场景**：需要先取得钥匙，视觉系统无法理解该提示 |
| `decision_source` | `escape` | 归因正确：动作确实由逃脱级联产生 |
| JUDGE 段 | `escape (stuck 1.00) preempts forward gate ✗` | stuck 置信度 1.0（卡住超 100s），逃脱级联完全压制前进门控 |
| ACTION 段 | `x=60 y=-50 → ack 5ms` | 转向+后退的逃脱相位，在锁门前来回摆动 |
| Stuck 计时 | **101.98s** · Loop 10.19 | 卡住检测持续触发，但逃脱只能原地打转 |
| Spatial memory | 死端 X 标记 + 3 个失败点 | 锁门被正确记为死路，但**没有"绕路去拿钥匙"的目标表征** |
| Coverage | 0.2% · 0.00 cells/min | 探索完全停滞——能力边界所致，非 bug |

实际运行中暴露的典型场景：马里奥面对锁门，画面出现对话文字 *"You need a key to open this door"*，此时：

| 环节 | 现状 | 后果 |
|------|------|------|
| 视觉采样/编码 | 只输出亮度/运动/颜色/光流/16 扇区能量，**无 OCR/文字理解** | "需要钥匙"这一关键语义信息完全丢失 |
| 判断逻辑 | 对话框检测仅二值（对话框出现/消失），且 3 次无奖励交互后触发习惯化抑制（2 分钟封锁 + 远离） | 马里奥**不会去获取钥匙**，只会反复撞门→放弃→离开 |
| 记忆系统 | FailureMemory 记录死端/坠落格 | 锁门被记为"死路"，但**不知道绕路目标**（钥匙在哪） |
| 因果归因 | decision_source 如实标注 `dialogue`/`escape` | 归因正确，但**归因正确 ≠ 行为正确**——系统知道自己为什么卡住，却没有获取钥匙的动作原语 |

**结论**：因果可视化解决的是"可解释性"，而非"能力"。归因链完整正确（escape 归因、stuck 1.00、死端标记全部准确），但系统在语义层面**三重缺失**：

1. **感知缺失**：无法读取对话文字，"需要钥匙"这一任务语义丢失
2. **认知缺失**：无目标表征——知道门是死路，不知道钥匙是解决方案
3. **行为缺失**：动作原语只有转向/前进/跳跃，没有拾取/使用道具

由此形成当前可观测的行为瓶颈：**锁门前 stuck→escape 死循环**（stuck 101s+，coverage 0%），逃脱逻辑在语义死角内无法自解。

### 技能自我进化闭环（EVO Round 1–17，Brain v1.0.0 → v2.11.0，Skill v3.0.0）

EvolutionSkill 具备**自我更新迭代**能力，七步循环已制度化：

```
1. EXECUTE      run_one_cycle() 实时仪表板数据
2. DETECT       目录未覆盖的新失败模式
3. LEARN        新 pattern 写入 default_patterns.json + 代码修复
4. PIN          回归测试固化（tests/test_evolution_capability.py）
5. VERSION      强制递增 BRAIN_VERSION
6. CONSOLIDATE  重启脑模型（"睡一觉"——新能力重启后才加载）
7. RECORD       agent.md 闭环总结 + 推送；仪表板 /evolution.json 实时展示
```

#### v3.0.0 五阶段执行管线（Monitor → Diagnose → Fix → Verify → Document）

七步是**轮次级制度**，v3.0.0 起每个轮次内部由一条五阶段管线自动执行（`fly64/skills/evolution_skill.py`）：

| 阶段 | 组件 | 行为 |
|------|------|------|
| ① Monitor | `DataCollector` | 轮询 `/bridge-status.json`、`/memory.json`、`/flow.json`、`/events.json` 等端点，维护 120s 滚动窗口（位置/控制/stuck/覆盖率） |
| ② Diagnose | `DiagnosisEngine` + `PatternCatalog` | 按 `default_patterns.json` 的 **13 条 pattern** 逐条匹配（JSON Schema draft-07 校验），条件字段缺失时**主动生成 `telemetry_gap` finding**（不再静默失效） |
| ③ Fix | `FixCatalog` | 记录版本化修复条目（`fix_NNNN`，含基线 stuck/coverage、诊断原文、fix_template、目标文件），落盘 `skills/fix_catalog.json` |
| ④ Verify | `VerificationEngine` | 修复后 60s 观察窗，量化 effectiveness score（stuck 降幅 0.7 + 覆盖率增幅 0.3），≥0.3 判有效；判定无效即回滚候选 |
| ⑤ Document | `SelfDocumenter` | 自动重写 `skills/README.md`（metrics/pattern 目录/fix 历史/最近周期摘要），并追加 `skills/evolution_log.jsonl` |

**常驻循环**（不再是一次性跑 10 轮）：

```bash
# 10s 间隔，auto-fix 开启，持续运行（86400 轮 ≈ 10 天）
python3 fly64/skills/evolution_skill.py --auto-fix --interval 10 --max-iterations 86400
```

> **修复语义**：`--auto-fix` 负责"记录 + 量化验证"，即把 pattern 的 `fix_template`（精确到文件与代码块）写入 catalog 并测量效果；**实际代码改动仍需按 fix_template 执行**（人工或 agent），brain 侧改动经重启（CONSOLIDATE）后生效——这正是"验证窗口横跨重启会导致 verdict 失效"这一已知口径问题的来源，跨会话的旧 fix 会被标记 `reverted` 以免污染有效率统计。

**近期新增 pattern**（R16/R17 + 遥测自诊断）：

| Pattern | 触发条件 | 捕获现象 |
|---------|---------|---------|
| `micro_loop_weave` | `anomaly_state=micro_loop` + `loop_score≥0.8` + `stuck≥60s` | 交替转向仍在原地编织 |
| `micro_loop_weave_signal` | `loop_score≥0.95` + `escape_behavior` + `stuck≥45s` | **纯行为信号判定**：绕过 anomaly 分类器，脑报 idle 而行为已编织时提前 15s 报警 |
| `cliff_standoff` | `cliff_confirmed` + `cliff_standoff_s≥20s` + `escape` | 悬崖边缘对峙驻留（切向绕行失效） |
| `mbon_saturation` | MBON 列持续饱和（R17 稳态缩放触发） | 蘑菇体输出贴在 `tanh` 绝对值 ≈1 的饱和区、学习停滞 |
| `dopamine_plateau` | `dopamine_gain_avg≥2.0` + `learning_progress≤0.05` + `stuck≥60s` | 多巴胺增益饱和、可塑性收敛 |
| `telemetry_gap` | 任一 pattern 的条件字段在 telemetry 中缺失 | **自诊断**：把"监控盲区"本身变成一条 finding（如曾据此发现 5 个 control 类字段未暴露、3 条 pattern 实际失效） |

**Plasticity 遥测**：`flow.json` 现直接输出 6 项可塑性汇总——`dopamine_gain_avg`、`learning_progress`、`mushroom_weight_changes`、`reward_trend`、`error_gradient_mean`、`gain_update_count`（brain 侧每 100 tick 聚合），使 `dopamine_plateau` pattern 与 Documenter 的 Plasticity Metrics 表真正有数据可用。

| 轮 | Brain v | 获得能力 | 触发场景 |
|:--:|:-------:|:---------|:---------|
| 1 | 1.0.0 | circle_loop 地形门控 | 无障碍转圈 |
| 2 | 1.0.x | 斜坡脱困覆盖 | 斜坡卡死 |
| 3 | 1.1.0 | 伴发放电比较器（视觉盲区） | 墙角卡死 |
| 4 | 1.2.0 | 双区对话检测 + 交互习惯化 + 场景命名 v2 + 全监控 | 钥匙门提示 |
| 5 | 1.3.0 | 交互习惯化 + 上置框双区检测制度化 | 钥匙门上置提示框 |
| 6 | 1.4.0 | 自适应反射冷却（stuck 越久冷却越短，下限 25%）+ 坠落恢复初始方向随机化 | fallen 恢复循环固定左转失效 |
| 7 | 2.0.0 | 🎨 颜色/UV 视觉 + 🌀 4方向 EMD + 🎯 小目标追踪 + 🧠 多巴胺蘑菇体学习（35 新信号，覆盖 38%→90%） | FlyWire MaleCNS 差距分析 |
| 8 | 2.1.0 | T4/T5 式 HRC 方向选择运动检测 + LC4 looming 种群 + 自适应相关接入碰撞规避 | brightness-not-flow 根治 |
| 9 | 2.2.0 | 室内封闭检测（`enclosure_score`/天花板×墙壁）+ 天空蓝主导门控（`sky_score` 受 `upper_blue` 限制）+ `indoor` 地形类 | 室内场景被误判为开阔天空 |
| 10 | 2.3.0 | `local_breakout`：持续 `micro_loop` 触发 `forced_bold_explore` 强制突破（Skill 2.7.0） | 497.9s 零位移循环、老地图上 bold 门控从不触发 |
| 11 | 2.5.0 | 方向性开口电流注入（16 扇区推导 `opening_left/right` 注入转向池，取代随机 `escape_x`）+ 位移多巴胺报告（Skill 2.8.0） | 逃逸方向随机导致无效 |
| 12 | 2.6.0 | `reflex_ineffective` 升级判据（反射活跃但 60s 位移<30u → 判定无效并向教官求助） | 497.9s/0u 事件类：反射活跃掩盖了真实卡死 |
| 13 | 2.7.0 | 对话暂停等待场景标签（`对话暂停等待 #hash`）+ 蘑菇体挫折多巴胺（负 DA，教学"此场景被封锁"）+ `llm_consult` 自加载 `plugin/llm.env`（Skill v3.0.0） | 钥匙门对话场景 |
| — | 2.8.0 | **P1 神经接管**：删除 11 处 A 类 Python 旁路，行为回归 LIF 网络 | 符号化旁路污染神经决策 |
| 14 | 2.9.0 | TurnAdaptation 自发交替（转向疲劳→竞争回路接管）+ MB 异常镜像 | 单侧持续转向疲劳 |
| t13 | 2.9.1 | LLM Coach Advice 真正生效（`exploration.turn_bias` 死写入修复 + 单位换算/夹紧） | 教官建议空转 |
| t16 | 2.10.1 | 监控可见性与布局（状态胶囊行、Coach 折叠面板、对话暂停决策优先级、共享 `/flow.json`、`/active_strategy.json` 路由） | 仪表板信息密度不足 |
| 16 | 2.10.0 | oscillation→forward 突破（`TurnAdaptation.breakout_drive`）+ skill 层遥测暴露（`decision_source`/`cliff_conf`/门控/`hrc_*`/`mb_*`）+ `telemetry_gap` 自诊断 + `micro_loop_weave`/`cliff_standoff` pattern + **常驻 EVO 循环**（`--max-iterations 0`）+ 场景识别在线校准 | 原地编织、悬崖对峙、监控盲区 |
| 17 | 2.11.0 | MBON 饱和稳态突触缩放（50 帧 `tanh` 绝对值 ≥0.98 → 该列 ×0.9）+ `breakout_hint` 反射相位混合（编织检测偏置 micro_loop 反射朝前冲爆发）+ `mbon_saturation` pattern | MBON 列饱和、输出贴顶学习停滞 |

Round 4/5 正是**能力边界判定的实战示范**：钥匙门的"行为层"问题（反复撞门）属内生能力群 → skill 自己进化出双区检测+习惯化解决；而"语义层"问题（文字内容不可读、需要钥匙的任务理解）超出内生边界 → 走 SEEK-HELP 向教官层求助（Phase 4）。

### 架构原则：训练教官层 vs 社交层 vs 果蝇自身能力群

上述三重缺失**不应也不需要在果蝇脑模型内解决**。按能力归属分层：

| 层 | 能力归属 | 具体能力 | 实现载体 |
|----|---------|---------|---------|
| **训练教官层**（教学/语义） | 非果蝇自身，属外部教学智能 | 对话文字理解（"need key"）、任务分解（取钥匙→开门）、场景问答、课程设计（奖励塑形/分阶段目标） | LLM/VLM（外部调用，如 Phase 4 的 P4.1/P4.3） |
| **社交层**（寻助/协作） | 果蝇系统对外沟通的能力 | **识别自身能力边界 → 形成具体求助要求 → 向教官层/外部系统/人提出**（如：血量归因显示"escape 黏滞"，技能自我进化判定反射参数调优超出内生能力 → 生成结构化求助单：现象数据+已试方案+期望能力） | skills 自我进化管线（evolution_skill）+ 结构化请求协议 |
| **果蝇神经元自身能力群**（具身/本能） | 果蝇脑模型应内生的能力 | 光流避障、悬崖反射、卡住/逃脱、空间记忆与死端回避、新奇性探索、习惯化——即本项目的 memory.py/model.py/reflex 全部既有回路 | LIF 连接组 + 记忆/反射模块（已落地 ✅） |

分层边界原则：

- **语义不下沉**：LLM 理解结果不以"语义向量"形式注入果蝇脑——果蝇没有语言中枢；教官层的输出只能降维为果蝇已有的信号通道（目标方向偏置、奖励/新颖性调制、反射触发），与嗅觉/新奇性等本能信号同构
- **本能不外包**：光流、反射、空间记忆等果蝇自身能力群必须由脑模型内生计算（当前已实现），不依赖 LLM 实时介入——断网也要能活
- **交互接口**：教官层通过类似"蛰足终器"（sub-esophageal 求食神经元）的下行通道施加调制——对应工程实现即 escape 优先级之上的一个"教官指令层"（goal bias），而非接管摇杆
- **寻助即社交**：技能自我进化遇到超出自身能力群的问题时，正确的做法不是强行硬解，而是**形成具体要求对外求助**——这是社交能力。求助单必须结构化：`能力缺口`（需要什么）、`证据`（因果链/decision_source/指标数据）、`已试方案`（内生尝试及失败原因）、`期望交付`（明确的能力/参数/知识）。因果可视化正是寻助的证据底座：`decision_source` 分布异常即"超出内生能力"的客观信号
- **社交能力可自我训练**：社交不是静态接口，而是自我进化闭环中的可训练维度。每次求助都是一次社交样本——`求助时机`（该问才问 vs 过早求助/硬解延误）、`请求质量`（结构完整度、证据充分性、教官一次响应成功率）、`成果转化`（获得的能力是否真的修复了问题）均可量化评分并进入进化循环。训练目标：**求助更少但更准**——内生能力群随教学扩展，能力边界外推，社交调用频率自然下降而单次价值上升

因此因果可视化的归因价值进一步明确：`decision_source` 能清晰区分"本能在驱动"（steering/cliff_reflex/escape）、"教学在驱动"（未来的 instructor 指令层）与"社交在驱动"（寻助请求的生成与响应）——**教官教什么、果蝇学没学会、何时该向外求助，在因果链上一目了然**。



## 🗺️ 导航能力分析 & 实施路线图

基于对 Fly64 当前控制能力的全面分析（详见 `fly64-control/final-report.md`），以下为分阶段实施计划：

### 当前能力评估

| 能力 | 状态 | 说明 |
|------|:----:|------|
| 前进控制 | ✅ | y∈[0,70]，无反向后撤 |
| 转向 | ✅ | x∈[-70,70]，左右竞争编码 |
| 跳跃 | ✅ | jump_rate 门控 + 800ms 冷却 |
| 光流计算 | ✅ | 8 方位不对称/looming/cliff/tau + 地形 8 类分类（Phase 2 已落地） |
| 卡住检测 | ✅ | StuckDetector 三信号融合 + 坠落检测（Phase 1 已落地） |
| 路线重复检测 | ✅ | loop_score + 50×50 空间记忆网格 + 场景签名数据库 |
| 失败记忆避让 | ✅ | FailureMemory 死端/坠落格避让方向 |
| 六级决策级联 | ✅ | 悬崖→反射→攻击→碰撞→逃脱 + decision_source 归因审计 |
| 因果链路可视化 | ✅ | 决策解释卡/扇区叠加/时间轴/回放（本变更） |
| 技能自我进化闭环 | ✅ | 七步制度化循环（EXECUTE→DETECT→LEARN→PIN→VERSION→CONSOLIDATE→RECORD）+ v3.0.0 五阶段执行管线（Monitor→Diagnose→Fix→Verify→Document，13 条 pattern / 60s 效果验证 / `telemetry_gap` 自诊断 / 常驻循环），已完成 17 轮（Brain v1.0.0→v2.11.0，Skill v3.0.0），每轮能力经回归测试固化、重启生效、仪表板 `/evolution.json` 实时展示 |
| 社交寻助能力 | 🔧 制度化 | SEEK-HELP 分支 + 结构化求助单 + 社交三指标自训练（v2.4.0，待实战触发） |
| 场景语义识别 | ❌ 缺失 | 视觉仅编码亮度/运动/颜色/光流，**无法理解画面语义**——如对话文字"You need a key to open this door"这类**需要钥匙**的提示无法被识别和利用 |
| 道具获取能力 | ❌ 缺失 | 无钥匙/星星等道具的定位、路径规划与拾取动作；遇锁门只能触发习惯化回避（3 次无奖励交互后抑制 2 分钟并远离，见 Interaction loop breaker） |
| 路径规划 | ❌ 缺失 | 无目标/奖励规划（远期） |

### 视觉处理瓶颈

```
384×256×3 RGB (294,912 像素)
    ↓ 99.5% 空间压缩
1,536 个视觉细胞 × 7 锥形采样
    ↓ 仅 ~5-15% 突触每 tick 活跃
25.6M 突触连接 (166,700 神经元)
    ↓ 0.1% 神经元驱动行为
160 个运动命令神经元 → 摇杆信号
```

### Phase 1: 卡住检测 + 空间记忆地图（1-2 天）

**优先级最高**，卡住信号已经可用，零成本启用。

| 任务 | 文件 | 行数 | 说明 |
|:----|:----|:----:|:-----|
| **P1.1** 卡住检测器 | `fly64/memory.py` | ~15 | 利用 temporal_energy + game_frame 检测停滞状态，触发随机转向逃脱 |
| **P1.2** 空间网格地图 | `fly64/memory.py` | ~120 | 50×50 单元地图，visit-counter，距上次访问时间衰减 |
| **P1.3** 探索/利用切换 | `fly64/memory.py` | ~40 | loop_score 综合速度、网格访问频率、时域能量、游戏帧停滞 |
| **P1.4** 集成到主循环 | `fly64/main.py` | ~30 | 每 publish 周期更新地图，注入 novelty 信号到 model.step() |
| **P1.5** 视觉偏置 | `fly64/model.py` | ~20 | Memory→Visual Habituation：novelty 信号调制视觉驱动的 0.62 增益 |
| **P1.6** 仪表板可视化 | `web/dashboard.js` + `web/index.html` | ~100 | 热力图显示访问频率，当前位置标记 |
| **P1.7** 轨迹保存增强 | `fly64/main.py` | ~47 | 退出时自动保存 .trajectory.npz |

**总计**: ~372 行，7 个文件

**效果**: 马里奥卡住时能检测 → 停止前进 → 随机转向 → 检测是否脱离 → 恢复正常巡航

### Phase 2: 仪表板增强 + 运动分析（~3 天）

| 任务 | 说明 |
|:----|:------|
| **P2.1** 访问热力图 | 基于空间地图渲染 coverage 热力图 |
| **P2.2** 路径回溯叠加 | 多条历史轨迹叠加对比 |
| **P2.3** 光流计算 | 利用 1,536 个视觉细胞的空间分布计算方位角方向运动 |
| **P2.4** 逼近指数 (looming index) | 检测视野中对称膨胀的运动模式 |

### Phase 3: 地标记忆（~5 天 + 研究）

| 任务 | 说明 |
|:----|:------|
| **P3.1** 视网膜签名提取 | 1,536 维 retina 输出 → 随机投影 → 128 维签名 |
| **P3.2** 签名数据库 | Top-K 相似度检索，余弦距离 |
| **P3.3** 地标触发的行为调制 | 已知位置 → 降低 novelty、熟悉区域加速 |
| **P3.4** 参考实现 | 果蝇 snapshot homing 机制的工程化实现 |

### Phase 4（远期）: 训练教官层 — 语义教学与任务引导

解决上述"需要钥匙"类场景。**架构定位：教官层是果蝇脑之外的教学智能，不侵入果蝇神经元回路**（见上文分层原则）：

| 任务 | 层 | 说明 |
|:----|:----|:------|
| **P4.1** 对话文字理解 | 教官 | 对话框裁剪 → OCR/VLM 提取任务语义（"need key"→教学目标：钥匙） |
| **P4.2** 教官指令通道 | 教官→果蝇接口 | LLM 结论降维为果蝇可感的调制信号：目标方向偏置 / 奖励 / 新颖性增益（类似蛰足终器下行通路），注入 escape 之上的"instructor"优先级层 |
| **P4.3** 课程与奖励塑形 | 教官 | 分阶段教学（先认钥匙→再走近→再拾取），VLM 场景问答决定下一课 |
| **P4.4** 本能回路巩固 | 果蝇 | 教官反复引导的成功路径经记忆/场景签名固化，逐步减少教官介入（果蝇"学会"） |
| **P4.5** 道具行为原语 | 果蝇 | 拾取/开门作为新动作原语进入控制级联（本能层的扩展，仍由神经解码触发） |
| **P4.6** 社交能力自训练 | 技能 | 在自我进化闭环中训练社交维度：记录每次寻助的时机/请求质量/一次响应率/成果转化，评分进入 patterns 进化循环；训练目标"求助更少但更准"——内生能力边界随教学外推，社交调用频率下降而单次价值上升 |

### 评估指标

| 指标 | 当前基线 | Phase 1 目标 | 测量方式 |
|:----|:--------:|:-----------:|:---------|
| 卡住响应时间 | 无响应 | <5 秒 | game_frame 停滞 → 转向 |
| 唯一位置覆盖/分钟 | ~50 | ~80 | 空间网格中活跃单元数 |
| 路径重叠率 | 无法检测 | <30% | 回访单元 / 总访问单元 |
| 平均前进速度 | 30-70 | 30-70 (保持) | y 控制信号均值 |
| 转向多样性 | ±69 | 保持 | x 控制信号标准差 |
| 探索半径（max distance） | ~3000u | ~5000u | max(当前位置距起点距离) |

## 🔧 常见问题

### Q: 游戏崩溃（Segmentation fault）
**原因**: GLEW 未正确初始化。确保：
```bash
# 在 fly64_vision.c 中添加 glewInit()
# 已在 patches/sm64ex-fly64.patch 中包含此修复
```

### Q: Frame difference 没有变化
**原因**: 合成世界场景变化太小。已在 SyntheticWorld 中添加高频闪烁。

### Q: 脑数据下载慢
**原因**: Google Cloud Storage 带宽限制。使用 curl（非 aria2c）可避免文件截断。

### Q: 仪表板 "Connecting..."
**原因**: WebSocket 连接未建立。检查浏览器是否可访问端口 8766。

## 📜 许可证

本项目基于 [ornata/fly](https://github.com/ornata/fly)（MIT License）修改。
MaleCNS 数据集遵循 [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/)。
Super Mario 64 为 Nintendo 版权作品，需要用户自行提供合法获取的 ROM。

## 🙏 致谢

- [ornata/fly](https://github.com/ornata/fly) — 原始 Fly64 项目
- [MaleCNS](https://male-cns.janelia.org) — 果蝇中枢神经连接组
- [sm64ex](https://github.com/sm64pc/sm64ex) — Super Mario 64 PC 移植
- [NeuroMechFly](https://www.nature.com/articles/s41592-024-02497-y) — 果蝇视觉参考