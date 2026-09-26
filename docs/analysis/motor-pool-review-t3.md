# t6 质量审查报告 —— t3（gate 单位契约统一与可达性证明）

- **任务**：t6 — 审查 t3：gate 单位契约统一与可达性证明的真实性
- **被审查对象**：t3 实现（`fly64/fly64/main.py` gate 段、`fly64/skills/brain_tunable_params.json` 两条 gate 参数、`fly64/docs/declared-not-implemented.md`、新增 `fly64/tests/test_gate_units.py`）
- **审查对象状态**：工作区未提交状态；`git diff HEAD --stat`：`fly64/fly64/main.py +95/-3`、`fly64/skills/brain_tunable_params.json 8+/8-`、`fly64/docs/declared-not-implemented.md`（含重新生成段与手工段）、`?? fly64/tests/test_gate_units.py`
- **证据来源**：
  1. 代码 diff（`git diff HEAD -- main.py / brain_tunable_params.json / declared-not-implemented.md`、`git status`）
  2. t1 根因报告 §4（gate 契约破裂的现场证据：同一 tick 两路 producer 相反 26/26）
  3. t4 独立验证报告 §8 与其脚本 `fly64/scripts/verify_motor_pools.py::section_gate_units`（只作对照，不作唯一证据）
  4. **本次自建探针（t6 独有，方法不同源）**：`.tmp_t5/reviewer_probe_t6.py` —— 用 AST 从 `main.py` 抠出 `flow.json` 段落的 **6 条赋值语句**与 `gate_forward`/`gate_jump` 两个字典值表达式，配合 stub `model/control/_expl` **真实执行生产表达式**（非重实现）；同样方式抠出 `telemetry.py` 的 `gate_forward`/`gate_jump` Compare 并执行，从而在同一 tick 上对比两路 producer。原始输出 `.tmp_t5/t6_probe_output.json`
  5. 活体只读采样（HTTP `flow.json` / `memory.json`，审查当时）
- **审查纪律**：不修改任何被审查文件；本轮只新增 `docs/analysis/motor-pool-review-t3.md` 与 `.tmp_t5/` 探针。

---

## 0. 裁决（TL;DR）

**verdict = pass**（t3 的 6 条 acceptance 全部通过），附 6 条**不阻塞**的残留 findings（F1–F3 medium 建议 t7/后续任务收口；F4–F6 low）。

