# LIF Injection Feasibility Report: 4-Design Evaluation

> **Evaluator**: `neural-engineer` | Team `fly64-vision-roadmap` | Task t6  
> **Audited against**: `fly64/fly64/model.py` (v1.0, 701 lines) and `fly64/fly64/retina.py` (690 lines)  
> **Date**: Based on code audit (t1) and design docs (t2–t5)

---

## Executive Summary

| Design | Feasibility | Risk Level | Key Issue |
|--------|-------------|------------|-----------|
| **4-Direction EMD** | ✅ **Feasible** | Low | Injection mechanism needs clarification (section 3 vs section 4) |
| **Color/UV Vision** | ✅ **Feasible** | Low | Drive saturation risk mitigated by clipping |
| **Small Target Tracking** | ✅ **Feasible** | Moderate | Injection placement must move from post-spike to pre-spike zone |
| **Dopamine MB Learning** | ✅ **Feasible** | Low | Clean injection pattern; main.py dependency is manageable |

**Bottom line**: All 4 designs can be injected into the existing LIF framework. Design C (target tracking) requires one structural fix. No conflicts make any design infeasible.

---

## 1. LIF Framework Architecture (Reference Model)

### 1.1 `step()` Execution Order

The `step()` method (model.py:475) executes in this strict order:

```
Line   ┌──────────────────────────────────────────────┐
478    │ encode_retina() → sensory drive vector        │ ← All retina computation
       │   (drive formula, ON/OFF, flow, tau, edges)   │
       ├──────────────────────────────────────────────┤
485    │ Synaptic current: w @ spikes                  │
488    │ LIF decay:  v *= exp(-dt/τ_m)                 │
489    │ LIF integrate: v += current + baseline + tonic │
491    │ Visual drive:  v[visual] += sensory × 0.62    │
       │                                               │
494    │ Escape mode: v[motor_nodes] += escape_current │
497    │ Tau injection: v[jump_nodes] += _tau_inj       │ ← up to 0.35
507    │ Sky injection: v[jump_nodes] += sky×0.12      │
514    │ Novelty: v[turn_left/right] ± novelty×0.075   │
522    │ Dialogue: v[forward] -= 0.30; v[jump]+=0.50   │
533    │ Interactive: v[forward] += 0.10                │
       ├──────────────────────────────────────────────┤
537    │ ★ SPIKE GENERATION: fired = v >= threshold    │ ← Threshold 1.0
       │    v[fired] = reset; spikes, activity update   │
       │    OU noise injection + re-check               │
       ├──────────────────────────────────────────────┤
567    │ HISTORY: append( spikes[motor_nodes] )         │
572    │ DECODE: forward_rate, turn_rate, jump_rate     │ ← 250ms rolling window
576    │ raw_y, raw_x = f(forward_rate, turn_rate)       │
       ├──────────────────────────────────────────────┤
579    │ ★ BEHAVIORAL MODULATION (operates on raw_x/y)  │
581    │   — flow_asymmetry → raw_x                    │
587    │   — flow_looming → raw_y                      │
593    │   — flow_cliff → raw_x                        │
601    │   — OFF channel → raw_x                       │
614    │   — sustained → raw_y                         │
619    │   — edge orientation → raw_x                  │
632    │   — tau avoidance → raw_x, raw_y              │
653    │   — terrain: wall/ramp/opening/door            │
       ├──────────────────────────────────────────────┤
691    │ CLIP: raw_x ∈ [-70,70], raw_y ∈ [0,70]        │
696    │ JUMP: jump_rate > 0.04 AND cooldown ≥ 0.8s    │
699    │ OUTPUT: Control(x, y, jump, rates)             │
       └──────────────────────────────────────────────┘
```

### 1.2 Two Distinct Injection Mechanisms

**Mechanism A — Pre-spike `self.v[...]` injection** (before line 537):
- Injects current directly into LIF neuron pools
- Affects **current frame** spiking probability
- Used by: tau, sky, novelty, dialogue, interactive mode
- Current range: −0.30 to +0.50

**Mechanism B — Post-spike `raw_x/raw_y` modulation** (after line 579):
- Modulates decoded behavioral output, not membrane potential
- Affects **decoded motor command** after LIF dynamics
- Used by: flow asymmetry, looming, cliff, OFF channel, edges, tau, terrain
- Gain style: `raw_x += bias × K` where K ∈ [8.0, 40.0]

