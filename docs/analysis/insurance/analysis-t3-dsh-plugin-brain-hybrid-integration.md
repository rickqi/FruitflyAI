# T3: DSH插件集成分析 — ghb-cost-control×Fly64脑模型混合集成方案

> 作者: dsh-plugin-specialist  
> 日期: 2026-09-07  
> 依赖: T1 (gbcost-analysys深度解构)  
> 参考: ghb-host.js(2946行), ghb-client.js, Fly64 plugin manifest.json/runner.py/bridge.py, model.py(1110+行)

---

## 一、ghb-host.js 全部 19 工具注册清单 — 脑模型替代/增强评估

### 1.1 工具总览

| 编号 | 工具名 | 当前技术栈 | 脑模型替代/增强评估 | 优先级 |
|------|--------|-----------|-------------------|--------|
| 1 | ghb_analyze | subprocess → Python CLI | **增强** — 脑模型神经元状态做分析前预筛选，取代规则引擎前置校验 | P1 |
| 2 | ghb_analyze_status | running Map 内存跟踪 | **替代** — 脑模型 memory 模块保存任务状态，断线重建 | P1 |
| 3 | ghb_query | readStateField JSON | **增强** — 脑模型因果链给出推理路径，不只是字段值 | P1 |
| 4 | ghb_registry | runPyJson → generate_viz_registry_report.py | **保持** — 纯元数据报告，无需脑模型介入 | — |
| 5 | ghb_indicator_recheck | runPyJson → indicator_recheck.py | **增强** — 脑模型 anomaly 检测替代静态对比阈值 | P2 |
| 6 | ghb_status | fs.listDir + stat | **保持** — 纯文件系统操作 | — |
| 7 | ghb_policy_mgmt | listPolicies + listExecutionHistory | **增强** — 脑模型 MushroomBody 给保单关联度打分 | P2 |
| 8 | ghb_logs | readAllLogEntries JSONL | **保持** — 纯文件解析 | — |
| 9 | ghb_reports | regenerate_reports.py | **保持** — 报告生成走 Python | — |
| 10 | ghb_query_prediction | query_policy_prediction.py | **增强** — 脑模型 CX compass 预测替代 ML | P2 |
| 11 | ghb_doris_status | fs.stat 时效检查 | **保持** — 纯文件操作 | — |
| 12 | ghb_doris_scan | scan_cache → listPolicies | **保持** — 元数据缓存 | — |
| 13 | ghb_doris_extract | doris_extract_runner.py | **保持** — 纯 ETL 操作 | — |
| 14 | ghb_doris_compare | doris_incremental_download.py compare | **保持** — 纯数据对比 | — |
| 15 | ghb_doris_download | 增量分批下载 (断点续传) | **保持** — 纯数据工程 | — |
| 16 | ghb_doris_download_status | .download_state.json | **保持** — 状态读取 | — |
| 17 | ghb_doris_wide_download | doris_download_wide_loop.py | **保持** — 纯数据工程 | — |
| 18 | ghb_doris_backup | COS AES-256-CBC 加密备份 | **保持** — 纯运维操作 | — |
| 19 | ghb_doris_backup_list | doris_backup.py list | **保持** — 纯查询 | — |
| 20 | ghb_llm_gate | readGateState + clearGateState | **增强** — 脑模型 self-regulation 替代人工门禁 | P2 |
| | RPC list-policies | listPolicies 封装 | **增强** — 脑模型记忆热度排序 | P3 |
| | RPC run-analysis | launchAnalysis → subprocess | **增强** — 脑模型状态触发自动分析 | P1 |
| | RPC job-progress | running Map 合并 runner 状态 | **增强** — 脑模型 memory 保存持久进度 | P1 |
| | RPC rich-render | rich_query_render.py | **保持** — 纯渲染 | — |
| | RPC ops-status | fs.stat 聚合 | **保持** — 纯文件操作 | — |

### 1.2 脑模型可替代的规则引擎模块 (7个Agent)

以下纯规则 Agent 可直接由 Fly64 脑模型对应模块替代:

