# A2 — 顽疾根因分析：持续性问题的证据链

> 任务：t2 [A2] · 执行者 rootcause-analyst · attempt 1 · **rev 3（口径收口）**
> 方法：11 个唯一 session 全量导出日志（`.tmp/sessions_v3/`，16 个重导出目录 / 351 MB）全文检索 + 工作区代码/工件/提交逐行取证。
> 取证脚本：`scripts/_a2_extract_v3.py`（权威语料真实用户消息提取，与 `scripts/analyze_sessions_v3.py` 共用同一个 11-session `CANONICAL` 去重表）、`scripts/_a2_extract_user_msgs.py`、`scripts/_a2_inventory.py`（早期口径，仅供对照）。中间产物在 `.tmp/a2/`。
> 代码基线：`git HEAD = cf2f472`（README 全面更新，Brain v2.23.12 / Skill v3.5.0）。

---

## 0. 证据基线与可复现口径

| 项 | 值 | 取证方式 |
|---|---|---|
| 唯一 session | **11 个**（`1f8fbe04 / 27ed0979 / 38542b1c / 71c21f6d / 90dd512b / 99cab60f / b2eeed98 / d983cef5 / ed4b8026 / f953d3fd / fdb47617`） | `.tmp/sessions_v3/`，去重表与 `scripts/analyze_sessions_v3.py:29-41` 的 `CANONICAL` 一致 |
| 语料规模 | 16 个重导出目录 / **351.2 MB**（`38542b1c`=17 jsonl/63.7MB，`f953d3fd`=59 jsonl/122.6MB） | `Get-ChildItem .tmp\sessions_v3 -Recurse -Filter *.jsonl \| Measure-Object Length -Sum` |
| 真实用户提问（`source.kind=user`，剔除 AgentTeams 派发/入队通知 + 注入快照） | **874 条**（团队权威口径，A0/A1/A4 一致） | `scripts/_a2_extract_v3.py` → `.tmp/a2/v3_index.txt`、`.tmp/a2/v3_merged_user_msgs.txt`；逐 session 分解见下表 |
| 代码基线 | `cf2f472` / Brain **2.23.12** / Skill **3.5.0** | `fly64/fly64/main.py:39-40` |
| 契约守卫套件实跑 | `test_strategy_key_contract` + `test_coach_contract` + `test_coach_dopamine` + `test_consult_context_pos_y` + `test_strategy_update_endpoint` + `test_action_entropy` = **58 项**，另 `test_version_consistency` + `test_rule17_versions` = 15 项 | 实跑 **57 passed / 1 failed**（§1.2 D12）与 **13 passed / 2 failed**（§1.2 D10） |

> **口径说明（本文件 rev 1 → rev 3 修订记录）**：本报告 rev 1 误将 `export logs/_extracted_*/` 当作权威语料 —— 那是**旧的、不完整**的解包（仅 9 个 session；`_extracted_38542b1c` 与 `_extracted_f953d3fd` 目录各 0 文件）。权威语料是 captain 本次从 16 个 zip 全量重新解包的 `.tmp/sessions_v3/`（11 个唯一 session / 351 MB），包含 rev 1 完全缺失的 **S3 视觉系统深度分析（209 问）** 与 **S10 FlyGym 集成 + Bridge（356 问）**。rev 2 及之后的计数、时间线与引用均以 `.tmp/sessions_v3/` 为准（rev 2 = 第一次复核修订；rev 3 = 874/870 裁决收口，明细见附录 C）。
>
> **真实提问数：951 → 874（最终裁定；870 已废弃）**。rev 2 首稿的 951 含 **89 条 AgentTeams 协议噪声**中未被剔除的部分 —— 协议噪声以 `source.kind == "user"` 注入，只按 `source.kind` 判定剔不掉，必须额外按内容剔除：
> - 权威复算命令：`rg -a -c "AgentTeams automatic task assignment|You have joined the team" .tmp/sessions_v3`
> - **最终链（captain 裁定 + 本报告独立复算确认）：基数为 963、协议噪声 89、真实提问 874。** 963 是 **11 个 canonical 目录内**的 `kind=user` 实测数（S7 取**完整导出** `b2eeed98 (1)`）；协议噪声 89 条全部位于我的 19 类注入标记之外（overlap = 0），我的标记另剔除 8 条非协议注入（`99cab60f` 5 + `71c21f6d` 3）。
> - **rev 2 曾提出的「963 未去重 / 故为 870」已废弃。** captain 用 `scripts/_captain_resolve_s7.py` 对 S7 两个导出做**消息级集合比对**：legacy（无后缀）59 条去重 58、`(1)` 63 条去重 62、`only in legacy = 0`、`union unique = 62` ⇒ **`(1)` 是 legacy 的严格超集**。我独立复算确认：S7 legacy 59 条 / `(1)` 63 条 / 差额 **4** 条，且两者协议噪声均为 **0**，故该 4 条**全为真实提问**。**只有当基线取"不完整的 legacy 导出"时才会得到 870** —— 而 `analyze_sessions_v3.py` 的 `CANONICAL` 表恰为 S7 选了 legacy，这正是我判断依据需要修正之处。
> - 那 4 条是 **09-21「探索三重死锁」现场记录**（`cx_novelty_dir 仍在 0.0 … cells 全面陈腐 1524 次/格`）—— 正是 `5c86272`（200t burst + waste_penalty）所针对的战役，也是本报告 §3.4 的实证来源。取 legacy 会**整场漏掉**这场战役。
> - **净差额表述（A4 采用，已同步 A0 §6.2）**：**85 = 89 − 4**。含义是"相对 **legacy-S7 口径**（`kind=user` = 959）而言，净剔除 85 条才到 874"：剔除 89 条协议噪声、再把 4 条本被 legacy 漏掉的真实提问补回。两种基数下的等价关系：`959 − 89 = 870`（legacy-S7）**+ 4**（S7 超集补回的探索三重死锁记录）`= 874`（完整导出）。
> - **不得改回 959，870 已废弃。**

会话时间窗与逐 session 分解（列含义：`kind=user` = 该 session 在**完整导出**下的 `source.kind == "user"` 记录数；`协议噪声` = 命中原命令两类派发/入队文本的条数；**真实提问** = 两者相减。另：我的 19 类注入快照标记会额外剔除 **8 条**非协议注入（`99cab60f` 5 + `71c21f6d` 3，与 89 条协议噪声 **overlap = 0**），该 8 条已在 rev 2 首稿的 951 中扣除，明细见脚本）：

| session | 标签 | `kind=user` | 协议噪声 | **真实提问** | 时间窗 |
|---|---|---:|---:|---:|---|
| `f953d3fd` | S10 FlyGym 集成 + Bridge | 356 | 56 | **300** | 09-10 18:44 → 09-18 22:44 |
| `38542b1c` | S3 视觉系统深度分析 | 209 | 11 | **198** | 09-13 19:08 → 09-20 09:03 |
| `1f8fbe04` | S1 跨领域能力分析 | 94 | 14 | **80** | 09-15 19:06 → 09-18 23:13 |
| `d983cef5` | S8 神经活动可视化 | 66 | 0 | **66** | 09-13 12:33 → 09-18 23:12 |
| `90dd512b` | S4 EVO 进化系统 | 64 | 0 | **64** | 09-14 23:02 → 09-18 22:44 |
| `b2eeed98` | S7 监控仪表板布局 | **63** | 0 | **63** | 09-14 23:26 → 09-19 12:40 |
| `27ed0979` | S2 Mario 运动能力扩展 | 51 | 0 | **51** | 09-16 14:01 → 09-18 23:11 |
| `99cab60f` | S5 脑模型启动 + SM64 | 40 | 5 | **35** | 09-19 00:38 → **09-22 18:12** |
| `fdb47617` | S11 技术文档生成 | 10 | 0 | **10** | 09-16 17:35 → 09-17 18:24 |
| `71c21f6d` | S12 AgentTeams 执行 | 7 | 3 | **4** | 09-20 23:37 → 09-21 00:14 |
| `ed4b8026` | S9 日志分析执行计划 | 3 | 0 | **3** | 09-20 20:49 → 09-20 21:56 |
| **合计** | | **963** | **89** | **874** | **09-10 18:44 → 09-22 18:12** |

> 表注 1（S7 基数的决定性依据）：S7 有两个导出，captain 的 `scripts/_captain_resolve_s7.py` 做**消息级集合比对** —— legacy（无后缀）59 / `(1)` 63 / `only in legacy = 0` / `union = 62` ⇒ **`(1)` 严格超集**，故本表 S7 取 **63**（含 4 条 09-21 探索三重死锁现场记录）。取 legacy 的 59 会得到 959 基数与 870 结论，**已废弃**。
> 表注 2（分布）：协议噪声集中在 5 个 session（`f953d3fd` 56 / `1f8fbe04` 14 / `38542b1c` 11 / `99cab60f` 5 / `71c21f6d` 3），与"多成员团队在会话内被批量创建/派发"的分布完全一致 —— 侧面印证 89 条确为**插件派发产物**而非人的提问（详见 §2.3：正是这些派发消息下达后成员从未 spawn）。

**口径修订（rev 1 → rev 3 全部错误与废弃结论，均由 captain 复核指出）**

1. **Coach 抱怨链不是止于 09-18，而是 09-13 18:42 → 09-22 18:12**（共 **73 条** coach 相关 human 消息，跨 8 个 session）。最后一条正是 §1.2 D7/D8 所分析缺陷的**用户侧原始诉求**：`09-22 18:12 [99cab60f seq=2753]`「修复 _inject/读取方的键名归一化——写入前清除点号前缀（这是一次真正的契约审计发现，符合 RULE-19 零容忍）  Coach 与 EVO 写同一文件会产生互相覆盖——建议 EVO 写入前保留 coach 段（_load_active_strategy 已做合并，但 coach 写入时可能覆盖 EVO 值）」→ 直接促成了 `879d983` / EVO-072。rev 1 把时间线画到 09-18，等于**漏掉了自己结论的提出者**。
2. **「大部分动作没有尝试」不是二次引用**：rev 1 检索串漏了「有」字（`大部分动作没尝试`）故零命中；含「有」的原文在语料中确实存在，权威出处为 **`09-22 17:09 [99cab60f seq=2463]`** 的**用户原话**：「几乎没有波动，分析主要原因，目前运动动作过于单调，运动动作为什么大部分没有尝试」（同 session `seq=2506` 另有复述「修复问题 为什么"大部分动作没有尝试"」）。A1 报告的转述仅属措辞偏差，不是虚构。
3. **分析范围恢复为 11 session**：rev 1 的「9 session / 342 提问」源于读取了空的残留目录，已废弃。§3.1 及其他章节的比例/结论已基于 11 session 语料复核。
4. **提问总数对齐团队权威口径 874（基数为 963）**：rev 2 首稿的 951 与中途提出的 870 都不采用。最终链为 **963（11 个 canonical 目录、S7 取完整导出 `b2eeed98 (1)` 的 `kind=user` 数）− 89（AgentTeams 派发/入队通知）= 874**。协议噪声以 `source.kind == "user"` 注入，仅按 `source.kind` 判定剔不掉，必须额外按内容剔除。本报告对外统一采用 **874**，与 A0（rev 2）/A1/A4 一致；**不得改回 959，870 亦已废弃**。推导、S7 超集证据与"净差额 85"见上方口径说明。
5. **rev 2 的「963 未去重 / 870」为废弃结论**：该判断把 S7 的**不完整 legacy 导出**（59 条）当作基线，因而丢掉了 4 条 **09-21 探索三重死锁**现场记录。captain 的 S7 消息级超集比对（`only in legacy = 0`、`union = 62`）在我独立复算下成立（S7 legacy 59 / `(1)` 63 / 差额 4，两者协议噪声均为 0），故 **874 为正确值**。这 4 条正是 §3.4 所分析战役的原始记录 —— 教训与顽疾 1 同源：**用不完整证据源会静默丢掉整场战役**。

