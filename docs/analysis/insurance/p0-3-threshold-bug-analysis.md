# P0-3 分析报告: 坠落阈值 + turn_right双注入 + TargetTracker匈牙利匹配

> **分析对象**: `fly64/fly64/memory.py` + `fly64/fly64/model.py`  
> **版本**: Brain v2.13.3  
> **报告人**: captain (代 threshold-fixer)

---

## 1. below_ground_stuck 阈值 Y<-100 过宽

### SM64坐标系

| Y值 | 含义 |
|:---:|------|
| ~120 | 正常地面高度 |
| 50-120 | 斜坡/台阶 |
| 0-50 | 深渊 |
| <0 | 虚空(地图外) |

### 当前实现 (memory.py L138-139)

```python
y_min: float = -100.0,
y_max: float = 1000.0,
```

- `Y < -100` 才判定坠落 → 这意味着马里奥需要坠入虚空 **220个单位** 才会触发跌落恢复
- SM64中 `Y=0` 即为地图底部，`Y<50` 即已明显异常
- 建议改为 `y_min=50.0`, `y_max=500.0`

### 影响

| 场景 | 当前行为 | 正确行为 |
|------|---------|---------|
| Y=20(已坠落) | 不触发fallen(要等Y<-100) | 立即触发fallen |
| Y=-50(深渊) | still no trigger | 已触发 |
| Y=200(正常高台) | OK | OK |

---

## 2. turn_right 双倍CX注入

### 代码 (model.py L1453-1455)

```python
self.v[self.turn_left] += cx_bias * self.cx_steering_gain_turn   # L1453: left 正常
self.v[self.turn_right] -= cx_bias * self.cx_steering_gain_turn   # L1454: right 正常
self.v[self.turn_right] -= cx_bias * self.cx_steering_gain_turn   # L1455: right 重复！
```

### 对称性破坏推导

正常 CX steering:
- `left_injected = +cx_bias × gain` 
- `right_injected = -cx_bias × gain` (对称)

实际(有bug):
- `left_injected = +cx_bias × gain`
- `right_injected = -2 × cx_bias × gain` (双倍)

当 `cx_bias > 0`(右转信号):
- left: `+cx_bias × gain` → 右转(左池兴奋=右转)
- right: `-2 × cx_bias × gain` → right被抑制两次 → **净效果: 过强右转**

当 `cx_bias < 0`(左转信号):
- left: `-|cx_bias| × gain` → left被抑制
- right: `+2 × |cx_bias| × gain` → right被兴奋两次 → **净效果: 左转被削弱**

**结论**: 此bug导致CX转向始终偏右。长期运行会使脑模型倾向于右转，导致空间探索不对称。

---

## 3. TargetTracker 匈牙利匹配索引混淆

### 当前有问题的实现 (model.py L222-236)

```python
# Step 1: already matched via linear_sum_assignment into assigned_tracks/dets
# Step 2: BUT then tries to RE-MATCH using convoluted all() logic
for i in assigned_tracks:
    det_idx = min(j for j in assigned_dets
                  if all(cost[i, j] < self.MAX_ASSOC
                         for other_i in assigned_tracks
                         if other_i == i))     # ← all() with self-conditional only
    j = det_idx
    # Then AGAIN tries to match via list comprehension
    matches = [(ii, jj) for ii in assigned_tracks
               for jj in assigned_dets
               if cost[ii, jj] < self.MAX_ASSOC]
    track_match = next(((ii, jj) for ii, jj in matches if ii == i), None)
    if track_match is None:
        continue
    j = track_match[1]
```

### 问题

1. `det_idx` 的计算: `all(cost[i, j] < ... for other_i ... if other_i == i)` — 这个条件等价于 `cost[i, j] < MAX_ASSOC` 本身，因为 other_i == i 只有一项。`min()` 返回 `assigned_dets` 中的最小值索引，不是匹配的检测索引。

2. 两层匹配尝试: 先 `det_idx` (错误), 再 `matches` (正确但昂贵), 如果 n_tracks≠n_dets, `track_match` 可能为 None → `continue` 跳过更新。

3. **正确做法**: 直接使用 `linear_sum_assignment` 返回的 `(row_idx, col_idx)`:

```python
row_idx, col_idx = linear_sum_assignment(cost)
for i, j in zip(row_idx, col_idx):
    if cost[i, j] < self.MAX_ASSOC:
        # Update track i with detection j
        dr = detections[j][0] - self.tracks[i].centroid[0]
        dc = detections[j][1] - self.tracks[i].centroid[1]
        # ... rest of update logic
```

---

## 总结

| Bug | 位置 | 影响 | 修复方式 |
|:---:|:----:|:----:|---------|
| 坠落阈值 | memory.py L138 | 晚触发跌落恢复 | y_min=-100.0→50.0 |
| 双注入 | model.py L1455 | 长期右偏 | 删除重复行 |
| 匈牙利匹配 | model.py L222-236 | 多目标错配 | 重写为直接使用row_idx/col_idx |