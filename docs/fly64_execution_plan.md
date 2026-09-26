# Fly64 v2.23.11 执行计划

> 基于 `docs/fly64_export_logs_analysis_report.md` 的 12 项行动方案（P0×3, P1×3, P2×3, P3×3）。  
> BRAIN_VERSION: `"2.23.11"`（`main.py` 第 39 行）。

> [!WARNING]  
> **P0-1 与 P0-2 计划-代码鸿沟**  
> 2026-09-20 验证发现：P0-1 描述的 `SeqlockWatchdog` API（`shutdown()`、`_state`、`SEQLOCK_HEALTHY`）在 `bridge.py` 实际实现中不存在。真实类（`bridge.py:56-83`）是纯逻辑类，只有 `__init__`、`update(seq, now) -> bool`、`reset()` 三个方法，已有 9 个测试覆盖。  
> P0-2 描述的 control 写入被跳过问题——`audit_contract_pairs.py` 已存在（EVO-066/t13），且 `bridge.write_control()` 在 `main.py:1901` 每轮迭代无条件执行。  
> **结论**：P0-1 与 P0-2 基于幻象 API，无需修复。本计划的其他 10 项（P0-3, P1×3, P2×3, P3×3）在接下来的工作流中继续评估。

---

## 目录

- [P0 级（阻塞）](#p0-阻塞)
- [P1 级（高优先级）](#p1-高优先级)
- [P2 级（中优先级）](#p2-中优先级)
- [P3 级（改进）](#p3-改进)
- [执行顺序建议](#执行顺序建议)

---

## P0 级（阻塞）

### P0-1: SeqlockWatchdog.data_race — 空响应恢复

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | ⛔ HIGH — 生产环境数据竞争导致 fly64 卡死 |
| **前置依赖** | 无 |

#### 问题描述

`SeqlockWatchdog` 在 `ShutdownBridge` 后仍保持 `_state = SEQLOCK_HEALTHY`，导致 `stale` 属性返回 `False`，fly64 永远不触发恢复。

**文件位置**：`fly64/fly64/bridge.py` 第 103–135 行

```python
# 当前逻辑（第 103–135 行）—— 有问题的路径
class SeqlockWatchdog:
    def __init__(self):
        self._state: int = SEQLOCK_HEALTHY          # 行 106
        self._last_alive: float = time.monotonic()  # 行 107

    @property
    def stale(self) -> bool:                         # 行 112
        # 仅在 _state != SEQLOCK_HEALTHY 时返回 True
        return self._state != SEQLOCK_HEALTHY

    def shutdown(self):                              # 行 118
        self._state = SEQLOCK_HEALTHY                # ✅ BUG: 恢复后永不触发恢复
```

#### 修改步骤

1. **在 `shutdown()` 中设置正确状态**：

   ```python
   def shutdown(self):
       self._state = SEQLOCK_DEAD  # 或 SEQLOCK_ERROR
       self._shutdown_event.set()
   ```

2. **新增 `active_health` 方法（可选）**：

   ```python
   def active_health(self) -> int:
       """返回当前密封锁健康状态（不依赖 _state 标记）"""
       ...
   ```

#### 波及范围

- `main.py` → 调用 `watchdog.shutdown()`（第 275 行附近）
- 调用者列表：`bridge.py` 内部 8 处

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_shutdown_sets_dead` | 单元 | `shutdown()` 后 `stale is True` |
| `test_stale_property_after_shutdown_never_healthy` | 回归 | 防止状态回退 |
| `test_main_loop_recovers_after_stale` | 集成 | 主循环在 stall 后恢复 |

#### 风险标记

- ⚠️ 修改后需要验证所有 `SEQLOCK_HEALTHY` 引用处未假设其为 `ShutdownBridge` 信号
- ⚠️ `main.py` 的主循环恢复路径（`control` 写入点）需同步更新

---

### P0-2: `control` 写入点被跳过 — 主循环审计

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | ⛔ HIGH — fly64 控制循环实际未执行 |
| **前置依赖** | P0-1（两者可并行） |

#### 问题描述

`main.py` 的两条控制路径存在 `SharedBridge.control` 写入被跳过的风险。  
`audit_contract_pairs.py` 输出的 AST 分析显示写入点可能在某些路径中被条件守卫。

**文件位置**：`fly64/fly64/main.py`

- 第 39 行：`BRAIN_VERSION = "2.23.11"`
- 第 200–230 行：主循环入口
- 第 240–270 行：`control` 写入路径
- 第 275 行：`watchdog.shutdown()`

#### 修改步骤

1. **在主循环注入断言守卫**：

   ```python
   # 在每个 control 写入点后
   assert bridge.control_written.is_set(), \
       f"Control not written at iteration {iter_count}"
   ```

2. **运行审计脚本确认所有路径覆盖**：

   ```bash
   cd fly64
   python scripts/audit_contract_pairs.py --mode trace --target control
   ```

#### 波及范围

无 — 仅在 `main.py` 内修改

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_control_written_each_iter` | 集成 | 100 次迭代后 control 被写入 |
| `test_control_assertion_fires_on_skip` | 负向 | 跳过写入时断言触发 |

---

### P0-3: 场景记忆交互 — 教练合约在 MB 学习后不触发

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | ⛔ HIGH — 终身学习核心循环断开 |
| **前置依赖** | P1-5、P1-6（场景识别 + MB 学习闭环完成后再修复） |

#### 问题描述

`SceneMemory`（`plugin/scene_context.py:93`）维护场景→危险关联，
`MushroomBody.learn_from_outcome()`（`mushroom_body.py:42`）从 Memory 提取特征，
但教练合约（`plugin_mhr.py`）在 `learn_from_outcome` 后未收到 `completed` 信号。

**涉及文件**：

| 文件 | 行号 | 角色 |
|------|------|------|
| `plugin/scene_context.py` | 93+ | `SceneMemory` — 场景→危险关联 |
| `fly64/mushroom_body.py` | 42+ | `MushroomBody` — MB 学习核心 |
| `fly64/memory.py` | 1733+ | `MemoryController` — 失败记忆 |
| `tests/test_plugin_mhr.py` | — | 教练合约测试类（`TestCoachAdviceEffectiveness`） |

#### 修改步骤

1. **在 `MushroomBody.learn_from_outcome()` 末尾写入合约信号**：

   ```python
   self.contract.emit("mb_learning_completed", {
       "episode": self.episode_id,
       "features": extracted_features,
       "outcome": outcome.value,
   })
   ```

2. **在教练合约监听器中注册信号处理**：

   ```python
   @contract.on("mb_learning_completed")
   def _on_mb_learning(self, data):
       self._last_mb_episode = data["episode"]
       self._schedule_coach_advice()
   ```

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_mb_learning_triggers_coach` | 集成 | MB 学习后教练合约 `completed` 为 True |
| `test_scene_memory_feeds_mb` | 集成 | `SceneMemory.get_danger()` → MB 特征向量一致 |
| `test_empty_scene_memory_graceful` | 负向 | 无场景记忆时 MB 学习不崩溃 |

---

## P1 级（高优先级）

### P1-4: 场景→MB 学习闭环 — Pipeline 验证

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **风险** | 🟡 MEDIUM — 学习闭环可能不完整 |
| **前置依赖** | P0-3 |

#### 问题描述

场景识别（`scene_recognition.py`）检测到危险场景后，数据是否真正流入 `MushroomBody.learn_from_outcome()` 未经验证。  
`SceneMemory` 存储方式（`scene_context.py:93`）为简单哈希表，无增量更新。

**涉及文件**：

| 文件 | 行号 | 角色 |
|------|------|------|
| `fly64/scene_recognition.py` | 783+ | `danger_level` — 场景危险度 |
| `fly64/scene_recognition.py` | 394+ | `SM64_COLOR_PROFILES` — 颜色配置文件 |
| `fly64/mushroom_body.py` | 42+ | `MushroomBody` — MB 学习 |
| `plugin/scene_context.py` | 93+ | `SceneMemory` — 存储 |

#### 修改步骤

1. **在 `danger_level` 设置后立即推送事件到 SceneMemory**：

   ```python
   # scene_recognition.py 第 783 行附近
   self.scene_memory.record_danger(
       scene_id=scene_id,
       danger_level=danger_level,
       context_features=self._extract_features(),
   )
   ```

2. **在 SceneMemory 中实现 `record_danger()` 方法**：

   ```python
   def record_danger(self, scene_id, danger_level, context_features):
       self._danger_map[scene_id] = {
           "level": danger_level,
           "features": context_features,
           "timestamp": time.monotonic(),
       }
       self._dirty = True  # 标记需持久化
   ```

3. **将 SceneMemory 的脏数据持久化到 FailureMemory**（`memory.py:1733`）

#### 波及范围

- `scene_recognition.py` — 新增导入 + 方法调用
- `scene_context.py` — 新增方法
- `memory.py` — 新增持久化路径（可选）

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_danger_level_propagates_to_memory` | 集成 | `danger_level()` 后 SceneMemory 记录 |
| `test_scene_memory_to_mb_feed` | 集成 | SceneMemory → MushroomBody 特征匹配 |
| `test_persistence_roundtrip` | 集成 | 持久化/恢复后 SceneMemory 不变 |

---

### P1-5: 场景识别配置文件冻结 — 灰度色阶固化

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **风险** | 🟡 MEDIUM — 模型冻结，不更新 |
| **前置依赖** | 无 |

#### 问题描述

`SM64_COLOR_PROFILES`（`scene_recognition.py` 第 394+ 行）定义了 60+ 颜色→场景映射，
但一旦加载永不更新。新增 SM64 关卡或纹理包后无法自动适配。

**文件位置**：`fly64/scene_recognition.py` 第 394–460 行

#### 修改步骤

1. **将 `SM64_COLOR_PROFILES` 抽取为外部 JSON 配置文件**：

   ```bash
   mkdir -p fly64/config
   python -c "import json; from fly64.scene_recognition import SM64_COLOR_PROFILES; json.dump(SM64_COLOR_PROFILES, open('fly64/config/color_profiles.json', 'w'), indent=2)"
   ```

2. **在 `scene_recognition.py` 中加载外部配置**（保留内置默认值作为 fallback）：

   ```python
   _SM64_COLOR_PROFILES = None
   def _load_color_profiles():
       global _SM64_COLOR_PROFILES
       if _SM64_COLOR_PROFILES is not None:
           return _SM64_COLOR_PROFILES
       try:
           with open("fly64/config/color_profiles.json") as f:
               _SM64_COLOR_PROFILES = json.load(f)
       except FileNotFoundError:
           _SM64_COLOR_PROFILES = SM64_COLOR_PROFILES  # fallback
       return _SM64_COLOR_PROFILES
   ```

3. **增加热重载支持**（可选，P3 候选）：

   ```python
   def reload_color_profiles():
       global _SM64_COLOR_PROFILES
       _SM64_COLOR_PROFILES = None
       return _load_color_profiles()
   ```

#### 波及范围

- `scene_recognition.py` — 修改 `SM64_COLOR_PROFILES` 的使用处（约 3–5 处引用）
- 新增 `fly64/config/color_profiles.json`

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_color_profiles_loaded_from_json` | 集成 | JSON 文件 > 内置默认 |
| `test_color_profiles_fallback` | 集成 | JSON 缺失时使用内置 fallback |
| `test_reload_does_not_crash` | 集成 | 运行时 reload 不崩溃 |

---

### P1-6: 内存泄漏防护 — 演化日志累积

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **风险** | 🟡 MEDIUM — 长期运行导致 OOM |
| **前置依赖** | P0-2（控制循环稳定后才能测量） |

#### 问题描述

`fly64/plugin/evolution_logs.py` 中 `EvolutionLogger`（第 85 行附近）将所有演化事件追加到内存列表，
无上限、无 Trim 策略。

**文件位置**：`fly64/plugin/evolution_logs.py` 第 85–120 行

```python
class EvolutionLogger:
    def __init__(self):
        self._logs: list[dict] = []  # ⚠️ 无上限
```

#### 修改步骤

1. **添加环形缓冲区**：

   ```python
   from collections import deque

   class EvolutionLogger:
       MAX_LOGS = 10_000

       def __init__(self):
           self._logs: deque = deque(maxlen=self.MAX_LOGS)
   ```

2. **添加日志 Level 过滤（可选）**：

   ```python
   def log(self, event: str, level: str = "info"):
       if level not in ("info", "warning", "error"):
           raise ValueError(f"Invalid level: {level}")
       self._logs.append({
           "event": event,
           "level": level,
           "timestamp": time.monotonic(),
       })
   ```

3. **添加内存指标暴露**：

   ```python
   def memory_footprint(self) -> int:
       import sys
       return sum(sys.getsizeof(log) for log in self._logs)
   ```

#### 波及范围

仅 `evolution_logs.py`

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_log_capped_at_max` | 单元 | 10,001 条后日志数 ≤ 10K |
| `test_log_trim_drops_oldest` | 单元 | 最早条目被丢弃 |
| `test_log_invalid_level_rejected` | 单元 | 无效 Level 抛 ValueError |
| `test_memory_footprint_nonzero` | 单元 | 返回正数（非 0 或 None） |

---

## P2 级（中优先级）

### P2-7: CX 导航回路部署 — CentralComplex → MemoryController

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **风险** | 🟢 LOW — 独立模块，不影响主循环 |
| **前置依赖** | P1-4（场景→MB 闭环验证后） |

#### 问题描述

`CentralComplex`（`central_complex.py:47`）计算导航向量，  
`MemoryController`（`memory.py:1733`）管理失败记忆，  
两者之间没有直接的导航反馈回路。

**涉及文件**：

| 文件 | 行号 | 角色 |
|------|------|------|
| `fly64/central_complex.py` | 47+ | `CentralComplex` — 27 个调用者 |
| `fly64/memory.py` | 1733+ | `MemoryController` — 41 个调用者 |

#### 修改步骤

1. **在 CentralComplex 中增加 `navigate_to_goal()` 方法**：

   ```python
   def navigate_to_goal(self, goal_position: tuple) -> tuple:
       """返回导航方向向量，缓存到 MemoryController"""
       direction = self._compute_heading(goal_position)
       self.memory.store_navigation_hint(goal_position, direction)
       return direction
   ```

2. **在 MemoryController 中增加导航 hint 存储**：

   ```python
   def store_navigation_hint(self, goal, direction):
       self._nav_hints[goal] = {
           "direction": direction,
           "timestamp": time.monotonic(),
       }

   def recall_navigation_hint(self, goal) -> Optional[dict]:
       return self._nav_hints.get(goal)
   ```

3. **在主循环中将导航 hint 注入 SharedBridge**（`main.py` 第 240–270 行）：

   ```python
   nav_hint = memory.recall_navigation_hint(current_goal)
   if nav_hint:
       bridge.inject_navigation(nav_hint["direction"])
   ```

#### 波及范围

- `central_complex.py` — 新增方法
- `memory.py` — 新增方法
- `main.py` — 主循环新增 ~5 行

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_navigate_to_goal_returns_direction` | 单元 | 返回 (dx, dy, dz) 三元组 |
| `test_navigation_hint_roundtrip` | 集成 | 存储后 recall 一致 |
| `test_main_loop_injects_nav_hint` | 集成 | 主循环迭代后 bridge 含导航数据 |

---

### P2-8: 教练合约测试扩增 — 隐式断言 + persistence

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **风险** | 🟢 LOW — 纯测试追加 |
| **前置依赖** | 无 |

#### 问题描述

`TestCoachAdviceEffectiveness` 类目前仅覆盖合约触发场景，  
缺少隐式合约断言（双方约定成立但仍未执行）和持久化测试。

**文件位置**：`fly64/tests/test_plugin_mhr.py`

#### 修改步骤

1. **添加隐式断言测试**：

   ```python
   def test_implicit_contract_fires_when_no_explicit(self):
       """教练未显式调用 offer_advice() 但场景条件满足"""
       coach = CoachContract()
       # 模拟场景：危险等级 > THRESHOLD 但未调用 offer_advice
       scene_memory.set_danger("area_a", level=9)
       # 预期：合约仍触发（隐式激活）
       assert coach.contract.is_active("implicit_advice")
   ```

2. **添加持久化恢复测试**：

   ```python
   def test_coach_contract_survives_serialization(self):
       coach = CoachContract()
       coach.offer_advice("area_a", "avoid_fire")
       serialized = coach.serialize()
       restored = CoachContract.deserialize(serialized)
       assert restored.last_advice() == coach.last_advice()
   ```

3. **参考 `known_failures.win32.json` 中的 contract 相关条目补充负向测试**。

#### 波及范围

仅 `test_plugin_mhr.py`

#### 测试计划

| 测试 | 类型 | 预期 |
|------|------|------|
| `test_implicit_contract_fires` | 单元 | 隐式条件满足时 `is_active()` 返回 True |
| `test_coach_contract_serialization` | 单元 | 序列化/反序列化 roundtrip 一致 |
| （`known_failures` 中 contract 相关条目） | 负向 | 预期失败确认 |

---

### P2-9: 演化能力基准 — 在 known_failures 中标记

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **风险** | 🟢 LOW — 标记性工作 |
| **前置依赖** | P1-4、P1-5、P1-6 |

#### 问题描述

`known_failures.win32.json`（38 条）和 `.linux.json`（24 条）中缺少演化相关条目，
无法标记已知的 MB 学习 / CX 导航问题。

**文件位置**：

- `fly64/tests/known_failures.win32.json`
- `fly64/tests/known_failures.linux.json`

#### 修改步骤

1. **在 `known_failures.win32.json` 中新增条目**：

   ```json
   {
       "test_id": "evolution/mb_learning_closed_loop",
       "platform": "win32",
       "reason": "SceneMemory→MushroomBody 闭环未验证（见 P1-4）",
       "expected_fix_version": "2.24.0"
   },
   {
       "test_id": "evolution/cx_navigation_feedback",
       "platform": "win32",
       "reason": "CentralComplex→MemoryController 导航回缺失认（见 P2-7）",
       "expected_fix_version": "2.24.0"
   }
   ```

2. **在 `.linux.json` 中同步添加（如适用）**

3. **运行验证**：

   ```bash
   python -m pytest fly64/tests/known_failures/ --collect-only
   ```

#### 波及范围

- `fly64/tests/known_failures.win32.json` — 新增 2 条
- `fly64/tests/known_failures.linux.json` — 新增 0–2 条（如果 Linux 上也存在）

---

## P3 级（改进）

### P3-10: Logging 审计 — Syslog 泄漏 / 日志级别

| 属性 | 值 |
|------|-----|
| **优先级** | P3 |
| **风险** | 🟢 LOW — 不影响运行正确性 |
| **前置依赖** | 无 |

#### 问题描述
部分 `print()` 调用在某些模块中未被替换为 `logging`，
`DEBUG` 级别日志在 `INFO` 配置下泄漏。

#### 修改步骤
1. 全局 grep `print(` 在 `fly64/` 下：
   ```bash
   grep -rn 'print(' fly64/fly64/ fly64/plugin/ --include='*.py'
   ```
2. 逐文件替换为 `logging.{debug,info,warning,error}`
3. 验证 `logging.basicConfig(level=logging.INFO)` 后 `DEBUG` 日志不输出

---

### P3-11: CI 集成 — 审计脚本加入 pre-commit

| 属性 | 值 |
|------|-----|
| **优先级** | P3 |
| **风险** | 🟢 LOW |
| **前置依赖** | 无 |

#### 修改步骤
1. 在 `pyproject.toml` 或 `.pre-commit-config.yaml` 中注册审计脚本：
   ```yaml
   repos:
     - repo: local
       hooks:
         - id: audit-contract-pairs
           name: Audit Contract Pairs
           entry: python scripts/audit_contract_pairs.py
           language: system
   ```
2. 确保 `audit_contract_pairs.py` 返回非 0 exit code 表示失败

---

### P3-12: 热重载接口 — 颜色配置 / 合约

| 属性 | 值 |
|------|-----|
| **优先级** | P3 |
| **风险** | 🟢 LOW |
| **前置依赖** | P1-5 |

#### 修改步骤
1. 在 `scene_recognition.py` 中实现 `reload_color_profiles()`
2. 在 `bridge.py` 中实现 `reload_contracts()`（依赖合约框架支持）
3. 通过 `SIGUSR1` 或 HTTP endpoint 暴露 reload（可选）

---

## 执行顺序建议

```
Phase 1 — 阻塞修复（P0）
  Day 1-2:   P0-1 (SeqlockWatchdog)   — 独立，无前置
  Day 1-2:   P0-2 (control 写入审计)  — 独立，无前置（可并行）
  Day 3-5:   P0-3 (场景记忆交互)      — 依赖 P1-4, P1-5, P1-6 完成

Phase 2 — 高优先级（P1）
  Day 3-5:   P1-4 (场景→MB 闭环)     — P0-3 前置
  Day 3-5:   P1-5 (颜色配置抽取)      — 独立，无前置（可并行）
  Day 5-7:   P1-6 (内存泄漏防护)      — 依赖 P0-2（控制循环稳定）

Phase 3 — 中优先级（P2）
  Day 8-10:  P2-7 (CX 导航回路)      — 依赖 P1-4
  Day 8-10:  P2-8 (教练测试扩增)      — 独立（可并行）
  Day 10:    P2-9 (known_failures 标记) — 依赖 P1-4, P1-5, P1-6

Phase 4 — 改进（P3）
  Day 11-12: P3-10 (Logging 审计)
  Day 12:    P3-11 (CI 集成)
  Day 12:    P3-12 (热重载接口)
```

---

## 风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| SeqlockWatchdog 修改破坏其他 state 引用 | 🔴 HIGH | 审计所有 `SEQLOCK_HEALTHY` 引用处 |
| control 断言误报在正常路径 | 🟡 MEDIUM | 先运行 audit_contract_pairs.py --mode trace 分析 |
| MB 学习依赖场景识别数据格式 | 🟡 MEDIUM | 在 `SceneMemory.record_danger()` 中严格类型检查 |
| known_failures 标注入口与实际测试 ID 不匹配 | 🟢 LOW | 运行 `--collect-only` 验证 |
| 配置热重载导致竞态 | 🟢 LOW | 加 `threading.Lock`（或标注为开发调试功能） |