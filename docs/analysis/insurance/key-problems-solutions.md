# 关键问题解决方案分析

> **问题**: 垂直维度缺失 / 逃逸位移≈0 / EVO不能自动改代码  
> **版本**: Brain v2.13.3 + P0-P4  
> **日期**: 2026-09-07

---

## 问题1: 无垂直维度

### 现状

```python
# memory.py L261-264 — 仅XZ平面
SpatialMemoryMap(cell_size=200.0, grid_cells=50)  # 50x50 = 2500格
# Key: tuple[int, int]  — (x, z) 无y
```

### 影响

| 场景 | 问题 |
|------|------|
| 多层关卡(地下室) | 垂直移动被映射到同一平面, 无法区分上下层 |
| 楼梯/斜坡 | 高度变化不被记录, 无法建立"上楼→新区域"的认知 |
| 坠落 | Y<50触发fallen但Y信息在内存中不持久 |

### 解决方案对比

| 方案 | 改动量 | 复杂度 | 内存影响 | 兼容性 |
|:----:|:------:|:------:|:--------:|:------:|
| **A: 3D网格扩展** (50×50×5) | ~20行 | 中 | 5× (12.5K→62.5K cells) | 好 — 仅改内部key |
| B: Y作为额外特征 | ~5行 | 低 | 极小 | 中 — 兼容现有网格 |
| C: 分层切换 | ~30行 | 高 | 不变 | 好 — 游戏层切换时重置 |

### 推荐方案A: 3D网格扩展

```python
# memory.py SpatialMemoryMap
def __init__(self, cell_size=200.0, grid_cells=50, y_layers=5):
    self.y_layers = y_layers
    # Key: tuple[int, int, int] → (x, z, y_layer)
    
def _key(self, x, y, z):
    ix = int(x / self.cell_size)
    iz = int(z / self.cell_size)
    iy = max(0, min(self.y_layers - 1, int((y + 500) / 400)))  # -500~+1500映射到5层
    return (ix, iz, iy)
```

**改动文件**: `memory.py SpatialMemoryMap._key()` + `SpatialMemoryMap.__init__()`  
**后续影响**: CX导航的goal_vectors也需Y分量 (`central_complex.py`)

---

## 问题2: 逃逸位移≈0

### 现状

```
11层脱困嵌套但逃逸位移≈0:
┌─────────────────────────────────────────────┐
│  TurnAdaptation: left=0.3 right=0.3         │
│    → counter_drive: drive_right=0.18        │
│    → breakout_drive: forward=0.21 (P1-1)    │
│  Result: 转向相消, 净位移≈0                  │
└─────────────────────────────────────────────┘
```

### 核心原因

```
编织/转圈的本质: 
  左转电流 ≈ 右转电流 → 方向互相抵消
  前向电流(0.21)不足以驱动LIF突破放电阈值(1.0)
  结果: 视觉剧烈变化(迷路), 但坐标几乎不动
```

### 解决方案对比

| 方案 | 预期收益 | 改动量 | 风险 |
|:----:|:--------:|:------:|:----:|
| **A: 方向提交** (commit方向持续≥1s) | 高 | ~10行 | 低 — 小参数变更 |
| **B: 自适应前向增益** (位移=0时递增forward) | 高 | ~15行 | 低 |
| C: 逃逸周期持续扩大 | 中 | ~5行 | 低 |
| D: CX主导逃脱(压制reflex转向) | 高 | ~20行 | 中 |

### 推荐方案A+B组合

#### A: 方向提交

```python
# model.py FlyModel — escape_mode下方向提交机制
# 在escape状态下, 选择转向方向后保持≥1秒不翻转
if self.escape_mode:
    if self._escape_commit_timer <= 0:
        # 选择方向
        self._escape_commit_dir = 1 if self.rng.random() < 0.5 else -1
        self._escape_commit_timer = 50  # 50 ticks = 1s at 50Hz
    else:
        self._escape_commit_timer -= 1
        # 抑制反方向电流, 增强提交方向
        if self._escape_commit_dir > 0:
            self.v[self.turn_right] += 0.15  # 增强已选方向
            self.v[self.turn_left] -= 0.10   # 抑制反方向
        else:
            self.v[self.turn_left] += 0.15
            self.v[self.turn_right] -= 0.10
```

