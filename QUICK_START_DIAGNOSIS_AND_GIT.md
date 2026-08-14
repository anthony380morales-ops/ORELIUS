# QUICK START: Diagnosis & Git Security Setup

## STEP 1: DIAGNOSE VPS (Current Running System)

SSH into your VPS and run these commands:

```bash
# Navigate to OREILUS
cd /opt/oreilus/backend

# Check service status
sudo systemctl status oreilus

# Check scheduler in logs
sudo journalctl -u oreilus -n 100 | grep -i "scheduler"

# Test automation endpoints
curl http://localhost:8000/api/automation/status

# Check what Telegram commands are available (current version)
grep "CommandHandler" app/telegram/bot.py
```

**What to look for**:
- Scheduler status: Should see "scheduler started" in logs
- Automation status: Should return JSON with job count
- Telegram commands: See how many commands are registered

---

## STEP 2: RUN SECURITY VERIFICATION (Local Machine)

On your Windows machine:

```powershell
cd C:\Users\Victoria\oreilus
.\verify_security.ps1
```

This will check:
- ✓ .gitignore is present
- ✓ Sensitive files are ignored
- ✓ No secrets in code
- ✓ Safe to commit

---

## STEP 3: INITIALIZE GIT (If Verification Passes)

```powershell
cd C:\Users\Victoria\oreilus

# Initialize Git
git init

# Configure user
git config user.name "Victoria"
git config user.email "your-email@example.com"

# Add all files (.gitignore will protect secrets)
git add .

# Run security check again
.\verify_security.ps1

# If all clear, commit
git commit -m "Initial commit: O.R.E.I.L.U.S. system with security implementation"
```

---

## STEP 4: CREATE PRIVATE GITHUB REPO (Optional)

1. Go to GitHub.com
2. Create **NEW PRIVATE REPOSITORY** named "oreilus"
3. Don't initialize with README (we already have one)
4. Copy the remote URL

Then on your local machine:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/oreilus.git
git push -u origin main
```

**CRITICAL**: Make sure repository is **PRIVATE**!

---

## FILES CREATED FOR YOU

1. **SECURITY_AUDIT.md** - Complete security checklist
2. **verify_security.ps1** - Automated security verification script
3. **VPS_COMMANDS.md** - All VPS management commands
4. **AUTOMATION_FIX_DEPLOYMENT_GUIDE.md** - Deployment guide for fixes

---

## QUICK REFERENCE

### Check VPS Automation Status:
```bash
curl http://localhost:8000/api/automation/status
```

### Check Local Git Status:
```powershell
.\verify_security.ps1
```

### View What Would Be Committed:
```powershell
git status
git diff --cached
```

---

## WHAT'S PROTECTED

Your `.gitignore` already protects:
- ✓ `.env` (API keys, passwords)
- ✓ `google-credentials.json` (service account)
- ✓ `*.log` files (may contain sensitive data)
- ✓ `venv/` directories
- ✓ `__pycache__/` Python cache
- ✓ `node_modules/` Node packages

**You're already secure!** Just need to initialize Git.
