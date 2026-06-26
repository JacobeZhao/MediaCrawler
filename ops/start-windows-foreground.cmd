@echo off
setlocal
cd /d "%~dp0\.."
if "%PORT%"=="" set PORT=8088
if "%HOST%"=="" set HOST=0.0.0.0
if "%XHS_LOG_DIR%"=="" set XHS_LOG_DIR=logs
if not exist "%XHS_LOG_DIR%" mkdir "%XHS_LOG_DIR%"
".venv\Scripts\python.exe" "start_xhs_service.py" --host %HOST% --port %PORT% --headless >> "%XHS_LOG_DIR%\service-%PORT%.log" 2>> "%XHS_LOG_DIR%\service-%PORT%.err.log"
