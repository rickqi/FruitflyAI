# t4 独立验证报告 —— 运动池动态范围恢复与 gate 可达性

- **任务**：t4 独立验证：运动池动态范围恢复与 gate 可达性（含独立探针与回归核验）
- **被验证对象**：t2（`fly64/fly64/model.py` + `fly64/tests/test_motor_pool_dynamics.py`）、t3（`fly64/fly64/main.py` + `fly64/skills/brain_tunable_params.json` + `fly64/docs/declared-not-implemented.md` + `fly64/tests/test_gate_units.py`）
- **验证者产出**：
  - `fly64/scripts/verify_motor_pools.py`（独立验证脚本，29 项检查，`--json` 机器可读）
  - `scripts/verify_motor_pools.py`（工作区根入口 shim，`runpy` 转发到上面同一个文件，无重复逻辑）
  - 本报告
- **未改动任何被验证的生产代码**：只 import 生产模块；"修复前"分支用**实例级**运行时替换重建（见 §2.2），不写任何 `fly64/fly64/**` 文件。

---

## 0. 结论速览

| # | 验收项 | 结论 | 关键量化证据 |
|---|---|---|---|
| 1 | 验证方法独立于实现者（自建探针/仿真，不复用 t2/t3 测试断言作为唯一证据） | **PASS** | 29 项检查全部由 `verify_motor_pools.py` 自己的 fixture/断言产生；t2/t3 的测试文件仅被**运行**（作为回归门），未作为证据引用 |
| 2 | 独立复现 t1 限周期律 `T = min{n≥1: I_eff(1-a^n)/(1-a) ≥ 1}`（`I_eff = a·I`，`a = 0.8187`）≥3 档；独立测出修复前 post-leak 地板（t1: 0.88 V/tick） | **PASS** | 7 档注入全覆盖，解析 vs 实测最大偏差 **0.00051**；地板独立测得 **0.8800 V/tick**，实测 max v = **0.8800 V**，限周期律预测 T=2 → 25.00 Hz，实测 0.5004 → **25.02 Hz** |
| 3 | 修复后 forward 占用率不再贴顶（<50% 上限）且对驱动力单调；steering 两池 live-like 下各自可非零；给出共放电明确结论 | **PASS**（边界余量仅 0.0011，见 §5.4） | live-like 全档 post 最大占用率 **0.4989（24.94 Hz）**，pre 同档 **1.0000（50.00 Hz）**；单调性严格成立；left 驱动→left 0.2502、right 驱动→right 0.2572（baseline 0.000 Hz）；**共放电：修复前 0 次，修复后 94/95 tick**（明确结论见 §6.3） |
| 4 | 核验 t2 是否满足 t1 §7 硬约束 | **PASS（3 项满足 + 1 项未闭合，已量化）** | breakout boost 已按疲劳 osc 门控（osc=0 → turn clamp 0.0000）；R17/`mushroom_body.py` 未改、`mbon_gain_forward` 仍 0.35、mb=0 时占用率仍 0.3336；steering 复活靠**删除对称钳位**而非新增单侧常量（diff 仅 2 行 `-=`）；**未闭合**：`reflex_forward` 仍粘滞（§7.2 的 (b) 项，属 main.py/t7 范围，t2 只界定了其后果） |
| 5 | gate 单位唯一化核验 + 残留分歧报告 | **PASS** | flow.json 两侧同量纲（`gate_open_hz(_forward_rate_hz, _gate_forward_hz)`，换算单次 `rate_per_tick_to_hz(…, _rate_dt)`）；健康 jump 池 0.2308/tick = **11.54 Hz > 8.0 Hz → gate_jump=True**；残留分歧 2 项已列（telemetry 阈值未同源、`jump_not_active` 仍 per-tick——后者自洽，不算缺陷） |
| 6 | 回归：verify 命令全部退出码 0；对基线核验无新增失败 | **PASS（附 2 项非 t2/t3 新增失败，已归因）** | cmd1 exit 0（29/29 passed）；cmd2 exit 0（25 passed）；cmd3 exit 0（64 passed）；全量套件 37 failed / 1254 passed vs 基线 36 条 → **2 项 NEW**，已证明与本任务无关（§9.3） |
| 7 | 报告区分离线仿真证据与活体实测证据；活体未部署新版时不得声称已验证 | **PASS** | 活体 `model.py` md5 = `9cb829ca…` = git HEAD = **修复前**，故活体一律标注为 **BASELINE / 未验证修复**（§10） |

**验证脚本退出码：0（29 passed / 0 failed，258.6 s）。**

---

## 1. 验证方法与"与实现者不同源"的具体含义

实现者的证据来自 `tests/test_motor_pool_dynamics.py`（10 例）与 `tests/test_gate_units.py`（12 例）。本验证**不引用**这些文件的断言作为证据，而是：

