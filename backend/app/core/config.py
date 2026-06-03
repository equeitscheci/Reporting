"""Application settings (12-factor: environment-driven)."""

from __future__ import annotations

import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INSIGHTFORGE_", env_file=".env", extra="ignore")

    app_name: str = "Insightforge"
    environment: str = "dev"

    # Warehouse connection (Postgres in dev; Snowflake/BigQuery DSN at scale).
    warehouse_dsn: str = "postgresql://insightforge:insightforge@localhost:5432/insightforge"

    # Secrets backend: env|file|aws_secrets_manager|vault
    secrets_backend: str = "env"
    secrets_file: str = str(CONFIG_DIR / "secrets.dev.json")

    # Where per-tenant config lives (Git-backed for review/audit).
    tenants_dir: str = str(CONFIG_DIR / "tenants")

    # Auth
    jwt_audience: str = "insightforge"
    auth_disabled: bool = True  # dev convenience; MUST be False in prod

    # Optional ECI AI Studio agent bridge. When ai_studio_agent_url is unset, the app uses the
    # built-in deterministic NLQ engine only.
    ai_studio_agent_url: str | None = None
    ai_studio_api_key: str | None = None
    ai_studio_agent_id: str | None = None
    ai_studio_timeout_seconds: float = 15.0

    # Token broker for the ECI AI Studio browser widget. Never expose client credentials directly
    # to the frontend; the widget calls /.ai/token and this backend performs the exchange.
    ai_widget_access_token: str | None = None  # dev-only escape hatch
    ai_widget_token_url: str | None = None
    ai_widget_client_id: str | None = None
    ai_widget_client_secret: str | None = None
    ai_widget_scope: str | None = None
    ai_widget_audience: str | None = None
    ai_widget_timeout_seconds: float = 10.0


settings = Settings()
