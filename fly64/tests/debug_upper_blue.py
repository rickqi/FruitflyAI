import sys
sys.path.insert(0, r"D:\codes\flygym\fly64")
import numpy as np
from fly64.retina import SphericalRetina
sys.path.insert(0, r"D:\codes\flygym\fly64\tests")
from test_retina import direction_atlas

r = SphericalRetina(np.array([(rr, c) for rr in range(0, 48, 2) for c in range(0, 64, 2)], float))
atlas = direction_atlas()
rgb = atlas.reshape(-1, 3)[r.indices].astype(np.float32)
rgb = np.sum(rgb * r.weights[None, :, None], axis=1) / 255.0
lum = rgb.mean(axis=1)
upper = r.elevation_deg >= 0
blue = np.clip(rgb[:, 2] - np.maximum(rgb[:, 0], rgb[:, 1]), 0, 1)
print("N cells:", len(lum), "upper cells:", upper.sum())
print("direction_atlas upper_blue:", round(float(blue[upper].mean()), 4))
print("direction_atlas upper_mean lum:", round(float(lum[upper].mean()), 4))