| 问题 | 实现者方法 | 本验证方法（不同源） |
|---|---|---|
| fixture | `CONNECTOME_SCALE=0.02` 缩放连接组，`mb` 扫 0…1，400 tick / warm 150 | **两个独立构型**：(a) `w=0`（去连接组回投，隔离 post-leak 地板，与 t1 §A5/E6b 同构型以可比）；(b) `w_scale ∈ {0.02, 1.0}` 缩放扫描（暴露实现者未报告的 fixture 极限） |
| 限周期律 | 断言"占用率 < 0.6 且单调" | **从零实现** `law_period()` 闭式（几何级数），对 7 档注入逐点比对 1/T，并单独验证前/后漏电两条分支的稳态（`I·a/(1-a)` vs `I/(1-a)`） |
| 修复前基线 | 未重建（只引用 t1 的叙述） | **实例级重建**（3 行运行时替换）+ 用 `git show HEAD` 的源码文本钉住该重建（§2.2），再在同一 harness/同一 seed 下跑 pre/post |
| steering | 交替 `reflex_turn=±70`（每 100 tick 翻转），断言"两侧都活跃" | **分别**给 left/right 单侧恒定驱动；另加 **null 试验**：把 t1 已存在的疲劳 `counter_drive` 置零（实例旋钮），观察未驱动侧是否塌陷 |
| 共放电 | 未报告 | 逐 tick 统计 `left>0 and right>0`，并给出 pre/post 与"切断疲劳耦合"三组对照 |
| gate | AST 扫描 + 断言 | 独立 AST 扫描（自写 `_flow_json_literals`/`_unname`）+ **真实池速率**跑出 gate 可达性 + 独立列出所有 `control.*_rate` 比较点 |
| 回归 | t2/t3 各自的 10+12 例 | 3 条合约命令（原样执行）+ **全量套件**对照 `tests/known_failures.win32.json` |

**证据分级（沿用 t1 的纪律）**：
- `离线仿真证据`：`FlyModel(demo=True)`（4096 神经元合成 fixture）上的确定性 `step()`。**只证明机制与算术**，绝对量级不代表真实 MaleCNS 连接组（t1 §5.2；本机 `fly64/.cache/malecns` 不存在，报告 JSON 里 `malecns_cache_present: false`）。
- `代码证据`：file:line + AST/文本扫描 + `git show HEAD` / `git diff`。
- `活体实测证据`：WS `ws://127.0.0.1:8766/` F643 packet + HTTP `http://127.0.0.1:8765/flow.json`（**只读**）。本轮活体跑的是**修复前**代码，因此只作 baseline 复测。

---

## 2. Provenance（可复现的溯源）

### 2.1 指纹

| 文件 | git HEAD (`5dba6fe9…`) | 工作区（被验证对象） | live WSL `/root/fly64` |
|---|---|---|---|
| `fly64/fly64/model.py` | `9cb829ca7c3d3985396e23daa94142d8` | `a2d4242d29534351297da7472e8e88f9` | `9cb829ca…`（= HEAD，**修复前**） |
| `fly64/fly64/main.py` | `7ed43e1cc3acbd3ab33d4520dd12086d` | `348283f05e6deb7131b032fe721fb35d` | `1ebcfcc7bbb5f1f3d4c6e79928da05f4`（**修复前**） |
| `fly64/fly64/telemetry.py` | `995074d9d9d19f78f02c9c628ac4bf4c` | 同 HEAD | 同 HEAD |
| `fly64/fly64/mushroom_body.py` | `12693745e8b29650154efd3f1770fcde` | 同 HEAD（**t2 未改**） | — |
| `fly64/skills/brain_tunable_params.json` | `39e23cbe6556b6723a735abbdf6010ac` | `5d2f21e9bc1d39b2621bf1bad9e32839` | `47e6d0739e50bf80c9b5ec7fa45bf59b`（**修复前**） |

- 验证对象是**工作区未提交状态**（`git status`：`M fly64/fly64/model.py`、`M fly64/fly64/main.py`、`M fly64/skills/brain_tunable_params.json`，`?? fly64/tests/test_motor_pool_dynamics.py`、`?? fly64/tests/test_gate_units.py`）。工作区 `model.py` md5 在验证开始与结束时一致（`a2d4242d…`）。
- **live 的 `model.py` 与 git HEAD 逐字节相同**（md5 相同）⇒ 活体进程跑的就是修复前版本，t1 关于"model.py 行号对 live 成立"的结论在本轮仍然成立。

### 2.2 修复前分支的重建（关键方法）

t2 对 `step()` 只改了三条 limb：

1. `v[forward] += mbon[0]·mbon_gain_forward`（现在再乘 `_fwd_homeo_gain`）→ model.py:1665-1666
2. forward 池 tonic limb（现在按同一 gain 缩放）→ model.py:1770-1772
3. R16 breakout 注入（现在 `breakout_split()` 拆分）→ model.py:1988-1996

重建方式：实例级替换 `forward_homeo_gain → 1.0`（同时中和 1、2）与 `breakout_split → (raw, raw·0.5, raw)`（恢复 3；`breakout_drive()` 本身 t2 未改，直接调用生产函数）。该重建被**源码钉住**（脚本 `prefix_emulation_pinned_to_head`）：

```
prov {'git_head_rc': 0, 'head_has_unsplit_breakout': True,
      'head_has_bare_mbon_injection': True, 'head_lacks_breakout_split': True}
```

即 HEAD 的 `model.py` 中确实存在 `self.v[self.forward] += _brk`、`self.v[self.turn_left] -= _brk * 0.5`、`self.v[self.turn_right] -= _brk * 0.5` 与裸的 `mbon[0] * self.mbon_gain_forward`，且没有 `def breakout_split`。

### 2.3 受控构型（每个 arm 都显式固定无关驱动）

`w=0`（去连接组回投）、`visual_connected=False`、`_explore_bias=0` 且 `_explore_commit_timer=10^9`（冻结探索方向惯性）、`mb_mbon_forward=0.96`（**钉住** EVO R22 `stuck>30 and mb<0.05` 与 R29 pit `stuck>60 and mb<0.2 and state∈{fallen,idle}` 两条既有开环注入器）、`anomaly_state_name="oscillating"`（live 观测值）、`escape_mode=False`、`scene_danger=0`、`restlessness=0`。MBON 注入量经 `_StubMushroom` 独立扫描。

