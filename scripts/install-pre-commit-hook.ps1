# install-pre-commit-hook.ps1 — 安装 B17 evolution_history.json 防覆盖 pre-commit 钩子 (Windows)。
#
# 用法:
#   .venv\Scripts\powershell.exe -File scripts\install-pre-commit-hook.ps1          # 安装
#   .venv\Scripts\powershell.exe -File scripts\install-pre-commit-hook.ps1 -Status   # 检查状态
#   .venv\Scripts\powershell.exe -File scripts\install-pre-commit-hook.ps1 -Uninstall # 移除

param(
    [switch]$Status,
    [switch]$Uninstall
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$HookFile = Join-Path $ProjectRoot ".git\hooks\pre-commit"
$ValidateScript = Join-Path $ProjectRoot "scripts\validate_evo_history.py"

# 查找 Python
$Python = ""
if (Test-Path (Join-Path $ProjectRoot ".venv\Scripts\python.exe")) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $Python = "python3"
} else {
    Write-Error "未找到 Python"
    exit 1
}

function Install-Hook {
    if (-not (Test-Path $ValidateScript)) {
        Write-Error "未找到验证脚本: $ValidateScript"
        exit 1
    }

    $hookContent = @"
#!/usr/bin/env bash
# Fly64 B17 pre-commit hook — evolution_history.json 防覆盖守卫。
# 由 scripts/install-pre-commit-hook.ps1 安装，请通过该脚本管理。
# 最后安装: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

set -euo pipefail

# 如果 evolution_history.json 未变更则跳过
if ! git diff --cached --name-only -- 'fly64/skills/evolution_history.json' | grep -q .; then
    if ! git diff --name-only -- 'fly64/skills/evolution_history.json' | grep -q .; then
        exit 0
    fi
fi

VALIDATE_SCRIPT="$ValidateScript"
PYTHON="$Python"

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
"@

    # 确保 .git/hooks 目录存在
    $hooksDir = Split-Path -Parent $HookFile
    if (-not (Test-Path $hooksDir)) {
        New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null
    }

    Set-Content -Path $HookFile -Value $hookContent -Encoding UTF8
    Write-Host "[OK] pre-commit 钩子已安装至: $HookFile"
    Write-Host "  验证脚本: $ValidateScript"
    Write-Host "  Python:    $Python"
}

function Check-Status {
    if (Test-Path $HookFile) {
        Write-Host "pre-commit 钩子状态: 已安装"
        Write-Host "  位置: $HookFile"
        Get-Content $HookFile -TotalCount 6
    } else {
        Write-Host "pre-commit 钩子状态: 未安装"
    }
}

function Uninstall-Hook {
    if (Test-Path $HookFile) {
        Remove-Item $HookFile -Force
        Write-Host "[OK] pre-commit 钩子已移除: $HookFile"
    } else {
        Write-Host "pre-commit 钩子未安装。"
    }
}

if ($Status) {
    Check-Status
} elseif ($Uninstall) {
    Uninstall-Hook
} else {
    Install-Hook
}