# R-B 新增 B/Z 解码池与 MBON 列扩展方案

依据：`model.py:423`（motor_nodes 组织）、`model.py:1595-1813`（解码窗）、`mushroom_body.py`（2000 KC · 5 MBON · top-5% 稀疏）、`gain_modulation.py`

## 1. 现状

- 解码池 4 个：forward(60, DNg100) / turn_left(40) / turn_right(40) / jump(20, DNp01/DNp10)，共 160 神经元；`motor_splits` 前缀和切分 history 窗口（model.py:1598）。
- MBON 5 列：forward/left/right/jump/explore，KC→MBON 可塑 + R17 饱和守卫。
- 连接组权重 `self.w` 只读（增益调制通路替代权重修改）——新增池不能"训练"新突触，只能**选已有群体做读出**。

## 2. B/Z 解码池构造（flyGNN 低维读出思路）

### 2.1 候选神经元群

MaleCNS 下行神经元中未占用的运动群。选择准则（与现有池一致：优先 located、有 optic-column/下行注释的 DN 群）：

| 新池 | 规模 | 候选 | 理由 |
|---|---|---|---|
| strike（B 池） | 20 | DNa01 副群 / DNg09 内筛选发放率与 jump 池相关性低且方差大的 20 神经元 | 拳击/俯冲是短促攻击动作，与 jump 池同源但需独立读出避免共激活 |
| crouch（Z 池） | 20 | DNg09 另一子群 / vnc 下行低频稳定群 | 蹲/长跳蓄力是持续姿态动作，宜用低频稳定群体 |

选址在 `__init__` 阶段完成（一次性，基于连接组度中心性 + 与现有 4 池的活动正交性筛选），写入 `self.strike_nodes` / `self.crouch_nodes`，并入 `motor_nodes`，`motor_splits` 扩为 6 段。

### 2.2 解码（model.py step 尾部）

```python
strike_rate, crouch_rate = [float(pool.mean()) for pool in np.split(recent, self.motor_splits)[4:6]]
strike = strike_rate > 0.05 and now - self.last_strike >= 1.0   # 与 jump 同款门控+冷却
crouch = crouch_rate > 0.03                                     # 电平制，供长跳蓄力组合
```

`Control` 扩展 `b=strike, z=crouch` 字段 → `bridge.write_control` → t1 的脉冲通道。

### 2.3 神经驱动（不训练权重的前提下让池活动起来）

沿用项目已验证的**电流注入**范式（escape/bold_turn_drive/CX 偏置同款）：

- `v[self.strike_nodes] += strike_gate * 0.6` —— strike_gate 由 CPG 原语触发器（t2）与交互目标显著性（`door_frame_score`）提供；
- `v[self.crouch_nodes] += crouch_gate * 0.5` —— crouch_gate 由长跳蓄力相位/低净空场景提供。

即：**神经池保留可解释的放电率读出 + 门控电流注入决定何时激活**，符合 P1 神经接管后"无 Python 旁路"的 PIN 约束（注入进 LIF 电压，不直写 control）。

## 3. MBON 列扩展

新增 4 列：`punch / dive / groundpound / longjump`（总 5→9 列）：

- KC 输入复用现有 top-5% 稀疏编码；KC→新列权重初始化为小随机，可塑规则与现列一致（dopamine 三因子 + R17 饱和守卫）；
- 多巴胺事件源扩展：原语成功（60s 位移达标 / gold spot 命中）→ 正脉冲到对应列；原语失败（超时熔断/坠落）→ 负脉冲；
- `mb_mbon_*` 输出按现格式追加进 `/flow.json`（dash 面板可自动展示）。

## 4. 开销与测试

- 计算开销：+40 神经元解码 + 4 MBON 列 ≈ +8 μs/tick（<0.05%），远低于 P1–P3 合计 190 μs。
- verify：

```bash
python -m pytest tests/test_model.py -q          # 6 段 motor_splits、新池门控/冷却
python -m pytest tests/test_mushroom_body.py -q  # 9 列可塑 + 饱和守卫
python -m pytest tests/test_dan_shaping.py -q    # 原语成败 dopamine 事件
```

## 5. 与 t2 的接口

- t2 CPG 门控 → 本模块 `strike_gate/crouch_gate` 电流（唯一入口，无旁路）；
- 本模块 strike/crouch 读出 → t2 状态机作为"神经意图"输入之一（CPG 可在无神经意图时自主触发，两路取或）。

## 6. 工作量

| 项 | 估计 |
|---|---|
| 池选址 + 解码扩展 | 1d |
| MBON 4 列 + dopamine 事件 | 1d |
| 测试固化 | 0.5d |
