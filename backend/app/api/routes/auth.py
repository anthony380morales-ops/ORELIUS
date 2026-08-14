"""
Authentication API Routes
Login, token refresh, and API key management
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ...core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    create_api_key_token,
    get_current_user
)
from ...config import settings
from ...utils.logger import logger
from datetime import timedelta


router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model"""
    user_id: str
    password: str


class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class APIKeyRequest(BaseModel):
    """API key creation request"""
    name: str
    expires_days: int = 365


class APIKeyResponse(BaseModel):
    """API key response"""
    api_key: str
    name: str
    expires_days: int


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login endpoint - authenticate with master password

    Only Anthony Morales can access this system
    """
    # Verify master password
    if request.password != settings.master_password:
        logger.warning(f"Failed login attempt for user {request.user_id}")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    # Verify user is in allowed list
    allowed_users = settings.telegram_allowed_users.split(",") if settings.telegram_allowed_users else []

    if request.user_id not in allowed_users:
        logger.warning(f"Unauthorized login attempt from user {request.user_id}")
        raise HTTPException(
            status_code=403,
            detail="Access denied: You are not authorized to access this system",
        )

    # Create tokens
    access_token = create_access_token(request.user_id)
    refresh_token = create_refresh_token(request.user_id)

    logger.info(f"Successful login for user {request.user_id}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600
    )


@router.post("/auth/refresh", response_model=LoginResponse)
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    """
    try:
        # Verify refresh token
        payload = verify_token(request.refresh_token)

        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")

        # Create new tokens
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        logger.info(f"Token refreshed for user {user_id}")

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Token refresh failed",
        )


@router.post("/auth/api-key", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Create API key for automation/external services

    Requires valid JWT access token
    """
    # Create API key
    api_key = create_api_key_token(request.name, request.expires_days)

    logger.info(f"API key created: {request.name} (expires in {request.expires_days} days)")

    return APIKeyResponse(
        api_key=api_key,
        name=request.name,
        expires_days=request.expires_days
    )


@router.get("/auth/me")
async def get_current_user_info(current_user: str = Depends(get_current_user)):
    """
    Get current authenticated user info
    """
    return {
        "user_id": current_user,
        "system": "O.R.E.I.L.U.S.",
        "role": "master"
    }
