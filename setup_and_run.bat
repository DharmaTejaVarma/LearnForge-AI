@echo off
title LearnForge AI — One-Click Setup and Launch
echo ======================================================================
echo    LearnForge AI — Interactive AI Learning Platform
echo    Automated Setup & Dual-Server Launcher
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not detected in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [2/4] Initializing Python virtual environment...
if not exist "backend\venv\Scripts\python.exe" (
    echo Creating virtual environment at backend\venv...
    python -m venv backend\venv
    echo Installing Python dependencies from backend\requirements.txt...
    backend\venv\Scripts\python.exe -m pip install --upgrade pip
    backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
) else (
    echo Virtual environment verified at backend\venv.
)

echo [3/4] Checking Frontend dependencies...
where npm >nul 2>&1
if errorlevel 1 (
    echo [NOTE] npm/Node.js not detected in PATH.
    echo The backend will serve the pre-built frontend distribution directly.
) else (
    if not exist "frontend\node_modules" (
        echo Installing frontend dependencies from frontend\package.json...
        cd frontend
        call npm install
        cd ..
    ) else (
        echo Frontend packages verified at frontend\node_modules.
    )
)

echo.
echo [4/4] Launching LearnForge AI Services...
echo  - Backend API:    http://localhost:8000
echo  - Interactive UI: http://localhost:5173
echo.
python run_servers.py
pause
