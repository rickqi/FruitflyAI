# FruitflyAI 项目记录

## 项目结构

```
D:\codes\flygym\
├── fly64/                    # Fly64 果蝇脑控制 Mario 项目
│   ├── fly64/                # Python 核心源码
│   │   ├── main.py           # 主循环 + HTTP API
│   │   ├── bridge.py         # 共享内存桥接 (Linux/macOS)
│   │   ├── model.py          # LIF 神经元模型
│   │   ├── retina.py         # 球面复眼采样
│   │   ├── telemetry.py      # 仪表板遥测
│   │   ├── data.py           # MaleCNS 数据下载/预处理
│   │   └── replay.py         # 回放录制
│   ├── web/                  # Web 仪表板
│   │   ├── index.html        # 主仪表板
│   │   ├── dashboard.js      # 仪表板 JS
│   │   ├── dashboard.css     # 仪表板样式
│   │   └── trajectory.html   # 3D 轨迹回放 (Three.js)
│   ├── scripts/              # 安装/运行脚本
│   ├── patches/              # sm64ex Fly64 补丁
│   ├── tests/                # 测试
│   ├── docs/                 # 文档
│   └── README.md             # 完整安装指南
├── scripts/                  # FlyGym 相关
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
| 轨迹 API | /trajectory.json /trajectory-list.json /trajectory-load | ✅ |

## 修改记录

### Phase 1 导航增强 — 空间记忆 & 卡住检测
- `fly64/memory.py`: StuckDetector (3 信号融合)、SpatialMemoryMap (50×50 网格)、MemoryController
- `main.py`: memory 集成、escape 行为控制、`/memory.json` API
- `model.py`: novelty 门控视觉增益、escape_mode 去极化
- `web/memory-heatmap.js`: 50×50 网格热力图 canvas

### Stuck 诊断与修复 (v2)
- **根因**: Y=-221（低于地面），马里奥掉出世界边缘
- **修复**: StuckDetector 新增 Y 轴异常检测（`pos_y < -100 ∨ > 1000 → fallen`）
- **FailureMemory**: 记录坠落位置，`avoid_direction()` 偏转逃脱方向避开已知坠落点
- **Fallen Recovery**: 特殊恢复模式 → 跳跃 + 前进 + 持续跳跃直至回到地面
- **Escape 优化**: 交替转向(0.8s) + 前进(0.8s) 循环，避免 y=0 死锁

### 轨迹回放页 (trajectory.html)
- Three.js 3D 轨迹显示 (CDN r160)
- OrbitControls 自由视角
- 等比例缩放 (球体/箭头自适应轨迹范围)
- 缩略图/全屏切换 (🗖 按钮)
- 0.5x 默认播放速度
- 文件选择器 (Live + 历史 .trajectory.npz)
- `__live__` 回退加载实时 /trajectory.json

### API 扩展 (main.py)
- GET /trajectory-list.json — 列出 artifacts/*.trajectory.npz
- GET /trajectory-load?file=xxx — 加载指定历史轨迹

### 注意事项
1. **页面文件更新后需重启脑模型**（HTTP 服务缓存文件到内存）
2. brain model 用 `pkill -f 'python.*main'` 重启
3. SM64 用 `pkill -f 'sm64\.us'` 重启
4. 轨迹数据通过 bridge.frame_metadata["pose"] 采集
5. 保存的 .trajectory.npz 需在脑模型退出时生成