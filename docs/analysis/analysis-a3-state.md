# A3 — 代码状态盘点：最新修复的验证情况

> 分析对象：`D:\codes\flygym\fly64`（HEAD `cf2f472`，2026-09-22）
> 生成方式：本文件由 `fly64/.tmp/_a3_build_doc.py` 从**实际文件内容与命令输出**装配而成；
> 全部表格均为机器生成，可复现（见 §7）。
> 范围声明：本任务只覆盖**代码/参数/测试/版本**状态，不覆盖对话日志统计；
> 因此不依赖也不会传播任何 session 计数口径。

---

## 0. 结论摘要（TL;DR）

| # | 结论 | 证据 |
|---|------|------|
| **S1** | **最新一次版本发布（`5c86272` v2.23.12 / v3.5.0）尚未通过自身的一致性门禁**：`test_version_consistency.py` 硬编码期望 `2.23.11`，`main.py` 已是 `2.23.12`，2 项断言失败，且 `skills.md` 徽章、`evolution_history.json` canonical、`evolution_skill.SKILL_VERSION` 三处仍是旧值 | §1 |
| **S2** | **“39 参数全部 wired=true”不成立**：探针把注册表 39 个 pid 逐个按面板写入路径 → apply_strategy_update → EVO-072 归一化 → 读取端表达式跑通，**38 个可达、1 个不可达**（`exploration.breakout_forward_bias`，声明段与读取段不同）；另有 `reflex.cooldown_min` 全仓零消费者 | §4.2 |
| **S3** | **`ea509a9` 声称修复的 5 个死参数中，4 个已修好，第 5 个被该次“修复”本身改成死参数**（原先读 `_expl` 正确，改成读 `_esc` 后永远读默认值 0.50） | §4.2 / §4.3 |
| **S4** | **EVO-072（`879d983`）的归一化只清理“同段前缀”死键**：真实 `active_strategy.json` 中 `exploration` 段内仍存 5 个 `escape.*` 点号死键，与其在 `escape` 段的清白键**值不同**（如 `forward_accum_step` 0.01576 vs 0.005），读取端静默使用默认值 | §4.3 |
| **S5** | **回归基线已失效且门禁为红**：`pytest tests` 现为 **62 failed / 1130 passed / 37 skipped**，其中 **34 个失败不在 `known_failures.win32.json` 里**（NEW），同时 **10 条基线条目已通过**（基线双向腐化）；`known_failures.*.json` 自 2026-09-18 未再刷新 | §5 |
| **S6** | **EVO-068 的“0 未分类”已回退**：win32 基线 38 条中含 **3 条 `cause=unknown` 且 `note` 为空** | §5.2 |
| **S7** | **进化档案缺一条**：`evolution_history.json` 共 79 条，止于 `EVO-071`（`canonical_versions` = brain 2.23.11 / skill 3.4.2，`as_of` 2026-09-18），**`EVO-072` 不在库中**；13 条为占位记录、23 条 `tests` 为空 | §2.4 |
| **S8** | **测试套件会写生产工件**：全量 `pytest tests` 期间 `plugin/.consult_request.json`、`.consult_response.json` 被改写（时间戳 22:35:39/22:35:43），其内容与 `tests/test_t3_handshake.py` 第 13–16 行的字面量**逐字节一致**——该模块在 import 期执行代码；`conftest.py` 只重定向了 `FLY64_EVIDENCE_DIR`，不覆盖这条路径 | §5.4 |
| **S9** | **README 的“39-param registry 是 Coach+EVO+panel 的单一事实源”不成立**：Coach 的 `plugin/llm_consult.py::SECTION_SPECS` 是手工维护的 4 个键，从不读取注册表 | §1.4 |

---

## 1. 版本与三源一致性核对（任务要求 5）

### 1.1 四处版本声明实测

| 位置 | 声明值 | 命令/文件 |
|------|--------|-----------|
| `fly64/fly64/main.py:39-40` | `BRAIN_VERSION = "2.23.12"` / `SKILL_VERSION = "3.5.0"` | `Select-String BRAIN_VERSION` |
| `fly64/skills/skills.md:3,70` | `BRAIN_VERSION **2.23.11** / SKILL_VERSION **3.4.2**`（两处徽章） | `Select-String 'BRAIN_VERSION \*\*'` |
| `fly64/skills/evolution_history.json` → `canonical_versions` | `brain 2.23.11 / skill 3.4.2`，`as_of 2026-09-18T01:08:22+08:00` | `json.load(...)['canonical_versions']` |
| `fly64/skills/evolution_skill.py:40` | `SKILL_VERSION = "3.4.2"` | `Select-String SKILL_VERSION` |

`main.py` 与其余三处**全部不一致**。agent.md 规则 8（三源同步）与规则 17（版本严格递增）在此刻同时失效。

### 1.2 门禁测试的实测结果

`tests/test_version_consistency.py` 第 40 行 `EXPECTED = "2.23.11"`。在当前树上：

- `TestVersionConsistency::test_main_py_is_expected` → **FAILED**（2.23.12 ≠ 2.23.11）
- `TestVersionConsistency::test_all_three_sources_agree` → **FAILED**（badges/canonical 2.23.11 vs main 2.23.12）
- `TestVersionConsistency::test_skills_md_badges_match_main` / `test_history_canonical_matches_main` → PASSED（因为三处旧值彼此一致）

这两项失败**都不在** `known_failures.win32.json` 中，因此 `scripts/check_regressions.py` 会把它们报为 NEW。

### 1.3 与 README 声明的一致性

README 模块行数（`main ~2700 / model ~2150 / memory ~2380`）实测为 **2701 / 2149 / 2379**（`sum(1 for _ in open(f))`）→ **一致**。
README 声明的 4 个新端点均存在：`/evolution-log.json`（main.py:218）、`/param-history.json`（:227）、
`/brain_tunable_params.json`（:254）、`POST /active_strategy-update`（:383）。
README 的 “tests 452→600+” 低于实测的 **1228 collected**，属保守陈述而非错误。

### 1.4 “39-param registry 作为单一事实源”核对

| 消费者 | 是否从 `brain_tunable_params.json` 取参数集 | 证据 |
|--------|--------------------------------------------|------|
| 操作面板 `web/evo-params.html` | 是 | `get('/brain_tunable_params.json')`（第 152 行），`meta.wired`（第 79 行）|
| EVO / Phase 6 `BrainMutator` | 是 | `live_params` 过滤 `wired is not False`（evolution_skill.py:1783），注释“Registry grew to 39 wired params”（:2115）|
| **Coach** `plugin/llm_consult.py` | **否** | `SECTION_SPECS`（第 110 行起）是手工 dict：`fallen_recovery.mode`、`exploration.bold_explore_stuck_s`、`exploration.turn_bias`、`escape.stuck_threshold_s` —— 4 个键，无一处读取注册表 |

结论：**“单一事实源”对 Coach 不成立**；Coach 侧另有 `escape.stuck_threshold_s` 这一**不在注册表中**的可调键，
说明“注册表 = 全量可调旋钮”也不成立（存在注册表外的活旋钮，和注册表内的死旋钮）。

---

## 2. 进化脉络：R1 → EVO-072（任务要求 1）

### 2.1 档案基本事实

| 指标 | 值 |
|------|----|
| `records` 总数 | **79** |
| EVO-* / AUTO-* | 63 / 16 |
| ID 范围 | EVO-001 … **EVO-071**（EVO-040…047 从未使用） |
| 去重后 round 数 | 63 |
| `canonical_versions` | brain **2.23.11** / skill **3.4.2**，`as_of` **2026-09-18T01:08:22+08:00** |
| 文件 mtime | 2026-09-20 23:39:47 |
| `tests` 为空的记录 | **23** 条 |
| 占位记录（“auto-recorded version change … REQUIRED from the evolving agent”） | **13** 条 |
| `deployed` 为 null | **38** 条 |
| 含“实机/活体/实测/端到端/生产/运行时”字样的记录 | **13** 条 |

