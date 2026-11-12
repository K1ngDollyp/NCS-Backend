# VITALIS demo launcher
# Usage (from the repo root, in PowerShell):
#   .\start-demo.ps1            -> fresh demo data, starts backend + frontend, opens the browser
#   .\start-demo.ps1 -KeepData  -> keep current data (e.g. after a rehearsal you want to continue)

param([switch]$KeepData)

$root = $PSScriptRoot
Set-Location $root

if (-not $KeepData) {
    Write-Host "Resetting demo data..." -ForegroundColor Cyan
    python -W ignore -m app.core.seed --reset
}

if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing frontend packages (first run only)..." -ForegroundColor Cyan
    Push-Location "$root\frontend"; npm install; Pop-Location
}

Write-Host "Starting VITALIS API on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; python -W ignore -m uvicorn app.main:app --port 8000"

Write-Host "Starting VITALIS web app on http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npx vite --port 5173 --host"

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173/login"
Write-Host "Ready. Demo password for every account: vitalis2026" -ForegroundColor Yellow
