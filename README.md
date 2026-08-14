# O.R.E.I.L.U.S. - Optimized Revenue Engine & Intelligent Logistics Unified System

An autonomous AI agent powered by Claude Sonnet 4.5, designed for strategic business advisory, market intelligence, and systems optimization.

## 🚀 Phase 1 Features (MVP)

✅ **Core AI Agent** - O.R.E.I.L.U.S. with British butler persona
✅ **Web Chat Interface** - Mission control dashboard
✅ **Telegram Bot** - Mobile access via Telegram
✅ **Conversation Memory** - Persistent chat history
✅ **Security Layer** - Prompt injection protection, audit logging
✅ **WebSocket Support** - Real-time streaming responses
✅ **System Monitoring** - Health checks and metrics

## 📋 Prerequisites

- **Docker & Docker Compose** (recommended) OR
- **Python 3.11+** and **Node.js 20+** (manual setup)
- **Anthropic API Key** (Claude API)
- **Telegram Bot Token** (optional, for mobile access)

## 🔧 Quick Start with Docker (Recommended)

### 1. Clone and Setup

```bash
cd C:\Users\Victoria\oreilus
```

### 2. Configure Environment

Copy the example env file and fill in your API keys:

```bash
copy .env.example .env
```

Edit `.env` and add:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
JWT_SECRET_KEY=your-random-secret-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key-here
MASTER_PASSWORD=your-master-password-here

# Optional (for Telegram)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ALLOWED_USERS=your-telegram-user-id

# Database (auto-configured by Docker)
POSTGRES_PASSWORD=oreilus_password
REDIS_PASSWORD=oreilus_redis
```

**Generate secure keys:**

```bash
# JWT Secret (32+ characters)
openssl rand -base64 32

# Encryption Key (32 bytes)
openssl rand -hex 32
```

### 3. Start All Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Backend API (port 8000)
- Frontend dashboard (port 3000)

### 4. Access O.R.E.I.L.U.S.

- **Web Interface**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 5. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 6. Stop Services

```bash
docker-compose down
```

## 🛠️ Manual Setup (Without Docker)

### Backend Setup

1. **Install Python dependencies:**

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **Set up PostgreSQL:**

Install PostgreSQL and create database:

```sql
CREATE DATABASE oreilus;
CREATE USER oreilus_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE oreilus TO oreilus_user;
```

3. **Set up Redis:**

Install Redis and start the server.

4. **Configure environment:**

Create `.env` in backend directory with your settings.

5. **Run backend:**

```bash
python -m app.main
```

Backend runs on http://localhost:8000

### Frontend Setup

1. **Install Node dependencies:**

```bash
cd frontend
npm install
```

2. **Run frontend:**

```bash
npm run dev
```

Frontend runs on http://localhost:3000

## 📱 Telegram Bot Setup

1. **Create bot with BotFather:**

Open Telegram and message [@BotFather](https://t.me/BotFather):

```
/newbot
```

Follow prompts to get your bot token.

2. **Get your Telegram User ID:**

Message [@userinfobot](https://t.me/userinfobot) to get your user ID.

3. **Add to `.env`:**

```env
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ALLOWED_USERS=your-user-id
```

4. **Start chatting:**

Find your bot on Telegram and send `/start`

## 🔒 Security Features

- **Prompt Injection Detection** - Automatically blocks manipulation attempts
- **User Authorization** - Whitelist-only access for Telegram
- **Input Sanitization** - Cleans and validates all inputs
- **Audit Logging** - All actions logged with severity levels
- **Zero-Trust Architecture** - Every request authenticated

## 📊 API Endpoints

### Chat

- `POST /api/chat` - Send message (non-streaming)
- `POST /api/chat/stream` - Send message (streaming)
- `WS /ws/{user_id}` - WebSocket real-time chat

### System

- `GET /api/system/status` - System health & status
- `GET /api/system/logs` - Audit logs
- `GET /api/system/metrics` - Usage metrics

### Conversations

- `GET /api/conversations/{user_id}` - User's conversations
- `GET /api/conversations/{id}/messages` - Conversation messages

## 🎯 O.R.E.I.L.U.S. Capabilities

O.R.E.I.L.U.S. is designed to:

✅ **Optimize the Master's life**
✅ **Strategic business planning**
✅ **Market intelligence analysis**
✅ **Systems architecture & optimization**
✅ **Cybersecurity strategy**
✅ **Business expansion opportunities**
✅ **Revenue-producing trend identification**

### Supported Systems

- **LUCIUS** - Automation & data retention
- **GREECE** - Appointment extraction & calendar integration
- **ION Systems** - Client acquisition & lead validation (NXG Life Group)
- **The Blueprint Collective** - Banking intelligence & IBC education

## 🧪 Testing

### Test Chat API

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "message": "Hello O.R.E.I.L.U.S., what are you capable of?",
    "source": "web"
  }'
```

### Test System Status

```bash
curl http://localhost:8000/api/system/status
```

## 📝 Troubleshooting

### Backend won't start

1. Check Claude API key is valid
2. Verify PostgreSQL is running
3. Check logs: `docker-compose logs backend`

### Frontend won't connect

1. Ensure backend is running first
2. Check proxy configuration in `vite.config.ts`
3. Verify port 8000 is accessible

### Telegram bot not responding

1. Verify bot token is correct
2. Check your user ID is in `TELEGRAM_ALLOWED_USERS`
3. Ensure backend is running
4. Check logs for authorization errors

### Database errors

1. Wait for PostgreSQL to fully start (health check)
2. Check database credentials in `.env`
3. Manually connect: `docker exec -it oreilus-postgres psql -U oreilus_user -d oreilus`

## 📚 Project Structure

```
oreilus/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── core/     # O.R.E.I.L.U.S. engine, Claude client
│   │   ├── api/      # REST & WebSocket endpoints
│   │   ├── models/   # Database models
│   │   ├── telegram/ # Telegram bot
│   │   └── utils/    # Logger, helpers
│   └── requirements.txt
├── frontend/         # React dashboard
│   ├── src/
│   │   ├── components/
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml
└── .env
```

## 🚀 Next Steps (Phase 2-4)

### Phase 2: Mission Control Dashboard (Week 2)
- Real-time metrics visualization
- System health monitoring
- Audit log viewer
- Task scheduler UI

### Phase 3: Automation Engine (Week 3)
- Daily 7 AM content trend scanner
- Daily 8 AM government banking intelligence
- Google Sheets integration
- Social media scraping

### Phase 4: Full Integration (Week 4)
- All social media platforms
- AI content suggestion engine
- Production deployment to VPS
- Monitoring & backups

## 📄 License

Proprietary - All rights reserved.

## 💬 Support

For issues or questions, check logs and system status first. All security events are logged in the audit log.

---

**O.R.E.I.L.U.S.** - Your strategic business empire architect.
