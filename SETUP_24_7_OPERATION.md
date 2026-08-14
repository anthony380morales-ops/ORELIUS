# O.R.E.I.L.U.S. 24/7 Background Operation Setup

## Overview

This guide will configure O.R.E.I.L.U.S. to run 24/7 in the background on Windows without needing an active PowerShell window. The system will:

- ✓ Start automatically when Windows boots
- ✓ Run completely hidden (no console windows)
- ✓ Execute daily automation tasks at 7 AM and 8 AM PST
- ✓ Continue running even if you log off
- ✓ Restart automatically if it crashes

## Automated Scheduling Confirmation

**Your automation is already configured to run autonomously:**
- **Content Trend Scanner**: Daily at 7:00 AM PST (Instagram, Facebook, LinkedIn, X, TikTok)
- **Government Banking Intelligence**: Daily at 8:00 AM PST (Fed, FDIC, OCC, CFPB)

No manual authorization needed - tasks run automatically when scheduled.

---

## Method 1: Windows Task Scheduler (Recommended)

### Step 1: Create the Scheduled Task

1. Press `Win + R` and type: `taskschd.msc` (opens Task Scheduler)
2. Click **"Create Task"** (not "Create Basic Task")

### Step 2: General Tab Settings

- **Name**: `O.R.E.I.L.U.S. Backend Service`
- **Description**: `Autonomous AI agent with daily automation at 7 AM and 8 AM PST`
- **Security Options**:
  - ☑ Run whether user is logged on or not
  - ☑ Run with highest privileges
  - ☐ Hidden (optional - hides from task list)
- **Configure for**: Windows 10

### Step 3: Triggers Tab

Click **"New"** and configure:

- **Begin the task**: At startup
- **Delay task for**: 30 seconds (gives Windows time to load)
- ☑ Enabled

(Optional) Add a second trigger:
- **Begin the task**: At log on
- **Specific user**: Victoria
- ☑ Enabled

### Step 4: Actions Tab

Click **"New"** and configure:

**Option A - Using VBScript (Completely Hidden)**
- **Action**: Start a program
- **Program/script**: `wscript.exe`
- **Add arguments**: `"C:\Users\Victoria\oreilus\start_oreilus_hidden.vbs"`
- **Start in**: `C:\Users\Victoria\oreilus`

**Option B - Using Python Service Script (Recommended)**
- **Action**: Start a program
- **Program/script**: `C:\Users\Victoria\oreilus\backend\venv\Scripts\python.exe`
- **Add arguments**: `"C:\Users\Victoria\oreilus\start_oreilus_service.py"`
- **Start in**: `C:\Users\Victoria\oreilus`

### Step 5: Conditions Tab

- ☐ Start the task only if the computer is on AC power (uncheck this!)
- ☑ Wake the computer to run this task (optional)
- ☑ Start only if the following network connection is available: Any connection

### Step 6: Settings Tab

- ☑ Allow task to be run on demand
- ☑ Run task as soon as possible after a scheduled start is missed
- ☐ Stop the task if it runs longer than (uncheck this - we want 24/7)
- **If the task is already running**: Do not start a new instance

### Step 7: Save and Test

1. Click **OK**
2. Enter your Windows password when prompted
3. Right-click the task and select **"Run"** to test
4. Check if it's running: Open browser to `http://localhost:8000`

---

## Method 2: Manual Startup (Quick Test)

### Start O.R.E.I.L.U.S. in Background

```batch
# Option 1: Start with visible console (for testing)
start_oreilus_backend.bat

# Option 2: Start hidden in background
start_oreilus_hidden.vbs

# Option 3: Start as service (Python)
python start_oreilus_service.py
```

### Stop O.R.E.I.L.U.S.

```batch
python stop_oreilus_service.py
```

### Check if Running

```batch
# Check if backend is running
curl http://localhost:8000
# Should return: {"system":"O.R.E.I.L.U.S.","version":"0.1.0","status":"operational"}

# OR open in browser
start http://localhost:8000
```

---

## Verification Checklist

After setup, verify the following:

### ✓ Backend Running
- [ ] Open browser: `http://localhost:8000` (should show JSON response)
- [ ] Check logs: `C:\Users\Victoria\oreilus\oreilus_service.log`

### ✓ Dashboard Access
- [ ] Frontend: `http://localhost:3000` (start separately with `npm run dev`)
- [ ] Chat interface working
- [ ] Automation dashboard showing scheduled jobs

### ✓ Automation Scheduled
- [ ] Go to Automation tab in dashboard
- [ ] Verify "Content Trend Scanner" scheduled for 7:00 AM PST
- [ ] Verify "Government Intel Scanner" scheduled for 8:00 AM PST

