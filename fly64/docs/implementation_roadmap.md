# Fly64 Visual Capability Enhancement — Implementation Roadmap

> **Synthesized from**: Visual Capability Gap Analysis, Code Audit, 4 Design Documents, LIF Injection Feasibility Report  
> **Author**: `roadmap-planner` | Team `fly64-vision-roadmap` | Task t7  
> **Date**: 2026-09-13

---

## Executive Summary

| Phase | Focus | Key Outcome | Effort | Risk |
|-------|-------|-------------|--------|------|
| **P1a** | Color/UV Vision Channels | Scene signature collisions 10³/day→<1/year | **4人天** | Low |
| **P1b** | 4-Direction EMD | Motion detection 25%→80% coverage | **4人天** | Low |
| **P2** | Small Target Tracking | Moving platform jump 30%→65% | **6人天** | Moderate (needs split-injection fix) |
| **P3** | Dopamine Mushroom Body | Associative learning capability | **10人天** | Low |
| **Total** | — | — | **24人天** | — |

All 4 designs validated as **feasible** for LIF injection. P1a and P1b are independent and can be implemented in parallel. P2 requires the split-injection fix from the LIF feasibility report. P3 requires the longest validation period.

---

## P1a: Color/UV Vision Channels (4人天)

**Priority**: 🔴 P1 — Highest impact/effort ratio  
**Dependencies**: None (independent of other designs)  
**Parallelizable with**: P1b (4-Direction EMD)

### Target

Transform Fly64 from grayscale luminance-only vision to 4-channel color vision (R/G/B/UV_approx) with opponent processing, enabling color-based scene discrimination, red-object detection (enemies/lava), sky/open-area identification, and 5× more discriminable scene signatures.

### Task List

| # | Task | File | Location | Effort (h) |
|---|------|------|----------|------------|
| A1 | Update CALIBRATION dict to v2 | `retina.py` | L13–18 | 0.5 |
| A2 | Add `_prev_color` ring buffer in `__init__()` | `retina.py` | After L86 | 0.5 |
| A3 | Implement `encode_color()` — 10-channel color encoding | `retina.py` | New method | 4.0 |
| A4 | Implement `_per_cell_color()` — (N,5) color vector | `retina.py` | New method | 2.0 |
| A5 | Enrich `compute_flow()` with color features (sky_blue, danger_red, azimuth hue) | `retina.py` | Inside compute_flow() | 3.0 |
| A6 | Add 10+ color keys to `compute_flow()` return dict | `retina.py` | Return dict | 1.0 |
| A7 | Add color buffer clear to `reset_temporal_state()` | `retina.py` | L275–280 | 0.5 |
| A8 | Add color state variables in `FlyModel.__init__()` | `model.py` | After L217 | 1.0 |
| A9 | Read color signals from flow dict in `encode_retina()` | `model.py` | After L384 | 2.0 |
| A10 | Enhance drive formula with red_sal + uv_sal + green_sal | `model.py` | L297 drive formula | 2.0 |
| A11 | Implement color modulation rules in `step()` (3 rules) | `model.py` | Before terrain block | 3.0 |
| A12 | Add optional 5-channel color projection for scene signatures | `model.py` | encode_retina() | 3.0 |
| | **Total retina.py changes** | | | **11.5** |
| | **Total model.py changes** | | | **11.0** |
| | **Integration & testing** | — | — | **9.5** |
| | **Grand total P1a** | | | **32h (~4人天)** |

### Key Implementation Details

**Drive Formula** (critical — affects all downstream behavior):
```python
# Replace single-channel luminance drive with color-enhanced drive
drive_lum = 0.45 * lum                          # luminance (R1-R6 analog)
drive_temp = 1.6 * temporal                      # motion transients
red_sal = max(0, R - G)                          # red salience
uv_sal = max(0, B - 0.5*(R+G))                  # UV approximation
green_sal = max(0, G - 0.5*(R+B))               # original green boost
drive_color = 0.15*red_sal + 0.10*uv_sal + 0.25*green_sal
drive = clip(drive_lum + drive_temp + drive_color, 0, 1)
```

**Scene Signature Enhancement** (optional, gated by `color_signature=False`):
```python
# 5-channel projection: (128, 7680) replaces (128, 1536)
color_input = stack([drive, red_sal, uv_sal, green_sal, mean_RGB])  # (N, 5)
scene_sig = (color_projection @ color_input.ravel()).astype(float32)
```

