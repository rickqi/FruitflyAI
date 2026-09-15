import sys
sys.path.insert(0, r"D:\codes\flygym\fly64")
import numpy as np
from fly64.main import build_help_snapshot
frame = np.zeros((4, 6, 3), np.uint8); frame[0, 0] = 200
snap = build_help_snapshot("test", {"x": 1}, "diag", frame)
print("keys:", sorted(snap.keys()))
