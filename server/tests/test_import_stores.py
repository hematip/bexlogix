from server.app.services.import_service import import_stores_from_excel
from server.db.database import get_db_session


def main():
    db = get_db_session()

    try:
        file_path = "data/stores_sample.xlsx"
        processed_count = import_stores_from_excel(file_path, db)
        print(f"{processed_count} store rows processed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()