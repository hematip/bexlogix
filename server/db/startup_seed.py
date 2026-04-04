"""Auto-seed the database with sample data on first run."""

# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from pathlib import Path

from server.app.models.user import User
from server.app.services import import_service, import_users_service
from server.db.create_tables import create_tables
from server.db.database import get_db_session
from server.db.generate_sample_files import generate_sample_files

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_SEED_FILES = [
    ("users_seed_sample_10_visitors.xlsx", import_users_service.import_users_from_excel),
    ("stores_sample_300.xlsx", import_service.import_stores_from_excel),
]


# Contract: seed_if_empty executes one deterministic step in the workflow.
def seed_if_empty() -> None:
    """Create tables and seed sample data if the database is empty."""
    create_tables()

    db = get_db_session()
    try:
        user_count = db.query(User).count()
        if user_count > 0:
            return
    finally:
        db.close()

    missing_seed_files = [filename for filename, _ in _SEED_FILES if not (DATA_DIR / filename).exists()]
    if missing_seed_files:
        # FIX: [SEC-02] Regenerate required seed files automatically when they are not committed.
        generate_sample_files()

    for filename, import_func in _SEED_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            continue
        db = get_db_session()
        try:
            import_func(str(filepath), db)
        finally:
            db.close()
