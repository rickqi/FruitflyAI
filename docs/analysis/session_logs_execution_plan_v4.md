# Fly64 下一步执行方案 v4

> **依据**：`docs/analysis/session_logs_analysis_v4.md`（A4 综合报告）—— 汇总 A0（captain 口径裁定 rev 2）/ A1（主题主线）/ A2（顽疾根因 rev 3）/ A3（代码状态）
> **口径**：**11 个唯一 session / 874 条真实用户提问**；数据源 `.tmp/sessions_v3/`；代码基线 `fly64` HEAD `cf2f472`，Brain 2.23.12 / Skill 3.5.0
> **生成**：report-synthesizer（A4）· 2026-09-22
> **核心原则**：**先把"变更 → 可观测行为 → 结果证据"的闭环建起来，再谈新能力。**

---

## 0. 为什么是这个方案（三个前提）

| # | 前提 | 证据 |
|---|---|---|
| 1 | **当前无法判定"改好了没有"** | `pytest tests` = 62 failed / 1130 passed / 37 skipped，**34 条 NEW 不在基线**、**10 条基线已通过（腐化）**；`test_version_consistency` 2 failed（A3 §5，A4 已复跑）；点号死键第 8 例仍在（A3 §4.3c，`__generation=161`） |
| 2 | **最新五处高风险改动零实机证据** | `artifacts/latest-*.npz` 停在 09-19 12:13；`evolution_log.jsonl` 停 09-17；`param_history.jsonl` 不存在（A3 §3.1） |
| 3 | **用户最后一天的诉求就是"验证生效"** | 09-22 17:09/17:18「运动动作为什么大部分没有尝试」；09-22 18:12 用户亲手定位键名归一化/覆盖缺陷，`879d983` 于 **10 分钟后 18:22** 提交（A2 §1.1 #39–40、§3.1 #9–10；A3 §3） |

> 三条前提共同指向同一个动作顺序：**P0 修判定能力 → P1 掐断缺陷再生机制 → P2 能力与证据并进**。

**工作量口径**：1 人日 = 1 名工程师 1 个专注工作日；不含 WSL/SM64 冷启动与 6h 长跑等待。

---

## 1. P0 级 —— 0–3 天：让"能否判定"成立

### P0-1 版本四源统一 + EVO-072 补录

| 属性 | 值 |
|---|---|
| **依据** | A3 §1.1、§1.2、§2.4、§6 P0；A2 D10 |
| **风险** | 🔴 HIGH —— 发布纪律（agent.md 规则 8 三源同步 / 规则 17 版本严格递增）当前同时失效 |
| **依赖** | 无 |
| **预估** | **0.5 天** |

**现状（四处声明，实测）**

| 位置 | 当前值 | 目标值 |
|---|---|---|
| `fly64/fly64/main.py:39-40` | `BRAIN_VERSION="2.23.12"` / `SKILL_VERSION="3.5.0"` | 保持（作为源） |
| `fly64/skills/skills.md:3,70`（双徽章） | `2.23.11` / `3.4.2` | `2.23.12` / `3.5.0` |
| `fly64/skills/evolution_history.json → canonical_versions` | `brain 2.23.11 / skill 3.4.2, as_of 2026-09-18` | `2.23.12 / 3.5.0`，`as_of` 刷新 |
| `fly64/skills/evolution_skill.py:40`（`SKILL_VERSION`） | `3.4.2` | `3.5.0` |
| `fly64/tests/test_version_consistency.py:40`（`EXPECTED`） | `"2.23.11"` | `"2.23.12"`（或改为从 `main.py` 读取，避免第四次硬编码） |
| `evolution_history.json → records` | 79 条，止于 `EVO-071`；**EVO-072 不存在** | 补录 `EVO-072`（trigger/changes/tests 必填，对应 `879d983`） |

**实施步骤**
1. 先补录 `EVO-072`（引用 `879d983` 的 diff 与 `tests/test_strategy_key_contract.py` 7 条 PIN），再刷 `canonical_versions`——顺序不能反（避免 canonical 指向不存在的记录）。
2. 同步 `skills.md` 双徽章与 `evolution_skill.py:SKILL_VERSION`。
3. `test_version_consistency.py` 的 `EXPECTED` 改为从 `main.py` 导入 `BRAIN_VERSION`（消除硬编码漂移源）。
4. 跑 `--history-check`（`evolution_skill.py:2595/2640` 已存在但从未被强制）。

**验收标准**
- `python -m pytest fly64/tests/test_version_consistency.py fly64/tests/test_rule17_versions.py -q` → **0 failed**（当前 2 failed）。
- `json.load(evolution_history.json)['canonical_versions'] == {'brain':'2.23.12','skill':'3.5.0'}` 且 `records` 中存在 `EVO-072` 且其 `tests` 非空。
- `skills.md` 两处徽章与 `main.py` 一致；`evolution_skill.SKILL_VERSION == main.SKILL_VERSION`。

---

### P0-2 修两个死参数：`exploration.breakout_forward_bias` 与 `reflex.cooldown_min`

| 属性 | 值 |
|---|---|
| **依据** | A3 §4.2(a)(b)、§4.5、§6 P0；A2 U2 |
| **风险** | 🟡 MEDIUM —— 影响 EVO Phase 6 的搜索空间与"接线即生效"的可信度 |
| **依赖** | 无（与 P0-1 可并行） |
| **预估** | **0.5 天** |

