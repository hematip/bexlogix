from __future__ import annotations

from server.app.services.import_service import import_stores_from_excel
from server.db.database import get_db_session


def test_import_stores_sample_file() -> None:
    db = get_db_session()
    try:
        processed_count = import_stores_from_excel("data/stores_sample_300.xlsx", db)
    finally:
        db.close()

    assert processed_count >= 300
