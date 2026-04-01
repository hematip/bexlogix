from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.app.services.import_users_service import import_users_from_excel
from server.db.database import get_db_session


def main() -> None:
    db = get_db_session()
    try:
        import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
        file_path = "data/daily_visitor_status_sample_10.xlsx"
        processed_count = import_daily_visitor_statuses_from_excel(file_path, db)
        print(f"{processed_count} daily visitor status rows processed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
