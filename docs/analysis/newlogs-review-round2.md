# 二轮复审：t6 对 F-1～F-10 与两处 t3 修正的闭环核验（t7）

> **复审对象**：t6 返修成果（objective：闭环 `docs/analysis/newlogs-review.md` §9 的 F-1～F-10 与 §4 的两处 t3 修正）
> **复审依据**：`docs/analysis/newlogs-review.md`（t5，284 行 / 45,078 B）
> **复审人**：`verifier`（AgentTeams `fly64-newlogs-0924-0926` / task **t7** / attempt `8ed1f838-7ee5-48d4-9d66-e86c7487a1f9`）
> **复审时刻**：2026-09-26 14:2x–14:4x（本地）
> **纪律**：只读核验 + 撰写本报告。**未修改** t6 产出（5 份 R3 文档）与 `fly64/**`；复算脚本落在 `.tmp/t7_verify/`（gitignore 内）。

## 0. 复审判定

| 项 | 判定 |
|---|---|
| **verdict** | **pass** |
| F-1～F-10 闭环 | **10 / 10 闭环**（F-10 为「登记 + 声明范围外」，其后续项见 §8-①） |
| 两处 t3 修正 | **2 / 2 闭环** |
| 独立复算 514 / 1312 | **复现成立**（`distinct callId = 1312`、`redundant = 514`；两域各自同域相减均为 514） |
| F-1 类错误（跨域相减）绝迹 | **成立** —— 残留 `1131` 12 处、`1826 − 695` 3 处、`1152` 3 处，**100% 位于显式勘误/反例语境，0 处作为权威值**（逐条附表见 §2.3） |
| 代码行号抽查 | **成立** —— `model.py:2562-2566`（ratio 门）+ `:678`（`_jump_rate_ratio_gate = 0.75`）+ `gain("jump")` 4 处（`1335/1849/1875/1906`）+ `main.py:3212`；`:2478` / `:1842` **不再作为权威位置**（全部带 `@HEAD` / 「注释行」/勘误标签） |
| §1.2「真问题」与 D-15 | **一致且不再矛盾**（同一条迁移的两个侧面：语义已迁 / 参数未落地） |
| medium / low 落实 | **7 / 7 落实** |
| append-only | **既有条目一条未删、未放宽**（反证见 §6）；**方法受限 + 发现 2 处块内插入（+1 / +2 行号位移）**，均为「块内补注」而非删除 |
| `verify_doc_citations.py` | **EXIT=0**（98/98 通过，96 警告）；**覆盖缺口未扩展**（仍只覆盖 3 份文档）→ 列为后续项（§8-②） |

**后续项（不阻塞本次 pass）**：① 修改 `blindspot-review-round2.md:396` 的「差值恒为 11」原文（F-10 的原始载体，t6 已声明不在其 in-scope）；② 扩展 `scripts/verify_doc_citations.py` 的 `DOCS` 以覆盖 R3 三份新文档；③（可选）为 12 处"历史值 `1131`"加一行 grep 白名单说明，避免下一轮复审误判为残留。

---

## 1. 逐条核验（要求 → 实际改动 file:line → 证据 → 判定）

> 证据列中的 grep 命令统一为 `python .tmp/t7_verify/dump.py '<正则>'`（正则逐行命中五份文档）与 `.tmp/t5_verify/indep_count_t5.py`（独立计数）。

### F-1（blocker）跨域相减「重复副本 = 1826 − 695 = 1131」

| | 内容 |
|---|---|
| **要求（t5 §9-F-1）** | 统一改写为三段式（全快照域 / 窗口域 / 窗口外）+ 每段声明域；加入「任何减法必须两项同域」；正确值 **514** |
| **实际改动** | `project-state-consolidated.md` **L19**（域声明）、**L23-30**（6 行域化口径表：全快照域 `1826 / 1312 / 514`；窗口域 `1209 / 695 / 514`）、**L32-33**（勘误 + 硬约束）、**L46-53**（三段式下游引用）；`blindspot-crossvalidation.md` **L534-539**（三域并列 + `1826` 只能与 `1312` 相减）、**L559**；`session-log-recommendations.md` **L999 / L1002 / L1003 / L1112 / L1140**；`session_logs_execution_plan.md` **L1063 / L1064 / L1074 / L1181** |
| **证据** | ① 独立复算：`main tool/call = 1826`、`distinct callIds = 1312`、`redundant copies = 514`（脚本原样输出见 §9-1）；② 算术自洽：`665+391+153 = 1209`、`1209+617 = 1826`、`695+617 = 1312`、`1826−1312 = 514`、`1209−695 = 514` —— 五式全部成立；③ 残留扫描见 §2.3（0 处未标注） |
| **判定** | **闭环（blocker 解除）**。修正方式优于要求：表格式三域并列 + 反例留痕（`1826 − 695` 作为"反例"保留在勘误语境内） |

