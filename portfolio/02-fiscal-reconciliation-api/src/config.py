"""
src/config.py

Centralized configuration, loaded from environment variables (or a .env
file) and validated once at startup instead of being read ad-hoc with
`os.environ.get(...)` scattered across the codebase.

Using `pydantic-settings` here means: if a required setting is missing or
malformed, the app fails immediately at startup with a clear error --
instead of failing three requests later, deep inside a function that
assumed the config was already correct.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # How many days back from today a reconciliation request is allowed to
    # reach. This mirrors the real business rule: today's data is not
    # considered "closed" yet, so requests for it are rejected at the API
    # layer (see api.py's `_validate_reference_date`).
    lookback_window_days: int = 30

    # Database connection strings/DSNs. Left as plain strings here for
    # portfolio clarity -- in the MCP server project (01), the equivalent
    # values are pulled from an encrypted credential store instead of
    # environment variables, which is the stricter approach for a
    # production deployment.
    legacy_system_dsn: str = ""
    erp_system_host: str = ""
    erp_system_port: int = 30015


# A single shared instance, imported wherever settings are needed.
settings = Settings()
