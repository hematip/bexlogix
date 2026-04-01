from server.app.services.import_visitors_service import import_visitor_profiles_from_excel
from server.db.database import get_db_session


def main():
    db = get_db_session()
    try:
        file_path = "data/visitors_sample_10.xlsx"
        processed_count = import_visitor_profiles_from_excel(file_path, db)
        print(f"{processed_count} visitor profile rows processed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
