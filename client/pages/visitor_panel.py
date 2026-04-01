from datetime import date
import html

import pandas as pd
import streamlit as st

from client.components.jalali_date import jalali_date_input
from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_metric, neu_section_header, status_badge
from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.visit_result import VisitResult
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import reporting_export_service, visit_service
from server.db.database import get_db_session


RESULT_COLORS = {
    "green": "#27AE60",
    "yellow": "#F39C12",
    "red": "#E74C3C",
}

VISIT_RESULT_LABELS = {
    VisitResult.GREEN.value: "سبز (خرید انجام شد)",
    VisitResult.YELLOW.value: "زرد (ویزیت شد، فروش نشد)",
    VisitResult.RED.value: "قرمز (ویزیت انجام نشد)",
}

_EMPTY_NOTE_MARKERS = {"", "<div/>", "<div></div>", "<p></p>", "<br>", "<br/>", "<br />", "nan", "none"}


def _normalized_note(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in _EMPTY_NOTE_MARKERS:
        return ""
    return text


def _get_visitor_profile(user_id: int) -> VisitorProfile | None:
    db = get_db_session()
    try:
        return db.query(VisitorProfile).filter(VisitorProfile.user_id == user_id).first()
    finally:
        db.close()


def _load_assignments(visitor_id: int, work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id,
            a.work_date,
            s.store_code,
            s.store_name,
            s.address,
            s.lat,
            s.lon,
            a.route_order,
            a.route_distance_km,
            a.assignment_status,
            COALESCE(dvs.start_lat, vp.default_start_lat) AS start_lat,
            COALESCE(dvs.start_lon, vp.default_start_lon) AS start_lon,
            vi.id AS visit_id,
            vi.result AS visit_result,
            vi.note AS visit_note
        FROM daily_assignments a
        JOIN visitor_profiles vp ON vp.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN daily_visitor_statuses dvs
            ON dvs.visitor_id = a.visitor_id AND dvs.work_date = a.work_date
        LEFT JOIN visits vi ON vi.assignment_id = a.id
        WHERE a.visitor_id = :vid AND a.work_date = :wd
        ORDER BY a.route_order IS NULL, a.route_order, s.store_code
        """
        return pd.read_sql_query(
            query,
            db.bind,
            params={"vid": visitor_id, "wd": work_date.isoformat()},
        )
    finally:
        db.close()


def render_visitor_panel(current_user: dict) -> None:
    st.markdown('<div class="page-title">مسیر من</div>', unsafe_allow_html=True)

    profile = _get_visitor_profile(current_user["id"])
    if not profile:
        st.error("برای این حساب کاربری پروفایل ویزیتور پیدا نشد.")
        return

    work_date = jalali_date_input(
        label="📅 تاریخ کاری",
        key_prefix="visitor_work_date",
        default_gregorian=date.today(),
    )
    assignments_df = _load_assignments(profile.id, work_date)

    if assignments_df.empty:
        st.info("برای این تاریخ تخصیصی ثبت نشده است.")
        return

    total_stops = len(assignments_df)
    completed_count = int(assignments_df["visit_result"].notna().sum())
    total_km = assignments_df["route_distance_km"].dropna()
    max_distance = float(total_km.max()) if not total_km.empty else 0.0

    m1, m2, m3 = st.columns(3)
    with m1:
        neu_metric("تعداد توقف", total_stops)
    with m2:
        neu_metric("تکمیل‌شده", completed_count)
    with m3:
        neu_metric("مسافت مسیر (km)", f"{max_distance:.1f}")

    neu_section_header("نقشه مسیر")
    render_route_map(assignments_df)

    db = get_db_session()
    try:
        route_buf = reporting_export_service.export_visitor_route_excel(
            db=db,
            work_date=work_date,
            visitor_id=profile.id,
        )
    finally:
        db.close()

    st.download_button(
        label="📥 دانلود مسیر من",
        data=route_buf.getvalue(),
        file_name=f"my_route_{work_date.isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    neu_section_header("ثبت نتیجه ویزیت فروشگاه‌ها")
    for row in assignments_df.to_dict(orient="records"):
        route_order = int(row["route_order"]) if pd.notna(row["route_order"]) else "—"
        expander_title = f"توقف {route_order} • {row['store_code']} — {row['store_name']}"

        with st.expander(expander_title, expanded=False):
            info_html = f"""
            <div class="neu-card-flat">
                <div style="display:flex;gap:2rem;flex-wrap:wrap;">
                    <div><strong>آدرس:</strong> {row['address'] or '—'}</div>
                    <div><strong>مختصات:</strong> {row['lat']}, {row['lon']}</div>
                    <div><strong>وضعیت تخصیص:</strong> {status_badge(row['assignment_status'])}</div>
                </div>
            </div>
            """
            st.markdown(info_html, unsafe_allow_html=True)

            if pd.notna(row["visit_result"]):
                result = str(row["visit_result"])
                color = RESULT_COLORS.get(result, "#6C7A89")
                note_value = _normalized_note(row.get("visit_note"))
                if note_value:
                    note_block = f"<br/><em>{html.escape(note_value)}</em>"
                elif result == VisitResult.RED.value:
                    note_block = "<br/><em>یادداشت نوشته نشده است یا خالی.</em>"
                else:
                    note_block = ""
                st.markdown(
                    f"""<div class="neu-card-flat" style="border-right:4px solid {color};padding-right:1rem;">
                        <strong>نتیجه ثبت‌شده:</strong> {status_badge(result)}
                        {note_block}
                    </div>""",
                    unsafe_allow_html=True,
                )
                continue

            if row["assignment_status"] != AssignmentStatus.PUBLISHED.value:
                st.info("ثبت نتیجه فقط برای تخصیص‌های منتشرشده فعال است.")
                continue

            form_key = f"visit_{row['assignment_id']}"
            with st.form(form_key):
                st.markdown("**ثبت نتیجه ویزیت**")
                selected_label = st.selectbox(
                    "نتیجه",
                    options=list(VISIT_RESULT_LABELS.values()),
                    key=f"result_{row['assignment_id']}",
                )
                result = next(
                    code
                    for code, label in VISIT_RESULT_LABELS.items()
                    if label == selected_label
                )
                note = st.text_area(
                    "یادداشت",
                    key=f"note_{row['assignment_id']}",
                    placeholder="یادداشت اختیاری برای این ویزیت...",
                )
                submitted = st.form_submit_button("ثبت نتیجه", use_container_width=True)

            if submitted:
                db = get_db_session()
                try:
                    visit_service.submit_visit_result(
                        db=db,
                        assignment_id=int(row["assignment_id"]),
                        visitor_user_id=current_user["id"],
                        result=result,
                        note=note,
                    )
                    st.success("نتیجه ویزیت با موفقیت ثبت شد.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"خطا در ثبت نتیجه: {exc}")
                finally:
                    db.close()