| # | t3 acceptance | 裁决 | 关键证据 |
|---|---|---|---|
| T3-1 | gate 判定两侧量纲一致（同为 Hz），注释与 schema 显式标注单位 | **passed** | `main.py:779-806` 新增 `GATE_RATE_DT_DEFAULT`/`rate_per_tick_to_hz`/`gate_open_hz`（单一比较入口，单侧换算，严格 `>`）；`main.py:2497-2510` 单次换算并发布 `forward_rate_hz/turn_rate_hz/jump_rate_hz` 与 `gate_forward_threshold_hz/gate_jump_threshold_hz`；`main.py:2572-2573` `gate_open_hz(*_hz, *_hz)`；注释在 helper 块、flow.json 站点、`jump_not_active`（`main.py:2679-2682`）三处标明 PER-TICK vs Hz；schema 两条描述均含「单位：Hz」+ 每-tick 观测侧 + `1/dt` + telemetry 一致性。**本次以 AST 执行生产表达式复核**：`gate_jump = gate_open_hz(13.8, 8.0) → True` |
| T3-2 | gate_jump 不再恒假；jump 池达阈值 Hz 时 True；PIN 含边界 | **passed** | 生产表达式执行（`t6_probe_output.json` sweep）：per-tick 0.276 → 13.8 Hz → **True**；0.16 → 恰好 8.0 Hz → **False**（边界闭合）；0.1600001 → **True**；0.0 → **False**；1.0 → 50 Hz → **True**；活体调参值 3.082 Hz 下 3.075 Hz→False / 3.085 Hz→True。`tests/test_gate_units.py::test_gate_jump_is_reachable_at_the_measured_pool_rate` / `::test_gate_jump_boundary_is_closed_and_ceiling_is_open` 同向断言 |
| T3-3 | gate_forward 在健康池（5 Hz）可开、静默池关闭，不再依赖 saturation | **passed** | 生产表达式执行：5.0 Hz→True；`raw_y` 满驱动点 2.15 Hz→True；1.95 Hz（0.039/tick）→False；0.0→False。t2 修复后 forward 池约 0.5/tick（25 Hz）> 2.0 Hz → 仍开；**静默池 0 Hz → False** ⇒ 不再是「只有贴顶才为真」 |
| T3-4 | schema 的 min/max/default 与描述单位自洽（Hz 区间合理） | **passed**（附 F1 校准 caveat） | `brain_tunable_params.json:31-43`：forward `0.4 .. 8.0`/default `2.0`；jump `2.0 .. 20.0`/default `8.0`；`0 < min ≤ default ≤ max ≤ Nyquist 50 Hz`；描述含 Hz/RULE-19/1dt/telemetry/标定来源（`model.py` 解码参照）。**注意常量为收紧而非放宽**（见 §3） |
| T3-5 | docs/declared-not-implemented.md 两条 gate_* 更新为实现态（含单位约定），不再标零消费者 | **passed** | `docs/declared-not-implemented.md:48-49`（§2b Closed decisions）两条均标 **implemented** + **Hz** + 区间 + reader + PIN；§2「Unwired tunable parameters」= **0 entries**（diff 实测）；总表 14→0、31→17。**独立核实**：schema 39/39 `wired: true`，且 39 个 pid 的叶名在 `fly64/*.py|plugin/*.py` 全部 ≥1 处出现（零消费者 = 0 个）；`tests/test_tunable_wiring.py:253-270` 为真实守卫（AST 读点 + `test_wired_set_is_the_whole_registry`）⇒「0 unwired」不是把 12 条待决策项静默抹掉 |
| T3-6 | 新增 test_gate_units.py ≥5 项 + test_strategy_key_contract.py 全绿 | **passed** | 文件 404 行 / 13 个测试函数（2 个 parametrize 覆盖两条 pid）= 15 items；命令实测 `22 passed`（15 + 7）、EXIT 0 |

**t6 acceptance 自评**

| t6 acceptance | 裁决 | 证据 |
|---|---|---|
| 逐一核验 t3 每条 acceptance（file:line、测试名、原始输出） | **passed** | 上表 + §1–§4（含 AST 执行原始输出） |
| 量纲统一真实、非靠调低阈值「伪造」可达 | **passed** | §3：常量为 5×/4× **收紧**；可达性来自单位换算——即使沿用旧字面值 2.0 Hz，13.8 Hz 也 > 2.0 ⇒ 可达性与阈值取值无关；且 `test_thresholds_are_calibrated_against_the_decoder_not_the_test` 把标定钉在 `model.py` 解码参照（jump 触发电平 2.0 Hz、forward onset 0.4 Hz / 满驱动 2.15 Hz） |
| gate_jump 可达 True（构造达阈值 Hz 的输入）且边界明确 | **passed** | §2.2 生产表达式执行表（含 `==阈值 → False`、`±1e-9`、Nyquist、dt=0.04 臂） |
| schema min/max/default 与描述单位自洽；docs 状态已更新 | **passed** | §1.3、§2.3、§4.2（另见 F1 校准 caveat） |
| 未越界修改 model.py / evolution_skill.py / strategy_writer.py | **passed** | §4.1：后两者 `git status` 无改动；model.py 仅被 t2 改动且其 diff 无任何 `gate_` 内容 |

---

## 1. 量纲统一的方向与依据（t6 关注点 1）

### 1.1 以 Hz 为权威与 telemetry 既有语义一致（核实）

