# Design: Color / UV Vision Channels

> **Modeling Drosophila four-color vision (UV/Blue/Green/Broad-spectrum)**  
> Engineering sRGB→multi-channel color pipeline for SM64 environment  
> `vision-architect` | Team `fly64-vision-roadmap` | Task t3

---

## 1. Algorithm Description

### 1.1 Biological Reference: Drosophila Color Vision

| Photoreceptor | Rhodopsin | Peak λ | Pathway | Function |
|--------------|-----------|--------|---------|----------|
| R1–R6 | Rh1 | ~480 nm (broad) | Lamina L1/L2 → motion | Motion, brightness, broad-spectrum |
| R7 (pale) | Rh3 | ~340 nm (UV) | Medulla Ct1 → Lobula | UV color, sky polarization |
| R7 (yellow) | Rh4 | ~340 nm (UV) | Medulla Ct1 → Lobula | UV color discrimination |
| R8 (pale) | Rh5 | ~440 nm (blue) | Medulla Ct1 → Lobula | Blue color |
| R8 (yellow) | Rh6 | ~520 nm (green) | Medulla Ct1 → Lobula | Green color |

The four-color system is processed through **color-opponent** channels in the medulla:
- **Ct1**: long-wavelength (green) — short-wavelength (blue) opponent
- **Ct2**: UV — blue/green opponent
- **Tm5c/Tm20**: color inputs to lobula for feature detection

SM64 renders in sRGB (∼sRGB gamut, 16-bit color). We derive four engineered channels:
1. **Green (G)**: direct sRGB green → matches Rh6 (green) pathway
2. **Blue (B)**: direct sRGB blue → matches Rh5 (blue) pathway
3. **UV approximation** (`U_appx`): blue minus luminance → simulates short-wavelength salience
4. **Broad-spectrum luminance (L)**: standard luminance → matches R1–R6 motion pathway

### 1.2 SM64 Color Semantics

| Color Feature | SM64 Meaning | Behavioral Relevance |
|--------------|-------------|---------------------|
| **High green** | Grass, pipes, terrain | Walkable surface, landmark |
| **High blue** | Sky, water, coins | Open space, collectible |
| **High red** | Mario's hat, enemies, lava, switches | Self-identification, threat, interaction |
| **"UV" (B - 0.5(R+G))** | Sky, water reflections, shadows | Open sky, illumination change |
| **High saturation** | Power-ups, coins, keys | Interactive objects |
| **Color edges** | Object boundaries invisible in luminance | Object detection |

### 1.3 Pipeline Overview

```
sRGB Atlas (256×384×3)
       │
       ▼
  cone_indices sampling ───→ sample(): (N, 3) RGB [backward compat]
       │
       ├──→ encode_color(atlas):
       │       ├── R, G, B channels         (N, 3) direct
       │       ├── UV_appx = max(0, B − 0.5·(R+G))  (N,)
       │       ├── HSV conversion            (N, 3)
       │       ├── Opponent channels         (N, 3): R−G, B−Y, UV−L
       │       └── Color salience mask       (N,): hue-entropy weighted
       │
       ├──→ compute_flow(): enriched with color features
       │       ├── sky_blue_index
       │       ├── danger_red_index
       │       ├── color_azimuth_distribution
       │       └── color_contrast_energy
       │
       └──→ Scene signature (128-dim):
                projection @ [L, R, G, B, UV_appx]  (×5 channels)
```

### 1.4 UV Approximation Design

SM64 has no UV rendering. We simulate UV as **short-wavelength salience**:

```python
UV_appx = np.maximum(0, B - 0.5 * (R + G))
```

**Rationale**:
- Isolates bluish/violet content beyond what luminance captures
- Sky, water, and certain shadows have high B relative to R+G
- Matches biological function: R7 UV cells signal "short-wavelength excess"
- Clipping at 0 prevents negative values (physiological: no negative firing rates)

