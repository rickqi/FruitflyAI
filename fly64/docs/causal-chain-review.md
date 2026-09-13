# 视觉神经因果链路方案 · 最终评审汇总（任务 t4 · reviewer）

> 评审对象：t1 链路分析（会话产出）、t2 `causal-chain-ui-design.md` + `causal-chain-prototype.html`、
> t3 `causal-chain-implementation.md`、t5 `skills/skills.md` 扩展 + `skills/neural_viz_skill.py`。
> 评审基线：`docs/dashboard-design.md` 设计准则、8765 现有五段布局、F643 schema=3 协议、50Hz/10Hz/1Hz 性能约束。
>
> **结论：PASS（含 4 项非阻塞修订建议，见 §4，需在对应实施阶段落实）。**

## 1. 链路可解释性完整性 — ✅ 通过

- t2 §8 覆盖表将 t1 全部 10 项缺失中间量（16 扇区对比度、ON/OFF τ、边缘方向、optic flow 三量、LIF 分离、门控、cliff/stuck 置信度、级联优先级、ack 闭环、单帧回放）逐一映射到展示位置，无遗漏。
- 「C 因果解释卡（机制因果、单帧）+ B 时间轴（时间因果、回放）」双联结构同时回答"现在为什么"与"刚才怎么发生"，方案 D（Sankey）否决理由成立（非守恒量、抖动）。
- 原型 `causal-chain-prototype.html` 为自包含演示，五段链 + 扇区叠加 + 四泳道 + scrub 回放可交互验证。

## 2. 可行性（遥测开销 / 协议兼容 / 性能） — ✅ 通过（实测验证）

- **协议兼容（实测）**：`test_dashboard_protocol.py` 与 `test_dashboard_js.py` 在当前工作区全部通过。t3 的加法演进论证正确：JSON meta 加键对旧 `decodePacket` 透明；二进制 payload（activity[n]+eyes+change）布局不变，`len(payload)` 断言不受影响；`test_observation_does_not_change_model` 只读性保障仍在。
- **性能**：扇区计算仅在新帧沿（10Hz）执行并复用同一 `delta` 数组；50 tick 中 40 tick 仅追加标量；发布增量 <4KB/s（sector 用 int[16]+uint16 bitmask 而非 float/bool 数组，省约 70%）；因果卡 200ms 节流（5Hz）远低于 1Hz 发布节奏，无渲染压力。量化合理。
- **守恒边界**：`causal` 快照由 main.py 注入、Observatory 只读消费，不回写模型——与 dashboard-design.md "read-only observer / never feed dashboard values back" 原则一致。
- **既有失败排除（实测）**：本机 8 个 test_memory、3 个 test_retina、1 个 test_optic_flow 失败经 git stash 基线对照确认为 HEAD 既有问题，与本次交付无关。

## 3. 与 dashboard-design.md 及现有布局一致性 — ✅ 通过（有条件）

- 增量式"覆盖层 + 新 section"不推翻五段布局，符合"compact 840×900 布局、去旋转、短历史、冻结语义"的既有决策；因果卡窄屏纵向折叠与"小屏可滚动不裁剪"一致。
- 新增紫（判断）/绿（行动）层色延续"类别用色相区分、量级用明度 ramp"的配色准则；preempt 降饱和+删除线直观表达仲裁，未引入 rainbow/threshold 型反模式。
- **条件**：ringBuffer 120s 回放偏离了设计文档"浏览器至多保留 10s records"的既定原则；新 section 也超出文档的仪表清单。落地时必须同步更新 `docs/dashboard-design.md`（见 §4-R1）。

## 4. 修订建议（非阻塞，按实施阶段落实）

- **R1（P0/P2，medium）**：ringBuffer 120s 与因果卡/时间轴 section 落地时，同步更新 `docs/dashboard-design.md`（仪表表新增 Causal Card / Timeline 行，修订 "ten seconds of records" 表述为"实时 10s + 回放快照 120s"），保持文档为单一事实源。
- **R2（P1，medium）**：`decision_source` 枚举缺 collision 分支。main.py L508 存在独立的 pre-emptive collision avoidance（在非 escape/reflex 时触发），t3 §1.3 注入伪码会把collision 规避误标为 `escape`。枚举应为 `cliff_reflex│anomaly_reflex│escape│collision_avoid│jump│steering`，并补一条验收断言：`decision_source` 与该 tick 实际发出的 control 语义一致（抽样对照）。
- **R3（P1，low）**：t2 §5.1 与 t3 §1.2 的字段类型不一致（float[16]+bool[16] vs int[16]+uint16 bitmask）。以 t3 为准；建议在 t2 文档加一行"实施以 causal-chain-implementation.md §1.2 为准"避免后续实现者取歧义。
- **R4（t5，low）**：`CausalAnalyzer.signal_to_action_latency` 以 `x != 0` 作为"响应"判据会把普通转向误计为 cliff 响应；且 cliff_confirmed 恒为 True 的录制段永不结算（返回 None）。可接受为近似指标，但应在 skills.md 标注"近似值，精确延迟以 P3 前端因果弧线为准"。另：Windows GBK 控制台下报告中文输出乱码（文件本身 UTF-8 正常），可在 CLI 加 `encoding='utf-8'` 写文件已达标，控制台打印无需处理。

## 5. skills 扩展专项评审 — ✅ 通过

- `skills.md` 新章节字段表与 t3 §1.2 一一对应，含 causal_schema 特性检测、DataCollector 采集配置、3 步验证法、Trigger keywords，文档完备。
- `neural_viz_skill.py` 实测（本评审）：`--input` 离线分析正常出报告；source 分布 / preempt 事件 / gate_flap 检测正确（mock 数据 4 行 → findings=1 gate_forward_flap）；全字段 `.get()` 容错，P0 未上线时自动降级。与 evolution_agent/evolution_skill import 兼容（新增键对旧 DataCollector 透明），只读原则一致，无新依赖。
- 缺陷仅 R4（low），不阻塞。

## 6. 验收标准核对（t4 contract）

| 标准 | 结论 | 证据 |
|---|---|---|
| 评审覆盖 t1/t2/t3 全部交付物（含 t5） | ✅ | §1–§3、§5，四份文档+原型逐一核对 |
| 链路可解释性有结论 | ✅ | §1 通过（10 项中间量全覆盖） |
| 性能可行性有结论 | ✅ | §2 通过（<4KB/s、10Hz 帧沿、5Hz 渲染节流，协议测试实测通过） |
| 与 dashboard-design.md 一致性有结论 | ✅ | §3 通过（条件：R1 文档同步） |
| pass 或具体 findings | ✅ | PASS + R1–R4 |
| 汇总最终建议文档 | ✅ | 本文件 `fly64/docs/causal-chain-review.md` |

## 7. 最终建议（一句话）

采纳 **C+B 融合主方案**，按 P0（纯前端因果卡）→ P1（telemetry 因果字段+decision_source，落实 R2 枚举）→ P2（扇区叠加+时间轴）→ P3（ringBuffer 回放+因果弧线）顺序实施；skills 离线分析技能随 P1 上线即可用；每阶段合入时同步更新 `dashboard-design.md`（R1）。
