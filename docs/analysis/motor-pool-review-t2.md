# t5 质量审查报告 —— t2（运动池动态范围 / steering 复活 / 反射混合）

- **任务**：t5 — 审查 t2：运动池动态范围与反射混合的正确性、边界与硬约束
- **被审查对象**：t2 实现（`fly64/fly64/model.py` +184/−11，`fly64/tests/test_motor_pool_dynamics.py` 新增 298 行）
- **审查对象状态**：工作区未提交状态。`fly64/fly64/model.py` 工作区 md5 `a2d4242d29534351297da7472e8e88f9`（= t4 验证时的同一状态，本次复核 `git diff HEAD -- model.py` 与 t4 §2.2 描述的三条 limb 完全一致，无第 4 条 limb）
- **证据来源（按要求不得只依赖 t2 自述）**：
  1. 代码 diff：`git diff HEAD -- fly64/fly64/model.py`、`git status`、`git diff HEAD -- fly64/tests`
  2. t1 根因报告：`docs/analysis/motor-pool-saturation-findings.md`（§A4 15 个 forward 写点穷举、§A5 地板账、§B4 steering 写点穷举、§7 五条硬约束）
  3. t4 独立验证报告：`docs/analysis/motor-pool-verification-report.md`（含其 §11 未闭合清单 U1–U8）
  4. **本次自建探针（t5 自有，方法/臂与 t2、t4 均不同源）**：`.tmp_t5/reviewer_probe.py`、`reviewer_probe2.py`、`reviewer_probe3.py`（复用 t4 的 `make_model/run_arm` 作可控构型，**新增 t4 未跑的臂**：escape 开启臂、osc=1 织网臂、live 参数（`breakout_forward_bias=0.2`）臂）；原始输出落盘 `.tmp_t5/t5_probe*.json`
  5. 活体只读采样（HTTP `flow.json`，审查当时）：`escape_behavior=True`、`forward_rate=1.0`（=50 Hz）、`gate_forward=True`
- **审查纪律**：不修改任何被审查文件；本轮只写 `docs/analysis/motor-pool-review-t2.md` 与本报告引用的 `.tmp_t5/` 探针（仓库根 `docs/analysis/` 与 `.tmp_t5/` 均在被审查范围之外）。

---

## 0. 裁决（TL;DR）

**verdict = needs_revision（不通过）**

