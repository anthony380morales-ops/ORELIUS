# O.R.E.I.L.U.S. VPS Deployment - Command List
**VPS IP**: 146.190.162.19
**Follow these commands in order**

---

## STEP 1: Connect to VPS

```powershell
# Run this on your laptop PowerShell
ssh root@146.190.162.19
```

Type `yes` when asked, then enter your root password.

---

## STEP 2: Update System (Run on VPS)

```bash
apt update && apt upgrade -y
```

Wait for completion (~2-3 minutes).

---

## STEP 3: Install Required Software

```bash
# Install Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# Install PostgreSQL
apt install -y postgresql postgresql-contrib

# Install Redis
apt install -y redis-server

# Install Git and build tools
apt install -y git build-essential libssl-dev libffi-dev python3-dev

# Install Nginx
apt install -y nginx
```

Wait for completion (~5 minutes).

---

## STEP 4: Set Up PostgreSQL Database

```bash
# Switch to postgres user and create database
sudo -u postgres psql
```

You'll see `postgres=#` prompt. Now run:

```sql
CREATE DATABASE oreilus;
CREATE USER oreilus_user WITH PASSWORD 'OREILUSdb2026$Secure';
GRANT ALL PRIVILEGES ON DATABASE oreilus TO oreilus_user;
\q
```

---

## STEP 5: Configure Redis

```bash
systemctl start redis-server
systemctl enable redis-server
redis-cli ping
```

Should return: `PONG`

---

## STEP 6: Create Application Directory

```bash
mkdir -p /opt/oreilus
cd /opt/oreilus
```

---

## STEP 7: Upload Code from Laptop

**STOP HERE** - Open a NEW PowerShell window on your laptop (keep VPS SSH open).

Run these commands on your **LAPTOP**:

```powershell
cd C:\Users\Victoria\oreilus

# Upload backend
scp -r backend root@146.190.162.19:/opt/oreilus/

# Upload google credentials
scp google-credentials.json root@146.190.162.19:/opt/oreilus/
```

When done, come back to VPS SSH window.

---

## STEP 8: Set Up Python Environment (Run on VPS)

```bash
cd /opt/oreilus/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

This will take 5-10 minutes to install all packages.

---

## STEP 9: Install Playwright Browsers

```bash
playwright install chromium
playwright install-deps
```

---

## STEP 10: Create Environment File

```bash
cd /opt/oreilus
nano .env
```

**Copy and paste this** (nano will be open, just paste):

```env
# Database
DATABASE_URL=postgresql://oreilus_user:OREILUSdb2026$Secure@localhost:5432/oreilus
REDIS_URL=redis://localhost:6379/0

# Claude API
ANTHROPIC_API_KEY=REDACTED

# Telegram Bot
TELEGRAM_BOT_TOKEN=REDACTED
TELEGRAM_ALLOWED_USERS=5171171510

# Security Keys
JWT_SECRET_KEY=BtosHWOjw5a5Ri6FVoVQRjggJdL5TJkXfKnLm94sCC8=
ENCRYPTION_KEY=70072df79b73e290371edb03b0dd1b7b7938d3dbcfc0e10f5636c09bd2fe4bbc
MASTER_PASSWORD=N1GHtF4LL#*$

# System Configuration
TIMEZONE=America/Los_Angeles
LOG_LEVEL=INFO
ENVIRONMENT=production
FRONTEND_URL=http://146.190.162.19
BACKEND_URL=http://146.190.162.19:8000
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE=/opt/oreilus/google-credentials.json
GOOGLE_SHEET_ID_TRENDS=1yGYSpeD8AjHYtZLqJ0nVVAb7KOKm1EwDq1VJJLROxFw
GOOGLE_SHEET_ID_BANKING=1pHSIlyFwAEIHEs4L15S_i1nTsCRX58ISNNyH0Xw_7Fo

# Social Media
INSTAGRAM_USERNAME=ibluezcluezflow
INSTAGRAM_PASSWORD=L0V34TH33Money
FACEBOOK_USERNAME=Ibluezcluzflow
FACEBOOK_PASSWORD=Morales256100
LINKEDIN_USERNAME=anthony380.morales@gmail.com
LINKEDIN_PASSWORD=GUNSR7un380*$
X_USERNAME=iBluezCluezFlow
X_PASSWORD=
X_BEARER_TOKEN=
FACEBOOK_ACCESS_TOKEN=
LINKEDIN_ACCESS_TOKEN=
TIKTOK_USERNAME=
TIKTOK_PASSWORD=
TIKTOK_SESSION_ID=
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

---

## STEP 11: Initialize Database

```bash
cd /opt/oreilus/backend
source venv/bin/activate

# Create database tables
python -c "from app.database import init_db; import asyncio; asyncio.run(init_db())"
```

---

## STEP 12: Create Systemd Service

```bash
nano /etc/systemd/system/oreilus.service
```

**Paste this**:

```ini
[Unit]
Description=O.R.E.I.L.U.S. Backend Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/oreilus/backend
Environment="PATH=/opt/oreilus/backend/venv/bin"
ExecStart=/opt/oreilus/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

---

## STEP 13: Start O.R.E.I.L.U.S. Service

```bash
systemctl daemon-reload
systemctl enable oreilus
systemctl start oreilus
systemctl status oreilus
```

Should show: **Active: active (running)** in green

Press `q` to exit status view.

---

## STEP 14: Configure Firewall

```bash
ufw allow 22/tcp
ufw allow 8000/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status
```

---

## STEP 15: Test Backend

```bash
curl http://localhost:8000
```

Should return JSON with "O.R.E.I.L.U.S." and "status":"operational"

---

## STEP 16: Test from Your Laptop

**Open browser on your laptop** to:
```
http://146.190.162.19:8000
```

Should see JSON response.

---

## STEP 17: Test Telegram Bot

**From your phone**, send a message to your Telegram bot.

Should get a response (even with laptop off!).

---

## STEP 18: Test Automation

```bash
# Check scheduled jobs
curl http://localhost:8000/api/automation/jobs

# Manual trigger test
curl -X POST http://localhost:8000/api/automation/trigger/content_trend_scanner
```

Check Google Sheets - should see new data appear!

---

## STEP 19: View Logs

```bash
# Real-time logs
journalctl -u oreilus -f

# Press Ctrl+C to stop watching
```

---

## FINAL TEST: Turn Off Your Laptop!

1. Close all windows
2. Turn off your laptop completely
3. From your phone:
   - Send Telegram message to bot â†’ Should get response
   - Open browser to http://146.190.162.19:8000 â†’ Should see JSON

**SUCCESS!** O.R.E.I.L.U.S. is now truly 24/7 autonomous!

---

## Tomorrow Morning:

- 7:00 AM PST: Content scanner runs automatically
- 8:00 AM PST: Intel scanner runs automatically
- Check Google Sheets after 8 AM
- Your laptop can be OFF, system keeps running!

---

## Useful Commands:

```bash
# Check status
systemctl status oreilus

# Restart service
systemctl restart oreilus

# View logs
journalctl -u oreilus -n 100

# Follow logs live
journalctl -u oreilus -f

# Stop service
systemctl stop oreilus

# Start service
systemctl start oreilus
```

---

**Your VPS IP**: 146.190.162.19
**Backend**: http://146.190.162.19:8000
**Cost**: $12/month
**Uptime**: 24/7/365

