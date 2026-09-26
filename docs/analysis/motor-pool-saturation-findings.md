# 运动池饱和 / steering 池静默 —— 根因定位报告（T1，只读）

- **任务**：t1 根因定位：forward 池饱和与 steering 池静默的因果链确认
- **约束**：只用只读手段；**未修改任何生产代码**。本任务新增文件仅两个：
  - 本报告 `docs/analysis/motor-pool-saturation-findings.md`
  - 临时复现脚本 `fly64/.tmp/t1_motor_pool_probe.py`（`.gitignore` 已忽略 `fly64/.tmp/`；只 import 生产模块、只写 stdout）
- **时间窗**：2026-09-23 14:57–15:2x（本地）
- **格式**：每条均按「假设 → 代码位置（file:line） → 实测/计算证据 → 结论」，并逐条标注证据等级。

---

## 0. 结论速览（TL;DR）

| 症状 | 本次定位的主因 | 关键代码锚点 | 证据等级 |
|---|---|---|---|
| forward 池贴顶 46.15/50 Hz | **不是 MBON**（MBON 单路上限 ~8.2 Hz，硬复位 LIF 周期限制）。真正地板是 post-leak 恒流三项：`TurnAdaptation.breakout_drive` 的 stuck>30 s **无条件** boost（实测 stuck=806.8 s → **0.500 V/tick**）+ `tonic_current` 0.18 + 粘滞 `reflex_forward` ≤0.20。离线 `w=0` 实测：**单靠该地板即 25.00 Hz**；叠加 live 平台 `mb=+0.96` → **50.00 Hz**；`mb=0` → 25.00 Hz | `model.py:1818-1823`、`model.py:377-392`、`model.py:1612`、`model.py:1696` | 在线实测 + 离线复现实测 |
| steering 池 0–2 Hz（left 常见 0.000） | 同一 boost 对左右池各 **−0.25 V/tick**；且除 `escape_current`/tonic/OU 外，**所有 steering 驱动都是成对反号的推挽项** → 两池实测**从不共放电**；`TurnAdaptation` 疲劳由池放电自身积分 → 双池静默时**无任何复活电流**（自锁）。离线 live-like 实测复现：**0.94–2.23 Hz 且每次只有一侧放电** | `model.py:1821-1823`、`model.py:1808-1812`、`model.py:365-392`、`model.py:1776-1777`、`model.py:1889-1901` | 在线实测 + 离线复现实测 + 解析推算 |
| `gate_jump` 恒假 | 同键两路 producer 单位相反：main.py 用 **per-tick 比例(0..1)** 去比 **Hz 阈值**(2.0/3.082) → 恒假；telemetry.py 用 **Hz**(12.5–26.9) 比 2.0 Hz → 恒真 | live `main.py:2417-2420` / `main.py:2527` / `telemetry.py:94` | 在线实测（同一 tick 两路取值相反，26/26） |

**最重要的一条更正**：既有叙事「`mb_mbon_forward≈0.96` 饱和 → forward 池贴顶（R17 守卫该拦没拦住）」在机制上**不成立**。MBON 注入在漏电**之前**（`model.py:1518` < `model.py:1611`）且放电后硬复位到 0（`model.py:1880`），因此 MBON 单路最多只能让 forward 池以 6 tick 周期放电（**8.2 Hz**，§A2 解析 + 离线实测双重确认）。46–50 Hz 只能由 post-leak 恒流地板产生（§A5）。R17 守卫「不触发」是**触发门限高于观测平台**（0.98/0.99 vs 实测 0.9633），并非被绕过；而且它只作用于 MBON 权重列，对真正的地板完全无效（§A3/§A4）。

**方法论自查与更正（详见 §A5/§B3）**：第一轮两处**推算**已被离线实测取代并修正——(a) "地板求和 ⇒ 缓冲 ≳0.12 V 就每 tick 放电（50 Hz）"过于乐观：post-leak 恒流 `I` 的稳态是**限周期**，`I=0.88 → 25.00 Hz`、`I=1.03 → 50.00 Hz`（统一限周期律见 §A5，10 个 arm 逐点吻合）；(b) "OU 只有阈值 0.9%"过于悲观：OU 相关时间 ≈50 tick，被 `v` 的泄漏积分放大 `1/(1−a) = 5.52×`，实际提供 **~0.3 V 共模亚阈基底**（80 s 内仍 0 次放电）。

---

## 1. 方法与证据分级

### 1.1 五类证据（全文逐条标注）

| 标记 | 含义 | 手段 |
|---|---|---|
| **在线实测** | live 大脑进程当前吐出的数据 | WS `ws://127.0.0.1:8766/` F643 packet（`scripts/probe_pools.py` 与等价内联探针）；HTTP `http://127.0.0.1:8765/flow.json`、`/memory.json` |
| **离线复现实测** | 在**未修改的**生产代码路径上跑确定性实验 | `FlyModel(demo=True)` + 运行时替换（monkey-patch 实例属性/方法）+ 与 `Observatory` 同一 `telemetry.py:71-79` 口径统计；脚本：`fly64/.tmp/t1_motor_pool_probe{,2,2b,3,3b}.py`（E1–E8b） |
| **解析推算** | 闭式计算 | LIF 递推、tanh 反函数、OU 稳态方差、疲劳积分 |
| **代码证据** | 静态读码 | 见各条 file:line |
| **未测量** | 明确无法取到的量 | §5 清单 |

> 纪律：**推算不写成实测**。凡由"地板求和 + 阈值比较"得到的界，均标注为推算；凡离线 fixture 上的数，均标注为"demo fixture，不代表真实连接组量级"。

### 1.2 在线数据源（可复现）

```
python scripts/probe_pools.py                        # 4 次运行，13 行 F643 采样
# 联合采样（同一时刻同时取 WS 行与 flow.json）见 §6.2 内联脚本
Invoke-WebRequest http://127.0.0.1:8765/flow.json
Invoke-WebRequest http://127.0.0.1:8765/memory.json
```

`rows[].{forward,left,right,jump,...}` 的单位定义（`telemetry.py:71-79`）：

```
denom = min(ticks, 13) * dt          # dt = model.dt = 0.02
rates[key] = counts[ids].mean() / denom      # ⇒ Hz（满值 rate_max = 1/dt = 50）
```

因此 `forward = 50.000` ⟺ 该池全部神经元在窗口内**每个 tick 都放电**；`46.1538 = 12/13 × 50` ⟺ 13 tick 内放电 12 次。这正是"46.15/50 Hz"的口径。

### 1.3 离线复现的条件与限制

- 预处理连接组缓存 `fly64/.cache/malecns` 在**本机不存在**（`Test-Path` = False），live 大脑实际跑在 WSL（`/root/fly64`，`python -m fly64.main`，已运行 02:36:49）。
- 因此离线实验用 `FlyModel(demo=True)`（`model.py:721-754`：4096 神经元、固定 seed 的合成 fixture 图）。它**只能**证明结构性/算术性结论（注入顺序、硬复位周期、噪声量级、疲劳自锁、A/B 差分），**不能**代表真实连接组的绝对量级。
- 离线实验中的数值均在报告中标注为 "demo fixture"。

### 1.4 溯源（provenance）

| 文件 | 仓库工作区 md5 | live WSL `/root/fly64` md5 | 结论 |
|---|---|---|---|
| `fly64/fly64/model.py` | `9cb829ca7c3d3985396e23daa94142d8` | 同 | **本报告 model.py 行号 = live 代码** |
| `fly64/fly64/telemetry.py` | `995074d9d9d19f78f02c9c628ac4bf4c` | 同 | 同上 |
| `fly64/fly64/mushroom_body.py` | `12693745e8b29650154efd3f1770fcde` | 同 | 同上 |
| `fly64/fly64/central_complex.py` | `c6c55ffc81a317756d64dbda7d1568aa` | 同 | 同上 |
| `fly64/fly64/main.py` | `348283f0…`（**并发修改中**） | `1ebcfcc7bbb5f1f3d4c6e79928da05f4` | live 与仓库**不一致** → 本报告凡引用 main.py 一律用 **live 行号** |

- git：`HEAD = 5dba6fe`（工作区 `main.py` 在本任务进行中被其他成员修改，15:00:18 起 +91 行，含 RULE-19 单位修复）。
- 进程：Windows PID 7852 为 WSL 端口转发；真实 brain 进程为 WSL `26220`（`./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj …`，启动时长 02:36:49）。
- 结论：**model/telemetry/mushroom_body/central_complex 的 file:line 全部对 live 代码成立**；main.py 的行号以 live 副本为准（并在 §4 标注）。

---

## 2. A) forward 池为何停在 46.15/50 Hz

### A1. 采样实测（任务要求 ≥6 行）

**`scripts/probe_pools.py` 4 次运行，13 行（去重后时间跨度 t=3930.92 → 3936.02 s）——在线实测：**

| t (s) | visual | forward | left | right | jump | strike | crouch | control.x | control.y | decision_source |
|---|---|---|---|---|---|---|---|---|---|---|
| 3930.92 | 11.983 | **50.000** | **0.000** | **0.000** | 25.000 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3930.94 | 11.264 | **50.000** | 0.000 | 0.000 | 25.000 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3930.96 | 11.290 | **50.000** | 0.000 | 0.000 | 25.000 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3933.76 | 11.869 | **50.000** | 0.000 | 0.000 | 26.923 | 0.000 | 0.000 | −70 | 70 | anomaly_reflex |
| 3933.78 | 11.399 | **50.000** | 0.000 | 0.000 | 23.077 | 0.000 | 0.000 | −70 | 70 | anomaly_reflex |
| 3933.80 | 11.491 | **50.000** | 0.000 | 0.000 | 26.923 | 0.000 | 0.000 | −70 | 70 | anomaly_reflex |
| 3934.96 | 10.962 | **50.000** | 0.000 | 0.000 | 23.077 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3934.98 | 11.424 | **50.000** | 0.000 | 0.000 | 23.077 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3935.00 | 10.774 | **50.000** | 0.000 | 0.000 | 22.115 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3935.02 | 10.785 | **50.000** | 0.000 | 0.000 | 22.115 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3935.98 | 11.950 | **50.000** | 0.000 | 0.000 | 14.423 | 0.000 | 0.000 | 70 | 70 | anomaly_reflex |
| 3936.00 | 12.119 | **50.000** | 0.000 | 0.000 | 13.462 | 0.000 | 0.000 | −70 | 70 | anomaly_reflex |
| 3936.02 | 11.229 | **50.000** | 0.000 | 0.000 | 15.385 | 0.000 | 0.000 | −70 | 70 | anomaly_reflex |

