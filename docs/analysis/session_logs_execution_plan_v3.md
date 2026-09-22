# Fly64 下一步执行计划 v3 — 基于对话日志分析

> **来源**: `docs/analysis/session_logs_analysis_v3.md`（11 session / 959 真实提问 / 35 团队）  
> **生成日期**: 2026-09-22  
> **当前版本**: Brain **v2.23.12** · Skill **v3.5.0** · 89 测试文件 · 79 条进化记录  
> **核心原则**: **先验证刚修好的链路，再开发新能力**——当前最大风险是"修了一堆但没证明有效"

---

## 目录

- [背景：为什么是这个计划](#背景为什么是这个计划)
- [P0 级：立即验证（1–2 天）](#p0-级立即验证12-天)
- [P1 级：高优先（3–7 天）](#p1-级高优先37-天)
- [P2 级：中优先（1–3 周）](#p2-级中优先13-周)
- [依赖关系图](#依赖关系图)
- [执行顺序建议](#执行顺序建议)

---

## 背景：为什么是这个计划

2026-09-22 有**两个关键修复刚落地**，但**都还没有端到端实测**：

| 修复 | 提交 | 解决的问题 | 验证状态 |
|------|------|-----------|---------|
| 探索三重死锁 | `5c86272` | escape-override-reflex 死锁 → 200t burst + cx_novelty recovery | ❌ 未实测 |
| EVO-072 键名归一化 | `879d983` | **Coach/EVO 写入的值从未真正生效** | ❌ 未实测 |

同时发现**参数系统存在同类缺陷**：

| 问题 | 提交 | 说明 |
|------|------|------|
| 5 个参数是"死参数" | `ea509a9` | 注册在 escape.*/reflex.*，实际从 _expl 镜像，面板 POST 到不了消费者 |
| 参数被互相覆盖 | `61e1e0d` | EVO/plugin 覆盖参数文件 → 加 12s 自愈回写 |

**用户的最后一次抱怨是"coach 建议未生效，未脱困"**（S5:35 上下文）——这恰好是上述修复的靶心。因此 P0 全部围绕"证明它真的修好了"。

---

## P0 级：立即验证（1–2 天）

### P0-1: Coach 六段链路端到端实测

| 属性 | 值 |
|------|-----|
| **优先级** | P0 — 阻塞判断 |
| **风险** | 🔴 HIGH — 不知道刚修的 EVO-072 是否真解决问题 |
| **前置依赖** | 无 |
| **预估** | 0.5 天 |

#### 要验证的六段链路

```
① 触发      stuck>60s AND anomaly AND no_reflex
            或 help_score ≥ 0.60（多信号加权）
                    ↓
② LLM 调用   GLM-5v-turbo 多模态咨询（http 传输）
            ⚠ 曾报 400 Missing `reasoning_content`
                    ↓
③ 截屏       /screen.json → base64 → 教练可见
            ⚠ 曾失真为"屏幕一部分"
                    ↓
④ 写盘       skills/active_strategy.json
            ⚠ 曾与 EVO 互相覆盖
                    ↓
⑤ 加载       main.py 每 600 tick 热加载
            ⚠ 曾因键名不匹配（点号前缀）静默失效 ← EVO-072 修复点
                    ↓
⑥ 行为       /flow.json coach_applied 反映实际参数
            多巴胺/转向偏置真正改变输出
```

#### 实施步骤

**步骤 1：准备可复现的卡死场景**

```bash
# 启动脑模型 + SM64（WSL）
cd /root/fly64
./scripts/consolidate.sh
# 确认服务在线
curl -s http://127.0.0.1:8765/memory.json | python -m json.tool | head -20
```

**步骤 2：启动教练服务并记录全链路日志**

```bash
PYTHONPATH=. nohup python3 -m plugin.service --interval 10 \
  >> plugin/service.log 2>&1 &
# 记录写入前的 active_strategy.json
cp skills/active_strategy.json /tmp/strategy_before.json
```

**步骤 3：注入教练策略，验证加载链路**

```bash
# 用测试值直接写入，确认 main.py 能加载（隔离 ⑤ 段）
curl -X POST http://127.0.0.1:8765/active_strategy-update \
  -H 'Content-Type: application/json' \
  -d '{"updates": {"exploration.turn_bias": 0.8}}'
# 等待 ≥600 tick（~12s）后检查
curl -s http://127.0.0.1:8765/flow.json | python -c \
  "import json,sys; d=json.load(sys.stdin); print('coach_applied:', d.get('coach_applied'))"
```

**步骤 4：触发真实求助，观察全链路**

- 等待 stuck > 60s 且无反射 → 教练应自动介入
- 检查 `plugin/service.log` 是否有 consult 记录
- 检查 `runtime/coach_frames/` 是否有新截图
- 检查 `skills/coach_advice.json` 内容
- 对比 `/memory.json` 的 `coach_applied` 与 `active_strategy.json`

#### 成功标准

- [ ] 六段链路每段都有**日志或端点证据**
- [ ] `active_strategy.json` 写入的值出现在 `/memory.json` 的 `coach_applied`
- [ ] 教练建议的转向/前进偏置在 `/flow.json` 中有可观测变化
- [ ] 截图完整（非"屏幕一部分"），可在 `/coach_frames` 打开
- [ ] 产出 `docs/analysis/coach-chain-verification.md` 记录

---

### P0-2: 探索/脱困效果量化基线

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **前置依赖** | 无（可与 P0-1 并行） |
| **预估** | 0.5–1 天 |

#### 实施步骤

**步骤 1：连续运行并采集**

```bash
# 连续运行 30–60 分钟，采集关键指标
python3 - <<'PY'
import urllib.request, json, time
samples = []
for i in range(360):  # 60 min @ 10s
    try:
        m = json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json", timeout=5))
        f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json", timeout=5))
        samples.append({
            "t": time.time(),
            "stuck": m.get("stuck_duration"),
            "coverage": m.get("coverage_pct"),
            "health": m.get("health_score"),
            "anomaly": m.get("anomaly_state"),
            "loop": m.get("loop_score"),
            "decision": f.get("decision_source"),
        })
    except Exception as e:
        pass
    time.sleep(10)
json.dump(samples, open("/tmp/explore_baseline.json","w"), indent=2)
PY
```

**步骤 2：计算关键指标**

| 指标 | 定义 | 目标 |
|------|------|------|
| 覆盖率增速 | cells/min | 对比修复前基线 |
| 最长 stuck 时长 | max(stuck_duration) | 显著低于历史 162s+ |
| 脱困成功率 | 离开 stuck 的次数 / 进入次数 | > 50% |
| 动作多样性 | distinct(decision_source) | 从 1–2 种提升 |
| 死锁复发 | escape-override-reflex 循环次数 | 应为 0 |

#### 成功标准

- [ ] 产出 `docs/analysis/exploration-baseline-2026-09.md` 含上述 5 项指标
- [ ] 与修复前（README 记录）对比表
- [ ] 明确"哪些指标达标、哪些未达标"

---

### P0-3: 39 参数生效性批量校验

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **风险** | 🔴 HIGH — 已发现 5 个死参数，同类可能还有 |
| **预估** | 0.5 天 |

#### 实施步骤

**步骤 1：编写批量校验脚本**

```python
# scripts/verify_param_wiring.py
"""对 brain_tunable_params.json 的每个参数 POST 极端值，
   验证 /flow.json 或 /memory.json 出现可观测变化。"""
import json, urllib.request, time

params = json.load(open("fly64/skills/brain_tunable_params.json"))
base = "http://127.0.0.1:8765"

def snapshot():
    f = json.load(urllib.request.urlopen(base + "/flow.json", timeout=5))
    m = json.load(urllib.request.urlopen(base + "/memory.json", timeout=5))
    return {**f, **m}

for section, entries in params.get("sections", {}).items():
    for name, spec in entries.items():
        key = f"{section}.{name}"
        before = snapshot()
        lo, hi = spec.get("range", [None, None])
        for probe in (lo, hi):
            if probe is None:
                continue
            body = json.dumps({"updates": {key: probe}}).encode()
            req = urllib.request.Request(
                base + "/active_strategy-update", data=body,
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            time.sleep(13)  # wait for 600-tick hot reload
            after = snapshot()
            changed = [k for k in before if before.get(k) != after.get(k)]
            print(f"{key}={probe} -> changed: {changed[:5]}")
```

**步骤 2：执行并归档**

```bash
python scripts/verify_param_wiring.py | tee /tmp/param_wiring_report.txt
```

#### 成功标准

- [ ] 39/39 参数产出具名报告（生效 / 未生效）
- [ ] 每个"未生效"参数定位到具体原因（键名错 / 无消费者 / 被覆盖）
- [ ] 未生效者提 issue 并回归测试

---

## P1 级：高优先（3–7 天）

### P1-1: 测试基线噪声清单

| 属性 | 值 |
|------|-----|
| **预估** | 1 天 |
| **依据** | EVO-068 记录："Windows 套件长期带约 40 个未分类失败，真实回归会被淹没" |

**步骤**：
1. 运行全量套件：`python3 -m pytest -q --tb=no 2>&1 | tee /tmp/pytest_full.txt`
2. 把每个失败归类为 `real-bug` / `test-drift` / `env-specific`
3. 写入 `fly64/tests/KNOWN_FAILURES.md`（含分类理由）
4. 接入 CI：输出"0 未知失败"才算通过

**成功标准**：
- [ ] 所有失败有明确分类
- [ ] CI 输出区分"已知噪声"与"新回归"
- [ ] 新回归会 fail CI

---

### P1-2: 启动契约自动校验

| 属性 | 值 |
|------|-----|
| **预估** | 0.5–1 天 |
| **依据** | SM64 显示问题反复出现（S5:5,20–26；S3:61；`d04264e`） |

**步骤**：编写 `scripts/verify_launch_contract.sh`，一键检查：

| # | 检查项 | 判定 |
|---|--------|------|
| 1 | SM64 进程存活 | `pgrep -f "sm64.us"` |
| 2 | 桥接文件新鲜度 | mtime < 5s |
| 3 | 脑模型进程存活 | `pgrep -f fly64.main` |
| 4 | Dashboard 可达 | `curl /evolution.json` |
| 5 | brain_version 一致 | main.py vs /flow.json |
| 6 | 窗口可见性 | `xdotool search --name 'Super Mario'` |

**成功标准**：
- [ ] 单命令输出 6 项检查结果
- [ ] 失败项给出明确修复指引
- [ ] 接入 `consolidate.sh` 启动后自动校验

---

### P1-3: 视觉能力行为层验证（R8 + R9）

| 属性 | 值 |
|------|-----|
| **预估** | 2–3 天 |
| **依据** | `docs/vision-coverage-analysis-t3.md`：颜色/UV ≈95% 完成，小目标追踪 ≈80%，多巴胺学习 ≈85% 但被 P0-2/P0-3 阻塞 |

**步骤**：
1. **R8 小目标追踪行为验证**：确认 LIF split-injection 修复生效，构造小目标场景验证行为响应
2. **R9 多巴胺学习全栈测试**：先修 P0-2 MBON 饱和 + P0-3 阈值错误，再启用全栈

**成功标准**：
- [ ] 小目标追踪有行为层证据（非仅单元测试）
- [ ] 多巴胺学习端到端可用
- [ ] 视觉覆盖度从 ~50% 有可量化提升

---

### P1-4: 社交求助（SEEK-HELP）端到端验证

| 属性 | 值 |
|------|-----|
| **预估** | 1 天 |
| **依据** | S8:15,16,17 明确"超出果蝇脑能力 → LLM 教学能力"；S8:50 抱怨"为什么没有给 GLM 教练提示建议" |

**步骤**：
1. 构造语义场景（钥匙门 / 对话提示）
2. 验证：场景识别 → 求助触发 → LLM 咨询 → 建议执行
3. 确认降级路径（LLM 不可用时写 `local_diagnosis`）

**成功标准**：
- [ ] 语义场景触发求助的完整证据链
- [ ] LLM 降级路径可用
- [ ] 文档化"哪些场景必须求助、哪些内生可解"

---

## P2 级：中优先（1–3 周）

| # | 行动 | 依据 | 预估 |
|---|------|------|------|
| **P2-1** | 语义/文字识别接入（OCR → 教练层） | S10:241 已提方案 | 3–4 天 |
| **P2-2** | FlyGym 端到端运行（非仅单元测试） | `fly64/analysis/t2-flygym-e2e-integration-analysis.md` 路线图 | 8–11 人天 |
| **P2-3** | CX + EMD 集成（运动流增强锚点重定位） | `next_challenge_analysis_report.md` | 2–3 天 |
| **P2-4** | 重复探索惩罚机制强化 | S1:67 "低效探索应被惩罚" | 2–3 天 |
| **P2-5** | 参数契约审计制度化（防死参数复发） | EVO-066 已有 `audit_contract_pair` 雏形 | 1–2 天 |

---

## 依赖关系图

```
P0-1 (Coach 六段链路实测)
  └── 无前置；是 P1-4 的前置（验证求助链）

P0-2 (探索效果基线)
  └── 无前置；为 P1-3 提供行为基线

P0-3 (39 参数生效性校验)
  └── 无前置；是 P2-5 的输入

P1-1 (测试噪声清单)
  └── 无前置（独立）

P1-2 (启动契约校验)
  └── 无前置（独立）

P1-3 (视觉行为层验证)
  └── 依赖 P0-2（需要行为基线对比）

P1-4 (社交求助验证)
  └── 依赖 P0-1（复用链路验证方法）

P2-1..P2-5
  └── 依赖对应 P1 完成
```

---

## 执行顺序建议

### 第一波：并行验证（Day 1–2）

```
  ├── P0-1 (Coach 链路实测)      ← 最关键，直接回应用户抱怨
  ├── P0-2 (探索效果基线)         ← 可与 P0-1 并行
  └── P0-3 (参数生效性校验)       ← 可与 P0-1 并行
```

### 第二波：治理与验证（Day 3–7）

```
  ├── P1-1 (测试噪声清单)         ← 独立
  ├── P1-2 (启动契约校验)         ← 独立
  ├── P1-3 (视觉行为层验证)       ← 依赖 P0-2
  └── P1-4 (社交求助验证)         ← 依赖 P0-1
```

### 第三波：能力扩展（Week 2–3）

```
  ├── P2-1 (OCR 接入)
  ├── P2-3 (CX + EMD 集成)
  ├── P2-4 (重复探索惩罚)
  ├── P2-5 (参数契约审计制度化)
  └── P2-2 (FlyGym 端到端)
```

### 工作量估算

| 阶段 | 时间 | 并行度 | 说明 |
|------|------|--------|------|
| 第一波 | 1–2 天 | 3 并行 | 全部是验证型任务，风险低 |
| 第二波 | 3–5 天 | 2–4 并行 | 治理 + 行为验证 |
| 第三波 | 1–3 周 | 2–3 并行 | 能力扩展 |
| **P0+P1 合计** | **~1 周** | | **建议先做完 P0+P1 再评估 P2** |

---

## 判断下一步是否成功的三个问题

做完 P0 后，应该能明确回答：

1. **Coach 建议真的影响行为了吗？** → P0-1 给出证据
2. **马里奥真的更少转圈、更多探索了吗？** → P0-2 给出数据
3. **还有多少参数是"注册了但不生效"的？** → P0-3 给出清单

如果三个答案都是肯定的，再进入 P1/P2 开发新能力。

---

> **生成**: 2026-09-22  
> **依据**: `docs/analysis/session_logs_analysis_v3.md`  
> **当前版本**: Brain v2.23.12 · Skill v3.5.0  
> **保存位置**: `docs/analysis/session_logs_execution_plan_v3.md`
