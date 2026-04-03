from __future__ import annotations

from pathlib import Path

import pytest

from server.app.services.import_visitors_service import import_visitor_profiles_from_excel
from server.db.database import get_db_session


@pytest.mark.smoke
def test_import_visitors_sample_file() -> None:
    path = Path("data/visitors_sample_10.xlsx")
    if not path.exists():
        pytest.skip("visitors sample file is not present in current workspace.")

    db = get_db_session()
    try:
        processed_count = import_visitor_profiles_from_excel(str(path), db)
    finally:
        db.close()

    assert processed_count >= 10
