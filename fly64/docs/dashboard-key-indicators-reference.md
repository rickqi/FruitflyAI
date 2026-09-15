# Fly64 监控仪表盘关键指标参考
## 用于跨领域能力分析与报告编写

> 基于 `fly64/web/dashboard.js`、`fly64/web/dashboard.css`、`fly64/web/monitor-preview.html` 和 `fly64/docs/dashboard-design.md` 提取
> 版本：F643 仪表盘协议，schema 3

---

## 一、视觉系统指标（Vision System）

| 指标 | 仪表盘显示 | 范围 | 技术含义 | 跨领域关联 |
|------|-----------|------|---------|-----------|
| 复眼预览 | L/R 270° fisheye, 256×128 RGB | 256×128 像素 per eye | 工程光学采样，cone-sampled | 自动驾驶鱼眼相机、360° 环视系统 |
| 亮度变化图 | Frame difference | 256×128 灰度 | 帧间绝对亮度差（不是光流） | 运动检测、安防监控、质检差异检测 |
| 对比度 ΔL / ΔR | Mean absolute luminance diff / 255 | 0–100% | 场景变化量化 | 异常事件检测、环境变化监测 |
| 帧年龄 | Frame age (ms) | ms | 输入停滞检测 | 系统健康监控、信号中断告警 |
| R1–R8 视觉速率 | Visual rate | Hz | 感光器信号处理速度 | 系统吞吐量、视觉带宽度量 |
| 场景识别 | Scene name + hash | 文本 | 环境分类（corridor_2f, terrain, underwater） | 自动驾驶场景分类、环境感知 |
| 局部运动 | Local motion detection | 0–1 | 移动物体检测 | 安防告警、动态障碍物检测 |
| 16 扇区活跃 | 8 azimuth × 2 elevation | bitmask 0–65535 | 空间视野分区的运动活跃度 | 目标定位、区域入侵检测 |
| 信号空间视图 | 270°×144° equirectangular | 240×128 px | 矫正投影后的信号空间布局 | 全景拼接、环视监视器 |

### 技术参数
- 采样方式：cone-sampled（非每个感光器精确显示）
- 帧间变化：仅在 distinct frame sequence number 变化时更新
- 变化停留：保留至下一新帧到来，停滞帧由帧年龄标记
- 视觉连接状态：visual_connected 字段

---

## 二、运动池与控制器指标（Motor & Control）

| 指标 | 仪表盘显示 | 范围 | 阈值 | 技术含义 |
|------|-----------|------|-----|---------|
| 前进池速率 | Forward (DNg100) | 0–10+ Hz | gate > 0.4 Hz | 前进指令神经源头 |
| 左转池速率 | Left (DNa02+DNg13) | 0–10+ Hz | — | 转向指令（左侧） |
| 右转池速率 | Right (DNa02+DNg13) | 0–10+ Hz | — | 转向指令（右侧） |
| 转向差值 | Δ = R - L | -70..+70 | — | 方向决策的量 |
| 跳跃池速率 | Jump (DNp01+DNp10) | 0–10+ Hz | gate > 2 Hz | 跳跃指令神经源头 |
| 跳跃冷却 | Cooldown | 0–0.8s | 0.8s | 跳跃门禁冷却计时器 |
| 神经请求 x | Steering x | -70..+70 | — | 神经端发出的转向值 |
| 神经请求 y | Forward y | 0..70 | — | 神经端发出的前进值 |
| 游戏确认 x | game_x | -70..+70 | — | 游戏端实际接收的转向 |
| 游戏确认 y | game_y | 0..70 | — | 游戏端实际接收的前进 |
| 决策文本 | Decision | 文本 | — | Forward/Idle · steering · jump status |

### 控制器动力学
- 原始控制器公式：`y=clip((forwardHz-0.4)*40, 0, 70)`，`x=clip((rightHz-leftHz)*22, -70, 70)`
- EMA 平滑：0.78/0.22 指数移动平均
- 死区：8 个单位
- 最后整数转换
- 跳跃事件标记：gold=请求, cyan=游戏确认

### 跨领域关联
- 机器人运动控制（前进/转向/跳跃对应轮式/足式控制原语）
- 自动驾驶纵向/横向控制类比
- 工业自动化多轴协调

---