---

# 顽疾 1 — Coach 建议不生效（六段链路）

## 1.1 症状（用户原文引用 + 出现次数与位置）

**共 73 条** coach 相关 human 消息（权威语料 `.tmp/sessions_v3/`，完整清单见 `.tmp/a2/_v3_coach.txt`）。下表列出其中**结构最关键的 40 条**，按时间排序（`seq` 为该 session 内序号，可直接在 `.tmp/sessions_v3/<session>/**.jsonl` 中定位）：

| # | 时间 | session | seq | 用户原文 | 命中的链路段 |
|---|---|---|---|---|---|
| 1 | **09-13 18:42** | d983cef5 | 63082 | "超出果蝇大脑神经元能力的属于训练教官的训练能力，也就是 llm 语义理解属于训练的教学只是能力，需要和果蝇神经元的自我具备能力区分" | ⑥ 教官职责定位 |
| 2 | 09-13 20:36 | f953d3fd | 361687 | "使用 skill 修复发现的问题并更新 skill，同时下一步分析当前状态下截屏分析如何寻求教练的帮助" | ①③ |
| 3 | 09-13 21:21 | f953d3fd | 363729 | "/agent-teams … **"寻求教练帮助"机制设计** … 问题本质：钥匙门是**不可自主解决**的问题（需先找到钥匙）——果蝇脑再进化也无法开门" | ① 触发（兜底定位） |
| 4 | 09-14 08:36 | f953d3fd | 384183 | "对于这类问题增加游戏截屏提交给 glm-5.3-flash 模型进行 OCR 识别，基于识别给出下一步建议，这个属于教练求助场景…截图识别。`build_help_snapshot()`" | ③ 截屏（首次提出） |
| 5 | 09-14 09:54 | f953d3fd | 393125 | "✅ `/coach_advice.json` 路由生效（当前无建议——正确，因无 stuck>120s 触发）不解决当前问题，需要解决当前问题" | ① 触发 |
| 6 | 09-14 14:31 | 38542b1c | 138070 | "LLM Coach Advice 布局与当前 health 组件布局重叠，调整组件布局确保布局合理充分利用布局，不重叠，不占用其他组件显示为 止" | ⑤ 展示 |
| 7 | 09-14 20:43 | d983cef5 | 212503 | `🤖 LLM Coach Advice · glm-5.3-flash 别再原地小碎步转圈了！先猛退一步拉开距离，再大胆选个新方向全速冲出去，哪怕走远路也比原地空转强。` | ② 已产出建议 |
| 8 | 09-14 20:57 | d983cef5 | 213019 | 同上 + **"会影响到实际动作吗"** | ⑥ 行为 |
| 9 | 09-14 21:21 | d983cef5 | 221388 | **"执行skills分析为什么没有识别出交互提示，为什么没有文GLM 教练提示建议"** | ①③ |
| 10 | 09-14 22:45 | f953d3fd | 422202 | **"分析 🤖 LLM Coach Advice 为什么没生效"** | ⑤⑥ |
| 11 | 09-15 15:35 | f953d3fd | 442861 | "分析GLM教练策略是否做了SM64游戏截屏的OCR识别，如果有应该将识别内容在GLM 教练策略里做描述，教练看到了什么" | ③ 截屏（`what_i_see` 需求来源） |
| 12 | 09-15 15:37 | f953d3fd | 444610 | "注意教练看到的图片需要保存在本地便于后续查询" | ③ 截屏留痕（`coach_frames` 需求来源） |
| 13 | 09-15 16:37 | 38542b1c | 402462 | "分析当前运动和监控状态，GLM 教练是否给出具体建议为什么没有执行，脑模型是否存在缺陷" | ④⑤⑥ |
| 14 | 09-15 23:42 | b2eeed98 | 130277 | **"进一步分析监控中coach snapshot为什么没有生成缩略图"** | ③ 截屏 |
| 15 | 09-16 11:25 | b2eeed98 | 150382 | **"检查coach snapshot功能是否正常，和目前运动状态"** | ③ |
| 16 | 09-16 20:22 | 90dd512b | 192741 | **"分析如何提高进化能力如何完善教练能力提升进化能力"** | 全局 |
| 17 | 09-17 01:34 | 1f8fbe04 | 106026 | **"当前运动状判断为什么么有coach建议"** | ① 触发 |
| 18 | 09-17 08:11 | 90dd512b | 308222 | **"检查状态问题，为什么不动 coach snapshot为什么不截屏，coach 为什么不捕获给出建议，修复这个问题"** | ①②③ |
| 19 | 09-17 10:19 | 38542b1c | 593255 | **"目前发现snapshot的图片不是完整游戏帧的内容是部分，分析原因，不完整的截图让Coach无法完整了解当前场景…同时要保证图片尺寸变化不影响显示，存储转换和llm提交"** | ③ 截屏 |
| 20 | 09-17 11:06 | 38542b1c | 608903 | "验证当前coach模式是否截图能力是最新完整截图，coach建议是否识别，llm建议脑模型是否可执行" | ③⑤⑥ |
| 21 | 09-17 11:40 | 27ed0979 | 186591 | **"当前coach截屏与实际游戏截屏还是不一致，snapshot只是游戏屏幕一部分，为什么这个问题依然存在"** | ③ |
| 22 | 09-17 14:46 | 27ed0979 | 211251 | **"分析当前运动状态及存在问题为什么没有解决没有触发coach"** | ① |
| 23 | 09-17 16:18 | 90dd512b | 377048 | **"需要更细的分工，本能化绑定是本轮重点，同时确保 coach 建议真正影响 behavior"** | ⑥ |
| 24 | 09-17 18:31 | 1f8fbe04 | 136771 | **"coach建议是否被执行生效"** | ④⑤⑥ |
| 25 | 09-17 20:20 | 27ed0979 | 261207 | **"coach建议"** | — |
| 26 | 09-17 20:24 | 27ed0979 | 263983 | **"coach 模型建议为什么没生效"** | ⑤⑥ |
| 27 | **09-17 20:45** | 38542b1c | 677321 | **"LLM coach建议是什么，为什么不生效"** | ⑤⑥ |
| 28 | 09-17 20:48 | 38542b1c | 679098 | **"LLM coach建议是什么，显示建议内容，为什么不生效"** | ⑤⑥ |
| 29 | 09-17 20:50 | 38542b1c | 679388 | "执行任务 coach-pipeline-audit" | 全链路审计（→ `coach-pipeline-audit` 团队） |
| 30 | 09-17 21:28 | 27ed0979 | 273188 | **"coach 建议可影响多巴胺，分析目前是否支持"** | ⑥ 奖惩 |
| 31 | 09-17 21:30 | 27ed0979 | 274093 | **"需要，教练建议应该对训练起重要作用，修复实施后增加测试案例验证"** | ⑥ |
| 32 | 09-18 15:50 | 1f8fbe04 | 146108 | **"coach建议行为是否有奖惩机制反馈，和生效"** | ⑥ |
| 33 | 09-18 16:03 | 38542b1c | 682761 | "增强运动检测异常能，对于处理方式确认是否有多巴胺奖励机制，如无法处理则提交给coach处理" | ⑥ 兜底分工 |
| 34 | 09-18 17:29 | 1f8fbe04 | 149661 | **"运动检查，分析当前状态coach为什么没有截屏生效"** | ③ |
| 35 | 09-18 23:06 | 38542b1c | 690983 | "解决方案 `capture_frame()` 当前优先级：前向面（128×128）→ screen.json（320×240）…要让教练看到清晰画面，确认 `capture_frame()` 当前用的是前向面还是游戏帧" | ③（→ `d646613` 的直接由来） |
| 36 | 09-19 20:57 | 38542b1c | 698314 | "运动状态检查，分析当前状态为什么coach没有建议，目前游戏截图与视觉输入差异比较" | ①③ |
| 37 | 09-19 22:34 | 38542b1c | 701243 | **"检查为很么coach snapshot没有截图成功，监控视觉输入和游戏显示不一致"** | ③ |
| 38 | 09-19 22:48 | 38542b1c | 702779 | "截取当前运动图片触发coach" | ① 手动触发 |
| 39 | **09-22 18:01** | 99cab60f | 2689 | **"当前 jump_rate=0.46 是写死的吗，那些参数是写死的，如何动态根据奖惩机制和记忆里优化参数或coach的建议调整"** | ⑥ + §3 动作参数化 |
| 40 | **09-22 18:12** | 99cab60f | 2753 | **"修复 _inject/读取方的键名归一化——写入前清除点号前缀（这是一次真正的契约审计发现，符合 RULE-19 零容忍）　Coach 与 EVO 写同一文件会产生互相覆盖——建议 EVO 写入前保留 coach 段（_load_active_strategy 已做合并，但 coach 写入时可能覆盖 EVO 值）"** | ④⑤（→ `879d983` / EVO-072） |

出现次数：**73 条**（上表摘列 40 条）；覆盖 **8 个 session**；时间跨度 **09-13 18:42 → 09-22 18:12（10 个自然日）**。
顶点症状（最尖锐的四句）：**"coach 模型建议为什么没生效"**（09-17 20:24）、**"LLM coach建议是什么，为什么不生效"**（09-17 20:45）、**"会影响到实际动作吗"**（09-14 20:57），以及收尾的 **"Coach 与 EVO 写同一文件会产生互相覆盖"**（09-22 18:12）。

