# what_i_see 语义通道协议设计

> 2026-09-15 · 语义接口工程师（semantic-engineer）
> 基于 `fly64/plugin/llm_consult.py`（t21）现有实现 + 分层原则重构。
> 目标：让教官层 LLM 看懂游戏画面语义，同时保持"语义不下沉"分界。

## 一、现状诊断

| 方面 | 当前状态（t21, v2.13.2） | 缺口 |
|------|------------------------|------|
| 帧传递 | GLM 收到 384×256 SM64 游戏帧（PNG base64） | 帧是游戏渲染，**不是果蝇视角**——教练看到的是人眼画面，而非复眼逐小眼采样 |
| 文字读屏 | `what_i_see` 字段：prompt 要求列出可见文字 → parse → 落盘 | 仅文本列表，无空间语义（文字在哪？对应什么对象？） |
| 场景上下文 | `context` 字典含 `scene_name/stuck_duration/anomaly_state/health_score` | 缺失飞行视觉系统自身处理结果（地形分类、光流状态、开口方向、显著目标）——教练不知道果蝇"自己看到了啥" |
| 历史关联 | 单帧孤立咨询，无跨帧场景演变 | 教练不知道"这一帧和前一次咨询比有什么变化" |
| 语义下沉 | 教练输出经 `sanitize_strategy` 降维为调制参数 | ✅ 正确，但教练需要更多果蝇侧视觉信息才能给出好建议 |

### 核心问题

**教练在替一个盲蝇导航**——他看到了游戏画面，但不知道果蝇视觉系统从中提取了什么信息。教练说的指令（"向左转"）可能果蝇根本看不到左侧的开口（因为复眼采样不到），导致指令无效。

## 二、设计原则（重申与补充）

```
┌─────────────────────────────────────────────────┐
│                 教官层（LLM）                      │
│  看到的：游戏帧 + 果蝇视觉结构化上下文               │
│  输出：降维调制信号（方向偏置/阈值/反射参数）          │
├─────────────────────────────────────────────────┤
│  ←──  what_i_see 结构化协议 ──→                   │
├─────────────────────────────────────────────────┤
│  果蝇自身能力群（LIF + 反射 + 记忆 + 光流）         │
│  看到的：1,536 小眼亮度/颜色/运动 -> 地形/光流/目标  │
│  输出：动作电流到运动命令池 + flow.json              │
└─────────────────────────────────────────────────┘
```

### 语义不下沉
- 教练的语义理解（"门需要钥匙"）**绝不**以语义向量注入 LIF 网络
- 教练输出始终是数值型调制信号（`turn_bias`, `stuck_threshold_s`, `climb_period`）
- `what_i_see` 字段只存在于教练层消费链（consult→advice），不入 `active_strategy.json` 供脑热加载

### 视界对齐
- 教练看到的帧是游戏渲染，果蝇看到的帧是复眼采样+光流处理
- 协议提供"果蝇视界摘要"（结构化数据），让教练理解果蝇实际感知到了什么

### 跨帧记忆
- 同场景多次求助时，教练应看到演变（上次建议 → 效果 → 当前快照）

## 三、what_i_see 结构化协议

### 3.1 协议包结构（每次 consult）

