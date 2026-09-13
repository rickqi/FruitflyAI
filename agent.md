# FruitflyAI 项目记录

## 工作流程规则

1. 按优先级顺序执行任务（P1 → P2 → P3 → P4）
2. **每完成一个任务**，立即更新 agent.md 变更说明
3. **每完成一个任务**，立即 `git add`、`git commit`、`git push`
4. 确保 `README.md` 和 `agent.md` 同步更新
5. 脑模型需重启使网页文件生效（HTTP 缓存）
6. 保留每个 commit 的根因分析和变更内容说明
7. **每轮 EvolutionSkill 进化后**：
   - **必须重启脑模型**——这是技能进化生效的基础（相当于"睡一觉"后新能力才被加载）
   - **必须递增 `main.py` 的 `BRAIN_VERSION`**（skill/行为管线更新推送时强制）
   - **必须将本轮 skill 闭环执行总结**（触发原因、发现、修复、能力变化）**作为一次完整进化记录写入变更说明并推送**
8. 每轮进化能力需配套**回归测试**（`tests/test_evolution_capability.py`），确保进化能力可重复验证、不退化

## 项目结构

```
D:\codes\flygym\
├── fly64/                    # Fly64 果蝇脑控制 Mario 项目
│   ├── fly64/                # Python 核心源码
│   │   ├── main.py           # 主循环 + HTTP API
│   │   ├── memory.py         # 空间记忆 + 卡住检测 (Phase 1)
│   │   ├── bridge.py         # 共享内存桥接 (Linux/macOS)
│   │   ├── model.py          # LIF 神经元模型
│   │   ├── retina.py         # 球面复眼采样
│   │   ├── telemetry.py      # 仪表板遥测
│   │   ├── data.py           # MaleCNS 数据下载/预处理
│   │   └── replay.py         # 回放录制
│   ├── web/                  # Web 仪表板
│   │   ├── index.html        # 主仪表板
│   │   ├── memory-heatmap.js # 空间记忆热力图
│   │   ├── dashboard.js      # 仪表板 JS
│   │   ├── dashboard.css     # 仪表板样式
│   │   └── trajectory.html   # 3D 轨迹回放 (Three.js)
│   ├── scripts/              # 安装/运行脚本
│   ├── patches/              # sm64ex Fly64 补丁
│   ├── tests/                # 测试
│   │   └── test_memory.py    # memory.py 单元测试 (19 tests)
│   ├── docs/                 # 文档
│   └── README.md             # 完整安装指南
├── scripts/                  # FlyGym 相关
├── agent.md                  # 项目记录 (本文件)
└── README.md                 # 项目总览
```

## 环境

- **Windows**: WSL2 Ubuntu-22.04
- **Python**: 3.10 (WSL) / 3.11 (Windows venv)
- **SM64**: sm64ex (patched) - sm64.us.f3dex2e
- **Brain Data**: MaleCNS v1.0 (166,700 neurons)
- **GitHub**: https://github.com/rickqi/FruitflyAI.git

## 运行状态

| 组件 | 位置 | 状态 |
|------|------|------|
| 脑模型 | WSL PID # | **v2.1.0** (T4/T5 HRC 方向选择运动检测) |
| SM64 游戏 | WSL PID # | 运行中 |
| 仪表板 | http://127.0.0.1:8765/ | ✅ |
| 3D 轨迹 | http://127.0.0.1:8765/trajectory.html | ✅ |
| 空间记忆 | http://127.0.0.1:8765/memory.json | ✅ |
| 轨迹 API | /trajectory.json /trajectory-list.json /trajectory-load | ✅ |

---

# 变更日志

## 2026-09-13: EVO Round 9 — Brain v2.2.0（室内围闭度检测 + 天空蓝色度门控）

**触发**：实测在建筑物内（蓝地毯/深色格纹天花板/立柱）场景被识别为"天空·山坡"。根因：sky_score 仅测上视野亮度（天花板灯/亮格纹误判为天空 0.46-0.82），ramp_score 把墙面明暗渐变当斜坡（0.41），classify_terrain 无室内类别。

**变更**（LEARN）：
- `retina.py` compute_flow 新增 `enclosure_score`（围闭度 = 0.6×天花板信号[(1-蓝色度)×上视野结构边缘×8] + 0.4×墙边缘[|edge_90|+|edge_0|]×3）与 `upper_blue`（上视野蓝色主导度）；sky_score 乘蓝色门控 `min(1, upper_blue×4)`；`enclosure>0.35` 时 terrain 覆盖为 `indoor`
- `model.py` 透传 `enclosure_score`；`main.py` 场景名新增"室内"标签（优先级最高）+ flow.json 两处新增字段；`telemetry.py` 每 tick 行携带 `enclosure_score`
- BRAIN_VERSION 2.1.0→2.2.0；SKILL_VERSION 2.5.0→2.6.0

**PIN**：test_retina.py 新增 3 用例（室内/室外合成场景 enclosure 分离、indoor terrain 标签+sky 抑制、加法键），全绿；修复 _hv_pair_ab 数组拼接 bug（int32 数组误用 +）；dashboard/evolution 套件 35 全绿；memory 8 失败既存。

