# 盲区分析二轮审查报告：t5（M-1～M-6）闭环 + stuck_score 根因链独立复现 + append-only 纪律

> **审查者**: `verifier`（AgentTeams `fly64-blindspot-0923-0926` / task `t6`）
> **attempt_id**: `d9847eb4-8740-4711-99db-4880c3236654`
> **审查时刻**: 2026-09-26 13:05 → 13:25 (+0800)；WSL 取证 13:19；最后一次活体复算 13:1x
> **审查对象（t5 产出）**: `docs/analysis/blindspot-analysis-0923-0926.md`（386 行）、`docs/analysis/blindspot-evidence-0923-0926.md`、`docs/analysis/session-log-recommendations.md`（981 行）、`docs/analysis/session_logs_execution_plan.md`（1046 行）、`docs/analysis/session-log-analysis.md`（544 行）
> **判定基准**: 本人 t4 报告 `docs/analysis/blindspot-review-0923-0926.md` §6.3-4（应改位置与文本）与 §7（M-1～M-5）
> **纪律**: 只读核验；未修改任何 t5 产出（仅新建本报告）。区分 **已闭环 / 部分闭环 / 未闭环**，不复述结论。

---

## 0. 结论

| 项 | 判定 |
|---|---|
| **verdict** | **needs_revision** |
| **闭环率** | M-1～M-6 中 **5 条完全闭环（M-1、M-2、M-3、M-5、M-6）、1 条部分闭环（M-4：a/b/c 三处已闭环，但同批更正把 `evo_liveness_guard.py`/`evo_loop_launcher.sh` 的行数写成 339/179，实测 407/211 ⇒ 新增缺陷 F-2）**；两处新遗漏、RC 口径、append-only 纪律、残留搜索、引用校验**均已通过**。 |
| **核心技术声明** | **stuck_score 根因链完全成立**（我独立复现，且比 t5 的复现更严格：命中数、命中刻、`dur==0` 三项全部对上）。**M-1/M-2 的改写方向正确**，无需返工技术结论。 |
| **阻塞缺陷** | **1 条（高）**：`blindspot-analysis-0923-0926.md` L175 的 **E13 行是"孤立表格行"**（L174 空行切断了 §3.2 的表格），全文件 16 个表格块中**唯一**一个无表头分隔行的块 ⇒ E13 在渲染视图中不显示为表格行。 |
| **次要缺陷** | **2 条（中）**：① `evo_liveness_guard.py` 行数写作 **339**（实测 **407**）、`evo_loop_launcher.sh` 写作 **179**（实测 **211**），**4 处**且与 t5 自己修好的 t1 "`+407/+211` 是新增行数"说明**自相矛盾**；② 磁盘仍写 134 GB（当前实测 **135G**）。 |
| **append-only 纪律** | **符合**：recommendations 36 个 `P*` 行 + 14 个 `B*` 行、plan 18 行建议表**一条未删**；全部更正均带「原值 → 实测值」痕迹或以独立勘误块追加。 |
| **残留旧口径** | 全文搜索 5 份文档：所有 `10→12` / `≡1.0 已消除` / `运行时断言` / `无视觉闭环校正` 命中**均在"原值/勘误/待更正"语境**，**无未标注的过期用法**。 |
| **引用校验** | `python scripts/verify_doc_citations.py` → **exit 0**，`总计: 98 条引用 (含 622 裸 L) / 通过: 98 / 失败: 0`。 |

---

## 1. 独立复现：`stuck_score` 根因链（本轮最关键项）

我**不引用** t5 的仿真，自己重读了源码并重跑了仿真与活体采样。

### 1.1 链条三段逐段核验（源码逐行读出）

```text
memory.py:213  temporal_stuck = self._temporal_low_s >= self.temporal_stuck_s
memory.py:214  frame_stuck    = self._frame_still_s  >= self.frame_stuck_s
memory.py:215  rate_stuck     = self._rate_low_s     >= self.rate_stuck_s
memory.py:217  t_score = min(1.0, self._temporal_low_s / self.temporal_stuck_s)
memory.py:218  f_score = min(1.0, self._frame_still_s  / self.frame_stuck_s)
memory.py:219  r_score = min(1.0, self._rate_low_s     / self.rate_stuck_s)
memory.py:225  stuck_score = max(t_score, f_score, r_score)        # ← 三子分取 max ✔
memory.py:227  currently_stuck = temporal_stuck or frame_stuck or rate_stuck or self._fallen
memory.py:229  self._stuck_duration += self._dt                    # +0.02
memory.py:231  self._stuck_duration = 0.0
memory.py:234  if self.disp_60s is not None and self.disp_60s > 500.0 and self._stuck_duration > 0.0:
memory.py:235      self._stuck_duration = max(0.0, self._stuck_duration - 1.0)   # ← 一次抹回 0 ✔
```

| 段 | 声明 | 我的核验 | 判定 |
|:-:|---|---|:--:|
| (a) | 三子信号取 `max` | 逐行读 `:213-225`；默认值实测 `rate_threshold=0.008` / `rate_stuck_s=3.0` / `temporal_stuck_s=2.0`（`@dt=0.02` ⇒ rate 需 **150 tick**、temporal 需 **100 tick**） | **✔ 成立** |
| (b) | `rate` 子信号是 idle 时恒真那一路 | **隔离实验**：`te=0.9`（temporal 永不触发）、`frame_seq` 每 tick 前进（frame 永不触发）、`fr=0` 恒输入 ⇒ 200 tick 后 `score=1.000`，`rate_low_s=4.00`、`temporal_low_s=0.00`、`frame_still_s=0.00` ⇒ **纯 rate 路径即可把 score 拉满** | **✔ 成立（强证据）** |
| (c) | `disp_60s>500` 泄放把 duration 抹零 | 见 §1.2 实验 A/B 对照 | **✔ 成立** |