| # | t2 acceptance | 本次裁决 | 关键证据（一句话） |
|---|---|---|---|
| A1 | breakout stuck boost 不再是「与疲劳无关的无条件常量注入」 | **passed，带残留(low)** | `breakout_split()` 的 turn 钳位乘 `osc`：osc=0 → 0.0000（`model.py:1387-1389`）；forward 突围保留 `0.25×raw=0.125`，单独 **亚阈**（brk-only 臂 post = **0.0000**，本报告 §3 A1 臂）；pre 同臂 0.3336（16.68 Hz） |
| A2 | **reflex_forward 不再粘滞**：反射结束后注入归零或按明确时间常数衰减；离线实测不得再出现由该常量贡献的常驻注入 | **failed (high)** | `model.py:1855-1856` **一字未改**：`if self.reflex_forward: v[forward] += min(0.20, reflex_forward*0.003)`；400 tick 后 `reflex_forward` 仍 70（模型侧唯一写点是 `__init__`，`model.py:727`）；该腿单独贡献占用率 **+0.1229**（0.2091→0.3320）。t2 的"passed"证据描述的是另一个机制（`blend_reflex_control`，输出侧混合） |
| A3 | post-leak 地板可测且**显著低于饱和线**：w=0 与 **live-like** 两档实测 forward 占用率 **< 50%**，且对驱动单调、不静音 | **failed (blocker)** | **live-like 档不成立**：`escape_mode=True`（活体 `escape_behavior=True` 12/12 且审查当时仍为 True）时 post 占用率 **0.6831–0.9979（34.15–49.90 Hz）**，与活体基线 34.6–50.0 Hz 不可区分；`breakout_forward_bias` 取默认 0.50 时 **1.0000（50.00 Hz）**，与 pre 完全相同。t2 的测试与 t4 的 "live-like" 臂都在 `escape_mode=False` 下测量（t4 §2.3 明示），未覆盖活体条件 |
| A4 | steering 复活（同号/持续/可单侧独立驱动，或与池放电无关的去抑制路径）+ 两池各自非零 + 共放电实例 | **passed（带 caveat, low）** | 删除对称钳位（diff 仅 2 行 `-=`，`model.py:1992-1993`）；本次独立复现 left/right 各非零（`L=0.1424 R=0.1280`；pre `0.0000/0.0000`），共放电 post 48/250、pre **0/250**；未驱动侧活动仍来自既有 `counter_drive`（t4 置零后 0.1127→0.0127）；**caveat**：osc 由池放电积分导出，复活并未新增"同号/持续"驱动，仅移除抑制 |
| A5 | 不得把 R17 门限 / `mbon_gain_forward` / `mb_mbon_forward` 当作修复手段 | **passed** | `git diff HEAD -- fly64/fly64/mushroom_body.py` 为空；`mbon_forward_weight = 0.35`（`model.py:633`）未变；`mb=0` 时 live-like(escape off) post 仍 0.3320 vs pre 0.5000 ⇒ 改善不依赖 MBON |
| A6 | 无未播种 RNG；不删除/放宽既有断言；stuck_ramp/oscillating/wall_stuck/micro_loop 触发与释放仍有效；**stuck 时长不得劣化** | **passed（前 3 项）/ UNVERIFIED（stuck 时长）** | diff 无任何 `random/default_rng/shuffle`；t2 未改任何既有测试文件（`changedPaths` 仅 2 个）；`tests/test_memory.py`（检测器+反射触发/释放）123 passed、stuck/escape 类定向回归 88 passed（1 项 `test_evolution_capability::test_bold_explore_decision_source` 为 `known_failures.win32.json:32` 登记基线项）。**stuck 时长无任何测量**（t2 与 t4 均未测），且 forward 突围推力对静默卡死个体由 0.5 降为 0.125（不可单独成峰） |
| A7 | 新增 `tests/test_motor_pool_dynamics.py` ≥5 项断言覆盖 **(a)–(e)** | **failed（部分, medium）** | 文件存在 10 例，覆盖 (a)(c)(d) 与另两项自选内容；但 **(b)「反射结束注入复位/衰减（非粘滞）」无任何断言**，**(e)「无新增常量级 post-leak 地板（逐写点核对 t1 §A4 的 15 个 forward 写点）」无任何断言** —— 测试文件里的 (e) 实为 `test_reflex_blend_retains_network_share`（对应已被修订删除的旧验收条款） |
| A8 | 全部 verify 退出码 0；既有测试无新增失败 | **passed** | 本次重跑 3 条 verify：`10 passed`(exit 0)、`59 passed`(exit 0)、`123 passed, 1 deselected`(exit 0)；新增失败 2 项为 `tests/test_plugin_mhr.py` LLM 型号漂移（本报告 §4.3 独立复核，与 t2 改动面无关） |
| A9 | 实现说明逐条对照 t1 §7 五条硬约束（**含 §7.4/§7.5**） | **failed（部分, low）** | t2 交付说明给出 §7.1/§7.2/§7.3/§7.5 → 改动位置的映射（t2 `acceptanceResults` 文本），**§7.4（单位契约唯一化）缺失**；且映射中 §7.2 的"不粘滞"一项与实现不符（见 A2） |
| — | t5 目标第三项：反射期保留网络份额（可配置、默认 ≥25%） | **未运行时交付（info）** | `blend_reflex_control()` 已实现且单测通过，但**生产代码零调用点**（全仓只有定义 + 测试 + `scripts/verify_motor_pools.py`）；t2 已声明"待 t7 接线"，属**声明性延后**，非隐瞒，但在 t7 接线前无任何运行期效果 |

**结论**：t2 **正确抓住了 t1 推翻 MBON 假设后的真实主因方向**（floor 拆分 + 去对称钳位 + 占用率负反馈），并且 steering 复活、共放电、pre/post 地板差分都可独立复现；**但主诉求"消除 post-leak 恒流地板 / 恢复 forward 动态范围"只在 `escape_mode=False` 且 `osc≈0` 的有利角落成立**。活体可达条件（`escape_behavior=True`，伴随 `_escape_forward_accum` 由 `_last_disp_x` **永不被赋值**而恒被顶到上限、`escape_current` 0.15–0.25 注入整个 motor pool）下，负反馈的权限（仅 MBON 通路 ≤0.35·|mb|·gain 与 forward tonic ≤0.135）**根本覆盖不到这两路常量大项**，占用率回到 0.68–1.00。此外 A2（粘滞 reflex_forward）**未实现却被标为 passed**，其证据指向另一机制；A7 要求的 (b)(e) 两项断言缺失。因此必须 `needs_revision`，由 t2 修复者补齐后重新走 t4/t5。

---

## 1. t2 实际改了什么（逐 hunk，与 t1 §7 对齐）

```
$ git diff HEAD -- fly64/fly64/model.py
@@ -639,6 +639,39   @@  新增 6 个参数：fwd_occ_tau/ref/ full/ homeo_floor、_fwd_occupancy、
                          _fwd_homeo_gain、_fwd_tonic_current、breakout_forward_osc_floor、
                          reflex_network_share、last_reflex_mix、last_lif_jump
@@ -1297,6 +1330  @@  新增 3 个纯函数：forward_homeo_gain()、breakout_split()、blend_reflex_control()
@@ -1512,10 +1649 @@ step():  ①占用率 EWMA + gain 计算（1654-1660）；②MBON 注入 ×gain（1665-1666）；
                                    ③recall 注入 ×gain（1689-1690）
@@ -1610,6 +1761  @@ step():  ④forward tonic 腿 ×gain（1771-1772，负项）
@@ -1815,15 +1975 @@ step():  ⑤R16 breakout 改为 breakout_split()：fwd×max(0.25,osc)、
                                    turn(每侧)×osc×0.5、jump 分支仍用 raw（1988-1996）
@@ -2138,6 +2308 @@ decode(): ⑥last_lif_jump 镜像（2313）
```
即 `step()` 共动 3 条 limb（与 t4 §2.2 一致），**未触碰**：`TurnAdaptation.breakout_drive/counter_drive/update`（§A5/§B2 的疲劳积分本体）、`escape_current` / `_escape_forward_accum` / `_last_disp_x`、`reflex_forward` 注入腿（`model.py:1855-1856`）、`mushroom_body.py`、pit/R22 两条 stuck 门控开环注入（`model.py:2029/2047`）。

