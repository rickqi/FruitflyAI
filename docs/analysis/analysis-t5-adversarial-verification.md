# t5 对抗性验证报告：`docs/analysis/fly64-autonomy-evolution-plan.md`

> **验证人**: verifier（team `fly64-autonomy-evolution`）· 任务 `t5` · attempt `7be1b297-b3c9-49a8-851c-9bec272f1123`
> **被验证对象**: `docs/analysis/fly64-autonomy-evolution-plan.md`（892 行 / 104 649 B，t4 交付）
> **基线**: `git rev-parse HEAD` = `cca66648a204043d881da502cf996b15882ad289`（与 t4 声明一致）
> **方法**: 只读代码/产物核验 + **独立重算**（本报告自带 6 个一次性脚本，全部落在 `.tmp/t5_verify_*.py`，不修改任何仓库文件）
> **verdict**: **needs_revision**（1 blocker + 1 high + 4 medium + 6 low）

---

## 0. 结论摘要

| 维度 | 结论 |
|---|---|
| 数据溯源 | **强**。我独立重算了 90+ 处 `文件:行号` 引用与 6 组关键数值，**除 F7/F8/F9/F10/F11 五处外全部逐位复现**（见 §1、§3）。轨迹运动学 8 项数值**全部精确复现**（含 6000 点、5330/6000、前 5455 点无 0、1385/5999、2.75%/5.35%、末 545 点 `(0,50)×480+(0,70)×65`、`127`=0/6000）。 |
| 主因判定 | **通过**。M3→M1→M2 与 M4 的性质/排序，每一条都能落到「读 HEAD 代码可直接证实」的引用上（我逐条打开核对）。 |
| 脑模型驱动性 | **基本成立，但有 2 处需收紧**：§5.3 改写的是**决定行为的解码式**（不是纯口径统一），§6.4 未说明"竞争槽胜出后如何越过 `not _lif_motion`"。均无新增 `control.*` 写入点，但 R1 的合规论证不完整。 |
| 反硬编码补丁 | **通过**：全文未提出任何新的 `control.x/y/jump = …` 写入点；T3 代码补丁被降级为提案。**但 §7.1 的门禁设计可被绕过**（F3）。 |
| 假设/伪影/版本边界纪律 | **通过**（H1–H14 全部登记，E-4 层数值全部带标注）；仅 2 处行内标注缺口（F11 附带项、§6.2）。 |
| 验证指标 | **每项都有落点/基线/阈值/失败回退**，但 V6 在方案自身的参数语义下**不可达**（F1），V9 的统计设计不能保证"接受量 > 噪声"（F5）。 |
| **阻断性问题** | **§5.3 / §7.1 的"线上 3.082 ∈ [0.25, 3.0] ⇒ 无需迁移"是算术错误**（3.082 271 242 248 696 **> 3.0**）。按方案实现后门限会被静默钳到 3.0，在**新的比值语义**下比今天的绝对门**更严 2.5–3.2×**，与 §5.3 自身目的相反，且 V6 验收无法满足。 |

---

## 1. 独立复现清单（真实命令 + 真实输出）

### 1.1 轨迹运动学（`.tmp/t5_verify_traj.py`，自写、非 t3 的脚本）

```
python .tmp/t5_verify_traj.py
n_points = 6000                       | t_range = 10728.07 -> 12053.03   | t_step_median = 0.21
ctrl_x value set size = 32            | ctrl_y set = [50, 70]            | jump true = 0 / 6000
ctrl_x fullscale(|70|) = 5330 / 6000  | first ctrl_x == 0 at index 5455  | ctrl_y == 127 count = 0
sign alternations = 3419 of 5999 = 57.0 %
static frames(d<0.5) = 1385 / 5999
x: path=135817.2 net=3739.0 eff=2.75%  |  z: path=114174.9 net=6111.3 eff=5.35%
tail-545 control multiset = [((0,50),480), ((0,70),65)]
ctrl_y=50 -> forward_rate = 0.0330 ; ctrl_y=70 -> forward_rate >= 0.0430 (saturated)
turn_rate saturation threshold = 0.063636
```

⇒ 方案 §2.6 / §0.1 / §9.2 引用的**每一个**轨迹数字都精确复现。`ctrl_x` 取值 32 个、`ctrl_y` 仅 {50,70}、`jump` 0/6000、`127` 0/6000 亦复现。

### 1.2 LIF 算术与增益链（真实命令）

```
v_ss_per_unit = 5.5167                         # 方案写 5.517 ✓
I for threshold = 0.181269                     # 方案写 0.18127 ✓
escape floor v_ss = 0.2758                     # 方案写 0.2758 ✓
gain 0.5 leg 0.07749 v_ss 0.4275               # ✓
gain 1.5 leg 0.23247 v_ss 1.2825               # ✓
gain 2.5 leg 0.38745 v_ss 2.1374（方案 2.1375） # ✓（四舍五入）
0.8/0.35 = 2.2857 ; 0.10/0.35 = 0.2857         # 方案写 ≈2.29× / ≈0.286× ✓
4*0.181269 = 0.72508                           # 探针 0.7251 ✓
```

