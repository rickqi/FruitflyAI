# Fly64 项目执行计划 — 基于对话日志分析

> **来源**: `docs/analysis/session_logs_analysis_report.md`（10 个 session、1763 条用户问题的综合分析）  
> **生成日期**: 2026-09-20（合并团队交付 2026-09-19）  
> **脑模型版本**: Fly64 v2.23.11 · 166K LIF神经元 · 151.9M突触 · MaleCNS v1.0  
> **重要说明**: AgentTeams 执行不稳定问题（对话中频繁出现的「任务为什么没有执行」）**已解决，不在本计划覆盖范围内**  
> 
> ✅ **已合并 `fly64-comprehensive-fix` 团队 5 项交付**（2026-09-19）：WSL 启动器、SM64 显示、Phase 6 进化效率、契约审计制度化、门禁冲刺。详见「已完成的治理性修复」。

---

## 目录

- [优先级总览](#优先级总览)
- [P0 级（阻塞）](#p0-级阻塞)
- [P1 级（高优先级）](#p1-级高优先级)
- [P2 级（中优先级）](#p2-级中优先级)
- [P3 级（改进）](#p3-级改进)
- [依赖关系图](#依赖关系图)
- [执行顺序建议](#执行顺序建议)

---

## ✅ 已完成的治理性修复

> 以下 5 项由 AgentTeams `fly64-comprehensive-fix` 于 2026-09-19 完成，全部通过质量审查。  
> 这些修复解决的是项目基础设施和治理层面的**长期困境**，为原有的执行计划提供了更稳定的运行基础。

| # | 任务 | 困境 | 关键产出 | 审查 |
|---|------|------|---------|------|
| ✅ **P0** | WSL 启动器方案 | WSL 后台进程生命周期不可控 | `scripts/wsl_launcher.sh`（tmux 守护 + 6 层防护）· `wsl_launcher.ps1` · `docs/wsl-launcher-deployment.md` | ✅ PASS |
| ✅ **P0** | SM64 WSLg 窗口显示 | 游戏窗口不可见的误判 | `docs/wslg-display-verification-report.md` · `verify_window_state.sh`（"131072x1" 为 tmux 警告，SM64 窗口实际正常） | ✅ PASS |
| ✅ **P1** | Phase 6 进化效率 | 适应度 40% 死重 + 62.5% 零 delta + 14/21 维噪声 | `evolution_skill.py` 重构（行为适应度、same-sample 短路、贝叶斯 GP+EI 优化）· `brain_tunable_params.json` 修复 · 12 项新测试 | ✅ PASS |
| ✅ **P1** | 契约审计制度化 | "机制存在、报告成功、无法生效" 的反复出现 | `contract_registry.json` · `contract_gate.py`（ZT-1/3/5 门禁）· `.github/workflows/ci.yml` | ✅ PASS |
| ✅ **P2** | 门禁冲刺 | 12h 连续运行从未达标 | `test_brain_startup_regression.py`（4→23 项，覆盖 10 类崩溃）· `monitor_soak.py` · `run_12h_soak.py` | ✅ PASS |

### 对现有执行计划的影响

| 原有项 | 影响 |
|--------|------|
| **P0-1 (EVO auto-fix)** | 基础更稳定：tmux 启动器确保脑模型可持久运行，不再因进程被 kill 打断 EVO 循环 |
| **P0-2 (stuck 根治)** | Phase 6 改进（行为适应度、贝叶斯搜索）可直接用于 stuck 模式的自动调参 |
| **P2-3 (EVO 度量)** | 门禁冲刺的 soak 监控脚本可直接复用；启动回归测试确保 EVO 循环不因启动崩溃中断 |
| **所有项** | 契约审计门禁可在 CI 中拦截同类"死机制"缺陷，降低新变更引入旧问题的风险 |

---

## 优先级总览

| 优先级 | 行动 | 预计工作量 | 状态 | 涉及文件 |
|--------|------|-----------|------|---------|
| ✅ **P0-G1** | WSL 启动器方案（tmux 守护） | **已完成** | ✅ 交付 | `wsl_launcher.sh`, `wsl_launcher.ps1` |
| ✅ **P0-G2** | SM64 WSLg 窗口显示验证 | **已完成** | ✅ 交付 | `wslg-display-verification-report.md` |
| ✅ **P1-G3** | Phase 6 进化效率改进 | **已完成** | ✅ 交付 | `evolution_skill.py`, `brain_tunable_params.json` |
| ✅ **P1-G4** | 契约审计制度化 | **已完成** | ✅ 交付 | `contract_registry.json`, `contract_gate.py`, `ci.yml` |
| ✅ **P2-G5** | 门禁冲刺（启动稳定 + soak） | **已完成** | ✅ 交付 | `test_brain_startup_regression.py`, `monitor_soak.py` |
| **P0-1** | EVO auto-fix 闭环：记录型→自动执行型 | 2-3 天 | 🔄 待执行 | `main.py`, `evolution_skill.py`, `fix_catalog.json` |
| **P0-2** | Mario stuck 模式根治（circle_loop, micro_loop_weave） | 2-3 天 | 🔄 待执行 | `memory.py`, `main.py`, `default_patterns.json` |
| **P1-1** | Telemetry 缺口补全（5 个缺失字段） | 0.5 天 | 🔄 待执行 | `main.py`, `telemetry.py`, `default_patterns.json` |
| **P1-2** | fallen recovery 修复 | 1 天 | 🔄 待执行 | `memory.py`, `main.py` |
| **P1-3** | 视觉系统 MVP 实现（EMD 运动检测落地） | 3-4 天 | 🔄 待执行 | `retina.py`, `model.py`, `default_patterns.json` |
| **P2-1** | 版本声明对齐 | 0.5 天 | 🔄 待执行 | `main.py`, `skills/skills.md` |
| **P2-2** | CX 导航回路完成（CX-2 锚点积分 + CX-3 目标竞争） | 3-5 天 | 🔄 待执行 | `central_complex.py`, `model.py`, `memory.py` |
| **P2-3** | EVO 健康度量自动化 | 1-2 天 | 🔄 待执行 | `evolution_skill.py`, `evolution_health_trend.jsonl` |
| **P3-1** | 过时文档标记与清理 | 1 天 | 🔄 待执行 | `docs/analysis/` |
| **P3-2** | 第二个验证场景搭建 | 5-7 天 | 🔄 待执行 | `scripts/`, `fly64/` |

---

## P0 级（阻塞）

### P0-1: EVO auto-fix 从记录型升级为自动执行型

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | ⛔ HIGH — EVO 循环断在 Fix→Verify 之间，已知 stuck 模式无法自愈 |
| **前置依赖** | 无 |

#### 问题描述

当前 EVO 系统的 Fix 阶段是**记录型修复**：`fix_template`（精确到文件和代码块的修改指引）写入 `fix_catalog.json` 并量化验证效果，但**不会自动编辑 main.py / memory.py / model.py 的游戏代码**。这导致：

- `evo_iter` 始终为 0，无常驻 evo 进程
- `fix_catalog.json` 从未创建
- Mario 已知 stuck 问题（circle_loop、micro_loop_weave）反复复现

**当前流程**：
```
telemetry → pattern 检测 ✅
pattern → fix_template 生成 ✅
fix_template → 自动代码编辑 ❌  ← 断点在这里
自动编辑 → 验证效果 ❌
```

#### 实施步骤

**步骤 1：实现 `FixExecutor` 类（`skills/fix_executor.py`）**

```python
class FixExecutor:
    """将 fix_template 翻译为实际代码编辑并执行。"""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)

    def execute(self, fix_entry: dict) -> dict:
        """执行一条 fix_template，返回执行结果。"""
        template = fix_entry.get("fix_template", {})
        target_file = template.get("target_file")
        edits = template.get("edits", [])
        for edit in edits:
            # edit = { "file": "fly64/main.py", "old": "...", "new": "..." }
            filepath = self.repo_root / edit["file"]
            content = filepath.read_text(encoding="utf-8")
            if edit["old"] in content:
                content = content.replace(edit["old"], edit["new"])
                filepath.write_text(content, encoding="utf-8")
            else:
                return {"status": "failed", "reason": "old text not found"}
        return {"status": "applied", "edits_applied": len(edits)}
```

**步骤 2：修改 `evolution_skill.py` 的 Fix 阶段**

在 `verification.py` 的 `FixCatalog.record_fix()` 调用后添加：

```python
# ── 自动执行修复（仅当 --auto-fix 开启） ──
if args.auto_fix and fix_entry.get("fix_template", {}).get("edits"):
    executor = FixExecutor(repo_root=REPO_ROOT)
    result = executor.execute(fix_entry)
    fix_entry["auto_executed"] = result
    if result["status"] == "applied":
        logger.info(f"Auto-fix applied: {fix_entry['id']} ({len(edits)} edits)")
    else:
        logger.warning(f"Auto-fix failed: {fix_entry['id']} - {result['reason']}")
```

**步骤 3：启用常驻 EVO 进程**

```bash
# 修改启动命令，启用 auto-fix + 常驻模式
python3 fly64/skills/evolution_skill.py --auto-fix --interval 30 --max-iterations 0
```

**步骤 4：添加测试验证**

新增 `tests/test_fix_executor.py`（5+ 用例）：
- 正常替换测试
- old text 不存在的 fallback 测试
- 多文件连续编辑测试
- 空 edits 列表的处理
- 回滚能力（apply 后自动备份 `*.bak`）

#### 成功标准

- [ ] `fix_catalog.json` 首次被创建并写入修复记录
- [ ] `evo_iter` 在常驻模式下持续递增
- [ ] 某条已知 stuck pattern 被自动修复并验证（effectiveness score ≥ 0.3）
- [ ] `tests/test_fix_executor.py` 5+ 用例全通过

---

### P0-2: Mario stuck 模式根治（circle_loop, micro_loop_weave）

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞 |
| **风险** | ⛔ HIGH — Mario 单次卡死可达 162s+，期间无有效行为数据 |
| **前置依赖** | P0-1（auto-fix 闭环）|

#### 问题描述

当前 Mario 同时命中 4 条 finding，最急迫的是：
- `circle_loop`：原地打转，地形门控后仍反复出现
- `micro_loop_weave`：微小循环摆动，与 circle_loop 同时出现
- `below_ground_stuck`：因 telemetry 缺失去效，悬空卡死无法检测
- `cliff_standoff`：因 telemetry 缺失去效，悬崖边上无法检测

#### 实施步骤

**步骤 1：分析 `circle_loop` 根因**

相关文件：`fly64/fly64/memory.py`（StuckDetector）、`fly64/fly64/main.py`（主循环）

需要排查：
1. `loop_score` 的计算窗口是否覆盖了合法的绕障碍运动
2. `ground_angle` 门控阈值是否在斜坡场景下误触发
3. CX 的 loop_break 机制（`CX_LOOP_BREAK_STUCK_S=45.0`）是否真的生效

参考已有分析文档：`docs/analysis/insurance/p1-1-loop-weave-analysis.md`

**步骤 2：修复 `micro_loop_weave`**

**问题**：R31-fix5 的 `cy=30` 已产生实际位移，但 anomaly 分类器只看交替转向模式无视位移 → `stuck_duration` 持续积压。

**修复**（已在 R31-fix6 中识别）：
```python
# memory.py AnomalyDetector._detect_micro_loop
# 已添加 Tier 2 门控：disp_60s > 3000 时解除 micro_loop 状态
# 确认该修复已部署且正常生效
```

**步骤 3：修复未部署的 fix_template**

从 session 日志中已有多条 fix_template 写入但未执行（如 fix_0002: fallen recovery 镜像转向、fix_0004: breakout_gain 0.15→0.25），通过 P0-1 的 auto-fix 机制全部执行。

**步骤 4：添加 stuck 模式持久化回归测试**

```python
# tests/test_stuck_patterns.py
def test_circle_loop_does_not_persist_past_45s():
    """CX loop_break 应在 45s 内打破 circle_loop。"""
    ...
def test_micro_loop_with_displacement_resets_stuck():
    """有位移时 micro_loop 不应持续积压 stuck_duration。"""
    ...
```

#### 成功标准

- [ ] Mario 单次卡死不超过 60s（当前 162s+）
- [ ] `circle_loop` 被 CX loop_break 在 45s 内打破
- [ ] `micro_loop_weave` 在有有效位移时自动解除
- [ ] 5+ 条积压的 fix_template 已自动执行并验证
- [ ] `tests/test_stuck_patterns.py` 10+ 用例全通过

---

## P1 级（高优先级）

### P1-1: Telemetry 缺口补全

| 属性 | 值 |
|------|-----|
| **优先级** | P1 — 高 |
| **风险** | 🟡 MEDIUM — 5 个缺失字段导致 3 条 pattern 实际失效 |
| **前置依赖** | 无 |

#### 问题描述

Session 4 对话中发现 `telemetry_gap` 揭示了 5 个条件字段仍未从 telemetry 暴露：

| 缺失字段 | 位置 | 导致失效的 pattern |
|----------|------|-------------------|
| `control_magnitude` | main.py | `below_ground_stuck` |
| `control_x_zero` | main.py | `cliff_standoff` |
| `control_y_zero` | main.py | `cliff_standoff` |
| `escape_behavior` | memory.py | `suspended_animation` |
| `jump_not_active` | main.py | 多条跳跃相关 pattern |

这些字段已经在 `memory.py` / `main.py` 中计算完毕，只是未在 `/flow.json` 或 `/memory.json` 端点暴露。

#### 实施步骤

**步骤 1：在 `/memory.json` 添加缺失字段**

```python
# main.py 中 memory_json 的构建位置
memory_json.update({
    "control_magnitude": float(np.sqrt(control_x**2 + control_y**2)),
    "control_x_zero": float(abs(control_x) < 1),
    "control_y_zero": float(abs(control_y) < 1),
    "escape_behavior": str(escape_behavior) if escape_behavior else None,
    "jump_not_active": float(jump_rate < 0.01),
})
```

**步骤 2：更新 `default_patterns.json` 的 condition 引用**

确认 `below_ground_stuck`、`cliff_standoff`、`suspended_animation` 三个 pattern 的条件字段与 json 键名完全一致。

**步骤 3：添加遥测完整性自检**

```python
# tests/test_telemetry_completeness.py
def test_all_pattern_conditions_have_telemetry_keys():
    """每个 pattern 的条件字段都能在 flow.json / memory.json 中找到对应键。"""
    ...
```

#### 成功标准

- [ ] 5 个字段全部在 `/memory.json` 端点可读
- [ ] `telemetry_gap` 自诊断不再报告上述字段缺失
- [ ] `below_ground_stuck`、`cliff_standoff`、`suspended_animation` 3 条 pattern 恢复可命中
- [ ] `tests/test_telemetry_completeness.py` 5+ 用例通过

---

### P1-2: fallen recovery 修复

| 属性 | 值 |
|------|-----|
| **优先级** | P1 — 高 |
| **风险** | 🟡 MEDIUM — fallen 状态下 Mario 长时间无效运行 |
| **前置依赖** | P1-1（telemetry 包含 control_y_zero）|

#### 问题描述

从 S4 对话中：Mario 卡在 y=-954 的地图下方，固定 1.5s 跳冲无法复位（depth too extreme）。R31-fix7 已实现自适应 burst duration，但需要验证在极端场景下是否真正生效。

另有 R31-fix9（教练建议影响多巴胺系统）已部署但需验证端到端效果。

#### 实施步骤

**步骤 1：验证 R31-fix7 部署状态**

```bash
# 检查 main.py 中 below-ground 逃逸的自适应 burst 时长
grep -n "burst" fly64/fly64/main.py
```

**步骤 2：编写 fallen recovery 端到端测试**

```python
# tests/test_fallen_recovery.py
def test_fallen_recovery_below_ground():
    """y<-900 的极端 fallen 场景应自适应延长 burst。"""
    ...

def test_fallen_recovery_normal():
    """正常 fallen 场景保持 1.5s burst。"""
    ...
```

#### 成功标准

- [ ] R31-fix7 代码已部署且验证通过
- [ ] `tests/test_fallen_recovery.py` 5+ 用例通过

---

### P1-3: 视觉系统 MVP 实现

| 属性 | 值 |
|------|-----|
| **优先级** | P1 — 高 |
| **风险** | 🟡 MEDIUM — 视觉覆盖度仅 ~38%，严重限制脑模型能力 |
| **前置依赖** | 无 |

#### 问题描述

从 S3 开始分析，到 S8 还在讨论设计方案。视觉系统推进缓慢的根本原因是**多个方向并行分析但没有端到端实现**。四个设计方向选择其一，用 MVP 方式落地一个。

**选择建议：4 方向 EMD 运动检测（收益最高、实现难度中等）**

参考已有设计文档：`docs/emd_4direction_design.md`、`docs/lif_injection_feasibility_report.md`

#### 实施步骤

**步骤 1：在 `retina.py` 中实现 4 方向 EMD**

EMD（基本运动检测器）使用 Hassenstein-Reichardt 相关器：
```python
# retina.py — 新增 EMD 检测器
class ElementaryMotionDetector:
    """Hassenstein-Reichardt 式 4 方向 EMD。"""

    def __init__(self, n_facets: int = 1536):
        # 定义 4 方向邻居偏移：上、下、左、右
        self.directions = {"up": ..., "down": ..., "left": ..., "right": ...}
        self.delay_buffer = np.zeros((2, n_facets))

    def compute(self, frame: np.ndarray) -> dict[str, float]:
        # HRC 核心：corr = delayed(A) × B - A × delayed(B)
        ...
        return {"emd_up": ..., "emd_down": ..., "emd_left": ..., "emd_right": ...}
```

**步骤 2：集成到 `model.py` 的视觉编码管道**

```python
# model.py encode_retina — 添加 EMD 信号
emd = self.emd.detect(brightness)
# 将 EMD 信号注入 visual 组驱动
v[visual] += emd_vector * 0.15  # 权重经校准
```

**步骤 3：在仪表板暴露 EMD 信号**

在 `/flow.json` 添加 `emd_up`/`emd_down`/`emd_left`/`emd_right` 4 个字段。

**步骤 4：添加回归测试**

```python
# tests/test_emd.py
def test_emd_right_signal():
    """水平右移图像应产生正的 emd_right 响应。"""
    ...
```

#### 成功标准

- [ ] 4 方向 EMD 在 `retina.py` 中实现，220+ 行代码
- [ ] EMD 信号注入 LIF 视觉驱动
- [ ] `/flow.json` 暴露 4 个 EMD 字段
- [ ] 仪表板 Vision 区块可观察 EMD 响应
- [ ] `tests/test_emd.py` 10+ 用例通过
- [ ] 视觉覆盖度从 ~38% 提升至 ~50%（EMD 带来的增量）

---

## P2 级（中优先级）

### P2-1: 版本声明对齐

| 属性 | 值 |
|------|-----|
| **优先级** | P2 — 中 |
| **风险** | 🟢 LOW — 不影响运行，但影响可追溯性 |
| **前置依赖** | 无 |

#### 问题描述

当前仓库存在 4 种不同的版本声明：

| 位置 | 声明的版本 | 状态 |
|------|-----------|------|
| `main.py:39` | **2.23.11** | 基准 |
| `skills/skills.md:3` | **2.23.7** | ❌ 落后 |
| `skills/skills.md:70` | **2.23.10** | ❌ 落后 |
| `evolution_history.json` | **2.23.6**（语义最大） | ❌ 落后 ≥5 个版本 |

#### 实施步骤

**步骤 1：对齐 `skills/skills.md`**

将 `skills/skills.md` 中的 `BRAIN_VERSION` 声明更新为 `2.23.11`。

**步骤 2：补全 `evolution_history.json`**

为 `2.23.7` 至 `2.23.11` 各个版本添加 `brain_update_auto` 记录（至少记录版本变化和时间）。

**步骤 3：添加版本一致性自检**

```python
# tests/test_version_consistency.py
def test_brain_version_consistent_across_files():
    """所有文件的 BRAIN_VERSION 声明必须一致。"""
    ...
```

#### 成功标准

- [ ] 4 处版本声明全部对齐为 `2.23.11`
- [ ] `evolution_history.json` 覆盖 ≥ 2.23.6
- [ ] `tests/test_version_consistency.py` 通过

---

### P2-2: CX 导航回路完成（CX-2 + CX-3）

| 属性 | 值 |
|------|-----|
| **优先级** | P2 — 中 |
| **风险** | 🟡 MEDIUM — 脑模型缺乏完整的空间定位与方向感 |
| **前置依赖** | 无 |

#### 问题描述

CX（中央复合体）硬件已在 `central_complex.py` 中存在（16 列环吸引子），但存在两个回路缺口：

| 回路 | 状态 | 作用 |
|------|------|------|
| CX-1 罗盘自主化 | ✅ v2.13.0 已完成 | 自运动 bump 积分 + 天空方位软校正 |
| CX-2 锚点路径积分 | ❌ 未完成 | 场景切换锚定 → 按罗盘航向积分位移 |
| CX-3 多源目标向量竞争 | ❌ 未完成 | novelty + 覆盖空隙质心 + 反失败格 → 向量合成 |

参考已有分析：`docs/analysis/plan-v2/` 系列文档

#### 实施步骤

**步骤 1：实现 CX-2 锚点路径积分**

```python
# central_complex.py — 新增锚点积分器
class AnchorPathIntegrator:
    """场景切换时锚定，按 CX 罗盘航向 × 前进率积分位移。"""
    def __init__(self):
        self.anchor_pos = (0.0, 0.0)
        self.integrated_pos = (0.0, 0.0)

    def update(self, heading: float, forward_speed: float, dt: float):
        dx = forward_speed * math.cos(heading) * dt
        dz = forward_speed * math.sin(heading) * dt
        self.integrated_pos = (self.integrated_pos[0] + dx, self.integrated_pos[1] + dz)

    def distance_from_anchor(self) -> float:
        return math.hypot(*self.integrated_pos)
```

**步骤 2：实现 CX-3 多源目标向量竞争**

```python
class MultiSourceGoalCompetition:
    """各源（novelty/空隙/反失败/锚点返回）目标向量竞争。"""
    def compute_goal_vector(self, sources: list[GoalSource]) -> tuple[float, float]:
        # 加权向量和，强度最大者主导
        total_angle = sum(s.angle * s.strength for s in sources)
        total_strength = sum(s.strength for s in sources)
        return (total_angle / total_strength, total_strength)
```

**步骤 3：添加回归测试**

```python
# tests/test_cx_navigation.py
def test_anchor_integration():
    """CX-2 锚点积分应准确累计位移。"""
    ...
def test_goal_vector_competition():
    """CX-3 多源竞争应选主导方向。"""
    ...
```

#### 成功标准

- [ ] CX-2 锚点路径积分实现，输出距锚距离 + 锚点方向角
- [ ] CX-3 多源目标向量竞争实现，自动选择主导目标
- [ ] `tests/test_cx_navigation.py` 15+ 用例通过
- [ ] 仪表板可查看锚点积分数据

---

### P2-3: EVO 健康度量自动化

| 属性 | 值 |
|------|-----|
| **优先级** | P2 — 中 |
| **风险** | 🟢 LOW — 不影响运行，但影响进化能力评估 |
| **前置依赖** | P0-1（auto-fix 闭环）|

#### 问题描述

`evolution_health_trend.jsonl` 仅 1 行（2026-09-18），自动度量无人采集。

#### 实施步骤

**步骤 1：在 evolution_skill 常驻循环中添加度量采集**

```python
# evolution_skill.py 的常驻循环中
health = {
    "timestamp": datetime.utcnow().isoformat(),
    "trials_unique": len(evolution_log),
    "commits": commit_count,
    "rollbacks": rollback_count,
    "inert_fraction": inert_count / max(total, 1),
    "fix_effectiveness": avg_effectiveness,
}
# 追加写入 evolution_health_trend.jsonl
```

**步骤 2：添加趋势可视化**

在仪表板添加 EVO 健康趋势面板（简单折线图，显示 trials_unique / inert_fraction 变化趋势）。

#### 成功标准

- [ ] `evolution_health_trend.jsonl` 每轮记录一次度量（不再是 1 行）
- [ ] 仪表板有 EVO 健康趋势面板

---

## P3 级（改进）

### P3-1: 过时文档标记与清理

| 属性 | 值 |
|------|-----|
| **优先级** | P3 — 改进 |
| **前置依赖** | 无 |

#### 实施计划

`docs/analysis/` 下大量文档已过时（如跨领域能力分析、保险应用报告），需要标记状态。

在每个文档头部添加状态标记：

```markdown
> **状态**: 📋 方案阶段（未实现） | ✅ 已实现 | ⏳ 部分实现 | ❌ 已废弃  
> **对应版本**: Brain v2.x.x  
> **对应代码**: `fly64/fly64/*.py` 第 XX–YY 行
```

**直接清理（标记为已废弃）**：
- `docs/analysis/t1_deep_technical_migration_plan.md` — 理论方案，无落地计划
- `docs/analysis/t3_commercialization_roadmap_report.md` — 保险领域路线图已过时
- `docs/analysis/t5_cross_domain_application_report.md` — 跨领域分析未更新
- `docs/analysis/t6_final_comprehensive_report.md` — 被新文档取代

**标记为已实现**：
- `docs/analysis/motor-expansion/*` — 运动扩展 Phase 1-5 已全部实现（Brain v2.14.0–2.17.0）
- `docs/causal-chain-ui-design.md` — 因果链路可视化已实现
- `docs/visual_capability_analysis.md` — 需要复查状态

**保留为历史参考**：
- `docs/analysis/insurance/*` — 保留为跨领域能力论述的历史参考

---

### P3-2: 第二个验证场景搭建

| 属性 | 值 |
|------|-----|
| **优先级** | P3 — 改进 |
| **前置依赖** | P1-3（视觉 MVP）|

#### 问题描述

脑模型的理论能力分析已经覆盖金融/保险/机器人/自动驾驶等领域（S1 已完成），但实际验证环境**仍是 SM64 单一场景**。

#### 实施计划

**方案 A：FlyGym 果蝇身体仿真（推荐）**

FlyGym v2 已在 S10 安装验证（`scripts/launch_interactive_viewer.py`），有现成的果蝇身体运动仿真环境。

- 将脑模型的视觉→控制闭环接入 FlyGym
- 验证脑模型能否控制果蝇身体在仿真环境中运动
- 这是最自然的第二个验证场景——从「脑+虚拟游戏」到「脑+仿真身体」

**方案 B：简单的 2D 导航环境**

- 用 `gymnasium` 搭建简单的 2D 导航环境
- 将脑模型的视觉/导航回路直接接入
- 验证 CX 导航回路在新环境中的泛化能力

**选择建议**：优先尝试方案 A（已有基础设施），如果 FlyGym 接入复杂度高则回退方案 B。

---

## 依赖关系图

```
已完成的治理性修复（2026-09-19）:
  ├── WSL 启动器 (t1) ✅ — tmux 守护脑模型 + SM64 持久运行
  ├── SM64 显示 (t2) ✅ — WSLg 窗口验证通过
  ├── Phase 6 进化 (t3) ✅ — 行为适应度 + same-sample + 贝叶斯 GP+EI
  ├── 契约审计 (t4) ✅ — ZT-1/3/5 CI 门禁 + 跨组件 WORM 契约
  └── 门禁冲刺 (t5) ✅ — 23 项启动回归 + soak + 12h 编排

待执行项:
P0-1 (auto-fix 闭环)
  ├── 无前置依赖
  └── 是 P0-2 的前置

P0-2 (stuck 模式根治)
  └── 依赖 P0-1

P1-1 (telemetry 补全)
  └── 无前置依赖（可独立执行）
  
P1-2 (fallen recovery)
  └── 依赖 P1-1（telemetry 含 control_y_zero）

P1-3 (视觉 MVP)
  └── 无前置依赖（可独立执行）

P2-1 (版本对齐)
  └── 无前置依赖（可独立执行）

P2-2 (CX 导航完成)
  └── 无前置依赖（可独立执行）

P2-3 (EVO 度量)
  └── 依赖 P0-1

P3-1 (文档清理)
  └── 无前置依赖（可独立执行）

P3-2 (第二场景)
  └── 依赖 P1-3（需要视觉 MVP）
```

---

## 执行顺序建议

### 已完成的治理性修复（无需执行）

| 优先级 | 行动 | 完成日期 | 说明 |
|--------|------|---------|------|
| ✅ **P0-G1** | WSL 启动器方案 | 2026-09-19 | tmux 守护 + 6 层防护 |
| ✅ **P0-G2** | SM64 WSLg 窗口显示 | 2026-09-19 | 消除"131072x1"误判 |
| ✅ **P1-G3** | Phase 6 进化效率 | 2026-09-19 | 行为适应度 + 贝叶斯优化 |
| ✅ **P1-G4** | 契约审计制度化 | 2026-09-19 | CI 门禁 + 跨组件契约 |
| ✅ **P2-G5** | 门禁冲刺 | 2026-09-19 | 23项启动测试 + soak |

### 第一波：独立先行（可并行执行）

```
Day 1-2:
  ┌── P0-1 (auto-fix)    ← 最关键，优先启动
  ├── P1-1 (telemetry)    ← 0.5 天，无依赖
  ├── P2-1 (版本对齐)      ← 0.5 天，无依赖
  └── P3-1 (文档清理)      ← 1 天，无依赖
```

### 第二波：依赖就绪后

```
Day 2-4:
  ├── P0-2 (stuck 根治)   ← 依赖 P0-1；Phase 6 贝叶斯优化可直接用于 stuck 参数搜索
  ├── P1-2 (fallen)       ← 依赖 P1-1
  ├── P1-3 (视觉 MVP)     ← 独立，可与 P0-1 同时启动
  └── P2-2 (CX 导航)      ← 独立
```

### 第三波：收尾

```
Day 4-7:
  ├── P2-3 (EVO 度量)     ← 依赖 P0-1；可复用 soak 监控框架
  └── P3-2 (第二场景)     ← 依赖 P1-3
```

### 工作量估算

| 阶段 | 时间 | 人数 | 说明 |
|------|------|------|------|
| 治理修复（已完成） | 3 天 | 5 | `fly64-comprehensive-fix` 团队 5 项交付 |
| 第一波 | 2 天 | 2-3 | P0-1（关键路径）+ P1-1/P2-1/P3-1（并行） |
| 第二波 | 3 天 | 2-3 | P0-2 + P1-2 + P1-3（关键路径）+ P2-2 |
| 第三波 | 3 天 | 1 | P2-3 + P3-2 |
| **合计（剩余）** | **~7-8 天** | **2-3** | 全部 10 项待执行行动 |

---

> **生成**: 2026-09-20（合并团队交付 2026-09-19） · 基于会话日志分析的实际问题与代码实测  
> **治理修复团队**: `fly64-comprehensive-fix`（5 人，2026-09-19 完成 5 项交付）  
> **取代关系**: 本计划基于 `docs/fly64_execution_plan_v2.md` 的现状评估（BRAIN_VERSION 2.23.11、929/38/36 测试基线）更新  
> **保存位置**: `docs/analysis/session_logs_execution_plan.md`

---

## 附件：团队交付文件索引

### `fly64-comprehensive-fix` 团队交付（2026-09-19）

| 文件 | 来源 | 用途 |
|------|------|------|
| `fly64/scripts/wsl_launcher.sh` | t1 | WSL tmux 守护启动器（424 行，6 层防护） |
| `fly64/scripts/wsl_launcher.ps1` | t1 | PowerShell 包装器（3 模式） |
| `fly64/docs/wsl-launcher-deployment.md` | t1 | 启动器完整部署文档 |
| `fly64/docs/wslg-display-verification-report.md` | t2 | SM64 窗口验证报告（6h+ 运行） |
| `fly64/scripts/verify_window_state.sh` | t2 | 窗口状态验证脚本 |
| `fly64/skills/evolution_skill.py`（修改）| t3 | Phase 6 行为适应度 + same-sample + 贝叶斯 GP+EI |
| `fly64/skills/brain_tunable_params.json`（修改）| t3 | 3 个参数范围修复 |
| `fly64/tests/test_phase6_fitness_inputs.py` | t3 | 新增 12 项 Phase 6 测试 |
| `fly64/contract_registry.json` | t4 | 跨组件契约注册表 v1（4 契约、18-80+ 字段） |
| `fly64/scripts/contract_gate.py` | t4 | CI 门禁脚本（ZT-1/3/5） |
| `.github/workflows/ci.yml`（修改）| t4 | CI 流水线增加 contract gate 步骤 |
| `fly64/tests/test_brain_startup_regression.py`（扩展）| t5 | 启动回归测试 4→23 项，覆盖 10 类崩溃 |
| `fly64/scripts/monitor_soak.py` | t5 | 跨平台进程树健康监控 |
| `fly64/scripts/run_12h_soak.py` | t5 | 12 小时连续运行编排器 |
| `fly64/scripts/run_soak.ps1` | t5 | Windows 侧 soak 包装器 |
| `fly64/docs/stability-report-gate-pass.md` | t5 | 门禁通过证明 |