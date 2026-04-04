# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from sqlalchemy import text

from server.db.base import Base
from server.db.database import engine
from server.app.models.model_registry import register_models


def _ensure_sqlite_column(table_name: str, column_name: str, ddl_fragment: str) -> None:
    # FIX: [SEC-01] Lightweight SQLite-safe schema evolution for new columns.
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
        existing_columns = {str(row[1]) for row in rows}
        if column_name in existing_columns:
            return
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_fragment}"))
        conn.commit()


def _ensure_schema_extensions() -> None:
    _ensure_sqlite_column(
        table_name="users",
        column_name="must_change_password",
        ddl_fragment="BOOLEAN NOT NULL DEFAULT 0",
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
