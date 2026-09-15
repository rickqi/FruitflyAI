# EvolutionSkill - Self-Evolving Motion Diagnosis

**Version**: 3.0.0 | **Catalog Version**: 2.0

A complete closed-loop pipeline for autonomous motion diagnosis in Fly64.

## Architecture

```
Monitor -> Diagnose -> Fix -> Verify -> Document
```

| Phase | Component | Description |
|-------|-----------|-------------|
| 1 Monitor | DataCollector | Rolling window sensor data from dashboard endpoints |
| 2 Diagnose | DiagnosisEngine + PatternCatalog | Pattern matching with JSON Schema validation |
| 3 Fix | FixCatalog | Versioned fix entries with baseline/outcome tracking |
| 4 Verify | VerificationEngine | Post-fix effectiveness measurement (30% threshold) |
| 5 Document | SelfDocumenter | Auto-updates this README with metrics and history |

---

## Effectiveness Metrics

| Metric | Value |
|--------|-------|
| Total Fixes Applied | 13 |
| Effective | 0 |
| Ineffective | 7 |
| Pending Verification | 6 |
| Reverted | 4 |
| Effectiveness Rate | 0.0% |
| Avg Score | 0.004 |

## Plasticity Metrics

| Metric | Value |
|--------|-------|
| Dopamine Gain Avg | 0.7968 |
| Learning Progress (mean |error| over 100 ticks) | 0.4009 |
| Mushroom Weight Changes (assoc_count) | 18835 |
| Reward Trend (cumulative) | -1.3506 |
| Error Gradient Mean | 0.4009 |
| Gain Update Count | 266328 |

## Pattern Catalog

The following 12 patterns are loaded from `default_patterns.json` and validated against JSON Schema (draft-07).

| ID | Name | Severity | Conditions |
|----|------|----------|------------|
| circle_loop | Circle loop — 无障碍转圈 | high | wall_score: {'max': 0.1}; asymmetry_magnitude: {'max': 0.06}; stuck_duration: {'min': 120}; ground_angle: {'min': 0.3} (wall_score<0.1=flat terrain, asymmetry<0.06=symmetrical movement (tuned from 0.05 based on real measured values), stuck>120s=abnormal duration, ground_angle>0.3=not a cliff edge) |
| ramp_trap | Ramp trap — 斜坡上无法脱困 | high | ramp_score: {'min': 0.5}; stuck_duration: {'min': 180}; position_unchanged_60s: True (ramp_score>0.5=strong slope signal, stuck>180s=3min threshold, position_unchanged=no progress despite effort) |
| reflex_cooldown_gap | Reflex cooldown — 冷却期内无效 escape (adaptive cooldown) | medium | anomaly_state_not_idle: True; reflex_active: False; stuck_duration: {'min': 60} (anomaly_state_not_idle=anomaly active, reflex_active=False=cooldown period, stuck>60s=1min without effective escape; adaptive cooldown formula derived from stuck_duration to allow more frequent reflex firings as stuck persists) |
| low_coverage_stagnation | Coverage stagnation — 覆盖率长期不增长 | medium | coverage_stagnant_120s: True; visited_cells: {'max': 50} (coverage_stagnant_120s=no new cells in 2min, visited_cells<50=very small explored area) |
| below_ground_stuck | Below ground stuck — Y坐标异常导致无法移动 | high | pos_y: {'min': -99, 'max': 49}; stuck_duration: {'min': 30}; control_magnitude: {'max': 10} (pos_y between -99 and 49=abnormal height (SM64 ground=120), stuck>30s=stuck in place, control_magnitude<10=no effective movement; the -100 fallen threshold was designed for extreme falls but misses partial falls into void/water at Y=-30 to Y=-80) |
| fallen_recovery_stuck | Fallen recovery stuck — 跌落恢复循环无效 | high | anomaly_state: {'eq': 'fallen'}; stuck_duration: {'min': 30} (anomaly_state='fallen'=agent detected in fall zone, stuck_duration>30s=persistent stuck despite recovery attempts; 30s allows ~15 recovery cycles before intervention) |
| suspended_animation | Suspended animation — 控制信号为零停止响应 | high | control_x_zero: True; control_y_zero: True; stuck_duration: {'min': 15}; jump_not_active: True (control_x/y both zero=no movement, stuck>15s=not just startup transient, jump=False=no escape attempt; combined with seq advancing indicates brain is running but outputting zero) |
| wall_corner_command_decoupled | Wall corner — 视觉盲区：动作-效果失配卡角 | high | command_effect_mismatch: True; mismatch_duration: {'min': 15} (expected>25 units/tick = meaningful forward command, moved<3 = static, >15 frames = not transient; reverse+turn physically un-wedges from 90-degree corners where asymmetry guidance is zero) |
| dopamine_plateau | Dopamine gain plateau — Learning saturation detected | medium | dopamine_gain_avg: {'min': 2.0}; learning_progress: {'max': 0.05}; stuck_duration: {'min': 60} (dopamine_gain_avg>=2.0=near ceiling (GAIN_MAX=2.5), learning_progress<0.05=minimal error gradient (converged), stuck>60s=sufficient run time) |
| cliff_standoff | Cliff standoff — 悬崖边缘对峙驻留 | medium | cliff_confirmed: True; cliff_standoff_s: {'min': 20}; escape_behavior: True (cliff_confirmed=multi-frame edge confirmed, standoff>20s = protection plateau (retreat+re-approach cycles), escape active = brain wants to move but cannot) |
| micro_loop_weave | Micro-loop weave — 原地编织（交替未产生位移） | high | anomaly_state: {'eq': 'micro_loop'}; loop_score: {'min': 0.8}; stuck_duration: {'min': 60} (anomaly=micro_loop=detector-confirmed circling, loop_score>=0.8=window near-fully revisits, stuck>60s=sustained weave despite alternation) |
| micro_loop_weave_signal | Micro-loop weave (signal-only) — 原地编织（行为信号判定，绕过 anomaly 分类器） | high | loop_score: {'min': 0.95}; escape_behavior: True; stuck_duration: {'min': 45} (loop_score>=0.95=window almost all revisits (weave is certain), escape_behavior=true=brain is trying to escape, stuck>45s=earlier than the detector-gated variant so the signal path can act first) |