**CONSOLIDATE**：首次使用制度化的 `scripts/consolidate.sh`——自动检测 SM64 进程（PID 18092）→ 完整模式接 /tmp/f64b → 实测 `flow.json brain_version=2.2.0` ✅、`enclosure_score` 在线（0.33）、`decision_source` 恢复 steering/escape 交替（escape 黏滞缓解）。

**RECORD**：skills.md 轮次表 + Round 9 + v2.6.0 章节。

---

## 2026-09-13: P1–P3 视觉能力增强 — Brain v2.0.0（颜色视觉 + 4方向运动检测 + 小目标追踪 + 蘑菇体学习）

**背景**：基于 FlyWire MaleCNS v1.0 实验（6字符识别, 38ms, 200nW）与 Fly64 现状的视觉能力差距分析（~38%覆盖），通过 7 人 AgentTeams 完成分析→设计→评估→路线图→实现全流程，落地 3 阶段 4 项能力增强。**需重启脑模型后生效**（`pkill -f 'python.*main'`，重新加载 `BRAIN_VERSION=2.0.0`）。

### 新增具体能力（脑模型重启后激活）

**🎨 颜色/UV 视觉感知**（P1a）
- 红/蓝/绿/UV 逼近 4 通道编码，替代单一灰度亮度
- 🆕 `danger_red_index`: 感知前方熔岩/红色敌人 → 提前转向避让（预期熔岩坠落 -30%→-15%）
- 🆕 `sky_blue_index`: 感知天空开阔区域 → 引导探索前进（预期导航正确率 50%→70%）
- 场景签名从 1 通道 → 5 通道，混淆碰撞率从 ~10³/天 降至 <1/年

**🌀 4方向运动检测**（P1b）
- 从单一左右不对称标量 → 4 方向矢量（↑↓←→），模拟果蝇 T4/T5 细胞
- 🆕 垂直运动检测: 感知升降平台/地形起伏，触发减速或跳跃
- 🆕 OFF-主导运动检测: 识别独立移动物体（Goomba/Koopa）→ 提前避让（预期躲避距离 3→5 体长）
- 🆕 对称水平流: 走廊中保持直线前进（预期墙壁碰撞 -40%）

**🎯 小目标追踪**（P2）
- 🆕 中心-周边运动对立: 从背景光流中分离独立运动物体（LPLC/LC11 等效）
- 🆕 卡尔曼滤波预测: 估算移动平台拦截时机 → 预判跳跃（预期平台跳跃 30%→65%）
- 🆕 匈牙利匹配: 多目标同时追踪（可同时跟踪多个 Goomba/Koopa）
- ⚠️ LIF 注入修复: 跳跃电流移至 spike 前注入，确保拦截帧立即生效

**🧠 多巴胺蘑菇体学习**（P3）
- 🆕 2000 个 Kenyon Cell 稀疏编码（top-5%活跃）：场景→动作关联的神经基础
- 🆕 三元因子 Hebbian 可塑: 仅修改活跃突触（FlyWire 精确匹配反馈机制）
- 🆕 代理奖励系统: 前进(+0.3) / 探索新区域(+0.5) → 多巴胺奖励；坠落(-0.8) / 卡住(-0.3) → 多巴胺惩罚
- 🆕 5 个 MBON 输出通道（前进/左转/右转/跳跃/探索）→ 逐步学会趋利避害
- 学习曲线: 0~1000帧权重初始化 → 1000~5000帧形成偏好 → 5000+帧稳定关联

### 技术变更

**新模块**: `fly64/fly64/mushroom_body.py`（~260行, MushroomBody 类）
**新增方法**:
- `retina.py`: `encode_color()`, `_per_cell_color()`, `compute_emd()`, `_build_grid_maps()`, `compute_small_targets()`
- `model.py`: `_compute_dopamine()`
- `memory.py`（迁移）: `TargetTracker` 类
**修改文件**: retina.py (18处), model.py (14处), main.py (1处), agent.md, fly64/README.md
**新测试**: `tests/test_mushroom_body.py` (27回归测试用例)

### 验证
- 全量 pytest: **179/179 核心测试通过**（15失败均为既有 Windows 兼容问题）
- compute_flow 返回键: 27 → ~62 (新增 35 个视觉信号)
- EMD 方向对: left_to_right=1440, up_to_down=1503
- 计算预算合计: ~190 μs/帧 (=0.95% of 20ms)
- 视觉覆盖度提升: ~38% → ~90%

### 💾 如何启用
```bash
# 1. 重启脑模型
pkill -f 'python.*main'
# 2. 重新启动
python3 -m fly64.main --bridge runtime/fly64_bridge.bin \
  --record artifacts/latest-replay.npz --no-browser --duration 0
# 3. 验证版本
curl http://127.0.0.1:8765/memory.json | grep brain_version
# 应返回 "brain_version": "2.1.0"
```

**触发**：EvolutionSkill 诊断循环发现 2 项 findings（fallen_recovery_stuck high / reflex_cooldown_gap medium，conf 均为 1.0）。因果时间轴上 x 固定方波 + 因果卡 `escape (stuck 1.00)` 为可视化证据。

