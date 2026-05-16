# Purpose: Sample data generator for local/offline development.
# Workflow Role: Produces canonical login, stores, and visitors daily files.

from __future__ import annotations

from datetime import date
from pathlib import Path
from random import Random

import pandas as pd

from server.app.utils.tehran_geo import (
    REGION_TO_DISTRICTS,
    TEHRAN_DISTRICT_CENTROIDS,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

USERS_SAMPLE_PATH = DATA_DIR / "login.xlsx"
STORE_SAMPLE_PATH = DATA_DIR / "stores.xlsx"
DAILY_STATUS_SAMPLE_PATH = DATA_DIR / "visitors.xlsx"

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
    """Generate STORE_COUNT stores anchored on real Tehran district centroids.

    Each store is placed within ~1 km of a district centroid (gaussian jitter)
    so the dataset stays inside Tehran's populated area instead of falling on
    mountains or the bare bounding box edges. Stores rotate through the five
    business regions and five grades to keep the per-region/per-grade balance
    the integrity tests rely on.
    """
    rng = Random(20260401)
    regions = list(REGION_TO_DISTRICTS.keys())
    grades = ["VIP", "A+", "A", "B", "C"]

    # ~1 km gaussian jitter — std dev expressed in degrees.
    JITTER_LAT_DEG = 0.008
    JITTER_LON_DEG = 0.010

    rows: list[dict] = []
    for index in range(1, STORE_COUNT + 1):
        has_confectionery = bool(rng.randint(0, 1))
        has_oil = bool(rng.randint(0, 1))
        has_pasta = bool(rng.randint(0, 1))
        if not (has_confectionery or has_oil or has_pasta):
            has_confectionery = True

        region = regions[(index - 1) % len(regions)]
        candidate_districts = REGION_TO_DISTRICTS[region]
        district_id = candidate_districts[(index - 1) % len(candidate_districts)]
        centroid_lat, centroid_lon = TEHRAN_DISTRICT_CENTROIDS[district_id]

        lat = centroid_lat + rng.gauss(0.0, JITTER_LAT_DEG)
        lon = centroid_lon + rng.gauss(0.0, JITTER_LON_DEG)

        rows.append(
            {
                "store_code": f"STR-{index:03d}",
                "store_name": f"Zar Store {index:03d}",
                "region": region,
                "address": f"تهران، منطقه {district_id}، خیابان نمونه {index}",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "grade": grades[(index - 1) % len(grades)],
                "has_confectionery": has_confectionery,
                "has_oil": has_oil,
                "has_pasta": has_pasta,
            }
        )

    return pd.DataFrame(rows)


# Contract: _build_daily_status executes one deterministic step in the workflow.
def _build_daily_status(work_date_iso: str) -> pd.DataFrame:
    """Place each of the VISITOR_COUNT visitors at a different Tehran
    district so their start points are spread across the city.

    Spreading start points across the city is what lets the territory
    clustering produce naturally compact per-visitor tours; if every
    visitor starts from the same spot, the only way to cover the city
    is for someone to drive a long way.
    """
    # Pick visually well-spread districts as seed start points.
    SEED_DISTRICT_IDS = [1, 5, 8, 22, 6, 11, 17, 20, 15, 14]
    rows: list[dict] = []
    for index in range(1, VISITOR_COUNT + 1):
        district_id = SEED_DISTRICT_IDS[(index - 1) % len(SEED_DISTRICT_IDS)]
        start_lat, start_lon = TEHRAN_DISTRICT_CENTROIDS[district_id]
        rows.append(
            {
                "work_date": work_date_iso,
                "username": f"visitor{index}",
                "visitor_code": f"VIS-{index:03d}",
                "full_name": f"ویزیتور {index:02d}",
                "start_lat": round(start_lat, 6),
                "start_lon": round(start_lon, 6),
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
    _build_daily_status(today_iso).to_excel(DAILY_STATUS_SAMPLE_PATH, index=False)

    print(f"Users seed written: {USERS_SAMPLE_PATH} (13 rows)")
    print(f"Stores sample written: {STORE_SAMPLE_PATH} ({STORE_COUNT} rows)")
    print(f"Daily status sample written: {DAILY_STATUS_SAMPLE_PATH} ({VISITOR_COUNT} rows)")


if __name__ == "__main__":
    generate_sample_files()
