# 自进化管线失效证据报告 (t2)
## Why the self-evolution loop never detected or repaired the 1100 s freeze

> **任务**: t2 — 审计自进化/自修复闭环为何未能自治修复「振荡陷阱 / 长期卡死」
> **审计员**: evo-auditor (team fly64-autonomy-evolution)
> **attempt_id**: 01a61ea2-e112-41fa-84cd-47eb86ad8284
> **审计时间**: 2026-09-24 (本机时钟 12:33; 日志数据窗口 2026-09-12 23:26 → 2026-09-17 10:22)
> **审计对象**: `fly64/skills/evolution_skill.py` (2 942 行 / 149 401 B)、`fly64/skills/evolution_agent.py`、`fly64/skills/brain_tunable_params.json`、`fly64/scripts/measure_evolution_health.py`、`fly64/skills/evolution_log.jsonl` (7 835 839 B / 13 728 行)、`fly64/skills/coach_outcomes.jsonl`、`fly64/skills/fix_catalog.json`、`fly64/skills/default_patterns.json`、`fly64/fly64/instinct_bindings.py`、`fly64/plugin/coach_outcomes.py`、`fly64/plugin/runner.py`
> **方法**: 全部为只读检查；除本文件外未修改任何仓库文件。所有结论均附**真实命令 + 真实输出**，复现命令见 §9。
> **故障基准**: `docs/analysis/fly64-trajectory-behavior-report.md` — `stuck_score=1.0`、`stuck_duration=1100.72 s`、`anomaly_state="stuck_ramp"`、`anomaly_confidence=1.0`、`reflex_active=False`、`loop_score=2.26`、`visited_cells=376/2500`、`coverage_pct=15.0`、`waste_ratio=29.34`、`jump=0/6000` 帧、末 545 帧 (124 s) 完全静止于墙边。

---

## 0. 结论 (TL;DR)

自进化管线**在结构上不可能**发现或修复这次 1100 s 卡死。六个独立、可复现的原因：

| # | 失效点 | 一句话证据 |
|---|--------|-----------|
| **1** | **闭环根本没在运行** | 最后一次进化迭代写入 `evolution_log.jsonl` 是 **2026-09-17 10:22:55**，审计时 (2026-09-24 12:33) 已停摆 **7 天**；无 python 进程、无 `.evo_loop.lock`、无计划任务，其唯一数据源 (dashboard `127.0.0.1:8765`) 不可达 |
| **2** | **没有能匹配该故障的 pattern** | 用真实引擎回放故障快照，只命中 `reflex_cooldown_gap` (medium) + `telemetry_gap` (low)；**0 个 high/critical 级 pattern 命中**，没有任何 pattern 描述「振荡陷阱」 |
| **3** | **最贴近的 pattern 被自己的"修复"改瞎了** | `ramp_trap` 的条件键 `position_unchanged_30s` **全仓库无生产者**（只有 `position_unchanged_60s`）→ 结构上永不可达；该键由 commit `048fd16` (2026-09-18) 引入，**比进化闭环死亡晚 1 天** |
| **4** | **生成的 fix 全是"注释占位"或写死 main.py 的控制补丁** | 19 条 fix 记录中 **16/19 的可执行代码行数 = 0**；全部 19 条的代码行合计 **7 行**、注释行 **87 行**；仅有的 3 条可执行 fix 中，`fix_0013` 正是 `control.x = rng.integers(60,80); control.y = 40` 这类写死控制补丁 |
| **5** | **修复验证成功率恒为 0，且 fix 是"一次性"的** | `fix_catalog.json` meta: `effective_count=0, ineffective_count=11, reverted=8`；技能自带漏斗: `13728 iterations → 44159 findings → 11 fixes → 11 verified → 0 effective`（`rate_finding_to_fix=0.0`）。`has_fix()` = "存在未回滚的 fix" → **一旦某 pattern 有了一条无效 fix，它永远不再生成新 fix** |
| **6** | **脑参数自进化（BrainMutator）信噪比 ≈ 0** | 4.46 天里 **68 个唯一试验**，其中 **41 个 delta 恰为 0.0**（"什么都没测到"），66/68 的 |delta| ≤ 0.03（低于通过门槛），**只 commit 了 1 次**（1.47%） |

**直接回答「为什么 1100 秒卡死没有被自治机制自行发现并修复」**：不是"检测到了但修不好"，而是**探测链、诊断链、修复链、验证链、运行链五处同时断开**——故障发生时（若发生在 9/17 之后）闭环不在运行；若发生在闭环运行期间，故障状态（`reflex_active=False`、贴墙、放弃逃逸）恰好落在所有 high 级 pattern 的**排除条件**里，只留下 medium 级 `reflex_cooldown_gap`，而该 pattern 的 fix 模板**一行可执行代码都没有**（`fix_0003`/`fix_0007` 全是 `#` 注释），并且它已经被"修过"并回滚过，闭环此后只会重复记录 finding、不产生任何新动作。

---

## 1. (d) 进化迭代是否真的在运行？有无近期记录？

### 1.1 结论

**没有在运行。** 已停摆 7 天；且**没有任何东西会把它重启**。

### 1.2 命令与输出

```powershell
# 1) 是否有进化进程 / 锁文件 / 计划任务
Get-CimInstance Win32_Process -Filter "Name like '%python%'" | Select ProcessId,CreationDate,CommandLine
Get-ChildItem D:\codes\flygym\fly64\skills -Force -Filter ".evo*"
Get-ScheduledTask | Where-Object { $_.TaskName -match 'fly|evo|mario' }

# 2) 唯一数据源是否活着
Invoke-WebRequest http://127.0.0.1:8765/memory.json -TimeoutSec 4 -UseBasicParsing
```

真实输出（节选）：

```
=== python processes ===
ProcessId : 12364  CreationDate : 2026/9/23 15:58:08   D:\docs\doc-search\.venv\...\python.exe -m src.mcp_server
ProcessId : 25960  CreationDate : 2026/9/23 15:58:08   ...Python.3.12...\python.exe -m src.mcp_server
ProcessId : 37320  CreationDate : 2026/9/24 12:02:20   D:\docs\doc-search\.venv\...\python.exe -m src.mcp_server
ProcessId : 25320  CreationDate : 2026/9/24 12:02:21   ...Python.3.12...\python.exe -m src.mcp_server
ProcessId : 40848  CreationDate : 2026/9/24 12:25:40   python.exe -m pytest --ignore-glob=*test_scene_rec* ...

=== lock files ===            <-- 无 fly64\skills\.evo_loop.lock
=== dashboard 8765 ===
UNREACHABLE: 无法连接到远程服务器
```