- `telemetry.py:77-78`（本行逐字核对）：`denom = min(self.ticks, WINDOW) * m.dt`；`rates[key] = counts[ids].mean()/denom` ⇒ **Hz**（WINDOW=13、dt=0.02 ⇒ 满值 50 Hz）。
- `main.py` 的换算：`rate_per_tick_to_hz(rate, dt) = rate/dt`（`main.py:782-793`），与 telemetry 同一 `1/dt`；`tests/test_gate_units.py::test_brain_and_dashboard_agree_on_the_hz_conversion` 用真实 `Observatory` 跑 30 tick，断言 `row["forward"] == rate_per_tick_to_hz(control.forward_rate, m.dt)`（rel 1e-6）⇒ 两面同源。**本次另行实测**：该测试通过（22 passed 内含）。
- 方向正确：`Control.*_rate` 是 per-tick 比例（`model.py:1914-1916` 的 13-tick 窗口均值；HEAD 行号，工作区因他人改动已移至 2217-2219），schema/docs/telemetry 三方原本都声明 Hz ⇒ 以 Hz 为权威是**取既有声明**而非新造语义。

### 1.2 是否留下隐式单位（核实，含两处残留）

- 单一换算点：`main.py:2499-2504` 每个池恰好换算一次（AST 断言 `test_every_pool_rate_is_converted_to_hz_before_the_gate` 要求三个 `*_rate_hz` 的 arg0 是 `getattr(control, '<rate>')`、arg1 是共享 `_rate_dt`，且 `_rate_dt` 源自 `model.dt` + 文档化 fallback）。
- `jump_not_active`（`main.py:2682`）仍走 per-tick（`< 0.04`），与 `model.py:2417` 的解码触发同口径，**自洽且注释已标明**（"PER-TICK comparison (0.04/tick = 2.0 Hz): the decoder's own jump trigger … NOT the Hz gate above"）。
- **残留 1（F2）**：`telemetry.py:93-94` 仍以字面量 `0.4` / `2.0` 与 Hz 速率比较 ⇒ WS packet 的 `gate_jump` 阈值为 2.0 Hz，flow.json 的为 schema default 8.0 Hz（活体调参值 3.082 Hz）。单位已一致，但**阈值无单一来源**；本次实测两路仍会分歧（§2.2 表：jump 3.0/5.0 Hz 时 WS=True、flow=False）。
- **残留 2（F6）**：`plugin/scene_context.py:230-232` 从 `memory.json` 读 `forward_rate`/`jump_rate`，而该文档**不含这两个键**（活体 `memory.json` 实测 absent）⇒ `MotorState.forward_rate ≡ 0.0`，却在 `:370` 渲染成 `前向=0.0Hz` 进 LLM prompt。属同族"读写文档错位"，不在 t3 inScope，登记给 t7。

### 1.3 schema 描述是否显式标注单位（核实）

`brain_tunable_params.json` 两条描述均含：`单位：Hz`、`RULE-19 单位契约`、观测侧是每-tick 比例、`1/dt`（dt=0.02 → ×50）、`与 telemetry.py 一致`、标定参照（forward onset 0.008/tick=0.4 Hz、`raw_y` 满驱动 0.043/tick≈2.15 Hz；jump 触发 0.04/tick=2.0 Hz、默认 8.0=4×、max 20<Nyquist）。`tests/test_gate_units.py::test_schema_description_names_both_sides_of_the_comparison` 断言 `每-tick`/`1/dt`/`telemetry.py` 三个词组存在。

---

## 2. 可达性与边界（t6 关注点 2）——本次以**生产表达式真实执行**取证

### 2.1 方法（与 t3/t4 不同源）

`.tmp_t5/reviewer_probe_t6.py`：AST 定位 `main.py` 的 `DashboardHTTP.flow_json` 字典字面量与其前方 6 条赋值（`_rate_dt,_forward_rate_hz,_turn_rate_hz,_jump_rate_hz,_gate_forward_hz,_gate_jump_hz`），用 `compile/exec` 在 stub 命名空间（`model.dt`、`control.*_rate`、`_expl`）中执行**生产语句**，再 `eval` 字典里 `gate_forward`/`gate_jump` 的值表达式；`telemetry.py` 的两个 gate Compare 同法抠出并执行。**不是重实现**：若有人把换算挪走或写错，本探针会跟着变。

### 2.2 原始输出（节选；完整见 `.tmp_t5/t6_probe_output.json`）

