"""Database engine, session management, and SQLite PRAGMAs matching Blueprint Section 14.1."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from warehouse_ai.config import REPO_ROOT, get_settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:
    """Enforce strict SQLite pragmas on every connection per Section 14.1."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()


def get_engine(db_url: str | None = None) -> Engine:
    """Create SQLAlchemy engine with connection pool suitable for SQLite."""
    settings = get_settings()
    url = db_url or settings.DATABASE_URL

    # Ensure parent directory of SQLite file exists if using sqlite:///
    if url.startswith("sqlite:///"):
        db_path_str = url[len("sqlite:///"):]
        if not Path(db_path_str).is_absolute():
            db_path = (REPO_ROOT / db_path_str).resolve()
        else:
            db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"

    return create_engine(
        url,
        connect_args={"check_same_thread": False},
        future=True,
    )


# Default engine & session factory
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def init_db(db_url: str | None = None) -> Engine:
    global _engine, _SessionFactory
    _engine = get_engine(db_url)
    _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        init_db()
    assert _SessionFactory is not None
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """Yield a database session within a transaction context."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
