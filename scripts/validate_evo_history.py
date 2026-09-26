#!/usr/bin/env python3
"""
validate_evo_history.py — evolution_history.json 防覆盖守卫（B17）。

防止 EVO-* / AUTO-* id 在提交中被无意删除（拦截 fbcc3d7 类事故）。
比较 HEAD~1（基线）与工作区/暂存区的 id 集合——工作区必须为基线的超集（可新增不可删除）。

模式：
  --pre-commit    预提交检查（默认 baseline=HEAD~1，比较工作区文件）
  --current-ok    验证当前工作区相对 HEAD~1 无删除（CI 门禁）
  --self-test     自检模式：模拟删除 → 检查 FAIL → 恢复 → 检查 PASS
  --git-ref REF   指定基线 git 引用（默认 HEAD~1）
  --strict        同时检查 AUTO-* 不可删除（默认已启用）

用法：
  python scripts/validate_evo_history.py --pre-commit
  python scripts/validate_evo_history.py --current-ok
  python scripts/validate_evo_history.py --self-test
  python scripts/validate_evo_history.py --git-ref HEAD --pre-commit
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVO_HISTORY = PROJECT_ROOT / "fly64" / "skills" / "evolution_history.json"
EVO_HISTORY_REPO_PATH = "fly64/skills/evolution_history.json"


# ─── helpers ────────────────────────────────────────────────────────────────


def die(message: str, exit_code: int = 1) -> None:
    print(f"\n[FAIL] VALIDATE EVO HISTORY: {message}", file=sys.stderr)
    sys.exit(exit_code)


def get_ids(records: list[dict]) -> dict[str, set[str]]:
    """从 records 提取 EVO-* 和 AUTO-* id 集合。"""
    evo = {r["id"] for r in records if r.get("id", "").startswith("EVO-")}
    auto = {r["id"] for r in records if r.get("id", "").startswith("AUTO-")}
    return {"evo": evo, "auto": auto}


def load_history(path: Path) -> list[dict]:
    """加载 evolution_history.json 并返回 records。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("records", [])


