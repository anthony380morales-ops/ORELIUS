"""
O.R.E.I.L.U.S. Backend - FastAPI Application
Main entry point for the API server
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .config import settings
from .database import init_db
from .utils.logger import logger
from .api.routes import chat, system, auth
import mimetypes
import os

# Correct MIME type for the PWA manifest when FastAPI serves the built frontend
mimetypes.add_type("application/manifest+json", ".webmanifest")

# Create logs directory
os.makedirs("logs", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting O.R.E.I.L.U.S. system...")
    await init_db()
    logger.info("Database initialized")

    # Validate Claude API
    from .core import oreilus_engine
    status = await oreilus_engine.validate_system()
    logger.info(f"System validation: {status}")

    # Start Telegram bot if configured
    from .telegram import telegram_bot
    if settings.telegram_bot_token:
        logger.info("Starting Telegram bot...")
        import asyncio
        asyncio.create_task(telegram_bot.start())
        logger.info("Telegram bot started")

    yield

    # Shutdown
    logger.info("Shutting down O.R.E.L.I.U.S. system...")

    # Stop Telegram bot
    if settings.telegram_bot_token:
        await telegram_bot.stop()


# Create FastAPI app
app = FastAPI(
    title="O.R.E.I.L.U.S. API",
    description="Optimized Revenue Engine & Intelligent Logistics Unified System",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS (SECURITY FIX: Restrict methods and headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", f"http://{settings.backend_url.split('//')[1].split(':')[0]}"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Only specific methods
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],  # Only specific headers
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add rate limiting middleware (SECURITY FIX)
from .core.rate_limiter import RateLimitMiddleware
app.add_middleware(
    RateLimitMiddleware,
    rate_per_minute=settings.rate_limit_per_minute,
    rate_per_hour=settings.rate_limit_per_hour
)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])  # No auth required for login
app.include_router(chat.router, prefix="/api", tags=["Chat"])  # Auth will be added to individual routes
app.include_router(system.router, prefix="/api", tags=["System"])  # Auth will be added to individual routes

# WebSocket endpoint
from .api.websocket import websocket_endpoint
from fastapi import WebSocket


@app.websocket("/ws/{user_id}")
async def websocket_route(websocket: WebSocket, user_id: str):
    """WebSocket route for real-time chat"""
    await websocket_endpoint(websocket, user_id)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# Serve the built frontend (the phone app) from the same service when present.
# This lets ORELIUS deploy as ONE container on any free host. API routes and
# /health above are registered first, so they always win over the static mount.
STATIC_DIR = os.getenv(
    "STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "static")
)
if os.path.isdir(STATIC_DIR):
    logger.info(f"Serving frontend from {STATIC_DIR}")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {
            "system": "O.R.E.L.I.U.S.",
            "version": "0.1.0",
            "status": "operational",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