> **注意收尾那条的份量**：用户在 09-22 18:12 **亲手诊断出了本报告 §1.2 D7/D8 的两个缺陷**（点号死键、coach 覆盖 EVO），而 `879d983` 在 **09-22 18:22**（10 分钟后）提交。这说明：**这条最长的顽疾链最终不是由代码审计终结的，而是由用户反复追问 10 天后自己给出的定位闭合的** —— 这正是 rev 1 把它误记为"止于 09-18"而丢失的关键事实。

## 1.2 六段链路：每段的当前实现、已被证明的缺陷、证据

链路：`触发 → LLM 调用 → 截屏 → 写盘 → 键名加载 → 行为/奖惩`

### ① 触发段 — `plugin/runner.py:check_help_needed`

**现状**（`fly64/plugin/runner.py:148-261`）：四路触发条件
- `help.json.help_reason` 非空（脑侧 L2/L2a 主动写）
- `primitive_ineffective`：CPG 连续 3 次完成且 `disp_60s < 30`
- `unsolvable_stuck`：`stuck > 60s AND anomaly != idle AND (no_reflex OR reflex_ineffective)`
- `multi_signal_stuck`：加权分 ≥ 0.60

**缺陷 D1（已修，且是"杀手级"）— 求助路径 100% NameError。**
`scripts/m8_add_posy_to_consult.py` 用 `str.replace` 往三处 consult context 插 `"pos_y": pos_y_ctx`，但锚点字符串（12 空格缩进的 `stuck = float(...)`）与实际源码（8 空格缩进，且中间隔着 `if self._prim_zero_run >= 3:` 块）不匹配 —— `str.replace` 不匹配时**静默成功、退出码 0**。结果 `pos_y_ctx` 从未定义，而 `reflex_ineffective_stuck` / `unsolvable_stuck` / `multi_signal_stuck` **三条路径全部引用它**。

> 证据：`fly64/plugin/runner.py:190-202` 保留了这个"考古现场"注释 ——
> `"the definition-insertion replace silently failed to match ... The result was a NameError on every help-escalation path — i.e. the coach would crash exactly when the fly is stuck."`
> 修复：commit **`3a0b993`**（EVO-062），并新增 `tests/test_consult_context_pos_y.py` 11 例（含"定义先于首次使用"静态守卫，且跳过注释行）。

这是"① 触发"段与用户质问（表中 #17 `09-17 01:34`、#18 `09-17 08:11`、#22 `09-17 14:46`、#36 `09-19 20:57`）的直接对应：**教练恰好在它唯一被需要的时刻（卡死）崩溃**。

**缺陷 D2（未修 / 结构性）— 触发判据把"高速振荡"误判为"有进展"。**
`fly64/fly64/main.py:1222-1224` 的 L2a 触发要求：
```python
_stuck_no_progress = (memory_ctrl.stuck_score >= 0.8
                      and memory_ctrl.spatial.coverage_rate < 0.05
                      and memory_ctrl.stuck_duration > 5.0)
```
`coverage_rate` 的单位是 **"覆盖率百分点 / 1000 ticks"**（`fly64/fly64/memory.py:707-717`），阈值 `0.05`。
而用户实测到的形态是 `中位速度 316u/s 但 60s 位移仅 28u`、`loop 0.93`、`coverage_rate = 1.14`（09-18 16:18，seq=331573）。`1.14 ≫ 0.05` ⇒ **L2a 永不触发**。
同类门槛还有两处：
- `_detect_oscillating` 的位移闸门：`disp_60s > 300 → return False`（`memory.py:1152-1153`）
- `_detect_micro_loop` 的 Tier-2：`disp_60s > 300 and loop_score < 0.8 → return False`（`memory.py:1184-1185`）

于是形成用户 09-17 亲口报告的自相矛盾：
> `"马里奥再次出现编织特征：stuck=54s 且持续上升、loop_score=0.99、escape=True、health 掉到 0.62——但 5 轮内 findings 全空。原因：micro_loop_weave 要求 anomaly_state == "micro_loop" 而脑报告 idle"`（90dd512b，seq=17557）

**这不是阈值没调好，而是判据之间互相抵消**：`loop_score≈1.0`（"原地编织"的充分证据）被 `anomaly=idle` 挡在门外，而 `anomaly` 之所以是 idle，正是因为同一条位移闸门。用户自己在 09-17 给出了正确修法建议（把 pattern 条件放宽为 `loop_score ≥ 0.95 AND escape AND stuck ≥ 45`），**该建议未落地**。

**当前可复现验证**（本次实测）：用活体形态的合成快照调用真实 `check_help_needed`：
```
snapshot.memory = {stuck_duration: 54.2, anomaly_state: 'idle', health_score: 0.62,
                   reflex_active: True, reflex_ineffective: False, disp_60s: 2100.0}
→ check_help_needed(...) == None      # 教练不触发
把 anomaly_state 改成 'oscillating' 后同样不触发（reflex_ineffective=False 且 reflex=-active）
```
即 **`stuck=54s` + `loop≈0.99` 的高速振荡不会让教练被叫醒**，与用户 09-17 的观测完全一致。

### ② LLM 调用段 — `plugin/llm_consult.py`

**现状**：双传输（`http` OpenAI 兼容 / `subagent` 文件握手，120s 硬超时），失败降级 `local_diagnosis`。

**缺陷 D3（已修）— 裸 RGB 被标成 `data:image/png` ⇒ GLM 400。**
`build_consult_request` 直接把共享内存里的裸 RGB 字节 base64 塞进 `"image": "data:image/png;base64,"+...`（`fly64/plugin/main.py`→`llm_consult.py:165-172` 现已是转换后版本）。GLM 解码失败返回 HTTP 400，而 `_dispatch_http` 只抛裸 `"HTTP 400"`，**根因被掩盖一轮**。
> 证据：`agent.md:677` 明文记录 —— `"HTTP 400 根修：根因是 main.py frame_to_b64 上送的是裸 RGB 字节，而请求体标注 data:image/png ——GLM 解码失败回 400"`；修复引入纯 stdlib PNG 编码器 `raw_rgb_b64_to_png_b64()`，并让 `_dispatch_http` 透出 API 错误体（现见 `llm_consult.py:369-380`）。

**缺陷 D4（未修 / 结构）— 教练可用旋钮与实际行为空间严重不对等。**
`SECTION_SPECS`（`fly64/plugin/llm_consult.py:110-149`）**只向 GLM 宣传 4 个可调键**：
`fallen_recovery.mode`、`exploration.bold_explore_stuck_s`、`exploration.turn_bias`、`escape.stuck_threshold_s`。
而行为侧实际消费的键（`main.py:1291-1458` + `brain_tunable_params.json` 39 项）远多于此。
EVO-066 的审计结论把这件事量化过：
> `"brain_tunable_params.json 向操作面板宣传 21 个可调参数，其中 14 个在整个 fly64/ 与 plugin/ 源码中零出现 ... 它们是先于实现写下的愿景名"`

即：**教练能看见的问题（截图里的振荡）与它能表达的处置手段（4 个旋钮）之间不匹配**；教练写"转向/速度/是否跳跃/目标位置"（`PROMPT_TEMPLATE:88-99`），但落地的只有 `turn_bias`（一个 0-1 的比例）。用户 #2"会影响到实际动作吗"的答案是"只能影响 4 个旋钮中的一部分"。

### ③ 截屏段 — 三重独立缺陷（全部已修，但遗留失效条件）

| 子缺陷 | 症状 | 根因（代码级） | 修复 |
|---|---|---|---|
| D5a 缩略图永不显示 | 用户问"为什么没有生成缩略图"（#4） | 后端 `frame_b64`/`screen_b64` 是**裸 RGB 字节串**，仪表板却加 `data:image/png` 前缀 → 浏览器静默解码失败 | commit **`2da6990`**：新增 `snapshotDataUri()`（raw RGB → canvas → `toDataURL`，PNG magic 直通） |
| D5b 缩略图倒置 | 图像上下颠倒 | `glReadPixels` 为 bottom-up；cubemap 路径显式翻行，R21 screen 路径未翻 | commit **`d9f006d`**：`snapshotDataUri` 增 `flipY` |
| D5c 教练看到的不是 320×240 游戏画面 | 用户问"snapshot 只是游戏屏幕一部分"（#9） | `capture_frame()` **优先返回 128×128 cubemap 正面**，320×240 `screen.json` 永不到达 | commit **`d646613`**：`capture_frame()` 改为优先 `/screen.json`（见 `runner.py:263-277`） |
| D5d 面板裁切导致"看起来没有缩略图" | 用户反复问（#5） | 遗留 `max-height/overflow` 裁切（200px 面板 / 118px、150px body），折叠无法展开；help/coach/strategy 折叠列塌进 100px 标签列 | commit **`6d37c04`** |

**缺陷 D6（未修 / 语义层，"截屏与实际不符"的真正残留）— 教练看的是 5–15 秒前的画面。**
- `screen.json` / `help.json` 的刷新节拍是 **每 60 tick**（`main.py:1903`：`if model.step_count % 60 == 5`，20fps ⇒ ~3s；`main.py:2604-2607` 同节拍）。
- `runner.save_consult_frame()` 落盘的是 **"教练即将看到的那一帧"**（`runner.py:355-360`），即它把"延时"固化进工件，因此**事后无法用 coach_frames 反证延时**。
- 教练每 10s 跑一轮（`PluginRunner.interval`），一次 consult 含 LLM 往返（subagent 传输硬超时 120s）。

⇒ 用户 #9 的"snapshot 与实际游戏截屏还是不一致"在**时序语义**上从未被修复：帧是同期的，**场景**不是。而 `save_consult_frame` 的"照它将要看的存"这一设计，主动消灭了唯一能审计该偏差的证据。

**实测缺口证据**：`fly64/runtime/coach_frames/` **目录存在且为空（0 个文件）** —— 即当前仓库状态下，没有任何一次教练截图被留存。结合 §1.3 的语料统计，说明教练咨询在最近一段时间**根本没有发生**。

### ④ 写盘段 — `plugin/strategy_writer.py` / `skills/active_strategy.json`

**缺陷 D7（已修）— Coach 整体覆盖 EVO 的策略文件。**
`write_strategy` 原为 `payload = dict(strategy or {})` 整体覆盖：教练每写一次，就**擦掉 `__generation` 与教练未提及的全部进化参数**，静默重置 Phase 6 搜索。
> 修复 commit **`879d983`**（EVO-072）：改为与磁盘现有内容 **逐 section 合并**（`fly64/plugin/strategy_writer.py:60-80`，`merged[sec] = {**merged[sec], **body}`，coach 键胜出、EVO 键保留）。

**缺陷 D8（未修 / 仍在持续退化）— 点号死键正在被 EVO 反复"再生"。**
活体策略文件 `fly64/skills/active_strategy.json` **今天仍然带着 5 个点号死键**（实测原文）：

