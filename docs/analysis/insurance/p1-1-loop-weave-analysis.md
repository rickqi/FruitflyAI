# P1-1 分析报告: micro_loop_weave + circle_loop 根因分析

> **分析对象**: `fly64/fly64/model.py` + `fly64/fly64/memory.py` + `skills/default_patterns.json`  
> **版本**: Brain v2.13.3 (+ P0修复)

---

## 1. micro_loop_weave — 原地编织

### 根因

`breakout_drive()` 使用 `min(nl, nr)` 取两个疲劳电路中的较小值：

```python
# model.py L355-365
def breakout_drive(self) -> float:
    nl = min(1.0, self.left / max(self.saturation, 1e-6))
    nr = min(1.0, self.right / max(self.saturation, 1e-6))
    return self.breakout_gain * min(nl, nr)  # ← 取小值
```

在编织状态下，两个电路同时疲劳，`nl ≈ nr ≈ 0.6-0.8`，但 `min(nl, nr) ≈ 0.6-0.8`，乘以 `breakout_gain=0.25` → 仅获得 **0.15-0.20 前向电流**。

同时 `counter_drive()` 也在向两个电路注入反向电流，形成竞争。

### 数字推导

```
编织状态: left=0.3, right=0.3 (fatigue), saturation=0.5
→ nl=0.6, nr=0.6
→ breakout_drive = 0.25 × min(0.6, 0.6) = 0.15
→ forward 池得到 +0.15 V
→ LIF 阈值 1.0, 膜电位 ~0.8-1.2 (振荡边界)
→ 0.15 增量不足以保证突破阈值
```

反之，若 `breakout_gain=0.35`:
```
breakout_drive = 0.35 × 0.6 = 0.21 → +40% 增量 → 更易突破
```

### 修复

```python
# model.py L335: breakout_gain 0.25→0.35 (增加40%突破电流)
```

同时在 `main.py` 的escape段增加micro_loop直接前向驱动:

```python
# main.py escape段: micro_loop时增加forward驱动
if memory_ctrl.anomaly_state == "micro_loop" and memory_ctrl.escape_behavior:
    model.v[model.forward] += 0.08  # 额外前向电流
```

---

## 2. circle_loop — 无障碍转圈

### 根因

Pattern 条件 (default_patterns.json L9-22):
```
wall_score < 0.1 (无障碍物)
asymmetry < 0.06 (对称运动)
stuck > 120s
ground_angle > 0.3 (不是悬崖)
```

矛盾: `terrain=cliff` 但 `ground_angle>0.3`。

代码位置 memory.py L1726-1731:
```python
is_actual_cliff = (ground_angle < 0.3)
cliff_emergency = (self._cliff_state["cliff_detected"]
                   and temporal_energy > 0.005
                   and is_actual_cliff)
```

CliffDetector 在 memory.py L23-115 中 `entering_threshold=0.35`, 当 `lower_field_green<0.35` 时触发。问题可能出在 terrain classifier (model.py L548-561) 中 `wall_score/ramp_score/opening_score` 等派生指标。

**根本原因**: `cliff_confirmed` 标志可能在 `ground_angle>0.3` 时仍为 true（因为 lower_field_green < entering_threshold），而 escape 逻辑检查 `cliff_detected` 而非 `is_actual_cliff`。

### 修复

在 main.py 的 escape 决策中增加 ground_angle 门控:

```python
# memory.py L1728-1731: 增加 escape_trigger 的 ground_angle 过滤
# 当 ground_angle>0.3 时，即使 cliff_detected 也不触发 cliff escape
if cliff_emergency and ground_angle < 0.3:
    # 只有真正的悬崖才触发
    ...
```