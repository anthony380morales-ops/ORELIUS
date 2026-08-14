# 🚀 O.R.E.I.L.U.S. Full Installation Guide

Complete step-by-step installation for the full system (no Docker).

---

## ✅ What You Already Have

- ✓ Python 3.14.1
- ✓ Node.js 24.12.0
- ✓ Windows 11 Pro

## 📦 What You Need to Install

- PostgreSQL 16 (database)
- Redis/Memurai (caching)

---

## 🎯 Installation Steps

### Step 1: Install PostgreSQL and Redis

**Right-click PowerShell and select "Run as Administrator"**, then:

```powershell
cd C:\Users\Victoria\oreilus
.\install-dependencies.ps1
```

**What this does:**
- Installs PostgreSQL 16 database
- Installs Memurai (Redis for Windows)
- Starts both services automatically

**During PostgreSQL installation:**
- You'll be asked to set a **password for the `postgres` user**
- **REMEMBER THIS PASSWORD** - you'll need it in Step 2
- Use something simple for testing: `postgres123`

**Time**: 5-10 minutes

---

### Step 2: Setup Database

**Open a NEW PowerShell window (normal, not admin)**, then:

```powershell
cd C:\Users\Victoria\oreilus
.\setup-database.ps1
```

**What this does:**
- Creates the `oreilus` database
- Creates the `oreilus_user` database user
- Sets up permissions

**You'll be asked for:**
- The `postgres` password you set in Step 1

**Time**: 1 minute

---

### Step 3: Configure O.R.E.I.L.U.S.

Before running this, **get your Claude API key**:

1. Go to: https://console.anthropic.com/
2. Sign up or log in
3. Add a payment method (they give $5 free credit)
4. Click "API Keys" → "Create Key"
5. Copy the key (starts with `sk-ant-`)

**Then run:**

```powershell
.\configure-env.ps1
```

**What this does:**
- Creates your `.env` configuration file
- Asks for your Claude API key
- Optionally configures Telegram bot
- Generates security keys

**You'll be asked for:**
1. **Claude API key** (required)
2. **Telegram bot token** (optional - you can skip)
3. **Telegram user ID** (optional - you can skip)
4. **Master password** (choose something secure)

**Time**: 2 minutes

---

### Step 4: Start O.R.E.I.L.U.S.

```powershell
.\start-oreilus.ps1
```

**What this does:**
- Starts PostgreSQL and Redis services
- Installs Python dependencies
- Installs Node.js dependencies
- Starts the backend API (port 8000)
- Starts the frontend dashboard (port 3000)
- Opens http://localhost:3000 in your browser

**Time**: First run: 5-10 minutes (installing dependencies)
**Time**: Subsequent runs: 10 seconds

**You'll see two new PowerShell windows open:**
- **Backend window** - Shows API logs
- **Frontend window** - Shows web server logs

**Keep both windows open while using O.R.E.I.L.U.S.**

---

## 🎉 Testing O.R.E.I.L.U.S.

Once the browser opens:

1. **You should see**: O.R.E.I.L.U.S. Mission Control interface

2. **Send a test message**:
   ```
   Hello O.R.E.I.L.U.S., introduce yourself and explain your capabilities.
   ```

3. **Expected response**:
   - British butler-style greeting
   - Professional tone
   - Lists of capabilities
   - Strategic business focus

4. **Verify features**:
   - Messages appear in chat
   - Refresh page - conversation persists
   - Check system status (green dot in top-right)

---

## 📱 Optional: Test Telegram Bot

If you configured Telegram:

1. Open Telegram
2. Search for your bot by username
3. Click "Start" or send `/start`
4. Send: `What are your capabilities?`
5. You should get the same British butler response

---

## 🛠️ Troubleshooting

### "PostgreSQL service not found"

**Fix:**
```powershell
# List all services with 'postgres' in the name
Get-Service | Where-Object {$_.Name -like "*postgres*"}

# Start the service manually
Start-Service -Name "postgresql-x64-16"
```

### "Cannot connect to database"

**Fix:**
```powershell
# Check if PostgreSQL is running
Get-Service -Name "postgresql-x64-16"

# If stopped, start it
Start-Service -Name "postgresql-x64-16"

# Wait 10 seconds, then try again
```

### "Claude API error: Invalid API key"

**Fix:**
1. Check your API key at https://console.anthropic.com/
2. Make sure you copied the full key
3. Edit `.env` file and update `ANTHROPIC_API_KEY`
4. Restart O.R.E.I.L.U.S.

### "Port 8000 already in use"

**Fix:**
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

### Backend crashes immediately

**Check logs:**
1. Look at the Backend PowerShell window
2. Read the error message
3. Common issues:
   - Database not running
   - Wrong password in `.env`
   - Missing API key

### Frontend shows blank page

**Fix:**
1. Open browser console (F12)
2. Check for errors
3. Make sure backend started successfully first
4. Try: http://localhost:8000/health (should show "healthy")

---

## 📂 Quick Reference

### Important Files

```
C:\Users\Victoria\oreilus\
├── .env                          ← Your configuration
├── start-oreilus.ps1             ← Start everything
├── configure-env.ps1             ← Reconfigure settings
├── INSTALL.md                    ← This file
├── README.md                     ← Full documentation
└── SETUP_GUIDE.md                ← Detailed guide
```

### Important Commands

```powershell
# Start O.R.E.I.L.U.S.
.\start-oreilus.ps1

# Reconfigure (if you need to change API keys)
.\configure-env.ps1

# Check PostgreSQL status
Get-Service postgresql-x64-16

# Start PostgreSQL manually
Start-Service postgresql-x64-16

# Check Redis/Memurai status
Get-Service Memurai

# Start Redis manually
Start-Service Memurai
```

### Important URLs

- **Web Interface**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **System Status**: http://localhost:8000/api/system/status

---

## 🔄 Daily Usage

### Starting O.R.E.I.L.U.S.

```powershell
cd C:\Users\Victoria\oreilus
.\start-oreilus.ps1
```

Wait for browser to open, then start chatting!

### Stopping O.R.E.I.L.U.S.

1. Close the **Backend** PowerShell window (or press Ctrl+C)
2. Close the **Frontend** PowerShell window (or press Ctrl+C)
3. Close the browser tab

**Services (PostgreSQL, Redis) will keep running in the background** - this is normal and fine.

---

## 🎯 Next Steps

Once everything is working:

1. **Explore capabilities** - Ask O.R.E.I.L.U.S. about:
   - Business strategy
   - Market analysis
   - System optimization
   - LUCIUS, GREECE, ION Systems

2. **Phase 2** - Enhanced dashboard with metrics (when ready)

3. **Phase 3** - Automation engine for daily reports (when ready)

4. **Phase 4** - VPS deployment for 24/7 access (when ready)

---

## 💰 Cost Tracking

Monitor your Claude API usage:
- Dashboard: https://console.anthropic.com/
- View usage and billing
- Set up usage alerts

**Typical costs:**
- Testing: $1-2/day
- Normal usage: $10-20/month
- Heavy usage: $30-50/month

---

## ✅ Installation Complete!

You're now ready to use O.R.E.I.L.U.S. as your strategic business AI advisor!

**Need help?** Check:
1. Backend PowerShell window for errors
2. http://localhost:8000/api/system/status for system health
3. README.md for full documentation

---

**O.R.E.I.L.U.S.** - Your empire architect awaits your command. 🚀