→ 13/13 行 forward ≡ 50.000（贴顶）、left = right ≡ 0.000、jump 13.5–26.9、visual 10.8–12.1、decision_source ≡ anomaly_reflex。

**更长窗口统计（在线实测，327 行 / 6.5 s）：**

| 池 | 行数 | min | max | mean | 非零行占比 |
|---|---|---|---|---|---|
| visual | 327 | 10.888 | 12.742 | 11.692 | 100% |
| **forward** | 327 | **30.769** | **50.000** | **45.272** | 100% |
| left | 327 | 0.000 | 5.769 | 0.994 | 32.4% |
| right | 327 | 0.000 | 9.615 | 1.606 | 30.0% |
| jump | 327 | 12.500 | 26.923 | 21.216 | 100% |
| strike | 327 | 0.000 | 17.885 | 6.787 | 94.2% |
| crouch | 327 | 0.192 | 3.846 | 0.877 | 100% |

**另一窗口（535 行 / 10.7 s，t=4067.18–4077.86）**：forward mean **46.17** Hz（min 34.62、max 50.00，**44% 行恰好 50.000**）；left mean 0.047（2.4% 行非零，最长连续 0 段 **392 tick = 7.84 s**）；right mean 0.866（11.2% 行非零，最长连续 0 段 329 tick = 6.58 s）。

**全局占用（同一 packet，在线实测）**：`n = 166700`，occupancy 字节 mean 22.1，`>0` 占 36.9%，**`==255` 占 3.94%（≈6570 个神经元在窗口内每 tick 都放电）**——网络整体处于大范围贴顶状态，不限于运动池。

### A2. LIF 稳态 ≠ 饱和（核心修正）

- **假设 H-A1（任务给定）**：注入 `I = mb_mbon_forward × mbon_gain_forward(0.35)`，漏电因子 `a = exp(−dt/τm) = exp(−0.2) = 0.8187`，`v_ss = I/(1−a)`；若 `v_ss > threshold = 1.0` ⇒ 仅 MBON 一路已使 forward 池饱和。
- **代码位置**：
  - 注入：`model.py:1516-1518` `self.v[self.forward] += mbon[0] * self.mbon_gain_forward`
  - 漏电：`model.py:1611` `self.v *= np.exp(-self.dt / self.tau_m)`
  - 放电与**硬复位**：`model.py:1879-1881` `fired = self.v >= self.threshold; self.v[fired] = self.reset  (reset = 0.0, model.py:406)`
  - 常量：`model.py:633-637`（`mbon_forward_weight = 0.35` → `mbon_gain_forward`；**全仓唯一赋值**，无任何调制）
- **解析推算**：`a = 0.818731`。
  | mb_mbon_forward | I = 0.35·mb | v_ss = I·a/(1−a) | 任务公式 I/(1−a) |
  |---|---|---|---|
  | 1.0000 | 0.3500 | 1.5808 | 1.9308 |
  | 0.9687 | 0.3390 | 1.5313 | 1.8704 |
  | 0.9633（实测平台） | 0.3372 | 1.5228 | 1.8600 |
  | 0.9600 | 0.3360 | 1.5176 | 1.8536 |
  | 0.8000 | 0.2800 | 1.2647 | 1.5525 |

  两点必须说清：
  1. 注入（1518）发生在漏电（1611）**之前**，故 MBON 对"下一 tick 电位"的贡献是 `a·I`，不是 `I`。任务给的 `I/(1−a)` 相当于"注入在漏电之后"，**高估 1/a = 1.22×**。正确式为 `v_ss = I·a/(1−a)`。
  2. 更重要的是：`v_ss > 1` 只说明"**不复位**的定点越过阈值"。由于放电后 `v` 被硬置 0，同 tick 电位最大只有 `a·I ≤ 0.8187 × 0.35 = 0.2866`，**永远不足以在同一 tick 再次放电**。于是神经元进入**周期放电**而非"每 tick 放电"：
     - 解析周期（对前漏电注入的硬复位递推 `v ← a·(v + I)`，复位 `v≥1 → 0`；统一写法见 §A5）：
       `T = min{ n ≥ 1 : a·I·(1 − a^n)/(1 − a) ≥ 1 }`；`mb = 0.96` ⇒ `I = 0.336` ⇒ `T = 6 tick` ⇒ **8.33 Hz**。
     - "每 tick 都放电"的必要条件：`a·I ≥ 1` ⇒ `I ≥ 1.2214` ⇒ **`mb ≥ 3.49`**，而 `mbon ∈ [−1, 1]` ⇒ **不可能**。
- **离线复现实测（真实 `step()` 路径，demo fixture，除 MBON 外全部驱动置零：`w=0`、`tonic=0`、`visual_connected=False`、OU σ=0、escape 关、CX gain=0、reflex=0、stuck=0）**：

  | mb_mbon_forward | 解析：周期/频率 | 实测 forward 占用率 | 实测 Hz |
  |---|---|---|---|
  | 0.40 | 永不放电（v_ss=0.632） | 0.0000 | 0.00 |
  | 0.55 | 永不放电（v_ss=0.870） | 0.0000 | 0.00 |
  | 0.63 | 永不放电（v_ss=0.994） | 0.0000 | 0.00 |
  | 0.80 | 8 tick / 6.25 Hz | 0.1280 | 6.40 |
  | **0.96** | **6 tick / 8.33 Hz** | **0.1640** | **8.20** |
  | 1.00 | 6 tick / 8.33 Hz | 0.1640 | 8.20 |

  解析与实测吻合到 1 个 tick 内 ⇒ **MBON 单路在真实代码路径上的上限就是 ~8.2 Hz（占用率 0.164）**。
- **注入顺序的独立验证（离线复现实测 E5）**：把一路**后漏电**常数电流（探索惯性 `model.py:1790`，同一个 `step()` 路径）固定住，实测稳态电位与 `I/(1−a)` **逐位吻合**：`I=0.0750 → max v = 0.4137`（预测 0.4137）、`I=0.0500 → 0.2758`、`I=0.0200 → 0.1103`。与 §A2 的"前漏电注入只有 `I·a/(1−a)`"形成对照，**实验确认了注入顺序的不对称性**（同一模型的同一 LIF 递推，前漏电驱动只能产生周期性放电）。
- **在线实测反证（26 次联合采样，同一时刻取 WS 行 + flow.json）**：`mb_mbon_forward` 在 **−0.8861 … +0.9659** 之间摆动，而 forward 池同期 38.46–50.00 Hz（mean 45.12，7/26 行恰好 50.000）：
  - t=4026.18：`mb=+0.2384`，forward = **46.15**，left 0.00，right 3.85（**正好复现任务给的基线数值**）
  - t=4027.60：`mb=−0.8861`（强负注入 ≈ −0.31 V），forward 仍 = **46.15**
  - t=4028.00–4028.40：`mb` 连续 5 次恰为 **+0.9633**（0.96 平台），forward = 50.00
  - 相关系数 `r(forward_Hz, mb_mbon_forward) = +0.449`（弱相关，且**符号无关**：负 mb 时池仍 46.15/50）
- **结论**：**H-A1 的"v_ss > 1"算术正确，但推论错误**——在硬复位 LIF 上，MBON 单路**不可能**产生 46–50 Hz 的贴顶；在线数据也证明 forward 占用率不随 MBON 符号改变。MBON 不是 forward 贴顶的主因（它是叠加在恒定地板上的 ±0.29 V 摆动的调制项）。

### A3. R17 饱和守卫为何从不触发

- **假设 H-A2**：`mb_mbon_forward ≈ 0.96` 使守卫（|tanh| ≥ 0.98 持续若干帧）无法触发。
- **代码位置**：`mushroom_body.py:239-241`（`sat = |mbon_outputs| >= 0.98`；`_saturation_frames` 计数）、`mushroom_body.py:250-258`（达到 `saturation_frames_threshold` 才做列缩放，`saturation_scale_factor = 0.85`）、`mushroom_body.py:246-249 + 159-161`（steep 模式：**进入** >0.99、**退出** <0.8、缩放 ×3）。
  - **更正任务给定值**：任务写作"持续 **50** 帧"，代码现值为 `saturation_frames_threshold = 30`（`mushroom_body.py:150`，注释"50→30: 更快响应饱和"）。docstring/README 中仍留有 50 帧的旧表述。
- **解析推算**：`|tanh(x)| ≥ 0.98 ⟺ |x| ≥ atanh(0.98) = 2.2976`；steep 门限 `|x| ≥ atanh(0.99) = 2.6467`。
  实测平台 `0.9633 ⟺ |raw| = atanh(0.9633) = 1.9898 ≈ 2.0`（`tanh(2.0)=0.9640`）⇒ 距守卫门限还差 **15.5%**（2.2976/1.9898 = 1.155）。另一实测极值 `|−0.932|`（punch）⟺ `raw = 1.6734`。
- **在线实测**：
  - 12 次采样（≈13 s）内 `mb_saturation_events` 恒为 **27**，同期 `mb_mbon_forward` 达 +0.9382；
  - 后段 6 次采样（15:03:45–15:04:02，≈17 s）`27 → 28`，同期 stuck_duration 806.8→808.4 s；
  - 26 次联合采样窗口内 `mb_mbon_forward` 触及 +0.9659 仍未触发（satEv 不变）。
  ⇒ 守卫**并未失效**（约十分钟一次事件），但对 **0.96–0.97 平台结构性不敏感**：`sat` 带（≥0.98）与 `steep` 带（≥0.99）都**高于观测平台**，形成一条"看不见"的盲带（0.8–0.98 之间的贴顶状态无人管理）。
