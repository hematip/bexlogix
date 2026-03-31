from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.db.database import get_db_session


def main():
    db = get_db_session()
    try:
        file_path = "data/daily_visitor_status_sample.xlsx"
        processed_count = import_daily_visitor_statuses_from_excel(file_path, db)
        print(f"{processed_count} daily visitor status rows processed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
