#!/usr/bin/env python3
"""
Fly64 merge_evolution_history.py — 规范合并并集工具 (B03)。

语义：
  取 HEAD 与 HEAD~1 两份 evolution_history.json 按 records[].id 做并集。
  将 EVO-072/073 按日期插入正确时间线位置。
  对齐 canonical_versions brain=2.24.0 / skill=3.5.1 / as_of=当前时刻。

用法：
  python3 scripts/merge_evolution_history.py [--output OUTPUT.json]
    [--base BASE.json] [--head HEAD.json]

  默认：--base 取 git show HEAD~1, --head 从技能目录读, --output 直接覆写技能目录。
  添加 --backup 在覆写前备份原文件 (.bak)。
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # fly64/
DEFAULT_SKILLS = PROJECT_ROOT / "skills" / "evolution_history.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_head1_head() -> dict:
    """读取 HEAD~1 版本 via git show (默认基线)。"""
    import subprocess
    r = subprocess.run(
        ["git", "show", "HEAD~1:fly64/skills/evolution_history.json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        print(f"ERROR: git show HEAD~1 failed: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)


def merge_records(head_records: list[dict], base_records: list[dict]) -> list[dict]:
    """按 id 做并集合并。HEAD 的版本优先（保留新增的 EVO-074 / AUTO-0017~0023）；
    base 补充 HEAD 中缺失的 EVO-072/073。
    """
    head_ids = {r["id"] for r in head_records}
    base_ids = {r["id"] for r in base_records}

    # 新建映射并集
    merged_map: dict[str, dict] = {}
    for r in head_records:
        merged_map[r["id"]] = r
    for r in base_records:
        if r["id"] not in head_ids:
            merged_map[r["id"]] = r

    added = base_ids - head_ids
    removed = head_ids - base_ids
    print(f"  HEAD records: {len(head_records)}")
    print(f"  BASE records: {len(base_records)}")
    print(f"  Added (from base): {len(added)} — {sorted(added)}")
    print(f"  Removed (from head, kept): {len(removed)} — {sorted(removed)}")
    print(f"  Merged total: {len(merged_map)}")

    # Convert back to list, maintaining chronological order
    def sort_key(r):
        """Derive a sortable timestamp for chronological ordering."""
        # Prefer date+time; fall back to recorded_at; use id for ties
        d = r.get("date", "")
        t = r.get("time", "")
        ra = r.get("recorded_at", "")
        rid = r.get("id", "")

        if d and t:
            return f"{d}T{t}"
        if d:
            return f"{d}T00:00:00"
        if ra:
            return ra
        return f"1970-01-01T00:00:00+{rid}"

    merged = sorted(merged_map.values(), key=sort_key)
    return merged


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Merge evolution_history.json HEAD ∪ HEAD~1")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output path (default: overwrite skills/evolution_history.json)")
    parser.add_argument("--base", type=Path, default=None,
                        help="Base JSON path (default: git show HEAD~1)")
    parser.add_argument("--head", type=Path, default=DEFAULT_SKILLS,
                        help="HEAD JSON path (default: skills/evolution_history.json)")
    parser.add_argument("--backup", action="store_true",
                        help="Backup output file before overwriting")
    args = parser.parse_args()

    # Load HEAD
    head_data = load_json(args.head)

    # Load base
    if args.base:
        base_data = load_json(args.base)
    else:
        print("  Loading HEAD~1 via git show...")
        base_data = get_head1_head()

    head_records = head_data.get("records", [])
    base_records = base_data.get("records", [])

    print(f"Merging evolution_history.json...")
    merged_records = merge_records(head_records, base_records)

    # Canonical versions: align with main.py (brain=2.24.0, skill=3.5.1)
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    canonical = {
        "brain": "2.24.0",
        "skill": "3.5.1",
        "as_of": now_iso,
    }

    result = {
        "$schema": head_data.get("$schema", "fly64/evolution-history/1.0"),
        "canonical_versions": canonical,
        "records": merged_records,
    }

    output = args.output
    if output is None:
        output = DEFAULT_SKILLS

    if args.backup and output.exists():
        bak = output.with_suffix(".json.bak")
        output.rename(bak)
        print(f"  Backed up existing → {bak}")

    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  Wrote {len(merged_records)} records to {output}")
    print(f"  Canonical: brain={canonical['brain']}, skill={canonical['skill']}, as_of={canonical['as_of']}")
    print("  ✅ Merge complete.")


if __name__ == "__main__":
    main()