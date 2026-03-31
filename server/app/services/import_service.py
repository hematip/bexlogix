from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.models.store import Store

REQUIRED_STORE_COLUMNS = {
    'store_code',
    'store_name',
    'region',
    'address',
    'lat',
    'lon',
    'grade',
    'has_confectionery',
    'has_oil',
    'has_pasta',
}

# Read store master data from an Excel file
def read_store_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)

# Normalize column names to make import more robust
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df

# Validate that all required columns exist in the upload file
def validate_store_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_STORE_COLUMNS) - set(df.columns)
    if missing_columns:
        missing_str = ', '.join(sorted(missing_columns))
        raise ValueError(f'Missing required columns: {missing_str}')

# Convert Excel-like boolean values to Python bool
def normalize_bool_value(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    return value in ['true', '1', 't', 'y', 'yes']


# Clean and normalize store data before saving to the database
def transform_store_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalize grade values
    df['grade'] = df['grade'].astype(str).str.strip()

    # Normalize boolean-like columns
    bool_columns = ["has_confectionery", "has_oil", "has_pasta"]
    for col in bool_columns:
        df[col] = df[col].apply(normalize_bool_value)
    return df

# Insert new stores or update existing ones base on store_code
# Returns the number of processed rows
def upsert_stores(df: pd.DataFrame, db: Session) -> int:
    processed_count = 0
    for _, row in df.iterrows():
        existing_store = (
            db.query(Store)
            .filter(Store.store_code == row['store_code'])
            .first()
        )

        # Update existing store
        if existing_store:
            existing_store.store_name = row['store_name']
            existing_store.region = row['region']
            existing_store.address = row['address']
            existing_store.lat = row['lat']
            existing_store.lon = row['lon']
            existing_store.grade = row['grade']
            existing_store.has_confectionery = row['has_confectionery']
            existing_store.has_oil = row['has_oil']
            existing_store.has_pasta = row['has_pasta']

        # Insert new store
        else:
            new_store = Store(
                store_code=row['store_code'],
                store_name=row['store_name'],
                region=row['region'],
                address=row['address'],
                lat=row['lat'],
                lon=row['lon'],
                grade=row['grade'],
                has_confectionery=row['has_confectionery'],
                has_oil=row['has_oil'],
                has_pasta=row['has_pasta'],
                is_active=True,
            )
            db.add(new_store)
        processed_count += 1
    db.commit()
    return processed_count

# Full import flow for store master data
def import_stores_from_excel(file_path: str | Path, db: Session) -> int:
    df = read_store_excel(file_path)
    df = normalize_column_names(df)
    validate_store_columns(df)
    df = transform_store_dataframe(df)
    return upsert_stores(df, db)