- **附带（重要）**：R17 只缩放 KC→MBON **权重列**（`mushroom_body.py:256`），它**完全不触碰** `model.py:1518` 的注入增益（`mbon_gain_forward` 恒 0.35，全仓唯一写入点 `model.py:637`）。因此：**即使守卫触发，也只能削弱 MBON 路径——而该路径本身不足以贴顶（§A2）**。
- **结论**：守卫"从不触发"的直接原因是**触发门限（0.98/0.99）高于实测平台（0.9633）**；但即便触发也不是本症状的解药，因为贴顶由 MBON 之外的路径维持。

### A4. `model.py:1518` 的注入对池占用率有负反馈吗？

- **假设 H-A3**：存在某种占用率负反馈使贴顶不可能发生（或守卫即该反馈）。
- **代码位置**：`model.py:1516-1542`（MBON 注入块）——逐字只有 `mbon[k] * 常数增益`，**没有任何** `spikes[forward]` / `forward_rate` / `activity` 项。
- **代码证据（穷举）**：`self.v[self.forward]` 的全部写点，共 15 处（其中 1619 为整池 `motor_nodes` 注入）：

  | 行 | 项 | 符号 | 门控 |
  |---|---|---|---|
  | 1518 | `mbon[0]·0.35` | + | 恒定 |
  | 1539 | `recalled[0]·0.35·0.5` | + | 记忆召回命中 |
  | 1619 | `escape_current`（整池） | + | `escape_mode` |
  | 1647 | `_fallen_forward` | + | fallen 相 |
  | 1685 | `_escape_forward_accum` | + | escape |
  | 1696 | `min(0.20, reflex_forward·0.003)` | + | reflex 标志（**粘滞，从不复位**） |
  | 1707 | coach forward | + | coach 活跃 |
  | 1802 | interactive 接近偏置 0.10 | + | interactive_near |
  | 1821 | **`_brk`（R16 breakout）** | + | `stuck_duration > 30`（**与疲劳无关**） |
  | 1840 | cliff 切向 −0.08 | **−** | cliff_confirmed |
  | 1846 | `_rest·0.12` | + | loop_score/cliff_standoff > 0 |
  | 1859 | pit 振荡 0.40·hop | + | stuck>60 且 mb<0.2 |
  | 1867 | `−scene_danger·0.06` | **−** | scene_danger > 0 |
  | 1877 | `_rec·0.08` | + | stuck>30 且 mb<0.05 |
  | 1893 | `ou_state[0]·0.15` | ± | 恒定（噪声） |

  **没有任何一项是池占用率的函数**；两个负项（1840/1867）由外部事件门控，与占用率无关。
- **全仓唯一的"占用率 → 电流"回路**（代码证据）：`model.py:1502-1513`（`pathway_activity["forward"] = spikes[forward].mean()` → `update_eligibility` → `apply_gain_update`，`gain_modulation.py:176-223`，`Δgain = η·R·E·scale`）→ 该 gain 只乘**突触电流**（`model.py:1573` `current *= gains[pathway_idx]`），**不乘 MBON 注入**（1518 用常量 0.35）。R>0 时这是**正反馈**（`GAIN_MAX = 2.5`），R<0 时才是负（`GAIN_MIN = 0.5`）。在线实测 `dopamine_gain.forward = 0.9504`（低于默认 1.5）⇒ 本会话总体上该回路在**抑制**侧，但幅度有界、且完全不作用于 R16 地板项。
- **结论**：**`model.py:1518` 的注入对池占用率零反馈**；模型中不存在"池贴顶 → 自动抑制"的负反馈（R17 在 MBON 权重侧、dopamine-gain 在突触电流侧、TurnAdaptation 只在 steering 池），对 §A5 的 post-leak 恒流地板**完全无约束**。

### A5. 真正的地板 = 主因（R16 breakout 的 stuck 无条件 boost）

- **假设 H-A4**：46–50 Hz 由 post-leak 恒流地板造成，其中最大单项是 `TurnAdaptation.breakout_drive` 的 stuck boost。
- **代码位置**：
  - `model.py:1818-1826`：
    ```
    _brk = self._turn_adapt.breakout_drive(stuck_duration=getattr(self, "stuck_duration", 0.0))
    if _brk > 0.0:
        self.v[self.forward] += _brk                    # 1821
        self.v[self.turn_left] -= _brk * 0.5            # 1822
        self.v[self.turn_right] -= _brk * 0.5           # 1823
        if _brk > 0.25:
            self.v[self.jump_nodes] += (_brk - 0.25) * 0.5   # 1826
    ```
  - `model.py:377-392`：
    ```
    nl = min(1.0, self.left / saturation) ; nr = min(1.0, self.right / saturation)
    base = self.breakout_gain * min(nl, nr)
    if stuck_duration > 30:
        boost = min(0.50, self.breakout_gain * (stuck_duration / 120.0))
        return base + boost            # ← boost 与 base（疲劳）无关
    return base
    ```
  - 其余 post-leak 恒流：`model.py:1612`（`tonic_current = 0.180`，`model.py:482`）、`model.py:1696`（reflex_forward ≤0.20）、`model.py:1618-1619`（escape_current ∈ [0.05, 0.25]）。
- **在线实测（stuck_duration）**：`memory.json` = 803.22 s（`stuck_score = 1.0`）；6 次采样 806.80 → 808.40 s；后段 876.5 → 878.5 s。**全程 > 30 s**。
- **解析推算（boost）**：`min(0.50, 0.35 × 806.8/120) = min(0.50, 2.353) = 0.5000`（已顶到 0.50 上限，且从 120 s 起就饱和）。
- **离线复现实测（未改代码，直接调生产函数）**，fatigue = (0, 0)（即**完全没有左右交替**）：

  | stuck_duration | `breakout_drive` 返回 |
  |---|---|
  | 0.00 s | 0.000000 |
  | 30.00 s | 0.000000 |
  | **30.01 s** | **0.087529** |
  | 60.00 s | 0.175000 |
  | 120.00 s | 0.350000 |
  | **806.80 s** | **0.500000** |
- **推算/实测统一的限周期律（本报告的核心机制式）**：设 `I_eff` 为该池"等效恒流"——**后漏电**注入（tonic / reflex_forward / breakout / escape_current / OU / CX…）取 `I_eff = I`，**前漏电**注入（MBON / 记忆召回 / corrective）取 `I_eff = a·I`。放电后 `v` 被硬置 0，故限周期为
  `T = min{ n ≥ 1 : I_eff·(1 − a^n)/(1 − a) ≥ 1 }`，占用率 `= 1/T`。
  - 校验（离线实测，见下表）：`I=0.18 → 永不放电（0.993 < 1）`；`I=0.38 → T=4 → 12.50 Hz`；`I=0.68 → T=2 → 25.00 Hz`；`I=0.88 → T=2 → 25.00 Hz`；`I=1.03 → T=1 → 50.00 Hz`。**8 个 arm 全部逐点吻合**。
  - 前漏电的代价因子：`mb=0.96 → I_eff = a·0.336 = 0.275 → T=6 → 8.33 Hz`（E2 实测 8.20 Hz）。
  - ⇒ 因此"地板 0.88 V/tick"**不等于**"必然 50 Hz"，而是"必然 25 Hz 限周期"；把 25 → 50 Hz 顶到天花板的最后一脚由**额外增量**提供（escape_current +0.15，或 MBON 高峰 +0.275 等效，或连接组缓冲电流）。
- **离线实测（E6b：post-leak 地板账，`w=0`，600 tick，clean config，demo fixture）**：

  | 臂 | 地板构成 | forward | left | right | jump | 观测 max v(fwd) |
  |---|---|---|---|---|---|---|
  | F1 | brk .50 + tonic .18 + reflex .20 = **0.88** | **0.5000 (25.00 Hz)** | 0.0000 | 0.0000 | 0.2000 | 0.880 |
  | F2 | tonic .18 + reflex .20 = 0.38（**去 boost**） | 0.2500 (12.50 Hz) | 0.0000 | 0.0000 | 0.0000 | 0.946 |
  | F3 | tonic .18 单路 | 0.0000 (0.00 Hz) | 0.0000 | 0.0000 | 0.0000 | 0.993（<1，永不放电） |
  | F4 | brk .50 + tonic .18 = 0.68（无 reflex） | 0.5000 (25.00 Hz) | 0.0000 | 0.0000 | 0.2000 | 0.680 |
  | F5 | F1 + `escape_current` .15 = **1.03** | **1.0000 (50.00 Hz)** | 0.0800 (4.00 Hz) | 0.0500 (2.50 Hz) | 0.3350 | — |
  | F6 | F1 + OU | 0.5000 (25.00 Hz) | 0.0000 | 0.0000 | 0.1981 | 0.952 |
  | F7 | F1 + OU + `mb=+0.96` | **1.0000 (50.00 Hz)** | 0.0000 | 0.0000 | 0.1981 | — |
- **附带实测（两个额外的 stuck 门控开环注入，当前 live 未满足条件）**：`model.py:1853-1861`（EVO R29 pit 振荡：`stuck>60` 且 `mb_mbon_forward<0.2` 且 `anomaly_state_name ∈ {fallen, idle}` ⇒ `forward += 0.40·hop`、`jump += 0.80·(1−hop)`、`turn_left += 0.05·sin`）与 `model.py:1873-1877`（EVO R22：`stuck>30` 且 `mb<0.05` ⇒ `forward += 0.08`）是**同族的第 2、3 路开环地板**。它们由 `main.py` 写入的 `mb_mbon_forward` 与 `anomaly_state_name` 门控；live 实测 `anomaly_state ∈ {oscillating, stuck_ramp}` 且 `mb` 常 >0.2 ⇒ **本会话未触发**。但把 offline arm 的这两个镜像值去掉后（part 3 初版），本会 0 Hz 的 `tonic=0.18` 臂立刻变成 **15.00 Hz（占用率 0.30）**、转向池 9.17/9.33 Hz —— 即这两路注入一旦满足条件，同样会**在不看池占用率的情况下**抬升/压制运动池（本报告的 clean config 已把它们对齐 live 值关闭）。
- **离线实测（E7b：MBON 在地板之上的**边际**效应，同一地板 0.88）**：

  | 臂 | `mb_mbon_forward` | forward 占用率 | forward Hz |
  |---|---|---|---|
  | G1 | 0.00 | 0.5000 | 25.00 |
  | G2 | **+0.96（live 平台）** | **1.0000** | **50.00** |
  | G3 | −0.89（live 实测最小值） | 0.5000 | 25.00 |
  | G4 | +0.96 + OU（live-like） | 1.0000 | 50.00 |

  ⇒ MBON 的等效增量 = `a·0.35·0.96 = 0.275 V`，恰好把 0.88 的地板推过 `T=1` 门槛；**它决定 25 还是 50 Hz，而不是决定"是否贴顶"**。这与在线实测完全一致：live forward 34.6–50.0 Hz（mean 46.17）在 `mb` −0.89…+0.97 之间摆动；`mb=+0.9633` 平台期 forward = 50.00（t=4028.00–4028.40），`mb=+0.2384` 时 46.15（t=4026.18），`mb=−0.8861` 时仍 46.15（t=4027.60，连接组缓冲把它托在地板之上）。
