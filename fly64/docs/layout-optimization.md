# Fly64 监控界面布局优化（layout-optimization）

日期：2026-02-27 · 范围：`fly64/web/{index.html, dashboard.css, dashboard.js}`
前置：`docs/layout-audit-t5.md` 审核结论的后续落地。

## 变更动机

对监控界面（Fly64 Neural Observatory）全量布局审查后发现的主要问题：
单列垂直布局在宽屏下浪费横向空间（8 行总高 >1400px 必然滚动）、
`grid-template-rows` 魔数在基线与 1100px 断点双份硬编码、
核心空间记忆热图画布仅 88px 高、Health 分数三处冗余展示、
Canvas 尺寸管理混用两种模式、HTML 内联样式散落。

## 变更内容（6 项）

### 1. 宽屏两列布局（≥1400px）
- 8 个 section/footer 增加 `area-*` 类（`index.html`）。
- 新增 `@media(min-width:1400px)` grid areas 两列：
  - 左栏：Vision → Causal Chain → Neurons→controls → Activity map
  - 右栏：Spatial memory → Causal Timeline → Escape Events
  - footer 横跨双栏；`main` max-width 1400→1800px。
- 总滚动高度约压缩 40%。

### 2. 行高声明单一化
- `:root` 新增 8 个 `--row-*` 行高变量 + `--mem-row-h/--mem-map-h/--mem-canvas-h/--esc-max-h` 组件尺寸变量。
- 基线与 `≥1100px` 断点的 `grid-template-rows` 只引用变量；媒体查询仅覆盖变量值，消除双份魔数（对应 layout-audit-t5 G2 的延续整改）。

### 3. 热图扩容
- memory heatmap canvas 高度 88→128px（基线）/ 138px（≥1100px）；所在行 140→180/190px。
- `memory-heatmap.js` 读 `clientHeight`，无需改动自动生效。

### 4. Health 去重
- 删除 Spatial memory 注释区的第三处 health 展示（`noteHealthFill` 进度条 + `noteHealthLabel`），连同 `updateHealthStrip()` 中的对应 JS 更新逻辑。
- 保留两处非冗余展示：healthGauge 圆环（主）+ healthPill 顶栏徽标（缩略）。

### 5. Canvas 尺寸统一管理（dashboard.js）
- 新增 `fitCanvas(canvas)` 辅助：CSS 盒（clientWidth/Height）为唯一尺寸源、
  backing store 按 ×dpr（上限 2）幂等设置（杜绝 clientWidth 反馈回路）、
  内置 clearRect。返回 null 当画布不可见。
- 接入点：`chart()`（4 个 motor 图）、`drawTimeline`、stuck/flow/coverage 三个历史图。
- `drawTimeline` 高度改从 CSS `clientHeight` 读取（原硬编码 120 与 CSS 双份），
  4 条泳道按高度比例伸缩。
- resize 处理改为 `ResizeObserver` 观察 9 个画布（兼容两列布局切换触发的高度变化），
  保留 `window resize` 兜底；重绘回调统一为 `repaint()`。

### 6. 样式收敛
- `index.html` 内联样式清零：escape 图例、sceneName、localMotion、noteAnomaly、
  healthGauge、coachAdviceText、escape 空表行全部迁入 `dashboard.css`
  （新增 `.escape-legend .esc-*`、`.skill-tag`、`.motion-warn/.motion-clear`、
  `.escape-empty` 等类）。
- memory 图例渐变改为 `.legend i.rainbow` 类，与 brain 图例共用 `.legend` 基类。
- 部分颜色改用 `var(--cyan)/var(--gold)` token。

## 不变量 / 回滚

- 未触碰 causal-off 回滚开关契约：所有 causal 区块仍带 `.causal-ui`，`body.causal-off` 行为不变。
- 数据协议、WS 逻辑、memory-heatmap.js、trajectory.html 未改动。
- ≤1100px 单列布局与 ≤650px 移动端布局保持原结构；≥1400px 为纯新增断点。
- 回滚方式：git revert 本次提交即可，无迁移状态。

## 验证

- `node --check` 通过（dashboard.js / memory-heatmap.js）。
- `index.html` grep `style=` 为 0 处。
- 手工验证建议：≥1400px 双列、1100–1400px 单列、<650px 移动端、`?noviz=1` 回滚模式。