### 1.3 接线事实（`FlyModel(demo=True)`，真实命令）

```
n = 4096
visual 1536 | forward 60 | turn_all 80 | jump_nodes 20 | recurrent(default) 2400
mbon_gain_jump 0.35  mbon_jump_weight 0.35
fwd_occ_tau 0.15 ref 0.3 full 0.6 floor 0.25 aux_ceiling 0.2
hasattr(cx,'steering_gain') = False
cx._goal_comp.steering_gain = 0.12
```

⇒ 方案 §5.1 的池大小「实测」在**结果上**成立（但见 F11 关于"探针实测"的措辞）；§5.4 的**影子属性**指控在对象层得到确证：`CentralComplex` 无 `steering_gain`，运算读的是 `MultiSourceGoalCompetition`（`cx._goal_comp`）的 0.12（`central_complex.py:198,314`）；`_loop_break_stuck_s` 的读取端在 `:297`（`getattr(self,...)`，`self` 即 `_goal_comp`），故 `main.py:1850` 的写入被回退常量 45.0 覆盖。**两处死写入 = 真**。

### 1.4 静默回滚（假回滚）指控（读 `evolution_skill.py:2238-2267`）

`_inject(params)` 对每个 pid 取 `params.get(pid, strat[section_key].get(param_name, default))`；`_inject({})` 时取的是**文件里的当前值**，只把 `__generation += 1` 后原样写回。⇒ `evolution_skill.py:2490,2532` 的 `self._inject({})  # resets to defaults only` **不是回滚**（甚至没有触碰被变异的值）。**方案的"假回滚"指控成立**。

### 1.5 自进化管线（真实 CLI）

```
cd fly64; python -m skills.evolution_skill --history-check
BRAIN_VERSION(main.py)=2.24.0  SKILL_VERSION=3.5.0  canonical=(2.24.0/3.5.1)
FAIL — SKILL_VERSION 3.5.0 != canonical 3.5.1          [exit=1]        # ✓ §7.5-e

python -m skills.evolution_skill --funnel
iterations 13728 | findings_fired 44159 | fixes_recorded 11 | fixes_verified 11 | fixes_effective 0
rate_finding_to_fix 0.0 | rate_verified_to_effective 0.0
top_patterns: micro_loop_weave_signal 9259, reflex_cooldown_gap 7764, fallen_recovery_stuck 7665,
              ramp_trap 5631, telemetry_gap 4773                      # ✓ §1.1/§7.4 全部一致
```

```
python fly64/scripts/audit_contract_pairs.py
→ 该工具**不扫描** brain_tunable_params.json；对 skills/active_strategy.json 的 47 个键报
  unreferenced 38 个（含 exploration.gate_jump_threshold w=0 r=0 decl=0、navigation.* 等）
→ 全仓合计 unreferenced 85 行、TOTAL dead-writes + silent-defaults: 8      # 见 F7
```

### 1.6 闭环日志与漏斗原始记录（`.tmp/t5_verify_log.py` / `t5_verify_drops.py` / `t5_verify_catalog.py`）

```
evolution_log.jsonl: lines=13728  first=2026-09-12T15:26:19Z  last=2026-09-17T02:22:55Z  span=4.46 天
  （02:22:55Z == 10:22:55 +08:00 ⇒ 方案 §7.4 的 "2026-09-17T10:22:55" ✓）
  iteration min/max = 1 / 4433        ✓（t2 "iter 1..4433"）
  restart-like resets (cur<=5 & prev>=20) = **9**  ✓（t2/方案 "被重启 ≥9 次"）
  含 'context' 键的行 = **0**          ✓（§7.3 "从不记录任何传感器数值"）
  top-level 键并集 = errors/evolution/findings/fixes/iteration/timestamp/verifications（无任何读数）

evolution_health_trend.jsonl:
  {"phase6_trials": 68, "phase6_commits": 1, "phase6_delta_exact_zero": 41, "outcomes_total": 30,
   "usable_outcomes": 0, "promoted": 0, "by_improved": {"1": 2}}   ✓ 41/68 = 60.3%、1/68 = 1.47%

fix_catalog.json: meta total_fixes 19 / effective 0 / ineffective 11 / reverted 8   ✓（方案 §1.1 一致）
  fix_template 可执行行统计：0 行的 fix = 16/19；可执行行合计 **7**，注释行 **87**   ✓ 逐位一致
  fix_0013 = `control.x = rng.integers(60,80)*(-1|1); control.y = 40`；458.98 → 464.72；effective=false ✓
  未被回滚的 fix = 11 条，覆盖 **11** 个不同 pattern_id                    # 见 F8
default_patterns.json: 16 个 pattern；fix_files 命中 main.py 的 = 8 个        ✓
  circle_loop 条件含 wall_score max 0.1 ✓；ramp_trap 含 position_unchanged_30s ✓；
  micro_loop_weave_signal 含 escape_behavior true ✓
scene_strategy_bindings.json: 2 bucket、各 improved=1、promoted=false、turn_bias 0.7/0.6 ✓
coach_outcomes.jsonl: 30 行，scene_label 为空 30/30                          ✓
```

