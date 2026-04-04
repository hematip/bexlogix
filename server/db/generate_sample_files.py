# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from datetime import date
from pathlib import Path
from random import Random

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

USERS_SAMPLE_PATH = DATA_DIR / "users_seed_sample_10_visitors.xlsx"
STORE_SAMPLE_PATH = DATA_DIR / "stores_sample_300.xlsx"
VISITOR_SAMPLE_PATH = DATA_DIR / "visitors_sample_10.xlsx"
DAILY_STATUS_SAMPLE_PATH = DATA_DIR / "daily_visitor_status_sample_10.xlsx"
DAILY_STATUS_TEMPLATE_PATH = DATA_DIR / "upload_template_daily_status.xlsx"

STORE_COUNT = 300
VISITOR_COUNT = 10


# Contract: _build_users executes one deterministic step in the workflow.
def _build_users() -> pd.DataFrame:
    rows = [
        {"username": "manager1", "password": "change_me", "role": "manager", "is_active": True},
        {"username": "supervisor1", "password": "change_me", "role": "supervisor", "is_active": True},
        {"username": "telesales1", "password": "change_me", "role": "telesales", "is_active": True},
    ]
    for index in range(1, VISITOR_COUNT + 1):
        rows.append(
            {
                "username": f"visitor{index}",
                "password": "change_me",
                "role": "visitor",
                "is_active": True,
            }
        )
    return pd.DataFrame(rows)


# Contract: _build_stores executes one deterministic step in the workflow.
def _build_stores() -> pd.DataFrame:
    rng = Random(20260401)
    regions = ["مرکز", "شمال", "جنوب", "شرق", "غرب"]
    grades = ["VIP", "A+", "A", "B", "C"]

    rows: list[dict] = []
    for index in range(1, STORE_COUNT + 1):
        has_confectionery = bool(rng.randint(0, 1))
        has_oil = bool(rng.randint(0, 1))
        has_pasta = bool(rng.randint(0, 1))
        if not (has_confectionery or has_oil or has_pasta):
            has_confectionery = True

        rows.append(
            {
                "store_code": f"STR-{index:03d}",
                "store_name": f"Zar Store {index:03d}",
                "region": regions[(index - 1) % len(regions)],
                "address": f"تهران، منطقه {(index % 22) + 1}، خیابان نمونه {index}",
                "lat": round(35.58 + rng.random() * 0.28, 6),
                "lon": round(51.20 + rng.random() * 0.42, 6),
                "grade": grades[(index - 1) % len(grades)],
                "has_confectionery": has_confectionery,
                "has_oil": has_oil,
                "has_pasta": has_pasta,
            }
        )

    return pd.DataFrame(rows)


# Contract: _build_visitors executes one deterministic step in the workflow.
def _build_visitors() -> pd.DataFrame:
    rows: list[dict] = []
    for index in range(1, VISITOR_COUNT + 1):
        rows.append(
            {
                "username": f"visitor{index}",
                "role": "visitor",
                "visitor_code": f"VIS-{index:03d}",
                "full_name": f"ویزیتور {index:02d}",
                "default_start_lat": round(35.66 + (index * 0.01), 6),
                "default_start_lon": round(51.32 + (index * 0.01), 6),
                "default_capacity": 30,
                "is_active": True,
            }
        )
    return pd.DataFrame(rows)


# Contract: _build_daily_status executes one deterministic step in the workflow.
def _build_daily_status(work_date_iso: str) -> pd.DataFrame:
    rows: list[dict] = []
    for index in range(1, VISITOR_COUNT + 1):
        rows.append(
            {
                "work_date": work_date_iso,
                "username": f"visitor{index}",
                "visitor_code": f"VIS-{index:03d}",
                "full_name": f"ویزیتور {index:02d}",
                "start_lat": round(35.66 + (index * 0.01), 6),
                "start_lon": round(51.32 + (index * 0.01), 6),
                "capacity": 30,
                "is_active_today": True,
            }
        )
    return pd.DataFrame(rows)


# Contract: generate_sample_files executes one deterministic step in the workflow.
def generate_sample_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today_iso = date.today().isoformat()
    _build_users().to_excel(USERS_SAMPLE_PATH, index=False)
    _build_stores().to_excel(STORE_SAMPLE_PATH, index=False)
    _build_visitors().to_excel(VISITOR_SAMPLE_PATH, index=False)
    _build_daily_status(today_iso).to_excel(DAILY_STATUS_SAMPLE_PATH, index=False)
    _build_daily_status(today_iso).to_excel(DAILY_STATUS_TEMPLATE_PATH, index=False)

    print(f"Users seed written: {USERS_SAMPLE_PATH} (13 rows)")
    print(f"Stores sample written: {STORE_SAMPLE_PATH} ({STORE_COUNT} rows)")
    print(f"Visitors sample written: {VISITOR_SAMPLE_PATH} ({VISITOR_COUNT} rows)")
    print(f"Daily status sample written: {DAILY_STATUS_SAMPLE_PATH} ({VISITOR_COUNT} rows)")
    print(f"Daily upload template written: {DAILY_STATUS_TEMPLATE_PATH} ({VISITOR_COUNT} rows)")


if __name__ == "__main__":
    generate_sample_files()
