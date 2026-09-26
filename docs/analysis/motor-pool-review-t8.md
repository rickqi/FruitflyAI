# t9 质量审查报告（round 2）—— t8 repair（t2 交付物的返修态）

- **任务**：t9 — review-round-2（Reviewed task: **t8**；round-1 报告见 `docs/analysis/motor-pool-review-t2.md`，裁决 needs_revision）
- **被审查状态**：工作区未提交状态，`fly64/fly64/model.py` md5 `8f43baa82f0f7491963f1229d0bb00d1`（2492 行；round-1 的 t2 态为 `a2d4242d…`，HEAD 为 `9cb829ca…`）
  - `fly64/tests/test_motor_pool_dynamics.py` md5 `66937c9b8b6aa1b5e0dad3ba693023d0`（767 行、22 个测试函数；round-1 为 298 行 / 10 个）
  - `fly64/fly64/main.py` md5 `348283f05e6deb7131b032fe721fb35d` = **round-1 时的同一 md5**（即 t3 的 gate 改动，t8 之后未再变）⇒ 本轮 main.py 未再被改动
  - `docs/analysis/motor-pool-saturation-findings.md` md5 `5d9cafc98511529656d8c0ba58c090c3`（t8 追加 §7.4 一行）
- **证据来源（不得只依赖 t8 自述）**：
  1. 代码 diff：`git diff HEAD -- fly64/fly64/model.py`（399 行改动 = t2+t8 合并态）、`git status`
  2. round-1 报告与 t1 根因报告（§A4 写点穷举、§A5 地板账、§7 硬约束）
  3. t4 独立验证脚本 `scripts/verify_motor_pools.py`（复用其 `make_model` 作为可控构型，**臂全部自建**）
  4. **本轮自建探针**：`.tmp_t5/reviewer_probe_t9.py`（13 臂：live-like escape 的 t8/t2 对照、osc=1、pit/R22 门控、steering/共放电、反射到期时间线、确定性）、`.tmp_t5/reviewer_probe_t9b.py`（逃生响应的"控制级"代理）；原始输出 `.tmp_t5/t9_probe_output.json`、`t9_probe_output2.json`
  5. 活体只读（本轮未新增采样；沿用 t1/t4 的活体窗口与 t8 记录的 pre 序列）
- **审查纪律**：不修改被审查文件；本轮只新增本报告与 `.tmp_t5/` 探针。

---

## 0. 裁决

**verdict = pass**（round-1 的 blocker/high 全部闭合且被独立复现；残留为不阻塞的收口项）

