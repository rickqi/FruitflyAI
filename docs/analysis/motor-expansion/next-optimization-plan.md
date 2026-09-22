# 运动能力扩展 · 下一步优化计划（分步实施）

基准：Brain v2.16.0 / Skill v3.0.0（五阶段 motor expansion 已落地，见本目录 execution-plan.md）

> **状态**: 🟢 已实现 (Implemented)  
> 此文档中的设计方案已编码实现并部署。实现详情参见对应代码文件与测试。
>
验收锚点沿用实机标准：锁门场景首破 stuck 死循环（PUNCH）、小目标 DIVE 命中率、`evolution_history.json` 中新 pattern 首条自动修复记录。

---

## M1 梯队 · 行为瓶颈直击（本周，~2.5 天）

### 任务 M1.1 — 预存债务清理（0.5~1 天，先行）
> 三笔实机验证期间确认的债务，阻塞后续 EVO 闭环质量。

| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | 修复 `skills/fix_catalog.json` 第 339 行 JSON 语法错误（先备份，修正后 `json.load` 全文校验 + EVO 常驻循环跑一轮确认 fix 登记成功） | `python3 -c "import json;json.load(open('skills/fix_catalog.json'))"` 退出 0 |
| 2 | `tests/test_evolution_capability.py` 隔离修复：pipeline 的 history/documenter 路径改指 `tmp_path`，不再写仓库默认 `skills/evolution_history.json` | 跑完测试后 `git status skills/evolution_history.json` 干净 |
| 3 | P1 直写 KPI 收编（main.py 26>20 行欠账）：残余直写逐处审阅——反射类移入 `memory.py` 反射回路或以 `apply_*` 辅助函数收编（同 Phase 2 `apply_phase` 模式），不可收编者在 test 注释登记豁免理由 | `test_control_write_count_shrunk` 转绿且豁免清单≤3 条 |
| 4 | BRAIN_VERSION → 2.17.0 + skills.md 轮次表同步 | `test_brain_version_in_skills_md_round_table` 过 |

### 任务 M1.2 — 启用 PUNCH / DIVE（1 天）
> 相位脚本与状态机已就绪（v2.15.0），只补触发门控。

| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | PUNCH 门控：`door_frame_score > 0.4` 或交互模式激活（`model.interactive_near`）+ GROUNDED + 静止（`|x|<8, y<8`） | `test_motor_primitives.py` 新门控用例 |
| 2 | DIVE 门控：AIRBORNE + P2 小目标锁定（`target_count>0` 且锁定持续>0.3s） | 同上 |
| 3 | main.py 白名单开关：`active_strategy.json` 新增 `primitives.enabled` 列表（默认 `["longjump","backflip","groundpound","punch","dive"]`），`cpg.request` 前检查 | 策略热加载测试 |
| 4 | 实机验收：锁门场景观察 PUNCH 触发与门状态变化；gold spot 场景观察 DIVE | decision_source 出现 `cpg_primitive:punch/dive` |

### 任务 M1.3 — EVO 效果量化接线（0.5~1 天）
> `primitive_timeout/zero_disp` pattern 已入目录，VerificationEngine 尚未消费原语遥测。

| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | `VerificationEngine` 评分公式扩展：窗口内有 cpg 完成时，score = 0.5×stuck 降幅 + 0.2×覆盖率 + 0.3×`primitive_disp` 归一化（30u 封顶） | 单测：disp=0 → score 上限 0.7 |
| 2 | `record_fix` 的 baseline 快照加入 `cpg.completed/aborted/disp` 三键 | catalog 条目含新键 |
| 3 | 实机跑 EVO 常驻循环 ≥1h，确认 `primitive_zero_disp` 或 `primitive_timeout` 首条 finding 落盘 | `evolution_log.jsonl` 出现新 pattern 条目 |

---

## M2 梯队 · 健壮性与数据质量（下周，~3 天）

