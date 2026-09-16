# 脑模型保险融合方案 — 可行性审核与执行建议

> **审核对象**: `docs/analysis/insurance/merged-brain-insurance-deliverable.md` + `fly64-brain-module-to-insurance-mapping.md`  
> **参考项目**: `D:\codes\gbcost-analysys` (v2.0.70-dev, 36 Agent, 19 DSH tools)  
> **脑模型**: `D:\codes\flygym\fly64` (MaleCNS v1.0, 166,700 neurons, Python LIF SNN)  
> **日期**: 2026-09-07

---

## 目录

1. [可行性总评](#1-可行性总评)
2. [环境依赖审核](#2-环境依赖审核)
3. [DSH插件实现方案 — 在gbcost项目中的具体开发计划](#3-dsh插件实现方案)
4. [脑模型WSL环境配置方案](#4-脑模型wsl环境配置方案)
5. [代码改造清单与引用](#5-代码改造清单与引用)
6. [分阶段执行计划](#6-分阶段执行计划)
7. [风险与回退方案](#7-风险与回退方案)

---

## 1. 可行性总评

### 1.1 方案成熟度评估

| 维度 | 评级 | 说明 |
|------|:----:|------|
| 技术可行性 | ✅ **可行** | 两项目均为Python，模块可独立调用 |
| 架构兼容性 | ⚠️ **需适配** | 脑模型为连续LIF SNN，gbcost为离散LangGraph Agent |
| 数据接口 | ✅ **可行** | Doris→CSV管线已就绪，脑模型输入适配器为纯Python |
| DSH插件扩展 | ✅ **可行** | ghb-host.js已有tool注册框架，加brain_*工具为标准化流程 |
| WSL部署 | ✅ **已验证** | fly64已在WSL2上完整运行，gbcost有.venvwsl |
| 团队技能 | ⚠️ **需培训** | gbcost团队需补充SNN/LIF基础，Fly64团队需理解保险领域 |
| 测试覆盖 | ✅ **充分** | gbcost 6134+测试，Fly64 452+测试 |

### 1.2 关键变更点

| 变更项 | 当前状态 | 目标状态 | 工作量 |
|--------|---------|---------|:------:|
| gbcost AgentState | 143字段 | +40 brain_*字段(total=False) | **小** |
| gbcost workflow.py | 38节点StateGraph | +1 brain_switch条件路由节点 | **中** |
| ghb-host.js | 19工具 | +4 brain_*工具 | **小** |
| ghb-client.js | 4 Tab | +1 🧠 Brain Tab | **中** |
| Fly64 model.py | SM64视觉→运动 | 保险数据输入适配器 | **中** |
| bridge2rpc | 不存在 | 新模块fly64/plugin/bridge2rpc.js | **中** |
| WSL service | 单个fly64 | fly64 + bridge2rpc双进程 | **小** |

---

## 2. 环境依赖审核

### 2.1 gbcost-analysys 现有环境

```
D:\codes\gbcost-analysys\
├── .venv\              # Python 3.11 (主环境)
├── .venv313\           # Python 3.13 (辅助)
├── .venv312off\        # Python 3.12
├── .venv314\           # Python 3.14
├── .venvwsl\           # WSL Python 环境
├── config.yaml         # LLM三提供商路由
├── .env                # API密钥
└── skills/ghb-cost-control/plugin/
    ├── ghb-host.js     # 19个DSH工具 (2946行)
    └── ghb-client.js   # Web前端面板
```

**依赖清单**: langgraph, yaml, pandas, mysql.connector, pymysql, qcloud_cos, cryptography, rich, lightgbm, scikit-learn, numpy

### 2.2 Fly64 脑模型现有环境

```
D:\codes\flygym\fly64\
├── .venv\              # Python 3.x
├── fly64/
│   ├── model.py        # 166,700神经元LIF引擎
│   ├── mushroom_body.py  # KC-MBON学习
│   ├── central_complex.py # CX导航
│   ├── retina.py       # 复眼视觉
│   ├── memory.py       # 空间记忆+反射
│   └── bridge.py       # mmap seqlock
├── plugin/
│   ├── runner.py       # 10s自治循环
│   └── manifest.json   # DSH插件清单
└── .cache/malecns/     # 脑数据(~1.3GB)

推荐: WSL2 (Ubuntu 22.04) — 已有.venvwsl
```

### 2.3 环境依赖冲突检测

| 依赖 | gbcost版本 | Fly64版本 | 冲突 |
|------|:----------:|:---------:|:----:|
| numpy | ≥1.24 | ≥1.24 | ✅ 兼容 |
| scipy | ≥1.11 (sparse) | ≥1.11 | ✅ 兼容 |
| pandas | ≥2.0 | — | ✅ Fly64不依赖 |
| langgraph | 1.1+ | — | ✅ 非强制依赖 |
| torch | — | torch | ✅ gbcost不依赖 |
| yaml | pyyaml | — | ✅ Fly64不依赖 |

**结论**: 无直接冲突。两项目可共存于同一Python环境，或保持独立env通过mmap/HTTP通信。

---

## 3. DSH插件实现方案 — 在gbcost项目中的具体开发计划

### 3.1 新增 brain_* 工具注册 (ghb-host.js 修改)

在 `skills/ghb-cost-control/plugin/ghb-host.js` 中注册4个新工具:

```javascript
// ── 新增: 脑模型推理工具 ──

// 1. brain_analyze: 脑模型保单分析
ctx.tools.register(defineTool({
    name: 'brain_analyze',
    description: '使用Fly64果蝇脑模型分析保单理赔/核保风险',
    args: {
        policy_id: { type: 'string', description: '保单号(GP/GA...)', required: true },
        mode: { type: 'string', enum: ['brain_native','hybrid','llm_primary','rule_only'],
                default: 'hybrid', description: '推理模式' },
        force: { type: 'boolean', default: false },
    },
    fn: async (args) => {
        // 1. 读取保单数据 (per-policy CSV)
        const data = await readPolicyCSV(args.policy_id)
        // 2. 调用bridge2rpc (HTTP GET)
        const brainResult = await callBrainAPI('analyze', {
            policy_id: args.policy_id,
            data: data,
            mode: args.mode || 'hybrid',
        })
        // 3. 分歧检测
        const divergence = await detectDivergence(brainResult, args.policy_id)
        return { result: brainResult, divergence, mode: args.mode || 'hybrid' }
    }
}))

// 2. brain_status: 脑模型状态查询
ctx.tools.register(defineTool({
    name: 'brain_status',
    description: '查询Fly64脑模型运行状态',
    args: {},
    fn: async () => {
        return await callBrainAPI('status', {})
    }
}))

// 3. brain_risk_map: 脑模型风险地图
ctx.tools.register(defineTool({
    name: 'brain_risk_map',
    description: '基于脑模型CX罗盘生成16维风险因子地图',
    args: {
        policy_id: { type: 'string', description: '保单号', required: true },
    },
    fn: async (args) => {
        return await callBrainAPI('risk-map', { policy_id: args.policy_id })
    }
}))

// 4. brain_steer: 手动决策覆盖
ctx.tools.register(defineTool({
    name: 'brain_steer',
    description: '覆盖脑模型决策 (人工干预)',
    args: {
        policy_id: { type: 'string', required: true },
        steer_direction: { type: 'string', enum: ['accept','conditional','reject','escalate'], required: true },
        reason: { type: 'string', required: true },
    },
    fn: async (args) => {
        return await callBrainAPI('steer', {
            policy_id: args.policy_id,
            direction: args.steer_direction,
            reason: args.reason,
        })
    }
}))
```

**对应修改文件**: `D:\codes\gbcost-analysys\skills\ghb-cost-control\plugin\ghb-host.js`

**定位参考**: 在现有19个 `ctx.tools.register(defineTool({...}))` 块后追加（代码行~2591之后），在 `export async function apply(ctx)` 范围内。

### 3.2 bridge2rpc 通信适配器 (新文件)

在 `D:\codes\gbcost-analysys\skills\ghb-cost-control\plugin\` 下新建:

```javascript
// bridge2rpc.js — Fly64 seqlock → HTTP RPC 适配器
// 部署在WSL中，与脑模型同进程或独立进程

const BRAIN_BRIDGE_PATH = '/tmp/f64b_insurance'  // WSL桥路径
const FETCH_INTERVAL_MS = 500  // 500ms快照

async function readBrainSeqlock(bridgePath) {
    // 读取共享内存帧
    const fs = require('fs')
    const buf = fs.readFileSync(bridgePath)
    // 解析seqlock协议: header(80 bytes) + payload
    const seq = buf.readUInt32LE(0)
    const x = buf.readInt16LE(4)
    const y = buf.readInt16LE(6)
    const jump = buf.readUInt8(8)
    const ageMs = buf.readBigUInt64LE(16)
    return { seq, x, y, jump, ageMs: Number(ageMs) }
}

async function callBrainAPI(endpoint, payload) {
    // HTTP 调用 WSL 脑模型服务
    const resp = await fetch(`http://127.0.0.1:8766/fly64/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
    return resp.json()
}

module.exports = { readBrainSeqlock, callBrainAPI }
```

### 3.3 🧠 Web Brain Tab (ghb-client.js 修改)

在 `skills/ghb-cost-control/plugin/ghb-client.js` 中新增:

```javascript
// FloatingPanel 新增第8个Tab
// 参考现有4个Tab的注册模式 (ANALYSIS_TAB, DASHBOARD_TAB等)

// 第8个Tab: 🧠 Brain Tab
// slots.inject 注册方式 (参考现有 inject 模式)
// PANEL_TABS 数组追加 brain_tab: { id: 'brain', label: '🧠 脑模型', icon: 'brain' }
// 宽度: 640px (PANEL_TAB_WIDTHS.brain = 640)

// WS连接: ws://127.0.0.1:8766/ (F643协议, 0.5Hz)
// 降级: 脑模型不可用时显示fallback图表
```

### 3.4 AgentState 扩展 (src/agents/state.py 修改)

在 `D:\codes\gbcost-analysys\src\agents\state.py` 的 AgentState 类中追加:

```python
class AgentState(TypedDict, total=False):
    # ... 现有143+字段 ...
    
    # === 🧠 Fly64 脑模型扩展字段 (2026-09-07) ===
    # 感知层
    brain_retina_output: Dict[str, Any]        # 复眼采样结果
    brain_flow_metrics: Dict[str, Any]          # 光流指标
    brain_mb_output: Dict[str, Any]             # 蘑菇体5通道输出
    brain_cx_state: Dict[str, Any]              # CX 16柱罗盘状态
    
    # 决策层
    brain_decision_source: str                  # L1-L5决策来源
    brain_seed: int                             # seed-64可追溯
    brain_causal_chain: List[Dict[str, Any]]    # 因果链
    brain_divergence: Optional[float]           # 规则vs脑分歧值
    
    # 监控
    brain_confidence: float                     # 置信度[0,1]
    brain_latency_ms: float                     # 推理耗时
    brain_mode: str                             # brain_native/hybrid/llm/rule
    brain_version: str                          # 脑模型版本
    
    # 仲裁
    brain_arbitration: Dict[str, Any]           # 5级仲裁结果
    brain_steering: Dict[str, Any]              # 最终转向信号
    brain_risk_scores: Dict[str, float]         # 16维风险评分
```

### 3.5 workflow.py 条件路由修改

在 `D:\codes\gbcost-analysys\src\agents\workflow.py` 中:

```python
# 新增: 脑模型开关节点 (插入在reconciliation之后)
def brain_switch(state: AgentState) -> AgentState:
    """脑模型条件路由: 根据运行模式决定走脑推理还是规则"""
    mode = state.get('brain_mode', 'hybrid')
    if mode == 'brain_native':
        state['brain_decision_source'] = 'L2_brain'
        return _run_brain_inference(state)
    elif mode == 'rule_only':
        state['brain_decision_source'] = 'L1_rule'
        return state  # 走原规则流程
    # hybrid模式: 脑先跑, 分歧检测决定是否升级
    brain_state = _run_brain_inference(state)
    divergence = _detect_divergence(brain_state, state)
    if divergence > 0.3:
        state['brain_decision_source'] = 'L3_llm'
        brain_state['brain_divergence'] = divergence
    return brain_state

# StateGraph 添加节点和边
workflow.add_node('brain_switch', brain_switch)
# 在 reconciliation→stability 之间插入条件路由
workflow.add_conditional_edges('reconciliation', brain_switch_router, {
    'brain_native': 'brain_switch',  # 跳脑推理
    'standard': 'stability',         # 走原流程
})
```

---

## 4. 脑模型WSL环境配置方案

### 4.1 WSL2 现有环境确认

```bash
# gbcost 已有 WSL 环境
# D:\codes\gbcost-analysys\.venvwsl\  — 已在WSL中配置

# Fly64 同样跑在WSL2中  — README.md 已验证
```

### 4.2 桥接模式 — Windows ↔ WSL 通信

因为 gbcost 跑在 Windows 原生（DSH 宿主），而脑模型跑在 WSL2 中，需要跨操作系统通信：

```
Windows (gbcost DSH)                         WSL2 (Fly64 Brain)
┌─────────────────────────┐         ┌─────────────────────────┐
│  ghb-host.js            │         │  fly64 main.py          │
│    │                    │  HTTP   │    │                    │
│    ├─ callBrainAPI() ───┼─────────┼──→ bridge2rpc.js       │
│    │                    │         │    │                    │
│  Node.js 19 tools       │         │  Python LIF SNN 50Hz   │
│  + 4 new brain_* tools  │         │  bridge mmap seqlock   │
└─────────────────────────┘         └─────────────────────────┘
```

**关键配置**:

```bash
# 1. WSL2 内启动脑模型 (常驻)
cd /root/fly64
setsid nohup python3 -m fly64.main --bridge /tmp/f64b_insurance \
  --no-browser --duration 0 > /tmp/fly64_insurance.log 2>&1 </dev/null &

# 2. WSL2 内启动bridge2rpc HTTP服务 (可选, 也可用现有8766端口)
#    现有 HTTP 仪表板已在 8765/8766 端口监听

# 3. Windows 端通过 localhost 访问 WSL2 服务
#    WSL2 自动端口转发: Windows 的 127.0.0.1:8766 → WSL2 的 :8766
```

### 4.3 环境依赖 — WSL2 侧

```bash
# WSL2 Ubuntu 22.04 依赖
sudo apt install -y build-essential python3 python3-venv python3-pip

# Brain 模型依赖
cd ~/fly64
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # numpy scipy flask aiohttp websockets

# 下载脑数据 (~1.3GB)
python -m fly64.data --prepare --cache .cache/malecns
```

### 4.4 环境依赖 — Windows 侧 (gbcost)

```bash
# gbcost 现有环境 (无需额外安装)
# .venv313 — 已验证具备所有依赖
# DSH Host 自动探测: ghb-host.js 中 PY_CANDIDATES 包含 .venv313

# 新增: 需在 .venv313 中验证 requests 或 aiohttp (bridge2rpc HTTP通信用)
.venv313\Scripts\python.exe -c "import requests; print('ok')"
# 如无: pip install requests
```

---

## 5. 代码改造清单与引用

### 5.1 完整文件变更清单

#### gbcost-analysys 侧 (9文件)

| # | 文件路径 | 变更类型 | 变更内容 | 参考行号 |
|:-:|---------|:--------:|---------|:--------:|
| 1 | `src/agents/state.py` | **修改** | 追加40脑模型字段 | L42之后 |
| 2 | `src/agents/workflow.py` | **修改** | 插入brain_switch条件路由节点 | L86-100 |
| 3 | `src/agents/base.py` | **修改** | BaseAgent增加brain_mode检测 | L20-30 |
| 4 | `skills/ghb-cost-control/plugin/ghb-host.js` | **修改** | 注册4个brain_*工具 | L2591之后 |
| 5 | `skills/ghb-cost-control/plugin/ghb-client.js` | **修改** | 新增🧠 Brain Tab (8th Tab) | PANEL_TABS区 |
| 6 | `skills/ghb-cost-control/plugin/bridge2rpc.js` | **新建** | seqlock→RPC适配器 | 新文件 |
| 7 | `config.yaml` | **修改** | 添加brain_mode配置项 | LLM区 |
| 8 | `tests/brain/` (新建目录) | **新建** | 脑模型保险推理单元测试 | 新目录 |
| 9 | `tests/hybrid/` (新建目录) | **新建** | 混合仲裁集成测试 | 新目录 |

#### Fly64 侧 (4文件)

| # | 文件路径 | 变更类型 | 变更内容 | 参考行号 |
|:-:|---------|:--------:|---------|:--------:|
| 1 | `fly64/underwriting/input_adapter.py` | **新建** | Doris CSV→178维输入向量 | 新模块 |
| 2 | `fly64/underwriting/cx_risk_compass.py` | **新建** | CX 16柱核保罗盘 | 新模块 |
| 3 | `fly64/underwriting/mb_underwriting.py` | **新建** | 蘑菇体核保决策 | 新模块 |
| 4 | `fly64/plugin/manifest.json` | **修改** | 添加insurance能力声明 | 能力数组 |

### 5.2 关键代码引用 — gbcost 现有代码

```python
# === 1. AgentState 扩展基址 ===
# D:\codes\gbcost-analysys\src\agents\state.py L42-415
# AgentState(TypedDict, total=False) — 追加brain_*字段

# === 2. workflow 路由锚点 ===
# D:\codes\gbcost-analysys\src\agents\workflow.py L86-100
# StateGraph.add_node / add_conditional_edges 模式

# === 3. DSH工具注册模式 ===
# D:\codes\gbcost-analysys\skills\ghb-cost-control\plugin\ghb-host.js 
# L1-L8: import { defineTool } + export async function apply(ctx)
# L902-2591: 19个 ctx.tools.register(defineTool({...})) 实例

# === 4. 客户端面板注册模式 ===
# D:\codes\gbcost-analysys\skills\ghb-cost-control\plugin\ghb-client.js
# slots.inject / PANEL_TABS 注册方式

# === 5. 保单分析执行入口 ===
# D:\codes\gbcost-analysys\src\cli.py L1-80
# python -m src.cli analyze --policy <id>  模式

# === 6. AgentState 字段读取 (参考降级) ===
# D:\codes\gbcost-analysys\src\agents\base.py L1-60
# BaseAgent: _safe_execute, validate_input, state.get() 安全读取
```

### 5.3 关键代码引用 — Fly64 现有代码

```python
# === 1. LIF SNN 推理引擎 ===
# D:\codes\flygym\fly64\fly64\model.py
# step() — 主推理循环, update_visual(), compute_motion()

# === 2. 蘑菇体 KC-MBON 学习 ===
# D:\codes\flygym\fly64\fly64\mushroom_body.py
# MushroomBody.step() — KC稀疏编码→MBON 5通道, learn() — 三因子Hebbian

# === 3. CX 16柱环形吸引子 ===
# D:\codes\flygym\fly64\fly64\central_complex.py
# CentralComplex.step() — heading/self_motion/goal/navigational_decision

# === 4. 复眼视觉采样 ===
# D:\codes\flygym\fly64\fly64\retina.py
# SphericalRetina.sample() — 1536像素采样
# encode_retina — ON/OFF/颜色/EMD 编码

# === 5. mmap bridge 协议 ===
# D:\codes\flygym\fly64\fly64\bridge.py
# Bridge.read_game_frame / write_controls — seqlock协议

# === 6. 异常检测 (Memory) ===
# D:\codes\flygym\fly64\fly64\memory.py
# MotionStateDetector — 6态检测
# StuckDetector — 卡住检测
# ReflexController — 4反射电路
```

---

## 6. 分阶段执行计划

### Phase 0 (W0): 环境准备与验证 — 3天

| 天 | 任务 | 验证标准 |
|:--:|------|---------|
| 1 | WSL2上启动脑模型常驻 | `curl http://127.0.0.1:8765/bridge-status.json` 返回200 |
| 2 | Windows→WSL2 HTTP连通 | `python -c "import requests; r=requests.get('http://127.0.0.1:8766/fly64/api/status'); print(r.json())"` |
| 3 | gbcost现有测试全绿 | `pytest tests/ -q` → 6134+ passed |

### Phase 1 (W1-2): 最小可行原型 — P0嵌入

**目标**: MushroomBody → FWA引擎 替换验证

```bash
# 1. 在 fly64/下创建保险输入适配器
cd D:\codes\flygym
mkdir -p fly64/underwriting

# 2. 验证脑模型读取保险数据
python -c "
import numpy as np
# 模拟128维保险特征向量 (替代原来的128维场景签名)
insurance_features = np.random.randn(128)
reward_signal = 1.0  # 正反馈(正确识别欺诈)
print('Ready for insurance inference')
"

# 3. 编写最小测试: MushroomBody输入128维→5维输出
# python -m pytest tests/test_mushroom_body.py -q
```

**交付物**: `fly64/underwriting/input_adapter.py` + 验证报告

### Phase 2 (W3-4): DSH工具注册与bridge2rpc

```bash
# 1. 在gbcost中添加桥接文件
cd D:\codes\gbcost-analysys
New-Item skills/ghb-cost-control/plugin/bridge2rpc.js

# 2. 注册brain_analyze工具
# 编辑 ghb-host.js 追加4个 brain_* 工具

# 3. 验证工具注册
# 启动 DSH host → 在 Web 界面看到 23 tools (19+4)
```

**交付物**: bridge2rpc.js + ghb-host.js 修改 + 🧠 Tab 占位

### Phase 3 (W5-8): 核心融合 — CX+MB+AgentState

```bash
# 1. AgentState扩展
cd D:\codes\gbcost-analysys
# 编辑 src/agents/state.py 追加40 brain_*字段

# 2. workflow条件路由
# 编辑 src/agents/workflow.py 追加brain_switch节点

# 3. 验证: 回归测试
pytest tests/ -q --tb=short
# 预期: 6140+ passed (原6134+6新)
```

**交付物**: 完整混合架构代码 + 回归测试通过

### Phase 4 (W9-12): 生产就绪

```bash
# 1. A/B测试
python -m src.cli compare --policy deloitte --mode hybrid
# vs
python -m src.cli compare --policy deloitte --mode rule_only

# 2. 灰度上线
# DSH工具: brain_analyze mode=hybrid → 分歧值记录

# 3. 文档与知识转移
```

**交付物**: 上线报告 + 运维手册

---

## 7. 风险与回退方案

### 7.1 风险评估矩阵

| # | 风险 | 概率 | 影响 | 缓解 | 回退方案 |
|:-:|------|:----:|:----:|------|---------|
| 1 | **脑模型精度<70%** | 中 | 高 | 分歧检测自动升级LLM | 切回rule_only模式 |
| 2 | **WSL网络不稳定** | 低 | 中 | bridge2rpc缓存+重试 | 改为本地模式(同进程) |
| 3 | **AgentState扩展破坏兼容** | 低 | 高 | total=False + brain_前缀 | git revert |
| 4 | **DSH WebSocket冲突** | 低 | 中 | 独立端口8767 | 使用HTTP轮询替代WS |
| 5 | **脑模型版本更新需同步** | 中 | 低 | AgentState含brain_version | version门禁检查 |
| 6 | **保险数据特征维度变化** | 中 | 中 | InputAdapter配置驱动 | 特征工程降维 |

### 7.2 关键决策记录 (ADR)

| ADR | 决策 | 理由 |
|:---:|------|------|
| 001 | bridge2rpc走HTTP而非mmap | gbcost在Windows而脑模型在WSL，mmap不能跨OS |
| 002 | brain_* 工具独立注册而非修改现有 | 保持向后兼容，rule_only模式不受影响 |
| 003 | 默认mode=hybrid而非brain_native | 分歧检测确保安全，精度~90% |
| 004 | 脑模型保持50Hz常驻而非按需启动 | 冷启动~30s，常驻可2秒响应 |
| 005 | AgentState total=False | LangGraph要求，保证字段可选不破坏现有Agent |

### 7.3 修改回退方案

任何阶段如果出现问题，回退路径:

```bash
# 1. 撤销brain_*字段 (不影响现有Agent)
git checkout src/agents/state.py
git checkout src/agents/workflow.py

# 2. 撤销DSH工具
git checkout skills/ghb-cost-control/plugin/ghb-host.js
git checkout skills/ghb-cost-control/plugin/ghb-client.js

# 3. 系统回退到纯规则模式
# config.yaml 中设置 default_mode: rule_only
# 脑模型不可用时DSH自动降级
```

---

## 附录 A: 环境变量清单

| 变量 | 用途 | 默认值 | 设置位置 |
|------|------|--------|---------|
| `BRAIN_BRIDGE_PATH` | WSL脑模型桥路径 | `/tmp/f64b_insurance` | gbcost .env |
| `BRAIN_API_URL` | bridge2rpc HTTP端点 | `http://127.0.0.1:8766/fly64/api` | gbcost .env |
| `BRAIN_DEFAULT_MODE` | 默认推理模式 | `hybrid` | config.yaml |
| `BRAIN_DIVERGENCE_THRESHOLD` | 分歧自动升级阈值 | `0.3` | config.yaml |
| `BRAIN_VERSION` | 脑模型版本门禁 | `>=2.0.0` | config.yaml |

## 附录 B: 命令速查表

```bash
# ===== 脑模型 (WSL2内) =====
# 启动脑模型
cd /root/fly64 && setsid nohup python3 -m fly64.main --bridge /tmp/f64b_insurance --no-browser --duration 0 > /tmp/fly64.log 2>&1 </dev/null &
# 检查状态
curl http://127.0.0.1:8765/bridge-status.json
# 停止
kill $(pgrep -f "fly64.main")

# ===== gbcost (Windows) =====
# 运行保险分析 (混合模式)
python -m src.cli analyze --policy deloitte --mode hybrid
# DSH工具列表
node -e "const h=require('./skills/ghb-cost-control/plugin/ghb-host.js'); console.log(Object.keys(h))"
# 回归测试
pytest tests/ -q --tb=short -x
# A/B测试对比
python -m src.cli compare --policy deloitte --mode hybrid --verbose
```