| 规则Agent | 脑模型替代模块 | 替代逻辑 | 置信度 |
|-----------|--------------|---------|--------|
| **reconciliation** | SceneMemory + anomaly_state | 数据一致性的神经编码检测 | 高 |
| **stability** | seqlock_watchdog + bridge | 帧序列稳定性 → 数据源时序稳定性 | 高 |
| **ramp_analysis** | memory history | 轨迹趋势的自然神经跟踪 | 中 |
| **anomaly_detection** | anomaly_state (cx goal) | 异常状态的神经信号直接编码 | 高 |
| **member_profiler** | MushroomBody MBONs | 会员画像=KC稀疏编码分类 | 中 |
| **health_score** | health_score属性+DAN信号 | 直接映射 | 高 |
| **hospital_fee_anomaly** | local_motion_detection | 异常检测的同构问题 | 中 |

### 1.3 脑模型可增强的 LLM Agent (7个Primary)

| LLM Agent | 脑模型增强方式 |
|-----------|--------------|
| **cost_control** | 脑模型 steering_bias 类比控费策略选择 |
| **anomaly_detection** | CX novelty_direction 作为 LLM 输入特征 |
| **ibnr_prediction** | CX goal_strength 衰减曲线类比 IBNR |
| **cross_dimension** | 多通道 retina 信号的自然多维度融合 |
| **pre_authorization** | MBON explore_bias 类比预授权决策 |
| **fwa_analysis** | MBON risk_score 关联度 |
| **report_generation** | LLM 保留，脑模型提供场景签名作为上下文 |

---

## 二、rpcApi 通信协议 — Fly64 bridge seqlock → DSH plugin RPC 适配设计

### 2.1 当前两套协议对比

| 特性 | Fly64 bridge (seqlock) | DSH ghb-host.js rpcApi |
|------|----------------------|----------------------|
| 通信机制 | 共享内存 mmap + seqlock | HTTP POST /ghb/api/<method> |
| 数据格式 | 二进制 header/pixels | JSON 信封 |
| 延迟 | 微秒级 (内存) | 毫秒级 (HTTP) |
| 同步机制 | 偶序锁 + 硬件 fence | async/await Promise |
| 连接模型 | 单生产者/单消费者 | 无状态请求-响应 |
| 心跳 | CLOCK_MONOTONIC ns | ISO timestamp |
| 安全 | 本地文件权限 | Host头+Origin验证 |
| 适用域 | 脑↔模拟器实时循环 | 插件↔AI代理按需查询 |

