# W1–W4 结案验证与 H13 最终裁定

> **本文件取代 `.tmp/closeout/closeout-report.md`**（后者位于临时目录，且其 W4 节使用了合成数据，
> 与真实运行数据相差约 6 倍 —— 见 §4）。
>
> - **来源团队**: `fly64-closeout-w1-w4`（t1 实施 W1–W3、t2 验证 + W4 复测），均已 pass 并归档
> - **日期**: 2026-09-25
> - **真实数据快照**: `artifacts/fitness_aa_report.json`（n=302）+ `fly64/skills/evolution_log.jsonl`
>   （3358 条真实 `aa_gate` 行）

---

## 1. W1 — 逐窗 A/A 观测值落盘（零新插桩）

| 检查项 | 结果 | 证据 |
|--------|------|------|
| `_last_aa_window_obs` 定义 / 每周期重置 | ✅ | `evolution_skill.py:4198` / `:4341` |
| `observe_aa_window` 调用与赋值 | ✅ | `:4343-4346` |
| 写入 `evolution_log.jsonl` 的 `aa_window` | ✅ | `:5076` |
| 含 raw 字段（`net_disp_60s` 等） | ✅ | `:3840-3854`；`baseline_components.raw` 见 `:3226-3273` |
| 零新插桩 / 无新增 `control.*` 写入 | ✅ | 复用既有 EvolutionPipeline 路径 |

**证据边界（重要）**：W1 是**在本次常驻运行之后**实施的，因此那次运行（n=302）的逐窗 raw 数据
**未被记录**，仅有聚合统计（`delta_stats`）。逐窗 raw 回放需**下一次在线运行**才能进行。

---

## 2. W2 — bootstrap 置信上界 + 口径 + k + R6

| 检查项 | 结果 | 证据 |
|--------|------|------|
| `_bootstrap_upper95` 返回 95% 置信上界（而非 P95 的均值） | ✅ | `:2306-2331`；独立重算 2000 次重抽样：`mean_of_means=0.1626`、`P95_of_means=0.1819`，函数返回 `0.181816`（差 <0.001） |
| 使用 `P95|δ|`（先取绝对值再重抽样） | ✅ | `abs_samples = [abs(v) for v in samples]` |
| `n<20` 保守回退 1.0 | ✅ | `:2321-2322` |
| `gate_status().p95` 走 `P95|δ|` | ✅ | `:2587-2643` |
| `commit_threshold = max(0.03, k·p95)`，`k ≥ 2` | ✅ | `k=2.0`；实测 `max(0.03, 2.0×0.210766)=0.421532` |
| `h13_assessment` 改用 R6 条件 | ✅ | `:2988-3049`；不足数据返回 `INSUFFICIENT_DATA` |
| `h13_assessment` 含 `pool_floor(1/√n)` 双重条件 | ❌ **未实现** | 见 §5 F1 |

**这一节修复了一个真实 bug**：原 `_bootstrap_upper95()` 返回 bootstrap P95 的**均值**
（实测 0.183226），而非 95% 置信上界（同数据 0.2611），导致判据被低估约 30%。

---

## 3. W3 — `missing_inputs` 硬门（仅试验/commit 路径）

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 非空 ⇒ trial 作废（`voided=True, delta=0.0`） | ✅ | `:4025-4056` |
| 不参与 delta 比较 | ✅ | `delta: 0.0` |
| 不耗预算 / 回滚 | ✅ | `committed: False` + `_restore_pre_inject_snapshot()` |
| A/A 标定路径不受影响（保持宽容） | ✅ | `observe_aa_window()` 记录但不 void |

这解决了 t2 规格审计的 **F2（中）**：此前 `missing_inputs` 非空时 `valid=True`，
且 `evaluate()`/`commit` 从不读取它，与 M4-d2 §4「非空 ⇒ 作废」直接冲突。

---

## 4. W4 — H13 裁定（**本节为对原报告的实质更正**）

### 4.1 真实运行数据（n=302）

来源：`artifacts/fitness_aa_report.json`（该产物由**修复前**代码写出，故 `commit_threshold`
仍显示 `k=1.5`；但 `noise_p95` 与 `delta_stats` 是真实运行测量）。

| 判据 | 真实值 | 门限 | 判定 |
|------|--------|------|------|
| `aa_window_count` | **302** | ≥100 | ✅ |
| `n_windows_span_aligned` | **302** | — | ✅ |
| `n_windows_kinematics_ok` | **301 / 302** | ≥100 | ✅ 非盲窗 |
| `span_stats` | min 60.03 / max 69.98 / mean **63.14** | — | ✅ 等长 |
| `aa_two_window_fpr.value` | **0.0**（301 对，`measured=true`） | ≤1% | ✅ **通过** |
| `noise_p95` | **0.177675** | ≤0.03 | ❌ **超 5.9×** |
| `delta_stats` | count 302, mean 0.006132, **std 0.090344**, p95 0.1754, p99 0.2742, min −0.2894, max 0.3185 | — | — |
| `g4_pass` | **false** | — | ❌ |
| `blockers` | `bootstrap_upper95(P95)=0.1789 > 0.03` | — | — |
| `data_source` | `runtime_aa_windows`（runtime_sourced 302 / unattributed **0**） | — | ✅ |

**真实日志噪声分布**（`evolution_log.jsonl` 中 3358 条真实 `aa_gate` 行）：

| 统计 | 值 |
|------|-----|
| 中位数 `noise_p95` | **0.1865** |
| ≤0.03 的比例 | **0.36%** |
| >0.10 的比例 | **97.5%** |

### 4.2 ❗ 原报告 W4 使用合成数据，两个数字均不成立

原 `.tmp/closeout/closeout-report.md` 的 W4 节自述（第 227 行）：

