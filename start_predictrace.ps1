<#
.SYNOPSIS
    Brings the entire PredicTrace stack online: backend (FastAPI) + frontend (Vite).

.DESCRIPTION
    Idempotent -- safe to run repeatedly. Each setup step (venv, dataset,
    DB seed, model training, npm install) only runs if its output doesn't
    already exist; each server only starts if its port isn't already
    listening. A fresh clone gets a full first-time setup automatically;
    a machine that's already set up just gets both servers started.

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

# 6. Start backend (new window, stays open so you can see logs)
if (Test-PortListening $BackendPort) {
    Write-Warn "Backend already running on port $BackendPort -- leaving it alone."
} else {
    Write-Step "Starting backend on port $BackendPort..."
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$BackendApp'; & '$VenvPython' -m uvicorn main:app --host 127.0.0.1 --port $BackendPort"
    ) | Out-Null
}

# 7. Start frontend (new window, stays open so you can see logs)
if (Test-PortListening $FrontendPort) {
    Write-Warn "Frontend already running on port $FrontendPort -- leaving it alone."
} else {
    Write-Step "Starting frontend on port $FrontendPort..."
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$Frontend'; npm run dev"
    ) | Out-Null
}

# 8. Wait for both to actually come up before declaring victory
Write-Step "Waiting for both services to come online..."
$maxWaitSeconds = 45
$elapsed = 0
while ($elapsed -lt $maxWaitSeconds) {
    $backendUp = Test-PortListening $BackendPort
    $frontendUp = Test-PortListening $FrontendPort
    if ($backendUp -and $frontendUp) { break }
    Start-Sleep -Seconds 1
    $elapsed++
}

Write-Host ""
if (Test-PortListening $BackendPort) {
    Write-Host "Backend:  http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
} else {
    Write-Host "Backend did not come up within ${maxWaitSeconds}s -- check its window for errors." -ForegroundColor Red
}
if (Test-PortListening $FrontendPort) {
    Write-Host "Frontend: http://localhost:$FrontendPort" -ForegroundColor Green
} else {
    Write-Host "Frontend did not come up within ${maxWaitSeconds}s -- check its window for errors." -ForegroundColor Red
}
Write-Host ""
Write-Host "Both servers run in their own windows -- close those windows (or Ctrl+C in them) to stop them." -ForegroundColor DarkGray