> 说明：t1 的 clean config 用同样手法关闭这两条注入器（t1 §6.2 脚本要点）。本报告 §5 的"brk-only"臂与 t1 §E6b 的 F1/F2 可直接对比。

---

## 3. 证据 A：限周期律独立复现（验收 #2）

`a = exp(-dt/τm) = exp(-0.02/0.1) = 0.818731`；`mbon_gain_forward = 0.35`（HEAD 与工作区相同）。
`I_eff = a·I`（前漏电注入；MBON 在漏电之前，model.py:1665 < 1762），`T = min{n≥1: I_eff(1-a^n)/(1-a) ≥ 1}`。

```
--- law a=0.818731 gain=0.350 worst=0.00051
  mb=-0.80 I=-0.2800 Ieff=-0.2292 T=None  occ_th=0.0000 occ_meas=0.0000 hz=0.00 maxv=0.0000 pred=-1.2647
  mb=+0.40 I= 0.1400 Ieff= 0.1146 T=None  occ_th=0.0000 occ_meas=0.0000 hz=0.00 maxv=0.6323 pred=0.6323
  mb=+0.55 I= 0.1925 Ieff= 0.1576 T=None  occ_th=0.0000 occ_meas=0.0000 hz=0.00 maxv=0.8695 pred=0.8695
  mb=+0.63 I= 0.2205 Ieff= 0.1805 T=None  occ_th=0.0000 occ_meas=0.0000 hz=0.00 maxv=0.9959 pred=0.9959
  mb=+0.80 I= 0.2800 Ieff= 0.2292 T=8     occ_th=0.1250 occ_meas=0.1255 hz=6.28 maxv=0.9528 pred=1.2647
  mb=+0.96 I= 0.3360 Ieff= 0.2751 T=6     occ_th=0.1667 occ_meas=0.1668 hz=8.34 maxv=0.9593 pred=1.5176
  mb=+1.00 I= 0.3500 Ieff= 0.2866 T=6     occ_th=0.1667 occ_meas=0.1668 hz=8.34 maxv=0.9993 pred=1.5808
  post-leak levels [(0.02,0.1103,0.1103),(0.05,0.2758,0.2758),(0.075,0.4137,0.4137),(0.12,0.6620,0.6620)]
  t1 cmp {'t1_mb_0.80_occ': 0.128, 't1_mb_0.96_occ': 0.164,
          'this_mb_0.80_occ': 0.12551, 'this_mb_0.96_occ': 0.16680}
```

**与 t1 的一致/偏差**：

| 量 | t1 报告 | 本验证实测 | 偏差 |
|---|---|---|---|
| `mb=0.80` forward 占用率 | 0.1280（6.40 Hz） | 0.1255（6.28 Hz） | −1.9%（0.0025） |
| `mb=0.96` forward 占用率 | 0.1640（8.20 Hz） | 0.1668（8.34 Hz） | +1.7%（0.0028） |
| `mb=0.96` 解析周期 | T=6（8.33 Hz） | T=6（8.34 Hz） | 一致 |
| 前漏电稳态 | `I·a/(1-a)` | 0.6323 / 0.8695 / 0.9959（逐位吻合） | 一致 |
| 后漏电稳态 | `I/(1-a)` | 4 档逐位吻合（0.1103/0.2758/0.4137/0.6620） | 一致 |
| 注入顺序惩罚因子 | 1/a = 1.22× | 1.2214× | 一致 |
| 覆盖档位 | 6 档 | **7 档前漏电 + 4 档后漏电** | 超出要求（≥3） |

解析 vs 实测最大偏差 `worst_delta = 0.00051`（≈ 0.3% of 1/T）。

**结论**：t1 的核心定量结论（限周期律 + 前漏电 `a·I` + MBON 单路上限 ~8.2 Hz）在本验证中**逐点独立复现**，偏差 < 2%。

---

## 4. 证据 B：修复前 post-leak 地板 = 0.88 V/tick（验收 #2 后半）

```
floor 0.8800 (brk 0.500 tonic 0.180 reflex 0.2000) law T=2 occ 0.5000
      preocc 0.5004  pre_maxv 0.8800  postocc 0.3336
```

推导全部来自**生产代码 / 生产函数**（不是引用 t1 文字）：

1. `TurnAdaptation().breakout_drive(stuck_duration=806.8) = 0.500000`
   （`min(0.50, 0.35 × 806.8/120) = 0.50` 顶到上限；`breakout_drive` t2 未改）
2. `FlyModel(demo=True).tonic_current = 0.180`
3. forward reflex limb：从源码正则读出 `min(0.20, self.reflex_forward * 0.003)`（model.py:1856），
   代入 live 粘滞值 70 → `min(0.20, 0.21) = 0.2000`
4. **合计 = 0.8800 V/tick**（t1 报 0.88）

**实测验证（重建修复前路径，`w=0`，OU 关，600 s 级 190 tick，warm 95）**：

| arm | 修复前 forward | 修复后 forward |
|---|---|---|
| `brk only`（0.500） | 0.3336（16.68 Hz，T=3 ✓ 律） | 0.0000（0.00 Hz） |
| `brk + tonic`（0.680） | 0.5004（25.02 Hz，T=2 ✓ 律） | 0.2000（10.00 Hz） |
| `brk + tonic + sticky reflex`（**0.880**） | **0.5004（25.02 Hz）** | 0.3336（16.68 Hz） |
| 同上 + MBON 平台 + OU（live-like） | 0.5004（25.02 Hz） | 0.3336（16.68 Hz） |
| 同上 `max v`（forward 池） | **0.8800 V**（解析 0.8800） | — |