**LIF Injection Pattern**: Mechanism A (pre-spike via enhanced drive → `self.v[visual]`) + Mechanism B (post-spike `raw_x/raw_y` modulation)

### Expected Behavioral Gains

| Metric | Before | After | Mechanism |
|--------|--------|-------|-----------|
| Scene signature collisions | ~10³/day | <1/year | 5-channel color projection |
| Red coin collection | ~20% | ~55% | Red salience in drive formula |
| Lava/ledge fatality | ~30% | ~15% | danger_red_index early detection |
| Navigation wayfinding | ~50% | ~70% | sky_blue_index guides open path |
| Compute overhead | — | +45 μs/frame | (0.225% of 20 ms) ✅ |

### Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| sRGB ≠ true UV spectrum | Medium | Low | UV_approx captures "short-wavelength salience" — functionally useful in SM64 |
| Drive over-excitation | Low | Medium | Conservative coefficients (0.15 red, 0.10 uv); np.clip to [0,1] |
| Scene signature backward incompatibility | High | Medium | Gate with `color_signature=False` flag; rebuild scene DB on enable |
| Noisy opponent signals in dark scenes | Medium | Low | Luminance-gated suppression below 0.03 |

---

## P1b: 4-Direction Elementary Motion Detector (4人天)

**Priority**: 🔴 P1 — Foundational motion detection upgrade  
**Dependencies**: None (independent of P1a)  
**Parallelizable with**: P1a (Color/UV)

### Target

Replace Fly64's single scalar `left_right_asymmetry` with a full 4-direction Hassenstein-Reichardt correlator (T4/T5 equivalent) detecting motion in all cardinal directions (↑↓←→) with ON/OFF contrast separation, enabling moving platform tracking, enemy approach detection, and vertical motion sensing.

### Task List

| # | Task | File | Location | Effort (h) |
|---|------|------|----------|------------|
| B1 | Build EMD neighbor pairs + delay buffers in `__init__()` | `retina.py` | After L154 | 2.0 |
| B2 | Implement `compute_emd()` — HR correlator ×4 dir ×2 channels | `retina.py` | New method after L273 | 6.0 |
| B3 | Call `compute_emd()` in `compute_flow()` | `retina.py` | After L387 | 0.5 |
| B4 | Add 10 EMD keys to `compute_flow()` return dict | `retina.py` | Return dict L455–481 | 1.0 |
| B5 | Add EMD buffer clear to `reset_temporal_state()` | `retina.py` | L275–280 | 0.5 |
| B6 | Add 14 EMD state variables in `FlyModel.__init__()` | `model.py` | After L217 | 1.5 |
| B7 | Read EMD signals + compute derived compounds in `encode_retina()` | `model.py` | After L384 | 3.0 |
| B8 | Implement EMD motor modulation in `step()` (4 rules) | `model.py` | After L631 | 4.0 |
| | **Total retina.py changes** | | | **10.0** |
| | **Total model.py changes** | | | **8.5** |
| | **Integration & testing** | — | — | **13.5** |
| | **Grand total P1b** | | | **32h (~4人天)** |

### Key Implementation Details

**HR Correlator Core** (vectorized across 1500+ ommatidial pairs):
```python
# For each direction: RAW = prev(pre) × current(post) − current(pre) × prev(post)
# Half-wave rectified: RESPONSE = max(0, mean(RAW))
# 4 directions × 2 contrast (ON/OFF) = 8 signals + 2 totals

# Pair topology:
# left_to_right pairs: (pre, post) where pre has smaller column index (same eye)
# up_to_down pairs:    (pre, post) where pre has smaller row index (same eye)
```

**LIF Injection Pattern**:
- **Mechanism B (post-spike)**: 4 motor modulation rules on `raw_x/raw_y`
- Optional Mechanism A (pre-spike): `self.v[pool] += emd_signal * gain` if fine-grained timing needed

**Motor Modulation Rules**:
1. Vertical EMD > 0.03 & horizontal < 0.01 → terrain change detected, caution (slow down)
2. Asymmetric horizontal EMD → precise turn bias toward optic flow
3. Symmetric horizontal EMD → straighten in corridor
4. OFF-dominant EMD (ON ×2) → external moving object → avoid

