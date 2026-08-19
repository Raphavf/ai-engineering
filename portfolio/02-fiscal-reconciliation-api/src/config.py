"""
src/config.py

App configuration, loaded from environment variables (or a .env file)
via pydantic-settings and validated once at startup.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # How far back a reconciliation request is allowed to reach
    lookback_window_days: int = 30

    # Database connection settings
    legacy_system_dsn: str = ""
    erp_system_host: str = ""
    erp_system_port: int = 30015


settings = Settings()