## 三、因果链与决策分析（Causal Chain / Explainable AI）

| 指标 | 仪表盘显示 | 范围 | 优先级 | 含义 |
|------|-----------|------|-------|------|
| 决策源 | decision_source | 枚举 | 5→0 | 当前正在执行的决策来源 |
| 对话 | dialogue | — | 5（最高） | LLM教练覆盖，暂停等决策 |
| 悬崖反射 | cliff_reflex | — | 4 | 反射前置转向（conf ≥ 阈值） |
| 异常反射 | anomaly_reflex | — | 3 | 异常态触发的反射 |
| 逃逸 | escape | — | 2 | 卡住逃逸（stuck_conf 判定） |
| 跳跃 | jump | — | 1 | 跳跃决策 |
| 转向 | steering | — | 0（最低） | 常规转向决策 |
| 场景流不对称 | flow_asymmetry | -1..+1 | — | 旋转光流 |
| 场景流逼近 | flow_looming | 0..1 | — | 物体逼近检测 |
| 场景流悬崖 | flow_cliff | 0..1 | — | 边缘/悬崖检测 |
| 悬崖置信度 | cliff_conf | 0..1 | — | 悬崖判断的可信度 |
| 卡住置信度 | stuck_conf | 0..1 | — | 卡住判断的可信度 |
| 前进门状态 | gate_forward | true/false | — | forward > 0.4 Hz |
| 跳跃门状态 | gate_jump | true/false | — | jump > 2 Hz |
| 前置标记 | preempted | 真/假 | — | 被高优先级源覆盖 |

### 因果链 5 阶段
1. **RAW** — 原始感知时间 t + 对比度百分比
2. **SIGNAL** — 光流加工：asymmetry / looming / cliff + 置信度
3. **NEURAL** — 神经池速率 + 门状态
4. **JUDGE** — 决策仲裁（哪个源胜出 + 理由）
5. **ACTION** — 执行的指令 + 游戏确认延迟(ms)

### 跨领域关联
- 可解释 AI（XAI）——完整决策追溯
- 审计追踪——金融交易/保险核保决策链
- 自动驾驶——多层级决策仲裁（紧急制动 优先于 常规转向）
- 工业安全——反射式紧急停止机制

---

## 四、脑活动图（Brain Activity Map）

| 指标 | 范围 | 技术细节 |
|------|-----|---------|
| 神经元总数 | 166,700（MaleCNS） | 连接组完整 |
| 显示神经元 | ~50K+ located | 已定位 + 未定位分别统计 |
| 活动速率编码 | 0–50 Hz, 256 级量化 | ~0.196 Hz/step |
| 群选择器 | all + named groups | 下拉切换子种群 |
| WebGL 渲染 | 两点大小：2px(all) / 6px(selected) | dim context + 高亮前景 |
| 平均速率显示 | Mean Hz | 选中的子种群均值 |
| 量化窗口 | 13 ticks × 20ms = 260ms | 固定滑动窗口 |

### 跨领域关联
- 神经形态计算部署监控
- 大规模脉冲网络活动可视化
- 脑机接口状态显示

---

## 五、性能与运行指标（Performance & Operations）

| 指标 | 格式 | 含义 | 监控方式 |
|------|-----|------|---------|
| 模拟时间 | t (s) | 仿真世界时间 | 每个 packet |
| 实时比 | RTF (×real time) | 仿真速度/墙钟 | 每个 packet |
| 步进延迟 | latency (ms) | 每 tick 处理时间 | 每个 packet |
| 内存占用 | RSS (MB) | 进程内存 | 每个 packet |
| 丢弃更新 | dropped | 丢失/背压计数 | 每个 packet |
| 游戏状态 | off/receiving/stale/torn/disconnected | 仿真器连接 | WebSocket |
| 桥接停滞 | bridge_stale (5s) | SM64 桥接看门狗 | /flow.json |
| 流错误 | streamError | 协议错误信息 | WebSocket 事件 |
| 协议检测 | F643 magic + schema 3 | 版本校验 | decodePacket |
| 活动连接 | 250ms 保活 | Live/Stale 状态 | setInterval 250ms |

### 稳定性测试指标 (monitor_soak.py)
- 10 分钟浸泡测试
- 最小稳态实时因子
- 模拟器峰值 RSS
- 进程树峰值 RSS（含子进程）
- 原生游戏确认率
- 帧捕获率（>10K frames）
- 跳跃/前进/转向统计

