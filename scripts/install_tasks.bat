@echo off
setlocal
cd /d "%~dp0.."
schtasks /Create /F /TN "TwFuturesSignalHubDaily" /SC DAILY /ST 18:10 /TR "\"%CD%\scripts\run_daily.bat\"" /RL LIMITED
schtasks /Create /F /TN "TwFuturesSignalHubQuotes" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:45 /TR "\"%CD%\scripts\run_quotes.bat\"" /RL LIMITED
powershell -NoProfile -Command "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable; Set-ScheduledTask -TaskName 'TwFuturesSignalHubQuotes' -Settings $settings | Out-Null"
echo Starting the quote task now so an installation after 08:45 does not wait until tomorrow.
schtasks /Run /TN "TwFuturesSignalHubQuotes"
pause
