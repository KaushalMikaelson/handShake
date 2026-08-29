"""Application configuration.

Every external dependency (Razorpay, Anthropic) degrades to a deterministic
local simulator when its credentials are absent, so the full end-to-end flow
runs with zero third-party accounts. See docs/architecture.md.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Bounded AI-to-AI Commerce"
    environment: str = "development"

    # postgres in docker-compose; sqlite fallback so the API and the test
    # suite run with no external services at all.
    database_url: str = "sqlite:///./agent_commerce.db"

    # --- Razorpay (test mode only) ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = "demo_webhook_secret"

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # --- demo identities (auth is out of scope per PRD 3.12) ---
    demo_buyer_id: str = "buyer_aditi"
    demo_merchant_id: str = "merchant_audiohub"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def razorpay_live_mode(self) -> bool:
        """True only when real test-mode API keys are configured."""
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def llm_live_mode(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
