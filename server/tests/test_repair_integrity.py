from __future__ import annotations

from datetime import date

import pytest

from server.app.services import integrity_service, reconciliation_service
from server.db.database import get_db_session


@pytest.mark.integration
def test_repair_known_integrity_blockers_contract() -> None:
    db = get_db_session()
    try:
        repair_summary = reconciliation_service.repair_known_integrity_blockers(db=db)
        report = integrity_service.run_integrity_report(
            db=db,
            work_date=date.today(),
            strict=False,
        )
    finally:
        db.close()

    assert isinstance(repair_summary, dict)
    assert "blockers" in report