### Expected Behavioral Gains

| Metric | Before | After | Mechanism |
|--------|--------|-------|-----------|
| Motion detection coverage | 25% (1 scalar) | 80% (4 directions) | 4-direction HR correlator |
| Moving platform jump | ~30% | ~60% | OFF-dominant EMD catches platform motion |
| Enemy avoidance distance | ~3 body lengths | ~5 body lengths | Earlier lateral motion detection |
| Wall collisions in corridors | Baseline | −40% | Directional EMD informs steering |
| Compute overhead | — | +35 μs/frame | (0.175% of 20 ms) ✅ |

### Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 20 ms delay vs Drosophila 5 ms | Medium | Low | SM64 visual dynamics < 5 Hz; delay adequate |
| Texture false positives (checker floor) | Medium | Medium | Gate with `sustained_energy` suppression |
| Self-motion contamination | High | Medium | Reuse `true_asymmetry` heading correction |
| LIF destabilization | Low | Medium | Conservative initial gain (0.10–0.20) |

---

## P2: Small Target Tracking (6人天)

**Priority**: 🟡 P2 — High behavioral impact, moderate complexity  
**Dependencies**: P1b (EMD) — EMD ON/OFF channels are input to figure-ground separation  
**⚠️ LIF Fix Required**: Split injection — jump `self.v` before spike gen; turn modulation via `raw_x/raw_y` after spike gen

### Target

Implement Drosophila LPLC1/2 + LC11 equivalent using center-surround motion opponency, connected-component labeling, and Kalman-filter multi-target tracking. Enables Mario to detect, track, and intercept moving platforms, approaching enemies, and peripheral objects.

### Task List

| # | Task | File | Location | Effort (h) |
|---|------|------|----------|------------|
| C1 | Build grid maps utility `_build_grid_maps()` | `retina.py` | New utility | 1.0 |
| C2 | Implement `_connected_components()` — 4-connectivity CCL | `retina.py` | New static method | 4.0 |
| C3 | Implement `compute_small_targets()` — center-surround + CCL | `retina.py` | New method after `compute_emd()` | 6.0 |
| C4 | Call `compute_small_targets()` in `compute_flow()` | `retina.py` | compute_flow() body | 0.5 |
| C5 | Add 7 target keys to `compute_flow()` return dict | `retina.py` | Return dict | 1.0 |
| C6 | Implement `TargetTracker` class — Kalman + Hungarian | `model.py` | New class before FlyModel | 8.0 |
| C7 | Add 7 target state variables in `FlyModel.__init__()` | `model.py` | After TAU_NEAR | 1.0 |
| C8 | Read targets from flow + update tracker in `encode_retina()` | `model.py` | After EMD/color reads | 4.0 |
| C9 | Implement target modulation rules in `step()` (3 rules) **with split-injection fix** | `model.py` | **Two zones** (see below) | 6.0 |
| C10 | Add tracker reset in `reset_scene()` | `model.py` | reset_scene() | 0.5 |
| | **Total retina.py changes** | | | **12.5** |
| | **Total model.py changes** | | | **19.5** |
| | **Integration & testing** | — | — | **16.0** |
| | **Grand total P2** | | | **48h (~6人天)** |

### ⚠️ Critical Fix: Split Injection Pattern

The LIF feasibility report identified that the original design placed `self.v[jump_nodes]` injection at line 631+ (post-spike), which **misses the jump decision frame**. **Corrected implementation** splits injection into two zones:

**Zone 1 — Pre-spike `self.v` injection** (near tau injection, ~line 497):
```python
# Jump-target injection (must be BEFORE spike generation at line 537)
if self.target_approaching:
    _t = self.target_intercept_time          # frames to intercept
    if 2.0 < _t < 6.0:                      # sweet spot: 2-6 frames
        strength = max(0.3, min(0.6, (6.0 - _t) * 0.1))
        self.v[self.jump_nodes] += strength
    elif _t <= 2.0:                          # imminent
        self.v[self.jump_nodes] += 0.50
```

**Zone 2 — Post-spike `raw_x/raw_y` modulation** (after line 631):
```python
# Turn toward target (Mechanism B — behavioral level)
if self.target_approaching and abs(_lateral_bias) > 0.15:
    raw_x -= _lateral_bias * 15.0            # turn toward target
```