**§A4 的 15 个 forward 写点占用率覆盖审计（本次逐点核对；t2 未新增正向写点，仅在 tonic 腿新加 1 项负项）**

| 现在行 | 项 | 是否读本池占用率（t2 后） | 门控 |
|---|---|---|---|
| 1665 | `mbon[0]·gain·_fwd_homeo_gain` | **是（新增）** | 恒定 |
| 1689 | `recall[0]·gain·0.5·_fwd_homeo_gain` | **是（新增）** | recall 命中 |
| 1772 | `−(tonic·(1−_fwd_homeo_gain))` | **是（新增，负）** | 恒定 |
| 1779 | `escape_current`（`motor_nodes` 整池） | **否** | `escape_mode`（活体 True 12/12） |
| 1807 | `_fallen_forward` | 否 | fallen 相 |
| 1845 | `_escape_forward_accum`（0.15→**0.20/0.50**） | **否** | `escape_mode` + `_disp < 0.5`（见 §3.2） |
| 1856 | `min(0.20, reflex_forward·0.003)` | **否（粘滞，A2 目标，未改）** | `reflex_forward` 非零（永不复位） |
| 1867 | coach forward ≤0.50 | 否 | coach_active |
| 1962 | interactive 接近 0.10 | 否 | interactive_near |
| 1990 | `_fwd_brk = raw·max(0.25, osc)` | **否** | `stuck_duration>30`（osc=0 时仍 0.125 常量） |
| 2010/2016/2029/2037/2047 | cliff −0.08 / rest 0.12 / pit `0.40·hop` / scene −0.06 / R22 0.08 | 否 | 事件门控 |
| 2063 | `ou_state[0]·0.15`（`motor_nodes` 切片，t1 的 §A4 第 15 项） | 否 | 每池标量共模（§B3） |

⇒ **没有任何"新增常量级 post-leak 地板"**（A7(e) 的第一半"无新增"成立），但 **`escape_*`(两路)、粘滞 `reflex_forward`、breakout 前向地板仍完全在负反馈权限之外** —— 这正是 A3 在 live-like 档失败的直接原因。

---

## 2. 硬约束核验（t5 acceptance 第 2–5 条）

### 2.1 未越界（passed）

```
$ git diff HEAD --name-only | grep -E 'main.py|brain_tunable_params|plugin/'
fly64/fly64/main.py                    <- t3 的 inScope（RULE-19 gate 单位），非 t2
fly64/skills/brain_tunable_params.json <- t3 的 inScope（阈值改 Hz 域），非 t2
fly64/plugin/.consult_request.json     <- 运行期产物（模型名从 glm-5.3-flash → qwen3.8-27b-uncensored + ts），非 t2
```
- `git diff HEAD -- fly64/fly64/main.py | grep blend_reflex|last_reflex_mix|reflex_network_share` → **空**：t2 未在 main.py 接线（与其自述"待 t7"一致）；
- `main.py` 的新增行首块为 `# ── RULE-19: motor-pool rate unit contract (per-tick fraction ⇄ Hz) ──`，全部属 t3 的 gate 单位契约；
- t2 `changedPaths` 声明 = `fly64/fly64/model.py`、`fly64/tests/test_motor_pool_dynamics.py`；`git diff HEAD -- fly64/fly64/model.py` 的全部 hunk 均为 T2 注释/逻辑，**无 gate、无 main、无 plugin**。
⇒ **越界：无**。

### 2.2 未删除/放宽既有断言（passed）

```
$ git diff HEAD --stat -- fly64/tests
 fly64/tests/_live_writeout_check.sh          |  2 +-
 fly64/tests/_live_writeout_probe.py          |  2 +-
 fly64/tests/test_coach_pipeline.py           |  4 ++--
 fly64/tests/test_environment_protocol.py     |  4 ++--
 fly64/tests/test_fix_template_interpreter.py | 21 +++++++++++++++++----
 fly64/tests/test_plugin_mhr.py               |  4 ++--
 fly64/tests/write_llm_env.sh                 |  2 +-
```
- 这些改动**不在 t2 的 changedPaths 内**，且逐条核对内容与运动池无关：`test_plugin_mhr.py` / `test_coach_pipeline.py` / `_live_writeout_probe.py` 是 LLM 型号字符串漂移（`glm-5.3-flash → glm-5v-turbo`，属其他并发工作流）；`test_environment_protocol.py` 是 `MockBridge.write_control(x,y,jump,enabled) → write_control(control)` 签名对齐（对应 `environments/protocol.py` 的并发改动，属其他工作流）；`test_fix_template_interpreter.py` 属 t8/t9 线。
- **运动池 / stuck / steering 相关断言零改动**；t2 未修改任何既有测试文件（新增文件为 `?? fly64/tests/test_motor_pool_dynamics.py`）。
- 注意（供 t7 记录）：工作区对 `test_plugin_mhr.py` 的期望值改成 `glm-5v-turbo`，而 `fly64/plugin/manifest.json` 实为 `qwen3.8-27b-uncensored`，故该 2 例在工作区**仍失败**（不是"改绿"），`HEAD` 版本亦失败（t4 §9.3 的对照实验 + 本次 §4.3 复核一致）。