```json
"exploration": {
    "escape.commit_ticks": 125.04821717847143,
    "escape.forward_accum_max": 0.2066931309445445,
    "escape.forward_accum_step": 0.015757426446775843,
    "escape.commit_reinforce": 0.1820265798466096,
    "escape.commit_suppress": 0.11829571149170438,
    "turn_bias": 0.25,
    ...
},
"__generation": 152,
"escape": { "commit_ticks": 50, "forward_accum_max": 0.5, ... }
```

三点结论：
1. **EVO 仍在往 `exploration` 段写 `escape.*` 前缀键**（`__generation = 152` 说明 Phase 6 已跑到第 152 代）。`evolution_skill.py` 的 `_inject` 走 `param_paths` 扁平映射，导致顶层 section 与点号键**同时存在**。
2. EVO-072 的迁移**只在读取端**（`main.py:1280-1290` 热加载时归一化、`evolution_skill.py:_load_active_strategy`）执行，**文件本体没有被修正**，因此每次热加载都要再做一次"搬运+删除"，死键随后又被写回。
3. 因此 **`commit_reinforce` / `commit_suppress` / `forward_accum_step` / `breakout_forward_bias` 这 4 个键在 `escape` 段里读到的始终是硬编码默认值**（`main.py:1332-1340` 读 `_esc.get(...)`，而真值被关在 `_expl["escape.commit_*"]` 里），与 commit `ea509a9` 声称"已修"的状态**不一致**。

⇒ 这正是用户反复质问的**"修复了但问题依然存在"的机制本体**：修的是读取端，写端每 152 代重复制造同一个死键。

### ⑤ 键名加载段 — `fly64/fly64/main.py:load_active_strategy`

**缺陷 D9（已修，且是最致命的一段）— 兄弟 section 全被丢弃。**
`load_active_strategy` 原先只返回 `fallen_recovery` 相关字段；调用方 `_active_strategy.get("exploration"/"escape"/"command")` **永远得到 `{}`**，于是每一个教练调参、每一个 BrainMutator 进化值都静默回落到硬编码默认值。
> 证据：commit **`d35e646`** 的提交信息原文 ——
> `"previously the caller always got {} and every coach-tuned / BrainMutator-evolved parameter silently fell back to hardcoded defaults (GLM advice reached the file but never reached behavior)"`
> 修复：`main.py:875-886` 增加 `for key in ("exploration","escape","command","dopamine")` 透传；并新增 `tests/test_strategy_passthrough.py`。

同族第二例（EVO-062，commit **`3a0b993`**）：操作面板 POST 的 id 是点号路径 `{"escape.commit_ticks": 125}`，`do_POST` 却写成**字面顶层键** `cur["escape.commit_ticks"]=125` —— 面板显示 ✓、接口返回 `{"status":"ok"}`、行为零变化。修复：`main.py:781-828` 的 `apply_strategy_update()` 展开点号路径，并**上报 `applied`/`rejected`**，让死写可见。

**缺陷 D10（未修 / 治理层）— "三处同步"规则本身失效。**
commit `5c86272` 把 skill 版本推到 **3.5.0**，但：
- `fly64/skills/evolution_skill.py:40` 的 `SKILL_VERSION = "3.4.2"`（未同步）
- `fly64/skills/evolution_history.json` 的 `canonical_versions = {brain: "2.23.11", skill: "3.4.2", as_of: 2026-09-18T01:08}`（两条都旧）
- **`EVO-072` 在 `evolution_history.json` 中不存在**（最大 id 为 EVO-071；`879d983` 的提交信息却声称已按规则记录）
- 且 `skills.md` 徽章仍是 **2.23.11**，与 `main.py:39` 的 **2.23.12** 不一致

本地实跑证据：
```
$ python -m pytest fly64/tests/test_version_consistency.py fly64/tests/test_rule17_versions.py -q
FAILED test_version_consistency.py::TestVersionConsistency::test_main_py_is_expected
FAILED test_version_consistency.py::TestVersionConsistency::test_all_three_sources_agree
    AssertionError: skills.md badge '2.23.11' != main.py '2.23.12'
2 failed, 13 passed in 0.36s
```

即 **"版本契约"守卫真的能抓到问题，但没有人跑它**；`--history-check` 存在（`evolution_skill.py:2595/2640`）却没有被 commit 流程强制。这属于用户长期抱怨的同一族：**机制存在、报告成功、无法生效**——这次连"报告成功"都是靠提交信息自己声明的。

### ⑥ 行为 / 奖惩段 — `main.py:1407-1458` + `model.py:1466-1494`

**现状（已接线部分，可逐行验证）**：
- `model.strategy_turn_bias` ← `_expl["turn_bias"]`，被**双限幅**：先 `max(0,min(0.25, ...))`（`main.py:1296`），再过 `max(0,min(1.0,...))`（`main.py:1409-1410`）。注释写 `[0, 0.4]`、代码是 **0.25**（`5c86272`/`61e1e0d` 两次收紧）。活体文件里 `turn_bias = 0.25` —— **卡在钳位上沿**，教练在此维度的建议事实上已失效（只能往小调）。
- `model.coach_turn_bias / coach_forward_bias / coach_timer / coach_active` ← `active_strategy["command"]`（`main.py:1431-1440`，`turn_and_go` 一次性指令）。
- `model._coach_dopamine_bias`（±0.3）与 `_pending_dopamine`（一次性 setback）← `active_strategy["dopamine"]`（`main.py:1441-1458`）。
- 模型侧消费：`dop = behavioral_dop + reward_signal * _coach_reward_gain + _pending`，再叠加 `_coach_dopamine_bias`，钳到 [-1,1] 后 `mushroom.set_dopamine(dop)`（`model.py:1470-1494`）。

**缺陷 D11（已修，2026-09-17）— 教练根本无法进入多巴胺系统。**
> `evolution_history.json` 的 EVO-069 记录原文：`trigger: "教练建议完全影响不到多巴胺系统——coach 看见虚空跳冲无效但无法传入奖惩信号"`；`source: "用户要求教练建议影响训练 → R31-fix9"`（对应 commit `73b7932`，Brain 2.23.6）。

这条**正是用户 #15/#16 的直接产物**：用户在 09-17 21:28 问"coach 建议可影响多巴胺，分析目前是否支持"，21:30 说"教练建议应该对训练起重要作用，修复实施后增加测试案例验证"，随后当天修复 + 7 例测试。

**缺陷 D12（未修 / 实测无效）— 奖惩闭环在真实运行中是空的。**
用户 #17（09-18 15:50）"coach建议行为是否有奖惩机制反馈，和生效"的**实测答案是"否"**。证据链（全部来自仓库内工件）：

1. `fly64/skills/coach_outcomes.jsonl` —— **30 行**：
   - `help_reason` 分布：`test_stuck` **21** / `unsolvable_stuck` **9** ⇒ 70% 是测试桩，**生产仅 9 条**。
   - `scene_label`：**30/30 全为空字符串** ⇒ 场景归因维度完全缺失（而 `scene_key()` 对空标签直接 `return ""`，见 `instinct_bindings.py:128-130`）。
   - 最后一行：`keys = {}`、`deltas = {stuck_duration: 0.0, health_score: 0.0, disp_60s: 0.0, loop_score: 0.0}` ⇒ **"哪条建议、带来什么变化"两个字段都是空的**。
   - `age_s` 跨度 30.1 → **22 964.1**（≈6.4 小时），说明该语料长期未刷新。
2. `fly64/skills/scene_strategy_bindings.json` —— 仅 2 个 bucket，均 `improved=1`（晋级门槛 `PROMOTE_MIN_IMPROVED = 2`，`instinct_bindings.py:79`），`promoted: false` ⇒ **本能固化一次都没成功**。
3. `fly64/skills/curriculum.json` —— `stage=1`、`attempts=8`（文件内 `history` 20 条，`consecutive_ok=0`、`consecutive_fail=0`）、`unobserved=0`、`reset_at: 2026-09-17T20:43`。对照 EVO-070 记录的"首个本能晋级 + 课程 stage 1→5"（09-17 实测），**当前状态是回落到 stage 1**，说明课程/本能状态没有被稳定维护。

⇒ **用户问的"奖惩机制是否在生效"，实测答案是：单元测试 7/7 通过，生产语料 0 条可用**。这就是 #18"为什么没有截屏生效"的同源结论：**教练链路已经"没有在跑"**（`coach_frames` 0 文件 + 生产 outcome 仅 9 条且字段为空），而不是"跑了但被某一行代码挡住"。

## 1.3 六段链路缺陷总表

| 段 | 缺陷 | 状态 | 证据/提交 |
|---|---|---|---|
| ① 触发 | 三条求助路径 100% NameError（`pos_y_ctx` 未定义） | ✅ 已修 | `3a0b993`；`runner.py:190-202` 考古注释 |
| ① 触发 | `coverage_rate < 0.05` 位移闸门 + `disp_60s > 300` 双重门 ⇒ 高速振荡永不求助 | ❌ 未修 | `main.py:1222-1224`、`memory.py:1152-1153`、`1184-1185`；用户 09-17 seq=17557 自证矛盾 |
| ② LLM | 裸 RGB 标注为 PNG ⇒ HTTP 400，且错误体被吞 | ✅ 已修 | `agent.md:677`；`llm_consult.py:165-172,369-380` |
| ② LLM | 仅 4 个旋钮对教练可见，与行为空间不对等 | ❌ 未修 | `llm_consult.py:110-149` vs EVO-066 审计（14/21 零消费者） |
| ③ 截屏 | 裸 RGB 被当 PNG 前缀 ⇒ 缩略图不显示 | ✅ 已修 | `2da6990` |
| ③ 截屏 | 屏幕纵向翻转缺失 | ✅ 已修 | `d9f006d` |
| ③ 截屏 | `capture_frame` 优先 128×128 cubemap，320×240 永不到达 | ✅ 已修 | `d646613`；`runner.py:263-277` |
| ③ 截屏 | 面板 max-height/overflow 裁切 + 折叠列塌陷 | ✅ 已修 | `6d37c04` |
| ③ 截屏 | **帧是 3–15s 前的画面**；且 `save_consult_frame` 主动消灭审计线索 | ❌ 未修（语义层） | `main.py:1903`、`2604-2607`；`runner.py:355-360`；`runtime/coach_frames` 0 文件 |
| ④ 写盘 | Coach 整体覆盖 EVO 的 active_strategy | ✅ 已修 | `879d983`；`strategy_writer.py:60-80` |
| ④ 写盘 | 点号死键被 EVO 反复再生（`__generation=152`）⇒ 4 个 escape 参数永远读默认值 | ❌ 未修 | `skills/active_strategy.json` 活体内容；`ea509a9` 声称已修 |
| ⑤ 键名 | 兄弟 section 被 `load_active_strategy` 丢弃 ⇒ 教练值 100% 回落默认 | ✅ 已修（t6 根修） | `d35e646`；`main.py:875-886` |
| ⑤ 键名 | 面板点号 id 写成字面顶层键 ⇒ 滑块报成功、行为零变化 | ✅ 已修 | `3a0b993`；`main.py:781-828` |
| ⑤ 键名 | "三处同步"守卫失效（SKILL 3.5.0 vs 3.4.2；EVO-072 未入史；徽章 2.23.11 vs 2.23.12） | ❌ 未修（治理） | 本报告 §1.2 D10 实测；`test_version_consistency` 2 failed |
| ⑥ 行为 | `turn_bias` 双限幅实际为 **0.25**（注释写 0.4），活体值卡在上沿 | ❌ 未修（语义矛盾） | `main.py:1296`、`1409-1410`；`active_strategy.json` |
| ⑥ 奖惩 | 教练无法进入多巴胺系统 | ✅ 已修 | EVO-069 / `73b7932`；`model.py:1484-1494` |
| ⑥ 奖惩 | 归因语料在生产中为空（9 条、键空、场景空、本能 0 晋级） | ❌ 未修（闭环缺口） | `coach_outcomes.jsonl`、`scene_strategy_bindings.json`、`curriculum.json` |

