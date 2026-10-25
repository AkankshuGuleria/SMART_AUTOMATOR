$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$backendPort = 8000
$healthUrl = "http://127.0.0.1:$backendPort/health"

function Test-Backend {
    param([int]$Port = $backendPort)
    try {
        Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return $null -ne $conn
    } catch {
        return $false
    }
}

function Get-FreeBackendPort {
    foreach ($port in 8000..8010) {
        if (-not (Test-PortInUse $port)) {
            return $port
        }
    }
    return 8000
}

if (Test-Backend $backendPort) {
    Write-Host "AUTOMATA backend already responding on http://127.0.0.1:$backendPort"
} else {
    if (Test-PortInUse $backendPort) {
        $oldPort = $backendPort
        $backendPort = Get-FreeBackendPort
        $healthUrl = "http://127.0.0.1:$backendPort/health"
        Write-Warning "Port $oldPort is occupied but not serving AUTOMATA /health. Starting backend on $backendPort instead."
    }

    Write-Host "Starting AUTOMATA backend on http://127.0.0.1:$backendPort"
    Start-Process `
        -FilePath "powershell" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            "Set-Location '$backendDir'; uv run uvicorn api.server:app --reload --host 127.0.0.1 --port $backendPort"
        ) `
        -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if (Test-Backend $backendPort) {
            Write-Host "AUTOMATA backend ready."
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not (Test-Backend $backendPort)) {
        Write-Warning "Backend did not answer /health within 20 seconds. Vite will still start; check the backend terminal/logs."
    }
}

Set-Location $frontendDir
$env:VITE_API_BASE = "http://127.0.0.1:$backendPort"
$env:VITE_WS_BASE = "ws://127.0.0.1:$backendPort"
Write-Host "Frontend API base: $env:VITE_API_BASE"
npm run dev
