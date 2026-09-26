# A4 · Fly64 脑模型「自治 / 自进化」表面盘点与生效性判定

> 任务: t1 — 盘点脑模型自治与自进化表面（交付：含文件:行号与生效性判定的清单）
> 作者: brain-architect (agent team `fly64-autonomy-evolution`)
> 判定基线（代码冻结点）: `fly64/fly64/main.py` mtime 2026-09-23 23:34；`memory.py` 2026-09-22 23:59；
> `model.py` 2026-09-23 17:30；`central_complex.py` 2026-09-22 16:01；`mushroom_body.py` 2026-09-18 17:16；
> `gain_modulation.py` 2026-09-14 03:26；`instinct_bindings.py` 2026-09-17 20:41（`git log` HEAD = `cca6664`）
>
> 判定等级
> | 标记 | 含义 |
> |---|---|
> | ✅ 生效 | 有生产者、有消费者、有可达的运行点，且实测/代码可证其作用于行为 |
> | ⚠️ 生效但被门禁收窄 | 通路存在且会被调用，但阈值/优先级/单位/前置条件把它压到极窄区间 |
> | ❌ 已接线但结构上不可达 | 生产者与消费者都在，但存在一个恒真/恒假条件使它在当前运行点永不触发 |
> | ⛔ 死写入 / 死代码 | 无消费者（写入无人读）或无生产者（读取永为空），或不含任何调用点 |

---

## 0. 结论速览（先给可执行的判定）

| # | 表面 | 位置 | 判定 |
|---|---|---|---|
| S1 | 多巴胺门控通路增益（三因子） | `gain_modulation.py:121-223`；`model.py:727,1754-1767,1837-1842` | ✅ 生效（阈值 0.15 与 `[GAIN_MIN 0.5, GAIN_MAX 2.5]` 两端**均实测可达**）；⚠️ 但只作用于「连线体突触电流」一条腿 |
| S2 | jump 通路的增益表达 | `model.py:1787,1842` | ⚠️ 增益被读取，但学习到的跳倾向（MBON→jump）走的是固定常数 `mbon_gain_jump=0.35`，**绕过增益** |
| S3 | jump 动作触发门 | `model.py:2478` | ❌ 结构上不可达（当前运行点）：门限 0.04/tick 与前向池满速 0.043/tick 同量级 |
| S4 | jump eligibility（可塑性记账） | `gain_modulation.py:53,162`；`model.py:1716-1718` | ⚠️ 门槛比行为门更严（需单 tick ≥2/20 神经元），且奖励脉冲路径要求跳池先发放 → 闭环死锁 |
| S5 | MB 价值学习（KC→MBON） | `mushroom_body.py:172-415` | ✅ 生效（`assoc_count` 增长、权重列实测变动、`|dop|≥0.3` 常态满足） |
| S6 | MB 自适应学习率 `lr_adapt` | `mushroom_body.py:350-360` | ⛔ 死代码：`set_adaptive_lr()` 全仓库无调用点（仅测试），`lr_adapt` 恒为 1.0 |
| S7 | MB 异常消解记忆（场景+动作→召回） | `mushroom_body.py:513-539`；`main.py:2693-2699` | ⛔ 死代码：守卫读 `model._kc_activity`，该属性**全仓库无写入点** → `getattr` 恒 None |
| S8 | MB 场景迁移 warm start | `model.py:1194-1199`；`mushroom_body.py:480-511` | ✅ 生效（场景变化且距上次 >1500 tick 时调用） |
| S9 | MB 饱和稳态（R17/t27） | `mushroom_body.py:235-276` | ✅ 生效（`steep_scaling_events`、`saturation_events` 实测非零） |
| S10 | CX 航向罗盘 + 路径积分 | `central_complex.py:392-577`；`model.py:2082-2101` | ✅ 生效 |
| S11 | CX 多源目标竞争（指向/转向） | `central_complex.py:221-317` | ✅ 生效；⚠️ 输出幅度被两步小增益压到 ≤0.018 V/tick |
| S12 | CX 目标注入 → 转向电流的增益旋钮 | `main.py:1848`；`central_complex.py:192,198,314` | ⛔ 死写入：写在 `CentralComplex` 上，读的是 `_goal_comp.steering_gain`（探针实测 0.12 不变） |
| S13 | CX 环路突破（环行破锁，EVO-057） | `central_complex.py:294-306`；`main.py:1850` | ❌ 结构上不可达 + ⛔ 旋钮死写入：`_no_goal` 依赖 `_ext_goal_strength`，而覆盖率目标向量恒存在使其恒 ≥0.05（探针实测 4000 tick 触发 0 次） |
| S14 | 本能绑定晋升（场景→本能） | `instinct_bindings.py:257-339`；`main.py:1682-1698` | ❌ 已接线但未达门槛：线上库 2 个签名各 `improved=1` < `PROMOTE_MIN_IMPROVED=2`，`get_binding()` 恒 None |
| S15 | 本能绑定参数与钳位的一致性 | `instinct_bindings.py:87-91`；`main.py:1102-1105` | ❌ 潜在不可达：库内 `turn_bias=0.6/0.7` 落在 `CLAMP_BOUNDS(0.0,0.25)` 之外，一旦晋升会被自愈改写 |
| S16 | `active_strategy.json` 600-tick 热重载（教练/EFO 参数自治） | `main.py:1677-1743` | ✅ 生效（含钳位可见化 + 回写自愈） |
| S17 | 参数钳位（R31-fix12 振荡护栏） | `main.py:1102-1202,1742-1753` | ✅ 生效；⚠️ 它同时把教练 `turn_bias` 压到 0.25 上限 |
| S18 | 逃逸行为门 `escape_behavior` | `memory.py:2183-2191` | ✅ 生效（`fallen` 无条件、`stuck_score≥0.8` + 探索模式等） |
| S19 | 卡的检测 `StuckDetector` | `memory.py:122-232`；`main.py:2650` | ❌ 单位契约缺陷：传入 per-tick 比例，阈值按 Hz 声明（5.0），恒真 → `stuck_score` 结构性钉在 1.0 |
| S20 | 运动状态机优先级 | `memory.py:1347-1373` | ✅ 生效（fallen > micro_loop > oscillating > wall_stuck > stuck_ramp > idle） |
| S21 | 反射控制器 + 4 条反射 | `memory.py:1598-1732,1784-1852` | ⚠️ 生效但需要异常状态 + 置信度≥0.6；观察窗口内未取得操纵权（见 §5） |
| S22 | oscillating 反射的 jump（唯一常规反射跳） | `memory.py:1809-1816` | ⚠️ 生效但依赖 `anomaly=oscillating` 且位移门放行 |
| S23 | `bold_direction()` 自发交替转向 | `memory.py:1662-1674`；`main.py:2124-2125` | ⚠️ 生效（但**每次调用即翻号**，实际是逐 tick 抖动而非"交替相位"） |
| S24 | 强制大胆探索门 `forced_bold_explore` | `memory.py:2079-2105` | ❌ 结构上不可达（当前运行点）：需要"同一异常连续 ≥`bold_explore_stuck_s`"（默认 60 s），报告 run 的 `anomaly_duration=11.14s` 反复重置 |
| S25 | 探索死锁 burst（前冲冲击） | `main.py:2039-2086`；`memory.py:1189-1220` | ✅ 生效（前置条件）；⛔ `_last_burst_tick` 只读不写 → 防重入守卫是空操作；❌ 且 burst 期间强制 `control.jump=False` |
| S26 | 动作熵（固定模式环路破解） | `main.py:732-762,2569-2578` | ⚠️ 生效但门禁苛刻（novelty<0.1 且 loop>0.7），且只抖动 x/y，不碰 jump |
| S27 | 前向池占用稳态（T2/T8） | `model.py:1452-1475,682-697` | ✅ 生效（MBON 腿 + 辅助腿合计上限 0.20 V/tick） |
| S28 | 转向回路疲劳/反驱动 + 突破（R14/R16） | `model.py:345-392,1477-1520,2132-2166` | ✅ 生效（幅度 ±0.18 / ≤0.85 V/tick，量级主导转向竞争） |
| S29 | CPG 运动原语（longjump/backflip/…） | `motor_primitives.py:62-123`；`main.py:2438-2530` | ❌ 结构上不可达（当前运行点）：`_lif_motion` 为真（`control.y=70>8`）→ 从不取得操纵权 |
| S30 | 深坑/地下跳跃护栏 | `main.py:2358-2384,2551-2561` | ✅ 生效但仅限 `pos_y<-200`/原点/`<-700` |
| S31 | 对话（LLM press_a/b）写入 jump | `main.py:2279-2323` | ✅ 生效（仅在对话会话中） |
| S32 | 教练 `command.turn_and_go` 直写控制 | `main.py:1905-1915,2330-2348` | ✅ 生效（**Python 直写 control.x/y/jump**，与本团队"排除硬编码控制补丁"原则正面冲突，需单独处置） |
| S33 | `gate_forward` / `gate_jump` Hz 门 | `main.py:776-803,2883-2957,3064`；`plugin/scene_context.py:115-116,233-234` | ⛔ 无执行侧消费者：只进 `flow.json`/`memory.json` 与教练上下文；既不 gate CPG 也不 gate 解码 |
| S34 | 脑内 EVO 循环（诊断） | `main.py:1419-1425,2209-2249` | ✅ 生效但**只诊断**：`EvolutionPipeline(auto_fix=False)`，不落任何修复 |
| S35 | 参数级自进化（EFO/教练写参） | `skills/active_strategy.json`（`__generation=332`） | ✅ 生效（写参 → 600 tick 热重载）；⚠️ 部分键为死写入（S12/S13/S33） |
| S36 | 代码级自进化（fix catalog） | `skills/evolution_skill.py:2557-2580,2644`；`README.md:193,827-830` | ⚠️ 非自治：`--auto-fix` 只"记录 + 量化验证"，真实代码改动仍需人工/agent 执行 |
| S37 | 场景策略绑定落盘 | `plugin/runner.py:498-529`；`instinct_bindings.py` | ✅ 生效（outcome→binding 证据链在累积） |

