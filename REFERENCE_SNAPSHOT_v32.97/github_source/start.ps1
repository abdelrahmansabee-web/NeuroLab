Write-Host "=== NeuroLab - Starting Services ===" -ForegroundColor Cyan
Write-Host ""

# Rebuild frontend so iPad always gets latest bundle
Write-Host "[Build]    npm run build ..." -ForegroundColor Yellow
Push-Location "frontend"
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Build]    FAILED — fix errors above" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "[Build]    OK" -ForegroundColor Green
Write-Host ""

# Detect local IP for network access
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -ne 'Loopback Pseudo-Interface 1' -and $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1).IPAddress

# Start backend
$be = Start-Process -NoNewWindow -PassThru -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "backend"
Write-Host "[Backend]  $(If ($be.Id) { 'Started' } Else { 'Failed' }) (PID $($be.Id))" -ForegroundColor Green

# Start frontend
$fe = Start-Process -NoNewWindow -PassThru -FilePath "npx" -ArgumentList "serve -s build -l 3000" -WorkingDirectory "frontend"
Write-Host "[Frontend] $(If ($fe.Id) { 'Started' } Else { 'Failed' }) (PID $($fe.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "╔═══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Local:   http://localhost:3000           ║" -ForegroundColor White
Write-Host "║  Network: http://$($ip):3000  " -ForegroundColor White
Write-Host "║  API:     http://$($ip):8000             ║" -ForegroundColor White
Write-Host "╚═══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║  iPad: Open Safari → http://$($ip):3000  ║" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

Write-Host "Press any key to stop both services..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Stop-Process -Id $be.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $fe.Id -Force -ErrorAction SilentlyContinue
Write-Host "Services stopped." -ForegroundColor Green
