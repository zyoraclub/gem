@echo off
REM GEM Portal Automation - Start Script for Windows
REM Run this to start both backend and frontend

echo 🚀 Starting GEM Portal Automation...
echo.

REM Start Backend in new window
echo Starting Backend on port 8000...
start "GEM Backend" cmd /k "cd backend && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM Wait for backend to start
timeout /t 5 /nobreak >nul

REM Start Frontend in new window
echo Starting Frontend on port 3000...
start "GEM Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ✅ Application starting!
echo.
echo 📊 Dashboard: http://localhost:3000
echo 🔧 API Docs:  http://localhost:8000/docs
echo.
echo Two new terminal windows have opened for Backend and Frontend.
echo Close those windows to stop the servers.
echo.

REM Open browser after a delay
timeout /t 8 /nobreak >nul
start http://localhost:3000

pause
