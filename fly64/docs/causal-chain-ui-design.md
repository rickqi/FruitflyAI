# 视觉神经因果链路 UI 设计方案（Fly64 Neural Observatory 增量设计）

> 任务 t2 · 基于 t1 信号链路分析 · 目标：直观呈现「视觉捕获信号 → 神经元处理 → 判断逻辑 → 具体行动」的完整因果链
> 原则：**增量设计**——在 http://127.0.0.1:8765/ 现有五段布局（Vision / Neurons→controls / Activity map / Spatial memory / Escape Events）之上"缝合"因果视图，不推翻重建。

---

## 1. 现状缺口回顾（承接 t1）

当前仪表板按"工艺阶段"分栏（视觉、神经元、记忆、事件），但**因果链是断开的**：

1. **中间量不可见**：视网膜 16 扇区对比度、ON/OFF 通道、边缘方向能量、sustained/transient（τ）、optic flow（asymmetry/looming/cliff 的原始值只在 60s 趋势线里）、LIF 编码后自运动分离量、阈值门控判断（gate 0.4 Hz / 2 Hz 只画了虚线没解释）、Stuck/Cliff 置信度、控制级联优先级（悬崖反射 > 健康 > 碰撞 > 逃脱）——均无"当前帧"展示。
2. **无因果连接**：用户无法回答"为什么这一帧向左转"——需要人工跨 4 个面板比对时间戳。
3. **无单帧回放**：freeze 只是停住画面，不能逐帧回放检查某次 escape 事件的触发链。

## 2. 候选方案对比

### 方案 A：视网膜激活叠加视图 + Optic Flow 矢量场（Retina Overlay）

在现有 256×128 retina/change 画布上叠加分析层：16 扇区网格线、每扇区对比度热力着色、边缘方向小箭头、optic flow 全局矢量（asym=左右色带、looming=中心径向、cliff=下方扇区高亮）。

- **优点**：最贴近"原始证据"；实现成本极低（纯 canvas 2D 叠加，复用 packet.eyes/change 已有像素）；对 researcher 暴露的每扇区字段一一对应。
- **缺点**：只覆盖"感知→特征"段，**神经元池→判断→行动仍断链**；扇区小、信息密度高，易读性差；无法表达门控判断与优先级仲裁。

### 方案 B：因果链路时间轴（Causal Timeline / 事件驱动泳道）

横向时间轴（复用现有 10 s 窗口 + history rows），四条泳道：① 视觉特征（flow_cliff / looming / asym 曲线 + 事件标记）② 神经元池（forward/left/right/jump Hz 曲线，已有）③ 判断（门控穿越点、Stuck/Cliff 确认时刻、异常态变迁）④ 行动（x/y 指令、jump 请求→game ack、escape 触发）。纵向对齐线 + 因果箭头连接"信号→响应"对。

- **优点**：天然表达**时间因果**与延迟（信号领先行动多少 ms）；与现有 chart() 绘图管线完全同构，增量最小；回放即时间轴 scrub，零额外数据结构。
- **缺点**：是"时间对齐"不是"机制因果"——不能直观显示是*哪个*扇区/哪群神经元导致的判断；四泳道并排信息量大，移动端不可用。

### 方案 C：决策解释卡片（Decision Explanation Card / "Why" 卡）

固定一张卡片回答单一问题："**为什么现在这个动作？**"内容为一条自上而下的因果链栈：

```
▸ 行动: TURN LEFT (x=-1)           [180ms 前]
▸ 判断: right-flow > left-flow + margin (3.2 vs 0.8 Hz) · gate 0.4 Hz ✓
▸ 神经: R-turn pool 4.1 Hz ↑ · L-turn 0.9 Hz · forward 0.3 Hz (gate✗)
▸ 信号: optic flow asym = +0.62 · 扇区 S12–S15 Δlight 高 (右侧边缘)
▸ 证据: [视网膜缩略图高亮扇区] [脑图高亮激活池]
```

每层可展开（hover 显示精确数值、点击下钻到对应面板）。逃生/反射等优先级判断显示仲裁结果（如 "CLIFF REFLECT preempts forward"）。

- **优点**：直接回答"为什么"，因果语义最强；把 t1 列出的全部中间量按解释结构组织而非平铺；天然支持悬停下钻；对排版/文案要求高但数据均为已有字段。
- **缺点**：单卡片只解释"当前帧"，**丢失时间上下文**；链式文本不如图形直观；仲裁逻辑需要 telemetry 暴露 decision_source 字段（t1 已列为低成本可暴露项）。

### 方案 D：Sankey / 流量图（否决）

把信号量作为流宽画桑基图。视觉冲击强，但：速率→池→动作的"流量"语义不成立（不是守恒量），每帧重排抖动大，且无法定位单帧。仅适合事后统计页，不选。

## 3. 推荐主方案：**C + B 融合 —— 「因果解释卡（上）+ 因果时间轴（下）」双联布局**