**Conflict mitigation with tau**: If tau < TAU_NEAR and target approaching concurrently, cap target jump to 0.20 to prevent premature firing (combined max: tau 0.35 + target 0.20 + tonic 0.18 = 0.73 < threshold 1.0).

### LIF Injection Summary

| Detection Event | Target | Mechanism | Value | Trigger |
|---------------|--------|-----------|-------|---------|
| Approaching target, 2–6 frames out | jump_nodes | A (pre-spike) | 0.30–0.60 | target_approaching & intercept < 6 |
| Imminent target (< 2 frames) | jump_nodes | A (pre-spike) | 0.50 | intercept_time ≤ 2.0 |
| Target on right | raw_x (turn left) | B (post-spike) | bias × 15.0 | lateral_bias > 0.15 |
| Target on left | raw_x (turn right) | B (post-spike) | bias × 15.0 | lateral_bias < −0.15 |
| Peripheral object | raw_x (turn away) | B (post-spike) | energy × 15.0 | max_target_energy > 0.05 |

### Expected Behavioral Gains

| Metric | Before | After | Mechanism |
|--------|--------|-------|-----------|
| Moving platform jump success | ~30% | ~65% | Kalman-predicted intercept timing |
| Enemy avoidance distance | ~3 body lengths | ~6 body lengths | Center-surround motion sensitivity |
| False positive rate | ~5% | Controlled | Dynamic threshold (mean + 2σ) |
| Compute overhead | — | +80 μs/frame | (0.4% of 20 ms) ✅ |

### Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fast self-motion false positives | High | Medium | heading_rate gating: fg_fraction × 0.3 when turning fast |
| Texture noise (grass/checker floor) | Medium | Medium | sustained channel gate: suppress if sustained < 0.01 |
| Hungarian matching failure (many targets) | Low | Low | Greedy NN fallback when n<5 or n>15; cap tracks at 20 |
| ⚠️ **Split injection missed during impl** | Medium | **High** | MUST enforce two-zone pattern (see critical fix above) |
| Jump pool overload with tau + target | Medium | Medium | Mutual gate: cap target inj to 0.20 when tau < TAU_NEAR |

---

## P3: Dopamine-Modulated Mushroom Body Learning (10人天)

**Priority**: 🟢 P3 — Highest architectural complexity, longest validation  
**Dependencies**: P1a (Color scene signature) — 5-channel scene sig enriches KC encoding  
**Note**: Cleanest LIF injection pattern (Mechanism A, pre-spike, Method `A` verified) but requires the longest learning curve to show behavioral results (~5000+ frames).

### Target

Implement a Drosophila-scale Mushroom Body associative learning module with 2000 Kenyon Cells, 5 MBON output channels, and dopamine-gated three-factor Hebbian plasticity. Enables learnable scene→action associations from proxy reward/punishment signals, adding adaptive behavior on top of existing engineered reflexes.

### Task List

| # | Task | File | Location | Effort (h) |
|---|------|------|----------|------------|
| D1 | Create `MushroomBody` class — KC sparse coding + MBON + 3-factor plasticity | `fly64/mushroom_body.py` | **New file** | 16.0 |
| D2 | Add import in `model.py` | `model.py` | Top of file | 0.5 |
| D3 | Initialize MB + gain constants in `FlyModel.__init__()` | `model.py` | After L241 | 1.5 |
| D4 | Feed scene_sig into `mushroom.encode()` in `encode_retina()` | `model.py` | End of encode_retina() | 1.0 |
| D5 | Implement `_compute_dopamine()` — proxy reward from 6 signals | `model.py` | New method | 4.0 |
| D6 | Add dopamine signal + MBON→self.v injection in `step()` | `model.py` | Before L485 (pre-spike) | 4.0 |
| D7 | Add `self.mushroom.reset()` in `reset_scene()` | `model.py` | reset_scene() | 0.5 |
| D8 | Mirror memory controller state in main loop | `main.py` | After memory_ctrl.update() | 2.0 |
| D9 | Add MB diagnostics to dashboard | `main.py` | Dashboard telemetry | 2.0 |
| | **New module** | | | **16.0** |
| | **Total model.py changes** | | | **11.0** |
| | **Total main.py changes** | | | **4.0** |
| | **Integration & testing** | — | — | **49.0** |
| | **Grand total P3** | | | **80h (~10人天)** |