### F-2（high）「唯一执行门 `jump = jump_rate > 0.04`（`model.py:2478`）」只对 HEAD 成立

| | 内容 |
|---|---|
| **要求** | 每条 `file:line` 标 scope（`@HEAD` / `@工作区`）；现时结论改用工作区行号 + ratio 语义；0.04-vs-0.043 降级为「迁移前的历史论据」 |
| **实际改动** | `project-state-consolidated.md` **L119**（`@HEAD（迁移前）` + `model.py:2478 @HEAD` + 工作区 `2562-2566` + `_jump_rate_ratio_gate = 0.75` @`678` + 「0.04-vs-0.043 降级为迁移前历史论据」+ 「与 D-15 不再矛盾」）；`session-analysis-0924-0926.md` **L84 / L210 / L458 / L459**；`blindspot-crossvalidation.md` **L271**（引用块内 `**@HEAD**`）/ **L272**（【t6／F-2 校正】整段）；`session-log-recommendations.md` **L1141**；`session_logs_execution_plan.md` **L1182** |
| **证据** | 全 10 处 `2478` 命中逐条检查（§9-3）：每条含 `@HEAD` / `HEAD 口径` / `迁移前` / 校正块之一；工作区实测 `model.py:2478` = `# 7a. Strong figure-ground energy without approaching → lateral object avoidance`（无关注释），`:2562-2566` = ratio 门、`:678` = `self._jump_rate_ratio_gate = 0.75`（§9-2） |
| **判定** | **闭环**。scope 标注 + 工作区口径 + 历史论据降级三项全部到位 |

### F-3（high）「`gain("jump")` 全仓库仅此一处（`model.py:1842`）」

| | 内容 |
|---|---|
| **要求** | 改为「`get_gain("jump")` 共 4 个代码位点（`1335/1849/1875/1906`），其中乘进电流注入的是 `:1849`/`:1875`」并删除"全仓库仅此一处" |
| **实际改动** | `project-state-consolidated.md` **L118**（4 位点 + `main.py:3212` + 乘进注入的只有 `:1849`/`:1875` + 勘误「原文写 `1842`，当前工作区是注释行、'仅此一处'不成立」+ 明示保留未推翻的子命题）；`session-analysis-0924-0926.md` **L84 / L458 / L459**；`session-log-recommendations.md` **L1142**；`session_logs_execution_plan.md` **L1183** |
| **证据** | ① 工作区实测 4 个 `get_gain("jump")` 代码位点 = `1335 / 1849 / 1875 / 1906`（+ `main.py:3212` 遥测、tests 若干）；② 全 6 处 `1842` 命中均为「注释行」/勘误/范围表语境（§9-3）；③ "仅此一处" 3 处命中全部位于引述旧文 + 反驳语境（§9-3） |
| **判定** | **闭环**（并正确保留了未推翻的子命题，未过度回退） |

### F-4（medium）「87 处 write/edit」口径未声明

| | 内容 |
|---|---|
| **要求** | 写为「原始调用 126（逐快照唯一 (工具,路径) 87；全局唯一路径 63）」 |
| **实际改动** | `project-state-consolidated.md` **L55**；`session-log-recommendations.md` **L1143**；`session_logs_execution_plan.md` **L1066 / L1184** |
| **证据** | 我的四值复算：调用 **126**、Σ逐快照 unique(工具,路径) **87**、全局唯一路径 **63**、全局 unique(工具,路径) **69** —— 文档给出的 126/87/63/69 **与复算逐位一致**（反而比要求多给了 69） |
| **判定** | **闭环** |

