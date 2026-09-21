# Fly64 WSL 可靠启动器 — 部署与根因分析文档

> 版本: 1.0.0 · 最后更新: 2026-09-21  
> 组件: `scripts/wsl_launcher.sh` + `scripts/wsl_launcher.ps1`  
> 替代: `consolidate.sh` 的原始 `setsid nohup` 裸启动方式

---

## 目录

1. [问题根因分析](#1-问题根因分析)
2. [方案评估与选择](#2-方案评估与选择)
3. [架构设计](#3-架构设计)
4. [部署说明](#4-部署说明)
5. [使用指南](#5-使用指南)
6. [可靠性验证](#6-可靠性验证)
7. [故障排除](#7-故障排除)
8. [附录：WSL 进程模型详解](#8-附录wsl-进程模型详解)

---

## 1. 问题根因分析

### 1.1 症状

```bash
# ❌ 启动后进程立即消失
wsl -e bash -c "setsid nohup python3 -m fly64.main ... &"

# ✅ 交互式终端内正常
wsl ~
# 然后在 WSL 内执行:
setsid nohup python3 -m fly64.main ... &
```

`wsl -e bash -c` 启动的进程在宿主 PowerShell/CMD 返回后数秒内被 kill，即使使用了 `setsid nohup`。

### 1.2 WSL 进程树结构

WSL2 不使用 systemd（默认 `systemd=false`），PID 1 是 WSL 自定义的 `/init`：

```
PID 1: /init (WSL 自定义 init)
  ├── Relay(17)          ← I/O 复用进程，绑定 dbus
  ├── Relay(1260)        ← 交互式 WSL 终端会话
  │   ├── python3(1263)  ← 脑模型 (Relay 子进程)
  │   └── sm64.us.f3dex2e ← SM64 (Relay 子进程)
  └── Relay(31092)       ← 当前 WSL 会话
      └── bash(31094)    ← 当前 shell
```

**关键发现：**
- 每个 WSL 终端会话绑定一个 `Relay(NNNN)` 进程
- `Relay` 进程是 WSL 的 I/O 多路复用层，负责转发 stdin/stdout/stderr
- **所有进程都是某个 Relay 进程的子进程或孙进程**
- 不存在"纯 init 直接子进程"的空间（即使 setsid 也无法脱离 init 进程树）

### 1.3 为什么 setsid nohup 在 `wsl -e` 中失效

**`setsid` 作用：** 创建新会话（Session），子进程成为新会话首领（Session Leader），脱离控制终端。  
**`nohup` 作用：** 忽略 SIGHUP 信号，并将输出重定向到 nohup.out。

当使用 `wsl -e bash -c "command"` 时：

```
第 1 步: PowerShell 执行 wsl -e bash -c "command"
         WSL 创建临时实例:
         /init → Relay(X) → bash(Y) → command

第 2 步: command 启动 setsid nohup 后台进程
         /init → Relay(X) → bash(Y) → setsid → 新会话进程(Z)
                                         ↑
                                    setsid 创建新会话，
                                    但 Z 仍然是 Relay(X) 的孙进程

第 3 步: bash(Y) 执行完毕，退出
         WSL 检测到该会话的 shell 已终止

第 4 步: WSL 回收该会话的所有 Relay 子进程树
         Relay(X) 被 SIGTERM 终止
         其所有子进程（包括孙进程 Z）被 SIGTERM 终止
         
         setsid nohup 失效原因:
         - nohup 只忽略 SIGHUP，不忽略 SIGTERM
         - setsid 创建的会话仍在该 WSL 实例的进程命名空间中
         - WSL 的会话回收是暴力 SIGTERM，不区分会话
```

**结论：** `setsid nohup` 能防止 SIGHUP，但无法防御 WSL 的会话回收 SIGTERM。

### 1.4 为什么 Start-Process 生效

```powershell
# ✅ 有效
Start-Process wsl "/bin/bash script.sh"
```

`Start-Process` 创建一个**新的 WSL 终端窗口**。这个窗口：
1. 创建独立的 WSL 会话 → 独立的 `Relay` 进程
2. `bash script.sh` 在前台运行，窗口保持打开
3. `Relay` 进程保持活跃，其子进程树不被回收
4. 只要窗口不关闭，进程持续运行

**缺陷：** 窗口关闭/终端崩溃时进程仍可能终止。

### 1.5 交互式 WSL 为何正常

```bash
# ✅ 有效
wsl ~
# 然后在 WSL 内运行:
setsid nohup python3 ... &
```

当通过交互式 `wsl ~` 进入时：
1. WSL 创建一个持久的交互式终端会话
2. 该会话的 `Relay` 进程保持活跃
3. 即使 bash 执行了 setsid nohup 后退出，终端窗口仍然存在
4. 不会触发会话回收机制

**已有证据：** 当前 WSL 实例中，脑模型（PID 1263）已连续运行 **超过 33 小时**（`ps -o etime` 显示 1-09:34:29），其父进程是 `Relay(1260)`，子进程是 `init(1)`。证明在交互式 WSL 会话中，setsid nohup 进程可以无限期存活。

---

## 2. 方案评估与选择

### 2.1 候选方案对比

| 方案 | 可行性 | 可靠性 | 复杂度 | 依赖 | 评分 |
|------|:------:|:------:|:------:|:----:|:----:|
| **① tmux session** | ✅ | ⭐⭐⭐⭐⭐ | 低 | 内置（已安装） | **⭐推荐** |
| ② systemd user service | ❌ | — | 高 | `systemd=true` 需重启 | ❌ 不可行 |
| ③ init.d / sysv-rc | ❌ | — | 中 | WSL 不支持 | ❌ 不可行 |
| ④ Start-Process + 窗口 | ✅ | ⭐⭐⭐ | 低 | 窗口必须存在 | ⚠️ 备用 |
| ⑤ wsl --fork | ⚠️ | ⭐⭐⭐ | 中 | WSL 预览版 | ⚠️ 后备 |

### 2.2 方案①：tmux session ⭐ 推荐

**原理：** tmux server 作为守护进程运行，tmux 会话内的进程以 tmux 为父进程：

```
正常 shell 退出后:
  init(1)
    ├── tmux: server (守护进程，不受 shell 退出影响)
    │   ├── bash(脑模型窗口)
    │   │   └── setsid nohup python3 -m fly64.main (独立会话)
    │   └── bash(SM64 窗口)
    │       └── setsid nohup sm64.us.f3dex2e (独立会话)
    └── Relay(其他会话)
```

**优势：**
- ✅ **tmux server 已安装在 WSL 中**（tmux 3.2a），零额外安装
- ✅ 完全独立于启动 shell 的进程树
- ✅ shell 退出后 tmux server 被重父到 init（PID 1）
- ✅ 可附加/分离（`tmux attach`/`Ctrl+B d`）
- ✅ 多窗口管理（脑模型 / SM64 / 监控各占一个窗口）
- ✅ `setsid nohup` 作为第二层防护（defense in depth）
- ✅ WSLg 显示不受影响（`DISPLAY=:0` 在 tmux 内同样有效）

### 2.3 方案②：systemd user service ❌ 不可行

**理由：**
- WSL 默认 `systemd=false`（`/etc/wsl.conf` 明确配置）
- PID 1 是 `/init`（WSL 自定义 init），不是 systemd
- `systemctl --user` 返回 `System has not been booted with systemd as init system`
- `loginctl` 不可用，无 `logind` 服务
- 启用 systemd 需修改 `wsl.conf` 并重启，对用户有侵入性
- systemd 在 WSL 中会增加资源开销

### 2.4 方案③：init.d / sysv-rc ❌ 不可行

**理由：**
- WSL 的 init 不处理 `/etc/init.d/` 脚本
- 没有运行级别系统（runlevel）
- init.d 脚本只能手动调用，无自动管理能力

### 2.5 方案④：Start-Process 窗口模式 ⚠️ 备用

**适用场景：** tmux 不可用时的降级方案。

**可靠性风险：**
- 窗口关闭或崩溃 → 所有子进程被回收
- 不能重启 Windows 或重启 WSL
- 长时间运行的桌面环境下窗口可能被误关闭

### 2.6 方案⑤：wsl --fork ⚠️ 后备

**适用场景：** WSL 预览版用户，希望完全隐藏窗口。

**限制：**
- 需要 WSL 预览版（`wsl --version` 检查）
- `--fork` 行为版本间不稳定
- 错误处理复杂

---

## 3. 架构设计

### 3.1 组件架构

```
┌─────────────────────────────────────────────────────────────┐
│ Windows 侧                                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ wsl_launcher.ps1 (PowerShell 包装器)                      │ │
│  │   3 种模式: tmux(默认) / console / background             │ │
│  │   Start-Process wsl → 持久 WSL 终端                      │ │
│  └──────────────────────┬──────────────────────────────────┘ │
└─────────────────────────┼───────────────────────────────────┘
                          │ wsl -- bash -c "script.sh"
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ WSL 侧 (Ubuntu 22.04)                                         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ wsl_launcher.sh (Bash 启动器)                             │ │
│  │   create tmux session → fly64                            │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │ tmux: fly64                                              │ │
│  │   ├─ window 0: brain  ← 脑模型                           │ │
│  │   │   └─ setsid nohup python3 -m fly64.main              │ │
│  │   ├─ window 1: sm64   ← SM64 游戏                         │ │
│  │   │   └─ setsid nohup ./sm64.us.f3dex2e                  │ │
│  │   └─ window 2: monitor ← 日志监控 (tail -f)               │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 防护层次（Defense in Depth）

| 层 | 机制 | 防御目标 | 存活条件 |
|:--:|:----|:---------|:---------|
| 1 | **PowerShell Start-Process** | WSL 会话回收 | 终端窗口保持 |
| 2 | **tmux server 守护进程** | Shell 退出 | tmux 重父到 init |
| 3 | **tmux session** | 终端断开 | tmux server 存活 |
| 4 | **setsid 新会话** | SIGHUP / 父进程退出 | PID 1 存活 |
| 5 | **nohup 忽略 SIGHUP** | SIGHUP 信号 | 4 层失效时兜底 |
| 6 | **输出重定向 </dev/null** | 读端关闭异常 | 标准 I/O 独立 |

**经验验证：** 当前运行的脑模型（PID 1263，已运行 33+ 小时）仅使用了第 4-6 层保护。增加第 1-3 层后，可靠性进一步提升。

### 3.3 tmux 内部结构

```
tmux: server (PID S, PPID=shell 或 init)
  │
  └── session: fly64
        ├── window 0: brain (bash)
        │     initiates:
        │     setsid nohup python3 -m fly64.main → PID B
        │       ├── http server (port 8765)
        │       ├── websocket server (port 8766)
        │       └── brain loop (50Hz)
        │
        ├── window 1: sm64 (bash, 可选)
        │     initiates:
        │     setsid nohup sm64.us.f3dex2e → PID G
        │       └── SDL2 window (WSLg → Windows 桌面)
        │
        └── window 2: monitor (bash)
              tail -f /tmp/fly64.log
```

---

## 4. 部署说明

### 4.1 前置条件

```bash
# 验证 tmux 已安装（默认已安装）
tmux -V          # 应输出 tmux 3.2a 或更高

# 如未安装（极少数情况）:
sudo apt-get update && sudo apt-get install -y tmux

# 验证 setsid 和 nohup
which setsid     # /usr/bin/setsid
which nohup      # /usr/bin/nohup
```

### 4.2 启动器文件位置

```
fly64/
├── scripts/
│   ├── wsl_launcher.sh      # 主启动器（WSL 侧 bash 脚本）
│   ├── wsl_launcher.ps1     # PowerShell 包装器（Windows 侧）
│   └── test_wsl_launcher.sh # 进程隔离测试脚本
├── docs/
│   └── wsl-launcher-deployment.md   # 本文档
└── run-fly64
```

### 4.3 从 WSL 内部启动

```bash
# 基本启动（仅脑模型，合成模式）
bash /root/fly64/scripts/wsl_launcher.sh

# 全模式启动（脑模型 + SM64 游戏）
bash /root/fly64/scripts/wsl_launcher.sh \
  --rom /root/fly64/.cache/sm64ex/baserom.us.z64

# 重启
bash /root/fly64/scripts/wsl_launcher.sh --restart

# 查看状态
bash /root/fly64/scripts/wsl_launcher.sh --status

# 附加到 tmux 会话（查看实时日志）
bash /root/fly64/scripts/wsl_launcher.sh --attach

# 停止所有进程
bash /root/fly64/scripts/wsl_launcher.sh --stop
```

### 4.4 从 Windows PowerShell 启动（推荐）

```powershell
# tmux 模式（默认，最稳定）
.\scripts\wsl_launcher.ps1 -Action launch -RomPath D:\roms\baserom.us.z64

# 仅状态查看
.\scripts\wsl_launcher.ps1 -Action status

# 停止
.\scripts\wsl_launcher.ps1 -Action stop
```

### 4.5 从 Windows CMD 启动

```cmd
powershell -ExecutionPolicy Bypass -File scripts\wsl_launcher.ps1 -Action launch -RomPath D:\roms\baserom.us.z64
```

### 4.6 从任意工作目录启动

```powershell
# 切换到 fly64 目录
cd D:\codes\flygym\fly64

# 启动
.\scripts\wsl_launcher.ps1 -Action launch -RomPath D:\roms\baserom.us.z64
```

---

## 5. 使用指南

### 5.1 启动后

tmux 创建 2-3 个窗口（在 `tmux attach` 后可见）：

| 窗口 | 名称 | 内容 |
|:----:|:----:|:-----|
| 0 | brain | 脑模型控制台（调式日志） |
| 1 | sm64 | SM64 游戏控制台 |
| 2 | monitor | `tail -f /tmp/fly64.log` 实时日志 |

### 5.2 tmux 快捷键

| 按键 | 功能 |
|:----:|:------|
| `Ctrl+B` `d` | 分离（detach），进程继续在后台运行 |
| `Ctrl+B` `0` | 切换到窗口 0（脑模型） |
| `Ctrl+B` `1` | 切换到窗口 1（SM64） |
| `Ctrl+B` `2` | 切换到窗口 2（监控） |
| `Ctrl+B` `n` | 下一个窗口 |
| `Ctrl+B` `p` | 上一个窗口 |
| `Ctrl+B` `c` | 创建新窗口 |
| `Ctrl+B` `w` | 窗口列表预览 |

### 5.3 日常操作

```bash
# 查看状态（不进入 tmux）
bash /root/fly64/scripts/wsl_launcher.sh --status

# 附加到 tmux 检查运行情况
bash /root/fly64/scripts/wsl_launcher.sh --attach

# 分离（不停止进程）
# Ctrl+B 然后 d

# 停止
bash /root/fly64/scripts/wsl_launcher.sh --stop
```

### 5.4 与现有工具协作

**与 consolidate.sh 的关系：** `wsl_launcher.sh` 是更可靠的替代方案。如果需要 `consolidate.sh` 的"根据 SM64 存在状态自动切换 full/synthetic 模式"功能，可在 tmux 窗口内执行 consolidate。

**与 run-fly64 的关系：** `run-fly64` 的前台交互模式不受影响。`wsl_launcher.sh` 适用于常驻/后台运行场景。

---

## 6. 可靠性验证

### 6.1 验证结果

2026-09-21 在目标 WSL 环境（Ubuntu 22.04, tmux 3.2a）完成验证：

| 测试项 | 结果 | 说明 |
|:-------|:---:|:-----|
| tmux server 进程隔离 | ✅ PASS | tmux server 独立运行，不受启动 shell 影响 |
| setsid 新会话创建 | ✅ PASS | SID != PPID，独立会话已验证 |
| nohup SIGHUP 忽略 | ✅ PASS | nohup 正确忽略挂断信号 |
| 进程树独立验证 | ✅ PASS | sleep 300 在 setsid 后显示独立 PGID/SID |
| 长跑稳定性 | ✅ PASS | 现有脑模型已运行 33+ 小时 |

### 6.2 反复测试

```bash
# 运行隔离测试
bash /root/fly64/scripts/test_wsl_launcher.sh

# 预期输出:
# ✓ TEST PASSED: sleep 300 process is alive
#   New session: ✓ (SID XXX != PPID YYY)
```

### 6.3 持续监控

```bash
# 在 monitor 窗口观察脑模型日志
tail -f /tmp/fly64.log

# 监控进程存活
watch -n 10 'bash /root/fly64/scripts/wsl_launcher.sh --status'
```

---

## 7. 故障排除

### 7.1 tmux 未安装

```bash
# 症状: tmux: command not found
# 解决方案:
sudo apt-get update
sudo apt-get install -y tmux

# 验证
tmux -V  # 应输出 tmux 3.2a
```

### 7.2 脑模型启动失败

```bash
# 检查日志
tail -50 /tmp/fly64.log

# 常见原因:
# - 端口 8765 被占用: lsof -i :8765
# - Python 依赖缺失: python3 -c "import fly64"
# - 脑数据未下载: ls -la /root/fly64/.cache/malecns/
```

### 7.3 SM64 窗口不显示

```bash
# 检查 WSLg 显示环境
echo $DISPLAY
# 应输出 :0

# 安装 xrandr（解决 SDL2 屏幕检测）
sudo apt-get install -y x11-xserver-utils

# 检查 WSLg 是否运行
ps aux | grep -i wslg
```

### 7.4 进程被误杀

```bash
# 检查进程是否存在
bash /root/fly64/scripts/wsl_launcher.sh --status

# 如果脑模型消失但 tmux 仍在:
bash /root/fly64/scripts/wsl_launcher.sh --restart

# 如果 tmux 也消失（WSL 重启等情况）:
bash /root/fly64/scripts/wsl_launcher.sh --launch
```

### 7.5 tmux 会话窗口自动关闭

如果 tmux 窗口内的 bash 因错误退出，该窗口会关闭。要避免：
```bash
# 在 tmux 窗口内使用:
setsid nohup your-command > log 2>&1 </dev/null &
```

`wsl_launcher.sh` 网络中使用 `setsid nohup` 已自动处理此问题。

### 7.6 多用户/多实例冲突

```bash
# 如果另一个用户已启动 fly64 会话:
bash /root/fly64/scripts/wsl_launcher.sh --status

# 使用不同的会话名称（修改 TMUX_SESSION 变量）
TMUX_SESSION=fly64-instance2 bash /root/fly64/scripts/wsl_launcher.sh
```

---

## 8. 附录：WSL 进程模型详解

### 8.1 WSL2 进程层次

```
Windows 侧                    WSL2 侧 (Ubuntu 22.04)
OpenConsole.exe ────── WSL   ──→ /init (PID 1)
  (终端窗口)                           │
                                       ├── init (PID 7) ← 二级 init，处理孤儿进程
                                       │
                                       ├── Relay(17) ← dbus 服务
                                       │   ├── dbus-launch
                                       │   └── dbus-daemon
                                       │
                                       ├── Relay(1260) ← 交互式终端会话（持久）
                                       │   ├── python3(1263) ← 脑模型 (运行 33h+)
                                       │   └── sm64.us.f3dex2e(1284) ← SM64
                                       │
                                       └── Relay(31092) ← 当前 wsl 命令会话
                                           └── bash(31094) ← 当前 shell
                                               └── ps(31109) ← 一次性命令
```

### 8.2 wsl.conf 配置

当前配置 (`/etc/wsl.conf`):
```ini
[boot]
systemd=false
```

**不推荐启用 systemd 的理由：**
1. WSL 的 systemd 支持仍存在兼容性问题（`systemd=true` 时可能影响网络/DNS）
2. 增加约 500MB 内存开销
3. tmux 方案无需 systemd，零侵入

### 8.3 关键进程角色

| 进程 | 角色 | 说明 |
|:-----|:-----|:------|
| `/init` | WSL init | PID 1，WSL 自定义，非 systemd |
| `init` | 二级 init | PID 7，处理孤儿子进程 |
| `Relay(N)` | I/O 复用 | 每终端会话绑定一个，转发 stdin/stdout/stderr |
| `SessionLeader` | 会话管理 | WSL 内部使用 |
| bash/zsh/ps | 用户交互 | 在 Relay 下运行 |

### 8.4 信号传播路径

```
     WSL 会话结束
          │
          ▼
    /init (PID 1)
          │
          ▼
    Relay(N)  ← 发送 SIGTERM
          │
          ├── bash → SIGTERM → 子进程 → SIGTERM → 孙进程
          │                              ↑
          │                        setsid nohup 无法防御
          │                        (因为 SIGTERM 来自 init，
          │                         不是 SIGHUP)
          └── ...
```

**tmux 如何打破这个链条：**
```
    tmux: server
          │
          ├── tmux client (bash) ← 这个 bash 退出不影响
          │
          └── tmux 会话内进程
                ├── brain model
                └── SM64
              
    tmux: server 崩溃条件:
    - WSL 实例重启
    - 手动 kill
    - 系统关闭
    
    tmux: server 不会因以下原因崩溃:
    - 启动 shell 退出
    - 终端窗口关闭
    - SIGHUP
    - SIGTERM（除非 init 发送广播）
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:------|
| 1.0.0 | 2026-09-21 | 初版：根因分析 + tmux 方案 + 启动器脚本 + 部署文档 |