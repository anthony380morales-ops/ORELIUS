# 🚀 O.R.E.I.L.U.S. Setup Guide

Complete step-by-step guide to get your AI agent running.

---

## 📋 Quick Setup Checklist

- [ ] Get Claude API key
- [ ] Get Telegram bot token (optional)
- [ ] Install Docker OR Python + PostgreSQL
- [ ] Configure .env file
- [ ] Start the system
- [ ] Open http://localhost:3000

---

## 🔑 STEP 1: Get Your API Keys

### Claude API Key (REQUIRED)

1. **Go to**: https://console.anthropic.com/
2. **Sign up/Login** with your email
3. **Add payment method** (they give $5 free credit to start)
4. Click **"API Keys"** in the left menu
5. Click **"Create Key"**
6. Name it "OREILUS" and click **Create**
7. **COPY THE KEY** (starts with `sk-ant-api-`)
   - ⚠️ Save it somewhere safe - you can't see it again!

**Pricing**:
- Input: ~$3 per 1M tokens (very cheap)
- Output: ~$15 per 1M tokens
- For testing: ~$1-2/day
- For normal usage: ~$10-20/month

### Telegram Bot Token (OPTIONAL - for mobile access)

1. Open Telegram app
2. Search for **@BotFather**
3. Send: `/newbot`
4. Follow prompts:
   - Bot name: "OREILUS Bot" (or any name)
   - Username: "oreilus_yourname_bot" (must end with 'bot')
5. **COPY THE TOKEN** (looks like `123456:ABC-DEF...`)
6. Search for **@userinfobot**
7. Send: `/start`
8. **COPY YOUR USER ID** (a number like `123456789`)

---

## 💻 STEP 2: Choose Your Installation Method

### Method A: Docker (Recommended - Easy)

**What is Docker?**
- One command installs everything (database, backend, frontend)
- Easiest and cleanest setup
- Best for beginners

**Installation:**

1. Download Docker Desktop:
   - Go to: https://www.docker.com/products/docker-desktop/
   - Click **"Download for Windows"**
   - Run the installer (takes 5-10 minutes)
   - Restart your computer when prompted

2. Verify installation:
   - Open PowerShell
   - Type: `docker --version`
   - Should show: `Docker version 24.x.x`

**Then jump to STEP 3**

---

### Method B: Manual Setup (No Docker)

**What you'll need:**
- Python 3.11+
- PostgreSQL database
- Redis server
- Node.js 20+

**Installation:**

#### 2.1: Install Python

1. Go to: https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. Run installer
   - ✅ CHECK "Add Python to PATH"
   - Click "Install Now"
4. Verify: Open PowerShell and type `python --version`

#### 2.2: Install PostgreSQL

1. Go to: https://www.postgresql.org/download/windows/
2. Download installer (version 16)
3. Run installer:
   - Password: Choose a password (remember it!)
   - Port: 5432 (default)
   - Locale: Default
4. Open **pgAdmin 4** (installed with PostgreSQL)
5. Create database:
   - Right-click "Databases" → Create → Database
   - Database name: `oreilus`
   - Click Save

#### 2.3: Install Redis

1. Go to: https://github.com/microsoftarchive/redis/releases
2. Download: `Redis-x64-3.0.504.msi`
3. Run installer (use defaults)
4. Redis will auto-start as a service

#### 2.4: Install Node.js

1. Go to: https://nodejs.org/
2. Download LTS version (20.x)
3. Run installer (use defaults)
4. Verify: `node --version`

**Then jump to STEP 3**

---

## ⚙️ STEP 3: Configure O.R.E.I.L.U.S.

1. Open PowerShell and navigate to project:
   ```powershell
   cd C:\Users\Victoria\oreilus
   ```

2. Create your `.env` file:
   ```powershell
   copy .env.example .env
   ```

3. Open `.env` in Notepad:
   ```powershell
   notepad .env
   ```

4. Fill in your values:

