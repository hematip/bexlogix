# Purpose: Shared Jalali date picker for all dashboards.
# Workflow Role: Provides a consistent Persian date selection UX with optional today shortcut.

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


# Contract: _to_fa_digits executes one deterministic step in the workflow.
def _to_fa_digits(value: str | int) -> str:
    return str(value).translate(_EN_TO_FA_DIGITS)


# Contract: _to_en_digits executes one deterministic step in the workflow.
def _to_en_digits(value: str) -> str:
    return str(value).translate(_FA_TO_EN_DIGITS)


# Contract: _jalali_days_in_month executes one deterministic step in the workflow.
def _jalali_days_in_month(year: int, month: int) -> int:
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


# Contract: jalali_date_input executes one deterministic step in the workflow.
def jalali_date_input(
    label: str,
    key_prefix: str,
    default_gregorian: gregorian_date | None = None,
) -> gregorian_date:
    # FIX: [UX-01] Add quick "today" shortcut while keeping three dropdowns intact.
    default_base = default_gregorian or gregorian_date.today()
    default_jalali = jdatetime.date.fromgregorian(date=default_base)

    year_key = f"{key_prefix}_jalali_year"
    month_key = f"{key_prefix}_jalali_month"
    day_key = f"{key_prefix}_jalali_day"
    today_jalali = jdatetime.date.today()

    if year_key not in st.session_state:
        st.session_state[year_key] = int(default_jalali.year)
    if month_key not in st.session_state:
        st.session_state[month_key] = (
            f"{_to_fa_digits(f'{int(default_jalali.month):02d}')} - {_PERSIAN_MONTHS[int(default_jalali.month)]}"
        )
    if day_key not in st.session_state:
        st.session_state[day_key] = int(default_jalali.day)

    preview_year = int(st.session_state.get(year_key, int(default_jalali.year)))
    preview_month_label = str(st.session_state.get(month_key, ""))
    preview_month = int(default_jalali.month)
    if preview_month_label and "-" in preview_month_label:
        try:
            preview_month = int(_to_en_digits(preview_month_label.split("-")[0].strip()))
        except Exception:
            preview_month = int(default_jalali.month)
    preview_month = max(1, min(12, preview_month))
    preview_day = int(st.session_state.get(day_key, int(default_jalali.day)))
    preview_day = max(1, min(_jalali_days_in_month(preview_year, preview_month), preview_day))

    preview_jalali = jdatetime.date(preview_year, preview_month, preview_day)
    preview_gregorian = preview_jalali.togregorian()
    preview_fa = f"{_to_fa_digits(preview_day)} {_PERSIAN_MONTHS[preview_month]} {_to_fa_digits(preview_year)}"

    caption_col, today_col = st.columns([5, 1], gap="small", vertical_alignment="center")
    with caption_col:
        st.markdown(
            f'<div class="jalali-selected-caption">تاریخ انتخابی: {preview_fa} (معادل میلادی: {preview_gregorian.isoformat()})</div>',
            unsafe_allow_html=True,
        )
    with today_col:
        if st.button("📅 امروز", key=f"{key_prefix}_today_shortcut", use_container_width=False):
            st.session_state[year_key] = int(today_jalali.year)
            st.session_state[month_key] = (
                f"{_to_fa_digits(f'{int(today_jalali.month):02d}')} - {_PERSIAN_MONTHS[int(today_jalali.month)]}"
            )
            st.session_state[day_key] = int(today_jalali.day)
            st.rerun()

    # FIX: [UX-DATE-01] Keep year/month/day as three equal-width columns across all panels.
    col_year, col_month, col_day = st.columns(3)

    with col_year:
        year = st.selectbox(
            "سال",
            options=list(range(default_jalali.year - 5, default_jalali.year + 6)),
            index=5,
            key=year_key,
            format_func=lambda v: _to_fa_digits(v),
        )

    with col_month:
        month_labels = [f"{_to_fa_digits(f'{idx:02d}')} - {_PERSIAN_MONTHS[idx]}" for idx in range(1, 13)]
        default_month_idx = int(default_jalali.month) - 1
        selected_month_label = st.selectbox(
            "ماه",
            options=month_labels,
            index=default_month_idx,
            key=month_key,
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
            key=day_key,
            format_func=lambda v: _to_fa_digits(v),
        )

    selected_jalali = jdatetime.date(int(year), int(month), int(day))
    return selected_jalali.togregorian()
