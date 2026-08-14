"""
Rate Limiting Middleware
Protects API from abuse with token bucket algorithm
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import asyncio
from ..config import settings
from ..utils.logger import logger


class RateLimiter:
    """
    Token bucket rate limiter
    """

    def __init__(self, rate_per_minute: int = 60, rate_per_hour: int = 1000):
        """
        Initialize rate limiter

        Args:
            rate_per_minute: Max requests per minute
            rate_per_hour: Max requests per hour
        """
        self.rate_per_minute = rate_per_minute
        self.rate_per_hour = rate_per_hour

        # Storage: {ip_address: {minute: count, hour: count, last_reset: datetime}}
        self.requests: Dict[str, Dict] = defaultdict(lambda: {
            "minute": 0,
            "hour": 0,
            "last_minute_reset": datetime.now(timezone.utc),
            "last_hour_reset": datetime.now(timezone.utc)
        })

        # Start cleanup task
        asyncio.create_task(self._cleanup_old_entries())

    def _reset_if_needed(self, ip: str):
        """Reset counters if time windows have passed"""
        now = datetime.now(timezone.utc)
        data = self.requests[ip]

        # Reset minute counter
        if now - data["last_minute_reset"] >= timedelta(minutes=1):
            data["minute"] = 0
            data["last_minute_reset"] = now

        # Reset hour counter
        if now - data["last_hour_reset"] >= timedelta(hours=1):
            data["hour"] = 0
            data["last_hour_reset"] = now

    def check_rate_limit(self, ip: str) -> Tuple[bool, str]:
        """
        Check if request should be allowed

        Args:
            ip: Client IP address

        Returns:
            Tuple of (is_allowed, error_message)
        """
        self._reset_if_needed(ip)
        data = self.requests[ip]

        # Check minute limit
        if data["minute"] >= self.rate_per_minute:
            logger.warning(f"Rate limit exceeded (per minute) for IP {ip}")
            return False, f"Rate limit exceeded: {self.rate_per_minute} requests per minute"

        # Check hour limit
        if data["hour"] >= self.rate_per_hour:
            logger.warning(f"Rate limit exceeded (per hour) for IP {ip}")
            return False, f"Rate limit exceeded: {self.rate_per_hour} requests per hour"

        # Increment counters
        data["minute"] += 1
        data["hour"] += 1

        return True, ""

    async def _cleanup_old_entries(self):
        """Periodically cleanup old IP entries"""
        while True:
            await asyncio.sleep(3600)  # Run every hour

            now = datetime.now(timezone.utc)
            to_remove = []

            for ip, data in self.requests.items():
                # Remove entries older than 2 hours
                if now - data["last_hour_reset"] > timedelta(hours=2):
                    to_remove.append(ip)

            for ip in to_remove:
                del self.requests[ip]

            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old rate limit entries")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting
    """

    def __init__(self, app, rate_per_minute: int = 60, rate_per_hour: int = 1000):
        super().__init__(app)
        self.limiter = RateLimiter(rate_per_minute, rate_per_hour)

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""

        # Get client IP
        client_ip = request.client.host

        # Skip rate limiting for health check and root endpoints
        if request.url.path in ["/", "/health"]:
            return await call_next(request)

        # Check rate limit
        is_allowed, error_message = self.limiter.check_rate_limit(client_ip)

        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail=error_message,
                headers={"Retry-After": "60"}
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(self.limiter.rate_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.limiter.rate_per_hour)

        return response


# Global rate limiter instance
rate_limiter = RateLimiter(
    rate_per_minute=settings.rate_limit_per_minute,
    rate_per_hour=settings.rate_limit_per_hour
)