### 2.3 未引入未播种 RNG（passed）

```
$ git diff HEAD -- fly64/fly64/model.py | grep -E 'random|shuffle|permutation|default_rng'
(空)
```
- 新增代码只用 `np.exp / np.clip / round / min / max`，纯确定性；
- 新测试文件里唯一的 RNG 是 `np.random.default_rng(7)`（`tests/test_motor_pool_dynamics.py:46`，已播种），夹具 `FlyModel(demo=True, seed=64)` 已播种；
- `escape_mode` 分支内的 `self.rng.random()`（`model.py:1820`）、探索惯性 `self.rng.random()`（`model.py:1945`）为**既有**代码，用模型自带已播种 `rng`，t2 未改。
⇒ **回放契约未被破坏**。

### 2.4 反射脱困能力未劣化（**部分未验证**）

- **释放条件未被放宽（代码证据）**：`git diff HEAD -- fly64/fly64/model.py` 不含 `memory.py` 检测器、`main.py` 反射/异常状态机、`FailureMemory`、`ReflexController` 的任何一行 ⇒ `stuck_ramp/oscillating/wall_stuck/micro_loop` 的触发/释放判据（`memory.py:1319-1400`、`main.py` 反射分支）逐字未变。
- **定向回归（本次执行，exit 0 for 88/89）**：
  ```
  tests/test_reflex_jitter.py tests/test_escape_release.py tests/test_evolution_capability.py
  tests/test_cx_loop_break.py tests/test_escape_outcomes.py -q
  → 1 failed, 88 passed
    FAILED tests/test_evolution_capability.py::TestEvoRound10::test_bold_explore_decision_source
  ```
  该失败项在 `tests/known_failures.win32.json:32` **已登记为基线**（`git diff HEAD -- fly64/fly64/main.py` 的 RULE-19 块不含 `decision_source` 行）⇒ 非 t2 新增。`tests/test_memory.py`（三个 anomaly 状态 + 四个 reflex 触发/释放）在 verify#3 中 123 passed。
- **stuck 时长未验证（结论 UNVERIFIED）**：t2 与 t4 都没有给出任何 stuck 时长指标（`memory.json.stuck_duration` 或仿真净位移）。可量化的风险相反方向是有的：**对"卡住但转向池静默"的个体，R16 前向突围推力由 `raw=0.500` 降为 `0.125`**，而 `0.125 V/tick` 的后漏电稳态仅 `0.125/(1−a)=0.690 < threshold 1.0` ⇒ **该腿单独不可使 forward 池放电**（本报告 §3 臂 A1：post 0.0000 vs pre 0.3336）。t2 测试只断言 `fwd > 0.0`（`test_motor_pool_dynamics.py:229`）与"live-like 臂 occ>0.2"，**都不是推力有效性证据**（后者靠 tonic+reflex 等其它腿撑起）。因此"escape capability preserved"目前**只有弱的断言级证据**，且一旦 A2 的粘滞 reflex 被正确复位（`−0.20 V/tick`），osc≈0 情形下的残余地板仅 `0.125+0.045=0.17`（T≈8，≈6 Hz），突围裕度会进一步收紧。

---

## 3. 本次独立测量（t5 自有探针，原始输出）

构型与 t4 同源作对照（`w=0`、`visual_connected=False`、探索惯性冻结、`mirror_mb=0.96` 关闭 pit/R22 门控、`anomaly_state_name="oscillating"`、`FlyModel(demo=True, seed=64)`、400 tick/warm 150），**新增 t4 未测的臂**。`PRE` = 实例级重建修复前路径（t4 §2.2 的 3 行替换）。

### 3.1 复现闸门（与 t4 §4/§5.1 对比，证明 harness 可信）

```
A1  brk-only (0.500)                fwd=0.0000 ( 0.00 Hz)  split=[0.125, 0.0, 0.5]
A2  brk+tonic (0.680)               fwd=0.2091 (10.45 Hz)
A3  brk+tonic+sticky reflex (0.880) fwd=0.3320 (16.60 Hz)  gain=0.908
A3p 同臂 PRE                        fwd=0.5000 (25.00 Hz)  gain=1.000
   （t4 §4：pre 0.5004 / post 0.3336；t4 §5.1：post mb=0→0.3336 — 本次 0.3320，一致）
```

### 3.2 escape 开启（= 活体条件）：**A3 失败的直接证据**