`Get-ScheduledTask` / `schtasks` 对 `fly|evo|mario` 无任何匹配 → **没有守护/计划任务**。`fly64/skills` 下亦无 `.evo_loop.lock`、`verify_state.json`、`fix_log.json`。

### 1.3 运行记录的真实时间窗

```powershell
python "$env:TEMP\evo_audit_log.py"   # 见 §9.2，只读聚合 evolution_log.jsonl
```

真实输出：

```
lines              : 13728
iteration range    : 1 .. 4433
first ts           : 2026-09-12T23:26:19.924868
last  ts           : 2026-09-17T10:22:55.874262
span days          : 4.46
top-level keys     : {'timestamp','iteration','findings','fixes','verifications','errors','evolution'}
lines with fixes   : 18
lines with verif   : 15
lines with errors  : 140
lines w/ evolution : 4299  passed: 26  committed: 26  delta==0.0: 2475
```

**关键**：日志的每行只有**finding 的 id 和 severity**，**从不记录任何传感器数值**（没有 `stuck_duration`、`position`、`loop_score`）。也就是说：**事后无法从进化日志证明闭环当时看到了什么**——这本身就是审计性缺陷。

### 1.4 闭环被重启过 ≥ 9 次（无人管理的崩溃-重启循环）

iteration 计数器在日志中反复回到低位：

```
restart epochs detected (iteration reset to <=3 after >=5): 9
   2026-09-14T23:26:41  iteration 10   -> 2
   2026-09-14T23:34:10  iteration 33   -> 2
   2026-09-14T23:46:36  iteration 70   -> 2
   2026-09-15T00:19:26  iteration 185  -> 2
   2026-09-15T19:14:24  iteration 4433 -> 2      <-- 9/15 就已到 4433, 之后重新从 1 开始
   2026-09-15T19:17:20  iteration 17   -> 2
   2026-09-16T20:51:36  iteration 1400 -> 2
   2026-09-16T22:00:59  iteration 402  -> 2
```

### 1.5 与"人类/Agent 手工修复"的关系

`evolution_history.json`（99 869 B，mtime 2026-09-23 20:47）**不是运行时产物**，是手工维护的变更台账（**81 条记录**：65 条 `EVO-001`…`EVO-073` + 16 条 `AUTO-*`；`canonical_versions.as_of = 2026-09-24T00:00:00+08:00`）。

> 结论：**2026-09-17 之后所有"进化"都是人工/Agent 写入的，闭环本身一次都没有跑过。** 台账一路更新到 2026-09-24，而闭环日志停在 2026-09-17——两者相差 7 天，正是"自治机制"与"人工劳动"的分界线。

---

## 2. (a) 是否存在能匹配「振荡陷阱 / 长期卡死」的 problem pattern？

### 2.1 两套 pattern 定义，都覆盖不到该故障

| 位置 | 数量 | 与"振荡陷阱"相关者 |
|------|------|---------------------|
| `fly64/skills/evolution_agent.py` `PROBLEM_PATTERNS` | 4 | `circle_loop` / `ramp_trap` / `reflex_cooldown_gap` / `low_coverage_stagnation` |
| `fly64/skills/evolution_skill.py` `DEFAULT_PATTERNS`（内嵌） | 15 | 同上 + `micro_loop_weave*` / `mbon_saturation` / `cliff_standoff` … |
| **实际生效**：`fly64/skills/default_patterns.json`（`PatternCatalog` 在 `evolution_skill.py:1592` 加载该文件） | **16** | 见下 |

**没有任何 pattern 的 id / name / conditions 描述"振荡陷阱 (oscillation trap)"**；最接近的是 `micro_loop_weave` / `micro_loop_weave_signal`（原地编织）与 `circle_loop`（无障碍转圈）。二者都有**会把本次故障排除掉的排除条件**（见 2.2）。

### 2.2 用**真实引擎**回放 1100 s 故障快照

把报告公布的故障指标喂进 `DiagnosisEngine`（真代码、真 `default_patterns.json`），命令见 §9.3：

```
--- scenario A) only fields the report states ---
  [medium] reflex_cooldown_gap (conf 1.00)
      fix_files: fly64/fly64/memory.py
      fix_template: 7 lines, 0 are executable code, 7 are comments
  [low] telemetry_gap (conf 1.00)
      fix_files: fly64/fly64/main.py
      fix_template: 1 lines, 0 are executable code, 1 are comments

--- scenario B) + ramp_score=0.6 (report suspects slope) ---
  [medium] reflex_cooldown_gap ... 0 executable code
  [low] telemetry_gap ... 0 executable code

--- scenario C) + ramp_score=0.6 & escape_behavior=True ---
  [high] micro_loop_weave_signal ... 0 executable code
  [medium] reflex_cooldown_gap ... 0 executable code
  [low] telemetry_gap ... 0 executable code
```

**读法**：
- **`ramp_trap` 即使在 `ramp_score=0.6`（斜坡）下也不命中**（原因见 §4-C1：条件键不存在）。
- 两个"长时卡死"类 high pattern 的排除条件正好命中本次故障：
  - `circle_loop` 要求 `wall_score ≤ 0.1`（**不在墙边**）——而故障末段 124 s 正贴墙 (`wall_stuck` 场景)；
  - `micro_loop_weave_signal` 要求 `escape_behavior = true`（**大脑正在尝试逃逸**）——而故障状态是 `reflex_active=False`、`ctrl=(0,70)`、**已经放弃逃逸**。
- 也就是说：**pattern 集偏向"在挣扎但无效"，而"已放弃的终态"只匹配 medium/low pattern。** 这正是 1100 s 卡死的终态特征。

**同一偏见也存在于脑内的异常分类器**（与轨迹报告 Problem 3/5 互为佐证）：

```
fly64/fly64/memory.py:1319-1321
    def _detect_wall_stuck(self, wall_score, escape_behavior, stuck_duration):
        return wall_score > 0.4 and escape_behavior and stuck_duration > 10.0
```

`wall_stuck` 的判定同样要求 `escape_behavior = True`。当反射放弃、`escape_behavior` 为假时，**连"贴墙卡死"这个异常状态本身都检测不出来** —— 与轨迹报告"末 545 帧静止于墙边但 wall_stuck reflex 未触发"的观测一致。这条链路上，"放弃"既是结果又是否定检测的条件，形成自锁。