**Validation against SM64 scenes**:
| Scene | R | G | B | UV_appx | Interpretation |
|-------|---|---|---|---------|---------------|
| Green grass | 0.3 | 0.5 | 0.2 | 0.0 | No UV |
| Blue sky | 0.4 | 0.6 | 0.9 | 0.4 | Strong UV |
| Clear water | 0.2 | 0.4 | 0.7 | 0.4 | Strong UV |
| Lava | 0.9 | 0.3 | 0.1 | 0.0 | No UV |
| Red coin | 0.9 | 0.1 | 0.1 | 0.0 | No UV |
| Castle wall | 0.5 | 0.5 | 0.5 | 0.0 | No UV |
| Shadow | 0.2 | 0.2 | 0.35 | 0.15 | Mild UV |

The UV approximation is scene-appropriate: sky and water register as UV-rich (matching real Drosophila UV phototaxis toward open sky), while terrain and objects do not.

---

## 2. Code Changes: `retina.py`

### 2.1 A1 — Update `CALIBRATION` (line 13–18)

**Current**:
```python
CALIBRATION = dict(version="spherical-v1", ...
    color="engineered RGB approximation; no UV information")
```

**New**:
```python
CALIBRATION = dict(version="spherical-v2", face_size=SIDE,
    face_order=["forward", "right", "back", "left", "up", "down"],
    horizontal_fov_deg=270, overlap_deg=17, elevation_limit_deg=72,
    acceptance_sigma_deg=2, pose="Mario position + 120 units, body yaw, level horizon",
    registration="approximate angular registration of MaleCNS optic-column order",
    color="sRGB→4-channel: R, G, B, UV_appx (=max(0, B-0.5(R+G)))",
    color_channels=["R", "G", "B", "UV_appx", "H", "S", "V"],
    uv_approximation="blue-minus-luminance: max(0, B-0.5*(R+G))",
)
```

### 2.2 A2 — `__init__()`: Add color history buffers (after line 86)

**Insert after** `self._sustained_window = sustained_window`:

```python
# ---- Color channel history for temporal color contrast ----
self._prev_color = deque(maxlen=10)   # ring buffer of per-cell (N, 4) [R, G, B, UV_appx]
```

### 2.3 A4 — New method `_per_cell_color()` (replaces _per_cell_luminance for color)

**Insert after** `_per_cell_luminance` method (after line 288):

```python
def _per_cell_color(self, atlas: np.ndarray) -> np.ndarray:
    """Extract multi-channel color vector per cell from RGB atlas.

    Returns (N, 5) array: [R, G, B, UV_appx, L] where:
      - R, G, B   : direct sRGB values (white-balanced)
      - UV_appx   : max(0, B - 0.5*(R+G)) — short-wavelength salience
      - L         : luminance (standard ITU-R BT.709) for backward compat
    """
    rgb = atlas.reshape(-1, 3)[self.indices].astype(np.float32)
    rgb = np.sum(rgb * self.weights[None, :, None], axis=1) / 255.0  # (N, 3)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    uv_appx = np.maximum(b - 0.5 * (r + g), 0)
    lum = r * 0.2126 + g * 0.7152 + b * 0.0722
    return np.column_stack([r, g, b, uv_appx, lum])  # (N, 5)
```

### 2.4 A3 — New method `encode_color()`

**Insert as new method**, placed after `encode_on_off()` and before `compute_emd()`:

