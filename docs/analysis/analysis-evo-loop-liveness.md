# EVO 闭环重启与停摆告警 — 实测报告 (P0-3 / t3)

> **任务**: t3 — P0-3 重启并守护进化闭环 + 停摆告警
> **执行人**: ops-engineer (team fly64-p0-signal-path)
> **attempt_id**: 0c571fde-f4d4-4e96-a335-9f3b38882a15
> **实测时间**: 2026-09-25 20:57–21:03 (本机 CST)
> **依据**: `docs/analysis/analysis-t2-evolution-pipeline-failure.md` 失效点 #1

---

## 0. 结论 (TL;DR)

自进化闭环已按项目启动契约（**tmux 守护会话 + setsid nohup 双重防护**）在 WSL
重新拉起并持续运行；新增**外部停摆守护脚本**（30 min 可配置阈值，三路告警落点）与
**环境契约一键自检**（「EVO 闭环」与脑模型/SM64 桥接同列）。全部四项验收均通过：

| # | 验收项 | 结果 | 证据 |
|---|--------|:---:|------|
| 1 | 闭环在跑，`evolution_log.jsonl` 持续增长 | ✅ | §2 两次采样（行数 48763→48769） |
| 2 | 人为 kill → 阈值内告警（red→green） | ✅ | §3 告警日志 stalled/recovered 两行 |
| 3 | 自检输出含「EVO 闭环」+ 失败修复指引 | ✅ | §4 通过态 + 失败态 + 修复指引 |
| 4 | 报告写入 `docs/analysis/analysis-evo-loop-liveness.md` | ✅ | 本文件 |

---

## 1. 故障复现与处置

审计时（2026-09-24）状态：`evolution_log.jsonl` 最后写入 2026-09-17 10:22，停摆
7 天；无 python 进程、无 `.evo_loop.lock`、无计划任务、dashboard 8765 不可达。

本任务实测起点（2026-09-25 20:51）：

```
tmux 会话  fly64: 3 windows（脑模型在跑）          ← dashboard 8765 在线 (http=200)
脑模型     PID 9557 /usr/bin/python3 -m fly64.main --bridge /tmp/f64b_traj ...
进化闭环   （无进程）                              ← 需要重启
/root/fly64/skills/evolution_log.jsonl            ← 130 MB，最后写入 2026-09-24 12:05
```

即：**dashboard（脑模型）是活的，唯独自进化闭环停摆**——与审计结论「闭环根本不在
运行」一致。本任务把闭环按启动契约重新拉起，并加上守护与告警。

---

## 2. 交付物

### 2.1 `fly64/scripts/evo_loop_launcher.sh`（新）— 常驻闭环启动器

严格遵循 `fly64/scripts/wsl_launcher.sh` 与
`fly64/docs/wsl-launcher-deployment.md` 的启动契约：

- 不使用裸 `wsl -e bash -c "setsid nohup ..."`（WSL 会话回收会 SIGTERM 整棵进程树）。
- **tmux 守护会话** `fly64-evo`（独立于脑模型会话 `fly64`，`--stop` 不会误杀脑模型）。
- 子进程 **setsid nohup + `</dev/null`** 双重防护。
- 支持 `--launch / --restart / --stop / --status / --attach`。

启动命令（等价于）：

```bash
tmux new-session -d -s fly64-evo
# 窗口内:
setsid nohup /usr/bin/python3 skills/evolution_skill.py \
  --max-iterations 0 --interval 5 > /tmp/evo_loop.log 2>&1 </dev/null &
```

### 2.2 `fly64/scripts/evo_liveness_guard.py`（新）— 停摆检测 + 告警 + 自检

**停摆检测**：`skills/evolution_log.jsonl` 超过阈值（默认 `1800s = 30 min`，可配置
`--threshold` / 环境变量 `EVO_STALL_THRESHOLD_S`）无新行 ⇒ 判停摆。

**三路告警落点**：

| 落点 | 路径 | 说明 |
|------|------|------|
| 日志 | `skills/evo_stall_alarm.jsonl` | 每状态跳变（stalled/recovered）追加一行 |
| dashboard 端点 | `skills/evo_stall_alarm.json` | 原子快照（规范告警状态，dashboard/监控可读） |
| service_status | `plugin/service_status.json` | 合并 `evo_loop` 键（可选、保留既有键） |

