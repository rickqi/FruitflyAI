# Fly64 项目当前挑战根因分析与行动建议

> **来源**: fly64-challenge-analysis 团队三项并行深度分析  
> **分析师**: analyst-a (EVO) / analyst-b (FlyGym) / analyst-c (视觉)  
> **日期**: 2026-09-21  
> **脑模型版本**: Fly64 v2.23.11 · 166K LIF神经元 · 151.9M突触 · MaleCNS v1.0  

---

## 目录

- [概览：三项挑战的风险排序](#概览三项挑战的风险排序)
- [🔴 P0-A: EVO auto-fix 常驻运行根因分析](#-p0-a-evo-auto-fix-常驻运行根因分析)
- [🔴 P0-B: FlyGym 端到端集成根因分析](#-p0-b-flygym-端到端集成根因分析)
- [🟡 P1-A: 视觉覆盖度提升方向分析](#-p1-a-视觉覆盖度提升方向分析)
- [综合路线图与优先级建议](#综合路线图与优先级建议)

---

## 概览：三项挑战的风险排序

| 排名 | 挑战 | 风险等级 | 关键发现 | 预估工作量 |
|------|------|---------|---------|-----------|
| 🥇 | **P0-A EVO auto-fix** | 🔴 高 | 存在 **8 项阻塞级问题** 需要修复 | 3-5 天 |
| 🥈 | **P0-B FlyGym 集成** | 🔴 高 | 视觉适配器压缩比 691200:1，信息完全丢失 | 8-11 天 |
| 🥉 | **P1-A 视觉覆盖度** | 🟡 中 | 颜色通道 ≈95% 已完成，可直接启用 | 1 天 |

---

## 🔴 P0-A: EVO auto-fix 常驻运行根因分析

### F1: FixExecutor 模板覆盖缺口 (影响面: 🔴 全局)

**现状**: FixExecutor 仅支持 4 种结构化指令格式（replace/insert_after/insert_before/append）

**影响**: `default_patterns.json` 中 **12 个 pattern 有 8 个（66.7%）** 的 fix_template 是纯自然语言描述，FixExecutor 解析后全部降级为 `manual_action_needed=True`，无法自动执行。

**被降级的 pattern**:
| Pattern | 当前修复格式 | 能否自动执行 |
|---------|-------------|------------|
| cliff_standoff | 纯自然语言描述 | ❌ |
| fallen_recovery_stuck | 纯自然语言描述 | ❌ |
| micro_loop_weave | 纯自然语言描述 | ❌ |
| mbon_saturation | 纯自然语言描述 | ❌ |
| dopamine_plateau | 纯自然语言描述 | ❌ |
| reflex_cooldown_gap | 纯自然语言描述 | ❌ |
| suspended_animation | 纯自然语言描述 | ❌ |
| mb_learning_stalled | 纯自然语言描述 | ❌ |

**根因**: FixExecutor 不支持 `# Files:`（复数多文件语法）、`# Change:# To:#` 的查找-替换二段式、`# Insert` / `# Add after` 等变体。

**建议修复**:
1. **[P0] 建立 `FixTemplateInterpreter` 组件**: 对 `manual_action` 模板使用 LLM 辅助解析为结构化指令（通过 subagent 调用）
2. **[P0] 补全 FixExecutor 语法支持**: 添加 `# Change:# To:#` / `# Files:` 多文件语法 / `# Add after` 变体
3. **[P1] 迁移自然语言模板**: 逐步将所有 8 个降级 pattern 的模板改写成结构化格式

---

### F2: 竞态条件与行号漂移风险 (影响面: 🔴 关键)

**风险项**:

| 风险 | 等级 | 说明 |
|------|------|------|
| 单次替换不精确 | 🔴 高 | `content.replace(find_text, replace_text, 1)` 若同一模式出现多次会误替换 |
| dashboard 数据竞态 | 🟡 中 | `DataCollector.fetch_all()` 顺序调用 4 个 HTTP 端点，非同一时刻快照 |
| 行号漂移 | 🔴 高 | FixExecutor 完全不依赖行号，全凭子串模糊匹配——多轮迭代修复后文件已变，第二轮 `find_text` 可能不匹配或匹配到错误位置 |
| 锁绕过风险 | 🟡 中 | `--no-lock` 参数可绕过单例保护，双进程并发编辑同一文件 |

**建议修复**:
1. **[P0] 实现 Git 式冲突检测**: 执行替换前使用 `git diff` 或语义行匹配检查目标文件是否已被其他修复修改过
2. **[P1] 添加可选的行号锚定支持**: `# Line: <int>` 指令，FixExecutor 校验替换位置时验证目标行附近上下文一致性

---

### F3: fix_catalog.json 写入锁定与并发安全性 (影响面: 🔴 关键)

**现状**: `FixCatalog.save()` 使用 `path.write_text(json.dumps(...))` 直接写入，虽已实现 tmp+replace 原子写入模式，但:
- **无进程级文件锁**: 两个 EVO 实例同时执行 `record_fix()` 时，后写入者完全覆盖前写入者结果
- `load()` 在写入前从磁盘重新读取全量数据，非内存增量——多线程/多进程场景下出现 classic "read-modify-write" 竞争
- `VerificationEngine.save_state()` 和 `FixCatalog.save()` 之间无事务保证

**建议修复**:
1. **[P0] 实现进程级写入锁**: 为所有写文件操作实现 `fcntl.flock()`（Windows 上等效 `msvcrt.locking()`），或移入单一序列化写入线程
2. **[P1] 增量修复记录**: `FixCatalog.save()` 改为仅追加新记录而非全量重写（保留 tmp+replace 保障写入原子性但减少 I/O）

---

### F4: 24h 持续运行的性能退化风险评估 (影响面: 🟡 中高)

| 组件 | 风险等级 | 原因 |
|------|---------|------|
| `DataCollector.samples` (deque, maxlen ~2400) | 🟢 低 | 固定窗口 120s，deque 有界 |
| `HealthTrendCollector._cache` (deque, maxlen 200) | 🟢 低 | 有界 |
| `EvolutionHistory._records` | 🟡 中高 | 无上限。每次迭代仅追加不裁剪，24h (~28800 次迭代) 产生约 5-10MB JSON 文件 |
| `evolution_log.jsonl` | 🟡 中 | 行式追加无旋转，24h ~2000-5000 行 |
| `BrainMutator._trial_history` | 🟡 中 | 无限制追加，但 ~28800 迭代中仅小部分启动试验 |
| `FixCatalog.fixes` | 🟢 低 | ~19 条，增长极慢 |
| `SelfDocumenter` 每次迭代生成整篇 README | 🟡 中高 | 每次迭代都完整重写 README（~200 行），写放大 |
| `FixCatalog.save()` 每次 record_fix 完整序列化 | 🔴 高 | 每次修复记录都 JSON 序列化全部 ~19-100+ 条记录（随运行时间增长），无增量写入 |
| `HealthTrendCollector` 每次迭代追加 JSONL + `json.dumps` | 🟡 中 | 24h 约 28800 行写入，性能线性退化（无日志旋转/截断） |

**建议修复**:
1. **[P1] 历史记录旋转与归档**: `EvolutionHistory` 追加达到阈值（如 1000 条）后自动旋转存档 `evolution_history.N.json`，防止完整序列化性能退化
2. **[P1] 增量 README 更新**: 仅在发生修复记录变更时调用 `SelfDocumenter.update()`，而非每次迭代
3. **[P2] 迭代级健康看门狗**: 在迭代耗时超过 3 倍 interval 或 `FixExecutor` 连续失败 ≥3 次时自动暂停 loop 并触发告警

---

### F5: 备份/回滚机制在迭代场景中的可靠性 (影响面: 🟡 中)

**备份机制评估**:
- FixExecutor 在每次编辑前创建 `.bak` 备份，命名策略 `path.suffix + ".bak"`（冲突时加时间戳后缀）——对单个文件多次修复时可能生成大量 `.bak.yyyyMMddHHmmssffffff` 冗余文件
- 备份存储在与源文件相同目录，长期运行可能导致目录膨胀（24h × 12 次迭代/h × 每次编辑~1-3 个备份 ≈ 288-864 个备份碎片文件）
- `rollback()` 基于 FixExecutionReport 的 action 级备份路径进行逐文件还原，操作正确但需调用方记录和传递历史报告。自动修复管线 (`run_one_cycle`) **不保留历史 report 列表**（仅暂存在 result.fix_execution_reports 中），迭代后丢失导致 `rollback()` 不可用
- 备份还原非原子（先读 .bak → 写目标文件 → 删 .bak），中途崩溃可能导致部分还原或文件损坏

**建议修复**:
1. **[P1] 会话级迭代报告暂存**: 保留最近 N 个 FixExecutionReport 以便调用方在检测到错误时可执行 `rollback()`
2. **[P2] 备份目录隔离**: 将 `.bak` 文件写入单独的 `.evo_backups/` 目录而非源目录，避免源目录污染 + 提供统一清理策略（保留最近 24h）

---

## 🔴 P0-B: FlyGym 端到端集成根因分析

### G1: FlyGym 版本兼容性 (影响面: 🟢 低)

**现状**: 系统当前安装的是 `flygym==1.2.1`。当前 `FlyGymBrainEnv` 使用的 API 在 v1.2.1 上完整可用:
- ✅ `flygym.Fly(enable_vision=..., render_raw_vision=...)`
- ✅ `flygym.SingleFlySimulation(fly=..., arena=..., timestep=...)`
- ✅ `.reset(seed=...)` / `.step(action=...)` 兼容 Gym API
- ✅ `.close()` 
- ✅ `info['raw_vision']` 可用，shape `(2, 512, 450, 3)`

**结论**: v1.2.1 不构成阻塞。迁移到 v2.x 需验证 `raw_vision` 键名和 `step()` 返回值签名是否变化，但风险可控。

---

### G2: CpgGait/FlyGymBrainEnv ↔ SM64 脑模型切换缺口 (影响面: 🔴 阻塞)

**现状架构**:
```
main.py 主循环
  ├── SM64 Bridge: bridge.read_frame() → model.step() → bridge.write_control()
  └── FlyGymBrainEnv: 独立环境，未集成到主循环
```

**缺口**: `CpgGait`/`FlyGymBrainEnv` 与 SM64 脑模型实例之间 **没有任何实时切换机制**——缺少 `VisionSource`/`MotorTarget` 抽象接口。

**根因**:
1. `main.py` 主循环硬编码 `bridge.read_frame()` 作为视觉输入源，没有抽象成可替换的 `VisionSource` 接口
2. 运动输出硬编码 `bridge.write_control()`，没有抽象成可替换的 `MotorTarget` 接口
3. 两个环境（SM64/FlyGym）的视觉格式完全不同（SM64: 1536 点预采样亮度 vs FlyGym: 2×512×450×3 RGB 原始帧）
4. 两个环境的控制维度完全不同（SM64: 2 自由度 x/y vs FlyGym: 42 关节角度）

**建议修复**: 
- **[P0] 实现 VisionSource 抽象层**: `protocol.py` 中添加 `VisionSource`（`read_frame() → np.ndarray`）和 `MotorTarget`（`write_control(control: np.ndarray)`）接口
- **[P0] 实现 SM64Bridge → VisionSource 适配器**: 将现有 `bridge.read_frame()` 包装为 VisionSource
- **[P0] 实现 FlyGymBrainEnv → VisionSource 适配器**: 将现有 `env.step()` + `flygym_to_luminance()` 包装为 VisionSource
- **[P0] 实现对应的 MotorTarget 适配器**: SM64 的 2-DOF 和 FlyGym 的 42-DOF 分别适配

---

### G3: 视觉适配器评估 (影响面: 🔴 阻塞)

**当前实现**: `flygym_to_luminance()` 将 `raw_vision (2×512×450×3)` 压缩为 `2 个 float`（每眼平均亮度）

**压缩比**: `691200 → 2 = 345600:1`（每像素）

**丢失的信息**:
| 丢失信息 | 重要性 | 影响 |
|---------|--------|------|
| 所有空间结构 | 🔴 致命 | 1536 点视网膜无法重建空间采样 |
| 所有颜色信息 | 🔴 致命 | 颜色/UV 通道完全不可用 |
| 所有运动信息 | 🔴 致命 | 帧间差消失，EMD 无法工作 |
| 双眼视差 | 🔴 致命 | 立体深度估计不可用 |
| 纹理/图案 | 🔴 致命 | 地形分类、场景识别全部失效 |

**根因**: 当前适配器使用了错误的抽象层级——将完整的视觉帧压缩为 2 个标量亮度值，丢失了视网膜处理所需的所有信息。实际上，1536 点视网膜采样应直接作用于视觉输入的像素级数据，而不是作用于一个已经丢失空间结构的平均值。

**建议修复**:
1. **[P0] 实现空间下采样适配器**: 将 `2×512×450×3` 帧通过双线性/步进采样降采样到 Fly64 的 1536 点视网膜采样格式，保留亮度/颜色/运动信息
2. **[P0] 直接集成到 compute_emd**: 使 EMD 检测器直接从降采样后的视网膜信号读取帧间差异，而非从两个平均亮度值

---

### G4: 控制流集成方案 (影响面: 🔴 阻塞)

**当前**: `main.py` 主循环硬编码：
```python
bridge.read_frame()    # SM64 输入
model.step(frame, ...) # 脑模型处理
bridge.write_control() # SM64 输出
```

**缺口**: 无适配器模式封装，切换环境需直接修改 `main.py` 核心逻辑。

**建议修复**: 实现环境选择开关（`--env sm64` / `--env flygym`），通过统一 VisionSource+MotorTarget 接口切换，不侵入主循环逻辑。

---

### G5: 测试覆盖缺口 (影响面: 🟡 中)

**当前**: 24 个测试全部是单元级别

**8 个关键集成测试缺口 (TC1-TC8)**:
| TC | 测试内容 | 优先级 |
|----|---------|--------|
| TC1 | VisionSource 适配器接口一致性 | P0 |
| TC2 | SM64 Bridge → VisionSource 包装 | P0 |
| TC3 | FlyGym env → VisionSource 包装 | P0 |
| TC4 | 从 SM64 切换到 FlyGym 不破坏运行 | P0 |
| TC5 | FlyGym 端到端: reset → N 步运行 | P1 |
| TC6 | 两种环境下脑模型行为一致性 | P1 |
| TC7 | 视觉适配器保真度: 压缩后信息保留 | P1 |
| TC8 | CpgGait 步态在脑模型控制下的行为 | P2 |

---

### G6: 端到端实施路线图

| 阶段 | 行动 | 预估工作量 |
|------|------|-----------|
| **Phase 1**: 抽象层 | 实现 VisionSource/MotorTarget 协议 + SM64/FlyGym 适配器 | 3-4 人天 |
| **Phase 2**: 完整 FlyGym 适配器 | 空间下采样视觉适配器 + 主循环开关 + 42-DOF 控制映射 | 3-4 人天 |
| **Phase 3**: 测试与 CI | TC1-TC8 集成测试 + CI 流水线 + 回归基线 | 2-3 人天 |
| **合计** | | **8-11 人天** |

---

## 🟡 P1-A: 视觉覆盖度提升方向分析

### H1: 三个候选方向的生物基础与实现状态

| 方向 | 生物基础 | Fly64 实现状态 | 剩余工作量 |
|------|---------|---------------|-----------|
| **🎯 颜色/UV 通道** | R7(Rh3/Rh4 UV≈340nm) + R8(Rh5 蓝≈440nm / Rh6 绿≈520nm) + Medulla Ct1/Ct2 拮抗 | **≈95% 完成**: encode_color() 完整实现 + 4 通道 RGBA + 拮抗通道 + HSV + sky_blue_index + danger_red_index + 8 扇区色相分布。model.py 驱动公式已融合红/UV/绿显著项 | **~1 天** (验证 + 场景签名兼容性) |
| **🎯 小目标追踪** | LPLC1/2 + LC11 神经元检测运动小目标 (<5°) | **≈80% 完成**: compute_small_targets() 完整实现 + TargetTracker + 匈牙利匹配卡尔曼滤波。但 **LIF 分裂注入修复尚未验证** | **~2-3 天** (验证修复 + 行为层测试) |
| **🧠 多巴胺学习** | 蘑菇体: PN→KC(2000, 5%稀疏)→MBON(34路) + 三因子赫布学习 | **≈85% 完成**: MushroomBody 模块完整实现（~650行）+ 三因子学习规则 + 代理奖赏信号。但 **P0-2 MBON 饱和 + P0-3 阈值错误** 阻塞启用 | **~3-5 天** (修复 P0 错误 + 启用全栈测试) |

---

### H2: 推荐方向——颜色/UV 通道 (R7-a)

**原因**:
1. **风险最低**: ≈95% 实现已完成，零额外依赖，仅需验证启用
2. **覆盖度提升**: 加权覆盖度 **+6.5%**（基于 FlyWire 神经类型计数）
3. **通用性强**: SM64（不同颜色平台/敌人）+ FlyGym（不同颜色光照/背景）均可受益
4. **实施极快**: 估计仅需 1 天即可完成验证并启用

**实施计划**:
```
R7-a: 颜色管道验证启用 (1 天)
  ├── Day 1: 验证 encode_color() 在当前测试套件下正常运行
  ├── Day 1: 验证场景签名兼容性（SM64 + FlyGym 双场景）
  ├── Day 1: 启用默认 color_signature=True
  └── Day 1: 添加 5+ 颜色相关回归测试

并行工作包:
  ├── P0-2 MBON 饱和修复
  ├── P0-3 阈值错误修复
  └── LIF 分裂注入修复验证

R8: 小目标追踪行为验证 (2-3 天) — 依赖 LIF 修复完成
R9: 多巴胺学习全栈测试 (3-5 天) — 依赖 P0-2 + P0-3 修复完成
```

---

## 综合路线图与优先级建议

### 执行顺序

```
Week 1 (P0 阻塞项)
  ├── P0-A: EVO auto-fix 常驻运行
  │   ├── Day 1-2: 自然语言 fix_template LLM 辅助结构化 (P0)
  │   ├── Day 2-3: 实现进程级写入锁 + Git 式冲突检测 (P0)
  │   └── Day 3-5: 历史记录旋转 + 增量 README + 健康看门狗 (P1)
  │
  ├── P0-B: FlyGym 端到端集成
  │   ├── Day 1-2: VisionSource/MotorTarget 抽象层 + 适配器 (P0)
  │   ├── Day 3-4: 空间下采样视觉适配器 + 主循环开关 (P0)
  │   └── Day 5: 集成测试 TC1-TC8 + CI (P1)
  │
  └── P1-A: 颜色/UV 通道 (R7-a)
      └── Day 1: 验证并启用 (P1)

Week 2 (P1 项)
  ├── 并行: R8 小目标追踪行为验证 (2-3 天)
  └── 并行: R9 多巴胺学习全栈测试 (3-5 天)
```

### 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| EVO auto-fix 常驻运行后发现更多模板兼容问题 | 🟡 中 | 🔴 高 | 先对小样本运行 2h 验证，再逐步扩大 |
| FlyGym v1.2.1 视觉管线接口不符合预期 | 🟡 低 | 🔴 高 | 先做 API 探测性测试再进入实现阶段 |
| 颜色管道启用后导致 SM64 行为退化 | 🟢 低 | 🟡 中 | 启用前后对比 regression 测试基线 |
| 多巴胺学习 P0 错误修复延迟 | 🟡 中 | 🟡 中 | 可先发布 R7-a + R8，多巴胺学习独立安排在后续迭代 |

---

## 总结

**核心信息**: 经过三轮深度根因分析，三个挑战分别存在 **8 项、6 项、3 项** 阻塞/高风险因子。建议按以下策略推进:

1. **立即启动 (P0)**: EVO auto-fix 的 LLM 辅助模板解释器 + 并发写入锁（预估 2-3 天）
2. **立即启动 (P0)**: FlyGym 的 VisionSource/MotorTarget 抽象层 + SM64 适配器（预估 3-4 天）
3. **并行推进 (P1)**: 颜色/UV 通道启用（预估 1 天）
4. **后续迭代**: 小目标追踪 + 多巴胺学习修复启用

---

> **生成日期**: 2026-09-21  
> **基于**: fly64-challenge-analysis 团队三项并行深度分析  
> **对应脑模型版本**: Fly64 v2.23.11  
> **报告保存位置**: `docs/analysis/next_challenge_analysis_report.md`  