#### B: 自适应前向增益

```python
# model.py FlyModel — 零位移时递增前向驱动
if self.escape_mode and abs(self._last_displacement) < 0.1:
    self._escape_forward_accum = min(0.50, self._escape_forward_accum + 0.005)
    self.v[self.forward] += self._escape_forward_accum
else:
    self._escape_forward_accum = 0.15  # reset to base
```

**改动文件**: `fly64/model.py` (FlyModel step(), ~25行新增)  
**持续影响**: 逃逸位移>0的比例预计从~20%提升至~60%

---

## 问题3: EVO不能自动改代码

### 现状

```
EvolutionSkill cycle:
  Monitor → Diagnose → Fix → Verify → Document
     ✅         ✅      ⚠️      ⚠️       ✅
                       仅记录   已验证
                       fix_template  (P0-1修)
                       需人工执行
```

### 核心约束

```python
# fix_template (default_patterns.json) 是文本字符串, 不是可执行代码
"fix_template": "# Fix: Add ground_angle gate before cliff avoidance\n# File: fly64/fly64/main.py\n# Find: ...\n# Replace: ...\n"
# EVO不能解析/执行这个template
```

### 解决方案对比

| 方案 | 收益 | 改动量 | 风险 | 说明 |
|:----:|:----:|:------:|:----:|:------|
| **A: 参数化扩展** | 中 | ~10行 | 🟢 低 | 现有BrainMutator可覆盖更多参数 |
| B: active_strategy热加载 | 中 | ~15行 | 🟢 低 | 运行时参数无需重启 |
| C: agent自动改代码 | 极高 | 大 | 🔴 高 | 需完整QA |
| D: fix_catalog → PR | 高 | 中 | 🟡 中 | 模板转DSH agent任务 |

### 推荐方案A+B组合 (立即可用)

#### A: 扩展BrainMutator参数范围

```python
# skills/evolution_skill.py BrainMutator._get_param_ranges()
# 当前只变异active_strategy中的3个参数:
#   - bold_explore_stuck_s [30, 300]  
#   - turn_bias [0, 1]
#   - stuck_threshold_s [5, 30]

# 扩展为更多运行时参数:
PARAM_RANGES = {
    'breakout_gain': (0.15, 0.50),         # escape forward drive
    'escape_forward_gain': (0.10, 0.50),   # forward injection during escape
    'escape_commit_ticks': (10, 100),       # direction commit window
    'cliff_tangent_strength': (0.05, 0.30),# cliff detour turn
    'restlessness_gain': (0.05, 0.25),     # stuck pressure→forward
}
```

#### B: 参数热加载

```python
# main.py — 从active_strategy.json读取数值参数(已有框架)
# 新增读取参数映射
strategy = load_active_strategy()  # 已有
# 映射到model实例属性
for key, val in strategy.get("brain_params", {}).items():
    if hasattr(model, key):
        setattr(model, key, val)
```

**改动文件**: `skills/evolution_skill.py` (mutator范围) + `main.py` (热加载字段)  
**效果**: EVO可以在运行时搜索参数空间(无需改代码), 找到有效组合后固化

---

## 实施优先级

| 优先级 | 方案 | 工时 | 风险 | 收益 |
|:------:|:----:|:----:|:----:|:----:|
| **P1** | 逃逸方向提交(问题2方案A) | 1天 | 🟢 低 | 逃逸位移>0比例~20%→~60% |
| **P1** | 自适应前向增益(问题2方案B) | 1天 | 🟢 低 | 逃逸位移>0→~80% |
| **P2** | 3D网格(问题1方案A) | 2天 | 🟡 中 | 多层关卡支持 |
| **P2** | EVO参数扩展(问题3方案A) | 1天 | 🟢 低 | EVO进化范围增大 |
| **P3** | EVO热加载(问题3方案B) | 1天 | 🟢 低 | 运行时无需重启 |