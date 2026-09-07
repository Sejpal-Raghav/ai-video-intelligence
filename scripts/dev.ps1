# scripts/dev.ps1
# Starts the API, analysis worker, and Next.js development server.

param(
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 8000,

    [ValidateRange(1, 65535)]
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$webDirectory = Join-Path $repoRoot "apps\web"
$storageRoot = Join-Path $repoRoot "storage"
$envFile = Join-Path $repoRoot ".env"
$envExample = Join-Path $repoRoot ".env.example"
$modelFile = Join-Path $repoRoot "models\warehouse-v1.pt"

$apiProcess = $null
$workerProcess = $null
$webProcess = $null

function Write-Status {
    param(
        [string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::White
    )

    Write-Host $Message -ForegroundColor $Color
}

function Test-PortAvailable {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $listener = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue

    if ($listener) {
        throw "$ServiceName cannot start because port $Port is already in use."
    }
}

function Stop-ProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Name
    )

    if ($null -eq $Process) {
        return
    }

    try {
        if (-not $Process.HasExited) {
            Write-Status "Stopping $Name..." Yellow

            # taskkill /T also terminates child processes such as next-server.
            & "$env:SystemRoot\System32\taskkill.exe" `
                /PID $Process.Id `
                /T `
                /F `
                2>$null | Out-Null
        }
    }
    catch {
        Write-Status "Warning: could not stop $Name cleanly: $($_.Exception.Message)" Yellow
    }
}

Write-Status "==========================================================" Cyan
Write-Status "  Warehouse Video Intelligence: Development Services" Cyan
Write-Status "==========================================================" Cyan
Write-Status "Repository: $repoRoot" DarkGray

# ---------------------------------------------------------------------------
# Validate the Python environment
# ---------------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    Write-Status "[ERROR] Python virtual environment was not found." Red
    Write-Host ""
    Write-Host "Run these commands from the repository root:"
    Write-Host ""
    Write-Host "  py -3.11 -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install --no-deps -e backend"
    exit 1
}

$pythonVersion = & $pythonExe --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Unable to execute $pythonExe"
}

$pythonMinorVersion = & $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $pythonMinorVersion.Trim() -ne "3.11") {
    throw "Python 3.11 is required. Found: $pythonVersion"
}

& $pythonExe -c "import warehouse_ai" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Status "[ERROR] The warehouse_ai package is not installed in .venv." Red
    Write-Host ""
    Write-Host "Run:"
    Write-Host ""
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install --no-deps -e backend"
    exit 1
}

Write-Status "[OK] Python: $pythonVersion" Green
Write-Status "[OK] Backend package: warehouse_ai" Green

# ---------------------------------------------------------------------------
# Validate Node.js and pnpm
# ---------------------------------------------------------------------------

$nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand) {
    throw "Node.js was not found. Install Node.js 22.x or activate the version in .nvmrc."
}

$nodeVersion = & $nodeCommand.Source --version
Write-Status "[OK] Node: $nodeVersion" Green

# Explicitly request pnpm.cmd. Using 'pnpm' can select the Unix shell shim and
# cause: '%1 is not a valid Win32 application'.
$pnpmCommand = Get-Command "pnpm.cmd" -ErrorAction SilentlyContinue
if ($null -eq $pnpmCommand) {
    Write-Status "[ERROR] pnpm.cmd was not found." Red
    Write-Host ""
    Write-Host "Install/activate pnpm and then run:"
    Write-Host ""
    Write-Host "  corepack enable"
    Write-Host "  pnpm.cmd --version"
    exit 1
}

$pnpmExe = $pnpmCommand.Source
$pnpmVersion = & $pnpmExe --version

Write-Status "[OK] pnpm: $pnpmVersion" Green
Write-Status "[OK] pnpm executable: $pnpmExe" Green

if (-not (Test-Path -LiteralPath (Join-Path $webDirectory "node_modules"))) {
    Write-Status "[ERROR] Frontend dependencies are not installed." Red
    Write-Host ""
    Write-Host "Run:"
    Write-Host ""
    Write-Host "  pnpm.cmd --dir apps\web install --frozen-lockfile"
    exit 1
}

