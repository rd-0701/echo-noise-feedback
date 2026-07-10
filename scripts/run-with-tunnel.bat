@echo off
REM Echo - Server + Cloudflare Tunnel Launcher (Remote access from 4G/5G)
cd /d "%~dp0\.."

set "PY=%~dp0..\venv\Scripts\python.exe"
set "CF=%~dp0..\tunnel\cloudflared.exe"
set "LOG=%~dp0..\tunnel\tunnel.log"

if not exist "%PY%" (
    echo venv NOT found. Run scripts\install.bat first!
    pause
    exit /b 1
)

if not exist "%CF%" (
    echo cloudflared.exe NOT found in tunnel\ directory!
    echo Download from: https://github.com/cloudflare/cloudflared/releases/latest
    echo File: cloudflared-windows-amd64.exe - rename to cloudflared.exe
    pause
    exit /b 1
)

REM Check if port 8000 is already in use
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo Port 8000 is already in use!
    echo Close the previous Echo instance first.
    pause
    exit /b 1
)

echo ============================================================
echo  Echo - Server + Cloudflare Tunnel
echo ============================================================
echo  Local:  http://127.0.0.1:8000
echo  Token:  see data\auth_token.txt
echo.
echo  Tunnel is starting... Public URL will appear below:
echo  (Look for "https://xxx.trycloudflare.com")
echo ============================================================
echo.

REM Start Echo server in a new background window
start "Echo Server" "%PY%" -m backend.main

REM Wait for server to be ready
echo Waiting for server to be ready ...
:WAIT_LOOP
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto :WAIT_LOOP
echo Server is up. Starting Cloudflare Tunnel ...
echo.

REM Start tunnel in foreground (Ctrl+C to stop both)
"%CF%" tunnel --url http://localhost:8000 --no-autoupdate 2>&1 | tee "%LOG%"

REM When tunnel exits, also kill the server window
echo.
echo Tunnel stopped. Killing Echo server ...
taskkill /FI "WindowTitle eq Echo Server*" /F >nul 2>&1
echo Done. Press any key to close.
pause >nul
