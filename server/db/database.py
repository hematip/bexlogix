# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

# DATABASE_URL is the canonical location of the operational database.
# Override via env var for test environments and alternative deployments.
DATABASE_URL = os.environ.get("BEXLOGIX_DATABASE_URL", "sqlite:///./bexlogix.db")

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# The main connection to db
engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,  # FIX: [ARCH-01] Keep SQLite connections healthy before use.
)


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, _connection_record):
        # FIX: [ARCH-01] Enable WAL + busy timeout to reduce "database is locked" under concurrent sessions.
        # FIX: enforce foreign keys (SQLite has them off by default).
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA busy_timeout=30000")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

# Take session from db
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Create a new database session
# Contract: get_db_session executes one deterministic step in the workflow.
def get_db_session():
    return SessionLocal()


@contextmanager
def get_db():
    # FIX: [ARCH-02] Context-managed DB session usage to guarantee close on all paths.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
