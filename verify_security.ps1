# O.R.E.I.L.U.S. Security Verification Script
# Run this before Git commits to ensure no secrets are exposed

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "O.R.E.I.L.U.S. SECURITY VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$errors = 0
$warnings = 0

# Check 1: .gitignore exists
Write-Host "[CHECK 1] Verifying .gitignore exists..." -ForegroundColor Yellow
if (Test-Path ".gitignore") {
    Write-Host "  OK .gitignore found" -ForegroundColor Green
} else {
    Write-Host "  ERROR .gitignore NOT FOUND!" -ForegroundColor Red
    $errors++
}

# Check 2: Sensitive files are ignored
Write-Host "`n[CHECK 2] Verifying sensitive files are in .gitignore..." -ForegroundColor Yellow
$requiredIgnores = @(".env", "google-credentials.json", "*.log", "venv/", "__pycache__/")
$gitignoreContent = Get-Content ".gitignore" -Raw

foreach ($pattern in $requiredIgnores) {
    if ($gitignoreContent -like "*$pattern*") {
        Write-Host "  OK $pattern is ignored" -ForegroundColor Green
    } else {
        Write-Host "  ERROR $pattern NOT in .gitignore!" -ForegroundColor Red
        $errors++
    }
}

# Check 3: Sensitive files exist but won't be committed
Write-Host "`n[CHECK 3] Checking sensitive files..." -ForegroundColor Yellow

if (Test-Path ".env") {
    Write-Host "  WARNING .env file exists (contains secrets)" -ForegroundColor Yellow
    Write-Host "    OK .env is in .gitignore" -ForegroundColor Green
} else {
    Write-Host "  INFO No .env file found" -ForegroundColor Cyan
}

if (Test-Path "google-credentials.json") {
    Write-Host "  WARNING google-credentials.json exists (contains secrets)" -ForegroundColor Yellow
    Write-Host "    OK google-credentials.json is in .gitignore" -ForegroundColor Green
}

if (Test-Path "backend/.env") {
    Write-Host "  WARNING backend/.env exists (contains secrets)" -ForegroundColor Yellow
    Write-Host "    OK backend/.env is in .gitignore" -ForegroundColor Green
}

# Check 4: .env.example exists (template)
Write-Host "`n[CHECK 4] Verifying .env.example exists..." -ForegroundColor Yellow
if (Test-Path ".env.example") {
    Write-Host "  OK .env.example found (template for users)" -ForegroundColor Green
} else {
    Write-Host "  WARNING .env.example not found (recommended)" -ForegroundColor Yellow
    $warnings++
}

# Check 5: Git status (if initialized)
Write-Host "`n[CHECK 5] Checking Git status..." -ForegroundColor Yellow
$gitInitialized = Test-Path ".git"

if ($gitInitialized) {
    Write-Host "  OK Git repository initialized" -ForegroundColor Green

    # Check what would be committed
    $staged = git diff --cached --name-only 2>$null
    if ($staged) {
        Write-Host "`n  Files staged for commit:" -ForegroundColor Cyan
        $staged | ForEach-Object {
            Write-Host "    - $_" -ForegroundColor White
        }

        # Check for sensitive files in staging
        $sensitiveFiles = @(".env", "google-credentials.json")
        foreach ($file in $staged) {
            foreach ($sensitive in $sensitiveFiles) {
                if ($file -eq $sensitive) {
                    Write-Host "    ERROR SENSITIVE FILE STAGED: $file" -ForegroundColor Red
                    $errors++
                }
            }
            if ($file -like "*.log") {
                Write-Host "    WARNING Log file staged: $file" -ForegroundColor Yellow
                $warnings++
            }
        }
    } else {
        Write-Host "  INFO No files currently staged" -ForegroundColor Cyan
    }
} else {
    Write-Host "  INFO Git not initialized yet" -ForegroundColor Cyan
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "SECURITY VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "`nALL CHECKS PASSED - Safe to commit!" -ForegroundColor Green
} elseif ($errors -eq 0) {
    Write-Host "`n$warnings WARNING(S) - Review before committing" -ForegroundColor Yellow
} else {
    Write-Host "`n$errors ERROR(S) - DO NOT COMMIT!" -ForegroundColor Red
    Write-Host "Fix the errors above before committing to Git" -ForegroundColor Red
}

Write-Host "`nRecommended next steps:" -ForegroundColor Cyan
if (-not $gitInitialized) {
    Write-Host "  1. Run: git init" -ForegroundColor White
    Write-Host "  2. Run: git add ." -ForegroundColor White
    Write-Host "  3. Run this script again to verify" -ForegroundColor White
    Write-Host "  4. Run: git commit -m ""Initial commit""" -ForegroundColor White
} else {
    Write-Host "  1. Review any warnings above" -ForegroundColor White
    Write-Host "  2. Make sure no sensitive files are staged" -ForegroundColor White
    Write-Host "  3. Proceed with commit if all clear" -ForegroundColor White
}

Write-Host ""