```
main_assigns: ['_rate_dt','_forward_rate_hz','_turn_rate_hz','_jump_rate_hz','_gate_forward_hz','_gate_jump_hz']
telemetry_gate_literals: {'gate_forward': "rates['forward'] is not None and rates['forward'] > 0.4",
                          'gate_jump'   : "rates['jump'] is not None and rates['jump'] > 2.0"}
schema_defaults: {'exploration.gate_forward_threshold': 2.0, 'exploration.gate_jump_threshold': 8.0}

[策略文件无 gate 键 ⇒ 走 schema 默认 2.0/8.0]
per_tick  jump_hz  flow_gate_jump(8.0)  ws_gate_jump(2.0)  flow_gate_forward(2.0)  ws_gate_forward(0.4)
0.0        0.000   False               False              False                   False
0.039      1.95    False               False              False                   True     <-- 前向两面分歧
0.04       2.00    False               False              False                   True
0.06       3.00    False               True               True                    True     <-- 跳跃两面分歧
0.10       5.00    False               True               True                    True
0.16       8.00    False               True               True                    True     <-- 边界闭合
0.1600001  8.00    True                True               True                    True     <-- 边界外
0.23      11.50    True                True               True                    True
0.276     13.80    True                True               True                    True     <-- t1 实测跃迁池
0.5385    26.93    True                True               True                    True
1.0       50.00    True                True               True                    True     <-- Nyquist

[活体 persisted active_strategy.json:12-13 = forward 0.5983 Hz / jump 3.0823 Hz]
0.0615     3.075   False  (tuned 3.082)  ws True
0.0617     3.085   True   (tuned 3.082)  ws True
0.16       8.00    True                 ws True
0.276     13.80    True                 ws True

boundary: {observed==8.0Hz -> gate_jump: False, observed=8.0+1e-9Hz -> True,
           dt=0.04 (25 Hz loop): jump 0.25/tick = 6.25 Hz -> gate_jump: False}
```

### 2.3 判读

1. **恒假已消除**：flow.json 的 `gate_jump` 在 t1 实测的活体 jump 池（0.276/tick = 13.8 Hz）下为 **True**；在 t4 活体窗口的 0.2308/tick（11.54 Hz）下亦 True。
2. **边界明确且闭合**：`observed == threshold → False`；`+1e-9 → True`；`0 Hz → False`；Nyquist 50 Hz → True。且 `dt` 改变时换算与阈值同步（dt=0.04 时 0.25/tick = 6.25 Hz < 8.0 → False），说明 `_rate_dt` 真的接到 `model.dt`。
3. **PIN 与生产同向**：`test_gate_jump_boundary_is_closed_and_ceiling_is_open` / `test_gate_forward_opens_on_a_healthy_pool_without_saturation` 断言与本次执行结果一致（独立复现，非引用）。
4. **两路 producer 的分歧窗口仍存在**（F2，事实记录）：jump ∈ (2.0, 8.0) Hz 与 forward ∈ (0.4, 2.0) Hz 时 WS 与 flow.json 结论相反；活体 jump 池高于两者 ⇒ 现场不冲突，但**根因（两处无同源阈值）未闭合**。

---

## 3. 是否靠放宽常量/硬编码默认值「让测试变绿」（t6 关注点 3）

**结论：否，且方向相反（收紧）。**

| 侧 | 旧值（被当 per-tick 用） | 新值（明确的 Hz） | 相对**声明的 Hz 语义** |
|---|---|---|---|
| gate_forward_threshold | `0.4`（default），区间 `0.1 .. 0.8` | `2.0` Hz，区间 `0.4 .. 8.0` | **5× 更严**（0.4 → 2.0 Hz） |
| gate_jump_threshold | `2.0`（default），区间 `0.5 .. 4.0` | `8.0` Hz，区间 `2.0 .. 20.0` | **4× 更严**（2.0 → 8.0 Hz） |

