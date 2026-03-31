from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.enums.contact_status import ContactStatus
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.models.store import Store
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.user import User  # noqa: F401
from server.app.models.visit import Visit

REQUIRED_TELESALES_FOLLOWUP_COLUMNS = {
    "followup_date",
    "store_code",
    "visit_id",
    "contact_status",
    "result",
    "note",
}


def read_telesales_followups_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def validate_telesales_followup_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_TELESALES_FOLLOWUP_COLUMNS) - set(df.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing_str}")


def transform_telesales_followup_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["followup_date"] = pd.to_datetime(df["followup_date"], errors="coerce").dt.date
    df["store_code"] = df["store_code"].astype(str).str.strip()
    df["visit_id"] = pd.to_numeric(df["visit_id"], errors="coerce")
    df["contact_status"] = df["contact_status"].astype(str).str.strip().str.lower()
    df["result"] = df["result"].astype(str).str.strip().str.lower()
    df["note"] = df["note"].astype(str)
    return df


def validate_telesales_followup_values(df: pd.DataFrame, db: Session) -> None:
    errors: list[str] = []

    invalid_dates = df[df["followup_date"].isna()]
    if not invalid_dates.empty:
        errors.append("followup_date contains invalid values.")

    invalid_visit_ids = df[df["visit_id"].isna()]
    if not invalid_visit_ids.empty:
        errors.append("visit_id must be numeric.")

    duplicate_pairs = df[df.duplicated(subset=["visit_id", "followup_date"], keep=False)]
    for idx in duplicate_pairs.index:
        errors.append(f"Row {idx + 2}: duplicate (visit_id, followup_date) found in file.")

    valid_contact_statuses = {item.value for item in ContactStatus}
    invalid_contact_statuses = sorted(set(df["contact_status"]) - valid_contact_statuses)
    if invalid_contact_statuses:
        errors.append(f"Invalid contact_status values: {', '.join(invalid_contact_statuses)}")

    valid_results = {item.value for item in TelesalesOutcome}
    invalid_results = sorted(set(df["result"]) - valid_results)
    if invalid_results:
        errors.append(f"Invalid result values: {', '.join(invalid_results)}")

    store_codes = set(df["store_code"].tolist())
    existing_store_codes = {
        code
        for (code,) in (
            db.query(Store.store_code)
            .filter(Store.store_code.in_(store_codes))
            .all()
        )
    }
    unknown_store_codes = sorted(store_codes - existing_store_codes)
    if unknown_store_codes:
        errors.append(f"Unknown store_code values: {', '.join(unknown_store_codes)}")

    visit_ids = set(int(visit_id) for visit_id in df["visit_id"].dropna().tolist())
    existing_visit_ids = {
        visit_id
        for (visit_id,) in (
            db.query(Visit.id)
            .filter(Visit.id.in_(visit_ids))
            .all()
        )
    }
    unknown_visit_ids = sorted(visit_ids - existing_visit_ids)
    if unknown_visit_ids:
        errors.append(f"Unknown visit_id values: {', '.join(str(v) for v in unknown_visit_ids)}")

    store_rows = (
        db.query(Store.id, Store.store_code)
        .filter(Store.store_code.in_(store_codes))
        .all()
    )
    store_code_to_id = {store_code: store_id for store_id, store_code in store_rows}
    visit_rows = (
        db.query(Visit.id, Visit.store_id)
        .filter(Visit.id.in_(visit_ids))
        .all()
    )
    visit_id_to_store_id = {visit_id: store_id for visit_id, store_id in visit_rows}

    for idx, row in df.iterrows():
        if pd.isna(row["visit_id"]) or pd.isna(row["followup_date"]):
            continue

        store_code = row["store_code"]
        if store_code not in store_code_to_id:
            continue

        visit_id = int(row["visit_id"])
        if visit_id not in visit_id_to_store_id:
            continue

        expected_store_id = visit_id_to_store_id[visit_id]
        actual_store_id = store_code_to_id[store_code]
        if actual_store_id != expected_store_id:
            errors.append(
                f"Row {idx + 2}: store_code '{store_code}' does not match visit_id {visit_id} store."
            )

    if errors:
        raise ValueError("\n".join(sorted(set(errors))))


def upsert_telesales_followups(df: pd.DataFrame, db: Session) -> int:
    store_rows = db.query(Store.id, Store.store_code).all()
    store_code_to_id = {store_code: store_id for store_id, store_code in store_rows}

    processed_count = 0
    try:
        for _, row in df.iterrows():
            followup_date: date = row["followup_date"]
            store_id = store_code_to_id[row["store_code"]]
            visit_id = int(row["visit_id"])
            note_value = str(row["note"]).strip() or None

            existing = (
                db.query(TelesalesFollowup)
                .filter(
                    TelesalesFollowup.visit_id == visit_id,
                    TelesalesFollowup.followup_date == followup_date,
                )
                .first()
            )

            if existing:
                existing.store_id = store_id
                existing.contact_status = row["contact_status"]
                existing.result = row["result"]
                existing.note = note_value
            else:
                db.add(
                    TelesalesFollowup(
                        store_id=store_id,
                        visit_id=visit_id,
                        followup_date=followup_date,
                        contact_status=row["contact_status"],
                        result=row["result"],
                        note=note_value,
                    )
                )
            processed_count += 1

        db.commit()
        return processed_count
    except Exception:
        db.rollback()
        raise


def import_telesales_followups_from_excel(
    file_path: str | Path,
    db: Session,
    allow_backfill_mode: bool = False,
) -> int:
    if not allow_backfill_mode:
        raise ValueError(
            "Telesales followup import is backfill-only and disabled in normal MVP operations."
        )

    df = read_telesales_followups_excel(file_path)
    df = normalize_column_names(df)
    validate_telesales_followup_columns(df)
    df = transform_telesales_followup_dataframe(df)
    validate_telesales_followup_values(df, db)
    return upsert_telesales_followups(df, db)
