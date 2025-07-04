@echo off
title Auto Translator - Installer

echo ================================================
echo          Auto Translator - Installer
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

:: Change to app directory
echo [1/3] Changing to app directory...
cd app

:: Install required packages
echo [2/3] Installing required packages...
uv sync

:: Return to original directory
cd ..

:: Installation complete
echo [3/3] Installation completed!
echo.
echo ========================================================
echo      Installation complete!
echo      Run the run.bat file to start the program.
echo ========================================================
echo.