### 2.3 pattern 条件键 × 生产者 的完整审计

用真实 `DataCollector.get_metrics()` 与真实 `PatternCatalog` 做集合差（§9.4）：

```
PatternCatalog: 16 patterns | get_metrics() producers: 65 keys
condition keys with NO producer: ['mbon_w_min_slope', 'position_unchanged_30s']

  circle_loop                    reachable
  ramp_trap                      UNREACHABLE missing=['position_unchanged_30s']
  reflex_cooldown_gap            reachable
  low_coverage_stagnation        reachable
  below_ground_stuck             reachable
  fallen_recovery_stuck          reachable
  suspended_animation            reachable
  wall_corner_command_decoupled  reachable
  dopamine_plateau               reachable
  cliff_standoff                 reachable
  micro_loop_weave               reachable
  micro_loop_weave_signal        reachable
  mbon_saturation                reachable
  primitive_timeout              reachable
  primitive_zero_disp            reachable
  mbon_wrong_direction           UNREACHABLE missing=['mbon_w_min_slope']

patterns total=16  structurally unreachable=2
```

（`mbon_w_min_slope` 由 `_mbon_slopes()` **条件性**产生：需 ≥8 样本且跨度 ≥3 min，故 `mbon_wrong_direction` 在长窗口下可达；`position_unchanged_30s` 则是**全仓库不存在**，见 §4-C1。）

### 2.4 为什么"字段缺失"会让整个 pattern 静默失效

`evolution_skill.py:1066-1087`：

```python
def _check(self, pattern, metrics):
    cond = pattern["conditions"]; values, total, passed = {}, 0, 0
    for key, threshold in cond.items():
        total += 1                      # <-- total 先自增
        val = metrics.get(key)
        if val is None: continue        # <-- 字段缺失只跳过，不报错
        ...
    if passed >= total: return values, passed/max(total,1)
    return None
```

**只要有 1 个条件键没有生产者，`passed` 永远 < `total`，该 pattern 永远不命中**，而唯一痕迹是 severity=low 的 `telemetry_gap`（把缺失字段名塞进 `current_values.missing_fields`）。日志中 `telemetry_gap` 出现了 **4 773 次**（占日志行数的 34.8%），却从未被当作故障处理——它自己也是 low 级。

---

## 3. (b) 生成的 fix 是否都是写死到 main.py 的控制补丁？

### 3.1 是（但比这更糟：绝大多数 fix 根本不是代码）

`default_patterns.json` 中 fix 的落点分布（§9.5）：

```
fly64/fly64/main.py            8 patterns
fly64/fly64/model.py           6 patterns
fly64/fly64/memory.py          3 patterns
fly64/fly64/motor_primitives.py 2 patterns
fly64/fly64/mushroom_body.py   1 patterns
```

即 **16 个 pattern 中 8 个直接把补丁指向 `main.py`**——正是用户明确排除的**硬编码控制补丁路线**。

### 3.2 19 条实际 fix 记录的内容成分（逐条）

```
  fix_0001  circle_loop                code=0  comment=4  effective=None  reverted=True  target=fly64/fly64/main.py
  fix_0002  fallen_recovery_stuck      code=0  comment=7  effective=None  reverted=True  target=fly64/fly64/main.py
  fix_0003  reflex_cooldown_gap        code=0  comment=7  effective=None  reverted=True  target=fly64/fly64/memory.py
  fix_0004  micro_loop_weave           code=0  comment=3  effective=False reverted=False target=fly64/fly64/model.py
  fix_0005  low_coverage_stagnation    code=2  comment=3  effective=None  reverted=True  target=fly64/fly64/main.py
  fix_0006  micro_loop_weave_signal    code=0  comment=4  effective=None  reverted=True  target=fly64/fly64/model.py
  fix_0007  reflex_cooldown_gap        code=0  comment=7  effective=None  reverted=True  target=fly64/fly64/memory.py
  fix_0008  suspended_animation        code=0  comment=3  effective=False reverted=False target=fly64/fly64/main.py,model.py
  fix_0009  low_coverage_stagnation    code=2  comment=3  effective=False reverted=False target=fly64/fly64/main.py
  fix_0010  circle_loop                code=0  comment=4  effective=False reverted=False target=fly64/fly64/main.py
  fix_0011  cliff_standoff             code=0  comment=4  effective=False reverted=False target=main.py,model.py,memory.py
  fix_0012  fallen_recovery_stuck      code=0  comment=8  effective=False reverted=False target=fly64/fly64/main.py
  fix_0013  ramp_trap                  code=3  comment=3  effective=False reverted=False target=fly64/fly64/main.py
  fix_0014  telemetry_gap              code=0  comment=1  effective=False reverted=False target=
  fix_0015  mbon_saturation            code=0  comment=1  effective=False reverted=False target=fly64/fly64/mushroom_body.py
  fix_0016  below_ground_stuck         code=0  comment=8  effective=False reverted=False target=fly64/fly64/memory.py
  fix_0017  fast_circle_help           code=0  comment=4  effective=None  reverted=True  target=
  fix_0018  reflex_ineffective_circling code=0  comment=11 effective=None  reverted=True  target=
  fix_0019  primitive_zero_disp        code=0  comment=2  effective=False reverted=False target=main.py,motor_primitives.py
  TOTAL executable lines in all 19 fixes: 7 ; comment lines: 87
  fixes whose template has ZERO executable lines: 16/19
```

**7 行可执行代码 / 87 行注释**。其中 3 行就是 `fix_0013`（`ramp_trap`）写进 `main.py` 的硬编码控制补丁：

```python
if ramp_score > 0.5 and stuck_duration > 180:
    control.x = rng.integers(60, 80) * (-1 if rng.random() < 0.5 else 1)
    control.y = 40
```

其效果记录为 **`effective: false`，`baseline_stuck=458.98 → post_fix_stuck=464.72`（更差）**。

**与本次故障直接相关的那条 fix（`fix_0003`/`fix_0007`, pattern=`reflex_cooldown_gap`）全文是注释**：

```
"# Fix: Make reflex cooldown adaptive based on stuck_duration\n
 # File: fly64/fly64/memory.py\n
 # In ReflexController.__init__: keep base_cooldown_duration=10.0\n
 # In _start_reflex: replace fixed cooldown with adaptive formula:\n
 #   cooldown = max(2.0, self.base_cooldown_duration - stuck_duration * 0.05)\n ..."
```

→ 也就是说：**对 1100 s 卡死唯一能命中的那个 pattern，闭环"生成的修复"就是一段注释；没有任何代码被执行。**