### 跨领域关联
- 生产部署 SLO/SLA 监控
- 容器化部署资源配额
- 实时系统性能基准
- 稳定性浸泡测试流程

---

## 六、空间记忆与导航（Spatial Memory / Navigation）

| 指标 | 范围 | 技术细节 | 跨领域意义 |
|------|-----|---------|-----------|
| 网格大小 | 50×50 | 2500 个单元, 200u/cell | 可调分辨率参数 |
| 覆盖率 | 0–100% | visited/2500 | 搜索/巡检完成度 |
| 访问单元数 | 0–2500 | 已访问计数 | 探索进度量化 |
| 死胡同数 | 0-N | 标记无法前行的位置 | 路径规划瓶颈 |
| 轨迹 | N 个点 | 记录最后 500 位置 | 回溯、回放 |
| 逃逸标记 | 4 类 | stuck/fallen/flow/dead-end | 障碍位置标记 |
| 重复惩罚 | 0-N | revisit_penalty | 避重策略 |
| 健康分数 | 0–100% | health_score | 整体自主性评估 |
| 异常状态 | idle/alarm | anomaly_state | 系统健康监测 |
| BOLD 突破 | 开/关 | forced_bold_explore | 强探索模式 |
| 反射无效 | 开/关 | reflex_ineffective | 自主诊断标记 |

### 跨领域关联
- 机器人 SLAM（直接移植：50×50 网格 → 环境建图）
- 自动驾驶场景记忆（已访问区域 vs 新区域）
- 保险风险地图（理赔空间热力 + 热点标记）
- 巡检机器人（覆盖率监控 + 遗漏区域检测）

---

## 七、卡住检测与逃逸反射（Stuck Detection & Escape Reflex）

| 指标 | 范围 | 阈值 | 类型 | 含义 |
|------|-----|------|-----|------|
| Stuck Score | 0–1 | ≥0.8 | 连续值 | 卡住程度量化 |
| 逃逸原因 | 枚举 | — | stuck/fallen/flow/cliff | 触发类型 |
| 逃逸持续时间 | seconds | — | 连续值 | 从触发到解决 |
| 移动距离 | units | — | 连续值 | 逃逸中的位移 |
| 逃逸时间戳 | seconds | — | 离散事件 | 事件记录 |
| 总逃逸/跌落 | counters | — | 累计 | 运行统计 |
| bold_explore_stuck_s | seconds | — | 策略参数 | 脱离卡住超时 |
| turn_bias | 0–1 | — | 策略参数 | 转向偏好强度 |
| stuck_threshold_s | seconds | — | 策略参数 | 卡住判定超时 |
| climb_mode | 枚举 | — | 策略参数 | 爬起模式 |
| climb_period | seconds | — | 策略参数 | 爬起周期 |

### 历史趋势图
- 60 秒滑动窗口，0.25s 采样
- 颜色梯度：绿色(低)→黄色(中)→红色(高)
- 0.8 阈值指示线
- 60 秒杯中的数据点自动缩放

### 跨领域关联
- 机器人自主故障恢复（卡住→尝试不同策略→记录成功率）
- 工业自动化停机检测与自愈
- 客服机器人对话卡死检测
- 量化交易策略停滞检测

---

## 八、光流信号（Optic Flow）

| 指标 | 范围 | 技术实现 | 含义 |
|------|-----|---------|------|
| Asymmetry | -1..+1 | HRC correlator | 旋转光流（左右不对称） |
| Looming | 0–1 | HRC correlator | 逼近检测（膨胀光流） |
| Cliff | 0–1 | HRC correlator | 悬崖/边缘检测 |
| true_asymmetry | -1..+1 | clamp(asymmetry - 0.08×heading_rate) | 自运动分离后的真实不对称性 |
| hrc_available | true/false | 3 帧预热 | 相关器就绪状态 |
| sector_loom | 32 维数组 | 16 方位 × 上/下 × L/R | 扇区级逼近检测 |
| Cliff confirmed | true/false | 综合判定 | 确认的悬崖事件 |

