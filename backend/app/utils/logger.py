"""
Logging configuration using loguru
"""
from loguru import logger
import sys
from ..config import settings

# Remove default handler
logger.remove()

# Add console handler with formatting
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level,
    colorize=True,
)

# Add file handler for errors
logger.add(
    "logs/oreilus_error.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level="ERROR",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
)

# Add file handler for all logs
logger.add(
    "logs/oreilus.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level="INFO",
    rotation="50 MB",
    retention="14 days",
    compression="zip",
)

__all__ = ["logger"]
