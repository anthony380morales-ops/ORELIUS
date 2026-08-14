"""
O.R.E.I.L.U.S. Configuration Module
Loads and manages all system configuration from environment variables
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "O.R.E.I.L.U.S."
    environment: str = "development"
    log_level: str = "INFO"
    timezone: str = "America/Los_Angeles"

    # Database
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Claude API
    anthropic_api_key: str

    # Telegram
    telegram_bot_token: str
    telegram_allowed_users: str = ""  # Comma-separated user IDs

    # Google Sheets
    google_sheets_credentials_file: str = "./google-credentials.json"
    google_sheet_id_trends: str = ""
    google_sheet_id_banking: str = ""

    # Social Media APIs (Phase 3+)
    instagram_username: str = ""
    instagram_password: str = ""
    facebook_username: str = ""
    facebook_password: str = ""
    linkedin_username: str = ""
    linkedin_password: str = ""
    x_username: str = ""
    x_password: str = ""
    x_bearer_token: str = ""
    tiktok_username: str = ""
    tiktok_password: str = ""
    tiktok_session_id: str = ""
    facebook_access_token: str = ""
    linkedin_access_token: str = ""

    # Security
    jwt_secret_key: str
    encryption_key: str
    master_password: str

    # URLs
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def allowed_telegram_users(self) -> list[int]:
        """Parse comma-separated telegram user IDs"""
        if not self.telegram_allowed_users:
            return []
        return [int(uid.strip()) for uid in self.telegram_allowed_users.split(",") if uid.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"

    @property
    def google_sheets_trends_id(self) -> str:
        """Google Sheets ID for content trends"""
        return self.google_sheet_id_trends

    @property
    def google_sheets_banking_id(self) -> str:
        """Google Sheets ID for banking intelligence"""
        return self.google_sheet_id_banking


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
