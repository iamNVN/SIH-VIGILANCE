@echo off
REM Double-click this to restart ONLY the backend, leaving the frontend alone.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_backend.ps1" %*
pause