- **可达性不依赖阈值取值**：一旦两侧同为 Hz，旧字面值 2.0 也满足 `13.8 > 2.0` ⇒ `gate_jump = True`（算术直接成立，本次探针 0.276 行即该数据）。也就是说修复来自**单位换算**，而不是"把阈值调到刚好能过"。
- **口径说明（避免误读为"放宽"）**：新阈值让门**在运行上更早开**（forward 从需要 0.4/tick=20 Hz 变成 2.0 Hz=0.04/tick；jump 从不打开变成 8.0 Hz=0.16/tick）。这是 acceptance T3-3 明确要求的语义纠正（"健康 forward 池（如 5 Hz）下可开"），不是为了让测试变绿的常量调整——按 declared-Hz 口径两个阈值都是**上调**，且可达性并不依赖这次上调。
- **反放宽的 PIN 存在且是行为级**：`test_thresholds_are_calibrated_against_the_decoder_not_the_test` 从 `model.py` **源码正则**读出解码参照（`raw_y = np.clip((forward_rate - 0.008) * 2000.0, 0, 70)` → onset 0.4 Hz、满驱动 2.15 Hz；`jump = jump_rate > 0.04` → 2.0 Hz），断言 `forward.default ∈ (0.4, 2.15]`、`jump.default > 2.0`、`min ≥ 触发点`、`max ≤ Nyquist`。**本行核对**：`model.py` HEAD 1942 / 2138 行的这两条表达式与正则一致（工作区因他人改动位于 2221 / 2417，见 F5）。
- 另：`test_main_defaults_equal_the_schema_defaults` 把 `main.py` 的两处 fallback（2.0/8.0）钉到 registry 默认值 ⇒ 不存在"回退默认值掩盖"的空间；`test_no_per_tick_rate_is_compared_against_a_hz_threshold` 遍历 main.py 全部 Compare 节点并断言旧字面量 `"gate_forward_threshold", 0.4` / `"gate_jump_threshold", 2.0` 已消失。
- **PIN 的覆盖边界（低）**：该 Compare 扫描以 `left.endswith(("forward_rate","turn_rate","jump_rate"))` 为筛子且只扫 `main.py`，因此**看不到** `telemetry.py`（`rates['forward'] > .4`）与"阈值存于变量、名字不含 gate/threshold"的写法。F2 的残留分歧正是落在该盲区里。

---

## 4. schema / docs / 越界（t6 关注点 4、5）

### 4.1 越界核查（passed）

```
$ git status --porcelain -- fly64/skills/evolution_skill.py fly64/plugin/strategy_writer.py fly64/fly64/model.py
 M fly64/fly64/model.py            <- t2 的改动（+184/-11），非 t3
$ git diff HEAD -- fly64/fly64/model.py | grep gate_     <- 空
$ git diff HEAD --stat -- fly64/skills/brain_tunable_params.json
 ... | 16 ++++++++--------   (8+/8-，仅两条 gate 条目：default/min/max/description)
```
- `evolution_skill.py`、`plugin/strategy_writer.py` **零改动** ✓；
- `model.py` 的改动全部来自 t2（§5 已审），且其 diff 不含任何 `gate_` 内容 ✓；
- `brain_tunable_params.json` 的改动**仅限于**两条 gate 参数（`wired: true` 为上下文行，未动）✓。

### 4.2 docs 登记与实际一致性（passed，附 F5 细节）

- `docs/declared-not-implemented.md` 的 §2（generated）现为 **0 entries**，两条 gate pid 不在其中；§2b（hand-maintained）两条均标 `implemented`（`wired: true`，live reader）+ `Hz` + 区间（`0.4 .. 8.0` / `2.0 .. 20.0`）+ reader（`rate_per_tick_to_hz`/`gate_open_hz`，flow.json 键名）+ PIN 文件；并记录了 RULE-19 案由、缺陷机理、边界闭合、标定来源、Nyquist 约束。
- **独立核实"0 unwired"不是静默抹除**：schema 39/39 `wired: true`（HEAD 与工作区同）；39 个 pid 的叶名在 `fly64/*.py`+`plugin/*.py` 均 ≥1 处出现（zero-consumer = 0）；原先列在 §2 的 12 个 pid（如 `escape.commit_reinforce`、`exploration.cliff_tangent_gain`、`reflex.cooldown_min`）逐个查到真实读取点（`main.py:1388-1435` 等）。生成器 `scripts/build_unimplemented_register.py:63-68` 的选择准则是 `wired is False`，并另有守卫测试 `tests/test_tunable_wiring.py`（AST 读点 + `test_wired_set_is_the_whole_registry`）⇒ 旧 §2 清单是**过期快照**（更早的审计发现后由 `ea509a9` 等提交接线并翻旗），t3 的重新生成是**修正**而非掩盖。
- F5 细节：§2b 引用的 `model.py:1912-1916`（per-tick 解码）与 `model.py:2138`（jump 触发）在 **HEAD 上逐字正确**（已用 `git show HEAD:...` 核对：1914-1916 是 `recent = np.stack(...)`/`forward_rate,... = [...]`/`float(pool.mean())`；2138 是 `jump = jump_rate > 0.04`），但工作区因 t2 的 +约160 行而移到了 2217-2219 / 2417 ⇒ 引用在当前工作区已过期（合并后需刷新）；且 §2b 是手工段，`scripts/build_unimplemented_register.py` 重跑会覆盖它（文档自身已如此警告）。

