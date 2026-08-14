# O.R.E.I.L.U.S. Startup Script
# Starts backend and frontend services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Starting O.R.E.I.L.U.S. System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] .env file not found!" -ForegroundColor Red
    Write-Host "Please run: .\configure-env.ps1" -ForegroundColor Yellow
    pause
    exit 1
}

# Check if PostgreSQL service is running
$pgService = Get-Service -Name "postgresql-x64-18" -ErrorAction SilentlyContinue

if ($null -eq $pgService) {
    Write-Host "[WARNING] PostgreSQL service not found!" -ForegroundColor Yellow
} elseif ($pgService.Status -ne "Running") {
    Write-Host "Starting PostgreSQL service..." -ForegroundColor Yellow
    Start-Service -Name "postgresql-x64-18"
    Start-Sleep -Seconds 3
}

# Check if Redis/Memurai service is running
$redisService = Get-Service -Name "Memurai" -ErrorAction SilentlyContinue

if ($null -eq $redisService) {
    Write-Host "[WARNING] Redis service not found!" -ForegroundColor Yellow
} elseif ($redisService.Status -ne "Running") {
    Write-Host "Starting Redis service..." -ForegroundColor Yellow
    Start-Service -Name "Memurai"
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "[1/4] Setting up Python virtual environment..." -ForegroundColor Green

# Setup backend
Set-Location -Path ".\backend"

# Create venv if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate venv and install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "(This may take a few minutes the first time)" -ForegroundColor Gray
Write-Host ""

& ".\venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Failed to install Python dependencies!" -ForegroundColor Red
    Set-Location -Path ".."
    pause
    exit 1
}

Write-Host "Python dependencies installed" -ForegroundColor Green
Write-Host ""

Write-Host "[2/4] Installing Node.js dependencies..." -ForegroundColor Green
Set-Location -Path "..\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend packages..." -ForegroundColor Yellow
    Write-Host "(This may take a few minutes the first time)" -ForegroundColor Gray
    Write-Host ""
    npm install --silent

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[ERROR] Failed to install Node.js dependencies!" -ForegroundColor Red
        Set-Location -Path ".."
        pause
        exit 1
    }
}

Write-Host "Node.js dependencies installed" -ForegroundColor Green
Write-Host ""

Set-Location -Path ".."

Write-Host "[3/4] Starting Backend API..." -ForegroundColor Green
Write-Host ""

# Start backend in new window
$backendCmd = "Set-Location '$PWD\backend'; & '.\venv\Scripts\python.exe' -m app.main; pause"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "Backend starting..." -ForegroundColor Green
Write-Host "  URL: http://localhost:8000" -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 5

Write-Host "[4/4] Starting Frontend Dashboard..." -ForegroundColor Green
Write-Host ""

# Start frontend in new window
$frontendCmd = "Set-Location '$PWD\frontend'; npm run dev; pause"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host "Frontend starting..." -ForegroundColor Green
Write-Host "  URL: http://localhost:3000" -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " O.R.E.I.L.U.S. is starting up!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  Backend API:    http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend:       http://localhost:3000" -ForegroundColor White
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Wait 10-15 seconds for everything to fully start..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Opening web interface in 10 seconds..." -ForegroundColor Green
Start-Sleep -Seconds 10

Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "O.R.E.I.L.U.S. is now operational!" -ForegroundColor Green
Write-Host ""
Write-Host "To stop:" -ForegroundColor Yellow
Write-Host "  1. Close the Backend window" -ForegroundColor White
Write-Host "  2. Close the Frontend window" -ForegroundColor White
Write-Host ""
pause
