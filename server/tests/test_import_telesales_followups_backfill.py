# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from pathlib import Path

import pytest

from server.app.services.import_telesales_followups_service import (
    import_telesales_followups_from_excel,
)
from server.db.database import get_db_session


# Contract: test_import_telesales_followups_backfill_mode executes one deterministic step in the workflow.
@pytest.mark.smoke
def test_import_telesales_followups_backfill_mode() -> None:
    sample_path = Path("data/telesales_followups_sample.xlsx")
    if not sample_path.exists():
        pytest.skip("telesales followups sample file is not present in current workspace.")

    db = get_db_session()
    try:
        processed_count = import_telesales_followups_from_excel(
            file_path=str(sample_path),
            db=db,
            allow_backfill_mode=True,
        )
    finally:
        db.close()

    assert processed_count >= 0
