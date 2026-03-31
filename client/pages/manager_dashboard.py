import os
from datetime import date
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_card, neu_metric, neu_section_header
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import (
    assignment_service,
    import_service,
    import_users_service,
    import_visitors_service,
    reporting_export_service,
    routing_service,
    telesales_service,
    visit_service,
)
from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.db.database import get_db_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_uploaded_excel(uploaded_file, import_func, label: str) -> None:
    """Run an Excel import through a temp file and display result."""
    if uploaded_file is None:
        st.warning(f"Please upload an Excel file for {label}.")
        return
    temp_path = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(uploaded_file.getbuffer())
            temp_path = tmp.name
        db = get_db_session()
        try:
            count = import_func(temp_path, db)
        finally:
            db.close()
        st.success(f"{count} rows processed for {label}.")
    except Exception as exc:
        st.error(f"{label} import failed: {exc}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _load_assignments(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id, a.work_date,
            v.visitor_code, s.store_code, s.store_name,
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


def _load_visitor_route_map(work_date: date, visitor_id: int) -> pd.DataFrame:
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


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render_manager_dashboard(current_user: dict) -> None:
    st.markdown(
        '<h2 style="margin-bottom:0.2rem;">Manager Dashboard</h2>',
        unsafe_allow_html=True,
    )

    # ── Work date ─────────────────────────────────────────────
    work_date = st.date_input("📅  Work Date", value=date.today())

    # ── Data imports ──────────────────────────────────────────
    with st.expander("📂  Data Imports", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            stores_file = st.file_uploader("Stores Excel", type=["xlsx"], key="stores_import")
            users_file = st.file_uploader("Users Excel", type=["xlsx"], key="users_import")
        with col2:
            visitors_file = st.file_uploader("Visitors Excel", type=["xlsx"], key="visitors_import")
            daily_file = st.file_uploader("Daily Status Excel", type=["xlsx"], key="daily_import")

        bc1, bc2, bc3, bc4 = st.columns(4)
        with bc1:
            if st.button("Import Stores"):
                _import_uploaded_excel(stores_file, import_service.import_stores_from_excel, "stores")
        with bc2:
            if st.button("Import Users"):
                _import_uploaded_excel(users_file, import_users_service.import_users_from_excel, "users")
        with bc3:
            if st.button("Import Visitors"):
                _import_uploaded_excel(
                    visitors_file,
                    import_visitors_service.import_visitor_profiles_from_excel,
                    "visitor profiles",
                )
        with bc4:
            if st.button("Import Daily Status"):
                _import_uploaded_excel(
                    daily_file, import_daily_visitor_statuses_from_excel, "daily visitor status"
                )

    # ── Route operations ──────────────────────────────────────
    neu_section_header("Route Operations")
    rc1, rc2, rc3, rc4 = st.columns(4)

    with rc1:
        if st.button("⚙️  Generate Draft", use_container_width=True):
            db = get_db_session()
            try:
                summary = assignment_service.generate_draft_assignments(
                    db=db, work_date=work_date,
                    manager_user_id=current_user["id"],
                    replace_existing_draft=True,
                )
                st.success(f"Draft done: {summary['created_assignments']} assignments")
            except Exception as exc:
                st.error(f"Draft failed: {exc}")
            finally:
                db.close()

    with rc2:
        if st.button("🗺️  Generate Route Order", use_container_width=True):
            db = get_db_session()
            try:
                count = routing_service.apply_routes_for_work_date(
                    db=db, work_date=work_date,
                    planner=routing_service.NearestNeighborRoutePlanner(),
                )
                st.success(f"Route order generated for {count} assignments.")
            except Exception as exc:
                st.error(f"Route generation failed: {exc}")
            finally:
                db.close()

    with rc3:
        if st.button("📤  Publish Routes", use_container_width=True):
            db = get_db_session()
            try:
                count = assignment_service.publish_assignments(
                    db=db, work_date=work_date,
                    manager_user_id=current_user["id"],
                )
                st.success(f"{count} assignments published.")
            except Exception as exc:
                st.error(f"Publish failed: {exc}")
            finally:
                db.close()

    with rc4:
        if st.button("🔒  Finalize Unsubmitted", use_container_width=True):
            db = get_db_session()
            try:
                count = visit_service.finalize_unsubmitted_assignments(
                    db=db, work_date=work_date,
                    actor_user_id=current_user["id"],
                )
                st.success(f"{count} unsubmitted finalized as red.")
            except Exception as exc:
                st.error(f"Finalize failed: {exc}")
            finally:
                db.close()

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

    # ── Assignments table ─────────────────────────────────────
    neu_section_header("Assignments")
    assignment_df = _load_assignments(work_date)
    if assignment_df.empty:
        st.info("No assignments for this date.")
    else:
        st.dataframe(assignment_df, use_container_width=True)

    # ── Telesales queue ───────────────────────────────────────
    neu_section_header("Telesales Pending Queue")
    if pending_queue:
        st.dataframe(pd.DataFrame(pending_queue), use_container_width=True)
    else:
        st.info("No pending telesales items.")

    # ── Route map ─────────────────────────────────────────────
    visitor_options = _get_visitor_options(work_date)

    neu_section_header("Route Map")
    selected_code = st.selectbox(
        "Select Visitor for Route Map & Export",
        options=[""] + list(visitor_options.keys()),
    )

    if selected_code:
        selected_id = visitor_options[selected_code]
        route_df = _load_visitor_route_map(work_date, selected_id)
        if route_df.empty:
            st.info("No route rows for selected visitor/date.")
        else:
            render_route_map(route_df)

    # ── Exports ───────────────────────────────────────────────
    neu_section_header("Exports")
    exp1, exp2 = st.columns(2)

    with exp1:
        if selected_code:
            db = get_db_session()
            try:
                route_buf = reporting_export_service.export_visitor_route_excel(
                    db=db, work_date=work_date,
                    visitor_id=visitor_options[selected_code],
                )
                st.download_button(
                    label=f"📥  Download Route — {selected_code}",
                    data=route_buf.getvalue(),
                    file_name=f"route_{work_date.isoformat()}_{selected_code}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            finally:
                db.close()

    with exp2:
        db = get_db_session()
        try:
            summary_buf = reporting_export_service.export_manager_daily_summary_excel(
                db=db, work_date=work_date,
            )
        finally:
            db.close()
        st.download_button(
            label="📥  Download Daily Summary",
            data=summary_buf.getvalue(),
            file_name=f"summary_{work_date.isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