| round-1 finding | 级别 | 本轮状态 | 独立证据（本次实测） |
|---|---|---|---|
| **F1** 活体可达（escape 开启）时 forward 占用率 0.68–1.00 | blocker | **已闭合** | live-like escape 档（escape + `breakout_forward_bias=0.20` + stuck 806.8 + 每 tick 刷新的 reflex + mb 平台）：**0.3913（w=0）/ 0.4276（w=0.02）< 0.5**；同 harness 关闭 t8 机构（t2 态）= **0.7423 / 0.8237（37.1/41.2 Hz）** ⇒ 修复确实把地板压下 ~47%，不是搬位置 |
| **F2** `reflex_forward` 粘滞未实现却标 passed | high | **已闭合** | 到期就地实现且**按模型 tick 计时（无 wall-clock）**：一次性写入后 `_reflex_effective` 前 15 tick 均值 **70.0** → 其后均值 **3.97**；`reflex_flag_scale` 在 age=0/15/25/135 tick = **1.0 / 1.0 / 0.3679(=e⁻¹) / 0.0**；每 tick 刷新则恒 70.0；原始标志 200 tick 后仍 70（未越权改生产者） |
| **F3** 交付说明事实性错误 | high | **未闭合（治理）** | 代码侧已不成立（见 F2），但 **t2 台账 `acceptanceResults[1].evidence` 仍是 round-1 的错误文本**（"blend_reflex_control() 实现反射期混合；model 侧注入不粘滞"）——t2 已终态，t8 无权改写，须由 captain 补录（见 N1） |
| **F4** A7 要求的 (b)(e) 两项断言缺失 | medium | **已闭合** | `test_stale_reflex_flag_injection_expires` / `test_reflex_flag_expiry_contract`（(b)）；`test_forward_pool_write_sites_are_covered_or_gated`（(e)，AST 穷举 + 16 条 RHS 注册表 + 无门控必被反馈覆盖 / aux 必过 `_aux_forward_current` / gated 必在 if 内且常量亚阈） |
| **F5** osc=1 时 breakout 前向腿全额且无反馈 | medium | **已闭合** | osc=1（双池饱和、stuck 806.8）：**0.3967（19.83 Hz）**，`_fwd_brk_applied` = **0.2000**＝上限（raw 0.85）；t2 态同臂 **0.5608**、`_fwd_brk_applied` 0.8500 |
| **F6** 脱困能力只有弱证据 + stuck 时长未测 | medium | **部分闭合** | 推力有效性断言已从 `>0` 升级为 Δocc > 0.05（测试）；本轮补测"**控制级**"等价性：解码 `forward_rate` t8 ≈ 0.35–0.46 vs t2 = 0.5385，两者 `raw_y = clip((rate−0.008)·2000, 0, 70) = 70`（满推力）⇒ 摇杆指令不变；**游戏级 stuck 时长仍不可测**（无桥接/游戏，t8 亦如此） |
| **F7** A9 缺 §7.4 映射 | low | **已闭合** | t1 文档 `§7` 第 4 条后新增一行"§7.4 范围映射（t8 补记）"，内容经复核准确（t2/t8 未读写任何 gate 字段/阈值/单位逻辑；唯一交点 main.py 归 t7） |
| **F8** 反射期网络份额未接线 | info | **按设计延后** | 新增 `test_t7_integration_surface_and_share_floor` 锁住接线面与 ≥25%；main.py 仍无 t8 布线（`grep _aux_forward_current|reflex_flag_scale|blend_reflex_control|fwd_aux_ceiling` 于 main.py = 空）⇒ 归 t7 |

**新增（不阻塞）findings**：N1 台账更正（治理，medium）、N2 aux 预算次序在 escape 模式下饿死 breakout 前向腿（medium-low，已量化、自限）、N3 (e) 写点审计的发现面不完整 + gated 亚阈判据偏弱（low）、N4 t8 自述数字与测试 docstring 略有差异（info）、N5 t7 待办与活体 post 序列（info）。

---

## 1. t9 acceptance 逐条核验

| t9 acceptance | 裁决 | 证据 |
|---|---|---|
| 逐一核验 t2 的每条 acceptance（file:line、测试名、原始输出） | **passed** | 见 §2（9 条，全部给出 file:line / 测试名 / 原始输出或实测）；结论：A1–A5、A7–A9 在当前代码上成立，A6 的"stuck 时长"仍 UNVERIFIED（见 §2 A6 与 F6） |
| 核实未越界：未修改 main.py / brain_tunable_params.json / plugin | **passed** | main.py md5 `348283f0…` 与 round-1 **完全相同**、且 `grep` 无任何 t8 标识符；`brain_tunable_params.json` 仅 t3 的两条 gate 条目（round-1 已核）；`plugin/.consult_request.json` 为运行期产物。t8 唯一越出 changedPaths 的动作是**追加 t1 文档一行**（已声明；本轮复核为纯追加、内容准确、未改 t1 原有证据） |
| 核实未通过删除/放宽既有断言取得绿测（对照 git diff） | **passed** | 新测试文件为 `??`（无 HEAD diff 可比），故逐行比对 round-1 记录的原文：**10 个原测试函数全部保留且断言逐字一致**（`occ<0.6`/`spread>0.05`/`raw==0.5`/`fwd==0.5·floor`/`raw2==0.85`/`turn2==0.425`/`left_active>=0.1·samples`/`reflex_network_share>=0.25` 等，见 `tests/test_motor_pool_dynamics.py:176-291,694-747`）；`tests/` 的 HEAD diff 仍是同 7 个文件、全部属其他工作流（LLM 型号漂移 / protocol 签名 / t8-t9 线），运动池断言零改动 |
| 核实未引入未播种 RNG（回放契约） | **passed** | diff 中无 `random/shuffle/permutation/default_rng`，**也无 `time./monotonic/perf_counter/datetime`**（到期按 `step_count·dt` 计时）；新测试 `test_no_unseeded_rng_in_the_motor_path` + 本轮独立双模型跑 60 tick：`spikes_equal/occupancy_equal/aux_used_equal/stamps_equal` 全 True |
| 核实反射脱困能力未劣化：stuck_ramp/oscillating/wall_stuck/micro_loop 触发与释放仍有效，stuck 时长未劣化 | **partially passed** | 释放条件零改动（t8 diff 不含 `memory.py`/`ReflexController`/`main.py`；`tests/test_memory.py` 123 passed 覆盖四态触发/释放）；控制级脱困推力等价（raw_y=70，见 F6）；**游戏级 stuck 时长仍无测量**（本机无桥接；t8 只记录了 pre 侧活体序列 1758.7→1760.6 s、forward_rate 0.65–1.00，post 侧待 t7 部署）⇒ 该项保持 UNVERIFIED 而非 failed |

