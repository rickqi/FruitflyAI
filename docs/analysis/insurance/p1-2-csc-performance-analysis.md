# P1-2 分析报告: CSC事件驱动传播可行性

> **分析对象**: `fly64/fly64/model.py step()` L1349-1380  
> **版本**: Brain v2.13.3 (+P0+P1-1修复)

---

## 1. 当前实现

```python
# model.py L1349:
current = np.asarray(self.w[:, np.flatnonzero(self.spikes)].sum(axis=1)).ravel()
```

`self.w` 在 L400 已转换为 CSC (Compressed Sparse Column) 格式：
```python
self.w = self.w.tocsc()  # L400
```

CSC 格式的列索引是 O(nnz_in_selected_columns)，**已经是事件驱动传播**——仅遍历放电神经元的传出边。

## 2. 实际瓶颈分析

### 单步操作耗时分解（估计，166,700神经元）

| 操作 | 行号 | 估计耗时 | 占比 |
|------|:----:|:--------:|:----:|
| CSC列索引求和 | L1349 | 3-5ms | 35% |
| 通路增益 | L1354-1359 | 0.1ms | 1% |
| 突触缓冲 | L1367-1369 | 0.5ms | 4% |
| **OU噪声(166,700神经元)** | L1375-1378 | **3-5ms** | **35%** |
| 膜电位更新(166,700) | L1381-1382 | 0.5ms | 4% |
| 视觉驱动 | L1383-1385 | 0.3ms | 2% |
| 预尖峰电流注入(15项) | L1388-1530 | 1-2ms | 15% |
| 放电检测+历史记录 | L1545-1555 | 0.5ms | 4% |
| **总计** | | **~9-14ms** | 100% |

### 结论
CSC传播本身已经是事件驱动。真正瓶颈是 **OU噪声生成**(166,700个独立正态采样) + **大量预尖峰电流注入**(15个独立Python分支)。

## 3. 两种优化方案对比

| 方案 | 预期加速 | 改动量 | 风险 | 效果 |
|:----:|:--------:|:------:|:----:|:----:|
| **A: OU噪声稀疏化** (仅活跃神经元) | +20-30% | 5行 | 低 | 约3-5ms→2ms |
| **B: 合并预尖峰注入** (用查表聚合) | +10-15% | ~20行 | 中 | 减少分支开销 |

## 4. 推荐方案

### 方案A: OU噪声稀疏化

当前:
```python
self.ou_global_state += (
    self.ou_global_theta * (-self.ou_global_state) * dt
    + self.ou_global_sigma * np.sqrt(dt)
    * self.rng.normal(size=self.n).astype(np.float32)
)
```

优化: 仅对活跃神经元(放电率>0)更新OU状态，不活跃神经元用均值回归逼近。

```python
# 仅更新最近活跃过的神经元 (有放电或膜电位>0.5)
active_mask = (self.spikes > 0) | (self.v > 0.5 * self.threshold)
n_active = int(active_mask.sum())
if n_active < self.n * 0.3:  # 仅<30%活跃时加速
    self.ou_global_state[active_mask] += (
        self.ou_global_theta * (-self.ou_global_state[active_mask]) * dt
        + self.ou_global_sigma * np.sqrt(dt)
        * self.rng.normal(size=n_active).astype(np.float32)
    )
    # 不活跃神经元缓慢回归0
    self.ou_global_state[~active_mask] *= 0.999
else:
    # 全量更新 (活跃神经元多时无优化空间)
    ...
```

### 预期效果
- 典型场景(10-30%活跃): 50Hz→65-70Hz(+30-40%)
- 高活跃场景: 维持50Hz