## Fix History (Last 10)

| ID | Pattern | Severity | Applied | Baseline | Post-Fix | Effective | Score |
|----|---------|----------|---------|----------|----------|-----------|-------|
| fix_0013 | Ramp trap — 斜坡上无法脱困 | high | 2026-09-14 | 458s | 464s | No | 0.00 |
| fix_0012 | Fallen recovery stuck — 跌落恢复循环无效 | high | 2026-09-14 | 445s | 451s | No | 0.02 |
| fix_0011 | Cliff standoff — 悬崖边缘对峙驻留 | medium | 2026-09-14 | 310s | 316s | No | 0.00 |
| fix_0010 | Circle loop — 无障碍转圈 | high | 2026-09-14 | 120s | 126s | No | 0.01 |
| fix_0009 | Coverage stagnation — 覆盖率长期不增长 | medium | 2026-09-14 | 0s | 5s | No | 0.00 |
| fix_0008 | Suspended animation — 控制信号为零停止响应 | high | 2026-09-14 | 78s | 83s | No | 0.00 |
| fix_0007 | Reflex cooldown — 冷却期内无效 escape (adaptive cooldown) | medium | 2026-09-14 | 73s | - | Pending | - |
| fix_0006 | Micro-loop weave (signal-only) — 原地编织（行为信号判定，绕过 anomaly 分类器） | high | 2026-09-14 | 70s | - | Pending | - |
| fix_0005 | Coverage stagnation — 覆盖率长期不增长 | medium | 2026-09-14 | 3s | - | Pending | - |
| fix_0004 | Micro-loop weave — 原地编织（交替未产生位移） | high | 2026-09-14 | 157s | 162s | No | 0.00 |

---

### Last Cycle Summary

**Time**: 2026-09-15 04:45:30 UTC

**Findings**: 3 pattern(s)
- [HIGH] Ramp trap — 斜坡上无法脱困 (conf=100%)
- [HIGH] Micro-loop weave — 原地编织（交替未产生位移） (conf=100%)
- [HIGH] Micro-loop weave (signal-only) — 原地编织（行为信号判定，绕过 anomaly 分类器） (conf=100%)


---

*Auto-generated by EvolutionSkill v3.0.0 on 2026-09-15 04:45:30 UTC*
