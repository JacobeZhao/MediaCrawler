@echo off
setlocal
cd /d "%~dp0\.."
if "%XHS_LOG_DIR%"=="" set XHS_LOG_DIR=logs
if not exist "%XHS_LOG_DIR%" mkdir "%XHS_LOG_DIR%"
".venv\Scripts\python.exe" "start_xhs_service.py" --headless >> "%XHS_LOG_DIR%\service-foreground.log" 2>> "%XHS_LOG_DIR%\service-foreground.err.log"