---

## 1. 多巴胺门控通路增益（S1–S4）— 本任务的重点

### 1.1 数据流（完整链路，含行号）

```
model.step() 每 tick
 ├─ model.py:1691-1705  reward_signal（stuck 骤降 +1.0 / 变卡 -0.1 / fallen -0.5 / 否则 ×0.95 衰减）
 ├─ model.py:1709-1718  按"上一条 tick 的发放向量"手工抬 eligibility（阈值 mean>0.01）
 ├─ model.py:1613-1676  _compute_dopamine()：reward−punishment（DAN_* 常量，max 合成，非求和）
 │     常量: model.py:1591-1599（REWARD_EXPLORATION .20 / PROGRESS .30 / PUNISH_STUCK .30 /
 │                              FALLEN .80 / CLIFF .40 / LOOMING .30 / REVISIT .20 /
 │                              LOOP_STATES .35 / STANDOFF .45）
 ├─ model.py:1725-1743  dop = clip(behavioral + reward_signal×coach_reward_gain + _pending_dopamine + coach_bias)
 ├─ model.py:1745-1748  mushroom.set_dopamine(dop) → mushroom.update_weights()   ← MB 学习
 ├─ model.py:1754-1765  dopamine_gain.set_dopamine(dop)
 │                       pathway_activity = {visual, forward, turn, jump, recurrent} 的即时发放率
 ├─ model.py:1766      dopamine_gain.update_eligibility(pathway_activity)
 ├─ model.py:1767      dopamine_gain.apply_gain_update()  → gain_update_count++
 └─ model.py:1837-1842 _pathway_gains_np[0..4] = gain(visual/forward/turn/jump/recurrent)
                       current *= _pathway_gains_np[_pathway_idx_map]     ← 唯一表达点
```

`_pathway_idx_map[3]` 就是 jump 神经元（`model.py:739-740`；`tests/test_gain_modulation.py:342` 断言）。
即：**gain("jump") 只缩放"投射到跳池的连线体突触电流"**。

### 1.2 「阈值 0.15 / GAIN_MIN 0.5 真的能到达吗」→ 实测：能

`DOPAMINE_GAIN_THRESHOLD=0.15`（`gain_modulation.py:51`）只在 `set_dopamine()`（L143）里用于**开可塑性窗口**；
`apply_gain_update()` 只检查 `|R| < 1e-6`（L196），因此增益更新并不被 0.15 拦住。

探针 `.tmp/a4_autonomy_probe.py`（`FlyModel(demo=True)`，4000 tick，三种场景）实测：

