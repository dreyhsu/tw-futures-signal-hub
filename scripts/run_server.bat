@echo off
setlocal
cd /d "%~dp0.."
call conda run --no-capture-output -n tss twfsh serve --host 127.0.0.1 --port 8081
exit /b %ERRORLEVEL%
