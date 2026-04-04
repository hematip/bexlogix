# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from server.app.services.import_service import import_stores_from_excel
from server.db.database import get_db_session


# Contract: test_import_stores_sample_file executes one deterministic step in the workflow.
def test_import_stores_sample_file() -> None:
    db = get_db_session()
    try:
        processed_count = import_stores_from_excel("data/stores_sample_300.xlsx", db)
    finally:
        db.close()

    assert processed_count >= 300