**Note**: Testing effort is high because the learning module requires extended simulation runs (5000+ frames) to validate convergence, and proxy reward signals must be tuned to avoid counterproductive associations.

### Key Implementation Details

**Mushroom Body Architecture**:
```
Scene signature (128-dim) → [fixed W_kc: 2000×128, N(0, 0.1)] → KC (top-5% = 100 active)
  → [plastic W: 2000×5, init ±0.05] → MBON (tanh-clipped [-1, 1])
    ↑ dopamine gate (three-factor Hebbian)
       ΔW[i,j] = η · R(t) · E[i,j]   (only active synapses, eligibility trace decay 0.8)
```

**Dopamine Sources**:
| Signal | Weight | Positive | Trigger |
|--------|--------|----------|---------|
| Scene novelty | +0.5 | Reward | scene_change_rate > 0.1 |
| Forward progress | +0.3 | Reward | filtered_y > 20.0 |
| Stuck | −0.3/5s | Punishment | stuck_duration > 5s |
| Fallen | −0.8 | Punishment | _fallen == True |
| Cliff detected | −0.4 | Punishment | cliff_confirmed == True |
| Looming collision | −0.3 | Punishment | tau < 1.0 |

**MBON → LIF Injection** (Mechanism A, pre-spike):
| MBON | Target Pool | Gain | Range |
|------|-------------|------|-------|
| forward_bias | `self.v[self.forward]` | +0.15 | [−0.15, +0.15] |
| left_bias | `self.v[self.turn_left]` | +0.12 | [−0.12, +0.12] |
| right_bias | `self.v[self.turn_right]` | +0.12 | [−0.12, +0.12] |
| jump_bias | `self.v[self.jump_nodes]` | +0.20 | [−0.20, +0.20] |
| explore_bias | `escape_current` | ±2%/frame | [0.05, 0.25] |

### Expected Behavioral Gains

| Metric | Before | After | Timeline |
|--------|--------|-------|----------|
| Scene→action association | None (rule-only) | Learnable | After 500+ associations |
| Stuck events per session | ~15 | ~10 (−33%) | After 200+ learning steps |
| Healthy exploration time | ~60% | ~70% | After learning stabilizes |
| Catastrophic forgetting | N/A | Low | Sparse KC (5%), η=0.001, weight bounds |

**Learning Curve**:
- 0–1000 frames: Weights near-initial, behavior unchanged from baseline
- 1000–5000 frames: Strong dopamine events shape weights → subtle biases emerge
- 5000+ frames: Stable associations for frequent scenes → noticeably different behavior

### Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Catastrophic forgetting | Low | High | Sparse KC (5% active); η=0.001; weight bounds [-1, 1] |
| Proxy reward noise | Medium | Medium | Same imperfection exists in real flies; "fallen" (−0.8) is dominant signal |
| Weight explosion | Low | Medium | Clip to [-1, 1]; only active synapses modified |
| No direct game state (coin count) | High | Low | Proxy signals cover main behavioral outcomes; extensible API |
| LIF instability from MBON | Low | Medium | Conservative gains (0.10–0.20) vs tonic 0.18; tanh clipping |

---

## Cross-Phase Dependencies & Integration

### Dependency Graph

```
                ┌─────────────────────┐
                │     P1a: Color/UV   │◄──── No deps
                │     (4人天)         │
                └─────────┬───────────┘
                          │ Optional: color scene sig enriches KC input
                          ▼
P1b: EMD        ┌─────────────────────┐
(4人天) ◄── No deps                    │
                 │                     │
                 ▼                     │
                ┌─────────────────────┤
                │  P2: Small Target    │◄──── Depends on P1b ON/OFF channels
                │  (6人天)            │
                └─────────────────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │  P3: Mushroom Body   │◄──── Depends on P1a scene signature
                │  (10人天)           │
                └─────────────────────┘
```

### Execution Order Options

| Option | Schedule | Risk | Best For |
|--------|----------|------|----------|
| **A — Sequential** | P1a→P1b→P2→P3: 24天 | Lowest | Production stability |
| **B — Parallel P1** | (P1a∥P1b)→P2→P3: 20天 | Low | Balanced speed & safety (✅ **recommended**) |
| **C — Full parallel** | (P1a∥P1b)→(P2∥P3): 14天 | High | Research/experimental |