| 场景 | `|dop|≥0.15` 占比 | 可塑性窗口开占比 | eligibility(jump) 非零占比 | gain(jump) 终值 | gain 更新次数 |
|---|---|---|---|---|---|
| calm（前进+场景变化） | 100% | 100% | 99.95% | **2.4091**（逼近 GAIN_MAX 2.5） | 3998 |
| stuck（stuck_ramp + escape） | 6.2% | 6.3% | 8.45% | **1.6379** | 310 |
| fallen（fallen + jump drive） | 100% | 100% | 99.97% | **0.5070**（逼近 GAIN_MIN 0.5） | 3999 |

> 附注（必须声明）：`demo=True` 是 modeled graph（n=4096，无非真实连接组），其运动池发放退化为 100%，
> 因此该表只能证明**阈值与上下界可达、增益更新被真实施加**，不能代表真实连接组的运行点。
> 本机无 `.cache/malecns/manifest.json`（实测不存在），**无法在本地复现真实连接组的运行点**。

结论：`0.15` 与 `GAIN_MIN=0.5` / `GAIN_MAX=2.5` 都不是"到不了"的阈值；S1 是活跃的自适应面。
另有一个方向性事实：受罚主导的 stuck 场景里 dop 为负 → 三因子规则**下压**增益（跌向 GAIN_MIN）；
在 calm/前进场景 dop=+0.3 → 上推（逼近 GAIN_MAX）。即增益对"卡死"的响应是把所有通路电流**变小**，
其中包括跳通路唯一受控的那条腿（见 §1.3）。

### 1.3 jump 通路：增益被读了，但只读了一条腿

| jump 池的注入腿 | 位置 | 是否乘 `gain("jump")` |
|---|---|---|
| 连线体突触电流 | `model.py:1842`（经 `_pathway_idx_map`） | ✅ 是（唯一） |
| MBON→jump（学到的跳倾向） | `model.py:1787` `mbon[3] * mbon_gain_jump`；`mbon_gain_jump=0.35`（`model.py:635,639`） | ❌ 否，固定常数 |
| 记忆召回 → jump | `model.py:1811` `_recalled[3] * mbon_gain_jump * 0.5` | ❌ 否 |
| escape_current（共享） | `model.py:1903` `v[motor_nodes] += escape_current`（motor_nodes ⊃ jump_nodes，`model.py:469-472`） | ❌ 否 |
| escape_jump_drive（fallen 专用） | `model.py:1920-1922` | ❌ 否 |
| reflex_jump 桥 | `model.py:2021-2022`（+0.30） | ❌ 否 |
| tau 临近碰撞 | `model.py:2038-2040` | ❌ 否 |
| 小目标接近 | `model.py:2043-2049` | ❌ 否 |
| sky_score | `model.py:2061-2062` | ❌ 否 |
| 突破（`_brk>0.25`） | `model.py:2165-2166` | ❌ 否 |
| 深坑振荡器（0.80） | `model.py:2193-2201` | ❌ 否 |
| OU 噪声 | `model.py:2241` | ❌ 否 |

`gain("jump")` 的全部消费者只有 3 处：`model.py:1840,1842`（施加）与 `main.py:3039,3155`（遥测）。
**"学到的跳倾向"走 MBON 腿，而 MBON 腿是增益盲区** —— 这是"增益存在却不改变跳行为"的第一层原因。

### 1.4 触发门：`jump_rate > 0.04` 与前向池满速同量级

```python
# model.py:2252-2256  13 tick(~0.26s) 滚动窗
forward_rate, ..., jump_rate = [pool.mean() for pool in np.split(recent, self.motor_splits)]
# model.py:2282-2283
raw_y = clip((forward_rate - 0.008) * 2000.0, 0, 70)     # forward_rate=0.043 → raw_y 饱和 70
raw_x = clip(turn_rate * 1100.0, -70, 70)                # |turn_rate|=0.0636 → raw_x 饱和 ±70
# model.py:2478
jump = jump_rate > 0.04 and now - self.last_jump >= 0.8
```

报告所用轨迹 `.tmp/fly64_trajectory.json`（6000 点，2026-09-24 11:50，与报告同一时间窗）实测：

- `jump=true`：**0 / 6000**
- `ctrl_y` 取值集 = `{70, 50}`（仅两个值）→ 反解 `forward_rate ∈ {0.043, 0.033}`，即前向池**全程钉在满速附近**
- `ctrl_x` 取值集以 `±70` 为主（2706 + 2624），另有 `0`(545)、`67/59/58/62/65/...`
- `ctrl_x` 连续同值游程：长度 1 占 3086 段 → 采样点之间符号几乎每 1.76 点翻转一次（发布间隔 ~10 tick ≈ 0.2 s，
  故实际交替周期 ≈ 0.4 s），且**从不经过中间值 0 之外的死区**，与 `filtered_x` 饱和谐振一致

⇒ 该 run 里前向池以 ≈4.3%/tick 的发放率满速前进，**跳池却始终 < 4.0%/tick**。
门限 0.04 与"已经满速前进的池"的发放率 0.043 属同一量级 —— 跳池要触发，必须与前向池同样活跃。

在观察到的运行点，跳池可用的**持续**驱动只有共享 `escape_current`，而它是带泄漏的：
`model.py:1793-1796`（`mbon[4]` 负 → `×0.98` 一路衰到下限 0.05）、`model.py:1818-1821`（familiarity>0.5 → `×0.90`）。
按 LIF 稳态 `v_ss = I/(1-e^{-dt/tau_m}) = I/(1-0.8187) ≈ 5.51·I`（`model.py:403-406`），
`I=0.05 → v_ss≈0.28`，远低于阈值 1.0；`I=0.15 → 0.83`，仍不足；只有 `I≥0.182` 才能单独越过阈值。
前向池除共享 escape 电流外还有 4 条辅助腿（逃逸累加器、突破前推、restlessness、reflex_forward），
但被 `fwd_aux_ceiling=0.20` 聚合封顶（`model.py:696`），恰好处于"刚够维持满速"的边界。

### 1.5 可塑性记账：比行为门更严，且与奖励脉冲互锁

```python
# gain_modulation.py:53,160-168
ACTIVITY_THRESHOLD = 0.05      # 20 神经元池 ⇒ mean>0.05 等价于"单 tick ≥2 个神经元同时发放"
if self.plasticity_remaining > 0 and is_active: eligibility = E*decay + activity
# model.py:1716-1718  更宽的一条（mean>0.01 ⇒ ≥1 个神经元），但要求同一 tick |reward_signal|>0.05
```

