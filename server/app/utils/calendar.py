from __future__ import annotations

from datetime import date, timedelta

import jdatetime

# FIX: [BIZ-01] Fixed public-holiday list for current Jalali year (manager-approved default policy).
_CURRENT_JALALI_YEAR = jdatetime.date.today().year
_FIXED_HOLIDAYS_JALALI: dict[int, set[tuple[int, int]]] = {
    _CURRENT_JALALI_YEAR: {
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 12),
        (1, 13),
        (11, 22),
        (12, 29),
    }
}


def _to_jalali(g_date: date) -> jdatetime.date:
    return jdatetime.date.fromgregorian(date=g_date)


def is_working_day(g_date: date) -> bool:
    jalali = _to_jalali(g_date)
    # Friday is non-working day in Iran (weekday(): Saturday=0 ... Friday=6).
    if jalali.weekday() == 6:
        return False

    holiday_set = _FIXED_HOLIDAYS_JALALI.get(jalali.year, set())
    if (jalali.month, jalali.day) in holiday_set:
        return False
    return True


def get_next_working_day(base_date: date) -> date:
    candidate = base_date
    while not is_working_day(candidate):
        candidate = candidate + timedelta(days=1)
    return candidate

