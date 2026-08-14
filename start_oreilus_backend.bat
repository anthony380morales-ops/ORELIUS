@echo off
REM O.R.E.I.L.U.S. Backend Startup Script
REM Starts the backend server with automation scheduler

echo ========================================
echo Starting O.R.E.I.L.U.S. Backend System
echo ========================================
echo.

cd /d "C:\Users\Victoria\oreilus\backend"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start the FastAPI server
echo Starting FastAPI server with automation...
echo Backend will run at: http://localhost:8000
echo Automation scheduled: 7 AM (Content) and 8 AM (Intel) PST
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