def load_git_history(git_ref: str) -> list[dict]:
    """从 git 历史加载指定版本的 evolution_history.json。"""
    cmd = [
        "git", "-C", str(PROJECT_ROOT), "show",
        f"{git_ref}:{EVO_HISTORY_REPO_PATH}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        data = json.loads(result.stdout.decode("utf-8"))
        return data.get("records", [])
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode("utf-8", errors="replace").strip() if e.stderr else str(e)
        die(f"无法从 git ref '{git_ref}' 读取: {msg}")
    except json.JSONDecodeError as e:
        die(f"git ref '{git_ref}' 的 evolution_history.json 不是合法 JSON: {e}")
    except FileNotFoundError:
        die("git 命令不可用，请确保已安装 git。")


def load_staged_version() -> list[dict] | None:
    """从 git 暂存区加载 evolution_history.json（若已 staged）。"""
    cmd = [
        "git", "-C", str(PROJECT_ROOT), "show", f":{EVO_HISTORY_REPO_PATH}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        data = json.loads(result.stdout.decode("utf-8"))
        return data.get("records", [])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def get_baseline_ref(args) -> str:
    """确定基线 git 引用。"""
    if args.git_ref:
        return args.git_ref
    # 默认 HEAD~1，若 HEAD 无父（初始提交）则用 HEAD
    try:
        subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD~1"],
            capture_output=True, check=True, timeout=10,
        )
        return "HEAD~1"
    except subprocess.CalledProcessError:
        return "HEAD"


# ─── 检查函数 ──────────────────────────────────────────────────────────────


def check_no_deletions(
    current_ids: dict[str, set[str]],
    baseline_ids: dict[str, set[str]],
    label: str,
    strict: bool = True,
) -> str | None:
    """检查 id 是否有删除。strict 同时检查 EVO-* 和 AUTO-*。

    返回 None=通过；str=失败原因。
    """
    failures = []

    # 检查 EVO-*
    evo_deleted = baseline_ids["evo"] - current_ids["evo"]
    if evo_deleted:
        failures.append(
            f"检测到 {len(evo_deleted)} 个 EVO-* id 消失（vs {label}）：\n"
            f"  已删除: {sorted(evo_deleted)}"
        )

    # 检查 AUTO-*（默认严格，B17 要求双保护）
    if strict:
        auto_deleted = baseline_ids["auto"] - current_ids["auto"]
        if auto_deleted:
            failures.append(
                f"检测到 {len(auto_deleted)} 个 AUTO-* id 消失（vs {label}）：\n"
                f"  已删除: {sorted(auto_deleted)}"
            )

    if failures:
        return "\n".join(failures)

    # 打印新增信息（非失败）
    evo_added = current_ids["evo"] - baseline_ids["evo"]
    if evo_added:
        print(f"  新增 EVO-* id: {sorted(evo_added)}（仅追加，合规）")
    auto_added = current_ids["auto"] - baseline_ids["auto"]
    if auto_added:
        print(f"  新增 AUTO-* id: {sorted(auto_added)}（仅追加，合规）")

    return None


def print_summary(current_ids, baseline_ids):
    """打印对比摘要。"""
    evo_added = current_ids["evo"] - baseline_ids["evo"]
    evo_common = current_ids["evo"] & baseline_ids["evo"]
    evo_deleted = baseline_ids["evo"] - current_ids["evo"]
    auto_added = current_ids["auto"] - baseline_ids["auto"]
    auto_common = current_ids["auto"] & baseline_ids["auto"]
    auto_deleted = baseline_ids["auto"] - current_ids["auto"]

    print("=" * 60)
    print("  evolution_history.json id 变更摘要")
    print("=" * 60)
    print(f"  基线 EVO-*:    {len(baseline_ids['evo']):>3d}  →  当前: {len(current_ids['evo']):>3d}")
    print(f"    共同: {len(evo_common):>3d}, 新增: {len(evo_added):>3d}, 删除: {len(evo_deleted):>3d}")
    print(f"  基线 AUTO-*:   {len(baseline_ids['auto']):>3d}  →  当前: {len(current_ids['auto']):>3d}")
    print(f"    共同: {len(auto_common):>3d}, 新增: {len(auto_added):>3d}, 删除: {len(auto_deleted):>3d}")
    print("=" * 60)


# ─── 自检模式 ──────────────────────────────────────────────────────────────


def run_self_test() -> None:
    """自检：模拟删除 EVO-* id → 必 FAIL → 恢复 → 必 PASS。"""
    print("=" * 60)
    print("  B17 自检模式：验证守卫『能探测』")
    print("=" * 60)

    if not EVO_HISTORY.exists():
        die(f"未找到 evolution_history.json: {EVO_HISTORY}")

    # 获取基线（HEAD~1）和当前文件
    baseline_ref = "HEAD~1"
    try:
        baseline_records = load_git_history(baseline_ref)
    except SystemExit:
        # HEAD~1 不存在时用 HEAD
        baseline_records = load_git_history("HEAD")
        baseline_ref = "HEAD"

    baseline_ids = get_ids(baseline_records)
    current_records = load_history(EVO_HISTORY)
    current_ids = get_ids(current_records)

    evo_ids = sorted(current_ids["evo"])
    if len(evo_ids) < 2:
        die("自检失败：当前 EVO-* id 不足 2 个，无法模拟删除")

    # 选一个非边界 EVO-* id 来删除（取中间的确保有代表性）
    victim = evo_ids[len(evo_ids) // 2]
    print(f"\n[1/4] 备份当前 evolution_history.json ...")
    backup = EVO_HISTORY.with_suffix(".json.bak_self_test")
    shutil.copy2(str(EVO_HISTORY), str(backup))

    try:
        # Step 1: 删除一个 EVO-* 记录
        print(f"[2/4] 模拟删除记录 {victim} ...")
        data = json.loads(EVO_HISTORY.read_text(encoding="utf-8"))
        original_count = len(data["records"])
        data["records"] = [r for r in data["records"] if r.get("id") != victim]
        EVO_HISTORY.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        deleted_count = original_count - len(data["records"])
        print(f"      原记录数: {original_count}, 删除后: {len(data['records'])} (删除了 {deleted_count} 条)")

        # Step 2: 运行检查──必须 FAIL
        print(f"[3/4] 验证守卫：检查修改后的文件 ...")
        modified_records = load_history(EVO_HISTORY)
        modified_ids = get_ids(modified_records)

        failure = check_no_deletions(modified_ids, baseline_ids, f"git:{baseline_ref}")
        if failure is None:
            die("自检失败：删除记录后守卫未触发 FAIL！守卫未生效。")
        print(f"      正确拦截 ✓")
        print(f"      错误信息: {failure}")

        # Step 3: 恢复原文件
        print(f"[4/4] 恢复 evolution_history.json ...")
        shutil.copy2(str(backup), str(EVO_HISTORY))

        # Step 4: 验证恢复后 PASS
        restored_records = load_history(EVO_HISTORY)
        restored_ids = get_ids(restored_records)
        failure = check_no_deletions(restored_ids, baseline_ids, f"git:{baseline_ref}")
        if failure is not None:
            die(f"自检失败：恢复后守卫仍 FAIL——{failure}")

        print(f"\n[OK] 自检通过：守卫『能探测』已确认。")
        print(f"  删除 {victim} → FAIL ✓")
        print(f"  恢复 → PASS ✓")

    finally:
        # 确保恢复
        if backup.exists():
            shutil.copy2(str(backup), str(EVO_HISTORY))
            backup.unlink()

    sys.exit(0)


# ─── 主入口 ────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="evolution_history.json 防覆盖守卫（B17）"
    )
    parser.add_argument(
        "--pre-commit", action="store_true",
        help="预提交模式：对比 HEAD~1 与工作区，拦截任何 EVO-*/AUTO-* 删除",
    )
    parser.add_argument(
        "--current-ok", action="store_true",
        help="验证当前工作区相对 HEAD~1 无删除",
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="自检模式：模拟删除 → 验证 FAIL → 恢复 → 验证 PASS",
    )
    parser.add_argument(
        "--git-ref", type=str, default=None,
        help="基线 git 引用（默认 HEAD~1，降级到 HEAD）",
    )
    parser.add_argument(
        "--no-strict", action="store_true",
        help="关闭 AUTO-* 删除检查（默认启用，B17 要求双保护）",
    )
    # 保留旧参数兼容
    parser.add_argument("--base", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--strict", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--save-baseline", type=str, default=None, metavar="OUTPUT.json", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # ── 自检模式 ──
    if args.self_test:
        run_self_test()
        return  # unreachable

    # ── 文件存在性 ──
    if not EVO_HISTORY.exists():
        die(f"未找到 evolution_history.json: {EVO_HISTORY}")

    # ── 确定基线 ──
    baseline_ref = get_baseline_ref(args)
    print(f"  基线: {baseline_ref}")

    try:
        baseline_records = load_git_history(baseline_ref)
    except SystemExit:
        # 单个 commit（无父）降级
        baseline_records = load_git_history("HEAD")
        baseline_ref = "HEAD"
        print(f"  （降级至 {baseline_ref}，初始提交入站检查）")

    baseline_ids = get_ids(baseline_records)

    # ── 加载当前内容 ──
    # pre-commit 模式优先读取暂存区，否则读工作区文件
    if args.pre_commit:
        staged = load_staged_version()
        if staged is not None:
            current_records = staged
            print(f"  来源: 暂存区 (staged)")
        else:
            current_records = load_history(EVO_HISTORY)
            print(f"  来源: 工作区文件 (未暂存)")
    else:
        current_records = load_history(EVO_HISTORY)
        print(f"  来源: 工作区文件")

    current_ids = get_ids(current_records)

    # ── 输出摘要 ──
    print_summary(current_ids, baseline_ids)

    # ── 核心检查 ──
    strict = not args.no_strict
    failure = check_no_deletions(current_ids, baseline_ids, f"git:{baseline_ref}", strict=strict)
    if failure:
        die(failure)

    print("\n[OK] VALIDATE EVO HISTORY PASSED: 无 EVO-* / AUTO-* id 被删除。")
    sys.exit(0)


if __name__ == "__main__":
    main()