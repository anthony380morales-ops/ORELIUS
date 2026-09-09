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
    # libpq / psql params that asyncpg does not understand — strip them and
    # translate SSL intent into connect_args. Neon's copyable URI ships with
    # both sslmode=require and channel_binding=require.
    sslmode = query.pop("sslmode", None)
    channel_binding = query.pop("channel_binding", None)
    for libpq_only in ("sslrootcert", "sslcert", "sslkey", "options", "target_session_attrs"):
        query.pop(libpq_only, None)
    async_url = urlunsplit(
        ("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    connect_args = {}
    wants_ssl = (sslmode and sslmode != "disable") or bool(channel_binding)
    if wants_ssl:
        connect_args["ssl"] = True
    return async_url, connect_args


_async_url, _connect_args = _build_async_db_url(settings.database_url)

# A managed free-tier Postgres (Neon) has a LOW connection ceiling and its compute
# can be suspended, so the first connection after idle must wake it. Give asyncpg an
# explicit connect timeout and keep the pool small so we never exhaust the ceiling.
_connect_args.setdefault("timeout", 30)          # seconds to establish a connection
_connect_args.setdefault("command_timeout", 60)  # seconds for a single statement

# Create async engine
engine = create_async_engine(
    _async_url,
    connect_args=_connect_args,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,       # drop dead connections instead of handing them out
    pool_size=5,              # Neon free ceiling is small — stay well under it
    max_overflow=5,
    pool_recycle=1800,        # recycle connections every 30 min (avoid server-side idle cuts)
    pool_timeout=30,
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
async def init_db(attempts: int = 6):
    """Initialize database tables, retrying while a cold/suspended DB wakes.

    A managed free-tier Postgres can be suspended after inactivity; the first
    connect on boot then times out. Rather than crash startup (exit 3), retry with
    exponential backoff so the compute has time to wake and accept the connection.
    """
    import asyncio
    from .utils.logger import logger

    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            if attempt > 1:
                logger.info(f"Database reachable on attempt {attempt}")
            return
        except Exception as e:  # noqa: BLE001 - retry any connect/DDL failure on boot
            last_err = e
            wait = min(30, 2 ** attempt)   # 2, 4, 8, 16, 30, 30 …
            logger.warning(
                f"init_db attempt {attempt}/{attempts} failed "
                f"({e.__class__.__name__}: {e}); retrying in {wait}s"
            )
            await asyncio.sleep(wait)
    logger.error(f"init_db exhausted {attempts} attempts; last error: {last_err}")
    raise last_err
