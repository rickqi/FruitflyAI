import json, re
from datetime import datetime, timezone, timedelta

path = "skills/evolution_history.json"
d = json.load(open(path))
recs = d["records"] if isinstance(d, dict) else d
if any("coach screen fidelity" in str(r.get("trigger", "")) for r in recs):
    print("already present; skipping")
    raise SystemExit(0)
mx = max((int(m.group(1)) for r in recs
          for m in [re.match(r"EVO-(\d+)$", str(r.get("id", "")))] if m), default=0)
now = datetime.now(timezone(timedelta(hours=8)))
recs.append({
    "id": f"EVO-{mx+1:03d}",
    "date": now.strftime("%Y-%m-%d"),
    "time": now.strftime("%H:%M %z"),
    "round": "R31-fix2",
    "kind": "brain",          # game-binary fix (sm64ex side)
    "brain_version": None,    # game binary; brain code untouched this fix
    "skill_version": "3.1.1",
    "trigger": "教练截屏与实际游戏画面长期不一致：snapshot 只是游戏屏幕一部分——R21 截图点落在复眼观察者通道尾部（时机=帧中段、视口=观察者残留、FBO 绑定错误），且原审计只验证感官隔离不验证内容保真（测试盲区）",
    "changes": [
        "fly64_vision.c: 移除观察者通道尾部的错误捕获块；新增 fly64_vision_capture_screen()（FB0 显式绑定 + 整幅读取 + Y 翻转 + GL 错误清零回退）",
        "fly64_vision.h: 声明 fly64_vision_capture_screen",
        "gfx_pc.c: gfx_run() 在 gfx_rapi->end_frame() 之后、swap 之前调用捕获（游戏帧完整绘制的正确时机）",
        "调试发现并规避：帧中段 glGetIntegerv(GL_FRAMEBUFFER_BINDING) 在本驱动触发段错误——capture 不做任何 glGet* 状态查询",
        "scripts/m4_screen_fidelity_check.py: 保真度回归（4 检查：完整帧/非零占比/与 cubemap 正面区分/活流非冻结）；tests/test_screen_fidelity.py 入库（FLY64_LIVE=1 门控）",
        "patches/sm64ex-fly64.patch 重建（含本修复），新鲜 checkout 验证可应用",
    ],
    "tests": "保真度 3/3 PASS（零占比 1.8%→27.9% 自然天空、活流 delta 0.51、与 cubemap 直方图区分）；游戏存活 120s+（旧代码 40s 段错误）；全量套件失败集与基线一致",
    "deployed": True,
    "source": "用户报告 coach 截屏不一致 → captain 根因定位（渲染管线钩子时机/视口/FBO 三重错位）→ 数据驱动修复",
})
d["canonical_versions"]["as_of"] = now.isoformat()
json.dump(d, open(path, "w"), ensure_ascii=False, indent=1)
print(f"EVO-{mx+1:03d} appended (R31-fix2 screen fidelity); total {len(recs)}")
