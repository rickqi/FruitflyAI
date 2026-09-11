"""Spherical compound-eye sampling, independent of the observer framebuffer.

The measured optic-column order is retained. Its registration to angular
coordinates is engineered, NOT a measured MaleCNS optical calibration.
Azimuth bounds approximate NeuroMechFly's 270-degree binocular field.
RGB is not UV; acceptance width and vertical coverage are model parameters.
"""
import numpy as np

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
    def __init__(self, visual_pixels):
        pixels = np.asarray(visual_pixels, float)
        eye = (pixels[:,1] >= 32).astype(int)
        horizontal = (pixels[:,1] % 32)/31
        # Existing column atlas goes left-to-right within each eye.
        self.azimuth_deg = np.where(eye == 0, -135, -8.5) + horizontal*143.5
        self.elevation_deg = 72 - pixels[:,0]/47*144
        self.rays = angular_rays(self.azimuth_deg, self.elevation_deg)
        self.indices = cone_indices(self.rays)
        self.weights = np.array([.25]+[.125]*6, np.float32)

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

    def sample(self, atlas):
        if atlas.shape != (256,384,3):
            raise ValueError("retina requires a 384x256 six-face first-person RGB atlas")
        values = atlas.reshape(-1,3)[self.indices].astype(np.float32)
        return np.sum(values*self.weights[None,:,None],axis=1)/255

    def preview(self, atlas):
        values = atlas.reshape(-1,3)[self.preview_indices].astype(np.float32)
        image = np.sum(values*self.weights[None,:,None],axis=1).reshape(PREVIEW_HEIGHT,PREVIEW_WIDTH,3)
        image[~self.mask] = 0
        return image.astype(np.uint8)

    def compute_flow(self, atlas):
        """Compute optic flow signals from the six-face first-person RGB atlas.

        Returns a dict with per-sector temporal-energy estimates and three
        higher-level collision-relevant signals:
          * left_right_asymmetry - positive when more motion on the left
          * center_expansion   - positive when central field energy exceeds periphery
                                 (indicates an approaching object / looming)
          * lower_field_green  - mean green intensity in the lower third of the field
                                 (drops at a cliff edge)
        """
        # Sample current frame
        rgb = atlas.reshape(-1,3)[self.indices].astype(np.float32)
        rgb = np.sum(rgb * self.weights[None, :, None], axis=1) / 255.0  # (1536, 3)

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

        return {
            "sectors": sectors,
            "left_right_asymmetry": left_right_asymmetry,
            "center_expansion": center_expansion,
            "lower_field_green": lower_green,
        }
