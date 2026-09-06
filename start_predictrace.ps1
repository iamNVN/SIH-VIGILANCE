<#
.SYNOPSIS
    Brings the entire PredicTrace stack online: backend (FastAPI) + frontend (Vite).

.DESCRIPTION
    Idempotent -- safe to run repeatedly. Each setup step (venv, dataset,
    DB seed, model training, npm install) only runs if its output doesn't
    already exist; each server only starts if its port isn't already
    listening. A fresh clone gets a full first-time setup automatically;
    a machine that's already set up just gets both servers started.

    Both servers run as background jobs of THIS script, not separate
    windows -- their output is streamed into this one terminal (prefixed
    [backend]/[frontend]), and Ctrl+C here stops both. To cycle just one
    server on its own (e.g. after a backend-only code change), use
    restart_backend.ps1 or restart_frontend.ps1 instead. To stop everything
    from a different terminal without Ctrl+C'ing this one, use
    stop_predictrace.ps1.

    Backend listens on 8001, not FastAPI's default 8000 -- an orphaned
    process from an earlier session got stuck on 8000 on this machine and
    couldn't be killed through any available channel (see PROGRESS_LOG.md).
    frontend/vite.config.js's dev proxy already points at 8001. If you're on
    a clean machine and want 8000 back, change $BackendPort below AND the
    proxy target in vite.config.js.

.PARAMETER Fresh
    Force a full regenerate: re-run the synthetic data generator, reseed the
    database, and retrain both models even if artifacts already exist. Use
    after changing the generator, the feature pipeline, or the model code.

.EXAMPLE
    .\start_predictrace.ps1
    .\start_predictrace.ps1 -Fresh
#>

param(
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$BackendApp = Join-Path $Backend "app"
$Frontend = Join-Path $Root "frontend"
$VenvPython = Join-Path $Backend "venv\Scripts\python.exe"
$BackendPort = 8001
$FrontendPort = 5173

function Write-Step($msg) { Write-Host ">> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   $msg" -ForegroundColor Yellow }

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host "=== PredicTrace startup ===" -ForegroundColor Magenta

# 1. Backend virtualenv
if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating backend virtualenv..."
    python -m venv (Join-Path $Backend "venv")
    & $VenvPython -m pip install --upgrade pip | Out-Null
    & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")
    Write-Ok "Virtualenv ready."
} else {
    Write-Ok "Backend virtualenv already exists."
}

# 2. Synthetic dataset
$GeneratedCsv = Join-Path $Root "data\output\complaints.csv"
if ($Fresh -or -not (Test-Path $GeneratedCsv)) {
    Write-Step "Generating synthetic dataset..."
    & $VenvPython (Join-Path $Root "data\generator\generate_synthetic_data.py") `
        --config (Join-Path $Root "data\generator\rings_config.yaml") `
        --outdir (Join-Path $Root "data\output") --seed 42
    Write-Ok "Dataset generated."
} else {
    Write-Ok "Dataset already generated (use -Fresh to regenerate)."
}

# 3. Seed the database
$DbPath = Join-Path $Backend "predictrace.db"
if ($Fresh -or -not (Test-Path $DbPath)) {
    Write-Step "Seeding database..."
    & $VenvPython (Join-Path $Root "scripts\seed_db.py") --data-dir (Join-Path $Root "data\output") --reset
    Write-Ok "Database seeded."
} else {
    Write-Ok "Database already seeded (use -Fresh to reseed)."
}

# 4. Train + calibrate both models
$ModelPath = Join-Path $BackendApp "ml\artifacts\advanced_calibrated.joblib"
if ($Fresh -or -not (Test-Path $ModelPath)) {
    Write-Step "Training + calibrating models (this takes a minute or two)..."
    if ($Fresh) {
        Remove-Item -Force -ErrorAction SilentlyContinue `
            (Join-Path $BackendApp "ml\artifacts\features_train.csv"), `
            (Join-Path $BackendApp "ml\artifacts\features_test.csv")
    }
    Push-Location $BackendApp
    & $VenvPython -m ml.train
    & $VenvPython -m ml.evaluate
    Pop-Location
    Write-Ok "Models trained and evaluated."
} else {
    Write-Ok "Models already trained (use -Fresh to retrain)."
}

# 5. Frontend dependencies
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Step "Installing frontend dependencies (npm install)..."
    Push-Location $Frontend
    npm install
    Pop-Location
    Write-Ok "Frontend dependencies installed."
} else {
    Write-Ok "Frontend dependencies already installed."
}