### F-5（medium）「51 个未跟踪」不可复现

| | 内容 |
|---|---|
| **要求** | 给出 51 的判据或改为 71（本轮前）/74（现测） |
| **实际改动** | `session-analysis-0924-0926.md` **L291 / L342 / L348 / L356 / L363 / L382 / L489**（`51` → 「51 个**窗口产出条目**（手工枚举子集）」，并补 `?? 实测 74 / 剔除本轮 3 份文档 71`）；`project-state-consolidated.md` **L223 / L361**；`session-log-recommendations.md` **L1144**；`session_logs_execution_plan.md` **L1067 / L1184** |
| **证据** | 现测 `?? = 75`（= 74 @t6 时点 + 我的 t5 报告 `newlogs-review.md` 1 份）；文档声明"74（2026-09-26 14:0x 现测）+ 剔除本轮 3 份新文档 71"**与时点一致**（本轮我新增的报告不在其口径内） |
| **判定** | **闭环**（判据补齐 + 时点声明，比"改为 71"更完整） |

### F-6（medium）t2 自报 563 行 vs 实测 562 行

| | 内容 |
|---|---|
| **要求** | 改 562 并写明计数方法 |
| **实际改动** | `session-analysis-0924-0926.md` **L381**（562 = `splitlines()` = `count("\n")`；并说明 563 只出现在交付消息、正文未声明；**加时点声明"现为 569 行"**）；`project-state-consolidated.md` **L10 / L506**；`session-log-recommendations.md` **L988 / L1128 / L1145**；`session_logs_execution_plan.md` **L1051 / L1069 / L1185** |
| **证据** | 现测：t2 = **569**、t3 = **564**、consolidated = **601**、reco = **1153**、plan = **1199** —— 与文档声明的"t2 = 569 / t3 = 564"**逐位一致**；t5 时点的 562/559 也被正确标注为「@t5 核验时点」 |
| **判定** | **闭环**（并额外解决了"返修后行数变化导致旧引用失真"的次生问题） |

### F-7（low）§0.3「两项（B15/B16）」实为三项

| | 内容 |
|---|---|
| **要求** | 改"三项（B15/B16/B17）" |
| **实际改动** | `project-state-consolidated.md` **L89** → 「**R3 新增三项续用 B 空间（`B15` / `B16` / `B17`）**（t6／F-7 更正：原文误记"两项"）」 |
| **证据** | 全文档 `B15/B16/B17` 出现于 §0.3-4、§4 标题、§4.1 映射、§4.2 清单、附录 A/B —— 计数 `B01…B17` 共 17 项、`35 = 18 + 14 + 3` 仍自洽 |
| **判定** | **闭环** |

### F-8（low）t3 的 O-1…O-10 / X-1…X-7 编号在 t4 中 0 次出现

| | 内容 |
|---|---|
| **要求** | 附录 A 增加 t3 O-/X- 编号映射 |
| **实际改动** | `project-state-consolidated.md` 新增 **附录 A.2（L542 起）**，逐行 **17 条**：`O-1…O-10`（L548-557）+ `X-1…X-7`（L558-564），每条给出落点（如 `O-1 → D-09 / §6.1-V-4 / §6.2-B-4`；`X-7 → D-02 / D-07`） |
| **证据** | 逐行提取：O 行 **10** 条（L548-557 连续）+ X 行 **7** 条（L558-564 连续）= **17**，无缺号；`O-/X-` 命中数由 t5 时的 `0 / 0` 变为非零（§9-4） |
| **判定** | **闭环** |

### F-9（low）`check_version.py` 未标路径

| | 内容 |
|---|---|
| **要求** | 首次出现处写全 `fly64/tests/check_version.py` |
| **实际改动** | 五份文档的**首次出现处**全部补齐：`session-analysis-0924-0926.md` **L279 / L288**；`blindspot-crossvalidation.md` **L69 / L92 / L94**（另 L101/L103/L410/L458）；`project-state-consolidated.md` **L201 / L202 / L325 / L341 / L358 / L489 / L592**；`session-log-recommendations.md` **L786**；`session_logs_execution_plan.md` **L91 / L1160** |
| **证据** | 全 43 处 `check_version` 命中逐条检查：**五份文档各自的首处均带 `fly64/tests/`**；后续出现处仍有短名（属正常回指，不影响） |
| **判定** | **闭环** |

