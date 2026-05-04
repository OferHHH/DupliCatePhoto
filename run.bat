@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=%LOCALAPPDATA%\PhotoDuplicatorApp\venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Virtual environment not found. Running first-time setup...
    call setup.bat
    if errorlevel 1 exit /b 1
)

"%VENV_DIR%\Scripts\python.exe" main.py
if errorlevel 1 pause
