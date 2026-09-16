# 脑模型全面检视报告

> **版本**: Brain v2.13.3 (+ P0修复) · 检视日期: 2026-09-07  
> **参考**: README.md (1182行) + 核心代码模块 (model.py 1788行 + main.py 1666行 + memory.py 2087行 + evolution_skill.py 1572行)  
> **审计基线**: `docs/analysis/insurance/brain-code-audit-report.md`

---

## 1. README声明能力 vs 代码实现 — 逐项核查

| # | README声称 | 代码位置 | 状态 | 备注 |
|:-:|-----------|---------|:----:|------|
| 1 | 166,700神经元LIF推理 | model.py L680-710 | ✅ 实现 | 真实MaleCNS需`--cache`参数加载，演示模式4096神经元 |
| 2 | 25.6M突触CSC传播 | model.py w sparse.csr | ✅ 实现 | 稀疏矩阵正确，演示模式为65536随机边 |
| 3 | 270°球面复眼 | retina.py SphericalRetina | ✅ 实现 | 1536像素6面体，已验证270°水平视场 |
| 4 | ON/OFF/颜色/EMD/HRC | model.py L500-540 | ✅ 实现 | 6通道+4方向+HRC全部实现 |
| 5 | 蘑菇体2000KC+5MBON | mushroom_body.py L41-520 | ⚠️ **P0-2修复中** | 饱和帧数30→缩放0.85→探索奖励0.20已调整 |
| 6 | CX 16柱环形吸引子 | central_complex.py | ⚠️ 新架构 | R20重写：CX-1自运动积分+天空校正+CX-3多源竞争 |
| 7 | 6态异常检测 | memory.py MotionStateDetector | ⚠️ 3信号综合 | vision/frame/rate三投票，非6独立检测器 |
| 8 | 4反射电路 | memory.py ReflexController | ✅ 实现 | stuck_ramp/oscillating/wall_stuck/micro_loop + 自适应冷却 |
| 9 | **自进化闭环(23轮)** | evolution_skill.py | 🟢 **P0-1修复** | 验证窗口持久化已完成，fix_catalog恢复机制就位 |
| 10 | LLM教官层 | plugin/runner.py | ⚠️ 精度~70% | 双传输实现，阈值已60s，文字理解仍缺 |
| 11 | 因果链可视化 | main.py L1093-1103 | ✅ 实现 | 6级decision_source+4泳道+因果卡 |
| 12 | mmap seqlock桥接 | bridge.py | ✅ 实现 | 80bytes/帧，8μs延迟 |
| 13 | 空间记忆50×50 | memory.py SpatialMemoryMap | ✅ 实现 | 200unit/格，visited+recency+loop惩罚 |
| 14 | 场景识别14关卡 | scene_recognition.py | ✅ 实现 | P05/P50/P95分布匹配+online calibration |
| 15 | 小目标追踪 | model.py TargetTracker | 🟢 **P0-3修复** | 匈牙利匹配正确重构，_update_track提取 |

---

## 2. P0修复验证状态

| 修复 | 检查结果 | 文件证据 |
|------|---------|---------|
| ✅ **P0-1 EVO持久化** | `verify_state.json` 读写完整 | evolution_skill.py L786-850: save_state/resume_pending 实现 |
| ✅ **P0-2 MBON饱和** | 参数已调整 | mushroom_body.py L132-133: 阈值30, 缩放0.85 |
| ✅ **P0-2 探索奖励** | 已降低 | model.py L1158-1159: DAN_REWARD_EXPLORATION=0.20 |
| ✅ **P0-3 坠落阈值** | 已修正 | memory.py L138-139: y_min=50.0, y_max=500.0 |
| ✅ **P0-3 双注入** | 已删除 | model.py L1453: 仅一行right注入 |
| ✅ **P0-3 匈牙利匹配** | 已重写 | model.py L200-290: 直用row_idx/col_idx + _update_track |

---

## 3. 剩余已知问题（P0修复后）

### 3.1 自进化闭环 — 剩余缺陷

| 问题 | 位置 | 严重度 | 说明 |
|------|------|:------:|------|
| **fix_catalog现存pending项** | fix_catalog.json | 🟡 中 | 18项中仍有6项pending(修复前已有), P0-1仅修复了后续验证 |
| **AUTO-0002已修但未验证** | evolution_history | 🟢 低 | P0-2修复了MBON饱和，但需真机运行确认效果 |
| **circle_loop持续检出** | evolution_log.jsonl | 🟡 中 | 原地转圈pattern持续出现在每轮，需进一步排查地形门控 |

### 3.2 视觉管道 — 边界限制