### 4.3 EVO 在该维度上是否变得真正有效（passed，附 F1 校准 caveat）

- **修复前**：判据是 `per-tick 比例 > 阈值`。取 default 2.0 时数学上不可能（per-tick ≤ 1.0）；即使 EVO 取区间下限 0.5，按 t1 实测池率 0.276/tick 也仍然关闭 —— 即对**本会话的池率**而言该维度是死维度（表观 fitness 与该参数无关）。严格地说，"恒假"是对 default 与实测池率成立，而不是对区间内每个取值都成立（0.6/tick 配 0.5 阈值本可打开）。
- **修复后**：阈值以 Hz 解释，门状态对参数**有因果响应**：`3.082 Hz → 跳池 3.075 Hz 时关、3.085 Hz 时开`；`15 Hz → 跳池 11.5 Hz 时关`。本次探针与 `tests/test_tunable_wiring.py::test_wired_set_is_the_whole_registry`/Phase-6 fitness PIN 均绿（38 passed）⇒ 维度**真实有效**。
- **F1（校准 caveat，medium）**：默认值 8.0 Hz 落在**活体观测池率之下**——t1 两个在线窗口 jump = 12.5–26.9 Hz（327 行，mean 21.2）与 t4 活体窗口 18.27–25.0 Hz（mean 21.0），而 live persisted 3.082 Hz 更低。因此在这两个观测窗口内 `gate_jump ≡ True`（我的探针 0.23/0.276/0.5385 三档全 True），即缺陷从「恒假」变成「在观测域恒真」；PIN 只断言了合成闭合态（0 Hz）与边界，**没有任何活体可达的闭合态证据**。这不是单位契约错误（契约已修好、旋钮已有效），但"门是否携带信息"仍需收口。

---

## 5. 回归与验证命令（原样重跑，TEMP 重定向）

```
cd fly64; New-Item -ItemType Directory -Force D:\codes\flygym\.tmp-pytest | Out-Null
$env:TEMP='D:\codes\flygym\.tmp-pytest'; $env:TMP=$env:TEMP
$ python -m pytest tests/test_gate_units.py tests/test_strategy_key_contract.py -q
22 passed in 5.73s                                                     EXIT=0     (verify#1)
$ python -m pytest tests/test_dashboard_protocol.py tests/test_phase6_fitness_inputs.py -q
32 passed in 24.80s                                                    EXIT=0     (verify#2)
$ python -m pytest tests/test_tunable_wiring.py tests/test_telemetry_completeness.py tests/test_evo_tunable.py -q
38 passed in 2.68s                                                     EXIT=0     (本轮附加)
```
- `22 = 15`（`test_gate_units.py`：13 函数 + 2 parametrize）`+ 7`（`test_strategy_key_contract.py`）✓ 与 t3 自述一致。
- 环境事实按队长说明处理：本机 `sessionfinish` 清理缺陷已由 TEMP 重定向绕开，未据此判 t3 任何失败；t3 自述也同时给出了"不改文件同样退出 1"的对照证伪（`acceptanceResults`/`commandsRun` 内已如实记录 exit 1 + 原因）。
- 本次审查**未**发现 t3 通过删除/放宽既有断言取绿：`git diff HEAD -- fly64/tests` 不含 `test_gate_units.py` 之外的新增（该文件为 `??` 新文件），且 `tests/test_dashboard_protocol.py:112-113` 仍原样钉住 WS 侧的 0.4/2.0 字面量（见 F4）。