### 3.3 fix 生效统计（技能自报）

```json
{"total_fixes": 19, "effective": 0, "ineffective": 11, "pending": 8,
 "reverted": 8, "effectiveness_rate": 0.0, "average_effectiveness_score": 0.003}
```

`fix_catalog.json` meta 亦为 `effective_count: 0, ineffective_count: 11, reverted_count: 8`。

---

## 4. (c) 是否存在「已接线但结构上不可达」的缺陷？（instinct_bindings / EVO-066 同类）

**存在，至少 6 处**，全部有命令与输出支撑。

### C1 — `ramp_trap` 的条件键没有生产者（最致命，直接对应本次故障）

```powershell
Get-ChildItem D:\codes\flygym\fly64 -Recurse -Include *.py,*.json,*.js,*.html,*.md -File |
  Where-Object { $_.FullName -notmatch '__pycache__|\.pytest-run|node_modules' } |
  Select-String -Pattern "position_unchanged_30s"
```

真实输出（仅两处命中，且都不是生产者）：

```
.tmp\.t4-full\test_first_observation_primes_0\README.md:42
...
skills\default_patterns.json:50
```

对照生产者：

```
skills\evolution_skill.py:863   def position_unchanged_60s(self) -> bool:
skills\evolution_skill.py:1009  vals["position_unchanged_60s"] = self.position_unchanged_60s()
```

`default_patterns.json:50` 声明：

```json
"ramp_trap": { "conditions": {"ramp_score": {"min":0.5},
                              "stuck_duration": {"min":60},
                              "position_unchanged_30s": true} }
```

**只有 `position_unchanged_60s` 存在；`position_unchanged_30s` 全仓库零生产者 → `ramp_trap` 永不命中。** 且 `threshold_justification` 仍写着 "stuck>180s"，而条件已被改成 `min: 60` —— 手工改动痕迹。

引入该键的提交：

```
$ git log -5 --format='%h %ad %s' --date=short -- fly64/skills/default_patterns.json
d86fc9d 2026-09-23 fix(HOTFIX): 修复 master 上诊断目录为空的生产故障（UTF-8 BOM + 回退语义）
048fd16 2026-09-18 fix(pattern): ramp_trap阈值180s->60s + position_unchanged_30s
...
```

**时间线**：闭环最后一行日志 = 2026-09-17 10:22；`048fd16`（把这唯一匹配"斜坡长时卡死"的 pattern 改瞎）落地于 **2026-09-18** ——**比闭环死亡晚一天**。因此这个自我改动**既没有被任何运行时观测覆盖，也没有在日志里留下任何痕迹**：闭环死后仍在被"修"，而修订反而解除了对该故障模式的探测能力。

**被日志追溯印证**：9/17 之前 `ramp_trap` 命中过 5 631 次（当时用旧键 `position_unchanged_60s`，可达）；改键之后它将永远沉默。

### C2 — 场景→策略本能固化（P4.4）在真实语料上不可达

`fly64/plugin/coach_outcomes.py:51-66` 把 `memory["scene_label"]` 写进 pending；`fly64/plugin/runner.py:515` 用 `outcome["scene_label"]` 调 `record_outcome`；`fly64/fly64/instinct_bindings.py:265-268`：

```python
scene = scene_key(scene_label)
params = binding_params(keys)
if not scene or not params:
    return None            # <-- scene_label 为空 => 整条证据链直接被丢弃
```

真实语料：

```
coach_outcomes.jsonl   rows=30  labeled=0  unlabeled=30
                       verdicts={'unchanged': 21, 'worse': 1, 'improved': 8}
      scene_label='' scene_id='' verdict=unchanged keys=['escape','exploration','fallen_recovery']
```

**30/30 行的 `scene_label` 为空**（`scene_id` 亦空）→ `record_outcome` 直接 `return None` → 绑定库无新证据。`measure_evolution_health.py --p44` 的独立读数完全一致：

```
  scenes / signatures : 1 / 2
  promoted            : 0
  signatures by improved count : {1: 2}
    ... imp=1 unch=0 worse=0 needed=1 | fallen_recovery.mode=directional_climb|exploration.turn_bi
  outcome lines      : 30  {'unchanged': 21, 'worse': 1, 'improved': 8}
  usable for a signature : 0  (skipped: 30 without scene label, 0 without keys)
  distinct signatures : 0 | outcomes reusing one: 0
```

**"接线完整、结构上不可达"**——`main.py:1686-1698` 确实热重载 `get_binding()`，`instinct_bindings.py` 文件头也自述了同类缺陷（第 27 行："The mechanism was wired, tested, and *structurally unreachable* — the same class of defect as the t6 passthrough bug"）。当前状态：`scene_strategy_bindings.json` 只有 2 个桶、各 `improved=1`（门槛 2）、`promoted: false`，所以 `get_binding()` 恒返回 `None`，本能路径完全休眠。

**附带证据（证据链已断裂）**：`coach_outcomes.jsonl` 现存 30 行全无 label，但绑定库里确实存在 2026-09-17 18:31/18:35 记录的**带场景名**的 2 条 improved（`first_seen 1789641096.7 / 1789641318.1`）。也就是说：**曾经进入绑定库的两条真实证据，如今已不在 `coach_outcomes.jsonl` 中**。同时 `coach_outcomes.jsonl.hwm` / `.snap` 侧车文件**都不存在**（`Get-ChildItem skills -Force -Filter "coach_outcomes*"` 只返回主文件），而 `coach_outcomes.py:117-150` 的 `guard_outcomes()` 正依赖这两个侧车文件来防止语料被截断（其 docstring 记录过一次 "45 rows -> 30" 的截断事故）。**即：防截断保护没有生效，审计轨迹已不可还原。**

### C3 — 活文件里存在"写进去也无效"的越界值（P1-5 家族，活体复现）

把 `skills/active_strategy.json` 与 `brain_tunable_params.json` 的注册区间逐键比对（§9.6）：

```
param                                     live value   registry range   status
exploration.bold_turn_bias                0.25         (not in registry) ORPHAN KEY   <- 实为 turn_bias 的声明别名, 无害
exploration.turn_bias                     0.25         [0.0, 0.25]      ok
exploration.bold_explore_stuck_s          60.0         [1.0, 10.0]      *** OUT OF RANGE (silently clamped by main.py) ***

live keys out of registry range: 1  orphan keys: 1
```

