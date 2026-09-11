# FruitflyAI 项目记录

## 项目结构

```
D:\codes\flygym\
├── fly64/                    # Fly64 果蝇脑控制 Mario 项目
│   ├── fly64/                # Python 核心源码
│   │   ├── main.py           # 主循环 + HTTP API
│   │   ├── memory.py         # 空间记忆 + 卡住检测 (Phase 1)
│   │   ├── bridge.py         # 共享内存桥接 (Linux/macOS)
│   │   ├── model.py          # LIF 神经元模型
│   │   ├── retina.py         # 球面复眼采样
│   │   ├── telemetry.py      # 仪表板遥测
│   │   ├── data.py           # MaleCNS 数据下载/预处理
│   │   └── replay.py         # 回放录制
│   ├── web/                  # Web 仪表板
│   │   ├── index.html        # 主仪表板
│   │   ├── memory-heatmap.js # 空间记忆热力图
│   │   ├── dashboard.js      # 仪表板 JS
│   │   ├── dashboard.css     # 仪表板样式
│   │   └── trajectory.html   # 3D 轨迹回放 (Three.js)
│   ├── scripts/              # 安装/运行脚本
│   ├── patches/              # sm64ex Fly64 补丁
│   ├── tests/                # 测试
│   │   └── test_memory.py    # memory.py 单元测试 (19 tests)
│   ├── docs/                 # 文档
│   └── README.md             # 完整安装指南
├── scripts/                  # FlyGym 相关
├── agent.md                  # 项目记录 (本文件)
└── README.md                 # 项目总览
```

## 环境

- **Windows**: WSL2 Ubuntu-22.04
- **Python**: 3.10 (WSL) / 3.11 (Windows venv)
- **SM64**: sm64ex (patched) - sm64.us.f3dex2e
- **Brain Data**: MaleCNS v1.0 (166,700 neurons)
- **GitHub**: https://github.com/rickqi/FruitflyAI.git

## 运行状态

| 组件 | 位置 | 状态 |
|------|------|------|
| 脑模型 | WSL PID # | 运行中 |
| SM64 游戏 | WSL PID # | 运行中 |
| 仪表板 | http://127.0.0.1:8765/ | ✅ |
| 3D 轨迹 | http://127.0.0.1:8765/trajectory.html | ✅ |
| 空间记忆 | http://127.0.0.1:8765/memory.json | ✅ |
| 轨迹 API | /trajectory.json /trajectory-list.json /trajectory-load | ✅ |

---

# 变更日志

## 2026-09-11: Phase 1 导航增强 + 卡住修复

### 变更 1: 空间记忆地图 + 卡住检测系统 (新模块)

**原因：** 果蝇脑模型只有 260ms 神经记忆窗口，无法检测是否在重复路线或卡住。导致马里奥经常撞墙后原地转圈，没有有效的逃脱策略。

**变更内容：**
- **新增** `fly64/fly64/memory.py` — 三个核心类：
  1. `StuckDetector` — 三信号融合卡住检测（temporal_energy 视觉坍缩、game_frame 停滞、forward_rate 下降）
  2. `SpatialMemoryMap` — 50×50 单元网格地图（200 unit/格），记录访问计数、recency 衰减、novelty 计算、loop_score 循环检测
  3. `MemoryController` — 整合 stuck + spatial 输出 escape_behavior 标志
- **新增** `fly64/tests/test_memory.py` — 19 个 pytest 测试覆盖全部功能
- **修改** `fly64/fly64/model.py` — 新增 `escape_mode` 属性、`step()` 接受 `novelty` 参数、新奇度门控视觉增益（novelty<0.3 时 ×1.1, >0.7 时 ×0.9）
- **修改** `fly64/fly64/main.py` — 集成 MemoryController、escape 控制覆盖（转向+前进爆发交替）、`/memory.json` 端点
- **新增** `fly64/web/memory-heatmap.js` — 50×50 网格热力图 canvas 渲染器（蓝→绿→黄→红渐变 + 当前位置白点，1s 自动刷新）
- **修改** `fly64/web/index.html` + `fly64/web/dashboard.css` — 新增 "Spatial Memory" 仪表板面板

**涉及文件：** 8 文件（3 新增，5 修改），~730 行

---