**变更**（LEARN）：
- `memory.py` ReflexController：update() 增加 `stuck_duration` 参数；`_start_reflex` 冷却自适应缩放 `max(0.25, 1 - stuck_duration/120)`——卡得越久反射重触发越频繁（修复固定 10s 冷却失效问题）
- `main.py` 坠落恢复：初始转向方向随机 ±50（原固定 -50 左偏），镜像交替保留；BRAIN_VERSION → 1.4.0

**PIN**：test_evolution_capability.py 新增 3 用例（自适应冷却缩短 / 默认参数向后兼容 / 初始方向随机化源码断言），16→19 用例全绿；test_memory 8 失败经 stash 基线对照为既存问题。

**CONSOLIDATE**：同步 WSL /root/fly64，脑模型重启，实测 `flow.json brain_version: 1.4.0` ✅；因果字段（causal_schema=1 / decision_source）持续在线。

**RECORD**：skills.md 轮次表 + Round 6。

---

## 2026-09-12: 神经因果链路可视化 (P0–P3 全量落地)

### 背景
仪表板无法直观展示"视觉信号→神经元处理→判断逻辑→具体行动"的因果链。经 AgentTeams 两轮团队（方案设计 dashboard-viz + 布局审核 dashboard-viz-audit）产出 6 份设计/审核文档后，按 GO(有条件) 结论执行三个前置并落地 P0–P3。

### 前置（commit a26caca / 83ed3b3）
- **基线锚定**: 干净基线打 `causal-baseline` tag；B1(model.py flow 先用后赋) 确认已由 8f3428a 修复，pytest 全绿
- **G1 修复**: dashboard.css L5/L12 `section:nth-child(2)` → `section.motor-section` 类选择器（防未来插 section 击穿 Neurons 网格）
- **noviz kill-switch**: `?noviz=1` > `localStorage['fly64.causal']='off']`；dashboard.js 顶部环境守卫设置 `body.causal-off`；CSS 契约 `body.causal-off .causal-ui{display:none!important}`——所有因果元素必须携带 `causal-ui` 类

### P0 决策解释卡 (6bbf5be, 纯前端)
- 新增 Causal Chain section（Vision/Neurons 之间）：explain()/judgeText() 五段链卡 RAW→SIGNAL→NEURAL→JUDGE→ACTION，紫=判断/绿=行动层色
- 缺 P1 字段时优雅降级 '—'/'awaiting causal fields'；200ms 节流；try/catch 隔离不短路 render 管线
- 悬停 tooltip + 点选下钻（滚动高亮 1.5s，事件委托）

### P1 遥测因果字段 (7d5eba0)
- `Observatory.observe(causal=)` 新参数：每 row 增加 cliff_conf/stuck_conf/cliff_confirmed/decision_source；gate_forward(>0.4Hz)/gate_jump(>2Hz) 与渲染阈值同源派生；meta 增加 `causal_schema=1` 哨兵
- main.py 控制级联末尾 decision_source 审计：dialogue > cliff_reflex > anomaly_reflex > escape > collision > jump > steering（含 t8 评审 R2 要求的 collision 分支）
- 新增 test_causal_fields_present_json_safe_and_degrade（枚举校验/JSON allow_nan 安全/legacy 调用降级）

### P2 扇区叠加 + 因果时间轴 (813b74a)
- telemetry.py 帧沿复用 delta 数组计算 sector_contrast(int16 0–100)/sector_active(bitmask)，仅帧行携带；显示空间 8 方位×上下分带（与眼图渲染对齐）
- dashboard.js：retinaOverlay 描边叠加（.eyes figure position:relative 锚点，V1 前置）；120s/0.25s ringBuffer；drawTimeline 四泳道（flow/池率+gate 虚线/判断条带+cliff▲/action x 阶梯线+jump 金标），1s 节流
- index.html 新增 Causal Timeline section + overlay canvas（均 causal-ui）；grid 行数 8=7 sections+footer（两断点）

### P3 因果弧线 + 回放跳转 (4e4cd00)
- drawArcs：cliff_confirmed 上升沿 → 1.5s 内首个 x 符号翻转，紫色弧线 + "+ms" 延迟标注
- Escape 表行点击 → 时间轴跳到事件前 2s 并冻结（复用 frozen 语义），显示该时刻因果卡；Freeze/Resume 恢复实时

### 验证
- test_dashboard_protocol + test_dashboard_js: 6 passed（含新 causal 测试）；node 草稿检查 9/9；node --check 语法 OK
- 后端 packet 解码实测: causal_schema=1、sector 字段 16 项、json allow_nan 安全
- test_memory 8 失败经 git stash 基线对照确认为 HEAD 既存问题，与本次无关

### 回滚
- 逐阶段 revert: 4e4cd00(P3) → 813b74a(P2) → 7d5eba0(P1) → 6bbf5be(P0) → causal-baseline
- 运行时: http://127.0.0.1:8765/?noviz=1 一键回到修改前布局
- 详见 fly64/docs/causal-chain-rollback-plan.md（7 症状定位手册）

---

## 2026-09-11: Phase 1 导航增强 + 卡住修复

### 变更 1: 空间记忆地图 + 卡住检测系统 (新模块)

