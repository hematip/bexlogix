from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")


def main() -> None:
    stores_path = DATA_DIR / "stores_sample_300.xlsx"
    visitors_path = DATA_DIR / "visitors_sample_10.xlsx"
    daily_status_path = DATA_DIR / "daily_visitor_status_sample_10.xlsx"
    users_path = DATA_DIR / "users_seed_sample_10_visitors.xlsx"

    stores_df = pd.read_excel(stores_path)
    visitors_df = pd.read_excel(visitors_path)
    daily_status_df = pd.read_excel(daily_status_path)
    users_df = pd.read_excel(users_path)

    assert len(stores_df) == 300, "stores_sample_300.xlsx must contain 300 rows."
    assert len(visitors_df) == 10, "visitors_sample_10.xlsx must contain 10 rows."
    assert len(daily_status_df) == 10, "daily_visitor_status_sample_10.xlsx must contain 10 rows."

    required_user_columns = {"username", "password", "role", "is_active"}
    missing_user_columns = required_user_columns - set(users_df.columns)
    assert not missing_user_columns, "users_seed_sample_10_visitors.xlsx structure changed unexpectedly."

    required_daily_columns = {
        "work_date",
        "username",
        "visitor_code",
        "full_name",
        "start_lat",
        "start_lon",
        "capacity",
        "is_active_today",
    }
    missing_daily_columns = required_daily_columns - set(daily_status_df.columns)
    assert not missing_daily_columns, (
        "daily_visitor_status_sample_10.xlsx must contain the new daily contract columns. "
        f"Missing: {sorted(missing_daily_columns)}"
    )

    print("Sample files dimension and schema test passed.")


if __name__ == "__main__":
    main()