- **结论**：forward 池贴顶的主因是 **R16 breakout 的 stuck 无条件 boost（0.500 V/tick）+ tonic（0.180）+ 粘滞 reflex_forward（0.200）** 组成的 post-leak 恒流地板（0.88 V/tick）——**单靠它、且不含任何 MBON 与连接组电流（`w=0`）时就已把 forward 顶到 25 Hz 限周期**；连接组回投与 MBON 峰值把它推到 45–50 Hz，且**与池占用率无负反馈**（§A4）、**守卫管不到**（§A3）。
- **粘滞标志**（代码证据 + live 行号）：live `main.py:1550-1552` 在 reflex 活跃时写 `model.reflex_forward = action["control_y"]`，但**从不复位**（live main.py 全仓只有 4 处赋值，无 `= 0`）⇒ 一旦被写为 70/127，`reflex_forward` 的 0.20 V/tick 注入**永久生效**，与 reflex 是否活跃无关。
- **在线一致性检查**（用限周期律读 live 数据）：
  - live 地板（brk 0.500 + tonic 0.180 + 粘滞 reflex 0.200）= 0.88 ⇒ 离线实测 **25.00 Hz（占用率 0.5）**；
  - live 实测 forward 34.6–50.0 Hz（mean 45–46）⇒ 说明 live 还有**额外增量**把 `I_eff` 推到 0.88 之上：连接组回投电流（`w≠0`，离线 `w=0` 臂没有这一项）+ escape_current（F5 实测 1.03 → **50.00 Hz**）+ MBON 峰值（E7b 实测 **50.00 Hz**）。三者叠加即 live 看到的"46.15–50 贴顶"；
  - 12 次采样（escape_behavior **全为 True**）⇒ `forward_rate ≡ 1.0` = 50.000 Hz（与 F5 臂一致）；
  - `mb=−0.89` 的 t=4027.60 仍 46.15 Hz ⇒ 负 MBON 未能压低地板上方的占用率，**证明地板不来自 MBON**。
- **结论**：forward 池贴顶的主因是 **R16 breakout 的 stuck 无条件 boost（0.500 V/tick）+ tonic（0.180）+ 粘滞 reflex_forward（0.200）** 组成的 post-leak 恒流地板（0.88 V/tick）——**单靠它、且不含任何 MBON 与连接组电流（`w=0`）时就已把 forward 顶到 25 Hz 限周期**；连接组回投、escape_current 与 MBON 峰值把它推到 45–50 Hz。该地板**与 MBON 无关**（§A2）、**无任何占用率负反馈**（§A4）、**守卫管不到**（§A3）。

---

## 3. B) left steering 池为何 0.000 Hz（right 3.85 Hz）

### B1. CX 转向偏置在 anomaly_reflex 期间被覆盖/清零了吗？

- **假设 H-B1**：anomaly_reflex 把 CX→转向池的注入清零/覆盖。
- **代码位置**：
  - CX 注入：`model.py:1758-1777`（`cx_bias = self.cx.update(...)`；`self.v[self.turn_left] += cx_bias * self.cx_steering_gain_turn`；`self.v[self.turn_right] -= cx_bias * self.cx_steering_gain_turn`；`cx_steering_gain_turn = 0.12`，`model.py:664`）
  - CX 输出范围：`central_complex.py:316`（`np.clip(raw, -max_steering, max_steering)`），文档串 `central_complex.py:537` "Steering bias in [-1, 1]" ⇒ 注入上限 **±0.12 V/tick**（阈值的 12%）。
- **代码证据**：**没有任何** anomaly/reflex 分支写 `turn_left`/`turn_right` 的 v 清零；模型侧异常反射只通过 `model.reflex_turn/reflex_forward/reflex_jump` 三个标志以**注入**形式参与（`model.py:1687-1698`）。
- **真正被"覆盖"的是输出**：live `main.py:1550-1552` reflex 直接写 `control.x/y/jump`，并置 `reflex_override = True`；`resolve_decision_source` 中 `reflex_override` 优先级高于 `lf_escape/lf_steering`（`main.py:700-721`，live 701-712 区段）。**在线实测**：535/535、327/327、26/26 行的 `decision_source` 均为 `anomaly_reflex`（或在其后的 `lf_steering/lf_escape` 混合中出现），且 WS 行的 `control.x = ±70` 在窗口内成对翻转 ⇒ LIF steering 表决不进摇杆。
- **附带（归因口径，仅记录）**：`_lif_motion` 在 reflex 写完 control 之后采样（live main.py 对应区段），因此 Python 写入的 x/y 会被记为"LIF 运动"。
- **未测量**：live `flow.json` 的 102 个键中**没有 cx/steering_bias 相关键**（见 §5）⇒ CX 实际输出幅度无法在线实测，本条只能给"未被清零 + 上限 0.12"的结论（代码 + 解析）。
- **结论**：**H-B1 不成立**（池级注入未被清零/覆盖）；被覆盖的是输出路径；CX 即使全额工作也只有 ±0.12 V/tick，属推挽项，无法单独把池顶过阈值。

### B2. TurnAdaptation 疲劳是否造成单侧锁死？

- **假设 H-B2**：left 池长期零放电被疲劳状态维持。
- **代码位置**：`model.py:345-375`（`update`：`self.left = self.left·exp(−dt/τ) + max(0,act_left)·dt`；`counter_drive` 返回 `(drive_right, drive_left) = (nl·gain, nr·gain)`，`gain = 0.18`、`saturation = 0.5`、`τ = 3.0`）；注入 `model.py:1808-1812`；`breakout_drive` `model.py:377-392`。
- **离线复现实测（E1，直接调生产类）**：
  | 场景 | 结果 |
  |---|---|
  | left、right 池**均静默** 10 s | fatigue = (0.000000, 0.000000)、`counter_drive = (0.0, 0.0)`、`breakout_drive(0) = 0.0` |
  | 按**实测速率**积分 10 s（left 0.047 Hz → 0.00094/tick；right 0.866 Hz → 0.01732/tick） | fatigue = (0.002728, 0.050274)、`counter_drive = (0.000982, 0.018098)`、`breakout_drive(0) = 0.001910`、`breakout_drive(806.8) = 0.501910` |
- **解析推算**：对静默池的**唯一**恢复电流是"对手池疲劳"产生的 counter_drive 注入——在上表实测速率下，注入静默 left 池的量是 **0.0181 V/tick = 阈值 1.8%**；而同一 tick 的 breakout boost 对 left 池施加 **−0.2500 V/tick**，压制强度是恢复电流的 **13.8×**。
- **结论**：**H-B2 不成立**（疲劳不是"锁死"机制：它按定义注入**对手**池）。但成立的是更严重的**自锁**：疲劳量由池自身放电积分，**双池静默 ⇒ 疲劳归零 ⇒ 恢复电流归零**。模型中不存在与池放电无关的 steering 复活路径（OU 见 §B3，量级不够）。

### B3. `model.py:1893-1901` 的 OU 噪声对 left 池有驱动吗？

- **假设 H-B3**：per-pool OU 噪声提供足够的 subthreshold 抖动来间歇点亮 left 池。
- **代码位置**：`model.py:1884-1901`。关键三点：
  1. **每池一个标量**：`ou_state[1]`（left 池）被**同一个值**加到全部 40 个 left 神经元（1896）⇒ 纯共模，**不可能制造左右差异**。
  2. 应用位置在**主放电判定之后**（`fired` 判定 1879-1881 → OU 注入 1886-1901 → `refired` 复检 1903）⇒ 只能在 `v` 已距阈值 < 0.15·|ou| 时补最后一脚。
  3. 幅度：`ou_sigma = 0.12`、`ou_theta = 2.0`（`model.py:497-499`）。
- **解析推算（含一处自我更正）**：OU 稳态 sd = `σ/√(2θ) = 0.12/2 = 0.0600`（per-pool）、`0.10/2 = 0.0500`（global）；**每 tick** 注入为 `0.15·ou_state` ⇒ sd 0.0090 V、`0.22·ou_global` ⇒ sd 0.0110 V。
  - ⚠️ **更正**：不能把"每 tick 注入 sd"直接当作对 `v` 的贡献——OU 自身相关时间 ≈ `1/θ = 50 tick`（`theta=2.0`，`dt=0.02`），而 `v` 是**泄漏积分器**，稳态放大 `1/(1−a) = 5.52×`。故相关性维持的 OU 包络对 `v` 的贡献约为 `(0.011 + 0.009) × 5.52 ≈ 0.11 V`，4σ 尾部（global 4σ = 0.2 V × 0.22 × 5.52 ≈ **0.24 V**，per-pool 4σ ≈ 0.20 V）可达 **~0.34 V**。首次估算（"0.9% 阈值"）**低估了约 30 倍**。
- **离线复现实测（E3'）**：仅保留 OU（`ou_sigma=0.12`、`ou_global_sigma=0.10`），其余全部置零（含 explore-commit bias，见下），跑 **4000 tick = 80 s**：
  | 量 | forward | left | right | jump |
  |---|---|---|---|---|
  | 放电 tick 数 | **0** | **0** | **0** | **0** |
  | 占用率 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
  | 观测到的 max v | 0.2746 V | **0.3377 V** | 0.3114 V | — |
  **对照实测**：同一配置但 `ou_sigma = ou_global_sigma = 0.0` ⇒ 400 tick 后所有池 `max v = 0.00000`（无放电）。⇒ **0.3 V 的亚阈基底完全来自 OU**，但 80 s 内**一次都没能跨过阈值**。
