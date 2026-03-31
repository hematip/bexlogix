from pathlib import Path

from sqlalchemy.orm import Session


def import_legacy_visits_from_excel(
    file_path: str | Path,
    db: Session,
    allow_backfill_mode: bool = False,
) -> int:
    """
    Backfill-only placeholder for future one-time migration.

    MVP policy:
    - Visit records are app-native and should be created by visitor workflow.
    - Legacy import remains intentionally disabled unless explicit backfill mode is enabled.
    """
    _ = (file_path, db)
    if not allow_backfill_mode:
        raise ValueError(
            "Legacy visits import is disabled in MVP. "
            "Visits must be created through in-app submission."
        )

    raise NotImplementedError(
        "Legacy visit migration format is not finalized yet. "
        "Implement this only for one-time migration projects."
    )