### Compute Budget Check

| Design | Overhead | % of 20 ms frame budget |
|--------|----------|-------------------------|
| P1a: Color/UV | 45 μs | 0.225% |
| P1b: EMD | 35 μs | 0.175% |
| P2: Small Target | 80 μs | 0.400% |
| P3: Mushroom Body | 30 μs | 0.150% |
| **Total** | **190 μs** | **0.950%** |

All four designs combined use < 1% of the 20 ms frame budget. ✅

### Return Dict Growth

`compute_flow()` return dict grows from 27 keys to ~56 keys. Acceptable (O(1) dict lookup). Optional: group into nested dict `flow["visual_signals"] = {"emd": ..., "color": ..., "targets": ...}`.

### Jump Pool Safety

Combined worst-case injection (tau 0.35 + target 0.60 + MBON 0.20 + tonic 0.18 = 1.63) exceeds threshold 1.0 only when all three coincide. **Each is transient and context-gated**. Mutual exclusion: when tau < TAU_NEAR, cap target injection to 0.20. The LIF neuron fires when it should (urgent jump) and resets.

---

## Code Modification Summary (All Phases)

### retina.py (21 changes + 4 new methods)

| Phase | # | Change | Type |
|-------|---|--------|------|
| P1a | A1 | CALIBRATION v2 with color/UV documentation | Edit |
| P1a | A2 | `_prev_color` ring buffer in `__init__()` | Insert |
| P1a | A3 | `encode_color()` — 10-channel color encoding | **New method** |
| P1a | A4 | `_per_cell_color()` — (N, 5) per-cell color vector | **New method** |
| P1a | A5 | Color features in `compute_flow()` | Insert |
| P1a | A6 | 10+ color keys in return dict | Append |
| P1a | A7 | `_prev_color.clear()` in `reset_temporal_state()` | Edit |
| P1b | B1 | EMD neighbor pairs + delay buffers in `__init__()` | Insert |
| P1b | B2 | `compute_emd()` — HR correlator ×4 dir ×2 channels | **New method** |
| P1b | B3 | `compute_emd()` call in `compute_flow()` | Insert |
| P1b | B4 | 10 EMD keys in return dict | Append |
| P1b | B5 | `_prev_on/off = None` in `reset_temporal_state()` | Edit |
| P2 | C1 | `_build_grid_maps()` utility | **New utility** |
| P2 | C2 | `_connected_components()` — 4-connectivity CCL | **New static method** |
| P2 | C3 | `compute_small_targets()` — center-surround + CCL | **New method** |
| P2 | C4 | `compute_small_targets()` call in `compute_flow()` | Insert |
| P2 | C5 | 7 target keys in return dict | Append |

### model.py (20+ changes + 2 new classes)

| Phase | # | Change | Type |
|-------|---|--------|------|
| P1a | A8 | 9 color state variables in `__init__()` | Insert |
| P1a | A9 | Read color signals from flow in `encode_retina()` | Insert |
| P1a | A10 | Enhanced drive formula (red_sal + uv_sal + green_sal) | Edit |
| P1a | A11 | 3 color modulation rules in `step()` | Insert |
| P1a | A12 | Optional 5-channel color projection (scene sig) | Insert |
| P1b | B6 | 14 EMD state variables in `__init__()` | Insert |
| P1b | B7 | Read EMD signals + derived compounds in `encode_retina()` | Insert |
| P1b | B8 | 4 EMD motor modulation rules in `step()` | Insert |
| P2 | C6 | **New class**: `TargetTracker` (Kalman + Hungarian) | **New class** |
| P2 | C7 | 7 target state variables in `__init__()` | Insert |
| P2 | C8 | Read targets + update tracker in `encode_retina()` | Insert |
| P2 | C9 | 3 target rules in `step()` **⚠️ with split-injection fix** | Insert (two zones) |
| P2 | C10 | `self.target_tracker.reset()` in `reset_scene()` | Edit |
| P3 | D2 | `from .mushroom_body import MushroomBody` | Insert |
| P3 | D3 | `self.mushroom = MushroomBody()` + gains in `__init__()` | Insert |
| P3 | D4 | `mushroom.encode(scene_sig)` in `encode_retina()` | Insert |
| P3 | D5 | `_compute_dopamine()` — proxy reward from 6 signals | **New method** |
| P3 | D6 | Dopamine + MBON→self.v injection in `step()` | Insert (pre-spike) |
| P3 | D7 | `self.mushroom.reset()` in `reset_scene()` | Edit |

