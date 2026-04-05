# Purpose: Startup seed bootstrap for database initialization.
# Workflow Role: Guarantees baseline users/stores exist for first application launch.
"""Auto-seed the database with local sample data on first run."""

from pathlib import Path

from server.app.models.user import User
from server.app.services import import_service, import_users_service
from server.db.create_tables import create_tables
from server.db.database import get_db_session
from server.db.generate_sample_files import generate_sample_files

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_LEGACY_TO_NEW_FILENAMES = {
    "users_seed_sample_10_visitors.xlsx": "login.xlsx",
    "stores_sample_300.xlsx": "stores.xlsx",
    "daily_visitor_status_sample_10.xlsx": "visitors.xlsx",
}

_SEED_FILES = [
    ("login.xlsx", import_users_service.import_users_from_excel),
    ("stores.xlsx", import_service.import_stores_from_excel),
]


# Contract: _migrate_legacy_filenames executes one deterministic step in the workflow.
def _migrate_legacy_filenames() -> None:
    # FIX: [DATA-RENAME] One-step compatibility migration from legacy sample names.
    for old_name, new_name in _LEGACY_TO_NEW_FILENAMES.items():
        old_path = DATA_DIR / old_name
        new_path = DATA_DIR / new_name
        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)


# Contract: seed_if_empty executes one deterministic step in the workflow.
def seed_if_empty() -> None:
    """Create tables and seed sample data if the database is empty."""
    create_tables()
    _migrate_legacy_filenames()

    db = get_db_session()
    try:
        user_count = db.query(User).count()
        if user_count > 0:
            return
    finally:
        db.close()

    missing_seed_files = [filename for filename, _ in _SEED_FILES if not (DATA_DIR / filename).exists()]
    if missing_seed_files:
        generate_sample_files()
        _migrate_legacy_filenames()

    for filename, import_func in _SEED_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            continue
        db = get_db_session()
        try:
            import_func(str(filepath), db)
        finally:
            db.close()