```python
# 添加到 consult request payload
what_i_see_context = {
    "frame_ts": 12345.67,           # 帧时间戳
    
    # ── Tier A: 果蝇视觉系统处理摘要 ──
    "fly_vision": {
        "terrain": "indoor",         # 地形分类（mixed/open_flat/cliff/corridor/
                                     #   wall_ahead/dense/indoor/water/forest_edge/
                                     #   door_frame/sky）
        "terrain_scores": {          # 逐地形置信度
            "wall_score": 0.32,
            "ramp_score": 0.12,
            "sky_score": 0.05,
            "enclosure_score": 0.85, # 室内围闭度
            "ground_angle": 0.02,    # 地面倾角
            "door_frame_score": 0.41 # 门框检测
        },
        "optic_flow": {
            "asymmetry": -0.48,      # 左右不对称（负=左转）
            "true_asymmetry": -0.08, # heading_rate 补偿后
            "looming": 0.12,         # 径向膨胀（碰撞威胁）
            "cliff": 0.57,           # 下视野绿/悬崖信号
            "tau": 2.34,             # 碰撞时间（秒）
            "hrc_asymmetry": -0.05,  # HRC 真实运动不对称
            "local_motion": 0.23,    # 局部运动能量
        },
        "targets": {
            "count": 1,              # 小目标追踪数
            "tracks": [              # 追踪目标列表
                {"azimuth": -15, "elevation": 5, "age": 1.2}
            ] if target_count > 0 else []
        },
        "scene_context": {
            "scene_hash": "f3f9aa",  # 场景签名
            "revisit_count": 3,      # 回访次数
            "scene_match": 0.87,     # 匹配置信度
        }
    },
    
    # ── Tier B: 运动神经元状态 ──
    "motor_state": {
        "decision_source": "steering",  # 当前主导决策源
        "forward_rate": 12.5,           # 前向池放电率（Hz）
        "turn_bias": -0.3,              # 当前转向偏置
        "jump_rate": 0.5,              # 跳跃池放电率（Hz）
        "gate_forward": True,           # 前向门控是否打开
        "gate_jump": False,             # 跳跃门控是否打开
    },
    
    # ── Tier C: 记忆与导航状态 ──
    "navigation": {
        "heading": 45.0,                # 当前航向（度）
        "heading_rate": 5.2,            # 转向角速度
        "stuck_duration": 62.0,         # 卡住时长
        "anomaly_state": "micro_loop",  # 异常类别
        "disp_60s": 12.5,              # 60秒位移
        "coverage_pct": 34.2,          # 空间覆盖率
    },
    
    # ── Tier D: 蘑菇体学习状态（Tier D, staged）──
    "plasticity": {
        "mb_mbon_forward": 0.95,       # MBON 前向价值（0~1）
        "mb_dopamine": -0.12,          # 当前多巴胺
        "dopamine_gain_avg": 1.25,     # 平均通路增益
        "learning_progress": 0.34,     # 学习进度
    } if plasticity_available else None,
    
    # ── Tier E: 语义场景标签（增强）──
    "scene_tags": [
        "室内场景",
        "有门框",
        "围闭度高(0.85)",
        "重复回访(第3次)"
    ],
}
```

### 3.2 包与已有数据的映射

| 协议字段 | 数据源端点 | 已有？ |
|----------|-----------|--------|
| `fly_vision.terrain` | `/flow.json` `terrain` | ✅ |
| `fly_vision.terrain_scores.*` | `/flow.json` `wall_score/ramp_score/sky_score/enclosure_score/ground_angle/door_frame_score` | ✅ |
| `fly_vision.optic_flow.*` | `/flow.json` `asymmetry/looming/cliff/tau/hrc_asymmetry/local_motion` | ✅ |
| `fly_vision.targets` | `/flow.json` `target_count` + `model.target_tracks` | ⚠️ count 有，轨迹需补充 |
| `fly_vision.scene_context` | `/memory.json` `scene_hash/scene_match/revisit_count/scene_label` | ✅ |
| `motor_state.*` | `/flow.json` + `/memory.json` 多字段 | ⚠️ 分散需聚合 |
| `navigation.*` | `/memory.json` `stuck_duration/anomaly_state/disp_60s/coverage_pct` | ✅ |
| `plasticity.*` | `/flow.json` `mb_mbon_forward/mb_dopamine/dopamine_gain_avg/learning_progress` | ✅ |
| `scene_tags` | 本协议新增 | ❌ 需标注生成 |

### 3.3 数据装配层

在 `runner.py` 的 `capture_frame()` 增强为 `capture_consult_data()`，既抓帧也聚合场景上下文：

```
增强前（t21）:
  frame_b64 = self.capture_frame()
  → 返回 None 或 PNG base64

增强后:
  context_enriched, frame_b64 = self.capture_consult_data(context)
  → 返回 (what_i_see_context_dict, frame_b64)
```

## 四、场景标签增强（Scene Tag Enhancement）

### 4.1 标签生成规则

基于果蝇视觉系统现有输出自动生成语义标签：

| 触发条件 | 标签 | 数据来源 |
|----------|------|---------|
| `enclosure_score > 0.65` | `"室内场景"` | flow.json |
| `sky_score > 0.5` | `"开阔天空"` | flow.json |
| `door_frame_score > 0.3` | `"有门框"` | flow.json |
| `cliff_detected or cliff > 0.4` | `"悬崖警告"` | flow.json |
| `looming > 0.15` | `"碰撞威胁"` | flow.json |
| `tau < 1.5 and tau > 0` | `"接近碰撞(τ<1.5s)"` | flow.json |
| `terrain == 'corridor'` | `"走廊狭窄"` | flow.json |
| `terrain == 'water'` | `"水域前方"` | flow.json |
| `terrain == 'indoor'` | `"封闭室内"` | flow.json |
| `target_count > 0` | `"检测到移动目标"` | flow.json |
| `revisit_count >= 3` | `"重复回访(第N次)"` | memory.json |
| `stuck_duration > 60` | `"长时间卡住"` | memory.json |
| `anomaly_state != 'idle'` | `"异常态:{类别}"` | memory.json |
| `dialogue_active` | `"对话框激活"` | flow.json |