**关键缺口**：`EVO-072`（`879d983`，2026-09-22，SKILL 侧修正）**不在档案中**；
`canonical_versions` 停留在 2.23.11/3.4.2，落后于 `main.py` 的 2.23.12/3.5.0。
任务要求的“R1→EVO-072 脉络”在档案层面**只能到 EVO-071**，EVO-072 仅存在于 git commit message。

### 2.2 阶段化脉络

| 阶段 | 记录 | 主线问题 | 版本 |
|------|------|----------|------|
| R1–R6 (2026-09-12 → 09-13) | EVO-001 … EVO-006 | 单机基础能力：绕圈/斜坡/墙角卡死 → 地形门控、脱困覆盖、伴发放电、自适应反射冷却 | B1.0.0 → 1.4.0 |
| R7–R10 (09-13 → 09-14) | EVO-007 … EVO-011 | FlyWire 差距分析驱动的视觉/场景子系统：颜色 UV、EMD、小目标追踪、亮度-流分离、室内围闭度、local_breakout | B2.0.0 → 2.4.0 |
| R11–R13 (09-14) | EVO-012 … EVO-017 | 教练（LLM）决策接入 + 死键首次暴露（bold_explore_stuck_s / turn_bias 无消费者）+ 反射风暴死循环 | B2.4.0 → 2.6.1 |
| R14–R19 (09-14 → 09-15) | EVO-018 … EVO-026 | 神经基质接管（删 11 处 Python 旁路）、悬崖对峙、MBON 饱和稳态缩放、DAN 塑形、restlessness 躁动电流 | B2.7.0 → 2.12.0 |
| t18–t21 (09-15) | EVO-027 … EVO-032 | 可观测性与运维：Seqlock 看门狗、启动契约、CX 罗盘自主化、求助阈值 120→60s、读屏 what_i_see、截图留档 | B2.12.1 → 2.13.3 |
| R23–R29 (09-15 → 09-16) | EVO-033 / EVO-034 | 瓶颈攻坚轮（T2 场景上下文 5 层协议 + T3 饱和恢复）与 CCL 连通性修复 | B2.14.0 |
| Motor-P1–P5 (09-16) | EVO-035 … EVO-038 | 运动原语扩展：Z 触发通道、CPG 级联、strike/crouch 池、MBON 5→9 列、PUNCH/DIVE | B2.14.0 → 2.17.0 |
| 运维收敛 (09-17) | EVO-048 | Windows/WSL 双循环竞态 → 单循环 + 跨文件系统锁，规则 16 固化 | B2.19.3 / S3.1.0 |
| v2.20.0 发布 (09-17) | EVO-049 / EVO-050 | breakout_gain 自适应、CPG 零位移切原语、flow.json 补 8 字段；SKILL 版本自动留痕 | B2.20.0 / S3.1.1→3.2.0 |
| L2 / R31-fix2–4 (09-17) | EVO-051 … EVO-055 | 截屏保真度（渲染管线钩子时机）、位移奖励误指定、fall 状态语义（速度+去抖）、教练键透传根因修复 | B2.20.0 → 2.21.1 / S3.2.0 |
| t9-A/B/C (09-17) | EVO-057 … EVO-059 | circle_loop 双死因、P4.4 本能固化四重死因、生产启动 NameError（干净检出全绿、生产必崩） | B2.22.0 → 2.23.1 / S3.2.0→3.3.0 |
| t10–t15 (09-17) | EVO-062 … EVO-068 | 点号路径死写入修复、场景身份实测（撤回假设）、课程三态判定、契约审计死旋钮、验证基线（回归可探测） | B2.23.4 → 2.23.5 / S3.3.0→3.4.1 |
| R31-fix6–9 / t16 (09-17) | EVO-060/061/063/069/070 | micro_loop 虚高、虚空逃逸自适应、command.turn_and_go 消费、教练多巴胺通道、首个本能晋级实测 | B2.23.2 → 2.23.6 |
| t17 (09-18) | EVO-071 | Phase 6 适应度根因（读 SensorSample 上不存在的 4 个字段）+ 归因工具 + 已声明未实现 30 项登记册 | B2.23.6 / S3.4.2 |
| **未入库** | **EVO-072** | active_strategy 键名归一化 + coach 合并写入（commit 879d983）——**evolution_history.json 中不存在此条** | B2.23.12 / S3.5.0 |

### 2.3 全量记录表（79 条，按档案顺序）

