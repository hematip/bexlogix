# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

# Where is my db
DATABASE_URL = "sqlite:///./bexlogix.db"

# The main connection to db
engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False},
    pool_pre_ping=True,  # FIX: [ARCH-01] Keep SQLite connections healthy before use.
)


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, _connection_record):
    # FIX: [ARCH-01] Enable WAL + busy timeout to reduce "database is locked" under concurrent sessions.
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=30000")

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
