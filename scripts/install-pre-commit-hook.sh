#!/usr/bin/env bash
# install-pre-commit-hook.sh — 安装 B17 evolution_history.json 防覆盖 pre-commit 钩子。
#
# 将 scripts/validate_evo_history.py 注册为 .git/hooks/pre-commit。
# 钩子本身不提交到 git（.git/ 是本地仓库），通过此脚本安装。
#
# 用法:
#   bash scripts/install-pre-commit-hook.sh          # 安装钩子
#   bash scripts/install-pre-commit-hook.sh --status # 检查安装状态
#   bash scripts/install-pre-commit-hook.sh --uninstall # 移除钩子

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOK_FILE="$PROJECT_ROOT/.git/hooks/pre-commit"
VALIDATE_SCRIPT="$SCRIPT_DIR/validate_evo_history.py"

# Unix Python (virtual env or system)
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

install_hook() {
    if [ ! -f "$VALIDATE_SCRIPT" ]; then
        echo "[ERROR] 未找到验证脚本: $VALIDATE_SCRIPT"
        exit 1
    fi

    # 确保 .git/hooks 存在
    mkdir -p "$(dirname "$HOOK_FILE")"

    cat > "$HOOK_FILE" << HOOK
#!/usr/bin/env bash
# Fly64 B17 pre-commit hook — evolution_history.json 防覆盖守卫。
# 由 scripts/install-pre-commit-hook.sh 安装，请通过该脚本管理。
# 最后安装: $(date "+%Y-%m-%d %H:%M:%S")

set -euo pipefail

# 如果 evolution_history.json 未变更则跳过（加速）
if ! git diff --cached --name-only -- 'fly64/skills/evolution_history.json' | grep -q .; then
    if ! git diff --name-only -- 'fly64/skills/evolution_history.json' | grep -q .; then
        exit 0
    fi
fi

# 运行验证
VALIDATE_SCRIPT="$VALIDATE_SCRIPT"
PYTHON="$PYTHON"

if [ ! -f "\$VALIDATE_SCRIPT" ]; then
    echo "[WARN] pre-commit hook: 验证脚本不存在 (\$VALIDATE_SCRIPT)，跳过"
    exit 0
fi

"\$PYTHON" "\$VALIDATE_SCRIPT" --pre-commit
RESULT=\$?

if [ \$RESULT -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "  pre-commit BLOCKED: evolution_history.json EVO-*/AUTO-* id"
    echo "  被删除——请检查并恢复丢失的记录。"
    echo ""
    echo "  辅助命令:"
    echo "    bash scripts/restore_blocked_commit.sh --diff-only  查看差异"
    echo "    bash scripts/restore_blocked_commit.sh             恢复 HEAD 版本"
    echo "============================================================"
    exit \$RESULT
fi

HOOK

    chmod +x "$HOOK_FILE"
    echo "[OK] pre-commit 钩子已安装至: $HOOK_FILE"
    echo "  验证脚本: $VALIDATE_SCRIPT"
    echo "  Python:    $PYTHON"
    echo ""
    echo "  首次运行验证:"
    echo "    $PYTHON $VALIDATE_SCRIPT --pre-commit"
}

check_status() {
    if [ -f "$HOOK_FILE" ]; then
        echo "pre-commit 钩子状态: 已安装"
        echo "  位置: $HOOK_FILE"
        head -6 "$HOOK_FILE"
    else
        echo "pre-commit 钩子状态: 未安装"
    fi
}

uninstall_hook() {
    if [ -f "$HOOK_FILE" ]; then
        rm -f "$HOOK_FILE"
        echo "[OK] pre-commit 钩子已移除: $HOOK_FILE"
    else
        echo "pre-commit 钩子未安装。"
    fi
}

case "${1:-}" in
    --status) check_status ;;
    --uninstall) uninstall_hook ;;
    *) install_hook ;;
esac