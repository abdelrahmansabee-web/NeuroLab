@echo off
powershell -NoProfile -Command "try { $line = (Select-String -Path 'C:\Users\acer\AppData\Local\Temp\cloudflared-proxy.log' -Pattern 'https://[^\s]+trycloudflare\.com' | Select-Object -Last 1).Line; if ($line) { $url = [regex]::Match($line, 'https://[^\s]+trycloudflare\.com').Value; Write-Output \"OpenCode Mobile URL: $url\" } else { Write-Output 'No tunnel URL found yet. Wait and try again.' } } catch { Write-Output 'No tunnel URL found yet.' }"
pause
