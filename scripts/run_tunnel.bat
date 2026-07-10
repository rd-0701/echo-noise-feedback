@echo off
REM Echo一键启动（公网访问）- 调用Python脚本

cd /d "%~dp0.."
python scripts\start_with_popup.py
pause