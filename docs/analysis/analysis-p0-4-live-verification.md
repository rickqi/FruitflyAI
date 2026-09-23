# P0-4 实机验证报告 + Coach 建议被钳位根因定位

> **验证人**: captain  
> **日期**: 2026-09-23 22:47–22:50 (+08:00)  
> **环境**: WSL2 Ubuntu-22.04 · WSLg `DISPLAY=:0` · 实时 SM64 + 脑模型 + 教练服务  
> **探针脚本**: `scripts/_probe_runtime.sh`、`_probe_live.sh`、`_probe_coach.sh`、`_monitor_strategy.sh`

---

## 一、运行环境实况

| 组件 | 状态 |
|------|------|
| 脑模型 | ✅ 运行中 · PID 27260 · `python3 -m fly64.main --bridge /tmp/f64b_traj` · uptime 1:53:00 |
| 教练服务 | ✅ 运行中 · PID 26255 · `plugin.service --interval 10 --bridge-path /tmp/f64b_traj` · cycle 922 |
| Dashboard | ✅ HTTP 200 |
| 服务健康 | `dashboard ok / bridge ok (age 11s) / strategy_write ok / degraded=false / consecutive_failures=0 / alert=false` |
| 桥接新鲜度 | 11.5s（健康） |

### ⚠️ 发现：部署世系与仓库分裂

| | 部署 `/root/fly64` | Windows 仓库 |
|---|---|---|
| `BRAIN_VERSION` | **2.24.0**（注释：*motor-pool recovery … t1-t9 team fix*）| **2.23.12** |
| `runner.py _weave_escalation` | **0 处（未部署）** | 已提交（t3/P0-4）|
| `memory.py displacement_per_speed` | 7 处 ✓ | 已提交 |
| `main.py median_speed` | 11 处 ✓ | 已提交 |

⇒ 部署副本是**另一条更新的世系**（含 "t1-t9 team fix"），与 Windows 仓库不是同一来源。**"单一真实来源分裂"这一已知问题在现场依然存在。** 因此下文区分"目标行为已验证"与"我的具体提交已部署"。

---

## 二、✅ P0-4 目标行为：已验证（教练确实被唤醒了）

抓到的**活体形态恰好是 P0-4 要解决的"高速振荡"**：

```
/memory.json
  median_speed           488.4        ← 高速
  displacement_per_speed 0.0386       ← 位移效率极低
  disp_60s               1131.3
  progress_ineffective   True         ← P0-4 指标正在触发
  stuck_duration         621.24s
  anomaly_state          oscillating
  loop_score             0.032
  coverage_pct           7.2
  reflex_active          True
  reflex_ineffective     False

/help.json
  help_reason  stuck_no_progress      ← 教练升级已激活
  diagnosis    stuck_no_progress: stuck=1.00 dur=579s loop=0.00 cov=6.8%
```

**判据**：以 `displacement_per_speed` 表示的"位移效率"口径已在生产中落地并触发；在这个形态下求助闸门**打开**（`help_reason` 非空），不再是旧版的 `check_help_needed() → None`。

**与我的 t3 提交的关系（如实说明）**：部署版发出的 `help_reason` 是 `stuck_no_progress`，而我的 t3 实现发出 `weave_no_progress` 且走 `runner.py::_weave_escalation`（该路径在部署副本中 **0 处**）。因此：

- ✅ **P0-4 的"设计意图"已实机验证**（低位移效率 → 唤起教练）
- ⚠️ **但验证的不是我的那份实现**，而是部署世系中一份语义等价、更早落地的实现

---

## 三、🎯 新根因：Coach 建议被脑模型钳位"吃掉"并持久化

### 3.1 活体观测（60 秒监控，5 秒采样）

```
t=+ 5s   file.turn_bias=0.8    file.bold=20.0   advice_ts=…931.01   ← 教练写入
t=+10s   file.turn_bias=0.8    file.bold=20.0
t=+15s   file.turn_bias=0.8    file.bold=20.0
t=+20s   file.turn_bias=0.8    file.bold=20.0
t=+25s   file.turn_bias=0.8    file.bold=20.0
t=+30s   file.turn_bias=0.8    file.bold=20.0
t=+35s   file.turn_bias=0.25   file.bold=10     advice_ts **不变**   ← 被覆写
t=+40s…+60s  turn_bias=0.25  bold=10                                ← 再未恢复
```

`advice_ts` 在覆写前后**不变** ⇒ 覆写者**不是教练**。

### 3.2 定位到写入方（`fly64/main.py` ≈ L1368）

```python
# Clamp turn_bias to [0, 0.4] — the EVO loop/plugin may write
# 0.8+ which amplifies the oscillating reflex (R31-fix12).
if "turn_bias" in _expl:
    _expl["turn_bias"] = max(0.0, min(0.25, float(_expl["turn_bias"])))
if "bold_explore_stuck_s" in _expl:
    _expl["bold_explore_stuck_s"] = max(1, min(10, float(...)))
...
memory_ctrl.bold_turn_bias = float(_expl.get("turn_bias", 69.0))   # 用的是钳位后的值
...
# P0 self-heal: write clamped values back to the file so every
# reader (EVO loop, coach plugin) sees the corrected values.
_as_raw.setdefault("exploration", {}).update({
    "turn_bias": _expl.get("turn_bias", 0.25),
    "bold_explore_stuck_s": _expl.get("bold_explore_stuck_s", 60), ...})
```

