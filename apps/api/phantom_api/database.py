"""SQLAlchemy engine, session management, and schema initialization.

SQLite is used for the local MVP. Schema creation is safe/idempotent and a
lightweight ``schema_migrations`` table records the applied schema version so
future migrations can be sequenced without destructive resets.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings

SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _enable_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_engine(settings: Settings) -> Engine:
    global _engine, _SessionFactory
    settings.ensure_directories()
    url = f"sqlite:///{settings.db_file.as_posix()}"
    _engine = create_engine(
        url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    event.listen(_engine, "connect", _enable_sqlite_pragmas)
    _SessionFactory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _engine


def get_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Session factory not initialized. Call init_engine() first.")
    return _SessionFactory()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema() -> None:
    """Create all tables and record the schema version (idempotent)."""
    from . import db_models  # noqa: F401  (register models on Base.metadata)

    engine = get_engine()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
        )
        existing = conn.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        if SCHEMA_VERSION not in existing:
            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version, applied_at) "
                    "VALUES (:v, datetime('now'))"
                ),
                {"v": SCHEMA_VERSION},
            )


def reset_runtime_state() -> None:
    """Drop engine/session state. Used by tests between cases."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