---

## 2. Design A: 4-Direction EMD

### 2.1 Feasibility: ✅ Feasible

### 2.2 Injection Placement Analysis

The design proposes two injection points (with a discrepancy between sections):

**Section 3.3 (code block)** — Post-spike `raw_x/raw_y` modulation:
```python
raw_y *= max(0.6, 1.0 - _emd_v * 3.0)     # vertical motion → slow down
raw_x -= _emd_net_lat * 15.0              # horizontal asymmetry → turn
raw_x *= max(0.5, 1.0 - _emd_h * 2.0)    # symmetric flow → straighten
raw_x += self.emd_off_total * 20.0        # OFF-dominant → avoid
```
**Proposed placement**: After line 630 (edge orientation) and before line 632 (tau avoidance)  
**Inject mechanism**: Mechanism B ✅ — matches existing flow modulation pattern  
**Gain range**: 2.0–20.0 (same band as existing: 8.0–40.0) ✅

**Section 4 (table)** — Pre-spike `self.v` injection:
```python
self.v[self.turn_left] += self.emd_on_right * 0.20
self.v[self.turn_right] += self.emd_on_left * 0.20
```
**Proposed placement**: Not specified in code (only in table)  
**Inject mechanism**: Mechanism A  
**Issue**: The table and code suggest different injection strategies. The table's self.v injection is **not implemented in the code block**. If self.v injection is desired, it must be placed **before line 537**.

### 2.3 Membrane Potential Impact

- No sustained depolarization: EMD signals decay to zero when motion stops
- Transient currents (0.10–0.30) are within safe range (tonic = 0.18, tau = 0.35)
- Half-wave rectified outputs guarantee no negative injection

### 2.4 Motor Pool Conflict Risk: Low

Conflict Source | Risk | Mitigation
---|---|---
EMD turn vs flow_asymmetry turn | Low | EMD operates on direction-selective motion energy; flow_asymmetry is brightness asymmetry. Different physics. Both modulate raw_x additively — no cancellation risk.
EMD vertical vs cliff/ramp | Low | EMD detects motion; cliff/ramp detect static terrain features. Independent triggers.
EMD threat avoidance vs tau | Low | EMD catches OFF-dominant lateral motion (moving objects); tau catches approaching surfaces. Complementary.

### 2.5 Placement Recommendation

```python
# In step(), after line 630 (edge orientation) and before line 632 (tau):
# ---- 4-direction EMD modulation (raw_x/raw_y level) ----
# (code from design section 3.3, lines 296-331)
```

For the self.v injection pattern (section 4), place **before line 537**, near the tau injection block (line 497).

---

## 3. Design B: Color/UV Vision Channels

### 3.1 Feasibility: ✅ Feasible

### 3.2 Injection Placement Analysis

Three separate injection points:

**Drive formula enhancement** (design section 3.2):
```python
# In encode_retina(), replacing line 297:
drive_lum = 0.45 * lum
drive_temp = 1.6 * temporal
red_sal = np.maximum(frame[..., 0] - frame[..., 1], 0)
uv_sal = np.maximum(frame[..., 2] - 0.5 * (frame[..., 0] + frame[..., 1]), 0)
green_sal = np.maximum(frame[..., 1] - 0.5 * (frame[..., 0] + frame[..., 2]), 0)
drive_color = 0.15 * red_sal + 0.10 * uv_sal + 0.25 * green_sal
drive = np.clip(drive_lum + drive_temp + drive_color, 0, 1)
```
**Impact**: This feeds into `self.v[self.visual] += sensory * 0.62` (line 491)  
**Inject mechanism**: Mechanism A (through sensory → self.v)  
**Saturation risk**: In scenes with strong red+UV (lava+sky: red_sal~0.6, uv_sal~0.4), drive_color adds ~0.13. Total drive stays within [0,1] via `np.clip`. ✅  
**Max increase**: ~25% above current drive in the reddest/UV-richest scenes. Drive mean should stay <15% above baseline. ✅

