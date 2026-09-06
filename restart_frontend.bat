@echo off
REM Double-click this to restart ONLY the frontend, leaving the backend alone.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_frontend.ps1" %*
pause
