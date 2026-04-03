from __future__ import annotations

from server.app.services.import_users_service import import_users_from_excel
from server.db.database import get_db_session


def test_import_users_seed_file() -> None:
    db = get_db_session()
    try:
        processed_count = import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
    finally:
        db.close()

    assert processed_count >= 1