### 1.2 「`score==1.0` 且 `dur==0.0`」的独立复现（含对照）

```text
# 实验 A：泄放生效（disp_60s = 600..1090 > 500），idle/move 交替 100 tick
ticks with score==1.0 : 14
of those, dur==0.0    : 14
  tick=299 te=0.0 fr=0.0 score=1.000 dur=0.000 rate_low_s=2.00 temporal_low_s=2.00 frame_still_s=0.00 raw_dur=0.0000
  tick=499 ... 同形  ...（命中 [299,499,699,899,1099,1299,1499,1699,1899,2099,2299,2499,2699,2899]）

# 实验 B（对照，泄放失效）：同一输入，仅把 disp_60s 置 None
  first score==1.0 at tick 299 -> dur=0.020
  ticks score==1.0: 14                      # 命中数相同，但 dur ≠ 0
```

**结论**：4000 tick 规模下命中 **14 次**，与 t5 报告的 **3000 tick / 14 次** 数量级一致；**且我拿到 14/14 全部 `dur==0.0`**，对照组同命中数但 `dur≠0` ⇒ **"抹零确由 `:234-235` 泄放造成"这一因果判断成立**。

### 1.3 对 t5 E13 行内数字的复现边界（诚实标注）

t5 在 E13 行给出命中刻 `[149,363,577,791,1005,1219,1433,1647,1861,2075,2289,2503,2717,2931]`（间隔 +214）。我按其文字参数（150 tick `fr=0` / 64 tick `fr=0.3`、`disp_60s=1090`、`te=0.5`）复跑，得到：

```text
hits: [150, 364, 578, 792, 1006, 1220, 1434, 1648, 1862, 2076, 2290, 2504, 2718, 2932] all dur==0: True
```

即 **t5 的命中刻 = 我的命中刻 − 1**（疑似首个 `frame_seq` 初值差 1 造成的 off-by-one），并额外实测出 **+214 的间隔来自 150/64 交替的世界周期**（我另外扫了 100/100、150/150、200/200、214/214 等周期，均不能产生 +214 间隔）。⇒ **t5 的命中刻列表只有 ±1 的初始化差异，属首次更新索引约定，不影响结论**；**该「离线 +214 间隔仿真」与活体 12:54 六连是同结论的两条独立路径**（活体那组我已在 t4 亲自取得）。

### 1.4 旁证：hz 口径不会误触发（支持 t5「docstring 仍写 Hz 属半迁移」）

```text
feed fr=1.0（per-tick 上限）连续 2000 tick 且 temporal 恒低：
  score=1.000 dur=38.020 rate_low_s=0.00     # rate 路永不触发，score 由 temporal 路给出
```

⇒ `rate_threshold=0.008` 的语义域是 **per-tick 比例**（0–1），与 docstring `:127` 残留的 `"< 5 Hz"` **确不等价**；`memory.py` 全文 **`assert` 计数 = 0**（我独立统计）。

---

## 2. 逐条核验 M-1～M-6