### ✓ Background Operation
- [ ] Close all PowerShell/terminal windows
- [ ] Backend should still be running
- [ ] Check: `http://localhost:8000` still responds

### ✓ Restart Persistence
- [ ] Restart Windows
- [ ] After reboot, check `http://localhost:8000` (should auto-start)

---

## Monitoring & Logs

### Log Files

```
C:\Users\Victoria\oreilus\oreilus_service.log       # Service startup/stop logs
C:\Users\Victoria\oreilus\oreilus_startup.log       # VBScript startup logs
C:\Users\Victoria\oreilus\backend\logs\*.log        # Application logs
```

### View Logs

```batch
# View service log
type C:\Users\Victoria\oreilus\oreilus_service.log

# View recent application logs
cd C:\Users\Victoria\oreilus\backend\logs
dir /o-d
type latest_log_file.log
```

### Check Process Status

```batch
# Find O.R.E.I.L.U.S. process
tasklist | findstr python

# Check PID file
type C:\Users\Victoria\oreilus\oreilus.pid
```

---

## Troubleshooting

### Backend Not Starting

**Issue**: Task Scheduler shows "Running" but backend doesn't respond

**Solutions**:
1. Check Task Scheduler Last Run Result (should be 0x0 for success)
2. Check logs: `C:\Users\Victoria\oreilus\oreilus_service.log`
3. Test manually: `python start_oreilus_service.py`
4. Verify virtual environment: `C:\Users\Victoria\oreilus\backend\venv`

### Port Already in Use

**Issue**: Error "Address already in use: port 8000"

**Solution**:
```batch
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /F /PID <PID>
```

### Automation Not Running

**Issue**: 7 AM or 8 AM tasks not executing

**Check**:
1. Backend is running: `http://localhost:8000`
2. Timezone is correct: PST (America/Los_Angeles)
3. Check automation logs in dashboard
4. Manually trigger test: Go to Automation tab → Click "Run Now"

### Frontend Not Connecting

**Issue**: Dashboard shows "Connection failed"

**Solution**:
1. Verify backend is running: `http://localhost:8000`
2. Start frontend: `cd C:\Users\Victoria\oreilus\frontend && npm run dev`
3. Check CORS settings in `backend/app/main.py`

---

## Frontend 24/7 Setup (Optional)

The backend runs 24/7 automatically. The frontend (React dashboard) can be started when needed:

```batch
cd C:\Users\Victoria\oreilus\frontend
npm run dev
```

**To make frontend 24/7 too:**
1. Build production version: `npm run build`
2. Serve with nginx or use `npm run preview`
3. Add to Task Scheduler (similar to backend)

---

## Security Notes

- ✓ Backend runs on localhost only (not exposed to internet)
- ✓ No external ports opened (safe from remote access)
- ✓ Credentials stored securely in `.env` file
- ✓ `.gitignore` prevents credential commits

**Important**: If you expose port 8000 to the internet (port forwarding), add authentication!

---

## Quick Reference Commands

```batch
# Start O.R.E.I.L.U.S.
python start_oreilus_service.py

# Stop O.R.E.I.L.U.S.
python stop_oreilus_service.py

# Check status
curl http://localhost:8000

# View logs
type C:\Users\Victoria\oreilus\oreilus_service.log

# Test automation manually (from dashboard)
http://localhost:3000 → Automation tab → "Run Now"
```

---

## What Happens After Setup

Once configured, O.R.E.I.L.U.S. will:

1. **Startup**: Automatically start when Windows boots
2. **7:00 AM PST**: Scrape trending content from Instagram, Facebook, LinkedIn, X, TikTok
3. **7:05 AM PST**: Write content trends to Google Sheets
4. **8:00 AM PST**: Fetch government banking intelligence from Fed, FDIC, OCC, CFPB
5. **8:05 AM PST**: Write banking intelligence to Google Sheets
6. **24/7**: Monitor system health, respond to Telegram messages, handle API requests
7. **Restart**: Continue running even after Windows restarts

**You can access the system anytime at:**
- Dashboard: `http://localhost:3000` (after starting frontend)
- API: `http://localhost:8000`
- Telegram: Message your Telegram bot

---

## Support

If you encounter issues:
1. Check logs: `C:\Users\Victoria\oreilus\oreilus_service.log`
2. Test manually: `python start_oreilus_service.py`
3. Verify credentials in `.env` file
4. Check Task Scheduler logs (Task Scheduler → task → History tab)

---

**System Status**: ✓ Ready for 24/7 autonomous operation
