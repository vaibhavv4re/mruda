"""MRUDA — Central Configuration via Pydantic Settings."""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── Meta API ──
    meta_access_token: str = ""
    meta_ad_account_id: str = ""
    meta_api_version: str = "v21.0"
    meta_base_url: str = "https://graph.facebook.com"

    # ── Database ──
    database_url: str = ""

    # ── AI Providers ──
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    sarvam_api_key: Optional[str] = None
    default_ai_provider: str = "sarvam"  # sarvam | openai | claude

    # ── App ──
    log_level: str = "INFO"
    scheduler_enabled: bool = True
    analysis_hour: int = 2  # Daily run at 2 AM

    # ── Analysis ──
    analysis_schema_version: str = "1.0.0"
    account_currency: str = "INR"  # Fallback; overridden by Meta API

    @property
    def effective_database_url(self) -> str:
        """Return PostgreSQL URL if set, otherwise fall back to SQLite."""
        if self.database_url:
            return self.database_url
        # Vercel has a read-only filesystem; use /tmp for SQLite
        if os.environ.get("VERCEL"):
            return "sqlite:////tmp/mruda.db"
        return "sqlite:///./mruda.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
