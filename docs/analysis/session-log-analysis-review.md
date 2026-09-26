# t4 独立核验报告：会话日志分析（t2）与行动建议（t3）准确性审查

> **审查时间**: 2026-09-24  
> **审查者**: reviewer  
> **审查范围**: `docs/analysis/session-log-analysis.md`（t2）+ `docs/analysis/session-log-recommendations.md`（t3）  
> **方法论**: 独立回到原始 JSONL、当前代码（grep/read/Python 脚本）与系统文件逐条核验  
> **注意**: 本报告不修改 t2/t3/t5 的产出，仅记录发现；如有返修需求由 captain 决定

---

## 目录

1. [整体可信度评级](#1-整体可信度评级)
2. [数据质量核验](#2-数据质量核验)
3. [抽样回溯核验（10 项）](#3-抽样回溯核验)
4. [路径与引用校验](#4-路径与引用校验)
5. [当前状态一致性](#5-当前状态一致性)
6. [control.x 旁路计数专项裁定](#6-controlx-旁路计数专项裁定)
7. [遗漏审计](#7-遗漏审计)
8. [过度推断审计](#8-过度推断审计)
9. [必须修正条目清单](#9-必须修正条目清单)
10. [建议清单（可选）](#10-建议清单)

---

## 1. 整体可信度评级

| 维度 | 评级 | 依据 |
|:----|:----:|------|
| **数据质量** | 🟢 **高** | t5 修复后的工具计数、编码、首条消息均通过独立校验 |
| **主题分析** | 🟡 **中** | 7 领域划分合理，但 Evo 版本数（9 次迭代）不可独立验证 |
| **困境清单** | 🔴 **低（control.x）** | 困境 4 的 "22 处" 定义不明、与当前代码不符；困境 4/5 关联代码位置已漂移 |
| **行动建议** | 🟡 **中** | 多数建议方向合理，但 file:line 引用严重过时，影响可执行性 |
| **模式识别** | 🟡 **中** | 12 个案例的归类合理，但部分 "已修复" 状态在当前代码中不能独立确认 |
| **整体** | **🟡 中等可信，含 3 项必须修正** | 核心分析方向正确，但存在历史叙事数字、过时代码引用、version 夸大等具体缺陷 |

---

## 2. 数据质量核验

### 2.1 工具调用计数独立重算

| 会话 | 独立重算 | t5 报告 | 匹配? |
|:----|:--------:|:-------:|:----:|
| 90dd512b | 1,511 | 1,511 | ✅ |
| 27ed0979 | 1,121 | 1,121 | ✅ |
| 38542b1c | 2,644 | 2,644 | ✅ |
| f953d3fd | 2,443 | 2,443 | ✅ |

**方法**: 从 `.tmp/sessions/` 下的原始 session.jsonl 逐行解析 `"type": "tool/call"` 记录计数

### 2.2 编码校验

`docs/analysis/session-log-summary.json` 中所有 `title` 和 `firstUserMessage` 字段均为正确的 UTF-8 编码的 CJK 字符。GBK 终端显示的 `?` 是 ASCII-only 渲染的产物，非数据损坏。

**结论**: t5 修复有效 ✅

### 2.3 旧错误计数引用核验

- `session-log-analysis.md`（t2）: **无**对旧工具计数的引用。t2 第 5 行明确声明："本报告**不引用** t1 的聚合工具计数" ✅
- `session-log-recommendations.md`（t3）: **无**对旧工具计数的引用 ✅

---

## 3. 抽样回溯核验

### 核验 1: MBON 饱和已修复（P0-2）✅

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L66-69: "MBON 饱和修复（P0-2）... 当前状态: 🟢 已解决" |
| **L301** | "MBON 饱和：学习报告成功但权重无法更新 — P0-2 已修复" |
| **核验方法** | grep/read `mushroom_body.py` |
| **证据** | `mushroom_body.py` 包含 20 处 saturation 相关引用、11 处 clip/normalize 引用；权重归一化机制可见 |
| **结论** | ✅ **成立** — 代码中包含 MBON 饱和修复证据 |

### 核验 2: Phase 6 零分已修复 ⚠️

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L303: "Phase 6 零分：Evo 评分报告成功但实际 fitness=0 — 属性函数修复" |
| **核验方法** | grep `evolution_skill.py` for phase6/attribute patterns |
| **证据** | `evolution_skill.py` 包含 phase6 和 fitness 处理，但无直接名为 "attribute_phase6" 的修复标识 |
| **结论** | ⚠️ **证据不足** — 代码结构暗示有 phase6 处理，但无法独立确认修复已部署生效 |

### 核验 3: 逃逸位移 ≈ 0 — 仍部分未解决 🟡

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L300: "逃逸位移≈0：11 层脱困嵌套但左右转向抵消 — 方向提交已修复，仍需验证" |
| **核验方法** | grep `model.py` for escape/direction submission |
| **证据** | `model.py` 有 4 处 escape+direction 相关引用（L796, L1346, L1435, L1941），但无 `escape_burst` 或 `direction_submit` 标识；逃逸机制存在但"方向提交"修复不可见 |
| **结论** | 🟡 **部分成立** — 机制存在，但"已修复"标签无法独立确认 |

### 核验 4: StuckDetector fallen 钉死已修复 ✅

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L307: "StuckDetector fallen 钉死：fallen 信号=1 持续不衰减 — t23 fix③ 已修复" |
| **核验方法** | grep `memory.py` for fallen decay/reset |
| **证据** | `memory.py` 含 45 处 fallen 引用，含 fallen+decay/reset 机制（带时间衰减逻辑） |
| **结论** | ✅ **成立** — 代码中有 fallen 信号衰减机制 |

### 核验 5: Coach 策略穿透 — 部分修复 ⚠️

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L304: "策略穿透失败：Coach 产生策略但 control 不生效 — fix5-fix12 部分修复" |
| **核验方法** | `coach_outcomes.py` + `test_coach_contract.py` 存在性/内容检查 |
| **证据** | `coach_outcomes.py`（352 行）存在策略处理；`test_coach_contract.py`（163 行）存在契约测试，但未明确验证 steering_bias→control.x 穿透 |
| **结论** | ⚠️ **证据不足** — 契约测试存在但穿透链验证不完整，"部分修复"表述合理 |

### 核验 6: instinct_bindings.py 已实现并部署 ✅

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L80-86: "instinct_bindings.py: 新文件 — 本能行为绑定系统（evo061）... 当前状态: 🟢 已解决" |
| **核验方法** | 文件存在性 + 内容检查 |
| **证据** | `instinct_bindings.py`（409 行）存在且包含 reflex/instinct 行为绑定内容 |
| **结论** | ✅ **成立** |

### 核验 7: 回归检测工具已实现 ✅

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L189-192: "回归检测... scripts/check_regressions.py + tests/test_regression_detector.py" |
| **核验方法** | 文件存在性检查 |
| **证据** | 两个文件均存在（236 行 + 237 行） |
| **结论** | ✅ **成立** |

### 核验 8: telemetry.py 存在 ✅

| 属性 | 内容 |
|:----|------|
| **t2/t3 引用** | 多处引用 telemetry.py |
| **核验方法** | 文件存在性检查 |
| **证据** | `fly64/fly64/telemetry.py`（118 行）存在 |
| **结论** | ✅ **成立** |

### 核验 9: Evo 版本迭代（9 次）🔴 **OVERREACH**

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L103: "Evo 版本演进: evo059 → evo061 → ... evo071（共 9 次迭代）" |
| **核验方法** | 全仓 grep evo0xx + `evolution_history.json` |
| **证据** | `evolution_history.json` 仅有 3 条记录（EVO-001~003）。全仓 grep 未找到 evo059-evo071 作为 Python 版本标识符。这些版本号可能来自会话中的文件创建历史而非代码中的版本标注 |
| **结论** | 🔴 **不成立** — 9 次迭代声称不可从当前代码独立验证；`evolution_history.json` 只记录 3 次 |

### 核验 10: 门禁与看门狗工作正常 ✅

| 属性 | 内容 |
|:----|------|
| **t2 声明** | L119-125: "门禁与看门狗工作正常" |
| **核验方法** | 文件存在性检查 |
| **证据** | `watchdog.sh`（75 行）、`service.py`（355 行）、`phase2_gate.sh`（53 行）均存在 |
| **结论** | ✅ **成立** — 文件存在，但"工作正常"的运行时断言未验证 |

---

## 4. 路径与引用校验

### 4.1 t3 建议中引用的 file:line 核验

| 引用位置 | 引用内容 | 在 t3 中的用途 | 核验结果 |
|:---------|---------|:--------------:|:--------:|
| `memory.py L135` | `rate_threshold: float = 5.0,` | StuckDetector 阈值定义 | ✅ 语义匹配 |
| `memory.py L127` | `forward_rate collapses (< 5 Hz for >3 s)` | 文档字符串引用 | ✅ 语义匹配 |
| `central_complex.py L210` | `self.steering_bias: float = 0.0` | Steering 优先级链 | ✅ 语义匹配 |
| `model.py L2094` | 注释行 | Steering 竞争引用 | ⚠️ 行存在但内容不直接涉及 steering 竞争 |
| `main.py L939` | `Cross-section aware rules...` | 声称是 control.x 绕过点 | ❌ **行存在但内容无关 control.x** |
| `main.py L956` | `passes one.` | 声称是 control.x 绕过点 | ❌ **行存在但内容无关 control.x** |
| `main.py L1011` | `def load_active_strategy...` | 声称是 control.x 绕过点 | ❌ **行存在但内容无关 control.x** |
| `main.py L1168-L1229` | 内存控制/夹紧逻辑 | 声称是 control.x 绕过点 | ❌ **行存在但内容不直接涉及 control.x 赋值** |

### 4.2 关键发现：t3 的 control.x bypass 行号已过时

**现状**:  
- t3 引用 `main.py L939-940, L956-958, L1011-1013, L1168-1179, L1191-1199, L1206, L1220-1229` 作为 control.x 直接写入点  
- **实际** control.x 写入出现在 main.py 的 **L760, L1948, L1965, L2029, L2078, L2080, L2286, L2294, L2346, L2372**  
- 行号偏移约 1000 行，可能是因为后续代码插入（fix5-fix12、evo 更新等）

**影响**: 这些引用行是 t3 的 **P2-N1**（control.x 迁移）、**P3-N1**（LLM→LIF 池）以及多个 recommendations 的直接依赖。行号错误意味着：
- 开发人员无法按文档所述的 `file:line` 定位目标代码
- 建议中"6 处 Reflex"、"11 处 LLM" 的分类可能与当前代码布局不匹配

**严重程度**: 🔴 **高** — 必须修正或标注"行号基于历史文档，需在当前 main.py 中重新定位"

---

## 5. 当前状态一致性

| t2/t3 声称状态 | 核验结果 | 证据 |
|:--------------|:--------:|------|
| MBON 饱和修复 🟢 已解决 | ✅ 一致 | mushroom_body.py 含饱和归一化机制 |
| 本能绑定 🟢 已解决 | ✅ 一致 | instinct_bindings.py 存在（409 行）|
| 门禁与看门狗 🟢 已解决 | ✅ 一致 | watchdog.sh/service.py/phase2_gate.sh 均存在 |
| 回归检测 🟢 已解决 | ✅ 一致 | check_regressions.py + test_regression_detector.py 存在 |
| stuck 模式部分 fix 🟡 部分修复 | ✅ 一致 | memory.py 含 fallen decay 机制 |
| **逃逸位移 ⚠️ "方向提交已修复"** | ❌ **状态存疑** | 无可独立确认的修复标识 |
| **Evo 9 次迭代** | ❌ **状态存疑** | evolution_history.json 仅 3 条 |
| **22 处 control.x bypass → 已从 34 处减少** | ❌ **状态不符** | 当前代码只有 10 处直接 control.x 赋值（main.py）|

---

## 6. control.x 旁路计数专项裁定

### 6.1 请求裁定

队长疑点: t2 困境 4 声称 "22 处 control.x Python 旁路（从 34 处降至 22 处）"，实测结果不一致。

### 6.2 独立计数（按不同定义）

| 定义 | 描述 | main.py 计数 | 全仓计数 |
|:----|------|:----------:|:-------:|
| **定义 A** | `control.x\s*=(?!=)` 字面赋值（生产代码） | **10** | **14**（含 motor_primitives.py 1 + evolution_agent.py 1 + fix_template_interpreter.py 2） |
| **定义 B** | 定义 A + 测试文件 | 10 | **16**（另含 test_evolution_capability.py 1 + test_fix_template_interpreter.py 1） |
| **定义 C** | `control.x` 任意出现 | **30**（main.py） | **65**（全仓） |
| **定义 D** | 按逻辑类别计（历史文档分类） | **22**（6+11+6） | — |
| **定义 E** | `control.x/control.y/control.jump` 合计 | **23**（历史文档） | — |

### 6.3 "22" 的来源追踪

`docs/analysis/insurance/remaining-issues-analysis.md`（L39-54）将 bypass 分为 3 类：
- **A: Reflex 控制**（6 处）— L939-940, L956-958, L1011-1013
- **B: 对话 LLM 控制**（11 处）— L1168-1179, L1191-1199, L1206
- **C: 坠落恢复**（6 处）— L1220-1229

**但**：这些行号引用的 main.py 是 9 月 13-15 日的版本，**当前 main.py 已发生大量代碼变更**，行号全面漂移。

而且该文档自身矛盾：
- L43 总数写 "23 处"（含 control.x/control.y/control.jump）
- L54 总数写 "22 处"（仅 control.x）

### 6.4 裁定

| 问题 | 裁定 |
|:----|:----|
| **"22" 在当前代码中可复现吗？** | **❌ 不可复现** — 使用字面赋值定义得 10（main.py）/14（全仓生产），使用任意出现得 30/65，均不为 22 |
| **t2 的定义明确吗？** | **❌ 定义不明** — t2 未区分"逻辑 bypass 点"与"实际赋值语句" |
| **t2 的 22 是否来自历史叙事？** | **✅ 是** — 来自 `remaining-issues-analysis.md` 的分类计数，不是当前代码实测 |
| **必须修正？** | **✅ 必须** — t2 困境 4 需补充明确定义和当前代码实测清单，或撤回"22"数字 |

---

## 7. 遗漏审计

| 检查项 | 结果 |
|:------|:----:|
| 未覆盖的会话 | **无** — 全部 11 个唯一会话（12 个条目）均被 7 个领域覆盖 |
| 未覆盖的主题 | **无** — GHB Cost Control 主题出现在所有会话中，但这是 t2 分析范围设定（脑模型项目聚焦）内的合理排除 |
| GHB/保险分析内容 | 虽然不在本分析范围，但贯穿 11/12 会话的 GHB 主题可能值得单独分析报告 |
| session-99cab60f（环境启动） | 仅 7 turns × 2 份导出，最小化覆盖合理 |

**结论**: 无重要遗漏 ✅

---

## 8. 过度推断审计

### 8.1 发现的过度推断

| # | t2/t3 位置 | 声称 | 实际证据 | 类别 |
|:-:|:----------|------|---------|:----:|
| O1 | t2 L57-59 | "control.x 直接写入从 34 处降至 22 处" | 历史叙事数字，非当前代码实测 | 🔴 过度推断 |
| O2 | t2 L103 | "Evo 版本演进: evo059 → ... → evo071（共 9 次迭代）" | `evolution_history.json` 仅 3 笔；全仓不可查 evo0xx 标识 | 🔴 过度推断 |
| O3 | t2 L298-311 | 12 个"死机制"模式案例表（含各修复状态） | 8/12 标注 ✅ 但部分"已修复"（如逃逸位移）不可当前验证 | 🟡 部分推断 |
| O4 | t2 L125 | "门禁与看门狗工作正常" | 文件存在但"工作正常"无运行时验证 | 🟡 轻微过度 |
| O5 | t3 全文件 | file:line 引用的 control.x bypass 行号 | 行号全面过时，不应标注为当前有效位置 | 🔴 技术性过度 |

### 8.2 合理的推断（非过度）

以下 t2 声明是合理的推断，有充分证据支持：
- Telemetry 魔数散落（8 组 magic numbers 可 grep 确认）✅
- CX-2 锚点积分漂移（heading_rate 开环积分可见）✅
- Steering 优先级未定义（steering_bias 无仲裁逻辑可确认）✅
- StuckDetector 单位混淆风险（rate_threshold 仅标 Hz 但实际使用歧义）✅
- "机制存在、报告成功、无法生效"模式分类 ✅

---

## 9. 必须修正条目清单

按严重程度从高到低排列：

| # | 文件 | 位置 | 问题描述 | 严重度 | 要求修正 |
|:-:|:----|:----|---------|:-----:|---------|
| **M1** | `session-log-analysis.md` | 困境 4（L385-394） | control.x "22 处" 定义不明、非当前代码实测、行号过时 | 🔴 阻塞 | 补充 bypass 的可复现定义并重新实测计数，或撤回数字 |
| **M2** | `session-log-analysis.md` | L103 | "9 次迭代"夸大 — evolution_history.json 仅 3 条 | 🔴 高 | 核实来源并修正（注明来自会话历史而非当前代码）|
| **M3** | `session-log-recommendations.md` | L318 及 P2-N1/P3-N1 的 file:line | control.x bypass 行号全面过时（实际在 L1948+，而非 L939-L1229）| 🔴 高 | 更新为当前代码的行号，或添加"基于历史文档，需在当前 main.py 重新定位"注释 |
| **M4** | `session-log-recommendations.md` | P2-N1 (L330-336) | 22 处分类（6+11+6）基于过时文档，可能不反映当前代码 | 🟡 中 | 核实当前代码中 bypass 的分类和数量 |
| **M5** | `session-log-analysis.md` | L300 | "逃逸方向提交已修复"缺乏当前代码可验证证据 | 🟡 中 | 补充当前代码证据或改为"修复待确认" |
| **M6** | `session-log-recommendations.md` | model.py L2094 引用 | L2094 是注释行，不直接涉及 steering 竞争 | 🟡 低 | 补充或修正引用行 |

---

## 10. 建议清单（可选）

以下建议供 captain 判断是否采纳：

1. **M1 快速修复**：在 t2 困境 4 标题后增加定义说明框，例如: `> 注："22 处"基于 remaining-issues-analysis.md 的历史分类（6 Reflex + 11 LLM + 6 Fallen），当前代码实测 control.x 字面赋值仅 10 处（main.py）。如以字面赋值重新计数，应为 X 处。`
2. **M2 快速修正**：将 "9 次迭代" 改为 "会话日志中记录了 9 个 evo 版本标识，当前可验证 N 个"
3. **M3 快速修正**：在 t3 的所有 `main.py` 引用前添加 `⚠️ 行号基于会话日志（09-13），当前 main.py 已漂移` 的警示
4. **建立 file:line 引用验证契约**：未来 t3 类文档生成后应自动验证每个 file:line 是否存在
5. **数据分级标签**：在 t2/t3 中清晰标注"基于当前代码"、"基于会话日志"、"基于推断"，避免读者混淆