# EvolutionSkill - Self-Evolving Motion Diagnosis

**Version**: 3.4.2 | **Catalog Version**: 2.0

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
| circle_loop | Circle loop - Circling on flat ground | high | wall_score: {'max': 0.1}; asymmetry_magnitude: {'max': 0.06}; stuck_duration: {'min': 120}; ground_angle: {'min': 0.3} (wall_score<0.1=flat terrain, asymmetry<0.06=symmetrical movement (tuned from 0.05 based on real measured values), stuck>120s=abnormal duration, ground_angle>0.3=not a cliff edge) |
| ramp_trap | Ramp trap - Stuck on slope | high | ramp_score: {'min': 0.5}; stuck_duration: {'min': 180}; position_unchanged_60s: True (ramp_score>0.5=strong slope signal, stuck>180s=3min threshold, position_unchanged=no progress despite effort) |
| reflex_cooldown_gap | Reflex cooldown - Ineffective escape during cooldown (adaptive) | medium | anomaly_state_not_idle: True; reflex_active: False; stuck_duration: {'min': 60} (anomaly_state_not_idle=anomaly active, reflex_active=False=cooldown period, stuck>60s=1min without effective escape; adaptive cooldown formula derived from stuck_duration to allow more frequent reflex firings as stuck persists) |
| low_coverage_stagnation | Coverage stagnation - Exploration stuck | medium | coverage_stagnant_120s: True; visited_cells: {'max': 50} (coverage_stagnant_120s=no new cells in 2min, visited_cells<50=very small explored area) |
| below_ground_stuck | Below ground stuck - Y anomaly prevents movement | high | pos_y: {'min': -99, 'max': 49}; stuck_duration: {'min': 30}; control_magnitude: {'max': 10} (pos_y between -99 and 49=abnormal (SM64 ground=120), stuck>30s, ctrl<10=no movement) |
| fallen_recovery_stuck | Fallen recovery stuck - Recovery cycles ineffective | high | anomaly_state: {'eq': 'fallen'}; stuck_duration: {'min': 30} (anomaly_state='fallen'=fall zone, stuck_duration>30s=persistent stuck despite recovery) |
| suspended_animation | Suspended animation - Zero control signals | high | control_x_zero: True; control_y_zero: True; stuck_duration: {'min': 15}; jump_not_active: True (x=0 and y=0=no movement, stuck>15s=not transient, jump=False=no escape attempt) |
| color_nav_blind | Color navigation blind - Mario ignores color signals | medium | danger_red_index: {'min': 0.5}; stuck_duration: {'min': 30}; forward_speed: {'max': 5} (danger_red_index>0.5=strong red hazard ahead, stuck>30s=persistent, speed<5=no effective avoid) |
| emd_vertical_blind | Vertical EMD blind - Missing elevator/platform motion | medium | emd_on_down: {'min': 0.02}; jump_rate: {'max': 0.01}; stuck_duration: {'min': 15} (emd_on_down>0.02=detectable downward motion, jump_rate<0.01=no jump attempt, stuck>15s=persistent) |
| target_tracking_inactive | Small target tracking inactive - No intercept behavior | medium | target_count: {'min': 1}; jump_rate: {'max': 0.01}; stuck_duration: {'min': 10} (target_count>=1=objects detected, jump_rate<0.01=no jump, stuck>10s=missed opportunity) |
| mb_learning_stalled | Mushroom body learning stalled - No weight change | low | assoc_count: {'max': 0}; stuck_duration: {'min': 120} (assoc_count=0=no learning events after extended run, stuck>120s=sufficient run time) |
| cliff_standoff | Cliff standoff - 悬崖边缘对峙驻留 | medium | cliff_confirmed: True; cliff_standoff_s: {'min': 20}; escape_behavior: True (cliff_confirmed=multi-frame edge confirmed, standoff>20s = protection plateau (retreat+re-approach cycles), escape active = brain wants to move but cannot) |
| micro_loop_weave | Micro-loop weave — 原地编织（交替未产生位移） | high | anomaly_state: {'eq': 'micro_loop'}; loop_score: {'min': 0.8}; stuck_duration: {'min': 60} (anomaly=micro_loop=detector-confirmed circling, loop_score>=0.8=window near-fully revisits, stuck>60s=sustained weave despite alternation) |
| micro_loop_weave_signal | Micro-loop weave (signal-only) — 原地编织（行为信号判定，绕过 anomaly 分类器） | high | loop_score: {'min': 0.95}; escape_behavior: True; stuck_duration: {'min': 45} (loop_score>=0.95=window almost all revisits (weave is certain), escape_behavior=true=brain is trying to escape, stuck>45s=earlier than the detector-gated variant) |
| mbon_saturation | MBON saturation — 蘑菇体输出饱和 | medium | mb_mbon_forward: {'min': 0.95}; loop_score: {'min': 0.8}; stuck_duration: {'min': 60} (mb_mbon_forward>=0.95=tanh ceiling, loop_score>=0.8=still weaving despite saturated forward drive, stuck>60s=sustained) |
| dopamine_plateau | Dopamine gain plateau — Learning saturation detected | medium | dopamine_gain_avg: {'min': 2.0}; learning_progress: {'max': 0.05}; stuck_duration: {'min': 60} (dopamine_gain_avg>=2.0=near ceiling (GAIN_MAX=2.5), learning_progress<0.05=minimal error gradient (converged), stuck>60s=sufficient run time) |

---

### Last Cycle Summary

**Time**: 2026-09-18 09:20:21 UTC

**Findings**: 1 pattern(s)
- [LOW] Telemetry gap — 条件字段缺失 (conf=100%)


---

*Auto-generated by EvolutionSkill v3.4.2 on 2026-09-18 09:20:21 UTC*