即：**要给跳通路记可塑性账，单 tick 瞬时占用率必须 >0.05（2/20），比行为门（13-tick 均值 >0.04）更严**；
另一条更宽的通道要求"奖励脉冲与跳池发放同 tick 相遇"。在报告 run 里跳池 6000 帧未发放，
所以奖励即使到达也不可能给跳通路记账 —— 形成"不发放 ⇒ 无 eligibility ⇒ 权重不动 ⇒ 更不发放"的闭环。

### 1.6 对"重点问题"的最终判定

> 问题：jump 通路增益存在但 jump 从未触发，是**增益被抑制**、**奖励信号从未到达**、还是**执行层根本没读该增益**？

**三者都不是主因**，实测/代码给出的是第四种组合：

1. **奖励/多巴胺信号到达了**（`|dop|≥0.15` 在卡死场景 6–100% 的 tick 满足、`gain_update_count` 持续增长、
   增益在 `[0.5, 2.5]` 内自由移动）。"奖励信号从未到达"**不成立**。
2. **增益没有被"卡死"**（既非恒 GAIN_MIN 也非恒 GAIN_MAX），但**它只作用于一条腿**：
   跳通路唯一受增益控制的注入是连线体突触电流；承载"学到的跳倾向"的 MBON→jump 用固定 `0.35`（`model.py:1787`）。
   于是"学习 → 增益 → 跳行为"的语义链在实际结构里是断开的（学习走 MBON，增益走突触电流，二者不并联）。
3. **执行层读了增益，但读到的是最弱的一条腿**，真正的堵点是**行为门的标定**：
   `jump_rate > 0.04`（`model.py:2478`）被标成与前向池满速（0.043）同级，而跳池缺乏能把它推到 0.04 的持续驱动腿
   （`escape_current` 下限 0.05 → `v_ss≈0.28`）。这不是"没读增益"，是"读了也没用 + 门限本身不可达"。
4. **附加的真实抑制（次要但方向一致）**：卡死场景 dop 为负，三因子规则把增益**下压**（S1 实测跌向 GAIN_MIN 0.5），
   而跳通路唯一受控的那条腿因此**在需要跳的时候被减半**。

**因此**：报告 §5.5「jump 4 条路径全部阻断在 memory.py」的因果链**与当前代码不符**。
当前代码里 jump 的主路径是 **LIF 解码**（`model.py:2478`），它对 `anomaly_state` **没有任何依赖**；
报告列出的 4 条路径（oscillating burst / CliffDetector / force_jump / 外部 action）都是**次级**路径。
据此提出的 P0.1/P0.2（在 `stuck_ramp` 反射里加 jump、超时强制 jump）属于**硬编码控制补丁**，
正是本团队要排除的路线；脑模型侧的等效目标是：让跳池的"学习表达腿"经过增益（把 `mbon_gain_jump` 与
`gain("jump")` 串起来）、并把 `jump_rate` 门改用可归一化的量（例如与前向池占用率比值），而不是加一个 Python 强制跳。

### 1.7 「跳」在系统里同时存在 4 个互不一致的门限口径

| 门限 | 值 | 单位 | 位置 | 是否决定行为 |
|---|---|---|---|---|
| LIF 解码门 | `> 0.04` | per-tick 比例（=2.0 Hz） | `model.py:2478` | ✅ **唯一的执行门** |
| 遥测镜像 | `< 0.04` | per-tick 比例 | `main.py:3064`（`jump_not_active`） | ❌ 只上报 |
| 参数门 `gate_jump_threshold` | `8.0`（默认）/ 线上文件 `3.082` | Hz | `main.py:2894,2957`；`skills/active_strategy.json:8` | ❌ 只进 `flow.json` + 教练上下文（`plugin/scene_context.py:234`） |
| 遥测独立门 | `> 2.` | Hz | `telemetry.py:94` | ❌ 只上报 |

外加面板文案把 forward 门写死成 "gate 0.4 Hz"（`fly64/web/dashboard.js:214`）。
⇒ 调任何"跳门"旋钮都不会改变行为，除非改 `model.py:2478`；这也是团队方案里**必须统一门限语义而非新增门限**的
直接依据（任何一个新门限都会变成第 5 个口径）。

---

## 2. 蘑菇体（MB）价值学习（S5–S9）

| 机制 | 位置 | 数据流入口 | 是否被调用 | 门禁 | 判定 |
|---|---|---|---|---|---|
| KC 稀疏编码 + MBON 输出 | `mushroom_body.py:172-233` | `model.py:1221-1226`（`mushroom.encode(scene_sig)`，128 维场景签名） | ✅ 每 tick | top-5%（`KC_SPARSITY=0.05`） | ✅ 生效 |
| 三因子权重更新 | `mushroom_body.py:362-415` | `model.py:1745-1746` | ✅ 每 tick | `DOPAMINE_THRESHOLD=0.3` 只用于开窗口（L333）；`update_weights` 只要求 `|dopamine|>1e-6`（L383） | ✅ 生效 |
| dopamine 平滑 | `mushroom_body.py:313-348` | 同上 | ✅ | `alpha=0.3` | ✅ |
| 记忆固化（强 dop → consolidated） | `mushroom_body.py:406-439` | `update_weights` 尾部 | ✅ | `CONSOLIDATION_THRESHOLD=0.6`（可达：fallen −0.8、setback −1.0） | ✅ |
| 记忆召回 → 行为 | `mushroom_body.py:541-574`；`model.py:1803-1811` | 每 tick | ✅ | `n_kc*sparsity*0.5 = 50` 共享 KC 重叠 | ✅（同场景可满足） |
| 饱和稳态（R17/t27 陡崖缩放） | `mushroom_body.py:235-276` | `encode()` 内 | ✅ | 进入 0.99 / 退出 0.8（滞回） | ✅（探针 `steep_scaling_events=282~5105`） |
| 学会无助的自动恢复（R22） | `mushroom_body.py:278-296` | `encode()` 内 | ✅ | `|out|<0.05 持续 50 帧` | ✅ |
| **自适应学习率 `lr_adapt`** | `mushroom_body.py:350-360` | 无 | ⛔ **全仓库无调用点**（仅 `tests/test_mushroom_body.py`） | — | ⛔ 死代码，`lr_adapt` 恒 1.0 |
| **异常消解记忆固化** | `mushroom_body.py:513-539` ← `main.py:2693-2699` | 守卫 `getattr(model,"_kc_activity",None)` | ⛔ `_kc_activity` **全仓库唯一出现处就是这一行读取**（grep 1 处） | 恒 None | ⛔ 死代码 |
| 场景迁移 warm start | `model.py:1194-1199` | 场景变化且距上次 >1500 tick | ✅ | 需 `consolidated` 非空 | ✅ |

