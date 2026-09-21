<#
.SYNOPSIS
    Fly64 12-hour soak test runner (Windows/PowerShell wrapper).

.DESCRIPTION
    Cross-platform soak wrapper that launches the brain process and the
    Python monitor_soak.py script for long-running stability verification.
    Supports both synthetic (no SM64) and real bridge modes.

.PARAMETER Synthetic
    Use synthetic world mode (no SM64 bridge dependency).

.PARAMETER Duration
    Soak duration in hours (default: 12).

.PARAMETER Interval
    Sampling interval in seconds (default: 5).

.PARAMETER HttpPort
    Dashboard HTTP port (default: 8765).

.PARAMETER WsPort
    WebSocket port (default: 8766).

.PARAMETER MaxRssMb
    RSS alert threshold in MB (default: 12000).

.PARAMETER OutputDir
    Output directory for reports (default: artifacts/).

.EXAMPLE
    .\scripts\run_soak.ps1 -Synthetic -Duration 12

.EXAMPLE
    .\scripts\run_soak.ps1 -Duration 0.5 -Interval 2   # 30-minute quick check
#>

param(
    [switch]$Synthetic,
    [float]$Duration = 12.0,
    [float]$Interval = 5.0,
    [int]$HttpPort = 8765,
    [int]$WsPort = 8766,
    [float]$MaxRssMb = 12000.0,
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

Write-Host "╔══════════════════════════════════════════════════════╗"
Write-Host "║     Fly64 Soak Runner ($(if ($Synthetic) { "Synthetic" } else { "SM64 Bridge" }))      ║"
Write-Host "╚══════════════════════════════════════════════════════╝"
Write-Host "Project:    $ProjectRoot"
Write-Host "Duration:   $Duration hours ($($Duration * 3600) seconds)"
Write-Host "Interval:   $Interval s"
Write-Host "HTTP port:  $HttpPort"
Write-Host "WS port:    $WsPort"
Write-Host "Max RSS:    $MaxRssMb MB"
Write-Host ""

# Build arguments for Python soak runner
$PyArgs = @(
    (Join-Path $ProjectRoot "scripts" "run_12h_soak.py")
    "--duration", ($Duration * 3600)
    "--interval", $Interval
    "--http-port", $HttpPort
    "--ws-port", $WsPort
    "--max-rss-mb", $MaxRssMb
)

if ($Synthetic) {
    $PyArgs += "--synthetic"
}

if ($OutputDir) {
    $PyArgs += "--output", $OutputDir
}

$PyArgs += "--check-service"

Write-Host "[$Timestamp] Starting soak run..." -ForegroundColor Cyan
Write-Host "[$Timestamp] Command: python $PyArgs" -ForegroundColor Gray

# Run the Python soak orchestrator
$proc = Start-Process -FilePath "python" -ArgumentList $PyArgs -NoNewWindow -Wait -PassThru

$Elapsed = [math]::Round((Get-Date).Subtract([DateTime]"$Timestamp").TotalSeconds, 1)
Write-Host ""
Write-Host "[$Timestamp] Soak run completed in ${Elapsed}s, exit code: $($proc.ExitCode)" -ForegroundColor Cyan

if ($proc.ExitCode -eq 0) {
    Write-Host "✅ SOAK PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ SOAK FAILED (exit code $($proc.ExitCode))" -ForegroundColor Red
}

exit $proc.ExitCode