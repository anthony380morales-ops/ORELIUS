@echo off
REM O.R.E.I.L.U.S. Dashboard Launcher
REM Opens the frontend dashboard in your browser

echo ============================================
echo Starting O.R.E.I.L.U.S. Dashboard
echo ============================================
echo.

cd /d "C:\Users\Victoria\oreilus\frontend"

echo Checking if backend is running...
curl -s http://localhost:8000 >nul 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Backend is not running!
    echo Starting backend first...
    wscript.exe "C:\Users\Victoria\oreilus\start_oreilus_hidden.vbs"
    echo Waiting for backend to start...
    timeout /t 5 /nobreak >nul
)

echo.
echo Starting frontend dashboard...
echo Dashboard will open at: http://localhost:3000
echo.
echo Keep this window open while using the dashboard.
echo Close this window to stop the dashboard.
echo.

start http://localhost:3000
npm run dev
