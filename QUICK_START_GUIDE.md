# O.R.E.I.L.U.S. Quick Start Guide

## ✓ Your System is Ready for 24/7 Operation

Your O.R.E.I.L.U.S. autonomous AI agent is fully configured and ready to run 24/7 in the background.

---

## Current Status

### ✓ Backend Running Now
- **Status**: Running in background (PID in `oreilus.pid`)
- **URL**: http://localhost:8000
- **API Test**: `curl http://localhost:8000` (should return JSON)

### ✓ Automation Scheduled
- **Content Trend Scanner**: Daily at 7:00 AM PST
  - Scrapes Instagram, Facebook, LinkedIn, X, TikTok
  - Writes to Google Sheets (Blueprint Collective - Daily Trending Intelligence)
- **Government Intel Scanner**: Daily at 8:00 AM PST
  - Fetches from Federal Reserve, FDIC, OCC, CFPB
  - Writes to Google Sheets (Blueprint Collective - Government Banking Intelligence)

### ✓ Mock Data Mode
- Currently using mock data for social media (as configured)
- Will attempt authentication, fall back to mock data gracefully
- No risk of account bans

---

## One-Time Setup: Windows Task Scheduler

**Run this once to enable auto-start on boot:**

### Option 1: Automated Setup (Easiest)
```batch
# Right-click and "Run as Administrator"
setup_24_7.bat
```

### Option 2: Manual Import
1. Open Task Scheduler: Press `Win + R` → type `taskschd.msc`
2. Action → Import Task
3. Select: `C:\Users\Victoria\oreilus\OREILUS_Task_Scheduler.xml`
4. Enter your Windows password when prompted
5. Done! O.R.E.I.L.U.S. will now start automatically on boot

---

## Daily Commands

### Start O.R.E.I.L.U.S. (if not already running)
```batch
cd C:\Users\Victoria\oreilus
python start_oreilus_service.py
```

### Stop O.R.E.I.L.U.S.
```batch
cd C:\Users\Victoria\oreilus
python stop_oreilus_service.py
```

### Check if Running
```batch
curl http://localhost:8000
# Should return: {"system":"O.R.E.I.L.U.S.","version":"0.1.0"...}
```

### Start Frontend Dashboard
```batch
cd C:\Users\Victoria\oreilus\frontend
npm run dev
# Opens at http://localhost:3000
```

---

## Access Your System

### Mission Control Dashboard
- **URL**: http://localhost:3000 (after starting frontend)
- **Features**:
  - Real-time chat with O.R.E.I.L.U.S.
  - System health monitoring
  - Automation dashboard
  - Audit logs
  - Manual job triggers

### API Endpoints
- **Base URL**: http://localhost:8000
- **Chat**: POST `/api/chat`
- **System Status**: GET `/api/system/status`
- **Automation Jobs**: GET `/api/automation/jobs`
- **Trigger Job**: POST `/api/automation/trigger/content_trend_scanner`

### Telegram Bot
- Message your bot (configured in .env)
- Commands: `/start`, `/status`, `/help`

---

## What Happens Daily

**7:00 AM PST - Content Trend Scanner**
1. Launches browser automation (Playwright)
2. Attempts to log into Instagram, Facebook, LinkedIn
3. Falls back to mock data if login fails (as expected)
4. Scrapes trending content about banking/IBC/insurance
5. Ranks top 10 by engagement rate
6. Writes to Google Sheet #1 (Daily Trending Intelligence)
7. Creates new worksheet with today's date

**8:00 AM PST - Government Banking Intelligence**
1. Fetches latest data from:
   - Federal Reserve
   - FDIC
   - OCC (Office of the Comptroller)
   - CFPB (Consumer Financial Protection Bureau)
2. Parses key banking/regulatory updates
3. Ranks top 20 by importance
4. Writes to Google Sheet #2 (Government Banking Intelligence)
5. Creates new worksheet with today's date

---

## Files & Logs

### Startup Scripts
- `start_oreilus_service.py` - Start backend as background service
- `stop_oreilus_service.py` - Stop background service
- `start_oreilus_backend.bat` - Start with visible console (for testing)
- `start_oreilus_hidden.vbs` - Start completely hidden

### Configuration
- `.env` - All credentials (NEVER commit to git)
- `OREILUS_Task_Scheduler.xml` - Windows Task Scheduler import file
- `setup_24_7.bat` - Automated Task Scheduler setup

### Logs
- `oreilus_service.log` - Service startup/stop events
- `backend/logs/` - Application logs (FastAPI, scheduler, scrapers)
- View latest: `tail -50 backend/logs/app.log` (if using loguru file handler)

### Process Tracking
- `oreilus.pid` - Contains process ID when running

---

## Troubleshooting

### Backend Not Responding
```batch
# Check if process is running
curl http://localhost:8000

# If not responding:
python stop_oreilus_service.py
python start_oreilus_service.py
```

### Port Already in Use
```batch
# Find process using port 8000
netstat -ano | findstr :8000

# Kill it (replace PID with actual number)
taskkill /F /PID <PID>

# Restart
python start_oreilus_service.py
```

### Automation Not Running
1. Check backend is running: `curl http://localhost:8000`
2. Verify scheduler status: `curl http://localhost:8000/api/automation/jobs`
3. Check next run times (should be 7 AM and 8 AM PST)
4. Manually trigger test: Dashboard → Automation → "Run Now"

### Google Sheets Not Updating
1. Verify credentials: `C:\Users\Victoria\oreilus\google-credentials.json`
2. Check Sheet IDs in `.env`:
   - `GOOGLE_SHEET_ID_TRENDS` (Daily Trending Intelligence)
   - `GOOGLE_SHEET_ID_BANKING` (Government Banking Intelligence)
3. Manually trigger: Dashboard → Automation → "Run Now" → Check Google Sheets

---

## Security Reminders

✓ Backend runs on localhost only (not exposed to internet)
✓ Credentials stored in `.env` (gitignored)
✓ Social media using mock data (no account bans)
✓ Google Sheets uses service account (secure)

---

## Next Steps

### Immediate (Already Running)
- [x] Backend running 24/7 in background
- [x] Automation scheduled for daily execution
- [x] Google Sheets integration active

### Configure Once (Optional)
- [ ] Set up Windows Task Scheduler (run `setup_24_7.bat`)
- [ ] Test by restarting computer (should auto-start)

### Ongoing
- Access dashboard: Start frontend when needed (`npm run dev`)
- Monitor automation: Check Google Sheets daily after 8 AM PST
- Chat with O.R.E.I.L.U.S.: Via dashboard or Telegram
- View logs: Check `oreilus_service.log` periodically

---

## Support Commands

```batch
# View service log
type oreilus_service.log

# Check scheduler status
curl http://localhost:8000/api/automation/status

# Check scheduled jobs
curl http://localhost:8000/api/automation/jobs

# Test automation manually
curl -X POST http://localhost:8000/api/automation/trigger/content_trend_scanner

# View process ID
type oreilus.pid

# Check if backend process is running
tasklist | findstr python
```

---

**Your O.R.E.I.L.U.S. system is now fully operational and ready for autonomous 24/7 operation!**

For detailed setup instructions, see: `SETUP_24_7_OPERATION.md`
