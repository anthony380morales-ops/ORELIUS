# O.R.E.I.L.U.S. Cloud VPS Deployment Guide
**Goal**: Deploy to DigitalOcean for true 24/7 autonomous operation
**Time Required**: 2-3 hours
**Cost**: $12/month

---

## Step 1: Create DigitalOcean Account (15 minutes)

### 1.1 Sign Up
1. Go to: https://www.digitalocean.com
2. Click "Sign Up"
3. Use email: anthony380.morales@gmail.com (or your preferred email)
4. Create strong password
5. Verify email

### 1.2 Add Payment Method
1. Click "Billing" in left sidebar
2. Add credit card OR link PayPal
3. You can use promo codes if available (often $200 credit for new accounts)

### 1.3 Create Your First Droplet
1. Click "Create" â†’ "Droplets"
2. Choose these settings:

**Region**:
- Choose closest to you: San Francisco (SF3) or Los Angeles

**Image**:
- Distribution: **Ubuntu 22.04 LTS**

**Droplet Type**:
- **Basic**
- CPU Options: **Regular**
- Size: **$12/month** (1 GB RAM / 1 CPU / 25 GB SSD)

**Authentication**:
- Choose: **Password** (easier for first time)
- Create a strong root password and SAVE IT

**Hostname**:
- Name it: `oreilus-production`

3. Click "Create Droplet"
4. Wait 1-2 minutes for creation
5. You'll see an **IP address** (e.g., 164.90.123.45) - SAVE THIS

---

## Step 2: Connect to Your VPS (10 minutes)

### 2.1 From Windows (Using PowerShell)

Open PowerShell and connect via SSH:
```powershell
ssh root@YOUR_IP_ADDRESS
```

Replace `YOUR_IP_ADDRESS` with the IP from Step 1.3

**Example**:
```powershell
ssh root@164.90.123.45
```

### First Connection:
- It will ask "Are you sure you want to continue connecting?" â†’ Type `yes`
- Enter the root password you created
- You're now connected to your VPS!

You should see something like:
```
root@oreilus-production:~#
```

---

## Step 3: Initial Server Setup (20 minutes)

### 3.1 Update System
```bash
apt update && apt upgrade -y
```

### 3.2 Install Required Software
```bash
# Install Python 3.11
apt install -y python3.11 python3.11-venv python3-pip

# Install PostgreSQL
apt install -y postgresql postgresql-contrib

# Install Redis
apt install -y redis-server

# Install Git
apt install -y git

# Install Nginx (web server for frontend)
apt install -y nginx

# Install system dependencies
apt install -y build-essential libssl-dev libffi-dev python3-dev
```

### 3.3 Set Up PostgreSQL Database
```bash
# Switch to postgres user
sudo -u postgres psql

# Inside PostgreSQL prompt, run:
CREATE DATABASE oreilus;
CREATE USER oreilus_user WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE oreilus TO oreilus_user;
\q
```

**IMPORTANT**: Replace `your_secure_password_here` with a strong password and SAVE IT

### 3.4 Configure Redis
```bash
# Start Redis
systemctl start redis-server
systemctl enable redis-server

# Test Redis
redis-cli ping
# Should return: PONG
```

---

## Step 4: Deploy O.R.E.I.L.U.S. Backend (30 minutes)

### 4.1 Create Application Directory
```bash
mkdir -p /opt/oreilus
cd /opt/oreilus
```

### 4.2 Upload Your Code

**Option A: Using Git (if you have a repository)**
```bash
git clone YOUR_REPO_URL .
```

**Option B: Upload via SCP from your laptop**

Open a NEW PowerShell window on your laptop (keep SSH session open):
```powershell
# Navigate to your project
cd C:\Users\Victoria\oreilus

# Upload backend directory
scp -r backend root@YOUR_IP_ADDRESS:/opt/oreilus/

# Upload google credentials
scp google-credentials.json root@YOUR_IP_ADDRESS:/opt/oreilus/
```

### 4.3 Create Virtual Environment on VPS
```bash
cd /opt/oreilus/backend
python3.11 -m venv venv
source venv/bin/activate
```

### 4.4 Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install-deps
```

### 4.5 Create Environment File
```bash
cd /opt/oreilus
nano .env
```

**Paste this content** (update with your actual values):
```env
# Database (use VPS PostgreSQL)
DATABASE_URL=postgresql://oreilus_user:your_secure_password_here@localhost:5432/oreilus
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
FRONTEND_URL=http://YOUR_IP_ADDRESS
BACKEND_URL=http://YOUR_IP_ADDRESS:8000
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
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

### 4.6 Initialize Database
```bash
cd /opt/oreilus/backend
source venv/bin/activate
python -m alembic upgrade head
```

---

## Step 5: Create Systemd Service for 24/7 Operation (15 minutes)

### 5.1 Create Service File
```bash
nano /etc/systemd/system/oreilus.service
```

**Paste this content**:
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

[Install]
WantedBy=multi-user.target
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

