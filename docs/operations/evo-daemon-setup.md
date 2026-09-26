# EVO 守护自愈接入指南

> **文档**: `docs/operations/evo-daemon-setup.md`
> **适用**: WSL (Ubuntu 22.04) 上的 Fly64 系统
> **版本**: 1.0 — 对应 B01 波次

---

## 概述

Fly64 的 EVO（自进化）闭环是一个独立于脑模型和 SM64 的常驻进程，运行在 `fly64-evo` tmux 会话中。本指南说明如何通过系统 crontab 定期检查 EVO 闭环活性，并在停摆时自动拉起。

核心守卫脚本：

| 组件 | 路径 | 职责 |
|------|------|------|
| **evo_liveness_guard.py** | `fly64/scripts/evo_liveness_guard.py` | 检查 EVO 循环日志新鲜度、环境契约自检 |
| **evo_loop_launcher.sh** | `fly64/scripts/evo_loop_launcher.sh` | 启动/停止/重启/状态查询 EVO 闭环进程 |

---

## 1. 前提条件

在安装 crontab 前，确保：

```bash
# 1) 脚本有执行权限（B02 已固化）
ls -la fly64/scripts/evo_liveness_guard.py
ls -la fly64/scripts/evo_loop_launcher.sh
# 预期输出: -rwxr-xr-x ... (100755)

# 2) EVO 闭环当前可通过 launcher 正确管理
bash fly64/scripts/evo_loop_launcher.sh --status
# 预期输出: "EVO loop is running" 或 "EVO loop is NOT running"
```

## 2. Crontab 安装

### 安装 crontab 条目

以 `root` 或运行 Fly64 的用户身份执行：

```bash
# 编辑 crontab
crontab -e
```

追加以下条目（每 5 分钟检查一次）：

```cron
# Fly64 EVO 循环活性守卫（每 5 分钟检查，停摆自动重启）
*/5 * * * * cd /root/fly64 && python3 scripts/evo_liveness_guard.py >> runtime/evo_guard.log 2>&1

# 可选项：自动拉起停摆的 EVO 进程
*/5 * * * * cd /root/fly64 && bash scripts/evo_loop_launcher.sh --status | grep -q "NOT running" && bash scripts/evo_loop_launcher.sh --restart >> /tmp/evo_auto_restart.log 2>&1
```

**说明**：

- 第一行：仅检查日志新鲜度并告警（推荐最小权限）
- 第二行（可选）：检测到 EVO 未运行自动重启
- 日志输出到 `runtime/evo_guard.log` 便于回溯

### 验证 crontab 已安装

```bash
crontab -l
# 应包含上述条目
```

### 强制激活

某些 WSL 发行版默认不启动 cron 服务。如 crontab 不执行：

```bash
sudo service cron status
sudo service cron start
sudo systemctl enable cron  # Ubuntu 22.04+
```

---

## 3. Kill→自愈验证

本验证**必须在 WSL 实机执行**，且需要用户确认（规则 9）。

### 3.1 记录当前状态

```bash
# 记录当前 PID
bash fly64/scripts/evo_loop_launcher.sh --status
ps aux | grep evolution_skill | grep -v grep
cat skills/evo_stall_alarm.json 2>/dev/null || echo "无告警文件（健康状态）"
```

### 3.2 人为 kill EVO 循环

```bash
# 找到 EVO 循环进程 PID
EVO_PID=$(ps aux | grep evolution_skill | grep -v grep | awk '{print $2}')
echo "Killing EVO loop PID=$EVO_PID"
kill "$EVO_PID"
sleep 3

# 确认已停止
bash fly64/scripts/evo_loop_launcher.sh --status
# 预期输出: "EVO loop is NOT running"
```

### 3.3 等待 crontab 自动恢复

等待 ≤ 1 个 crontab 间隔（默认 5 分钟）：

```bash
# 每 30 秒检查一次
for i in $(seq 10); do
  echo "=== check $i ==="
  bash fly64/scripts/evo_loop_launcher.sh --status
  sleep 30
done
```

### 3.4 验证自愈成功

```bash
# 1) EVO 进程已运行且 PID 更新
bash fly64/scripts/evo_loop_launcher.sh --status
# 应显示 "EVO loop is running" 且 PID 与 3.2 步不同

# 2) 告警文件刷新（出现新的告警记录）
cat skills/evo_stall_alarm.json
# expected: 时间戳不应晚于 kill 时刻

# 3) 护日志留存
tail -20 runtime/evo_guard.log
# 应包含停摆检测→重启的记录

# 4) 记录自愈事件到 evolution_history（规则 15）
# 手动追加记录（agent 自动执行时由 agent 补全）
```

---

## 4. 回滚说明

### 4.1 回滚 crontab

```bash
crontab -e
# 删除或注释已添加的 Fly64 EVO 条目
# 保存退出后验证
crontab -l | grep -c evo  # 应返回 0
```

### 4.2 回滚执行位

```bash
git checkout -- fly64/scripts/evo_liveness_guard.py fly64/scripts/evo_loop_launcher.sh
```

### 4.3 回滚整个文档

```bash
git rm docs/operations/evo-daemon-setup.md
git commit -m "revert: 移除 EVO 守护文档"
```

---

## 5. 规则 9 提醒

> **规则 9**: 任何部署/重启/kill 操作需用户显式确认后执行。

在 WSL 上实际执行以下操作前必须先获得用户确认：

1. ❗ `crontab -e` 追加/修改 EVO 守卫条目
2. ❗ `kill` EVO 循环进程（用于自愈验证）
3. ❗ `bash evo_loop_launcher.sh --restart`
4. ❗ 部署 `install-pre-commit-hook.sh`（B17）

**建议的确认格式**：

```
用户，请确认是否在 WSL 上执行以下操作：
  1. 安装 EVO 守卫 crontab（每 5 分钟检查）
  2. 执行 kill→自愈验证（人为停止 EVO 循环）
输入 Y 确认执行，N 跳过。
```

---

## 6. 守护架构图

```
┌─────────────────────────────────────────────┐
│                  crond (每 5 分钟)            │
│  ┌──────────────────────────────────────┐    │
│  │ evo_liveness_guard.py --check        │    │
│  │  ├─ 读 evolution_log.jsonl 时间戳    │    │
│  │  ├─ 超 30 分钟无更新 → 写告警        │    │
│  │  └─ --selfcheck → 全环境契约自检     │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  停摆检测                                    │
│  ┌──────────────────────────────────────┐    │
│  │ evo_loop_launcher.sh --status        │    │
│  │  └─ 未运行 → --restart               │    │
│  │      ├─ kill 旧锁进程                 │    │
│  │      ├─ tmux new-session fly64-evo   │    │
│  │      └─ setsid nohup evolution_skill │    │
│  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 附录 A：常用命令速查

| 动作 | 命令 |
|------|------|
| 检查 EVO 进程状态 | `bash fly64/scripts/evo_loop_launcher.sh --status` |
| 手动启动 EVO | `bash fly64/scripts/evo_loop_launcher.sh --launch` |
| 停止 EVO | `bash fly64/scripts/evo_loop_launcher.sh --stop` |
| 重启 EVO | `bash fly64/scripts/evo_loop_launcher.sh --restart` |
| 附加到 EVO tmux | `bash fly64/scripts/evo_loop_launcher.sh --attach` |
| 查看守卫日志 | `tail -f runtime/evo_guard.log` |
| 查看告警快照 | `cat fly64/skills/evo_stall_alarm.json` |
| 环境契约自检 | `python3 fly64/scripts/evo_liveness_guard.py --selfcheck` |