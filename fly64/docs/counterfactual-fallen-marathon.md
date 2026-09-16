# 反事实报告 #1 — fallen 马拉松（幽暗洞穴，stuck 400s+）

- 分块: `/tmp/f64r_traj-00059.npz`（500 ticks，schema 3，实况录制）
- 方法: `replay.counterfactual` 开环重仿真（同帧序、参数覆盖、种子一致）
- 通道: baseline（escape_jump_drive=off）→ 现行（forward 0.20 / jump 0.60）→ 强化（forward 0.50 / jump 1.00）

## 数据

| 指标 | baseline | 现行 | 强化 | 强化 vs baseline |
|------|---------:|------:|------:|-----------------|
| jump_count | 13 | 13 | 13 | 0% |
| mean_y（前进） | 62.44 | 62.44 | **64.71** | +3.6% |
| mean_abs_x（转向） | 4.19 | 4.19 | **0.20** | **−95%** |
| mean_abs_mbon | 0.944 | 0.944 | 0.944 | ≈0 |
| dopamine_mean | 0.292 | 0.292 | 0.294 | +0.6% |

（baseline 与"现行"完全一致为预期：录制本身发生于 escape_jump_drive=True 的实况中，重放设 True 不产生增量）

## 机制结论

1. **振幅不是约束，方向才是**：fallen forward 电流放大 2.5× 只换来 +3.6% 前进输出，却把转向几乎完全抹平（|x| 4.19→0.20）——更强的前向电流经 LIF 竞争**压制了转向池**，马里奥会"更用力地直线冲进虚空"。
2. **跳跃通道对电流增幅不敏感**：jump_count 恒 13，说明跳跃门控由输入特征（gold spot/opening）而非电流振幅驱动——`_fallen_jump_boost` 翻倍在此场景无效果。
3. **MBON/多巴胺对电流振幅无感**（0.944/0.292 持平）——该失败模式的可塑性调制通道未激活，R13b 挫折 DA 已在惩罚但不足以改变响应。

## 可执行建议（按优先级）

1. **fallen 恢复保留转向交替**：`_fallen_forward` 增益前，先让 `bold_direction()` 交替在 fallen 期间持续提供方向信号（当前前向电流压制了转向竞争）——候选实现：fallen 期间 `_fallen_forward` 与转向交替**分时**而非同时注入。
2. **振幅调参降级**：`_fallen_jump_boost`/`_fallen_forward` 的继续加大收益有限（+3.6% 前进 vs −95% 转向），不建议作为下一步。
3. **对照实验**：live 验证建议 1（closed-loop），verdict 记入 `coach_outcomes.jsonl`。

## 边界

开环反事实：世界不对新控制做出反应。结论是"神经响应层面"的，闭环逃脱需 live 配对验证（上表建议 3）。
