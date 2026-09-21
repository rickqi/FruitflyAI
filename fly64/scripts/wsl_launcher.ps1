<#
.SYNOPSIS
    Fly64 WSL Launcher — PowerShell 包装器
.DESCRIPTION
    从 Windows 侧启动 Fly64 WSL 环境。使用 Start-Process 创建持久 WSL 终端，
    解决 `wsl -e bash -c` 导致的进程被 kill 问题。

    问题根因：
    当使用 `wsl -e bash -c "command"` 时，WSL 创建一个临时终端会话。
    bash 执行完毕（command 完成）→ bash 退出 → WSL Relay 进程终止 →
    Relay 下所有子进程（包括 setsid nohup 的进程）被 SIGTERM 杀死。

    Start-Process workaround:
    Start-Process wsl /bin/bash script.sh 创建一个新 WSL 终端窗口，
    bash 在前台运行脚本，窗口保持打开 → Relay 进程保持活跃。
    tmux 在此基础上增加守护层：即使窗口关闭，tmux server 继续运行。

    三选一模式：
    1. tmux 模式（默认）: 最可靠，使用 tmux 守护会话
    2. console 模式: 保留窗口在前台（传统方式）
    3. background 模式: 隐藏窗口后台运行

.PARAMETER Action
    操作类型: launch / stop / status / restart / attach
.PARAMETER Mode
    启动模式: tmux (默认) / console / background
.PARAMETER RomPath
    SM64 ROM 文件路径（Windows 路径如 D:\roms\sm64.z64）
.PARAMETER WslDistro
    WSL 发行版名称（默认 Ubuntu-22.04）
.PARAMETER NoWindow
    隐藏 PowerShell 窗口

.EXAMPLE
    # tmux 模式（推荐）— 使用 tmux 守护，最稳定
    .\scripts\wsl_launcher.ps1 -Action launch -RomPath D:\roms\baserom.us.z64

    # console 模式 — 保留 WSL 终端窗口可见
    .\scripts\wsl_launcher.ps1 -Action launch -Mode console -RomPath D:\roms\baserom.us.z64

    # background 模式 — 完全隐藏窗口
    .\scripts\wsl_launcher.ps1 -Action launch -Mode background

    # 查看状态
    .\scripts\wsl_launcher.ps1 -Action status

    # 停止
    .\scripts\wsl_launcher.ps1 -Action stop

    # 重启
    .\scripts\wsl_launcher.ps1 -Action restart

    # 附加到 tmux 会话
    .\scripts\wsl_launcher.ps1 -Action attach
#>

param(
    [ValidateSet('launch', 'stop', 'status', 'restart', 'attach')]
    [string]$Action = 'launch',

    [ValidateSet('tmux', 'console', 'background')]
    [string]$Mode = 'tmux',

    [string]$RomPath = '',

    [string]$WslDistro = 'Ubuntu-22.04',

    [switch]$NoWindow
)

# ---- 配置 ---------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$WslScript = '/root/fly64/scripts/wsl_launcher.sh'
$WslRomPath = ''

# ---- 路径转换: Windows 路径 → WSL 路径 -----------------------------------
if ($RomPath -and (Test-Path $RomPath)) {
    $RomPath = (Resolve-Path $RomPath).Path
    # 转换 D:\... → /mnt/d/...
    if ($RomPath -match '^([A-Za-z]):\\(.*)') {
        $DriveLetter = $Matches[1].ToLower()
        $WslPath = $Matches[2] -replace '\\', '/'
        $WslRomPath = "/mnt/$DriveLetter/$WslPath"
    } else {
        Write-Warning "无法转换路径: $RomPath，尝试直接传递"
        $WslRomPath = $RomPath
    }
}

# ---- 辅助函数 ---------------------------------------------------------------
function Write-Header {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " Fly64 WSL Launcher (PowerShell)" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " 分发版    : $WslDistro"
    Write-Host " 模式      : $Mode"
    Write-Host " 操作      : $Action"
    if ($WslRomPath) { Write-Host " ROM路径   : $WslRomPath" }
    Write-Host "--------------------------------------------" -ForegroundColor Gray
}

function Invoke-WslCommand {
    param([string]$Command)
    $wslArgs = @('-d', $WslDistro, '--')
    if ($Mode -eq 'console') {
        # 交互式: bash -i 保持 shell 活动
        $wslArgs += 'bash', '-i', '-c', $Command
    } else {
        $wslArgs += 'bash', '-c', $Command
    }
    & 'wsl' $wslArgs 2>&1
}