| 条目 | 要求（t4 §6.3-4/§7） | 实际改动（file:line） | 证据（命令/原文） | 判定 |
|:-:|---|---|---|:--:|
| **M-1** | A3 拆为两句；判据 `0.08` 标为单点失效 | `blindspot-analysis…:226`（§4.1-A3）：「① ✅ 已解决（仅"单位标注"）／② ✘ 不成立（"不再 ≡1.0"）」，且带 `（t5 拆分；原值：单句「✅ 已解决」）`；`:253`（§4.4-C1）改为「**拆分后"部分冲突"**：① 单位标注…"仍存在"过时、已解决 ② 可观测性…仍成立」；`:19` 摘要同步 | 逐行读出原文；`memory.py:135/207-208` 复读确认；t4 六连 + 我的隔离实验与对照实验 | **已闭环** |
| **M-2** | B3 改写为「不成立/未缓解」并给机制 | `…:236`（§4.2-B3）判定列已改「**未缓解**`（t5 改写；原值：「部分缓解 + 新增子项…」中的"缓解"部分不成立）`」，依据列写明「原写『构造伪影已消除』✘ 不成立」+ rate 子信号 + 泄放 + 离线仿真；`:335`（§8 返修表 M-2 行）给出「原值 → 改写后」 | 原文逐行读出；§1.2 独立复现（14/14 `dur==0.0`） | **已闭环** |
| **M-3** | A4 统一 10/14/16/17 且标注未恶化与 12 伪影来源 | `…:227`（§4.1-A4）判定「**仍存在，但未恶化**`（t5 更正；原值：「仍存在且恶化」）`」，依据列给 `10 / 生产 14 / 含 fly64/tests 16 / 含根 tests 17` + 冻结正则 +「`2f87d77^`=`HEAD`=工作区均为 10」+ 12 来源（`main.py:2618`/`:2959`）；`:338`（§8 M-3 行）同文；`recommendations:359/918` 已有同样口径；`session-log-analysis:402-404/428/430-442/451-452` 全部换成当前行号 | 我重跑 `control\.x\s*=(?!=)` → main.py 10「行号 [760,2060,2077,2141,2190,2192,2406,2414,2466,2492]」/ naive 12 / 生产 14 / 含 fly64/tests 16 / 含根 tests 17；`2f87d77^` 与 HEAD 同 10 | **已闭环** |
| **M-4a** | guard 路径改 `fly64/scripts/` | `…:162`（E1 行）已写 **`fly64/scripts/evo_liveness_guard.py`** + 「⚠️ t5 更正：不在 `fly64/skills/`」；`:339`（§8 M-4a 行）同；`recommendations:972`（E-6）；`evidence:677-689` | `Test-Path fly64/skills/evo_liveness_guard.py` → **False**；文件在 `fly64/scripts/`（15,863 B） | **已闭环** |
| **M-4b** | 锁路径改 `/root/fly64/skills/.evo_loop.lock` | `…:340`（§8 M-4b 行）；`evidence` 同 | `wsl cat /root/fly64/skills/.evo_loop.lock` → `11997`；根目录下不存在 | **已闭环** |
| **M-4c** | E8 措辞改「无 flow/memory 发布点」 | `…:169`（E8 行）已就地更正 | 我复跑：`main.py:2206 model.burst_active = …` 存在；活体 `flow.json`/`memory.json` 均无该键 | **已闭环** |
| **⚠️ M-4d（新发现）** | —（t5 自行引入，不在 t4 要求内） | `…:162`「**（339 行 / 15863 B）**」、`:339`「**339 行/15863 B**」；`recommendations:771`/`:785`「`evo_liveness_guard.py`（339 行）· `evo_loop_launcher.sh`（179 行）」、`:972`（E-6）「**339 行 / 15,863 B**」「**179 行 / 7,889 B**」 | **实测：`evo_liveness_guard.py` = 407 行 / 15,863 B；`evo_loop_launcher.sh` = 211 行 / 7,889 B**（字节数对、行数错）。且 t5 自己在 `evidence:677` 写「`+407/+211` 是 `git show --stat` 的**新增行数**；**文件总行数** …」⇒ **t5 前后自相矛盾** | **未闭环（缺陷 F-2，共 5 处）** |
| **M-5** | P1-N1 标题「+运行时断言」更正 | `recommendations:195`（标题留原文）+ `:967`（E-1 勘误行，点名 L195/L223/L234/L248 与"断言这一半"）；`plan:1040`（E-1，点名 L72/L88/L846/L975/L1010/L859）；`session-log-analysis:396/541` 就地勘误 | 我实测 `memory.py` 全文 **`assert` 计数 = 0**、`rate_threshold` 仅 135/142/208 三处 | **已闭环** |
| **M-6** | 已交付文档回改：CX-2 + 10 个写点行号 | `session-log-analysis:379`（§困境 2 勘误：`relocalize()` 已在 + `:128-140` + 调用点 `:529`/`:673` + 测试 + 活体未验证）；`:395-396`（§困境 3）；`:398/402-404`（§困境 4 两条"必须先读"勘误）；`:428`（四级口径）；`:430-442`（10 行写点表 + 漂移列 +112/+120）；`:451`（当前代码位置，标注"原值（09-24）"）；`:534-542`（附录 C 汇总，声明"只追加"）；`:544`（未改动项声明） | 逐行读出；行号与漂移量与我 t4 实测**逐项一致** | **已闭环** |

---

## 3. 其余核验项

### 3.1 RC 口径 12→13（RC-4 = 2）

| 位置 | 内容 | 核验 |
|---|---|---|
| `analysis:16` | 「本窗口再现同族缺陷 **13 例**（工程侧 10 + 分析工作侧 3）」 | ✔ 与 E1–E13 对应 |
| `analysis:17` | 「原值 12 例（RC-4 = 1，仅 E5）→ 13 例（RC-4 = 2，+ E13）」 | ✔ 留痕 |
| `analysis:175` | E13 行（内容见下 §4.1 缺陷说明） | ⚠️ 内容正确、**结构破坏（F-1）** |
| `analysis:177` | 「与 A3 的关系是『同族症状、不同判据』…与 RC-5 叠加…不构成新子型」 | ✔ 与我 t4 §6.3-5 的 RC 归属一致 |
| `analysis:190/191` | RC-4 由 1 → **2**（E5、E13）；RC-5 行注明 E13 叠加 | ✔ |
| `analysis:194` | 合计 `1+2+2+2+2+2+2 = 13 ✔` | ✔ 算术正确、且注明"E13 只归 RC-4，无重复计数" |
| `analysis:200` | §3.4 改为「**9 例同族延伸 + 4 例新增子型**」（原 8+4=12 → 9+4=13） | ✔ 留痕 |
| `recommendations:974`（E-8）、`plan:1042`（E-3） | 跨文档一致声明 | ✔ 三文档口径一致 |

### 3.2 两处新遗漏补录

| 遗漏 | 要求 | 实际 | 判定 |
|---|---|---|:--:|
| **100644 无执行位** | 记入 `evo_loop_launcher.sh`（与 guard） | `analysis:162`（E1 行）、`:343`（§8 补录 1）；`evidence:687-689`；`recommendations:973`（E-7 补录 1）；`plan:1041`（E-2） | **✔ 已补录** |
| **两份不同 evolution_history** | 记入两侧差异 + 各自消费方 | `analysis:344`（§8 补录 2）+ §2.5；`evidence:199/545/565/697-698`；`recommendations:973`（E-7 补录 2）；`plan:1043`（E-4）——均写明 **`7,110–7,134 B`、每轮重写、仅 WSL**、结构 `{brain_version, iterations}`、消费方 `main.py:61/220/2360` vs `evolution_skill.py:202` | **✔ 已补录，且为正确口径**（见 §5） |

