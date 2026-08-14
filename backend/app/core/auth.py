"""
Authentication and Authorization Module
JWT-based authentication for API endpoints
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..config import settings
from ..utils.logger import logger

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days

security = HTTPBearer()


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        user_id: User identifier
        expires_delta: Token expiration time

    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str) -> str:
    """
    Create JWT refresh token

    Args:
        user_id: User identifier

    Returns:
        JWT refresh token string
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])

        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing required fields",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Dependency to get current authenticated user

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        User ID from token

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    payload = verify_token(token)

    # Verify token type is access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    return user_id


async def verify_master_user(user_id: str = Depends(get_current_user)) -> str:
    """
    Dependency to verify user is Anthony Morales (master user)

    Args:
        user_id: User ID from token

    Returns:
        User ID if authorized

    Raises:
        HTTPException: If user is not the master user
    """
    # Check if user is in allowed list (Anthony's Telegram ID)
    allowed_users = settings.telegram_allowed_users.split(",") if settings.telegram_allowed_users else []

    if user_id not in allowed_users:
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        raise HTTPException(
            status_code=403,
            detail="Access denied: You are not authorized to access this system",
        )

    return user_id


def create_api_key_token(name: str, expires_days: Optional[int] = None) -> str:
    """
    Create API key for automation/external services

    Args:
        name: API key name/purpose
        expires_days: Optional expiration in days

    Returns:
        API key token
    """
    if expires_days:
        expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=365)  # 1 year default

    to_encode = {
        "sub": "api_key",
        "name": name,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "api_key"
    }

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Verify API key for automation endpoints

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        API key payload

    Raises:
        HTTPException: If API key is invalid
    """
    token = credentials.credentials
    payload = verify_token(token)

    # Verify token type is API key
    if payload.get("type") != "api_key":
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