---

## 6. Findings（不阻塞 pass；建议排期）

| id | severity | 问题 | 建议修复 |
|---|---|---|---|
| F1 | medium | **默认阈值低于活体观测池率 ⇒ gate_jump 在观测域恒真**：默认 8.0 Hz（live persisted 3.082 Hz）都低于 t1/t4 活体 jump 池 12.5–26.9 Hz；探针 0.23/0.276/0.5385 per-tick 三档全 True。PIN 只断言合成闭合态（0 Hz）与边界，无活体可达闭合态证据。缺陷从"恒假"变为"观测域恒真"，信号仍不携带信息 | 把默认值标定到观测区间内（如 18–22 Hz，仍 ≤ Nyquist 50 与 schema max 20 的取舍需一并调），或在 schema/docs 明确"gate_jump = 跳池已被强招募"的语义并给出观测到的开/关直方图；补一条 PIN：断言在某个**活体可达**池率（如 t1 窗口最小值 0.25/tick=12.5 Hz）下门可关。负责人：schema/gate owner（t3 后续或新任务） |
| F2 | medium | **阈值无单一来源**：`telemetry.py:93-94` 仍用字面量 0.4/2.0 Hz，flow.json 用 schema default（2.0/8.0）或策略值（0.598/3.082）；本次探针显示 jump ∈ (2.0, 8.0) Hz、forward ∈ (0.4, 2.0) Hz 时 WS 与 flow.json 结论相反。t1 §4「同一 tick 两路 producer 相反」的根因只闭合了一半（单位一致了，数值仍不同源） | telemetry.py 不要再写字面量：从同一 registry/策略读取，或直接取消 WS 的 gate_* 字段（改由 flow.json 单一来源），并在 `tests/test_dashboard_protocol.py` 同步改为断言同源。负责人：t3 后续/t7 |
| F3 | medium | **持久化的旧口径值被静默重解释**：`skills/active_strategy.json:12-13` = `gate_forward_threshold 0.5983` / `gate_jump_threshold 3.0823`，取自旧的 per-tick 域区间（`[0.1,0.8]`/`[0.5,4.0]`）；`main.py:2508-2510` 读取时**不做区间校验/裁剪**。于是活体实际阈值变成 0.598 Hz（=0.012/tick）与 3.082 Hz（=0.062/tick），既非旧语义也非新默认标定。旧区间内落在新 min 之外的值（如 forward 0.1–0.4、jump 0.5–2.0）会静默越界 | 迁移/校验持久值：读取时裁剪到 schema `[min,max]` 并告警，或直接重刷 `active_strategy.json` 到 Hz 标定值；在 register/docs 记录本次单位迁移（哪些历史值处于外来单位）。负责人：t7（strategy 写入面）|
| F4 | low | **其它文档/前端仍写旧阈值**：`skills/skills.md:272`（"0.4 Hz / 2.0 Hz，与渲染阈值同源"）、`docs/dashboard-key-indicators-reference.md:77-78`、`docs/causal-chain-implementation.md:27`、`web/dashboard.js:214`（"gate 0.4 Hz ✓/✗"）、`docs/causal-chain-prototype.html:97`。这些描述 WS 侧（telemetry 字面量）或已过期的值，与 flow.json 的 2.0/8.0 不一致 | 与 F2 一并收口：阈值单源化后统一更新这些文本/标签（或在其中明确"WS 侧阈值"字样）。负责人：t7 文档同步 |
| F5 | low | **register 行号引用已过期 + 手工段易被覆盖**：§2b 引用的 `model.py:1912-1916`/`2138` 在 HEAD 上正确、在当前工作区因 t2 的 +约160 行已移走（2217-2219/2417）；§3 的行号是 t3 生成时的快照（现亦过期）。§2b 是手工段，`scripts/build_unimplemented_register.py` 重跑会整体覆盖（文档自身已警告"survives only if re-added"） | t7 合并时刷新引用行号；并让生成器支持"closed items"持久化（或把 §2b 内容纳入生成器输入），避免下次重生成时两条 gate 记录再次消失。负责人：t7 |
| F6 | low | **相邻同族缺陷（t3 inScope 之外）**：`plugin/scene_context.py:230-232` 从 `memory.json` 读 `forward_rate`/`jump_rate`，但该文档不含这两个键（活体实测 absent）⇒ `MotorState.forward_rate ≡ 0.0`，却在 `:370` 渲染为 `前向=0.0Hz` 进入 coach prompt | 改从 `flow.json`（或新发布的 `*_rate_hz`）读取并统一单位；补一条断言 `memory.json`/`flow.json` 的键存在性。负责人：plugin/coach 面（新任务或 t7 附带） |

