"""Spherical compound-eye sampling, independent of the observer framebuffer.

The measured optic-column order is retained. Its registration to angular
coordinates is engineered, NOT a measured MaleCNS optical calibration.
Azimuth bounds approximate NeuroMechFly's 270-degree binocular field.
RGB is not UV; acceptance width and vertical coverage are model parameters.
"""
import numpy as np
from collections import deque

SIDE = 128
PREVIEW_WIDTH, PREVIEW_HEIGHT = 256, 128
CALIBRATION = dict(version="spherical-v1", face_size=SIDE,
    face_order=["forward", "right", "back", "left", "up", "down"],
    horizontal_fov_deg=270, overlap_deg=17, elevation_limit_deg=72,
    acceptance_sigma_deg=2, pose="Mario position + 120 units, body yaw, level horizon",
    registration="approximate angular registration of MaleCNS optic-column order",
    color="engineered RGB approximation; no UV information")

_EPS = 1e-8

# Face right/up/forward bases, identical to native fly64_vision.c.
BASES = np.asarray([
    [[1,0,0],[0,1,0],[0,0,1]], [[0,0,-1],[0,1,0],[1,0,0]],
    [[-1,0,0],[0,1,0],[0,0,-1]], [[0,0,1],[0,1,0],[-1,0,0]],
    [[1,0,0],[0,0,-1],[0,1,0]], [[1,0,0],[0,0,1],[0,-1,0]],
], dtype=np.float32)


def angular_rays(azimuth, elevation):
    a, e = np.deg2rad(azimuth), np.deg2rad(elevation)
    return np.stack((np.sin(a)*np.cos(e), np.sin(e), np.cos(a)*np.cos(e)), axis=-1)