`exploration.bold_explore_stuck_s = 60.0` 却注册为 `[1,10]`（注册表自己的 description 明确写着"main.py 的 `max(1, min(10, x))` 是硬界限……任何合法采样（含旧默认 60）都会被静默钳掉"）→ **活文件里正躺着一个"机制存在、报告成功、无法生效"的实例**。这个参数恰恰是"卡死多久后强制突围"的门限（本故障中 `stuck_duration=1100 s`）。

另外 `exploration.turn_bias = 0.25` 正好压在 main.py "R31-fix12 振荡防护" 的硬上限上（**振荡防护钳位**），即进化值被顶在"未放大振荡"的边界值。

### C4 — 监督工具本身无法证实 "39/39 wired"（未决项，须运行时 A/B）

`brain_tunable_params.json` 在 2026-09-23 被重新审计为 **39 参数全部 `wired: true`**，其 `wired_note` 写着"Re-check with `scripts/audit_contract_pairs.py` before flipping a flag"。执行该指定工具：

```powershell
python D:\codes\flygym\fly64\scripts\audit_contract_pairs.py
```

真实输出（节选）：

```
### skills/active_strategy.json
    scanned 7 .py + 16 web file(s), 47 keys
    [unreferenced    ] exploration.bold_turn_bias                w=0 r=0 decl=0
    [unreferenced    ] exploration.revisit_penalty_scale         w=0 r=0 decl=0
    ... (39 行, 全部 unreferenced w=0 r=0 decl=0) ...
```

我的独立核查（`§9.7`，把每个 param 的叶子键在全仓 `fly64/`、`plugin/`、`scripts/` 的 90 个 .py 里做整词计数）：

```
PARAMS WITH ZERO SOURCE OCCURRENCE IN fly64/, plugin/, scripts/: 0   (全部 39 个都有出现)
```

**诚实结论**：该"unreferenced"更可能是**静态扫描对 `_expl.get("turn_bias")` 这类"扁平化后读取"的盲区**（`audit_contract_pairs.py` 在 166-169 行确实把 `fly64/fly64/main.py` 纳入了扫描范围，说明它找的是点号键的读写对，而非归一化后的叶键）。因此我不主张"39 个都是死键"；我主张的是：**指定复核工具给出的报告无法支撑 `wired: true` 的结论**，即"接线"目前缺乏可信的判定手段。EVO-066 的原始结论（21 个 schema 参数中仅 7 个有消费者，`git log` 中 `c0f27e0`）与随后一串 `wire all 21 params` / "registry 39 params / 6 sections all wired" 提交（`f3501e7`/`5b62706`/`218c6c0`/`ea509a9`/`f486ad0`）表明这块一直是"指标宣称 vs 实际消费"的反复争夺区。**建议的确定性判据是运行时 A/B**：写一个越界/极端值，观察对应消费点是否变化——这正是 EVO-066/EVO-072 家族反复漏掉的验证方式。

### C5 — fix 是"一次性"的：一条无效 fix 永久关闭一个 pattern

`evolution_skill.py:1163-1164`：

```python
def has_fix(self, pid: str) -> bool:
    return any(f.pattern_id == pid and not f.reverted for f in self.fixes)
```

`evolution_skill.py:2644`：`if not self.fix_catalog.has_fix(f.pattern_id) and self.auto_fix:` → **只要该 pattern 有一条"未回滚"的 fix，就永远不再生成新 fix——哪怕这条 fix 记录为 `effective=False`。** 真实输出（`§9.5`）：

```
  patterns with a fix entry: ['below_ground_stuck','circle_loop','cliff_standoff',
    'fallen_recovery_stuck','fast_circle_help','low_coverage_stagnation','mbon_saturation',
    'micro_loop_weave','micro_loop_weave_signal','primitive_zero_disp','ramp_trap',
    'reflex_cooldown_gap','reflex_ineffective_circling','suspended_animation','telemetry_gap']
  patterns still eligible   : ['dopamine_plateau','mbon_wrong_direction',
    'micro_loop_weave_signal','primitive_timeout','reflex_cooldown_gap',
    'wall_corner_command_decoupled']
```

⇒ **当前被"未回滚 fix"永久关闭的 pattern 共 13 个**（两个列表之差）：

```
below_ground_stuck, circle_loop, cliff_standoff, fallen_recovery_stuck,
fast_circle_help, low_coverage_stagnation, mbon_saturation, micro_loop_weave,
primitive_zero_disp, ramp_trap, reflex_ineffective_circling, suspended_animation, telemetry_gap
```

（`fast_circle_help` / `reflex_ineffective_circling` 的 fix 已不属于现行 16 个 pattern；`micro_loop_weave_signal` 与 `reflex_cooldown_gap` 因历史 fix 均被回滚而"可再修"——但它们在 2026-09-16T21:03 之后各自又命中 2 041 / 3 046 次，**依然一条新 fix 都没生成**，见 §4-C6。）

**对本次故障的意义**：`ramp_trap` 的 fix_0013 是"未回滚"的，因此 `ramp_trap` 已被关闭；而它的 fix 模板是硬编码控制补丁且 `effective=false`。**"失败"没有重开入口，只有人工 `revert_fix` 才行。**

### C6 — `--auto-fix` 默认关闭 + 失败熔断

`main()` 中 `p.add_argument("--auto-fix", action="store_true")`（**默认 False**）；`FixExecutor` 只在 `auto_fix=True` 时构造（`evolution_skill.py:2580`）。也就是说**不显式传 `--auto-fix` 时，闭环只诊断、不修复**。

另有熔断：连续 3 次 fix 失败 → `self.auto_fix = False`（`:2736-2740`，注释为 "auto-fix paused until next restart"），**只在 `errors` 里留一行，无告警、无持久化、无外部通知**。日志里没有出现该熔断行（140 行 errors 全部是 evolution trial / README 权限 / brain 版本变更），因此**不能断言**本次是被熔断关闭的；但修复在 2026-09-16T21:03（fix_0019）之后**彻底停止**，而此后 4 757 行日志中 `reflex_cooldown_gap` 仍命中 3 046 次、`micro_loop_weave_signal` 仍命中 2 041 次（二者当时都是"可再修"状态）却**一条 fix 都没生成**——说明最后那段运行就是**没有开启 auto-fix（或已被人为关闭）的诊断-only 模式**。

### C7 — 技能自身的版本链自检当前是 **红的**

```powershell
cd D:\codes\flygym\fly64; python -m skills.evolution_skill --history-check
```

真实输出末行：

