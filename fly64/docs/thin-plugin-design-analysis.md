# 薄插件（Thin Cordis Tool 层）设计思路分析

> 2026-09-14 · 基于 Host half Builtin 实测（ctx/harness/console/btoa/atob/TextEncoder/TextDecoder——无定时器、无网络、无文件系统）与三层架构原则。

## 一、为什么是"薄"——实测约束决定的形态

对 Cordis Host half Builtin 的实测结论：动态插件的 Host half **没有** setInterval、fetch、文件系统、子进程、LLM 通道。可用的是：

| Builtin | 能力 |
|---------|------|
| ctx.get/on/provide/effect | 服务获取、事件监听、效果管理 |
| harness.defineTool / registerTool | **注册 Agent 可调用的动态 Tool**（核心能力） |
| harness.handle | Package 内 RPC（Client↔Host） |
| console / btoa / TextEncoder | 日志与编码 |

因此"10s 轮询仪表板 → 主动推送告警"的**推模式在 Cordis 层不可实现**——那正是 WSL 自治基底（方案 A）的职责。薄插件只能做**拉模式**：把能力封装成 Tool，等 Agent（教官层的"手"）在会话内按需调用。

这就是"薄"的三层含义：
1. **无状态**：不驻留监控循环（监控已在 WSL 24×7 运行）
2. **无数据平面**：不持有数据管道，数据获取发生在 Tool 被调用的瞬间
3. **无自主性**：不自行决策，只提供"看/问/写"三个动词给教官

## 二、三个 Tool 的职责设计

| Tool | 动词 | 读/写 | 数据源 | 教官层语义 |
|------|------|------|--------|-----------|
| `fly64_status` | 看 | 只读 | agent shell 读 `service_status.json`/`memory.json`/`flow.json`（bash cat，经 Agent 标准工具链） | 一眼看清健康心跳/降级/告警/当前场景标签 |
| `fly64_consult` | 问 | 触发 | 构造 context + 截图 → GLM 咨询（http，密钥在 WSL llm.env） | 按需向 GLM 教官提问（不只被动等升级触发） |
| `fly64_strategy` | 教 | 写 | 校验并原子写 `active_strategy.json`（白名单键 + 数值钳位，复用 sanitize_strategy） | 教官直接修改行为参数（LLM 建议落地的手动通道） |

关键取舍：**数据获取交给 Agent 的 shell**（cat/jq 读 WSL 文件），Cordis Tool 只做 schema 校验、格式化输出与写操作防护。这规避了 Host half 无 fs/network 的硬约束，也不需要 CORS/UNC 改造。

## 三、生命周期与失效模式

| 场景 | 行为 |
|------|------|
| DSH 会话关闭 | Tool 不可用（正常——教官不在场，WSL 自治照常） |
| WSL 自治服务挂了 | `fly64_status` 读到过期心跳（age 超阈值）→ 输出 DEGRADED，教官可介入 |
| 脑模型挂了 | dashboard fetch 失败 → Tool 报 BRAIN-DOWN |
| 策略文件损坏 | `fly64_strategy` 写前校验（sanitize_strategy）+ 原子写，拒收非法键 |

原则对照：教官层是**增强不是依赖**——Tool 全挂，果蝇自身能力群（反射/MB 学习/自治循环）照常运行。

## 四、为什么不在 Cordis 层做更多（对照被否决的方案 B 原始构想）

| 被否决的设计 | 否决原因（实测） |
|------------|----------------|
| Host half 内 10s 定时轮询 | 无定时器 Builtin |
| Host half fetch 8765 | 无网络 Builtin |
| Host half 写 \\wsl$ 策略文件 | 无 fs Builtin；且 /root 属主权限障碍 |
| Host half 直调 LLM | 无 LLM Builtin（LLM = Agent 自身） |

## 五、二期立项建议

- **前置实测**：① Agent 会话内 shell 读 `/root/fly64/plugin/service_status.json` 的可行性（root 属主问题——可能需要 WSL 侧把产物同步到可读路径或 chmod）；② 自治服务稳定运行满 1 周
- **实现顺序**：`fly64_status`（纯读，最先）→ `fly64_consult`（封装 GLMConsultant http 调用为 Tool，需解决进程边界——建议由 WSL 侧暴露 HTTP 咨询端点，Tool 转发）→ `fly64_strategy`（写防护最后做）
- **维护**：Package 版本化 + cordis_run update/rollback；插件变更走 define→run 流程，与 EVO 轮次解耦（插件是教官的工具，不随果蝇脑版本走）