**实施步骤**
1. `exploration.breakout_forward_bias`（二选一，**推荐方案 A**）：
   - **A**：把 `fly64/fly64/main.py:1333` 的 `_esc.get("breakout_forward_bias", 0.50)` 改回 `_expl.get(...)`（`ea509a9` 之前是正确的），并删除该行上方"these five live in escape/reflex sections"注释中错误的那一条前提。
   - **B**：把注册表 pid 从 `exploration.breakout_forward_bias` 改名为 `escape.breakout_forward_bias`，并迁移 `active_strategy.json` 中既有值（0.2）到 `escape` 段。
   - 若选 B，需同步 `web/evo-params.html` 展示分组与 `brain_tunable_params.json` 的 `section` 字段。
2. `reflex.cooldown_min`（二选一）：
   - **A（推荐）**：接上真实消费者——反射的 `cooldown_duration`（补读点 + 钳位 `[0.5,5]`），并补 1 条单测断言"设置值后反射冷却改变"。
   - **B**：标 `wired: false` 并在 `docs/declared-not-implemented.md` 登记为"未实现愿景"，同步更新 `test_tunable_wiring.py` 的 known-unwired 清单。
3. 更新 `test_tunable_wiring.py`：契约从"7 wired / 14 unwired"改为当前事实（并加入 **区间相交** 断言，与 P1-2 合并）。

**验收标准**
- 重跑 A3 的参数路由探针（`fly64/.tmp/_a3_param_route_probe.py`，或改为仓库内的 `scripts/` 版本）→ **39/39 可达**（当前 38/39）。
- 对两个 pid 各自"写值 → 读回值 ≠ 默认值"，并在 `flow.json` 或等价遥测中可观测。
- `python -m pytest fly64/tests/test_tunable_wiring.py -q` → **0 failed**（当前 8 failed）。

---

### P0-3 回归基线刷新：34 条 NEW 逐条归因 + 清除腐化 + 门禁转绿

| 属性 | 值 |
|---|---|
| **依据** | A3 §5.1、§5.2、§5.3、§5.5、§6 P0；A2 §4（"验证粒度"结论） |
| **风险** | 🔴 HIGH —— 门禁为红时，任何真实回归都会被 34 条噪声淹没 |
| **依赖** | **P0-1、P0-2**（否则失败集会在刷新过程中改变） |
| **预估** | **1 天** |

**实施步骤**
1. 在 P0-1/P0-2 合并后重跑全量：`cd fly64; python -m pytest tests -q --junitxml=.tmp/a4_junit.xml`（约 250 s）。
2. 按 A3 §5.3 的归因分层逐条确认 34 条 NEW：14 条由 09-21/09-22 参数接线与版本提升引起（P0-1/P0-2 后应消失）、11 条为工作树未跟踪的在途工作（`test_fix_template_interpreter.py` + `skills/fix_template_interpreter.py`，需决定提交或删除）、1 条由基线自身 3 条 `unknown` 引起、8 条待归因。
3. 重写 `fly64/tests/known_failures.win32.json`（`recorded_at` 刷新；每条必须含 `cause` + 非空 `note`）与 `known_failures.linux.json` 的复核（本机不能跑 linux，标注为"静态核对"）。
4. 清掉 3 条 `cause=unknown` 的条目（A3 §5.2 已列出具体 test id）。
5. 为"测试写生产工件"的隔离修复（见 P1-4）预留字段：基线刷新应在 P1-4 **之后**再跑一次终版，或把 P1-4 提前并入本项执行窗口。

**验收标准**
- `python scripts/check_regressions.py --strict` → **通过**（0 条 NEW、0 条"基线已通过"）。
- `known_failures.win32.json` 中 `cause == "unknown"` 的条目数 = **0**（当前 3）。
- 基线内每条都有非空 `note`；基线 `count` 与实跑失败数**相等**。
- 干净检出（`git stash` 未跟踪文件后）复跑一次，确认 NEW 数不再漂移。

---

### P0-4 触发闸门自相矛盾修复 + 合成快照断言

| 属性 | 值 |
|---|---|
| **依据** | A2 §1.2 ①（D2）、§5 U1、§6 第 1 条；A1 §5.3 顽疾 1 |
| **风险** | 🔴 HIGH —— 这是"教练在唯一被需要的时刻不被叫醒"的机制本体 |
| **依赖** | 无 |
| **预估** | **1 天** |

**现象（A2 已实测）**：用户 09-18 观测形态为「中位速度 316u/s、60s 位移仅 28u、`loop_score=0.93`」，但 `check_help_needed()` 返回 `None`；原因是两道闸门互相抵消：
- `fly64/fly64/main.py:1222-1224` 的 L2a 要求 `coverage_rate < 0.05`，而实测 `coverage_rate = 1.14`（单位：百分点/1000 ticks）。
- `fly64/fly64/memory.py:1152-1153`（`_detect_oscillating`）与 `1184-1185`（`_detect_micro_loop` Tier-2）的 `disp_60s > 300 → return False`，把"高速振荡"误判为"有进展"。
- 结果 `anomaly_state` 为 `idle`，而 `micro_loop_weave` pattern 要求 `anomaly_state == "micro_loop"` ⇒ 5 轮 findings 全空。

**实施步骤**
1. 三个判据**同一口径**重写：引入"位移效率"（`displacement_per_speed = disp_60s / (median_speed × 60)`）替代单一位移/覆盖率闸门；位移效率低于阈值即视为无效前进（正对用户 09-17 在 `90dd512b` seq=17557 的自证矛盾：`stuck=54s` 且上升、`loop_score=0.99`、`health=0.62`，但 5 轮 findings 全空）。
2. 用户已在 09-17 给出正确修法建议（把 pattern 条件放宽为 `loop_score ≥ 0.95 AND escape AND stuck ≥ 45`）——**该建议至今未落地**，本次一并落地。
3. 增加**合成快照回归测试**（新增 `tests/test_trigger_conflict.py`）：
   - 注入 `memory={stuck_duration:54.2, anomaly_state:'idle', health_score:0.62, reflex_active:True, reflex_ineffective:False, disp_60s:2100.0}` ⇒ 断言 `check_help_needed()` **非 None**（当前为 `None`）。
   - 注入 `loop_score=0.99, disp_60s=2100, anomaly=idle` ⇒ 断言突围逻辑**可进入**。
