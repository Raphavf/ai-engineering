"""
config.py

Settings from environment variables (prefix FISCAL_RECON_) or a .env
file, validated once at startup.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FISCAL_RECON_", env_file=".env", extra="ignore")

    # "sqlite": synthetic data, no external DB. "oracle_hana": real connectors.
    backend: Literal["sqlite", "oracle_hana"] = "sqlite"
    sqlite_path: str = "data/synthetic.db"

    encrypted_credentials_path: str = "credentials.enc"

    cache_ttl_seconds: float = 300
    lookback_window_days: int = 30
