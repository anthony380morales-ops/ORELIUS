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

    # --- Personality learning (the "normal AI chatbot" side) ---
    # ORELIUS learns the Master's communication style over conversations and
    # tailors replies to it. This ONLY affects chat — never the finance engine.
    persona_learning_enabled: bool = True
    persona_update_every: int = 6          # refresh the profile every N exchanges
    persona_reflect_max_tokens: int = 700  # tight cap for the cheap reflection call
    persona_context_char_cap: int = 1400   # cap the profile block injected into chat

    # === Autonomous ecosystem orchestration (multi-agent social growth engine) ===
    # ORELIUS = executive brain; ATHENA = social ops; HIGGBOT = creative engine;
    # LUCIUS = owner interface. All endpoints/tokens are placeholders — set real
    # values in the environment; never commit secrets.
    athena_base_url: str = "http://127.0.0.1:8787"
    athena_api_token: str = ""
    higgbot_mcp_path: str = ""            # path/command to higgbot's MCP stdio server
    higgbot_api_url: str = ""             # optional HTTP surface if exposed
    lucius_base_url: str = ""
    lucius_api_token: str = ""
    manychat_api_token: str = ""
    manychat_base_url: str = "https://api.manychat.com"
    n8n_base_url: str = ""
    n8n_api_token: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_access_token: str = ""

    # Run mode — SAFETY DEFAULT is 'simulation' (no real messages/publishing/spend).
    # Values: simulation | dry_run | live.
    social_automation_mode: str = "simulation"
    social_daily_touchpoint_target: int = 1050
    social_daily_budget_usd: float = 25.0
    # Initial per-brand touchpoint baselines (targets, NOT quotas; the allocation
    # engine learns and reallocates from these).
    ibc_touchpoint_baseline: int = 600   # Infinite Blueprint Collective (Instagram)
    nxg_touchpoint_baseline: int = 430   # NXG Life Group (Facebook)

    # Kill switches (durable overrides live in the system_flags table; these are the
    # boot defaults). Any True immediately blocks the matching outbound actions.
    system_pause: bool = False
    messaging_pause: bool = False
    publishing_pause: bool = False
    outbound_pause: bool = False
    nxg_pause: bool = False
    ibc_pause: bool = False
    higgbot_pause: bool = False
    athena_pause: bool = False

    # --- Chat memory retention ---
    # ORELIUS holds the conversation across app closes for this many days, then the
    # older messages auto-expire (a fresh holding period rolls forward).
    chat_retention_days: int = 7

    # --- Hot-topic reel pipeline (economic intel -> post package -> ATHENA/higgbot) ---
    # Two conversational steps: (1) ORELIUS compiles the 3 best/hottest VERIFIED facts
    # from the financial-intelligence briefing, compresses them into plain language for
    # the hottest life-insurance angle, and builds a post caption + viral hashtags + a
    # reel idea; (2) on the Master's word, ORELIUS hands that package to ATHENA, who
    # gives it to higgbot (the Master's own custom design agent — NOT Higgsfield) to
    # generate an award-winning reel and publish per the ibluezcluezflow content roadmap
    # ATHENA holds in her files.
    #
    # These brand notes only steer ORELIUS's caption/hashtag drafting; the reel format,
    # style, and account routing follow ATHENA's stored ibluezcluezflow content roadmap.
    ibluezcluezflow_guidelines: str = (
        "Brand: ibluezcluezflow — financial education that decodes money, banking, and "
        "life insurance for everyday people.\n"
        "Voice: simple, confident, bold, high-trust; plain language, zero jargon; never "
        "hype; compliance-conscious — education, NOT individualized financial advice; "
        "never promise returns or invent figures.\n"
        "Caption shape: strong hook -> the insight(s) -> why it matters to YOU -> soft "
        "CTA (follow / DM / learn more). Tie to life insurance / Infinite Banking / "
        "protect-and-grow. Viral, relevant hashtags."
    )
    # ATHENA's custom design agent that renders the reel (the Master's own — not Higgsfield).
    higgbot_name: str = "higgbot"
    # How many facts ORELIUS compiles into the post package.
    hot_topic_facts: int = 3
    # If true, dispatch one solo reel PER fact (3 solo reels); if false, one reel
    # carrying the whole package. Master's choice: 3 solo reels.
    hot_topic_solo_reels: bool = True

    # Telegram (optional — leave blank to run ORELIUS without the Telegram bot)
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""  # Comma-separated user IDs allowed to log in

    # --- Daily Financial Intelligence automation ---
    # Free FRED API key (https://fred.stlouisfed.org/docs/api/api_key.html).
    # FRED also carries Moody's corporate bond yields. Treasury Fiscal Data +
    # FDIC need no key.
    fred_api_key: str = ""
    # Free BEA API key (https://apps.bea.gov/API/signup/) for GDP/output data.
    bea_api_key: str = ""
    # Daily intel: never retrieve data older than this many days (the 2-month barrier).
    finance_lookback_days: int = 60

    # --- Live economic news via Anthropic web search (verified outlets only) ---
    # The finance brief pulls ACTUAL recent economic news (cited) and stacks it
    # against life insurance/annuities/retirement — not just data-series numbers.
    web_search_enabled: bool = True
    web_search_max_uses: int = 5
    # Reputable, verifiable sources the search is restricted to, keeping to the
    # Master's "verified sources only" mandate. NOTE: these must be crawlable by
    # Anthropic's search agent — paywalled sites that block the crawler (Reuters,
    # AP, WSJ, FT, MarketWatch, Barron's) cause a hard 400 if included, so they are
    # deliberately omitted. Official .gov feeds + CNBC/Bloomberg + ratings/insurance
    # bodies are the accessible reputable set; the engine also falls back to an
    # unrestricted (still reputable-instructed, cited) search if any domain is
    # rejected, so the brief never comes back empty.
    finance_news_domains: list[str] = [
        "cnbc.com", "bloomberg.com", "morningstar.com", "investopedia.com",
        "federalreserve.gov", "bls.gov", "treasury.gov", "bea.gov", "irs.gov",
        "sec.gov", "spglobal.com", "moodys.com", "limra.com", "iii.org", "naic.org",
    ]

    # --- NXG Life Group funnel intelligence (leads + site traffic) ---
    # ORELIUS reads the LifeFunnel site's Supabase project (the same DB the admin
    # dashboard reads) for leads, and a page_views table for visitor/device counts.
    # This is a SEPARATE daily automation from the finance engine.
    nxg_supabase_url: str = "https://bhuclkecnnbsovbdplwe.supabase.co"
    nxg_supabase_service_key: str = ""   # Supabase service_role key (set in Render env; secret)
    nxg_site_url: str = "https://nxglifegroup.com"
    # Optional Netlify Analytics fallback for traffic (paid add-on; best-effort).
    netlify_api_token: str = ""
    netlify_site_id: str = ""

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