```
BRAIN_VERSION(main.py)=2.24.0  SKILL_VERSION=3.5.0  canonical=(2.24.0/3.5.1)
  FAIL — SKILL_VERSION 3.5.0 != canonical 3.5.1 (agent.md rules 15/17)
```

（`evolution_history.json.canonical_versions.skill = "3.5.1"`，而 `evolution_skill.py:42` 为 `SKILL_VERSION = "3.5.0"`；`git status` 显示该文件未被修改，即 **HEAD 上就是红的**。）这条自检失败意味着"用自检守卫生效"的治理链本身已失效。

---

## 5. 脑参数自进化（BrainMutator / Phase 6）：跑了，但测不到东西

```powershell
cd D:\codes\flygym; python fly64\scripts\measure_evolution_health.py --phase6 --p44
```

真实输出（节选）：

```
PHASE 6 (BrainMutator) ATTRIBUTION
  schema params      : 39 total | 39 wired | 0 inert (0.0% inert)
  unique trials      : 68
  commits / rollbacks: 1 / 67  (commit rate 1.47%)
  fitness delta      : min=-0.0443 p50=0.0 max=0.0397 mean=-0.0018
  delta EXACTLY 0.0  : 41 / 68 (60.3%)  <- trial measured nothing
  |delta| <= 0.03    : 66 / 68 (97.1%)  <- below the pass threshold
  moved dims (total) : wired=1069 inert=0  (inert share 0.0%)
  commits by # wired dims moved : {16: 1}
  >>> commits with ZERO live-dim movement: 0 / 1 (0.0%)
```

补充时序统计（§9.2 脚本）：

```
unique trial param-sets  : 68
trial interval  median   : 404 s (6.7 min)   mean 649 s
trials per hour          : 5.63
delta==0.0 trials        : 41
passed trials            : 1
last trial at            : 2026-09-17T10:14:52
```

**含义**：
1. **4.46 天里只完成 68 个"唯一"试验**（日志里 4 299 行带 evolution 字段，但绝大多数是把**同一个**试验结果重复追加——`measure_evolution_health.py` 的 docstring 也点明了这个重复写入问题："the log appends the LAST evolution result to every iteration line"）。
2. **60.3% 的试验 delta 恰为 0.0**：baseline 与 current 完全相等 → 该试验**什么都没测到**；97.1% 低于 0.03 的通过门槛。**进化在噪声中搜索。**
3. **通过率 1.47%**：搜到的那 1 次 commit 也无法归因到行为（唯一 commit 动了 16 个 wired 维度，multi-dim 变更不可归因）。
4. **EVO-066 的"21 参数仅 7 个有消费者"已被推翻/改写为 39/39 wired**，但**适应度信号本身仍是主要瓶颈**（脚本自己的结论文字："The dominant problem is the fitness signal itself"）。这与 §4-C4 的"接线判定不可信"叠加，意味着"改对了参数"和"改动了参数"目前都难以分辨。

### 5.1 闭环自身的健康趋势（3 条记录，含 1 条退化行）

```
$ type fly64\skills\evolution_health_trend.jsonl
{"ts": "2026-09-18T07:11:59+00:00", "scenes": 1, "signatures": 2, "promoted": 0,
 "by_improved": {"1": 2}, "usable_outcomes": 0, "signature_reuse_rate": 0.0,
 "outcomes_total": 30, "phase6_trials": 68, "phase6_commits": 1,
 "phase6_delta_exact_zero": 41, "phase6_instrumented": 0}
{"ts": "2026-09-20T15:56:25+00:00", "health_score": null, "stuck_duration": null,
 "coverage_pct": null, "fixes_total": 0, "evo_trials": 0, "evo_passed": 0}
```

- 只有 **2 条**有效时间序列点（相距 2 天），不足以判断趋势；
- 9-20 那条**字段全为 null**（无遥测源时被写成的退化行），说明"健康度量"没有与闭环绑定成日程。

---

## 6. 闭环自己的元指标（`--funnel`）：漏斗在最后一节归零

```powershell
cd D:\codes\flygym\fly64; python -m skills.evolution_skill --funnel
```

真实输出：

```json
{
  "iterations": 13728,
  "findings_fired": 44159,
  "patterns_seen": 13,
  "fixes_recorded": 11,
  "fixes_verified": 11,
  "fixes_effective": 0,
  "rate_finding_to_fix": 0.0,
  "rate_fix_to_verified": 1.0,
  "rate_verified_to_effective": 0.0,
  "top_patterns": [["micro_loop_weave_signal", 9259], ["reflex_cooldown_gap", 7764],
                   ["fallen_recovery_stuck", 7665], ["ramp_trap", 5631], ["telemetry_gap", 4773]]
}
```

**13 728 次迭代 → 44 159 次 finding → 11 条 fix → 11 条"验证"→ 0 条生效。** 技能自生成的 `skills/README.md` 亦自报：

```
| Total Fixes Applied | 19 |
| Effective | 0 |
| Ineffective | 11 |
| Effectiveness Rate | 0.0% |
```

---

## 7. 因果链：为什么 1100 s 卡死没有被自治修复

```
[运行层] 闭环 2026-09-17T10:22 停止, 无守护/无计划任务/无锁, 数据源 8765 死
   │        └─ 9/17 之后 7 天的全部修复都是人工(evolution_history.json 至 EVO-073)
   ▼
[探测层] 闭环只从 dashboard 读数据(DataCollector.fetch_json → 127.0.0.1:8765)
   │        └─ 数据源不在 ⇒ "Waiting for dashboard..." ⇒ 连 finding 都不会产生
   ▼
[诊断层] 16 个 pattern 中 2 个结构上永不可达(ramp_trap / mbon_wrong_direction)
   │      "振荡陷阱"没有任何 pattern; 最贴近的 2 个 high pattern 的排除条件
   │      恰好覆盖本故障终态(贴墙 wall_score>0.1 / 已放弃逃逸 escape_behavior=false)
   │      ⇒ 只剩 medium 的 reflex_cooldown_gap + low 的 telemetry_gap
   ▼
[修复层] reflex_cooldown_gap 的 fix 模板 = 7 行纯注释(0 行可执行代码)
   │      其余 pattern 的 fix 主要落点 = main.py 硬编码控制补丁(8/16 pattern)
   │      fix 一次性: has_fix(未回滚) ⇒ 该 pattern 永久关闭
   │      auto-fix 默认关闭; 连续 3 次失败自动熔断(仅一行 errors, 无告警)
   ▼
[验证层] 19 条 fix: 16 条零可执行代码, 3 条硬编码补丁; effective=0, ineffective=11, reverted=8
   │      ⇒ "修过了"成为关闭后续修复的理由, 而"有效"从未发生
   ▼
[参数层] BrainMutator: 68 试验 / 60.3% delta 恰为 0.0 / 1 次 commit
   │      活策略文件里还有越界值(bold_explore_stuck_s=60 vs [1,10]) ⇒ 静默钳位
   ▼
[本能层] scene→strategy 固化: 30/30 语料 scene_label 为空 ⇒ record_outcome 直接 return None
          绑定库 2 桶各 improved=1(门槛2) ⇒ promoted=0 ⇒ get_binding() 恒 None
          防截断侧车(.hwm/.snap)缺失 ⇒ 曾经入库的证据已从语料消失
```

