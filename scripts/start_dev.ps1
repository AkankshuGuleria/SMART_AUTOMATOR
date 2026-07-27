# scripts/start_dev.ps1
# Start AUTOMATA backend + frontend for development.
# Run from the repo root: .\scripts\start_dev.ps1
#
# Requirements:
#   - Python virtualenv at backend\.venv
#   - Node packages installed in frontend\

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$Root = Split-Path $PSScriptRoot -Parent
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$PythonExe   = Join-Path $BackendDir ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "  ╔═══════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║   AUTOMATA Dev Environment    ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if (-not $FrontendOnly) {
    Write-Host "[1/2] Checking backend…" -ForegroundColor Yellow
    $backendRunning = $false
    try {
        $response = Invoke-WebRequest "http://127.0.0.1:8000/health" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            $backendRunning = $true
            Write-Host "  Backend already running on http://127.0.0.1:8000" -ForegroundColor Green
        }
    } catch {
        # Backend not running, will start it
    }

    if (-not $backendRunning) {
        Write-Host "  Starting backend (FastAPI on :8000)…" -ForegroundColor Yellow
        if (-not (Test-Path $PythonExe)) {
            Write-Host "  ERROR: Python venv not found at $PythonExe" -ForegroundColor Red
            Write-Host "  Run: cd backend && uv sync" -ForegroundColor Gray
            exit 1
        }
        Start-Process -FilePath "wt" -ArgumentList "-d", $BackendDir, "powershell", "-NoExit", "-Command", "& '$PythonExe' main.py" -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -ne 0) {
            Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; & '$PythonExe' main.py" -WindowStyle Normal
        }
        Write-Host "  Backend started in new terminal window." -ForegroundColor Green
        Write-Host "  Waiting 3s for backend to initialise…" -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
}

if (-not $BackendOnly) {
    Write-Host "[2/2] Starting frontend (Tauri dev)…" -ForegroundColor Yellow
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Host "  Installing npm packages…" -ForegroundColor Gray
        Set-Location $FrontendDir
        npm install --silent
    }
    Write-Host "  Launching Tauri dev…" -ForegroundColor Gray
    Set-Location $FrontendDir
    npm run tauri dev
}