### New Files

| Phase | File | Contents | Lines |
|-------|------|----------|-------|
| P3 | `fly64/mushroom_body.py` | `MushroomBody` class — KC projection, MBON, 3-factor Hebbian plasticity, eligibility trace | ~390 |

### main.py Changes

| Phase | Change | Description |
|-------|--------|-------------|
| P3 | D8 | Mirror `memory_ctrl.stuck_duration/fallen/_revisit_penalty` to model before `model.step()` |
| P3 | D9 | Add MB diagnostics to dashboard telemetry |

---

## Validation Strategy

### Per-Phase Validation

| Phase | Validation | Success Criteria |
|-------|-----------|-----------------|
| **P1a** | Run 3 SM64 scenes (grass, lava, sky) with color enabled | `sky_blue_index > 0.4` in sky scenes; `danger_red_index > 0.3` in lava scenes; scene sig hamming distance between contrasting scenes > 0.5 |
| **P1b** | Run Mario through corridor with moving Goomba | `emd_on_right/left` ~0 when static; `emd_off_right > 0.02` when Goomba passes left→right; `emd_on_up > 0.01` on elevator |
| **P2** | Run Mario near moving platform (rotating bridge) | `target_count > 0` within 5 frames of platform motion; `target_intercept_time` within ±2 frames of actual; jump success > 2× baseline |
| **P3** | Run 5000-frame learning session in same level | `assoc_count > 20` over session; MBON weights change > ±0.05; KC sparsity = 4–6% actual |

### Regression Checks (All Phases)

1. **No-fly test**: Run 3 identical 1000-frame sessions before & after each phase — ensure `forward_rate.mean()` changes < ±15% in static scenes
2. **Trigger test**: Place Mario in front of known trigger (lava, Goomba, platform) — ensure engineered reflexes fire faster than learned responses
3. **Compute budget**: Frame time must stay below 19 ms (leaving 1 ms headroom)
4. **Return dict completeness**: `compute_flow()` keys must match `encode_retina()` expectations (no KeyError on new keys)

---

## Release Checklist

### Pre-P1
- [ ] Git branch: `feature/visual-enhancements`
- [ ] Backup existing `scene_database.pkl` (will require rebuild with color signatures)
- [ ] Add `color_signature = False` default to preserve backward compat

### During P1a
- [ ] Verify `encode_color()` with 3 test scenes (green, blue, red-dominant)
- [ ] Verify drive formula output stays in [0, 1] in all test scenes
- [ ] Verify `sky_blue_index` and `danger_red_index` correct

### During P1b
- [ ] Verify EMD = 0 on static frame (reset check)
- [ ] Verify EMD > 0 on moving Goomba frame
- [ ] Verify ON/OFF ratio distinguishes motion direction

### During P2
- [ ] **Verify split-injection pattern** — jump `self.v` before line 537, turn `raw_x` after line 631
- [ ] Verify `TargetTracker` track creation after 2 consecutive detections
- [ ] Verify track pruning after 10 consecutive misses
- [ ] Verify `fg_fraction > 0.15` suppresses tracking updates

### During P3
- [ ] Verify KC sparsity = 5% (±1%) across 100 frames
- [ ] Verify dopamine smoothing α = 0.3
- [ ] Verify weight update only when |dopamine| > 0.3
- [ ] Verify MBON outputs start near-zero (|output| < 0.05 for first 100 frames)
- [ ] Run 5000-frame learning session — verify association count ≥ 20
- [ ] Run 50-frame main loop without main.py mirror — verify no KeyError from self.stuck_duration

### Pre-Merge
- [ ] All per-phase validations pass
- [ ] Regression checks pass (no-fly, trigger, compute, dict)
- [ ] Scene database rebuilt with color signatures (if `color_signature=True`)
- [ ] Documentation updated in `CALIBRATION` dict

---

*End of Implementation Roadmap — ready for captain review and delivery.*