### 历史趋势图
- 3 条线：asymmetry(cyan) / looming(gold) / cliff(muted)
- 0.3 参考阈线
- cliff_confirmed 红色竖线标记事件
- 因果弧线：cliff detected → 响应延迟(ms)

### 跨领域关联
- 自动驾驶碰撞预警（逼近检测）
- 无人机避障（光流法直接复用）
- 机器人 τ 策略（time-to-contact 计算）
- 工业安全区域入侵检测

---

## 九、时间线与历史回放（Timeline & Replay）

| 组件 | 描述 | 参数 |
|------|-----|------|
| 环形缓冲 | 120 秒, 0.25s 采样 | 约 480 个样本点 |
| 泳道 1 | 光流信号 | asymmetry/looming/cliff |
| 泳道 2 | 神经池速率(Hz) | forward/left/right + 门线 |
| 泳道 3 | 判定带 | 紫色 = gate_forward 活跃, 红色▲ = cliff 确认 |
| 泳道 4 | 动作 | x 阶梯线 + 金色跳跃标记 |
| 因果弧线 | cliff→转向反应延迟 | 紫色弧线 + 延迟标注(ms) |
| 交互操作 | hover=查看因果卡, click=跳转冻结 | timelineInfo 指示 |
| 回放游标 | 紫色虚线 | canvas + setLineDash |

### 跨领域关联
- 事故分析回放（自动驾驶/工业事故）
- 审计日志可视化（金融交易序列）
- 时间线因果追溯（保险理赔全链路）
- 人机交互行为分析

---

## 十、混合智能与自我进化系统（Hybrid AI / Evolution）