探针实测（demo）：`mb_assoc_count` 随 tick 线性增长；`weights[:,3]`（jump_bias 列）最大绝对值从 0.04998 变为
0.1144（fallen 场景，Δ=0.1083）→ **MB 学习确实在写权重**，不是只记账。
但注意：MBON 列 `|output|<0.05` 时其 eligibility ≈ 0（`eligibility = outer(kc, mbon)`），
该列会陷入"输出为零 ⇒ 不能学习"的退化态；R22 恢复机制是唯一逃生口。

---

## 3. 中央复合体（CX）（S10–S13）

| 机制 | 位置 | 入口 | 门禁 | 判定 |
|---|---|---|---|---|
| 环形吸引子航向罗盘 | `central_complex.py:392-414,541-558` | `model.py:2082-2097` | — | ✅ |
| 锚点路径积分 + 视觉重定位 | `central_complex.py:47-175,560-564` | `model.py:2099`；`main.py:2731`（场景变化重锚） | 需 anchor 非空 | ✅ |
| 多源目标向量竞争（FB） | `central_complex.py:257-283` | `main.py:2748-2751` → `navigation_vectors()`（`memory.py:2471-2490`） | `goal_vectors` 为真 | ✅ |
| 无目标时的 novelty 回退 | `central_complex.py:270-280` | 同上（`|novelty_direction|>0.1` 或 `|novelty-0.5|>0.3`） | — | ✅ |
| 空转漫游 | `central_complex.py:286-292` | `goal_strength<0.05` | 被上一条常驻压住 | ⚠️ |
| 转向电流 | `model.py:2100-2101`（`cx_steering_gain_turn=0.12`，`model.py:746`） | 每 tick | 两级小增益：`steering_gain 0.12 × goal_strength ≤1 → bias ≤0.15`，再 `×0.12` ⇒ **≤0.018 V/tick** | ⚠️ 量级仅为转向竞争主导项（±0.18）的 1/10 |
| **环路突破（环行破锁 EVO-057）** | `central_complex.py:294-306` | `stuck_duration`（`model.py:2096`，此前是死读已修） | `stuck > _loop_break_stuck_s` **且** `_no_goal` **且** 冷却 1500 tick | ❌ 见下 |
| `navigation.steering_gain` 旋钮 | `main.py:1848-1849` | — | — | ⛔ 死写入 |
| `navigation.loop_break_stuck_s` 旋钮 | `main.py:1850-1851` | — | — | ⛔ 死写入 |

**探针实测**（`.tmp/a4_cx_probe.py`，4000 tick，`stuck_duration=1000s`）：

```
写入前: hasattr(cx,'steering_gain') = False           # CentralComplex 根本没有这个属性
        cx._goal_comp.steering_gain    = 0.12
写入后: cx.steering_gain               = 0.5   ← main.py:1848 写的影子属性，无人读
        cx._goal_comp.steering_gain    = 0.12  ← 真正参与运算的那个没变
        cx._loop_break_stuck_s         = 10.0  ← 写在 CentralComplex 上
        cx._goal_comp._loop_break_stuck_s = None ← 读取端在 goal_comp 内（central_complex.py:297）
⇒ effective_steering_gain = 0.12（教练/EFO 的 0.5 无效）；loop_break 阈值永久=45.0
```

环路突破可达性矩阵（同探针）：

| 目标向量 | novelty_direction | stuck | 4000 tick 内突破次数 | `_ext_goal_strength` |
|---|---|---|---|---|
| 典型（danger 1.2 / frontier 0.7） | 0.0 | 1000 s | **0** | 0.625 |
| 典型 | 0.0 | 30 s | 0 | 0.4667 |
| 极弱权重（norm<0.075） | 0.0 | 1000 s | 3 | 0.0133 |
| 无向量 | 0.0 | 1000 s | 3 | 0.0 |
| 无向量 | 0.4 | 1000 s | 0 | 1.0 |

⇒ **只要 `coverage_gap_vector` 或 danger 向量在供（未访问格子存在时为真，报告 run 覆盖率 15%），
`_ext_goal_strength = min(1, norm/1.5) ≥ 0.05` 恒成立 → `_no_goal` 恒假 → CX 环路突破永不触发。**
这是"环行陷阱"在脑模型侧最直接的失效点之一：唯一为"持续环行"设计的 CX 原生机制被"仍有未探索格子"这一
信号锁死。同时它的阈值旋钮是死写入，无法由教练/EFO 调参。

---

## 4. 本能绑定：场景 → 本能晋升（S14–S15）

- 晋升规则：`instinct_bindings.py:303-307`，`improved >= PROMOTE_MIN_IMPROVED (2)`（L79），`worse` 会清零并降级（L286-296）。
- 显著性签名：`SALIENT_PARAMS`（L87-91）= `fallen_recovery.mode`、`exploration.turn_bias`（量化 0.1）、
  `escape.stuck_threshold_s`（量化 5.0）。模块 docstring 明确记录了"全参数指纹"曾导致 13 个互异签名、永不晋升的负结果。
- 消费端：`main.py:1685-1698`，热重载时 `get_binding(scene_key)` 命中就把参数合并进 `_active_strategy` 并置 `_instinct_applied`。
- **线上库实测**（`fly64/skills/scene_strategy_bindings.json`，mtime 2026-09-17 18:35）：
  ```
  场景 "致命熔岩地"：2 个 bucket
    mode=directional_climb|turn_bias=0.7|stuck_threshold_s=20.0  improved=1  promoted=false
    mode=directional_climb|turn_bias=0.6|stuck_threshold_s=10.0  improved=1  promoted=false
  entry.promoted = false, promoted_signature = null
  ```
  ⇒ 两个候选各差 1 次 clean improvement ⇒ `get_binding()` 恒返回 None ⇒ **本能晋升面"已接线但未达门槛"（休眠）**。
  模块 docstring（L53-61）已把这个状态记录为"recorded negative result"，并明确要求**不得降低门禁来制造晋升**。