### F-10（low，跨文档）「`Measure-Object -Line` 与 `wc -l` 差值恒为 11」

| | 内容 |
|---|---|
| **要求** | 更正为差值 32 / 68 |
| **实际改动** | `session-analysis-0924-0926.md` **L367**（【t6／F-10 更正】「原文写'与 `wc -l` 差 11'不成立；实测 68（PS 339 vs Python 407）/ 32（PS 179 vs Python 211）」）；`project-state-consolidated.md` **L507**（§6.3-8 明确记载"该说法出现在 `blindspot-review-round2.md:396`，**非 R3 产出且不在本任务 in-scope**"）；`session-log-recommendations.md` **L1149**；`session_logs_execution_plan.md` **L1068 / L1187** |
| **证据** | 我的独立实测：`evo_liveness_guard.py` PS **339** / Python **407**（差 **68**）；`evo_loop_launcher.sh` PS **179** / Python **211**（差 **32**）；`blindspot-review-round2.md:396` **仍含**「两文件差值同为 11」（该文件不在 t6 in-scope，t6 已声明未改） |
| **判定** | **闭环（登记 + 声明范围外）**；原始载体未改 → **后续项 §8-①** |

### t3 修正 ①（EVO-072/073「零处提及」→「3 处回显、均未识别为待删对象」）

| | 内容 |
|---|---|
| **要求** | 改写措辞，实质结论不变 |
| **实际改动** | `blindspot-crossvalidation.md` **L254**；`project-state-consolidated.md` **L216**；`session-log-recommendations.md` **L1150**；`session_logs_execution_plan.md` **L1188** |
| **证据** | 三处均写「提及 **3 处**（12:24:27 锚点表回显 / 12:25:31 读文件 / 12:25:40 自述），**均未识别为待删对象**」；与我的 t5 C7 一手计数（51f62457-v2 命中 3 处，全为回显）**逐位一致** |
| **判定** | **闭环** |

### t3 修正 ②（pkill「连续 6 轮」→ 双口径）

| | 内容 |
|---|---|
| **要求** | 「6 次 `write` 脚本轮次（11:54:25→12:02:59）/ 实际执行 3 条（11:55:30 / 11:57:24 / 12:02:47）」 |
| **实际改动** | `blindspot-crossvalidation.md` **L498 / L501 / L561**；`project-state-consolidated.md` **L272**（D-10 事件行）；`session-log-recommendations.md` **L1151**；`session_logs_execution_plan.md` **L1095 / L1189** |
| **证据** | 6 处全部为双口径表述；「连续 6 轮」仅剩 **4 处**命中且全部是「引述旧措辞 + 改写说明」的勘误行（reco L1151、plan L1189 等）；D-10 事件行（consolidated L272）已确认改写 |
| **判定** | **闭环**（归因结论"09-26 全天仅 `6c53f724-v3` 执行过 `pkill -f fly64.main`"未变，与 t5 C1 复现一致） |

---

## 2. 独立复算与残留扫描（F-1 专项）

### 2.1 独立计数（复用 t5 自写抽取器，非 t6 脚本）
```
$ python .tmp/t5_verify/indep_count_t5.py
main tool/call TOTAL = 1826
sub  tool/call TOTAL = 12782
distinct callIds     = 1312
callIds appearing >1 = 456  redundant copies = 514
snapshot-chain dedup = 1312  (redundant 514 )
per-date dedup (distinct callId):  2026-09-24 336 | 2026-09-25 206 | 2026-09-26 153
sum of per-date distinct = 1312
```
⇒ **514 / 1312 复现成立**；窗口域 `1209 − 695 = 514` 与全快照域 `1826 − 1312 = 514` **同值**，且 `695 + 617 = 1312` 解释了二者一致的原因。**F-1 的算术与域声明均正确。**

