# P0-2 分析报告: MBON forward 饱和 — 稳态缩放守卫失效

> **分析对象**: `fly64/fly64/mushroom_body.py` + `fly64/fly64/gain_modulation.py`  
> **版本**: Brain v2.13.3  
> **报告人**: captain (代 mbon-fixer)

---

## 1. 根因定位

### 核心问题: 稳态缩放守卫(×0.9)被正多巴胺增益调制持续抵消

```
encode() → tanh(weights @ kc) = 1.0 (saturated)
          → scale_down: weights × 0.9 (reduces)
          → update_weights: weights += lr × dopamine × eligibility (increases back)
          → 下一帧: 再次饱和
```

### 代码行级追踪

#### A. 饱和检测 (mushroom_body.py L207-220)

```python
# L211: 检测条件 — 检查 MBON 的 tanh 输出
sat = np.abs(self.mbon_outputs) >= 0.98    # ← 问题1: 条件过于严格

# L212-213: 计数器 — 连续饱和帧累计
self._saturation_frames = np.where(sat, self._saturation_frames + 1, 0)

# L214-220: 触发 — 当连续>=50帧饱和
for j in np.flatnonzero(self._saturation_frames >= 50):  # 50 frames = 1s at 50Hz
    active = self.kc_activity > 0
    if active.any():
        self.weights[active, j] *= 0.9   # 将活跃KC→MBON权重×0.9
    self._saturation_frames[j] = 0
    self.saturation_events += 1
```

**问题1**: 条件 `abs(mbon_outputs) >= 0.98` 要求在 **tanh 输出层**检测饱和。但 `tanh(x)` 在 `x >= 2.5` 时即达到 0.987，在 `x >= 3.0` 时达到 0.995。权重只需要高到 `raw_mbon ≈ 2.5` 即可触发饱和检测，但权重范围是 [-1, 1]，所以需要 `sum(active_weights) ≈ 2.5` 才能饱和。

#### B. 权重更新 (mushroom_body.py L293-345)

```python
# L326: 三因子学习规则
delta = self.lr * self.dopamine * self.eligibility  # lr=0.001
# L330: 应用到活跃突触
self.weights[active_mask] += delta[active_mask]
```

**问题2**: `学习率 lr=0.001` × `正多巴胺(≈0.3-0.5)` × `资格迹(≈0.8)` = `delta ≈ 0.00024-0.0004/帧`。看起来很小，但:
- 如果有 100 个活跃 KC，每个贡献 ≈0.0003 → ~0.03/帧的总增长
- 缩放因子 0.9 将权重降低 10% → 如果权重均值为 0.5，降低 0.05
- 一次缩放后的恢复时间: 0.05 / 0.03 ≈ 1.67帧 ≈ 33ms

**结论**: 缩放守卫的效果在1-2帧内被正多巴胺完全抵消！

#### C. 多巴胺路径 (gain_modulation.py + mushroom_body.py)

```
main.py 中 dopg.set_dopamine(reward_signal, pathway_activity)
  → gain_modulation.py: Δgain = η × R × E × (1-gain)  [正多巴胺时]
  → 所有5通路增益保持 ≥ 1.5 (DEFAULT_GAINS中所有通路初始=1.5)
  → model.py step(): v += current × gain[pathway]  (LIF电流被放大)
  → 更多神经元放电 → 更强的MBON驱动 → 更容易饱和
```

## 2. 稳态平衡点推导

### 关键参数

| 参数 | 当前值 | 位置 |
|------|:------:|------|
| lr (学习率) | 0.001 | mushroom_body.py L21 |
| 正多巴胺 (forward) | ~0.3-0.5 | R18调整0.50→0.30后 |
| 资格迹 decay | 0.8 | mushroom_body.py L23 |
| 缩放因子 | 0.9 | mushroom_body.py L133 |
| 饱和阈值 | 0.98 | mushroom_body.py L211 |
| 饱和帧数要求 | 50 | mushroom_body.py L132 |

### 平衡点计算

令 W = 平均权重值, K = 活跃KC数, D = 正多巴胺值

```
缩放减少: ΔW_scale = -0.1 × W          (×0.9 缩放)
学习增加: ΔW_learn = K × lr × D × E    (每次更新)

平衡条件: ΔW_scale + ΔW_learn = 0
→ -0.1 × W + K × 0.001 × D × 0.8 = 0
→ W = K × 0.001 × D × 0.8 / 0.1
→ W = K × 0.008 × D
```

当 D=0.3: W = 100 × 0.008 × 0.3 = 0.24 (可控)
**但当 D=0.5**: W = 100 × 0.008 × 0.5 = **0.40** (更接近饱和)
当 D=0.8(极端): W = 100 × 0.008 × 0.8 = **0.64** (持续饱和)

**关键发现**: 正多巴胺值 D 是饱和与否的决定因素。R18 将探索奖励 0.50→0.30 理论上下调了40%，但 `raw_mbon = kc_activity @ weights` 中活跃KC数量 K 可能在 50-150 之间变化，导致实际平衡点漂移。

## 3. 计数器可靠性检查

```python
# L211-213
sat = np.abs(self.mbon_outputs) >= 0.98
self._saturation_frames = np.where(sat, self._saturation_frames + 1, 0)
```

此计数器逻辑正确——`np.where(sat, +1, 0)` 在饱和帧递增，不饱和帧归零。但存在边界条件:

**问题**: 如果 MBON 在 49 帧时饱和(计数器=49)，下一帧偶然降至 0.97(不饱和)，计数器归零。需要重新累计 50 帧才能触发。在噪声环境下，这意味着实际需要远多于 50 帧(游戏帧率波动+视觉变化会导致频繁重置)。

## 4. 改造方案对比

| 方案 | 改动量 | 预期效果 | 副作用 |
|:----:|:------:|---------|--------|
| **A: 降低饱和阈值** 0.98→0.95 | 1行 | 更早检测饱和, 减少噪声重置 | 可能误判正常高输出 |
| **B: 降低帧数要求** 50→30 | 1行 | 更快触发缩放 | 短期波动也可能触发 |
| **C: 加强缩放因子** 0.9→0.8 | 1行 | 一次缩放更大幅度降低 | 可能过度抑制 |
| **D: 组合方案** 0.95+30帧+0.85缩放 | 3行 | 综合效果最优 | 需验证平衡点 |
| **E: 减少正多巴胺** 探索奖励0.30→0.20 | 1行 | 降低学习增量(D从0.3→0.2) | 可能降低探索意愿 |

### 推荐方案 D+E 组合

```python
# mushroom_body.py
self.saturation_frames_threshold = 30      # 50→30
self.saturation_scale_factor = 0.85        # 0.9→0.85
```

同时 `gain_modulation.py` 或 `main.py` 中探索奖励进一步降低:
```python
# main.py 中探索多巴胺信号
explore_reward = 0.20  # 0.30→0.20 (R18已从0.50→0.30)
```

## 5. 总结

| 问题 | 结论 |
|------|------|
| 根因 | 缩放守卫(×0.9)被正多巴胺学习(ΔW≈0.0003/帧/突触)在~2帧内抵消 |
| 计数器 | 逻辑正确, 但 0.98 阈值+噪声导致实际触发间隔远长于理论 50 帧 |
| 推荐方案 | 降低饱和帧数 50→30 + 加强缩放 0.9→0.85 + 探索奖励 0.30→0.20 |
| 验证方法 | test_mbon_saturation.py + test_dan_shaping.py 回归 |