### 1.7 版本边界 H1（真实命令）

```
git log -S 'deadlock_burst_ready' -- fly64/fly64/main.py
→ 仅 6d0aa42 2026-09-23 08:36:08 +0800        ✓（方案/ t3 声明一致）
git log -5 -- fly64/skills/default_patterns.json
→ 048fd16 2026-09-18 fix(pattern): ramp_trap阈值180s->60s + position_unchanged_30s   ✓
```

并且我**独立验证了 H1 的推论在 HEAD 上成立**（而不只是转述）：

- `memory.py:1215-1218`：`if loop > threshold: return True; if stuck > 60.0: return True`；
- `main.py:2055-2086`：`deadlock_burst_ready(...)` 为真且冷却结束时置 `_deadlock_burst_remaining=200 / cooldown=300`，随后 `control.y = 127`（:2081）、`control.x` 写入（:2078-2080）；
- 伪影使 `stuck_duration` 单调增长（§2.3 链条，我逐行核对 `memory.py:1985` vs `:1994-1995`，泄放确实在下一 tick 被覆盖）⇒ **HEAD 上 burst 必周期性触发**；
- 实测 `ctrl_y ∈ {50,70}`、`127` = 0/6000 ⇒ **该 run 不可能产自 HEAD**。

⇒ 方案把「主因与方案只在读 HEAD 代码可直接证实的证据上成立」作为硬边界，**是正确且被本验证支持的**。

### 1.8 其它对照（真实命令）

```
grep position_unchanged_30s（全仓 *.py）→ 0 命中（只有 default_patterns.json:50 与其 60s 版本）✓ §7.5-a
grep _last_burst_tick          → 仅 main.py:2062（getattr 读取），全仓无写入点 ✓ §5.6
grep GoalComparator            → 全仓 0 命中                              # 见 F9
gain_modulation: DopamineGainController().pathway_gains = 全 1.5，get_gain('jump') = 1.5  # 见 F2
main.py:702 LIF_MOTION_MIN = 8；main.py:2521 `_lif_motion = abs(control.x) > LIF_MOTION_MIN …` ✓ §6.4
main.py:1879 `_as_path.write_text(json.dumps(_as_raw …))`（自愈回写）✓；1873-1876 param_history.jsonl
        字段名为 "source"（非方案 §7.5-f 的 "owner="）                     # 见 F12
active_strategy.json:5 bold_explore_stuck_s=60.0（注册 [1,10]）✓ ; :8 gate_jump_threshold=3.082271242248696
        ; :16 __generation=332 ; :33-38 navigation 0.12/45.0              ✓
line-number sweep（约 90 处引用，逐行打印）→ 仅一处**类名**对不上（`GoalComparator`，F9）；数值类差异见 F7/F8/F10/F11
```

---

## 2. 逐项核验结论（对应任务书 11 项）