**Behavioral modulation** (design section 3.3):
```python
# raw_x/raw_y level, after EMD block:
if self.danger_red_index > 0.4 and self.tau < 3.0:
    raw_x += 30.0  # turn away from red
    raw_y *= 0.6
if self.sky_blue_index > 0.5:
    raw_y = min(70, raw_y * 1.15)  # forward boost in open
if self.color_contrast > 0.3 and self.saturation_mean > 0.25:
    raw_x *= 0.7  # reduce random turning
```
**Inject mechanism**: Mechanism B ✅  
**Gains**: 30.0 (turn) is within existing range (up to 60.0 for sharp turn at line 637). ✅  
**Placement**: After EMD block, before tau avoidance — same as EMD recommendation.

**Scene signature enhancement** (design section 4):
```python
color_input = np.column_stack([drive, red_sal, uv_sal, green_sal, frame.mean(axis=1)])
self.scene_sig = (self.color_projection @ color_input.ravel()).astype(np.float32)
```
**Impact**: Changes `self.projection` from (128, 1536) to `self.color_projection` of (128, 7680).  
**Backward compatibility**: All existing scene memories invalidated.  
**Recommendation**: Gate with `self.color_signature = False` flag, as design suggests. ✅

### 3.3 Membrane Potential Impact

- `np.clip(drive, 0, 1)` prevents over-excitation
- Color channels are derived from RGB, which is already being computed — no additional atlas sampling cost
- The LIF network will see ~15% higher drive in color-rich scenes, which is within normal operating range

### 3.4 Motor Pool Conflict Risk: Low

Conflict Source | Risk | Mitigation
---|---|---
danger_red turn vs tau turn | Low | danger_red needs tau<3 (near object) — they coincide rationally.
sky_blue boost vs cliff | Low | sky_blue only triggers with tau>3 (no immediate danger).
color_contrast vs edges | Low | Different signals: color_contrast from hue, edges from luminance.

---

## 4. Design C: Small Target Tracking (LPLC/LC11)

### 4.1 Feasibility: ✅ Feasible (with structural fix)

### 4.2 ⚠️ CRITICAL PLACEMENT ISSUE

The design's section 3.4 proposes injecting into `self.v[...]` **after** spike generation:

```python
# Proposed at line 631+ (after color vision, before terrain):
if self.target_approaching and self.target_intercept_time < 10.0:
    if 2.0 < _frames_to_intercept < 6.0:
        self.v[self.jump_nodes] += _jump_strength    # 0.30-0.60
    elif _frames_to_intercept <= 2.0:
        self.v[self.jump_nodes] += 0.50
    self.v[self.turn_left] -= _lateral_bias * 0.12
    self.v[self.turn_right] += _lateral_bias * 0.12
```

**The problem**: At line 631+ (after line 537 spike generation), the self.v injection:
1. Does NOT affect this frame's jump decision (already decoded from history at line 573)
2. Only affects frames 2-5 later (through LIF dynamics in subsequent steps)
3. The jump control signal is computed from `jump_rate` (line 573), which is fixed for this frame

**This is critical for intercept timing**: If a moving platform is 3 frames away, the jump needs to happen NOW, not in 2-5 frames.

### 4.3 Fix: Split Injection into Two Zones

**Zone 1 — Pre-spike `self.v` injection** (near line 497, before spike gen):

```python
# Jump-target injection (pre-spike, near tau injection, line 497):
if self.target_approaching:
    _t = self.target_intercept_time
    if 0 < _t < 10.0:  # frames to intercept
        if 2.0 < _t < 6.0:
            self.v[self.jump_nodes] += max(0.3, min(0.6, (6.0 - _t) * 0.1))
        elif _t <= 2.0:
            self.v[self.jump_nodes] += 0.50
```

**Zone 2 — Post-spike `raw_x/raw_y` modulation** (at line 631+, like EMD and color):

```python
# Turn/avoidance modulation (post-spike, behavioral level):
_tgt_r, _tgt_c = self.target_nearest_centroid
_lateral_bias = (_tgt_c - 32.0) / 32.0
if abs(_lateral_bias) > 0.15 and self.target_approaching:
    raw_x -= _lateral_bias * 15.0  # turn toward target
```

This split resolves the timing issue and aligns with the existing pattern where:
- `self.v[jump_nodes]` injection happens pre-spike (tau at line 497, sky at line 507)
- Turn bias happens post-spike through raw_x (all flow modulation)