---

## 2. t2 的 9 条 acceptance（**在当前代码上**重新核验）

| # | t2 acceptance | 当前代码裁决 | 证据 |
|---|---|---|---|
| A1 | breakout stuck boost 不再是与疲劳无关的无条件常量注入 | **passed** | `breakout_split`（`model.py:1381-1420`）turn 钳位 × `osc`；`_fwd_brk` 再经 `_aux_forward_current`（`model.py:2156-2158`）⇒ osc=0 时 forward 腿 = raw×0.25×gain，且受 0.20 聚合上限约束（实测 `_fwd_brk_applied` 0.2000 vs raw 0.85） |
| A2 | reflex_forward 不粘滞（归零或按明确时间常数衰减） | **passed**（代码）；台账文本未更正 | `model.py:699-711,808-852,1995-2022`：`__setattr__` 写戳 + `reflex_flag_scale`（ttl 0.30 s / tau 0.20 s，按 tick）；三腿注入改用 `_reflex_effective`；实测到期曲线见 F2。**台账 evidence 仍是旧文本（N1）** |
| A3 | post-leak 地板可测且显著低于饱和线（w=0 与 live-like 两档 < 50%，单调、不静音） | **passed** | 本轮 §3 表：live-like escape 0.3913/0.4276、osc=1 0.3967、pit/R22 门控 0.2320/0.3841 全部 < 0.5；单调性仍由 `test_forward_occupancy_is_monotonic_in_mbon_input` 保持（22 passed）；最低档未被压死（0.23–0.39 ≫ 解码满驱动点 0.043） |
| A4 | steering 复活（去抑制路径 + 两池各自非零 + 共放电实例） | **passed** | 本轮 P6：定向驱动下 L=0.0410 / R=0.0483，co-fire 48/250（t1 的 never-co-fire 0/95 不再成立）；去抑制路径（osc 门控钳位）未变 |
| A5 | 不得把 R17 门限 / `mbon_gain_forward` / `mb_mbon_forward` 当修复手段 | **passed** | `git diff -- mushroom_body.py` 空；`mbon_forward_weight = 0.35`；本轮 `mb=0` 的 live-like escape 档仍 0.3913（不依赖 MBON） |
| A6 | 无未播种 RNG；不删除/放宽断言；四态触发/释放有效；**stuck 时长不得劣化** | **partial** | 前三项 passed（见 §1）；stuck 时长 UNVERIFIED（F6） |
| A7 | 新增测试 ≥5 项覆盖 (a)–(e) | **passed** | 22 个测试：10 原始 + 12 新增，含 (b) 两项、(e) 写点合同、(A5) osc=1、(A1) live-like escape < 50%、aux 上限、A6 Δocc、(A8) t7 接线面、无 RNG；`verify#1` 22 passed |
| A8 | verify 全部 exit 0；既有测试无新增失败 | **passed** | 本轮原样重跑：verify#1 22 passed / verify#2 59 passed / verify#3 123 passed+1 deselected / 相关回归 64 passed，**EXIT 0/0/0/0**（TEMP 重定向） |
| A9 | 实现说明逐条对照 t1 §7（含 §7.4/§7.5） | **passed** | t1 文档新增 §7.4 映射一行（md5 `5d9cafc9…`），内容准确；§7.1/7.2/7.3/7.5 映射见 t8 交付说明与测试落点 |

