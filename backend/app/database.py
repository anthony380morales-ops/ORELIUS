"""
Database connection and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .config import settings
import redis.asyncio as aioredis

# SQLAlchemy Base
Base = declarative_base()


def _build_async_db_url(raw: str):
    """Normalize a Postgres URL for the asyncpg driver.

    Managed databases (DigitalOcean, Render, Heroku, etc.) hand out URLs like
    `postgres://…?sslmode=require`. asyncpg uses the `postgresql+asyncpg` scheme
    and does not understand libpq's `sslmode` query param, so translate it into
    a `connect_args={"ssl": True}` flag and strip it from the URL.
    """
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    parts = urlsplit(raw)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    async_url = urlunsplit(
        ("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    connect_args = {}
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = True
    return async_url, connect_args


_async_url, _connect_args = _build_async_db_url(settings.database_url)

# Create async engine
engine = create_async_engine(
    _async_url,
    connect_args=_connect_args,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Redis connection
async def get_redis():
    """Get Redis connection"""
    return await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


# Dependency for database sessions
async def get_db():
    """Get database session for dependency injection"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Initialize database (create tables)
async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