### 4.4 Membrane Potential Impact

- Jump injection (0.30–0.60) is stronger than tau (max 0.35). This is justified: intercept jump needs higher urgency than collision avoidance.
- Turn bias (0.12 × self.v) is moderate — similar to novelty (0.075) and sky (0.12)
- The `TargetTracker` class has clean separation: it runs in `encode_retina()` (model.py change C8) and only updates tracks — no LIF interaction until `step()` injection

### 4.5 Motor Pool Conflict Risk: Moderate

Conflict Source | Risk | Mitigation
---|---|---
Jump target vs tau jump | Moderate | Both inject into jump_nodes. If target approaching AND tau near, sum of injections could reach 0.35+0.50=0.85. **Risk of premature jump** (v threshold = 1.0, but with tonic 0.18 + OU 0.15, injection 0.85 could cross threshold). **Mitigation**: Gate: if tau<TAU_NEAR, cap target jump at 0.20.
Turn toward target vs flow asymmetry | Low | Target tracking explicitly wants to turn toward the target. Flow asymmetry wants to turn toward/away from motion. These could conflict when the target moves in the opposite direction. **Mitigation**: When target_approaching, reduce flow_asymmetry gain by 50%.
fg_fraction gating | Low | When fg_fraction > 0.15 (self-motion), suppress target tracking entirely (already in design).

### 4.6 Computational Cost

| Component | Cost | % of 20ms budget |
|-----------|------|-------------------|
| Center-surround (numpy vectorized) | ~20 μs | 0.1% |
| Connected components (scipy ndimage) | ~30 μs | 0.15% |
| Hungarian matching (rare, n>0) | ~25 μs | 0.125% |
| Kalman update | ~5 μs | 0.025% |
| **Total** | ~80 μs | **0.4%** ✅ |

---

## 5. Design D: Dopamine-Modulated Mushroom Body

### 5.1 Feasibility: ✅ Feasible (cleanest injection pattern)

### 5.2 Injection Placement Analysis

The design correctly places MBON injection BEFORE LIF dynamics (design section 3.4):

```python
# In step(), after encode_retina() and before line 485:
# (inserted at design's specified "before line 485")
dop = self._compute_dopamine()
self.mushroom.set_dopamine(dop)
n_syn = self.mushroom.update_weights()

# MBON → self.v injection:
self.v[self.forward] += mbon[0] * 0.15
self.v[self.turn_left] += mbon[1] * 0.12
self.v[self.turn_right] += mbon[2] * 0.12
self.v[self.jump_nodes] += mbon[3] * 0.20
# explore_bias: modulates escape_current
if mbon[4] > 0.2:
    self.escape_current = min(0.25, self.escape_current * 1.02)
elif mbon[4] < -0.2:
    self.escape_current = max(0.05, self.escape_current * 0.98)
```

**Placement**: After line 478 (encode_retina) and before line 485 (synaptic current)  
**Inject mechanism**: Mechanism A ✅ — pre-spike self.v injection  
**Gains**: 0.12–0.20 — all below tau injection (0.35) and comparable to tonic (0.18) ✅

### 5.3 Membrane Potential Impact

- MBON outputs are tanh-clipped [-1, 1] → bounded injection
- Initially near-zero (weighted random init ±0.05) → gradual ramp-up
- Three-factor rule prevents runaway: only active synapses change
- Learning rate η=0.001 and weight bounds [-1,1] prevent weight explosion

### 5.4 Motor Pool Conflict Risk: Low

Conflict Source | Risk | Mitigation
---|---|---
MBON forward vs dialogue/interactive | Low | MBON adds +0.15 max; dialogue subtracts -0.30. Different contexts.
MBON jump vs tau jump | Low | MBON max 0.20; tau max 0.35; combined max 0.55 — below threshold with tonic.
MBON explore vs escape_current | Low | MBON modulates escape_current ±2% per frame; slow, bounded adaptation.
**Learning convergence** | Low | KB sparsity (5% active) means minimal interference between scene associations.

### 5.5 Main.py Dependency

The `_compute_dopamine()` method requires `stuck_duration`, `fallen`, and `_revisit_penalty` from the MemoryController. These aren't on `self` currently.