| 问题 | 位置 | 严重度 | 说明 |
|------|------|:------:|------|
| **颜色仅覆盖水平180°** | retina.py cubemap | 🟢 低 | 上/下/后面无颜色通道，仅前/左/右有 |
| **EMD帧率敏感** | model.py emd_* | 🟢 低 | 50Hz下有效，游戏帧率25-60Hz波动时退化 |
| **UV通道为蓝通道近似** | model.py uv_sal | 🟢 低 | 非真实UV感光，区分度够用但有限 |

### 3.3 控制级联 — 架构性关注

| 问题 | 位置 | 严重度 | 说明 |
|------|------|:------:|------|
| **CSC全量传播性能瓶颈** | model.py step() | 🟡 中 | 25.6M边每次全扫，dt=20ms下8-15ms/step |
| **bold_turn_drive与CX竞争** | model.py L1037-1048 | 🟡 中 | 两个独立转向信号(0.12), 无优先级仲裁 |
| **dialogue改写绕过LIF** | main.py L1157-1191 | 🟡 中 | 对话状态下control被Python直接改写 |

### 3.4 蘑菇体学习 — 剩余关注

| 问题 | 位置 | 严重度 | 说明 |
|------|------|:------:|------|
| **资格迹单时间常数** | mushroom_body.py L246 | 🟢 低 | E(t)=E*0.8+hebbian, 固定decay |
| **DAN信号来源单一** | model.py DAN_* | 🟡 中 | 主要来自位移多巴胺，缺乏场景价值信号 |

### 3.5 导航与记忆 — 已知局限

| 问题 | 位置 | 严重度 | 说明 |
|------|------|:------:|------|
| **50×50网格无垂直维度** | memory.py | 🟡 中 | SM64多层关卡无法区分Y轴高度 |
| **CX-2锚点积分漂移** | central_complex.py | 🟡 中 | 无闭环视觉校正，~5%/min漂移 |
| **FailureMemory仅邻近向量** | memory.py | 🟢 低 | 半径2.5格内仅最近失败 |

---

## 4. README声明 vs 实际 — 差距汇总

| 差距 | README声称 | 实际情况 | 严重度 | P0后状态 |
|------|-----------|---------|:------:|:--------:|
| **自进化闭环** | "23轮已验证" | 修复前0 effective → P0-1修复验证持久化 | 🔴→🟢 | **已修复** |
| **MBON学习** | "稳态缩放" | 缩放被正DA抵消 → P0-2调整参数 | 🔴→🟡 | **已调参** |
| **坠落阈值** | (未明确声称) | Y<-100过宽 → P0-3修正为Y<50 | 🟡→🟢 | **已修复** |
| **452项测试** | "当前452项" | Windows无法运行(WSL only) | 🟡 | 未变更 |
| **12+种奖励信号** | "12+种奖励/惩罚" | 实际~6种DAN信号 | 🟡 | 未变更 |
| **6态异常检测** | "6态" | 3信号综合派生非6独立 | 🟡 | 未变更 |

---

## 5. 残留风险等级 (P0修复后)

```
🔴 高 (P1级) ─── 持续异常的3大pattern + 性能瓶颈
  ├── micro_loop_weave (每轮检出)
  ├── circle_loop (每轮检出)
  └── CSC全量传播性能(25.6M边每次全扫, 制约频率提升)

🟡 中 ────────── 功能限制
  ├── fix_catalog 6项pending(修复前遗留)
  ├── CX steering vs bold_turn_drive 竞争
  ├── 空间记忆无垂直维度
  ├── CX-2锚点积分漂移
  └── 测试套件WSL-only

🟢 低 ────────── 边缘限制
  ├── 颜色覆盖水平180°(够用)
  ├── UV近似(够用)
  ├── EMD帧率敏感(50Hz目标)
  └── 资格迹单时间常数
```

---

## 6. 建议优先级 (P0修复后)

| 优先级 | 建议 | 预计工时 | 预期收益 |
|:------:|------|:-------:|---------|
| **P1-1** | 排查 `micro_loop_weave` 根因（深度分析 breakout_drive 注入时机与LIF竞争时序） | 2-3天 | 消除最高频异常 |
| **P1-2** | 修复 `circle_loop` 地形门控（ground_angle 在平地的误触发） | 1-2天 | 消除第二高频异常 |
| **P1-3** | 性能优化：CSC事件驱动传播（仅传播活跃神经元） | 5-7天 | 50Hz→可能提升至100Hz |
| **P2-1** | CX-2添加视觉闭环校正（场景匹配重定位） | 3-5天 | 消除漂移，提升长距导航 |
| **P2-2** | 空间记忆扩展为3D网格 | 3-5天 | 支持多层关卡 |
| **P2-3** | bold_turn_drive与CX steering仲裁 | 1天 | 消除转向竞争 |