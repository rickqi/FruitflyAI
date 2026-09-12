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

游戏/模型运行时访问 **http://127.0.0.1:8765/**：

| 面板 | 功能 |
|------|------|
| **Vision** | 果蝇 270° 复眼视野预览 + 帧差异 |
| **Neurons → controls** | 神经活动实时图表（前进/转向/跳跃） |
| **Brain** | 全脑 WebGL 热力图 |
| **Trajectory** | 马里奥运动轨迹回放（`/trajectory.html`） |

API 端点：
- `http://127.0.0.1:8765/trajectory.json` — 实时运动轨迹数据
- `http://127.0.0.1:8765/bridge-status.json` — 桥接状态

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
│  • 果蝇复眼视图 (270°) • 神经活动图表 • 全脑热力图      │
│  • 轨迹回放 • 实时数据 WebSocket                         │
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
| `web/trajectory.html` | 马里奥运动轨迹回放页面 |

## 🧠 视觉→运动控制机制详解

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
每个视觉细胞输出三维融合信号：
```python
brightness = frame @ [0.2126, 0.7152, 0.0722]     # 亮度 (luminance)
temporal   = abs(current_lum - prev_lum)            # 时域运动 (权重最高)
color      = max(green - 0.5×(red+blue), 0)         # 颜色对比

drive = 0.45×brightness + 1.6×temporal + 0.25×color
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

## 🗺️ 导航能力分析 & 实施路线图

基于对 Fly64 当前控制能力的全面分析（详见 `fly64-control/final-report.md`），以下为分阶段实施计划：

### 当前能力评估

| 能力 | 状态 | 说明 |
|------|:----:|------|
| 前进控制 | ✅ | y∈[0,70]，无反向后撤 |
| 转向 | ✅ | x∈[-70,70]，左右竞争编码 |
| 跳跃 | ✅ | jump_rate > 0.04Hz 触发 |
| 场景识别 | ⚠️ 局部 | 仅时域对比检测逼近物体，无深度/物体识别 |
| 光流计算 | ❌ 缺失 | temporal_energy 是全局标量，无方向运动检测 |
| 卡住检测 | ❌ 未使用 | temporal_energy + game_frame 信号存在但无逻辑使用 |
| 路线重复检测 | ❌ 缺失 | 仅 260ms 神经记忆窗口 |
| 路线记忆 | ❌ 缺失 | 无空间表征 |
| 路径规划 | ❌ 缺失 | 无目标/奖励/地图 |

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