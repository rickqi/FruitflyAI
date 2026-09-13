# Fly64 布局基线逐区审核报告（t5 · layout-auditor）

基线：`fly64/web/{index.html,dashboard.js,dashboard.css,memory-heatmap.js}`（当前 HEAD），对照 `docs/causal-chain-ui-design.md` / `causal-chain-implementation.md` 的增量落点。

严重级别：🔴 blocker（按方案直接落点必坏）· 🟠 high（明显显示 bug/高风险）· 🟡 medium（易碎点/交互退化）· 🔵 low（打磨项）。

---

## G. 全局布局

- **G1 🔴 `section:nth-child(2)` 结构选择器与增量插入点冲突。**
  `dashboard.css L5` 用 `section:nth-child(2)` 选中 Neurons 段的 7 行网格（26/24/4×1fr/24）。设计方案 §3 要求在 Vision 之后插入因果卡 section、在 Activity map 之前插入时间轴 section——任一插入都会使 Neurons 变成 nth-child(3) 或 nth-child(4)，其 chart-row 网格全部失效（四条图塌成 min-content），而新插入的 section 反而错误获得该网格。
  **修正**：将 `section:nth-child(2)` 改为类选择器（如 `.neurons-section`），这是所有增量落地的前置条件（P0 必做）。
- **G2 🟡 `main{grid-template-rows:166px …50px}` 六行固定像素，且基线+1100px 断点两处硬编码。**
  实施文档 §4 已推荐改 `auto`，审核确认推荐成立：每新增 section 必须同步改两处行清单，漏改断点即 1100px+ 溢出/压缩。建议落地因果卡/时间轴时一并切换 `auto` + section 内部自持最小高度。
- **G3 🔵 各 section 固定高度内已无冗余**：Vision(166=26+122+16+2)、Activity(163)、memory(275=26+140+6+~70+16+2)、Escape(265) 均贴合；任何 section 内新增行必须同时扩 `grid-template-rows` 对应行高。

## 1. Vision 区

- **V1 🔴 retina overlay（方案 D3/§3-4）缺 `position:relative` 锚点。**
  方案 CSS 只写 `#retinaOverlay{position:absolute;inset:0}`，但 `.eyes figure`（overlay 的预期包含块）没有 `position:relative` → overlay 会相对 main/body 定位，叠错位置甚至盖住整页。必须补 `.eyes figure{position:relative}`。
- **V2 🟠 overlay 画布尺寸失配**：基线 retina canvas 是 CSS `width:100%;height:96px` 拉伸（1100px 断点 110px）。overlay 若只带 `width/height=256/128` 属性而无同样 CSS 拉伸，叠加网格与底图像素错位。overlay 需复制 `width:100%;height:96px`（断点同步）。
- **V3 🔵 现状核对**：`image()` 用 putImageData 画满 256×128，`object-fit:contain` 对 canvas 生效，基线无失真问题。

## 2. Neurons → controls 区

- **N1 🟠 因果卡 5Hz innerHTML 重排抖动（方案 D2）**：`renderCausal` 5 次/秒整段 innerHTML 重建 → 每次重建 11+ DOM 节点，文本宽度抖动 + GC 压力。建议改为固定 5 段 DOM 只更新 `textContent`（节流保留），彻底消除重排。
- **N2 🔵 基线核对**：7 个子节点与 7 行网格一一对应；`chart()` 每秒重设 canvas.width 但 clientWidth 由网格固定，无反馈回路；resize 有监听。阈值参考线（gate 0.4/2Hz 虚线）现状正常。下钻锚点 id（方案 §3-5）纯加法，安全。

## 3. Activity map 区

- **A1 🔵 基线核对**：WebGL brain canvas 每帧按 clientWidth×dpr 重设，`.map` 高度 118px 内 canvas 98px + legend 无溢出；population 下拉在 26px head 内。安全。方案的时间轴 section 插到本区之前 → 见 G1（nth-child 连带破坏），本区自身无落点改动。

## 4. Spatial memory 区

