@echo off
title Auto Translator - Installer

echo ================================================
echo          Auto Translator - Run
echo ================================================
echo.

:: Check uv installation
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] uv package manager is not installed.
    echo.
    echo Please install uv first and then run this again.
    echo Installation method:
    echo   Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    echo For more information, visit https://github.com/astral-sh/uv
    echo.
    pause
    exit /b 1
) else (
    echo [INFO] uv package manager is installed.
)

call update.bat

:: Change to app directory
echo [1/3] Changing to app directory...
cd app

:: Activate virtual environment
echo [2/3] Activating virtual environment...
call .venv\Scripts\activate.bat

:: Run the program
echo [3/3] Running the program...
python run_flet_gui.py

:: Deactivate virtual environment
echo [4/4] Deactivating virtual environment...
call .venv\Scripts\deactivate.bat

:: Return to original directory
cd ..

echo.
echo Program has been terminated.
pause