function Stop-PortProcess([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

# 6. Start backend + frontend as background jobs of THIS session, not new
# windows -- both servers' output streams into this one terminal, prefixed
# so you can tell them apart. Ctrl+C here stops both (see the finally block
# below); closing this one window is the only "close all" you need.
if (Test-PortListening $BackendPort) {
    Write-Warn "Backend already running on port $BackendPort -- leaving it alone. Use restart_backend.ps1 to cycle it."
    $backendJob = $null
} else {
    Write-Step "Starting backend on port $BackendPort..."
    $backendJob = Start-Job -Name "PredicTrace-Backend" -ScriptBlock {
        param($BackendApp, $VenvPython, $BackendPort)
        Set-Location $BackendApp
        & $VenvPython -m uvicorn main:app --host 127.0.0.1 --port $BackendPort 2>&1
    } -ArgumentList $BackendApp, $VenvPython, $BackendPort
}

if (Test-PortListening $FrontendPort) {
    Write-Warn "Frontend already running on port $FrontendPort -- leaving it alone. Use restart_frontend.ps1 to cycle it."
    $frontendJob = $null
} else {
    Write-Step "Starting frontend on port $FrontendPort..."
    $frontendJob = Start-Job -Name "PredicTrace-Frontend" -ScriptBlock {
        param($Frontend)
        Set-Location $Frontend
        npm run dev 2>&1
    } -ArgumentList $Frontend
    # Vite's startup banner uses a UTF-8 arrow character that renders as
    # "Γ₧£" once piped through a background job's captured output -- known,
    # purely cosmetic (the URL/port text around it is unaffected), not
    # worth chasing further; ignore it.
}

# 7. Wait for both to actually come up before declaring victory
Write-Step "Waiting for both services to come online..."
$maxWaitSeconds = 45
$elapsed = 0
while ($elapsed -lt $maxWaitSeconds) {
    if ((Test-PortListening $BackendPort) -and (Test-PortListening $FrontendPort)) { break }
    Start-Sleep -Seconds 1
    $elapsed++
}

Write-Host ""
if (Test-PortListening $BackendPort) {
    Write-Host "Backend:  http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
} else {
    Write-Host "Backend did not come up within ${maxWaitSeconds}s -- check the [backend] lines below for errors." -ForegroundColor Red
}
if (Test-PortListening $FrontendPort) {
    Write-Host "Frontend: http://localhost:$FrontendPort" -ForegroundColor Green
} else {
    Write-Host "Frontend did not come up within ${maxWaitSeconds}s -- check the [frontend] lines below for errors." -ForegroundColor Red
}
Write-Host ""
Write-Host "Both servers are running in THIS window. Press Ctrl+C to stop both." -ForegroundColor DarkGray
Write-Host "(To restart just one without the other, use restart_backend.ps1 / restart_frontend.ps1 in a separate terminal.)" -ForegroundColor DarkGray
Write-Host ""

$jobs = @($backendJob, $frontendJob) | Where-Object { $_ -ne $null }
try {
    # Streams both jobs' output into this one console, live, prefixed by
    # source, until Ctrl+C -- that's the whole point of using jobs instead
    # of Start-Process's separate windows.
    while ($jobs | Where-Object { $_.State -eq "Running" }) {
        if ($backendJob) { Receive-Job $backendJob | ForEach-Object { Write-Host "[backend]  $_" -ForegroundColor Cyan } }
        if ($frontendJob) { Receive-Job $frontendJob | ForEach-Object { Write-Host "[frontend] $_" -ForegroundColor Yellow } }
        Start-Sleep -Milliseconds 300
    }
    Write-Warn "A job exited on its own -- check the output above."
} finally {
    Write-Host ""
    Write-Step "Stopping both servers..."
    if ($jobs) { Stop-Job $jobs -ErrorAction SilentlyContinue; Remove-Job $jobs -Force -ErrorAction SilentlyContinue }
    # Belt-and-suspenders: Stop-Job kills the job's own process, but not
    # reliably every child it spawned (uvicorn/node) on Windows -- a stuck
    # port from an orphaned child has bitten this project before (see
    # PROGRESS_LOG.md), so kill by port too, not just by job.
    Stop-PortProcess $BackendPort
    Stop-PortProcess $FrontendPort
    Write-Ok "Stopped."
}