- **潜在不可达（二次）**：库内候选参数 `turn_bias=0.6/0.7` 落在 `CLAMP_BOUNDS["exploration.turn_bias"]=(0.0,0.25)`
  （`main.py:1102-1105`）之外。若将来晋升成功并被合并，`main.py:1742` 的钳位会把它改写成 0.25 并回写磁盘
  （自愈，`main.py:1756-1879`）→ **"被记录的本能"与"实际生效的参数"不一致**，且这种改写是静默的（只有 WARNING + `clamped_keys` 遥测）。
- 现在的 `active_strategy.json` 里 `turn_bias=0.25`、`bold_turn_bias=0.25` 正好等于钳位上界，
  说明 EFO/教练一直在试图写更高值而被打到上限。

---

## 5. memory.py 的驱动 / 稳态逻辑（S18–S26）

### 5.1 结构性缺陷：`StuckDetector` 的 Hz / per-tick 单位混用（S19，最高优先级发现）

```python
# memory.py:135-137（阈值声明为 Hz）
rate_threshold: float = 5.0, rate_stuck_s: float = 3.0
# memory.py:206-209 / 217（用 Hz 阈值比较）
if forward_rate < self.rate_threshold: self._rate_low_s += self._dt
r_score = min(1.0, self._rate_low_s / self.rate_stuck_s)
# main.py:2650（传入的是 per-tick 比例！）
forward_rate=getattr(control, 'forward_rate', 0.0),
```
`Control.forward_rate` 是 13-tick 窗的**每 tick 发放比例 ∈ [0,1]**（`model.py:2255`；单位契约见 `main.py:765-803`）。
`per-tick 比例 < 5.0` **恒真** ⇒ `_rate_low_s` 只增不减 ⇒ 3 s 后 `r_score = 1.0` ⇒
`stuck_score = max(t,f,r) = 1.0` **由构造决定**，与是否真的卡住无关。

这与代码库里**已经修过**的同类缺陷完全同型：`main.py:776-783` 记录了 `gate_jump` 因为"per-tick 比例永不超过 1.0
却与 2.0 Hz 阈值比较"而**永久为假**。同一契约在**显示侧**修了，在**检测侧**（StuckDetector 调用点）**没有修**。

后果链（与报告 memory.json 的多项症状一致）：
`stuck_score≡1.0` → `escape_behavior≡True`（`memory.py:2186`：`stuck_score≥0.8` + `exploration_mode`）→
`escape_mode≡True` → `deadlock_burst_ready(stuck>60)≡True`（`memory.py:1217`）→ burst 机制应每 300 tick 触发一次。
这一条同时说明：**报告里"stuck_score=1.0 / stuck_duration=1100.72s"不是"卡死"的证据，而是检测器单位缺陷的产物**。

### 5.2 报告 memory.json 快照与当前代码不可复现

- `stuck_duration=1100.72 s` 与 `disp_60s=1080.7` 同时成立，与 `memory.py:1993-1995`
  （`disp_60s > 500` 时 `_stuck_duration -= 1.0/tick`，即 22 s 内清零）矛盾。
- `anomaly_state="stuck_ramp"` 与 `loop_score=2.26`、`stuck_duration=1100 s` 矛盾：
  `_detect_micro_loop` Tier-2（`memory.py:1330-1340`）在 `stuck>90` 且 `loop>0.5` 时返回 True
  （进度豁免仅在 `loop_score<0.8` 时生效）→ 多数票应落到 `micro_loop`。
- 若真为 `micro_loop`，反射会取操纵权并写 `control.y=30`（`memory.py:1836`），
  但轨迹的 `ctrl_y` 取值集只有 `{70,50}`。

⇒ **建议**：把报告 §3/§4 中依赖 memory.json 的结论（"反射疲劳""MotionStateDetector 优先级断裂导致 jump 阻断"）
标记为**待复核**；可复现的证据是 `.tmp/fly64_trajectory.json`（6000 点，见 §1.4）与
`fly64/artifacts/latest.jsonl`（29266 条发布记录，其 `jump` 字段是发布窗内的 `pending_jump` OR，二者定义不同，不可混用）。

### 5.3 其它驱动 / 稳态表面

| 机制 | 位置 | 入口 | 门禁 | 判定 |
|---|---|---|---|---|
| 卡的三信号检测 | `memory.py:162-232` | `main.py:2647-2663` | 见 §5.1 | ❌ 单位缺陷 |
| 空间记忆/新颖度/覆盖 | `memory.py:270-827` | 同上 | — | ✅ |
| 「进展」账本 `progress_is_ineffective` | `memory.py:1113-1160` | L2a、anomaly、burst、plugin/runner 共用 | `efficiency < 0.25` | ✅ 单一口径 |
| 死锁 burst 前置条件 | `memory.py:1189-1220` | `main.py:2055-2062` | `loop>阈值` 或 `stuck>60` 或 (`stuck≥45` 且无进展) | ✅；但 `main.py:2062` 的 `_last_burst_tick` **只读不写** ⇒ 防重入守卫恒真（⛔ 空守卫），且 burst 期间 `control.jump=False`（`main.py:2082` **主动抑制跳**） |
| 运动状态多数票 + 优先级 | `memory.py:1377-1462,1347-1373` | `main.py:2020-2035` | 30 帧窗，tie-break 按严重度 | ✅ |
| 反射控制器 4 条反射 | `memory.py:1598-1732` | `main.py:2009-2017` | `anomaly∈REFLEX_TYPES 且 confidence≥0.6 且 冷却≤0` | ⚠️ |
| 早期墙检测（wall_persist>2 s） | `memory.py:2040-2051,1654-1658` | `main.py:2016` | `wall_score>0.3` 连续 | ✅ |
| `bold_direction()` | `memory.py:1662-1674` | `main.py:2124-2125`（**每 tick 调用**） | 需 `escape_behavior and forced_bold_explore` | ⚠️ 函数体每次调用即 `self._last_direction = -self._last_direction` ⇒ 实际输出是**逐 tick 翻号的抖动**，而非 docstring 声称的"交替相位" |
| `forced_bold_explore` | `memory.py:2079-2105` | 每 tick | `_scene_low_duration ≥ 10 s`，其累加需"同一异常持续 > `bold_explore_stuck_s`(默认 60 s)"或"访问格<20" | ❌ 报告 run 的 `anomaly_duration=11.14 s` 反复重置 ⇒ 恒假 |
| 逃逸释放 / 冷却 | `memory.py:2129-2191` | 每 tick | `escape_s>60` 或（>30 且异常∈{idle,micro_loop}） | ✅ |
| `health_score` | `memory.py:2226-2250` | 主循环 | 权重含 `_revisit_penalty_scale`（教练可调） | ✅ |
| 反射时强制跳（fallen>60 s） | `memory.py:2400-2410` | `reflex_action` | `_fallen 且 _stuck_duration>60` 且反射 active | ⚠️ |
| 导航目标向量 | `memory.py:2471-2490` | `main.py:2748` | 失败记忆/覆盖率缺口 | ✅（同时锁死 S13） |

