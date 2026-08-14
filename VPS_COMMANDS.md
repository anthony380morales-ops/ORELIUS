# VPS Commands for OREILUS Diagnosis & Management

## CONNECT TO VPS

```bash
ssh root@YOUR_VPS_IP
# Enter your password when prompted
```

---

## RUN DIAGNOSTIC SCRIPT

### Option 1: With Virtual Environment (Recommended)
```bash
cd /root/oreilus/backend
source venv/bin/activate
python3 diagnose_scheduler.py
```

### Option 2: Without Virtual Environment
```bash
cd /root/oreilus/backend
python3 diagnose_scheduler.py
```

### Option 3: Using Full Python Path
```bash
cd /root/oreilus/backend
/root/oreilus/backend/venv/bin/python diagnose_scheduler.py
```

---

## FIND WHERE OREILUS IS LOCATED

If you're not sure where OREILUS is installed:

```bash
# Find oreilus directory
find / -name "oreilus" -type d 2>/dev/null

# Common locations:
ls /root/oreilus
ls /home/*/oreilus
ls /opt/oreilus
```

---

## CHECK IF BACKEND IS RUNNING

```bash
# Check for running Python/Uvicorn processes
ps aux | grep uvicorn
ps aux | grep "app.main"

# Check if port 8000 is in use
netstat -tulpn | grep 8000
# OR
lsof -i :8000
```

---

## VIEW BACKEND LOGS

```bash
# Live log viewing (Ctrl+C to stop)
tail -f /root/oreilus/backend/logs/oreilus.log

# Last 50 lines of logs
tail -50 /root/oreilus/backend/logs/oreilus.log

# Search for scheduler in logs
grep "scheduler" /root/oreilus/backend/logs/oreilus.log | tail -20

# Search for automation runs
grep -i "content_scan\|government_scan" /root/oreilus/backend/logs/oreilus.log | tail -20

# Search for errors
grep -i "error" /root/oreilus/backend/logs/oreilus.log | tail -20
```

---

## RESTART BACKEND SERVICE

### If using systemd service:
```bash
# Check status
sudo systemctl status oreilus

# Restart
sudo systemctl restart oreilus

# Stop
sudo systemctl stop oreilus

# Start
sudo systemctl start oreilus

# View service logs
sudo journalctl -u oreilus -f
```

### If using screen:
```bash
# List screen sessions
screen -ls

# Attach to OREILUS screen
screen -r oreilus

# Inside screen:
# - Ctrl+C to stop the backend
# - Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
# - Ctrl+A then D to detach

# Kill a screen session
screen -X -S oreilus quit
```

### If running directly (no systemd/screen):
```bash
# Find the process
ps aux | grep "uvicorn.*app.main"

# Kill it (replace PID with actual process ID)
kill -9 PID

# Start manually
cd /root/oreilus/backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &

# OR with output logging
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> logs/oreilus.log 2>&1 &
```

---

## UPLOAD FILES TO VPS

### From your Windows machine (PowerShell or Git Bash):

```bash
# Upload bot.py
scp C:\Users\Victoria\oreilus\backend\app\telegram\bot.py root@YOUR_VPS_IP:/root/oreilus/backend/app/telegram/bot.py

# Upload scheduler.py
scp C:\Users\Victoria\oreilus\backend\app\automation\scheduler.py root@YOUR_VPS_IP:/root/oreilus/backend/app/automation/scheduler.py

# Upload diagnostic script
scp C:\Users\Victoria\oreilus\backend\diagnose_scheduler.py root@YOUR_VPS_IP:/root/oreilus/backend/diagnose_scheduler.py
```

---

## MANUAL DIAGNOSTIC CHECKS (Without Script)

### Check if scheduler is imported correctly:
```bash
cd /root/oreilus/backend
source venv/bin/activate
python3 -c "from app.automation.scheduler import automation_scheduler; print('✓ Scheduler imported successfully')"
```

### Check if jobs are scheduled:
```bash
cd /root/oreilus/backend
source venv/bin/activate
python3 << 'EOF'
from app.automation.scheduler import automation_scheduler
automation_scheduler.start()
jobs = automation_scheduler.get_jobs()
print(f"Jobs scheduled: {len(jobs)}")
for job in jobs:
    print(f"  - {job.name}: {job.next_run_time}")
EOF
```