我独立复核该条的**事实正确性**：Windows `fly64/runtime/evolution_history.json` → **不存在**（`os.path.exists` False）；WSL `/root/fly64/runtime/evolution_history.json` → 存在，**7,120 B / 顶层键 `brain_version`+`iterations` / iterations = 20 条**；WSL `skills/evolution_history.json` → 存在，**87 条记录**、`canonical_versions.skill = 3.4.2`、首 `EVO-001` 末 `EVO-074`、`EVO-072` 不存在；Windows 同文件 → 同样 **87 条**、md5 与 WSL **完全相同 `d98c46f96e7d`**。

### 3.3 残留旧口径搜索（5 份文档）

| 搜索词 | 命中 | 是否均为「已标注」语境 |
|---|---|:--:|
| `10→12` | `analysis:19/227/338`、`recommendations:359/918`、`session-log-analysis:403/542` | ✔ 全部为「原报/伪影来源/更正后」语境（含 `（t5 更正；原值：…）` 或 `原值（09-24）` 标记） |
| `≡1.0 … 已消除` / `已消除` | `analysis:236/335`、`recommendations:200/865/968` | ✔ 全部在「原写…✘ 不成立」或「E-2/E-3 勘误」语境 |
| `运行时断言` | `analysis:17/175/177/191/337`、`recommendations:195/223/234/248/967/975`、`plan:859/1040`、`session-log-analysis:396/541` | ✔ 正文出现处均被 E-1（recommendations）/E-1（plan）/就地勘误（session-log-analysis）点名更正 |
| `无视觉闭环校正` | `analysis:19/225/254/345/348`、`recommendations:135/809/975/976/981`、`plan:840/1045`、`session-log-analysis:379/540` | ✔ `recommendations:135` 属基线原文（已由 §A.8 E-10 声明为过时，见 §4.2）；其余均在更正语境 |
| `7124` / 工作区存在 `runtime/…` | **0 命中** | ✔ t5 已把该条收紧为「仅 WSL」 |
| `134 GB` | `analysis:238/259` | ⚠️ 未刷新（实测当前 **135G**）；属滚动运维值，见 F-3 |

### 3.4 引用校验

```text
$ python scripts/verify_doc_citations.py
session-log-recommendations.md: 76 条引用 + 374 条裸 L
session_logs_execution_plan.md: 15 条引用 + 58 条裸 L
总计: 98 条引用 (含 622 裸 L)
通过: 98
失败: 0
[PASS] 所有引用校验通过！      → exit 0
```

✔ 与 t5 声明一致（98 引用 / 0 失败）。

---

## 4. 发现（findings）

### F-1（high，阻塞）E13 行是孤立表格行 —— 渲染层失效

- **现象**：`docs/analysis/blindspot-analysis-0923-0926.md` **L173 = E12 行、L174 = 空行、L175 = E13 行**。
- **实测判定**（脚本化分类全文件 16 个表格块）：

```text
table blocks: 16
  BLOCK WITHOUT SEPARATOR: (175, 175, '| **E13** | **`stuck_score` 可达 1.0 而同刻 `stuck_duration == 0.0`（观测层假绿）**…')
E13 in section 3.2 -> line 175
```

  ⇒ 全文件**唯一**一个"有 `|` 行但无 `|:--|` 表头分隔行"的块。任何标准 Markdown 渲染器都会把 E13 渲染为**普通段落文本**（或与前文粘连），而不是 `|ID|实例|…` 表格的第 13 行；该行又较长（含 `[149,363,…]` 仿真细节），渲染后极难阅读，且会被读成"表格结束后的散句"。
- **后果**：§3.2 的小节标题（**L156**）已正确写为「本窗口内再现的实例清单（**E1–E13**）」，表头（L160-161）也在位；但**表格本体只到 E12（L173）就结束**，E13 是表格外的独立行 ⇒ **渲染后读者在表内只会数到 12 行**，与标题与全文反复声明的「13 例」**在视觉上冲突**（标题说 13、表里只有 12）。这是本项目 RC-7「口径/工具链纪律」的又一实例：**内容写对了、结构没接上**（与 E7「生产者删键、消费者兜底」同型）。
- **requiredFix**：① 删除 **L174** 空行，把 L175 直接接回 L173 之后（成为 §3.2 表格的第 13 行，L156 标题无需改动，已为 E1–E13）；② 若担心 E13 行过长，可把「离线仿真参数与命中刻」移入紧随表后的说明段（保留表内摘要），但**必须保证该行处于同一表格块内**（即其后不得出现空行）。

### F-2（medium）行数与字节数不自洽，且与 t5 自己的更正矛盾

- **实测**：`fly64/scripts/evo_liveness_guard.py` = **407 行 / 15,863 B**；`fly64/scripts/evo_loop_launcher.sh` = **211 行 / 7,889 B**。
- **文档写**：`analysis:162`「（**339 行** / 15863 B）」、`analysis:339`「**339 行**/15863 B」、`recommendations:972`「**339 行** / 15,863 B」「**179 行** / 7,889 B」。
- **矛盾**：t5 在 `evidence:677` 明确更正 t1「`+407/+211` 是 `git show --stat` 的**新增行数**，不是文件行数」；t1（`evidence:162`）也已写「（407 行 / 15863 B）」。⇒ **三份文档出现 339/179 与 407/211 两套行数**，属**未标注的口径分叉**（字节数两侧一致，恰好说明"数字被换错的是行数"）。
- **requiredFix**：4 处全部改为 **407 行 / 211 行**；或在被引用处改为「40x 行（见 t1 §1 表）」，避免再落地一个不可复现的行数。

