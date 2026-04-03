from __future__ import annotations

from datetime import date

import pytest

from server.app.services import integrity_service
from server.db.database import get_db_session


@pytest.mark.integration
def test_integrity_snapshot_contract() -> None:
    db = get_db_session()
    try:
        report = integrity_service.run_integrity_report(
            db=db,
            work_date=date.today(),
            strict=False,
        )
    finally:
        db.close()

    assert "work_date" in report
    assert "blockers" in report
    assert "warnings" in report
    assert "summary" in report
    assert report["summary"]["blocker_checks"] == len(report["blockers"])
    assert report["summary"]["warning_checks"] == len(report["warnings"])
