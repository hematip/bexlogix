# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from pathlib import Path

from sqlalchemy.orm import Session


# Contract: import_legacy_visits_from_excel executes one deterministic step in the workflow.
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
            "در نسخه فعلی، import ویزیت‌های قدیمی غیرفعال است و ثبت ویزیت باید داخل سامانه انجام شود."
        )

    raise NotImplementedError(
        "فرمت مهاجرت ویزیت‌های قدیمی هنوز نهایی نشده است و فقط برای پروژه مهاجرت یک‌باره باید پیاده‌سازی شود."
    )
