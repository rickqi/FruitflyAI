# R-A 桥接层 B/Z 键解锁 — 具体实现方案

依据：`patches/sm64ex-fly64.patch`、`fly64/fly64/bridge.py`、`tests/test_bridge.py`

## 1. 现状盘点（实测代码）

| 环节 | A 键 | B 键 | Z 键 |
|---|---|---|---|
| Python `bridge.py` | ✅ `jump` 参数，A_BUTTON=0x8000，附 jump_event 脉冲计数（offset 36） | ✅ `write_control(..., b=...)` 已实现，B_BUTTON=0x4000 打进 buttons 字段 | ❌ 无参数、无常量 |
| C 侧 patch | `buttons &= ~A_BUTTON` 强制剥离，再由 `jump_frames` 脉冲重新注入 | ✅ **未过滤**，随 `pad->button |= buttons` 直通 | ❌ 无 Z_TRIG 处理 |
| main.py 调用 | 每 tick 传 `control.jump` | 仅对话场景传 b（`dialogue` 级联） | ❌ |

**关键结论：B 键的桥接通路其实已通，真正的缺口是 (1) Z 键全链路缺失；(2) B 键缺 game 侧多帧保持（B 写电平单 tick，game 30fps 读取可能错过）；(3) 无下游调用方**。

## 2. 实现方案

### 2.1 Python 侧（`fly64/bridge.py`）

```python
Z_TRIG = 0x2000   # N64 标准位（A=0x8000, B=0x4000, Z=0x2000）

def write_control(self, x, y, jump, enabled=True, b=False, z=False):
    buttons = ((A_BUTTON if jump else 0) | (B_BUTTON if b else 0)
               | (Z_TRIG if z else 0))
    ...
```

- 复用 offset 36 的 `reserved` jump_event 字段扩展为 event 位域，或新增 `b_event/z_event` 到 header `extension[40]`（推荐：`extension` 前 8 字节做 event counters，向后兼容——旧 sm64ex 不读 extension）。
- `game_status()` 增加 `b_pressed`/`z_pressed` 回读。

### 2.2 C 侧（`sm64ex-fly64.patch`，`fly64_bridge.c`）

仿照 `jump_frames` 的多帧保持机制（jump_frames=2 保证 50Hz 写入不被 30fps 读取错过）：

```c
static unsigned b_frames, z_frames;
static uint32_t last_b_event, last_z_event;

/* seqlock 块内追加读取 */
b_event = shared->h.extension_b_event;   /* extension 内 */
z_event = shared->h.extension_z_event;
...
if (b_event != last_b_event) { b_frames = 2; last_b_event = b_event; }
if (z_event != last_z_event) { z_frames = 2; last_z_event = z_event; }
buttons &= ~A_BUTTON;                       /* A 仍走脉冲 */
if (b_frames) { buttons |= B_BUTTON; --b_frames; }   /* 改为脉冲制 */
if (z_frames) { buttons |= Z_TRIG;   --z_frames; }
```

注意：B 从"直通电平"改为"脉冲制"与 A 对齐，保证对话框确认等单次按键语义；持续按住场景（如俯冲滑翔）由 Python 每 tick 重写 event 实现。

### 2.3 调用方（`main.py`）

- `Control` dataclass 增加 `b: bool = False, z: bool = False` 字段；
- 级联末端 `bridge.write_control(control.x, control.y, control.jump, ..., b=control.b, z=control.z)`；
- 遥测 `ws packet` tick 行追加 `ctrl_b/ctrl_z`（`causal_schema=1` 加法演进，`.get()` 兼容旧客户端）。

### 2.4 兼容性与版本

- mmap 版本号保持 `FLY64V2`/`version=2`（extension 字段在既有 40 字节预留区内，不需要 bump）；旧 sm64ex 二进制忽略 extension，新二进制忽略未用位——**双向向后兼容**。
- `replay.py` 与 synthetic 模式的 `frame(x, y, jump)` 签名加可选参数，默认 False 不破坏录制回放。

## 3. 测试与验证（verify）

```bash
python -m pytest tests/test_bridge.py -q                       # Z 位域写入/读回、event 计数
python -m pytest tests/test_dashboard_protocol.py -q           # ctrl_b/ctrl_z packet 契约
python -m pytest tests/test_invariants.py -q                   # header 布局不变量
# 实机（WSL）：对话场景发 B、长跳时序发 Z，观察 /bridge-status.json applied_buttons 位
```

## 4. 工作量与风险

| 项 | 估计 |
|---|---|
| Python 侧 | ~30 行 + 测试，0.5d |
| C patch | ~20 行 + 重编译 sm64ex，0.5d |
| 风险 | Z 与人类玩家 Z 键冲突（同 A 键的"人类摇杆优先"策略可复用到按钮：仅当 pad 无按钮时注入）；sm64ex 需重编译，`scripts/setup_sm64.sh` 已脚本化 |

解锁动作：拳击/踢腿/抓取(B)、俯冲(空中B)、蹲/爬(Z)、长跳(跑+Z+A)、后空翻(蹲+A)、落地砸(空中Z)。