### 2.2 跨域相减残留（F-1 类错误是否绝迹）
| 表达式 | 命中数 | 语境 | 判定 |
|---|:--:|---|---|
| `1826 − 695` | **3** | consolidated L32、reco L1003、crossvalidation L534 —— 全部标注「跨域相减 / 反例 / 已更正」 | ✅ 无权威用法 |
| `1826 − 1312` | 8+ | 全部作为**同域**正确算式 | ✅ |
| `1209 − 695` | 8+ | 全部作为**同域**正确算式 | ✅ |
| `1152`（t2 反推的另一种跨域结果） | **3** | consolidated L300/L502、crossvalidation L534 —— 全部标注「跨域反推、已作废」 | ✅ |
| `674`（t2 口径合计） | **6** | 对比表"t2 口径"列 + 勘误语境 | ✅ |

### 2.3 `1131` 逐条判定（12 处）
| 文件:行 | 语境 | 是否标注 |
|---|---|:--:|
| `blindspot-crossvalidation.md:559` | 「原写"重复 1131"为跨域相减，已更正」 | ✅ |
| `project-state-consolidated.md:32` | 【t6／F-1 勘误（blocker）】「本文原写…1131，是跨域相减…正确值 514」 | ✅ |
| `project-state-consolidated.md:50` | 【t6／F-1 勘误】「原文写"按 695 反推…1131"——该反推跨域」 | ✅ |
| `project-state-consolidated.md:174` | 「原文「1131」为跨域相减，已勘误」 | ✅ |
| `project-state-consolidated.md:300` | 「原文「1131/1152」为跨域反推，已更正」 | ✅ |
| `project-state-consolidated.md:502` | 「原文的「1131/1152」两种反推均跨域，已作废」 | ✅ |
| `session-log-recommendations.md:999` | C13 行「本块初版曾写…1131（已更正）」「→ 1131（本块初版，跨域相减）」 | ✅ |
| `session-log-recommendations.md:1112` | 冲突裁定表「重复 1131（本块初版值）…1131 = 跨域相减，已作废」 | ✅ |
| `session-log-recommendations.md:1140` | §A.9.10 返修表「F-1：…跨域相减 ⇒「重复副本 1131」错误，正确值 514」 | ✅ |
| `session_logs_execution_plan.md:1064` | 口径增量表「617（t2）→ 1131（本轮初版，跨域相减）→ 514」 | ✅ |
| `session-analysis-0924-0926.md:29` / `:382`（含 `1312` 的同行） | F-1 勘误块（已含"重复副本 514"） | ✅ |

⇒ **12/12 处于勘误、反例或返修清单语境；0 处作为可用值。** F-1 类错误（跨域相减被当作结论）**已绝迹**。
**关于"是否必须把 1131 全部删除"**：验收文字为「确认再无「1131」及任何跨域相减残留」，同时验收又要求「recommendations 与 plan 的既有条目一条未删、未放宽」。两条只有"保留 + 标注"才能同时满足 → 本复审采信 t6 的处置（保留历史值以维持审计链），并落实为 §8-③ 的可选改进。

---

## 3. 代码行号抽查（原始输出见 §9-2）

| 抽查项 | 工作区实测 | 文档引用 | 判定 |
|---|---|---|:--:|
| jump 执行门位置 | `model.py:2562-2566`：`jump = ((jump_rate / max(forward_rate, FWD_RATIO_FLOOR)) > getattr(self, '_jump_rate_ratio_gate', 0.75) and now - self.last_jump >= 0.8)`；注释 `L2562-2563` 自述 *replaces absolute occupancy threshold (jump_rate > 0.04)* | consolidated L119、crossvalidation L272、reco L1141、plan L1182 均引用 `2562-2566` + ratio 语义 | **正确** |
| ratio 门阈值常量 | `model.py:678` = `self._jump_rate_ratio_gate = 0.75` | 同上四处均给 `@ model.py:678` | **正确** |
| `gain("jump")` 位点 | `1335` / `1849` / `1875` / `1906`（+ `main.py:3212` 遥测；`fly64/tests/*` 若干测试） | consolidated L118、session-analysis L458、reco L1142、plan L1183 均为「4 处 + main.py:3212」 | **正确** |
| `model.py:2478` 的当前身份 | `# 7a. Strong figure-ground energy without approaching → lateral object avoidance`（注释） | 全部 10 处命中带 `@HEAD` / 「无关注释」/ 校正块 | **不再是权威位置** |
| `model.py:1842` 的当前身份 | `# ---- MBON-to-motor current injection ----`（注释） | 全部 6 处命中带「注释行」/勘误 | **不再是权威位置** |
| HEAD 对照 | `git show HEAD:fly64/fly64/model.py` = 2492 行、`:2478` = `jump = jump_rate > 0.04 and now - self.last_jump >= 0.8`（`@HEAD` 成立的唯一依据） | 文档明确 `@HEAD` | **正确** |