4. 同步检查 `fly64/fly64/main.py:1572-1600` 的 burst 前置条件 `anomaly_state_name == "oscillating"`，改为不依赖被同一闸门污染的字段（与 P1-6 协作，但**前置条件解绑在本项完成**）。

**验收标准**
- 新增测试文件在修复前**必须失败**（提供 red→green 证据）。
- 合成快照形态（316u/s + 28u/60s）下：`check_help_needed()` 返回非 None，**且** burst 分支可达（两条断言）。
- 回归：`coverage_rate` 单位与阈值在 `memory.py` 与 `main.py` 中的语义**文档化一致**（同一注释块说明单位）。

---

### P0-5 Coach 链路级端到端断言（发布门禁）

| 属性 | 值 |
|---|---|
| **依据** | A2 §1.4、§4、§5 U1/U4、§6 第 1 条；A3 S1/S5；A1 §10 |
| **风险** | 🔴 HIGH —— 这是把"73 条追问、10 天"压缩成"一条测试"的关键 |
| **依赖** | **P0-2**（死参数会污染断言）、**P0-4**（触发是链路第一段） |
| **预估** | **1 天** |

**断言（一条，端到端）**

```
写入 coach_advice.json（含 exploration.turn_bias + escape.commit_ticks）
  → 600 tick（≈12s，热加载周期）内 telemetry.coach_applied 的对应键必须改变
  → 30s 后 coach_outcomes.jsonl 必须新增一条：keys 非空 且 scene_label 非空 且 deltas 非全 0
```

**实施步骤**
1. 把断言实现为 `tests/test_coach_end_to_end.py`，并允许"无 SM64 环境"降级为注入式（写文件 + 直接调热加载函数 + 断言读取端值），**但必须覆盖 ④写盘 → ⑤键名 → ⑥行为** 三段（A2 D7/D8/D9 缺口）。
2. 断言读取端时**必须跨段感知**：同时检查 `exploration` 与 `escape` 段，防止 P1-1 的死键形态通过测试。
3. 把该测试加入发布门禁（与 P0-3 的 `check_regressions.py`/CI 一并启用）。
4. 记录失败时的诊断输出：`applied` / `rejected` 列表（`main.py:781-828` 已上报 `applied/rejected`，应被断言消费而不是被忽略）。

**验收标准**
- `tests/test_coach_end_to_end.py` 在**当前代码**上失败（证明它真的在检测 D7/D8/D9 的残留），在修好后的代码上通过。
- 门禁运行输出中可见该测试名；`applied` 与 `active_strategy.json` 最终值一致；`coach_outcomes.jsonl` 新行 `scene_label` 非空。
- `runtime/coach_frames` 在同一次运行中新增 ≥1 文件（与 P2-2 联动，若 P2-2 未完成则可先跳过该子断言）。

---

## 2. P1 级 —— 3–10 天：掐断缺陷的"再生机制"

### P1-1 跨段点号死键根治（写端修正 + 跨段迁移 + 显式上报）

| 属性 | 值 |
|---|---|
| **依据** | A2 D8/U2；A3 §4.3(c)、§6 P1 |
| **依赖** | P0-2 |
| **预估** | **1 天** |

**现状**：`fly64/skills/active_strategy.json` 的 `exploration` 段内仍有 5 个 `escape.*` 死键（A4 实测：`escape.forward_accum_step=0.015757` 等，`__generation=161`），而 `escape` 段的清白键是默认值 `0.005`。EVO-072 的归一化实现是 `prefix = sec + "."`，**只清"同段前缀"**，跨段键永不迁移、永不删除 ⇒ 该缺陷家族第 8 例。

**实施步骤**
1. **写端修正**（根因）：`fly64/skills/evolution_skill.py` 的 `_inject` / `param_paths` 按 pid 的**注册段**决定写入段（而不是按当前 section），杜绝跨段键生成。
2. **读端升级**：`main.py:1280-1290` 与 `evolution_skill.py:2026` 的归一化改为"跨段前缀感知"——**识别**键名前缀所属段，迁移到正确段，或**显式上报**到 `rejected`（不静默保留）。
3. **一次性迁移**：清理磁盘上存量 5 个死键（保留数值较大的那个？——**以注册段值为准**，跨段死键值仅记录到日志再删除）。
4. 补测试：连续跑 3 轮 Phase 6（或模拟 `_inject`），断言文件内**不出现任何含 `.` 的键**。

**验收标准**
- `json.load(active_strategy.json)` 中**任何 section 内都不存在含 `.` 的键**（当前 exploration 段有 5 个）。
- 连跑 3 次 EVO Phase 6 后该断言仍成立（**不再再生**）。
- `escape.commit_reinforce/commit_suppress/forward_accum_step` 的实际读值 = `escape` 段的显式值（而非默认值）。

---

### P1-2 注册区间 vs 运行期钳位对齐

| 属性 | 值 |
|---|---|
| **依据** | A3 §4.4、§6 P1 |
| **依赖** | P0-2（同一注册表文件） |
| **预估** | **0.5 天** |

