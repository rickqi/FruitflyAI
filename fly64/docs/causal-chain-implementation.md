# 因果链路落地实施建议（任务 t3 · engineer）

> 承接 t1（链路分析）与 t2（UI 设计方案 `causal-chain-ui-design.md`），本文件给出**可落地的具体实施建议**：
> telemetry.py 新增字段、dashboard.js / index.html / dashboard.css 改动点与关键代码草稿、协议兼容性（tests/test_dashboard_protocol.py / test_dashboard_js.py）、性能约束分析。
> **不直接修改产品代码**；以下代码均为草稿，标注了插入位置。

---

## 1. telemetry.py 新增字段（协议变更点）

### 1.1 设计原则

- `Observatory` 是只读仪表（docstring: "Never feed dashboard values back into the model"）。所有因果标注必须是**已有内部量的透传**，不能反向影响模型。验证基准：`test_observation_does_not_change_model_and_matches_decoder` 必须继续通过。
- 协议采用**加法演进，schema 保持 3**：`decodePacket` 只校验 `schema/width/height/n/rows`（dashboard.js L14），JSON meta 新增键对旧前端透明；二进制 payload 布局**完全不变**（activity[n] + eyes + change），`test_dashboard_packet_and_every_tick_timestamp` 的 `len(payload)` 断言不受影响。

### 1.2 新增 row 字段清单（全部有现成来源，无新计算管线）

| 字段 | 类型 | 来源（现成内部量） | 频率 |
|---|---|---|---|
| `sector_contrast` | `int[16]`（0–100，量化） | retina 扇区 Δlight 聚合（t1 已确认 retina.py 有 16 扇区中间量；Observatory 已算 `self.contrast` 左右两半的均值，扇区版是同一公式的细分） | 每 frame（10Hz） |
| `sector_active` | `int`（uint16 bitmask，1 bit/扇区） | `sector_contrast[i] > 全程均值+2σ` | 每 frame |
| `edge_dir` | `int`（0–359，None=-1） | retina 边缘方向能量 argmax | 每 frame |
| `tau_sustained` / `tau_transient` | float | retina ON 通道慢/快 τ 能量比 | 每 frame |
| `cliff_conf` | float(0–1) | `memory_ctrl.cliff_confidence`（memory.py L1554，main.py L718 已在 /history.json 透传 `round(...,3)`） | 每 tick |
| `stuck_conf` | float(0–1) | `memory_ctrl.stuck_score`（main.py L675/L760 同上） | 每 tick |
| `cliff_confirmed` | bool | `model.cliff_confirmed`（model.py L370） | 每 tick |
| `gate_forward` / `gate_jump` | bool | 与 render 阈值同源：`forward_rate > 0.4`、`jump_rate > 2.0`（model.py 门控） | 每 tick |
| `decision_source` | enum str | main.py 控制级联胜出者：`cliff_reflex │ anomaly_reflex │ escape │ steering │ jump`（见 1.3） | 每 tick |
| `anomaly_state` | str | `memory_ctrl.anomaly_state_name`（main.py L701 已有） | 变化时 |
| `escape_behavior` | bool | `memory_ctrl.escape_behavior`（main.py L678 已有） | 每 tick |

**成本关键点**：`sector_* / edge_dir / tau_*` 只在 `seq != frame_seq`（新帧到达，10Hz）时写入该 tick 的 row；其余 40 tick/秒 不带这三个字段 → JSON 体积增量 ≈ 10 rows/s × ~90B ≈ **0.9 KB/s**，而非 50 行全带（4.5 KB/s）。

### 1.3 telemetry.py 代码草稿

