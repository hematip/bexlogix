from server.app.services.import_users_service import import_users_from_excel
from server.db.database import get_db_session


def main():
    db = get_db_session()
    try:
        file_path = "data/users_seed_sample_10_visitors.xlsx"
        processed_count = import_users_from_excel(file_path, db)
        print(f"{processed_count} user rows processed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
