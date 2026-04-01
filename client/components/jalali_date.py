from __future__ import annotations

from datetime import date as gregorian_date

import jdatetime
import streamlit as st

_PERSIAN_MONTHS = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند",
}

_EN_TO_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_FA_TO_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _to_fa_digits(value: str) -> str:
    return str(value).translate(_EN_TO_FA_DIGITS)


def _to_en_digits(value: str) -> str:
    return str(value).translate(_FA_TO_EN_DIGITS)


def _jalali_days_in_month(year: int, month: int) -> int:
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def jalali_date_input(
    label: str,
    key_prefix: str,
    default_gregorian: gregorian_date | None = None,
) -> gregorian_date:
    default_base = default_gregorian or gregorian_date.today()
    default_jalali = jdatetime.date.fromgregorian(date=default_base)

    st.markdown(f'<div class="date-input-label">{label}</div>', unsafe_allow_html=True)
    col_year, col_month, col_day = st.columns([1.1, 1.3, 1.0])

    with col_year:
        year = st.selectbox(
            "سال",
            options=list(range(default_jalali.year - 5, default_jalali.year + 6)),
            index=5,
            key=f"{key_prefix}_jalali_year",
            format_func=lambda v: _to_fa_digits(v),
        )

    with col_month:
        month_labels = [f"{_to_fa_digits(f'{idx:02d}')} - {_PERSIAN_MONTHS[idx]}" for idx in range(1, 13)]
        default_month_idx = int(default_jalali.month) - 1
        selected_month_label = st.selectbox(
            "ماه",
            options=month_labels,
            index=default_month_idx,
            key=f"{key_prefix}_jalali_month",
        )
        month = int(_to_en_digits(selected_month_label.split("-")[0].strip()))

    max_days = _jalali_days_in_month(int(year), int(month))
    day_options = list(range(1, max_days + 1))
    day_default = min(int(default_jalali.day), max_days)
    day_default_index = max(0, day_default - 1)
    with col_day:
        day = st.selectbox(
            "روز",
            options=day_options,
            index=day_default_index,
            key=f"{key_prefix}_jalali_day",
            format_func=lambda v: _to_fa_digits(v),
        )

    selected_jalali = jdatetime.date(int(year), int(month), int(day))
    selected_gregorian = selected_jalali.togregorian()
    st.caption(f"تاریخ انتخاب‌شده (میلادی): {selected_gregorian.isoformat()}")
    return selected_gregorian