> **dashboard 端点说明**：脑模型 dashboard（8765）是只读 HTTP 服务，无告警 POST
> 端点（唯一 POST 是 `/active_strategy-update`，语义为参数更新）。故「dashboard
> 端点」落点为 `evo_stall_alarm.json` 快照 + 每次告警时刻对 dashboard 做可达性
> 记录（`dashboard_reachable`）。把 `evo_loop_stale` 注入 `/memory.json` 是 main.py
> 的一行改动，**在本任务 inScope 之外**（详见 §6 后续建议）。

**环境契约自检**（`--selfcheck`）：把「EVO 闭环」与「脑模型 dashboard」「SM64/桥接」
「EVO 心跳」同列输出，失败给出可执行修复指引；退出码 0=通过 / 1=失败。

### 2.3 `fly64/skills/evolution_skill.py` — **零改动**

并发约束：另一 DSH 会话正在改 `evolution_skill.py`（本任务开始时该文件已被并行会话
改到 `SKILL_VERSION=3.5.1`，并已集成 `evo_funnel_alarm.py` 的 `write_heartbeat`）。
按任务要求「告警逻辑放在新脚本里、对 evolution_skill.py 改动降到最小」，本任务把
全部停摆检测/告警/自检逻辑放在新脚本 `evo_liveness_guard.py`，**对 evolution_skill.py
零改动**——这是并发约束下改动最小的选择，也完全满足「告警写入点在外部脚本」的要求。

---

## 3. 验收证据

### 3.1 闭环在跑 + `evolution_log.jsonl` 持续增长

启动后两次采样（`wc -l` + 时间戳）：

```
$ bash scripts/evo_loop_launcher.sh --launch
[2026-09-25 20:57:32] 进化闭环已启动 (PID: 11262)     # tmux fly64-evo + setsid nohup

# 采样 A
21:02:11   48763 skills/evolution_log.jsonl

# 采样 B（+30s）
21:02:41   48769 skills/evolution_log.jsonl           # 30s 内 +6 行（interval=5s）

$ cat skills/.evo_loop_heartbeat.json
{"ts": 1790341359.3, "pid": null, "state": {"iteration": 11, "ts": 1790341359.3}}
```

另一次更长窗口采样：`20:57:37 = 48728 行 → 20:58:21 = 48736 行`（44s +8 行）。
日志尾行含 `context.version`（brain 2.24.0 / skill 3.5.1），证明写的是新版观测上下文。

### 3.2 人为 kill → 阈值内告警（red → green）

守护脚本用**缩短阈值 30s**（`--watch --interval 5 --threshold 30`，生产用默认 30 min）
实测：

```
# 1) kill 闭环
$ bash scripts/evo_loop_launcher.sh --stop     # 终止 PID 11262

# 2) 守护在阈值内自动触发 RED
$ cat skills/evo_stall_alarm.jsonl
{"ts":1790341183.98,"event":"stalled","threshold_s":30.0,
 "reason":"evolution_log.jsonl 32s 无新行 > 阈值 30s",
 "log_age_s":32.04,"log_lines":48747,"loop_pid":null,
 "dashboard_reachable":true}

$ cat skills/evo_stall_alarm.json        # snapshot: {"stale": true, "loop":{"pid":null,"alive":false}, ...}

# 3) 重启闭环 → 守护自动恢复 GREEN
$ bash scripts/evo_loop_launcher.sh --launch     # 新 PID 11732

$ cat skills/evo_stall_alarm.jsonl
{..."event":"stalled",...}
{"ts":1790341245.13,"event":"recovered","reason":"正常",
 "log_age_s":2.85,"log_lines":48748,"loop_pid":11732,
 "dashboard_reachable":true}

$ cat skills/evo_stall_alarm.json        # snapshot: {"stale": false, "loop":{"pid":11732,"alive":true}, ...}
```

告警在日志最后写入后 **32.04s**（阈值 30s）内触发；`plugin/service_status.json` 第 185 行
合并出 `evo_loop` 键（第三路落点）。**red→green 证据完整。**

### 3.3 自检：通过态 / 失败态 + 修复指引

通过态（闭环在线）：

