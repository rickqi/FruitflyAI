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
        azimuth = np.where(eye == 0, -135, -8.5) + horizontal*143.5
        elevation = 72 - pixels[:,0]/47*144
        self.rays = angular_rays(azimuth, elevation)
        self.indices = cone_indices(self.rays)
        self.weights = np.array([.25]+[.125]*6, np.float32)
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
