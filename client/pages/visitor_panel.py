# Purpose: Visitor panel for route execution and visit result submission.
# Workflow Role: Field-user workflow for published assignments only.

from __future__ import annotations

from datetime import date
import html
import re

import pandas as pd
import streamlit as st

from client.components.empty_state import get_empty_state_message
from client.components.jalali_date import jalali_date_input
from client.components.route_map import render_route_map
from client.i18n import align, direction, is_fa, start_side, t
from client.styles.neumorphism import (
    neu_section_header,
    render_metric_grid,
    render_page_title,
    status_badge,
)
from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.visit_result import VisitResult
from server.app.services import dashboard_query_service, reporting_export_service, runtime_health_service, visit_service
from server.db.database import get_db

RESULT_COLORS = {
    "green": "#27AE60",
    "yellow": "#F39C12",
    "red": "#E74C3C",
}

def _visit_result_labels() -> dict[str, str]:
    return {
        VisitResult.GREEN.value: t("سبز (خرید انجام شد)", "Green (sale completed)"),
        VisitResult.YELLOW.value: t("زرد (ویزیت شد، فروش نشد)", "Yellow (visited, no sale)"),
        VisitResult.RED.value: t("قرمز (ویزیت انجام نشد)", "Red (visit not completed)"),
    }

_EMPTY_NOTE_MARKERS = {
    "",
    "<div/>",
    "<div></div>",
    "<div><br></div>",
    "<div><br/></div>",
    "<p></p>",
    "<p><br></p>",
    "<br>",
    "<br/>",
    "<br />",
    "nan",
    "none",
    "null",
}
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalized_note(value: object) -> str:
    # FIX: Strip placeholder HTML so empty notes never render raw tags like <div/>.
    raw_text = str(value or "").strip()
    if raw_text.lower() in _EMPTY_NOTE_MARKERS:
        return ""

    without_tags = _HTML_TAG_RE.sub(" ", raw_text)
    text = html.unescape(without_tags).replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if text.lower() in _EMPTY_NOTE_MARKERS:
        return ""
    return text