**两处不相交（实测）**
- `exploration.bold_explore_stuck_s`：注册 `[15,180]`（default 60）vs `main.py:1298` 钳位 `[1,10]` —— **完全不相交**，EVO 任何合法采样都被钳到 10；注册表描述却在推荐"5~10"。
- `exploration.turn_bias`：注册 `[0,0.4]` vs `main.py:1296` 钳位 `[0,0.25]`；注释写 `[0, 0.4]` 而代码是 0.25。

**实施步骤**：先决定"哪个是对的行为"，再让三处一致（注册表 / 注释 / 钳位代码）；把两个区间写入 `test_tunable_wiring.py` 的断言（注册区间必须与运行期钳位**相交**，且 default 落在两者交集中）。

**验收标准**：探针报告两处均"相交"；`test_tunable_wiring.py` 含区间断言并通过；`main.py` 注释与代码数值一致。

---

### P1-3 教练可调旋钮与注册表统一 + 扩旋钮面

| 属性 | 值 |
|---|---|
| **依据** | A2 D4/U8；A3 S9/§1.4、§6 P2 |
| **依赖** | P1-2 |
| **预估** | **1.5 天** |

**现状**：`plugin/llm_consult.py::SECTION_SPECS`（第 110-149 行）是**手工维护的 4 个键**（`fallen_recovery.mode`、`exploration.bold_explore_stuck_s`、`exploration.turn_bias`、`escape.stuck_threshold_s`），从不读注册表；行为侧却有 39 个参数、9 个运动池；且 `escape.stuck_threshold_s` **不在注册表内**。⇒ 教练"能看见的问题（截图里的振荡）"与"能表达的处置手段（4 个旋钮）"严重不对等——这正是用户"会影响到实际动作吗"的答案。

**实施步骤**
1. `SECTION_SPECS` 改为**从 `brain_tunable_params.json` 生成**（按 `coach` 分区 + 显式白名单），消除第二事实源。
2. 把教练**动作维度**补齐：至少为"跳跃 / 轻转向 / 后退 / 停止"各暴露 1 个可控量（对应 A2 §3.1 #10 用户逐项清单）。
3. 处理注册表外键 `escape.stuck_threshold_s`：纳入注册表，或从教练可见集中移除并说明原因。
4. 更新 `PROMPT_TEMPLATE`（`llm_consult.py:88-99`）使"可表达的键"与"prompt 里承诺的键"一致。

**验收标准**
- 断言 `set(SECTION_SPECS 键) ⊆ set(注册表 pid)` 且两者差集为**显式白名单**（非空差集需在代码注释中列出理由）。
- 教练可表达键数从 4 → **≥8**，且覆盖"动作类别"维度。
- 单元测试：注册表新增参数时，若有 `coach` 分区标记，`SECTION_SPECS` **自动**包含（防回归）。

---

### P1-4 测试隔离：测试不得写生产工件

| 属性 | 值 |
|---|---|
| **依据** | A3 S8/§5.4；A3 §6 P1 |
| **依赖** | 无（建议与 P0-3 同一窗口） |
| **预估** | **0.5 天** |

**实施步骤**
1. `tests/test_t3_handshake.py`：模块级可执行代码包进 `if __name__ == "__main__":`（或改为 `pytest.skip` + 显式 `@pytest.mark.manual`）。
2. `fly64/tests/conftest.py`：除 `FLY64_EVIDENCE_DIR` 外，重定向 `plugin/.consult_request.json`、`plugin/.consult_response.json`、`skills/active_strategy.json`（及 `coach_outcomes.jsonl` / `.pending_outcome.json` 的确认）。
3. 定位 `active_strategy.json` 在测试期间被改写的写点（A3 §7.3 未归因项）；**若确认是驻留循环进程**，则在测试里加"检测到生产进程在跑就显式跳过"的守卫，而不是放任。
4. 清理被测试污染的 git 跟踪文件（`plugin/.consult_*.json`）并加入 `.gitignore` 或改为不跟踪。

**验收标准**
- 全量 `pytest tests` 前后，`git status --porcelain` 对**被跟踪文件**零变更。
- `runtime/coach_frames/` 计数不因测试变化；`active_strategy.json` 的 `__generation` 在测试期间**不变**（需先排除驻留进程，或断言其存在并跳过）。
- 测试后文件哈希（`plugin/.consult_*.json`、`skills/active_strategy.json`）前后一致。

---

### P1-5 归因闭环填真数据（scene_label / keys / deltas / 本能晋级）

| 属性 | 值 |
|---|---|
| **依据** | A2 D12/U4、§4 表"仍未闭环的原因"；A3 §3.1 |
| **依赖** | P0-5（端到端断言） |
| **预估** | **1.5 天** |

**现状（实测）**：`coach_outcomes.jsonl` 30 行中 **21 行是 test 桩**（生产仅 9 条）、**`scene_label` 30/30 为空**、末行 `keys={}` 且 `deltas` 全 0；`scene_strategy_bindings.json` 仅 2 bucket、`promoted: false`（门槛 `PROMOTE_MIN_IMPROVED=2`）；`curriculum.json` 回落 `stage=1`（EVO-070 记录过"首个本能晋级 + stage 1→5"，当前是回落）。⇒ 用户 09-18 问"coach建议行为是否有奖惩机制反馈，和生效"，实测答案是**否**。

