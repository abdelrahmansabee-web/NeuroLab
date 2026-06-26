@echo off
cd /d "%~dp0"
echo Stopping old serve processes...
taskkill /f /im node.exe 2>nul
timeout /t 2 /nobreak >nul
echo Starting frontend on port 3000...
npx serve -s build -l 3000 --no-clipboard
pause
