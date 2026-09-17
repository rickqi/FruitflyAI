# 脑模型导航探索效率深度分析与优化方案

## 现状诊断

### 问题1: 路径记录与场景不匹配

当前空间记忆只记录 `(x, y_layer, z)` 坐标和 `visit_count`，不关联场景标签。`SceneDatabase` 的128维签名匹配是全局的，不绑定到具体网格单元。

```
现状:
  _cells[(x, y, z)] = visit_count  ← 仅记录访问次数
  _scene_db.match(signature) → scene_id  ← 全局匹配，不绑定位

需要的:
  _cells[(x, y, z)] = {visit_count, scene_id, event_count}
```

### 问题2: 场景标签不是每格级

`scene_name` / `scene_label` 是当前帧的全局值，来自 `scene_recognizer`。无法查询"某个格子是什么场景"。

### 问题3: 重复探索效率极低

当前新颖性公式:
```python
novelty = (1 / (visit_count + 1)) * recency * (1 - penalty - repulsion)
```

| 访问次数 | 新颖性 | 行为倾向 |
|:-------:|:------:|---------|
| 1次 | 0.50 | 还会再去 |
| 2次 | 0.33 | 仍会回访 ← **问题** |
| 5次 | 0.05 | 终于放弃 |

→ 一个格子去过2次还有33%的吸引力，这是重复探索的根因

### 问题4: EVO不惩罚重复探索

EVO适应度函数:
```python
fitness = coverage_pct×0.35 + (1−stuck/120)×0.25 + novelty×0.15 + health×0.15 + coverage_rate×0.10
```

- `coverage_pct` 只关心"探索了多少格"，不区分"首次"还是"重复"
- 没有任何项惩罚 **revisit_ratio**（重复访问比例）
- `novelty` 奖励去新地方，但只占15%
- 重复探索也能增加 `coverage_rate`（因为每次重新进入都算"移动"）

---

## 优化方案

### 方案A: 每格场景标签 (P1, ~30行)

```python
# memory.py SpatialMemoryMap
self._cell_scenes: dict[tuple, int] = {}  # cell_key → scene_id
self._cell_events: dict[tuple, int] = {}  # cell_key → event_count (dialogue/fallen/escape)

def update(self, x, z, y=0.0, scene_id=None, scene_confidence=0.0):
    key = self._key(x, y, z)
    # 首次访问记录场景
    if scene_id is not None and scene_confidence > 0.5:
        if key not in self._cell_scenes:
            self._cell_scenes[key] = scene_id
```

**效果**: 知"这个格子是什么场景"，可以按场景类型分配探索优先级

### 方案B: 事件热度地图 (P1, ~20行)

```python
# 在MemoryController中:
# 当dialogue/fallen/escape/cliff事件发生时:
self.spatial.record_event(cell_key, event_type)

# 用于CX-3目标向量: 事件丰富区域 = 高探索价值
event_attractor = 0.3  # 事件区域的高探索权重
```

**效果**: 引导模型前往有交互事件(对话/物品)的区域

### 方案C: 增强新颖性公式 (P2, ~5行)

```python
# 当前(已太弱了):
novelty = (1 / (v + 1)) * recency * (1 - penalty)

# 增强(访问2次后快速衰减):
novelty = (1 / (v * v + 1)) * recency * (1 - penalty)
#         ^^^^^ 平方衰减
```

| 访问次数 | 当前 | 增强后 |
|:-------:|:----:|:------:|
| 1 | 0.50 | 0.50 |
| 2 | 0.33 | **0.20** ← 快速降低 |
| 5 | 0.05 | **0.04** |

### 方案D: EVO适应度增加探索效率惩罚 (P1, ~10行)

```python
# 新增适应度项:
revisit_ratio = revisits / total_moves  # 重复访问占比
revisit_penalty = max(0, (revisit_ratio - 0.2) * 2.0)  # >20%重复开始惩罚

# 新增: first_contact_bonus (首次接触新格奖励)
first_contact = new_cells_discovered / max(ticks, 1) * 100  # 每分钟新格数

fitness = cov*0.30 + unstuck*0.20 + nov*0.10 + health*0.10 + \
          speed*0.10 + first_contact*0.10 - revisit_penalty*0.10
#                                              ^^^^^^^^^^^^^^^^
#                              新增: 重复探索惩罚, 最高−0.10
```

### 方案E: 探索目标级联 (P2, ~40行)

```
长期目标(每1000 ticks): 选择地图上最远的未探索区域方向
  → 使用frontier_direction() + 场景多样性最大化

中期目标(每100 ticks): 前往最近的frontier边界
  → 使用现有的frontier_direction(search_radius=15)

短期目标(每tick): 避免最近5个访问过的格子
  → CX转向偏置中增加"最近cell排斥向量"
```

---

## 推荐实施顺序

| 优先级 | 方案 | 收益 | 工时 | 风险 |
|:------:|:-----|:----:|:----:|:----:|
| **P1** | C: 增强新颖性公式(平方衰减) | 重复探索-40% | 5min | 🟢 |
| **P1** | D: EVO增加重复探索惩罚 | EVO学习导向效率 | 30min | 🟢 |
| **P2** | A: 每格场景标签 | 场景感知导航 | 1h | 🟢 |
| **P2** | B: 事件热度地图 | 交互区域引导 | 1h | 🟢 |
| **P3** | E: 探索目标级联 | 系统级导航提升 | 2h | 🟡 |

最大短期收益: **C(平方衰减) + D(EVO惩罚)** — 半天见效