## 1.4 根因链（一句话链条）

```
① 求助路径 NameError（直到 EVO-062 才修）
   ↓ 即使不崩溃
② 触发判据被 disp_60s/coverage_rate 闸门抵消 → anomaly=idle → 教练不被叫醒
   ↓ 即使被叫醒
③ 教练看的是 3–15s 前的画面，且只有 4 个旋钮可表达（+ 截图工件不留审证）
   ↓ 即使给出建议
④⑤ 写盘被覆盖 / 键名不匹配 → 建议在文件里，不在行为里（t6 与 EVO-062/072 各修一段）
   ↓ 即使值抵达行为
⑥ turn_bias 钳在 0.25 上沿、其余 35+ 旋钮教练无权触碰
   ↓ 于是
   多巴胺/奖惩通道虽在（EVO-069），但 outcome 语料空 ⇒ 无人能证明建议有效
```

**根因（元层）**：整条链路的每一段都是**"文件可写、机制存在、单元测试通过"**，但**没有任何一处端到端断言"建议文本 → 行为变化 → 结果证据"**。因此缺陷只能靠用户肉眼发现（**73 条** coach 相关消息），修复只能靠一次次偶然定位——正是 EVO-066 自己命名的 **"机制存在、报告成功、无法生效"缺陷族**（该族在 09-17 一天内被系统审计一次性找出 3 组、含 14 个零消费者参数）。

---

# 顽疾 2 — AgentTeams 任务未执行

## 2.1 症状（用户原文 + 出现次数与位置）

至少三次质问，**分布在 5 个自然日、3 个 session**：

| # | 时间 | session | seq | 用户原文 | 上下文 |
|---|---|---|---|---|---|
| 1 | 09-16 14:19 | 27ed0979 | 6030 | **"分析为什么任务没有执行"** | 较早失败模式（团队已建、任务 pending） |
| 2 | 09-16 17:46 | fdb47617 | 1612 | **"激活任务，目前任务未执行"** | 同上，用户被迫手动催 |
| 3 | 09-20 20:51 | ed4b8026 | 11097 | **"分析任务为什么没有执行"** | `fly64-plan-v2` 已获 UI 批准后 |

## 2.2 早期失败模式（对照 session 取证）

**失败模式 A — 阶段未推进：团队 `phase=staged`，调度器直接返回。**
用户在 UI 里批准计划之前，团队是 `staged`；而调度器 `kickTeam` 第一道门就是：
```js
// dsh-agent-teams/lib/scheduler.js:204
if (team === undefined || team.halted === true || team.phase === 'staged') return;
```
⇒ 此时任何 `reassign_task` / mailbox 投递都**不会唤醒任何人**。

**失败模式 B — 成员从未被 spawn，`member.id === ''`。**
成员记录在**建团队/编辑计划阶段**就被写入（`add_member` 里的 `update_member` 分支明文拒绝已 spawn 的成员：`tools.js:363-364` `"staged member ... was already spawned"`），但真正的子会话只在**首次投递**时惰性创建：
```js
// tools.js:318-323  （dispatchToMember：唯一的惰性 spawn 路径）
if (member.id !== '') return deliverToMember(ctx, captain, member.id, text, signal, mode);
const selection = await resolveMemberLlmSelection(...);
await spawnMember(ctx, memberRuntime(config), memberSelections, selection,
                  captain, team, member, config.stateDir, signal, text);
```
而 **scheduler 不经过这条路径**：
```js
// scheduler.js:243-245 / 331-333 —— 直接调 deliverToMember，没有 spawn 分支
const accepted = await deliverToMember(ctx, captain, member.id, prompt, signal);
```
`deliverToMember` 只做 `ctx.subagents.queueMemberPrompt(...)`，失败即吞掉并返回 `false`：
```js
// members.js:559-572
catch (error) { ctx.logger.warn(`agent-teams: prompt delivery to member ${childId} failed: ${String(error)}`); return false; }
```
而可用性判据**把"从未 spawn"当成"可用"**：
```js
// scheduler.js:106-111
function isMemberAvailable(ctx, member) {
  if (member.stopping === true) return false;
  const live = liveMember(ctx, member);
  return live === undefined || live.status === 'idle';   // undefined（无会话）也算可用
}
```
⇒ 死循环：`member.id` 为空 → `deliverToMember` 失败 → `kickMember` 回滚 `task.status='pending'` 并把成员置回 `idle`（`scheduler.js:355-368`）→ 下次 kick 再走同一条不 spawn 的路。

**活体证据**（session `90dd512b` 原始工具输出）：
```
- instinct-implementer [本能化实现工程师] idle/unspawned · litellm-gateway/deepseek-v4-flash
- coach-behavior-tracer [教练行为追踪师] idle/unspawned · litellm-gateway/deepseek-v4-flash
- coach-infra-reviewer [教练基础设施审查员] idle/unspawned · litellm-gateway/deepseek-v4-flash
Tasks (9):
  - t1 [pending] work attempt 2 全栈状态审计报告 → auditor
  - t2 [pending] work attempt 2 教练基础设施审计 → coach-infra-reviewer
  ...
```
**队长在会话中的诊断原文**（同一 session 的 assistant 消息）：
- `"The status shows all members 'idle/unspawned' which means no child sessions were created. This could indicate a systemic issue: the scheduler may not be dispatching because members are unspawned."`
- `"['agent_teams_reassign_task'] increments attempt counter but doesn't trigger spawning"`
- `"AgentTeams backend in this deployment — members never spawn. Diagnosis: 'idle/unspawned'"`
- `"Team `evolution-next-phase` was approved; scheduler never spawned members (all `idle/unspawned`, attempts 2→4). User chose option B then said '执行' / '执行剩余任务' → captain executes the DAG directly."`

**关键量化事实**：`attempt 2 → 4` 说明队长**合规地**用了 2–3 次 `reassign_task`（唯一被文档许可的唤醒手段），每次都成功递增 attempt，**但没有一次创建子会话**。用户三次质问，两次（#1、#2）发生在 09-16 —— 比后期"captain 协议修复"早 4 天。

## 2.3 后期协议修复及其对早期失败模式的作用

时间线（从 commit 与 session 取证）：

| 日期 | 事件 | 对失败模式的作用 |
|---|---|---|
| 09-15 ~ 09-16 | 失败模式 A+B 首次出现，用户质问 #1/#2 | — |
| 09-19 | commit `cd9a5a7`（两次 AgentTeams 交付 + 根因分析报告）：`fly64-comprehensive-fix`、`fly64-plan-exec`、`fly64-challenge-analysis` 三团队**成功交付** | 说明"批准后 + 队长主动执行"是可行路径 |
| 09-20 | `fly64-plan-v2` 批准后用户质问 #3（ed4b8026 seq=11097）；队长反复 `agent_teams_status`（**重复调用告警：consecutive_calls 5 / 8**）后放弃等待、亲自执行 | 协议仍不可靠 |
| 现装版本 | `@nanmicoder/dsh-agent-teams@0.1.20` | 交付路径可用；**早期失败模式 A+B 在调度器代码中依然存在** |

**协议修复的实际内容（有效部分）**：
1. **队长接管通道**：`agent_teams_reassign_task(assignee="captain")` + 文档明示"captain 一次只能持有一个未完成接管，队长转 idle 时未完成接管回到成员池"（`tools.js:1232-1245`）。这就是 09-20 队长最终让 DAG 跑完的方式 —— **绕过调度器，由队长亲自执行**。
2. **成员侧认领协议**：`agent_teams_claim_task` 成为成员唯一的任务入口，并强制传 `attempt_id`；stale attempt 被拒（`tools.js:1369-1470`）。这让"任务已认领但没人执行"变得**可观测**（而不是沉默）。
3. **`view_team` 暴露 `spawnError`**：`tools.js:292-306` 的 `recordSpawnError` 明确写着修复动机 ——
   > `"without this the captain only ever sees an unexplained 'unspawned' member and no diagnostic reaches any surface."`

**未修部分**：调度器仍未复用 `dispatchToMember` 的惰性 spawn 分支。于是：
- 团队**批准后**若无人先触发一次 `add_member`/`send_message` 类投递，正则的调度器 kick **永远无法**创建第一个成员会话；
- `reassign_task` 会"报告成功"（返回 `attempt N`、`status pending`），而成员依旧 `unspawned` —— **同一族"报告成功、无法生效"缺陷在编排层的翻版**；
- 用户的解法只能是回到"队长自己干"，即 **AgentTeams 的并行价值在早期三轮里是负数**（建团队 + 审批 + 两次 reassign 的代价 > 队长直接执行）。

## 2.4 根因链

```
用户批准计划（phase: staged → running）
   ↓
调度器 kickTeam/kickMember 走 deliverToMember(member.id)
   ↓  member.id === ''（从未 spawn；spawn 只在 tools.js:318-323 的 dispatchToMember 里惰性发生）
deliverToMember → queueMemberPrompt(childId='') → throw → catch → return false（只写 warn 日志）
   ↓
kickMember 回滚：task.status='pending'、成员置回 idle、删 parkedAttemptId
   ↓
isMemberAvailable 把 live===undefined 判为可用 → 下一次 kick 重复同一路径
   ↓
队长唯一合规手段 reassign_task 递增 attempt（2→4）但不 spawn → 用户看到"任务未执行"
   ↓
收敛方式：队长亲自执行 DAG（09-19/09-21 的实际结局）
```

