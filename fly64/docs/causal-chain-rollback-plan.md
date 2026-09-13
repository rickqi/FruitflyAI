# 因果链路增量修改的回滚机制与异常定位手册（任务 t6 · rollback-engineer）

> 承接 t2（`causal-chain-ui-design.md`）与 t3（`causal-chain-implementation.md`）。
> 目标：P0–P3 任一阶段出现布局/显示异常时，**5 分钟内定位嫌疑文件并恢复到修改前布局**，且降级开关一键回到当前最新基线布局（保留 health 仪表 / pills / #decision 等既有功能）。
> 本文不直接修改产品代码；§3 的降级开关代码为落地草稿。

---

## 1. Git 基线与恢复点策略

### 1.1 当前基线（已核实）

- 仓库：`fly64/`（独立 git 仓库），当前 HEAD = **`25a0284`**（"Health gauge: inline 110px style on canvas, immune to CSS load failures"）。
- HEAD 干净可恢复：最近 5 次提交均为独立可 revert 的修复（health gauge 布局反馈环修复、scene identification、fallen recovery 等）。
- **基线污染警告**：工作区有未提交改动，开工会前必须先处理，否则 revert/tag 基线不纯：

| 文件 | 状态 | 处置建议 |
|---|---|---|
| `fly64/model.py` | modified (+16 行) | 与因果链路无关 → 开工前单独提交或 stash |
| `tests/test_model.py` / `test_optic_flow.py` | modified | 同上，与 model.py 同一逻辑提交 |
| `docs/causal-chain-*.md` + `causal-chain-prototype.html` | untracked | 随 P0 提交或单独 docs 提交 |
| `skills/*`, `neural-model/`, `skill-core/` | untracked | 与本任务无关，勿混入 P0–P3 提交 |

### 1.2 恢复点三级策略

```bash
# ① tag 锚定修改前基线（开工第一步）
git tag causal-baseline 25a0284

# ② 每个阶段完成后打 tag（可独立跳回任意阶段）
git tag causal-p0-done   # …之后每个阶段同理

# ③ 长改动期的临时快照（防半成品丢失）
git branch causal-wip && git checkout causal-wip   # 大改前开 wip 分支
```

**兜底（不依赖 git）**：P0 动工前对 `fly64/web/` 三件套做一次文件级快照：

```bash
cp -r web web.bak-causal-baseline    # 或 PowerShell: Copy-Item -Recurse web web.bak-causal-baseline
```

> 理由：dashboard.js 已出现"两段式"历史（核心渲染 + 追加的 history/gauge/export 代码块），git revert 若与后续提交纠缠时，目录级快照是最快恢复手段。

---

## 2. P0–P3 原子提交拆分（每阶段独立可 revert）

对齐 t3 §7 实施顺序，**一阶段 = 一个提交 = 一次 revert**：

| 阶段 | 提交内容（文件） | 回退命令 | 回退影响面 |
|---|---|---|---|
| P0 | `web/dashboard.js`（explain/renderCausal 追加块）、`web/index.html`（#causal section）、`web/dashboard.css`（chain 样式 + grid 行）+ 本 rollback 文档 + `docs/causal-chain-*.md` | `git revert <p0-sha>` | 仅移除因果卡，回到当前布局 |
| P1 | `telemetry.py` + `main.py`（causal 注入、`causal_schema=1`）+ `tests/test_dashboard_protocol.py` 追加用例 | `git revert <p1-sha>` | 前端因果卡自动显示 '—'（P0 已按缺字段容错），无需连锁回退 |
| P2 | `web/` 三件套：retina overlay canvas + timeline section + escape 行跳转 | `git revert <p2-sha>` | 回到 P0+P1 状态 |
| P3 | `web/dashboard.js`：ringBuffer + scrub 回放 + 脑图快照 + header 回放控制组 | `git revert <p3-sha>` | 回到 P2 状态 |

**原子性纪律**：