```python
class Observatory:
    def __init__(self, model):
        ...
        self.causal = None          # main.py 每 tick 注入的只读快照，见下

    def observe(self, frame, seq, control, spikes, game, causal=None):
        ...
        # —— 新帧时才计算扇区中间量（10Hz，而非 50Hz）——
        if seq != self.frame_seq:
            ...  # 现有 preview/contrast 逻辑不动
            self.sectors = self._sector_contrast(delta)      # 新私有方法，复用 delta
        causal = causal or {}
        row = dict(t=t, **rates,
                   contrast_left=..., contrast_right=...,
                   ...现有字段不动...,
                   # —— 新增：判断层 ——
                   cliff_conf=causal.get('cliff_conf'),
                   stuck_conf=causal.get('stuck_conf'),
                   cliff_confirmed=causal.get('cliff_confirmed', False),
                   gate_forward=bool(rates['forward'] is not None and rates['forward'] > .4),
                   gate_jump=bool(rates['jump'] is not None and rates['jump'] > 2.),
                   decision_source=causal.get('decision_source', 'steering'),
                   escape_behavior=causal.get('escape_behavior', False),
                   # —— 新增：信号层（仅新帧行携带）——
                   **(self._signal_fields() if seq != self.frame_seq or self.frame_seq is None else {}))
        self.rows.append(row)
        return row

    def _sector_contrast(self, delta):        # 16 扇区，量化为 0–100 整型
        s = delta.reshape(128, 16, 16)[self.retina_mask_16]  # retina 已有扇区划分
        return [int(round(c.mean()/255*100)) for c in s]

    def _signal_fields(self):
        act = 0
        for i, c in enumerate(self.sectors):
            if c > self.sector_threshold[i]: act |= 1 << i
        return dict(sector_contrast=self.sectors, sector_active=act,
                    edge_dir=self._edge_dir(), tau_sustained=..., tau_transient=...)
```

**main.py 注入点**（控制级联末尾、`control` 定稿后）：

```python
# main.py run() 内，escape/cascade 判定完成后：
if cliff_triggered:
    source = 'cliff_reflex'
elif reflex_active:
    source = 'anomaly_reflex'
elif memory_ctrl.escape_behavior:
    source = 'escape'
elif control.jump:
    source = 'jump'
else:
    source = 'steering'
obs.observe(frame, seq, control, spikes, game,
            causal=dict(cliff_conf=round(memory_ctrl.cliff_confidence, 3),
                        stuck_conf=round(memory_ctrl.stuck_score, 3),
                        cliff_confirmed=model.cliff_confirmed,
                        decision_source=source,
                        escape_behavior=memory_ctrl.escape_behavior))
```

优先级顺序与 main.py 现有级联一致（L381 悬崖反射最先 → L437 反射 → L482 正常 escape → 普通 steering）。

### 1.4 packet() 变更点

`meta = dict(schema=3, ..., causal_schema=1, **performance)` —— 仅加一个 `causal_schema=1` 哨兵键，供新前端特性检测（`d.causal_schema ? showCausalCard() : hideLegacy()`），旧 JS 忽略。

---

## 2. dashboard.js 改动点与代码草稿

改动全部为**新增函数 + render() 尾部追加一行**，不动 `decodePacket`（协议兼容的另一半）。

### 2.1 D1 · explain() 派生模型（纯函数，P0）

```js
const PURPLE = '#9d7bff', GREEN = '#7dff9d', RED = '#ff3c3c';
const hz = v => Number.isFinite(v) ? v.toFixed(1) : '—';
const PRIORITY = { cliff_reflex: 4, anomaly_reflex: 3, escape: 2, jump: 1, steering: 0 };

function judgeText(r) {
  if (!Number.isFinite(r.cliff_conf)) return 'awaiting causal fields';
  if (r.decision_source === 'cliff_reflex')
    return `CLIFF REFLEX preempts steering (conf ${r.cliff_conf}${r.cliff_confirmed ? ' · confirmed' : ''})`;
  if (r.decision_source === 'escape')
    return `escape (stuck ${r.stuck_conf}) preempts forward gate ${r.gate_forward ? '✓' : '✗'}`;
  const gate = r.gate_forward ? 'gate 0.4 Hz ✓' : 'gate 0.4 Hz ✗';
  const turn = Math.abs(r.right - r.left) > .1 ? `R-turn ${hz(r.right)} vs L ${hz(r.left)}` : 'neutral';
  return `${turn} · forward ${hz(r.forward)} ${gate}`;
}

function explain(r) {                       // 返回 5 段因果链，见 t2 §5.2
  return [
    { stage: 'raw',    cls: '',      detail: `t=${r.t.toFixed(2)}s · ΔL ${pct(r.contrast_left)} / ΔR ${pct(r.contrast_right)}` },
    { stage: 'signal', cls: 'sig',   detail: `flow asym ${number(r.flow_asymmetry,2)} · loom ${number(r.flow_looming,2)} · cliff ${number(r.flow_cliff,2)} (conf ${number(r.cliff_conf,2)})`,
      active: r.sector_active },
    { stage: 'neural', cls: 'neu',   detail: `fwd ${hz(r.forward)}${r.gate_forward ? ' ✓gate' : ' ✗'} · L ${hz(r.left)} · R ${hz(r.right)} · jump ${hz(r.jump)}${r.gate_jump ? ' ✓' : ''}` },
    { stage: 'judge',  cls: 'jud',   detail: judgeText(r) },
    { stage: 'action', cls: 'act',   detail: `x=${r.x} y=${r.y}${r.jump_event ? ' +JUMP' : ''} → ack ${number(r.game_age,0)}ms` },
  ].map(seg => PRIORITY[r.decision_source] > 1 && seg.stage === 'neural'
    ? { ...seg, preempted: r.decision_source !== 'steering' && PRIORITY[r.decision_source] > 0 } : seg);
}
```

