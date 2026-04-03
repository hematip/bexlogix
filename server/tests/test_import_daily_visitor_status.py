from __future__ import annotations

from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.app.services.import_users_service import import_users_from_excel
from server.db.database import get_db_session


def _run_import() -> int:
    db = get_db_session()
    try:
        import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
        return import_daily_visitor_statuses_from_excel(
            "data/daily_visitor_status_sample_10.xlsx",
            db,
        )
    finally:
        db.close()


def test_import_daily_visitor_status_rows() -> None:
    processed_count = _run_import()
    assert processed_count >= 10