**一句话**：这条"自修复"链的每一节都只在**受控/合成条件下**被测试过（单测里注入带 label 的 memory、注入完好的 dashboard），因此每一节都"测试通过"；而在真实运行里，**探测没数据、诊断没 pattern、修复没代码、验证没成功、参数没信号**。

---

## 8. 对最终方案 (docs/analysis/fly64-autonomy-evolution-plan.md) 的直接含义

1. **"让自治机制自己修复"这条路目前是不可用的**，不能把方案建立"闭环会自己发现并修"的假设上。必须先修管线，再谈自治。
2. **当前闭环能产出的唯一"可执行"修复就是写死 main.py 的控制补丁**（`fix_0013` 就是范例，且 `effective=false`）。这与用户明确排除的路线**同源**——所以"排除硬编码控制补丁"不仅是设计偏好，更是**移除闭环目前唯一的输出形态**。
3. **替代路线必须落在脑参数/脑电路空间，并且要有可信的适应度**：`--phase6` 的 60.3% 零 delta 说明现有 `fitness()` 无法分辨差异。方案需要规定**可验证的适应度**（例如以 `waste_ratio`/`net displacement`/`stuck_duration` 的长时间窗观测替代 120 s 瞬时窗，并要求 A/B 双向复现）。
4. **"接线判定"必须有确定性判据**：`brain_tunable_params.json` 的 `wired` 标志目前靠静态工具自证（§4-C4），需改为运行时 A/B（写值→观察消费点变化），否则 EVO-066/EVO-072 的"机制存在、报告成功、无法生效"家族会继续复发。
5. **pattern 集需要覆盖"已放弃的终态"**：现有 high 级 pattern 都要求"还在挣扎"（`escape_behavior=true`、`wall_score<0.1`），必须新增/改造成以 `stuck_duration` + `loop_score` + `reflex_active=false` + `waste_ratio` 为主判据的"终态卡死"检出（**注意：不要用写死补丁，而是接入脑内逃逸/突围驱动**）。
6. **闭环需要守护与告警**：无 guard、无计划任务、失败静默（熔断仅一行 errors、fix 归零无告警）是"1100 s 无人知晓"的组织性成因；方案应包含"进化闭环存活自检 + 元指标(漏斗)阈值告警"。
7. **审计性补齐**：`evolution_log.jsonl` 必须记录观测值（现在只有 finding id），否则任何"闭环当时看到了什么"的复盘都不可能；`coach_outcomes` 的防截断侧车必须真正生效。

---

## 9. 复现命令与脚本（全部只读）

> Windows PowerShell 不支持 heredoc；下列 Python 片段先用 `Set-Content` 落到临时文件再执行（本次审计即如此，脚本位于 `%TEMP%\evo_*.py`，未写入仓库）。

### 9.1 健康度量（官方工具）

```powershell
cd D:\codes\flygym
python fly64\scripts\measure_evolution_health.py --phase6 --p44
```

### 9.2 进化日志聚合 + 试验节奏

```powershell
$py = @'
import json, collections, datetime, statistics
p=r"D:\codes\flygym\fly64\skills\evolution_log.jsonl"
n=0; find=collections.Counter(); sev=collections.Counter()
fixes_nonempty=verif_nonempty=errors_nonempty=0
ev=ev_pass=ev_commit=delta0=0; keys=collections.Counter(); ts=[]; iters=[]
for line in open(p,encoding='utf-8'):
    line=line.strip()
    if not line: continue
    try: r=json.loads(line)
    except Exception: continue
    n+=1; keys.update(r.keys()); ts.append(r.get('timestamp')); iters.append(r.get('iteration'))
    if r.get('fixes'): fixes_nonempty+=1
    if r.get('verifications'): verif_nonempty+=1
    if r.get('errors'): errors_nonempty+=1
    for f in r.get('findings') or []:
        find[f.get('id')]+=1; sev[f.get('severity')]+=1
    e=r.get('evolution')
    if isinstance(e,dict):
        ev+=1
        if e.get('passed'): ev_pass+=1
        if e.get('committed'): ev_commit+=1
        if float(e.get('delta') or 0)==0.0: delta0+=1
print('lines',n,'iters',min(iters),max(iters))
print('first',datetime.datetime.fromtimestamp(min(ts)),'last',datetime.datetime.fromtimestamp(max(ts)))
print('keys',dict(keys),'fixes',fixes_nonempty,'verif',verif_nonempty,'errors',errors_nonempty)
print('evolution',ev,'passed',ev_pass,'committed',ev_commit,'delta0',delta0)
print(find.most_common())
print(sev)
# 唯一试验与节奏
seen={}; trials=[]
for line in open(p,encoding='utf-8'):
    line=line.strip()
    if not line: continue
    try: r=json.loads(line)
    except Exception: continue
    e=r.get('evolution')
    if not isinstance(e,dict) or not e.get('params'): continue
    k=tuple(sorted((a,round(float(b),6)) for a,b in e['params'].items() if isinstance(b,(int,float))))
    if k in seen: continue
    seen[k]=r['timestamp']; trials.append((r['timestamp'],e.get('delta'),e.get('passed')))
trials.sort()
g=[trials[i][0]-trials[i-1][0] for i in range(1,len(trials))]
print('unique trials',len(trials),'median gap %.0fs'%statistics.median(g),
      'per hour %.2f'%(len(trials)/((trials[-1][0]-trials[0][0])/3600)),
      'delta0',sum(1 for t in trials if float(t[1] or 0)==0.0),
      'passed',sum(1 for t in trials if t[2]))
'@
Set-Content "$env:TEMP\evo_audit_log.py" $py -Encoding UTF8
$env:PYTHONIOENCODING="utf-8"; python "$env:TEMP\evo_audit_log.py"
```