**为什么"后期 captain 协议修复"没有解决它**：修复解决的是**可观测性**（`spawnError`、`view_team` 显示 unspawned、attempt_id 强校验）与**兜底通路**（captain takeover），而根因在**调度器缺少惰性 spawn 分支**。所以"任务未执行"从"沉默失败"变成了"有明确诊断的失败 + 队长手动兜底"，症状频率下降但机制仍在。

---

# 顽疾 3 — 动作单调 / 探索无效

## 3.1 症状（用户原文 + 出现次数与位置）

| # | 时间 | session | seq | 用户原文（节选） |
|---|---|---|---|---|
| 1 | **09-17 14:55** | 27ed0979 | 216367 | **"脑模型对于运动的状态j检查认为异常的反应应该有自治的反应，重复的无效动作应该受惩罚，更多尝试受奖励，如果都无效则鼓励寻求coach帮助，但coach是兜底而不是优先选择"** ← 这是"奖惩 + 寻求 coach"的**原始需求全文** |
| 2 | **09-17 16:14** | 38542b1c | 637556 | **"分析马里奥在寻路导航中经常撞墙后持续做同样撞墙动作，为什么没有检测出状态异常，如何通过脑模型自治的训练，对于这种寻路重复无效作为寻路导航的第一优先级要规避这类操作，作为自治能力增加到脑模型，鼓励采用不同路径方向进行新的探索"** ← "撞同一堵墙"的**用户侧首次明确描述** |
| 3 | 09-17 17:14 | 27ed0979 | 133611 | **"目前大量时间在探索过的场景重复探索效率极低，应该在脑模型中认为是低效，应该自我进化中被惩罚，应该选择去未探索的网格探索或者去的少的次数地方，或者有交互对话可以产生更多事件的地方尝试"** |
| 4 | 09-18 16:18 | 27ed0979 | 331573 | **"未缓解：振荡强度加大 中位速度 316u/s（翻倍）但 60s 位移仅 28u（更差），loop 0.93 说明振荡频率更高、半径更小。cx_novelty_dir=0.0 持续无方向偏好 ... 全力转向但找不到出口"** ← 关键实测数据 |
| 5 | **09-18 16:47** | f953d3fd | 463044 | **"检查运动状态，在受困或者重复状态为什么不尝试其他的动作尝试脱困？"** |
| 6 | 09-18 21:55 | b2eeed98 | 335974 | **"分析目前运动探索的路径，分析探索路径的问题，重复路径尝试的原因和如何激活探索能力"** |
| 7 | 09-18 22:05 | b2eeed98 | 340478 | **"增加 evo skilll 对 [重复路径尝试的] 分析…同时要执行 A 和 B"** |
| 8 | 09-18 22:52 | 27ed0979 | 283022 | **"分析行动轨迹，分析目前导航策略的问题和重复无效运动的判定和问题解决"** |
| 9 | **09-22 17:09** | **99cab60f** | **2463** | **"分析 Forward pool 和 Jump pool 几乎没有波动，分析主要原因，目前运动动作过于单调，运动动作为什么大部分没有尝试"** ← **「大部分动作没有尝试」的权威原始出处（用户原话，含"有"字）** |
| 10 | **09-22 17:18** | 99cab60f | 2506 | **"修复问题 为什么"大部分动作没有尝试"　当前控制模式只有 1 种动作：全力转向+全力前进交替（oscillating 反射相位），其他所有动作被抑制：跳跃 ❌ 从不（gate_jump=False，MBON 信号被截断）／轻转向 ❌ 从不（reflex 只输出 ±70，无中间值）／停止后退 ❌ 从不／探索 ❌ 从不（coverage 2.1%，loop_score 0.99）"** ← **动作被抑制的逐项清单，与 §3.2 的代码机制逐条对应** |

出现次数：**10 条**（rev 2 新增 #2、#5、#9、#10 四条，均出自 rev 1 完全缺失的 `38542b1c` / `f953d3fd` / `99cab60f` 三个 session）；跨 **5 个 session**（`27ed0979` / `38542b1c` / `f953d3fd` / `b2eeed98` / `99cab60f`）、**09-17 14:55 → 09-22 17:18（6 个自然日）**。核心可观测指标（用户自行测得）：`中位速度 316u/s`、`60s 位移 28u`、`loop_score 0.93–0.99`、`cx_novelty_dir = 0.0`、`coverage 2.1%`、`jump_rate 0.46`。

> **口径更正（rev 2）**：rev 1 声称**「大部分动作没尝试」在 380MB 原始 jsonl 中零命中**、系 A1 报告的"二次引用"。**该结论错误**：rev 1 的检索串漏了一个「有」字。含「有」的原文确实存在，且是**用户本人的原话**（上表 #9，`09-22 17:09`，session `99cab60f` seq=2463），同 session `seq=2506` 用户又复述一次。A1 报告的转述（`docs/analysis/session_logs_analysis_v3.md:92` 写作「动作过于单调，大部分动作没尝试」）只是**掉了「有」字的措辞偏差，不是虚构**。rev 1 据此把它降级为"二次引用"并替换措辞，属**误判**，本版已恢复为用户原文引用（表 #9/#10）。rev 1 在附录 A 中给出的"0 命中"检索命令同样已修正为含「有」字的正确形式。

> **同时新增的关键上下文**：`seq=2506` 的用户清单（#10）把"动作被抑制"逐项列了出来（跳跃/轻转向/停止后退/探索各自"❌ 从不"及其原因）。这份清单**与 §3.2 的代码机制逐条对应** —— 用户再次**先于代码审计**给出了正确的问题分解（对照 `gate_jump=False`、`reflex 只输出 ±70`），与顽疾 1 收尾于用户自诊断（`09-22 18:12`）的模式完全一致。


## 3.2 振荡反射钳制 — 代码级机制

**钳制点 1：`turn_bias` 双限幅（`0.25` 硬上沿）。**
```python
# fly64/fly64/main.py:1293-1296
# Clamp turn_bias to [0, 0.4] — the EVO loop/plugin may write 0.8+ ...
if "turn_bias" in _expl:
    _expl["turn_bias"] = max(0.0, min(0.25, float(_expl["turn_bias"])))     # 代码 0.25
# fly64/fly64/main.py:1409-1410
model.strategy_turn_bias = max(0.0, min(1.0, float(_expl.get("turn_bias", 0.0) or 0.0)))
```
注释与代码不一致（0.4 vs 0.25，由 `61e1e0d` 收紧），且**活体文件里的值正好是 0.25**（钳位饱和）——用户（表 #4）观察到的 `turn_bias=0.8（最大）` 就是被这条钳住之前的形态。**教练/EVO 在此维度上只能往小调**，"更猛转向"这一类建议在结构上无法生效。用户表 #10 把这一点表述为「**轻转向 ❌ 从不 — reflex 只输出 ±70，无中间值**」：`turn_bias` 名义上可调，实际只剩两个饱和档。

**钳制点 2：振荡反射把控制量锁死在 ±70/±70 附近。**
用户描述的"全力转向↔全力前进交替"来自反射层与 LIF 的零和竞争；`_detect_oscillating` 的判据是 `control.x` 在窗口内 ≥3 次跨 ±60 交替（`memory.py:1146-1168`）——**检测到振荡的方式是"控制量已经饱和到 ±60"**，即振荡本身即是钳制的表现。

**钳制点 3：死锁突围 burst 与 cooldown 的比例失衡。**
```python
# fly64/fly64/main.py:1572-1600（当前 2.23.12）
if (memory_ctrl.anomaly_state_name == "oscillating"
        and (memory_ctrl.stuck_duration > 60
             or memory_ctrl.spatial.loop_score > float(_expl.get("loop_breakout_threshold", 0.90)))
        and not getattr(memory_ctrl, '_last_burst_tick', 0) == model.step_count):
    if _deadlock_burst_cooldown <= 0:
        _deadlock_burst_remaining = 200     # <-- 60 → 200（commit 5c86272）
        _deadlock_burst_cooldown = 300
        _fd = memory_ctrl.spatial.frontier_direction(pose[0], pose[1], pose[2], search_radius=50)  # <-- 20 → 50（commit 61e1e0d）
        ...
if _deadlock_burst_remaining > 0:
    if abs(_burst_heading) > 5:
        control.x = int(max(-80, min(80, _burst_heading * 1.5)))
    else:
        control.x = 0
    control.y = 127
    control.jump = False
    reflex_override = True
    _deadlock_burst_remaining -= 1
```
- **前置条件含 `anomaly_state_name == "oscillating"`**，而 §1.2 D2 已证明该状态在"高速振荡 + 真实位移"时会被置为 `idle` ⇒ **突围逻辑在用户报告的形态下根本不进入**。
- burst 期间 `control.y = 127`（全速前进）且 `jump = False`，`control.x` 固定为一个开环航向 ⇒ **连续 200 tick（~4s）剥夺其他动作**；300 tick cooldown 后再次进入 ⇒ **稳态下最多 200/500 = 40% 的 tick 处于"单动作开环冲刺"**，其余时间落在振荡反射上。这就是"动作过于单调"的机制本体：不是网络不想尝试别的动作，而是**控制量在两条固定轨迹之间被来回占用**。
- `_burst_heading` 只在"新 burst 开始"时赋值（`1585-1588`），burst 全程**不重算、不校验是否真在靠近前沿**——开环、无反馈。

## 3.3 重复路径探索 — 三重结构性缺陷

**缺陷 D13（未修，最重要）— 前沿方向不能随位置更新，burst 是开环的。**
`frontier_direction()` 每次 burst **只调用一次**，`_burst_heading` 在整个 200-tick burst 内不变。若前沿在 burst 中途变化（Mario 被墙/坡改动朝向），burst 仍朝旧方位全速前进 —— **这正是"沿同一路径反复试探、撞同一堵墙"的机制**。用户的 #2/#4/#6 全部指向这一点。

**缺陷 D14（未修）— 三个"探索有效性"信号都为 0 或恒定，惩罚无从生效。**
- `cx_novelty_dir = 0.0` 持续无方向偏好（用户 #3 实测）⇒ CX 新奇度没有给出方向梯度，因此 `frontier_direction` 的前沿选择事实上是在**无偏好状态**下做的最近邻选择 ⇒ 反复选中同一片"最近而未访问"的格子。
- `loop_score` 作为"重复探索"的唯一量化指标，其合法性依赖 `_revisit_count / len(self._history)`（`memory.py:535-539`），而 `_revisit_count` 在**有持续位移时每 30 tick 被衰减**（R31-fix10，`memory.py:413-421`）。⇒ **"高速绕圈"这一形态被主动衰减掉**，`loop_score` 无法长期维持高位 ⇒ 依赖它的三个消费者（burst 触发、`action_entropy` 触发、EVO pattern）同时失效。这是 §1.2 D2 与本节 D13 的**共同上游**。

