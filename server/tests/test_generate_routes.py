from __future__ import annotations

from datetime import date, timedelta

import pytest

from server.app.models.user import User
from server.app.services import assignment_service, import_service, import_users_service, routing_service
from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.db.create_tables import create_tables
from server.db.database import get_db_session


@pytest.mark.integration
def test_generate_routes_pipeline() -> None:
    create_tables()

    db = get_db_session()
    try:
        import_service.import_stores_from_excel("data/stores_sample_300.xlsx", db)
        import_users_service.import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
        import_daily_visitor_statuses_from_excel("data/daily_visitor_status_sample_10.xlsx", db)

        manager = db.query(User).filter(User.username == "manager1").first()
        assert manager is not None

        work_date = date.today()
        for offset in range(0, 21):
            candidate = date.today() + timedelta(days=offset)
            snapshot = assignment_service.get_work_date_operational_snapshot(db, candidate)
            if not snapshot["is_locked"]:
                work_date = candidate
                break

        summary = assignment_service.generate_draft_assignments(
            db=db,
            work_date=work_date,
            manager_user_id=manager.id,
            replace_existing_draft=True,
        )
        routed_count = routing_service.apply_routes_for_work_date(
            db=db,
            work_date=work_date,
            planner=routing_service.OSRMRoutePlanner(
                fallback_planner=routing_service.NearestNeighborRoutePlanner(),
            ),
        )
        quality = assignment_service.evaluate_route_quality_vs_round_robin(
            db=db,
            work_date=work_date,
        )

        # Keep legacy behavior: publish only when drafts exist.
        if summary.get("created_assignments", 0) > 0:
            published_count = assignment_service.publish_assignments(
                db=db,
                work_date=work_date,
                manager_user_id=manager.id,
            )
            assert published_count >= 0

        assert routed_count >= 0
        assert "improvement_pct" in quality
    finally:
        db.close()