- **附带发现（同一隔离实验暴露的另一个推挽驱动）**：`model.py:1782-1791` 的探索方向惯性 `_explore_bias ∈ [−0.75, 0.75]` × `_explore_commit_strength = 0.10` ⇒ 每 tick 对一个转向池注入 **±0.075 V 的推挽电流**，符号每 250 tick（5 s）随机翻转；它是**后漏电注入**，稳态 `v_ss = 0.075/(1−a) = 0.4137 V`。E5 实测（`_explore_bias` 固定、其余全零）：`I=0.0750 → max v = 0.4137`、`I=0.0500 → 0.2758`、`I=0.0200 → 0.1103`，**与 `I/(1−a)` 逐位吻合**（同时验证了 §A2 的"注入顺序决定稳态"结论）。这是"干净"模型里**最强的单路 steering 驱动**，但仍是推挽项、且不放电。
- **结论**：OU 对 left 池**没有可用驱动**：它贡献 ~0.3 V 的**共模亚阈基底**（阈值的 34%），80 s 内 0 次放电；且"每池一个标量"意味着 OU **在结构上不可能区分左右**。**H-B3 不成立**。

### B4. 转向池的突触输入是否"无人驱动"？

- **假设 H-B4**：转向池因 MBON/CX 缺失而收不到任何驱动（故必然静默）。
- **代码证据（穷举 turn 池写点）**：

  | 行 | 项 | 极性 | 说明 |
  |---|---|---|---|
  | 1270 | `corrective_left/right`（`compute_error_gradient`，`model.py:1187-1272`） | ±（+amp / −0.6amp） | 实测饱和 amp=0.06：`corrective=(+0.06, −0.036)` |
  | 1519/1520 | `mbon[1]·0.35` / `mbon[2]·0.35` | ± | **MBON turn 通道（未暴露于遥测）** |
  | 1540/1541 | `recalled[1..2]·0.175` | ± | 记忆召回 |
  | 1619 | `escape_current`（整池） | + | 0.05–0.25，`escape_mode` 门控 |
  | 1627-1630 | coach `strategy_turn_bias·0.30` | 单侧 | 需 bias>0.01 |
  | 1651-1653 | `bold_turn_drive`（±0.35·mag） | 单侧 | forced-bold |
  | 1668-1672 | escape commit `+0.15 / −0.10` | 单侧对 | 50 tick 相位翻转 |
  | 1692-1694 | `reflex_turn`：`min(0.25, |x|·0.004)` | 单侧 | 实测 control_x=±70 ⇒ **0.25** |
  | 1705 | coach_turn_bias ∓0.006 | ± | coach |
  | 1731-1732 | 目标横向偏置 ∓0.12 | ± | 需 target approaching |
  | 1749-1751 | opening 注入 ≤0.20 | 单侧 | escape 且 opening 非对称 |
  | 1776-1777 | **CX `±cx_bias·0.12`** | ± | 推挽 |
  | 1790-1791 | explore commit `|_explore_bias·0.10| ≤ 0.075` | ± | 推挽；符号每 250 tick 翻转（见 §B3） |
  | 1808-1812 | counter_drive | 单侧 | 见 §B2（量级 ~0.018） |
  | 1822-1823 | breakout **−0.25 每侧** | **−** | 见 §A5 |
  | 1837-1839 | cliff 切向 +≤0.15 | 单侧 | cliff_confirmed |
  | 1861 | pit `0.05·sin` | ± | stuck>60 且 mb<0.2 |
  | 1896/1899 | OU `0.15·ou_state[1/2]` | ±共模 | 每池一个标量；稳态贡献 ~0.3 V（§B3 实测），80 s 内 0 次放电 |

- **关键结构事实**：除 `escape_current`（+0.05…0.25，整池同号）、`tonic`（+0.18）、OU（共模亚阈基底 ~0.3 V，§B3）外，**每一项都是成对反号（推挽）或某侧专用**；模型中**不存在"同号、持续、可单侧独立"的 steering 驱动**。⇒ 两池**不可能同时**被顶到阈值以上。
- **在线实测支持**：535 行窗口内 **`left>0 且 right>0` 的行数 = 0**（严格互斥；`left>0 & right==0` 13 行、`right>0 & left==0` 60 行、双零 462 行 = 86.4%）。
- **在线实测（"left 是否被硬锁在 0"）**：两个窗口结论不同——
  | 窗口 | left mean / 非零占比 / max | right mean / 非零占比 / max |
  |---|---|---|
  | 327 行（6.5 s） | 0.994 Hz / 32.4% / 5.769 | 1.606 Hz / 30.0% / 9.615 |
  | 535 行（10.7 s） | **0.047 Hz** / 2.4% / 1.923 | 0.866 Hz / 11.2% / 15.385 |
  | 22 次抽样（22 s） | turn_rate(=R−L) 在 0.0 与 ±0.2308 之间 | 同 |
  ⇒ **left 不是硬锁**（存在 left 独立放电的窗口），而是与 right 一同**塌缩到 forward 的 1/50–1/100**（0.047–1.6 Hz vs 45–50 Hz），且**永不共放电**。"left 0.000 / right 3.85" 是其中一个**可复现的单包快照**（本次实测在 t=4026.18 精确重现：forward 46.15 / left 0.00 / right 3.85）。
- **未测量**：`mbon[1]`/`mbon[2]`（转向 MBON 通道，`model.py:1519-1520`）在 live `flow.json` 的 102 键中**未暴露**（只暴露 forward/jump/punch/dive/groundpound/longjump）⇒ "MBON→转向"的实际读数无法在线实测。作为上界参考：同 tick 内 punch 通道曾达 |0.932|，即 |mbon| ≤ 1 ⇒ 该路注入 ≤0.35 V/tick（**推算**，非实测）。
- **离线复现实测（E8b，live-like 转向驱动 + live-like 地板 0.88，demo fixture）**：

  | 臂 | 转向驱动（每侧另有 −0.25 boost 压制） | left | right | 备注 |
  |---|---|---|---|---|
  | H1 | `reflex_turn=+70`（right +0.25）+ OU | 0.0000 (0.00 Hz) | **0.0206 (1.03 Hz)** | 单侧 |
  | H2 | `reflex_turn=−70`（left +0.25）+ OU | **0.0428 (2.14 Hz)** | 0.0000 (0.00 Hz) | 单侧；与 H1 不镜像 |
  | H3 | H1 + CX gain 0.12 | 0.0000 | 0.0188 (0.94 Hz) | CX 只改变 ±0.1 Hz |
  | H4 | H2 + CX gain 0.12 | 0.0446 (2.23 Hz) | 0.0000 | 同上 |

  ⇒ 转向池只达到 **0.94–2.23 Hz**，且**每次只有一侧放电**（left×right 从不同时为正），H1/H2 的不镜像正对应 live 中"有时 left 先动、有时 right 先动"的窗口差异。**这离线复现了在线实测的形态**（0–2.3 Hz、严格互斥、比例随窗口翻转），且 **CX 的 ±0.12 推挽只带来 ±0.1 Hz 变化** ⇒ 症状可由"post-leak 地板 + 推挽驱动"完全解释，不需要"某侧通道损坏"这一假设。
- **结论**：转向池**并非"完全没有输入"**（代码上它接收连接组突触电流 × `gain_turn`，在线实测 `dopamine_gain.turn = 0.8474`），但所有输入的**结构**使其只能间歇点亮单侧：推挽对 + 双侧 −0.25 V/tick 的 boost 压制 + 无持续同号驱动。**H-B4 需要修正为**："输入存在但结构性不足，且被同一 boost 主动压制"。

### B5. 与既有假设的差异（更正清单）

| 既有表述 | 本次结论 |
|---|---|
| left 池"单侧锁死"在 0.000 Hz | **部分不成立**：是双池共同死区 + 推挽互斥 + 单调 boost 压制；left/right 比值随窗口在 0.054–0.62 之间变化，left 存在独立放电窗口 |
| CX 偏置在 anomaly_reflex 期间被清零 | **不成立**：池级注入未被清零；被覆盖的是输出（reflex 直写 control） |
| TurnAdaptation 疲劳"维持左池零放电" | **机制不成立**（疲劳只注入对手池），但**自锁结论成立**：双池静默 ⇒ 疲劳归零 ⇒ 无复活电流 |
| mb_mbon_forward ≈ 0.96 饱和导致 forward 贴顶 | **不成立**：该路径上限 8.2 Hz（§A2 解析 + 离线实测），在线实测负 MBON 时仍 46.15 Hz |
| R17 守卫"该触发而未触发" | 门限 0.98/0.99 高于实测平台 0.9633 ⇒ 结构性不触发；且即使触发也不解决贴顶 |

---

## 4. 附带实测：gate 阈值单位契约破裂（供 gate 相关任务参考；本任务未修改任何代码）

- **假设 H-C1**：`gate_jump` 阈值按 Hz 声明，却与 per-tick 比例字段比较 ⇒ 恒假。
- **代码位置（live WSL `main.py`，md5 `1ebcfcc7…`）**：

  | 行 | 代码 | 口径 |
  |---|---|---|
  | live `main.py:2417-2418` | `"gate_forward": control.forward_rate > _expl.get("gate_forward_threshold", 0.4)` | 比例(0..1) vs 阈值 0.4 / 实测配置 0.598 |
  | live `main.py:2419-2420` | `"gate_jump": control.jump_rate > _expl.get("gate_jump_threshold", 2.0)` | 比例(0..1) vs 阈值 2.0 / 实测配置 **3.082** ⇒ **恒假** |
  | live `main.py:2527` | `"jump_not_active": control.jump_rate < 0.04` | **同字段、比例口径** ⇒ 证明该字段确为比例 |
  | `telemetry.py:94` | `gate_jump = rates["jump"] > 2.` （rates 为 Hz，`telemetry.py:78`） | Hz(12.5–26.9) vs 2.0 Hz ⇒ **恒真** |

