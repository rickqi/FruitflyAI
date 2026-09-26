# Fly64 项目执行计划 — 基于对话日志分析

> **来源**: `docs/analysis/session_logs_analysis_report.md`（10 个 session、1763 条用户问题的综合分析）  
> **生成日期**: 2026-09-24（合并 t2 综合分析 + t3 执行建议）  
> **脑模型版本**: Fly64 **v2.24.0 / SKILL 3.5.1**（2026-09-26 实测；09-24 基线为 v2.23.11）· 166K LIF神经元 · 151.9M突触 · MaleCNS v1.0。⚠️ `evolution_history.json` 的 `canonical_versions.skill` 仍为 `3.4.2`（回退未修，见 P2-1）  
> **重要说明**: AgentTeams 执行不稳定问题（对话中频繁出现的「任务为什么没有执行」）**已解决，不在本计划覆盖范围内**  
> 
> ✅ **已合并 `fly64-comprehensive-fix` 团队 5 项交付**（2026-09-19）：WSL 启动器、SM64 显示、Phase 6 进化效率、契约审计制度化、门禁冲刺。详见「已完成的治理性修复」。
> 
> 🆕 **本次更新（2026-09-24）**: 基于 `docs/analysis/session-log-analysis.md`（t2）的 5 个当前困境与 12 个"死机制"模式，新增 8 项 P0-P3 建议。详见末尾「2026-09-24 更新附录」。
>
> 🆕 **2026-09-26 盲区合并更新**: 由 AgentTeams `fly64-blindspot-0923-0926` 的 t3 把 09-23 09:58 → 09-26 盲区结论并入本计划。**代码状态基准**: Windows 工作区 @ `fbcc3d7`（2026-09-26 12:28:02 +0800），实测时刻 **2026-09-26 12:47 (+0800)**。本文件新增的引用行号均为该基准下的当前实测值。详见末尾「2026-09-26 盲区合并更新附录」；完整建议条目见 `docs/analysis/session-log-recommendations.md` 的「2026-09-26 合并更新」。
> **条目数更正**: 本计划的待执行清单实测为 **18 条**（保留 10 + 新增 8），此前正文的「16 项」漏计 2 条（`P0-N2`、`P1-N1` 在波次表中未单列计数）。
> 
> **数据来源分级**:
>   - 🟢 **基于当前代码**: 文件存在性、已验证的当前代码状态
>   - 🟡 **基于会话日志**: 会话记录中的历史问题描述、行号引用（⚠️ 当前代码可能已漂移）
>   - 🔵 **基于推断**: 技术方案设计、工作量估计、优先级排序

---

## 目录

