# O.R.E.I.L.U.S. Database Setup Script
# Run this AFTER installing PostgreSQL

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " O.R.E.I.L.U.S. Database Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if PostgreSQL is installed
$pgPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

if (-not (Test-Path $pgPath)) {
    Write-Host "[ERROR] PostgreSQL not found!" -ForegroundColor Red
    Write-Host "Please install PostgreSQL first" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "PostgreSQL found!" -ForegroundColor Green
Write-Host ""
Write-Host "We need to create the O.R.E.I.L.U.S. database." -ForegroundColor Yellow
Write-Host ""
Write-Host "Please enter the PostgreSQL password (postgres123):" -ForegroundColor Yellow
Write-Host ""

# Set environment variable for psql path
$env:PATH = "C:\Program Files\PostgreSQL\18\bin;$env:PATH"

Write-Host "Creating database..." -ForegroundColor Green
Write-Host ""

# Run SQL commands directly (avoiding file encoding issues)
& $pgPath -U postgres -c "CREATE DATABASE oreilus;"
& $pgPath -U postgres -c "CREATE USER oreilus_user WITH PASSWORD 'oreilus_password';"
& $pgPath -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE oreilus TO oreilus_user;"
& $pgPath -U postgres -d oreilus -c "GRANT ALL ON SCHEMA public TO oreilus_user;"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Database Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: Get your Claude API key and run configure-env.ps1" -ForegroundColor Yellow
Write-Host ""
pause