| # | 核验项 | 结论 | 证据/备注 |
|---|---|---|---|
| 1 | 引用数据可复现、行号准确 | **基本通过**（90+ 处仅 4 处问题） | §1；问题见 F7/F9/F11/F10 |
| 2 | 主因判定被 t1/t2/t3 实际证据支撑 | **通过** | M1 的三解码器（`model.py:2282,2283,2478`）、M2（`memory.py:1361-1373`/`1319-1321`/`central_complex.py:286-306`）、M3（`memory.py:135,206-217,223` ← `main.py:2650`；`main.py:765-785` 同型自述）、M4（`evolution_skill.py:2460,2505,2325-2326,2019-2036`）全部**逐行核对为真**；60.3%/1.47%/0 effective/5631 次 ramp_trap 等量化证据我独立复现 |
| 3 | 是否真是「脑模型驱动自治」 | **基本通过**（2 处需收紧） | 无新增 `control.*` 写入点；§5.1/§5.2 = 膜电流腿，§5.4 = 把已有写入送到已有消费者，§7 = 参数/增益空间。但 §5.3 改写的是**决定行为的解码式**（占用率→比值，语义耦合新增），§6.4 未说明如何越过 `not _lif_motion`（F4）。另 T3 门禁可绕过（F3） |
| 4 | 所依赖脑机制在运行时是否真被调用 | **通过** | 不重复依赖"结构不可达"面：S13 环路突破被**改判据**而非直用；S14 本能只修上游证据链且**明确不降 `PROMOTE_MIN_IMPROVED`**；S29 CPG 改走仲裁（但 F4）；S33 由 §5.3 统一（但 F1）；S1/S16/S35 的"✅ 生效"我核对 t1 原文一致 |
| 5 | 验证指标可观测 + 阈值 + 失败回退 | **形式通过、实质 2 项不成立** | V1–V20 全部四要素齐全；但 **V6 在 F1 的参数语义下不可达**，V9 的统计设计不保证"接受量>噪声"（F5） |
| 6 | t3 §9 的 10 条假设是否被当断言 | **通过（1 项措辞建议）** | H1–H9 + H1' 全部在 §13 登记；H1 仅作边界约束且其推论被本验证证实；H5/H10/H11/H12/H13 均在引用处行内标注「（假设 Hxx）」。仅 §5.3 正文 L355 的 H6 派生句无行内标记（F11③） |
| 7 | 版本边界 H1 合规性 | **通过** | 主因与 5 个脑侧改动项的引用全部落在 HEAD 可读代码上（§1.3–1.8）；轨迹证据仅用于标定/对照，且被 §0.1/§2.6 的「引用纪律」限定 |
| 8 | 伪影引用纪律 | **通过（1 处 low）** | `stuck_score/stuck_duration/reflex_active/median_speed/disp_60s` 只在 E-4 层出现并带「检测伪影」+ H1 标注；§6.2 明确要求 `stuck_duration` 用重建量。**但 §6.2 的新判据仍含 `reflex_active = false` 分量**，而 §2.5 已判定该量在本 run 不可复现（F11 附带项） |
| 9 | 禁止项合规 | **通过** | (a) 主因**未**写成控制层/反射层（§9.2 逐层否定）；(b) 未为 M1 新增控制分支（§5.3/§6.4 见 F1/F4 的收紧要求）；(c) **已否定** P0.1/P0.2/P0.3/P1.1 并说明技术前提错误（§9.1，且 `model.py:2478` 对 anomaly 无依赖我逐行确认） |
| 10 | 独立复现 ≥3 项 | **通过（复现 13 组）** | §1.1–1.8：轨迹 8 项、LIF 4 项、池大小 5 项、假回滚、CLI 2 条、漏斗 4 项、fix_catalog 3 项、日志 5 项、git 2 条、接线 3 项 |
| 11 | 与 t3 §6 的 A/B 分类一致 | **通过（1 处映射不一致）** | 方案 §3 的 A 类 11 项与 t3 A1–A11 **一一对应**、B1–B5 一字不差；仅 §3 说"A 类 ⇒ §4/§7 的 P0/P2 条目"与自身 §5.4/§5.6（P1）矛盾（F12） |

---

## 3. Findings

### F1 — blocker · §5.3/§7.1：`3.082 ∈ [0.25, 3.0]` 是算术错误，"无需迁移"不成立，且实现后门限比今天更严

- **问题**：`fly64/skills/active_strategy.json:8` 实为 `3.082271242248696`，**大于** §5.3 提出的新注册区间上界 `3.0`（越界 0.0823）。因此 §5.3③ 的 `max(0.25, min(3.0, float(_expl.get("gate_jump_threshold", 0.75))))` 会把线上值**静默钳到 3.0**。在**新的比值语义**（`jump_rate / max(forward_rate, eps) > ratio`）下：实测 `forward_rate ∈ {0.033, 0.043}` ⇒ 需要 `jump_rate > 0.099 ~ 0.129` ⇒ 约 **2.0–2.6/20 个跳神经元同时发放**，而今天是绝对门 `0.04`（= 0.8/20）。**新门比旧门严 2.5–3.2×**，与 §5.3 的目的（"跳池的常态驱动远低于该水平 ⇒ 改为相对占用率"）完全相反；V6「0 < 占空比 ≤ 5% 且门限 6000 tick 内真/假都出现」在 3.0 下大概率不可满足 ⇒ P1-b3 无法通过自己的验收。
- **附带自相矛盾**：§7.1 T1 自己要求"实际钳位与注册区间**必须相交**"并点名 `active_strategy.json:5` 为"当前的反例"——`:8` 是同族的**第二个未被列出的反例**。
- **必须修正**：
  1. 把新区间上界设为**严格大于线上值**（如 `max: 4.0`，`default: 0.75`，`min: 0.25`），或
  2. 在 P0 增加**显式迁移项**：经 §4.6 授权点把 `:8` 改写为绝对等效占用率**不高于**今天 0.04 的比值（例如 `0.75 × 0.043 = 0.032`），并在 §14-D(j) 的迁移清单里与 `:5` 并列；
  3. 无论选 1 或 2，增加一条**硬断言**：语义翻转后对每个 pid 断言 `registry_min < live_value < registry_max`（复用 §7.1 T1 的同一断言），断言失败即阻断 P1 上线；
  4. 在 §5.3 给出"新门 ≥/≤ 旧门的等效换算"，明确本项的目的是**放宽**而非收紧，并把 V6 的阈值改写为可判定的形式（例如"占空比 ∈ [0.1%, 5%]"并给出基线对照）。

### F2 — high · §5.1：`_jump_leg_weight` 默认 0.35 并**不能**保证行为不变（首 tick 即 +50% 跳腿驱动）

