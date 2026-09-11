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

        # ---- 8 azimuth-elevation sector masks (4 horizontal x 2 vertical) ----
        left = self.azimuth_deg < -67.5
        ctr_left = (~left) & (self.azimuth_deg < 0)
        ctr_right = (~left) & (~ctr_left) & (self.azimuth_deg < 67.5)
        right = self.azimuth_deg >= 67.5
        upper = self.elevation_deg >= 0
        lower = ~upper
        self._sector_names = (
            "left_upper","left_lower",
            "center-left_upper","center-left_lower",
            "center-right_upper","center-right_lower",
            "right_upper","right_lower",
        )
        self._sector_masks = {}
        for h_name, h_mask in (("left", left), ("center-left", ctr_left),
                               ("center-right", ctr_right), ("right", right)):
            self._sector_masks[h_name + "_upper"] = h_mask & upper
            self._sector_masks[h_name + "_lower"] = h_mask & lower

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

        # ---- Per-sector energy ----
        sectors = {}
        for name in self._sector_names:
            mask = self._sector_masks[name]
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

        return {
            "sectors": sectors,
            "left_right_asymmetry": left_right_asymmetry,
            "center_expansion": center_expansion,
            "lower_field_green": lower_green,
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