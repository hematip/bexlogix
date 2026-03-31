from datetime import date

from server.app.models.daily_assignment import DailyAssignment
from server.app.models.user import User
from server.app.services import assignment_service, import_service, import_users_service
from server.app.services import import_visitors_service, routing_service
from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.db.create_tables import create_tables
from server.db.database import get_db_session


def main():
    create_tables()

    db = get_db_session()
    try:
        import_service.import_stores_from_excel("data/stores_sample.xlsx", db)
        import_users_service.import_users_from_excel("data/users_seed_sample.xlsx", db)
        import_visitors_service.import_visitor_profiles_from_excel("data/visitors_sample.xlsx", db)
        import_daily_visitor_statuses_from_excel("data/daily_visitor_status_sample.xlsx", db)

        manager = db.query(User).filter(User.username == "manager1").first()
        if not manager:
            raise ValueError("manager1 was not found after users import.")

        work_date = date(2026, 3, 31)
        existing_non_draft_count = (
            db.query(DailyAssignment)
            .filter(
                DailyAssignment.work_date == work_date,
                DailyAssignment.assignment_status != "draft",
            )
            .count()
        )
        if existing_non_draft_count > 0:
            print(
                f"Non-draft assignments already exist for {work_date.isoformat()} "
                f"({existing_non_draft_count} rows). Skipping draft regeneration."
            )
            return

        summary = assignment_service.generate_draft_assignments(
            db=db,
            work_date=work_date,
            manager_user_id=manager.id,
            replace_existing_draft=True,
        )
        if summary.get("created_assignments", 0) == 0:
            print(
                f"No draft assignments generated for {work_date.isoformat()} "
                "(likely no due stores or zero active capacity)."
            )
            print(f"Draft summary: {summary}")
            return

        planned_count = routing_service.apply_routes_for_work_date(
            db=db,
            work_date=work_date,
            planner=routing_service.NearestNeighborRoutePlanner(),
        )
        published_count = assignment_service.publish_assignments(
            db=db,
            work_date=work_date,
            manager_user_id=manager.id,
        )

        print(f"Draft summary: {summary}")
        print(f"Route planned assignments: {planned_count}")
        print(f"Published assignments: {published_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
