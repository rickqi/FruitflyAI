# 进化能力与教练能力提升路线图（可行性审核版）

> 状态：设计评审通过（2026-09-15/16，经代码级可行性再审）
> 基线数据：fix_catalog 18 条 fix，effective=0，均分 0.004 —— 检测/记录已工业化，**验证因果化是唯一 P0**
> 关键发现：`fly64/replay.py` 已具备**种子化确定性重仿真**基建（seed + PROJECTION_SEED=42 + 逐 tick control/spike 断言），反事实验证是加法而非新造

## 0. 可行性审核结论总表

| # | 建议 | 原方案 | 审核结果 | 修正后方案 | 依赖 |
|---|------|--------|---------|-----------|------|
| 1 | 验证因果化 | replay A/B 回放对比 | ✅ **升级**：replay.py 本就是确定性重仿真（`FlyModel(cache, seed)` + 逐 tick 断言），加一个 counterfactual 变体即可 | **开环反事实**：同一录制片段 + 参数覆盖重仿 → 对比净位移/脱离 tick。⚠️ 诚实边界：开环（世界不反应），验证"神经响应变了"，不保证闭环逃脱 | 录制需含 seed/frames/controls（现有 npz 已含） |
| 2 | pattern 级 KPI | 每 pattern 专属验证指标 | ✅ 直接可行 | PATTERN_SCHEMA 加 `verify_metric` 字段（key + direction + target），VerificationEngine 优先用它 | schema 演进（additive） |
| 3 | 配对分桶验证 | 同场景同触发条件对照 | ✅ 可行 | 触发时记录指纹（scene_id+anomaly_state），与同桶历史基线比 | escape 事件已有 scene 字段 |
| 4 | 生成型修复 | template→补丁提案 | 🔧 降级为"提案" | 产出 diff 草案 + PIN 测试草案，**人/agent 审查应用**（不自动 apply——连接组模型行为敏感，自动改码风险高） | 无 |
| 5 | DETECT 自动化 | 事件聚类→pattern 草案 | ✅ 可行（离线分析） | 对 escape 事件 + AUTO 记录做场景/异常态聚类，产出候选 pattern 草案文件，agent 确认后入库 | 数据已在（events/history） |
| 6 | 教练课程状态机 | curriculum 持久化 | ✅ 可行 | `active_strategy.json` 加 `curriculum` 段；**plugin 自己消费**（不依赖 brain 解析新键） | runner 读写逻辑 |
| 7 | 建议键级 outcome | 策略键效果归因 | ✅ 可行 | `write_strategy` 时快照上下文，下一 N 周期（runner 10s）读 memory delta 回写 | runner 周期即测量节拍 |
| 8 | 多信号触发 | 60s 标量→加权 | ✅ 可行 | `check_help_needed` 加权：stuck + reflex_ineffective + mban 饱和增速 + danger 场景 | runner 已聚合全部信号 |
| 9 | 教练上下文增强 | 喂进化病史 | ✅ 可行 | `build_consult_request` 加 evolution 段（最近 AUTO 记录/失败 fix/当前 findings） | 函数已存在 |
| 10 | CSC 性能 | — | ✅ 已立项 | P1-2（8–15ms/step），是**进化实验迭代速度**的前置 | 见 p1-2 分析文档 |

**审核发现的边界（诚实声明）**：
- 反事实重仿真验证的是"**神经响应改变**"，不是闭环逃脱保证（游戏世界不会对新控制做出反应）→ 闭环结论仍需 live 配对验证（方案 3）
- 精确重放对代码路径敏感：任何模型代码变更后，旧录制可能不再逐 tick 一致 → A/B 必须用**候选版本自己重录**的片段，或退化为统计性对比（N 次种子）
- `evolution_history.json` 目前多写入者（Windows 常驻循环 + 并行会话），AUTO id 撞号风险真实存在 → 单实例锁应先于方案 5 落地

## 1. P0：救活 0% 有效率（1–2 天）

### 1.1 开环反事实验证（新增 `replay.counterfactual`）