**原因：** 果蝇脑模型只有 260ms 神经记忆窗口，无法检测是否在重复路线或卡住。导致马里奥经常撞墙后原地转圈，没有有效的逃脱策略。

**变更内容：**
- **新增** `fly64/fly64/memory.py` — 三个核心类：
  1. `StuckDetector` — 三信号融合卡住检测（temporal_energy 视觉坍缩、game_frame 停滞、forward_rate 下降）
  2. `SpatialMemoryMap` — 50×50 单元网格地图（200 unit/格），记录访问计数、recency 衰减、novelty 计算、loop_score 循环检测
  3. `MemoryController` — 整合 stuck + spatial 输出 escape_behavior 标志
- **新增** `fly64/tests/test_memory.py` — 19 个 pytest 测试覆盖全部功能
- **修改** `fly64/fly64/model.py` — 新增 `escape_mode` 属性、`step()` 接受 `novelty` 参数、新奇度门控视觉增益（novelty<0.3 时 ×1.1, >0.7 时 ×0.9）
- **修改** `fly64/fly64/main.py` — 集成 MemoryController、escape 控制覆盖（转向+前进爆发交替）、`/memory.json` 端点
- **新增** `fly64/web/memory-heatmap.js` — 50×50 网格热力图 canvas 渲染器（蓝→绿→黄→红渐变 + 当前位置白点，1s 自动刷新）
- **修改** `fly64/web/index.html` + `fly64/web/dashboard.css` — 新增 "Spatial Memory" 仪表板面板

**涉及文件：** 8 文件（3 新增，5 修改），~730 行

---

### 变更 2: Stuck 诊断 — 坠落检测 + FailureMemory

**原因：** 运行中发现马里奥卡住的原因是 Y 坐标异常（Y=-221，低于地面正常值 120），实际已掉出地图边界。原 escape 行为设置 `y=0`（停止前进）导致马里奥只转圈不前进，卡住检测持续触发形成死锁。

**根因分析：**
1. 果蝇脑缺乏避障能力，在马里奥走到 Bob-omb Battlefield 边缘时继续向前 → 坠落
2. 坠落时 Y 从 120 降至 -200+，游戏物理引擎限制移动
3. Escape 行为启动 → 随机转向 + `y=0` → 没有前推动力 → 位置不变 → stuck_score 不降
4. 无限循环：卡住→escape→y=0→转圈→仍卡住→继续escape

**变更内容：**
- **修改** `StuckDetector.__init__()` — 新增 `y_min`/`y_max` 参数，默认 `y<-100 ∨ y>1000` 判定为 fallen
- **修改** `StuckDetector.update()` — 增加 `pos_y` 参数，返回 `(stuck_score, stuck_duration, fallen)` 三值元组
- **新增** `FailureMemory` 类 — 记录坠落位置网格键，`avoid_direction()` 方法检查前方格是否为已知坠落点，返回转向偏置
- **修改** `MemoryController.update()` — 增加 `pos_y` 参数，fallen 状态下强制触发 escape_behavior
- **修改** `main.py` escape 逻辑 — 区分 fallen/stuck 两种模式：
  - Fallen：跳跃 + 前进 + 持续跳跃的坠落恢复模式
  - Stuck：交替 0.8s 转向 + 0.8s 前进爆发，集成 failure 避让
- **修改** `/memory.json` 输出 — 增加 `fallen`, `failure_count` 字段
- **修改** `main.py` memory update 调用 — 传递 `pos_y=pose[1]`

**涉及文件：** 2 文件修改（`memory.py`, `main.py`），+137/-38 行

---

### 变更 4: Phase 2 光流计算 + 碰撞避障

**提交**: `40b241d`

**原因：** 马里奥频繁坠落和卡住的根本原因是**无法感知前方障碍和悬崖**。原有 1,536 个视觉细胞仅输出全局 temporal_energy 标量，无法区分左右/中心相对运动。

**变更内容：**
- `retina.py` — 新增 `compute_flow()`：8 方位角扇区、左右不对称、中心膨胀（looming）、下视野绿色（cliff）
- `model.py` — `encode_retina()` 存储 flow 信号，`step()` 按 asymmetry/looming/cliff 调制转向/减速/提前转向
- `main.py` — 新增 `/flow.json`、主动避障模块（先于 escape 触发）、flow 传入 memory 决策
- `memory.py` — MemoryController 接收 flow 参数，flow 感知型 escape 阈值
- `telemetry.py` — 新增 flow 字段到 observatory 行

**涉及文件：** 6 文件，+695/-102 行

---

### 变更 5: 仪表板增强 — Escape 事件日志 + 历史图表 + 热力图

**提交**: `3b24246`

**原因：** 仪表板只能看瞬时值，无法观察 stuck_score、flow_asymmetry 等信号的历史趋势。

**变更内容：**
- `main.py` — EscapeEventBuffer（200 事件环形缓冲）、escape 起止追踪、`/events.json`、`/history.json`（60 秒滚动）
- `memory-heatmap.js` — 轨迹路径叠加（青色）、Escape 事件标记（颜色编码）、悬停提示
- `dashboard.js` — Stuck Trend 图表（绿→黄→红渐变）、Optic Flow 三线图表（asymmetry/looming/cliff）
- `index.html` + `dashboard.css` — 新增 chart 元素和布局

