@echo off
REM Double-click this to bring PredicTrace online.
REM Just calls start_predictrace.ps1 with the execution-policy prompt bypassed
REM for this one run (does not change your machine's PowerShell policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_predictrace.ps1" %*
pause