### 5.4 `oscillating` 检测窗 与 被观测交替周期的量级关系

```python
# memory.py:1289-1317
def _detect_oscillating(self, disp_60s=None, median_speed=None) -> bool:
    if disp_60s is not None and not progress_is_ineffective(...): return False   # 进度门
    if len(self._ctrl_x_buf) < 6: return False
    ... # 统计 <=-60 / >=+60 之间的切换次数
    return alternations >= 3                                                     # 30 帧窗内 ≥3 次
```
`_ctrl_x_buf` 是 `MotionStateDetector(window=30)` 的 30 帧缓冲（`memory.py:1255,1394`）。
由轨迹实测（§1.4）推算：符号切换约每 1.76 个发布点一次，发布间隔 ≈10 tick ⇒ **一次完整往返 ≈ 17–18 tick**。
30 帧窗内因此只有 **≈3–3.5 次符号切换**，正卡在 `>= 3` 的门限上 —— 检测会**抖动**而不是锁定。
多数票（30 帧）随后把状态交给 `micro_loop`（需 `loop>0.5`）或 `wall_stuck`（需 `wall>0.4`）或 `stuck_ramp`
（需 `ramp>0.5`），于是**唯一携带 jump 的反射（oscillating burst，`memory.py:1809-1816`）拿不到触发条件**。

⇒ 报告"oscillating 永不触发 ⇒ jump 路径 A 阻断"的现象与代码一致，但**机制不是"优先级排序缺陷"**
（优先级 `memory.py:1361-1373` 只是决定谁先被问），而是 **30 帧窗 / ≥3 次切换这个检测口径与真实交替周期同量级**。
这一条属于**待实机复核的候选根因**（需要 `/flow.json` 的 `ctrl_x` 原序列或 `anomaly_state_history` 才能定量确认），
但它比"降低优先级/加硬编码 jump"更接近脑侧根因，且天然可用"检测窗自适应于实测交替周期"来修。

---

## 6. main.py 中的实际调用点（按 tick 顺序）

| 行 | 内容 | 相关表面 |
|---|---|---|
| 1419-1425 | `EvolutionPipeline(auto_fix=False, window_seconds=120)` | S34（只诊断） |
| 1512 | `model.escape_mode = memory_ctrl.escape_behavior` | S18 → jump 共享电流腿 |
| 1518-1546 | 位移窗口 → `report_movement` / `disp_60s` / `median_speed` | S5（奖励脉冲） |
| 1557 | `control, spikes = model.step(...)` | S1–S4, S27, S28 |
| 1678-1698 | 600-tick 热重载 + 本能绑定合并 | S14, S16 |
| 1742-1753 | `apply_strategy_clamps` → `memory_ctrl.bold_explore_stuck_s / bold_turn_bias` | S17 |
| 1756-1879 | 钳位回写自愈 + `active_strategy`/`navigation`/`coach`/`memory` 各旋钮下发 | S16 |
| **1848-1851** | `model.cx.steering_gain` / `model.cx._loop_break_stuck_s` | **S12, S13（死写入）** |
| 1884-1885 | `model.strategy_turn_bias`（`×0.30` 注入胜出转向池，`model.py:1911-1916`） | S16（被钳到 ≤0.25） |
| 1905-1933 | 教练 `command.turn_and_go` → 模型标志；`dopamine.bias/setback` | S32, S5 |
| 1996-2037 | 反射 update + **直写 `control.x/y/jump`**（并同时设 `model.reflex_*` 标志） | S21, S22 |
| 2039-2086 | 探索死锁 burst（`control.y=127`、`control.jump=False`、`reflex_override=True`） | S25 |
| 2111-2130 | `bold_now` → `model.bold_turn_drive` | S23, S24 |
| 2149-2150 | `model.set_python_correction(control.x, reward_signal)` | 误差梯度桥（t3） |
| 2275 | `latest_control = control` | 合成帧回灌 |
| 2279-2323 | 对话：`control.jump=True/False` | S31 |
| 2330-2348 | 教练命令消费者：直写 `control.x/y/jump` | S32 |
| 2358-2384 | 地下/原点跳跃护栏：`control.jump=True` | S30 |
| 2438-2511 | CPG 原语请求（**被 `_lif_motion` 门挡住**） | S29 |
| 2521-2530 | CPG 取操纵权条件 `not _lif_motion` | S29（结构性不可达） |
| 2551-2561 | 深坑 bailout：`control.jump=False` | S30 |
| 2569-2578 | `apply_action_entropy`（只抖 x/y） | S26 |
| 2579-2581 | `bridge.write_control(control.x, control.y, control.jump, b, z)` | 最终执行点 |
| **2647-2663** | `memory_ctrl.update(forward_rate=control.forward_rate, ...)` | **S19（单位缺陷）** |
| 2686-2699 | 状态镜像；`consolidate_anomaly_resolution` 守卫 | S7（死路径） |
| 2730-2751 | CX 重锚 / 视觉方位 / 目标向量 | S10–S13 |
| 2883-2957 | Hz 换算的 `gate_forward` / `gate_jump`（仅遥测） | S33 |
| 3034-3053 | `dopamine_gain` 五通路增益 + `reward_signal` + `gain_update_count` 遥测 | S1（可观测） |
| 3064 | `jump_not_active: control.jump_rate < 0.04` | S3（同门限的遥测镜像） |
| 3149-3168 | `_plasticity_metrics`（每 100 tick） | S1, S34 |

