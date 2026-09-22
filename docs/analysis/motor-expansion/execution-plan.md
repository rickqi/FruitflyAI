# 运动能力扩展 · 完整执行计划（汇总）

汇总：`bridge-bz-unlock.md`(R-A) · `cpg-motor-primitives.md`(R-C/R-D) · `neural-pools-extension.md`(R-B) · `dashboard-impact-assessment.md`

> **状态**: 🟢 已实现 (Implemented)  
> 此文档中的设计方案已编码实现并部署。实现详情参见对应代码文件与测试。
>

## 0. 交叉一致性检查（已核对）

| 接口 | t1 桥接 | t2 CPG | t3 神经池 | t4 监控 | 结论 |
|---|---|---|---|---|---|
| Control 字段 | `b, z` 参数 | 相位脚本输出 x/y/a/b/z | `b=strike, z=crouch` | `ctrl_b/ctrl_z` 遥测 | ✅ 命名一致 |
| decision_source | — | `cpg_primitive:<name>`（优先级 4.5） | — | explain() 新分支 M3 | ✅ |
| 新池遥测 | — | — | strike/crouch 池率 + gate 0.05/0.03 | 图表 6 曲线 M2 | ✅ |
| 神经接管 PIN | bridge.write_control 扩展（合法通路） | CPG 在 main.py 级联层写 control（与现有级联合法） | strike/crouch 经 LIF 电压注入，不直写 control | — | ✅ 无 Python 旁路 |
| mmap 版本 | extension[40] 预留区，不 bump version | — | — | — | ✅ 双向兼容 |

## 1. 分阶段执行计划（每阶段独立可验证、可回滚）

### Phase 1 — 桥接解锁（1 天）
1. `bridge.py`：Z_TRIG 常量、`write_control(z=)`、extension event counters
2. C patch：`b_frames/z_frames` 脉冲制 + Z_TRIG 透传；重编译 sm64ex
3. `main.py` Control 扩展 + write_control 调用；`replay.py` 可选参数
- **门禁**：`test_bridge.py` / `test_invariants.py` 全绿；实机 applied_buttons 位回读
- **BRAIN_VERSION → v2.14.0**

### Phase 2 — CPG 原语层（3 天，依赖 Phase 1）
1. `motor_primitives.py`：MarioState 状态机 + 7 原语相位脚本 + 2s 超时熔断
2. `main.py` 级联 4.5 层接入 + `primitive_disp` 记账
3. 先只启用 LONG_JUMP / BACKFLIP / GROUND_POUND（直击 ramp_trap 零位移）
- **门禁**：`test_motor_primitives.py`；实机验收 ramp_trap 场景首次非零逃逸位移（对照 README 5 次 0u 基线）
- **BRAIN_VERSION → v2.15.0**

### Phase 3 — 神经池 + MBON（2.5 天，可与 Phase 2 并行开发、Phase 2 后合入）
1. strike/crouch 池选址 + motor_splits 6 段 + 门控解码
2. CPG gate → LIF 电流注入；MBON 5→9 列 + 原语成败 dopamine 事件
- **门禁**：`test_model.py` / `test_mushroom_body.py` / `test_dan_shaping.py`
- **BRAIN_VERSION → v2.16.0**

### Phase 4 — 监控页面（1 天，M1–M4 必须；S1–S3 延后）
1. telemetry 加键（随 Phase 2 同步发）→ 前端 6 曲线 + explain() 分支 + /flow.json
- **门禁**：`test_dashboard_js.py` / `test_dashboard_protocol.py`；浏览器刷新目检 8 区块
- 前端资产热更新，无需重启

### Phase 5 — EVO 收编（0.5 天）
- `default_patterns.json` 追加 `primitive_timeout` / `primitive_zero_disp` pattern；fix_catalog 登记基线；Phase2 门禁 `scripts/phase2_gate.sh` 重新计时

**合计 ~6–8 天（含测试）；关键路径：Phase 1 → 2 → 5。**

## 2. 风险与回滚

| 风险 | 缓解 | 回滚点 |
|---|---|---|
| Z 键与人类玩家冲突 | 复用"人类摇杆优先"策略：pad 无按钮时才注入 | C patch 单文件 revert |
| 原语期间卡死 | 2s 超时熔断回退反射级联 | 级联层开关（active_strategy 白名单禁用） |
| pose 推断 SWIMMING 不准 | 先不上 SWIM_STROKE，留 Phase 6 | 原语白名单逐个启用 |
| 神经池选址过拟合 | 选址脚本一次性固化 + 正交性断言测试 | motor_splits 回退 4 段 |
| sm64ex 重编译失败 | `scripts/setup_sm64.sh` 一键重建 | 旧二进制忽略 extension，可继续用 |

## 3. 预期收益（对照 README 基线）

- 动作原语 5 → 12+；解码神经元 160 → 200（0.12%）
- ramp_trap：0u → 首个非零逃逸位移（EVO 长期目标）
- 锁门语义死角：PUNCH 原语为未来"拾取钥匙"闭环提供行为出口
- 全部改动遵守：神经接管 PIN（无旁路）、`.get()` 遥测兼容、BRAIN_VERSION 七步制度