### 2.2 D2 · 因果卡渲染（render() 尾部 + 200ms 节流，P0）

```js
let lastCausal = 0;
function renderCausal(r) {
  const now = performance.now();
  if (now - lastCausal < 200) return; lastCausal = now;      // 5Hz 渲染，低于 1Hz 发布节奏安全
  const host = $('causalChain'); if (!host) return;
  host.innerHTML = explain(r).map(s =>
    `<div class="chain-seg ${s.cls}${s.preempted ? ' preempted' : ''}" data-stage="${s.stage}">
       <span class="chain-label">${s.stage.toUpperCase()}</span><span class="chain-detail">${s.detail}</span>
       <span class="chain-tip" hidden>${s.detail}</span></div>`).join('<span class="chain-arrow">←</span>');
}
// render(packet) 末尾追加： renderCausal(r);
```

下钻（点击滚动 + 1.5s 高亮）与 tooltip hover 用事件委托，一段 ~25 行草稿略（原型 `causal-chain-prototype.html` 已实现，可平移）。

### 2.3 D3 · 视网膜扇区叠加（P2，纯 canvas 2D）

`image('retina', packet.eyes)` 之后追加 overlay 层（独立 canvas `retinaOverlay` 叠放，避免每帧重画基图）：

```js
function drawSectors(r) {
  const cv = $('retinaOverlay'), ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, 256, 128);
  if (!Number.isInteger(r.sector_active)) return;
  for (let i = 0; i < 16; i++) {
    const x = (i % 2) * 128, y = Math.floor(i / 2) * 21.3;      // 2 列×8 行 16 扇区
    ctx.strokeStyle = '#354250'; ctx.strokeRect(x, y, 128, 21.3);
    if (r.sector_active >> i & 1) {
      ctx.strokeStyle = CYAN; ctx.lineWidth = 2; ctx.strokeRect(x + 1, y + 1, 126, 19.3); ctx.lineWidth = 1;
    }
  }
}
```

（扇区几何以 retina.py 实际扇区划分为准对齐；此处示意。）

### 2.4 D4 · 因果时间轴 + ringBuffer（P2/P3）

```js
let ringBuffer = [];                                   // 120s · 每 0.25s 采样一条 row
ws.onmessage = ... if (packet.data.seq > lastSeq)
  for (const r of packet.data.rows)
    if (!ringBuffer.length || r.t - ringBuffer.at(-1).t >= .25) {
      ringBuffer.push(r);
      if (r.t - ringBuffer[0].t > 120) ringBuffer.shift();
    }

function timeline(id) {                                // 四泳道，复用 chart() 网格/裁剪风格
  const L3 = history.filter(r => r.gate_forward !== undefined);
  drawLane(id, L3, [ ['flow_cliff', RED], ['flow_looming', GOLD], ['flow_asymmetry', CYAN] ]);
  // L3 判断条带: gate_forward ✓ 段画紫 2px 条; cliff_confirmed=true 画红 ▲
  // L4: x/y 阶梯线 + jump_event 金色标记（同 chart(marks) 逻辑）
}
```

