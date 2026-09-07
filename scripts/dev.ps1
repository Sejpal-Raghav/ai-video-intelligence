# scripts/dev.ps1 - Start Warehouse Video Intelligence services concurrently
param (
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Warehouse Video Intelligence: Development Services" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check Python environment
try {
    $pyVer = python --version 2>&1
    Write-Host "[OK] Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 3.11+ is required." -ForegroundColor Red
    exit 1
}

# Check Node environment
try {
    $nodeVer = node --version 2>&1
    Write-Host "[OK] Node: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js 22+ is required." -ForegroundColor Red
    exit 1
}

# Ensure storage directories exist
$storageRoot = Join-Path $PSScriptRoot "..\data\storage"
if (-not (Test-Path $storageRoot)) {
    New-Item -ItemType Directory -Path $storageRoot -Force | Out-Null
    Write-Host "[OK] Created storage root: $storageRoot" -ForegroundColor Green
}

Write-Host "`nStarting API Server (port $ApiPort)..." -ForegroundColor Yellow
$apiJob = Start-Process -FilePath "python" -ArgumentList "-m uvicorn warehouse_ai.api.app:app --host 127.0.0.1 --port $ApiPort" -PassThru -NoNewWindow

Write-Host "Starting Background Worker..." -ForegroundColor Yellow
$workerJob = Start-Process -FilePath "python" -ArgumentList "-m warehouse_ai.worker.main" -PassThru -NoNewWindow

Write-Host "Starting Next.js Web App (port $WebPort)..." -ForegroundColor Yellow
$webJob = Start-Process -FilePath "pnpm" -ArgumentList "--dir apps/web dev -p $WebPort" -PassThru -NoNewWindow

Write-Host "`nAll services launched successfully!" -ForegroundColor Green
Write-Host "Web UI:     http://localhost:$WebPort" -ForegroundColor Cyan
Write-Host "API Docs:   http://127.0.0.1:$ApiPort/docs" -ForegroundColor Cyan
Write-Host "Readyz:     http://127.0.0.1:$ApiPort/readyz" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to terminate all services..." -ForegroundColor White

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($apiJob.HasExited -or $workerJob.HasExited -or $webJob.HasExited) {
            Write-Host "`nOne or more background services exited unexpectedly." -ForegroundColor Yellow
            break
        }
    }
} finally {
    Write-Host "`nStopping all processes..." -ForegroundColor Yellow
    if (-not $apiJob.HasExited) { Stop-Process -Id $apiJob.Id -Force }
    if (-not $workerJob.HasExited) { Stop-Process -Id $workerJob.Id -Force }
    if (-not $webJob.HasExited) { Stop-Process -Id $webJob.Id -Force }
    Write-Host "[OK] Clean shutdown complete." -ForegroundColor Green
}