活体事实：`main.py:1161` `model.escape_mode = memory_ctrl.escape_behavior`；t1 采样 `escape_behavior` **12/12 True**，本次审查当时再取 `flow.json` 仍为 `escape_behavior=True`、`forward_rate=1.0`。而 `model.py:1835-1836` 读 `getattr(self,"_last_disp_x",0.0)` / `_last_disp_z`，**这两个属性在全仓（含 HEAD）没有任何写入点**（`grep '_last_disp_x\s*='` 命中仅本审查探针）⇒ `_disp ≡ 0 < 0.5` **恒成立** ⇒ `_escape_forward_accum` 每 tick `+0.005` 一路顶到 `_max_escape_forward` 并保持。活体 `active_strategy.json:19` 为 `exploration.breakout_forward_bias = 0.2` ⇒ 活体上限 **0.20**（`main.py:1413` 默认值 0.50 为未配置时的取值）。

```
[D0] escape only, stuck=0, reflex=0, tonic=0, cap=0.50   fwd=0.5000 (25.00 Hz) acc=0.500
[L8] escape only (stuck=0,rf=0,tonic=0,mb=0,cap=0.20)    fwd=0.3083 (15.42 Hz) acc=0.200
[L9] escape + 粘滞 reflex only (mb=0,tonic=0,cap=0.20)   fwd=0.4994 (24.97 Hz) acc=0.200  ← 恰好 T=2 边界
[L1] 活体参数 cap=0.20 + 粘滞 reflex 0.2 + tonic 0.18 + brk(0.125) 的 mb 扫描：
     mb=-1.0000 → fwd=0.6831 (34.15 Hz)
     mb=-0.8861 → fwd=0.8031 (40.15 Hz)
     mb=+0.0000 → fwd=0.9465 (47.32 Hz)      gain=0.259
     mb=+0.2384 → fwd=0.9787 (48.94 Hz)
     mb=+0.9633 → fwd=0.9979 (49.90 Hz)      gain=0.250（负反馈已顶到下限）
[L2] 同 L1 但 escape_current=0.25（活体上界）           fwd=1.0000 (50.00 Hz)
[L3] 同 L1 但 reflex_forward=0（去掉粘滞项）             fwd=0.7391 (36.95 Hz)
[L4] 同 L1 但 tonic=0                                   fwd=0.5000 (25.00 Hz)
[L5] cap=0.50（`breakout_forward_bias` 未配置）          fwd=1.0000 (50.00 Hz)
[L6] L5 PRE-emulation                                   fwd=1.0000 (50.00 Hz)
[L7] L1 PRE-emulation（活体参数）                       fwd=1.0000 (50.00 Hz)
```
**读数**：
1. 活体可达条件下 **post 占用率 0.6831–0.9979（34.15–49.90 Hz）**，与活体基线 **34.6–50.0 Hz（mean 45–46）** 不可区分 ⇒ A3 的 "<50% 且显著低于饱和线" **不成立**；
2. `breakout_forward_bias` 未配置（默认 0.50）时 post = **1.0000（50.00 Hz）**，与 pre **完全相同** ⇒ 该条件下修复对 forward 贴顶 **零效果**；
3. 负反馈 `_fwd_homeo_gain` 已到下限 `0.250`（`gain=0.250`）而占用率仍近 1.0 ⇒ 权限耗尽，因为 `escape_current + _escape_forward_accum + 粘滞 reflex + breakout 地板` ≈ `0.20+0.15+0.20+0.125 = 0.675`（tonic 已降至 0.045）> T=2 阈值 0.550，甚至逼近 T=1；
4. t2 的测试臂与 t4 的 "live-like" 臂（t4 §2.3 明示 `escape_mode=False`）**恰好把这两路最大常量项排除在外**，因此两处都测到"修复成功"。

### 3.3 osc=1（织网态）：breakout 全额支付且不受占用率反馈

```
[C0]  osc=1, mb=0, reflex=0, tonic=0     fwd=0.5000 (25.00 Hz) split(fwd=0.8500, raw=0.8500)
[C0p] 同臂 PRE-emulation                  fwd=0.5000 (25.00 Hz)
[C0b] osc=1, mb=0, reflex=0, tonic=0.18   fwd=0.5000 (25.00 Hz)
[C0c] osc=1, mb=0.96, reflex=70, tonic=0.18 fwd=1.0000 (50.00 Hz) gain=0.250
[C0d] osc=0.5   (fwd 腿 0.3375)           fwd=0.2309 (11.54 Hz)
[C0e] osc=0.17 + stuck=120s (fwd 腿 0.1024) fwd=0.0000
```
`osc = min(left,right)/saturation`，而 `TurnAdaptation.update`（`model.py:365-369`）为**无上限积分**：转向池按 12.5 Hz 放电（= t4 测得的复活后 0.2502/0.2572 占用率）稳态疲劳 = `3.01×rate ≈ 0.75 > saturation 0.5` ⇒ **osc→1**。于是 `breakout_split` 给 forward 全额 `raw≥0.5`，而该腿**无占用率反馈**：仅 C0 臂即 **0.5000（25.00 Hz）= 恰好 50% 上限（不满足严格 `<50%`）**；叠加粘滞 reflex 与 tonic 后 **1.0000**。t4 只测了 `breakout_split` 的返回值（其 §6.2），未测 osc=1 下的**池占用率**，故遗漏该面。

