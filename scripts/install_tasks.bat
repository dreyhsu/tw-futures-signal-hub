@echo off
setlocal
cd /d "%~dp0.."
schtasks /Create /F /TN "TwFuturesSignalHubDaily" /SC DAILY /ST 18:10 /TR "\"%CD%\scripts\run_daily.bat\"" /RL LIMITED
schtasks /Create /F /TN "TwFuturesSignalHubQuotes" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:45 /TR "\"%CD%\scripts\run_quotes.bat\"" /RL LIMITED