- **M1 🟠 `#memoryInfo` 多行 innerHTML 溢出 26px section-head。**
  `memory-heatmap.js updateInfo()` 每 1s 向 section-head 内的 span 写入含两个 `<br>` 的 3+ 行 HTML（Stuck/Loop/Coverage/Cliff/计数），而 `.section-head{height:26px}` 固定高、未裁剪 → 文本向下溢出并压到 heatmap 网格上，1s 一次闪烁式覆盖 marker 图例。**修正**：拆分展示（head 只留单行摘要，明细移入 `.memory-note` 或 tooltip），或 head 改 `min-height` + 布局行相应加高（需连动 G2）。
- **M2 🟡 tooltip 溢出画布**：heatmap tooltip `white-space:nowrap`、定位 `clientX+12`，悬停右缘 marker 时向右溢出 `.memory-map`（无 overflow:hidden，会盖到 memory-note 列）。建议 `left = min(x+12, w - tooltip.width - 4)`。
- **M3 🔵 canvas 反馈回路已防**：CSS 高度 88px 固定，`render()` 每秒重设 width/height 会重置 transform，`ctx.scale` 不叠加。escape-legend 内联样式可用但建议挪入 CSS。cliff 红框闪烁（box-shadow inset）不改布局，安全。

## 5. Stuck / OpticFlow 趋势图（history-row）

- **H1 🔵 基线核对**：两 canvas 高度 CSS 固定 54px，每 1s 重绘无尺寸漂移；0.8/0.3 参考线绘制在 clip 区内。`renderCoverageChart` 同。
- **H2 🟡 时间轴（方案 D4）复用该行风格时注意**：四泳道至少需 ~120px 高度，history-row 当前 `min-height:70px`；若作为新 section 插入需独立行高（连动 G1/G2）。泳道曲线每秒重绘可接受，勿升到 5Hz。

## 6. Escape Events & Coverage 区

- **E1 🟡 escape 表每 2s innerHTML 重建**：滚动位置可能跳回、hover 行闪烁；且方案要求"行点击 → 时间轴跳转"，2s 重建会销毁逐行 listener。**必须用事件委托绑定在 `#escapeBody`/table 上**，并考虑 diff 更新或仅追加新行。
- **E2 🟡 health-strip 在 651–1099px 中间宽度不换行**：`.section-head` 仅在 ≤650px 有 `flex-wrap`；pill 文本（anomaly 状态名、事件计数）变长时 nowrap 溢出 section 右缘。建议给 `.health-strip` 加 `flex-wrap:wrap`（head 高度改 min-height，连动 G2）。
- **E3 🔵 基线核对**：gauge 固定 110px 且已防 clientWidth 反馈回路（dashboard.js L526 注释属实）；表格 sticky 表头、max-height 110px 滚动正常。

## 7. 顶部状态

- **S1 🔵 状态错误文本无截断**：`$('status')` 写入原始 error.message，长消息在 54px header 内换行/挤压 Freeze 按钮。建议 `max-width+ellipsis`。
- **S2 🔵 回放控制组（方案 §3-3）加入 `.session`**：`⏵ + scrub range` 会加宽 session，窄 header 下挤压 h1；≤650px 已 wrap，651–1099 建议同样允许 wrap。

## 8. 小屏（≤650px）核对

- **B1 🔵**：main 变 block、各 row 单列/双列自适应，interactive-row 单列，均正常。但因果卡纵向栈（<900px 断点，方案 §4）与现有 650px 断点之间 651–899px 区间是横向 5 段链最挤的区间，chain-detail 长文案会溢出——建议该区间即折为纵向或允许 detail 换行（`white-space:normal`）。

## 结论（P0 前置清单）

1. 🔴 `section:nth-child(2)` → 类选择器（G1），先于一切 section 插入。
2. 🔴 overlay 需要 `figure{position:relative}` + CSS 尺寸同步（V1/V2）。
3. 🟠 `#memoryInfo` 溢出修复（M1）——这是**基线已有 bug**，与增量无关但同屏叠加会误判为新改动引入。
4. 🟠 因果卡改 textContent 更新（N1）；escape 表事件委托（E1）。
5. 🟡 grid-template-rows 改 auto 或双处同步清单（G2）；`.health-strip`/header 允许 wrap（E2/S2）；tooltip 右缘钳制（M2）。