### 3.4 A2 粘滞：直接测量

```
[D1] sticky rf=70（与 A3 同构型）  fwd=0.3320  max_v=0.9776
[D2] rf=0        （其余完全相同）  fwd=0.2091
Δocc = +0.1229  ← 全部来自 min(0.20, 70*0.003) = 0.200 V/tick 的常驻注入
rf_before/after（rf=70 臂跑 400 tick）= [70, 70]   ← model.step() 从不改写该标志
model.py 中 self.reflex_forward 的赋值点 = ['self.reflex_forward = 0']  ← 只有 __init__(model.py:727)
```
⇒ 判据"反射结束后注入归零或按明确时间常数衰减"**未被实现**，且模型侧本可就地实现（衰减/超时归零都在 `model.py`，属 t2 inScope）。

### 3.5 steering（独立复现 A4 通过）

```
pre  （A3p / B2p / D3p 等 PRE 臂）  L=0.0000 R=0.0000  cofire=0/250, 0/250, 0/250
post （A3 / L1 / L9 臂）            L=0.0142–0.2370  R=0.0805–0.1498  cofire=35/250, 48/250, 220/250
```
两池各自非零 ✓；共放电实例存在 ✓；pre 的 never-co-fire 与 turn 池 0.000 复现 ✓（与 t1 §B4/E8b、t4 §6 三方一致）。

---

## 4. 复核 t2/t4 的既有结论（不得只依赖自述）

### 4.1 与 t4 一致的部分（本次独立复现）

| 量 | t4 | 本次 | 判读 |
|---|---|---|---|
| pre 地板占用率（w=0，0.88 地板） | 0.5004（25.02 Hz） | 0.5000（25.00 Hz） | 一致 |
| post 地板占用率（同臂） | 0.3336（16.68 Hz） | 0.3320（16.60 Hz） | 一致 |
| brk-only post | 0.0000（t4 §4 表首行） | 0.0000 | 一致 |
| steering pre → post | 0.0452/0.0621 → 0.2502/0.2572 | 0.0000/0.0000 → 0.1424/0.1280（escape 臂） | 同向、同量级 |
| 共放电 pre/post | 0/95 → 94/95 | 0/250 → 48/250, 220/250 | 一致（严格互斥已破） |

### 4.2 t4 已列但未升级为结论的两项，本次升级为 findings

- **U6（余量 0.0011）**：t4 记为 low；本次显示该余量是"结构上限的偶然穿越"，一旦加上 t4 自己排除的 escape 腿就立刻越界（§3.2）⇒ 升级为 **blocker**。
- **U1（`reflex_forward` 粘滞 UNCLOSED）**：t4 归因"属 main.py/t7"，但 t2 的 acceptance A2 明确要求**注入侧**"归零或按明确时间常数衰减"，该注入在 `model.py:1856`（t2 inScope）；且 t2 自己把该项标为 passed 并给出不符的证据 ⇒ 升级为 **high**。

### 4.3 独立复核"2 项 NEW 失败与本任务无关"（t4 §9.3）

```
$ python -m pytest tests/test_plugin_mhr.py -q
2 failed, 44 passed
  assert req["model"] == "glm-5v-turbo"  ->  'qwen3.8-27b-uncensored'
  assert m["llm"]["model"] == "glm-5v-turbo" -> 'qwen3.8-27b-uncensored'
```
断言只涉及 LLM 型号字符串；`plugin/**` 不含运动池代码；t2 改动面不含 `plugin/**`；`known_failures.win32.json` 记录时间 `2026-09-23T01:09:27Z` 早于把 manifest 改为 `qwen3.8-27b-uncensored` 的 commit `78b3175`（12:42 +0800）⇒ **该 2 项为 test-drift，与 t2 无关**，t4 的归因成立。

### 4.4 verify 命令（本次原样重跑，契约命令）

```
cd fly64; $env:TEMP='D:\codes\flygym\.tmp-pytest'; $env:TMP=$env:TEMP
$ python -m pytest tests/test_motor_pool_dynamics.py -q
10 passed in 121.24s (0:02:01)                 EXIT=0
$ python -m pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_cpg_priority.py -q
59 passed in 2.54s                             EXIT=0
$ python -m pytest tests/test_memory.py tests/test_optic_flow.py \
    --deselect tests/test_optic_flow.py::test_flow_computation_performance -q
123 passed, 1 deselected in 10.11s             EXIT=0
```
⇒ A8 成立（临时目录重定向后退出码 0，与队长环境事实一致）。

---

## 5. Findings（needs_revision 依据）

