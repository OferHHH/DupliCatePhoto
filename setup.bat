@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=%LOCALAPPDATA%\PhotoDuplicatorApp\venv"

echo ============================================
echo   PhotoDuplicatorApp - First-Time Setup
echo ============================================
echo.
echo Virtual environment will be created at:
echo   %VENV_DIR%
echo (kept out of OneDrive to avoid file-lock issues)
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Download Python 3.10+ from https://www.python.org/downloads/
    echo During installation, CHECK the box "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist "%LOCALAPPDATA%\PhotoDuplicatorApp" mkdir "%LOCALAPPDATA%\PhotoDuplicatorApp"

echo Creating virtual environment...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo.
echo Installing dependencies (this may take a minute)...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Setup complete! Double-click run.bat to
echo   start PhotoDuplicatorApp.
echo ============================================
pause