### 4.2 标签在 consult 请求中的使用

标签既作为独立字段 `scene_tags` 传入，也注入 **prompt 增强段**：

```
=== 果蝇视觉分析 ===
场景标签: [室内场景, 有门框, 围闭度高(0.85), 重复回访(第3次)]
果蝇感知地形: indoor（围闭度0.85）
果蝇感知运动: 左右不对称 -0.48（左转偏置），碰撞 looming 0.12
卡住状态: micro_loop 异常持续62秒
蘑菇体学习: forward MBON 0.95（已饱和）
```

### 4.3 标签持久化

场景标签不单独写入 `active_strategy.json`（语义不下沉），但持久化在 `coach_advice.json` 的历史记录中以供回溯：

```json
{
  "advice": "...",
  "context": {...},
  "strategy": {...},
  "scene_tags": ["室内场景", "有门框", "重复回访(第3次)"],
  "ts": 12345.67
}
```

## 五、教官层提示词优化

### 5.1 增强提示词体系

当前单一 PROMPT_TEMPLATE → 三阶段提示词架构：

```
PHASE 1: 果蝇感知对齐
「你看到的游戏画面是人类的渲染视角。下面是果蝇实际感知的结构化摘要——"
  它看不到你看到的文字和细节，只能通过下面这些数值"感受"世界。」

PHASE 2: 场景分析 + 文字读屏
（保留原 what_i_see 读屏指令）

PHASE 3: 决策推理
「基于：①游戏画面中的可见元素 ②果蝇实际感知到的视觉数据
  ③上次咨询至今的变化，给出降维策略参数。」
```

### 5.2 带场景上下文的增强 Prompt

```python
ENHANCED_PROMPT_TEMPLATE = (
    "你是 SM64 果蝇脑控制系统的教练。\n\n"
    "=== 游戏画面 ===\n"
    "你上方看到的是当前 SM64 游戏帧。注意这是人类视角的画面，"
    "果蝇的复眼只能看到 1,536 个暗淡的光点。\n\n"
    "=== 果蝇实际感知摘要 ===\n"
    "{scene_context_summary}\n\n"
    "=== 任务 ===\n"
    "1. **读取屏幕文字**：列出所有可见文字（对话框、UI、金币数、"
    "生命值、星星数、菜单项），写在 what_i_see 字段。\n"
    "2. **场景元素**（你在画面中看到的）：门/坡/敌人/金币/平台/水体……\n"
    "3. **果蝇感知盲区**：果蝇的视觉系统能感知到上面摘要中的数据，"
    "但它看不到你看到的文字和语义。请判断：当前问题属于"
    "   - 果蝇自身能力群可解决（光流/反射/记忆）→ 调优参数即可\n"
    "   - 需要语义理解（门需要钥匙等）→ 必须通过教官指令通道\n"
    "4. **行动建议**：给出转向方向、速度、是否跳跃、目标位置。\n\n"
    "=== 输出格式 ===\n"
    "只回复一个 JSON 对象，格式：\n"
    '{"scene_elements": ["..."], "what_i_see": ["屏幕文字1", "屏幕文字2"], '
    '"problem": "...", "action": "...", '
    '"semantic_level": "innate|coach", '  # 问题归属判断
    '"advice": "给马里奥的一句中文建议", '
    '"strategy": {"fallen_recovery": {"mode": "mirror|directional_climb", '
    '"climb_period": 2.0, "persist_seconds": 2.0}, '
    '"exploration": {"bold_explore_stuck_s": 60.0, "turn_bias": 0}, '
    '"escape": {"stuck_threshold_s": 30.0, "reverse_seconds": 0.5}}}\n'
    '策略参数语义卡（严格遵守单位与方向，不要反向调参）:\n'
    '- exploration.bold_explore_stuck_s: 秒。异常持续该秒数后触发突围，'
    '越小越快突围（建议 20-120）。\n'
    '- exploration.turn_bias: 0-1 转向强度（占最大转向电流的比例），'
    '越大转向越猛（建议 0.3-1.0；不要填 69 这类角度值）。\n'
    '- escape.stuck_threshold_s: 秒。持续卡住该秒数后强制逃逸，'
    '越小越快逃逸（建议 1-60）。\n'
)
```