### 9.3 用真实引擎回放故障快照

```powershell
$py = @'
import sys
sys.path.insert(0, r"D:\codes\flygym\fly64")
from skills.evolution_skill import DiagnosisEngine, PatternCatalog
FREEZE = {"stuck_duration":1100.72,"anomaly_state":"stuck_ramp","reflex_active":False,
 "anomaly_state_not_idle":True,"loop_score":2.26,"coverage_pct":15.0,"visited_cells":376,
 "pos_y":120.0,"waste_ratio":29.34,"control_x_zero":True,"control_y_zero":False,
 "jump_not_active":True,"control_magnitude":70.0,"revisit_count":128.0,"health_score":0.0}
class Stub:
    def __init__(self,m): self.m=m
    def get_metrics(self): return dict(self.m)
for tag,extra in (("A",{}),("B",{"ramp_score":0.6}),("C",{"ramp_score":0.6,"escape_behavior":True})):
    m=dict(FREEZE); m.update(extra)
    print("--- scenario",tag,"---")
    for f in DiagnosisEngine(Stub(m), PatternCatalog()).evaluate():
        body=[l for l in f.fix_template.splitlines() if l.strip()]
        code=[l for l in body if not l.strip().startswith('#')]
        print("  [%s] %s conf=%.2f files=%s code_lines=%d comment_lines=%d"
              % (f.severity,f.pattern_id,f.confidence,f.fix_files,len(code),len(body)-len(code)))
'@
Set-Content "$env:TEMP\evo_replay.py" $py -Encoding UTF8
$env:PYTHONIOENCODING="utf-8"; python "$env:TEMP\evo_replay.py"
```

### 9.4 pattern 条件键 × 生产者 可达性审计

```powershell
# 见 §9.3 同法建脚本，核心：
#   dc = DataCollector(window_seconds=120); 用 time.time()-10+i 作为样本时间戳，循环 dc.sample(...) 6 次
#   metrics = dc.get_metrics();  cat = PatternCatalog()
#   [k for p in cat.patterns for k in p["conditions"] if k not in metrics]
# 输出: condition keys with NO producer: ['mbon_w_min_slope', 'position_unchanged_30s']
```

> **注意**：样本时间戳必须用接近 `time.time()` 的值，否则 `DataCollector._trim()` 会把样本全部裁掉，`get_metrics()` 只剩 6 个键（本次审计第一版即踩此坑，已修正后重跑）。

### 9.5 fix 目录成分与落点

```powershell
$py = @'
import sys, collections
sys.path.insert(0, r"D:\codes\flygym\fly64")
from skills.evolution_skill import PatternCatalog, FixCatalog
cat=PatternCatalog(); fc=FixCatalog()
hits=collections.Counter()
for p in cat.patterns:
    for f in (p.get("fix_files") or []): hits[f]+=1
print(hits.most_common())
for e in fc.fixes:
    body=[l for l in (e.fix_template or "").splitlines() if l.strip()]
    code=[l for l in body if not l.strip().startswith("#")]
    print(e.id,e.pattern_id,"code=%d"%len(code),"comment=%d"%(len(body)-len(code)),
          e.effective,e.reverted)
print(fc.get_statistics())
'@
Set-Content "$env:TEMP\evo_b2.py" $py -Encoding UTF8
$env:PYTHONIOENCODING="utf-8"; python "$env:TEMP\evo_b2.py"
```

### 9.6 活策略 vs 注册区间

```powershell
# 逐键比对 skills/active_strategy.json 与 brain_tunable_params.json 的 [min,max]
# 输出: live keys out of registry range: 1   (exploration.bold_explore_stuck_s = 60.0 vs [1.0,10.0])
```

### 9.7 参数消费者独立核查（整词 grep）

```powershell
# 对 brain_tunable_params.json 的 39 个 pid, 取叶子键, 在 fly64/fly64, fly64/plugin, fly64/scripts 的 *.py 中整词计数
# 输出: PARAMS WITH ZERO SOURCE OCCURRENCE IN fly64/, plugin/, scripts/: 0
```

### 9.8 关键只读证据文件清单

```
fly64/skills/evolution_log.jsonl          7 835 839 B  13 728 行  最后写入 2026-09-17 10:22:55
fly64/skills/fix_catalog.json                21 679 B  19 条 fix  effective=0
fly64/skills/coach_outcomes.jsonl            13 169 B  30 行      30/30 scene_label 为空
fly64/skills/scene_strategy_bindings.json     1 746 B  2 桶       promoted=0
fly64/skills/brain_tunable_params.json       15 424 B  39 参数    全 wired=true, 复核于 2026-09-23
fly64/skills/default_patterns.json           22 888 B  16 pattern 含 position_unchanged_30s
fly64/skills/evolution_health_trend.jsonl       470 B  2 条有效快照
fly64/skills/evolution_history.json          99 869 B  81 条手工台账 (EVO-001..EVO-073)
fly64/skills/active_strategy.json             1 543 B  含 1 个越界值
```

---

## 10. 证据边界与诚实声明（本次**未能**验证的部分）

1. **故障原始数据不在仓库内**：`trajectory.json` / `memory.json` 在本工作区**不存在**（全盘搜索无结果；报告 §附录亦未附文件路径）。因此 §2.2 的回放**使用报告公布的指标值**，不是原始流。若需更强证据，需要导出日志原件。
2. **闭环停摆期间故障是否发生**：报告数据的时间戳是"10728.07 s ~ 12053.03 s"（仿真/会话内时间），**无法换算为墙钟**，故不能断言 1100 s 卡死就发生在那 7 天停摆窗口内。但这不影响结论：**无论在不在窗口内，闭环都修不了它**（窗口内则是 §2/§3 的诊断/修复链断裂，窗口外则连运行都没有）。
3. **`audit_contract_pairs.py` 的 "unreferenced"** 我按"静态扫描盲区"处理，未主张 39 个都是死键（§4-C4）。判定需要运行时 A/B。
4. **熔断（连续 3 次 fix 失败 → auto_fix=False）在本次日志中未见触发行**，故只能作为设计风险列出（§4-C6），不作为已观测事实。
5. 所有检查均为只读；**本文件是本次审计唯一写入物**。

---

*审计员: evo-auditor · 团队: fly64-autonomy-evolution · 任务: t2 · attempt: 01a61ea2-e112-41fa-84cd-47eb86ad8284*
*证据形态: 真实命令 + 真实输出（§1–§6），复现命令见 §9；所有原始文件在审计时点未做任何修改。*