### 变更 2: Stuck 诊断 — 坠落检测 + FailureMemory

**原因：** 运行中发现马里奥卡住的原因是 Y 坐标异常（Y=-221，低于地面正常值 120），实际已掉出地图边界。原 escape 行为设置 `y=0`（停止前进）导致马里奥只转圈不前进，卡住检测持续触发形成死锁。

**根因分析：**
1. 果蝇脑缺乏避障能力，在马里奥走到 Bob-omb Battlefield 边缘时继续向前 → 坠落
2. 坠落时 Y 从 120 降至 -200+，游戏物理引擎限制移动
3. Escape 行为启动 → 随机转向 + `y=0` → 没有前推动力 → 位置不变 → stuck_score 不降
4. 无限循环：卡住→escape→y=0→转圈→仍卡住→继续escape

**变更内容：**
- **修改** `StuckDetector.__init__()` — 新增 `y_min`/`y_max` 参数，默认 `y<-100 ∨ y>1000` 判定为 fallen
- **修改** `StuckDetector.update()` — 增加 `pos_y` 参数，返回 `(stuck_score, stuck_duration, fallen)` 三值元组
- **新增** `FailureMemory` 类 — 记录坠落位置网格键，`avoid_direction()` 方法检查前方格是否为已知坠落点，返回转向偏置
- **修改** `MemoryController.update()` — 增加 `pos_y` 参数，fallen 状态下强制触发 escape_behavior
- **修改** `main.py` escape 逻辑 — 区分 fallen/stuck 两种模式：
  - Fallen：跳跃 + 前进 + 持续跳跃的坠落恢复模式
  - Stuck：交替 0.8s 转向 + 0.8s 前进爆发，集成 failure 避让
- **修改** `/memory.json` 输出 — 增加 `fallen`, `failure_count` 字段
- **修改** `main.py` memory update 调用 — 传递 `pos_y=pose[1]`

**涉及文件：** 2 文件修改（`memory.py`, `main.py`），+137/-38 行

---

### 变更 3: 修复 telemetry JSON 序列化错误

**原因：** `telemetry.py` 中 `json.dumps()` 遇到 numpy int64 类型时抛出 `TypeError: Object of type int64 is not JSON serializable`。原因是 memory 模块引入的 numpy 类型数据进入 observatory 数据链。

**变更内容：**
- **修改** `fly64/fly64/telemetry.py:68` — `json.dumps()` 增加 `default=str` 参数
- **修改** `fly64/fly64/main.py:340` — `log.write()` 中的 `frame_seq` 和 `temporal_energy` 显式转换为 Python 原生类型

**涉及文件：** 2 文件（`telemetry.py`, `main.py`）

---

## 早期变更

### 基础设施
- WSL2 Ubuntu-22.04 环境搭建与适配
- Linux x86_64 内存屏障支持（`bridge.py` macOS 独占修复）
- sm64ex 编译：GLEW 链接修复（`-lGLEW`），`glewInit()` 初始化修复
- MaleCNS 脑数据下载（curl 方式，aria2c 会产生截断文件）
- 脚本适配：`run-fly64`、`setup_sm64.sh` Linux/WSL 适配

### 3D 轨迹回放
- Three.js 3D 轨迹显示 + OrbitControls 自由视角
- 等比例缩放、缩略图/全屏切换
- 0.5x 默认播放速度、文件选择器（Live + 历史）
- `__live__` 回退加载实时 `/trajectory.json`

### API 扩展
- `GET /trajectory-list.json` — 列出历史轨迹文件
- `GET /trajectory-load?file=xxx` — 加载指定历史轨迹
- `GET /memory.json` — 空间记忆状态（Phase 1）
- `GET /bridge-status.json` — 桥接状态

## 注意事项
1. **页面文件更新后需重启脑模型**（HTTP 服务缓存文件到内存）
2. brain model 用 `pkill -f 'python.*main'` 重启
3. SM64 用 `pkill -f 'sm64\.us'` 重启
4. 轨迹数据通过 `bridge.frame_metadata["pose"]` 采集
5. 保存的 `.trajectory.npz` 需在脑模型退出时生成
6. `model.py:180` `self.spikes |= newly_fired` float32 兼容（已修复）
7. `bridge.py:47` `clock_gettime_ns` Windows 不兼容（已知问题）