1. **绝不跨阶段混提交**——尤其不要把 `model.py` / skills 类无关改动带进来（见 §1.1 表）。
2. P0/P2/P3 均触碰 `grid-template-rows`（`dashboard.css` L4/L11），revert 冲突高发区在此两行；冲突时以 `git checkout causal-baseline -- web/dashboard.css` 再手工重放"新增 chain 样式"为最快路径（chain 样式集中在文件尾新增块，重放成本低）。
3. 每阶段提交信息模板：`causal-pN: <一句话> (revert-safe; files: a,b,c)`，便于 `git log --grep causal-p` 定位。
4. revert P1 后**必须重跑** `tests/test_dashboard_protocol.py`——P0 前端对缺字段容错（显示 '—'），P1 后端回退不会导致前端报错，但测试套件要确认协议回到 schema=3 纯净态。

---

## 3. 前端降级开关（kill-switch）设计

**目标**：不改代码、不 revert，URL 或 localStorage 一键禁用全部因果链路新增 UI（因果卡 / 扇区叠加 / 时间轴 / 回放控件），回到当前最新基线布局；**不影响**既有 health 仪表、pills、#decision、escape 表、导出等任何现有功能。

### 3.1 开关定义

```
优先级：URL 参数 ?noviz=1  >  localStorage['fly64.causal'] === 'off'  >  默认开启
关闭方式：http://127.0.0.1:8765/?noviz=1
          或 DevTools: localStorage.setItem('fly64.causal','off') 后刷新
恢复：    ?noviz=0 或 localStorage.removeItem('fly64.causal')
```

### 3.2 实现草稿（dashboard.js，render/init 前置 ~15 行）

```js
// ── causal kill-switch（P0 随因果卡一并合入）──────────────────
const CAUSAL_OFF = new URLSearchParams(location.search).get('noviz') === '1'
  || localStorage.getItem('fly64.causal') === 'off';
if (CAUSAL_OFF) document.documentElement.classList.add('causal-off');
// 渲染守卫：renderCausal/drawSectors/timeline/scrub 各入口第一行
const causalGate = fn => (...a) => { if (CAUSAL_OFF) return; fn(...a); };
```

配套 CSS（追加，不改动任何现有规则）：

```css
/* kill-switch：直接折叠新增 section/overlay，主 grid 行数不变 */
html.causal-off #causal, html.causal-off #timelineSection,
html.causal-off #retinaOverlay { display: none !important; }
html.causal-off #replay, html.causal-off #scrub { display: none !important; }
```

### 3.3 关键设计约束（防"开关引入新 bug"）

1. **grid 行数对称**：因果卡/时间轴按 t3 §4 建议用 `grid-template-rows:auto` 或"新增行在 off 时为 0 高"。若采用固定 `64px` 新增行，`.causal-off` 下必须同步 `main{grid-template-rows:166px minmax(330px,1fr) 0 163px 275px 265px 50px}`（1100px 断点同理）——**这是开关失效时最常见的半塌陷根因**，见 §4-S1。
2. **HTML 结构保留、仅 display:none**：不 `remove()` DOM 节点，保证开启/关闭往返无状态泄漏；`renderCausal` 内已有 `if (!host) return` 双保险。
3. **只读性不受开关影响**：开关只作用于前端渲染，`decodePacket` 与后端 observe 逻辑无关，`test_observation_does_not_change_model` 永远不受牵连。
4. 开关状态可加入 §5 的 DOM 回归断言：`causal-off` 类存在时 `#causal` 的 computed display 必须为 none。

---

## 4. 异常定位手册（症状 → 嫌疑 → 回退命令）

> 三件套职责速查：`index.html` = DOM 结构/section 顺序；`dashboard.css` = grid 行数/断点/新增样式；`dashboard.js` = 渲染逻辑（两段式：核心 render + 尾部追加的 history/gauge/export 块）。