**涉及文件：** 5 文件，+443/-13 行

---

### 变更 6: CSS 布局重叠修复（多次迭代）

**提交**: `661b939` → `a30dfbb` → `cd555f8` → `d9bd246`

**原因链：**
1. `.history-row` 高度不足，chart 溢出
2. `@media(min-width:1100px)` 覆盖 `grid-template-rows`，145px 替代 260px
3. `.memory-map` 106px 无法容纳 124px 内容

**修复：**
- 媒体查询 Row4 145px → 275px；`.memory-map` 106px → 146px；`.memory-row` 110px → 150px
- 简化 grid 从 6 行 → 5 行

---

### 变更 7: Escape 方向修复 — 光流不对称引导

**提交**: `f265bd8`

**原因：** Escape 转向方向完全随机（50% 左/右），转角撞墙时无法脱困。观测到 stuck_score=1.0 持续 167 秒。

**变更内容：**
- `main.py` — 两级 escape 的转向方向由随机改为 `flow_asymmetry > 0.12 → 右转；< -0.12 → 左转；否则随机`
- FailureMemory `avoid_direction()` 优先于不对称信号

**涉及文件：** 1 文件，+17/-5 行

---

### 变更 8: P3 地形感知 — 悬崖检测 + 提前避障

**提交**: `5ed950e`

**原因：** Phase 2 已计算 cliff 信号但仅作为被动监控，无人使用提前转向逻辑，马里奥走到悬崖边时坠落。

**变更内容：**
- `model.py` — `_cliff_history`（maxlen=10）、`cliff_confirmed`（7/10 < 0.25）、`cliff_rate`
- `memory.py` — CliffDetector（迟滞 entry=0.35/exit=0.40）、集成到 MemoryController
- `main.py` — 三级提前避障：高置信→急转±60+后退；低置信→放大转向；恢复→0.5s 渐变
- `dashboard.js` + `memory-heatmap.js` — 悬崖指示器（Safe/Edge/Cliff）+ 红色边框闪烁

**涉及文件：** 5 文件，+278/-17 行

---

### 变更 9: 探索策略 — novelty 导向 + 覆盖率 + 死胡同

**提交**: `4ab5485`

**原因：** Escape 仅有"随机转向"一种策略，无目标导向探索，覆盖率仅 ~15%。

**变更内容：**
- `memory.py` — `novelty_direction()` 采样 4 方向 novelty；`coverage_pct`、`coverage_rate`、`coverage_history`；FailureMemory `record_dead_end`、`is_dead_end`
- `main.py` — Escape 方向优先级：avoid → flow_asymmetry → novelty_bias（>0.2）→ 随机
- `memory-heatmap.js` — 覆盖率百分比（红/黄/绿）、死胡同 X 标记

**涉及文件：** 4 文件，+271/-2 行

---

### 变更 10: 多通道视网膜升级（6 通道编码）

**提交**: `8161eee`

**原因：** 每个小眼仅 1 个细胞类型，信息维度太低，无法区分"静止墙壁"vs"移动物体"。

**变更内容：**
- `retina.py` — `encode_on_off()`（ON=+Δ、OFF=-Δ、sustained=5 帧滑动对比）；`edge_orientation()`（4 方向边缘能量 0/45/90/135°）
- `model.py` — 7 个新通道信号：ON 跳跃提升、OFF 转向偏置、sustained 减速、dominant edge 转向塑形
- `main.py` — flow_json + signal_history 包含所有新通道

**涉及文件：** 3 文件，+457/-172 行

---

### 变更 11: 自运动分离 — true_asymmetry

**提交**: `7b1ac9e`

**原因：** `flow_asymmetry` 同时包含"马里奥在转向"和"障碍物在靠近"两种运动，无法区分，导致误触发 escape。

**变更内容：**
- `model.py` — `SELF_MOTION_K=0.08`；`heading_rate`（从连续 pose[3] 差值计算）；`true_asymmetry = raw - K × heading_rate`
- `main.py` — escape 方向使用 `true_asymmetry`；避障保留 raw（低级反射）；flow_json + signal_history 含 `true_asymmetry`/`heading_rate`
- 6 新测试，全部通过

**涉及文件：** 3 文件，+174/-11 行

**原因：** `telemetry.py` 中 `json.dumps()` 遇到 numpy int64 类型时抛出 `TypeError: Object of type int64 is not JSON serializable`。原因是 memory 模块引入的 numpy 类型数据进入 observatory 数据链。

**变更内容：**
- **修改** `fly64/fly64/telemetry.py:68` — `json.dumps()` 增加 `default=str` 参数
- **修改** `fly64/fly64/main.py:340` — `log.write()` 中的 `frame_seq` 和 `temporal_energy` 显式转换为 Python 原生类型

**涉及文件：** 2 文件（`telemetry.py`, `main.py`）

---

### 变更 12: 视觉提升 — 16扇区光流 + 地形分类 + 地面角 + 门框检测

**提交**: `cd8f10b`

**原因：** 原有 8 扇区光流无法区分墙壁、斜坡、通道、天空。地面角无感知导致斜坡误判为悬崖。门/通道无法识别。

