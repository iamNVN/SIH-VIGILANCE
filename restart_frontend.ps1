<#
.SYNOPSIS
    Restarts ONLY the frontend (Vite dev server) -- leaves the backend
    running untouched. Runs in the foreground of this terminal so you can
    watch its logs directly.

.DESCRIPTION
    Vite already hot-reloads most frontend edits on its own, so this is
    mostly for when the dev server itself is stuck/crashed, a dependency
    changed (package.json), or vite.config.js was edited -- the
    "I don't want to touch the backend" shortcut, instead of re-running
    the full start_predictrace.ps1.

.EXAMPLE
    .\restart_frontend.ps1
#>

$Root = $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$FrontendPort = 5173

$procIds = Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($procIds) {
    Write-Host ">> Stopping existing frontend (port $FrontendPort)..." -ForegroundColor Cyan
    foreach ($processId in $procIds) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
} else {
    Write-Host ">> No frontend currently running on port $FrontendPort." -ForegroundColor DarkGray
}

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "Frontend dependencies not installed -- run start_predictrace.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host ">> Starting frontend on port $FrontendPort (Ctrl+C to stop)..." -ForegroundColor Cyan
Set-Location $Frontend
npm run dev