**实施步骤**
1. `scene_label` 填充：`instinct_bindings.py:128-130` 的 `scene_key()` 对空标签 `return ""`——改为在 outcome 写入时**强制**带上场景指纹（缺场景不得写空串，应写 `unknown:<原因>` 或拒绝写入并告警）。
2. `keys` / `deltas` 填充：把"哪条建议、带来什么变化"两个字段接到 `telemetry.coach_applied` 与 30s 后的行为差分（与 P0-5 共用数据源）。
3. 本能晋级：复核 `PROMOTE_MIN_IMPROVED` 与 scene bucket 维度是否过窄（现仅 2 bucket、1/1 improved），把"教练每次咨询都重调参数导致指纹不一致"这一 EVO-058 的四重死因之一再确认（A3 §2.3 EVO-058 记录）。
4. 课程状态：查清 `curriculum.json` 回落到 `stage=1` 的原因（`reset_at 2026-09-17T20:43`），修复状态被覆盖的路径。

**验收标准**
- 生产语料（非 test 桩）`coach_outcomes.jsonl` ≥ **30 行**，且 `scene_label` 非空率 **100%**（当前 0%）。
- 至少 1 条记录的 `keys` 非空、`deltas` 非全 0。
- `scene_strategy_bindings.json` 出现 **≥1 次 `promoted: true`**（当前 0）。
- `curriculum.json` 的 `stage` 在一次完整运行后**不回退**到 1（或回退有显式原因字段）。

---

### P1-6 探索闭环：burst 途中重算航向 + 解除单动作固化 + `loop_score` 语义统一

| 属性 | 值 |
|---|---|
| **依据** | A2 §3.2/§3.3（D13/D14/D15）、§5 U5/U6/U11；A1 §5.3 顽疾 2 |
| **依赖** | P0-4（burst 前置条件） |
| **预估** | **2 天** |

**实施步骤**
1. **burst 闭环化**（`main.py:1572-1600`）：`_burst_heading` 由"每次 burst 只算一次"改为**每 N tick（建议 25）重算** `frontier_direction()`，并加入"是否真在靠近前沿"的校验（位移投影 > 0），否则提前退出 burst。
2. **解除单动作固化**：burst 期间不再固定 `control.y=127` + `jump=False`；改为"默认全速前进，但允许 action pool 在每 50 tick 抢占 1 次"（或按 `action_entropy` 注入动作类别采样）。目标：稳态下"单动作开环冲刺"tick 占比从 **≤40%** 降到 **≤15%**。
3. **`loop_score` 语义统一**：`memory.py:413-421` 的 `_revisit_count` 30 tick 衰减改为"位移只在**有效增益**（位移效率达标）时才衰减"，使"高速绕圈"能维持 `loop_score > 0.9`；同步复核三个消费者（burst 触发 / `action_entropy` 触发 / EVO pattern）。
4. **`cx_novelty_dir` 方向梯度**：`5c86272` 声称的 "cx_novelty recovery path" 目前**没有任何代码给出方向偏好**（A2 §3.4 未修 7）；本项需真正产出方向梯度（或明确登记为"未实现"，不得留在提交信息里）。

**验收标准**
- 合成形态（316u/s + 28u/60s）下：burst 可进入，且在 200 tick 内**至少切换 2 类动作原语**（当前恒为"单航向 + y=127"）。
- 高速绕圈 60s 后 `loop_score > 0.9`（当前被衰减抹平）。
- `cx_novelty_dir` 在存在未访问前沿时**非 0**；若做不到，则在 `docs/declared-not-implemented.md` 显式登记并从 `5c86272` 的表述中撤回。
- "单动作 tick 占比"指标进入 `flow.json` 遥测（可被仪表板观测）。

---

### P1-7 AgentTeams：惰性 spawn（或兜底 + 约束文档化）

| 属性 | 值 |
|---|---|
| **依据** | A2 §2.2/§2.3/§2.4、§5 U3；a0 §2（真实抱怨 7 条） |
| **依赖** | 第三方插件边界评估（路径在工作区外） |
| **预估** | **1 天**（若不可改则转为评估 + 兜底，0.5 天） |

**根因**：`@nanmicoder/dsh-agent-teams@0.1.20` 的 `scheduler.js:243-245,331-333` 直接调 `deliverToMember(member.id)`，缺少 `tools.js:318-323` 的惰性 spawn 分支；`isMemberAvailable` 把 `live===undefined` 判为可用（`scheduler.js:106-111`）；失败被 catch 成 `false` 并回滚 `pending`（`scheduler.js:355-368`）⇒ 永不 spawn。

**实施步骤**
1. 评估能否在插件侧补"调度器复用 `dispatchToMember`"的最小改动（若有本地可写副本）。
2. 若不可改：在团队使用约束中固化"**建团队后必须先用 `reassign_task` 或 `send_message` 触发一次真实投递，再依赖调度器自动推进**"，并把该约束写入 `agent.md`（team 使用章节）。
3. 兜底：让 `view_team`/`status` 的输出在"成员全 `idle/unspawned`"时给出**显式告警**（`recordSpawnError` 已有机制，需在队长可见面上暴露）。

**验收标准**
- 端到端断言（人工或脚本）：团队 `approve` 后，**不调用** `add_member`/`send_message`，仅 kick 一次 ⇒ **产生 ≥1 个 child session**（当前为 0）。
- 若判定不可修：`agent.md` 中存在该约束条目，且 `view_team` 输出中能看到"unspawned"告警字段（可被队长察觉）。

---

## 3. P2 级 —— 1–4 周：能力与证据并进

### P2-1 09-21/09-22 高风险改动的实机复验

| 属性 | 值 |
|---|---|
| **依据** | A3 §3.1/§6 P2；A2 §3.4 |
| **依赖** | P0-3（门禁转绿后再做实机，避免噪声） |
| **预估** | **2 天**（含冷启动与长跑等待） |