| id | severity | 问题 | 必须的修复 | file:line |
|---|---|---|---|---|
| F1 | **blocker** | **A3 在活体可达条件下失败**：`escape_mode=True`（活体 `escape_behavior=True` 12/12，审查当时仍 True）时 post forward 占用率 **0.6831–0.9979（34.15–49.90 Hz）**，与活体基线 34.6–50 Hz 不可区分；`breakout_forward_bias` 未配置（默认 0.50）时 **1.0000（50.00 Hz）= pre**。占用率负反馈只覆盖 MBON 通路与 forward tonic，**不覆盖** `escape_current`（`model.py:1779`）与 `_escape_forward_accum`（`model.py:1845`，因 `_last_disp_x/_last_disp_z` 全仓无写入点而恒被顶到上限 0.20/0.50） | 把 homeostat（或等价占用率负反馈/上限）扩展到 escape 两腿与 breakout 前向腿；同时处理 `_last_disp_x` 无写入点这一死读（接线或封顶）；**在 `escape_mode=True`（活体参数 `breakout_forward_bias=0.2`）下重做 A3 的 live-like 档测量，占用率必须实测 < 50%**；t4 的 "live-like" 臂须包含 escape | `fly64/fly64/model.py:1779,1835-1845,1990` |
| F2 | **high** | **A2（粘滞 reflex_forward）未实现却标 passed**：`model.py:1855-1856` 一字未改，"反射结束后注入归零或按明确时间常数衰减"无任何实现；实测 400 tick 后 `reflex_forward` 仍为 70，该腿单独贡献占用率 +0.1229，并把 live-like 占用率从 0.7391（无该腿）抬到 0.9979 | 在 `model.py` 就地实现到期/衰减（例如反射标志 N tick 未刷新则按 τ 衰减归零），或把该腿也纳入占用率负反馈；若坚持归 t7，必须把 A2 从 t2 acceptance 中移除并显式登记为 t7 的阻塞项 | `fly64/fly64/model.py:1855-1856`（写点在 `fly64/fly64/main.py:1563,1642,1901`） |
| F3 | high | **交付说明的事实性错误**：A2 的证据写为"`blend_reflex_control()` 实现反射期混合；model 侧注入不粘滞"——后者与代码/实测相反（§3.4），前者是输出侧机制、与粘滞注入无关。质量门不能以该证据判 pass | 更正 acceptanceResults 证据与说明；补充粘滞项的实测数据 | t2 `acceptanceResults[1].evidence` |
| F4 | medium | **A7 要求的 (b)(e) 两项断言缺失**：(b)"反射结束注入复位/衰减（非粘滞）"无任何测试；(e)"无新增常量级 post-leak 地板（逐写点核对 t1 §A4 的 15 个写点）"无任何测试——文件里的 (e) 实为 `test_reflex_blend_returns_network_share`（对应已被修订删除的旧条款） | 补两项测试：(b) 断言反射标志过期后注入衰减/归零；(e) 用 AST/正则穷举 `self.v[self.forward]` 写点并断言每个常量项要么被占用率反馈覆盖、要么有事件门控且单独亚阈 | `fly64/tests/test_motor_pool_dynamics.py` |
| F5 | medium | **osc→1 时 breakout 前向腿全额支付且无占用率反馈**：仅该腿即 0.5000（25.00 Hz）= 恰好 50% 上限（不满足严格 <50%）；叠粘滞 reflex/tonic 后 1.0000。而转向池复活（0.25 占用率）稳态疲劳 ≈0.75 > saturation ⇒ osc→1 是修复后的**可达稳态**，即该修复的副作用会把 forward 重新顶回天花板 | breakout 前向腿也纳入占用率反馈（或把 0.25 下限改为对饱和池不叠加）；在 osc=1 臂上把"占用率 < 50%"作为验收实测项 | `fly64/fly64/model.py:1988-1990`；`fly64/fly64/model.py:365-369` |
| F6 | medium | **"反射脱困能力保留"只有弱证据 + stuck 时长未验证**：forward 突围推力对静默卡死个体由 0.500 降到 0.125（后漏电稳态 0.690 < 阈值，**单独不可成峰**；brk-only 臂 post 0.0000 vs pre 0.3336），而测试只断言 `fwd > 0.0` 与"live-like occ>0.2"（后者靠其它腿支撑）；A6 要求的"stuck 时长不得劣化"在 t2 与 t4 均无任何测量 | 给出 stuck 时长的定量对照（同 harness pre/post，或活体 net displacement / `stuck_duration` 时间序列）；把"推力有效性"断言从 `>0` 升级为"在有/无 breakout 腿时静默卡死个体的 forward 占用率差 > x" | `fly64/tests/test_motor_pool_dynamics.py:229,260`；`fly64/fly64/model.py:1839-1845` |
| F7 | low | **A9 缺 §7.4 映射**：交付说明给出 §7.1/§7.2/§7.3/§7.5 → 改动位置的映射，但未提 §7.4（单位契约唯一化，t3 领域）；按 acceptance 应显式写出"§7.4 属 t3，t2 不涉及/不冲突" | 补 §7.4 一行映射（说明归属与不冲突依据） | t2 `acceptanceResults` |
| F8 | info | **反射期网络份额未运行时交付**：`blend_reflex_control()` 生产代码零调用点（仅定义 + 测试 + t4 脚本），t5 目标第三项在 t7 接线前无运行期效果；t2 已声明延后（非隐瞒） | 由 t7 完成接线并在活体/集成验证中覆盖"反射期 LIF 份额 ≥25%" | `fly64/fly64/model.py:1391-1434`（接线目标 `fly64/fly64/main.py:1550-1552` 区段） |