⇒ **地板量级与"单靠地板即 25 Hz 限周期、不贴顶但也不停摆"两条结论均被独立实测确认**（与 t1 §E6b F1 的 0.5000/25.00 Hz、max v 0.880 一致）。

---

## 5. 证据 C：修复后 forward 动态范围（验收 #3）

### 5.1 live-like 构型的 MBON 扫描（`w=0`、`stuck=806.8 s`、粘滞 `reflex_forward=70`、`tonic=0.18`、OU 开）

```
--- forward range cfg {'stuck':806.8,'reflex_forward':70,'tonic':0.18,'ou':True,'w_scale':0.0,'mirror_mb':0.96}
  POST mb=-1.0000 occ=0.1230 hz= 6.15 gain=1.000 tonic=0.1800
  POST mb=-0.8861 occ=0.1589 hz= 7.94 gain=1.000 tonic=0.1800
  POST mb=+0.0000 occ=0.3336 hz=16.68 gain=0.908 tonic=0.1635
  POST mb=+0.2384 occ=0.3692 hz=18.46 gain=0.828 tonic=0.1491
  POST mb=+0.5000 occ=0.4355 hz=21.78 gain=0.663 tonic=0.1193
  POST mb=+0.7500 occ=0.4761 hz=23.81 gain=0.561 tonic=0.1010
  POST mb=+0.9633 occ=0.4972 hz=24.86 gain=0.509 tonic=0.0916   <- live 平台
  POST mb=+1.0000 occ=0.4989 hz=24.94 gain=0.505 tonic=0.0908
  PRE  mb=+0.0000 occ=0.5000 hz=25.00
  PRE  mb=+0.2384 occ=0.5000 hz=25.00
  PRE  mb=+0.5000 occ=0.9818 hz=49.09
  PRE  mb=+0.9633 occ=1.0000 hz=50.00
  PRE  mb=+1.0000 occ=1.0000 hz=50.00
  worst 0.49889  monotonic True
```

- **不再贴顶**：post 全档最大占用率 **0.4989（24.94 Hz）**；同档 pre **1.0000（50.00 Hz）**。live 平台档（mb=+0.9633）post **0.4972（24.86 Hz）** vs pre **1.0000（50.00 Hz）**。
- **对驱动力单调**：8 档严格非降（0.1230→0.1589→0.3336→0.3692→0.4355→0.4761→0.4972→0.4989）。
- **不静音**：最低档仍有 0.1230（6.15 Hz）；homeostat 的 floor 0.25 保证 MBON 通路不会归零。
- **阴性反馈确实生效**：live 平台档 `gain=0.509`、forward tonic limb 从 0.1800 降到 0.0916 V/tick（≈ −49%）。
- 与 live baseline（46.15–50.00 Hz）对比：修复前重建档位 49.09–50.00 Hz 落在 live 区间内；w=0 臂缺连接组回投电流（t1 §5.5），故 pre 在 mb≤0.24 时停在 25.00 Hz 而不是 live 的 34.6–50 Hz —— 这是**证据的限制**，不是矛盾。

### 5.2 fixture 连接组强度扫描（实现者未报告的部分）

```
  connectome scale 0.02 : pre occ=1.0000 (50.00 Hz) -> post occ=0.5000 (25.00 Hz)  post_gain=0.5004
  connectome scale 1.00 : pre occ=1.0000 (50.00 Hz) -> post occ=1.0000 (50.00 Hz)  post_gain=0.2500
```

⇒ 在 `w_scale=1.0`（原始 demo fixture 连接组）下，**修复前后都在天花板**：homeostat 的权限只覆盖 MBON 通路（≤0.35·|mb|）与 forward tonic（≤0.135 V/tick），**不覆盖 `_synaptic_buf`（连接组回投）**。这是**证据限制**而非 live 预测（fixture 是合成随机图，绝对量级不代表 MaleCNS；本机无 `.cache/malecns`，真实连接组臂无法运行）。实现者的测试正是靠把图缩放到 0.02 才能测到机制；本验证把这一点显式报告出来（脚本 note `fixture_connectome_pins_pools`, severity=medium）。

### 5.3 §7.1 独立性：修复不依赖 MBON

`mb=0` 且在 live-like 地板下 post 占用率 **0.3336（16.68 Hz）**（pre 0.5004 = 25.02 Hz）——即 **MBON 通路完全为 0 时动态范围也已恢复**，修复不是"调 MBON"。

### 5.4 边界余量（必须如实说明）

`worst = 0.4989` 距"< 50%"仅 **0.0011（0.22%）**。机制上这是硬复位 LIF 的 **T=2 限周期**（每神经元每 2 tick 放电 1 次 → 占用率 1/2），残余地板 `brk(0.125)+tonic(gain·0.18)+reflex(0.20) ≈ 0.558 V/tick` 恰好略高于 T=2 阈值 0.55 V/tick，因此占用率**只能到 0.5 而不会更高**，也不会更低。结论"< 50%"成立但**没有工程余量**：任何把残余地板再抬高 ~0.02 V/tick 的改动都会让 worst 回到 0.5 以上。

---

## 6. 证据 D：steering 池（验收 #3）

### 6.1 单侧定向驱动（live-like：`w=0`、`stuck=806.8`、粘滞 `reflex_forward=70`、OU 开、`reflex_turn=±70` → 单侧 +0.25 V/tick）

