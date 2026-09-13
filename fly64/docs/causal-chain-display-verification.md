# Fly64 因果链路显示验证与测试回归报告（t7 · display-verifier）

基线：`fly64/web/{index.html, dashboard.js, dashboard.css, memory-heatmap.js}` + `fly64/fly64/model.py`（HEAD bc8f939 + 未提交工作区改动）。
对照：`docs/causal-chain-ui-design.md`、`causal-chain-implementation.md`、`docs/layout-audit-t5.md`（t5 结论）。
验证脚本：`fly64/tests/node_draft_check.mjs`（本次新增，可重复执行）。

---

## 1. 测试与静态检查结果

| 检查项 | 命令 | 结果 |
|---|---|---|
| dashboard.js 语法 | `node --check` | ✅ 通过 |
| memory-heatmap.js 语法 | `node --check` | ✅ 通过 |
| 设计草稿函数 node 端可执行性（explain/judgeText/renderCausal/drawSectors，含 NaN 降级、节流、preempted 标记） | `node fly64/tests/node_draft_check.mjs` | ✅ 9/9 通过 |
| test_dashboard_protocol.py + test_dashboard_js.py | `python -m pytest …` | ❌ **5 failed / 1.24s** |
| 同测试在 HEAD 基线（临时 git worktree bc8f939） | 同上 | ❌ 同样 5 failed |

### 🔴 B1（blocker，测试回归根因）`model.py encode_retina` 使用未定义的 `flow`
`fly64/fly64/model.py:320` 在 `interactive_near` 判定里读 `flow.get("edge_90",…)`，而 `flow = self.retina.compute_flow(rgb)` 在 **L324 之后才赋值** → `UnboundLocalError`。每次 `encode_retina` 必炸，**dashboard 数据管线整体中断**，5 个协议/JS 测试全部连带失败。
关键定性：**HEAD bc8f939（"Interactive scene handling" 提交）就已含此 bug**，非本次工作区增量引入；但工作区 diff 又原样复制了这段代码（interactive_near 块未提交改动同样在错误位置）。t5 审核的"web 层增量"与此无关。
**修正（一行级）**：将 `interactive_near` 计算块整体移到 `flow = self.retina.compute_flow(rgb)` 与各 `flow.get` 赋值之后（或在块内改用 `self.flow_*` 已存字段）。这是所有显示验证恢复"绿基线"的前置条件（与 t5 的 G1 同级 P0）。

## 2. HTML/CSS 结构完整性扫描

- JS 引用的全部 id（`$('…')`）在 index.html 中一一存在，**无缺失 id**。✅
- HTML/JS 使用的 class 与 CSS 定义比对：`escape-legend`、`gauge-ring` 两个类**在 dashboard.css 无定义**——二者均为纯包裹 div，子元素靠内联样式/.legend 等既有规则渲染，当前**无显示缺陷**（🔵 low：建议补空规则或删除以避免"看似有样式"的误导，也为增量样式留挂点）。
- 🔴 **G1 复核确认**：`dashboard.css L5` 的 `section:nth-child(2)`（Neurons 7 行网格）与 `L12` ≤650px 断点中的 `section:nth-child(2)` 双处硬编码。任何前置 section 插入（因果卡/时间轴）都会双倍破坏。与 t5 一致，P0 改类选择器（两处都要改）。
- 题述"重点元素"样式定义核对：`gauge`（`.health-gauge-wrap canvas` 110px ✅）、`pills`（`.health-pill/.repulsion-pill/.anomaly-pill` 及 data-health/data-state 全部定义 ✅）、`note-health`（`.note-health/-bar/-fill/-label`、`.note-stats/.note-stat` 全部定义 ✅）。**无未定义样式导致的功能缺失**。
- index.html 57 行结构完整：header→6 sections→footer→module script，aria-label 齐全，`<main>` 六行 grid 与 css L4 `grid-template-rows` 六值对应。✅

## 3. noviz / 降级恢复可行性