---

## 3. 本轮独立实测（原始输出）

配置：`FlyModel(demo=True, seed=64)`、`w_scale∈{0,0.02}`、`visual_connected=False`、探索惯性冻结、`mirror_mb=0.96`（关闭 pit/R22 门控，除 P5 专门打开）、`anomaly_state_name="oscillating"`、400 tick / warm 150；`t2 态` = 实例级重建（`escape_leg_homeostat=False`、`breakout_leg_homeostat=False`、`reflex_flag_ttl=1e9`），不改源码。

```
P1  live-like escape (t8, no disp signal)      fwd=0.3913 (19.57 Hz) L=0.1424 R=0.1280 aux=0.2000 brk=0.0000 eff=70.00 raw_y=70.0 disp=False acc=0.150
P1b live-like escape (t8, scale=0.02)          fwd=0.4276 (21.38 Hz) L=0.1562 R=0.1361 aux=0.2000 brk=0.0000 eff=70.00 raw_y=70.0 disp=False acc=0.150
P2  same harness, t2 state (legs bypass)       fwd=0.7423 (37.11 Hz) L=0.1424 R=0.1280 aux=0.1166 brk=0.5112 eff=70.00 raw_y=70.0 disp=False acc=0.150
P2b same harness, t2 state, scale=0.02         fwd=0.8237 (41.18 Hz) L=0.1817 R=0.1351 aux=0.0864 brk=0.5463 eff=70.00 raw_y=70.0 disp=False acc=0.150
P3  live-like escape + disp signal (ramp)      fwd=0.3913 (19.57 Hz) aux=0.2000 brk=0.0000 disp=True  acc=0.200   ← 有位移信号也不会顶破上限
P3b live-like escape + disp signal, t2 state   fwd=0.8181 (40.90 Hz) aux=0.1149 brk=0.5112 disp=True  acc=0.200
P3c live-like escape, no reflex write at all   fwd=0.3913 (19.57 Hz) aux=0.2000 eff=0.00              ← 不依赖粘滞项
P4  osc=1 (t8), mb=1.0, escape off             fwd=0.3967 (19.83 Hz) aux=0.2000 brk=0.2000 raw_y=70.0
P4b osc=1 (t2 state), mb=1.0, escape off       fwd=0.5608 (28.04 Hz) aux=0.0000 brk=0.8500
P4c osc=1 (t8) + escape on                     fwd=0.4011 (20.05 Hz) L=0.0682 R=0.0506 aux=0.2000 brk=0.0000
P5  pit/R22 gates open (mb=0, idle, stuck=100) fwd=0.2320 (11.60 Hz) aux=0.0729 brk=0.0728
P5b same + tonic 0.18 + OU (live-ish)          fwd=0.3841 (19.21 Hz) aux=0.1116 brk=0.0823
P6  steering t8:  L=0.0410 R=0.0483 cofire=48/250   |  t2-state: L=0.1448 R=0.0987 cofire=13/250
P7  reflex expiry: first15=70.0, after=3.9725, scale@0/15/25/135 tick = 1.0/1.0/0.367879/0.0, raw_flag_after_200=70, refreshed_tail=70.0
P8  determinism: {spikes_equal: True, occupancy_equal: True, aux_used_equal: True, stamps_equal: True}
```
（`raw_y` = 生产解码式 `clip((forward_rate−0.008)·2000, 0, 70)`；`aux` = `_fwd_aux_used` 峰值，≤ 0.20 上限；`brk` = `_fwd_brk_applied` 均值。）

