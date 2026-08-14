@echo off
echo.
echo ========================================
echo  O.R.E.I.L.U.S. Startup Script
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo.
    echo Please create .env file from .env.example:
    echo   copy .env.example .env
    echo.
    echo Then add your API keys to the .env file.
    echo.
    pause
    exit /b 1
)

echo [1/3] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not running
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo Docker is ready!

echo.
echo [2/3] Starting O.R.E.I.L.U.S. services...
docker-compose up -d

echo.
echo [3/3] Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo  O.R.E.I.L.U.S. is now running!
echo ========================================
echo.
echo Web Interface:  http://localhost:3000
echo API Docs:       http://localhost:8000/docs
echo Health Check:   http://localhost:8000/health
echo.
echo To view logs:   docker-compose logs -f
echo To stop:        docker-compose down
echo.
echo Opening web interface...
start http://localhost:3000

echo.
pause