```
  none   POST L=0.0267 R=0.0286 cofire=30/95 Lfire=58 Rfire=52 | PRE L=0.0000 R=0.0000 cofire=0
  left   POST L=0.2502 R=0.1127 cofire=94/95 Lfire=95 Rfire=94 | PRE L=0.0452 R=0.0000 cofire=0
  right  POST L=0.1065 R=0.2572 cofire=94/95 Lfire=94 Rfire=95 | PRE L=0.0000 R=0.0621 cofire=0
  left   NOCD(counter-drive 置零) L=0.3122 R=0.0127 cofire=30/95 Lfire=95 Rfire=30
  right  NOCD(counter-drive 置零) L=0.0061 R=0.3279 cofire=21/95 Lfire=21 Rfire=95
```

- **两池各自可非零**：left 驱动 → left **0.2502（12.51 Hz）**；right 驱动 → right **0.2572（12.86 Hz）**。（`win_occ` 是 13-tick 窗口均值；`Lfire/Rfire` 是逐 tick 池内有无放电。）
- **修复机制 = 删除对称钳位**：同一 harness、同一 seed 下 pre 为 0.0452 / 0.0621（≈2.3 / 3.1 Hz），post 为 0.2502 / 0.2572 → **5.5× / 4.1×**。pre 的数值与 t1 §E8b（H2 left=0.0428=2.14 Hz、H1 right=0.0206=1.03 Hz）同量级、同形态（单侧被压制），本验证独立复现了 t1 的转向池基线。
- **"不是对单侧强加常量电流"**：未驱动侧的活动（0.1127）来自 **t1 已存在的、状态相关的** `TurnAdaptation.counter_drive`（`min(left,right)` 疲劳积分 → 注入对手池；`git diff` 未触碰 `counter_drive` 任何一行）。把该耦合置零（实例旋钮，不改源码）后未驱动侧塌到 **0.0127**，而驱动侧升到 0.3122 —— 归因明确。修复的 `model.py` diff 只新增 2 行转向池写入，且都是同一个**抑制性** `-=`：

```
  added_turn ['self.v[self.turn_left] -= _turn_brk', 'self.v[self.turn_right] -= _turn_brk']
```

### 6.2 疲劳门控（`breakout_split`，`stuck=806.8 s`）

```
  osc=0.00: raw=0.5000  forward_push=0.1250  turn_clamp_per_side=0.0000
  osc=0.25: raw=0.5875  forward_push=0.1469  turn_clamp_per_side=0.0734
  osc=1.00: raw=0.8500  forward_push=0.8500  turn_clamp_per_side=0.4250
```

即：**单侧/静默（osc=0）时双侧钳位为 0**（这正是 left=0.000 Hz 被解开的原因）；真实交替（osc=1）时把 raw 全额支付；前向突围保留 0.25 的有界地板。

### 6.3 共放电的明确结论（验收要求）

| 构型 | co-fire tick / 采样 |
|---|---|
| 修复前（none / left / right 三臂） | **0 / 95，0 / 95，0 / 95**（t1 的 never-co-fire 基线复现） |
| 修复后 · 无方向驱动 | **30 / 95** |
| 修复后 · left 驱动 | **94 / 95** |
| 修复后 · right 驱动 | **94 / 95** |
| 修复后 · 方向驱动 + 疲劳耦合置零 | left 驱动 **30 / 95**、right 驱动 **21 / 95** |

**结论**：**修复后会出现共放电**，t1 的 never-co-fire 严格互斥**没有保留**。机制：钳位（每侧 −0.25 V/tick）原本是两池互斥的来源（t1 §B4）；钳位按疲劳门控后，被驱动侧稳定放电并通过**既有**的疲劳 counter_drive（≤0.18 V/tick）招募对侧，于是两池同 tick 放电。共放电需要"驱动 + 疲劳耦合"两条件（把耦合置零后仍保留 30/95 的窗口级耦合，逐 tick 的 pool 级共放电降到 30/95——注意 30/95 来自 OU 共模与疲劳残余）。

> 影响提示（供 live 集成评审）：这是**行为变化**，不是缺陷——但它意味着 live 中 `left`/`right` 不再严格互斥，转向表决 `turn_rate = right − left` 的统计分布会改变；`t7` 接线后应在 live 上复查转向行为（本轮未做，见 §10）。

---

## 7. 证据 E：t2 是否满足 t1 §7 硬约束（验收 #4）

| t1 §7 约束 | 结论 | 证据 |
|---|---|---|
| §7.2/§7.5 `breakout_drive` 的 stuck boost 不再与疲劳水平无关 | **满足（含 1 项残留，已量化）** | `osc=0 → turn_clamp=0.0000, forward_push=0.125` vs `osc=1 → 0.425 / 0.850`；**残留**：前向突围保留 `0.25×raw = 0.125 V/tick` 的无条件地板（< 0.552 V/tick 的 T=2 阈值，单独不足以自持，但不是 0） |
| §7.2 `reflex_forward` 不再粘滞 | **未满足（UNCLOSED，live/main.py 侧）** | 全仓 `reflex_forward` 只有 3 处写入（`main.py:1563 = -10`、`:1642 = action["control_y"]`、`:1901 = -60`），**没有任何 `= 0`**；`model.py` 仅在 `__init__` 置 0。t2 未改该 limb（属 runner 文件，t2 声明范围外，留给 t7 接线）。t2 做到了**界定其后果**：粘滞 0.20 V/tick 仍在时，live-like worst 为 **0.4989（24.94 Hz）** 而非修复前 **50.00 Hz**。残留风险量化：0.20 / 0.55（T=2 所需）≈ **36% 的剩余余量被一个过期标志占用** |
| §7.1 R17/MBON 未被用作修复手段 | **满足** | `mushroom_body.py` 与 HEAD **逐字节相同**（`git diff --name-only` 无此项）；`mbon_gain_forward = 0.35 == HEAD`；`mb=0` 时 live-like post 占用率仍 0.3336；限周期律证明 MBON 单路上限 8.2 Hz（§3） |
| §7.3 steering 复活不是靠对单侧强加常量电流 | **满足** | diff 仅新增 2 行对称 `-=`（抑制项）；`turn_clamp_per_side` 是**单一标量**同时施加于左右；未驱动侧活动被证明来自既有 `counter_drive`（置零后 0.1127 → 0.0127） |