- [优先级总览](#优先级总览)
- [P0 级（阻塞）](#p0-级阻塞)
- [P1 级（高优先级）](#p1-级高优先级)
- [P2 级（中优先级）](#p2-级中优先级)
- [P3 级（改进）](#p3-级改进)
- [依赖关系图](#依赖关系图)
- [执行顺序建议](#执行顺序建议)
- [2026-09-26 盲区合并更新附录](#2026-09-26-盲区合并更新附录)

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
| **P0-N1** 🆕 | Telemetry 魔数提取为命名常量 | 1 小时 | 🆕 新增 | `model.py`, `telemetry.py` |
| **P0-N2** 🆕 | CX-2 锚点积分视觉重定位校正 | 3 天 | 🆕 新增 | `central_complex.py`, `scene_recognition.py` |
| **P0-1** | EVO auto-fix 闭环：记录型→自动执行型 | 2-3 天 | 🔄 待执行 | `main.py`, `evolution_skill.py`, `fix_catalog.json` |
| **P0-2** | Mario stuck 模式根治（circle_loop, micro_loop_weave） | 2-3 天 | 🔄 待执行 | `memory.py`, `main.py`, `default_patterns.json` |
| **P1-N1** 🆕 | StuckDetector rate_threshold 单位文档化+断言 | 0.5 天 | 🆕 新增 | `memory.py` |
| **P1-N2** 🆕 | Steering 优先级链显式实现 | 2 天 | 🆕 新增 | `central_complex.py`, `model.py` |
| **P1-1** | Telemetry 缺口补全（5 个缺失字段） | 0.5 天 | 🔄 待执行 | `main.py`, `telemetry.py`, `default_patterns.json` |
| **P1-2** | fallen recovery 修复 | 1 天 | 🔄 待执行 | `memory.py`, `main.py` |
| **P1-3** | 视觉系统 MVP 实现（EMD 运动检测落地） | 3-4 天 | 🔄 待执行 | `retina.py`, `model.py`, `default_patterns.json` |
| **P2-N1** 🆕 | control.x 旁路(10处 main.py实测)迁移至 LIF 电流注入 | 3-5 天 | 🆕 新增 | `main.py`, `model.py` |
| **P2-N2** 🆕 | 端到端契约审计测试套件增量 | 2 天 | 🆕 新增 | `tests/test_*_contract.py`, `contract_registry.json` |
| **P2-1** | 版本声明对齐 | 0.5 天 | 🔄 待执行 | `main.py`, `skills/skills.md` |
| **P2-2** | CX 导航回路完成（CX-2 锚点积分 + CX-3 目标竞争） | 3-5 天 | 🔄 待执行 | `central_complex.py`, `model.py`, `memory.py` |
| **P2-3** | EVO 健康度量自动化 | 1-2 天 | 🔄 待执行 | `evolution_skill.py`, `evolution_health_trend.jsonl` |
| **P3-N1** 🆕 | 对话 LLM 策略输出迁移至 LIF 池 | 3-5 天 | 🆕 新增 | `main.py`, `plugin/llm_consult.py` |
| **P3-N2** 🆕 | 部署脚本体系治理（50+ 脚本） | 1 天 | 🆕 新增 | `scripts/`, `.tmp/` |
| **P3-1** | 过时文档标记与清理 | 1 天 | 🔄 待执行 | `docs/analysis/` |
| **P3-2** | 第二个验证场景搭建 | 5-7 天 | 🔄 待执行 | `scripts/`, `fly64/` |

> **2026-09-26 状态增量（本表本身不改；明细见文末「2026-09-26 盲区合并更新附录」）**:
> - **`P1-N1` → ✅ 本窗口闭环**（`` `memory.py` L135 `` 已改为 `0.008` per-tick；`` `memory.py` L208 `` 带单位注释；改动未入库）。
> - **`P0-1` / `P0-2` → 部分完成，未闭环**（25-P0-2 可执行 fix / 25-P0-4 `has_fix` 已验收，但**不在 HEAD、不在活体、无记录**）。
> - **`P2-3` → 部分完成**（25-P0-3 守护 `` `evo_liveness_guard.py` `` + `` `evo_loop_launcher.sh` `` 已交付，**未接调度**）。
> - **`P2-1` → 升级为 P0**（`canonical_versions.skill = 3.4.2` ≠ `` `main.py` L50 `` / `` `skills.md` L3 `` 的 `3.5.1`；规则 8 守卫 `` `fly64/tests/check_version.py` L1 `` 为空壳）。
> - **`P2-N1` 口径确认**：`` `main.py` `` **10** 写点 / 生产 **14** / 含 `tests/` **16**（正则须排除 `==` 比较）。
> - **新增建议 `B01`–`B14`**（EVO 守护接入调度、守卫真断言、记录回收、跨环境一致性、观测点接线等）见 `docs/analysis/session-log-recommendations.md` §A.2。

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

当前仓库存在 4 种不同的版本声明（**下表为 2026-09-26 实测；09-24 旧口径一并保留于括号内**）：

| 位置 | 声明的版本（2026-09-26 实测） | 状态 |
|------|-----------|------|
| `fly64/fly64/main.py` L49（`BRAIN_VERSION`） | **2.24.0**（旧口径 `main.py:39` = 2.23.11） | 基准 |
| `fly64/fly64/main.py` L50（`SKILL_VERSION`） | **3.5.1** | 基准 |
| `fly64/skills/skills.md` L3 / L70 | **2.24.0 / 3.5.1**（旧口径 2.23.7 / 2.23.10） | ✅ 已对齐 |
| `fly64/skills/evolution_history.json` → `canonical_versions` | **brain 2.24.0 / skill `3.4.2`**（旧口径 2.23.6） | ❌ **skill 落后一版（且为回退）** |

> ⚠️ **2026-09-26 复核**: `canonical_versions.skill` 由 `3.5.1` **回退为 `3.4.2`** 发生在 commit `fbcc3d7`（非记录类提交改动 `evolution_history.json`，同时删除 `EVO-072`/`EVO-073`）。规则 8 的指定校验器 `` `check_version.py` L1 ``–`` L4 `` 全文 4 行、无 `assert`，因此该不一致**从未被拦截**（详见 `docs/analysis/session-log-recommendations.md` 新增困境 A/B）。

#### 实施步骤

**步骤 1：对齐 `skills/skills.md`**

将 `skills/skills.md` 中的版本声明更新为 `2.24.0 / 3.5.1`（**2026-09-26 实测：此项已对齐**）。

**步骤 2：补全并修复 `evolution_history.json`**

为缺失版本补 `brain_update_auto` 记录（至少记录版本变化和时间）；**并把 `canonical_versions.skill` 由 `3.4.2` 恢复/对齐为 `3.5.1`，同时回收被 `fbcc3d7` 删除的 `EVO-072`/`EVO-073`**（`git show HEAD~1:fly64/skills/evolution_history.json` 可取回；见 `docs/analysis/session-log-recommendations.md` 建议 `B03`）。

**步骤 3：添加版本一致性自检**

```python
# tests/test_version_consistency.py
def test_brain_version_consistent_across_files():
    """所有文件的 BRAIN_VERSION 声明必须一致。"""
    ...
```

#### 成功标准

- [ ] 4 处版本声明全部对齐为 `2.24.0`（brain）/ `3.5.1`（skill）——**当前 `skills.md` 已对齐，`canonical_versions.skill` 仍为 `3.4.2`**
- [ ] `evolution_history.json` 覆盖至最新 brain 版本，且 `EVO-072`/`EVO-073` 已回收
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
P0-N1 (魔数常量化) 🆕
  └── 无前置依赖（独立，1h 纯重构）

P0-N2 (CX 视觉校正) 🆕
  └── 无前置依赖（独立，但建议 P2-2 在其之后）

P0-1 (auto-fix 闭环)
  ├── 无前置依赖
  └── 是 P0-2 的前置

P0-2 (stuck 模式根治)
  └── 依赖 P0-1

P1-N1 (StuckDetector 单位) 🆕
  └── 无前置依赖（可独立执行）

P1-N2 (Steering 优先级) 🆕
  └── 无前置依赖（可独立执行，P2-N1 建议在其之后）

P1-1 (telemetry 补全)
  └── 无前置依赖（可独立执行）
  
P1-2 (fallen recovery)
  └── 依赖 P1-1（telemetry 含 control_y_zero）

P1-3 (视觉 MVP)
  └── 无前置依赖（可独立执行）

P2-N1 (control.x 迁移) 🆕
  ├── 无前置依赖
  └── 建议在 P1-N2 之后（Steering 仲裁先行）

P2-N2 (契约测试增量) 🆕
  └── 无前置依赖（可独立并行执行）

P2-1 (版本对齐)
  └── 无前置依赖（可独立执行）

P2-2 (CX 导航完成)
  ├── 无前置依赖
  └── 建议在 P0-N2 之后（先解决漂移再完成导航）

P2-3 (EVO 度量)
  └── 依赖 P0-1

P3-N1 (LLM→LIF) 🆕
  └── 依赖 P2-N1（先迁移 Reflex 再迁移 LLM）

P3-N2 (脚本治理) 🆕
  └── 无前置依赖（可独立执行）

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

### 第一波：独立先行（可高度并行）

```
Day 1:
  ├── P0-N1 (魔数常量化)    ← 1h，纯重构，最高优先
  ├── P1-N1 (StuckDetector) ← 0.5 天
  ├── P1-1 (telemetry)      ← 0.5 天
  ├── P1-3 (视觉 MVP)       ← 3-4 天，独立长任务
  ├── P2-1 (版本对齐)        ← 0.5 天
  ├── P2-N2 (契约扩展)       ← 2 天
  ├── P3-N2 (脚本治理)       ← 1 天
  └── P3-1 (文档清理)        ← 1 天
```

### 第二波：核心修复

```
Day 2-4:
  ├── P0-N2 (CX 视觉校正)   ← 3 天，无依赖但长期阻塞
  ├── P0-1 (auto-fix)       ← 2-3 天，关键路径
  ├── P1-N2 (Steering 仲裁) ← 2 天
  └── P1-2 (fallen)         ← 1 天，依赖 P1-1
```

### 第三波：依赖就绪后

```
Day 4-7:
  ├── P0-2 (stuck 根治)     ← 依赖 P0-1
  ├── P2-N1 (control.x)     ← 3-5 天，建议 P1-N2 后
  ├── P2-2 (CX 导航完成)    ← 3-5 天，建议 P0-N2 后
  └── P2-3 (EVO 度量)       ← 1-2 天，依赖 P0-1
```

### 第四波：收尾

```
Day 7-10:
  ├── P3-N1 (LLM→LIF)       ← 3-5 天，依赖 P2-N1
  └── P3-2 (第二场景)       ← 5-7 天，依赖 P1-3
```

### 工作量估算

| 波次 | 时间 | 并行人数 | 说明 |
|------|------|:--------:|------|
| 治理修复（已完成） | 3 天 | 5 | `fly64-comprehensive-fix` 5 项交付 |
| 第一波（独立先行） | 1 天 | 3-5 | 8 个无依赖项 |
| 第二波（核心修复） | 3 天 | 3-4 | P0-1(关键) + P0-N2 + P1-N2 + P1-2 |
| 第三波（依赖就绪） | 3 天 | 2-3 | P0-2 + P2-N1 + P2-2 + P2-3 |
| 第四波（收尾） | 3 天 | 1-2 | P3-N1 + P3-2 |
| **合计（剩余）** | **~10 天** | **2-4** | **18 项待执行**（保留 10 + 新增 8；09-24 的「16 项」为漏计口径，见文首条目数更正） |
| **2026-09-26 盲区新增** | **+2 小时 + 1 天（P0 三条）/ 全量约 5–7 天** | 2-3 | **新增 `B01`–`B14` 共 14 条**（P0 ×3 / P1 ×4 / P2 ×7），详见 `docs/analysis/session-log-recommendations.md` §A.2 |

---

> **生成**: 2026-09-24（合并 2026-09-20 原始版 + t2 综合分析 + t3 执行建议）  
> **治理修复团队**: `fly64-comprehensive-fix`（5 人，2026-09-19 完成 5 项交付）  
> **新增建议来源**: `docs/analysis/session-log-recommendations.md`（基于 t2 分析新增 8 项 P0-P3）  
> **取代关系**: 本计划基于 `docs/fly64_execution_plan_v2.md` 的现状评估（BRAIN_VERSION 2.23.11、929/38/36 测试基线）更新（**2026-09-26 更新：BRAIN_VERSION 现为 2.24.0 / SKILL 3.5.1；`canonical_versions.skill` 为 3.4.2**）  
> **保存位置**: `docs/analysis/session_logs_execution_plan.md`

---

## 2026-09-24 更新附录：新增建议

> 以下 8 项基于 `docs/analysis/session-log-analysis.md`（t2）在本次更新中新增。  
> 完整技术方案见 `docs/analysis/session-log-recommendations.md`。

### P0-N1: Telemetry 魔数提取为命名常量 🆕

| 属性 | 值 |
|------|-----|
| **来源** | 困境 1 🔴 — Magic numbers 散落 |
| **风险** | 🟡 MEDIUM — 可维护性灾难，长期导致 drift |
| **估计工作量** | 1 小时 |
| **涉及文件** | `fly64/fly64/model.py` |

**问题**: `model.py` 中至少 8 组魔数（0.12×8, 0.15×14, 0.20, 0.25, 0.35 等），各语义不标注。

**方案**: 抽取为命名类常量（`CX_STEERING_GAIN`, `TARGET_TURN_GAIN`，含物理单位注释），替换 20+ 处引用。

---

### P0-N2: CX-2 锚点积分视觉重定位校正 🆕

| 属性 | 值 |
|------|-----|
| **来源** | 困境 2 🔴 — 60 秒后导航方向失效 37.5% |
| **风险** | 🔴 HIGH — 长时间导航不可靠 |
| **估计工作量** | 3 天 |
| **涉及文件** | `central_complex.py`, `scene_recognition.py`, `memory.py` |

**问题**: `_self_motion_update()` 使用 heading_rate 开环积分，无视觉闭环校正。

**方案**: 场景识别 → 锚点 heading 匹配 → 估计偏差 → 校正 CX 罗盘 bump_center。

---

### P1-N1: StuckDetector rate_threshold 单位文档化+断言 🆕

> ### ✅ **本窗口闭环（2026-09-26 复核确认）**
> `` `memory.py` L135 `` 现为 `rate_threshold: float = 0.008,   # P0-a2: per-tick fraction; was 5.0 Hz`，`` `memory.py` L208 `` 比较式带显式单位注释。完成时间：本窗口内（≥09-23）；具体提交时间不可定位（改动属 37 个已跟踪未提交文件之一）。详见 `docs/analysis/session-log-recommendations.md` §A.1。以下 09-24 原文保留为历史记录。

| 属性 | 值 |
|------|-----|
| **来源** | 困境 3 🟡 — `forward_rate` 单位歧义 |
| **估计工作量** | 0.5 天 |
| **涉及文件** | `fly64/fly64/memory.py` |

**问题**: `rate_threshold=5.0` 标注为 Hz，但 `forward_rate` 物理含义为"动作频率"还是"位移速率"未明确。

**方案**: 更新文档字符串 + 添加运行时断言验证 `0 < forward_rate < 100 Hz`。

---

### P1-N2: Steering 优先级链显式实现 🆕

| 属性 | 值 |
|------|-----|
| **来源** | 困境 5 🟡 — Escape vs CX 竞争 |
| **估计工作量** | 2 天 |
| **涉及文件** | `central_complex.py`, `model.py` |

**问题**: escape 方向提交与 CX 新颖性引导产生相反偏置，无显式仲裁。

**方案**: 新增 `SteeringArbiter` 类，优先级链: **Reflex > Escape > CX Exploration > Default**，所有 steering_bias 经 arbiter 输出。

---

### P2-N1: control.x 旁路（10处 main.py写点/71次全仓引用）迁移至 LIF 电流注入 🆕

| 属性 | 值 |
|------|-----|
| **来源** | 困境 4 🟡 — Python 层无条件覆盖神经决策 |
| **估计工作量** | 3-5 天 |
| **涉及文件** | `fly64/fly64/main.py`, `model.py` |

**问题**: **10 处**直接（`main.py` 写点，2026-09-26 实测；生产口径 14 / 含 `tests/` 16）`control.x` 写入，跳过神经决策链。（原文的「Reflex 6 + LLM 11 + 坠落恢复 6」为 09-13 版本的 22 处旧口径，**已作废**——现行分类为 reflex 1 / escape+fallen 4 / cliff 1 / LLM policy 1 / nav+test 4，共 10 处；见 `docs/analysis/session-log-recommendations.md` 勘误块与 §A.6-C8。）

**方案**: Phase 1（P2）：Reflex + 坠落 → 设 flag / LIF 注入；Phase 2（P3-N1）：LLM 策略迁移。

---

### P2-N2: 端到端契约审计测试套件增量 🆕

| 属性 | 值 |
|------|-----|
| **来源** | t2 第 4 节 — 12 个"死机制"模式 |
| **估计工作量** | 2 天 |
| **涉及文件** | `contract_registry.json`, `tests/test_*_contract.py` |

**问题**: 当前契约注册表仅 4 项，未覆盖多数已知"死机制"模式（逃逸位移、StuckDetector 衰减等）。

**方案**: 新增 5 项契约 + 相应 `test_*_contract.py`（逃逸、StuckDetector 衰减、Loop Score、策略穿透、Steering 竞争）。

---

### P3-N1: 对话 LLM 策略输出迁移至 LIF 池 🆕

| 属性 | 值 |
|------|-----|
| **来源** | 困境 4 Phase 2 — 11 处 LLM 旁路 |
| **前置依赖** | P2-N1 |
| **估计工作量** | 3-5 天 |
| **涉及文件** | `main.py`, `plugin/llm_consult.py` |

**问题**: 最严重的架构性问题 — LLM 输出跳过整个神经决策链。

**方案**: 新增 `LIF_PolicyPool` 接收 LLM/Coach 策略，在主循环中 resolve 注入神经链。

---

### P3-N2: 部署脚本体系治理 🆕

| 属性 | 值 |
|------|-----|
| **来源** | t2 领域 C3 — 50+ 脚本缺乏统一治理 |
| **估计工作量** | 1 天 |
| **涉及文件** | `scripts/`, `.tmp/` |

**问题**: fixN / mN / ver_append 命名混乱 + 重复逻辑 + .tmp/ 未清理。

**方案**: 分类为 `deploy/`, `diagnostics/`, `monitoring/` 子目录 + 合并重复部署逻辑 + 清理临时文件。

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

---

## 2026-09-26 盲区合并更新附录

> **来源**: AgentTeams `fly64-blindspot-0923-0926` — `docs/analysis/blindspot-evidence-0923-0926.md`（t1，469 行）、`docs/analysis/blindspot-analysis-0923-0926.md`（t2，328 行）
> **合并落点**: 本附录（执行计划侧）+ `docs/analysis/session-log-recommendations.md`「2026-09-26 合并更新」（建议与困境清单侧）
> **代码状态基准**: Windows 工作区 @ `fbcc3d7`（2026-09-26 12:28:02 +0800）；**实测时刻 2026-09-26 12:47 (+0800)**
> **纪律**: 原有 18 项条目**一条不删、不放宽**；已闭环项仅追加 ✅ 标注与完成时间。

### 1. 本窗口（09-23 09:58 → 09-26）落地了什么

| 结论 | 状态 | 证据 |
|---|---|---|
| gate 单位契约（Hz 域统一）生效 | ✅ 闭环（活体确认可达：`gate_jump_ratio` 6 采样 4 次 > 阈值 0.75） | t2 §2.1-#4 |
| WSLg 渲染修复 | ✅ 闭环（活体单点 `render_ms 6.12` / `bridge age_ms 16.59`） | t2 §2.1-#12 |
| 25-P0-1 信用分配矩阵 | ✅ 闭环（134 写点 / 6 断口，AST） | t2 §2.1-#11 |
| 25-P0-3 EVO 守护与停摆告警 | ⚠️ **部分**（脚本 4/4 验收，**未接调度**） | t2 §3.2-E1 |
| 25-P0-2 可执行 fix / 25-P0-4 `has_fix` | ⚠️ **部分**（已验收，**不在 HEAD、不在活体、无记录**） | t2 §3.2-E4/E9 |
| StuckDetector 单位（本计划 `P1-N1`） | ✅ **本窗口闭环** | `` `memory.py` L135 `` |
| 窗口产出入库 | ❌ **37 个已跟踪未提交 + 65 个未跟踪** | t2 §2.2 |

### 2. 新增建议索引（`B01`–`B14`，全部有盲区证据）

| 编号 | 优先级 | 工时 | 行动 | 归属既有条目 |
|---|:--:|:--:|---|---|
| B01 | P0 | 1 小时 | EVO 守护接入 crontab + 真实 kill→拉起验证 | `P2-3`（补充） |
| B02 | P0 | 0.5 天 | `` `check_version.py` `` 改为真断言（四处比对 + `exit 1`） | `P2-1`（升级） |
| B03 | P0 | 0.5 天 | 回收 `EVO-072`/`EVO-073` + 三处版本对齐 | `P2-1`（升级） |
| B04 | P1 | 0.5–1 天 | 未入库交付分批收口 | `P3-1`/`P3-2`（补充） |
| B05 | P1 | 0.5 天 | 跨环境部署一致性门禁（md5 manifest） | `P3-N2`（补充） |
| B06 | P1 | 0.5 天 | 钳位观测点/归因接线 | `P1-1(clamp)` 后续 |
| B07 | P2 | 1 小时 | 契约消费者侧补测 + 删除夹具补键 | `P2-N2`（补充） |
| B08 | P2 | 2 小时 | 验收清单假绿项收口 | `P2-N2`（补充） |
| B09 | P2 | 0.5 天 | 引用校验器精度改进（S1/S2） | `P2-N2`（补充） |
| B10 | P2 | 0.5 天 | 分析工具链编码/口径纪律 | 新增 |
| B11 | P2 | 2 小时 | 磁盘/日志轮转 | 运维 |
| B12 | P1 | 1 天 | 复采 ≥6000 帧验证运动改善 | `P1-2`/`P0-2`（补充） |
| B13 | P2 | 0.5 天 | 双测试根收敛确认 | 基线 |
| B14 | P2 | 0.5 天 | 教练链路口径核查 | 新增 |

> 每条的技术方案、涉及文件（含当前实测 `file:line`）与证据出处见 `docs/analysis/session-log-recommendations.md` §A.2。

### 3. 现行优先级（与建议文档一致）

```
P0: 新增困境 A（守卫无断言） → B02
   新增困境 B（记录删除+版本回退） → B03
   B1 自进化闭环（部分缓解未解决；09-26 11:47 再停摆；告警器最后自检 09-25 21:01） → B01
   新增困境 C（窗口产出未入库） → B04
   A1 Telemetry 常量（P0-N1，未缓解）
P1: A4 control.x 直写（未恶化）/ A2 CX-2 改为「验证」 / B2–B3 断口与观测层 /
   新增困境 D 活体漂移 → B05 / 新增困境 E 假绿清单 → B08 / P2-N2 契约审计 / P2-1 版本对齐
P2: A5 Steering 仲裁（被 H13 阻塞）/ B4 多会话并发写 / B5 运维负担 → B11
关闭: A3 StuckDetector 单位 ✅ 本窗口闭环
阻塞: H13 裁定 ⇒ P2/P3 整体阻塞（含闭环转正式）
```

### 4. 数字口径（本附录与建议文档**必须一致**）

| 数字 | 值（2026-09-26 实测） | 复现 |
|---|---|---|
| `control.x` 写点 | `` `main.py` `` **10** / 生产 **14** / 含 `tests/` **16** | `Select-String -Path fly64/fly64/main.py -Pattern 'control\.x\s*=(?!=)'` |
| 已跟踪未提交 / 未跟踪 | **37 / 65** | `git status --porcelain` |
| `evolution_history.json` | **87** 条；`EVO-072`/`EVO-073` 缺失；`canonical_versions.skill = 3.4.2`；`fbcc3d7` numstat **115/39**；`HEAD~1` = **81** 条含两条记录、`skill = 3.5.1` | 见建议文档 §A.7 |
| 版本四处 | `` `main.py` L49 `` 2.24.0 / `` `main.py` L50 `` 3.5.1 / `` `skills.md` L3 ``+`` L70 `` 3.5.1 / canonical skill 3.4.2 | `Select-String -Path fly64/fly64/main.py -Pattern 'BRAIN_VERSION\s*=\|SKILL_VERSION\s*='` |
| 守卫 | `` `check_version.py` `` 4 行、无 `assert`；WSL `exit 0` | 见建议文档 §A.7 |
| 调度 | WSL `crontab -l` 仅 `watchdog.sh` / `phase2_gate.sh` | `wsl -e bash -c 'crontab -l'` |
| 运维 | `/tmp` **≥134 G（滚动；13:19 = 135 G / 13:24 = 136 G）** / `f64r_traj-*.npz` 3435 个 / 根分区 78% / `evolution_log.jsonl` 200 MB | `wsl -e bash -c 'du -sh /tmp; df -h /'` |

### 5. 文档自洽校验

```powershell
python scripts/verify_doc_citations.py    # 必须 exit 0（建议文档 + 本计划 + 分析文档三份一起校验）
```

---

## 2026-09-26 t5 返修勘误块（append-only，依据 t4 核验报告）

> 依据 `docs/analysis/blindspot-review-0923-0926.md`（t4 独立核验），处置 M-1~M-5 与两处新遗漏。**本块只追加，不修改上文任何条目**；凡与下文冲突的上文表述，**以本块为准**。配套勘误见 `session-log-recommendations.md` §A.8。

| # | 上文位置 | 原表述（被本块更正） | 更正后（实测） | 依据 |
|:-:|---|---|---|---|
| **E-1** | L72「P1-N1 ｜ StuckDetector rate_threshold 单位文档化**+断言**」；L88「`P1-N1` → ✅ 本窗口闭环」；L846 小节标题；L975「✅ 本窗口闭环」；L1010「关闭: A3 StuckDetector 单位 ✅」；L859「方案: 更新文档字符串 + **添加运行时断言**验证 `0 < forward_rate < 100 Hz`」 | 「单位文档化 + 运行时断言」均记为完成、A3 记为关闭 | **拆分**：① **单位标注/文档化 ✅ 已实现**（`memory.py:135` = `0.008 per-tick`、`:207-208` 单位注释）② **运行时断言 ❌ 未实现** —— `memory.py` 内 `rate_threshold` 仅 `135/142/208` 三处，**全文 `assert` 计数 = 0**；③ **可观测性未闭环**：`stuck_score` 仍可达 1.0（t4 12:54 六连；我的离线仿真 3000 tick 内 **14 次** `score==1.0` 且全部 `dur==0.0`），且 `docstring:127` 仍写「`< 5 Hz`」⇒ **A3 只在"单位口径"上关闭** | `Select-String -Path fly64/fly64/memory.py -Pattern 'rate_threshold'`（3 处）/`'^\s*assert\b'`（0 处）/`'5 Hz'`；t4 §3 与 §6 |
| **E-2** | L90「`P2-3` → 部分完成（`evo_liveness_guard.py` + `evo_loop_launcher.sh` 已交付，**未接调度**）」 | 未标注目录；未记录执行位 | 补明：两脚本均在 **`fly64/scripts/`**（`fly64/skills/evo_liveness_guard.py` **不存在**）；且在 git 中均为 **`100644`（无执行位）** ⇒ WSL 上必须 `bash scripts/…`，与"可被 cron/启动器直接调用"的运行契约冲突（与 B01 同族） | `Test-Path`；`git ls-files --stage`；行数 **407 / 211**（⚠️ **t7 更正**：原先用 `Measure-Object -Line` 得 339 / 179，属**漏计口径**，已废弃；可靠口径为 `wc -l` 或 `git show 38c8bae --stat` 的新增行数——两文件在该提交新建 ⇒ 新增行数 == 文件总行数） |
| **E-3** | L1007「P1: A4 control.x 直写（**未恶化**）/ A2 CX-2 改为「验证」/ B2–B3 断口与观测层」 | A4 已写"未恶化"（**正确，保留**）；B3 未定级 | **A4 保留"未恶化"并给全口径**：`main.py` **10** / 生产 **14** / 含 `fly64/tests` **16** / 含根 `tests` **17**（赋值口径 `control\.x\s*=(?!=)`；`2f87d77^`=`HEAD`=工作区均 10）。**B3 升级为"未缓解"**：`stuck_score ≡ 1.0` 构造伪影**未消除**（同上 E-1③）。**RC 例数 12 → 13**（RC-4 1 → 2，新增 `stuck_score`/`rate` 实例；与 A3 同族症状、不同判据，与 RC-5 叠加，非新子型） | 同 E-1；队长裁定；t2 §3.2-E13/§3.3 |
| **E-4** | 全文**未记录** | — | **补录**：`runtime/evolution_history.json`（7,110–7,134 B，**每轮重写、仅 WSL**，消费方 `fly64/fly64/main.py:61/220/2360`）与 `skills/evolution_history.json`（99,101 B，canonical，消费方 `skills/evolution_skill.py:202` + `tests/test_version_consistency.py:28`）是**两份不同历史文件** ⇒ 恢复/一致性动作（本计划 P0 的"回收 EVO-072/073"等）**必须分别处置** | WSL `ls -l` + `head -c`；`Select-String` 消费方 |
| **E-5** | L90 等处的"未接调度"结论 | — | **不变（复核确认）**：WSL `crontab -l` 仍仅 `watchdog.sh` / `phase2_gate.sh`；`evo_stall_alarm.json` 停 09-25 21:01:25 ⇒ B01（把守护接入调度）**仍待执行** | t4 §2-V8 |
| **E-6** | **L840**「**问题**: `_self_motion_update()` 使用 heading_rate 开环积分，**无视觉闭环校正**」+ L842「方案: 场景识别 → 锚点 heading 匹配 → 偏差校正（3 天）」（M-6，t5 attempt 2） | 该条把视觉重定位写作"**尚未实现**"（3 天工作量） | ⚠️ **过时**：`AnchorPathIntegrator.relocalize()` **已存在**（`central_complex.py:128-140`，gate 0.8 / strength 0.3）+ **调用点 2 处**（`:529`、`:673`）+ 测试 `test_cx_navigation.py:179-204` ⇒ 本条应从"实现（3 天）"改为「**验证/接线（0.5–1 天）**：核对 `scene_id`/`scene_confidence` 的实际来源与类型、统计活体命中率」。**已交付文档 `session-log-analysis.md` 的同源过时表述已就地回改**（其附录 C 第 1 项），本计划的对应工作项见本轮 t3 的 A2 降级 | `central_complex.py:128-140/529/673`；`test_cx_navigation.py:179-204`；`session-log-analysis.md` 附录 C |

---

## 2026-09-26 第三轮（一手会话）合并更新附录（append-only）

> **来源**: AgentTeams `fly64-newlogs-0924-0926` — `docs/analysis/session-analysis-0924-0926.md`（t2，**562 行 @t5 核验时点**）· `docs/analysis/blindspot-crossvalidation.md`（t3，**559 行 @t5 核验时点**）
> ⚠️ **时点/修改声明（t6 补）**：本附录写入时二者未改动；**t6 已对 t2/t3 就地更正**（F-1/F-2/F-3/F-5/F-9/F-10 + t3 措辞与 pkill 口径）⇒ 现测 **t2 = 569 行 / t3 = 564 行**。细则见本附录 **第 9 节**。
> **合并落点**: 本附录（执行计划侧）+ `docs/analysis/session-log-recommendations.md` **§A.9**（建议与困境清单侧）+ `docs/analysis/project-state-consolidated.md`（项目级合并结论，t4）
> **纪律**: 本附录**只追加**；原有 18 项、`B01`–`B14`、本文档既有波次与 §A.0–§A.8 勘误块**一条不删、一条不放宽**。凡与本附录冲突的上文表述，**以本附录为准**（最新）。
> **性质限定**: 本附录**不含新一轮实测**；所有 `file:line` 与活体数值**转引自** t2/t3/blindspot 文档。

### 1. 数字口径增量（**与建议文档 §A.9.1 必须一致**）

| 项 | 旧口径 | **本轮权威（t3 §A.2，队长更正确认）** | 复现 |
|---|---|---|---|
| 主会话 `tool/call` 快照合计 | 1826 | **1826（6 快照相加值，非"当日工作量"）** | 逐快照 726/58/304/350/152/236 = 1826 |
| 去重后日度 | 336 / **185** / 153（合计 674） | **336 / 206 / 153（合计 695）** — 185 漏掉只存于 v3 的 21 次 | 每会话取最新切片再求和 |
| 全局去重（distinct `callId`） | — | **1312**（`1826 − 1312 = 514`；`1312 = 695 + 617`） | t5 §1.1-A4 |
| 切片重复副本 | 617（t2；**算式不自洽**）→ 1131（**本轮初版，跨域相减**） | **514** = **窗口域** `快照合计 1209 − 去重 695` = **全快照域** `1826 − 全局去重 1312`（**t6／F-1 更正**） | t5 §9-F-1（`distinct callId = 1312`） |
| 窗口外调用量 | — | **617**（09-19→09-23，仅存于 `99cab60f-latest`，**无副本** ⇒ 正是它使 1826 与 695 不可相减） | t5 §1.1-A4 |
| write/edit 变更 | 87（t1，**口径未声明**） | **调用 126**（逐快照唯一 (工具,路径) = **87**；全局唯一路径 **63**；全局唯一 (工具,路径) **69**）—— t6／F-4 | t5 §1.1-A5 |
| 未跟踪项数 | 65（t2 时点）；另有"51" | **65 不变**（t3 §A.6-C11）；**"51" = t2 手工枚举的窗口产出子集（判据缺失）**；`git status ??` 实测 **74**、剔除本轮 3 份新文档 **71**（t6／F-5） | `git status --porcelain=v1 \| Where-Object {$_ -match '^\?\?'}` |
| `evo_liveness_guard.py` / `evo_loop_launcher.sh` 行数 | PS `Measure-Object -Line` 339 / 179 | 权威 **407 / 211**（`wc -l` 与 `git show --stat` 双证）；**PS 与 Python 差值分别为 68 / 32，不是"恒为 11"**（t6／F-10） | `python -c "print(open(p,encoding='utf-8').read().count(chr(10)))"` |
| t2 篇幅 | 自报 563 行 | **562 行 @t5 核验时点**（t6／F-6；`563` 在正文中仅作为 inode `125256364637215400` 的片段出现）；**t6 就地补注后现为 569 行** | `len(open(...).read().splitlines())` |
| `evolution_history.json` 改动量 | 队长口述 +137/−41 | **115/39**（该文件 `--numstat`）；**137/41 是 `git commit` 的三文件汇总行**（`51f62457-v2` 12:28:03 `L1098`） | `git show fbcc3d7 --numstat` |
| `control.x` 写点 | 10 / 14 / 16 | **10 / 14 / 16 / 17**（第 4 级 = 含根 `tests/`；赋值口径 `control\.x\s*=(?!=)`）；`2f87d77^`=`HEAD`=工作区均 10 ⇒ **未恶化** | 同 §A.8-E-3 |
| 未跟踪项数 | 65（t2 时点） | **不变**（t3 §A.6-C11）——**注**：本行原写「未跟踪 51（t2 亲自复算）」已被上表 t6／F-5 行取代（51 是**手工枚举的窗口产出子集**，非 `git status` 计数） | `git status --porcelain` |

> **引用禁令（t6／F-1 修订）**：**1826 不得写成"当日工作量"**；**617 不得再被引用为"重复数"**（它是窗口外调用量、无副本）；**`1826` 只能与 `1312` 相减** ⇒ 重复副本 = **514**；**任何减法必须两项同域**；`fbcc3d7` 的 `evolution_history.json` 改动量写 **115/39**。

### 2. 困境与结论的**性质修订**索引（细则见建议文档 §A.9.2）

| ID | 被修订的上文条目 | 修订要点 | 归属建议 |
|:--:|---|---|---|
| **G-1** | 「新增困境 B」触发提交（§本附录 E-4 / 建议文档 §A.3.2） | `fbcc3d7` = **意外覆盖（`cp` 事故）**，作者会话 = **`51f62457-v2`**；根因 = 双份 `evolution_history.json` 分叉；附带解开 U11 | **B03 + B17** |
| **G-2** | §本附录 E-4 / §1「25-P0-2/P0-4 不在 HEAD、不在活体」 | 「**不在活体**」= **过度推断**，降级为**待验证**（须做符号存在性核对，非 md5 差集） | **B04 + B05** |
| **G-3** | 「新增困境 E」/ §A.0 与 §1 的假绿项 | 性质改写为「**承诺过 + 派过单 + 未落到发布点**」；新增同族更早实例 `HAS_EVO_LIVENESS=False` | **B08 + B01** |
| **G-4** | `stuck_score` 相关（§E-1/E-3） | 补**反判据 `stuck_duration_true`（4.48/4.88）**；会话当场误判为"真卡死/伪影已消" | **B15** |
| **G-5** | §3「B1 自进化闭环」中的 E1 时间语义 | **11:47 = 心跳末次写入（现象时刻）**；「14.5h 无告警」= **09-26 12:36 事后算出**；**窗口内无会话记录该停摆**；E1/RC-1 引文**降级为待补证**；**导出覆盖有洞（09-25 21:00–21:18）** | **B01** + 独立任务 |
| **G-6** | §A.8-E-5（E7） | **部分成立**（生产者+测试迁移可见，消费者改动未见）；低危限定必须保留 | **B07** |
| **G-7** | §4 数字口径 / 全报告 | `833848c`/`38c8bae` **非 0 命中**（38/176 次，均为 `git log`/`push` 输出行）⇒ 未覆盖的是**其作者会话**；**43 项 `D` 全在 `fly64/.pytest-run/**`（pytest 夹具），不计入证据真空** | 独立任务 |
| **G-8** | 全文未记录 | **补录**：`gate_jump_threshold` 语义断裂 = **一条被明确警告却未闭环的迁移**（同 key 换语义 → 队长 09-24 13:13:14 以 `3.082 > 3.0` 当场证伪 F1 → t7 迁移清单 0.75 → 09-25 18:54 部署清单明文警告 → 仍未闭环） | **B01/B04 同批** |
| **G-9** | 「新增困境 C」（窗口产出未入库） | **补因**：除脏树外新增「**有意搁置**（避免带入他方在途工作，有解除条件）」；未入库 2485 行中约 **2450 行属另一 DSH 会话** | **B04** |
| **G-10** | §3「B1」/ A4 | A4 **保留"未恶化"**并给全口径 **10/14/16/17**；**B4 严重度上调**（同一文件内混合改动 + 同一实例被互相拆掉） | **P2-N1 + B16** |

### 3. 新增困境（**F / G**）与新增建议（**B15 / B16 / B17**）

| 项 | 类型 | 要点 | 建议 |
|---|---|---|---|
| **新增困境 F** | 困境（P1） | **跨会话/跨进程「重启无互斥」**：09-26 11:47–12:05 两会话并发处置同一故障；12:02:59 起**唯一**执行 `pkill -f fly64.main` 的是 `6c53f724-v3`（**6 次 `write` 脚本轮次（11:54:25→12:02:59），实际执行 `pkill` 共 3 条（11:55:30 / 11:57:24 / 12:02:47）** + `rm -f /tmp/f64b_traj`，杀掉 `51f62457` 自 11:47:47 起的脑 2505 及后续实例）；**「描述矛盾」实为不同时刻（11:52 vs 12:03），同刻无矛盾**；`locked_launcher.py`（只防 `run-fly64` 重复启动、不识 SM64）与 `.evo_loop.lock`（PID 11997，只锁 EVO 循环）**均不覆盖「brain+SM64 重启」** | **B16** |
| **新增困境 G** | 困境（P1） | **工作区/WSL 双份 `evolution_history.json` 分叉**：`skills/…`（99,101 B / 87 条）vs `runtime/…`（7,110–7,134 B / 2 键 / 仅 WSL）；**已兑现两个后果**（`cp` 覆盖删记录；md5 分叉致部署证据链断裂）。**B03/B05 只治后果、不治根因** | **B17** |
| **B15** | 建议 P1 / 0.5 天 | `stuck_score` 恒真代码修复（`memory.py:213-225` 取 `max` + `memory.py:234-235` 泄放抹零；改口径 + 断言「`stuck_duration == 0` 时 `stuck_score` 不得为 1.0」） | 别名 **P1** |
| **B16** | 建议 P1 / 0.5 天 | 「brain+SM64 重启」补锁/互斥 + 告警（覆盖 `wsl_launcher.sh` / `setsid python3 -m fly64.main` / `pkill` 三路径；`brain_wrapper.sh` 纳入协调） | 别名 **P1-new** |
| **B17** | 建议 P1 / 0.5 天 | 消除双份 `evolution_history.json` 分叉 + 一致性守卫（canonical 单一权威 / 分叉检测门禁） | 别名 **P1-new2** |

**口语编号 → 正式编号映射**: `P0-a`→**B03**、`P0-b`→**B02**、`P0-c`→**B01**、`P0-d`→**B04**、`P1`→**B15**、`P1-new`→**B16**、`P1-new2`→**B17**。

### 4. 更新后的执行波次（**增量，不替换**上文 §A.5 与正文波次）

```
Wave-0（立即，总 ≈2 小时 + 1 天）— 不变
  ├── B02 守卫真断言（0.5 天）      ← 守卫先能失败，其余"验证通过"才有意义
  ├── B03 回收 EVO-072/073 + 版本对齐（0.5 天）＋ 与 B17 配套处置双份文件
  ├── B01 守护入调度 + kill→自愈验证（1 小时）+ 补执行位
  └── B04 未入库分批收口（0.5–1 天） ← 先入库再谈其他收口

Wave-1（可并行，P1）— 本轮新增 3 项
  ├── B15 stuck_score 恒真修复（0.5 天）        ← 独立
  ├── B16 重启互斥 + 归属告警（0.5 天）          ← 独立，对治 09-26 11:47–12:05 型事故
  ├── B17 双份 history 分叉消除 + 一致性守卫（0.5 天） ← 独立，治 D-03/D-05 共同根因
  ├── B05 跨环境一致性门禁（0.5 天）  ├── B06 钳位观测点/归因接线（0.5 天）
  ├── B12 复采 ≥6000 帧（1 天，需 SM64 可跑）├── P2-N2 契约审计增量（2 天，含 B07）
  └── A2 视觉重定位"验证/接线"（0.5–1 天，需活体可跑）

Wave-2（P2，与 Wave-1 并行）— 不变
  ├── B07（1 小时）├── B08（2 小时）├── B09（0.5 天）├── B10（0.5 天）
  ├── B11（2 小时）├── B13（0.5 天）├── B14（0.5 天）└── A1/P0-N1（1 小时）

阻塞项（不由本计划解除）
  └── H13 裁定 ⇒ P2/P3 整体阻塞（含 A5/P1-N2、P2-2、B2 断口、闭环转正式、SP5-B/SP6）
      解除条件：H13 需在真实数据下重新验证成立，且属项目级决策

顺序约束（新增）
  ├── B13（双根收集确认）必须早于任何"用 pytest 基线做验收"的动作
  ├── B04（入库）建议早于 P3-1（清理过时文档）
  └── B12（复采）完成前，不得声称"运动问题已解决"
```

### 5. 需用户决策的前置门（**本计划不代为决定**）

| ID | 事项 | 状态 |
|---|---|---|
| **U1** | 是否另建修复团队执行 `P0-a`(B03) + `P0-b`(B02) + `P0-c`(B01) + `P0-d`(B04) + `P1`(B15) | 操作者 **09-26 13:04:37 / 13:13 / 13:19:14 / 13:22:48 / 13:27:14 / 13:31:44 共询问 6 次**，快照结束**仍无答复** |
| **U2** | H13 阻塞是否维持 | 同上，随 U1 一并询问 6 次未答；已明确"分析团队无权解除" |

### 6. 反向证据（**真实成效**，不得只列困境）

| 成效 | 数值 | 限定 |
|---|---|---|
| gate 单位契约生效 | `gate_jump_ratio` 6 采样中 4 次 > 0.75；`forward_rate_hz` **3.85–15.38** | 🟢 实测（54 点采样方向一致） |
| WSLg 渲染修复有效 | `render_ms = 6.118` / `bridge age_ms = 16.59` | 🟢 **单点**快照 |
| 首次观测到 `jump` | `0/6000 → 113/6000 = 1.88%`；09-26 独立读数 24/1146、26/1722、10/318 | 🟡 有会话侧支撑；**精确对照仍需 B12** |
| 振荡陷阱缓解 | `ctrl_x` 交替 3404→43；静止帧 31.6%→6.4%；`stuck_score` 1.0→0.17；coverage 8.3%→28.4% | 🟠 **对照非同场景**；X/Z 效率与 `waste_ratio` 仍劣于基线 |
| 记忆与路径避免 | 来回振荡 **0 次**；新细胞率 41.4% | 🟠 **回访率 48%**、覆盖平台期 40–60% 无增长 |
| 25-P0-1 信用分配矩阵 | AST **134 写点 / 6 断口** | 🟢 |

> **三项必须保留的反向保留**：① 场景不严格可比；② `stuck_score` 假绿使"stuck 已消除"不可靠（先过 **B15**）；③ **B12 未完成前不得声称运动问题已解决**。

### 7. 下一阶段独立任务（**不强行收口**；细则见建议文档 §A.9 与 t3 §6）

| ID | 未验证项 | 归属 |
|:--:|---|---|
| **B-1** | 活体跳门是否**实际关闭**（WSL `3.082` 在 ratio 语义下的后果） | 运行时采样 |
| **B-2** | `P0-2`/`P0-4` 是否**在活体**（须符号存在性核对） | 代码级核对 |
| **B-3** | **`fly64/tests/check_version.py`** 的**作者与创建时间** | `git log --follow` |
| **B-4** | E1 / RC-1 的"报告自述"（作者会话不在导出集） | 补 09-25 21:00–21:18 导出 / 读文档原文 |
| **B-5** | CX-2 `relocalize()` **活体命中率** | 运行时统计（→ A2 的验证部分） |
| **B-6** | `gate_jump` 消费者 `scene_context.py:234` 是否**当前**仍读旧键、产物是否真零调用者 | 代码/调用图核验 |
| **B-7** | **双根 pytest 收集**、WSL 磁盘/日志规模 | 运行时/文件系统实测（→ **B13**） |
| **B-8** | `evo_loop_stale` 是否**最终**仍未发布 | 活体 `memory.json` 键 + `main.py` 发布点 |

### 8. 文档自洽校验

```powershell
python scripts/verify_doc_citations.py    # 必须 exit 0（建议文档 + 本计划 + 分析文档三份一起校验）
```

---

### 9. t6 返修勘误块（append-only；依据 `docs/analysis/newlogs-review.md` 的 F-1～F-10）

> **纪律**：本节**只追加**；与上文（含本附录第 1–8 节）冲突者**以本节为准**。未删除任何条目、未放宽任何表述。配套块见 `session-log-recommendations.md` §A.9.10。

| # | 级别 | finding | 处置 |
|:--:|:--:|---|---|
| 1 | **blocker** | **F-1** 域混用：`1826`（全快照）− `695`（窗口去重）≠ 重复副本 | 第 1 节已改为**三段式 + 声明域**：全快照域 `1826 / 1312 / 514`；窗口域 `1209 / 695 / 514`；窗口外 `617（无副本）`。**引用禁令**加入「任何减法必须两项同域」 |
| 2 | high | **F-2** gate 行号/语义：`model.py:2478` 仅 **@HEAD** 成立；工作区真实门在 **`model.py:2562-2566`**（ratio，`_jump_rate_ratio_gate=0.75` @ `model.py:678`） | 本计划正文的 gate 引用属 R1/R2 旧口径；**新增引用一律标 scope**。0.04-vs-0.043 论证按"迁移前历史论据"读 |
| 3 | high | **F-3** gain 位置：`model.py:1842` 是注释；实为 **4 处**（`1335/1849/1875/1906`）+ `main.py:3212` | 同上；**保留**子命题"注入腿只有一条带增益" |
| 4–5 | medium | **F-4** 87 处口径未声明；**F-5** 51 个未跟踪不可复现 | 第 1 节已补：write/edit **调用 126 / 逐快照唯一 (工具,路径) 87 / 全局唯一路径 63**；未跟踪 `??` 实测 **74**（剔除本轮 3 份新文档 **71**） |
| 6 | medium | **F-6** t2 自报 563 → 实测 **562**（**t5 核验时点**） | 第 1 节已补行并加时点标注（t2 在 t6 补注后现为 **569 行**）；正文无需改写（`563` 仅作为 inode 片段出现） |
| 7–9 | low | **F-7** §0.3"两项"→ 三项；**F-8** t3 O-/X- 编号映射；**F-9** `check_version.py` 全路径 | F-7/F-8 落在 `project-state-consolidated.md`（§0.3-4 与附录 A.2）；F-9 本附录 B-3 行已补 **`fly64/tests/check_version.py`** |
| 10 | low（跨文档） | **F-10**「差值恒为 11」不成立（实测 **68 / 32**） | 原文出自 `blindspot-review-round2.md:396`（**不在本任务 in-scope，未修改**）；第 1 节已登记更正行 |
| — | — | **t3 措辞**：「零处提及 EVO-072/073」 | 改写为「**提及 3 处（12:24:27 / 12:25:31 / 12:25:40），均未识别为待删对象**」；实质结论不变 |
| — | — | **pkill 计数**：「连续 6 轮」 | 改写为「**6 次 `write` 脚本轮次（11:54:25→12:02:59），实际执行 `pkill` 3 条（11:55:30 / 11:57:24 / 12:02:47）**」；归因结论不变 |

### 10. 文档自洽校验（t6 复跑）

```powershell
python scripts/verify_doc_citations.py    # exit 0（建议文档 + 本计划 + 分析文档三份一起校验）
```

---

> **本附录结束**。本附录为 2026-09-26 第三轮（一手会话）的 **append-only** 同步块；上文的 18 项、`B01`–`B14`、既有波次与 §A.0–§A.8 勘误块**一条未删、一条未放宽**。配套块见 `docs/analysis/session-log-recommendations.md` §A.9（含 §A.9.10 t6 返修块）；项目级合并结论见 `docs/analysis/project-state-consolidated.md`。
