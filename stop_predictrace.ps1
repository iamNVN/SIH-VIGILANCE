<#
.SYNOPSIS
    Stops both the PredicTrace backend and frontend, however they were
    started (this script, restart_backend.ps1/restart_frontend.ps1, or
    manually) -- "close all" in one command.

.DESCRIPTION
    Finds whatever process is actually listening on the backend/frontend
    ports and force-stops it, rather than trying to track PIDs or job
    handles across scripts/terminals -- the port is the one thing that's
    always true regardless of how the process was launched.

.EXAMPLE
    .\stop_predictrace.ps1
#>

$BackendPort = 8001
$FrontendPort = 5173

function Stop-PortProcess([int]$Port, [string]$Label) {
    $procIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $procIds) {
        Write-Host "   $Label -- nothing listening on port $Port." -ForegroundColor DarkGray
        return
    }
    foreach ($processId in $procIds) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Write-Host "   $Label -- stopped process $processId (port $Port)." -ForegroundColor Green
    }
}

Write-Host "=== Stopping PredicTrace ===" -ForegroundColor Magenta
Stop-PortProcess $BackendPort "Backend"
Stop-PortProcess $FrontendPort "Frontend"

# Also clean up any leftover PredicTrace-* background jobs from
# start_predictrace.ps1, if this is run in the same PowerShell session.
Get-Job -Name "PredicTrace-*" -ErrorAction SilentlyContinue | Stop-Job -ErrorAction SilentlyContinue
Get-Job -Name "PredicTrace-*" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue

Write-Host "Done." -ForegroundColor Green
