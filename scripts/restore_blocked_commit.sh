#!/usr/bin/env bash
# restore_blocked_commit.sh — 从被 pre-commit 钩子拦截的提交中恢复
# evolution_history.json（B17 辅助脚本）。
#
# 当 pre-commit 钩子拒绝提交（EVO-* / AUTO-* id 被删除）时，
# 此脚本将 evolution_history.json 从 git HEAD 恢复，
# 并显示被拦截时丢失的 id 差异。
#
# 用法:
#   bash scripts/restore_blocked_commit.sh
#   bash scripts/restore_blocked_commit.sh --diff-only   # 仅显示差异，不恢复
#   bash scripts/restore_blocked_commit.sh --force       # 强制恢复（不询问）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EVO_FILE="fly64/skills/evolution_history.json"

DIFF_ONLY=false
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --diff-only) DIFF_ONLY=true ;;
        --force) FORCE=true ;;
        *) echo "未知参数: $arg"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

echo "========================================================"
echo "  B17 恢复辅助: restore_blocked_commit.sh"
echo "========================================================"

# 检查 git HEAD 中的版本
if ! git show HEAD:"$EVO_FILE" > /dev/null 2>&1; then
    echo "[ERROR] HEAD 中没有 $EVO_FILE"
    exit 1
fi

# 检查工作区文件
if [ ! -f "$EVO_FILE" ]; then
    echo "[ERROR] 工作区中不存在 $EVO_FILE"
    exit 1
fi

# 显示差异
echo ""
echo "--- 当前工作区 vs HEAD 的 EVO-*/AUTO-* id 差异 ---"

python3 - "$EVO_FILE" << 'PYEOF'
import json, sys
from pathlib import Path

def get_ids(records):
    return {
        "evo": {r["id"] for r in records if r.get("id","").startswith("EVO-")},
        "auto": {r["id"] for r in records if r.get("id","").startswith("AUTO-")},
    }

# 从 HEAD 读取
import subprocess
hdr = subprocess.run(["git", "show", "HEAD:fly64/skills/evolution_history.json"],
                     capture_output=True, check=True)
head_data = json.loads(hdr.stdout.decode("utf-8"))
head_ids = get_ids(head_data.get("records", []))

# 从工作区读取
ws_path = Path(sys.argv[1])
ws_data = json.loads(ws_path.read_text(encoding="utf-8"))
ws_ids = get_ids(ws_data.get("records", []))

evo_deleted = head_ids["evo"] - ws_ids["evo"]
auto_deleted = head_ids["auto"] - ws_ids["auto"]

if evo_deleted:
    print(f"  HEAD 有但工作区缺失的 EVO-* id: {sorted(evo_deleted)}")
if auto_deleted:
    print(f"  HEAD 有但工作区缺失的 AUTO-* id: {sorted(auto_deleted)}")
if not evo_deleted and not auto_deleted:
    print("  无 id 丢失（但 pre-commit 可能因其他原因拦截）")

evo_added = ws_ids["evo"] - head_ids["evo"]
auto_added = ws_ids["auto"] - head_ids["auto"]
if evo_added:
    print(f"  工作区新增 EVO-* id（将被保留）: {sorted(evo_added)}")
if auto_added:
    print(f"  工作区新增 AUTO-* id（将被保留）: {sorted(auto_added)}")

PYEOF

echo "--------------------------------------------------------"

if [ "$DIFF_ONLY" = true ]; then
    exit 0
fi

if [ "$FORCE" = false ]; then
    echo ""
    echo "即将用 HEAD 版本覆盖工作区的 $EVO_FILE"
    echo "（新增记录不会丢失——下方会提示如何仅恢复删除的部分）"
    read -rp "确认恢复？(y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "已取消。"
        exit 1
    fi
fi

# 恢复：先备份，再 checkout
BACKUP_FILE="${EVO_FILE}.bak_$(date +%Y%m%d_%H%M%S)"
cp "$EVO_FILE" "$BACKUP_FILE"
echo "  已备份当前文件至: $BACKUP_FILE"

git checkout HEAD -- "$EVO_FILE"
echo "  已从 HEAD 恢复 $EVO_FILE"
echo ""
echo "注意: 工作区中新增的 EVO-* / AUTO-* id 已在 HEAD 版本中丢失。"
echo "  备份文件: $BACKUP_FILE"
echo "  建议: 使用 scripts/merge_evolution_history.py 将备份中的新 id 合并回"
echo "  恢复后的 $EVO_FILE"
echo ""
echo "[OK] 恢复完成。请手动检查后将备份文件删除。"