**缺陷 D15（已部分修 / 参数化未覆盖）— 动作熵探索的作用域过窄。**
```python
# fly64/fly64/main.py:698-731（commit f4db53f，t28 P1，Brain 2.23.10）
def apply_action_entropy(control, *, novelty, loop_score, stuck_duration, rng) -> bool:
    if novelty >= 0.1 or loop_score <= 0.7:
        return False
    sigma = action_entropy_sigma(stuck_duration)   # min(30, stuck/10)
    dx = float(rng.normal(0.0, sigma)); dy = float(rng.normal(0.0, sigma))
    control.x = int(np.clip(round(control.x + dx), -80, 80))
    control.y = int(np.clip(round(control.y + dy), -80, 80))
    return True
```
- 触发条件是 **`novelty < 0.1` 且 `loop_score > 0.7`** —— 二者都被 D14 的衰减机制削弱，**实际触发窗口很窄**。
- 噪声是**逐 tick 独立高斯**：均值 0 的随机扰动会被 reflex/LIF 的低通与 cooldown 平滑掉，等价于"抖动"而非"换一个动作"；用户在 #1 要求的"更多尝试受奖励"需要的是**动作集合上的探索（policy entropy）**，而不是**控制量上的高斯噪声**。
- 该函数**不在 39 参数注册表内**（`brain_tunable_params.json` 无 `action_entropy_sigma` / 触发阈值条目）⇒ 无法被 EVO/面板调参，属"硬编码常量"，与 `218c6c0`"剩余 8 个常量是结构性、故意不可调"的声明不同（这条是可调的行为参数）。

## 3.4 已修 vs 未修（对照 `5c86272` 与 frontier radius 调整）

**已修（commit `5c86272`，Brain 2.23.12 / Skill 3.5.0）**：
- burst 时长 `60 → 200` tick（"escape-override-reflex 200t burst"）
- 触发门槛放宽：`escape_behavior AND stuck>300` → `oscillating AND (stuck>60 OR loop_score>0.90)`
- 新增 `waste_penalty` 适应度项（Skill 侧，使"无效位移"在 Phase 6 中被惩罚 —— 正对用户 #1"重复的无效动作应该受惩罚"）
- `loop_score` 阈值参数化：读 `_expl["loop_breakout_threshold"]`（默认 0.90）

**已修（commit `61e1e0d`，P0/P1/P2）**：
- `frontier_direction(search_radius=20 → 50)`，burst 从"直冲"改为"朝最近前沿"
- P0 参数写冲突自愈：限幅值每 12s（600 tick）回写文件，EVO/插件覆盖不再持久
- `_last_burst_tick` 去重守卫

**未修**：
1. burst 前置条件仍绑 `anomaly_state_name == "oscillating"`，而该状态在"高速振荡 + 真实位移"时为 `idle` ⇒ **最常见的用户报告形态仍不触发**。
2. burst 期间固定 `control.y = 127`、`jump = False`、航向开环 ⇒ 40% tick 单动作占用。
3. `frontier_direction` 每次 burst 只算一次，中途不更新 ⇒ 开环撞墙。
4. `_revisit_count` 的 30-tick 衰减使 `loop_score` 无法表达"高速绕圈" ⇒ 三个下游消费者共同失明。
5. `action_entropy` 未进参数注册表、逐 tick 独立噪声、触发窗口被 4 压缩。
6. `turn_bias` 钳位 `0.25` 与注释 `0.4` 不一致且饱和。
7. `cx_novelty_dir = 0.0`（CX 无方向偏好）在 `5c86272` 的提交信息里被称为"cx_novelty recovery path"，但**没有任何代码改变给出方向偏好**：`memory_ctrl.navigation_frontier_weight`/`danger_weight` 只调权重（`main.py:1345-1350`），不产生方向梯度。

## 3.5 根因链

```
探索失效的观测量：中位速度 316u/s、60s 位移 28u、loop_score 0.93、cx_novelty_dir 0.0
   ↓
上游 1：loop_score 被"有位移就衰减"主动抹平（memory.py:413-421, R31-fix10）
        → 依赖它的 3 个消费者（burst / action_entropy / EVO pattern）同时失明
   ↓
上游 2：anomaly 分类器与 loop_score 互相矛盾（memory.py:1152,1184 的 disp_60s>300 闸门）
        → anomaly=idle → burst 前置条件不成立
   ↓
上游 3：即使 burst 触发，航向开环、y=127 全速、jump=False 固定 200 tick
        → 40% tick 单动作 + 沿同一路径撞同一障碍（开环）
   ↓
上游 4：turn_bias 钳在 0.25 上沿 → "更猛转向"类建议结构性不可生效
   ↓
上游 5：探索噪声（action_entropy）窄触发 + 逐 tick 独立 + 不可调参
   ↓
上游 6：CX 无方向偏好（cx_novelty_dir 恒 0.0），前沿选择退化为"最近未访问格"
        → 反复回到同一片前沿
   ↓
用户观测："重复路径尝试"、"重复无效运动"、"大部分动作没尝试"
```

---

# 4. 三顽疾的共同结构（A2 的核心结论）

三个顽疾的修复史高度同构，可归纳为**同一缺陷族的三种表现**：

| 共同结构 | 顽疾 1（Coach） | 顽疾 2（AgentTeams） | 顽疾 3（探索） |
|---|---|---|---|
| **机制存在** | 双传输 LLM 咨询 + 策略热加载 + 多巴胺通道 | 团队/任务/依赖/心跳/claim 协议齐备 | 振荡反射 + burst + 前沿 + 动作熵 |
| **报告成功** | 接口 `{"status":"ok"}`、滑块 ✓、单测 7/7 | `reassign_task` 返回 `attempt 2..4` | burst 触发埋点、`+action_entropy` 标记、7 例测试 |
| **无法生效** | `_active_strategy` 兄弟段被丢（t6）、点号死键（EVO-062/072）、教练崩溃（EVO-062） | `deliverToMember` 对 `id==''` 必然失败，回滚后重试同一路径 | `anomaly=idle` 使 burst 前置不成立；`loop_score` 被衰减；开环航向 |
| **发现方式** | 用户肉眼，**73 条**相关消息 | 用户质问 3 次 | 用户肉眼，**10 条**相关消息 |
| **修复方式** | 逐点定位 + 事后补单元测试 | 可观测性 + 队长兜底 | 参数化 + 时长/半径调整 |
| **仍未闭环的原因** | 无端到端断言"建议→行为→证据"；写端反复再生死键 | 调度器缺惰性 spawn 分支 | 上游信号被自己的衰减/闸门抵消 |

**A2 判断**：Fly64 的顽疾不是"某个 bug 没修"，而是 **"验证的粒度停在单元级、而失效的粒度在链路级"**。
EVO-066 把这件事做对过一次（用 `scripts/audit_contract_pairs.py` 做 AST 级跨组件契约审计，一次找出 3 组缺陷）；EVO-071 也做对过一次（用仪表把 Phase 6 41% 零 delta 归因到 4 个不存在字段，**没改任何阈值就拿到根因**）。这两次是正确方法论，但**没有被固化为发布门禁**——`test_version_consistency` 现在就是红的，`--history-check` 存在却没人跑，`coach_outcomes.jsonl` 里的场景标签 30/30 为空也没人发现。

---

# 5. 未修部分清单（可直接转成任务书）

按"证据强度 × 阻塞下游程度"排序：

| # | 优先级 | 未修项 | 代码位置 | 验证方式（可复现） |
|---|---|---|---|---|
| U1 | **P0** | 触发闸门自相矛盾：`disp_60s>300` / `coverage_rate<0.05` 使"高速振荡"既不报警也不求助 | `main.py:1222-1224`；`memory.py:1152-1153, 1184-1185` | 合成快照调用 `check_help_needed` 返回 `None`（本报告已实测）；或注入 `loop_score=0.99, disp_60s=2100, anomaly=idle` |
| U2 | **P0** | EVO 反复再生点号死键 ⇒ `commit_reinforce/suppress/forward_accum_step/breakout_forward_bias` 读默认值 | `active_strategy.json`（`__generation=152`）；`evolution_skill.py` `param_paths/_inject`；`main.py:1332-1340` | `json.load(active_strategy.json)["exploration"]` 含 `escape.*` 键 5 个（本报告已实测） |
| U3 | **P0** | 崩溃修复未覆盖"子会话从未创建"：调度器缺惰性 spawn 分支 | `dsh-agent-teams/lib/scheduler.js:243-245, 331-333, 355-368`；`tools.js:318-323`；`isMemberAvailable` `scheduler.js:106-111` | 见 §2.2；复现需 staged→running 后直接 `reassign_task` |
| U4 | P1 | 归因闭环在真实运行中为空（键空、场景空、本能 0 晋级） | `coach_outcomes.jsonl`（9 条生产）、`scene_strategy_bindings.json`、`curriculum.json` | `deltas`/`keys`/`scene_label` 统计（本报告 §1.2 D12 已实测） |
| U5 | P1 | burst 开环 + 40% tick 单动作占用 | `main.py:1589-1598` | 复现 tick 序（本报告已按源码逐 tick 复刻，burst 内 `ctrl_x` 恒定） |
| U6 | P1 | `loop_score` 被"有位移即衰减"抹平 ⇒ 三消费者失明 | `memory.py:413-421, 535-539` | 高速绕圈 60s 后读 `loop_score` |
| U7 | P1 | 版本治理失效（三个版本源不一致、EVO-072 未入史） | `main.py:39-40`、`evolution_skill.py:40`、`evolution_history.json` `canonical_versions`、`skills.md` | `pytest fly64/tests/test_version_consistency.py` → 2 failed（本报告已实测） |
| U8 | P1 | 教练可见旋钮 4 个 vs 行为 39 个，严重不对等 | `llm_consult.py:110-149` vs `brain_tunable_params.json` | 对比 `SECTION_SPECS` 键集与 `main.py:1291-1458` 读取键集 |
| U9 | P2 | 帧延迟 3–15s 且 `save_consult_frame` 消灭审计线索 | `main.py:1903, 2604-2607`；`runner.py:355-360` | `runtime/coach_frames` 为空；需加"帧时间戳 ↔ 咨询时间戳"差分遥测 |
| U10 | P2 | `turn_bias` 钳位注释 0.4 / 代码 0.25，活体值饱和 | `main.py:1293-1296` | `active_strategy.json` `turn_bias = 0.25` |
| U11 | P2 | `action_entropy` 未进参数注册表、逐 tick 独立噪声 | `main.py:698-731` | `brain_tunable_params.json` 无对应条目 |
| U12 | P2 | 测试自身有 Windows 编码缺陷（同步守卫无法运行） | `tests/test_coach_dopamine.py:73`（`read_text()` 无 `encoding`） | `pytest test_coach_dopamine.py -q` → 1 failed（UnicodeDecodeError: gbk） |

