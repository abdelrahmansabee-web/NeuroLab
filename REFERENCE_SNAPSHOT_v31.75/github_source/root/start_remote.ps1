Write-Host "=== NeuroLab - Remote Access ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "[Build]    npm run build ..." -ForegroundColor Yellow
Push-Location "frontend"
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Build]    FAILED" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "[Build]    OK" -ForegroundColor Green
Write-Host ""

# Start backend (single port serves both API + frontend)
$be = Start-Process -NoNewWindow -PassThru -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "backend"
Write-Host "[Backend] Started (PID $($be.Id))  ->  http://localhost:8000" -ForegroundColor Green

# Try to auto-start ngrok if available
$ngrok = Get-Command "ngrok.exe" -ErrorAction SilentlyContinue
if (-not $ngrok) {
    $ngrok = Get-Command "ngrok" -ErrorAction SilentlyContinue
}

if ($ngrok) {
    Start-Process -NoNewWindow -PassThru -FilePath $ngrok.Source -ArgumentList "http 8000 --log=stdout"
    Write-Host "[ngrok]   Started" -ForegroundColor Green
    Write-Host ""
    Write-Host "Open https://dashboard.ngrok.com to find your URL" -ForegroundColor Cyan
    Write-Host "Or check the terminal that opened with ngrok." -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "ngrok not found. Download from: https://ngrok.com/download" -ForegroundColor Yellow
    Write-Host "After installing, run in a NEW terminal: ngrok http 8000" -ForegroundColor White
}

Write-Host ""
Write-Host "From iPad anywhere in the world:" -ForegroundColor Magenta
Write-Host "Open the ngrok URL (looks like https://xxxx.ngrok-free.app)" -ForegroundColor White
Write-Host ""

Write-Host "Press any key to stop..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Stop-Process -Id $be.Id -Force -ErrorAction SilentlyContinue
Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Services stopped." -ForegroundColor Green
