from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from client.components.jalali_date import jalali_date_input
from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_card, neu_metric, neu_section_header
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import reporting_export_service, telesales_service
from server.db.database import get_db_session

_ALL_VISITORS_OPTION = "— همه ویزیتورها —"


def _load_assignments(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.work_date,
            v.visitor_code,
            s.store_code,
            s.store_name,
            a.route_order,
            a.route_distance_km,
            a.assignment_status,
            vi.result AS visit_result
        FROM daily_assignments a
        JOIN visitor_profiles v ON v.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN visits vi ON vi.assignment_id = a.id
        WHERE a.work_date = :wd
        ORDER BY v.visitor_code, a.route_order IS NULL, a.route_order, s.store_code
        """
        return pd.read_sql_query(query, db.bind, params={"wd": work_date.isoformat()})
    finally:
        db.close()


def _load_visits(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            vi.id AS visit_id,
            vi.visit_date,
            vp.visitor_code,
            s.store_code,
            vi.result,
            vi.note
        FROM visits vi
        JOIN visitor_profiles vp ON vp.id = vi.visitor_id
        JOIN stores s ON s.id = vi.store_id
        WHERE vi.visit_date = :wd
        ORDER BY vp.visitor_code, s.store_code
        """
        return pd.read_sql_query(query, db.bind, params={"wd": work_date.isoformat()})
    finally:
        db.close()


def _load_route_map_data(work_date: date, visitor_id: int) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id,
            a.work_date,
            v.visitor_code,
            s.store_code,
            s.store_name,
            s.lat,
            s.lon,
            a.route_order,
            a.assignment_status,
            COALESCE(dvs.start_lat, v.default_start_lat) AS start_lat,
            COALESCE(dvs.start_lon, v.default_start_lon) AS start_lon
        FROM daily_assignments a
        JOIN visitor_profiles v ON v.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN daily_visitor_statuses dvs
            ON dvs.visitor_id = a.visitor_id AND dvs.work_date = a.work_date
        WHERE a.work_date = :wd AND a.visitor_id = :vid
        ORDER BY a.route_order IS NULL, a.route_order, s.store_code
        """
        return pd.read_sql_query(
            query,
            db.bind,
            params={"wd": work_date.isoformat(), "vid": visitor_id},
        )
    finally:
        db.close()


def _get_visitor_options(work_date: date) -> dict[str, int]:
    db = get_db_session()
    try:
        rows = (
            db.query(VisitorProfile.id, VisitorProfile.visitor_code)
            .join(DailyAssignment, DailyAssignment.visitor_id == VisitorProfile.id)
            .filter(DailyAssignment.work_date == work_date)
            .distinct()
            .order_by(VisitorProfile.visitor_code)
            .all()
        )
        return {code: visitor_id for visitor_id, code in rows}
    finally:
        db.close()


def _export_all_routes(work_date: date, visitor_options: dict[str, int]) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for visitor_code, visitor_id in visitor_options.items():
            db = get_db_session()
            try:
                route_buffer = reporting_export_service.export_visitor_route_excel(
                    db=db,
                    work_date=work_date,
                    visitor_id=visitor_id,
                )
            finally:
                db.close()

            route_df = pd.read_excel(BytesIO(route_buffer.getvalue()), sheet_name="route")
            route_df.to_excel(writer, sheet_name=visitor_code[:31], index=False)

    output.seek(0)
    return output


def render_supervisor_dashboard(current_user: dict) -> None:
    del current_user

    st.markdown('<div class="page-title">داشبورد سرپرست</div>', unsafe_allow_html=True)

    neu_card(
        '<span style="font-weight:600;color:#1e40af;">👁️‍🗨️ حالت نظارتی - فقط مشاهده</span>',
        css_class="monitoring-bar",
    )

    work_date = jalali_date_input(
        label="📅 تاریخ کاری",
        key_prefix="supervisor_work_date",
        default_gregorian=date.today(),
    )

    db = get_db_session()
    try:
        kpis = reporting_export_service.get_daily_kpis(db, work_date)
        pending_queue = telesales_service.list_pending_followups(db, as_of_date=work_date)
    finally:
        db.close()

    neu_section_header("شاخص‌های روزانه")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        neu_metric("صف تامین‌پذیر", kpis["due_stores"])
    with k2:
        neu_metric("تخصیص‌شده", kpis["assigned_stores"])
    with k3:
        neu_metric("ویزیت تکمیل‌شده", kpis["completed_visits"])
    with k4:
        neu_metric("سبز / زرد / قرمز", f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}")
    with k5:
        neu_metric("صف فروش تلفنی", kpis["telesales_queue_size"])

    visitor_options = _get_visitor_options(work_date)
    assignment_df = _load_assignments(work_date)

    neu_section_header("بررسی مسیر ویزیتورها")
    selected_code = st.selectbox(
        "انتخاب ویزیتور",
        options=[_ALL_VISITORS_OPTION] + list(visitor_options.keys()),
        key=f"supervisor_select_{work_date.isoformat()}",
    )

    if selected_code == _ALL_VISITORS_OPTION:
        if assignment_df.empty:
            st.info("برای این تاریخ تخصیصی وجود ندارد.")
        else:
            st.dataframe(assignment_df, use_container_width=True)
    else:
        selected_id = visitor_options[selected_code]
        filtered_df = assignment_df[assignment_df["visitor_code"] == selected_code]
        if filtered_df.empty:
            st.info(f"برای {selected_code} تخصیصی ثبت نشده است.")
        else:
            st.dataframe(filtered_df, use_container_width=True)

        route_df = _load_route_map_data(work_date, selected_id)
        if not route_df.empty:
            render_route_map(route_df)

    neu_section_header("خروجی‌ها")
    d1, d2 = st.columns(2)
    with d1:
        if selected_code != _ALL_VISITORS_OPTION and selected_code in visitor_options:
            db = get_db_session()
            try:
                route_buf = reporting_export_service.export_visitor_route_excel(
                    db=db,
                    work_date=work_date,
                    visitor_id=visitor_options[selected_code],
                )
            finally:
                db.close()

            st.download_button(
                label=f"📥 دانلود مسیر {selected_code}",
                data=route_buf.getvalue(),
                file_name=f"route_{work_date.isoformat()}_{selected_code}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with d2:
        if visitor_options:
            all_buf = _export_all_routes(work_date, visitor_options)
            st.download_button(
                label="📥 دانلود همه مسیرها",
                data=all_buf.getvalue(),
                file_name=f"all_routes_{work_date.isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    neu_section_header("نتایج ویزیت")
    visit_df = _load_visits(work_date)
    if visit_df.empty:
        st.info("نتیجه ویزیتی برای این تاریخ ثبت نشده است.")
    else:
        st.dataframe(visit_df, use_container_width=True)

    neu_section_header("صف فروش تلفنی")
    if pending_queue:
        st.dataframe(pd.DataFrame(pending_queue), use_container_width=True)
    else:
        st.info("موردی در صف فروش تلفنی وجود ندارد.")
