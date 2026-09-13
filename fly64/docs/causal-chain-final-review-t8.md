# Fly64 因果链路增量：最终汇总评审（t8 · layout-auditor）

基线：`fly64/web/` 最新布局（t5/t7 双重复核一致）。输入：`layout-audit-t5.md`（布局审核）、`causal-chain-rollback-plan.md`（t6 回滚机制）、`causal-chain-display-verification.md`（t7 显示验证）。

---

## 1. 风险点处置完备性核对

| 风险 | 级别 | 处置 | 状态 |
|---|---|---|---|
| B1 model.py:320 flow 先用后赋 | 🔴 | t7：移判定块到 compute_flow 之后（一行级），HEAD 基线复跑确认既存 | ✅ 有修复方案，**绿基线前置** |
| G1 `section:nth-child(2)` 双处硬编码（css L5 + L12 断点） | 🔴 | t5/t7 一致：改类选择器（两处） | ✅ P0 前置，方案明确 |
| V1/V2 overlay 缺 relative 锚点 + CSS 尺寸断点同步 | 🔴 | t5：`.eyes figure{position:relative}` + overlay 复制 100%/96px（1100px 断点 110px） | ✅ 方案明确 |
| M1 #memoryInfo 多行溢出 26px head（基线既有） | 🟠 | t5：head 留单行摘要，明细移 memory-note/tooltip | ✅ 已归因基线，防误判为新改动引入 |
| N1 因果卡 5Hz innerHTML | 🟠 | t5：固定 5 段 DOM + textContent | ✅ |
| E1 escape 表 2s 重建 vs 行点击下钻 | 🟡 | t5：事件委托绑定 #escapeBody | ✅ |
| E2/M2/S2/S1/H2 中低风险 | 🟡🔵 | 均有具体修正建议（wrap/钳制/截断/独立行高） | ✅ 接受或随阶段顺手修 |

**结论：每个风险点均有明确处置（修复/前置/接受），无悬空项。**

## 2. 回滚保障完备性（t6）

- **命令级可操作** ✅：tag 三级锚定（causal-baseline → causal-pN-done → wip 分支）+ 文件级快照兜底 + P0–P3 一阶段一 revert 映射表 + S1–S7 症状→命令速查树，均可直接执行。
- **kill-switch（?noviz=1 / localStorage）** ✅ 设计合理（display:none 不动 grid 结构、往返无泄漏）。⚠️ 两点约束必须落实：
  1. **noviz 目前不存在于基线**（t7 核实），必须随 P0 一并合入——S2/S3 定位流程依赖它，属回滚链路的组成部分而非可选项；
  2. 若采用固定 64px 新增行，off 态须同步 grid 行归零（t6 §3.3-1）；**采纳 t5 G2 建议改 `grid-template-rows:auto` 可直接消除该对称性负担，推荐**。
- ⚠️ **基线 SHA 不一致（medium）**：t6 记 HEAD=`25a0284`，t7 记 HEAD=`bc8f939`。开工时必须以当时实际 `git rev-parse HEAD` 重新打 `causal-baseline` tag，不得沿用文档中的旧 SHA；t7 证实的 5 个测试红（B1）修复后再补打 `causal-green` tag 作为增量起点。
- 防扩散纪律（新增渲染入口 try/catch）✅ 与 S3/S4/S5 对应，写入 review checklist。

## 3. 显示验证（t7）

- web 层全绿：语法 ✅、草稿函数 node 9/9 ✅、id/class 扫描无缺失 ✅、gauge/pills/note-health 样式齐全 ✅、6 行 grid 与 main 结构对应 ✅。
- 唯一阻塞 B1 属后端既存 bug，修复方案已给出；修复后重跑 `pytest tests/test_dashboard_protocol.py tests/test_dashboard_js.py` 确认绿，**无未处理阻塞项**。
- 降级路径（WS 重连/reload/WebGL 降级/heatmap import 静默 catch）可行；建议 heatmap catch 中置 #memoryInfo 提示文案（🟡）。

## 4. 设计文档与最新布局的差异（需更新）

1. `causal-chain-ui-design.md` §4 线框声明"Activity map / Spatial memory / Escape Events（不变）"——**已过时**：Escape Events 现含 health gauge 仪表环 + 三 pills + Coverage Trend（interactive-row 三列）。需更新：① "Escape 表行点击→时间轴跳转"的落点说明（表格现为 2s innerHTML 重建，见 E1 委托要求）；② 时间轴 section 插入点重申为"Activity map 之前"，且注明其行高不得挤压 escape 区 265px 行。
2. 决策解释卡（C 卡）与现有 `#decision` 行语义重叠（"Forward · steering · jump…"）：设计文档应明确二者关系——**保留 #decision 作为常驻状态行，C 卡为下钻解释层**，避免实施时误删 #decision（它是 Neurons 区 7 行网格的第 2 行，删除同样破坏布局）。
3. `causal-chain-implementation.md` §4 的 grid 行数调整建议需补充 G1 前置（改类选择器）与 t5 的 auto 行推荐；§3 的 retina overlay 落点需补 figure relative 锚点与断点尺寸同步。

## 5. 最终结论

**GO（有条件）** —— 最新布局下风险处置与回滚保障完备，允许进入增量实施，前提是按序执行：

1. **前置-0**：修复 B1（model.py flow 先用后赋）→ pytest 全绿 → 以实际 HEAD 打 `causal-baseline`（绿基线）tag + web/ 文件快照；
2. **前置-P0**：G1 改类选择器（css 两处）→ 合入 noviz kill-switch → 打 `causal-p0-done`；
3. P0–P3 按各自清单（V1/V2、N1、E1、M1 顺手修）与 t6 原子提交纪律执行，每阶段过 §5.3 演练检查单；
4. 设计文档按 §4 三点更新后再启动 P2（时间轴/escape 跳转涉及过时段落）。

若跳过前置-0/P0 直接落点，G1/V1 必然引入布局破坏，届时按 t6 S1/S2 速查树回退。