Escape 表行点击 → `scrubTo(ev.timestamp - 2)`：从 ringBuffer 找最近快照，`renderSnapshot(row)` 冻结各面板；⏵/⏸ 复用 `frozen` 语义。因果弧线（信号峰→响应 +ms 标注）为 P3，检测 `cliff_confirmed` 上升沿与其后首个 `x` 符号翻转。

---

## 3. index.html 改动点

1. **因果卡 section**（新增，横跨 Vision/Neurons 视觉位置）：插在 `</section><!-- vision -->` 之后：
```html
<section id="causal" aria-labelledby="causal-title">
  <div class="section-head"><h2 id="causal-title">Causal Chain · why this action</h2>
    <span id="causalSource">—</span></div>
  <div id="causalChain" class="chain"></div>
</section>
```
2. **时间轴 section**：插在 Activity map section 之前，含 `<canvas id="timeline">` 与泳道标签。
3. **header 回放控制组**：`.session` 内 Freeze 旁加 `<button id="replay" disabled>⏵</button><input id="scrub" type="range" hidden>`。
4. **retina overlay canvas**：`#retina` figure 内加 `<canvas id="retinaOverlay" width="256" height="128" class="overlay"></canvas>`。
5. **Neurons 各 chart-row 加锚点 id**（`id="row-forward"` 等）供下钻定位。

## 4. dashboard.css 改动点

```css
:root{ ...; --purple:#9d7bff; --green:#7dff9d; --red:#ff3c3c }        /* 判断/行动/危险层 token */
#causal .chain{display:flex;align-items:stretch;gap:6px;height:64px}
.chain-seg{flex:1;border-left:3px solid var(--cyan);padding:4px 8px;font-size:12px;
  box-shadow:0 0 6px color-mix(in srgb,var(--cyan) 30%,transparent)}
.chain-seg.neu{border-color:var(--gold)} .chain-seg.jud{border-color:var(--purple)}
.chain-seg.act{border-color:var(--green)} .chain-arrow{color:#536170;align-self:center}
.chain-seg.preempted{opacity:.4;text-decoration:line-through solid #ff3c3c88}
.chain-seg:hover .chain-tip{display:block;position:absolute;...}
#retinaOverlay{position:absolute;inset:0;pointer-events:none}          /* 叠加层 */
#timeline{width:100%;height:120px;display:block}
@media(max-width:900px){#causal .chain{flex-direction:column}          /* t2 §4 窄屏折叠 */
  .chain-arrow{transform:rotate(90deg)}}
```

**布局行数调整**：`main{grid-template-rows:166px minmax(330px,1fr) 163px 275px 265px 50px}` 需在 Vision 与 Neurons 行间插入因果卡行（建议 `64px`），1100px 断点同步 `180px …`；或用 `grid-template-rows:auto …` 降低脆弱性（推荐后者，一次小重构）。

---

## 5. 性能约束分析（50Hz 神经 / 10Hz 帧 / 1Hz 发布）

| 环节 | 约束 | 本方案开销 | 结论 |
|---|---|---|---|
| 神经步进 50Hz | `observe()` 不得拖慢 `m.step()`；`test_observation_does_not_change_model` 保证只读 | 扇区聚合 `reshape+mean` 只在新帧（10Hz）执行，每帧 ~16 次 mean over 128×16，numpy 微秒级；50 tick 中 40 个 tick 仅 dict 追加 6 个标量 | ✅ 无影响 |
| 帧捕获 10Hz | `preview/delta` 已在帧沿计算 | `sector_contrast` 复用同一个 `delta` 数组，不新增像素遍历 | ✅ 复用 |
| 发布 1Hz | packet JSON 大小 | 现状 ~50 rows/s × ~300B ≈ 15KB/s；新增：tick 字段 ~+60B×50 = 3KB/s，帧字段 ~+90B×10 = 0.9KB/s（sector 用 0–100 int、bitmask 而非 float[16]+bool[16]，省 ~70%）→ 总增量 **<4KB/s（+25%），二进制 payload 不变** | ✅ 可接受；如需再压，把 `sector_contrast` 移到 meta 级每 packet 一份（帧间变化小） |
| 前端渲染 | render() 每 packet（1Hz）全量重绘 | 因果卡 200ms 节流实际 5Hz 上限、DOM 为 5 节点 innerHTML；时间轴复用 chart() 管线每秒一次；扇区 overlay 独立 canvas 仅在 sector_active 变化时重绘 | ✅ |
| ringBuffer 120s | 内存 | 480 条 row 引用 ≈ 1MB（不含 activity 快照）；activity 快照若做（P3）480×4KB ≈ 1.9MB，t2 已评估可接受，紧张时降 0.5s 采样 | ✅ |
| JSON 序列化 | `allow_nan=False`（telemetry L71） | 所有新字段必须保证非 NaN：`cliff_conf` 等来自 `round()` 的有限 float；`edge_dir` 用 -1 表示未知，不传 `None`/NaN | ⚠️ 需在测试中固定 |

