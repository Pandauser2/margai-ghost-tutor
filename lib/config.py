"""
Environment config for MargAI Ghost Tutor pilot.
Load from env; used by ingestion scripts and (via env) Vercel API.
Loads pilot/.env when present (so scripts work from repo root).
"""
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Pilot root (margai-ghost-tutor-pilot/); .env lives here
_PILOT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PILOT_ROOT / ".env"


class Settings(BaseSettings):
    """Settings from env (e.g. .env or Vercel env vars)."""

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "margai-ghost-tutor"

    # Gemini
    gemini_api_key: str = ""

    # Telegram (for webhook)
    telegram_bot_token: str = ""
    telegram_webhook_secret: Optional[str] = None

    # Pilot: default institute when single-bot (chat_id -> institute_id mapping)
    institute_id_default: int = 1

    # Alert email for ingestion failures (optional)
    alert_email: Optional[str] = None

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        "extra": "ignore",
    }


def get_settings() -> Settings:
    return Settings()
