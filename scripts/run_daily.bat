@echo off
setlocal
cd /d "%~dp0.."
if not exist logs mkdir logs
call conda run -n tss twfsh run-daily >> logs\daily.log 2>&1
exit /b %ERRORLEVEL%
