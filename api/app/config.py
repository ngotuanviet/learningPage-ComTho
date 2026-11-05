from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """All config comes from environment variables (or api/.env locally)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["development", "test", "preview", "production"] = "development"
    database_url: str = "sqlite:///./dev.db"

    # Used to hash IPs for rate limiting. >= 32 random characters.
    app_secret: str = Field(min_length=32)

    # Public website origins allowed to call the API (CORS). Comma separated.
    public_allowed_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    # Bank account that receives transfers (shown on the QR / checkout page).
    bank_code: str = "MBBank"  # SePay bank short name
    bank_account: str = "0000000000"
    bank_account_name: str = "TEN CHU TAI KHOAN"

    # Order code = prefix + random chars. Configure the same prefix in SePay.
    order_code_prefix: str = "CT"
    order_ttl_minutes: int = 30

    # SePay webhook: SePay sends header "Authorization: Apikey <key>".
    sepay_webhook_api_key: str | None = None

    # Email (Resend). Without an API key, emails are skipped (logged) - fine for local dev.
    resend_api_key: str | None = None
    email_from: str = "Cơm Đốt Thố Hội An <no-reply@example.com>"
    email_reply_to: str | None = None

    # Abuse limits for creating orders
    max_pending_orders_per_email: int = 3
    max_orders_per_ip_per_hour: int = 10

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        # Neon/Heroku style URLs -> SQLAlchemy psycopg3 driver
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @field_validator("order_code_prefix")
    @classmethod
    def _prefix_alnum(cls, value: str) -> str:
        # Banks strip special characters from transfer notes, so keep it A-Z / 0-9 only.
        if not value.isalnum() or not value.isupper():
            raise ValueError("ORDER_CODE_PREFIX must be uppercase letters/digits")
        return value

    @property
    def public_origins(self) -> list[str]:
        return _split_csv(self.public_allowed_origins)

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