```python
# fly64/replay.py 新增（复用 verify 的装载逻辑，不 assert 而是度量）
def counterfactual(index: Path, cache: Path, overrides: dict | None = None,
                   metrics: Callable[[FlyModel], dict] | None = None) -> dict:
    """同帧序重仿真，参数覆盖前后对比神经响应。

    overrides: {"tonic_current": .., "breakout_gain": .., "y_min": ..} 等 setattr 级参数
    返回: {"displacement": ..., "escape_tick": ...|None, "mean_forward_rate": ...}
          —— 度量=净位移 / 首次脱离异常的 tick / 运动池率曲线
    """
```

- fix_template 中**参数级修复**（历史上 80% 是：阈值/增益/权重）直接可用
- 验收：对 AUTO-0003（Y 阈值 −100→50）做反事实——同一段 fallen 录制，阈值改后模型应输出恢复控制；对 AUTO-0002 做 DAN 衰减前后 MBON 轨迹对比

### 1.2 pattern 级 verify_metric

```json
{"id": "mbon_saturation", "verify_metric": {"key": "mb_saturation_events", "direction": "rate_down"},
 "id": "micro_loop_weave", "verify_metric": {"key": "net_displacement_60s", "direction": "up"}}
```

`VerificationEngine` 优先读 pattern 的 `verify_metric`，无则回退全局 stuck/coverage。旧 10 条 0 分 fix 用新指标重验一遍。

### 1.3 配对分桶（live 侧）

`start()` 时记录指纹 `{scene_id, anomaly_state, terrain}`，`tick()` 判定时只在**同桶**内比较（跨桶 → 判 `inconclusive`，不算 ineffective）。消除"切场景误杀"。

## 2. P1：教练从工具到老师（2–3 天）

### 2.1 建议键级 outcome（数据地基）

```python
# plugin/strategy_writer.write_strategy 时追加
snapshot = {"keys": strategy, "scene_id": ..., "anomaly": ..., "stuck": ...,
            "health": ..., "disp_60s": ...}
# runner 下一个/下三个周期读 memory.json，回写 delta → skills/coach_outcomes.jsonl
```

产出 `场景 × 策略键 → 效果分布` 表；这是 P4.4 本能化与 P4.6 社交评分的共同地基。

### 2.2 课程状态机（P4.3）

```json
"curriculum": {
  "course": "escape-lava-field", "stage": 2,
  "goal": "对峙<20s 且位移>30u", "attempts": 3,
  "history": [{"advice": "turn_bias=0.6", "outcome": "no_change"}]
}
```

coach 每次咨询先读 curriculum（`runner` 注入 prompt），建议后自评是否达标并推进/回退阶段。存 `skills/curriculum.json`。

### 2.3 多信号加权触发（替代 60s 标量）

`check_help_needed` 改为 score = w1·stuck_norm + w2·reflex_ineffective + w3·saturation_rate + w4·scene_danger，阈值可调；保留 60s 作为保底下限。

### 2.4 教练上下文增强

`build_consult_request` 注入 `evolution_context`：最近 5 条 AUTO 记录、当前 findings、验证失败的 fix——教练从"看照片"到"看病史"。

## 3. P2：元进化与吞吐

- **单实例锁**（前置）：`locked_launcher` 模式治理双写
- **DETECT 聚类**：escape 事件 + AUTO 记录 → 候选 pattern 草案（`skills/pattern_drafts/`，agent 确认入库）
- **元指标漏斗**：每轮统计 检出→记录→落地→有效→本能化 五级转化率，进 `--history-md` 与仪表板
- **CSC 优化**（P1-2）：活跃边集/分块调度——tick 提速 = 验证窗口迭代提速

## 4. 验收标准（每阶段）

| 阶段 | 验收 |
|------|------|
| P0 | 对 AUTO-0002/0003 两个真实案例产出反事实报告；≥1 个 fix 在 verify_metric 下判"有效"；0.3 全局阈值退役为参考项 |
| P1 | coach_outcomes.jsonl 积累 ≥20 条键级 outcome；同场景咨询率可统计；加权触发上线（60s 保底不变） |
| P2 | 单实例锁上线；候选 pattern 草案自动化产出 ≥1 条被采纳；漏斗五级转化率进仪表板 |

## 5. 明确不做（边界重申）

- 不自动 apply 代码补丁（人/agent 审查制不变，规则 15 与 PIN 套件是安全网）
- 不把 LLM 语义下沉进果蝇回路（教官层只发调制信号/原语建议）
- 不承诺开环反事实 = 闭环逃脱（闭环结论以 live 配对验证为准）