---

## 8. 证据 F：gate 单位契约（验收 #5）

### 8.1 Control 语义 & 两侧同量纲

- `Control.forward_rate/turn_rate/jump_rate` 由 model.py:2084-2086 的 13-tick 窗口均值解码，**per-tick 比例（|·| ≤ 1）**。本验证在 live-like arm 上跑 60 tick，三字段始终在 [0,1]（最大观测 0.5000）。
- `Observatory`（telemetry.py:77-78）把同一物理量按 Hz 上报：120 个采样点上 `row["forward"/"jump"] == rate_per_tick_to_hz(Control.rate, model.dt)`，最大绝对差 **3.4e-06 Hz**（float32 ring vs float64 换算的舍入）。
- flow.json（main.py）：
  ```
  {'gate_forward': 'gate_open_hz(_forward_rate_hz, _gate_forward_hz)',
   'gate_jump':    'gate_open_hz(_jump_rate_hz, _gate_jump_hz)',
   'gate_forward_threshold_hz': 'round(_gate_forward_hz, 4)',
   'gate_jump_threshold_hz':    'round(_gate_jump_hz, 4)'}
  '{'_forward_rate_hz': "rate_per_tick_to_hz(getattr(control, 'forward_rate', 0.0), _rate_dt)",
    '_turn_rate_hz':    "rate_per_tick_to_hz(getattr(control, 'turn_rate', 0.0), _rate_dt)",
    '_jump_rate_hz':    "rate_per_tick_to_hz(getattr(control, 'jump_rate', 0.0), _rate_dt)"}
  ```
  ⇒ **单次换算、两侧同量纲、显式发布阈值单位**；工作区 `main.py` 中已无 `"gate_forward_threshold", 0.4` / `"gate_jump_threshold", 2.0` 这类旧口径读取。
- 边界：`gate_open_hz` 用严格 `>`（观测 == 阈值 → 关）；静默池 → 关；天花板 1/dt = 50 Hz → 开。

### 8.2 gate_jump 可达性（真实池速率）

```
healthy jump pool: jump_rate=0.2308/tick -> 11.54 Hz > threshold 8.0 Hz -> gate_jump=True
（修复前同输入的比较：0.2308 > 2.0 → False，恒假复现）
```

### 8.3 同一 flow.json 内其余 `control.*_rate` 消费点

| 位置 | 表达式 | 口径 | 判定 |
|---|---|---|---|
| main.py:2682 | `getattr(control, 'jump_rate', 0.0) < 0.04`（`jump_not_active`） | **per-tick**（读原始字段 + per-tick 阈值 0.04/tick = 2.0 Hz） | **自洽**，与 `gate_jump_threshold_hz` 不同单位但读的是不同字段，非缺陷；注释已写明 |
| main.py（flow.json gate_*） | `gate_open_hz(*_hz, *_threshold_hz)` | Hz | 契约统一 |
| 其他（AST 全量扫描） | 无 | — | 无第三处比较 |

### 8.4 残留分歧（如实列为未闭合项，不据此判 t3 失败）

1. **telemetry.py 阈值未与 schema 同源**：`telemetry.py:93-94` 仍用字面 `0.4` / `2.0` 与其 **Hz 速率**比较，而 schema/registry 现声明 `2.0 Hz` / `8.0 Hz`；`active_strategy.json` 里另有 `3.082`（旧口径数值）。同一 `gate_jump` 的两路 producer 在 5.0 Hz 池上给出相反结论（WS=True，flow.json=False）。**单位缺陷两侧都已修好（都成了 Hz-vs-Hz），但数值阈值没有单一来源。**
2. 上述 `jump_not_active` 的 per-tick 口径（已判定自洽，仅记录）。
3. **live 未部署**：活体 `flow.json` 尚无 `forward_rate_hz` / `gate_jump_threshold_hz` 等键（§10），故修复后的 flow.json 口径**只经离线静态+单元级证据**，未经活体验证。

---

## 9. 证据 G：回归核验（验收 #6）

### 9.1 合约 verify 命令（原样执行）

| # | 命令 | 退出码 | 原始输出 |
|---|---|---|---|
| 1 | `cd fly64; ..\.venv\Scripts\python scripts/verify_motor_pools.py --json` | **0** | `SUMMARY {'passed': 29, 'failed': 0, 'failed_ids': [], 'elapsed_s': 258.6}` |
| 2 | `cd fly64; … python -m pytest tests/test_motor_pool_dynamics.py tests/test_gate_units.py -q` | **0** | `25 passed in 115.37s (0:01:55)` |
| 3 | `cd fly64; … python -m pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_dashboard_protocol.py tests/test_strategy_key_contract.py -q` | **0** | `64 passed in 17.29s` |

（命令 1 的完整 JSON 报告见脚本 `--out`；29 项检查逐条 PASS，无失败项。）

### 9.2 全量套件 vs 基线

