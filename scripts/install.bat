@echo off
REM Echo - Dependency Installer
cd /d "%~dp0\.."

set "PY=%~dp0..\venv\Scripts\python.exe"

if exist "%PY%" (
    echo venv already exists, upgrading pip ...
) else (
    echo [1/3] Creating venv ...
    python -m venv venv
    if not exist "%PY%" (
        echo FAILED: venv creation. Is Python 3.11+ in PATH?
        pause
        exit /b 1
    )
)

echo [2/3] Upgrading pip ...
"%PY%" -m pip install --upgrade pip

echo [3/3] Installing dependencies ...
"%PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo.
    echo FAILED: Some packages failed to install. Check network and retry.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Install complete!
echo  Start server:  scripts\run.bat
echo  Access token:  data\auth_token.txt
echo ========================================
pause