**关于 `control.jump=True` 的全部写入者（用于回答"执行层是否读增益"的边界）**：
`model.py:2478`（LIF 解码，主路径，与 anomaly 无关）、`main.py:2031`（反射）、`main.py:2311/2317`（对话）、
`main.py:2348`（教练命令）、`main.py:2369`（地下护栏）、`motor_primitives.py:66/71/89/94/104` + `main.py:2530`（CPG，当前不可达）。
报告 run 的取值覆盖面（`ctrl_y∈{50,70}`、无 127、无 30、无 ±60/±69 群）与"仅 LIF 解码在写控制"一致，
⇒ **该 run 中 ≈97% 的采样帧由 LIF 解码拥有操纵权，memory/reflex/CPG 层没有接管**。

---

## 7. 自进化面（S34–S37）

- **脑内 EVO 循环**（`main.py:1419-1425`，逃逸触发时每 10 s 跑一次 `run_one_cycle()`）：
  `auto_fix=False` ⇒ 只产出 findings + 写 `DashboardHTTP.evolution_json` / `runtime/evolution_history.json`，
  **不修改任何脑模型代码或参数**。判定：✅ 生效但仅为诊断。
- **参数级自进化（真正闭环）**：`skills/active_strategy.json`（`__generation=332`，mtime 2026-09-23 23:36）
  由 EFO/教练写入，脑侧每 600 tick（≈12 s 模型时间）热重载。判定：✅ 生效。
  其中**死写入项**必须从"自治能力"计分中剔除：`navigation.steering_gain`(S12)、`navigation.loop_break_stuck_s`(S13)、
  `exploration.gate_forward_threshold` / `gate_jump_threshold`(S33)。
- **代码级自进化**：`README.md:827-830` 明确 `evolution_skill.py --auto-fix` 的语义是
  "记录 + 量化验证（写 fix_template 到 catalog 并测量效果），**实际代码改动仍需按 fix_template 执行（人工或 agent）**"。
  判定：⚠️ **非自治**。这与团队目标"以脑模型自进化与自治能力为核心"直接相关：
  目前的"自进化"在代码维度上依赖外部 agent，而"参数维度 + 突触/增益维度"是真正运行时自治的。
- **神经可视化/模式草稿**：`skills/pattern_drafts.py`、`skills/neural_viz_skill.py`、`plugin/coach_outcomes.py`
  构成"证据 → 建议 → 策略 → 结果"的回环（`plugin/runner.py:498-529`）。判定：✅ 生效。

---

## 8. 给下游（队长/根因任务的）可复用结论

1. **把 jump 问题从"决策链断裂"改写为"输出层标定 + 增益覆盖不全"**：
   主路径是 `model.py:2478` 的 LIF 解码，它对 `anomaly_state` 无依赖；报告 §5.5 的 4 条路径是次级路径。
2. **jump 三选一的答案**（§1.6）：奖励到达了、增益没坏、增益被读但只覆盖一条最弱的腿；
   真正的门是 `0.04/tick` 与"前向池满速 0.043/tick"同量级，而跳池缺少持续驱动腿（`escape_current` 下限 0.05 → `v_ss≈0.28`）。
   硬编码加跳（报告 P0.1/P0.2）会有即时行为效果，但属于被排除的路线；脑原生的等效改法是
   **把 MBON→jump 腿纳入增益链**（`mbon_gain_jump` 与 `gain("jump")` 串联）**并把 `jump_rate` 门改为归一化量**。
3. **CX 环路突破是"环行陷阱"最直接的脑侧失效点**（S13，已实测触发 0 次，且旋钮死写入）。
4. **StuckDetector 的单位缺陷（S19）会污染所有以 `stuck_score` / `stuck_duration` 为输入的自适应面**
   （反射冷却、burst 前置条件、逃逸门、help 升级、EVO 模式匹配），建议列为 P0 且**与报告无关地独立成立**。
5. **oscillating 检测口径与真实交替周期同量级**（§5.4）：30 帧窗 / ≥3 次切换 对上实测 ≈17–18 tick 的往返周期 ⇒
   检测抖动、状态被让给别的类别 ⇒ 唯一携带 jump 的反射拿不到触发条件。这是"报告现象正确、机制待改写"的第二例。
6. **可复现证据 vs 不可复现证据**：轨迹（6000 点）与 `gain_modulation` 探针可复现；
   报告 memory.json 的多项数值与当前代码矛盾（§5.2），引用时需标注。
7. **本机限制**：无 `.cache/malecns/manifest.json`，真实连接组的运行点无法离线复现；
   探针结论仅覆盖"接线/算术/阈值可达性"。
8. **给"排除硬编码补丁"的可操作口径**：本次盘点给出的 5 个脑侧可改点全部是"让已有信号真正到达"，
   而不是新增控制分支 —— (a) `StuckDetector` 单位对齐、(b) MBON→jump 腿纳入增益、(c) `jump_rate` 门归一化、
   (d) CX 环路突破的目标门改为"进展/环行"而非"是否有目标向量"、(e) 修 `cx.steering_gain` /
   `cx._loop_break_stuck_s` 的两个死写入（写端改到 `_goal_comp`）。

---

### 附：本次判定所用的可复现证据

| 证据 | 路径 | 说明 |
|---|---|---|
| 增益探针 | `.tmp/a4_autonomy_probe.py` → `.tmp/a4_probe_out.json` | demo 模型 3 场景 × 4000 tick，测 dop/阈值/界/eligibility/增益/解码 |
| CX 探针 | `.tmp/a4_cx_probe.py` | 证明 `steering_gain` / `_loop_break_stuck_s` 死写入 + 环路突破可达性矩阵 |
| 轨迹统计 | `.tmp/fly64_trajectory.json`（6000 点） | `jump=0/6000`；`ctrl_y∈{70,50}`；`ctrl_x` ±70 主导；游程长度 1 占 3086 |
| 遥测 | `fly64/artifacts/latest.jsonl`（29266 条，2026-09-19） | 字段 `jump` 是发布窗内 `pending_jump` 的 OR，**与轨迹 `jump` 口径不同，不可混用** |
| 参数面 | `fly64/skills/active_strategy.json`（`__generation=332`） | `turn_bias=0.25`（=钳位上界）、`navigation.steering_gain=0.12`、`loop_break_stuck_s=45.0` |
| 本能库 | `fly64/skills/scene_strategy_bindings.json` | 2 个 bucket 各 `improved=1`、`promoted=false` |
| 运行环境 | `.cache/malecns/manifest.json` 不存在 | 真实连接组运行点无法离线复现 |