```
$ python3 scripts/evo_liveness_guard.py --selfcheck
==============================================================
 Fly64 环境契约一键自检
==============================================================
  [● 通过] EVO 闭环: pid=11732 日志48757行/最后写3s 前
  [● 通过] 脑模型 dashboard: http://127.0.0.1:8765/memory.json http=200
  [● 通过] SM64 / 桥接: 桥接 /tmp/f64b_traj age=7.6s
  [● 通过] EVO 心跳: 3s 前
--------------------------------------------------------------
  结论: 全部通过 ✅
```

失败态（人工 `--stop` 后）：

```
  [○ 失败] EVO 闭环: 进化闭环进程不在运行
  [● 通过] 脑模型 dashboard: http://127.0.0.1:8765/memory.json http=200
  [● 通过] SM64 / 桥接: 桥接 /tmp/f64b_traj age=5.1s
  [● 通过] EVO 心跳: 6s 前
--------------------------------------------------------------
  结论: 存在失败项 ❌
--------------------------------------------------------------
修复指引:
  → EVO 闭环: bash scripts/evo_loop_launcher.sh --launch（或 --restart）；随后用 --status 确认 pid 与日志增长
==============================================================
[exit code: 1]
```

---

## 4. inScope 文件清单

| 文件 | 动作 |
|------|------|
| `fly64/scripts/evo_loop_launcher.sh` | ★ 新增（常驻闭环启动器） |
| `fly64/scripts/evo_liveness_guard.py` | ★ 新增（停摆检测 + 告警 + 自检） |
| `docs/analysis/analysis-evo-loop-liveness.md` | ★ 新增（本报告） |
| `fly64/skills/evolution_skill.py` | **零改动**（并发约束，告警全在外置脚本） |

---

## 5. 证据边界与诚实声明

1. **WSL 与 Windows 双副本**：开发侧 `D:\codes\flygym\fly64`（git 仓库），部署侧
   `/root/fly64`（非 git，`autonomy_deploy_restart.sh` 按精选文件清单同步）。本任务
   新脚本在开发侧落盘后 `cp` 到 `/root/fly64/scripts/`；实测全部在 WSL 部署侧完成。
2. **「dashboard 端点」实现边界**：dashboard 无告警 POST 端点，告警的 dashboard
   可见面是 `evo_stall_alarm.json` 快照 + `service_status.json["evo_loop"]` 合并；
   注入 `/memory.json["evo_loop_stale"]` 需改 `main.py`（本任务 inScope 之外）。
3. **测试用缩短阈值**：red/green 实测用 `--threshold 30`（秒）以在合理时间内取证；
   生产默认 `1800s = 30 min`，可配置。
4. **守护脚本自身的常驻化**：`evo_liveness_guard.py` 提供 `--check`（适合 cron/计划
   任务每分钟驱动）与 `--watch`（前台/`nohup` 常驻）两种形态；未把它焊进
   `evo_loop_launcher.sh`（避免超出 inScope），见 §6 建议。
5. **脑模型/session 状态**：本次只重启进化闭环，未动脑模型（PID 9557）与 SM64；
   SM64 进程当前未运行（脑模型跑合成模式，桥接 `/tmp/f64b_traj` 由脑模型维护）。

---

## 6. 后续建议（非本任务 inScope）

1. **把守护接入计划任务/启动器**：`*/1 * * * * /usr/bin/python3 /root/fly64/scripts/evo_liveness_guard.py --check`，
   或让 `evo_loop_launcher.sh --launch` 连带 `nohup` 拉起 `--watch`（默认 30 min 阈值）。
2. **dashboard 内联告警**：`main.py` 读 `skills/evo_stall_alarm.json` 并把
   `stale` 暴露为 `/memory.json["evo_loop_stale"]`（M4-d4 计划里的落点），一处改动。
3. **闭环空转与 dashboard 停摆的区分**：当前 `evolution_log.jsonl` 与心跳都只在
   dashboard 可达时写入（`fetch_all` 全真才落盘）。若 dashboard 死而闭环活着，日志
   停增会误报「闭环停摆」——守护已同时探测 dashboard 可达性（`dashboard_reachable`）
   以区分，但更彻底的修法是把心跳写到 dashboard 门之外（属于 evolution_skill.py 的
   改动，留给正在编辑它的并行会话）。
