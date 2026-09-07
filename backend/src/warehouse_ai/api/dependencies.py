"""FastAPI dependencies for database sessions and configuration."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from warehouse_ai.config import Settings, get_settings
from warehouse_ai.repositories.database import get_db


def get_db_session() -> Generator[Session, None, None]:
    """Yield database session from connection pool."""
    yield from get_db()


def get_app_settings() -> Settings:
    """Return application settings instance."""
    return get_settings()


def get_storage_path(settings: Settings = Depends(get_app_settings)) -> Path:
    """Return configured absolute storage root path."""
    return settings.storage_root_path
