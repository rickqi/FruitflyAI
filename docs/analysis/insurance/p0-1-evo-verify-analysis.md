# P0-1 分析报告: EVO验证窗口跨重启失效

> **分析对象**: `fly64/skills/evolution_skill.py`  
> **版本**: v3.0.0 · Brain v2.13.3  
> **报告人**: captain (代 evo-fixer)

---

## 1. 根因定位

### 核心问题: VerificationEngine 状态全部在内存中，无持久化

```
Fix Detection (OK) ──→ Fix Record (OK) ──→ Verify Start (OK) ──→ Wait 60s ... ──→
                          baselines saved      _start = time.time()      ✗ BRAIN RESTART
                          to fix_catalog.json  (in-memory only)          ✗ All state lost
```

### 代码行级追踪

| 步骤 | 方法 | 行号 | 状态存储 | 持久化? |
|:----:|------|:----:|---------|:-------:|
| 1. 检测到pattern | `DiagnosisEngine.evaluate()` | L1311 | 无状态 | ✅ 无状态函数 |
| 2. 记录Fix | `FixCatalog.record_fix()` | L705-713 | **磁盘**: fix_catalog.json | ✅ |
| 3. 记录基线 | `FixCatalog.record_baseline()` | L716-717 | **磁盘**: fix_catalog.json | ✅ |
| 4. ⭐ 启动验证 | `VerificationEngine.start()` | L790-794 | `_active`, `_start`, `_baseline` **均在内存** | ❌ |
| 5. 检查超时 | `VerificationEngine.tick()` | L796-800 | 读取 `self._start` (时间差) — 内存 | ❌ |
| 6. 记录结果 | `FixCatalog.record_outcome()` | L719-725 | **磁盘**: fix_catalog.json | ✅ 但永不会到达 |

### VerificationEngine 状态变量

```python
# VerificationEngine.__init__ (L784-788)
self._active: Optional[FixEntry] = None   # ← 内存: 当前验证中的fix
self._start: Optional[float] = None        # ← 内存: time.time() 时间戳
self._baseline: Optional[dict] = None      # ← 内存: 基线 {stuck, coverage}
```

这三个变量 → **全部在进程重启后丢失**。

## 2. 重启路径追踪

### 触发条件

```
run_one_cycle() 检测到 brain_version 变化 (L1303-1309)
  → EvolutionHistory.record_brain_version() 记录版本变化
  → 外部: CONSOLIDATE 重启 (scripts/consolidate.sh)
  → 新进程: 新的 EvolutionPipeline 实例
  → 新的 VerificationEngine: _active=None, _start=None, _baseline=None
```

### fix_catalog.json 中的数据

虽然 `baseline_stuck` 和 `baseline_coverage` 被正确持久化到 fix_catalog.json，但：

```python
# FixEntry (dataclass)
baseline_stuck: Optional[float] = None      # ✅ 持久化
baseline_coverage: Optional[float] = None   # ✅ 持久化
post_fix_stuck: Optional[float] = None       # ℹ️ 尚未写入
post_fix_coverage: Optional[float] = None    # ℹ️ 尚未写入
effective: Optional[bool] = None             # ℹ️ 尚未写入
effectiveness_score: Optional[float] = None  # ℹ️ 尚未写入
```

这些字段在 `record_outcome()` 中写入（L719-724），但 `record_outcome()` 只被 `tick()` 调用（L808），而 `tick()` 需要 `_start` 非空才能检查超时。

### stale baseline 根因

fix_catalog.json 中 5/18 修复标注 `"stale baseline: dead pre-restart session"`：

```
验证开始 → 基线写入 fix_catalog (baseline_stuck=155.82)
  → 等待60s验证窗口...
  → 进程重启 ✗
  → 新进程: VerificationEngine 没有 _active → tick() 返回 None
  → 这条fix永远卡在 pending 状态
  → 下次检测到同一pattern时，has_fix() 返回 True (有未回滚的记录)
  → 不会再创建新fix → 该pattern永久被"锁定"为 pending
```

## 3. 数据流图（当前 vs 修复后）

### 当前（断裂）:

```
Monitor ──→ Diagnose ──→ Fix(持久化) ──→ Verify Start ✗(内存)
                                              │
                                        等待60s ──→ BRAIN RESTART ──→ 状态丢失
                                                                          │
                                                                   下次cycle: 无待验证
                                                                   的fix，但 has_fix()
                                                                   返回 True → 永不重试
```

### 修复后（预期）:

```
Monitor ──→ Diagnose ──→ Fix(持久化) ──→ Verify Start ✓(状态持久化)
                                              │               verify_state.json
                                        等待60s ──→ BRAIN RESTART
                                                       │
                                              新进程初始化: 加载 verify_state.json
                                                       │
                                              发现待验证fix → 恢复计时 → 完成验证
```

## 4. 改造方案对比

| 方案 | 改动量 | 优点 | 缺点 |
|:----:|:------:|------|------|
| **A: 独立 verify_state.json** | ~40行 | 最小改动, 不修改fix_catalog结构 | 多一个文件 |
| B: 扩展 fix_catalog 字段 | ~30行 | 单文件 | 改变了现有JSON schema |
| C: 仅存 _start 时间戳 | ~20行 | 最简 | 丢失 _active 指针 |

### 推荐方案 A

新建 `skills/verify_state.json`:

```json
{
  "$schema": "fly64/evolution-verify-state/1.0",
  "active_fix_id": "fix_0004",
  "started_at": 1789226800.0,
  "baseline": {
    "stuck": 155.82,
    "coverage": 11.1
  }
}
```

**VerificationEngine 新增方法**:

```python
VERIFY_STATE_PATH = SKILL_DIR / "verify_state.json"

def save_state(self):
    """持久化当前验证状态"""
    state = {
        "active_fix_id": self._active.id if self._active else None,
        "started_at": self._start,
        "baseline": self._baseline,
    }
    VERIFY_STATE_PATH.write_text(json.dumps(state, indent=2), "utf-8")

def resume_pending(self) -> bool:
    """从磁盘恢复未完成的验证窗口"""
    if not VERIFY_STATE_PATH.exists():
        return False
    state = json.loads(VERIFY_STATE_PATH.read_text("utf-8"))
    if not state.get("active_fix_id"):
        return False
    # 从 fix_catalog 恢复 _active
    self._active = next((f for f in self.catalog.fixes 
                         if f.id == state["active_fix_id"]), None)
    self._start = state["started_at"]
    self._baseline = state["baseline"]
    return self._active is not None
```

**修改点**:
1. `VerificationEngine.__init__` 末尾调用 `self.resume_pending()`
2. `VerificationEngine.start()` 末尾调用 `self.save_state()`
3. `VerificationEngine.tick()` 完成验证后删除 verify_state.json
4. `EvolutionPipeline.__init__` 无变化(V.E.自恢复)
5. 新增测试 `test_verify_persistence`: ≥3用例

---

## 5. 总结

| 问题 | 结论 |
|------|------|
| 根因 | `VerificationEngine` 的 `_active/ _start/ _baseline` 全在内存中 |
| 影响面 | 18项fix 0 effective，10 ineffective，6 pending |
| 修复方案 | 推荐方案A: verify_state.json持久化 (~40行新代码) |
| 风险 | 极低: 新增文件、不影响现有fix_catalog schema |
| 测试 | test_verify_persistence.py (3用例: 保存/恢复/过期清理) |