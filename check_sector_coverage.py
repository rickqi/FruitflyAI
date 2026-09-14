"""Cross-check: Python sector-map vs dashboard.js buildSectorMap (must be identical)."""
import numpy as np, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fly64"))

# --- Replicate dashboard.js buildSectorMap in Python ---
W, H = 256, 128
yy, xx = np.mgrid[0:H, 0:W]
eye = (xx // 128).astype(int)
u = ((xx % 128) + .5 - 64) / 64.0
v = (64 - yy - .5) / 64.0
radius = np.hypot(u, v)
valid = (radius <= 1) & (radius >= 1e-6)
ang = radius * np.pi / 2
scale = np.divide(np.sin(ang), radius, out=np.ones_like(radius), where=radius > 1e-6)
lx, ly, lz = u * scale, v * scale, np.cos(ang)
a = np.deg2rad(np.where(eye == 0, -63.25, 63.25))
rx = np.cos(a) * lx + np.sin(a) * lz
ry = ly
rz = -np.sin(a) * lx + np.cos(a) * lz
az = np.rad2deg(np.arctan2(rx, rz))
el = np.rad2deg(np.arcsin(np.clip(ry, -1, 1)))
in_fov = valid & (np.abs(el) <= 72) & np.where(
    eye == 0, (az >= -135) & (az <= 8.5), (az >= -8.5) & (az <= 135))
band = np.clip(((az + 135) / 33.75).astype(int), 0, 7)
py_map = np.where(in_fov, band * 2 + (el < 0).astype(int) + 1, 0).astype(np.int32)

py_cov = int((py_map > 0).sum())
py_left = int((py_map[:, :128] > 0).sum())
py_right = int((py_map[:, 128:] > 0).sum())
print(f"Python map: covered={py_cov}  L={py_left}  R={py_right}  frac={py_left/(np.pi*64*64):.3f}")

# --- Compare with retina.py's own preview mask (the image content mask) ---
from fly64.retina import SphericalRetina
fp = np.linspace(0, 3071, 1536, dtype=np.int32)
vp = np.column_stack((fp // 64, fp % 64)).astype(np.uint8)
ret = SphericalRetina(vp)
mask = ret.mask
print(f"retina.preview mask: covered={int(mask.sum())} (image-visible pixels)")
print(f"JS-identical map vs preview mask: identical={bool(np.array_equal((py_map > 0), mask))}")

# --- Sector coverage over the RETINA CELLS (signal space) ---
azc, elc = ret.azimuth_deg, ret.elevation_deg
in_fov_cells = np.abs(elc) <= 72
bands = np.clip(((azc + 135) / 33.75).astype(int), 0, 7)
cell_sector = bands * 2 + (elc < 0).astype(int) + 1
present = sorted(set(cell_sector[in_fov_cells].tolist()))
print(f"Retina cells in FOV: {int(in_fov_cells.sum())}/1536, sectors present: {len(present)}/16")
missing = set(range(1, 17)) - set(present)
print(f"Sectors with zero retina cells: {sorted(missing) if missing else 'NONE — full signal coverage'}")

# Angular extent check: what the sectors cover vs what the eye geometry shows
print(f"\nFOV covered by sectors: az -135..+135 (270 deg), el -72..+72 (144 deg)")
print(f"Fisheye circle geometric extent per eye: az center+-90, el -90..+90 (clipped by mask)")
print(f"=> display black regions = outside fly FOV (by design), NOT missing sectors")