```
37 failed, 1254 passed, 36 skipped in 320.85s (0:05:20)
$ python scripts/check_regressions.py --report .tmp/t4_full_suite_utf8.txt
  failing now      : 37
  still failing    : 35 (known)
  NEW failures     : 2
  baseline entries that now PASS : 1
  !!! NEW FAILURES:
      tests/test_plugin_mhr.py::TestCycle::test_frame_captured_into_request
      tests/test_plugin_mhr.py::TestPluginStructure::test_manifest_valid
```

> 基线文件是平台作用域的 `fly64/tests/known_failures.win32.json`（36 条）——`tests/known_failures.json` 在本树**不存在**，`scripts/check_regressions.py` 明确优先平台作用域文件（其 docstring 与 `baseline_path()` 均如此），故用后者对照是正确的对照目标。

### 9.3 两项 NEW 失败的归因（**与本任务无关**，含对照实验）

两项都是同一个 LLM 型号字符串断言：

```
assert m["llm"]["model"] == "glm-5v-turbo"   -> actual 'qwen3.8-27b-uncensored'
assert req["model"]       == "glm-5v-turbo"  -> actual 'qwen3.8-27b-uncensored'
```

对照证据：

1. `fly64/plugin/manifest.json:30` = `"model": "qwen3.8-27b-uncensored"`，由**已提交**commit `78b3175`（2026-09-23 12:42:27 +0800，"switch coach LLM … DEFAULT_MODEL + manifest updated"）改动；基线记录时间 2026-09-23T01:09:27Z **早于**该 commit。
2. `fly64/tests/test_plugin_mhr.py` 在工作区有**未提交的 2 行编辑**（`glm-5.3-flash` → `glm-5v-turbo`），且 HEAD 版本期望 `glm-5.3-flash`。
3. **决定性对照**：把该测试文件的 **HEAD 版本**（无未提交编辑）复制到 `fly64/.tmp/` 运行两项：
   ```
   2 failed, 44 deselected in 0.29s
   assert req["model"] == "glm-5.3-flash"  -> 'qwen3.8-27b-uncensored'
   ```
   ⇒ 该失败**在 HEAD 上就已存在**，与未提交编辑、与 t2/t3 均无关。
4. t2/t3 的改动面（`fly64/fly64/model.py`、`fly64/fly64/main.py`、`skills/brain_tunable_params.json`、各自测试）**不含** `plugin/**`、`plugin/manifest.json`、`llm_consult.py`；`plugin/runner.py` 只 import `fly64.memory` / `fly64.instinct_bindings`，**不 import** `fly64.model` 或 `fly64.main`。

**处理建议（给队长/后续任务）**：这 2 条属 `test-drift`（模型切换 commit 未同步测试期望），应由 LLM/plugin 相关任务更新 `tests/test_plugin_mhr.py` 的期望值（或改为从 manifest 读取），并在 `known_failures.win32.json` 中补录。

另：`baseline entries that now PASS: 1` = `tests/test_fix_executor.py::TestParseFixTemplate::test_manual_fallback`——由工作区中**其他并发成员**对 `skills/fix_template_interpreter.py` 的未提交改动所致，同样不在 t2/t3 改动面内（本验证期间该文件始终是 `M` 状态）。

---

## 10. 活体实测证据（**BASELINE，非修复验证**）

### 10.1 部署指纹

```
deployed /root/fly64/fly64/model.py  = 9cb829ca7c3d3985396e23daa94142d8  (== git HEAD == 修复前)
         working tree  model.py       = a2d4242d29534351297da7472e8e88f9  (修复后)
deployed main.py                     = 1ebcfcc7bbb5f1f3d4c6e79928da05f4  (修复前)
         brain 进程                   = ./venv/bin/python -m fly64.main --bridge /tmp/f64b_traj …
repair_deployed = False
```

⇒ **活体没有部署修复代码**。把新代码部署到 WSL 并重启脑模型属于**部署动作，需用户确认**；未获确认时本任务只做离线验证。**因此本报告不得、也没有声称"活体已验证修复"。**

### 10.2 活体 baseline 复测（`scripts/probe_pools.py` + 内联 F643 采样）

```
magic=b'F643' schema=3 window_ticks=13 dt=0.02 rate_max=50.0
t           visual  forward     left    right     jump   strike   crouch      x      y decision
6744.12     11.332   50.000    0.000    0.000   24.038   22.692    8.077     70     70 lf_escape
6744.14     11.202   50.000    0.000    0.000   24.038   19.615    7.500     70     70 lf_escape
6744.16     11.624   50.000    0.000    0.000   25.000   18.846    6.731     70     70 lf_escape
6744.18     11.567   50.000    0.000    0.000   25.000   15.962    6.154     70     70 lf_escape
forward pool: n=4 min=50.000 max=50.000 mean=50.000  (Hz)
```

第二个窗口（10 次联合采样，WS + 同时刻 flow.json；本轮 `--json` 报告的 live 段即此窗口）：

```
pool_stats_hz = {
  visual : min 11.22 max 12.35 mean 11.63
  forward: min 50.00 max 50.00 mean 50.00     <- 贴顶（团队基线 46.15–50.00 Hz）
  left   : min  0.00 max  5.77 mean  2.50
  right  : min  0.00 max  3.85 mean  0.38     <- 与 forward 差 ~130×~260×
  jump   : min 18.27 max 25.00 mean 20.96 }
gate_agreement = {'samples': 10, 'ws_true': 10, 'flow_true': 0}
```

> 窗口敏感性（如实记录）：同一会话另一个 10 样本窗口实测 `left mean 0.77 / max 5.77`、`right mean 0.19 / max 1.92`、`jump mean 27.21`。两个窗口都显示 **(a) forward 恒 50.000 Hz 贴顶；(b) left/right 远低于 forward 且随窗口翻转**——与 t1 §B4"left 不是硬锁，而是与 right 一同塌缩到 forward 的 1/50–1/100"一致。**这些是"修复前"的读数**。

