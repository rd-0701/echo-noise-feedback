@echo off
REM Echo - Local Server Launcher (LAN access only)
cd /d "%~dp0\.."

set "PY=%~dp0..\venv\Scripts\python.exe"

if not exist "%PY%" (
    echo venv NOT found. Run scripts\install.bat first!
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

echo Starting Echo server (LAN only) ...
echo Access token: see data\auth_token.txt
echo Browser: http://127.0.0.1:8000
echo For remote access (4G/5G): run scripts\run-with-tunnel.bat instead.
echo.

if /i "%1"=="tray" (
    start "" "%~dp0..\venv\Scripts\pythonw.exe" -m backend.scripts_tray
    exit /b 0
)

"%PY%" -m backend.main

echo.
echo Server stopped. Press any key to close.
pause >nul