- **问题**：方案把 `model.py:1787` 的 `mbon[3] * self.mbon_gain_jump` 改为 `mbon[3] * self._jump_leg_weight * self._pathway_gains_np[3]`，并声称赞"`self._jump_leg_weight = 0.35`（默认值与今天**逐位相同**，保证行为不变）"。实测 `DopamineGainController().pathway_gains['jump'] = 1.5`（`gain_modulation.py:39-45,331` 的 `DEFAULT_GAINS`，`get_gain('jump')=1.5`），故新表达式在标称状态下等于 `0.35 × 1.5 = 0.525` 倍 `mbon[3]`，比今天**高 50%**。
- **更强的问题**：方案自己的探针**已经做了归一化**——`.tmp/a4_plan_probe.py:121` 是 `cur = leg_mean * g / DEFAULT_GAINS["jump"]`，即 §14-A 的增益链表（0.07749/0.23247/0.38746）假设的是 `gain/nominal`，**而 §5.1 拟写的代码没有这个除法**。方案内部的算术与拟写代码不一致。
- **必须修正**（二选一，并同步 V4/R1 的数值）：
  1. 默认权重取 `0.35 / 1.5 = 0.23333`（注册 `escape.jump_leg_weight {default: 0.2333, min: 0.0667, max: 0.5333}`），或
  2. 实现为 `mbon[3] * self._jump_leg_weight * (self._pathway_gains_np[3] / DEFAULT_GAINS["jump"])`；
  并增加一条**位精确回归断言**："权重为默认值且 `gain('jump') == DEFAULT_GAINS['jump']` 时，跳腿电流与改动前逐位相同"；同时说明 `jump_pool_occupancy` 的验证阈值（V5：非零占比 ≥5% 且 P95 ≤ 0.20）是在"默认不变"的前提下标定的。

### F3 — medium · §7.1 T3 门禁可被绕过（`fix_files` 不是执行目标的事实来源）

- **问题**：方案把 T3 门禁定义为"`fix_files` 命中 `.py` 且未获批准 ⇒ 只写提案，不执行"，并说明插在 `evolution_skill.py:2644` 与 `FixExecutor`（`:2653-2668`，实际调用在 `:2655`）之间。但 `FixExecutor.execute` 的实际目标来自 `parse_fix_template(fix_template)` 的 directive（`fix_executor.py:469,486-489`），`_resolve_file` 是 **`rel = file_rel or (fix_files[0] if fix_files else "")`**（`fix_executor.py:603-609`）——**模板内的 `# File: fly64/fly64/main.py` 优先**。因此 `fix_files: []` 或非 `.py` 但模板含 `# File: …main.py` 的 fix 仍会被写盘。此外"静态断言落在 `tests/test_evolution_fix_contract.py`"本身**不能阻止运行时执行**，只能在没有门禁的情况下事后告警。
- **必须修正**：① 门禁判据改为「`f.fix_files` **∪** `parse_fix_template(f.fix_template)` 的全部 `directive["file"]`」命中 `.py` ⇒ 拒绝执行；② 在**唯一写盘点** `FixExecutor.execute` 内再加一道运行时守卫（同一判据），使旁路不可能；③ 明确 V20 的静态断言是第二道防线而非门禁本身。

### F4 — medium · §6.4：CPG 竞争槽未说明如何越过 `not _lif_motion`，选项与 R1 冲突

- **问题**：方案称"不改 `_lif_motion` 的判据……而是把 CPG 请求变成竞争槽"，但 `main.py:2521` 的 `_lif_motion = (abs(control.x) > LIF_MOTION_MIN …)`（`LIF_MOTION_MIN = 8`，`main.py:702`）在观察运行点**恒真**（`control.y = 70`）。要使 V-指标 `primitive_granted_count ≥ 1`（对照改前 0）成立，最终**必须**有一条路径让仲裁授予的 primitive 越过这个门；方案没有给出该机制的落点。若实现为在 `_lif_motion` 上加一个 OR 支路，那就是**新增控制分支**，与 R1/用户硬约束冲突。
- **必须修正**：明确写出"授予 → 执行"的落点，且不得新增 `control.*` 写入点。建议：把 `_lif_motion` 的判据**替换**为由仲裁持有的"运动权威拥有者"谓词（`authority ∈ {lif, primitive}`，由 §6.1 的状态机维护），既保持"单一口径"（R3），又把 CPG 的取权从"恒真门"变成"竞争结果"；并把该替换加入 §7.1 的静态断言（禁止在 `_lif_motion` 上追加 OR）。

### F5 — medium · §7.2：A/A 零假设门与 commit 阈值同值 + 样本量不足，不能保证"接受量 > 噪声"