### 5.2 Enable and Start Service
```bash
# Reload systemd
systemctl daemon-reload

# Enable service (auto-start on boot)
systemctl enable oreilus

# Start service now
systemctl start oreilus

# Check status
systemctl status oreilus
```

You should see: **Active: active (running)**

### 5.3 Test Backend
```bash
curl http://localhost:8000
```

Should return:
```json
{"system":"O.R.E.I.L.U.S.","version":"0.1.0","status":"operational"}
```

---

## Step 6: Configure Firewall (10 minutes)

### 6.1 Set Up UFW Firewall
```bash
# Allow SSH (important!)
ufw allow 22/tcp

# Allow backend API
ufw allow 8000/tcp

# Allow HTTP/HTTPS for frontend
ufw allow 80/tcp
ufw allow 443/tcp

# Enable firewall
ufw enable

# Check status
ufw status
```

---

## Step 7: Test Everything (15 minutes)

### 7.1 Test Backend from Internet

On your laptop, open browser to:
```
http://YOUR_IP_ADDRESS:8000
```

Should show JSON response.

### 7.2 Test Telegram Bot

Send a message to your Telegram bot from your phone.
Should get response (even with laptop OFF!).

### 7.3 Test Automation

```bash
# SSH into VPS
ssh root@YOUR_IP_ADDRESS

# Check scheduled jobs
curl http://localhost:8000/api/automation/jobs
```

Should show jobs scheduled for 7 AM and 8 AM PST.

### 7.4 Manual Trigger Test

```bash
# Trigger content scanner manually
curl -X POST http://localhost:8000/api/automation/trigger/content_trend_scanner

# Check Google Sheets - should see new data
```

---

## Step 8: Deploy Frontend (Optional - 30 minutes)

### 8.1 Build Frontend on Laptop
```powershell
cd C:\Users\Victoria\oreilus\frontend

# Update API URL in .env
# Create .env.production file:
VITE_API_URL=http://YOUR_IP_ADDRESS:8000

# Build production version
npm run build
```

### 8.2 Upload Frontend to VPS
```powershell
# Upload build directory
scp -r dist root@YOUR_IP_ADDRESS:/var/www/oreilus
```

### 8.3 Configure Nginx on VPS
```bash
nano /etc/nginx/sites-available/oreilus
```

**Paste**:
```nginx
server {
    listen 80;
    server_name YOUR_IP_ADDRESS;

    root /var/www/oreilus;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Save and enable**:
```bash
ln -s /etc/nginx/sites-available/oreilus /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Now access dashboard at: `http://YOUR_IP_ADDRESS`

---

## Step 9: Verify 24/7 Operation (Final Test)

### 9.1 Turn Off Your Laptop

Yes, completely turn it off!

### 9.2 Test from Phone

1. Send Telegram message to bot â†’ Should get response
2. Open browser on phone to `http://YOUR_IP_ADDRESS:8000` â†’ Should see JSON

### 9.3 Wait for Tomorrow Morning

- 7:00 AM PST: Content scanner runs automatically
- 8:00 AM PST: Intel scanner runs automatically
- Check Google Sheets after 8 AM â†’ Should have new data

**Your laptop can be OFF, ASLEEP, or ANYWHERE. System keeps running!**

---

## Maintenance & Monitoring

### View Backend Logs
```bash
# Real-time logs
journalctl -u oreilus -f

# Last 100 lines
journalctl -u oreilus -n 100

# Logs from today
journalctl -u oreilus --since today
```

### Restart Backend
```bash
systemctl restart oreilus
```

### Check Backend Status
```bash
systemctl status oreilus
```

### Update Code (After Changes)
```bash
cd /opt/oreilus/backend
git pull  # if using git
systemctl restart oreilus
```

---

## Troubleshooting

### Backend Won't Start
```bash
# Check logs
journalctl -u oreilus -n 50

# Test manually
cd /opt/oreilus/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Can't Connect from Internet
```bash
# Check firewall
ufw status

# Make sure port 8000 is open
ufw allow 8000/tcp
```

### Telegram Bot Not Responding
```bash
# Check if backend is running
curl http://localhost:8000

# Check logs for errors
journalctl -u oreilus | grep -i telegram
```

---

## Cost Summary

**Monthly Costs**:
- DigitalOcean Droplet: $12/month
- **Total: $12/month**

**What You Get**:
- âœ“ True 24/7 operation
- âœ“ Works even when laptop is off
- âœ“ 99.99% uptime
- âœ“ Always connected to internet
- âœ“ Professional infrastructure
- âœ“ Can travel anywhere with laptop

---

## Next Steps After Deployment

1. âœ“ Verify Telegram bot responds (laptop off)
2. âœ“ Wait for tomorrow's 7 AM & 8 AM automation
3. âœ“ Check Google Sheets after 8 AM
4. âœ“ Stop local laptop backend (no longer needed)
5. âœ“ Update any bookmarks to use VPS IP instead of localhost

---

**Ready to deploy? Let me know when you've created the DigitalOcean account and I'll guide you through each step!**

