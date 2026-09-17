# Fly64 脑模型跨机部署分析报告 — Linux 脑模型 ↔ Windows SM64 游戏

> **分析日期**: 2026-09-15 | **脑模型**: Fly64 v2.13.3  
> **核心问题**: 是否支持在一台 Linux 主机运行脑模型，另一台 Windows 主机运行 SM64 游戏  
> **当前架构**: 单机 WSL2 — 脑模型 + SM64 均在同一 Linux 内核，通过 mmap 共享内存通信  
> **建议状态**: ✅ 可行（同局域网），❌ 不可行（跨互联网/广域网）

---

## 目录

1. [背景与当前架构分析](#1-背景与当前架构分析)
2. [跨机部署的核心障碍](#2-跨机部署的核心障碍)
3. [可行方案对比](#3-可行方案对比)
4. [推荐方案详细设计：TCP 代理桥](#4-推荐方案详细设计tcp-代理桥)
5. [帧数据传输方案](#5-帧数据传输方案)
6. [具体实践计划](#6-具体实践计划)
7. [风险与权衡](#7-风险与权衡)

---

## 1. 背景与当前架构分析

### 1.1 当前单机 WSL 架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Windows 桌面 (Windows 10/11)              │
│                                                              │
│  ┌────────────────── WSL2（Ubuntu 22.04）──────────────────┐  │
│  │                                                         │  │
│  │  ┌───────────────┐     mmap共享内存     ┌──────────────┐  │
│  │  │  Fly64 脑模型  │ ◄──────────────────► │ sm64ex (补丁) │  │
│  │  │  main.py      │     /tmp/f64b_*     │  C 语言游戏    │  │
│  │  │  model.py     │     ~701KB          │  30fps读帧    │  │
│  │  │  bridge.py    │     seqlock无锁      │  游戏逻辑+渲染 │  │
│  │  │  50Hz 写控制   │                     │               │  │
│  │  └───────┬───────┘                     └───────┬───────┘  │
│  │          │  读取帧数据/写入按钮                  │          │
│  │          └─────────────────────────────────────┘          │
│  │                                                         │
│  │              ┌──────────────────────────────┐            │
│  │              │  WSLg (GUI 转发层)            │            │
│  │              │  Weston 合成器 + FreeRDP      │            │
│  │              │  SM64 的 SDL2/OpenGL 渲染     │            │
│  │              │  → 通过 RDP 推送帧到 Windows   │            │
│  │              └──────────────┬───────────────┘            │
│  └─────────────────────────────┼───────────────────────────┘
│                                │
│                    ┌───────────▼───────────┐
│                    │  Windows 桌面窗口       │
│                    │  显示 SM64 游戏画面     │
│                    │  + Fly64 Web 仪表板    │
│                    │  (http://127.0.0.1:3080)│
│                    └───────────────────────┘
└──────────────────────────────────────────────────────────────┘
```

**关键事实**: 脑模型（Python）和 SM64（C 游戏）都运行在 **同一个 WSL Linux 内核**中。mmap 是**标准 Linux 进程间通信(IPC)**——共享内存对象由 Linux 内核管理，两个进程在同一地址空间内直接读写。延迟约 **~8μs**。

### 1.2 目标架构

```
┌──────────────────────────────┐     ┌──────────────────────────────┐
│      Linux 主机 A             │     │      Windows 主机 B           │
│                              │     │                              │
│  ┌────────────────────────┐  │     │  ┌────────────────────────┐  │
│  │  Fly64 脑模型           │  │     │  │ sm64ex 游戏            │  │
│  │  main.py + model.py    │  │     │  │ SDL2 + OpenGL 渲染     │  │
│  │  bridge.py (网络模式)   │  │     │  │ bridge.c (网络模式)    │  │
│  │  50Hz 推理 + 学习      │  │     │  │ 30fps 游戏逻辑+显示    │  │
│  │                        │  │     │  │                        │  │
│  │  输出: 控制信号(12B)   │──┼─────┼─►│  输入: 摇杆+按钮       │  │
│  │  输入: 姿态+帧(网络)   │◄─┼─────┼──│  输出: 姿态+帧(压缩)   │  │
│  └────────────────────────┘  │     │  └────────────────────────┘  │
│                              │     │                              │
│  Web 仪表板:                  │     │  Windows 桌面:               │
│  http://hostA:8765           │     │  SM64 游戏窗口原生显示       │
│                              │     │  http://hostA:8765 浏览器访问│
└──────────────────────────────┘     └──────────────────────────────┘
                              │
                              网络 (千兆局域网, RTT < 1-5ms)
```

---

## 2. 跨机部署的核心障碍

### 2.1 底层机制不可复用

| 组件 | 当前 mmap 实现 | 跨机问题 | 严重度 |
|------|--------------|---------|--------|
| **mmap 共享文件** | `os.open() → mmap.mmap()` (701KB) | ❌ mmap 不能跨网络 | 🔴 阻塞 |
| **Seqlock 无锁读写** | 内存栅栏 + 偶数/奇数序列号 | ❌ 网络无共享内存 | 🔴 阻塞 |
| **~8μs 延迟** | 直接内存访问 | ❌ 网络至少 1-10ms RTT | 🟡 中等 |
| **帧传输** | 零拷贝共享 294KB RGB | ❌ 需网络传输 ~70Mbps | 🟡 中等 |

### 2.2 核心需替换模块

| 文件 | 当前机制 | 跨机替换方案 | 修改量 |
|------|---------|------------|-------|
| `bridge.py` | `SharedBridge` (mmap) | **`NetworkedBridge`** (TCP) | ~200 行新增 |
| `sm64ex-fly64.patch` (C) | mmap 读取帧+写入姿态 | **socket send/recv** + JPEG 压缩 | ~100 行 |
| `main.py` | `SharedBridge(args.bridge)` | `NetworkedBridge(args.remote)` | ~30 行 |
| 启动脚本 | `setup_sm64.sh` 一键启动 | 两端独立启动 + 脚本 | ~50 行 |

### 2.3 脑模型内部零修改

以下模块**无需任何修改**（全部通过 bridge 接口隔离）：

- ✅ `model.py` — LIF 推理引擎、strike/crouch 解码池、CPG 门控
- ✅ `mushroom_body.py` — MBON 9 通道、三因子 Hebbian 学习
- ✅ `memory.py` — ReflexController、MotionStateDetector、空间记忆
- ✅ `central_complex.py` — CX 环形吸引子
- ✅ `motor_primitives.py` — CPG 运动原语
- ✅ `retina.py` — 视觉感知管道（帧格式不变）
- ✅ `gain_modulation.py` — 多巴胺增益
- ✅ `evolution_skill.py` — 自我进化闭环
- ✅ `telemetry.py` — 可观测性系统

---

## 3. 可行方案对比

### 3.1 方案总览

| # | 方案 | 可行性 | 工作量 | 延迟 | 复杂度 | 推荐场景 |
|---|------|--------|-------|------|--------|---------|
| **A** | **TCP 代理桥** | ✅ **可行** | **~2周** | **5-15ms** | **低** | **首选** 开发/演示/分离GPU负载 |
| B | ZeroMQ PUB/SUB | ✅ 可行 | ~3周 | 8-20ms | 中 | 多消费者场景(仪表板+脑模型+录像) |
| C | ROS2 桥接 | ⚠️ 重量级 | ~4周 | 10-25ms | 高 | 机器人系统集成(非SM64游戏场景) |
| D | 维持 mmap+WSL | ✅ 现成 | 0 | ~8μs | 无 | 当前推荐，无需任何改动 |

### 3.2 方案详解

#### 方案 A: TCP 代理桥（推荐）

**设计**: 在 `bridge.py` 中新增 `NetworkedBridge` 类，保持与 `SharedBridge` 相同的接口。底层用 TCP socket 替代 mmap。

**数据传输格式**（每 tick ~未压缩 524KB / 压缩 ~15KB）：

```
脑模型 → SM64 (每 tick 50Hz):
  [control_packet] = {stick_x(1B) + stick_y(1B) + buttons(1B) + seq(4B)} = 7 字节

SM64 → 脑模型 (每 tick 30fps):
  [pose_packet]    = {x(4B) + y(4B) + z(4B) + heading(4B) + game_frame(4B)} = 20 字节
  [frame_packet]   = MJPEG 压缩帧 (~15-20KB 或仅 16扇区流 ~1KB)
```

**协议流程**:

```
TCP 连接建立阶段:
  脑模型端 (Linux):  connect(hostB:8767)
  SM64 端 (Windows): listen(8767), accept()

每 tick 循环:
  ┌─────────────────────┐          ┌─────────────────────┐
  │  Fly64 脑模型 (Linux)│          │  sm64ex (Windows)   │
  │                     │          │                     │
  │  ① read_frame() ←──│◄─────────│  写: pose + 帧数据   │
  │                     │   TCP    │                     │
  │  ② 视觉管道处理      │          │  游戏逻辑 30fps      │
  │  ③ model.step()     │          │  渲染 OpenGL        │
  │  ④ write_control() ─│─────────►│  读: 摇杆+按钮       │
  │                     │    TCP   │                     │
  │  ⑤ 50Hz 下一 tick   │          │  ⑥ 30fps 下一 tick  │
  └─────────────────────┘          └─────────────────────┘
```

#### 方案 B: ZeroMQ PUB/SUB

```
SM64 侧 (Windows)                      脑模型侧 (Linux)
  ZMQ_PUB(zmqtcp://*:8767)              ZMQ_SUB(zmqtcp://hostA:8767)
    ├── topic "frame" → MJPEG 帧         ├── subscribe "frame"
    ├── topic "pose"  → 姿态数据          ├── subscribe "pose"
    └── ZMQ_SUB(zmqtcp://*:8768)          └── ZMQ_PUB(zmqtcp://*:8768)
          ← topic "control" ← 摇杆+按钮        → publish "control"
```

**优势**: 内置自动重连、多消费者（可同时接仪表板）、消息去重
**劣势**: 依赖 libzmq 编译（Windows 侧交叉编译或 vcpkg）

#### 方案 C: ROS2 桥接

```
SM64 侧 (Windows)                      脑模型侧 (Linux)
  ROS2 Node: /sm64_publisher            ROS2 Node: /fly64_brain
    ├── /sm64/image (sensor_msgs/Image)   ├── subscribe /sm64/image
    ├── /sm64/pose  (geometry_msgs/Pose)  ├── subscribe /sm64/pose
    └── /sm64/joy   (sensor_msgs/Joy)     └── publish /fly64/control_x
         ← subscribe
```

**优势**: 机器人标准、Rviz2 可视化、rosbag 录制
**劣势**: 搭建环境重、延迟高、不适合纯游戏场景

---

## 4. 推荐方案详细设计：TCP 代理桥

### 4.1 NetworkedBridge 接口设计

```python
# fly64/fly64/network_bridge.py — 新建模块 (约 200 行)

from __future__ import annotations
import socket
import struct
import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

# === 网络协议包格式 ===
# 控制包（脑模型→SM64，7字节）
CTRL_HEADER = struct.Struct("<bbBi")
#  x: int8, y: int8, buttons: uint8, seq: uint32

# 姿态包（SM64→脑模型，20字节）
POSE_HEADER = struct.Struct("<ffffI")
#  x: float32, y: float32, z: float32, heading: float32, game_frame: uint32

CTRL_PORT = 8767   # 控制端口（TCP）
FRAME_PORT = 8768  # 帧流端口（TCP，独立连接减少Head-of-Line阻塞）


class NetworkedBridge:
    """基于 TCP 的网络桥接，替代 SharedBridge (mmap)。
    
    与 SharedBridge 保持相同接口:
      read_frame() -> (frame_seq, pixels | None)
      write_control(x, y, jump, b, z)
      read_screen() -> bytes | None
      stale -> bool
      game_status() -> dict
    """
    
    def __init__(self, remote_addr: str = "192.168.1.100",
                 ctrl_port: int = CTRL_PORT,
                 frame_port: int = FRAME_PORT,
                 is_server: bool = False,
                 jpeg_quality: int = 80):
        self._connected = False
        self._stale = False
        self._last_pose = (0., 0., 0., 0., 0)
        self._last_frame: Optional[bytes] = None
        self._last_frame_seq = 0
        self._send_seq = 0
        self._jpeg_quality = jpeg_quality
        
        if is_server:
            # SM64 侧：等待脑模型连接
            self._setup_server(remote_addr, ctrl_port, frame_port)
        else:
            # 脑模型侧：主动连接 SM64
            self._connect_client(remote_addr, ctrl_port, frame_port)
    
    def _connect_client(self, host: str, ctrl_port: int, frame_port: int):
        """脑模型侧：建立双 TCP 连接"""
        self._ctrl_sock = socket.create_connection((host, ctrl_port), timeout=5.0)
        self._ctrl_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # 帧通道单独连接，避免大帧阻塞控制信号
        self._frame_sock = socket.create_connection((host, frame_port), timeout=5.0)
        self._frame_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._connected = True
        self._last_contact = time.monotonic()
    
    def read_frame(self) -> Tuple[int, bytes]:
        """从帧 Socket 读取最新帧 + 姿态（非阻塞）"""
        # 读取帧长度前缀 (4 字节小端 uint32)
        header = self._recv_exact(self._frame_sock, 4 + POSE_HEADER.size)
        if not header:
            return self._last_frame_seq, self._last_frame or b""
        frame_len = struct.unpack_from("<I", header, 0)[0]
        pose_data = header[4:4+POSE_HEADER.size]
        self._last_pose = POSE_HEADER.unpack(pose_data)
        # MJPEG 帧
        frame = self._recv_exact(self._frame_sock, frame_len)
        if frame:
            self._last_frame = frame
            self._last_frame_seq += 1
            self._last_contact = time.monotonic()
            self._stale = False
        # 解码 MJPEG → numpy (由 retina.py 处理)
        return self._last_frame_seq, frame or self._last_frame or b""
    
    def write_control(self, x: int, y: int, jump: bool,
                      b: bool = False, z: bool = False,
                      enabled: bool = True):
        """发送控制信号"""
        buttons = 0
        if jump: buttons |= 0x01
        if b:    buttons |= 0x02
        if z:    buttons |= 0x04
        packet = CTRL_HEADER.pack(
            max(-70, min(70, x)),
            max(-70, min(70, y)),
            buttons,
            self._send_seq
        )
        self._send_seq += 1
        try:
            self._ctrl_sock.sendall(packet)
        except (BrokenPipeError, ConnectionError):
            self._stale = True
    
    def read_screen(self) -> Optional[bytes]:
        """SM64 屏幕预览（复用帧通道，降采样 JPEG）"""
        return self._last_frame  # 同 read_frame 的 MJPEG 流
    
    @property
    def stale(self) -> bool:
        if self._last_contact and (time.monotonic() - self._last_contact) > 5.0:
            self._stale = True
        return self._stale
    
    def game_status(self) -> dict:
        x, y, z, heading, game_frame = self._last_pose
        return dict(
            seq=self._last_frame_seq,
            x=int(x), y=int(y), z=int(z), heading=heading,
            game_frame=int(game_frame),
            stale=self.stale
        )
    
    def close(self):
        self._ctrl_sock.close()
        self._frame_sock.close()
    
    def _recv_exact(self, sock, n: int) -> Optional[bytes]:
        """非阻塞精确接收 n 字节"""
        parts = []
        while n > 0:
            try:
                chunk = sock.recv(n)
            except (BlockingIOError, socket.timeout):
                continue
            if not chunk:
                return None
            parts.append(chunk)
            n -= len(chunk)
        return b"".join(parts)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *_):
        self.close()
```

### 4.2 main.py 适配

```python
# main.py — 新增 --remote-bridge 参数 (约 30 行)
import argparse

parser.add_argument("--remote-bridge", type=str, default=None,
                    help="连接远程 SM64 (IP:PORT), 替代本地 mmap 桥接")
parser.add_argument("--bridge-is-server", action="store_true",
                    help="本机是 SM64 端 (Windows 侧监听)")

# 实例化桥接:
if args.remote_bridge:
    from .network_bridge import NetworkedBridge
    host, port = args.remote_bridge.split(":")
    bridge = NetworkedBridge(
        remote_addr=host,
        ctrl_port=int(port),
        frame_port=int(port) + 1,
        is_server=args.bridge_is_server
    )
else:
    bridge = SharedBridge(args.bridge, create=True)
```

### 4.3 C 侧 sm64ex 补丁适配

```c
// sm64ex-fly64.patch — 新增网络读写路径 (约 100 行)

#include <winsock2.h>  // Windows 原生 socket
#include <jpeglib.h>   // libjpeg-turbo 帧压缩

static SOCKET ctrl_sock, frame_sock;

void fly64_network_init(const char *listen_addr, int ctrl_port) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
    // 监听控制端口
    ctrl_sock = socket(AF_INET, SOCK_STREAM, 0);
    bind(ctrl_sock, ...);
    listen(ctrl_sock, 1);
    // 等待脑模型连接
    accept(ctrl_sock, ...);
    // 帧端口也等待连接
    frame_sock = socket(...);
    bind(..., ctrl_port + 1);
    listen(frame_sock, 1);
    accept(frame_sock, ...);
}

void fly64_network_write_frame_and_pose(
    uint8_t *rgb, int w, int h,
    float x, float y, float z, float heading,
    int game_frame)
{
    // 1. JPEG 压缩帧
    uint8_t *jpeg_buf;
    unsigned long jpeg_size;
    jpeg_compress_rgb(rgb, w, h, 80, &jpeg_buf, &jpeg_size);
    
    // 2. 发送帧
    uint32_t frame_len = jpeg_size;
    send(frame_sock, (char*)&frame_len, 4, 0);
    send(frame_sock, (char*)&pose_data, POSE_HEADER_SIZE, 0);
    send(frame_sock, (char*)jpeg_buf, jpeg_size, 0);
    
    free(jpeg_buf);
    
    // 3. 读取控制
    recv(ctrl_sock, (char*)&ctrl_packet, CTRL_PACKET_SIZE, 0);
    apply_control(ctrl_packet.x, ctrl_packet.y, ctrl_packet.buttons);
}
```

---

## 5. 帧数据传输方案

脑模型视觉管道需要 `256×384×3` RGB 帧（294KB/帧，~35MB/s @30fps）。跨网络必须压缩：

### 5.1 方案对比

| 方案 | 每帧大小 | 带宽(30fps) | 视觉管道影响 | 编码开销 | 推荐度 |
|------|---------|-----------|------------|---------|-------|
| **A: 16扇区光流特征** | **~1KB** | **~0.24 Mbps** | 脑模型视觉管道完全无需帧本身，只需 **16扇区光流特征** | 0ms (SM64 侧已计算) | ⭐ **首选** |
| **B: MJPEG 压缩** | ~15-20KB | ~3.5-4.7 Mbps | retina.py 解码 MJPEG→numpy 即可 | ~1ms | ⭐ 推荐 |
| **C: 原始 RGB** | 294KB | ~70 Mbps | 零修改 | 0ms | ❌ 带宽过高 |
| **D: WebP** | ~10KB | ~2.3 Mbps | 需解码库 | ~3ms | ✅ 备选 |

### 5.2 推荐：16扇区光流特征方案

**核心洞察**: 脑模型的视觉管道不直接使用完整帧，而是使用 `retina.py` 中从帧提取的**光流特征**（16 扇区活跃度/EMD/HRC/τ 估计等）。如果 SM64 侧直接计算这些特征并传给脑模型，带宽将从 35MB/s 降到 ~1KB/s。

```
SM64 侧（C, 每帧 30fps）:                      脑模型侧（Python, 50Hz）:
  ┌─────────────────────┐                       ┌──────────────────────┐
  │ 游戏渲染 → 帧缓存     │                      │ 接收光流特征包        │
  │       │              │  UDP/TCP ~1KB       │     ↓               │
  │  retina_feature.c   │─────────────────────►│  model.encode_retina │
  │   ├── ON/OFF 帧差   │   16 扇区 × 8 字段    │     ↓               │
  │   ├── EMD 4方向      │   光流特征            │  场景签名 128维       │
  │   ├── 16扇区活跃度   │                      │     ↓               │
  │   ├── τ 估计         │                      │  LIF 推理 50Hz       │
  │   └── 场景签名 128D  │                      │     ↓               │
  └─────────────────────┘                      │  MBON 学习           │
                                               └──────────────────────┘
```

**带宽需求**: 16 扇区 × 8 字段 × 4 字节 × 30fps = **15.36 KB/s** — 即使走 WiFi 也绰绰有余。

**缺点**: retina.py 中的视觉处理会少一个原始帧数据源（用于 LLM 截图咨询）。但 LLM 截图可以在 SM64 侧独立通过 http 提供。

### 5.3 双模式自适应

```python
class NetworkedBridge:
    """支持双模式帧传输"""
    MODE_FEATURE = "feature"  # 仅光流特征 (~1KB/frame)
    MODE_JPEG = "jpeg"        # MJPEG 帧 (~15KB/frame)
    
    def set_frame_mode(self, mode: str):
        """动态切换帧传输模式"""
        self._frame_mode = mode
```

- **默认模式**: `MODE_FEATURE`（光流特征，最低带宽）
- **LLM 咨询时切换**: `MODE_JPEG`（截图用于多模态分析）
- **降级**: 网络延迟 >200ms 时自动切到 `MODE_FEATURE`

---

## 6. 具体实践计划

### 6.1 总体时间线：2 周

```
Week 1                  Week 2
├── Day 1-2: 原型构建   ├── Day 8-9: 双机联调
│   NetworkedBridge.py  │   Linux ↔ Windows 联机测试
│   C 侧 socket 移植    │   延迟/带宽/帧率验证
├── Day 3-4: 帧压缩    ├── Day 10-11: 鲁棒性
│   libjpeg 集成        │   断线重连、降级策略
│   16扇区特征提取      │   抖动缓冲 Jitter Buffer
├── Day 5-6: 集成测试  ├── Day 12-13: Web 仪表板兼容
│   main.py 参数适配    │   screen.json 远程访问
│   单机 TCP loopback   │   LLM 截图隧道
├── Day 7: 缓冲         ├── Day 14: 验收
│   Jitter Buffer (2-5帧)│   全场景回归测试
│   帧率自适应降级       │   文档 + 启动脚本
```

### 6.2 详细任务分解

#### Phase 0: 环境准备（第 1 天）

| 任务 | 责任人 | 产出 | 工时 |
|------|-------|------|------|
| Linux 主机确认脑模型运行环境 | 部署工程师 | Python 3.11 + numpy/scipy 已验证 | 0.5d |
| Windows 主机确认 sm64ex 编译 | 部署工程师 | sm64ex 编译通过，原生运行正常 | 0.5d |
| 网络测试（ping + iperf） | 部署工程师 | 延迟 <5ms, 带宽 >100Mbps | 0.5d |
| 创建 `network_bridge.py` 骨架 | 开发 | 接口定义与 SharedBridge 对齐 | 0.5d |

#### Phase 1: 核心通信（第 2-3 天）

| 任务 | 文件 | 工时 |
|------|------|------|
| `NetworkedBridge` 类实现（TCP 连接管理 + 控制包） | `fly64/network_bridge.py` | 1d |
| SM64 C 侧 socket 移植（Windows winsock2 初始化 + 双连接 accept） | `patches/sm64ex-fly64.patch` | 1d |
| 单机 TCP loopback 测试（Windows 本地 127.0.0.1） | 测试 | 0.5d |

**验收标准**: `write_control(70, 0, True)` → SM64 侧读取到 stick_x=70, jump=True（<20ms 延迟）

#### Phase 2: 帧传输（第 3-5 天）

| 任务 | 文件 | 工时 |
|------|------|------|
| SM64 侧 MJPEG 压缩（libjpeg-turbo 集成） | `patches/sm64ex-fly64.patch` | 1d |
| Python 侧 MJPEG 解码（OpenCV `imdecode` / Pillow） | `retina.py` 适配层 | 0.5d |
| 16扇区光流特征提取（C 侧 retina 特征管道实现） | `retina_feature.c` | 1.5d |
| 双模式帧传输（特征/MJPEG 自适应切换） | `network_bridge.py` | 0.5d |

**验收标准**:
- 特征模式: 脑模型场景识别准确率 ≥ 当前 mmap 模式的 95%
- JPEG 模式: 截图清晰度满足 LLM 视觉分析（Q≥80）
- 带宽: 特征模式 <0.5Mbps, JPEG 模式 <10Mbps

#### Phase 3: 集成与鲁棒性（第 5-8 天）

| 任务 | 文件 | 工时 |
|------|------|------|
| `main.py` 添加 `--remote-bridge` / `--bridge-is-server` 参数 | `main.py` | 0.5d |
| 抖动缓冲 Jitter Buffer（2-5帧，容忍网络抖动） | `network_bridge.py` | 0.5d |
| 帧率自适应降级（网络差时30→15fps） | `network_bridge.py` | 0.5d |
| 断线重连（自动重连 + 状态恢复） | `network_bridge.py` | 0.5d |
| 启动脚本（Linux -> Windows 双端） | `scripts/remote_bridge*.sh` | 0.5d |

**验收标准**:
- 脑模型在 Linux 上正常 50Hz 运行
- SM64 在 Windows 上正常 30fps 显示
- 断线 10s 内自动重连恢复
- 网络抖动 ±50ms 内帧率稳定

#### Phase 4: Web 仪表板兼容（第 9-10 天）

| 任务 | 工时 | 说明 |
|------|------|------|
| `screen.json` 远程访问（通过 HTTP 代理转发 MJPEG 帧） | 1d | Windows 浏览器访问 Linux 端 `/screen.json` 仍能显示 SM64 画面 |
| LLM 截图隧道（LLM 咨询时请求 SM64 侧「当前帧」JPEG） | 0.5d | 点击截图时从 SM64 侧拉取而非 mmap |
| `/bridge-status.json` 新增网络延迟/帧率指标 | 0.5d | 仪表板实时监控网络 QoS |

**验收标准**: Windows 浏览器打开 `http://hostA:8765` → 仪表板完整可用、screen 预览 <500ms 延迟、LLM 咨询截图正常

#### Phase 5: 回归测试 + 验收（第 11-14 天）

| 测试项 | 方法 | 标准 |
|-------|------|------|
| 功能回归 | 运行 10 轮 EVO 闭环（单机 TCP loopback） | 与 mmap 基线行为一致 |
| 延迟预算 | wireshark + timestamps | 端到端延迟 <50ms（P95） |
| 带宽测试 | iperf + 实时监控 | 特征模式 <0.5Mbps, JPEG <10Mbps |
| 断线测试 | 手动断开网线 + 恢复 | 10s 内自动重连 |
| 长稳测试 | 12 小时不间断运行 | 零崩溃，帧率波动 <5% |
| LLM 截图 | 检查 coach_frames 目录 | 截图可读，文字清晰 |

### 6.3 硬件与网络要求

| 要求 | 最低 | 推荐 |
|------|------|------|
| **Linux 主机 CPU** | 4核 @2.5GHz | 8核 @3.0GHz（脑模型实时推理） |
| **Windows 主机 GPU** | 集成显卡 | NVIDIA GTX 1060+（SM64 GL 渲染 + 可选 GPU 帧编码） |
| **网络** | 千兆局域网 | 同交换机千兆（RTT <1ms） |
| **RAM (Linux)** | 8GB | 16GB（脑模型 + numpy 大型矩阵） |
| **RAM (Windows)** | 4GB | 8GB（SM64 + WSL） |

### 6.4 交付物清单

| 交付物 | 路径 | 说明 |
|--------|------|------|
| `fly64/network_bridge.py` | 新建 | NetworkedBridge 类（TCP 代理桥实现） |
| `patches/sm64ex-fly64.patch` 更新 | 更新 | 新增 C 侧网络路径 (winsock2 + libjpeg) |
| `fly64/main.py` 更新 | 更新 | `--remote-bridge` / `--bridge-is-server` 参数 |
| `scripts/remote_bridge_windows.ps1` | 新建 | Windows 侧启动脚本（编译 + 监听 + 启动游戏） |
| `scripts/remote_bridge_linux.sh` | 新建 | Linux 侧启动脚本（连接 + 启动脑模型） |
| 测试文档 | `docs/deployment/remote-bridge-test-report.md` | 验收测试报告 |

---

## 7. 风险与权衡

### 7.1 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 网络延迟导致推理时序偏移 | 中 | 高 | Jitter Buffer + 帧率自适应降级 |
| libjpeg 编译在 Windows 交叉编译困难 | 中 | 中 | 备选方案：直接 fip-feature 不传帧 |
| 断线时脑模型无输入帧 | 高 | 中 | model.py 已内置冻结检测 + 降级（stale→restlessness→escape） |
| WSL 方案与双机方案冲突 | 低 | 低 | 两套 Bridge 共存，通过启动参数选择 |
| 帧率不匹配（脑50Hz / SM64 30fps） | 无 | 无 | 现有架构已处理，帧采样缓存机制不变 |

### 7.2 与单机 WSL 方案的比较

| 维度 | 单机 WSL (当前) | 双机 TCP 桥 (新) | 差异 |
|------|----------------|-----------------|------|
| **延迟** | ~8μs | 5-15ms (局域网) | TCP 方案高 3 个数量级，但仍在 50Hz 预算内 |
| **带宽** | 0 (共享内存) | 0.5-10Mbps | 需要网络 |
| **硬件隔离** | ❌ 共享 CPU/GPU | ✅ **独立** | GPU 负载分离、脑模型独占 CPU |
| **远程控制** | ❌ 同一台 | ✅ **远程** | Linux 服务器 + Windows 工作站 |
| **复杂度** | 低 | 中 | 需要网络配置 |
| **维护成本** | 低 | 中 | 双机运维 |

### 7.3 决策树

```
需要分离脑模型和游戏执行?
├── 否 → 维持当前 WSL+WSLg 方案（零改动，推荐）
└── 是 → 需要跨机器?
    ├── 否 (同机但分离 GPU 负载)
    │   └── 使用 WSL2 GPU 分区 或 单机 TCP loopback → 无需双机
    └── 是 (不同物理机)
        ├── 同局域网 (<5ms RTT)
        │   └── 选用 TCP 代理桥 (方案 A, 2 周)
        └── 广域网/互联网 (>20ms RTT)
            └── ❌ 不推荐 — 延迟远超脑模型 50Hz 预算
```

---

## 附录

### A. 文件变更清单

| 操作 | 文件 | 行数估计 | 影响 |
|------|------|--------|------|
| **新建** | `fly64/network_bridge.py` | ~200 | 核心网络桥接实现 |
| **更新** | `patches/sm64ex-fly64.patch` | ~+100 | C 侧 socket+JPEG 集成 |
| **更新** | `fly64/main.py` | ~+30 | `--remote-bridge` 参数 |
| **新建** | `scripts/remote_bridge_linux.sh` | ~30 | Linux 端启动脚本 |
| **新建** | `scripts/remote_bridge_windows.ps1` | ~30 | Windows 端启动脚本 |

### B. 性能预算表

```
脑模型 50Hz tick 预算 (20ms):
  ├── 网络接收姿态+帧:  2-5ms  (TCP 同局域网)
  ├── retina.py 视觉管道: 3-5ms  (16扇区光流/JPEG解码)
  ├── model.step() LIF:  5-8ms  (CSC 151.9M边稀疏乘法)
  ├── 蘑菇体学习:         1-2ms  (三因子Hebbian)
  └── 网络发送控制:       1ms    (7 字节 UDP/TCP)
  ─────────────────────────────────
  合计: 12-21ms (P95 < 20ms ✓)
```

### C. 模拟器替代方案（不依赖 SM64 实机）

如果只是为了调试跨机通信，可以先用以下替代方案验证：

```
脑模型侧 (Linux)                Windows 侧 (Python 模拟器)
  NetworkedBridge ←──TCP──→   TestHarness (fake sm64)
                                 ├── 每帧返回模拟 pose
                                 ├── 接收控制再打印
                                 └── 发送随机帧 (或纯色)
```

验证通过后再接入真实 sm64ex，隔离网络问题与游戏问题。

---

> **文档版本**: v1.0 | **分析日期**: 2026-09-15  
> **脑模型版本**: Fly64 v2.13.3  
> **数据源**: `fly64/fly64/bridge.py` (200行) · `fly64/README.md` · `fly64/fly64/main.py` · `fly64/docs/wsl-setup-guide.md`  
> **保存位置**: `docs/analysis/cross_machine_deployment_analysis.md`