- **问题**：① 门是 `P95(|delta_A/A|) ≤ 0.03`，而 commit 阈值恰为 `delta > 0.03`（`evolution_skill.py:2505`）⇒ 由构造决定，**最多 5% 的零假设窗口会越过 commit 阈值**；§7.2 的"双窗确认"虽能降低假阳性，但方案未给出降幅（相邻窗口强相关 ⇒ 不能按 0.05² 估计）。② "20 次 A/A"对 P95 的估计在统计上不可靠（n=20 的 95 分位≈最大值，置信区间极宽），而后一条判据"20 次中 |delta|≥0.03 的比例 ≤10%"比第一条更弱、**永远不会先失败**。③ 失败回退只写了"延长窗口/多窗平均"，**没有**"噪声地板无法降到 0.03 以下时怎么办"。
- **必须修正**：① commit 阈值改为随噪声标定（如 `threshold = max(0.03, k · P95_noise)`，`k ≥ 2`），或改用显式显著性检验（置换检验/t 检验）并声明目标 FPR 与功效；② 明确最小 A/A 样本量（建议 ≥100 窗口）或给出 bootstrap 置信区间，并说明双窗确认后的实际 FPR；③ 补一条失败回退："噪声地板在 2 倍窗口后仍 > 0.03 ⇒ 该 fitness 维度标记 `unmeasurable` 并移出搜索空间（而不是继续盲搜）"。

### F6 — medium · §5.5 与既有 deadlock burst 的触发条件重叠、且 V8 无法归因

- **问题**：§5.5 的新门是「`stuck_duration > loop_break_stuck_s` AND (`progress_is_ineffective` OR `loop_score > loop_breakout_threshold`)」，而 `main.py:2055` 的既有 burst（`deadlock_burst_ready`，`memory.py:1215-1220`）是「`loop_score > threshold` OR `stuck_duration > 60` OR (`stuck ≥45` AND no-progress)」，占空比 200/500、**直接写** `control.x/control.y=127`。两者的触发条件在几乎同一场景下同时成立，而方案（a）没有规定优先级/互锁，（b）把 V8 写成"复现场景 4000 tick 内 `cx_loop_break_count` ≥ 1"，但在该场景里 burst 必然也在触发（§0.1 自己证明了 HEAD 下 burst 必现），**观测无法归因给 CX**。
- **必须修正**：① 明确两者的优先级/互锁（建议按 §4.2 的架构把 CX 环路突破与 deadlock burst 都注册为 §6.1 的候选，由同一成效分裁决；或规定 burst 激活期间抑制 CX 环路突破）；② V8 的观测窗口限定为"burst 未激活的 tick"，或增补一个可区分量（如 `cx_loop_break_count_burst_off`）；③ §5.6 已提到审查 `main.py:2082` 的 `control.jump=False`，请把该审查扩展为"burst 与 §5.3 门归一化、§5.5 CX 突破三者的相互作用"，给出冲突矩阵。

### F7 — low · §4.5：「audit_contract_pairs.py 对 39 个参数全部报 unreferenced」与工具真实行为不符

- **问题**：该工具**不扫描** `brain_tunable_params.json`；它扫描 `skills/active_strategy.json`（47 键）等 8 个工件，在其中报 **38** 条 `unreferenced w=0 r=0 decl=0`（含 `exploration.gate_jump_threshold`、`navigation.steering_gain`、`navigation.loop_break_stuck_s` 等）。所以"39 个参数全部报 unreferenced"既**数字不准**（38 vs 39），也**指错了文件**。
- **必须修正**：把该句改写为"该工具对线上 `active_strategy.json` 的 47 个键报 38 条 `unreferenced`（w=0 r=0 decl=0），其中包含 39 个注册 pid 的绝大多数；工具本身不扫描注册表"。**实质结论不变且我支持**：一个静态工具无法支撑 `wired: true`，必须用运行时 A/B（t2 §4-C4 / §4.5）。

### F8 — low · §3 / §7.5-c：`has_fix()` "现关闭 13 个 pattern" 实为 **11** 个

- **问题**：`fix_catalog.json` 19 条 fix 中未被回滚 11 条，覆盖 **11 个不同 `pattern_id`**（`below_ground_stuck, circle_loop, cliff_standoff, fallen_recovery_stuck, low_coverage_stagnation, mbon_saturation, micro_loop_weave, primitive_zero_disp, ramp_trap, suspended_animation, telemetry_gap`）；`has_fix()`（`evolution_skill.py:1163-1164`）按 `pattern_id` 判、且 `FixCatalog._load` 只读这一个文件（`:1099-1104`）。故"关闭 13 个"高估 2 个（与 `pattern_id` 总数 16 亦不匹配）。
- **必须修正**：改为 11，并注明统计口径（未被回滚的 fix 覆盖的 distinct pattern_id 数）。

### F9 — low · §5.4：`GoalComparator` 类在仓库中不存在

- **问题**：§5.4 的"需修改/新增②"要求为 `GoalComparator` 增加 property；全仓 grep `GoalComparator` **0 命中**，真实类是 `MultiSourceGoalCompetition`（`central_complex.py:178`，实例挂在 `cx._goal_comp`，`central_complex.py:369`）。
- **必须修正**：改名为 `MultiSourceGoalCompetition`（或明确写 `cx._goal_comp` 的类型），并确认 property 加在该类上（`:198` 的 `self.steering_gain`、`:297` 的 `getattr(self,'_loop_break_stuck_s',…)` 都在该类的命名空间内）。

