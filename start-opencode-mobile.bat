@echo off
set OPENCODE_SERVER_PASSWORD=
set OPENCODE_SERVER_USERNAME=
start "OpenCode Server" cmd /k "cd /d ""D:\Thesis app\NeuroLab"" & set OPENCODE_SERVER_PASSWORD= & set OPENCODE_SERVER_USERNAME= & opencode serve --hostname 0.0.0.0 --port 4096"
timeout /t 8 /nobreak > nul
start "Mobile Proxy" cmd /k "cd /d ""D:\Thesis app\NeuroLab"" & node mobile-proxy.js"
timeout /t 5 /nobreak > nul
echo.
echo OpenCode Server and Mobile Proxy started.
echo Wait 25 seconds, then run Show-OpenCode-URL.bat to get the current URL.
pause
