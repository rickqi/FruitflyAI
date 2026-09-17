# EvolutionSkill - Self-Evolving Motion Diagnosis

**Version**: 3.2.0 | **Catalog Version**: 2.0

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
| Total Fixes Applied | 0 |
| Effective | 0 |
| Ineffective | 0 |
| Pending Verification | 0 |
| Reverted | 0 |
| Effectiveness Rate | 0.0% |
| Avg Score | 0.0 |

## Pattern Catalog

The following 16 patterns are loaded from `default_patterns.json` and validated against JSON Schema (draft-07).

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
| mbon_saturation | MBON saturation — 蘑菇体输出饱和 | medium | mb_mbon_forward: {'min': 0.95}; loop_score: {'min': 0.8}; stuck_duration: {'min': 60} (mb_mbon_forward>=0.95=tanh ceiling, loop_score>=0.8=still weaving, stuck>60s=sustained) |
| primitive_timeout | CPG primitive timeout — 运动原语超时熔断 | medium | cpg_aborted: {'min': 1}; cpg_last_abort: {'const': 'timeout'} (MAX_PRIMITIVE_S=2.0s breaker (v2.15.0); any timeout event means the scripted duration was exceeded, so a single occurrence is diagnosable) |
| primitive_zero_disp | CPG primitive zero displacement — 原语执行后零位移 | high | cpg_completed: {'min': 3}; primitive_disp: {'max': 30} (EVO VerificationEngine effectiveness threshold score>=0.3 and reflex_ineffective uses 30u/60s (v2.x) — same 30u floor reused for primitive outcomes) |
| mbon_wrong_direction | MBON 学习方向错误 — 原语列权重持续下行 | medium | mbon_w_min_slope: {'max': -0.0005}; cpg_completed: {'min': 10} (columns drift ~+0.002/min under healthy success shaping (M3.1 live data); a sustained -0.0005/min over >=3 min is a 4x-sign opposite trend and cannot arise from noise (delta quantisation 1e-5)) |

---

### Last Cycle Summary

**Time**: 2026-09-17 03:53:19 UTC

**Findings**: 1 pattern(s)
- [LOW] Telemetry gap — 条件字段缺失 (conf=100%)


---

*Auto-generated by EvolutionSkill v3.2.0 on 2026-09-17 03:53:19 UTC*