- **在线实测（同一 tick 联合采样 26 次）**：WS packet 的 `gate_jump = True` **26/26**；同一时刻 `flow.json` 的 `gate_jump = False` **26/26**；327 行窗口 WS `gate_jump = True` **327/327**。`flow.json` 同 tick 的 `jump_rate = 0.4615`（比例）、`forward_rate = 1.0`、`turn_rate = 0.0`。
- **声明侧（HEAD 5dba6fe）**：`skills/brain_tunable_params.json` 声明 `exploration.gate_jump_threshold` 默认 2.0、范围 [0.5, 4.0]，`gate_forward_threshold` 默认 0.4、范围 [0.1, 0.8] ⇒ **范围本身是"比例"域**，而文档（`docs/declared-not-implemented.md:43`）写作 "Jump pool firing rate gate (**Hz**)"，`skills/active_strategy.json:13` 又被 EVO/coach 写成 3.082 ⇒ 三处口径互斥。
- **工作区状态（溯源，非本任务改动）**：仓库 `main.py` 在本任务进行期间（15:00:18）被**其他成员**修改（+91 行），新增 `rate_per_tick_to_hz`/`gate_open_hz`/`*_rate_hz`/`gate_*_threshold_hz` 与 `tests/test_gate_units.py`，并把 registry 默认值改为 Hz 域（0.4→2.0、2.0→8.0）。本报告 §4 记录的是 **live/HEAD 口径**（缺陷现状），修复代码不在本任务范围内、本任务亦未验证其正确性。
- **残留分歧（供复核，仅记录）**：`telemetry.py:94` 仍用字面 `2.0` Hz，而新 registry 默认 `8.0` Hz、`active_strategy.json` 为 `3.082`（旧口径数值）⇒ 同键 `gate_jump` 的两路 producer（WS packet / flow.json）在新口径下**仍可能给出不同值**。
- **结论**：**H-C1 成立**：`gate_jump` 恒假的直接原因是"per-tick 比例 vs Hz 阈值"的比较；同一 flow.json 内 `jump_not_active`（0.04，比例）与 `gate_jump`（2.0，Hz）对同一字段使用两套单位，是契约破裂的现场证据。

---

## 5. 未测量 / 不可测（诚实清单）

1. **逐项电流分解**：live 端点不暴露 `v`、`_synaptic_buf`、`_turn_adapt`（left/right 疲劳）、`cx_bias`、`mbon[1..2]` ⇒ 无法给出"各项对 v 的百分比贡献"。本报告用"恒流地板求和 + 与 1.0 比较"给出**界**，并明确标注为推算。
2. **真实连接组离线复现不可能**：`fly64/.cache/malecns` 在本机不存在（`Test-Path` = False），live 大脑运行在 WSL `/root/fly64`。E2/E3'/E5/E6b/E7b/E8b 全部使用 `FlyModel(demo=True)`（4096 神经元合成 fixture，`model.py:721-754`），其绝对量级**不代表**真实 MaleCNS 连接组；这些实验证明的是**机制与算术**（限周期律、注入顺序、噪声量级、疲劳自锁、A/B 差分），不是 live 的精确数值。
3. **MBON turn 通道**：`mb_mbon_left/right` 或 `mbon[1]/[2]` 未进入 `flow.json`（102 键中只有 forward/jump/punch/dive/groundpound/longjump）⇒ §B4 中"该路注入 ≤0.35 V/tick"是**推算**。
4. **CX 输出幅度**：无 `cx_bias` 遥测键 ⇒ §B1 的"上限 ±0.12"来自代码，实际值未测量。
5. **连接组回投（`_synaptic_buf`）量级**：`w=0` 臂实测地板 0.88 → 25.00 Hz，而 live 观察到 34.6–50.0 Hz ⇒ 二者之差归因于**连接组回投电流**（`model.py:1581-1583` + `model.py:1573` 的 pathway gain），但该量的实际数值**未测量**（无遥测键）。把 25 → 34.6 Hz 的抬升归因于它是**推算**，不是实测。
6. **live 与仓库不一致**：live `main.py` md5 ≠ 仓库（并发修改中）⇒ main.py 行号一律以 live 副本为准；模型侧文件 md5 一致，行号对 live 成立。

---

## 6. 复现步骤

### 6.1 在线采样

```powershell
# 1) 13 行 pool 采样（4 次运行；需 live brain 在 8766 上）
python scripts/probe_pools.py
# 2) 长窗口统计 / 联合采样（WS + flow.json 同一时刻）
#    联合采样脚本（本次会话用过；等价内联写法）：
python -c "
import asyncio, json, struct, urllib.request, numpy as np
HEADER = struct.Struct('<4sI')
def flow():
    with urllib.request.urlopen('http://127.0.0.1:8765/flow.json', timeout=8) as r:
        return json.loads(r.read().decode())
async def main():
    import websockets
    F=[];M=[];G=[]
    async with websockets.connect('ws://127.0.0.1:8766/', max_size=None) as ws:
        for i in range(26):
            raw=await asyncio.wait_for(ws.recv(), timeout=10)
            _,L=HEADER.unpack_from(raw,0); meta=json.loads(raw[8:8+L]); r=meta['rows'][-1]
            f=flow(); F.append(r['forward']); M.append(f['mb_mbon_forward']); G.append((r['gate_jump'], f['gate_jump']))
    A=np.array(F);B=np.array(M)
    print('fwd mean/min/max', A.mean(), A.min(), A.max())
    print('mbon mean/min/max', B.mean(), B.min(), B.max())
    print('r =', np.corrcoef(A,B)[0,1])
    print('gate ws True %d/%d ; gate flow True %d/%d' % (sum(1 for a,b in G if a),len(G),sum(1 for a,b in G if b),len(G)))
asyncio.run(main())"
```

### 6.2 离线复现（本报告 E1–E8b）

```powershell
cd D:\codes\flygym\fly64
$env:PYTHONPATH='.'
..\.venv\Scripts\python.exe -u .tmp\t1_motor_pool_probe.py     # E1 E2（+ E3/E4 初版，已被取代）
..\.venv\Scripts\python.exe -u .tmp\t1_motor_pool_probe2.py    # E3'（OU-only）
..\.venv\Scripts\python.exe -u .tmp\t1_motor_pool_probe2b.py   # E5（注入顺序验证）
..\.venv\Scripts\python.exe -u .tmp\t1_motor_pool_probe3.py    # E6/E7/E8 初版（含 stuck-gated 混入，已被取代）
..\.venv\Scripts\python.exe -u .tmp\t1_motor_pool_probe3b.py   # E6b/E7b/E8b（本报告采用的 clean config）
```

脚本要点（**只读**：import 生产模块 + 运行时替换实例属性，不修改任何源文件）：
- E1：`TurnAdaptation().breakout_drive(stuck)` / `.counter_drive()` / 10 s 疲劳积分。
- E2：`FlyModel(demo=True)` 清空 `w`/`tonic`/OU/escape/CX/reflex，`mushroom` 换成常量 MBON stub，扫 `mb` 测 forward 占用率。
- E3'：同 E2 但保留 OU（`ou_sigma=0.12`、`ou_global_sigma=0.10`）、MBON=0，4000 tick 统计放电次数与 max v。
- E5：只保留**后漏电**常数电流（`_explore_bias` 固定、`_explore_commit_strength=0.10`），验证 `v_ss = I/(1−a)`。
- E6b/E7b/E8b：`w=0` 的 post-leak 地板账 + 逐项增删 + live-like 转向驱动。**clean config 的关键**：把 `stuck_duration=806.8` 同时镜射 live 的 `anomaly_state_name="oscillating"` 与 `mb_mbon_forward=0.96`，以关闭两个 stuck 门控的开环注入（EVO R29 pit 振荡 `model.py:1856-1861`/`1937-1940`、EVO R22 恢复 `model.py:1875-1877`）——否则实测会被这两项污染（part 3 的初版即因此失真，已弃用）。

### 6.3 原始输出（节选）

