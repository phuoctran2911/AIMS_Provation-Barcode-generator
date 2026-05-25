@echo off
setlocal
TITLE Provation Barcode Generator
cd /d "%~dp0"

echo ==========================================
echo Provation Barcode Generator - Windows
 echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: Python is not installed or not added to PATH.
    echo Install Python from https://www.python.org/downloads/windows/
    echo During install, check: Add Python to PATH
    pause
    exit /b 1
)

REM Create virtual environment once
IF NOT EXIST ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv .venv
    IF ERRORLEVEL 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

REM Install dependencies once
python -c "import fastapi, uvicorn, openai" >nul 2>&1
IF ERRORLEVEL 1 (
    echo Installing required packages. This may take a few minutes the first time...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo ERROR: Package installation failed.
        pause
        exit /b 1
    )
)

REM Create .env template if missing
IF NOT EXIST ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env file.
    echo Open .env and paste your OpenAI API key if you want AI extraction.
    echo Example: OPENAI_API_KEY=sk-yourkeyhere
    echo.
)

echo Starting server...
echo Leave this window open while using the app.
echo Close this window to stop the app.
echo.
start "" "http://127.0.0.1:8000"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

echo.
echo App stopped.
pause