### 3.3 逐位吻合 —— 根因确认

| 参数 | 教练发出 | 文件实际 | 代码钳位上限 |
|------|---------:|--------:|-------------|
| `turn_bias` | **0.8** | **0.25** | `min(…, 0.25)` ✅ |
| `bold_explore_stuck_s` | **20.0** | **10** | `min(…, 10)` ✅ |

### 3.4 完整机制

```
① 教练写入 turn_bias=0.8 / bold=20.0        → active_strategy.json
② 脑模型热加载（每 600 tick ≈ 12s）读取该文件
③ R31-fix12 安全钳位：turn_bias → 0.25（上限 0.25）/ bold → 10（上限 10）
④ 「P0 self-heal」把**钳位后的值回写文件** ⇒ 教练的原值被永久覆盖
⑤ 脑模型实际使用 memory_ctrl.bold_turn_bias = 0.25（钳位值）
⇒ 教练建议从"进入消费"到"被抹掉"不超过一个热加载周期
```

### 3.5 为什么这是缺陷（而非单纯的设计取舍）

钳位本身**有正当理由**（注释说明：`0.8+` 会放大振荡反射）。缺陷在于**三个叠加**：

1. **静默**：教练与仪表板都看不到"建议被钳掉"。`/memory.json` **没有 `coach_applied` 字段**（本次实测 missing），所以链路断在何处无人可见 —— 典型 **EVO-066「机制存在、报告成功、无法生效」** 家族。
2. **持久化放大**：自愈回写把钳位值写回文件，使教练原值**不可恢复**，下次读取也拿不到。
3. **注释与代码不一致**：注释写 `[0, 0.4]`，代码实际 `min(…, 0.25)`（与 P0-2 中 param-engineer 发现的 `turn_bias 注释 [0,0.4] vs 代码 0.25` **同一处**，现已在生产中确认）。

**这直接解释了用户的原话「coach 建议未生效，未脱困」** —— 建议确实被接收、被解析、被写入，但被脑模型的安全钳位吃掉，行为因此不变。

---

## 四、其他现场观察

| 观察 | 值 | 说明 |
|------|-----|------|
| 教练模型 | `qwen3.8-27b-uncensored` | 与仓库 `llm.env` 的 `glm-5v-turbo` **不同** |
| 教练建议 | "别在蓝水里打转了，立刻朝右上角那抹绿色岸边猛转方向并连跳爬上岸！" + 👁 读屏 | 建议质量合理、含读屏 |
| 教练 strategy | `fallen_recovery.mode=directional_climb`、`exploration.bold_explore_stuck_s=20.0/turn_bias=0.8`、`escape.stuck_threshold_s=8.0`、`command{turn_and_go,45,2.5,70}` | 含 `command` 直控 |
| `command` 是否落地 | **未落地**（文件中无 `command` 段）| 另一处断链，值得单独查 |
| `coach_frames` | **4,938 个文件** | 与 A3 报告中"0 文件"不同；P2-2 的留痕实际在工作 |
| `__generation` | 12 | 较低 |
| 教练建议时效 | 生效约 **26 秒**后被覆写 | 与热加载周期同量级 |

另：`/tmp/f64r_traj-*.npz` 累计 **3,000+ 个 × 40–55 MB**（约 130+ GB），`f64r_v220-*` 另有 100+ 个。**磁盘占用值得关注**。

---

## 五、结论与建议

### 结论

| 项 | 结果 |
|----|------|
| **P0-4 设计意图** | ✅ **实机验证通过** —— 低位移效率形态下教练被成功唤起 |
| 我的 t3 具体实现 | ⚠️ 未部署（部署世系有等价实现） |
| **Coach 建议不生效** | 🎯 **根因定位** —— 脑模型 R31-fix12 钳位 + 自愈回写抹掉教练值 |
| 部署/仓库一致性 | ⚠️ 分裂仍在（2.24.0 vs 2.23.12） |

### 建议（P1 优先级）

1. **让钳位可见**：`/memory.json` 增加 `coach_applied` 与 `clamped_keys`（键 → 原值 → 钳后值），使"建议被钳掉"可观测。这是把 EVO-066 家族第 N 例变成"响亮失败"的最小改动。
2. **解决教练与钳位的设计冲突**：二选一 ——
   - 让钳位对**教练来源**放宽（例如教练经 `command` 直控而非调 `turn_bias`），或
   - 在教练 prompt 中显式给出**可用取值范围**，使 LLM 不再输出必然被钳掉的值（当前 prompt 要求 0–1，而代码只接受 ≤0.25）。
3. **注释与代码对齐**：`[0, 0.4]` → 实际的 `0.25`（P1-2 已登记）。
4. **查 `command` 未落地**：教练给出了 `command{turn_and_go}` 但文件无该段，需单独定位。
5. **收敛部署世系**：把 `/root/fly64` 与仓库做一次正式对齐（已有的 "单一真实来源分裂" 待办）。
6. **磁盘**：`/tmp/f64r_traj-*.npz` 130+ GB，建议加轮转/清理策略。

---

> **生成**: captain · 2026-09-23  
> **保存位置**: `docs/analysis/analysis-p0-4-live-verification.md`