| # | 症状 | 首要嫌疑（按概率） | 定位/回退 |
|---|---|---|---|
| S1 | **布局塔陷**：整页纵向错位、footer 顶上来、某 section 被压扁 | ① `dashboard.css` L4/L11 `grid-template-rows` 行数与 `index.html` `<main>` 子元素数不匹配（因果卡/时间轴 section 增删不同步）；② kill-switch off 时 grid 行未归零（§3.3-1） | 1. DevTools 查 `main` 的 computed `grid-template-rows` 条数 vs section 数；2. `git diff causal-baseline -- web/dashboard.css web/index.html` 只看 grid 行；3. 快回退：`git checkout causal-baseline -- web/dashboard.css`（grid 行恢复原值，新增样式丢一门重放） |
| S2 | **canvas 黑块 / retina 区域全黑** | ① overlay canvas 叠放错位（`#retinaOverlay` `position:absolute` 但父 figure 非 relative，遮挡或错绘）；② dpr/scale 处理破坏 `image()` | 1. 先 `?noviz=1` 验证是否因果叠加层引入；2. 若仍黑 → 与因果无关，查 `web/dashboard.js` `image()` 与 health gauge 的 dpr clamp（HEAD 37baa38/25a0284 曾修过同类）；3. 回退 P2：`git revert <p2-sha>` |
| S3 | **曲线消失**（forward/steering/jump/stick 或 60s 趋势空白） | ① `chart()` 容器高被 grid 行压缩为 0（S1 的局部表现）；② renderCausal 异常抛出截断 render() 尾部后续绘制（**新增代码必须 try/catch**，见下） | 1. Console 看有无 `renderCausal`/`explain` 抛错；2. `?noviz=1` 后恢复 → 定位因果卡渲染块，revert P0；3. 不恢复 → 查 `.history-row`/`.chart-wrap` 高度（css L8） |
| S4 | **仪表环不动 / health gauge 不更新** | ① `renderHealthGauge`（dashboard.js L522 尾部块）被新增代码在前面抛错短路；② gauge canvas 尺寸又被改动（HEAD 25a0284 刚加固过，revert 冲突高危） | 1. Console 错误栈直达文件行号；2. **禁止**为因果改动触碰 `.health-gauge-wrap`/inline 110px 样式；3. `git diff causal-baseline -- web/dashboard.js` 确认 gauge 函数零改动 |
| S5 | **pills 不更新**（health/repulsion/anomaly pill 或 #decision 停滞） | ① WebSocket `onmessage` 内新增 ringBuffer 逻辑抛错，阻断 `history.push`/`render`；② `frozen` 状态被回放 scrub 置位后未复位 | 1. 看 #status 文字：`Disconnected / stale` → 后端/连接；`Display frozen` → 回放未退出；2. 刷新 + `?noviz=1`；3. 回退 P3（ringBuffer/scrub 全在 P3）：`git revert <p3-sha>` |
| S6 | **回放卡死**（scrub 后无法回到 Live） | ringBuffer 空窗（<2 条快照）或 `scrubTo` 未清 `frozen`；escape 行跳转传入越界 t | 1. 临时恢复：点击 Freeze→Resume live（复用既有语义）；2. 回退 P3；3. 修复后补测试：`scrubTo(越界t)` 必须夹取到 ringBuffer 首尾 |
| S7 | **packet 解析失败 / 整页 Connecting** | P1 后端字段含 `None`/NaN，`allow_nan=False` 序列化抛错 | 1. 后端日志看 `json.dumps` 异常；2. `git revert <p1-sha>`；3. 补 §6 测试 `test_causal_row_json_serializable_no_nan` |

**新增代码防扩散纪律**（写入各阶段 review checklist）：P0–P3 所有新增渲染入口必须 `try{...}catch(e){console.warn('causal render failed',e)}` 包裹——保证因果链路任何异常**只能杀死自己，不能杀死既有 render() 管线**（对应 S3/S4/S5 三大高危症状）。

---

## 5. 测试核对与新增 DOM 结构回归断言