### F-3（low）运维数字未刷新

- `analysis:238`（B5）与 `:259`（C7）仍写「`/tmp` = **134 GB**」；当前实测 `du -sh /tmp` = **135G**（滚动值）。t4 已标明「134→135 同一量级」，**不是错误**，但既已逐条刷新 A4/行号，建议顺手标注「（135G @13:19，滚动）」。

### 4.2 需说明但**不构成缺陷**的一处

- `recommendations:135` 正文仍写「`_self_motion_update()` 使用 heading_rate 开环积分，**无视觉闭环校正**」——这是**基线原文**（P0-N2 小节），已由 `recommendations:976` 的 **E-10** 明确声明该表述与「3 天纯新增」方案已过时，并说明「不修改该小节原文，仅以本块声明」（append-only 纪律允许）。**判定：符合纪律，不需修改**（若追求可读性，可在 L135 行尾加一个指向 §A.8 的锚点，属可选）。
- `analysis:19/225/254/345/348` 的 `无视觉闭环校正`、`analysis:17/175/177` 的 `运行时断言` 均为"引用已交付原文/说明其已更正"的语境 ⇒ ✔。

---

## 5. 队长补充证据的裁定（两份 `evolution_history` 与我的 `7124 B` 出处）

| 问题 | 我的实测与判定 |
|---|---|
| 我的 `7124 B` 是何时何地测得的？ | **WSL 侧 `wc -c /root/fly64/runtime/evolution_history.json` = 7124**（t4 期间 12:56–12:57 测得；同一文件 `ls -l` 显示 7128/7120 等，因该文件**每轮被重写**）。**绝非工作区副本**——t4 报告 §8.2-2 原文即写「`runtime/evolution_history.json`（7124 B）与 `skills/evolution_history.json`（99101 B）是两份不同的『进化历史』文件，t1/t2/t3 只核对了后者；前者 mtime 每轮更新，**是运行时会话的独立副本**」。 |
| 工作区是否存在该文件？ | **不存在**（`os.path.exists('fly64/runtime/evolution_history.json')` → **False**）。t5 收紧为「**WSL-only**」**正确**，t4 的原表述也未声称工作区存在。 |
| 两侧大小/记录数会独立变化吗？ | **会**。我 13:19 实测：WSL `runtime` = **7,120 B / iterations 20 条**（与你 7,810 B 之差即"两次测量间增长"）；WSL `skills` = **99,101 B / records 87 条**（与**你的 86 条不符**，但与 Windows 87 条**完全一致**，且两侧 **md5 相同 `d98c46f96e7d`**）⇒ 「WSL skills = 86」这一条**我无法复现**（我的两次测量均为 87），建议以「87（Windows）/ 87（WSL，md5 相同）」并入文档，并把 86 标为"另一时点观测"。 |
| 该条属 t6 验收项「两处新遗漏补录」的范畴吗？ | 属。**t5 已正确写为「仅 WSL / 7,110–7,134 B / 每轮重写 / 消费方 main.py:61/220/2360」**（`analysis:344`、`evidence:697`、`recommendations:973`、`plan:1043`），**该验收项通过**；仅需在上述行数缺陷（F-2）与"86 vs 87"上补一句口径说明。 |

---

## 6. append-only 纪律核验

| 文档 | 手段 | 结果 |
|---|---|---|
| `session-log-recommendations.md` | 统计 `^\| \*\*P[0-3]` 行数 = **36**、`^\| \*\*B[0-1]` = **14**、新增 `^\| \*\*E-` = **10**；勘误集中在 §A.8（L961–981） | ✔ `P*`/`B*` **一条未删**；全部更正以 E-1～E-10 追加 |
| `session_logs_execution_plan.md` | 建议表 18 行（L68–85）仍在；新增 `E-1～E-6`（L1040–1045）在文末块 | ✔ 18 行**未减**；勘误仅在文末附录 |
| `blindspot-analysis-0923-0926.md` | §8 返修表（L330–349）逐条「原值 → 实测值」；就地更正处均带 `（t5 更正；原值：…）` | ✔ 留痕完整 |
| `session-log-analysis.md` | 就地勘误 + **附录 C**（L534–544「本附录只追加」）+ L544「未改动项（明确不放宽）」 | ✔ 三处过时事实更正，§1–§4 主题分类/12 例清单/§5 困境问题本身**保持原样** |
| `blindspot-evidence-0923-0926.md` | `:677` 更正 `+407/+211` 口径；`:199/697` 补录两份历史文件 | ✔ 追加式 |

**未发现任何条目被删除或表述被放宽。**

---

## 7. 判定与 requiredFix 汇总

**verdict: needs_revision**（技术结论全部成立，缺陷在呈现结构与两个数字）