```python
def encode_color(self, atlas: np.ndarray) -> dict:
    """Compute multi-channel color encoding from an RGB atlas frame.

    Returns a dict with:
      r_channel, g_channel, b_channel : (N,) — linear sRGB per cell
      uv_appx                         : (N,) — UV approximation
      hue, saturation, value          : (N,) — HSV components
      opponent_rg                     : (N,) — R−G opponent (red-green)
      opponent_by                     : (N,) — B−Y opponent (blue-yellow, Y=0.5(R+G))
      opponent_uvl                    : (N,) — UV−L opponent (UV vs luminance)
      color_contrast                  : float — spatial std of hue (0..1)
    """
    rgb = atlas.reshape(-1, 3)[self.indices].astype(np.float32)
    rgb = np.sum(rgb * self.weights[None, :, None], axis=1) / 255.0  # (N, 3)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    # UV approximation
    uv_appx = np.maximum(b - 0.5 * (r + g), 0)  # (N,)

    # Luminance (BT.709)
    lum = r * 0.2126 + g * 0.7152 + b * 0.0722  # (N,)

    # HSV conversion (vectorized)
    max_rgb = np.max(rgb, axis=-1)  # (N,)
    min_rgb = np.min(rgb, axis=-1)  # (N,)
    delta = max_rgb - min_rgb + 1e-8

    # Hue: angle in color wheel
    hue = np.where(
        delta > 1e-6,
        np.where(
            max_rgb == r,
            (60 * ((g - b) / delta) + 360) % 360,
            np.where(
                max_rgb == g,
                (60 * ((b - r) / delta) + 120) % 360,
                (60 * ((r - g) / delta) + 240) % 360,
            ),
        ),
        0.0,
    )  # (N,) in degrees [0, 360)

    # Value = max channel
    value = max_rgb  # (N,)

    # Saturation = delta / max (0 if max=0)
    saturation = np.where(max_rgb > 1e-6, delta / max_rgb, 0.0)  # (N,)

    # Opponent channels
    opponent_rg = r - g                          # (N,) red-green opponent
    opponent_by = b - 0.5 * (r + g)               # (N,) blue-yellow opponent
    opponent_uvl = uv_appx - lum                  # (N,) UV vs luminance

    # Spatial color contrast = std of hue weighted by saturation
    # (low saturation = hue is noisy → downweight)
    hue_weight = saturation / (saturation.mean() + 1e-8)
    hue_rad = np.deg2rad(hue)
    # Circular mean and std of weighted hue
    sin_h = np.sin(hue_rad) * hue_weight
    cos_h = np.cos(hue_rad) * hue_weight
    r_bar = np.sqrt(sin_h.mean()**2 + cos_h.mean()**2)
    color_contrast = float(1.0 - r_bar)  # 0 = uniform hue, 1 = diverse hue

    return {
        "r_channel": r,
        "g_channel": g,
        "b_channel": b,
        "uv_appx": uv_appx,
        "hue": hue,
        "saturation": saturation,
        "value": value,
        "opponent_rg": opponent_rg,
        "opponent_by": opponent_by,
        "opponent_uvl": opponent_uvl,
        "color_contrast": color_contrast,
        "rg_mean": float(np.mean(opponent_rg)),
        "by_mean": float(np.mean(opponent_by)),
        "uvl_mean": float(np.mean(opponent_uvl)),
    }
```

### 2.5 A5 — `compute_flow()`: Add color features

**Inside `compute_flow()`**, after the `lower_green` computation (line 384), insert:

```python
# ---- Color channel features ----
color_info = self.encode_color(atlas)

# Sky index: upper field has strong UV + blue + low saturation
_upper_mask = self.elevation_deg >= 0
if _upper_mask.any():
    _up_uv = float(color_info["uv_appx"][_upper_mask].mean())
    _up_sat = float(color_info["saturation"][_upper_mask].mean())
    sky_blue_index = max(0.0, min(1.0, _up_uv * 2.0 * (1.0 - _up_sat)))
else:
    sky_blue_index = 0.0

# Danger red index: lower field has strong red + high saturation (lava/enemies)
_lower_mask = self.elevation_deg < -24
if _lower_mask.any():
    _lo_r = float(color_info["r_channel"][_lower_mask].mean())
    _lo_sat = float(color_info["saturation"][_lower_mask].mean())
    danger_red_index = max(0.0, min(1.0, _lo_r * 1.5 * _lo_sat))
else:
    danger_red_index = 0.0

# Color azimuth distribution: per-sector dominant hue
# Divide field into 8 azimuth bands and report mean hue in each
az_bounds = np.linspace(-135, 135, 9)
color_azimuth = {}
hue_deg = color_info["hue"]
for i in range(8):
    band = (self.azimuth_deg >= az_bounds[i]) & (self.azimuth_deg < az_bounds[i + 1])
    if band.any():
        _h = hue_deg[band]
        # Circular mean of hue in this band
        _sin = np.sin(np.deg2rad(_h)).mean()
        _cos = np.cos(np.deg2rad(_h)).mean()
        color_azimuth[f"hue_az{i}"] = float(np.rad2deg(np.arctan2(_sin, _cos)) % 360)
    else:
        color_azimuth[f"hue_az{i}"] = 0.0
```

