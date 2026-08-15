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

    # Claude API (ORELIUS brain)
    anthropic_api_key: str
    # Brain model: Claude Haiku 4.5 — cheapest + most efficient for high-volume daily use
    oreilus_model: str = "claude-haiku-4-5"
    oreilus_max_tokens: int = 1500          # tight cap keeps credits long-lasting
    oreilus_report_max_tokens: int = 4096   # larger cap when a full report/plan is requested
    oreilus_temperature: float = 0.7

    # --- Token & credit optimization (the credit saver) ---
    enable_prompt_caching: bool = True      # cache the persona prefix (~90% cheaper on reuse)
    enable_response_cache: bool = True      # serve identical repeat questions from cache (0 credits)
    response_cache_ttl: int = 3600          # seconds
    response_cache_max_items: int = 500
    max_history_messages: int = 12          # trim conversation history sent to the model
    max_history_tokens: int = 6000
    usage_log_path: str = "./logs/usage_tracker.json"

    # --- LUCIUS shared memory (companion link) ---
    shared_memory_path: str = "./shared_memory/orelius_lucius_memory.json"
    shared_memory_max_items: int = 300
    shared_memory_context_items: int = 6    # how many recent shared items to inject (keeps tokens low)
    lucius_api_url: str = ""                # optional: LUCIUS HTTP endpoint for two-way sync
    lucius_api_key: str = ""
    lucius_shared_secret: str = ""

    # --- ATHENA design agent (companion link) ---
    # ORELIUS delegates design work to ATHENA by writing a `design_request` event
    # to shared memory; a local bridge daemon on the user's machine drives ATHENA's
    # localhost job API and writes a `design_result` back. No direct network path
    # to ATHENA is needed (or exposed) from the cloud.
    athena_enabled: bool = True             # offer the athena_design tool to the brain
    # ATHENA is an Instagram content agent; every action revolves around a post.
    # Default to "once" (create + publish one post now) so a plain "make/publish a
    # post" request actually produces one. NOTE: "brief" only emails a plan and
    # publishes nothing — never use it as the default for publish requests.
    athena_default_action: str = "once"

    # Telegram (optional — leave blank to run ORELIUS without the Telegram bot)
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""  # Comma-separated user IDs allowed to log in

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
    def allowed_login_ids(self) -> list[str]:
        """All authorized login IDs (web + Telegram), as raw strings.

        Web login IDs can be words like 'anthony'; Telegram IDs are numbers.
        Both live in TELEGRAM_ALLOWED_USERS and are matched as strings.
        """
        if not self.telegram_allowed_users:
            return []
        return [uid.strip() for uid in self.telegram_allowed_users.split(",") if uid.strip()]

    @property
    def allowed_telegram_users(self) -> list[int]:
        """Numeric Telegram user IDs only (non-numeric login IDs are skipped)."""
        ids: list[int] = []
        for uid in self.allowed_login_ids:
            try:
                ids.append(int(uid))
            except ValueError:
                continue
        return ids

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
