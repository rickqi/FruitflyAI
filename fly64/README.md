# FruitflyAI — Fly64: 果蝇大脑控制 Super Mario 64

[![Fly64 Neural Observatory](https://img.shields.io/badge/Fly64-Neural%20Observatory-6cdaed)](https://github.com/rickqi/FruitflyAI)

将果蝇（Drosophila）真实神经连接组（MaleCNS v1.0，**166,700 神经元，2,560 万突触连接**）接入 Super Mario 64，实现完整的视觉→神经→运动控制闭环。

## 🖥️ 支持平台

| 平台 | 状态 | 说明 |
|------|------|------|
| **macOS** (原始) | ✅ | Apple Silicon (M1/M2), Homebrew |
| **WSL2 Ubuntu 22.04** | ✅ **已验证** | Windows 10/11 + WSL2 + WSLg |
| **Linux (Ubuntu 22.04+)** | ✅ 理论可行 | 需 x86_64 + NVIDIA/Intel GPU |
| **原生 Windows** | ❌ | 需要 MSYS2 + 大量移植，不推荐 |

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
└──────────────────────────────────────────────────────────┘
```

### 关键组件

| 组件 | 说明 |
|------|------|
| `fly64/main.py` | 主循环：视觉→脑模型→控制闭环 |
| `fly64/bridge.py` | 共享内存桥接（跨进程通信） |
| `fly64/model.py` | LIF 神经元模型 + 连接组加载 |
| `fly64/retina.py` | 球面复眼采样（270° 视野） |
| `fly64/telemetry.py` | 仪表板遥测数据 |
| `fly64/data.py` | MaleCNS 脑数据下载与预处理 |
| `web/trajectory.html` | 马里奥运动轨迹回放页面 |

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