### 任务 M2.1 — MHR 教官层原语策略（1 天）
| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | `active_strategy.json` schema 扩展 `primitives: {enabled[], prefer: {scene_tag: primitive}}` | schema 校验测试 |
| 2 | `plugin/runner.py` prompt 注入当前可用原语清单与近期成败统计（`cpg.status()` + disp），GLM 可下发偏好 | `test_plugin_mhr` 用例 |
| 3 | `check_help_needed` 增加 `primitive_ineffective`（连续 3 次 zero_disp → 求助） | 单测 |
| 4 | 实机：斜坡场景教官建议 `prefer: {ramp: longjump}` 热加载生效 | `/active_strategy.json` → 行为变化 |

### 任务 M2.2 — pose 状态机精化（1.5 天）
| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | `MarioState` 增 `WALL`（贴墙 + 摇杆顶死 + 转向池持续同向）与 `SLIDING`（坡面 + 位移向下） | 状态机单测 |
| 2 | 墙面判定信号：复用 `wall_score` + 16 扇区单侧贴脸 + `filtered_x` 饱和 | 单测 |
| 3 | SLIDING 态抑制 longjump 误触发（滑行中长跳无效） | 非法组合用例 |
| 4 | 实机采样验证状态机准确率（人工标注 100 个 tick 对照） | ≥90% 一致率 |

### 任务 M2.3 — 踢墙跳 + 侧空翻（1 天，依赖 M2.2）
| 步骤 | 内容 | 验证 |
|---|---|---|
| 1 | `WALL_JUMP` 原语：WALL 态 + A 脉冲（远离墙向 stick），纯 A 键零桥接改动 | 相位脚本测试 |
| 2 | `SIDE_FLIP`：转向反转检测（`filtered_x` 过零且速率>阈值）+ A | 同上 |
| 3 | 级联启用 + EVO 位移验证 | 实机非零位移 |

---

## M3 梯队 · 学习闭环（后续，~2 天）

### 任务 M3.1 — MBON 原语列学习效果 A/B 评估（0.5 天）
| 步骤 | 内容 |
|---|---|
| 1 | 分析脚本：`weights[:, 5:9]` 在原语成败前后 30s 的变化统计（读 `/flow.json` 的 `mb_mbon_*` + `evolution_log` 时间戳对齐） |
| 2 | 判据：成功原语对应列 30s 后均值显著高于失败列（配对 t 检验，n≥20 事件） |
| 3 | 产出：`docs/analysis/motor-expansion/mbon-learning-evaluation.md`，若方向错误 → 检查 `add_primitive_outcome` 的 dopamine 符号通路 |

### 任务 M3.2 — 长跳门控 MBON 闭环（1 天，依赖 M3.1 通过）
| 步骤 | 内容 |
|---|---|
| 1 | `longjump_bias`（MBON[8]）输出 > 0.3 时作为 `cpg.request(LONG_JUMP)` 的附加许可（替代部分硬编码条件，降低 `stuck>3s` 到 `>1.5s`） |
| 2 | A/B 实机对照：规则式 vs MBON 辅助门控的逃逸位移与误触发率 |
| 3 | 门禁：误触发率不升 + 平均逃逸时间下降才转正 |

### 任务 M3.3 — Phase 4 建议项收尾（S1–S3，各 0.5~1 天，可拆散进 EVO 轮）
- S1 Causal Timeline b/z 动作标记（ACTION 泳道）
- S2 Escape Events 表 `cpg_primitive_*` 事件类型 + 行点击回放
- S3 Coach 面板展示 primitives 策略段

---

## 执行纪律（沿用 EVO 七步制度）

每个任务收尾必须：测试 PIN 化 → `BRAIN_VERSION` 递增（仅脑侧变更）→ `skills/evolution_history.json` 完整记录 → `consolidate.sh` 制度化重启 → 实机验收锚点核对 → README 轮次表同步。

风险与回滚不变式：原语白名单热开关（随时禁用任一原语）、2s 熔断、级联优先级不变、`decision_source`/遥测只做加法演进。

---

*生成于 v2.16.0 落地后（2026-09-16）。M1 三任务完成后建议回看本计划，按 M3.1 的评估结果决定 M3.2 是否执行。*
