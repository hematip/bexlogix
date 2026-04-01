"""Auto-seed the database with sample data on first run."""

from pathlib import Path

from server.app.models.user import User
from server.app.services import import_service, import_users_service
from server.db.create_tables import create_tables
from server.db.database import get_db_session

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_SEED_FILES = [
    ("users_seed_sample_10_visitors.xlsx", import_users_service.import_users_from_excel),
    ("stores_sample_300.xlsx", import_service.import_stores_from_excel),
]


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

    for filename, import_func in _SEED_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            continue
        db = get_db_session()
        try:
            import_func(str(filepath), db)
        finally:
            db.close()
