from __future__ import annotations

from datetime import date

import pytest

from server.app.utils.calendar import get_next_working_day, is_working_day


@pytest.mark.unit
def test_friday_is_non_working_day() -> None:
    # 2026-04-03 is Friday.
    assert is_working_day(date(2026, 4, 3)) is False


@pytest.mark.unit
def test_get_next_working_day_skips_friday() -> None:
    assert get_next_working_day(date(2026, 4, 3)) == date(2026, 4, 4)

