@echo off
setlocal
cd /d "%~dp0.."
if not exist logs mkdir logs
echo [TWFSH] Starting quote updater. Keep this window open.
echo [TWFSH] Schedule: weekdays, every 5 minutes from 08:45 through 13:45.
echo [TWFSH] Status is also written to logs\quotes.log.
set "condaExe=%USERPROFILE%\anaconda3\Scripts\conda.exe"
if not exist "%condaExe%" set "condaExe=conda"
call "%condaExe%" run --no-capture-output -n tss twfsh refresh-quotes --loop --start 08:45 --end 13:45 --interval 5
set "quoteExit=%ERRORLEVEL%"
if "%quoteExit%"=="0" (
  echo [TWFSH] Quote updater finished normally.
) else (
  echo [TWFSH] Quote updater stopped with error code %quoteExit%.
)
exit /b %quoteExit%