| ID | 级别 | 问题 | 文件:行 | requiredFix |
|:-:|:--:|---|---|---|
| F-1 | **high** | E13 行被空行切出表格（全文件唯一无分隔行的表格块）；§3.2 标题仍写 E1–E12，渲染层只能数到 12 行，与"13 例"冲突 | `blindspot-analysis-0923-0926.md` L174–L175（§3.2） | 删除 L174 空行使 E13 归入表格；标题/表头改 E1–E13；过长内容可移入表后说明段但须留在同一表格块 |
| F-2 | medium | `evo_liveness_guard.py` 写 339 行（实测 407）、`evo_loop_launcher.sh` 写 179 行（实测 211），共 **5 处**；与 t5 自己在 `evidence:677` 的口径更正（`+407/+211` 是 `--stat` 新增行数）矛盾 | `analysis:162`、`analysis:339`、`recommendations:771`、`recommendations:785`、`recommendations:972` | 5 处改为 **407 行 / 211 行**（或统一引用 t1 §1 表已写对的 `407 行 / 15863 B`） |
| F-3 | low | `/tmp` 仍写 134 GB | `analysis:238`、`analysis:259` | 标注为「134→135 GB（滚动，13:19 实测 135G）」 |
| F-4 | low | 「WSL `skills` records = 86」与我的两次实测（均 87、与 Windows md5 相同）不符 | 无文档待改；建议在 `evidence:697`/`analysis:344` 的口径中补一句 | 建议表述为「Windows 87 / WSL 87（md5 `d98c46f9…` 相同）；曾观测到 86（另一时点）」 |

**返工范围建议**：仅需在 **`blindspot-analysis-0923-0926.md`（F-1、F-2 的 2 处、F-3）** 与 **`session-log-recommendations.md`（F-2 的 1 处）** 做**就地/追加**小改（约 5 处），**无需重开技术分析、无需改任何结论**；改完由 `verify_doc_citations.py` 复跑 exit 0 即可再送审。

**已通过、不得再改的部分**（防止返工时误伤）：M-1/M-2 的 B3/A3 改写文本、M-3 的四级口径与"未恶化"、M-4a/b/c 三处路径、M-5 的 E-1 勘误、M-6 的 `session-log-analysis.md` 附录 C 与行号表、RC 13 例口径与 RC-4=2、两处新遗漏补录、append-only 结构。

---

## 附录：本轮全部复现命令与原始输出（摘要）

```bash
# 1) stuck_score 根因链（离线，只读）：见正文 §1.1/§1.2/§1.4 的逐行源码与仿真输出
#    关键点：memory.py:213-225 max() / :227-231 duration ±0.02 / :234-235 disp>500 ⇒ −1.0
#    实验 A（disp=600+…）3000~4000 tick：score==1.0 恰 14 次，14/14 dur==0.0
#    实验 B（disp=None）   ：score==1.0 同 14 次，dur=0.020（≠0）⇒ 抹零因果成立
#    隔离实验（te=0.9, frame 每 tick 前进, fr=0）200 tick：score=1.000 rate_low_s=4.00 temporal/frame=0.00
#    对照（fr=1.0 恒输入 2000 tick）：score=1.000 dur=38.020 rate_low_s=0.00

# 2) E13 表格结构
python -X utf8 -c "import io;L=io.open('docs/analysis/blindspot-analysis-0923-0926.md',encoding='utf-8').read().splitlines();print(L[173]=='' , L[174].startswith('|'))"
#  → True True（L174 空行、L175 表格行）＋全文件表格块分类：唯一无分隔行者 = (175,175)

# 3) 行数/字节
python -c "import io,os;[print(p,sum(1 for _ in io.open(p,encoding='utf-8')),os.path.getsize(p)) for p in ['fly64/scripts/evo_liveness_guard.py','fly64/scripts/evo_loop_launcher.sh']]"
#  → evo_liveness_guard.py 407 15863 ; evo_loop_launcher.sh 211 7889

# 4) control.x 四级口径
python -c "import re,io;t=io.open('fly64/fly64/main.py',encoding='utf-8').read();print(len(re.findall(r'control\.x\s*=(?!=)',t)),len(re.findall(r'control\.x\s*=',t)))"
#  → 10 12（赋值 / 朴素）

# 5) memory.py assert 与 rate_threshold 出现处
python -c "import re,io;t=io.open('fly64/fly64/memory.py',encoding='utf-8').read();print(len(re.findall(r'\bassert\b',t)))"
#  → 0 ；rate_threshold 出现处 [135,142,208]

# 6) 两份 evolution_history
python -c "import os;print(os.path.exists('fly64/runtime/evolution_history.json'))"        # → False（工作区无）
wsl -e bash -c 'cd /root/fly64 && ls -l runtime/evolution_history.json skills/evolution_history.json; md5sum skills/evolution_history.json'
#  → runtime 7,120 B；skills 99,101 B / md5 d98c46f96e7d58128c5707e182ef4be2
#  → skills records=87（首 EVO-001 末 EVO-074，canonical skill=3.4.2）；runtime iterations=20

# 7) append-only 计数
#  recommendations：P* 行 36 / B* 行 14 / 新增 E-* 行 10；plan：建议表 18 行 + E-1~E-6

# 8) 引用校验
python scripts/verify_doc_citations.py       # → 98/98 通过, 失败 0, exit 0
```

*本报告为只读核验产物；未修改 t5 任何产出。所有 `[实测]` 均可按上述命令复现。*

---

# 第二轮复审（t8，2026-09-26 13:26–13:34 +0800）— 针对 t7 返修

