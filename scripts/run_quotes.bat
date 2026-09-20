@echo off
setlocal
cd /d "%~dp0.."
if not exist logs mkdir logs
call conda run -n tss twfsh refresh-quotes --loop --start 08:45 --end 13:45 --interval 5 >> logs\quotes.log 2>&1
exit /b %ERRORLEVEL%
