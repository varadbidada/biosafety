param(
    [switch]$NoFrontend,
    [switch]$NoBackend,
    [switch]$Install,
    [string]$ApiPort = "8001",
    [string]$WebPort = "5174"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DengueCast India - Development Server " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($Install) {
    Write-Host "[1/2] Installing frontend dependencies..." -ForegroundColor Green
    Push-Location "$Root\web"
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed"; exit 1 }
    Pop-Location

    Write-Host "[2/2] Installing backend dependencies..." -ForegroundColor Green
    pip install -r "$Root\requirements.txt"
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }

    Write-Host "`nDone! Run this script again without -Install to start." -ForegroundColor Green
    exit 0
}

if (-not $NoBackend) {
    Write-Host "Starting backend (API) on port $ApiPort ..." -ForegroundColor Yellow
    $backendJob = Start-Job -ScriptBlock {
        param($r, $p)
        Set-Location "$r\api"
        python -m uvicorn main:app --reload --host 0.0.0.0 --port $p
    } -ArgumentList $Root, $ApiPort
    Write-Host "  → API at http://localhost:$ApiPort" -ForegroundColor Green
    Write-Host "  → Docs at http://localhost:$ApiPort/docs" -ForegroundColor Green
}

if (-not $NoFrontend) {
    Write-Host "Starting frontend (Vite) on port $WebPort ..." -ForegroundColor Yellow
    $frontendJob = Start-Job -ScriptBlock {
        param($r, $p)
        Set-Location "$r\web"
        npm run dev -- --port $p
    } -ArgumentList $Root, $WebPort
    Write-Host "  → Frontend at http://localhost:$WebPort" -ForegroundColor Green
}

Write-Host ""
Write-Host "Press Ctrl+C to stop all servers." -ForegroundColor Magenta

try {
    while ($true) {
        if (-not $NoBackend) {
            Receive-Job $backendJob -ErrorAction SilentlyContinue
        }
        if (-not $NoFrontend) {
            Receive-Job $frontendJob -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    if (-not $NoBackend) { Stop-Job $backendJob -ErrorAction SilentlyContinue; Remove-Job $backendJob -ErrorAction SilentlyContinue }
    if (-not $NoFrontend) { Stop-Job $frontendJob -ErrorAction SilentlyContinue; Remove-Job $frontendJob -ErrorAction SilentlyContinue }
    Write-Host "Done." -ForegroundColor Green
}