**待复验清单（当前零实机证据）**：`5c86272`（200t burst，改行为回路）、`61e1e0d`（P0 参数自愈 + frontier 半径 20→50）、`d719a60`（param history 持久化）、`5703efa`（遥测字段）。

**验收标准**：每次实机运行产出**新时间戳**的 `artifacts/latest-*.npz`、`artifacts/param_history.jsonl`（当前**不存在**）、`skills/evolution_log.jsonl`（当前停 09-17）；每项改动附一段"行为可观测差异"结论写入 `docs/`；`5c86272` 需给出 200t burst 在真实卡死形态下的触发次数与脱困率。

---

### P2-2 帧延迟遥测 + `coach_frames` 留痕

| 属性 | 值 |
|---|---|
| **依据** | A2 D6/U9 |
| **依赖** | P0-5 |
| **预估** | **1 天** |

**现状**：帧是 **3–15s 前**的画面（`main.py:1903, 2604-2607` 每 60 tick 刷新）；`runner.save_consult_frame()` 只存"教练将看到的那帧"⇒ **主动消灭了唯一能审计延时的证据**；`runtime/coach_frames` **0 文件**（A4 实测）。

**验收标准**：`save_consult_frame` 同时存"原始帧 + 采集时间戳 + 咨询时间戳"；每次咨询 `runtime/coach_frames` ≥1 文件；报告 `Δt = 咨询时刻 − 帧时刻`，目标 **≤1s**；若无法达标，则在仪表板显式标注"教练所见画面滞后 Δt 秒"。

---

### P2-3 动作集合级探索（policy entropy）替代逐 tick 高斯噪声

| 属性 | 值 |
|---|---|
| **依据** | A2 D15/U11、§3.1 #10 |
| **依赖** | P1-6 |
| **预估** | **2 天** |

**验收标准**：`action_entropy_*` 进入参数注册表（可被面板/EVO 调）；`jump_rate` 与"轻转向中间值"出现**非饱和分布**（当前 `gate_jump=False`、`reflex 只输出 ±70`）；用户 09-22 的"动作被抑制逐项清单"中至少 2 项变为"可用"。

---

### P2-4 契约审计 + 归因仪器 → CI 常驻

| 属性 | 值 |
|---|---|
| **依据** | A2 §4、§6 第 2/3 条；A3 §4 |
| **依赖** | P0-3、P1-1 |
| **预估** | **2 天** |

**验收标准**：`scripts/audit_contract_pairs.py`（EVO-066 已存在）进入 CI，任何"只写不读"键 = 0 或显式登记；`fitness_components/same_sample/missing_inputs`（EVO-071 仪器）进 `flow.json` 每 100 tick 一行；"41% 零 delta"类问题可在仪表板上自证。

---

### P2-5 环境契约自动校验（SM64/显示/8765 心跳）

| 属性 | 值 |
|---|---|
| **依据** | a0 §2（第一大话题 393）；A1 E2（238 条）/§5.1（启动-重启 17 次）；A3 §3（`d04264e`/`e0edc29` 已实测） |
| **依赖** | 无 |
| **预估** | **1.5 天** |

**验收标准**：冷启动后 60s 内自动判定"脑模型 / SM64 / 桥 / 8765 服务"四态，失败时给出**可执行的修复建议**；该自检接入启动脚本（`fly64/scripts/launch_full.sh` 或 Windows 侧等价物），并在每次启动写一条记录（可与 P2-1 的工件时间戳互相印证）。

---

### P2-6 跨领域 / 商业化（K2）

| 属性 | 值 |
|---|---|
| **依据** | A1 §2.1（K2 仅 **9 条**，3 天活跃）；`1f8fbe04:1/13` 原始诉求；`docs/analysis/insurance/fly64-brain-module-to-insurance-mapping.md` |
| **依赖** | P0/P1 全绿（**明确排后**：验证缺口未闭合时扩域会放大成本） |
| **预估** | **1 周+** |

**验收标准**：交付"果蝇脑模块 → 保险核保"映射的可执行任务书（含接口边界、数据契约、可验证的 PoC 指标），而非仅方案文档。

---

## 4. 依赖关系图

```mermaid
graph TD
  subgraph P0[P0 · 0–3 天 · 让"能否判定"成立]
    A1[P0-1 版本四源 + EVO-072 补录]
    A2[P0-2 两个死参数]
    A3[P0-3 回归基线刷新 · 门禁转绿]
    A4[P0-4 触发闸门自相矛盾]
    A5[P0-5 Coach 链路级端到端断言]
    A1 --> A3
    A2 --> A3
    A2 --> A5
    A4 --> A5
  end
  subgraph P1[P1 · 3–10 天 · 掐断再生机制]
    B1[P1-1 跨段点号死键根治]
    B2[P1-2 区间对齐]
    B3[P1-3 教练旋钮统一/扩面]
    B4[P1-4 测试隔离]
    B5[P1-5 归因闭环填真数据]
    B6[P1-6 探索闭环]
    B7[P1-7 AgentTeams 惰性 spawn]
    A2 --> B1
    B2 --> B3
    A5 --> B5
    A4 --> B6
    A3 --> B4
  end
  subgraph P2[P2 · 1–4 周 · 能力与证据并进]
    C1[P2-1 高风险改动实机复验]
    C2[P2-2 帧延迟遥测 + 留痕]
    C3[P2-3 动作集合级探索]
    C4[P2-4 契约审计与归因仪表 → CI]
    C5[P2-5 环境契约自动校验]
    C6[P2-6 跨领域/商业化]
    A3 --> C1
    A5 --> C2
    B6 --> C3
    B1 --> C4
    A3 --> C4
    C1 --> C6
  end
```

---

## 5. 执行顺序与里程碑

