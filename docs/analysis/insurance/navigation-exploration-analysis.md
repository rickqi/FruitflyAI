# 寻路导航能力缺陷与改进方案分析

> **版本**: Brain v2.13.3 + P0-P4 + 关键问题修复  
> **评估日期**: 2026-09-07

---

## 1. 当前探索机制分析

### 现有导航体系

```
探索驱动链:
SpatialMemoryMap.novelty(位置) → CX-3 goal_vector(方向) → CX转向偏置 → 运动池
       ↑                              ↑
  网格新颖性                  多源向量竞争:
  50×50 grid                  novelty方向+覆盖空隙+反失败+锚点返回
  回访惩罚+排斥               goal_vectors列表加权合成
```

### 核心参数

| 参数 | 值 | 物理含义 |
|------|:--:|---------|
| grid_cells | 50 | 每边50格 |
| cell_size | 200u | 每格200游戏单位 |
| recency_decay | 0.9995 | 每次衰减系数(每10帧) |
| loop_window | 500帧(10s) | 回访检测窗口 |
| revisit_penalty | 0→0.5 (3→8次) | 回访惩罚 |
| coverage_gap_radius | 6格(1200u) | 未访问格搜索半径 |

---

## 2. 导航缺陷诊断

### 缺陷1: 新颖性衰减过慢

```python
# memory.py L261-262
recency_decay = 0.9995   # ← 每10帧乘一次
```

**衰减曲线**:
```
时间    衰减后值    含义
10s     0.951      有新鲜感
30s     0.861      仍有新鲜感 ← 导致反复回访已去过的区域
60s     0.741      仍然不低
120s    0.549      衰减过半
300s    0.223      终于低了
```

**后果**: 模型在30秒内不会对刚去过的地方失去兴趣, 导致在"有趣但已探索"的区域反复兜圈, 而不是向前推进。

### 缺陷2: 前向探索无远距引导

```python
# memory.py L306-325: coverage_gap_vector(radius=6)
# 仅搜索半径6格(1200u)内的未访问格
# 如果局部全部探索过 → 无探索方向 → CX无所适从
```

**后果**: 当局部探索完成(6格半径内全部visited), coverage_gap_vector返回None → CX-3失去"去探索"的驱动力 → 模型在新方向上无系统性引导。

### 缺陷3: 回访惩罚不够强

```python
# memory.py L408-419  
revisit_penalty: 0→0.5 (3→8次)  ← 需要回访8次才达到最大惩罚
```

**后果**: 在"好路径"和"回头路"之间没有有效的区分——模型在同一个走廊来回3-4次才开始被惩罚。

### 缺陷4: CX转向缺乏探索惯性

当前CX转向是逐帧计算的——每帧根据当前novelty/flow/光流计算转向偏置。没有"选择方向→坚持5秒→换方向"的探索策略。

### 缺陷5: 场景数据库回访惩罚不是空间性的

SceneDatabase的revisit_count是所有场景的汇总, 不区分"回到出生点"(好的)和"在死胡同来回走"(坏的)。

---

## 3. 改进方案

### 方案A: 前向探索惯性 (推荐, 最高收益)

在CX导航中增加"探索方向提交"——类似于逃逸方向提交但持续时间更长。

```python
# model.py FlyModel — exploration direction commitment
# 在探索模式下保持前进方向5-10秒
if not self.escape_mode and self._explore_commit_timer > 0:
    self._explore_commit_timer -= 1
    # 向已选方向注入偏置
    self.v[self.turn_right] += self._explore_bias * 0.10
    self.v[self.turn_left] -= self._explore_bias * 0.10
```

**预期收益**: 减少局部徘徊, 增加长途移动

### 方案B: 前沿探索 (Frontier Exploration)

```
概念: 找到"已探索"和"未探索"区域的边界(前沿),
      生成从当前位置指向最近前沿的吸引向量。
```

```python
# memory.py SpatialMemoryMap — frontier_direction()
def frontier_direction(self, x, z, search_radius=15):
    """找到距当前位置最近的前沿方向"""
    cxk = self._key(x, 0, z)
    best_dist = float('inf')
    best_dir = None
    for dx in range(-search_radius, search_radius + 1):
        for dz in range(-search_radius, search_radius + 1):
            k = (cxk[0] + dx, cxk[1], cxk[2] + dz)
            if k not in self._cells:
                # 未访问格
                frontier = k
                # 检查它的邻居中是否有已访问格
                has_visited = False
                for ndx in (-1, 0, 1):
                    for ndz in (-1, 0, 1):
                        nk = (frontier[0] + ndx, frontier[1], frontier[2] + ndz)
                        if nk in self._cells:
                            has_visited = True
                            break
                if has_visited:
                    dist = math.hypot(dx, dz)
                    if dist < best_dist:
                        best_dist = dist
                        best_dir = (dx / dist, dz / dist)
    return best_dir
```

**预期收益**: 当局部探索完成后, 引导模型前往更远的未探索区域

### 方案C: 加速新颖性衰减

```python
# memory.py — 双时间尺度新颖性
# 快通道: 用于探索决策
# 慢通道: 用于长期记忆
self.fast_decay = 0.995  # 30s衰减到~0.5
self.slow_decay = 0.9995 # 保持当前(300s衰减到~0.2)
```

**预期收益**: 减少30秒内的回访冲动, 推动持续前向移动

### 方案D: 更强的回访惩罚

```python
# memory.py
revisit_penalty: 0→0.7 (2→5次)  # 更早、更强制止回访
```

---

## 4. 综合方案

| 优先级 | 方案 | 预期收益 | 改动量 | 风险 |
|:------:|:----:|:--------:|:------:|:----:|
| **P1** | 探索方向惯性(方案A) | 减少徘徊+30% | ~15行 | 🟢 |
| **P1** | 前沿探索(方案B) | 新场景发现+50% | ~25行 | 🟢 |
| **P2** | 加速新颖性衰减(方案C) | 减少回访+20% | ~5行 | 🟢 |
| **P2** | 加强回访惩罚(方案D) | 抑制绕圈+15% | ~3行 | 🟢 |

### 推荐执行

```
P1: 探索惯性 + 前沿探索 → 立即可改善探索路径
P2: 新颖性衰减 + 回访惩罚 → 参数调优
```