### 5.3 `semantic_level` 归因

新增 `semantic_level` 解析字段区分两类问题：

| `semantic_level` | 含义 | 教练应对 |
|------------------|------|---------|
| `"innate"` | 属于果蝇自身能力群的问题 | 调优反射/参数即可，无需语义指令 |
| `"coach"` | 需要语义理解或任务规划 | 需要教官指令通道或引导性策略 |

## 六、内存检索增强（跨帧语义上下文）

### 6.1 咨询历史摘要

每次咨询时，从 `coach_advice.json` 取最近 N 条历史并摘要：

```python
consult_history_summary = {
    "last_advice": "向左轉前往開口方向",
    "last_strategy": {"exploration": {"turn_bias": 0.6}},
    "last_terrain": "indoor",
    "improvement_since_last": True,  # 上次建议后 stuck_duration 是否改善
    "same_scene_consults": 2,        # 同一场景已咨询次数
}
```

### 6.2 跨帧差异比较

```python
frame_delta = {
    "changed_scene": False,          # 场景是否切换
    "terrain_changed": False,        # 地形是否变化
    "stuck_trend": "worsening",      # 卡住趋势（improving/worsening/stable）
    "displacement_60s": 12.5,        # 60秒位移
    "new_targets_detected": False,   # 是否有新目标
}
```

## 七、实现变更清单

### 7.1 新增文件

| 文件 | 内容 |
|------|------|
| `fly64/docs/what_i_see_protocol.md` | 本协议文档 |
| `fly64/plugin/scene_context.py` | 场景上下文聚合器：从 `/flow.json` + `/memory.json` 提取结构化上下文 + 生成场景标签 |

### 7.2 修改文件

| 文件 | 变更 |
|------|------|
| `fly64/plugin/llm_consult.py` | 枚举 `ENHANCED_PROMPT_TEMPLATE`；`build_consult_request` 接收并注入 scene_context；`parse_response` 新增 `semantic_level` 字段 |
| `fly64/plugin/runner.py` | `capture_frame()` → `capture_consult_data()` 双重取帧+场景上下文；`check_help_needed()` 返回增加 scene_context_id |
| `fly64/plugin/strategy_writer.py` | `write_advice()`/`write_strategy()` 接收并持久化 `scene_tags`；`coach_advice.json` 增加 `scene_tags` 历史字段 |

### 7.3 不变更

| 不涉及 | 原因 |
|--------|------|
| `fly64/fly64/main.py` | 上下文数据已全量在 `/flow.json` 和 `/memory.json` 中提供 |
| `fly64/fly64/retina.py` | 视网膜处理不变，只新增数据消费端 |
| `fly64/fly64/model.py` | 脑模型不感知语义 |
| `skills/active_strategy.json` 的热加载消费 | `what_i_see` 和 `scene_tags` 不入该文件（语义不下沉） |

## 八、测试验证

### 8.1 新增测试

```python
class TestSceneContextProtocol:
    def test_scene_context_assembly(self):     # 验证上下文聚合正确
    def test_scene_tags_generation(self):      # 验证场景标签基于阈值生成
    def test_prompt_embeds_context(self):      # 验证增强 prompt 含场景摘要
    def test_semantic_level_parsed(self):      # 验证 semantic_level 解析
    def test_frame_delta_tracking(self):       # 验证跨帧差异比较
    def test_semantic_level_defaults(self):    # 验证缺失时降级
```

### 8.2 回归保证

- 所有现有 `TestWhatISee` 测试必须继续通过（前向兼容）
- `PROMPT_TEMPLATE` 可废弃使用旧 prompt（通过默认值控制）
- `capture_consult_data` 返回兼容签名 `(context, frame_b64)` vs 原 `capture_frame` 返回 `frame_b64`

## 九、协议边界重申

| 属于 what_i_see 协议 | 不属于 |
|----------------------|--------|
| ✅ 果蝇侧结构化视觉摘要 | ❌ 语义向量注入 LIF |
| ✅ 场景标签（从现有数据推导） | ❌ OCR 结果注入脑模型 |
| ✅ 跨帧上下文演变 | ❌ 完全替代果蝇视觉处理 |
| ✅ semantic_level 归因 | ❌ 教练直接接管摇杆 |
| ✅ 提示词优化（场景上下文嵌入） | ❌ 改变 active_strategy 热加载契约 |

---

*版本：v1.0 · 对应 Brain 2.14.x · 语义接口工程师产出*