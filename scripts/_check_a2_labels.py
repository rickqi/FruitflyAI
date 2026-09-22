#!/usr/bin/env python3
"""Check A2 residual version-label consistency."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = r"docs\analysis\analysis-a2-rootcauses.md"
L = open(P, encoding="utf-8").readlines()
print("total lines:", len(L))
print()
print("--- line 3 (header) ---")
print(L[2].rstrip()[:220])
print()
print("--- lines mentioning rev label ---")
for i, l in enumerate(L):
    s = l.strip()
    if ("rev 2" in s or "rev 3" in s or "rev 1" in s) and (
            "任务：" in s or "附录" in s or "产出" in s or "修订记录" in s):
        print("%3d| %s" % (i + 1, s[:170]))
print()
print('--- exact stale label check: rev 2 vs rev 3 in header/appendix ---')
for i in (2,):
    print("L%d: %s" % (i + 1, L[i].strip()[:200]))