| 批次 | 内容 | 完成判据（里程碑） | 累计工作量 |
|---|---|---|---|
| **第 1 批（第 1 天）** | P0-1 + P0-2（可并行） | 版本四源一致、EVO-072 入史、两个死参数复活、探针 **39/39** | 0.5–1 天 |
| **第 2 批（第 2–3 天）** | P0-3 + P0-4 + P0-5 + P1-4 | **门禁转绿**（`check_regressions --strict` 通过）、三条链路级断言存在且能 red→green、测试不再写生产工件 | 3.5 天 |
| **第 3 批（第 4–7 天）** | P1-1 + P1-2 + P1-5 | 死键 **0 再生**、区间相交、归因语料 `scene_label` 100% 非空 + 首次本能晋级 | 6.5 天 |
| **第 4 批（第 8–10 天）** | P1-3 + P1-6（+P1-7 并行评估） | 教练旋钮 ≥8 且与注册表同源；burst 闭环 + 单动作占比 ≤15% + `loop_score` 语义统一 | 10 天 |
| **第 5 批（第 11 天起）** | P2-1 → P2-5 → P2-2/3/4 → P2-6 | 实机工件全部刷新到当周；帧延迟 ≤1s；动作非饱和分布；审计进 CI；环境自检在线 | +9 天起 |

> **硬性顺序约束（不可调换）**：`P0-1/P0-2 → P0-3`（先修再刷基线）、`P0-4 → P0-5/P1-6`（先让触发成立再断言链路）、`P0-2 → P1-1`（先修接线再根治死键）、`P0-5 → P1-5`（先有端到端数据再填归因）、`P0/P1 全绿 → P2-6`（扩域最后）。

---

## 6. 风险与回滚

| 风险 | 触发条件 | 缓解 / 回滚 |
|---|---|---|
| 改触发闸门后**过度求助**（教练被频繁叫醒） | P0-4 放宽位移效率阈值后 consult 频率激增 | 阈值先"影子模式"运行（只记录不触发）24h，对比旧判据命中集后再启用；保留 `coach.consult_min_interval` 硬下限 |
| 改 `loop_score` 衰减后**探索收益下降** | P1-6 让 `loop_score` 长期高位 ⇒ burst 频繁 | 加入 burst 冷却 + 单位时间 burst 上限；用 `flow.json` 的"单动作占比"与覆盖率双指标共同判定 |
| 参数接线改动**打破既有 EVO 搜索** | P0-2/P1-1/P1-2 改了注册段/区间 | 保留 `active_strategy.json` 迁移前快照（`/tmp/strategy_before.json`）；Phase 6 用 `warm-start` 从上代精英继续 |
| 基线刷新把**真实回归**误归类为环境噪声 | P0-3 归因阶段为了"转绿"而放宽 | 每条 `unknown` 必须填 `note` 与责任人；`real-bug` 类保留在原处，只允许 3 条 `environment` 类标注平台 |
| AgentTeams 插件在工作区外**无法修改** | P1-7 评估结果 | 退回"约束文档化 + 兜底告警"，并把"队长亲自执行 DAG"作为已知可行路径写入 `agent.md` |
| 实机不可用（WSL/SM64 环境起不来） | P2-1 需要长跑 | 先用 P2-5 的环境自检定位；不可用时降级为"注入式端到端断言"（P0-5 已提供该能力），但**必须在报告中标注为注入级证据** |

---

## 7. 与 v3 计划（`session_logs_execution_plan_v3.md`）的差异

| 项 | v3 计划 | v4 计划 | 差异原因 |
|---|---|---|---|
| 口径基础 | 11 session / **959** 提问 | 11 session / **874** 提问 | a0 §1 裁定；A4 §1.3 精确分解 |
| P0 起点 | "先验证刚修好的（Coach 六段 / EVO-072）" | **先让"能否判定"成立**（门禁转绿 + 版本统一 + 死参数 + 端到端断言） | 门禁当前为红（62 failed / 34 NEW），此时"验证"的结论无法被采信（A3 S5） |
| P0 是否含版本治理 | 未列 | **列为 P0-1**（阻塞 P0-3） | A3 §1.1/§2.4：四处版本失配 + EVO-072 未入史，且守卫测试本身就是红的 |
| P0 是否含触发闸门 | 未列（只在六段链路图上标"⚠曾 400"） | **列为 P0-4**（含合成快照断言） | A2 D2/U1：闸门自相矛盾是"教练在唯一被需要的时刻不被叫醒"的机制本体 |
| 死参数 | "5 个参数是死参数（`ea509a9`）" | **2 个仍未修**（`breakout_forward_bias` 被该次修复自己改死；`reflex.cooldown_min` 零消费者） | A3 §4.2/§4.5 逐项实测（38/39） |
| 第一大话题 | 未讨论（沿用 v3 报告） | **运行环境/桥接/SM64（393 命中）**，并列为 P2-5 环境契约自检 | a0 §2 裁定 |
| 探索类工作 | P1/P2 中零散提及 | 集中为 **P0-4 + P1-6 + P2-3** 三阶梯（触发 → 闭环 → 动作集合级） | A2 D2/D13/D14/D15 的根因链 |
| 团队协作类 | 未列 | **P1-7**（惰性 spawn 或约束文档化），并明确"不是最大顽疾（真实抱怨 7 条）" | A2 §2；a0 §2 |
| 证据级要求 | "每段有日志或端点证据" | **每条 P 项一条可执行验收命令/断言**，且要求 red→green 证据 | A2 §6 第 1 条：链路级断言作为发布门禁 |
| 跨领域/商业化 | 未列 | **P2-6**（明确排最后） | A1 §2.1：K2 仅 9 条，验证缺口未闭合时扩域会放大成本 |