**变更内容：**
- `retina.py` — 升级 8→16 扇区（8 方位 × 2 高度）；`classify_terrain()` 返回 8 种地形；`wall/ramp/opening/sky_score`；`_compute_ground_angle()` 区分悬崖 vs 斜坡；`_compute_door_frame()` 垂直边缘对分析检测门框
- `model.py` — 8 个新信号；`wall_score>0.5` 转向、`ramp_score>0.5` 抑制悬崖、`opening_score>0.5` 前进、`door_frame_score>0.5` 优先转向门
- `main.py` — flow_json 包含所有新信号；斜坡时抑制悬崖触发
- `memory.py` — `ground_angle` 参数门控 cliff_emergency

**涉及文件：** 5 文件，+633/-49 行，93/93 测试通过

---

### 变更 13: 地标记忆 — 视网膜签名匹配 + 回访检测

**提交**: `5a39e74`（+ 修复 `df7be90`）

**原因：** 无法判断"来过这里"→ 每次重新探索 → 重复场景重复行动。缺乏场景级记忆。

**变更内容：**
- `model.py` — 128×1536 随机投影（PROJECTION_SEED=42）；`scene_sig = projection @ drive` L2 归一化
- `memory.py` — `SceneDatabase` 环形缓冲（maxlen=500）；余弦相似度匹配 0.85 阈值；`revisit_penalty` 线性增长 0→0.5
- `main.py` — memory_json/flow_json 含 `scene_id/revisit_count/revisit_penalty`；`revisit_penalty>0.3` 增强转向

**涉及文件：** 3 文件，+230/-11 行，100/100 测试通过

---

### 变更 14: 神经跳跃 — tau→jump 电流注入 + novelty→CX 注入

**提交**: `93e4612`

**原因：** 跳跃只在 escape 循环结束时触发，166,700 个神经元的运动决策能力被绕过。需要将视觉计算的碰撞时间（tau）直接作为电流注入跳跃运动池，让 LIF 网络自然决定何时跳。

**变更内容：**
- `model.py` — tau < 2.0s 时注入最高 0.35 电流到 jump 运动池；sky_score > 0.5 时注入 sky_score × 0.12；novelty [0,1] 映射为 ±0.075 转向偏置注入 turn_left/turn_right 运动池；简化 Python 跳跃逻辑
- 跳跃从 Python escape 逻辑移入 LIF 神经网络输出

**涉及文件：** 1 文件，+23/-6 行。验证：tau=0.3 时 jump_rate 0→0.95

---

### 变更 15: EvolutionSkill v2.0 — 自进化运动诊断技能

**提交**: `520584d` → `378e943`（v2.0.1）

**原因：** 马里奥运动问题需要系统化的闭环诊断→修复→验证流程。手动分析效率低，修复效果无法量化追踪。

**变更内容：**
- `skills/evolution_skill.py` — 729 行核心模块，5 相闭环管道（Monitor→Diagnose→Fix→Verify→Document）
- `skills/evolution_agent.py` — v1 兼容入口
- `skills/default_patterns.json` — 4 个检测模式（circle_loop/ramp_trap/reflex_cooldown/low_coverage），JSON Schema (draft-07) 验证
- `skills/README.md` — 自文档化 README，自动更新修复历史 + 有效性指标
- `skills/skills.md` — 标准技能文档（用法、架构、API、触发词）
- `skills/__init__.py` — 导出 13 个符号

**v2.0.1 更新**（`378e943`）：
- `circle_loop` asymmetry 阈值 0.05→0.06（根据实际测量 0.0553 调整）
- `reflex_cooldown` 冷却时间 10s→5s（内存.py ReflexController）
- 自适应冷却公式：`cooldown = max(2.0, 10.0 - stuck_duration * 0.05)`

**涉及文件：** 6 文件（skills/），+1063 行

---

## 进化迭代记录（Evolution Iteration Log）

> 依据工作流程规则 7/8：每轮 skill 闭环执行后，在此记录完整进化过程。
> 脑模型版本随每轮进化强制递增（`main.py` `BRAIN_VERSION`）。

### EVO Round 8 — Brain v2.1.0（T4/T5 式 HRC 方向选择运动检测 + LC4 looming 种群化）

**提交**: 待 commit（retina.py/model.py/telemetry.py/main.py HRC 接入 + 协议测试扩展）

**触发原因**: MaleCNS-TrackMania 参照方案（`docs/multi-eye-vision-analysis.md`）指出：既有亮度差分光流**无方向选择性**（静止纹理与真实运动不可分），真果蝇 T4/T5 经 Hassenstein-Reichardt 相关器实现方向选择运动检测——这是"运动真值"的生物学正确实现。