代码中**不存在显式 noviz/no-visual 标志**（全仓 grep 无匹配）。现有降级路径核验：
- WS 断开 → `onclose` 1.5s 重连 + `#status` 置 stale/error 文案（S1 指出长文案会挤压 Freeze 按钮，🔵）；
- `packet.data.n` 与解剖不匹配 → `location.reload()` 自愈；✅
- `memory-heatmap.js` 动态 import 失败被 `.catch(() => {})` 吞掉 → Spatial memory 区静默停摆但主 dashboard 不崩；✅ 可接受，但建议 catch 里至少置 `#memoryInfo` 文案（🟡 改进项）；
- WebGL 不可用 → brain canvas 降级为 aria-label 提示，population rates 保留。✅
结论：**降级与恢复可行**（重连/自愈/局部静默），无需要新建 noviz 开关；建议仅补充 memory 区失败提示。

## 4. 逐区显示基线核对表

| # | 区域 | 基线核对 | 增量落点风险（承接 t5） |
|---|---|---|---|
| ① | Vision（含 sceneName/contrast） | ✅ 眼图 canvas 256×128 CSS 拉伸无失真；#sceneName/#contrast/#visualRate/#localMotion 均有渲染与样式；三列 grid 122px 稳定 | 🔴 V1/V2：overlay 缺 `figure{position:relative}` + CSS 尺寸同步（1100px 断点 110px）→ 叠错位 |
| ② | Neurons（含 #decision） | ✅ 7 子节点 = 7 行网格；chart() 无尺寸反馈回路；阈值参考线正常 | 🔴 G1 nth-child(2) 前置插入即失效（两处）；🟠 N1 因果卡改 textContent |
| ③ | Activity map | ✅ WebGL per-frame dpr 重设正常；legend 无溢出；下拉在 26px head 内 | 本区自身无落点改动，仅受 G1 连带 |
| ④ | Spatial memory（health 条 + escape 图例） | ✅ heatmap 88px 固定、transform 不叠加；note-health 三件套与 note-stats 样式齐全；escape-legend 内联可用 | 🟠 **M1 为基线已有 bug**：#memoryInfo 多行 innerHTML 溢出 26px head 压热图；🟡 M2 tooltip 右缘钳制 |
| ⑤ | history-row 双图（Stuck/OpticFlow） | ✅ 54px 固定、每秒重绘无漂移；参考线在 clip 区内 | 🟡 H2：时间轴若复用此行需独立行高 |
| ⑥ | Escape Events（仪表环 + pills） | ✅ gauge 110px 已防反馈回路；表格 sticky+滚动正常；pills 三态样式齐全 | 🟡 E1 2s innerHTML 重建 → 行点击必须事件委托；🟡 E2 health-strip 651–1099px 不换行 |
| ⑦ | 顶部状态（Freeze 按钮） | ✅ header 54px 冻结；Freeze toggle 文案切换正常 | 🔵 S1 错误长文本无截断；🔵 S2 回放控件 651–1099px 挤压 |

## 5. 显示问题清单（按优先级）

1. 🔴 **B1** `model.py:320` flow 先用后赋 → 全部协议测试红、数据管线断。**非 web 层引入，但为绿基线前置。**
2. 🔴 **G1** `section:nth-child(2)` 双处硬编码 → 任何 section 插入破坏 Neurons 网格（P0 改类选择器）。
3. 🔴 **V1/V2** overlay 缺 `position:relative` 锚点 + CSS 尺寸断点同步。
4. 🟠 **M1（基线既有）** #memoryInfo 溢出压热图——注意与增量区分归因。
5. 🟠 **N1** 因果卡 5Hz innerHTML → textContent。
6. 🟡 **E1/E2/M2/S2** 事件委托 / strip 换行 / tooltip 钳制 / header wrap。
7. 🔵 escape-legend、gauge-ring 无 CSS 定义（纯包裹，无缺陷）；memory import 失败静默；S1 错误文本截断。

**结论**：web 层结构完整性与草稿函数可执行性全部通过（9/9 + 语法 + id/class 扫描）；测试回归红根因是 model.py 既存 bug（B1），修复后需重跑两套 pytest 确认绿基线，再按 t5 P0 清单（G1/V1/V2/M1/N1）执行增量落地。
