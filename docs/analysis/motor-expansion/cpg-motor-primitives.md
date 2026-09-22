# R-C/R-D VNC CPG 运动原语层设计与触发映射

依据：`main.py` 六级控制级联、`memory.py`（StuckDetector/FailureMemory/CliffDetector 信号）、`model.py`（pose 输入、escape_jump_drive）、t4 §7 文献（MaleCNS VNC CPG / subsumption 分层）

> **状态**: 🟢 已实现 (Implemented)  
> 此文档中的设计方案已编码实现并部署。实现详情参见对应代码文件与测试。
>

## 1. 设计原则（与文献及现有架构对齐）

- **脑发门控、CPG 出时序**：LIF 脑模型只输出"启动某原语"的低维门控信号（同 CX 只注入转向偏置、不写指令的分层原则一致）；节律/时序由确定性 CPG 振荡器完成——对应文献中 VNC CPG 独立于脑生成节律行走。
- **不侵入反射级联**：CPG 原语作为新的 `decision_source="cpg_primitive"` 级联层，插在 `escape`（优先级4）与 `jump`（5）之间，即优先级 4.5：神经跳跃与纯转向仍可被更高优先级抢占。
- **动作状态机前置（R-D）**：由桥接已有 `pose[4]`（x/y/z + yaw）+ z 变化率推断物理状态，防止非法组合（空中禁 Z 长跳、地面禁落地砸）。

## 2. 新模块 `fly64/motor_primitives.py`（预计 ~400 行）

```python
class MarioState(Enum):        # R-D 状态机，由 pose 推断
    GROUNDED / AIRBORNE / SWIMMING / WALL / SLIDING

class Primitive(Enum):
    LONG_JUMP      # 跑动中: [Z 1帧] → 50ms后 [A 4帧 + stick_y=70 保持600ms]
    BACKFLIP       # 静止:   [Z 2帧] → 80ms后 [A 3帧]，期间 stick_y=0
    GROUND_POUND   # 空中:   [Z 2帧]，落地前不重复
    DIVE           # 空中+前向: [B 2帧 + stick_y=50 保持400ms]
    PUNCH          # 地面静止: [B 1帧] ×3 连段间隔 250ms（拳/踢/抓）
    SWIM_STROKE    # 水中: A 以 400ms 周期连打（CPG 振荡器，无脑输入自续）
    CRAWL          # 蹲(Z 持续) + stick_y=30 慢速

class CPGController:
    def update(self, now, mario_state, gates) -> PrimitivePhase | None:
        """振荡器相位推进；gates 为脑/记忆层提供的启动门控 dict。"""
```

每个原语是一个**相位脚本**（phase → 输出 x/y/a/b/z + 剩余时长），由 CPG 按帧推进，期间脑的其他动作输出被该级联层覆盖。

## 3. 触发映射（复用已有信号，零新增感知）

| 原语 | 门控条件（已有信号） | 状态前置 |
|---|---|---|
| LONG_JUMP | `stuck_duration>3s` 且 `scene_label` 含 ramp/slope，或 `cliff_tangent_bias` 活跃且需大位移脱困 | GROUNDED 且 `filtered_y>40`（跑动） |
| BACKFLIP | `anomaly_state=="fallen"`（复用 escape_jump_drive）或身后死端（FailureMemory 失败向量与朝向夹角>120°） | GROUNDED 且静止 |
| GROUND_POUND | AIRBORNE 且下方 `ground_angle<0.3` 判定平台（防误砸入渊） | AIRBORNE |
| DIVE | AIRBORNE 且小目标追踪锁定 gold spot（P2 信号）或跳距不足（tau 分析） | AIRBORNE |
| PUNCH | 对话框习惯化后的可交互目标（`door_frame_score`/交互模式） | GROUNDED 静止 |
| SWIM_STROKE | `pose.y` 持续低于入场水平面 + 浮力特征 | SWIMMING（自续直至离水） |
| CRAWL | 低净空场景（上/前/下三面贴脸的 vision 扇区特征） | GROUNDED |

## 4. 级联接入点（`main.py`）

```
priority 4   escape
priority 4.5 cpg_primitive   ← 新增；占先期间写 decision_source="cpg_primitive:<name>"
priority 5   jump
```

- `CPhaseGate`：原语激活期间吞掉 model.step 的 control 输出（保留池率统计），仅透传遥测；
- 与 `forced_bold_explore` 互斥（同为突破通道，避免双重突破）；
- EVO 验证窗口复用：原语结束后 60s 位移进 `/memory.json` 的新键 `primitive_disp`，供 EvolutionSkill 量化 fix 效果。

## 5. 测试与验证

```bash
python -m pytest tests/test_motor_primitives.py -q   # 新增：相位脚本时序、状态机转移、门控条件、非法组合拒绝
python -m pytest tests/test_evolution_capability.py -q  # primitive_disp 遥测契约
# 实机验收：ramp_trap 场景 LONG_JUMP 产生非零位移（对照 README 记录的 5 次 0u 事件）
```

## 6. 工作量与风险

| 项 | 估计 |
|---|---|
| motor_primitives.py + 状态机 | 2d |
| 级联接入 + 遥测 | 1d |
| 测试 | 1d |
| 风险 | pose 推断 SWIMMING 需水面标定（可先由"落水音效帧差"退化判定）；原语期间卡死需 2s 超时熔断回退反射 |