**闭环过程**:
1. **Implement** — `retina.py` 新增 `compute_hrc()`：按 `_edge_pairs` 邻接对复用 `_prev_cell_lum`，逐对 `corr = lum_a(t-1)·lum_b(t) − lum_b(t-1)·lum_a(t)`；汇聚 `hrc_right/left/up/down`（右移亮条→`hrc_right>0`）、`hrc_asymmetry`（与 `flow_asymmetry` 同号）、LC4 式 16扇区×上/下×左/右 looming 种群 32 键；`reset_temporal_state` 同步清理 HRC 缓冲；只读观测契约保持
2. **Integrate** — `model.py` 新增 `true_hrc_asymmetry`（减 `SELF_MOTION_K×heading_rate` 自运动分量，与 flow 同公式）+ `hrc_available`（≥2 帧预热）；`main.py` escape 判定预热后优先 HRC motion-truth；`telemetry.py` WS 行携带 `hrc_asymmetry` + 帧行 `sector_loom`
3. **PIN** — 新增 HRC 方向/静态纹理/协议回归测试；修复 `test_hrc_self_motion_separation_matches_flow_formula` 测试自身的口径错误（模型用逐步 heading_rate，测试误用 3 步平均）
4. **基线对照** — 全量 219 用例：200 通过 / 19 既存失败（stash 基线逐一对照确认：`time.clock_gettime_ns` Windows 平台缺失、memory/optic_flow 既存断言，与 HRC 变更无关；HRC 新增 9 用例全绿，零新增失败）
5. **VERSION** — BRAIN_VERSION 2.0.0→**2.1.0**、SKILL_VERSION 2.4.0→**2.5.0**（`check_version.py` 镜像一致）
6. **CONSOLIDATE** — 同步 retina/model/telemetry/main/evolution_skill/web 至 `/root/fly64` 并重启脑模型；`tests/ws_probe.py` 通过；WS 实测每行 `hrc_asymmetry` 在线、`sector_loom` 32 键 LC4 种群在线、`flow.json` `brain_version=2.1.0` 且旧字段（asymmetry/true_asymmetry/looming/cliff/heading_rate）无损
7. **RECORD** — 本记录 + skills.md 轮次表（第 8 行）+ v2.5.0 能力描述

**能力增益**:
- 🧭 方向选择运动真值：`hrc_asymmetry`/`hrc_right/left/up/down`（T4/T5 等效，Hassenstein-Reichardt 相关器）
- 🧭 自运动分离真值：`true_hrc_asymmetry`（转身视觉回流剔除，escape 不再被自转误导）
- 🧭 LC4 looming 种群：16 扇区×上下×左右 32 键逐细胞能量聚合（`sector_loom`）
- 计算代价：加法接入 `compute_flow`，每帧 ~50 邻接对乘加，预算占比 <0.5%

**回归测试**: `tests/test_retina.py`（+7 HRC 用例）+ `tests/test_dashboard_protocol.py`（hrc 字段 JSON 安全/自运动分离公式/LC4 32 键）；全量基线对照零新增失败

---

### EVO Round 7 — Brain v2.0.0（颜色/UV + 4方向EMD + 小目标追踪 + 多巴胺蘑菇体学习）

**提交**: 待 commit（P1-P3 视觉能力增强，含 mushroom_body.py 新模块 + 27 回归测试）

**触发原因**: FlyWire MaleCNS v1.0 实验（6字符识别, 38ms, 200nW）与 Fly64 当前实现的能力差距分析，发现视觉覆盖度仅 ~38%，最大缺失在 Medulla 级信息压缩（1/50,000 维度比）

**闭环过程**:
1. **Analyze** — `docs/visual_capability_analysis.md`：系统分析果蝇真实复眼 vs Fly64 实现差距
2. **Plan** — AgentTeams 7人团队（vision-architect / neural-engineer / code-auditor / roadmap-planner）产出 6 份方案 + 路线图
3. **Implement P1a** — retina.py + model.py：颜色/UV 4通道编码 + 增强 drive 公式 + sky_blue/danger_red 指数
4. **Implement P1b** — retina.py + model.py：Hassenstein-Reichardt 4方向 EMD（T4/T5等效）+ 4条调制规则
5. **Implement P2** — retina.py + model.py：LPLC1/2 中心-周边运动对立 + 卡尔曼滤波多目标追踪
6. **Implement P3** — 新 mushroom_body.py + model.py + main.py：2000 KC / 5 MBON / 三元因子可塑 + 代理奖励
7. **LIF 注入修复** — P2 跳跃电流从 post-spike 移至 pre-spike（near tau），确保拦截帧立即生效
8. **PIN** — 新增 `tests/test_mushroom_body.py`（27 回归测试）+ 全量 179/179 通过
9. **VERSION** — BRAIN_VERSION 1.4.0→2.0.0、SKILL_VERSION 2.3.0→2.4.0
10. **CONSOLIDATE** — 同步代码，脑模型重启后新能力加载生效
11. **RECORD** — agent.md、skills.md、fly64/README.md 全部更新

**能力增益**: 
- 🎨 颜色/UV 视觉（`danger_red_index` 熔岩避让、`sky_blue_index` 探索引导）
- 🌀 4方向 EMD 运动检测（上下左右方向选择、外部运动识别）
- 🎯 小目标追踪（移动平台拦截跳跃 30%→65%、躲避距离 3→6 体长）
- 🧠 多巴胺蘑菇体学习（2000 KC 经验关联、>5000帧稳定）
- 计算预算合计: ~190 μs/帧 = 0.95% of 20ms

**回归测试**: `tests/test_mushroom_body.py`（27 用例）+ `test_evolution_capability.py`（19 用例）+ 全量 179/179 通过