```
== E1  TurnAdaptation closed forms (code: model.py:345-392) ==
   fatigue=(0,0) stuck=   0.00 -> breakout_drive=0.000000  (counter_drive=(0.0, 0.0))
   fatigue=(0,0) stuck=  30.00 -> breakout_drive=0.000000  (counter_drive=(0.0, 0.0))
   fatigue=(0,0) stuck=  30.01 -> breakout_drive=0.087529  (counter_drive=(0.0, 0.0))
   fatigue=(0,0) stuck=  60.00 -> breakout_drive=0.175000  (counter_drive=(0.0, 0.0))
   fatigue=(0,0) stuck= 120.00 -> breakout_drive=0.350000  (counter_drive=(0.0, 0.0))
   fatigue=(0,0) stuck= 806.80 -> breakout_drive=0.500000  (counter_drive=(0.0, 0.0))
   after 10 s at live rates (L=0.00094 R=0.01732 per-tick): fatigue=(0.002728, 0.050274)
      counter_drive=(0.000982250667023475, 0.0180984910136666)  breakout(0)=0.001910  breakout(806.8)=0.501910
      both pools silent 10 s -> fatigue=(0.000000, 0.000000) counter_drive=(0.0, 0.0)

== E2  MBON-only drive: hard-reset LIF period (code: model.py:1518,1611,1879-1881) ==
   leak a=exp(-dt/tau_m)=0.818731 ; mbon_gain_forward=0.35 (constant, model.py:633-637)
   mb=0.4000 I=0.1400 v_ss(no-reset)=0.6323  analytic period=600.0 ticks ->  0.00 Hz
   mb=0.5500 I=0.1925 v_ss(no-reset)=0.8695  analytic period=600.0 ticks ->  0.00 Hz
   mb=0.6290 I=0.2201 v_ss(no-reset)=0.9943  analytic period=600.0 ticks ->  0.00 Hz
   mb=0.8000 I=0.2800 v_ss(no-reset)=1.2647  analytic period= 8.0 ticks ->  6.25 Hz
   mb=0.9600 I=0.3360 v_ss(no-reset)=1.5176  analytic period= 6.0 ticks ->  8.33 Hz
   mb=1.0000 I=0.3500 v_ss(no-reset)=1.5808  analytic period= 6.0 ticks ->  8.33 Hz
   -- measured on the real step() path (demo fixture, all other drive zeroed) --
   mb=0.4000 -> forward occupancy=0.0000  (0.00 Hz of the 50 Hz ceiling)
   mb=0.5500 -> forward occupancy=0.0000  (0.00 Hz of the 50 Hz ceiling)
   mb=0.6300 -> forward occupancy=0.0000  (0.00 Hz of the 50 Hz ceiling)
   mb=0.8000 -> forward occupancy=0.1280  (6.40 Hz of the 50 Hz ceiling)
   mb=0.9600 -> forward occupancy=0.1640  (8.20 Hz of the 50 Hz ceiling)
   mb=1.0000 -> forward occupancy=0.1640  (8.20 Hz of the 50 Hz ceiling)

== E3'  OU-ONLY drive on the steering pools (explore bias removed) ==
   ticks=4000 (80 s)  spike-counts={'forward': 0, 'left': 0, 'right': 0, 'jump': 0}  occupancy={'forward': 0.0, 'left': 0.0, 'right': 0.0, 'jump': 0.0}
   max v seen: left=0.3377 right=0.3114 forward=0.2746 V (threshold 1.0)
   （对照：ou_sigma=ou_global_sigma=0.0 时 400 tick 后所有池 max v = 0.00000，0 放电）

== E5  injection-order asymmetry (POST-leak constant drive) ==
   a = exp(-dt/tau_m) = 0.818731 ; pre-leak v_ss = I*a/(1-a) = 4.5167*I ; post-leak v_ss = I/(1-a) = 5.5167*I
   post-leak I=0.0750 -> predicted v_ss=0.4137 ; measured max v(right pool)=0.4137 ; spikes=0
   post-leak I=0.0500 -> predicted v_ss=0.2758 ; measured max v(right pool)=0.2758 ; spikes=0
   post-leak I=0.0200 -> predicted v_ss=0.1103 ; measured max v(right pool)=0.1103 ; spikes=0

== E6b  post-leak floor accounting (w=0, clean config, 600 ticks) ==
   F1 floor 0.88 = brk .50 + tonic .18 + reflex .20   fwd=0.5000 (25.00 Hz)  left=0.0000  right=0.0000  jump=0.2000
   F2 floor 0.38 (no brk)                            fwd=0.2500 (12.50 Hz)  left=0.0000  right=0.0000  jump=0.0000
   F3 floor 0.18 = tonic only                        fwd=0.0000 ( 0.00 Hz)  left=0.0000  right=0.0000  jump=0.0000
   F4 floor 0.68 = brk + tonic (no reflex)           fwd=0.5000 (25.00 Hz)  left=0.0000  right=0.0000  jump=0.2000
   F5 floor 1.03 = F1 + escape .15                   fwd=1.0000 (50.00 Hz)  left=0.0800  right=0.0500  jump=0.3350
   F6 floor 0.88 + OU                                fwd=0.5000 (25.00 Hz)  left=0.0000  right=0.0000  jump=0.1981
   F7 floor 0.88 + OU + mb=+0.96                     fwd=1.0000 (50.00 Hz)  left=0.0000  right=0.0000  jump=0.1981

== E7b  marginal effect of the MBON path on the same floor ==
   G1 floor 0.88, mb=0.00          fwd=0.5000 (25.00 Hz)
   G2 floor 0.88, mb=+0.96         fwd=1.0000 (50.00 Hz)
   G3 floor 0.88, mb=-0.89         fwd=0.5000 (25.00 Hz)
   G4 floor 0.88, mb=+0.96, OU on  fwd=1.0000 (50.00 Hz)

== E8b  steering pools, live-like reflexive turn drive ==
   H1 reflex_turn=+70   fwd=0.5000 (25.00 Hz)  left=0.0000 (0.00 Hz)  right=0.0206 (1.03 Hz)
   H2 reflex_turn=-70   fwd=0.5000 (25.00 Hz)  left=0.0428 (2.14 Hz)  right=0.0000 (0.00 Hz)
   H3 H1 + CX gain 0.12 fwd=0.5000 (25.00 Hz)  left=0.0000 (0.00 Hz)  right=0.0188 (0.94 Hz)
   H4 H2 + CX gain 0.12 fwd=0.5000 (25.00 Hz)  left=0.0446 (2.23 Hz)  right=0.0000 (0.00 Hz)
```

---

## 7. 结论对修复方向的约束（**非实现方案**，仅列出证据导出的硬约束）

1. **只调 MBON / `mbon_gain_forward` / R17 门限不可能修好 forward 贴顶**：该路径在真实代码路径上的上限是 8.2 Hz（=50 Hz 天花板的 16.4%，§A2 离线实测 + 在线反证）。
2. **必须处理 post-leak 恒流地板**：`breakout_drive` 的 stuck boost 与疲劳水平**无关**（`model.py:389-391`）、`reflex_forward` **粘滞不复位**（live `main.py:1550-1552`）、且 post-leak 注入**没有任何占用率负反馈**（§A4 的 15 个写点穷举）。
3. **steering 池要恢复动态范围，需要在"推挽对"之外引入至少一路同号/持续/可单侧独立的驱动，或提供与池放电无关的去抑制路径**；否则双池静默时 `TurnAdaptation` 无法自愈（§B2），OU 也不够（§B3）。
4. **单位契约需唯一化**：同一 `control.*_rate` 字段已同时以两种口径存在于同一 flow.json（`gate_*` 用 Hz、`jump_not_active` 用比例），且 `telemetry.py:94` 与 main.py/registry 的阈值来源不同（§4 残留分歧）。
   - **§7.4 范围映射（t8 补记）**：本条属 **t3 的 gate 单位契约任务**；t2/t8 的改动只在 `fly64/model.py` 的运动池注入与占用率反馈（MBON/tonic/escape/breakout/reflex 五腿 + 标志到期），**未读取、未写入、也未改动任何 gate 字段、阈值或 `main.py`/`telemetry.py`/`brain_tunable_params.json` 中的单位逻辑**，因此与 t3 的变更在文件与语义上都不冲突（唯一交点是 `main.py`，已明确划归 t7 合并）。
5. **任何只改"阈值/门限"的修复都无法改变 §A5 的 0.88 V/tick 地板**：`breakout(0.500) + tonic(0.180) + reflex(0.200)` 是**常量级**注入，与阈值无关。

---

## 8. 修复对照（t7 集成：问题 → 修复 → 验证证据）

本节由 **t7（集成）** 追加：把 t2/t8（运动池）与 t3（gate 单位）两条实现线合并为一个可交付整体，记录「问题 → 修复 → 验证证据」、集成回归结果、残留项与**待用户确认的部署步骤**（t7 未执行任何部署）。

### 8.1 两条实现线的合并状态（无冲突核对）

| 文件 | 变更线 | 状态 | 证据 |
|---|---|---|---|
| `fly64/fly64/model.py` | t2 + t8 | 已合并（+399/−28） | 无任何 `gate_*` 标识符（0 处匹配）⇒ 未与 t3 交叠 |
| `fly64/fly64/mushroom_body.py` | 未改动 | 保持 HEAD | R17 守卫 0.98/0.99 契约未动（t1 §A3 已证其非杠杆） |
| `fly64/fly64/main.py` | t3 | 已合并（+95） | `rate_per_tick_to_hz()` / `gate_open_hz()` 单点换算与比较 |
| `fly64/skills/brain_tunable_params.json` | t3 | 已合并（16 行） | `gate_forward_threshold` 0.4..8.0/默认 2.0；`gate_jump_threshold` 2.0..20.0/默认 8.0（Hz） |
| `fly64/docs/declared-not-implemented.md` | t3 | 已合并 | §2 未接线项 0 条；§2b 登记两个 gate pid 为 implemented |
| `fly64/contract_registry.json` | **t7** | 本文档同步更新（v1.0.0 → v1.1.0） | `rate_gate_group` + `unit_contract` + `RULE-19k` |
| `fly64/tests/test_gate_units.py` | t3 | 新增 | 单位/边界/可达性 PIN |
| `fly64/tests/test_motor_pool_dynamics.py` | t2 + t8 | 新增（22 测试） | 占用率/负反馈/到期/写点契约 |

**结论**：两条线在**不同文件与不同语义层**（model.py 运动池注入 vs main.py 契约层）上共存，唯一文件级交点是 `main.py`（t3 唯一改动者，t2/t8 未触碰），因此 **无冲突、无互相覆盖**。

### 8.2 问题 → 修复 → 验证证据（逐条）

| # | 问题（t1 实测） | 修复 | 验证证据（t7 复核） |
|---|---|---|---|
| F-A | forward 池钉在 0.92–1.00（46.15–50.00 Hz），与 MBON 无关；post-leak 地板 0.88 V/tick | t2：占用率 homeostat（MBON/tonic）；t8：扩到 escape 两腿 + breakout 前向腿，并加**聚合上限 0.20 V/tick** | live-like escape 档 forward 占用率 **0.3890 / 0.4282**（scale 0.00/0.02）< 0.50；同 harness 关闭 t8 机构（t2 态）**0.7421 / 0.8266（37.1/41.3 Hz）**；osc=1 臂 **0.4090**；MBON 扫描严格单调 |
| F-B | steering left 0.000 / right 0.000 Hz（对称 −0.25 V/tick 钳位 + 疲劳自锁） | t8：`breakout_split()` 让双侧钳位乘真实交替量（静默飞行 → 0），前向突破保留 0.25 下限 | ±70 定向驱动下 left/right 均非零（t8：249/250、199/250）；t4 独立复现 left 驱动→left 0.2502、right 驱动→right 0.2572（pre 0.0452/0.0621）；共放电不再严格互斥 |
| F-C | `reflex_forward` 粘滞不复位（0.20 V/tick 永久注入） | t8：`__setattr__` 写戳 + `reflex_flag_scale()`（ttl 0.30 s / τ 0.20 s）+ 该腿同时受增益与上限约束 | 一次性写入 eff 前 15 tick=70.0 → 其后 3.97；age 15/25/135 tick = 1.0/0.3679/0.0；每 tick 刷新恒 70；raw 标志永不被模型改写（=70） |
| F-D | `_last_disp_x/_z` 全仓无写入点 ⇒ escape accumulator 被无条件推到上限 | t8：无位移信号时回落到 base(0.15)（有信号仍可 ramp，有进度不 ramp） | 无信号 0.2000→0.1500（`_disp_signal_available=False`）；注入 (0,0) → 0.2000；注入 (5,0) → 0.1500 |
| F-E | `gate_jump` 恒假：per-tick 比例(0..1) 与 Hz 阈值(2.0/3.082) 比较；同一 tick WS 包 True 与 flow.json False 并存 | t3：`rate_per_tick_to_hz()` 单点换算 + `gate_open_hz()` 同量纲严格 `>`；发布 `*_rate_hz` / `gate_*_threshold_hz`；schema 改为 Hz | t6 用 AST 执行生产表达式：per-tick 0.276→13.8 Hz > 8.0 → **True**（修复前恒假）；0.16→恰好 8.0 → **False**（边界闭合）；t7 审计：`main.py` 中残留的 per-tick 比较 0 处 |
| F-F | 契约登记缺失：flow.json 的 Hz 键与新单位语义未登记 | t7：`contract_registry.json` v1.1.0 增 `rate_gate_group`（9 键）、`flow_json.unit_contract`（per-tick/Hh 键、换算点、比较点、阈值单位、残留分歧）、`RULE-19k` 零容忍条目 | t7 审计 **21/21 PASS**：注册的 9 键在 producer 中全部存在、`*_hz` 键在 registry 与 producer 双侧存在、fallback 与 schema 默认一致（2.0/8.0）、maxima < Nyquist、docs §2b 一致、telemetry 分歧已在 `known_divergence` 登记 |

