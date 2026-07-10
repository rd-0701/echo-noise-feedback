@echo off
REM Echo - One-click Launcher (Server + Tunnel + QR Code)
REM Run this to start everything with QR code for phone access
cd /d "%~dp0\.."
"%~dp0..\venv\Scripts\python.exe" scripts\start.py
pause