> **复审者**: `verifier`（task `t8`，attempt `695562fe-9e87-475f-b467-3cc6775b949e`）
> **返修单**: t7（repair-round-2，实际改动 1 文件：`docs/analysis/session-log-recommendations.md` L972；其余 4 处 F-1/F-2 前 4 处/F-3/F-4 由前次崩溃的 t7 attempt 已落盘）
> **判定基准**: 本报告 §7 findings（F-1 high / F-2 medium / F-3 low / F-4 low）

## R1. 结论

| 项 | 判定 |
|---|---|
| **verdict** | **pass** |
| F-1 | **✔ 已闭环** |
| F-2 | **✔ 已闭环**（5 处全部改对，并与 `git show --stat` 双向印证） |
| F-3 | **✔ 已闭环**（且已改为滚动区间口径） |
| F-4 | **✔ 已闭环** |
| 未回归 | ✔ M-1～M-6、RC 12→13、两处新遗漏、append-only 纪律**均未被本轮返修破坏** |
| 引用校验 | `python scripts/verify_doc_citations.py` → **exit 0**（98 通过 / 0 失败） |
| 遗留 | 2 条**低危观察**（O-1a、O-1b，均不阻塞）；**未发现任何未标注的旧口径用法** |

## R2. F-1～F-4 逐条复核

### F-1（high）E13 行被空行切出 §3.2 表格 → **已闭环**

```text
table blocks: 15   blocks without separator: []          # 第一轮为 16 块且 1 块无分隔行
156 TEXT  ### 3.2 本窗口内再现的实例清单（E1–E13）
160 TABLE | ID | 实例 | 「机制存在」 | 「报告成功」 | 「无法生效」 | 强度 | 来源 |
161 TABLE |:--:|---|---|---|---|:--:|---|
162..173   E1 … E12（连续）
174 TABLE | **E13** | **`stuck_score` 可达 1.0 而同刻 `stuck_duration == 0.0`（观测层假绿）** …
175 BLANK
176 TEXT  **E13 离线仿真的命中 tick（自表内移出，内容未删）**：[149, 363, 577, …, 2931]
```

- 表格块 **L160–L174 连续、13 行数据（E1–E13）**，空行已移到 E13 **之后**（L175）；过长内容（命中 tick 列表）**移入表后 L176 说明段并注明「自表内移出，内容未删」** ⇒ **无静默删除**。
- 全文件 **15 个表格块全部带表头分隔行**（脚本化分类），F-1 的"唯一畸形块"已消失。
- 另核：`analysis` 中 **E1～E13 十三行全部存在**（逐行 grep 命中），标题 L156 为「E1–E13」，与「13 例」9 处表述一致。
- **判定：通过。**

### F-2（medium）行数 339/179 → 407/211 → **已闭环（5 处 + 口径自洽）**

| 位置 | 现值 | 复核 |
|---|---|---|
| `analysis:162`（E1 行） | `evo_liveness_guard.py`（**407 行** / 15,863 B） | ✔ |
| `analysis:340`（§8 M-4a） | guard **407 行** / 15,863 B + launcher **211 行** / 7,889 B | ✔ |
| `recommendations:771`（P2-3 行） | guard **407 行** / 15,863 B + launcher **211 行** / 7,889 B，并带「⚠️ **t7 更正**：原写 339 行 / 179 行」 | ✔ 留痕 |
| `recommendations:785`（B01 行） | guard **407 行** · launcher **211 行** | ✔ |
| `recommendations:972`（E-6 勘误行） | 「上文位置」列忠实引用 **写作 339 行 / 179 行**；「更正后」列给 **407 / 211** 并显式写 **339 → 407**、**179 → 211** | ✔ |
| `evidence:677`（口径勘误） | 「`+407 / +211` 是 `git show --stat` 新增行数；两文件在 `38c8bae` **新建** ⇒ 新增行数 == 文件总行数 = 407 行 / 211 行」 | ✔ |

**我的独立复算（双向印证）**：

```text
python: read().count('\n')      -> evo_liveness_guard.py 407 / 15,863 B ；evo_loop_launcher.sh 211 / 7,889 B
git show 38c8bae --numstat --   -> "407  0  fly64/scripts/evo_liveness_guard.py" / "211  0  fly64/scripts/evo_loop_launcher.sh"
git show 38c8bae --name-status  -> A  fly64/scripts/evo_liveness_guard.py ; A  fly64/scripts/evo_loop_launcher.sh
```

⇒ `A`（新增文件）+ 删除数 0 ⇒ **`--stat` 新增行数 == 文件总行数**，与 `wc -l` 完全一致，t7 的"双向印证"说明**成立**。
**其余提及 `339/179` 之处均已处于勘误上下文**（`analysis:339` 的 M-3 行引用的是 A4 的 12/16/18；`recommendations:972`、`evidence:677` 为更正行）⇒ 无"把 339/179 当当前值"的用法。
**判定：通过。**

### F-3（low）磁盘 134 GB → **已闭环**

```text
analysis:239 (B5)  →  `/tmp` = **≥134 GB（滚动值：13:19 实测 135 G、13:24 复测 136 G）**、3435 npz、根分区 78%（745G/1007G）
analysis:260 (C7)  →  磁盘 **≥134 GB（滚动；13:19 = 135 G / 13:24 = 136 G）/78%**
```

- 我 13:29 复测：`du -sh /tmp` = **136G**、`df -h /` = `746G/1007G 78%` ⇒ 与文档所记 13:24 的 136 G 一致（且 745G→746G 同步刷新）。
- **判定：通过**（并优于此前的单值写法）。

### F-4（low）records 86 vs 87 → **已闭环**

`evidence:697` 现写：