```env
# ========================================
# REQUIRED: Claude API (get from console.anthropic.com)
# ========================================
ANTHROPIC_API_KEY=sk-ant-api-YOUR-KEY-HERE

# ========================================
# OPTIONAL: Telegram Bot
# ========================================
TELEGRAM_BOT_TOKEN=123456:ABC-YOUR-BOT-TOKEN
TELEGRAM_ALLOWED_USERS=123456789

# ========================================
# Database (LEAVE AS-IS for Docker)
# ========================================
DATABASE_URL=postgresql://oreilus_user:oreilus_password@localhost:5432/oreilus
REDIS_URL=redis://localhost:6379/0
POSTGRES_PASSWORD=oreilus_password
REDIS_PASSWORD=oreilus_redis

# ========================================
# Security Keys (GENERATE NEW ONES!)
# ========================================
# Generate with: openssl rand -base64 32
JWT_SECRET_KEY=REPLACE-WITH-RANDOM-KEY-HERE

# Generate with: openssl rand -hex 32
ENCRYPTION_KEY=REPLACE-WITH-RANDOM-HEX-HERE

# Your master password
MASTER_PASSWORD=ChooseAStrongPasswordHere123!

# ========================================
# System Configuration
# ========================================
TIMEZONE=America/Los_Angeles
LOG_LEVEL=INFO
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

5. **Generate secure keys** (if you have Git Bash or OpenSSL):
   ```bash
   openssl rand -base64 32  # Use for JWT_SECRET_KEY
   openssl rand -hex 32     # Use for ENCRYPTION_KEY
   ```

   **OR use these example keys for testing** (NOT for production):
   ```
   JWT_SECRET_KEY=sXp8vQ2mK9nR4wL7tY6cJ3bH5gF8dA1zN0xM
   ENCRYPTION_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
   ```

6. **Save the file** (Ctrl+S) and close Notepad

---

## 🚀 STEP 4: Start O.R.E.I.L.U.S.

### If using Docker:

1. Open PowerShell in the project folder:
   ```powershell
   cd C:\Users\Victoria\oreilus
   ```

2. Start everything:
   ```powershell
   docker-compose up -d
   ```

3. Wait 30 seconds for everything to start

4. Check status:
   ```powershell
   docker-compose ps
   ```

   You should see 4 services running:
   - oreilus-postgres
   - oreilus-redis
   - oreilus-backend
   - oreilus-frontend

5. View logs (if needed):
   ```powershell
   docker-compose logs -f backend
   ```

### If using Manual Setup:

#### Terminal 1 - Start Backend:
```powershell
cd C:\Users\Victoria\oreilus\backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

#### Terminal 2 - Start Frontend:
```powershell
cd C:\Users\Victoria\oreilus\frontend
npm install
npm run dev
```

---

## 🎉 STEP 5: Access O.R.E.I.L.U.S.

1. **Open your browser**: http://localhost:3000

2. **Send your first message**:
   ```
   Hello O.R.E.I.L.U.S., introduce yourself and tell me your capabilities.
   ```

3. **Expected response**:
   - You should see O.R.E.I.L.U.S. respond in British butler style
   - Professional, analytical, strategic advice

### Other URLs:

- **API Documentation**: http://localhost:8000/docs
- **System Status**: http://localhost:8000/api/system/status
- **Health Check**: http://localhost:8000/health

### Test Telegram (if configured):

1. Open Telegram
2. Search for your bot username
3. Send: `/start`
4. Send: "What can you do?"

---

## 🛠️ Troubleshooting

### "Docker is not running"
- Open Docker Desktop application
- Wait for it to say "Docker Desktop is running"
- Try again

### "Cannot connect to backend"
- Check backend is running: `docker-compose ps`
- Check logs: `docker-compose logs backend`
- Verify port 8000 is free: `netstat -ano | findstr :8000`

### "Claude API error"
- Verify your API key is correct in `.env`
- Check you have credits: https://console.anthropic.com/
- Look for error in logs: `docker-compose logs backend`

### "Database connection error"
- Wait 30 seconds for PostgreSQL to start
- Check PostgreSQL is running: `docker-compose ps postgres`
- Restart: `docker-compose restart postgres`

### Frontend shows blank page
- Check browser console (F12)
- Verify backend is running first
- Check frontend logs: `docker-compose logs frontend`

### Telegram bot not responding
- Verify bot token is correct
- Verify your user ID is in TELEGRAM_ALLOWED_USERS
- Check backend logs: `docker-compose logs backend | findstr telegram`

---

## 📝 Common Commands

```powershell
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Restart a service
docker-compose restart backend

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Check what's running
docker-compose ps

# Rebuild after code changes
docker-compose up -d --build

# Stop and remove everything (including data!)
docker-compose down -v
```

---

## ✅ Success Checklist

After setup, verify:

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Database (PostgreSQL) running
- [ ] Redis running
- [ ] Can open http://localhost:3000
- [ ] Can send messages to O.R.E.I.L.U.S.
- [ ] O.R.E.I.L.U.S. responds in British butler style
- [ ] Messages are saved (refresh page, history persists)
- [ ] Telegram bot responds (if configured)

---

## 🎯 Next Steps

Once everything is working:

1. **Test the agent** - Have conversations, test capabilities
2. **Review Phase 2** - Enhanced dashboard with metrics
3. **Plan Phase 3** - Automation engine for daily reports
4. **Deploy to VPS** - Make it 24/7 accessible

---

## 💬 Need Help?

If you're stuck:

1. Check the logs: `docker-compose logs -f`
2. Check system status: http://localhost:8000/api/system/status
3. Review error messages carefully
4. Check `.env` file has all required values
5. Ensure Docker Desktop is running
6. Restart everything: `docker-compose down && docker-compose up -d`

---

**Ready to activate your AI empire architect!** 🚀