---

## 7. 复现命令

```powershell
# 0) 被审查状态
cd D:\codes\flygym
git diff HEAD --stat -- fly64/fly64/main.py fly64/skills/brain_tunable_params.json fly64/docs/declared-not-implemented.md
git status --porcelain -- fly64/fly64/model.py fly64/skills/evolution_skill.py fly64/plugin/strategy_writer.py

# 1) t6 自有探针：以 AST 执行生产 gate 表达式（含 WS 对照、边界、dt 臂）
cd D:\codes\flygym\fly64
..\.venv\Scripts\python.exe -u D:\codes\flygym\.tmp_t5\reviewer_probe_t6.py
#   原始输出：D:\codes\flygym\.tmp_t5\t6_probe_output.json

# 2) t3 合约 verify（TEMP 重定向）
cd D:\codes\flygym\fly64
New-Item -ItemType Directory -Force D:\codes\flygym\.tmp-pytest | Out-Null
$env:TEMP='D:\codes\flygym\.tmp-pytest'; $env:TMP=$env:TEMP
..\.venv\Scripts\python -m pytest tests/test_gate_units.py tests/test_strategy_key_contract.py -q
..\.venv\Scripts\python -m pytest tests/test_dashboard_protocol.py tests/test_phase6_fitness_inputs.py -q
..\.venv\Scripts\python -m pytest tests/test_tunable_wiring.py tests/test_telemetry_completeness.py tests/test_evo_tunable.py -q

# 3) docs/schema 一致性抽查
cd D:\codes\flygym
Select-String -Path fly64\skills\brain_tunable_params.json -Pattern '"wired"' | Group-Object Line
Select-String -Path fly64\docs\declared-not-implemented.md -Pattern 'gate_(forward|jump)_threshold'
git show HEAD:fly64/fly64/model.py > .tmp_t5\head_model.py
Select-String -Path .tmp_t5\head_model.py -Pattern 'jump = jump_rate >|raw_y = np.clip\(\(forward_rate'
# 4) 活体只读
Invoke-WebRequest http://127.0.0.1:8765/memory.json -UseBasicParsing   # forward_rate/jump_rate absent
```

---

## 8. 证据限制 / 诚实清单

1. **活体未部署**：deployed `main.py` 仍是修复前版本（t4 §10 的指纹；本轮 `flow.json` 仍无 `forward_rate_hz` / `gate_jump_threshold_hz` 键，且 `gate_jump=False`），故本报告的 flow.json 可达性结论全部来自**离线执行生产表达式**（AST lift + stub），不是活体验证；活体只作基线与"观测池率范围"取值来源。
2. **探针的 stub 化**：`model`/`control`/`_expl` 是替身，只覆盖 gate 段落所引用的属性（`model.dt`、`control.{forward,turn,jump}_rate`）。因而它证明的是**表达式与单位契约**，不覆盖 `_expl` 的真实装载路径（该路径由 `tests/test_strategy_key_contract.py` 覆盖）。
3. **jump 池的"观测域"结论基于 t1/t4 的两个在线窗口**（327 行与 10–13 行）；未采集新窗口，故"gate_jump 在活体恒真"是对**这两个窗口**的陈述，不是全时段断言（F1 已按此措辞）。
4. **连接组/仿真量级**：本任务不涉及池动力学，未做任何 LIF 仿真；t2 相关的池占用率数字只在引用 t1/t4 时出现。
5. 未测量的量一律标注为推算/未测量；无推算冒充实测。