@st.cache_data(ttl=300, show_spinner=False)
def _cached_visitor_profile(user_id: int):
    with get_db() as db:
        return dashboard_query_service.get_visitor_profile_for_user(db=db, user_id=user_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_assignments(visitor_id: int, work_date_iso: str) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_visitor_assignments_df(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
        )


def _render_visit_progress(completed_count: int, total_stops: int) -> float:
    # FIX: Visitor progress bar should be RTL and have right-aligned descriptive text.
    progress_ratio = (completed_count / total_stops) if total_stops else 0.0
    progress_pct = int(round(progress_ratio * 100))
    progress_fill_color = "#27AE60" if progress_pct >= 100 else ("#3D5FCC" if is_fa() else "#D9A300")
    progress_note = t(
        f"{completed_count} از {total_stops} ویزیت انجام شده ({progress_pct}٪)",
        f"{completed_count} of {total_stops} visits completed ({progress_pct}%)",
    )
    st.markdown(
        f"""
        <div class="visitor-progress-wrap">
            <div class="visitor-progress-track">
                <div class="visitor-progress-fill" style="width:{progress_pct}%; background:{progress_fill_color};"></div>
            </div>
            <div class="visitor-progress-note">{progress_note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return progress_ratio


def _render_grade_distribution(assignments_df: pd.DataFrame) -> None:
    # FIX: Show per-grade store counts in visitor panel (VIP, A+, A, B, C).
    if "store_grade" not in assignments_df.columns:
        return

    order = ["VIP", "A+", "A", "B", "C"]
    counts = (
        assignments_df["store_grade"]
        .fillna(t("نامشخص", "Unknown"))
        .astype(str)
        .str.strip()
        .str.upper()
        .value_counts()
        .to_dict()
    )
    parts = [f"{int(counts[g])} {g}" for g in order if int(counts.get(g, 0)) > 0]
    unknown_count = int(sum(v for k, v in counts.items() if k not in set(order)))
    if unknown_count > 0:
        parts.append(t(f"{unknown_count} نامشخص", f"{unknown_count} Unknown"))

    if parts:
        st.markdown(
            f'<div class="panel-description"><strong>{t("ترکیب گرید فروشگاه‌های مسیر:", "Route Store Grade Mix:")}</strong> {" | ".join(parts)}</div>',
            unsafe_allow_html=True,
        )


def render_visitor_panel(current_user: dict) -> None:
    visit_result_labels = _visit_result_labels()

    render_page_title(t("مسیر من", "My Route"))
    profile = _cached_visitor_profile(current_user["id"])
    if not profile:
        st.error(t("برای این حساب کاربری پروفایل ویزیتور پیدا نشد.", "No visitor profile was found for this account."))
        return

    work_date = jalali_date_input(
        label=t("📅 تاریخ کاری", "📅 Work Date"),
        key_prefix="visitor_work_date",
        default_gregorian=date.today(),
    )
    work_date_iso = work_date.isoformat()
    assignments_df = _cached_assignments(profile.id, work_date_iso)

    if assignments_df.empty:
        st.info(get_empty_state_message(role="visitor", context="no_assignments"))
        return

    total_stops = len(assignments_df)
    completed_count = int(assignments_df["visit_result"].notna().sum())
    total_km = assignments_df["route_distance_km"].dropna()
    max_distance = float(total_km.max()) if not total_km.empty else 0.0

    # FIX: Better top-section alignment using responsive metric grid.
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    render_metric_grid(
        [
            (t("تعداد توقف", "Stops"), total_stops),
            (t("تکمیل‌شده", "Completed"), completed_count),
            (t("مسافت مسیر (km)", "Route Distance (km)"), f"{max_distance:.1f}"),
        ]
    )
    _render_grade_distribution(assignments_df)
    progress_ratio = _render_visit_progress(completed_count=completed_count, total_stops=total_stops)
    if progress_ratio >= 1:
        st.success(t("همه توقف‌ها کامل شد. مسیر امروز با موفقیت پایان یافت.", "All stops are complete. Today's route has finished successfully."))

    neu_section_header(t("نقشه مسیر", "Route Map"))
    runtime_state = runtime_health_service.get_offline_runtime_status()
    if (not bool(runtime_state.get("osrm_up", False))) or (not bool(runtime_state.get("tiles_up", False))):
        st.info(t("حالت کاهشی فعال است: اگر سرویس محلی در دسترس نباشد، نقشه بدون خیابان یا با مسیر خطی نمایش داده می‌شود.", "Degraded mode is active: if local services are unavailable, the map is shown without streets or with straight-line routing."))
    if not bool(runtime_state.get("osrm_data_ready", False)):
        st.warning(t("فایل داده OSRM پیدا نشد (offline/osrm/data/tehran-latest.osrm).", "OSRM data file was not found (offline/osrm/data/tehran-latest.osrm)."))
    if not bool(runtime_state.get("tiles_data_ready", False)):
        st.warning(t("فایل MBTiles پیدا نشد (offline/tiles/data/*.mbtiles).", "MBTiles data file was not found (offline/tiles/data/*.mbtiles)."))
    # FIX: [PERF-04] Reuse page-level runtime health state in map renderer.
    render_route_map(
        assignments_df,
        runtime_status=runtime_state,
        show_runtime_messages=False,
    )

    with get_db() as db:
        route_buf = reporting_export_service.export_visitor_route_excel(
            db=db,
            work_date=work_date,
            visitor_id=profile.id,
        )
    st.download_button(
        label=t("📥 دانلود مسیر من", "📥 Download My Route"),
        data=route_buf.getvalue(),
        file_name=f"my_route_{work_date_iso}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    neu_section_header(t("ثبت نتیجه ویزیت فروشگاه‌ها", "Submit Store Visit Results"))
    for row in assignments_df.to_dict(orient="records"):
        route_order = int(row["route_order"]) if pd.notna(row["route_order"]) else "—"
        expander_title = t(
            f"توقف {route_order} • {row['store_code']} — {row['store_name']}",
            f"Stop {route_order} • {row['store_code']} — {row['store_name']}",
        )

        with st.expander(expander_title, expanded=False):
            info_html = f"""
            <div class="neu-card-flat">
                <div style="display:flex;gap:2rem;flex-wrap:wrap;direction:{direction()};text-align:{align()};justify-content:flex-start;">
                    <div><strong>{t("آدرس", "Address")}:</strong> {row['address'] or '—'}</div>
                    <div><strong>{t("مختصات", "Coordinates")}:</strong> {row['lat']}, {row['lon']}</div>
                    <div><strong>{t("وضعیت تخصیص", "Assignment Status")}:</strong> {status_badge(str(row['assignment_status']))}</div>
                </div>
            </div>
            """
            st.markdown(info_html, unsafe_allow_html=True)

            if pd.notna(row["visit_result"]):
                result = str(row["visit_result"])
                color = RESULT_COLORS.get(result, "#6C7A89")
                note_value = _normalized_note(row.get("visit_note"))
                note_text = note_value if note_value else t("یادداشت ثبت نشده است.", "No note has been registered.")
                note_block = f"<br/><em>{html.escape(note_text)}</em>"
                st.markdown(
                    f"""<div class="neu-card-flat" style="border-{start_side()}:4px solid {color};padding-{start_side()}:1rem;direction:{direction()};text-align:{align()};">
                        <strong>{t("نتیجه ثبت‌شده", "Recorded Result")}:</strong> {status_badge(result)}
                        {note_block}
                    </div>""",
                    unsafe_allow_html=True,
                )
                continue

            if row["assignment_status"] != AssignmentStatus.PUBLISHED.value:
                st.info(t("ثبت نتیجه فقط برای تخصیص‌های منتشرشده فعال است.", "Result submission is enabled only for published assignments."))
                continue

            form_key = f"visit_{row['assignment_id']}"
            with st.form(form_key):
                st.markdown(f"**{t('ثبت نتیجه ویزیت', 'Submit Visit Result')}**")
                selected_label = st.selectbox(
                    t("نتیجه", "Result"),
                    options=list(visit_result_labels.values()),
                    key=f"result_{row['assignment_id']}",
                )
                result = next(
                    code
                    for code, label in visit_result_labels.items()
                    if label == selected_label
                )
                note = st.text_area(
                    t("یادداشت", "Note"),
                    key=f"note_{row['assignment_id']}",
                    placeholder=t("یادداشت اختیاری برای این ویزیت...", "Optional note for this visit..."),
                )
                submitted = st.form_submit_button(t("ثبت نتیجه", "Submit Result"), use_container_width=True)

            if submitted:
                try:
                    with get_db() as db:
                        visit_service.submit_visit_result(
                            db=db,
                            assignment_id=int(row["assignment_id"]),
                            visitor_user_id=current_user["id"],
                            result=result,
                            note=note,
                        )
                    st.success(t("نتیجه ویزیت با موفقیت ثبت شد.", "Visit result was submitted successfully."))
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(t(f"خطا در ثبت نتیجه: {exc}", f"Error submitting visit result: {exc}"))
