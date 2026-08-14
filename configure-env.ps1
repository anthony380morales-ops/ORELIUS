# O.R.E.I.L.U.S. Environment Configuration Script
# Interactive .env file setup

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " O.R.E.I.L.U.S. Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env already exists
if (Test-Path ".env") {
    Write-Host "[WARNING] .env file already exists!" -ForegroundColor Yellow
    $overwrite = Read-Host "Do you want to overwrite it? (yes/no)"
    if ($overwrite -ne "yes") {
        Write-Host "Configuration cancelled." -ForegroundColor Yellow
        pause
        exit 0
    }
}

Write-Host "Let's configure your O.R.E.I.L.U.S. system." -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " REQUIRED: Claude API Key" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
$claudeKey = Read-Host "Paste your Claude API key here"

if ($claudeKey -notlike "sk-ant-*") {
    Write-Host ""
    Write-Host "[WARNING] Key doesn't start with 'sk-ant-'. Are you sure it's correct?" -ForegroundColor Yellow
    Write-Host "Continuing anyway..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " OPTIONAL: Telegram Bot" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Do you want to set up Telegram bot integration?" -ForegroundColor Yellow
Write-Host "(You can skip this and add it later)" -ForegroundColor Gray
Write-Host ""
$setupTelegram = Read-Host "Set up Telegram? (yes/no)"

$telegramToken = ""
$telegramUsers = ""

if ($setupTelegram -eq "yes") {
    Write-Host ""
    $telegramToken = Read-Host "Paste your Telegram bot token"
    Write-Host ""
    $telegramUsers = Read-Host "Paste your Telegram user ID"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Security Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Creating secure random keys..." -ForegroundColor Green

# Generate random keys
function Get-RandomKey {
    param([int]$Length = 32)
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
}

function Get-RandomHex {
    param([int]$Length = 32)
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ''
}

$jwtSecret = Get-RandomKey
$encryptionKey = Get-RandomHex

Write-Host "Security keys generated!" -ForegroundColor Green
Write-Host ""

Write-Host "Choose a master password for O.R.E.I.L.U.S.:" -ForegroundColor Yellow
Write-Host "(This is for administrative access)" -ForegroundColor Gray
Write-Host ""
$masterPassword = Read-Host "Master password"

# Create .env file
Write-Host ""
Write-Host "Creating .env file..." -ForegroundColor Green

$envContent = "# O.R.E.I.L.U.S. Configuration`n"
$envContent += "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n`n"
$envContent += "# Claude API`n"
$envContent += "ANTHROPIC_API_KEY=$claudeKey`n`n"
$envContent += "# Telegram Bot`n"
$envContent += "TELEGRAM_BOT_TOKEN=$telegramToken`n"
$envContent += "TELEGRAM_ALLOWED_USERS=$telegramUsers`n`n"
$envContent += "# Database`n"
$envContent += "DATABASE_URL=postgresql://oreilus_user:oreilus_password@localhost:5432/oreilus`n"
$envContent += "REDIS_URL=redis://localhost:6379/0`n`n"
$envContent += "# Security Keys`n"
$envContent += "JWT_SECRET_KEY=$jwtSecret`n"
$envContent += "ENCRYPTION_KEY=$encryptionKey`n"
$envContent += "MASTER_PASSWORD=$masterPassword`n`n"
$envContent += "# System Configuration`n"
$envContent += "TIMEZONE=America/Los_Angeles`n"
$envContent += "LOG_LEVEL=INFO`n"
$envContent += "ENVIRONMENT=development`n"
$envContent += "FRONTEND_URL=http://localhost:3000`n"
$envContent += "BACKEND_URL=http://localhost:8000`n"
$envContent += "RATE_LIMIT_PER_MINUTE=60`n"
$envContent += "RATE_LIMIT_PER_HOUR=1000`n"

$envContent | Out-File -FilePath ".env" -Encoding ASCII

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Configuration Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next step: Start O.R.E.I.L.U.S." -ForegroundColor Yellow
Write-Host ""
Write-Host "Run: .\start-oreilus.ps1" -ForegroundColor White
Write-Host ""
pause
