# 监控页面修改影响评估

依据：`web/dashboard.js`（60KB，8 区块）、`web/dashboard.css`、`telemetry.py`（F643 causal_schema=1 packet）、HTTP 端点（README API 表）、布局体系（`--row-*` 变量 + 单列/两列 grid areas）

> **状态**: 🟢 已实现 (Implemented)  
> 此文档中的设计方案已编码实现并部署。实现详情参见对应代码文件与测试。
>

## 1. 结论先行

**必须改的最小集合很小：4 处加法演进，全部兼容旧 schema（`.get()` 容错），无布局重构。** 现有"Neurons→controls 四泳道曲线"是唯一需要新增曲线的区块；因果链组件按取值表自动扩展。

## 2. 逐项评估

### 2.1 必须改（不做会导致新能力不可观测或显示错误）

| # | 位置 | 改动 | 工作量 |
|---|---|---|---|
| M1 | `telemetry.py` tick 行 | 追加 `ctrl_b`/`ctrl_z`/`decision_source` 新值 `cpg_primitive:<name>`；schema 哨兵不变（加法演进） | 0.5h |
| M2 | dashboard.js 神经图表 | "Neurons→controls" 从 4 曲线扩为 6 曲线（+strike/crouch 池率 + 2 条 gate 虚线 0.05/0.03）；溢出 ▲ 标注逻辑复用 | 2h |
| M3 | dashboard.js `explain()` | decision_source 取值表追加 `cpg_primitive` 分支：JUDGE 段显示原语名+相位进度；被抢占时删除线降饱和（现有逻辑自动覆盖） | 2h |
| M4 | `/flow.json` | 追加 `primitive_disp`（原语后 60s 位移）、`mb_mbon_punch/dive/groundpound/longjump`；EVO pattern 条件消费 | 1h |

### 2.2 建议改（提升可观测性，可延后）

| # | 位置 | 改动 | 工作量 |
|---|---|---|---|
| S1 | Causal Timeline | jump 标记旁追加 b/z 动作标记（四泳道 ACTION 泳道） | 2h |
| S2 | Escape Events 表 | 事件类型追加 `cpg_primitive_*`（原语超时熔断/失败记录），复用行点击回放 | 1.5h |
| S3 | Coach 面板 | 教官策略 `active_strategy.json` 支持原语白名单/禁用配置段展示 | 1h |

### 2.3 不改（验证为无需变动）

| 区块 | 理由 |
|---|---|
| Vision / 复眼视图 | 感知侧无变化 |
| Activity map 全脑热图 | 新池神经元本身已有坐标定位，热图自动包含 |
| Spatial memory | `stuck/fall/flow` 语义不变；coverage 逻辑不变 |
| 布局系统（`--row-*` / grid areas / 响应式断点） | 无新区块，仅既有区块内容扩展；行高变量驱动，自动伸缩 |
| 轨迹回放页 / memory-heatmap 组件 | 数据格式不变 |
| `?noviz=1` 降级 | 新组件沿用 `.causal-ui` 类与 try/catch 隔离，零改动 |

## 3. 兼容性保障

- 全部 JSON/WS 变更为加法键；旧前端与新后端（或反之）混跑不报错（README 已确立 `.get()` 容错约定）；
- dashboard.js 为每请求即时读取（资产热更新），前端改动**刷新即生效，无需重启主进程**；
- 唯一不可热更的是 `telemetry.py`/`main.py` 侧（启动快照），随 BRAIN_VERSION 递增走 `consolidate.sh` 重启。

## 4. 总工作量

| 类别 | 估计 |
|---|---|
| 必须（M1–M4） | ~0.5d |
| 建议（S1–S3） | ~0.5d（可拆入后续 EVO 轮） |
| 测试（`test_dashboard_js.py` + `test_dashboard_protocol.py` 用例扩展） | 0.5d |