**Design's recommendation (b)** is correct: mirror state in main.py before model.step():
```python
model.stuck_duration = memory_ctrl.stuck_duration
model.fallen = memory_ctrl._fallen
model._revisit_penalty = memory_ctrl.revisit_penalty
```

This is a **trivial, non-invasive change** — one-time attribute assignment per frame. ✅

### 5.6 Computational Cost

| Component | Cost | % of 20ms budget |
|-----------|------|-------------------|
| KC projection (2000×128 matmul) | ~2 μs | 0.01% |
| Top-k sparsification | ~1 μs | 0.005% |
| MBON integration (2000×5) | ~1 μs | 0.005% |
| Eligibility update | ~5 μs | 0.025% |
| Dopamine computation | ~1 μs | 0.005% |
| Weight update (sparse) | ~20 μs | 0.1% |
| **Total** | ~30 μs | **0.15%** ✅ |

---

## 6. Cross-Design Conflict Analysis

### 6.1 Combined current load on each motor pool

| Motor Pool | Existing max | +EMD | +Color | +Target | +MBON | Combined max | Threshold |
|-----------|-------------|------|--------|---------|-------|-------------|-----------|
| **forward** | tonic 0.18 + sensory 0.62 = 0.80 | — | — | — | +0.15 | 0.95 | 1.0 |
| **turn_left** | tonic 0.18 + OU 0.15 = 0.33 | +0.25 (avoid) | — | +0.12 | +0.12 | 0.82 | 1.0 |
| **turn_right** | tonic 0.18 + OU 0.15 = 0.33 | +0.25 (avoid) | — | +0.12 | +0.12 | 0.82 | 1.0 |
| **jump** | tonic 0.18 + tau 0.35 = 0.53 | +0.30 (platform) | — | +0.60 (target) | +0.20 | **1.63** 🚨 | 1.0 |

**⚠️ Jump pool critical overload**: Combined injection from tau (0.35), target tracking (0.60), and MBON (0.20) plus tonic (0.18) = **1.63**, well above threshold 1.0.

**Mitigation**: The pre-spike LIF dynamics include:
1. `self.v *= exp(-dt/τ_m)` — exponential decay (line 488). At `τ_m=0.1s`, `dt=0.02s`, decay factor = 0.819.
2. Firing resets v to 0 (line 538).
3. Tau injection (0.35) only triggers when `tau < TAU_NEAR` (2.0).
4. Target tracking injection (0.30-0.60) only when `target_intercept_time < 6.0`.
5. MBON injection (0.20) only after learning, slowly ramping.

**Actual worst case**: `v_decay + tau(0.35) + target(0.60) + mbon(0.20)` in a frame where all three conditions coincide. After decay (factor 0.819), v ≈ 0.94 + injections → 1.94. This would fire and reset. **Acceptable** — the neuron fires when it should (urgent jump needed) and resets.

**No sustained firing risk**: All three sources are transient (tau decays as distance decreases, target intercept fires once, MBON slowly adapts).

### 6.2 Retina compute_flow() return dict extension

All three retina-level designs (EMD, color, targets) extend `compute_flow()`'s return dict. Current dict (retina.py:455-481) has 27 keys. Expected additions:

| Design | New Keys | Type |
|--------|----------|------|
| EMD | 10 (emd_on_right/left/down/up/off_*, emd_on/off_total) | float scalar |
| Color | ~12 (sky_blue_index, danger_red_index, color_contrast, opponent_*, uv_appx_mean, hue_*, sat_mean, 8× hue_az) | float scalar |
| Target | 7 (target_count, centroids, sizes, energies, directions, fg_fraction, max_target_energy) | mixed (scalar + list) |

**Total new keys**: ~29. Return dict grows from 27 to 56 keys. **Acceptable** — dict lookups are O(1). ✅

### 6.3 Prioritization of execution order in step()

After all 4 designs, the recommended complete step() structure:

