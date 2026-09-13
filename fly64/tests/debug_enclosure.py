import sys
sys.path.insert(0, r"D:\codes\flygym\fly64")
import numpy as np
from fly64.retina import SphericalRetina

def _scene_atlas(indoor):
    atlas = np.zeros((256, 384, 3), np.uint8)
    if indoor:
        top = (80, 80, 90); bottom = (200, 40, 40)
    else:
        top = (200, 120, 40); bottom = (60, 180, 60)
    for fr in range(2):
        for fc in range(3):
            tile = atlas[fr*128:(fr+1)*128, fc*128:(fc+1)*128]
            tile[:64] = top; tile[64:] = bottom
            if indoor:
                for x in range(0, 128, 16):
                    tile[:64, x:x+4] = (200, 200, 210)
                    tile[64:, x:x+2] = (40, 40, 50)
    return atlas

r = SphericalRetina(np.array([(r, c) for r in range(0, 48, 2) for c in range(0, 64, 2)], float))
ri = r.compute_flow(_scene_atlas(True))
r.reset_temporal_state()
ro = r.compute_flow(_scene_atlas(False))
print("indoor: enclosure", ri["enclosure_score"], "upper_blue", ri["upper_blue"], "terrain", ri["terrain"], "sky", ri["sky_score"], "edge90", ri["edge_90"], "edge0", ri["edge_0"])
print("outdoor: enclosure", ro["enclosure_score"], "upper_blue", ro["upper_blue"], "terrain", ro["terrain"], "sky", ro["sky_score"], "edge90", ro["edge_90"], "edge0", ro["edge_0"])