### 5.1 现有测试适用性（已核对源码）

- **tests/test_dashboard_protocol.py**：P1 的核心防线。`schema==3`、payload 长度、只读性断言不受加法演进影响；P1 回退（revert）后必须全绿回归。注意 t3 草稿中 `observe(frame,1,...)` 不传 `causal` 的用例——回退 P1 后这些用例随文件回退消失，无残留。
- **tests/test_dashboard_js.py**：node 端 `decodePacket` 纯二进制校验，P0/P2/P3（纯前端展示层）不影响任何断言；P1 若给 `decodePacket` 加 `causal_schema` 透传也不破坏。**局限**：它只测数据解码，不测 DOM/布局——这正是需要新增断言的原因。

### 5.2 建议新增：DOM 结构回归测试（tests/test_dashboard_dom.py，零浏览器依赖）

用 node 对 `web/index.html` 做静态结构断言（无 jsdom 也可用正则/解析；有 jsdom 更佳），防"section 增删与 grid 行数失配"（S1 根因）进主干：

```python
NODE_CHECK = """
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const html = readFileSync('web/index.html','utf8');
const css  = readFileSync('web/dashboard.css','utf8');
// ① main 直接子 section 数与 grid-template-rows 逗号段数一致
const sections = (html.match(/<section[\\s>]/g) || []).length;
const rows = css.match(/main\\{[^}]*grid-template-rows:([^}]*)\\}/);
assert.ok(rows, 'main grid-template-rows must exist');
assert.equal(rows[1].split(/\\s+/).filter(Boolean).length, sections + 1 /*footer*/,
  'grid rows count must match section count (S1 regression)');
// ② 关键既有元素永不丢失（回滚后的守护清单）
for (const id of ['retina','change','decision','forwardChart','steeringChart',
                  'jumpChart','stickChart','brain','memoryHeatmap','healthGauge',
                  'escapeBody','healthPill','repulsionPill','anomalyPill','status','freeze'])
  assert.ok(html.includes(`id="${id}"`), `existing feature lost: ${id}`);
// ③ kill-switch 类存在时新增 section 被折叠（css 契约）
assert.ok(/html\\.causal-off[^}]*#causal[^}]*display:\\s*none/.test(css.replace(/\\n/g,'')),
  'kill-switch must hide #causal');
// ④ grid-template-rows 不得出现负值/0 以外的非法 token（防手滑）
assert.ok(!/grid-template-rows:[^;}]*-/.test(css), 'no negative row heights');
"""
```

配套 JS 纯函数测试（并入 test_dashboard_js.py 或独立）：若 `explain/judgeText` 按 t3 §6.2 建议 `export`，node 端断言 5 段链结构 + 缺字段容错（`cliff_conf` 为 undefined 时 `judgeText` 返回 'awaiting causal fields' 而非抛错）——这是 S3 防扩散纪律的自动化验证。

### 5.3 回滚演练检查单（每次阶段合入前 2 分钟执行）

1. `python -m pytest tests/test_dashboard_protocol.py tests/test_dashboard_js.py` 全绿；
2. 打开 `http://127.0.0.1:8765/` 正常 → 加 `?noviz=1` 刷新：新增 section 消失、既有五段 + health/pills 完好；
3. `git tag causal-pN-done`。

---

## 6. 一页速查（回退决策树）

```
仪表板异常
├─ Console 有 causal/chain 相关报错？
│   ├─ 是 → ?noviz=1 验证 → 消失：定位阶段 → git revert <该阶段sha>
│   └─ 否 ↓
├─ 仅新增 section 区域异常 → revert 对应阶段（P0 卡 / P2 overlay+时间轴 / P3 回放）
├─ 既有布局异常（S1 塔陷）→ git checkout causal-baseline -- web/dashboard.css
├─ 数据/解析异常（S7）→ git revert <p1-sha>（后端）
└─ 全线失守 → git checkout causal-baseline -- web/   （回到修改前完整布局）
```