### 8.3 集成回归（t7 实测）

| verify 命令 | 结果 |
|---|---|
| `pytest tests/test_motor_pool_dynamics.py tests/test_gate_units.py tests/test_strategy_key_contract.py -q` | **44 passed**，exit 0（t9 复核 64 passed 的另一组合口径为 `+test_mushroom_body` 等） |
| `pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_cpg_priority.py tests/test_dashboard_protocol.py -q` | **66 passed**，exit 0 |
| `pytest tests/test_phase6_fitness_inputs.py tests/test_memory.py tests/test_optic_flow.py --deselect …test_flow_computation_performance -q` | **148 passed, 1 deselected**，exit 0 |

全量套件与**规则 20 门禁**（`scripts/check_regressions.py`，自带套件运行，非转述）：

```
REGRESSION CHECK  (baseline win32, 36 entries)
  failing now      : 37
  still failing    : 35 (known)
  NEW failures     : 2
  baseline entries that now PASS : 1
!!! NEW FAILURES (a regression, or an unclassified pre-existing one)
```
退出码 **1**。2 条 NEW 全部是 `tests/test_plugin_mhr.py`（`TestPluginStructure::test_manifest_valid`、`TestCycle::test_frame_captured_into_request`），**同一个根因**：两处断言都要求 LLM 型号字符串 `glm-5v-turbo`，而**已提交**的 `fly64/plugin/manifest.json` 与插件产出的请求里是 `qwen3.8-27b-uncensored`（`AssertionError: assert 'qwen3.8-27b-uncensored' == 'glm-5v-turbo'`，测试文件 45/169 行）。

**归因（与本轮两条实现线无关，非本轮引入）**：
- **HEAD 即失败（A/B 实测）**：把 `git show HEAD:fly64/tests/test_plugin_mhr.py` 原样取出运行 → **同样 2 failed / 44 passed**，与工作区版本逐条一致 ⇒ 失败不来自工作区对该测试文件的未提交修改，也不是本轮引入；
- 该测试文件**不 import** `fly64.model`（`fly64.model|FlyModel` 匹配数 = 0），t2/t3/t8 的 diff 面完全不含 `fly64/plugin/**`；
- 基线文件记录于 `2026-09-23T01:09`，而 `plugin/manifest.json` 的 GLM→本地 vLLM 型号切换是其后提交的 `78b3175` ⇒ 这是**基线陈旧**（baseline staleness），不是行为回归；
- 另有 1 条基线条目转为通过（`tests/test_fix_executor.py::TestParseFixTemplate::test_manual_fallback`，他人并发改动所致）。

**建议处置**（均不在 t7 scope 内，需归属方执行）：① plugin/LLM 线把测试期望值改为 manifest 的实际型号（或反之统一），② 或基线归属方用 `python scripts/check_regressions.py --update` 将该 2 条以 `cause=test-drift`+证据 note 登记；在二者之一完成前，规则 20 门禁保持 **exit 1**。

`scripts/contract_gate.py` 当前 **FAIL（8 blocker，全部 ZT-1）**：8 条全部来自 `audit_contract_pairs.py` 对 `skills/scene_strategy_bindings.json` 与 `plugin/.consult_{request,response}.json` 的 DEAD-WRITE/SILENT-DEFAULT 判定，**与 registry/单位契约无关**；A/B 证明：registry 相关检查（ZT-5 / bridge / completeness）对 **HEAD registry 与工作区 registry 均为 0 findings**，且 ZT-1 由审计产物的行数（8 行）直接得出 ⇒ 该 FAIL 为**预存状态**，t7 未引入也未掩盖。

`scripts/contract_gate.py` 当前 **FAIL（8 blocker，全部 ZT-1）**：8 条全部来自 `audit_contract_pairs.py` 对 `skills/scene_strategy_bindings.json` 与 `plugin/.consult_{request,response}.json` 的 DEAD-WRITE/SILENT-DEFAULT 判定，**与 registry/单位契约无关**；A/B 证明：registry 相关检查（ZT-5 / bridge / completeness）对 **HEAD registry 与工作区 registry 均为 0 findings**，且 ZT-1 由审计产物的行数（8 行）直接得出 ⇒ 该 FAIL 为**预存状态**，t7 未引入也未掩盖。

### 8.4 残留项（不阻塞交付，已登记）

| id | 级别 | 内容 | 归属 |
|---|---|---|---|
| U1 | high | 活体 `reflex_forward` 仍粘滞（main.py 三处写入无 `=0`）；t8 的到期把最坏占用率压到 0.4989（非 50 Hz），但显式清零更干净 | main.py 线 / t3 或后续 |
| N2 | medium | aux 预算按 step 顺序分配：escape 模式下 breakout 前向腿可能被饿死（`_fwd_brk_applied`=0.0000 而 turn 钳位照付，自限、转向池仍活） | model.py 后续小任务 |
| N3 | low | (e) 写点审计按 `self.v[self.forward]` 枚举 16 处，未覆盖 OU 的 `motor_nodes` 切片写点（切片感知枚举 20 处）；gated 亚阈判据为 `< 1.0` | 后续小任务 |
| t6-F1 | medium | 默认阈值 8.0 Hz（活体 3.082 Hz）低于活体 jump 池 12.5–26.9 Hz ⇒ `gate_jump` 在观测域恒真（信号不携带信息；PIN 只覆盖合成闭合态） | 阈值标定 / main.py 线 |
| t6-F2 / t4-U3 | medium | `telemetry.py:93-94` 的 F643 gate_jump 仍用自带字面 2.0 Hz，与 schema（8.0）不同源 ⇒ 两路 producer 在 jump∈(2,8) Hz 相反 | telemetry.py 线 |
| t6-F3 | medium | `skills/active_strategy.json` 的旧 per-tick 域值 0.598/3.082 被静默重解释为 Hz（无区间校验） | skills/main.py 线 |
| t6-F6 | low | `plugin/scene_context.py` 从 memory.json 死读 `forward_rate/jump_rate` 却渲染成 “Hz” 进 coach prompt | plugin 线 |
| F6 | medium | 游戏级 stuck 时长未测（本机无桥接）；控制级已证等价（两者 raw_y=70 满推力），post 侧活体序列待部署 | 部署后验收 |
| — | — | 本轮**未做任何部署**：WSL `/root/fly64` 仍是修复前代码（活体 forward 恒 50 Hz），因此**活体验收尚未成立** | 待用户确认 |

### 8.5 待用户确认的部署步骤（t7 产出，**未执行**）

> 规则 9：部署与重启需**显式用户确认**。本节只是可执行清单，t7 未运行其中任何命令；规则 12 的方向是 Windows→WSL 下发修复，证据文件（`skills/coach_outcomes.jsonl` 等）**禁止**反向推送。

1. **记录现状（回滚锚点）**：`wsl -d Ubuntu-22.04 -- md5sum /root/fly64/fly64/model.py /root/fly64/fly64/main.py /root/fly64/skills/brain_tunable_params.json`；确认 `model.py` 仍是 `9cb829ca…`（修复前）。
2. **同步代码（Windows → WSL）**：`wsl -d Ubuntu-22.04 -- rsync -a /mnt/d/codes/flygym/fly64/fly64/{model.py,main.py} /root/fly64/fly64/ && rsync -a /mnt/d/codes/flygym/fly64/skills/brain_tunable_params.json /root/fly64/skills/`（只同步这两条实现线的文件；`contract_registry.json`/docs 不参与运行）。
3. **重启脑模型 + SM64**：`wsl -d Ubuntu-22.04 -- bash /root/fly64/scripts/launch_full.sh`（或 `scripts/consolidate.sh` 智能重启，规则 8）。
4. **活体复测（探针）**：`python scripts/probe_pools.py`（≥12 个 packet）记录 `forward/left/right/jump/visual` 的 Hz 与波动；并 `GET http://127.0.0.1:8765/flow.json` 检查出现 `forward_rate_hz / turn_rate_hz / jump_rate_hz / gate_*_threshold_hz`。
5. **验收判据（建议，供用户确认）**：forward 稳态占用率 **< 0.5**（目标 0.39–0.43，即 ≈20–22 Hz；修复前恒 50 Hz）；定向驱动下 left/right **均非零**（不再单侧 0.000 Hz）；`/flow.json` 的 `gate_jump` 与同一 tick 的 WS packet 口径**同量纲**（注意 t6-F2 的 2.0 vs 8.0 Hz 残留分歧）；复采 `stuck_duration / disp_60s` 作为 post 侧活体序列（pre 侧：stuck 1758.7→1760.6 s、disp_60s 38.5–419.3、forward_rate 0.65–1.00）。
6. **回滚预案**：用第 1 步的 md5 备份还原 `model.py`/`main.py`/`brain_tunable_params.json` 并重启；活体异常（健康分下降、卡死时长劣化）时立即回滚。