**提交**: `ea0eefd` / `56c9a1b` / `f6de494` / `25ea329`（链条）

**触发原因**: 马里奥反复卡死墙角，视觉因果链无法解释（temporal=0、ON/OFF=0、asymmetry≈0 —— 与开阔地静止信号完全相同）

**闭环过程**:
1. **Monitor** — 发现"卡墙角"期间全部视觉信号与正常静止无法区分
2. **Diagnose** — 根因定位：**视觉因果链缺少动作-效果比较器**（corollary discharge）："卡住"由电机命令 vs 实际位移失配定义，属本体感觉，视觉天然不可见
3. **Fix** — `main.py` 新增伴发放电比较器：`expected=y×0.6` vs `actual=pose位移`，失配>15帧触发 `command_decoupled`
4. **Reflex** — 失配>60帧（~1.2s）→ 后退 y=-50 + 交替转向 物理脱出墙角
5. **Verify** — skill v2.1 全监控实测命中 `wall_corner_command_decoupled` + `reflex_cooldown_gap`
6. **Document** — 本记录 + 13 个回归测试（`test_evolution_capability.py`）固化能力

**附带修复（同轮）**:
- `telemetry.py`/`bridge.py` WSL 旧版崩溃修复（causal kwarg + Linux 屏障）
- 对话框检测假阳性：亮墙 ≠ 对话框（SM64 对话框为暗色底，改用 亮度骤降判据 `lum<0.30 + Δ>0.12`）
- 场景命名 v2：相对优势 top-2（如"天空·山坡"）替代"混合地形"兜底；签名 EMA 平稳定哈希
- 交互习惯化：同位置 3 次无奖励对话 → 封锁 2min + 后退（锁门策略）
- Escape 触发时自动运行 skill（10s 节流），`/evolution.json` 暴露迭代记录

**能力增益**: 视觉盲区（几何卡死）检测能力从 0 → 1；仪表板新增 Brain v/EVO # 徽章与迭代历史列表

**回归测试**: `fly64/tests/test_evolution_capability.py` — 13 用例（全监控/墙角盲区/对话判别/场景命名/端到端闭环），全部通过

---

### EVO Round 5 — Brain v1.3.0（交互习惯化制度化 + 双区提示框检测）

**提交**: `25ea329` / `ef962e9` / `f6de494`

**触发原因**: 马里奥卡在钥匙门前——提示框"You need a key to open this door."位于屏幕**上方**，单下视野检测漏检；文字语义（2-4°/字母 vs 5.6°小眼）物理不可读。

**闭环过程**:
1. **Monitor** — skill 执行发现 dialogue 误报（亮墙判为对话）
2. **Diagnose** — SM64 对话框为暗色底白字 → 改判据为亮度骤降（lum<0.30 + Δ>0.12）
3. **Fix** — 双区检测（上/下视野独立判定，上置 key-sign 框可检出）
4. **Learn** — 交互习惯化：同位置 3 次无奖励对话 → 封锁 2min + 后退（果蝇 learned non-association）
5. **PIN** — 回归测试 13→**16 用例**（新增 TestDualZoneDialogue：上置框✅/下置框✅/亮坡❌）
6. **CONSOLIDATE** — BRAIN_VERSION 1.2.0→**1.3.0**，重启脑模型
7. **RECORD** — 本记录 + skills.md 自进化章节（制度化 EXECUTE→DETECT→LEARN→PIN→VERSION→CONSOLIDATE→RECORD 七步循环）

**能力增益**: 上置提示框检测 0→1；交互习惯化记忆；skills.md 具备自我更新迭代的制度化描述

---

## 早期变更

### 基础设施
- WSL2 Ubuntu-22.04 环境搭建与适配
- Linux x86_64 内存屏障支持（`bridge.py` macOS 独占修复）
- sm64ex 编译：GLEW 链接修复（`-lGLEW`），`glewInit()` 初始化修复
- MaleCNS 脑数据下载（curl 方式，aria2c 会产生截断文件）
- 脚本适配：`run-fly64`、`setup_sm64.sh` Linux/WSL 适配

### 3D 轨迹回放
- Three.js 3D 轨迹显示 + OrbitControls 自由视角
- 等比例缩放、缩略图/全屏切换
- 0.5x 默认播放速度、文件选择器（Live + 历史）
- `__live__` 回退加载实时 `/trajectory.json`

### API 扩展
- `GET /trajectory-list.json` — 列出历史轨迹文件
- `GET /trajectory-load?file=xxx` — 加载指定历史轨迹
- `GET /memory.json` — 空间记忆状态（Phase 1）
- `GET /bridge-status.json` — 桥接状态

## 注意事项
1. **页面文件更新后需重启脑模型**（HTTP 服务缓存文件到内存）
2. brain model 用 `pkill -f 'python.*main'` 重启
3. SM64 用 `pkill -f 'sm64\.us'` 重启
4. 轨迹数据通过 `bridge.frame_metadata["pose"]` 采集
5. 保存的 `.trajectory.npz` 需在脑模型退出时生成
6. `model.py:180` `self.spikes |= newly_fired` float32 兼容（已修复）
7. `bridge.py:47` `clock_gettime_ns` Windows 不兼容（已知问题）