---

## 8. 全量验收（Definition of Done）汇总

| # | 项 | 验收命令 / 断言 | 当前基线 | 目标 |
|---|---|---|---|---|
| P0-1 | 版本四源 + EVO-072 | `pytest tests/test_version_consistency.py tests/test_rule17_versions.py -q` | **2 failed / 13 passed** | 0 failed |
| P0-1 | 档案 | `json.load(evolution_history.json)` | 79 条、无 EVO-072、canonical 2.23.11/3.4.2 | 含 EVO-072、canonical 2.23.12/3.5.0 |
| P0-2 | 参数接线探针 | `python .tmp/_a3_param_route_probe.py`（或仓库化版本） | **38/39** | 39/39 |
| P0-2 | 接线契约测试 | `pytest tests/test_tunable_wiring.py -q` | **8 failed** | 0 failed |
| P0-3 | 回归门禁 | `python scripts/check_regressions.py --strict` | 34 NEW / 10 腐化 | 通过（0/0） |
| P0-3 | 基线未分类 | `known_failures.win32.json` 中 `cause=unknown` | **3** | 0 |
| P0-4 | 触发断言 | 合成快照 ⇒ `check_help_needed()` | **None** | 非 None |
| P0-5 | 链路断言 | `coach_advice.json` → `coach_applied` → `coach_outcomes` | 无此断言 | red→green 通过 |
| P1-1 | 死键 | `active_strategy.json` 内含 `.` 的键 | **5 个**（`__generation=161`） | 0 且 3 轮 Phase 6 不再生 |
| P1-2 | 区间 | `bold_explore_stuck_s` / `turn_bias` 注册 vs 钳位 | **不相交 / 0.4 vs 0.25** | 相交且注释=代码 |
| P1-3 | 教练旋钮 | `SECTION_SPECS` 键集 vs 注册表 | **4 键、手工、注册表外键 1 个** | ≥8 键、与注册表同源 |
| P1-4 | 测试隔离 | 全量 pytest 后 `git status --porcelain` | 有被跟踪文件变更 | 零变更 |
| P1-5 | 归因语料 | `coach_outcomes.jsonl` 统计 | 30 行 / 21 test 桩 / scene_label 0% | ≥30 生产行 / scene_label 100% / ≥1 晋级 |
| P1-6 | 探索闭环 | 合成形态下 burst 动作切换数、`loop_score`、单动作占比 | 单航向 + y=127；loop 被衰减；≤40% 单动作 | ≥2 类动作；loop>0.9；≤15% |
| P1-7 | AgentTeams | approve 后仅 kick 一次 ⇒ child session 数 | **0**（或降级为文档+告警） | ≥1 或显式登记约束 |
| P2-1 | 实机工件 | `artifacts/latest-*.npz` / `param_history.jsonl` / `evolution_log.jsonl` mtime | **09-19 12:13 / 不存在 / 09-17** | 当周新时间戳 |
| P2-2 | 帧延迟 | `runtime/coach_frames` 文件数；Δt | **0 文件**；Δ 3–15s | ≥1/次；≤1s |
| P2-3 | 动作分布 | `jump_rate` / 转向中间值分布 | 饱和（gate_jump=False；±70） | 非饱和、≥2 项解禁 |
| P2-4 | 契约审计 | `audit_contract_pairs.py` 进 CI；归因进 `flow.json` | 手动脚本 | CI 常驻 + 每 100 tick |
| P2-5 | 环境自检 | 冷启动 60s 内四态判定 | 无 | 有且给出修复建议 |
| P2-6 | 跨领域 | 保险映射可执行任务书 | 仅方案文档（K2：9 条提问） | PoC 指标可验证 |

---

## 9. 文档一致性任务（本方案附带，来自 A4 §2.5）

| 项 | 现状 | 目标 |
|---|---|---|
| 协议噪声条数表述 | a0 rev 1 §1.2 表末行 **97**、captain 邮件初稿 **96**；**a0 rev 2 已修为 963 / 874 / 89**（captain 裁定 1，2026-09-22） | 统一为 **"协议噪声 89 条；v3 的 959 与权威 874 的净差额 85 条 = 89 噪声 − 4 条 S7 少算"**（captain 裁定 2 采纳 A4 表述；裁定 3 确认 874 成立、870 废弃） |
| 各产物口径数字 | A2 rev 2 首稿用 951/959（曾报 870，已废弃），A1 用 874，a0 rev 2 / v4 用 874 | 全部改为 **874**；**870 废弃**（legacy S7 导出不完整，见 a0 §1.3/§6.1）；残留的 951 表述仅作方法学注记 |
| 引用原话 | v3 写"大部分动作**没**尝试" | 一律用原始措辞 **「大部分动作没有尝试」** |
| coach 消息数 | 73（A2）/ 75（A1 语料） | 统一写法"**73 条（A2 结构化关键词；A1 语料关键词为 75）**" |

**验收标准**：A0/A1/A2/A3/A4 五份产物中，出现"874 / 11 session"以外的总数表述时，**必须**带口径标注；`grep -c "959"` 在 v4 两份文档中仅出现在"对 v3 的修正清单"与"差异说明"语境中。

---

> **生成**：report-synthesizer（A4）· 2026-09-22
> **配套报告**：`docs/analysis/session_logs_analysis_v4.md`
> **上游产物**：`analysis-a0-captain-verification.md`（rev 2）· `analysis-a1-themes.md` · `analysis-a2-rootcauses.md`（rev 3）· `analysis-a3-state.md`
