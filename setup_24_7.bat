@echo off
REM Quick Setup for O.R.E.I.L.U.S. 24/7 Operation
REM This script imports the Task Scheduler configuration

echo ============================================================
echo O.R.E.I.L.U.S. 24/7 Background Operation Setup
echo ============================================================
echo.
echo This will configure O.R.E.I.L.U.S. to run automatically:
echo   - Start when Windows boots
echo   - Run in background (no console window)
echo   - Daily automation at 7 AM and 8 AM PST
echo.

pause

echo.
echo [1/3] Importing Task Scheduler configuration...
schtasks /Create /TN "O.R.E.I.L.U.S. Backend Service" /XML "C:\Users\Victoria\oreilus\OREILUS_Task_Scheduler.xml" /F

if %ERRORLEVEL% EQU 0 (
    echo     Success - Task created
) else (
    echo     ERROR - Failed to create task. Run as Administrator!
    pause
    exit /b 1
)

echo.
echo [2/3] Testing the service...
echo Starting O.R.E.I.L.U.S. now...
python "C:\Users\Victoria\oreilus\start_oreilus_service.py"

timeout /t 5 /nobreak >nul

echo.
echo [3/3] Verifying backend is running...
curl -s http://localhost:8000 >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo     Success - Backend is running
) else (
    echo     Warning - Backend may not be running yet. Check logs.
)

echo.
echo ============================================================
echo Setup Complete
echo ============================================================
echo.
echo O.R.E.I.L.U.S. is now configured for 24/7 operation
echo.
echo What happens next:
echo   - Backend is running now at http://localhost:8000
echo   - Will auto-start when Windows reboots
echo   - Daily automation at 7 AM (Content) and 8 AM (Intel) PST
echo.
echo Access your system:
echo   - Dashboard: http://localhost:3000 (start frontend separately)
echo   - API: http://localhost:8000
echo   - Telegram: Message your bot
echo.
echo Logs location: C:\Users\Victoria\oreilus\oreilus_service.log
echo.
echo To stop: python stop_oreilus_service.py
echo.
pause