---

## 4. §1.2 项目级「真问题」与 D-15 的一致性

| 检查 | 结果 |
|---|---|
| §1.2 三条堵点是否与当前工作区语义一致 | **一致**：① gain 4 位点 + 仅 `:1849`/`:1875` 乘进注入；② 门 = `@HEAD` absolute 0.04 → 工作区 `2562-2566` ratio（`0.75` @678）；③ 断口形态迁移仍用 `@HEAD`-独立量级（`v_ss≈0.28 ≪ 1.0`） |
| 是否与 D-15 矛盾 | **不再矛盾**，且 §1.2 已显式写出「与 D-15（工作区 0.75 vs WSL 3.082）**不再矛盾**——D-15 讲的正是同一条迁移的**落地缺口**」。D-15（L304-313）与 §1.2 现为同一迁移的两个侧面（语义已迁 / 参数未落到活体） |
| 是否过度回退（把已成立的论证删掉） | **否**：0.04-vs-0.043 明确降级为「迁移前的历史论据」，未删除；"注入腿只有一条带增益"子命题显式保留 |

---

## 5. medium / low 落实明细（抽查原始输出）

| 验收项 | 要求 | 落实 | 判定 |
|---|---|---|:--:|
| 87 处 write/edit 三选一口径 | 126 / 87 / 63（+69） | consolidated L55 给出 **126 / 87 / 63 / 69** 四值；reco L1143、plan L1066/L1184 同步 | ✅ |
| 未跟踪 74 / 71 | 74 / 71 | session-analysis L291/L342/L348/L356/L363/L382/L489 + consolidated L223/L361 + reco L1144 + plan L1067/L1184 | ✅ |
| t2 562 行 | 562 + 计数方法 | session-analysis L381（`splitlines()` = `count("\n")` = 562 @t5 时点）+ 4 份文档的时点声明 | ✅ |
| §0.3 三项 | 三项（B15/B16/B17） | consolidated L89 + 【t6／F-7 更正】 | ✅ |
| O-/X- 编号映射 | 附录 A.2 | consolidated L542-564：**17 行**（O 10 + X 7） | ✅ |
| `fly64/tests/check_version.py` 路径 | 首处全路径 | 五份文档首处均带路径（见 §1-F-9 清单） | ✅ |
| `Measure-Object` vs `wc -l` 差值 | 68 / 32 | session-analysis L367 + consolidated L507 + reco L1149 + plan L1068/L1187（**原始载体未改**，已声明） | ✅（含后续项） |

---

## 6. append-only 纪律复核（方法受限声明）

### 6.1 既有条目未删、未放宽（反证）
既然 `session-log-recommendations.md` **未被 git 跟踪**（`git ls-files --error-unmatch` → pathspec 不存在），采用**三层反证**：

1. **基线行数只增不减**：reco `1131 → 1153`（+22）、plan `1168 → 1199`（+31）；五份文档均**无净减行**（t2 562→569、t3 559→564、consolidated 563→601）。
2. **t5 时点的关键锚点（行号 + 内容）逐位不变**：
   - reco：**L771**（P2-3 行，含 `407 行`）✔、**L772**（P3-N1 行）✔、**L785**（B01 行，含 `407/211`）✔、**L961**（`## A.8 t5 返修勘误块（append-only…）`）✔、**L972/L973**（E-6/E-7 行）✔、**L979**（「未改动项（明确不放宽）」）✔、**L981**（E-10 追加说明）✔、**L985**（`# A.9 …（append-only）`）✔ —— 全部与 t5 记录**行号与内容一致**（均 < 989）。
   - plan：**L68-85**（18 项建议表）✔、**L1040-1045**（E-1…E-6）✔、**L1046**（空行）✔、**L1049**（`## 2026-09-26 第三轮（一手会话）合并更新附录（append-only）`）✔ —— 行号与内容一致。