**gate 契约破裂的活体重现（修复前代码）**：

```
t=7039.6 ws_gate_jump=True  flow_gate_jump=False  flow_jump_rate=0.5385  flow_jump_rate_hz=None
t=7039.7 ws_gate_jump=True  flow_gate_jump=False  flow_jump_rate=0.6154  flow_jump_rate_hz=None
…
（10/10 行：WS 用 Hz 比较 → True；flow.json 用 per-tick 0.54 比 "2.0 Hz" → 恒 False）
```

并且活体 `flow.json` 中 `forward_rate_hz` / `jump_rate_hz` / `gate_jump_threshold_hz` **均为 absent**，`jump_not_active=False`，`forward_rate=1.0`、`jump_rate=0.4423`、`gate_forward=True` —— 与 §8 描述的修复前口径完全一致。

---

## 11. 未闭合项 / 限制清单

| ID | 级别 | 内容 | 归属 |
|---|---|---|---|
| U1 | **high** | `reflex_forward` 粘滞（无任何 `= 0` 复位点）；t2 只界定其后果（worst 仍 <0.5，但占用 36% 剩余余量） | t7（main.py 接线）/ runner |
| U2 | medium | 修复后 **steering 两池会共放电**（t1 的 never-co-fire 不再成立）；钳位按疲劳门控的必然代价 | live 集成评审 / t7 |
| U3 | medium | `telemetry.py:93-94` 阈值（0.4 / 2.0 Hz）与 schema（2.0 / 8.0 Hz）**未同源**，同一 gate_jump 两路 producer 可给出不同结论 | t3 后续 / 单源化任务 |
| U4 | medium | demo fixture 原始连接组（`w_scale=1.0`）下修复前后都贴顶；homeostat 不覆盖 `_synaptic_buf`；真实 MaleCNS 臂本机无法运行（无 `.cache/malecns`） | 证据限制 + 后续 live 验证 |
| U5 | low | 前向突围保留 `0.25×raw = 0.125 V/tick` 的**无条件**地板（t1 §7.2 的"与疲劳无关"仅部分消除；单独不足以自持） | t2 设计权衡（已注释） |
| U6 | low | 修复后 worst 占用率 0.4989 距 "<50%" 仅 **0.0011** 余量 | 结构上限（T=2 限周期） |
| U7 | info | 活体仍跑**修复前**代码；flow.json 的 `*_hz` 口径只经离线证据 | 部署需用户确认 |
| U8 | low | 全量套件 2 项 NEW 失败（`test_plugin_mhr.py`，模型名漂移，HEAD 即失败，与本任务无关）；基线有 1 条已转为通过（他人并发改动） | 回归治理 |

---

## 12. 复现命令

```powershell
# 1) 独立验证脚本（本报告全部量化证据；exit 0 = 29/29 checks passed）
cd D:\codes\flygym\fly64
..\.venv\Scripts\python scripts/verify_motor_pools.py --json --out .tmp\t4_verify.json
#   可选：--quick 缩短臂；--no-live 跳过活体；--skip-sim 只跑 gate+基线
#   工作区根等价入口：
cd D:\codes\flygym; .\.venv\Scripts\python scripts\verify_motor_pools.py --json

# 2) 合约 verify 命令
cd D:\codes\flygym\fly64
New-Item -ItemType Directory -Force D:\codes\flygym\.tmp-pytest | Out-Null
$env:TEMP='D:\codes\flygym\.tmp-pytest'; $env:TMP=$env:TEMP
..\.venv\Scripts\python -m pytest tests/test_motor_pool_dynamics.py tests/test_gate_units.py -q
..\.venv\Scripts\python -m pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_dashboard_protocol.py tests/test_strategy_key_contract.py -q

# 3) 全量套件 vs 基线
..\.venv\Scripts\python -m pytest -q -rf --basetemp .tmp\.t4-full -p no:cacheprovider |
    Out-File -Encoding utf8 .tmp\t4_full_suite.txt
..\.venv\Scripts\python scripts\check_regressions.py --report .tmp\t4_full_suite.txt

# 4) 活体 baseline（只读；需 WSL 脑模型在跑）
cd D:\codes\flygym; .\.venv\Scripts\python scripts\probe_pools.py
Invoke-WebRequest http://127.0.0.1:8765/flow.json -UseBasicParsing | Select-Object -Expand Content
```

---

## 13. 最终裁决

- **t2（forward 动态范围 + steering 复活）**：**通过**。修复前 0.88 V/tick 地板与 50 Hz 贴顶被独立复现；修复后 live-like 全档占用率 ≤ 0.4989（24.94 Hz）、对驱动力严格单调、两转向池各自可非零（0.25 / 0.26，修复前 0.045 / 0.062），且四项 §7 硬约束中三项满足、`reflex_forward` 粘滞项如实列为未闭合（归属 t7，后果已量化）。
- **t3（gate 单位契约）**：**通过**。gate 判定两侧同量纲、换算单次且与 telemetry 同源、`gate_jump` 在健康 jump 池下可达 True、边界闭合；残留分歧（telemetry 阈值未同源、`jump_not_active` per-tick）已如实列为未闭合项，未据此判 t3 失败。
- **回归**：3 条合约命令全部退出码 0；全量套件 2 项 NEW 失败经 HEAD 对照实验证明与本任务无关（LLM 型号漂移）。
- **活体**：**未验证修复**（部署的是修复前代码）——任何"活体已恢复"的说法在本轮都不成立。
