from __future__ import annotations

import pandas as pd
import pytest

from server.app.services import import_visitors_service


@pytest.mark.unit
def test_import_visitors_generates_temp_password_when_missing(db) -> None:
    df = pd.DataFrame(
        [
            {
                "username": "visitor-new",
                "role": "visitor",
                "visitor_code": "VIS-100",
                "full_name": "ویزیتور جدید",
                "default_start_lat": 35.7,
                "default_start_lon": 51.4,
                "default_capacity": 30,
                "is_active": True,
            }
        ]
    )
    normalized = import_visitors_service.normalize_column_names(df)
    import_visitors_service.validate_visitor_columns(normalized)
    transformed = import_visitors_service.transform_visitor_dataframe(normalized)
    result = import_visitors_service.upsert_visitor_profiles(transformed, db)

    assert result["processed_count"] == 1
    assert "visitor-new" in result["generated_temp_passwords"]
    assert len(result["generated_temp_passwords"]["visitor-new"]) >= 12