3. **关键锚字符串全部存在**（无删除证据）：reco 的 `未改动项（明确不放宽）`、`| **C12**`、`| **C13**`、`| **B01**`、`| **B14**`、`| **P3-N1**`、`A.8 t5 返修勘误块`、`# A.9 2026-09-26 第三轮`、`## A.9.9`、`## A.9.10` **全部 OK**；plan 的 `**P0-N1**`、`**P3-2**`、`| **E-1**`、`| **E-6**`、`第三轮（一手会话）合并更新附录`、`## 2026-09-26 盲区合并更新附录` **全部 OK**。

### 6.2 发现的 2 处「块内插入」（必须如实登记，非删除）
| 文件 | 现象 | 证据 | 影响判定 |
|---|---|---|---|
| reco | 在 §A.9 头部**插入 1 行**（L989「⚠️ 时点/修改声明（t6 补）」）⇒ **L989 及之后的既有内容整体 +1 行**（`## A.9.1` 993→994、C12 997→998、C13 998→999） | 现 L990 仍为旧的「**项目级合并结论**」行、L991 纪律、L992 性质限定 —— 逐条仍在，仅下移 1 行 | **无删除/无放宽**；但"只追加"在**块内**不严格成立（属补注） |
| plan | 第三轮块内**插入口径行**（如 L1063「全局去重（distinct `callId`）」）⇒ 块内后续行 **+2**（切片重复副本 1062→1064、未跟踪 1065→1067） | 现 L1064「切片重复副本」、L1067「未跟踪项数」内容完整；L68-85 与 L1040-1049 未受影响 | **无删除/无放宽**；块内补注导致行号位移 |

⇒ **结论**：**既有条目一条未删、一条未放宽**（三条反证均通过）；但"两文件只追加"应精确表述为「**在文件尾部追加新块 + 在本轮新增块内部补注**」。**方法受限**：① reco 无 git 基线；② 我无法排除"既有行被就地改写但字数不减"的个别情形 —— 只能对上述抽样锚点逐位比对（reco 9 个 / plan 9 个），未做全文逐行 diff。

---

## 7. `verify_doc_citations.py` 与覆盖缺口

```
$ python scripts/verify_doc_citations.py
  session-log-analysis.md: 7 条引用 + 190 条裸 L
  session-log-recommendations.md: 76 条引用 + 384 条裸 L
  session_logs_execution_plan.md: 15 条引用 + 58 条裸 L
总计: 98 条引用 (含 632 裸 L)
通过: 98   警告: 96   失败: 0
[PASS] 所有引用校验通过！
EXIT=0
```
- **exit 0 成立** ✔（t5 时同样为 exit 0，未回归）。
- **覆盖缺口仍未扩展**：脚本的 `DOCS` 列表**仍只有 3 份**（`session-log-analysis.md` / `session-log-recommendations.md` / `session_logs_execution_plan.md`）——**R3 三份新文档（t2/t3/consolidated）不受校验**。t6 未扩展覆盖（其任务未包含该动作）⇒ 按验收要求**列为后续项 §8-②**，不构成 t6 缺陷，但**t7 复审仍以人工抽查替代**（本报告 §3 的 6 项代码行号 + §1 的 file:line 全部人工复核，未发现新的失效引用）。

---

## 8. 后续项与残余风险

