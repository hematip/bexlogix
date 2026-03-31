from server.app.services.import_telesales_followups_service import (
    import_telesales_followups_from_excel,
)
from server.db.database import get_db_session


def main():
    db = get_db_session()
    try:
        file_path = "data/telesales_followups_sample.xlsx"
        processed_count = import_telesales_followups_from_excel(
            file_path=file_path,
            db=db,
            allow_backfill_mode=True,
        )
        print(f"{processed_count} telesales followup rows processed in backfill mode.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
