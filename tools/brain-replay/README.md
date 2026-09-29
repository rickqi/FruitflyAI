# Fly64 决策过程回放浏览器

读取 Fly64 脑模型的决策 trace 日志（`fly64/runtime/mbon_eval.csv` + `fly64/skills/coach_outcomes.jsonl`），
时间轴回放 MBON 通道 / 多巴胺 / 决策事件 / CX 环状态的演化。纯静态网页 + 零依赖 Python server。

## 运行

```bash
python export_trace.py   # 日志 -> web/trace.json
python server.py         # http://127.0.0.1:8787/
```

数据更新后可直接访问 `/api/export` 重新导出，然后刷新页面。

## 界面

- **MBON 时间序列**：punch/dive/groundpound/longjump 四通道 + dopamine 曲线，红色竖线为 coach 异常事件（anomaly/verdict）
- **CX 16 列吸引子环（示意）**：目前 `cx_risk_compass` 模块尚未输出日志，环用 dopamine 相位 + MBON 平均能量驱动示意；待 CX 日志落地后替换 `drawCx()` 数据源即可
- **控制**：播放 / 单步 / 拖动时间轴；下方明细表显示当前 tick 全部字段

## 接入新数据源

编辑 `export_trace.py`：新增 loader 并在 `trace["ticks"]`（时间对齐的状态行）或 `trace["events"]`（离散事件）中追加字段，
前端即自动随 `trace.mbon_channels` / 明细表扩展。