| # | 项 | 级别 | 归属 | 建议动作 |
|:--:|---|:--:|---|---|
| ① | `blindspot-review-round2.md:396` 仍写「两文件差值**同为 11**」（实证 68 / 32） | low | **非 t6 in-scope**（t6 已声明并登记） | 另开任务就地更正该行（或加勘误块） |
| ② | `verify_doc_citations.py` 的 `DOCS` 仍只覆盖 3 份，**R3 三份新文档不受校验** | low（工具覆盖） | 工具改进 | 扩展 `DOCS` 至 5 份（含 `session-analysis-0924-0926.md` / `blindspot-crossvalidation.md` / `project-state-consolidated.md`），并复核 exit 0 |
| ③ | 12 处历史值 `1131` 保留在勘误块内（0 处可用） | info | 口径纪律 |（可选）在 §0.1 引用规则处加一句「历史值 `1131` 仅存于勘误语境，grep 命中属预期」，避免下轮复审误判为残留 |
| ④ | append-only 的精确表述 | info | 文档纪律 | 把"只追加"补充为「尾部追加新块 + 块内补注」；若需严格行号稳定，则补注应改为**追加到块尾**而非插在块头 |
| ⑤ | consolidated L276 仍用「连续 `pkill` 叠加」这一**无计数含义**的措辞 | info | 措辞 | 无需修改（非 "6 轮" 计数声明）；如需统一口径可改为「多次 `pkill`（实际执行 3 条）」 |

**未发现任何需要 needs_revision / reject 的问题。**

---

## 9. 复现命令与原始输出摘要（全部只读）

**9-1 独立计数**
```
$ python .tmp/t5_verify/indep_count_t5.py
main tool/call TOTAL = 1826 ; sub = 12782 ; combined = 14608 ; subagent dirs = 118
distinct callIds = 1312 ; redundant copies = 514 ; snapshot-chain dedup = 1312 (redundant 514)
per-date dedup: 2026-09-24 336 | 2026-09-25 206 | 2026-09-26 153 ; sum = 1312
```

**9-2 代码行号（工作区 vs HEAD）**
```
worktree fly64/fly64/model.py (2580 lines)
  L678 : self._jump_rate_ratio_gate = 0.75
  L2478: # 7a. Strong figure-ground energy without approaching → lateral object avoidance   <-- 注释
  L2562: # P1-b3: jump gate uses ratio semantics: jump_rate / max(forward_rate, FWD_RATIO_FLOOR)
  L2563: # replaces absolute occupancy threshold (jump_rate > 0.04).
  L2564: jump = ((jump_rate / max(forward_rate, FWD_RATIO_FLOOR))
  L2565:         > getattr(self, '_jump_rate_ratio_gate', 0.75)
  L2566:         and now - self.last_jump >= 0.8)
  get_gain("jump") sites: 1335 / 1849 / 1875 / 1906 (+ main.py:3212 telemetry)
HEAD:fly64/fly64/model.py (2492 lines)
  L2478: jump = jump_rate > 0.04 and now - self.last_jump >= 0.8      <-- @HEAD 成立
```

**9-3 残留审计**
```
1131     : 12 hits  (crossvalidation 559 | consolidated 32/50/174/300/502 | reco 999/1112/1140 | plan 1064 | analysis 29/382) → 12/12 标注
1826 − 695: 3 hits  (consolidated 32 | reco 1003 | crossvalidation 534) → 3/3 标注为跨域反例
1152     : 3 hits  → 3/3 标注为跨域/作废
2478     : 10 hits → 10/10 带 @HEAD 或校正块
1842     : 6 hits  → 6/6 带「注释行」或勘误
仅此一处  : 3 hits  → 3/3 位于引述+反驳语境
连续 6 轮 : 4 hits  → 4/4 位于勘误改写行
```

**9-4 行数与锚点**
```
session-analysis-0924-0926.md  569 lines
blindspot-crossvalidation.md   564 lines
project-state-consolidated.md  601 lines
session-log-recommendations.md 1153 lines   (L771/772/785/961/972/973/979/981/985 与 t5 记录逐位一致)
session_logs_execution_plan.md 1199 lines   (L68-85 / L1040-1045 / L1046 / L1049 与 t5 记录逐位一致)
appendix A.2 rows: O-1..O-10 = 10 ; X-1..X-7 = 7
$ python scripts/verify_doc_citations.py  → EXIT=0 (98/98 pass, 96 warn)
```

**9-5 脚本清单（`.tmp/t7_verify/`，gitignore 内）**
| 脚本 | 作用 |
|---|---|
| `dump.py` | 在五份文档中按正则逐行打印命中（文件:行 + 上下文），本报告 §1/§2/§9-3 的全部命中清单由它产出 |
| `anchors.py` | 打印 reco/plan 的基线锚点行与 §A.9.10 / 第三轮块标题位置，用于 append-only 反证 |
