# EvolutionSkill — Self-Evolving Motion Diagnosis

**Version**: 2.0.0
**Status**: Active
**Category**: Autonomous Agent / Self-Improvement

## Description

A complete closed-loop pipeline for autonomous motion diagnosis and self-improvement in the Fly64 fruit fly brain-controlled SM64 system. Monitors Mario's motion in real-time, detects behavioral anomaly patterns (circle loops, ramp traps, coverage stagnation), diagnoses root causes, applies code fixes, verifies effectiveness, and auto-updates documentation.

## When to Use

Use this skill when:
- Mario is stuck in a behavioral loop (circling, ramp trap, oscillation)
- Coverage rate is stagnating
- Health score consistently low
- You need automated diagnosis of motion problems
- You want the system to self-improve over time

## How to Use

### Quick Start
```bash
# Run one diagnosis cycle manually
python3 -m fly64.skills.evolution_skill

# Continuous monitoring with auto-fix
python3 -m fly64.skills.evolution_skill --auto-fix --interval 5 --max-iterations 100
```

### Python API
```python
from fly64.skills.evolution_skill import EvolutionPipeline

pipeline = EvolutionPipeline(
    dashboard_url="http://127.0.0.1:8765",
    patterns_path="default_patterns.json",
    auto_fix=True
)
result = pipeline.run_one_cycle()
print(f"Findings: {len(result.findings)}")
print(f"Fix applied: {result.fix_applied}")
```

### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--interval` | 5 | Poll interval in seconds |
| `--window` | 120 | Rolling window in seconds |
| `--auto-fix` | false | Auto-apply generated fixes |
| `--max-iterations` | 10 | Max cycles before stopping |
| `--dashboard` | http://127.0.0.1:8765 | Dashboard URL |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                 EvolutionPipeline.run_one_cycle()          │
├──────────┬──────────┬──────┬──────────┬──────────────────┤
│ Monitor  │ Diagnose │ Fix  │ Verify   │ Document         │
│ Phase 1  │ Phase 2  │ P3   │ Phase 4  │ Phase 5          │
├──────────┼──────────┼──────┼──────────┼──────────────────┤
│Fetch all │ Match    │Save  │Measure   │Auto-update       │
│endpoints │patterns  │fix   │effect    │README.md         │
│Rolling   │JSON      │with  │≥30%      │with fix history  │
│window    │Schema    │meta  │threshold │+ metrics table   │
└──────────┴──────────┴──────┴──────────┴──────────────────┘
```

## Pipeline Phases

| Phase | Component | Description |
|-------|-----------|-------------|
| 1️⃣ **Monitor** | `DataCollector` | Polls /memory.json, /flow.json, /bridge-status.json every `interval` seconds. Maintains rolling window of positions, controls, stuck_duration, coverage. |
| 2️⃣ **Diagnose** | `DiagnosisEngine` | Evaluates 4 anomaly patterns against collected data. Each pattern has JSON Schema-validated conditions with threshold justification. Confidence scoring via condition match ratio. |
| 3️⃣ **Fix** | `FixCatalog` | Logs fix with unique ID, timestamp, pattern reference, baseline stuck_duration. Supports auto-fix and manual-approval modes. Persisted to `fix_log.json`. |
| 4️⃣ **Verify** | `VerificationEngine` | After fix applied, monitors for N cycles. Effectiveness = 70% stuck_duration improvement + 30% coverage gain. Threshold: ≥30% score = effective. |
| 5️⃣ **Document** | `SelfDocumenter` | Auto-updates `README.md` with latest fix entry, effectiveness metrics table, cycle findings summary. |

## Pattern Catalog (4 Patterns)

### 🔴 high: Circle Loop
- **Detection**: wall_score<0.1, asymmetry<0.05, stuck>120s, ground_angle>0.3
- **Contradiction**: terrain=cliff but ground_angle>0.3 (not actually a cliff)
- **Root Cause**: Terrain classifier false-positive "cliff"; cliff avoidance overrides straight-forward escape
- **Fix**: Add ground_angle gate to suppress false cliff triggers

### 🔴 high: Ramp Trap
- **Detection**: ramp_score>0.5, stuck>180s, position unchanged 60s
- **Root Cause**: Ramp suppression blocks turning; Mario stays on slope indefinitely
- **Fix**: Add ramp escape override with sharp turn when stuck >180s

### 🟡 medium: Reflex Cooldown Gap
- **Detection**: anomaly_state≠idle, reflex_active=False, stuck>60s
- **Root Cause**: Reflex correctly detects anomaly but cooldown prevents re-trigger; normal escape ineffective during cooldown
- **Fix**: Reduce reflex cooldown or make adaptive

### 🟡 medium: Coverage Stagnation
- **Detection**: coverage stagnant 120s, visited_cells<50
- **Root Cause**: Mario trapped in small area; exploration strategy insufficient
- **Fix**: Force bold explore when coverage stagnates

## Effectiveness Metrics

| Metric | Description |
|--------|-------------|
| stuck_duration_ratio | Post-fix stuck_duration / baseline stuck_duration (lower = better) |
| coverage_gain | Post-fix coverage_pct - baseline coverage_pct (higher = better) |
| effectiveness_score | 0.70 × (1 - stuck_duration_ratio) + 0.30 × coverage_gain, clamped [0,1] |
| effectiveness_threshold | Score ≥0.30 = fix is effective |

## Data Flow

```
SM64 Game → Shared Memory Bridge → Fly64 Brain Model
                                       ↓
                              Web Dashboard API
                              (memory/flow/bridge/events)
                                       ↓
                              EvolutionSkill Pipeline
                              Monitor → Diagnose → Fix → Verify → Document
                                       ↓
                              fix_log.json ←→ README.md (auto-update)
                                       ↓
                              Git Commit (suggested)
```

## Files

| File | Description |
|------|-------------|
| `fly64/skills/evolution_skill.py` | Core skill module (~730 lines) |
| `fly64/skills/default_patterns.json` | 4 patterns with JSON Schema |
| `fly64/skills/README.md` | Auto-generated documentation |
| `fly64/skills/__init__.py` | Package exports (13 symbols) |
| `fly64/skills/evolution_agent.py` | v1 legacy agent |

## Dependencies

- Python 3.10+
- `jsonschema` (optional, for pattern validation)
- Fly64 dashboard at http://127.0.0.1:8765

## Trigger Keywords

- evolution, self-improve, diagnose motion, stuck analysis, circle loop problem
- Mario stuck, behavioral analysis, auto-fix, motion health
- 进化, 自改进, 运动诊断, 卡住分析, 闭环优化