**逃生响应（控制级代理，`.tmp_t5/t9_probe2_output.json`）**：t8 态解码 `forward_rate` 稳定在 0.35–0.46、t2 态 0.5385 ⇒ 两者 `raw_y` 均 = **70（满推力）**；本机无游戏/桥接，**游戏级 stuck 时长无法离线测量**（探针里"首次越过 0.043"被 `history` 预置窗口污染，故不作为证据使用，仅记录）。

---

## 4. Findings

| id | severity | 问题 | 建议修复 |
|---|---|---|---|
| N1 | medium（治理） | **t2 台账未更正**：`team.json` t2 `acceptanceResults[1].evidence` 仍写"model 侧注入不粘滞"（round-1 已被证伪，代码侧现已修复）。t2 为终态，t8 无权改写，本轮仍可见错误文本 | captain 将该条证据替换为 t8 的实测（到期曲线 ttl 0.30 s/tau 0.20 s、一次性写入 eff 70→3.97、刷新恒 70），并在 t2 台账注明"由 t8 修复、t9 复核" |
| N2 | medium-low | **aux 预算次序在 escape 模式下饿死 breakout 前向腿**：`_fwd_aux_used` 由 escape 两腿先占用（`model.py:1778` 重置 → 1901/1991 → 2157），实测 P1/P4c 的 `_fwd_brk_applied = 0.0000`，而**每侧 turn 钳位不在预算内**（`model.py:2161-2163`；osc=1 时 −0.425/side）⇒ escape+织网态会短暂重现"只有钳位、没有前向突围"的 t1 形态。实测该态转向池仍活（L=0.068/R=0.051），且钳位受 osc 门控（池静默→疲劳衰减→钳位归零）自限 | 让 breakout 前向腿在预算内**先于** escape 腿取用，或令 turn 钳位按"实际到位的 forward 推力比例"缩放（保持 push/clamp 成对） |
| N3 | low | **(e) 写点审计的发现面不完整 + 亚阈判据偏弱**：`_forward_write_sites()` 的 `pool_of` 只认 `motor_nodes` 的 **Attribute** 形式，漏掉 OU 的切片写点（`model.py:2233/2236/2239/2241`，其中 2233 正是 t1 §A4 的第 15 项 `ou_state[0]·0.15`）；用切片感知的访问器枚举得 20 处，审计只覆盖 16 处。另 gated 判据为"常量 < 1.0"，弱于 T=3 边界 0.402，且不检查多个 gated 腿的**和**（本轮 P5/P5b 打开 pit/R22 门控实测 0.2320/0.3841，未复现贴顶，故判 low） | 扩展 `pool_of` 支持 `motor_nodes[a:b]`（或断言"枚举数 == 源码 `self.v[...]` 写点数"）；把 gated 判据收紧到 < 0.402 或增加"gated 腿之和 < T=3 边界"的聚合断言 |
| N4 | info | t8 自述 0.3890/0.4282 与其测试 docstring 的 0.3963/0.4336 略有差异；本轮独立测得 0.3913/0.4276（同向、均 < 0.5）。差异来自 harness 细节（tick 数/OU/初始 accumulator），不影响结论 | 交付说明统一以测试实测值为准（或在报告中标注 harness） |
| N5 | info | 待办：t7 一行接线 `blend_reflex_control`（live `main.py:1550-1552`）+ 集成/活体验证"反射期 LIF 份额 ≥25%"；t7 部署后补采 post 侧 `stuck_duration/disp_60s` 序列（pre 侧已记录）以关闭 A6 的 stuck 时长项 | 归 t7；部署属需用户确认的动作 |

**已闭合项不再列为 finding**：round-1 的 F1（blocker）、F2（high）、F4、F5、F7 均已闭合且被本轮独立复现；F6 部分闭合（控制级等价已验证、游戏级 stuck 时长未测）；F3 转为 N1（治理）；F8 按设计归 t7（N5）。