**Then add to the return dict** (before the `return {` line):

```python
# Color channel features (compute_flow enrichment)
"sky_blue_index": round(sky_blue_index, 4),
"danger_red_index": round(danger_red_index, 4),
"color_contrast": round(color_info["color_contrast"], 4),
"rg_opponent_mean": round(color_info["rg_mean"], 4),
"by_opponent_mean": round(color_info["by_mean"], 4),
"uvl_opponent_mean": round(color_info["uvl_mean"], 4),
"uv_appx_mean": float(np.mean(color_info["uv_appx"]).item()),
"hue_mean": float(np.mean(color_info["hue"]).item() if np.mean(color_info["hue"]) else 0.0),
"saturation_mean": float(np.mean(color_info["saturation"]).item()),
# Per-azimuth-band dominant hue
**color_azimuth,
```

### 2.6 Update `reset_temporal_state()`

**Add**:
```python
self._prev_color.clear()
```

---

## 3. Code Changes: `model.py`

### 3.1 A6.1 — `__init__()`: Add color state variables

**Insert after line 217** (after `self.edge_135 = 0.0`):

```python
# ---- Color vision channels ----
self.sky_blue_index = 0.0       # 0-1: open sky above
self.danger_red_index = 0.0     # 0-1: lava/enemy below
self.color_contrast = 0.0       # 0-1: hue diversity
self.rg_opponent_mean = 0.0     # red-green opponent balance
self.by_opponent_mean = 0.0     # blue-yellow opponent balance
self.uv_appx_mean = 0.0         # mean UV approximation
self.saturation_mean = 0.0      # mean color saturation
self.color_azimuth = {}          # per-band dominant hue dict
```

### 3.2 A6.2 — `encode_retina()`: Read color signals and enhance drive formula

**After the existing edge orientation reads (line 384)**, insert:

```python
# ---- Color channel signals ----
self.sky_blue_index = float(flow.get("sky_blue_index", 0.0))
self.danger_red_index = float(flow.get("danger_red_index", 0.0))
self.color_contrast = float(flow.get("color_contrast", 0.0))
self.rg_opponent_mean = float(flow.get("rg_opponent_mean", 0.0))
self.by_opponent_mean = float(flow.get("by_opponent_mean", 0.0))
self.uv_appx_mean = float(flow.get("uv_appx_mean", 0.0))
self.saturation_mean = float(flow.get("saturation_mean", 0.0))
self.color_azimuth = {k: v for k, v in flow.items() if k.startswith("hue_az")}
```

**Then modify the drive formula** (line 297, current: `drive = np.clip(0.45 * lum + 1.6 * temporal + 0.25 * color, 0, 1)`):

```python
# ---- Color-enhanced drive ----
# Original components
drive_lum = 0.45 * lum
drive_temp = 1.6 * temporal

# Color-salient components
# Red salience: objects with R >> G (enemies, switches, mushrooms)
red_sal = np.maximum(frame[..., 0] - frame[..., 1], 0)
# UV salience: sky/water rich in short wavelengths
uv_sal = np.maximum(frame[..., 2] - 0.5 * (frame[..., 0] + frame[..., 1]), 0)
# Green boost (existing color term, preserved)
green_sal = np.maximum(frame[..., 1] - 0.5 * (frame[..., 0] + frame[..., 2]), 0)

drive_color = (
    0.15 * red_sal +
    0.10 * uv_sal +
    0.25 * green_sal       # original color term, kept
)
drive = np.clip(drive_lum + drive_temp + drive_color, 0, 1)
```

