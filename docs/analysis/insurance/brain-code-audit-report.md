# 脑模型代码审计与能力评估报告

> **对象**: Fly64 Brain Model (v2.13.3) — `D:\codes\flygym\fly64`  
> **审计日期**: 2026-09-07  
> **覆盖**: README声明能力 vs 实际代码实现 / 已知缺陷 / EVO进化记录分析 / 功能盲区

---

## 目录

1. [README声明能力核查](#1-readme声明能力核查)
2. [已知持续性问题](#2-已知持续性问题)
3. [功能性缺陷详细清单](#3-功能性缺陷详细清单)
4. [代码质量发现](#4-代码质量发现)
5. [监控与可观测性缺口](#5-监控与可观测性缺口)
6. [建议优先级](#6-建议优先级)

---

## 1. README声明能力核查

### 1.1 声称已实现 vs 实际代码状态

| # | README声称能力 | 代码位置 | 实现状态 | 发现 |
|:-:|---------------|---------|:--------:|------|
| 1 | **166,700神经元LIF推理** | `model.py:680-710, 1520-1550` | ✅ 基本实现 | 演示模式仅4096神经元(demo_load)，真实连接组需`--cache`参数加载MaleCNS数据 |
| 2 | **25.6M突触CSC传播** | `model.py __init__` w sparse.csr_matrix | ✅ 实现 | CSC格式正确，但演示模式随机生成65536边，非真实25.6M |
| 3 | **270°球面复眼** | `retina.py SphericalRetina.sample()` | ✅ 实现 | 1536像素6面体采样，270°水平视场已验证 |
| 4 | **ON/OFF/颜色/EMD/HRC** | `model.py:500-540` retina.py | ✅ 实现 | 6通道+4方向+HRC全部实现 |
| 5 | **蘑菇体2000KC+5MBON** | `mushroom_body.py` | ✅ 实现 | P3-4实现完成，三因子Hebbian+资格迹+稳态缩放 |
| 6 | **CX 16柱环形吸引子** | `central_complex.py` | ⚠️ R20新实现 | v2.13.0重写: CX-1自运动积分+天空校正+CX-3多源向量竞争 |
| 7 | **6态异常检测** | `memory.py MotionStateDetector` | ⚠️ 部分实现 | 3信号投票(vision/frame/rate)，微环/斜坡/振荡/墙卡/坠落/对峙中部分为综合派生而非独立检测器 |
| 8 | **4反射电路** | `memory.py ReflexController` | ✅ 实现 | stuck_ramp/oscillating/wall_stuck/micro_loop + 自适应冷却+激进模式 |
| 9 | **自进化闭环(23轮)** | `skills/evolution_skill.py` | ⚠️ 存在缺陷 | 见§2.1 — fix_catalog 18项全部reverted/pending，0项effective |
| 10 | **LLM教官层** | `plugin/runner.py + llm_consult.py` | ⚠️ 部分验证 | 双传输机制实现，但精度~70%，t20才把阈值从120s→60s |
| 11 | **因果链可视化** | `main.py:1093-1103` telemetry.py | ✅ 实现 | decision_source 6级+4泳道时间轴+因果链卡 |
| 12 | **mmap seqlock桥接** | `bridge.py SharedBridge` | ✅ 实现 | 80bytes/帧, 8μs延迟, 撕裂保护 |
| 13 | **空间记忆50×50网格** | `memory.py SpatialMemoryMap` | ✅ 实现 | 200unit/格, visited+recency+loop+revisit惩罚 |
| 14 | **场景识别14关卡** | `scene_recognition.py` | ✅ 实现 | P05/P50/P95分布匹配, online calibration |
| 15 | **小目标追踪** | `model.py TargetTracker` | ✅ 实现 | 卡尔曼+匈牙利匹配, 但匈牙利匹配实现有bug(见§3.5) |

### 1.2 声称但存在显著差距的能力

| 能力 | README声称 | 实际代码差异 | 严重度 |
|------|-----------|-------------|:------:|
| 23轮自进化验证 | "23轮已验证" | fix_catalog: 0 effective / 10 ineffective / 6 pending / 2 reverted | 🔴 **高** |
| 测试452项 | "当前452项，pytest.ini" | 测试文件存在，但无法在Windows运行(依赖WSL) | 🟡 中 |
| 70+关键指标 | "11大类70+项" | 实际仪表板暴露~50+项，部分指标在特定异常态才填充 | 🟡 中 |
| 多巴胺学习闭环 | "12+种奖励/惩罚信号" | 实际奖励来源较单一(位移多巴胺+场景变化+探索)，少于12种 | 🟡 中 |

---

## 2. 已知持续性问题

### 2.1 EVO自进化系统 — 核心缺陷

**严重度: 🔴 高 — 自进化闭环实际不闭环**

fix_catalog.json 统计(v2.0):
```
total_fixes: 18
effective_count: 0    ← 没有一个修复被判定有效
ineffective_count: 10  ← 10个被判定无效
pending_count: 6      ← 6个待验证
reverted: 2           ← 2个被回滚
```

**根因分析**:
1. **验证窗口跨重启失效**: 所有fix的 `post_fix_stuck: null, post_fix_coverage: null` — 修复记录后脑模型重启, 验证窗口丢失
2. **stale baseline污染**: 18项中有5项标注 `"stale baseline: dead pre-restart session"` — 基线数据来自不同会话
3. **AUTO-0002/AUTO-0003待验证**: 最新两轮自诊断提出的 `forward MBON饱和` 和 `below_ground_stuck阈值` 问题尚未有人处理

**evolution_log.jsonl** 显示(8971行)持续高频率检出：
- `circle_loop` (高) — 持续出现在几乎所有轮次
- `micro_loop_weave` (高) — 持续出现在几乎所有轮次
- `fallen_recovery_stuck` (高) — 间歇出现
- `reflex_cooldown_gap` (中) — 间歇出现

> **结论**: 自进化系统虽然在**检测**(Diagnose)环节有效，但在**修复→验证**环节存在架构性缺陷——验证窗口无法跨脑模型重启保持，导致所有自动修复最终都被标记为 `reverted` 或 `ineffective`。

### 2.2 行为模式 — 3大未解决异常态

| 异常态 | 占比 | 典型时长 | README承认 | 当前缓解 |
|--------|:----:|:--------:|:----------:|---------|
| **micro_loop 原地编织** | 最高频 | 30s~973s | ✅ | breakout_drive(0.25增益) + 反射混合, 但验证无效 |
| **circle_loop 无障碍转圈** | 第二高频 | 155s+ | ✅ | ground_angle门控, 但仍有误触发 |
| **锁门语义死循环** | 特定场景 | 101s+ | ✅ 已知局限 | LLM教练60s阈值求助, 但无文字理解能力 |

### 2.3 已知未修复缺陷 (从evolution_log提取)

| 缺陷ID | 问题 | 检出次数 | 严重度 | 备注 |
|--------|------|:--------:|:------:|------|
| below_ground_stuck | 坠落阈值Y<-100过宽(实际Y<50即异常) | 持续 | 🟡中 | AUTO-0003已记录, 待修复 |
| mbon_saturation | MBON forward列饱和贴顶, 稳态缩放失效 | 持续 | 🔴高 | AUTO-0002已记录, 待排查 |
| reflex_cooldown_gap | 冷却期内escape无效 | 每轮 | 🟡中 | 自适应冷却已实现但验证无效 |
| fallen_recovery_stuck | 跌落恢复循环无效 | 间歇 | 🟡中 | mirror turn+延长burst已实现未验证 |

---

## 3. 功能性缺陷详细清单

### 3.1 视觉管道 (retina.py + model.py encode_retina)

| 缺陷 | 位置 | 影响 | 严重度 |
|------|------|------|:------:|
| **颜色通道仅1/3视场有效** | `retina.py` cubemap采样 — 仅前/左/右三面(水平180°)有颜色, 上/下/后三面无颜色信号 | 颜色视觉覆盖不完整, 后方来袭敌人无法通过颜色检测 | 🟡 中 |
| **EMD在低帧率退化** | `model.py:emd_on_*` 依赖帧间差异, 50Hz下有效, 但游戏实际帧率波动25-60Hz | 帧率不稳时运动检测不可靠 | 🟡 中 |
| **UV通道近似简化** | `uv_sal = max(B - 0.5*(R+G), 0)` — 用蓝色通道近似UV | 非真实UV感光, 区分度有限 | 🟢 低 |

### 3.2 控制级联 (main.py 控制循环)

| 缺陷 | 位置 | 影响 | 严重度 |
|------|------|------|:------:|
| **CSC稀疏矩阵每次step全量传播** | `model.py step()` ~L700: `current = self.w[:, fired].sum(axis=1)` | 25.6M边每次全扫, 性能瓶颈, dt=20ms下每step约8-15ms | 🟡 中 |
| **多重Python分支覆盖LIF决策** | `main.py:1000-1199` — 反射/逃逸/对话等分支在spike后改写control | P1虽删除了11处A类旁路, 但仍有reflex/dialogue改写路径 | 🟡 中 |
| **bold_turn_drive与CX steering竞争** | `model.py bold_turn_drive(0.12)` vs `cx_bias(0.12)` | 两个独立转向信号同时注入, 无优先级仲裁 | 🟡 中 |

### 3.3 蘑菇体学习 (mushroom_body.py)

| 缺陷 | 位置 | 影响 | 严重度 |
|------|------|------|:------:|
| **forward MBON持续饱和** | `mushroom_body.py` MBON输出tanh≈1.0, 稳态缩放未触发 | 学习停滞, 行为同质化 | 🔴 **高** |
| **资格迹衰减时间常数固定** | `E(t)=E(t-1)*0.95 + KC*MBON` — 单时间常数 | 无法适配不同时间尺度的关联(短期碰撞 vs 长期探索) | 🟡 中 |
| **DAN信号来源单一** | 主要来自位移多巴胺(report_movement) | 缺乏场景价值/任务完成等高层奖励信号 | 🟡 中 |

### 3.4 空间记忆与导航 (memory.py + central_complex.py)

| 缺陷 | 位置 | 影响 | 严重度 |
|------|------|------|:------:|
| **50×50网格仅200u/格** | `memory.py SpatialMemoryMap` — 总覆盖10000×10000u | SM64世界约8000×8000u, 网格刚好够但无法区分垂直维度(多层关卡) | 🟡 中 |
| **CX-2锚点路径积分精度漂移** | `central_complex.py _self_motion_update` — heading_rate累加 | 无闭环校正(不含视觉/触觉重定位), 长距离积分漂移~5%/min | 🔴 **高** |
| **FailureMemory仅记录最近失败** | `memory.py FailureMemory — 半径2.5格内最近向量` | 有限短期记忆, 不保存路径/地形上下文 | 🟡 中 |

### 3.5 TargetTracker匈牙利匹配实现缺陷

```python
# model.py L222-236 — 匈牙利匹配后更新逻辑存在索引混淆
# assigned_tracks 和 assigned_dets 是 Set, 但更新时用 list index 匹配
# 注释提到"Find the detection matched to this track"但逻辑混乱：
for i in assigned_tracks:
    # ... 下面试图在 assigned_dets 中反查匹配, 用 all() 条件过滤
    # 这段代码在 n_tracks != n_dets 时可能产生错误匹配
```

**影响**: 小目标追踪在目标数≠轨迹数时关联错误, 导致平台跳跃时机误判

**严重度**: 🟡 中 — 但不常触发(通常detections==tracks)

---

## 4. 代码质量发现

### 4.1 重复代码与硬编码

| 问题 | 位置 | 详情 |
|------|------|------|
| **turn_right双倍注入** | `model.py:1453-1455` | `self.v[self.turn_right] += cx_bias` 出现了两次，行号紧邻 |
| **escape_x随机初始值** | `main.py:1158-1161` | 对话回避方向用 `(step_count // 20) % 2` 取替, 但缺少对称初始化 |
| **Python→neuron梯度桥P1后残留** | `model.py:611-618` | `_last_error_gradient` 和 `_pending_python_turn` 字段, P1删除11处旁路后这些字段可能已无用 |
| **magic number散落** | `model.py:1298-1500` | 大量电流注入系数(0.12, 0.15, 0.20, 0.50等)无命名常量 |

### 4.2 异常处理缺口

| 问题 | 位置 | 详情 |
|------|------|------|
| **EVO循环try/except空pass** | `main.py:1134-1135` | `except Exception: pass` — EVO轮次异常被静默吞噬 |
| **桥读取无校验** | `bridge.py` — 无帧序列完整性校验 | seqlock协议含版本号但未在读取侧验证数据完整性 |
| **connectome数据加载无fallback** | `model.py _load_cache` — 直接assert | 13GB脑数据加载失败时直接崩溃, 无法优雅降级 |

### 4.3 性能瓶颈

| 瓶颈 | 位置 | 当前 | 建议 |
|------|------|:----:|------|
| CSC矩阵全量传播 | model.py step() | ~8-15ms/step (50Hz上限) | 使用事件驱动传播, 只更新活跃神经元 |
| 复眼采样预处理 | retina.py sample() | ~3ms/step | 可缓存cubemap静态部分的采样映射 |
| HTTP/WS双服务 | main.py HTTP+WS | ~1-2ms/step | 可分离到独立线程 |

---

## 5. 监控与可观测性缺口

### 5.1 指标覆盖盲区

| 未暴露指标 | 影响 | 备注 |
|-----------|------|------|
| **LIF膜电位分布** | 无法诊断神经元群体活动水平 | 现有仅pool rate, 无膜电位统计 |
| **突触权重变化率** | 无法监控学习速率 | mushroom_body.py有权重但未暴露 |
| **控制级联各层命中率** | 无法量化P1神经接管效果 | decision_source当前仅记录最终来源 |
| **逃逸成功率时序** | 无法追踪能力提升趋势 | escape_buffer记录单事件但无聚合趋势 |

### 5.2 自诊断缺失

| 缺口 | 详情 |
|------|------|
| **心跳监控跨进程** | 无脑模型↔DSH插件之间的双向心跳 |
| **版本一致性校验** | `BRAIN_VERSION` 在main.py硬编码, 无远程版本校验 |
| **回归测试门槛** | 452项测试无法在Windows运行(WSL only), 增加CI门槛 |

---

## 6. 建议优先级

### P0 (紧急 — 阻塞核心能力)

| 序号 | 建议 | 预计工时 | 参考 |
|:----:|------|:-------:|------|
| 1 | **修复EVO验证窗口跨重启问题** — 改为持久化基线+验证状态 | 2-3天 | fix_catalog.json §2.1 |
| 2 | **排查MBON forward饱和** — 稳态缩放守卫未触发的根因 | 1-2天 | AUTO-0002, mushroom_body.py |
| 3 | **修复below_ground_stuck阈值** — Y<-100→Y<50 | 0.5天 | AUTO-0003, memory.py:138 |

### P1 (重要 — 影响核心行为质量)

| 序号 | 建议 | 预计工时 | 参考 |
|:----:|------|:-------:|------|
| 4 | **修复TargetTracker匈牙利匹配索引混淆** | 1天 | model.py:222-236 §3.5 |
| 5 | **CX-2路径积分添加闭环校正** (视觉重定位) | 3-5天 | central_complex.py §3.4 |
| 6 | **消除model.py turn_right双倍注入** | 0.5天 | model.py:1453-1455 |
| 7 | **清理P1残留的python_correction字段** | 0.5天 | model.py:611-618 |

### P2 (改进 — 功能增强)

| 序号 | 建议 | 预计工时 |
|:----:|------|:-------:|
| 8 | 空间记忆网格扩展为3D (X×Y×Z) | 3-5天 |
| 9 | 资格迹多时间常数支持 | 2-3天 |
| 10 | EVO循环异常捕获改为logging而非空pass | 0.5天 |
| 11 | 性能优化: CSC事件驱动传播 | 5-7天 |
| 12 | Windows CI集成(WSL运行测试) | 3-5天 |

---

## 总结

| 维度 | 状态 | 评级 |
|------|:----:|:----:|
| LIF推理引擎核心 | 基本稳定运行50Hz | 🟢 **B+** |
| 复眼视觉管道 | 功能完整, 有边界限制 | 🟢 **B+** |
| 蘑菇体学习 | 学习机制实现但饱和问题未解 | 🟡 **C+** |
| CX导航(R20) | 新架构有改进但漂移未控 | 🟡 **C** |
| **自进化闭环** | **检测有效, 修复验证无效** | 🔴 **D** |
| 可观测性 | 因果链亮点, 但仍有盲区 | 🟡 **B-** |
| 代码质量 | 有残留重复/硬编码 | 🟡 **B-** |
| 异常态处理 | 3大异常持续未彻底解决 | 🔴 **D+** |