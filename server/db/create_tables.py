# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from server.db.base import Base
from server.db.database import engine
from server.app.models.model_registry import register_models

logger = logging.getLogger(__name__)


def _ensure_sqlite_column(table_name: str, column_name: str, ddl_fragment: str) -> None:
    # FIX: [SEC-01] Lightweight SQLite-safe schema evolution for new columns.
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        existing_columns = {str(row[1]) for row in rows}
        if column_name in existing_columns:
            return
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_fragment}"))
        conn.commit()


def _ensure_unique_index(index_name: str, table_name: str, columns: list[str]) -> None:
    """Create a unique index idempotently. Equivalent to a UNIQUE constraint
    in SQLite and Postgres, and safe to run on a fresh or upgraded DB.

    If existing duplicate rows would violate the constraint, raises a clear
    runtime error pointing at the integrity report. Startup will fail fast
    rather than silently leaving duplicates in place.
    """
    column_list = ", ".join(columns)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                    f"ON {table_name} ({column_list})"
                )
            )
            conn.commit()
    except (IntegrityError, OperationalError) as exc:
        logger.error(
            "Failed to create unique index %s on %s(%s): duplicate rows exist. "
            "Run integrity_service.run_integrity_report and resolve duplicates "
            "before next startup. Underlying error: %s",
            index_name,
            table_name,
            column_list,
            exc,
        )
        raise


def _ensure_index(index_name: str, table_name: str, columns: list[str]) -> None:
    """Create a non-unique covering index idempotently."""
    column_list = ", ".join(columns)
    with engine.connect() as conn:
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON {table_name} ({column_list})"
            )
        )
        conn.commit()


def _ensure_schema_extensions() -> None:
    _ensure_sqlite_column(
        table_name="users",
        column_name="must_change_password",
        ddl_fragment="BOOLEAN NOT NULL DEFAULT 0",
    )
    # Production-readiness invariants — these enforce business rules at the
    # database layer so concurrent writes can't corrupt state.
    _ensure_unique_index(
        index_name="uq_visit_assignment_id",
        table_name="visits",
        columns=["assignment_id"],
    )
    _ensure_unique_index(
        index_name="uq_daily_assignment_date_store",
        table_name="daily_assignments",
        columns=["work_date", "store_id"],
    )
    # Performance: queries that filter by (visitor, date) are hot paths.
    _ensure_index(
        index_name="ix_daily_assignment_visitor_date",
        table_name="daily_assignments",
        columns=["visitor_id", "work_date"],
    )
    _ensure_index(
        index_name="ix_visit_store_date",
        table_name="visits",
        columns=["store_id", "visit_date"],
    )


# Create all tables defined in ORM models.
# MVP note: migration tool is intentionally not introduced yet.
# Contract: create_tables executes one deterministic step in the workflow.
def create_tables():
    register_models()
    Base.metadata.create_all(bind=engine)
    _ensure_schema_extensions()

if __name__ == '__main__':
    create_tables()
    print('Tables created successfully')