| 指标 | 技术实现 | 更新频率 | 含义 |
|------|---------|---------|------|
| 健康仪表 | Health Gauge + 百分比 | 2s | 整体自主运行健康度 |
| 重复惩罚 | Revisit Penalty (↖ 值) | 2s | 空间探索的避重系数 |
| 异常状态 | anomaly_state | 2s | 系统异常态检测(idle→alarm) |
| LLM 决策 | waiting/decided/timeout | 2s | 大模型对话决策状态 |
| LLM 等待时间 | wait_s / 600s | 2s | 决策等待预算 |
| LLM 超时→A | timeout fallback | 2s | 自动降级策略 |
| 教练建议 | coach_advice.json | 5s | LLM 生成的导航建议 |
| 策略参数 | active_strategy.json | 5s | bold_explore/turn_bias/stuck_threshold |
| 进化迭代 | evolution.json | 3s | 脑版本号 + 能力标签历史 |
| 教练帧快照 | coach_frames/*.png | 5s | 每次教练咨询的截图 |
| SOS 面板 | help.json | 2s | 求助信号（位置/场景/原因/诊断） |
| 桥停滞报警 | bridge_stale 红色脉冲 | 2s | SM64 桥接冻结 |
| 导出 | exportTelemetryData | 手动 | JSON 格式全量数据导出 |

### 进化迭代能力标签（示例）
- #14 v2.9.1 · cliff standoff fix
- #13 v2.9.0 · turn alternation + MB mirror
- EVO R21: fallen_recovery strategy climb_mode

### 跨领域关联
- MLOps/LLMOps 全链路监控
- 自适应系统健康管理
- 混合决策系统（规则+LLM）可观测性
- 持续学习系统的在线评估

---

## 十一、跨领域能力映射矩阵

### 金融领域可复用指标
| 仪表盘能力 | 金融映射 | 理论依据 |
|-----------|---------|---------|
| 光流不对称性 | 市场波动不对称检测 | 自运动分离→信号去噪 |
| 逼近检测(Looming) | 波动率聚集/黑天鹅前兆 | 膨胀检测=异常信号放大 |
| 悬崖反射 | 止损/风控触发机制 | 反射前置=自动止损 |
| 卡住检测(Escape) | 策略失效检测 | stuck_score=策略停滞度 |
| 空间记忆覆盖 | 投资组合分散度 | coverage_pct=持仓分散度 |
| EVO 进化闭环 | 策略自优化 | Monitor→Diagnose→Fix→Verify |

### 保险领域可复用指标
| 仪表盘能力 | 保险映射 | 理论依据 |
|-----------|---------|---------|
| 扇区活跃检测 | 理赔区域热力监测 | 16 sectors→区域风险分布 |
| 异常状态检测 | 欺诈模式识别 | anomaly_state→异常行为标记 |
| 轨迹回放 | 理赔全链路审计 | timeline回放→事件序列 |
| 死胡同标记 | 拒赔/争议点标记 | dead-end→处理瓶颈 |
| 健康仪表 | 保单健康度评估 | health_score→综合风险分 |
| 冷却/门禁 | 核保规则引擎 | gate/cooldown→审批流控制 |

### 机器人控制领域直接可移植能力
| 仪表盘能力 | 机器人应用 | 可移植性评估 |
|-----------|-----------|------------|
| 复眼 270° 视觉 | 全向避障相机 | ★★★★★ 直接复用 |
| CX 朝向罗盘 | 惯性导航/方位保持 | ★★★★★ 算法同构 |
| 场景识别 | 环境分类 | ★★★★☆ 替换场景数据 |
| 光流避障 | 无人机自主飞行 | ★★★★★ 完全同构 |
| 空间记忆网格 | 移动建图(SLAM) | ★★★★☆ 调参迁移 |
| 因果链仲裁 | 多级安全决策 | ★★★★★ 框架通用 |
| mmap 桥接 | 机器人中间件 | ★★★★☆ 协议标准化潜力 |
| 蘑菇体联想 | 抓取/操作学习 | ★★★☆☆ 架构概念迁移 |
| EVO 自我进化 | 自适应运动控制 | ★★★★☆ 闭环算法通用 |
| 卡住逃逸 | 自恢复导航 | ★★★★★ 直接复用框架 |

### 其他领域可复用指标
| 领域 | 可复用能力 | 关键指标 |
|------|-----------|---------|
| 自动驾驶 | 鱼眼感知、τ碰撞预测、多级决策仲裁 | looming, cliff, causal chain |
| 工业质检 | 16扇区运动检测、帧间差异分析 | contrast %, sector_active |
| 多Agent系统 | EVO自我进化、LLM教练架构 | evolution iterations, coach strategy |
| 安防监控 | 帧差运动检测、局部运动告警 | change image, local_motion |
| 游戏AI | 端到端神经控制、进化策略 | stick values, escape events |
| 能耗优化 | 实时比、内存占用、步进延迟 | RTF, RSS, latency |

---

## 十二、仪表盘架构要点

### 数据管道
1. **生成端**：`fly64/telemetry.py` — Observatory 类（只读观察者，不修改模型）
   - 13×N 字节环形缓冲跟踪所有神经元的滚动发放率
   - 每 20ms tick 生成一条命名记录
   - 5–10Hz 显示分组打包（不平滑掉控制器事件）
2. **序列化**：F643 协议（shared-memory Bridge + WebSocket）
   - Little-endian `<4sI` header：magic `F643` + JSON 字节长度
   - JSON metadata（schema 3, seq, dimensions, n, rate scale, window, rows, perf counters）
   - N uint8 发放率值（量化 0–50Hz → 0–255）
   - 256×128×3 uint8 眼睛预览
   - 256×128×3 uint8 亮度变化预览
3. **客户端**：`dashboard.js` — 纯前端（无 CDN/外部字体/前端包/FaaS）
   - 浏览器保留最多 10 秒记录 + 最近全神经元/眼睛快照
   - Freeze 保留额外 1 个快照
4. **设计原则**：
   - 仪器化是工程模型的理解工具，不是"果蝇思想"的读取
   - 共同活动本身不建立因果通路
   - 显示转换将原始 spikes/cell/tick 除以 0.02s → Hz

### 布局结构
- 8 行网格：vision(196px) / causal(auto) / motor(330px+) / brain(163px) / memory(300px) / timeline(140px+) / events(265px) / footer(50px)
- 宽屏模式（≥1400px）：2 列 5 行，压缩滚动约 40%
- 回滚开关：`?noviz=1` 或 `localStorage['fly64.causal']='off'`
- 最大 1800px 宽，最小 650px 响应式

---

*本文档基于 Fly64 项目的完整代码审计生成，供跨领域分析团队成员使用。*
*路径：`fly64/web/dashboard.js` + `fly64/web/dashboard.css` + `fly64/docs/dashboard-design.md` + `fly64/web/monitor-preview.html` + `fly64/scripts/monitor_soak.py` + `fly64/tests/test_dashboard_*.py`*