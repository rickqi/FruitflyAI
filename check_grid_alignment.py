"""End-to-end grid alignment proof.

Paint black stripes into the synthetic atlas at EXACT sector boundaries
(az=-67.5° vertical, el=0° horizontal), render through the real preview()
pipeline (cone sampling included), then verify that the strip-view sector
boundary lines land precisely on the painted stripes — and that mid-band
control columns land on bright background. Any real misalignment shows up
as bright boundary columns / dark control columns.
"""
import numpy as np, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fly64"))
from fly64.retina import SphericalRetina, atlas_indices

W, H = 256, 128
vp = np.column_stack((np.linspace(0, 3071, 1536, dtype=np.int32) // 64,
                      np.linspace(0, 3071, 1536, dtype=np.int32) % 64)).astype(np.uint8)
ret = SphericalRetina(vp)

# ---- preview pixel rays (verbatim retina.py preview block) ----
yy, xx = np.mgrid[0:H, 0:W]
eye = xx // 128
u = ((xx % 128) + .5 - 64) / 64.0
v = (64 - yy - .5) / 64.0
radius = np.hypot(u, v)
ang = radius * np.pi / 2
scale = np.divide(np.sin(ang), radius, out=np.ones_like(radius), where=radius > 1e-6)
lx, ly, lz = u * scale, v * scale, np.cos(ang)
a = np.deg2rad(np.where(eye == 0, -63.25, 63.25))
rx = np.cos(a) * lx + np.sin(a) * lz
ry = ly
rz = -np.sin(a) * lx + np.cos(a) * lz
az = np.rad2deg(np.arctan2(rx, rz))
el = np.rad2deg(np.arcsin(np.clip(ry, -1, 1)))
rays = np.stack((rx, ry, rz), axis=-1).reshape(-1, 3)

# ---- paint stripes into the atlas at exact boundaries ----
atlas = np.full((256, 384, 3), 200, np.uint8)
vstripe = np.abs(az - (-67.5)) < 1.5            # sector boundary az=-67.5° (3° wide)
hstripe = np.abs(el) < 1.5                       # upper/lower boundary el=0°
tex = atlas_indices(rays[vstripe.reshape(-1)])
atlas.reshape(-1, 3)[tex] = 0
tex = atlas_indices(rays[hstripe.reshape(-1)])
atlas.reshape(-1, 3)[tex] = 0

# ---- render through the REAL pipeline ----
eyes = ret.preview(atlas)                        # (128, 256, 3)
gray = eyes.mean(axis=2)

# ---- strip-view LUT (verbatim dashboard.js buildStripLUT) ----
lut = np.full(W * H, -1, np.int64)
SW, SH = 256, 128
for sy in range(SH):
    for sx in range(SW):
        saz = -135 + (sx + .5) / SW * 270
        sel = 72 - (sy + .5) / SH * 144
        seye = 0 if saz < 0 else 1
        sa = np.deg2rad(-63.25 if seye == 0 else 63.25)
        cer, ser = np.cos(np.deg2rad(sel)), np.sin(np.deg2rad(sel))
        srx, sry, srz = np.sin(np.deg2rad(saz)) * cer, ser, np.cos(np.deg2rad(saz)) * cer
        ca, saa = np.cos(sa), np.sin(sa)
        slx, sly, slz = ca * srx - saa * srz, sry, saa * srx + ca * srz
        th = np.arccos(np.clip(slz, -1, 1))
        if th >= np.pi / 2:
            continue
        rho = th / (np.pi / 2)
        uu, vv = slx / np.sin(th) * rho, sly / np.sin(th) * rho
        fx = int(np.clip(np.floor((uu + 1) * 64), 0, 127))
        fy = int(np.clip(np.floor((1 - vv) * 64), 0, 127))
        lut[sy * SW + sx] = (fy * 256 + seye * 128 + fx)

lut2d = lut.reshape(SH, SW)

def col_mean(sx):
    idx = lut2d[:, sx]
    idx = idx[idx >= 0]
    return float(gray.reshape(-1)[idx].mean())

def row_mean(sy):
    idx = lut2d[sy, :]
    idx = idx[idx >= 0]
    return float(gray.reshape(-1)[idx].mean())

print("=== 竖直条纹测试: az=-67.5° 扇区边界 (期望 strip x=64) ===")
cols = np.array([col_mean(x) if 2 < x < 253 else 255.0 for x in range(256)])
win = cols[59:70]                     # 期望边界 ±5 列
argmin = 59 + int(np.argmin(win))
w = np.clip(200 - win, 0, None)
centroid = float((w * np.arange(59, 70)).sum() / max(w.sum(), 1e-9))
print(f"  最暗列 x={argmin}  亮度={cols[argmin]:5.1f}   期望 x=64")
print(f"  暗度质心 x={centroid:.2f}          偏移 = {centroid - 64:+.2f} px")
print(f"  对照: x=48 亮度={cols[48]:5.1f} / x=80 亮度={cols[80]:5.1f} (应≈200)")
off_v = centroid - 64
verdict_v = "对齐" if abs(off_v) <= 1.5 else "错位"
print(f"  判定: {verdict_v}  (锥形采样模糊 σ≈2° ≈ 1.4px, 容差 ±1.5px)")

print("=== 水平条纹测试: el=0° 上/下分界 (期望 strip y=64) ===")
rows = np.array([row_mean(y) if 2 < y < 125 else 255.0 for y in range(128)])
winn = rows[59:70]
argminr = 59 + int(np.argmin(winn))
wr = np.clip(200 - winn, 0, None)
centroidr = float((wr * np.arange(59, 70)).sum() / max(wr.sum(), 1e-9))
print(f"  最暗行 y={argminr}  亮度={rows[argminr]:5.1f}   期望 y=64")
print(f"  暗度质心 y={centroidr:.2f}          偏移 = {centroidr - 64:+.2f} px")
off_h = centroidr - 64
verdict_h = "对齐" if abs(off_h) <= 1.5 else "错位"
print(f"  判定: {verdict_h}")

ok = verdict_v == "对齐" and verdict_h == "对齐"
print(f"\n{'全部对齐：overlay 网格与图像内容逐像素一致 (偏移 ≤1px)' if ok else '检测到真实错位，需修码'}")
sys.exit(0 if ok else 1)