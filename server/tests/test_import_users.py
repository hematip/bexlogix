# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from server.app.services.import_users_service import import_users_from_excel
from server.db.database import get_db_session


# Contract: test_import_users_seed_file executes one deterministic step in the workflow.
def test_import_users_seed_file() -> None:
    db = get_db_session()
    try:
        processed_count = import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
    finally:
        db.close()

    assert processed_count >= 1