---

## 6. 协议兼容性评估与新增测试建议

### 6.1 现有测试兼容性

- **test_dashboard_protocol.py**：`schema==3`、`rate_max==50`、payload 长度、`rows[].t` 序列、只读性、`counts` 窗口、change 语义、量化 —— **全部不受影响**（改动均为 JSON 加法、无二进制变化、无模型接触）。唯一注意：`test_dashboard_packet_and_every_tick_timestamp` 中 `obs.observe(frame, 1, ...)` 不传 `causal` → 新字段走 `.get()` 默认值，row 仍可 JSON 序列化（`None` 合法）。
- **test_dashboard_js.py**：node 端 `decodePacket` 不改 → 断言 `n=4096 / rows[0].t==0 / activity 4096 / eyes+change 98304 / 三种异常路径` 全部保持。若在草稿中给 `decodePacket` 加 `causal_schema` 透传，也不破坏任何断言。

### 6.2 建议新增测试（追加到现有文件，不改旧用例）

```python
# tests/test_dashboard_protocol.py 追加
def test_causal_fields_present_and_typed():
    ...  # 构造 causal=dict(cliff_conf=.91, decision_source='cliff_reflex', ...)
    row = obs.observe(frame, 1, control, spikes, GAME, causal=causal)
    assert row['decision_source'] in {'steering','jump','escape','anomaly_reflex','cliff_reflex'}
    assert isinstance(row['sector_active'], int) and 0 <= row['sector_active'] < 2**16
    assert 'sector_contrast' in row and len(row['sector_contrast']) == 16   # 仅新帧行
    obs.observe(frame, 1, control, spikes, GAME, causal=causal)             # 同帧旧 tick
    assert 'sector_contrast' not in obs.rows[-1]

def test_causal_row_json_serializable_no_nan():
    meta = json.loads(...)   # packet() 输出可 json.loads 且 allow_nan=False 不抛

def test_gate_flags_match_thresholds():
    ...  # forward 0.41→True / 0.39→False; jump 2.1→True / 1.9→False
```

```js
// test_dashboard_js.py 的 node -e 脚本追加断言（或新增独立 node 片段）
import {decodePacket} from './web/dashboard.js';   // 若 explain() 导出：
const chain = explain(parsed.data.rows.at(-1));
assert.equal(chain.length, 5);
assert.ok(chain.some(s => s.stage === 'judge' && /preempt|gate/.test(s.detail)));
```

建议将 `explain/judgeText` 以 `export` 暴露（dashboard.js 现已 `export decodePacket`，模式一致），使 JS 逻辑可被 node 测试覆盖。

---

## 7. 实施顺序（对齐 t2 §9 P0–P3）

| 阶段 | 改动文件 | 内容 |
|---|---|---|
| P0 | dashboard.js/index.html/dashboard.css | 因果卡静态链（缺字段显示 '—'）+ tooltip + 下钻 + CSS token |
| P1 | telemetry.py + main.py | §1 全部字段 + `causal_schema=1` + 新测试（6.2） |
| P2 | 前端三件套 | 扇区叠加 + 时间轴 section + escape 行跳转 |
| P3 | dashboard.js | ringBuffer 120s + scrub 回放 + 脑图快照 + 因果弧线 |

每阶段独立可合入、独立可回滚；P0 无协议风险先行验证交互价值。
