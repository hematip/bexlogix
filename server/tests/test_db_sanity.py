from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path("bexlogix.db")

_CHECKS = [
    (
        "daily_visitor_status_dups",
        "SELECT visitor_id, work_date, COUNT(*) c "
        "FROM daily_visitor_statuses GROUP BY visitor_id, work_date HAVING c > 1",
    ),
    (
        "daily_assignment_dups",
        "SELECT work_date, store_id, COUNT(*) c "
        "FROM daily_assignments GROUP BY work_date, store_id HAVING c > 1",
    ),
    (
        "visit_dups",
        "SELECT assignment_id, COUNT(*) c "
        "FROM visits GROUP BY assignment_id HAVING c > 1",
    ),
    (
        "schedule_state_dups",
        "SELECT store_id, COUNT(*) c "
        "FROM store_schedule_states GROUP BY store_id HAVING c > 1",
    ),
    (
        "followup_visit_store_mismatch",
        "SELECT tf.id, tf.store_id, tf.visit_id, v.store_id "
        "FROM telesales_followups tf "
        "JOIN visits v ON v.id = tf.visit_id "
        "WHERE tf.store_id <> v.store_id",
    ),
    (
        "postpone_without_open_next_followup",
        "SELECT p.id, p.visit_id, p.followup_date "
        "FROM telesales_followups p "
        "WHERE p.result = 'postpone' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM telesales_followups n "
        "  WHERE n.visit_id = p.visit_id "
        "    AND n.result IS NULL "
        "    AND n.followup_date > p.followup_date"
        ")",
    ),
]


@pytest.mark.integration
def test_db_sanity_checks() -> None:
    if not DB_PATH.exists():
        pytest.skip("bexlogix.db does not exist in workspace.")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        failures: list[str] = []
        for name, query in _CHECKS:
            rows = cur.execute(query).fetchall()
            if rows:
                failures.append(f"{name}: {rows[:5]}")
        assert not failures, "Database sanity checks failed:\n" + "\n".join(failures)
    finally:
        conn.close()
