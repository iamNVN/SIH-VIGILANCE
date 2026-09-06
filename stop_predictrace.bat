@echo off
REM Double-click this to stop both the backend and frontend -- "close all."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_predictrace.ps1" %*
pause
