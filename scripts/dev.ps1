<#
.SYNOPSIS
  Start AUTOMATA for development: the Python agent (with auto-reload) plus the UI.

.DESCRIPTION
  Reuses an agent that already answers on /health; otherwise starts one in its
  own window (falling back to a free port 8001-8010 if 8000 is taken by
  something else) and waits for it. Then starts the UI:
    default   -> Vite in the browser (http://localhost:5173)
    -Desktop  -> the Tauri desktop app in dev mode

.EXAMPLE
  .\scripts\dev.ps1               # browser UI
  .\scripts\dev.ps1 -Desktop      # desktop app
  .\scripts\dev.ps1 -BackendOnly  # agent only
#>
param(
    [switch]$Desktop,
    [switch]$BackendOnly
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

function Test-Agent([int]$Port) {
    try { Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

function Test-PortInUse([int]$Port) {
    $null -ne (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. See docs/DEVELOPMENT.md (https://docs.astral.sh/uv/)."
}

$port = 8000
if (Test-Agent $port) {
    Write-Host "Agent already running on http://127.0.0.1:$port" -ForegroundColor Green
} else {
    if (Test-PortInUse $port) {
        $port = (8001..8010 | Where-Object { -not (Test-PortInUse $_) } | Select-Object -First 1)
        Write-Warning "Port 8000 is used by another program; starting the agent on $port."
    }
    Write-Host "Starting the agent on http://127.0.0.1:$port ..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-NoProfile", "-Command",
        "Set-Location '$backendDir'; uv run uvicorn api.server:app --reload --host 127.0.0.1 --port $port"
    ) | Out-Null
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline -and -not (Test-Agent $port)) { Start-Sleep -Milliseconds 500 }
    if (Test-Agent $port) { Write-Host "Agent ready." -ForegroundColor Green }
    else { Write-Warning "The agent did not answer /health within 30 s; check its window for errors." }
}

if ($BackendOnly) { return }

Set-Location $frontendDir
if (-not (Test-Path "node_modules")) { npm ci }
$env:VITE_API_BASE = "http://127.0.0.1:$port"
$env:VITE_WS_BASE = "ws://127.0.0.1:$port"
if ($Desktop) { npm run tauri dev } else { npm run dev }