> `| 噪声分布 | N(0, 0.025) + 10% outlier N(0, 0.08) | 模拟真实运行噪声 |`

其 F3（第 286 行）亦自承「W4 复测使用模拟数据而非真实运行日志数据」。但**结论采用了模拟数字**：

| 指标 | 原报告（合成） | **真实数据** | 差异 |
|------|---------------|-------------|------|
| `noise` | 0.0302（"超门限 0.6%"） | **0.1777** | **5.9×** |
| `FPR` | 1.7%（判失败） | **0.0%** | **判定相反** |
| H13 | 不成立 | 不成立 | 结论一致，**但依据强度完全不同** |

**同时**，原报告第 104 行自己记录的**真实**门值恰是 `gate_status()["noise_p95"] = 0.210766`
—— 与它用于结论的 0.0302 相差约 7 倍，构成报告内部矛盾。

### 4.3 更正后的裁定

> **H13（噪声基底 ≤ 0.03 适应度分辨率）在真实运行数据下不成立。**
>
> - `noise_p95 = 0.1777`（日志中位 0.1865），**超出 0.03 门限约 5.9 倍** —— 属**决定性**超出，
>   不存在「接近门限、可能是统计波动」的解释空间。
> - `aa_two_window_fpr = 0.0%` **通过** ≤1% 门限。
> - ⇒ **G4 的失败完全由 `noise_p95` 一项造成**，而非两项都失败。

按方案 §11 R6 / M4-d2：**P2/P3 整体阻塞，SP5-B 与 SP6 不可开工；闭环保持永久 shadow。**

### 4.4 对先前表述的更正（留痕）

本项目早前一处汇总额表述为「新口径 `bootstrap_upper95(P95|δ|) = 0.0302 > 0.03`（超 0.6%）」，
并据此推测「距门限仅 0.6%，可能属统计波动」。**该表述源自合成数据，已作废。**
真实差距为 **5.9 倍**。

---

## 5. 未完项

| ID | 严重度 | 问题 | 状态 |
|----|--------|------|------|
| **F1** | 中 | `_h13_assessment` 仅检查 `noise_p95 > 0.03`，未含 `pool_floor(1/√n)` 双重条件 | **未修 —— 见下** |
| F2 | 低 | 历史 `evolution_log.jsonl` 无 `aa_window` 键（W1 之前记录） | 待下次在线运行自然产生 |
| F3 | 低 | W4 曾用合成数据 | **已由本文件 §4 更正** |

### F1 的技术张力（为何未直接照字面实施）

验证者给出的修法字面为：`pool_floor = 1.0/√n`，当 `p95 > 0.03 且 p95 > pool_floor` 时触发 H13。
但其实测数据**否证了该模型所隐含的「池化按 1/√k 降噪」前提**：

- 决策备忘（`docs/execution/g4-noise-diagnosis-and-decision.md`）用重建的 147 窗序列实测：
  - **未配对池化** null P95 最小仅 **0.0956**（去趋势 k=3），k≥5 后**回升**
  - **A-B-A 配对**最优 **0.0732**（k=6，19 min/决策），且扫描至 **k=30 仍无 ≤0.03 的点**
- 原因是窗口 delta 强自相关（lag-1 `r1 = −0.504`，与「两点采样之差」理论值 −0.5 吻合）
  且存在分钟级慢漂移分量 —— 池化并不按 1/√k 收敛。

因此若按 `1/√n` 字面实施，在 n≥1111 时 `pool_floor < 0.03`，会**误判「池化可达」**，
与实测的「k=30 仍不可达」直接矛盾。

**建议**：F1 的判据应基于**实测池化曲线**（如「在 k ≤ K_max 内池化后的 P95 是否曾 ≤0.03」），
而非解析的 `1/√n` 模型。这是一个需要设计决策的小改动，不宜按字面照抄。

> 注：无论采用哪种口径，当前真实数据下 H13 的裁定**不变**（0.1777 ≫ 0.03，且实测池化最小 0.0732 > 0.03）。

---

## 6. 回归与硬约束

| 检查项 | 结果 |
|--------|------|
| 回归测试（18 文件） | ✅ **292 / 292 passed** |
| G3 位精确 | ✅ 二进制位不变 |
| C1 新增 `control.*` 写入 | ✅ **0** |
| C3 `jump_rate >` 处数 | ✅ 1 |
| C5 `_vote` 顺序同 HEAD | ✅ |
| C6 四处 `clip(·,±70)` 逐字 | ✅ |
| `auto_commit_enabled` / `shadow` | ✅ 恒 `false` / 恒 `true` |
| 退出码 | ✅ 非 0 均判定为 pytest atexit cleanup（Windows Temp PermissionError），非测试失败 |

---

## 7. 留存证据

| 路径 | 内容 |
|------|------|
| `artifacts/fitness_aa_report.json` | n=302 真实 A/A 报告（`g4_pass=false`） |
| `fly64/skills/evolution_log.jsonl` | 3358 条真实 `aa_gate` 行（噪声时间序列） |
| `docs/execution/g4-noise-diagnosis-and-decision.md` | 噪声根因诊断与三路径决策备忘 |
| `.tmp/closeout/closeout-report.md` | 原结案报告（W4 节已由本文件更正） |
| `.tmp/g4_diag/`、`.tmp/t4_verify/`、`.tmp/t2_verify/` | 各阶段可复跑脚本与 JSON |

**证据边界**：`memory.json` 与 `.cache/malecns/manifest.json` 不存在（H5/H6/H11 未关闭）；
`σ_floor=0.03`、`k`、`FPR≤1%` 均为规格初值【待标定】；引用的 `noise_p95` / `delta_stats`
属 E-4 层检测伪影范畴，已随文标注。