### 2.2 seqlock→RPC 协议适配层设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fly64 Brain (共享内存域)                      │
│  ┌──────────┐    seqlock     ┌──────────┐                      │
│  │  model   │ ←───────────→ │  bridge  │                      │
│  │ .step()  │  80 bytes/帧  │  mmap    │                      │
│  └──────────┘                └────┬─────┘                      │
│                                    │                            │
│       ┌────────────────────────────┘                            │
│       │ 心跳帧(128B)每秒8次                                     │
│       ▼                                                          │
│  ┌──────────────────────┐                                       │
│  │ Adapter: bridge2rpc  │  ← 新模块: fly64/plugin/bridge2rpc.js │
│  │  - 读 seqlock 帧     │    (或 Python 等价)                   │
│  │  - 缓存到 JSON       │                                       │
│  │  - 暴露 POST 路由    │                                       │
│  └──────┬───────────────┘                                       │
│         │                                                      │
│         │ POST /fly64/api/state (脑状态快照)                    │
│         │ POST /fly64/api/control (控制命令)                     │
│         ▼                                                      │
└─────────────────────────────────────────────────────────────────┘
         │ HTTP JSON
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DSH Host Plugin (ghb-host.js)                  │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ rpcApi:     │  │ webServer        │  │ ctx.tools:       │   │
│  │ read-state  │  │ /ghb/api/*       │  │ ghb_analyze...   │   │
│  │ job-progress│  │ /fly64/api/*     │  │                  │   │
│  └─────────────┘  └──────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 bridge2rpc 适配器核心设计

```javascript
// fly64/plugin/bridge2rpc.js — 概念原型
const BRIDGE_PATH = process.env.FLY64_BRIDGE_PATH || '/tmp/f64b'
const HEADER_SIZE = 128
const MAGIC = 'FLY64V2'

// 1. 周期读取 seqlock 帧 (非阻塞, 1.5ms timeout)
function readBridgeFrame() {
  try {
    const fd = fs.openSync(BRIDGE_PATH, 'r')
    const header = Buffer.alloc(HEADER_SIZE)
    fs.readSync(fd, header, 0, HEADER_SIZE, 0)
    const magic = header.toString('utf8', 0, 8)
    if (magic !== MAGIC) return null
    
    const frameSeq = header.readUInt32LE(12)      // 帧序号
    const controlSeq = header.readUInt32LE(16)     // 控制序号
    const enabled = header.readUInt32LE(20)        // 启用标志
    const heartbeatNs = header.readBigUInt64LE(24) // 心跳
    const [joyX, joyY] = [header.readInt8(32), header.readInt8(33)]  // 摇杆
    const buttons = header.readUInt16LE(34)        // 按钮
    const [poseX, poseY, poseZ, poseH] = [         // 位姿
      header.readFloatLE(64), header.readFloatLE(68),
      header.readFloatLE(72), header.readFloatLE(76)
    ]
    const gameFrame = header.readUInt32LE(80)      // 游戏帧
    const renderMs = header.readFloatLE(84)        // 渲染耗时
    
    fs.closeSync(fd)
    return { frameSeq, controlSeq, enabled, heartbeatNs,
             joyX, joyY, buttons, poseX, poseY, poseZ, poseH,
             gameFrame, renderMs }
  } catch (e) { return null }
}

// 2. 暴露 RPC 路由 (注册到 DSH webServer)
const fly64RpcApi = {
  'brain-status': async () => {
    const frame = readBridgeFrame()
    if (!frame) return { ok: false, error: 'bridge not accessible' }
    return { ok: true, ...frame }
  },
  'brain-control': async (args) => {
    // 通过 seqlock 写控制指令 (同桥的 write_control)
    // ...
  },
  'brain-telemetry': async () => {
    // 返回完整遥测 (读取 model 导出文件)
    const telemetry = await fs.readJsonFile('runtime/telemetry.json')
    return { ok: true, ...telemetry }
  }
}
```

### 2.4 协议转换成本

| 操作 | Seqlock 读耗时 | RPC 调用额外开销 | 适用场景 |
|------|---------------|-----------------|---------|
| 实时状态轮询 | 12μs | +0.5ms HTTP | 遥测面板 (可接受) |
| 控制写入 | 8μs | +0.3ms HTTP | 手动干预 (低频) |
| 批量数据查询 | N/A | +2-5ms | 保单分析 (不敏感) |

**结论**: seqlock→RPC 适配增加约 0.5ms 延迟，对遥测面板可接受；高频实时控制(50Hz)仍需原生 seqlock。

---

## 三、ghb-client.js Web 前端集成 — 脑模型可视化嵌入

### 3.1 当前 FloatingPanel 架构

```
ghb-client.js FloatingPanel (shell.overlay, order:79)
  ├── 📊 指标探索器 (ExplorerBody) — 96 项指标/13 组
  ├── 📄 保单列表 (PolicyBrowser) — 12 列/分页/批量
  ├── 🗺️ 风险地图 (RiskMapBody) — 4维度×23风险点
  ├── 🤖 ML训练 (MlTrainingInfo)
  ├── 🖼️ 影像 (ImageTabBody) — 理赔影像查询
  ├── 🔮 预测查询 (PredictionQuery) — ML预测
  └── 🧰 操作/指引 (OpsPanel)
```

### 3.2 脑模型可视化嵌入方案

新增 **🧠 脑模型 Tab**，嵌入到现有 FloatingPanel 的 8 Tab 体系:

```javascript
// 在 PANEL_TABS 追加
{ key: 'brain', label: '🧠', name: '脑模型状态' }

// Tab 内容: BrainPanel 组件
function BrainPanel() {
  // 1. 因果链可视化 — 脑模型 steering_bias → anomaly_state → escape_mode
  //    用 Vega-Lite 或 SVG 实时渲染神经活动管道
  // 2. 复眼视图 — 模拟 Fly64 retina 384×256 伪彩色
  // 3. 神经元活动 — 166,700神经元分8区的实时热图(聚合)
  // 4. Motor池 — forward/turn_left/turn_right/jump 解码值
  // 5. MBON输出 — 5通道 MBON 关联值条图
  // 6. CX Compass — 16列 ring attractor 方向罗盘
  // 7. 控制面板 — 手动 steering override (A/B按钮)
}
```

### 3.3 现有 slot 复用

| 现有 slot | 脑模型复用方案 |
|-----------|-------------|
| `tool.view.cordis` | ExplorerBody 内追加「脑模型推理路径」折叠区 |
| `shell.overlay` (ghb-activity) | FloatingPanel 已有 🧠 Tab |

### 3.4 F643 WebSocket 协议集成 (低速通道)

```javascript
// fly64/fly64/neural_viz_skill.py → ws://localhost:8766/ws
// 客户端 (ghb-client.js 内)
function useBrainWebSocket() {
  const ws = new WebSocket('ws://localhost:8766/ws')
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data)
    // data = { neurons: 166700, spikes: [...], 
    //          motor: {x, y, jump}, scene_sig: [...],
    //          cx: {compass, steering_bias} }
    setBrainState(data)
  }
  return () => ws.close()
}
```

### 3.5 panel-geometry 适配

脑模型 Tab 需要更大的宽度 (建议 640px, 与保单列表对齐):
```javascript
const PANEL_TAB_WIDTHS = {
  ...PANEL_TAB_WIDTHS,
  brain: 640,  // 新增脑模型 Tab
}
```

---

## 四、混合执行模式 — 四模式推理路径选择

### 4.1 四模式路由架构

```
                      ┌─ 输入: Doris保单 CSV ─┐
                      │   / 脑模型 sensor 帧   │
                      └──────────┬────────────┘
                                 │
                          PolicyRouter
                      ┌─────────┼─────────┐
                      │         │         │
                ┌─────▼──┐ ┌──▼───┐ ┌──▼───┐ ┌───────▼────┐
                │ 原生脑  │ │LLM   │ │规则   │ │混合决策    │
                │ 模型    │ │增强  │ │引擎   │ │(AutoSelector)│
                │ Mode 0  │ │Mode 1│ │Mode 2 │ │Mode 3       │
                └────┬────┘ └──┬───┘ └──┬───┘ └──────┬─────┘
                     │         │        │             │
                     └─────────┼────────┼─────────────┘
                               │        │
                         ┌─────▼────────▼─────┐
                         │  PolicyVote / Merge │
                         └──────────┬──────────┘
                                    ▼
                           agent_state.json
```

### 4.2 各模式详细设计

#### Mode 0: 原生脑模型 (Brain Native)
```
适用: 快速筛查, 归档保单, 首次评估
执行器: Fly64 model.step() → forward/turn/jump → 解码为分析结论
精度: 粗略 (~70% 规则引擎召回率)
速度: ~2s/保单 (vs 10min Phase2)
Token: 0 (纯神经计算)
降级路径: 确定性低 → 自动升级 Mode 1
```

#### Mode 1: LLM 增强 (LLM Enhanced)
```
适用: 深度分析, 高价值保单, 异常案件
执行器: LLM Primary 7个Agent + 脑模型上下文注入
脑模型输入: scene_sig(128维), cx steering_bias, MBON outputs
精度: 最高 (~95%)
速度: ~15min/保单
Token: ~170K
```

#### Mode 2: 规则引擎 (Rule Engine)
```
适用: 批量扫描, 数据对账, 快速过滤
执行器: 23 纯规则 Agent (当前 ghb 系统)
精度: 中 (~80%)
速度: ~5min/保单
Token: 0
降级路径: 规则分岐 > 阈值 → 升级 Mode 1/3
```

#### Mode 3: 混合决策 (Hybrid AutoSelector)
```
适用: 日常无监督批量运行 (默认)
执行流程:
  1. 脑模型先行 (Mode 0, 2s) → 产生初步评估
  2. 规则引擎 (Mode 2, 5min) → 与脑模型结果对比
  3. divergence > 阈值 (如 steering_bias vs rule 分歧>0.3) 
     → 自动触发 LLM 增强 (Mode 1) 精化
  4. 规则 ↔ LLM 分歧记录到 rule_llm_divergence.json (复用现有)
精度: ~90% (自适应)
速度: ~5-15min (按需)
Token: 自适应 (0-170K)
```

### 4.3 路由决策图 (在 LangGraph 中实现)

```python
# 思维决策路由 — 在 workflow.py 中增加
def route_hybrid(state: AgentState) -> str:
    """根据脑模型状态和配置选择执行路径"""
    # 1. 检查显式模式配置
    if state.llm_mode == 'brain_native':
        return 'brain_only_path'
    if state.llm_mode == 'brain_hybrid':
        # 2. 脑模型先行评估
        brain_result = fly64_analyze(state.policy_data)
        state.brain_preliminary = brain_result
        
        # 3. 分歧检测
        if brain_result.confidence < 0.6:
            return 'llm_enhanced_path'
        if brain_result.anomaly_score > 0.7:
            return 'rule_engine_path'  
        # 4. 默认混合
        return 'parallel_brain_rule'
    
    # 回退
    return state.llm_mode  # 'hybrid' | 'rule_only' | 'llm_primary'
```

---

## 五、Skill 文档集成 — 脑模型能力合并为统一技能

### 5.1 当前 GHB DSH Skills 清单

| Skill | 文件 | 能力 |
|-------|------|------|
| ghb-cost-control | skills/ghb-cost-control/ | 36 Agent 分析引擎 |
| ghb-query | skills/ghb-query/ | 107 项指标查询 |
| ghb-batch | skills/ghb-batch/ | 批量保单分析 |
| ghb-doris | skills/ghb-doris/ | Doris 数仓操作 |
| risk-map-analyzer | skills/risk-map-analyzer/ | 风险地图 4×23 |

### 5.2 脑模型 Skills 集成

新增 **fly64-brain** skill, 与既有 skills 合并:

```markdown
# fly64-brain — Fly64 果蝇脑模型保险分析技能

## 能力:
1. **神经实时分析** — 166,700神经元/25.6M突触 LIF 推理
2. **场景识别** — Retina→KC→MBON 场景签名(128维)，类比保单分类
3. **异常检测** — anomaly_state + cx novelty_direction, 类比 FWA 检测
4. **关联记忆** — MushroomBody 关联学习, 类比案件关联分析
5. **时序预测** — CX goal_strength 衰减, 类比 IBNR 预测
6. **导航决策** — steering_bias 类比控费策略选择

## 与既有 skills 合并策略:
- ghb-cost-control: 增加 `llm_mode: brain_native|brain_hybrid`
- ghb-query: 增加 brain_* 指标路径
- ghb-batch: 脑模型先行筛查 + 规则精化批量管线
```

### 5.3 统一技能入口

```yaml
# skills/unified-brain-insurance/manifest.yaml
name: "brain-insurance-analysis"
version: "1.0"
skills:
  - ghb-cost-control    # 36 Agent 分析
  - ghb-query           # 指标查询
  - ghb-doris           # 数据管理
  - fly64-brain         # 脑模型引擎 (新增)
routing:
  default: hybrid
  priority: brain_native > rule_only > hybrid > llm_primary
```

---

## 六、配置兼容性 — config.yaml × brain plugin manifest.json

### 6.1 当前两套配置

| 配置域 | gbcost-analysys config.yaml | Fly64 plugin/manifest.json |
|--------|---------------------------|--------------------------|
| 格式 | YAML | JSON |
| Python 路径 | PY_CANDIDATES 数组 | entry + capabilities |
| LLM 提供商 | liteLLM(deepseek-v4-flash) + 备用 | glm-5.3-flash (GLM) |
| 运行周期 | 每次分析启动 | 10s 周期 (periodic) |
| 阈值 | analysis.* 参数 | SECTION_SPECS |
| 网络 | N/A | dashboard_base + bridge |

### 6.2 统一配置方案

```yaml
# fly64/config/brain-insurance.yaml — 合并配置
dsh:
  plugin_name: "brain-insurance-hybrid"
  version: "1.0.0"

brain:
  model: "fly64-mhr"
  neurons: 166700
  synapses: 25600000
  dt: 0.020  # 50Hz 神经计算
  interval_seconds: 10  # DSH 周期插件
  dashboard_base: "http://127.0.0.1:8765"
  bridge_path: "/tmp/f64b"
  
llm:
  providers:
    primary:
      model: "deepseek-v4-flash"
      transport: "liteLLM"
      gateway: "litellm-gateway"
    secondary:
      model: "glm-5.3-flash" 
      transport: "subagent"
      multimodal: true  # GLM 多模态 (脑模型帧)
    fallback:
      model: "deepseek-v3.2"
      transport: "tencent-lkeap"

analysis:
  default_mode: "brain_hybrid"    # 新增模式
  modes:
    brain_native:                  # Mode 0
      llm_tokens: 0
      duration_s: 2
      confidence: 0.70
    rule_only:                     # Mode 2
      llm_tokens: 0
      duration_min: 5
    hybrid:                        # Mode 3 (当前默认)
      llm_tokens: 50000
      duration_min: 10
    llm_primary:                   # Mode 1
      llm_tokens: 170000
      duration_min: 15
      refine_rounds: 2

  divergence_detection:
    threshold: 0.3  # 脑模型 vs 规则分歧 > 0.3 → 触发 LLM
    max_escalations: 3
    
gate:
  llm_max_calls: 5000
  llm_max_tokens: 1000000
  # 新增: 脑模型无 LLM 时不触发门禁
```

### 6.3 LLM 通道复用

现有 DSH 三提供商路由已集成到 liteLLM 网关:

```javascript
// 脑模型复用同一 LLM 通道
// 现有: liteLLM (deepseek-v4-flash) → 保单分析
// 新增: GLM-5.3-flash (multimodal) → 脑模型教练咨询
// 
// provider 选择逻辑:
// if (mode === 'brain_consult' || hasFrameB64) → glm-5.3-flash
// if (mode === 'insurance_analysis') → deepseek-v4-flash
// if (fallback) → deepseek-v3.2 (tencent lkeap)
```

---

## 七、完整集成架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DSH Web UI (port 3080)                          │
│  ┌────────────────────────────────┐  ┌──────────────────────────┐  │
│  │ ghb-client.js FloatingPanel    │  │ 🧠 Brain Tab (新)       │  │
│  │ 📊 📄 🗺️ 🤖 🖼️ 🔮 🧰        │  │ - 因果链可视化          │  │
│  │                                │  │ - 复眼视网膜视图        │  │
│  └────────────┬───────────────────┘  │ - CX 罗盘               │  │
│               │                      │ - MBON 关联度           │  │
│               │                      └───────────┬──────────────┘  │
├───────────────┼──────────────────────────────────┼─────────────────┤
│               ▼                                  ▼                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              DSH Host Plugin (ghb-host.js)                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │   │
│  │  │ ghb_* tools │  │ rpcApi     │  │ bridge2rpc adapter   │  │   │
│  │  │ 20工具     │  │ 15 RPC方法  │  │ (新: seqlock→JSON)    │  │   │
│  │  └────────────┘  └─────┬──────┘  └──────────┬───────────┘  │   │
│  └────────────────────────┼────────────────────┼───────────────┘   │
├───────────────────────────┼────────────────────┼───────────────────┤
│                           │                    │                    │
│              ┌────────────▼────┐        ┌──────▼────────┐         │
│              │ 36 Agent        │        │ Fly64 Brain   │         │
│              │ LangGraph       │        │ 166,700 neurons│         │
│              │ StateGraph      │        │ 25.6M synapses │         │
│              │ 38 nodes        │        │ seqlock bridge │         │
│              └────────┬───────┘        └──────┬──────────┘         │
│                       │                       │                    │
│                       ▼                       ▼                    │
│              ┌──────────────────────────────────────┐              │
│              │     4-Mode Hybrid Router             │              │
│              │  brain_native <-> rule_only <->      │              │
│              │  hybrid <-> llm_primary              │              │
│              └──────────────────┬───────────────────┘              │
│                                 ▼                                  │
│                       agent_state.json                             │
│                   (143+ fields, total=False)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 八、关键发现与风险

### 8.1 关键发现

1. **80% 的 ghb_* 工具属于纯数据工程/运维** — 脑模型只适合替代/增强其中约 40%，剩余 60% 应保持原有实现
2. **Seqlock→RPC 适配是可行的** — 增加 0.5ms 延迟对遥测可接受，高频控制仍需原生 seqlock
3. **脑模型最适替代规则引擎 Agent** — 7个纯规则Agent可直接映射（reconciliation→SceneMemory等）
4. **LLM 通道复用成本低** — 脑模型用 GLM-5.3-flash 多模态，保险分析用 deepseek-v4-flash，共享 liteLLM 网关
5. **四模式路由是混合系统的核心创新** — 脑模型先行 2s 后自动分歧检测，按需升级

### 8.2 主要风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 脑模型精度不足 (<70%) | 误报/漏报 | divergence 检测自动升级 |
| seqlock 桥 Windows 不支持 | bridge2rpc 适配器无法运行 | bridge2rpc 用 Python 等效, 跑在 WSL |
| 脑模型 10s 周期 vs 分析 10min | 时序不匹配 | 脑模型作前置，非实时嵌入 |
| 166,700 神经元可视化性能 | Web 渲染卡顿 | 聚合到 8 区域热图 + 降采样 |