**方向性判断（回答审查要点"是否仍基于被推翻的假设"）**：**否**。t2 未用 MBON/R17 当修复手段（A5 passed，`mb=0` 时仍 0.3320 vs pre 0.5000）；floor 拆分与去对称钳位正对 t1 §A5/§B4。问题不在方向，而在**覆盖度**：只覆盖了 t1 §A5 列出的 3 项地板中的 1 项（tonic）＋ 部分削弱 breakout，**漏掉了活体实测中更大量级的 escape 两腿**，且 t1 §7.2 明列的"粘滞 reflex_forward"完全未做。所以是"方向对、未完成 + 验收自述失真"，必须 needs_revision 而不是 reject。

---

## 6. 复现命令（本次全部证据）

```powershell
# 0) 被审查状态指纹
cd D:\codes\flygym; git diff HEAD --stat -- fly64/fly64/model.py fly64/tests
Get-FileHash fly64\fly64\model.py -Algorithm MD5     # a2d4242d29534351297da7472e8e88f9

# 1) 本次 t5 探针（三条，均为只读：实例属性替换，不改源码）
cd D:\codes\flygym\fly64
..\.venv\Scripts\python.exe -u D:\codes\flygym\.tmp_t5\reviewer_probe.py    # §3.1 §3.3 §3.4
..\.venv\Scripts\python.exe -u D:\codes\flygym\.tmp_t5\reviewer_probe2.py   # escape/osc 分解
..\.venv\Scripts\python.exe -u D:\codes\flygym\.tmp_t5\reviewer_probe3.py   # 活体参数 cap=0.20 扫描
#   原始输出：.tmp_t5\t5_probe_output.json / t5_probe2_output.json / t5_probe3_output.json

# 2) 契约 verify（TEMP 重定向，规避 sessionfinish PermissionError）
cd D:\codes\flygym\fly64
New-Item -ItemType Directory -Force D:\codes\flygym\.tmp-pytest | Out-Null
$env:TEMP='D:\codes\flygym\.tmp-pytest'; $env:TMP=$env:TEMP
..\.venv\Scripts\python -m pytest tests/test_motor_pool_dynamics.py -q
..\.venv\Scripts\python -m pytest tests/test_mushroom_body.py tests/test_brain_alternation.py tests/test_cpg_priority.py -q
..\.venv\Scripts\python -m pytest tests/test_memory.py tests/test_optic_flow.py --deselect tests/test_optic_flow.py::test_flow_computation_performance -q

# 3) stuck/escape 定向回归 + 基线归属
..\.venv\Scripts\python -m pytest tests/test_reflex_jitter.py tests/test_escape_release.py tests/test_evolution_capability.py tests/test_cx_loop_break.py tests/test_escape_outcomes.py -q
..\.venv\Scripts\python -m pytest tests/test_plugin_mhr.py -q
Select-String -Path tests\known_failures.win32.json -Pattern 'test_evolution_capability|plugin_mhr'

# 4) 活体只读采样
Invoke-WebRequest http://127.0.0.1:8765/flow.json -UseBasicParsing | Select-Object -Expand Content
#   escape_behavior=True, forward_rate=1.0, gate_forward=True, gate_jump=False, 无 *_hz 键

# 5) 死读核查（escape 上限恒被顶满的机理）
cd D:\codes\flygym; Get-ChildItem -Recurse -Include *.py -File | Select-String -Pattern '_last_disp_x\s*='
#   生产代码零命中（只有 .tmp_t5 探针）
```

---

## 7. 证据限制 / 诚实清单

1. **离线夹具**：`FlyModel(demo=True)`（4096 神经元合成图，`fly64/.cache/malecns` 本机不存在）⇒ 只证明**机制与算术**（占用率、限周期、注入分解），绝对量级不代表真实 MaleCNS。t4 §5.2 已报告 `w_scale=1.0` 时 pre/post 均贴顶；本次的 `w=0` 臂与此互补，不能替代真实连接组。
2. **连接组回投电流未建模**：本审查的 `w=0` 臂缺 `_synaptic_buf`；活体该量存在（t1 §5.5）。因此 §3.2 的 34.15–49.90 Hz 是**下界性质**的活体预测（活体基线 34.6–50 Hz 与之同区间）。
3. **osc=1 臂**用实例级冻结疲劳（`_turn_adapt.update` 替换）构造，代表"双池刚织过网"的状态；其可达性论证（复活后 0.25 占用率 ⇒ 稳态疲劳 0.75 > saturation）为解析推算，未在闭环中实测。
4. **stuck 时长**：本机无端到端（main.py+桥接）跑动条件，未测量；故 A6 的该项列为 UNVERIFIED 而非 failed。
5. **活体未部署修复**（deployed `model.py` md5 = HEAD = 修复前，t4 §10 一致），本报告所有"post"读数均为**工作区代码的离线实测**，不含活体验证；活体部分仅作基线复测与 `escape_behavior=True` 的条件取证。
6. 未测量的量一律标注"推算/未测量"，无推算冒充实测。