# ---- 启动（tmux 模式 — 推荐）-----------------------------------------------
function Start-TmuxMode {
    Write-Host "[launch] 启动方式: tmux 守护会话 (最可靠)" -ForegroundColor Green
    Write-Host "[launch] tmux server 作为独立守护进程运行" -ForegroundColor Green
    Write-Host "[launch] 关闭此窗口不会影响 Fly64 运行" -ForegroundColor Green
    Write-Host ""

    # 设置 tmux 或 console 模式
    $launchCmd = "cd /root/fly64 && bash scripts/wsl_launcher.sh --launch"
    if ($WslRomPath) {
        $launchCmd += " --rom '$WslRomPath'"
    }

    Invoke-WslCommand -Command $launchCmd

    # 验证启动 (等待 3 秒后检查)
    Start-Sleep -Seconds 3
    $status = Invoke-WslCommand -Command "cd /root/fly64 && bash scripts/wsl_launcher.sh --status"
    Write-Host ""
    Write-Host "[verify] 启动状态:" -ForegroundColor Cyan
    $status | ForEach-Object { Write-Host "  $_" }
}

# ---- 启动（console 模式 — 保留终端窗口）-----------------------------------
function Start-ConsoleMode {
    Write-Host "[launch] 启动方式: 持久终端窗口" -ForegroundColor Yellow
    Write-Host "[launch] 关闭 WSL 终端窗口将终止进程" -ForegroundColor Yellow
    Write-Host "[launch] 推荐在不关闭窗口的自动化任务中使用" -ForegroundColor Yellow
    Write-Host ""

    # 构建 WSL 命令字符串
    $wslCmd = "export DISPLAY=:0 SDL_VIDEODRIVER=x11; "
    $wslCmd += "cd /root/fly64 && export PYTHONPATH=/root/fly64 && "
    $wslCmd += "rm -f /tmp/f64b_traj && "

    # 启动脑模型 (setsid nohup)
    $wslCmd += "setsid nohup python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64.log 2>&1 < /dev/null & "
    $wslCmd += "echo 'Brain PID: ' \$!; sleep 5; "

    # 启动 SM64（如果提供了 ROM）
    if ($WslRomPath) {
        $wslCmd += "echo 'Starting SM64...'; "
        $wslCmd += "cd /root/fly64/.cache/sm64ex && "
        $wslCmd += "setsid nohup env DISPLAY=:0 SDL_VIDEODRIVER=x11 FLY64_BRIDGE=/tmp/f64b_traj "
        $wslCmd += "./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/sm64.log 2>&1 < /dev/null & "
        $wslCmd += "echo 'SM64 PID: ' \$!; "
        $wslCmd += "cd /root/fly64; "
    }

    # 保持窗口打开，显示状态
    $wslCmd += "echo ''; echo '=== Status ==='; "
    $wslCmd += "ps aux | grep -E 'fly64|sm64' | grep -v grep; "
    $wslCmd += "echo ''; echo 'Dashboard: http://127.0.0.1:8765/'; "
    $wslCmd += "echo 'Press Ctrl+C to stop'; "
    $wslCmd += "tail -f /tmp/fly64.log"

    # 使用 Start-Process 创建新 WSL 终端窗口
    $startArgs = @{
        FilePath = 'wsl.exe'
        ArgumentList = @('-d', $WslDistro, '--', 'bash', '-i', '-c', $wslCmd)
        WindowStyle = if ($NoWindow) { 'Hidden' } else { 'Normal' }
        WorkingDirectory = $ProjectDir
    }

    if ($NoWindow) {
        $startArgs['WindowStyle'] = 'Hidden'
        $startArgs['PassThru'] = $true
        $proc = Start-Process @startArgs
        Write-Host "[launch] 后台 WSL 进程 PID: $($proc.Id)" -ForegroundColor Green
    } else {
        $startArgs['PassThru'] = $false
        Start-Process @startArgs
        Write-Host "[launch] 已启动 WSL 终端窗口" -ForegroundColor Green
    }
}