| # | id | date | round | kind | 版本 | 触发问题（截断） | 证据 |
|---|----|------|-------|------|------|------------------|------|
| 1 | `EVO-001` | 2026-09-12 | R1 | brain | B1.0.0 | 无障碍平地上原地转圈（circle_loop） | 单测 |
| 2 | `EVO-002` | 2026-09-12 | R2 | brain | B1.0.x | 斜坡卡死 | 单测 |
| 3 | `EVO-003` | 2026-09-13 | R3 | brain | B1.1.0 | 墙角视觉盲区卡死 | 单测 |
| 4 | `EVO-004` | 2026-09-13 | R4 | brain | B1.2.0 | 钥匙门提示场景；进化过程需仪表板可见 | 单测 |
| 5 | `EVO-005` | 2026-09-13 | R5 | brain | B1.3.0 | 上置提示框（钥匙门第二形态）重复交互 | 单测 |
| 6 | `EVO-006` | 2026-09-13 | R6 | brain | B1.4.0 | 固定 10s 反射冷却在长时间卡住下失效；fallen 恢复固定左转失败 | 单测 |
| 7 | `EVO-007` | 2026-09-13 | R7 | brain | B2.0.0 | FlyWire MaleCNS 差距分析：视觉覆盖 38% 过低 | 单测 |
| 8 | `EVO-008` | 2026-09-13 | R8 | brain | B2.1.0 / S2.5.0 | brightness-not-flow：亮度差被误当运动 | 单测 |
| 9 | `EVO-009` | 2026-09-13 | R9 制度化 | infra | — | R8 事故：合成模式 consolidate 静默断开游戏视觉 | — |
| 10 | `EVO-010` | 2026-09-13 | R9 | brain | B2.2.0 / S2.6.0 | 室内场景被识别为天空·山坡（天花板灯/格纹误判） | 单测 |
| 11 | `EVO-011` | 2026-09-14 | R10 | brain | B2.3.0 / S2.7.0 | 497.9s micro_loop 零位移事件；bold 门控用全局 visited_cells<20 在老地图永不触发 | 单测 |
| 12 | `EVO-012` | 2026-09-14 | MHR-1 | brain | B2.4.0 | 对话场景需要 LLM 按键决策 | 单测 |
| 13 | `EVO-013` | 2026-09-14 | R11 | brain | B2.5.0 / S2.8.0 | escape_x 随机方向导致逃逸无效；撞墙行为需网络自行学习 | 单测 |
| 14 | `EVO-014` | 2026-09-14 | R11 完成 | brain | B2.6.1 / S2.9.1 | coach 策略键为死写入无消费者 | 单测 |
| 15 | `EVO-015` | 2026-09-14 | R12 | infra | B2.6.0 / S2.9.0 | 10s 循环依赖 DSH 会话，会话结束即停——自治不能依赖外部会话 | 单测 |
| 16 | `EVO-016` | 2026-09-14 | R12 follow-up | brain | B2.6.0 | 反射活跃掩盖真实卡死（497.9s/0u 事件类）：help 判定被 reflex_active 短路 | 单测 |
| 17 | `EVO-017` | 2026-09-14 | R13a | brain | B2.6.1 / S2.9.1 | stuck=1063s/micro_loop 973s/loop_score 病态 104.9——自适应冷却触底引发反射风暴死循环 | 单测 |
| 18 | `EVO-018` | 2026-09-14 | R13b | brain | B2.7.0 / S3.0.0 | 对话暂停场景缺乏可观测性与负反馈学习 | 单测 |
| 19 | `EVO-019` | 2026-09-14 | P1 接管 | brain | B2.8.0 / S3.0.0 | 双轨旁路：main.py ~35 处直接改写 control，五大神经基质被旁路 | 单测 |
| 20 | `EVO-020` | 2026-09-14 | R14/R15 | brain | B2.9.0 / S3.0.0 | 恒向转圈→原地编织；悬崖边缘对峙驻留（EscapeSkill findings=0） | 单测 |
| 21 | `EVO-021` | 2026-09-14 | t13 | brain | B2.9.1 / S3.0.0 | Coach Advice 四环节三处不生效（死键/触发窄/prompt 语义/HTTP 400） | 单测 |
| 22 | `EVO-022` | 2026-09-14 | R16 | brain+skill | B2.10.0 / S3.0.0 | 交替把转圈变成原地编织（缺 forward 突破）；flow.json 缺 5 个因果键致 skill 检测永不命中；字段缺失被静默跳过 | 单测 |
| 23 | `EVO-023` | 2026-09-15 | t16 | brain+skill | B2.10.1 / S3.0.0 | t15 监控布局分析发现的 P0 可见性缺口 | 单测 |
| 24 | `EVO-024` | 2026-09-15 | R17 | brain+skill | B2.11.0 / S3.0.0 | mb_mbon_forward=1.0 饱和（正 DA 再膨胀 vs 稳态缩放平衡点贴顶）；anomaly_reflex 改写 control 使 bre… | 单测 |
| 25 | `EVO-025` | 2026-09-15 | R18 | brain | B2.11.x / S3.0.0 | R17 后正多巴胺再膨胀与稳态缩放平衡点仍在天花板；探索奖励 0.5 持续 +DA 是膨胀主因 | 单测 |
| 26 | `EVO-026` | 2026-09-15 | R19 | brain | B2.12.0 / S3.0.0 | 熔岩地悬崖边驻留 61s：识别结果未驱动行为、静息状态 breakout 电流失效（TurnAdaptation 只响应转弯） | 单测 |
| 27 | `EVO-027` | 2026-09-15 | t19 | infra | B2.12.1 / S3.0.0 | SM64 被连带 kill 后桥停更，视觉画布静默冻结且无监护 | 单测 |
| 28 | `EVO-028` | 2026-09-15 | t18+R20 | brain+infra | B2.13.0 / S3.0.0 | 启动契约事故（托管 job 连带 kill）；CX 罗盘是外部航向副本、零路径积分、目标向量单源 | 单测 |
| 29 | `EVO-029` | 2026-09-15 | t20 | skill | B2.13.1 / S3.0.0 | 教练介入太晚：120s 阈值下马里奥已深陷 | 单测 |
| 30 | `EVO-030` | 2026-09-15 | t21 | skill | B2.13.2 / S3.0.0 | 无法验证 GLM 是否真在读屏；屏幕文字语义丢失 | 单测 |
| 31 | `EVO-031` | 2026-09-15 | t21 收尾 | skill | B2.13.3 / S3.0.0 | 回溯无法知道教练当时看到了什么画面 | 单测 |
| 32 | `EVO-032` | 2026-09-15 | R21 | brain+skill | B2.13.3 / S3.0.0 | runner 读 scene_name 但 memory_json 只有 scene_label；面板看不到 fallen_recovery 策略细节 | — |
| 33 | `EVO-034` | 2026-09-16 | R29 | brain | S3.0.0 | stride-2 采样下小目标检测被 CCL 4-连通性阻断 | 单测 |
| 34 | `EVO-035` | 2026-09-16 | Motor-P1 | brain | B2.14.0 / S3.0.0 | 电机扩展：摇杆 x/y/jump 之外的动作原语需要 Z 触发键通道 | — |
| 35 | `EVO-036` | 2026-09-16 | Motor-P2 | brain | B2.15.0 / S3.0.0 | 运动原语需要级联层与神经解码衔接 | — |
| 36 | `EVO-037` | 2026-09-16 | Motor-P3 | brain | B2.16.0 / S3.0.0 | 打击/下蹲动作需要独立运动池；蘑菇体输出通道需扩展 | — |
| 37 | `EVO-038` | 2026-09-16 | Motor-P4/P5+M1 | brain | B2.17.0 / S3.0.0 | Phase 4 仪表板可视化 + Phase 5 EVO pattern + M1 优化层（债务清理 + 新动作原语 PUNCH/DIVE） | — |
| 38 | `EVO-039` | 2026-09-16 | P1-2 perf | analysis | B2.17.0 / S3.0.0 | P1-2 CSC 传播 8-15ms/step 制约 tick 频率与进化验证吞吐；尝试选择路径微优化（布尔掩码/fancy/gather+bincoun… | 单测 |
| 39 | `EVO-048` | 2026-09-17 | 运维收敛 | infra | B2.19.3 / S3.1.0 | 双循环并发：Windows 循环（09-16 22:00 启动，pwsh 会话）+ WSL 循环（并行 agent 启动，旧代码无锁）——跨文件系统锁互不… | 单测 |
| 40 | `EVO-049` | 2026-09-17 | v2.20.0 发布 | brain+skill | B2.20.0 / S3.1.1 | 3 项持续缺陷修复：①breakout 电流非自适应（恒定振幅压制转向）②CPG 原语零位移不切换③flow.json 遥测缺 8 字段 | 单测 |
| 41 | `EVO-050` | 2026-09-17 | — | skill_update_… | B2.20.0 / S3.2.0 | 工作树观测到 SKILL_VERSION 3.1.1→3.2.0（并行会话在途轮）——按规则 15/17 留痕；完整 trigger/changes/te… | — |
| 42 | `EVO-054` | 2026-09-17 | t6 根因修复 | brain | B2.21.0 / S3.2.0 | coach 建议从未真正影响 behavior：load_active_strategy() 只返回 fallen_recovery 派生字段，从不透传 … | **实测** |
| 43 | `AUTO-0001` | — | — | skill_fix | B2.13.3 / S3.0.0 | Patterns skipped because their condition fields are absent from telemetry: ['… | — |
| 44 | `AUTO-0002` | — | — | skill_fix | B2.13.3 / S3.0.0 | forward MBON saturated at ceiling while behaviour still loops. The built-in h… | — |
| 45 | `AUTO-0003` | — | — | skill_fix | B2.13.3 / S3.0.0 | Fallen detection threshold (Y<-100) is too permissive. SM64 normal ground is … | — |
| 46 | `EVO-033` | 2026-09-15 | R23 | brain | B2.14.0 / S3.0.0 | 系统性攻破 Fly64 脑模型剩余瓶颈：7 大瓶颈（语义三缺失/视网膜配准/P2 KPI/MBON 饱和拉锯/计算纪律/遥测漂移/死值遥测）+ 2 项部分… | 单测 |
| 47 | `AUTO-0004` | — | — | brain_update_… | B2.13.3 / S3.0.0 | dashboard brain_version change | — |
| 48 | `AUTO-0005` | — | — | brain_update_… | B2.13.3 / S3.0.0 | dashboard brain_version change | — |
| 49 | `AUTO-0006` | — | — | brain_update_… | B2.18.0 / S3.0.0 | dashboard brain_version change | — |
| 50 | `AUTO-0007` | — | — | skill_fix | B2.18.0 / S3.0.0 | Wrong primitive for the terrain (e.g. longjump on a ledge edge) or Z/A pulse … | — |
| 51 | `AUTO-0008` | — | — | brain_update_… | B2.19.0 / S3.0.0 | dashboard brain_version change | — |
| 52 | `AUTO-0009` | — | — | brain_update_… | B2.19.1 / S3.0.0 | dashboard brain_version change | — |
| 53 | `AUTO-0010` | — | — | brain_update_… | B2.19.2 / S3.0.0 | dashboard brain_version change | — |
| 54 | `AUTO-0011` | — | — | brain_update_… | B2.19.3 / S3.0.0 | dashboard brain_version change | — |
| 55 | `EVO-055` | 2026-09-17 | L2 导航质量与自我进化闭环 | skill | B2.20.0 / S3.2.0 | SOS 缩略图空白（raw RGB 误作 PNG 解码）；L2 求助触发仅覆盖对话习惯化，高速绕圈类（loop>0.9/coverage_rate=0/s… | **实测** |
| 56 | `EVO-051` | 2026-09-17 | R31-fix2 | brain | S3.1.1 | 教练截屏与实际游戏画面长期不一致：snapshot 只是游戏屏幕一部分——R21 截图点落在复眼观察者通道尾部（时机=帧中段、视口=观察者残留、FBO 绑… | 单测 |
| 57 | `EVO-052` | 2026-09-17 | R31-fix3 | brain | B2.20.3 / S3.1.1 | 熔岩地移动型困境分析：位移奖励误指定（493u/60s 高速绕圈拿正奖励、coverage 4.1% 纹丝不动、掉血无负 RPE、受击格不在失败记忆）——… | 单测 |
| 58 | `EVO-053` | 2026-09-17 | R31-fix4 | brain | B2.20.4 / S3.2.0 | 用户指出 fall 状态判定不准确：旧谓词 pos_y<50 or pos_y>500 把合法高处（塔/平台 y 可达 600~2000+）误判为坠落、无… | 单测 |
| 59 | `EVO-056` | 2026-09-17 | R31-fix5 | brain | B2.21.1 / S3.2.0 | 用户反馈 Mario 在 micro_loop 反射期间看起来不动 → 分析发现反射相位的交替纯旋转（x=±69,y=0，左右抵消），spin-in-pl… | 单测 |
| 60 | `EVO-057` | 2026-09-17 | t9-A P1-1 环路破解 | brain | B2.22.0 / S3.2.0 | circle_loop 可持续数分钟不破：CX 的探索游走是 ~10s 正弦扫掠，频率远低于紧致轨道；工作树中另有一段“强制随机跳列”代码，但它从未生效—… | 单测 |
| 61 | `EVO-058` | 2026-09-17 | t9-B P4.4 本能固化 + 证据基座 | brain | B2.23.0 / S3.3.0 | P4.4 场景→策略本能固化“已实现但结构上不可能达成”。四重独立死因：① 指纹要求全参数精确一致，而教练每次咨询都重调参数——真实 45 条 outco… | **实测** |
| 62 | `EVO-059` | 2026-09-17 | t9-C 启动崩溃修复 | brain | B2.23.1 / S3.3.0 | 脑进程在生产环境无法启动：main.py 在模块级第 64 行调用 _load_evolution_history()，而该函数写入 DashboardH… | **实测** |
| 63 | `EVO-060` | 2026-09-17 | R31-fix6 | brain | B2.23.2 / S3.2.0 | micro_loop stuck_duration 虚高：R31-fix5 的 cy=30 已产生实际位移（disp_60s>3000u），但 anoma… | 单测 |
| 64 | `AUTO-0012` | — | — | brain_update_… | B2.23.1 / S3.3.0 | dashboard brain_version change | — |
| 65 | `EVO-061` | 2026-09-17 | R31-fix7 | brain | B2.23.3 / S3.3.0 | fallen 状态下 Mario 卡在地图下方 y=-954，固定 1.5s 跳冲无法复位（depth too extreme） | **实测** |
| 66 | `EVO-062` | 2026-09-17 | t10 操作面板/教练上下文修复 | brain | B2.23.4 / S3.3.0 | ① 操作面板滑块是“死控件”：web/evo-params.html 直接 POST brain_tunable_params.json 的参数 id，而… | **实测** |
| 67 | `AUTO-0013` | — | — | brain_update_… | B2.23.1 / S3.3.0 | dashboard brain_version change | — |
| 68 | `AUTO-0014` | — | — | brain_update_… | B2.23.2 / S3.3.0 | dashboard brain_version change | — |
| 69 | `AUTO-0015` | — | — | brain_update_… | B2.23.3 / S3.3.0 | dashboard brain_version change | — |
| 70 | `AUTO-0016` | — | — | brain_update_… | B2.23.4 / S3.3.0 | dashboard brain_version change | — |
| 71 | `EVO-063` | 2026-09-17 | R31-fix8 | brain | B2.23.5 / S3.3.0 | 教练建议的 command.turn_and_go 是死键码——prompt 要求教练输出但脑模型从未消费；y=-954 虚空场景教练不知高度 | 单测 |
| 72 | `EVO-064` | 2026-09-17 | t11 场景身份实测（负结果 + 记录更正） | infra | B2.23.4 / S3.3.0 | EVO-058 的 notes 把 scene_key 前缀漂移列为“下一步开放缺陷”，我在本轮报告里也据此宣称“场景身份稳定性是 P4.4 的真瓶颈”。… | **实测** |
| 73 | `EVO-065` | 2026-09-17 | t12 课程三态判定（不可观测≠失败） | infra | B2.23.5 / S3.3.0 | 课程目标的度量在预热期不可观测时被静默计为**失败**：脑重启后约 4 分钟内 /memory.json 的 disp_60s 为 null（位移追踪器预… | **实测** |
| 74 | `EVO-066` | 2026-09-17 | t13 契约审计：死旋钮清理 | skill | B2.23.5 / S3.4.0 | 把本次会话反复手工发现的“机制存在、报告成功、无法生效”缺陷族**系统化审计**：新增 scripts/audit_contract_pairs.py，对… | **实测** |
| 75 | `EVO-067` | 2026-09-17 | t14 双环度量 + Phase 6 归因仪表 | skill | B2.23.5 / S3.4.1 | 执行上一轮给出的建议“度量 Phase 6 收益、跟踪 P4.4 晋级”。新增只读度量工具 scripts/measure_evolution_healt… | **实测** |
| 76 | `EVO-068` | 2026-09-17 | t15 验证基线（回归可探测） | infra | B2.23.5 / S3.4.1 | 项目无法把进展与噪声分开：Windows 套件长期带约 40 个未分类失败，真实回归会被淹没——本轮为回答“我是否弄坏了什么”，不得不派子代理做一次基线归… | **实测** |
| 77 | `EVO-069` | 2026-09-17 | R31-fix9 | brain | B2.23.6 / S3.4.1 | 教练建议完全无法影响多巴胺系统——coach 看见虚空跳冲无效但无法传入奖惩信号 | 单测 |
| 78 | `EVO-070` | 2026-09-17 | t16 里程碑：首个本能晋级 + 课程阶梯晋级 | infra | B2.23.6 / S3.4.1 | 对 EVO-058（P4.4 本能固化可达化 + 课程渐进阶梯）与 EVO-065（课程三态判定）的端到端验证：此前两者都只有单元测试与受控注入证据，本轮… | **实测** |
| 79 | `EVO-071` | 2026-09-18 | t17 执行四条建议：度量工具化 + Phase 6 根因… | skill | B2.23.6 / S3.4.2 | 执行上一轮的四条建议。过程中**修正了我自己对两处失败的误判**（原记为 real-bug，实测均为 test-drift），并借助 EVO-067 上线… | **实测** |

### 2.4 档案可信度评估

1. **档案不完整**：最后一条 `EVO-071` 于 09-18 入库，而 09-21/09-22 有 17 次提交（含 1 次版本发布）未入库。
2. **20%（16/79）为机器占位**：`AUTO-0004`…`AUTO-0016` 与 `EVO-050` 只写了“版本变了、待补全”，
   按 agent.md 规则 15 本应补全的 trigger/changes/tests **至今为空**。
3. **记录顺序即写入顺序**：`EVO-033` 出现在第 46 位（在 `AUTO-0003` 之后），说明档案是追加式且存在跨会话交错写入。
4. **`tests` 字段的证据强度分层明显**：仅 13/79 条含实机/端到端字样，其余多为“编译通过”“N 项单测”。
   `EVO-061` 的 `tests` 字段就是 `"编译通过；实机验证 fallen 逃逸"`——编译通过不是验证。

---

## 3. 最近提交的修复验证状态矩阵（任务要求 2）

范围：`cf2f472`（最新）回溯至 `5c86272`（v2.23.12 发布），共 **17 个提交**。
判定口径：
- **实测** = 有运行期证据（进程/工件时间戳/外部报告/端到端断言）
- **单测** = 有针对性测试且当前通过
- **代码级已验证** = 用探针/静态读取确认了代码路径确实可达（本次新做）
- **仅代码提交** = 无任何测试、无运行期证据

| # | commit | 日期 | 主题 | 随行测试/证据 | 验证状态判定 |
|---|--------|------|------|---------------|--------------|
| 17 | `cf2f472` | 09-22 20:56 | README 全面更新（Brain v2.23.12 / Skill v3.5.0） | 仅 `fly64/README.md` | **文档**：与代码一致性核验见 §1、§4；模块行数/端点/39 参数数字已核对，但“39-param registry 作为 Coach+EVO+panel 单一事实源”与代码不符（Coach 不读注册表） |
| 16 | `879d983` | 09-22 18:22 | fix(EVO-072)：active_strategy 键名归一化 + coach 合并写入 | 新增 `tests/test_strategy_key_contract.py`（7 PIN） | **单测**：新增 PIN 全部通过；但归一化只处理“同段前缀”，真实文件 `exploration["escape.*"]` 死键仍在（§4.3），且 **evolution_history.json 未记录本条**（§2.4） |
| 15 | `ea509a9` | 09-22 18:03 | audit fix + memory 回路参数（39 参数 / 6 分区 / all wired） | **无新增测试**；`test_tunable_wiring.py` 未同步 | **部分失败**：探针实测 38/39 可达；`exploration.breakout_forward_bias` 被本次“修复”改成读 `_esc` 而注册段仍为 `exploration.*` → 反而变死；`reflex.cooldown_min` 无任何消费者仍标 wired=true；`test_tunable_wiring.py` 8 项断言因此失败（新增失败） |
| 14 | `5703efa` | 09-22 | 遥测补 forward/turn/jump_rate + 振荡反射位移释放条件 | 无新增测试 | **仅代码提交**：无测试或实机证据 |
| 13 | `d04264e` | 09-22 | SM64 WSLg 窗口屏幕外 → SDL_VIDEO_WINDOW_POS + 预设窗口位置 | `docs/wslg-display-verification-report.md`（09-21，11 项 PASS，SM64 PID 1284 运行 6h+） | **实测**（报告级证据） |
| 12 | `d719a60` | 09-22 | param history 持久化 + `/param-history.json` + Y 轴自适应 | 无新增测试 | **仅代码提交**：`artifacts/param_history.jsonl` 在磁盘上**不存在**，历史持久化无落盘证据 |
| 11 | `e0edc29` | 09-22 | launch_full.sh 双显示模式（wslg/xvfb）+ 窗口可见性监控 | 同上验证报告 | **实测**（报告级证据） |
| 10 | `9a5cb94` | 09-22 | 36 个参数说明中文化（用途/回路位置/推荐区间） | 无新增测试 | **已验证（文件级）**：现 39 个参数说明均为中文且含“用途/推荐” |
| 9 | `218c6c0` | 09-22 | wire 最后 10 个高价值参数（coach DAN + MB + navigation + escape） | 无新增测试 | **代码级已验证**（探针可达）；契约测试未同步 |
| 8 | `5b62706` | 09-22 | navigation + coach 回路参数（26 参数 / 5 分区） | 无新增测试 | **代码级已验证** |
| 7 | `d58b385` | 09-22 | merge：fly64-comprehensive-fix 团队交付 + 计划更新 | — | **合并提交** |
| 6 | `f3501e7` | 09-22 | wire all 21 params（自称 21/21 wired=True） | 无新增测试 | **部分不实**：当时 `test_tunable_wiring.py` 仍把 14 个参数列为 known-unwired，两处互相矛盾；现探针证实其中 14 个确实已接线 |
| 5 | `37724b8` | 09-21 | wire all 11 exploration/escape params + gate_* 进 flow.json 遥测 | 无新增测试 | **代码级已验证**（leaf 名可达）；但 `gate_forward_threshold`/`gate_jump_threshold` 仅进遥测，未驱动行为 |
| 4 | `85f2036` | 09-21 | wire 3 exploration params（loop_breakout_threshold/cliff_tangent_gain/revisit_penalty_scale） | 无新增测试 | **代码级已验证** |
| 3 | `b23364b` | 09-21 | fix evo-params renderParams 自 append bug | 无新增测试 | **仅代码提交** |
| 2 | `61e1e0d` | 09-21 | P0 参数写入冲突自愈 + P1 frontier 半径 20→50 + P2 evo-params 仪表板 | 无新增测试；commit 内含现场快照“turn_bias 0.25 on disk” | **部分验证**：P2 的历史持久化无 `param_history.jsonl` 落盘证据；自愈分支未在提交后 09-21/09-22 的实机运行中被观测 |
| 1 | `5c86272` | 09-21 18:44 | brain v2.23.12 / skill v3.5.0 — 探索死锁修复（burst 60→200t） | **无新增测试**；仅 main.py 4 行 | **仅代码提交**：① 200t burst 无任何实测证据；② 本次版本提升**打破三源一致**（`test_version_consistency.py` 期望 2.23.11，2 项失败）；③ `evolution_skill.SKILL_VERSION` 仍为 3.4.2 |

### 3.1 新鲜度证据（为什么 09-21/09-22 的改动普遍“未实测”）

| 工件 | 最后写入 | 含义 |
|------|----------|------|
| `fly64/artifacts/latest-00000…00060.npz`、`latest.jsonl`、`latest-session.trajectory.npz` | **2026-09-19 10:08 → 12:13** | 脑模型轨迹录制的最后一次实机运行在 **09-19 中午** |
| `fly64/skills/evolution_log.jsonl` | 2026-09-17 10:22 | EVO 试验日志停更 |
| `fly64/skills/coach_outcomes.jsonl` | 2026-09-17 18:14 | 教练证据库停更 |
| `fly64/skills/curriculum.json` | 2026-09-17 20:44 | 课程状态停更 |
| `fly64/skills/evolution_health_trend.jsonl` | 2026-09-20 23:56 | 双环健康快照最后一次 |
| `fly64/docs/wslg-display-verification-report.md` | 2026-09-22 16:12（内容日期 09-21） | 唯一覆盖 09-21 之后的**实测级**证据（SM64 窗口/仪表板在线） |
| `fly64/artifacts/param_history.jsonl` | **不存在** | `d719a60` 声称的历史持久化**无落盘证据** |

结论：`5c86272`（探索死锁 200t burst）、`61e1e0d`（P0 自愈 / P1 frontier 半径）、`d719a60`（param history）、
`5703efa`（遥测字段）、`ea509a9`/`879d983`（参数接线与键名归一化）在 **09-21 18:44 之后没有任何一次脑进程运行证据**。
其中 `5c86272` 与 `ea509a9` 直接改变行为回路，属于**高风险未验证改动**。

---

## 4. 参数系统状态核对（任务要求 3）

### 4.1 注册表总览

`skills/brain_tunable_params.json`：`version = 1.1.0`，`params` 共 **39** 条，
6 个分区（exploration 11 · escape 10 · reflex 2 · navigation 4 · coach 9 · memory 3），
**39 条全部 `wired: true`**，`wired_audited_at = 2026-09-17T20:52:38+08:00`。
各条含 `default/min/max/description`（中文，含用途与推荐区间）——`9a5cb94` 的中文化成果**已验证**。

### 4.2 逐参数接线清单（本次新增探针实测）

探针（`fly64/.tmp/_a3_param_route_probe.py`）复刻真实管线：
面板 `{pid: v}`（`web/evo-params.html:92`）→ `apply_strategy_update` 点号展开（`main.py:781`）
→ EVO-072 归一化循环（`main.py:1280-1290`）→ 对每个 pid 用**其读取端表达式所在的段**查值。
探针值 `0.123456789`（故意落在多个声明区间之外以便识别默认值回退）。

**结果：38/39 可达，1 个不可达。**

| pid | wired | 声明区间 | default | 运行期钳位 | 读取段 | 判定 |
|-----|-------|----------|---------|------------|--------|------|
| `exploration.turn_bias` | True | [0, 0.4] | 0.25 | [0, 0.25] | `exploration` | ✅ |
| `exploration.bold_explore_stuck_s` | True | [15, 180] | 60.0 | [1, 10] | `exploration` | ✅ ⚠️**与声明区间不相交** |
| `exploration.revisit_penalty_scale` | True | [0, 0.8] | 0.4 | — | `exploration` | ✅ |
| `exploration.gate_forward_threshold` | True | [0.1, 0.8] | 0.4 | — | `exploration` | ✅ |
| `exploration.gate_jump_threshold` | True | [0.5, 4] | 2.0 | — | `exploration` | ✅ |
| `exploration.cliff_tangent_gain` | True | [0, 3] | 1.0 | — | `exploration` | ✅ |
| `exploration.loop_breakout_threshold` | True | [0.3, 0.95] | 0.6 | — | `exploration` | ✅ |
| `exploration.stuck_ramp_cooldown` | True | [1, 15] | 5.0 | [1, 15] | `exploration` | ✅ |
| `exploration.visual_gain_novelty_boost` | True | [-0.2, 0.5] | 0.1 | — | `exploration` | ✅ |
| `exploration.dopamine_revisit_cost` | True | [0, 1] | 0.5 | — | `exploration` | ✅ |
| `exploration.breakout_forward_bias` | True | [0.15, 0.6] | 0.5 | [0.15, 0.6] | `escape   ← 声明段≠读取段` | ❌ **段失配**：写 exploration，读 `_esc` |
| `escape.commit_ticks` | True | [10, 150] | 50 | int() 无钳位 | `escape` | ✅ |
| `escape.forward_accum_max` | True | [0.2, 0.8] | 0.5 | 无钳位 | `escape` | ✅ |
| `escape.forward_accum_step` | True | [0.001, 0.02] | 0.005 | [0.001, 0.02] | `escape` | ✅ |
| `escape.commit_reinforce` | True | [0.05, 0.3] | 0.15 | [0.05, 0.3] | `escape` | ✅ |
| `escape.commit_suppress` | True | [0.02, 0.25] | 0.1 | [0.02, 0.25] | `escape` | ✅ |
| `escape.fallen_forward` | True | [0.05, 0.5] | 0.2 | 无钳位 | `escape` | ✅ |
| `escape.fallen_jump_boost` | True | [0.2, 0.6] | 0.35 | 无钳位 | `escape` | ✅ |
| `escape.fallen_switch_s` | True | [1, 10] | 3.0 | 无钳位 | `escape` | ✅ |
| `reflex.cooldown_min` | True | [0.5, 5] | 2.0 | — | `（无消费者）` | ❌ **死参数**：全仓零消费者 |
| `reflex.adaptive_cooldown_scale` | True | [0.01, 0.15] | 0.05 | [0.01, 0.15] | `reflex` | ✅ |
| `navigation.danger_weight` | True | [0, 3] | 1.2 | [0, 3] | `navigation` | ✅ |
| `navigation.frontier_weight` | True | [0, 3] | 0.7 | [0, 3] | `navigation` | ✅ |
| `coach.reward_gain` | True | [0, 1.5] | 0.4 | [0, 1.5] | `coach` | ✅ |
| `coach.dan_punish_stuck` | True | [0, 1] | 0.3 | [0, 1] | `coach` | ✅ |
| `coach.dan_punish_loop` | True | [0, 1] | 0.35 | [0, 1] | `coach` | ✅ |
| `coach.dan_reward_exploration` | True | [0, 1] | 0.2 | [0, 1] | `coach` | ✅ |
| `coach.dan_reward_progress` | True | [0, 1] | 0.3 | [0, 1] | `coach` | ✅ |
| `coach.dan_punish_fallen` | True | [0, 1] | 0.8 | [0, 1] | `coach` | ✅ |
| `coach.dan_punish_cliff` | True | [0, 1] | 0.4 | [0, 1] | `coach` | ✅ |
| `coach.mb_learning_rate` | True | [0.0001, 0.02] | 0.001 | [0.0001, 0.02] | `coach` | ✅ |
| `coach.mb_dopamine_threshold` | True | [0.05, 0.9] | 0.3 | [0.05, 0.9] | `coach` | ✅ |
| `navigation.steering_gain` | True | [0.01, 0.5] | 0.12 | [0.01, 0.5] | `navigation` | ✅ |
| `navigation.loop_break_stuck_s` | True | [10, 120] | 45.0 | [10, 120] | `navigation` | ✅ |
| `escape.escape_jump_drive` | True | [0.1, 1] | 0.45 | [0.1, 1] | `escape` | ✅ |
| `escape.bold_turn_drive` | True | [0.1, 1] | 0.35 | [0.1, 1] | `escape` | ✅ |
| `memory.recency_decay` | True | [0.999, 1] | 0.9995 | [0.999, 1] | `memory` | ✅ |
| `memory.failure_radius_cells` | True | [1.5, 6] | 3.0 | [1.5, 6] | `memory` | ✅ |
| `memory.revisit_punish_threshold` | True | [0.2, 0.8] | 0.5 | [0.2, 0.8] | `memory` | ✅ |

> **表内 ✅ 的语义限定**：✅ 表示“该 pid 的点号路径能到达 `main.py` 中对应的
> `_expl/_esc/_as_raw[sec].get(leaf)` 读取点”。它**不等于**“该参数改变了行为”：
> `exploration.gate_forward_threshold` / `gate_jump_threshold` 的读取点位于
> `main.py:2418,2420` 的 **flow.json 遥测字典**内，只把值暴露给仪表板，**不驱动任何运动池**；
> 同理 `escape.commit_ticks` 与 `commit_ticks_explore` 之间还隔着
> `_expl.get("commit_ticks_explore", 250)` 这一注册表外键（`active_strategy.json` 里不存在）。

### 4.3 三个具体缺陷（含代码位置）

**(a) `exploration.breakout_forward_bias` — 声明段 ≠ 读取段（`ea509a9` 引入）**

```python
# fly64/fly64/main.py:1329-1333   （当前 HEAD）
# Wire breakout_forward_bias into model (max escape forward gain)
# NOTE: these five live in escape/reflex sections — read from
# _esc, NOT _expl (registry pids are escape.*/reflex.*).
model._max_escape_forward = max(0.15, min(0.60, float(
    _esc.get("breakout_forward_bias", 0.50))))
```

而注册表里该 pid 是 **`exploration.breakout_forward_bias`**（`brain_tunable_params.json:80`），
`ea509a9` 的注册表 diff **没有**把它改名。`git show ea509a9 -- main.py` 显示这次提交把
`_expl.get("breakout_forward_bias", 0.50)` 改成了 `_esc.get("breakout_forward_bias", 0.50)`：
**改动前是对的，改动后变成死参数**。注释里“these five live in escape/reflex sections”的前提
对 5 个中的 1 个（就是这一个）是错的。

实测后果：磁盘上 `exploration.breakout_forward_bias = 0.2`（`active_strategy.json:19`），
而 `_esc` 段**没有**该键 → 读取端每 tick 取默认 **0.50**。面板滑块、EVO 变异、Phase 6 搜索维度全部空转。

**(b) `reflex.cooldown_min` — wired=true 但全仓零消费者**

全仓 grep（`docs` / `skills` / `tests` 之外）只命中：注册表自身、`active_strategy.json:35`（值 2.0）、
`docs/declared-not-implemented.md:49`（登记为 `_implement / retire_`）、
`evolution_skill.py:1774`（审计说明文本）。`fly64/`、`plugin/` 的生产代码**没有**任何读点；
反射的真实概念是 `cooldown_duration`。这属于 `EVO-066` 已识别、`EVO-068` 已登记，但 `ea509a9`
仍把它标成 `wired: true` 的**登记册回归**。

**(c) `active_strategy.json` 中的跨段点号死键（EVO-072 归一化未覆盖）**

磁盘实况（`skills/active_strategy.json:2-20`）：

```
"exploration": {
  "bold_turn_bias": 0.25,
  "escape.commit_ticks": 125.04821717847143,
  "escape.forward_accum_max": 0.2066931309445445,
  "escape.forward_accum_step": 0.015757426446775843,
  "escape.commit_reinforce": 0.1820265798466096,
  "escape.commit_suppress": 0.11829571149170438,
  ... 清白键 11 个 ...
}
...
"escape": { "commit_ticks": 50, "forward_accum_max": 0.5, "forward_accum_step": 0.005,
             "commit_reinforce": 0.15, "commit_suppress": 0.1, ... }
```

EVO-072 的归一化实现（`main.py:1284` / `evolution_skill.py:2026`）是 `prefix = sec + "."`，
即**只**把 `exploration["exploration.xxx"]` 改成 `exploration["xxx"]`；
`exploration` 段里的 `escape.*` 死键**永远不会被转成 `escape["xxx"]`**，也**永远不会被删除**。

后果：EVO 曾写进 `exploration["escape.forward_accum_step"] = 0.01576` 的进化值，
在 `escape["forward_accum_step"] = 0.005`（默认值）存在的情况下被读取端忽略——
即“机制存在、报告成功、无法生效”缺陷家族的**第 8 例**，且它就在“修复该家族”的同一次提交旁边。

### 4.4 注册表声明区间 vs 运行期钳位：两处不相交

| pid | 注册表区间 | `main.py` 运行期钳位 | 影响 |
|-----|-----------|----------------------|------|
| `exploration.bold_explore_stuck_s` | `[15, 180]`，default 60 | `[1, 10]`（main.py:1298） | **两区间不相交**——EVO 采样到的任何合法值都被钳到 10；注册表描述却在推荐“5~10”，自相矛盾 |
| `exploration.turn_bias` | `[0.0, 0.4]` | `[0.0, 0.25]`（main.py:1296） | 上界 37.5% 的搜索空间不可达；注释写“Clamp turn_bias to [0, 0.4]”但代码是 0.25 |

这两处使 Phase 6 的“活维度”在报告上移动、在行为上不动，与 EVO-071 诊断的“适应度无法归因”是同一后果。

### 4.5 `ea509a9` “5 个死参数”逐项结论

| ea509a9 声称修复的 5 个 | 当前是否真的可达 | 说明 |
|--------------------------|------------------|------|
| `escape.forward_accum_step` | ✅ | 读 `_esc`，注册段也是 `escape.*` |
| `escape.commit_reinforce` | ✅ | 同上 |
| `escape.commit_suppress` | ✅ | 同上 |
| `reflex.adaptive_cooldown_scale` | ✅ | 读 `_as_raw["reflex"]`，一致 |
| `exploration.breakout_forward_bias` | ❌ | 被本次提交改成读 `_esc`，与注册段不符 |

**结论：4/5 修复，1/5 被该提交本身破坏。** 同一次提交新增的 3 个 memory 参数
（`recency_decay` / `failure_radius_cells` / `revisit_punish_threshold`）**全部可达**（探针 38 通过项之一）。

---

## 5. 测试基线现状（任务要求 4）

### 5.1 规模与当前结果

| 指标 | 值 | 命令 |
|------|----|------|
| `fly64/tests/test_*.py` 文件数 | **89** | `(Get-ChildItem tests -Filter test_*.py).Count` |
| `fly64/tests/*.py` 总数（含分析/探针脚本） | 111 | 同上（无 `test_` 限定） |
| pytest 收集用例 | **1228** | `python -m pytest tests --collect-only -q` |
| JUnit 汇总用例 | **1229**（= 1130 + 62 + 37） | `python -m pytest tests -q --junitxml=.tmp/a3_junit.xml` |
| 当前结果（Windows / Python 3.11.9 / pytest 9.0.3 / 248.9 s） | **62 failed · 1130 passed · 37 skipped** | 同上 |

> 收集数 1228 与执行数 1229 差 1 项，**未定位原因**（可能为运行期动态参数化展开）；
> 两处均为本次实测输出，此处如实并列而非取整。

### 5.2 与 EVO-068 基线的比对（“约 40 个未分类失败是否仍在”）

**基线文件**：`tests/known_failures.win32.json`，`recorded_at 2026-09-18T08:05:26Z`，`count = 38`

| 基线 cause | 条数 | 含义 |
|------------|------|------|
| `aspirational` | 16 | 断言的功能在全仓零实现（ENHANCED_PROMPT_TEMPLATE 未实现、`_saturation_recovery_counter` 零出现） |
| `environment` | 14 | Windows 环境缺口（time.clock_gettime_ns / gbk 解码 / .nc 缓存 / 原生桥） |
| `test-drift` | 3 | 功能仍在、断言过时 |
| `real-bug` | 2 | 真实缺陷（optic_flow 性能 29.35ms vs 5ms 预算；启动器锁） |
| `unknown` | 3 | **未分类**（`note` 为空） |

| 比对项 | 值 |
|--------|----|
| 当前失败总数 | 62 |
| **NEW（不在基线中）** | **34** |
| 基线中仍失败 | 28 |
| **基线中已通过（基线腐化）** | **10** |

**对任务原问题的直接回答：**
- EVO-068 说的“约 40 个失败”**仍在**（现在 62 个，比当时更多）。
- EVO-068 声称的 **“0 未分类”已不成立**：win32 基线里重新出现 **3 条 `cause=unknown`、`note` 为空**的条目：
  - `tests/test_autonomy_regression.py::TestVersionContract::test_brain_version_in_skills_md_round_table`
  - `tests/test_coach_pipeline.py::TestStrategyExecution::test_fallen_recovery_has_params`
  - `tests/test_regression_detector.py::TestDetectorDetects::test_reports_clean_against_its_own_baseline`
- 由于基线自 09-18 未刷新，`scripts/check_regressions.py` 会把 34 个 NEW + 10 个“已通过条目”都算作异常，
  即**回归门禁当前为红**，`--strict` 也会因基线腐化失败。

### 5.3 当前 62 个失败的文件分布

| 文件 | 失败数 |
|------|--------|
| `test_autonomy_regression.py` | 2 |
| `test_coach_advice_fix.py` | 1 |
| `test_coach_dopamine.py` | 1 |
| `test_coach_pipeline.py` | 2 |
| `test_dan_shaping.py` | 1 |
| `test_evolution_capability.py` | 3 |
| `test_fix_executor.py` | 1 |
| `test_fix_template_interpreter.py` | 11 |
| `test_invariants.py` | 4 |
| `test_mbon_saturation.py` | 8 |
| `test_mbon_skill_capability.py` | 1 |
| `test_optic_flow.py` | 1 |
| `test_p1_neural_takeover.py` | 2 |
| `test_r31fix3_reward_reshaping.py` | 1 |
| `test_regression_detector.py` | 1 |
| `test_retina_calibration.py` | 1 |
| `test_trajectory_height.py` | 1 |
| `test_tunable_wiring.py` | 8 |
| `test_version_consistency.py` | 2 |
| `test_what_i_see_protocol.py` | 10 |

**34 个 NEW 的归因分层**：

| 归因 | 条数 | 明细 |
|------|------|------|
| 直接由 09-21/09-22 参数接线与版本提升引起 | 14 | `test_tunable_wiring.py` 8（契约仍是“7 wired / 14 unwired”）+ `test_version_consistency.py` 2 + `test_mbon_saturation.py::TestMbonSaturationHomeostasis` 3 + `test_autonomy_regression.py::TestVersionContract::test_skill_version_mirror` 1 |
| 由基线自身的 3 条 `cause=unknown` 引起 | 1 | `test_regression_detector.py::TestBaselineIsWellFormed::test_every_entry_has_a_cause_and_note` |
| 未提交的在途工作（`git status` 为 `??`） | 11 | `test_fix_template_interpreter.py` 11 —— `test_fix_template_interpreter.py` 与 `skills/fix_template_interpreter.py` 在工作树中均为**未跟踪新文件** |
| 其余未归因 | 8 | `test_coach_advice_fix` 1 · `test_coach_pipeline` 1（需活体 GLM 返回 advice）· `test_dan_shaping` 1 · `test_evolution_capability` 2 · `test_fix_executor` 1 · `test_p1_neural_takeover` 1 · `test_retina_calibration` 1 |

### 5.4 测试隔离缺陷（新发现，与 EVO-068 的验证基线目标直接冲突）

`fly64/tests/test_t3_handshake.py` **没有测试函数**，但有模块级可执行代码：

```python
# fly64/tests/test_t3_handshake.py:1-20（节选）
import sys, json, time, threading
sys.path.insert(0, "/root/fly64")
from plugin.llm_consult import GLMConsultant, RESPONSE_PATH
...
def dsh_responder():
    ...
        RESPONSE_PATH.write_text(json.dumps({
            "advice": "[DSH 教官] 演示：检测到 micro_loop 零位移，向 opening 扇区方向突围 2.5s",
            "strategy": {"exploration": {"turn_bias": 0.4}},
        }, ensure_ascii=False), encoding="utf-8")
...
sub = GLMConsultant(transport="subagent")        # 默认路径 = 真实 plugin/
out = sub.consult({"kind": "test", "stuck_duration": 100.0}, frame_b64=None)
```

pytest 收集该模块时会 **import 它 → 模块级代码执行**，于是：

- `plugin/.consult_request.json`、`plugin/.consult_response.json` 被**真实写入**
  （全量运行期间 mtime 22:35:39 / 22:35:43；`.consult_response.json` 的内容与该文件第 13–16 行**逐字节相同**）；
- 这两个文件是**被 git 跟踪**的（`git status` 显示 ` M fly64/plugin/.consult_request.json`）。

`conftest.py` 只做了 `os.environ["FLY64_EVIDENCE_DIR"] = tmpdir`，覆盖 `coach_outcomes.jsonl` /
`.pending_outcome.json` 一类路径，**不覆盖** consult 握手文件，也不覆盖 `skills/active_strategy.json`。

补充观测（**未能归因，列为待验证项**）：同一批全量运行期间 `skills/active_strategy.json` 的 mtime 前进
（22:32:58 → 22:37:29），其 `__generation` 从 149 变为 155。`__generation` 在全仓只有
`evolution_skill.py:2059`（`BrainMutator._inject`）一个写点；`pytest tests --collect-only -q` 不会改动该文件
（已用哈希前后比对确认）。因此**要么**存在未被路径隔离的测试写点，**要么**驻留循环进程在运行；
无论哪种，都意味着“测试运行”与“生产状态”当前不可区分。

### 5.5 结论

项目在 09-18 建立的“验证基线（回归可探测）”机制**本身仍在、且探测能力有效**（`test_regression_detector`
的注入探针用例通过），但：
1. **基线未随 09-21/09-22 的 17 次提交刷新** → 现在一次全量运行会冒出 34 个 NEW，噪声远超信号；
2. **基线双向腐化**（10 条已通过仍在基线里）；
3. **基线里重新出现未分类条目**（3 条 `unknown`），EVO-068 的“0 未分类”目标已回退；
4. **存在跨进程/跨测试的生产工件写入**，使“这次失败是不是我弄坏的”依然难以回答——正是 EVO-068 想解决的问题。

---

## 6. 对下一步执行方案的影响（给下游的输入）

| 优先级 | 动作 | 依据 |
|--------|------|------|
| **P0** | 统一版本三源：`main.py` / `skills.md` 双徽章 / `evolution_history.json.canonical_versions` / `evolution_skill.SKILL_VERSION`，并更新 `test_version_consistency.py` 的 `EXPECTED` | §1.1、§1.2 |
| **P0** | 修 `exploration.breakout_forward_bias`：读取端改回 `_expl`，或注册表 pid 改为 `escape.breakout_forward_bias`（二选一，并同步 `active_strategy.json` 既有值） | §4.2(a) |
| **P0** | 修 `reflex.cooldown_min`：补真实消费者（反射 `cooldown_duration`）或标 `wired: false` / 退役 | §4.2(b) |
| **P0** | 刷新 `known_failures.win32.json` / `.linux.json`：重跑基线、把 34 个 NEW 逐条归因（至少填 cause+note），并把 3 条 `unknown` 分类 | §5.2 |
| **P1** | 把 EVO-072 补录进 `evolution_history.json`（含 trigger/changes/tests），并刷新 `canonical_versions` | §2.4 |
| **P1** | 归一化逻辑升级为“跨段前缀感知”：`exploration` 段内的 `escape.*` / `reflex.*` 键应迁移到对应段或显式上报，而非静默保留 | §4.3(c) |
| **P1** | 对齐 `bold_explore_stuck_s`（[15,180] vs [1,10]）与 `turn_bias`（[0,0.4] vs [0,0.25]）的注册区间与运行期钳位 | §4.4 |
| **P1** | 消解 `test_tunable_wiring.py` 的 8 项失败：要么把契约更新为当前 39 参数事实，要么承认 39 个并未全部接线（推荐前者并**先修 P0 的两个死参数**） | §4.2、§5.3 |
| **P1** | 在 `conftest.py` 中一并重定向 `plugin/.consult_request.json` / `.consult_response.json` 与 `skills/active_strategy.json`；`test_t3_handshake.py` 改为 `if __name__ == "__main__"` 或加 `pytest.skip` | §5.4 |
| **P2** | 补齐 09-21/09-22 高风险改动的实机验证：`5c86272`（200t burst）、`61e1e0d`（P0 自愈）、`d719a60`（param history 落盘） | §3.1 |
| **P2** | 统一 Coach 与注册表的可调键集合（Coach 目前另有注册表外的 `escape.stuck_threshold_s`） | §1.4 |

---

## 7. 证据与复现

### 7.1 本文件所用命令

```powershell
# 版本三源
Select-String -Path fly64\fly64\main.py,fly64\skills\skills.md,fly64\skills\evolution_skill.py -Pattern 'BRAIN_VERSION|SKILL_VERSION'
python -c "import json;print(json.load(open('fly64/skills/evolution_history.json',encoding='utf-8'))['canonical_versions'])"
# 测试基线
cd fly64; python -m pytest tests -q --tb=no -p no:cacheprovider --junitxml=.tmp/a3_junit.xml
python .tmp/_a3_build_doc.py         # 本文件（含 §5 的 NEW/仍失败/已通过三组比对）
# 参数接线探针（复刻面板→apply_strategy_update→EVO-072 归一化→读取端）
python .tmp/_a3_param_route_probe.py
# 关键提交
git show ea509a9 -- fly64/fly64/main.py fly64/skills/brain_tunable_params.json
git show 879d983 -- fly64/fly64/main.py fly64/skills/evolution_skill.py
git show 5c86272
```

### 7.2 本次生成的辅助工件（可直接复查）

| 路径 | 内容 |
|------|------|
| `fly64/.tmp/_a3_build_doc.py` | 本文件的生成器（表格全部机器生成） |
| `fly64/.tmp/_a3_param_route_probe.py` | 参数接线探针（39 pid 逐条路由实测） |
| `fly64/.tmp/_a3_junit.xml` | 全量 pytest JUnit 报告（62/1130/37） |
| `fly64/.tmp/_a3_evo_dump.txt` | 79 条进化记录的完整字段转储 |
| `fly64/.tmp/_a3_params.txt` | 39 个参数的原始 JSON 转储 |
| `fly64/.tmp/_a3_knownfail.txt` | win32 基线 38 条逐条 cause+note |
| `fly64/.tmp/_a3_test_delta.txt` | NEW / 仍失败 / 基线已通过 三组清单 |

### 7.3 未能取证 / 待验证项（诚实声明）

1. **09-21/09-22 的实机运行状态无法从本仓库证据确定**：WSL 侧 `/root/fly64` 是独立副本，
   其进程日志、`/root/fly64/artifacts/` 不在本仓库；本报告只能证明“Windows 树上的轨迹/试验工件在 09-19 之后停更”。
2. **`skills/active_strategy.json` 在测试期间被改写的确切写点未定位**（§5.4 补充观测）；
   已排除：`pytest --collect-only`、`test_plugin_mhr.py`、`test_what_i_see_protocol.py`（哈希前后不变）。
3. **`exploration.breakout_forward_bias` 是否曾在实机上被人工设过值无法区分**：
   磁盘现值 0.2 在注册区间内，可能是面板写入或 EVO 写入；但无论来源如何，读取端都取 0.50。
4. **`known_failures.linux.json`（24 条）未在本机复跑**（本机为 Windows），
   只做了与其自身内容的静态核对。
5. 本报告**不涉及**对话日志/session 计数口径，故与团队内部关于 9/11 session、342/959 提问的争论无关。
