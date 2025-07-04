@echo off
title Auto Translator - Update

echo ================================================
echo          Auto Translator - Update
echo ================================================
echo.

:: Change to app directory
echo [1/5] Changing to app directory...
cd app

:: Get the latest code from GitHub
echo [2/5] Getting the latest code from GitHub...
if not exist ".git" (
    echo [!] Git repository not found. Initializing repository...
    git init
    git remote add origin https://github.com/kunho-park/auto-translate.git
)

git pull https://github.com/kunho-park/auto-translate.git main 2>NUL
if %ERRORLEVEL% == 0 goto :skip_reset

echo [!] Pull failed, resetting and trying again...
git reset --hard
git clean -fd
git pull https://github.com/kunho-park/auto-translate.git main

:skip_reset

:: Clean cache
echo [3/5] Cleaning cache...
if exist "__pycache__" rmdir /s /q "__pycache__"

:: Update required packages
echo [4/5] Updating required packages...
uv sync

:: Return to original directory
cd ..

:: Run installer to ensure all dependencies are properly set up
echo [5/5] Running installer to ensure all dependencies are properly set up...
call installer.bat