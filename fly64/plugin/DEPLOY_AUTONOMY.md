# Fly64 自治常驻服务部署（WSL）

目标：`plugin/runner.py` 的 10s 循环落成 WSL 常驻服务——自治不依赖 DSH 会话存活，
教官层（LLM 咨询）按需介入且不可用时自动降级。

## 组件

| 文件 | 作用 |
|---|---|
| `plugin/service.py` | 常驻服务入口：10s 循环 + 健康自检 + LLM 降级 + pid/状态/日志 |
| `plugin/watchdog.sh` | 存活监控：进程死掉自动重启，连续失败告警 |
| `scripts/consolidate.sh` | 已制度化：重启脑模型时连带重启自治循环 |

## 运行时产物（plugin/ 下）

- `fly64-service.pid` — 进程 pid（systemd 模式下由服务管理，可不依赖）
- `service_status.json` — 每周期心跳：`health.dashboard/bridge/strategy_write/degraded/alert`
- `service.log` — 运行日志；`watchdog.log` — 看门狗日志

## 健康自检（每周期写入 service_status.json）

1. `dashboard` — 仪表板 HTTP `/evolution.json` 可达
2. `bridge` — 桥接文件（默认 `/tmp/f64b`，可用 `--bridge-path`/`FLY64_BRIDGE_PATH`）
   mtime 新鲜度（默认 60s 内为健康，`--bridge-stale` 可调）
3. `strategy_write` — 咨询后 `skills/active_strategy.json` 确认写出
4. 连续失败 ≥5 → `health.alert=true` 并写 ALERT 日志

## LLM 咨询链路与降级

- `http` 传输（`FLY64_LLM_BASE_URL`/`FLY64_LLM_API_KEY`/`FLY64_LLM_MODEL`）：
  不依赖 DSH 会话，优先配置。
- `subagent` 文件握手传输：依赖 DSH 会话存活；有硬超时（120s），
  超时/失败时服务**降级**为本地诊断（`source=local_diagnosis` 写入
  coach_advice.json，EvolutionSkill 照常本地诊断）——自治不依赖会话。
- 降级状态见 `service_status.json` 的 `health.degraded`。

## 部署步骤（WSL，/root/fly64）

### 方式 A：systemd（推荐）

`/etc/systemd/system/fly64-autonomy.service`:

```ini
[Unit]
Description=Fly64 autonomy resident service (10s cycle)
After=network.target

[Service]
WorkingDirectory=/root/fly64
Environment=PYTHONPATH=/root/fly64
# Environment=FLY64_LLM_TRANSPORT=http
# Environment=FLY64_LLM_BASE_URL=https://.../v1
# Environment=FLY64_LLM_API_KEY=sk-...
ExecStart=/usr/bin/python3 -m plugin.service --interval 10
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fly64-autonomy
systemctl status fly64-autonomy
```

systemd 自带存活监控；可再加 watchdog.sh 的 cron 作为二级兜底
（`is_alive` 检测 systemd 管理的 pid 文件同样有效——service.py 始终写 pid 文件）。

### 方式 B：nohup + watchdog（无 systemd 权限时）

```bash
cd /root/fly64
chmod +x plugin/watchdog.sh
PYTHONPATH=/root/fly64 nohup /usr/bin/python3 -m plugin.service --interval 10 \
  >> plugin/service.log 2>&1 &
# 存活监控：每分钟检查并自动重启
(crontab -l 2>/dev/null; echo "* * * * * /root/fly64/plugin/watchdog.sh") | crontab -
```

watchdog 行为：pid 存活→退出；死了→重启并清零失败计数；启动失败连续 ≥3 次→
`watchdog.log` 写 ALERT 并附 service.log 末尾 20 行。

### 方式 C：随 consolidate.sh

`scripts/consolidate.sh` 现在会在重启脑模型后自动重启自治循环（并停旧 pid）。
无需手动干预。

## 验证

```bash
# 1) 进程与 pid（注意：进程 cmdline 是 plugin.service，pgrep -af fly64 匹配不到）
cat plugin/fly64-service.pid && ps -p $(cat plugin/fly64-service.pid)
pgrep -af plugin.service
# 2) 心跳健康
python3 -c "import json;print(json.load(open('plugin/service_status.json'))['health'])"
# 3) 降级链路（无 LLM env 时 consult 走 local_diagnosis）
grep local_diagnosis plugin/service.log
# 4) 看门狗：手动 kill 后 60s 内应自动重启
kill $(cat plugin/fly64-service.pid); sleep 65; tail plugin/watchdog.log
# 5) 单元测试
python3 -m pytest tests/test_service.py -q   # 10 passed
# 6) 部署证据留档（评审要求）
{ cat plugin/fly64-service.pid; ps -p $(cat plugin/fly64-service.pid) -o pid,lstart,cmd; \
  cat plugin/service_status.json; } > plugin/DEPLOY_EVIDENCE.txt
```

## 回归说明

- 不改动 `PluginRunner.run_cycle` 语义；ServiceRunner 复用其取数/触发判定与
  StrategyWriter，brain 侧 `load_active_strategy` 热加载协议不变。
- `test_plugin_mhr.py::TestDialogueDecision::test_main_dialogue_pause_wait_wiring`
  在本次改动前的基线上即已失败（预先存在，与本任务无关）。