- **C 卡**回答"*现在*为什么这么做"（机制因果、空间下钻）；
- **B 轴**回答"*刚才那一下*是怎么发生的"（时间因果、回放取证）。
- 方案 A 的扇区叠加不作为独立方案，而是**降维吸收**进 C 卡的证据缩略图与视网膜面板的轻量叠加（一条扇区网格 + 活跃扇区描边，~40 行 JS）。

**推荐理由**：① 覆盖单帧（卡）与回放（轴）两个验收场景；② 全部数据来自现有 packet + t1 建议新增的 6 个低成本字段，无新管线；③ 与现有面板是"覆盖层 + 新 section"关系，迁移成本最低；④ A/D 各自的致命缺口（断链/无意义流）被规避。

## 4. 布局线框（增量标注）

现有五段保持原位；改动如下（`[+]` 新增，`[~]` 增强现有）：

```
┌─ header: status · [+] ⏵/⏸/⟲ 回放控制组（接在 Freeze 旁）─────────┐
├─ [~] Vision ────────────────────────────────────────────────┤
│   retina canvas [~]: +16扇区网格(1px #354250), 活跃扇区描边   │
│   [+] Causal Card（跨 Vision 与 Neurons 两栏的横向新 section）│
│   ┌──────────────────────────────────────────────────────┐  │
│   │ ▸ ACTION  ←  ▸ JUDGE  ←  ▸ NEURAL  ←  ▸ SIGNAL  ← ▸ RAW│  │
│   │  (5 段横向链，箭头连接；每段 hover 展开 tooltip，        │  │
│   │   点击下钻滚动到对应面板并高亮该元素 1.5s)               │  │
│   └──────────────────────────────────────────────────────┘  │
├─ [~] Neurons → controls: 各 chart 行 label 处加 id 锚点供下钻  │
├─ [+] Causal Timeline（新 section，Activity map 之前）────────┤
│   ┌──────────────────────────────────────────────────────┐  │
│   │ L1 信号   cliff ─┤  loom ──┐      asym ══╗            │  │
│   │ L2 神经   fwd ──── lr ══╗   jump ──┤   (复用曲线)      │  │
│   │ L3 判断   ├gate✓┤ ├CLIFF┤  (事件条带+确认时刻▲)          │  │
│   │ L4 行动   x/y 阶梯线 + jump 标记 + ack 虚标               │  │
│   │      ────── scrub 手柄 + 因果连线(信号峰→响应点) ──────   │  │
│   └──────────────────────────────────────────────────────┘  │
├─ Activity map / Spatial memory / Escape Events（不变）        │
│   [~] Escape 表行点击 → 时间轴跳到该事件 t-2s 并暂停          │
└─────────────────────────────────────────────────────────────┘
```

因果卡 5 段横向布局在窄屏 (<900px) 折叠为纵向栈（flex-direction: column，箭头旋转 90°）。

## 5. 数据结构（新增，全部兼容现有 WebSocket schema=3 增量）

### 5.1 telemetry row 新增字段（t1 已论证低成本）

```python
row = dict(...,
  sector_contrast=[...16 floats...],   # 各扇区 Δlight 均值 0–1（retina.py 扇区聚合已有中间量）
  sector_active=[...16 bool...],       # 扇区超阈值标记（阈值=全程均值+2σ）
  edge_dir=...,                        # 主导边缘方向 (0–360°，方向能量 argmax)
  tau_sustained=..., tau_transient=...,# ON 通道慢/快时间常数通道能量比
  flow_asymmetry=..., flow_looming=..., flow_cliff=...,  # 已有
  cliff_conf=..., stuck_conf=...,      # 判断置信度（memory.py 检查器已有内部量）
  decision_source='forward|turn|jump|cliff_reflex|escape|collision',  # 控制级联胜出者
  gate_forward=bool, gate_jump=bool,   # 门控判定结果
)
```

### 5.2 前端因果卡模型（dashboard.js 内派生，无后端改动）

```js
// 由 row 派生的解释链，纯函数：
function explain(r) {
  const chain = [
    { stage:'raw',    label:'RAW FRAME',   detail:`frame ${r.t}s · Δlight L${pct(r.contrast_left)}/R${pct(r.contrast_right)}` },
    { stage:'signal', label:'SIGNAL',      detail:`flow asym ${r.flow_asymmetry} · loom ${r.flow_looming} · cliff ${r.flow_cliff} (conf ${r.cliff_conf})`,
                      highlight: activeSectors(r) },
    { stage:'neural', label:'NEURAL',      detail:`fwd ${hz(r.forward)}${r.gate_forward?' ✓gate':' ✗'} · L ${hz(r.left)} · R ${hz(r.right)} · jump ${hz(r.jump)}${r.gate_jump?' ✓':''}` },
    { stage:'judge',  label:'JUDGE',       detail: judgeText(r) },   // 含 decision_source 仲裁说明
    { stage:'action', label:'ACTION',      detail:`x=${r.x} y=${r.y}${r.jump_event?' + JUMP':''} → game ack ${r.game_age}ms` },
  ];
  return chain;
}
// judgeText 示例: "cliff_reflex preempts forward (cliff_conf 0.91 > 0.8)" / "R-turn: right 3.2 > left 0.8 + margin"
```