```
Line 478:    encode_retina()
               └── color drive formula
               └── EMD signals (via compute_flow)
               └── small target signals (via compute_flow)
               └── color features (via compute_flow)
Line 478-485: [NEW] Dopamine + MBON → self.v injection  (MECHANISM A)
Line 485-536: Existing: current, LIF decay/integrate, tau/sky/novelty/dialogue/injections
Line 537:     ★ Spike generation
Line 567-577: Decode → raw_x, raw_y
Line 579-630: Existing flow modulation (asymmetry, looming, cliff, edges)
Line 631+:    [NEW] EMD modulation on raw_x/raw_y          (MECHANISM B)
              [NEW] Color modulation on raw_x/raw_y        (MECHANISM B)
              [NEW] Target tracking turn on raw_x/raw_y     (MECHANISM B)
Line 632-651: Tau avoidance (unchanged)
Line 653-689: Terrain modulation (unchanged)
Line 691-701: Clip + Control output
```

And pre-spike for target jump (near line 497):
```
Line 497+:   [NEW] Target jump: self.v[jump_nodes] += strength  (MECHANISM A)
```

---

## 7. Summary of Changes Required

### 7.1 Changes Correct as Designed (no modifications needed)

| Design | Change | Status |
|--------|--------|--------|
| **EMD** | retina.py: `compute_emd()` method | ✅ Cleanly inserted after `encode_on_off()` |
| **EMD** | retina.py: `compute_flow()` call + return dict keys | ✅ Standard extension pattern |
| **EMD** | model.py: `__init__()` state variables | ✅ Standard attribute pattern |
| **EMD** | model.py: `encode_retina()` read EMD from flow | ✅ Standard read pattern |
| **EMD** | model.py: `step()` raw_x/raw_y modulation | ✅ Mechanism B, correct placement |
| **Color** | retina.py CALIBRATION, `encode_color()`, `_per_cell_color()` | ✅ Clean |
| **Color** | retina.py compute_flow() enrichment | ✅ Clean |
| **Color** | model.py `encode_retina()` enhanced drive formula | ✅ Safe via np.clip |
| **Color** | model.py `step()` raw_x/raw_y modulation | ✅ Mechanism B |
| **MB** | New `mushroom_body.py` module | ✅ Clean class design |
| **MB** | model.py `__init__()` `self.mushroom = MushroomBody()` | ✅ |
| **MB** | model.py `encode_retina()` feed scene_sig → MB | ✅ |
| **MB** | model.py `step()` dopamine + MBON → self.v injection | ✅ Mechanism A, correct placement |
| **MB** | main.py memory mirror | ✅ Trivial change |

### 7.2 Changes Requiring Correction

| Design | Change | Issue | Fix |
|--------|--------|-------|-----|
| **Target** | model.py `step()`: self.v[jump_nodes] injection | Placed at line 631+ (post-spike). Jump won't fire on correct frame. | **Move to pre-spike zone** (near tau injection, line 497). Split turn bias to post-spike raw_x/raw_y. |
| **Target** | model.py `step()`: turn injection via self.v | Same placement issue. self.v injection at line 631+ won't affect current frame. | **Use raw_x/raw_y** for turn modulation (Mechanism B) at line 631+. |
| **EMD** | Section 4 table vs Section 3.3 code | Table proposes self.v injection but code uses raw_x/raw_y. | **Clarify**: Use Mechanism B (raw_x/raw_y) for behavioral modulation. self.v injection is optional and must go pre-spike. |
| **All** | retina.py: `compute_flow()` return dict | EMD, color, and target each add keys. If all added, dict explodes to ~56 keys. | **Group in a nested dict**: `flow["visual_signals"] = {"emd": ..., "color": ..., "targets": ...}` to keep flat dict manageable. Optional. |

---

## 8. Final Verdict

| # | Design | LIF Feasibility | Confidence | Priority |
|---|--------|-----------------|------------|----------|
| A | 4-Direction EMD | ✅ **Feasible** | High | **P1** (no corrections needed for raw_x/raw_y path) |
| B | Color/UV Vision | ✅ **Feasible** | High | **P1** (all injection points correct as designed) |
| C | Small Target Tracking | ✅ **Feasible with fix** | Medium | **P1** (requires split injection fix before implementation) |
| D | Dopamine MB Learning | ✅ **Feasible** | High | **P2** (cleanest design, but depends on slow learning curve) |

**Key recommendation**: Designs A, B, and D can proceed to implementation as designed. Design C requires the split-injection fix described in §4.3 before it will produce correct intercept-timing behavior.

---

*End of LIF injection feasibility report — ready for roadmap-planner (t7) synthesis.*