# 6. 方法论建议（三条，直接来自取证过程）

1. **把"链路级断言"作为发布门禁**：每个顽疾各需**一条端到端断言**，而不是 N 条单元断言。
   - 顽疾 1：`写入 coach_advice.json → 600 tick 内 telemetry.coach_applied 的对应键必须改变 → 30s 后 coach_outcomes.jsonl 必须新增一条 keys 非空、scene_label 非空的记录`。
   - 顽疾 2：`团队 approve 后，不调用任何 add_member/send_message，仅 kick 一次，必须产生至少一个 child session`。
   - 顽疾 3：`注入 loop_score=0.99 + disp_60s=2100 + anomaly=idle 的合成快照，突围/求助必须至少有一条触发`。
2. **把 EVO-066 的契约审计做成 CI 门禁**（`scripts/audit_contract_pairs.py` 已在仓中）：任何"只写不读"键必须在发布时归零或显式登记为"未实现愿景"。
3. **把 EVO-071 的归因仪器固化为常规遥测**：`fitness_components` + `same_sample` + `missing_inputs` 已经存在，但只在手动跑脚本时可见；应进 `flow.json` 每 100 tick 一行，让"41% 零 delta"这类问题在仪表板上自证，而不是等用户抱怨。

---

## 附录 A — 取证命令（可复现）

```powershell
# 1) 权威语料真实用户消息提取（11 session 去重 + 剔除注入快照）  ← rev 2 主用
python scripts\_a2_extract_v3.py              # → .tmp/a2/v3_index.txt / v3_merged_user_msgs.txt
#    与 captain 的语料分析共用同一去重表：
python scripts\analyze_sessions_v3.py         # → .tmp/sessions_v3_analysis.json
python scripts\_captain_verify_msgs.py        # → 关键用户消息按时间线（captain 取证脚本）
# 2) 早期（不完整）口径，仅供对照，勿再用于计数
python scripts\_a2_extract_user_msgs.py       # 读 export logs/_extracted_*/（9 session，已废弃）
python scripts\_a2_inventory.py
# 3) coach 抱怨计数与分 session 归属（rev 2）
python -c "import io,re; txt=io.open(r'.tmp/a2/v3_merged_user_msgs.txt',encoding='utf-8').read(); blocks=re.split(r'\n(?=\[\w+\] \d\d-\d\d \d\d:\d\d)', txt); rows=[b for b in blocks if re.match(r'\[\w+\] \d\d-\d\d \d\d:\d\d', b) and re.search(r'coach|Coach|教练|教官', b)]; print(len(rows))"   # → 73
# 4) 全库检索（351 MB 权威语料）
rg -a -c "大部分动作没有尝试" .tmp\sessions_v3          # 含「有」字 → 命中（rev 1 漏字导致误判）
rg -a -o --no-filename ".{240}scheduler never spawned members.{240}" .tmp\sessions_v3 -g "*.jsonl"
# 5) 活体工件
Get-Content fly64\skills\active_strategy.json -Raw
(Get-ChildItem fly64\runtime\coach_frames -File).Count          # 0
python -c "import json,collections;rows=[json.loads(l) for l in open(r'fly64/skills/coach_outcomes.jsonl',encoding='utf-8') if l.strip()];print(len(rows),collections.Counter(r['help_reason'] for r in rows),collections.Counter(r['scene_label'] for r in rows))"
# 6) 契约测试实跑
python -m pytest fly64/tests/test_version_consistency.py fly64/tests/test_rule17_versions.py -q
python -m pytest fly64/tests/test_strategy_key_contract.py fly64/tests/test_coach_contract.py fly64/tests/test_coach_dopamine.py fly64/tests/test_consult_context_pos_y.py fly64/tests/test_strategy_update_endpoint.py fly64/tests/test_action_entropy.py -q
```

## 附录 B — 本报告涉及的提交

| commit | 日期 | 一句话 | 对应本报告 |
|---|---|---|---|
| `d35e646` | 09-17 | `load_active_strategy` 透传 exploration/escape/command（t6 根修） | D9 |
| `3a0b993` | 09-17 | EVO-062：点号 tunable id 展开 + consult context NameError | D1、D9 |
| `6b7f169` | 09-17 | EVO-049：SOS 缩略图 rawRGB→PNG + flipY + screen_b64 优先 | D5a/D5b/D5c |
| `73b7932` | 09-17 | R31-fix9：coach→dopamine 通路（EVO-069 的记录提交） | D11 |
| `c0f27e0` | 09-17 | EVO-066：契约审计，移除 3 个死旋钮，Phase 6 21→7 维 | D4 |
| `1a6249a` | 09-18 | `coverage_rate` 门限 0.01 → 0.05（三处） | D2 |
| `f4db53f` | 09-18 | t28 P1：动作熵探索（Gaussian stick noise） | D15 |
| `b913726`/`5253078`/`a6507e6`/`866db91` | 09-18 | R31-fix6/10/11/12：`disp_60s` 闸门、`loop_score` 衰减、位移释放 | D2、D14 |
| `9e7152a`/`6d37c04` | 09-18 | L2a `stuck_no_progress` 求助触发 + coach 面板显示修复 | D2、D5d |
| `5c86272` | 09-21 | Brain 2.23.12：200t burst + waste_penalty | §3.4 |
| `61e1e0d` | 09-21 | P0 参数自愈 + frontier radius 20→50 + evo-params 面板 | §3.4 |
| `879d983` | 09-22 | EVO-072：死键归一化 + coach 合并写入 | D7、D8 |
| `ea509a9` | 09-22 | 5 个参数修正读取 section + memory 段新增 3 参数 | D8 |
| `d646613` | 09-18 | `capture_frame` 优先 320×240 | D5c |
| `2da6990`/`d9f006d` | 09-16/17 | 缩略图 rawRGB 解码 + 纵向翻转 | D5a/D5b |

---

**产出**：`docs/analysis/analysis-a2-rootcauses.md`（本文件）· **rev 3**
**辅助脚本**：`scripts/_a2_extract_v3.py`（rev 3 主用，权威语料）、`scripts/_a2_extract_user_msgs.py`、`scripts/_a2_inventory.py`（早期口径，仅供对照）
**中间产物**：`.tmp/a2/{v3_index.txt, v3_merged_user_msgs.txt, v3_<session>_S*.txt, _v3_coach.txt, _v3_phrase.txt, _evo_records.txt, _90dd_spawn.txt, _90dd_reassign.txt, _inventory.txt, _kind_count.txt, _sid_map.txt, _index.txt, _coach_count.txt}`（`.tmp/` 被 `.gitignore:30` 忽略）

## 附录 C — 修订记录（rev 2 第一次复核 + rev 3 裁决收口；均由 captain 复核指出，逐条已改）

| # | 原错误主张 | 复核结论 | 处置 |
|---|---|---|---|
| 1 | rev 1："Coach 抱怨链止于 09-18" | **错**。最后一条为 `09-22 18:12 [99cab60f seq=2753]`，内容正是 §1.2 D7/D8 缺陷的用户侧原始诉求 | §0 口径修订 1 + §1.1 扩为 73 条（09-13 18:42 → 09-22 18:12）、删去原 #7 的"二次引用"降级 |
| 2 | rev 1："「大部分动作没尝试」零命中，系二次引用" | **错**。rev 1 检索串漏「有」字；原文为 **「大部分动作没有尝试」**，用户原话在 `09-22 17:09 [99cab60f seq=2463]` | §0 口径修订 2 + §3.1 表 #9/#10 恢复为用户原文，并修正附录 A 检索命令 |
| 3 | rev 1："仅 9 主 session / 342 条真实提问" | **错**。rev 1 读了空的残留目录 `export logs/_extracted_38542b1c`、`_extracted_f953d3fd`（各 0 文件） | §0 改为 11 session，时间线上溯至 **09-10 18:44**；并在 `38542b1c`/`f953d3fd` 中**新发现 4 条**原缺失的探索类原话（§3.1 #2/#5/#9/#10） |
| 4 | rev 2 首稿："951 条" | **偏差**。含 89 条 AgentTeams 派发/入队通知（以 `kind=user` 注入，须按内容剔除） | §0 提问总数改为团队权威口径 **874**；明确"不得改回 959" |
| 5 | rev 3 首稿："963 未去重，故应为 **870**" | **错（已废弃）**。该判断把 S7 的**不完整 legacy 导出**（59 条）当基线。captain 的 S7 消息级集合比对证明 `b2eeed98 (1)` ⊋ legacy（`only in legacy = 0`），基数应为 **963**；我独立复算确认 legacy 59 / `(1)` 63 / 差额 4、两者协议噪声均为 0 ⇒ **真实提问 = 874** | §0 最终链改为「**963 − 89 = 874**」，S7 表行改 63，逐行合计改 963/89/874；`870` 与"A0 待对齐项"表述删除；补记"净差额 85 = 89 − 4"（A4 已采用） |

> **裁决 3（本表第 5 行的裁定依据）：874 成立、870 废弃。** 依据 `scripts/_captain_resolve_s7.py` 对 S7 两个导出的**消息级集合比对**：`only in legacy = 0`、`only in (1) = 4`、`union unique = 62` ⇒ **`b2eeed98 (1)` 是 legacy 的严格超集**，故基数取 **963**（S7 = 63）而非 959（S7 = 59），真实提问 = 963 − 89 = **874**。**870 仅在 legacy-S7 这一不完整口径下成立**（`959 − 89 = 870`），因 legacy 丢失了 4 条 **09-21 探索三重死锁**现场记录（`cx_novelty_dir 仍在 0.0 … cells 全面陈腐 1524 次/格`）而作废。该 4 条正是 §3.4 所分析战役的原始证据，取 legacy 会整场漏掉 —— 教训与第 3 行同源。

**实质结论未变（captain 已认可）**：三顽疾根因链、EVO-066「机制存在、报告成功、无法生效」缺陷族判定、12 项未修清单（U1–U12）。
**rev 2 – rev 3 净增益**：新增 4 条可溯源用户原话（含「大部分动作没有尝试」原始出处）+ 2 条用户先于代码审计给出的正确问题分解（`09-17 16:14` 撞墙重复、`09-22 17:18` 动作抑制清单），使 §3 的"用户早就说对了"论断从推测变为有据；把顽疾 1 的收尾从"09-18 未回答"修正为"**09-22 由用户自诊断闭合**"；并把 S7 那 4 条 09-21 探索三重死锁记录**纳入证据源**（它们一度因 legacy 导出而整体缺失）。