---

## 5. 回归与验证命令（原样重跑，含 TEMP 重定向）

```
cd fly64; New-Item -ItemType Directory -Force D:\codes\flygym\.tmp-pytest | Out-Null
$env:TEMP='D:\codes\flygym\.tmp-pytest'; $env:TMP=$env:TEMP
$ python -m pytest tests/test_motor_pool_dynamics.py -q
22 passed in 214.07s (0:03:34)                          EXIT=0     (verify#1)
$ python -m pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_cpg_priority.py -q
59 passed in 3.04s                                      EXIT=0     (verify#2)
$ python -m pytest tests/test_memory.py tests/test_optic_flow.py \
      --deselect tests/test_optic_flow.py::test_flow_computation_performance -q
123 passed, 1 deselected in 9.34s                       EXIT=0     (verify#3)
$ python -m pytest tests/test_tunable_wiring.py tests/test_telemetry_completeness.py \
      tests/test_gate_units.py tests/test_strategy_key_contract.py tests/test_dashboard_protocol.py -q
64 passed in 19.49s                                     EXIT=0     (本轮附加)
```
- 22 = 10 原始 + 12 新增，与 t8 自述"10 → 22"一致；附加的 64 项同时覆盖 t3 的 gate 单位契约与 registry 守卫（未因 t8 回退）。
- 环境事实（队长已复现的 `%TEMP%` 清理缺陷）按说明以 TEMP 重定向处理；未据此判任何失败。

---

## 6. 复现命令

```powershell
cd D:\codes\flygym
# 0) 指纹
Get-FileHash fly64\fly64\model.py,fly64\tests\test_motor_pool_dynamics.py,fly64\fly64\main.py -Algorithm MD5
#    model.py 8f43baa8…, test 66937c9b…, main.py 348283f0…（= round-1，未再变）

# 1) 本轮探针（只读：实例属性/实例方法替换，不改源码）
cd D:\codes\flygym\fly64
..\.venv\Scripts\python.exe -u D:\codes\flygym\.tmp_t5\reviewer_probe_t9.py     # 13 臂
..\.venv\Scripts\python.exe -u D:\codes\flygym\.tmp_t5\reviewer_probe_t9b.py    # 控制级逃生代理

# 2) t8 合约 verify（见 §5）

# 3) 写点枚举对照（发现 OU 切片漏检）
python -c "<slice-aware AST visitor over fly64/fly64/model.py count: 20 vs audit 16>"
```

---

## 7. 证据限制 / 诚实清单

1. **活体未部署**：deployed `model.py` 仍是修复前（t4 §10 指纹；本轮未再采样）；所有 post 读数均为**离线实测**（demo fixture，4096 神经元合成图；`fly64/.cache/malecns` 本机不存在）⇒ 只证明机制与算术，绝对量级不代表真实 MaleCNS。
2. **`t2 态` 是实例级重建**，不是旧代码：`escape_leg_homeostat=False` + `breakout_leg_homeostat=False` + `reflex_flag_ttl=1e9` 三条旋钮把 t8 机构旁路；重建值与 t8/t5 的独立读数一致（0.742/0.824 vs 0.7421/0.8266；round-1 我测的 0.6831–0.9979 为不同 harness/参数区间）。
3. **osc=1 臂**用实例级冻结疲劳（`_turn_adapt.update` 替换）构造，代表"双池刚织过网"的可达态。
4. **游戏级 stuck 时长**：本机无桥接/游戏，离线不可测；本轮只给控制级代理（raw_y 满推力）与"释放条件零改动"的代码证据。
5. **pit/R22 门控臂**（P5/P5b）用 `state="idle"` + `mirror_mb=0` 打开两条既有开环注入器，属**非本会话活体状态**的构造臂；结论只用于"不贴顶"的下界判断。
6. 未测量的量一律标注推算/未测量，无推算冒充实测。
