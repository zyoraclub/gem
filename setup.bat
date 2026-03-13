@echo off
REM GEM Portal Automation - Setup Script for Windows
REM Run this once to set up the project

echo 🚀 Setting up GEM Portal Automation...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed!
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add to PATH" during installation!
    pause
    exit /b 1
)

REM Check if Node.js is installed
where node >nul 2>&1
if %errorlevel% neq 0 (
    REM Try common installation paths
    if exist "C:\Program Files\nodejs\node.exe" (
        set "PATH=%PATH%;C:\Program Files\nodejs"
        echo Found Node.js in Program Files, adding to PATH...
    ) else if exist "%LOCALAPPDATA%\Programs\nodejs\node.exe" (
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\nodejs"
        echo Found Node.js in LocalAppData, adding to PATH...
    ) else if exist "%APPDATA%\npm" (
        set "PATH=%PATH%;%APPDATA%\npm"
        echo Found npm in AppData, adding to PATH...
    ) else (
        echo ❌ Node.js is not found in PATH!
        echo.
        echo You installed Node.js but the terminal cannot find it.
        echo Try these steps:
        echo   1. CLOSE this window completely
        echo   2. Open a NEW Command Prompt or PowerShell
        echo   3. Run setup.bat again
        echo.
        echo If still not working, reinstall Node.js and check "Add to PATH"
        echo Download from: https://nodejs.org/
        pause
        exit /b 1
    )
)

REM Verify node works
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js found but not working. Please restart your terminal.
    pause
    exit /b 1
)

echo ✅ Python found
echo ✅ Node.js found
echo.

REM Setup Backend
echo 📦 Setting up Backend...
cd backend

REM Create virtual environment
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment and install dependencies
call venv\Scripts\activate.bat
echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    (
        echo # Gmail IMAP for OTP fetching
        echo GMAIL_EMAIL=
        echo GMAIL_APP_PASSWORD=
        echo.
        echo # Google OAuth ^(Sheets^)
        echo GOOGLE_CLIENT_ID=694469542353-lvcig3hqbpjv58274jqcsoht33uibuu0.apps.googleusercontent.com
        echo GOOGLE_CLIENT_SECRET=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
        echo GOOGLE_REDIRECT_URI=http://localhost:8000/api/oauth/callback
    ) > .env
)

cd ..

REM Setup Frontend
echo.
echo 📦 Setting up Frontend...
cd frontend

echo Installing Node.js dependencies...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\Program Files\nodejs\npm.cmd" (
        call "C:\Program Files\nodejs\npm.cmd" install
    ) else (
        call npm install
    )
) else (
    call npm install
)

cd ..

echo.
echo ✅ Setup complete!
echo.
echo To start the application, run: start.bat
echo.
echo Then open http://localhost:3000 in your browser
pause
