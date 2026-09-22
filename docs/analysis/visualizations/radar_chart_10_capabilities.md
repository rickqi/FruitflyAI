## 🎯 Fly64 10大核心能力成熟度 × 泛化潜力雷达图

> **状态**: 🔴 已废弃 (Deprecated)  
> 此可视化文档为 brain-model-deep-expansion 阶段的历史分析产物，内容已过时。

```vega
{
  "$schema": "https://vega.github.io/schema/vega/v6.json",
  "width": 500, "height": 500, "padding": 60,
  "autosize": {"type": "none", "contains": "padding"},
  "signals": [{"name": "radius", "update": "width / 2.5"}],
  "data": [
    {
      "name": "table",
      "values": [
        {"dim": "LIF SNN引擎", "val": 100, "cat": "Fly64基线成熟度"},
        {"dim": "复眼视觉管道", "val": 100, "cat": "Fly64基线成熟度"},
        {"dim": "蘑菇体学习", "val": 95, "cat": "Fly64基线成熟度"},
        {"dim": "CX导航系统", "val": 95, "cat": "Fly64基线成熟度"},
        {"dim": "异常检测系统", "val": 90, "cat": "Fly64基线成熟度"},
        {"dim": "自我进化闭环", "val": 85, "cat": "Fly64基线成熟度"},
        {"dim": "感官融合", "val": 80, "cat": "Fly64基线成熟度"},
        {"dim": "LLM教官", "val": 85, "cat": "Fly64基线成熟度"},
        {"dim": "可观测性", "val": 90, "cat": "Fly64基线成熟度"},
        {"dim": "mmap桥接", "val": 80, "cat": "Fly64基线成熟度"},
        {"dim": "LIF SNN引擎", "val": 100, "cat": "7大核心域平均泛化潜力"},
        {"dim": "复眼视觉管道", "val": 77, "cat": "7大核心域平均泛化潜力"},
        {"dim": "蘑菇体学习", "val": 86, "cat": "7大核心域平均泛化潜力"},
        {"dim": "CX导航系统", "val": 80, "cat": "7大核心域平均泛化潜力"},
        {"dim": "异常检测系统", "val": 100, "cat": "7大核心域平均泛化潜力"},
        {"dim": "自我进化闭环", "val": 100, "cat": "7大核心域平均泛化潜力"},
        {"dim": "感官融合", "val": 83, "cat": "7大核心域平均泛化潜力"},
        {"dim": "LLM教官", "val": 91, "cat": "7大核心域平均泛化潜力"},
        {"dim": "可观测性", "val": 100, "cat": "7大核心域平均泛化潜力"},
        {"dim": "mmap桥接", "val": 80, "cat": "7大核心域平均泛化潜力"},
        {"dim": "LIF SNN引擎", "val": 90, "cat": "6大新领域平均泛化潜力"},
        {"dim": "复眼视觉管道", "val": 70, "cat": "6大新领域平均泛化潜力"},
        {"dim": "蘑菇体学习", "val": 87, "cat": "6大新领域平均泛化潜力"},
        {"dim": "CX导航系统", "val": 73, "cat": "6大新领域平均泛化潜力"},
        {"dim": "异常检测系统", "val": 97, "cat": "6大新领域平均泛化潜力"},
        {"dim": "自我进化闭环", "val": 100, "cat": "6大新领域平均泛化潜力"},
        {"dim": "感官融合", "val": 90, "cat": "6大新领域平均泛化潜力"},
        {"dim": "LLM教官", "val": 90, "cat": "6大新领域平均泛化潜力"},
        {"dim": "可观测性", "val": 97, "cat": "6大新领域平均泛化潜力"},
        {"dim": "mmap桥接", "val": 67, "cat": "6大新领域平均泛化潜力"}
      ]
    },
    {
      "name": "grid",
      "values": [
        {"r": 20}, {"r": 40}, {"r": 60}, {"r": 80}, {"r": 100}
      ]
    }
  ],
  "scales": [
    {"name": "angular", "type": "point", "range": {"signal": "[-PI/2, 3*PI/2]"}, "padding": 0.5, "domain": {"data": "table", "field": "dim"}},
    {"name": "radial", "type": "linear", "range": {"signal": "[0, radius]"}, "zero": true, "domain": [0, 100]},
    {"name": "color", "type": "ordinal", "domain": ["Fly64基线成熟度", "7大核心域平均泛化潜力", "6大新领域平均泛化潜力"], "range": ["#2d5a2d", "#3b82f6", "#f59e0b"]}
  ],
  "encode": {"enter": {"x": {"signal": "radius + 60"}, "y": {"signal": "radius + 60"}}},
  "marks": [
    {
      "type": "group",
      "from": {"facet": {"data": "table", "name": "facet", "groupby": ["cat"]}},
      "marks": [
        {
          "type": "line",
          "from": {"data": "facet"},
          "encode": {
            "enter": {
              "interpolate": {"value": "linear-closed"},
              "x": {"signal": "scale('radial', datum.val) * cos(scale('angular', datum.dim)) + radius + 60"},
              "y": {"signal": "scale('radial', datum.val) * sin(scale('angular', datum.dim)) + radius + 60"},
              "stroke": {"scale": "color", "field": "cat"},
              "strokeWidth": {"value": 2.5},
              "fill": {"scale": "color", "field": "cat"},
              "fillOpacity": {"value": 0.08}
            }
          }
        },
        {
          "type": "symbol",
          "from": {"data": "facet"},
          "encode": {
            "enter": {
              "x": {"signal": "scale('radial', datum.val) * cos(scale('angular', datum.dim)) + radius + 60"},
              "y": {"signal": "scale('radial', datum.val) * sin(scale('angular', datum.dim)) + radius + 60"},
              "fill": {"scale": "color", "field": "cat"},
              "size": {"value": 40}
            }
          }
        }
      ]
    },
    {
      "type": "text",
      "from": {"data": "table"},
      "encode": {
        "enter": {
          "x": {"signal": "(radius + 8) * cos(scale('angular', datum.dim)) + radius + 60"},
          "y": {"signal": "(radius + 8) * sin(scale('angular', datum.dim)) + radius + 60"},
          "text": {"field": "dim"},
          "fontSize": {"value": 10},
          "fontWeight": {"value": "bold"},
          "fill": {"value": "#333"},
          "align": {"signal": "scale('angular', datum.dim) > 0 ? 'left' : 'right'"},
          "baseline": {"signal": "abs(scale('angular', datum.dim)) < 0.2 ? 'bottom' : 'middle'"}
        }
      }
    }
  ],
  "legends": [
    {
      "fill": "color",
      "title": "能力评估维度",
      "offset": 10,
      "encode": {
        "symbols": {"enter": {"fillOpacity": {"value": 0.8}}}
      }
    }
  ]
}
```

**源数据**: t1_deep_technical_migration_plan.md §9.1 代码复用度 + t2_new_domain_exploration_report.md §5.1 跨领域能力迁移矩阵  
**评分标准**: ★★★★★=100, ★★★★☆=80, ★★★☆☆=60, ★★☆☆☆=40, ★☆☆☆☆=20  
**关键发现**: 自我进化闭环(★100)和异常检测系统(★97-100)是所有13个域中最通用的能力；mmap桥接在新领域泛化最弱(★67)