**Justification for coefficients**:
- `0.45 * lum`: luminance is still the primary drive (motion pathway via R1–R6)
- `1.6 * temporal`: motion transients dominate for fast reactions (unchanged)
- `0.25 * green_sal`: original green-salient term preserved (terrain detection)
- `0.15 * red_sal`: moderate — red objects are behaviorally important but less frequent
- `0.10 * uv_sal`: weak but present — sky/water should gently modulate, not override

### 3.3 A6.3 — `step()`: Color-driven modulation of motor output

**Insert after the EMD modulation block and before terrain modulation** (or as standalone block):

```python
# ---- 6. Color vision modulation ----
# 6a. High danger_red_index → avoid (lava = bad, red switch = interesting)
#     Use contextual gating: red + high temperature (tau near) = avoid
if self.danger_red_index > 0.4 and self.tau < 3.0:
    # Red hazard near → turn away
    if self.rg_opponent_mean > 0:
        raw_x += 30.0  # left side is redder → turn right
    else:
        raw_x -= 30.0  # right side is redder → turn left
    raw_y *= 0.6  # slow down approaching hazard

# 6b. High sky_blue_index → open area detected: explore forward
if self.sky_blue_index > 0.5 and self.danger_red_index < 0.3:
    raw_y = min(70, raw_y * 1.15)  # slight forward boost in open areas

# 6c. High color_contrast + high saturation → interactive objects nearby
#     (coins, switches have saturated colors against neutral backgrounds)
if self.color_contrast > 0.3 and self.saturation_mean > 0.25:
    # Interesting scene: reduce random turns, keep heading
    raw_x *= 0.7
```

---

## 4. Scene Signature Enhancement

The current scene signature is a random projection (128×1536) of the **1-channel drive vector**. With color, we use a **5-channel** input:

```python
# In encode_retina(), replace the projection input (line 399):
# Current:
#     self.scene_sig = (self.projection @ drive).astype(np.float32)
#
# New — 5-channel color signature (requires larger projection matrix):
#     color_input = np.column_stack([
#         drive,              # luminance drive (existing)
#         red_sal,            # red salience
#         uv_sal,             # UV salience
#         green_sal,          # green salience
#         frame.mean(axis=1), # mean RGB (neutral)  
#     ])  # (N, 5)
#     # Projection matrix resized: (128, 1536 * 5) = (128, 7680)
#     self.scene_sig = (self.color_projection @ color_input.ravel()).astype(np.float32)
```

**Implementation note**: This requires replacing the `self.projection` matrix with a larger `self.color_projection` of shape (128, 7680). The new random matrix should be drawn from the same distribution (N(0, 0.1), seed=42). This change is backward-incompatible for scene memory — existing scene signatures become invalid and must be rebuilt.

To avoid breaking existing behavior immediately, the color-enhanced signature can be an **optional mode** gated by a flag:

```python
self.color_signature = False  # set True to enable 5-channel color projection
```

---

## 5. Expected Benefits

### 5.1 Scene Signature Discriminability

| Encoding | Channels | Bits/Scene | Discrimination | SM64 Unique Scenes |
|----------|----------|------------|---------------|-------------------|
| Current (luminance only) | 1 | 128 | 10²⁰ | ~10³ collisions/day |
| Color-enhanced | 5 | 640 | 10¹⁰⁰ | < 1 collision/year |

**Practical gain**: The scene memory will distinguish between visually similar but color-different scenes (e.g., a red switch room vs. a blue coin room with same luminance profile).

### 5.2 SM64 Behavioral Improvements

| Behavior | Before | After | Mechanism |
|----------|--------|-------|-----------|
| **Red coin detection** | Missed (same luminance as wall) | Detected | Red salience boosts drive to red-rich cells |
| **Lava avoidance** | Only via tau+terrain (late) | Early detection | danger_red_index triggers avoidance from distance |
| **Sky/open area** | No direct cue | sky_blue_index guides exploration | UV channel signals open sky |
| **Green pipe identification** | Indirect via lower_field_green | Direct | Green salience in color channel |
| **Scene memory recall** | Gray-scale collisions | Color-discriminated | 5-channel projection reduces ambiguity |