def atlas_indices(rays):
    """Nearest texel, choosing the face for EACH ray (also across seams)."""
    rays = np.asarray(rays, np.float32)
    dot = rays @ BASES[:, 2].T
    face = np.argmax(dot, axis=-1)
    z = np.take_along_axis(dot, face[..., None], axis=-1)[..., 0]
    u = np.sum(rays * BASES[face, 0], axis=-1) / z
    v = np.sum(rays * BASES[face, 1], axis=-1) / z
    x = np.clip(((u+1)*.5*SIDE).astype(int), 0, SIDE-1)
    y = np.clip(((1-v)*.5*SIDE).astype(int), 0, SIDE-1)
    return ((face//3*SIDE+y)*(3*SIDE) + face%3*SIDE+x).astype(np.int32)


def cone_indices(rays):
    """Seven weighted samples per receptor, on the sphere, not blurred seams."""
    rays = np.asarray(rays, np.float32)
    tangent = np.cross(rays, np.array([0,1,0], np.float32))
    pole = np.linalg.norm(tangent, axis=-1) < 1e-5
    tangent[pole] = np.cross(rays[pole], np.array([1,0,0], np.float32))
    tangent /= np.linalg.norm(tangent, axis=-1, keepdims=True)
    vertical = np.cross(tangent, rays)
    theta = np.arange(6)*np.pi/3
    radius = np.deg2rad(CALIBRATION["acceptance_sigma_deg"])*np.sqrt(2)
    ring = (rays[:,None]*np.cos(radius) + np.sin(radius)*(
        tangent[:,None]*np.cos(theta)[None,:,None] + vertical[:,None]*np.sin(theta)[None,:,None]))
    return atlas_indices(np.concatenate((rays[:,None], ring), axis=1))


class SphericalRetina:
    def __init__(self, visual_pixels, sustained_window=5):
        """Multi-channel spherical compound-eye retina.

        Parameters
        ----------
        visual_pixels : ndarray
            (N, 2) pixel coordinates mapping optic-column order to atlas texels.
        sustained_window : int
            Number of frames for the sustained-channel sliding-window contrast.
        """
        pixels = np.asarray(visual_pixels, float)
        eye = (pixels[:,1] >= 32).astype(int)
        horizontal = (pixels[:,1] % 32)/31
        # Existing column atlas goes left-to-right within each eye.
        self.azimuth_deg = np.where(eye == 0, -135, -8.5) + horizontal*143.5
        self.elevation_deg = 72 - pixels[:,0]/47*144
        self.rays = angular_rays(self.azimuth_deg, self.elevation_deg)
        self.indices = cone_indices(self.rays)
        self.weights = np.array([.25]+[.125]*6, np.float32)

        # ---- Luminance history for ON/OFF and sustained channels ----
        self._prev_lum = deque(maxlen=10)   # ring buffer of per-cell luminance
        self._sustained_window = sustained_window

        # ---- Edge orientation: build neighbor pairs from visual_pixels grid ----
        # visual_pixels: (N, 2) with (row, col) in 48×64 atlas, col 0-31 left eye, 32-63 right eye.
        # Visual cells are sampled at stride ~2 in the grid (e.g. linspace from 0 to 3071 for 1536 cells).
        # We find the nearest sampled neighbor in each of the 4 cardinal directions.
        self._vp_rc = visual_pixels.astype(np.int32) if hasattr(visual_pixels, 'dtype') \
            else np.asarray(visual_pixels, np.int32)
        n_cells = len(self._vp_rc)

        # For each cell, find the next cell to the right (same row, larger col) — edge_0 (horizontal)
        # and the next cell below (same col, larger row) — edge_90 (vertical).
        # Then derive edge_45 and edge_135 as combinations.
        # Build lookup: for each (r,c) store cell index
        idx_map = {}
        for idx, (r, c) in enumerate(self._vp_rc):
            idx_map[(r, c)] = idx

        # For each cell, look for the nearest sampled neighbor to the right (horizontal 0°) and
        # below (vertical 90°).  Since sampling is regular (stride ~2) the nearest right neighbor
        # is the smallest dc>0 such that (r, c+dc) exists.
        h_pairs, v_pairs = [], []
        for idx, (r, c) in enumerate(self._vp_rc):
            # Horizontal: same row, rightward
            same_eye = c < 32
            for dc in range(1, 64 - c):
                nb = (r, c + dc)
                if nb in idx_map and (nb[1] < 32) == same_eye:
                    h_pairs.append((idx, idx_map[nb]))
                    break
            # Vertical: same column, downward
            for dr in range(1, 48 - r):
                nb = (r + dr, c)
                if nb in idx_map and (nb[1] < 32) == same_eye:
                    v_pairs.append((idx, idx_map[nb]))
                    break

        # Diagonal 45°: combine horizontal+vertical offset: neighbor at (r+dr, c+dc) where
        # (r, c+dc) exists and (r+dr, c+dc) exists.
        # We can simply use the same h/v stride to form 45° pairs.
        # For each horizontal pair (idxA→idxB) where A=(r,c) and B=(r,c+dc),
        # look for the cell below B at (r+dr, c+dc) where dr is the vertical stride at that cell.
        d45_pairs, d135_pairs = [], []
        for idx_h, (idx_a, idx_b) in enumerate(h_pairs[:len(v_pairs)]):
            r_a, c_a = self._vp_rc[idx_a]
            r_b, c_b = self._vp_rc[idx_b]
            dc = c_b - c_a
            # 45°: cell at (r_a+dr, c_a+dc) where dr is the vertical stride from the row below
            for dr in range(1, 48 - r_a):
                nb = (r_a + dr, c_a + dc)
                if nb in idx_map and (nb[1] < 32) == (c_a < 32):
                    d45_pairs.append((idx_a, idx_map[nb]))
                    break
            # 135°: anti-diagonal — |lum(r_a, c_a+dc) - lum(r_a+dr, c_a)|
            # using the vertical stride from (r_a, c_a) to get (r_a+dr, c_a)
            for dr in range(1, 48 - r_a):
                nb_vert = (r_a + dr, c_a)
                if nb_vert in idx_map and (nb_vert[1] < 32) == (c_a < 32):
                    # pair (r_a, c_a+dc) with (r_a+dr, c_a) where dc from horizontal stride
                    if (r_a, c_b) in idx_map:
                        d135_pairs.append((idx_map[(r_a, c_b)], idx_map[nb_vert]))
                    break

        self._edge_pairs = {
            "edge_0": np.asarray(h_pairs, dtype=np.int32) if h_pairs else np.empty((0, 2), dtype=np.int32),
            "edge_90": np.asarray(v_pairs, dtype=np.int32) if v_pairs else np.empty((0, 2), dtype=np.int32),
            "edge_45": np.asarray(d45_pairs, dtype=np.int32) if d45_pairs else np.empty((0, 2), dtype=np.int32),
            "edge_135": np.asarray(d135_pairs, dtype=np.int32) if d135_pairs else np.empty((0, 2), dtype=np.int32),
        }
        self._edge_names = ["edge_0", "edge_45", "edge_90", "edge_135"]

        # ---- 16 azimuth-elevation sector masks (8 horizontal x 2 vertical) ----
        # Visual field spans -135° to +135° (270° total), each azimuth band = 33.75°.
        az_bounds = np.linspace(-135, 135, 9)  # 9 edges → 8 bands
        upper = self.elevation_deg >= 0
        lower = ~upper
        self._sector_names = tuple(
            f"az{i}_{v}" for i in range(8) for v in ("upper", "lower")
        )
        self._sector_masks = {}
        for i in range(8):
            band = (self.azimuth_deg >= az_bounds[i]) & (self.azimuth_deg < az_bounds[i + 1])
            self._sector_masks[f"az{i}_upper"] = band & upper
            self._sector_masks[f"az{i}_lower"] = band & lower

        # For backward compatibility keep 4-band analysis
        self._old_sector_names = (
            "left_upper","left_lower",
            "center-left_upper","center-left_lower",
            "center-right_upper","center-right_lower",
            "right_upper","right_lower",
        )
        _left = self.azimuth_deg < -67.5
        _ctr_left = (~_left) & (self.azimuth_deg < 0)
        _ctr_right = (~_left) & (~_ctr_left) & (self.azimuth_deg < 67.5)
        _right = self.azimuth_deg >= 67.5
        self._old_sector_masks = {}
        for h_name, h_mask in (("left", _left), ("center-left", _ctr_left),
                               ("center-right", _ctr_right), ("right", _right)):
            self._old_sector_masks[h_name + "_upper"] = h_mask & upper
            self._old_sector_masks[h_name + "_lower"] = h_mask & lower

        # ---- Masks for flow-signal computations ----
        self._left_half = self.azimuth_deg < 0           # azimuth < 0
        self._right_half = ~self._left_half               # azimuth >= 0
        self._center_60 = np.abs(self.azimuth_deg) <= 30  # central 60 degrees
        self._periphery_60 = ~self._center_60             # peripheral
        self._lower_third = self.elevation_deg < -24      # lower 1/3 of field

        # Two equidistant fisheye previews; black means outside the eye's field.
        yy, xx = np.mgrid[0:PREVIEW_HEIGHT,0:PREVIEW_WIDTH]
        eye = xx//PREVIEW_HEIGHT
        u = ((xx%PREVIEW_HEIGHT)+.5-PREVIEW_HEIGHT/2)/(PREVIEW_HEIGHT/2)
        v = (PREVIEW_HEIGHT/2-yy-.5)/(PREVIEW_HEIGHT/2)
        radius = np.hypot(u,v)
        angle = radius*np.pi/2
        scale = np.divide(np.sin(angle), radius, out=np.ones_like(radius), where=radius>0)
        local = np.stack((u*scale,v*scale,np.cos(angle)),axis=-1)
        a = np.deg2rad(np.where(eye == 0,-63.25,63.25))
        rays = np.stack((np.cos(a)*local[...,0]+np.sin(a)*local[...,2],local[...,1],
                         -np.sin(a)*local[...,0]+np.cos(a)*local[...,2]),axis=-1)
        az = np.rad2deg(np.arctan2(rays[...,0],rays[...,2]))
        el = np.rad2deg(np.arcsin(np.clip(rays[...,1],-1,1)))
        self.mask = (radius<=1)&(np.abs(el)<=72)&np.where(eye==0,(az>=-135)&(az<=8.5),(az>=-8.5)&(az<=135))
        self.preview_indices = cone_indices(rays.reshape(-1,3))

    @property
    def n_cells(self) -> int:
        """Number of visual sampling cells (1536 for standard MaleCNS)."""
        return len(self.rays)

    # ---- ON/OFF and sustained channel computation ----

    def encode_on_off(self, atlas: np.ndarray) -> dict:
        """Compute ON/OFF and sustained channels from an RGB atlas frame.

        Parameters
        ----------
        atlas : ndarray, shape (256, 384, 3)
            Six-face first-person RGB atlas.

        Returns
        -------
        dict with keys:
            on_channel  : ndarray, (N,) — positive luminance transients
            off_channel : ndarray, (N,) — negative luminance transients (positive values)
            sustained   : ndarray, (N,) — |mean(window[-S:]) - mean(window[-2S:-S])|
        """
        # Per-cell luminance
        rgb = atlas.reshape(-1, 3)[self.indices].astype(np.float32)
        rgb = np.sum(rgb * self.weights[None, :, None], axis=1) / 255.0  # (N, 3)
        lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)  # (N,)

        # ---- ON/OFF channels from consecutive frame differences ----
        if not self._prev_lum:
            self._prev_lum.append(lum.copy())
            on_channel = np.zeros_like(lum)
            off_channel = np.zeros_like(lum)
            sustained = np.zeros_like(lum)
        else:
            prev_lum = self._prev_lum[-1]
            diff = lum - prev_lum
            on_channel = np.clip(diff, 0, None)
            off_channel = np.clip(-diff, 0, None)
            self._prev_lum.append(lum.copy())

            # ---- Sustained: |mean(last 5-frame window) - mean(previous 5-frame window)| ----
            S = self._sustained_window
            hist = list(self._prev_lum)
            if len(hist) >= 2 * S:
                recent = np.mean(np.stack(hist[-S:], axis=0), axis=0)
                earlier = np.mean(np.stack(hist[-2 * S:-S], axis=0), axis=0)
                sustained = np.abs(recent - earlier)
            elif len(hist) >= 2:
                # Fewer frames available — use what we have
                half = max(len(hist) // 2, 1)
                recent = np.mean(np.stack(hist[-half:], axis=0), axis=0)
                earlier = np.mean(np.stack(hist[:-half], axis=0), axis=0) if len(hist) > half else \
                    np.mean(np.stack(hist, axis=0), axis=0)
                sustained = np.abs(recent - earlier)
            else:
                sustained = np.zeros_like(lum)

        return {
            "on_channel": on_channel,
            "off_channel": off_channel,
            "sustained": sustained,
        }

    def reset_temporal_state(self):
        """Reset all luminance history for ON/OFF and sustained channels.

        Call this when switching to a new visual environment.
        """
        self._prev_lum.clear()

    # ---- Edge orientation detection ----

    def _per_cell_luminance(self, atlas: np.ndarray) -> np.ndarray:
        """Convenience: per-cell luminance from an atlas frame."""
        rgb = atlas.reshape(-1, 3)[self.indices].astype(np.float32)
        rgb = np.sum(rgb * self.weights[None, :, None], axis=1) / 255.0  # (N, 3)
        return rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)  # (N,)

    def edge_orientation(self, atlas: np.ndarray) -> dict:
        """Detect oriented edge energy from the six-face RGB atlas.

        Uses the 48×64 spatial arrangement of visual_pixels to compute
        luminance differences between adjacent ommatidia at four orientations.
        Edge energies are normalised to [0, 1].

        Returns
        -------
        dict with keys:
            edge_0   : float — horizontal edge energy  (left-right luminance diff)
            edge_45  : float — diagonal edge energy     (45°)
            edge_90  : float — vertical edge energy     (up-down luminance diff)
            edge_135 : float — anti-diagonal edge energy (135°)
        """
        lum = self._per_cell_luminance(atlas)  # (N,)
        result = {}
        for name in self._edge_names:
            pairs = self._edge_pairs[name]
            if len(pairs) == 0:
                result[name] = 0.0
            else:
                diff = np.abs(lum[pairs[:, 0]] - lum[pairs[:, 1]])
                # Normalise: luminance difference in [0, 1] range → clip to stay valid
                val = float(np.clip(np.mean(diff).item(), 0, 1))
                result[name] = val
        return result

    def sample(self, atlas):
        if atlas.shape != (256, 384, 3):
            raise ValueError("retina requires a 384x256 six-face first-person RGB atlas")
        values = atlas.reshape(-1, 3)[self.indices].astype(np.float32)
        return np.sum(values * self.weights[None, :, None], axis=1) / 255

    def preview(self, atlas):
        values = atlas.reshape(-1, 3)[self.preview_indices].astype(np.float32)
        image = np.sum(values * self.weights[None, :, None], axis=1).reshape(
            PREVIEW_HEIGHT, PREVIEW_WIDTH, 3)
        image[~self.mask] = 0
        return image.astype(np.uint8)

    def compute_flow(self, atlas):
        """Compute optic flow signals from the six-face first-person RGB atlas.

        Returns a dict with per-sector temporal-energy estimates, three
        higher-level collision-relevant signals, and per-frame ON/OFF/sustained
        raw-channel means.

        Flow signals:
          * left_right_asymmetry - positive when more motion on the left
          * center_expansion   - positive when central field energy exceeds periphery
                                 (indicates an approaching object / looming)
          * lower_field_green  - mean green intensity in the lower third of the field
                                (drops at a cliff edge)
        Added channel-mean keys:
          * on_raw, off_raw, sustained_raw (Python float, mean across visual cells)
        """
        # Sample current frame
        rgb = atlas.reshape(-1, 3)[self.indices].astype(np.float32)
        rgb = np.sum(rgb * self.weights[None, :, None], axis=1) / 255.0  # (1536, 3)

        # ---- Compute ON/OFF/sustained (drives _prev_lum for temporal tracking) ----
        on_off = self.encode_on_off(atlas)
        on_raw = float(np.mean(on_off["on_channel"]).item())
        off_raw = float(np.mean(on_off["off_channel"]).item())
        sustained_raw = float(np.mean(on_off["sustained"]).item())

        # Per-cell brightness as a proxy for local energy
        brightness = rgb.mean(axis=1)  # (1536,)

        # ---- Per-sector energy (16 sectors) ----
        sectors_16 = {}
        for name in self._sector_names:
            mask = self._sector_masks[name]
            sectors_16[name] = float(brightness[mask].mean()) if mask.any() else 0.0

        # ---- Legacy 8-sector energy (backward compat) ----
        sectors = {}
        for name in self._old_sector_names:
            mask = self._old_sector_masks[name]
            sectors[name] = float(brightness[mask].mean()) if mask.any() else 0.0

        # ---- Flow signals ----
        left_energy = float(brightness[self._left_half].mean()) if self._left_half.any() else 0.0
        right_energy = float(brightness[self._right_half].mean()) if self._right_half.any() else 0.0
        total = left_energy + right_energy + _EPS

        left_right_asymmetry = float((left_energy - right_energy) / total)

        center_energy = float(brightness[self._center_60].mean()) if self._center_60.any() else 0.0
        periphery_energy = float(brightness[self._periphery_60].mean()) if self._periphery_60.any() else 0.0
        ce_total = center_energy + periphery_energy + _EPS
        center_expansion = float((center_energy - periphery_energy) / ce_total)

        lower_green = float(rgb[self._lower_third, 1].mean()) if self._lower_third.any() else 0.0

        # ---- Edge orientation means ----
        edges = self.edge_orientation(atlas)

        # Compute per-cell luminance once for downstream consumers
        _per_cell_lum = self._per_cell_luminance(atlas)

        # ---- Ground angle detection (cliff vs slope discrimination) ----
        # Analyze horizontal green gradient across elevation bands in lower field
        ground_angle = self._compute_ground_angle(rgb)

        # ---- Door frame detection from vertical edge pair spatial analysis ----
        door_frame_score, opening_width = self._compute_door_frame(_per_cell_lum)

        # ---- Tau (time-to-contact) estimation from radial divergence ----
        # During approach, the optic flow field expands radially outward:
        # peripheral cells brighten (ON) while central cells darken (OFF).
        # The radial gradient of (ON - OFF) is proportional to divergence.
        # Time-to-contact τ = 1 / max(divergence, ε) [seconds].
        on_m = on_off["on_channel"]
        off_m = on_off["off_channel"]
        motion = on_m - off_m                              # (N,) net luminance transient

        r = np.sqrt(self.azimuth_deg**2 + self.elevation_deg**2)  # eccentricity [deg]
        r_max = r.max()
        if r_max > _EPS:
            n_bins = 10
            edges_r = np.linspace(0, r_max, n_bins + 1)
            centres = (edges_r[:-1] + edges_r[1:]) / 2
            # Mean net motion in each radial band
            bin_means = np.zeros(n_bins)
            for i in range(n_bins):
                m = (r >= edges_r[i]) & (r < edges_r[i + 1])
                bin_means[i] = motion[m].mean() if m.any() else 0.0
            # Radial gradient via linear fit
            slope = np.polyfit(centres, bin_means, 1)[0] if np.ptp(centres) > _EPS else 0.0
        else:
            slope = 0.0

        # Scale luminance-gradient slope to divergence (s⁻¹).
        # Calibration: slope 0.01/deg → ~0.2 s⁻¹ at model timestep 0.020 s.
        div_scale = 20.0
        divergence = max(slope * div_scale, 0.0)          # expansion-only
        tau = 1.0 / max(divergence, _EPS) if divergence > _EPS else float("inf")

        # ---- Terrain classification from 16-sector flow pattern ----
        terrain = self.classify_terrain(sectors_16, edges, lower_green,
                                        left_right_asymmetry, center_expansion)

        # ---- Sector-derived terrain scores (task contract) ----
        # wall_score: lower sectors bright, upper sectors dark (vertical surface ahead)
        _lower_vals = np.array([sectors_16.get(f"az{i}_lower", 0.0) for i in range(8)])
        _upper_vals = np.array([sectors_16.get(f"az{i}_upper", 0.0) for i in range(8)])
        _lower_mean = float(_lower_vals.mean())
        _upper_mean = float(_upper_vals.mean())
        wall_score = max(0.0, min(1.0, (_lower_mean - _upper_mean + 0.2) * 2.5))
        # ramp_score: both upper and lower elevated, moderate looming
        _both = min(_lower_mean, _upper_mean)
        ramp_score = max(0.0, min(1.0, (_both - 0.1) * 2.5 * (1.0 - min(center_expansion, 0.5) * 1.5)))
        # opening_score: center (az3,az4) dimmer than periphery (az0,az1,az6,az7)
        _center_vals = np.array([sectors_16.get(f"az{i}_upper", 0.0) + sectors_16.get(f"az{i}_lower", 0.0)
                                 for i in (3, 4)])
        _peri_vals = np.array([sectors_16.get(f"az{i}_upper", 0.0) + sectors_16.get(f"az{i}_lower", 0.0)
                               for i in (0, 1, 6, 7)])
        _c_mean = _center_vals.mean() if _center_vals.size > 0 else 0.0
        _p_mean = _peri_vals.mean() if _peri_vals.size > 0 else 0.0
        opening_score = max(0.0, min(1.0, (_p_mean - _c_mean) * 3.0))
        # sky_score: upper sectors bright, low temporal energy (on_raw small)
        sky_score = max(0.0, min(1.0, (_upper_mean - 0.1) * 2.0 * (1.0 - min(on_raw, 0.2) * 5.0)))

        return {"tau": tau,
            "sectors": sectors,
            "sectors_16": sectors_16,
            "left_right_asymmetry": left_right_asymmetry,
            "center_expansion": center_expansion,
            "lower_field_green": lower_green,
            "terrain": terrain,
            # Sector-derived terrain scores (task contract)
            "wall_score": round(wall_score, 4),
            "ramp_score": round(ramp_score, 4),
            "opening_score": round(opening_score, 4),
            "sky_score": round(sky_score, 4),
            # Ground angle discrimination (cliff vs slope)
            "ground_angle": round(ground_angle, 4),
            # Door frame detection from vertical edge pairs
            "door_frame_score": round(door_frame_score, 4),
            "opening_width": round(opening_width, 4),
            # New multi-channel raw means
            "on_raw": on_raw,
            "off_raw": off_raw,
            "sustained_raw": sustained_raw,
            # Edge orientation means
            "edge_0": edges["edge_0"],
            "edge_45": edges["edge_45"],
            "edge_90": edges["edge_90"],
            "edge_135": edges["edge_135"],
        }

    def _compute_ground_angle(self, rgb: np.ndarray) -> float:
        """Compute ground disappearance angle from horizontal green gradient.

        Groups lower-visual-field cells by elevation band and measures how
        green intensity changes horizontally across azimuth.  A gradual
        drop → slope (ground_angle ~0.3-0.7); an abrupt drop → cliff
        (ground_angle < 0.3); sustained high green → flat (ground_angle > 0.7).

        Returns float in [0, 1].
        """
        lower = self._lower_third
        n_lower = int(lower.sum())
        if n_lower < 10:
            return 0.7  # insufficient data → assume flat

        green = rgb[:, 1]  # green channel
        green_lower = green[lower]
        el_lower = self.elevation_deg[lower]

        # Bin by elevation (5 bins of ~14.4° each, covering -72° to -24°)
        n_bins = 5
        el_min, el_max = -72.0, -24.0
        edges_el = np.linspace(el_min, el_max, n_bins + 1)
        centres_el = (edges_el[:-1] + edges_el[1:]) * 0.5

        bin_means = np.zeros(n_bins)
        for i in range(n_bins):
            m = (el_lower >= edges_el[i]) & (el_lower < edges_el[i + 1])
            bin_means[i] = float(green_lower[m].mean()) if m.any() else 0.0

        # Slope of green vs. elevation (most negative = cliff drop)
        if np.ptp(centres_el) > _EPS and np.std(bin_means) > 0.01:
            slope = np.polyfit(centres_el, bin_means, 1)[0]
        else:
            slope = 0.0

        # Abruptness: negative slope magnitude normalized
        # slope units: green_per_degree.  -0.02/deg → abrupt cliff
        abruptness = max(0.0, min(1.0, abs(slope) * 50.0))

        # ground_angle = 1 - abruptness, but modulated by overall green
        base = max(0.0, min(1.0, 1.0 - abruptness))
        overall_green = float(green_lower.mean())
        return max(0.0, min(1.0, base * 0.7 + min(overall_green * 1.5, 1.0) * 0.3))

    def _compute_door_frame(self, lum: np.ndarray) -> tuple[float, float]:
        """Detect door frames from spatial distribution of vertical-edge pairs.

        Uses precomputed per-cell luminance (from _per_cell_luminance).
        Analyzes per-row vertical-edge (edge_0: horizontal luminance difference)
        patterns across the visual grid.  A doorway appears as two strong
        vertical-edges with a low-edge gap between them at a width matching
        typical openings.

        Returns
        -------
        door_frame_score : float [0, 1]
            0 = no door frame detected, 1 = clear doorway ahead
        opening_width : float [0, 1]
            Normalized width of the detected opening (0 = narrow, 1 = wide)
        """
        pairs = self._edge_pairs["edge_0"]
        n_pairs = len(pairs)
        if n_pairs == 0:
            return 0.0, 0.0

        diffs = np.abs(lum[pairs[:, 0]] - lum[pairs[:, 1]])

        # Build per-cell edge_0 magnitude using numpy scatter
        n_cells = len(lum)
        cell_edge = np.zeros(n_cells, dtype=np.float32)
        # For each pair, assign mean diff to both ends (vectorized)
        pair_max = np.maximum(
            np.zeros(n_pairs, dtype=np.float32),
            np.maximum(diffs, cell_edge[pairs[:, 0]])
        )
        # Scatter via loop-free approach: use np.maximum.at for unbounded update
        np.maximum.at(cell_edge, pairs[:, 0], diffs)
        np.maximum.at(cell_edge, pairs[:, 1], diffs)

        vp = self._vp_rc
        rows_set = sorted(set(int(r) for r in vp[:, 0]))
        total_score = 0.0
        total_width = 0.0
        row_count = 0
        strong_thr = 0.04
        gap_thr = 0.015

        for row in rows_set:
            row_mask = vp[:, 0] == row
            idx = np.where(row_mask)[0]
            if len(idx) < 11:
                continue
            order = np.argsort(vp[idx, 1])
            idx = idx[order]
            edges_row = cell_edge[idx]
            n = len(edges_row)

            # Categorize cells into state runs using diff transitions
            state = np.zeros(n, dtype=np.int8)
            state[edges_row > strong_thr] = 1  # strong
            state[edges_row < gap_thr] = -1    # gap

            # Find runs: where state changes
            trans = np.diff(state, prepend=0)
            starts = np.where(trans != 0)[0]
            ends = np.concatenate((starts[1:], [n]))
            run_len = ends - starts
            run_state = state[starts]

            # Pattern: strong(≥2) → gap(≥3) → strong(≥2)
            for i in range(len(run_state) - 2):
                if (run_state[i] == 1 and run_len[i] >= 2 and
                    run_state[i + 1] == -1 and run_len[i + 1] >= 3 and
                    run_state[i + 2] == 1 and run_len[i + 2] >= 2):
                    left_s = starts[i]
                    left_e = ends[i]
                    gap_s = starts[i + 1]
                    gap_e = ends[i + 1]
                    right_s = starts[i + 2]
                    right_e = ends[i + 2]

                    left_strength = float(np.mean(edges_row[left_s:left_e]))
                    right_strength = float(np.mean(edges_row[right_s:right_e]))
                    avg_strength = (left_strength + right_strength) * 0.5
                    gap_ratio = (gap_e - gap_s) / n
                    seg_balance = (min(left_e - left_s, right_e - right_s) /
                                   max(left_e - left_s, right_e - right_s, 1))

                    if avg_strength > 0.03 and gap_ratio > 0.1:
                        row_score = avg_strength * min(1.0, gap_ratio * 3.0) * seg_balance
                        total_score += row_score
                        total_width += gap_ratio
                        row_count += 1

        if row_count == 0:
            return 0.0, 0.0

        door_frame_score = max(0.0, min(1.0, total_score / row_count))
        opening_width = max(0.0, min(1.0, total_width / row_count))
        return door_frame_score, opening_width

    @staticmethod
    def classify_terrain(sectors_16: dict, edges: dict,
                         lower_green: float, asymmetry: float,
                         looming: float) -> str:
        """Classify terrain type from 16-sector flow pattern.

        Rules (applied in priority order):
          "cliff"       — lower_green < 0.3 and lower azimuth sectors
                          significantly dimmer than upper ones
          "water"       — low overall brightness (< 0.15) and near-zero
                          edge energy
          "corridor"    — strong vertical edges (edge_90 > 0.15) but
                          low horizontal edges (edge_0 < 0.08)
          "wall_ahead"  — strong center expansion (looming > 0.3) with
                          high forward-sector energy
          "open_flat"   — uniform sector energy (std < 0.04) and
                          low edge energy overall
          "dense"       — high complexity: all edge orientations > 0.1
                          and high sector variance
          "forest_edge" — strong diagonal edges (edge_45+edge_135 > 0.3)
                          and moderate asymmetry
          "mixed"       — default when no clear pattern
        """
        vals_16 = list(sectors_16.values())
        mean_16 = float(np.mean(vals_16)) if vals_16 else 0.0
        std_16 = float(np.std(vals_16)) if vals_16 else 0.0

        # Cliff: lower-field green collapse AND lower sectors dimmer than upper
        lower_sectors = [v for k, v in sectors_16.items() if "lower" in k]
        upper_sectors = [v for k, v in sectors_16.items() if "upper" in k]
        lower_mean = float(np.mean(lower_sectors)) if lower_sectors else 0.0
        upper_mean = float(np.mean(upper_sectors)) if upper_sectors else 0.0

        if lower_green < 0.3 and lower_mean < upper_mean * 0.6 and upper_mean > 0.05:
            return "cliff"

        # Water: very low brightness and negligible edges
        edge_total = sum(edges.get(k, 0.0) for k in ("edge_0", "edge_45", "edge_90", "edge_135"))
        if mean_16 < 0.15 and edge_total < 0.05:
            return "water"

        # Wall ahead: strong looming with high forward-sector energy
        if looming > 0.3 and mean_16 > 0.15:
            return "wall_ahead"

        # Corridor: strong vertical edges, weak horizontal
        vertical = edges.get("edge_90", 0.0)
        horizontal = edges.get("edge_0", 0.0)
        if vertical > 0.15 and horizontal < 0.08:
            return "corridor"

        # Dense / forest: all edge orientations active
        diag_45 = edges.get("edge_45", 0.0)
        diag_135 = edges.get("edge_135", 0.0)
        if all(edges.get(k, 0.0) > 0.1 for k in ("edge_0", "edge_45", "edge_90", "edge_135")) and std_16 > 0.05:
            return "dense"

        # Forest edge: strong diagonal edges with asymmetry
        if diag_45 + diag_135 > 0.3 and abs(asymmetry) > 0.15:
            return "forest_edge"

        # Open flat: low variance and low edges
        if std_16 < 0.04 and edge_total < 0.15:
            return "open_flat"

        return "mixed"