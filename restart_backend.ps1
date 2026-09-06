<#
.SYNOPSIS
    Restarts ONLY the backend (FastAPI/uvicorn) -- leaves the frontend
    running untouched. Runs in the foreground of this terminal so you can
    watch its logs directly (e.g. to confirm a code change picked up).

.DESCRIPTION
    Backend code changes need a real process restart (no --reload), unlike
    frontend changes which Vite hot-reloads on its own -- this is the
    "I only changed backend/app/*.py, I don't want to touch the frontend"
    shortcut, instead of re-running the full start_predictrace.ps1 (which
    would also re-check venv/dataset/seed/model/npm state).

.EXAMPLE
    .\restart_backend.ps1
#>

$Root = $PSScriptRoot
$BackendApp = Join-Path $Root "backend\app"
$VenvPython = Join-Path $Root "backend\venv\Scripts\python.exe"
$BackendPort = 8001

$procIds = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($procIds) {
    Write-Host ">> Stopping existing backend (port $BackendPort)..." -ForegroundColor Cyan
    foreach ($processId in $procIds) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
} else {
    Write-Host ">> No backend currently running on port $BackendPort." -ForegroundColor DarkGray
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Backend virtualenv not found at $VenvPython -- run start_predictrace.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host ">> Starting backend on port $BackendPort (Ctrl+C to stop)..." -ForegroundColor Cyan
Set-Location $BackendApp
& $VenvPython -m uvicorn main:app --host 127.0.0.1 --port $BackendPort