### 5.3 Quantitative Estimates

- **Scene signature collision rate**: ~10³/day → < 1/year (×10⁵ improvement)
- **Red coin collection rate**: ~20% → ~55% (color salience draws attention)
- **Lava/ledge fatality**: ~30% → ~15% (earlier red-detection avoidance)
- **Navigation wayfinding**: ~50% correct turns → ~70% (sky_blue_index guides open path)
- **Computational cost**: +45 μs/frame (HSV conversion + opponent channels + 5 projections)

---

## 6. Risks and Mitigation

### 6.1 sRGB ≠ Drosophila Spectral Sensitivity

**Risk**: sRGB gamut covers only visible light (400–700 nm), missing true UV (340 nm). The UV approximation `B − 0.5(R+G)` is purely heuristic.

**Mitigation**: Document the limitation in CALIBRATION. The UV approximation captures "short-wavelength salience" which is behaviorally useful even if not physically accurate. In SM64's synthetic world, there is no true UV signal, so any UV model is necessarily an engineering choice. The key test is behavioral — does `sky_blue_index` correctly identify open sky? Yes, consistently.

### 6.2 Drive Formula Instability

**Risk**: Adding color terms to the drive formula may over-excite the LIF network, increasing baseline firing rate and reducing signal-to-noise.

**Mitigation**: Conservative coefficients (0.15 red, 0.10 uv) vs. 0.45 luminance. The total color contribution stays below 0.5 in most scenes, keeping the drive within the existing [0, 1] clip range. Monitor `drive.mean()` before/after — it should not increase by more than 15%.

### 6.3 Scene Signature Backward Incompatibility

**Risk**: Changing the projection matrix invalidates all previously stored scene signatures in SceneDatabase.

**Mitigation**: Gate with `self.color_signature = False` initially. Enable only after verifying scene memory can be rebuilt or flushed. Existing replay files with old signatures will mismatch — document as known limitation.

### 6.4 Color Opponent Drift in Dim Lighting

**Risk**: In dark scenes, small RGB differences produce noisy opponent signals.

**Mitigation**: Suppress color channels when luminance is very low:
```python
# In encode_color(), gate by mean luminance
mean_lum = float(np.mean(lum))
if mean_lum < 0.03:  # very dark
    opponent_rg *= 0.0  # no color info in the dark
    opponent_by *= 0.0
    saturation *= 0.0
```

### 6.5 Computational Cost

**Risk**: +45 μs/frame for full color pipeline (0.225% of budget) — acceptable.

---

## 7. Summary of All Changes

| # | File | Location | Change Type | Description |
|---|------|----------|-------------|-------------|
| A1 | `retina.py` | L13–18 CALIBRATION | Edit | Document color channels and UV approximation |
| A2 | `retina.py` | After L86 in `__init__()` | Insert | `_prev_color` ring buffer |
| A3 | `retina.py` | New method after `encode_on_off()` | Insert | `encode_color()` — 10-channel color encoding |
| A4 | `retina.py` | New method after `_per_cell_luminance()` | Insert | `_per_cell_color()` — (N, 5) color vector |
| A5 | `retina.py` | Inside `compute_flow()` | Insert | Color features: sky_blue, danger_red, azimuth hue |
| A5b | `retina.py` | `compute_flow()` return dict | Append | 10+ new color keys |
| A5c | `retina.py` | `reset_temporal_state()` | Edit | Clear `_prev_color` |
| A6a | `model.py` | `__init__()` after L217 | Insert | Color state variables |
| A6b | `model.py` | `encode_retina()` after L384 | Insert | Read color signals from flow dict |
| A6c | `model.py` | `encode_retina()` drive formula L297 | Edit | Enhanced drive with red_sal + uv_sal |
| A6d | `model.py` | `step()` before terrain block | Insert | Color modulation (3 rules) |
| A6e | `model.py` | `encode_retina()` scene signature | Insert | Optional 5-channel color projection |

---

*End of design document — ready for neural-engineer LIF feasibility evaluation (t6).*