### F10 — low · §5.2：默认值自相矛盾 + 一处量纲标注错误

- **问题**：① §5.2「需修改/新增①」写常量 `jump_intrinsic_max=0.25`，而「④」的注册项是 `{default: 0.15, min: 0.05, max: 0.25}`，而「精确算术」段又以"0.15 的默认值"论证——同一项在三处取两个默认值。② 「精确算术」写"现有缺口 = 0.13127/tick（= 0.31·threshold）"：`0.13127/1.0 = 0.131`，不是 0.31（0.31 是缺口对该腿 `GAIN_MIN` 下 `v_ss=0.4275` 的比值）。
- **必须修正**：统一 `jump_intrinsic_max` 默认值（建议 0.15，与注册项一致并把常量默认改为 0.15），并把比值改写为"0.13 × threshold（或 0.31 × GAIN_MIN 腿的 v_ss）"。

### F11 — low · 多处：探针归属与两处"无"的措辞强于实测

- **问题**：① §5.1 称"**实测**该映射中 jump 神经元 20 个、forward 60、turn 80、recurrent 2400、visual 1536"——`.tmp/a4_plan_probe.py:102` 把 `jump_pool = 20` **写死**，只测了 `len(m.forward)`；turn/visual/recurrent 未测量（**我独立测出五个数完全正确**，故结论无害，但归属应改为直接测量）。② §2.5 称"无 burst 的 127、**无 CPG 的 ±60/±69 群**"——实测 `ctrl_x` 有 `60`×1 与 `69`×7（全部在正侧，`-60/-69` 为 0），"无群"成立但绝对化的"无"不精确。③ 附带：§5.3 的唯一未标注 H6 派生句是 L355 的「而跳池的常态驱动远低于该水平」——该判断的量化版本（"跳池 < 0.04 而前向池 ≈ 0.043"）确实登记在 §13 H6 行内，但 §5.3 正文这句没有行内 H1/H6 标记（§0.1 全局边界可覆盖，行内标注更稳）。
- **必须修正**：① 改为"本机直接测量（`.tmp` 探针 + 本验证独立复算）"；② 改为"无 `-60/-69`，正侧仅 1 次 `60`、7 次 `69`（8/6000），不构成群"；③ 在 L355 该句后补「（H6，需真实连接组确认）」。

### F12 — low · §3 的 A 类落点映射与 §8 阶段划分不一致；§7.5-f 字段名与实现不符

- **问题**：① §3 称"A 类硬缺陷 11 项 ⇒ 修它们……是 **§4/§7 的 P0/P2 条目**"，但方案自身把 A3（`§5.4`）、A4/A5/A6/A7（`§5.6`）放在 **§5 = P1**；② §7.5-f 要求直写留 `owner="coach-direct"`，而 `main.py:1873-1876` 的 `artifacts/param_history.jsonl` 使用的字段名是 **`source`**（现有值为 `"self-heal"`）。
- **必须修正**：① 把 §3 的句子改为"分属 §4（P0）、§5（P1）、§7（P2）"；② 统一字段名为 `source`（或明确要求新增 `owner` 字段并说明与 `source` 的关系）。

---

## 4. 假设分级核验明细（任务书第 6 项）

| 假设 | 报告中的使用方式 | 判定 |
|---|---|---|
| H1 版本边界 | §0.1 第 1 条硬边界；§2.5 反证；§2.6 引用纪律 | **合规**（只作边界/否定用途；其**推论**被本报告 §1.7 独立证实。建议在 §13 的一行里区分"H1 的 provenance 仍是假设 / H1 的推论在 HEAD 上可证"） |
| H2 分类不可复现 | §2.5 理由 2（"HEAD 上不可复现"） | 合规（否定性用法，保守） |
| H3 检测抖动 | §2.4 末尾"（假设 H3）"、§6.3 标题 | 合规 |
| H1' 0.37 s 生成者 | 仅 §13 登记，未进设计 | 合规 |
| H4 `forced_bold_explore` 可达性 | §13 登记，注明"不作为任何回退条件" | 合规（但方案的 §7.5-d 未给该面专属验证项，建议在 §10 增 1 行） |
| H5 真实连接组 | §0.1 第 2 条 + §14-A「诚实声明」 | 合规 |
| H6 M1 在真实连接组 | §13 登记；仅 §5.3 正文 L355 引用无行内标记 | 合规（见 F11③） |
| H7 CX 突破条件性 | §5.5 正文"（仅在向量 norm < 0.075 或无向量时触发 3 次）" | 合规（我另在 `central_complex.py:280-298` 结构上确证该条件性） |
| H8 auto-fix 熔断 | §7.5-c（`:2739-2740` 已核对为真） | 合规 |
| H9 停摆窗口 | 仅 §13 登记，未使用 | 合规 |
| H10 静态扫描盲区 | §4.5 行内"（假设 H10）" | 合规（数字见 F7） |
| H11 MBON 腿有效性 | §13 登记；§5.1 阈值设定受其限定 | 合规 |
| H12 `JUMP_GAIN_MAX` | §13 明确"**可撤回**" | 合规 |
| **H13 A/A 零假设门** | §7.2「未通过 ⇒ 禁止 fitness 变更与自动 commit（仅 shadow）」；§11 R6 硬门；§8 判据 ① | **合规**：**未**被当作已验证前提——它被写成"必须先通过的前置门"，通过与否是待测项；§13 亦写"若不过门，P2/P3 整体阻塞"。**问题在门的统计设计（F5），不在纪律** |
| H14 `dwell_ticks` | §6.1"初值 1500 tick"；§13"唯一标定参数" | 合规 |