# ---------------------------------------------------------------------------
# Prepare configuration and storage
# ---------------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $envFile)) {
    if (Test-Path -LiteralPath $envExample) {
        Copy-Item -LiteralPath $envExample -Destination $envFile
        Write-Status "[OK] Created .env from .env.example" Green
    }
    else {
        throw ".env and .env.example are both missing."
    }
}

if (-not (Test-Path -LiteralPath $storageRoot)) {
    New-Item -ItemType Directory -Path $storageRoot -Force | Out-Null
    Write-Status "[OK] Created storage directory: $storageRoot" Green
}

$ffmpegCommand = Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue
$ffprobeCommand = Get-Command "ffprobe.exe" -ErrorAction SilentlyContinue

if ($null -eq $ffmpegCommand -or $null -eq $ffprobeCommand) {
    Write-Status "[WARNING] FFmpeg or ffprobe was not found in PATH." Yellow
    Write-Status "Uploads and video processing will fail until FFmpeg is installed." Yellow
}
else {
    Write-Status "[OK] FFmpeg and ffprobe found" Green
}

if (-not (Test-Path -LiteralPath $modelFile -PathType Leaf)) {
    Write-Status "[WARNING] Model file is missing: $modelFile" Yellow
    Write-Status "The services can start, but live inference jobs will fail." Yellow
}

# ---------------------------------------------------------------------------
# Verify ports before launching anything
# ---------------------------------------------------------------------------

Test-PortAvailable -Port $ApiPort -ServiceName "API server"
Test-PortAvailable -Port $WebPort -ServiceName "Next.js server"

# ---------------------------------------------------------------------------
# Launch services
# ---------------------------------------------------------------------------

try {
    Write-Host ""
    Write-Status "Starting API server on port $ApiPort..." Yellow

    $apiProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "warehouse_ai.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "$ApiPort",
            "--workers",
            "1"
        ) `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -PassThru

    Write-Status "Starting analysis worker..." Yellow

    $workerProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @(
            "-m",
            "warehouse_ai.worker.main"
        ) `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -PassThru

    Write-Status "Starting Next.js on port $WebPort..." Yellow

    # Use 'pnpm exec next' because package.json currently hardcodes port 3000.
    $webProcess = Start-Process `
        -FilePath $pnpmExe `
        -ArgumentList @(
            "--dir",
            "apps/web",
            "exec",
            "next",
            "dev",
            "-p",
            "$WebPort"
        ) `
        -WorkingDirectory $repoRoot `
        -NoNewWindow `
        -PassThru

    Start-Sleep -Seconds 2

    if ($apiProcess.HasExited) {
        throw "API server exited during startup with code $($apiProcess.ExitCode)."
    }

    if ($workerProcess.HasExited) {
        throw "Analysis worker exited during startup with code $($workerProcess.ExitCode)."
    }

    if ($webProcess.HasExited) {
        throw "Next.js exited during startup with code $($webProcess.ExitCode)."
    }

    Write-Host ""
    Write-Status "All services launched." Green
    Write-Status "Web UI:   http://127.0.0.1:$WebPort" Cyan
    Write-Status "API Docs: http://127.0.0.1:$ApiPort/docs" Cyan
    Write-Status "Ready:    http://127.0.0.1:$ApiPort/readyz" Cyan
    Write-Host ""
    Write-Status "Press Ctrl+C to stop all services." White

    while ($true) {
        Start-Sleep -Seconds 1

        if ($apiProcess.HasExited) {
            throw "API server exited unexpectedly with code $($apiProcess.ExitCode)."
        }

        if ($workerProcess.HasExited) {
            throw "Analysis worker exited unexpectedly with code $($workerProcess.ExitCode)."
        }

        if ($webProcess.HasExited) {
            throw "Next.js exited unexpectedly with code $($webProcess.ExitCode)."
        }
    }
}
catch {
    Write-Host ""
    Write-Status "[ERROR] $($_.Exception.Message)" Red
}
finally {
    Write-Host ""
    Write-Status "Stopping development services..." Yellow

    Stop-ProcessTree -Process $webProcess -Name "Next.js"
    Stop-ProcessTree -Process $workerProcess -Name "analysis worker"
    Stop-ProcessTree -Process $apiProcess -Name "API server"

    Write-Status "[OK] Shutdown complete." Green
}