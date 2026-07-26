$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$healthUrl = "http://127.0.0.1:8000/health"

function Test-Backend {
    try {
        Invoke-RestMethod $healthUrl -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (Test-Backend) {
    Write-Host "AUTOMATA backend already responding on http://127.0.0.1:8000"
} else {
    Write-Host "Starting AUTOMATA backend on http://127.0.0.1:8000"
    Start-Process `
        -FilePath "powershell" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            "Set-Location '$backendDir'; uv run uvicorn api.server:app --reload --host 127.0.0.1 --port 8000"
        ) `
        -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if (Test-Backend) {
            Write-Host "AUTOMATA backend ready."
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not (Test-Backend)) {
        Write-Warning "Backend did not answer /health within 20 seconds. Vite will still start; check the backend terminal/logs."
    }
}

Set-Location $frontendDir
npm run dev