### Test Telegram bot import:
```bash
cd /root/oreilus/backend
source venv/bin/activate
python3 -c "from app.telegram import telegram_bot; print('✓ Telegram bot imported successfully')"
```

---

## CHECK PYTHON VERSION

```bash
# Check python3 version
python3 --version

# Check if python command exists
python --version

# Find python installations
which python3
which python
```

---

## COMMON ERROR FIXES

### Error: "python: command not found"
**Solution**: Use `python3` instead of `python`
```bash
python3 diagnose_scheduler.py
```

### Error: "ModuleNotFoundError: No module named 'app'"
**Solution**: Make sure you're in the backend directory and venv is activated
```bash
cd /root/oreilus/backend
source venv/bin/activate
python3 diagnose_scheduler.py
```

### Error: "No module named 'apscheduler'"
**Solution**: Install dependencies
```bash
cd /root/oreilus/backend
source venv/bin/activate
pip install -r requirements.txt
```

### Error: "Connection refused" when accessing backend
**Solution**: Backend is not running, start it
```bash
cd /root/oreilus/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## QUICK TEST SEQUENCE

Run these commands in order to diagnose issues:

```bash
# 1. Connect to VPS
ssh root@YOUR_VPS_IP

# 2. Navigate to backend
cd /root/oreilus/backend

# 3. Activate virtual environment
source venv/bin/activate

# 4. Check if backend is running
ps aux | grep uvicorn

# 5. Check backend logs for errors
tail -50 logs/oreilus.log | grep -i error

# 6. Run diagnostic script
python3 diagnose_scheduler.py

# 7. Check scheduler logs
grep "scheduler" logs/oreilus.log | tail -20

# 8. Test backend API
curl http://localhost:8000/health
curl http://localhost:8000/api/automation/status
```

---

## VERIFY AUTOMATIONS ARE SCHEDULED

### Using curl (on VPS):
```bash
curl http://localhost:8000/api/automation/jobs
curl http://localhost:8000/api/automation/status
```

### Expected output:
```json
{
  "success": true,
  "scheduler_running": true,
  "jobs_scheduled": 2,
  "timezone": "America/Los_Angeles",
  "jobs": [
    {
      "id": "content_trend_scanner",
      "name": "Content Trend Scanner",
      "next_run": "2026-03-15T07:00:00-08:00"
    },
    {
      "id": "government_intel_scanner",
      "name": "Government Banking Intelligence Scanner",
      "next_run": "2026-03-15T08:00:00-08:00"
    }
  ]
}
```

---

## MANUALLY TRIGGER AUTOMATIONS (for testing)

### Using curl:
```bash
# Trigger Content Scanner
curl -X POST http://localhost:8000/api/automation/trigger/content_trend_scanner

# Trigger Intel Scanner
curl -X POST http://localhost:8000/api/automation/trigger/government_intel_scanner
```

### Using Telegram:
Just send these commands to your bot:
- `/trigger_content`
- `/trigger_intel`

---

## FILE LOCATIONS ON VPS

```
/root/oreilus/
├── backend/
│   ├── app/
│   │   ├── main.py                    # Main application entry
│   │   ├── telegram/
│   │   │   └── bot.py                 # Telegram bot (UPDATED)
│   │   └── automation/
│   │       └── scheduler.py           # Scheduler (UPDATED)
│   ├── diagnose_scheduler.py          # Diagnostic script (NEW)
│   ├── logs/
│   │   └── oreilus.log               # Main log file
│   └── venv/                          # Virtual environment
└── .env                               # Environment variables
```

---

## EMERGENCY RESTART

If everything is broken and you need to restart fresh:

```bash
# 1. Stop everything
pkill -f uvicorn
screen -X -S oreilus quit

# 2. Navigate to backend
cd /root/oreilus/backend

# 3. Activate venv
source venv/bin/activate

# 4. Start backend in foreground (to see errors)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Watch for errors in startup
# If you see scheduler errors, that's what we need to fix

# 5. Once working, stop (Ctrl+C) and run in background:
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> logs/oreilus.log 2>&1 &
```

---

## NOTES

- Replace `YOUR_VPS_IP` with your actual VPS IP address
- Replace `/root/oreilus` with actual path if different
- Most VPS systems use `python3`, not `python`
- Always activate the virtual environment before running Python scripts
- Use `Ctrl+C` to stop foreground processes
- Use `Ctrl+A then D` to detach from screen sessions