### 5.3 事件缓冲（时间轴回放用）

复用现有 `history`（10s 滚窗）+ 新增 `ringBuffer`：最近 120s 每 0.25s 一条 row 快照（约 30KB/s JSON，可 Uint8 压缩），供 scrub 回放与 escape 事件跳转。

## 6. 配色与视觉语言（延续现有 token）

| 用途 | 颜色 | 说明 |
|---|---|---|
| 信号层 | `#6cdaed` CYAN | 感知/特征（沿用） |
| 神经层 | `#ffca72` GOLD | 神经元池（沿用 steering 色） |
| 判断层 | `#9d7bff` 紫 | 新增：门控/仲裁/置信度 |
| 行动层 | `#7dff9d` 绿 | 新增：指令与 game ack |
| 危险/反射 | `#ff3c3c` 红 | cliff/escape/异常（沿用） |
| 中性 | `#354250`/`#b0bdcc` | 网格/次要文字（沿用） |

- 因果卡 5 段左边框各用层色，箭头 `#536170`；被仲裁压制（preempted）的层降饱和至 40% 并加删除线样式，直观显示"优先级级联"。
- 时间轴 L3 判断条带：gate✓ 用层色 2px 条，CLIFF/STUCK 确认用红色 ▲ + 事件名。
- 深色背景 `#0b1116`–`#10151c` 不变；新元素均为描边+发光型（box-shadow 0 0 6px 层色 30%），与现有霓虹观测台气质一致。

## 7. 交互设计

### 实时模式
- 因果卡 200ms 节流刷新（跟随 render()），任一层值越过阈值时该段短促脉冲动画（120ms box-shadow 增强）。
- 视网膜扇区叠加：活跃扇区 2px CYAN 描边 + 半透明填充；hover 扇区显示 tooltip（扇区号、Δlight、方向能量）。

### 悬停（因果卡）
- 每段 hover：tooltip 显示精确值 + 阈值 + 判定公式（如 `gate: forward 0.43 Hz > 0.4 Hz ✓`）。
- hover `judge` 段若发生 preempt，显示被压制链（"escape preempted: forward gate was ✓ but cascade priority 4>2"）。

### 点选下钻
- 点击某段：平滑滚动至对应面板（signal→Vision / neural→Neurons→controls / judge→Causal Timeline 并居中该时刻 / action→stickChart），目标元素加 1.5s 呼吸高亮环。
- Escape 表行点击：时间轴 scrub 至 `t_event − 2s`，进入回放暂停态。

### 回放（时间轴）
- 底部 scrub 手柄 + ⏵/⏸（2×/0.5×）按钮；scrub 时所有面板（含 retina、脑图、因果卡）渲染 ringBuffer 中该时刻快照，脑图 activity 需随快照存档（uint8[n] 每 0.25s ≈ 1.9MB/120s，可接受；紧张时降为每 0.5s）。
- 时间轴上"因果连线"：信号峰（如 cliff 确认▲）到首个响应（x 翻转）之间画贝塞尔弧线 + 延迟标注（如 "+240ms"），悬停弧线显示两端精确值。
- 回放结束自动回到 Live（复用现有 freeze→resume 语义，回放 = 增强的 freeze）。

## 8. 覆盖 t1 缺失中间量对照表

| t1 缺失量 | 展示位置 | 形式 |
|---|---|---|
| 16 扇区对比度 | 因果卡 signal 段 + retina 叠加 | 活跃扇区描边 + tooltip |
| ON/OFF、sustained/τ | 因果卡 signal 段 tooltip | 数值 + 通道比 |
| 边缘方向能量 | retina 叠加 | 扇区内小箭头 |
| optic flow 三量当前值 | 因果卡 signal 段 | 数值（趋势线已有） |
| LIF 编码/自运动分离 | neural 段 tooltip | 池率 + 分离说明文案 |
| 门控判断（0.4/2 Hz） | judge 段 + 时间轴 L3 | ✓/✗ 徽标 + gate 事件条 |
| cliff/stuck 置信度与确认 | judge 段 + L3 ▲ | conf 数值 + 确认时刻 |
| 控制级联优先级 | judge 段 | preempt 展示（降饱和+删除线） |
| 指令→game ack 闭环 | action 段 + L4 | x/y + ack 延迟 ms |
| 单帧回放 | 回放控制组 + scrub | 全面板时间快照 |

## 9. 实施拆分建议（供 engineer 排期）

1. **P0（纯前端，无协议改动）**：因果卡静态五段链 + hover tooltip（用现有 row 字段，缺的字段先显示 "—"）。
2. **P1（telemetry 增量）**：row 新增 5.1 字段（后端多为已有中间量透传）+ decision_source 仲裁文案。
3. **P2**：视网膜扇区叠加、时间轴 section、escape 行跳转。
4. **P3**：ringBuffer 回放 + 脑图快照 + 因果连线延迟标注。

原型见 `fly64/docs/causal-chain-prototype.html`（自包含 HTML，内置模拟数据，浏览器直接打开演示因果卡、时间轴、scrub 回放与下钻高亮）。
