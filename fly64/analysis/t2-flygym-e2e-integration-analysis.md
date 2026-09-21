# P0-B: FlyGym 端到端集成根因分析报告

> **分析师**: analyst-b | 团队: fly64-challenge-analysis  
> **任务**: t2 [A2] — FlyGym 端到端集成根因分析  
> **日期**: 2026-09-19  
> **版本**: 1.0

---

## 目录

1. [FlyGym 版本兼容性](#1-flygym-版本兼容性)
2. [CpgGait/FlyGymBrainEnv ↔ SM64 脑模型切换缺口](#2-cpggaitflygymbrainenv--sm64-脑模型切换缺口)
3. [视觉适配器评估](#3-视觉适配器评估)
4. [控制流集成方案](#4-控制流集成方案)
5. [测试覆盖范围缺口](#5-测试覆盖范围缺口)
6. [端到端集成实施路线图与风险评估](#6-端到端集成实施路线图与风险评估)

---

## 1. FlyGym 版本兼容性

### 1.1 当前安装版本: v1.2.1

**检测结果**：系统当前安装的是 `flygym==1.2.1`，不是最新的 v2.x。

### 1.2 v1.2.1 公开 API 概览

| API 模块 | 可用成员 |
|---------|---------|
| `flygym.Fly` | `enable_vision`, `render_raw_vision` 参数支持 |
| `flygym.SingleFlySimulation` | `reset(seed, options)`, `step(action)` → `(obs, reward, terminated, truncated, info)` |
| `flygym.arena` | `FlatTerrain`, `BlocksTerrain`, `MixedTerrain`, `GappedTerrain`, `OdorArena` |
| `flygym.get_data_path()` | 数据路径访问 |

### 1.3 当前代码实际使用的 API（`flygym_env.py`）

当前 `FlyGymBrainEnv` 使用的 API 在 v1.2.1 上完整可用：
- ✅ `flygym.Fly(enable_vision=..., render_raw_vision=...)` — 存在
- ✅ `flygym.SingleFlySimulation(fly=..., arena=..., timestep=...)` — 存在
- ✅ `.reset(seed=...)` / `.step(action=...)` — 兼容 Gym API
- ✅ `.close()` — 存在
- ✅ `info['raw_vision']` — v1.2.1 中可用，shape `(2, 512, 450, 3)`

### 1.4 v1.2.1 与 v2.x 的关键差异

| 特性 | v1.2.1 (当前) | v2.x (未安装) | 影响 |
|------|---------------|---------------|------|
| Gym API 基类 | Gym v0.21+ | Gymnasium | step() 返回签名兼容 |
| 视觉管线 | raw_vision dict key | 可能重构为 obs key | 需要验证 |
| 物理后端 | MuJoCo 2.3.x | MuJoCo 3.x | 行为可能变化 |
| 地形 API | 直接导入 | 包结构可能调整 | 低风险 |
| 果蝇模型 | 42-DOF 标准模型 | 可能扩展 | 42 维兼容 |

**结论**：当前代码在 v1.2.1 上完全可运行。迁移到 v2.x 需要验证 `raw_vision` 键名和 `step()` 返回值签名是否变化，但**不构成当前阻塞**。

---

## 2. CpgGait/FlyGymBrainEnv ↔ SM64 脑模型切换缺口

### 2.1 当前架构现状

```
┌─────────────────────────────────────────────────────────┐
│                    main.py 主循环                        │
│                                                         │
│  ┌──────────────────┐     ┌────────────────────────┐   │
│  │    SM64 Bridge     │     │   FlyModel (LIF 脑)   │   │
│  │                    │     │                        │   │
│  │ bridge.read_frame()│────▶│ model.step(frame, ...) │   │
│  │ bridge.write_ctrl()│◀────│ control = ...          │   │
│  └──────────────────┘     └────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │    FlyGymBrainEnv (独立环境, 未被集成到主循环)     │   │
│  │                                                  │   │
│  │  env.reset() → obs      env.step(fwd, turn)      │   │
│  │  flygym_to_luminance() → 2-element luminance     │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 关键缺口分析

#### 缺口 G1: 视觉数据格式不兼容

| 维度 | SM64 桥接 | FlyGym 环境 |
|------|----------|------------|
| 图像源 | `bridge.read_frame()` → 384×256×3 cubemap atlas | `info['raw_vision']` → `(2, 512, 450, 3)` 双视角 |
| 视觉管线 | `model.encode_retina(atlas, heading)` → SphericalRetina | `flygym_to_luminance()` → `2-element` 平均亮度 |
| 采样网格 | `visual_pixels` (1536 点) 映射到 atlas 384×256 | 无对应 |
| 视网膜采样 | `cone_indices()` 在球面进行 7-sample 加权采样 | 无 |

#### 缺口 G2: 运动输出格式不兼容

| 维度 | SM64 控制 | FlyGym 控制 |
|------|----------|------------|
| 输出接口 | `bridge.write_control(x, y, jump, b, z)` | `env.step(forward_mod, turn_mod)` |
| 控制域 | x: [-80, 80], y: [0, 80] | forward_mod: [0,1], turn_mod: [-1,1] |
| 映射方式 | 直接 N64 手柄值 | CPG 幅度调制 |
| 跳跃 | 布尔 A 键 | 隐式通过腿摆动 |

#### 缺口 G3: 无运行时切换机制

`main.py` 硬编码了 SM64 主循环：
- `bridge.read_frame()` → 无抽象层包装视觉源
- `bridge.write_control()` → 无抽象层包装控制输出
- 不存在 `VisionSource` / `MotorTarget` 接口让主循环在不修改代码的情况下切换环境

### 2.3 根因

FlyGym 集成是**作为独立验证环境实现的**（见 `environments/__init__.py` 文档："Provides alternative simulation environments to the primary SM64 interface"），而不是作为可以插入主循环的替换视觉-运动管道。三个组件——视觉适配器（`flygym_to_luminance` → 2 元素亮度）、CPG 步态生成器和 `FlyGymBrainEnv` 生命周期——都是为了**独立测试/验证**而设计的，没有遵循使它们可作为主循环替代品插入的抽象接口。

---

## 3. 视觉适配器评估: `flygym_to_luminance()`

### 3.1 当前实现

```python
def flygym_to_luminance(raw_vision: np.ndarray) -> np.ndarray:
    """Convert FlyGym raw vision to 2-element per-eye luminance."""
    raw = np.asarray(raw_vision, dtype=np.float32)
    if raw.ndim == 4 and raw.shape[-1] == 3:
        lum = raw[..., 0] * 0.2126 + raw[..., 1] * 0.7152 + raw[..., 2] * 0.0722
        return np.array([lum[i].mean() for i in range(min(2, raw.shape[0]))],
                        dtype=np.float32)
    return np.zeros(2, dtype=np.float32)
```

### 3.2 降采样对比

| 属性 | FlyGym 输出 | Fly64 视网膜期望 |
|------|------------|-----------------|
| 输入形状 | `(2, 512, 450, 3)` | 384×256×3 cubemap atlas |
| 输出元素 | 2（每眼一个平均亮度值） | 1536 个细胞 × 7 通道 = 10752 个值 |
| 空间信息 | **完全丢失** | 保留 270° 方位角 × 144° 仰角 |
| 颜色 | 仅亮度（BT.709 加权） | 7 通道（R, G, B, UV_approx, H, S, V） |
| 运动检测 | 无 | EMD（4 方向） |
| 小目标 | 无 | 连接分量标记 |

### 3.3 定量差距

当前适配器丢弃了 **>99.9% 的视觉信息**：
- 输入: `2 × 512 × 450 × 3 = 1,382,400` 字节
- 输出: `2` 个浮点值（每个眼球一个标量亮度均值）
- 压缩比: **691,200:1**

虽然这对于某些低等动物的视觉处理来说可能足够，但对于 Fly64 的复杂视觉处理管线（涉及 1536 个视觉采样细胞 × 7 个颜色/亮度/UV 通道 + 4 方向 EMD + 小目标跟踪 + 场景识别）来说完全不够。

### 3.4 根本缺口

FlyGym 的双视角渲染（每眼 512×450）与 Fly64 所需的 384×256 cubemap atlas 之间有**根本性的几何不匹配**：
- FlyGym: 每只果蝇复眼的 2× 正交视图 → 提供真实的生物视觉几何
- Fly64: SM64 的 6 面立方体贴图渲染 → 专为 SM64 的全景渲染而设计

没有直接的逐像素映射；正确的集成需要：
1. 将 FlyGym 双视角渲染为伪立方体贴图进行 retina 采样，或者
2. 为 FlyGym 构建独立的视网膜采样网格（使用实际果蝇眼睛角度）

---

## 4. SM64 主循环的控制流集成方案

### 4.1 当前架构

```
main.py 中的 while 循环:
    1. bridge.read_frame()                    ← 硬编码 SM64
    2. model.encode_retina(frame, heading)    ← 需要 384×256×3 atlas
    3. model.step(frame, now, ...)            ← LIF 推理 + 运动池
    4. bridge.write_control(x, y, jump, ...)  ← 硬编码 SM64
```

### 4.2 建议的抽象层

为了消除切换缺口，应该引入**两个抽象接口**，使主循环能够在 SM64 和 FlyGym 之间切换，只需在启动时修改配置：

```python
class VisionSource(ABC):
    """主循环消耗视觉输入的抽象"""
    @abstractmethod
    def get_frame(self) -> np.ndarray:
        """返回 384×256×3 uint8 atlas 供 retina 处理"""
        ...

class MotorTarget(ABC):
    """主循环产生运动输出的抽象"""
    @abstractmethod
    def apply_control(self, control: Control) -> None:
        ...
```

### 4.3 两个适配器

```python
class SM64BridgeAdapter(VisionSource, MotorTarget):
    """当前硬编码行为的包装器"""
    def get_frame(self):
        seq, pixels = bridge.read_frame()
        return np.frombuffer(pixels, uint8).reshape(256, 384, 3) 
    def apply_control(self, control):
        bridge.write_control(control.x, control.y, control.jump, ...)

class FlyGymAdapter(VisionSource, MotorTarget):
    """FlyGym 环境的包装器"""
    def __init__(self, env: FlyGymBrainEnv):
        self.env = env
        self._atlas_buffer = np.zeros((256, 384, 3), uint8)
    def get_frame(self):
        # 选项 A: 直接使用渲染的帧并重新投影到 atlas
        # 选项 B: 使用适配的 retina（见下文）
        return self._atlas_buffer
    def apply_control(self, control):
        fwd = max(0.0, min(1.0, control.y / 80.0))
        turn = max(-1.0, min(1.0, control.x / 80.0))
        self.env.step(forward_mod=fwd, turn_mod=turn)
```

### 4.4 集成场景

当前架构可以支持三种集成模式：

| 模式 | 视觉 | 运动 | 用例 |
|------|------|------|------|
| **完整 SM64** | SM64 cubemap → retina | bridge.write_control() | 生产环境 |
| **完整 FlyGym** | FlyGym 帧→适配的 retina | env.step(fwd, turn) | 验证 P3-2 |
| **混合** | SM64 | env.step(...) | 组件测试 |

---

## 5. 测试覆盖范围缺口

### 5.1 当前测试库存（24 个测试仅覆盖单元级别）

对 `test_verify_scenario.py`（24 个测试函数）的审计显示：

| 测试类别 | 计数 | 范围 | 限制 |
|----------|------|------|------|
| CpgGait 单元 | 5 | 关节计数、有限值、转向、幅值、相位 | 无模拟器回环 |
| FlyGymBrainEnv 生命周期 | 6 | reset、step、关闭、多次重置、向前速度 | 无渲染、无步进后验证 |
| 视觉适配器 | 3 | 形状、一致性、亮度对比 | 仅 2 元素亮度输出 |
| 脑模型集成 | 6 | 亮度 + 暗帧 EMD + 合成控制 | 使用 `demo=True` 模型，非完全 SM64 集成 |
| 端到端 | 3 | 可导入性、加载 | 无真正的端到端测试 |
| 占位符 | 1 | 文档字符串 | 无功能断言 |

### 5.2 严重缺口

| 缺口 ID | 缺失的测试 | 影响 |
|---------|-----------|------|
| TC1 | 脑模型在 FlyGym 输入下的全闭环 | 无验证脑模型是否可以通过视觉管道实际控制飞行器 |
| TC2 | `flygym_to_luminance()` 全分辨率渲染 | 仅使用合成随机数据测试；无真实渲染管道验证 |
| TC3 | SM64 ↔ FlyGym 切换机制 | 切换逻辑不存在，因此不可测试 |
| TC4 | 两种环境的性能基准测试 | 无关于推理延迟、帧率、可达到的步进速度的数据 |
| TC5 | 回归测试套件同时针对 SM64 和 FlyGym | 脑模型更改可能会破坏 FlyGym 集成而无需任何通知 |
| TC6 | `main.py` 参数集成测试 | 无验证命令行参数是否选择环境 |
| TC7 | 视觉适配器下游影响 | 适配器将视觉数据减少到 2 个浮点值；无测试验证这对行为有何影响 |
| TC8 | FlyGym 渲染性能 | 渲染将 CPU 工作量增加约 10 倍；无测试验证此开销是否可持续 |

### 5.3 根本原因

集成范围测试的缺乏源于**根本的设计选择**：FlyGym 是事后才作为验证环境添加的，而不是从一开始就计划作为主循环替代方案。视觉适配器和 CPG 是为了**证明概念**而编写的——而不是作为生产就绪的集成层。

---

## 6. 端到端集成实施路线图与风险评估

### 6.1 建议方法：分 3 个阶段

#### 第一阶段：抽象层（2–3 天，风险低）

| 步骤 | 描述 | 产出 |
|------|------|------|
| S1 | 定义 `VisionSource` 和 `MotorTarget` 抽象接口 | `environments/base.py` |
| S2 | 创建 `SM64BridgeAdapter` 包装现有逻辑 | 零行为变化 |
| S3 | 重构 `main.py` 以使用适配器而不是硬编码的桥接调用 | 主循环变得与环境无关 |
| S4 | 添加 `--environment` CLI 参数（默认 `sm64`） | 运行时可选择 |
| S5 | 添加单元测试以验证适配器合约 | 测试覆盖率缺口部分填补 |

**风险**：重构可能引入回归。缓解措施：保留旧代码路径直到新代码通过所有现有测试。

#### 第二阶段：全功能 FlyGym 适配器（3–5 天，风险中等）

| 步骤 | 描述 | 产出 |
|------|------|------|
| S6 | 构建 `FlyGymAdapter` 实现 `VisionSource` + `MotorTarget` | 适配器代码 |
| S7 | 实现选项 A：将 FlyGym `raw_vision`（2×512×450×3）重新投影到 SM64 式 atlas 384×256×3 | 视觉重新投影层 |
| S8 | **替代方案**：构建特定于 FlyGym 的视网膜，使用 `visual_pixels` 直接映射到果蝇的实际眼睛角度 | 独立视觉管道 |
| S9 | 实现选项 B（更好的选项）：计算实际果蝇视网膜角度并直接从 FlyGym 渲染的每眼图像进行采样 | 生物视觉集成 |
| S10 | 实现控制信号重新映射（`Control` → `forward_mod/turn_mod` 转换） | 运动适配 |
| S11 | 验证闭环：脑模型接收 FlyGym 视觉并控制飞行器 ≥1000 步 | 功能验证测试 |

**风险**：
- 选项 A（atlas 重新投影）会丢失生物保真度，但集成速度最快。
- 选项 B（原生视网膜角度）更正确但更复杂。
- **推荐**：从选项 A 开始用于快速验证，然后迭代到选项 B 作为升级版。

#### 第三阶段：测试基础设施 + CI（2–3 天，风险低）

| 步骤 | 描述 | 产出 |
|------|------|------|
| S12 | 添加缺口测试 TC1–TC8 | 完整测试套件 |
| S13 | 添加基准测试（两种环境下的步进时间、FPS） | 性能基线 |
| S14 | 为两种环境模式添加 CI 门控 | CI 门控 |
| S15 | 添加回归测试：环境开关不会破坏行为 | 回归安全网 |

### 6.2 集成风险矩阵

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| **视觉重新投影保真度不足** | 中等 | 高 | 独立验证视觉特征保留；设计选项 B 作为回退 |
| **控制信号映射错误** | 低 | 中等 | 通过视觉/运动闭环测试验证 |
| **FlyGym 渲染性能瓶颈** | 高 | 中等 | 性能基准测试；降低渲染分辨率；定期步骤 |
| **LIF 脑模型推理时序违规** | 低 | 高 | 使用隔离运行中的 `demo=True` 模式进行验证 |
| **脑模型更新使适配器接口失效** | 中等 | 中等 | 适配器合约测试捕获中断 |
| **v1.2.1 → v2.x 迁移破坏 raw_vision** | 低 | 中等 | 延迟到集成稳定后；验证 v1.2.1 |

### 6.3 成功标准

集成被视为**完成**需要：

1. ✅ `main.py` 通过 `--environment` 参数支持 SM64 和 FlyGym
2. ✅ 两种环境的闭环步进验证 ≥1000 步，不会出现视觉/运动错误
3. ✅ 视觉适配器保留足够信息以供视网膜处理和 EMD 运行
4. ✅ 通过控制信号映射验证，CPG 生成有效的腿关节目标
5. ✅ 所有 24 个现有测试通过 + 8 个新集成测试通过
6. ✅ 两种环境的性能基准记录在案（FPS、步进时间、延迟）

### 6.4 执行建议

**推荐顺序**：

```
第 1 周：第 1 阶段 → 第 2 阶段（选项 A）
第 2 周：第 2 阶段（选项 B）→ 第 3 阶段 + 基准测试
第 3 周：集成调试、v2.x 兼容性检查、文档编制
```

**资源**：
- 1 名后端工程师（Python 抽象、main.py 重构）
- 1 名视觉工程师（FlyGym 视觉重新投影/视网膜适配）
- 1 名 QA 工程师（测试缺口填充、基准测试、CI 门控）

**总计**：**8–11 人天**到完整的端到端集成，包含完整的测试覆盖率和性能基线。

---

*报告结束*