from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_metric, neu_section_header, neu_card
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import reporting_export_service, telesales_service
from server.db.database import get_db_session


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _load_assignments(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.work_date, v.visitor_code, s.store_code, s.store_name,
            a.route_order, a.route_distance_km,
            a.assignment_status, vi.result AS visit_result
        FROM daily_assignments a
        JOIN visitor_profiles v ON v.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN visits vi ON vi.assignment_id = a.id
        WHERE a.work_date = :wd
        ORDER BY v.visitor_code, a.route_order, s.store_code
        """
        return pd.read_sql_query(query, db.bind, params={"wd": work_date.isoformat()})
    finally:
        db.close()


def _load_visits(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            vi.id AS visit_id, vi.visit_date, vp.visitor_code,
            s.store_code, vi.result, vi.note
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
            a.id AS assignment_id, a.work_date, v.visitor_code,
            s.store_code, s.store_name, s.lat, s.lon,
            a.route_order, a.assignment_status,
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
            query, db.bind, params={"wd": work_date.isoformat(), "vid": visitor_id}
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
        return {code: vid for vid, code in rows}
    finally:
        db.close()


def _export_all_routes(work_date: date, visitor_options: dict[str, int]) -> BytesIO:
    """Export all visitor routes into a single Excel workbook (one sheet per visitor)."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for code, vid in visitor_options.items():
            db = get_db_session()
            try:
                buf = reporting_export_service.export_visitor_route_excel(
                    db=db, work_date=work_date, visitor_id=vid,
                )
            finally:
                db.close()
            df = pd.read_excel(BytesIO(buf.getvalue()), sheet_name="route")
            sheet_name = code[:31]  # Excel sheet name limit
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render_supervisor_dashboard(current_user: dict) -> None:
    st.markdown(
        '<h2 style="margin-bottom:0.2rem;">Supervisor Dashboard</h2>',
        unsafe_allow_html=True,
    )

    neu_card(
        '<span style="font-weight:600;color:#1e40af;">👁️  Monitoring Mode — Read Only</span>',
        css_class="monitoring-bar",
    )

    work_date = st.date_input("📅  Work Date", value=date.today())

    # ── KPIs ──────────────────────────────────────────────────
    db = get_db_session()
    try:
        kpis = reporting_export_service.get_daily_kpis(db, work_date)
        pending_queue = telesales_service.list_pending_followups(db, as_of_date=work_date)
    finally:
        db.close()

    neu_section_header("Daily KPIs")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        neu_metric("Due Stores", kpis["due_stores"])
    with k2:
        neu_metric("Assigned", kpis["assigned_stores"])
    with k3:
        neu_metric("Completed", kpis["completed_visits"])
    with k4:
        neu_metric("G / Y / R", f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}")
    with k5:
        neu_metric("Telesales Queue", kpis["telesales_queue_size"])

    # ── Visitor route inspector ───────────────────────────────
    visitor_options = _get_visitor_options(work_date)

    neu_section_header("Visitor Route Inspector")
    selected_code = st.selectbox(
        "Select Visitor",
        options=["— All Visitors —"] + list(visitor_options.keys()),
    )

    assignment_df = _load_assignments(work_date)

    if selected_code == "— All Visitors —":
        if assignment_df.empty:
            st.info("No assignments for this date.")
        else:
            st.dataframe(assignment_df, use_container_width=True)
    else:
        selected_id = visitor_options[selected_code]
        filtered = assignment_df[assignment_df["visitor_code"] == selected_code]
        if filtered.empty:
            st.info(f"No assignments for {selected_code}.")
        else:
            st.dataframe(filtered, use_container_width=True)

        # Route map for selected visitor
        route_df = _load_route_map_data(work_date, selected_id)
        if not route_df.empty:
            render_route_map(route_df)

    # ── Downloads ─────────────────────────────────────────────
    neu_section_header("Downloads")
    dl1, dl2 = st.columns(2)

    with dl1:
        if selected_code != "— All Visitors —" and selected_code in visitor_options:
            db = get_db_session()
            try:
                buf = reporting_export_service.export_visitor_route_excel(
                    db=db, work_date=work_date,
                    visitor_id=visitor_options[selected_code],
                )
                st.download_button(
                    label=f"📥  Download Route — {selected_code}",
                    data=buf.getvalue(),
                    file_name=f"route_{work_date.isoformat()}_{selected_code}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            finally:
                db.close()

    with dl2:
        if visitor_options:
            all_buf = _export_all_routes(work_date, visitor_options)
            st.download_button(
                label="📥  Download All Routes",
                data=all_buf.getvalue(),
                file_name=f"all_routes_{work_date.isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # ── Visit results ─────────────────────────────────────────
    neu_section_header("Visit Results")
    visit_df = _load_visits(work_date)
    if visit_df.empty:
        st.info("No visit results submitted yet.")
    else:
        st.dataframe(visit_df, use_container_width=True)

    # ── Telesales queue ───────────────────────────────────────
    neu_section_header("Telesales Queue")
    if pending_queue:
        st.dataframe(pd.DataFrame(pending_queue), use_container_width=True)
    else:
        st.info("No pending telesales follow-ups.")