> ⚠️ **t7 记录数复核（2026-09-26 13:24:50 Windows / 13:24:58 WSL）**：**Windows 87 / WSL 87（md5 `d98c46f96e7d58128c5707e182ef4be2` 相同）**；**另有时点观测到 86 条**（过时读数，已作废——md5 逐字节相同即两侧必然同条数，故 87 为权威读数）。该文件**随运行时追加**，**任何引用都必须注明测量时刻**…

- 与我 13:19 的独立实测一致（WSL 87 / Windows 87、md5 相同）；`analysis:141` 同口径。
- 我 13:29 补充实测 `runtime/evolution_history.json` = **7,145 B**（13:29:19），仍落在文档声明的 **7,110–7,134 B** 滚动带附近 ⇒ 该文件的"滚动"性质进一步被证实（瞬时值可短暂超出带外，属预期）。
- **判定：通过**（"必须注明测量时刻"的纪律要求已写入文档，正是本轮问题的预防措施）。

## R3. 独立复现（重跑，确定性一致）

```text
memory.py: rate_threshold=0.008 / rate_stuck_s=3.0 / temporal_stuck_s=2.0 / assert count = 0
  225  stuck_score = max(t_score, f_score, r_score)
  229  self._stuck_duration += self._dt
  234  if self.disp_60s is not None and self.disp_60s > 500.0 and self._stuck_duration > 0.0:
  235      self._stuck_duration = max(0.0, self._stuck_duration - 1.0)

实验 A（泄放生效，disp_60s=600+(i%50)*10）：score==1.0 count = 14 ; all dur==0.0 = True ; ticks [299,499,699,899,1099,1299]
实验 B（对照，disp=None）            ：score==1.0 count = 14 ; first hit (tick,dur) = (299, 0.02)
```

与第一轮**逐值一致**（14 / 14 / 全 `dur==0.0`；对照组同 14 次但 `dur=0.02`）⇒ 根因链（三子分取 `max` + `rate` 子信号恒真 + `:234-235` 泄放抹零）在返修后**未发生任何漂移**。

## R4. append-only 与未回归核验

| 项 | 结果 |
|---|---|
| `recommendations` 条目 | `P*` **36** 行、`B*` **14** 行、新增 `E-*` **10** 行（t7 未删任何条目；勘误仅 §A.8） |
| `plan` 条目 | 建议表 **21** 个 `P*` 行（含既有 18 条 + 表格行）、`E-*` **6** 行，勘误仅在文末块 |
| M-1/M-2（A3 拆分、B3「未缓解」） | 未被触碰（`analysis:226/253/237/336` 原文仍在，含「原值 → 实测值」留痕） |
| M-3（四级口径 10/14/16/17 + 未恶化 + 12 来源） | 未被触碰（`analysis:228/339`） |
| M-4a/b/c（scripts 路径 / skills 锁 / E8 措辞） | 未被触碰（`analysis:162/340/169`） |
| M-5（E-1 勘误） | 未被触碰（`recommendations:967`、`plan:1040`） |
| M-6（`session-log-analysis` 附录 C + 十行写点表） | 未被触碰（`:379/396/403/430-442/451/534-544`） |
| RC 12→13 / RC-4=2 | 未被触碰（`analysis:16/17/174/178/192/195`） |
| 两处新遗漏（100644 / 两份历史） | 未被触碰（`analysis:343/344`、`evidence:687-689/696-698`、`recommendations:973`、`plan:1041/1043`） |
| 残留旧口径 | 5 份文档全部命中均在「原值/勘误/待更正」语境，**无未标注用法** |
| 引用校验 | **exit 0**，98/98 通过、0 失败 |

## R5. 低危观察（不构成返修要求）

| ID | 观察 | 建议（可延后/可不做） |
|---|---|---|
| **O-1a** | `recommendations:972`「上文位置」列现含**解释性文字**（「（**写作 339 行 / 179 行**）」），而非 L771/L785 的原样引用 | 该列语义是"引用位置"，插入说明虽不影响"原表述"列的忠实性，但严格来说属于对勘误块定位列的编辑；后续若再改，建议把解释性文字只放「原表述/备注」列 |
| **O-1b** | `recommendations:972` 与 `evidence:677` 把 339/179 归因为「`Measure-Object -Line` 的漏计口径」 | **属实的发现（我第一轮判断错误，此处更正）**：我在本机重跑 `Get-Content <file> \| Measure-Object -Line` 得到 **launcher = 179、guard = 339** —— 与 t5 原值**逐值一致**，证明 339/179 **是 `Measure-Object -Line` 的可复现产物**（该 cmdlet 与 `wc -l` / `read().count('\n')` 不一致：launcher 211 vs 179、guard 407 vs 339；两文件差值同为 11，具体机制属 PowerShell 行计数语义，不影响结论）。⇒ t7 的归因**成立**，可作为"错误口径复现证据"引用；仅建议补上实测命令与两个对照值，使读者不必再猜。 |

## R6. 复审判定

> **verdict = pass**：t7 的返修**完整闭合 F-1（阻塞）与 F-2/F-3/F-4**，未触碰任何已通过项，未破坏 append-only 结构；核心结论（stuck_score 根因链）在返修后**逐值复现不变**；引用校验 exit 0。
> 遗留 O-1a/O-1b 为**低危文档卫生**问题，**不阻塞验收**，可在后续任何一次文档整理中顺手处理。

*（本节由 t8 复审者追加；不修改上文第一轮审查的判定与历史记录。）*

