# O.R.E.I.L.U.S. Dependency Installation Script
# Run this in PowerShell as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " O.R.E.I.L.U.S. Dependency Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[1/3] Installing PostgreSQL..." -ForegroundColor Green
Write-Host "This will take a few minutes. Please wait..." -ForegroundColor Yellow
Write-Host ""

# Install PostgreSQL
winget install --id PostgreSQL.PostgreSQL --version 16.2 --silent --accept-package-agreements --accept-source-agreements

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ PostgreSQL installed successfully!" -ForegroundColor Green
} else {
    Write-Host "✗ PostgreSQL installation failed. You may need to install manually." -ForegroundColor Red
}

Write-Host ""
Write-Host "[2/3] Installing Redis..." -ForegroundColor Green
Write-Host ""

# Install Redis (using Memurai as Redis alternative for Windows)
winget install --id Memurai.Memurai-Developer --silent --accept-package-agreements --accept-source-agreements

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Redis (Memurai) installed successfully!" -ForegroundColor Green
} else {
    Write-Host "✗ Redis installation failed. You may need to install manually." -ForegroundColor Red
}

Write-Host ""
Write-Host "[3/3] Starting services..." -ForegroundColor Green
Write-Host ""

# Start PostgreSQL service
Start-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue

# Start Redis/Memurai service
Start-Service -Name "Memurai" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Close this PowerShell window"
Write-Host "2. Open a NEW PowerShell window (normal, not admin)"
Write-Host "3. Run: cd C:\Users\Victoria\oreilus"
Write-Host "4. Run: .\setup-database.ps1"
Write-Host ""
pause