# ---- 启动（background 模式 — 完全隐藏）------------------------------------
function Start-BackgroundMode {
    Write-Host "[launch] 启动方式: 完全后台 (隐藏 WSL 窗口)" -ForegroundColor Magenta
    Write-Host "[launch] 进程由 WSL --fork 维持" -ForegroundColor Magenta
    Write-Host ""

    # 先检查 tmux 是否可用（bmux 模式保证可靠性）
    $tmuxOk = Invoke-WslCommand -Command "command -v tmux && tmux -V || echo 'no tmux'"
    if ($tmuxOk -match 'tmux') {
        Write-Host "[launch] 检测到 tmux，使用 tmux 守护模式" -ForegroundColor Green
        Start-TmuxMode
        return
    }

    # 无 tmux：使用 wsl --fork 后台维持
    Write-Host "[launch] tmux 不可用，使用 wsl --fork 模式" -ForegroundColor Yellow
    Write-Host "[launch] 注意事项: 需要 WSL 预览版支持 --fork" -ForegroundColor Yellow

    # 创建后台 WSL 实例来维持进程
    $bgCmd = "cd /root/fly64 && export PYTHONPATH=/root/fly64 && "
    $bgCmd += "rm -f /tmp/f64b_traj && "
    $bgCmd += "setsid nohup python3 -m fly64.main --bridge /tmp/f64b_traj --record /tmp/f64r_traj.npz --no-browser --duration 0 > /tmp/fly64.log 2>&1 < /dev/null & "
    $bgCmd += "echo 'Brain started'; "

    if ($WslRomPath) {
        $bgCmd += "cd /root/fly64/.cache/sm64ex && "
        $bgCmd += "setsid nohup env DISPLAY=:0 SDL_VIDEODRIVER=x11 FLY64_BRIDGE=/tmp/f64b_traj ./build/us_pc/sm64.us.f3dex2e --skip-intro > /tmp/sm64.log 2>&1 < /dev/null & "
        $bgCmd += "echo 'SM64 started'; "
    }

    $bgCmd += "echo 'Fly64 running in background'; "
    $bgCmd += "while true; do sleep 60; done"  # 保持进程存在

    try {
        # 使用 wsl -e bash -c 但通过保持 stdin 开放来维持
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = 'wsl.exe'
        $psi.Arguments = "-d $WslDistro -- bash -c '$bgCmd'"
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $proc = [System.Diagnostics.Process]::Start($psi)

        Write-Host "[launch] 后台 WSL 进程 PID: $($proc.Id)" -ForegroundColor Green
        Write-Host "[launch] 注意: 此模式依赖 WSL 进程存活" -ForegroundColor Yellow
        Write-Host "[launch] 推荐安装 tmux 以获得更稳定的体验" -ForegroundColor Yellow
    } catch {
        Write-Error "后台启动失败: $_"
        Write-Host "请重试 tmux 模式: 在 WSL 中执行: sudo apt-get install -y tmux" -ForegroundColor Yellow
    }
}

# ---- 停止 ---------------------------------------------------------------
function Stop-Fly64 {
    Write-Host "[stop] 停止 Fly64..." -ForegroundColor Red
    Invoke-WslCommand -Command "cd /root/fly64 && bash scripts/wsl_launcher.sh --stop"
}

# ---- 状态查看 ---------------------------------------------------------------
function Get-Fly64Status {
    Invoke-WslCommand -Command "cd /root/fly64 && bash scripts/wsl_launcher.sh --status"
}

# ---- 附加 tmux ---------------------------------------------------------------
function Connect-Tmux {
    Write-Host "[attach] 附加到 tmux 会话 fly64..." -ForegroundColor Cyan
    Write-Host "[attach] 使用 Ctrl+B d 分离（不会停止进程）" -ForegroundColor Cyan
    Write-Host ""

    # 使用 Start-Process 打开新窗口进行 tmux attach
    $tmuxCmd = "cd /root/fly64 && tmux attach-session -t fly64"
    Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d', $WslDistro, '--', 'bash', '-i', '-c', $tmuxCmd) -WindowStyle Normal
}

# ---- 主流程 ---------------------------------------------------------------
Write-Header

switch ($Action) {
    'launch' {
        switch ($Mode) {
            'tmux'       { Start-TmuxMode }
            'console'    { Start-ConsoleMode }
            'background' { Start-BackgroundMode }
        }
    }
    'stop'    { Stop-Fly64 }
    'status'  { Get-Fly64Status }
    'restart' {
        Stop-Fly64
        Start-Sleep -Seconds 3
        Start-TmuxMode
    }
    'attach'  { Connect-Tmux }
}

Write-Host ""
Write-Host "--------------------------------------------" -ForegroundColor Gray
Write-Host " 完成" -ForegroundColor Cyan