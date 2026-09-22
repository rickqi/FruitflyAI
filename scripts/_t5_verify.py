"""t5 acceptance verification for the A2 rev2 -> rev3 label closeout."""
import io

P = r"docs/analysis/analysis-a2-rootcauses.md"
t = io.open(P, encoding="utf-8").read()
lines = t.splitlines()
ok = True

print("=== A1: grep 'rev 2（口径修订）' must be EMPTY ===")
hits = [i for i, l in enumerate(lines, 1) if "rev 2（口径修订）" in l]
print("  matches:", hits, "->", "PASS" if not hits else "FAIL")
ok &= not hits

print("\n=== A2: self-labels ===")
for pat in ["**rev 3（口径收口）**", "（本文件）· **rev 3**",
            "## 附录 C — 修订记录（rev 2 第一次复核 + rev 3 裁决收口",
            "口径说明（本文件 rev 1 → rev 3 修订记录）"]:
    c = t.count(pat)
    print("  %-56s count=%d %s" % (pat[:56], c, "OK" if c == 1 else "CHECK"))
    ok &= c == 1

print("\n=== A3: line count / analysis invariants ===")
print("  logical lines: %d (baseline 686; +2 = appendix block)" % len(lines))
inv = ["963 − 89 = 874", "## 1.3 六段链路缺陷总表", "# 5. 未修部分清单（可直接转成任务书）",
       "# 4. 三顽疾的共同结构（A2 的核心结论）", "## 1.1 症状", "## 3.1 症状",
       "# 顽疾 1 — Coach 建议不生效", "# 顽疾 2 — AgentTeams 任务未执行",
       "# 顽疾 3 — 动作单调 / 探索无效",
       "裁决 3（本表第 5 行的裁定依据）", "only in (1) = 4", "union unique = 62",
       "874 成立、870 废弃"]
for k in inv:
    c = t.count(k)
    print("  %-40s count=%d %s" % (k, c, "OK" if c >= 1 else "MISSING"))
    ok &= c >= 1
miss = [u for u in ["U%d" % i for i in range(1, 13)] if ("| %s |" % u) not in t]
print("  U1-U12 rows:", "all present" if not miss else "MISSING " + str(miss))
ok &= not miss

print("\n=== A4: any remaining bare 'rev 2' self-label ===")
allowed_ctx = ["rev 2 首稿", "rev 2 新增", "rev 2 主用", "rev 2 第一次复核",
               "rev 2 及之后", "rev 1", "口径更正（rev 2）", "rev 2）", "rev 2 的",
               "rev 2 曾提出", "rev 2 – rev 3 净增益"]
strays = []
for i, l in enumerate(lines, 1):
    if "rev 2" not in l:
        continue
    if any(a in l for a in allowed_ctx):
        continue
    strays.append((i, l[:110]))
for i, l in strays:
    print("  L%d: %s" % (i, l))
print("  (no output above = clean)")
ok &= not strays

print("\nRESULT:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