---

## 5. 证据边界（本验证未能覆盖 / 无法验证项）

1. **`memory.json` 在本机不存在**（`Get-ChildItem -Recurse -Filter memory.json` 无结果）。因此报告 E-4 层的全部数值——`stuck_score=1.0`、`stuck_duration=1100.72`、`reflex_active=False`、`median_speed=0.0`、`disp_60s=1080.7`、`anomaly_state=stuck_ramp`——**我既无法证实也无法否证**；我只能验证方案**是否合规地标注**它们（结论：合规）。这同时意味着 t4 把它们降级为"被审视对象"是唯一诚实的处理。
2. **本机无 `.cache` 目录（更没有 `.cache/malecns/manifest.json`）** ⇒ 真实连接组运行点无法离线复现。H5/H6/H11 以及 §5.1/§5.2 的**全部定量阈值**（0.18127、5.517×、`fwd_aux_ceiling` 比例、跳腿电流量级）**只能在真实连接组上确认**；探针 `FlyModel(demo=True)` 实测 `jump_pool_spike_rate_mean = 1.0`、`forward_rate_mean = 1.0`、`decode_gate_0.04_open_frac = 1.0`，**完全不能代表真实运行点**（方案 §14-A 已如实声明）。
3. **`66/68 |delta| ≤ 0.03`**（§1.1 第 3 条）在 `evolution_health_trend.jsonl` 中没有对应字段（该文件只有 `phase6_trials/commits/delta_exact_zero`），只在 t2 §5 有；我复现了 68/1/41 三项，**未能独立复现 66**。未重跑 `measure_evolution_health.py --phase6`（耗时且需要完整管线）。
4. **H1 的 provenance 无法闭合**：我确证了"HEAD 下 burst 必触发"这一推论（§1.7），但**无法**证明该 trajectory 具体产自哪个 revision（`t` 是会话时间，无墙钟换算）。因此本报告对 H1 的支持是"推论成立"，不是"provenance 已证实"。
5. **`DiagnosisEngine` 真引擎回放**（t2 §2.2、"改前 0 个 high pattern"、V14）未由我重跑——它依赖 dashboard 与运行期快照；我改为核对了 pattern 集与 `has_fix()`/`_check()` 语义（全部为真）。
6. 本验证是**只读静态/离线**验证：不启动脑进程、不写任何仓库文件（新增物仅 `.tmp/t5_verify_*.py` 与 `docs/analysis/analysis-t5-adversarial-verification.md`）。因此"运行时 A/B 是否真能证明接线"这一**方法论主张**我无法执行判定，只能核对其设计是否可判定、是否有回退（结论：设计可判定；F5 指出统计缺陷）。
7. 我未复核 `fly64/fly64/evolution_agent.py`（与 `evolution_skill.py` 存在同名逻辑的旧副本）是否会成为第三条写入/执行路径——若它仍可被调用，F3 的门禁需要同时在两处生效。**此项为开放风险，建议 t4 在 §7.1 明确 legacy 路径的处置。**

---

## 6. 修正优先级建议（供 t4 返修）

1. **F1（blocker）** → 先改区间/迁移/断言，否则 P1-b3 与 V6 落地即失败。
2. **F2（high）** → 改默认权重或加归一化 + 位精确回归断言；否则 §5.1 首日就改变行为并污染 V5/R1 的标定。
3. F3/F4/F5/F6（medium）→ 门禁判据与旁路守卫；CPG 取权落点；A/A 门统计与样本量；burst↔CX 优先级与可归因观测。
4. F7–F12（low）→ 数字/命名/映射一致性与措辞归属，可与上面一并返修。

> **总体判断**：这是一份**证据纪律很强、与 t1/t2/t3 的判定高度自洽**的方案——主因排序、版本边界、伪影/假设分级、A/B 类划分、20 项指标的"落点/阈值/回退"四要素都经得起对抗性核验；其最脆弱的地方恰好是**两处最关键的算式**（`3.082 ∈ [0.25,3.0]`、默认权重"逐位不变"）与**三处机制落点**（T3 门禁、CPG 取权、A/A 门）。这些都可以在不改变方案骨架的前提下修正。
>
> *验证人: verifier · 任务 t5 · attempt `7be1b297-b3c9-49a8-851c-9bec272f1123` · 全部数值为本机真实命令输出*
